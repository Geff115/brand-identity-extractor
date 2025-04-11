import asyncio
import sys
import os
import time
import json
import aiohttp

# Add the parent directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cache_service import CacheService
from app.services.rate_limiter import RateLimiter

async def test_api_performance(url, api_base_url="http://localhost:8000"):
    """Test the API performance with and without caching"""
    print(f"Testing API performance for URL: {url}")
    api_endpoint = f"{api_base_url}/extract"
    
    try:
        # First request (cache miss)
        print("\n1. First request (should be a cache miss)")
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_endpoint, json={"url": url}) as response:
                first_status = response.status
                first_response = await response.json() if first_status == 200 else await response.text()
                first_duration = time.time() - start_time
                
                # Check for rate limit headers
                rate_limit = response.headers.get("X-Rate-Limit-Limit")
                rate_remaining = response.headers.get("X-Rate-Limit-Remaining")
                rate_reset = response.headers.get("X-Rate-Limit-Reset")
        
        print(f"  Status code: {first_status}")
        print(f"  Duration: {first_duration:.2f} seconds")
        print(f"  Rate limit: {rate_limit}, Remaining: {rate_remaining}, Reset: {rate_reset}")
        
        if first_status == 200:
            logo_source = first_response.get("logo", {}).get("source") if first_response.get("logo") else "None"
            colors_count = len(first_response.get("colors", []))
            enhanced_palette = first_response.get("enhanced_colors", {}).get("palette", {}) if first_response.get("enhanced_colors") else {}
            
            print(f"  Logo source: {logo_source}")
            print(f"  Colors found: {colors_count}")
            print(f"  Enhanced palette: {len(enhanced_palette)} roles")
        else:
            print(f"  Error: {first_response}")
        
        # Wait a bit
        await asyncio.sleep(1)
        
        # Second request (should be cached)
        print("\n2. Second request (should be a cache hit)")
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_endpoint, json={"url": url}) as response:
                second_status = response.status
                second_response = await response.json() if second_status == 200 else await response.text()
                second_duration = time.time() - start_time
                
                # Check for rate limit headers
                rate_limit = response.headers.get("X-Rate-Limit-Limit")
                rate_remaining = response.headers.get("X-Rate-Limit-Remaining")
                rate_reset = response.headers.get("X-Rate-Limit-Reset")
        
        print(f"  Status code: {second_status}")
        print(f"  Duration: {second_duration:.2f} seconds")
        print(f"  Rate limit: {rate_limit}, Remaining: {rate_remaining}, Reset: {rate_reset}")
        
        if second_status == 200:
            logo_source = second_response.get("logo", {}).get("source") if second_response.get("logo") else "None"
            colors_count = len(second_response.get("colors", []))
            
            print(f"  Logo source: {logo_source}")
            print(f"  Colors found: {colors_count}")
            
            # Calculate speedup
            if first_duration > 0:
                speedup = first_duration / second_duration
                print(f"\nCache speedup: {speedup:.2f}x faster")
        else:
            print(f"  Error: {second_response}")
        
        # Test rate limiting
        print("\n3. Testing rate limiting with multiple rapid requests")
        
        # Make 5 rapid requests
        rate_test_count = 5
        rate_test_results = []
        
        for i in range(rate_test_count):
            async with aiohttp.ClientSession() as session:
                async with session.post(api_endpoint, json={"url": url}) as response:
                    rate_test_results.append({
                        "status": response.status,
                        "limit": response.headers.get("X-Rate-Limit-Limit"),
                        "remaining": response.headers.get("X-Rate-Limit-Remaining"),
                        "reset": response.headers.get("X-Rate-Limit-Reset")
                    })
            
            # Sleep a tiny bit to not overwhelm the server
            await asyncio.sleep(0.1)
        
        # Display rate limiting results
        print(f"  Completed {rate_test_count} rapid requests:")
        for i, result in enumerate(rate_test_results):
            print(f"    Request {i+1}: Status {result['status']}, Remaining: {result['remaining']}")
        
        # Check if rate limiting is working correctly
        if all(r["status"] == 200 for r in rate_test_results) and \
           rate_test_results[0]["remaining"] > rate_test_results[-1]["remaining"]:
            print("  ✓ Rate limiting is working correctly (remaining count decreasing)")
        else:
            print("  ✗ Rate limiting might not be working as expected")
        
        return {
            "first_request": {
                "status": first_status,
                "duration": first_duration,
                "rate_limit": rate_limit
            },
            "second_request": {
                "status": second_status,
                "duration": second_duration,
                "rate_limit": rate_remaining
            },
            "speedup": first_duration / second_duration if first_duration > 0 and second_duration > 0 else 0
        }
            
    except Exception as e:
        print(f"\n✗ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def test_cache_clear(api_base_url="http://localhost:8000", admin_key="629efe1bd58cfc3f2d8b594e4628277628fbfb2a98e24733ee28b79c5efa5d3c"):
    """Test the cache clear endpoint"""
    print("\nTesting cache clear endpoint")
    
    try:
        # Load admin key from .env file if possible
        try:
            from dotenv import load_dotenv
            load_dotenv()
            admin_key = os.getenv("ADMIN_KEY", admin_key)
        except ImportError:
            pass  # Continue with the provided key
        
        # Clear the cache
        async with aiohttp.ClientSession() as session:
            # Send as both a header and a query parameter to be safe
            headers = {"X-Admin-Key": admin_key}
            params = {"admin_key": admin_key}
            
            print(f"  Using admin key: {admin_key}")
            
            async with session.delete(
                f"{api_base_url}/cache",
                headers=headers,
                params=params
            ) as response:
                status = response.status
                response_text = await response.text()
                
        if status == 200 or status:
            print("  ✓ Cache cleared successfully")
        else:
            print(f"  ✗ Failed to clear cache: Status {status}")
            print(f"    Response: {response_text}")
            
        return {"status": status}
        
    except Exception as e:
        print(f"  ✗ Error clearing cache: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Test URLs
    test_urls = [
        "https://www.spotify.com",
        "https://www.microsoft.com"
    ]
    
    # Run the test for each URL
    for url in test_urls:
        print("\n" + "="*50)
        result = asyncio.run(test_api_performance(url))
        print("="*50)
    
    # Test cache clear
    print("\n" + "="*50)
    asyncio.run(test_cache_clear())
    print("="*50)