import logging
import time
import asyncio
from typing import Callable, Any, Dict, Optional
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    """Circuit breaker pattern implementation for external service calls"""
    
    # Circuit states
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Service calls are blocked
    HALF_OPEN = "half_open"  # Testing if service is restored
    
    def __init__(self, name: str, failure_threshold: int = 5, 
                 recovery_timeout: int = 30, timeout: float = 10.0):
        """
        Initialize the circuit breaker
        
        Args:
            name: Name of the protected service
            failure_threshold: Number of failures before opening the circuit
            recovery_timeout: Seconds before attempting recovery
            timeout: Timeout for service calls in seconds
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.timeout = timeout
        
        # State
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.successes_since_last_failure = 0
        
        logger.info(f"Circuit breaker {name} initialized")
    
    async def call(self, func, *args, **kwargs):
        """
        Execute the function with circuit breaker protection
        
        Args:
            func: Async function to call
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            CircuitBreakerError: If circuit is open
            Various exceptions from the called function
        """
        if self.state == self.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(f"Circuit {self.name} transitioning from OPEN to HALF-OPEN")
                self.state = self.HALF_OPEN
            else:
                # Circuit is still open
                raise CircuitBreakerError(
                    f"Circuit {self.name} is OPEN. Service call rejected."
                )
        
        try:
            # Set a timeout for the function call
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.timeout)
            
            # On success in half-open state, close the circuit
            if self.state == self.HALF_OPEN:
                self.successes_since_last_failure += 1
                if self.successes_since_last_failure >= 2:  # Require 2 successes to fully close
                    logger.info(f"Circuit {self.name} transitioning from HALF-OPEN to CLOSED")
                    self.reset()
            
            return result
            
        except Exception as e:
            # Record the failure
            self.record_failure(e)
            raise
    
    def record_failure(self, exception: Exception) -> None:
        """Record a failure and possibly open the circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.successes_since_last_failure = 0
        
        if self.state == self.CLOSED and self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit {self.name} transitioning from CLOSED to OPEN: "
                f"{self.failure_count} failures occurred. Last error: {str(exception)}"
            )
            self.state = self.OPEN
        elif self.state == self.HALF_OPEN:
            logger.warning(
                f"Circuit {self.name} transitioning from HALF-OPEN to OPEN: "
                f"Failed recovery attempt. Error: {str(exception)}"
            )
            self.state = self.OPEN
    
    def reset(self) -> None:
        """Reset the circuit breaker to its original state"""
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.successes_since_last_failure = 0
        
        logger.info(f"Circuit {self.name} reset to CLOSED state")

# Create a registry of circuit breakers for different services
circuit_breakers = {
    "openai": CircuitBreaker("openai", failure_threshold=3, recovery_timeout=60),
    "redis": CircuitBreaker("redis", failure_threshold=3, recovery_timeout=30),
    "scraper": CircuitBreaker("scraper", failure_threshold=5, recovery_timeout=120, timeout=30.0),
}

def with_circuit_breaker(service_name: str, fallback_function: Optional[Callable] = None):
    """
    Decorator to protect a function with a circuit breaker
    
    Args:
        service_name: Name of the service to protect
        fallback_function: Optional function to call if circuit is open
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            circuit = circuit_breakers.get(service_name)
            if not circuit:
                # No circuit breaker for this service, just call the function
                return await func(*args, **kwargs)
            
            try:
                # Call through the circuit breaker
                return await circuit.call(func, *args, **kwargs)
            except CircuitBreakerError as e:
                logger.warning(f"Circuit is open for {service_name}: {str(e)}")
                # Try fallback if provided
                if fallback_function:
                    logger.info(f"Using fallback for {service_name}")
                    return await fallback_function(*args, **kwargs)
                # Re-raise if no fallback
                raise
                
        return wrapper
    return decorator