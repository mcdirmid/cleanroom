# sandbox_file_editor_impl implementation component

imports: filesystem_ext, tool_provider, file_alias, node_config
implements: sandbox_file_editor

## Purpose

The sandbox_file_editor_impl implementation component realizes targeted in-place text replacement and line updates for writable workspace files.

Unchecked modifications to source code can introduce partial edits, exceed LLM window constraints, or write to invalid file coordinates. The sandbox_file_editor_impl implementation component provides guarded in-memory and disk operations that validate string uniqueness, enforce payload size ceilings, check line boundary conditions, and perform atomic template initialization for newly configured tasks.

**Out of scope:** The sandbox_file_editor_impl implementation component does not enforce git version control, execute code formatters, or resolve task dependencies; these are handled by other components.

## Types and Behavior

The edit manager provides the text replacement tool and line update tool for the agent session. Materializing templates retrieves configured templates, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, and writes initial template content for missing files while preserving existing files. The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing, and tracks a file update revision that increments whenever workspace files are updated. Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.

The text replacement tool is named `replace`, accepting a file alias *file* parameter, a text *target* parameter, and a text *replacement* parameter. Executing the text replacement tool reads the file content from the filesystem, failing if the target text exceeds 100,000 characters and reminding the agent that target text for replacement must not exceed 100,000 characters, if the target text is not found in the file content, or if the target text matches multiple locations in the file. On success, the tool replaces the single occurrence of the target text with the replacement text, writes the updated file content to the filesystem, and records that workspace file modifications occurred.

The line update tool is named `update_lines`, accepting a file alias *file* parameter, an integer *start line* parameter, an integer *end line* parameter, and a text *replacement* parameter. Executing the line update tool reads the file content from the filesystem, failing if the start line is less than one or exceeds the total line count plus one. When the start line is less than or equal to the end line, executing the line update tool fails if the end line exceeds the total line count, and otherwise replaces the lines within the range. When the start line exceeds the end line, the tool inserts the replacement lines before the start line without removing existing lines. On success, the tool writes the updated file content to the filesystem and records that workspace file modifications occurred.
