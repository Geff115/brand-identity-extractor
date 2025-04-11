# FastAPI Application
from fastapi import FastAPI, HTTPException, Query, Depends, Request, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import HttpUrl
import uvicorn
import os
import logging
import uuid
import traceback
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from app.services.scraper import WebScraper
from app.services.logo_extractor import LogoExtractor
from app.services.color_extractor import ColorExtractor
from app.services.enhanced_color_extractor import EnhancedColorExtractor
from app.services.enhanced_scraper import EnhancedWebScraper
from app.services.cache_service import CacheService
from app.services.rate_limiter import RateLimiter
from app.services.circuit_breaker import with_circuit_breaker, CircuitBreakerError
from app.services.error_handler import ErrorHandler, ErrorDetails, ErrorCategory
from app.models.schemas import ExtractionResponse, ExtractionRequest, LogoData, ColorData, EnhancedColorData

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Brand Identity Extractor API",
    description="API for extracting brand logos and colors from websites",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins, might need to adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
# Get Redis URL from environment or use default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create cache service
cache_service = CacheService(redis_url=REDIS_URL)

# Create rate limiter
rate_limiter = RateLimiter(
    redis_url=REDIS_URL,
    rate_limit=60,  # 60 requests per hour by default
    window_size=3600  # 1 hour window
)

# Dependency for the scraper
async def get_scraper():
    scraper = EnhancedWebScraper(use_cache=True)
    try:
        yield scraper
    finally:
        await scraper.close()

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for non-API endpoints
    if not request.url.path.startswith("/extract"):
        return await call_next(request)
    
    # Get client identifier (IP address or API key)
    client_id = request.client.host  # Default to IP address
    
    # If API key is available, use that instead
    api_key = request.headers.get("X-API-Key")
    if api_key:
        client_id = api_key
    
    # Check rate limit
    is_allowed, rate_info = await rate_limiter.check_rate_limit(client_id)
    
    # Add rate limit headers to the response
    response = await call_next(request)
    response.headers["X-Rate-Limit-Limit"] = str(rate_info["limit"])
    response.headers["X-Rate-Limit-Remaining"] = str(rate_info["remaining"])
    response.headers["X-Rate-Limit-Reset"] = str(rate_info["reset"])
    
    # If rate limit exceeded, return 429 Too Many Requests
    if not is_allowed:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded",
                "rate_limit": rate_info
            }
        )
    
    return response

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Brand Identity Extractor API is running"}

@app.post("/extract", response_model=ExtractionResponse)
async def extract_brand_identity(
    request: ExtractionRequest, 
    scraper: EnhancedWebScraper = Depends(get_scraper),
    x_api_key: Optional[str] = Header(None)
):
    """
    Extract brand logo and colors from a website
    """
    try:
        # Create cache key based on URL
        url_str = str(request.url)
        cache_key = cache_service.create_key("extract", url_str)
        
        # Check cache first
        cached_result = await cache_service.get(cache_key)
        if cached_result:
            # Log cache hit
            logger.info(f"Cache hit for {url_str}")
            
            # Convert cached result to response model
            try:
                # Create a proper ExtractionResponse from the cached dictionary
                return ExtractionResponse(
                    url=cached_result["url"],
                    logo=LogoData(**cached_result["logo"]) if cached_result.get("logo") else None,
                    colors=[ColorData(**color) for color in cached_result["colors"]],
                    enhanced_colors=EnhancedColorData(**cached_result["enhanced_colors"]) if cached_result.get("enhanced_colors") else None,
                    success=cached_result["success"],
                    message=cached_result.get("message", "Cached response")
                )
            except Exception as e:
                logger.error(f"Error deserializing cached result: {str(e)}")
                # If there's an error with the cached data, continue with a fresh extraction
        
        # Log cache miss
        logger.info(f"Cache miss for {url_str}, extracting fresh data")
        
        # Scrape the website with the headless browser
        html_content, screenshot = await scraper.scrape(url_str)
        if not html_content:
            raise HTTPException(status_code=404, detail="No content found at the provided URL")
        
        # Extract logo using both HTML and screenshot
        logo_extractor = LogoExtractor()
        logo_data = await logo_extractor.extract_logo(html_content, screenshot, url_str)
        
        # Extract basic colors (for backward compatibility)
        color_extractor = ColorExtractor()
        basic_colors = await color_extractor.extract_colors(html_content, logo_data.get("image"))
        
        # Extract enhanced colors with semantic palette
        enhanced_color_extractor = EnhancedColorExtractor()
        enhanced_colors = await enhanced_color_extractor.extract_colors(html_content, logo_data.get("image"))
        
        # Create response with proper handling of logo data
        logo_model = None
        if logo_data and logo_data.get("source"):
            try:
                logo_model = LogoData(
                    url=logo_data.get("url"),
                    image=logo_data.get("image"),
                    width=logo_data.get("width"),
                    height=logo_data.get("height"),
                    source=logo_data.get("source", "unknown"),
                    description=logo_data.get("description")
                )
            except Exception as e:
                logger.error(f"Error creating LogoData: {str(e)}")
                # Continue without logo data
        
        # Create the response
        response = ExtractionResponse(
            url=request.url,
            logo=logo_model,
            colors=basic_colors,
            enhanced_colors=enhanced_colors,
            success=True,
            message="Extraction completed successfully"
        )
        
        # Create a proper serializable dictionary for caching
        if response.enhanced_colors:
            enhanced_colors_dict = {
                "palette": {},
                "all_colors": {}
            }
            
            # Handle palette
            palette = response.enhanced_colors.palette
            if palette:
                enhanced_colors_dict["palette"] = {
                    "primary": palette.primary.dict() if palette.primary else None,
                    "secondary": palette.secondary.dict() if palette.secondary else None,
                    "accent": palette.accent.dict() if palette.accent else None,
                    "background": palette.background.dict() if palette.background else None,
                    "text": palette.text.dict() if palette.text else None,
                    "additional": [color.dict() for color in palette.additional] if palette.additional else []
                }
            
            # Handle all_colors
            all_colors = response.enhanced_colors.all_colors
            if all_colors:
                enhanced_colors_dict["all_colors"] = {
                    k: [color.dict() for color in v] for k, v in all_colors.items()
                }
        else:
            enhanced_colors_dict = None
            
        # Create the response dict
        response_dict = {
            "url": str(response.url),  # Convert HttpUrl to string
            "logo": response.logo.dict() if response.logo else None,
            "colors": [color.dict() for color in response.colors],
            "enhanced_colors": enhanced_colors_dict,
            "success": response.success,
            "message": response.message
        }

        # Cache the response
        await cache_service.set(cache_key, response_dict)
        
        return response
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error processing request: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.delete("/cache", status_code=204)
async def clear_cache(admin_key: Optional[str] = Header(None), admin_key_param: Optional[str] = Query(None, alias="admin_key")):
    """
    Clear the API cache (admin only)
    
    Requires the X-Admin-Key header or admin_key query parameter with the correct admin key
    """
    # Load environment variables if not already loaded
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check admin key (in production, use a more secure method)
    expected_key = os.getenv("ADMIN_KEY", "admin-secret-key")
    logger.info(f"Expected admin key: {expected_key[:5]}...{expected_key[-5:]} (length: {len(expected_key)})")
    
    # Allow the key to be passed either as a header or query parameter
    provided_key = admin_key or admin_key_param
    
    if not provided_key:
        logger.warning("Cache clear attempt with missing admin key")
        raise HTTPException(status_code=401, detail="Missing admin key")
    
    logger.info(f"Provided admin key: {provided_key[:5]}...{provided_key[-5:]} (length: {len(provided_key)})")
        
    if provided_key != expected_key:
        logger.warning(f"Keys do not match: Expected {expected_key[:5]}... vs Provided {provided_key[:5]}...")
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    # Clear the cache
    success = await cache_service.clear_all()
    if success:
        logger.info("Cache cleared successfully")
        return {"message": "Cache cleared successfully"}
    else:
        logger.error("Failed to clear cache")
        raise HTTPException(status_code=500, detail="Failed to clear cache")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)