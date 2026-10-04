# sandbox_file_editor_impl implementation component

imports: filesystem_ext, tool_provider, agent_file_alias, agent_node_config, agent_config
implements: sandbox_file_editor

## Intent

Unchecked file overwrites can corrupt source repositories, destroy uncommitted user work, and exhaust token budgets with repetitive full-file payload emissions. The sandbox_file_editor_impl implementation component realizes safe, localized text replacements within bounded line ranges for declared read-write files. By checking line bounds, falling back from exact string matches to whitespace-tolerant line comparisons, and producing contextual line diagnostics when matches are ambiguous or relocated, the editor prevents accidental clobbering while assisting autonomous agents in self-correcting drift.

Furthermore, the implementation tracks revision counters and emits structured diff deltas to minimize conversational overhead.

## Factored Contracts

### Contracts

- The edit manager provides the replace file content tool when mcp mode is inactive. [provide_tool_when_mcp_inactive]
- The edit manager installs no editing tools when mcp mode is active. [install_no_tools_when_mcp_active]
- At session initialization, initial content baselines are recorded for active read-write files. [record_initial_content_baselines]
- The edit manager compares current workspace file content against initial content before editing. [compare_current_against_initial_content]
- The edit manager increments the file update revision whenever workspace files are updated. [increment_revision_on_file_update]
- The edit manager computes the file hash by returning an MD5 hexadecimal digest of content read from the filesystem. [compute_md5_file_hash]
- Editing tool execution fails when the target file is not a read-write file. [fail_when_target_not_read_write]
- Editing tool execution reminds the agent that only declared read-write files can be written when the target file is not a read-write file. [remind_only_read_write_writable]
- Editing tool execution fails when the edit produces no change to file content. [fail_when_edit_produces_no_change]
- Editing tool execution reminds the agent that no-op edits will fail when the edit produces no change. [remind_no_op_edits_fail]
- Successful editing tool execution writes updated file content to the filesystem. [write_updated_content_on_success]
- Successful editing tool execution creates missing parent directories. [create_missing_parent_dirs_on_success]
- Successful editing tool execution records that workspace file writes occurred. [record_writes_occurred_on_success]
- Successful editing tool execution reminds the agent to call check file to verify syntax and types. [remind_call_check_file]
- Successful editing tool execution includes a diff delta representation in the response content when configured to produce delta output. [include_diff_delta_when_configured]
- Editing tool responses share the constant suppression key "replace_file_content". [share_replace_file_content_suppression_key]
- The missing message function explains that start line and end line only restrict the search window when line range arguments are supplied. [explain_line_range_restrictions]
- The missing message function explains that target content must match existing text to append or insert content when line range arguments are omitted. [explain_append_insert_matching]
- When the path parameter is omitted and the last read or edited file is a read-write file, tool execution binds the target file to the last read or edited file. [implicitly_bind_last_read_or_edited_file]
- When the path parameter is omitted and implicitly bound, tool execution informs the agent with a warning in the response content. [warn_when_path_implicitly_bound]
- When the path parameter is omitted and no file was read or edited, tool execution fails. [fail_when_path_omitted_and_no_last_file]
- When the path parameter is omitted and the last read or edited file is not a read-write file, tool execution fails. [fail_when_path_omitted_and_last_not_read_write]
- Tool execution treats missing files read from the filesystem as empty. [treat_missing_file_as_empty]
- When a start line is provided, tool execution fails if the start line is less than one. [fail_when_start_line_less_than_one]
- When a start line is provided, tool execution fails if the start line exceeds the total line count plus one. [fail_when_start_line_exceeds_line_count_plus_one]
- When an end line is provided, tool execution fails if the end line is less than one. [fail_when_end_line_less_than_one]
- When an end line is provided, tool execution fails if the end line exceeds the total line count. [fail_when_end_line_exceeds_line_count]
- When a start line and an end line are provided, tool execution fails if the start line exceeds the end line. [fail_when_start_exceeds_end]
- Tool execution matches target content using exact matching. [match_target_content_exactly]
- When exact matching finds zero occurrences and allow multiple is false, tool execution falls back to line-by-line whitespace-stripped matching. [fallback_whitespace_stripped_matching]
- Whitespace-stripped fallback succeeds if and only if exactly one unique line window matches after stripping leading and trailing whitespace from each line. [whitespace_fallback_succeeds_on_single_match]
- When allow multiple is false, tool execution fails if target content is not found within the search window. [fail_when_not_found_single]
- When allow multiple is false, tool execution fails if target content matches multiple locations within the search window. [fail_when_multiple_matches_single]
- When allow multiple is false, tool execution replaces the single matching occurrence on success. [replace_single_match_on_success]
- When allow multiple is true, tool execution fails if target content is not found within the search window. [fail_when_not_found_multiple]
- When allow multiple is true, tool execution replaces all occurrences of target content within the search window. [replace_all_matches_when_allow_multiple]
- When target content matches multiple locations and allow multiple is false, failure feedback indicates the first two matching line numbers. [feedback_first_two_matching_lines]
- When target content is not found in the search window but exists elsewhere in the file, failure feedback indicates the line numbers where target content was located. [feedback_relocated_lines_when_outside_range]
- The can write operation fails when the target path is not a declared read-write file. [can_write_fails_when_not_read_write]
- When a declared read-write file is supplied, the can write operation records the file edit. [can_write_records_file_edit]
- When a declared read-write file is supplied, the can write operation produces a successful response indicating write access is permitted. [can_write_produces_success_response]

## Woven Contracts

- Validating write access confirms access and records file edits for declared read-write files, but rejects undeclared targets. [can_write_fails_when_not_read_write, can_write_records_file_edit, can_write_produces_success_response, remind_only_read_write_writable, sandbox_file_editor: [can_write_validates_access]]
- Missing path arguments default to the last read or edited read-write file with an advisory warning, failing if no valid file history exists. [implicitly_bind_last_read_or_edited_file, warn_when_path_implicitly_bound, fail_when_path_omitted_and_no_last_file, fail_when_path_omitted_and_last_not_read_write, sandbox_file_editor: [track_last_read_or_edited]]
- Line search windows are validated against file bounds, rejecting non-positive or inverted bounds before matching proceeds. [fail_when_start_line_less_than_one, fail_when_start_line_exceeds_line_count_plus_one, fail_when_end_line_less_than_one, fail_when_end_line_exceeds_line_count, fail_when_start_exceeds_end]
- Target content matching attempts exact matching first, falling back to whitespace-tolerant matching when single replacements are requested. [match_target_content_exactly, fallback_whitespace_stripped_matching, whitespace_fallback_succeeds_on_single_match]
- Ambiguous or missing target content triggers detailed line location diagnostics to guide correction. [fail_when_not_found_single, fail_when_multiple_matches_single, feedback_first_two_matching_lines, feedback_relocated_lines_when_outside_range]
- Successful replacements update the filesystem, advance the update revision, and emit reminders to verify syntax with check file. [write_updated_content_on_success, create_missing_parent_dirs_on_success, record_writes_occurred_on_success, remind_call_check_file, increment_revision_on_file_update, share_replace_file_content_suppression_key, sandbox_file_editor: [replace_content_in_line_range, replace_multiple_when_permitted]]
