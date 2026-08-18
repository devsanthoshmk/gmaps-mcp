"""In-memory storage manager for Google Maps MCP tool results.

Provides thread-safe, memory-bounded storage for search results when
result_delivery='resource' is used. Returns MCP resource URI links without
exposing local filesystem paths.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gmaps_mcp.schemas import SearchGoogleMapsResult

logger = logging.getLogger("gmaps_mcp.storage")


@dataclass
class StoredEntry:
    resource_id: str
    result: SearchGoogleMapsResult
    created_at: float
    ttl_seconds: float

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class ResultStore:
    """Thread-safe, bounded in-memory store for search results."""

    def __init__(self, max_capacity: int = 1000, default_ttl_seconds: float = 86400.0) -> None:
        self._max_capacity = max_capacity
        self._default_ttl_seconds = default_ttl_seconds
        self._store: OrderedDict[str, StoredEntry] = OrderedDict()
        self._lock = threading.Lock()

    def store(
        self,
        result: SearchGoogleMapsResult,
        resource_id: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
    ) -> str:
        """Store a search result and return its unique resource ID."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
        if not resource_id:
            resource_id = f"search_{uuid.uuid4().hex[:16]}"

        entry = StoredEntry(
            resource_id=resource_id,
            result=result,
            created_at=time.time(),
            ttl_seconds=ttl,
        )

        with self._lock:
            self._purge_expired_locked()
            if resource_id in self._store:
                self._store.move_to_end(resource_id)
            self._store[resource_id] = entry

            # Enforce max capacity (evict oldest)
            while len(self._store) > self._max_capacity:
                self._store.popitem(last=False)

        logger.debug(
            "Stored result for resource_id=%s (total_results=%d)",
            resource_id,
            result.total_results,
        )
        return resource_id

    def get(self, resource_id: str) -> Optional[SearchGoogleMapsResult]:
        """Retrieve a stored search result by resource ID, or None if expired/not found."""
        with self._lock:
            entry = self._store.get(resource_id)
            if not entry:
                return None

            if entry.is_expired:
                del self._store[resource_id]
                return None

            # Mark as recently used
            self._store.move_to_end(resource_id)
            return entry.result

    def exists(self, resource_id: str) -> bool:
        """Check if a resource exists and is not expired."""
        return self.get(resource_id) is not None

    def delete(self, resource_id: str) -> bool:
        """Delete a stored result."""
        with self._lock:
            if resource_id in self._store:
                del self._store[resource_id]
                return True
            return False

    def clear(self) -> None:
        """Clear all stored results."""
        with self._lock:
            self._store.clear()

    def _purge_expired_locked(self) -> None:
        """Purge all expired entries while holding the lock."""
        expired_keys = [k for k, v in self._store.items() if v.is_expired]
        for k in expired_keys:
            del self._store[k]


# Global singleton store instance
result_store = ResultStore()
