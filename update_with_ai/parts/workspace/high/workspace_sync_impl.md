<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:03Z
LAST_CHANGED: 2026-10-09T02:39:58Z
CHANGE: add contamination tripwire to AGENTS.md refresh specification
CODE_HASH: cc98fbd579a1
SPEC_QA_AUDIT: 2026-10-11T22:09:03Z
-->

# workspace_sync_impl implementation component

imports: agent_session, workspace_registry, src_metadata
implements: workspace_sync

## Purpose

The workspace_sync_impl implementation component realizes two-phase harvesting, inbound change pulling, system file refreshing, and blame buffer application.

Distributing work across disjoint workspaces introduces data synchronization races and the threat of overwriting verified code with stale payloads. The workspace_sync_impl implementation component provides guarded two-phase synchronization: in the first phase, source files are parsed and compared against recorded in-band hashes to detect modifications and merge collisions; in the second phase, validated changes and audit tags are written atomically to the canonical repository. Furthermore, blame feedback accumulated in local buffers is translated into in-band comment entries on culprit files, and system files are refreshed without disturbing working tree targets.

**Out of scope:** The workspace_sync_impl implementation component does not parse AST grammar, compute topological task schedules, or execute Bazel test rules; these are handled by other components.

**Delegated:** Role configuration and workspace directory lookups are delegated to workspace_registry; in-band source metadata extraction, audit stamping, code hashing, and feedback appending are delegated to src_metadata.

## Types and Behavior

When pulling changes from the canonical main repository into a role workspace, the workspace synchronizer:

- Identifies the files within the target directory scope, the declared role dependencies, and the stub role dependencies.

- Verifies that the workspace files matching stub role dependencies are valid read-only test stubs that contain no implementation details, and synthesizes read-only test stubs raising `NotImplementedError` from the companion specification files of the main repository when such a file is missing, is outdated against its companion specification, or contains leaked implementation code. Orphaned stubs whose companion specifications no longer exist in the main repository are deleted, and an implementation file matching a stub role dependency is never copied from the canonical main repository into the role workspace.

- Copies newer files from the main repository into the role workspace, enforcing read-only permissions on upstream dependencies and read-write permissions on role targets. An existing writable target is pulled from the main repository whenever the local target carries no uncommitted code modification and the main repository version differs in content or metadata, preserving pending local targets and deleted targets that await template regeneration.

- Preserves the uncommitted local modifications of a writable target, failing fast when an upstream modification conflicts with an active local change.

- Deletes the files within the role workspace scope that no longer exist in the canonical main repository.

When refreshing system files, the workspace synchronizer recopies the tool runners, project configurations, guide files, and linters from the main repository into the role workspace, regenerates `AGENTS.md` with its boundary rules, contamination tripwires, and fail-stop constraints without touching an in-scope source file, and validates that every stub role dependency file remains a read-only test stub.

When harvesting changes from a role workspace back to the canonical main repository, the workspace synchronizer performs two-phase synchronization:

- In the inspection phase, the synchronizer scans writable target files, computes current code hashes, extracts in-band metadata, and filters out unchanged files.

- In the validation phase, the synchronizer checks that main repository targets have not been modified concurrently by comparing main repository code hashes against the role workspace baseline.

- In the commit phase, the synchronizer copies validated files into the main repository and updates in-band timestamps. For auditor roles, the synchronizer stamps role audit attributes onto verified targets without changing target code bodies.

When flushing blame feedback, the workspace synchronizer reads the local blame buffer file `.cleanroom_blame_buffer.json`, extracts culprit file paths and critique messages, locates target files in the canonical main repository, appends unacted feedback entries with UTC timestamps to target headers in-place, and deletes the blame buffer file upon successful application.
