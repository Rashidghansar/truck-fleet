from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple
import time

class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.cleanup_interval = timedelta(minutes=5)
        self.last_cleanup = datetime.utcnow()
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """Check if request is allowed. Returns (is_allowed, remaining_requests)"""
        now = time.time()
        window_start = now - window_seconds
        
        # Clean up old entries
        if (datetime.utcnow() - self.last_cleanup) > self.cleanup_interval:
            self._cleanup()
            self.last_cleanup = datetime.utcnow()
        
        # Filter requests within window
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > window_start
        ]
        
        # Check if limit exceeded
        if len(self.requests[key]) >= max_requests:
            remaining = 0
        else:
            remaining = max_requests - len(self.requests[key])
        
        # Add current request
        self.requests[key].append(now)
        
        return len(self.requests[key]) <= max_requests, remaining
    
    def _cleanup(self):
        """Remove old entries"""
        now = time.time()
        keys_to_remove = []
        
        for key, requests in self.requests.items():
            # Keep only recent requests (last hour)
            self.requests[key] = [
                req_time for req_time in requests
                if req_time > (now - 3600)
            ]
            if not self.requests[key]:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.requests[key]

# Global rate limiter instance
rate_limiter = RateLimiter()

# Rate limit configurations per endpoint
RATE_LIMITS = {
    "/api/v1/auth/login": (5, 60),  # 5 requests per minute
    "/api/v1/auth/register": (3, 60),  # 3 requests per minute
    "/api/v1/auth/verify-phone": (10, 60),  # 10 requests per minute
    "/api/v1/auth/reset-password": (3, 60),  # 3 requests per minute
    "/api/v1/auth/forgot-password": (3, 60),  # 3 requests per minute
    "default": (100, 60),  # 100 requests per minute for other endpoints
}

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    # Skip rate limiting for health checks and docs
    if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # Get client identifier
    client_ip = request.client.host if request.client else "unknown"
    user_id = None
    
    # Try to get user ID from token if available
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from ..core.security import decode_token
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            if payload:
                user_id = payload.get("sub")
        except:
            pass
    
    # Use user_id if available, otherwise use IP
    identifier = f"{user_id}:{client_ip}" if user_id else client_ip
    
    # Get rate limit for this endpoint
    endpoint = request.url.path
    max_requests, window_seconds = RATE_LIMITS.get(endpoint, RATE_LIMITS["default"])
    
    # Check rate limit
    is_allowed, remaining = rate_limiter.is_allowed(
        f"{identifier}:{endpoint}",
        max_requests,
        window_seconds
    )
    
    if not is_allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "message": "Rate limit exceeded. Please try again later.",
                "retry_after": window_seconds
            },
            headers={
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + window_seconds)
            }
        )
    
    response = await call_next(request)
    
    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(max_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining - 1)
    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window_seconds)
    
    return response
