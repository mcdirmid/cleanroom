# agent_node_cleaner_impl

imports: dag_storage, dag_node_cleaner, agent_runner, sandbox, conversation_history, build_graph_storage, runner_logger, agent_node_cleaner
types from dag_storage: node, pending message
types from dag_node_cleaner: node cleaner, change message, feedback message
types from agent_runner: agent runner, agent outcome
types from sandbox: sandbox, sandbox factory, sandbox configuration, startup interaction
types from conversation_history: conversation history, conversation history factory
types from build_graph_storage: build graph storage, node definition, task prompt
types from runner_logger: runner logger
types from agent_node_cleaner: agent node cleaner
implements: agent node cleaner

## Behavior

- An *agent node cleaner* retrieves the *node definition*, *task prompt*, and *sandbox configuration* for a dirty *node* from *build graph storage*, creates a *sandbox* with a *sandbox factory*, materializes startup templates, and seeds a fresh *conversation history* from a *conversation history factory* with the *task prompt*, the *startup interaction* from the *sandbox* (pairing session-start reads with synthetic `read_file` tool calls and initial step delivery with a synthetic `advance` tool call), and incoming *pending messages* before running the agent with a *runner logger*.
- When an *agent outcome* signals a change result, the *agent node cleaner* formats change summaries into *change messages*.
- When an *agent outcome* signals blame, the *agent node cleaner* formats blame feedback into *feedback messages* addressed to blamed dependencies.
- When an *agent outcome* signals run failure, the *agent node cleaner* leaves the *node* dirty.
