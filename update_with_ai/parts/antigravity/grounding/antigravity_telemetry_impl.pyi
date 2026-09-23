from framework import operation, override, singleton_type
from typing import Optional, Sequence
import antigravity_telemetry

@singleton_type('system')
class AntigravityTelemetry(antigravity_telemetry.AntigravityTelemetry):
    """
PURPOSE:
Realizes token extraction, prompt cache rate computation, and API cost accounting for Antigravity conversations.

GROUNDING_ARGUMENT:
- System singleton querying conversation databases, aggregating prompt cache hit rates, checking caps, and formatting markdown tables.
"""

    @operation
    @override
    def get_conversation_stats(self, identifier: str) -> Optional[antigravity_telemetry.ConversationStats]:
        """
PURPOSE:
Queries conversation databases and transcript logs for the specified conversation identifier to compute token metrics.

FRESH_REQUIREMENTS:
- Extracting conversation stats queries conversation databases and transcript logs for the specified conversation identifier.
- The telemetry service aggregates turns, context tokens from the final turn, fresh input tokens, cached input tokens, and output tokens.
- The cache hit percentage is computed as cached tokens divided by the sum of fresh and cached input tokens.

INHERITED_REQUIREMENTS:
- [AntigravityTelemetry] The antigravity telemetry extracts a conversation stats record for a conversation identifier.

GROUNDING_ARGUMENT:
- Reads conversation SQLite database or transcript jsonl for turn records, extracts usage metadata, and instantiates ConversationStats.
"""
        ...

    @operation
    @override
    def get_coordinator_run_stats(self, coordinator_id: str) -> Sequence[antigravity_telemetry.ConversationStats]:
        """
PURPOSE:
Discovers all child worker conversations associated with a coordinator identifier, gathering metrics for each child and computing cumulative totals.

FRESH_REQUIREMENTS:
- Extracting coordinator run stats discovers all child worker conversations associated with a coordinator identifier, gathering metrics for each child and computing cumulative totals.

INHERITED_REQUIREMENTS:
- [AntigravityTelemetry] The antigravity telemetry extracts conversation stats across all worker conversations spawned by a coordinator identifier.

GROUNDING_ARGUMENT:
- Scans conversation subagent manifests referencing the coordinator parent, retrieves stats for each, and appends a summary total row.
"""
        ...

    @operation
    @override
    def check_context_cap(self, identifier: str, threshold: int) -> bool:
        """
PURPOSE:
Compares the conversation context tokens against the specified threshold, returning true when the context exceeds the threshold.

FRESH_REQUIREMENTS:
- Checking a context cap compares the conversation context tokens against the specified threshold, returning true when the context exceeds the threshold.

INHERITED_REQUIREMENTS:
- [AntigravityTelemetry] The antigravity telemetry evaluates whether the context tokens of a conversation identifier exceed a specified threshold.

GROUNDING_ARGUMENT:
- Retrieves conversation context tokens and returns context_tokens >= threshold.
"""
        ...

    @operation
    @override
    def render_stats_table(self, stats: Sequence[antigravity_telemetry.ConversationStats]) -> str:
        """
PURPOSE:
Constructs a formatted markdown table displaying agent name, turns, context, fresh input, cached input, hit percentage, output, and estimated cost dollars.

FRESH_REQUIREMENTS:
- Rendering a stats table constructs a formatted markdown table displaying agent name, turns, context, fresh input, cached input, hit percentage, output, and estimated cost dollars.

INHERITED_REQUIREMENTS:
- [AntigravityTelemetry] The antigravity telemetry formats a collection of conversation stats records into a markdown table.

GROUNDING_ARGUMENT:
- Formats markdown table lines with aligned column headers and formatted integer/dollar strings.
"""
        ...

    @operation
    @override
    def calculate_cost(self, fresh_tokens: int, cached_tokens: int, output_tokens: int, model: str) -> float:
        """
PURPOSE:
Applies pricing rates per million tokens based on the pricing model.

FRESH_REQUIREMENTS:
- For `gemini-3.8-flash` pricing, rates apply fifty cents per million cached input tokens, two dollars per million fresh input tokens, and twelve dollars per million output tokens.
- For `deepseek` pricing, rates apply fourteen cents per million cached input tokens, twenty-eight cents per million fresh input tokens, and two dollars nineteen cents per million output tokens.

INHERITED_REQUIREMENTS:
- [AntigravityTelemetry] The antigravity telemetry computes estimated cost dollars from fresh input tokens, cached input tokens, output tokens, and a pricing model.

GROUNDING_ARGUMENT:
- Multiplies input token counts by configured pricing rates per million and returns total dollar cost.
"""
        ...
