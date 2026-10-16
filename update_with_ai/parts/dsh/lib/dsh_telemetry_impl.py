# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:55:00Z
# CHANGE: Author dsh_telemetry_impl implementation
# CODE_HASH: 8f9044a93160
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for dsh_telemetry_impl."""

from __future__ import annotations

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
from update_with_ai.parts.agent.lib import agent_session
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


def _notify_desktop_session(
    sessions_dir: str,
    workspace_dir: str,
    session_id: str,
) -> bool:
    """Notifies live DeepSeek Harness Desktop application over local RPC bridge."""
    target_key = f"{workspace_dir}::{session_id}"
    if target_key in _notified_desktop_sessions:
        return True

    try:
        harness_dir = os.path.dirname(sessions_dir)
        desktop_dir = os.path.dirname(harness_dir)
        cookies_path = os.path.join(desktop_dir, "Cookies")
        if not os.path.isfile(cookies_path):
            return False

        # Open SQLite in immutable mode to avoid blocking or locks from Chromium
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
            return False

        cookie_name, cookie_value, port = row
        if not port or not cookie_name or not cookie_value:
            return False

        def _call_rpc(endpoint: str, payload_args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
            return None

        # 1. Ensure workspace exists in DSH Desktop in-memory registry
        ws_res = _call_rpc("workspace/create", {"request": {"path": os.path.realpath(workspace_dir)}})
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
        sess_res = _call_rpc("session/create", {"request": {"workspaceId": target_ws_id, "sessionId": session_id}})
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


class DshTelemetryParser(dsh_telemetry.DshTelemetryParser, Singleton):
    """Realizes event stream and session storage archive parsing for DeepSeek Harness."""

    tier = agent_session.agent_session

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
                # Search directory names containing the basename of the workspace
                ws_base = os.path.basename(workspace_dir.rstrip("/"))
                matches = [
                    d for d in os.listdir(sessions_dir)
                    if os.path.isdir(os.path.join(sessions_dir, d)) and ws_base in d
                ]
                if matches:
                    target_dir = os.path.join(sessions_dir, sorted(matches)[-1])
                else:
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
