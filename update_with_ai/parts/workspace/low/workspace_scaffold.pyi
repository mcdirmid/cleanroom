# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:50:00Z
# CHANGE: Author workspace_scaffold low-level specification
# CODE_HASH: 59a612cfd721
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_scaffold."""

from typing import Optional, Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import cleanroom_files_ext
import workspace_roles


@singleton_type("agent_session")
class WorkspaceScaffolder(InTier[AgentSessionTier], Protocol):
    """Service scaffolding runner tools, metadata, instructions, and target skeletons."""

    @operation
    def deploy_runner_zipapps(self, bin_dir: str) -> None:
        """Packages executable runner tools into the specified bin directory.

        POSTCONDITIONS:
        - MUST create bin_dir if absent.
        - MUST package runner zipapps for get_work, check_files, submit, blame, feedback, and fail tools with executable permissions (0o755).
        - MUST remove stale coverage script if present in bin_dir.
        """
        ...

    @operation
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

        POSTCONDITIONS:
        - MUST write cleanroom_files_ext.ROLE_DESCRIPTOR_FILE in workspace_dir with 0o644 permissions.
        - MUST record role identity, directory scope, and optional model profile configuration without exposing host repository paths.
        """
        ...

    @operation
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_def: workspace_roles.RoleDefinition,
        dir_scope: str,
    ) -> None:
        """Synthesizes role-tailored AGENTS.md instructions in the workspace root.

        POSTCONDITIONS:
        - MUST write AGENTS.md in workspace_dir with 0o644 permissions.
        - MUST include boundary rules, contamination tripwires, terminal command restrictions, fail-stop protocols, and role-tailored workflow instructions.
        """
        ...

    @operation
    def create_missing_target_skeletons(
        self,
        workspace_dir: str,
        repo_root: str,
        dir_scope: str,
        role_def: workspace_roles.RoleDefinition,
    ) -> list[str]:
        """Creates starter skeletons for declared writable targets absent from disk.

        POSTCONDITIONS:
        - MUST generate starter skeleton files for missing targets matching role_def.writable_file_patterns.
        - MUST return relative paths of newly created skeleton files.
        """
        ...

    @operation
    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        """Writes text content to a destination file and applies exact permissions.

        POSTCONDITIONS:
        - MUST write content to dst with UTF-8 encoding.
        - WHEN readonly is true, MUST set permissions to 0o444.
        - WHEN executable is true and readonly is true, MUST set permissions to 0o555.
        - WHEN executable is true and readonly is false, MUST set permissions to 0o755.
        - WHEN neither is true, MUST set permissions to 0o644.
        """
        ...
