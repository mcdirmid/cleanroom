"""Build message store implementation with textproto persistence."""

import os
import tempfile
from typing import Sequence, Optional, List, Dict
from .dag_storage import NodeId, DagMessage, PendingMessage, NodeData
from .node_id_utils import NodeIdUtils, NodeDirectory, WorkspaceRootPath
from .build_message_store import BuildMessageStore
from .update_with_ai_proto_ext import ProtoPackageStore, ProtoNodeEntry, ProtoMessage


def _parse_textproto(content: str) -> Dict[str, ProtoNodeEntry]:
    entries: Dict[str, ProtoNodeEntry] = {}
    current_node: Optional[str] = None
    messages: List[ProtoMessage] = []
    rdeps: List[str] = []
    in_message = False
    msg_kind = ""
    msg_text = ""

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("node_entry {"):
            current_node = None
            messages = []
            rdeps = []
        elif line.startswith("node_id:"):
            val = line.split(":", 1)[1].strip().strip('"')
            current_node = val
        elif line.startswith("message {"):
            in_message = True
            msg_kind = ""
            msg_text = ""
        elif in_message and line.startswith("kind:"):
            msg_kind = line.split(":", 1)[1].strip().strip('"')
        elif in_message and line.startswith("text:"):
            msg_text = line.split(":", 1)[1].strip().strip('"')
        elif in_message and line.startswith("}"):
            messages.append(ProtoMessage(kind=msg_kind, text=msg_text))
            in_message = False
        elif line.startswith("reverse_dependency:"):
            val = line.split(":", 1)[1].strip().strip('"')
            rdeps.append(val)
        elif line.startswith("}"):
            if current_node:
                entries[current_node] = ProtoNodeEntry(
                    messages=list(messages), reverse_dependencies=list(rdeps)
                )
            current_node = None
            messages = []
            rdeps = []

    return entries


def _serialize_textproto(entries: Dict[str, ProtoNodeEntry]) -> str:
    lines: List[str] = []
    for node_id, entry in entries.items():
        lines.append("node_entry {")
        lines.append(f'  node_id: "{node_id}"')
        for msg in entry.messages:
            lines.append("  message {")
            lines.append(f'    kind: "{msg.kind}"')
            lines.append(f'    text: "{msg.text}"')
            lines.append("  }")
        for rdep in entry.reverse_dependencies:
            lines.append(f'  reverse_dependency: "{rdep}"')
        lines.append("}")
    return "\n".join(lines) + ("\n" if lines else "")


class BuildMessageStoreImpl(BuildMessageStore):
    def __init__(self, workspace_root: WorkspaceRootPath, node_id_utils: NodeIdUtils) -> None:
        self.workspace_root = workspace_root
        self.node_id_utils = node_id_utils
        self._node_data: Dict[NodeId, NodeData] = {}

    def get_package_directory(self, node: NodeId) -> NodeDirectory:
        return self.node_id_utils.extract_node_directory(node, self.workspace_root)

    def _proto_file_for_node(self, node: NodeId) -> str:
        pkg_dir = self.get_package_directory(node)
        return os.path.join(pkg_dir, ".update_with_ai.textproto")

    def _read_package_store(self, node: NodeId) -> Dict[str, ProtoNodeEntry]:
        proto_file = self._proto_file_for_node(node)
        if not os.path.isfile(proto_file):
            return {}
        with open(proto_file, "r", encoding="utf-8") as f:
            return _parse_textproto(f.read())

    def _write_package_store(
        self, node: NodeId, entries: Dict[str, ProtoNodeEntry]
    ) -> None:
        proto_file = self._proto_file_for_node(node)
        pkg_dir = os.path.dirname(proto_file)
        os.makedirs(pkg_dir, exist_ok=True)
        content = _serialize_textproto(entries)
        # Atomic write
        temp_file = proto_file + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_file, proto_file)

    def get_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return []

    def get_reverse_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        entries = self._read_package_store(node)
        entry = entries.get(node)
        if entry:
            return entry.reverse_dependencies
        return []

    def get_pending_messages(self, node: NodeId) -> Sequence[PendingMessage]:
        entries = self._read_package_store(node)
        entry = entries.get(node)
        if not entry:
            return []
        return [DagMessage(content=m.text) for m in entry.messages]

    def queue_pending_messages(
        self, node: NodeId, messages: Sequence[DagMessage]
    ) -> None:
        entries = self._read_package_store(node)
        current = entries.get(node)
        cur_msgs = list(current.messages) if current else []
        cur_rdeps = list(current.reverse_dependencies) if current else []
        for m in messages:
            cur_msgs.append(ProtoMessage(kind="message", text=m.content))
        entries[node] = ProtoNodeEntry(
            messages=cur_msgs, reverse_dependencies=cur_rdeps
        )
        self._write_package_store(node, entries)

    def clear_pending_messages(self, node: NodeId) -> None:
        entries = self._read_package_store(node)
        if node in entries:
            current = entries[node]
            entries[node] = ProtoNodeEntry(
                messages=[], reverse_dependencies=current.reverse_dependencies
            )
            self._write_package_store(node, entries)

    def record_node_data(self, node: NodeId, data: NodeData) -> None:
        self._node_data[node] = data

    def get_node_data(self, node: NodeId) -> Optional[NodeData]:
        return self._node_data.get(node)

    def mark_dirty(self, node: NodeId) -> None:
        self.queue_pending_messages(node, [DagMessage(content="dirty")])

    def is_dirty(self, node: NodeId) -> bool:
        return len(self.get_pending_messages(node)) > 0
