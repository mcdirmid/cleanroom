# pending_impl implementation component

imports: session, cleanroom_files_ext, dag_storage, src_metadata, role_registry
implements: pending

## Purpose

The pending_impl implementation component realizes pending work buffer persistence, target removal, and pending target dirtiness verification for Cleanroom role workspaces.

Operating command-line subagents in isolated workspaces requires durable file-based tracking of in-progress tasks to enforce task completion and prevent agents from acquiring new work while incomplete targets remain dirty. The pending_impl implementation component manages JSON-serialized pending target state in `.cleanroom_pending_work.json`, evaluates whether assigned targets remain dirty across local and canonical workspaces, and materializes starter templates via graph storage for missing targets.

**Out of scope:** The pending_impl implementation component does not discover ready queues across whole directory scopes or execute CLI commands; these are handled by other components.

**Delegated:** Session tier scoping is delegated to agent_session; workspace file conventions are delegated to cleanroom_files_ext; role definitions and file patterns are delegated to role_registry; in-band source metadata extraction is delegated to src_metadata; starter template materialization is delegated to dag_storage.

## Types and Behavior

The workspace pending manager manages pending work buffer state and dirty evaluation.

When managing pending target state:

- The pending manager reads target file paths from `.cleanroom_pending_work.json` in the designated workspace directory.

- The pending manager serializes assigned target paths into the pending work buffer file, overwriting existing records.

- The pending manager removes matching submitted or blamed target paths and unit stems from the pending work buffer file, preserving unmatched entries.

- The pending manager removes the pending work buffer file completely when cleared.

- The pending manager evaluates whether a pending target remains dirty by checking in-band source metadata across the workspace and main repository, evaluating canonical lifecycle timestamps from the main repository when available, evaluating star-role and feedback dependencies as implicit dependencies, verifying auditor role feedback targets against audit timestamps, and materializing starter templates via graph storage when missing.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:40:00Z
CHANGE: Define pending_impl implementation specification
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
