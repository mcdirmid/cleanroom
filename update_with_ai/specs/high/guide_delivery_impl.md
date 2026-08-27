# guide_delivery_impl

fulfills: guide_delivery
imports: tool_provider (presented tool result)
terms (from tool_provider): presented tool result, tool result
terms (from guide_delivery): guide, guide summary, step section, step mode

## Deltas

- Reads the declared guide's content at run start and splits it into its guide summary and step sections, following the guide format; the guide's content is available only through the step-delivery rules.
- In step mode, excludes the guide from the readable files: reads of the guide are rejected and the guide is never provided whole.
- Pre-injects the advance call providing the step-mode output (the guide summary and the ensure instruction) as a presented tool result at run start, before the agent's first turn.
- Maintains the step-section pointer: a passing verification advances it; a failing verification does not; the pointer gates which output the advance tool provides.
- Provides the advance tool's definition without the change-message argument while step sections remain; when verification passes with no step sections remaining, the definition includes it.
- [ordering] In step mode, each advance output is composed at delivery time from the guide summary, the ensure instruction, and the pointer's current selection (a step section or the failure reason).
- [state] Per-run state only: the step state (the guide, its split, and the step-section pointer); nothing persists across runs.

## Non-concerns

- Step-delivery mechanism: the exact mechanism for tracking the step-section pointer is unspecified.
