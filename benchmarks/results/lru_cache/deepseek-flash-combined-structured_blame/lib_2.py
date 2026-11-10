# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_220402_deepseek-flash_lru_cache_combined
# Timestamp: 2026-11-09T22:04:02.283440+00:00
# Benchmark Task: lru_cache
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 103,369
#   Cached Inbound Tokens:   2,588,672
#   Outbound Tokens:         83,201
#   Total Tokens:            2,775,242
#   Financial Cost ($USD):   $0.0732
#   Wall Clock Duration:     443.32s
#   Step Latencies (s):      [125.0, 137.6, 10.1, 20.3, 374.5, 20.3, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, pretense: 1, pretense_coverage: 1, pretense_qa: 1, qa: 1, test: 1 (Total: 7)
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
"""Low-level interface specification for bounded least-recently-used cache."""

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
# LAST_CLEANED: 2026-11-09T22:06:30Z
# LAST_CHANGED: 2026-11-09T22:06:30Z
# CHANGE: Implemented LRUCache interface: data_type-decorated CacheError hierarchy and CacheStats record, poly_type Protocol with all operations and test_only keys_in_lru_order; fixed pretense import to package-qualified path.
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
"""Low-level implementation of bounded least-recently-used cache."""

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
        # GROUNDING: returns the internal capacity limit.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        """Current count of active key-value entries in the cache."""
        # GROUNDING: returns length of the internal mapping.
        return len(self._items)

    @property
    @override
    def is_empty(self) -> bool:
        """Indicates whether the cache currently contains zero entries."""
        # GROUNDING: the cache is empty when the internal mapping has no entries.
        return len(self._items) == 0

    @property
    @override
    def is_full(self) -> bool:
        """Indicates whether the cache has reached its maximum capacity limit."""
        # GROUNDING: the cache is full once the mapping length reaches the limit.
        return len(self._items) >= self._capacity

    @operation
    @override
    def configure(self, capacity: int) -> None:
        """Configures the maximum capacity limit of the cache."""
        # A non-positive capacity is a contracted violation and must raise.
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(
                f"capacity must be greater than zero, got {capacity}"
            )
        # Adopt the new limit.
        self._capacity = capacity
        # Evict least recently used entries until the size fits the new limit.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any]) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used."""
        # A hit is promoted to the most recently used position and counted.
        if key in self._items:
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return self._items[key]
        # A miss returns the default without altering access order.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used."""
        # An existing key is updated in place and promoted without changing size.
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        # A new key at capacity evicts the least recently used entry and reports it.
        if len(self._items) >= self._capacity:
            evicted = self._items.popitem(last=False)
            self._evictions += 1
            self._items[key] = value
            return evicted
        # A new key below capacity is stored at the most recently used position.
        self._items[key] = value
        return None

    @operation
    @override
    def peek(self, key: str, default: Optional[Any]) -> Any:
        """Inspects a cached value without altering access recency or telemetry."""
        # Read the mapping without reordering entries or touching counters.
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        """Removes a key-value entry from the cache."""
        # An absent key is a contracted violation and must raise.
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(f"key not found in cache: {key}")
        # The removed value is returned and the entry count shrinks accordingly.
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        """Removes all entries from the cache while preserving operational telemetry."""
        # Drop every entry while leaving the telemetry counters untouched.
        self._items.clear()

    @operation
    @override
    def get_stats(self) -> lru_cache.CacheStats:
        """Produces current operational telemetry statistics."""
        # Report the cumulative telemetry counters.
        return lru_cache.CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
        )

    @operation
    @override
    def reset_stats(self) -> None:
        """Resets operational telemetry counters to zero."""
        # Zero all counters without altering cached entries.
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @operation
    @override
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        """Produces active cache keys ordered from least-recently-used to most-recently-used."""
        # Snapshot the key order in ascending recency without mutating the cache.
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
# LAST_CLEANED: 2026-11-09T22:11:12Z
# LAST_CHANGED: 2026-11-09T22:06:36Z
# CHANGE: Implemented concrete singleton LRUCache backed by OrderedDict<str, Any>: capacity/size/is_empty/is_full properties, configure with CacheCapacityError guard and downsize eviction, get/put with LRU promotion and eviction reporting, non-mutating peek, remove with CacheKeyNotFoundError guard, clear preserving telemetry, stats get/reset, and keys_in_lru_order snapshot.
# COVERAGE_AUDIT: 2026-11-09T22:07:14Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:11:12Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:10:51Z
# QA_AUDIT: 2026-11-09T22:07:00Z
# --- END AUTOFAB METADATA ---
