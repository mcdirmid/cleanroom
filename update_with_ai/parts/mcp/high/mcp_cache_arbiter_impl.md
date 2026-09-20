# mcp_cache_arbiter_impl implementation component

imports: dag_storage, dag_subgraph, mcp_session
implements: mcp_cache_arbiter

## Purpose

The mcp_cache_arbiter_impl implementation component realizes fifteen-minute eviction window evaluation, DAG readiness detection, and sampling directive generation for idle sessions.

Distinguishing between cost-effective warm-cache resumption and token-wasteful cold-cache waking requires continuous synchronization between graph task readiness and session inactivity timers. Without continuous cache window tracking, orchestrators risk waking stale contexts that trigger costly re-ingestion of full transcripts. The mcp_cache_arbiter_impl implementation component inspects the dependency graph for unblocked dirty nodes belonging to registered roles, measures elapsed time since last activity against a fifteen-minute threshold, and formats specialized sampling prompts for sub-agents and parent coordinators.

**Out of scope:** The mcp_cache_arbiter_impl implementation component does not parse build rules, manage subprocess lifecycles, or serialize JSON-RPC messages; these are handled by other components.

## Types and Behavior

The cache arbiter evaluates idle sessions registered in the role session manager against the graph state in dag storage and dag subgraph.

Evaluating session readiness resolves the role agent session for the conversation identifier. If the session status is not idle or the session is not found, evaluation produces a no routing action. The next ready batch of dirty nodes is obtained from dag subgraph for the session role, producing a no routing action when no dirty nodes are ready for that role.

Inactivity duration is calculated by subtracting the session last active timestamp from the current system timestamp.

When ready dirty nodes exist for the session role:

- An elapsed duration less than or equal to nine hundred seconds produces a warm cache wakeup carrying a prompt directing the sub-agent to retrieve tasks by calling `get_work`.

- An elapsed duration exceeding nine hundred seconds produces a cold cache recycle carrying a prompt instructing the coordinator to terminate the stale conversation identifier and invoke a fresh sub-agent for the role address and unit root.

Evaluating all idle sessions inspects registered sessions from the role session manager, filtering for sessions marked with idle status and evaluating readiness for each to collect all actionable routing directives.
