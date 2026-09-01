# agent_node_cleaner_asm

imports: agent_node_cleaner, agent_runner, sandbox, conversation_history, build_agent_config, build_graph_storage, runner_logger
types from agent_node_cleaner: agent node cleaner
types from agent_runner: agent runner
types from sandbox: sandbox factory
types from conversation_history: conversation history factory
types from build_agent_config: build agent config resolver, config target, agent configuration
types from build_graph_storage: build graph storage, node definition
types from runner_logger: runner logger
implements: agent node cleaner

## Behavior

- An *agent node cleaner* is assembled from concrete implementations of *agent runner*, *sandbox factory*, *conversation history factory*, *build agent config resolver*, *build graph storage*, and an optional *runner logger*.
- The assembled cleaner retrieves the *config target* from the target *node definition*, resolves its *agent configuration* using the *build agent config resolver*, forwards endpoint and model settings to the *agent runner*, and coordinates node cleaning.
