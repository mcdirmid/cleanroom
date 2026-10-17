# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:55:00Z
# CHANGE: Define workspace_stub low-level interface specification
# CODE_HASH: 23d7da7e168c
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_stub."""

from typing import Dict, Optional, Protocol, Tuple
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_registry


@singleton_type("agent_session")
class WorkspaceStubSynthesizer(InTier[AgentSessionTier], Protocol):
    """Service synthesizing and synchronizing read-only test stubs from specifications."""

    @operation
    def generate_readonly_test_stub(
        self,
        pyi_path: Optional[str],
        stem: str,
        out_path: str,
        dep_dir: str = "",
        part_map: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> None:
        """Generates a read-only test stub from a .pyi specification raising NotImplementedError.

        POSTCONDITIONS:
        - MUST parse pyi_path into an AST and extract class, method, and function signatures.
        - MUST write a read-only test stub file at out_path with permissions set to 0o444.
        - MUST replace function and method bodies with NotImplementedError.
        - MUST rewrite imports and inject missing interface method signatures from upstream specifications.
        """
        ...

    @operation
    def sync_all_stub_deps(
        self,
        workspace_dir: str,
        main_root: str,
        role_def: workspace_registry.RoleDefinition,
        dir_scope: str = "staging",
    ) -> int:
        """Synchronizes read-only test stubs for all stub_role_deps of a role.

        POSTCONDITIONS:
        - WHEN role_def declares stub_role_deps, MUST generate or update test stubs for out-of-date or missing specifications.
        - MUST return the count of synchronized test stub files.
        """
        ...

    @operation
    def is_stub_dep_file(
        self,
        rel_path: str,
        role_def: workspace_registry.RoleDefinition,
        repo_root: Optional[str] = None,
    ) -> bool:
        """Checks whether rel_path corresponds to any declared role in stub_role_deps."""
        ...

    @operation
    def is_valid_test_stub(self, file_path: str) -> bool:
        """Checks whether file_path is already a valid cleanroom test stub."""
        ...
