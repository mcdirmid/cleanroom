# Requirements specified in antigravity_telemetry.pyi
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


@dataclass(frozen=True)
class ConversationStats:
    agent_name: str
    turns: int
    context_tokens: int
    fresh_input_tokens: int
    cached_input_tokens: int
    cache_hit_percentage: float
    output_tokens: int
    estimated_cost_dollars: float


class AntigravityTelemetry(Protocol):
    def get_conversation_stats(self, identifier: str) -> Optional[ConversationStats]: ...

    def get_coordinator_run_stats(self, coordinator_id: str) -> Sequence[ConversationStats]: ...

    def check_context_cap(self, identifier: str, threshold: int) -> bool: ...

    def render_stats_table(self, stats: Sequence[ConversationStats]) -> str: ...

    def calculate_cost(self, fresh_tokens: int, cached_tokens: int, output_tokens: int, model: str) -> float: ...
