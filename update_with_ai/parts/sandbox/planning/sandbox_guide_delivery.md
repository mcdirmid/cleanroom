<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T03:10:53Z
CHANGE: Declare progressive guide delivery, primer, and step advancement typing statements
CODE_HASH: 20548bbc54e4
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# sandbox_guide_delivery interface component

## Intent

Autonomous agents given monolithic multi-phase guidelines frequently attempt all objectives concurrently, accumulating errors across intermediate steps and producing unanchored diffs that fail validation checks. The sandbox_guide_delivery interface component breaks multi-phase workflows into discrete verifiable milestones, delivering instructional context incrementally and gating progression until prerequisite verification checks pass.

By parsing markdown guides into sequential milestone sections, retaining active milestone positions when verification checks fail, and delivering contextual diagnostic feedback, the guide delivery service keeps agents focused on a single task phase at a time.

## Factored Contracts

### Typing

- An agent session's guide delivery delivers the instructions of a configured guide to an agent progressively.
- An initial primer presents the first instructional content of a session.
- A guide delivery can advance step given a verification passed indicator and failure diagnostics.

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

### Woven Contracts

- When advancing a step with verification passed, instructional text for the next milestone is delivered. [advance_step_passed_supplied, deliver_instructions_on_pass, expose_steps_remain]
- When advancing a step with verification failed, the current milestone is retained while diagnostics and failure instructions are reported. [advance_step_passed_supplied, advance_step_diagnostics_supplied, retain_milestone_on_fail, report_diagnostics_on_fail, report_failure_instructions_on_fail]
- Parsing file content constructs a guide containing a summary, step sections, and verification failure instructions. [parse_guide_content_supplied, parse_file_content_into_guide, expose_configured_guide]

## Grounding

### Knowledge Provisions

- Parses file content into structured milestone guides. [guide_parsing]
- Records initial primer instructional context. [primer_recording]
- Delivers instructional milestones upon verification advancement. [step_delivery]
- Exposes whether progressive steps remain. [steps_remaining_status]

### Knowledge Requirements

- Tracking active milestone offset and initial primer in session state.
  - Deferred: Requires state tracking in implementation.
- Parsing markdown section headers and bulleted checklists.
  - Deferred: Requires markdown parsing in implementation.
