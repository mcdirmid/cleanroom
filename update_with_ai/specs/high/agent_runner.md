# agent_runner

imports: tool_provider, conversation_history, loop_guard, runner_logger
types from tool_provider: tool, tool provider, tool result, tool failure, termination outcome
types from conversation_history: conversation history, message, model request
types from loop_guard: loop guard, loop reminder, loop failure
types from runner_logger: runner logger, log event

## Purpose

Orchestrates iterative model-tool interaction turns, managing conversation flow and guarding against runaway repetition.

Autonomous agent tasks require multi-turn interaction loops where model decisions trigger tool executions. Agent runner coordinates this turn lifecycle: sending formatted model requests, dispatching tool calls, recording history, and evaluating repetition guards until an explicit termination outcome concludes the run.

## Types

- An *agent runner* is an orchestration service that drives an iterative agent run
- An *iteration limit* is a bound on the maximum number of model interaction turns permitted in a run
- An *agent outcome* is the final result of an agent run, carrying the *termination outcome* and the *conversation history*

## Behavior

- An *agent runner* drives turns by sending a *model request* to a language model and executing requested *tools*.
- An *agent runner* appends model responses and correlates *tool results* with originating tool call identifiers in a *conversation history*.
- An *agent runner* emits execution progress events for model turns and tool invocations.
- An *agent runner* records *log events* for model requests, assistant responses, and tool executions to a *runner logger*.
- An *agent runner* evaluates tool executions with a *loop guard*, injecting *loop reminders* or terminating with a *loop failure* on runaway repetition.
- When an execution produces a *termination outcome*, the *agent runner* concludes atomically and produces an *agent outcome*.
- An *agent runner* concludes with a failure outcome if the *iteration limit* is exceeded.
