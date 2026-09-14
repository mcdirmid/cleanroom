import json
import os
from typing import Any, Dict, List, Optional, Sequence, Set, cast
from update_with_ai.parts.agent.lib import agent_storage
from . import bazel_manifest_loader
from . import bazel_target
from update_with_ai.parts.dag.lib import dag_storage
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)


class BazelManifestLoader(bazel_manifest_loader.BazelManifestLoader, Singleton):
    tier = "system"

    def __init__(self) -> None:
        self._manifests: Dict[dag_storage.Node, bazel_manifest_loader.Manifest] = {}

    def _find_file(self, pkg_path: str, filename: str) -> Optional[str]:
        candidates = [
            os.path.join(pkg_path, filename),
            os.path.join("bazel-bin", pkg_path, filename),
            filename,
        ]
        for base in (
            os.environ.get("RUNFILES_DIR", ""),
            os.environ.get("BAZEL_RUNFILES", ""),
        ):
            if base:
                candidates.extend(
                    [
                        os.path.join(base, filename),
                        os.path.join(base, "_main", filename),
                        os.path.join(base, "cleanroom", filename),
                        os.path.join(base, "_main", pkg_path, filename),
                        os.path.join(base, "cleanroom", pkg_path, filename),
                        os.path.join(base, pkg_path, filename),
                    ]
                )
        for path in candidates:
            if os.path.exists(path) and os.path.isfile(path):
                return path
        return None

    def get_manifest(
        self, node: dag_storage.Node
    ) -> Optional[bazel_manifest_loader.Manifest]:
        # Check in-memory cache first
        if node in self._manifests:
            return self._manifests[node]

        # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
        # Requirement: [BazelManifestLoader] The bazel manifest loader retrieves the manifest for a node in dag storage.
        node_util = get_singleton(bazel_target.BazelTarget)
        pkg_dir = node_util.extract_directory(node)
        unit_name = (
            node.unit_address.split(":")[-1]
            if ":" in node.unit_address
            else os.path.basename(node.unit_address)
        )

        if node.role_address:
            role_name = (
                node.role_address.split(":")[-1]
                if ":" in node.role_address
                else os.path.basename(node.role_address)
            )
            # Check for direct node manifest first
            node_manifest_file = f"{unit_name}_{role_name}_manifest.json"
            path = self._find_file(pkg_dir.path, node_manifest_file)
            if not path:
                path = self._find_file(pkg_dir.path, f".{node_manifest_file}")
            if path:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        raw_str = f.read()
                        raw_data = json.loads(raw_str)
                        if "unit_data" in raw_data and "role_data" in raw_data:
                            m = bazel_manifest_loader.Manifest(raw_str)
                            self._manifests[node] = m
                            return m
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    pass

            # Check for unit manifest and role manifest
            unit_file = self._find_file(pkg_dir.path, f"{unit_name}_unit_manifest.json")
            if not unit_file:
                unit_file = self._find_file(pkg_dir.path, f".{unit_name}_unit_manifest.json")
            if not unit_file:
                unit_file = self._find_file(pkg_dir.path, f"{unit_name}_manifest.json")
            if not unit_file:
                unit_file = self._find_file(pkg_dir.path, f".{unit_name}_manifest.json")

            role_node = dag_storage.Node(
                unit_address=node.role_address, role_address=""
            )
            role_pkg = node_util.extract_directory(role_node).path
            role_file = self._find_file(role_pkg, f"{role_name}_role_manifest.json")
            if not role_file:
                role_file = self._find_file(role_pkg, f".{role_name}_role_manifest.json")
            if not role_file:
                role_file = self._find_file(role_pkg, f"{role_name}_manifest.json")
            if not role_file:
                role_file = self._find_file(role_pkg, f".{role_name}_manifest.json")

            if unit_file and role_file:
                try:
                    with open(unit_file, "r", encoding="utf-8") as uf:
                        unit_data = json.load(uf)
                    with open(role_file, "r", encoding="utf-8") as rf:
                        role_data = json.load(rf)

                    unit_name = (
                        unit_data.get("name")
                        or unit_data.get("unit_name")
                        or node.unit_address.split(":")[-1]
                    )
                    unit_dir = (
                        unit_data.get("dir")
                        or unit_data.get("unit_dir")
                        or pkg_dir.path.lstrip("/")
                    )
                    src_pattern = role_data.get("src_pattern", "")
                    try:
                        src_val = src_pattern.format(
                            unit_dir=unit_dir, unit_name=unit_name
                        )
                    except Exception:
                        src_val = src_pattern

                    verify_tmpl = role_data.get("verify_template", "")
                    try:
                        verify_val = verify_tmpl.format(
                            unit_dir=unit_dir, unit_name=unit_name
                        )
                    except Exception:
                        verify_val = verify_tmpl

                    v_msg_tmpl = role_data.get("verification_success_message", "")
                    try:
                        v_msg_val = v_msg_tmpl.format(
                            unit_dir=unit_dir, unit_name=unit_name
                        )
                    except Exception:
                        v_msg_val = v_msg_tmpl

                    component_type = unit_data.get("component_type", "implementation")
                    active_types = role_data.get(
                        "active_component_types",
                        ["implementation", "assembly", "interface", "external"],
                    )

                    role_pkg = (
                        node.role_address.split(":")[0]
                        if ":" in node.role_address
                        else "//update_python_with_ai"
                    )

                    def _resolve_role_label(r_label: str) -> str:
                        if r_label.startswith(":"):
                            return f"{role_pkg}{r_label}"
                        return node_util.normalize(r_label).unit_address

                    deps_list: List[str] = []
                    feedback_deps_list: List[str] = []
                    silent_deps_list: List[str] = []
                    star_deps_list: List[str] = []

                    raw_unit_deps = unit_data.get("unit_deps", unit_data.get("deps", []))

                    if component_type in active_types:
                        # 1. Intra-unit role dependencies
                        for r_dep in role_data.get("role_deps", []):
                            dep_role = _resolve_role_label(r_dep)
                            deps_list.append(f"{node.unit_address}#{dep_role}")

                        # 2. Intra-unit feedback dependencies
                        for r_dep in role_data.get("feedback_role_deps", []):
                            dep_role = _resolve_role_label(r_dep)
                            feedback_deps_list.append(f"{node.unit_address}#{dep_role}")
                            if f"{node.unit_address}#{dep_role}" not in deps_list:
                                deps_list.append(f"{node.unit_address}#{dep_role}")

                        # 3. Intra-unit silent dependencies
                        for r_dep in role_data.get("silent_role_deps", []):
                            dep_role = _resolve_role_label(r_dep)
                            silent_deps_list.append(f"{node.unit_address}#{dep_role}")

                        # 4. Cross-unit dependencies
                        for u_dep in raw_unit_deps:
                            u_norm = node_util.normalize(u_dep).unit_address
                            for sr in role_data.get("star_role_deps", []):
                                sr_norm = _resolve_role_label(sr)
                                star_deps_list.append(f"{u_norm}#{sr_norm}")
                            for scr in role_data.get("silent_cross_role_deps", []):
                                scr_norm = _resolve_role_label(scr)
                                if scr_norm.endswith("lib") and u_norm.endswith("_ext"):
                                    continue
                                silent_deps_list.append(f"{u_norm}#{scr_norm}")

                        if role_data.get("guide"):
                            deps_list.append(role_data["guide"])
                    else:
                        # Pass-through node dependencies
                        src_val = ""
                        verify_val = ""
                        v_msg_val = ""
                        for u_dep in raw_unit_deps:
                            u_norm = node_util.normalize(u_dep).unit_address
                            deps_list.append(f"{u_norm}#{node.role_address}")
                        for r_dep in role_data.get("role_deps", []):
                            dep_role = _resolve_role_label(r_dep)
                            deps_list.append(f"{node.unit_address}#{dep_role}")
                        for r_dep in role_data.get("silent_role_deps", []):
                            dep_role = _resolve_role_label(r_dep)
                            silent_deps_list.append(f"{node.unit_address}#{dep_role}")

                    # Requirement: A manifest loader synthesizes target node manifests with templates, template parameters, declared dependencies, feedback dependencies, silent dependencies, and star dependencies across unit and role dimensions.
                    synthesized = {
                        "unit": node.unit_address,
                        "role": node.role_address,
                        "unit_data": unit_data,
                        "role_data": role_data,
                        "src": src_val,
                        "template": role_data.get("template"),
                        "template_parameters": {
                            "unit_name": unit_name,
                            "unit_dir": unit_dir,
                            "name": unit_name,
                            "dir": unit_dir,
                        },
                        "guide": role_data.get("guide"),
                        "allows_step_mode": role_data.get("allows_step_mode", True),
                        "verify": verify_val,
                        "verification_success_message": v_msg_val,
                        "deps": deps_list,
                        "feedback_deps": feedback_deps_list,
                        "silent_deps": silent_deps_list,
                        "star_deps": star_deps_list,
                    }
                    m = bazel_manifest_loader.Manifest(json.dumps(synthesized))
                    self._manifests[node] = m
                    return m
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    pass

        # Fallback for nodes without role or legacy single manifests
        manifest_filename = f"{unit_name}_manifest.json"
        path = self._find_file(pkg_dir.path, manifest_filename)
        if not path:
            path = self._find_file(pkg_dir.path, ".manifest.json")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    m = bazel_manifest_loader.Manifest(f.read())
                    self._manifests[node] = m
                    return m
            except (OSError, UnicodeDecodeError):
                pass

        return None

    def load_manifest(
        self,
        content: bazel_manifest_loader.Manifest,
        storage: agent_storage.AgentStorage,
    ) -> Sequence[agent_storage.NodeDefinition]:
        # Requirement: A manifest loader parses JSON manifests using the filesystem into json manifest records.
        data = json.loads(str(content))
        node_util = get_singleton(bazel_target.BazelTarget)
        results: List[agent_storage.NodeDefinition] = []

        if isinstance(data, dict) and "unit_data" in data and "role_data" in data:
            # Requirement: A manifest loader resolves target manifests by loading unit manifests and role manifests to synthesize node definitions and dependencies across unit and role dimensions.
            unit_data = data["unit_data"]
            role_data = data["role_data"]
            unit_addr = (
                data.get("unit")
                or node_util.normalize(unit_data.get("label", "")).unit_address
            )
            role_addr = (
                data.get("role")
                or node_util.normalize(role_data.get("label", "")).unit_address
            )
            node = dag_storage.Node(unit_address=unit_addr, role_address=role_addr)

            unit_name = (
                unit_data.get("name")
                or unit_data.get("unit_name")
                or unit_addr.split(":")[-1]
            )
            unit_dir = (
                unit_data.get("dir")
                or unit_data.get("unit_dir")
                or node_util.extract_directory(node).path
            )
            component_type = unit_data.get("component_type", "implementation")
            is_impl = component_type == "implementation" or unit_name.endswith("_impl")
            is_asm = component_type == "assembly" or unit_name.endswith("_asm")

            if is_impl:
                lib_kind_clause = "This is an implementation module: it realizes concrete singleton classes and functions defined in the grounding specification."
            elif is_asm:
                lib_kind_clause = "This is an assembly module: it wires concrete implementations into configured interface components and provides the assembled result."
            else:
                lib_kind_clause = "This is an interface module: it defines the interface's protocol and types."

            role_pkg = (
                role_addr.split(":")[0]
                if ":" in role_addr
                else "//update_python_with_ai"
            )

            def _resolve_role(r_label: str) -> str:
                if r_label.startswith(":"):
                    return f"{role_pkg}{r_label}"
                return node_util.normalize(r_label).unit_address

            active_types = role_data.get(
                "active_component_types",
                ["implementation", "assembly", "interface", "external"],
            )
            is_active = component_type in active_types
            if not is_active:
                # Requirement: A manifest loader synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.
                prompt = agent_storage.TaskPrompt("")
                defn = agent_storage.NodeDefinition(node=node, task_prompt=prompt)
                results.append(defn)
                self._manifests[node] = content
                storage_any = cast(Any, storage)
                if hasattr(storage_any, "_definitions"):
                    storage_any._definitions[node] = defn
                deps: Set[dag_storage.Dependency] = set()
                raw_unit_deps = unit_data.get("unit_deps", unit_data.get("deps", []))
                for u_dep in raw_unit_deps:
                    u_norm = node_util.normalize(u_dep).unit_address
                    deps.add(
                        dag_storage.Dependency(
                            node=dag_storage.Node(
                                unit_address=u_norm, role_address=role_addr
                            ),
                            is_silent=False,
                        )
                    )
                for r_dep in role_data.get("role_deps", []):
                    dep_role = _resolve_role(r_dep)
                    deps.add(
                        dag_storage.Dependency(
                            node=dag_storage.Node(
                                unit_address=unit_addr, role_address=dep_role
                            ),
                            is_silent=False,
                        )
                    )
                for r_dep in role_data.get("silent_role_deps", []):
                    dep_role = _resolve_role(r_dep)
                    deps.add(
                        dag_storage.Dependency(
                            node=dag_storage.Node(
                                unit_address=unit_addr, role_address=dep_role
                            ),
                            is_silent=True,
                        )
                    )
                if hasattr(storage_any, "_dependencies"):
                    storage_any._dependencies[node] = deps
                return results

            # Requirement: A manifest loader evaluates role source patterns and task prompt templates parameterized with unit metadata to configure synthesized nodes.
            prompt_tmpl = role_data.get("prompt_template", "")
            fmt_kwargs = {
                "unit_dir": unit_dir,
                "unit_name": unit_name,
                "lib_kind_clause": lib_kind_clause,
                "component_name": unit_name,
                "component_type": component_type,
            }
            try:
                prompt_text = prompt_tmpl.format(**fmt_kwargs)
            except Exception:
                prompt_text = prompt_tmpl

            prompt = agent_storage.TaskPrompt(prompt_text)
            defn = agent_storage.NodeDefinition(node=node, task_prompt=prompt)
            results.append(defn)
            self._manifests[node] = content

            storage_any = cast(Any, storage)
            if hasattr(storage_any, "_definitions"):
                storage_any._definitions[node] = defn

            src_pattern = role_data.get("src_pattern", "")
            if src_pattern:
                try:
                    src_file = src_pattern.format(
                        unit_dir=unit_dir, unit_name=unit_name
                    )
                except Exception:
                    src_file = src_pattern
                if hasattr(storage_any, "_source_files"):
                    storage_any._source_files[node] = os.path.normpath(src_file)

            deps: Set[dag_storage.Dependency] = set()

            # 1. Intra-unit role dependencies
            for r_dep in role_data.get("role_deps", []):
                dep_role = _resolve_role(r_dep)
                deps.add(
                    dag_storage.Dependency(
                        node=dag_storage.Node(
                            unit_address=unit_addr, role_address=dep_role
                        ),
                        is_silent=False,
                    )
                )

            # 2. Intra-unit silent role dependencies
            for r_dep in role_data.get("silent_role_deps", []):
                dep_role = _resolve_role(r_dep)
                deps.add(
                    dag_storage.Dependency(
                        node=dag_storage.Node(
                            unit_address=unit_addr, role_address=dep_role
                        ),
                        is_silent=True,
                    )
                )

            # 3. Cross-unit dependencies
            raw_unit_deps = unit_data.get("unit_deps", unit_data.get("deps", []))
            star_roles = role_data.get("star_role_deps", [])
            silent_cross_roles = role_data.get("silent_cross_role_deps", [])

            for u_dep in raw_unit_deps:
                u_norm = node_util.normalize(u_dep).unit_address
                for sr in star_roles:
                    sr_norm = _resolve_role(sr)
                    deps.add(
                        dag_storage.Dependency(
                            node=dag_storage.Node(
                                unit_address=u_norm, role_address=sr_norm
                            ),
                            is_silent=False,
                        )
                    )
                for scr in silent_cross_roles:
                    scr_norm = _resolve_role(scr)
                    if scr_norm.endswith("lib") and u_norm.endswith("_ext"):
                        continue
                    deps.add(
                        dag_storage.Dependency(
                            node=dag_storage.Node(
                                unit_address=u_norm, role_address=scr_norm
                            ),
                            is_silent=True,
                        )
                    )

            if hasattr(storage_any, "_dependencies"):
                storage_any._dependencies[node] = deps

            return results

        targets = data.get("targets", [data]) if isinstance(data, dict) else []
        for t in targets:
            label = t.get("label", "")
            # Requirement: A manifest loader normalizes node references into canonical nodes using node identifier utilities.
            node = node_util.normalize(label)
            # Cache the manifest for this node
            self._manifests[node] = bazel_manifest_loader.Manifest(
                json.dumps(t) if "targets" in data else str(content)
            )

            prompt = agent_storage.TaskPrompt(t.get("prompt", t.get("task_prompt", "")))
            defn = agent_storage.NodeDefinition(node=node, task_prompt=prompt)
            results.append(defn)

            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the agent storage.
            storage_any = cast(Any, storage)
            if hasattr(storage_any, "_definitions"):
                storage_any._definitions[node] = defn

            src = t.get("src")
            if src and hasattr(storage_any, "_source_files"):
                pkg_path = node_util.extract_directory(node).path
                norm_rel = os.path.normpath(os.path.join(pkg_path, src))
                storage_any._source_files[node] = norm_rel

            # Requirement: A manifest loader registers silent dependencies as non-propagating dependencies excluding their source files.
            # Requirement: [BazelManifestLoader] A manifest loader resolves declared silent dependencies as non-propagating dependencies while excluding their source files from read-only files.
            deps = set()
            for dep_label in t.get("deps", []):
                dep_node = node_util.normalize(dep_label)
                deps.add(dag_storage.Dependency(node=dep_node, is_silent=False))
            for dep_label in t.get("silent_deps", []):
                dep_node = node_util.normalize(dep_label)
                deps.add(dag_storage.Dependency(node=dep_node, is_silent=True))

            if hasattr(storage_any, "_dependencies"):
                storage_any._dependencies[node] = deps

        return results


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        BazelManifestLoader,
        keys=[BazelManifestLoader, bazel_manifest_loader.BazelManifestLoader],
        tier="system",
    )
