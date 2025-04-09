import sys
import os
import json
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

# Create a test client
client = TestClient(app)

def test_root_endpoint():
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("✓ Root endpoint test passed")

def test_extract_endpoint():
    """Test the extract endpoint with a test URL"""
    url = "https://www.nba.com/lakers/tickets/in-arena-faq"
    
    try:
        print(f"Sending request to /extract with URL: {url}")
        response = client.post(
            "/extract",
            json={"url": url}
        )
        
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✓ Extract endpoint test passed")
            print(f"  URL: {result['url']}")
            
            if result.get('logo'):
                print(f"  Logo source: {result['logo'].get('source')}")
                print(f"  Logo dimensions: {result['logo'].get('width')}x{result['logo'].get('height')}")
            else:
                print("  No logo found in response")
                
            print(f"  Colors found: {len(result.get('colors', []))}")
            
            # Save the response to a file for inspection
            with open("test_response.json", "w") as f:
                json.dump(result, f, indent=2)
                print("\nResponse saved to 'test_response.json'")
        else:
            print(f"✗ Test failed: {response.text}")
            # For debugging
            print("\nRequest details:")
            print(f"  URL: {url}")
            print(f"  Payload: {{'url': '{url}'}}")
    except Exception as e:
        print(f"✗ Exception during test: {str(e)}")

if __name__ == "__main__":
    print("Testing API endpoints...")
    print("\n1. Testing root endpoint")
    test_root_endpoint()
    
    print("\n2. Testing extract endpoint")
    test_extract_endpoint()