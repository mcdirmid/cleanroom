#!/usr/bin/env python3
"""cleanroom_sandbox_hook.py — Antigravity PreToolUse hook for Cleanroom sandbox enforcement.

Enforces role blindness and write lock boundaries on Antigravity native file tools
(`view_file`, `replace_file_content`, `write_to_file`) with a two-tier fail-safe:
  1. Non-subagents (Pair programmer / user): Immediate allow, zero network overhead.
  2. Cleanroom subagents: Validated against FastMCP server. If the server is crashed,
     fails closed (`decision: "deny"`), preventing subagents from running wild.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional, Tuple
import urllib.error
import urllib.request


def is_process_alive(pid: Optional[int]) -> bool:
    """Checks whether a process with the given PID is running via an in-kernel check."""
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def get_sentinel_path(workspace_root: Optional[str] = None) -> str:
    """Returns the path to the workspace sentinel file."""
    override = os.environ.get("CLEANROOM_SENTINEL_PATH")
    if override:
        return override
    root = workspace_root if workspace_root else os.getcwd()
    cand1 = os.path.join(os.path.abspath(root), ".mcp.active")
    if os.path.exists(cand1):
        return cand1
    cand2 = os.path.join(os.path.abspath(root), "..", ".mcp.active")
    if os.path.exists(cand2):
        return cand2
    return cand1


def read_sentinel_file(path: str) -> Optional[dict[str, Any]]:
    """Reads and parses the sentinel file JSON if it exists."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def validate_via_http(
    host: str,
    port: int,
    conversation_id: str,
    tool_name: str,
    file_path: str,
    timeout: float = 3.0,
) -> Tuple[bool, str]:
    """Queries the FastMCP HTTP route to validate tool access."""
    url = f"http://{host}:{port}/validate_access"
    payload = json.dumps({
        "conversation_id": conversation_id,
        "tool_name": tool_name,
        "file_path": file_path,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            is_allowed = bool(data.get("is_allowed", False))
            reason = str(data.get("reason", "Access denied by Cleanroom sandbox gate."))
            return is_allowed, reason
    except urllib.error.URLError as e:
        return False, f"Cleanroom MCP server communication error: {e}"
    except Exception as e:
        return False, f"Unexpected validation error: {e}"


def process_hook_input(
    raw_input: str, sentinel_path: Optional[str] = None
) -> dict[str, Any]:
    """Processes PreToolUse input from Antigravity and returns the gating decision."""
    try:
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}

    workspace_paths = payload.get("workspacePaths", [])
    workspace_root = workspace_paths[0] if workspace_paths and isinstance(workspace_paths, list) else None

    path = sentinel_path if sentinel_path is not None else get_sentinel_path(workspace_root)

    # Fast path: No sentinel file means Cleanroom server is not running
    if not os.path.exists(path):
        return {"decision": "allow"}

    conversation_id = str(payload.get("conversationId", "default"))
    tool_call = payload.get("toolCall", {})
    tool_name = str(tool_call.get("name", ""))
    args = tool_call.get("args", {})
    file_path = str(
        args.get("AbsolutePath")
        or args.get("TargetFile")
        or args.get("file_path")
        or args.get("path")
        or ""
    )

    sentinel_data = read_sentinel_file(path)
    if sentinel_data is None:
        return {"decision": "allow"}

    pid = sentinel_data.get("pid")
    port = int(sentinel_data.get("port", 8765))
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    subagents = [str(x) for x in sentinel_data.get("subagents", [])]

    # Check caller identity
    if conversation_id not in subagents:
        # Pair programming or developer caller — never block
        if not is_process_alive(pid):
            # Clean up stale sentinel file
            try:
                os.remove(path)
            except OSError:
                pass
        return {"decision": "allow"}

    # Caller IS a registered Cleanroom subagent
    if not is_process_alive(pid):
        # Strict Fail-Closed: subagents must not run wild when server crashes
        return {
            "decision": "deny",
            "reason": (
                f"Cleanroom MCP server (PID {pid}) has crashed or is not running. "
                "File access denied to preserve sandbox confinement."
            ),
        }

    # Server is alive: query fine-grained access decision
    is_allowed, reason = validate_via_http(host, port, conversation_id, tool_name, file_path)
    if is_allowed:
        return {"decision": "allow"}
    return {"decision": "deny", "reason": reason}


def main() -> None:
    raw_input = sys.stdin.read()
    decision = process_hook_input(raw_input)
    sys.stdout.write(json.dumps(decision))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
