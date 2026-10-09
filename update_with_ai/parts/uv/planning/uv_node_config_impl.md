<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: 60cf0aa8e680
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# uv_node_config_impl implementation component

imports: agent_config, dag_storage, file_paths, tool_provider, uv_manifest_loader
implements: agent_node_config, agent_file_alias

## Intent

Multi-turn agent execution within Cleanroom workspaces requires binding node-specific manifest metadata to virtual session boundaries. Individual sessions require hermetic file isolation, mapping relative target sources to read-write paths, expanding direct and transitive dependencies to read-only paths, and isolating local host paths from language model visibility. The uv_node_config_impl implementation component resolves the active target nodes' manifests via the manifest loader, constructs declared file sets and guide bindings for the node config, and maintains minimal unambiguous file aliases and path masking for the alias manager.

By resolving per-node metadata from target manifests, aggregating session parameters across active cleaning batches, and dynamically masking host paths with relative file aliases, the implementation provides consistent session environments.

## Factored Contracts

### Contracts

- The session config resolves configuration parameters for active nodes from target node manifests. [resolve_configuration_parameters]
- The session config dynamically aggregates session parameters across active nodes per node info. [aggregate_session_parameters]
- Loading per node info resolves declared source files and templates into node read-write files and templates. [resolve_node_read_write_files_and_templates]
- Loading per node info resolves declared template parameters into node template parameters. [resolve_node_template_parameters]
- Loading per node info resolves direct dependencies and transitive star dependencies into node read-only files. [resolve_node_read_only_dependencies]
- Loading per node info excludes silent dependencies from node read-only files. [exclude_silent_deps_from_read_only]
- Loading per node info excludes read-write files from node read-only files. [exclude_read_write_from_read_only]
- Loading per node info resolves whether the node allows step mode. [resolve_node_allows_step_mode]
- The node config retrieves the guide target manifest via the manifest loader. [retrieve_guide_target_manifest]
- The node config resolves candidate guide paths from declared guide target source files. [resolve_candidate_guide_paths_from_source_file]
- The node config resolves candidate guide paths from guide target labels. [resolve_candidate_guide_paths_from_label]
- The node config loads guide markdown content by reading the resolved guide file across workspace trees. [load_guide_content_from_resolved_file]
- The node config exposes the unbound guide file from guide target labels. [provide_unbound_guide_file]
- Loading per node info resolves declared feedback dependencies into blame targets mapped to owning nodes. [resolve_node_blame_targets]
- Loading per node info resolves declared verification commands as verification checks. [resolve_node_verification_checks]
- Loading per node info resolves declared source file alias relative paths as the src file alias. [resolve_node_src_file_alias]
- Loading per node info resolves declared verification success messages. [resolve_node_verification_success_message]
- Loading per node info resolves feedback messages from graph storage. [resolve_node_feedback_messages]
- Parsing a task guide extracts the guide summary from content preceding the first section heading. [guide_extract_summary_preceding_first_heading]
- Parsing a task guide extracts the guide summary from content under headings titled "Summary". [guide_extract_summary_under_summary_heading]
- Parsing a task guide captures verification failure instructions when a section heading begins with "Verification failure". [guide_capture_verification_failure_instructions]
- Parsing a task guide creates sequential step sections for subsequent level-two headings. [guide_create_sequential_step_sections]
- Parsing a task guide excludes sections titled "Summary", "Lint checks", or "Verification failure" from step sections. [guide_exclude_metadata_sections_from_steps]
- The node config aggregates read-only files across active nodes, excluding session read-write files. [aggregate_session_read_only_files]
- The node config aggregates read-write files and templates across active nodes. [aggregate_session_read_write_files]
- The node config combines template parameters across active nodes. [combine_session_template_parameters]
- Step mode eligibility is permitted for single-node sessions when the target node allows step mode. [step_mode_eligibility_single_node]
- Step mode is active when permitted by agent configuration with an eligible session lacking feedback. [activate_step_mode_when_criteria_met]
- The node config provides the session guide file and task guide when guide step mode is active. [provide_session_guide_in_step_mode]
- The node config maps each active node to its declared blame targets. [map_session_blame_targets_by_node]
- The node config aggregates verification checks across active nodes. [aggregate_session_verification_checks]
- The node config maps each active node to its verification checks. [map_session_verification_checks_by_node]
- The node config maps each active node to the relative path of its declared source file alias. [map_session_src_file_alias_by_node]
- The node config provides the verification success message from the active node when exactly one node is active. [provide_single_node_verification_success_message]
- The node config combines feedback messages from graph storage across active nodes. [combine_session_feedback_messages]
- The node config maps each active node to its per node info. [map_session_per_node_info_by_node]
- The alias manager generates file aliases with relative paths for accessible workspace files. [generate_relative_file_aliases]
- The alias manager matches relative paths to file aliases when converting wire type strings. [match_relative_paths_to_aliases]
- The alias manager produces unbound files when relative paths are unmapped. [produce_unbound_files_when_unmapped]
- The alias manager replaces matching host paths with relative workspace paths when sanitizing output text. [replace_matching_host_paths_with_relative_paths]
- The alias manager masks occurrences of workspace root path prefixes when sanitizing output text. [strip_workspace_root_prefixes]
- The alias manager masks occurrences of execution root path prefixes when sanitizing output text. [strip_execution_root_prefixes]

### Woven Contracts

- The session config resolves configuration parameters for active nodes from manifests and dynamically aggregates session parameters across per-node metadata. [resolve_configuration_parameters, aggregate_session_parameters, agent_node_config: [session_config_read_only_files, session_config_read_write_files]]
- Loading per-node metadata extracts sources, templates, dependencies, guides, checks, and feedback from manifests and graph storage. [resolve_node_read_write_files_and_templates, resolve_node_template_parameters, resolve_node_read_only_dependencies, exclude_silent_deps_from_read_only, exclude_read_write_from_read_only, resolve_node_allows_step_mode, retrieve_guide_target_manifest, resolve_candidate_guide_paths_from_source_file, resolve_candidate_guide_paths_from_label, load_guide_content_from_resolved_file, provide_unbound_guide_file, resolve_node_blame_targets, resolve_node_verification_checks, resolve_node_src_file_alias, resolve_node_verification_success_message, resolve_node_feedback_messages, uv_manifest_loader: [retrieve_manifest_for_node, populate_agent_storage], dag_storage: [access_node_messages]]
- Declared guide targets retrieve manifests via the manifest loader, resolve candidate paths across workspace trees, read resolved guide files, and provide unbound guide files. [retrieve_guide_target_manifest, resolve_candidate_guide_paths_from_source_file, resolve_candidate_guide_paths_from_label, load_guide_content_from_resolved_file, provide_unbound_guide_file, uv_manifest_loader: [retrieve_manifest_for_node]]
- Task guide content is parsed into summaries, step sections, and verification failure instructions while omitting metadata headings. [guide_extract_summary_preceding_first_heading, guide_extract_summary_under_summary_heading, guide_capture_verification_failure_instructions, guide_create_sequential_step_sections, guide_exclude_metadata_sections_from_steps, agent_node_config: [session_config_guide]]
- Session parameters aggregate active nodes' files, templates, parameters, and checks, activating step mode only for single feedback-free nodes. [aggregate_session_read_only_files, aggregate_session_read_write_files, combine_session_template_parameters, step_mode_eligibility_single_node, activate_step_mode_when_criteria_met, provide_session_guide_in_step_mode, map_session_blame_targets_by_node, aggregate_session_verification_checks, map_session_verification_checks_by_node, map_session_src_file_alias_by_node, provide_single_node_verification_success_message, combine_session_feedback_messages, map_session_per_node_info_by_node, agent_node_config: [session_config_read_only_files, session_config_read_write_files, session_config_templates, session_config_template_params, session_config_verification_checks, session_config_blame_targets, session_config_messages]]
- The alias manager generates relative aliases for active workspace files, resolves wire paths, and sanitizes output text by replacing host path prefixes with relative workspace paths. [generate_relative_file_aliases, match_relative_paths_to_aliases, produce_unbound_files_when_unmapped, replace_matching_host_paths_with_relative_paths, strip_workspace_root_prefixes, strip_execution_root_prefixes, agent_file_alias: [convert_matching_bound_file, convert_unmatched_unbound_file, sanitize_mask_ws_paths, sanitize_mask_preceding_prefixes]]

## Grounding

### Knowledge Provisions

- Session node configuration, file boundary resolution, and virtual alias masking. [uv_node_configuration_service]

### Inherited Deferred Requirements

- Session role configuration and active cleaned nodes.
  - Grounded: [uv_manifest_loader: [manifest_loading_service], dag_storage: [dag_storage_service]]
- Read-only and read-write bound file declarations for active session nodes.
  - Grounded: [uv_manifest_loader: [manifest_loading_service], dag_storage: [dag_storage_service], file_paths: [typed_path_construction]]
- Workspace root absolute path and session declared file boundaries.
  - Grounded: [file_paths: [path_resolution_service, typed_path_construction]]

### Knowledge Requirements

- Manifest lookup and dependency resolution for active session nodes.
  - Grounded: [uv_manifest_loader: [manifest_loading_service], dag_storage: [dag_storage_service]]
- Generating relative file aliases and sanitizing host path occurrences.
  - Grounded: [file_paths: [typed_path_construction, path_resolution_service]]
