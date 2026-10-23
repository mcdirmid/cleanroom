# run_control interface component

## Intent

Autonomous agents operating across complex workspaces require explicit, governed control boundaries to conclude successful tasks, attribute upstream defects, and abort unrecoverable executions. Without centralized outcome coordination, agents risk silent failures, endless re-cleaning loops, or unverified task completions. The run_control interface component establishes a governed execution boundary that coordinates verification checks, advances step guidance, acquires active dirty work, and installs session outcome tools.

By providing dedicated tools for verification inspection, milestone advancement, and work acquisition, the run controller couples session execution to empirical validation and structured provenance.

## Factored Contracts

### Typing

- An agent session's run controller is configured with per-node blame targets and node config verification checks, initializes session tools upon agent session entry, and provides tools for terminating agent sessions and attributing outcomes.
- The check files tool is an argument-free tool named check_files.
- The advance tool is an argument-free tool named advance.
- The get work tool is an argument-free tool named get_work.

### Contracts

- The run controller exposes verification checks that validate session criteria. [expose_verification_checks]
- The run controller caches verification evaluation results alongside target node file hashes. [cache_verification_results]
- The run controller reuses cached verification outcomes when no workspace files have been updated. [reuse_cached_verification_outcome]
- The run controller exposes whether the latest verification evaluation passed. [expose_is_passed]
- The run controller exposes whether target file hashes are unchanged since the last evaluation. [expose_is_unchanged]
- The run controller exposes aggregated diagnostic output from failing verification checks. [expose_diagnostic_output]
- The check files tool updates verification results when results are outdated. [check_files_updates_outdated_results]
- The check files tool evaluates verification checks across open targets and modified workspace files. [check_files_evaluates_checks]
- The check files tool presents aggregated verification outcomes to the agent. [check_files_presents_outcomes]
- The check files tool tracks last tested file hashes. [check_files_tracks_tested_hashes]
- The check files tool fails when verification fails. [check_files_fails_on_verification_failure]
- The run controller initializes session tools upon agent session entry. [initialize_session_tools_on_entry]
- The run controller unconditionally installs the submit tool, fail tool, check files tool, and get work tool. [unconditionally_install_session_tools]
- The get work tool installs the blame tool when any active node has configured blame targets. [install_blame_tool_when_targets_exist]
- The run controller installs an advance tool when guide step mode is active. [install_advance_tool_when_step_mode]
- The advance tool coordinates step progression through guide delivery upon passing verification. [advance_tool_coordinates_step_progression]
- The get work tool retrieves active dirty nodes. [get_work_retrieves_dirty_nodes]
- The get work tool materializes startup templates. [get_work_materializes_templates]
- The get work tool delivers the session task prompt, resolving the primary guide file from provisioned read-only documentation when omitted from node configuration. [get_work_delivers_task_prompt]
- The get work tool specifies a follow-up execution of the advance tool when the guide is in step mode. [get_work_specifies_advance_followup_in_step_mode]

### Woven Contracts

- Session outcome tools are initialized upon session entry, unconditionally installing termination and verification tools while gating the advance tool behind step mode and blame tool behind blame targets. [initialize_session_tools_on_entry, unconditionally_install_session_tools, install_advance_tool_when_step_mode, install_blame_tool_when_targets_exist, tool_provider: [install_tools]]
- The check files tool evaluates session verification checks, caching results against file hashes and reporting outcomes or failures. [expose_verification_checks, cache_verification_results, reuse_cached_verification_outcome, expose_is_passed, expose_is_unchanged, expose_diagnostic_output, check_files_updates_outdated_results, check_files_evaluates_checks, check_files_presents_outcomes, check_files_tracks_tested_hashes, check_files_fails_on_verification_failure, node_config: [session_config_verification_checks]]
- In guide step mode, the advance tool coordinates progressive milestone advancement through guide delivery upon passing verification. [install_advance_tool_when_step_mode, advance_tool_coordinates_step_progression]
- The get work tool retrieves ready dirty nodes, materializes starter templates, delivers session prompts, installs the blame tool if blame targets exist, and initiates step guidance when configured. [get_work_retrieves_dirty_nodes, get_work_materializes_templates, get_work_delivers_task_prompt, get_work_specifies_advance_followup_in_step_mode, install_blame_tool_when_targets_exist, tool_provider: [call_by_name]]

## Grounding

### Knowledge Provisions

- Evaluates and aggregates session verification checks. [verification_evaluation]
- Coordinates milestone step progression through guide delivery. [advance_step_coordination]
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

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:30:00Z
CHANGE: Update run_control planning specification
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
