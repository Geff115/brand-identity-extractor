# Color extraction logic
from bs4 import BeautifulSoup
import logging
import re
from typing import List, Dict, Optional
import base64
from io import BytesIO
from PIL import Image
from colorthief import ColorThief
import binascii

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ColorExtractor:
    """Service for extracting brand colors from websites"""
    
    def __init__(self):
        pass
    
    async def extract_colors(self, html_content: str, logo_image: Optional[str] = None) -> List[Dict]:
        """
        Extract brand colors from website content and logo
        
        Args:
            html_content: HTML content of the website
            logo_image: Base64 encoded logo image (if available)
            
        Returns:
            List of color information dictionaries
        """
        colors = []
        
        # Strategy 1: Extract colors from logo
        if logo_image:
            logo_colors = self._extract_colors_from_logo(logo_image)
            colors.extend(logo_colors)
        
        # Strategy 2: Extract colors from CSS
        css_colors = self._extract_colors_from_css(html_content)
        colors.extend(css_colors)
        
        # Strategy 3: Extract colors from inline styles
        inline_colors = self._extract_colors_from_inline_styles(html_content)
        colors.extend(inline_colors)
        
        # Deduplicate colors and return
        return self._deduplicate_colors(colors)
    
    def _extract_colors_from_logo(self, logo_image: str) -> List[Dict]:
        """Extract dominant colors from logo"""
        try:
            # Parse base64 image
            if not logo_image or not logo_image.startswith('data:image/'):
                return []
            
            # Extract the base64 part
            base64_data = logo_image.split(',')[1]
            image_data = base64.b64decode(base64_data)
            
            # Use ColorThief to extract dominant colors
            image = BytesIO(image_data)
            color_thief = ColorThief(image)
            
            # Get dominant color
            dominant_color = color_thief.get_color(quality=1)
            
            # Get color palette (up to 5 colors)
            palette = color_thief.get_palette(color_count=5, quality=1)
            
            colors = []
            
            # Add dominant color
            hex_color = '#{:02x}{:02x}{:02x}'.format(*dominant_color)
            colors.append({
                "hex": hex_color,
                "rgb": list(dominant_color),
                "source": "logo-dominant"
            })
            
            # Add palette colors
            for i, color in enumerate(palette):
                hex_color = '#{:02x}{:02x}{:02x}'.format(*color)
                colors.append({
                    "hex": hex_color,
                    "rgb": list(color),
                    "source": f"logo-palette-{i+1}"
                })
            
            return colors
            
        except Exception as e:
            logger.error(f"Error extracting colors from logo: {str(e)}")
            return []
    
    def _extract_colors_from_css(self, html_content: str) -> List[Dict]:
        """Extract colors from CSS"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            colors = []
            
            # Look for style tags
            style_tags = soup.find_all('style')
            for style in style_tags:
                if style.string:
                    css_content = style.string
                    css_colors = self._parse_css_colors(css_content)
                    colors.extend(css_colors)
            
            # Look for link tags with CSS
            # In a more advanced implementation, we would download and parse external CSS files
            
            return colors
            
        except Exception as e:
            logger.error(f"Error extracting colors from CSS: {str(e)}")
            return []
    
    def _extract_colors_from_inline_styles(self, html_content: str) -> List[Dict]:
        """Extract colors from inline styles"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            colors = []
            
            # Common elements that might have brand colors
            brand_elements = [
                'header', 'nav', 'footer', 
                '.header', '.nav', '.footer', 
                '.brand', '.logo', '.site-title',
                '#header', '#nav', '#footer'
            ]
            
            for selector in brand_elements:
                elements = soup.select(selector)
                for element in elements:
                    if element.get('style'):
                        css_colors = self._parse_css_colors(element['style'])
                        for color in css_colors:
                            color['source'] = f"inline-{selector}"
                        colors.extend(css_colors)
            
            return colors
            
        except Exception as e:
            logger.error(f"Error extracting colors from inline styles: {str(e)}")
            return []
    
    def _parse_css_colors(self, css_content: str) -> List[Dict]:
        """Parse colors from CSS content"""
        colors = []
        
        # Match hex colors
        hex_pattern = r'#([0-9a-fA-F]{3}){1,2}\b'
        hex_colors = re.findall(hex_pattern, css_content)
        
        for hex_color in hex_colors:
            # Convert 3-digit hex to 6-digit
            if len(hex_color) == 3:
                hex_color = ''.join([c*2 for c in hex_color])
            
            # Convert hex to RGB
            rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
            
            colors.append({
                "hex": f"#{hex_color}",
                "rgb": rgb,
                "source": "css-hex"
            })
        
        # Match rgb/rgba colors
        rgb_pattern = r'rgb\((\d+),\s*(\d+),\s*(\d+)\)'
        rgb_colors = re.findall(rgb_pattern, css_content)
        
        for rgb_color in rgb_colors:
            rgb = [int(c) for c in rgb_color]
            hex_color = '#{:02x}{:02x}{:02x}'.format(*rgb)
            
            colors.append({
                "hex": hex_color,
                "rgb": rgb,
                "source": "css-rgb"
            })
        
        return colors
    
    def _deduplicate_colors(self, colors: List[Dict]) -> List[Dict]:
        """Deduplicate colors by hex value"""
        unique_colors = {}
        
        for color in colors:
            hex_color = color['hex'].lower()
            
            if hex_color not in unique_colors:
                unique_colors[hex_color] = color
            elif color['source'].startswith('logo'):
                # Prioritize logo colors
                unique_colors[hex_color] = color
        
        return list(unique_colors.values())