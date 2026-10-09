# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 10aacce70297
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

import os
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import tomllib

from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.core.lib import file_paths
from . import uv_manifest_loader
from . import uv_target
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)

try:
    from update_with_ai.parts.bazel.lib import bazel_manifest_loader
except ImportError:
    bazel_manifest_loader = None  # type: ignore


class UvManifestLoader(uv_manifest_loader.UvManifestLoader, Singleton):
    tier = system

    def __init__(self) -> None:
        self._manifests: Dict[dag_storage.DagNode, uv_manifest_loader.TargetManifest] = {}
        self._methodology_roles: Dict[str, Tuple[str, Dict[str, Dict[str, Any]]]] = {}
        self._unit_locations: Dict[str, Dict[str, str]] = {}

    def _get_workspace_root(self) -> str:
        try:
            fp_mgr: Any = get_singleton(file_paths.FilePathManager)
            if fp_mgr and hasattr(fp_mgr, "get_workspace_root"):
                return str(fp_mgr.get_workspace_root().path)
        except Exception:
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
                except Exception:
                    pass
            curr_parent = os.path.dirname(curr)
            if curr == root_abs or curr == curr_parent or not curr.startswith(root_abs):
                break
            curr = curr_parent
        return "//update_python_with_ai"

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
            except Exception:
                toml_path = os.path.join(root, meth, "cleanroom_roles.toml")

        roles: Dict[str, Dict[str, Any]] = {}
        if os.path.isfile(toml_path):
            try:
                with open(toml_path, "rb") as f:
                    data = tomllib.load(f)
                r_dict = data.get("roles")
                roles = r_dict if isinstance(r_dict, dict) else {}
            except Exception:
                roles = {}

        result = (canon_meth, roles)
        self._methodology_roles[meth] = result
        return result

    def _find_parts_root(self, root: str, pkg_dir: str) -> Optional[str]:
        norm_pkg = pkg_dir.replace("\\", "/").strip("/")
        if "/parts/" in norm_pkg:
            return norm_pkg.split("/parts/")[0] + "/parts"
        elif norm_pkg.startswith("parts/"):
            return "parts"
        elif norm_pkg.endswith("/parts"):
            return norm_pkg
        for cand in ("staging/parts", "update_with_ai/parts", "parts"):
            if os.path.isdir(os.path.join(root, cand)):
                return cand
        return None

    def _get_unit_to_pkg_map(self, root: str, parts_prefix: str) -> Dict[str, str]:
        if parts_prefix in self._unit_locations:
            return self._unit_locations[parts_prefix]
        unit_map: Dict[str, str] = {}
        parts_abs = os.path.join(root, parts_prefix)
        if os.path.isdir(parts_abs):
            for sub in sorted(os.listdir(parts_abs)):
                sub_dir = os.path.join(parts_abs, sub)
                if not os.path.isdir(sub_dir) or sub.startswith("."):
                    continue
                high_dir = os.path.join(sub_dir, "high")
                if os.path.isdir(high_dir):
                    for h_file in os.listdir(high_dir):
                        if h_file.endswith(".md") and not h_file.startswith("."):
                            u_name = h_file[:-3]
                            unit_map[u_name] = f"//{parts_prefix}/{sub}"
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

        parts_prefix = self._find_parts_root(root, pkg_dir)
        if parts_prefix:
            u_map = self._get_unit_to_pkg_map(root, parts_prefix)
            if clean_name in u_map:
                return f"{u_map[clean_name]}:{clean_name}"

        for cand_scope in ("staging/parts", "update_with_ai/parts", "parts"):
            u_map = self._get_unit_to_pkg_map(root, cand_scope)
            if clean_name in u_map:
                return f"{u_map[clean_name]}:{clean_name}"

        return f"//{pkg_dir}:{clean_name}"

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
        except Exception:
            pass
        return info

    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[uv_manifest_loader.TargetManifest]:
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

            manifest = uv_manifest_loader.TargetManifest(
                label=uv_manifest_loader.TargetLabel(f"//{pkg_dir}:{unit_name}#{role_name}"),
                dependencies=tuple(uv_manifest_loader.TargetLabel(d) for d in deps_list),
                silent_dependencies=tuple(uv_manifest_loader.TargetLabel(d) for d in silent_deps_list),
                star_dependencies=tuple(uv_manifest_loader.TargetLabel(d) for d in deps_list),
                feedback_dependencies=(),
                allows_step_mode=False,
            )
            self._manifests[node] = manifest
            return manifest

        src_pattern = role_cfg.get("src_pattern", "")
        src_file = None
        if src_pattern:
            src_file = uv_manifest_loader.agent_file_alias.RelativePath(
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
            task_prompt = agent_storage.TaskPrompt(prompt_text)

        verify_template = role_cfg.get("verify_template", "")
        verification_check = None
        if verify_template:
            verification_check = uv_manifest_loader.VerificationCommand(
                verify_template.format(unit_dir=pkg_dir, unit_name=unit_name)
            )

        guide_target = None
        guide_str = role_cfg.get("guide", "")
        if guide_str:
            guide_target = uv_manifest_loader.TargetLabel(guide_str)

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

        manifest = uv_manifest_loader.TargetManifest(
            label=uv_manifest_loader.TargetLabel(f"//{pkg_dir}:{unit_name}#{role_name}"),
            task_prompt=task_prompt,
            source_file=src_file,
            silent_source_files=(),
            template=uv_manifest_loader.agent_file_alias.FileContent(role_cfg["template"]) if role_cfg.get("template") else None,
            dependencies=tuple(uv_manifest_loader.TargetLabel(d) for d in direct_deps + [sd for sd in star_deps if sd not in direct_deps]),
            silent_dependencies=tuple(uv_manifest_loader.TargetLabel(d) for d in silent_deps),
            star_dependencies=tuple(uv_manifest_loader.TargetLabel(d) for d in star_deps),
            feedback_dependencies=tuple(uv_manifest_loader.TargetLabel(d) for d in feedback_deps),
            guide_target=guide_target,
            verification_check=verification_check,
            allows_step_mode=role_cfg.get("allows_step_mode", True),
        )
        self._manifests[node] = manifest
        return manifest

    def load_manifest(self, node: dag_storage.DagNode) -> None:
        manifest = self.retrieve_manifest(node)
        if not manifest:
            return

        try:
            storage = get_singleton(agent_storage.AgentStorage)
        except Exception:
            storage = None

        if storage is not None:
            storage_any: Any = storage
            prompt_str = manifest.task_prompt if manifest.task_prompt is not None else ""
            node_def = agent_storage.NodeDefinition(
                task_prompt=agent_storage.TaskPrompt(str(prompt_str)),
            )
            if hasattr(storage_any, "store_node_definition"):
                storage_any.store_node_definition(node, node_def)

            if manifest.source_file is not None and hasattr(storage_any, "record_source_file"):
                storage_any.record_source_file(node, str(manifest.source_file))

            if hasattr(storage_any, "store_dependencies"):
                dag_deps: Set[dag_storage.DagDependency] = set()
                target_service = None
                try:
                    target_service = get_singleton(uv_target.UvTarget)
                except Exception:
                    pass

                for d_label in manifest.dependencies:
                    dep_node = (
                        target_service.normalize_target(uv_target.TargetIdentifier(d_label))
                        if target_service
                        else dag_storage.DagNode(
                            unit_address=dag_storage.UnitAddress(d_label.split("#")[0]),
                            role_address=dag_storage.RoleAddress(d_label.split("#")[1] if "#" in d_label else ""),
                        )
                    )
                    is_silent = d_label in manifest.silent_dependencies
                    dag_deps.add(
                        dag_storage.DagDependency(
                            node=dep_node,
                            is_silent=is_silent,
                        )
                    )
                for d_label in manifest.silent_dependencies:
                    dep_node = (
                        target_service.normalize_target(uv_target.TargetIdentifier(d_label))
                        if target_service
                        else dag_storage.DagNode(
                            unit_address=dag_storage.UnitAddress(d_label.split("#")[0]),
                            role_address=dag_storage.RoleAddress(d_label.split("#")[1] if "#" in d_label else ""),
                        )
                    )
                    dag_deps.add(
                        dag_storage.DagDependency(
                            node=dep_node,
                            is_silent=True,
                        )
                    )
                storage_any.store_dependencies(node, dag_deps)

            if hasattr(storage_any, "store_feedback_dependencies"):
                fb_nodes: Set[dag_storage.DagNode] = set()
                if manifest.feedback_dependencies:
                    target_service = None
                    try:
                        target_service = get_singleton(uv_target.UvTarget)
                    except Exception:
                        pass
                    for fb_label in manifest.feedback_dependencies:
                        fb_node = (
                            target_service.normalize_target(uv_target.TargetIdentifier(fb_label))
                            if target_service
                            else dag_storage.DagNode(
                                unit_address=dag_storage.UnitAddress(fb_label.split("#")[0]),
                                role_address=dag_storage.RoleAddress(fb_label.split("#")[1] if "#" in fb_label else ""),
                            )
                        )
                        fb_nodes.add(fb_node)
                storage_any.store_feedback_dependencies(node, fb_nodes)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    keys = [UvManifestLoader, uv_manifest_loader.UvManifestLoader]
    if bazel_manifest_loader is not None and hasattr(bazel_manifest_loader, "BazelManifestLoader"):
        keys.append(bazel_manifest_loader.BazelManifestLoader)
    reg.register_singleton(
        UvManifestLoader,
        keys=keys,
        tier=system,
    )
