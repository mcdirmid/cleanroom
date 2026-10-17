<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-09T22:20:00Z
CHANGE: Record change summary during clean status transition without appending dirty change message
CODE_HASH: 3f376f45cb7a
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# submit_impl implementation component

imports: session, dag_storage, node_config, verification, file_alias, src_metadata
implements: submit

## Purpose

The submit_impl implementation component realizes submission precondition validation, audit role restrictions, change summary persistence, and graph status mutation.

Enforcing submission integrity prevents corrupting the dependency graph with broken or improperly documented artifacts. The submit_impl implementation component queries the verification evaluator to ensure checks have passed, evaluates whether the target role is marked as an auditor in role configuration, checks file modification status, and records change descriptions directly into graph storage.

**Out of scope:** The submit_impl implementation component does not execute compilers or run regression test suites; these are handled by other components.

**Delegated:** Verification status checks are delegated to verification; in-band source metadata extraction and header updates are delegated to src_metadata; graph storage mutations are delegated to dag_storage.

## Types and Behavior

The submission coordinator implements submission coordination for an agent session.

When submitting a target:

- The submission coordinator checks whether verification for the target node is passing, rejecting the submission with an explanatory error message when verification has failed or has not run.

- The submission coordinator checks each in-batch dependency of the target, rejecting the submission when any dependency remains unsubmitted or dirty.

- The submission coordinator rejects a non-empty change summary when the role configuration marks the resolved target as an auditor role, reminding the caller that auditor roles must not submit change summaries.

- The submission coordinator requires a non-empty change summary when workspace files were modified, rejecting submissions with an empty summary.

- The submission coordinator forbids a non-empty change summary when workspace files were unmodified and the target is not an auditor role, rejecting submissions that document changes when no modification occurred.

- The submission coordinator rejects submissions when session feedback is present and no workspace files were modified, instructing that workspace files must be modified to address feedback before submitting, or that fail must be called if the feedback cannot be resolved.

- The submission coordinator marks the target node status as clean in graph storage with the change summary and returns an accepted submission outcome once every precondition and change summary rule is satisfied.

- The submission coordinator formats submission outcomes and in-batch dependency errors using user-facing file aliases rather than raw graph node addresses.

When submitting a file target:

- The submission coordinator resolves the target file path and unit name against the local workspace and canonical repository roots.

- The submission coordinator submits an auditor role by rejecting test files, resolving the audited implementation and companion test files, stamping in-band audit tags directly in the canonical repository, constructing an audit outcome message formatted with the audit tag, and synchronizing the updated files back to the role workspace.

- The submission coordinator submits a producer role by verifying write permissions and active directory scope patterns, requiring a change summary exactly when code was modified, updating in-band change metadata directly in the canonical repository, constructing an outcome message formatted with a change summary or clean status, and synchronizing the updated files back to the role workspace.
