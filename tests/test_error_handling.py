import asyncio
import sys
import os
import time
import json
import aiohttp

# Add the parent directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_health_check(api_base_url="http://localhost:8000"):
    """Test the health check endpoint"""
    print("\nTesting health check endpoint")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_base_url}/health") as response:
                status = response.status
                data = await response.json()
                
        print(f"  Status code: {status}")
        print(f"  Overall health: {data.get('status', 'unknown')}")
        
        # Print service statuses
        services = data.get("services", {})
        for service_name, service_data in services.items():
            service_status = service_data.get("status", "unknown")
            print(f"  {service_name}: {service_status}")
            
            # Show error if unhealthy
            if service_status != "healthy" and "error" in service_data:
                print(f"    Error: {service_data['error']}")
        
        return data
    except Exception as e:
        print(f"  ✗ Error checking health: {str(e)}")
        return None

async def test_invalid_url(api_base_url="http://localhost:8000"):
    """Test error handling with an invalid URL"""
    print("\nTesting invalid URL error handling")
    
    try:
        invalid_url = "https://thisdomaindoesnotexistatall12345.com"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_base_url}/extract",
                json={"url": invalid_url}
            ) as response:
                status = response.status
                try:
                    data = await response.json()
                except:
                    data = {"error": "Could not parse response as JSON"}
                
                # Get request ID from header
                request_id = response.headers.get("X-Request-ID")
                
        print(f"  Status code: {status}")
        if "error" in data:
            error = data["error"]
            print(f"  Error message: {error.get('message', 'No message')}")
            print(f"  Error category: {error.get('category', 'No category')}")
            print(f"  Request ID: {request_id or 'None'}")
        else:
            print(f"  Unexpected response format: {data}")
            
        return data
    except Exception as e:
        print(f"  ✗ Error testing invalid URL: {str(e)}")
        return None

async def test_rate_limiting(api_base_url="http://localhost:8000"):
    """Test rate limiting error handling"""
    print("\nTesting rate limiting error handling")
    
    try:
        # Make requests until we hit the rate limit
        url = "https://www.example.com"
        max_requests = 100  # Safety limit
        request_count = 0
        
        print("  Making requests until rate limit is hit...")
        
        async with aiohttp.ClientSession() as session:
            for i in range(max_requests):
                request_count = i + 1
                
                async with session.post(
                    f"{api_base_url}/extract",
                    json={"url": url}
                ) as response:
                    status = response.status
                    remaining = response.headers.get("X-Rate-Limit-Remaining", "unknown")
                    
                    # Print progress every 10 requests
                    if i % 10 == 0:
                        print(f"    Request {request_count}: Status {status}, Remaining: {remaining}")
                    
                    # If we hit the rate limit, stop
                    if status == 429:
                        data = await response.json()
                        print(f"  ✓ Rate limit hit after {request_count} requests")
                        if "error" in data:
                            error = data["error"]
                            print(f"  Error message: {error.get('message')}")
                            print(f"  Error category: {error.get('category')}")
                        return data
                
                # Sleep a tiny bit to not overwhelm the server
                await asyncio.sleep(0.05)
        
        print(f"  ✗ Rate limit not hit after {request_count} requests")
        return None
    except Exception as e:
        print(f"  ✗ Error testing rate limiting: {str(e)}")
        return None

async def test_circuit_breaker(api_base_url="http://localhost:8000"):
    """
    Test circuit breaker functionality by causing errors
    (Note: this is difficult to test without mocking the services)
    """
    print("\nTesting circuit breaker functionality")
    print("  (This is a simulated test since we can't easily trigger the circuit breaker)")
    
    # In a real test, we would:
    # 1. Mock the external service to fail repeatedly
    # 2. Make requests until the circuit breaker opens
    # 3. Verify that subsequent requests are rejected with the appropriate error
    
    print("  Circuit breaker would open after multiple failures")
    print("  Subsequent requests would receive a 503 Service Unavailable error")
    print("  After the recovery timeout, the circuit would enter half-open state")
    
    return None

async def test_graceful_degradation(api_base_url="http://localhost:8000"):
    """Test graceful degradation when parts of the system fail"""
    print("\nTesting graceful degradation")
    
    try:
        # Use a valid URL but one that loads cleanly without complex media
        url = "https://example.com"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_base_url}/extract",
                json={"url": url}
            ) as response:
                status = response.status
                try:
                    data = await response.json()
                except:
                    data = {"error": "Could not parse response as JSON"}
                
        print(f"  Status code: {status}")
        
        if status == 200:
            # Verify that we got at least some results even if parts failed
            has_logo = data.get("logo") is not None
            has_colors = len(data.get("colors", [])) > 0
            has_enhanced_colors = data.get("enhanced_colors") is not None
            
            print(f"  Logo extracted: {'Yes' if has_logo else 'No'}")
            print(f"  Colors extracted: {'Yes' if has_colors else 'No'}")
            print(f"  Enhanced colors: {'Yes' if has_enhanced_colors else 'No'}")
            
            print("  ✓ API returned results even if some components may have failed")
        else:
            print(f"  ✗ API did not demonstrate graceful degradation: {status}")
            if "error" in data:
                error = data.get("error", {})
                print(f"    Error message: {error.get('message', 'No message')}")
        
        return data
    except Exception as e:
        print(f"  ✗ Error testing graceful degradation: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Test health check
    asyncio.run(test_health_check())
    
    # Test error handling
    asyncio.run(test_invalid_url())
    
    # Test graceful degradation
    asyncio.run(test_graceful_degradation())
    
    # Note: Rate limiting test can be time-consuming
    # Uncomment if you want to test it
    # asyncio.run(test_rate_limiting())
    
    # Circuit breaker test is simulated
    asyncio.run(test_circuit_breaker())