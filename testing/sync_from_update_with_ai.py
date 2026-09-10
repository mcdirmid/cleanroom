#!/usr/bin/env python3
"""Sync update_with_ai directories and specs BUILD.bazel into testing/.

Copies:
    update_with_ai/specs/high        -> testing/specs/high
    update_with_ai/specs/grounding   -> testing/specs/grounding
    update_with_ai/specs/BUILD.bazel -> testing/specs/BUILD.bazel
    update_with_ai/lib               -> testing/lib
    update_with_ai/tests             -> testing/tests

Performs string replacements:
    - In BUILD.bazel and .bzl files: '//update_with_ai/{lib,specs,tests}' -> '//testing/{lib,specs,tests}'
    - In .py/.pyi files: 'update_with_ai.{lib,tests}' -> 'testing.{lib,tests}'
"""

import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    workspace_root = Path(__file__).resolve().parent.parent
    src_root = workspace_root / "update_with_ai"
    dest_root = workspace_root / "testing"

    if not src_root.is_dir():
        print(f"Error: Source directory {src_root} not found.", file=sys.stderr)
        return 1

    sync_targets = [
        ("specs/high", "specs/high"),
        ("specs/grounding", "specs/grounding"),
        ("specs/BUILD.bazel", "specs/BUILD.bazel"),
        ("lib", "lib"),
        ("tests", "tests"),
    ]

    for src_rel, dest_rel in sync_targets:
        src_path = src_root / src_rel
        if not src_path.exists() and src_rel == "tests" and (src_root / "test").exists():
            src_path = src_root / "test"

        dest_path = dest_root / dest_rel

        if not src_path.exists():
            print(f"Warning: {src_path} does not exist, skipping.", file=sys.stderr)
            continue

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_file():
            if dest_path.is_dir():
                shutil.rmtree(dest_path)
            shutil.copy2(src_path, dest_path)
        else:
            if dest_path.is_dir():
                shutil.rmtree(dest_path)
            elif dest_path.is_file():
                dest_path.unlink()
            shutil.copytree(
                src_path,
                dest_path,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store"),
            )
        print(f"Copied {src_path.relative_to(workspace_root)} -> {dest_path.relative_to(workspace_root)}")

    # Clean up any stale directories under dest_root/specs (e.g. obsolete 'low')
    stale_low = dest_root / "specs" / "low"
    if stale_low.exists():
        shutil.rmtree(stale_low)

    # Perform text replacements across copied files
    for root, _dirs, files in os.walk(dest_root):
        for filename in files:
            filepath = Path(root) / filename
            if filepath == Path(__file__).resolve():
                continue

            if filename.endswith(".pyc") or filename == ".DS_Store":
                continue

            try:
                content = filepath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            modified = False

            if filename == "BUILD.bazel" or filename.endswith(".bzl") or filename.endswith(".bazel"):
                for synced in ("lib", "specs", "tests"):
                    src_label = f"//update_with_ai/{synced}"
                    dest_label = f"//testing/{synced}"
                    if src_label in content:
                        content = content.replace(src_label, dest_label)
                        modified = True

            if filename.endswith(".py") or filename.endswith(".pyi"):
                for synced in ("lib", "tests"):
                    src_mod = f"update_with_ai.{synced}"
                    dest_mod = f"testing.{synced}"
                    if src_mod in content:
                        content = content.replace(src_mod, dest_mod)
                        modified = True

                for synced in ("lib", "specs", "tests"):
                    src_label = f"//update_with_ai/{synced}"
                    dest_label = f"//testing/{synced}"
                    if src_label in content:
                        content = content.replace(src_label, dest_label)
                        modified = True

            if modified:
                filepath.write_text(content, encoding="utf-8")

    print("Sync complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
