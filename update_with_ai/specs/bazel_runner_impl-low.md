<!-- Dependencies (md files to read alongside this one):
  - bazel_runner-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
  - dag-low.md
  - bazel_graph_storage-low.md
  - agent_loop-low.md
  - sandbox-low.md
  - bazel_agent_config-low.md
-->

# Implementation LLS: bazel_runner_impl

## Data Types
```python
from bazel_runner import BazRunner
from dag_storage import NodeId
from dag import CleaningResult
from dag_clean_logic import CleanResult, ChangeResult, FeedbackResult, NoChangeResult, FailureResult

class BazRunnerImpl(BazRunner): ...
```

Constructed with no configuration; `workspace_root` and the optional `config_target` are per-call parameters of the interface (see `bazel_runner` Interface LLS). The agent/model configuration itself is loaded per call from an `agent_config` target by the `bazel_agent_config` component.

## Composition

The implementation is an assembler: it wires together these concrete implementations (named here without making them dependencies — the dependency comment above lists the interfaces only):

- Graph storage: `BazelGraphStorageFileImpl`
- Agent loop: `AgentLoopImpl`
- DAG clean logic: `AgentNodeCleanLogicImpl`
- DAG: `DagImpl`
- Sandbox: `SandboxImpl`

**HLS Justification:** The implementation assembles the cleanroom system internally (graph storage, agent loop, DAG clean logic).

## Behavioral Description

`BazRunnerImpl` implements the `BazRunner` Protocol by assembling and running all cleanroom components internally per call.

- **`run_dag`** — Returns the `CleaningResult` produced by the DAG cleaning pass: `(True, CleanResult)` on successful cleaning (a `ChangeResult`, `FeedbackResult`, or `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`). Assembles the components (graph storage, agent loop, DAG clean logic), runs the DAG cleaning pass, and writes a log file regardless of outcome. The agent loop is configured from the resolved agent configuration (config target argument, then `AGENT_CONFIG_TARGET`, then `//agent_configs:default`) with the API key resolved from the environment; configuration failures are unexpected failures signaled by the `bazel_agent_config` component before the cleaning pass starts. Subgraph traversal is a private detail of the DAG cleaning pass. Emits compact one-line event summaries to stdout for tool-called, API-response, run-terminated, and error events (per the `bazel_runner` interface contract). Each event line is flushed to the log file immediately after it is written (log writes are unbuffered), so the transcript reflects the run in real time.

- **`inject_feedback`** — Delivers the given messages to the node's pending message store, marking the node dirty for a subsequent cleaning pass. Returns `(True, CleanResult)` on success (a `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`) if the node does not exist.

**HLS Justification:** Assembles the cleanroom system internally (graph storage, agent loop, DAG clean logic).

## Invariants

- All components (graph storage, agent loop, DAG) are created internally during each call; no persistent state is held across calls.
- A new graph storage is constructed for `inject_feedback` separately from the one used by `run_dag`.
- The log file is always written, regardless of the result.

## Non-Concerns

- **Agent configuration values (API URL, model, iteration count, temperature, timeout):** Declared as `agent_config` Bazel targets (see update_with_ai/agent_config.bzl) and loaded per call by the `bazel_agent_config` component; changing them requires editing a BUILD file, not code.
- **API keys:** Resolved from the environment by the `bazel_agent_config` component; never stored in code, Bazel, or version control.
- **Log file format:** The exact text format of the log file is implementation-specific.

