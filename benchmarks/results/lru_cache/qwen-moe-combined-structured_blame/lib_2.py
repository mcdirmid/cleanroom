# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_071146_qwen-moe_lru_cache_combined
# Timestamp: 2026-11-09T07:11:46.626519+00:00
# Benchmark Task: lru_cache
# Model: qwen-moe (Tier 1)
# Methodology: combined
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 597,967
#   Cached Inbound Tokens:   6,725,843
#   Outbound Tokens:         142,238
#   Total Tokens:            7,466,048
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     2219.50s
#   Step Latencies (s):      [219.5, 260.5, 299.1, 124.9, 65.7, 22.6, 32.8, 22.4, 186.0, 153.1, 484.6, 114.9, 20.3, 20.3, 170.5, 186.0, 165.6, 318.9, 124.8, 20.3, 61.2]
#   Role Execution Rounds:   coverage: 2, lib: 3, pretense: 6, pretense_coverage: 2, pretense_qa: 5, qa: 2, test: 1 (Total: 21)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       23
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: lru_cache.py ===
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Protocol, Tuple

from pretense.parts.pretense.lib.pretense import (
    PretenseSpecificationError,
    test_only,
)
from support.lib.framework import data_type, operation, poly_type


# Requirements specified in lru_cache.pyi


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
    def get(self, key: str, default: Optional[Any]) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used."""
        ...

    @operation
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used."""
        ...

    @operation
    def peek(self, key: str, default: Optional[Any]) -> Any:
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
# LAST_CLEANED: 2026-11-09T07:15:41Z
# LAST_CHANGED: 2026-11-09T07:15:41Z
# CHANGE: Implemented interface module for bounded LRU cache. Fixed bare import of 'pretense' to use full package path 'from pretense.parts.pretense.lib.pretense import ...'. Added @data_type decorators to CacheError, CacheCapacityError, CacheKeyNotFoundError, and CacheStats. Added @poly_type decorator to LRUCache Protocol. Added @operation decorators to all protocol methods. Includes CacheStats frozen dataclass with hits/misses/evictions counters and complete LRUCache Protocol with capacity, size, is_empty, is_full properties plus configure, get, put, peek, remove, clear, get_stats, reset_stats, and keys_in_lru_order operations.
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
from __future__ import annotations

from collections import OrderedDict
from typing import Any, List, Optional, Tuple

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import lru_cache


# Requirements specified in lru_cache_impl.pyi


@singleton_type("system")
class LRUCache(lru_cache.LRUCache):
    """Concrete realization of least-recently-used cache using an ordered dictionary.

    Maintains _items as collections.OrderedDict mapping string keys to arbitrary values.
    Tracks _capacity as integer, initializing with default limit 100.
    Tracks _hits, _misses, and _evictions as integer telemetry counters.
    """

    tier = system

    def __init__(self) -> None:
        # GROUNDING: Initialize backing storage and telemetry counters. Default capacity 100.
        self._items: OrderedDict[str, Any] = OrderedDict()
        self._capacity: int = 100
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    @property
    @override
    def capacity(self) -> int:
        # GROUNDING: Returns internal _capacity attribute.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # GROUNDING: Returns length of internal _items mapping.
        return len(self._items)

    @property
    @override
    def is_empty(self) -> bool:
        # GROUNDING: Evaluates whether length of _items equals zero.
        return len(self._items) == 0

    @property
    @override
    def is_full(self) -> bool:
        # GROUNDING: Evaluates whether length of _items is greater than or equal to _capacity.
        return len(self._items) >= self._capacity

    @operation
    @override
    def configure(self, capacity: int) -> None:
        # GROUNDING: Enforces precondition requires(capacity > 0, lru_cache.CacheCapacityError).
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(f"Cache capacity must be positive, got {capacity}")
        # GROUNDING: Sets _capacity to capacity.
        self._capacity = capacity
        # GROUNDING: While length of _items exceeds _capacity, pops oldest entry
        # via popitem(last=False) and increments _evictions.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any]) -> Any:
        # GROUNDING: If key exists in _items, moves key to end via move_to_end(key, last=True),
        # increments _hits, and returns value.
        if key in self._items:
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return self._items[key]
        # GROUNDING: If key is absent, increments _misses and returns default.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        # GROUNDING: If key exists in _items, updates value, moves to end
        # via move_to_end(key, last=True), and returns None.
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # GROUNDING: If key is new and length of _items >= _capacity,
        # pops oldest entry via popitem(last=False), increments _evictions,
        # stores key and value, and returns popped (evicted_key, evicted_value).
        if len(self._items) >= self._capacity:
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return (evicted_key, evicted_value)
        # GROUNDING: If key is new and length of _items < _capacity,
        # stores key and value in _items and returns None.
        self._items[key] = value
        return None

    @operation
    @override
    def peek(self, key: str, default: Optional[Any]) -> Any:
        # GROUNDING: Delegates directly to _items.get(key, default) without
        # reordering or mutating counters.
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        # GROUNDING: Enforces precondition requires(key in self._items, lru_cache.CacheKeyNotFoundError).
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(f"Key not found in cache: {key}")
        # GROUNDING: Otherwise pops key from _items and returns associated value.
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        # GROUNDING: Calls _items.clear() without resetting telemetry counters.
        self._items.clear()

    @operation
    @override
    def get_stats(self) -> lru_cache.CacheStats:
        # GROUNDING: Returns lru_cache.CacheStats initialized with _hits, _misses, and _evictions.
        return lru_cache.CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    @operation
    @override
    def reset_stats(self) -> None:
        # GROUNDING: Resets _hits, _misses, and _evictions to 0.
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @operation
    @override
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        # GROUNDING: Returns a shallow list copy of keys from self._items.
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
# LAST_CLEANED: 2026-11-09T07:48:28Z
# LAST_CHANGED: 2026-11-09T07:33:41Z
# CHANGE: Resolved unapproved @operation decorator on property methods: removed @operation from capacity, size, is_empty, and is_full properties — matching low/lru_cache_impl.pyi spec which only uses @property + @override on properties. Regular methods retain @operation + @override per spec.
# COVERAGE_AUDIT: 2026-11-09T07:34:33Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T07:48:28Z
# PRETENSE_QA_AUDIT: 2026-11-09T07:47:30Z
# QA_AUDIT: 2026-11-09T07:34:10Z
# --- END AUTOFAB METADATA ---
