# agent_node_cleaner_impl implementation component

imports: dag_storage, agent_runner, sandbox, agent_conversation_history, bazel_graph_storage
implements: agent_node_cleaner, dag_node_cleaner

## Purpose

The agent_node_cleaner_impl implementation component realizes node clean execution, synthetic startup transcript seeding, and outcome message dispatching for agent-driven nodes.

Driving node execution requires bridging abstract graph clean directives to concrete multi-turn turn loops and translating tool termination responses back into graph messages. The agent_node_cleaner_impl implementation component configures session sandboxes from stored target metadata, injects paired startup executions into conversation histories, executes the agent loop, and converts termination responses into propagating graph updates.

**Out of scope:** The agent_node_cleaner_impl implementation component does not parse JSON build manifests, enforce repetition thresholds, or write transcript logs to disk; these are handled by other components.

## Types and Behavior

The agent node cleaner cleans a dirty node within an agent session phase, establishing the scope where session services operate and configuring the cleaned node with the target node.

Within the agent session phase, cleaning executes the agent runner from agent runner, a sandbox from sandbox, and a conversation history from agent conversation history.

Startup templates provided by the sandbox are materialized into missing read-write files before agent interaction.

The conversation history is seeded with startup context comprising the node definition and task prompt retrieved from bazel graph storage for the dirty node, incoming pending messages from dag storage, and paired startup tool executions from the sandbox formatted with synthetic tool requests and captured responses.

Execution of the agent runner resolves the dirty node based on the produced agent outcome:

- An outcome signaling successful advancement with workspace file modifications produces change messages for downstream dependent nodes.

- An outcome signaling blame attributed to an upstream node produces feedback messages addressed to that dependency node.

- An outcome signaling run failure leaves the node dirty without producing propagating messages.
