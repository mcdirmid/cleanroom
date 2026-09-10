# agent_runner_impl implementation component

imports: tool_provider, agent_conversation_history, agent_loop_guard, runner_logger, openai_ext, model_config
implements: agent_runner

## Purpose

The agent_runner_impl implementation component realizes language model completion requests, tool execution dispatch, output continuation, and termination handling for agent turns.

Executing robust model loops requires managing protocol-level token limits, handling tool failures gracefully, and binding runtime parameters to API completion endpoints. The agent_runner_impl implementation component constructs completion requests using model parameters from model config, dispatches model-invoked tool executions through the tool manager, injects recovery guidance on failures, and resumes truncated completions.

**Out of scope:** The agent_runner_impl implementation component does not parse tool argument schemas, format disk transcripts, or discover build target manifests; these are handled by other components.

## Types and Behavior

The agent runner coordinates interaction turns using the session conversation history, the tool manager, the loop guard, the model config, and the runner logger.

When driving a turn, the agent runner transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions. When a model response is truncated at the generation limit, the agent runner resumes generation with a continuation turn.

The agent runner logs log events for turn requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool call names and arguments or text response previews, and tool execution status and diagnostic outcomes including corrective reminders in the transcript when present.

Before each tool execution in the tool manager, the agent runner evaluates the tool invocation with the loop guard. If the loop guard produces a loop failure, the agent runner concludes the run with a failure outcome. If the loop guard produces a loop reminder, the agent runner appends the reminder to the conversation history and proceeds with execution. Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard.

When tool execution in the tool manager produces a response indicating failure without terminating the run, the agent runner appends the failure feedback to the conversation history and continues the turn loop. When tool execution produces a response indicating that the session should terminate, the agent runner concludes the run and returns an agent outcome.
 
When a model response produces no tool executions, the agent runner appends a prompt to the conversation history reminding that progress and conclusion require invoking tools, and continues the turn loop.
 
When interaction turns reach the conversation limit from model config, the agent runner concludes the run with a failure outcome.
