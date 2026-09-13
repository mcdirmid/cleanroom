from typing import Protocol
from framework import data_type, singleton_type

@data_type
class ConversationLimit(int):
    """
PURPOSE:
Bound on the maximum number of model interaction turns permitted
"""
    ...

@singleton_type('system')
class AgentConfig(Protocol):
    """
PURPOSE:
Defined as a system service providing execution parameters for agent sessions
"""

    @property
    def conversation_limit(self) -> ConversationLimit:
        """
PURPOSE:
Bound on the maximum number of model interaction turns

FRESH_REQUIREMENTS:
- The agent config provides the conversation limit bounding interaction turns.
"""
        ...

    @property
    def inject_followups(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should inject followups to execute follow-up tool calls specified by tool responses

FRESH_REQUIREMENTS:
- The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.
"""
        ...

    @property
    def is_step_mode(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should use step mode to communicate a guide progressively

FRESH_REQUIREMENTS:
- The agent config provides whether the agent should use step mode to communicate a guide progressively.
"""
        ...

    @property
    def is_startup_reads(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should perform startup reads to inspect declared files at session start

FRESH_REQUIREMENTS:
- The agent config provides whether the agent should perform startup reads to inspect declared files at session start.
"""
        ...
