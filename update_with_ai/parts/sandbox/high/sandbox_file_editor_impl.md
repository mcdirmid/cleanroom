# sandbox_file_editor_impl implementation component

imports: filesystem_ext, tool_provider, agent_file_alias, agent_node_config, agent_config, template_format
implements: sandbox_file_editor

## Purpose

The sandbox_file_editor_impl implementation component realizes targeted in-place text replacement for writable workspace files.

Unchecked modifications to source code can introduce partial edits, exceed LLM window constraints, or write to invalid file coordinates. The sandbox_file_editor_impl implementation component provides guarded in-memory and disk operations that validate string uniqueness, check line boundary conditions, and perform atomic template initialization for newly configured tasks.

**Out of scope:** The sandbox_file_editor_impl implementation component does not enforce git version control, execute code formatters, or resolve task dependencies; these are handled by other components.

## Types and Behavior

The edit manager provides the replace file content tool for the agent session. Materializing templates retrieves configured templates from the node config, formats initial template content using the template formatter with session template parameters, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, and writes formatted template content for missing files while preserving existing files. The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing, tracks a file update revision that increments whenever workspace files are updated, and exposes read-write files locked against modification, supporting locking and unlocking individual read-write files. Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.

Editing tools modify read-write files in the workspace.

Before modifying a file, editing tool execution fails if:

- The file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.

- The file alias is locked against modification, reminding the agent that files that have been the target of a submit, fail, or blame cannot be modified.

- The edit produces no change to file content, reminding the agent that the edit had no effect and such edits will fail.

- The edit overlaps with auto-generated dependency imports between `# --- DO NOT EDIT: Auto-generated dependencies ---` and `# --- END DO NOT EDIT ---`, reminding the agent that auto-generated dependencies are managed by the build toolchain.

On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and when configured to perform follow-up reads on edits, produces a response specifying a follow-up execution of the view file tool on the modified read-write file, accompanied by a reminder justifying inspecting the updated file. When configured to produce delta output, successful editing tool execution includes a diff delta representation in the response content.

The replace file content tool is named `replace_file_content`, accepting a file alias *path* parameter, a text *target_content* parameter, a text *replacement_content* parameter, an integer *start_line* parameter, an integer *end_line* parameter, and a boolean *allow_multiple* parameter. Replace file content tool execution reads the file content from the filesystem, treating missing files as empty. When a start line is provided, execution fails if the start line is less than one or exceeds the total line count plus one. When an end line is provided, execution fails if the end line is less than one or exceeds the total line count. When both start line and end line are provided, execution fails if the start line exceeds the end line. When allow multiple is not set or false, execution fails if the target content is not found within the designated line range or matches multiple locations within the designated line range, and on success replaces the single matching occurrence. When allow multiple is true, execution fails if the target content is not found within the designated line range, and replaces all occurrences of the target content within the designated line range. On success, the tool writes the updated file content to the filesystem, creating any missing parent directories, and records that workspace file modifications occurred.
