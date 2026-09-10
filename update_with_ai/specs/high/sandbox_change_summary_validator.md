# sandbox_change_summary_validator interface component

imports: sandbox_run_control, file_alias

## Purpose

The sandbox_change_summary_validator interface component enforces change summary accuracy and conciseness against actual workspace file modifications, preventing inaccurate completion claims.

Language models often write change descriptions that do not match actual modifications, fail to describe altered files, or write excessively verbose change essays. The sandbox_change_summary_validator interface component verifies claimed changes against net-modified files, rejects net-unchanged claims, and bounds summary length within configured limits.

**Out of scope:** The sandbox_change_summary_validator interface component does not orchestrate agent turns, apply edits to disk, or format model prompts; these are handled by other components.

## Types and Behavior

A *diff summary* is a formatted representation of line changes across modified files. A *net change* is an observable difference between a file's initial content and its current content.

The *change summary validator* is an agent session service that is a verification check.

The change summary validator:

- Verifies that a change summary describes all net changes across read-write files.

- Rejects a change summary that claims changes for files with no net change.

- Produces a diff summary of modified files.

- Rejects a change summary exceeding configured length bounds, providing actionable shortening guidance.
