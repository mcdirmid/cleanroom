<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: guide_delivery

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Optional
from dataclasses import dataclass
from tool_provider import ToolResult

GuideSummary: TypeAlias = str
StepIndex: TypeAlias = int
StepTitle: TypeAlias = str
StepContent: TypeAlias = str

@dataclass(frozen=True)
class StepSection:
    index: StepIndex
    title: StepTitle
    content: StepContent

@dataclass(frozen=True)
class TaskGuide:
    summary: GuideSummary
    sections: Sequence[StepSection]

StepDelivery: TypeAlias = ToolResult

class GuideDelivery(Protocol):
    def get_summary_delivery(self) -> StepDelivery: ...
    def advance_step(self, verification_passed: bool) -> Optional[StepDelivery]: ...
    def has_steps_remaining(self) -> bool: ...

class GuideDeliveryFactory(Protocol):
    def create_guide_delivery(self, guide: TaskGuide) -> GuideDelivery: ...
```

- `GuideSummary` → corresponds to guide summary.
- `StepIndex` → corresponds to index of a step section.
- `StepTitle` → corresponds to title of a step section.
- `StepContent` → corresponds to content of a step section.
- `StepSection` → corresponds to *step section*: a discrete milestone section within a *guide*.
- `TaskGuide` → corresponds to *guide*: structured instructional text containing a summary and sequential *step sections*.
- `StepDelivery` → corresponds to *step delivery*: a *tool result* delivering active guidance to an agent.
- `GuideDelivery` → corresponds to *guide delivery*: a service that delivers step-by-step instructions from a *guide*.
- `GuideDeliveryFactory` → corresponds to *guide delivery factory*: a provider that constructs *guide delivery* services for specific *guides*.

## Term definitions

- **guide** → the `TaskGuide` alias
- **step section** → the `StepSection` alias
- **step delivery** → the `StepDelivery` alias
- **guide delivery** → term definition: a service that delivers step-by-step instructions from a *guide*
- **guide delivery factory** → term definition: a provider that constructs *guide delivery* services for specific *guides*

## Component-Provided Operations

### `get_summary_delivery`

```python
def get_summary_delivery(self) -> StepDelivery: ...
```

**Purpose:** (GuideDelivery) Provides the initial guide summary as a startup step delivery.

**Preconditions:** None.

**Postconditions:**
- Returns a `StepDelivery` identifying the active guide and containing the guide summary.

**Failure Handling:** Always succeeds.

**HLS Justification:** "A *guide delivery* provides initial summary guidance identifying the active *guide* as a *step delivery* at session start."

### `advance_step`

```python
def advance_step(self, verification_passed: bool) -> Optional[StepDelivery]: ...
```

**Purpose:** (GuideDelivery) Advances to and delivers the next step section if verification passed, or retains the current step on failure.

**Preconditions:** None.

**Postconditions:**
- If `verification_passed` is `True` and steps remain, advances to and returns the next `StepDelivery`.
- If `verification_passed` is `False`, retains the current step section and returns `None`.

**Failure Handling:** Retaining the current step allows the agent to retry and correct verification errors.

**HLS Justification:** "A *guide delivery* advances to the next *step section* upon successful verification, producing a *step delivery*."

### `has_steps_remaining`

```python
def has_steps_remaining(self) -> bool: ...
```

**Purpose:** (GuideDelivery) Queries whether any progressive step sections remain to be completed.

**Preconditions:** None.

**Postconditions:**
- Returns `True` if further step sections remain; `False` if all steps are completed.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Delivers incremental task guidance to keep agents focused on single milestones and prevent rushed execution."

### `create_guide_delivery`

```python
def create_guide_delivery(self, guide: TaskGuide) -> GuideDelivery: ...
```

**Purpose:** (GuideDeliveryFactory) Creates a guide delivery instance initialized from a guide.

**Preconditions:** None.

**Postconditions:**
- Returns a `GuideDelivery` initialized with `guide`.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Creating a *guide delivery* through a *guide delivery factory* yields a *guide delivery* initialized from a *guide*."

## Invariants

- Step sections are delivered strictly sequentially.
- Failing verification retains the current step section without advancement.
