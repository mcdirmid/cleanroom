# Requirements specified in antigravity_coordinator_impl.pyi
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)
if not os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
    os.environ["BUILD_WORKSPACE_DIRECTORY"] = _repo_root

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import antigravity_coordinator
from . import antigravity_mcp_client
from . import antigravity_sandbox_gate
from . import antigravity_telemetry


def build_worker_prompt(role: str, unit: str, session_id: str, units: Sequence[str]) -> str:
    unit_list_str = json.dumps(list(units))
    return (
        f"You are the Cleanroom role worker for role '{role}' at target '{unit}'.\n"
        f"Your assigned session ID is '{session_id}'.\n"
        f"Your assigned batch is: {unit_list_str}.\n\n"
        f"Execution procedure:\n"
        f"1. Register session at target root:\n"
        f"   python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl --session {session_id} register --role \"{role}\" --unit \"{unit}\"\n"
        f"2. Retrieve task prompt:\n"
        f"   python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl --session {session_id} get-work\n"
        f"3. Macro-batch execution across ALL files in the batch:\n"
        f"   - Inspect grounding specs (.pyi) and role guide (.md) for the batch in whole passes (avoid 50-line micro-slicing).\n"
        f"   - Apply edits across all files via replace_file_content or write_to_file.\n"
        f"   - Run whole-batch verification:\n"
        f"     python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl --session {session_id} check-files\n"
        f"   - Submit verified files (dependencies first):\n"
        f"     python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl --session {session_id} submit --target <path> --change-summary \"<summary>\"\n"
        f"4. If verification succeeds across your batch:\n"
        f"   Send 1-line completion report to coordinator via send_message ('status: complete') and finish turn immediately. Do NOT call get-work again.\n"
        f"5. If verification fails or cannot be resolved:\n"
        f"   Call fail subcommand:\n"
        f"     python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl --session {session_id} fail --explanation \"<reason>\"\n"
        f"   Send failure report to coordinator via send_message ('status: failed: <reason>') and finish turn immediately."
    )


def build_revive_message(role: str, unit: str, session_id: str, units: Sequence[str]) -> str:
    unit_list_str = json.dumps(list(units))
    return (
        f"New tasks are ready for role '{role}' at target '{unit}' (Session: {session_id}).\n"
        f"Your assigned batch is: {unit_list_str}.\n\n"
        f"Procedure:\n"
        f"1. Run get-work to receive updated feedback:\n"
        f"   python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl --session {session_id} get-work\n"
        f"2. Apply targeted fixes directly in your warm context without re-reading unchanged specifications.\n"
        f"3. Run whole-batch verification:\n"
        f"   python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl --session {session_id} check-files\n"
        f"4. Submit verified files (dependencies first):\n"
        f"   python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl --session {session_id} submit --target <path> --change-summary \"<summary>\"\n"
        f"5. If verification succeeds, send 1-line completion report to coordinator via send_message ('status: complete') and finish turn immediately.\n"
        f"6. If verification fails or cannot be resolved:\n"
        f"   Call fail subcommand:\n"
        f"     python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl --session {session_id} fail --explanation \"<reason>\"\n"
        f"   Send failure report to coordinator via send_message ('status: failed: <reason>') and finish turn immediately."
    )


def _get_state_path(workspace_root: Optional[str] = None) -> str:
    root = workspace_root or os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
    cleanroom_dir = os.path.join(root, ".cleanroom")
    os.makedirs(cleanroom_dir, exist_ok=True)
    return os.path.join(cleanroom_dir, "coordinator_state.json")


class AntigravityCoordinator(antigravity_coordinator.AntigravityCoordinator, Singleton):
    tier = system

    def load_state(self, root: str, target: str) -> antigravity_coordinator.CoordinatorState:
        path = _get_state_path(root)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tgt = target or data.get("target", "")
                counter = data.get("session_counter", 0)
                workers = {
                    cid: antigravity_coordinator.WorkerState(**w)
                    for cid, w in data.get("workers", {}).items()
                }
                pending = data.get("pending_spawns", {})
                fcounts = {str(k): int(v) for k, v in data.get("failure_counts", {}).items()}
                return antigravity_coordinator.CoordinatorState(
                    target=tgt,
                    session_counter=counter,
                    workers=workers,
                    pending_spawns=pending,
                    failure_counts=fcounts,
                )
            except Exception:
                pass
        return antigravity_coordinator.CoordinatorState(
            target=target,
            session_counter=0,
            workers={},
            pending_spawns={},
            failure_counts={},
        )

    def save_state(self, state: antigravity_coordinator.CoordinatorState, root: str) -> None:
        path = _get_state_path(root)
        payload = {
            "target": state.target,
            "session_counter": state.session_counter,
            "workers": {
                cid: {
                    "conv_id": w.conv_id,
                    "role": w.role,
                    "session_id": w.session_id,
                    "created_at": w.created_at,
                    "last_active_at": w.last_active_at,
                    "unit_footprint": list(w.unit_footprint),
                    "context_tokens": w.context_tokens,
                    "status": w.status,
                }
                for cid, w in state.workers.items()
            },
            "pending_spawns": dict(state.pending_spawns),
            "failure_counts": dict(state.failure_counts),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def evaluate_pruning(
        self,
        state: antigravity_coordinator.CoordinatorState,
        config: antigravity_coordinator.CoordinatorConfig,
        now: float,
    ) -> Sequence[str]:
        to_kill: List[str] = []
        for conv_id, worker in list(state.workers.items()):
            if worker.status == "failed":
                to_kill.append(conv_id)
                continue
            idle_time = max(0.0, now - worker.last_active_at)
            if idle_time > config.idle_prune_ttl_sec:
                to_kill.append(conv_id)
                continue
            if (
                worker.context_tokens > config.idle_prune_warm_cap_tokens
                and idle_time > config.idle_prune_warm_ttl_sec
            ):
                to_kill.append(conv_id)
                continue

        workers_mut = dict(state.workers)
        for cid in to_kill:
            workers_mut.pop(cid, None)
        # Note: state.workers is updated in caller or mutably if dict
        if isinstance(state.workers, dict):
            for cid in to_kill:
                state.workers.pop(cid, None)
        return to_kill

    def is_worker_eligible_for_reuse(
        self,
        worker: antigravity_coordinator.WorkerState,
        units: Sequence[str],
        config: antigravity_coordinator.CoordinatorConfig,
        now: float,
    ) -> bool:
        if worker.status != "idle":
            return False
        age_sec = max(0.0, now - worker.created_at)

        if age_sec < config.ttl_fresh_sec:
            return worker.context_tokens < config.cap_fresh_tokens

        if age_sec <= config.ttl_max_sec:
            return worker.context_tokens < config.cap_warm_tokens

        return False

    def partition_batches(
        self,
        batch: Sequence[Mapping[str, str]],
        batch_size: int,
    ) -> Sequence[Sequence[Mapping[str, str]]]:
        if len(batch) <= batch_size:
            return [batch]
        chunks: List[Sequence[Mapping[str, str]]] = []
        for i in range(0, len(batch), batch_size):
            chunks.append(batch[i : i + batch_size])
        return chunks

    def ensure_server_running(self, port: int, batch_size: int, root: str) -> bool:
        from .antigravity_sandbox_gate_impl import get_sentinel_path, read_sentinel_file, is_process_alive
        sent_path = get_sentinel_path(root)
        if os.path.exists(sent_path):
            sdata = read_sentinel_file(sent_path)
            if sdata and is_process_alive(sdata.get("pid")):
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
        subprocess.Popen(cmd, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            time.sleep(0.2)
            if os.path.exists(sent_path):
                sdata = read_sentinel_file(sent_path)
                if sdata and is_process_alive(sdata.get("pid")):
                    return True
        return False

    def plan_next_step(
        self,
        target: str,
        reports: Mapping[str, str],
        config: antigravity_coordinator.CoordinatorConfig,
        root: str,
        now: float,
        port: int,
        reset: bool = False,
    ) -> antigravity_coordinator.ActionPlan:
        if reset:
            state = antigravity_coordinator.CoordinatorState(
                target=target,
                session_counter=0,
                workers={},
                pending_spawns={},
                failure_counts={},
            )
        else:
            state = self.load_state(root, target)
            if state.target and state.target != target:
                state = antigravity_coordinator.CoordinatorState(
                    target=target,
                    session_counter=0,
                    workers={},
                    pending_spawns={},
                    failure_counts={},
                )
        workers_dict: Dict[str, antigravity_coordinator.WorkerState] = dict(state.workers)
        pending_dict: Dict[str, Any] = dict(state.pending_spawns)
        failure_counts: Dict[str, int] = dict(state.failure_counts)

        aborted_unit: Optional[str] = None
        for cid, status in reports.items():
            if cid in workers_dict:
                w = workers_dict[cid]
                stat_lower = str(status).strip().lower()
                is_failed = "fail" in stat_lower or stat_lower.startswith("failed")
                is_success = "complete" in stat_lower or "success" in stat_lower
                workers_dict[cid] = antigravity_coordinator.WorkerState(
                    conv_id=w.conv_id,
                    role=w.role,
                    session_id=w.session_id,
                    created_at=w.created_at,
                    last_active_at=now,
                    unit_footprint=w.unit_footprint,
                    context_tokens=w.context_tokens,
                    status="failed" if is_failed else "idle",
                )
                for u in w.unit_footprint:
                    if is_failed:
                        curr_f = failure_counts.get(u, 0) + 1
                        failure_counts[u] = curr_f
                        if curr_f > config.max_retries_per_unit:
                            aborted_unit = u
                    elif is_success:
                        failure_counts[u] = 0

        for u, fcount in failure_counts.items():
            if fcount > config.max_retries_per_unit:
                aborted_unit = u
                break

        if aborted_unit:
            all_kill = sorted(list(set(list(workers_dict.keys()) + list(self.evaluate_pruning(state, config, now)))))
            workers_dict.clear()
            pending_dict.clear()
            aborted_state = antigravity_coordinator.CoordinatorState(
                target=target,
                session_counter=state.session_counter,
                workers={},
                pending_spawns={},
                failure_counts=failure_counts,
            )
            self.save_state(aborted_state, root)
            return antigravity_coordinator.ActionPlan(
                is_complete=False,
                kill=all_kill,
                spawns=[],
                revives=[],
                dirty_nodes=[],
                summary=f"DAG convergence aborted: unit '{aborted_unit}' failed twice without resolution.",
            )

        # Update context tokens via telemetry
        try:
            telemetry = get_singleton(antigravity_telemetry.AntigravityTelemetry)
            for cid, w in list(workers_dict.items()):
                cstats = telemetry.get_conversation_stats(cid)
                if cstats:
                    workers_dict[cid] = antigravity_coordinator.WorkerState(
                        conv_id=w.conv_id,
                        role=w.role,
                        session_id=w.session_id,
                        created_at=w.created_at,
                        last_active_at=w.last_active_at,
                        unit_footprint=w.unit_footprint,
                        context_tokens=cstats.context_tokens,
                        status=w.status,
                    )
        except Exception:
            pass

        updated_state = antigravity_coordinator.CoordinatorState(
            target=state.target,
            session_counter=state.session_counter,
            workers=workers_dict,
            pending_spawns=pending_dict,
            failure_counts=failure_counts,
        )

        kill_ids = list(self.evaluate_pruning(updated_state, config, now))
        for cid in kill_ids:
            workers_dict.pop(cid, None)

        self.ensure_server_running(port=port, batch_size=config.batch_size, root=root)

        mcp_client = get_singleton(antigravity_mcp_client.AntigravityMcpClient)
        nb_raw = mcp_client.next_batch(target, port=port)
        nb_data = json.loads(nb_raw) if nb_raw.startswith("{") else {}

        is_complete = bool(nb_data.get("is_complete", False))
        dirty_nodes = nb_data.get("dirty_nodes", [])

        if is_complete or not dirty_nodes:
            all_kill = sorted(list(set(list(workers_dict.keys()) + kill_ids)))
            workers_dict.clear()
            pending_dict.clear()
            final_state = antigravity_coordinator.CoordinatorState(
                target=target,
                session_counter=state.session_counter,
                workers={},
                pending_spawns={},
                failure_counts=failure_counts,
            )
            self.save_state(final_state, root)
            try:
                mcp_client.shutdown(port=port)
            except Exception:
                pass
            return antigravity_coordinator.ActionPlan(
                is_complete=True,
                kill=all_kill,
                spawns=[],
                revives=[],
                dirty_nodes=[],
                summary="Cleanroom DAG convergence achieved.",
            )

        raw_batch = nb_data.get("batch", [])
        ready_role = nb_data.get("ready_role") or (raw_batch[0]["role"] if raw_batch else None)
        if not ready_role or not raw_batch:
            self.save_state(updated_state, root)
            return antigravity_coordinator.ActionPlan(
                is_complete=False,
                kill=kill_ids,
                spawns=[],
                revives=[],
                dirty_nodes=dirty_nodes,
                summary="Awaiting ready role nodes.",
            )

        chunks = self.partition_batches(raw_batch, batch_size=config.batch_size)

        # In-flight busy worker tracking: do not dispatch chunks whose units are already in-flight
        busy_units: set[str] = set()
        for w in workers_dict.values():
            if w.status == "busy":
                busy_units.update(w.unit_footprint)

        chunks_to_dispatch = []
        for chunk in chunks:
            chunk_units = [item["unit"] for item in chunk]
            if any(u not in busy_units for u in chunk_units):
                chunks_to_dispatch.append(chunk)

        if not chunks_to_dispatch:
            self.save_state(updated_state, root)
            return antigravity_coordinator.ActionPlan(
                is_complete=False,
                kill=kill_ids,
                spawns=[],
                revives=[],
                dirty_nodes=dirty_nodes,
                summary=f"Waiting for in-flight workers on units: {sorted(list(busy_units))}",
            )

        spawns: List[Dict[str, Any]] = []
        revives: List[Dict[str, Any]] = []
        counter = state.session_counter

        for chunk in chunks_to_dispatch:
            unit_addrs = [item["unit"] for item in chunk]
            primary_unit = unit_addrs[0]

            overlapping_candidates: List[antigravity_coordinator.WorkerState] = []
            non_overlapping_candidates: List[antigravity_coordinator.WorkerState] = []
            for w in workers_dict.values():
                if w.role == ready_role and w.status == "idle":
                    if self.is_worker_eligible_for_reuse(w, unit_addrs, config, now):
                        if any(u in w.unit_footprint for u in unit_addrs):
                            overlapping_candidates.append(w)
                        else:
                            non_overlapping_candidates.append(w)

            candidate_worker: Optional[antigravity_coordinator.WorkerState] = None
            if overlapping_candidates:
                overlapping_candidates.sort(key=lambda x: (x.context_tokens, x.created_at))
                candidate_worker = overlapping_candidates[0]
            elif non_overlapping_candidates:
                non_overlapping_candidates.sort(key=lambda x: (x.context_tokens, x.created_at))
                candidate_worker = non_overlapping_candidates[0]

            counter += 1
            new_session = f"s_{counter}"

            if candidate_worker:
                new_footprint = list(candidate_worker.unit_footprint)
                for u in unit_addrs:
                    if u not in new_footprint:
                        new_footprint.append(u)

                workers_dict[candidate_worker.conv_id] = antigravity_coordinator.WorkerState(
                    conv_id=candidate_worker.conv_id,
                    role=candidate_worker.role,
                    session_id=new_session,
                    created_at=candidate_worker.created_at,
                    last_active_at=now,
                    unit_footprint=new_footprint,
                    context_tokens=candidate_worker.context_tokens,
                    status="busy",
                )

                try:
                    mcp_client.register_session(new_session, ready_role, primary_unit, port=port)
                    gate = get_singleton(antigravity_sandbox_gate.AntigravitySandboxGate)
                    gate.save_worker_session(candidate_worker.conv_id, new_session)
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
                try:
                    mcp_client.register_session(new_session, ready_role, primary_unit, port=port)
                except Exception:
                    pass

                pending_dict[new_session] = {
                    "role": ready_role,
                    "units": unit_addrs,
                    "created_at": now,
                }
                prompt = build_worker_prompt(ready_role, primary_unit, new_session, unit_addrs)
                spawns.append({
                    "TypeName": "cleanroom_role_worker",
                    "Role": f"Cleanroom Role Worker - {ready_role.split(':')[-1]}",
                    "Prompt": prompt,
                    "session_id": new_session,
                    "role": ready_role,
                    "units": unit_addrs,
                })

        new_state = antigravity_coordinator.CoordinatorState(
            target=target,
            session_counter=counter,
            workers=workers_dict,
            pending_spawns=pending_dict,
            failure_counts=failure_counts,
        )
        self.save_state(new_state, root)

        return antigravity_coordinator.ActionPlan(
            is_complete=False,
            kill=kill_ids,
            spawns=spawns,
            revives=revives,
            dirty_nodes=dirty_nodes,
            summary="Dispatched wave action plan.",
        )

    def record_worker_status(self, session_id: str, status: str, root: str, now: float, unit: str = "") -> None:
        state = self.load_state(root, "")
        workers_dict = dict(state.workers)
        failure_counts = dict(state.failure_counts)

        stat_lower = str(status).strip().lower()
        is_failed = "fail" in stat_lower or stat_lower.startswith("failed")
        is_success = "complete" in stat_lower or "success" in stat_lower

        target_cid = None
        for cid, w in list(workers_dict.items()):
            if w.session_id == session_id:
                target_cid = cid
                workers_dict[cid] = antigravity_coordinator.WorkerState(
                    conv_id=w.conv_id,
                    role=w.role,
                    session_id=w.session_id,
                    created_at=w.created_at,
                    last_active_at=now,
                    unit_footprint=w.unit_footprint,
                    context_tokens=w.context_tokens,
                    status="failed" if is_failed else "idle",
                )
                affected_units = set(w.unit_footprint)
                if unit:
                    affected_units.add(unit)
                for u in affected_units:
                    if is_failed:
                        failure_counts[u] = failure_counts.get(u, 0) + 1
                    elif is_success:
                        failure_counts[u] = 0
                break

        if not target_cid and unit:
            if is_failed:
                failure_counts[unit] = failure_counts.get(unit, 0) + 1
            elif is_success:
                failure_counts[unit] = 0

        updated_state = antigravity_coordinator.CoordinatorState(
            target=state.target,
            session_counter=state.session_counter,
            workers=workers_dict,
            pending_spawns=state.pending_spawns,
            failure_counts=failure_counts,
        )
        self.save_state(updated_state, root)

    def register_spawned_workers(self, spawned_map: Mapping[str, str], root: str, now: float) -> None:
        state = self.load_state(root, "")
        workers_dict = dict(state.workers)
        pending_dict = dict(state.pending_spawns)

        try:
            gate = get_singleton(antigravity_sandbox_gate.AntigravitySandboxGate)
        except Exception:
            gate = None

        for conv_id, session_id in spawned_map.items():
            if gate:
                gate.save_worker_session(conv_id, session_id)
            pending = pending_dict.pop(session_id, None)
            role = pending.get("role", "") if pending else ""
            units = pending.get("units", []) if pending else []
            workers_dict[conv_id] = antigravity_coordinator.WorkerState(
                conv_id=conv_id,
                role=role,
                session_id=session_id,
                created_at=now,
                last_active_at=now,
                unit_footprint=list(units),
                context_tokens=0,
                status="busy",
            )

        new_state = antigravity_coordinator.CoordinatorState(
            target=state.target,
            session_counter=state.session_counter,
            workers=workers_dict,
            pending_spawns=pending_dict,
            failure_counts=state.failure_counts,
        )
        self.save_state(new_state, root)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AntigravityCoordinator,
        keys=[AntigravityCoordinator, antigravity_coordinator.AntigravityCoordinator],
        tier=system,
    )


_initialize_ = __initialize__


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Antigravity Cleanroom Coordinator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    step_p = subparsers.add_parser("step", help="Compute next coordinator action plan")
    step_p.add_argument("target", help="Cleanroom target")
    step_p.add_argument("--port", type=int, default=8765, help="FastMCP server port")
    step_p.add_argument(
        "--completed-worker",
        nargs=2,
        action="append",
        metavar=("CONV_ID", "STATUS"),
        help="Report worker completion",
    )
    step_p.add_argument("--reset", action="store_true", default=False, help="Reset coordinator state for fresh run")

    reg_p = subparsers.add_parser("register-spawned", help="Register spawned workers")
    reg_p.add_argument(
        "--mapping",
        nargs=2,
        action="append",
        metavar=("CONV_ID", "SESSION_ID"),
        help="Associate conv_id with session_id",
    )

    args = parser.parse_args(argv)
    try:
        import importlib
        asm = importlib.import_module("update_with_ai.parts.antigravity.lib.antigravity_asm")
        init_fn = getattr(asm, "__initialize__", None)
        if callable(init_fn):
            init_fn()
    except Exception:
        pass
    coordinator = AntigravityCoordinator()
    root = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()

    if args.command == "step":
        reports = {}
        if args.completed_worker:
            for cid, stat in args.completed_worker:
                reports[cid] = stat
        cfg = antigravity_coordinator.CoordinatorConfig()
        now = time.time()
        plan = coordinator.plan_next_step(
            target=args.target,
            reports=reports,
            config=cfg,
            root=root,
            now=now,
            port=args.port,
            reset=getattr(args, "reset", False),
        )
        print(json.dumps({
            "is_complete": plan.is_complete,
            "kill": list(plan.kill),
            "spawns": list(plan.spawns),
            "revives": list(plan.revives),
            "dirty_nodes": list(plan.dirty_nodes),
            "summary": plan.summary,
        }, indent=2))
        return 0

    if args.command == "register-spawned":
        smap = {}
        if args.mapping:
            for cid, sid in args.mapping:
                smap[cid] = sid
        now = time.time()
        coordinator.register_spawned_workers(smap, root=root, now=now)
        print(json.dumps({"registered": smap}))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
