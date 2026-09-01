"""DAG node cleaner interface and outcome messages."""

from typing import Protocol, TypeAlias, Sequence, Union, Optional
from .dag_storage import NodeId, DagMessage, PendingMessage

ChangeMessage: TypeAlias = DagMessage
FeedbackMessage: TypeAlias = DagMessage

NodeCleaningOutcome: TypeAlias = Optional[Sequence[Union[ChangeMessage, FeedbackMessage]]]


class NodeCleaner(Protocol):
    def clean_node(self, node: NodeId, pending_messages: Sequence[PendingMessage]) -> NodeCleaningOutcome:
        ...
