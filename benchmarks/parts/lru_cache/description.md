# lru_cache

The `lru_cache` component realizes a lightweight, high-performance Least-Recently-Used (LRU) memory cache with dynamic capacity resizing, access recency promotion, overflow eviction, and hit/miss/eviction telemetry.

## Capabilities

- **Recency Management & Access Promotion**: Tracks key access recency across reads (`get`) and writes (`put`), promoting accessed items to the most-recently-used position.
- **Capacity Bounds & Overflow Eviction**: Enforces maximum cache capacity, automatically evicting the least-recently-used entry when inserting beyond capacity or downsizing capacity.
- **Non-Mutating Inspection**: Supports inspecting cached values (`peek`) without disturbing the access order or mutating telemetry.
- **Operational Telemetry**: Maintains counters for cache hits, misses, and evictions, supporting runtime reporting and telemetry resets.
