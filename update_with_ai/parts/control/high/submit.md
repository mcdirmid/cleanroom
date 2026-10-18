<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-09T22:20:00Z
CHANGE: Record change summary during clean status transition without appending dirty change message
CODE_HASH: 0433704faf59
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# submit interface component

imports: session, dag_storage, cleanroom_files_ext

## Purpose

The submit interface component defines submission gating, change documentation contracts, and clean node resolution for completed targets.

Premature or undocumented task completion introduces regressions into software builds. Without strict submission gating, agents can submit targets while verification checks are failing, leave code changes undocumented, or declare modifications on audit roles that must produce zero code changes. The submit interface component verifies that target checks pass, validates in-batch dependency cleanliness, enforces change summary contracts, and marks resolved targets clean in graph storage.

**Out of scope:** The submit interface component does not edit file contents, interact with git remotes, or schedule subsequent turns; these are handled by other components.

**Delegated:** Graph storage mutations are delegated to dag_storage; workspace file conventions are delegated to cleanroom_files_ext; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *submission outcome* reports the resolution of a target submission, indicating whether the submission was *accepted*, and providing an outcome *message*.

An agent session's *submission coordinator* validates and executes target submissions.

The submission coordinator:

- Verifies that verification checks for the target node are passing before allowing submission.

- Asserts that all in-batch dependencies of the target node are clean in the current turn before allowing dependent targets to submit.

- Enforces change documentation rules by requiring a change summary when workspace files were modified, forbidding a change summary when workspace files were unmodified, and forbidding change summaries when resolving auditor roles.

- Rejects submissions for targets with unresolved session feedback when no workspace files were modified, requiring file modifications to address feedback before submission can be accepted.

- Resolves accepted targets by marking the target node status as clean in graph storage with the change summary.

- Submits an auditor file target in a repository workspace by validating the target against test file submission prohibitions, discovering role context and directory scope from workspace manifest metadata when executed in an isolated workspace, and updating in-band audit tags in the canonical repository.

- Submits a producer file target in a repository workspace by validating the target against read-only permissions and directory scope patterns, discovering role context and directory scope from workspace manifest metadata when executed in an isolated workspace, requiring a change summary exactly when source code was modified, updating in-band change metadata in the canonical repository, and stripping ephemeral code hashes when committing files to the main repository.
