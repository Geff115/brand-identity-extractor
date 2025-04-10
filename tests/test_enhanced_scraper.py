import asyncio
import sys
import os
import base64
from PIL import Image
from io import BytesIO

# Add the parent directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.enhanced_scraper import EnhancedWebScraper
from app.services.logo_extractor import LogoExtractor
from app.services.color_extractor import ColorExtractor

async def test_enhanced_extraction(url):
    """Test the enhanced extraction pipeline with the given URL"""
    print(f"Testing enhanced extraction for: {url}")
    
    try:
        # Step 1: Initialize the scraper
        scraper = EnhancedWebScraper(use_cache=False)  # Disable cache for testing
        
        try:
            # Step 2: Scrape the website
            print("\n1. Scraping website with headless browser...")
            html_content, screenshot = await scraper.scrape(url)
            print(f"✓ Successfully scraped website ({len(html_content)} bytes)")
            
            # Save screenshot to file for inspection
            if screenshot and screenshot.startswith('data:image/png;base64,'):
                screenshot_data = screenshot.split(',')[1]
                screenshot_bytes = base64.b64decode(screenshot_data)
                
                # Save screenshot to file
                with open("screenshot.png", "wb") as f:
                    f.write(screenshot_bytes)
                print("✓ Saved screenshot to 'screenshot.png'")
            
            # Step 3: Extract logo
            print("\n2. Extracting logo...")
            logo_extractor = LogoExtractor()
            logo_data = await logo_extractor.extract_logo(html_content, screenshot, url)
            
            if logo_data.get("image"):
                print(f"✓ Logo extracted! Source: {logo_data['source']}")
                print(f"  Size: {logo_data.get('width')}x{logo_data.get('height')}")
                print(f"  URL: {logo_data.get('url')}")
                
                # Save logo to file if available
                if logo_data.get("image").startswith('data:image/png;base64,'):
                    logo_data_b64 = logo_data["image"].split(',')[1]
                    logo_bytes = base64.b64decode(logo_data_b64)
                    
                    with open("logo.png", "wb") as f:
                        f.write(logo_bytes)
                    print("✓ Saved logo to 'logo.png'")
            else:
                print(f"✗ No logo found, but process completed without errors")
                
            # Step 4: Extract colors
            print("\n3. Extracting colors...")
            color_extractor = ColorExtractor()
            colors = await color_extractor.extract_colors(html_content, logo_data.get("image"))
            
            if colors:
                print(f"✓ Found {len(colors)} unique colors:")
                for i, color in enumerate(colors[:5]):  # Show only first 5 colors
                    print(f"  {i+1}. {color['hex']} (source: {color['source']})")
                if len(colors) > 5:
                    print(f"  ... and {len(colors) - 5} more")
            else:
                print(f"✗ No colors found")
            
            return {
                "logo": logo_data,
                "colors": colors
            }
        finally:
            # Always close the browser when done
            await scraper.close()
            
    except Exception as e:
        print(f"\n✗ Error during extraction: {str(e)}")
        return None

if __name__ == "__main__":
    # Test URLs
    test_urls = [
        "https://www.nba.com/lakers/tickets/in-arena-faq",  # Original example
        "https://www.apple.com",                           # Clean design, should be easy
        "https://www.airbnb.com",                          # Dynamic JS-heavy site
    ]
    
    # Run the test for each URL
    for url in test_urls:
        print("\n" + "="*50)
        result = asyncio.run(test_enhanced_extraction(url))
        print("="*50)