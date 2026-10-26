# check_impl implementation component

imports: session, submit, pending, role_registry, sync, work
implements: check

## Purpose

The check_impl implementation component realizes work queue discovery, actionable task formatting, template regeneration, and file verification runners for Cleanroom role workspaces.

Guiding subagents in role workspaces requires pulling changes from the canonical main workspace, evaluating dirty tasks, enforcing pending buffer resolution, and executing verification rules with starter template regeneration when targets are missing. The check_impl implementation component realizes these developer loop operations within the agent session lifecycle tier.

**Out of scope:** The check_impl implementation component does not submit changes, attribute blame critiques, evaluate test coverage, or provision workspaces; these are handled by other components.

**Delegated:** Session tier scoping is delegated to agent_session; workspace role definitions and resolution are delegated to role_registry; queue evaluation is delegated to work; pending work buffer tracking is delegated to pending; pulling changes is delegated to sync; submit target resolution is delegated to submit.

## Types and Behavior

The workspace checker realization implements work discovery and verification workflows for Cleanroom role workspaces.

The checker:

- Pulls inbound changes from the canonical main workspace during work execution, verifies whether prior dirty targets remain pending in the role workspace via the pending manager, resolves batch size and feedback throttling limits from configuration or arguments, evaluates ready and blocked items from the work manager, records the bounded batch of pending targets via the pending manager, presents exclusively the assigned ready targets without extraneous remaining or blocked queue details, throttling unacted feedback reasons exceeding maximum character limits, resolves the companion guide declared for the active role from the role registry, resolving its path relative to the role workspace root (`guides/<basename>`), and formats actionable next steps including specification contracts, reasons and feedback driving the work, and the workspace-relative companion guide to follow for presented and pending targets, with tailored resolution workflows for author and auditor roles, and when no ready targets are available and only blocked targets remain waiting on prerequisites, formats an actionable next step directing the worker that all targets are blocked waiting on upstream prerequisites, no ready targets remain, and the round must be concluded immediately without executing further tools.

- Resolves the active role, target files, and active model failure limits during check files execution, extracting max_failures from the active model configuration (defaulting to 5 for local engines and 100 for non-local models when unspecified) and propagating failure limits to test execution runners, regenerates a missing target file from its starter template for roles that declare source patterns and upstream dependencies before verification, executes the corresponding static linting, type-checking, or test rules assembling the verification execution environment bounded strictly to the active role workspace directory and its constituent package directories, isolating verification from the canonical repository root in PYTHONPATH and sys.path, enforcing an execution timeout on verification commands to prevent blocked or hung sub-processes from stalling the workspace developer loop and reporting verification failure with explicit diagnostic messaging that the timeout indicates a code defect (such as an infinite loop, deadlock, or live-lock) to be blamed against the code under test rather than an infrastructure failure when execution expires, records verification execution records and file hashes in the workspace to gate subsequent submissions, blame, or failure operations on modified files, surfaces warning notifications and unacted feedback items when targets carrying unaddressed feedback pass static verification checks to alert agents that static checks do not verify runtime behavior or test assertions, formats clean diagnostic outcomes, and returns the verification exit status.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T12:40:00Z
LAST_CHANGED: 2026-10-26T12:40:00Z
CHANGE: Clarify in check_files that verification timeouts indicate code defects rather than infrastructure failures
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
