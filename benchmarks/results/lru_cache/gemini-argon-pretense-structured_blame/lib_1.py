# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_212905_gemini-argon_lru_cache_pretense
# Timestamp: 2026-11-13T21:29:05.423358+00:00
# Benchmark Task: lru_cache
# Model: gemini-argon (Tier 4)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 447,045
#   Cached Inbound Tokens:   3,238,999
#   Outbound Tokens:         71,751
#   Total Tokens:            3,757,795
#   Financial Cost ($USD):   $3.2311
#   Wall Clock Duration:     1445.87s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 3, pretense: 5, pretense_coverage: 3, pretense_qa: 3 (Total: 14)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: lru_cache.py ===
"""Low-level interface definitions for bounded least-recently-used cache."""

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
    """Operational telemetry counters for cache access operations."""

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
# LAST_CLEANED: 2026-11-13T21:32:12Z
# LAST_CHANGED: 2026-11-13T21:32:12Z
# CHANGE: Implement LRUCache protocol, CacheStats data type, and cache error hierarchy
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
"""Concrete implementation of bounded least-recently-used cache."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, List, Optional, Tuple
from pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton
from . import lru_cache


@singleton
class LRUCache(lru_cache.LRUCache):
    """Concrete realization of least-recently-used cache using an ordered dictionary."""

    tier = "system"

    def __init__(self) -> None:
        """Initializes the ordered dictionary backing store, default capacity, and telemetry counters."""
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
        """Configures the maximum capacity limit of the cache and evicts excess oldest entries."""
        # Reject non-positive capacity values.
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(f"Capacity must be positive, got {capacity}")
        self._capacity = capacity
        # Evict least-recently-used entries until current size is within the new capacity limit.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used."""
        # When key is present, promote to most-recently-used and record a hit.
        if key in self._items:
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return self._items[key]
        # When key is absent, record a miss and return the fallback value.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used."""
        # Update existing entry in place and promote to most-recently-used without eviction.
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # Evict the oldest entry when inserting a new key at capacity.
        evicted: Optional[Tuple[str, Any]] = None
        if len(self._items) >= self._capacity:
            evicted = self._items.popitem(last=False)
            self._evictions += 1
        # Store the new entry at the most-recently-used position.
        self._items[key] = value
        return evicted

    @operation
    @override
    def peek(self, key: str, default: Optional[Any] = None) -> Any:
        """Inspects a cached value without altering access recency or telemetry."""
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        """Removes a key-value entry from the cache and returns its value."""
        # Enforce that the target key exists before removal.
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(f"Key not found in cache: {key}")
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T21:53:09Z
# LAST_CHANGED: 2026-11-13T21:32:16Z
# CHANGE: Implement concrete LRUCache singleton backed by OrderedDict with capacity eviction and telemetry
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T21:53:09Z
# PRETENSE_QA_AUDIT: 2026-11-13T21:52:36Z
# --- END AUTOFAB METADATA ---
