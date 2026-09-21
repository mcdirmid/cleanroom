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

from mcp import ClientSession
from mcp.client.sse import sse_client


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

    # check-file
    p_check = subparsers.add_parser("check-file", parents=[parent_parser], help="Run verification checks on edited file")
    p_check.add_argument("--file", required=True, help="Relative path to file")

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
            print(res)
        elif args.command == "deregister":
            res = call_tool("deregister_role_agent", _with_session({}), port=args.port)
            print(res)
        elif args.command == "get-work":
            res = call_tool("get_work", _with_session({}), port=args.port)
            print(res)
        elif args.command == "check-file":
            res = call_tool("check_file", _with_session({"path": args.file}), port=args.port)
            print(res)
        elif args.command == "submit":
            payload = {}
            if getattr(args, "target", None):
                payload["target"] = args.target
            if getattr(args, "change_summary", None):
                payload["change_summary"] = args.change_summary
            res = call_tool("submit", _with_session(payload), port=args.port)
            print(res)
        elif args.command == "blame":
            payload = {"explanation": args.explanation}
            if getattr(args, "blame_target", None):
                payload["blame_target"] = args.blame_target
            if getattr(args, "target", None):
                payload["target"] = args.target
            res = call_tool("blame", _with_session(payload), port=args.port)
            print(res)
        elif args.command == "fail":
            payload = {"explanation": args.explanation}
            if getattr(args, "target", None):
                payload["target"] = args.target
            res = call_tool("fail", _with_session(payload), port=args.port)
            print(res)
        elif args.command == "shutdown":
            res = call_tool("shutdown", {}, port=args.port)
            print(res)
        return 0
    except Exception as e:
        sys.stderr.write(f"Error calling MCP tool '{args.command}': {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
