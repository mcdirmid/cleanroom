<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_coordinator_impl planning specification
CODE_HASH: ca79e97dbb1b
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# antigravity_coordinator_impl implementation component

## Intent

Automated coordination requires precise prompt construction, dynamic workspace path binding, and robust completion message extraction. The antigravity_coordinator_impl implementation component formats skill markdown templates, builds subagent tool parameters, and parses structured completion messages.

## Factored Contracts

### Typing

- The antigravity coordinator generator realization implements AntigravityCoordinatorGenerator and operates within the system tier.

### Contracts

- The realization formats the skill markdown containing frontmatter and zero-execution coordination instructions. [render_skill_markdown]
- The realization asserts that the generated skill enforces workspace directory pinning. [verify_workspace_pinning]
- The realization maps role dispatch directives into subagent dispatch payloads. [map_dispatch_directive]
- The realization deserializes structured status, submitted targets, blamed targets, and failure diagnostics from subagent message text. [deserialize_wake_message]

### Woven Contracts

- When generating skills, the realization renders markdown and verifies workspace directory pinning. [render_skill_markdown, verify_workspace_pinning, antigravity_coordinator: [generate_coordinator_skill, enforce_workspace_pinning_requirement]]
- When preparing and handling dispatch, the realization maps dispatch directives and deserializes wake messages. [map_dispatch_directive, deserialize_wake_message, antigravity_coordinator: [format_subagent_dispatch, parse_wake_notification]]

## Grounding

### Knowledge Provisions

- Coordinator skill rendering and dispatch serialization mechanics. [coordinator_skill_mechanics]

### Inherited Deferred Requirements

- Coordinator skill generation, dispatch formatting, and notification parsing logic.
  - Grounded: [coordinator_skill_mechanics]

### Knowledge Requirements

- Multi-agent workspace coordination services and wave scheduling.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
