<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:07:15Z
CHANGE: Canonicalize change timestamps and state the feedback routing invariant
CODE_HASH: 813128a78879
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# loop_node_cleaner_impl implementation component

## Intent

Driving node execution requires bridging abstract graph clean directives to concrete multi-turn turn loops and translating tool termination responses back into graph updates. The loop_node_cleaner_impl implementation component configures session roles for dirty nodes, initializes conversation history with get work directives, executes the agent loop, and converts termination responses into in-band graph state updates.

By retrying transient session failures once before propagation, isolating promptless pass-through nodes from agent sessions, and routing blame feedback strictly to blamed dependency owners, the cleaner provides dependable node execution without pushing messages into downstream files.

## Factored Contracts

### Contracts

- The node cleaner cleans dirty nodes within an agent session phase. [clean_within_agent_session_phase]
- Cleaning sets the target node on the dag subgraph to determine dependency-first topological order. [set_target_on_subgraph]
- Cleaning processes ready batches of dirty nodes in topological order. [process_ready_batches]
- Cleaning records node visits for each cleaned batch. [record_node_visits_for_cleaned_batch]
- Cleaning halts immediately if the node cleaner communicates that processing cannot continue. [halt_immediately_when_cleaner_signals_halt]
- Cleaning concludes when the dag subgraph reports that the target subgraph is complete, meaning every reachable node in the target subgraph is clean in dag storage. [conclude_when_subgraph_complete]
- Role config presents the role of the dirty nodes to session services. [role_config_presents_node_role]
- The node cleaner logs unexpected execution failures to the runner logger. [log_unexpected_failures_to_logger]
- The node cleaner retries the session phase once upon encountering an unexpected execution failure. [retry_session_phase_once_on_failure]
- The node cleaner propagates unexpected execution failures if a retried phase fails. [propagate_failure_after_retry]
- The conversation is initialized with instructions directing the agent to call the get work tool. [initialize_conversation_with_get_work]
- Cleaning resolves dirty nodes by evaluating the loop driver outcome. [resolve_nodes_evaluating_loop_outcome]
- Resolving dirty nodes marks each node clean in graph storage with the change summary when the outcome signals successful advancement with workspace file modifications for that node. [mark_nodes_clean_with_summary_on_advancement_with_mods]
- Resolving dirty nodes marks each node clean in graph storage without advancing change timestamps when no workspace files were modified for that node. [mark_nodes_clean_without_change_when_unmodified]
- Resolving dirty nodes produces feedback messages addressed strictly to the declared feedback dependency node owning the blamed file when the outcome signals blame attributed to a configured blame target. [produce_feedback_messages_on_blame]
- Resolving dirty nodes produces no feedback message and leaves the nodes dirty when the blamed file does not match a configured blame target. [omit_feedback_messages_on_unconfigured_blame]
- Resolving dirty nodes produces no propagating messages when the outcome signals run failure. [omit_messages_on_run_failure]
- Resolving dirty nodes leaves nodes dirty when the outcome signals run failure. [leave_nodes_dirty_on_run_failure]
- Resolving dirty nodes communicates that processing cannot continue when the outcome signals run failure. [signal_cannot_continue_on_run_failure]
- When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase. [resolve_promptless_nodes_without_session]
- When dirty nodes define no task prompt and incoming messages indicate upstream changes, cleaning marks the nodes clean with a change summary. [mark_promptless_clean_with_summary_when_incoming_changes]
- When dirty nodes define no task prompt and incoming messages indicate no upstream changes, cleaning marks the nodes clean without changes. [mark_promptless_clean_without_changes_when_no_incoming_changes]
- Cleaning dirty nodes marks the nodes clean in graph storage. [mark_cleaned_nodes_clean_in_storage]
- Cleaning dirty nodes delivers resulting feedback messages strictly to their addressed feedback dependency node. [deliver_feedback_messages_to_target]
- Cleaning dirty nodes omits delivering feedback messages to non-feedback dependencies. [omit_feedback_delivery_to_non_feedback_dependencies]

### Woven Contracts

- The node cleaner establishes session roles, seeds get work instructions, drives agent turns, and retries once on unexpected failures before aborting. [clean_within_agent_session_phase, role_config_presents_node_role, initialize_conversation_with_get_work, log_unexpected_failures_to_logger, retry_session_phase_once_on_failure, propagate_failure_after_retry, agent_node_config: [role_config_set_role], loop_conversation: [initialize_with_initial_messages], loop_driver: [drive_turns_executing_tools]]
- Evaluating loop driver outcomes updates graph storage, marking nodes clean when files are modified, routing blame feedback, or halting on failure. [resolve_nodes_evaluating_loop_outcome, mark_nodes_clean_with_summary_on_advancement_with_mods, mark_nodes_clean_without_change_when_unmodified, produce_feedback_messages_on_blame, omit_feedback_messages_on_unconfigured_blame, omit_messages_on_run_failure, leave_nodes_dirty_on_run_failure, signal_cannot_continue_on_run_failure, mark_cleaned_nodes_clean_in_storage, deliver_feedback_messages_to_target, omit_feedback_delivery_to_non_feedback_dependencies, loop_node_cleaner: [communicate_processing_continuation, cannot_continue_on_unhandleable_failure], dag_storage: [add_feedback_messages, record_feedback_in_metadata, access_node_messages]]
- Nodes lacking task prompts resolve pass-through changes directly without agent sessions, marking nodes clean based on incoming update presence. [resolve_promptless_nodes_without_session, mark_promptless_clean_with_summary_when_incoming_changes, mark_promptless_clean_without_changes_when_no_incoming_changes, agent_storage: [query_node_def_supplied, provide_node_definitions]]
- Scoping the target node on the dag subgraph computes dependency-first topological order and delivers ready batches for execution. [set_target_on_subgraph, process_ready_batches, dag_subgraph: [set_target_node_supplied, compute_topological_order, provide_next_ready_batch]]
- Ready batches are passed to the node cleaner, recording visit limits and halting immediately upon unhandled execution failure. [record_node_visits_for_cleaned_batch, halt_immediately_when_cleaner_signals_halt, loop_cleaner: [halt_when_node_cleaner_cannot_continue], loop_node_cleaner: [clean_dirty_nodes, communicate_processing_continuation], dag_subgraph: [record_visit_batch_supplied, record_visit_increment_counts, record_visit_enforce_iteration_limits]]
- Cleaning concludes when the dag subgraph confirms all reachable dependency nodes are clean. [conclude_when_subgraph_complete, loop_cleaner: [conclude_when_all_nodes_clean], dag_subgraph: [report_subgraph_complete, subgraph_complete_when_all_clean]]

## Grounding

### Knowledge Provisions

- Topological dependency-first cleaning traversal across target subgraphs. [loop_cleaner_service]
- Node cleaning execution for batches of dirty nodes sharing a role. [node_cleaner_service]

### Inherited Deferred Requirements

- Subgraph topological traversal and batch dirty node discovery.
  - Grounded: [dag_subgraph: [dag_subgraph_service]]
- Delegation of ready batch workloads to NodeCleaner.
  - Grounded: [node_cleaner_service]
- Execution environment orchestration for agent session phases.
  - Grounded: [loop_driver: [loop_driver_service], agent_node_config: [node_configuration_service], loop_conversation: [loop_conversation_service], runner_logger: [runner_logging_service]]
- Translation of execution outcomes into graph storage mutations.
  - Grounded: [dag_storage: [dag_storage_service], src_metadata: [source_metadata_service]]

### Knowledge Requirements

- Pass-through resolution for promptless nodes without establishing agent sessions.
  - Grounded: [agent_storage: [agent_storage_service], dag_storage: [dag_storage_service]]
