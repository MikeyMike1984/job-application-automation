# app/utils/rate_limiter.py
import asyncio
import time
from typing import Dict, Any, Callable, Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter for controlling request frequency."""
    
    def __init__(self, calls_per_second: float = 1.0):
        """Initialize rate limiter.
        
        Args:
            calls_per_second: Maximum number of calls per second
        """
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0.0
        self._lock = asyncio.Lock()
    
    async def wait(self):
        """Wait until it's safe to make another call."""
        async with self._lock:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_interval:
                delay = self.min_interval - elapsed
                await asyncio.sleep(delay)
            
            self.last_call_time = time.time()
    
    def __call__(self, func):
        """Decorator for rate limiting a function."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await self.wait()
            return await func(*args, **kwargs)
        
        return wrapper


class DomainRateLimiter:
    """Rate limiter for multiple domains."""
    
    def __init__(self, default_rate: float = 1.0, domain_rates: Optional[Dict[str, float]] = None):
        """Initialize domain-specific rate limiter.
        
        Args:
            default_rate: Default calls per second
            domain_rates: Dict mapping domains to calls per second
        """
        self.default_rate = default_rate
        self.domain_rates = domain_rates or {}
        self.limiters = {}
        
        # Create default limiter
        self.default_limiter = RateLimiter(default_rate)
        
        # Create domain-specific limiters
        for domain, rate in self.domain_rates.items():
            self.limiters[domain] = RateLimiter(rate)
    
    def get_limiter(self, domain: str) -> RateLimiter:
        """Get appropriate rate limiter for domain.
        
        Args:
            domain: Domain to get rate limiter for
            
        Returns:
            RateLimiter instance
        """
        # Try exact match
        if domain in self.limiters:
            return self.limiters[domain]
        
        # Try subdomain match
        for known_domain, limiter in self.limiters.items():
            if domain.endswith(f".{known_domain}") or known_domain.endswith(f".{domain}"):
                return limiter
        
        # Use default
        return self.default_limiter
    
    async def wait_for_domain(self, domain: str):
        """Wait according to rate limit for specified domain.
        
        Args:
            domain: Domain to wait for
        """
        limiter = self.get_limiter(domain)
        await limiter.wait()