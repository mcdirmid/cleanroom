<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-09T22:20:00Z
CHANGE: Record change summary during clean status transition without appending dirty change message
CODE_HASH: b2dd759fc96f
-->

# control_submit_impl implementation component

imports: agent_session, dag_storage, agent_node_config, control_verification, agent_file_alias, src_metadata
implements: control_submit

## Purpose

The control_submit_impl implementation component realizes submission precondition validation, audit role restrictions, change summary persistence, and graph status mutation.

Enforcing submission integrity prevents corrupting the dependency graph with broken or improperly documented artifacts. The control_submit_impl implementation component queries the verification evaluator to ensure checks have passed, evaluates whether the target role is marked as an auditor in role configuration, checks file modification status, and records change descriptions directly into graph storage.

**Out of scope:** The control_submit_impl implementation component does not execute compilers or run regression test suites; these are handled by other components.

**Delegated:** Verification status checks are delegated to control_verification; in-band source metadata extraction and header updates are delegated to src_metadata; graph storage mutations are delegated to dag_storage.

## Types and Behavior

The submission coordinator implements submission coordination for the session.

When submitting a target:

- The submission coordinator checks whether verification for the target node is passing, rejecting the submission with an explanatory error message when verification has failed or has not run.

- The submission coordinator checks each in-batch dependency of the target, rejecting the submission if any dependency remains unsubmitted or dirty.

- When resolving a target whose role configuration marks it as an auditor role, the submission coordinator rejects submissions that supply a non-empty change summary, reminding the caller that auditor roles must not submit change summaries.

- When workspace files were modified, the submission coordinator requires a non-empty change summary, rejecting submissions with an empty summary.

- When workspace files were not modified and the target is not an auditor role, the submission coordinator forbids non-empty change summaries, rejecting submissions that attempt to document changes when no modifications occurred.

- When all preconditions and change summary rules are satisfied, the submission coordinator marks the target node status as clean in graph storage with the change summary and returns an accepted submission outcome.

When submitting a file target:

- The submission coordinator resolves the target file path and unit name against the local workspace and canonical repository roots.

- When submitting in an auditor role, the submission coordinator rejects test files, resolves audited implementation and companion test files, stamps in-band audit tags directly in the canonical repository, constructs an audit outcome message formatted with the audit tag, and synchronizes updated files back to the role workspace.

- When submitting in a producer role, the submission coordinator verifies write permissions and active directory scope patterns, validates that a change summary was provided if and only if code was modified, updates in-band change metadata directly in the canonical repository, constructs an outcome message formatted with a change summary or clean status, and synchronizes updated files back to the role workspace.
