from typing import Protocol, Sequence
from .dag_storage import NodeId, PendingMessage
from .dag_node_cleaner import NodeCleaner, NodeCleaningOutcome


class AgentNodeCleaner(NodeCleaner, Protocol):
    def clean_node(
        self, node: NodeId, pending_messages: Sequence[PendingMessage]
    ) -> NodeCleaningOutcome:
        ...

