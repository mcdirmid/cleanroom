# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:50:00Z
# CHANGE: Define workspace_scaffold interface
# CODE_HASH: 41c5ba626d41
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_scaffold."""

from __future__ import annotations

from typing import List, Optional, Protocol
from . import workspace_roles


class WorkspaceScaffolder(Protocol):
    """Service scaffolding runner tools, metadata, instructions, and target skeletons."""

    def deploy_runner_zipapps(self, bin_dir: str) -> None: ...

    def write_role_metadata(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_feedback_chars: Optional[int] = None,
    ) -> None: ...

    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_def: workspace_roles.RoleDefinition,
        dir_scope: str,
    ) -> None: ...

    def create_missing_target_skeletons(
        self,
        workspace_dir: str,
        repo_root: str,
        dir_scope: str,
        role_def: workspace_roles.RoleDefinition,
    ) -> List[str]: ...

    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None: ...
