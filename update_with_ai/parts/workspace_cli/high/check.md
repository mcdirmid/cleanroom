# check interface component

imports: session

## Purpose

The check interface component defines operational contracts for workspace developer loop commands, specifically work queue discovery and file verification.

Autonomous subagents executing inside isolated role workspaces require commands to inspect pending work, evaluate dirty targets, format actionable next steps, and run role-specific verification and linters. The check interface component establishes contracts for discovering work and checking files.

**Out of scope:** The check interface component does not submit changes, attribute defect blame, evaluate coverage, or commission workspaces; these are handled by other components.

**Delegated:** Execution phase context boundaries are delegated to agent_session.

## Types and Behavior

An agent session's *workspace checker* executes work discovery and file verification for role workspaces.

The workspace checker:

- Evaluates dirty work in the local role workspace, presenting bounded batches of ready targets without extraneous remaining or blocked queue details, throttling unacted feedback reasons exceeding maximum character limits when configured, formatting a prominent round conclusion directive when zero ready targets remain instructing the worker that all work assigned to their role is resolved and directing immediate round conclusion without further tool calls, and returning an integer exit code.

- Executes role-specific verification checks, linters, and type checking for specified or pending target files, recording verification execution records and target file hashes to gate subsequent submissions, blame attributions, or failure markings for modified files, configuring PYTHONPATH in the execution environment to include the package root and constituent support libraries, enforcing an execution timeout on verification commands to prevent blocked or hung sub-processes from stalling the workspace developer loop, regenerating missing target files from starter templates before verification for roles with source patterns and upstream dependencies, surfacing unacted feedback warnings when targets carrying unaddressed feedback pass static verification, and returning the verification exit code.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-21T21:50:00Z
LAST_CHANGED: 2026-10-28T20:15:00Z
CHANGE: Format prominent round conclusion directive when 0 ready targets remain in run_get_work
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
