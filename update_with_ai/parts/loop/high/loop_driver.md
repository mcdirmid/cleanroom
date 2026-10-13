<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Remove the runner logger dependency from the interface scope and state turn handling declaratively
CODE_HASH: e571710fc38b
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# loop_driver interface component

imports: agent_session, loop_conversation, tool_provider

## Purpose

The loop_driver interface component orchestrates iterative model-tool interaction turns, managing conversation flow and guarding against runaway repetition.

Autonomous agent tasks require multi-turn interaction loops where model decisions trigger tool executions. The loop_driver interface component coordinates this turn lifecycle: sending formatted model requests from conversation, dispatching tool calls to the tool manager, and evaluating loop guards until an explicit termination outcome concludes the run.

**Out of scope:** The loop_driver interface component does not serialize network wire protocols, define domain tools, or persist node graphs; these are handled by other components.

**Delegated:** Model request conversation state is delegated to loop_conversation; tool dispatching and tool responses are delegated to tool_provider; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *loop outcome* is the final result of an agent run that carries a termination outcome from tool execution and the final state of the conversation.

An agent session's *loop driver* coordinates the turn loop for an agent session.

The loop driver can *run* to drive turns by sending a model request to a language model and executing the requested tools.

The loop driver appends model responses to the conversation and correlates tool execution responses with their originating tool call identifiers. The loop driver can also dispatch follow-up tool calls that tool responses specify, recording each follow-up execution in the conversation.

The loop driver evaluates tool executions with the loop guard, injecting loop reminders into the conversation or halting with an unexpected failure on runaway repetition. When a model response contains no tool executions, the loop driver injects a tool reminder into the conversation stating that session progress and conclusion require executing tools, and continues the turn loop.

The loop driver concludes atomically and produces a loop outcome when tool execution produces a termination outcome, and halts with an unexpected failure when that termination indicates a failing outcome or when the conversation limit is exceeded.
