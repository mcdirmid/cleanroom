# build_runner_impl

fulfills: build_runner
imports: build_graph_storage (graph and message store interfaces), dag_storage (messages), dag_clean_logic (cleaning), dag_cleaner (topological cleaning), agent_loop (agent runs, agent-loop configuration), build_agent_config (agent configuration, config target)
terms (from dag_storage): node, pending message, subgraph
terms (from dag_clean_logic): cleaning, change message, feedback message
terms (from build_agent_config): agent configuration, config target, API key
terms (from agent_loop): run
terms (from build_runner): result

## Deltas

- Implements the build_runner operations over components supplied at construction: a graph factory, a clean-logic factory, and a DAG factory.
- Runs a topological cleaning pass over the target node's subgraph through a DAG supplied by the DAG factory, built from the graph and the clean logic.
- The clean-logic factory supplies the per-node agent loop and sandbox, resolving the run's agent configuration from the config target and applying its sandbox gates.
- The graph factory supplies the graph and message store for the pass; feedback injection, change addition, and change broadcast each construct a graph through the graph factory separately from the pass's graph.
- Delivers injected feedback to a node's message store as feedback messages; delivers change additions to a node's message store as change messages.
- A change addition with no provided change text adds the change message `check`.
- Implements change broadcast by composing the message from the target's declared source file and the provided change text, adding it to the pending set of each of the target's known reverse dependencies, then deleting the target's data.
- [boundary] All components are created per call through the supplied factories; the implementation holds no component instances across calls.
- Tracks cumulative token usage and duration across all agent sessions in the cleaning pass, reporting both session and cumulative totals in stdout and the log file on each session termination.
- [state] No persistent state is held across calls.
- [external] The component implementations supplied through the factories, the language model service, and the generated module of the selected agent_config target (config target).
- [failure] Expected failures are provided as values (a result); the log file is always written, regardless of the result.
- [failure] Unexpected failures — configuration failures (missing config target module, missing API key) signaled by the build_agent_config component, a missing manifest, or log-file failure — are signaled as exceptions and are outside the value contract.
- [failure] Configuration failures are signaled by the build_agent_config component before the cleaning pass starts.
- [failure] The run honors ctrl-C: SIGINT interrupts the run promptly — the interrupt is never ignored and processing never continues past it; the log file is closed, and no partial state is left that would corrupt a subsequent run.

## Non-concerns

- Agent configuration values (model, URL, limits): declared as agent_config Bazel targets, not specified here.
- API keys: resolved from the environment by the build_agent_config component; never stored in code, Bazel, or version control.
- Component selection: the concrete implementations the supplied factories provide are selected elsewhere, not here.
