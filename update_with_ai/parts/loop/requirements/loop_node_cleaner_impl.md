# loop_node_cleaner_impl implementation component

imports: agent_node_config, agent_storage, dag_storage, loop_conversation, loop_driver, loop_node_cleaner, runner_logger, sandbox
implements: loop_node_cleaner, agent_node_config

## Assumptions and Requirements

### Requirements

1. The node cleaner cleans dirty nodes within an agent session phase where the role config presents the role of the dirty nodes to session services, logging unexpected execution failures to the runner logger and retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
2. The conversation is initialized with instructions directing the agent to call the get work tool.
3. Resolving dirty nodes produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
4. Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
5. Resolving dirty nodes produces no propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.
6. When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.
7. Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.

## Grounding Facts

### Knowledge Needed

- Dirty nodes role and task prompts from `agent_storage`.
- Session scope and initialization instructions.
- Loop outcome status.
- Non-silent dependencies in `dag_storage`.

### Actions Needed

- Clean dirty nodes within scoped agent session phase.
- Initialize conversation with instructions.
- Generate change messages on success or feedback messages on blame.
- Register dependents and deliver messages to `dag_storage`.
- Log unexpected execution failures to `runner_logger` and retry once before propagating failure.
