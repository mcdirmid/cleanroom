<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:40:42Z
LAST_CHANGED: 2026-10-09T21:36:15Z
CHANGE: Contract run controller session tool initialization on agent session entry
CODE_HASH: a3f778ca5d5a
SPEC_QA_AUDIT: 2026-10-09T21:40:42Z
-->

# sandbox_run_control interface component

imports: tool_provider, agent_file_alias, dag_storage, agent_node_config, dag_config

## Intent

Autonomous agents operating across complex workspaces require explicit, governed control boundaries to conclude successful tasks, attribute upstream defects, and abort unrecoverable executions. Without centralized outcome coordination, agents risk silent failures, endless re-cleaning loops, or unverified task completions. The sandbox_run_control interface component establishes a governed termination boundary that verifies session criteria, enforces change documentation when files are modified, and routes diagnostic feedback to responsible dependency nodes.

By providing dedicated tools for verification inspection, milestone advancement, clean submission, failure attribution, and work acquisition, the run controller couples session conclusion to empirical validation and structured provenance.

## Factored Contracts

### Typing

- A resolve tool is a tool defining a resolve target parameter identifying the active node being resolved.
- The check files tool is an argument-free tool named check_files.
- The advance tool is an argument-free tool named advance.
- The submit tool is a resolve tool specifying a change summary parameter.
- The fail tool is a resolve tool specifying an explanation parameter.
- The blame tool is a resolve tool specifying a blame target parameter and an explanation parameter.
- The get work tool specifies a max batch size parameter.

### Contracts

- The run controller exposes verification checks that validate session criteria. [expose_verification_checks]
- The run controller caches verification evaluation results alongside target node file hashes. [cache_verification_results]
- The run controller reuses cached verification outcomes when no workspace files have been updated. [reuse_cached_verification_outcome]
- The check files tool updates verification results when results are outdated. [check_files_updates_outdated_results]
- The check files tool evaluates verification checks across open targets and modified workspace files. [check_files_evaluates_checks]
- The check files tool presents aggregated verification outcomes to the agent. [check_files_presents_outcomes]
- The check files tool tracks last tested file hashes. [check_files_tracks_tested_hashes]
- The check files tool fails when verification fails. [check_files_fails_on_verification_failure]
- The run controller initializes session tools upon agent session entry. [initialize_session_tools_on_entry]
- The run controller unconditionally installs the submit tool, fail tool, check files tool, get work tool, and blame tool. [unconditionally_install_session_tools]
- The run controller installs an advance tool when guide step mode is active. [install_advance_tool_when_step_mode]
- The advance tool coordinates step progression through guide delivery upon passing verification. [advance_tool_coordinates_step_progression]
- A resolve tool produces a terminating response when all active nodes are resolved. [resolve_tool_terminates_when_all_resolved]
- A resolve tool produces a non-terminating response when other active nodes remain. [resolve_tool_lists_remaining_nodes]
- The submit tool concludes active nodes upon passing verification. [submit_concludes_nodes_on_pass]
- The submit tool marks the resolve target clean in the current get work turn. [submit_marks_target_clean]
- The submit tool enforces change documentation. [submit_enforces_change_documentation]
- The fail tool terminates the run in failure. [fail_terminates_run_in_failure]
- The blame tool attributes task failure to an upstream dependency node. [blame_attributes_upstream_failure]
- The get work tool retrieves active dirty nodes. [get_work_retrieves_dirty_nodes]
- The get work tool materializes startup templates. [get_work_materializes_templates]
- The get work tool delivers the session task prompt. [get_work_delivers_task_prompt]
- The get work tool specifies a follow-up execution of the advance tool when the guide is in step mode. [get_work_specifies_advance_followup_in_step_mode]

### Woven Contracts

- Session outcome tools are initialized upon session entry, unconditionally installing termination and verification tools while gating the advance tool behind step mode. [initialize_session_tools_on_entry, unconditionally_install_session_tools, install_advance_tool_when_step_mode, tool_provider: [install_tools]]
- The check files tool evaluates session verification checks, caching results against file hashes and reporting outcomes or failures. [expose_verification_checks, cache_verification_results, reuse_cached_verification_outcome, check_files_updates_outdated_results, check_files_evaluates_checks, check_files_presents_outcomes, check_files_tracks_tested_hashes, check_files_fails_on_verification_failure, agent_node_config: [session_config_verification_checks]]
- In guide step mode, the advance tool coordinates progressive milestone advancement through guide delivery upon passing verification. [install_advance_tool_when_step_mode, advance_tool_coordinates_step_progression]
- Concluding tasks via the submit tool validates passing verification, documents modifications, and marks resolved targets clean in the graph. [submit_concludes_nodes_on_pass, submit_marks_target_clean, submit_enforces_change_documentation, dag_storage: [clear_node_messages]]
- Resolving active targets terminates the session when all active nodes are resolved, or produces a non-terminating response listing remaining targets when other nodes remain open. [resolve_tool_terminates_when_all_resolved, resolve_tool_lists_remaining_nodes]
- Attributing task failure via the blame tool records diagnostic explanations blaming upstream dependency nodes. [blame_attributes_upstream_failure, dag_storage: [add_node_messages]]
- The get work tool retrieves ready dirty nodes, materializes starter templates, delivers session prompts, and initiates step guidance when configured. [get_work_retrieves_dirty_nodes, get_work_materializes_templates, get_work_delivers_task_prompt, get_work_specifies_advance_followup_in_step_mode, tool_provider: [call_by_name]]

## Grounding

### Knowledge Provisions

- Evaluates and aggregates session verification checks. [verification_evaluation]
- Coordinates milestone step progression through guide delivery. [advance_step_coordination]
- Concludes active nodes clean in graph storage. [clean_submission]
- Records defect attribution to upstream dependencies. [defect_blame]
- Acquires active dirty nodes and initializes session tasks. [work_acquisition]

### Knowledge Requirements

- Access to dag storage to query nodes and record messages.
  - Deferred: Requires graph storage in implementation.
- Access to session edit manager to inspect modification state and hashes.
  - Deferred: Requires edit manager in implementation.
- Capability to execute external verification commands.
  - Deferred: Requires command execution in implementation.
- Access to guide delivery to manage milestone transitions.
  - Deferred: Requires guide delivery in implementation.
