# file_reader_impl

imports: tool_provider, virtual_file_name, file_reader
types from tool_provider: tool metadata, tool result, tool failure
types from virtual_file_name: virtual file name, virtual file mapper
types from file_reader: file reader factory, file reader, file reader configuration, read-only file, read-write file, file read tool, file search tool, session-start read
implements: file reader factory

## Behavior

- Creating a *file reader* through a *file reader factory* yields a *file reader* configured with declared permissions and path mappings using a *virtual file mapper*.
- A *session-start read* is formatted as a `read_file` *tool result* containing the plain content of a declared *read-only file*.
- The *tool metadata* for the *file read tool* specifies the name `read_file`, a *virtual file name* parameter, and a line-numbering flag indicating explicit *agent* intent for line-numbered output.
- Executing the *file read tool* on an existing *read-write file* with the line-numbering flag disabled produces a *tool failure* requiring line numbers for writable files.
- Executing the *file read tool* on a *read-only file* with the line-numbering flag enabled produces a *tool failure* requiring plain content for read-only files.
- Executing the *file read tool* on an unmapped or missing *virtual file name* produces a *tool failure* listing available readable files.
- Executing the *file read tool* on a guide configured for progressive step delivery produces a *tool failure* explaining that the guide is delivered progressively via advance execution.
- The *tool metadata* for the *file search tool* specifies the name `search_files`, a regex pattern, an optional search path defaulting to the workspace, and optional offset and limit parameters.
- Executing the *file search tool* produces matching lines with line numbers for *read-only files*, and match count notes for *read-write files*, formatted with *virtual file names* using a *virtual file mapper*.
- Transforming text during sanitization replaces host paths matched in descending order of length using a *virtual file mapper*.
