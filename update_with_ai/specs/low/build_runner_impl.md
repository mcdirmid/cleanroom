<!-- Dependencies (md files to read alongside this one):
  - build_runner.md
  - runner_logger.md
  - dag_storage.md
  - dag_cleaner.md
  - dag_clean_logic.md
  - build_graph_storage.md
  - agent_loop.md
  - build_agent_config.md
  - conversation_history.md
-->

# Implementation LLS: build_runner_impl

## Data Types
```python
from typing import Callable, List, Optional, TypeAlias
from build_runner import BuildRunner
from dag_storage import NodeMessage
from dag_cleaner import DagCleaner, CleaningResult
from dag_clean_logic import DagCleanLogic, CleanResult, ChangeResult, FeedbackResult, NoChangeResult, FailureResult
from build_graph_storage import BuildGraphStorage, GraphConfig
from conversation_history import LoggerCallback
from build_agent_config import ConfigTarget
from runner_logger import RunnerLogger

CleanLogicFactory: TypeAlias = Callable[[BuildGraphStorage, str, Optional[ConfigTarget], Optional[LoggerCallback]], DagCleanLogic]

class BuildRunnerImpl(BuildRunner):
    def __init__(self, graph_factory: Callable[[GraphConfig], BuildGraphStorage], clean_logic_factory: CleanLogicFactory, dag_factory: Callable[[BuildGraphStorage, DagCleanLogic], DagCleaner], runner_logger: RunnerLogger): ...
```

`CleanLogicFactory` constructs the per-run clean logic from the graph, the
workspace root, the config target, and the run logger; it resolves the run's
agent configuration (config target argument, then `AGENT_CONFIG_TARGET`, then
`//agent_configs:default`) with the API key resolved from the environment and
supplies the per-node agent loop and sandbox (with the configuration's sandbox
gates applied). `BuildRunnerImpl` is constructed with the three factories and
holds no component instances; it creates the components per call through the
factories. The concrete implementations the factories provide are the
supplying component's concern, never this module's.

## Behavioral Description

`BuildRunnerImpl` implements the `BuildRunner` Protocol over the component
factories supplied at construction; it holds no component instances and
creates them per call.

- **`run_dag`** — Returns the `CleaningResult` produced by the DAG cleaning pass: `(True, CleanResult)` on successful cleaning (a `ChangeResult`, `FeedbackResult`, or `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`). Constructs the graph and message store through the graph factory from the workspace root; opens the run log file (the path follows the `CLEANROOM_AGENT_LOG` / `BUILD_WORKSPACE_DIRECTORY` / `BUILD_WORKING_DIRECTORY` priority, defaulting to `agent_loop.log`); constructs the run logger, which tracks cumulative token usage and duration across all agent sessions in the pass, emits compact one-line event summaries to stdout (for `tool_called`, `run_terminated` reporting session and all-session cumulative token usage and timing, and `error` events) and writes a verbose transcript line for every event to the log file, each line flushed immediately after it is written; constructs the clean logic through the clean-logic factory with the graph, the workspace root, the config target, and the run logger; constructs the DAG through the DAG factory from the graph and the clean logic; runs the cleaning pass. The log file is always written and closed, regardless of the result; a failure during graph construction propagates without a log file. Configuration failures (signaled by the `build_agent_config` component) are unexpected failures that propagate before the cleaning pass starts. An interrupt (ctrl-C / SIGINT) terminates the run promptly: the interrupt is never ignored and processing never continues past it, the log file is closed, and the process exits with the interruption status (`128 + SIGINT`); no partial state is left that would corrupt a subsequent run.

- **`inject_feedback`** — Constructs a graph through the graph factory and delivers the given messages to the node's pending message store as feedback-kind `NodeMessage` values, marking the node dirty for a subsequent cleaning pass. Returns `(True, CleanResult)` on success (a `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`) if the node does not exist.

- **`add_change`** — Constructs a graph through the graph factory and delivers a change-kind `NodeMessage` (the given change text, or `check` when omitted) to the node's pending message store, marking the node dirty for a subsequent cleaning pass. Returns `(True, CleanResult)` on success (a `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`) if the node does not exist.

- **`broadcast_change`** — Constructs a graph through the graph factory, composes the message from the node's declared source file (its sandbox configuration's first writable path) and the given change text (`<declared source file>: <change text>`), adds a change-kind `NodeMessage` of that text to the pending set of each of the node's known reverse dependencies, then deletes the node's data (pending messages and known reverse dependencies). A recorded reverse dependency absent from the graph is skipped (its message is not delivered); the skip is a pinned refinement of the delivery rule, so stale reverse dependencies do not fail the broadcast. Returns `(True, CleanResult)` on success (a `NoChangeResult` per `dag_clean_logic`) or `(False, CleanResult)` on failure (a `FailureResult`) if the node does not exist.

## Invariants

- All components are created per call through the supplied factories; no persistent state is held across calls.
- A new graph is constructed for `inject_feedback`, `add_change`, and `broadcast_change` separately from the one used by `run_dag`.
- The log file is always written, regardless of the result.
- SIGINT terminates the run promptly: the interrupt is never ignored, the log file is closed on interruption, and no partial state is left that would corrupt a subsequent run.

## Non-Concerns

- **Agent configuration values (API URL, model, iteration count, temperature, timeout):** Declared as `agent_config` Bazel targets and loaded by the `build_agent_config` component through the clean-logic factory; changing them requires editing a BUILD file, not code.
- **API keys:** Resolved from the environment by the `build_agent_config` component; never stored in code, Bazel, or version control.
- **Component selection:** The concrete implementations the supplied factories provide are the supplying component's concern, not specified here.
- **Log file format:** The exact text format of the log file is implementation-specific.
