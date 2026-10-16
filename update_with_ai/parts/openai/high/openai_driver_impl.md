<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T12:07:00Z
CHANGE: Rebuild completion tools payload on each turn from currently installed tools
CODE_HASH: bde0fa1dd656
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# openai_driver_impl implementation component

imports: agent_config, json_ext, loop_conversation, loop_guard, openai_config, openai_ext, runner_logger, tool_provider
implements: loop_driver

## Purpose

The openai_driver_impl implementation component realizes language model completion requests, tool execution dispatch, output continuation, and termination handling for agent turns.

Executing robust model loops requires managing protocol-level token limits, handling tool failures gracefully, and binding runtime parameters to API completion endpoints. The openai_driver_impl implementation component constructs completion requests using configuration parameters from openai config and agent config, dispatches model-invoked tool executions through the tool manager, injects recovery guidance on failures, and resumes truncated completions.

**Out of scope:** The openai_driver_impl implementation component does not parse tool argument schemas, format disk transcripts, or discover build target manifests; these are handled by other components.

**Delegated:** HTTP transport and endpoint communication are delegated to openai_ext; JSON argument repair is delegated to json_ext; turn logging is delegated to runner_logger; repetition detection is delegated to loop_guard; message formatting is delegated to loop_conversation; tool definition schemas and dispatch are delegated to tool_provider; runtime configuration is delegated to openai_config and agent_config.

## Types and Behavior

The loop driver coordinates interaction turns using the session conversation, installed tools, the loop guard, the openai config, the agent config, and the runner logger.

When driving each turn, the loop driver constructs the tools payload from currently installed tools, ordering tools deterministically by tool name with parameters ordered deterministically by parameter sequence, and transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from the openai config. Tool results are correlated with model invocations according to OpenAI tool calling conventions.

When a model response is truncated at the generation limit, the loop driver recovers truncated tool invocations by repairing unclosed arguments into valid JSON.

When repairing a truncated invocation:

- A replace file content invocation providing a target file, target content, and partial replacement content deletes any trailing incomplete line without a terminating newline, replacing it with a sentinel that raises a non implemented error carrying an incrementing session truncation identifier matching the indentation of the deleted line, or appends the sentinel on the next line matching the last line's indentation when the last line is complete. The loop driver then executes the tool to persist the partial modifications and returns an actionable notice directing the model to resume implementation targeting the sentinel.

- Any other tool invocation terminates by appending a tool failure response carrying the suppression key of the tool, then resuming generation with a continuation turn.

When a model completion response fails with an incomplete tool call error, the loop driver appends an actionable recovery notice directing smaller edits and continues the turn loop, halting with an unexpected failure when consecutive truncation failures repeat.

The loop driver logs an event to the runner logger for every turn request, completion, and tool result. Each event carries a compact summary containing the turn identifier, the conversation token size rounded to the nearest thousand tokens, the percentage of tokens cached on the last turn from the model response usage fields, the tool call names and arguments or text response previews, and the tool execution status naming the file read or written with its timestamp without inlining file content. Corrective reminders appear in the transcript when present.

Evaluating a tool invocation with the loop guard:

- Halts execution with an unexpected failure carrying the loop failure explanation when the loop guard produces a loop failure.

- Appends the reminder to the conversation and proceeds with execution when the loop guard produces a loop reminder.

A productive tool execution that modifies a workspace file or advances a guide step clears repetition tracking in the loop guard.

When tool execution produces a response indicating failure without terminating the run, the loop driver appends the failure feedback to the conversation and continues the turn loop. When tool execution produces a response indicating terminating failure, the loop driver halts execution with an unexpected failure carrying the failure explanation. When tool execution produces a response indicating successful session termination, the loop driver concludes the run and returns a successful loop outcome.

When agent configuration requests follow-up injection, a tool response specifying a follow-up tool call prompts execution of that tool, appending a synthetic assistant invocation that carries the reasoning text of the follow-up tool call as preceding thought, followed by the resulting follow-up response immediately after the originating response.

When a model response produces no tool executions, the loop driver appends a prompt to the conversation reminding that progress and conclusion require invoking tools, and continues the turn loop.

When interaction turns reach the conversation limit from the agent configuration, the loop driver halts execution with an unexpected failure indicating that the conversation limit was reached.
