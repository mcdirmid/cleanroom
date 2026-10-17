# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:45:00Z
# CHANGE: Implement workspace_roles_impl
# CODE_HASH: 47aa58960ee1
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_roles_impl."""

from __future__ import annotations

import ast
import os
import tomllib
from typing import Any, Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from . import workspace_registry, workspace_roles

# Contract: Caches parsed role definitions keyed by file path and modified timestamp.
_ROLE_CACHE: Dict[str, Tuple[float, Dict[str, workspace_roles.RoleDefinition]]] = {}


# Contract: Discovers repository root from argument, registry, or ambient environment.
def _discover_root(repo_root: Optional[str] = None) -> str:
    """Discovers repository root directory from argument, registry, or ambient environment."""
    if repo_root and os.path.isdir(repo_root):
        return os.path.abspath(repo_root)
    try:
        reg = get_singleton(workspace_registry.WorkspaceRegistry)
        return reg.discover_repository_root(repo_root)
    except Exception:
        pass
    bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "")
    if bwd and os.path.isdir(bwd):
        return os.path.abspath(bwd)
    return os.path.abspath(os.getcwd())


# Contract: Decomposes source path pattern into directory, stem suffix, and extension.
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


# Contract: Builds role definition records from raw attributes, enforcing dependency constraints and postconditions.
def _build_role_definitions(
    raw_roles: Dict[str, Dict[str, Any]],
) -> Dict[str, workspace_roles.RoleDefinition]:
    """Builds role definition records from raw role declaration attributes."""
    # Contract: Identifies auditor roles based on missing src_pattern or explicit audit_tag.
    auditor_roles = {
        r.split(":")[-1]
        for r, kwargs in raw_roles.items()
        if not kwargs.get("src_pattern") or kwargs.get("audit_tag")
    }

    role_defs: Dict[str, workspace_roles.RoleDefinition] = {}
    for rname, rkwargs in raw_roles.items():
        raw_role_deps = rkwargs.get("role_deps") or []
        raw_star_deps = rkwargs.get("star_role_deps") or []
        raw_fb_deps = rkwargs.get("feedback_role_deps") or []
        raw_silent_deps = rkwargs.get("silent_role_deps") or []

        role_deps_clean = {d.split(":")[-1] for d in raw_role_deps}
        star_deps_clean = {d.split(":")[-1] for d in raw_star_deps}
        fb_deps_clean = {d.split(":")[-1] for d in raw_fb_deps}
        silent_deps_clean = {d.split(":")[-1] for d in raw_silent_deps}

        # Contract: Postcondition - WHEN feedback role dependencies are redundantly declared as role dependencies, MUST raise ValueError.
        redundant_fb = role_deps_clean & fb_deps_clean
        if redundant_fb:
            raise ValueError(
                f"Role '{rname}' redundantly declares feedback_role_deps {sorted(redundant_fb)} in role_deps. "
                "feedback_role_deps are implicitly role_deps."
            )

        # Contract: Postcondition - WHEN star role dependencies are redundantly declared as role dependencies, MUST raise ValueError.
        redundant_star = role_deps_clean & star_deps_clean
        if redundant_star:
            raise ValueError(
                f"Role '{rname}' redundantly declares star_role_deps {sorted(redundant_star)} in role_deps. "
                "star_role_deps are implicitly role_deps."
            )

        # Contract: Postcondition - WHEN a dependency is declared as both a role dependency and a silent role dependency, MUST raise ValueError.
        conflicting_silent = silent_deps_clean & (role_deps_clean | star_deps_clean | fb_deps_clean)
        if conflicting_silent:
            raise ValueError(
                f"Role '{rname}' declares dependency {sorted(conflicting_silent)} as both a role dependency and a silent role dependency."
            )

        # Contract: Postcondition - WHEN an auditor role is declared as a role dependency, a star role dependency, or a feedback role dependency, MUST raise ValueError.
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

        # Contract: Derives writable and readonly file patterns from source pattern and dependencies.
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

        # Contract: Resolves guide path from configured guide label.
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
            guide_path = f"{guide_label.lstrip(':')}.md"
        else:
            guide_path = ""

        audit_tag = f"{rname.upper()}_AUDIT" if not pat else None

        role_defs[rname] = workspace_roles.RoleDefinition(
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


# Contract: Parses role declarations from a TOML role configuration file.
def _load_roles_from_toml_file(
    toml_path: str,
) -> Dict[str, workspace_roles.RoleDefinition]:
    """Parses role declarations from a TOML role configuration file."""
    if not os.path.isfile(toml_path):
        raise FileNotFoundError(
            f"Cleanroom role definitions TOML file not found: {toml_path}"
        )
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    raw_roles = data.get("roles", {})
    return _build_role_definitions(raw_roles)


# Contract: Evaluates define_role invocations and assignments from build file AST.
def _load_roles_from_build_file(
    build_file_path: str,
) -> Dict[str, workspace_roles.RoleDefinition]:
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


# Contract: Normalizes role identifier removing colon prefixes and leading slashes.
def _normalize_role_identifier(role_name_or_address: str) -> str:
    """Normalizes a role name or package-qualified role address into a canonical role name."""
    cleaned = role_name_or_address.strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":")[-1]
    return cleaned.strip("/").lower()


# Contract: Discovers methodology binding from cleanroom.toml within dir_scope or upward package hierarchy.
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


# Contract: Loads role definitions from bound methodology package or path.
def _load_roles_from_methodology(
    root: str, methodology: str
) -> Optional[Dict[str, workspace_roles.RoleDefinition]]:
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
            for cand_name in ("cleanroom_roles.toml", "cleanroom_python_roles.toml"):
                cand = str(files.joinpath(cand_name))
                if os.path.isfile(cand):
                    return _load_roles_from_toml_file(cand)
        except (ImportError, TypeError, OSError):
            pass
        for cand_name in ("cleanroom_roles.toml", "cleanroom_python_roles.toml"):
            cand = os.path.join(root, methodology, cand_name)
            if os.path.isfile(cand):
                return _load_roles_from_toml_file(cand)
    return None


# Contract: Realizes workspace_roles.RoleResolver singleton.
class RoleResolver(workspace_roles.RoleResolver, Singleton):
    """Realizes role configuration resolution and constraint verification."""

    tier = agent_session.agent_session

    # Contract: Parses role declarations from repository role configuration files or build files.
    def _get_roles(
        self, repo_root: Optional[str] = None
    ) -> Dict[str, workspace_roles.RoleDefinition]:
        """Parses role declarations from repository role configuration files or build files."""
        root = _discover_root(repo_root)

        roots_to_try = [root]
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
            f"Cleanroom role definitions file (cleanroom_roles.toml) not found under: '{root}'"
        )

    # Contract: Constructs role definition carrying its resolved qualified role address.
    def _with_role_address(
        self, base: workspace_roles.RoleDefinition, role_address: str
    ) -> workspace_roles.RoleDefinition:
        """Returns a role definition carrying its resolved qualified role address."""
        return workspace_roles.RoleDefinition(
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

    # Contract: Resolves role configuration matching declared roles or addressed packages.
    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> workspace_roles.RoleDefinition:
        """Resolves a role configuration matching declared roles or addressed packages."""
        root = _discover_root(repo_root)

        clean_addr = role_name_or_address.strip()
        # Contract: Package-qualified role address resolution from addressed package.
        if (
            clean_addr.startswith("//")
            or clean_addr.startswith("./")
            or (":" in clean_addr and not clean_addr.startswith(":"))
        ):
            pkg_part, role_part = clean_addr.split(":", 1)
            target_role = role_part.strip().lower()
            meth_defs = _load_roles_from_methodology(root, pkg_part)
            if meth_defs and target_role in meth_defs:
                base = meth_defs[target_role]
                return self._with_role_address(base, role_name_or_address)

        clean = _normalize_role_identifier(role_name_or_address)

        # Contract: Resolves role definition from methodology bound to dir_scope when specified.
        if dir_scope:
            meth = _find_methodology_for_scope(root, dir_scope)
            if meth:
                scope_roles = _load_roles_from_methodology(root, meth)
                if scope_roles and clean in scope_roles:
                    return scope_roles[clean]

        roles = self._get_roles(repo_root)
        # Contract: Postcondition - WHEN the queried role is undeclared, MUST raise KeyError.
        if clean not in roles:
            raise KeyError(
                f"Unknown cleanroom role: '{clean}'. Declared roles: {sorted(roles.keys())}"
            )
        base = roles[clean]
        if ":" in role_name_or_address and base.role_address is None:
            return self._with_role_address(base, role_name_or_address)
        return base

    # Contract: Loads and resolves all role definitions declared in repository or bound methodology.
    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[workspace_roles.RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository."""
        root = _discover_root(repo_root)
        if dir_scope:
            meth = _find_methodology_for_scope(root, dir_scope)
            if meth:
                scope_roles = _load_roles_from_methodology(root, meth)
                if scope_roles:
                    return list(scope_roles.values())
        roles = self._get_roles(repo_root)
        return list(roles.values())


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RoleResolver,
        keys=[workspace_roles.RoleResolver, RoleResolver],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
