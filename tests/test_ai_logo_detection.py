import asyncio
import sys
import os
import json

# Add the parent directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.enhanced_scraper import EnhancedWebScraper
from app.services.logo_extractor import LogoExtractor
from app.services.ai_logo_detector import AILogoDetector
from app.services.color_extractor import ColorExtractor
from app.services.fallback_logo_detector import FallbackLogoDetector

async def test_ai_logo_detection(url):
    """Test the AI-powered logo detection with the given URL"""
    print(f"Testing AI logo detection for: {url}")
    
    try:
        # Step 1: Initialize the scraper
        scraper = EnhancedWebScraper(use_cache=False)  # Disable cache for testing
        
        try:
            # Step 2: Scrape the website
            print("\n1. Scraping website with headless browser...")
            html_content, screenshot = await scraper.scrape(url)
            print(f"✓ Successfully scraped website ({len(html_content)} bytes)")
            print(f"✓ Screenshot captured")
            
            # Step 3: Try AI detection first, then fallback to the logo extractor
            print("\n2. Using AI or fallback methods to detect logo...")
            ai_logo_detector = AILogoDetector()
            detection_result = await ai_logo_detector.detect_logo_from_screenshot(screenshot)
            
            # If AI detection fails, try fallback
            if not detection_result.get("logo_detected") and "error" in detection_result:
                print(f"AI detection failed with error: {detection_result.get('error')}")
                print("Trying fallback heuristic detection...")
                fallback_detector = FallbackLogoDetector()
                detection_result = await fallback_detector.detect_logo_from_screenshot(screenshot)
            
            print(f"Detection Result:")
            print(json.dumps(detection_result, indent=2))
            
            if detection_result.get("logo_detected"):
                print(f"✓ Logo detected at {detection_result.get('location')}")
                print(f"  Description: {detection_result.get('description')}")
                print(f"  Method: {detection_result.get('detection_method', 'unknown')}")
                
                # Visualize the detection
                if detection_result.get("bounding_box"):
                    # Choose the appropriate detector for visualization
                    if detection_result.get("detection_method", "").startswith("heuristic"):
                        # Fallback detector doesn't have visualization, so use AI detector's method
                        if ai_logo_detector.visualize_logo_detection(
                            screenshot, 
                            detection_result["bounding_box"], 
                            "detected_logo.png"
                        ):
                            print(f"✓ Detection visualization saved to 'detected_logo.png'")
                    else:
                        if ai_logo_detector.visualize_logo_detection(
                            screenshot, 
                            detection_result["bounding_box"], 
                            "detected_logo.png"
                        ):
                            print(f"✓ Detection visualization saved to 'detected_logo.png'")
                    
                    # Crop the logo using the appropriate detector
                    cropper = fallback_detector if detection_result.get("detection_method", "").startswith("heuristic") else ai_logo_detector
                    cropped_logo = await cropper.crop_logo_from_screenshot(
                        screenshot, 
                        detection_result["bounding_box"]
                    )
                    
                    if cropped_logo:
                        # Save the cropped logo to a file
                        logo_data = cropped_logo.split(',')[1]
                        with open("cropped_logo.png", "wb") as f:
                            f.write(base64.b64decode(logo_data))
                        print(f"✓ Cropped logo saved to 'cropped_logo.png'")
                        
                        # Extract colors from the cropped logo
                        print("\n3. Extracting colors from detected logo...")
                        color_extractor = ColorExtractor()
                        colors = await color_extractor.extract_colors("", cropped_logo)
                        
                        if colors:
                            print(f"✓ Found {len(colors)} unique colors:")
                            for i, color in enumerate(colors[:5]):  # Show only first 5 colors
                                print(f"  {i+1}. {color['hex']} (source: {color['source']})")
                            if len(colors) > 5:
                                print(f"  ... and {len(colors) - 5} more")
            else:
                print(f"✗ No logo detected with either AI or fallback methods")
            
            # Step 4: Use the full logo extractor (which includes AI as fallback)
            print("\n4. Using complete logo extraction pipeline...")
            logo_extractor = LogoExtractor()
            logo_data = await logo_extractor.extract_logo(html_content, screenshot, url)
            
            if logo_data.get("image"):
                print(f"✓ Logo extracted! Source: {logo_data['source']}")
                print(f"  Size: {logo_data.get('width')}x{logo_data.get('height')}")
                print(f"  URL: {logo_data.get('url') or 'Generated from screenshot'}")
                
                # Save the extracted logo to compare with AI detection
                if logo_data.get("image").startswith('data:image/'):
                    import base64
                    logo_img_data = logo_data["image"].split(',')[1]
                    with open("extracted_logo.png", "wb") as f:
                        f.write(base64.b64decode(logo_img_data))
                    print(f"✓ Extracted logo saved to 'extracted_logo.png'")
            else:
                print(f"✗ No logo extracted by the pipeline")
            
            return {
                "ai_detection": detection_result,
                "logo_extraction": logo_data
            }
            
        finally:
            # Always close the browser when done
            await scraper.close()
            
    except Exception as e:
        print(f"\n✗ Error during testing: {str(e)}")
        return None

if __name__ == "__main__":
    # Test URLs - choose sites with varied logo placements and styles
    test_urls = [
        "https://www.spotify.com",         # Distinctive and colorful logo
        "https://www.netflix.com",         # Simple but recognizable logo
        "https://www.amazon.com",          # Logo that might be harder to detect
        "https://www.microsoft.com",       # Multi-colored logo
    ]
    
    # Run the test for each URL
    for url in test_urls:
        print("\n" + "="*50)
        result = asyncio.run(test_ai_logo_detection(url))
        print("="*50)