<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T21:57:18Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Remove the interface-restated edit manager catalog, canonicalize the missing note, and split run-on paragraphs
CODE_HASH: 7d8c07152f45
SPEC_QA_AUDIT: 2026-10-12T21:57:18Z
-->

# sandbox_file_editor_impl implementation component

imports: filesystem_ext, tool_provider, agent_file_alias, agent_node_config, agent_config, src_metadata
implements: sandbox_file_editor

## Purpose

The sandbox_file_editor_impl implementation component realizes targeted in-place text replacement for writable workspace files.

Unchecked writes to source code can introduce partial edits, exceed LLM window constraints, or write to invalid file coordinates. The sandbox_file_editor_impl implementation component provides guarded in-memory and disk operations that validate string uniqueness and check line boundary conditions.

**Out of scope:** The sandbox_file_editor_impl implementation component does not enforce git version control, execute code formatters, or resolve task dependencies; these are handled by other components.

**Delegated:** In-band source code hash checking and metadata parsing are delegated to src_metadata.

## Types and Behavior

The replace file content tool is installed for the agent session to enable targeted text replacement in declared read-write files.

The edit manager determines workspace file writes by comparing current workspace file content against its in-band code hash, increments a file update revision whenever workspace files are updated, and computes the file hash by reading file content from the filesystem at its resolved host path and returning an MD5 hexadecimal digest of that content. The edit manager records the last file read from the file reader or edited by an editing tool as the session's last read or edited file alias.

Editing tools write to read-write files in the workspace.

Editing tool execution fails if:

- The file alias is not a read-write file, reminding the agent that only declared read-write files can be written.

- The edit produces no change to file content, reminding the agent that the edit had no effect.

An editing tool that changes file content writes the updated content to the filesystem, records that workspace file writes occurred, and reminds the agent to verify syntax and type correctness before making further writes. Successful editing tool execution includes a diff delta representation in the response content when delta output is configured. Editing tool responses share the constant suppression key `replace_file_content`.

The replace file content tool is named `replace_file_content`, accepting in sequence a file alias *path* parameter, an integer *start_line* parameter defining the starting line of the search window, an integer *end_line* parameter defining the ending line of the search window, a boolean *allow_multiple* parameter, a text *target_content* parameter specifying the exact text to replace within the search window, and a text *replacement_content* parameter.

The target content parameter configures a *missing note* that produces diagnostic feedback from the supplied parameter names.

The missing note for target content explains that start line and end line only restrict the search window when line range arguments are supplied, and that target content must match existing text to append or insert content when line range arguments are omitted.

Tool execution applies text replacements to designated read-write file content.

Tool execution:

- Implicitly binds the target file to the last file read or edited in the edit manager if that file is a read-write file, informing the agent with a warning that the path was implicitly bound while allowing the tool execution to proceed, and fails if no file has been read or edited or if the last read or edited file is not a read-write file, when the path parameter is omitted.

- Reads the file content from the filesystem, treating a missing file as empty.

- Fails if the start line is less than one or exceeds the total line count plus one, when a start line is provided.

- Fails if the end line is less than one or exceeds the total line count, when an end line is provided.

- Fails if the start line exceeds the end line, when both start line and end line are provided.

- Matches target content by exact matching, falling back to line-by-line whitespace-stripped matching across the search window when exact matching finds no occurrence and multiple replacements are not permitted. The fallback succeeds if and only if exactly one unique line window matches, replacing the single matching occurrence and failing when target content is not found within the designated line range or matches multiple locations within that range.

- Fails if the target content is not found within the designated line range, and replaces every occurrence of the target content within the designated line range, when multiple replacements are permitted.

- Provides failure feedback indicating the first two matching line numbers to assist in narrowing the replacement region and directs the agent to include more surrounding lines in target content or to specify start line and end line, when target content matches multiple locations in the file and multiple replacements are not permitted.

- Provides failure feedback indicating the line numbers where the target content was located, when target content is not found within the designated line range but exists elsewhere in the file.

- Writes the updated file content to the filesystem, creating any missing parent directories, and records that workspace file writes occurred.

Executing can write validates file write access.

Executing can write:

- Fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be written.

- Records the file edit in the edit manager and produces a successful response indicating that write access is permitted, when a declared read-write file is supplied.
