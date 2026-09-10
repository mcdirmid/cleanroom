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
    check_dataclass_stubs,
    check_exception_eating,
    check_framework_imports,
    check_impl_imports,
    check_lib_structure,
    check_sibling_imports,
    check_syntax,
    check_type_ignore,
    ensure_load,
    ensure_pip_load,
    ensure_target,
    load_line,
    local_imports,
    module_file,
    module_stem,
    package_of,
    parse_spec_build_dependencies,
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
    ap.add_argument(
        "--pyi-deps",
        default="",
        help="comma-separated paths to dependent .pyi specification files",
    )
    args = ap.parse_args()

    syntax_errors = check_syntax(args.module_path)
    if syntax_errors:
        for err in syntax_errors:
            sys.stderr.write(err + "\n")
        return 1

    package = package_of(args.build_path)
    stem = module_stem(args.module_path)
    srcs = module_file(args.module_path)
    raw_deps = [d for d in args.deps.split(",") if d]
    pyi_paths = [p for p in args.pyi_deps.split(",") if p]

    # Separate library dependencies from external specification dependencies
    lib_deps: list[str] = []
    for d in raw_deps:
        if d.endswith("_ext"):
            # External specification dependency: find its .pyi file
            candidates = [
                p for p in pyi_paths if os.path.splitext(os.path.basename(p))[0] == d
            ]
            if not candidates:
                spec_file = f"{d}.pyi"
                build_dir = os.path.dirname(args.build_path)
                for search_dir in [
                    os.path.join(build_dir, "..", "specs", "grounding"),
                    "update_with_ai/specs/grounding",
                    "specs/grounding",
                ]:
                    candidate = os.path.join(search_dir, spec_file)
                    if os.path.isfile(candidate):
                        pyi_paths.append(candidate)
                        break
        else:
            lib_deps.append(d)

    # Collect build dependencies from all dependent .pyi files
    target_deps: list[str] = []
    for p in pyi_paths:
        for dep_expr in parse_spec_build_dependencies(p):
            if dep_expr not in target_deps:
                target_deps.append(dep_expr)

    has_pip_req = any(d.startswith("requirement(") for d in target_deps)

    if not os.path.exists(args.build_path):
        d = os.path.dirname(args.build_path)
        if d:
            os.makedirs(d, exist_ok=True)
        header = "# " + (package + "/BUILD.bazel" if package else "BUILD.bazel") + "\n"
        loads = load_line(["pyright_library"])
        if has_pip_req:
            loads += '\nload("@pip//:requirements.bzl", "requirement")'
        write_text(args.build_path, header + loads + "\n")
    text = read_text(args.build_path)
    text = ensure_load(text, ["pyright_library"])
    if has_pip_req:
        text = ensure_pip_load(text)
    # pyright_deps cover the spec-derived deps plus the transitive closure
    # of sibling-module imports: pyright must resolve every module the
    # target's files import, directly or transitively.
    roots = sorted(set(lib_deps + local_imports(package, args.module_path)))
    deps = transitive_closure(package, roots)
    text = ensure_target(text, RULE, stem, srcs, deps, package, target_deps=target_deps)
    write_text(args.build_path, text)

    structure_errors = check_lib_structure(args.module_path)
    import_errors = check_sibling_imports(package, args.module_path)
    impl_errors = check_impl_imports(args.module_path)
    exception_errors = check_exception_eating(args.module_path)
    framework_errors = check_framework_imports(args.module_path)
    dataclass_errors = check_dataclass_stubs(args.module_path)
    type_ignore_errors = check_type_ignore(args.module_path)
    all_errors = (
        structure_errors
        + import_errors
        + impl_errors
        + exception_errors
        + framework_errors
        + dataclass_errors
        + type_ignore_errors
    )
    if all_errors:
        for err in all_errors:
            sys.stderr.write(err + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
