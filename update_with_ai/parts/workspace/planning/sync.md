<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-11T03:16:09Z
CHANGE: Declare synchronizer typing and enforce test stub integrity in refresh
CODE_HASH: e1f7f39a7146
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# sync interface component

## Intent

Operating across isolated role workspaces requires atomic data movement to prevent partial updates, stale contract reads, and merge conflicts. Unsynchronized upstream changes leave agents writing against obsolete specifications, while uncoordinated writes to canonical repositories risk clobbering concurrent user edits. The sync interface component establishes contracts for pulling upstream changes and refreshed system files into role workspaces, harvesting modified targets and attested audit stamps back to the main repository via two-phase validation, and flushing buffered blame feedback into culprit files in-band.

## Factored Contracts

### Typing

- A sync result record encapsulates a count of pulled files, a count of harvested files, a sequence of stamped audits, and a sequence of flushed blames.
- An agent session's workspace synchronizer transfers files and in-band metadata between canonical repositories and role workspaces.

### Contracts

- The workspace synchronizer pulls updated upstream contracts and source files from the canonical main repository into a role workspace, projecting in-band metadata to expose only change, feedback, and ephemeral code hash attributes on writable targets. [pull_upstream_contracts]
- The workspace synchronizer delegates test stub synchronization for stub role dependencies to workspace provisioning without copying implementation code. [sync_stub_dependencies]
- The workspace synchronizer refreshes non-parts system files from the canonical main repository into a role workspace, delegating runner deployment, role guide regeneration, and test stub synchronization, while scoping tool configurations to the role workspace boundaries. [refresh_system_files_into_workspace]
- The workspace synchronizer scans writable target files in a role workspace to identify modified content. [scan_modified_targets]
- The workspace synchronizer verifies that canonical main targets match workspace baseline hashes before committing harvested files. [validate_harvest_baselines]
- The workspace synchronizer copies validated target files from a role workspace into the canonical main repository, stripping ephemeral code hashes. [commit_harvested_files]
- The workspace synchronizer stamps role audits on verified targets in the canonical main repository for auditor roles. [stamp_auditor_role_audits]
- The workspace synchronizer flushes buffered blame feedback from the role workspace blame buffer into culprit files in the main repository. [flush_blame_buffer_entries]

### Woven Contracts

- When pulling updates from the canonical repository, the synchronizer copies newer upstream files into the role workspace, synchronizes stub dependencies, and enforces read-only permissions on contracts. [pull_upstream_contracts, sync_stub_dependencies]
- When refreshing system files, the synchronizer recopies project configurations and guides, refreshing system files and stub dependencies. [refresh_system_files_into_workspace]
- When harvesting changes, the synchronizer scans modified targets, validates baseline hashes against the main repository, commits validated files, stamps audits for auditor roles, and flushes buffered blame feedback. [scan_modified_targets, validate_harvest_baselines, commit_harvested_files, stamp_auditor_role_audits, flush_blame_buffer_entries]

## Grounding

### Knowledge Provisions

- Inbound upstream file pull and non-parts system refresh services. [workspace_pull_service]
- Two-phase atomic harvesting, audit attestation, and blame flushing capabilities. [workspace_harvest_service]

### Knowledge Requirements

- Layout conventions and state marker constants for Cleanroom workspace files.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
- Copying files across workspaces with permission preservation.
  - Deferred: Provided by workspace synchronizer implementation.
- Two-phase conflict detection and atomic file replacement on disk.
  - Deferred: Provided by workspace synchronizer implementation.
