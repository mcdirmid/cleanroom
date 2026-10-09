<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 2dae2e447223
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# sandbox_file_reader_impl implementation component

imports: agent_session, filesystem_ext, tool_provider, agent_file_alias, agent_node_config, template_format, sandbox_file_editor, file_paths
implements: sandbox_file_reader

## Intent

Autonomous agents require structured access to workspace files, but naive whole-file reads risk flooding prompt context and enabling unanchored edits across writable targets. When errors occur, silent failures or uninformative exceptions cause agents to hallucinate corrective actions or become stuck in repetitive loops. The sandbox_file_reader_impl implementation component enforces deterministic preconditions and rich recovery feedback on each read action, compelling the agent to maintain precise intent while safeguarding the session from environment path leakage and premature instruction access.

By formatting lines with right-aligned line numbers, filtering metadata paragraphs, substituting template parameters in read-only guides, and withholding line contents for read-write search matches, the implementation enforces strict edit-safety guardrails and host path isolation across all agent turns.

## Factored Contracts

### Contracts

- The view file tool is named `view_file`. [view_file_name]
- The view file tool is installed for the agent session. [view_file_installed]
- The search tool is named `search_files`. [search_files_name]
- The search tool is omitted from installation. [search_files_omitted]
- The regex pattern parameter type converts a wire type string into a regex pattern. [convert_regex_pattern]
- Reading file content formats lines with one-indexed right-aligned line numbers followed by a colon and space. [format_numbered_lines]
- Template evaluation filters out paragraphs beginning with `> META:` in read-only markdown files. [filter_meta_paragraphs]
- Template evaluation renders template placeholders in read-only markdown files ending with `.md` using session template parameters. [render_markdown_templates]
- Reading a missing read-write file returns empty content. [read_missing_rw_empty]
- Successful file reading records the read file as the session's last read or written file. [record_read_file]
- Tool responses for read-write files carry a suppression key matching the file relative path. [rw_response_suppression_key]
- Tool responses for read-only files omit suppression keys. [ro_response_omit_suppression_key]
- Tool responses for read-only files sanitize host paths. [ro_response_sanitize_paths]
- Tool execution fails with recovery guidance when a read-only file is missing from disk. [missing_ro_file_fails]
- The regex pattern parameter type fails when given an invalid regex pattern. [invalid_regex_pattern_fails]
- Searching read-only files provides sanitized matched line contents. [search_ro_returns_contents]
- Searching read-only files provides matched line numbers. [search_ro_returns_line_numbers]
- Searching read-write files states that matches were found without displaying line contents. [search_rw_withholds_contents]

### Woven Contracts

- The view_file tool is installed for the agent session to provide structured file access. [view_file_name, view_file_installed, tool_provider: [install_tools]]
- Search tool search_files is defined but omitted from installation across all session modes. [search_files_name, search_files_omitted]
- Read file content formats lines with one-indexed right-aligned line numbers, filters metadata paragraphs, and renders markdown templates for read-only files. [format_numbered_lines, filter_meta_paragraphs, render_markdown_templates, template_format: [format_template_text, substitute_bound_placeholders]]
- Responses for read-write files carry suppression keys to supersede earlier turns, while read-only responses omit suppression keys and sanitize host paths. [rw_response_suppression_key, ro_response_omit_suppression_key, ro_response_sanitize_paths, tool_provider: [supersede_by_key], agent_file_alias: [sanitize_mask_ws_paths, sanitize_mask_preceding_prefixes]]
- When reading a missing read-write file, empty content is returned, whereas a missing read-only file fails with recovery guidance. [read_missing_rw_empty, missing_ro_file_fails, tool_provider: [call_improper_fails, failed_call_feedback]]
- Upon successful file reading, the file is recorded as the session's last read or written file. [record_read_file, sandbox_file_editor: [track_last_read_or_edited, record_file_read_op]]
- When converting an invalid regex search pattern, conversion fails with diagnostic feedback. [convert_regex_pattern, invalid_regex_pattern_fails, tool_provider: [convert_failure_error]]
- When searching declared files, read-only matches return sanitized lines while read-write matches withhold line contents to enforce edit safety. [search_ro_returns_contents, search_ro_returns_line_numbers, search_rw_withholds_contents, agent_file_alias: [sanitize_mask_ws_paths]]

## Grounding

### Knowledge Provisions

- Exposes declared read-only session files. [ro_files_provision]
- Exposes declared read-write session files. [rw_files_provision]
- Checks read access for workspace paths. [read_access_check]
- Reads file content for specified file alias paths. [view_file_capability]
- Searches pattern matches across declared session files. [search_files_capability]

### Inherited Deferred Requirements

- Access to underlying filesystem to inspect and read file contents.
  - Grounded: [filesystem_ext: [filesystem_operations]]
- Access to session node configuration to resolve declared files.
  - Grounded: [agent_node_config: [node_configuration_service]]
- Capability to record file reads in session edit manager.
  - Grounded: [sandbox_file_editor: [update_revision_tracking]]

### Knowledge Requirements

- Formatting line numbered output with metadata filtering and template rendering.
  - Grounded: [template_format: [template_formatting], agent_file_alias: [alias_mapping]]
