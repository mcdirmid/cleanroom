# sandbox_guide_delivery_impl implementation component

imports: tool_provider, agent_file_alias, agent_node_config
implements: sandbox_guide_delivery

## Intent

Agent guidance documents contain disparate front-matter, structural summaries, and checklist sections that must be filtered into actionable milestone chunks. The sandbox_guide_delivery_impl implementation component extracts high-level task summaries and active instructional sections from markdown text while omitting verification lint checklists, managing current step offsets to ensure instructions advance monotonically upon successful phase verification.

By isolating milestone sections, maintaining current step offsets, and synthesizing diagnostic failure feedback when verification fails, the implementation prevents premature task completion and anchors agent progression to concrete validation results.

## Factored Contracts

### Contracts

- Parsing extracts the guide summary from content preceding the first section heading. [extract_summary_preceding_first_heading]
- Parsing extracts the guide summary from content under any heading titled "Summary". [extract_summary_under_summary_heading]
- Parsing captures verification failure instructions when a section heading begins with "Verification failure". [capture_verification_failure_instructions]
- Parsing creates sequential step sections for subsequent level-two headings. [create_sequential_step_sections]
- Parsing excludes sections whose title begins with "Summary" from step sections. [exclude_summary_sections_from_steps]
- Parsing excludes sections whose title begins with "Lint checks" from step sections. [exclude_lint_check_sections_from_steps]
- Parsing excludes sections whose title begins with "Verification failure" from step sections. [exclude_verification_failure_sections_from_steps]
- When verification passes and further step sections remain, advancing emits a response presenting the next step section introduced by "Now check carefully:". [emit_next_step_on_pass]
- When verification passes and further step sections remain, advancing instructs the agent to check carefully. [instruct_check_carefully_on_pass]
- When verification passes and further step sections remain, advancing instructs the agent to make edits if the source file does not conform to any checklist item. [instruct_make_edits_on_nonconformance]
- When verification passes and further step sections remain, advancing instructs the agent to call advance() only when conforming. [instruct_call_advance_when_conforming]
- When verification passes and further step sections remain, advancing transitions to the next step section. [transition_to_next_step_on_pass]
- When verification fails and no step section is active, advancing emits a response combining the initial primer content, verification failure instructions, and failure diagnostics. [emit_primer_failure_response_when_inactive]
- When verification fails, no step section is active, and the initial primer is omitted, advancing substitutes the guide summary for the initial primer. [substitute_summary_when_primer_omitted]
- When verification fails and a step section is active, advancing emits a response combining the current step section introduced by "Now check carefully:", verification failure instructions, and failure diagnostics. [emit_current_step_failure_response]
- When verification fails, advancing preserves the current step section without advancing to subsequent sections. [preserve_current_step_on_fail]
- When no guide is configured, the guide delivery indicates that no steps remain. [indicate_no_steps_when_no_guide]
- When all step sections have been completed, the guide delivery indicates that no steps remain. [indicate_no_steps_when_completed]
- When no steps remain, advancing produces no response. [produce_no_response_when_no_steps_remain]

## Woven Contracts

- Guide markdown parsing extracts summaries, verification failure instructions, and sequential step sections while filtering out metadata sections. [extract_summary_preceding_first_heading, extract_summary_under_summary_heading, capture_verification_failure_instructions, create_sequential_step_sections, exclude_summary_sections_from_steps, exclude_lint_check_sections_from_steps, exclude_verification_failure_sections_from_steps, sandbox_guide_delivery: [parse_file_content_into_guide]]
- Advancing a step upon passing verification transitions to the next milestone, prompting careful inspection and self-correction before subsequent progression. [emit_next_step_on_pass, instruct_check_carefully_on_pass, instruct_make_edits_on_nonconformance, instruct_call_advance_when_conforming, transition_to_next_step_on_pass, sandbox_guide_delivery: [deliver_instructions_on_pass]]
- Advancing a step upon failed verification retains the current milestone, formatting contextual guidance, failure instructions, and failure diagnostics. [emit_primer_failure_response_when_inactive, substitute_summary_when_primer_omitted, emit_current_step_failure_response, preserve_current_step_on_fail, sandbox_guide_delivery: [retain_milestone_on_fail, report_diagnostics_on_fail, report_failure_instructions_on_fail]]
- When no guide is configured or all sections have been completed, step delivery indicates completion and emits no further responses. [indicate_no_steps_when_no_guide, indicate_no_steps_when_completed, produce_no_response_when_no_steps_remain, sandbox_guide_delivery: [expose_steps_remain]]
