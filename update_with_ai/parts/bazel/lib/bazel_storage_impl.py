from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set
from update_with_ai.parts.agent.lib import agent_storage
from . import bazel_target
from update_with_ai.parts.dag.lib import dag_storage
from . import file_paths
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
        self._definitions: Dict[dag_storage.Node, agent_storage.NodeDefinition] = {}
        self._dependencies: Dict[dag_storage.Node, Set[dag_storage.Dependency]] = {}
        self._source_files: Dict[dag_storage.Node, str] = {}

    def _get_store_path(self, node: dag_storage.Node) -> Path:
        # Requirement: All nodes located within the same package directory resolved by the bazel target share a common package message file named `.update_with_ai.textproto`.
        # Requirement: The agent storage resolves the package directory against the workspace root to read and write message files at their absolute path, creating files if missing and ignoring absent files on read.
        node_util = get_singleton(bazel_target.BazelTarget)
        pkg_dir = node_util.extract_directory(node)
        paths_service = get_singleton(file_paths.FilePaths)
        root = paths_service.get_workspace_root()
        resolved_dir = paths_service.resolve_directory(root, pkg_dir)
        return Path(resolved_dir.path) / ".update_with_ai.textproto"

    def _load_package_data(self, path: Path) -> Dict[str, Dict[str, Any]]:
        # Requirement: The agent storage resolves the package directory against the workspace root to read and write message files at their absolute path, creating files if missing and ignoring absent files on read.
        if not path.is_file():
            return {}
        content = path.read_text(encoding="utf-8")

        # Requirement: The agent storage serializes pending messages and reverse dependencies for nodes from dag storage into protobuf text format files using proto package store from update with ai proto ext.
        nodes: Dict[str, Dict[str, Any]] = {}
        current_node_id: Optional[str] = None
        current_messages: List[Dict[str, str]] = []
        current_rev_deps: List[str] = []

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("node_id:"):
                current_node_id = stripped.split(":", 1)[1].strip().strip('"')
                current_messages = []
                current_rev_deps = []
                nodes[current_node_id] = {
                    "messages": current_messages,
                    "reverse_dependencies": current_rev_deps,
                }
            elif stripped.startswith("reverse_dependencies:"):
                rev_dep = stripped.split(":", 1)[1].strip().strip('"')
                current_rev_deps.append(rev_dep)
            elif stripped.startswith("kind:"):
                kind = stripped.split(":", 1)[1].strip().strip('"')
                current_messages.append({"kind": kind, "content": ""})
            elif stripped.startswith("content:") and current_messages:
                content_val = stripped.split(":", 1)[1].strip().strip('"')
                current_messages[-1]["content"] = content_val

        return nodes

    def _save_package_data(
        self, path: Path, node_records: Mapping[str, Mapping[str, Any]]
    ) -> bool:
        # Requirement: The agent storage serializes pending messages and reverse dependencies for nodes from dag storage into protobuf text format files using proto package store from update with ai proto ext.
        lines: List[str] = []
        for node_id in sorted(node_records.keys()):
            record = node_records[node_id]
            lines.append("node {")
            lines.append(f'  node_id: "{node_id}"')

            for msg in record.get("messages", []):
                lines.append("  messages {")
                lines.append(f'    kind: "{msg.get("kind", "change")}"')
                lines.append(f'    content: "{msg.get("content", "")}"')
                lines.append("  }")

            for rev_dep in sorted(record.get("reverse_dependencies", [])):
                lines.append(f'  reverse_dependencies: "{rev_dep}"')

            lines.append("}")

        content = "\n".join(lines) + "\n"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return True
        except OSError:
            return False

    def get_node_definition(
        self, node: dag_storage.Node
    ) -> Optional[agent_storage.NodeDefinition]:
        # Requirement: [AgentStorage] The agent storage provides task prompts and node definitions for declared nodes.
        # Requirement: The agent storage maintains node definitions and task prompts mapped to nodes in dag storage.
        return self._definitions.get(node)

    def get_dependencies(self, node: dag_storage.Node) -> Set[dag_storage.Dependency]:
        # Requirement: [AgentStorage] The agent storage maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.
        return set(self._dependencies.get(node, set()))

    def _node_to_id(self, node: dag_storage.Node) -> str:
        if node.role_address:
            return f"{node.unit_address}#{node.role_address}"
        return node.unit_address

    def _id_to_node(self, node_id: str) -> dag_storage.Node:
        node_util = get_singleton(bazel_target.BazelTarget)
        return node_util.normalize(node_id)

    def get_dependents(self, node: dag_storage.Node) -> Set[dag_storage.Node]:
        # Requirement: All nodes located within the same package directory resolved by the bazel target share a common package message file named `.update_with_ai.textproto`.
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        record = data.get(self._node_to_id(node), {})
        deps: Set[dag_storage.Node] = set()
        for rev_dep in record.get("reverse_dependencies", []):
            deps.add(self._id_to_node(rev_dep))
        return deps

    def get_messages(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        # Requirement: All nodes located within the same package directory resolved by the bazel target share a common package message file named `.update_with_ai.textproto`.
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        record = data.get(self._node_to_id(node), {})
        messages: Set[dag_storage.Message] = set()
        for msg in record.get("messages", []):
            content = msg.get("content", "")
            if msg.get("kind") == "feedback":
                messages.add(dag_storage.Feedback(content=content))
            else:
                messages.add(dag_storage.Change(content=content))
        return messages

    def is_dirty(self, node: dag_storage.Node) -> bool:
        # Requirement: A node in dag storage is dirty if it has messages explaining why it requires cleaning, or if its declared source file is missing from the workspace root, recording a change message to implement the source file for the node.
        # Requirement: [DagStorage] A node is dirty if, but not only if, it has messages.
        if node in self._source_files:
            src_rel = self._source_files[node]
            paths_service = get_singleton(file_paths.FilePaths)
            root = paths_service.get_workspace_root()
            resolved = Path(root.path) / src_rel
            if not resolved.is_file():
                content = f"implement {src_rel}"
                msgs = self.get_messages(node)
                if not any(m.content == content for m in msgs):
                    self.add_message(dag_storage.Change(content=content), to=node)
                return True
        return len(self.get_messages(node)) > 0

    def register_dependent(self, node: dag_storage.Node) -> None:
        # Requirement: Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
        # Requirement: [DagStorage] Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
        # Requirement: Propagating dependencies exclude silent dependencies declared on a node.
        for dep in self.get_dependencies(node):
            if not dep.is_silent:
                path = self._get_store_path(dep.node)
                data = self._load_package_data(path)
                dep_id = self._node_to_id(dep.node)
                record = data.setdefault(
                    dep_id, {"messages": [], "reverse_dependencies": []}
                )
                rev_deps = set(record.get("reverse_dependencies", []))
                rev_deps.add(self._node_to_id(node))
                record["reverse_dependencies"] = sorted(rev_deps)
                self._save_package_data(path, data)

    def clear_dependents(self, node: dag_storage.Node) -> None:
        # Requirement: Clearing the dependents of a node empties all recorded dependents for that node.
        # Requirement: [DagStorage] Clearing the dependents of a node empties all recorded dependents for that node.
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        node_id = self._node_to_id(node)
        if node_id in data:
            data[node_id]["reverse_dependencies"] = []
            self._save_package_data(path, data)

    def add_message(self, message: dag_storage.Message, to: dag_storage.Node) -> None:
        # Requirement: Adding a message to a node records the message explaining why the node requires cleaning.
        # Requirement: [DagStorage] Adding a message to a node records the message for that node.
        path = self._get_store_path(to)
        data = self._load_package_data(path)
        to_id = self._node_to_id(to)
        record = data.setdefault(to_id, {"messages": [], "reverse_dependencies": []})
        msg_list: List[Dict[str, str]] = record.setdefault("messages", [])
        kind = "feedback" if isinstance(message, dag_storage.Feedback) else "change"
        content = message.content if hasattr(message, "content") else ""
        msg_list.append({"kind": kind, "content": content})
        self._save_package_data(path, data)

    def clear_messages(self, node: dag_storage.Node) -> None:
        # Requirement: Clearing messages for a node removes all recorded messages explaining why it requires cleaning.
        # Requirement: [DagStorage] Clearing messages for a node removes all recorded messages for that node.
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        node_id = self._node_to_id(node)
        if node_id in data:
            data[node_id]["messages"] = []
            self._save_package_data(path, data)


# Compatibility alias
DagStorage = AgentStorage


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AgentStorage,
        keys=[AgentStorage, agent_storage.AgentStorage, dag_storage.DagStorage],
        tier=system,
    )
