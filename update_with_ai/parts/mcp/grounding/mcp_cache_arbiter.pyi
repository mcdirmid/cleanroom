from dataclasses import dataclass
from typing import Protocol, Sequence
from framework import data_type, operation, singleton_type, variant
import mcp_session


@dataclass(frozen=True, init=False)
@data_type
class CacheRoutingAction:
    """Classifies a decision governing how an idle sub-agent should be engaged when work becomes ready."""
    ...


@dataclass(frozen=True)
@variant
class WarmCacheWakeup(CacheRoutingAction):
    """Indicates that the sub-agent cache remains warm, directing the worker to resume."""

    def __init__(self, conversation_id: mcp_session.ConversationId, role_address: str, wakeup_prompt: str) -> None:
        ...

    @property
    def conversation_id(self) -> mcp_session.ConversationId:
        """Identifies the target sub-agent conversation."""
        ...

    @property
    def role_address(self) -> str:
        """Specifies the role address of the sub-agent."""
        ...

    @property
    def wakeup_prompt(self) -> str:
        """Provides the prompt directing the sub-agent to retrieve tasks."""
        ...


@dataclass(frozen=True)
@variant
class ColdCacheRecycle(CacheRoutingAction):
    """Indicates that the sub-agent cache has expired, directing coordinator recycling."""

    def __init__(self, conversation_id: mcp_session.ConversationId, role_address: str, unit_root: str, recycle_prompt: str) -> None:
        ...

    @property
    def conversation_id(self) -> mcp_session.ConversationId:
        """Identifies the stale sub-agent conversation to terminate."""
        ...

    @property
    def role_address(self) -> str:
        """Specifies the role address of the sub-agent to recreate."""
        ...

    @property
    def unit_root(self) -> str:
        """Specifies the target unit root label for worker recreation."""
        ...

    @property
    def recycle_prompt(self) -> str:
        """Provides the instruction directing the coordinator to recycle the worker."""
        ...


@dataclass(frozen=True)
@variant
class NoRoutingAction(CacheRoutingAction):
    """Indicates that no work is ready or that no routing transition is warranted."""

    def __init__(self) -> None:
        ...


@singleton_type('system')
class CacheArbiter(Protocol):
    """System service that monitors idle sub-agent sessions and determines cache-aware routing actions.

    REQUIREMENTS:
    - Evaluating session readiness produces a warm cache wakeup when ready dirty nodes exist and elapsed inactivity is at most nine hundred seconds.
    - Evaluating session readiness produces a cold cache recycle when ready dirty nodes exist and elapsed inactivity exceeds nine hundred seconds.
    - Evaluating all idle sessions produces routing actions for all idle sessions with ready work.
    """

    @operation
    def evaluate_session_readiness(self, conversation_id: mcp_session.ConversationId) -> CacheRoutingAction:
        """Evaluates task readiness and cache window for a specified conversation.

        GROUNDING_PROVISIONS:
        - action("evaluate_session_readiness", CacheRoutingAction): Evaluates session readiness against cache window and dirty nodes.
        """
        ...

    @operation
    def evaluate_all_idle_sessions(self) -> Sequence[CacheRoutingAction]:
        """Evaluates task readiness across all currently idle registered sessions.

        GROUNDING_PROVISIONS:
        - action("evaluate_all_idle_sessions", Sequence[CacheRoutingAction]): Evaluates all idle sessions with ready work.
        """
        ...
