<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T04:27:23Z
CHANGE: Contract dispatch state transitions for submit, blame, and fail with in-batch dependent failure marks
CODE_HASH: 53361977594d
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# coordinate_impl implementation component

## Intent

The coordinate_impl implementation component provides concrete mechanics for session node registration, default target resolution algorithms, and dispatching to constituent control services.

The implementation maintains session dictionaries mapping dag nodes to their target states and file aliases, resolves string arguments to target nodes, routes commands to specialized coordinators, and aggregates outcomes into control dispatch outcomes.

## Factored Contracts

### Contracts

- The session coordinator maintains an in-memory dictionary of node target states. [store_node_states]
- The session coordinator maps file alias strings to registered dag nodes via exact matches, path suffixes, and role-compatible source file proxies. [map_alias_to_node]
- The session coordinator selects the single open node when only one open target remains. [default_single_open_node]
- The session coordinator selects the open node corresponding to the last modified file. [default_last_modified_file]
- The session coordinator invokes the work scheduler to discover tasks and populates session nodes. [populate_scheduled_nodes]
- The session coordinator updates the sequence of active nodes on role config when dispatching get work. [update_active_nodes_on_role_config]
- The session coordinator delegates verification to the verification evaluator, falling back to the single open target when unambiguous. [delegate_verification]
- The session coordinator delegates submission to the submission coordinator. [delegate_submission]
- The session coordinator delegates attribution to the attribution coordinator, resolving blame targets against configured upstream blame targets and rejecting self-blame. [delegate_attribution]
- Dispatching submission delegates validation and resolution to the submission coordinator and updates the target state to clean upon success. [dispatch_submit_updates_clean_state]
- Dispatching blame resolves upstream targets, delegates defect attribution to the attribution coordinator, updates the target state to attributed, and marks any in-batch dependents as failed. [dispatch_blame_updates_attributed_state]
- Dispatching fail delegates failure logging to the attribution coordinator, updates the target state to failed, and marks any in-batch dependents as failed. [dispatch_fail_updates_failed_state]
- The session coordinator formats node display aliases as source file paths or configured patterns instead of graph node target addresses. [format_node_display_alias]

### Woven Contracts

- When resolving a default target with multiple open nodes, the coordinator checks last modified file timestamps to pick the active node. [default_last_modified_file, coordinate: [resolve_default_target_contract]]
- When get work is called, the coordinator invokes the work scheduler, stores newly discovered nodes as open, updates active nodes on role config, and returns the work schedule. [populate_scheduled_nodes, store_node_states, update_active_nodes_on_role_config, coordinate: [dispatch_get_work], node_config: [role_config_set_nodes]]
- When check files is called, the coordinator evaluates single or multiple targets via the verification evaluator and returns the combined results. [delegate_verification, coordinate: [dispatch_check_files]]
- When submission is dispatched, the coordinator delegates validation and resolution to the submission coordinator and updates the target state to clean upon success. [delegate_submission, dispatch_submit_updates_clean_state, coordinate: [dispatch_submit]]
- When blame or fail is dispatched, the coordinator delegates to the attribution coordinator, updates the target state to attributed or failed, and marks in-batch dependents as failed. [delegate_attribution, dispatch_blame_updates_attributed_state, dispatch_fail_updates_failed_state, coordinate: [dispatch_blame, dispatch_fail]]
- When formatting node aliases for agent interaction or errors, the coordinator maps nodes to source file aliases or configured role source patterns. [format_node_display_alias, map_alias_to_node]

## Grounding

### Knowledge Provisions

- Session target state tracking and active node registry. [session_target_registry]
- Default target resolution for ambiguous or omitted tool invocations. [default_target_resolution]
- Central dispatching facade for control operations across verification, work scheduling, submission, and attribution. [control_dispatch_facade]

### Inherited Deferred Requirements

- Registration and tracking of active session targets across target states.
  - Grounded: [session_target_registry]
- Resolution of default targets based on open counts or file modification timestamps.
  - Grounded: [default_target_resolution]
- Work discovery dispatching to work scheduler.
  - Grounded: [work_scheduler: [work_schedule_provision]]
- Verification evaluation dispatching across single or all open targets.
  - Grounded: [verification: [verification_evaluation]]
- Target submission dispatching through submission coordinator.
  - Grounded: [submit: [submission_gating]]
- Defect attribution and failure dispatching through attribution coordinator.
  - Grounded: [attribution: [attribution_gating]]

### Knowledge Requirements

- Mapping of file alias strings to registered dag nodes.
  - Grounded: [file_alias: [alias_mapping]]
- Synchronization of active session nodes with role configuration.
  - Grounded: [node_config: [node_configuration_service]]
