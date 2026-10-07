<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T23:30:00Z
CHANGE: new file
CODE_HASH: 7a8b9c1d2e3f
-->

# workspace_tool interface component

imports: agent_session, workspace_work

## Purpose

The workspace_tool interface component defines operational contracts and execution facilities for running cleanroom role workspace command-line subcommands including work discovery, target submission, failure attribution, statement test coverage, and workspace lifecycle management.

Autonomous subagents executing inside isolated Cleanroom role workspaces rely on a unified suite of bin utilities to inspect work queues, submit compliant changes, blame defects, and report diagnostics. Without a consistent and declarative CLI runner interface, command handling logic becomes fragmented across entrypoints, leading to inconsistent error reporting, missing dirty state synchronization, and uncontrolled execution across workspace boundaries. The workspace_tool interface component defines structured command execution contracts and result formulations for role workspaces.

**Out of scope:** The workspace_tool interface component does not directly implement filesystem mutation or Bazel build graph evaluation; these are handled by other components.

**Delegated:** Execution phase context boundaries are delegated to agent_session; work queue computation, pending buffer management, and dirtiness evaluation are delegated to workspace_work.

## Types and Behavior

A session's *workspace tool runner* provides command dispatch and execution for cleanroom role workspaces.

The workspace tool runner:

- Dispatches and executes role commands matching an argument sequence, returning an integer exit code.

- Evaluates ready tasks for the active role scope via the work manager, formatting structured console reports with target paths, companion specification contracts to read, and actionable next steps.

- Submits target files, enforcing producer change summaries, attesting auditor stamps, and clearing pending target buffers upon success.

- Attributes defect blame or failure diagnostics to culprit targets, propagating feedback and clearing pending target buffers upon success.

- Evaluates statement test coverage across implementation and test pairs against target thresholds.

- Evaluates static verification checks, linters, and type checking for specified or pending target files.

- Commissions and decommissions isolated role workspaces for specified roles and directory scopes.

- Refreshes system configuration files, bin utilities, and companion guides across active role workspaces.
