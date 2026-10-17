<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T19:15:00Z
CHANGE: author antigravity_harness planning specification
CODE_HASH: 3c642f6aaee0
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# antigravity_harness interface component

## Intent

Autonomous multi-agent execution requires reliable dispatch into isolated role workspaces, process management, and precise telemetry harvesting from platform event logs. The antigravity_harness interface component formalizes execution dispatch, transcript log parsing, token rate-card accounting, and role turn result construction for Google Antigravity.

## Factored Contracts

### Typing

- A transcript token metrics record holds uncached prompt tokens, cached prompt tokens, completion tokens, model name, and monetary expenditure in USD.
- An abstract transcript telemetry parser parses execution logs and extracts model token consumption.
- An antigravity harness adapter realizes the harness adapter protocol for Google Antigravity execution sessions.
- An antigravity harness manager operates in the agent session tier, manages Antigravity execution adapters, installs the Antigravity adapter factory into the harness registry, and manages transcript parsing services.

### Contracts

- An antigravity harness adapter dispatches the role directive into the target role workspace and monitors turn completion. [dispatch_role_to_workspace]
- An antigravity harness adapter polls active role turns non-blockingly without halting caller execution. [poll_active_turn]
- An antigravity harness adapter extracts token usage metrics from the execution transcript log and applies standard model pricing rate cards. [extract_transcript_telemetry]
- An antigravity harness adapter inspects role workspace submission outcomes and blame buffers to construct a complete role turn result. [construct_role_turn_result]
- An antigravity harness adapter interrupts active turns when execution deadlines are exceeded. [interrupt_active_turn]
- An antigravity harness manager installs the Antigravity adapter factory into the harness registry. [install_antigravity_harness_adapter]

### Woven Contracts

- When executing a role turn, the harness adapter dispatches the directive, monitors completion, extracts telemetry, and constructs a role turn result. [dispatch_role_to_workspace, extract_transcript_telemetry, construct_role_turn_result]
- When supervising active turns, the harness adapter polls status non-blockingly and returns turn results upon completion. [poll_active_turn]
- When an active turn exceeds its execution deadline, the harness adapter interrupts the turn. [interrupt_active_turn]

## Grounding

### Knowledge Provisions

- Antigravity harness execution adapter and transcript parsing services. [antigravity_harness_services]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [session: [agent_session_tier_provision]]
- Multi-agent workspace coordination services and wave scheduling.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Harness adapter execution protocol and turn outcome types.
  - Grounded: [subagent_coordinator: [harness_adapter_protocol]]
- Subagent harness registry and adapter factory installation.
  - Grounded: [subagent_harness: [harness_registry_service]]
- Subagent turn execution, transcript parsing, and rate card calculation logic.
  - Deferred: Realized by the antigravity harness implementation component.
