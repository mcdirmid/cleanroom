# build_asm

imports: build_runner_impl (the interface-only runner), build_graph_storage_impl (file-backed graph and message store), build_agent_config_impl (agent configuration loading), agent_loop_impl (agent loop), agent_node_clean_logic_impl (agent clean logic), sandbox_impl (sandbox), dag_cleaner_impl (topological cleaning)
terms (from build_agent_config): agent configuration, config target, API key

## Deltas

- Provides a configured build runner: assembles the concrete implementations of the cleanroom components into the interface-only runner implementation.
- The graph factory supplies the file-backed graph and message store.
- The clean-logic factory supplies the agent clean logic: the agent loop, the sandbox, and the agent configuration loading, applying the configuration's sandbox gates to each sandbox it constructs; the factory resolves the configuration from the config target and loads the API key from the environment.
- The DAG factory supplies the topological cleaner over the graph and the clean logic.
- The assembled runner's operations create the components per call through the supplied factories.
- [boundary] The concrete implementations are selected here; the runner's operations never select components.
- [external] The concrete component implementations, the language model service, and the generated module of the selected agent_config target (config target).
- [failure] Configuration failures — a missing generated module or a missing API key — are signaled by the build_agent_config component as exceptions.

## Non-concerns

- Consumption of the assembled runner (entry points, generated wrappers): unspecified here.
- Selection policy: the concrete implementations wired here are a default assembly; other selections may differ.
- Testability: this assembly is never tested; it performs no functionality beyond configuration and assembly of other modules.
