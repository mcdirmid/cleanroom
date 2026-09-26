# mcp_cache_arbiter_impl implementation component

imports: dag_storage, dag_subgraph, mcp_cache_arbiter, mcp_session
implements: mcp_cache_arbiter

## Assumptions and Requirements

### Requirements

1. Evaluating session readiness produces a warm cache wakeup when ready dirty nodes exist and elapsed inactivity is at most nine hundred seconds.
2. Evaluating session readiness produces a cold cache recycle when ready dirty nodes exist and elapsed inactivity exceeds nine hundred seconds.
3. Evaluating all idle sessions produces routing actions for all idle sessions with ready work.

## Grounding Facts

### Knowledge Needed

- Cache inactivity threshold.
- Session last active timestamp and idle status from `mcp_session.RoleSessionManager`.
- Ready dirty nodes for session role from `dag_subgraph.DagSubgraph`.
- Predefined prompt templates for warm wakeup and cold recycle.

### Actions Needed

- Resolve session by conversation identifier from `mcp_session.RoleSessionManager`.
- Enumerate active sessions from `mcp_session.RoleSessionManager`.
- Query ready dirty nodes for session role from `dag_subgraph.DagSubgraph`.
- Calculate elapsed inactivity against current timestamp.
- Construct routing action based on elapsed duration and dirty node availability.
