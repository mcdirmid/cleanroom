# agent_driver interface component

imports: agent_config, agent_conversation, agent_loop_guard, runner_logger, tool_provider

## Purpose

The agent_driver interface component orchestrates iterative model-tool interaction turns, managing conversation flow and guarding against runaway repetition.

Autonomous agent tasks require multi-turn interaction loops where model decisions trigger tool executions. The agent_driver interface component coordinates this turn lifecycle: sending formatted model requests from conversation, dispatching tool calls to the tool manager, evaluating loop guards, and recording audit events until an explicit termination outcome concludes the run.

**Out of scope:** The agent_driver interface component does not serialize network wire protocols, define domain tools, or persist node graphs; these are handled by other components.

## Types and Behavior

An *agent outcome* is the final result of an agent run that carries a termination outcome from tool execution and the final state of the conversation.

The *agent driver* is an agent session service that coordinates the turn loop for an agent session.

The agent driver:

- Can *run* to drive turns by sending a model request to a language model and executing requested tools.

- Appends model responses and correlates tool execution responses with originating tool call identifiers in the conversation.

- Can dispatch follow-up tool calls specified by tool responses, recording the follow-up execution in the conversation.

- Records log events for interaction turns, tool executions, and turn outcomes to the runner logger.

- Evaluates tool executions with the loop guard, injecting loop reminders into the conversation or halting with an unexpected failure on runaway repetition.

- Injects a tool reminder into the conversation when a model response contains no tool executions, prompting that session progress and conclusion require executing tools, and continues the turn loop.

- Concludes atomically and produces an agent outcome when tool execution produces a termination outcome, or halts with an unexpected failure if the termination indicates a failing outcome.

- Halts with an unexpected failure if the conversation limit is exceeded.
