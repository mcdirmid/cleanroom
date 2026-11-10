"""Low-level interface specification for bounded least-recently-used cache."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Protocol, Tuple
from pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
class CacheError(PretenseSpecificationError):
    """Base exception for all cache operational errors."""


@data_type
class CacheCapacityError(CacheError):
    """Raised when an invalid non-positive capacity limit is specified."""


@data_type
class CacheKeyNotFoundError(CacheError):
    """Raised when attempting to remove or access a non-existent cache key."""


@data_type
@dataclass(frozen=True)
class CacheStats:
    """Operational telemetry counters for cache access operations.

    Args:
        hits: Cumulative count of successful key lookups.
        misses: Cumulative count of failed key lookups.
        evictions: Cumulative count of entries evicted due to capacity constraints.
    """
    hits: int = 0
    misses: int = 0
    evictions: int = 0


@poly_type
class LRUCache(Protocol):
    """Bounded memory cache with access recency tracking and overflow eviction."""

    @property
    def capacity(self) -> int:
        """Maximum number of key-value entries permitted in the cache."""
        ...

    @property
    def size(self) -> int:
        """Current count of active key-value entries in the cache."""
        ...

    @property
    def is_empty(self) -> bool:
        """Indicates whether the cache currently contains zero entries."""
        ...

    @property
    def is_full(self) -> bool:
        """Indicates whether the cache has reached its maximum capacity limit."""
        ...

    @operation
    def configure(self, capacity: int) -> None:
        """Configures the maximum capacity limit of the cache.

        Args:
            capacity: Maximum number of entries permitted.

        Raises:
            CacheCapacityError: If capacity is less than or equal to zero.

        PRECONDITIONS:
        - [slug:lru_cache.configure.invalid_capacity]: WHEN capacity is less than or equal to zero, MUST raise CacheCapacityError.

        POSTCONDITIONS:
        - [slug:lru_cache.configure.update_limit]: MUST update the cache capacity limit to the specified value.
        - [slug:lru_cache.configure.downsize_eviction]: WHEN new capacity is smaller than current size, MUST evict least-recently-used entries in sequence until size equals capacity, incrementing the evictions counter for each evicted entry.
        """
        ...

    @operation
    def get(self, key: str, default: Optional[Any]) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used.

        Args:
            key: Lookup key.
            default: Value to return if key is absent.

        Returns:
            The associated value if present, or default if absent.

        POSTCONDITIONS:
        - [slug:lru_cache.get.hit]: WHEN key is present in cache, MUST return the associated value, promote key to most-recently-used position, and increment hits counter.
        - [slug:lru_cache.get.miss]: WHEN key is absent from cache, MUST return default value and increment misses counter without altering access order.
        """
        ...

    @operation
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used.

        Args:
            key: Cache key.
            value: Associated value to store.

        Returns:
            Tuple of (evicted_key, evicted_value) if an entry was evicted, or None otherwise.

        POSTCONDITIONS:
        - [slug:lru_cache.put.update_existing]: WHEN key already exists in cache, MUST update its stored value, promote key to most-recently-used position without increasing size, and return None.
        - [slug:lru_cache.put.evict_on_capacity]: WHEN key is new and size is at capacity, MUST evict the least-recently-used entry, increment evictions counter, store the new entry at the most-recently-used position, and return tuple of (evicted_key, evicted_value).
        - [slug:lru_cache.put.insert_below_capacity]: WHEN key is new and size is below capacity, MUST store entry at most-recently-used position, increment size by 1, and return None.
        """
        ...

    @operation
    def peek(self, key: str, default: Optional[Any]) -> Any:
        """Inspects a cached value without altering access recency or telemetry.

        Args:
            key: Lookup key.
            default: Value to return if key is absent.

        Returns:
            The associated value if present, or default if absent.

        POSTCONDITIONS:
        - [slug:lru_cache.peek.present_key]: WHEN key is present in cache, MUST return the associated value without modifying access recency order or incrementing telemetry counters.
        - [slug:lru_cache.peek.absent_key]: WHEN key is absent from cache, MUST return default value without modifying access recency order or incrementing telemetry counters.
        """
        ...

    @operation
    def remove(self, key: str) -> Any:
        """Removes a key-value entry from the cache.

        Args:
            key: Key to remove.

        Returns:
            The value that was associated with the removed key.

        Raises:
            CacheKeyNotFoundError: If key is not present in the cache.

        PRECONDITIONS:
        - [slug:lru_cache.remove.key_not_found]: WHEN key is absent from cache, MUST raise CacheKeyNotFoundError.

        POSTCONDITIONS:
        - [slug:lru_cache.remove.existing_key]: WHEN key exists in cache, MUST remove entry, decrement size by 1, and return removed value.
        """
        ...

    @operation
    def clear(self) -> None:
        """Removes all entries from the cache while preserving operational telemetry.

        POSTCONDITIONS:
        - [slug:lru_cache.clear.reset_entries]: MUST remove all key-value entries from the cache and reset size to zero.
        - [slug:lru_cache.clear.preserve_telemetry]: MUST preserve telemetry counters across clear operations.
        """
        ...

    @operation
    def get_stats(self) -> CacheStats:
        """Produces current operational telemetry statistics.

        Returns:
            Immutable CacheStats record reflecting hits, misses, and evictions.

        POSTCONDITIONS:
        - [slug:lru_cache.stats.report_telemetry]: MUST return CacheStats reflecting cumulative hits, misses, and evictions.
        """
        ...

    @operation
    def reset_stats(self) -> None:
        """Resets operational telemetry counters to zero.

        POSTCONDITIONS:
        - [slug:lru_cache.stats.reset_telemetry]: MUST reset hits, misses, and evictions counters to zero without altering cached entries.
        """
        ...

    @operation
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        """Produces active cache keys ordered from least-recently-used to most-recently-used.

        Returns:
            List of active cache keys in access recency ascending order.

        POSTCONDITIONS:
        - [slug:lru_cache.keys.lru_order]: MUST return all active cache keys ordered from least-recently-used to most-recently-used.
        - [slug:lru_cache.keys.non_mutating]: MUST NOT alter access recency order or increment operational telemetry counters.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T07:51:09Z
# LAST_CHANGED: 2026-11-02T19:50:00Z
# CHANGE: Add keys_in_lru_order @test_only observability query to LRUCache
# CODE_HASH: 25aaf0ad82fd
# SPEC_QA_AUDIT: 2026-11-10T07:51:09Z
# --- END AUTOFAB METADATA ---
