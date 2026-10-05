<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 20d0208511f4
-->

# sandbox_file_reader interface component

imports: agent_session, agent_file_alias, tool_provider, file_paths

## Intent

Autonomous agents require structured access to workspace files, but naive whole-file reads risk flooding prompt context and enabling unanchored edits across writable targets. Furthermore, when workflows enforce guided step-by-step progression, unconstrained file access risks bypassing phase pacing. The sandbox_file_reader interface component establishes a governed read layer that balances external context injection with safety guardrails, ensuring file read remains scoped to the agent's immediate operational phase.

By restricting access to declared read-only and read-write session files and validating workspace paths prior to inspection, the read manager and its associated tools keep agent interactions safely anchored to active task boundaries.

## Factored Contracts

### Typing

- The view file tool is a tool specifying a file alias path parameter.
- The search tool is a tool specifying a regex pattern parameter.

### Contracts

- A caller supplies a workspace path when checking read access. [check_read_access_supplied]
- An agent session's read manager regulates file reading. [read_mgr_regulates_reading]
- The read manager exposes the session read-only files. [read_mgr_exposes_ro_files]
- The read manager exposes the session read-write files. [read_mgr_exposes_rw_files]
- The read manager checks read access for a workspace path. [read_mgr_checks_read_access]
- An agent session's view file tool reads the content of a file specified by its file alias path parameter. [view_file_reads_content]
- An agent session's search tool searches pattern matches across declared session files. [search_tool_searches_files]
- Read access check confirms access for declared read-only files. [read_access_confirms_ro]
- Read access check confirms access for declared read-write files. [read_access_confirms_rw]
- Read access check fails with guidance listing readable file aliases when access is disallowed. [read_access_fails_with_guidance]
- The search tool searches across the session's read-only files. [search_tool_searches_ro]
- The search tool searches across the session's read-write files. [search_tool_searches_rw]

## Woven Contracts

- When checking read access for a workspace path matching declared files, access is confirmed. [check_read_access_supplied, read_mgr_exposes_ro_files, read_mgr_exposes_rw_files, read_mgr_checks_read_access, read_access_confirms_ro, read_access_confirms_rw]
- When checking read access for an undeclared workspace path, access fails with guidance listing readable file aliases. [check_read_access_supplied, read_mgr_exposes_ro_files, read_mgr_exposes_rw_files, read_mgr_checks_read_access, read_access_fails_with_guidance]
- When executing the view file tool, file content is retrieved for the specified file alias path. \[view_file_reads_content, tool_provider: [call_by_name, call_with_python_bindings]\]
- When executing the search tool, pattern matches are discovered across read-only and read-write files. \[search_tool_searches_files, search_tool_searches_ro, search_tool_searches_rw, tool_provider: [call_by_name, call_with_python_bindings]\]
