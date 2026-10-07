<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: ca3f68739a3b
-->

# control_attribution_impl implementation component

imports: agent_session, dag_storage, agent_file_alias, agent_node_config
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

### Woven Contracts

- When a blame target does not match an upstream dependency, the coordinator rejects attribution with an error listing valid targets. [resolve_culprit_node, validate_culprit_upstream, format_invalid_target_error]
- When an explanation contains newlines, the coordinator rejects attribution with a single-paragraph requirement error. [check_explanation_newlines, format_newline_error]
- When blame validation succeeds, the coordinator stores the feedback message, updates the culprit to dirty, and marks dependents as failed. [store_feedback_message, update_culprit_status_dirty, update_dependent_nodes_failed, control_attribution: [mark_source_attributed]]

## Grounding

### Knowledge Provisions

- Defect blame gating validating upstream targets, feedback configuration, and single-paragraph critique formatting. [attribution_gating]
- Failure recording and cascading invalidation across in-batch dependent nodes. [failure_propagation]

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
