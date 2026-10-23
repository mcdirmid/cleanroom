"""Low-level implementation for dsh_telemetry_impl."""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import subprocess
import time
from typing import Any, Dict, Optional, Set
import urllib.request
import uuid

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
)
from update_with_ai.parts.agent.lib import session as agent_session
from . import dsh_telemetry


def _compute_dsh_rate_card_cost(
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    model_name: Optional[str] = None,
) -> float:
    """Computes monetary token expenditure based on model rate cards."""
    # Default rates for frontier DeepSeek models (DeepSeek-V4.1-Flash)
    # $0.14 per 1M uncached input tokens, $0.014 per 1M cached input tokens, $0.28 per 1M output tokens
    uncached_rate = 0.00000014
    cached_rate = 0.000000014
    output_rate = 0.00000028

    if model_name:
        m = model_name.lower()
        if any(local_k in m for local_k in ("qwen", "reap", "gemma", "mlx", "local")):
            # Local models run with zero marginal cloud API cost
            return 0.0
        elif "opus" in m:
            uncached_rate = 0.000015
            cached_rate = 0.00000375
            output_rate = 0.000075
        elif "gpt-4o" in m:
            uncached_rate = 0.0000025
            cached_rate = 0.000000625
            output_rate = 0.000010

    return (input_tokens * uncached_rate) + (cached_tokens * cached_rate) + (output_tokens * output_rate)


_notified_desktop_sessions: Set[str] = set()


def _discover_desktop_server(sessions_dir: Optional[str] = None) -> Optional[tuple[int, str, str]]:
    """Discovers active DeepSeek Harness server port and authentication cookie."""
    cookies_path: Optional[str] = None
    if sessions_dir:
        harness_dir = os.path.dirname(sessions_dir)
        desktop_dir = os.path.dirname(harness_dir)
        c_cand = os.path.join(desktop_dir, "Cookies")
        if os.path.isfile(c_cand):
            cookies_path = c_cand
        else:
            return None

    if not cookies_path:
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(home, "Library", "Application Support", "dsh-desktop", "Cookies"),
            os.path.join(home, ".config", "dsh-desktop", "Cookies"),
            os.path.join(home, ".local", "share", "dsh-desktop", "Cookies"),
        ]
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(os.path.join(appdata, "dsh-desktop", "Cookies"))
        dsh_home = os.environ.get("DSH_HOME")
        if dsh_home:
            candidates.insert(0, os.path.join(dsh_home, "Cookies"))
            candidates.insert(1, os.path.join(os.path.dirname(dsh_home), "Cookies"))

        for cand in candidates:
            if os.path.isfile(cand):
                cookies_path = cand
                break

    if not cookies_path or not os.path.isfile(cookies_path):
        return None

    try:
        conn = sqlite3.connect(f"file:{cookies_path}?immutable=1", uri=True)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name, value, source_port FROM cookies WHERE name LIKE 'dsh-auth-%' ORDER BY last_access_utc DESC LIMIT 1"
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return None

        cookie_name, cookie_value, port = row
        actual_port = int(port) if port else 3080
        if not cookie_name or not cookie_value:
            return None
        return (actual_port, str(cookie_name), str(cookie_value))
    except Exception:
        return None


def _call_dsh_rpc(
    port: int,
    cookie_name: str,
    cookie_value: str,
    endpoint: str,
    payload_args: Dict[str, Any],
    timeout: float = 2.0,
) -> Optional[Dict[str, Any]]:
    """Dispatches a JSON-RPC request to the DeepSeek Harness server."""
    envelope = {
        "type": "client-request",
        "rpcId": str(uuid.uuid4()),
        "method": endpoint,
        "payload": {"args": payload_args},
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/{endpoint}",
        data=json.dumps(envelope).encode("utf-8"),
        headers={
            "Cookie": f"{cookie_name}={cookie_value}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    return None


def _notify_desktop_session(
    sessions_dir: str,
    workspace_dir: str,
    session_id: str,
) -> bool:
    """Notifies live DeepSeek Harness Desktop application over local RPC bridge."""
    target_key = f"{workspace_dir}::{session_id}"
    if target_key in _notified_desktop_sessions:
        return True

    server_info = _discover_desktop_server(sessions_dir)
    if not server_info:
        return False
    port, cookie_name, cookie_value = server_info

    try:
        # 1. Ensure workspace exists in DSH Desktop in-memory registry
        ws_res = _call_dsh_rpc(
            port, cookie_name, cookie_value,
            "workspace/create",
            {"request": {"path": os.path.realpath(workspace_dir)}},
            timeout=1.0,
        )
        target_ws_id = None
        if ws_res and isinstance(ws_res, dict):
            val = ws_res.get("result", {}).get("value", {})
            if isinstance(val, dict):
                ws_info = val.get("workspace", {})
                if isinstance(ws_info, dict):
                    target_ws_id = ws_info.get("workspaceId")

        if not target_ws_id:
            return False

        # 2. Attach session to workspace in memory
        sess_res = _call_dsh_rpc(
            port, cookie_name, cookie_value,
            "session/create",
            {"request": {"workspaceId": target_ws_id, "sessionId": session_id}},
            timeout=1.0,
        )
        ok = bool(sess_res and isinstance(sess_res, dict) and sess_res.get("result", {}).get("ok"))
        if ok:
            _notified_desktop_sessions.add(target_key)
        return ok
    except Exception:
        return False


def _sync_desktop_session(
    sessions_dir: Optional[str],
    workspace_dir: str,
    role_name: str,
    dir_scope: str,
    start_time: float,
) -> None:
    """Synchronizes sessions into DeepSeekHarness Desktop App workspace and session storage."""
    if not sessions_dir or not os.path.isdir(sessions_dir):
        return
    try:
        harness_dir = os.path.dirname(sessions_dir)
        ws_file = os.path.join(harness_dir, "storages", "workspace.json")
        projcache_dir = os.path.join(harness_dir, "storages", "session_projcache", "sessions")
        os.makedirs(projcache_dir, exist_ok=True)

        ws_data: Dict[str, Any] = {}
        if os.path.isfile(ws_file):
            with open(ws_file, "r", encoding="utf-8") as f:
                ws_data = json.load(f)

        tables = ws_data.setdefault("tables", {})
        workspaces = tables.setdefault("workspaces", {})
        global_info = ws_data.setdefault("global", {})
        ws_ids = global_info.setdefault("workspaceIds", [])

        # Find or create workspace entry
        target_ws_id = None
        for wid, winfo in workspaces.items():
            if os.path.realpath(winfo.get("path", "")) == os.path.realpath(workspace_dir):
                target_ws_id = wid
                break

        if not target_ws_id:
            target_ws_id = str(uuid.uuid4())
            workspaces[target_ws_id] = {
                "path": os.path.realpath(workspace_dir),
                "title": os.path.basename(workspace_dir),
                "sessionIds": [],
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
            if target_ws_id not in ws_ids:
                ws_ids.append(target_ws_id)

        ws_entry = workspaces[target_ws_id]
        existing_sess = set(ws_entry.setdefault("sessionIds", []))

        # Look up workspace sessions directory
        encoded_ws = "--" + os.path.realpath(workspace_dir).strip("/").replace("/", "-") + "--"
        ws_sess_dir = os.path.join(sessions_dir, encoded_ws)
        if os.path.isdir(ws_sess_dir):
            for entry in os.listdir(ws_sess_dir):
                if entry.startswith("."):
                    continue
                if entry not in existing_sess:
                    ws_entry["sessionIds"].append(entry)
                    existing_sess.add(entry)

                # Set title in projcache
                pc_file = os.path.join(projcache_dir, f"{entry}.json")
                title_val = f"[{role_name.upper()}] {dir_scope} Turn"
                if not os.path.isfile(pc_file):
                    rec = {
                        "version": 7,
                        "record": {
                            "identity": {
                                "formatVersion": 4,
                                "createdAt": int(start_time * 1000),
                                "cwd": workspace_dir,
                                "isSeeded": False,
                                "inheritedEventCount": 0,
                            },
                            "rows": {
                                "title": {"ver": 1, "seq": 1, "val": title_val},
                            },
                        },
                    }
                    with open(pc_file, "w", encoding="utf-8") as pf:
                        json.dump(rec, pf, indent=2)
                else:
                    try:
                        with open(pc_file, "r", encoding="utf-8") as pf:
                            pdata = json.load(pf)
                        rec = pdata.setdefault("record", {})
                        ident = rec.setdefault("identity", {})
                        ident.setdefault("formatVersion", 4)
                        ident.setdefault("cwd", workspace_dir)
                        ident.setdefault("isSeeded", False)
                        ident.setdefault("inheritedEventCount", 0)
                        if "createdAt" not in ident:
                            ident["createdAt"] = int(start_time * 1000)

                        rows = rec.setdefault("rows", {})
                        cur_title = rows.get("title", {}).get("val")
                        if not cur_title or cur_title == "Untitled":
                            rows["title"] = {"ver": 1, "seq": 1, "val": title_val}
                        with open(pc_file, "w", encoding="utf-8") as pf:
                            json.dump(pdata, pf, indent=2)
                    except Exception:
                        pass

                # Live desktop RPC synchronization
                _notify_desktop_session(
                    sessions_dir=sessions_dir,
                    workspace_dir=workspace_dir,
                    session_id=entry,
                )

        with open(ws_file, "w", encoding="utf-8") as f:
            json.dump(ws_data, f, indent=2)
    except Exception:
        pass


def _is_valid_model_config(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    if path.endswith(".toml"):
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore
            with open(path, "rb") as f:
                data = tomllib.load(f)
            return "models" in data or "default" in data
        except Exception:
            return False
    return True


def _find_model_configs_file(workspace_dir: Optional[str] = None) -> Optional[str]:
    candidates = []
    if workspace_dir:
        candidates.append(workspace_dir)
        candidates.append(os.path.dirname(workspace_dir))
        candidates.append(os.path.dirname(os.path.dirname(workspace_dir)))
    candidates.append(os.getcwd())
    cur = os.path.dirname(os.path.abspath(__file__))
    while cur and cur != os.path.dirname(cur):
        candidates.append(cur)
        cur = os.path.dirname(cur)
    for c in candidates:
        for fname in ("model_configs.toml", "cleanroom_models.toml", "cleanroom.toml"):
            p = os.path.join(c, fname)
            if _is_valid_model_config(p):
                return p
    home = os.path.expanduser("~")
    for cand in (
        os.path.join(home, ".config", "cleanroom", "model_configs.toml"),
        os.path.join(home, ".cleanroom", "model_configs.toml"),
        os.path.join(home, ".config", "cleanroom", "models.toml"),
        os.path.join(home, ".cleanroom", "models.toml"),
    ):
        if _is_valid_model_config(cand):
            return cand
    return None


def _resolve_dsh_model_selection(
    model_name: Optional[str],
    workspace_dir: Optional[str] = None,
) -> tuple[str, str, Optional[str]]:
    """Resolves (provider, model, reasoningEffort) for DSH Desktop session/selectModel."""
    cfg_model = None
    cfg_provider = None
    if model_name:
        cfg_file = _find_model_configs_file(workspace_dir)
        if cfg_file:
            try:
                try:
                    import tomllib
                except ImportError:
                    import tomli as tomllib  # type: ignore
                with open(cfg_file, "rb") as f:
                    data = tomllib.load(f)
                models_sec = data.get("models", {})
                clean = model_name.strip()
                for prefix in ("dsh ", "antigravity ", "models."):
                    if clean.startswith(prefix):
                        clean = clean[len(prefix):].strip()
                target_cfg = None
                if isinstance(models_sec, dict):
                    if clean in models_sec:
                        target_cfg = models_sec[clean]
                    else:
                        for k, v in models_sec.items():
                            if isinstance(v, dict) and (v.get("model") == clean or k.lower() == clean.lower()):
                                target_cfg = v
                                break
                if target_cfg and isinstance(target_cfg, dict):
                    cfg_model = target_cfg.get("model") or clean
                    cfg_provider = target_cfg.get("provider")
            except Exception:
                pass

    sel_prov = cfg_provider or "deepseek-official"
    if sel_prov.lower() in ("deepseek", "deepseek-official"):
        sel_prov = "deepseek-official"
    elif sel_prov in ("mlx", "omlx"):
        sel_prov = "omlx"

    sel_model = cfg_model or model_name or "deepseek-flash"
    if sel_prov == "deepseek-official":
        return sel_prov, sel_model, "high"
    return sel_prov, sel_model, None


# Contract: Realizes event stream and session storage archive parsing for DeepSeek Harness in agent_session tier.
class DshTelemetryParser(dsh_telemetry.DshTelemetryParser):
    """Realizes event stream and session storage archive parsing for DeepSeek Harness."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._active_rpc_turns: Dict[str, Dict[str, Any]] = {}

    # Contract: MUST parse token counts from JSON stream events or fallback log text and calculate cost_usd.
    def parse_stream_text(
        self,
        stream_text: str,
        model_name: Optional[str] = None,
    ) -> dsh_telemetry.DshSessionTokenMetrics:
        """Parses stdout JSON event stream or log text for token metrics."""
        input_tokens = 0
        cached_tokens = 0
        output_tokens = 0

        # Try parsing JSON stream lines from `dsh --profile headless --json`
        found_json_usage = False
        for line in stream_text.splitlines():
            line_str = line.strip()
            if not line_str.startswith("{"):
                continue
            try:
                ev = json.loads(line_str)
                # Look for usage object in root, data, or stream chunks
                usage = ev.get("usage")
                if not usage and isinstance(ev.get("data"), dict):
                    usage = ev["data"].get("usage")
                if isinstance(usage, dict):
                    in_t = int(usage.get("inputTokens") or 0)
                    cached_t = int(usage.get("cacheReadTokens") or 0)
                    out_t = int(usage.get("outputTokens") or 0)
                    if in_t > 0 or cached_t > 0 or out_t > 0:
                        input_tokens += in_t
                        cached_tokens += cached_t
                        output_tokens += out_t
                        found_json_usage = True
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

        # Fallback to regex pattern matching if JSON usage objects were absent
        if not found_json_usage:
            for line in stream_text.splitlines():
                m_in = re.search(r"(?:input_tokens|Input tokens|inputTokens):\s*(\d+)", line, re.IGNORECASE)
                if m_in:
                    input_tokens += int(m_in.group(1))

                m_cached = re.search(r"(?:cached_tokens|Cached tokens|cacheReadTokens):\s*(\d+)", line, re.IGNORECASE)
                if m_cached:
                    cached_tokens += int(m_cached.group(1))

                m_out = re.search(r"(?:output_tokens|Output tokens|outputTokens):\s*(\d+)", line, re.IGNORECASE)
                if m_out:
                    output_tokens += int(m_out.group(1))

        total_tokens = input_tokens + cached_tokens + output_tokens
        cost = _compute_dsh_rate_card_cost(input_tokens, cached_tokens, output_tokens, model_name)

        return dsh_telemetry.DshSessionTokenMetrics(
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            model_name=model_name or "",
        )

    # Contract: MUST locate session archives under sessions_dir matching workspace_dir and extract token usage with rate card cost.
    def parse_session_storage(
        self,
        sessions_dir: str,
        workspace_dir: str,
        model_name: Optional[str] = None,
    ) -> dsh_telemetry.DshSessionTokenMetrics:
        """Queries session storage archives and returns token metrics."""
        if not os.path.isdir(sessions_dir):
            return dsh_telemetry.DshSessionTokenMetrics(model_name=model_name or "")

        slug = "-" + workspace_dir.strip("/").replace("/", "-") + "-"
        target_dir = os.path.join(sessions_dir, slug)
        if not os.path.isdir(target_dir):
            target_dir = os.path.join(sessions_dir, f"-{slug}-")
            if not os.path.isdir(target_dir):
                return dsh_telemetry.DshSessionTokenMetrics(model_name=model_name or "")

        # Find newest session subdirectory
        subdirs = [
            os.path.join(target_dir, s)
            for s in os.listdir(target_dir)
            if os.path.isdir(os.path.join(target_dir, s))
        ]
        if not subdirs:
            return dsh_telemetry.DshSessionTokenMetrics(model_name=model_name or "")

        newest_session = max(subdirs, key=os.path.getmtime)
        jsonl_zstd = os.path.join(newest_session, "session.v4.jsonl.zstd")
        jsonl_plain = os.path.join(newest_session, "session.v4.jsonl")

        decompressed_text = ""
        if os.path.isfile(jsonl_zstd):
            try:
                proc = subprocess.run(
                    ["zstd", "-dc", jsonl_zstd],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0:
                    decompressed_text = proc.stdout
            except (OSError, subprocess.SubprocessError):
                pass
        elif os.path.isfile(jsonl_plain):
            try:
                with open(jsonl_plain, "r", encoding="utf-8", errors="replace") as f:
                    decompressed_text = f.read()
            except OSError:
                pass

        if decompressed_text:
            return self.parse_stream_text(decompressed_text, model_name=model_name)

        return dsh_telemetry.DshSessionTokenMetrics(model_name=model_name or "")

    # Contract: MUST update desktop storage files and send RPC notifications when sessions_dir is valid.
    def sync_desktop_session(
        self,
        sessions_dir: Optional[str],
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        start_time: float,
    ) -> None:
        """Synchronizes sessions into DeepSeekHarness Desktop App storage."""
        _sync_desktop_session(
            sessions_dir=sessions_dir,
            workspace_dir=workspace_dir,
            role_name=role_name,
            dir_scope=dir_scope,
            start_time=start_time,
        )

    # Contract: MUST probe application cookie storage and verify reachability over the local RPC bridge.
    def is_desktop_server_available(
        self,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Evaluates whether an active DeepSeek Harness Desktop application or background server is reachable."""
        server_info = _discover_desktop_server(sessions_dir)
        if not server_info:
            return False
        port, cookie_name, cookie_value = server_info
        res = _call_dsh_rpc(port, cookie_name, cookie_value, "session/list", {"_request": {}}, timeout=1.5)
        if res is not None and isinstance(res, dict):
            if res.get("result", {}).get("ok") is True:
                return True
        res_init = _call_dsh_rpc(port, cookie_name, cookie_value, "initialize", {}, timeout=1.0)
        return res_init is not None and res_init.get("result", {}).get("ok") is True

    # Contract: MUST ensure workspace registration and create or resume session on the server.
    # MUST enqueue the prompt task and return a task handle, or None if unreachable.
    def dispatch_round_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Optional[str]:
        """Dispatches a role round over the local JSON-RPC bridge to the central DeepSeek Harness server."""
        server_info = _discover_desktop_server(sessions_dir)
        if not server_info:
            return None
        port, cookie_name, cookie_value = server_info

        real_ws = os.path.realpath(workspace_dir)

        # 1. Discover existing sessions for this workspace in DSH Desktop
        list_res = _call_dsh_rpc(port, cookie_name, cookie_value, "session/list", {"_request": {}}, timeout=2.0)
        actual_session_id: Optional[str] = None
        items: list[Dict[str, Any]] = []
        if list_res and isinstance(list_res, dict):
            items = list_res.get("result", {}).get("value", {}).get("items", [])

            def _is_usable(it: Dict[str, Any]) -> bool:
                # Sessions locked in minimal preset lack file mutation tools
                preset = it.get("projections", {}).get("values", {}).get("agentPreset")
                return preset != "minimal"

            # If session_id was passed, check if it matches an existing usable session
            if session_id:
                for it in items:
                    if it.get("sessionId") == session_id and _is_usable(it):
                        actual_session_id = session_id
                        break

        # 2. If no existing session found, ensure workspace registration and create one
        if not actual_session_id:
            # Clean up stale sessions matching this cwd in DSH Desktop before creating a new one
            for it in items:
                if it.get("cwd") == real_ws:
                    stale_sid = it.get("sessionId")
                    if stale_sid:
                        _call_dsh_rpc(
                            port, cookie_name, cookie_value,
                            "session/delete",
                            {"request": {"sessionId": stale_sid}},
                            timeout=2.0,
                        )
            _call_dsh_rpc(
                port, cookie_name, cookie_value,
                "workspace/create",
                {"request": {"path": real_ws}},
                timeout=2.0,
            )
            create_args: Dict[str, Any] = {"request": {"cwd": real_ws, "agentPreset": "standard"}}
            if session_id:
                create_args["request"]["sessionId"] = session_id
            create_res = _call_dsh_rpc(
                port, cookie_name, cookie_value,
                "session/create",
                create_args,
                timeout=2.0,
            )
            if create_res and isinstance(create_res, dict):
                val = create_res.get("result", {}).get("value", {})
                if isinstance(val, dict):
                    actual_session_id = val.get("sessionId")
                if not actual_session_id:
                    actual_session_id = create_res.get("result", {}).get("sessionId")
            if not actual_session_id:
                actual_session_id = session_id or f"dsh-sess-{role_name}-{int(time.time() * 1000)}"

        # Explicitly configure session model selection on DSH Desktop
        target_model = model_name
        if not target_model and os.path.isdir(workspace_dir):
            role_json_path = os.path.join(workspace_dir, ".cleanroom_role.json")
            if os.path.isfile(role_json_path):
                try:
                    with open(role_json_path, "r", encoding="utf-8") as rf:
                        r_data = json.load(rf)
                        target_model = r_data.get("model")
                except Exception:
                    pass

        if actual_session_id and target_model:
            sel_prov, sel_model, sel_effort = _resolve_dsh_model_selection(target_model, workspace_dir)
            sel_req: Dict[str, Any] = {
                "request": {
                    "sessionId": actual_session_id,
                    "provider": sel_prov,
                    "model": sel_model,
                }
            }
            if sel_effort:
                sel_req["request"]["reasoningEffort"] = sel_effort
            _call_dsh_rpc(
                port, cookie_name, cookie_value,
                "session/selectModel",
                sel_req,
                timeout=2.0,
            )

        # 3. Dispatch prompt over session/prompt
        request_id = str(uuid.uuid4())
        prompt_args: Dict[str, Any] = {
            "request": {
                "requestId": request_id,
                "sessionId": actual_session_id,
                "mode": "queue",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_text,
                    }
                ],
            }
        }

        prompt_res = _call_dsh_rpc(
            port, cookie_name, cookie_value,
            "session/prompt",
            prompt_args,
            timeout=3.0,
        )
        if prompt_res is None or not isinstance(prompt_res, dict):
            # Backward compatibility with mock handler accepting flat prompt args
            fallback_args: Dict[str, Any] = {
                "sessionId": actual_session_id,
                "prompt": prompt_text,
            }
            if model_name:
                fallback_args["config"] = {"model": model_name}
            prompt_res = _call_dsh_rpc(
                port, cookie_name, cookie_value,
                "session/prompt",
                fallback_args,
                timeout=2.0,
            )
            if prompt_res is None or not isinstance(prompt_res, dict):
                return None

        res_data = prompt_res.get("result", {})
        if isinstance(res_data, dict) and not res_data.get("ok", True):
            return None

        task_handle = f"dsh_rpc::{actual_session_id}::{uuid.uuid4().hex[:8]}"
        self._active_rpc_turns[task_handle] = {
            "session_id": actual_session_id,
            "request_id": request_id,
            "workspace_dir": workspace_dir,
            "role_name": role_name,
            "model_name": model_name,
            "start_time": time.time(),
            "port": port,
            "cookie_name": cookie_name,
            "cookie_value": cookie_value,
        }
        return task_handle

    # Backward compatibility alias
    dispatch_turn_rpc = dispatch_round_rpc

    # Contract: MUST query round execution status from the central server and return DshRpcRoundStatus.
    def poll_round_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> dsh_telemetry.DshRpcRoundStatus:
        """Polls active round status over the local JSON-RPC bridge."""
        turn_info = self._active_rpc_turns.get(task_handle)
        session_id = ""
        port = None
        cookie_name = ""
        cookie_value = ""
        workspace_dir = ""
        model_name = None

        if turn_info:
            session_id = turn_info["session_id"]
            port = turn_info["port"]
            cookie_name = turn_info["cookie_name"]
            cookie_value = turn_info["cookie_value"]
            workspace_dir = turn_info["workspace_dir"]
            model_name = turn_info["model_name"]
        elif task_handle.startswith("dsh_rpc::"):
            parts = task_handle.split("::")
            if len(parts) >= 2:
                session_id = parts[1]

        if not session_id:
            return dsh_telemetry.DshRpcRoundStatus(
                is_active=False,
                is_completed=True,
                error=f"Unknown task handle '{task_handle}'",
            )

        if port is None:
            server_info = _discover_desktop_server(sessions_dir)
            if server_info:
                port, cookie_name, cookie_value = server_info

        if port is None:
            return dsh_telemetry.DshRpcRoundStatus(
                is_active=False,
                is_completed=True,
                error="DeepSeek Harness server is unreachable",
            )

        # 1. Query session/list
        list_res = _call_dsh_rpc(
            port, cookie_name, cookie_value,
            "session/list",
            {"_request": {}},
            timeout=2.0,
        )
        if list_res and isinstance(list_res, dict):
            items = list_res.get("result", {}).get("value", {}).get("items", [])
            for it in items:
                if it.get("sessionId") == session_id:
                    running = it.get("running", False)
                    projections = it.get("projections", {}).get("values", {})
                    token_usage = projections.get("tokenUsage", {})
                    in_t = int(token_usage.get("uncachedInputTokens") or 0)
                    c_t = int(token_usage.get("cacheReadTokens") or 0)
                    out_t = int(token_usage.get("outputTokens") or 0)
                    metrics = None
                    if in_t or c_t or out_t:
                        metrics = dsh_telemetry.DshSessionTokenMetrics(
                            input_tokens=in_t,
                            cached_tokens=c_t,
                            output_tokens=out_t,
                            total_tokens=in_t + c_t + out_t,
                            cost_usd=_compute_dsh_rate_card_cost(in_t, c_t, out_t, model_name),
                            model_name=model_name or "",
                        )

                    if running:
                        return dsh_telemetry.DshRpcRoundStatus(
                            is_active=True,
                            is_completed=False,
                            metrics=metrics,
                        )
                    else:
                        if not metrics and sessions_dir and workspace_dir:
                            metrics = self.parse_session_storage(sessions_dir, workspace_dir, model_name)
                        return dsh_telemetry.DshRpcRoundStatus(
                            is_active=False,
                            is_completed=True,
                            metrics=metrics,
                        )

        # 2. Fallback to session/status for backward compatibility with mock servers
        status_res = _call_dsh_rpc(
            port, cookie_name, cookie_value,
            "session/status",
            {"sessionId": session_id},
            timeout=2.0,
        )
        if status_res and isinstance(status_res, dict):
            res_obj = status_res.get("result", {})
            if isinstance(res_obj, dict):
                st = res_obj.get("status")
                err = res_obj.get("error")
                usage = res_obj.get("usage")
                metrics = None
                if isinstance(usage, dict):
                    in_t = int(usage.get("inputTokens") or 0)
                    c_t = int(usage.get("cacheReadTokens") or 0)
                    out_t = int(usage.get("outputTokens") or 0)
                    metrics = dsh_telemetry.DshSessionTokenMetrics(
                        input_tokens=in_t,
                        cached_tokens=c_t,
                        output_tokens=out_t,
                        total_tokens=in_t + c_t + out_t,
                        cost_usd=_compute_dsh_rate_card_cost(in_t, c_t, out_t, model_name),
                        model_name=model_name or "",
                    )
                if st in ("running", "active", "busy", "streaming"):
                    return dsh_telemetry.DshRpcRoundStatus(
                        is_active=True,
                        is_completed=False,
                        metrics=metrics,
                    )
                elif st in ("completed", "idle", "finished", "success"):
                    if not metrics and sessions_dir and workspace_dir:
                        metrics = self.parse_session_storage(sessions_dir, workspace_dir, model_name)
                    return dsh_telemetry.DshRpcRoundStatus(
                        is_active=False,
                        is_completed=True,
                        metrics=metrics,
                    )
                elif st in ("error", "failed"):
                    return dsh_telemetry.DshRpcRoundStatus(
                        is_active=False,
                        is_completed=True,
                        error=str(err) if err else "Execution error",
                        metrics=metrics,
                    )

        # 3. Fallback check on session lock
        if sessions_dir and workspace_dir:
            encoded_ws = "--" + os.path.realpath(workspace_dir).strip("/").replace("/", "-") + "--"
            lock_path = os.path.join(sessions_dir, encoded_ws, session_id, "session.lock")
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, "r+") as lf:
                        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(lf, fcntl.LOCK_UN)
                    metrics = self.parse_session_storage(sessions_dir, workspace_dir, model_name)
                    return dsh_telemetry.DshRpcRoundStatus(
                        is_active=False,
                        is_completed=True,
                        metrics=metrics,
                    )
                except (BlockingIOError, OSError):
                    return dsh_telemetry.DshRpcRoundStatus(
                        is_active=True,
                        is_completed=False,
                    )

        metrics = None
        if sessions_dir and workspace_dir:
            metrics = self.parse_session_storage(sessions_dir, workspace_dir, model_name)
        return dsh_telemetry.DshRpcRoundStatus(
            is_active=False,
            is_completed=True,
            metrics=metrics,
        )

    # Backward compatibility alias
    poll_turn_rpc = poll_round_rpc
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:55:00Z
# CHANGE: Author dsh_telemetry_impl implementation
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DshTelemetryParser,
        keys=[DshTelemetryParser, dsh_telemetry.DshTelemetryParser],
        tier=DshTelemetryParser.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
