# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261115_091554_deepseek-flash_lru_cache_pretense
# Timestamp: 2026-11-15T09:15:54.236382+00:00
# Benchmark Task: lru_cache
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 119,630
#   Cached Inbound Tokens:   3,093,120
#   Outbound Tokens:         86,122
#   Total Tokens:            3,298,872
#   Financial Cost ($USD):   $0.0789
#   Wall Clock Duration:     533.99s
#   Step Latencies (s):      [127.0, 327.3, 153.1, 10.1, 20.3]
#   Role Execution Rounds:   lib: 1, pretense_coverage: 1, pretense_impl: 1, pretense_intf: 1, pretense_qa: 1 (Total: 5)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       3
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: lru_cache.py ===
"""Library interface for a bounded least-recently-used cache."""

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
        """
        ...

    @operation
    def clear(self) -> None:
        """Removes all entries from the cache while preserving operational telemetry."""
        ...

    @operation
    def get_stats(self) -> CacheStats:
        """Produces current operational telemetry statistics.

        Returns:
            Immutable CacheStats record reflecting hits, misses, and evictions.
        """
        ...

    @operation
    def reset_stats(self) -> None:
        """Resets operational telemetry counters to zero."""
        ...

    @operation
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        """Produces active cache keys ordered from least-recently-used to most-recently-used.

        Returns:
            List of active cache keys in access recency ascending order.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T09:17:51Z
# LAST_CHANGED: 2026-11-15T09:17:51Z
# CHANGE: Implement LRUCache interface module: data_type cache exceptions, frozen CacheStats telemetry record, and poly_type LRUCache protocol with capacity/eviction contracts
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
"""Library implementation of a bounded least-recently-used cache."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, List, Optional, Tuple

from pretense import test_only

from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import lru_cache


@singleton
class LRUCache(lru_cache.LRUCache):
    """Concrete least-recently-used cache backed by an ordered dictionary."""

    tier = "system"

    def __init__(self) -> None:
        self._items: OrderedDict[str, Any] = OrderedDict()
        self._capacity: int = 100
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    @property
    @override
    def capacity(self) -> int:
        return self._capacity

    @property
    @override
    def size(self) -> int:
        return len(self._items)

    @property
    @override
    def is_empty(self) -> bool:
        return len(self._items) == 0

    @property
    @override
    def is_full(self) -> bool:
        return len(self._items) >= self._capacity

    @operation
    @override
    def configure(self, capacity: int) -> None:
        # Reject non-positive limits before touching cache state.
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(
                f"Cache capacity must be greater than zero, got {capacity}"
            )
        self._capacity = capacity
        # Shrink the cache by evicting least-recently-used entries until it fits.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any]) -> Any:
        # A present key is promoted to most-recently-used and recorded as a hit.
        if key in self._items:
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return self._items[key]
        # An absent key records a miss and leaves access order untouched.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        # Updating an existing key never changes the cache size.
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # A new key at capacity evicts the least-recently-used entry.
        if len(self._items) >= self._capacity:
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return (evicted_key, evicted_value)
        # A new key below capacity is simply inserted at the most-recently-used position.
        self._items[key] = value
        return None

    @operation
    @override
    def peek(self, key: str, default: Optional[Any]) -> Any:
        # Inspection returns the stored value without reordering or counting.
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        # Removal requires the key to be present.
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(f"Cache key not found: {key!r}")
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        # Entries are discarded while telemetry counters are retained.
        self._items.clear()

    @operation
    @override
    def get_stats(self) -> lru_cache.CacheStats:
        return lru_cache.CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    @operation
    @override
    def reset_stats(self) -> None:
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @operation
    @override
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        # Keys follow insertion order, which tracks recency after every promotion.
        return list(self._items.keys())

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T09:24:37Z
# LAST_CHANGED: 2026-11-15T09:17:57Z
# CHANGE: Implement concrete singleton LRUCache with OrderedDict backing, recency promotion, LRU eviction, capacity downsize, key removal, telemetry counters, and LRU key ordering
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T09:24:37Z
# PRETENSE_QA_AUDIT: 2026-11-15T09:24:21Z
# --- END AUTOFAB METADATA ---
