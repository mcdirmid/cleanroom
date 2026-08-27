"""
dag_clean_logic — Interface for DAG cleaning logic.

This module defines the DagCleanLogic Protocol and associated result types
for cleaning nodes in a DAG (Directed Acyclic Graph). Implementations live
in the _impl module.
"""

from __future__ import annotations

from dag_storage import NodeId, PendingMessages, NodeMessage
from tool_provider import TerminateSuccessResult
from typing import Protocol, Union, Literal, TypeAlias
from dataclasses import dataclass


@dataclass
class ChangeResult(TerminateSuccessResult):
    """Messages to broadcast to all reverse dependencies (nodes that depend on this node)."""
    messages: list[NodeMessage]
    type: Literal["change"] = "change"


@dataclass
class FeedbackResult(TerminateSuccessResult):
    """Messages to deliver to specific dependencies (tuples of target node and message)."""
    messages: list[tuple[NodeId, NodeMessage]]
    type: Literal["feedback"] = "feedback"


@dataclass
class NoChangeResult(TerminateSuccessResult):
    """Node cleaned successfully, no messages produced."""
    type: Literal["no_change"] = "no_change"


@dataclass
class FailureResult:
    """Cleaning failed, no messages produced."""
    type: Literal["failure"] = "failure"


CleanResult: TypeAlias = Union[ChangeResult, FeedbackResult, NoChangeResult, FailureResult]


class DagCleanLogic(Protocol):
    """Protocol for DAG cleaning logic.

    Operations:
        clean: Process a node's pending messages and produce new messages.
        is_dirty: Determine if a node requires cleaning.
    """

    def clean(self, node_id: NodeId, messages: PendingMessages) -> CleanResult:
        """Process a node's pending messages and produce new messages.

        On success: provides ChangeResult (broadcast messages to reverse
        dependencies), FeedbackResult (deliver messages to specific
        dependencies), or NoChangeResult (no messages). All pending messages
        were processed. Produced messages are valid for delivery.

        On failure: provides FailureResult; no messages are produced and
        pending messages remain unchanged.

        A node produces either change or feedback messages, not both.
        When messages includes a feedback message, provides no NoChangeResult.
        """
        ...

    def is_dirty(self, node_id: NodeId, pending_messages: PendingMessages) -> bool:
        """Determine if a node requires cleaning.

        Signals dirtiness if the node has pending messages or custom
        dirtiness conditions defined by the implementation hold.
        """
        ...

