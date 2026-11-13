# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_040947_gemini-flash_lru_cache_pretense
# Timestamp: 2026-11-13T04:09:47.557619+00:00
# Benchmark Task: lru_cache
# Model: gemini-flash (Tier 2)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 439,519
#   Cached Inbound Tokens:   2,578,918
#   Outbound Tokens:         86,614
#   Total Tokens:            3,105,051
#   Financial Cost ($USD):   $0.1431
#   Wall Clock Duration:     602.11s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 1, pretense: 1, pretense_coverage: 1, pretense_qa: 1 (Total: 4)
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

    def __str__(self) -> str:
        return f"CacheStats(hits={self.hits}, misses={self.misses}, evictions={self.evictions})"


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
# LAST_CLEANED: 2026-11-13T04:14:19Z
# LAST_CHANGED: 2026-11-13T04:14:19Z
# CHANGE: Initial implementation of LRUCache interface protocol and data types
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
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
        if capacity <= 0:
            raise lru_cache.CacheCapacityError("Capacity must be positive.")
        self._capacity = capacity
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used."""
        if key in self._items:
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return self._items[key]
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used."""
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

    @operation
    @override
    def peek(self, key: str, default: Optional[Any] = None) -> Any:
        """Inspects a cached value without altering access recency or telemetry."""
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        """Removes a key-value entry from the cache."""
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(f"Key '{key}' not found in cache.")
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
# LAST_CLEANED: 2026-11-13T04:19:44Z
# LAST_CHANGED: 2026-11-13T04:14:34Z
# CHANGE: Initial concrete realization of LRUCache using OrderedDict with recency promotion, eviction, and telemetry
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T04:19:44Z
# PRETENSE_QA_AUDIT: 2026-11-13T04:19:05Z
# --- END AUTOFAB METADATA ---
