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

TARGET_DIRS_JOINED="${TARGET_DIRS[*]:-}"
unset TARGET_DIRS
export TARGET_DIRS="$TARGET_DIRS_JOINED"
export FROM_DIR="$FROM_DIR"
export TO_DIR="$TO_DIR"

python3 -B - << 'EOF'
import os
import shutil
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

try:
    from update_with_ai.parts.control.lib import src_metadata
except ImportError:
    try:
        from update_python_with_ai.parts.control.lib import src_metadata
    except ImportError:
        src_metadata = None

target_dirs_env = os.environ.get("TARGET_DIRS", "").strip()
target_dirs = set(target_dirs_env.split()) if target_dirs_env else set()

from_parts_dir = os.path.join(from_dir, "parts")
to_parts_dir = os.path.join(to_dir, "parts")
os.makedirs(to_parts_dir, exist_ok=True)

if os.path.basename(to_dir) == "staging" and not target_dirs:
    if os.path.isdir(to_dir):
        for item in os.listdir(to_dir):
            if item not in ("parts", "pyproject.toml"):
                p = os.path.join(to_dir, item)
                if os.path.isdir(p):
                    shutil.rmtree(p)
                elif os.path.exists(p):
                    os.remove(p)

def transform_content(filename: str, content: str, from_d: str, to_d: str) -> str:
    from_pkg = os.path.basename(from_d)
    to_pkg = os.path.basename(to_d)
    if filename.endswith((".bazel", ".bzl")):
        new_content = content.replace(f"//{from_d}/parts", f"//{to_d}/parts")
        if from_pkg != from_d or to_pkg != to_d:
            new_content = new_content.replace(f"//{from_pkg}/parts", f"//{to_pkg}/parts")
        new_content = new_content.replace(f"from {from_pkg}.parts.", f"from {to_pkg}.parts.")
        new_content = new_content.replace(f"import {from_pkg}.parts.", f"import {to_pkg}.parts.")
        new_content = new_content.replace(f"{from_pkg}.parts.", f"{to_pkg}.parts.")
        if from_pkg == "staging":
            new_content = new_content.replace("//staging/support", "//update_with_ai/support")
            new_content = new_content.replace("staging.support.", "update_with_ai.support.")
        return new_content
    elif filename.endswith((".py", ".pyi")):
        new_content = content.replace(f"from {from_pkg}.parts.", f"from {to_pkg}.parts.")
        new_content = new_content.replace(f"import {from_pkg}.parts.", f"import {to_pkg}.parts.")
        new_content = new_content.replace(f"{from_pkg}.parts.", f"{to_pkg}.parts.")
        if from_pkg == "staging":
            new_content = new_content.replace("from staging.support.", "from update_with_ai.support.")
            new_content = new_content.replace("import staging.support.", "import update_with_ai.support.")
            new_content = new_content.replace("staging.support.", "update_with_ai.support.")
        if src_metadata:
            meta = src_metadata.extract_metadata_from_text(new_content, filename)
            if meta and meta.code_hash:
                new_hash = src_metadata.compute_code_hash(new_content, filename)
                if new_hash != meta.code_hash:
                    new_content = src_metadata.rewrite_metadata_in_text(new_content, filename, code_hash=new_hash)
        return new_content
    elif filename.endswith(".sh"):
        new_content = content.replace(f"//{from_d}/parts", f"//{to_d}/parts")
        if from_pkg != from_d or to_pkg != to_d:
            new_content = new_content.replace(f"//{from_pkg}/parts", f"//{to_pkg}/parts")
        new_content = new_content.replace(f"/{from_d}/parts/", f"/{to_d}/parts/")
        if from_pkg != from_d or to_pkg != to_d:
            new_content = new_content.replace(f"/{from_pkg}/parts/", f"/{to_pkg}/parts/")
        new_content = new_content.replace(f"{from_d}/parts/", f"{to_d}/parts/")
        if from_pkg != from_d or to_pkg != to_d:
            new_content = new_content.replace(f"{from_pkg}/parts/", f"{to_pkg}/parts/")
        new_content = new_content.replace(f"{from_pkg}.parts.", f"{to_pkg}.parts.")
        new_content = new_content.replace(f"{from_pkg}\\.parts\\.", f"{to_pkg}\\.parts\\.")
        new_content = new_content.replace(f"from {from_pkg}.parts.", f"from {to_pkg}.parts.")
        new_content = new_content.replace(f"import {from_pkg}.parts.", f"import {to_pkg}.parts.")
        if from_pkg == "staging":
            new_content = new_content.replace("//staging/support", "//update_with_ai/support")
            new_content = new_content.replace("/staging/support/", "/update_with_ai/support/")
            new_content = new_content.replace("staging/support/", "update_with_ai/support/")
            new_content = new_content.replace("staging.support.", "update_with_ai.support.")
            new_content = new_content.replace("from staging.support.", "from update_with_ai.support.")
            new_content = new_content.replace("import staging.support.", "import update_with_ai.support.")
        return new_content
    elif filename.endswith((".proto", ".textproto")):
        new_content = content.replace(f"//{from_d}/parts", f"//{to_d}/parts")
        if from_pkg != from_d or to_pkg != to_d:
            new_content = new_content.replace(f"//{from_pkg}/parts", f"//{to_pkg}/parts")
        return new_content
    return content

def dir_matches(rel_path: str, targets: set) -> bool:
    if not targets:
        return True
    path_parts = set(rel_path.split(os.sep))
    norm_rel = os.path.normpath(rel_path)
    for t in targets:
        norm_t = os.path.normpath(t)
        if "/" in t:
            if norm_rel == norm_t or norm_rel.startswith(norm_t + os.sep) or norm_rel.endswith(norm_t) or f"{os.sep}{norm_t}{os.sep}" in norm_rel:
                return True
        elif t in path_parts:
            return True
    return False

TRANSFORM_EXTS = (".bazel", ".bzl", ".py", ".pyi", ".sh", ".proto", ".textproto")

matched_any = False
synced_files = set()

for root, dirs, files in os.walk(from_parts_dir):
    dirs[:] = sorted([d for d in dirs if d != "__pycache__"])
    rel_root = os.path.relpath(root, from_parts_dir)
    if target_dirs:
        if not dir_matches(rel_root, target_dirs):
            continue
        matched_any = True

    target_root = to_parts_dir if rel_root == "." else os.path.join(to_parts_dir, rel_root)
    os.makedirs(target_root, exist_ok=True)

    for f in sorted(files):
        if f.endswith(".pyc") or f == ".DS_Store":
            continue
        src_file = os.path.join(root, f)
        dst_file = os.path.join(target_root, f)
        synced_files.add(os.path.normpath(dst_file))

        if f.endswith(TRANSFORM_EXTS):
            try:
                with open(src_file, "r", encoding="utf-8") as fp:
                    src_content = fp.read()
                transformed = transform_content(f, src_content, from_dir, to_dir)
            except UnicodeDecodeError:
                transformed = None

            if transformed is not None:
                is_different = True
                if os.path.isfile(dst_file):
                    try:
                        with open(dst_file, "r", encoding="utf-8") as fp:
                            dst_content = fp.read()
                        if dst_content == transformed:
                            is_different = False
                    except UnicodeDecodeError:
                        is_different = True

                if is_different:
                    os.makedirs(target_root, exist_ok=True)
                    with open(dst_file, "w", encoding="utf-8") as fp:
                        fp.write(transformed)
                    shutil.copymode(src_file, dst_file)
                    print(f"{src_file} -> {dst_file}")
                continue

        # Binary or non-transformable file
        with open(src_file, "rb") as fp:
            src_bytes = fp.read()

        is_different = True
        if os.path.isfile(dst_file):
            with open(dst_file, "rb") as fp:
                dst_bytes = fp.read()
            if dst_bytes == src_bytes:
                is_different = False

        if is_different:
            os.makedirs(target_root, exist_ok=True)
            with open(dst_file, "wb") as fp:
                fp.write(src_bytes)
            shutil.copymode(src_file, dst_file)
            print(f"{src_file} -> {dst_file}")

if target_dirs and not matched_any:
    print(f"Warning: No directories matching '{' '.join(sorted(target_dirs))}' found in {from_dir}/parts.", file=sys.stderr)

# Prune orphaned files
if not target_dirs:
    for root, dirs, files in os.walk(to_parts_dir, topdown=False):
        for f in files:
            if f.endswith(".pyc") or f == ".DS_Store":
                continue
            dst_file = os.path.normpath(os.path.join(root, f))
            if dst_file not in synced_files:
                os.remove(dst_file)
        if not os.listdir(root):
            try:
                os.rmdir(root)
            except OSError:
                pass
else:
    for root, dirs, files in os.walk(to_parts_dir, topdown=False):
        rel_root = os.path.relpath(root, to_parts_dir)
        if dir_matches(rel_root, target_dirs):
            for f in files:
                if f.endswith(".pyc") or f == ".DS_Store":
                    continue
                dst_file = os.path.normpath(os.path.join(root, f))
                if dst_file not in synced_files:
                    os.remove(dst_file)
            if not os.listdir(root):
                try:
                    os.rmdir(root)
                except OSError:
                    pass
EOF

find "$TO_DIR/parts" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$TO_DIR/parts" -name "*.pyc" -delete 2>/dev/null || true
find "$TO_DIR/parts" -name ".DS_Store" -delete 2>/dev/null || true


