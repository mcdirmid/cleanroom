<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 5259c42f587d
-->

# sandbox_guide_delivery interface component

imports: tool_provider, agent_file_alias, agent_node_config

## Intent

Autonomous agents given monolithic multi-phase guidelines frequently attempt all objectives concurrently, accumulating errors across intermediate steps and producing unanchored diffs that fail validation checks. The sandbox_guide_delivery interface component breaks multi-phase workflows into discrete verifiable milestones, delivering instructional context incrementally and gating progression until prerequisite verification checks pass.

By parsing markdown guides into sequential milestone sections, retaining active milestone positions when verification checks fail, and delivering contextual diagnostic feedback, the guide delivery service keeps agents focused on a single task phase at a time.

## Factored Contracts

### Typing

- An initial primer provides initial instructional context recorded prior to step delivery.

### Contracts

- A caller supplies file content when parsing a guide. [parse_guide_content_supplied]
- The guide delivery parses file content into a guide. [parse_file_content_into_guide]
- A caller supplies initial primer text when recording an initial primer. [record_primer_text_supplied]
- The guide delivery records an initial primer. [record_initial_primer]
- A caller supplies a verification passed indicator when advancing a step. [advance_step_passed_supplied]
- A caller supplies failure diagnostics when advancing a step. [advance_step_diagnostics_supplied]
- The guide delivery delivers instructional text when verification passes. [deliver_instructions_on_pass]
- The guide delivery retains the current milestone when verification fails. [retain_milestone_on_fail]
- The guide delivery reports failure diagnostics when verification fails. [report_diagnostics_on_fail]
- The guide delivery reports verification failure instructions when verification fails. [report_failure_instructions_on_fail]
- The guide delivery exposes whether progressive steps remain. [expose_steps_remain]
- The guide delivery exposes its configured guide. [expose_configured_guide]

## Woven Contracts

- When advancing a step with verification passed, instructional text for the next milestone is delivered. [advance_step_passed_supplied, deliver_instructions_on_pass, expose_steps_remain]
- When advancing a step with verification failed, the current milestone is retained while diagnostics and failure instructions are reported. [advance_step_passed_supplied, advance_step_diagnostics_supplied, retain_milestone_on_fail, report_diagnostics_on_fail, report_failure_instructions_on_fail]
- Parsing file content constructs a guide containing a summary, step sections, and verification failure instructions. [parse_guide_content_supplied, parse_file_content_into_guide, expose_configured_guide]
