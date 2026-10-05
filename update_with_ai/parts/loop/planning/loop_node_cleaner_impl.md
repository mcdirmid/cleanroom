<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 375a7c5eef5c
-->

# loop_node_cleaner_impl implementation component

imports: agent_node_config, agent_storage, dag_storage, loop_conversation, loop_driver, runner_logger, sandbox
implements: loop_node_cleaner

## Intent

Driving node execution requires bridging abstract graph clean directives to concrete multi-turn turn loops and translating tool termination responses back into graph updates. The loop_node_cleaner_impl implementation component configures session roles for dirty nodes, initializes conversation history with get work directives, executes the agent loop, and converts termination responses into in-band graph state updates.

By retrying transient session failures once before propagation, isolating promptless pass-through nodes from agent sessions, and routing blame feedback strictly to blamed dependency owners, the cleaner provides dependable node execution without pushing messages into downstream files.

## Factored Contracts

### Contracts

- The node cleaner cleans dirty nodes within an agent session phase. [clean_within_agent_session_phase]
- Role config presents the role of the dirty nodes to session services. [role_config_presents_node_role]
- The node cleaner logs unexpected execution failures to the runner logger. [log_unexpected_failures_to_logger]
- The node cleaner retries the session phase once upon encountering an unexpected execution failure. [retry_session_phase_once_on_failure]
- The node cleaner propagates unexpected execution failures if a retried phase fails. [propagate_failure_after_retry]
- The conversation is initialized with instructions directing the agent to call the get work tool. [initialize_conversation_with_get_work]
- Cleaning resolves dirty nodes by evaluating the loop driver outcome. [resolve_nodes_evaluating_loop_outcome]
- Resolving dirty nodes marks the nodes clean in graph storage with the change summary when the outcome signals successful advancement with workspace file modifications. [mark_nodes_clean_with_summary_on_advancement_with_mods]
- Resolving dirty nodes marks the nodes clean in graph storage without advancing last changed timestamps when no workspace files were modified. [mark_nodes_clean_without_change_when_unmodified]
- Resolving dirty nodes produces feedback messages addressed strictly to the declared feedback dependency node owning the blamed file when the outcome signals blame attributed to a configured blame target. [produce_feedback_messages_on_blame]
- Resolving dirty nodes produces no propagating messages when the blamed file fails to match a configured blame target. [omit_feedback_messages_on_unconfigured_blame]
- Resolving dirty nodes produces no propagating messages when the outcome signals run failure. [omit_messages_on_run_failure]
- Resolving dirty nodes leaves nodes dirty when the outcome signals run failure. [leave_nodes_dirty_on_run_failure]
- Resolving dirty nodes communicates that processing cannot continue when the outcome signals run failure. [signal_cannot_continue_on_run_failure]
- When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase. [resolve_promptless_nodes_without_session]
- When dirty nodes define no task prompt and incoming messages indicate upstream changes, cleaning marks the nodes clean with a change summary. [mark_promptless_clean_with_summary_when_incoming_changes]
- When dirty nodes define no task prompt and incoming messages indicate no upstream changes, cleaning marks the nodes clean without changes. [mark_promptless_clean_without_changes_when_no_incoming_changes]
- Cleaning dirty nodes marks the nodes clean in graph storage. [mark_cleaned_nodes_clean_in_storage]
- Cleaning dirty nodes delivers resulting feedback messages strictly to their addressed feedback dependency node. [deliver_feedback_messages_to_target]
- Cleaning dirty nodes omits delivering feedback messages to non-feedback dependencies. [omit_feedback_delivery_to_non_feedback_dependencies]

## Woven Contracts

- The node cleaner establishes session roles, seeds get work instructions, drives agent turns, and retries once on unexpected failures before aborting. \[clean_within_agent_session_phase, role_config_presents_node_role, initialize_conversation_with_get_work, log_unexpected_failures_to_logger, retry_session_phase_once_on_failure, propagate_failure_after_retry, agent_node_config: [role_config_set_role, role_config_set_nodes], loop_conversation: [initialize_with_initial_messages], loop_driver: [drive_turns_executing_tools]\]
- Evaluating loop driver outcomes updates graph storage, marking nodes clean when files are modified, routing blame feedback, or halting on failure. \[resolve_nodes_evaluating_loop_outcome, mark_nodes_clean_with_summary_on_advancement_with_mods, mark_nodes_clean_without_change_when_unmodified, produce_feedback_messages_on_blame, omit_feedback_messages_on_unconfigured_blame, omit_messages_on_run_failure, leave_nodes_dirty_on_run_failure, signal_cannot_continue_on_run_failure, mark_cleaned_nodes_clean_in_storage, deliver_feedback_messages_to_target, omit_feedback_delivery_to_non_feedback_dependencies, loop_node_cleaner: [communicate_processing_continuation, cannot_continue_on_unhandleable_failure], dag_storage: [record_feedback_messages, access_node_messages]\]
- Nodes lacking task prompts resolve pass-through changes directly without agent sessions, marking nodes clean based on incoming update presence. \[resolve_promptless_nodes_without_session, mark_promptless_clean_with_summary_when_incoming_changes, mark_promptless_clean_without_changes_when_no_incoming_changes, agent_storage: [query_node_def_supplied, provide_node_definitions]\]
