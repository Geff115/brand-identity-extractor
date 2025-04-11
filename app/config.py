# OpenAI API Key and Configuration
# This module handles the OpenAI API key and configuration settings for the logo detection service.
# It includes the model to be used, maximum tokens for the response, and the prompt for logo detection.
# It also loads the API key from environment variables for security.
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # User needs to set this environment variable

# OpenAI Configuration
OPENAI_MODEL = "gpt-4o"  # Latest model with vision capabilities
OPENAI_MAX_TOKENS = 1000  # Maximum tokens for response

# Logo Detection Settings
LOGO_DETECTION_PROMPT = """
You are an expert logo detector. Analyze this website screenshot and:
1. Identify if there's a brand logo visible
2. Describe the exact location of the logo (usually top-left, center or in the header)
3. Describe the logo in detail (colors, shapes, text)
4. Estimate the pixel coordinates of the logo's bounding box (x1, y1, x2, y2)

Format your response as JSON with these fields:
{
  "logo_detected": true/false,
  "location": "top-left/top-center/etc",
  "description": "Detailed description of the logo",
  "bounding_box": {
    "x1": approximate x coordinate of top-left,
    "y1": approximate y coordinate of top-left,
    "x2": approximate x coordinate of bottom-right,
    "y2": approximate y coordinate of bottom-right
  }
}
"""