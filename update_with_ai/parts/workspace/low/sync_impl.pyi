"""Low-level implementation specification for sync_impl."""

from typing import Sequence
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import sync
import role_registry
import provision
import src_metadata
import cleanroom_files_ext


@singleton_type("agent_session")
class WorkspaceSynchronizer(sync.WorkspaceSynchronizer):
    """Realizes two-phase harvesting, inbound pulling, system file refresh, and blame flushing.

    GROUNDING:
    - Realizes permission-preserving inbound pulls and system file refresh
      (workspace_pull_algorithms) through newer-file copying with 0o444 contract
      permissions, 0o644 writable target updates, and missing-file deletion.
    - Delegates runner deployment, role guide generation, test stub synchronization,
      and permission-enforced file copying to provision.WorkspaceProvisioner.
    - Realizes two-phase conflict detection and atomic file replacement on disk
      (workspace_harvest_algorithms) through temporary staging files.
    - Delegates in-band metadata handling to src_metadata.SourceMetadataCoordinator, using
      compute_file_code_hash, extract_metadata, update_metadata, stamp_audit, and
      append_feedback.
    - Accesses and mutates the role workspace blame buffer designated by
      cleanroom_files_ext.BLAME_BUFFER_FILE and accumulates the pulled, harvested,
      stamped audit, and flushed blame values into the sync.SyncResult record.
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
        - Copies newer upstream files from main into the role workspace, projecting metadata
          headers to retain only change and feedback fields, stamping ephemeral code hashes
          on writable targets, setting 0o444 on read-only contracts, updating writable
          targets that are not modified with 0o644, and deleting files absent from main,
          using provision.WorkspaceProvisioner.copy_file_with_permissions and
          provision.WorkspaceProvisioner.write_file_with_permissions.
        - Determines writable target modification state against ephemeral code hashes through
          src_metadata.SourceMetadataCoordinator.is_code_modified and
          src_metadata.SourceMetadataCoordinator.compute_file_code_hash.
        - Delegates test stub synchronization to
          provision.WorkspaceProvisioner.sync_test_stubs.
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
          through role_registry.WorkspaceRegistry.discover_repository_root and
          role_registry.WorkspaceDescriptor before recopying system files from that root.
        - Recopies project configurations, runtime support libraries (./support/lib/), and the assigned companion guide (./guides/) belonging exclusively to the active methodology binding from main into the workspace root
          using provision.WorkspaceProvisioner.copy_file_with_permissions without copying templates, unneeded configuration files, or unbound repository root directories and without altering writable targets.
        - Delegates runner packaging to provision.WorkspaceProvisioner.deploy_runner_zipapps,
          role guide regeneration to provision.WorkspaceProvisioner.write_role_agents_guide,
          and test stub synchronization to provision.WorkspaceProvisioner.sync_test_stubs.
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
    ) -> sync.SyncResult:
        """Harvests modified targets, stamps audits, and flushes blame back to main.

        GROUNDING:
        - Identifies modified targets in the first phase by computing on-disk code hashes
          through src_metadata.SourceMetadataCoordinator.compute_file_code_hash and
          extracting in-band metadata through
          src_metadata.SourceMetadataCoordinator.extract_metadata.
        - Detects concurrent edits by comparing main repository code hashes against recorded
          workspace baseline hashes before committing.
        - Commits validated target files into the canonical repository, stripping ephemeral
          code hashes and replacing them atomically through temporary staging files and
          refreshing in-band clean timestamps through
          src_metadata.SourceMetadataCoordinator.update_metadata.
        - Stamps auditor role attestations on audited targets through
          src_metadata.SourceMetadataCoordinator.stamp_audit.
        - Flushes buffered blame feedback by appending unacted entries through
          src_metadata.SourceMetadataCoordinator.append_feedback.
        - Populates the sync.SyncResult pulled and harvested counts and stamped
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T13:50:00Z
# LAST_CHANGED: 2026-10-22T13:50:00Z
# CHANGE: Restrict system file refreshing exclusively to bound methodology package assets
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
