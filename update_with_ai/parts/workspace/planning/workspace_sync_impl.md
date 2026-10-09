<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-08T03:34:00Z
CHANGE: update pull contract for writable target updates and deleted files
CODE_HASH: 0389263a3afe
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# workspace_sync_impl implementation component

imports: agent_session, workspace_registry, src_metadata
implements: workspace_sync

## Intent

Distributing work across disjoint workspaces introduces data synchronization races and the threat of overwriting verified code with stale payloads. The workspace_sync_impl implementation component provides guarded two-phase synchronization: in the first phase, source files are parsed and compared against recorded in-band hashes to detect modifications and merge collisions; in the second phase, validated changes and audit tags are written atomically to the canonical repository. Furthermore, blame feedback accumulated in local buffers is translated into in-band comment entries on culprit files, and system files are refreshed without disturbing working tree targets.

## Factored Contracts

### Contracts

- The workspace synchronizer copies newer upstream files from main to workspace setting 0o444 permissions on contracts and updating unmodified writable targets with 0o644 permissions while deleting missing files. [copy_upstream_files_with_perms]
- The workspace synchronizer synthesizes read-only test stubs from companion specifications, replaces leaked implementation code, and deletes orphaned stubs for stub role dependencies. [sync_stub_role_dependencies]
- The workspace synchronizer recopies tool runners, project configurations, guides, and AGENTS.md from main into the workspace without altering targets. [recopy_system_files_fast]
- The workspace synchronizer computes on-disk SHA-256 code hashes and extracts in-band metadata to identify modified files. [evaluate_target_file_modifications]
- The workspace synchronizer compares main repository code hashes against workspace baselines to detect concurrent edits. [compare_main_and_workspace_hashes]
- The workspace synchronizer copies validated target files into the canonical repository and updates in-band clean timestamps. [copy_validated_files_to_main]
- The workspace synchronizer calls stamp_audit and update_metadata on audited target files for auditor roles. [stamp_audit_on_targets]
- The workspace synchronizer parses .cleanroom_blame_buffer.json and appends unacted feedback to culprit files in main. [process_blame_buffer_entries]

### Woven Contracts

- When pulling updates from main, the synchronizer copies upstream files with read-only permissions, synchronizes stub role dependencies, and fast-refreshes system files. [copy_upstream_files_with_perms, sync_stub_role_dependencies, recopy_system_files_fast, workspace_sync: [pull_upstream_contracts, sync_stub_dependencies, refresh_system_files_into_workspace]]
- When harvesting changes, the synchronizer evaluates target modifications, detects concurrent edits against main, copies validated files, stamps audits, and flushes blame entries. [evaluate_target_file_modifications, compare_main_and_workspace_hashes, copy_validated_files_to_main, stamp_audit_on_targets, process_blame_buffer_entries, workspace_sync: [scan_modified_targets, validate_harvest_baselines, commit_harvested_files, stamp_auditor_role_audits, flush_blame_buffer_entries], src_metadata: [extract_metadata_disk, update_metadata_disk, stamp_audit_entry, append_feedback_entry]]

## Grounding

### Knowledge Provisions

- Inbound file transfer and permission-preserving update algorithms. [workspace_pull_algorithms]
- Two-phase validation, atomic harvest commit, and blame translation logic. [workspace_harvest_algorithms]

### Inherited Deferred Requirements

- Copying files across workspaces with permission preservation.
  - Grounded: [workspace_pull_algorithms]
- Two-phase conflict detection and atomic file replacement on disk.
  - Grounded: [workspace_harvest_algorithms]

### Knowledge Requirements

- Inspection and mutation of in-band source metadata headers.
  - Grounded: [src_metadata: [source_metadata_service]]
- Filesystem reading, writing, and permission manipulation.
  - Grounded: [workspace_pull_algorithms, workspace_harvest_algorithms]
