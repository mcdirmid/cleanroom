from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set
from . import bazel_graph_storage
from . import bazel_node_id_utils
from . import dag_storage
from . import file_paths
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class BazelGraphStorage(bazel_graph_storage.BazelGraphStorage, Singleton):
    tier = "system"

    def __init__(self) -> None:
        self._definitions: Dict[dag_storage.Node, bazel_graph_storage.NodeDefinition] = {}
        self._dependencies: Dict[dag_storage.Node, Set[dag_storage.Dependency]] = {}
        self._source_files: Dict[dag_storage.Node, str] = {}

    def _get_store_path(self, node: dag_storage.Node) -> Path:
        # Requirement: All nodes located within the same package directory resolved by the bazel node identifier utility from bazel node id utils share a common package message file named `.update_with_ai.textproto`.
        # Requirement: [BazelGraphStorage] The bazel graph storage reads and writes pending messages and reverse dependencies for nodes from dag storage in node directories resolved by the bazel node identifier utility from bazel node id utils.
        node_util = get_singleton(bazel_node_id_utils.BazelNodeIdentifierUtility)
        pkg_dir = node_util.extract_directory(node)
        paths_service = get_singleton(file_paths.FilePaths)
        root = paths_service.get_workspace_root()
        resolved_dir = paths_service.resolve_directory(root, pkg_dir)
        return Path(resolved_dir.path) / ".update_with_ai.textproto"

    def _load_package_data(self, path: Path) -> Dict[str, Dict[str, Any]]:
        # Requirement: [BazelGraphStorage] The bazel graph storage creates missing package message files on write and treats absent files as empty.
        if not path.is_file():
            return {}
        content = path.read_text(encoding="utf-8")

        # Requirement: The bazel graph storage serializes pending messages and reverse dependencies for nodes from dag storage into protobuf text format files using proto package store from update with ai proto ext.
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

    def _save_package_data(self, path: Path, node_records: Mapping[str, Mapping[str, Any]]) -> bool:
        # Requirement: The bazel graph storage serializes pending messages and reverse dependencies for nodes from dag storage into protobuf text format files using proto package store from update with ai proto ext.
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
            # Requirement: [BazelGraphStorage] Modifying messages or reverse dependencies in the bazel graph storage preserves existing records on failure.
            return False

    def get_node_definition(self, node: dag_storage.Node) -> Optional[bazel_graph_storage.NodeDefinition]:
        # Requirement: [BazelGraphStorage] The bazel graph storage provides task prompts and node definitions for declared nodes.
        # Requirement: The bazel graph storage maintains node definitions and task prompts mapped to nodes in dag storage.
        return self._definitions.get(node)

    def get_dependencies(self, node: dag_storage.Node) -> Set[dag_storage.Dependency]:
        # Requirement: [BazelGraphStorage] The bazel graph storage maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.
        return set(self._dependencies.get(node, set()))

    def get_dependents(self, node: dag_storage.Node) -> Set[dag_storage.Node]:
        # Requirement: [BazelGraphStorage] The bazel graph storage reads and writes pending messages and reverse dependencies for nodes from dag storage in node directories resolved by the bazel node identifier utility from bazel node id utils.
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        record = data.get(node.address, {})
        deps: Set[dag_storage.Node] = set()
        node_util = get_singleton(bazel_node_id_utils.BazelNodeIdentifierUtility)
        for rev_dep in record.get("reverse_dependencies", []):
            deps.add(node_util.normalize(rev_dep))
        return deps

    def get_messages(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        # Requirement: [BazelGraphStorage] The bazel graph storage reads and writes pending messages and reverse dependencies for nodes from dag storage in node directories resolved by the bazel node identifier utility from bazel node id utils.
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        record = data.get(node.address, {})
        messages: Set[dag_storage.Message] = set()
        for msg in record.get("messages", []):
            content = msg.get("content", "")
            if msg.get("kind") == "feedback":
                messages.add(dag_storage.Feedback(content=content))
            else:
                messages.add(dag_storage.Change(content=content))
        return messages

    def is_dirty(self, node: dag_storage.Node) -> bool:
        # Requirement: A node in dag storage is dirty if it has messages explaining why it requires cleaning, or if its declared source file is missing from the workspace root.
        # Requirement: [DagStorage] A node is dirty if, but not only if, it has messages.
        if len(self.get_messages(node)) > 0:
            return True
        if node in self._source_files:
            src_rel = self._source_files[node]
            paths_service = get_singleton(file_paths.FilePaths)
            root = paths_service.get_workspace_root()
            resolved = Path(root.path) / src_rel
            if not resolved.is_file():
                return True
        return False

    def register_dependent(self, node: dag_storage.Node) -> None:
        # Requirement: Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
        # Requirement: [DagStorage] Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
        # Requirement: Propagating dependencies exclude silent dependencies declared on a node.
        for dep in self.get_dependencies(node):
            if not dep.is_silent:
                path = self._get_store_path(dep.node)
                data = self._load_package_data(path)
                record = data.setdefault(dep.node.address, {"messages": [], "reverse_dependencies": []})
                rev_deps = set(record.get("reverse_dependencies", []))
                rev_deps.add(node.address)
                record["reverse_dependencies"] = sorted(rev_deps)
                self._save_package_data(path, data)

    def clear_dependents(self, node: dag_storage.Node) -> None:
        # Requirement: Clearing the dependents of a node empties all recorded dependents for that node.
        # Requirement: [DagStorage] Clearing the dependents of a node empties all recorded dependents for that node.
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        if node.address in data:
            data[node.address]["reverse_dependencies"] = []
            self._save_package_data(path, data)

    def add_message(self, message: dag_storage.Message, to: dag_storage.Node) -> None:
        # Requirement: Adding a message to a node records the message explaining why the node requires cleaning.
        # Requirement: [DagStorage] Adding a message to a node records the message for that node.
        path = self._get_store_path(to)
        data = self._load_package_data(path)
        record = data.setdefault(to.address, {"messages": [], "reverse_dependencies": []})
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
        if node.address in data:
            data[node.address]["messages"] = []
            self._save_package_data(path, data)

# Compatibility alias
DagStorage = BazelGraphStorage

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        BazelGraphStorage,
        keys=[BazelGraphStorage, bazel_graph_storage.BazelGraphStorage, dag_storage.DagStorage],
        tier="system",
    )
