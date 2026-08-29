#!/usr/bin/env python3
"""lib_lint.py — maintain a module's pyright_library BUILD entry.

Usage: lib_lint.py <BUILD.bazel> <module.py> [--deps dep1,dep2,...]

Fixes (idempotent, add-only):
  - creates the BUILD file when it does not exist (load statement included),
  - adds the pyright load statement when missing,
  - adds the pyright_library target when missing,
  - adds any missing pyright_deps (existing entries are left in place).

The expected pyright_deps are the spec-graph-derived module names passed via
--deps (the module names corresponding to the spec's module_deps) plus the
transitive closure of the module's sibling imports: pyright must resolve
every module the target's files import, directly or transitively.
Exits 0 when the BUILD entry is maintained; exits 1 on unexpected errors.
"""

import argparse
import os
import sys

from build_lint_common import (
    check_sibling_imports,
    ensure_load,
    ensure_target,
    load_line,
    local_imports,
    module_file,
    module_stem,
    package_of,
    read_text,
    transitive_closure,
    write_text,
)

RULE = "pyright_library"


def main() -> int:
    ap = argparse.ArgumentParser(description="Maintain a pyright_library BUILD entry.")
    ap.add_argument("build_path", help="path to the package's BUILD.bazel file")
    ap.add_argument("module_path", help="path to the module the entry is for")
    ap.add_argument(
        "--deps",
        default="",
        help="comma-separated expected pyright_deps module names (spec-derived)",
    )
    args = ap.parse_args()

    package = package_of(args.build_path)
    stem = module_stem(args.module_path)
    srcs = module_file(args.module_path)
    deps = [d for d in args.deps.split(",") if d]

    if not os.path.exists(args.build_path):
        d = os.path.dirname(args.build_path)
        if d:
            os.makedirs(d, exist_ok=True)
        header = "# " + (package + "/BUILD.bazel" if package else "BUILD.bazel") + "\n"
        write_text(args.build_path, header + load_line(["pyright_library"]) + "\n")
    text = read_text(args.build_path)
    text = ensure_load(text, ["pyright_library"])
    # pyright_deps cover the spec-derived deps plus the transitive closure
    # of sibling-module imports: pyright must resolve every module the
    # target's files import, directly or transitively.
    roots = sorted(set(deps + local_imports(package, args.module_path)))
    deps = transitive_closure(package, roots)
    text = ensure_target(text, RULE, stem, srcs, deps, package)
    write_text(args.build_path, text)

    import_errors = check_sibling_imports(package, args.module_path)
    if import_errors:
        for err in import_errors:
            sys.stderr.write(err + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
