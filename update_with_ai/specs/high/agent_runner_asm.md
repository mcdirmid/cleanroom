# agent_runner_asm

imports: agent_runner, loop_guard, runner_logger, openai_ext
types from agent_runner: agent runner
types from loop_guard: loop guard
types from runner_logger: runner logger
types from openai_ext: model name
implements: agent runner

## Behavior

- An *agent runner* is assembled from concrete implementations of *loop guard*, *runner logger*, and *agent runner*.
- The *agent runner* assembly configures external completion services with endpoint URLs, timeouts, and authentication credentials.
- The *agent runner* initializes repetition guarding and execution logging per execution.
