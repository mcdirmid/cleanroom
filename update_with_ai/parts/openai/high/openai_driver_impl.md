# openai_driver_impl implementation component

imports: agent_config, loop_conversation, loop_guard, openai_config, openai_ext, runner_logger, tool_provider
implements: loop_driver

## Purpose

The openai_driver_impl implementation component realizes language model completion requests, tool execution dispatch, output continuation, and termination handling for agent turns.

Executing robust model loops requires managing protocol-level token limits, handling tool failures gracefully, and binding runtime parameters to API completion endpoints. The openai_driver_impl implementation component constructs completion requests using configuration parameters from openai config and agent config, dispatches model-invoked tool executions through the tool manager, injects recovery guidance on failures, and resumes truncated completions.

**Out of scope:** The openai_driver_impl implementation component does not parse tool argument schemas, format disk transcripts, or discover build target manifests; these are handled by other components.

## Types and Behavior

The loop driver coordinates interaction turns using the session conversation, installed tools, the loop guard, the openai config, the agent config, and the runner logger.

When driving a turn, the loop driver transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from the openai config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter sequence, and correlates tool results with model invocations according to OpenAI tool calling conventions. When a model response is truncated at the generation limit, the loop driver terminates any truncated tool invocation by repairing unclosed arguments into valid JSON and appending a tool failure response with the tool's suppression key, and resumes generation with a continuation turn.

The loop driver logs log events for turn requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool call names and arguments or text response previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in the transcript when present.

Before each tool execution, the loop driver evaluates the tool invocation with the loop guard. Evaluating a tool invocation:

- Halts execution with an unexpected failure carrying the loop failure explanation if the loop guard produces a loop failure.

- Appends the reminder to the conversation and proceeds with execution if the loop guard produces a loop reminder.

Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard.

When tool execution produces a response indicating failure without terminating the run, the loop driver appends the failure feedback to the conversation and continues the turn loop. When tool execution produces a response indicating terminating failure, the loop driver halts execution with an unexpected failure carrying the failure explanation. When tool execution produces a response indicating successful session termination, the loop driver concludes the run and returns a successful loop outcome.

When configured by agent configuration to inject followups, a tool response specifying a follow-up tool call prompts execution of the designated tool, appending a synthetic assistant invocation carrying the follow-up tool call's reasoning text as prior thought preceding the requested tool execution and the resulting follow-up response to the conversation immediately following the originating response.

When a model response produces no tool executions, the loop driver appends a prompt to the conversation reminding that progress and conclusion require invoking tools, and continues the turn loop.

When interaction turns reach the conversation limit from the agent configuration, the loop driver halts execution with an unexpected failure indicating that the conversation limit was reached.
