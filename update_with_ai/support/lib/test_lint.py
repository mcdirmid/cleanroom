#!/usr/bin/env python3
"""test_lint.py — maintain a module's pyright_test BUILD entry.

Usage: test_lint.py <BUILD.bazel> <module_test.py> [--deps dep1,dep2,...]

Same fix semantics as lib_lint.py, for the pyright_test rule: creates the
BUILD file when missing, adds the pyright load statement when missing, adds
the pyright_test target when missing, and adds any missing pyright_deps
(add-only). The expected deps are the spec-graph-derived module names — the
implementation module under test plus the module names of the spec's
module_deps — plus the transitive closure of the test's imports into the lib
package: pyright must resolve every lib module the test imports, directly or
transitively.
"""

import argparse
import os
import re
import sys

from build_lint_common import (
    build_module_resolution_map,
    check_syntax,
    check_test_dry_run,
    check_test_impl_imports,
    check_test_imports,
    check_test_mocks,
    check_test_structure,
    check_undeclared_imports,
    strip_dependency_header,
    ensure_load,
    ensure_target,
    extract_target_pyright_deps,
    load_line,
    local_imports,
    module_file,
    module_stem,
    package_of,
    parse_dependency_header,
    parse_pyi_dependencies,
    read_text,
    rewrite_test_imports,
    transitive_closure,
    write_text,
)

RULE = "pyright_test"


def main() -> int:
    ap = argparse.ArgumentParser(description="Maintain a pyright_test BUILD entry.")
    ap.add_argument("build_path", help="path to the package's BUILD.bazel file")
    ap.add_argument("module_path", help="path to the test module the entry is for")
    ap.add_argument(
        "--deps",
        default="",
        help="comma-separated expected pyright_deps module names (spec-derived)",
    )
    ap.add_argument(
        "--lib-pkg",
        required=True,
        help="the Bazel package holding the modules' pyright_library targets "
        "(the lib package one level up; pyright_deps are written against it)",
    )
    ap.add_argument(
        "--pyi",
        default="",
        help="path to the grounding specification .pyi file",
    )
    args = ap.parse_args()

    package = package_of(args.build_path)
    stem = module_stem(args.module_path)
    srcs = module_file(args.module_path)
    deps = [d for d in args.deps.split(",") if d and not d.endswith("_ext")]

    impl_stem = stem[:-5] if stem.endswith("_test") else stem
    allowed_deps: set[str] = {impl_stem}

    for d in deps:
        m = re.search(r'requirement\(["\']([^"\']+)["\']\)', d)
        if m:
            allowed_deps.add(m.group(1))
        elif ":" in d:
            allowed_deps.add(d.split(":")[-1])
        elif d and not d.startswith("//"):
            allowed_deps.add(d)

    pyi_path = args.pyi
    if not pyi_path or not os.path.isfile(pyi_path):
        inferred = os.path.join(
            os.path.dirname(args.lib_pkg.rstrip("/")), "grounding", f"{impl_stem}.pyi"
        )
        if os.path.isfile(inferred):
            pyi_path = inferred

    if pyi_path and os.path.isfile(pyi_path):
        for d in parse_pyi_dependencies(pyi_path):
            allowed_deps.add(d)

    for d in extract_target_pyright_deps(args.build_path, RULE, stem):
        allowed_deps.add(d.split(":")[-1])

    if os.path.exists(args.module_path):
        parsed = parse_dependency_header(read_text(args.module_path))
        if parsed is not None:
            for d in parsed:
                allowed_deps.add(d)

    if os.path.exists(args.module_path):
        strip_dependency_header(args.module_path)

    # Build resolution map and rewrite test module imports if test module exists
    import_map, label_map, _ = build_module_resolution_map(
        args.build_path, args.lib_pkg, deps
    )
    if os.path.exists(args.module_path):
        _, imported_stems = rewrite_test_imports(args.module_path, import_map)
        for s in imported_stems:
            if s in label_map and label_map[s] not in deps:
                deps.append(label_map[s])

    if not os.path.exists(args.build_path):
        d = os.path.dirname(args.build_path)
        if d:
            os.makedirs(d, exist_ok=True)
        header = "# " + (package + "/BUILD.bazel" if package else "BUILD.bazel") + "\n"
        write_text(args.build_path, header + load_line(["pyright_test"]) + "\n")
    text = read_text(args.build_path)
    text = ensure_load(text, ["pyright_test"])
    # pyright_deps cover the spec-derived deps plus the transitive closure
    # of the test's imports into the lib package: pyright must resolve
    # every lib module the test imports, directly or transitively.
    roots = sorted(set(deps + local_imports(args.lib_pkg, args.module_path)))
    deps = transitive_closure(args.lib_pkg, roots)
    text = ensure_target(text, RULE, stem, srcs, deps, args.lib_pkg)
    write_text(args.build_path, text)

    if os.path.exists(args.module_path):
        syntax_errors = check_syntax(args.module_path)
        if syntax_errors:
            for err in syntax_errors:
                sys.stderr.write(err + "\n")
            return 1
        module_text = read_text(args.module_path)
        if "unittest.main()" not in module_text:
            sys.stderr.write(
                f"{args.module_path}: error: test module must end with 'if __name__ == \"__main__\": unittest.main()'\n"
            )
            return 1
        undeclared_errors = check_undeclared_imports(
            args.module_path,
            sorted(allowed_deps),
            extra_allowed=[impl_stem],
        )
        all_errors = (
            check_test_imports(args.lib_pkg, args.module_path)
            + check_test_impl_imports(args.lib_pkg, args.module_path)
            + check_test_mocks(args.module_path)
            + check_test_structure(args.module_path)
            + undeclared_errors
        )
        if all_errors:
            for err in all_errors:
                sys.stderr.write(err + "\n")
            return 1

        dry_run_errors = check_test_dry_run(args.lib_pkg, args.module_path)
        if dry_run_errors:
            for err in dry_run_errors:
                sys.stderr.write(err + "\n")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
