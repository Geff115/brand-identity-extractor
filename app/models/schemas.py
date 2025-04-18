# Pydantic models
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, HttpUrl, Field, validator

class ExtractionRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL of the website to extract brand identity from")
    
class LogoData(BaseModel):
    url: Optional[str] = Field(None, description="URL of the extracted logo")
    image: Optional[str] = Field(None, description="Base64 encoded PNG image of the logo")
    width: Optional[int] = Field(None, description="Width of the logo in pixels")
    height: Optional[int] = Field(None, description="Height of the logo in pixels")
    source: str = Field(..., description="How the logo was extracted (e.g., 'meta-tag', 'img-tag', 'ai-detection')")
    description: Optional[str] = Field(None, description="Description of the logo (from AI detection)")
    
    # Validators to handle potential None values
    @validator('source', pre=True)
    def validate_source(cls, v):
        return v or "unknown"

class ColorData(BaseModel):
    hex: str = Field(..., description="Hex code of the color")
    rgb: List[int] = Field(..., description="RGB values of the color")
    source: str = Field(..., description="Source of the color (e.g., 'logo', 'css', 'dominant')")
    name: Optional[str] = Field(None, description="Human-friendly name of the color")
    luminance: Optional[float] = Field(None, description="Perceived luminance (brightness) of the color")
    hsv: Optional[List[float]] = Field(None, description="HSV values of the color")
    
class PaletteData(BaseModel):
    primary: Optional[ColorData] = Field(None, description="Primary brand color")
    secondary: Optional[ColorData] = Field(None, description="Secondary brand color")
    accent: Optional[ColorData] = Field(None, description="Accent color for highlights")
    background: Optional[ColorData] = Field(None, description="Background color")
    text: Optional[ColorData] = Field(None, description="Text color")
    additional: List[ColorData] = Field(default_factory=list, description="Additional colors in the palette")

class EnhancedColorData(BaseModel):
    palette: PaletteData = Field(..., description="Organized color palette with semantic roles")
    all_colors: Dict[str, List[ColorData]] = Field(..., description="All extracted colors by source")
    
class ExtractionResponse(BaseModel):
    url: HttpUrl = Field(..., description="Original URL requested")
    logo: Optional[LogoData] = Field(None, description="Extracted logo information")
    colors: List[ColorData] = Field(default_factory=list, description="Basic extracted brand colors (for backward compatibility)")
    enhanced_colors: Optional[EnhancedColorData] = Field(None, description="Enhanced color extraction with semantic palette")
    success: bool = Field(..., description="Whether the extraction was successful")
    message: Optional[str] = Field(None, description="Additional information about the extraction")