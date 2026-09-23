# Requirements specified in antigravity_sandbox_gate_impl.pyi
from __future__ import annotations

import glob
import json
import os
import shlex
import urllib.error
import urllib.request
import sys
from typing import Any, Dict, List, Optional, Tuple

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)
if not os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
    os.environ["BUILD_WORKSPACE_DIRECTORY"] = _repo_root

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import antigravity_run_logger
from . import antigravity_sandbox_gate

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
VALID_COORDINATOR_SUBCOMMANDS = frozenset({
    "step",
    "register-spawned",
})
VALID_PYTHON_BINARIES = frozenset({"python3", "python", "python3.12", "python3.13"})
DENY_REASON_COMMAND = (
    "Cleanroom security violation: Role workers are strictly forbidden from executing arbitrary shell commands."
)
DENY_REASON_COORDINATOR_COMMAND = (
    "Cleanroom security violation: Coordinator is strictly forbidden from executing troubleshooting or arbitrary shell commands."
)
DENY_REASON_COORDINATOR_FILE_TOOL = (
    "Cleanroom security violation: Coordinator is strictly forbidden from editing or creating workspace files."
)


def is_process_alive(pid: Optional[int]) -> bool:
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
    override = os.environ.get("CLEANROOM_SENTINEL_PATH")
    if override:
        return override
    root = workspace_root if workspace_root else (os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd())
    cand1 = os.path.join(os.path.abspath(root), ".mcp.active")
    if os.path.exists(cand1):
        return cand1
    cand2 = os.path.join(os.path.abspath(root), "..", ".mcp.active")
    if os.path.exists(cand2):
        return cand2
    return cand1


def read_sentinel_file(path: str) -> Optional[dict[str, Any]]:
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
    spath = sentinel_path if sentinel_path is not None else get_sentinel_path(workspace_root)
    return os.path.join(os.path.dirname(os.path.abspath(spath)), ".mcp.worker_sessions.json")


def validate_via_http(
    host: str,
    port: int,
    conversation_id: str,
    tool_name: str,
    file_path: str,
    timeout: float = 3.0,
) -> Tuple[bool, str]:
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


class AntigravitySandboxGate(antigravity_sandbox_gate.AntigravitySandboxGate, Singleton):
    tier = system

    def validate_worker_command(self, command_line: str) -> Tuple[bool, str]:
        cmd = command_line.strip()
        if not cmd:
            return False, DENY_REASON_COMMAND

        for pattern in FORBIDDEN_SHELL_PATTERNS:
            if pattern in cmd:
                return False, DENY_REASON_COMMAND

        try:
            tokens = shlex.split(cmd)
        except Exception:
            return False, DENY_REASON_COMMAND

        if len(tokens) < 3:
            return False, DENY_REASON_COMMAND

        binary_base = os.path.basename(tokens[0])
        if tokens[0] not in VALID_PYTHON_BINARIES and binary_base not in VALID_PYTHON_BINARIES:
            return False, DENY_REASON_COMMAND

        # Check script ending or module invocation
        norm_script = os.path.normpath(tokens[1])
        valid_scripts = (
            "cleanroom_mcp_client.py",
            "antigravity_mcp_client.py",
            "update_with_ai/support/lib/cleanroom_mcp_client.py",
            "update_with_ai/parts/antigravity/lib/antigravity_mcp_client.py",
        )
        is_valid_script = any(norm_script == s or norm_script.endswith("/" + s) for s in valid_scripts)
        is_valid_module = (tokens[1] == "-m" and len(tokens) >= 3 and (
            "antigravity_mcp_client" in tokens[2] or "cleanroom_mcp_client" in tokens[2]
        ))
        if not is_valid_script and not is_valid_module:
            return False, DENY_REASON_COMMAND

        start_idx = 3 if is_valid_module else 2
        subcommand: Optional[str] = None
        idx = start_idx
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
            return False, DENY_REASON_COMMAND

        return True, ""

    def validate_coordinator_command(self, command_line: str) -> Tuple[bool, str]:
        cmd = command_line.strip()
        if not cmd:
            return False, DENY_REASON_COORDINATOR_COMMAND

        for pattern in FORBIDDEN_SHELL_PATTERNS:
            if pattern in cmd:
                return False, DENY_REASON_COORDINATOR_COMMAND

        try:
            tokens = shlex.split(cmd)
        except Exception:
            return False, DENY_REASON_COORDINATOR_COMMAND

        if len(tokens) < 2:
            return False, DENY_REASON_COORDINATOR_COMMAND

        binary_base = os.path.basename(tokens[0])
        if tokens[0] not in VALID_PYTHON_BINARIES and binary_base not in VALID_PYTHON_BINARIES:
            return False, DENY_REASON_COORDINATOR_COMMAND

        if tokens[1] == "-m" and len(tokens) >= 3:
            mod = tokens[2]
            if "antigravity_coordinator" in mod or "cleanroom_coordinator" in mod:
                if len(tokens) < 4:
                    return False, DENY_REASON_COORDINATOR_COMMAND
                subcommand = tokens[3]
                if subcommand in VALID_COORDINATOR_SUBCOMMANDS:
                    return True, ""
                return False, DENY_REASON_COORDINATOR_COMMAND
            if "antigravity_telemetry" in mod or "antigravity_token_stats" in mod:
                return True, ""
            return False, DENY_REASON_COORDINATOR_COMMAND

        norm_script = os.path.normpath(tokens[1])
        if norm_script.endswith("antigravity_coordinator_impl.py") or norm_script.endswith("cleanroom_coordinator_engine.py"):
            if len(tokens) < 3:
                return False, DENY_REASON_COORDINATOR_COMMAND
            subcommand = tokens[2]
            if subcommand in VALID_COORDINATOR_SUBCOMMANDS:
                return True, ""
            return False, DENY_REASON_COORDINATOR_COMMAND
        if norm_script.endswith("antigravity_telemetry_impl.py") or norm_script.endswith("antigravity_token_stats.py"):
            return True, ""

        return False, DENY_REASON_COORDINATOR_COMMAND

    def is_coordinator_caller(self, identifier: str) -> bool:
        desc = get_caller_descriptor(identifier)
        return bool(desc and desc.get("typeName") == "cleanroom_coordinator")

    def is_role_worker_caller(self, identifier: str) -> bool:
        desc = get_caller_descriptor(identifier)
        return bool(desc and desc.get("typeName") == "cleanroom_role_worker")

    def save_worker_session(self, worker_id: str, session_id: str) -> None:
        path = get_worker_sessions_path()
        sessions = self.read_worker_sessions()
        sessions[worker_id] = session_id
        tmp = f"{path}.tmp.{os.getpid()}"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(sessions, f)
            os.replace(tmp, path)
        except Exception:
            pass

    def remove_worker_session(self, worker_id: str) -> None:
        path = get_worker_sessions_path()
        sessions = self.read_worker_sessions()
        if worker_id in sessions:
            del sessions[worker_id]
            tmp = f"{path}.tmp.{os.getpid()}"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(sessions, f)
                os.replace(tmp, path)
            except Exception:
                pass

    def read_worker_sessions(self) -> Dict[str, str]:
        path = get_worker_sessions_path()
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

    def process_hook_input(self, payload: str) -> antigravity_sandbox_gate.GatingDecision:
        try:
            data = json.loads(payload) if payload.strip() else {}
        except Exception:
            data = {}

        conversation_id = str(data.get("conversationId", "default"))
        tool_call = data.get("toolCall", {})
        tool_name = str(tool_call.get("name", ""))
        args = tool_call.get("args", {})
        workspace_paths = data.get("workspacePaths", [])
        workspace_root = workspace_paths[0] if workspace_paths and isinstance(workspace_paths, list) else None

        # Check invoke_subagent caller
        if tool_name == "invoke_subagent":
            subagents_arg = args.get("Subagents", [])
            was_str = False
            if isinstance(subagents_arg, str):
                try:
                    subagents_arg = json.loads(subagents_arg)
                    was_str = True
                except Exception:
                    subagents_arg = []
            if isinstance(subagents_arg, list):
                for sa in subagents_arg:
                    if isinstance(sa, dict):
                        tn = sa.get("TypeName") or sa.get("typeName") or ""
                        if tn == "cleanroom_role_worker":
                            if not self.is_coordinator_caller(conversation_id):
                                return antigravity_sandbox_gate.GatingDecision(
                                    decision="deny",
                                    reason="Cleanroom security violation: 'cleanroom_role_worker' subagents can only be spawned by 'cleanroom_coordinator'.",
                                )
            overwrite = {"Subagents": subagents_arg} if was_str and isinstance(subagents_arg, list) else None
            return antigravity_sandbox_gate.GatingDecision(decision="allow", reason="", overwrite=overwrite)

        caller_desc = get_caller_descriptor(conversation_id, payload=data)
        is_role_worker = bool(caller_desc and caller_desc.get("typeName") == "cleanroom_role_worker")
        is_coordinator = bool(caller_desc and caller_desc.get("typeName") == "cleanroom_coordinator")

        if is_coordinator:
            if tool_name in ("replace_file_content", "write_to_file"):
                return antigravity_sandbox_gate.GatingDecision(
                    decision="deny",
                    reason=DENY_REASON_COORDINATOR_FILE_TOOL,
                )
            if tool_name == "run_command":
                cmd = args.get("CommandLine", "")
                if not isinstance(cmd, str):
                    cmd = str(cmd or "")
                is_allowed, deny_reason = self.validate_coordinator_command(cmd)
                if not is_allowed:
                    return antigravity_sandbox_gate.GatingDecision(decision="deny", reason=deny_reason)
                return antigravity_sandbox_gate.GatingDecision(decision="allow", reason="")
            return antigravity_sandbox_gate.GatingDecision(decision="allow", reason="")

        if not is_role_worker:
            return antigravity_sandbox_gate.GatingDecision(decision="allow", reason="")

        # Role worker run_command check
        if tool_name == "run_command":
            cmd = args.get("CommandLine", "")
            if not isinstance(cmd, str):
                cmd = str(cmd or "")
            is_allowed, deny_reason = self.validate_worker_command(cmd)
            if not is_allowed:
                return antigravity_sandbox_gate.GatingDecision(decision="deny", reason=deny_reason)
            return antigravity_sandbox_gate.GatingDecision(decision="allow", reason="")

        # Role worker file access check
        if tool_name in ("view_file", "replace_file_content", "write_to_file"):
            sent_path = get_sentinel_path(workspace_root)
            if not os.path.exists(sent_path):
                return antigravity_sandbox_gate.GatingDecision(
                    decision="deny",
                    reason="Cleanroom MCP server is not running. File access denied to preserve sandbox confinement.",
                )
            sentinel_data = read_sentinel_file(sent_path)
            if not sentinel_data or not is_process_alive(sentinel_data.get("pid")):
                return antigravity_sandbox_gate.GatingDecision(
                    decision="deny",
                    reason="Cleanroom MCP server has crashed or is unreadable. File access denied.",
                )

            port = int(sentinel_data.get("port", 8765))
            host = os.environ.get("MCP_HOST", "127.0.0.1")
            subagents = [str(x) for x in sentinel_data.get("subagents", [])]
            sessions_map = self.read_worker_sessions()

            target_session: Optional[str] = None
            if conversation_id in subagents:
                target_session = conversation_id
            elif conversation_id in sessions_map and sessions_map[conversation_id] in subagents:
                target_session = sessions_map[conversation_id]
            elif len(subagents) == 1:
                target_session = subagents[0]
            else:
                role_hint = str(caller_desc.get("role", "") if caller_desc else "").lower()
                for s in subagents:
                    if s.lower() in role_hint or role_hint.endswith(s.lower()):
                        target_session = s
                        break

            if not target_session:
                return antigravity_sandbox_gate.GatingDecision(
                    decision="deny",
                    reason=f"Cleanroom security violation: No active role session registered for worker '{conversation_id}'.",
                )

            file_path = str(args.get("AbsolutePath") or args.get("TargetFile") or args.get("path") or "").strip('"\'')
            is_allowed, reason = validate_via_http(host, port, target_session, tool_name, file_path)
            if is_allowed:
                return antigravity_sandbox_gate.GatingDecision(decision="allow", reason="")
            return antigravity_sandbox_gate.GatingDecision(decision="deny", reason=reason)

        return antigravity_sandbox_gate.GatingDecision(
            decision="deny",
            reason=f"Cleanroom security violation: Tool '{tool_name}' is not permitted for role workers.",
        )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AntigravitySandboxGate,
        keys=[AntigravitySandboxGate, antigravity_sandbox_gate.AntigravitySandboxGate],
        tier=system,
    )


_initialize_ = __initialize__

