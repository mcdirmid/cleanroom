# check_impl implementation component

## Intent

Operating command-line subagents in isolated role workspaces requires robust developer loop commands that pull changes from canonical workspaces, evaluate ready targets, enforce task completion, and execute file verification rules with starter template regeneration. The check_impl implementation component realizes get_work and check_files execution within the agent session lifecycle tier.

## Factored Contracts

### Contracts

- The workspace checker pulls inbound changes from the canonical main workspace during work execution, evaluates whether prior dirty targets remain pending in the role workspace via the pending manager (bypassing destructive inbound pull when executing in a fused role workspace or auditor role workspace), relisting assigned pending targets directly as ready work items when dirty work is already set rather than emitting an error, verifies when `gemini-argon` (or `gemini-4-argon`) is configured on the `antigravity` harness that the active Antigravity subagent conversation is actually executing on `gemini-argon` (aborting with an explicit error instructing the user to manually switch their Antigravity model to "Gemini Argon" before requesting the run again when a non-argon model is detected), resolves batch size and feedback throttling limits, evaluates ready and blocked items from the work manager, and for auditor roles (roles declaring an audit tag or lacking source patterns), aggressively executes verification checks on each discovered ready dirty target before presenting work, automatically submitting targets passing checks with audit attestation via the submission coordinator and omitting them from presented work, while retaining failing targets in the work queue without outputting failure diagnostics or triage summaries during work acquisition (leaving failure diagnostics to be surfaced when the worker executes `check_files` directly), and when all ready targets pass and are auto-submitted (or when no ready targets are available), clears the pending work buffer, records that no pending work remains, and formats a prominent round conclusion directive directing the worker that all work assigned to their role is resolved and to conclude the round immediately without further tools, while for authoring roles, records the bounded batch of pending targets via the pending manager, presents exclusively the assigned ready targets without extraneous remaining or blocked queue details, throttling unacted feedback reasons exceeding maximum character limits, resolves the companion guide declared for the active role from the role registry, projecting its path relative to the role workspace root (`guides/<basename>`), and formats actionable next steps including specification contracts, reasons and feedback driving the work, and the workspace-relative companion guide to follow for presented and pending targets across author, auditor, and fused roles. [execute_workspace_get_work]
- The workspace checker resolves the active role, target files, and active model failure limits during check files execution, extracting max_failures from the active model configuration (defaulting to 5 for local engines and 100 for non-local models) and propagating failure limits to test execution runners, enforces that verification cannot be executed when the role workspace has zero pending work assigned (reporting failure and directing the worker to call get_work first or conclude the round), verifies that any specified target file belongs to the active pending work buffer before executing checks (reporting failure when an unassigned target is requested), pulls inbound changes and refreshes system files from the canonical main workspace before executing checks, verifies that package `__init__.py` files and other read-only files outside the role's writeable file patterns have not been modified, reporting verification failure and reverting unauthorized modifications when detected, regenerates a missing target file from its starter template for roles that declare source patterns and upstream dependencies before verification, executes the corresponding static linting, type-checking, or test rules assembling the verification execution environment bounded strictly to the active role workspace directory and its constituent package directories, isolating verification from the canonical repository root in PYTHONPATH and sys.path, enforcing an execution timeout on verification commands to prevent blocked or hung sub-processes from stalling the workspace developer loop and reporting verification failure with explicit diagnostic messaging that the timeout indicates a code defect (such as an infinite loop, deadlock, or live-lock) rather than an infrastructure failure when execution expires, records verification execution records and file hashes in the workspace to gate subsequent modifications, records an in-workspace git milestone checkpoint commit when verification checks succeed with zero errors for authoring roles with writable targets to preserve working code states (omitting milestone commits for auditor roles with zero writable targets), surfaces warning notifications and unacted feedback items when targets carrying unaddressed feedback pass static verification checks to alert agents that static checks do not verify runtime behavior or test assertions, sanitizes verification process output by stripping redundant embedded arbiter reminders before display, formats clean diagnostic outcomes, surfaces cleanroom triage summaries extracting the author's latest # CHANGE: commit header from the target, primary failure exception or assertion, and candidate culprit file, and prominent specification grounding reminders when verification fails for auditor roles directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files or authoring debug scripts, and instructing the agent when an uncovered line persists across rounds or after test updates to examine the library implementation closely to determine whether the line is structurally or logically unreachable, and returns the verification exit status. [execute_workspace_check_files]

### Woven Contracts

- When executing get_work or check_files commands, the checker coordinates with work, pending, sync, submit, and role_registry. [execute_workspace_get_work, execute_workspace_check_files, check: [run_workspace_get_work, run_workspace_check_files], work: [compute_role_work_queue_targets, bound_ready_items_by_batch_size], pending: [get_pending_work_targets, is_pending_target_dirty_disk, set_pending_work_targets], sync: [pull_upstream_contracts, refresh_system_files_into_workspace], submit: [assert_verification_passed], role_registry: [resolve_role_definition]]

## Grounding

### Knowledge Provisions

- Work queue evaluation, batch presentation, and feedback throttling mechanics. [work_discovery_command_mechanics]
- Target verification, static lint execution, and starter template regeneration mechanics. [target_checking_command_mechanics]

### Inherited Deferred Requirements

- In-workspace work queue discovery and diagnostic formatting.
  - Grounded: [work_discovery_command_mechanics, work: [workspace_work_discovery_service], pending: [workspace_pending_work_tracking]]
- Target file verification, linting, and starter template regeneration.
  - Grounded: [target_checking_command_mechanics, submit: [file_submission_gating_service], role_registry: [workspace_registry_service]]

### Knowledge Requirements

- Workspace role definition resolution and pattern matching.
  - Grounded: [role_registry: [workspace_registry_service]]
- Work queue scheduling and candidate discovery.
  - Grounded: [work: [workspace_work_discovery_service]]
- Pending work buffer state management and target tracking.
  - Grounded: [pending: [workspace_pending_work_tracking]]
- Workspace file synchronization and inbound changes pulling.
  - Grounded: [sync: [workspace_pull_service]]
- Submission target resolution and verification.
  - Grounded: [submit: [file_submission_gating_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T11:00:00Z
LAST_CHANGED: 2026-11-03T23:45:00Z
CHANGE: Instruct coverage auditor when uncovered lines persist to examine library implementation for unreachable code
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
