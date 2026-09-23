# Requirements specified in antigravity_mcp_client_impl.pyi
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Mapping, Optional, Sequence

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)
if not os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
    os.environ["BUILD_WORKSPACE_DIRECTORY"] = _repo_root

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import antigravity_mcp_client


async def _call_tool_sse(host: str, port: int, tool_name: str, arguments: Mapping[str, Any]) -> str:
    mcp_pkg = importlib.import_module("mcp")
    client_session_cls = getattr(mcp_pkg, "ClientSession")
    sse_mod = importlib.import_module("mcp.client.sse")
    sse_client_fn = getattr(sse_mod, "sse_client")

    url = f"http://{host}:{port}/sse"
    async with sse_client_fn(url) as (read_stream, write_stream):
        async with client_session_cls(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, dict(arguments))
            if getattr(result, "content", None):
                texts = [
                    getattr(c, "text", "")
                    for c in result.content
                    if getattr(c, "text", None) is not None
                ]
                if texts:
                    return "\n".join(texts)
            return "OK"


class AntigravityMcpClient(antigravity_mcp_client.AntigravityMcpClient, Singleton):
    tier = system

    def call_tool(self, name: str, arguments: Mapping[str, Any], port: int = 8765) -> str:
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        try:
            import asyncio
            return asyncio.run(_call_tool_sse(host, port, name, arguments))
        except Exception:
            pass

        url = f"http://{host}:{port}/call_tool"
        payload = json.dumps({"name": name, "arguments": dict(arguments)}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict):
                    content = data.get("content", [])
                    if isinstance(content, list) and content:
                        first = content[0]
                        if isinstance(first, dict) and "text" in first:
                            return str(first["text"])
                    if "text" in data:
                        return str(data["text"])
                return json.dumps(data)
        except urllib.error.URLError as e:
            return f"Error connecting to Cleanroom MCP server at http://{host}:{port}/call_tool: {e}"
        except Exception as e:
            return f"Error executing tool '{name}': {e}"

    def register_session(self, identifier: str, role: str, unit: str, port: int = 8765) -> str:
        return self.call_tool(
            "register_role_agent",
            {"conversation_id": identifier, "role": role, "unit_root": unit},
            port=port,
        )

    def deregister_session(self, identifier: str, port: int = 8765) -> str:
        return self.call_tool(
            "deregister_role_agent",
            {"conversation_id": identifier},
            port=port,
        )

    def get_work(self, identifier: str, port: int = 8765) -> str:
        return self.call_tool("get_work", {"conversation_id": identifier}, port=port)

    def check_files(self, identifier: str, port: int = 8765) -> str:
        return self.call_tool("check_files", {"conversation_id": identifier}, port=port)

    def submit(self, identifier: str, target: str, summary: str, port: int = 8765) -> str:
        return self.call_tool(
            "submit",
            {"conversation_id": identifier, "target": target, "change_summary": summary},
            port=port,
        )

    def blame(self, identifier: str, target: str, blame_target: str, explanation: str, port: int = 8765) -> str:
        return self.call_tool(
            "blame",
            {
                "conversation_id": identifier,
                "target": target,
                "blame_target": blame_target,
                "explanation": explanation,
            },
            port=port,
        )

    def shutdown(self, port: int = 8765) -> str:
        return self.call_tool("shutdown", {}, port=port)

    def next_batch(self, unit: str, port: int = 8765) -> str:
        s_role = "//update_python_with_ai:qa"
        s_unit = unit
        if ":" in unit:
            base, target_name = unit.split(":", 1)
            for action in ("_clean", "_dirty", "_change", "_feedback", "_prompt"):
                if target_name.endswith(action):
                    target_name = target_name[: -len(action)]
                    break
            for role_sfx in ("_qa", "_test", "_lib", "_low", "_high"):
                if target_name.endswith(role_sfx):
                    clean_name = target_name[: -len(role_sfx)]
                    s_role = f"//update_python_with_ai:{role_sfx.lstrip('_')}"
                    s_unit = f"{base}:{clean_name}"
                    break
        return self.call_tool(
            "next_batch",
            {"unit_address": s_unit, "role_address": s_role},
            port=port,
        )


def call_tool(tool_name: str, arguments: Mapping[str, Any], port: int = 8765) -> str:
    return AntigravityMcpClient().call_tool(tool_name, arguments, port=port)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AntigravityMcpClient,
        keys=[AntigravityMcpClient, antigravity_mcp_client.AntigravityMcpClient],
        tier=system,
    )


_initialize_ = __initialize__


def _get_gate() -> Optional[Any]:
    try:
        from update_with_ai.parts.antigravity.lib import antigravity_sandbox_gate
        return get_singleton(antigravity_sandbox_gate.AntigravitySandboxGate)
    except Exception:
        try:
            gate_mod = importlib.import_module("update_with_ai.parts.antigravity.lib.antigravity_sandbox_gate_impl")
            return gate_mod.AntigravitySandboxGate()
        except Exception:
            return None


def _get_logger() -> Optional[Any]:
    try:
        from update_with_ai.parts.antigravity.lib import antigravity_run_logger
        return get_singleton(antigravity_run_logger.AntigravityRunLogger)
    except Exception:
        try:
            logger_mod = importlib.import_module("update_with_ai.parts.antigravity.lib.antigravity_run_logger_impl")
            return logger_mod.AntigravityRunLogger()
        except Exception:
            return None


def _record_worker_status(session_id: Optional[str], status: str, unit: Optional[str] = None) -> None:
    if not session_id:
        return
    try:
        from update_with_ai.parts.antigravity.lib import antigravity_coordinator
        coord = get_singleton(antigravity_coordinator.AntigravityCoordinator)
        import time
        coord.record_worker_status(str(session_id), status, root=_repo_root, now=time.time(), unit=unit or "")
    except Exception:
        pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--session",
        "-s",
        default=argparse.SUPPRESS,
        help="Session/conversation identifier",
    )

    parser = argparse.ArgumentParser(
        description="Cleanroom FastMCP CLI Client",
        parents=[parent_parser],
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8765")))
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_reg = subparsers.add_parser("register", parents=[parent_parser], help="Register role agent session")
    p_reg.add_argument("--role", required=True, help="Role address")
    p_reg.add_argument("--unit", required=True, help="Unit root")
    p_reg.add_argument("--worker-id", "--conv-id", dest="worker_id", required=False, default=None)

    p_dereg = subparsers.add_parser("deregister", parents=[parent_parser], help="Deregister role agent session")
    p_dereg.add_argument("--worker-id", "--conv-id", dest="worker_id", required=False, default=None)

    subparsers.add_parser("get-work", parents=[parent_parser], help="Request work prompt for active role session")

    p_next = subparsers.add_parser("next-batch", help="Query next ready batch")
    p_next.add_argument("target", nargs="?", default=None)
    p_next.add_argument("--unit", default=None)
    p_next.add_argument("--role", default=None)

    subparsers.add_parser("check-files", parents=[parent_parser], help="Run verification checks")
    p_check = subparsers.add_parser("check-file", parents=[parent_parser], help="Run verification checks")
    p_check.add_argument("--file", required=False, default=None)

    p_sub = subparsers.add_parser("submit", parents=[parent_parser], help="Submit completed task")
    p_sub.add_argument("--target", required=False, default=None)
    p_sub.add_argument("--change-summary", required=False, default="")

    p_blame = subparsers.add_parser("blame", parents=[parent_parser], help="Blame upstream dependency")
    p_blame.add_argument("--blame-target", "--to", dest="blame_target", required=False, default=None)
    p_blame.add_argument("--target", required=False, default=None)
    p_blame.add_argument("--explanation", "--message", dest="explanation", required=True)

    p_fail = subparsers.add_parser("fail", parents=[parent_parser], help="Fail active task")
    p_fail.add_argument("--target", required=False, default=None)
    p_fail.add_argument("--explanation", "--message", dest="explanation", required=True)

    subparsers.add_parser("shutdown", parents=[parent_parser], help="Shut down server")

    args = parser.parse_args(list(argv) if argv is not None else None)
    session_id: Optional[str] = getattr(args, "session", None)
    if not session_id and getattr(args, "role", None):
        session_id = args.role.split(":")[-1]

    def _with_session(payload: dict[str, Any]) -> dict[str, Any]:
        if session_id:
            payload["conversation_id"] = session_id
        return payload

    try:
        from update_with_ai.parts.antigravity.lib import antigravity_asm
        antigravity_asm.__initialize__()
    except Exception:
        pass

    try:
        client = get_singleton(antigravity_mcp_client.AntigravityMcpClient)
    except Exception:
        client = AntigravityMcpClient()

    try:
        if args.command == "register":
            payload = _with_session({"role": args.role, "unit_root": args.unit})
            res = client.call_tool("register_role_agent", payload, port=args.port)
            worker_id = getattr(args, "worker_id", None)
            if worker_id and session_id:
                gate = _get_gate()
                if gate:
                    try:
                        gate.save_worker_session(str(worker_id), str(session_id))
                    except Exception:
                        pass
            logger = _get_logger()
            if logger:
                try:
                    logger.log_event("REGISTER", f"worker:{session_id}", f"Registered session for role `{args.role}` at unit `{args.unit}`")
                except Exception:
                    pass
            print(res)
        elif args.command == "deregister":
            res = client.call_tool("deregister_role_agent", _with_session({}), port=args.port)
            worker_id = getattr(args, "worker_id", None)
            if session_id:
                _record_worker_status(session_id, "complete")
                gate = _get_gate()
                if gate:
                    try:
                        gate.remove_worker_session_by_session_id(str(session_id))
                        if worker_id:
                            gate.remove_worker_session(str(worker_id))
                    except Exception:
                        pass
            logger = _get_logger()
            if logger:
                try:
                    logger.log_event("DEREGISTER", f"worker:{session_id}", f"Deregistered session `{session_id}`")
                except Exception:
                    pass
            print(res)
        elif args.command == "get-work":
            res = client.call_tool("get_work", _with_session({}), port=args.port)
            logger = _get_logger()
            if logger:
                try:
                    logger.log_event("GET_WORK", f"worker:{session_id}", "Retrieved task prompt and instructions")
                except Exception:
                    pass
            print(res)
        elif args.command == "next-batch":
            unit_addr = getattr(args, "unit", None)
            role_addr = getattr(args, "role", None)
            target_shortcut = getattr(args, "target", None)
            if target_shortcut and (not unit_addr or not role_addr):
                try:
                    cli_mod = importlib.import_module("update_with_ai.support.lib.cleanroom_dag_cli")
                    fn = getattr(cli_mod, "resolve_define_node_target")
                    resolved_role, resolved_unit = fn(target_shortcut)
                    unit_addr = unit_addr or resolved_unit
                    role_addr = role_addr or resolved_role
                except Exception:
                    pass
            if not unit_addr or not role_addr:
                sys.stderr.write("Error: next-batch requires either a positional target or both --unit and --role\n")
                return 1
            res = client.call_tool("next_batch", {"unit_address": unit_addr, "role_address": role_addr}, port=args.port)
            print(res)
        elif args.command in ("check-files", "check-file"):
            try:
                res = client.call_tool("check_files", _with_session({}), port=args.port)
            except Exception:
                res = client.call_tool("check_file", _with_session({}), port=args.port)
            logger = _get_logger()
            if logger:
                try:
                    status = "PASSED" if ("passed" in res.lower() or "0 errors" in res.lower()) else "FAILED"
                    summary_line = res.strip().split("\n")[0] if res else ""
                    logger.log_event("CHECK_FILES", f"worker:{session_id}", f"Verification {status}: {summary_line}")
                except Exception:
                    pass
            print(res)
        elif args.command == "submit":
            payload: dict[str, Any] = {}
            target_val = getattr(args, "target", None)
            summary_val = getattr(args, "change_summary", None) or ""
            if target_val:
                payload["target"] = target_val
            if summary_val:
                payload["change_summary"] = summary_val
            res = client.call_tool("submit", _with_session(payload), port=args.port)
            if session_id:
                _record_worker_status(session_id, "complete", target_val)
            logger = _get_logger()
            if logger:
                try:
                    logger.log_event("SUBMIT", f"worker:{session_id}", f"Submitted `{target_val or 'batch'}`: {summary_val}")
                except Exception:
                    pass
            print(res)
        elif args.command == "blame":
            payload = {"explanation": args.explanation}
            if getattr(args, "blame_target", None):
                payload["blame_target"] = args.blame_target
            if getattr(args, "target", None):
                payload["target"] = args.target
            res = client.call_tool("blame", _with_session(payload), port=args.port)
            if session_id:
                _record_worker_status(session_id, "complete", getattr(args, "target", None))
            logger = _get_logger()
            if logger:
                try:
                    logger.log_event("BLAME", f"worker:{session_id}", f"Blamed `{args.blame_target}`: {args.explanation}")
                except Exception:
                    pass
            print(res)
        elif args.command == "fail":
            payload = {"explanation": args.explanation}
            target_val = getattr(args, "target", None)
            if target_val:
                payload["target"] = target_val
            res = client.call_tool("fail", _with_session(payload), port=args.port)
            if session_id:
                _record_worker_status(session_id, "failed", target_val)
            logger = _get_logger()
            if logger:
                try:
                    logger.log_event("FAIL", f"worker:{session_id}", f"Failed active task: {args.explanation}")
                except Exception:
                    pass
            print(res)
        elif args.command == "shutdown":
            res = client.call_tool("shutdown", {}, port=args.port)
            logger = _get_logger()
            if logger:
                try:
                    logger.log_event("SHUTDOWN", "coordinator", "Cleanroom FastMCP server shutdown")
                    logger.finish_run("COMPLETED")
                except Exception:
                    pass
            print(res)
        return 0
    except Exception as e:
        sys.stderr.write(f"Error calling MCP tool '{args.command}': {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
