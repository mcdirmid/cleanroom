# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_034922_gemini-flash_lru_cache_combined
# Timestamp: 2026-11-12T03:49:22.132165+00:00
# Benchmark Task: lru_cache
# Model: gemini-flash (Tier 2)
# Methodology: combined
# Harness: antigravity
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 2,310,207
#   Cached Inbound Tokens:   56,330,858
#   Outbound Tokens:         430,691
#   Total Tokens:            59,071,756
#   Financial Cost ($USD):   $1.8116
#   Wall Clock Duration:     2048.87s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 1, lib: 5, pretense: 5, pretense_coverage: 1, pretense_qa: 3, qa: 2, test: 3 (Total: 20)
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
# LAST_CLEANED: 2026-11-12T04:18:12Z
# LAST_CHANGED: 2026-11-12T04:14:01Z
# CHANGE: Implement LRUCache protocol, CacheError hierarchy, and CacheStats
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
from __future__ import annotations

from collections import OrderedDict
from typing import Any, List, Optional, Tuple

from . import lru_cache
from support.lib.lifecycle import singleton


@singleton
class LRUCache(lru_cache.LRUCache):
    """Concrete realization of least-recently-used cache using an ordered dictionary."""

    tier = "system"

    def __init__(self) -> None:
        self._items: OrderedDict[str, Any] = OrderedDict()
        self._capacity: int = 100
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def size(self) -> int:
        return len(self._items)

    @property
    def is_empty(self) -> bool:
        return len(self._items) == 0

    @property
    def is_full(self) -> bool:
        return len(self._items) >= self._capacity

    def configure(self, capacity: int) -> None:
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(f"Capacity must be positive, got {capacity}")
        self._capacity = capacity
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        if key in self._items:
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return self._items[key]
        self._misses += 1
        return default

    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        if len(self._items) >= self._capacity:
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return (evicted_key, evicted_value)
        self._items[key] = value
        return None

    def peek(self, key: str, default: Optional[Any] = None) -> Any:
        return self._items.get(key, default)

    def remove(self, key: str) -> Any:
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(f"Key '{key}' not found in cache")
        return self._items.pop(key)

    def clear(self) -> None:
        self._items.clear()

    def get_stats(self) -> lru_cache.CacheStats:
        return lru_cache.CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    def reset_stats(self) -> None:
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def keys_in_lru_order(self) -> List[str]:
        return list(self._items.keys())

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T04:23:29Z
# LAST_CHANGED: 2026-11-12T04:22:32Z
# CHANGE: Change import of lru_cache to relative sibling import 'from . import lru_cache' so exceptions resolve to canonical interface types
# COVERAGE_AUDIT: 2026-11-12T04:23:26Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T04:23:29Z
# PRETENSE_QA_AUDIT: 2026-11-12T04:23:03Z
# QA_AUDIT: 2026-11-12T04:23:02Z
# --- END AUTOFAB METADATA ---
