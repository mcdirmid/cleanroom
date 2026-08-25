<!-- Dependencies (md files to read alongside this one):
  - bazel_runner-low.md
  - bazel_graph_storage-low.md
  - bazel_node_loader-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
  - dag-low.md
  - agent_loop-low.md
  - sandbox-low.md
  - bazel_agent_config-low.md
-->

# Implementation LLS: bazel_runner_impl

## Data Types
```python
from typing import Sequence

from bazel_runner import CleaningResult, ResultOutcome, BazelRunner
from dag_clean_logic import FeedbackMessage
from bazel_node_loader import NodeLabel
from bazel_agent_config import ConfigTarget

class BazelRunnerImpl(BazelRunner):
    def run(self, root_label: NodeLabel, workspace_root: str,
            config_target: ConfigTarget | None = None) -> tuple[CleaningResult, ResultOutcome]: ...
    def inject_feedback(self, node_label: NodeLabel,
                        messages: Sequence[FeedbackMessage]) -> tuple[CleaningResult, ResultOutcome]: ...
```

## Term definitions

- **node** → the `NodeName` alias from dag_storage
- **pending message** → the `PendingMessage` alias from dag_storage
- **subgraph** → term definition from dag_storage
- **cleaning** → term definition from dag_clean_logic
- **feedback message** → the `FeedbackMessage` alias from dag_clean_logic
- **agent configuration** → the `AgentConfig` alias from bazel_agent_config
- **config target** → the `ConfigTarget` alias from bazel_agent_config
- **API key** → the `ApiCredential` alias from bazel_agent_config
- **result** → the `CleaningResult` alias from bazel_runner

## Behavioral Description

#### `run`
```python
def run(self, root_label: NodeLabel, workspace_root: str,
        config_target: ConfigTarget | None = None) -> tuple[CleaningResult, ResultOutcome]: ...
```
**Purpose:** Run a topological cleaning pass starting from a root node. Assembles all components internally, resolves the agent configuration from the config target, loads the graph, and cleans every dirty node in the subgraph rooted at the target node, routing change messages to reverse dependencies and feedback messages to specific dependencies.

**Preconditions:** The root node is a valid node label. The workspace root points to a valid workspace with manifest files. When `config_target` is provided, it is a canonical main-repo Bazel label; when none is provided, the config target is selected by the environment and then the `//agent_configs:default` convention. The graph topology does not change during the run.

**Postconditions:** Returns a `tuple[CleaningResult, ResultOutcome]` indicating the outcome:
- `("success", "no_messages")`: all nodes in the subgraph were cleaned; no messages produced.
- `("success", "change")`: all nodes in the subgraph were cleaned; change messages were produced and delivered to reverse dependencies.
- `("success", "feedback")`: all nodes in the subgraph were cleaned; feedback messages were produced and delivered to specific dependencies.
- `("failure", None)`: processing halted — the offending node's messages remain unchanged, previously cleaned nodes retain changes, and no further processing occurs.

**Failure Handling:** Returns `("failure", None)` when:
- A node's cleaning fails — the offending node's messages remain unchanged.
- A termination limit was exceeded (message cycle or non-clearing dirty state).
- Feedback targets a node outside the subgraph — feedback is delivered only within the subgraph.
- The graph contains a cycle (the subgraph cannot be topologically ordered).

Unexpected failures — configuration failures (missing config target module, missing API key) signaled by `bazel_agent_config`, a missing manifest, or log-file failure — are signaled as exceptions and are outside the value contract. Configuration failures are detected and signaled before the cleaning pass starts. The log file is always written, regardless of the result.

**HLS Justification:** Contract → Operations → "Assembles the cleanroom system internally ... and runs a topological cleaning pass over the target node's subgraph"; Contract → Guarantees → all guarantee statements; Contract → Unexpected failures.

#### `inject_feedback`
```python
def inject_feedback(self, node_label: NodeLabel,
                    messages: Sequence[FeedbackMessage]) -> tuple[CleaningResult, ResultOutcome]: ...
```

**Purpose:** Inject feedback messages to a specific node's message store, marking the node dirty for a subsequent cleaning pass.

**Preconditions:** The node exists in the graph.

**Postconditions:** Adds each feedback message to the target node's pending messages. Returns `("success", "no_messages")` on success. The graph constructed for injection is separate from the graph used by a cleaning pass.

**Failure Handling:** Returns `("failure", None)` when the feedback targets a node that does not exist in the graph, leaving state unchanged.

**HLS Justification:** Contract → Guarantees → [state] Feedback injection constructs a graph separately from the graph used by a cleaning pass.

## Invariants

- All components are created internally per call; no persistent state is held across calls.
- The log file is always written, regardless of the result.
- Feedback injection constructs a graph separately from the graph used by a cleaning pass.

## Non-Concerns

- **Agent configuration values (model, URL, limits):** Declared as agent_config Bazel targets, not specified here. — Bounded by the HLS non-concern; the component uses whatever values the selected config target provides.
- **API keys:** Resolved from the environment by the bazel_agent_config component; never stored in code, Bazel, or version control. — Bounded by the HLS non-concern.
