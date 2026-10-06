# control_submit_impl implementation component

imports: agent_session, dag_storage, agent_node_config, control_verification, agent_file_alias
implements: control_submit

## Purpose

The control_submit_impl implementation component realizes submission precondition validation, audit role restrictions, change message persistence, and graph status mutation.

Enforcing submission integrity prevents corrupting the dependency graph with broken or improperly documented artifacts. The control_submit_impl implementation component queries the verification evaluator to ensure checks have passed, evaluates whether the target role is marked as an auditor in role configuration, checks file modification status, and records change descriptions directly into graph storage.

**Out of scope:** The control_submit_impl implementation component does not execute compilers or run regression test suites; these are handled by other components.

**Delegated:** Verification status checks are delegated to control_verification. Graph storage mutations are delegated to dag_storage.

## Types and Behavior

The submission coordinator implements submission coordination for the session.

When submitting a target:

- The submission coordinator checks whether verification for the target node is passing, rejecting the submission with an explanatory error message when verification has failed or has not run.

- The submission coordinator checks each in-batch dependency of the target, rejecting the submission if any dependency remains unsubmitted or dirty.

- When resolving a target whose role configuration marks it as an auditor role, the submission coordinator rejects submissions that supply a non-empty change summary, reminding the caller that auditor roles must not submit change summaries.

- When workspace files were modified, the submission coordinator requires a non-empty change summary, rejecting submissions with an empty summary.

- When workspace files were not modified and the target is not an auditor role, the submission coordinator forbids non-empty change summaries, rejecting submissions that attempt to document changes when no modifications occurred.

- When all preconditions and change summary rules are satisfied, the submission coordinator marks the target node status as clean in graph storage, records the change message, and returns an accepted submission outcome.
