<!-- Dependencies (md files to read alongside this one):
  - dag-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
  - bazel_agent_config-low.md
  - sandbox-low.md
  - bazel_node_loader-low.md
  - agent_loop-low.md
-->

# Interface LLS: bazel_runner

## Data Types
```python
from typing import Protocol, Sequence, TypeAlias, Literal

from dag_clean_logic import FeedbackMessage
from bazel_node_loader import NodeLabel
from bazel_agent_config import ConfigTarget

CleaningResult: TypeAlias = Literal["success", "failure"]
ResultOutcome: TypeAlias = Literal["no_messages", "change", "feedback"] | None

class BazelRunner(Protocol):
    def run(self, root_label: NodeLabel, workspace_root: str,
            config_target: ConfigTarget | None = None) -> tuple[CleaningResult, ResultOutcome]: ...
    def inject_feedback(self, node_label: NodeLabel,
                        messages: Sequence[FeedbackMessage]) -> tuple[CleaningResult, ResultOutcome]: ...
```

**CleaningResult:** The outcome of a cleaning operation — `"success"` (all nodes in the subgraph cleaned; the `ResultOutcome` indicates which: `"no_messages"`, `"change"`, or `"feedback"`) or `"failure"` (processing halted due to a cleaning failure, termination limit exceeded, invalid feedback target, or graph cycle).

**ResultOutcome:** The sub-outcome within a success result — `"no_messages"` (no messages produced), `"change"` (change messages were produced), or `"feedback"` (feedback messages were produced).
## Term definitions

- **node** → the `NodeName` alias from dag_storage
- **pending message** → the `PendingMessage` alias from dag_storage
- **subgraph** → term definition from dag_storage: a target node (included) plus all nodes reachable through its direct and indirect dependencies
- **dirty** → term definition from dag_clean_logic: a state indicating a node requires cleaning; a node is dirty when it has pending messages or custom conditions hold
- **cleaning** → term definition from dag_clean_logic: the processing of a node which may produce zero or more messages for delivery
- **change message** → the `ChangeMessage` alias from dag_clean_logic
- **feedback message** → the `FeedbackMessage` alias from dag_clean_logic
- **result** → the `CleaningResult` alias
- **config target** → the `ConfigTarget` alias from bazel_agent_config
- **agent configuration** → the `AgentConfig` alias from bazel_agent_config
- **run** → the `run` term from agent_loop
- **step mode** → the `step mode` term from sandbox
- **manifest** → the `NodeManifest` type from bazel_node_loader

## Component-Provided Operations

### `run`

```python
def run(self, root_label: NodeLabel, workspace_root: str,
        config_target: ConfigTarget | None = None) -> tuple[CleaningResult, ResultOutcome]: ...
```

**Purpose:** Run a topological cleaning pass starting from a root node. Resolves the graph, loads nodes, applies agent configuration to each node's sandbox configuration, and executes cleaning topologically.

**Preconditions:** The root node is a valid node label. The workspace root points to a valid workspace with manifest files. When `config_target` is provided, it is a canonical main-repo Bazel label; when none is provided, the config target is selected by the environment (`AGENT_CONFIG_TARGET`) and then the `//agent_configs:default` convention. The graph topology does not change during the run.

**Postconditions:** Returns a `tuple[CleaningResult, ResultOutcome]` indicating the outcome:
- `("success", "no_messages")`: all nodes in the subgraph were cleaned; no messages produced.
- `("success", "change")`: all nodes in the subgraph were cleaned; change messages were produced and delivered to reverse dependencies.
- `("success", "feedback")`: all nodes in the subgraph were cleaned; feedback messages were produced and delivered to specific dependencies.
- `("failure", None)`: processing halted — the offending node's messages remain unchanged, previously cleaned nodes retain changes, and no further processing occurs.


The agent configuration is applied to each node's sandbox configuration: whether session-start reads are enabled and whether step mode is enabled.

**Failure Handling:** Returns `("failure", None)` when:
- A node's cleaning failed — the offending node's messages remain unchanged.
- A termination limit was exceeded (message cycle or non-clearing dirty state).
- Feedback targets a node outside the subgraph — feedback is delivered only within the subgraph.
- The graph contains a cycle (the subgraph cannot be topologically ordered).

Unexpected failures — assembly failures such as agent-configuration resolution failure or a missing manifest — are signaled as exceptions and are outside the value contract.

**Logging:** Provides compact one-line summaries of run events to standard output. Provides a verbose transcript to a log file whose path is determined by a configured environment variable or a default location (the Bazel workspace directory when running under Bazel, otherwise the current working directory). The transcript records each request's conversation state.

**HLS Justification:** Contract → Operations → cleaning pass; Contract → Guarantees → all guarantee statements; Contract → Unexpected failures.

### `inject_feedback`

```python
def inject_feedback(self, node_label: NodeLabel,
                    messages: Sequence[FeedbackMessage]) -> tuple[CleaningResult, ResultOutcome]: ...
```

**Purpose:** Inject feedback messages to a specific node's message store, marking the node dirty for a subsequent cleaning pass.

**Preconditions:** The node_label identifies a node that exists in the graph.

**Postconditions:** Adds each feedback message to the target node's pending messages. Returns `("success", "no_messages")` on success.

**Failure Handling:** Returns `("failure", None)` when the feedback targets a node that does not exist in the graph, leaving state unchanged.

**HLS Justification:** Contract → Operations → feedback injection; Contract → Guarantees → feedback injection behavior and failure on missing node.


## Invariants

- All output (changes and feedback) is delivered to the appropriate target nodes' message stores.
- Assembles its components internally; the client provides no component instances.
- Expected failures are provided as values (a result); unexpected failures are signaled as exceptions.
- The component exposes only the cleaning and feedback operations, not component APIs.

## Non-Concerns
- **Error message wording:** the exact wording of failure reasons is unspecified. — Bounded by the HLS non-concern.
- **Error handling details:** the exact mechanism for propagating errors between components is unspecified. — Bounded by the HLS guarantee on expected vs. unexpected failures; the component's internal error propagation is an implementation detail.
- **Graph construction details:** the exact algorithm for constructing the graph from manifests is unspecified. — Bounded by the HLS assumptions; the component assumes valid inputs and does not specify graph construction.
- **Logging implementation:** the exact format of one-line summaries and the transcript file format are unspecified; the transcript records each request's conversation state. — Bounded by the HLS Logging section; the content is specified but the format is not.
