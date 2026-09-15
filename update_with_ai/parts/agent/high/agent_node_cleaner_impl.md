# agent_node_cleaner_impl implementation component

imports: agent_conversation, agent_driver, agent_node_config, agent_storage, dag_storage, sandbox, template_format
implements: dag_node_cleaner

## Purpose

The agent_node_cleaner_impl implementation component realizes node clean execution, synthetic startup transcript seeding, and outcome message dispatching for agent-driven nodes.

Driving node execution requires bridging abstract graph clean directives to concrete multi-turn turn loops and translating tool termination responses back into graph messages. The agent_node_cleaner_impl implementation component configures session sandboxes from stored target metadata, injects paired startup executions into conversation histories, executes the agent loop, and converts termination responses into propagating graph updates.

**Out of scope:** The agent_node_cleaner_impl implementation component does not parse JSON build manifests, enforce repetition thresholds, or write transcript logs to disk; these are handled by other components.

## Types and Behavior

The node cleaner cleans dirty nodes within an agent session phase where the cleaned nodes present the nodes currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure. The cleaned nodes designate the first node in the sequence as the primary node.

Within the agent session phase, missing read-write files materialize from sandbox startup templates.

The conversation is initialized with startup context comprising the node definition and task prompt retrieved from graph storage for dirty nodes, incoming pending messages ordered deterministically by content and formatted with their message content, and paired startup tool executions from the sandbox formatted with synthetic tool requests and captured responses.

The task prompt is formatted using the template formatter. When cleaning multiple nodes, the task prompt enumerates each target file identified by its file alias alongside its task prompt. Incoming feedback and change messages are formatted per target node identified by its file alias, prefaced with directives to fix read-write target files based on the feedback.

When a dirty node is configured with a guide, the task prompt incorporates guide instructions based on guide step mode. Task prompt instructions for a guided node include:

- Directing the agent to call advance without arguments to view each guide step and omit a change summary until all guide steps are complete when guide step mode is active.

- Identifying the guide file by its file alias and directing the agent to call the submit tool with a change summary describing modifications when complete, or call submit without arguments if no workspace files were modified, when guide step mode is inactive.

Cleaning resolves dirty nodes by evaluating the agent driver outcome.

Resolving dirty nodes produces:

- Change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.

- Feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.

- No propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.

When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.

Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
