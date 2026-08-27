<!-- Dependencies (md files to read alongside this one):
  - build_runner.md
  - dag_storage.md
  - dag_clean_logic.md
  - dag_cleaner.md
  - build_graph_storage.md
  - agent_loop.md
  - sandbox.md
  - build_agent_config.md
-->

# Implementation LLS: build_runner_impl

## Data Types
```python
from build_runner import BuildRunner
from dag_storage import NodeId
from dag_cleaner import CleaningResult
from dag_clean_logic import CleanResult, ChangeResult, FeedbackResult, NoChangeResult, FailureResult

class BuildRunnerImpl(BuildRunner): ...
```

Constructed with no configuration; `workspace_root` and the optional `config_target` are per-call parameters of the interface (see `build_runner` Interface LLS). The agent/model configuration itself is loaded per call from an `agent_config` target by the `build_agent_config` component.

## Composition

The implementation is an assembler: it wires together these concrete implementations (named here without making them dependencies — the dependency comment above lists the interfaces only):

- Graph storage: `BuildGraphStorageFileImpl`
- Agent loop: `AgentLoopImpl`
- DAG clean logic: `AgentNodeCleanLogicImpl`
- DAG: `DagCleanerImpl`
- Sandbox: `SandboxImpl`

**HLS Justification:** The implementation assembles the cleanroom system internally (graph storage, agent loop, DAG clean logic).

## Behavioral Description

`BuildRunnerImpl` implements the `BuildRunner` Protocol by assembling and running all cleanroom components internally per call.

- **`run_dag`** — Returns the `CleaningResult` produced by the DAG cleaning pass: `(True, CleanResult)` on successful cleaning (a `ChangeResult`, `FeedbackResult`, or `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`). Assembles the components (graph storage, agent loop, DAG clean logic), runs the DAG cleaning pass, and writes a log file regardless of outcome. The agent loop is configured from the resolved agent configuration (config target argument, then `AGENT_CONFIG_TARGET`, then `//agent_configs:default`) with the API key resolved from the environment; configuration failures are unexpected failures signaled by the `build_agent_config` component before the cleaning pass starts. Each node's sandbox is constructed with the agent configuration's gates applied to the node's sandbox configuration: `session_start_reads_enabled` from the session-start-reads gate and `step_sections_enabled` from the step-mode gate (see `build_agent_config`). Subgraph traversal is a private detail of the DAG cleaning pass. Emits compact one-line event summaries to stdout for tool-called, API-response, run-terminated, and error events (per the `build_runner` interface contract). Each event line is flushed to the log file immediately after it is written (log writes are unbuffered), so the transcript reflects the run in real time. An interrupt (ctrl-C / SIGINT) terminates the run promptly: the interrupt is never ignored and processing never continues past it, the log file is closed, and the process exits with the interruption status (`128 + SIGINT`); no partial state is left that would corrupt a subsequent run.

- **`inject_feedback`** — Delivers the given messages to the node's pending message store as feedback-kind `NodeMessage` values, marking the node dirty for a subsequent cleaning pass. Returns `(True, CleanResult)` on success (a `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`) if the node does not exist.

- **`add_change`** — Delivers a change-kind `NodeMessage` (the given change text, or `check` when omitted) to the node's pending message store, marking the node dirty for a subsequent cleaning pass. Returns `(True, CleanResult)` on success (a `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`) if the node does not exist.

- **`broadcast_change`** — Composes the message from the node's declared source file (its sandbox configuration's first writable path) and the given change text (`<declared source file>: <change text>`), adds a change-kind `NodeMessage` of that text to the pending set of each of the node's known reverse dependencies, then deletes the node's data (pending messages and known reverse dependencies). A recorded reverse dependency absent from the graph is skipped (its message is not delivered); the skip is a pinned refinement of the delivery rule, so stale reverse dependencies do not fail the broadcast. Returns `(True, CleanResult)` on success (a `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`) if the node does not exist.

**HLS Justification:** Assembles the cleanroom system internally (graph storage, agent loop, DAG clean logic).

## Invariants

- All components (graph storage, agent loop, DAG) are created internally during each call; no persistent state is held across calls.
- A new graph storage is constructed for `inject_feedback`, `add_change`, and `broadcast_change` separately from the one used by `run_dag`.
- The log file is always written, regardless of the result.
- SIGINT terminates the run promptly: the interrupt is never ignored, the log file is closed on interruption, and no partial state is left that would corrupt a subsequent run.

## Non-Concerns

- **Agent configuration values (API URL, model, iteration count, temperature, timeout):** Declared as `agent_config` Bazel targets (see update_with_ai/agent_config.bzl) and loaded per call by the `build_agent_config` component; changing them requires editing a BUILD file, not code.
- **API keys:** Resolved from the environment by the `build_agent_config` component; never stored in code, Bazel, or version control.
- **Log file format:** The exact text format of the log file is implementation-specific.

