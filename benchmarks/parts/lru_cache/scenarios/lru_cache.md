# Concrete scenarios for lru_cache interface

## Scenario 1 — Basic insertion and lookup with hit and miss telemetry

Given: A newly initialized least-recently-used cache configured with capacity 3.

1. Put key `alpha` with value `100` and key `beta` with value `200`.
Observed: Cache size is 2, and no entries were evicted.

2. Get key `alpha`.
Observed: Value `100` is returned, and cache stats report 1 hit and 0 misses.

3. Get non-existent key `gamma` with default `999`.
Observed: Default value `999` is returned, and cache stats report 1 hit and 1 miss.

## Scenario 2 — Capacity overflow eviction of least-recently-used entry

Given: A newly initialized least-recently-used cache configured with capacity 2.

1. Put key `k1` with `v1` and key `k2` with `v2`.
Observed: Cache is full with size 2.

2. Get key `k1`.
Observed: Key `k1` is promoted to most-recently-used, leaving `k2` as the least-recently-used entry.

3. Put key `k3` with `v3`.
Observed: Key `k2` is evicted, the evicted pair `("k2", "v2")` is returned, and cache stats report 1 eviction.

4. Get key `k2` with default `None`.
Observed: Default `None` is returned because `k2` was evicted.

## Scenario 3 — Updating existing key without eviction

Given: A newly initialized least-recently-used cache configured with capacity 2.

1. Put key `k1` with `v1` and key `k2` with `v2`.
Observed: Cache is full with size 2.

2. Put key `k1` with updated value `v1_updated`.
Observed: Value for `k1` is updated, no eviction occurs, and cache size remains 2.

3. Put key `k3` with `v3`.
Observed: Key `k2` is evicted because `k1` was recently updated.

## Scenario 4 — Peeking without access recency promotion

Given: A newly initialized least-recently-used cache configured with capacity 2.

1. Put key `k1` with `v1` and key `k2` with `v2`.
Observed: `k1` is the least-recently-used entry.

2. Peek key `k1`.
Observed: Value `v1` is returned without changing access order; telemetry hits remain 0.

3. Put key `k3` with `v3`.
Observed: Key `k1` is evicted because peek did not promote it.

## Scenario 5 — Removing entry and handling missing keys

Given: A newly initialized least-recently-used cache configured with capacity 3 containing `k1` with `v1`.

1. Remove key `k1`.
Observed: Value `v1` is returned, and cache becomes empty with size 0.

2. Remove key `k1` again.
Observed: A cache key not found error is raised.

## Scenario 6 — Dynamic capacity configuration and downsizing eviction

Given: A newly initialized least-recently-used cache with capacity 4 containing `a`, `b`, `c`, `d` in insertion order.

1. Configure capacity to 2.
Observed: Capacity is updated to 2, entries `a` and `b` are evicted in sequence, and cache stats report 2 evictions.

2. Configure capacity to 0 or -1.
Observed: A cache capacity error is raised.

## Scenario 7 — Clearing entries and resetting telemetry

Given: A newly initialized least-recently-used cache containing 2 entries with recorded hits, misses, and evictions.

1. Clear cache.
Observed: Cache size becomes 0, and emptiness evaluates to True, while stats are retained.

2. Reset stats.
Observed: Cache stats report 0 hits, 0 misses, and 0 evictions.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T18:30:00Z
LAST_CHANGED: 2026-10-30T18:30:00Z
CHANGE: Author lru_cache interface concrete scenarios
-->
