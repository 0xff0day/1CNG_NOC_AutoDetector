from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable


@dataclass
class CacheEntry:
    """Single cache entry with TTL."""
    key: str
    value: Any
    created_at: float
    ttl_sec: float
    access_count: int = 0
    last_accessed: float = 0.0


class CacheManager:
    """In-memory cache with TTL and LRU eviction."""
    
    def __init__(self, max_size: int = 1000, default_ttl_sec: float = 300.0):
        self.max_size = max_size
        self.default_ttl_sec = default_ttl_sec
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            # Check if expired
            if time.time() - entry.created_at > entry.ttl_sec:
                del self._cache[key]
                self._misses += 1
                return None
            
            # Update access stats
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._hits += 1
            
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl_sec: Optional[float] = None
    ):
        """Set value in cache."""
        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl_sec=ttl_sec or self.default_ttl_sec
            )
            self._cache[key] = entry
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self._cache:
            return
        
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_accessed
        )
        del self._cache[lru_key]
        self._evictions += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
                "evictions": self._evictions,
            }
    
    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        with self._lock:
            now = time.time()
            expired = [
                key for key, entry in self._cache.items()
                if now - entry.created_at > entry.ttl_sec
            ]
            for key in expired:
                del self._cache[key]
            return len(expired)


class DeviceDataCache:
    """Cache for device data with device-specific TTLs."""
    
    TTL_CONFIG = {
        "metrics": 60.0,  # 1 minute
        "device_info": 300.0,  # 5 minutes
        "interface_status": 120.0,  # 2 minutes
        "configuration": 600.0,  # 10 minutes
    }
    
    def __init__(self):
        self.cache = CacheManager(max_size=5000)
    
    def _make_key(self, device_id: str, data_type: str) -> str:
        """Create cache key."""
        return f"{device_id}:{data_type}"
    
    def get_device_metrics(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get cached device metrics."""
        return self.cache.get(self._make_key(device_id, "metrics"))
    
    def set_device_metrics(self, device_id: str, metrics: Dict[str, Any]):
        """Cache device metrics."""
        self.cache.set(
            self._make_key(device_id, "metrics"),
            metrics,
            self.TTL_CONFIG["metrics"]
        )
    
    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get cached device info."""
        return self.cache.get(self._make_key(device_id, "device_info"))
    
    def set_device_info(self, device_id: str, info: Dict[str, Any]):
        """Cache device info."""
        self.cache.set(
            self._make_key(device_id, "device_info"),
            info,
            self.TTL_CONFIG["device_info"]
        )
    
    def invalidate_device(self, device_id: str):
        """Invalidate all cache entries for a device."""
        for data_type in self.TTL_CONFIG.keys():
            self.cache.delete(self._make_key(device_id, data_type))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()


class ResultCache:
    """Cache for expensive operation results."""
    
    def __init__(self, ttl_sec: float = 300.0):
        self.cache = CacheManager(max_size=1000, default_ttl_sec=ttl_sec)
    
    def memoize(self, ttl_sec: Optional[float] = None):
        """Decorator to memoize function results."""
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                # Create cache key from function name and arguments
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                key = ":".join(key_parts)
                
                # Try to get from cache
                cached = self.cache.get(key)
                if cached is not None:
                    return cached
                
                # Compute and cache
                result = func(*args, **kwargs)
                self.cache.set(key, result, ttl_sec)
                return result
            
            return wrapper
        return decorator
