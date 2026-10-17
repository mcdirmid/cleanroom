<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:30:00Z
CHANGE: Define submission_impl planning specification
CODE_HASH: ae56b844dc13
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# submission_impl implementation component

## Intent

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The submission_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

By providing atomic failure handling for out-of-order execution, preventing submissions when prerequisites remain unverified, and ensuring blame explanations adhere to single-paragraph formatting, the implementation maintains workflow discipline across agent turns.

## Factored Contracts

### Contracts

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
- Executing the submit tool updates outdated verification results. [submit_updates_outdated_results]
- The submit tool dispatches target submission with the resolve target, change summary, and workspace modification status to the session coordinator. [submit_dispatches_target_submission]
- When submission gating rejects the request, the submit tool relays rejection feedback alongside change summary reminders when summary rules are violated, or feedback resolution reminders when unaddressed feedback blocks submission. [submit_fails_relaying_rejection_feedback]
- When submission succeeds and all active nodes are resolved, the submit tool produces a terminating response. [submit_terminates_when_all_resolved]
- When submission succeeds and open active nodes remain, the submit tool produces a non-terminating response. [submit_non_terminating_when_open_remain]
- The fail tool marks the active node as failed. [fail_marks_node_failed]
- The blame tool identifies the active node attributing blame from the specified blame target, treating the resolve target parameter as the blame target when it matches a configured blame target. [blame_identifies_active_node_from_target]
- When blame target is omitted in a single-target context, the blame tool defaults to the single configured blame target of the active node. [blame_defaults_single_target]
- The blame tool fails when the blame target does not match any configured blame target. [blame_fails_when_target_unconfigured]
- The blame tool fails when the explanation contains newline characters. [blame_fails_when_explanation_has_newlines]
- The blame tool records defect feedback for the blamed target via dag storage so that the blamed node receives the feedback message. [blame_records_defect_feedback_in_storage]
- The blame tool marks the blame target as attributed. [blame_marks_target_attributed]

### Woven Contracts

- Resolve tools match and default target arguments and validate in-batch dependency ordering. [resolve_tool_accepts_target_alias, resolve_tool_matches_target, resolve_target_defaults_single_node, resolve_target_defaults_last_path, resolve_tool_fails_when_unresolvable, resolve_tool_fails_when_target_not_open, resolve_tool_fails_when_dependency_not_clean, resolve_tool_fails_dependent_nodes]
- A resolve tool produces a terminating response when all active nodes are resolved, or produces a non-terminating response listing remaining active nodes when other targets remain open. [resolve_tool_lists_remaining_nodes, resolve_tool_terminates_when_all_resolved, submission: [resolve_tool_terminates_when_all_resolved, resolve_tool_lists_remaining_nodes]]
- The submit tool verifies that guide milestones are finished and tests pass before dispatching submission to the session coordinator, relaying rejection feedback and change summary reminders upon failure. [submit_fails_when_guide_steps_remain, submit_specifies_advance_followup, submit_fails_when_verification_failing, submit_specifies_check_files_followup, submit_updates_outdated_results, submit_dispatches_target_submission, submit_fails_relaying_rejection_feedback, submit_terminates_when_all_resolved, submit_non_terminating_when_open_remain, share_submit_suppression_key, submission: [submit_concludes_nodes_on_pass, submit_marks_target_clean, submit_enforces_change_documentation], coordinate: [dispatch_submit]]
- The blame tool attributes defects to upstream dependencies using single-paragraph explanations, recording defect feedback in storage and identifying the active node from the blame target. [blame_identifies_active_node_from_target, blame_defaults_single_target, blame_fails_when_target_unconfigured, blame_fails_when_explanation_has_newlines, blame_records_defect_feedback_in_storage, blame_marks_target_attributed, submission: [blame_attributes_upstream_failure], coordinate: [dispatch_blame]]
- The fail tool marks tasks as failed and resolves active nodes. [fail_marks_node_failed, submission: [fail_terminates_run_in_failure]]

## Grounding

### Knowledge Provisions

- Concludes active nodes clean in graph storage. [clean_submission]
- Records defect attribution to upstream dependencies. [defect_blame]
- Terminates tasks in failure. [failure_termination]

### Inherited Deferred Requirements

- Tracking of open targets and dispatch of submission and failure outcomes.
  - Grounded: [coordinate: [session_target_registry, default_target_resolution]]

### Knowledge Requirements

- Verification of passing status before task submission.
  - Grounded: [run_control: [verification_evaluation]]
- Inspection of workspace file modification state.
  - Grounded: [src_metadata: [source_metadata_service]]
- Determination of remaining guide steps.
  - Grounded: [guide_delivery: [steps_remaining_status]]
