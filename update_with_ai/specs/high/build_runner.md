# build_runner

imports: dag_cleaner (topological cleaning), dag_storage (messages), dag_clean_logic (change and feedback), build_agent_config (agent configuration), sandbox (sandbox configuration), guide_delivery (step mode), run_control (blame), runner_logger (verbose transcript)
terms (from dag_storage): node, pending message, subgraph
terms (from dag_clean_logic): dirty, cleaning, change message, feedback message
terms (from build_node_loader): manifest
terms (from build_agent_config): agent configuration, config target
terms (from guide_delivery): step mode
terms (from run_control): blame
terms (from runner_logger): verbose transcript
terms (owned): result

## Purpose

Orchestrates the full agent pipeline — graph resolution, message persistence, agent execution, and topological cleaning — as a single executable unit.

## Terms

- Result: the outcome of a cleaning operation: success (no messages, change, or feedback produced) or failure.

## Contract

**Inputs**

- A root node label.
- A workspace root.
- An optional config target (selecting the agent configuration).
- For feedback injection: feedback messages.
- For change addition: a change text.
- For change broadcast: a change text.

**Operations**

- Run a topological cleaning pass starting from a root node.
- Inject feedback messages to a specific node's message store (marking the node dirty for a subsequent run).
- Add a change message to a specific node's message store (marking the node dirty for a subsequent run).
- Broadcast a change from a specific node to its known reverse dependencies.
- Provide a config target selecting the agent configuration for the cleaning pass; when none is provided, the agent configuration is selected by the environment (AGENT_CONFIG_TARGET) and then the //agent_configs:default convention.

**Guarantees**

- On success: provides a clean result — no messages, a change result, or a feedback result (all nodes in the subgraph cleaned).
- On failure — the offending node's messages remain unchanged, previously cleaned nodes retain changes, and processing halts — when:
  - a node's cleaning failed;
  - a termination limit was exceeded (message cycle or non-clearing dirty state);
  - feedback targets a node outside the subgraph;
  - the graph contains a cycle (the subgraph cannot be topologically ordered).
- All output (changes and feedback) is delivered to the appropriate target nodes' message stores.
- Assembles its components internally; the client provides no component instances.
- Applies the agent configuration to each node's sandbox configuration: whether session-start reads are enabled and whether step mode is enabled.
- Exposes only the cleaning, feedback, change-addition, and change-broadcast operations, not component APIs.
- A successful feedback injection adds each message to the target node's pending messages as a feedback message (marking the node dirty; when cleaned, the node must change, blame, or fail) and provides a no-change result.
- A successful change addition adds a change message to the target node's pending messages (marking the node dirty for a subsequent cleaning pass); the node may succeed without changing.
- A change addition with no provided change text adds a default change message.
- A change broadcast adds a change message to the pending set of each of the target's known reverse dependencies.
- The broadcast message is the target's declared source file name followed by the provided change text.
- A change broadcast clears the target's pending messages and known reverse dependencies.
- A feedback injection, a change addition, or a change broadcast for a node that does not exist in the graph signals failure, leaving state unchanged.
- Expected failures are provided as values (a result); unexpected failures — assembly failures such as agent-configuration resolution failure or a missing manifest — are signaled as exceptions and are outside the value contract.

**Assumptions**

- The root node is a valid node label.
- The workspace root points to a valid workspace with manifest files.

**Logging**

- Provides compact one-line summaries of run events to standard output; on agent session termination, reports the agent session's token usage (input tokens with cached percentage and output tokens) and elapsed duration alongside cumulative totals across all agent sessions in the pass.
- Provides a verbose transcript to a log file whose path is determined by a configured environment variable or a default location (the Bazel workspace directory when running under Bazel, otherwise the current working directory).
- The transcript records each request's conversation state.

## Non-concerns

- Error message wording: the exact wording of failure reasons is unspecified.
