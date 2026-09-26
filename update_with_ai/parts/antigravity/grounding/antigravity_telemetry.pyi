from dataclasses import dataclass
from framework import data_type, operation, singleton_type
from typing import Optional, Sequence

@data_type
@dataclass(frozen=True)
class ConversationStats:
    """Encapsulates token usage metrics for a subagent conversation.

    REQUIREMENTS:
    - A conversation stats record encapsulates token usage metrics for a subagent conversation, exposing an agent name, a turns count, a context tokens size, a fresh input tokens count, a cached input tokens count, a cache hit percentage, an output tokens count, and an estimated cost dollars.

    GROUNDING_PROVISIONS:
    - knows("agent_name", Self)
    - knows("turns", Self)
    - knows("context_tokens", Self)
    - knows("fresh_input_tokens", Self)
    - knows("cached_input_tokens", Self)
    - knows("cache_hit_percentage", Self)
    - knows("output_tokens", Self)
    - knows("estimated_cost_dollars", Self)
    """

    def __init__(self, agent_name: str, turns: int, context_tokens: int, fresh_input_tokens: int, cached_input_tokens: int, cache_hit_percentage: float, output_tokens: int, estimated_cost_dollars: float) -> None:
        ...

    @property
    def agent_name(self) -> str:
        ...

    @property
    def turns(self) -> int:
        ...

    @property
    def context_tokens(self) -> int:
        ...

    @property
    def fresh_input_tokens(self) -> int:
        ...

    @property
    def cached_input_tokens(self) -> int:
        ...

    @property
    def cache_hit_percentage(self) -> float:
        ...

    @property
    def output_tokens(self) -> int:
        ...

    @property
    def estimated_cost_dollars(self) -> float:
        ...

@singleton_type('system')
class AntigravityTelemetry:
    """System service that extracts token statistics and computes usage metrics across conversations.

    REQUIREMENTS:
    - The antigravity telemetry extracts a conversation stats record for a conversation identifier.
    - The antigravity telemetry extracts conversation stats across all worker conversations spawned by a coordinator identifier.
    - The antigravity telemetry evaluates whether the context tokens of a conversation identifier exceed a specified threshold.
    - The antigravity telemetry formats a collection of conversation stats records into a markdown table.
    - The antigravity telemetry computes estimated cost dollars from fresh input tokens, cached input tokens, output tokens, and a pricing model.

    GROUNDING_PROVISIONS:
    - action("extract_conversation_stats", Optional[ConversationStats]): Extracts token metrics from conversation logs.
    - action("aggregate_coordinator_stats", Sequence[ConversationStats]): Aggregates worker conversation stats for coordinator.
    - action("check_context_cap", bool): Evaluates whether conversation context tokens exceed threshold.
    - action("format_stats_table", str): Formats stats records into markdown table.
    - action("calculate_cost", float): Computes cost dollars from token counts and pricing rates.
    """

    @operation
    def get_conversation_stats(self, identifier: str) -> Optional[ConversationStats]:
        ...

    @operation
    def get_coordinator_run_stats(self, coordinator_id: str) -> Sequence[ConversationStats]:
        ...

    @operation
    def check_context_cap(self, identifier: str, threshold: int) -> bool:
        ...

    @operation
    def render_stats_table(self, stats: Sequence[ConversationStats]) -> str:
        ...

    @operation
    def calculate_cost(self, fresh_tokens: int, cached_tokens: int, output_tokens: int, model: str) -> float:
        ...
