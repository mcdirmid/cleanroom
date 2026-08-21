<!-- Dependencies (md files to read alongside this one):
  - dag-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
  - agent_loop-low.md
  - bazel_node_loader-low.md
  - bazel_agent_config-low.md
-->

# Interface LLS: bazel_runner

## Data Types
```python
from typing import Protocol, List
from dag_storage import NodeId
from dag import CleaningResult
from dag_clean_logic import CleanResult, ChangeResult, FeedbackResult, NoChangeResult, FailureResult

class BazRunner(Protocol):
    def run_dag(self, root_node: NodeId, workspace_root: str, config_target: Optional[str] = None) -> CleaningResult: ...
    def inject_feedback(self, node_id: NodeId, workspace_root: str, messages: List[str]) -> CleaningResult: ...
```
## Component-Provided Operations

### `run_dag`

```python
def run_dag(self, root_node: NodeId, workspace_root: str, config_target: Optional[str] = None) -> CleaningResult
```

**Purpose:** Run a topological cleaning pass starting from `root_node`, producing output (changes or feedback) for all dirty nodes in the subgraph rooted at `root_node`.

**Preconditions:**
- `root_node` is a valid node label
- `workspace_root` points to a valid workspace with manifest files
- `config_target`, when provided, is a valid `agent_config` target whose generated module is available (in runfiles or bazel-bin); when omitted, the agent configuration is selected by the `AGENT_CONFIG_TARGET` environment variable and then the `//agent_configs:default` convention (see `bazel_agent_config` Interface LLS)
- The environment provides an API key for the selected agent configuration (its pinned variable or AGENT_API_KEY)

**Postconditions:**
- Returns `(True, CleanResult)` on success (where `CleanResult` is a `ChangeResult`, `FeedbackResult`, or `NoChangeResult` from `dag_clean_logic`).
- Returns `(False, CleanResult)` on failure (where `CleanResult` is a `FailureResult` from `dag_clean_logic`).
  - Cleaning failure: a node's clean returned a `FailureResult`.
  - Termination limit exceeded: message cycle or non-clearing dirty state.
  - Feedback target outside the subgraph.
  - Graph contains a cycle (subgraph cannot be topologically ordered).
- On failure: the offending node's messages remain unchanged; previously cleaned nodes retain changes; processing halts.
- All output (changes and feedback) is delivered to the appropriate target nodes' message stores.
- A full agent transcript is written to a log file.

**Failure Handling:**
- All expected failures from the underlying DAG cleaning propagate as `(False, CleanResult)`.
- Logging continues regardless of success or failure (the log file is always written). The log file is created after component assembly; a failure during assembly (e.g., graph construction) propagates without a log file.
- Log output includes compact one-line event summaries to stdout (covering `tool_called`, `api_response`, `run_terminated`, `error` events) and a verbose full transcript to a log file; the transcript records each request's conversation state.
- Log file path is determined by (in priority order): 1) The `CLEANROOM_AGENT_LOG` environment variable (absolute path or a name relative to the log base directory), 2) `agent_loop.log` in the log base directory.
- The log base directory is the Bazel workspace directory (`BUILD_WORKSPACE_DIRECTORY`, else `BUILD_WORKING_DIRECTORY`) when present, otherwise the current working directory.

**HLS Justification:** "The client may request cleaning of a subgraph rooted at a target node."

### `inject_feedback`

```python
def inject_feedback(self, node_id: NodeId, workspace_root: str, messages: List[str]) -> CleaningResult
```

**Purpose:** Deliver feedback messages to a node's own pending message store, marking the node dirty for a subsequent cleaning pass.

**Preconditions:**
- `node_id` is a valid node label in the workspace
- `workspace_root` points to a valid workspace with manifest files
- `messages` is a list of feedback strings

**Postconditions:**
- Each message is added to the node's pending messages (the same store the DAG reads)
- A subsequent call to `run_dag` with this `node_id` (or any ancestor) will re-process the node as dirty
- Returns `(True, CleanResult)` on success (a `NoChangeResult` from `dag_clean_logic`).
- Returns `(False, CleanResult)` on failure (a `FailureResult` from `dag_clean_logic`) — the node does not exist in the graph.

**Failure Handling:**
- If the node does not exist in the graph, returns `(False, CleanResult)` (a `FailureResult`) without modifying any state.

**HLS Justification:** "Deliver feedback messages to a node's pending message store."


## Invariants

- The runner assembles all components internally; the client provides no component instances
- The runner owns the full lifecycle of all components it creates (graph storage, agent loop, DAG)
- The log file is always written, regardless of success or failure
- The runner does not expose component APIs; the interface is `run_dag` and `inject_feedback` only


## Non-Concerns

- **Component wiring strategy:** How the runner assembles (graph storage, agent loop, DAG) is specified in the implementation spec only; the interface contract specifies only the operational behavior.

