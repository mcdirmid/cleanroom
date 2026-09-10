# sandbox_guide_delivery interface component

imports: tool_provider, file_alias

## Purpose

The sandbox_guide_delivery interface component provides progressive step-by-step task guidance to keep agents focused on single milestones and prevent rushed execution.

Autonomous agents given monolithic instructions frequently attempt all objectives simultaneously, accumulating errors across intermediate steps and producing unanchored multi-file diffs that fail validation. The sandbox_guide_delivery interface component breaks multi-phase workflows into discrete verifiable milestones, delivering instructional context incrementally and gating progression until prerequisite verification checks pass.

**Out of scope:** The sandbox_guide_delivery interface component does not parse tool arguments, execute build commands, or manage host storage; these are handled by other components.

## Types and Behavior

A *guide* provides structured instructional text containing a *summary* and sequential *step sections*. A *step section* is a milestone section within a guide having an *index*, a *title*, and *content*. A guide delivery can *parse* file content into a guide, extracting the summary from content preceding the first section heading, and creating sequential step sections for subsequent level-two headings while excluding sections whose title begins with `Lint checks`.

A *guide delivery* is an agent session service configured with a guide that delivers instructions to an agent progressively.

A guide delivery:

- Can *advance step* with a boolean *verification passed* indicator and text *failure diagnostics*, delivering the guide summary alone on initial delivery, presenting the guide summary above each step section on subsequent steps when verification passes, or retaining the current step section and reporting the failure diagnostics when verification fails.

- Exposes whether progressive *steps remain* to be completed.
