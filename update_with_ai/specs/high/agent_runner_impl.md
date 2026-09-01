# agent_runner_impl

imports: tool_provider, conversation_history, loop_guard, runner_logger, agent_runner, openai_ext
types from tool_provider: tool, tool provider, tool result, tool failure, termination outcome
types from conversation_history: conversation history, message, model request
types from loop_guard: loop guard, loop reminder, loop failure
types from runner_logger: runner logger, log event
types from agent_runner: agent runner, iteration limit, agent outcome
types from openai_ext: completion request, completion response, model name
implements: agent runner

## Behavior

- An *agent runner* accepts an initialized *conversation history* and a *tool provider* to drive interaction turns.
- An *agent runner* transmits *completion requests* using a *model name* to drive interaction turns.
- An *agent runner* logs *log events* for turn requests, completions, and tool results to a *runner logger*.
- When tool execution produces a *tool failure*, the *agent runner* appends the failure feedback to the *conversation history* and continues the run.
- When a model response is truncated at the generation limit, the *agent runner* resumes generation with a continuation turn.
