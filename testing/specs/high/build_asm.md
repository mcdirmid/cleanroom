# build_asm

fulfills: build_runner
imports: build_runner_impl (the interface-only runner), build_graph_storage_impl (file-backed graph and message store), agent_node_clean_logic_asm (agent clean logic assembly), dag_cleaner_asm (DAG cleaner assembly)

## Deltas

- Provides a configured build runner: assembles the concrete implementations and sub-assemblies of the cleanroom components into the interface-only runner implementation.
- The graph factory supplies the file-backed graph and message store.
- The clean-logic factory supplies the agent clean logic through the agent_node_clean_logic_asm sub-assembly.
- The DAG factory supplies the topological cleaner through the dag_cleaner_asm sub-assembly.
- The assembled runner's operations create the components per call through the supplied factories.
- [boundary] The concrete implementations and sub-assemblies are selected here; the runner's operations never select components.
- [external] The concrete component implementations and sub-assemblies.

## Non-concerns

- Consumption of the assembled runner (entry points, generated wrappers): unspecified here.
- Selection policy: the concrete implementations wired here are a default assembly; other selections may differ.
- Testability: this assembly is never tested; it performs no functionality beyond configuration and assembly of other modules.
