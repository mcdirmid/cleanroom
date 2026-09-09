from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set
from . import bazel_graph_storage
from . import bazel_node_id_utils
from . import dag_storage
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class BazelGraphStorage(bazel_graph_storage.BazelGraphStorage, Singleton):
    tier = "system"

    def __init__(self) -> None:
        self._definitions: Dict[dag_storage.Node, bazel_graph_storage.NodeDefinition] = {}
        self._dependencies: Dict[dag_storage.Node, Set[dag_storage.Dependency]] = {}

    def _get_store_path(self, node: dag_storage.Node) -> Path:
        # Requirement: Maps target node to package directory textproto store path
        node_util = get_singleton(bazel_node_id_utils.BazelNodeIdentifierUtility)
        pkg_dir = node_util.extract_directory(node)
        return Path(pkg_dir.path) / ".update_with_ai.textproto"

    def _load_package_data(self, path: Path) -> Dict[str, Dict[str, Any]]:
        # Requirement: Missing textproto file is treated as empty store
        if not path.is_file():
            return {}
        content = path.read_text(encoding="utf-8")

        # Requirement: Deserializes textproto records into node dictionary
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
        # Requirement: Serializes node records to deterministic textproto format
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

    def get_node_definition(self, node: dag_storage.Node) -> Optional[bazel_graph_storage.NodeDefinition]:
        # Requirement: Returns node definition metadata for specified node
        return self._definitions.get(node)

    def get_dependencies(self, node: dag_storage.Node) -> Set[dag_storage.Dependency]:
        # Requirement: Returns direct dependency edges recorded for specified node
        return set(self._dependencies.get(node, set()))

    def get_dependents(self, node: dag_storage.Node) -> Set[dag_storage.Node]:
        # Requirement: Resolves reverse dependency nodes from package textproto store
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        record = data.get(node.address, {})
        deps: Set[dag_storage.Node] = set()
        node_util = get_singleton(bazel_node_id_utils.BazelNodeIdentifierUtility)
        for rev_dep in record.get("reverse_dependencies", []):
            deps.add(node_util.normalize(rev_dep))
        return deps

    def get_messages(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        # Requirement: Reads pending messages recorded for specified node from package textproto store
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        record = data.get(node.address, {})
        messages: Set[dag_storage.Message] = set()
        for msg in record.get("messages", []):
            if msg.get("kind") == "feedback":
                messages.add(dag_storage.Feedback())
            else:
                messages.add(dag_storage.Change())
        return messages

    def is_dirty(self, node: dag_storage.Node) -> bool:
        # Requirement: Target node is dirty if it has any unprocessed incoming messages
        return len(self.get_messages(node)) > 0

    def register_dependent(self, node: dag_storage.Node) -> None:
        # Requirement: Registers node as reverse dependency on its non-silent dependencies in package textproto store
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
        # Requirement: Clears all recorded reverse dependencies for node in package textproto store
        path = self._get_store_path(node)
        data = self._load_package_data(path)
        if node.address in data:
            data[node.address]["reverse_dependencies"] = []
            self._save_package_data(path, data)

    def add_message(self, message: dag_storage.Message, to: dag_storage.Node) -> None:
        # Requirement: Appends a message to target node's pending message store in package textproto file
        path = self._get_store_path(to)
        data = self._load_package_data(path)
        record = data.setdefault(to.address, {"messages": [], "reverse_dependencies": []})
        msg_list: List[Dict[str, str]] = record.setdefault("messages", [])
        kind = "feedback" if isinstance(message, dag_storage.Feedback) else "change"
        msg_list.append({"kind": kind, "content": ""})
        self._save_package_data(path, data)

    def clear_messages(self, node: dag_storage.Node) -> None:
        # Requirement: Clears all pending messages for target node in package textproto file
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
