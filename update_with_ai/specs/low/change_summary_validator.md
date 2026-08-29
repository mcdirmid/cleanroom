<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: change_summary_validator

## Data Types
```python
from typing import Any, Dict, List, Optional, Protocol, TypeAlias
from tool_provider import ToolFailure

ClaimedChanges: TypeAlias = Optional[List[Dict[str, str]]]
ValidationOutcome: TypeAlias = Optional[ToolFailure[str]]

class ChangeSummaryValidator(Protocol):
    def compute_diff_summary(self) -> str: ...
    def get_effective_changes(self) -> List[str]: ...
    def validate_change_summaries(self, changes: ClaimedChanges) -> ValidationOutcome: ...
    def reset_validator_state(self) -> None: ...
```

## Term definitions

- **change validation** → term definition: checking that claimed changed files match actual modified files whose current content differs from their initial run-start content
- **diff summary** → term definition: a formatted representation of line-by-line file changes across modified files
- **net change** → term definition: an effective modification where a file's current content differs from its initial content at run start; a file written back to its initial content is net-unchanged

## Component-Provided Operations

### `compute_diff_summary`

```python
def compute_diff_summary(self) -> str
```

**Purpose:** Compute a unified diff summary across modified files up to the configured limit.

**Preconditions:** None.

**Postconditions:**
- Returns formatted diff string showing line changes.

**Failure Handling:** None.

**HLS Justification:** "Produces a formatted diff summary truncated at the configured diff size limit."

### `get_effective_changes`

```python
def get_effective_changes(self) -> List[str]
```

**Purpose:** Return list of paths whose current content differs from their run-start snapshot.

**Preconditions:** None.

**Postconditions:**
- Returns list of net-changed file virtual names.

**Failure Handling:** None.

**HLS Justification:** "A write that nets out to no change is detected as net-unchanged."

### `validate_change_summaries`

```python
def validate_change_summaries(self, changes: ClaimedChanges) -> ValidationOutcome
```

**Purpose:** Validate claimed change summaries against effective changes, soft bounds, and hard bounds.

**Preconditions:** None.

**Postconditions:**
- Returns `None` if valid, or `ToolFailure[str]` with guidance if invalid.

**Failure Handling:** Returns ToolFailure when invalid.

**HLS Justification:** "Enforces the soft length bound and hard length bound with a grace count."

### `reset_validator_state`

```python
def reset_validator_state(self) -> None
```

**Purpose:** Reset per-run validation state.

**Preconditions:** None.

**Postconditions:**
- Resets rejection and grace counters.

**Failure Handling:** None.

**HLS Justification:** "State is per-run only."

## Invariants

- A net-unchanged file is never accepted in claimed changes.
- Summaries exceeding bounds receive shortening guidance up to the grace count.
