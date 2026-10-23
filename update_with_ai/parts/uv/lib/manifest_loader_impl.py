import os
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import tomllib

from update_with_ai.parts.agent.lib import node_storage
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.core.lib import file_paths
from . import manifest_loader
from . import target
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)


class UvManifestLoader(manifest_loader.UvManifestLoader):
    tier = system

    def __init__(self) -> None:
        self._manifests: Dict[dag_storage.DagNode, manifest_loader.TargetManifest] = {}
        self._methodology_roles: Dict[str, Tuple[str, Dict[str, Dict[str, Any]]]] = {}
        self._unit_locations: Dict[str, Dict[str, str]] = {}

    def _get_workspace_root(self) -> str:
        try:
            fp_mgr: Any = get_singleton(file_paths.FilePathManager)
            if fp_mgr and hasattr(fp_mgr, "get_workspace_root"):
                return str(fp_mgr.get_workspace_root().path)
        except (LifecycleResolutionError, KeyError, LookupError, RuntimeError):
            pass
        return os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()

    def _find_methodology_for_package(self, root: str, pkg_dir: str) -> str:
        curr = os.path.join(root, pkg_dir)
        root_abs = os.path.abspath(root)
        while True:
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
            if curr == root_abs or curr == curr_parent or not curr.startswith(root_abs):
                break
            curr = curr_parent
        raise FileNotFoundError(
            f"No 'cleanroom.toml' methodology binding found upwards from '{os.path.join(root, pkg_dir)}' to workspace root '{root_abs}'"
        )

    # Contract: retrieve_manifest - discovers methodology bindings and loads role definitions
    def _get_methodology_roles(
        self, root: str, pkg_dir: str
    ) -> Tuple[str, Dict[str, Dict[str, Any]]]:
        meth = self._find_methodology_for_package(root, pkg_dir)
        if meth in self._methodology_roles:
            return self._methodology_roles[meth]

        if meth.startswith("//") or meth.startswith("./"):
            rel_pkg = meth.lstrip("./").lstrip("/")
            toml_path = os.path.join(root, rel_pkg, "cleanroom_roles.toml")
            if not os.path.isfile(toml_path):
                cand = os.path.join(root, rel_pkg, "cleanroom_python_roles.toml")
                if os.path.isfile(cand):
                    toml_path = cand
            if not os.path.isfile(toml_path):
                for root_cand in ("cleanroom_roles.toml", "cleanroom_python_roles.toml"):
                    c_path = os.path.join(root, root_cand)
                    if os.path.isfile(c_path):
                        toml_path = c_path
                        break
            canon_meth = f"//{rel_pkg}"
        else:
            canon_meth = meth
            pkg_name = meth.replace("-", "_")
            try:
                import importlib.resources
                files = importlib.resources.files(pkg_name)
                toml_path = str(files.joinpath("cleanroom_roles.toml"))
            except (ImportError, AttributeError, TypeError, ValueError, OSError):
                toml_path = os.path.join(root, meth, "cleanroom_roles.toml")

        roles: Dict[str, Dict[str, Any]] = {}
        if not os.path.isfile(toml_path):
            raise FileNotFoundError(
                f"Methodology role definition file not found for '{meth}' at '{toml_path}'"
            )
        try:
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
            r_dict = data.get("roles")
            roles = r_dict if isinstance(r_dict, dict) else {}
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise ValueError(f"Failed to parse role definitions from '{toml_path}': {e}") from e
        if not roles:
            raise ValueError(f"Methodology at '{toml_path}' declares no roles in '[roles]'")

        result = (canon_meth, roles)
        self._methodology_roles[meth] = result
        return result

    def _parts_roots(self, root: str) -> List[str]:
        """Discovers parts workspace roots under the workspace root.

        Parts packages live under a scope directory that contains a `parts` child
        (e.g. `update_python_with_ai/parts` in the canonical repository and
        `staging/parts` in a role workspace), so the scope directories present on
        the host are derived first; the conventional layouts remain as fallbacks.
        """
        roots: List[str] = []
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            entries = []
        for entry in entries:
            if entry.startswith(".") or entry.startswith("bazel-"):
                continue
            if os.path.isdir(os.path.join(root, entry, "parts")):
                roots.append(f"{entry}/parts")
        if os.path.isdir(os.path.join(root, "parts")):
            roots.append("parts")
        return list(dict.fromkeys(roots))

    def _find_parts_root(self, root: str, pkg_dir: str) -> Optional[str]:
        norm_pkg = pkg_dir.replace("\\", "/").strip("/")
        if "/parts/" in norm_pkg:
            return norm_pkg.split("/parts/")[0] + "/parts"
        elif norm_pkg.startswith("parts/"):
            return "parts"
        elif norm_pkg.endswith("/parts"):
            return norm_pkg
        for cand in self._parts_roots(root):
            if os.path.isdir(os.path.join(root, cand)):
                return cand
        return None

    def _get_unit_to_pkg_map(self, root: str, parts_prefix: str) -> Dict[str, str]:
        """Maps unit names to their containing parts packages.

        A unit is evidenced by its declaration directories (`high`, `planning`,
        `low`, `lib`), so the mapping remains derivable when a role workspace
        only projects a subset of the package layout.
        """
        if parts_prefix in self._unit_locations:
            return self._unit_locations[parts_prefix]
        unit_map: Dict[str, str] = {}
        parts_abs = os.path.join(root, parts_prefix)
        if os.path.isdir(parts_abs):
            try:
                subpackages = sorted(os.listdir(parts_abs))
            except OSError:
                subpackages = []
            layouts: List[Tuple[str, str]] = []
            _, roles_dict = self._get_methodology_roles(root, parts_prefix)
            for r_cfg in roles_dict.values():
                src_pat = r_cfg.get("src_pattern", "")
                if "{unit_name}" in src_pat:
                    clean_pat = src_pat.replace("{unit_dir}/", "").replace("{unit_dir}\\", "")
                    if "/" in clean_pat:
                        layout_d, file_pat = clean_pat.split("/", 1)
                        if "{unit_name}" in file_pat:
                            sfx = file_pat.split("{unit_name}", 1)[1]
                            layouts.append((layout_d, sfx))
            if not layouts:
                raise ValueError(
                    f"No layout patterns with {{unit_name}} found in methodology for '{parts_prefix}'"
                )

            for sub in subpackages:
                sub_dir = os.path.join(parts_abs, sub)
                if not os.path.isdir(sub_dir) or sub.startswith("."):
                    continue

                for layout_dir, suffix in layouts:
                    layout_abs = os.path.join(sub_dir, layout_dir)
                    if not os.path.isdir(layout_abs):
                        continue
                    try:
                        entries = sorted(os.listdir(layout_abs))
                    except OSError:
                        continue
                    for entry in entries:
                        if entry.startswith(".") or not entry.endswith(suffix):
                            continue
                        unit_name = entry[: -len(suffix)]
                        if not unit_name or unit_name.startswith("_"):
                            continue
                        unit_map.setdefault(unit_name, f"//{parts_prefix}/{sub}")
        self._unit_locations[parts_prefix] = unit_map
        return unit_map

    def _resolve_unit_package(self, root: str, pkg_dir: str, unit_name: str) -> str:
        clean_name = unit_name.strip()
        if "/" in clean_name or ":" in clean_name:
            if not clean_name.startswith("//"):
                return f"//{clean_name.lstrip('/')}"
            return clean_name

        if os.path.isfile(os.path.join(root, pkg_dir, "high", f"{clean_name}.md")):
            return f"//{pkg_dir}:{clean_name}"

        own_prefix = self._find_parts_root(root, pkg_dir)
        scopes = [own_prefix] if own_prefix else []
        scopes.extend(scope for scope in self._parts_roots(root) if scope != own_prefix)
        for parts_prefix in scopes:
            u_map = self._get_unit_to_pkg_map(root, parts_prefix)
            if clean_name in u_map:
                return f"{u_map[clean_name]}:{clean_name}"

        return f"//{pkg_dir}:{clean_name}"

    # Contract: retrieve_manifest - parses high-level specifications for component metadata
    def _parse_hls(self, hls_path: str) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "component_type": "implementation",
            "imports": [],
            "implements": [],
            "assembles": [],
        }
        if not os.path.exists(hls_path):
            return info
        try:
            with open(hls_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                s = line.strip()
                if s.startswith("# ") and " component" in s:
                    parts = s[2:].split()
                    if len(parts) >= 2 and parts[-1].lower() == "component":
                        info["component_type"] = parts[-2]
                elif s.startswith("imports:"):
                    raw = s[len("imports:") :].strip()
                    info["imports"] = [x.strip() for x in raw.split(",") if x.strip()]
                elif s.startswith("implements:"):
                    raw = s[len("implements:") :].strip()
                    info["implements"] = [x.strip() for x in raw.split(",") if x.strip()]
                elif s.startswith("assembles:"):
                    raw = s[len("assembles:") :].strip()
                    info["assembles"] = [x.strip() for x in raw.split(",") if x.strip()]
                elif s.startswith("## "):
                    break
        except OSError:
            pass
        return info

    # Contract: retrieve target manifests from workspace directories for graph nodes
    # Contract: anchor relative package directories to workspace root
    # Contract: search package directories upwards for scope configuration files to discover methodology bindings
    # Contract: load role definitions using uv manifest ext
    # Contract: evaluate role source patterns parameterized with unit metadata
    # Contract: evaluate task prompt templates parameterized with unit metadata
    # Contract: evaluate verification check templates parameterized with unit metadata
    # Contract: evaluate verification success message templates parameterized with unit metadata
    # Contract: cross-product unit dependencies with role dependencies to produce target dependencies
    # Contract: incorporate fixed role node dependencies as declared direct dependencies
    # Contract: resolve bare cross-package unit dependency references to their containing packages within parts workspaces
    # Contract: forward constituent unit dependencies and role dependencies for inactive pass-through nodes
    # Contract: synthesize promptless pass-through node definitions when unit component type is not active for a role
    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[manifest_loader.TargetManifest]:
        if node in self._manifests:
            return self._manifests[node]

        root = self._get_workspace_root()

        unit_str = node.unit_address
        if unit_str.startswith("//"):
            unit_str = unit_str[2:]
        if ":" in unit_str:
            pkg_dir, unit_name = unit_str.split(":", 1)
        else:
            pkg_dir = os.path.dirname(unit_str)
            unit_name = os.path.basename(unit_str)

        role_name = node.role_address
        if not role_name:
            role_name = "lib"
        elif ":" in role_name:
            role_name = role_name.split(":")[-1]

        canon_meth, roles_dict = self._get_methodology_roles(root, pkg_dir)
        role_cfg = roles_dict.get(role_name, {})
        hls_path = os.path.join(root, pkg_dir, "high", f"{unit_name}.md")
        if not os.path.isfile(hls_path):
            resolved = self._resolve_unit_package(root, pkg_dir, unit_name)
            res_unit = resolved.lstrip("/")
            if ":" in res_unit:
                r_pkg, r_name = res_unit.split(":", 1)
                cand = os.path.join(root, r_pkg, "high", f"{r_name}.md")
                if os.path.isfile(cand):
                    pkg_dir = r_pkg
                    unit_name = r_name
                    hls_path = cand

        if not os.path.isfile(hls_path):
            return None

        hls_info = self._parse_hls(hls_path)
        comp_type = hls_info["component_type"]

        raw_unit_deps: List[str] = []
        if comp_type == "assembly":
            raw_unit_deps.extend(hls_info["assembles"])
        raw_unit_deps.extend(hls_info["imports"])
        raw_unit_deps.extend(hls_info["implements"])
        raw_unit_deps = list(dict.fromkeys(raw_unit_deps))

        active_types = role_cfg.get("active_component_types", ["implementation"])
        is_active = comp_type in active_types

        if not is_active:
            deps_list: List[str] = []
            silent_deps_list: List[str] = []

            for udep in raw_unit_deps:
                u_norm = self._resolve_unit_package(root, pkg_dir, udep)
                deps_list.append(f"{u_norm}#{role_name}")

            for rd in role_cfg.get("role_deps", []):
                deps_list.append(f"//{pkg_dir}:{unit_name}#{rd}")

            for sr in role_cfg.get("star_role_deps", []):
                if sr != role_name:
                    implied = f"//{pkg_dir}:{unit_name}#{sr}"
                    if implied not in deps_list:
                        deps_list.append(implied)

            for srd in role_cfg.get("silent_role_deps", []):
                silent_deps_list.append(f"//{pkg_dir}:{unit_name}#{srd}")

            manifest = manifest_loader.TargetManifest(
                label=manifest_loader.TargetLabel(f"//{pkg_dir}:{unit_name}#{role_name}"),
                dependencies=tuple(manifest_loader.TargetLabel(d) for d in deps_list),
                silent_dependencies=tuple(manifest_loader.TargetLabel(d) for d in silent_deps_list),
                star_dependencies=tuple(manifest_loader.TargetLabel(d) for d in deps_list),
                feedback_dependencies=(),
                allows_step_mode=False,
            )
            self._manifests[node] = manifest
            return manifest

        src_pattern = role_cfg.get("src_pattern", "")
        src_file = None
        if src_pattern:
            src_file = manifest_loader.file_alias.RelativePath(
                src_pattern.format(unit_dir=pkg_dir, unit_name=unit_name)
            )

        prompt_pattern = role_cfg.get("prompt_template", "")
        task_prompt = None
        if prompt_pattern:
            prompt_text = prompt_pattern.format(
                unit_dir=pkg_dir,
                unit_name=unit_name,
                component_type=comp_type,
            )
            task_prompt = node_storage.TaskPrompt(prompt_text)

        verify_template = role_cfg.get("verify_template", "")
        verification_check = None
        if verify_template:
            verification_check = manifest_loader.VerificationCommand(
                verify_template.format(unit_dir=pkg_dir, unit_name=unit_name)
            )

        guide_target = None
        guide_str = role_cfg.get("guide", "")
        if guide_str:
            guide_target = manifest_loader.TargetLabel(guide_str)

        direct_deps: List[str] = []
        feedback_deps: List[str] = []
        silent_deps: List[str] = []
        star_deps: List[str] = []

        for rd in role_cfg.get("role_deps", []):
            direct_deps.append(f"//{pkg_dir}:{unit_name}#{rd}")

        for frd in role_cfg.get("feedback_role_deps", []):
            feedback_deps.append(f"//{pkg_dir}:{unit_name}#{frd}")

        for srd in role_cfg.get("silent_role_deps", []):
            silent_deps.append(f"//{pkg_dir}:{unit_name}#{srd}")

        for udep in raw_unit_deps:
            u_norm = self._resolve_unit_package(root, pkg_dir, udep)
            for srd in role_cfg.get("star_role_deps", []):
                star_deps.append(f"{u_norm}#{srd}")
            for scr in role_cfg.get("silent_cross_role_deps", []):
                silent_deps.append(f"{u_norm}#{scr}")

        for sr in role_cfg.get("star_role_deps", []):
            if sr != role_name:
                implied = f"//{pkg_dir}:{unit_name}#{sr}"
                if implied not in direct_deps:
                    direct_deps.append(implied)

        if not role_cfg.get("src_pattern"):
            for fd in feedback_deps:
                if fd not in direct_deps:
                    direct_deps.append(fd)

        v_success_msg = None
        if "verification_success_message" in role_cfg and role_cfg["verification_success_message"]:
            try:
                v_success_msg = role_cfg["verification_success_message"].format(
                    unit_name=unit_name, unit_dir=pkg_dir
                )
            except Exception:
                v_success_msg = role_cfg["verification_success_message"]

        manifest = manifest_loader.TargetManifest(
            label=manifest_loader.TargetLabel(f"//{pkg_dir}:{unit_name}#{role_name}"),
            task_prompt=task_prompt,
            source_file=src_file,
            silent_source_files=(),
            template=manifest_loader.file_alias.FileContent(role_cfg["template"]) if role_cfg.get("template") else None,
            dependencies=tuple(manifest_loader.TargetLabel(d) for d in direct_deps + [sd for sd in star_deps if sd not in direct_deps]),
            silent_dependencies=tuple(manifest_loader.TargetLabel(d) for d in silent_deps),
            star_dependencies=tuple(manifest_loader.TargetLabel(d) for d in star_deps),
            feedback_dependencies=tuple(manifest_loader.TargetLabel(d) for d in feedback_deps),
            guide_target=guide_target,
            verification_check=verification_check,
            allows_step_mode=role_cfg.get("allows_step_mode", True),
            verification_success_message=v_success_msg,
        )
        self._manifests[node] = manifest
        return manifest

    def _resolve_dependency_node(self, label: str) -> dag_storage.DagNode:
        """Resolves a declared dependency target label into its graph node."""
        try:
            target_service = get_singleton(target.UvTarget)
        except (LifecycleResolutionError, KeyError, LookupError, RuntimeError):
            target_service = None
        if target_service is not None:
            return target_service.normalize_target(target.TargetIdentifier(label))
        unit_address, _, role_address = label.partition("#")
        return dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress(unit_address),
            role_address=dag_storage.RoleAddress(role_address),
        )

    def _synthesize_dependency_definition(
        self, storage: Any, node: dag_storage.DagNode
    ) -> None:
        """Synthesizes a promptless node definition for a dependency without a manifest."""
        # Legitimate reflection: optional capability detection on dynamic storage backend
        store_definition = getattr(storage, "store_node_definition", None)
        if callable(store_definition):
            store_definition(
                node,
                node_storage.NodeDefinition(
                    task_prompt=node_storage.TaskPrompt(""),
                ),
            )

    # Contract: populate agent storage with node definitions carrying task prompts
    # Contract: record declared primary source file paths in agent storage without duplicating package path segments
    # Contract: record silent source file paths in agent storage without duplicating package path segments
    # Contract: register declared direct dependencies in agent storage
    # Contract: register declared feedback dependencies in agent storage
    # Contract: register declared silent dependencies as non-propagating dependencies in agent storage
    # Contract: synthesize fallback node definitions for referenced targets lacking manifests
    def load_manifest(self, node: dag_storage.DagNode) -> None:
        manifest = self.retrieve_manifest(node)
        if not manifest:
            return

        try:
            storage = get_singleton(node_storage.AgentStorage)
        except (LifecycleResolutionError, KeyError, LookupError, RuntimeError):
            storage = None

        if storage is not None:
            storage_any: Any = storage
            prompt_str = manifest.task_prompt if manifest.task_prompt is not None else ""
            node_def = node_storage.NodeDefinition(
                task_prompt=node_storage.TaskPrompt(str(prompt_str)),
            )
            if hasattr(storage_any, "store_node_definition"):
                storage_any.store_node_definition(node, node_def)

            if manifest.source_file is not None and hasattr(storage_any, "record_source_file"):
                storage_any.record_source_file(node, str(manifest.source_file))

            if manifest.silent_source_files and hasattr(
                storage_any, "store_silent_source_files"
            ):
                storage_any.store_silent_source_files(
                    node,
                    tuple(str(path) for path in manifest.silent_source_files),
                )

            if hasattr(storage_any, "store_dependencies"):
                dag_deps: Set[dag_storage.DagDependency] = set()
                for d_label in manifest.dependencies:
                    dep_node = self._resolve_dependency_node(str(d_label))
                    is_silent = d_label in manifest.silent_dependencies
                    if not is_silent:
                        dep_manifest = self.retrieve_manifest(dep_node)
                        if dep_manifest is None:
                            # A referenced target without a manifest still receives a fallback
                            # definition, but the declared direct dependency must propagate.
                            self._synthesize_dependency_definition(storage_any, dep_node)
                        elif dep_manifest.task_prompt is None:
                            # Promptless pass-through synthesized because the unit component type
                            # is not active for its role: non-propagating per the contract.
                            is_silent = True
                    dag_deps.add(
                        dag_storage.DagDependency(
                            node=dep_node,
                            is_silent=is_silent,
                        )
                    )
                for d_label in manifest.silent_dependencies:
                    dep_node = self._resolve_dependency_node(str(d_label))
                    if self.retrieve_manifest(dep_node) is None:
                        self._synthesize_dependency_definition(storage_any, dep_node)
                    dag_deps.add(
                        dag_storage.DagDependency(
                            node=dep_node,
                            is_silent=True,
                        )
                    )
                storage_any.store_dependencies(node, dag_deps)

            if hasattr(storage_any, "store_feedback_dependencies"):
                fb_nodes: Set[dag_storage.DagNode] = {
                    self._resolve_dependency_node(str(fb_label))
                    for fb_label in manifest.feedback_dependencies
                }
                storage_any.store_feedback_dependencies(node, fb_nodes)
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:42:33Z
# CHANGE: Keep declared direct dependencies propagating when their manifest cannot be discovered, synthesizing only the fallback definition and reserving non-propagation for declared silent and promptless pass-through dependencies
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        UvManifestLoader,
        keys=[UvManifestLoader, manifest_loader.UvManifestLoader],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
