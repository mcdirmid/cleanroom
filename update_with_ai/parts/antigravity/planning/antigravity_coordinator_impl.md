<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_coordinator_impl planning specification
CODE_HASH: 1c1e4108a5f8
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
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
- The realization creates the workspace-local rules directory and writes isolation boundary rules. [write_boundary_rules_file]
- The realization formats role guidance instructions incorporating verification gates and submission protocols. [write_guidance_instruction_file]
- The realization records created boundary file paths and returns a confinement report. [create_confinement_report]

### Woven Contracts

- When generating skills, the realization renders markdown and verifies workspace directory pinning. [render_skill_markdown, verify_workspace_pinning, antigravity_coordinator: [generate_coordinator_skill, enforce_workspace_pinning_requirement]]
- When preparing and handling dispatch, the realization maps dispatch directives and deserializes wake messages. [map_dispatch_directive, deserialize_wake_message, antigravity_coordinator: [format_subagent_dispatch, parse_wake_notification]]
- When configuring a workspace, the realization writes boundary rules, writes role guidance, and creates a confinement report. [write_boundary_rules_file, write_guidance_instruction_file, create_confinement_report, antigravity_workspace: [write_workspace_isolation_rules, generate_role_guidance_docs, produce_confinement_report], role_registry: [resolve_role_definition]]

## Grounding

### Knowledge Provisions

- Coordinator skill rendering and dispatch serialization mechanics. [coordinator_skill_mechanics]
- Workspace isolation rule rendering and confinement generation mechanics. [workspace_isolation_mechanics]

### Inherited Deferred Requirements

- Coordinator skill generation, dispatch formatting, and notification parsing logic.
  - Grounded: [coordinator_skill_mechanics]
- Workspace isolation rule writing and confinement reporting logic.
  - Grounded: [workspace_isolation_mechanics]

### Knowledge Requirements

- Multi-agent workspace coordination services and wave scheduling.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Role definition resolution services.
  - Grounded: [role_registry: [workspace_registry_service]]
