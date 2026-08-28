<!-- Dependencies (md files to read alongside this one):
  - dag_clean_logic.md
  - dag_storage.md
  - build_graph_storage.md
  - agent_loop.md
  - agent_loop_config.md
  - sandbox.md
  - tool_provider.md
  - file_view.md
  - guide_delivery.md
  - run_control.md
-->

# Implementation LLS: agent_node_clean_logic_impl

## Data Types
```python
from typing import Callable
from dag_clean_logic import DagCleanLogic, CleanResult, ChangeResult, FeedbackResult, NoChangeResult, FailureResult
from dag_storage import NodeMessage
from build_graph_storage import BuildGraphStorage
from agent_loop import AgentLoop, AgentResult, LoggerCallback
from agent_loop_config import AgentLoopConfig
from sandbox import Sandbox, SandboxConfig
from tool_provider import ToolDefinition, ToolExecutor, ToolFailure, TerminateSuccessResult, TerminateAgentWithSuccess, TerminateAgentWithFailure

class AgentNodeCleanLogicImpl(DagCleanLogic):
    def __init__(
        self,
        graph: BuildGraphStorage,
        agent_loop_config: AgentLoopConfig,
        make_sandbox: Callable[[SandboxConfig], Sandbox],
        make_agent_loop: Callable[[AgentLoopConfig], AgentLoop],
        logger: LoggerCallback | None = None,
    ): ...
```

The implementation creates `AgentNodeCleanLogicImpl`, which fulfills the `DagCleanLogic` interface from `dag_clean_logic.md`. The interface admits multiple implementations (e.g., different cleaning strategies), so per the naming rule the implementation name does not match the interface name; this one is agent-loop-based. Constructed with a `BuildGraphStorage` for node definitions, the agent loop configuration, and factories that construct sandboxes and agent loops (capability bundling; the assembler wires concrete implementations); an optional logger callback reports run events attributed to the node being cleaned.

## Behavioral Description

`AgentNodeCleanLogicImpl` fulfills the `DagCleanLogic` interface from `dag_clean_logic.md`:

- `clean` — for a node: resolves the node's definition (prompt and sandbox configuration) via the configured `build_graph_storage`; constructs a sandbox from the node's sandbox configuration with its `feedback_pending` set from whether the node's pending messages include a feedback message; requests the sandbox's session-start reads and runs the agent loop with the node's prompt as the system prompt, the pending messages as the user prompt, the session-start reads as the run's session-start tool results, the sandbox's `ToolDefinition`s, and `ToolExecutor` execution delegated to the sandbox; maps the run outcome to a `CleanResult`:
  - `(TerminateAgentWithSuccess, history)` — the termination value is the `TerminateSuccessResult` formed by the sandbox's termination tool (`advance`/`blame`) and adopted as the result: a `FeedbackResult`, a `ChangeResult`, or a `NoChangeResult`
  - `(TerminateAgentWithFailure[T_tool], history)` — `failure`, leaving pending messages unchanged (per the `dag_clean_logic` contract)
  - `(error, history)` (a loop failure) — `failure`, leaving pending messages unchanged (per the `dag_clean_logic` contract)
- `is_dirty` — signals dirtiness when the node has pending messages, a writable output file does not exist on disk, or a writable output file with a configured template (an entry in the sandbox configuration's `templates`) holds exactly its template's content. When the file-based condition holds, delivers a template-update feedback message (kind `feedback`, text `update target file from template`) to the node's pending set via the graph's `add_messages` — only when the `pending_messages` passed to `is_dirty` does not already contain it (at most once per pending set); the message is present before the node's cleaning and persists across failed cleanings, so the node remains dirty until a cleaning succeeds.

**Prompt composition:** The run's system prompt is the node's prompt augmented with lines naming the readable and writable files (from the sandbox configuration's `readable_paths` and `writable_paths`); the run's user prompt is the node's pending messages' text joined by newlines, so the agent can act on change and feedback from other nodes. The user prompt carries the pending messages' text and no statement of the feedback obligation; the obligation surfaces only through advance's rejection. When the node has no pending messages, the user prompt is empty. When step mode is enabled (the sandbox configuration's `step_sections_enabled` is set and a guide is configured), the user prompt includes the step-mode protocol: the guide arrives through the advance operation — the guide summary at run start, then a step section after each advance that passed verification; call advance after each section.

**Blame-target validation (handoff between layers):** The `FeedbackResult` formed by `sandbox`'s `blame` tool specifies owning nodes from the `blame_targets` mapping (validated and resolved by the sandbox at call time: each pair's target is a blameable artifact's virtual name). The `ToolExecutor` additionally validates that each `blame` target's owning node (resolved via the sandbox configuration's `blame_targets` mapping) is a dependency of the node: a `blame` call with a target that resolves to no owning node, or whose owning node is not a dependency, returns `ToolFailure[T_tool]` (a tool failure — the agent may correct and continue), so only valid pairs ever reach the run result.

**Tool-call delegation:** The `ToolExecutor` dispatches each tool call by name to the corresponding sandbox operation. A tool call for an operation the sandbox does not provide signals a tool failure identifying the tool.

**Messages for DAG storage:** The messages placed into the DAG's message store are `NodeMessage` values (a kind and text, per `dag_storage.md`), adopted from the run outcome without conversion: a `ChangeResult`'s messages carry the `change` kind, a `FeedbackResult`'s messages carry the `feedback` kind, and the template-update feedback message carries the `feedback` kind.

**HLS Justification:** Creates `AgentNodeCleanLogicImpl` that fulfills the `DagCleanLogic` interface and uses the configured `build_graph_storage`.

## Invariants

- Each cleaning runs exactly one agent run; the run provides messages or signals failure, never both
- The template-update feedback message is delivered at most once per pending set (never duplicated)
- Cleaning is sequential per node; the consuming dag_cleaner component does not invoke cleaning concurrently
- The sandbox's per-run state (including the write-occurred flag) is reset for each cleaning
- Each blame target's owning node is validated to be a dependency of the node (handoff from sandbox's blame_targets validation)
- Messages placed into the DAG's message store are `NodeMessage` values with the `change` or `feedback` kind

## Non-Concerns

- **Change-message content:** The exact content of change messages (e.g., the summary of produced artifacts) is unspecified.
- **Template-feedback wording:** Pinned to `update target file from template`; tests may assert it.
- **Sandbox construction caching:** Whether sandboxes are cached across cleanings is unspecified.
- **Agent-loop retry behavior:** Per the `agent_loop` contract.
- **Defensive outcome fallback:** A run outcome outside the mapped cases (a non-tuple `AgentResult` or an out-of-contract termination value) is adopted as a `NoChangeResult` — an unreachable-in-contract defensive fallback (the agent loop produces only the mapped outcomes), pinned here so it is not read as an error.
- **Tool-execution error conversion:** An unexpected sandbox exception during a tool call is converted to a tool failure (the session continues), and a parameter-validation error is refined into a tool failure identifying the parameter — a defensive refinement of the dispatch rule, pinned here.

