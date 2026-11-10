# lru_cache interface component

## Purpose

The lru_cache interface component defines abstract memory cache models, access recency promotion rules, overflow eviction policies, and operational hit/miss telemetry for bounded key-value caches.

Applications require bounded in-memory caching to eliminate redundant computations and buffer frequently accessed items without unbounded memory growth. Without disciplined recency tracking and deterministic eviction policies, caches suffer from memory leaks, stale entries, or unpredictable eviction order. The lru_cache interface component provides canonical data representations and protocols for key-value storage, dynamic capacity enforcement, access recency promotion, and telemetry tracking to ensure deterministic and bounded memory management.

**Out of scope:** The lru_cache interface component does not serialize cache records to persistent disk storage, manage distributed cache clusters over network protocols, or enforce wall-clock expiration (TTL) schedules; these are handled by other components.

## Types and Behavior

A *cache error* specializes specification error as the base error for cache operations. Operational failures are categorized into:

- A *cache capacity error* specializing cache error with zero arguments, signaling that an invalid non-positive capacity limit was specified.

- A *cache key not found error* specializing cache error with zero arguments, signaling that an operation was attempted on a non-existent key.

A *cache stats* record encapsulates operational cache telemetry, carrying integer counts for *hits*, *misses*, and *evictions*.

A *least-recently-used cache* stores bounded key-value pairs with access recency tracking. Cache operations provide:

- Retrieving cached values by key, returning the associated value, promoting the accessed key to the most-recently-used position, and incrementing the cache hit counter when the key exists, or returning a default value and incrementing the cache miss counter without altering access order when the key is absent.

- Inserting or updating key-value pairs, promoting the key to the most-recently-used position. Updating an existing key modifies its value without changing total cache size or triggering eviction. Inserting a new key into a cache currently at maximum capacity evicts the least-recently-used key-value pair, increments the eviction counter, and returns the evicted key-value pair, while inserting into a cache below capacity increases cache size without eviction.

- Peeking at cached values by key, inspecting and returning the stored value or a default value when absent without modifying access recency order or incrementing hit or miss counters.

- Removing cached entries by key, deleting the entry, decrementing cache size, and returning the removed value, raising cache key not found error when the key is absent.

- Configuring maximum capacity, updating the cache limit, raising cache capacity error when the specified capacity is non-positive, and eagerly evicting least-recently-used entries in sequence until cache size satisfies the new capacity limit when downsizing.

- Clearing all stored key-value pairs, resetting cache size to zero while preserving operational telemetry counters.

- Reporting current capacity, active size, emptiness status, fullness status, and telemetry statistics, as well as resetting operational telemetry counters.

<!-- AUTOFAB METADATA
LAST_CLEANED: 2026-11-10T07:51:09Z
LAST_CHANGED: 2026-10-30T18:30:00Z
CHANGE: Author lru_cache interface component specification
SPEC_QA_AUDIT: 2026-11-10T07:51:09Z
-->
