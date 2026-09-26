# antigravity_telemetry interface component

## Assumptions and Requirements

### Requirements

1. A conversation stats record encapsulates token usage metrics for a subagent conversation, exposing an agent name, a turns count, a context tokens size, a fresh input tokens count, a cached input tokens count, a cache hit percentage, an output tokens count, and an estimated cost dollars.
2. The antigravity telemetry extracts a conversation stats record for a conversation identifier.
3. The antigravity telemetry extracts conversation stats across all worker conversations spawned by a coordinator identifier.
4. The antigravity telemetry evaluates whether the context tokens of a conversation identifier exceed a specified threshold.
5. The antigravity telemetry formats a collection of conversation stats records into a markdown table.
6. The antigravity telemetry computes estimated cost dollars from fresh input tokens, cached input tokens, output tokens, and a pricing model.

## Grounding Facts

### Knowledge Needed

- Conversation identifier.
- Token counts (context tokens, fresh input tokens, cached input tokens, output tokens).
- Pricing model rates.
- Context token ceiling threshold.

### Actions Needed

- Extract conversation statistics from logs.
- Aggregate child conversation statistics for coordinator.
- Compare context tokens against threshold.
- Compute estimated cost dollars from token counts and pricing rates.
- Format stats records into markdown table.
