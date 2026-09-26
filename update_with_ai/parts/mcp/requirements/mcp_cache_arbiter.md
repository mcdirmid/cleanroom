# mcp_cache_arbiter interface component

imports: mcp_session

## Assumptions and Requirements

### Requirements

1. Evaluating session readiness produces a warm cache wakeup when ready dirty nodes exist and elapsed inactivity is at most nine hundred seconds.
2. Evaluating session readiness produces a cold cache recycle when ready dirty nodes exist and elapsed inactivity exceeds nine hundred seconds.
3. Evaluating all idle sessions produces routing actions for all idle sessions with ready work.

## Grounding Facts

### Knowledge Needed

- Cache inactivity threshold.
- Session last active timestamp and idle status.
- Ready dirty nodes for assigned role.

### Actions Needed

- Evaluate conversation readiness against elapsed inactivity and ready dirty nodes.
- Enumerate idle sessions to collect routing actions.
