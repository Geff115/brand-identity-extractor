import logging
import time
from typing import Dict, Any, List, Optional
import os
from redis.exceptions import RedisError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HealthCheck:
    """Service for checking system health and dependencies"""
    
    def __init__(self):
        """Initialize the health checker"""
        self.services = {}
        self.last_check = {}
        self.status = {}
    
    async def check_redis(self, redis_client) -> Dict[str, Any]:
        """
        Check Redis connection
        
        Args:
            redis_client: Redis client to check
            
        Returns:
            Dictionary with health check results
        """
        service_name = "redis"
        start_time = time.time()
        
        try:
            # Try to ping Redis
            response = redis_client.ping()
            success = response == True
            
            latency = time.time() - start_time
            
            result = {
                "status": "healthy" if success else "unhealthy",
                "latency_ms": round(latency * 1000, 2),
                "timestamp": time.time()
            }
            
            # Update service status
            self.services[service_name] = result
            self.last_check[service_name] = time.time()
            
            return result
            
        except RedisError as e:
            result = {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
            
            # Update service status
            self.services[service_name] = result
            self.last_check[service_name] = time.time()
            
            return result
        except Exception as e:
            logger.error(f"Error checking Redis health: {str(e)}")
            
            result = {
                "status": "unhealthy",
                "error": f"Unexpected error: {str(e)}",
                "timestamp": time.time()
            }
            
            # Update service status
            self.services[service_name] = result
            self.last_check[service_name] = time.time()
            
            return result
    
    async def check_openai(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Check OpenAI API connection
        
        Args:
            api_key: OpenAI API key (defaults to environment variable)
            
        Returns:
            Dictionary with health check results
        """
        import aiohttp
        
        service_name = "openai"
        start_time = time.time()
        
        # Get API key from environment if not provided
        api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        
        if not api_key:
            result = {
                "status": "unknown",
                "error": "API key not configured",
                "timestamp": time.time()
            }
            
            # Update service status
            self.services[service_name] = result
            self.last_check[service_name] = time.time()
            
            return result
        
        try:
            # We'll make a simple models list request to check connectivity
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                ) as response:
                    success = response.status == 200
                    latency = time.time() - start_time
                    
                    if success:
                        result = {
                            "status": "healthy",
                            "latency_ms": round(latency * 1000, 2),
                            "timestamp": time.time()
                        }
                    else:
                        error_text = await response.text()
                        result = {
                            "status": "unhealthy",
                            "error": f"API returned status {response.status}: {error_text}",
                            "timestamp": time.time()
                        }
                    
                    # Update service status
                    self.services[service_name] = result
                    self.last_check[service_name] = time.time()
                    
                    return result
                    
        except Exception as e:
            logger.error(f"Error checking OpenAI health: {str(e)}")
            
            result = {
                "status": "unhealthy",
                "error": f"Connection error: {str(e)}",
                "timestamp": time.time()
            }
            
            # Update service status
            self.services[service_name] = result
            self.last_check[service_name] = time.time()
            
            return result
    
    async def check_playwright(self) -> Dict[str, Any]:
        """
        Check Playwright installation
        
        Returns:
            Dictionary with health check results
        """
        service_name = "playwright"
        
        try:
            # Try to import playwright
            from playwright.async_api import async_playwright
            
            result = {
                "status": "healthy",
                "timestamp": time.time()
            }
            
            # Update service status
            self.services[service_name] = result
            self.last_check[service_name] = time.time()
            
            return result
            
        except ImportError as e:
            logger.error(f"Playwright not installed: {str(e)}")
            
            result = {
                "status": "unhealthy",
                "error": f"Playwright not installed: {str(e)}",
                "timestamp": time.time()
            }
            
            # Update service status
            self.services[service_name] = result
            self.last_check[service_name] = time.time()
            
            return result
        except Exception as e:
            logger.error(f"Error checking Playwright health: {str(e)}")
            
            result = {
                "status": "unhealthy",
                "error": f"Unexpected error: {str(e)}",
                "timestamp": time.time()
            }
            
            # Update service status
            self.services[service_name] = result
            self.last_check[service_name] = time.time()
            
            return result
    
    async def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health
        
        Returns:
            Dictionary with overall health status and individual service statuses
        """
        now = time.time()
        
        # Consider a service unhealthy if check is older than 5 minutes
        stale_threshold = 300  # 5 minutes
        
        services_health = {}
        overall_status = "healthy"
        
        # Check each service
        for service, result in self.services.items():
            # Check if result is stale
            last_check = self.last_check.get(service, 0)
            if now - last_check > stale_threshold:
                result["status"] = "unknown"
                result["warning"] = "Data is stale"
            
            services_health[service] = result
            
            # Update overall status
            if result["status"] != "healthy" and overall_status == "healthy":
                overall_status = result["status"]
        
        return {
            "status": overall_status,
            "timestamp": now,
            "services": services_health
        }
    
    async def check_all_services(self, cache_service, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Check all services
        
        Args:
            cache_service: Cache service with Redis client
            api_key: OpenAI API key
            
        Returns:
            Dictionary with health check results
        """
        # Check Redis
        if cache_service and hasattr(cache_service, 'client') and cache_service.client:
            await self.check_redis(cache_service.client)
        
        # Check OpenAI
        await self.check_openai(api_key)
        
        # Check Playwright
        await self.check_playwright()
        
        # Return overall health
        return await self.get_system_health()