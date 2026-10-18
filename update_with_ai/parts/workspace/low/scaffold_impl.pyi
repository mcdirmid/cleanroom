# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:50:00Z
# CHANGE: Author scaffold_impl low-level specification
# CODE_HASH: 6d495bfa9be4
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for scaffold_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier
import cleanroom_files_ext
import roles
import scaffold


@singleton_type("agent_session")
class WorkspaceScaffolder(
    scaffold.WorkspaceScaffolder,
    InTier[AgentSessionTier],
):
    """Realizes runner zipapp packaging, role metadata, guide synthesis, and starter skeletons.

    GROUNDING:
    - Realizes scaffold.WorkspaceScaffolder by packaging zipapps, serializing
      metadata into cleanroom_files_ext.ROLE_DESCRIPTOR_FILE, formatting AGENTS.md instructions,
      and generating starter skeletons from companion specifications (workspace_scaffold_mechanics).
    """

    @operation
    @override
    def deploy_runner_zipapps(self, bin_dir: str) -> None:
        """Packages executable runner tools into the specified bin directory.

        GROUNDING:
        - Packages self-contained executable runner zipapp wrappers into bin_dir with 0o755
          permissions (workspace_scaffold_mechanics).
        """
        ...

    @operation
    @override
    def write_role_metadata(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_feedback_chars: Optional[int] = None,
    ) -> None:
        """Writes role configuration metadata in the workspace root.

        GROUNDING:
        - Writes cleanroom_files_ext.ROLE_DESCRIPTOR_FILE with role identity, directory scope,
          and optional model parameters with 0o644 permissions (workspace_scaffold_mechanics).
        """
        ...

    @operation
    @override
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_def: roles.RoleDefinition,
        dir_scope: str,
    ) -> None:
        """Synthesizes role-tailored AGENTS.md instructions in the workspace root.

        GROUNDING:
        - Formats AGENTS.md instructions carrying role constraints, boundary rules, contamination
          tripwires, terminal command restrictions, fail-stop reporting protocols, and tool execution
          instructions with 0o644 permissions (workspace_scaffold_mechanics).
        """
        ...

    @operation
    @override
    def create_missing_target_skeletons(
        self,
        workspace_dir: str,
        repo_root: str,
        dir_scope: str,
        role_def: roles.RoleDefinition,
    ) -> list[str]:
        """Creates starter skeletons for declared writable targets absent from disk.

        GROUNDING:
        - Inspects declared units and generates starter skeleton code from companion specifications
          or templates (workspace_scaffold_mechanics).
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
        - Realizes permission-enforced file writing (workspace_scaffold_mechanics) applying
          0o444, 0o644, 0o555, or 0o755 mode flags.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for workspace role metadata writing.

    POSTCONDITIONS:
    - MUST write role configuration metadata with 0o644 permissions.
    """
    ...

