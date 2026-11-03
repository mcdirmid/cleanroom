# Concrete scenarios for lru_cache_impl implementation

## Reused from the interface

### Scenario 1 — Basic insertion and lookup with hit and miss telemetry

Given: A newly initialized least-recently-used cache configured with capacity 3.

1. Put key `alpha` with value `100` and key `beta` with value `200`.
Observed: Cache size is 2, and no entries were evicted.
Realized by: Inserting keys into the internal ordered dictionary without reaching capacity limit.

2. Get key `alpha`.
Observed: Value `100` is returned, and cache stats report 1 hit and 0 misses.
Realized by: Moving `alpha` to the end of the ordered mapping and incrementing the hit counter.

3. Get non-existent key `gamma` with default `999`.
Observed: Default value `999` is returned, and cache stats report 1 hit and 1 miss.
Realized by: Returning the caller default value and incrementing the miss counter.

### Scenario 2 — Capacity overflow eviction of least-recently-used entry

Given: A newly initialized least-recently-used cache configured with capacity 2.

1. Put key `k1` with `v1` and key `k2` with `v2`.
Observed: Cache is full with size 2.
Realized by: Storing two entries in the ordered dictionary.

2. Get key `k1`.
Observed: Key `k1` is promoted to most-recently-used, leaving `k2` as the least-recently-used entry.
Realized by: Moving `k1` to the end of the ordered dictionary via move_to_end.

3. Put key `k3` with `v3`.
Observed: Key `k2` is evicted, the evicted pair `("k2", "v2")` is returned, and cache stats report 1 eviction.
Realized by: Popping the first item from the ordered dictionary, incrementing evictions, and inserting `k3`.

4. Get key `k2` with default `None`.
Observed: Default `None` is returned because `k2` was evicted.
Realized by: Looking up `k2` in the ordered dictionary which fails and triggers a miss.

### Scenario 3 — Updating existing key without eviction

Given: A newly initialized least-recently-used cache configured with capacity 2.

1. Put key `k1` with `v1` and key `k2` with `v2`.
Observed: Cache is full with size 2.
Realized by: Inserting two initial key-value pairs.

2. Put key `k1` with updated value `v1_updated`.
Observed: Value for `k1` is updated, no eviction occurs, and cache size remains 2.
Realized by: Updating `k1` in place and moving it to the end without calling popitem.

3. Put key `k3` with `v3`.
Observed: Key `k2` is evicted because `k1` was recently updated.
Realized by: Popping the oldest item `k2` from the beginning of the dictionary.

### Scenario 4 — Peeking without access recency promotion

Given: A newly initialized least-recently-used cache configured with capacity 2.

1. Put key `k1` with `v1` and key `k2` with `v2`.
Observed: `k1` is the least-recently-used entry.
Realized by: Populating the dictionary in order `k1`, `k2`.

2. Peek key `k1`.
Observed: Value `v1` is returned without changing access order; telemetry hits remain 0.
Realized by: Direct dictionary get without reordering or counter mutation.

3. Put key `k3` with `v3`.
Observed: Key `k1` is evicted because peek did not promote it.
Realized by: Popping the first item `k1`.

### Scenario 5 — Removing entry and handling missing keys

Given: A newly initialized least-recently-used cache configured with capacity 3 containing `k1` with `v1`.

1. Remove key `k1`.
Observed: Value `v1` is returned, and cache becomes empty with size 0.
Realized by: Deleting `k1` from the ordered dictionary.

2. Remove key `k1` again.
Observed: A cache key not found error is raised.
Realized by: Enforcing precondition requires(key in self._items, lru_cache.CacheKeyNotFoundError) and popping key from the ordered dictionary.

### Scenario 6 — Dynamic capacity configuration and downsizing eviction

Given: A newly initialized least-recently-used cache with capacity 4 containing `a`, `b`, `c`, `d` in insertion order.

1. Configure capacity to 2.
Observed: Capacity is updated to 2, entries `a` and `b` are evicted in sequence, and cache stats report 2 evictions.
Realized by: Updating the capacity property and looping to pop oldest entries until length equals 2.

2. Configure capacity to 0 or -1.
Observed: A cache capacity error is raised.
Realized by: Enforcing precondition requires(capacity > 0, lru_cache.CacheCapacityError).

### Scenario 7 — Clearing entries and resetting telemetry

Given: A newly initialized least-recently-used cache containing 2 entries with recorded hits, misses, and evictions.

1. Clear cache.
Observed: Cache size becomes 0, and emptiness evaluates to True, while stats are retained.
Realized by: Calling clear on the internal ordered dictionary.

2. Reset stats.
Observed: Cache stats report 0 hits, 0 misses, and 0 evictions.
Realized by: Resetting integer counters to zero.

## Implementation-only

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T18:30:00Z
LAST_CHANGED: 2026-10-30T18:30:00Z
CHANGE: Author lru_cache_impl implementation concrete scenarios
-->
