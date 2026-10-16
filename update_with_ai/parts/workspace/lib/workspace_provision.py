# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: 1d6d0e4c1345
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_provision."""

from __future__ import annotations

from typing import Optional, Protocol
from . import workspace_registry


class WorkspaceProvisioner(Protocol):
    """Service commissioning and decommissioning isolated role workspaces."""

    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> workspace_registry.WorkspaceDescriptor: ...

    def copy_file_with_permissions(
        self,
        src: str,
        dst: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None: ...

    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None: ...

    def deploy_runner_zipapps(self, bin_dir: str) -> None: ...

    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> None: ...

    def sync_test_stubs(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> int: ...
