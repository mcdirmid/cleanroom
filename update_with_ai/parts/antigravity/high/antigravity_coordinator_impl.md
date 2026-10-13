<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_coordinator_impl implementation specification
CODE_HASH: 2cf896e6a853
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# antigravity_coordinator_impl implementation component

imports: agent_session, antigravity_coordinator, antigravity_ext, subagent_coordinator
implements: antigravity_coordinator

## Purpose

The antigravity_coordinator_impl implementation component realizes skill artifact generation, tool parameter formatting, and wake notification parsing for Google Antigravity coordinator subagents.

Automated coordination requires precise prompt construction, dynamic workspace path binding, and robust completion message extraction. The antigravity_coordinator_impl implementation component formats skill markdown templates, builds subagent tool parameters, and parses structured completion messages.

**Out of scope:** The antigravity_coordinator_impl implementation component does not directly execute subagent subprocesses or mutate source files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; interface definitions are delegated to antigravity_coordinator; skill schema conventions are delegated to antigravity_ext; role dispatch models are delegated to subagent_coordinator.

## Types and Behavior

The antigravity coordinator generator realization creates coordinator skills and formats subagent dispatch payloads.

When generating the coordinator skill:

- The realization renders the skill document containing YAML metadata and instructions for evaluating work queues and dispatching worker subagents.

- The realization validates that the generated skill enforces workspace directory pinning and prohibits inheriting the supervisor workspace.

- The realization maps role dispatch directives into subagent dispatch specifications with target workspace paths and task prompts instructing workers to drain ready nodes via submission, blame attribution, or failure diagnostics.

- The realization extracts action status, submitted targets, blamed targets, and failure diagnostics from subagent completion messages.
