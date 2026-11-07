# sync_impl implementation component

imports: session, role_registry, src_metadata, autofab_files_ext, provision
implements: sync

## Purpose

The sync_impl implementation component realizes two-phase harvesting, inbound change pulling, system file refreshing, and blame buffer application.

Distributing work across disjoint workspaces introduces data synchronization races and the threat of overwriting verified code with stale payloads. The sync_impl implementation component provides guarded two-phase synchronization: in the first phase, source files are parsed and compared against recorded in-band hashes to detect modifications and merge collisions; in the second phase, validated changes and audit tags are written atomically to the canonical repository. Furthermore, blame feedback accumulated in local buffers is translated into in-band comment entries on culprit files, and system files are refreshed without disturbing working tree targets.

**Out of scope:** The sync_impl implementation component does not parse AST grammar, compute topological task schedules, or execute test runners; these are handled by other components.

**Delegated:** Role configuration and workspace directory lookups are delegated to role_registry; in-band source metadata extraction, audit stamping, code hashing, and feedback appending are delegated to src_metadata; runner deployment, role guide generation, and test stub synchronization are delegated to provision; workspace file conventions are delegated to autofab_files_ext.

## Types and Behavior

When pulling changes from the canonical main repository into a role workspace, the workspace synchronizer:

- Identifies the files within the target directory scope, the declared role dependencies, and the stub role dependencies.

- Evaluates inbound changes against a pull manifest recorded in the role workspace state directory, pulling only files that have changed in the canonical main repository since the role workspace last pulled files from the canonical repository.

- Delegates test stub synchronization to workspace provisioning to verify that the workspace files matching stub role dependencies are valid read-only test stubs that contain no implementation details, synthesizing read-only test stubs raising `NotImplementedError` from companion specification files of the main repository when such a file is missing, is outdated against its companion specification, or contains leaked implementation code, and deleting orphaned stubs whose companion specifications no longer exist in the main repository.

- Copies newer files from the main repository into the role workspace, enforcing read-only permissions on upstream dependencies and read-write permissions on role targets, projecting metadata headers to expose only change, feedback, and code hash attributes while omitting lifecycle timestamps, and computing code body hashes on all writable files in the scope. It records the canonical source file hash and projected workspace file hash in the pull manifest upon copying. When a canonical file has not changed since the last pull, the synchronizer preserves the workspace file without copying over any local edits. When a canonical file has changed upstream since the last pull, read-only upstream dependencies and audited targets are always overwritten with the projected canonical version so auditor and consumer workspaces never retain stale upstream copies, whereas an existing writable target is pulled only when the local target carries no uncommitted code modification, preserving pending local targets and deleted targets that await template regeneration.

- Preserves the uncommitted local modifications of role targets, failing fast when an upstream code modification conflicts with an active local code change. An upstream change conflicts with a writable target only when the canonical code body differs from the workspace baseline and the workspace target carries uncommitted code modifications; upstream metadata-only updates and non-conflicting code pulls to clean targets proceed without conflict.

- Deletes the files within the role workspace scope that no longer exist in the canonical main repository when deleting missing files, preserving locally created and pending targets.

When refreshing system files, the workspace synchronizer recopies project configurations, runtime support libraries (`./support/lib/`), and the role's assigned companion guide (`./guides/`) belonging exclusively to the active methodology binding from the main repository into the role workspace root without copying templates, unneeded configuration files (`autofab_roles.toml`, `pyright_spec.json`), redundant package directories, or unbound repository root directories, stripping readme declaration attributes from refreshed pyproject.toml to prevent build backend failures, delegates runner packaging, role guide regeneration, and test stub synchronization to workspace provisioning without touching an in-scope source file, and validates that every stub role dependency file remains a read-only test stub.

When harvesting changes from a role workspace back to the canonical main repository, the workspace synchronizer performs two-phase synchronization:

- In the inspection phase, the synchronizer scans writable target files, computes current code hashes, extracts in-band metadata, and filters out unchanged files.

- In the validation phase, the synchronizer checks that main repository targets have not been modified concurrently by comparing main repository code hashes against the role workspace baseline.

- In the commit phase, the synchronizer copies validated files into the main repository, strips code hashes from the committed files, and updates in-band timestamps. For auditor roles, the synchronizer stamps role audit attributes onto verified targets without changing target code bodies.

When flushing blame feedback, the workspace synchronizer reads the local blame buffer file, extracts culprit file paths and critique messages, locates target files in the canonical main repository, appends unacted feedback entries with UTC timestamps to target headers in-place, and deletes the blame buffer file upon successful application.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-06T20:48:00Z
LAST_CHANGED: 2026-11-06T20:48:00Z
CHANGE: Always overwrite read-only upstream files on pull when canonical version changes in main
SPEC_QA_AUDIT: 2026-11-06T20:48:00Z
-->
