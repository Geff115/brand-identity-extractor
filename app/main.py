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
from app.services.health_check import HealthCheck
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
    rate_limit=int(os.getenv("RATE_LIMIT", "60")),  # 60 requests per hour by default
    window_size=int(os.getenv("RATE_WINDOW", "3600"))  # 1 hour window
)

# Create health checker
health_checker = HealthCheck()

# Dependency for the scraper
async def get_scraper():
    scraper = EnhancedWebScraper(use_cache=True)
    try:
        yield scraper
    finally:
        await scraper.close()

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # Generate a unique ID for this request
    request_id = str(uuid.uuid4())
    
    # Add the ID to the request state
    request.state.request_id = request_id
    
    # Process the request
    try:
        response = await call_next(request)
        
        # Add the request ID to the response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
    except Exception as e:
        # If an unhandled exception occurs, log it with the request ID
        logger.error(f"Unhandled error in request {request_id}: {str(e)}")
        
        # Create proper error response
        error_details = ErrorDetails(
            message=f"Internal server error: {str(e)}",
            category=ErrorCategory.SERVER,
            http_status=500,
            exception=e,
            context={"request_id": request_id, "path": request.url.path},
            trace_id=request_id
        )
        error_details.log()
        
        # Return JSON error response
        return JSONResponse(
            status_code=500,
            content={"error": error_details.to_dict()}
        )

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

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Generate a trace ID if not already in request state
    trace_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    # Create error details
    error_details = ErrorHandler.handle_exception(
        exc, 
        context={"path": request.url.path, "method": request.method}
    )
    error_details.trace_id = trace_id
    
    # Log the error
    error_details.log()
    
    # Return a consistent error response
    return JSONResponse(
        status_code=error_details.http_status,
        content={"error": error_details.to_dict()},
        headers={"X-Request-ID": trace_id}
    )

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Brand Identity Extractor API is running"}

@app.get("/health")
async def health_check():
    """
    Detailed health check endpoint
    
    Returns the status of all system components
    """
    # Check all services
    health_data = await health_checker.check_all_services(
        cache_service=cache_service,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Return 200 OK if all services are healthy, otherwise 503 Service Unavailable
    status_code = 200 if health_data["status"] == "healthy" else 503
    
    return JSONResponse(
        status_code=status_code,
        content=health_data
    )

@app.post("/extract", response_model=ExtractionResponse)
@with_circuit_breaker("scraper")
async def extract_brand_identity(
    request: ExtractionRequest,
    request_obj: Request,
    scraper: EnhancedWebScraper = Depends(get_scraper),
    x_api_key: Optional[str] = Header(None),
):
    """
    Extract brand logo and colors from a website
    """
    # Use request ID from middleware if available
    request_id = getattr(request_obj.state, "request_id", None)
    
    # Create context for error handling
    context = {
        "url": str(request.url),
        "request_id": request_id
    }
    
    # Use the error handler context manager
    async with ErrorHandler.try_catch_async(context=context):
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
        
        # Scrape the website with the headless browser - with circuit breaker protection
        try:
            html_content, screenshot = await scraper.scrape(url_str)
            if not html_content:
                error_details = ErrorDetails(
                    message="No content found at the provided URL",
                    category=ErrorCategory.RESOURCE,
                    http_status=404,
                    context=context
                )
                error_details.log()
                raise error_details.to_http_exception()
        except CircuitBreakerError as e:
            # Circuit breaker is open, use graceful degradation
            error_details = ErrorDetails(
                message="Service temporarily unavailable. Please try again later.",
                category=ErrorCategory.EXTERNAL_SERVICE,
                http_status=503,
                exception=e,
                context=context
            )
            error_details.log()
            raise error_details.to_http_exception()
        
        # Extract logo using both HTML and screenshot
        logo_extractor = LogoExtractor()
        logo_data = await ErrorHandler.with_error_handling(
            logo_extractor.extract_logo,
            html_content, screenshot, url_str,
            context={"step": "logo_extraction", **context},
            fallback_result={"url": None, "image": None, "width": None, "height": None, "source": "extraction-failed"},
            raise_error=False
        )
        
        # Extract basic colors (for backward compatibility)
        color_extractor = ColorExtractor()
        basic_colors = await ErrorHandler.with_error_handling(
            color_extractor.extract_colors,
            html_content, logo_data.get("image"),
            context={"step": "color_extraction", **context},
            fallback_result=[],
            raise_error=False
        )
        
        # Extract enhanced colors with semantic palette
        enhanced_color_extractor = EnhancedColorExtractor()
        enhanced_colors = await ErrorHandler.with_error_handling(
            enhanced_color_extractor.extract_colors,
            html_content, logo_data.get("image"),
            context={"step": "enhanced_color_extraction", **context},
            fallback_result=None,
            raise_error=False
        )
        
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

@app.delete("/cache")
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