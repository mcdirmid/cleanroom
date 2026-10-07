# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: 28a82dfd10da
# --- END CLEANROOM METADATA ---

"""Low-level interface for workspace_registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


@dataclass(frozen=True)
class RoleDefinition:
    role_name: str
    guide_path: str
    writable_file_patterns: Sequence[str]
    readonly_file_patterns: Sequence[str]
    feedback_role_deps: Sequence[str]
    src_pattern: str = ""
    role_deps: Sequence[str] = ()
    star_role_deps: Sequence[str] = ()
    silent_role_deps: Sequence[str] = ()
    stub_role_deps: Sequence[str] = ()
    silent_cross_role_deps: Sequence[str] = ()
    active_component_types: Sequence[str] = ()
    verify_template: str = ""
    verification_success_message: str = ""
    persona: str = ""
    workspace_files: Sequence[str] = ()
    tools: Sequence[str] = ()
    derive_build_template: str = ""
    role_address: Optional[str] = None
    audit_tag: Optional[str] = None
    task_prompt: Optional[str] = None


@dataclass(frozen=True)
class WorkspaceDescriptor:
    workspace_dir: str
    main_repository_root: str
    directory_scope: str
    role_definition: RoleDefinition
    last_sync_timestamp: Optional[str] = None


class WorkspaceRegistry(Protocol):
    def discover_repository_root(
        self, start_dir: Optional[str] = None
    ) -> str: ...

    def resolve_role_definition(
        self, role_name_or_address: str, repo_root: Optional[str] = None
    ) -> RoleDefinition: ...

    def list_roles(
        self, repo_root: Optional[str] = None
    ) -> Sequence[RoleDefinition]: ...

    def compute_workspace_dir(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> str: ...

    def record_workspace(
        self, descriptor: WorkspaceDescriptor, repo_root: Optional[str] = None
    ) -> None: ...

    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool: ...

    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[WorkspaceDescriptor]: ...
