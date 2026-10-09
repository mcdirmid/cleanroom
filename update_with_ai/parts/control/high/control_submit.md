<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-09T22:20:00Z
CHANGE: Record change summary during clean status transition without appending dirty change message
CODE_HASH: 0d9883b55b84
-->

# control_submit interface component

imports: agent_session, dag_storage, agent_node_config, control_verification, src_metadata

## Purpose

The control_submit interface component defines submission gating, change documentation contracts, and clean node resolution for completed targets.

Premature or undocumented task completion introduces regressions into software builds. Without strict submission gating, agents can submit targets while verification checks are failing, leave code changes undocumented, or declare modifications on audit roles that must produce zero code changes. The control_submit interface component verifies that target checks pass, validates in-batch dependency cleanliness, enforces change summary contracts, and marks resolved targets clean in graph storage.

**Out of scope:** The control_submit interface component does not edit file contents, interact with git remotes, or schedule subsequent turns; these are handled by other components.

**Delegated:** Verification status checks are delegated to control_verification; in-band source metadata extraction and header updates are delegated to src_metadata; graph storage mutations are delegated to dag_storage.

## Types and Behavior

A *submission outcome* reports the resolution of a target submission, indicating whether the submission was *accepted*, and providing an outcome *message*.

A session's *submission coordinator* validates and executes target submissions.

The submission coordinator:

- Verifies that verification checks for the target node are passing before allowing submission.

- Asserts that all in-batch dependencies of the target node are clean in the current turn before allowing dependent targets to submit.

- Enforces change documentation rules by requiring a change summary when workspace files were modified, forbidding a change summary when workspace files were unmodified, and forbidding change summaries when resolving auditor roles.

- Resolves accepted targets by marking the target node status as clean in graph storage with the change summary.

- Submits file targets in repository workspaces, validating auditor targets against test file submission prohibitions, validating producer targets against read-only permissions and directory scope patterns, requiring change summaries exclusively when source code was modified, and updating in-band audit tags and change metadata in canonical repositories.
