# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_165923_deepseek-flash_lru_cache_combined
# Timestamp: 2026-11-10T16:59:23.522551+00:00
# Benchmark Task: lru_cache
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 106,950
#   Cached Inbound Tokens:   2,016,640
#   Outbound Tokens:         88,654
#   Total Tokens:            2,212,244
#   Financial Cost ($USD):   $0.0753
#   Wall Clock Duration:     402.07s
#   Step Latencies (s):      [96.9, 135.3, 10.1, 20.3, 331.4, 20.2, 10.0]
#   Role Execution Rounds:   coverage: 1, lib: 1, pretense: 1, pretense_coverage: 1, pretense_qa: 1, qa: 1, test: 1 (Total: 7)
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
"""Interface specification for bounded least-recently-used cache."""

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

        PRECONDITIONS:
        - WHEN capacity is less than or equal to zero, MUST raise CacheCapacityError.

        POSTCONDITIONS:
        - MUST update the cache capacity limit to the specified value.
        - WHEN new capacity is smaller than current size, MUST evict least-recently-used entries in sequence until size equals capacity, incrementing the evictions counter for each evicted entry.
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

        POSTCONDITIONS:
        - WHEN key is present in cache, MUST return the associated value, promote key to most-recently-used position, and increment hits counter.
        - WHEN key is absent from cache, MUST return default value and increment misses counter without altering access order.
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

        POSTCONDITIONS:
        - WHEN key already exists in cache, MUST update its stored value, promote key to most-recently-used position without increasing size, and return None.
        - WHEN key is new and size is at capacity, MUST evict the least-recently-used entry, increment evictions counter, store the new entry at the most-recently-used position, and return tuple of (evicted_key, evicted_value).
        - WHEN key is new and size is below capacity, MUST store entry at most-recently-used position, increment size by 1, and return None.
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

        POSTCONDITIONS:
        - WHEN key is present in cache, MUST return the associated value without modifying access recency order or incrementing telemetry counters.
        - WHEN key is absent from cache, MUST return default value without modifying access recency order or incrementing telemetry counters.
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

        PRECONDITIONS:
        - WHEN key is absent from cache, MUST raise CacheKeyNotFoundError.

        POSTCONDITIONS:
        - WHEN key exists in cache, MUST remove entry, decrement size by 1, and return removed value.
        """
        ...

    @operation
    def clear(self) -> None:
        """Removes all entries from the cache while preserving operational telemetry.

        POSTCONDITIONS:
        - MUST remove all key-value entries from the cache and reset size to zero.
        - MUST preserve telemetry counters across clear operations.
        """
        ...

    @operation
    def get_stats(self) -> CacheStats:
        """Produces current operational telemetry statistics.

        Returns:
            Immutable CacheStats record reflecting hits, misses, and evictions.

        POSTCONDITIONS:
        - MUST return CacheStats reflecting cumulative hits, misses, and evictions.
        """
        ...

    @operation
    def reset_stats(self) -> None:
        """Resets operational telemetry counters to zero.

        POSTCONDITIONS:
        - MUST reset hits, misses, and evictions counters to zero without altering cached entries.
        """
        ...

    @operation
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        """Produces active cache keys ordered from least-recently-used to most-recently-used.

        Returns:
            List of active cache keys in access recency ascending order.

        POSTCONDITIONS:
        - MUST return all active cache keys ordered from least-recently-used to most-recently-used.
        - MUST NOT alter access recency order or increment operational telemetry counters.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T17:01:17Z
# LAST_CHANGED: 2026-11-10T17:01:17Z
# CHANGE: Implement interface module: package-qualified pretense import, @data_type error hierarchy and CacheStats dataclass, @poly_type LRUCache Protocol with @operation/@test_only members matching low/lru_cache.pyi.
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
"""Concrete implementation of bounded least-recently-used cache."""

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
        """Initializes empty entry storage at the default capacity with zeroed telemetry."""
        # _items preserves insertion/access recency: least-recently-used first, most-recent last.
        self._items: "OrderedDict[str, Any]" = OrderedDict()
        # Default capacity limit is 100 per the grounding specification.
        self._capacity: int = 100
        # Cumulative telemetry counters.
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
        # WHEN capacity is less than or equal to zero, MUST raise CacheCapacityError.
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(
                f"Cache capacity must be positive, got {capacity}."
            )
        # MUST update the cache capacity limit to the specified value.
        self._capacity = capacity
        # WHEN new capacity is smaller than current size, MUST evict least-recently-used
        # entries in sequence until size equals capacity, counting each eviction.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any]) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used."""
        # WHEN key is present, MUST return the value, promote to most-recently-used,
        # and increment the hits counter.
        if key in self._items:
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return self._items[key]
        # WHEN key is absent, MUST return default and increment misses without reordering.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used."""
        # WHEN key already exists, MUST update the value and promote without growing size.
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # WHEN key is new and the cache is at capacity, MUST evict the
        # least-recently-used entry, count the eviction, and report what was evicted.
        if len(self._items) >= self._capacity:
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return (evicted_key, evicted_value)
        # WHEN key is new and the cache is below capacity, MUST store at the
        # most-recently-used position without evicting anything.
        self._items[key] = value
        return None

    @operation
    @override
    def peek(self, key: str, default: Optional[Any]) -> Any:
        """Inspects a cached value without altering access recency or telemetry."""
        # Returns present value or default, never reordering or counting.
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        """Removes a key-value entry from the cache."""
        # WHEN key is absent, MUST raise CacheKeyNotFoundError.
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(
                f"Cache key not found: {key!r}."
            )
        # WHEN key exists, MUST remove and return the associated value.
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        """Removes all entries from the cache while preserving operational telemetry."""
        # MUST remove all entries; telemetry counters are intentionally preserved.
        self._items.clear()

    @operation
    @override
    def get_stats(self) -> lru_cache.CacheStats:
        """Produces current operational telemetry statistics."""
        # MUST report cumulative hits, misses, and evictions.
        return lru_cache.CacheStats(self._hits, self._misses, self._evictions)

    @operation
    @override
    def reset_stats(self) -> None:
        """Resets operational telemetry counters to zero."""
        # MUST zero all telemetry without altering cached entries.
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @operation
    @override
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        """Produces active cache keys ordered from least-recently-used to most-recently-used."""
        # MUST return a non-mutating shallow list copy in ascending recency order.
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
# LAST_CLEANED: 2026-11-10T17:06:02Z
# LAST_CHANGED: 2026-11-10T17:01:23Z
# CHANGE: Implement concrete LRUCache singleton: OrderedDict backing with default capacity 100, recency promotion on get/put, LRU eviction with eviction telemetry, configure downsize eviction, CacheCapacityError/CacheKeyNotFoundError preconditions, telemetry reporting/reset, and non-mutating keys_in_lru_order.
# COVERAGE_AUDIT: 2026-11-10T17:02:34Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T17:06:02Z
# PRETENSE_QA_AUDIT: 2026-11-10T17:05:41Z
# QA_AUDIT: 2026-11-10T17:02:21Z
# --- END AUTOFAB METADATA ---
