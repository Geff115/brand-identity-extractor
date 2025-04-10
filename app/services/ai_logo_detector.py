import logging
import json
import base64
import os
from typing import Dict, Optional, Any
import aiohttp
from PIL import Image, ImageDraw
from io import BytesIO

from app.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_TOKENS, LOGO_DETECTION_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AILogoDetector:
    """Service for AI-powered logo detection using OpenAI's vision capabilities"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the AI Logo Detector"""
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            logger.warning("No OpenAI API key provided. AI logo detection will not work.")
    
    async def detect_logo_from_screenshot(self, screenshot: str) -> Dict[str, Any]:
        """
        Use OpenAI's vision capabilities to detect a logo in a screenshot
        
        Args:
            screenshot: Base64 encoded screenshot
            
        Returns:
            Dictionary containing detection results
        """
        if not self.api_key:
            logger.error("OpenAI API key is required for logo detection")
            return {"logo_detected": False, "error": "API key not configured"}
        
        if not screenshot or not isinstance(screenshot, str) or not screenshot.startswith('data:image/'):
            logger.error("Invalid screenshot format")
            return {"logo_detected": False, "error": "Invalid screenshot format"}
        
        try:
            # Extract base64 image data from data URL
            image_data = screenshot.split(',')[1] if ',' in screenshot else screenshot
            
            # Prepare the API request to OpenAI
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": OPENAI_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert in logo detection and analysis."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": LOGO_DETECTION_PROMPT
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": OPENAI_MAX_TOKENS
            }
            
            logger.info("Sending request to OpenAI for logo detection")
            
            # Make the API call
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error: {error_text}")
                        return {"logo_detected": False, "error": f"API error: {response.status}"}
                    
                    result = await response.json()
                    
                    # Extract the content from the response
                    if not result.get("choices") or not result["choices"][0].get("message"):
                        logger.error("Unexpected response format from OpenAI")
                        return {"logo_detected": False, "error": "Unexpected response format"}
                    
                    content = result["choices"][0]["message"]["content"]
                    
                    # Parse the JSON response
                    try:
                        # The response might have markdown code blocks or extra text
                        # Try to extract JSON content
                        json_content = self._extract_json_from_text(content)
                        detection_result = json.loads(json_content)
                        
                        # Add metadata about the detection method
                        detection_result["detection_method"] = "openai-vision"
                        
                        return detection_result
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing OpenAI response: {str(e)}")
                        return {
                            "logo_detected": False, 
                            "error": "Could not parse response",
                            "raw_response": content
                        }
            
        except Exception as e:
            logger.error(f"Error in AI logo detection: {str(e)}")
            return {"logo_detected": False, "error": str(e)}
    
    def _extract_json_from_text(self, text: str) -> str:
        """Extract JSON from potentially formatted text (e.g., with markdown)"""
        # Check if the text contains a code block with JSON
        if "```json" in text:
            # Extract content between ```json and ```
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        
        # Check if the text contains any code block
        if "```" in text:
            # Extract content between ``` and ```
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        
        # Otherwise, assume the entire text is JSON or contains JSON
        # Try to find content that looks like JSON (starting with { and ending with })
        if "{" in text and "}" in text:
            start = text.find("{")
            # Find the last }
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                return text[start:end].strip()
        
        # If we can't identify a JSON structure, return the whole text
        return text.strip()
    
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
            
    def visualize_logo_detection(self, screenshot: str, bounding_box: Dict[str, int], 
                                output_path: str = "detected_logo.png") -> bool:
        """
        Draw the bounding box on the screenshot and save it for visualization
        
        Args:
            screenshot: Base64 encoded screenshot
            bounding_box: Dictionary with x1, y1, x2, y2 coordinates
            output_path: Path to save the visualization
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract base64 image data
            image_data = screenshot.split(',')[1] if ',' in screenshot else screenshot
            image_bytes = base64.b64decode(image_data)
            
            # Open the image
            img = Image.open(BytesIO(image_bytes))
            draw = ImageDraw.Draw(img)
            
            # Get bounding box coordinates
            x1 = max(0, int(bounding_box.get('x1', 0)))
            y1 = max(0, int(bounding_box.get('y1', 0)))
            x2 = min(img.width, int(bounding_box.get('x2', img.width)))
            y2 = min(img.height, int(bounding_box.get('y2', img.height)))
            
            # Draw the bounding box
            draw.rectangle([(x1, y1), (x2, y2)], outline="red", width=3)
            
            # Save the image
            img.save(output_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Error visualizing logo detection: {str(e)}")
            return False