# Requirements specified in bazel_storage_impl.pyi
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set

from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage
from support.lib import src_metadata
from . import bazel_target
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)


class AgentStorage(agent_storage.AgentStorage, Singleton):
    tier = system

    def __init__(self) -> None:
        self._definitions: Dict[dag_storage.DagNode, agent_storage.NodeDefinition] = {}
        self._dependencies: Dict[dag_storage.DagNode, Set[dag_storage.DagDependency]] = {}
        self._dependents: Dict[dag_storage.DagNode, Set[dag_storage.DagNode]] = {}
        self._source_files: Dict[dag_storage.DagNode, str] = {}
        self._messages: Dict[dag_storage.DagNode, Set[dag_storage.DagMessage]] = {}

    def _resolve_source_path(self, node: dag_storage.DagNode) -> Optional[Path]:
        if node not in self._source_files:
            try:
                reg = get_default_registry()
                singletons = getattr(reg, "_singletons", {})
                for key, instance in singletons.items():
                    if getattr(key, "__name__", "") == "BazelManifestLoader":
                        getattr(instance, "load_manifest")(node)
                        break
            except Exception:
                pass
        if node not in self._source_files:
            return None
        src_rel = self._source_files[node]
        paths_service = get_singleton(file_paths.FilePathManager)
        root_str = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
        root = file_paths.WorkspaceRoot(file_paths.PathString(root_str))
        resolved = paths_service.resolve_path(root, file_paths.WorkspacePath(file_paths.PathString(src_rel)))
        return Path(resolved.path)

    def get_node_definition(
        self, node: dag_storage.DagNode
    ) -> agent_storage.NodeDefinition:
        return self._definitions.get(
            node,
            agent_storage.NodeDefinition(
                task_prompt=agent_storage.TaskPrompt("")
            ),
        )

    def store_node_definition(
        self, node: dag_storage.DagNode, definition: agent_storage.NodeDefinition
    ) -> None:
        self._definitions[node] = definition

    def get_task_prompt(self, node: dag_storage.DagNode) -> agent_storage.TaskPrompt:
        return self.get_node_definition(node).task_prompt

    def mark_dependents_dirty(self, node: dag_storage.DagNode) -> None:
        for dep in self.get_dependents(node):
            self.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent(
                        f"dependency {node.unit_address} changed"
                    )
                ),
                to=dep,
            )

    def get_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagDependency]:
        return set(self._dependencies.get(node, set()))

    def get_dependents(self, node: dag_storage.DagNode) -> Set[dag_storage.DagNode]:
        deps: Set[dag_storage.DagNode] = set(self._dependents.get(node, set()))
        for candidate, candidate_deps in self._dependencies.items():
            for d in candidate_deps:
                if not d.is_silent and d.node == node:
                    deps.add(candidate)
        return deps

    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        messages: Set[dag_storage.DagMessage] = set(self._messages.get(node, set()))
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
        if meta.feedback:
            return True
        for dep in self.get_dependencies(node):
            if not dep.is_silent:
                dep_src = self._resolve_source_path(dep.node)
                if dep_src is None or not dep_src.is_file():
                    return True
                dep_meta = src_metadata.extract_metadata(dep_src)
                if dep_meta is None or not dep_meta.last_changed:
                    return True
                if meta.last_cleaned < dep_meta.last_changed:
                    return True
        return len(self._messages.get(node, set())) > 0

    def register_dependent(self, node: dag_storage.DagNode) -> None:
        for dep in self.get_dependencies(node):
            if not dep.is_silent:
                self._dependents.setdefault(dep.node, set()).add(node)

    def clear_dependents(self, node: dag_storage.DagNode) -> None:
        self._dependents[node] = set()

    def add_message(self, message: dag_storage.DagMessage, to: dag_storage.DagNode) -> None:
        src_path = self._resolve_source_path(to)
        if src_path is not None and src_path.is_file():
            if isinstance(message, dag_storage.FeedbackMessage):
                content_str = str(message.content) if message.content else "unspecified feedback"
                src_metadata.append_feedback(src_path, content_str)
                return
        self._messages.setdefault(to, set()).add(message)

    def clear_messages(self, node: dag_storage.DagNode) -> None:
        self._messages[node] = set()
        src_path = self._resolve_source_path(node)
        if src_path is not None and src_path.is_file():
            src_metadata.mark_clean(src_path)

    def delete_last_cleaned(self, node: dag_storage.DagNode) -> None:
        src_path = self._resolve_source_path(node)
        if src_path is not None and src_path.is_file():
            src_metadata.delete_last_cleaned(src_path)

    def record_change(self, node: dag_storage.DagNode, change_description: str) -> None:
        src_path = self._resolve_source_path(node)
        if src_path is not None and src_path.is_file():
            src_metadata.record_change(src_path, change_description)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AgentStorage,
        keys=[AgentStorage, agent_storage.AgentStorage, dag_storage.DagStorage],
        tier=system,
    )
