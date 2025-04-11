import logging
import traceback
import time
import json
from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Union, List
from contextlib import asynccontextmanager
import httpx
from fastapi import HTTPException, status

from app.services.circuit_breaker import CircuitBreakerError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Type variable for the function result
T = TypeVar('T')

# Error categories for better organization
class ErrorCategory:
    NETWORK = "network"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RESOURCE = "resource"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    UNKNOWN = "unknown"

class ErrorDetails:
    """Container for detailed error information"""
    
    def __init__(
        self,
        message: str,
        category: str = ErrorCategory.UNKNOWN,
        http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
        trace_id: Optional[str] = None,
    ):
        self.message = message
        self.category = category
        self.http_status = http_status
        self.exception = exception
        self.context = context or {}
        self.timestamp = timestamp or time.time()
        self.trace_id = trace_id
        
        # Get stack trace if exception is provided
        if exception:
            self.stack_trace = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        else:
            self.stack_trace = []
    
    def to_dict(self, include_private: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API responses and logging"""
        result = {
            "message": self.message,
            "category": self.category,
            "timestamp": self.timestamp,
        }
        
        # Add trace ID if available
        if self.trace_id:
            result["trace_id"] = self.trace_id
            
        # Add additional context that's safe to expose
        for key, value in self.context.items():
            if key not in ["password", "token", "secret", "api_key"]:
                result[key] = value
                
        # Include private details for logging (not for API responses)
        if include_private and self.exception:
            result["exception_type"] = type(self.exception).__name__
            result["stack_trace"] = self.stack_trace
            
        return result
    
    def log(self) -> None:
        """Log the error with appropriate level and details"""
        # Determine log level based on HTTP status
        if self.http_status >= 500:
            log_method = logger.error
        elif self.http_status >= 400:
            log_method = logger.warning
        else:
            log_method = logger.info
            
        # Format as JSON for structured logging
        error_details = self.to_dict(include_private=True)
        try:
            log_method(f"Error: {self.message} - {json.dumps(error_details)}")
        except:
            # Fallback if JSON serialization fails
            log_method(f"Error: {self.message} - Category: {self.category}")
            if self.exception:
                log_method(f"Exception: {type(self.exception).__name__}: {str(self.exception)}")

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException"""
        return HTTPException(
            status_code=self.http_status,
            detail={
                "error": self.to_dict(include_private=False)
            }
        )

class ErrorHandler:
    """Centralized error handling service"""
    
    @staticmethod
    def handle_exception(e: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorDetails:
        """
        Create appropriate ErrorDetails from an exception
        
        Args:
            e: The exception to handle
            context: Additional context information
            
        Returns:
            ErrorDetails object with categorized error information
        """
        context = context or {}
        
        # Handle different types of exceptions
        if isinstance(e, HTTPException):
            # Pass through FastAPI HTTP exceptions
            return ErrorDetails(
                message=str(e.detail) if isinstance(e.detail, str) else "HTTP error",
                category=ErrorCategory.VALIDATION,
                http_status=e.status_code,
                exception=e,
                context=context
            )
        elif isinstance(e, CircuitBreakerError):
            # Circuit breaker is open
            return ErrorDetails(
                message=f"Service temporarily unavailable: {str(e)}",
                category=ErrorCategory.EXTERNAL_SERVICE,
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                exception=e,
                context=context
            )
        elif isinstance(e, httpx.TimeoutException):
            # External service timeout
            return ErrorDetails(
                message="Request timed out",
                category=ErrorCategory.NETWORK,
                http_status=status.HTTP_504_GATEWAY_TIMEOUT,
                exception=e,
                context=context
            )
        elif isinstance(e, httpx.RequestError):
            # Network or connection error
            return ErrorDetails(
                message="Network error connecting to service",
                category=ErrorCategory.NETWORK,
                http_status=status.HTTP_502_BAD_GATEWAY,
                exception=e,
                context=context
            )
        elif isinstance(e, json.JSONDecodeError):
            # JSON parsing error
            return ErrorDetails(
                message="Error parsing JSON data",
                category=ErrorCategory.VALIDATION,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                exception=e,
                context=context
            )
        elif isinstance(e, ValueError):
            # Validation error
            return ErrorDetails(
                message=str(e),
                category=ErrorCategory.VALIDATION,
                http_status=status.HTTP_400_BAD_REQUEST,
                exception=e,
                context=context
            )
        else:
            # Generic server error
            return ErrorDetails(
                message=f"Internal server error: {str(e)}",
                category=ErrorCategory.SERVER,
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                exception=e,
                context=context
            )
    
    @staticmethod
    @asynccontextmanager
    async def try_catch_async(
        context: Optional[Dict[str, Any]] = None,
        fallback_result: Optional[T] = None,
        raise_error: bool = True
    ):
        """
        Async context manager for error handling
        
        Args:
            context: Additional context information
            fallback_result: Result to return if an error occurs and raise_error is False
            raise_error: Whether to raise the error or return fallback_result
            
        Yields:
            None
            
        Raises:
            HTTPException: If an error occurs and raise_error is True
        """
        try:
            yield
        except Exception as e:
            error_details = ErrorHandler.handle_exception(e, context)
            error_details.log()
            
            if raise_error:
                raise error_details.to_http_exception()
                
            # Otherwise, we'll just continue and return the fallback result later
    
    @staticmethod
    async def with_error_handling(
        func: Callable[..., Awaitable[T]],
        *args,
        context: Optional[Dict[str, Any]] = None,
        fallback_result: Optional[T] = None,
        raise_error: bool = True,
        **kwargs
    ) -> T:
        """
        Execute a function with error handling
        
        Args:
            func: Async function to execute
            *args: Arguments to pass to the function
            context: Additional context information
            fallback_result: Result to return if an error occurs and raise_error is False
            raise_error: Whether to raise the error or return fallback_result
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function or fallback_result if an error occurs
            
        Raises:
            HTTPException: If an error occurs and raise_error is True
        """
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_details = ErrorHandler.handle_exception(e, context)
            error_details.log()
            
            if raise_error:
                raise error_details.to_http_exception()
                
            return fallback_result