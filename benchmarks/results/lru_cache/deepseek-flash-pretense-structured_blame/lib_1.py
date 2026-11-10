# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_174130_deepseek-flash_lru_cache_pretense
# Timestamp: 2026-11-08T17:41:30.375311+00:00
# Benchmark Task: lru_cache
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 120,290
#   Cached Inbound Tokens:   3,406,208
#   Outbound Tokens:         74,681
#   Total Tokens:            3,601,179
#   Financial Cost ($USD):   $0.0731
#   Wall Clock Duration:     514.84s
#   Step Latencies (s):      [144.5, 225.7, 20.2, 73.2, 174.9, 10.1, 10.1]
#   Role Execution Rounds:   lib: 1, pretense: 2, pretense_coverage: 2, pretense_qa: 2 (Total: 7)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: lru_cache.py ===
"""Interface module for bounded least-recently-used cache."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Protocol, Tuple

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only
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
# LAST_CLEANED: 2026-11-08T17:44:00Z
# LAST_CHANGED: 2026-11-08T17:44:00Z
# CHANGE: Implement lru_cache interface module: CacheError/CacheCapacityError/CacheKeyNotFoundError data types, CacheStats frozen dataclass, and LRUCache poly_type Protocol declaring capacity/size/is_empty/is_full properties plus configure/get/put/peek/remove/clear/get_stats/reset_stats/keys_in_lru_order operations
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
"""Implementation module for bounded least-recently-used cache."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, List, Optional, Tuple

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import lru_cache


@singleton_type("system")
class LRUCache(lru_cache.LRUCache):
    """Concrete realization of least-recently-used cache using an ordered dictionary."""

    tier = system

    def __init__(self) -> None:
        # Backing store: insertion order doubles as access recency order (LRU first).
        self._items: OrderedDict[str, Any] = OrderedDict()
        self._capacity: int = 100
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    @property
    @override
    def capacity(self) -> int:
        # Expose the configured maximum entry limit.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # Current count of active entries.
        return len(self._items)

    @property
    @override
    def is_empty(self) -> bool:
        # Empty exactly when the entry count is zero.
        return len(self._items) == 0

    @property
    @override
    def is_full(self) -> bool:
        # Full once the entry count reaches the capacity limit.
        return len(self._items) >= self._capacity

    @operation
    @override
    def configure(self, capacity: int) -> None:
        # Precondition: non-positive limits are rejected with CacheCapacityError.
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(
                f"Cache capacity must be greater than zero, got {capacity}"
            )
        # Adopt the new maximum limit.
        self._capacity = capacity
        # Evict least-recently-used entries until the entry count fits the new limit.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any]) -> Any:
        # Hit: promote to most-recently-used and count the hit.
        if key in self._items:
            value = self._items[key]
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return value
        # Miss: return the default without disturbing recency order.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        # Update path: overwrite in place and promote; size is unchanged.
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # Capacity path: evict the least-recently-used entry before inserting.
        if len(self._items) >= self._capacity:
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return (evicted_key, evicted_value)
        # Insert path: append at the most-recently-used position.
        self._items[key] = value
        return None

    @operation
    @override
    def peek(self, key: str, default: Optional[Any]) -> Any:
        # Read-only lookup; no reordering and no telemetry changes.
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        # Precondition: removing an absent key raises CacheKeyNotFoundError.
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(
                f"Cache key {key!r} is not present"
            )
        # Drop the entry and return its value.
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        # Drop every entry.
        self._items.clear()
        # Telemetry counters are intentionally preserved.

    @operation
    @override
    def get_stats(self) -> lru_cache.CacheStats:
        # Snapshot the cumulative counters.
        return lru_cache.CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    @operation
    @override
    def reset_stats(self) -> None:
        # Zero the counters without touching cached entries.
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @operation
    @override
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        # Dictionary order runs least-recently-used to most-recently-used.
        # Return a shallow copy, never the live mapping view.
        return list(self._items.keys())


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LRUCache,
        keys=[LRUCache, lru_cache.LRUCache],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:50:01Z
# LAST_CHANGED: 2026-11-08T17:44:06Z
# CHANGE: Implement LRUCache singleton realizations: OrderedDict-backed entries with default capacity 100, recency promotion on get/put, LRU eviction counters, capacity downsize eviction with CacheCapacityError guard, CacheKeyNotFoundError on absent remove, preserved telemetry across clear, CacheStats snapshot/reset, and test-only LRU key ordering
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:50:01Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:49:49Z
# --- END AUTOFAB METADATA ---
