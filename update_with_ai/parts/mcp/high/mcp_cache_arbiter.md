# mcp_cache_arbiter interface component

imports: mcp_session

## Purpose

The mcp_cache_arbiter interface component defines cache eviction window accounting, idle session monitoring, and sampling routing actions for ready dirty nodes.

Holding tool calls open while waiting for upstream dependencies causes client-side safety timeouts in desktop agent harnesses, while waking idle agents after cache expiration incurs full transcript re-reading costs. Without cache-aware task routing, idle workers either trigger timeout deadlocks or suffer expensive cold restarts. The mcp_cache_arbiter interface component establishes a system service that tracks sub-agent idle durations against the server-side cache eviction window, producing routing actions that resume warm-cache workers via sampling or recycle stale workers through the coordinator.

**Out of scope:** The mcp_cache_arbiter interface component does not send network packets, execute compiler checks, or maintain file edit buffers; these are handled by other components.

## Types and Behavior

A *cache routing action* is a decision governing how an idle sub-agent should be engaged when work becomes ready.

A *warm cache wakeup* is a cache routing action indicating that the sub-agent cache remains warm. It provides the target conversation identifier, role address, and a *wakeup prompt* directing the sub-agent to retrieve tasks.

A *cold cache recycle* is a cache routing action indicating that the sub-agent cache has expired. It provides the target conversation identifier, role address, unit root, and a *recycle prompt* instructing the parent coordinator to terminate the stale sub-agent and spawn a fresh instance.

A *no routing action* is a cache routing action indicating that no work is ready or that no routing transition is warranted.

The *cache arbiter* is a system service that monitors idle sub-agent sessions and determines cache-aware routing actions.

The cache arbiter:

- Can *evaluate session readiness* for a conversation identifier, producing a cache routing action.

- Can *evaluate all idle sessions*, producing a sequence of cache routing actions for sessions with ready work.
