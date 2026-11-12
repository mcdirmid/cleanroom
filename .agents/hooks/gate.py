import json
import os
import re
import sys

def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({"decision": "allow"}))
            return
        data = json.loads(raw)
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return

    def allow() -> None:
        print(json.dumps({"decision": "allow"}))
        sys.exit(0)

    def allow_overwrite(overwrite: dict) -> None:
        print(json.dumps({"decision": "allow", "overwrite": overwrite}))
        sys.exit(0)

    def deny(reason: str) -> None:
        print(json.dumps({"decision": "deny", "reason": reason}))
        sys.exit(0)

    tool_call = data.get("toolCall", {})
    name = tool_call.get("name", "")
    args = tool_call.get("args", {})
    conv_id = data.get("conversationId", "")
    last_user_input = data.get("lastUserInput", "")

    # 1. CONVERSATIONAL CHAT EXEMPTION
    # In Antigravity, root interactive chat always starts with source == "USER_EXPLICIT".
    # Conversational chat is completely unconstrained by Autofab rules.
    candidates = []
    tpath = data.get("transcriptPath")
    if tpath and os.path.isfile(tpath):
        candidates.append(tpath)
    if conv_id:
        brain_tpath = os.path.expanduser(f"~/.gemini/antigravity/brain/{conv_id}/.system_generated/logs/transcript.jsonl")
        if brain_tpath not in candidates and os.path.isfile(brain_tpath):
            candidates.append(brain_tpath)

    for c_file in candidates:
        try:
            with open(c_file, "r", encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if rec.get("step_index") == 0:
                        if rec.get("source") == "USER_EXPLICIT":
                            allow()
                        break
                    elif rec.get("source") == "USER_EXPLICIT":
                        allow()
                        break
        except Exception:
            pass

    # 2. REGISTRY MANAGEMENT FOR WORKER SUBAGENTS
    plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    registry_path = os.path.join(plugin_dir, "active_workers.json")

    registry = {}
    if os.path.isfile(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                content_reg = json.load(f)
                if isinstance(content_reg, dict):
                    registry = content_reg
        except Exception:
            registry = {}

    pruned = False
    for cid in list(registry.keys()):
        entry = registry[cid]
        if not isinstance(entry, dict) or not os.path.isdir(entry.get("workspace_dir", "")):
            del registry[cid]
            pruned = True

    ws_pattern = re.compile(
        r"(?:assigned\s+(?:role\s+)?workspace(?:\s+directory)?\s+(?:is\s*[:=]?\s*|:\s*)|workspace:\s*)['\"](?P<ws>[^'\"]+)['\"]",
        re.IGNORECASE,
    )
    role_pattern = re.compile(
        r"autonomous\s+Autofab\s+(?:fused\s+)?'?(?P<role>[a-zA-Z0-9_-]+)'?\s+worker",
        re.IGNORECASE,
    )

    ws_dir = None
    if conv_id and conv_id in registry:
        ws_dir = registry[conv_id].get("workspace_dir")

    if not ws_dir and conv_id:
        for c_file in candidates:
            try:
                with open(c_file, "r", encoding="utf-8") as fp:
                    for _ in range(5):
                        line_str = fp.readline()
                        if not line_str:
                            break
                        rec = json.loads(line_str)
                        text = rec.get("content", "")
                        m = ws_pattern.search(text)
                        if m:
                            cand = m.group("ws").strip()
                            if os.path.isdir(cand):
                                ws_dir = cand
                                rm = role_pattern.search(text)
                                role = rm.group("role") if rm else "worker"
                                registry[conv_id] = {
                                    "role": role,
                                    "workspace_dir": ws_dir,
                                }
                                pruned = True
                                break
                    if ws_dir:
                        break
            except Exception:
                pass

    if not ws_dir and last_user_input:
        m = ws_pattern.search(last_user_input)
        if m:
            cand = m.group("ws").strip()
            if os.path.isdir(cand):
                ws_dir = cand
                if conv_id:
                    rm = role_pattern.search(last_user_input)
                    role = rm.group("role") if rm else "worker"
                    registry[conv_id] = {
                        "role": role,
                        "workspace_dir": ws_dir,
                    }
                    pruned = True

    if pruned:
        try:
            tmp_path = f"{registry_path}.tmp.{os.getpid()}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2)
                f.write("\n")
            os.replace(tmp_path, registry_path)
        except Exception:
            pass

    # 3. COORDINATOR SUBAGENT CONSTRAINTS
    _coord_name = "autofab" + "_coordinator"
    _coord_name2 = "Zero-Execution Autofab " + "Coordinator"
    coordinator_pattern = re.compile(
        rf"(?:{_coord_name2}|{_coord_name})",
        re.IGNORECASE,
    )
    is_coord = False
    if not ws_dir:
        if last_user_input and coordinator_pattern.search(last_user_input):
            is_coord = True
        elif candidates:
            for c_file in candidates:
                try:
                    with open(c_file, "r", encoding="utf-8") as fp:
                        first = fp.readline()
                        if first:
                            rec = json.loads(first)
                            content = rec.get("content", "")
                            if coordinator_pattern.search(content):
                                is_coord = True
                                break
                except Exception:
                    pass

    if is_coord:
        if name in ("write_file", "edit_file", "view_file", "write_to_file", "replace_file_content", "multi_replace_file_content"):
            deny("STRICT POLICY VIOLATION: The Autofab Coordinator subagent has zero code custody and cannot author or edit files.")

        if name == "run_command":
            cmd = (args.get("CommandLine") or "").strip("'\"").strip()
            coord_cmd_pattern = re.compile(
                r"^\s*uv\s+run\s+autofab\s+(?:work-queue|verify-fused|harvest-fused|decommission)\b"
            )
            if not coord_cmd_pattern.search(cmd):
                deny(
                    "STRICT POLICY VIOLATION: The Autofab Coordinator subagent is strictly constrained to orchestrating subagents "
                    "and may only execute 'uv run autofab' queue and lifecycle commands."
                )
        allow()

    if not ws_dir:
        allow()

    # 4. ROLE WORKER HERMETIC ROOT INVARIANT
    canonical_ws = os.path.realpath(os.path.abspath(ws_dir))

    if name == "run_command":
        cmd = (args.get("CommandLine") or "").strip("'\"").strip()

        if re.search(r"(?:^|[\s;&|`$()])git(?:\.exe)?(?:\s|$)", cmd) or re.search(
            r"(?:^|[\s;&|`$()])(?:\.git/|cat\s+.*\.git|tail\s+.*\.git|head\s+.*\.git|ls\s+.*\.git)",
            cmd,
        ):
            deny(
                "STRICT POLICY VIOLATION: Direct git commands and inspecting .git/ directories are strictly prohibited in Autofab workspaces. "
                "Workspace state and submissions are managed exclusively through repository binaries "
                "(bin/check_files, bin/submit, bin/blame). To revert broken edits, use bin/revert."
            )

        if re.search(r"(?:^|[\s;&|`$()])unzip(?:\s|$)", cmd):
            deny("STRICT POLICY VIOLATION: Unzipping runner binaries or inspecting internal tool archives is strictly prohibited.")

        if "/projects/cleanroom" in cmd or "/cleanroom/" in cmd:
            deny(f"STRICT BOUNDARY VIOLATION: Referencing host repository paths outside your role workspace is strictly prohibited. Confined to: '{ws_dir}'.")

        probe_pattern = re.compile(
            r"(?:^|[;&|`()]\s*|\$\(\s*)(?:(?:sudo|env|time|nohup)\s+)*(?:python[0-9.]*|pytest|pyright|mypy|ruff|ipython|uv\s+run)(?:\.exe)?(?:\s|$)",
            re.IGNORECASE,
        )
        if probe_pattern.search(cmd):
            deny("STRICT POLICY VIOLATION: Role workers are strictly prohibited from executing ad-hoc Python probes or test runners directly.")

        cd_re = re.compile(r"(?:^|[;&|`()]\s*|\$\(\s*)\s*cd(?:\s+([^;&|`$()]+|\"[^\"]+\"|'[^']+'))?")
        for m in cd_re.finditer(cmd):
            target = m.group(1)
            if not target:
                deny(f"STRICT BOUNDARY VIOLATION: Subagents are permanently rooted in their workspace directory ('{ws_dir}').")
            clean_target = target.strip("'\"").strip()
            if clean_target in (".", "./"):
                continue
            try:
                target_canonical = os.path.realpath(os.path.abspath(clean_target))
            except Exception:
                target_canonical = ""
            if target_canonical == canonical_ws or clean_target == ws_dir:
                continue
            deny(f"STRICT BOUNDARY VIOLATION: Subagents are permanently rooted in their workspace directory ('{ws_dir}').")

        pattern_escaped = re.escape(ws_dir)
        canonical_escaped = re.escape(canonical_ws)
        prefix_re = re.compile(rf"^\s*cd\s+['\"]?(?:{pattern_escaped}|{canonical_escaped})['\"]?\s*&&\s*", re.IGNORECASE)
        if not prefix_re.search(cmd):
            new_cmd = f"cd {ws_dir} && ({cmd})"
            allow_overwrite({"CommandLine": new_cmd})
        elif (args.get("CommandLine") or "") != cmd:
            allow_overwrite({"CommandLine": cmd})
        else:
            allow()

    elif name in ("read_file", "write_file", "edit_file", "view_file", "write_to_file", "replace_file_content", "multi_replace_file_content"):
        raw_path = args.get("Path") or args.get("path") or ""
        path = raw_path.strip("'\"").strip()
        path_key = "Path" if "Path" in args else "path"

        if "/scratch/" in path or path.endswith("/scratch"):
            deny("STRICT POLICY VIOLATION: Authoring files in scratch/ directories is strictly prohibited.")

        overwrite_patch = {}
        for ok in ("Overwrite", "overwrite"):
            if ok in args and isinstance(args[ok], str):
                overwrite_patch[ok] = args[ok].lower() == "true"

        if not os.path.isabs(path):
            resolved = os.path.normpath(os.path.join(ws_dir, path))
            canonical_resolved = os.path.realpath(resolved)
            if canonical_resolved == canonical_ws or canonical_resolved.startswith(canonical_ws + os.sep):
                patch = {path_key: resolved, **overwrite_patch}
                allow_overwrite(patch)
            else:
                deny(f"STRICT BOUNDARY VIOLATION: Path traversal '{path}' escapes assigned workspace.")
        else:
            canonical_path = os.path.realpath(os.path.normpath(path))
            if canonical_path == canonical_ws or canonical_path.startswith(canonical_ws + os.sep):
                if raw_path != path or overwrite_patch:
                    patch = {path_key: path, **overwrite_patch}
                    allow_overwrite(patch)
                else:
                    allow()
            else:
                deny(f"STRICT BOUNDARY VIOLATION: Access to path '{path}' is strictly prohibited. Confined to: '{ws_dir}'.")

    allow()

if __name__ == "__main__":
    main()
