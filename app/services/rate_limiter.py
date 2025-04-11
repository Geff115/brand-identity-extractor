import logging
import time
from typing import Dict, Tuple, Optional, Any
import redis
from redis.exceptions import RedisError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimiter:
    """Service for rate limiting API requests"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", 
                 rate_limit: int = 60, window_size: int = 3600):
        """
        Initialize the rate limiter
        
        Args:
            redis_url: Redis connection URL
            rate_limit: Maximum number of requests allowed in the window
            window_size: Time window in seconds (default: 1 hour)
        """
        self.redis_url = redis_url
        self.rate_limit = rate_limit
        self.window_size = window_size
        self.enabled = True
        self.client = None
        
        try:
            self.client = redis.from_url(redis_url)
            # Test connection
            self.client.ping()
            logger.info(f"Connected to Redis at {redis_url} for rate limiting")
        except RedisError as e:
            logger.warning(f"Redis connection failed: {str(e)}. Rate limiting will be disabled.")
            self.enabled = False
        except Exception as e:
            logger.warning(f"Error initializing Redis for rate limiting: {str(e)}. Rate limiting will be disabled.")
            self.enabled = False
    
    async def check_rate_limit(self, client_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a client has exceeded their rate limit
        
        Args:
            client_id: Unique identifier for the client (e.g., IP address, API key)
            
        Returns:
            Tuple with (is_allowed, rate_limit_info)
        """
        if not self.enabled or not self.client:
            # If rate limiting is disabled, always allow
            return True, {
                "allowed": True,
                "limit": self.rate_limit,
                "remaining": self.rate_limit,
                "reset": int(time.time()) + self.window_size
            }
            
        try:
            # Create Redis key for this client
            key = f"rate:limit:{client_id}"
            current_time = int(time.time())
            window_start = current_time - self.window_size
            
            # Use pipeline for atomic operations
            pipe = self.client.pipeline()
            
            # Remove old entries outside the current window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count requests in the current window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration on the key
            pipe.expire(key, self.window_size)
            
            # Execute pipeline
            results = pipe.execute()
            
            # Get current count
            current_count = results[1]
            
            # Check if rate limit is exceeded
            is_allowed = current_count <= self.rate_limit
            remaining = max(0, self.rate_limit - current_count)
            
            # Calculate reset time
            oldest_request_time = self.client.zrange(key, 0, 0, withscores=True)
            if oldest_request_time and len(oldest_request_time) > 0:
                # Reset time is when the oldest request exits the window
                reset_time = int(oldest_request_time[0][1]) + self.window_size
            else:
                reset_time = current_time + self.window_size
            
            # Return result and rate limit info
            return is_allowed, {
                "allowed": is_allowed,
                "limit": self.rate_limit,
                "remaining": remaining,
                "reset": reset_time
            }
            
        except RedisError as e:
            logger.error(f"Redis error in check_rate_limit({client_id}): {str(e)}")
            # If there's an error, we'll allow the request but log it
            return True, {
                "allowed": True,
                "limit": self.rate_limit,
                "remaining": 0,  # Unknown
                "reset": int(time.time()) + self.window_size,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            # If there's an error, we'll allow the request but log it
            return True, {
                "allowed": True,
                "limit": self.rate_limit,
                "remaining": 0,  # Unknown
                "reset": int(time.time()) + self.window_size,
                "error": str(e)
            }