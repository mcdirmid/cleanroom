# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_212102_deepseek-flash_lru_cache_combined
# Timestamp: 2026-11-09T21:21:02.215127+00:00
# Benchmark Task: lru_cache
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 179,656
#   Cached Inbound Tokens:   6,292,480
#   Outbound Tokens:         155,347
#   Total Tokens:            6,627,483
#   Financial Cost ($USD):   $0.1390
#   Wall Clock Duration:     892.46s
#   Step Latencies (s):      [145.5, 188.7, 43.1, 40.8, 10.1, 20.3, 451.2, 134.8, 268.4, 20.3, 10.0]
#   Role Execution Rounds:   coverage: 1, lib: 1, pretense: 2, pretense_coverage: 1, pretense_qa: 2, qa: 2, test: 2 (Total: 11)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       22
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

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
class CacheError(PretenseSpecificationError):
    """Base exception for all cache operational errors."""

    pass


@data_type
class CacheCapacityError(CacheError):
    """Raised when an invalid non-positive capacity limit is specified."""

    pass


@data_type
class CacheKeyNotFoundError(CacheError):
    """Raised when attempting to remove or access a non-existent cache key."""

    pass


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
# LAST_CLEANED: 2026-11-09T21:24:17Z
# LAST_CHANGED: 2026-11-09T21:24:17Z
# CHANGE: Implement LRUCache interface: data-type errors and frozen CacheStats, poly_type protocol with operation-decorated stubs, @test_only keys_in_lru_order; use full pretense package path; remove scaffold TODOs.
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
"""Library implementation of a bounded least-recently-used cache."""

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
        self._items: OrderedDict[str, Any] = OrderedDict()
        self._capacity: int = 100
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    @property
    @override
    def capacity(self) -> int:
        # Expose the configured maximum number of entries.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # Report the current count of active entries.
        return len(self._items)

    @property
    @override
    def is_empty(self) -> bool:
        # Report whether no entries are currently active.
        return len(self._items) == 0

    @property
    @override
    def is_full(self) -> bool:
        # Report whether the entry count has reached the configured limit.
        return len(self._items) >= self._capacity

    @operation
    @override
    def configure(self, capacity: int) -> None:
        # Precondition: a non-positive limit is rejected with a capacity error.
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(
                "cache capacity must be greater than zero"
            )
        # Record the new limit before rebalancing the active entries.
        self._capacity = capacity
        # Evict least-recently-used entries while the cache is over the limit.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any]) -> Any:
        # A present key is promoted to most-recently-used and counted as a hit.
        if key in self._items:
            value = self._items.pop(key)
            self._items[key] = value
            self._hits += 1
            return value
        # An absent key counts as a miss and leaves recency order untouched.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        # An existing key is refreshed in place and promoted; size is unchanged.
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # A new key at capacity displaces the oldest entry and reports it.
        if len(self._items) >= self._capacity:
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return (evicted_key, evicted_value)
        # A new key below capacity is inserted as most-recently-used.
        self._items[key] = value
        return None

    @operation
    @override
    def peek(self, key: str, default: Optional[Any]) -> Any:
        # Look up the value without reordering entries or counting telemetry.
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        # Precondition: an absent key is rejected with a not-found error.
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(f"cache key not found: {key}")
        # Drop the entry and return the value it formerly held.
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        # Drop every entry while leaving the telemetry counters intact.
        self._items.clear()

    @operation
    @override
    def get_stats(self) -> lru_cache.CacheStats:
        # Report the cumulative hits, misses, and evictions.
        return lru_cache.CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    @operation
    @override
    def reset_stats(self) -> None:
        # Zero the telemetry counters without touching the cached entries.
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @operation
    @override
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        # Report keys from least- to most-recently-used without mutating state.
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
# LAST_CLEANED: 2026-11-09T21:35:51Z
# LAST_CHANGED: 2026-11-09T21:24:21Z
# CHANGE: Implement stateful LRUCache singleton over OrderedDict: capacity/size/is_empty/is_full, configure with capacity validation and LRU downsize eviction, get/put with recency promotion and eviction return, peek, remove with not-found error, clear preserving telemetry, stats get/reset, test-only keys_in_lru_order; tier=system; keep auto-generated __initialize__.
# COVERAGE_AUDIT: 2026-11-09T21:26:20Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T21:35:51Z
# PRETENSE_QA_AUDIT: 2026-11-09T21:35:29Z
# QA_AUDIT: 2026-11-09T21:26:07Z
# --- END AUTOFAB METADATA ---
