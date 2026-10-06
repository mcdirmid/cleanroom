<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 13258382b8a5
-->

# sandbox_run_control_impl implementation component

imports: tool_provider, agent_file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery, agent_node_config, template_format, dag_subgraph, sandbox, control_coordinate, control_asm
implements: sandbox_run_control

## Intent

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The sandbox_run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

By providing atomic failure handling for out-of-order execution, preventing submissions when prerequisites remain unverified, and ensuring blame explanations adhere to single-paragraph formatting, the implementation maintains workflow discipline across agent turns.

## Factored Contracts

### Contracts

- The run controller installs the submit tool for the agent session. [install_submit_tool]
- The run controller installs the fail tool for the agent session. [install_fail_tool]
- The run controller installs the check files tool for the agent session. [install_check_files_tool]
- The run controller installs the get work tool for the agent session. [install_get_work_tool]
- The run controller installs the blame tool for the agent session. [install_blame_tool]
- The run controller installs the advance tool only when guide step mode is active. [install_advance_tool_conditional]
- Verification checks exposed by the run controller include session verification checks from node config. [expose_session_verification_checks]
- Verification check evaluation for an active node is cached alongside the edit manager target file hash. [cache_verification_with_file_hash]
- Verification checks are evaluated sequentially when verification results are outdated. [evaluate_verification_checks_sequentially]
- Verification results are outdated before initial evaluation. [verification_outdated_initially]
- Verification results are outdated when the target read-write file hash has changed since previous evaluation. [verification_outdated_on_hash_change]
- Verification check execution is omitted when target file hashes have not changed since previous evaluation. [omit_checks_when_hashes_match]
- The check files tool shares the constant suppression key "check_files". [share_check_files_suppression_key]
- When target file hashes have not changed, the check files tool reminds the agent that verification status is unchanged. [remind_verification_unchanged]
- When verification fails, the check files tool presents sanitized diagnostic feedback alongside verification failure instructions. [present_sanitized_feedback_on_check_failure]
- When verification passes, the check files tool produces a response presenting passing results. [present_passing_results_on_check_success]
- The advance tool shares the constant suppression key "advance". [share_advance_suppression_key]
- When verification is failing on the first step, the advance tool repeats primer and summary content through guide delivery. [advance_repeats_primer_on_first_step_failure]
- When verification is failing, the advance tool reminds the agent that check files should be called first. [advance_reminds_call_check_files]
- When verification is failing, the advance tool specifies a follow-up execution of check files. [advance_specifies_check_files_followup]
- When verification passes and guide steps remain, the advance tool delivers the next step section. [advance_delivers_next_step_on_pass]
- When verification passes, no steps remain, and workspace files were modified, the advance tool fails reminding the agent to call submit with a change summary. [advance_fails_reminding_submit_when_modified]
- When verification passes, no steps remain, and no workspace files were modified, the advance tool produces a response specifying a follow-up execution of submit without a change summary. [advance_specifies_submit_followup_when_unmodified]
- A resolve tool accepts target as an alias for the resolve target parameter. [resolve_tool_accepts_target_alias]
- A resolve tool matches the resolve target parameter by declared source file, short unit name (when unique), or package-qualified unit name against open active nodes. [resolve_tool_matches_target]
- When omitted with a single open active node, resolve target defaults to that remaining unsubmitted active node. [resolve_target_defaults_single_node]
- When omitted with multiple unsubmitted files, resolve target defaults to the last read or written path corresponding to an open active node. [resolve_target_defaults_last_path]
- A resolve tool fails when resolve target cannot be defaulted. [resolve_tool_fails_when_unresolvable]
- A resolve tool fails when the specified resolve target does not match an open active node. [resolve_tool_fails_when_target_not_open]
- A resolve tool fails when an in-batch dependency of the resolve target is not clean. [resolve_tool_fails_when_dependency_not_clean]
- Upon node failure or blame, a resolve tool marks in-batch dependent nodes as failed. [resolve_tool_fails_dependent_nodes]
- When other active nodes remain, a resolve tool produces a non-terminating response listing remaining active nodes. [resolve_tool_lists_remaining_nodes]
- When all active nodes are resolved, a resolve tool produces a terminating response. [resolve_tool_terminates_when_all_resolved]
- The submit tool shares the constant suppression key "submit". [share_submit_suppression_key]
- When guide step mode is active and guide steps remain, the submit tool fails. [submit_fails_when_guide_steps_remain]
- When guide step mode is active and guide steps remain, the submit tool specifies advance as a follow-up tool call. [submit_specifies_advance_followup]
- When verification is failing, the submit tool fails. [submit_fails_when_verification_failing]
- When verification is failing, the submit tool specifies a follow-up execution of check files. [submit_specifies_check_files_followup]
- When an initial implementation change is assigned and no files were modified, the submit tool fails. [submit_fails_when_initial_change_unmodified]
- When session feedback is present and no files were modified, the submit tool fails. [submit_fails_when_feedback_unmodified]
- When the target is an auditor node and a change summary is provided, the submit tool fails. [submit_fails_when_summary_provided_for_auditor]
- When files were modified and the change summary is omitted, the submit tool fails. [submit_fails_when_change_summary_omitted]
- When workspace files were not modified and a change summary is provided, the submit tool fails. [submit_fails_when_summary_provided_without_modifications]
- The submit tool marks the resolve target clean in graph storage via dag storage with the provided change summary so that the node is no longer dirty. [submit_marks_node_clean_in_storage]
- The submit tool marks the resolve target clean in the current get work turn. [submit_marks_node_clean]
- The fail tool marks the active node as failed. [fail_marks_node_failed]
- The blame tool identifies the active node attributing blame from the specified blame target. [blame_identifies_active_node_from_target]
- When blame target is omitted in a single-target context, the blame tool defaults to the single configured blame target of the active node. [blame_defaults_single_target]
- The blame tool fails when the blame target does not match any configured blame target. [blame_fails_when_target_unconfigured]
- The blame tool fails when the explanation contains newline characters. [blame_fails_when_explanation_has_newlines]
- The blame tool records defect feedback for the blamed target via dag storage so that the blamed node receives the feedback message. [blame_records_defect_feedback_in_storage]
- The blame tool marks the blame target as attributed. [blame_marks_target_attributed]
- The get work tool fails when open active nodes remain. [get_work_fails_when_open_nodes_remain]
- When no open active nodes remain, the get work tool obtains dirty nodes from dag storage and dag subgraph. [get_work_obtains_dirty_nodes]
- When no dirty nodes are ready, the get work tool produces an idle response. [get_work_produces_idle_response]
- The get work tool materializes startup templates on disk through dag storage. [get_work_materializes_templates_via_storage]
- When ready dirty nodes are obtained and guide step mode is inactive, the get work tool returns the task primer with guide file attribution. [get_work_returns_primer_with_guide_file]
- When ready dirty nodes are obtained and guide step mode is active, the get work tool returns the task primer prompting advance. [get_work_returns_primer_with_advance_prompt]

## Woven Contracts

- Session outcome tools are installed during controller initialization, restricting the advance tool strictly to guide step mode. [install_submit_tool, install_fail_tool, install_check_files_tool, install_get_work_tool, install_blame_tool, install_advance_tool_conditional, expose_session_verification_checks]
- Verification results are evaluated sequentially and cached against target file hashes, reusing cached evaluations when files remain unchanged. \[cache_verification_with_file_hash, evaluate_verification_checks_sequentially, verification_outdated_initially, verification_outdated_on_hash_change, omit_checks_when_hashes_match, sandbox_run_control: [cache_verification_results, reuse_cached_verification_outcome]\]
- The check files tool executes verification across modified workspace files, presenting sanitized failure diagnostics or passing results. \[present_sanitized_feedback_on_check_failure, present_passing_results_on_check_success, remind_verification_unchanged, share_check_files_suppression_key, sandbox_run_control: [check_files_evaluates_checks, check_files_presents_outcomes, check_files_fails_on_verification_failure]\]
- The advance tool gates step progression behind passing verification, guiding the agent to run verification checks or submit completed work. \[advance_repeats_primer_on_first_step_failure, advance_reminds_call_check_files, advance_specifies_check_files_followup, advance_delivers_next_step_on_pass, advance_fails_reminding_submit_when_modified, advance_specifies_submit_followup_when_unmodified, share_advance_suppression_key, sandbox_guide_delivery: [advance_step_passed_supplied, advance_step_diagnostics_supplied]\]
- Resolve tools match and default target arguments and validate in-batch dependency ordering. [resolve_tool_accepts_target_alias, resolve_tool_matches_target, resolve_target_defaults_single_node, resolve_target_defaults_last_path, resolve_tool_fails_when_unresolvable, resolve_tool_fails_when_target_not_open, resolve_tool_fails_when_dependency_not_clean, resolve_tool_fails_dependent_nodes, resolve_tool_lists_remaining_nodes, resolve_tool_terminates_when_all_resolved]
- The submit tool verifies that guide milestones are finished and tests pass before marking the node clean in storage and in turn with documented changes. \[submit_fails_when_guide_steps_remain, submit_specifies_advance_followup, submit_fails_when_verification_failing, submit_specifies_check_files_followup, submit_fails_when_initial_change_unmodified, submit_fails_when_feedback_unmodified, submit_fails_when_summary_provided_for_auditor, submit_fails_when_change_summary_omitted, submit_fails_when_summary_provided_without_modifications, submit_marks_node_clean_in_storage, submit_marks_node_clean, share_submit_suppression_key, sandbox_run_control: [submit_concludes_nodes_on_pass, submit_marks_target_clean, submit_enforces_change_documentation], dag_storage: [mark_node_clean_in_storage, mark_clean_with_change_description, mark_auditor_node_clean_stamps_dependencies]\]
- The blame tool attributes defects to upstream dependencies using single-paragraph explanations, recording defect feedback in storage and identifying the active node from the blame target. \[blame_identifies_active_node_from_target, blame_defaults_single_target, blame_fails_when_target_unconfigured, blame_fails_when_explanation_has_newlines, blame_records_defect_feedback_in_storage, blame_marks_target_attributed, sandbox_run_control: [blame_attributes_upstream_failure], dag_storage: [record_feedback_messages]\]
- The get work tool orchestrates batch acquisition from graph storage, template materialization via dag storage, and session initialization. \[get_work_fails_when_open_nodes_remain, get_work_obtains_dirty_nodes, get_work_produces_idle_response, get_work_materializes_templates_via_storage, get_work_returns_primer_with_guide_file, get_work_returns_primer_with_advance_prompt, dag_storage: [materialize_node_template]\]
