# agent_runner_impl implementation component

imports: tool_provider, agent_conversation_history, agent_loop_guard, runner_logger, openai_ext, model_config
implements: agent_runner

## Purpose

The agent_runner_impl implementation component realizes language model completion requests, tool execution dispatch, output continuation, and termination handling for agent turns.

Executing robust model loops requires managing protocol-level token limits, handling tool failures gracefully, and binding runtime parameters to API completion endpoints. The agent_runner_impl implementation component constructs completion requests using model parameters from model config, dispatches model-invoked tool executions through the tool manager, injects recovery guidance on failures, and resumes truncated completions.

**Out of scope:** The agent_runner_impl implementation component does not parse tool argument schemas, format disk transcripts, or discover build target manifests; these are handled by other components.

## Types and Behavior

The agent runner coordinates interaction turns using the session conversation history, the tool manager from the tool provider, the loop guard from agent loop guard, the model config from model_config, and the runner logger.

When driving a turn, the agent runner transmits a completion request using the model name, base url, api key, and timeout from model config with openai_ext. When a model response is truncated at the generation limit, the agent runner resumes generation with a continuation turn.

The agent runner logs log events for turn requests, completions, and tool results to the runner logger.

When tool execution in the tool manager produces a response indicating failure without terminating the run, the agent runner appends the failure feedback to the conversation history and continues the turn loop. When tool execution produces a response indicating that the session should terminate, the agent runner concludes the run and returns an agent outcome.

When interaction turns reach the conversation limit from model config, the agent runner concludes the run with a failure outcome.
