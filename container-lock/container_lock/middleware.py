from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import redis
import time
import logging
from container_lock.config import config
from container_lock.utils import get_client_ip

logger = logging.getLogger(__name__)

class IPLockMiddleware:
    """
    Redis-based IP locking middleware for session endpoints.
    Prevents concurrent session requests from the same IP address.
    Based on the guide for handling real IPs behind Caddy.
    """
    
    def __init__(self, redis_url: str = None, lock_timeout: int = 30):
        self.redis_client = redis.Redis.from_url(redis_url or config.REDIS_URL, decode_responses=True)
        self.lock_timeout = lock_timeout
        self.session_paths = ["/acquire", "/release", "/end-session"]
    
    async def __call__(self, request: Request, call_next):
        """
        Middleware that implements IP-based locking for session endpoints
        """
        # Check if this is a session endpoint that needs locking
        if not self._is_session_endpoint(request.url.path):
            return await call_next(request)
        
        # Extract real client IP (handles Caddy proxy)
        client_ip = get_client_ip(request)
        if client_ip == "unknown":
            logger.warning("[IP_LOCK] No valid client IP found")
            return JSONResponse(
                status_code=400,
                content={"error": "Unable to determine client IP address"}
            )
        
        # Create lock key for this IP
        lock_key = f"session_lock:{client_ip}"
        
        # Try to acquire lock
        lock_acquired = False
        try:
            # Use Redis SET with NX (not exists) and EX (expire) for atomic lock
            lock_acquired = self.redis_client.set(
                lock_key, 
                int(time.time()), 
                nx=True,  # Only set if key doesn't exist
                ex=self.lock_timeout  # Expire after timeout
            )
            
            if not lock_acquired:
                logger.warning(f"[IP_LOCK] IP {client_ip} blocked - concurrent session request")
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": f"IP {client_ip} already has an active session request",
                        "retry_after": 5  # Suggest retry after 5 seconds
                    }
                )
            
            logger.info(f"[IP_LOCK] Lock acquired for IP {client_ip} on {request.url.path}")
            
            # Process the request
            response = await call_next(request)
            
            return response
            
        except redis.RedisError as e:
            logger.error(f"[IP_LOCK] Redis error: {e}")
            # If Redis is down, allow request to proceed (fail open)
            return await call_next(request)
            
        finally:
            # Always release lock after request completion
            if lock_acquired:
                try:
                    self.redis_client.delete(lock_key)
                    logger.info(f"[IP_LOCK] Lock released for IP {client_ip}")
                except redis.RedisError as e:
                    logger.error(f"[IP_LOCK] Error releasing lock: {e}")
    
    def _is_session_endpoint(self, path: str) -> bool:
        """Check if the path is a session endpoint that requires locking"""
        return any(path.startswith(session_path) for session_path in self.session_paths)

def create_ip_lock_middleware(redis_url: str = None, lock_timeout: int = 30):
    """Factory function to create IP lock middleware"""
    return IPLockMiddleware(redis_url, lock_timeout) 