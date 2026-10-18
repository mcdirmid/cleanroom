# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:45:00Z
# CHANGE: align AGENTS.md low spec with in-workspace file inspection and terminal command restrictions
# CODE_HASH: 578fc117e549
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for provision_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier
import cleanroom_files_ext
import provision
import role_registry
import scaffold
import stub
import src_metadata


@singleton_type("agent_session")
class WorkspaceProvisioner(
    provision.WorkspaceProvisioner,
    InTier[AgentSessionTier],
):
    """Realizes role workspace directory provisioning, permissions, and runner deployment.

    GROUNDING:
    - Realizes provision.WorkspaceProvisioner.commission by layering working tree
      creation with type-checking coverage, folder creation, missing target skeleton
      synthesis, permission-enforced file copying, zipapp runner packaging, role metadata
      serialization, and AGENTS.md formatting over role resolution and descriptor tracking
      delegated to role_registry.WorkspaceRegistry and scaffolding services delegated
      to scaffold.WorkspaceScaffolder.
    - Maintains no private backing collections or mutable state fields; each commissioning
      call composes a role_registry.WorkspaceDescriptor from the resolved
      role_registry.RoleDefinition and persists it through
      role_registry.WorkspaceRegistry.record_workspace.
    """

    @operation
    @override
    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> role_registry.WorkspaceDescriptor:
        """Commissions an isolated role workspace with permission boundaries.

        POSTCONDITIONS:
        - MUST create the role workspace working tree by copying workspace roots, project configurations, and build definitions.
        - MUST configure type-checking to cover the workspace without directory exclusions.
        - WHEN a declared writable target file does not yet exist on disk, MUST create a missing target skeleton.
        - WHEN reset is true, MUST clear stale pending work buffers in the workspace.
        - MUST write role configuration in cleanroom_files_ext.ROLE_DESCRIPTOR_FILE without exposing host repository paths.
        - WHEN model is specified, MUST record model execution parameters in cleanroom_files_ext.ROLE_DESCRIPTOR_FILE.

        GROUNDING:
        - Resolves the role_registry.RoleDefinition through
          role_registry.WorkspaceRegistry.resolve_role_definition and the destination
          working tree through role_registry.WorkspaceRegistry.compute_workspace_dir.
        - Creates the role workspace working tree by copying workspace roots, project
          configurations, and build definitions into the computed workspace directory and
          configures type-checking to cover the workspace without directory exclusions.
        - Creates a missing target skeleton for a declared writable target file matching
          role_registry.RoleDefinition.writable_file_patterns when that file does not
          yet exist on disk.
        - Creates bin and target package folders, copies files matching
          role_registry.RoleDefinition.writable_file_patterns with 0o644 permissions
          (projecting metadata headers through src_metadata.SourceMetadataCoordinator
          to expose only change and feedback fields with an ephemeral code hash
          computed via src_metadata.SourceMetadataCoordinator.compute_file_code_hash),
          copies files matching role_registry.RoleDefinition.readonly_file_patterns with
          0o444 permissions (projecting metadata headers through
          src_metadata.SourceMetadataCoordinator to expose only change and feedback fields),
          and synthesizes read-only test stubs raising NotImplementedError for every
          role_registry.RoleDefinition.stub_role_deps entry from companion specifications
          without copying real implementation files.
        - Packages executable bin zipapps whose __main__.py invokes the cleanroom_role_tool
          runner entrypoint, writes role metadata containing role identity, directory scope, and
          optional model profile parameters into cleanroom_files_ext.ROLE_DESCRIPTOR_FILE without
          recording host repository paths, and formats AGENTS.md instructions carrying
          role constraints, strict boundary rules, a contamination tripwire (distinguishing prohibited out-of-bounds files from permitted in-workspace code inspection), a terminal command execution
          restriction tripwire, instructions for acting on blame and feedback (warning that static checks do not verify runtime behavior or feedback resolution and requiring target change header inspection before auditor blame delivery), a fail-stop reporting protocol with unresolvable impasse handling via bin/fail,
          and tool execution instructions.
        - Composes the role_registry.WorkspaceDescriptor from the workspace directory,
          main repository root, directory scope, and resolved role_registry.RoleDefinition,
          then persists it through role_registry.WorkspaceRegistry.record_workspace.
        """
        ...

    @operation
    @override
    def copy_file_with_permissions(
        self,
        src: str,
        dst: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        """Copies a file and applies exact read-only, writable, or executable permissions.

        GROUNDING:
        - Realizes permission-enforced file copying (workspace_filesystem_mechanics) applying
          0o444, 0o644, 0o555, or 0o755 mode flags.
        """
        ...

    @operation
    @override
    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        """Writes text content to a destination file and applies exact permissions.

        GROUNDING:
        - Realizes permission-enforced file writing (workspace_filesystem_mechanics) applying
          0o444, 0o644, 0o555, or 0o755 mode flags.
        """
        ...

    @operation
    @override
    def deploy_runner_zipapps(self, bin_dir: str) -> None:
        """Packages executable runner tools into the specified bin directory.

        GROUNDING:
        - Packages self-contained executable runner zipapp wrappers into bin_dir with 0o755
          permissions (workspace_filesystem_mechanics).
        """
        ...

    @operation
    @override
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> None:
        """Synthesizes role-tailored AGENTS.md instructions in the workspace root.

        GROUNDING:
        - Resolves role definition and formats AGENTS.md instructions carrying role constraints,
          boundary rules, contamination tripwires, terminal command restrictions, fail-stop
          reporting protocols, and tool execution instructions (workspace_filesystem_mechanics).
        """
        ...

    @operation
    @override
    def sync_test_stubs(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Synchronizes read-only test stubs for stub role dependencies.

        GROUNDING:
        - Resolves role definition and delegates test stub synchronization to
          stub.WorkspaceStubSynthesizer.sync_all_stub_deps.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for workspace provisioning file writing routines.

    POSTCONDITIONS:
    - MUST write files with specific content and permissions.
    """
    ...

