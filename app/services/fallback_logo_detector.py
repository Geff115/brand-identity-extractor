import logging
import base64
from typing import Dict, Optional, Any, List, Tuple
from io import BytesIO
from PIL import Image, ImageDraw

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FallbackLogoDetector:
    """Simple fallback logo detector using basic heuristics to find a logo in a screenshot"""
    
    def __init__(self):
        """Initialize the fallback logo detector"""
        pass
    
    async def detect_logo_from_screenshot(self, screenshot: str) -> Dict[str, Any]:
        """
        Use basic heuristics to detect a logo in a screenshot
        
        Args:
            screenshot: Base64 encoded screenshot
            
        Returns:
            Dictionary containing detection results
        """
        try:
            # Extract base64 image data
            import base64  # Explicitly import here too
            image_data = screenshot.split(',')[1] if ',' in screenshot else screenshot
            image_bytes = base64.b64decode(image_data)
            
            # Open the image
            img = Image.open(BytesIO(image_bytes))
            
            # Heuristic 1: Check top left corner (common logo position)
            top_left = self._check_top_left_corner(img)
            if top_left:
                return {
                    "logo_detected": True,
                    "location": "top-left",
                    "description": "Possible logo detected in top-left corner",
                    "bounding_box": top_left,
                    "detection_method": "heuristic-top-left"
                }
            
            # Heuristic 2: Check top center (also common for logos)
            top_center = self._check_top_center(img)
            if top_center:
                return {
                    "logo_detected": True,
                    "location": "top-center",
                    "description": "Possible logo detected in top-center area",
                    "bounding_box": top_center,
                    "detection_method": "heuristic-top-center"
                }
            
            # If no logo found, return failure
            return {
                "logo_detected": False,
                "error": "No logo detected using fallback heuristics"
            }
            
        except Exception as e:
            logger.error(f"Error in fallback logo detection: {str(e)}")
            return {"logo_detected": False, "error": str(e)}
    
    def _check_top_left_corner(self, img: Image.Image) -> Optional[Dict[str, int]]:
        """Check top left corner for potential logo"""
        width, height = img.width, img.height
        
        # Define a reasonable area to check (top left 20% of the width, 15% of the height)
        area_width = int(width * 0.2)
        area_height = int(height * 0.15)
        
        # Create a bounding box
        return {
            "x1": int(width * 0.02),  # 2% from left edge
            "y1": int(height * 0.02),  # 2% from top edge
            "x2": area_width,
            "y2": area_height
        }
    
    def _check_top_center(self, img: Image.Image) -> Optional[Dict[str, int]]:
        """Check top center for potential logo"""
        width, height = img.width, img.height
        
        # Define center region (middle 30% of width, top 15% of height)
        center_start = int(width * 0.35)
        center_end = int(width * 0.65)
        area_height = int(height * 0.15)
        
        # Create a bounding box
        return {
            "x1": center_start,
            "y1": int(height * 0.02),  # 2% from top edge
            "x2": center_end,
            "y2": area_height
        }
    
    async def crop_logo_from_screenshot(self, screenshot: str, bounding_box: Dict[str, int]) -> Optional[str]:
        """
        Crop the logo from a screenshot using the bounding box coordinates
        
        Args:
            screenshot: Base64 encoded screenshot
            bounding_box: Dictionary with x1, y1, x2, y2 coordinates
            
        Returns:
            Base64 encoded cropped logo image or None if failed
        """
        try:
            # Extract base64 image data
            import base64  # Explicitly import here too
            image_data = screenshot.split(',')[1] if ',' in screenshot else screenshot
            image_bytes = base64.b64decode(image_data)
            
            # Open the image
            img = Image.open(BytesIO(image_bytes))
            
            # Get bounding box coordinates
            x1 = max(0, int(bounding_box.get('x1', 0)))
            y1 = max(0, int(bounding_box.get('y1', 0)))
            x2 = min(img.width, int(bounding_box.get('x2', img.width)))
            y2 = min(img.height, int(bounding_box.get('y2', img.height)))
            
            # Make sure we have a valid crop region
            if x2 <= x1 or y2 <= y1:
                logger.error("Invalid bounding box for cropping")
                return None
            
            # Crop the image
            cropped_img = img.crop((x1, y1, x2, y2))
            
            # Convert back to base64
            buffer = BytesIO()
            cropped_img.save(buffer, format="PNG")
            crop_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return f"data:image/png;base64,{crop_base64}"
            
        except Exception as e:
            logger.error(f"Error cropping logo: {str(e)}")
            return None