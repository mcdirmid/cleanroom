# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:45:00Z
# CHANGE: Delegate role configuration resolution to roles
# CODE_HASH: 525d3d9ca3b4
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for role_registry_impl."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Sequence, Set

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.core.lib import file_paths
from . import role_registry, roles


def _file_path_manager() -> Optional[file_paths.FilePathManager]:
    """Resolves the host file path manager singleton when it is active in scope."""
    try:
        return get_singleton(file_paths.FilePathManager)
    except (LifecycleResolutionError, LookupError):
        return None


def _create_absolute_path(path: str) -> str:
    """Promotes a host directory onto the absolute path representation."""
    absolute = os.path.abspath(path)
    manager = _file_path_manager()
    if manager is None:
        return absolute
    return str(manager.create_absolute_path(file_paths.PathString(absolute)).path)


def _create_workspace_path_under(parent_root: str, relative_name: str) -> str:
    """Combines a workspace-relative name beneath an absolute parent root directory."""
    manager = _file_path_manager()
    if manager is None:
        return os.path.abspath(os.path.join(parent_root, relative_name))
    root = manager.create_absolute_path(file_paths.PathString(os.path.abspath(parent_root)))
    relative = manager.create_workspace_path(file_paths.PathString(relative_name))
    return str(manager.resolve_path(root, relative).path)


def _sanitize_directory_folder_name(folder_name: str) -> str:
    """Replaces directory delimiter characters with underscores within a folder name."""
    return folder_name.replace("/", "_").replace("\\", "_")


def _match_sibling_workspace_conventions(workspace_dir: str) -> Optional[str]:
    """Adopts the main repository root carried by sibling role workspaces."""
    parent = os.path.dirname(workspace_dir)
    if os.path.basename(parent) != "role_workspaces":
        return None
    projects_root = os.path.dirname(parent)
    workspace_base = os.path.basename(workspace_dir)
    if not os.path.isdir(projects_root):
        return None
    for entry in sorted(os.listdir(projects_root), key=len, reverse=True):
        if entry == "role_workspaces" or not workspace_base.startswith(f"{entry}_"):
            continue
        candidate = os.path.join(projects_root, entry)
        if os.path.isdir(candidate) and (
            os.path.exists(os.path.join(candidate, ".git"))
            or any(
                os.path.exists(os.path.join(candidate, marker))
                for marker in ("cleanroom.toml", "cleanroom_roles.toml", "pyproject.toml")
            )
        ):
            return os.path.realpath(candidate)
    return None


def _search_ancestor_markers(start_dir: str) -> Optional[str]:
    """Searches ancestor directories for repository markers."""
    curr = start_dir
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)

    topmost: Optional[str] = None
    curr = start_dir
    while curr and curr != os.path.dirname(curr):
        if (
            any(
                os.path.exists(os.path.join(curr, marker))
                for marker in (
                    "cleanroom.toml",
                    "cleanroom_roles.toml",
                    "cleanroom_python_roles.toml",
                    "pyproject.toml",
                )
            )
            and not os.path.exists(
                os.path.join(curr, ".cleanroom_role.json")
            )
        ):
            topmost = curr
        curr = os.path.dirname(curr)
    return topmost


def _fallback_to_ambient_working_directory() -> str:
    """Falls back to the ambient working directory environment when no marker is found."""
    return os.path.abspath(os.getcwd())


# Contract: Realizes role_registry.WorkspaceRegistry singleton.
class WorkspaceRegistry(role_registry.WorkspaceRegistry, Singleton):
    """Realizes role configuration resolution and active workspace tracking."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._workspaces: Dict[str, role_registry.WorkspaceDescriptor] = {}

    # Contract: Discovers canonical repository root by searching ancestor directories and matching sibling conventions.
    def discover_repository_root(self, start_dir: Optional[str] = None) -> str:
        """Discovers the canonical repository root by searching ancestor directories."""
        # Contract: Resolves canonical repository root from filesystem environment.
        env_main = os.environ.get("CLEANROOM_MAIN_ROOT")
        if env_main and os.path.isdir(env_main):
            return _create_absolute_path(os.path.realpath(env_main))

        curr = os.path.abspath(start_dir or os.getcwd())
        check_role = curr
        while check_role and check_role != os.path.dirname(check_role):
            if os.path.isfile(os.path.join(check_role, ".cleanroom_role.json")):
                discovered = _match_sibling_workspace_conventions(check_role)
                if discovered:
                    return _create_absolute_path(os.path.realpath(discovered))
                break
            check_role = os.path.dirname(check_role)

        discovered = _search_ancestor_markers(curr)
        if discovered:
            return _create_absolute_path(discovered)

        if start_dir:
            return _create_absolute_path(os.path.abspath(start_dir))

        return _create_absolute_path(_fallback_to_ambient_working_directory())

    # Contract: Delegates role definition resolution to roles.RoleResolver.
    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> roles.RoleDefinition:
        """Resolves a role configuration matching declared roles or addressed packages."""
        resolver = get_singleton(roles.RoleResolver)
        return resolver.resolve_role_definition(
            role_name_or_address, repo_root=repo_root, dir_scope=dir_scope
        )

    # Contract: Delegates role listing to roles.RoleResolver.list_roles.
    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[roles.RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository."""
        resolver = get_singleton(roles.RoleResolver)
        return resolver.list_roles(repo_root=repo_root, dir_scope=dir_scope)

    # Contract: Computes sanitized path for role workspace directory under role_workspaces container.
    def compute_workspace_dir(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> str:
        """Computes sanitized path for a role workspace working tree."""
        if custom_dest:
            return custom_dest

        root = self.discover_repository_root(repo_root)
        parent_dir = os.path.dirname(root)
        clean = role_name.strip()
        if ":" in clean:
            clean = clean.split(":")[-1]
        norm_role = clean.strip("/").lower()
        folder_name = _sanitize_directory_folder_name(
            f"{os.path.basename(root)}_{norm_role}_{dir_scope.strip('/')}"
        )
        return _create_workspace_path_under(
            os.path.join(parent_dir, "role_workspaces"), folder_name
        )

    # Contract: Loads active workspace descriptors from session memory and scanned role_workspaces metadata.
    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[role_registry.WorkspaceDescriptor]:
        """Loads active workspace descriptors from active session memory and provisioned role workspaces."""
        root = self.discover_repository_root(repo_root)
        target_repo = os.path.abspath(root) if repo_root else None

        seen_dirs: Set[str] = set()
        descriptors: List[role_registry.WorkspaceDescriptor] = []

        # 1. Collect from in-memory session descriptors
        for ws_dir, desc in list(self._workspaces.items()):
            norm_ws = os.path.abspath(ws_dir)
            if target_repo is not None:
                item_repo = os.path.abspath(desc.main_repository_root)
                if item_repo != target_repo:
                    continue
            seen_dirs.add(norm_ws)
            descriptors.append(desc)

        # 2. Discover provisioned role workspaces from role_workspaces directory
        parent_dir = os.path.dirname(root)
        workspaces_dir = os.path.join(parent_dir, "role_workspaces")
        expected_prefix = f"{os.path.basename(root)}_"
        if os.path.isdir(workspaces_dir):
            try:
                for item_name in sorted(os.listdir(workspaces_dir)):
                    item_path = os.path.join(workspaces_dir, item_name)
                    norm_ws = os.path.abspath(item_path)
                    if norm_ws in seen_dirs:
                        continue
                    if os.path.isdir(item_path):
                        role_cfg_path = os.path.join(item_path, ".cleanroom_role.json")
                        if os.path.isfile(role_cfg_path):
                            try:
                                with open(role_cfg_path, "r", encoding="utf-8") as f:
                                    rdata = json.load(f)
                                if not item_name.startswith(expected_prefix):
                                    continue
                                repo = root
                                item_repo = os.path.abspath(repo)
                                if target_repo is not None and item_repo != target_repo:
                                    continue
                                role_identifier = rdata.get("role_name", "")
                                if not role_identifier:
                                    continue
                                dir_scope = rdata.get("dir_scope", "")
                                try:
                                    r_def = self.resolve_role_definition(
                                        role_identifier,
                                        repo_root=repo,
                                        dir_scope=dir_scope,
                                    )
                                except (KeyError, ValueError, OSError):
                                    continue

                                descriptor = role_registry.WorkspaceDescriptor(
                                    workspace_dir=norm_ws,
                                    main_repository_root=repo,
                                    directory_scope=dir_scope,
                                    role_definition=r_def,
                                    last_sync_timestamp=rdata.get("last_sync_timestamp"),
                                )
                                self._workspaces[norm_ws] = descriptor
                                seen_dirs.add(norm_ws)
                                descriptors.append(descriptor)
                            except (OSError, json.JSONDecodeError):
                                pass
            except OSError:
                pass

        return tuple(descriptors)

    # Contract: Records active workspace descriptor into active session memory keyed by workspace_dir.
    def record_workspace(
        self,
        descriptor: role_registry.WorkspaceDescriptor,
        repo_root: Optional[str] = None,
    ) -> None:
        """Records an active workspace descriptor into active session memory."""
        self._workspaces[descriptor.workspace_dir] = descriptor

    # Contract: Removes workspace descriptor from active session memory and returns whether entry was removed.
    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        """Removes a workspace descriptor from active session memory."""
        target_abs = os.path.abspath(workspace_dir)
        removed = False
        for key in list(self._workspaces.keys()):
            if os.path.abspath(key) == target_abs:
                del self._workspaces[key]
                removed = True
        return removed


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceRegistry,
        keys=[role_registry.WorkspaceRegistry, WorkspaceRegistry],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
