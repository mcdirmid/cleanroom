# sandbox_file_editor_impl implementation component

imports: filesystem_ext, tool_provider, agent_file_alias, agent_node_config, agent_config, template_format
implements: sandbox_file_editor

## Purpose

The sandbox_file_editor_impl implementation component realizes targeted in-place text replacement for writable workspace files.

Unchecked modifications to source code can introduce partial edits, exceed LLM window constraints, or write to invalid file coordinates. The sandbox_file_editor_impl implementation component provides guarded in-memory and disk operations that validate string uniqueness, check line boundary conditions, and perform atomic template initialization for newly configured tasks.

**Out of scope:** The sandbox_file_editor_impl implementation component does not enforce git version control, execute code formatters, or resolve task dependencies; these are handled by other components.

## Types and Behavior

The edit manager provides the replace file content tool for the agent session. Materializing templates retrieves configured templates from the node config, formats initial template content using the template formatter with session template parameters, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, and writes formatted template content for missing files while preserving existing files.

The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing, tracks a file update revision that increments whenever workspace files are updated, and exposes read-write files locked against modification, supporting locking and unlocking individual read-write files. The edit manager tracks the last read or edited file alias across the session, recording file reads from the file reader and file edits from editing tools.

Editing tools modify read-write files in the workspace.

Before modifying a file, editing tool execution fails if:

- The file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.

- The file alias is locked against modification, reminding the agent that files that have been the target of a submit, fail, or blame cannot be modified.

- The edit produces no change to file content, reminding the agent that the edit had no effect and such edits will fail.

On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and reminds the agent to call the check file tool to verify syntax and type correctness before making further modifications. When configured to produce delta output, successful editing tool execution includes a diff delta representation in the response content. Editing tool responses share a constant suppression key replace_file_content.

The replace file content tool is named `replace_file_content`, accepting in sequence an optional file alias *path* parameter, an integer *start_line* parameter, an integer *end_line* parameter, a boolean *allow_multiple* parameter, a text *target_content* parameter, and a text *replacement_content* parameter. Tool execution:

- Implicitly binds the target file to the last file read or edited in the edit manager if that file is a read-write file, informs the agent with a warning in the response content that the path was implicitly bound while allowing the tool execution to proceed, or fails if no file has been read or edited or if the last read or edited file is not a read-write file, when the path parameter is omitted.

- Reads the file content from the filesystem, treating missing files as empty.

- Fails if the start line is less than one or exceeds the total line count plus one, when a start line is provided.

- Fails if the end line is less than one or exceeds the total line count, when an end line is provided.

- Fails if the start line exceeds the end line, when both start line and end line are provided.

- Fails if the target content is not found within the designated line range or matches multiple locations within the designated line range, and on success replaces the single matching occurrence, when allow multiple is not set or false.

- Fails if the target content is not found within the designated line range, and replaces all occurrences of the target content within the designated line range, when allow multiple is true.

- Provides failure feedback indicating the first two matching line numbers to assist in narrowing the replacement region and instructs the agent to include more surrounding lines in target_content or specify start_line and end_line, when target content matches multiple locations in the file and allow multiple is false.

- Provides failure feedback indicating the line numbers where the target content was located, when target content is not found within the designated line range but exists elsewhere in the file.

- Specifies a follow-up execution of the view file tool on the target file with reasoning text indicating that the target content was not found, when target content is not found anywhere in the file.

- Writes the updated file content to the filesystem, creating any missing parent directories, and records that workspace file modifications occurred on success.
