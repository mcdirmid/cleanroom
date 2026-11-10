# cli_tool interface component

imports: session, autofab_files_ext

## Purpose

The cli_tool interface component defines operational contracts and execution facilities for running Autofab role workspace command-line subcommands including work discovery, target submission, failure attribution, statement test coverage, and workspace lifecycle management.

Autonomous subagents executing inside isolated Autofab role workspaces rely on a unified suite of bin utilities to inspect work queues, submit compliant changes, blame defects, and report diagnostics. Without a consistent and declarative CLI runner interface, command handling logic becomes fragmented across entrypoints, leading to inconsistent error reporting, missing dirty state synchronization, and uncontrolled execution across workspace boundaries. The cli_tool interface component defines structured command execution contracts and result formulations for role workspaces.

**Out of scope:** The cli_tool interface component does not directly implement filesystem mutation or build graph evaluation; these are handled by other components.

**Delegated:** Execution phase context boundaries are delegated to agent_session. Autofab event log file naming conventions are delegated to autofab_files_ext.

## Types and Behavior

An agent session's *workspace tool runner* provides command dispatch and execution for Autofab role workspaces.

The workspace tool runner dispatches and executes role commands matching an argument sequence, returning an integer exit code.

The workspace tool runner evaluates ready tasks for the active role scope through the work manager, presenting the bounded batch of ready items without extraneous remaining or blocked queue details, throttling unacted feedback reasons exceeding maximum character limits when configured, and formatting structured console reports carrying target paths, the companion specification contracts to read, and actionable next steps.

The workspace tool runner submits target files, evaluating verification checks, committing staged blame feedback to culprits when staged blame exists for a failing target, disallowing manual submission without preceding blame in auditor roles, rejecting failing targets without staged blame unless bypassed, enforcing producer change summaries, attesting auditor stamps, appending submission records to the event log, and clearing the pending target buffers on success.

The workspace tool runner attributes defect blame or failure diagnostics to culprit targets, supporting structured blame options (--slug, --viol, --facet, --lines, --witness) and validating structured blame when the structured blame experiment is active, staging critique feedback for subsequent commit upon submit, and notifying the caller to stage additional blame or commit staged blame.

The workspace tool runner rejects active feedback delivered to an unmodified target file, enforcing that the target file has not been modified since receiving feedback, immediately removing the feedback comment block from the target file header, recording the contest explanation into the workspace blame buffer and event log, and clearing the target from pending work buffers on success.

The workspace tool runner evaluates statement test coverage across implementation and test pairs against target thresholds.

The workspace tool runner restores modified workspace files or the entire workspace tree from git snapshot points, and creates git commit checkpoints of active workspace state.

The workspace tool runner evaluates static verification checks, linters, and type checking for specified or pending target files, regenerating a missing target file from its starter template before verification for roles that declare source patterns and upstream dependencies.

The workspace tool runner commissions isolated role workspaces for specified roles or across all declared roles within a directory scope, dynamically discovering or requiring the directory scope without hardcoded defaults, supporting resetting stale work buffers and stamping model execution profiles, and refreshes system configuration files, bin utilities, and companion guides across the active role workspaces.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-09T19:50:00Z
CHANGE: Omit redundant feedback repetition on check_files
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
