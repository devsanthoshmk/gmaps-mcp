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
from collections.abc import Callable
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

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
        self._on_store_callbacks: List[Callable[[StoredEntry], None]] = []
        self._on_delete_callbacks: List[Callable[[str], None]] = []

    def add_store_callback(self, callback: Callable[[StoredEntry], None]) -> None:
        """Register a callback called whenever a new result is stored."""
        self._on_store_callbacks.append(callback)

    def add_delete_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback called whenever a result is deleted or evicted."""
        self._on_delete_callbacks.append(callback)

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

        evicted_ids: List[str] = []
        with self._lock:
            evicted_ids.extend(self._purge_expired_locked())
            if resource_id in self._store:
                self._store.move_to_end(resource_id)
            self._store[resource_id] = entry

            # Enforce max capacity (evict oldest)
            while len(self._store) > self._max_capacity:
                oldest_id, _ = self._store.popitem(last=False)
                evicted_ids.append(oldest_id)

        # Notify deletion callbacks for evicted entries
        for eid in evicted_ids:
            for cb in self._on_delete_callbacks:
                try:
                    cb(eid)
                except Exception as e:
                    logger.debug("Error in delete callback for %s: %s", eid, e)

        # Notify store callbacks
        for cb in self._on_store_callbacks:
            try:
                cb(entry)
            except Exception as e:
                logger.debug("Error in store callback for %s: %s", resource_id, e)

        logger.debug(
            "Stored result for resource_id=%s (total_results=%d)",
            resource_id,
            result.total_results,
        )
        return resource_id

    def get(self, resource_id: str) -> Optional[SearchGoogleMapsResult]:
        """Retrieve a stored search result by resource ID, or None if expired/not found."""
        expired_id: Optional[str] = None
        with self._lock:
            entry = self._store.get(resource_id)
            if not entry:
                return None

            if entry.is_expired:
                del self._store[resource_id]
                expired_id = resource_id
                entry = None
            else:
                self._store.move_to_end(resource_id)

        if expired_id:
            for cb in self._on_delete_callbacks:
                try:
                    cb(expired_id)
                except Exception:
                    pass
            return None

        return entry.result if entry else None

    def get_json(self, resource_id: str) -> Optional[str]:
        """Retrieve stored result formatted as JSON string."""
        res = self.get(resource_id)
        if res is not None:
            return res.model_dump_json(indent=2)
        return None

    def list_entries(self) -> List[StoredEntry]:
        """List all active non-expired stored entries."""
        with self._lock:
            self._purge_expired_locked()
            return list(self._store.values())

    def exists(self, resource_id: str) -> bool:
        """Check if a resource exists and is not expired."""
        return self.get(resource_id) is not None

    def delete(self, resource_id: str) -> bool:
        """Delete a stored result."""
        deleted = False
        with self._lock:
            if resource_id in self._store:
                del self._store[resource_id]
                deleted = True

        if deleted:
            for cb in self._on_delete_callbacks:
                try:
                    cb(resource_id)
                except Exception as e:
                    logger.debug("Error in delete callback for %s: %s", resource_id, e)
        return deleted

    def clear(self) -> None:
        """Clear all stored results."""
        all_ids: List[str] = []
        with self._lock:
            all_ids = list(self._store.keys())
            self._store.clear()

        for eid in all_ids:
            for cb in self._on_delete_callbacks:
                try:
                    cb(eid)
                except Exception:
                    pass

    def _purge_expired_locked(self) -> List[str]:
        """Purge all expired entries while holding the lock and return their IDs."""
        expired_keys = [k for k, v in self._store.items() if v.is_expired]
        for k in expired_keys:
            del self._store[k]
        return expired_keys


# Global singleton store instance
result_store = ResultStore()
