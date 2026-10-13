<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_coordinator planning specification
CODE_HASH: 34adbfde1a2a
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# antigravity_coordinator interface component

## Intent

Coordinating multi-agent workflows inside an interactive desktop IDE requires specialized skills and dispatch formats that prevent context pollution and enforce physical workspace boundaries. The antigravity_coordinator interface component formalizes coordinator skill generation, subagent invocation payload synthesis, and reactive completion notification parsing.

## Factored Contracts

### Typing

- A subagent dispatch specification holds type name, role name, prompt, workspace path, and optional model name.
- A coordinator skill document holds skill name, description, YAML frontmatter, and markdown body content.
- A wake notification message holds action, role name, submitted targets, blamed targets, and failure diagnostics.
- An antigravity coordinator generator operates in the system tier and creates coordinator skills and formats subagent dispatch payloads.

### Contracts

- An antigravity coordinator generator produces skill content instructing the coordinator subagent to inspect DAG queues for ready nodes and dispatch role subagents. [generate_coordinator_skill]
- An antigravity coordinator generator embeds requirements that strictly forbid inheriting the supervisor workspace and require pinning the workspace directory to the provisioned role workspace. [enforce_workspace_pinning_requirement]
- An antigravity coordinator generator formats subagent dispatch specifications for ready roles identified in an execution wave, instructing workers to drain ready nodes via submission, blame attribution, or failure diagnostics. [format_subagent_dispatch]
- An antigravity coordinator generator parses wake notification messages received from subagent turns to extract completed, blamed, and failed targets. [parse_wake_notification]

### Woven Contracts

- When generating the coordinator skill, the generator enforces workspace directory pinning and formats instructional prompts. [generate_coordinator_skill, enforce_workspace_pinning_requirement]
- When preparing wave directives, the generator formats subagent dispatch specifications and parses wake notifications upon completion. [format_subagent_dispatch, parse_wake_notification]

## Grounding

### Knowledge Provisions

- Coordinator skill rendering and subagent dispatch formatting capabilities. [antigravity_coordinator_services]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [agent_session: [agent_session_tier_provision]]
- Multi-agent workspace coordination services and wave scheduling.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Coordinator skill generation, dispatch formatting, and notification parsing logic.
  - Deferred: Realized by the antigravity coordinator implementation component.
