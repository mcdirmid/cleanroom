"""
lib/agent_loop_config.py

Interface for the agent-loop configuration: the complete set of connection
and processing parameters supplied when an agent loop is constructed. The
type is produced by the build_agent_config component and consumed by the
agent_loop_impl component, exchanged without an interface-to-implementation
import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from .agent_loop import TerminationReminderGenerator


@dataclass
class AgentLoopConfig:
    """The run's configuration, supplied when the loop is constructed:
    connection and processing parameters, an optional iteration limit, and an
    optional termination reminder generator."""
    base_url: str
    api_key: str
    model: str
    max_iterations: int = 10
    temperature: float = 0.0
    timeout: float = 60.0
    max_tokens: Optional[int] = None
    termination_reminder_generator: Optional[TerminationReminderGenerator] = None
    continuation_prompt: Optional[str] = None


class AgentLoopConfigProvider(Protocol):
    """Documents the construction operation (per the interface LLS); the
    dataclass constructor is the concrete construction entry point."""

    def construct(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_iterations: int = 10,
        temperature: float = 0.0,
        timeout: float = 60.0,
        max_tokens: Optional[int] = None,
        termination_reminder_generator: Optional[TerminationReminderGenerator] = None,
        continuation_prompt: Optional[str] = None,
    ) -> AgentLoopConfig:
        ...


__all__ = ["AgentLoopConfig", "AgentLoopConfigProvider"]
