# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_221316_gemini-flash_lru_cache_combined
# Timestamp: 2026-11-09T22:13:16.245633+00:00
# Benchmark Task: lru_cache
# Model: gemini-flash (Tier 2)
# Methodology: combined
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 730,917
#   Cached Inbound Tokens:   4,445,939
#   Outbound Tokens:         105,011
#   Total Tokens:            5,281,867
#   Financial Cost ($USD):   $0.2262
#   Wall Clock Duration:     453.46s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 2, lib: 2, pretense: 1, pretense_coverage: 1, pretense_qa: 1, qa: 1, test: 1 (Total: 9)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       19
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: lru_cache.py ===
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
        """Configures the maximum capacity limit of the cache."""
        ...

    @operation
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used."""
        ...

    @operation
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used."""
        ...

    @operation
    def peek(self, key: str, default: Optional[Any] = None) -> Any:
        """Inspects a cached value without altering access recency or telemetry."""
        ...

    @operation
    def remove(self, key: str) -> Any:
        """Removes a key-value entry from the cache."""
        ...

    @operation
    def clear(self) -> None:
        """Removes all entries from the cache while preserving operational telemetry."""
        ...

    @operation
    def get_stats(self) -> CacheStats:
        """Produces current operational telemetry statistics."""
        ...

    @operation
    def reset_stats(self) -> None:
        """Resets operational telemetry counters to zero."""
        ...

    @operation
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        """Produces active cache keys ordered from least-recently-used to most-recently-used."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:17:50Z
# LAST_CHANGED: 2026-11-09T22:17:50Z
# CHANGE: Initial implementation of LRUCache protocol, CacheStats, and cache exceptions
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
from __future__ import annotations

from collections import OrderedDict
from typing import Any, List, Optional, Tuple
from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import lru_cache


@singleton_type("system")
class LRUCache(lru_cache.LRUCache):
    """Concrete realization of least-recently-used cache using an ordered dictionary.

    GROUNDING:
    - Maintains _items as collections.OrderedDict mapping string keys to arbitrary values.
    - Tracks _capacity as integer, initializing with default limit 100.
    - Tracks _hits, _misses, and _evictions as integer telemetry counters.
    """

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
        """Maximum number of key-value entries permitted in the cache."""
        return self._capacity

    @property
    @override
    def size(self) -> int:
        """Current count of active key-value entries in the cache."""
        return len(self._items)

    @property
    @override
    def is_empty(self) -> bool:
        """Indicates whether the cache currently contains zero entries."""
        return len(self._items) == 0

    @property
    @override
    def is_full(self) -> bool:
        """Indicates whether the cache has reached its maximum capacity limit."""
        return len(self._items) >= self._capacity

    @operation
    @override
    def configure(self, capacity: int) -> None:
        """Configures the maximum capacity limit of the cache."""
        # WHEN capacity is less than or equal to zero, MUST raise CacheCapacityError
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(f"Cache capacity must be positive, got {capacity}")
        # MUST update the cache capacity limit to the specified value
        self._capacity = capacity
        # WHEN new capacity is smaller than current size, MUST evict least-recently-used entries
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used."""
        # WHEN key is present in cache, MUST return the associated value and promote key
        if key in self._items:
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return self._items[key]
        # WHEN key is absent from cache, MUST return default value
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used."""
        # WHEN key already exists in cache, MUST update its stored value and promote key
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # WHEN key is new and size is at capacity, MUST evict least-recently-used entry
        if len(self._items) >= self._capacity:
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return (evicted_key, evicted_value)
        # WHEN key is new and size is below capacity, MUST store entry
        self._items[key] = value
        return None

    @operation
    @override
    def peek(self, key: str, default: Optional[Any] = None) -> Any:
        """Inspects a cached value without altering access recency or telemetry."""
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        """Removes a key-value entry from the cache."""
        # WHEN key is absent from cache, MUST raise CacheKeyNotFoundError
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(f"Key '{key}' not found in cache")
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        """Removes all entries from the cache while preserving operational telemetry."""
        self._items.clear()

    @operation
    @override
    def get_stats(self) -> lru_cache.CacheStats:
        """Produces current operational telemetry statistics."""
        return lru_cache.CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    @operation
    @override
    def reset_stats(self) -> None:
        """Resets operational telemetry counters to zero."""
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @operation
    @override
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        """Produces active cache keys ordered from least-recently-used to most-recently-used."""
        return list(self._items.keys())


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LRUCache,
        keys=[LRUCache, lru_cache.LRUCache],
        tier=LRUCache.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:20:47Z
# LAST_CHANGED: 2026-11-09T22:17:57Z
# CHANGE: Initial implementation of LRUCache with OrderedDict backing storage, LRU eviction, and operational telemetry
# COVERAGE_AUDIT: 2026-11-09T22:19:36Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:20:47Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:20:22Z
# QA_AUDIT: 2026-11-09T22:19:10Z
# --- END AUTOFAB METADATA ---
