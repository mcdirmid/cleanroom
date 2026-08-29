# lib/build_message_store_impl.py
"""
Implementation of the LLS BuildMessageStore interface.
"""

from typing import Dict, List, Optional, Tuple, cast
import os

from .dag_storage import NodeId, NodeMessage, MessageKind, PendingMessages, KnownReverseDependencies
from .build_graph_storage import PackageDirectory
from .build_message_store import BuildMessageStore, PackageMessageData

HARNESS_FILE = ".update_with_ai.textproto"


def _proto_quote(s: str) -> str:
    out = ['"']
    for ch in s:
        code = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif code < 0x20 or code == 0x7F:
            out.append("\\x{:02x}".format(code))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _proto_unquote(token: str) -> str:
    body = token[1:-1]
    out: List[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(body):
            break
        esc = body[i]
        i += 1
        simple = {
            "n": "\n", "r": "\r", "t": "\t", "a": "\a", "b": "\b",
            "f": "\f", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?",
        }
        if esc in simple:
            out.append(simple[esc])
        elif esc == "x":
            hex_digits = body[i:i + 2]
            out.append(chr(int(hex_digits, 16)))
            i += 2
        elif esc.isdigit():
            oct_digits = body[i:i + 3]
            out.append(chr(int(oct_digits, 8)))
            i += 3
        else:
            out.append(esc)
    return "".join(out)


class BuildMessageStoreImpl(BuildMessageStore):
    def read_package_messages(self, package_dir: PackageDirectory) -> PackageMessageData:
        path = os.path.join(package_dir, HARNESS_FILE)
        if not os.path.exists(path):
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return {}

        return self._parse_textproto(content)

    def write_package_messages(self, package_dir: PackageDirectory, data: PackageMessageData) -> None:
        path = os.path.join(package_dir, HARNESS_FILE)
        if not data:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            return

        lines: List[str] = []
        for node in sorted(data.keys()):
            pending, rev_deps = data[node]
            lines.append("nodes {")
            lines.append(f"  label: {_proto_quote(node)}")
            for msg in pending:
                lines.append("  pending_messages {")
                lines.append(f"    kind: {msg.kind}")
                lines.append(f"    text: {_proto_quote(msg.text)}")
                lines.append("  }")
            for rev in sorted(rev_deps):
                lines.append(f"  known_reverse_dependencies: {_proto_quote(rev)}")
            lines.append("}")
        text = "\n".join(lines) + "\n"

        os.makedirs(package_dir, exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, path)

    def _parse_textproto(self, text: str) -> PackageMessageData:
        result: PackageMessageData = {}
        tokens = self._tokenize(text)
        idx = 0

        def next_token() -> Optional[str]:
            nonlocal idx
            if idx < len(tokens):
                tok = tokens[idx]
                idx += 1
                return tok
            return None

        while idx < len(tokens):
            tok = next_token()
            if tok != "nodes":
                continue
            if next_token() != "{":
                continue

            label: Optional[str] = None
            pending: List[NodeMessage] = []
            rev_deps: List[str] = []

            while idx < len(tokens):
                t = next_token()
                if t == "}":
                    break
                elif t == "label:":
                    val = next_token()
                    if val and val.startswith('"'):
                        label = _proto_unquote(val)
                elif t == "known_reverse_dependencies:":
                    val = next_token()
                    if val and val.startswith('"'):
                        rev_deps.append(_proto_unquote(val))
                elif t == "pending_messages":
                    if next_token() == "{":
                        kind: str = "change"
                        msg_text: str = ""
                        while idx < len(tokens):
                            mt = next_token()
                            if mt == "}":
                                break
                            elif mt == "kind:":
                                kind = next_token() or "change"
                            elif mt == "text:":
                                val = next_token()
                                if val and val.startswith('"'):
                                    msg_text = _proto_unquote(val)
                        pending.append(NodeMessage(kind=cast(MessageKind, kind), text=msg_text))

            if label:
                result[label] = (pending, rev_deps)

        return result


    def _tokenize(self, text: str) -> List[str]:
        tokens: List[str] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch.isspace():
                i += 1
                continue
            if ch == "#":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if ch in ("{", "}"):
                tokens.append(ch)
                i += 1
                continue
            if ch == '"':
                start = i
                i += 1
                while i < n:
                    if text[i] == "\\" and i + 1 < n:
                        i += 2
                    elif text[i] == '"':
                        i += 1
                        break
                    else:
                        i += 1
                tokens.append(text[start:i])
                continue

            start = i
            while i < n and not text[i].isspace() and text[i] not in ("{", "}", "#", '"'):
                i += 1
            tokens.append(text[start:i])
        return tokens

    def get_pending_messages(self, package_dir: PackageDirectory, node: NodeId) -> PendingMessages:
        data = self.read_package_messages(package_dir)
        if node in data:
            return list(data[node][0])
        return []

    def add_pending_message(self, package_dir: PackageDirectory, node: NodeId, message: NodeMessage) -> None:
        data = self.read_package_messages(package_dir)
        pending, rev_deps = data.get(node, ([], []))
        data[node] = (pending + [message], rev_deps)
        self.write_package_messages(package_dir, data)

    def set_pending_messages(self, package_dir: PackageDirectory, node: NodeId, messages: PendingMessages) -> None:
        data = self.read_package_messages(package_dir)
        _, rev_deps = data.get(node, ([], []))
        data[node] = (list(messages), rev_deps)
        self.write_package_messages(package_dir, data)

    def clear_pending_messages(self, package_dir: PackageDirectory, node: NodeId) -> None:
        data = self.read_package_messages(package_dir)
        if node in data:
            data[node] = ([], data[node][1])
            self.write_package_messages(package_dir, data)

    def delete_node_messages(self, package_dir: PackageDirectory, node: NodeId) -> None:
        data = self.read_package_messages(package_dir)
        if node in data:
            del data[node]
            self.write_package_messages(package_dir, data)

    def get_known_reverse_dependencies(self, package_dir: PackageDirectory, node: NodeId) -> KnownReverseDependencies:
        data = self.read_package_messages(package_dir)
        if node in data:
            return list(data[node][1])
        return []

    def add_known_reverse_dependency(self, package_dir: PackageDirectory, node: NodeId, reverse_dep: NodeId) -> None:
        data = self.read_package_messages(package_dir)
        pending, rev_deps = data.get(node, ([], []))
        if reverse_dep not in rev_deps:
            data[node] = (pending, rev_deps + [reverse_dep])
            self.write_package_messages(package_dir, data)

    def clear_known_reverse_dependencies(self, package_dir: PackageDirectory, node: NodeId) -> None:
        data = self.read_package_messages(package_dir)
        if node in data:
            data[node] = (data[node][0], [])
            self.write_package_messages(package_dir, data)
