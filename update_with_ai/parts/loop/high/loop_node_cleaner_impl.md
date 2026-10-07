<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-05T05:06:19Z
CHANGE: Add delegated collaborator statement and eliminate redundant outcome sentence
CODE_HASH: 0bfb9c80e86b
-->

# loop_node_cleaner_impl implementation component

imports: agent_node_config, agent_storage, dag_storage, loop_conversation, loop_driver, runner_logger, sandbox
implements: loop_node_cleaner

## Purpose

The loop_node_cleaner_impl implementation component realizes node clean execution, initial get work conversation seeding, and outcome message dispatching for agent-driven nodes.

Driving node execution requires bridging abstract graph clean directives to concrete multi-turn turn loops and translating tool termination responses back into graph updates. The loop_node_cleaner_impl implementation component configures session roles for dirty nodes, initializes conversation history with get work directives, executes the agent loop, and converts termination responses into in-band graph state updates.

**Out of scope:** The loop_node_cleaner_impl implementation component does not parse JSON build manifests, enforce repetition thresholds, or write transcript logs to disk; these are handled by other components.

**Delegated:** Turn loop execution is delegated to loop_driver; session services are delegated to sandbox; graph storage updates are delegated to dag_storage.

## Types and Behavior

The node cleaner cleans dirty nodes within an agent session phase where the role config presents the role of the dirty nodes to session services, logging unexpected execution failures to the runner logger and retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.

The conversation is initialized with instructions directing the agent to call the get work tool.

Cleaning resolves dirty nodes by evaluating the loop driver outcome.

Resolving dirty nodes results in:

- Marking the nodes clean in graph storage with the change summary from the outcome when the outcome signals successful advancement with workspace file modifications, and marking the nodes clean without advancing last changed timestamps when no workspace files were modified.

- Feedback messages containing the blame explanation and addressed strictly to the declared feedback dependency node owning the blamed file when the outcome signals blame attributed to a configured blame target of the dirty nodes, leaving the nodes dirty when the blamed file does not match a configured blame target.

- Leaving the nodes dirty without updating clean state when the outcome signals run failure, communicating that processing cannot continue.

When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, marking the nodes clean with a change summary when incoming pending messages indicate changes from upstream dependencies, and marking the nodes clean without changes otherwise.

Delivering feedback messages to arbitrary dependencies, non-feedback dependencies, guides, or fixed node specifications is prohibited.
