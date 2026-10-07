# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: 66972724e0f5
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
    ) -> workspace_registry.WorkspaceDescriptor: ...

    def decommission(
        self,
        role_name_or_dir: str,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        force: bool = False,
    ) -> bool: ...
