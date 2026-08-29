<!-- Dependencies (md files to read alongside this one):
  - file_editor.md
  - file_reader.md
  - tool_provider.md
-->

# Implementation LLS: file_editor_impl

## Data Types
```python
from file_editor import FileEditor, FileEditorConfig
from file_reader import FileReader

class FileEditorImpl(FileEditor):
    def __init__(self, config: FileEditorConfig, file_reader: FileReader) -> None: ...
```

## Behavioral Description
Implements FileEditor by performing content replacement, line range editing, template creation at startup, and tracking snapshots and changed files.

## Invariants
- `replace` string lengths capped at 200 characters.
- Injected read sets line-numbered view.
- Snapshots record original content prior to first write.
