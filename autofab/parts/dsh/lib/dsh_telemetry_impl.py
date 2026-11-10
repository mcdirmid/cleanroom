"""Low-level implementation for dsh_telemetry_impl."""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, Optional, Set
import urllib.request
import uuid

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
)

try:
    from support.lib import app_info
except Exception:
    import app_info  # type: ignore
from autofab.parts.agent.lib import session as agent_session
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

    return (
        (input_tokens * uncached_rate)
        + (cached_tokens * cached_rate)
        + (output_tokens * output_rate)
    )


_notified_desktop_sessions: Set[str] = set()


def _resolve_default_sessions_dir() -> str:
    """Discovers DeepSeek Harness sessions directory across environment and OS candidates."""
    if "DSH_SESSIONS_DIR" in os.environ and os.environ["DSH_SESSIONS_DIR"].strip():
        return os.environ["DSH_SESSIONS_DIR"].strip()

    home = os.path.expanduser("~")
    dsh_web_cand = os.path.join(home, ".dsh", "sessions")
    if os.environ.get("AUTOFAB_DSH_WEB") == "1":
        return dsh_web_cand

    dsh_home = os.environ.get("DSH_HOME")
    if dsh_home and dsh_home.strip():
        h_cand = os.path.join(dsh_home.strip(), "harness", "sessions")
        if os.path.isdir(h_cand):
            return h_cand
        s_cand = os.path.join(dsh_home.strip(), "sessions")
        if os.path.isdir(s_cand):
            return s_cand
        return h_cand

    candidates = [
        os.path.join(
            home, "Library", "Application Support", "dsh-desktop", "harness", "sessions"
        ),
        os.path.join(home, ".config", "dsh-desktop", "harness", "sessions"),
        os.path.join(home, ".local", "share", "dsh-desktop", "harness", "sessions"),
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(os.path.join(appdata, "dsh-desktop", "harness", "sessions"))

    for cand in candidates:
        if os.path.isdir(cand):
            return cand

    # Platform default fallback
    if sys.platform == "darwin":
        return os.path.join(
            home, "Library", "Application Support", "dsh-desktop", "harness", "sessions"
        )
    elif sys.platform == "win32":
        return os.path.join(
            os.environ.get("APPDATA", home), "dsh-desktop", "harness", "sessions"
        )
    return os.path.join(home, ".config", "dsh-desktop", "harness", "sessions")


def _discover_desktop_server(
    sessions_dir: Optional[str] = None,
) -> Optional[tuple[int, str, str]]:
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
        if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
            "AUTOFAB_ALLOW_TEST_BRIDGE"
        ):
            return None
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(
                home, "Library", "Application Support", "dsh-desktop", "Cookies"
            ),
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


def _discover_web_bridge() -> Optional[Dict[str, Any]]:
    """Discovers active DeepSeek Harness Web loopback bridge endpoint configuration."""
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
        "AUTOFAB_ALLOW_TEST_BRIDGE"
    ):
        return None
    p = os.path.expanduser("~/.dsh/bridge/endpoint.json")
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "url" in data and "token" in data:
                return data
        except Exception:
            return None
    return None


def _call_web_bridge(
    endpoint_data: Dict[str, Any],
    tool_name: str,
    arguments: Dict[str, Any],
    timeout: float = 10.0,
) -> Optional[Dict[str, Any]]:
    """Dispatches a tool call request to the DeepSeek Harness Web loopback bridge."""
    url = endpoint_data.get("url")
    if not url:
        return None
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
        "id": int(time.time() * 1000) % 1000000,
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("result")
    except Exception:
        return None
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
    role_name: Optional[str] = None,
    dir_scope: Optional[str] = None,
) -> bool:
    """Notifies live DeepSeek Harness Desktop application over local RPC bridge."""
    target_key = f"{workspace_dir}::{session_id}::{role_name}::{dir_scope}"
    if target_key in _notified_desktop_sessions:
        return True

    server_info = _discover_desktop_server(sessions_dir)
    if not server_info:
        return False
    port, cookie_name, cookie_value = server_info

    try:
        clean_scope = dir_scope.strip("/").strip() if dir_scope else ""
        display_scope = os.path.basename(clean_scope) if clean_scope else ""
        clean_role = role_name.strip() if role_name else ""
        session_title = (
            f"[{display_scope}] {clean_role}"
            if display_scope and clean_role
            else (clean_role or display_scope or "autofab")
        )

        # 1. Adopt session directly in role workspace directory
        sess_res = _call_dsh_rpc(
            port,
            cookie_name,
            cookie_value,
            "session/create",
            {
                "request": {
                    "cwd": os.path.realpath(workspace_dir),
                    "sessionId": session_id,
                    "agentPreset": "standard",
                }
            },
            timeout=1.0,
        )
        ok = bool(
            sess_res
            and isinstance(sess_res, dict)
            and sess_res.get("result", {}).get("ok")
        )

        if ok and session_title:
            _call_dsh_rpc(
                port,
                cookie_name,
                cookie_value,
                "session/rename",
                {"request": {"sessionId": session_id, "title": session_title}},
                timeout=1.0,
            )

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
    """Synchronizes sessions into DeepSeekHarness Desktop App session storage."""
    if not sessions_dir or not os.path.isdir(sessions_dir):
        return
    try:
        harness_dir = os.path.dirname(sessions_dir)
        projcache_dir = os.path.join(
            harness_dir, "storages", "session_projcache", "sessions"
        )
        os.makedirs(projcache_dir, exist_ok=True)

        clean_scope = dir_scope.strip("/").strip() if dir_scope else ""
        display_scope = os.path.basename(clean_scope) if clean_scope else ""
        clean_role = role_name.strip() if role_name else ""
        title_val = (
            f"[{display_scope}] {clean_role}"
            if display_scope and clean_role
            else (clean_role or display_scope or "autofab")
        )

        # Look up workspace sessions directory
        real_ws_path = os.path.realpath(workspace_dir).strip("/")
        slug1 = "--" + real_ws_path.replace("/", "-") + "--"
        slug2 = "-" + real_ws_path.replace("/", "-") + "-"
        ws_sess_dir = os.path.join(sessions_dir, slug1)
        if not os.path.isdir(ws_sess_dir):
            ws_sess_dir = os.path.join(sessions_dir, slug2)
        if os.path.isdir(ws_sess_dir):
            for entry in os.listdir(ws_sess_dir):
                if entry.startswith("."):
                    continue

                # Set title in projcache to scoped role name
                pc_file = os.path.join(projcache_dir, f"{entry}.json")
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
                    try:
                        with open(pc_file, "w", encoding="utf-8") as pf:
                            json.dump(rec, pf, indent=2)
                    except Exception:
                        pass
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
                        cur_title_obj = rows.get("title", {})
                        cur_seq = (
                            cur_title_obj.get("seq", 1) + 1
                            if isinstance(cur_title_obj, dict)
                            else 1
                        )
                        rows["title"] = {"ver": 1, "seq": cur_seq, "val": title_val}
                        with open(pc_file, "w", encoding="utf-8") as pf:
                            json.dump(pdata, pf, indent=2)
                    except Exception:
                        pass

                # Live desktop RPC synchronization
                _notify_desktop_session(
                    sessions_dir=sessions_dir,
                    workspace_dir=workspace_dir,
                    session_id=entry,
                    role_name=role_name,
                    dir_scope=dir_scope,
                )
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
    cfg_names = (
        "model_configs.toml",
        f"{app_info.APP_NAME}_models.toml",
    ) + app_info.get_config_filenames()
    for c in candidates:
        for fname in cfg_names:
            p = os.path.join(c, fname)
            if _is_valid_model_config(p):
                return p
    user_model_cfg = getattr(app_info, "get_user_model_config_file", lambda: "")()
    if user_model_cfg and _is_valid_model_config(user_model_cfg):
        return user_model_cfg
    cands_fn = getattr(app_info, "get_candidate_user_model_config_files", None)
    if cands_fn:
        for cand in cands_fn():
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
                        clean = clean[len(prefix) :].strip()
                target_cfg = None
                if isinstance(models_sec, dict):
                    if clean in models_sec:
                        target_cfg = models_sec[clean]
                    else:
                        for k, v in models_sec.items():
                            if isinstance(v, dict) and (
                                v.get("model") == clean or k.lower() == clean.lower()
                            ):
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
                m_in = re.search(
                    r"(?:input_tokens|Input tokens|inputTokens):\s*(\d+)",
                    line,
                    re.IGNORECASE,
                )
                if m_in:
                    input_tokens += int(m_in.group(1))

                m_cached = re.search(
                    r"(?:cached_tokens|Cached tokens|cacheReadTokens):\s*(\d+)",
                    line,
                    re.IGNORECASE,
                )
                if m_cached:
                    cached_tokens += int(m_cached.group(1))

                m_out = re.search(
                    r"(?:output_tokens|Output tokens|outputTokens):\s*(\d+)",
                    line,
                    re.IGNORECASE,
                )
                if m_out:
                    output_tokens += int(m_out.group(1))

        total_tokens = input_tokens + cached_tokens + output_tokens
        cost = _compute_dsh_rate_card_cost(
            input_tokens, cached_tokens, output_tokens, model_name
        )

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
        dsh_web_dir = os.path.expanduser("~/.dsh/sessions")
        if os.environ.get("AUTOFAB_DSH_WEB") == "1" and (
            not sessions_dir
            or os.path.abspath(sessions_dir) == os.path.abspath(dsh_web_dir)
        ):
            bridge = _discover_web_bridge()
            if bridge:
                res = _call_web_bridge(bridge, "dsh_list_workers", {}, timeout=2.0)
                if res is not None:
                    return True
        server_info = _discover_desktop_server(sessions_dir)
        if not server_info:
            return False
        port, cookie_name, cookie_value = server_info
        res = _call_dsh_rpc(
            port,
            cookie_name,
            cookie_value,
            "session/list",
            {"_request": {}},
            timeout=1.5,
        )
        if res is not None and isinstance(res, dict):
            if res.get("result", {}).get("ok") is True:
                return True
        res_init = _call_dsh_rpc(
            port, cookie_name, cookie_value, "initialize", {}, timeout=1.0
        )
        return res_init is not None and res_init.get("result", {}).get("ok") is True

    # Contract: MUST ensure workspace registration and create or resume session on the server.
    # MUST set workspace title to the scope and session title to the role name.
    # MUST enqueue the prompt task and return a task handle, or None if unreachable.
    def dispatch_round_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Optional[str]:
        """Dispatches a role round over the local JSON-RPC bridge to the central DeepSeek Harness server."""
        dsh_web_dir = os.path.expanduser("~/.dsh/sessions")
        if os.environ.get("AUTOFAB_DSH_WEB") == "1" and (
            not sessions_dir
            or os.path.abspath(sessions_dir) == os.path.abspath(dsh_web_dir)
        ):
            bridge = _discover_web_bridge()
            if not bridge:
                return None
            real_ws = os.path.realpath(workspace_dir)
            clean_scope = re.sub(
                r"[^a-zA-Z0-9_]", "_", dir_scope.strip("/").strip() if dir_scope else ""
            )[:16]
            clean_role = re.sub(
                r"[^a-zA-Z0-9_]", "_", role_name.strip() if role_name else ""
            )[:16]
            entropy = uuid.uuid4().hex[:8]
            task_name = f"dsh_{clean_scope}_{clean_role}_{int(time.time() * 1000)}_{entropy}".strip(
                "_"
            )

            saved_worker: Optional[str] = None
            if session_id:
                saved_worker = (
                    session_id[len("worker_") :]
                    if session_id.startswith("worker_")
                    else session_id
                )

            if saved_worker:
                followup_args: Dict[str, Any] = {
                    "worker": saved_worker,
                    "message": prompt_text,
                }
                if model_name:
                    sel_prov, sel_model, sel_effort = _resolve_dsh_model_selection(
                        model_name, workspace_dir
                    )
                    followup_args["model"] = f"{sel_prov}/{sel_model}"
                    if sel_effort:
                        followup_args["reasoningEffort"] = sel_effort
                res = _call_web_bridge(
                    bridge, "dsh_followup", followup_args, timeout=30.0
                )
                if res and not res.get("isError"):
                    if session_id:
                        display_scope = (
                            os.path.basename(clean_scope) if clean_scope else ""
                        )
                        active_label = (
                            f"[{display_scope}] {role_name}"
                            if display_scope
                            else role_name
                        )
                        try:
                            self.rename_session(
                                session_id, active_label, sessions_dir=sessions_dir
                            )
                        except Exception:
                            pass
                    task_handle = f"dsh_rpc_web::{session_id}::{saved_worker}"
                    self._active_rpc_turns[task_handle] = {
                        "session_id": session_id,
                        "request_id": saved_worker,
                        "workspace_dir": workspace_dir,
                        "role_name": role_name,
                        "model_name": model_name,
                        "dir_scope": dir_scope,
                        "start_time": time.time(),
                        "port": bridge.get("port", 47821),
                        "cookie_name": "",
                        "cookie_value": "",
                    }
                    return task_handle

            display_scope = os.path.basename(clean_scope) if clean_scope else ""
            spawn_args: Dict[str, Any] = {
                "task_name": task_name,
                "message": prompt_text,
                "cwd": real_ws,
                "label": f"[{display_scope}] {role_name}" if display_scope else role_name,
            }
            if model_name:
                sel_prov, sel_model, sel_effort = _resolve_dsh_model_selection(
                    model_name, workspace_dir
                )
                spawn_args["model"] = f"{sel_prov}/{sel_model}"
                if sel_effort:
                    spawn_args["reasoningEffort"] = sel_effort

            res = _call_web_bridge(bridge, "dsh_spawn", spawn_args, timeout=30.0)
            if res and not res.get("isError"):
                actual_sid = task_name
                content_list = res.get("content", [])
                if content_list and isinstance(content_list, list):
                    txt = content_list[0].get("text", "")
                    if "sessionId" in txt:
                        try:
                            parsed_data = json.loads(txt)
                            actual_sid = parsed_data.get("sessionId", task_name)
                        except Exception:
                            pass
                task_handle = f"dsh_rpc_web::{actual_sid}::{task_name}"
                self._active_rpc_turns[task_handle] = {
                    "session_id": actual_sid,
                    "request_id": task_name,
                    "workspace_dir": workspace_dir,
                    "role_name": role_name,
                    "model_name": model_name,
                    "dir_scope": dir_scope,
                    "start_time": time.time(),
                    "port": bridge.get("port", 47821),
                    "cookie_name": "",
                    "cookie_value": "",
                }
                return task_handle
            if res and res.get("isError"):
                content_list = res.get("content", [])
                err_text = ""
                if content_list and isinstance(content_list, list):
                    err_text = content_list[0].get("text", "")
                sys.stderr.write(
                    f"[DSH_WEB] dsh_spawn failed for {task_name}: {err_text}\n"
                )
            return None

        server_info = _discover_desktop_server(sessions_dir)
        if not server_info:
            return None
        port, cookie_name, cookie_value = server_info

        real_ws = os.path.realpath(workspace_dir)

        # 1. Discover existing sessions for this workspace in DSH Desktop
        list_res = _call_dsh_rpc(
            port,
            cookie_name,
            cookie_value,
            "session/list",
            {"_request": {}},
            timeout=2.0,
        )
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

        # 2. Format conversation title capturing scope and role
        clean_scope = dir_scope.strip("/").strip() if dir_scope else ""
        display_scope = os.path.basename(clean_scope) if clean_scope else ""
        clean_role = role_name.strip() if role_name else ""
        session_title = (
            f"[{display_scope}] {clean_role}"
            if display_scope and clean_role
            else (clean_role or display_scope or "autofab")
        )

        # 3. If no existing session found, create one directly in role workspace cwd
        if not actual_session_id:
            # Clean up stale sessions matching this cwd in DSH Desktop before creating a new one
            for it in items:
                if it.get("cwd") == real_ws:
                    stale_sid = it.get("sessionId")
                    if stale_sid:
                        _call_dsh_rpc(
                            port,
                            cookie_name,
                            cookie_value,
                            "session/delete",
                            {"request": {"sessionId": stale_sid}},
                            timeout=2.0,
                        )
            create_args: Dict[str, Any] = {
                "request": {
                    "cwd": real_ws,
                    "agentPreset": "standard",
                }
            }
            if session_id:
                create_args["request"]["sessionId"] = session_id
            create_res = _call_dsh_rpc(
                port,
                cookie_name,
                cookie_value,
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
                actual_session_id = (
                    session_id or f"dsh-sess-{role_name}-{int(time.time() * 1000)}"
                )
        else:
            # Resuming an existing session: ensure it is adopted on the server
            _call_dsh_rpc(
                port,
                cookie_name,
                cookie_value,
                "session/create",
                {
                    "request": {
                        "cwd": real_ws,
                        "sessionId": actual_session_id,
                        "agentPreset": "standard",
                    }
                },
                timeout=2.0,
            )

        # 4. Set conversation name to scope and role
        if actual_session_id and session_title:
            _call_dsh_rpc(
                port,
                cookie_name,
                cookie_value,
                "session/rename",
                {"request": {"sessionId": actual_session_id, "title": session_title}},
                timeout=2.0,
            )

        # 5. Explicitly configure session model selection on DSH Desktop
        target_model = model_name
        if not target_model and os.path.isdir(workspace_dir):
            for desc_name in app_info.get_role_descriptors():
                role_json_path = os.path.join(workspace_dir, desc_name)
                if os.path.isfile(role_json_path):
                    try:
                        with open(role_json_path, "r", encoding="utf-8") as rf:
                            r_data = json.load(rf)
                            target_model = r_data.get("model")
                            if target_model:
                                break
                    except Exception:
                        pass

        if actual_session_id and target_model:
            sel_prov, sel_model, sel_effort = _resolve_dsh_model_selection(
                target_model, workspace_dir
            )
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
                port,
                cookie_name,
                cookie_value,
                "session/selectModel",
                sel_req,
                timeout=2.0,
            )

        # 6. Dispatch prompt over session/prompt
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
            port,
            cookie_name,
            cookie_value,
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
                port,
                cookie_name,
                cookie_value,
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
            "dir_scope": dir_scope,
            "start_time": time.time(),
            "port": port,
            "cookie_name": cookie_name,
            "cookie_value": cookie_value,
        }
        return task_handle

    # Backward compatibility alias
    def dispatch_turn_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Optional[str]:
        return self.dispatch_round_rpc(
            workspace_dir=workspace_dir,
            role_name=role_name,
            prompt_text=prompt_text,
            session_id=session_id,
            sessions_dir=sessions_dir,
            model_name=model_name,
            dir_scope=dir_scope,
        )

    # Contract: MUST query round execution status from the central server and return DshRpcRoundStatus.
    def poll_round_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> dsh_telemetry.DshRpcRoundStatus:
        """Polls active round status over the local JSON-RPC bridge."""
        if task_handle.startswith("dsh_rpc_web::"):
            parts = task_handle.split("::")
            actual_sid = parts[1] if len(parts) >= 2 else ""
            task_name = parts[2] if len(parts) >= 3 else actual_sid
            bridge = _discover_web_bridge()
            if not bridge:
                return dsh_telemetry.DshRpcRoundStatus(
                    is_active=False, is_completed=True, error="Web bridge unreachable"
                )

            res = _call_web_bridge(bridge, "dsh_list_workers", {}, timeout=2.0)
            is_completed = False
            is_error = False
            worker_found = False
            if res:
                content_list = res.get("content", [])
                if content_list and isinstance(content_list, list):
                    txt = content_list[0].get("text", "")
                    try:
                        workers = json.loads(txt)
                        if isinstance(workers, list):
                            for w in workers:
                                if isinstance(w, dict) and (
                                    w.get("task_name") == task_name
                                    or (actual_sid and w.get("sessionId") == actual_sid)
                                    or (task_name and w.get("sessionId") == task_name)
                                ):
                                    worker_found = True
                                    status = w.get("status")
                                    if isinstance(status, dict):
                                        if "completed" in status:
                                            is_completed = True
                                        elif "errored" in status or "error" in status:
                                            is_completed = True
                                            is_error = True
                                    elif status in (
                                        "completed",
                                        "done",
                                        "success",
                                        "closed",
                                    ):
                                        is_completed = True
                                    elif status in ("error", "failed", "aborted"):
                                        is_completed = True
                                        is_error = True
                                    elif status == "running":
                                        is_completed = False
                                    break
                    except Exception:
                        pass

            round_info = self._active_rpc_turns.get(task_handle)
            start_time = round_info.get("start_time", 0.0) if round_info else 0.0
            elapsed = (time.time() - start_time) if start_time > 0 else 999.0
            if not worker_found and res and elapsed > 15.0:
                is_completed = True
                is_error = True

            if is_completed:
                _call_web_bridge(
                    bridge, "dsh_close", {"worker": task_name}, timeout=2.0
                )

            w_dir = round_info.get("workspace_dir", "") if round_info else ""
            m_name = round_info.get("model_name") if round_info else None
            actual_sessions_dir = sessions_dir or _resolve_default_sessions_dir()
            metrics = None
            if w_dir:
                metrics = self.parse_session_storage(
                    actual_sessions_dir, w_dir, model_name=m_name
                )

            return dsh_telemetry.DshRpcRoundStatus(
                is_active=not is_completed,
                is_completed=is_completed,
                metrics=metrics,
                error="Worker missing from DSH Web registry (server restarted or connection dropped)"
                if (not worker_found and is_error)
                else None,
            )

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
            port,
            cookie_name,
            cookie_value,
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
                            cost_usd=_compute_dsh_rate_card_cost(
                                in_t, c_t, out_t, model_name
                            ),
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
                            metrics = self.parse_session_storage(
                                sessions_dir, workspace_dir, model_name
                            )
                        return dsh_telemetry.DshRpcRoundStatus(
                            is_active=False,
                            is_completed=True,
                            metrics=metrics,
                        )

        # 2. Fallback to session/status for backward compatibility with mock servers
        status_res = _call_dsh_rpc(
            port,
            cookie_name,
            cookie_value,
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
                        cost_usd=_compute_dsh_rate_card_cost(
                            in_t, c_t, out_t, model_name
                        ),
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
                        metrics = self.parse_session_storage(
                            sessions_dir, workspace_dir, model_name
                        )
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
            encoded_ws = (
                "--"
                + os.path.realpath(workspace_dir).strip("/").replace("/", "-")
                + "--"
            )
            lock_path = os.path.join(
                sessions_dir, encoded_ws, session_id, "session.lock"
            )
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, "r+") as lf:
                        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(lf, fcntl.LOCK_UN)
                    metrics = self.parse_session_storage(
                        sessions_dir, workspace_dir, model_name
                    )
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
            metrics = self.parse_session_storage(
                sessions_dir, workspace_dir, model_name
            )
        return dsh_telemetry.DshRpcRoundStatus(
            is_active=False,
            is_completed=True,
            metrics=metrics,
        )

    # Backward compatibility alias
    poll_turn_rpc = poll_round_rpc

    # Contract: MUST rename a session on DeepSeek Harness Web bridge or Desktop RPC.
    def rename_session(
        self,
        session_id: str,
        title: str,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Renames a session on DeepSeek Harness Web bridge or Desktop RPC."""
        bridge = _discover_web_bridge()
        if bridge:
            res = _call_web_bridge(
                bridge,
                "dsh_rename_session",
                {"sessionId": session_id, "title": title},
                timeout=5.0,
            )
            if res and not res.get("isError"):
                return True

        server_info = _discover_desktop_server(sessions_dir)
        if server_info:
            port, cookie_name, cookie_value = server_info
            res = _call_dsh_rpc(
                port,
                cookie_name,
                cookie_value,
                "session/rename",
                {"request": {"sessionId": session_id, "title": title}},
                timeout=2.0,
            )
            if (
                res
                and isinstance(res, dict)
                and res.get("result", {}).get("ok") is not False
            ):
                return True

        actual_sessions_dir = sessions_dir or _resolve_default_sessions_dir()
        if actual_sessions_dir and os.path.isdir(actual_sessions_dir):
            try:
                for ws_entry in os.listdir(actual_sessions_dir):
                    hdr_file = os.path.join(
                        actual_sessions_dir, ws_entry, session_id, "header.json"
                    )
                    if os.path.isfile(hdr_file):
                        with open(hdr_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        data["title"] = title
                        with open(hdr_file, "w", encoding="utf-8") as f:
                            json.dump(data, f)
                        return True
            except Exception:
                pass
        return False

    # Contract: MUST delete a session from DeepSeek Harness Web bridge or Desktop RPC.
    def delete_session(
        self,
        session_id: str,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Deletes a session from DeepSeek Harness Web bridge or Desktop RPC."""
        deleted = False
        bridge = _discover_web_bridge()
        if bridge:
            res = _call_web_bridge(
                bridge, "dsh_delete_session", {"sessionId": session_id}, timeout=5.0
            )
            if res and not res.get("isError"):
                deleted = True

        if not deleted and os.environ.get("AUTOFAB_DSH_WEB") == "1":
            try:
                data = json.dumps({"sessionId": session_id}).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:3080/session-manager/api/delete",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        body = json.loads(resp.read().decode("utf-8"))
                        if body.get("ok"):
                            deleted = True
            except Exception:
                pass

        server_info = _discover_desktop_server(sessions_dir)
        if server_info:
            port, cookie_name, cookie_value = server_info
            res = _call_dsh_rpc(
                port,
                cookie_name,
                cookie_value,
                "session/delete",
                {"request": {"sessionId": session_id}},
                timeout=2.0,
            )
            if (
                res
                and isinstance(res, dict)
                and res.get("result", {}).get("ok") is not False
            ):
                deleted = True

        actual_sessions_dir = sessions_dir or _resolve_default_sessions_dir()
        if actual_sessions_dir and os.path.isdir(actual_sessions_dir):
            try:
                for ws_entry in os.listdir(actual_sessions_dir):
                    cand = os.path.join(actual_sessions_dir, ws_entry, session_id)
                    if os.path.isdir(cand):
                        shutil.rmtree(cand, ignore_errors=True)
                        deleted = True
            except Exception:
                pass

        return deleted

    # Contract: MUST discover and delete all existing sessions whose title contains [<dir_scope>].
    def cleanup_scope_sessions(
        self,
        dir_scope: str,
        sessions_dir: Optional[str] = None,
    ) -> int:
        """Discovers and deletes all existing sessions whose title contains [<dir_scope>]."""
        clean_scope = dir_scope.strip("/").strip()
        if not clean_scope:
            return 0
        display_scope = os.path.basename(clean_scope)
        target_tags = {f"[{clean_scope}]", f"[{display_scope}]"}
        sessions_to_delete: list[str] = []

        bridge = _discover_web_bridge()
        if bridge:
            res = _call_web_bridge(bridge, "dsh_list_sessions", {}, timeout=5.0)
            if res:
                content_list = res.get("content", [])
                if content_list and isinstance(content_list, list):
                    txt = content_list[0].get("text", "")
                    try:
                        items = json.loads(txt)
                        if isinstance(items, list):
                            for it in items:
                                if isinstance(it, dict):
                                    title = it.get("title") or ""
                                    sid = it.get("sessionId")
                                    if sid and any(tag in title for tag in target_tags):
                                        if sid not in sessions_to_delete:
                                            sessions_to_delete.append(sid)
                    except Exception:
                        pass

        server_info = _discover_desktop_server(sessions_dir)
        if server_info:
            port, cookie_name, cookie_value = server_info
            res = _call_dsh_rpc(
                port,
                cookie_name,
                cookie_value,
                "session/list",
                {"_request": {}},
                timeout=2.0,
            )
            if res and isinstance(res, dict):
                items = res.get("result", {}).get("value", {}).get("items", [])
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict):
                            title = it.get("title") or ""
                            sid = it.get("sessionId")
                            if sid and any(tag in title for tag in target_tags):
                                if sid not in sessions_to_delete:
                                    sessions_to_delete.append(sid)

        deleted_count = 0
        for sid in sessions_to_delete:
            if self.delete_session(sid, sessions_dir=sessions_dir):
                deleted_count += 1
        return deleted_count


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-11-09T23:32:00Z
# CHANGE: Realize session renaming, deletion, and scope conversation cleanup operations
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
