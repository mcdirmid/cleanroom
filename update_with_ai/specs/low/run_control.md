<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - virtual_file_name.md
  - dag_storage.md
  - dag_node_cleaner.md
  - change_summary_validator.md
-->

# Interface LLS: run_control

## Data Types
```python
from typing import Protocol, TypeAlias, Mapping, Optional
from dataclasses import dataclass
from tool_provider import Tool, ToolProvider, ToolFailure, TerminationOutcome
from virtual_file_name import VirtualFileName
from dag_storage import NodeId
from dag_node_cleaner import ChangeMessage, FeedbackMessage
from change_summary_validator import ChangeValidator

BlameTarget: TypeAlias = VirtualFileName
BlameTargetMapping: TypeAlias = Mapping[BlameTarget, NodeId]

@dataclass(frozen=True)
class RunControlConfig:
    blame_targets: Optional[BlameTargetMapping] = None
    change_summary_required: bool = True

class RunController(ToolProvider, Protocol):
    def get_advance_tool(self) -> Tool: ...
    def get_fail_tool(self) -> Tool: ...
    def get_blame_tool(self) -> Optional[Tool]: ...

class RunControlFactory(Protocol):
    def create_run_control(
        self,
        config: RunControlConfig,
        change_validator: Optional[ChangeValidator] = None,
    ) -> RunController: ...
```

- `BlameTarget` → corresponds to *blame target*: a source file addressed by a *virtual file name* owned by a dependency *node*.
- `BlameTargetMapping` → corresponds to blame target mappings.
- `RunControlConfig` → corresponds to run control configuration.
- `RunController` → corresponds to *run controller*: a *tool provider* providing an *advance tool*, a *fail tool*, and an optional *blame tool*.
- `RunControlFactory` → corresponds to *run control factory*: a provider that constructs *run controllers* configured for specific sessions.

## Term definitions

- **blame target** → the `BlameTarget` alias
- **advance tool** → term definition: a *tool* (returned by `get_advance_tool`) that verifies session state and produces a *termination outcome*
- **fail tool** → term definition: a *tool* (returned by `get_fail_tool`) that terminates an agent run in failure
- **blame tool** → term definition: a *tool* (returned by `get_blame_tool`) that attributes incomplete tasks to dependency *nodes* and routes *feedback messages*
- **run controller** → term definition: a *tool provider* providing an *advance tool*, a *fail tool*, and an optional *blame tool*
- **run control factory** → term definition: a provider that constructs *run controllers* configured for specific sessions

## Component-Provided Operations

### `get_advance_tool`

```python
def get_advance_tool(self) -> Tool: ...
```

**Purpose:** (RunController) Retrieves the advance verification and completion tool instance.

**Preconditions:** None.

**Postconditions:**
- Returns a `Tool` that executes verification, checks change summaries on write, and emits a `TerminationOutcome` carrying a `ChangeMessage` on success.

**Failure Handling:** Verification failure produces a `ToolFailure` with feedback.

**HLS Justification:** "An *advance tool* is a *tool* that verifies session state, validates change summaries, and produces a *termination outcome* on success."

### `get_fail_tool`

```python
def get_fail_tool(self) -> Tool: ...
```

**Purpose:** (RunController) Retrieves the explicit failure termination tool instance.

**Preconditions:** None.

**Postconditions:**
- Returns a `Tool` that terminates the agent run with a failure `TerminationOutcome`.

**Failure Handling:** Always succeeds.

**HLS Justification:** "A *fail tool* is a *tool* that terminates an agent run in failure."

### `get_blame_tool`

```python
def get_blame_tool(self) -> Optional[Tool]: ...
```

**Purpose:** (RunController) Retrieves the blame feedback tool instance when blame targets are configured.

**Preconditions:** None.

**Postconditions:**
- Returns a `Tool` if blame targets are configured, emitting a `TerminationOutcome` carrying a `FeedbackMessage` addressed to the owning dependency node.
- Returns `None` if no blame targets are configured.

**Failure Handling:** Invalid blame targets produce a `ToolFailure` listing valid blame targets.

**HLS Justification:** "A *blame tool* is a *tool* that attributes incomplete tasks to dependency *nodes* and routes *feedback messages*."

### `create_run_control`

```python
def create_run_control(
    self,
    config: RunControlConfig,
    change_validator: Optional[ChangeValidator] = None,
) -> RunController: ...
```

**Purpose:** (RunControlFactory) Creates a run controller instance configured with verification checks and blame targets.

**Preconditions:** None.

**Postconditions:**
- Returns a `RunController` configured with `config`, `verification_fn`, and `workspace_dirty_check_fn`.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Creating a *run controller* through a *run control factory* yields a *run controller* configured with verification checks and *blame targets*."

## Invariants

- Advance produces a terminal outcome only when all verification checks pass.
- Blame targets are validated strictly against configured dependency node mappings.
