# loop_node_cleaner_impl implementation component

imports: agent_node_config, agent_storage, dag_storage, loop_conversation, loop_driver, runner_logger, sandbox
implements: loop_node_cleaner

## Purpose

The loop_node_cleaner_impl implementation component realizes node clean execution, initial get work conversation seeding, and outcome message dispatching for agent-driven nodes.

Driving node execution requires bridging abstract graph clean directives to concrete multi-turn turn loops and translating tool termination responses back into graph messages. The loop_node_cleaner_impl implementation component configures session roles for dirty nodes, initializes conversation history with get work directives, executes the agent loop, and converts termination responses into propagating graph updates.

**Out of scope:** The loop_node_cleaner_impl implementation component does not parse JSON build manifests, enforce repetition thresholds, or write transcript logs to disk; these are handled by other components.

## Types and Behavior

The node cleaner cleans dirty nodes within an agent session phase where the role config presents the role of the dirty nodes to session services, logging unexpected execution failures to the runner logger and retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.

The conversation is initialized with instructions directing the agent to call the get work tool.

Cleaning resolves dirty nodes by evaluating the loop driver outcome.

Resolving dirty nodes produces:

- Change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.

- Feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.

- No propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.

When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.

Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
