# Logo detection logic
from bs4 import BeautifulSoup
import logging
import base64
import requests
from urllib.parse import urljoin
from PIL import Image
from io import BytesIO
import re
from typing import Dict, Optional, List

from app.services.ai_logo_detector import AILogoDetector
from app.services.fallback_logo_detector import FallbackLogoDetector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LogoExtractor:
    """Service for extracting logos from websites"""
    
    def __init__(self):
        self.session = requests.Session()
        self.ai_logo_detector = AILogoDetector()
        self.fallback_detector = FallbackLogoDetector()
    
    async def extract_logo(self, html_content: str, screenshot: Optional[str] = None, base_url: str = "") -> Dict:
        """
        Extract logo from website content
        
        Args:
            html_content: HTML content of the website
            screenshot: Base64 encoded screenshot (if available)
            base_url: Original URL of the website
            
        Returns:
            Dictionary containing logo information
        """
        logger.info(f"Extracting logo from {base_url}")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Strategy 1: Check meta tags (OpenGraph, Twitter, etc.)
        logo_url = self._extract_from_meta_tags(soup, base_url)
        if logo_url:
            return await self._process_logo(logo_url, base_url, "meta-tag")
        
        # Strategy 2: Look for logo in image tags
        logo_url = self._extract_from_image_tags(soup, base_url)
        if logo_url:
            return await self._process_logo(logo_url, base_url, "img-tag")
        
        # Strategy 3: Check for favicon or apple-touch-icon
        logo_url = self._extract_from_link_tags(soup, base_url)
        if logo_url:
            return await self._process_logo(logo_url, base_url, "link-tag")
        
        # Strategy 4: Look for SVG logos
        svg_logo = self._extract_svg_logo(soup)
        if svg_logo:
            # Convert SVG to PNG and encode it
            # This would require additional implementation
            # For now, we'll return the SVG as is
            return {
                "url": None,
                "image": svg_logo,
                "width": None,
                "height": None,
                "source": "svg"
            }
        
        # Strategy 5: Use the screenshot and AI to detect and extract the logo
        if screenshot and screenshot.startswith('data:image/'):
            logger.info("Using AI for logo detection from screenshot")
            
            # Try AI-based detection first
            detection_result = await self.ai_logo_detector.detect_logo_from_screenshot(screenshot)
            
            # If AI detection fails, use fallback heuristic detection
            if not detection_result.get("logo_detected") and "error" in detection_result:
                logger.info("AI detection failed, using fallback heuristic detection")
                detection_result = await self.fallback_detector.detect_logo_from_screenshot(screenshot)
            
            # If a logo was detected and we have bounding box coordinates
            if detection_result.get("logo_detected") and detection_result.get("bounding_box"):
                logger.info(f"Logo detected at {detection_result.get('location')}: {detection_result.get('description')}")
                
                # Visualize the detection (useful for debugging)
                if hasattr(self.ai_logo_detector, 'visualize_logo_detection'):
                    self.ai_logo_detector.visualize_logo_detection(
                        screenshot, 
                        detection_result["bounding_box"], 
                        "detected_logo_visualization.png"
                    )
                
                # Crop the logo from the screenshot
                # Use the appropriate detector for cropping
                if detection_result.get("detection_method", "").startswith("heuristic"):
                    cropped_logo = await self.fallback_detector.crop_logo_from_screenshot(
                        screenshot, 
                        detection_result["bounding_box"]
                    )
                else:
                    cropped_logo = await self.ai_logo_detector.crop_logo_from_screenshot(
                        screenshot, 
                        detection_result["bounding_box"]
                    )
                
                if cropped_logo:
                    # Try to estimate dimensions of the cropped logo
                    width, height = None, None
                    try:
                        # Extract dimensions from the bounding box
                        box = detection_result["bounding_box"]
                        width = int(box["x2"]) - int(box["x1"])
                        height = int(box["y2"]) - int(box["y1"])
                    except:
                        pass
                    
                    return {
                        "url": None,  # No direct URL as this is extracted from screenshot
                        "image": cropped_logo,
                        "width": width,
                        "height": height,
                        "source": detection_result.get("detection_method", "ai-detection"),
                        "description": detection_result.get("description")
                    }

        # If all strategies fail, return not found
        return {
            "url": None,
            "image": None,
            "width": None,
            "height": None,
            "source": "not-found"
        }
    
    def _extract_from_meta_tags(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract logo from meta tags"""
        # Check for Open Graph image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return urljoin(base_url, og_image['content'])
        
        # Check for Twitter image
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            return urljoin(base_url, twitter_image['content'])
        
        # Check for schema.org Organization logo
        schema_org = soup.find('script', type='application/ld+json')
        if schema_org:
            try:
                import json
                data = json.loads(schema_org.string)
                if isinstance(data, dict) and 'logo' in data:
                    return urljoin(base_url, data['logo'])
                elif isinstance(data, dict) and '@graph' in data:
                    for item in data['@graph']:
                        if isinstance(item, dict) and 'logo' in item:
                            return urljoin(base_url, item['logo'])
            except:
                pass
                
        return None
    
    def _extract_from_image_tags(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract logo from image tags"""
        # Look for images with 'logo' in various attributes
        logo_patterns = ['logo', 'brand', 'header-image', 'site-logo']
        
        for pattern in logo_patterns:
            # Check class attribute
            img = soup.find('img', class_=lambda x: x and pattern in x.lower())
            if img and img.get('src'):
                return urljoin(base_url, img['src'])
            
            # Check id attribute
            img = soup.find('img', id=lambda x: x and pattern in x.lower())
            if img and img.get('src'):
                return urljoin(base_url, img['src'])
            
            # Check alt attribute
            img = soup.find('img', alt=lambda x: x and pattern in x.lower())
            if img and img.get('src'):
                return urljoin(base_url, img['src'])
            
            # Check src attribute
            img = soup.find('img', src=lambda x: x and pattern in x.lower())
            if img:
                return urljoin(base_url, img['src'])
        
        # In a more complex implementation, we would:
        # 1. Look for common logo container patterns
        # 2. Analyze image sizes and positions
        # 3. Use heuristics to identify which image is most likely a logo
        
        return None
    
    def _extract_from_link_tags(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract logo from link tags (favicon, apple-touch-icon, etc.)"""
        # Check for apple-touch-icon (usually higher quality than favicon)
        apple_icon = soup.find('link', rel='apple-touch-icon')
        if apple_icon and apple_icon.get('href'):
            return urljoin(base_url, apple_icon['href'])
        
        # Check for favicon
        favicon = soup.find('link', rel='icon') or soup.find('link', rel='shortcut icon')
        if favicon and favicon.get('href'):
            return urljoin(base_url, favicon['href'])
        
        # If no explicit favicon link, try the default location
        return urljoin(base_url, '/favicon.ico')
    
    def _extract_svg_logo(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract SVG logo"""
        # Look for SVG elements that might be logos
        svg_logo = soup.find('svg', class_=lambda x: x and 'logo' in x.lower())
        if svg_logo:
            return str(svg_logo)
        
        # Look for SVG in common logo containers
        logo_container = soup.find(['div', 'a'], class_=lambda x: x and 'logo' in x.lower())
        if logo_container:
            svg = logo_container.find('svg')
            if svg:
                return str(svg)
        
        return None
    
    async def _process_logo(self, logo_url: str, base_url: str, source: str) -> Dict:
        """Process logo image and convert to PNG if needed"""
        try:
            # Download the image
            response = self.session.get(logo_url, timeout=10)
            response.raise_for_status()
            
            # Process the image
            img = Image.open(BytesIO(response.content))
            
            # Convert to PNG
            buffer = BytesIO()
            # If image has transparency (like a PNG), preserve it
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img.save(buffer, format="PNG")
            else:
                # Convert to RGB if needed (e.g., for JPEG)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(buffer, format="PNG")
            
            # Encode to base64
            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return {
                "url": logo_url,
                "image": f"data:image/png;base64,{img_str}",
                "width": img.width,
                "height": img.height,
                "source": source
            }
        except Exception as e:
            logger.error(f"Error processing logo {logo_url}: {str(e)}")
            return {
                "url": logo_url,
                "image": None,
                "width": None,
                "height": None,
                "source": source
            }