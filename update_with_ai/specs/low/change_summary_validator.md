<!-- Dependencies (md files to read alongside this one):
  - virtual_file_name.md
-->

# Interface LLS: change_summary_validator

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Optional
from dataclasses import dataclass
from virtual_file_name import VirtualFileName

ChangeSummary: TypeAlias = str
DiffSummary: TypeAlias = str
FileContent: TypeAlias = str
ValidationFeedback: TypeAlias = str

@dataclass(frozen=True)
class NetChange:
    file_name: VirtualFileName
    initial_content: FileContent
    current_content: FileContent

class ChangeValidator(Protocol):
    def validate_change_summary(self, summary: ChangeSummary, net_changes: Sequence[NetChange]) -> Optional[ValidationFeedback]: ...
    def compute_diff_summary(self, net_changes: Sequence[NetChange]) -> DiffSummary: ...
```

- `ChangeSummary` → corresponds to *change summary*: a description of modifications made to workspace files.
- `DiffSummary` → corresponds to *diff summary*: a formatted representation of line changes across modified files.
- `FileContent` → corresponds to file content string.
- `ValidationFeedback` → corresponds to validation feedback error string.
- `NetChange` → corresponds to *net change*: an observable difference between a file's initial content and its current content.
- `ChangeValidator` → corresponds to *change validator*: a service that verifies *change summaries* against net file modifications.

## Term definitions

- **change summary** → the `ChangeSummary` alias
- **diff summary** → the `DiffSummary` alias
- **net change** → the `NetChange` alias
- **change validator** → term definition: a service that verifies *change summaries* against net file modifications

## Component-Provided Operations

### `validate_change_summary`

```python
def validate_change_summary(self, summary: ChangeSummary, net_changes: Sequence[NetChange]) -> Optional[ValidationFeedback]: ...
```

**Purpose:** (ChangeValidator) Validates that a change summary accurately describes all net-changed files and does not claim changes for net-unchanged files.

**Preconditions:** None.

**Postconditions:**
- Returns `None` if validation passes.
- Returns a corrective feedback error string if summary is inaccurate or exceeds length bounds.

**Failure Handling:** Discrepancies return actionable feedback strings for agent self-correction.

**HLS Justification:** "A *change validator* verifies that a *change summary* describes all *net changes* across workspace files."

### `compute_diff_summary`

```python
def compute_diff_summary(self, net_changes: Sequence[NetChange]) -> DiffSummary: ...
```

**Purpose:** (ChangeValidator) Produces a formatted line-by-line diff representation across modified files.

**Preconditions:** None.

**Postconditions:**
- Returns a truncated `DiffSummary` representing line changes.

**Failure Handling:** Always succeeds.

**HLS Justification:** "A *change validator* produces a *diff summary* of modified files."

## Invariants

- Net-unchanged files written back to initial content are rejected if claimed as changes.
- Diff outputs are bounded by configured character limits.
