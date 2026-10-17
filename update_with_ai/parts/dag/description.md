# DAG Part (`update_with_ai/parts/dag`)

## Purpose

The **dag** part defines the core Directed Acyclic Graph (DAG) abstractions, in-memory graph indexing, subgraph reachability queries, ready task batching, and dirty state evaluation for Cleanroom.

Cleanroom views software development as a dependency-directed graph of discrete units of work across methodological roles (e.g. high-level spec, planning, scenarios, low-level spec, spec QA, library implementation, unit tests, QA, coverage). The dag part provides the structural model for these target nodes and their dependencies, establishes rules for message propagation across non-silent edges, provides active subgraph views over reachable dependencies, and bounds node visit limits to prevent infinite execution loops.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/dag/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/dag/high):

- [`dag_storage.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/dag/high/dag_storage.md): Defines the abstract `DagStorage` interface. A `DagNode` couples a *unit address* (the artifact worked on) with a *role address* (the phase of work applied). It tracks direct dependencies (distinguishing regular dependencies from *silent* dependencies that suppress change message propagation) and manages two message categories: *change messages* (informing dependents how an upstream artifact changed) and *feedback messages* (blaming an upstream dependency for defects detected downstream). It formalizes the dirty evaluation contract (a node is dirty if its artifact is missing, metadata is invalid, tagged dirty, has unacted feedback, or an upstream non-silent dependency was changed after the node was last cleaned).
- [`dag_subgraph.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/dag/high/dag_subgraph.md) & [`dag_subgraph_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/dag/high/dag_subgraph_impl.md): Models an active execution subgraph rooted at a target node. It indexes all reachable nodes in dependency-first topological order, breaking ties by dynamic *role tier depth* first and unit address second. It provides the `next ready batch` of dirty nodes whose dependencies are satisfied (grouped by role address up to configured batch limits), reports whether the target subgraph is `complete` (all reachable nodes clean), and tracks node visit counts to prevent cycle divergence.
- [`dag_config.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/dag/high/dag_config.md): Formalizes system-level configuration parameters for DAG traversal, specifically the maximum batch size of nodes processed simultaneously and the node visit limit that halts execution if a node is visited too many times.
- [`dag_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/dag/high/dag_asm.md): Assembles the DAG storage and subgraph query implementations into the unified DAG subsystem.

## How It Is Used by Other Parts

The `dag` part is the mathematical and structural spine of Cleanroom's build and cleaning pipelines:

- **`agent`**: `agent_storage` extends `dag_storage` with target manifest configuration, task prompts, and node execution definitions.
- **`control`**: `control_work_scheduler` and `control_attribution` rely directly on `dag_storage` and `dag_subgraph` to query reachable nodes, schedule tasks by role tier depth, order execution batches, and route feedback messages to blamed upstream DAG nodes.
- **`storage`**: `src_storage_impl` implements the persistent backend for `dag_storage`, mapping in-memory DAG nodes to on-disk source files and evaluating dirtiness dynamically from in-band comment metadata.
- **`loop`**: `loop_cleaner` and `loop_node_cleaner` use `dag_subgraph` to traverse ready node batches in topological order and iterate until `subgraph.is_complete` returns true.
- **`sandbox`**: `sandbox_run_control` and `sandbox_submission` query node addresses and update DAG state when agents call `submit` or `blame`.
- **`tools`**: `workspace_work`, `workspace_dirtiness`, and `workspace_pending` query DAG dirtiness and pending messages to present actionable work items to agents.
- **`uv`**: `uv_target` and `uv_node_config_impl` map build targets and role definitions to canonical DAG nodes and dependencies.
- **`systems`**: Aggregated into `uv_openai_loop_asm` and `uv_cleanroom_asm`.
