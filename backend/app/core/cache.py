"""In-memory thread-safe TTL Cache for MoveIQ backend.

Prevents query storms and repeated database lookups on page refreshes.
"""

from __future__ import annotations

import fnmatch
import threading
import time
from typing import Any, Dict, Optional, Tuple


class SimpleTtlCache:
    """Thread-safe in-memory cache with per-item TTL expiration."""

    def __init__(self, default_ttl: float = 600.0):
        self.default_ttl = default_ttl
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value if not expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expiry, val = entry
            if time.time() < expiry:
                return val
            # Expired, clean up
            del self._store[key]
            return None

    def set(self, key: str, val: Any, ttl: Optional[float] = None) -> None:
        """Store value with TTL."""
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            self._store[key] = (expiry, val)

    def delete(self, key: str) -> bool:
        """Remove key from cache."""
        with self._lock:
            return self._store.pop(key, None) is not None

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern (e.g. 'situations:*')."""
        with self._lock:
            keys_to_del = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
            for k in keys_to_del:
                del self._store[k]
            return len(keys_to_del)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)


# Global singleton instance (default TTL: 10 minutes)
cache = SimpleTtlCache(default_ttl=600.0)
