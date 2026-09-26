# sandbox_file_reader interface component

imports: agent_session, agent_file_alias, tool_provider, file_paths

## Assumptions and Requirements

### Requirements

1. The read manager is an agent session service that regulates file reading.
2. The view file tool is an agent session tool that reads the content of a file specified by its file alias path parameter.
3. The search tool is an agent session tool that searches pattern matches across the session's read-only and read-write files according to its regex pattern parameter.
4. The read manager exposes the session read-only files and read-write files.
5. The read manager checks read access for a workspace path to validate external file access, confirming access for declared files while failing with guidance listing readable file aliases when access is disallowed.

## Grounding Facts

### Knowledge Needed

- Session read-only and read-write files.
- File alias path and line offset parameters.
- Search regex pattern.

### Actions Needed

- Read file content within requested line ranges.
- Search patterns across session files.
- Validate workspace path read access.
