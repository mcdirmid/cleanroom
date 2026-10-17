# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: 1d6d0e4c1345
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for provision."""

from __future__ import annotations

from typing import Optional, Protocol
from . import role_registry


class WorkspaceProvisioner(Protocol):
    """Service commissioning and decommissioning isolated role workspaces."""

    # Contract: MUST commission an isolated role workspace with permission boundaries, runner tools, and AGENTS.md.
    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> role_registry.WorkspaceDescriptor: ...

    # Contract: MUST copy file applying exact read-only (0o444), writable (0o644), or executable (0o755/0o555) permissions.
    def copy_file_with_permissions(
        self,
        src: str,
        dst: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None: ...

    # Contract: MUST write content with exact permissions (0o444, 0o644, 0o755, or 0o555).
    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None: ...

    # Contract: MUST package executable runner zipapps into bin_dir with 0o755 permissions and remove stale coverage script.
    def deploy_runner_zipapps(self, bin_dir: str) -> None: ...

    # Contract: MUST synthesize role-tailored AGENTS.md instructions in the workspace root with 0o644 permissions.
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> None: ...

    # Contract: MUST synthesize read-only test stubs for stub role dependencies and delete orphaned stubs.
    def sync_test_stubs(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> int: ...
