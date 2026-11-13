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

    # Registry management for worker subagent hermetic rooting
    this_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_dir = os.path.dirname(this_dir)
    registry_path = os.path.join(plugin_dir, "active_workers.json")
    if not os.path.isfile(registry_path):
        alt_path = os.path.join(plugin_dir, "plugins", "autofab", "active_workers.json")
        if os.path.isfile(alt_path):
            registry_path = alt_path

    registry = {}
    if os.path.isfile(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                content_reg = json.load(f)
                if isinstance(content_reg, dict):
                    registry = content_reg
        except Exception:
            registry = {}

    # Stale pruning
    pruned = False
    for cid in list(registry.keys()):
        entry = registry[cid]
        if not isinstance(entry, dict) or not os.path.isdir(entry.get("workspace_dir", "")):
            del registry[cid]
            pruned = True

    ws_pattern = re.compile(
        r"(?:assigned\s+(?:role\s+)?workspace(?:\s+directory)?\s+(?:is\s*[:=]?\s*|:\s*)|workspace:\s*)[\x27\x22](?P<ws>[^\x27\x22]+)[\x27\x22]",
        re.IGNORECASE,
    )
    role_pattern = re.compile(
        r"autonomous\s+Autofab\s+(?:fused\s+)?[\x27\x22]?(?P<role>[a-zA-Z0-9_-]+)[\x27\x22]?\s+worker",
        re.IGNORECASE,
    )

    ws_dir = None
    if conv_id and conv_id in registry:
        ws_dir = registry[conv_id].get("workspace_dir")

    if not ws_dir and conv_id:
        candidates = []
        tpath = data.get("transcriptPath")
        if tpath and os.path.isfile(tpath):
            candidates.append(tpath)
        brain_tpath = os.path.expanduser(f"~/.gemini/antigravity/brain/{conv_id}/.system_generated/logs/transcript.jsonl")
        if brain_tpath not in candidates and os.path.isfile(brain_tpath):
            candidates.append(brain_tpath)

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
                f.write(chr(10))
            os.replace(tmp_path, registry_path)
        except Exception:
            pass

    # If this is NOT an active worker subagent assigned to a role workspace, ALLOW IMMEDIATELY!
    # Non-worker conversations (coordinator, parent chats, other workspaces) must NEVER be restricted.
    if not ws_dir:
        allow()

    canonical_ws = os.path.realpath(os.path.abspath(ws_dir))

    # All restrictions below apply EXCLUSIVELY to registered Autofab role workers inside their assigned role workspace

    # 1. Scratch path prohibition for role workers
    if name in ("write_file", "edit_file", "view_file", "write_to_file", "replace_file_content", "multi_replace_file_content"):
        path = (args.get("Path") or args.get("path") or "").strip().strip("'").strip('"')
        if "/scratch/" in path or path.endswith("/scratch"):
            deny(
                "STRICT POLICY VIOLATION: Authoring files in scratch/ directories is strictly prohibited. "
                "Author and edit assigned target files directly in place within your workspace."
            )

    # 2. Command restrictions for role workers
    if name == "run_command":
        cmd = (args.get("CommandLine") or "").strip().strip("'").strip('"')

        # Block referencing canonical host repository outside workspace
        if "/projects/cleanroom" in cmd or "/cleanroom/" in cmd:
            deny(
                f"STRICT BOUNDARY VIOLATION: Referencing host repository paths outside your role workspace is strictly prohibited. "
                f"You are confined exclusively to your assigned role workspace: '{ws_dir}'."
            )

        # Direct git commands and inspecting .git/ directories
        if re.search(r"(?:^|[\s;&|`$()])git(?:\.exe)?(?:\s|$)", cmd) or re.search(
            r"(?:^|[\s;&|`$()])(?:\.git/|cat\s+.*\.git|tail\s+.*\.git|head\s+.*\.git|ls\s+.*\.git)",
            cmd,
        ):
            deny(
                "STRICT POLICY VIOLATION: Direct git commands and inspecting .git/ directories are strictly prohibited in Autofab workspaces. "
                "Workspace state and submissions are managed exclusively through repository binaries "
                "(bin/check_files, bin/submit, bin/blame). To revert broken edits, use bin/revert."
            )

        # Unzipping runner binaries or inspecting internal tool archives
        if re.search(r"(?:^|[\s;&|`$()])unzip(?:\s|$)", cmd):
            deny(
                "STRICT POLICY VIOLATION: Unzipping runner binaries or inspecting internal tool archives is strictly prohibited. "
                "Consult your companion guide in guides/ for all required structures and conventions."
            )

        # Prohibit ad-hoc python execution, inline scripts, test runners, or typecheckers by worker subagents
        probe_pattern = re.compile(
            r"(?:^|[;&|`()]\s*|\$\(\s*)"
            r"(?:(?:sudo|env|time|nohup)\s+)*"
            r"(?:python[0-9.]*|pytest|pyright|mypy|ruff|ipython|uv\s+run)(?:\.exe)?(?:\s|$)",
            re.IGNORECASE,
        )
        if probe_pattern.search(cmd):
            deny(
                "STRICT POLICY VIOLATION: Role workers are strictly prohibited from executing ad-hoc Python probes, "
                "inline scripts (python -c), test runners (pytest), or typecheckers directly. "
                "Target verification relies exclusively on 'bin/check_files <target>'."
            )

        # Prohibit internal cd navigation
        cd_re = re.compile(
            r"(?:^|[;&|`()]\s*|\$\(\s*)\s*cd(?:\s+([^;&|`$()]+|[\x27\x22][^\x27\x22]+[\x27\x22]))?"
        )
        for m in cd_re.finditer(cmd):
            target = m.group(1)
            if not target:
                deny(
                    f"STRICT BOUNDARY VIOLATION: Subagents are permanently rooted in their workspace directory ('{ws_dir}'). "
                    f"Changing directories (cd) into subdirectories (e.g. guides/) or external paths is strictly prohibited. "
                    f"Run all tools (bin/get_work, bin/check_files, bin/submit) directly from the workspace root."
                )
            clean_target = target.strip().strip("'").strip('"')
            if clean_target in (".", "./"):
                continue
            try:
                target_canonical = os.path.realpath(os.path.abspath(clean_target))
            except Exception:
                target_canonical = ""
            if target_canonical == canonical_ws or clean_target == ws_dir:
                continue
            deny(
                f"STRICT BOUNDARY VIOLATION: Subagents are permanently rooted in their workspace directory ('{ws_dir}'). "
                f"Changing directories (cd) into subdirectories (e.g. guides/) or external paths is strictly prohibited. "
                f"Run all tools (bin/get_work, bin/check_files, bin/submit) directly from the workspace root."
            )

        # Transparent command auto-rooting via overwrite
        pattern_escaped = re.escape(ws_dir)
        canonical_escaped = re.escape(canonical_ws)
        prefix_re = re.compile(
            rf"^\s*cd\s+[\x27\x22]?(?:{pattern_escaped}|{canonical_escaped})[\x27\x22]?\s*&&\s*",
            re.IGNORECASE,
        )
        if not prefix_re.search(cmd):
            new_cmd = f"cd {ws_dir} && ({cmd})"
            allow_overwrite({"CommandLine": new_cmd})
        elif (args.get("CommandLine") or "") != cmd:
            allow_overwrite({"CommandLine": cmd})
        else:
            allow()

    # 3. Path confinement for role workers
    elif name in ("read_file", "write_file", "edit_file", "view_file", "write_to_file", "replace_file_content", "multi_replace_file_content"):
        raw_path = args.get("Path") or args.get("path") or ""
        path = raw_path.strip().strip("'").strip('"')
        path_key = "Path" if "Path" in args else "path"

        # Also normalize Overwrite boolean if passed as a string
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
                deny(
                    f"STRICT BOUNDARY VIOLATION: Access to path '{path}' is strictly prohibited. "
                    f"You are confined exclusively to your assigned role workspace: '{ws_dir}'."
                )

    allow()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"decision": "allow"}))
        sys.exit(0)
