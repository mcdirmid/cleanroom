#!/usr/bin/env python3
"""cleanroom_coordinator_engine.py — Deterministic Cleanroom orchestration engine.

Executes deterministic Cleanroom DAG convergence planning, worker pool lifecycle management,
tiered context-cap enforcement, and parallel role scheduling in Python code.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_with_ai"), os.path.join(_repo_root, "update_python_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from update_with_ai.support.lib.coordinator_config import CoordinatorConfig, DEFAULT_CONFIG
from update_with_ai.support.lib.antigravity_token_stats import get_conversation_stats
from update_with_ai.support.lib import cleanroom_sandbox_hook


def _call_tool(name: str, payload: dict[str, Any], port: int = 8765) -> str:
    from update_with_ai.support.lib.cleanroom_mcp_client import call_tool
    return call_tool(name, payload, port=port)


@dataclass
class WorkerState:
    """State record for an active or retained role worker."""
    conv_id: str
    role: str
    session_id: str
    created_at: float
    last_active_at: float
    unit_footprint: List[str] = field(default_factory=list)
    context_tokens: int = 0
    status: str = "idle"  # "busy" | "idle"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkerState:
        return cls(**data)


@dataclass
class CoordinatorState:
    """Persistent state across coordinator engine steps."""
    target: str
    session_counter: int = 0
    workers: Dict[str, WorkerState] = field(default_factory=dict)  # conv_id -> WorkerState
    pending_spawns: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # session_id -> metadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "session_counter": self.session_counter,
            "workers": {cid: w.to_dict() for cid, w in self.workers.items()},
            "pending_spawns": self.pending_spawns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoordinatorState:
        target = data.get("target", "")
        counter = data.get("session_counter", 0)
        workers = {
            cid: WorkerState.from_dict(w)
            for cid, w in data.get("workers", {}).items()
        }
        pending_spawns = data.get("pending_spawns", {})
        return cls(target=target, session_counter=counter, workers=workers, pending_spawns=pending_spawns)


def _get_state_path(workspace_root: Optional[str] = None) -> str:
    root = workspace_root or os.getcwd()
    cleanroom_dir = os.path.join(root, ".cleanroom")
    os.makedirs(cleanroom_dir, exist_ok=True)
    return os.path.join(cleanroom_dir, "coordinator_state.json")


def load_state(workspace_root: Optional[str] = None, target: str = "") -> CoordinatorState:
    path = _get_state_path(workspace_root)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            st = CoordinatorState.from_dict(data)
            if target and st.target != target:
                st.target = target
            return st
        except Exception:
            pass
    return CoordinatorState(target=target)


def save_state(state: CoordinatorState, workspace_root: Optional[str] = None) -> None:
    path = _get_state_path(workspace_root)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)


def ensure_mcp_server_running(
    port: int = 8765,
    batch_size: int = 10,
    workspace_root: Optional[str] = None,
) -> bool:
    """Verifies that the Cleanroom FastMCP server is active, starting it in the background if absent."""
    sent_path = cleanroom_sandbox_hook.get_sentinel_path(workspace_root)
    if os.path.exists(sent_path):
        sdata = cleanroom_sandbox_hook.read_sentinel_file(sent_path)
        if sdata and cleanroom_sandbox_hook.is_process_alive(sdata.get("pid")):
            return True
        try:
            os.remove(sent_path)
        except Exception:
            pass

    cmd = [
        sys.executable,
        "update_with_ai/parts/systems/lib/cleanroom_mcp_runner_impl.py",
        "--transport",
        "sse",
        "--port",
        str(port),
        "--batch-size",
        str(batch_size),
    ]
    root = workspace_root or os.getcwd()
    subprocess.Popen(cmd, cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(0.2)
        if os.path.exists(sent_path):
            sdata = cleanroom_sandbox_hook.read_sentinel_file(sent_path)
            if sdata and cleanroom_sandbox_hook.is_process_alive(sdata.get("pid")):
                return True
    return False


def build_worker_prompt(role: str, unit: str, session_id: str, units: List[str]) -> str:
    """Constructs the prompt for a freshly spawned cleanroom_role_worker."""
    unit_list_str = json.dumps(units)
    return (
        f"You are the Cleanroom role worker for role '{role}' at target '{unit}'.\n"
        f"Your assigned session ID is '{session_id}'.\n"
        f"Your assigned batch is: {unit_list_str}.\n\n"
        f"Execution procedure:\n"
        f"1. Register session at target root:\n"
        f"   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {session_id} register --role \"{role}\" --unit \"{unit}\"\n"
        f"2. Retrieve task prompt:\n"
        f"   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {session_id} get-work\n"
        f"3. Macro-batch execution across ALL files in the batch:\n"
        f"   - Inspect grounding specs (.pyi) and role guide (.md) for the batch in whole passes (avoid 50-line micro-slicing).\n"
        f"   - Apply edits across all files via replace_file_content or write_to_file.\n"
        f"   - Run whole-batch verification:\n"
        f"     python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {session_id} check-files\n"
        f"   - Submit verified files (dependencies first):\n"
        f"     python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {session_id} submit --target <path> --change-summary \"<summary>\"\n"
        f"4. When batch is complete:\n"
        f"   Send 1-line completion report to coordinator via send_message ('status: complete') and finish turn immediately. Do NOT call get-work again."
    )


def build_revive_message(role: str, unit: str, session_id: str, units: List[str]) -> str:
    """Constructs the wake message for a warm retained worker."""
    unit_list_str = json.dumps(units)
    return (
        f"New tasks are ready for role '{role}' at target '{unit}' (Session: {session_id}).\n"
        f"Your assigned batch is: {unit_list_str}.\n\n"
        f"Procedure:\n"
        f"1. Run get-work to receive updated feedback:\n"
        f"   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {session_id} get-work\n"
        f"2. Apply targeted fixes directly in your warm context without re-reading unchanged specifications.\n"
        f"3. Run whole-batch verification:\n"
        f"   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {session_id} check-files\n"
        f"4. Submit verified files (dependencies first):\n"
        f"   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {session_id} submit --target <path> --change-summary \"<summary>\"\n"
        f"5. Send 1-line completion report to coordinator via send_message ('status: complete') and finish turn immediately."
    )


def update_worker_stats(state: CoordinatorState, now: Optional[float] = None) -> None:
    """Refreshes context token counts and idle states for all tracked workers."""
    for conv_id, worker in list(state.workers.items()):
        stats = get_conversation_stats(conv_id)
        if stats:
            worker.context_tokens = stats.get("last_context_tokens", 0)


def evaluate_pruning(
    state: CoordinatorState,
    config: CoordinatorConfig = DEFAULT_CONFIG,
    now: Optional[float] = None,
) -> List[str]:
    """Applies idle and tiered cap rules to prune workers.

    Returns a list of conversation IDs that must be terminated.
    """
    current_time = now if now is not None else time.time()
    to_kill: List[str] = []

    for conv_id, worker in list(state.workers.items()):
        idle_time = max(0.0, current_time - worker.last_active_at)

        # Rule 1: Idle > 10 minutes -> killed
        if idle_time > config.idle_prune_ttl_sec:
            to_kill.append(conv_id)
            continue

        # Rule 2: > 100k context AND idle > 5 minutes -> killed
        if (
            worker.context_tokens > config.idle_prune_warm_cap_tokens
            and idle_time > config.idle_prune_warm_ttl_sec
        ):
            to_kill.append(conv_id)
            continue

    for cid in to_kill:
        state.workers.pop(cid, None)

    return to_kill


def is_worker_eligible_for_reuse(
    worker: WorkerState,
    target_units: List[str],
    config: CoordinatorConfig = DEFAULT_CONFIG,
    now: Optional[float] = None,
) -> bool:
    """Evaluates whether a retained worker qualifies for reuse under tiered rules."""
    current_time = now if now is not None else time.time()
    age_sec = max(0.0, current_time - worker.created_at)

    # Unit overlap check: worker must have touched at least one unit in the target batch
    overlap = any(u in worker.unit_footprint for u in target_units)
    if not overlap:
        return False

    # Tiered age & token cap rules:
    # 1. Less than 5 minutes old -> context < 200k tokens
    if age_sec < config.ttl_fresh_sec:
        return worker.context_tokens < config.cap_fresh_tokens

    # 2. 5 to 10 minutes old -> context < 100k tokens
    if age_sec <= config.ttl_max_sec:
        return worker.context_tokens < config.cap_warm_tokens

    return False


def partition_batches_if_needed(
    batch: List[Dict[str, str]],
    batch_size: int = 10,
) -> List[List[Dict[str, str]]]:
    """Partitions large batches (> batch_size units) into parallel batches if units are independent."""
    if len(batch) <= batch_size:
        return [batch]
    # Chunk into clusters of size batch_size
    chunks: List[List[Dict[str, str]]] = []
    for i in range(0, len(batch), batch_size):
        chunks.append(batch[i : i + batch_size])
    return chunks


def plan_next_step(
    target: str,
    active_worker_reports: Optional[Dict[str, str]] = None,
    config: CoordinatorConfig = DEFAULT_CONFIG,
    workspace_root: Optional[str] = None,
    now: Optional[float] = None,
    port: int = 8765,
) -> Dict[str, Any]:
    """Computes the deterministic action plan for the next coordinator turn.

    Output format:
    {
      "is_complete": bool,
      "kill": [conv_id, ...],
      "spawns": [{"Role": ..., "TypeName": ..., "Prompt": ..., "session_id": ...}],
      "revives": [{"recipient": ..., "message": ..., "session_id": ...}],
      "dirty_nodes": [...]
    }
    """
    current_time = now if now is not None else time.time()
    state = load_state(workspace_root, target=target)

    # If any subagent sent a completion report, mark it as idle
    if active_worker_reports:
        for cid, status in active_worker_reports.items():
            if cid in state.workers:
                state.workers[cid].status = "idle"
                state.workers[cid].last_active_at = current_time

    # Update token usage stats
    update_worker_stats(state, now=current_time)

    # Prune stale workers based on idle timers and caps
    kill_ids = evaluate_pruning(state, config=config, now=current_time)

    # Ensure MCP server is running with configured batch_size
    ensure_mcp_server_running(port=port, batch_size=config.batch_size, workspace_root=workspace_root)

    # Query next batch from MCP server
    from update_with_ai.support.lib.cleanroom_dag_cli import resolve_define_node_target
    resolved_role, resolved_unit = resolve_define_node_target(target)

    nb_raw = _call_tool(
        "next_batch",
        {"unit_address": resolved_unit, "role_address": resolved_role},
        port=port,
    )
    nb_data = json.loads(nb_raw)

    is_complete = bool(nb_data.get("is_complete", False))
    dirty_nodes = nb_data.get("dirty_nodes", [])

    if is_complete or not dirty_nodes:
        # All clean: shut down server and terminate all remaining workers
        all_remaining_workers = list(state.workers.keys()) + kill_ids
        # Clear state
        state.workers.clear()
        save_state(state, workspace_root)
        try:
            _call_tool("shutdown", {}, port=port)
        except Exception:
            pass
        return {
            "is_complete": True,
            "kill": sorted(list(set(all_remaining_workers))),
            "spawns": [],
            "revives": [],
            "dirty_nodes": [],
            "summary": "Cleanroom DAG convergence achieved.",
        }

    raw_batch = nb_data.get("batch", [])
    ready_role = nb_data.get("ready_role") or (raw_batch[0]["role"] if raw_batch else None)
    if not ready_role or not raw_batch:
        save_state(state, workspace_root)
        return {
            "is_complete": False,
            "kill": kill_ids,
            "spawns": [],
            "revives": [],
            "dirty_nodes": dirty_nodes,
        }

    # Partition batch if ready units exceed batch_size
    batch_chunks = partition_batches_if_needed(raw_batch, batch_size=config.batch_size)

    spawns: List[Dict[str, Any]] = []
    revives: List[Dict[str, Any]] = []

    for chunk in batch_chunks:
        unit_addrs = [item["unit"] for item in chunk]
        primary_unit = unit_addrs[0]

        # Search for an eligible warm worker with unit overlap
        candidate_worker: Optional[WorkerState] = None
        for w in state.workers.values():
            if w.role == ready_role and w.status == "idle":
                if is_worker_eligible_for_reuse(w, unit_addrs, config=config, now=current_time):
                    candidate_worker = w
                    break

        state.session_counter += 1
        new_session = f"s_{state.session_counter}"

        if candidate_worker:
            # Revive existing worker
            candidate_worker.status = "busy"
            candidate_worker.session_id = new_session
            for u in unit_addrs:
                if u not in candidate_worker.unit_footprint:
                    candidate_worker.unit_footprint.append(u)

            # Pre-register session on server
            try:
                _call_tool(
                    "register_role_agent",
                    {"conversation_id": new_session, "role": ready_role, "unit_root": resolved_unit},
                    port=port,
                )
                sessions_path = cleanroom_sandbox_hook.get_worker_sessions_path(workspace_root=workspace_root)
                cleanroom_sandbox_hook.save_worker_session(candidate_worker.conv_id, new_session, sessions_path)
            except Exception:
                pass

            msg = build_revive_message(ready_role, primary_unit, new_session, unit_addrs)
            revives.append({
                "recipient": candidate_worker.conv_id,
                "message": msg,
                "session_id": new_session,
                "role": ready_role,
                "units": unit_addrs,
            })
        else:
            # Spawn fresh worker (keep other non-overlapping workers warm!)
            # Pre-register session
            try:
                _call_tool(
                    "register_role_agent",
                    {"conversation_id": new_session, "role": ready_role, "unit_root": resolved_unit},
                    port=port,
                )
            except Exception:
                pass

            prompt = build_worker_prompt(ready_role, primary_unit, new_session, unit_addrs)
            state.pending_spawns[new_session] = {
                "role": ready_role,
                "units": unit_addrs,
                "created_at": current_time,
            }
            spawns.append({
                "TypeName": "cleanroom_role_worker",
                "Role": f"Cleanroom Role Worker - {ready_role.split(':')[-1]}",
                "Prompt": prompt,
                "session_id": new_session,
                "role": ready_role,
                "units": unit_addrs,
            })

    save_state(state, workspace_root)

    return {
        "is_complete": False,
        "kill": kill_ids,
        "spawns": spawns,
        "revives": revives,
        "dirty_nodes": dirty_nodes,
    }


def register_spawned_workers(
    spawned_map: Dict[str, str],  # conv_id -> session_id
    workspace_root: Optional[str] = None,
    now: Optional[float] = None,
) -> None:
    """Associates newly spawned conversation IDs with their pre-registered sessions in engine state."""
    current_time = now if now is not None else time.time()
    state = load_state(workspace_root)
    sessions_path = cleanroom_sandbox_hook.get_worker_sessions_path(workspace_root=workspace_root)

    for conv_id, session_id in spawned_map.items():
        cleanroom_sandbox_hook.save_worker_session(conv_id, session_id, sessions_path)
        pending = state.pending_spawns.pop(session_id, None)
        role = pending.get("role", "") if pending else ""
        units = pending.get("units", []) if pending else []
        worker = WorkerState(
            conv_id=conv_id,
            role=role,
            session_id=session_id,
            created_at=current_time,
            last_active_at=current_time,
            unit_footprint=list(units),
            status="busy",
        )
        state.workers[conv_id] = worker

    save_state(state, workspace_root)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cleanroom Coordinator deterministic orchestration engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    step_p = subparsers.add_parser("step", help="Compute next coordinator action plan")
    step_p.add_argument("target", help="Cleanroom target (e.g. //testing/parts/sandbox:sandbox_asm_qa)")
    step_p.add_argument("--port", type=int, default=8765, help="FastMCP server port")
    step_p.add_argument("--completed-worker", nargs=2, action="append", metavar=("CONV_ID", "STATUS"),
                        help="Report worker completion (e.g. --completed-worker <id> complete)")

    register_p = subparsers.add_parser("register-spawned", help="Register newly spawned worker conversation IDs")
    register_p.add_argument("--mapping", nargs=2, action="append", metavar=("CONV_ID", "SESSION_ID"),
                            help="Associate conv_id with session_id")

    args = parser.parse_args(argv)

    if args.command == "step":
        reports = {}
        if args.completed_worker:
            for cid, stat in args.completed_worker:
                reports[cid] = stat
        plan = plan_next_step(args.target, active_worker_reports=reports, port=args.port)
        print(json.dumps(plan, indent=2))
        return 0

    if args.command == "register-spawned":
        smap = {}
        if args.mapping:
            for cid, sid in args.mapping:
                smap[cid] = sid
        register_spawned_workers(smap)
        print(json.dumps({"registered": smap}))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
