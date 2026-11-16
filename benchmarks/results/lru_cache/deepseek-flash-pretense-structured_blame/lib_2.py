# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261114_202841_deepseek-flash_lru_cache_pretense
# Timestamp: 2026-11-14T20:28:41.173603+00:00
# Benchmark Task: lru_cache
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 150,828
#   Cached Inbound Tokens:   9,855,232
#   Outbound Tokens:         95,217
#   Total Tokens:            10,101,277
#   Financial Cost ($USD):   $0.1093
#   Wall Clock Duration:     837.28s
#   Step Latencies (s):      [75.7, 561.2, 20.3, 50.8, 61.2, 10.0, 30.5, 30.5, 20.3, 20.3]
#   Role Execution Rounds:   lib: 1, pretense: 3, pretense_coverage: 3, pretense_qa: 3 (Total: 10)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       3
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

    @operation
    @test_only
    def keys_in_lru_order(self) -> List[str]:
        """Produces active cache keys ordered from least-recently-used to most-recently-used.

        Returns:
            List of active cache keys in access recency ascending order.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:29:52Z
# LAST_CHANGED: 2026-11-14T20:29:52Z
# CHANGE: Implement interface module: CacheError/CacheCapacityError/CacheKeyNotFoundError exceptions, frozen CacheStats record, and LRUCache protocol with capacity/size/is_empty/is_full properties plus configure/get/put/peek/remove/clear/get_stats/reset_stats/keys_in_lru_order operations
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl.py ===
"""Concrete realization of bounded least-recently-used cache."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, List, Optional, Tuple

from pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import lru_cache

DEFAULT_CAPACITY = 100


@singleton
class LRUCache(lru_cache.LRUCache):
    """Concrete realization of least-recently-used cache using an ordered dictionary.

    Entries are kept in an ordered mapping whose iteration order runs from the
    least-recently-used key to the most-recently-used key. Access operations promote
    the touched key to the most-recently-used position, while capacity pressure
    evicts from the least-recently-used end.
    """

    tier = "system"

    def __init__(self) -> None:
        # Ordered mapping of keys to values, oldest (least recently used) first.
        self._items: OrderedDict[str, Any] = OrderedDict()
        # Maximum number of entries permitted before eviction begins.
        self._capacity: int = DEFAULT_CAPACITY
        # Accumulated telemetry counters for lookups and evictions.
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
        """Configures the maximum capacity limit of the cache.

        Rejects non-positive limits and shrinks the cache by evicting the
        least-recently-used entries whenever the new limit is below the current size.
        """
        if capacity <= 0:
            raise lru_cache.CacheCapacityError(
                f"cache capacity must be greater than zero, received {capacity}"
            )
        # Apply the new limit before trimming so the sweep observes the target size.
        self._capacity = capacity
        # Discard the oldest entries until the cache fits inside the new limit.
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
            self._evictions += 1

    @operation
    @override
    def get(self, key: str, default: Optional[Any]) -> Any:
        """Retrieves the value associated with key, promoting it to most-recently-used."""
        if key in self._items:
            # Promotion keeps the touched entry at the newest end of the ordering.
            self._items.move_to_end(key, last=True)
            self._hits += 1
            return self._items[key]
        # A miss leaves the recency ordering untouched.
        self._misses += 1
        return default

    @operation
    @override
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Inserts or updates a key-value entry, promoting it to most-recently-used."""
        if key in self._items:
            # Existing keys refresh their value and move to the newest position.
            self._items[key] = value
            self._items.move_to_end(key, last=True)
            return None
        evicted: Optional[Tuple[str, Any]] = None
        if len(self._items) >= self._capacity:
            # Capacity pressure removes the oldest entry ahead of the insertion.
            evicted_key, evicted_value = self._items.popitem(last=False)
            self._evictions += 1
            evicted = (evicted_key, evicted_value)
        self._items[key] = value
        return evicted

    @operation
    @override
    def peek(self, key: str, default: Optional[Any]) -> Any:
        """Inspects a cached value without altering access recency or telemetry."""
        # Direct lookup avoids both reordering and counter updates.
        return self._items.get(key, default)

    @operation
    @override
    def remove(self, key: str) -> Any:
        """Removes a key-value entry from the cache."""
        if key not in self._items:
            raise lru_cache.CacheKeyNotFoundError(
                f"cache key not found: {key!r}"
            )
        return self._items.pop(key)

    @operation
    @override
    def clear(self) -> None:
        """Removes all entries from the cache while preserving operational telemetry."""
        # Only the entries are dropped; accumulated counters survive the clear.
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
        # Ordering follows the internal mapping without disturbing recency state.
        return list(self._items.keys())

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:42:26Z
# LAST_CHANGED: 2026-11-14T20:29:57Z
# CHANGE: Implement LRUCache singleton over OrderedDict: default capacity 100 with telemetry counters, recency promotion on get/put, LRU eviction on capacity pressure, capacity guard raising CacheCapacityError, remove guard raising CacheKeyNotFoundError, clear preserving telemetry, and keys_in_lru_order query
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T20:42:26Z
# PRETENSE_QA_AUDIT: 2026-11-14T20:42:03Z
# --- END AUTOFAB METADATA ---
