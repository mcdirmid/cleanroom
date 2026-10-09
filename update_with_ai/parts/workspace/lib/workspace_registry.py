# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: c219b0cb43f3
# --- END CLEANROOM METADATA ---

"""Low-level interface for workspace_registry."""

from __future__ import annotations

from dataclasses import dataclass
import ast
import json
import os
import tempfile
import tomllib
from typing import Any, Dict, List, Optional, Protocol, Sequence, Set, Tuple


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
    template: str = ""
    template_command: str = ""


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


REGISTRY_FILE = ".cleanroom_workspaces.json"
_ROLE_CACHE: Dict[str, Tuple[float, Dict[str, RoleDefinition]]] = {}


def _parse_pat_to_glob(pat: str) -> Tuple[str, str, str]:
    if not pat:
        return "", "", ""
    parts = pat.split("/")
    d = parts[1] if len(parts) > 1 else ""
    f = parts[-1]
    stem, ext = os.path.splitext(f)
    suffix = ""
    if "_" in stem and not stem.startswith("{"):
        suffix = stem.replace("{unit_name}", "")
    return d, suffix, ext


def _build_role_definitions(
    raw_roles: Dict[str, Dict[str, Any]],
) -> Dict[str, RoleDefinition]:
    role_defs: Dict[str, RoleDefinition] = {}
    for rname, rkwargs in raw_roles.items():
        pat = rkwargs.get("src_pattern", "")
        d, sfx, ext = _parse_pat_to_glob(pat)
        writable = [f"{d}/*{sfx}{ext}"] if pat else []
        readonly: List[str] = []
        deps = list(rkwargs.get("role_deps") or []) + list(rkwargs.get("star_role_deps") or [])
        if not pat:
            deps += list(rkwargs.get("feedback_role_deps") or [])
        for dep in deps:
            dname = dep.split(":")[-1]
            dpat = raw_roles.get(dname, {}).get("src_pattern", "")
            dd, dsfx, dext = _parse_pat_to_glob(dpat)
            if dd and dext:
                p = f"{dd}/*{dsfx}{dext}"
                if p not in readonly and p not in writable:
                    readonly.append(p)
        if rkwargs.get("guide"):
            readonly.append("guides/*.md")

        guide_label = str(rkwargs.get("guide") or "")
        if guide_label.startswith("//"):
            guide_clean = guide_label.lstrip("/")
            if ":" in guide_clean:
                pkg, tgt = guide_clean.split(":", 1)
                guide_path = f"{pkg}/{tgt}.md"
            else:
                guide_path = f"{guide_clean}.md"
        elif guide_label.endswith(".md"):
            guide_path = guide_label
        elif guide_label:
            guide_path = f"update_python_with_ai/guides/{guide_label.lstrip(':')}.md"
        else:
            guide_path = ""

        audit_tag = f"{rname.upper()}_AUDIT" if not pat else None

        role_defs[rname] = RoleDefinition(
            role_name=rname,
            guide_path=guide_path,
            writable_file_patterns=writable,
            readonly_file_patterns=readonly,
            feedback_role_deps=[d.split(":")[-1] for d in (rkwargs.get("feedback_role_deps") or [])],
            src_pattern=pat,
            role_deps=rkwargs.get("role_deps") or [],
            star_role_deps=rkwargs.get("star_role_deps") or [],
            silent_role_deps=rkwargs.get("silent_role_deps") or [],
            stub_role_deps=rkwargs.get("stub_role_deps") or [],
            silent_cross_role_deps=rkwargs.get("silent_cross_role_deps") or [],
            active_component_types=rkwargs.get("active_component_types") or [],
            verify_template=rkwargs.get("verify_template") or "",
            verification_success_message=rkwargs.get("verification_success_message") or "",
            persona=rkwargs.get("persona") or "",
            workspace_files=rkwargs.get("workspace_files") or [],
            tools=rkwargs.get("tools") or [],
            derive_build_template=rkwargs.get("derive_build_template") or "",
            audit_tag=audit_tag,
            task_prompt=rkwargs.get("prompt_template") or None,
            template=rkwargs.get("template") or "",
            template_command=rkwargs.get("template_command") or "",
        )

    return role_defs


def _load_roles_from_toml_file(
    toml_path: str,
) -> Dict[str, RoleDefinition]:
    if not os.path.isfile(toml_path):
        raise FileNotFoundError(
            f"Cleanroom role definitions TOML file not found: {toml_path}"
        )
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    raw_roles = data.get("roles", {})
    return _build_role_definitions(raw_roles)


def _load_roles_from_build_file(
    build_file_path: str,
) -> Dict[str, RoleDefinition]:
    if not os.path.isfile(build_file_path):
        raise FileNotFoundError(f"Cleanroom role definition build file not found: {build_file_path}")

    with open(build_file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=build_file_path)

    env: Dict[str, Any] = {}
    raw_roles: Dict[str, Dict[str, Any]] = {}

    def _eval_node(node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.List):
            return [_eval_node(el) for el in node.elts]
        elif isinstance(node, ast.Tuple):
            return tuple(_eval_node(el) for el in node.elts)
        elif isinstance(node, ast.Dict):
            return {
                _eval_node(k): _eval_node(v)
                for k, v in zip(node.keys, node.values)
                if k is not None
            }
        elif isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            elif node.id == "True":
                return True
            elif node.id == "False":
                return False
            elif node.id == "None":
                return None
            raise ValueError(f"Undefined identifier in {build_file_path}: {node.id}")
        raise ValueError(f"Unsupported AST node type in {build_file_path}: {type(node).__name__}")

    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    env[target.id] = _eval_node(stmt.value)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            func = stmt.value.func
            is_define_role = (
                (isinstance(func, ast.Name) and func.id == "define_role")
                or (isinstance(func, ast.Attribute) and func.attr == "define_role")
            )
            if is_define_role:
                kwargs: Dict[str, Any] = {}
                for kw in stmt.value.keywords:
                    if kw.arg:
                        kwargs[kw.arg] = _eval_node(kw.value)
                role_name = kwargs.get("name")
                if not role_name or not isinstance(role_name, str):
                    raise ValueError(f"define_role in {build_file_path} missing required 'name' argument")
                raw_roles[role_name] = kwargs

    return _build_role_definitions(raw_roles)


def _normalize_role_name(role_name_or_address: str) -> str:
    cleaned = role_name_or_address.strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":")[-1]
    return cleaned.strip("/").lower()


class _DefaultWorkspaceRegistry:
    """Default implementation of WorkspaceRegistry."""

    def discover_repository_root(
        self, start_dir: Optional[str] = None
    ) -> str:
        curr = os.path.abspath(start_dir or os.getcwd())
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
                except (OSError, json.JSONDecodeError):
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

        check_marker = curr
        while check_marker and check_marker != os.path.dirname(check_marker):
            if os.path.exists(os.path.join(check_marker, ".git")):
                return check_marker
            if os.path.exists(os.path.join(check_marker, "MODULE.bazel")) and not os.path.exists(
                os.path.join(check_marker, ".cleanroom_role.json")
            ):
                return check_marker
            check_marker = os.path.dirname(check_marker)

        if start_dir:
            return os.path.abspath(start_dir)

        bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        if bwd and os.path.isdir(bwd):
            return os.path.realpath(bwd)

        mod_dir = os.path.dirname(os.path.realpath(__file__))
        while mod_dir and mod_dir != os.path.dirname(mod_dir):
            if os.path.exists(os.path.join(mod_dir, ".git")):
                return mod_dir
            if os.path.exists(os.path.join(mod_dir, "MODULE.bazel")) and not os.path.exists(
                os.path.join(mod_dir, ".cleanroom_role.json")
            ):
                return mod_dir
            mod_dir = os.path.dirname(mod_dir)

        return os.path.abspath(curr)

    def _discover_canonical_repo_root(self) -> str:
        bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        if bwd and any(
            os.path.isfile(os.path.join(bwd, marker))
            for marker in ("MODULE.bazel", "pyproject.toml", "cleanroom_roles.toml", "WORKSPACE", "WORKSPACE.bazel")
        ):
            return os.path.realpath(bwd)

        mod_dir = os.path.dirname(os.path.realpath(__file__))
        while mod_dir and mod_dir != os.path.dirname(mod_dir):
            if any(
                os.path.isfile(os.path.join(mod_dir, marker))
                for marker in ("MODULE.bazel", "pyproject.toml", "cleanroom_roles.toml")
            ):
                return mod_dir
            mod_dir = os.path.dirname(mod_dir)

        rf = os.environ.get("PYTHON_RUNFILES") or os.environ.get("TEST_SRCDIR")
        if rf:
            cand = os.path.join(rf, "_main")
            if any(
                os.path.isfile(os.path.join(cand, marker))
                for marker in ("MODULE.bazel", "pyproject.toml", "cleanroom_roles.toml")
            ):
                return cand
        return ""

    def _get_roles(
        self, repo_root: Optional[str] = None
    ) -> Dict[str, RoleDefinition]:
        root = self.discover_repository_root(repo_root)

        roots_to_try = [root]
        fallback_root = self._discover_canonical_repo_root()
        if fallback_root and fallback_root != root:
            roots_to_try.append(fallback_root)

        for r in roots_to_try:
            for toml_name in (
                "cleanroom_roles.toml",
                "cleanroom_python_roles.toml",
            ):
                cand = os.path.join(r, toml_name)
                if os.path.isfile(cand):
                    mtime = os.path.getmtime(cand)
                    cached = _ROLE_CACHE.get(cand)
                    if cached and cached[0] == mtime:
                        return cached[1]
                    defs = _load_roles_from_toml_file(cand)
                    _ROLE_CACHE[cand] = (mtime, defs)
                    return defs

            if os.path.isdir(r):
                try:
                    for entry in os.listdir(r):
                        pkg_dir = os.path.join(r, entry)
                        if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                            for toml_name in (
                                "cleanroom_roles.toml",
                                "cleanroom_python_roles.toml",
                            ):
                                cand = os.path.join(pkg_dir, toml_name)
                                if os.path.isfile(cand):
                                    mtime = os.path.getmtime(cand)
                                    cached = _ROLE_CACHE.get(cand)
                                    if cached and cached[0] == mtime:
                                        return cached[1]
                                    defs = _load_roles_from_toml_file(cand)
                                    _ROLE_CACHE[cand] = (mtime, defs)
                                    return defs
                except OSError:
                    pass

            cand = os.path.join(r, "BUILD.bazel")
            if os.path.isfile(cand):
                try:
                    defs = _load_roles_from_build_file(cand)
                    if defs:
                        return defs
                except (ValueError, OSError):
                    pass

            if os.path.isdir(r):
                try:
                    for entry in os.listdir(r):
                        pkg_dir = os.path.join(r, entry)
                        if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                            cand = os.path.join(pkg_dir, "BUILD.bazel")
                            if os.path.isfile(cand):
                                try:
                                    defs = _load_roles_from_build_file(cand)
                                    if defs:
                                        return defs
                                except (ValueError, OSError):
                                    pass
                except OSError:
                    pass

        raise FileNotFoundError(
            f"Cleanroom role definitions file (cleanroom_roles.toml or cleanroom_python_roles.toml) not found under: '{root}'"
        )

    def resolve_role_definition(
        self, role_name_or_address: str, repo_root: Optional[str] = None
    ) -> RoleDefinition:
        clean = _normalize_role_name(role_name_or_address)
        roles = self._get_roles(repo_root)
        if clean not in roles:
            raise KeyError(
                f"Unknown cleanroom role: '{clean}'. Declared roles: {sorted(roles.keys())}"
            )
        base = roles[clean]
        if ":" in role_name_or_address and base.role_address is None:
            return RoleDefinition(
                role_name=base.role_name,
                guide_path=base.guide_path,
                writable_file_patterns=base.writable_file_patterns,
                readonly_file_patterns=base.readonly_file_patterns,
                feedback_role_deps=base.feedback_role_deps,
                src_pattern=base.src_pattern,
                role_deps=base.role_deps,
                star_role_deps=base.star_role_deps,
                silent_role_deps=base.silent_role_deps,
                stub_role_deps=base.stub_role_deps,
                silent_cross_role_deps=base.silent_cross_role_deps,
                active_component_types=base.active_component_types,
                verify_template=base.verify_template,
                verification_success_message=base.verification_success_message,
                persona=base.persona,
                workspace_files=base.workspace_files,
                tools=base.tools,
                derive_build_template=base.derive_build_template,
                role_address=role_name_or_address,
                audit_tag=base.audit_tag,
                task_prompt=base.task_prompt,
            )
        return base

    def list_roles(
        self, repo_root: Optional[str] = None
    ) -> Sequence[RoleDefinition]:
        roles = self._get_roles(repo_root)
        return list(roles.values())

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
    ) -> Sequence[WorkspaceDescriptor]:
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
                                    "dir": rdata.get("parts_dir") or rdata.get("dir_scope", ""),
                                    "main_workspace_root": repo,
                                    "last_sync_timestamp": rdata.get("last_sync_timestamp"),
                                })
                            except (OSError, json.JSONDecodeError):
                                pass
            except OSError:
                pass

        seen_dirs: Set[str] = set()
        descriptors: List[WorkspaceDescriptor] = []
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
            except (KeyError, ValueError, OSError):
                continue

            descriptors.append(
                WorkspaceDescriptor(
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
        descriptor: WorkspaceDescriptor,
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


_DEFAULT_WORKSPACE_REGISTRY_CLS = _DefaultWorkspaceRegistry

