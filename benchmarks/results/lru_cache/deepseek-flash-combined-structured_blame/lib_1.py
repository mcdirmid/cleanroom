# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_174158_deepseek-flash_lru_cache_combined
# Timestamp: 2026-11-08T17:41:58.899115+00:00
# Benchmark Task: lru_cache
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 156,244
#   Cached Inbound Tokens:   4,851,328
#   Outbound Tokens:         127,972
#   Total Tokens:            5,135,544
#   Financial Cost ($USD):   $0.1148
#   Wall Clock Duration:     684.00s
#   Step Latencies (s):      [127.1, 186.2, 10.0, 10.0, 333.8, 20.3, 53.1, 237.1, 20.3, 10.1]
#   Role Execution Rounds:   coverage: 1, lib: 1, pretense: 2, pretense_coverage: 2, pretense_qa: 2, qa: 1, test: 1 (Total: 10)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       21
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: lru_cache.py ===
"""Library interface for bounded least-recently-used cache."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Protocol, Tuple
from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only

# Requirements specified in lru_cache.pyi


class CacheError(PretenseSpecificationError):
    """Base exception for all cache operational errors."""

    pass


class CacheCapacityError(CacheError):
    """Raised when an invalid non-positive capacity limit is specified."""

    pass


class CacheKeyNotFoundError(CacheError):
    """Raised when attempting to remove or access a non-existent cache key."""

    pass


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

    def configure(self, capacity: int) -> None:
        """Configures the maximum capacity limit of the cache."""
        ...

    def get(self, key: str, default: Optional[Any]) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used."""
        ...

    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used."""
        ...

    def peek(self, key: str, default: Optional[Any]) -> Any:
        """Inspects a cached value without altering access recency or telemetry."""
        ...

    def remove(self, key: str) -> Any:
        """Removes a key-value entry from the cache."""
        ...

    def clear(self) -> None:
        """Removes all entries from the cache while preserving operational telemetry."""
        ...

    def get_stats(self) -> CacheStats:
        """Produces current operational telemetry statistics."""
        ...

    def reset_stats(self) -> None:
        """Resets operational telemetry counters to zero."""
        ...

    @test_only
    def keys_in_lru_order(self) -> List[str]:
        """Produces active cache keys ordered from least-recently-used to most-recently-used."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:44:18Z
# LAST_CHANGED: 2026-11-08T17:44:18Z
# CHANGE: Implement library interface for LRU cache: CacheError hierarchy, frozen CacheStats telemetry record, and LRUCache Protocol with capacity/size/is_empty/is_full properties plus configure/get/put/peek/remove/clear/get_stats/reset_stats/keys_in_lru_order operations per low/lru_cache.pyi; use package-qualified pretense import.
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
"""Library implementation for bounded least-recently-used cache."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, List, Optional, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import lru_cache
from pretense.parts.pretense.lib.pretense import test_only

# Requirements specified in lru_cache_impl.pyi


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
        # OrderedDict keeps least-recently-used entries at the front and
        # most-recently-used entries at the back.
        self._items: "OrderedDict[str, Any]" = OrderedDict()
        # Default capacity limit from the grounding constraints.
        self._capacity: int = 100
        # Cumulative operational telemetry counters.
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    @property
    @override
    def capacity(self) -> int:
        # Expose the configured capacity limit.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # Number of currently cached entries.
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
        # A non-positive limit is a contracted error.
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(
                f"cache capacity must be positive, got {capacity}"
            )
        # Adopt the new limit.
        self._capacity = capacity
        # Shrink the cache from the least-recently-used end until it fits.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any]) -> Any:
        # Present key: return the value, record a hit, and promote recency.
        if key in self._items:
            value = self._items[key]
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return value
        # Absent key: record a miss and leave access order untouched.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        # Existing key: overwrite in place, promote recency, no eviction.
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # New key at capacity: evict the least-recently-used entry first.
        if len(self._items) >= self._capacity:
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return (evicted_key, evicted_value)
        # New key below capacity: insert at the most-recently-used end.
        self._items[key] = value
        return None

    @operation
    @override
    def peek(self, key: str, default: Optional[Any]) -> Any:
        # Read without reordering entries or touching telemetry counters.
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        # Removing an absent key is a contracted error.
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(
                f"cache key not found: {key!r}"
            )
        # Drop the entry and hand back its former value.
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        # Drop entries only, keeping hits, misses, and evictions intact.
        self._items.clear()

    @operation
    @override
    def get_stats(self) -> lru_cache.CacheStats:
        # Snapshot the cumulative telemetry counters.
        return lru_cache.CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    @operation
    @override
    def reset_stats(self) -> None:
        # Zero the telemetry counters without disturbing cached entries.
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @operation
    @override
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        # Active keys from least-recently-used to most-recently-used.
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
# LAST_CLEANED: 2026-11-08T17:53:19Z
# LAST_CHANGED: 2026-11-08T17:44:24Z
# CHANGE: Implement concrete @singleton_type LRUCache backed by collections.OrderedDict with capacity 100 default, recency promotion, LRU eviction on put/configure-downsize with eviction telemetry, hit/miss counters, contracted CacheCapacityError/CacheKeyNotFoundError, telemetry-preserving clear, and non-mutating @test_only keys_in_lru_order.
# COVERAGE_AUDIT: 2026-11-08T17:46:00Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:53:19Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:52:56Z
# QA_AUDIT: 2026-11-08T17:45:46Z
# --- END AUTOFAB METADATA ---
