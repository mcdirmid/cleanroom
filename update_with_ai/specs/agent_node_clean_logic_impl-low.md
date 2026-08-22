<!-- Dependencies (md files to read alongside this one):
  - dag_clean_logic-low.md
  - dag_storage-low.md
  - bazel_graph_storage-low.md
  - agent_loop-low.md
  - sandbox-low.md
  - tool_provider-low.md
-->

# Implementation LLS: agent_node_clean_logic_impl

## Data Types
```python
from typing import Callable
from dag_clean_logic import DagCleanLogic, NodeId, CleanResult, ChangeResult, FeedbackResult, NoChangeResult, FailureResult
from dag_storage import NodeMessage
from bazel_graph_storage import BazelGraphStorage
from agent_loop import AgentLoop, AgentLoopConfig, AgentResult, LoggerCallback
from sandbox import Sandbox, SandboxConfig
from tool_provider import ToolDefinition, ToolExecutor, ToolFailure, TerminateSuccessResult, TerminateAgentWithSuccess, TerminateAgentWithFailure

class AgentNodeCleanLogicImpl(DagCleanLogic):
    def __init__(
        self,
        graph: BazelGraphStorage,
        agent_loop_config: AgentLoopConfig,
        make_sandbox: Callable[[SandboxConfig], Sandbox],
        make_agent_loop: Callable[[AgentLoopConfig], AgentLoop],
        logger: LoggerCallback | None = None,
    ): ...
```

The implementation creates `AgentNodeCleanLogicImpl`, which fulfills the `DagCleanLogic` interface from `dag_clean_logic-low.md`. The interface admits multiple implementations (e.g., different cleaning strategies), so per the naming rule the implementation name does not match the interface name; this one is agent-loop-based. Constructed with a `BazelGraphStorage` for node definitions, the agent loop configuration, and factories that construct sandboxes and agent loops (capability bundling; the assembler wires concrete implementations); an optional logger callback reports run events attributed to the node being cleaned.

## Behavioral Description

`AgentNodeCleanLogicImpl` fulfills the `DagCleanLogic` interface from `dag_clean_logic-low.md`:

- `clean` — for a node: resolves the node's definition (prompt and sandbox configuration) via the configured `bazel_graph_storage`; constructs a sandbox from the node's sandbox configuration; requests the sandbox's session-start reads and runs the agent loop with the node's prompt as the system prompt, the pending messages as the user prompt, the session-start reads as the run's session-start tool results, the sandbox's `ToolDefinition`s, and `ToolExecutor` execution delegated to the sandbox; maps the run outcome to a `CleanResult`:
  - `(TerminateAgentWithSuccess, history)` — the termination value is the `TerminateSuccessResult` formed by the sandbox's termination tool (`advance`/`blame`) and adopted as the result: a `FeedbackResult`, a `ChangeResult`, or a `NoChangeResult`
  - `(TerminateAgentWithFailure[T_tool], history)` — `failure`, leaving pending messages unchanged (per the `dag_clean_logic` contract)
  - `(error, history)` (a loop failure) — `failure`, leaving pending messages unchanged (per the `dag_clean_logic` contract)
- `is_dirty` — signals dirtiness when the node has pending messages, a writable output file does not exist on disk, or a writable output file with a configured template (an entry in the sandbox configuration's `templates`) holds exactly its template's content. When the file-based condition holds, delivers a template-update feedback message to the node's pending set via the graph's `add_messages` — the message content pinned to `update target file from template` — only when the `pending_messages` passed to `is_dirty` does not already contain it (at most once per pending set); the message is present before the node's cleaning and persists across failed cleanings, so the node remains dirty until a cleaning succeeds.

**Prompt composition:** The run's system prompt is the node's prompt augmented with lines naming the readable and writable files (from the sandbox configuration's `readable_paths` and `writable_paths`); the run's user prompt is the node's pending messages joined by newlines, so the agent can act on change and feedback from other nodes. When the node has no pending messages, the user prompt is empty.

**Blame-target validation (handoff between layers):** The `FeedbackResult` formed by `sandbox`'s `blame` tool specifies targets from the `blame_targets` set (validated by the sandbox at call time). The `ToolExecutor` additionally validates that each `blame` target is a dependency of the node: a `blame` call with a target that is not a dependency returns `ToolFailure[T_tool]` (a tool failure — the agent may correct and continue), so only valid pairs ever reach the run result.

**Tool-call delegation:** The `ToolExecutor` dispatches each tool call by name to the corresponding sandbox operation. A tool call for an operation the sandbox does not provide signals a tool failure identifying the tool.

**Message conversion for DAG storage:** Conversation entries from the agent loop are converted to `NodeMessage = str` when placed into the DAG's message store. The implementation explicitly converts `result.answer` to a string via `str(result.answer)` when mapping to `ChangeResult`.

**HLS Justification:** Creates `AgentNodeCleanLogicImpl` that fulfills the `DagCleanLogic` interface and uses the configured `bazel_graph_storage`.

## Invariants

- Each cleaning runs exactly one agent run; the run provides messages or signals failure, never both
- The template-update feedback message is delivered at most once per pending set (never duplicated)
- Cleaning is sequential per node; the consuming dag component does not invoke cleaning concurrently
- The sandbox's per-run state (including the write-occurred flag) is reset for each cleaning
- Blame targets are validated to be dependencies of the node (handoff from sandbox's blame_targets validation)
- Conversation entries are converted to strings when placed into the DAG's message store

## Non-Concerns

- **Change-message content:** The exact content of change messages (e.g., the summary of produced artifacts) is unspecified.
- **Template-feedback wording:** Pinned to `update target file from template`; tests may assert it.
- **Sandbox construction caching:** Whether sandboxes are cached across cleanings is unspecified.
- **Agent-loop retry behavior:** Per the `agent_loop` contract.

