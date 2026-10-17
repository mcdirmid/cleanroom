<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Split the phase execution paragraph, canonicalize change timestamps, and state the feedback routing invariant
CODE_HASH: ed55f7543be9
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# loop_node_cleaner_impl implementation component

imports: agent_node_config, agent_storage, dag_storage, dag_subgraph, loop_conversation, loop_driver, runner_logger, src_metadata
implements: loop_node_cleaner, loop_cleaner

## Purpose

The loop_node_cleaner_impl implementation component realizes node clean execution, topological graph cleaning traversal, initial get work conversation seeding, and outcome message dispatching for agent-driven nodes.

Driving node execution requires bridging abstract graph clean directives to concrete multi-turn turn loops and translating tool termination responses back into graph updates. The loop_node_cleaner_impl implementation component configures session roles for dirty nodes, initializes conversation history with get work directives, executes the agent loop, and converts termination responses into in-band graph state updates.

**Out of scope:** The loop_node_cleaner_impl implementation component does not parse JSON build manifests, enforce repetition thresholds, or write transcript logs to disk; these are handled by other components.

**Delegated:** Turn loop execution is delegated to loop_driver; source code modification checking is delegated to src_metadata; graph storage updates are delegated to dag_storage; unexpected execution failures are logged through runner_logger; subgraph batching and topological ordering are delegated to dag_subgraph.

## Types and Behavior

Cleaning a target node through the loop cleaner scopes an active subgraph by setting the target node on the dag subgraph, which determines the dependency-first topological order of the reachable nodes.

Cleaning then processes ready batches of dirty nodes in topological order, records node visits for each cleaned batch, and halts immediately when the node cleaner communicates that processing cannot continue.

Cleaning concludes when the dag subgraph reports that the target subgraph is complete, meaning every reachable node in the target subgraph is clean in dag storage.

The node cleaner cleans dirty nodes within an agent session phase, where the role config presents the role of the dirty nodes to session services.

When an unexpected execution failure occurs, the node cleaner logs the failure to the runner logger, retries the session phase once, and propagates the failure when the retry also fails.

The conversation is initialized with instructions directing the agent to call the get work tool.

Cleaning resolves dirty nodes by evaluating the loop driver outcome.

Resolving dirty nodes results in:

- Marking each node clean in graph storage with the change summary from the outcome when workspace file modifications occurred for that node, and marking the node clean without advancing its change timestamp when no workspace files were modified for that node.

- Recording a feedback message containing the blame explanation and addressed strictly to the declared feedback dependency node that owns the blamed file when the outcome signals blame attributed to a configured blame target of the dirty nodes (extracting blame targets and explanations from conversational response text and matching configured targets by unit address, address suffix, or file path and stem), leaving the nodes dirty when the blamed file does not match a configured blame target.

- Leaving the nodes dirty without updating clean state when the outcome signals run failure, communicating that processing cannot continue.

When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, marking the nodes clean with a change summary when incoming pending messages indicate changes from upstream dependencies, and marking the nodes clean without a change summary otherwise.

A feedback message is delivered only to the declared feedback dependency node that owns the blamed file, never to an arbitrary dependency, a non-feedback dependency, a guide, or a fixed node specification.
