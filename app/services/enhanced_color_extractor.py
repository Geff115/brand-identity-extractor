import logging
import re
import math
import colorsys
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from io import BytesIO
import base64

from bs4 import BeautifulSoup
from PIL import Image
from colorthief import ColorThief

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedColorExtractor:
    """Enhanced service for extracting and categorizing brand colors"""
    
    # Color name mapping based on common color names
    COLOR_NAMES = {
        # Reds
        (255, 0, 0): "red",
        (220, 20, 60): "crimson",
        (178, 34, 34): "firebrick",
        (139, 0, 0): "dark red",
        (205, 92, 92): "indian red",
        # Oranges
        (255, 165, 0): "orange",
        (255, 140, 0): "dark orange",
        (255, 127, 80): "coral",
        (255, 99, 71): "tomato",
        # Yellows
        (255, 255, 0): "yellow",
        (255, 215, 0): "gold",
        (240, 230, 140): "khaki",
        # Greens
        (0, 128, 0): "green",
        (0, 255, 0): "lime",
        (34, 139, 34): "forest green",
        (50, 205, 50): "lime green",
        (152, 251, 152): "pale green",
        (143, 188, 143): "dark sea green",
        # Blues
        (0, 0, 255): "blue",
        (0, 0, 139): "dark blue",
        (0, 191, 255): "deep sky blue",
        (135, 206, 235): "sky blue",
        (70, 130, 180): "steel blue",
        (100, 149, 237): "cornflower blue",
        # Purples
        (128, 0, 128): "purple",
        (153, 50, 204): "dark orchid",
        (148, 0, 211): "dark violet",
        (138, 43, 226): "blue violet",
        (147, 112, 219): "medium purple",
        # Pinks
        (255, 192, 203): "pink",
        (255, 105, 180): "hot pink",
        (219, 112, 147): "pale violet red",
        # Browns
        (165, 42, 42): "brown",
        (160, 82, 45): "sienna",
        (210, 105, 30): "chocolate",
        # Neutrals
        (0, 0, 0): "black",
        (128, 128, 128): "gray",
        (192, 192, 192): "silver",
        (245, 245, 245): "white smoke",
        (255, 255, 255): "white",
    }
    
    def __init__(self):
        """Initialize the enhanced color extractor"""
        pass
    
    async def extract_colors(self, html_content: str, logo_image: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract and categorize colors from website content and logo
        
        Args:
            html_content: HTML content of the website
            logo_image: Base64 encoded logo image (if available)
            
        Returns:
            Dictionary containing organized color information
        """
        all_colors = []
        
        # Step 1: Extract colors from the logo (most important for brand colors)
        logo_colors = []
        if logo_image:
            logo_colors = self._extract_colors_from_logo(logo_image)
            all_colors.extend(logo_colors)
        
        # Step 2: Extract colors from CSS
        css_colors = []
        if html_content:
            css_colors = self._extract_colors_from_css(html_content)
            all_colors.extend(css_colors)
        
        # Step 3: Extract colors from inline styles
        inline_colors = []
        if html_content:
            inline_colors = self._extract_colors_from_inline_styles(html_content)
            all_colors.extend(inline_colors)
        
        # Step 4: Organize colors into a palette
        palette = self._organize_color_palette(all_colors)
        
        return {
            "palette": palette,
            "all_colors": {
                "logo": logo_colors,
                "css": css_colors,
                "inline": inline_colors
            }
        }
    
    def _extract_colors_from_logo(self, logo_image: str) -> List[Dict]:
        """Extract and categorize colors from logo"""
        try:
            # Parse base64 image
            if not logo_image or not isinstance(logo_image, str) or not logo_image.startswith('data:image/'):
                return []
            
            # Extract the base64 part
            base64_data = logo_image.split(',')[1]
            image_data = base64.b64decode(base64_data)
            
            # Use ColorThief to extract dominant colors
            image = BytesIO(image_data)
            color_thief = ColorThief(image)
            
            # Get dominant color
            dominant_color = color_thief.get_color(quality=1)
            
            # Get color palette (up to 8 colors for more detailed palette)
            palette = color_thief.get_palette(color_count=8, quality=1)
            
            colors = []
            
            # Add dominant color
            hex_color = '#{:02x}{:02x}{:02x}'.format(*dominant_color)
            colors.append({
                "hex": hex_color,
                "rgb": list(dominant_color),
                "source": "logo-dominant",
                "name": self._get_closest_color_name(dominant_color),
                "luminance": self._calculate_luminance(dominant_color),
                "hsv": self._rgb_to_hsv(dominant_color)
            })
            
            # Add palette colors
            for i, color in enumerate(palette):
                hex_color = '#{:02x}{:02x}{:02x}'.format(*color)
                colors.append({
                    "hex": hex_color,
                    "rgb": list(color),
                    "source": f"logo-palette-{i+1}",
                    "name": self._get_closest_color_name(color),
                    "luminance": self._calculate_luminance(color),
                    "hsv": self._rgb_to_hsv(color)
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
                    css_colors = self._parse_css_colors(css_content, "css")
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
                '#header', '#nav', '#footer',
                'button', '.btn', '.button',
                'a', 'h1', 'h2', 'h3'
            ]
            
            for selector in brand_elements:
                elements = soup.select(selector)
                for element in elements:
                    if element.get('style'):
                        css_colors = self._parse_css_colors(element['style'], f"inline-{selector}")
                        colors.extend(css_colors)
            
            return colors
            
        except Exception as e:
            logger.error(f"Error extracting colors from inline styles: {str(e)}")
            return []
    
    def _parse_css_colors(self, css_content: str, source: str) -> List[Dict]:
        """Parse colors from CSS content with enhanced detection"""
        colors = []
        
        # Match hex colors (both 3 and 6 digit formats)
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
                "source": f"{source}-hex",
                "name": self._get_closest_color_name(rgb),
                "luminance": self._calculate_luminance(rgb),
                "hsv": self._rgb_to_hsv(rgb)
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
                "source": f"{source}-rgb",
                "name": self._get_closest_color_name(rgb),
                "luminance": self._calculate_luminance(rgb),
                "hsv": self._rgb_to_hsv(rgb)
            })
        
        # Match rgba colors
        rgba_pattern = r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d\.]+)\)'
        rgba_colors = re.findall(rgba_pattern, css_content)
        
        for rgba_color in rgba_colors:
            rgb = [int(c) for c in rgba_color[:3]]
            alpha = float(rgba_color[3])
            
            # Skip fully transparent colors
            if alpha < 0.1:
                continue
                
            hex_color = '#{:02x}{:02x}{:02x}'.format(*rgb)
            
            colors.append({
                "hex": hex_color,
                "rgb": rgb,
                "alpha": alpha,
                "source": f"{source}-rgba",
                "name": self._get_closest_color_name(rgb),
                "luminance": self._calculate_luminance(rgb),
                "hsv": self._rgb_to_hsv(rgb)
            })
        
        # Match HSL colors
        hsl_pattern = r'hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)'
        hsl_colors = re.findall(hsl_pattern, css_content)
        
        for hsl_color in hsl_colors:
            # Convert HSL to RGB
            h = int(hsl_color[0]) / 360.0
            s = int(hsl_color[1]) / 100.0
            l = int(hsl_color[2]) / 100.0
            
            r, g, b = self._hsl_to_rgb(h, s, l)
            rgb = [int(r * 255), int(g * 255), int(b * 255)]
            hex_color = '#{:02x}{:02x}{:02x}'.format(*rgb)
            
            colors.append({
                "hex": hex_color,
                "rgb": rgb,
                "source": f"{source}-hsl",
                "name": self._get_closest_color_name(rgb),
                "luminance": self._calculate_luminance(rgb),
                "hsv": self._rgb_to_hsv(rgb)
            })
        
        return colors
    
    def _organize_color_palette(self, colors: List[Dict]) -> Dict[str, Any]:
        """Organize colors into a meaningful palette with semantic naming"""
        # Return empty palette if no colors
        if not colors:
            return {
                "primary": None,
                "secondary": None,
                "accent": None,
                "background": None,
                "text": None,
                "additional": []
            }
        
        # Step 1: Deduplicate colors by hex value
        unique_colors = {}
        for color in colors:
            hex_value = color['hex'].lower()
            
            # Prioritize logo colors
            if hex_value not in unique_colors or color['source'].startswith('logo'):
                unique_colors[hex_value] = color
        
        # Convert back to list
        color_list = list(unique_colors.values())
        
        # Step 2: Sort colors by frequency and source importance
        # Count occurrences of each color across all sources
        color_counts = Counter([c['hex'].lower() for c in colors])
        
        # Add count to each color
        for color in color_list:
            color['count'] = color_counts[color['hex'].lower()]
        
        # Sort by source and count
        def color_sort_key(color):
            # Logo colors get highest priority
            if color['source'].startswith('logo'):
                return (0, -color['count'])
            # CSS colors next
            elif color['source'].startswith('css'):
                return (1, -color['count'])
            # Then inline styles
            else:
                return (2, -color['count'])
        
        color_list.sort(key=color_sort_key)
        
        # Step 3: Classify colors by role
        # Get color with highest luminance for background
        background_color = max(color_list, key=lambda c: c['luminance'])
        
        # Get color with lowest luminance for text
        text_color = min(color_list, key=lambda c: c['luminance'])
        
        # Primary is typically the most frequent color that's not background or text
        primary_candidates = [c for c in color_list if c != background_color and c != text_color]
        primary_color = primary_candidates[0] if primary_candidates else None
        
        # Secondary is the second most frequent color that's not primary, background or text
        secondary_candidates = [c for c in primary_candidates if c != primary_color]
        secondary_color = secondary_candidates[0] if secondary_candidates else None
        
        # Accent is typically a contrasting color to primary
        if primary_color:
            # Find color with most different hue from primary
            primary_hsv = primary_color['hsv']
            accent_color = max(
                [c for c in color_list if c != primary_color and c != secondary_color 
                 and c != background_color and c != text_color],
                key=lambda c: abs(c['hsv'][0] - primary_hsv[0]),
                default=None
            )
        else:
            accent_color = None
        
        # Additional colors are all remaining colors
        used_colors = {c['hex'] for c in [primary_color, secondary_color, accent_color, background_color, text_color] if c}
        additional_colors = [c for c in color_list if c['hex'] not in used_colors]
        
        # Step 4: Construct the palette
        palette = {
            "primary": primary_color,
            "secondary": secondary_color,
            "accent": accent_color,
            "background": background_color,
            "text": text_color,
            "additional": additional_colors
        }
        
        return palette
    
    def _get_closest_color_name(self, rgb: List[int]) -> str:
        """Get the closest named color to the given RGB value"""
        # If exact match, return it
        if tuple(rgb) in self.COLOR_NAMES:
            return self.COLOR_NAMES[tuple(rgb)]
        
        # Find closest color by Euclidean distance
        min_distance = float('inf')
        closest_name = "custom"
        
        for color_rgb, name in self.COLOR_NAMES.items():
            # Calculate Euclidean distance in RGB space
            distance = sum((a - b) ** 2 for a, b in zip(rgb, color_rgb)) ** 0.5
            if distance < min_distance:
                min_distance = distance
                closest_name = name
        
        # If distance is too large, it's a custom color
        if min_distance > 60:  # Threshold for considering it a custom color
            return "custom"
            
        return closest_name
    
    def _calculate_luminance(self, rgb: List[int]) -> float:
        """Calculate perceived luminance of a color (for determining brightness)"""
        # Formula: 0.299*R + 0.587*G + 0.114*B
        return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
    
    def _rgb_to_hsv(self, rgb: List[int]) -> List[float]:
        """Convert RGB to HSV color space"""
        r, g, b = [x / 255.0 for x in rgb]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        # Convert H to degrees
        h = h * 360
        # Convert S and V to percentages
        s = s * 100
        v = v * 100
        return [h, s, v]
    
    def _hsl_to_rgb(self, h: float, s: float, l: float) -> Tuple[float, float, float]:
        """Convert HSL to RGB color space"""
        return colorsys.hls_to_rgb(h, l, s)