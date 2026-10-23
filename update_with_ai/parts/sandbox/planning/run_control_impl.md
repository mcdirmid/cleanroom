# run_control_impl implementation component

## Intent

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and manages session tool installation.

By providing atomic failure handling for out-of-order execution, preventing advances when prerequisites remain unverified, and delivering contextual task primers, the implementation maintains workflow discipline across agent turns.

## Factored Contracts

### Contracts

- The run controller initializes session tools upon agent session entry. [initialize_session_tools_on_entry]
- The run controller installs the submit tool for the agent session. [install_submit_tool]
- The run controller installs the fail tool for the agent session. [install_fail_tool]
- The run controller installs the check files tool for the agent session. [install_check_files_tool]
- The run controller installs the get work tool for the agent session. [install_get_work_tool]
- When ready dirty nodes are obtained, the get work tool installs the blame tool into the tool manager if and only if any active node has configured blame targets in node config. [install_blame_tool_when_targets_exist]
- The run controller installs the advance tool only when guide step mode is active. [install_advance_tool_conditional]
- Verification checks exposed by the run controller include session verification checks from node config. [expose_session_verification_checks]
- Verification check evaluation for an active node is cached alongside the edit manager target file hash. [cache_verification_with_file_hash]
- Verification checks are evaluated sequentially when verification results are outdated. [evaluate_verification_checks_sequentially]
- Verification results are outdated before initial evaluation. [verification_outdated_initially]
- Verification results are outdated when the target read-write file hash has changed since previous evaluation. [verification_outdated_on_hash_change]
- Verification check execution is omitted when target file hashes have not changed since previous evaluation. [omit_checks_when_hashes_match]
- The run controller exposes whether the latest verification evaluation passed. [expose_is_passed]
- The run controller exposes whether target file hashes are unchanged since the last evaluation. [expose_is_unchanged]
- The run controller exposes aggregated diagnostic output from failing verification checks. [expose_diagnostic_output]
- The check files tool shares the constant suppression key "check_files". [share_check_files_suppression_key]
- When target file hashes have not changed and verification is passing, the check files tool reminds the agent that verification status is unchanged. [remind_verification_unchanged]
- When verification fails, the check files tool presents sanitized diagnostic feedback alongside verification failure instructions regardless of whether target file hashes changed. [present_sanitized_feedback_on_check_failure]
- When verification passes, the check files tool produces a response presenting passing results. [present_passing_results_on_check_success]
- The advance tool shares the constant suppression key "advance". [share_advance_suppression_key]
- When verification is failing on the first step, the advance tool repeats primer and summary content through guide delivery. [advance_repeats_primer_on_first_step_failure]
- When verification is failing, the advance tool reminds the agent that check files should be called first. [advance_reminds_call_check_files]
- When verification is failing, the advance tool specifies a follow-up execution of check files. [advance_specifies_check_files_followup]
- When verification passes and guide steps remain, the advance tool delivers the next step section. [advance_delivers_next_step_on_pass]
- When verification passes, no steps remain, and workspace files were modified, the advance tool fails reminding the agent to call submit with a change summary. [advance_fails_reminding_submit_when_modified]
- When verification passes, no steps remain, and no workspace files were modified, the advance tool produces a response specifying a follow-up execution of submit without a change summary. [advance_specifies_submit_followup_when_unmodified]
- The get work tool fails when open active nodes remain. [get_work_fails_when_open_nodes_remain]
- When no open active nodes remain, the get work tool obtains dirty nodes from dag storage and dag subgraph. [get_work_obtains_dirty_nodes]
- When no dirty nodes are ready, the get work tool produces an idle response. [get_work_produces_idle_response]
- The get work tool materializes startup templates on disk through dag storage. [get_work_materializes_templates_via_storage]
- When ready dirty nodes are obtained and guide step mode is inactive, the get work tool returns the task primer with guide file attribution. [get_work_returns_primer_with_guide_file]
- When ready dirty nodes are obtained and guide step mode is active, the get work tool installs the advance tool and returns the task primer prompting advance. [get_work_returns_primer_with_advance_prompt]

### Woven Contracts

- Session outcome tools are installed during controller initialization, restricting the advance tool strictly to guide step mode. [initialize_session_tools_on_entry, install_submit_tool, install_fail_tool, install_check_files_tool, install_get_work_tool, install_advance_tool_conditional, expose_session_verification_checks, run_control: [initialize_session_tools_on_entry, unconditionally_install_session_tools, install_advance_tool_when_step_mode]]
- Verification results are evaluated sequentially and cached against target file hashes, exposing pass/fail status, hash stability, and diagnostic output while reusing cached evaluations when files remain unchanged. [cache_verification_with_file_hash, evaluate_verification_checks_sequentially, verification_outdated_initially, verification_outdated_on_hash_change, omit_checks_when_hashes_match, expose_is_passed, expose_is_unchanged, expose_diagnostic_output, run_control: [cache_verification_results, reuse_cached_verification_outcome, expose_is_passed, expose_is_unchanged, expose_diagnostic_output]]
- The check files tool executes verification across modified workspace files, presenting sanitized failure diagnostics or passing results. [present_sanitized_feedback_on_check_failure, present_passing_results_on_check_success, remind_verification_unchanged, share_check_files_suppression_key, run_control: [check_files_evaluates_checks, check_files_presents_outcomes, check_files_fails_on_verification_failure]]
- The advance tool gates step progression behind passing verification, guiding the agent to run verification checks or submit completed work. [advance_repeats_primer_on_first_step_failure, advance_reminds_call_check_files, advance_specifies_check_files_followup, advance_delivers_next_step_on_pass, advance_fails_reminding_submit_when_modified, advance_specifies_submit_followup_when_unmodified, share_advance_suppression_key, guide_delivery: [advance_step_passed_supplied, advance_step_diagnostics_supplied]]
- The get work tool orchestrates batch acquisition from graph storage, template materialization via dag storage, conditional blame tool installation, and session initialization. [get_work_fails_when_open_nodes_remain, get_work_obtains_dirty_nodes, get_work_produces_idle_response, get_work_materializes_templates_via_storage, get_work_returns_primer_with_guide_file, get_work_returns_primer_with_advance_prompt, install_blame_tool_when_targets_exist, dag_storage: [materialize_node_template]]

## Grounding

### Knowledge Provisions

- Evaluates and aggregates session verification checks. [verification_evaluation]
- Coordinates milestone step progression through guide delivery. [advance_step_coordination]
- Acquires active dirty nodes and initializes session tasks. [work_acquisition]

### Inherited Deferred Requirements

- Access to dag storage to query nodes and record messages.
  - Grounded: [dag_storage: [dag_storage_service]]
- Access to session edit manager to inspect modification state and hashes.
  - Grounded: [file_editor: [writes_occurred_status]]
- Capability to execute external verification commands.
  - Grounded: [node_config: [node_configuration_service]]
- Access to guide delivery to manage milestone transitions.
  - Grounded: [guide_delivery: [step_delivery]]

### Knowledge Requirements

- Resolution of active targets from command line arguments or session state.
  - Grounded: [coordinate: [session_target_registry, default_target_resolution]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-21T22:00:00Z
LAST_CHANGED: 2026-10-21T22:00:00Z
CHANGE: Present diagnostic feedback on verification failure regardless of whether target file hashes changed
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
