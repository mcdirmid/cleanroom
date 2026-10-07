# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: c553278f40fd
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_registry_impl."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Set

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from . import workspace_registry


STANDARD_ROLES: Dict[str, workspace_registry.RoleDefinition] = {
    "high": workspace_registry.RoleDefinition(
        role_name="high",
        guide_path="update_python_with_ai/guides/high_level_spec.md",
        writable_file_patterns=["high/*.md"],
        readonly_file_patterns=["guides/*.md"],
        feedback_role_deps=[],
    ),
    "planning": workspace_registry.RoleDefinition(
        role_name="planning",
        guide_path="update_python_with_ai/guides/high_to_planning.md",
        writable_file_patterns=["planning/*.md"],
        readonly_file_patterns=["high/*.md", "guides/*.md"],
        feedback_role_deps=["high"],
    ),
    "low": workspace_registry.RoleDefinition(
        role_name="low",
        guide_path="update_python_with_ai/guides/planning_to_low.md",
        writable_file_patterns=["low/*.pyi"],
        readonly_file_patterns=["planning/*.md", "grounding/*.gt", "grounding/*.pyi", "guides/*.md"],
        feedback_role_deps=["planning"],
    ),
    "lib": workspace_registry.RoleDefinition(
        role_name="lib",
        guide_path="update_python_with_ai/guides/low_to_lib.md",
        writable_file_patterns=["lib/*.py"],
        readonly_file_patterns=["low/*.pyi", "grounding/*.gt", "grounding/*.pyi", "guides/*.md"],
        feedback_role_deps=["low"],
    ),
    "test": workspace_registry.RoleDefinition(
        role_name="test",
        guide_path="update_python_with_ai/guides/low_to_test.md",
        writable_file_patterns=["tests/*_test.py"],
        readonly_file_patterns=["low/*.pyi", "lib/*.py", "guides/*.md"],
        feedback_role_deps=["low", "lib"],
    ),
    "qa": workspace_registry.RoleDefinition(
        role_name="qa",
        guide_path="update_python_with_ai/guides/qa.md",
        writable_file_patterns=[],
        readonly_file_patterns=["lib/*.py", "tests/*_test.py", "low/*.pyi"],
        feedback_role_deps=["lib", "test"],
        audit_tag="QA_AUDIT",
    ),
    "coverage": workspace_registry.RoleDefinition(
        role_name="coverage",
        guide_path="update_python_with_ai/guides/coverage.md",
        writable_file_patterns=[],
        readonly_file_patterns=["lib/*.py", "tests/*_test.py"],
        feedback_role_deps=["test"],
        audit_tag="COVERAGE_AUDIT",
    ),
}

REGISTRY_FILE = ".cleanroom_workspaces.json"


def _normalize_role_name(role_name_or_address: str) -> str:
    cleaned = role_name_or_address.strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":")[-1]
    return cleaned.strip("/").lower()


class WorkspaceRegistry(workspace_registry.WorkspaceRegistry, Singleton):
    """Realizes role configuration resolution and persistent workspace registration."""

    tier = agent_session.agent_session

    def discover_repository_root(
        self, start_dir: Optional[str] = None
    ) -> str:
        curr = os.path.abspath(start_dir or os.getcwd())
        # First check if start_dir is inside a role workspace
        check_role = curr
        while check_role and check_role != os.path.dirname(check_role):
            role_meta = os.path.join(check_role, ".cleanroom_role.json")
            if os.path.isfile(role_meta):
                try:
                    with open(role_meta, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    m_root = data.get("main_workspace_root") or data.get("repo_root")
                    if m_root and os.path.isdir(m_root):
                        return os.path.realpath(m_root)
                except Exception:
                    pass
                parent = os.path.dirname(check_role)
                if os.path.basename(parent) == "role_workspaces":
                    projects_root = os.path.dirname(parent)
                    ws_base = os.path.basename(check_role)
                    if os.path.isdir(projects_root):
                        for entry in sorted(os.listdir(projects_root)):
                            if entry != "role_workspaces" and ws_base.startswith(f"{entry}_"):
                                cand = os.path.join(projects_root, entry)
                                if os.path.isdir(cand) and (
                                    os.path.exists(os.path.join(cand, ".git"))
                                    or os.path.exists(os.path.join(cand, "MODULE.bazel"))
                                ):
                                    return os.path.realpath(cand)
                break
            check_role = os.path.dirname(check_role)

        while curr and curr != os.path.dirname(curr):
            if os.path.exists(os.path.join(curr, ".git")):
                return curr
            if os.path.exists(os.path.join(curr, "MODULE.bazel")) and not os.path.exists(
                os.path.join(curr, ".cleanroom_role.json")
            ):
                return curr
            curr = os.path.dirname(curr)
        return os.path.abspath(start_dir or os.getcwd())

    def resolve_role_definition(
        self, role_name_or_address: str, repo_root: Optional[str] = None
    ) -> workspace_registry.RoleDefinition:
        clean = _normalize_role_name(role_name_or_address)
        if clean in STANDARD_ROLES:
            base = STANDARD_ROLES[clean]
            if base.role_address is None and ":" in role_name_or_address:
                return workspace_registry.RoleDefinition(
                    role_name=base.role_name,
                    guide_path=base.guide_path,
                    writable_file_patterns=base.writable_file_patterns,
                    readonly_file_patterns=base.readonly_file_patterns,
                    feedback_role_deps=base.feedback_role_deps,
                    role_address=role_name_or_address,
                    audit_tag=base.audit_tag,
                    task_prompt=base.task_prompt,
                )
            return base

        return workspace_registry.RoleDefinition(
            role_name=clean,
            guide_path=f"update_python_with_ai/guides/{clean}.md",
            writable_file_patterns=[f"{clean}/*"],
            readonly_file_patterns=["guides/*.md"],
            feedback_role_deps=[],
            role_address=role_name_or_address if ":" in role_name_or_address else None,
        )

    def compute_workspace_dir(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> str:
        if custom_dest:
            return os.path.abspath(custom_dest)

        root = self.discover_repository_root(repo_root)
        parent_dir = os.path.dirname(root)
        ws_name = os.path.basename(root)
        clean_role = _normalize_role_name(role_name)
        sanitized_scope = dir_scope.strip("/").replace("/", "_")
        folder_name = f"{ws_name}_{clean_role}_{sanitized_scope}"
        return os.path.join(parent_dir, "role_workspaces", folder_name)

    def _get_registry_path(self, repo_root: Optional[str] = None) -> str:
        root = self.discover_repository_root(repo_root)
        parent_dir = os.path.dirname(root)
        workspaces_dir = os.path.join(parent_dir, "role_workspaces")
        os.makedirs(workspaces_dir, exist_ok=True)
        return os.path.join(workspaces_dir, REGISTRY_FILE)

    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[workspace_registry.WorkspaceDescriptor]:
        reg_path = self._get_registry_path(repo_root)
        root = self.discover_repository_root(repo_root)
        repo_reg_path = os.path.join(root, REGISTRY_FILE)

        target_repo = (
            os.path.abspath(root)
            if repo_root
            else None
        )

        candidates: List[Dict[str, Any]] = []
        for p in (reg_path, repo_reg_path):
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and "workspaces" in data:
                        candidates.extend(data["workspaces"])
                    elif isinstance(data, list):
                        candidates.extend(data)
                except (OSError, json.JSONDecodeError):
                    pass

        # Also inspect parent_dir/role_workspaces subdirectories for existing commissioned .cleanroom_role.json
        parent_dir = os.path.dirname(root)
        workspaces_dir = os.path.join(parent_dir, "role_workspaces")
        expected_prefix = f"{os.path.basename(root)}_"
        if os.path.isdir(workspaces_dir):
            try:
                for item_name in sorted(os.listdir(workspaces_dir)):
                    item_path = os.path.join(workspaces_dir, item_name)
                    if os.path.isdir(item_path):
                        role_cfg_path = os.path.join(item_path, ".cleanroom_role.json")
                        if os.path.isfile(role_cfg_path):
                            try:
                                with open(role_cfg_path, "r", encoding="utf-8") as f:
                                    rdata = json.load(f)
                                repo = rdata.get("main_workspace_root") or rdata.get("repo_root")
                                if not repo:
                                    if not item_name.startswith(expected_prefix):
                                        continue
                                    repo = root
                                candidates.append({
                                    "workspace_dir": item_path,
                                    "role": rdata.get("role_name") or rdata.get("role", ""),
                                    "dir": rdata.get("parts_dir") or rdata.get("dir_scope", "staging"),
                                    "main_workspace_root": repo,
                                    "last_sync_timestamp": rdata.get("last_sync_timestamp"),
                                })
                            except (OSError, json.JSONDecodeError):
                                pass
            except OSError:
                pass

        seen_dirs: Set[str] = set()
        descriptors: List[workspace_registry.WorkspaceDescriptor] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            ws_path = item.get("workspace_dir", "")
            if not ws_path:
                continue
            norm_ws = os.path.abspath(ws_path)
            if norm_ws in seen_dirs:
                continue

            item_repo = (
                os.path.abspath(item.get("main_workspace_root", ""))
                if item.get("main_workspace_root")
                else None
            )
            if target_repo is not None and item_repo is not None and item_repo != target_repo:
                continue

            seen_dirs.add(norm_ws)
            role_identifier = item.get("role") or item.get("role_name", "")
            if not role_identifier:
                continue
            try:
                r_def = self.resolve_role_definition(
                    role_identifier,
                    repo_root=item.get("main_workspace_root") or root,
                )
            except Exception:
                continue

            descriptors.append(
                workspace_registry.WorkspaceDescriptor(
                    workspace_dir=norm_ws,
                    main_repository_root=item.get("main_workspace_root") or root,
                    directory_scope=item.get("dir", item.get("parts_dir", "")),
                    role_definition=r_def,
                    last_sync_timestamp=item.get("last_sync_timestamp"),
                )
            )
        return tuple(descriptors)

    def record_workspace(
        self,
        descriptor: workspace_registry.WorkspaceDescriptor,
        repo_root: Optional[str] = None,
    ) -> None:
        reg_path = self._get_registry_path(repo_root)
        root = self.discover_repository_root(repo_root)
        repo_reg_path = os.path.join(root, REGISTRY_FILE)

        for path in (reg_path, repo_reg_path):
            raw_list: List[Dict[str, Any]] = []
            is_dict = False
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "workspaces" in data:
                            is_dict = True
                            raw_list = data["workspaces"]
                        elif isinstance(data, list):
                            raw_list = data
                except (OSError, json.JSONDecodeError):
                    raw_list = []

            updated: List[Dict[str, Any]] = []
            found = False
            target_ws = os.path.abspath(descriptor.workspace_dir)

            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                if os.path.abspath(item.get("workspace_dir", "")) == target_ws:
                    entry = {
                        "workspace_dir": descriptor.workspace_dir,
                        "main_workspace_root": descriptor.main_repository_root,
                        "role": descriptor.role_definition.role_name,
                        "dir": descriptor.directory_scope,
                        "last_sync_timestamp": descriptor.last_sync_timestamp or "",
                    }
                    updated.append(entry)
                    found = True
                else:
                    updated.append(item)

            if not found:
                entry = {
                    "workspace_dir": descriptor.workspace_dir,
                    "main_workspace_root": descriptor.main_repository_root,
                    "role": descriptor.role_definition.role_name,
                    "dir": descriptor.directory_scope,
                    "last_sync_timestamp": descriptor.last_sync_timestamp or "",
                }
                updated.append(entry)

            temp_fd, temp_path = tempfile.mkstemp(
                prefix=".workspaces_", suffix=".json", dir=os.path.dirname(path)
            )
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                if is_dict:
                    json.dump({"workspaces": updated}, f, indent=2)
                else:
                    json.dump(updated, f, indent=2)
                f.write("\n")
            os.replace(temp_path, path)

    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        reg_path = self._get_registry_path(repo_root)
        root = self.discover_repository_root(repo_root)
        repo_reg_path = os.path.join(root, REGISTRY_FILE)
        target_abs = os.path.abspath(workspace_dir)
        removed = False

        for path in (reg_path, repo_reg_path):
            if not os.path.isfile(path):
                continue

            raw_list: List[Dict[str, Any]] = []
            is_dict = False
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "workspaces" in data:
                        is_dict = True
                        raw_list = data["workspaces"]
                    elif isinstance(data, list):
                        raw_list = data
            except (OSError, json.JSONDecodeError):
                continue

            remaining: List[Dict[str, Any]] = []
            file_removed = False

            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                if os.path.abspath(item.get("workspace_dir", "")) == target_abs:
                    file_removed = True
                    removed = True
                else:
                    remaining.append(item)

            if file_removed:
                temp_fd, temp_path = tempfile.mkstemp(
                    prefix=".workspaces_", suffix=".json", dir=os.path.dirname(path)
                )
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    if is_dict:
                        json.dump({"workspaces": remaining}, f, indent=2)
                    else:
                        json.dump(remaining, f, indent=2)
                    f.write("\n")
                os.replace(temp_path, path)

        return removed


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceRegistry,
        keys=[workspace_registry.WorkspaceRegistry, WorkspaceRegistry],
        tier=agent_session.agent_session,
    )
