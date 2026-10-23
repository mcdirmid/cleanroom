# sync_impl implementation component

imports: session, role_registry, src_metadata, cleanroom_files_ext, provision
implements: sync

## Purpose

The sync_impl implementation component realizes two-phase harvesting, inbound change pulling, system file refreshing, and blame buffer application.

Distributing work across disjoint workspaces introduces data synchronization races and the threat of overwriting verified code with stale payloads. The sync_impl implementation component provides guarded two-phase synchronization: in the first phase, source files are parsed and compared against recorded in-band hashes to detect modifications and merge collisions; in the second phase, validated changes and audit tags are written atomically to the canonical repository. Furthermore, blame feedback accumulated in local buffers is translated into in-band comment entries on culprit files, and system files are refreshed without disturbing working tree targets.

**Out of scope:** The sync_impl implementation component does not parse AST grammar, compute topological task schedules, or execute test runners; these are handled by other components.

**Delegated:** Role configuration and workspace directory lookups are delegated to role_registry; in-band source metadata extraction, audit stamping, code hashing, and feedback appending are delegated to src_metadata; runner deployment, role guide generation, and test stub synchronization are delegated to provision; workspace file conventions are delegated to cleanroom_files_ext.

## Types and Behavior

When pulling changes from the canonical main repository into a role workspace, the workspace synchronizer:

- Identifies the files within the target directory scope, the declared role dependencies, and the stub role dependencies.

- Delegates test stub synchronization to workspace provisioning to verify that the workspace files matching stub role dependencies are valid read-only test stubs that contain no implementation details, synthesizing read-only test stubs raising `NotImplementedError` from companion specification files of the main repository when such a file is missing, is outdated against its companion specification, or contains leaked implementation code, and deleting orphaned stubs whose companion specifications no longer exist in the main repository.

- Copies newer files from the main repository into the role workspace, enforcing read-only permissions on upstream dependencies and read-write permissions on role targets, projecting metadata headers to expose only change, feedback, and code hash attributes while omitting lifecycle timestamps, and computing code body hashes on all writable files in the scope. An existing writable target is pulled from the main repository whenever the local target carries no uncommitted code modification and the main repository version differs in content or metadata, preserving pending local targets and deleted targets that await template regeneration.

- Preserves the uncommitted local modifications of a writable target, failing fast when an upstream modification conflicts with an active local change.

- Deletes the files within the role workspace scope that no longer exist in the canonical main repository.

When refreshing system files, the workspace synchronizer recopies project configurations, runtime support libraries (`./support/lib/`), and the role's assigned companion guide (`./guides/`) belonging exclusively to the active methodology binding from the main repository into the role workspace root without copying templates, unneeded configuration files (`cleanroom_roles.toml`, `pyright_spec.json`), redundant package directories, or unbound repository root directories, delegates runner packaging, role guide regeneration, and test stub synchronization to workspace provisioning without touching an in-scope source file, and validates that every stub role dependency file remains a read-only test stub.

When harvesting changes from a role workspace back to the canonical main repository, the workspace synchronizer performs two-phase synchronization:

- In the inspection phase, the synchronizer scans writable target files, computes current code hashes, extracts in-band metadata, and filters out unchanged files.

- In the validation phase, the synchronizer checks that main repository targets have not been modified concurrently by comparing main repository code hashes against the role workspace baseline.

- In the commit phase, the synchronizer copies validated files into the main repository, strips code hashes from the committed files, and updates in-band timestamps. For auditor roles, the synchronizer stamps role audit attributes onto verified targets without changing target code bodies.

When flushing blame feedback, the workspace synchronizer reads the local blame buffer file, extracts culprit file paths and critique messages, locates target files in the canonical main repository, appends unacted feedback entries with UTC timestamps to target headers in-place, and deletes the blame buffer file upon successful application.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-22T13:50:00Z
LAST_CHANGED: 2026-10-22T13:50:00Z
CHANGE: Restrict system file refreshing exclusively to bound methodology package assets
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
