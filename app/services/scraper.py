# Web scraping functionality
import requests
from urllib.parse import urlparse, urljoin
import logging
from bs4 import BeautifulSoup
import random
from typing import Tuple, Optional
import base64
from io import BytesIO
from PIL import Image
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User agents for rotating to avoid detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
]

class WebScraper:
    """Service for scraping web content"""
    
    def __init__(self):
        self.session = requests.Session()
        self.cache = {}  # Simple in-memory cache
    
    async def scrape(self, url: str) -> Tuple[str, Optional[str]]:
        """
        Scrape the website content
        
        Args:
            url: Website URL to scrape
            
        Returns:
            Tuple containing HTML content and screenshot as base64
        """
        # Check cache first
        if url in self.cache:
            logger.info(f"Using cached data for {url}")
            return self.cache[url]
        
        logger.info(f"Scraping website: {url}")
        
        # Set random user agent to avoid detection
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            # Initial request with timeout
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            html_content = response.text
            
            # For now, we'll use a simple approach without a headless browser
            # In a more advanced implementation, we would use Selenium or Playwright 
            # to render JavaScript and capture a screenshot
            screenshot = None
            
            # In the next phase, we'll add:
            # 1. JavaScript rendering with a headless browser
            # 2. Screenshot capture
            # 3. Handling of various error cases (JS redirects, etc.)
            
            # Cache the results
            self.cache[url] = (html_content, screenshot)
            
            return html_content, screenshot
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            raise Exception(f"Failed to scrape website: {str(e)}")
    
    def get_absolute_url(self, base_url: str, relative_url: str) -> str:
        """Convert a relative URL to an absolute URL"""
        return urljoin(base_url, relative_url)
    
    def is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False