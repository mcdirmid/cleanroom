# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T18:18:00Z
# CHANGE: support label resolution and role template fallbacks in materialize_template
# CODE_HASH: 5d0a7834f272
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage
from . import src_metadata
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_active_scope,
    get_ambient_system_scope,
    get_default_registry,
    get_singleton,
    system,
)

AUDITOR_ROLE_TAGS: Mapping[str, str] = {
    "spec_qa": "SPEC_QA_AUDIT",
    "low_qa": "LOW_QA_AUDIT",
    "qa": "QA_AUDIT",
    "coverage": "COVERAGE_AUDIT",
    "grounding_qa": "GROUNDING_QA_AUDIT",
}


def is_auditor_role(role_name: str) -> bool:
    return role_name in AUDITOR_ROLE_TAGS


class _RoleDefFallback:
    def __init__(
        self,
        template: str = "",
        template_command: str = "",
        src_pattern: str = "",
    ) -> None:
        self.template = template
        self.template_command = template_command
        self.src_pattern = src_pattern


class AgentStorage(agent_storage.AgentStorage, Singleton):
    tier = system

    def __init__(self) -> None:
        self._definitions: Dict[dag_storage.DagNode, agent_storage.NodeDefinition] = {}
        self._dependencies: Dict[
            dag_storage.DagNode, Set[dag_storage.DagDependency]
        ] = {}
        self._feedback_dependencies: Dict[
            dag_storage.DagNode, Set[dag_storage.DagNode]
        ] = {}
        self._source_files: Dict[dag_storage.DagNode, str] = {}
        self._silent_source_files: Dict[dag_storage.DagNode, Tuple[str, ...]] = {}
        self._messages: Dict[dag_storage.DagNode, Set[dag_storage.DagMessage]] = {}

    def _get_manifest_loader(self) -> Optional[Any]:
        try:
            reg = get_default_registry()
            scope = get_active_scope() or get_ambient_system_scope()
            for proto in getattr(reg, "_prototypes", {}).values():
                for desc in getattr(proto, "_descriptors", []):
                    if getattr(desc.impl, "__name__", "") in ("UvManifestLoader", "BazelManifestLoader"):
                        if desc.impl is not None:
                            return scope.get(desc.impl)
        except (LookupError, AttributeError, TypeError, ValueError, KeyError):
            pass
        return None

    def _ensure_manifest_loaded(self, node: dag_storage.DagNode) -> None:
        if node in self._source_files:
            return
        manifest_loader = self._get_manifest_loader()
        if manifest_loader is not None:
            try:
                manifest_loader.load_manifest(node)
            except (LifecycleResolutionError, LookupError, AttributeError, RuntimeError, OSError):
                pass

    def _resolve_source_path(self, node: dag_storage.DagNode) -> Optional[Path]:
        self._ensure_manifest_loaded(node)
        rel_path = self._source_files.get(node)
        if rel_path is None:
            addr = str(node.unit_address).strip().lstrip("/")
            if "/" in addr and ("." in addr.split("/")[-1]):
                rel_path = addr
            else:
                return None
        root_str = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
        try:
            paths_service = get_singleton(file_paths.FilePathManager)
            root = file_paths.WorkspaceRoot(file_paths.PathString(root_str))
            resolved = paths_service.resolve_path(
                root, file_paths.WorkspacePath(file_paths.PathString(rel_path))
            )
            return Path(resolved.path)
        except (LifecycleResolutionError, LookupError, AttributeError, ValueError, OSError):
            return Path(os.path.abspath(os.path.join(root_str, rel_path)))

    def get_node_definition(
        self, node: dag_storage.DagNode
    ) -> agent_storage.NodeDefinition:
        self._ensure_manifest_loaded(node)
        if node in self._definitions:
            return self._definitions[node]
        return agent_storage.NodeDefinition(
            task_prompt=agent_storage.TaskPrompt("")
        )

    def store_node_definition(
        self, node: dag_storage.DagNode, definition: agent_storage.NodeDefinition
    ) -> None:
        self._definitions[node] = definition

    def get_task_prompt(
        self, node: dag_storage.DagNode
    ) -> agent_storage.TaskPrompt:
        return self.get_node_definition(node).task_prompt

    def record_source_file(self, node: dag_storage.DagNode, path: str) -> None:
        norm_path = path.lstrip("/")
        self._source_files[node] = norm_path

    def store_dependencies(
        self, node: dag_storage.DagNode, dependencies: Set[dag_storage.DagDependency]
    ) -> None:
        self._dependencies[node] = set(dependencies)

    def get_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagDependency]:
        self._ensure_manifest_loaded(node)
        return set(self._dependencies.get(node, set()))

    def store_silent_source_files(
        self, node: dag_storage.DagNode, paths: Tuple[str, ...]
    ) -> None:
        self._silent_source_files[node] = tuple(paths)

    def store_feedback_dependencies(
        self, node: dag_storage.DagNode, feedback_dependencies: Set[dag_storage.DagNode]
    ) -> None:
        self._feedback_dependencies[node] = set(feedback_dependencies)

    def get_feedback_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagNode]:
        self._ensure_manifest_loaded(node)
        if node in self._feedback_dependencies:
            return set(self._feedback_dependencies[node])
        role_name = node.role_address.split(":")[-1]
        if is_auditor_role(role_name):
            raise KeyError(
                f"No feedback dependencies configured for auditor node '{node}'"
            )
        return set()

    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        messages: Set[dag_storage.DagMessage] = set(self._messages.get(node, set()))
        role_name = node.role_address.split(":")[-1]
        if is_auditor_role(role_name):
            if self.is_dirty(node) and not messages:
                messages.add(
                    dag_storage.ChangeMessage(
                        content=dag_storage.MessageContent(
                            f"audit {role_name} for {node.unit_address}"
                        )
                    )
                )
            return messages

        src_path = self._resolve_source_path(node)
        if src_path is not None:
            if not src_path.is_file():
                src_rel = self._source_files.get(node, node.unit_address)
                messages.add(
                    dag_storage.ChangeMessage(
                        content=dag_storage.MessageContent(f"implement {src_rel}")
                    )
                )
            else:
                meta = src_metadata.extract_metadata(src_path)
                if meta is not None:
                    if meta.dirty:
                        messages.add(
                            dag_storage.ChangeMessage(
                                content=dag_storage.MessageContent(meta.dirty)
                            )
                        )
                    for fb in meta.feedback:
                        messages.add(
                            dag_storage.FeedbackMessage(
                                content=dag_storage.MessageContent(fb)
                            )
                        )
                    for dep in self.get_dependencies(node):
                        if not dep.is_silent:
                            dep_src = self._resolve_source_path(dep.node)
                            if dep_src is not None and dep_src.is_file():
                                dep_meta = src_metadata.extract_metadata(dep_src)
                                if (
                                    dep_meta
                                    and dep_meta.last_changed
                                    and meta.last_cleaned
                                    and meta.last_cleaned < dep_meta.last_changed
                                ):
                                    desc = dep_meta.change_summary or "updated"
                                    messages.add(
                                        dag_storage.ChangeMessage(
                                            content=dag_storage.MessageContent(
                                                f"dependency {dep.node.unit_address} changed: {desc}"
                                            )
                                        )
                                    )
        return messages

    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        role_name = node.role_address.split(":")[-1]
        if is_auditor_role(role_name):
            if len(self._messages.get(node, set())) > 0:
                return True
            audit_tag = AUDITOR_ROLE_TAGS[role_name]
            feedback_deps = self.get_feedback_dependencies(node)
            if not feedback_deps:
                deps = self.get_dependencies(node)
                if deps:
                    return any(self.is_dirty(dep.node) for dep in deps if not dep.is_silent)
                return False

            contract_deps = [
                d
                for d in self.get_dependencies(node)
                if not d.is_silent and d.node not in feedback_deps
            ]

            for fb_dep in feedback_deps:
                fb_src = self._resolve_source_path(fb_dep)
                if fb_src is None or not fb_src.is_file():
                    return True

                if self.is_dirty(fb_dep):
                    return True

                meta = src_metadata.extract_metadata(fb_src)
                if meta is None or not meta.last_changed:
                    return True

                audit_ts = meta.audits.get(audit_tag)
                if not audit_ts:
                    return True

                if audit_ts < meta.last_changed:
                    return True

                for c_dep in contract_deps:
                    c_src = self._resolve_source_path(c_dep.node)
                    if c_src is not None and c_src.is_file():
                        c_meta = src_metadata.extract_metadata(c_src)
                        if (
                            c_meta
                            and c_meta.last_changed
                            and audit_ts < c_meta.last_changed
                        ):
                            return True
            return False

        src_path = self._resolve_source_path(node)
        if src_path is None:
            deps = self.get_dependencies(node)
            if deps:
                return any(self.is_dirty(dep.node) for dep in deps if not dep.is_silent)
            return len(self.get_messages(node)) > 0

        if not src_path.is_file():
            src_rel = self._source_files.get(node, node.unit_address)
            content = f"implement {src_rel}"
            msgs = self._messages.get(node, set())
            if not any(
                isinstance(m, (dag_storage.ChangeMessage, dag_storage.FeedbackMessage))
                and m.content == content
                for m in msgs
            ):
                self.add_message(
                    dag_storage.ChangeMessage(
                        content=dag_storage.MessageContent(content)
                    ),
                    to=node,
                )
            return True

        meta = src_metadata.extract_metadata(src_path)
        if meta is None or not meta.last_cleaned:
            return True
        if meta.dirty:
            return True
        if meta.feedback:
            return True
        for dep in self.get_dependencies(node):
            if not dep.is_silent:
                dep_src = self._resolve_source_path(dep.node)
                if dep_src is not None and dep_src.is_file():
                    dep_meta = src_metadata.extract_metadata(dep_src)
                    if (
                        dep_meta
                        and dep_meta.last_changed
                        and meta.last_cleaned < dep_meta.last_changed
                    ):
                        return True
        return len(self._messages.get(node, set())) > 0

    def add_feedback_message(
        self, node: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        src_path = self._resolve_source_path(node)
        if src_path is not None and src_path.is_file():
            content_str = (
                str(message.content) if message.content else "unspecified feedback"
            )
            src_metadata.append_feedback(src_path, content_str)
            return
        self._messages.setdefault(node, set()).add(message)

    def add_message(
        self, message: dag_storage.DagMessage, to: dag_storage.DagNode
    ) -> None:
        if isinstance(message, dag_storage.FeedbackMessage):
            self.add_feedback_message(to, message)
            return
        src_path = self._resolve_source_path(to)
        if src_path is not None and src_path.is_file():
            if isinstance(message, dag_storage.ChangeMessage):
                content_str = (
                    str(message.content) if message.content else "manual dirty"
                )
                src_metadata.update_metadata(
                    src_path, dirty=content_str, clear_last_cleaned=True
                )
                return
        self._messages.setdefault(to, set()).add(message)

    def mark_node_dirty(
        self, node: dag_storage.DagNode, reason: Optional[str] = None
    ) -> None:
        role_name = node.role_address.split(":")[-1]
        if is_auditor_role(role_name):
            audit_tag = AUDITOR_ROLE_TAGS[role_name]
            for fb_dep in self.get_feedback_dependencies(node):
                fb_src = self._resolve_source_path(fb_dep)
                if fb_src is not None and fb_src.is_file():
                    meta = src_metadata.extract_metadata(fb_src)
                    if meta and audit_tag in meta.audits:
                        new_audits = {
                            k: v for k, v in meta.audits.items() if k != audit_tag
                        }
                        src_metadata.update_metadata(fb_src, audits=new_audits)
            if reason:
                self._messages.setdefault(node, set()).add(
                    dag_storage.ChangeMessage(
                        content=dag_storage.MessageContent(reason)
                    )
                )
            return

        src_path = self._resolve_source_path(node)
        if src_path is not None and src_path.is_file():
            if reason:
                src_metadata.update_metadata(
                    src_path, dirty=reason, clear_last_cleaned=True
                )
            else:
                src_metadata.delete_last_cleaned(src_path)
            return

        msg = reason if reason else "dirty"
        self._messages.setdefault(node, set()).add(
            dag_storage.ChangeMessage(content=dag_storage.MessageContent(msg))
        )

    def mark_subgraph_clean(self, node: dag_storage.DagNode) -> None:
        visited: Set[dag_storage.DagNode] = set()
        order: list[dag_storage.DagNode] = []

        def dfs(n: dag_storage.DagNode) -> None:
            if n in visited:
                return
            visited.add(n)
            for dep in self.get_dependencies(n):
                dfs(dep.node)
            role_name = n.role_address.split(":")[-1]
            if is_auditor_role(role_name):
                for fb_dep in self.get_feedback_dependencies(n):
                    dfs(fb_dep)
            order.append(n)

        dfs(node)

        for n in order:
            self.materialize_template(n)
            self.mark_node_clean(n)

    def clear_messages(self, node: dag_storage.DagNode) -> None:
        self._messages[node] = set()

    def mark_node_clean(
        self,
        node: dag_storage.DagNode,
        change_description: Optional[dag_storage.ChangeDescription] = None,
    ) -> None:
        self.clear_messages(node)
        role_name = node.role_address.split(":")[-1]
        if is_auditor_role(role_name):
            for fb_dep in self.get_feedback_dependencies(node):
                fb_src = self._resolve_source_path(fb_dep)
                if fb_src is not None and fb_src.is_file():
                    src_metadata.stamp_audit(fb_src, role_name)
            return

        src_path = self._resolve_source_path(node)
        if src_path is not None and src_path.is_file():
            if change_description is not None:
                src_metadata.record_change(src_path, str(change_description))
            else:
                src_metadata.mark_clean(src_path)

    def materialize_template(self, node: dag_storage.DagNode) -> None:
        src_path = self._resolve_source_path(node)
        if src_path is None or src_path.is_file():
            return

        clean_role = node.role_address.split(":")[-1].strip().lower()
        bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
        role_def: Any = None
        main_repo = None

        search_roots = [bwd]
        cur = bwd
        while cur and cur != os.path.dirname(cur):
            search_roots.append(cur)
            cur = os.path.dirname(cur)

        import tomllib

        for root in search_roots:
            for fname in ("cleanroom_roles.toml", "cleanroom_python_roles.toml"):
                t_path = os.path.join(root, fname)
                if os.path.isfile(t_path):
                    try:
                        with open(t_path, "rb") as f:
                            data = tomllib.load(f)
                        r_info = data.get("roles", {}).get(clean_role, {})
                        if r_info:
                            role_def = _RoleDefFallback(
                                template=r_info.get("template", ""),
                                template_command=r_info.get("template_command", ""),
                                src_pattern=r_info.get("src_pattern", ""),
                            )
                            main_repo = root
                            break
                    except (tomllib.TOMLDecodeError, OSError):
                        pass
            if role_def is not None:
                break

        if role_def and getattr(role_def, "template_command", ""):
            unit_str = str(node.unit_address).strip()
            unit_stem = os.path.splitext(os.path.basename(unit_str))[0]
            unit_name = unit_stem[:-5] if unit_stem.endswith("_test") else unit_stem
            unit_dir = ""
            if ":" in unit_str:
                unit_dir = unit_str.split(":", 1)[0].lstrip("/")
            else:
                rel_p = str(src_path)
                bwd_str = str(bwd)
                if rel_p.startswith(bwd_str):
                    rel_p = os.path.relpath(rel_p, bwd_str)
                p_dir = os.path.dirname(rel_p)
                for sfx in ("/lib", "/tests", "/low", "/high", "/planning"):
                    if p_dir.endswith(sfx):
                        p_dir = p_dir[:-len(sfx)]
                        break
                unit_dir = p_dir

            target_rel = (
                os.path.relpath(str(src_path), bwd)
                if str(src_path).startswith(bwd)
                else str(src_path)
            )
            try:
                cmd = role_def.template_command.format(
                    unit_dir=unit_dir,
                    unit_name=unit_name,
                    target_file=target_rel,
                )
                env = dict(os.environ)
                env["BUILD_WORKSPACE_DIRECTORY"] = bwd
                if main_repo:
                    env["UV_PROJECT"] = main_repo
                pypaths = [bwd]
                if main_repo and main_repo not in pypaths:
                    pypaths.append(main_repo)
                for root_cand in (main_repo, bwd):
                    if not root_cand or not os.path.isdir(root_cand):
                        continue
                    if unit_dir:
                        ud_full = os.path.join(root_cand, unit_dir)
                        if os.path.isdir(ud_full):
                            pypaths.append(ud_full)
                    try:
                        for entry in os.listdir(root_cand):
                            pkg_dir = os.path.join(root_cand, entry)
                            if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv", "__pycache__")):
                                sup_lib = os.path.join(pkg_dir, "support", "lib")
                                if os.path.isdir(sup_lib):
                                    pypaths.append(pkg_dir)
                                    pypaths.append(sup_lib)
                    except OSError:
                        pass
                if "PYTHONPATH" in env and env["PYTHONPATH"]:
                    pypaths.append(env["PYTHONPATH"])
                env["PYTHONPATH"] = ":".join(p for p in pypaths if p)
                src_path.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    cmd,
                    shell=True,
                    cwd=bwd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if src_path.is_file():
                    return
            except (subprocess.SubprocessError, OSError):
                pass

        manifest_loader = self._get_manifest_loader()
        tmpl_content = ""
        if manifest_loader is not None:
            m = manifest_loader.retrieve_manifest(node)
            if m is not None and getattr(m, "template", None) is not None:
                tmpl_str = str(m.template)
                tmpl_candidates = [
                    tmpl_str,
                    os.path.join(
                        os.environ.get("BUILD_WORKSPACE_DIRECTORY", ""), tmpl_str
                    ),
                ]
                if tmpl_str.startswith("//"):
                    pkg_sub = tmpl_str[2:].replace(":", "/")
                    tmpl_candidates.append(pkg_sub)
                    tmpl_candidates.append(
                        os.path.join(
                            os.environ.get("BUILD_WORKSPACE_DIRECTORY", ""), pkg_sub
                        )
                    )
                    tmpl_name = None
                    if "templates:hls" in tmpl_str:
                        tmpl_name = "hls_template.md"
                    elif "templates:lib" in tmpl_str:
                        tmpl_name = "lib_template.py"
                    elif "templates:test" in tmpl_str:
                        tmpl_name = "test_template.py"
                    if tmpl_name:
                        bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
                        tmpl_candidates.append(os.path.join(bwd, "templates", tmpl_name))
                        try:
                            for entry in os.listdir(bwd):
                                pkg_dir = os.path.join(bwd, entry)
                                if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                                    tmpl_candidates.append(os.path.join(pkg_dir, "templates", tmpl_name))
                        except OSError:
                            pass
                for cand in tmpl_candidates:
                    if os.path.isfile(cand):
                        try:
                            with open(cand, "r", encoding="utf-8") as f:
                                tmpl_content = f.read()
                            break
                        except OSError:
                            pass
                else:
                    tmpl_content = tmpl_str
        if not tmpl_content:
            clean_role = node.role_address.split(":")[-1].strip().lower()
            bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
            roots = [bwd]
            if main_repo and main_repo not in roots:
                roots.append(main_repo)
            cands = []
            if role_def and getattr(role_def, "template", ""):
                t_spec = role_def.template
                for r in roots:
                    cands.append(os.path.join(r, t_spec))
                cands.append(t_spec)

            role_to_filename = {
                "high": "hls_template.md",
                "planning": "planning_template.md",
                "low": "low_template.pyi",
                "lib": "lib_template.py",
                "test": "test_template.py",
            }
            if clean_role in role_to_filename:
                tname = role_to_filename[clean_role]
                for r in roots:
                    cands.append(os.path.join(r, "templates", tname))
                    try:
                        for entry in os.listdir(r):
                            pkg_dir = os.path.join(r, entry)
                            if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                                cands.append(os.path.join(pkg_dir, "templates", tname))
                    except OSError:
                        pass
            for c in cands:
                if os.path.isfile(c):
                    try:
                        with open(c, "r", encoding="utf-8") as f:
                            tmpl_content = f.read()
                        break
                    except OSError:
                        pass

        if tmpl_content:
            unit_str = str(node.unit_address).strip()
            unit_stem = os.path.splitext(os.path.basename(unit_str))[0]
            if unit_stem.endswith("_test"):
                unit_name = unit_stem[:-5]
            else:
                unit_name = unit_stem
            comp_type = (
                "implementation"
                if unit_name.endswith("_impl")
                else ("assembly" if unit_name.endswith("_asm") else ("external" if unit_name.endswith("_ext") else "interface"))
            )
            context = {
                "name": unit_name,
                "component_type": comp_type,
                "is_impl": comp_type == "implementation",
                "needs_implements": comp_type == "implementation",
                "implemented_interfaces": unit_name[:-5] if unit_name.endswith("_impl") else "",
                "is_asm": comp_type == "assembly",
                "is_ext": comp_type == "external",
                "is_not_ext": comp_type != "external",
                "has_imports": False,
                "imported_modules": "",
            }
            for k, v in context.items():
                if isinstance(v, str):
                    tmpl_content = tmpl_content.replace(f"<{k}>", v)

        src_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.write_text(tmpl_content, encoding="utf-8")

    def delete_last_cleaned(self, node: dag_storage.DagNode) -> None:
        self.mark_node_dirty(node)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AgentStorage,
        keys=[AgentStorage, agent_storage.AgentStorage, dag_storage.DagStorage],
        tier=system,
    )
