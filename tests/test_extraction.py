import asyncio
import sys
import os

# Add the parent directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.scraper import WebScraper
from app.services.logo_extractor import LogoExtractor
from app.services.color_extractor import ColorExtractor

async def test_extraction(url):
    """Test the extraction pipeline with the given URL"""
    print(f"Testing extraction for: {url}")
    
    try:
        # Step 1: Scrape the website
        print("\n1. Scraping website...")
        scraper = WebScraper()
        html_content, screenshot = await scraper.scrape(url)
        print(f"✓ Successfully scraped website ({len(html_content)} bytes)")
        
        # Step 2: Extract logo
        print("\n2. Extracting logo...")
        logo_extractor = LogoExtractor()
        logo_data = await logo_extractor.extract_logo(html_content, screenshot, url)
        
        if logo_data.get("image"):
            print(f"✓ Logo extracted! Source: {logo_data['source']}")
            print(f"  Size: {logo_data.get('width')}x{logo_data.get('height')}")
            print(f"  URL: {logo_data.get('url')}")
        else:
            print(f"✗ No logo found, but process completed without errors")
            
        # Step 3: Extract colors
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
            
    except Exception as e:
        print(f"\n✗ Error during extraction: {str(e)}")
        return None

if __name__ == "__main__":
    # Test URLs
    test_urls = [
        "https://www.nba.com/lakers/tickets/in-arena-faq",  # Original example
        "https://www.apple.com",                           # Clean design, should be easy
        "https://www.github.com",                          # Another well-known site
    ]
    
    # Run the test for each URL
    for url in test_urls:
        print("\n" + "="*50)
        result = asyncio.run(test_extraction(url))
        print("="*50)