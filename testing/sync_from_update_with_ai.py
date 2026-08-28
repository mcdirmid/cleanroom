#!/usr/bin/env python3
"""Sync update_with_ai directories (lib, specs, tests) into testing/.

Copies:
    update_with_ai/lib   -> testing/lib
    update_with_ai/specs -> testing/specs
    update_with_ai/tests -> testing/tests

Performs string replacements:
    - In BUILD.bazel and .bzl files: '//update_with_ai' -> '//testing'
    - In .py files: 'update_with_ai.' -> 'testing.'
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

    directories = ["lib", "specs", "tests"]

    for d in directories:
        src_dir = src_root / d
        dest_dir = dest_root / d

        if not src_dir.exists():
            print(f"Warning: {src_dir} does not exist, skipping.", file=sys.stderr)
            continue

        if dest_dir.exists():
            shutil.rmtree(dest_dir)

        shutil.copytree(
            src_dir,
            dest_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store"),
        )
        print(f"Copied {src_dir.relative_to(workspace_root)} -> {dest_dir.relative_to(workspace_root)}")

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
                if "//update_with_ai" in content:
                    content = content.replace("//update_with_ai", "//testing")
                    modified = True

            if filename.endswith(".py"):
                if "update_with_ai." in content:
                    content = content.replace("update_with_ai.", "testing.")
                    modified = True
                if "//update_with_ai" in content:
                    content = content.replace("//update_with_ai", "//testing")
                    modified = True

            if modified:
                filepath.write_text(content, encoding="utf-8")

    print("Sync complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
