<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-12T21:14:00Z
CHANGE: dynamic directory scope resolution for workspace commissioning without hardcoded defaults
CODE_HASH: 167fdb531f63
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# workspace_tool interface component

imports: agent_session, cleanroom_files_ext

## Purpose

The workspace_tool interface component defines operational contracts and execution facilities for running cleanroom role workspace command-line subcommands including work discovery, target submission, failure attribution, statement test coverage, and workspace lifecycle management.

Autonomous subagents executing inside isolated Cleanroom role workspaces rely on a unified suite of bin utilities to inspect work queues, submit compliant changes, blame defects, and report diagnostics. Without a consistent and declarative CLI runner interface, command handling logic becomes fragmented across entrypoints, leading to inconsistent error reporting, missing dirty state synchronization, and uncontrolled execution across workspace boundaries. The workspace_tool interface component defines structured command execution contracts and result formulations for role workspaces.

**Out of scope:** The workspace_tool interface component does not directly implement filesystem mutation or build graph evaluation; these are handled by other components.

**Delegated:** Execution phase context boundaries are delegated to agent_session. Cleanroom log file naming conventions are delegated to cleanroom_files_ext.

## Types and Behavior

An agent session's *workspace tool runner* provides command dispatch and execution for cleanroom role workspaces.

The workspace tool runner dispatches and executes role commands matching an argument sequence, returning an integer exit code.

The workspace tool runner evaluates ready tasks for the active role scope through the work manager, bounding presented ready items by configured or requested batch sizes, providing diagnostic advice when additional ready units remain, and formatting structured console reports carrying target paths, the companion specification contracts to read, and actionable next steps.

The workspace tool runner submits target files, evaluating verification checks and rejecting failing targets prior to submission unless bypassed, enforcing producer change summaries, attesting auditor stamps, appending submission records to the cleanroom log, and clearing the pending target buffers on success.

The workspace tool runner attributes defect blame or failure diagnostics to culprit targets, propagating feedback, appending feedback records to the cleanroom log, and clearing the pending target buffers on success.

The workspace tool runner evaluates statement test coverage across implementation and test pairs against target thresholds.

The workspace tool runner evaluates static verification checks, linters, and type checking for specified or pending target files, regenerating a missing target file from its starter template before verification for roles that declare source patterns and upstream dependencies.

The workspace tool runner commissions isolated role workspaces for specified roles or across all declared roles within a directory scope, dynamically discovering or requiring the directory scope without hardcoded defaults, and refreshes system configuration files, bin utilities, and companion guides across the active role workspaces.
