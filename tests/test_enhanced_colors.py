import asyncio
import sys
import os
import json
import base64
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Add the parent directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.enhanced_scraper import EnhancedWebScraper
from app.services.logo_extractor import LogoExtractor
from app.services.enhanced_color_extractor import EnhancedColorExtractor

async def test_enhanced_color_extraction(url):
    """Test the enhanced color extraction with the given URL"""
    print(f"Testing enhanced color extraction for: {url}")
    
    try:
        # Step 1: Initialize the scraper
        scraper = EnhancedWebScraper(use_cache=False)  # Disable cache for testing
        
        try:
            # Step 2: Scrape the website
            print("\n1. Scraping website with headless browser...")
            html_content, screenshot = await scraper.scrape(url)
            print(f"✓ Successfully scraped website ({len(html_content)} bytes)")
            
            # Step 3: Extract logo
            print("\n2. Extracting logo...")
            logo_extractor = LogoExtractor()
            logo_data = await logo_extractor.extract_logo(html_content, screenshot, url)
            
            if logo_data.get("image"):
                print(f"✓ Logo extracted! Source: {logo_data['source']}")
                print(f"  Size: {logo_data.get('width')}x{logo_data.get('height')}")
                print(f"  URL: {logo_data.get('url', 'Generated from screenshot')}")
                
                # Save logo to file if available
                if logo_data.get("image").startswith('data:image/'):
                    logo_data_b64 = logo_data["image"].split(',')[1]
                    logo_bytes = base64.b64decode(logo_data_b64)
                    
                    with open("extracted_logo.png", "wb") as f:
                        f.write(logo_bytes)
                    print("✓ Saved logo to 'extracted_logo.png'")
            else:
                print(f"✗ No logo found, but process completed without errors")
                
            # Step 4: Extract enhanced colors
            print("\n3. Extracting enhanced colors...")
            enhanced_color_extractor = EnhancedColorExtractor()
            enhanced_colors = await enhanced_color_extractor.extract_colors(html_content, logo_data.get("image"))
            
            # Save color data to JSON for inspection
            with open("enhanced_colors.json", "w") as f:
                json.dump(enhanced_colors, f, indent=2, default=lambda o: str(o))
                print("✓ Saved color data to 'enhanced_colors.json'")
            
            # Print color palette information
            palette = enhanced_colors.get("palette", {})
            print("\nColor Palette:")
            
            for role, color in palette.items():
                if color and role != "additional":
                    print(f"  {role.capitalize()}: {color.get('hex')} ({color.get('name', 'unnamed')})")
            
            additional = palette.get("additional", [])
            if additional:
                print(f"  Additional Colors: {len(additional)} colors found")
                for i, color in enumerate(additional[:3]):  # Show only first 3 additional colors
                    print(f"    - {color.get('hex')} ({color.get('name', 'unnamed')})")
                if len(additional) > 3:
                    print(f"    - ... and {len(additional) - 3} more")
            
            # Create a visualization of the color palette
            await create_palette_visualization(palette, "color_palette.png")
            print("✓ Created color palette visualization at 'color_palette.png'")
            
            return enhanced_colors
        finally:
            # Always close the browser when done
            await scraper.close()
            
    except Exception as e:
        print(f"\n✗ Error during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def create_palette_visualization(palette, filename="color_palette.png"):
    """Create a visualization of the color palette"""
    # Set up the image
    width, height = 800, 400
    img = Image.new('RGB', (width, height), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    
    # Helper function to draw a color rectangle with label
    def draw_color_rect(x, y, w, h, color, label):
        # Draw rectangle with the color
        if color:
            rgb = tuple(color.get("rgb", [128, 128, 128]))
            draw.rectangle([x, y, x+w, y+h], fill=rgb, outline=(0, 0, 0))
            
            # Draw label
            label_text = f"{label}: {color.get('hex', 'N/A')}"
            # Calculate text position
            text_x = x + 10
            text_y = y + h - 30
            
            # Draw text background for visibility
            text_w = len(label_text) * 8  # Approximate width
            text_h = 20
            text_bg_color = (255, 255, 255, 180)  # Semi-transparent white
            draw.rectangle([text_x-5, text_y-5, text_x+text_w, text_y+text_h], fill=text_bg_color)
            
            # Draw text (no font specified, using default)
            draw.text((text_x, text_y), label_text, fill=(0, 0, 0))
    
    # Draw main color roles
    roles = ["primary", "secondary", "accent", "background", "text"]
    x_positions = [50, 200, 350, 500, 650]
    
    for i, role in enumerate(roles):
        color = palette.get(role)
        draw_color_rect(x_positions[i], 50, 100, 100, color, role.capitalize())
    
    # Draw additional colors
    additional = palette.get("additional", [])
    max_additional = min(len(additional), 8)  # Show up to 8 additional colors
    
    if additional:
        # Draw title for additional colors
        draw.text((50, 200), "Additional Colors:", fill=(0, 0, 0))
        
        # Calculate grid for additional colors
        cols = 4
        rows = (max_additional + cols - 1) // cols
        cell_width = 150
        cell_height = 80
        
        for i in range(max_additional):
            row = i // cols
            col = i % cols
            x = 50 + col * cell_width
            y = 230 + row * cell_height
            
            color = additional[i]
            # Use a shorter label for additional colors
            short_label = f"Color {i+1}"
            draw_color_rect(x, y, cell_width-10, cell_height-10, color, short_label)
    
    # Save the image
    img.save(filename)

if __name__ == "__main__":
    # Test URLs
    test_urls = [
        "https://www.spotify.com",      # Green and black
        "https://www.coca-cola.com",    # Red and white
        "https://www.microsoft.com",    # Colorful
        "https://www.ibm.com",          # Blue
    ]
    
    # Run the test for each URL
    for url in test_urls:
        print("\n" + "="*50)
        result = asyncio.run(test_enhanced_color_extraction(url))
        print("="*50)
        print(f"✓ Test completed for {url}")
        # print(f"  Result: {result}")