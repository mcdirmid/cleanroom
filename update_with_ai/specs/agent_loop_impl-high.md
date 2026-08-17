# agent_loop_impl

fulfills: agent_loop
imports: tool_provider (tool results, signals)
terms (from agent_loop): run, termination value, conversation
terms (from tool_provider): tool failure

## Deltas beyond the agent_loop contract

### Behavior

- Uses the OpenAI API for language model processing.
- Maintains conversation history for the duration of a run; sends conversation and tool definitions to the OpenAI API; appends responses; delegates tool execution to the provided logic; continues until completion, termination, or failure.
- Deduplication behavior follows the tool_provider semantics.
- Tool failures are appended to the conversation and the loop continues; they do not signal an agent failure.
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

## Non-concerns

- Retry behavior: whether failed API calls are retried is unspecified; any failure signals the run's failure.
