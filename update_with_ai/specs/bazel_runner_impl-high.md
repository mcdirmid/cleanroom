# bazel_runner_impl

fulfills: bazel_runner
imports: bazel_graph_storage (graph + message store), dag_storage (messages), dag_clean_logic (cleaning), dag (topological cleaning), agent_loop (agent runs), sandbox (tool definitions and execution), bazel_agent_config (agent configuration)
terms (from dag_storage): node, pending message, subgraph
terms (from dag_clean_logic): cleaning, feedback message
terms (from bazel_agent_config): agent configuration, config target, API key
terms (from bazel_runner): result

## Deltas beyond the bazel_runner contract

### Behavior

- Assembles the cleanroom system internally — a Bazel graph storage, an agent loop, and a DAG clean logic — and runs a topological cleaning pass over the target node's subgraph.
- Configures the agent loop from an agent configuration declared as an agent_config target (config target), resolving the API key from the environment; the config target is a per-call parameter of `run_dag` and is never hardcoded.
- Delivers injected feedback to a node's message store.

### Operation Boundaries

- All components (graph storage, agent loop, DAG) are created internally per call; the cleaning pass's atomicity is per the bazel_runner interface contract.
- The agent configuration is resolved per call: the explicit config target (when provided), then the AGENT_CONFIG_TARGET environment variable, then the //agent_configs:default convention.

### State Management

- No persistent state is held across calls.
- Feedback injection constructs a graph separately from the graph used by a cleaning pass.

### External Dependencies

- The assembled components (graph, message store, agent loop, DAG clean logic), the language model service, and the generated module of the selected agent_config target (config target).

### Error Handling

- Expected failures are provided as values per the bazel_runner interface contract (a result); the log file is always written, regardless of the result.
- Unexpected failures — configuration failures (missing config target module, missing API key) signaled by the bazel_agent_config component, a missing manifest, or log-file failure — are signaled as exceptions and are outside the value contract.
- Configuration failures are signaled by the bazel_agent_config component before the cleaning pass starts.

## Non-concerns

- Agent configuration values (model, URL, limits): declared as agent_config Bazel targets (see update_with_ai/agent_config.bzl), not specified here.
- API keys: resolved from the environment by the bazel_agent_config component; never stored in code, Bazel, or version control.
