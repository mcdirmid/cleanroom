# sandbox_file_editor_impl implementation component

imports: filesystem_ext, tool_provider, agent_file_alias, agent_node_config, agent_config, template_format
implements: sandbox_file_editor

## Assumptions and Requirements

### Requirements

1. The edit manager provides the replace file content tool for the agent session when mcp mode is inactive.
2. The edit manager installs no editing tools when mcp mode is active.
3. The edit manager provides a can write operation validating write access for a read-write file.
4. Materializing templates retrieves configured templates from node config, formats initial template content using the template formatter with session template parameters, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, writes formatted template content for missing files while preserving existing files, and records initial content baselines for active read-write files.
5. The edit manager exposes whether workspace file writes occurred during the session by comparing current workspace file content against initial content before editing.
6. The edit manager tracks a file update revision that increments whenever workspace files are updated.
7. The edit manager computes the file hash by reading file content from the filesystem at its resolved host path and returning an MD5 hexadecimal digest of the content.
8. The edit manager exposes read-write files locked against write, supporting locking and unlocking individual read-write files.
9. The edit manager tracks the last read or edited file alias across the session, recording file reads from the file reader and file edits from editing tools.
10. Editing tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be written.
11. Editing tool execution fails if the file alias is locked against write, reminding the agent that files that have been the target of a submit, fail, or blame cannot be written.
12. Editing tool execution fails if the edit produces no change to file content, reminding the agent that the edit had no effect.
13. On successful execution, an editing tool writes updated file content to the filesystem, records that workspace file writes occurred, and reminds the agent to call the check file tool to verify syntax and type correctness.
14. When configured to produce delta output, successful editing tool execution includes a diff delta representation in the response content.
15. Editing tool responses share a constant suppression key replace_file_content.
16. The replace file content tool is named replace_file_content, accepting path, start_line, end_line, allow_multiple, target_content, and replacement_content.
17. The target content parameter specifies a missing message function that explains search window and match semantics.
18. Tool execution implicitly binds target file to the last file read or edited if it is a read-write file, warning that the path was implicitly bound, or fails if no file was read or edited or if it is not a read-write file, when path is omitted.
19. Reads file content from filesystem, treating missing files as empty.
20. Validates start line and end line boundaries against total line count.
21. Matches target content using exact matching or line-by-line whitespace-stripped matching when exact match finds zero occurrences and allow multiple is false, succeeding if exactly one unique line window matches.
22. Fails if target content is not found or matches multiple locations when allow multiple is false, providing first two matching line numbers.
23. Fails if target content is not found and replaces all occurrences when allow multiple is true.
24. Writes updated file content to filesystem creating parent directories on success.

## Grounding Facts

### Knowledge Needed

- Mode flags from `agent_config` (`mcp_mode`, `delta_output`).
- Node templates and parameters from `agent_node_config`.
- Workspace root and file aliases from `agent_file_alias`.
- Locked files set.
- Line boundary and target content matching semantics.

### Actions Needed

- Format and materialize initial templates via `template_format`.
- Read and write file content via `filesystem_ext`.
- Compute MD5 content hashes and increment update revision.
- Validate write permissions and locked states.
- Execute line-based or multi-occurrence replacements.
- Generate diff delta representation.
