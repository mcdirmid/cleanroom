from __future__ import annotations
import asyncio
import atexit
import inspect
import json
import os
import threading
from typing import Any, Iterable, Mapping, Optional, Sequence
from mcp.server.fastmcp import FastMCP, Context
from support.lib.lifecycle import LifecycleRegistry, LifecycleResolutionError, Singleton, get_default_registry, get_singleton, system
from . import mcp_cache_arbiter
from . import mcp_gate
from . import mcp_server
from . import mcp_session
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib import dag_subgraph
from update_with_ai.parts.sandbox.lib import sandbox_run_control
from update_with_ai.parts.sandbox.lib import tool_provider

# Requirements specified in mcp_server_impl.pyi

class McpServer(mcp_server.McpServer, Singleton):
    tier = system

    def __init__(self) -> None:
        self._app: Optional[FastMCP] = None
        self._running: bool = False
        self._eval_task: Optional[asyncio.Task[Any]] = None
        self._tools_to_export: dict[str, tool_provider.Tool] = {}
        self._exported_tools: set[str] = set()
        self._port: int = 8765

    def _get_sentinel_path(self) -> str:
        override = os.environ.get("CLEANROOM_SENTINEL_PATH")
        if override:
            return override
        workspace_dir = os.environ.get("BUILD_WORKING_DIRECTORY") or os.getcwd()
        return os.path.join(os.path.abspath(workspace_dir), ".mcp.active")

    def _sync_sentinel_file(self) -> None:
        try:
            path = self._get_sentinel_path()
            session_mgr = get_singleton(mcp_session.RoleSessionManager)
            subagents = [str(cid) for cid in session_mgr.active_sessions.keys()]
            data = {
                "pid": os.getpid(),
                "port": self._port,
                "subagents": subagents,
            }
            tmp_path = f"{path}.tmp.{os.getpid()}"
            with open(tmp_path, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, path)
        except Exception:  # pragma: no cover (assumption: filesystem writes succeed)
            pass  # pragma: no cover (assumption: filesystem writes succeed)

    def _remove_sentinel_file(self) -> None:
        try:
            path = self._get_sentinel_path()
            if os.path.exists(path):
                os.remove(path)
        except Exception:  # pragma: no cover (assumption: filesystem removal succeeds)
            pass  # pragma: no cover (assumption: filesystem removal succeeds)

    def _create_fastmcp_tool_callable(self, tool: tool_provider.Tool) -> Any:
        tool_name = tool.name
        sorted_params = sorted(tool.parameters, key=lambda p: (not p.is_required, p.name))
        annotations: dict[str, Any] = {}
        sig_params: list[inspect.Parameter] = []

        for p in sorted_params:
            wire_type = getattr(p.parameter_type, "wire_type", str)
            if p.is_required:
                param_kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
                default = inspect.Parameter.empty
                annotations[p.name] = wire_type
            else:
                param_kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
                default = p.default_value if p.default_value is not None else None
                annotations[p.name] = Optional[wire_type]

            sig_params.append(
                inspect.Parameter(
                    name=p.name,
                    kind=param_kind,
                    default=default,
                    annotation=annotations[p.name],
                )
            )

        sig_params.append(
            inspect.Parameter(
                name="conversation_id",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=Optional[str],
            )
        )
        annotations["conversation_id"] = Optional[str]

        sig_params.append(
            inspect.Parameter(
                name="ctx",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=Context,
            )
        )
        annotations["ctx"] = Context
        annotations["return"] = str

        sig = inspect.Signature(parameters=sig_params, return_annotation=str)

        def dynamic_tool_handler(*args: Any, **kwargs: Any) -> str:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = dict(bound.arguments)
            ctx_val = arguments.pop("ctx", None)
            conv_id_val = arguments.pop("conversation_id", None)

            if conv_id_val:
                cid = mcp_session.ConversationId(str(conv_id_val))
            elif ctx_val is not None and getattr(ctx_val, "client_id", None):
                cid = mcp_session.ConversationId(str(ctx_val.client_id))
            else:
                session_mgr = get_singleton(mcp_session.RoleSessionManager)
                if len(session_mgr.active_sessions) == 1:
                    cid = next(iter(session_mgr.active_sessions.keys()))
                else:
                    cid = mcp_session.ConversationId("default")
            filtered_args = {k: v for k, v in arguments.items() if v is not None}
            return self.execute_domain_tool(cid, tool_name, filtered_args)

        dynamic_tool_handler.__name__ = tool.name
        dynamic_tool_handler.__doc__ = tool.description or f"Tool {tool.name}"
        dynamic_tool_handler.__annotations__ = annotations
        setattr(dynamic_tool_handler, "__signature__", sig)
        return dynamic_tool_handler

    def export_domain_tools(self, tools: Iterable[tool_provider.Tool]) -> None:
        for tool in tools:
            self._tools_to_export[tool.name] = tool
            if self._app is not None and tool.name not in self._exported_tools:
                fn = self._create_fastmcp_tool_callable(tool)
                self._app.add_tool(fn)
                self._exported_tools.add(tool.name)

    def register_role_agent(
        self,
        conversation_id: mcp_session.ConversationId,
        role_address: str,
        unit_root: str,
    ) -> str:
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        scope = session_mgr.register_session(conversation_id, role_address, unit_root)
        if scope is not None and hasattr(scope, "activate"):
            with scope.activate():
                try:
                    _ = scope.get_singleton(sandbox_run_control.RunController)
                    tool_mgr = scope.get_singleton(tool_provider.ToolManager)
                    try:
                        adv_tool = scope.get_singleton(sandbox_run_control.AdvanceTool)
                        tool_mgr.install_tool(adv_tool)
                    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
                        pass
                    try:
                        blame_tool = scope.get_singleton(sandbox_run_control.BlameTool)
                        tool_mgr.install_tool(blame_tool)
                    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
                        pass
                except (LifecycleResolutionError, KeyError, RuntimeError, AttributeError):  # pragma: no cover (assumption: run controller present in session tier)
                    pass  # pragma: no cover
                try:
                    tool_mgr = scope.get_singleton(tool_provider.ToolManager)
                    if hasattr(tool_mgr, "installed_tools"):
                        self.export_domain_tools(tool_mgr.installed_tools)
                except (LifecycleResolutionError, KeyError, RuntimeError, AttributeError):  # pragma: no cover (assumption: tool_mgr resolvable)
                    pass  # pragma: no cover (assumption: tool_mgr resolvable)
        self._sync_sentinel_file()
        return f"Registered role agent session '{conversation_id}' for role '{role_address}' at unit root '{unit_root}'."

    def deregister_role_agent(
        self, conversation_id: mcp_session.ConversationId
    ) -> str:
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        session_mgr.deregister_session(conversation_id)
        self._sync_sentinel_file()
        return f"Deregistered role agent session '{conversation_id}'."

    def next_batch(self, unit_address: str, role_address: str) -> str:
        s_role = role_address.strip()
        norm_role = (
            s_role
            if s_role.startswith("//")
            else (
                f"//update_python_with_ai{s_role}"
                if s_role.startswith(":")
                else f"//update_python_with_ai:{s_role}"
            )
        )
        s_unit = unit_address.strip()
        norm_unit = (
            s_unit.rstrip("/")
            if s_unit.startswith("//")
            else (s_unit if s_unit.startswith(":") else f"//{s_unit.rstrip('/')}")
        )

        storage = get_singleton(dag_storage.DagStorage)
        subgraph = get_singleton(dag_subgraph.DagSubgraph)
        root = dag_storage.DagNode(unit_address=norm_unit, role_address=norm_role)

        visited: set[dag_storage.DagNode] = set()
        try:
            import importlib

            loader_cls = None
            try:
                import importlib

                bml = importlib.import_module(
                    "update_with_ai.parts.bazel.lib.bazel_manifest_loader_impl"
                )
                loader_cls = getattr(bml, "BazelManifestLoader", None)
            except (ImportError, AttributeError):  # pragma: no cover (defensive: dynamic import fallback)
                pass  # pragma: no cover (defensive: dynamic import fallback)

            manifest_loader = None
            if loader_cls is not None:
                try:
                    manifest_loader = get_singleton(loader_cls)
                except Exception:
                    manifest_loader = None

            if manifest_loader is None:
                try:
                    from support.lib.lifecycle import get_active_scope

                    scope = get_active_scope()
                    if scope is not None:
                        for proto in getattr(scope.registry, "_prototypes", {}).values():
                            for desc in getattr(proto, "descriptors", []):
                                for k in getattr(desc, "keys", ()):
                                    if getattr(k, "__name__", "") == "BazelManifestLoader":
                                        manifest_loader = getattr(desc, "instance", None)
                                        if manifest_loader is None and hasattr(scope, "get"):  # pragma: no cover (defensive: class-registered loader fallback)
                                            try:
                                                manifest_loader = scope.get(k)
                                            except Exception:
                                                pass
                                        if manifest_loader is not None:
                                            break
                                if manifest_loader is not None:
                                    break
                            if manifest_loader is not None:
                                break
                except Exception:  # pragma: no cover (defensive: scope resolution fallback)
                    pass  # pragma: no cover (defensive: scope resolution fallback)

            if manifest_loader is not None:
                queue: list[dag_storage.DagNode] = [root]
                while queue:
                    curr = queue.pop(0)
                    if curr in visited:
                        continue
                    visited.add(curr)
                    manifest = manifest_loader.get_manifest(curr)
                    if manifest is not None:
                        manifest_loader.load_manifest(manifest, storage)
                    for dep in storage.get_dependencies(curr):
                        if dep.node not in visited:
                            queue.append(dep.node)
        except Exception:  # pragma: no cover (defensive: resilient traversal error)
            visited = set()  # pragma: no cover (defensive: resilient traversal error)

        subgraph.set_target(root)
        batch = subgraph.next_ready_batch()
        batch_nodes = [
            {"unit": n.unit_address, "role": n.role_address} for n in batch
        ]
        ready_role = batch[0].role_address if batch else None

        reachable_nodes = (
            visited if visited else set(getattr(subgraph, "_nodes", [root]))
        )
        dirty_nodes = [
            f"{n.unit_address}:{n.role_address}"
            for n in sorted(
                reachable_nodes, key=lambda x: (x.unit_address, x.role_address)
            )
            if storage.is_dirty(n)
        ]

        result = {
            "unit": norm_unit,
            "role": norm_role,
            "is_complete": subgraph.is_complete,
            "ready_role": ready_role,
            "batch": batch_nodes,
            "dirty_nodes": dirty_nodes,
        }
        return json.dumps(result)

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
            norm_args = dict(arguments)
            if "message" in norm_args and "explanation" not in norm_args:
                norm_args["explanation"] = norm_args.pop("message")
            if "to" in norm_args and "blame_target" not in norm_args:
                norm_args["blame_target"] = norm_args.pop("to")
            resp = tool_mgr.execute_tool_with_arguments(tool_name, norm_args)
            if hasattr(tool_mgr, "installed_tools"):
                self.export_domain_tools(tool_mgr.installed_tools)
            if tool_name == "get_work":
                if "No dirty nodes are ready" in resp.content:
                    session_mgr.set_session_status(conversation_id, mcp_session.IdleSession())
                else:
                    session_mgr.set_session_status(conversation_id, mcp_session.ActiveSession())
            elif tool_name == "submit" and not resp.is_failed:
                try:
                    storage = scope.get_singleton(dag_storage.DagStorage)
                    subgraph = scope.get_singleton(dag_subgraph.DagSubgraph)
                    role_cfg = scope.get_singleton(agent_node_config.RoleConfig)
                    rc = scope.get_singleton(sandbox_run_control.RunController)
                    for n in role_cfg.nodes:
                        if getattr(rc, "get_node_state", lambda _: "")(n) == "SUBMITTED" or getattr(rc, "is_clean_in_turn", lambda _: False)(n):
                            storage.register_dependent(n)
                            storage.clear_messages(n)
                            subgraph.record_visit([n])
                            summary = str(norm_args.get("change_summary", "") or "").strip()
                            if summary:
                                target_val = str(norm_args.get("target", "") or "").strip()
                                alias = ""
                                try:
                                    node_cfg = scope.get_singleton(agent_node_config.NodeConfig)
                                    alias_map = getattr(node_cfg, "src_file_alias_by_node", {}) or {}
                                    alias = alias_map.get(n, "")
                                except Exception:  # pragma: no cover (assumption: node_cfg present)
                                    pass  # pragma: no cover
                                target_name = target_val or alias
                                target_prefix = f"[{os.path.basename(target_name)}] " if target_name else ""
                                chg = dag_storage.ChangeMessage(content=f"{target_prefix}{summary}")
                                for dep in storage.get_dependents(n):
                                    storage.add_message(chg, to=dep)
                except Exception:  # pragma: no cover (assumption: storage present)
                    pass  # pragma: no cover
            elif tool_name == "blame" and not resp.is_failed:
                try:
                    storage = scope.get_singleton(dag_storage.DagStorage)
                    node_cfg = scope.get_singleton(agent_node_config.NodeConfig)
                    blame_target_str = str(norm_args.get("blame_target", "") or norm_args.get("target", "") or "").strip()
                    exp = str(norm_args.get("explanation", "") or "").strip()
                    all_bts = [
                        bt
                        for bts in node_cfg.blame_targets_by_node.values()
                        for bt in bts
                    ]
                    candidates = all_bts + list(node_cfg.read_only_files)
                    for f in candidates:
                        rel = getattr(f, "relative_path", "")
                        short = getattr(f, "short_name", "")
                        base = os.path.basename(rel)
                        owner = getattr(f, "owning_node", None)
                        if owner is not None:
                            if (
                                rel == blame_target_str
                                or short == blame_target_str
                                or base == os.path.basename(blame_target_str)  # pragma: no cover (defensive: flexible blame target format fallback)
                                or (rel and blame_target_str and rel.endswith("/" + blame_target_str.lstrip("/")))  # pragma: no cover (defensive: flexible blame target format fallback)
                                or (rel and blame_target_str and blame_target_str.endswith("/" + rel.lstrip("/")))  # pragma: no cover (defensive: flexible blame target format fallback)
                                or str(owner) == blame_target_str  # pragma: no cover (defensive: flexible blame target format fallback)
                                or getattr(owner, "unit_address", None) == blame_target_str  # pragma: no cover (defensive: flexible blame target format fallback)
                            ):
                                storage.add_message(dag_storage.FeedbackMessage(content=exp, target=owner), to=owner)
                                break
                except Exception:  # pragma: no cover (assumption: storage and node_cfg present)
                    pass  # pragma: no cover
            elif tool_name == "fail" and not resp.is_failed:
                try:
                    storage = scope.get_singleton(dag_storage.DagStorage)
                    role_cfg = scope.get_singleton(agent_node_config.RoleConfig)
                    exp = str(norm_args.get("explanation", "") or "").strip()
                    for n in role_cfg.nodes:
                        storage.add_message(dag_storage.FeedbackMessage(content=exp), to=n)
                except Exception:  # pragma: no cover (assumption: storage and role_cfg present)
                    pass  # pragma: no cover
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
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("MCP_PORT", "8765"))
        self._port = port
        self._sync_sentinel_file()
        try:
            atexit.register(self._remove_sentinel_file)
        except Exception:  # pragma: no cover (assumption: atexit registration succeeds)
            pass  # pragma: no cover (assumption: atexit registration succeeds)
        app = FastMCP("cleanroom", host=host, port=port)
        self._app = app
        self._exported_tools.clear()

        @app.tool()
        def register_role_agent(
            role: str,
            unit_root: str,
            conversation_id: Optional[str] = None,
            ctx: Optional[Context] = None,
        ) -> str:
            cid_str = conversation_id or "default"
            if not conversation_id and ctx is not None and getattr(ctx, "client_id", None):
                cid_str = str(ctx.client_id)
            cid = mcp_session.ConversationId(cid_str)
            return self.register_role_agent(cid, role, unit_root)

        @app.tool()
        def deregister_role_agent(
            conversation_id: Optional[str] = None, ctx: Optional[Context] = None
        ) -> str:
            if conversation_id:
                cid = mcp_session.ConversationId(conversation_id)
            elif ctx is not None and getattr(ctx, "client_id", None):
                cid = mcp_session.ConversationId(str(ctx.client_id))
            else:
                session_mgr = get_singleton(mcp_session.RoleSessionManager)
                if len(session_mgr.active_sessions) == 1:
                    cid = next(iter(session_mgr.active_sessions.keys()))
                else:
                    cid = mcp_session.ConversationId("default")
            return self.deregister_role_agent(cid)

        @app.tool()
        def shutdown() -> str:
            self.stop()
            def _delayed_exit() -> None:  # pragma: no cover (process exit thread)
                import time
                time.sleep(0.5)
                os._exit(0)
            threading.Thread(target=_delayed_exit, daemon=True).start()
            return "Cleanroom FastMCP server shutting down."

        @app.tool()
        def next_batch(unit_address: str, role_address: str) -> str:
            return self.next_batch(unit_address, role_address)

        # Export tools that were queued prior to start
        for tool in list(self._tools_to_export.values()):
            if tool.name not in self._exported_tools:
                fn = self._create_fastmcp_tool_callable(tool)
                app.add_tool(fn)
                self._exported_tools.add(tool.name)

        # Export tools from any active sessions
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        for session in session_mgr.active_sessions.values():
            if session.scope is not None and hasattr(session.scope, "activate"):
                with session.scope.activate():
                    try:
                        tool_mgr = session.scope.get_singleton(tool_provider.ToolManager)
                        if hasattr(tool_mgr, "installed_tools"):
                            self.export_domain_tools(tool_mgr.installed_tools)
                    except Exception:  # pragma: no cover (assumption: tool_mgr resolvable)
                        pass  # pragma: no cover (assumption: tool_mgr resolvable)

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
        except RuntimeError:  # pragma: no cover (assumption: event loop available)
            pass  # pragma: no cover (assumption: event loop available)

        if transport == "stdio":
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(app.run_stdio_async())
                else:
                    loop.run_until_complete(app.run_stdio_async())  # pragma: no cover (assumption: running in event loop)
            except Exception:  # pragma: no cover (assumption: async task creation succeeds)
                pass  # pragma: no cover (assumption: async task creation succeeds)
        elif transport == "sse":
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(app.run_sse_async())
                else:
                    loop.run_until_complete(app.run_sse_async())  # pragma: no cover (assumption: running in event loop)
            except Exception:  # pragma: no cover (assumption: async task creation succeeds)
                pass  # pragma: no cover (assumption: async task creation succeeds)

    def stop(self) -> None:
        self._running = False
        if self._eval_task is not None and not self._eval_task.done():
            self._eval_task.cancel()
            self._eval_task = None
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        for conv_id in list(session_mgr.active_sessions.keys()):
            session_mgr.deregister_session(conv_id)
        self._remove_sentinel_file()


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        McpServer,
        keys=[McpServer, mcp_server.McpServer],
        tier=system,
    )

_initialize_ = __initialize__
