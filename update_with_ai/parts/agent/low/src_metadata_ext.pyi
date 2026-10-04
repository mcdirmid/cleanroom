"""
## External Mechanics & API Documentation

The `src_metadata_ext` external component specifies the grammar, comment conventions, placement rules, and in-place rewriting mechanics for embedding in-band dirty tracking and feedback metadata into source files. External boundary specifications define no standalone library files; consumers import the standard library or reusable helpers.

**Comment Conventions by File Type**

- Markdown (`.md`): Enclosed in HTML comment blocks:
  ```markdown
  <!-- CLEANROOM METADATA
  LAST_CLEANED: 2026-10-02T14:40:00Z
  LAST_CHANGED: 2026-10-02T14:35:10Z
  CHANGE: Change summary text.
  -->
  ```
- Python (`.py`, `.pyi`), Starlark (`BUILD`, `BUILD.bazel`, `.bzl`), Shell (`.sh`): Enclosed in line hash comments:
  ```python
  # --- CLEANROOM METADATA ---
  # LAST_CLEANED: 2026-10-02T14:55:48Z
  # LAST_CHANGED: 2026-10-02T14:50:12Z
  # CHANGE: Change summary text.
  # --- END CLEANROOM METADATA ---
  ```

**Header Placement Rules**

1. Placed at the top of the file.
2. In executable scripts with a shebang (`#!/usr/bin/...`) or encoding directive (`# -*- coding: ... -*-`), placed immediately below those directives.
3. In Markdown documents with YAML frontmatter (`---`), placed immediately below the closing frontmatter delimiter.

**Grammar & Fields**

- `LAST_CLEANED`: UTC ISO 8601 timestamp truncated to seconds (`YYYY-MM-DDTHH:MM:SSZ`).
- `LAST_CHANGED`: UTC ISO 8601 timestamp truncated to seconds (`YYYY-MM-DDTHH:MM:SSZ`).
- `CHANGE`: Single-line text description of changes made during the last clean.
- `FEEDBACK`: Optional list of unacted feedback items formatted as `- [<timestamp> from <blamer>]: <explanation>`. Omitted when there is no unacted feedback.

**In-Place Rewriting Semantics**

- Cleaning with changes: `LAST_CLEANED` = now, `LAST_CHANGED` = now, `CHANGE` = updated summary, `FEEDBACK` removed.
- No-op cleaning: `LAST_CLEANED` = now, `LAST_CHANGED` unchanged, `CHANGE` unchanged, `FEEDBACK` removed.
- Blaming upstream: Target file's `FEEDBACK` section created or appended with `- [now from blamer]: explanation`. Target timestamps unchanged.

## Build Dependencies

- `//update_python_with_ai/support/lib:src_metadata`

## Usage Snippets

### `Parsing and Updating File Metadata Headers`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass(frozen=True)
class FileMetadata:
    last_cleaned: Optional[str]
    last_changed: Optional[str]
    change_summary: str
    feedback: List[str]

def extract_metadata(file_path: Path) -> Optional[FileMetadata]:
    ...

def update_metadata(
    file_path: Path,
    last_cleaned: Optional[str] = None,
    clear_last_cleaned: bool = False,
    last_changed: Optional[str] = None,
    change_summary: Optional[str] = None,
    clear_feedback: bool = False,
    append_feedback: Optional[str] = None,
) -> None:
    ...
```
"""
