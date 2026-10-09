<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 129386e17927
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# loop_cleaner_impl implementation component

imports: dag_storage, dag_subgraph, loop_node_cleaner
implements: loop_cleaner

## Intent

Executing complex multi-node workflows requires scheduling tasks in dependency order and re-evaluating dirty status without permitting runaway re-cleaning loops. Orchestrating these steps directly inside node runners creates procedural coupling and duplicates graph traversal algorithms. The loop_cleaner_impl implementation component establishes a clean push loop that consumes topologically ordered ready batches from the dag subgraph and delegates single-node execution to the node cleaner.

By delegating active subgraph scoping, ready batch selection, and node visit enforcement to the dag_subgraph component, the loop cleaner maintains clean separation between graph traversal logic and execution mechanics.

## Factored Contracts

### Contracts

- Cleaning sets the target node on the dag subgraph to determine dependency-first topological order. [set_target_on_subgraph]
- Cleaning processes ready batches of dirty nodes in topological order. [process_ready_batches]
- Cleaning records node visits for each cleaned batch. [record_node_visits_for_cleaned_batch]
- Cleaning halts immediately if the node cleaner communicates that processing cannot continue. [halt_immediately_when_cleaner_signals_halt]
- Cleaning concludes when the dag subgraph is complete. [conclude_when_subgraph_complete]

### Woven Contracts

- Scoping the target node on the dag subgraph computes dependency-first topological order and delivers ready batches for execution. [set_target_on_subgraph, process_ready_batches, dag_subgraph: [set_target_node_supplied, compute_topological_order, provide_next_ready_batch]]
- Ready batches are passed to the node cleaner, recording visit limits and halting immediately upon unhandled execution failure. [record_node_visits_for_cleaned_batch, halt_immediately_when_cleaner_signals_halt, loop_cleaner: [halt_when_node_cleaner_cannot_continue], loop_node_cleaner: [clean_dirty_nodes, communicate_processing_continuation], dag_subgraph: [record_visit_batch_supplied, record_visit_increment_counts, record_visit_enforce_iteration_limits]]
- Cleaning concludes when the dag subgraph confirms all reachable dependency nodes are clean. [conclude_when_subgraph_complete, loop_cleaner: [conclude_when_all_nodes_clean], dag_subgraph: [report_subgraph_complete, subgraph_complete_when_all_clean]]

## Grounding

### Knowledge Provisions

- Topological dependency-first cleaning traversal across target subgraphs. [loop_cleaner_service]

### Inherited Deferred Requirements

- Subgraph topological traversal and batch dirty node discovery.
  - Grounded: [dag_subgraph: [dag_subgraph_service]]
- Delegation of ready batch workloads to NodeCleaner.
  - Grounded: [loop_node_cleaner: [node_cleaner_service]]

### Knowledge Requirements

- Completion check across target subgraph.
  - Grounded: [dag_subgraph: [dag_subgraph_service]]
