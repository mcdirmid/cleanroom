# commands interface component

imports: session, autofab_files_ext

## Purpose

The commands interface component defines the operational contracts and execution workflows for autofab role workspace subcommands, including work discovery, file verification, change submission, defect blame attribution, statement coverage analysis, workspace commissioning, and system synchronization.

Autonomous subagents executing inside isolated role workspaces require standard handlers to execute domain operations without entangling argument parsing with business workflows. The commands interface component defines structured command execution methods and exit codes for all workspace operations.

**Out of scope:** The commands interface component does not parse command-line argument strings; argument parsing and CLI dispatch are handled by cli_tool.

**Delegated:** Execution phase context boundaries are delegated to agent_session. Event log file naming conventions are delegated to autofab_files_ext.

## Types and Behavior

An agent session's *workspace command handler* provides domain command execution for autofab role workspaces.

The command handler:

- Evaluates dirty work in the local role workspace, presenting bounded batches of ready targets without extraneous remaining or blocked queue details, throttling unacted feedback reasons exceeding maximum character limits when configured, and returning an integer exit code.

- Executes role-specific verification checks, linters, and type checking for specified or pending target files, regenerating missing target files from starter templates before verification for roles with source patterns and upstream dependencies, surfacing unacted feedback warnings when targets carrying unaddressed feedback pass static verification, and returning the verification exit code.

- Submits target files to the canonical main repository, enforcing that modified target files have been checked via check_files since their latest modifications unless bypassed, committing staged blame feedback to culprit metadata and dirtying culprits when staged blame exists for a failing target, disallowing manual submission without preceding blame in auditor roles, rejecting failing targets without staged blame unless bypassed, enforcing producer change summaries, attesting auditor stamps, appending submission records to the event log both in the canonical repository and the local role workspace, and clearing the target from pending work buffers on success.

- Attributes defect blame or failure diagnostics to culprit targets, enforcing that any modified workspace target files have been checked via check_files since their latest modifications, validating caller role feedback delivery permissions against both direct feedback role dependencies (`feedback_role_deps`) and cross-unit star feedback role dependencies (`star_feedback_role_deps`), validating the structured blame tuple (specification slug grounding in low-level specifications, violation code taxonomy, noun phrase facet constraints, and zero-entropy symbol embargo) when the structured blame experiment is active, staging single-paragraph critique feedback for subsequent submission commit, recording blamed culprit targets into the workspace blame buffer, and notifying the caller to stage additional blame or commit staged blame via submit.

- Rejects active feedback delivered to an unmodified target file, enforcing that the target file has not been modified since receiving feedback, immediately removing the feedback comment block from the target file header, recording the contest explanation into the workspace blame buffer and event log, and clearing the target from pending work buffers on success.

- Marks targets failed with dirty status, enforcing that modified target files have been checked via check_files since their latest modifications, and clearing the target from pending work buffers on success.

- Evaluates statement test coverage across implementation and test pairs against target thresholds, formatting span diagnostics and returning an integer exit code.

- Commissions isolated role workspaces for specified roles or across all declared roles within a directory scope, dynamically discovering or requiring the directory scope without hardcoded defaults, supporting resetting stale work buffers and stamping model execution profiles.

- Refreshes system configuration files, bin utilities, and companion guides across active role workspaces.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-20T21:07:00Z
LAST_CHANGED: 2026-11-07T10:20:00Z
CHANGE: Specify reject command and stage-and-commit blame submission workflow with auditor blame requirement
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
