from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(default=0.0)
    last_update: float = field(default_factory=time.time)
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket."""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_update = now
    
    def get_status(self) -> Dict[str, Any]:
        """Get bucket status."""
        self._refill()
        return {
            "capacity": self.capacity,
            "tokens": round(self.tokens, 2),
            "refill_rate": self.refill_rate,
            "available": int(self.tokens),
        }


class RateLimiter:
    """Rate limiter for API calls and operations."""
    
    def __init__(self):
        self.buckets: Dict[str, RateLimitBucket] = {}
    
    def configure_limit(
        self,
        key: str,
        capacity: int,
        refill_rate: float
    ):
        """Configure rate limit for a key."""
        self.buckets[key] = RateLimitBucket(
            capacity=capacity,
            refill_rate=refill_rate,
            tokens=capacity  # Start with full bucket
        )
    
    def check_rate_limit(self, key: str, tokens: int = 1) -> Dict[str, Any]:
        """Check if operation is within rate limit."""
        bucket = self.buckets.get(key)
        if not bucket:
            return {"allowed": True, "reason": "no_limit_configured"}
        
        allowed = bucket.consume(tokens)
        status = bucket.get_status()
        
        return {
            "allowed": allowed,
            "key": key,
            "tokens_remaining": status["tokens"],
            "capacity": status["capacity"],
            "retry_after": self._calculate_retry_after(bucket) if not allowed else 0,
        }
    
    def _calculate_retry_after(self, bucket: RateLimitBucket) -> float:
        """Calculate seconds until next token available."""
        if bucket.tokens >= 1:
            return 0.0
        return (1 - bucket.tokens) / bucket.refill_rate
    
    def get_all_statuses(self) -> Dict[str, Any]:
        """Get status of all rate limit buckets."""
        return {
            key: bucket.get_status()
            for key, bucket in self.buckets.items()
        }


class DeviceRateLimiter:
    """Rate limiting specifically for device operations."""
    
    # Default limits per device
    DEFAULT_LIMITS = {
        "ssh_connections": {"capacity": 10, "refill_rate": 1.0},  # 10 per 10 sec
        "commands_per_minute": {"capacity": 60, "refill_rate": 1.0},
        "config_changes": {"capacity": 5, "refill_rate": 0.1},  # 5 per 50 sec
    }
    
    def __init__(self):
        self.limiters: Dict[str, RateLimiter] = {}
    
    def _get_device_limiter(self, device_id: str) -> RateLimiter:
        """Get or create rate limiter for device."""
        if device_id not in self.limiters:
            limiter = RateLimiter()
            for key, config in self.DEFAULT_LIMITS.items():
                limiter.configure_limit(
                    key,
                    config["capacity"],
                    config["refill_rate"]
                )
            self.limiters[device_id] = limiter
        return self.limiters[device_id]
    
    def check_operation(
        self,
        device_id: str,
        operation_type: str
    ) -> Dict[str, Any]:
        """Check if device operation is allowed."""
        limiter = self._get_device_limiter(device_id)
        return limiter.check_rate_limit(operation_type)
    
    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Get rate limit status for device."""
        limiter = self._get_device_limiter(device_id)
        return {
            "device_id": device_id,
            "limits": limiter.get_all_statuses(),
        }


class GlobalRateLimiter:
    """Global rate limits across entire system."""
    
    def __init__(self):
        self.limiter = RateLimiter()
        
        # Configure global limits
        self.limiter.configure_limit("api_requests", capacity=1000, refill_rate=10.0)
        self.limiter.configure_limit("alert_creations", capacity=100, refill_rate=5.0)
        self.limiter.configure_limit("report_generations", capacity=10, refill_rate=0.1)
        self.limiter.configure_limit("device_discoveries", capacity=50, refill_rate=2.0)
    
    def check(self, operation: str) -> Dict[str, Any]:
        """Check global rate limit."""
        return self.limiter.check_rate_limit(operation)
