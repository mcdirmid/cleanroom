"""
Interface LLS: dag_clean_logic
Provides message processing logic for DAG nodes.
"""

from typing import List, Tuple, Literal, Protocol, Union
from dataclasses import dataclass

# Use relative import for same-directory modules
from .dag_storage import NodeId, NodeMessage, PendingMessages
from .tool_provider import TerminateSuccessResult


@dataclass
class ChangeResult(TerminateSuccessResult):
    """Change: messages to broadcast to all reverse dependencies."""
    messages: List[NodeMessage]
    type: Literal["change"] = "change"


@dataclass
class FeedbackResult(TerminateSuccessResult):
    """Feedback: messages to deliver to specific dependencies (target, message) pairs."""
    messages: List[Tuple[NodeId, NodeMessage]]
    type: Literal["feedback"] = "feedback"


@dataclass
class NoChangeResult(TerminateSuccessResult):
    """No change: node cleaned successfully, no messages produced."""
    type: Literal["no_change"] = "no_change"


@dataclass
class FailureResult:
    """Failure: cleaning failed, no messages produced."""
    type: Literal["failure"] = "failure"


CleanResult = Union[ChangeResult, FeedbackResult, NoChangeResult, FailureResult]


class DagCleanLogic(Protocol):
    """Interface for DAG cleaning logic operations."""

    def clean(self, node_id: NodeId, messages: PendingMessages) -> CleanResult:
        """
        Process a node's pending messages and produce new messages.

        Preconditions: node_id must exist in the graph; graph topology is accessible.

        Postconditions:
        - On success: provides ChangeResult (broadcast messages to reverse
          dependencies), FeedbackResult (deliver messages to specific
          dependencies), or NoChangeResult (no messages)
        - On failure: provides FailureResult
        - Produces either change or feedback messages, not both.
        - Caller routes change messages to reverse dependencies; feedback
          messages to specified dependencies.

        Failure Handling:
        - On failure, provides FailureResult; no messages are produced and
          pending messages remain unchanged.

        HLS Justification: "The client may invoke cleaning on a node with its pending messages."
        """
        ...

    def is_dirty(self, node_id: NodeId, pending_messages: PendingMessages) -> bool:
        """
        Determine if a node requires cleaning.

        Preconditions: node_id must exist in the graph; graph topology is accessible.
        Postconditions: Signals dirtiness if the node has pending messages, or if
                       custom dirtiness conditions defined by the implementation
                       hold (e.g., the node's writable output files do not exist
                       on disk).

        HLS Justification: "The client may query whether a node is dirty."
        """
        ...
