# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-12T23:35:00Z
# CHANGE: align AGENTS.md refresh low spec with command execution tripwire and impasse fail protocol
# CODE_HASH: ac14df123a69
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_sync_impl."""

from typing import Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_sync
import workspace_registry
import src_metadata
import cleanroom_files_ext


@singleton_type("agent_session")
class WorkspaceSynchronizer(
    workspace_sync.WorkspaceSynchronizer,
    InTier[AgentSessionTier],
):
    """Realizes two-phase harvesting, inbound pulling, system file refresh, and blame flushing.

    GROUNDING:
    - Realizes permission-preserving inbound pulls and system file refresh
      (workspace_pull_algorithms) through newer-file copying with 0o444 contract
      permissions, 0o644 writable target updates, and missing-file deletion.
    - Realizes two-phase conflict detection and atomic file replacement on disk
      (workspace_harvest_algorithms) through temporary staging files.
    - Delegates in-band metadata handling to src_metadata.SourceMetadataCoordinator, using
      compute_file_code_hash, extract_metadata, update_metadata, stamp_audit, and
      append_feedback.
    - Accesses and mutates the role workspace blame buffer designated by
      cleanroom_files_ext.BLAME_BUFFER_FILE and accumulates the pulled, harvested,
      stamped audit, and flushed blame values into the workspace_sync.SyncResult record.
    """

    @operation
    @override
    def pull(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int:
        """Pulls updated upstream contracts and source files into role workspace.

        GROUNDING:
        - Copies newer upstream files from main into the role workspace, setting 0o444 on
          read-only contracts, updating writable targets that are not modified with 0o644,
          and deleting files absent from main.
        - Determines writable target modification state through
          src_metadata.SourceMetadataCoordinator.is_code_modified.
        - Synthesizes read-only test stubs from companion specifications for stub role
          dependencies, replaces leaked implementation code, and deletes orphaned stubs.
        """
        ...

    @operation
    @override
    def refresh_system_files(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int:
        """Refreshes non-parts system files into role workspace.

        GROUNDING:
        - Resolves the canonical repository root and role context of the synchronized workspace
          through workspace_registry.WorkspaceRegistry.discover_repository_root and
          workspace_registry.WorkspaceDescriptor before recopying system files from that root.
        - Recopies tool runners, project configurations, guides, and AGENTS.md carrying
          boundary rules, contamination tripwires, command execution restrictions, and
          fail-stop/impasse constraints from main into the workspace without altering writable targets.
        - Re-asserts read-only test stub integrity for stub role dependencies by replacing
          leaked implementation code and restoring read-only permissions on stub targets.
        """
        ...

    @operation
    @override
    def harvest(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
    ) -> workspace_sync.SyncResult:
        """Harvests modified targets, stamps audits, and flushes blame back to main.

        GROUNDING:
        - Identifies modified targets in the first phase by computing on-disk code hashes
          through src_metadata.SourceMetadataCoordinator.compute_file_code_hash and
          extracting in-band metadata through
          src_metadata.SourceMetadataCoordinator.extract_metadata.
        - Detects concurrent edits by comparing main repository code hashes against recorded
          workspace baseline hashes before committing.
        - Commits validated target files into the canonical repository, replacing them
          atomically through temporary staging files and refreshing in-band clean timestamps
          through src_metadata.SourceMetadataCoordinator.update_metadata.
        - Stamps auditor role attestations on audited targets through
          src_metadata.SourceMetadataCoordinator.stamp_audit.
        - Flushes buffered blame feedback by appending unacted entries through
          src_metadata.SourceMetadataCoordinator.append_feedback.
        - Populates the workspace_sync.SyncResult pulled and harvested counts and stamped
          audit and flushed blame path sequences from the run.
        """
        ...

    @operation
    @override
    def flush_blame_buffer(
        self, workspace_dir: str, main_root: str
    ) -> Sequence[str]:
        """Flushes buffered blame feedback entries from workspace into main.

        GROUNDING:
        - Parses cleanroom_files_ext.BLAME_BUFFER_FILE from the role workspace and appends unacted
          feedback to culprit files in the canonical repository through
          src_metadata.SourceMetadataCoordinator.append_feedback.
        - Deletes the consumed blame buffer file after every buffered entry is applied and
          returns the culprit paths receiving feedback.
        """
        ...
