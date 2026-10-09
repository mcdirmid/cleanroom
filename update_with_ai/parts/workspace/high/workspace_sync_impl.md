<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-09T02:39:58Z
CHANGE: add contamination tripwire to AGENTS.md refresh specification
CODE_HASH: d30619091086
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

- Identifies files within the target directory scope, declared role dependencies, and stub role dependencies.

- For files matching stub role dependencies, verifies that workspace files are valid read-only test stubs (`chmod 444`) containing no implementation details; if missing, outdated compared to upstream companion specifications, or containing leaked implementation code, synthesizes read-only test stubs with `raise NotImplementedError` from companion specification files (`low/*.pyi`) in the main repository, and deletes orphaned stubs whose companion specifications no longer exist in the main repository. Real implementation files matching stub role dependencies are never copied from the canonical main repository into the role workspace.

- Copies newer files from the main repository into the role workspace, enforcing read-only permissions (`chmod 444`) on upstream dependencies and read-write permissions (`chmod 644`) on role targets. For existing writable targets, pulls updates from the main repository whenever the local target has no uncommitted code modifications and the main repository version differs in content or metadata, preserving pending local targets and deleted targets awaiting template regeneration, and ensures standard write permissions (`chmod 644`).

- Preserves uncommitted local modifications on writable targets, failing fast if an upstream modification conflicts with an active local change.

- Deletes files within the role workspace scope that no longer exist in the canonical main repository.

When refreshing system files, the workspace synchronizer recopies tool runners, project configurations, guide files, and linters from the main repository into the role workspace, regenerates `AGENTS.md` with strict boundary rules, contamination tripwires, and fail-stop constraints without touching in-scope source files, and validates that all stub role dependency files remain read-only test stubs.

When harvesting changes from a role workspace back to the canonical main repository, the workspace synchronizer performs two-phase synchronization:

- In the inspection phase, the synchronizer scans writable target files, computes current code hashes, extracts in-band metadata, and filters out unchanged files.

- In the validation phase, the synchronizer checks that main repository targets have not been modified concurrently by comparing main repository code hashes against the role workspace baseline.

- In the commit phase, the synchronizer copies validated files into the main repository and updates in-band timestamps. For auditor roles, the synchronizer stamps role audit attributes onto verified targets without changing target code bodies.

When flushing blame feedback, the workspace synchronizer reads the local blame buffer file `.cleanroom_blame_buffer.json`, extracts culprit file paths and critique messages, locates target files in the canonical main repository, appends unacted feedback entries with UTC timestamps to target headers in-place, and deletes the blame buffer file upon successful application.
