# agent_loop_impl

fulfills: agent_loop
imports: agent_loop_config (agent-loop configuration), tool_provider (tool results, signals, tool call), conversation_history (conversation management, system prompt), loop_guard (loop repetition and guardrails, degenerate response)
terms (from agent_loop): run, termination value, conversation, truncated response
terms (from conversation_history): conversation history, history entry, rendered message, system prompt
terms (from loop_guard): loop repetition, range repetition, loop reminder, degenerate loop, degenerate response
terms (from tool_provider): tool failure, supersession flag, stub, tool result, tool call
terms (refined): continuation prompt

## Deltas

- Uses the OpenAI API for language model processing.
- Language-model requests use the configured sampling temperature and request timeout.
- The default maximum number of loop iterations is ten; the default sampling temperature is 0.0; the default request timeout is 60 seconds; each default applies when the loop is constructed without an explicit value.
- Delegates conversation management, OpenAI message formatting, synthetic tool call injection, and in-place tool result stubbing to conversation_history.
- Delegates tool call repetition tracking, line-range repetition tracking, degenerate response detection, and termination reminder generation to loop_guard.
- Delegates tool execution to the provided tool_provider logic; continues until completion, termination, or failure.
- Tool failures are appended to the conversation and the loop continues; they do not signal an agent failure.
- A model response that stops at the generation limit (the API's truncation signal) is not treated as complete; the loop appends the continuation prompt and continues with a follow-up request.
- When loop_guard detects a degenerate truncated response or a degenerate loop, signals failure without resuming generation.
- Token usage (input, cached input, output) and request duration (seconds) are extracted for each API response; session totals and duration are tracked and reported on session termination.
- [ordering] Logger callbacks are invoked after data is appended to history.
- [state] No persistence or caching across runs; conversation history and usage metrics are provided in the result and not retained.
- [external] The OpenAI API (external language model service); the run's configuration — the service endpoint, credentials, and model; the maximum number of loop iterations; the sampling temperature; the request timeout; the maximum token count; and an optional termination reminder generator — supplied when the loop is constructed.
- [refines] continuation prompt -> the fixed default continuation prompt message, appended as a user message when a continuation prompt is not configured; the text is pinned in the implementation LLS.

## Non-concerns

- Retry behavior: whether failed API calls are retried is unspecified; any failure signals the run's failure.
