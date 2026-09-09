'''
# External Specification: update_with_ai_proto_ext

## External Mechanics & API Documentation

The `update_with_ai_proto_ext` external component specifies message store persistence in `.update_with_ai.textproto` files using the Python Protobuf text format API. External boundary specifications define no standalone library files; dependent implementation components (specifically `bazel_graph_storage_impl`) import and invoke Google Protobuf text format serialization directly.

**Protobuf Text Format Schema & Record Structure**

Package `.update_with_ai.textproto` files store structured node records:
- `node` (repeated message):
  - `node_id: str` (required): Target coordinate address (e.g. `"//pkg:target"`).
  - `messages` (repeated message):
    - `kind: str`: Message discriminator (`"change"` or `"feedback"`).
    - `content: str`: Diagnostic or change text explanation.
    - `sender: Optional[str]`: Originating node target identifier.
  - `reverse_dependencies: List[str]`: Target coordinates of registered downstream nodes.

**Protobuf Python Text Format APIs**

- **Module**: `google.protobuf.text_format` (from `@com_google_protobuf//:protobuf_python`).
- **Parsing API**:
  - `text_format.Parse(text: str, message: Message) -> Message`: Parses human-readable protobuf text into structured protobuf message instances.
  - `text_format.ParseError`: Raised on syntax errors or unrecognized field descriptors.
- **Serialization API**:
  - `text_format.MessageToString(message: Message, as_utf8: bool = True) -> str`: Formats in-memory protobuf message to deterministic human-readable textproto representation.
- **Missing File Semantics**: Missing `.update_with_ai.textproto` files in package directories are treated as empty stores without raising errors.

## Build Dependencies

Consuming implementation components require the Python protobuf library in `BUILD.bazel`.

The consuming component `bazel_graph_storage_impl` must configure its Bazel target in `update_with_ai/lib/BUILD.bazel` with:
- Protobuf dependency label: `@com_google_protobuf//:protobuf_python` (or proto rules).
- Target dependency definition:
  ```python
  py_library(
      name = "bazel_graph_storage_impl",
      srcs = ["bazel_graph_storage_impl.py"],
      deps = [
          ":bazel_graph_storage",
          ":dag_storage",
          ":file_alias",
          "@com_google_protobuf//:protobuf_python",
      ],
  )
  ```

## Usage Snippets

### `Parsing Message Records from Textproto File`

```python
from pathlib import Path
from typing import Any, Dict, List, Mapping

def load_package_textproto(textproto_path: str) -> Mapping[str, Any]:
    """Loads node messages and reverse dependencies from .update_with_ai.textproto file."""
    path = Path(textproto_path)
    if not path.is_file():
        return {"nodes": {}}
        
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {"nodes": {}}
        
    nodes: Dict[str, Dict[str, Any]] = {}
    current_node_id = None
    current_messages: List[Mapping[str, str]] = []
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
            
    return {"nodes": nodes}
```

### `Serializing Message Records to Canonical Textproto Format`

```python
from pathlib import Path
from typing import Any, Mapping

def save_package_textproto(
    textproto_path: str,
    node_records: Mapping[str, Mapping[str, Any]],
) -> bool:
    """Writes package node messages and reverse dependencies to .update_with_ai.textproto."""
    lines = []
    for node_id in sorted(node_records.keys()):
        record = node_records[node_id]
        lines.append("node {")
        lines.append(f'  node_id: "{node_id}"')
        
        for msg in record.get("messages", []):
            lines.append("  messages {")
            lines.append(f'    kind: "{msg.get("kind", "change")}"')
            lines.append(f'    content: "{msg.get("content", "")}"')
            if msg.get("sender"):
                lines.append(f'    sender: "{msg["sender"]}"')
            lines.append("  }")
            
        for rev_dep in sorted(record.get("reverse_dependencies", [])):
            lines.append(f'  reverse_dependencies: "{rev_dep}"')
            
        lines.append("}")
        
    content = "\n".join(lines) + "\n"
    path = Path(textproto_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False
```
'''
