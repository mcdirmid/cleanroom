<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Declare guide delivery capabilities as complete statements and name step advancement canonically
CODE_HASH: 3b35f5f52a2d
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# guide_delivery interface component

imports: tool_provider, file_alias, node_config

## Purpose

The guide_delivery interface component provides progressive step-by-step task guidance to keep agents focused on single milestones and prevent rushed execution.

Autonomous agents given monolithic instructions frequently attempt all objectives simultaneously, accumulating errors across intermediate steps and producing unanchored multi-file diffs that fail validation. The guide_delivery interface component breaks multi-phase workflows into discrete verifiable milestones, delivering instructional context incrementally and gating progression until prerequisite verification checks pass.

**Out of scope:** The guide_delivery interface component does not parse tool arguments, execute build commands, or manage host storage; these are handled by other components.

## Types and Behavior

An agent session's *guide delivery* delivers the instructions of a configured guide to an agent progressively.

A guide delivery can *parse* file content into a guide, and can record an *initial primer* presenting the first instructional content of a session.

A guide delivery can *advance step* given a boolean *verification passed* indicator and text *failure diagnostics*, delivering the instructional text of the next milestone when verification passes or retaining the current milestone and reporting failure diagnostics alongside verification failure instructions when verification fails.

A guide delivery exposes whether progressive *steps remain* to be completed, and exposes its configured guide.
