# antigravity_coordinator_impl implementation component

imports: antigravity_mcp_client, antigravity_sandbox_gate, antigravity_telemetry
implements: antigravity_coordinator

## Purpose

The antigravity_coordinator_impl implementation component realizes deterministic orchestration, tiered worker retention, and wave action planning for Cleanroom convergence workflows.

Executing multi-wave Cleanroom workflows without token bloat or context corruption requires enforcing strict worker reuse criteria, preserving warm context for overlapping units, and terminating stale workers. The antigravity_coordinator_impl implementation component queries the Model Context Protocol server, tracks worker lifecycles, and formulates JSON action plans.

**Out of scope:** The antigravity_coordinator_impl implementation component does not edit code lines, execute build targets directly, or compile AST specifications; these are handled by other components.

## Types and Behavior

The antigravity coordinator operates as a system service managing worker pool lifecycles and wave batch planning.

Loading and saving state reads and writes coordinator state as JSON within the cleanroom state directory in the workspace root.

Evaluating pruning identifies workers with failed status or exceeding idle timeouts or token limits. Workers with failed status are immediately marked for termination. Workers idle longer than the idle prune ttl sec timeout are marked for termination. Workers whose context tokens exceed the idle prune warm cap tokens ceiling and whose idle duration exceeds the idle prune warm ttl sec timeout are marked for termination. Pruned workers are removed from active coordinator state.

Evaluating worker eligibility for reuse verifies idle status and tiered context limits based on worker age. When the worker age is less than the ttl fresh sec duration, the worker qualifies if its context tokens are below the cap fresh tokens ceiling. When the worker age is between the ttl fresh sec duration and the ttl max sec duration, the worker qualifies if its context tokens are below the cap warm tokens ceiling. Workers exceeding the ttl max sec duration or not in idle status do not qualify for reuse.

Partitioning batches divides ready units into contiguous sub-batches bounded by the batch size limit to enable concurrent worker execution across independent units.

Planning the next step updates worker completion reports, refreshes token usage statistics from telemetry, prunes expired workers, ensures the server is active, and queries the next ready batch:

- When worker reports indicate failures, failure counts for assigned units are incremented. If any unit exceeds the max retries per unit limit, DAG convergence is aborted and all workers are terminated. When worker reports indicate successful completion, failure counts for assigned units are cleared.

- Workers currently in busy status are in-flight; only idle workers are eligible for reuse or revives. If ready units are already assigned to in-flight busy workers, no redundant spawns or revives are generated. Newly spawned and revived workers are marked with busy status.

- When the subgraph is clean or no dirty nodes remain, all remaining workers are terminated, the server is shut down, and a completed action plan is returned.

- When a ready batch is returned, the batch is partitioned by batch size. For each partition, eligible warm workers matching the ready role are evaluated, preferring workers with unit footprint overlap and selecting the worker with the least conversation context tokens, falling back to eligible non-overlapping workers with least conversation context tokens. Assigned units are additively merged into the revived worker's unit footprint. Reviving a warm worker registers the new session on the Model Context Protocol server and records the session association in the sandbox gate. If no eligible warm worker is found, a fresh worker is spawned and its session is registered on the Model Context Protocol server.

Registering spawned workers associates newly spawned conversation identifiers with their assigned sessions, copying role and unit footprint from pending spawns into active worker state records with busy status.

Recording worker status transitions a worker matching the session identifier to failed status upon failure or idle status upon completion, updates last active timestamp, and records unit failure counts or clears failure counts based on completion or failure status.

The antigravity coordinator ensures server availability on a configured port and batch size by checking active sentinel file presence and process liveness in the workspace root, removing stale sentinels, launching the cleanroom Model Context Protocol runner subprocess when inactive, and polling until the active sentinel file confirms process liveness.

