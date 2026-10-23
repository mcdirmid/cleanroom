"""
## External Mechanics & API Documentation

The `dsh_ext` external component specifies DeepSeek Harness CLI options, role agent documentation formats, Cordis overlay patches, and session storage structures.

**DeepSeek Harness CLI Execution Interface**

- Executable Command: `dsh --profile headless`
- CLI Parameters:
  - `--patch <PATH>`: Extra patch-list overlay applied after the profile layer.
  - `--json`: Emit newline-delimited JSON run events to stdout instead of final message.
  - `--session-id <ID>`: Adopt or resume the persisted session with this ID.
  - `-h, --help`: Show help text.
  - `task`: Task text passed as positional argument or read from stdin via `-`.

**Cordis Overlay Patch Format (`.cleanroom/dsh_patch.yml`)**

- File Path: `<workspace_dir>/.cleanroom/dsh_patch.yml`
- Overrides `@deepseek-ai/dsh-agent-default-model` to route model requests (`provider: deepseek-official` or `provider: omlx`).
- Configures `reasoningEffort: high` when targeting DeepSeek providers.
- Disables `@deepseek-ai/todo` plugin (`disabled: true`) for headless operation.
- Overrides `@deepseek-ai/dsh-user-approval` with `policy: never` and `@deepseek-ai/dsh-permission-presets` with `defaultPreset: danger-full-access` for unattended execution.

**Role Agent Documentation Format (`AGENTS.md`)**

- File Path: `<workspace_dir>/AGENTS.md`
- Injected automatically into round context via `@deepseek-ai/dsh-agent-instructions`.
- Enforces strict role workspace boundary confinement and prohibits directory traversal outside the root.
- Embeds command execution guidelines permitting in-workspace shell commands and native harness tools while mandating round resolution through prescribed bin/ tools (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/fail`, and `bin/blame` when feedback capability is declared).

**Session Storage and Telemetry Schema**

- Storage Directory: Discovered via `DSH_SESSIONS_DIR`, `DSH_HOME/harness/sessions`, or platform application support directory (`~/Library/Application Support/dsh-desktop/harness/sessions` on macOS, `~/.config/dsh-desktop/harness/sessions` on Linux), storing `<dir-slug>/<session-id>/session.v4.jsonl.zstd` (with uncompressed `session.v4.jsonl` fallback)
- Concurrency Lock: `session.lock` inside the active session directory verified non-blockingly via file locking.
- Active Session ID: `<workspace_dir>/.cleanroom/dsh_session_id.txt` for persisting active session ID across rounds, reset upon failed rounds.
- Structured JSON run event usage fields:
  - `usage.inputTokens`: INTEGER (uncached prompt tokens)
  - `usage.cacheReadTokens`: INTEGER (cached prompt tokens)
  - `usage.outputTokens`: INTEGER (generated completion tokens)
  - `usage.totalTokens`: INTEGER (sum of tokens)

**DeepSeek Harness Local JSON-RPC Wire Protocol**

- Discovery: Read-only SQLite `Cookies` (`dsh-auth-%`) in application support directories discovering active listening port and authentication cookie.
- Local RPC Endpoints (`POST http://127.0.0.1:{port}/api/{endpoint}`):
  - `workspace/create`: Enrolls workspace path, returns `{ result: { value: { workspace: { workspaceId } } } }`.
  - `session/create`: Enrolls or attaches session to workspace, returns `{ result: { ok: true } }`.
  - `session/prompt`: Enqueues prompt task, returns `{ result: { messageId } }`.
- Subagent Delegation Depth Limits (`maxDepth`):
  - Supported in `@deepseek-ai/dsh-tool-subagent` via integer values (`maxDepth: 2`) or `'provider-managed'`, backed by in-process providers with `depthLimit` capability.

## Build Dependencies

- None

## Usage Snippets

### `Querying DeepSeek Harness Session Telemetry`

```python
import json
from typing import Optional, Tuple

def parse_dsh_stream_line(line: str) -> Optional[Tuple[int, int, int, int]]:
    \"\"\"Parses a stream JSON event line for token usage.\"\"\"
    try:
        data = json.loads(line)
        usage = data.get("usage") or data.get("data", {}).get("usage")
        if usage:
            return (
                usage.get("inputTokens", 0),
                usage.get("cacheReadTokens", 0),
                usage.get("outputTokens", 0),
                usage.get("totalTokens", 0),
            )
    except Exception:
        pass
    return None
```
"""

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-20T22:50:00Z
# LAST_CHANGED: 2026-10-20T22:50:00Z
# CHANGE: Specify session reset only upon failed rounds
# --- END CLEANROOM METADATA ---
