# sandbox_file_reader_impl implementation component

imports: filesystem_ext, tool_provider, file_alias, node_config
implements: sandbox_file_reader

## Purpose

The sandbox_file_reader_impl implementation component realizes workspace inspection tools with strict edit-safety guardrails, agent self-correction feedback, and host path isolation.

Permissive or forgiving tool implementations allow agents to drift into ambiguous formatting states, bypass intended procedural phases, or attempt unanchored modifications without adequate context. When errors occur, silent failures or uninformative exceptions cause agents to hallucinate corrective actions or become stuck in repetitive loops. The sandbox_file_reader_impl implementation component enforces deterministic preconditions and rich recovery feedback on each inspection action, compelling the agent to maintain precise intent while safeguarding the session from environment path leakage and premature instruction access.

**Out of scope:** The sandbox_file_reader_impl implementation component does not deliver progressive workflow instructions, advance workflow execution, or execute file modifications; these are handled by other components.

## Types and Behavior

The read manager unconditionally installs the read tool into the tool manager for the agent session and never installs the search tool, obtaining declared read-only files, read-write files, and the guide file, when configured, from the node config.

The read tool is named `read_file`, accepting a file alias *file* parameter and a boolean *line numbers* parameter that must be true when reading read-write files and false or omitted when reading read-only files. The read tool reads file content using filesystem ext at the host path formed from the alias manager workspace root and the bound file workspace path. Successful read tool execution requires:

- Requesting line numbers when reading a read-write file, and omitting line numbers when reading a read-only file; violating either requirement causes execution to fail, and reminds the agent that line numbers must be requested when reading read-write files and omitted when reading read-only files.

- A bound file. If an unbound file is supplied, execution fails with a response guiding agent recovery, and reminds the agent that only declared files can be inspected. This response lists available readable file aliases, and, if the unbound file matches the guide file configured for step-mode, that `advance` must be called to read the guide instead.

Read tool responses for read-write files carry a suppression key matching the file's short name, while responses for read-only files omit suppression keys and sanitize host paths through the alias manager.

The *regex pattern converter* is a parameter converter for regex patterns that converts a wire type string into a regex pattern.

The search tool is named `search_files`, accepting a regex pattern *pattern* parameter using the regex pattern converter. The search tool searches for regex pattern matches across the read-only files and read-write files using filesystem ext. Search tool execution fails when given an invalid regex pattern. On successful execution, the response provides matched line contents and line numbers for read-only files, sanitized by the alias manager to mask host paths. For read-write files, the response only says that matches were found but cannot be displayed to prevent unanchored edits.
