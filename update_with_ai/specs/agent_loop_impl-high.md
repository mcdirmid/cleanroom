# agent_loop_impl

fulfills: agent_loop
imports: tool_provider (tool results, signals)
terms (from agent_loop): run, termination value, conversation, system prompt, truncated response, degenerate response
terms (from tool_provider): tool failure, supersession flag, stub
terms (refined): continuation prompt

## Deltas

- Uses the OpenAI API for language model processing.
- Maintains the conversation history for the duration of a run; sends the system prompt, the conversation, and the tool definitions to the OpenAI API; appends responses; delegates tool execution to the provided logic; continues until completion, termination, or failure.
- Stubbing follows the tool_provider semantics: when a result's supersession flag is set, the earlier result for the same file or tool command is replaced in place with the static stub before the new result is appended; stubbed messages keep their positions.
- The stub is a fixed placeholder, so a stubbed message's content never changes once set; the conversation up to the most recent live result for a file or tool command is byte-identical across requests, preserving the model service's prefix caching.
- Tool failures are appended to the conversation and the loop continues; they do not signal an agent failure.
- A model response that stops at the generation limit (the API's truncation signal) is not treated as complete; the loop appends the continuation prompt and continues with a follow-up request.
- A truncated response whose content is a single character repeated (a degenerate response) signals failure; the loop does not resume generation.
- Tool calls present in a truncated response are never executed.
- If a termination reminder generator is configured, the reminder is injected at most once per run.
- Token usage is extracted from each API response and included in logger events.
- [ordering] Logger callbacks are invoked after data is appended to history.
- [ordering] Stubbing is applied when a result with the supersession flag set is processed, before the next request is sent; a stub set by a result is reflected in the request that follows it.
- [state] No persistence or caching; the conversation history is provided in the result and not retained; the mapping between results and the file or tool command they concern exists only for the duration of the run.
- [external] The OpenAI API (external language model service).
- [failure] A truncated response does not halt the run; generation resumes via the continuation prompt.
- [refines] continuation prompt -> the fixed default continuation prompt message, appended as a user message when a continuation prompt is not configured; the text is pinned in the implementation LLS.

## Non-concerns

- Retry behavior: whether failed API calls are retried is unspecified; any failure signals the run's failure.
