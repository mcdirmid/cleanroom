<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 1f9ea8e57798
-->

# control_submit interface component

imports: agent_session, dag_storage, agent_node_config, control_verification, src_metadata

## Intent

The control_submit interface component defines contracts for submission gating, dependency cleanliness assertions, change documentation rules, and clean state mutation in graph storage.

Allowing untested code to enter the repository creates regressions. The submission coordinator acts as an authoritative checkpoint: verification must pass, in-batch dependencies must be clean, change summaries must accurately reflect file modifications, and auditor roles must not submit change summaries.

## Factored Contracts

### Typing

- A submission outcome reports an accepted status and an outcome message.
- A submission coordinator operates within the agent session lifecycle tier.

### Contracts

- A submission coordinator asserts that verification checks for the target are passing. [assert_verification_passed]
- A submission coordinator asserts that all in-batch dependencies of the target are clean. [assert_in_batch_dependencies_clean]
- A submission coordinator requires a change summary when workspace files were modified. [require_summary_when_modified]
- A submission coordinator forbids a change summary when workspace files were not modified. [forbid_summary_when_unmodified]
- A submission coordinator forbids a change summary when resolving an auditor role. [forbid_summary_for_auditors]
- A submission coordinator marks the target node status as clean in graph storage upon acceptance. [mark_node_clean]
- A submission coordinator records the change summary as a change message on the target node. [record_change_message]
- A submission coordinator rejects submission of test files in auditor roles. [reject_test_submission_for_auditors]
- A submission coordinator rejects submission of read-only targets or targets outside directory scope. [reject_invalid_producer_file_submission]
- A submission coordinator validates file modification hash against change summary presence. [validate_file_change_summary]
- A submission coordinator executes build submission targets or updates in-band source metadata directly. [execute_file_submission_mutation]

### Woven Contracts

- When submitting a target node with passing verification, clean in-batch dependencies, and valid change summary, the coordinator marks the target clean and records the change message. [assert_verification_passed, assert_in_batch_dependencies_clean, mark_node_clean, record_change_message]
- When submitting an auditor node, the coordinator rejects any submission containing a change summary. [forbid_summary_for_auditors]
- When submitting a file target, the coordinator validates role permissions, enforces change summary consistency, executes submission mutations, and stamps in-band metadata. [reject_test_submission_for_auditors, reject_invalid_producer_file_submission, validate_file_change_summary, execute_file_submission_mutation, src_metadata: [source_metadata_service]]

## Grounding

### Knowledge Provisions

- Submission gating enforcing verification success, in-batch cleanliness, and change summary rules. [submission_gating]
- Transition of submitted nodes to clean state with change message recording in graph storage. [clean_state_transition]
- File-level submission gating and in-band metadata stamping services. [file_submission_gating_service]

### Knowledge Requirements

- Evaluation of verification check results for candidate targets.
  - Deferred: Delegated to VerificationEvaluator in implementation.
- Inspection of auditor role declarations in role configuration.
  - Deferred: Queried from role configuration in implementation.
- Mutation of target node status to clean and persistence of change messages in graph storage.
  - Deferred: Delegated to DagStorage in implementation.
- Extraction and mutation of in-band source metadata.
  - Grounded: [src_metadata: [source_metadata_service]]
