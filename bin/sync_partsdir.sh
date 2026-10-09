#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

POSITIONAL_ARGS=()
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
            echo "Usage: $(basename "$0") <from-parts-dir> <to-parts-dir> [--dir=<role>]"
            echo "Copies <from-parts-dir>/parts to <to-parts-dir>/parts, updating references."
            echo "If --dir is specified (e.g. --dir=high), only copies and updates files in matching <role> directories under parts."
            echo ""
            echo "Shorthands:"
            echo "  bin/sync_staging.sh [--dir=<role>]        (sync update_with_ai -> staging)"
            echo "  bin/sync_update_with_ai.sh [--dir=<role>] (sync staging -> update_with_ai)"
            exit 0
            ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Usage: $(basename "$0") <from-parts-dir> <to-parts-dir> [--dir=<role>]" >&2
            exit 1
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

if [ ${#POSITIONAL_ARGS[@]} -ne 2 ]; then
    echo "Error: Must specify <from-parts-dir> and <to-parts-dir>" >&2
    echo "Usage: $(basename "$0") <from-parts-dir> <to-parts-dir> [--dir=<role>]" >&2
    exit 1
fi

FROM_DIR="${POSITIONAL_ARGS[0]#./}"
FROM_DIR="${FROM_DIR#/}"
FROM_DIR="${FROM_DIR%/}"

TO_DIR="${POSITIONAL_ARGS[1]#./}"
TO_DIR="${TO_DIR#/}"
TO_DIR="${TO_DIR%/}"

if [ ! -d "$FROM_DIR/parts" ]; then
    echo "Error: $FROM_DIR/parts directory does not exist." >&2
    exit 1
fi

copy_tree() {
    local src="$1"
    local dst="$2"
    python3 -B - "$src" "$dst" << 'PYEOF'
import os
import shutil
import sys

src = sys.argv[1]
dst = sys.argv[2]
os.makedirs(dst, exist_ok=True)

for root, dirs, files in os.walk(src):
    dirs[:] = sorted([d for d in dirs if d != "__pycache__"])
    rel = os.path.relpath(root, src)
    target_root = dst if rel == "." else os.path.join(dst, rel)
    if rel != ".":
        os.makedirs(target_root, exist_ok=True)
        print(f"{root} -> {target_root}")
    for f in sorted(files):
        if f.endswith(".pyc") or f == ".DS_Store":
            continue
        src_file = os.path.join(root, f)
        dst_file = os.path.join(target_root, f)
        os.makedirs(target_root, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        print(f"{src_file} -> {dst_file}")
PYEOF
}

if [ ${#TARGET_DIRS[@]} -eq 0 ]; then
    echo "Copying $FROM_DIR/parts -> $TO_DIR/parts"
    rm -rf "$TO_DIR/parts"
    mkdir -p "$TO_DIR/parts"
    copy_tree "$FROM_DIR/parts" "$TO_DIR/parts"
    if [ "$TO_DIR" = "staging" ]; then
        for item in "$TO_DIR"/*; do
            base="$(basename "$item")"
            if [ "$base" != "parts" ] && [ "$base" != "pyproject.toml" ] && [ -e "$item" ]; then
                rm -rf "$item"
            fi
        done
    fi
else
    found=0
    for d in "${TARGET_DIRS[@]}"; do
        if [[ "$d" == *"/"* ]]; then
            matched_dirs=$(find "$FROM_DIR/parts" -type d \( -path "$FROM_DIR/parts/$d" -o -path "*/$d" \))
        else
            matched_dirs=$(find "$FROM_DIR/parts" -type d -name "$d")
        fi
        if [ -n "$matched_dirs" ]; then
            found=1
            while IFS= read -r src_dir; do
                [ -z "$src_dir" ] && continue
                if [[ "$src_dir" != "$FROM_DIR/parts"* ]]; then
                    continue
                fi
                rel_path="${src_dir#$FROM_DIR/}"
                dest_dir="$TO_DIR/$rel_path"
                if [[ "$dest_dir" != "$TO_DIR/parts"* ]]; then
                    echo "Skipping non-parts destination: $dest_dir" >&2
                    continue
                fi
                echo "Copying $src_dir -> $dest_dir"
                mkdir -p "$dest_dir"
                copy_tree "$src_dir" "$dest_dir"
            done <<< "$matched_dirs"
        fi
    done

    if [ "$found" -eq 0 ]; then
        echo "Warning: No directories matching '${TARGET_DIRS[*]}' found in $FROM_DIR/parts." >&2
    fi
fi

# Clean bytecode caches and OS files copied from $FROM_DIR (only under $TO_DIR/parts)
find "$TO_DIR/parts" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$TO_DIR/parts" -name "*.pyc" -delete 2>/dev/null || true
find "$TO_DIR/parts" -name ".DS_Store" -delete 2>/dev/null || true

export TARGET_DIRS="${TARGET_DIRS[*]:-}"
export FROM_DIR="$FROM_DIR"
export TO_DIR="$TO_DIR"

python3 -B - << 'EOF'
import os
import sys

from_dir = os.environ["FROM_DIR"].strip()
to_dir = os.environ["TO_DIR"].strip()

repo_root = os.path.abspath(".")
for p in [
    repo_root,
    os.path.join(repo_root, "update_with_ai"),
    os.path.join(repo_root, "update_python_with_ai"),
    os.path.join(repo_root, "update_with_ai", "support", "lib"),
    os.path.join(repo_root, "update_python_with_ai", "support", "lib"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from update_with_ai.parts.control.lib import src_metadata

target_dirs_env = os.environ.get("TARGET_DIRS", "").strip()
target_dirs = set(target_dirs_env.split()) if target_dirs_env else set()

to_parts_dir = os.path.join(to_dir, "parts")

for root, dirs, files in os.walk(to_parts_dir):
    norm_root = os.path.normpath(root)
    if not norm_root.startswith(os.path.normpath(to_parts_dir)):
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
            new_content = content.replace(f"//{from_dir}/parts", f"//{to_dir}/parts")
            new_content = new_content.replace(f"from {from_dir}.parts.", f"from {to_dir}.parts.")
            new_content = new_content.replace(f"import {from_dir}.parts.", f"import {to_dir}.parts.")
            new_content = new_content.replace(f"{from_dir}.parts.", f"{to_dir}.parts.")
            if from_dir == "staging":
                new_content = new_content.replace("//staging/support", "//update_with_ai/support")
                new_content = new_content.replace("staging.support.", "update_with_ai.support.")
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        elif file.endswith((".py", ".pyi")):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace(f"from {from_dir}.parts.", f"from {to_dir}.parts.")
            new_content = new_content.replace(f"import {from_dir}.parts.", f"import {to_dir}.parts.")
            new_content = new_content.replace(f"{from_dir}.parts.", f"{to_dir}.parts.")
            if from_dir == "staging":
                new_content = new_content.replace("from staging.support.", "from update_with_ai.support.")
                new_content = new_content.replace("import staging.support.", "import update_with_ai.support.")
                new_content = new_content.replace("staging.support.", "update_with_ai.support.")
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
            new_content = content.replace(f"//{from_dir}/parts", f"//{to_dir}/parts")
            new_content = new_content.replace(f"/{from_dir}/parts/", f"/{to_dir}/parts/")
            new_content = new_content.replace(f"{from_dir}/parts/", f"{to_dir}/parts/")
            new_content = new_content.replace(f"{from_dir}.parts.", f"{to_dir}.parts.")
            new_content = new_content.replace(f"{from_dir}\\.parts\\.", f"{to_dir}\\.parts\\.")
            new_content = new_content.replace(f"from {from_dir}.parts.", f"from {to_dir}.parts.")
            new_content = new_content.replace(f"import {from_dir}.parts.", f"import {to_dir}.parts.")
            if from_dir == "staging":
                new_content = new_content.replace("//staging/support", "//update_with_ai/support")
                new_content = new_content.replace("/staging/support/", "/update_with_ai/support/")
                new_content = new_content.replace("staging/support/", "update_with_ai/support/")
                new_content = new_content.replace("staging.support.", "update_with_ai.support.")
                new_content = new_content.replace("from staging.support.", "from update_with_ai.support.")
                new_content = new_content.replace("import staging.support.", "import update_with_ai.support.")
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        elif file.endswith((".proto", ".textproto")):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace(f"//{from_dir}/parts", f"//{to_dir}/parts")
EOF

find "$TO_DIR/parts" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$TO_DIR/parts" -name "*.pyc" -delete 2>/dev/null || true

