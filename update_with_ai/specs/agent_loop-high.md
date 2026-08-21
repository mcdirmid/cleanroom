# agent_loop

imports: tool_provider (tool definitions, results, signals)
terms (from tool_provider): tool definition, tool result, supersession flag, stub, signal, termination result, tool failure
terms (owned): run, termination value, conversation, conversation message, system prompt, truncated response, continuation prompt, degenerate response

## Purpose

Answers a user prompt through an iterative process of LLM processing and tool execution. Tool execution may provide a result that continues the loop, a tool failure that guides the agent, or a termination signal whose value passes through unchanged.

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

- Configured: connection and processing parameters for the language model service; an optional maximum number of loop iterations (default ten); an optional termination reminder generator (the message source for the termination reminder; a default message is used when not configured); an optional continuation prompt (a default is used when omitted); a default sampling temperature of 0.0 and a default request timeout of 60 seconds.
- Per run: a system prompt, a user prompt, tool definitions and tool execution logic, as defined by tool_provider; an optional logger callback.

**Operations**

- Request an agent run.

**Guarantees**

- Provides a termination signal with its carried value, or a failure result, each with the full conversation history; there is no free-text final answer.
- Signals failure, leaving state unchanged, when the run fails, the language model service fails, the response is malformed, tool execution raises an exception, or a truncated response is degenerate.
- Signals failure, leaving state unchanged, when the run exceeds the configured maximum number of loop iterations.
- Maintains chronological conversation order and processes tool results per tool_provider semantics, rendering each tool result's note into the model-visible message.
- The conversation is append-only except for stubbing; never modifies the system prompt; rewrites prior conversation messages only by stubbing, per tool_provider semantics.
- Stubs the earlier result for the same file or tool command when a result's supersession flag is set.
- Appends tool failures to the conversation and continues the loop; no session reset, no history clearing.
- The termination reminder is not triggered by tool failures.
- Injects a loop reminder at most once per run when the model repeats itself without progress: the same tool call (name and arguments) repeated 4 consecutive times, or replace_lines targeting the same file and line range 4 consecutive times (even with different content) — urging the agent to make progress (re-read the file or finish the run).
- Signals failure, leaving state unchanged, when the same tool call (name and arguments) repeats 8 consecutive times, or when replace_lines targets the same file and line range 8 consecutive times (even with different content) — the run ends instead of spinning to the iteration limit.
- Injects the termination reminder whenever the model stops with free text without signaling termination (the generator's message, or a default), and continues the loop; the run completes only via a termination signal or the iteration limit.
- A truncated response is not treated as a complete answer.
- When a response is truncated and is not degenerate, the component appends the continuation prompt and resumes generation with a follow-up request.
- Tool calls present in a truncated response are not executed.
- Final termination is atomic: once a termination signal occurs, no further API calls or tool executions occur.
- Internal bookkeeping (supersession flags) is not sent to the language model service.
- Stubbing preserves the conversation prefix: a stubbed result keeps its position and its stub is fixed once set, so the conversation up to the most recent live result is identical from one request to the next except for appended messages.
- Each run is independent; no state persists.
- Delegates tool execution to the provided logic.
- If a logger callback is provided: invokes it chronologically for the events in the Events block; includes per-request and cumulative token usage in applicable events; catches and ignores logger callback exceptions.

**Assumptions**

- The language model supports chat completion with tool calling.
- The tool execution logic handles all tools defined in the request and produces results in the tool_provider format.
- The tool execution logic produces results that supersede at most one earlier result.
- The termination reminder generator, if provided, produces conversation messages in the same format as other conversation messages.

**Events**

| Event | When | Data fields |
|---|---|---|
| message added | message appended | message |
| message stubbed | tool result stubbed | stubbed message, replacement message |
| tool called | model requests tools | tool calls |
| tool result | tool results received | results, in tool_provider format |
| API response | API response received | usage (prompt, completion, total tokens) |
| response truncated | model response stops at the generation limit | message, usage |
| reminder injected | reminder injected | message |
| run terminated | termination signaled | termination value, usage, cumulative usage, final context size |
| error | failure occurs | error, usage (if any), cumulative usage (if any), last context size (if any) |

## Non-concerns

- Timer implementation: the exact timeout mechanism is unspecified.
- Model API version: the specific API version is unspecified; the implementation determines it.
- Stub text: the exact text of a stub placeholder is pinned in the implementation spec.
