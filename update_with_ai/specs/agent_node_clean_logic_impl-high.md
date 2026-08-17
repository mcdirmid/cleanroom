# agent_node_clean_logic_impl

fulfills: dag_clean_logic
imports: bazel_graph_storage (node definitions), dag_storage (messages), agent_loop (agent runs), sandbox (tool definitions and execution)
terms (from dag_clean_logic): dirty, cleaning, change message, feedback message
terms (from dag_storage): node, dependency, pending message
terms (from agent_loop): run
terms (from sandbox): blame, blame target, file write
terms (from tool_provider): tool definition, tool failure
terms (refined): dirty -> pending messages or writable output files missing on disk
terms (refined): cleaning -> running the node's agent

## Deltas beyond the dag_clean_logic contract

### Behavior

- Cleaning a node builds a sandbox from the node's sandbox configuration (via bazel_graph_storage), then runs the agent loop with the node's prompt and the sandbox's tool definitions, delegating tool execution to the sandbox.
- The node's pending messages are provided to the agent run as context, so the agent can respond to change and feedback from its dependencies.
- The agent run is informed of the files it may read and write, per the node's sandbox configuration.
- The node's sandbox configuration may omit the verification callback; in that case the verification tool is not provided.

### Outcome mapping

| Run outcome | Cleaning result |
|---|---|
| final answer | change messages if the run modified the workspace; otherwise no change (no messages) |
| feedback result (the sandbox's blame tool) | feedback messages — one (target, feedback) pair per blamed dependency; each target is validated to be a dependency of the node; a blame with an invalid target signals a tool failure (not an agent failure) |
| change result (the sandbox's success tool when the run modified the workspace) | change messages |
| no-change result (the sandbox's success tool) | no change (no messages) |
| run fails | failure (cleaning halts per the dag contract) |

### Refined terms

- dirty -> pending messages or writable output files missing on disk.
- cleaning -> running the node's agent.

### Operation Boundaries

- Each cleaning runs exactly one agent run.
- The run is atomic: it provides messages or signals failure, never both.

### Ordering

- Cleaning is sequential per node; the consuming dag component does not invoke cleaning concurrently.

### State Management

- No state beyond the current run; the sandbox's per-run state (including the write-occurred flag) is reset for each cleaning.
- Run events may be reported to an optional logger callback, attributing each event to the node being cleaned.

### External Dependencies

- bazel_graph_storage (node definitions), agent_loop (agent run), sandbox (tool definitions and execution), and the language model service.

### Error Handling

- Agent failures and tool-execution failures signal failure per the dag_clean_logic contract, leaving pending messages unchanged.
- An invalid blame target (one that is not a dependency of the node) signals a tool failure, not an agent failure: the agent may correct its blame and continue.

## Non-concerns

- Change-message content: the exact content of change messages (e.g., the final answer or a summary of produced artifacts) is unspecified.
- Sandbox construction: whether sandboxes are cached across cleanings is unspecified.
- Agent-loop retry behavior: per the agent_loop contract.
