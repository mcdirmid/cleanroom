# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:04:03Z
# CHANGE: Name the private backing mappings per the grounding, make the audit helpers private, and synthesize the change and feedback diagnostics that mark a node dirty
# CODE_HASH: 9d7c29b7eebc
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from update_with_ai.parts.agent.lib import node_storage
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

_get_audit_tag = src_metadata.get_audit_tag
_is_auditor_role = src_metadata.is_auditor_role


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


class AgentStorage(node_storage.AgentStorage, Singleton):
    tier = system

    def __init__(self) -> None:
        self._node_definitions: Dict[dag_storage.DagNode, node_storage.NodeDefinition] = {}
        self._dependencies: Dict[
            dag_storage.DagNode, Set[dag_storage.DagDependency]
        ] = {}
        self._feedback_dependencies: Dict[
            dag_storage.DagNode, Set[dag_storage.DagNode]
        ] = {}
        self._source_paths: Dict[dag_storage.DagNode, str] = {}
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
        if node in self._source_paths:
            return
        manifest_loader = self._get_manifest_loader()
        if manifest_loader is not None:
            try:
                manifest_loader.load_manifest(node)
            except (LifecycleResolutionError, LookupError, AttributeError, RuntimeError, OSError):
                pass

    def _resolve_source_path(self, node: dag_storage.DagNode) -> Optional[Path]:
        self._ensure_manifest_loaded(node)
        rel_path = self._source_paths.get(node)
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
    ) -> node_storage.NodeDefinition:
        # Contract: Reads NodeDefinition recorded in private _node_definitions mapping for node.
        self._ensure_manifest_loaded(node)
        if node in self._node_definitions:
            return self._node_definitions[node]
        return node_storage.NodeDefinition(
            task_prompt=node_storage.TaskPrompt("")
        )

    def store_node_definition(
        self, node: dag_storage.DagNode, definition: node_storage.NodeDefinition
    ) -> None:
        # Contract: MUST record the node definition mapped to the node in storage.
        self._node_definitions[node] = definition

    def get_task_prompt(
        self, node: dag_storage.DagNode
    ) -> node_storage.TaskPrompt:
        return self.get_node_definition(node).task_prompt

    # Contract: Associates a declared source file relative path with a node in storage.
    def record_source_file(self, node: dag_storage.DagNode, path: str) -> None:
        norm_path = path.lstrip("/")
        self._source_paths[node] = norm_path

    # Contract: Stores the set of upstream forward dependencies for a node.
    def store_dependencies(
        self, node: dag_storage.DagNode, dependencies: Set[dag_storage.DagDependency]
    ) -> None:
        self._dependencies[node] = set(dependencies)

    # Contract: Provides the set of upstream forward dependencies for a node.
    def get_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagDependency]:
        self._ensure_manifest_loaded(node)
        return set(self._dependencies.get(node, set()))

    # Contract: Stores the tuple of silent source file relative paths for a node.
    def store_silent_source_files(
        self, node: dag_storage.DagNode, paths: Tuple[str, ...]
    ) -> None:
        self._silent_source_files[node] = tuple(paths)

    # Contract: Stores the set of verified feedback target nodes for an auditor node.
    def store_feedback_dependencies(
        self, node: dag_storage.DagNode, feedback_dependencies: Set[dag_storage.DagNode]
    ) -> None:
        self._feedback_dependencies[node] = set(feedback_dependencies)

    # Contract: Returns the set of verified feedback target nodes for an auditor node.
    def get_feedback_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagNode]:
        self._ensure_manifest_loaded(node)
        if node in self._feedback_dependencies:
            return set(self._feedback_dependencies[node])
        role_name = node.role_address.split(":")[-1]
        if _is_auditor_role(role_name):
            raise KeyError(
                f"No feedback dependencies configured for auditor node '{node}'"
            )
        return set()

    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        messages: Set[dag_storage.DagMessage] = set(self._messages.get(node, set()))
        role_name = node.role_address.split(":")[-1]
        if _is_auditor_role(role_name):
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
                src_rel = self._source_paths.get(node, node.unit_address)
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

    # Contract: Indicates whether a node requires cleaning based on missing files, metadata, feedback, or dependency updates.
    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        role_name = node.role_address.split(":")[-1]
        if _is_auditor_role(role_name):
            if len(self._messages.get(node, set())) > 0:
                return True
            audit_tag = _get_audit_tag(role_name)
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
            src_rel = self._source_paths.get(node, node.unit_address)
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
        if meta is None:
            return True
        if meta.dirty:
            self._record_message(
                node,
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent(meta.dirty)
                ),
            )
            return True
        if meta.feedback:
            for entry in meta.feedback:
                self._record_message(
                    node,
                    dag_storage.FeedbackMessage(
                        content=dag_storage.MessageContent(entry)
                    ),
                )
            return True
        if not meta.last_cleaned:
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
                        description = dep_meta.change_summary or "updated"
                        self._record_message(
                            node,
                            dag_storage.ChangeMessage(
                                content=dag_storage.MessageContent(
                                    f"dependency {dep.node.unit_address} changed: {description}"
                                )
                            ),
                        )
                        return True
        return len(self._messages.get(node, set())) > 0

    def _record_message(
        self, node: dag_storage.DagNode, message: dag_storage.DagMessage
    ) -> None:
        """Records a synthesized diagnostic message for a node."""
        self._messages.setdefault(node, set()).add(message)

    # Contract: Adds a feedback message blaming a dependency target node.
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

    # Contract: Adds a message to a node, updating in-band source metadata.
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

    # Contract: Marks a node dirty by recording dirty reason in in-band metadata.
    def mark_node_dirty(
        self, node: dag_storage.DagNode, reason: Optional[str] = None
    ) -> None:
        role_name = node.role_address.split(":")[-1]
        if _is_auditor_role(role_name):
            audit_tag = _get_audit_tag(role_name)
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

        dirty_msg = reason if reason else "dirty"
        src_path = self._resolve_source_path(node)
        if src_path is not None and src_path.is_file():
            src_metadata.update_metadata(src_path, dirty=dirty_msg)
            return

        self._messages.setdefault(node, set()).add(
            dag_storage.ChangeMessage(content=dag_storage.MessageContent(dirty_msg))
        )

    # Contract: Marks the target node and all reachable dependencies in its subgraph clean.
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
            if _is_auditor_role(role_name):
                for fb_dep in self.get_feedback_dependencies(n):
                    dfs(fb_dep)
            order.append(n)

        dfs(node)

        for n in order:
            self.materialize_template(n)
            self.mark_node_clean(n)

    # Contract: Clears messages recorded for a node.
    def clear_messages(self, node: dag_storage.DagNode) -> None:
        self._messages[node] = set()

    # Contract: Marks a node clean in storage, updating metadata and clearing messages.
    def mark_node_clean(
        self,
        node: dag_storage.DagNode,
        change_description: Optional[dag_storage.ChangeDescription] = None,
    ) -> None:
        self.clear_messages(node)
        role_name = node.role_address.split(":")[-1]
        if _is_auditor_role(role_name):
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
        # Contract: WHEN the declared source file already exists, MUST preserve the existing file content without overwriting.
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

        candidate_toml_paths: List[str] = []
        if node.role_address.startswith("//"):
            pkg = node.role_address.split(":")[0].lstrip("/")
            candidate_toml_paths.append(os.path.join(bwd, pkg, "cleanroom_roles.toml"))

        if src_path is not None:
            curr_p = src_path.parent
            while curr_p and str(curr_p) != os.path.dirname(str(curr_p)):
                meth_cand = curr_p / "cleanroom.toml"
                if meth_cand.is_file():
                    try:
                        with open(meth_cand, "rb") as f:
                            c_data = tomllib.load(f)
                        m_val = c_data.get("methodology")
                        if m_val and isinstance(m_val, str):
                            m_pkg = m_val.lstrip("/").split(":")[0]
                            candidate_toml_paths.append(os.path.join(bwd, m_pkg, "cleanroom_roles.toml"))
                            break
                    except (tomllib.TOMLDecodeError, OSError):
                        pass
                curr_p = curr_p.parent

        for root in search_roots:
            candidate_toml_paths.append(os.path.join(root, "cleanroom_roles.toml"))
            try:
                for entry in os.listdir(root):
                    sub = os.path.join(root, entry)
                    if os.path.isdir(sub) and not entry.startswith((".", "bazel-", "venv")):
                        candidate_toml_paths.append(os.path.join(sub, "cleanroom_roles.toml"))
            except OSError:
                pass

        for t_path in candidate_toml_paths:
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
                        main_repo = os.path.dirname(t_path)
                        break
                except (tomllib.TOMLDecodeError, OSError):
                    pass

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
                sub_dir = ""
                if role_def and getattr(role_def, "src_pattern", ""):
                    clean = role_def.src_pattern.replace("{unit_dir}/", "").replace("{unit_dir}\\", "")
                    if "/" in clean:
                        sub_dir = clean.split("/", 1)[0]
                if sub_dir:
                    sfx = "/" + sub_dir
                    if p_dir.endswith(sfx):
                        p_dir = p_dir[:-len(sfx)]
                    elif p_dir == sub_dir:
                        p_dir = ""
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
                    bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
                    t_label = tmpl_str.split(":")[-1] if ":" in tmpl_str else ""
                    names = []
                    if t_label:
                        names.extend([
                            f"{t_label}_template.md",
                            f"{t_label}_template.py",
                            f"{t_label}.md",
                            f"{t_label}.py",
                        ])
                        if t_label.endswith("_template"):
                            names.append(f"{t_label}.md")
                            names.append(f"{t_label}.py")
                    for t_name in names:
                        tmpl_candidates.append(os.path.join(bwd, "templates", t_name))
                        try:
                            for entry in os.listdir(bwd):
                                pkg_dir = os.path.join(bwd, entry)
                                if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                                    tmpl_candidates.append(os.path.join(pkg_dir, "templates", t_name))
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

            for r in roots:
                for tdir in [os.path.join(r, "templates")]:
                    if os.path.isdir(tdir):
                        try:
                            for f in os.listdir(tdir):
                                if clean_role in f:
                                    cands.append(os.path.join(tdir, f))
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

        # Contract: Write template content with missing parent directories created.
        src_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.write_text(tmpl_content, encoding="utf-8")

    def delete_last_cleaned(self, node: dag_storage.DagNode) -> None:
        # Contract: MUST delete last cleaned timestamp from source file metadata header and mark node dirty.
        role_name = node.role_address.split(":")[-1]
        if _is_auditor_role(role_name):
            for fb_dep in self.get_feedback_dependencies(node):
                fb_src = self._resolve_source_path(fb_dep)
                if fb_src is not None and fb_src.is_file():
                    meta = src_metadata.extract_metadata(fb_src)
                    if meta and meta.audits and role_name in meta.audits:
                        new_audits = {k: v for k, v in meta.audits.items() if k != role_name}
                        src_metadata.update_metadata(fb_src, audits=new_audits)
            return

        src_path = self._resolve_source_path(node)
        if src_path is not None and src_path.is_file():
            src_metadata.delete_last_cleaned(src_path)
            return

        self._messages.setdefault(node, set()).add(
            dag_storage.ChangeMessage(content=dag_storage.MessageContent("dirty"))
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AgentStorage,
        keys=[AgentStorage, node_storage.AgentStorage, dag_storage.DagStorage],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
