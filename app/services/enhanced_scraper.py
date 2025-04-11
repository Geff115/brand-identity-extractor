import logging
import random
import base64
import asyncio
import time
from urllib.parse import urlparse, urljoin
from typing import Tuple, Optional, Dict, Any, List

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

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

class EnhancedWebScraper:
    """Advanced web scraper with headless browser capabilities"""
    
    def __init__(self, use_cache: bool = True, cache_timeout: int = 3600):
        self.use_cache = use_cache
        self.cache_timeout = cache_timeout  # Cache timeout in seconds
        self.cache = {}  # Simple in-memory cache, will be replaced by Redis in production
        self._browser = None
    
    async def _initialize_browser(self) -> None:
        """Initialize the browser if it's not already running"""
        if self._browser is None:
            playwright = await async_playwright().start()
            # Use chromium for best compatibility
            self._browser = await playwright.chromium.launch(
                headless=True,  # Run in headless mode
            )
            logger.info("Initialized headless browser")
    
    async def close(self) -> None:
        """Close the browser when done"""
        if self._browser:
            await self._browser.close()
            self._browser = None
            logger.info("Closed headless browser")
    
    async def scrape(self, url: str, wait_for_selectors: List[str] = None) -> Tuple[str, Optional[str]]:
        """
        Scrape a website using a headless browser
        
        Args:
            url: Website URL to scrape
            wait_for_selectors: Optional list of CSS selectors to wait for before capturing
            
        Returns:
            Tuple containing HTML content and screenshot as base64
        """
        # Check cache first if enabled
        if self.use_cache and url in self.cache:
            cache_entry = self.cache[url]
            cache_time = cache_entry.get('timestamp', 0)
            current_time = time.time()
            
            # If cache is still valid
            if current_time - cache_time < self.cache_timeout:
                logger.info(f"Using cached data for {url}")
                return cache_entry['html'], cache_entry['screenshot']
        
        logger.info(f"Scraping website with headless browser: {url}")
        
        try:
            # Initialize browser if needed
            await self._initialize_browser()
            
            # Create a new context (like an incognito window) with random user agent
            context = await self._browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
            )
            
            # Open a new page
            page = await context.new_page()
            
            # Set default timeout to 30 seconds
            page.set_default_timeout(30000)
            
            # Add request interception for optimization
            await self._setup_request_interception(page)
            
            # Navigate to the URL with retry mechanism
            html_content, screenshot = await self._navigate_with_retry(page, url, wait_for_selectors)
            
            # Close the context
            await context.close()
            
            # Cache the results if caching is enabled
            if self.use_cache:
                self.cache[url] = {
                    'html': html_content,
                    'screenshot': screenshot,
                    'timestamp': time.time()
                }
            
            return html_content, screenshot
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            # Close browser on error to prevent resource leaks
            await self.close()
            raise Exception(f"Failed to scrape website: {str(e)}")
    
    async def _setup_request_interception(self, page: Page) -> None:
        """Set up request interception to block unnecessary resources"""
        
        # Create a handler to block non-essential resources
        async def route_handler(route):
            resource_type = route.request.resource_type
            
            # Block unnecessary resources to speed up scraping
            if resource_type in ['image', 'media', 'font', 'stylesheet']:
                if resource_type == 'image' and 'logo' in route.request.url.lower():
                    # Allow logo images to load
                    await route.continue_()
                else:
                    # Block other non-essential resources
                    await route.abort()
            else:
                # Continue with the request
                await route.continue_()
        
        # Enable request interception
        await page.route('**/*', route_handler)
    
    async def _navigate_with_retry(self, page: Page, url: str, wait_for_selectors: List[str] = None, 
                                  max_retries: int = 2) -> Tuple[str, Optional[str]]:
        """Navigate to URL with retry mechanism"""
        retries = 0
        
        while retries <= max_retries:
            try:
                # Navigate to the URL - use 'domcontentloaded' instead of 'networkidle' for faster loading
                response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                
                # Check if navigation was successful
                if not response:
                    raise Exception("Failed to get response from page")
                
                # Check if the page returned an error status
                if response.status >= 400:
                    raise Exception(f"Page returned status code: {response.status}")
                
                # Wait for critical elements if specified
                if wait_for_selectors:
                    for selector in wait_for_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                        except PlaywrightTimeout:
                            logger.warning(f"Selector '{selector}' not found on page")
                            # Continue anyway - the selector might not be present on all pages
                
                # Wait a bit for any critical JavaScript to execute (reduced from 1000ms)
                await page.wait_for_timeout(500)
                
                # Get the HTML content
                html_content = await page.content()
                
                # Take a screenshot
                screenshot_bytes = await page.screenshot(type='png', full_page=True)
                screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                screenshot = f"data:image/png;base64,{screenshot_base64}"
                
                # Return the results
                return html_content, screenshot

            except Exception as e:
                retries += 1
                logger.warning(f"Navigation attempt {retries} failed: {str(e)}")
                if retries <= max_retries:
                    # Wait before retrying (with exponential backoff)
                    await asyncio.sleep(2 ** retries)
                else:
                    # If all retries failed, raise the exception
                    raise Exception(f"Failed to navigate to {url} after {max_retries} attempts: {str(e)}")
    
    def get_absolute_url(self, base_url: str, relative_url: str) -> str:
        """Convert a relative URL to an absolute URL"""
        return urljoin(base_url, relative_url)
    
    def is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False