# sandbox_file_reader_impl implementation component

imports: filesystem_ext, tool_provider, agent_file_alias, agent_node_config, template_format, sandbox_file_editor
implements: sandbox_file_reader

## Purpose

The sandbox_file_reader_impl implementation component realizes workspace inspection tools with strict edit-safety guardrails, agent self-correction feedback, and host path isolation.

Permissive or forgiving tool implementations allow agents to drift into ambiguous formatting states, bypass intended procedural phases, or attempt unanchored modifications without adequate context. When errors occur, silent failures or uninformative exceptions cause agents to hallucinate corrective actions or become stuck in repetitive loops. The sandbox_file_reader_impl implementation component enforces deterministic preconditions and rich recovery feedback on each inspection action, compelling the agent to maintain precise intent while safeguarding the session from environment path leakage and premature instruction access.

**Out of scope:** The sandbox_file_reader_impl implementation component does not deliver progressive workflow instructions, advance workflow execution, or execute file modifications; these are handled by other components.

## Types and Behavior

The read manager provides the view file tool for the agent session and omits the search tool, obtaining declared read-only files, read-write files, and the guide file, when configured, from the session node configuration.

The view file tool is named `view_file`, accepting a file alias *path* parameter using the alias manager. On successful execution, the view file tool records the read file in the edit manager. The view file tool reads file content from the filesystem at the host path formed from the alias manager workspace root and the bound file workspace path, returning the content formatted with one-indexed right-aligned line numbers followed by a colon and space, and formatting read-only markdown files ending with `.md` using the template formatter with session template parameters after filtering out paragraphs beginning with `> META:`. When the target file does not exist on disk, view file tool execution treats a read-write file as having empty content, and fails with a response guiding agent recovery when inspecting a missing read-only file.

Executing the view file tool requires a bound file. If an unbound file is supplied whose relative path or qualified path addresses a module name or ends with `.py` and matches a declared read-only grounding specification ending with `.pyi`, execution resolves to that grounding specification file alias. If an unbound file addresses a test file ending with `_test.py`, execution fails with a response explaining that test files are not inspectable and grounding specifications serve as the contract. Otherwise, supplying an unbound file fails with a response guiding agent recovery, reminding the agent that only declared files can be inspected, listing available readable file aliases, and, if the unbound file matches the guide file configured for step-mode, that `advance` must be called to read the guide instead.

View file tool responses for read-write files carry a suppression key matching the file's relative path, while responses for read-only files omit suppression keys and sanitize host paths through the alias manager.

The *regex pattern parameter type* is a parameter type for regex patterns that converts a wire type string into a regex pattern.

The search tool is named `search_files`, accepting a regex pattern *pattern* parameter using the regex pattern parameter type. The search tool searches for regex pattern matches across the read-only files and read-write files in the filesystem. Search tool execution fails when given an invalid regex pattern. On successful execution, the response provides matched line contents and line numbers for read-only files, sanitized by the alias manager to mask host paths. For read-write files, the response only says that matches were found but cannot be displayed to prevent unanchored edits.
