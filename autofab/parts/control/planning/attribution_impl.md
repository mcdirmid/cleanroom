# attribution_impl implementation component

## Intent

The attribution_impl implementation component provides concrete mechanics for blame target matching, newline validation, feedback message formatting, and cascade failure updates.

The implementation matches blame strings against upstream file aliases, sanitizes critique explanations into a single continuous paragraph without line breaks or carriage returns, injects feedback messages into graph storage, updates node statuses, and visits dependent in-batch nodes to transition them to failed state.

## Factored Contracts

### Contracts

- The attribution coordinator resolves the culprit node corresponding to the blame target string. [resolve_culprit_node]
- The attribution coordinator validates that the culprit node is in the source node's upstream dependency set. [validate_culprit_upstream]
- The attribution coordinator sanitizes multi-line critique explanations by collapsing line breaks into spaces and validates critique length against configured feedback limits. [sanitize_critique_newlines]
- The attribution coordinator formats a rejection response listing allowed blame targets as file aliases when matching fails. [format_invalid_target_error]
- The attribution coordinator formats a rejection response when critique explanations exceed configured feedback character limits, advising defect prioritization. [format_critique_limit_error]
- The attribution coordinator creates a feedback message and stores it on the culprit node. [store_feedback_message]
- The attribution coordinator updates culprit node status to dirty in graph storage. [update_culprit_status_dirty]
- The attribution coordinator updates dependent node states to failed in the active session. [update_dependent_nodes_failed]
- The attribution coordinator formats blame and failure outcome messages using user-facing file aliases. [format_attribution_outcome_aliases]
- The attribution coordinator resolves culprit files and executes in-band feedback mutations directly in the canonical repository. [execute_file_blame_mechanics]
- The attribution coordinator resolves target files and appends failure diagnostics to in-band metadata. [execute_file_failure_mechanics]

### Woven Contracts

- When a blame target does not match an upstream dependency, the coordinator rejects attribution with an error listing valid targets as file aliases. [resolve_culprit_node, validate_culprit_upstream, format_invalid_target_error]
- When an explanation contains newlines, the coordinator sanitizes it into a continuous paragraph without rejecting. [sanitize_critique_newlines]
- When blame validation succeeds, the coordinator stores the feedback message, updates the culprit to dirty, marks dependents as failed, and formats outcomes using file aliases. [store_feedback_message, update_culprit_status_dirty, update_dependent_nodes_failed, format_attribution_outcome_aliases, attribution: [mark_source_attributed]]
- When blaming a culprit file, the coordinator sanitizes newlines, writes in-band feedback directly in the canonical repository, and constructs formatted blame messages. [sanitize_critique_newlines, execute_file_blame_mechanics, attribution: [execute_file_blame_mutation], src_metadata: [append_feedback_entry, update_metadata_disk]]
- When failing a target file, the coordinator writes failure diagnostics and copies files. [execute_file_failure_mechanics, attribution: [execute_file_failure_mutation], src_metadata: [append_feedback_entry, update_metadata_disk]]

## Grounding

### Knowledge Provisions

- Defect blame gating validating upstream targets, feedback configuration, and single-paragraph critique formatting. [attribution_gating]
- Failure recording and cascading invalidation across in-batch dependent nodes. [failure_propagation]
- File-level blame and failure execution mechanics. [file_attribution_mechanics]

### Inherited Deferred Requirements

- Verification of upstream dependency relationships and feedback reception enablement.
  - Grounded: [dag_storage: [dag_storage_service], node_config: [node_configuration_service]]
- Sanitization of multi-line critique structure into a continuous paragraph and length boundary enforcement.
  - Grounded: [attribution_gating]
- Persistence of feedback messages and node status mutations in graph storage.
  - Grounded: [dag_storage: [dag_storage_service]]

### Knowledge Requirements

- Cascading status transitions to failed state across active session in-batch dependents.
  - Grounded: [failure_propagation]
- In-band source metadata extraction and feedback formatting on disk.
  - Grounded: [src_metadata: [source_metadata_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T11:00:00Z
LAST_CHANGED: 2026-10-30T11:00:00Z
CHANGE: Sanitize multi-line critique explanations into continuous paragraph
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
