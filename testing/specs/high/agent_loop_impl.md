# agent_loop_impl

fulfills: agent_loop
imports: agent_loop_config (agent-loop configuration), tool_provider (tool results, signals)
terms (from agent_loop): run, termination value, conversation, system prompt, truncated response, degenerate response
terms (from tool_provider): tool failure, supersession flag, stub, tool result
terms (refined): continuation prompt

## Deltas

- Uses the OpenAI API for language model processing.
- Language-model requests use the configured sampling temperature and request timeout.
- The default maximum number of loop iterations is ten; the default sampling temperature is 0.0; the default request timeout is 60 seconds; each default applies when the loop is constructed without an explicit value.
- Maintains the conversation history for the duration of a run; sends the system prompt, the conversation, and the tool definitions to the OpenAI API; appends responses; delegates tool execution to the provided logic; continues until completion, termination, or failure.
- Stubbing follows the tool_provider semantics: when a result's supersession flag is set, the earlier result for the same file or tool command is replaced in place with the static stub before the new result is appended; stubbed messages keep their positions.
- The stub is a fixed placeholder, so a stubbed message's content never changes once set; the conversation up to the most recent live result for a file or tool command is byte-identical across requests, preserving the model service's prefix caching.
- [ordering] The conversation is append-only except for stubbing: prior messages are never rewritten or reordered.
- Tool failures are appended to the conversation and the loop continues; they do not signal an agent failure.
- A model response that stops at the generation limit (the API's truncation signal) is not treated as complete; the loop appends the continuation prompt and continues with a follow-up request.
- A truncated response whose content is a single character repeated (a degenerate response) signals failure; the loop does not resume generation.
- If a termination reminder generator is configured, the reminder is injected at most once per run.
- The termination reminder uses the configured generator's message when one is configured, and the default message otherwise; a configured generator produces conversation messages in the same format as other conversation messages.
- [state] Repetition counts consecutive identical tool calls, or file-editing calls targeting the same file and line range (even with different content); any other call resets the count; the advance call is exempt and resets it; four consecutive repeats inject the loop reminder; eight signal failure.
- Token usage (input, cached input, output, total) and request duration (seconds) are extracted for each API response; session totals and duration are tracked and reported on session termination.
- [ordering] Logger callbacks are invoked after data is appended to history.
- [ordering] Stubbing is applied when a result with the supersession flag set is processed, before the next request is sent; a stub set by a result is reflected in the request that follows it.
- [ordering] The results a tool call produces are appended in the order produced; stubbing is applied per a result's flag before the next result of the same call is appended.
- [ordering] A tool result whose tool call the model did not make is presented with its tool call immediately before the result, so the conversation contains no tool result without its preceding call.
- [ordering] Session-start tool results are rendered immediately after the user prompt (or at the start of the conversation when the prompt is empty), before the model's first request; each result is presented with the tool call it carries.
- [state] No persistence or caching; the conversation history is provided in the result and not retained; the mapping between results and the file or tool command they concern exists only for the duration of the run.
- [external] The OpenAI API (external language model service); the run's configuration — the service endpoint, credentials, and model; the maximum number of loop iterations; the sampling temperature; the request timeout; the maximum token count; and an optional termination reminder generator — supplied when the loop is constructed.
- [refines] continuation prompt -> the fixed default continuation prompt message, appended as a user message when a continuation prompt is not configured; the text is pinned in the implementation LLS.

## Non-concerns

- Retry behavior: whether failed API calls are retried is unspecified; any failure signals the run's failure.
