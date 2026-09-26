# openai_driver_impl implementation component

imports: agent_config, loop_conversation, loop_driver, loop_guard, openai_config, openai_ext, runner_logger, tool_provider
implements: loop_driver

## Assumptions and Requirements

### Requirements

1. When driving a turn, the loop driver transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from openai config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter sequence, and correlates tool results with model invocations according to OpenAI tool calling conventions.
2. When a model response is truncated at the generation limit, the loop driver recovers truncated tool invocations by repairing unclosed arguments into valid JSON: when a replace file content invocation provides a target file, target content, and partial replacement content, any trailing incomplete line without a terminating newline is deleted and replaced with a raise NotImplementedError sentinel carrying an incrementing session truncation identifier matching the indentation of the deleted line, or if the last line is complete the sentinel is appended on the next line matching the last line's indentation, executing the tool to persist partial modifications and returning an actionable notice directing the model to resume implementation targeting the sentinel; otherwise the loop driver terminates the truncated tool invocation by appending a tool failure response with the tool's suppression key, and resumes generation with a continuation turn.
3. The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
4. Evaluating a tool invocation with the loop guard records the tool execution in the loop guard, injecting a loop reminder into the conversation when a reminder is produced, or concluding the run with an unexpected failure when a loop failure is produced.
5. Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard.
6. When tool execution produces a non-terminating failure response, the failure feedback is appended to the conversation and the run continues.
7. When configured by agent configuration to inject followups, a tool response specifying a follow-up tool call prompts execution of the designated tool, appending a synthetic assistant invocation carrying the follow-up tool call's reasoning text as prior thought preceding the requested tool execution and the resulting follow-up response to the conversation immediately following the originating response.
8. When a model response produces no tool executions, the loop driver appends a prompt to the conversation reminding that progress and conclusion require invoking tools, and continues the turn loop.
9. When tool execution produces a terminating response, the loop driver concludes the run and returns a loop outcome, or halts with an unexpected failure if the response indicates terminating failure.
10. When turns reach the conversation limit from agent config, the loop driver halts with an unexpected failure.

## Grounding Facts

### Knowledge Needed

- Model and network options from `openai_config`.
- Conversation limit and followup injection flags from `agent_config`.
- Tool definitions and parameter order from `tool_provider`.
- Repetition tracking and loop state from `loop_guard`.

### Actions Needed

- Transmit completion request via `openai_ext`.
- Repair truncated tool calls and handle generation limits.
- Log events to `runner_logger`.
- Evaluate tool executions with `loop_guard`.
- Dispatch tool calls and inject follow-up turns.
- Conclude run with loop outcome or signal unexpected failure.
