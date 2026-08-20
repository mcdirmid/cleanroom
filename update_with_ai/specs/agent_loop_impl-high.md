# agent_loop_impl

fulfills: agent_loop
imports: tool_provider (tool results, signals)
terms (from agent_loop): run, termination value, conversation, truncated response, degenerate response
terms (from tool_provider): tool failure
terms (refined): continuation prompt -> the fixed default continuation prompt message used when a continuation prompt is not configured

## Deltas beyond the agent_loop contract

### Behavior

- Uses the OpenAI API for language model processing.
- Maintains conversation history for the duration of a run; sends conversation and tool definitions to the OpenAI API; appends responses; delegates tool execution to the provided logic; continues until completion, termination, or failure.
- Deduplication behavior follows the tool_provider semantics.
- Tool failures are appended to the conversation and the loop continues; they do not signal an agent failure.
- A model response that stops at the generation limit (the API's truncation signal) is not treated as a final answer; the loop appends the continuation prompt and continues with a follow-up request.
- A truncated response whose content is a single character repeated (a degenerate response) signals failure; the loop does not resume generation.
- Tool calls present in a truncated response are never executed.
- If a termination reminder generator is configured, the reminder is injected at most once per run per the interface contract.
- Token usage is extracted from each API response and included in logger events.

### Ordering

- Logger callbacks are invoked after data is appended to history.

### State Management

- No persistence or caching; conversation history is provided in the result and not retained.

### External Dependencies

- OpenAI API (external language model service).

### Error Handling

- API errors, malformed responses, tool-executor exceptions, or exceeded iteration limits halt the run and signal failure per the interface contract.
- A truncated response does not halt the run; generation resumes via the continuation prompt.
- A degenerate truncated response halts the run and signals failure; the loop does not resume.

### Refined terms

- continuation prompt -> the fixed default continuation prompt message, appended as a user message when a continuation prompt is not configured; the text is pinned in the implementation LLS

## Non-concerns

- Retry behavior: whether failed API calls are retried is unspecified; any failure signals the run's failure.
