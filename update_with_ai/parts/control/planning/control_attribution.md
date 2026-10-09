<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: a80d52ee1919
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# control_attribution interface component

imports: agent_session, dag_storage, agent_file_alias, agent_node_config, src_metadata

## Intent

The control_attribution interface component defines contracts for upstream blame validation, single-paragraph critique enforcement, defect feedback injection, and failure status recording.

Defect attribution allows agents encountering irrecoverable upstream flaws to send targeted feedback to upstream dependency owners rather than producing invalid workarounds. The attribution coordinator verifies that blame targets are declared upstream dependencies, rejects multi-paragraph or rambling critiques, records feedback in graph storage, marks culprits dirty for reprocessing, and propagates failure cascades to dependent in-batch targets.

## Factored Contracts

### Typing

- An attribution outcome reports an accepted status, outcome message, and affected nodes.
- An attribution coordinator operates within the agent session lifecycle tier.

### Contracts

- An attribution coordinator asserts that the blame target is a declared upstream dependency. [assert_blame_target_is_upstream]
- An attribution coordinator asserts that the blame target is configured to receive feedback. [assert_blame_target_receives_feedback]
- An attribution coordinator asserts that the explanation string contains zero newline characters. [assert_single_paragraph_critique]
- An attribution coordinator asserts that in-batch dependencies of the source target are clean. [assert_source_dependencies_clean]
- An attribution coordinator records a feedback message on the culprit node in graph storage. [record_blame_feedback]
- An attribution coordinator marks the culprit node status as dirty in graph storage. [mark_culprit_dirty]
- An attribution coordinator marks the source target node as attributed. [mark_source_attributed]
- An attribution coordinator marks downstream in-batch dependent nodes as failed. [propagate_in_batch_failure]
- An attribution coordinator records a failure diagnostic on the target node in graph storage. [record_failure_diagnostic]
- An attribution coordinator preserves dirty status on a failed target node in graph storage. [preserve_target_dirty]
- An attribution coordinator resolves culprit files, validates critique explanations, and executes blame mutations on disk. [execute_file_blame_mutation]
- An attribution coordinator resolves target files, appends failure feedback, and marks dirty status on disk. [execute_file_failure_mutation]

### Woven Contracts

- When blaming a valid upstream dependency with a single-paragraph critique, the coordinator records feedback, marks the culprit dirty, attributes the source, and fails in-batch dependents. [assert_blame_target_is_upstream, assert_blame_target_receives_feedback, assert_single_paragraph_critique, assert_source_dependencies_clean, record_blame_feedback, mark_culprit_dirty, mark_source_attributed, propagate_in_batch_failure]
- When recording a task failure, the coordinator logs the failure diagnostic, preserves the target's dirty state, and fails dependent in-batch nodes. [record_failure_diagnostic, preserve_target_dirty, propagate_in_batch_failure]
- When blaming a culprit file, the coordinator validates critique formatting, executes build blame targets or mutates in-band metadata, and synchronizes files. [assert_single_paragraph_critique, execute_file_blame_mutation, src_metadata: [source_metadata_service]]
- When failing a file target, the coordinator appends failure diagnostics, marks dirty status, and synchronizes files. [execute_file_failure_mutation, src_metadata: [source_metadata_service]]

## Grounding

### Knowledge Provisions

- Defect blame gating validating upstream targets, feedback configuration, and single-paragraph critique formatting. [attribution_gating]
- Failure recording and cascading invalidation across in-batch dependent nodes. [failure_propagation]
- File-level blame attribution and failure mutation services. [file_attribution_service]

### Knowledge Requirements

- Verification of upstream dependency relationships and feedback reception enablement.
  - Deferred: Verified against graph storage and node configuration in implementation.
- Enforcement of single-paragraph critique structure with zero newline characters.
  - Deferred: Validated via string inspection in implementation.
- Persistence of feedback messages and node status mutations in graph storage.
  - Deferred: Delegated to DagStorage in implementation.
- In-band source metadata extraction and feedback formatting.
  - Grounded: [src_metadata: [source_metadata_service]]
