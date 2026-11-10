# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_173614_deepseek-flash_lru_cache
# Timestamp: 2026-11-08T17:36:14.239663+00:00
# Benchmark Task: lru_cache
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 90,751
#   Cached Inbound Tokens:   2,175,488
#   Outbound Tokens:         36,036
#   Total Tokens:            2,302,275
#   Financial Cost ($USD):   $0.0418
#   Wall Clock Duration:     309.03s
#   Step Latencies (s):      [91.5, 134.3, 52.8, 71.0, 10.0, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 2, test: 2 (Total: 6)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       17
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: lru_cache.py ===
"""Low-level interface specification for bounded least-recently-used cache."""

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
# LAST_CLEANED: 2026-11-08T17:38:33Z
# LAST_CHANGED: 2026-11-08T17:38:33Z
# CHANGE: Implement interface module: data-type error hierarchy, frozen CacheStats telemetry record, and poly-type LRUCache protocol with all contracted members and package-qualified pretense import.
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
"""Low-level implementation specification for bounded least-recently-used cache."""

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
        # Backing store keeps entries ordered from least- to most-recently-used.
        self._items: OrderedDict[str, Any] = OrderedDict()
        # Default capacity limit is 100 entries.
        self._capacity: int = 100
        # Cumulative telemetry counters.
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    @property
    @override
    def capacity(self) -> int:
        # Expose the configured maximum entry count.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # Active entries are exactly the keys currently stored.
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
        # Reject non-positive limits with the contracted capacity error.
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(
                "Cache capacity must be greater than zero"
            )
        # Adopt the new limit.
        self._capacity = capacity
        # Evict least-recently-used entries until the cache fits the new limit.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any]) -> Any:
        # A present key is a hit: promote it and return its value.
        if key in self._items:
            value = self._items[key]
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return value
        # An absent key is a miss: leave recency order untouched.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        # Updating an existing key preserves size and promotes recency.
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # Inserting at capacity evicts the least-recently-used entry first.
        if len(self._items) >= self._capacity:
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return (evicted_key, evicted_value)
        # Inserting below capacity simply appends the newest entry.
        self._items[key] = value
        return None

    @operation
    @override
    def peek(self, key: str, default: Optional[Any]) -> Any:
        # Inspection neither reorders entries nor changes telemetry.
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        # Removal of an absent key is a contracted error.
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(
                f"Cache key not found: {key}"
            )
        # Removal shrinks the entry set and returns the stored value.
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        # Drop every entry while preserving telemetry counters.
        self._items.clear()

    @operation
    @override
    def get_stats(self) -> lru_cache.CacheStats:
        # Report the current cumulative telemetry snapshot.
        return lru_cache.CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    @operation
    @override
    def reset_stats(self) -> None:
        # Zero the counters without altering cached entries.
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @operation
    @override
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        # OrderedDict iteration yields keys from least to most recently used.
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
# LAST_CLEANED: 2026-11-08T17:41:10Z
# LAST_CHANGED: 2026-11-08T17:38:39Z
# CHANGE: Implement LRUCache singleton over OrderedDict: default capacity 100, recency promotion on get/put, capacity validation and downsizing eviction, peek/remove/clear, telemetry stats, reset, and LRU-ordered key listing with retained auto-generated registration.
# COVERAGE_AUDIT: 2026-11-08T17:41:10Z
# QA_AUDIT: 2026-11-08T17:40:57Z
# --- END AUTOFAB METADATA ---
