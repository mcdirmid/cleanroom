<!-- Dependencies (md files to read alongside this one):
  - file_reader.md
  - tool_provider.md
-->

# Implementation LLS: file_reader_impl

## Data Types
```python
from file_reader import FileReader, FileReaderConfig

class FileReaderImpl(FileReader):
    def __init__(self, config: FileReaderConfig) -> None: ...
```

## Behavioral Description
Implements FileReader by mapping virtual names to disk paths, formatting plain or line-numbered views, searching regex patterns, and sanitizing output.

## Invariants
- Search limit enforced when limit parameter is omitted.
- Output paths sanitized to virtual names.
