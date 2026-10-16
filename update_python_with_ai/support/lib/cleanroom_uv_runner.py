#!/usr/bin/env python3
"""cleanroom_uv_runner.py — Standalone UV Cleanroom agent loop runner."""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from update_with_ai.parts.uv.lib.uv_manifest_loader import UvManifestLoader
    from update_with_ai.parts.dag.lib.dag_storage import DagNode


def _setup_python_path() -> None:
    curr = os.path.dirname(os.path.realpath(__file__))
    repo_root = os.path.abspath(os.path.join(curr, "../../.."))
    if os.path.isdir(repo_root) and repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        for entry in os.listdir(repo_root):
            pkg_dir = os.path.join(repo_root, entry)
            if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                sup_lib = os.path.join(pkg_dir, "support", "lib")
                if os.path.isdir(sup_lib):
                    if pkg_dir not in sys.path:
                        sys.path.insert(0, pkg_dir)
                    if sup_lib not in sys.path:
                        sys.path.insert(0, sup_lib)
    except OSError:
        pass


_setup_python_path()

from support.lib.lifecycle import get_singleton

uv_cleanroom_asm = None
import importlib
_curr = os.path.dirname(os.path.realpath(__file__))
_repo = os.path.abspath(os.path.join(_curr, "../../.."))
for entry in os.listdir(_repo):
    if not entry.startswith((".", "bazel-", "venv")):
        if os.path.isdir(os.path.join(_repo, entry, "support", "lib")):
            try:
                uv_cleanroom_asm = importlib.import_module(f"{entry}.parts.systems.lib.uv_cleanroom_asm")
                uv_target = importlib.import_module(f"{entry}.parts.uv.lib.uv_target")
                uv_manifest_loader = importlib.import_module(f"{entry}.parts.uv.lib.uv_manifest_loader")
                dag_storage = importlib.import_module(f"{entry}.parts.dag.lib.dag_storage")
                loop = importlib.import_module(f"{entry}.parts.loop.lib.loop")
                openai_config = importlib.import_module(f"{entry}.parts.openai.lib.openai_config")
                OpenAIConfig = openai_config.OpenAIConfig
                break
            except ImportError:
                pass
if uv_cleanroom_asm is None:
    try:
        from update_with_ai.parts.systems.lib import uv_cleanroom_asm
        from update_with_ai.parts.uv.lib import uv_target, uv_manifest_loader
        from update_with_ai.parts.dag.lib import dag_storage
        from update_with_ai.parts.loop.lib import loop
        from update_with_ai.parts.openai.lib.openai_config import OpenAIConfig
    except ImportError:
        try:
            uv_cleanroom_asm = importlib.import_module("parts.systems.lib.uv_cleanroom_asm")
            uv_target = importlib.import_module("parts.uv.lib.uv_target")
            uv_manifest_loader = importlib.import_module("parts.uv.lib.uv_manifest_loader")
            dag_storage = importlib.import_module("parts.dag.lib.dag_storage")
            loop = importlib.import_module("parts.loop.lib.loop")
            _openai_cfg_mod = importlib.import_module("parts.openai.lib.openai_config")
            OpenAIConfig = _openai_cfg_mod.OpenAIConfig
        except ImportError:
            raise ImportError("Failed to locate uv_cleanroom_asm across discovered Cleanroom roots")

def _compute_role_depths(roles_map: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """Ranks roles by dependency depth so that upstream roles precede downstream roles."""
    depths: Dict[str, int] = {}
    resolving: Set[str] = set()

    def _depth(role: str) -> int:
        if role in depths:
            return depths[role]
        if role in resolving:
            return 0
        resolving.add(role)
        rcfg = roles_map.get(role, {})
        upstream: Set[str] = set()
        for k in (
            "role_deps",
            "star_role_deps",
            "feedback_role_deps",
            "silent_role_deps",
            "silent_cross_role_deps",
            "stub_role_deps",
        ):
            for d in rcfg.get(k) or []:
                upstream.add(d.split(":")[-1].strip().lower())
        val = 1 + max((_depth(u) for u in upstream if u in roles_map), default=-1) if upstream else 0
        resolving.discard(role)
        depths[role] = val
        return val

    for r in roles_map:
        _depth(r)
    return depths


def resolve_scope_nodes(
    target_str: str,
    root_dir: str,
    loader: Any,
    up_to_role: Optional[str] = None,
) -> Optional[List[DagNode]]:
    """Resolves a filesystem path or scope string to an ordered list of DagNodes.

    Returns None if target_str is not a directory/path scope (e.g. is a specific Bazel target label).
    """
    raw_str = target_str.strip()
    if raw_str.startswith("//") and ":" in raw_str:
        return None

    explicit_role = None
    if "#" in raw_str:
        raw_str, explicit_role = raw_str.split("#", 1)

    clean_path = raw_str.lstrip("/").rstrip("/")
    abs_cand = os.path.abspath(os.path.join(root_dir, clean_path))
    if not os.path.exists(abs_cand):
        abs_cand = os.path.abspath(clean_path)
        if not os.path.exists(abs_cand):
            for entry in sorted(os.listdir(root_dir)):
                if not entry.startswith((".", "bazel-", "venv")):
                    cand_pkg = os.path.join(root_dir, entry, clean_path)
                    if os.path.exists(cand_pkg):
                        abs_cand = os.path.abspath(cand_pkg)
                        break
            if not os.path.exists(abs_cand):
                return None

    try:
        norm_rel = os.path.relpath(abs_cand, root_dir).replace("\\", "/")
    except ValueError:
        return None

    if norm_rel == ".":
        return None

    segs = norm_rel.split("/")
    dir_scope = ""
    part_filter = None
    role_filter = explicit_role
    unit_filter = None

    if "parts" in segs:
        p_idx = segs.index("parts")
        dir_scope = "/".join(segs[:p_idx]) if p_idx > 0 else ""
        if len(segs) > p_idx + 1:
            part_filter = segs[p_idx + 1]
    else:
        dir_scope = segs[0]

    if dir_scope:
        parts_base = os.path.join(root_dir, dir_scope, "parts")
    else:
        parts_base = os.path.join(root_dir, "parts")
        if not os.path.isdir(parts_base):
            for entry in os.listdir(root_dir):
                cand = os.path.join(root_dir, entry, "parts")
                if os.path.isdir(cand) and not entry.startswith((".", "bazel-", "venv")):
                    parts_base = cand
                    dir_scope = entry
                    break

    if not os.path.isdir(parts_base):
        return None

    scope_prefix = f"{dir_scope}/parts" if dir_scope else "parts"
    canon_meth, roles_dict = loader._get_methodology_roles(root_dir, scope_prefix)
    if not roles_dict:
        raise ValueError(f"No roles declared in methodology '{canon_meth}' for scope '{target_str}'")

    dir_to_role: Dict[str, str] = {}
    for rname, rcfg in roles_dict.items():
        src_pat = rcfg.get("src_pattern", "")
        if src_pat:
            clean_pat = src_pat.replace("{unit_dir}/", "").replace("{unit_dir}\\", "")
            if "/" in clean_pat:
                layout_d = clean_pat.split("/", 1)[0]
                dir_to_role[layout_d] = rname
                if layout_d.endswith("s"):
                    dir_to_role[layout_d[:-1]] = rname
                else:
                    dir_to_role[layout_d + "s"] = rname

    if "parts" in segs:
        p_idx = segs.index("parts")
        if len(segs) > p_idx + 2:
            tier_or_file = segs[p_idx + 2]
            if tier_or_file in dir_to_role:
                if not role_filter:
                    role_filter = dir_to_role[tier_or_file]
                if len(segs) > p_idx + 3:
                    f_name = segs[p_idx + 3]
                    stem = os.path.splitext(f_name)[0]
                    if stem.endswith("_test"):
                        unit_filter = stem[:-5]
                    else:
                        unit_filter = stem

    if part_filter:
        parts_to_scan = [part_filter]
    else:
        parts_to_scan = sorted(
            [
                d
                for d in os.listdir(parts_base)
                if os.path.isdir(os.path.join(parts_base, d))
                and not d.startswith(".")
            ]
        )

    depths = _compute_role_depths(roles_dict)
    ordered_roles = sorted(roles_dict.keys(), key=lambda r: (depths.get(r, 0), r))
    if role_filter:
        roles_to_scan = [role_filter]
    elif up_to_role:
        target_clean = up_to_role.strip().lower()
        matching_idx = None
        for idx, r in enumerate(ordered_roles):
            if r.lower() == target_clean or r.split(":")[-1].strip().lower() == target_clean:
                matching_idx = idx
                break
        if matching_idx is not None:
            roles_to_scan = ordered_roles[: matching_idx + 1]
        else:
            roles_to_scan = ordered_roles
    else:
        roles_to_scan = ordered_roles

    nodes: List[DagNode] = []

    for role_name in roles_to_scan:
        for p_name in parts_to_scan:
            p_dir = os.path.join(parts_base, p_name)
            high_dir = os.path.join(p_dir, "high")
            if not os.path.isdir(high_dir):
                continue

            scope_prefix = f"{dir_scope}/parts/{p_name}" if dir_scope else f"parts/{p_name}"
            try:
                _, roles_dict = loader._get_methodology_roles(  # type: ignore[reportPrivateUsage]
                    root_dir, scope_prefix
                )
            except Exception:
                roles_dict = {}

            role_cfg = roles_dict.get(role_name, {})
            active_types = role_cfg.get("active_component_types", ["implementation"])

            for hls_file in sorted(os.listdir(high_dir)):
                if not hls_file.endswith(".md"):
                    continue
                uname = hls_file[:-3]
                if unit_filter and uname != unit_filter:
                    continue

                hls_path = os.path.join(high_dir, hls_file)
                try:
                    hls_info = loader._parse_hls(hls_path)  # type: ignore[reportPrivateUsage]
                    comp_type = hls_info.get("component_type", "implementation")
                except Exception:
                    comp_type = "implementation"

                unit_prefix = f"//{dir_scope}/parts/{p_name}:{uname}" if dir_scope else f"//parts/{p_name}:{uname}"
                if comp_type in active_types:
                    nodes.append(
                        dag_storage.DagNode(
                            unit_address=dag_storage.UnitAddress(unit_prefix),
                            role_address=dag_storage.RoleAddress(role_name),
                        )
                    )

    return nodes if nodes else None


def run_cleanroom_target(
    target_str: str,
    action: str = "clean",
    model: Optional[str] = None,
    message: Optional[str] = None,
    workspace_dir: Optional[str] = None,
    up_to_role: Optional[str] = None,
    config: Optional[str] = None,
) -> int:
    resolved_model = model or config
    if not resolved_model or resolved_model == "default":
        try:
            curr = os.path.dirname(os.path.realpath(__file__))
            r_root = (
                os.path.abspath(workspace_dir)
                if workspace_dir and os.path.isdir(workspace_dir)
                else (os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.path.abspath(os.path.join(curr, "../../..")))
            )
            import tomllib
            for cand in (os.path.join(r_root, "model_configs.toml"), os.path.join(os.path.dirname(r_root), "model_configs.toml")):
                if os.path.isfile(cand):
                    with open(cand, "rb") as f:
                        tdata = tomllib.load(f)
                    val = tdata.get("loop_default") or tdata.get("default")
                    if isinstance(val, str) and val.strip():
                        resolved_model = val.strip()
                        break
        except Exception:
            pass
    if resolved_model:
        os.environ["CLEANROOM_MODEL"] = resolved_model

    if workspace_dir and os.path.isdir(workspace_dir):
        os.chdir(workspace_dir)

    curr = os.path.dirname(os.path.realpath(__file__))
    repo_root = (
        os.path.abspath(workspace_dir)
        if workspace_dir and os.path.isdir(workspace_dir)
        else (os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.path.abspath(os.path.join(curr, "../../..")))
    )

    assert uv_cleanroom_asm is not None
    uv_cleanroom_asm.__initialize__()

    loader = get_singleton(uv_manifest_loader.UvManifestLoader)
    storage = get_singleton(dag_storage.DagStorage)
    runner = get_singleton(loop.Loop)

    scope_nodes = resolve_scope_nodes(target_str, repo_root, loader, up_to_role=up_to_role)

    if scope_nodes is not None:
        if action == "mark-clean":
            count = 0
            for n in scope_nodes:
                loader.load_manifest(n)
                if hasattr(storage, "is_dirty") and not storage.is_dirty(n):
                    continue
                if hasattr(storage, "materialize_template"):
                    storage.materialize_template(n)
                if hasattr(storage, "mark_node_clean"):
                    storage.mark_node_clean(n)
                elif hasattr(storage, "mark_subgraph_clean"):
                    storage.mark_subgraph_clean(n)
                else:
                    runner.mark_subgraph_clean(n)
                count += 1
            print(f"✔ Marked {count} target(s) clean across {target_str}")
            return 0

        elif action == "dirty":
            reason = message or "Marked dirty"
            for n in scope_nodes:
                loader.load_manifest(n)
                if hasattr(storage, "mark_node_dirty"):
                    storage.mark_node_dirty(n, reason=reason)
                else:
                    msg = dag_storage.ChangeMessage(content=dag_storage.MessageContent(reason))
                    runner.mark_dirty(n, msg)
            print(f"✔ Marked {len(scope_nodes)} target(s) dirty across {target_str} ({reason})")
            return 0

        elif action == "change":
            desc = message or "Manual change"
            for n in scope_nodes:
                loader.load_manifest(n)
                storage.mark_node_clean(n, dag_storage.ChangeDescription(desc))
            print(f"✔ Recorded change for {len(scope_nodes)} target(s) across {target_str}: {desc}")
            return 0

        elif action == "prompt":
            for n in scope_nodes:
                loader.load_manifest(n)
                get_defn = getattr(storage, "get_node_definition", None)
                defn = get_defn(n) if callable(get_defn) else None
                prompt = getattr(defn, "task_prompt", None) if defn else None
                if prompt:
                    print(f"=== {n.unit_address}#{n.role_address} ===\n{prompt}\n")
            return 0

        elif len(scope_nodes) == 1:
            node = scope_nodes[0]
            loader.load_manifest(node)
        elif action == "clean":
            openai_cfg = get_singleton(OpenAIConfig)
            cfg_name = resolved_model or os.environ.get("CLEANROOM_MODEL") or "default"
            dirty_nodes = []
            for n in scope_nodes:
                loader.load_manifest(n)
                if hasattr(storage, "is_dirty") and storage.is_dirty(n):
                    dirty_nodes.append(n)
            if not dirty_nodes:
                print(f"✔ CLEAN: All {len(scope_nodes)} targets in scope '{target_str}' evaluate clean.")
                return 0
            print(f"Cleaning {len(dirty_nodes)} dirty target(s) across {target_str} (config: {cfg_name}, model: {openai_cfg.model_name})...")
            for n in dirty_nodes:
                if hasattr(storage, "is_dirty") and not storage.is_dirty(n):
                    continue
                try:
                    res = runner.clean_subgraph(n)
                    if not res.success:
                        print(f"Error: {res.summary}", file=sys.stderr)
                        return 1
                    print(f"✔ {res.summary}")
                except KeyboardInterrupt:
                    print("Interrupted.", file=sys.stderr)
                    return 130
                except Exception as e:
                    print(f"Failed to execute cleaning pass: {e}", file=sys.stderr)
                    return 1
            print(f"✔ All targets in scope '{target_str}' converged clean.")
            return 0
        else:
            print(
                f"Error: Action '{action}' cannot be run across multiple targets in scope '{target_str}' ({len(scope_nodes)} nodes). Specify a single target.",
                file=sys.stderr,
            )
            return 2
    else:
        target_util = get_singleton(uv_target.UvTarget)
        node = target_util.normalize_target(uv_target.TargetIdentifier(target_str))
        if not node.role_address:
            # Default role to 'lib' if unspecified
            node = dag_storage.DagNode(
                unit_address=node.unit_address,
                role_address=dag_storage.RoleAddress("lib"),
            )

        manifest = loader.retrieve_manifest(node)
        if manifest is None:
            print(
                f"Error: Target '{target_str}' not found (no specification found for '{node.unit_address}')",
                file=sys.stderr,
            )
            return 1

        loader.load_manifest(node)

    if action == "clean":
        openai_cfg = get_singleton(OpenAIConfig)
        cfg_name = resolved_model or os.environ.get("CLEANROOM_MODEL") or "default"
        print(f"Cleaning target {node.unit_address}#{node.role_address} (config: {cfg_name}, model: {openai_cfg.model_name})...")
        try:
            res = runner.clean_subgraph(node)
            if not res.success:
                print(f"Error: {res.summary}", file=sys.stderr)
                return 1
            print(f"✔ {res.summary}")
            return 0
        except KeyboardInterrupt:
            print("Interrupted.", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"Failed to execute cleaning pass: {e}", file=sys.stderr)
            return 1

    elif action == "mark-clean":
        if hasattr(storage, "get_dependencies"):
            visited: Set[DagNode] = set()
            order: List[DagNode] = []

            def dfs(n: DagNode) -> None:
                if n in visited:
                    return
                visited.add(n)
                loader.load_manifest(n)
                for dep in storage.get_dependencies(n):
                    dfs(dep.node)
                order.append(n)

            dfs(node)
            count = 0
            for n in order:
                if hasattr(storage, "is_dirty") and not storage.is_dirty(n):
                    continue
                if hasattr(storage, "materialize_template"):
                    storage.materialize_template(n)
                if hasattr(storage, "mark_node_clean"):
                    storage.mark_node_clean(n)
                elif hasattr(storage, "mark_subgraph_clean"):
                    storage.mark_subgraph_clean(n)
                else:
                    runner.mark_subgraph_clean(n)
                count += 1
            if count == 0:
                print(f"✔ Target is already clean: {node.unit_address}#{node.role_address}")
            else:
                print(f"✔ Marked {count} target(s) clean: {node.unit_address}#{node.role_address}")
            return 0
        else:
            if hasattr(storage, "is_dirty") and not storage.is_dirty(node):
                print(f"✔ Target is already clean: {node.unit_address}#{node.role_address}")
                return 0
            if hasattr(storage, "materialize_template"):
                storage.materialize_template(node)
            if hasattr(storage, "mark_node_clean"):
                storage.mark_node_clean(node)
            elif hasattr(storage, "mark_subgraph_clean"):
                storage.mark_subgraph_clean(node)
            else:
                runner.mark_subgraph_clean(node)
            print(f"✔ Marked target clean: {node.unit_address}#{node.role_address}")
            return 0

    elif action == "change":
        desc = message or "Manual change"
        storage.mark_node_clean(node, dag_storage.ChangeDescription(desc))
        print(f"✔ Recorded change for {node.unit_address}#{node.role_address}: {desc}")
        return 0

    elif action == "feedback":
        if not message:
            print("Error: feedback action requires a critique message", file=sys.stderr)
            return 2
        fb_msg = dag_storage.FeedbackMessage(content=dag_storage.MessageContent(message))
        if hasattr(storage, "add_feedback_message"):
            storage.add_feedback_message(node, fb_msg)
        else:
            storage.add_message(fb_msg, to=node)
        print(f"✔ Added feedback to {node.unit_address}#{node.role_address}: {message}")
        return 0

    elif action == "dirty":
        reason = message or "Marked dirty"
        if hasattr(storage, "mark_node_dirty"):
            storage.mark_node_dirty(node, reason=reason)
        else:
            msg = dag_storage.ChangeMessage(content=dag_storage.MessageContent(reason))
            runner.mark_dirty(node, msg)
        print(f"✔ Marked dirty: {node.unit_address}#{node.role_address} ({reason})")
        return 0

    elif action == "prompt":
        get_defn = getattr(storage, "get_node_definition", None)
        defn = get_defn(node) if callable(get_defn) else None
        prompt = getattr(defn, "task_prompt", None) if defn else None
        if prompt:
            print(prompt)
        else:
            print(f"No prompt configured for {node.unit_address}#{node.role_address}")
        return 0

    else:
        print(f"Unrecognized action: {action}", file=sys.stderr)
        return 2


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cleanroom-loop",
        description="Cleanroom Autonomous Agent Loop Runner (Native UV)",
    )
    parser.add_argument(
        "target",
        help="Target node or file path (e.g. //parts/agent:agent_config#lib or lib/agent_config.py)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model configuration or profile name (e.g. default, careful, fast)",
    )
    parser.add_argument(
        "--action",
        "-a",
        choices=["clean", "mark-clean", "change", "feedback", "dirty", "prompt"],
        default="clean",
        help="Action to perform on target node (default: clean)",
    )
    parser.add_argument(
        "--message",
        "-m",
        default=None,
        help="Message payload for change, feedback, or dirty action",
    )
    parser.add_argument(
        "--workspace-dir",
        "-w",
        default=None,
        help="Custom workspace directory (default: current working directory)",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Additional arguments or trailing message",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    msg = args.message
    if not msg and args.extra_args:
        msg = " ".join(args.extra_args)

    return run_cleanroom_target(
        target_str=args.target,
        action=args.action,
        model=args.model,
        message=msg,
        workspace_dir=args.workspace_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
