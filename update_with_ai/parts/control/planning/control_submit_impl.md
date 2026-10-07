<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 36c776b5e376
-->

# control_submit_impl implementation component

imports: agent_session, dag_storage, agent_node_config, control_verification, agent_file_alias, src_metadata
implements: control_submit

## Intent

The control_submit_impl implementation component provides concrete validation logic for submission gating, role config inspection for auditor flags, graph storage updates, and diagnostic rejection messaging.

The implementation evaluates verification results from the verification evaluator, inspects file modification flags, examines role configuration to identify auditor roles, and commits change records into graph storage.

## Factored Contracts

### Contracts

- The submission coordinator queries the verification evaluator for the target's verification status. [query_target_verification]
- The submission coordinator checks whether the target role is declared as an auditor in role configuration. [check_auditor_role]
- The submission coordinator inspects whether workspace files were modified during the turn. [inspect_file_modifications]
- The submission coordinator constructs an error message when verification has failed. [format_verification_error]
- The submission coordinator constructs an error message when in-batch dependencies remain unsubmitted. [format_dependency_error]
- The submission coordinator constructs an error message when change summary requirements are violated. [format_summary_error]
- The submission coordinator invokes graph storage to update node status to clean. [update_storage_clean]
- The submission coordinator invokes graph storage to append the change message. [append_storage_change]
- The submission coordinator validates file targets against auditor and producer file submission constraints. [validate_file_target_submission_constraints]
- The submission coordinator executes build submission targets or updates in-band file metadata headers. [execute_file_target_submission_execution]

### Woven Contracts

- When verification fails or has not run, the coordinator rejects the submission with a verification error. [query_target_verification, format_verification_error]
- When an in-batch dependency is not clean, the coordinator rejects the submission with a dependency error. [format_dependency_error, control_submit: [assert_in_batch_dependencies_clean]]
- When change summary rules fail based on file modifications or auditor role status, the coordinator rejects the submission with a summary error. [check_auditor_role, inspect_file_modifications, format_summary_error, control_submit: [require_summary_when_modified, forbid_summary_when_unmodified, forbid_summary_for_auditors]]
- When all checks succeed, the coordinator updates node status to clean and appends the change message in graph storage. [update_storage_clean, append_storage_change, control_submit: [mark_node_clean, record_change_message]]
- When submitting a file target, the coordinator validates submission constraints, executes submission targets, and updates in-band headers. [validate_file_target_submission_constraints, execute_file_target_submission_execution, control_submit: [reject_test_submission_for_auditors, reject_invalid_producer_file_submission, validate_file_change_summary, execute_file_submission_mutation], src_metadata: [source_metadata_service]]

## Grounding

### Knowledge Provisions

- Submission gating enforcing verification success, in-batch cleanliness, and change summary rules. [submission_gating]
- Transition of submitted nodes to clean state with change message recording in graph storage. [clean_state_transition]
- File-level target submission and metadata stamping logic. [file_submission_logic]

### Inherited Deferred Requirements

- Evaluation of verification check results for candidate targets.
  - Grounded: [control_verification: [verification_evaluation]]
- Inspection of auditor role declarations in role configuration.
  - Grounded: [agent_node_config: [node_configuration_service]]
- Mutation of target node status to clean and persistence of change messages in graph storage.
  - Grounded: [dag_storage: [dag_storage_service], clean_state_transition]

### Knowledge Requirements

- Inspection of session file modification state to validate change summary requirements.
  - Grounded: [caller input, submission_gating]
- Source metadata header extraction and mutation on disk.
  - Grounded: [src_metadata: [source_metadata_service]]
