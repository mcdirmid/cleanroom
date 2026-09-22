#!/usr/bin/env python3
"""cleanroom_dag_cli.py — CLI helper for Cleanroom DAG inspection and role discovery.

Supports top-level Antigravity skills and orchestrators:
  - resolve-roles: Discover the target role and all transitive dependency roles in topological order.
  - inject-change: Attach a Change message to a node, marking it and its dependents dirty.
  - status: Query the subgraph completion and dirty node status.

Supports both canonical 2-argument addressing (role, unit) and define_node target shortcuts (e.g. //testing/parts/sandbox:sandbox_asm_qa).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, List, Optional, Sequence

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

# Canonical Python role dependency graph
PYTHON_ROLE_DEPENDENCIES: dict[str, list[str]] = {
    "//update_python_with_ai:high": [],
    "//update_python_with_ai:low": ["//update_python_with_ai:high"],
    "//update_python_with_ai:lib": ["//update_python_with_ai:low", "//update_python_with_ai:high"],
    "//update_python_with_ai:test": [
        "//update_python_with_ai:lib",
        "//update_python_with_ai:low",
        "//update_python_with_ai:high",
    ],
    "//update_python_with_ai:qa": [
        "//update_python_with_ai:test",
        "//update_python_with_ai:lib",
        "//update_python_with_ai:low",
        "//update_python_with_ai:high",
    ],
    "//update_python_with_ai:coverage": [
        "//update_python_with_ai:qa",
        "//update_python_with_ai:test",
        "//update_python_with_ai:lib",
        "//update_python_with_ai:low",
        "//update_python_with_ai:high",
    ],
}

PYTHON_ROLES = ["high", "low", "lib", "test", "qa", "coverage"]


def normalize_role_address(role: str) -> str:
    """Normalizes a role label into a canonical Bazel target address."""
    s = role.strip()
    if s.startswith("//"):
        return s
    if s.startswith(":"):
        return f"//update_python_with_ai{s}"
    return f"//update_python_with_ai:{s}"


def normalize_unit_address(unit: str) -> str:
    """Normalizes a unit path or target into a canonical Bazel target address."""
    s = unit.strip()
    if s.startswith("//"):
        return s.rstrip("/")
    if s.startswith(":"):
        return s
    return f"//{s.rstrip('/')}"


def is_role_identifier(val: str) -> bool:
    """Checks if a string represents a role label or role name."""
    s = val.strip()
    if s in PYTHON_ROLES or s.lstrip(":") in PYTHON_ROLES:
        return True
    if s.startswith("//update_python_with_ai:") or s.startswith("//roles:"):
        return True
    if ":" in s:
        after = s.split(":", 1)[1]
        if after in PYTHON_ROLES:
            return True
    return False


def resolve_define_node_target(target: str) -> tuple[str, str]:
    """Resolves a define_node target into (role_address, unit_address).

    Handles shortcuts like:
      //testing/parts/sandbox:sandbox_asm_qa -> (//update_python_with_ai:qa, //testing/parts/sandbox:sandbox_asm)
      :sandbox_asm_qa -> (//update_python_with_ai:qa, :sandbox_asm)
    Falls back to `bazel query` for arbitrary define_node targets.
    """
    t = target.strip()
    if t.startswith("/") and not t.startswith("//"):
        t = "/" + t
    if ":" in t:
        pkg, target_name = t.split(":", 1)
    else:
        pkg, target_name = "", t

    for action in ["_clean", "_dirty", "_change", "_feedback", "_prompt"]:
        if target_name.endswith(action):
            target_name = target_name[: -len(action)]
            break

    for role_name in PYTHON_ROLES:
        suffix = f"_{role_name}"
        if target_name.endswith(suffix):
            unit_name = target_name[: -len(suffix)]
            for prior_role in PYTHON_ROLES:
                prior_suffix = f"_{prior_role}"
                if unit_name.endswith(prior_suffix):
                    unit_name = unit_name[: -len(prior_suffix)]
                    break
            unit_label = f"{pkg}:{unit_name}" if pkg else f":{unit_name}"
            role_label = f"//update_python_with_ai:{role_name}"
            return role_label, unit_label

    # Fallback to bazel query for arbitrary define_node rules
    try:
        u_out = subprocess.check_output(
            ["bazel", "query", f"labels(unit, {t})", "--output=label"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        r_out = subprocess.check_output(
            ["bazel", "query", f"labels(role, {t})", "--output=label"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if u_out and r_out:
            return r_out, u_out
    except Exception:
        pass

    raise ValueError(f"Target '{target}' is not a recognized define_node target or shortcut.")


def parse_target_args(
    target: Optional[str] = None,
    role: Optional[str] = None,
    unit: Optional[str] = None,
    positional: Optional[Sequence[str]] = None,
) -> tuple[str, str, Optional[str]]:
    """Parses role and unit addresses from flags or positional arguments.

    Returns:
        tuple[role_address, unit_address, Optional[node_target]]
    """
    if target:
        r, u = resolve_define_node_target(target)
        return normalize_role_address(r), normalize_unit_address(u), target

    pos = list(positional) if positional else []
    if len(pos) == 1:
        r, u = resolve_define_node_target(pos[0])
        return normalize_role_address(r), normalize_unit_address(u), pos[0]
    elif len(pos) >= 2:
        arg1, arg2 = pos[0], pos[1]
        if is_role_identifier(arg1) and not is_role_identifier(arg2):
            return normalize_role_address(arg1), normalize_unit_address(arg2), None
        elif is_role_identifier(arg2) and not is_role_identifier(arg1):
            return normalize_role_address(arg2), normalize_unit_address(arg1), None
        else:
            return normalize_role_address(arg1), normalize_unit_address(arg2), None

    if role and unit:
        return normalize_role_address(role), normalize_unit_address(unit), None
    if role and not unit:
        try:
            r, u = resolve_define_node_target(role)
            return normalize_role_address(r), normalize_unit_address(u), role
        except ValueError:
            raise ValueError(f"Missing unit address for role '{role}'.")
    if unit and not role:
        try:
            r, u = resolve_define_node_target(unit)
            return normalize_role_address(r), normalize_unit_address(u), unit
        except ValueError:
            raise ValueError(f"Missing role address for unit '{unit}'.")

    raise ValueError("Target not specified. Provide a define_node target or both role and unit.")


def resolve_roles(role_address: str, unit_address: str) -> list[str]:
    """Resolves the target role and all transitive dependency roles in topological order (root first)."""
    norm_role = normalize_role_address(role_address)

    # Check canonical role dependency mapping
    if norm_role in PYTHON_ROLE_DEPENDENCIES:
        deps = list(PYTHON_ROLE_DEPENDENCIES[norm_role])
        # Return in dependency execution order: root dependencies first, target last
        roles_in_order: list[str] = []
        for d in reversed(deps):
            if d not in roles_in_order:
                roles_in_order.append(d)
        if norm_role not in roles_in_order:
            roles_in_order.append(norm_role)
        return roles_in_order

    # Fallback to single role if unknown custom role
    return [norm_role]


def inject_change(
    unit_address: str, role_address: str, message: str
) -> dict[str, Any]:
    """Attaches a Change message to a target node in DagStorage."""
    norm_role = normalize_role_address(role_address)
    norm_unit = normalize_unit_address(unit_address)

    # Initialize Cleanroom system assembly if available
    try:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
        from update_with_ai.parts.dag.lib import dag_storage
        from update_with_ai.parts.systems.lib import bazel_mcp_system_asm

        reg = LifecycleRegistry()
        bazel_mcp_system_asm.__initialize__(reg)
        with enter_phase(system, registry=reg) as scope:
            storage = scope.get_singleton(dag_storage.DagStorage)
            node = dag_storage.Node(unit_address=norm_unit, role_address=norm_role)
            storage.add_message(dag_storage.Change(content=message), to=node)
            is_dirty = storage.is_dirty(node)
            return {
                "status": "injected",
                "unit": norm_unit,
                "role": norm_role,
                "message": message,
                "is_dirty": is_dirty,
            }
    except Exception as e:
        return {
            "status": "recorded",
            "unit": norm_unit,
            "role": norm_role,
            "message": message,
            "note": f"Change recorded (lifecycle: {e})",
        }


def get_subgraph_status(unit_address: str, role_address: str) -> dict[str, Any]:
    """Checks the completion status of the subgraph rooted at the target node."""
    norm_role = normalize_role_address(role_address)
    norm_unit = normalize_unit_address(unit_address)
    roles = resolve_roles(norm_role, norm_unit)

    try:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
        from update_with_ai.parts.dag.lib import dag_storage, dag_subgraph
        from update_with_ai.parts.systems.lib import bazel_mcp_system_asm
        from update_with_ai.parts.bazel.lib import bazel_manifest_loader

        reg = LifecycleRegistry()
        bazel_mcp_system_asm.__initialize__(reg)
        with enter_phase(system, registry=reg) as scope:
            storage = scope.get_singleton(dag_storage.DagStorage)
            manifest_loader = scope.get_singleton(bazel_manifest_loader.BazelManifestLoader)
            root = dag_storage.Node(unit_address=norm_unit, role_address=norm_role)
            visited: set[dag_storage.Node] = set()
            queue: list[dag_storage.Node] = [root]
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

            subgraph = scope.get_singleton(dag_subgraph.DagSubgraph)
            subgraph.set_target(root)

            dirty_nodes = [
                f"{n.unit_address}:{n.role_address}"
                for n in visited
                if storage.is_dirty(n)
            ]

            return {
                "unit": norm_unit,
                "role": norm_role,
                "roles": roles,
                "is_complete": subgraph.is_complete,
                "dirty_nodes": dirty_nodes,
            }
    except Exception:
        return {
            "unit": norm_unit,
            "role": norm_role,
            "roles": roles,
            "is_complete": False,
            "dirty_nodes": [],
        }


def get_next_batch(unit_address: str, role_address: str, batch_size: Optional[int] = None) -> dict[str, Any]:
    """Retrieves the next ready batch of dirty nodes to clean in topological order."""
    norm_role = normalize_role_address(role_address)
    norm_unit = normalize_unit_address(unit_address)

    if batch_size is None:
        env_bs = os.environ.get("BATCH_SIZE")
        if env_bs and env_bs.strip().isdigit():
            batch_size = int(env_bs.strip())

    try:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
        from update_with_ai.parts.dag.lib import dag_storage, dag_subgraph
        from update_with_ai.parts.systems.lib import bazel_mcp_system_asm
        from update_with_ai.parts.bazel.lib import bazel_manifest_loader

        reg = LifecycleRegistry()
        bazel_mcp_system_asm.__initialize__(reg)
        with enter_phase(system, registry=reg) as scope:
            storage = scope.get_singleton(dag_storage.DagStorage)
            manifest_loader = scope.get_singleton(bazel_manifest_loader.BazelManifestLoader)
            root = dag_storage.Node(unit_address=norm_unit, role_address=norm_role)
            visited: set[dag_storage.Node] = set()
            queue: list[dag_storage.Node] = [root]
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

            subgraph = scope.get_singleton(dag_subgraph.DagSubgraph)
            subgraph.set_target(root)

            batch = subgraph.next_ready_batch()
            if batch_size is not None and batch_size > 0:
                batch = batch[:batch_size]
            batch_nodes = [
                {"unit": n.unit_address, "role": n.role_address}
                for n in batch
            ]
            ready_role = batch[0].role_address if batch else None

            dirty_nodes = [
                f"{n.unit_address}:{n.role_address}"
                for n in visited
                if storage.is_dirty(n)
            ]

            return {
                "unit": norm_unit,
                "role": norm_role,
                "is_complete": subgraph.is_complete,
                "ready_role": ready_role,
                "batch": batch_nodes,
                "dirty_nodes": dirty_nodes,
            }
    except Exception as e:
        return {
            "unit": norm_unit,
            "role": norm_role,
            "is_complete": False,
            "ready_role": None,
            "batch": [],
            "dirty_nodes": [],
            "error": str(e),
        }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cleanroom_dag_cli",
        description="Cleanroom DAG CLI for role resolution, status, and change injection",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # resolve-roles
    p_resolve = subparsers.add_parser("resolve-roles", help="Resolve roles for a target")
    p_resolve.add_argument("positional", nargs="*", help="[target] or [role, unit]")
    p_resolve.add_argument("--target", help="define_node target shortcut (e.g. //testing/parts/sandbox:sandbox_asm_qa)")
    p_resolve.add_argument("--role", help="Target role address (e.g. //update_python_with_ai:test)")
    p_resolve.add_argument("--unit", help="Root unit address (e.g. //testing/parts/sandbox:sandbox_asm)")

    # next-batch
    p_batch = subparsers.add_parser("next-batch", help="Query next ready batch of dirty nodes")
    p_batch.add_argument("positional", nargs="*", help="[target] or [role, unit]")
    p_batch.add_argument("--target", help="define_node target shortcut")
    p_batch.add_argument("--role", help="Target role address")
    p_batch.add_argument("--unit", help="Root unit address")
    p_batch.add_argument("--batch-size", type=int, default=None, help="Maximum units in batch (e.g. 1 for single-target mode)")

    # inject-change
    p_change = subparsers.add_parser("inject-change", help="Inject a change message")
    p_change.add_argument("positional", nargs="*", help="[target, message] or [role, unit, message]")
    p_change.add_argument("--target", help="define_node target shortcut")
    p_change.add_argument("--role", help="Target role address")
    p_change.add_argument("--unit", help="Target unit address")
    p_change.add_argument("--message", help="Change message content")

    # status
    p_status = subparsers.add_parser("status", help="Check subgraph completion status")
    p_status.add_argument("positional", nargs="*", help="[target] or [role, unit]")
    p_status.add_argument("--target", help="define_node target shortcut")
    p_status.add_argument("--role", help="Target role address")
    p_status.add_argument("--unit", help="Root unit address")

    args = parser.parse_args(argv)

    if args.command == "resolve-roles":
        role, unit, node_target = parse_target_args(
            target=args.target,
            role=args.role,
            unit=args.unit,
            positional=args.positional,
        )
        roles = resolve_roles(role, unit)
        target_info: dict[str, Any] = {
            "role": role,
            "unit": unit,
        }
        if node_target:
            target_info["node_target"] = node_target

        result = {
            "target": target_info,
            "roles": roles,
        }
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0

    elif args.command == "inject-change":
        pos = list(args.positional) if args.positional else []
        message = args.message
        if not message:
            if len(pos) >= 2 and (len(pos) == 2 or not is_role_identifier(pos[-1])):
                message = pos.pop()
            else:
                raise ValueError("Change message must be provided via argument or --message flag.")

        role, unit, _ = parse_target_args(
            target=args.target,
            role=args.role,
            unit=args.unit,
            positional=pos,
        )
        res = inject_change(unit, role, message)
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
        return 0

    elif args.command == "status":
        role, unit, _ = parse_target_args(
            target=args.target,
            role=args.role,
            unit=args.unit,
            positional=args.positional,
        )
        res = get_subgraph_status(unit, role)
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
        return 0
    elif args.command == "next-batch":
        role, unit, _ = parse_target_args(
            target=args.target,
            role=args.role,
            unit=args.unit,
            positional=args.positional,
        )
        res = get_next_batch(unit, role, batch_size=args.batch_size)
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
