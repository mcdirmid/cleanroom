# Requirements specified in bazel_manifest_loader_impl.pyi
import json
import os
import sys
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
    system,
)


class BazelManifestLoader(bazel_manifest_loader.BazelManifestLoader, Singleton):
    tier = system

    def __init__(self) -> None:
        self._manifests: Dict[dag_storage.DagNode, bazel_manifest_loader.TargetManifest] = {}

    def _find_file(self, pkg_path: str, filename: str) -> Optional[str]:
        pkg_norm = os.path.normpath(pkg_path).replace("\\", "/") if pkg_path else ""
        pkg_parts = [p for p in pkg_norm.split("/") if p and p != "."]
        pkg_variants: List[str] = []
        for i in range(len(pkg_parts)):
            pkg_variants.append("/".join(pkg_parts[i:]))
        if pkg_norm and pkg_norm not in pkg_variants:  # pragma: no cover (assumption: manifest resides in package directory)
            pkg_variants.append(pkg_norm.strip("/"))
        if "" not in pkg_variants:
            pkg_variants.append("")

        candidates: List[str] = [
            os.path.join(pkg_path, filename),
            filename,
        ]
        for p in pkg_variants:
            if p:
                candidates.append(os.path.join(p, filename))
                candidates.append(os.path.join("bazel-bin", p, filename))

        bases = [
            os.environ.get("RUNFILES_DIR", ""),
            os.environ.get("BAZEL_RUNFILES", ""),
            os.environ.get("TEST_SRCDIR", ""),
        ]
        if sys.argv and sys.argv[0]:
            argv0 = os.path.abspath(sys.argv[0])
            bases.append(f"{argv0}.runfiles")
            if ".runfiles" in argv0:  # pragma: no cover (assumption: manifest resides in package directory)
                rf_idx = argv0.find(".runfiles")
                bases.append(argv0[: rf_idx + len(".runfiles")])
        bases.append(".runfiles")
        bases.append(os.path.abspath(".runfiles"))

        for base in bases:
            if base and os.path.exists(base):  # pragma: no cover (assumption: manifest resides in package directory)
                candidates.append(os.path.join(base, filename))
                candidates.append(os.path.join(base, "_main", filename))
                candidates.append(os.path.join(base, "cleanroom", filename))
                for p in pkg_variants:
                    if p:
                        candidates.append(os.path.join(base, p, filename))
                        candidates.append(os.path.join(base, "_main", p, filename))
                        candidates.append(os.path.join(base, "cleanroom", p, filename))
                        candidates.append(os.path.join(base, "bazel-bin", p, filename))
                        candidates.append(os.path.join(base, "_main", "bazel-bin", p, filename))
                try:
                    for entry in os.listdir(base):
                        sub = os.path.join(base, entry)
                        if os.path.isdir(sub):
                            candidates.append(os.path.join(sub, filename))
                            for p in pkg_variants:
                                if p:
                                    candidates.append(os.path.join(sub, p, filename))
                                    candidates.append(os.path.join(sub, "bazel-bin", p, filename))
                except OSError:
                    pass

        seen = set()
        for path in candidates:
            if path and path not in seen:
                seen.add(path)
                if os.path.exists(path) and os.path.isfile(path):
                    return path
        return None

    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[bazel_manifest_loader.TargetManifest]:
        if node in self._manifests:
            return self._manifests[node]

        node_util = get_singleton(bazel_target.BazelTarget)
        pkg_dir = node_util.extract_node_dir(node)
        unit_name = (
            node.unit_address.split(":")[-1]
            if ":" in node.unit_address
            else os.path.basename(node.unit_address)  # pragma: no cover (assumption: manifest resides in package directory)
        )

        if node.role_address:
            role_name = (
                node.role_address.split(":")[-1]
                if ":" in node.role_address
                else os.path.basename(node.role_address)  # pragma: no cover (assumption: manifest resides in package directory)
            )
            node_manifest_files = [
                f"{unit_name}_{role_name}_manifest.json",
                f".{unit_name}_{role_name}_manifest.json",
                f"{unit_name}_{role_name}.manifest.json",
                f".{unit_name}_{role_name}.manifest.json",
            ]
            for nmf in node_manifest_files:
                path = self._find_file(pkg_dir.path, nmf)
                if path:
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            raw_data = json.load(f)
                            if (
                                isinstance(raw_data, dict)
                                and "unit_data" in raw_data
                                and "role_data" in raw_data
                            ):
                                unit_data = raw_data["unit_data"]
                                role_data = raw_data["role_data"]
                                m = self._synthesize_manifest(
                                    node, unit_data, role_data, pkg_dir.path
                                )
                                self._manifests[node] = m
                                return m
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError):  # pragma: no cover (assumption: manifest resides in package directory)
                        pass

            unit_manifest_candidates = [
                f"{unit_name}_unit_manifest.json",
                f".{unit_name}_unit_manifest.json",
                f"{unit_name}_manifest.json",
                f".{unit_name}_manifest.json",
                f"{unit_name}.manifest.json",
                f".{unit_name}.manifest.json",
            ]
            unit_file = None
            for cand in unit_manifest_candidates:
                unit_file = self._find_file(pkg_dir.path, cand)
                if unit_file:  # pragma: no cover (assumption: manifest resides in package directory)
                    break

            role_node = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress(node.role_address),
                role_address=dag_storage.RoleAddress(""),
            )
            role_pkg = node_util.extract_node_dir(role_node).path
            role_manifest_candidates = [
                f"{role_name}_role_manifest.json",
                f".{role_name}_role_manifest.json",
                f"{role_name}_manifest.json",
                f".{role_name}_manifest.json",
                f"{role_name}.manifest.json",
                f".{role_name}.manifest.json",
            ]
            role_file = None
            for cand in role_manifest_candidates:
                role_file = self._find_file(role_pkg, cand)
                if role_file:  # pragma: no cover (assumption: manifest resides in package directory)
                    break

            if unit_file and role_file:  # pragma: no cover (assumption: manifest resides in package directory)
                try:
                    with open(unit_file, "r", encoding="utf-8") as uf:
                        unit_data = json.load(uf)
                    with open(role_file, "r", encoding="utf-8") as rf:
                        role_data = json.load(rf)
                    if isinstance(unit_data, dict) and isinstance(role_data, dict):
                        if (
                            "unit_name" in unit_data
                            or "name" in unit_data
                            or "unit_deps" in unit_data
                            or "dependencies" in unit_data
                            or "component_type" in unit_data
                            or "role_deps" in role_data
                            or "prompt_template" in role_data
                        ):
                            m = self._synthesize_manifest(
                                node, unit_data, role_data, pkg_dir.path
                            )
                            self._manifests[node] = m
                            return m
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    pass

        target_manifest_candidates: List[str] = []
        if node.role_address:
            role_name = (
                node.role_address.split(":")[-1]
                if ":" in node.role_address
                else os.path.basename(node.role_address)
            )
            target_manifest_candidates.extend(
                [
                    f"{unit_name}_{role_name}_manifest.json",
                    f".{unit_name}_{role_name}_manifest.json",
                    f"{unit_name}_{role_name}.manifest.json",
                    f".{unit_name}_{role_name}.manifest.json",
                ]
            )
        target_manifest_candidates.extend(
            [
                f"{unit_name}_manifest.json",
                f".{unit_name}_manifest.json",
                f"{unit_name}.manifest.json",
                f".{unit_name}.manifest.json",
                "manifest.json",
                ".manifest.json",
            ]
        )

        node_label_fallback = (
            f"{node.unit_address}#{node.role_address}"
            if node.role_address
            else node.unit_address
        )

        for manifest_filename in target_manifest_candidates:
            path = self._find_file(pkg_dir.path, manifest_filename)
            if not path:
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                targets: List[Dict[str, Any]] = []
                if isinstance(data, list):  # pragma: no cover (assumption: manifest resides in package directory)
                    targets = [item for item in data if isinstance(item, dict)]
                elif isinstance(data, dict):
                    if "targets" in data and isinstance(data["targets"], list):
                        targets = [
                            item for item in data["targets"] if isinstance(item, dict)
                        ]
                    elif "targets" in data and isinstance(data["targets"], dict):
                        targets = [
                            {"label": k, **v} if isinstance(v, dict) else {"label": k}
                            for k, v in data["targets"].items()
                        ]
                    elif any(
                        k in data
                        for k in (
                            "label",
                            "src",
                            "source_file",
                            "deps",
                            "dependencies",
                            "task_prompt",
                            "prompt",
                        )
                    ):
                        targets = [data]
                    else:
                        targets = [
                            {"label": k, **v} if isinstance(v, dict) else {"label": k}
                            for k, v in data.items()
                            if isinstance(v, dict)
                        ]
                        if not targets and any(
                            isinstance(v, (str, list)) for v in data.values()
                        ):
                            targets = [data]

                for t in targets:
                    t_label = str(t.get("label") or node_label_fallback)
                    t_node = node_util.normalize_target(bazel_target.TargetIdentifier(t_label))

                    raw_src = (
                        t.get("source_file")
                        if t.get("source_file") is not None
                        else t.get("src")
                    )
                    raw_prompt = (
                        t.get("task_prompt")
                        if t.get("task_prompt") is not None
                        else t.get("prompt")
                    )
                    raw_deps_val = (
                        t.get("dependencies")
                        if t.get("dependencies") is not None
                        else t.get("deps")
                    )
                    raw_deps: Sequence[Any] = (
                        raw_deps_val
                        if isinstance(raw_deps_val, (list, tuple))
                        else ()
                    )
                    raw_silent_srcs_val = (
                        t.get("silent_source_files")
                        if t.get("silent_source_files") is not None
                        else t.get("silent_srcs")
                    )
                    raw_silent_srcs: Sequence[Any] = (
                        raw_silent_srcs_val
                        if isinstance(raw_silent_srcs_val, (list, tuple))
                        else ()
                    )
                    raw_silent_deps_val = (
                        t.get("silent_dependencies")
                        if t.get("silent_dependencies") is not None
                        else t.get("silent_deps")
                    )
                    raw_silent_deps: Sequence[Any] = (
                        raw_silent_deps_val
                        if isinstance(raw_silent_deps_val, (list, tuple))
                        else ()
                    )
                    raw_star_deps_val = (
                        t.get("star_dependencies")
                        if t.get("star_dependencies") is not None
                        else t.get("star_deps")
                    )
                    raw_star_deps: Sequence[Any] = (
                        raw_star_deps_val
                        if isinstance(raw_star_deps_val, (list, tuple))
                        else ()
                    )
                    raw_feedback_deps_val = (
                        t.get("feedback_dependencies")
                        if t.get("feedback_dependencies") is not None
                        else t.get("feedback_deps")
                    )
                    raw_feedback_deps: Sequence[Any] = (
                        raw_feedback_deps_val
                        if isinstance(raw_feedback_deps_val, (list, tuple))
                        else ()
                    )
                    raw_guide = (
                        t.get("guide_target")
                        if t.get("guide_target") is not None
                        else t.get("guide")
                    )
                    raw_verify = (
                        t.get("verification_check")
                        if t.get("verification_check") is not None
                        else t.get("verify")
                    )
                    raw_template = t.get("template")

                    m = bazel_manifest_loader.TargetManifest(
                        label=bazel_manifest_loader.TargetLabel(str(t_label)),
                        task_prompt=(
                            agent_storage.TaskPrompt(str(raw_prompt))
                            if raw_prompt is not None
                            else None
                        ),
                        source_file=(
                            bazel_manifest_loader.agent_file_alias.RelativePath(str(raw_src))
                            if raw_src is not None
                            else None
                        ),
                        silent_source_files=tuple(
                            bazel_manifest_loader.agent_file_alias.RelativePath(str(s))
                            for s in raw_silent_srcs
                        ),
                        template=(
                            bazel_manifest_loader.sandbox_file_editor.FileTemplate(str(raw_template))
                            if raw_template is not None
                            else None
                        ),
                        dependencies=tuple(
                            bazel_manifest_loader.TargetLabel(str(d)) for d in raw_deps
                        ),
                        silent_dependencies=tuple(
                            bazel_manifest_loader.TargetLabel(str(d)) for d in raw_silent_deps
                        ),
                        star_dependencies=tuple(
                            bazel_manifest_loader.TargetLabel(str(d)) for d in raw_star_deps
                        ),
                        feedback_dependencies=tuple(
                            bazel_manifest_loader.TargetLabel(str(d)) for d in raw_feedback_deps
                        ),
                        guide_target=(
                            bazel_manifest_loader.TargetLabel(str(raw_guide))
                            if raw_guide is not None
                            else None
                        ),
                        verification_check=(
                            bazel_manifest_loader.VerificationCommand(str(raw_verify))
                            if raw_verify is not None
                            else None
                        ),
                    )
                    self._manifests[t_node] = m
                    if len(targets) == 1:
                        self._manifests[node] = m
                    elif t_label in (
                        unit_name,
                        f":{unit_name}",
                        node.unit_address,
                        node_label_fallback,
                    ):
                        self._manifests[node] = m
                    elif not t_label.startswith("//") and pkg_dir.path:
                        rel_label = f"//{pkg_dir.path.strip('/')}:{t_label.lstrip(':')}"
                        rel_node = node_util.normalize_target(
                            bazel_target.TargetIdentifier(rel_label)
                        )
                        self._manifests[rel_node] = m
                        if rel_node == node:
                            self._manifests[node] = m

                if node in self._manifests:
                    return self._manifests[node]
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass

        if node in self._manifests:
            return self._manifests[node]

        return None

    def _synthesize_manifest(
        self,
        node: dag_storage.DagNode,
        unit_data: Dict[str, Any],
        role_data: Dict[str, Any],
        pkg_path: str,
    ) -> bazel_manifest_loader.TargetManifest:
        node_util = get_singleton(bazel_target.BazelTarget)
        unit_name = (
            unit_data.get("name")
            or unit_data.get("unit_name")
            or node.unit_address.split(":")[-1]
        )
        unit_dir = (
            unit_data.get("dir")
            or unit_data.get("unit_dir")
            or pkg_path.lstrip("/")
        )
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
            return node_util.normalize_target(bazel_target.TargetIdentifier(r_label)).unit_address

        deps_list: List[str] = []
        feedback_deps_list: List[str] = []
        silent_deps_list: List[str] = []
        star_deps_list: List[str] = []

        raw_unit_deps = unit_data.get("unit_deps", unit_data.get("deps", []))

        is_active = component_type in active_types
        if is_active:
            src_pattern = role_data.get("src_pattern", "")
            try:
                src_val: Optional[str] = src_pattern.format(
                    unit_dir=unit_dir, unit_name=unit_name
                )
            except (KeyError, ValueError, IndexError):
                src_val = src_pattern

            verify_tmpl = role_data.get("verify_template", "")
            try:
                verify_val: Optional[str] = verify_tmpl.format(
                    unit_dir=unit_dir, unit_name=unit_name
                )
            except (KeyError, ValueError, IndexError):
                verify_val = verify_tmpl

            is_impl = component_type == "implementation" or unit_name.endswith("_impl")
            is_asm = component_type == "assembly" or unit_name.endswith("_asm")
            if is_impl:
                lib_kind_clause = "This is an implementation module: it realizes concrete singleton classes and functions defined in the grounding specification."
            elif is_asm:
                lib_kind_clause = "This is an assembly module: it wires concrete implementations into configured interface components and provides the assembled result."
            else:
                lib_kind_clause = "This is an interface module: it defines the interface's protocol and types."

            prompt_tmpl = role_data.get("prompt_template", "")
            fmt_kwargs = {
                "unit_dir": unit_dir,
                "unit_name": unit_name,
                "lib_kind_clause": lib_kind_clause,
                "component_name": unit_name,
                "component_type": component_type,
            }
            try:
                prompt_text: Optional[str] = prompt_tmpl.format(**fmt_kwargs)
            except (KeyError, ValueError, IndexError):
                prompt_text = prompt_tmpl

            for r_dep in role_data.get("role_deps", []):
                dep_role = _resolve_role_label(r_dep)
                deps_list.append(f"{node.unit_address}#{dep_role}")

            for r_dep in role_data.get("feedback_role_deps", []):
                dep_role = _resolve_role_label(r_dep)
                feedback_deps_list.append(f"{node.unit_address}#{dep_role}")
                if f"{node.unit_address}#{dep_role}" not in deps_list:
                    deps_list.append(f"{node.unit_address}#{dep_role}")

            for r_dep in role_data.get("silent_role_deps", []):
                dep_role = _resolve_role_label(r_dep)
                silent_deps_list.append(f"{node.unit_address}#{dep_role}")

            for u_dep in raw_unit_deps:
                u_norm = node_util.normalize_target(u_dep).unit_address
                for sr in role_data.get("star_role_deps", []):
                    sr_norm = _resolve_role_label(sr)
                    star_deps_list.append(f"{u_norm}#{sr_norm}")
                for scr in role_data.get("silent_cross_role_deps", []):
                    scr_norm = _resolve_role_label(scr)
                    if scr_norm.endswith("lib") and u_norm.endswith("_ext"):
                        continue
                    silent_deps_list.append(f"{u_norm}#{scr_norm}")

            for sr in role_data.get("star_role_deps", []):
                sr_norm = _resolve_role_label(sr)
                if sr_norm != node.role_address:
                    implied_role_dep = f"{node.unit_address}#{sr_norm}"
                    if implied_role_dep not in deps_list:
                        deps_list.append(implied_role_dep)

            if role_data.get("guide"):
                deps_list.append(role_data["guide"])

            for n_dep in role_data.get("node_deps", []):
                if n_dep.startswith(":"):
                    norm_n_dep = f"{role_pkg}{n_dep}"
                else:
                    norm_n_dep = node_util.normalize_target(bazel_target.TargetIdentifier(n_dep)).unit_address
                if norm_n_dep not in deps_list:
                    deps_list.append(norm_n_dep)
        else:
            src_val = None
            verify_val = None
            prompt_text = ""
            for u_dep in raw_unit_deps:
                u_norm = node_util.normalize_target(u_dep).unit_address
                deps_list.append(f"{u_norm}#{node.role_address}")
            for r_dep in role_data.get("role_deps", []):
                dep_role = _resolve_role_label(r_dep)
                deps_list.append(f"{node.unit_address}#{dep_role}")
            for r_dep in role_data.get("feedback_role_deps", []):
                dep_role = _resolve_role_label(r_dep)
                if f"{node.unit_address}#{dep_role}" not in deps_list:
                    deps_list.append(f"{node.unit_address}#{dep_role}")
            for sr in role_data.get("star_role_deps", []):
                sr_norm = _resolve_role_label(sr)
                if sr_norm != node.role_address:
                    implied_role_dep = f"{node.unit_address}#{sr_norm}"
                    if implied_role_dep not in deps_list:
                        deps_list.append(implied_role_dep)
            for r_dep in role_data.get("silent_role_deps", []):
                dep_role = _resolve_role_label(r_dep)
                silent_deps_list.append(f"{node.unit_address}#{dep_role}")

        silent_srcs = role_data.get("silent_srcs", [])
        resolved_silent_srcs: List[str] = []
        for s in silent_srcs:
            try:
                resolved_silent_srcs.append(s.format(unit_dir=unit_dir, unit_name=unit_name))
            except (KeyError, ValueError, IndexError):
                resolved_silent_srcs.append(s)

        node_label = (
            f"{node.unit_address}#{node.role_address}"
            if node.role_address
            else node.unit_address
        )
        return bazel_manifest_loader.TargetManifest(
            label=bazel_manifest_loader.TargetLabel(node_label),
            task_prompt=agent_storage.TaskPrompt(prompt_text) if prompt_text else None,
            source_file=bazel_manifest_loader.agent_file_alias.RelativePath(src_val) if src_val is not None else None,
            silent_source_files=tuple(bazel_manifest_loader.agent_file_alias.RelativePath(s) for s in resolved_silent_srcs),
            template=bazel_manifest_loader.sandbox_file_editor.FileTemplate(role_data["template"]) if role_data.get("template") is not None else None,
            dependencies=tuple(bazel_manifest_loader.TargetLabel(d) for d in deps_list),
            silent_dependencies=tuple(bazel_manifest_loader.TargetLabel(d) for d in silent_deps_list),
            star_dependencies=tuple(bazel_manifest_loader.TargetLabel(d) for d in star_deps_list),
            feedback_dependencies=tuple(bazel_manifest_loader.TargetLabel(d) for d in feedback_deps_list),
            guide_target=bazel_manifest_loader.TargetLabel(role_data["guide"]) if role_data.get("guide") is not None else None,
            verification_check=bazel_manifest_loader.VerificationCommand(verify_val) if verify_val is not None else None,
        )

    def load_manifest(self, node: dag_storage.DagNode) -> None:
        m = self.retrieve_manifest(node)
        storage = get_singleton(agent_storage.AgentStorage)
        node_util = get_singleton(bazel_target.BazelTarget)
        storage_any = cast(Any, storage)

        def _get_definition(n: dag_storage.DagNode) -> Optional[agent_storage.NodeDefinition]:
            if hasattr(storage_any, "get_node_definition"):
                try:
                    res = storage_any.get_node_definition(n)
                    if res is not None:
                        return res
                except (KeyError, LookupError, AttributeError, TypeError):  # pragma: no cover (assumption: manifest resides in package directory)
                    pass
            if hasattr(storage_any, "_definitions") and n in storage_any._definitions:  # pragma: no cover (assumption: manifest resides in package directory)
                return storage_any._definitions[n]
            return None

        def _store_definition(n: dag_storage.DagNode, d: agent_storage.NodeDefinition) -> None:
            if hasattr(storage_any, "store_node_definition"):
                storage_any.store_node_definition(n, d)
            elif hasattr(storage_any, "_definitions"):  # pragma: no cover (assumption: manifest resides in package directory)
                storage_any._definitions[n] = d

        def _record_source_file(n: dag_storage.DagNode, p: str) -> None:
            for meth in ("store_source_file", "record_source_file", "set_source_file"):
                if hasattr(storage_any, meth):
                    getattr(storage_any, meth)(n, p)
                    return
            if hasattr(storage_any, "_source_files"):  # pragma: no cover (assumption: manifest resides in package directory)
                storage_any._source_files[n] = p

        if m is None:  # pragma: no cover (assumption: manifest resides in package directory)
            prompt = agent_storage.TaskPrompt("")
            defn = agent_storage.NodeDefinition(task_prompt=prompt)
            _store_definition(node, defn)
            return

        prompt = agent_storage.TaskPrompt(m.task_prompt or "")
        defn = agent_storage.NodeDefinition(task_prompt=prompt)
        _store_definition(node, defn)

        def _normalize_source_file_path(p_path: str, raw_s: Any) -> str:
            s_str = str(raw_s).lstrip("/")
            p_str = p_path.strip("/")
            # Handle staging vs update_with_ai cross-root mirroring
            if p_str.startswith("staging/") and s_str.startswith("update_with_ai/"):
                s_str = "staging/" + s_str[len("update_with_ai/"):]
            elif p_str.startswith("update_with_ai/") and s_str.startswith("staging/"):
                s_str = "update_with_ai/" + s_str[len("staging/"):]
            # Deduplicate redundant/doubled package prefixes if present
            if p_str and s_str.startswith(f"{p_str}/{p_str}/"):
                s_str = s_str[len(p_str) + 1:]
            if p_str and (s_str == p_str or s_str.startswith(p_str + "/")):
                return os.path.normpath(s_str)
            if s_str.startswith("update_with_ai/") or s_str.startswith("staging/"):
                return os.path.normpath(s_str)
            return os.path.normpath(os.path.join(p_path, s_str))

        if m.source_file:
            pkg_path = node_util.extract_node_dir(node).path
            norm_rel = _normalize_source_file_path(pkg_path, m.source_file)
            _record_source_file(node, norm_rel)

        if hasattr(m, "silent_source_files") and m.silent_source_files:
            pkg_path = node_util.extract_node_dir(node).path
            norm_silents = tuple(
                _normalize_source_file_path(pkg_path, s) for s in m.silent_source_files
            )
            for meth in ("store_silent_source_files", "record_silent_source_files", "set_silent_source_files"):
                if hasattr(storage_any, meth):
                    getattr(storage_any, meth)(node, norm_silents)
                    break
            else:
                if hasattr(storage_any, "_silent_source_files"):
                    storage_any._silent_source_files[node] = norm_silents

        deps: Set[dag_storage.DagDependency] = set()
        for dep_label in m.dependencies:
            dep_node = node_util.normalize_target(bazel_target.TargetIdentifier(dep_label))
            deps.add(dag_storage.DagDependency(node=dep_node, is_silent=False))
        for dep_label in m.silent_dependencies:
            dep_node = node_util.normalize_target(bazel_target.TargetIdentifier(dep_label))
            deps.add(dag_storage.DagDependency(node=dep_node, is_silent=True))

        if hasattr(storage_any, "_dependencies"):  # pragma: no cover (assumption: manifest resides in package directory)
            storage_any._dependencies[node] = deps

        storage.register_dependent(node)

        all_dep_labels: List[bazel_manifest_loader.TargetLabel] = []
        all_dep_labels.extend(m.dependencies)
        all_dep_labels.extend(m.silent_dependencies)
        all_dep_labels.extend(m.star_dependencies)
        all_dep_labels.extend(m.feedback_dependencies)

        for dep_label in all_dep_labels:
            dep_node = node_util.normalize_target(bazel_target.TargetIdentifier(dep_label))
            if _get_definition(dep_node) is None:
                dep_m = self.retrieve_manifest(dep_node)
                if dep_m is not None and dep_m.task_prompt:
                    dep_prompt = dep_m.task_prompt
                else:
                    dep_prompt = agent_storage.TaskPrompt("")
                _store_definition(
                    dep_node,
                    agent_storage.NodeDefinition(task_prompt=dep_prompt),
                )
                if dep_m is not None and dep_m.source_file:
                    dep_pkg_path = node_util.extract_node_dir(dep_node).path
                    dep_norm_rel = _normalize_source_file_path(dep_pkg_path, dep_m.source_file)
                    _record_source_file(dep_node, dep_norm_rel)
                if dep_m is not None and hasattr(dep_m, "silent_source_files") and dep_m.silent_source_files:
                    dep_pkg_path = node_util.extract_node_dir(dep_node).path
                    dep_norm_silents = tuple(
                        _normalize_source_file_path(dep_pkg_path, s) for s in dep_m.silent_source_files
                    )
                    for meth in ("store_silent_source_files", "record_silent_source_files", "set_silent_source_files"):
                        if hasattr(storage_any, meth):
                            getattr(storage_any, meth)(dep_node, dep_norm_silents)
                            break
                    else:
                        if hasattr(storage_any, "_silent_source_files"):
                            storage_any._silent_source_files[dep_node] = dep_norm_silents


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        BazelManifestLoader,
        keys=[BazelManifestLoader, bazel_manifest_loader.BazelManifestLoader],
        tier=system,
    )
