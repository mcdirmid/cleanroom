# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:04Z
# LAST_CHANGED: 2026-10-11T05:04:09Z
# CHANGE: Implement the registry grounding directly with file path manager path construction, atomic JSON registry writes and reads, in-memory descriptor collection, and the declared key and value error branches
# CODE_HASH: 5784c19e88c4
# COVERAGE_AUDIT: 2026-10-12T18:21:04Z
# QA_AUDIT: 2026-10-12T18:21:04Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_registry_impl."""

from __future__ import annotations

import ast
import json
import os
import tempfile
import tomllib
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.core.lib import file_paths
from . import workspace_registry

_REGISTRY_FILE = ".cleanroom_workspaces.json"
_ROLE_CACHE: Dict[str, Tuple[float, Dict[str, workspace_registry.RoleDefinition]]] = {}


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


def _parse_pat_to_glob(pat: str) -> Tuple[str, str, str]:
    """Decomposes a source path pattern into its directory, stem suffix, and extension."""
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
) -> Dict[str, workspace_registry.RoleDefinition]:
    """Builds role definition records from raw role declaration attributes."""
    auditor_roles = {
        r.split(":")[-1]
        for r, kwargs in raw_roles.items()
        if not kwargs.get("src_pattern") or kwargs.get("audit_tag")
    }

    role_defs: Dict[str, workspace_registry.RoleDefinition] = {}
    for rname, rkwargs in raw_roles.items():
        raw_role_deps = rkwargs.get("role_deps") or []
        raw_star_deps = rkwargs.get("star_role_deps") or []
        raw_fb_deps = rkwargs.get("feedback_role_deps") or []
        raw_silent_deps = rkwargs.get("silent_role_deps") or []

        role_deps_clean = {d.split(":")[-1] for d in raw_role_deps}
        star_deps_clean = {d.split(":")[-1] for d in raw_star_deps}
        fb_deps_clean = {d.split(":")[-1] for d in raw_fb_deps}
        silent_deps_clean = {d.split(":")[-1] for d in raw_silent_deps}

        redundant_fb = role_deps_clean & fb_deps_clean
        if redundant_fb:
            raise ValueError(
                f"Role '{rname}' redundantly declares feedback_role_deps {sorted(redundant_fb)} in role_deps. "
                "feedback_role_deps are implicitly role_deps."
            )

        redundant_star = role_deps_clean & star_deps_clean
        if redundant_star:
            raise ValueError(
                f"Role '{rname}' redundantly declares star_role_deps {sorted(redundant_star)} in role_deps. "
                "star_role_deps are implicitly role_deps."
            )

        conflicting_silent = silent_deps_clean & (role_deps_clean | star_deps_clean | fb_deps_clean)
        if conflicting_silent:
            raise ValueError(
                f"Role '{rname}' declares dependency {sorted(conflicting_silent)} as both a role dependency and a silent role dependency."
            )

        auditor_in_role = role_deps_clean & auditor_roles
        if auditor_in_role:
            raise ValueError(
                f"Role '{rname}' declares auditor role {sorted(auditor_in_role)} in role_deps. "
                "Auditor roles can only be silent_role_deps."
            )

        auditor_in_star = star_deps_clean & auditor_roles
        if auditor_in_star:
            raise ValueError(
                f"Role '{rname}' declares auditor role {sorted(auditor_in_star)} in star_role_deps. "
                "Auditor roles can only be silent_role_deps."
            )

        auditor_in_fb = fb_deps_clean & auditor_roles
        if auditor_in_fb:
            raise ValueError(
                f"Role '{rname}' declares auditor role {sorted(auditor_in_fb)} in feedback_role_deps. "
                "Auditor roles can only be silent_role_deps."
            )

        pat = rkwargs.get("src_pattern", "")
        d, sfx, ext = _parse_pat_to_glob(pat)
        writable = [f"{d}/*{sfx}{ext}"] if pat else []
        readonly: List[str] = []
        deps = list(raw_role_deps) + list(raw_star_deps) + list(raw_fb_deps)
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

        role_defs[rname] = workspace_registry.RoleDefinition(
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
) -> Dict[str, workspace_registry.RoleDefinition]:
    """Parses role declarations from a TOML role configuration file."""
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
) -> Dict[str, workspace_registry.RoleDefinition]:
    """Parses role declarations from a repository build file."""
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


def _normalize_role_identifier(role_name_or_address: str) -> str:
    """Normalizes a role name or package-qualified role address into a canonical role name."""
    cleaned = role_name_or_address.strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":")[-1]
    return cleaned.strip("/").lower()


def _find_methodology_for_scope(root: str, dir_scope: str) -> Optional[str]:
    """Finds methodology binding from cleanroom.toml within dir_scope or upward."""
    if not dir_scope:
        return None
    scope_dir = os.path.join(root, dir_scope)
    root_abs = os.path.abspath(root)

    cand = os.path.join(scope_dir, "cleanroom.toml")
    if os.path.isfile(cand):
        try:
            with open(cand, "rb") as f:
                data = tomllib.load(f)
            meth = data.get("methodology")
            if meth and isinstance(meth, str):
                return meth.strip()
        except (OSError, tomllib.TOMLDecodeError):
            pass

    if os.path.isdir(scope_dir):
        try:
            for entry in os.listdir(scope_dir):
                sub = os.path.join(scope_dir, entry)
                if os.path.isdir(sub) and not entry.startswith((".", "bazel-", "venv")):
                    sub_cand = os.path.join(sub, "cleanroom.toml")
                    if os.path.isfile(sub_cand):
                        try:
                            with open(sub_cand, "rb") as f:
                                data = tomllib.load(f)
                            meth = data.get("methodology")
                            if meth and isinstance(meth, str):
                                return meth.strip()
                        except (OSError, tomllib.TOMLDecodeError):
                            pass
        except OSError:
            pass

    curr = os.path.abspath(scope_dir)
    while curr and curr.startswith(root_abs) and curr != root_abs:
        cand = os.path.join(curr, "cleanroom.toml")
        if os.path.isfile(cand):
            try:
                with open(cand, "rb") as f:
                    data = tomllib.load(f)
                meth = data.get("methodology")
                if meth and isinstance(meth, str):
                    return meth.strip()
            except (OSError, tomllib.TOMLDecodeError):
                pass
        curr_parent = os.path.dirname(curr)
        if curr == curr_parent:
            break
        curr = curr_parent

    return None


def _load_roles_from_methodology(
    root: str, methodology: str
) -> Optional[Dict[str, workspace_registry.RoleDefinition]]:
    """Loads role definitions from a bound methodology string (e.g. '//update_python_with_ai')."""
    if methodology.startswith("//") or methodology.startswith("./"):
        rel_pkg = methodology.lstrip("./").lstrip("/")
        pkg_dir = os.path.join(root, rel_pkg)
        for cand_name in ("cleanroom_roles.toml", "cleanroom_python_roles.toml"):
            cand = os.path.join(pkg_dir, cand_name)
            if os.path.isfile(cand):
                mtime = os.path.getmtime(cand)
                cached = _ROLE_CACHE.get(cand)
                if cached and cached[0] == mtime:
                    return cached[1]
                defs = _load_roles_from_toml_file(cand)
                _ROLE_CACHE[cand] = (mtime, defs)
                return defs
        cand_b = os.path.join(pkg_dir, "BUILD.bazel")
        if os.path.isfile(cand_b):
            try:
                defs = _load_roles_from_build_file(cand_b)
                if defs:
                    return defs
            except (ValueError, OSError):
                pass
    else:
        pkg_name = methodology.replace("-", "_")
        try:
            import importlib.resources
            files = importlib.resources.files(pkg_name)
            cand = str(files.joinpath("cleanroom_roles.toml"))
            if os.path.isfile(cand):
                return _load_roles_from_toml_file(cand)
        except (ImportError, TypeError, OSError):
            pass
        cand = os.path.join(root, methodology, "cleanroom_roles.toml")
        if os.path.isfile(cand):
            return _load_roles_from_toml_file(cand)
    return None


def _inspect_role_metadata_descriptor(workspace_dir: str) -> Optional[str]:
    """Reads the role metadata JSON of an enclosing isolated role workspace."""
    role_meta = os.path.join(workspace_dir, ".cleanroom_role.json")
    if not os.path.isfile(role_meta):
        return None
    try:
        with open(role_meta, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    main_root = data.get("main_workspace_root") or data.get("repo_root")
    if main_root and os.path.isdir(main_root):
        return os.path.realpath(main_root)
    return None


def _match_sibling_workspace_conventions(workspace_dir: str) -> Optional[str]:
    """Adopts the main repository root carried by sibling role workspaces."""
    parent = os.path.dirname(workspace_dir)
    if os.path.basename(parent) != "role_workspaces":
        return None
    projects_root = os.path.dirname(parent)
    workspace_base = os.path.basename(workspace_dir)
    if not os.path.isdir(projects_root):
        return None
    for entry in sorted(os.listdir(projects_root)):
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
    mod_dir = os.path.dirname(os.path.realpath(__file__))
    curr = mod_dir
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)

    topmost: Optional[str] = None
    curr = mod_dir
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
    if topmost:
        return topmost

    return os.path.abspath(os.getcwd())


def _read_json_registry_descriptors(path: str) -> List[Dict[str, Any]]:
    """Decodes the workspace descriptor array held in the persistent registry file."""
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        entries = data.get("workspaces")
        if isinstance(entries, list):
            return [e for e in entries if isinstance(e, dict)]
        return []
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    return []


def _registry_uses_object_envelope(path: str) -> bool:
    """Reports whether the persistent registry file wraps its array in an object envelope."""
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and "workspaces" in data


def _write_json_registry_atomically(
    path: str, descriptors: List[Dict[str, Any]], wrap_in_object: bool = False
) -> None:
    """Encodes deterministic JSON into a temporary sibling file and atomically replaces the registry file."""
    payload: Any = {"workspaces": descriptors} if wrap_in_object else descriptors
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(
        prefix=".workspaces_", suffix=".json", dir=directory
    )
    with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True, indent=2))
        f.write("\n")
    os.replace(temp_path, path)


def _descriptor_entry(
    descriptor: workspace_registry.WorkspaceDescriptor,
) -> Dict[str, Any]:
    """Serializes a workspace descriptor into its persistent registry entry."""
    return {
        "workspace_dir": descriptor.workspace_dir,
        "main_workspace_root": descriptor.main_repository_root,
        "role": descriptor.role_definition.role_name,
        "dir": descriptor.directory_scope,
        "last_sync_timestamp": descriptor.last_sync_timestamp or "",
    }


class WorkspaceRegistry(workspace_registry.WorkspaceRegistry, Singleton):
    """Realizes role configuration resolution and persistent workspace registration."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._workspaces: Dict[str, workspace_registry.WorkspaceDescriptor] = {}

    def discover_repository_root(self, start_dir: Optional[str] = None) -> str:
        """Discovers the canonical repository root by searching ancestor directories."""
        curr = os.path.abspath(start_dir or os.getcwd())
        check_role = curr
        while check_role and check_role != os.path.dirname(check_role):
            if os.path.isfile(os.path.join(check_role, ".cleanroom_role.json")):
                discovered = _inspect_role_metadata_descriptor(check_role)
                if discovered:
                    return _create_absolute_path(os.path.realpath(discovered))
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

    def _discover_canonical_repo_root(self) -> str:
        """Discovers the canonical repository root from the ambient environment."""
        mod_dir = os.path.dirname(os.path.realpath(__file__))
        curr = mod_dir
        while curr and curr != os.path.dirname(curr):
            if os.path.exists(os.path.join(curr, ".git")):
                return curr
            curr = os.path.dirname(curr)

        topmost_marker_dir = ""
        curr = mod_dir
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
                topmost_marker_dir = curr
            curr = os.path.dirname(curr)
        if topmost_marker_dir:
            return topmost_marker_dir

        rf = os.environ.get("PYTHON_RUNFILES") or os.environ.get("TEST_SRCDIR")
        if rf:
            cand = os.path.join(rf, "_main")
            if any(
                os.path.isfile(os.path.join(cand, marker))
                for marker in ("cleanroom.toml", "cleanroom_roles.toml", "pyproject.toml")
            ):
                return cand
        return ""

    def _get_roles(
        self, repo_root: Optional[str] = None
    ) -> Dict[str, workspace_registry.RoleDefinition]:
        """Parses role declarations from repository role configuration files or build files."""
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
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> workspace_registry.RoleDefinition:
        """Resolves a role configuration matching declared roles or addressed packages."""
        root = self.discover_repository_root(repo_root)

        clean_addr = role_name_or_address.strip()
        if (clean_addr.startswith("//") or clean_addr.startswith("./") or (":" in clean_addr and not clean_addr.startswith(":"))):
            pkg_part, role_part = clean_addr.split(":", 1)
            target_role = role_part.strip().lower()
            meth_defs = _load_roles_from_methodology(root, pkg_part)
            if meth_defs and target_role in meth_defs:
                base = meth_defs[target_role]
                return self._with_role_address(base, role_name_or_address)

        clean = _normalize_role_identifier(role_name_or_address)

        if dir_scope:
            meth = _find_methodology_for_scope(root, dir_scope)
            if meth:
                scope_roles = _load_roles_from_methodology(root, meth)
                if scope_roles and clean in scope_roles:
                    return scope_roles[clean]

        roles = self._get_roles(repo_root)
        if clean not in roles:
            raise KeyError(
                f"Unknown cleanroom role: '{clean}'. Declared roles: {sorted(roles.keys())}"
            )
        base = roles[clean]
        if ":" in role_name_or_address and base.role_address is None:
            return self._with_role_address(base, role_name_or_address)
        return base

    def _with_role_address(
        self, base: workspace_registry.RoleDefinition, role_address: str
    ) -> workspace_registry.RoleDefinition:
        """Returns a role definition carrying its resolved qualified role address."""
        return workspace_registry.RoleDefinition(
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
            role_address=role_address,
            audit_tag=base.audit_tag,
            task_prompt=base.task_prompt,
            template=base.template,
            template_command=base.template_command,
        )

    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[workspace_registry.RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository."""
        root = self.discover_repository_root(repo_root)
        if dir_scope:
            meth = _find_methodology_for_scope(root, dir_scope)
            if meth:
                scope_roles = _load_roles_from_methodology(root, meth)
                if scope_roles:
                    return list(scope_roles.values())
        roles = self._get_roles(repo_root)
        return list(roles.values())

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
        folder_name = _sanitize_directory_folder_name(
            f"{os.path.basename(root)}_{_normalize_role_identifier(role_name)}_{dir_scope.strip('/')}"
        )
        return _create_workspace_path_under(
            os.path.join(parent_dir, "role_workspaces"), folder_name
        )

    def _get_registry_path(self, repo_root: Optional[str] = None) -> str:
        """Resolves the persistent registry file path held beside the role workspaces."""
        root = self.discover_repository_root(repo_root)
        parent_dir = os.path.dirname(root)
        workspaces_dir = os.path.join(parent_dir, "role_workspaces")
        os.makedirs(workspaces_dir, exist_ok=True)
        return os.path.join(workspaces_dir, _REGISTRY_FILE)

    def _read_all_descriptor_entries(
        self, repo_root: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Hydrates the in-memory descriptor collection from the persistent registry files."""
        entries = _read_json_registry_descriptors(self._get_registry_path(repo_root))
        root = self.discover_repository_root(repo_root)
        entries.extend(
            _read_json_registry_descriptors(os.path.join(root, _REGISTRY_FILE))
        )
        return entries

    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[workspace_registry.WorkspaceDescriptor]:
        """Loads active workspace descriptors from the persistent registry file."""
        root = self.discover_repository_root(repo_root)
        repo_reg_path = os.path.join(root, _REGISTRY_FILE)
        target_repo = os.path.abspath(root) if repo_root else None

        candidates: List[Dict[str, Any]] = self._read_all_descriptor_entries(repo_root)

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
        descriptors: List[workspace_registry.WorkspaceDescriptor] = []
        for item in candidates:
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
                    dir_scope=item.get("dir", item.get("parts_dir", "")),
                )
            except (KeyError, ValueError, OSError):
                continue

            descriptor = workspace_registry.WorkspaceDescriptor(
                workspace_dir=norm_ws,
                main_repository_root=item.get("main_workspace_root") or root,
                directory_scope=item.get("dir", item.get("parts_dir", "")),
                role_definition=r_def,
                last_sync_timestamp=item.get("last_sync_timestamp"),
            )
            self._workspaces[norm_ws] = descriptor
            descriptors.append(descriptor)
        return tuple(descriptors)

    def record_workspace(
        self,
        descriptor: workspace_registry.WorkspaceDescriptor,
        repo_root: Optional[str] = None,
    ) -> None:
        """Records an active workspace descriptor into the persistent registry file."""
        self._workspaces[descriptor.workspace_dir] = descriptor
        reg_path = self._get_registry_path(repo_root)
        root = self.discover_repository_root(repo_root)
        repo_reg_path = os.path.join(root, _REGISTRY_FILE)
        entry = _descriptor_entry(descriptor)
        target_ws = os.path.abspath(descriptor.workspace_dir)

        for path in (reg_path, repo_reg_path):
            wrapped = _registry_uses_object_envelope(path)
            entries = _read_json_registry_descriptors(path)
            updated: List[Dict[str, Any]] = []
            for item in entries:
                if os.path.abspath(str(item.get("workspace_dir", ""))) == target_ws:
                    continue
                updated.append(item)
            updated.append(entry)
            _write_json_registry_atomically(path, updated, wrap_in_object=wrapped)

    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        """Removes a workspace descriptor from the persistent registry file."""
        reg_path = self._get_registry_path(repo_root)
        root = self.discover_repository_root(repo_root)
        repo_reg_path = os.path.join(root, _REGISTRY_FILE)
        target_abs = os.path.abspath(workspace_dir)
        removed = False

        for path in (reg_path, repo_reg_path):
            if not os.path.isfile(path):
                continue
            wrapped = _registry_uses_object_envelope(path)
            entries = _read_json_registry_descriptors(path)
            remaining: List[Dict[str, Any]] = []
            file_removed = False

            for item in entries:
                if os.path.abspath(str(item.get("workspace_dir", ""))) == target_abs:
                    file_removed = True
                    removed = True
                else:
                    remaining.append(item)

            if file_removed:
                _write_json_registry_atomically(path, remaining, wrap_in_object=wrapped)

        self._workspaces.pop(workspace_dir, None)
        return removed


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceRegistry,
        keys=[workspace_registry.WorkspaceRegistry, WorkspaceRegistry],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
