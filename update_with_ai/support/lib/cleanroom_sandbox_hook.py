#!/usr/bin/env python3
"""cleanroom_sandbox_hook.py — Antigravity PreToolUse hook for Cleanroom sandbox enforcement.

Enforces role blindness and write lock boundaries on Antigravity native file tools
(`view_file`, `replace_file_content`, `write_to_file`) with a two-tier fail-safe:
  1. Non-subagents (Pair programmer / user): Immediate allow, zero network overhead.
  2. Cleanroom subagents: Validated against FastMCP server. If the server is crashed,
     fails closed (`decision: "deny"`), preventing subagents from running wild.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any, List, Optional, Tuple
import urllib.error
import urllib.request

try:
    from update_with_ai.support.lib import cleanroom_run_logger
except ImportError:
    try:
        import cleanroom_run_logger  # type: ignore
    except ImportError:
        cleanroom_run_logger = None  # type: ignore


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


def get_caller_descriptor(
    conversation_id: str,
    payload: Optional[dict[str, Any]] = None,
    brain_roots: Optional[List[str]] = None,
) -> Optional[dict[str, Any]]:
    """Retrieves the subagentDescriptor dict for the calling conversation if it exists."""
    if not conversation_id or conversation_id == "default":
        return None

    candidate_roots: List[str] = []
    if brain_roots:
        candidate_roots.extend(brain_roots)
    else:
        if payload:
            art_dir = payload.get("artifactDirectoryPath")
            if art_dir and isinstance(art_dir, str):
                candidate_roots.append(os.path.dirname(os.path.abspath(art_dir)))
            t_path = payload.get("transcriptPath")
            if t_path and isinstance(t_path, str):
                cur = os.path.abspath(t_path.replace("file://", ""))
                for _ in range(4):
                    cur = os.path.dirname(cur)
                candidate_roots.append(cur)

        candidate_roots.append(os.path.expanduser("~/.gemini/antigravity/brain"))
        candidate_roots.append(os.path.expanduser("~/.gemini/antigravity-ide/brain"))

    for root in candidate_roots:
        if not os.path.isdir(root):
            continue
        pattern = os.path.join(root, "*", ".system_generated", "subagents", f"{conversation_id}.json")
        for match in glob.glob(pattern):
            try:
                with open(match, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    desc = data.get("subagentDescriptor", {})
                    if desc and isinstance(desc, dict):
                        return desc
            except Exception:
                continue
    return None


def is_coordinator_caller(
    conversation_id: str,
    payload: Optional[dict[str, Any]] = None,
    brain_roots: Optional[List[str]] = None,
) -> bool:
    """Verifies whether the calling conversation belongs to a cleanroom_coordinator subagent."""
    desc = get_caller_descriptor(conversation_id, payload=payload, brain_roots=brain_roots)
    return bool(desc and desc.get("typeName") == "cleanroom_coordinator")


def process_hook_input(
    raw_input: str,
    sentinel_path: Optional[str] = None,
    brain_roots: Optional[List[str]] = None,
) -> dict[str, Any]:
    """Processes PreToolUse input from Antigravity and returns the gating decision."""
    try:
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}

    conversation_id = str(payload.get("conversationId", "default"))
    tool_call = payload.get("toolCall", {})
    tool_name = str(tool_call.get("name", ""))
    args = tool_call.get("args", {})
    workspace_paths = payload.get("workspacePaths", [])
    workspace_root = workspace_paths[0] if workspace_paths and isinstance(workspace_paths, list) else None

    # Tool gating for invoke_subagent:
    # cleanroom_role_worker subagents can ONLY be invoked by cleanroom_coordinator
    if tool_name == "invoke_subagent":
        subagents_arg = args.get("Subagents", [])
        was_string_encoded = False
        if isinstance(subagents_arg, str):
            try:
                subagents_arg = json.loads(subagents_arg)
                was_string_encoded = True
            except Exception:
                subagents_arg = []
        if isinstance(subagents_arg, list):
            for sa in subagents_arg:
                if isinstance(sa, dict):
                    type_name = sa.get("TypeName") or sa.get("typeName") or ""
                    if type_name == "cleanroom_role_worker":
                        if not is_coordinator_caller(conversation_id, payload, brain_roots=brain_roots):
                            return {
                                "decision": "deny",
                                "reason": (
                                    "Cleanroom security violation: 'cleanroom_role_worker' subagents "
                                    "can only be spawned by 'cleanroom_coordinator'."
                                ),
                            }
        if cleanroom_run_logger:
            cleanroom_run_logger.register_transcript(
                conversation_id, "00_coordinator", workspace_root=workspace_root, brain_roots=brain_roots
            )
            if isinstance(subagents_arg, list):
                for sa in subagents_arg:
                    if isinstance(sa, dict):
                        role_name = sa.get("Role") or sa.get("role") or sa.get("TypeName") or "worker"
                        cleanroom_run_logger.log_event(
                            "SPAWN", "coordinator", f"Spawning worker `{role_name}`", workspace_root=workspace_root
                        )
        res_allow: dict[str, Any] = {"decision": "allow"}
        if was_string_encoded and isinstance(subagents_arg, list):
            res_allow["overwrite"] = {"Subagents": subagents_arg}
        return res_allow

    file_path = str(
        args.get("AbsolutePath")
        or args.get("TargetFile")
        or args.get("file_path")
        or args.get("path")
        or ""
    ).strip('"\'')

    # Detect role worker from subagent descriptor
    caller_desc = get_caller_descriptor(conversation_id, payload=payload, brain_roots=brain_roots)
    if caller_desc and caller_desc.get("typeName") == "cleanroom_role_worker":
        role_label = str(caller_desc.get("role", "worker")).split()[0]
        role_slug = cleanroom_run_logger.sanitize_slug(role_label) if cleanroom_run_logger else "worker"
        if cleanroom_run_logger:
            cleanroom_run_logger.register_transcript(
                conversation_id, f"worker_{role_slug}", workspace_root=workspace_root, brain_roots=brain_roots
            )
            if tool_name == "view_file":
                cleanroom_run_logger.log_event(
                    "READ", f"worker:{role_slug}", f"`{file_path}`", workspace_root=workspace_root
                )
            elif tool_name in ("replace_file_content", "write_to_file"):
                cleanroom_run_logger.log_event(
                    "EDIT", f"worker:{role_slug}", f"`{file_path}`", workspace_root=workspace_root
                )

    path = sentinel_path if sentinel_path is not None else get_sentinel_path(workspace_root)

    # Fast path: No sentinel file means Cleanroom server is not running
    if not os.path.exists(path):
        return {"decision": "allow"}

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

    # Register transcript for active worker subagent
    if cleanroom_run_logger:
        cleanroom_run_logger.register_transcript(
            conversation_id, f"worker_{conversation_id[:8]}", workspace_root=workspace_root, brain_roots=brain_roots
        )

    # Server is alive: query fine-grained access decision
    is_allowed, reason = validate_via_http(host, port, conversation_id, tool_name, file_path)
    if is_allowed:
        if cleanroom_run_logger:
            if tool_name == "view_file":
                cleanroom_run_logger.log_event(
                    "READ", f"worker:{conversation_id[:8]}", f"`{file_path}`", workspace_root=workspace_root
                )
            elif tool_name in ("replace_file_content", "write_to_file"):
                cleanroom_run_logger.log_event(
                    "EDIT", f"worker:{conversation_id[:8]}", f"`{file_path}`", workspace_root=workspace_root
                )
        return {"decision": "allow"}
    return {"decision": "deny", "reason": reason}


def main() -> None:
    raw_input = sys.stdin.read()
    decision = process_hook_input(raw_input)
    sys.stdout.write(json.dumps(decision))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
