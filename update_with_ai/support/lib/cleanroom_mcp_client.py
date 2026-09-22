#!/usr/bin/env python3
"""cleanroom_mcp_client.py — CLI helper for invoking Cleanroom FastMCP tools.

Enables role workers and scripts to call MCP tools synchronously via CLI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Optional

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from mcp import ClientSession
from mcp.client.sse import sse_client

try:
    from update_with_ai.support.lib import cleanroom_run_logger
except ImportError:
    try:
        import cleanroom_run_logger  # type: ignore
    except ImportError:
        cleanroom_run_logger = None  # type: ignore


async def _call_tool_async(
    port: int,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    url = f"http://127.0.0.1:{port}/sse"
    async with sse_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                return "\n".join(c.text for c in result.content if hasattr(c, "text"))
            return "OK"


def call_tool(
    tool_name: str,
    arguments: dict[str, Any],
    port: int = 8765,
) -> str:
    return asyncio.run(_call_tool_async(port, tool_name, arguments))


def main() -> int:
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--session",
        "-s",
        default=argparse.SUPPRESS,
        help="Session/conversation identifier (e.g. qa, lib, test)",
    )

    parser = argparse.ArgumentParser(
        description="Cleanroom FastMCP CLI Client",
        parents=[parent_parser],
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8765")))
    subparsers = parser.add_subparsers(dest="command", required=True)

    # register
    p_reg = subparsers.add_parser("register", parents=[parent_parser], help="Register role agent session")
    p_reg.add_argument("--role", required=True, help="Role address (e.g. //update_python_with_ai:lib)")
    p_reg.add_argument("--unit", required=True, help="Unit root (e.g. //testing/parts/sandbox:sandbox_asm)")

    # deregister
    subparsers.add_parser("deregister", parents=[parent_parser], help="Deregister role agent session")

    # get-work
    subparsers.add_parser("get-work", parents=[parent_parser], help="Request work prompt for active role session")

    # next-batch
    p_next = subparsers.add_parser("next-batch", help="Query next ready batch of dirty nodes from the DAG")
    p_next.add_argument("target", nargs="?", default=None, help="define_node target shortcut (e.g. //testing/parts/sandbox:sandbox_asm_qa)")
    p_next.add_argument("--unit", default=None, help="Target unit address (e.g. //testing/parts/sandbox:sandbox_asm)")
    p_next.add_argument("--role", default=None, help="Target role address (e.g. //update_python_with_ai:qa)")

    # check-files
    subparsers.add_parser("check-files", parents=[parent_parser], help="Run verification checks across all open targets")

    # check-file (backward compatibility)
    p_check = subparsers.add_parser("check-file", parents=[parent_parser], help="Run verification checks (alias for check-files)")
    p_check.add_argument("--file", required=False, default=None, help="Optional relative path to file")

    # submit
    p_sub = subparsers.add_parser("submit", parents=[parent_parser], help="Submit completed task for verification")
    p_sub.add_argument("--target", required=False, default=None, help="Target file to submit individually")
    p_sub.add_argument("--change-summary", required=False, default="", help="Summary of changes")

    # blame
    p_blame = subparsers.add_parser("blame", parents=[parent_parser], help="Blame upstream dependency for contract failure")
    p_blame.add_argument("--blame-target", "--to", dest="blame_target", required=False, default=None, help="Target upstream file or node to blame")
    p_blame.add_argument("--target", required=False, default=None, help="Current session target experiencing the defect")
    p_blame.add_argument("--explanation", "--message", dest="explanation", required=True, help="Feedback / defect explanation message")

    # fail
    p_fail = subparsers.add_parser("fail", parents=[parent_parser], help="Fail active task")
    p_fail.add_argument("--target", required=False, default=None, help="Target node to fail")
    p_fail.add_argument("--explanation", "--message", dest="explanation", required=True, help="Failure explanation message")

    # shutdown
    subparsers.add_parser("shutdown", parents=[parent_parser], help="Shut down Cleanroom FastMCP server")

    args = parser.parse_args()

    session_id: Optional[str] = getattr(args, "session", None)
    if not session_id and getattr(args, "role", None):
        session_id = args.role.split(":")[-1]

    def _with_session(payload: dict[str, Any]) -> dict[str, Any]:
        if session_id:
            payload["conversation_id"] = session_id
        return payload

    try:
        if args.command == "register":
            payload = _with_session({"role": args.role, "unit_root": args.unit})
            res = call_tool("register_role_agent", payload, port=args.port)
            if cleanroom_run_logger:
                cleanroom_run_logger.log_event(
                    "REGISTER",
                    f"worker:{session_id}",
                    f"Registered session for role `{args.role}` at unit `{args.unit}`",
                )
            print(res)
        elif args.command == "deregister":
            res = call_tool("deregister_role_agent", _with_session({}), port=args.port)
            if cleanroom_run_logger:
                cleanroom_run_logger.log_event(
                    "DEREGISTER",
                    f"worker:{session_id}",
                    f"Deregistered session `{session_id}`",
                )
            print(res)
        elif args.command == "get-work":
            res = call_tool("get_work", _with_session({}), port=args.port)
            if cleanroom_run_logger:
                cleanroom_run_logger.log_event(
                    "GET_WORK",
                    f"worker:{session_id}",
                    "Retrieved task prompt and instructions",
                )
            print(res)
        elif args.command == "next-batch":
            unit_addr = getattr(args, "unit", None)
            role_addr = getattr(args, "role", None)
            target_shortcut = getattr(args, "target", None)
            if target_shortcut and (not unit_addr or not role_addr):
                from update_with_ai.support.lib.cleanroom_dag_cli import resolve_define_node_target
                resolved_role, resolved_unit = resolve_define_node_target(target_shortcut)
                unit_addr = unit_addr or resolved_unit
                role_addr = role_addr or resolved_role
            if not unit_addr or not role_addr:
                sys.stderr.write("Error: next-batch requires either a positional target or both --unit and --role\n")
                return 1
            if cleanroom_run_logger:
                cleanroom_run_logger.get_or_create_active_run(target=target_shortcut or f"{unit_addr}_{role_addr}")
            res = call_tool("next_batch", {"unit_address": unit_addr, "role_address": role_addr}, port=args.port)
            if cleanroom_run_logger:
                try:
                    data = json.loads(res)
                    if data.get("is_complete"):
                        cleanroom_run_logger.log_event("CONVERGED", "coordinator", "DAG convergence achieved (is_complete: true)")
                    else:
                        batch = data.get("batch", [])
                        ready_role = data.get("ready_role", "")
                        cleanroom_run_logger.log_event("NEXT_BATCH", "coordinator", f"Wave ready: `{ready_role}` with {len(batch)} unit(s)")
                except Exception:
                    cleanroom_run_logger.log_event("NEXT_BATCH", "coordinator", "Queried next batch")
            print(res)
        elif args.command in ("check-files", "check-file"):
            try:
                res = call_tool("check_files", _with_session({}), port=args.port)
            except Exception:
                res = call_tool("check_file", _with_session({}), port=args.port)
            if cleanroom_run_logger:
                status = "PASSED" if ("passed" in res.lower() or "0 errors" in res.lower()) else "FAILED"
                summary_line = res.strip().split("\n")[0] if res else ""
                cleanroom_run_logger.log_event("CHECK_FILES", f"worker:{session_id}", f"Verification {status}: {summary_line}")
            print(res)
        elif args.command == "submit":
            payload = {}
            target_val = getattr(args, "target", None)
            summary_val = getattr(args, "change_summary", None) or ""
            if target_val:
                payload["target"] = target_val
            if summary_val:
                payload["change_summary"] = summary_val
            res = call_tool("submit", _with_session(payload), port=args.port)
            if cleanroom_run_logger:
                cleanroom_run_logger.log_event("SUBMIT", f"worker:{session_id}", f"Submitted `{target_val or 'batch'}`: {summary_val}")
            print(res)
        elif args.command == "blame":
            payload = {"explanation": args.explanation}
            if getattr(args, "blame_target", None):
                payload["blame_target"] = args.blame_target
            if getattr(args, "target", None):
                payload["target"] = args.target
            res = call_tool("blame", _with_session(payload), port=args.port)
            if cleanroom_run_logger:
                cleanroom_run_logger.log_event("BLAME", f"worker:{session_id}", f"Blamed `{args.blame_target}`: {args.explanation}")
            print(res)
        elif args.command == "fail":
            payload = {"explanation": args.explanation}
            if getattr(args, "target", None):
                payload["target"] = args.target
            res = call_tool("fail", _with_session(payload), port=args.port)
            if cleanroom_run_logger:
                cleanroom_run_logger.log_event("FAIL", f"worker:{session_id}", f"Failed active task: {args.explanation}")
            print(res)
        elif args.command == "shutdown":
            res = call_tool("shutdown", {}, port=args.port)
            if cleanroom_run_logger:
                cleanroom_run_logger.log_event("SHUTDOWN", "coordinator", "Cleanroom FastMCP server shutdown")
                cleanroom_run_logger.finish_run("COMPLETED")
            print(res)
        return 0
    except Exception as e:
        sys.stderr.write(f"Error calling MCP tool '{args.command}': {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
