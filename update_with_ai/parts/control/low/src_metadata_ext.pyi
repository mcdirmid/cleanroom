# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-06T14:35:00Z
# CHANGE: new file
# CODE_HASH: 283606d131f6
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

r"""
## External Mechanics & API Documentation

The `src_metadata_ext` external component specifies the grammar, comment conventions, placement rules, and in-place rewriting mechanics for embedding in-band dirty tracking and feedback metadata into source files. External boundary specifications define no standalone library files; consumers import standard libraries or reusable helpers.

**Comment Conventions by File Type**

- Markdown (`.md`): Enclosed in HTML comment blocks:
  ```markdown
  <!-- CLEANROOM METADATA
  LAST_CLEANED: 2026-10-02T14:40:00Z
  LAST_CHANGED: 2026-10-02T14:35:10Z
  CHANGE: Change summary text.
  CODE_HASH: 3f7eec2be07d
  -->
  ```
- Python (`.py`, `.pyi`), Starlark (`BUILD`, `BUILD.bazel`, `.bzl`), Shell (`.sh`): Enclosed in line hash comments:
  ```python
  # --- CLEANROOM METADATA ---
  # LAST_CLEANED: 2026-10-05T20:52:01Z
  # LAST_CHANGED: 2026-10-02T14:50:12Z
  # CHANGE: Change summary text.
  # CODE_HASH: 3f7eec2be07d
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
- `CODE_HASH`: 12-character SHA-256 hexadecimal hash of the file body excluding the metadata comment header.
- `DIRTY`: Optional reason string present when a node is marked dirty manually or by dependency failure.
- `FEEDBACK`: Optional list of unacted feedback items formatted as `- [<timestamp> from <blamer>]: <explanation>`.
- `<ROLE>_AUDIT`: Audit timestamp for an auditor role (e.g. `QA_AUDIT`, `COVERAGE_AUDIT`, `SPEC_QA_AUDIT`, `LOW_QA_AUDIT`).

**In-Place Rewriting Semantics**

- Cleaning with changes: `LAST_CLEANED` = now, `LAST_CHANGED` = now, `CHANGE` = updated summary, `CODE_HASH` = new hash, `FEEDBACK` removed, `DIRTY` removed, audits removed.
- No-op cleaning: `LAST_CLEANED` = now, `LAST_CHANGED` unchanged, `CHANGE` unchanged, `CODE_HASH` unchanged, `FEEDBACK` removed, `DIRTY` removed.
- Blaming upstream: Target file's `FEEDBACK` section created or appended with `- [now from blamer]: explanation`, and `LAST_CLEANED` advanced to now.
- Marking dirty: `DIRTY` tag set with reason description, and `LAST_CLEANED` advanced to now.
- Stamping audit: `<ROLE>_AUDIT` set to now, and `LAST_CLEANED` advanced to now.

## Build Dependencies

(none)

## Usage Snippets

### `Comment Delimiters and Directives`

```python
import re

MD_OPEN = "<!-- CLEANROOM METADATA"
MD_CLOSE = "-->"
CODE_OPEN = "# --- CLEANROOM METADATA ---"
CODE_CLOSE = "# --- END CLEANROOM METADATA ---"
FEEDBACK_PREFIX = "FEEDBACK:"
FEEDBACK_ITEM_PATTERN = re.compile(r"^-\s*\[(.*?)\]:\s*(.*)$")
```
"""
