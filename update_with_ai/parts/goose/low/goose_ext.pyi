# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:15Z
# LAST_CHANGED: 2026-10-13T11:20:00Z
# CHANGE: update goose_ext to remove recipes and reflect AGENTS.md conventions
# CODE_HASH: c0d2f136bc50
# --- END CLEANROOM METADATA ---

"""
## External Mechanics & API Documentation

The `goose_ext` external component specifies Goose CLI options, role agent documentation formats, and SQLite session database structures.

**Goose CLI Execution Interface**

- Executable Command: `goose run`
- CLI Parameters:
  - `-i, --instructions <FILE>`: Path to markdown instruction file containing task prompts.
  - `-n, --name <NAME>`: Custom identifier name for the execution session.
  - `--max-turns <NUMBER>`: Maximum turn count limit for the agent run.
  - `--cwd <DIR>` or executing with process working directory set to target workspace directory.

**Role Agent Documentation Format (`AGENTS.md`)**

- File Path: `<workspace_dir>/AGENTS.md`
- Injected automatically into turn context via Goose's native `CONTEXT_FILE_NAMES` discovery.
- Enforces strict role workspace boundary confinement and prohibits directory traversal outside the root.
- Enforces the 5-command restriction tripwire limiting commands to `bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, and `bin/fail`.

**SQLite Session Telemetry Database Schema (`sessions.db`)**

- Database Path: `~/.local/share/goose/sessions/sessions.db`
- `sessions` Table:
  - `id`: TEXT PRIMARY KEY
  - `name`: TEXT NOT NULL
  - `working_dir`: TEXT NOT NULL
  - `input_tokens`: INTEGER
  - `output_tokens`: INTEGER
  - `cache_read_tokens`: INTEGER
  - `accumulated_cost`: REAL
- `usage_ledger` Table:
  - `session_id`: TEXT REFERENCES sessions(id)
  - `input_tokens`: INTEGER
  - `output_tokens`: INTEGER
  - `cache_read_tokens`: INTEGER
  - `cost`: REAL

## Build Dependencies

- None

## Usage Snippets

### `Querying Goose Session Telemetry from SQLite`

```python
import sqlite3
from typing import Optional, Tuple

def query_goose_session_tokens(
    db_path: str,
    session_name: str,
) -> Optional[Tuple[int, int, int, float]]:
    \"\"\"Queries recorded tokens from the Goose session database.\"\"\"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT input_tokens, cache_read_tokens, output_tokens, accumulated_cost "
            "FROM sessions WHERE name = ? ORDER BY updated_at DESC LIMIT 1",
            (session_name,),
        )
        row = cursor.fetchone()
        if row:
            return (row[0] or 0, row[1] or 0, row[2] or 0, row[3] or 0.0)
    return None
```
"""
