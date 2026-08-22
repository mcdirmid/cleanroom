# agent_node_clean_logic_impl

fulfills: dag_clean_logic
imports: bazel_graph_storage (node definitions), dag_storage (messages), agent_loop (agent runs), sandbox (tool definitions and execution)
terms (from dag_clean_logic): dirty, cleaning, change message, feedback message
terms (from dag_storage): node, dependency, pending message
terms (from agent_loop): run, system prompt
terms (from sandbox): blame, blame target, file write, session-start read, template
terms (from tool_provider): tool definition, tool failure
terms (refined): dirty, cleaning

## Deltas

- Cleaning a node builds a sandbox from the node's sandbox configuration (via bazel_graph_storage), then runs the agent loop with the sandbox's tool definitions, delegating tool execution to the sandbox.
- The node's prompt, augmented with lines naming the readable and writable files, is provided as the run's system prompt.
- The node's pending messages are provided as the run's user prompt, so the agent can respond to change and feedback from its dependencies.
- Cleaning a node requests the sandbox's session-start reads and provides them as the run's session-start tool results, so the read-only files' content is in the conversation before the agent's first turn.
- A node whose writable output file does not exist on disk or holds exactly its template's content receives a feedback message directing it to update the file from its template: the message is present in the node's pending messages before the node's cleaning, at most once per pending set; a failed cleaning leaves it pending, so the node remains dirty until a cleaning succeeds.
- The node's sandbox configuration may omit the verification callback; in that case advance's verification passes without a callback.

| Run outcome | Cleaning result |
|---|---|
| feedback result (the sandbox's blame tool) | feedback messages — one (target, feedback) pair per blamed dependency; each target is validated to be a dependency of the node; a blame with an invalid target signals a tool failure (not an agent failure) |
| change result (the sandbox's advance tool when the run modified the workspace) | change messages |
| no-change result (the sandbox's advance tool) | no change (no messages) |
| run fails | failure (cleaning halts) |

- [boundary] Each cleaning runs exactly one agent run.
- [boundary] The run is atomic: it provides messages or signals failure, never both.
- [ordering] Cleaning is sequential per node; the consuming dag component does not invoke cleaning concurrently.
- [state] No state beyond the current run; the sandbox's per-run state (including the write-occurred flag) is reset for each cleaning.
- [state] Run events may be reported to an optional logger callback, attributing each event to the node being cleaned.
- [external] bazel_graph_storage (node definitions), agent_loop (agent run), sandbox (tool definitions and execution), and the language model service.
- [failure] Agent failures and tool-execution failures signal failure, leaving pending messages unchanged.
- [failure] An invalid blame target (one that is not a dependency of the node) signals a tool failure, not an agent failure: the agent may correct its blame and continue.
- [refines] dirty -> pending messages, a writable output file missing on disk, or a writable output file with a template holding exactly its template's content.
- [refines] cleaning -> running the node's agent.

## Non-concerns

- Change-message content: the exact content of change messages (e.g., the summary of produced artifacts) is unspecified.
- Template-feedback wording: the exact wording of the template-update feedback message is unspecified.
- Sandbox construction: whether sandboxes are cached across cleanings is unspecified.
- Agent-loop retry behavior: per the agent_loop contract.
