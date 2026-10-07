# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-05T17:28:49Z
# CHANGE: Add dirty tag checks to get_messages and is_dirty
# CODE_HASH: 53bffead0de9
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

# Requirements specified in bazel_storage_impl.pyi
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.control.lib import src_metadata
from . import bazel_target
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_active_scope,
    get_ambient_system_scope,
    get_default_registry,
    get_singleton,
    system,
)


AUDITOR_ROLE_TAGS: Mapping[str, str] = {
    "grounding_qa": "GROUNDING_QA_AUDIT",
    "qa": "QA_AUDIT",
    "coverage": "COVERAGE_AUDIT",
}


def is_auditor_role(role_name: str) -> bool:
    return role_name in AUDITOR_ROLE_TAGS


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
                    if getattr(desc.impl, "__name__", "") == "BazelManifestLoader":
                        if desc.impl is not None:
                            return scope.get(desc.impl)
        except (LookupError, AttributeError, TypeError, ValueError, KeyError):
            pass
        return None

    def _ensure_manifest_loaded(self, node: dag_storage.DagNode) -> None:
        if node not in self._dependencies and node not in self._source_files:
            loader = self._get_manifest_loader()
            if loader is not None:
                try:
                    loader.load_manifest(node)
                except (
                    LookupError,
                    AttributeError,
                    TypeError,
                    ValueError,
                    KeyError,
                    OSError,
                ):
                    pass

    def _resolve_source_path(self, node: dag_storage.DagNode) -> Optional[Path]:
        if node not in self._source_files:
            self._ensure_manifest_loaded(node)
        if node not in self._source_files:
            return None
        src_rel = self._source_files[node]
        paths_service = get_singleton(file_paths.FilePathManager)
        root_str = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
        root = file_paths.WorkspaceRoot(file_paths.PathString(root_str))
        resolved = paths_service.resolve_path(
            root, file_paths.WorkspacePath(file_paths.PathString(src_rel))
        )
        return Path(resolved.path)

    def get_node_definition(
        self, node: dag_storage.DagNode
    ) -> agent_storage.NodeDefinition:
        return self._definitions.get(
            node,
            agent_storage.NodeDefinition(task_prompt=agent_storage.TaskPrompt("")),
        )

    def store_node_definition(
        self, node: dag_storage.DagNode, definition: agent_storage.NodeDefinition
    ) -> None:
        self._definitions[node] = definition

    def get_task_prompt(self, node: dag_storage.DagNode) -> agent_storage.TaskPrompt:
        return self.get_node_definition(node).task_prompt

    def record_source_file(self, node: dag_storage.DagNode, path: str) -> None:
        self._source_files[node] = path

    def store_dependencies(
        self, node: dag_storage.DagNode, dependencies: Set[dag_storage.DagDependency]
    ) -> None:
        self._dependencies[node] = set(dependencies)

    def store_silent_source_files(
        self, node: dag_storage.DagNode, paths: Tuple[str, ...]
    ) -> None:
        self._silent_source_files[node] = tuple(paths)

    def get_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagDependency]:
        self._ensure_manifest_loaded(node)
        return set(self._dependencies.get(node, set()))

    def store_feedback_dependencies(
        self, node: dag_storage.DagNode, feedback_dependencies: Set[dag_storage.DagNode]
    ) -> None:
        self._feedback_dependencies[node] = set(feedback_dependencies)

    def get_feedback_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagNode]:
        if node in self._feedback_dependencies:
            return set(self._feedback_dependencies[node])
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

    def add_message(
        self, message: dag_storage.DagMessage, to: dag_storage.DagNode
    ) -> None:
        src_path = self._resolve_source_path(to)
        if src_path is not None and src_path.is_file():
            if isinstance(message, dag_storage.FeedbackMessage):
                content_str = (
                    str(message.content) if message.content else "unspecified feedback"
                )
                src_metadata.append_feedback(src_path, content_str)
                return
        self._messages.setdefault(to, set()).add(message)

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
                    if "templates:hls" in tmpl_str:
                        tmpl_candidates.append(
                            "update_python_with_ai/templates/hls_template.md"
                        )
                    elif "templates:lib" in tmpl_str:
                        tmpl_candidates.append(
                            "update_python_with_ai/templates/lib_template.py"
                        )
                    elif "templates:test" in tmpl_str:
                        tmpl_candidates.append(
                            "update_python_with_ai/templates/test_template.py"
                        )
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
        src_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.write_text(tmpl_content, encoding="utf-8")

    def delete_last_cleaned(self, node: dag_storage.DagNode) -> None:
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
            return

        src_path = self._resolve_source_path(node)
        if src_path is not None and src_path.is_file():
            src_metadata.delete_last_cleaned(src_path)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AgentStorage,
        keys=[AgentStorage, agent_storage.AgentStorage, dag_storage.DagStorage],
        tier=system,
    )
