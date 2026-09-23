from dataclasses import dataclass
from framework import data_type, operation, singleton_type
from typing import Optional, Sequence

@data_type
@dataclass(frozen=True)
class ConversationStats:
    """
PURPOSE:
Encapsulates token usage metrics for a subagent conversation, exposing an agent name, a turns count, a context tokens size, a fresh input tokens count, a cached input tokens count, a cache hit percentage, an output tokens count, and an estimated cost dollars.

FRESH_REQUIREMENTS:
- A conversation stats record encapsulates token usage metrics for a subagent conversation, exposing an agent name, a turns count, a context tokens size, a fresh input tokens count, a cached input tokens count, a cache hit percentage, an output tokens count, and an estimated cost dollars.
"""

    def __init__(self, agent_name: str, turns: int, context_tokens: int, fresh_input_tokens: int, cached_input_tokens: int, cache_hit_percentage: float, output_tokens: int, estimated_cost_dollars: float) -> None:
        ...

    @property
    def agent_name(self) -> str:
        """
PURPOSE:
Exposes display name or role of the agent.
"""
        ...

    @property
    def turns(self) -> int:
        """
PURPOSE:
Exposes total turn count of the conversation.
"""
        ...

    @property
    def context_tokens(self) -> int:
        """
PURPOSE:
Exposes current context size in tokens.
"""
        ...

    @property
    def fresh_input_tokens(self) -> int:
        """
PURPOSE:
Exposes cumulative non-cached input tokens.
"""
        ...

    @property
    def cached_input_tokens(self) -> int:
        """
PURPOSE:
Exposes cumulative cached input tokens.
"""
        ...

    @property
    def cache_hit_percentage(self) -> float:
        """
PURPOSE:
Exposes cache hit ratio.
"""
        ...

    @property
    def output_tokens(self) -> int:
        """
PURPOSE:
Exposes cumulative generated output tokens.
"""
        ...

    @property
    def estimated_cost_dollars(self) -> float:
        """
PURPOSE:
Exposes total estimated API dollar cost.
"""
        ...

@singleton_type('system')
class AntigravityTelemetry:
    """
PURPOSE:
System service that extracts token statistics and computes usage metrics across conversations.
"""

    @operation
    def get_conversation_stats(self, identifier: str) -> Optional[ConversationStats]:
        """
PURPOSE:
Extracts a conversation stats record for a conversation identifier.

FRESH_REQUIREMENTS:
- The antigravity telemetry extracts a conversation stats record for a conversation identifier.
"""
        ...

    @operation
    def get_coordinator_run_stats(self, coordinator_id: str) -> Sequence[ConversationStats]:
        """
PURPOSE:
Extracts conversation stats across all worker conversations spawned by a coordinator identifier.

FRESH_REQUIREMENTS:
- The antigravity telemetry extracts conversation stats across all worker conversations spawned by a coordinator identifier.
"""
        ...

    @operation
    def check_context_cap(self, identifier: str, threshold: int) -> bool:
        """
PURPOSE:
Evaluates whether the context tokens of a conversation identifier exceed a specified threshold.

FRESH_REQUIREMENTS:
- The antigravity telemetry evaluates whether the context tokens of a conversation identifier exceed a specified threshold.
"""
        ...

    @operation
    def render_stats_table(self, stats: Sequence[ConversationStats]) -> str:
        """
PURPOSE:
Formats a collection of conversation stats records into a markdown table.

FRESH_REQUIREMENTS:
- The antigravity telemetry formats a collection of conversation stats records into a markdown table.
"""
        ...

    @operation
    def calculate_cost(self, fresh_tokens: int, cached_tokens: int, output_tokens: int, model: str) -> float:
        """
PURPOSE:
Computes estimated cost dollars from fresh input tokens, cached input tokens, output tokens, and a pricing model.

FRESH_REQUIREMENTS:
- The antigravity telemetry computes estimated cost dollars from fresh input tokens, cached input tokens, output tokens, and a pricing model.
"""
        ...
