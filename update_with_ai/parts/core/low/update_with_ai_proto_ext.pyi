"""
## External Mechanics & API Documentation

The `update_with_ai_proto_ext` external component specifies the protobuf text format schema and serialization conventions for storing per-package message records in `.update_with_ai.textproto` files. External boundary specifications define no standalone library files; storage implementations import Google's `google.protobuf.text_format` or custom lightweight textproto parsers directly.

**Textproto Package Schema**

```protobuf
syntax = "proto3";

package update_with_ai;

message MessageEntry {
  string kind = 1;      // "change" or "feedback"
  string content = 2;   // diagnostic explanatory text
  string target = 3;    // blamed target node address (for feedback)
}

message NodeEntry {
  string node_id = 1;
  repeated MessageEntry messages = 2;
  repeated string reverse_deps = 3;
}

message PackageStore {
  repeated NodeEntry nodes = 1;
}
```

**Serialization & Error Recovery**

- Parsing: Deserializes textproto strings into structured node records. Missing files are treated as empty stores (`{}`).
- Serialization: Serializes nodes deterministically, ordering entries by `node_id`.
- Corruption: Invalid syntax or unrecognized fields fall back to empty collections without process crashing.

## Build Dependencies

(none)

## Usage Snippets

### `Parsing and Serializing Package Textproto`

```python
from typing import Any, Dict

def parse_package_textproto(text: str) -> Dict[str, Any]:
    # Parses textproto into dictionary mapping node_id to messages and reverse_deps
    ...

def serialize_package_textproto(data: Dict[str, Any]) -> str:
    # Formats dictionary into canonical textproto string
    ...
```
"""
