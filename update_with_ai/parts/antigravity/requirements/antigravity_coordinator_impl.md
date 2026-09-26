# antigravity_coordinator_impl implementation component

imports: antigravity_mcp_client, antigravity_sandbox_gate, antigravity_telemetry
implements: antigravity_coordinator

## Assumptions and Requirements

### Requirements

1. Loading and saving state reads and writes coordinator state as JSON within the cleanroom state directory in the workspace root.
2. Evaluating pruning identifies workers with failed status or exceeding idle timeouts or token limits.
3. Workers with failed status are immediately marked for termination.
4. Workers idle longer than the idle prune ttl sec timeout are marked for termination.
5. Workers whose context tokens exceed the idle prune warm cap tokens ceiling and whose idle duration exceeds the idle prune warm ttl sec timeout are marked for termination.
6. Pruned workers are removed from active coordinator state.
7. Evaluating worker eligibility for reuse verifies idle status and tiered context limits based on worker age.
8. When the worker age is less than the ttl fresh sec duration, the worker qualifies if its context tokens are below the cap fresh tokens ceiling.
9. When the worker age is between the ttl fresh sec duration and the ttl max sec duration, the worker qualifies if its context tokens are below the cap warm tokens ceiling.
10. Workers exceeding the ttl max sec duration or not in idle status do not qualify for reuse.
11. Partitioning batches divides ready units into contiguous sub-batches bounded by the batch size limit to enable concurrent worker execution across independent units.
12. Planning the next step updates worker completion reports, refreshes token usage statistics from telemetry, prunes expired workers, ensures the server is active, and queries the next ready batch.
13. When worker reports indicate failures, failure counts for assigned units are incremented. If any unit exceeds the max retries per unit limit, DAG convergence is aborted and all workers are terminated. When worker reports indicate successful completion, failure counts for assigned units are cleared.
14. Workers currently in busy status are in-flight; only idle workers are eligible for reuse or revives. If ready units are already assigned to in-flight busy workers, no redundant spawns or revives are generated. Newly spawned and revived workers are marked with busy status.
15. When the subgraph is clean or no dirty nodes remain, all remaining workers are terminated, the server is shut down, and a completed action plan is returned.
16. When a ready batch is returned, the batch is partitioned by batch size. For each partition, eligible warm workers matching the ready role are evaluated, preferring workers with unit footprint overlap and selecting the worker with the least conversation context tokens, falling back to eligible non-overlapping workers with least conversation context tokens. Assigned units are additively merged into the revived worker's unit footprint. Reviving a warm worker registers the new session on the Model Context Protocol server and records the session association in the sandbox gate. If no eligible warm worker is found, a fresh worker is spawned and its session is registered on the Model Context Protocol server.
17. Registering spawned workers associates newly spawned conversation identifiers with their assigned sessions, copying role and unit footprint from pending spawns into active worker state records with busy status.
18. Recording worker status transitions a worker matching the session identifier to failed status upon failure or idle status upon completion, updates last active timestamp, and records unit failure counts or clears failure counts based on completion or failure status.
19. The antigravity coordinator ensures server availability on a configured port and batch size by checking active sentinel file presence and process liveness in the workspace root, removing stale sentinels, launching the cleanroom Model Context Protocol runner subprocess when inactive, and polling until the active sentinel file confirms process liveness.

## Grounding Facts

### Knowledge Needed

- Coordinator configuration thresholds.
- Coordinator state file path in cleanroom state directory.
- Sentinel file path and process liveness in workspace root.
- Worker lifecycle states and token metrics from `antigravity_telemetry`.
- Active worker session mappings from `antigravity_sandbox_gate`.
- Next ready batch from `antigravity_mcp_client`.

### Actions Needed

- Read and write coordinator state JSON file.
- Inspect sentinel file and verify process liveness.
- Launch cleanroom MCP runner subprocess.
- Query token usage statistics via `antigravity_telemetry`.
- Register sessions on `antigravity_mcp_client` and record associations in `antigravity_sandbox_gate`.
- Dispatch tool calls via `antigravity_mcp_client` to query next batch and shutdown server.
- Evaluate pruning and reuse eligibility.
- Partition batches and select warm or fresh workers.
- Construct action plan.

