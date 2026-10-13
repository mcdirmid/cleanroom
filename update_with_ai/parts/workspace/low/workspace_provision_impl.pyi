# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-12T23:35:00Z
# CHANGE: align AGENTS.md low spec with command execution tripwire and impasse fail protocol
# CODE_HASH: 1f706f0f0a66
# SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_provision_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import cleanroom_files_ext
import workspace_provision
import workspace_registry


@singleton_type("agent_session")
class WorkspaceProvisioner(
    workspace_provision.WorkspaceProvisioner,
    InTier[AgentSessionTier],
):
    """Realizes role workspace directory provisioning, permissions, and runner deployment.

    GROUNDING:
    - Realizes workspace_provision.WorkspaceProvisioner.commission by layering working tree
      creation with type-checking coverage, folder creation, missing target skeleton
      synthesis, permission-enforced file copying, zipapp runner packaging, role metadata
      serialization, and AGENTS.md formatting over role resolution and descriptor tracking
      delegated to workspace_registry.WorkspaceRegistry.
    - Maintains no private backing collections or mutable state fields; each commissioning
      call composes a workspace_registry.WorkspaceDescriptor from the resolved
      workspace_registry.RoleDefinition and persists it through
      workspace_registry.WorkspaceRegistry.record_workspace.
    """

    @operation
    @override
    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> workspace_registry.WorkspaceDescriptor:
        """Commissions an isolated role workspace with permission boundaries.

        POSTCONDITIONS:
        - MUST create the role workspace working tree by copying workspace roots, project configurations, and build definitions.
        - MUST configure type-checking to cover the workspace without directory exclusions.
        - WHEN a declared writable target file does not yet exist on disk, MUST create a missing target skeleton.

        GROUNDING:
        - Resolves the workspace_registry.RoleDefinition through
          workspace_registry.WorkspaceRegistry.resolve_role_definition and the destination
          working tree through workspace_registry.WorkspaceRegistry.compute_workspace_dir.
        - Creates the role workspace working tree by copying workspace roots, project
          configurations, and build definitions into the computed workspace directory and
          configures type-checking to cover the workspace without directory exclusions.
        - Creates a missing target skeleton for a declared writable target file matching
          workspace_registry.RoleDefinition.writable_file_patterns when that file does not
          yet exist on disk.
        - Creates bin and target package folders, copies files matching
          workspace_registry.RoleDefinition.writable_file_patterns with 0o644 permissions,
          copies files matching workspace_registry.RoleDefinition.readonly_file_patterns with
          0o444 permissions, and synthesizes read-only test stubs raising NotImplementedError
          for every workspace_registry.RoleDefinition.stub_role_deps entry from companion
          specifications without copying real implementation files.
        - Packages executable bin zipapps whose __main__.py invokes the cleanroom_role_tool
          runner entrypoint, writes role metadata containing the main repository root and
          directory scope into cleanroom_files_ext.ROLE_DESCRIPTOR_FILE, and formats AGENTS.md instructions carrying
          role constraints, strict boundary rules, a contamination tripwire, a command execution
          restriction tripwire, a fail-stop reporting protocol with unresolvable impasse handling via bin/fail,
          and tool execution instructions.
        - Composes the workspace_registry.WorkspaceDescriptor from the workspace directory,
          main repository root, directory scope, and resolved workspace_registry.RoleDefinition,
          then persists it through workspace_registry.WorkspaceRegistry.record_workspace.
        """
        ...
