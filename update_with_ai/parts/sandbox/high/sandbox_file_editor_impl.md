# sandbox_file_editor_impl implementation component

imports: filesystem_ext, tool_provider, agent_file_alias, agent_node_config, template_format
implements: sandbox_file_editor

## Purpose

The sandbox_file_editor_impl implementation component realizes targeted in-place text replacement and line updates for writable workspace files.

Unchecked modifications to source code can introduce partial edits, exceed LLM window constraints, or write to invalid file coordinates. The sandbox_file_editor_impl implementation component provides guarded in-memory and disk operations that validate string uniqueness, enforce payload size ceilings, check line boundary conditions, and perform atomic template initialization for newly configured tasks.

**Out of scope:** The sandbox_file_editor_impl implementation component does not enforce git version control, execute code formatters, or resolve task dependencies; these are handled by other components.

## Types and Behavior

The edit manager provides the text replacement tool and line update tool for the agent session. Materializing templates retrieves configured templates from the node config, formats initial template content using the template formatter with session template parameters, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, and writes formatted template content for missing files while preserving existing files. The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing, and tracks a file update revision that increments whenever workspace files are updated. Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.

Editing tools modify read-write files in the workspace.

Before modifying a file, editing tool execution fails if:

- The file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.

- The edit produces no change to file content, reminding the agent that the edit had no effect and such edits will fail.

On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and produces a response specifying a follow-up execution of the read tool on the modified read-write file with line numbers requested, accompanied by a reminder justifying inspecting the updated file.

The text replacement tool is named `replace`, accepting a file alias *file* parameter, a text *target* parameter, and a text *replacement* parameter. Text replacement tool execution reads the file content from the filesystem, failing if the target text exceeds 100,000 characters and reminding the agent that target text for replacement must not exceed 100,000 characters, if the target text is not found in the file content, or if the target text matches multiple locations in the file. On success, the tool replaces the single occurrence of the target text with the replacement text, writes the updated file content to the filesystem, and records that workspace file modifications occurred.

The line update tool is named `update_lines`, accepting a file alias *file* parameter, an integer *start line* parameter, an integer *end line* parameter, and a text *replacement* parameter. Line update tool execution reads the file content from the filesystem, failing if the start line is less than one or exceeds the total line count plus one. When the start line is less than or equal to the end line, line update tool execution fails if the end line exceeds the total line count, and otherwise replaces the lines within the range. When the start line exceeds the end line, the tool inserts the replacement lines before the start line without removing existing lines. Each line of replacement text constitutes a distinct line in the file, ensuring line boundaries remain preserved even if the replacement text lacks a trailing newline. On success, the tool writes the updated file content to the filesystem and records that workspace file modifications occurred.
