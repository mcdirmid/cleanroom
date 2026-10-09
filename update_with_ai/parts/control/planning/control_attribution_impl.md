<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: ca3f68739a3b
-->

# control_attribution_impl implementation component

imports: agent_session, dag_storage, agent_file_alias, agent_node_config, src_metadata
implements: control_attribution

## Intent

The control_attribution_impl implementation component provides concrete mechanics for blame target matching, newline validation, feedback message formatting, and cascade failure updates.

The implementation matches blame strings against upstream file aliases, validates that the explanation contains no line breaks or carriage returns, injects feedback messages into graph storage, updates node statuses, and visits dependent in-batch nodes to transition them to failed state.

## Factored Contracts

### Contracts

- The attribution coordinator resolves the culprit node corresponding to the blame target string. [resolve_culprit_node]
- The attribution coordinator validates that the culprit node is in the source node's upstream dependency set. [validate_culprit_upstream]
- The attribution coordinator inspects the explanation string for newline and carriage return characters. [check_explanation_newlines]
- The attribution coordinator formats a rejection response listing allowed blame targets when matching fails. [format_invalid_target_error]
- The attribution coordinator formats a rejection response when newlines are detected. [format_newline_error]
- The attribution coordinator creates a feedback message and stores it on the culprit node. [store_feedback_message]
- The attribution coordinator updates culprit node status to dirty in graph storage. [update_culprit_status_dirty]
- The attribution coordinator updates dependent node states to failed in the active session. [update_dependent_nodes_failed]
- The attribution coordinator resolves culprit files and executes in-band feedback mutations directly in the canonical repository. [execute_file_blame_mechanics]
- The attribution coordinator resolves target files and appends failure diagnostics to in-band metadata. [execute_file_failure_mechanics]

### Woven Contracts

- When a blame target does not match an upstream dependency, the coordinator rejects attribution with an error listing valid targets. [resolve_culprit_node, validate_culprit_upstream, format_invalid_target_error]
- When an explanation contains newlines, the coordinator rejects attribution with a single-paragraph requirement error. [check_explanation_newlines, format_newline_error]
- When blame validation succeeds, the coordinator stores the feedback message, updates the culprit to dirty, and marks dependents as failed. [store_feedback_message, update_culprit_status_dirty, update_dependent_nodes_failed, control_attribution: [mark_source_attributed]]
- When blaming a culprit file, the coordinator checks newlines, writes in-band feedback directly in the canonical repository, and constructs formatted blame messages. [check_explanation_newlines, execute_file_blame_mechanics, control_attribution: [execute_file_blame_mutation], src_metadata: [append_feedback_entry, mark_dirty_status, update_metadata_disk]]
- When failing a target file, the coordinator writes failure diagnostics and copies files. [execute_file_failure_mechanics, control_attribution: [execute_file_failure_mutation], src_metadata: [append_feedback_entry, update_metadata_disk]]

## Grounding

### Knowledge Provisions

- Defect blame gating validating upstream targets, feedback configuration, and single-paragraph critique formatting. [attribution_gating]
- Failure recording and cascading invalidation across in-batch dependent nodes. [failure_propagation]
- File-level blame and failure execution mechanics. [file_attribution_mechanics]

### Inherited Deferred Requirements

- Verification of upstream dependency relationships and feedback reception enablement.
  - Grounded: [dag_storage: [dag_storage_service], agent_node_config: [node_configuration_service]]
- Enforcement of single-paragraph critique structure with zero newline characters.
  - Grounded: [attribution_gating]
- Persistence of feedback messages and node status mutations in graph storage.
  - Grounded: [dag_storage: [dag_storage_service]]

### Knowledge Requirements

- Cascading status transitions to failed state across active session in-batch dependents.
  - Grounded: [failure_propagation]
- In-band source metadata extraction and feedback formatting on disk.
  - Grounded: [src_metadata: [source_metadata_service]]
