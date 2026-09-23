# antigravity_telemetry_impl implementation component

implements: antigravity_telemetry

## Purpose

The antigravity_telemetry_impl implementation component realizes token extraction, prompt cache rate computation, and API cost accounting for Antigravity conversations.

Monitoring subagent token consumption across Antigravity desktop environments requires querying conversation SQLite databases, reading step transcripts, and applying current model API pricing. The antigravity_telemetry_impl implementation component extracts turn metrics, calculates cache hit ratios, checks context caps, and produces markdown summaries.

**Out of scope:** The antigravity_telemetry_impl implementation component does not manage worker lifecycles, register session tokens, or edit source code; these are handled by other components.

## Types and Behavior

The antigravity telemetry operates as a system service calculating usage metrics and API costs.

Extracting conversation stats queries conversation databases and transcript logs for the specified conversation identifier. The telemetry service aggregates turns, context tokens from the final turn, fresh input tokens, cached input tokens, and output tokens. The cache hit percentage is computed as cached tokens divided by the sum of fresh and cached input tokens.

Extracting coordinator run stats discovers all child worker conversations associated with a coordinator identifier, gathering metrics for each child and computing cumulative totals.

Checking a context cap compares the conversation context tokens against the specified threshold, returning true when the context exceeds the threshold.

Rendering a stats table constructs a formatted markdown table displaying agent name, turns, context, fresh input, cached input, hit percentage, output, and estimated cost dollars.

Calculating cost applies pricing rates per million tokens based on the pricing model:

- For `gemini-3.8-flash` pricing, rates apply fifty cents per million cached input tokens, two dollars per million fresh input tokens, and twelve dollars per million output tokens.

- For `deepseek` pricing, rates apply fourteen cents per million cached input tokens, twenty-eight cents per million fresh input tokens, and two dollars nineteen cents per million output tokens.
