# agent_node_clean_logic_asm

fulfills: dag_clean_logic
imports: agent_node_clean_logic_impl (clean logic), agent_loop_asm (agent loop), build_agent_config_impl (agent configuration loading), sandbox_asm (sandbox assembly), agent_node_tool_executor_impl (tool execution)
terms (from build_agent_config): agent configuration, config target, API key

## Deltas

- Assembles the concrete agent clean logic: resolves the agent configuration from the config target, loads the API key from the environment, creates the agent loop, and wires the sandbox factory (applying the configuration's sandbox gates to each sandbox via sandbox_asm) into the agent_node_clean_logic_impl component.
- [boundary] The concrete implementations for agent execution are selected here.
- [external] The concrete component implementations, the language model service, and the generated module of the selected agent_config target (config target).
- [failure] Configuration failures — a missing generated module or a missing API key — are signaled by the build_agent_config component as exceptions.

## Non-concerns

- Consumption: how the assembled clean logic is used is unspecified here.
- Selection policy: the concrete implementations wired here are a default assembly; other selections may differ.
- Testability: this assembly is never tested; it performs no functionality beyond configuration and assembly of other modules.
