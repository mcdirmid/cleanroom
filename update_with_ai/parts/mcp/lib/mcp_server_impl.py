from __future__ import annotations
import asyncio
from typing import Any, Mapping, Optional, Sequence
from mcp.server.fastmcp import FastMCP, Context
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import mcp_cache_arbiter
from . import mcp_gate
from . import mcp_server
from . import mcp_session
from update_with_ai.parts.sandbox.lib import tool_provider

# Requirements specified in mcp_server_impl.pyi

class McpServer(mcp_server.McpServer, Singleton):
    tier = system

    def __init__(self) -> None:
        self._app: Optional[FastMCP] = None
        self._running: bool = False
        self._eval_task: Optional[asyncio.Task[Any]] = None

    def register_role_agent(
        self,
        conversation_id: mcp_session.ConversationId,
        role_address: str,
        unit_root: str,
    ) -> str:
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        session_mgr.register_session(conversation_id, role_address, unit_root)
        return f"Registered role agent session '{conversation_id}' for role '{role_address}' at unit root '{unit_root}'."

    def deregister_role_agent(
        self, conversation_id: mcp_session.ConversationId
    ) -> str:
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        session_mgr.deregister_session(conversation_id)
        return f"Deregistered role agent session '{conversation_id}'."

    def execute_domain_tool(
        self,
        conversation_id: mcp_session.ConversationId,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> str:
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        session_mgr.touch_session(conversation_id)
        scope = session_mgr.get_session_scope(conversation_id)
        if scope is None:
            return f"Error: No active session registered for conversation '{conversation_id}'."

        with scope.activate():
            tool_mgr = scope.get_singleton(tool_provider.ToolManager)
            resp = tool_mgr.execute_tool_with_arguments(tool_name, arguments)
            if tool_name == "get_work":
                if "No dirty nodes are ready" in resp.content:
                    session_mgr.set_session_status(conversation_id, mcp_session.Idle())
                else:
                    session_mgr.set_session_status(conversation_id, mcp_session.Active())
            if resp.reminder:
                return f"{resp.content}\n\nReminder: {resp.reminder}"
            return resp.content

    def handle_validate_access(
        self,
        conversation_id: mcp_session.ConversationId,
        tool_name: str,
        file_path: str,
    ) -> Mapping[str, Any]:
        gate = get_singleton(mcp_gate.AccessGate)
        decision = gate.validate_access(conversation_id, tool_name, file_path)
        return {"is_allowed": decision.is_allowed, "reason": decision.reason}

    def handle_filter_dir(
        self,
        conversation_id: mcp_session.ConversationId,
        directory_path: str,
        entries: Sequence[str],
    ) -> Sequence[str]:
        gate = get_singleton(mcp_gate.AccessGate)
        return gate.filter_directory_listing(conversation_id, directory_path, entries)

    def start(self, transport: str) -> None:
        self._running = True
        app = FastMCP("cleanroom")
        self._app = app

        @app.tool()
        def register_role_agent(role: str, unit_root: str, ctx: Context) -> str:
            cid = mcp_session.ConversationId(str(ctx.client_id or "default"))
            return self.register_role_agent(cid, role, unit_root)

        @app.tool()
        def deregister_role_agent(ctx: Context) -> str:
            cid = mcp_session.ConversationId(str(ctx.client_id or "default"))
            return self.deregister_role_agent(cid)

        @app.tool()
        def get_work(ctx: Context) -> str:
            cid = mcp_session.ConversationId(str(ctx.client_id or "default"))
            return self.execute_domain_tool(cid, "get_work", {})

        @app.tool()
        def check_file(path: str, ctx: Context) -> str:
            cid = mcp_session.ConversationId(str(ctx.client_id or "default"))
            return self.execute_domain_tool(cid, "check_file", {"path": path})

        @app.tool()
        def submit(target: str, change_summary: str, ctx: Context) -> str:
            cid = mcp_session.ConversationId(str(ctx.client_id or "default"))
            return self.execute_domain_tool(
                cid, "submit", {"target": target, "change_summary": change_summary}
            )

        @app.tool()
        def blame(target: str, feedback: str, ctx: Context) -> str:
            cid = mcp_session.ConversationId(str(ctx.client_id or "default"))
            return self.execute_domain_tool(
                cid, "blame", {"target": target, "feedback": feedback}
            )

        @app.tool()
        def fail(target: str, reason: str, ctx: Context) -> str:
            cid = mcp_session.ConversationId(str(ctx.client_id or "default"))
            return self.execute_domain_tool(
                cid, "fail", {"target": target, "reason": reason}
            )

        @app.custom_route("/validate_access", methods=["POST"])
        async def validate_access_route(request: Any) -> Any:
            from starlette.responses import JSONResponse
            body = await request.json()
            cid = mcp_session.ConversationId(str(body.get("conversation_id", "default")))
            t_name = str(body.get("tool_name", ""))
            f_path = str(body.get("file_path", ""))
            res = self.handle_validate_access(cid, t_name, f_path)
            return JSONResponse(res)

        @app.custom_route("/filter_dir", methods=["POST"])
        async def filter_dir_route(request: Any) -> Any:
            from starlette.responses import JSONResponse
            body = await request.json()
            cid = mcp_session.ConversationId(str(body.get("conversation_id", "default")))
            d_path = str(body.get("directory_path", ""))
            dir_entries = list(body.get("entries", []))
            filtered = self.handle_filter_dir(cid, d_path, dir_entries)
            return JSONResponse({"entries": list(filtered)})

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                async def _background_cache_monitor() -> None:
                    arbiter = get_singleton(mcp_cache_arbiter.CacheArbiter)
                    while self._running:
                        arbiter.evaluate_all_idle_sessions()
                        await asyncio.sleep(5.0)
                self._eval_task = asyncio.create_task(_background_cache_monitor())
        except RuntimeError:
            pass

        if transport == "stdio":
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(app.run_stdio_async())
                else:
                    loop.run_until_complete(app.run_stdio_async())
            except RuntimeError:
                pass
        elif transport == "sse":
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(app.run_sse_async())
                else:
                    loop.run_until_complete(app.run_sse_async())
            except RuntimeError:
                pass

    def stop(self) -> None:
        self._running = False
        if self._eval_task is not None and not self._eval_task.done():
            self._eval_task.cancel()
            self._eval_task = None
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        for conv_id in list(session_mgr.active_sessions.keys()):
            session_mgr.deregister_session(conv_id)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        McpServer,
        keys=[McpServer, mcp_server.McpServer],
        tier=system,
    )

_initialize_ = __initialize__
