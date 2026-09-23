#!/usr/bin/env python3
"""cleanroom_sandbox_hook.py — Antigravity PreToolUse hook for Cleanroom sandbox enforcement.

Enforces role sandboxing on Cleanroom role workers (`cleanroom_role_worker`):
  1. Whitelists `run_command` strictly to `python3 update_with_ai/support/lib/cleanroom_mcp_client.py <valid_subcommand>`.
     Blocks arbitrary shell commands, chaining, metacharacters, and unauthorized subcommands.
  2. Enforces role blindness and write lock boundaries on file tools (`view_file`, `replace_file_content`, `write_to_file`)
     via FastMCP access gate validation. Fails closed if the server is missing or crashed.
  3. Non-workers (cleanroom_coordinator, human developers, pair programmer): Unrestricted `run_command` and file operations.
  4. Spawning restriction: `cleanroom_role_worker` subagents may only be spawned by `cleanroom_coordinator`.
"""

from __future__ import annotations

import glob
import json
import os
import shlex
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

FORBIDDEN_SHELL_PATTERNS = (";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r")
VALID_WORKER_SUBCOMMANDS = frozenset({
    "register",
    "deregister",
    "get-work",
    "check-files",
    "check-file",
    "submit",
    "blame",
    "fail",
})
VALID_PYTHON_BINARIES = frozenset({"python3", "python", "python3.12", "python3.13"})
DENY_REASON_COMMAND = (
    "Cleanroom security violation: Role workers are strictly forbidden from executing arbitrary shell commands."
)


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


def get_worker_sessions_path(sentinel_path: Optional[str] = None, workspace_root: Optional[str] = None) -> str:
    """Returns the path to the worker session mapping file."""
    spath = sentinel_path if sentinel_path is not None else get_sentinel_path(workspace_root)
    return os.path.join(os.path.dirname(os.path.abspath(spath)), ".mcp.worker_sessions.json")


def read_worker_sessions(path: str) -> dict[str, str]:
    """Reads the worker UUID -> session_id mapping from disk."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def save_worker_session(conversation_id: str, session_id: str, path: str) -> None:
    """Saves a worker UUID -> session_id mapping to disk atomically."""
    try:
        sessions = read_worker_sessions(path)
        sessions[conversation_id] = session_id
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sessions, f)
        os.replace(tmp, path)
    except Exception:
        pass


def remove_worker_session(conversation_id: str, path: str) -> None:
    """Removes a worker UUID -> session_id mapping from disk."""
    try:
        sessions = read_worker_sessions(path)
        if conversation_id in sessions:
            del sessions[conversation_id]
            tmp = f"{path}.tmp.{os.getpid()}"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(sessions, f)
            os.replace(tmp, path)
    except Exception:
        pass


def remove_worker_session_by_session_id(session_id: str, path: str) -> None:
    """Removes any worker mapping associated with the given session_id from disk."""
    try:
        sessions = read_worker_sessions(path)
        keys_to_del = [k for k, v in sessions.items() if v == session_id]
        if keys_to_del:
            for k in keys_to_del:
                del sessions[k]
            tmp = f"{path}.tmp.{os.getpid()}"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(sessions, f)
            os.replace(tmp, path)
    except Exception:
        pass


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
                candidate_roots.append(os.path.abspath(art_dir))
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
        patterns = [
            os.path.join(root, "*", ".system_generated", "subagents", f"{conversation_id}.json"),
            os.path.join(root, ".system_generated", "subagents", f"{conversation_id}.json"),
        ]
        for pattern in patterns:
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


def is_role_worker_caller(
    conversation_id: str,
    payload: Optional[dict[str, Any]] = None,
    brain_roots: Optional[List[str]] = None,
) -> bool:
    """Verifies whether the calling conversation belongs to a cleanroom_role_worker subagent."""
    desc = get_caller_descriptor(conversation_id, payload=payload, brain_roots=brain_roots)
    return bool(desc and desc.get("typeName") == "cleanroom_role_worker")


def extract_command_line(args: dict[str, Any]) -> str:
    """Extracts and normalizes CommandLine from tool arguments."""
    cmd = args.get("CommandLine", "")
    if not isinstance(cmd, str):
        cmd = str(cmd or "")
    cmd = cmd.strip()
    if (cmd.startswith('"') and cmd.endswith('"')) or (cmd.startswith("'") and cmd.endswith("'")):
        try:
            unquoted = json.loads(cmd)
            if isinstance(unquoted, str):
                cmd = unquoted.strip()
        except Exception:
            if len(cmd) >= 2 and cmd[0] == cmd[-1] and cmd[0] in ('"', "'"):
                cmd = cmd[1:-1].strip()
    return cmd


def validate_worker_command_line(cmd: str) -> Tuple[bool, str, Optional[list[str]]]:
    """Validates that a CommandLine from a role worker strictly matches the allowed whitelist.

    Returns (is_allowed, deny_reason, parsed_tokens).
    """
    if not cmd:
        return False, DENY_REASON_COMMAND, None

    # Block shell metacharacters and command chaining
    for pattern in FORBIDDEN_SHELL_PATTERNS:
        if pattern in cmd:
            return False, DENY_REASON_COMMAND, None

    try:
        tokens = shlex.split(cmd)
    except Exception:
        return False, DENY_REASON_COMMAND, None

    if len(tokens) < 3:
        return False, DENY_REASON_COMMAND, None

    # Binary check
    binary_base = os.path.basename(tokens[0])
    if tokens[0] not in VALID_PYTHON_BINARIES and binary_base not in VALID_PYTHON_BINARIES:
        return False, DENY_REASON_COMMAND, None

    # Script check
    norm_script = os.path.normpath(tokens[1])
    target_script = "update_with_ai/support/lib/cleanroom_mcp_client.py"
    if norm_script != target_script and not norm_script.endswith("/" + target_script):
        return False, DENY_REASON_COMMAND, None

    # Subcommand check: find first non-option token after token 1
    subcommand: Optional[str] = None
    idx = 2
    while idx < len(tokens):
        tok = tokens[idx]
        if tok in ("--session", "-s", "--port", "--worker-id", "--conv-id"):
            idx += 2
            continue
        if tok.startswith(("--session=", "-s=", "--port=", "--worker-id=", "--conv-id=")):
            idx += 1
            continue
        if tok.startswith("-"):
            idx += 1
            continue
        subcommand = tok
        break

    if subcommand is None or subcommand not in VALID_WORKER_SUBCOMMANDS:
        return False, DENY_REASON_COMMAND, None

    return True, "", tokens


def extract_session_id_from_register(tokens: list[str]) -> Optional[str]:
    """Extracts the session ID from register command tokens."""
    for i, tok in enumerate(tokens):
        if tok in ("--session", "-s") and i + 1 < len(tokens):
            return tokens[i + 1]
        if tok.startswith(("--session=", "-s=")):
            return tok.split("=", 1)[1]
    for i, tok in enumerate(tokens):
        if tok == "--role" and i + 1 < len(tokens):
            return tokens[i + 1].split(":")[-1]
        if tok.startswith("--role="):
            return tok.split("=", 1)[1].split(":")[-1]
    return None


def extract_worker_id_from_tokens(tokens: list[str]) -> Optional[str]:
    """Extracts the worker conversation ID from command tokens if present."""
    for i, tok in enumerate(tokens):
        if tok in ("--worker-id", "--conv-id") and i + 1 < len(tokens):
            return tokens[i + 1]
        if tok.startswith(("--worker-id=", "--conv-id=")):
            return tok.split("=", 1)[1]
    return None


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

    # Identify caller role
    caller_desc = get_caller_descriptor(conversation_id, payload=payload, brain_roots=brain_roots)
    is_role_worker = bool(caller_desc and caller_desc.get("typeName") == "cleanroom_role_worker")
    role_label = str(caller_desc.get("role", "worker")).split()[0] if caller_desc else "worker"
    role_slug = cleanroom_run_logger.sanitize_slug(role_label) if cleanroom_run_logger else "worker"

    if cleanroom_run_logger and is_role_worker:
        cleanroom_run_logger.register_transcript(
            conversation_id, f"worker_{role_slug}", workspace_root=workspace_root, brain_roots=brain_roots
        )

    # Non-role-workers (human developer, pair programmer, coordinator):
    if not is_role_worker:
        if tool_name == "run_command":
            return {"decision": "allow"}
        # File tools for non-workers: clean up dead sentinel if exists, then allow
        sent_path = sentinel_path if sentinel_path is not None else get_sentinel_path(workspace_root)
        if os.path.exists(sent_path):
            sentinel_data = read_sentinel_file(sent_path)
            if sentinel_data is not None:
                pid = sentinel_data.get("pid")
                if not is_process_alive(pid):
                    try:
                        os.remove(sent_path)
                    except OSError:
                        pass
        return {"decision": "allow"}

    # --- Role Worker Sandboxing ---
    if tool_name == "run_command":
        cmd_line = extract_command_line(args)
        is_allowed, deny_reason, tokens = validate_worker_command_line(cmd_line)
        if not is_allowed:
            if cleanroom_run_logger:
                cleanroom_run_logger.log_event(
                    "DENY",
                    f"worker:{role_slug}",
                    f"Prohibited run_command: `{cmd_line}`",
                    workspace_root=workspace_root,
                )
            return {"decision": "deny", "reason": deny_reason}

        # Track session registration / deregistration
        if tokens:
            sessions_path = get_worker_sessions_path(sentinel_path=sentinel_path, workspace_root=workspace_root)
            subcmd = None
            for t in tokens[2:]:
                if not t.startswith("-"):
                    subcmd = t
                    break
            if subcmd == "register":
                sess_id = extract_session_id_from_register(tokens)
                target_worker = extract_worker_id_from_tokens(tokens) or conversation_id
                if sess_id and target_worker:
                    save_worker_session(target_worker, sess_id, sessions_path)
            elif subcmd == "deregister":
                sess_id = extract_session_id_from_register(tokens)
                if sess_id:
                    remove_worker_session_by_session_id(sess_id, sessions_path)
                target_worker = extract_worker_id_from_tokens(tokens) or conversation_id
                remove_worker_session(target_worker, sessions_path)

        return {"decision": "allow"}

    if tool_name in ("view_file", "replace_file_content", "write_to_file"):
        file_path = str(
            args.get("AbsolutePath")
            or args.get("TargetFile")
            or args.get("file_path")
            or args.get("path")
            or ""
        ).strip('"\'')

        sent_path = sentinel_path if sentinel_path is not None else get_sentinel_path(workspace_root)
        if not os.path.exists(sent_path):
            return {
                "decision": "deny",
                "reason": (
                    "Cleanroom MCP server is not running. "
                    "File access denied to preserve sandbox confinement."
                ),
            }

        sentinel_data = read_sentinel_file(sent_path)
        if sentinel_data is None:
            return {
                "decision": "deny",
                "reason": (
                    "Cleanroom MCP server sentinel is unreadable. "
                    "File access denied to preserve sandbox confinement."
                ),
            }

        pid = sentinel_data.get("pid")
        if not is_process_alive(pid):
            return {
                "decision": "deny",
                "reason": (
                    f"Cleanroom MCP server (PID {pid}) has crashed or is not running. "
                    "File access denied to preserve sandbox confinement."
                ),
            }

        port = int(sentinel_data.get("port", 8765))
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        subagents = [str(x) for x in sentinel_data.get("subagents", [])]

        sessions_path = get_worker_sessions_path(sentinel_path=sentinel_path, workspace_root=workspace_root)
        sessions_map = read_worker_sessions(sessions_path)

        target_session: Optional[str] = None
        if conversation_id in subagents:
            target_session = conversation_id
        elif conversation_id in sessions_map and sessions_map[conversation_id] in subagents:
            target_session = sessions_map[conversation_id]
        elif len(subagents) == 1:
            target_session = subagents[0]
        else:
            role_hint = str(caller_desc.get("role", "")).lower()
            for s in subagents:
                if s.lower() in role_hint or role_hint.endswith(s.lower()):
                    target_session = s
                    break

        if not target_session:
            return {
                "decision": "deny",
                "reason": f"Cleanroom security violation: No active role session registered for worker '{conversation_id}'.",
            }

        is_allowed, reason = validate_via_http(host, port, target_session, tool_name, file_path)
        if is_allowed:
            if cleanroom_run_logger:
                if tool_name == "view_file":
                    cleanroom_run_logger.log_event(
                        "READ", f"worker:{role_slug}", f"`{file_path}`", workspace_root=workspace_root
                    )
                elif tool_name in ("replace_file_content", "write_to_file"):
                    cleanroom_run_logger.log_event(
                        "EDIT", f"worker:{role_slug}", f"`{file_path}`", workspace_root=workspace_root
                    )
            return {"decision": "allow"}
        return {"decision": "deny", "reason": reason}

    # Any other tool invoked by a role worker is forbidden
    return {
        "decision": "deny",
        "reason": f"Cleanroom security violation: Tool '{tool_name}' is not permitted for role workers.",
    }


def main() -> None:
    raw_input = sys.stdin.read()
    decision = process_hook_input(raw_input)
    sys.stdout.write(json.dumps(decision))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
