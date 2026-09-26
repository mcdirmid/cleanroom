# sandbox_file_reader_impl implementation component

imports: agent_session, filesystem_ext, tool_provider, agent_file_alias, agent_node_config, agent_config, template_format, sandbox_file_editor, file_paths
implements: sandbox_file_reader

## Purpose

The sandbox_file_reader_impl implementation component realizes workspace read tools with strict edit-safety guardrails, agent self-correction feedback, and host path isolation.

Autonomous agents require structured access to workspace files, but naive whole-file reads risk flooding prompt context and enabling unanchored edits across writable targets. When errors occur, silent failures or uninformative exceptions cause agents to hallucinate corrective actions or become stuck in repetitive loops. The sandbox_file_reader_impl implementation component enforces deterministic preconditions and rich recovery feedback on each read action, compelling the agent to maintain precise intent while safeguarding the session from environment path leakage and premature instruction access.

**Out of scope:** The sandbox_file_reader_impl implementation component does not deliver progressive workflow instructions, advance workflow execution, or execute file writes; these are handled by other components.

## Types and Behavior

The read manager exposes declared read-only files and read-write files to anchor access permissions to target boundaries.

The view file tool is named `view_file`, accepting a file alias path parameter to read declared workspace files. Tool availability depends on session interaction mode: in standard mode when mcp mode is inactive, the view file tool is installed for the agent session to keep agent context focused on declared files; when mcp mode is active, external protocol servers manage tools directly, so tool installation is omitted. The search tool is omitted from installation.

Tool execution:

- Reads file content from the filesystem, formatting lines with one-indexed right-aligned line numbers followed by a colon and space to enable precise, line-bounded edits.

- Evaluates template placeholders in read-only markdown files ending with `.md` with session template parameters after filtering out paragraphs beginning with `> META:`, presenting rendered instructions to the agent.

- Accommodates uncreated workspace targets by treating missing read-write files as having empty content, while failing with a response guiding agent recovery when a required read-only file is missing from disk.

- Establishes the read file as the session's last read or written file upon successful execution, which can anchor subsequent file-based operations.

To prevent context clutter across multi-turn interactions, responses for read-write files carry a suppression key matching the file relative path so that repeated reads supersede earlier content, whereas responses for read-only files omit suppression keys and sanitize host paths to preserve reference context and prevent environment leakage.

The *regex pattern parameter type* is a parameter type that converts a wire type string into a regex pattern.

The search tool is named `search_files`, accepting a regex pattern parameter to discover text patterns across declared workspace files while enforcing edit guardrails.

Tool execution:

- Rejects malformed search queries by failing when given an invalid regex pattern.

- Facilitates contract and reference discovery by searching across read-only files in the filesystem, providing matched line contents and line numbers sanitized to mask host paths on successful execution.

- Enforces edit safety by searching across read-write files in the filesystem and stating that matches were found but cannot be displayed, preventing unanchored edits without reading the target file directly through the view file tool.
