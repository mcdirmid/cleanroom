"""External schema definitions for .update_with_ai.textproto."""

from typing import Sequence, Mapping, TypeAlias
from dataclasses import dataclass
from .dag_storage import NodeId


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
