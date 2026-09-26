# sandbox_guide_delivery interface component

imports: tool_provider, agent_file_alias, agent_node_config

## Purpose

The sandbox_guide_delivery interface component provides progressive step-by-step task guidance to keep agents focused on single milestones and prevent rushed execution.

Autonomous agents given monolithic instructions frequently attempt all objectives simultaneously, accumulating errors across intermediate steps and producing unanchored multi-file diffs that fail validation. The sandbox_guide_delivery interface component breaks multi-phase workflows into discrete verifiable milestones, delivering instructional context incrementally and gating progression until prerequisite verification checks pass.

**Out of scope:** The sandbox_guide_delivery interface component does not parse tool arguments, execute build commands, or manage host storage; these are handled by other components.

## Types and Behavior

The *guide delivery* is an agent session service configured with a guide that delivers instructions to an agent progressively.

A guide delivery:

- Can *parse* file content into a guide.

- Can record an *initial primer*.

- Can *advance step* with a boolean *verification passed* indicator and text *failure diagnostics*, delivering instructional text when verification passes, or retaining the current milestone and reporting failure diagnostics alongside verification failure instructions when verification fails.

- Exposes whether progressive *steps remain* to be completed, and exposes its configured guide.
