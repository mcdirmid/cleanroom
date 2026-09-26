# Requirements specified in agent_config.pyi
"""Agent configuration interface and data types."""

from typing import Protocol

ConversationLimit = int


class AgentConfig(Protocol):
    @property
    def conversation_limit(self) -> ConversationLimit: ...

    @property
    def inject_followups(self) -> bool: ...

    @property
    def is_step_mode(self) -> bool: ...

    @property
    def is_startup_reads(self) -> bool: ...

    @property
    def edit_delta_output(self) -> bool: ...

    @property
    def is_mcp_mode(self) -> bool: ...

    @property
    def supersede_arg_keep(self) -> int: ...

