# sandbox_file_reader_impl implementation component

imports: agent_session, filesystem_ext, tool_provider, agent_file_alias, agent_node_config, agent_config, template_format, sandbox_file_editor, file_paths
implements: sandbox_file_reader

## Assumptions and Requirements

### Requirements

1. The view file tool is installed for the agent session when mcp mode is inactive.
   - (woven with [sandbox_file_reader: 2], [agent_config: 6], [tool_provider: 3]): When mcp mode is inactive, installs the view file tool for the agent session to keep agent context focused on declared files.
   - (woven with [sandbox_file_reader: 3]): Omits the search tool from installation.
   - (woven with [agent_config: 6]): When mcp mode is active, omits tool installation.

2. The read manager exposes declared file sets to anchor access permissions to target boundaries.
   - (woven with [sandbox_file_reader: 4], [agent_node_config: 8, 9]): Resolves declared read-only files and read-write files.

3. The view file tool is named `view_file` and reads declared workspace files.
   - (woven with [sandbox_file_reader: 2], [sandbox_file_editor: 7]): Establishes the read file as the session's last read or written file upon successful execution to anchor subsequent file-based operations.
   - (woven with [sandbox_file_reader: 2], [template_format: 1, 2, 3, 4], [agent_node_config: 12]): Reads file content from the filesystem, formatting lines with one-indexed right-aligned line numbers followed by a colon and space to enable precise, line-bounded edits, and evaluating template placeholders in read-only markdown files ending with `.md` with session template parameters after filtering out paragraphs beginning with `> META:` to present rendered instructions.
   - (woven with [tool_provider: 14]): Treats a read-write file as having empty content when the target file does not exist on disk to accommodate uncreated workspace targets, and fails with a response guiding agent recovery when reading a missing read-only file.
   - (woven with [tool_provider: 15], [agent_file_alias: 6]): Responses for read-write files carry a suppression key matching the file's relative path so that repeated reads supersede earlier content to prevent multi-turn context clutter, while responses for read-only files omit suppression keys and sanitize host paths to preserve reference context and prevent environment leakage.

4. The read manager checks read access for a workspace path to validate external file access.
   - (woven with [sandbox_file_reader: 5], [agent_file_alias: 4, 5], [agent_node_config: 8, 9], [tool_provider: 14]): Fails with a response guiding agent recovery, reminding the agent that only declared files can be read and listing available readable file aliases, when an undeclared workspace path is supplied, to redirect the agent to valid targets.
   - (woven with [sandbox_file_reader: 5], [tool_provider: 13]): Produces a successful response indicating that access is permitted, when a declared workspace path is supplied.

5. The regex pattern parameter type converts a wire type string into a regex pattern.
   - (woven with [tool_provider: 8]): Converts a wire type string into a regex pattern.

6. The search tool is named `search_files` and searches pattern matches across files while enforcing edit guardrails.
   - (woven with [sandbox_file_reader: 3], [tool_provider: 14]): Searches for regex pattern matches across the read-only files and read-write files in the filesystem, failing when given an invalid regex pattern to reject malformed queries.
   - (woven with [sandbox_file_reader: 3], [agent_file_alias: 6], [tool_provider: 13]): Provides matched line contents and line numbers for read-only files, sanitized to mask host paths, on successful execution to facilitate contract and reference discovery.
   - (woven with [sandbox_file_reader: 3], [tool_provider: 13]): States that matches were found but cannot be displayed for read-write files, preventing unanchored edits without reading the target file directly through the view file tool.

## Grounding Facts

### Knowledge Needed

- Mode flags from `agent_config` (`mcp_mode`).
- Read-only and read-write files from `agent_node_config`.
- Workspace root and aliases from `agent_file_alias`.
- Template parameters from `agent_node_config`.
- Line numbering format and template rendering rules from `template_format`.

### Actions Needed

- Read file content via `filesystem_ext`.
- Render markdown templates and format line numbers.
- Record last read file on `sandbox_file_editor`.
- Check and validate workspace path read access.
- Execute regex pattern searches across files.
