# sandbox_file_reader_impl implementation component

imports: filesystem_ext, tool_provider, file_alias, node_config, template_format
implements: sandbox_file_reader

## Purpose

The sandbox_file_reader_impl implementation component realizes workspace inspection tools with strict edit-safety guardrails, agent self-correction feedback, and host path isolation.

Permissive or forgiving tool implementations allow agents to drift into ambiguous formatting states, bypass intended procedural phases, or attempt unanchored modifications without adequate context. When errors occur, silent failures or uninformative exceptions cause agents to hallucinate corrective actions or become stuck in repetitive loops. The sandbox_file_reader_impl implementation component enforces deterministic preconditions and rich recovery feedback on each inspection action, compelling the agent to maintain precise intent while safeguarding the session from environment path leakage and premature instruction access.

**Out of scope:** The sandbox_file_reader_impl implementation component does not deliver progressive workflow instructions, advance workflow execution, or execute file modifications; these are handled by other components.

## Types and Behavior

The read manager provides the read tool for the agent session and omits the search tool, obtaining declared read-only files, read-write files, and the guide file, when configured, from the session node configuration. The read manager identifies that read-write files and source code files require line numbers when read, identifying files ending with `.py` as source code files.

The read tool is named `read_file`, accepting a file alias *file* parameter and a boolean *line numbers* parameter that must be true when reading read-write files and source code files, and false or omitted when reading non-source read-only files. The read tool reads file content from the filesystem at the host path formed from the alias manager workspace root and the bound file workspace path, formatting read-only markdown files ending with `.md` using the template formatter with session template parameters after filtering out paragraphs beginning with `> META:`. Successful read tool execution requires:

- Requesting line numbers when reading a read-write file or source code file, and omitting line numbers when reading a non-source read-only file; violating either requirement causes execution to fail, reminds the agent that line numbers must be requested when reading read-write files and source code files and omitted when reading non-source read-only files, and specifies a follow-up execution of the read tool on the file with line numbers requested for a read-write file or source code file and line numbers omitted for a non-source read-only file.

- A bound file. If an unbound file is supplied, execution fails with a response guiding agent recovery, and reminds the agent that only declared files can be inspected. This response lists available readable file aliases, and, if the unbound file matches the guide file configured for step-mode, that `advance` must be called to read the guide instead.

Read tool responses for read-write files carry a suppression key matching the file's short name, while responses for read-only files omit suppression keys and sanitize host paths through the alias manager.

The *regex pattern converter* is a parameter converter for regex patterns that converts a wire type string into a regex pattern.

The search tool is named `search_files`, accepting a regex pattern *pattern* parameter using the regex pattern converter. The search tool searches for regex pattern matches across the read-only files and read-write files in the filesystem. Search tool execution fails when given an invalid regex pattern. On successful execution, the response provides matched line contents and line numbers for read-only files, sanitized by the alias manager to mask host paths. For read-write files, the response only says that matches were found but cannot be displayed to prevent unanchored edits.
