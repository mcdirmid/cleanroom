<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - guide_delivery.md
-->

# Implementation LLS: guide_delivery_impl

## Data Types
```python
from guide_delivery import GuideDelivery, GuideDeliveryConfig

class GuideDeliveryImpl(GuideDelivery):
    def __init__(self, config: GuideDeliveryConfig): ...
```

Constructed with the `guide_delivery` interface's `GuideDeliveryConfig` (see Interface LLS Data Types); it bundles no imported capabilities. Implements the `GuideDelivery` Protocol, providing all operations: `get_tool_definitions`, `get_session_start_reads`, `get_advance_output`, and `has_step_sections_remaining`.

## Behavioral Description

The implementation:
- Reads the declared guide's content at run start and splits it into its guide summary and step sections, following the guide format; the guide's content is available only through the step-delivery rules.
- In step mode, excludes the guide from the readable files: reads of the guide are rejected (the guide is not among the readable files the file machinery is configured with, per the composition) and the guide is never provided whole.
- Pre-injects the advance call providing the step-mode output (the guide summary and the ensure instruction) as a presented tool result at run start, before the agent's first turn.
- Maintains the step-section pointer: a passing verification advances it; a failing verification does not; the pointer gates which output the advance tool provides.
- Provides the advance tool's definition without the change-message argument while step sections remain; when verification passes with no step sections remaining, the definition includes it.
- In step mode, each advance output is composed at delivery time from the guide summary, the ensure instruction, and the pointer's current selection (a step section on a passing verification with sections remaining; the guide summary with the reason on a failing verification), with `supersedes` set — the output supersedes the previous advance output, so the guide summary is always visible and at most one step section is live.
- When step mode is disabled, provides no step-mode output: the guide is a readable file, provided whole at run start through the file machinery.
- Per-run state only: the step state (the guide, its split, and the step-section pointer); nothing persists across runs.

**HLS Justification:** Reads the declared guide's content at run start and splits it into its guide summary and step sections, following the guide format; the guide's content is available only through the step-delivery rules.

## Invariants

- In step mode, the guide is excluded from the run's readable files: reads of the guide are rejected and the guide is never provided whole
- A failing verification does not advance the step-section pointer
- No state persists across runs

## Non-Concerns

- **Step-delivery mechanism:** the exact mechanism for tracking the step-section pointer is unspecified.
- **Step presentation:** the exact wording of the ensure instruction and the formatting of the summary and step sections within an advance output are unspecified; the intent is conveyed by the step mode rules.
