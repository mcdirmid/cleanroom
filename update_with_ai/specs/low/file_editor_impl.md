<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - file_reader.md
  - virtual_file_name.md
  - file_editor.md
-->

# Implementation LLS: file_editor_impl

## Data Types
```python
from file_editor import FileEditor, FileEditorFactory, FileEditorConfig

class _FileEditorImpl(FileEditor):
    def __init__(self, config: FileEditorConfig) -> None: ...

class FileEditorFactoryImpl(FileEditorFactory):
    def __init__(self) -> None: ...
```

## Behavioral Description

- `FileEditorFactoryImpl.create_file_editor` constructs a `_FileEditorImpl` configured with writable permissions, host paths, and startup templates.
- The `replace` tool specifies metadata with the name `replace` and accepts target text and replacement text parameters.
- Executing `replace` with an unmapped or non-writable `VirtualFileName`, on ambiguous matches, missing target text, or target text exceeding the maximum replacement size limit (100,000 characters) produces a `ToolFailure`.
- The `update_lines` tool specifies metadata with the name `update_lines` and accepts 1-indexed start line, end line, and replacement text parameters.
- Executing `update_lines` with a start line greater than the end line performs an insertion at the start line.
- Executing `update_lines` with empty replacement text deletes the specified line range.
- Executing `update_lines` with an unmapped or non-writable `VirtualFileName`, or with out-of-bounds indices produces a `ToolFailure`.
- `materialize_templates` writes starter template files for missing files at startup without overwriting existing files.
- Captures run-start baseline file content before the first modification to a read-write file to evaluate net file modifications.

## Invariants

- Existing files are never overwritten by template materialization.
- Replaced text matches exact character sequences within target files.
- Executing line updates with empty replacement text deletes the target lines.
- Executing line updates where start line exceeds end line inserts content without replacing lines.
