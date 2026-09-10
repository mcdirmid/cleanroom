# agent_runner interface component

imports: tool_provider, agent_conversation_history, agent_loop_guard, runner_logger, model_config

## Purpose

The agent_runner interface component orchestrates iterative model-tool interaction turns, managing conversation flow and guarding against runaway repetition.

Autonomous agent tasks require multi-turn interaction loops where model decisions trigger tool executions. The agent_runner interface component coordinates this turn lifecycle: sending formatted model requests from conversation history, dispatching tool calls to the tool manager, evaluating loop guards, and recording audit events until an explicit termination outcome concludes the run.

**Out of scope:** The agent_runner interface component does not serialize network wire protocols, define domain tools, or persist node graphs; these are handled by other components.

## Types and Behavior

An *agent outcome* is the final result of an agent run that carries a *termination outcome* from tool execution in a tool provider and the final state of the conversation history from agent conversation history.

The *agent runner* is an agent session service that coordinates the turn loop for an agent session. The agent runner:

- Drives turns by sending a model request to a language model and executing requested tools in the tool manager.

- Appends model responses and correlates tool execution responses with originating tool call identifiers in the conversation history.

- Can dispatch follow-up tool calls specified by tool responses through the tool manager, appending an antecedent synthetic assistant tool invocation message and the follow-up tool response to the conversation history immediately following the originating response.

- Records log events for model requests, assistant responses, and tool executions to the runner logger, providing event summaries that convey turn progress, tool calls with arguments or non-tool response text, and tool execution outcomes.

- Evaluates tool executions with the loop guard, injecting loop reminders from agent loop guard into the conversation or terminating with a loop failure on runaway repetition.

- Injects a tool reminder into the conversation history when a model response contains no tool executions, prompting that session progress and conclusion require executing tools, and continues the turn loop.

- Concludes atomically and produces an agent outcome when tool execution produces a termination outcome.

- Concludes with a failure outcome if the conversation limit is exceeded.
