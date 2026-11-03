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
- Python (`.py`, `.pyi`), Shell (`.sh`): Enclosed in line hash comments:
  ```python
  # --- CLEANROOM METADATA ---
  # LAST_CLEANED: 2026-10-05T20:52:01Z
  # LAST_CHANGED: 2026-10-02T14:50:12Z
  # CHANGE: Change summary text.
  # CODE_HASH: 3f7eec2be07d
  # --- END CLEANROOM METADATA ---
  ```

**Metadata Block Placement Rules**

1. Positioned at the bottom of the file following the source code or markdown body, separated by a blank line.
2. Preserves line numbers of the underlying source code so diagnostics, compiler errors, pytest tracebacks, and coverage reports do not drift when metadata fields are added or modified.
3. For extraction backward compatibility, blocks positioned anywhere in the file (top or bottom) are recognized and parsed.

**Grammar & Fields**

- `LAST_CLEANED`: UTC ISO 8601 timestamp truncated to seconds (`YYYY-MM-DDTHH:MM:SSZ`).
- `LAST_CHANGED`: UTC ISO 8601 timestamp truncated to seconds (`YYYY-MM-DDTHH:MM:SSZ`).
- `CHANGE`: Single-line text description of changes made during the last clean.
- `CODE_HASH`: 12-character SHA-256 hexadecimal hash of the file body excluding the metadata comment header.
- `DIRTY`: Optional reason string present when a node is marked dirty manually or by dependency failure.
- `FEEDBACK`: Optional list of unacted feedback items formatted as `- <explanation>`.
- `<ROLE>_AUDIT`: Audit timestamp for an auditor role (e.g. `QA_AUDIT`, `COVERAGE_AUDIT`, `SPEC_QA_AUDIT`).

**In-Place Rewriting Semantics**

- Cleaning with changes: `LAST_CLEANED` = now, `LAST_CHANGED` = now, `CHANGE` = updated summary, `CODE_HASH` = new hash, `FEEDBACK` removed, `DIRTY` removed, audits removed.
- No-op cleaning: `LAST_CLEANED` = now, `LAST_CHANGED` unchanged, `CHANGE` unchanged, `CODE_HASH` unchanged, `FEEDBACK` removed, `DIRTY` removed.
- Blaming upstream: Target file's `FEEDBACK` section created or appended with `- <explanation>`, and `LAST_CLEANED` advanced to now.
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
FEEDBACK_ITEM_PATTERN = re.compile(r"^-\s*(?:\[.*?\]:\s*)?(.*)$")
```
"""

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-06T14:35:00Z
# CHANGE: new file
# SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---
