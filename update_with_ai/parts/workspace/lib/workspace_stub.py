# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:55:00Z
# CHANGE: Define workspace_stub interface protocol
# CODE_HASH: 6ced7557ed52
# COVERAGE_AUDIT: 2026-10-14T17:55:00Z
# QA_AUDIT: 2026-10-14T17:55:00Z
# --- END CLEANROOM METADATA ---

"""Low-level interface for workspace_stub."""

from __future__ import annotations

from typing import Dict, Optional, Protocol, Tuple
from support.lib.lifecycle import InTier
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
from . import workspace_registry


# Contract: WorkspaceStubSynthesizer protocol synthesizes and synchronizes read-only test stubs from specifications.
class WorkspaceStubSynthesizer(InTier[AgentSessionTier], Protocol):
    """Service synthesizing and synchronizing read-only test stubs from specifications."""

    # Contract: Generates read-only test stub from .pyi specification raising NotImplementedError with 0o444 permissions.
    def generate_readonly_test_stub(
        self,
        pyi_path: Optional[str],
        stem: str,
        out_path: str,
        dep_dir: str = "",
        part_map: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> None:
        """Generates a read-only test stub from a .pyi specification raising NotImplementedError."""
        ...

    # Contract: Synchronizes read-only test stubs for all stub_role_deps of a role, returning synced count.
    def sync_all_stub_deps(
        self,
        workspace_dir: str,
        main_root: str,
        role_def: workspace_registry.RoleDefinition,
        dir_scope: str = "staging",
    ) -> int:
        """Synchronizes read-only test stubs for all stub_role_deps of a role."""
        ...

    # Contract: Checks whether rel_path corresponds to any declared role in stub_role_deps.
    def is_stub_dep_file(
        self,
        rel_path: str,
        role_def: workspace_registry.RoleDefinition,
        repo_root: Optional[str] = None,
    ) -> bool:
        """Checks whether rel_path corresponds to any declared role in stub_role_deps."""
        ...

    # Contract: Checks whether file_path is already a valid cleanroom test stub.
    def is_valid_test_stub(self, file_path: str) -> bool:
        """Checks whether file_path is already a valid cleanroom test stub."""
        ...
