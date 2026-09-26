# antigravity_coordinator interface component

## Assumptions and Requirements

### Requirements

1. A coordinator config record encapsulates scheduling thresholds, exposing a ttl fresh sec duration, a ttl max sec duration, a cap fresh tokens ceiling, a cap warm tokens ceiling, an idle prune ttl sec timeout, an idle prune warm ttl sec timeout, an idle prune warm cap tokens ceiling, a batch size limit, and a max retries per unit limit.
2. A worker state record maintains lifecycle data for a subagent worker, exposing a conv id, a role, a session id, a created at timestamp, a last active at timestamp, a unit footprint sequence, a context tokens size, and a status.
3. A coordinator state record persists state across execution turns, exposing a target unit, a session counter, a workers mapping, a pending spawns mapping, and a failure counts mapping.
4. An action plan record defines actions for an orchestration turn, exposing an is complete indicator, a kill list, a spawns list, a revives list, a dirty nodes list, and a summary description.
5. The antigravity coordinator reads coordinator state for a workspace root and target.
6. The antigravity coordinator writes coordinator state to a workspace root.
7. The antigravity coordinator determines worker identifiers to terminate based on worker failure status, idle timeouts, and context token caps.
8. The antigravity coordinator checks whether a worker state qualifies for reuse given target units, coordinator config, and a current timestamp.
9. The antigravity coordinator divides a ready batch into clusters bounded by batch size.
10. The antigravity coordinator computes an action plan for a target, an active worker reports mapping, coordinator config, workspace root, timestamp, and a server port.
11. The antigravity coordinator associates newly spawned conversation identifiers with assigned sessions in coordinator state.
12. The antigravity coordinator updates worker lifecycle status to idle or failed and updates unit failure counts for a session identifier in coordinator state.
13. The antigravity coordinator verifies server availability on a port with the configured batch size.

## Grounding Facts

### Knowledge Needed

- Coordinator configuration thresholds.
- Coordinator state from workspace persistence.
- Worker state records and active worker telemetry reports.
- Server availability and port number.
- Ready batch nodes and target unit.

### Actions Needed

- Read and write coordinator state in workspace root.
- Evaluate worker termination criteria.
- Check worker qualification for reuse.
- Partition ready nodes into bounded clusters.
- Compute orchestration action plan.
- Update worker status, spawned sessions, and failure counts.
- Verify server port availability.
