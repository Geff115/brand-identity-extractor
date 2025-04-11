import logging
import json
import time
import hashlib
from typing import Any, Optional, Dict, Union
import redis
from redis.exceptions import RedisError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CacheService:
    """Service for caching API responses in Redis"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", expire_time: int = 86400):
        """
        Initialize the cache service
        
        Args:
            redis_url: Redis connection URL
            expire_time: Default cache expiration time in seconds (1 day)
        """
        self.redis_url = redis_url
        self.expire_time = expire_time
        self.enabled = True
        self.client = None
        
        try:
            self.client = redis.from_url(redis_url)
            # Test connection
            self.client.ping()
            logger.info(f"Connected to Redis at {redis_url}")
        except RedisError as e:
            logger.warning(f"Redis connection failed: {str(e)}. Caching will be disabled.")
            self.enabled = False
        except Exception as e:
            logger.warning(f"Error initializing Redis cache: {str(e)}. Caching will be disabled.")
            self.enabled = False
    
    def create_key(self, prefix: str, data: Any) -> str:
        """
        Create a cache key from prefix and data
        
        Args:
            prefix: Key prefix (e.g., 'url', 'logo')
            data: Data to hash for the key
            
        Returns:
            Cache key as string
        """
        # Convert data to string and create hash
        if isinstance(data, dict) or isinstance(data, list):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        
        # Create MD5 hash of the data
        hash_obj = hashlib.md5(data_str.encode())
        hash_str = hash_obj.hexdigest()
        
        # Combine prefix and hash
        return f"{prefix}:{hash_str}"
    
    async def get(self, key: str) -> Optional[Dict]:
        """
        Get data from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found
        """
        if not self.enabled or not self.client:
            return None
            
        try:
            # Get data from Redis
            data = self.client.get(key)
            if data:
                # Parse JSON data
                return json.loads(data)
            return None
        except RedisError as e:
            logger.error(f"Redis error in get({key}): {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error getting data from cache: {str(e)}")
            return None
    
    async def set(self, key: str, data: Any, expire: Optional[int] = None) -> bool:
        """
        Set data in cache
        
        Args:
            key: Cache key
            data: Data to cache
            expire: Expiration time in seconds (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            return False
            
        try:
            # Convert data to JSON
            json_data = json.dumps(data)
            
            # Set expiration time
            expiration = expire if expire is not None else self.expire_time
            
            # Set data in Redis
            self.client.setex(key, expiration, json_data)
            return True
        except RedisError as e:
            logger.error(f"Redis error in set({key}): {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error setting data in cache: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete data from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            return False
            
        try:
            # Delete key from Redis
            self.client.delete(key)
            return True
        except RedisError as e:
            logger.error(f"Redis error in delete({key}): {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error deleting data from cache: {str(e)}")
            return False
    
    async def clear_all(self) -> bool:
        """
        Clear all cache data
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            return False
            
        try:
            # Flush all data from Redis (dangerous, use with caution!)
            self.client.flushall()
            return True
        except RedisError as e:
            logger.error(f"Redis error in clear_all(): {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False