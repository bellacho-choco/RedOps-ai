"""
====================================================================
PROJECT REDOPS-AI - CONNECTION POOL & CACHING LAYER
High-performance HTTP connection pooling with intelligent caching
====================================================================
"""

import asyncio
import time
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from contextlib import asynccontextmanager
import httpx


@dataclass
class CacheEntry:
    """Represents a cached HTTP response with metadata."""
    data: Dict[str, Any]
    timestamp: float
    ttl: int
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


class ResponseCache:
    """
    Intelligent HTTP response cache with TTL and hit tracking.
    """
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0
    
    def _generate_key(self, method: str, url: str, 
                     params: Optional[Dict] = None,
                     headers: Optional[Dict] = None,
                     body: Optional[str] = None) -> str:
        """Generate cache key from request components."""
        key_data = f"{method}:{url}"
        if params:
            key_data += json.dumps(params, sort_keys=True)
        if headers:
            # Only include cache-relevant headers
            cache_headers = {k: v for k, v in headers.items() 
                           if k.lower() in ['authorization', 'accept', 'content-type']}
            if cache_headers:
                key_data += json.dumps(cache_headers, sort_keys=True)
        if body:
            key_data += body
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def get(self, method: str, url: str, 
                 params: Optional[Dict] = None,
                 headers: Optional[Dict] = None,
                 body: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve cached response if available and not expired."""
        key = self._generate_key(method, url, params, headers, body)
        
        async with self._lock:
            entry = self.cache.get(key)
            if entry and not entry.is_expired():
                entry.hit_count += 1
                self.hits += 1
                return entry.data
            self.misses += 1
            return None
    
    async def set(self, method: str, url: str, data: Dict[str, Any],
                ttl: Optional[int] = None,
                params: Optional[Dict] = None,
                headers: Optional[Dict] = None,
                body: Optional[str] = None):
        """Cache response with configurable TTL."""
        key = self._generate_key(method, url, params, headers, body)
        ttl = ttl or self.default_ttl
        
        async with self._lock:
            if len(self.cache) >= self.max_size:
                # Evict least recently used (simple FIFO based on hit count)
                lru_key = min(self.cache.keys(), 
                            key=lambda k: self.cache[k].hit_count)
                del self.cache[lru_key]
            
            self.cache[key] = CacheEntry(
                data=data,
                timestamp=time.time(),
                ttl=ttl
            )
    
    async def clear(self):
        """Clear all cached entries."""
        async with self._lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests) if total_requests > 0 else 0
            
            return {
                "entries": len(self.cache),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(hit_rate * 100, 2),
                "max_size": self.max_size
            }


class ConnectionPoolManager:
    """
    Manages HTTP connection pools with intelligent caching and retry logic.
    """
    def __init__(self, 
                 max_connections: int = 100,
                 max_keepalive_connections: int = 20,
                 enable_cache: bool = True,
                 cache_size: int = 1000,
                 cache_ttl: int = 300):
        self.enable_cache = enable_cache
        self.cache = ResponseCache(max_size=cache_size, default_ttl=cache_ttl) if enable_cache else None
        
        # Configure connection limits
        self.limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections
        )
        
        # Dynamically detect HTTP/2 support
        http2_supported = False
        try:
            import h2  # noqa: F401
            http2_supported = True
        except ImportError:
            http2_supported = False

        # Create async client with connection pooling
        self.client = httpx.AsyncClient(
            limits=self.limits,
            timeout=httpx.Timeout(30.0, connect=10.0),
            http2=http2_supported,
            verify=True  # SSL verification
        )
    
    async def request(self, method: str, url: str,
                     params: Optional[Dict] = None,
                     headers: Optional[Dict] = None,
                     json_data: Optional[Dict] = None,
                     data: Optional[str] = None,
                     use_cache: bool = True,
                     cache_ttl: Optional[int] = None,
                     max_retries: int = 3) -> Dict[str, Any]:
        """
        Execute HTTP request with caching and retry logic.
        """
        # Check cache first if enabled
        if self.enable_cache and use_cache:
            cached = await self.cache.get(
                method, url, params, headers, 
                json.dumps(json_data) if json_data else data
            )
            if cached:
                cached["cached"] = True
                return cached
        
        # Execute request with retry logic
        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    json=json_data,
                    content=data.encode() if data else None
                )
                
                result = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "content": response.text,
                    "json": None,
                    "elapsed_ms": response.elapsed.total_seconds() * 1000,
                    "cached": False
                }
                
                # Try to parse JSON response
                try:
                    result["json"] = response.json()
                except:
                    pass
                
                # Cache successful responses
                if self.enable_cache and use_cache and response.status_code == 200:
                    await self.cache.set(
                        method, url, result, cache_ttl,
                        params, headers,
                        json.dumps(json_data) if json_data else data
                    )
                
                return result
                
            except httpx.TimeoutError as e:
                last_error = e
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
            except httpx.RequestError as e:
                last_error = e
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
        
        raise last_error or Exception("Max retries exceeded")
    
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for GET requests."""
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for POST requests."""
        return await self.request("POST", url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for PUT requests."""
        return await self.request("PUT", url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for DELETE requests."""
        return await self.request("DELETE", url, **kwargs)
    
    async def close(self):
        """Close the connection pool."""
        await self.client.aclose()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get connection pool and cache statistics."""
        cache_stats = await self.cache.get_stats() if self.cache else {"enabled": False}
        
        return {
            "connection_pool": {
                "max_connections": self.limits.max_connections,
                "max_keepalive": self.limits.max_keepalive_connections
            },
            "cache": cache_stats
        }


# Global connection pool instance
connection_pool = ConnectionPoolManager()


@asynccontextmanager
async def get_connection_pool():
    """Context manager for using the connection pool."""
    try:
        yield connection_pool
    finally:
        # Pool is kept alive for reuse
        pass