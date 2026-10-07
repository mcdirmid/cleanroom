<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: 5dd783090a15
-->

# workspace_sync interface component

imports: agent_session, workspace_registry, src_metadata

## Intent

Operating across isolated role workspaces requires atomic data movement to prevent partial updates, stale contract reads, and merge conflicts. Unsynchronized upstream changes leave agents writing against obsolete specifications, while uncoordinated writes to canonical repositories risk clobbering concurrent user edits. The workspace_sync interface component establishes contracts for pulling upstream changes and refreshed system files into role workspaces, harvesting modified targets and attested audit stamps back to the main repository via two-phase validation, and flushing buffered blame feedback into culprit files in-band.

## Factored Contracts

### Typing

- A sync result record encapsulates a count of pulled files, a count of harvested files, a sequence of stamped audits, and a sequence of flushed blames.
- A workspace synchronizer operates within the agent session lifecycle tier.

### Contracts

- The workspace synchronizer pulls updated upstream contracts and source files from the canonical main repository into a role workspace. [pull_upstream_contracts]
- The workspace synchronizer refreshes non-parts system files from the canonical main repository into a role workspace. [refresh_system_files_into_workspace]
- The workspace synchronizer scans writable target files in a role workspace to identify modified content. [scan_modified_targets]
- The workspace synchronizer verifies that canonical main targets match workspace baseline hashes before committing harvested files. [validate_harvest_baselines]
- The workspace synchronizer copies validated target files from a role workspace into the canonical main repository. [commit_harvested_files]
- The workspace synchronizer stamps role audits on verified targets in the canonical main repository for auditor roles. [stamp_auditor_role_audits]
- The workspace synchronizer flushes buffered blame feedback from the role workspace blame buffer into culprit files in the main repository. [flush_blame_buffer_entries]

### Woven Contracts

- When pulling updates from the canonical repository, the synchronizer copies newer upstream files into the role workspace while enforcing read-only permissions on contracts. [pull_upstream_contracts, workspace_registry: [resolve_standard_role_definition]]
- When harvesting changes, the synchronizer scans modified targets, validates baseline hashes against the main repository, commits validated files, stamps audits for auditor roles, and flushes buffered blame feedback. [scan_modified_targets, validate_harvest_baselines, commit_harvested_files, stamp_auditor_role_audits, flush_blame_buffer_entries, src_metadata: [extract_metadata_disk, update_metadata_disk, stamp_audit_entry, append_feedback_entry]]

## Grounding

### Knowledge Provisions

- Inbound upstream file pull and non-parts system refresh services. [workspace_pull_service]
- Two-phase atomic harvesting, audit attestation, and blame flushing capabilities. [workspace_harvest_service]

### Knowledge Requirements

- Copying files across workspaces with permission preservation.
  - Deferred: Provided by workspace synchronizer implementation.
- Two-phase conflict detection and atomic file replacement on disk.
  - Deferred: Provided by workspace synchronizer implementation.
- In-band comment header manipulation and blame appending.
  - Grounded: [src_metadata: [source_metadata_service]]
