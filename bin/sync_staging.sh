#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d "update_with_ai/parts" ]; then
    echo "Error: update_with_ai/parts directory does not exist." >&2
    exit 1
fi

TARGET_DIRS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --dir=*)
            IFS=',' read -ra DIRS <<< "${1#*=}"
            for d in "${DIRS[@]}"; do
                d="${d#/}"
                d="${d%/}"
                [ -n "$d" ] && TARGET_DIRS+=("$d")
            done
            shift
            ;;
        --dir|-d)
            if [ $# -lt 2 ]; then
                echo "Error: --dir requires a directory name argument" >&2
                exit 1
            fi
            IFS=',' read -ra DIRS <<< "$2"
            for d in "${DIRS[@]}"; do
                d="${d#/}"
                d="${d%/}"
                [ -n "$d" ] && TARGET_DIRS+=("$d")
            done
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--dir=<role>]"
            echo "Copies update_with_ai/parts to staging/parts, updating references."
            echo "If --dir is specified (e.g. --dir=high), only copies and updates files in matching <role> directories under parts."
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--dir=<role>]" >&2
            exit 1
            ;;
    esac
done

if [ ${#TARGET_DIRS[@]} -eq 0 ]; then
    rm -rf staging/parts
    mkdir -p staging/parts
    cp -R update_with_ai/parts/. staging/parts/
else
    found=0
    for d in "${TARGET_DIRS[@]}"; do
        if [[ "$d" == *"/"* ]]; then
            matched_dirs=$(find update_with_ai/parts -type d \( -path "update_with_ai/parts/$d" -o -path "*/$d" \))
        else
            matched_dirs=$(find update_with_ai/parts -type d -name "$d")
        fi
        if [ -n "$matched_dirs" ]; then
            found=1
            while IFS= read -r src_dir; do
                [ -z "$src_dir" ] && continue
                if [[ "$src_dir" != update_with_ai/parts* ]]; then
                    continue
                fi
                rel_path="${src_dir#update_with_ai/}"
                dest_dir="staging/$rel_path"
                if [[ "$dest_dir" != staging/parts* ]]; then
                    echo "Skipping non-parts destination: $dest_dir" >&2
                    continue
                fi
                mkdir -p "$dest_dir"
                cp -R "$src_dir/." "$dest_dir/"
            done <<< "$matched_dirs"
        fi
    done

    if [ "$found" -eq 0 ]; then
        echo "Warning: No directories matching '${TARGET_DIRS[*]}' found in update_with_ai/parts." >&2
    fi
fi

# Clean bytecode caches copied from update_with_ai (only under staging/parts)
find staging/parts -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find staging/parts -name "*.pyc" -delete 2>/dev/null || true

export TARGET_DIRS="${TARGET_DIRS[*]:-}"

python3 - << 'EOF'
import os
import sys

repo_root = os.path.abspath(".")
for p in [
    os.path.join(repo_root, "update_with_ai"),
    os.path.join(repo_root, "update_python_with_ai"),
    os.path.join(repo_root, "update_with_ai", "support", "lib"),
    os.path.join(repo_root, "update_python_with_ai", "support", "lib"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from support.lib import src_metadata

target_dirs_env = os.environ.get("TARGET_DIRS", "").strip()
target_dirs = set(target_dirs_env.split()) if target_dirs_env else set()

for root, dirs, files in os.walk("staging/parts"):
    norm_root = os.path.normpath(root)
    if not norm_root.startswith(os.path.normpath("staging/parts")):
        continue
    if target_dirs:
        parts = set(norm_root.split(os.sep))
        matched = False
        for t in target_dirs:
            if "/" in t:
                if norm_root.endswith(t) or f"{os.sep}{t}{os.sep}" in norm_root or norm_root == t:
                    matched = True
                    break
            elif t in parts:
                matched = True
                break
        if not matched:
            continue

    for file in files:
        path = os.path.join(root, file)
        if file.endswith((".bazel", ".bzl")):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace("//update_with_ai", "//staging")
            new_content = new_content.replace("from update_with_ai.", "from staging.")
            new_content = new_content.replace("import update_with_ai.", "import staging.")
            new_content = new_content.replace("update_with_ai.parts.", "staging.parts.")
            new_content = new_content.replace("update_with_ai.support.", "staging.support.")
            new_content = new_content.replace("os.path.join(_runfiles_root, 'update_with_ai')", "os.path.join(_runfiles_root, 'staging')")
            new_content = new_content.replace("os.path.join(_runfiles_root, \"update_with_ai\")", "os.path.join(_runfiles_root, \"staging\")")
            new_content = new_content.replace("os.path.join(_runfiles_root, '_main', 'update_with_ai')", "os.path.join(_runfiles_root, '_main', 'staging')")
            new_content = new_content.replace("os.path.join(_runfiles_root, \"_main\", \"update_with_ai\")", "os.path.join(_runfiles_root, \"_main\", \"staging\")")
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        elif file.endswith((".py", ".pyi")):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace("from update_with_ai.", "from staging.")
            new_content = new_content.replace("import update_with_ai.", "import staging.")
            new_content = new_content.replace("update_with_ai.parts.", "staging.parts.")
            new_content = new_content.replace("update_with_ai.support.", "staging.support.")
            new_content = new_content.replace("//update_with_ai", "//staging")
            meta = src_metadata.extract_metadata_from_text(new_content, file)
            if meta and meta.code_hash:
                new_hash = src_metadata.compute_code_hash(new_content, file)
                if new_hash != meta.code_hash:
                    new_content = src_metadata.rewrite_metadata_in_text(new_content, file, code_hash=new_hash)
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        elif file.endswith(".sh"):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace("//update_with_ai", "//staging")
            new_content = new_content.replace("/update_with_ai/", "/staging/")
            new_content = new_content.replace("update_with_ai/parts/", "staging/parts/")
            new_content = new_content.replace("update_with_ai/support/", "staging/support/")
            new_content = new_content.replace("update_with_ai/tests/", "staging/tests/")
            new_content = new_content.replace("update_with_ai.parts.", "staging.parts.")
            new_content = new_content.replace("update_with_ai\\.parts\\.", "staging\\.parts\\.")
            new_content = new_content.replace("from update_with_ai.", "from staging.")
            new_content = new_content.replace("import update_with_ai.", "import staging.")
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        elif file.endswith((".proto", ".textproto")):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace("//update_with_ai", "//staging")
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
EOF
