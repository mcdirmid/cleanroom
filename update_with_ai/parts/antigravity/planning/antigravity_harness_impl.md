<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T19:15:00Z
CHANGE: author antigravity_harness_impl planning specification
CODE_HASH: 8e15701f4c7b
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# antigravity_harness_impl implementation component

## Intent

Harvesting accurate token telemetry from local execution logs and managing subprocess lifecycles requires specialized parsing and cost calculation algorithms. The antigravity_harness_impl implementation component provides transcript parsing, subprocess management, and standardized financial rate cards.

## Factored Contracts

### Typing

- The antigravity harness manager realization implements AntigravityHarnessManager and operates within the system tier.

### Contracts

- The realization launches the Antigravity subagent process using configured CLI arguments with working directory bound to the role workspace. [launch_subagent_process]
- The realization polls active subprocess status non-blockingly and reaps completed turns. [poll_active_process]
- The realization streams and parses JSONL lines from the transcript log file. [parse_transcript_jsonl_lines]
- The realization applies model-specific pricing formulas for Gemini Flash and Gemini Pro to tally monetary costs. [calculate_model_rate_costs]
- The realization reads submitted target lists and blame buffer records to build role turn results. [gather_role_turn_results]
- The realization sends termination signals to active subprocesses upon timeout. [terminate_subagent_process]

### Woven Contracts

- When executing turns, the realization launches the process, parses transcript JSONL lines, calculates rate costs, and gathers role turn results. [launch_subagent_process, parse_transcript_jsonl_lines, calculate_model_rate_costs, gather_role_turn_results, antigravity_harness: [dispatch_role_to_workspace, extract_transcript_telemetry, construct_role_turn_result]]
- When polling active turns, the realization checks child process state and reaps completed results. [poll_active_process, antigravity_harness: [poll_active_turn]]
- When a turn times out, the realization terminates the process. [terminate_subagent_process, antigravity_harness: [interrupt_active_turn]]

## Grounding

### Knowledge Provisions

- Antigravity transcript telemetry extraction and process adapter mechanics. [antigravity_adapter_mechanics]

### Inherited Deferred Requirements

- Subagent turn execution, transcript parsing, and rate card calculation logic.
  - Grounded: [antigravity_adapter_mechanics]

### Knowledge Requirements

- Multi-agent workspace coordination services and wave scheduling.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Harness adapter execution protocol and turn outcome types.
  - Grounded: [subagent_coordinator: [harness_adapter_protocol]]
