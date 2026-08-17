# bazel_runner

imports: dag (topological cleaning), dag_storage (messages), dag_clean_logic (change and feedback), bazel_agent_config (agent configuration)
terms (from dag_storage): node, pending message, subgraph
terms (from dag_clean_logic): dirty, cleaning, change message, feedback message
terms (from agent_loop): run
terms (from bazel_node_loader): manifest
terms (from bazel_agent_config): agent configuration, config target
terms (owned): result

## Purpose

Orchestrates the full agent run pipeline — graph resolution, message persistence, agent execution, and topological cleaning — as a single executable unit.

## Owned definitions

- Result: the outcome of a cleaning operation: success (no messages, change, or feedback produced) or failure.

## Observable dataflow

- Inputs: a root node label, a workspace root, and an optional config target (selecting the agent configuration); for feedback injection, feedback messages.
- Outputs: a result; all output (changes and feedback) is delivered to the appropriate target nodes' message stores.
- The runner assembles all components internally; the client provides no component instances, and the runner owns the full lifecycle of the components it creates (graph, message store, agent loop, DAG).
- The runner exposes only the cleaning and feedback operations, not component APIs.
- The log file is always written once the runner is assembled; a failure during assembly propagates without a log file.

## Contract

**The client provides:**

- A root node label.
- A workspace root.
- For feedback injection: messages (feedback strings).

**The client may:**

- Run a topological cleaning pass starting from a root node.
- Inject feedback messages to a specific node's message store (marking the node dirty for a subsequent run).
- Provide a config target selecting the agent configuration for the cleaning pass; when none is provided, the agent configuration is selected by the environment (AGENT_CONFIG_TARGET) and then the //agent_configs:default convention.

**The component guarantees:**

- On success: provides a clean result — no messages, a change result, or a feedback result (all nodes in the subgraph cleaned).
- On failure — the offending node's messages remain unchanged, previously cleaned nodes retain changes, and processing halts — when:
  - a node's cleaning failed;
  - a termination limit was exceeded (message cycle or non-clearing dirty state);
  - feedback targets a node outside the subgraph;
  - the graph contains a cycle (the subgraph cannot be topologically ordered).
- All output (changes and feedback) is delivered to the appropriate target nodes' message stores.
- A full agent transcript is written to a log file (see Logging).
- A successful feedback injection adds each message to the target node's pending messages (marking the node dirty for a subsequent cleaning pass) and provides a no-change result.
- A feedback injection for a node that does not exist in the graph signals failure, leaving state unchanged.
- Expected failures are provided as values (a result); unexpected failures — assembly failures such as agent-configuration resolution failure or a missing manifest — are signaled as exceptions and are outside the value contract.

**The component assumes:**

- The root node is a valid node label.
- The workspace root points to a valid workspace with manifest files.

## Logging

- Compact one-line event summaries to stdout, covering tool-called, API-response, final-answer, run-terminated, and error events.
- A verbose full transcript to a log file whose path is determined by a configured environment variable or a default location (the Bazel workspace directory when running under Bazel, otherwise the current working directory).

## Non-concerns

- Error message wording: the exact wording of failure reasons is unspecified.
