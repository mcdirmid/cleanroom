# agent_loop

imports: tool_provider (tool definitions, results, signals)
terms (from tool_provider): tool definition, tool result, content ID, stub, signal, termination result, tool failure
terms (owned): run, termination value, conversation, conversation message, truncated response, continuation prompt, degenerate response

## Purpose

Answers a user prompt through an iterative process of LLM processing and tool execution. Tool execution may provide a result that continues the loop, a tool failure that guides the agent, or a termination signal whose value passes through unchanged.

## Owned definitions

- Run: a single agent execution session.
- Termination value: the opaque value of a successful termination signal. It enters via tool execution and exits via the run result unchanged; the component does not inspect, transform, or interpret it.
- Conversation: the chronological history of conversation messages maintained for a run and provided with the run result.
- Conversation message: an entry in the conversation history, produced by the model or by tool execution.
- Truncated response: a model response that stops because the generation limit was reached, before completing naturally; it is not a complete answer.
- Continuation prompt: the message appended to the conversation so that generation resumes from where a truncated response stopped.
- Degenerate response: a truncated response whose content is a single character repeated; it carries no meaningful content and is not resumed.

## Observable dataflow

- Inputs per run: a user prompt, tool definitions, and tool execution logic (per tool_provider).
- Outputs: a final answer, a termination signal with its carried value, or a failure result — each paired with the full conversation history.
- The agent loop handles detection of free-text responses: a model response that requests no tools provides a final answer (free-text responses end the run without a termination signal).
- Termination is observable dataflow: the signal produced by tool execution exits via the run result, paired with the conversation history.
- The component delegates tool execution to the provided logic; it does not execute tools.
- Tool failures (per tool_provider) are appended to the conversation and the loop continues; no session reset, no history clearing.
- Internal bookkeeping (content IDs, stubbing flags) is not sent to the language model service.
- A truncated response is not a final answer: the component appends the continuation prompt and resumes generation with a follow-up request.
- A degenerate response is not resumed: the run exits with a failure result.
- Tool calls present in a truncated response do not reach tool execution.

## Contract

**The client configures the component with:**

- Connection and processing parameters for the language model service.
- An optional maximum number of loop iterations; if exceeded, the run signals failure.
- An optional termination reminder generator; the reminder is injected at most once per run, and is not triggered by tool failures.
- An optional continuation prompt; when the model response is truncated, the component resumes generation by appending the continuation prompt; a default continuation prompt is used when omitted.
- Defaults when omitted: an iteration limit of ten, a sampling temperature of 0.0, a request timeout of 60 seconds, and a default continuation prompt.

**For each run, the client provides:**

- A user prompt.
- Tool definitions and tool execution logic, as defined by tool_provider.
- An optional logger callback.

**The client may:**

- Request an agent run.

**The component guarantees:**

- Provides a final answer, a termination signal with its carried value, or a failure result, each with the full conversation history.
- Signals failure, leaving state unchanged, when the run fails, the language model service fails, the response is malformed, tool execution raises an exception, or a truncated response is degenerate.
- Signals failure, leaving state unchanged, when the run exceeds the configured maximum number of loop iterations.
- Maintains chronological conversation order and processes tool results per tool_provider semantics, rendering each tool result's note into the model-visible message.
- Appends tool failures to the conversation and continues the loop.
- Injects the termination reminder at most once per run when the generator is configured.
- A truncated response is not treated as a complete answer.
- When a response is truncated and is not degenerate, the component appends the continuation prompt and resumes generation with a follow-up request.
- Tool calls present in a truncated response are not executed.
- Final termination is atomic: once a termination signal occurs, no further API calls or tool executions occur.
- Each run is independent; no state persists.
- Delegates tool execution to the provided logic.
- If a logger callback is provided: invokes it chronologically for the events in the Logger Event Summary; includes per-request and cumulative token usage in applicable events; catches and ignores logger callback exceptions.

**The component assumes:**

- The language model supports chat completion with tool calling.
- The tool execution logic handles all tools defined in the request and produces results in the tool_provider format.
- The termination reminder generator, if provided, produces conversation messages in the same format as other conversation messages.

## Logger Event Summary

| Event | When | Data fields |
|---|---|---|
| message added | message appended | message |
| message stubbed | tool result stubbed | content ID, stubbed message, replacement message |
| tool called | model requests tools | tool calls |
| tool result | tool results received | results, in tool_provider format |
| API response | API response received | usage (prompt, completion, total tokens) |
| response truncated | model response stops at the generation limit | message, usage |
| reminder injected | reminder injected | message |
| final answer | final answer produced | answer, usage, cumulative usage, final context size |
| run terminated | termination signaled | termination value, usage, cumulative usage, final context size |
| error | failure occurs | error, usage (if any), cumulative usage (if any), last context size (if any) |

## Non-concerns

- Timer implementation: the exact timeout mechanism is unspecified.
- Model API version: the specific API version is unspecified; the implementation determines it.
