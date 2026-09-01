<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
-->

# External LLS: update_with_ai_proto_ext

## Data Types
```python
from typing import Sequence, Mapping, TypeAlias
from dataclasses import dataclass
from dag_storage import NodeId

MessageKind: TypeAlias = str
MessageText: TypeAlias = str

@dataclass(frozen=True)
class ProtoMessage:
    kind: MessageKind
    text: MessageText

@dataclass(frozen=True)
class ProtoNodeEntry:
    messages: Sequence[ProtoMessage]
    reverse_dependencies: Sequence[NodeId]

ProtoPackageStore: TypeAlias = Mapping[NodeId, ProtoNodeEntry]
```

- `ProtoMessage` → corresponds to *proto message*: an external textproto message record with a kind discriminator and text payload.
- `ProtoNodeEntry` → corresponds to *proto node entry*: an external textproto record containing pending *messages* and *reverse dependencies* for a *node*.
- `ProtoPackageStore` → corresponds to *proto package store*: a collection of *proto node entries* serialized to a package textproto file aligning with protobuf text-format representation for `.update_with_ai.textproto`.
