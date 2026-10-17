<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:25:00Z
CHANGE: Define check_impl implementation specification
CODE_HASH: e3401910e161
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

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

- Pulls inbound changes from the canonical main workspace during work execution, verifies whether prior dirty targets remain pending in the role workspace via the pending manager, resolves batch size and feedback throttling limits from configuration or arguments, evaluates ready and blocked items from the work manager, records the bounded batch of pending targets via the pending manager, presents exclusively the assigned ready targets without extraneous remaining or blocked queue details, throttling unacted feedback reasons exceeding maximum character limits, and formats actionable next steps.

- Resolves the active role and target files during check files execution, regenerates a missing target file from its starter template for roles that declare source patterns and upstream dependencies before verification, executes the corresponding static linting, type-checking, or test rules, surfaces warning notifications and unacted feedback items when targets carrying unaddressed feedback pass static verification checks to alert agents that static checks do not verify runtime behavior or test assertions, formats clean diagnostic outcomes, and returns the verification exit status.
