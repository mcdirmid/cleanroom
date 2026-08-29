# agent_loop

imports: tool_provider (tool definitions, results, signals)
terms (from tool_provider): tool definition, tool result, supersession flag, stub, signal, termination result, tool failure
terms (owned): run, termination value, conversation, conversation message, system prompt, truncated response, continuation prompt, degenerate response

## Purpose

Answers a user prompt through an iterative process of LLM processing and tool execution, guarding against wasted cycles and runaway repetition. Tool execution may provide a result that continues the loop, a tool failure that guides the agent, or a termination signal whose value passes through unchanged.

## Terms

- Run: a single agent execution session.
- Termination value: the opaque value of a successful termination signal. It enters via tool execution and exits via the run result unchanged; the component does not inspect, transform, or interpret it.
- Conversation: the chronological history of conversation messages maintained for a run and provided with the run result.
- Conversation message: an entry in the conversation history, produced by the model or by tool execution.
- System prompt: the static opening section of the conversation context, supplied per run; it is never modified during the run.
- Truncated response: a model response that stops because the generation limit was reached, before completing naturally; it is not a complete answer.
- Continuation prompt: the message appended to the conversation so that generation resumes from where a truncated response stopped.
- Degenerate response: a truncated response whose content is a single character repeated; it carries no meaningful content and is not resumed.

## Contract

**Inputs**

- Per run: a system prompt, a user prompt, tool definitions and tool execution logic, as defined by tool_provider; optional session-start tool results (rendered at the beginning of the run, before the model's first turn); an optional logger callback.

**Operations**

- Request an agent run.

**Guarantees**

- Provides a termination signal with its carried value, or a failure result, each with the full conversation history; there is no free-text final answer.
- Signals failure, leaving state unchanged, when the run fails, the language model service fails, the response is malformed, tool execution raises an exception, or a truncated response is degenerate.
- Signals failure, leaving state unchanged, when the run exceeds the maximum number of loop iterations.
- The termination reminder is not triggered by tool failures.
- A loop reminder is provided at most once per run when the model repeats itself without progress.
- Signals failure, leaving state unchanged, when repetition continues beyond the run's repetition limit.
- The advance tool is exempt from repetition tracking.
- A termination reminder is provided when the model stops without signaling termination, and the loop continues; the run completes only via a termination signal or the iteration limit.
- A truncated response is not treated as a complete answer.
- When a response is truncated and is not degenerate, generation resumes with a follow-up request.
- Tool calls present in a truncated response are not executed.
- Final termination is atomic: once a termination signal occurs, no further API calls or tool executions occur.
- Each run is independent; no state persists.
- Delegates tool execution to the provided logic.
- If a logger callback is provided: invokes it chronologically for the events in the Events block; includes session token usage (input tokens, cached input tokens, output tokens, total tokens) and timing (duration in seconds) in session termination events; catches and ignores logger callback exceptions.

**Assumptions**

- The language model supports chat completion with tool calling.
- The tool execution logic handles all tools defined in the request and produces results in the tool_provider format.
- The tool execution logic produces results that supersede at most one earlier result.

**Events**

| Event | When | Data fields |
|---|---|---|
| message added | message appended | message |
| message stubbed | tool result stubbed | stubbed message, replacement message |
| tool called | model requests tools | tool calls |
| tool result | tool results received | results, in tool_provider format |
| API response | API response received | none |
| response truncated | model response stops at the generation limit | message |
| reminder injected | reminder injected | message |
| run terminated | termination signaled | termination value, usage, cumulative usage, final context size |
| error | failure occurs | error, usage (if any), cumulative usage (if any), last context size (if any) |

## Non-concerns

- Timer implementation: the exact timeout mechanism is unspecified.
- Model API version: the specific API version is unspecified.
- Stub text: the exact text of a stub placeholder is unspecified.
