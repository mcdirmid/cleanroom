<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - virtual_file_name.md
  - file_reader.md
-->

# Implementation LLS: file_reader_impl

## Data Types
```python
from file_reader import FileReader, FileReaderFactory, FileReaderConfig

class _FileReaderImpl(FileReader):
    def __init__(self, config: FileReaderConfig) -> None: ...

class FileReaderFactoryImpl(FileReaderFactory):
    def __init__(self) -> None: ...
```

## Behavioral Description

- `FileReaderFactoryImpl.create_file_reader` constructs a `FileReader` configured with declared file permissions and host path mappings.
- The `read_file` tool specifies metadata with the name `read_file`, a `file_name` (`VirtualFileName`) parameter, and a `line_numbers` boolean flag indicating explicit agent intent.
- Executing `read_file` on an existing `ReadWriteFile` with `line_numbers` disabled produces a `ToolFailure` requiring line numbers for writable files.
- Executing `read_file` on a `ReadOnlyFile` with `line_numbers` enabled produces a `ToolFailure` requiring plain unnumbered content for read-only files.
- Executing `read_file` on a `step_mode_guide` produces a `ToolFailure` explaining that the guide is delivered progressively via advance execution.
- Executing `read_file` on an unmapped or missing `VirtualFileName` produces a `ToolFailure` listing all available readable virtual file names.
- Relative host paths in `file_mappings` are anchored to the workspace root directory or runfiles environment when accessing files on disk.
- The `search_files` tool specifies metadata with the name `search_files`, a regex pattern, an optional search path defaulting to workspace root, and optional offset and limit parameters.
- Executing `search_files` produces matching lines with line numbers for `ReadOnlyFile` targets, and match count notes for `ReadWriteFile` targets, formatted with `VirtualFileName` locations.
- `sanitize_paths` replaces host filesystem paths with virtual file names in descending order of host path length.
- `get_session_start_reads` produces a sequence of `read_file` `ToolResult` objects containing plain unnumbered content for every declared `ReadOnlyFile`.

## Invariants

- Writable files are read exclusively with 1-indexed line numbers.
- Read-only files are read exclusively as plain unnumbered content.
- Unmapped file read failures list all available readable virtual file names.
- Host path replacements during sanitization match longer paths before shorter substrings.
