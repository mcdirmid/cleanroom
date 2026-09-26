from framework import operation, override, singleton_type
from typing import Optional, Self, Sequence
import antigravity_telemetry

@singleton_type('system')
class AntigravityTelemetry(antigravity_telemetry.AntigravityTelemetry):
    """Realizes token extraction, prompt cache rate computation, and API cost accounting for Antigravity conversations.

    GROUNDING_ARGUMENT:
    - System singleton querying conversation databases, aggregating prompt cache hit rates, checking caps, and formatting markdown tables.
    """

    @operation
    @override
    def get_conversation_stats(self, identifier: str) -> Optional[antigravity_telemetry.ConversationStats]:
        """
        REQUIREMENTS:
        - Extracting conversation stats queries conversation databases and transcript logs for the specified conversation identifier.
        - The telemetry service aggregates turns, context tokens from the final turn, fresh input tokens, cached input tokens, and output tokens.
        - The cache hit percentage is computed as cached tokens divided by the sum of fresh and cached input tokens.

        GROUNDING_IMPLEMENTS:
        - action("extract_conversation_stats", Optional[antigravity_telemetry.ConversationStats]): Extracts stats for conversation.
        """
        ...

    @operation
    @override
    def get_coordinator_run_stats(self, coordinator_id: str) -> Sequence[antigravity_telemetry.ConversationStats]:
        """
        REQUIREMENTS:
        - Extracting coordinator run stats discovers all child worker conversations associated with a coordinator identifier, gathering metrics for each child and computing cumulative totals.

        GROUNDING_IMPLEMENTS:
        - action("aggregate_coordinator_stats", Sequence[antigravity_telemetry.ConversationStats]): Extracts stats across workers.
        """
        ...

    @operation
    @override
    def check_context_cap(self, identifier: str, threshold: int) -> bool:
        """
        REQUIREMENTS:
        - Checking a context cap compares the conversation context tokens against the specified threshold, returning true when the context exceeds the threshold.

        GROUNDING_IMPLEMENTS:
        - action("check_context_cap", bool): Checks if context tokens exceed threshold.
        """
        ...

    @operation
    @override
    def render_stats_table(self, stats: Sequence[antigravity_telemetry.ConversationStats]) -> str:
        """
        REQUIREMENTS:
        - Rendering a stats table constructs a formatted markdown table displaying agent name, turns, context, fresh input, cached input, hit percentage, output, and estimated cost dollars.

        GROUNDING_IMPLEMENTS:
        - action("format_stats_table", str): Renders markdown table.
        """
        ...

    @operation
    @override
    def calculate_cost(self, fresh_tokens: int, cached_tokens: int, output_tokens: int, model: str) -> float:
        """
        REQUIREMENTS:
        - For `gemini-3.8-flash` pricing, rates apply fifty cents per million cached input tokens, two dollars per million fresh input tokens, and twelve dollars per million output tokens.
        - For `deepseek` pricing, rates apply fourteen cents per million cached input tokens, twenty-eight cents per million fresh input tokens, and two dollars nineteen cents per million output tokens.

        GROUNDING_IMPLEMENTS:
        - action("calculate_cost", float): Computes cost dollars.
        """
        ...
