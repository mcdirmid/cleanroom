<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: guide_delivery

## Data Types
```python
from dataclasses import dataclass
from typing import Protocol, TypeAlias
from tool_provider import PresentedToolResult, ToolDefinition

@dataclass
class GuideDeliveryConfig:
    guide: str | None
    step_sections_enabled: bool

class GuideDelivery(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def get_session_start_reads(self) -> list[PresentedToolResult]: ...
    def get_advance_output(self, verification_passed: bool, failure_reason: str | None = None) -> PresentedToolResult | None: ...
    def has_step_sections_remaining(self) -> bool: ...
```

`GuideDeliveryConfig` is the client-supplied configuration for the guide's delivery: the guide (the declared guide file's location — its full filesystem path, resolved by the composer from the guide's virtual name via the file mappings; `None` when no guide is declared) and whether step mode is enabled.
## Term definitions

- **guide** → term definition: the declared guide input — a readable file the node declares separately from its dependencies, at most one per run, in the guide format: its first line is `# Guide: <title>` and its first `##` heading is `## Summary`
- **guide summary** → term definition: the guide's first part — the content from the guide's first line through the end of its `## Summary` section
- **step section** → term definition: a checklist section of the guide — a part of the guide after the guide summary, delimited by `## <name>` headings (excluding any `## Lint checks` section, which is skipped in step mode), delivered after an advance that passed verification
- **step mode** → term definition: a configuration in which the guide is not readable and its content reaches the agent only through the advance operation: the guide summary at run start, then the step sections one at a time after successful advances; in step mode the guide is not presented among the readable files (file lists shown to the agent do not name the guide), and a readable file that is not the guide is unaffected by step mode
- **presented tool result** → the `PresentedToolResult` type from tool_provider
- **tool result** → the `ToolResult` type from tool_provider
- **tool definition** → the `ToolDefinition` alias from tool_provider

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the advance tool's definition — the tool through which the guide's step-mode delivery reaches the agent.

**Preconditions:** None.

**Postconditions:**
- Returns a list containing exactly the advance tool's definition; the advance tool is always included
- The advance tool's parameters follow the step state: in step mode, the change-message argument is omitted while step sections remain and is included when verification passes with no step sections remaining; when step mode is disabled, it is always included

**Failure Handling:** No failure conditions.

**HLS Justification:** "Provide the advance's step-mode output (a presented tool result)": the advance tool is the vehicle through which the step-mode output is delivered, and its parameters reflect the step state.


### `get_session_start_reads`

```python
def get_session_start_reads(self) -> list[PresentedToolResult]
```

**Purpose:** Provide the guide's presentation at run start: in step mode, the pre-injected advance call carrying the guide summary and the ensure instruction, before the agent's first turn.

**Preconditions:** None.

**Postconditions:**
- In step mode: returns one `PresentedToolResult` pairing the advance call with its step-mode output — the guide summary and the ensure instruction — with `supersedes` set
- When step mode is disabled: returns an empty list (the guide is a readable file, provided whole at run start through the file machinery)
- Requesting the guide's presentation changes no guide_delivery state

**Failure Handling:** Always succeeds; filesystem errors reading the guide are unhandled.

**HLS Justification:** "Provide the guide's presentation at run start."


### `get_advance_output`

```python
def get_advance_output(self, verification_passed: bool, failure_reason: str | None = None) -> PresentedToolResult | None
```

**Purpose:** Provide the advance's step-mode output: the next step section on a passing verification while sections remain, or the restated guide summary with the reason on a failing verification.

**Preconditions:**
- Step mode is enabled and a guide is configured
- On a passing verification: step sections remain (a passing verification with no sections remaining proceeds to the termination machinery, never to step delivery)

**Postconditions:**
- On a failing verification: returns the restated guide summary with the reason verification failed as a `PresentedToolResult` with `supersedes` set; the next step section is not delivered
- On a passing verification with step sections remaining: returns the next step section as a `PresentedToolResult` with `supersedes` set, composed from the guide summary, the ensure instruction, and the step-section pointer's current selection
- When step mode is disabled, or verification passed with no step sections remaining: returns `None`

**Failure Handling:** No failure conditions; the preconditions are caller obligations (per the step mode rules, a failing verification prevents progressing to the next section).

**HLS Justification:** "Provide the advance's step-mode output (a presented tool result)."


### `has_step_sections_remaining`

```python
def has_step_sections_remaining(self) -> bool
```

**Purpose:** Query whether step sections remain: whether the next advance that passes verification would deliver a step section rather than proceed to the termination machinery.

**Preconditions:** None.

**Postconditions:**
- Returns `True` when step mode is enabled, a guide is configured, and the step-section pointer has not reached the end of the guide's step sections (excluding `## Lint checks`); `False` otherwise (step mode disabled, no guide, or all sections delivered)
- Requesting changes no guide_delivery state

**Failure Handling:** Always succeeds.

**HLS Justification:** "Query whether step sections remain."

## Invariants

- In step mode, the guide's content reaches the agent only through the advance operation's outputs
- In step mode, the guide is not presented among the readable files: file lists shown to the agent do not name the guide
- In step mode, the `## Lint checks` section is skipped and never delivered as a step section
- A failing verification prevents progressing to the next section (the step-section pointer does not advance on a failing verification)
- Termination cannot occur until all guide sections are delivered and verification passes
- In step mode, the guide summary is always visible: each advance output supersedes the previous advance output, so at most one step section is live
- A readable file that is not the guide is unaffected by step mode
- No state persists across runs

## Non-Concerns

- **Step section size:** step sections are parts of the guide file, which is assumed reasonably sized; no separate size bound is introduced for step sections.
- **Guide parsing:** the exact rules for splitting the guide into its guide summary and step sections follow the guide format; section content is delivered in order without interpretation.
- **Step presentation:** the exact wording of the ensure instruction and the formatting of the summary and step sections within an advance output are unspecified; the intent is conveyed by the step mode rules.
- **Step-delivery mechanism:** the exact mechanism for tracking the step-section pointer is unspecified.
