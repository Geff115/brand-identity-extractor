# FastAPI Application
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import HttpUrl
import uvicorn

from app.services.scraper import WebScraper
from app.services.logo_extractor import LogoExtractor
from app.services.color_extractor import ColorExtractor
from app.models.schemas import ExtractionResponse, ExtractionRequest, LogoData

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

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Brand Identity Extractor API is running"}

@app.post("/extract", response_model=ExtractionResponse)
async def extract_brand_identity(request: ExtractionRequest):
    """
    Extract brand logo and colors from a website
    """
    try:
        scraper = WebScraper()
        html_content, screenshot = await scraper.scrape(str(request.url))
        if not html_content:
            raise HTTPException(status_code=404, detail="No content found at the provided URL")
        
        # Screenshot is optional in our current implementation
        
        logo_extractor = LogoExtractor()
        logo_data = await logo_extractor.extract_logo(html_content, screenshot, str(request.url))
        
        # Make logo optional - don't raise an error if not found
        
        color_extractor = ColorExtractor()
        colors = await color_extractor.extract_colors(html_content, logo_data.get("image"))
        
        # Create response with proper handling of logo data
        logo_model = None
        if logo_data and logo_data.get("source"):
            try:
                logo_model = LogoData(
                    url=logo_data.get("url"),
                    image=logo_data.get("image"),
                    width=logo_data.get("width"),
                    height=logo_data.get("height"),
                    source=logo_data.get("source", "unknown")
                )
            except Exception as e:
                print(f"Error creating LogoData: {str(e)}")
                # Continue without logo data
        
        return ExtractionResponse(
            url=request.url,
            logo=logo_model,
            colors=colors,
            success=True,
            message="Extraction completed successfully"
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)