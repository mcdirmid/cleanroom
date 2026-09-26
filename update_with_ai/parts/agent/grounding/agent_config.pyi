from typing import Protocol
from framework import data_type, singleton_type
from support.lib.lifecycle import InTier, SystemTier


@data_type
class ConversationLimit(int):
    """Bound on the maximum number of model interaction turns permitted."""
    ...


@singleton_type("system")
class AgentConfig(InTier[SystemTier], Protocol):
    """Provides execution parameters for agent sessions."""

    @property
    def conversation_limit(self) -> ConversationLimit:
        """Bound on the maximum number of model interaction turns.

        REQUIREMENTS:
        - MUST provide the conversation limit bounding interaction turns.

        GROUNDING_PROVISIONS:
        - knows("conversation_turn_limit", ConversationLimit): Exposes the conversation turn limit to satisfy requirement 1.
        """
        ...

    @property
    def inject_followups(self) -> bool:
        """Indicates whether the agent should inject followups to execute follow-up tool calls.

        REQUIREMENTS:
        - MUST provide whether the agent should inject followups to execute follow-up tool calls.

        GROUNDING_PROVISIONS:
        - knows("followup_injection_enabled", bool): Exposes whether follow-up tool calls are injected to satisfy requirement 2.
        """
        ...

    @property
    def is_step_mode(self) -> bool:
        """Indicates whether the agent should use step mode to communicate a guide progressively.

        REQUIREMENTS:
        - MUST provide whether the agent should use step mode to communicate a guide progressively.

        GROUNDING_PROVISIONS:
        - knows("step_mode_enabled", bool): Exposes whether progressive step mode is active to satisfy requirement 3.
        """
        ...

    @property
    def is_startup_reads(self) -> bool:
        """Indicates whether the agent should perform startup reads to read declared files.

        REQUIREMENTS:
        - MUST provide whether the agent should perform startup reads to read declared files.

        GROUNDING_PROVISIONS:
        - knows("startup_reads_enabled", bool): Exposes whether startup file reads are performed to satisfy requirement 4.
        """
        ...

    @property
    def edit_delta_output(self) -> bool:
        """Indicates whether editing tools should produce delta output.

        REQUIREMENTS:
        - MUST provide whether editing tools should produce delta output.

        GROUNDING_PROVISIONS:
        - knows("delta_output_enabled", bool): Exposes whether editing tools produce delta output to satisfy requirement 5.
        """
        ...

    @property
    def is_mcp_mode(self) -> bool:
        """Indicates whether the agent should operate in mcp mode.

        REQUIREMENTS:
        - MUST provide whether the agent should operate in mcp mode.

        GROUNDING_PROVISIONS:
        - knows("mcp_mode", bool): Exposes whether mcp mode is active to satisfy requirement 6.
        """
        ...

    @property
    def supersede_arg_keep(self) -> int:
        """Trailing character retention limit for string arguments on superseded tool calls.

        REQUIREMENTS:
        - MUST provide the character retention limit bounding preserved string argument tails when tool responses are superseded.

        GROUNDING_PROVISIONS:
        - knows("supersede_arg_keep", int): Exposes the character retention limit for superseded tool calls to satisfy requirement 7.
        """
        ...

