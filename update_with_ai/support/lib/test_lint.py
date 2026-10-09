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
import ast
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_lint_common import (
    _parse_build_targets,
    build_module_resolution_map,
    compute_allowed_spec_deps,
    compute_test_derived_info,
    check_syntax,
    check_test_dry_run,
    check_test_impl_imports,
    check_test_imports,
    check_test_mocks,
    check_test_structure,
    check_undeclared_imports,

    ensure_load,
    ensure_pip_load,
    ensure_target,
    extract_imported_stems,
    extract_target_pyright_deps,
    find_spec_pyi,
    load_line,
    local_imports,
    module_file,
    module_stem,
    package_of,
    parse_dependency_header,
    parse_package_build_dependencies,
    parse_pyi_dependencies,
    parse_spec_build_dependencies,
    parse_targets_by_rule,
    read_text,
    rewrite_test_imports,
    strip_dependency_header,
    transitive_closure,
    write_text,
)

RULE = "pyright_test"


def is_uninitialized_test_module(content: str) -> bool:
    stripped = content.strip()
    if not stripped:
        return True
    if "<TargetClass>" in content or "<target_impl>" in content:
        return True
    try:
        tree = ast.parse(content)
        test_classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        test_methods: list[ast.AST] = []
        for cls in test_classes:
            for item in cls.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and item.name.startswith("test_"):
                    test_methods.append(item)
        if not test_classes or not test_methods:
            return True
    except SyntaxError:
        if "<" in content and ">" in content:
            return True
    return False


def extract_requirements_from_pyi(
    pyi_path: str, visited: set[str] | None = None
) -> list[str]:
    if visited is None:
        visited = set()
    norm = os.path.abspath(pyi_path)
    if norm in visited:
        return []
    visited.add(norm)

    try:
        with open(pyi_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=pyi_path)
    except (OSError, SyntaxError):
        return []

    docstrings: list[str] = []
    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        docstrings.append(mod_doc)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc:
                docstrings.append(doc)

    requirements: list[str] = []
    seen: set[str] = set()

    for doc in docstrings:
        current_section = None
        for line in doc.splitlines():
            stripped = line.strip()
            if stripped in (
                "FRESH_REQUIREMENTS:",
                "REQUIREMENTS:",
                "PROSE_REQUIREMENTS:",
            ):
                current_section = "FRESH_REQUIREMENTS"
                continue
            elif stripped == "INHERITED_REQUIREMENTS:":
                current_section = "INHERITED_REQUIREMENTS"
                continue
            elif stripped.endswith(":") and not stripped.startswith("-"):
                current_section = None
                continue

            if current_section in ("FRESH_REQUIREMENTS", "INHERITED_REQUIREMENTS"):
                if stripped.startswith("- "):
                    item = stripped[2:].strip()
                    if item and item not in seen:
                        seen.add(item)
                        requirements.append(item)
                elif stripped.startswith("-"):
                    item = stripped[1:].strip()
                    if item and item not in seen:
                        seen.add(item)
                        requirements.append(item)

    # Transitive inheritance for new specification format:
    # If this is an _impl.pyi, also inspect sibling interface .pyi and imported local .pyi files
    dir_name = os.path.dirname(pyi_path)
    base_name = os.path.basename(pyi_path)
    if base_name.endswith("_impl.pyi"):
        iface_path = os.path.join(dir_name, base_name[:-9] + ".pyi")
        if os.path.isfile(iface_path):
            for req in extract_requirements_from_pyi(iface_path, visited):
                if req not in seen:
                    seen.add(req)
                    requirements.append(req)

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            mod_target = node.module
            if mod_target:
                target_stem = mod_target.split(".")[-1]
                imported_pyi = os.path.join(dir_name, f"{target_stem}.pyi")
                if os.path.isfile(imported_pyi):
                    for req in extract_requirements_from_pyi(imported_pyi, visited):
                        if req not in seen:
                            seen.add(req)
                            requirements.append(req)

    return requirements


def generate_test_skeleton(
    pyi_path: str, stem: str, impl_stem: str, lib_pkg: str
) -> str:
    if not impl_stem.endswith("_impl"):
        return ""
    try:
        with open(pyi_path, "r", encoding="utf-8") as f:
            pyi_content = f.read()
        tree = ast.parse(pyi_content, filename=pyi_path)
    except (OSError, SyntaxError):
        tree = ast.Module(body=[], type_ignores=[])

    impl_classes: list[str] = []
    has_singleton = False
    is_impl = impl_stem.endswith("_impl")

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            impl_classes.append(node.name)
            for dec in node.decorator_list:
                dec_name = None
                if isinstance(dec, ast.Name):
                    dec_name = dec.id
                elif isinstance(dec, ast.Attribute):
                    dec_name = dec.attr
                elif isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        dec_name = dec.func.id
                    elif isinstance(dec.func, ast.Attribute):
                        dec_name = dec.func.attr
                if dec_name == "singleton_type":
                    has_singleton = True

    reqs = extract_requirements_from_pyi(pyi_path)

    test_cls_name = "".join(part.capitalize() for part in impl_stem.split("_")) + "Test"

    lines: list[str] = [
        f'"""Unit tests for {impl_stem} per its grounding specification."""',
        "",
        "from __future__ import annotations",
        "",
        "import unittest",
    ]
    if is_impl or has_singleton:
        lines.append("from support.lib.lifecycle import LifecycleRegistry, enter_phase")

    if impl_classes:
        lines.append(f"from lib.{impl_stem} import (")
        for c in sorted(impl_classes):
            lines.append(f"    {c},")
        if is_impl:
            lines.append("    __initialize__,")
        lines.append(")")
    elif is_impl:
        lines.append(f"from lib.{impl_stem} import __initialize__")

    lines.append("")
    lines.append(f"class {test_cls_name}(unittest.TestCase):")
    if is_impl or has_singleton:
        lines.append("    def setUp(self) -> None:")
        lines.append("        self.registry = LifecycleRegistry()")
        lines.append("        __initialize__(self.registry)")
        lines.append("")
        lines.append("    def test_initialization(self) -> None:")
        lines.append('        """CUJ: Verify initial component presence."""')
        lines.append("        self.assertIsNotNone(self.registry)")
        if impl_classes:
            classes_str = ", ".join(sorted(impl_classes))
            lines.append(f"        for cls in [{classes_str}]:")
            lines.append("            self.assertIsNotNone(cls)")
            lines.append(
                "        # Singletons are resolved within an active phase scope:"
            )
            lines.append(
                "        # with enter_phase(agent_session, registry=self.registry) as scope:"
            )
            lines.append(
                f"        #     instance = scope.get_singleton({sorted(impl_classes)[0]})"
            )
    else:
        lines.append("    def test_initialization(self) -> None:")
        lines.append('        """CUJ: Verify initial component presence."""')
        if impl_classes:
            classes_str = ", ".join(sorted(impl_classes))
            lines.append(f"        for cls in [{classes_str}]:")
            lines.append("            self.assertIsNotNone(cls)")
        else:
            lines.append("        self.assertTrue(True)")

    lines.append("")
    lines.append('if __name__ == "__main__":')
    lines.append("    unittest.main()")
    lines.append("")
    lines.append("# Untested requirements:")
    if reqs:
        for r in reqs:
            lines.append(f"# - {r}")
    else:
        lines.append("# None")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Maintain a pyright_test BUILD entry.")
    ap.add_argument(
        "build_path_or_module",
        help="path to the package's BUILD.bazel file or test module",
    )
    ap.add_argument(
        "module_path",
        nargs="?",
        default=None,
        help="path to the test module the entry is for",
    )
    ap.add_argument(
        "--deps",
        default="",
        help="comma-separated expected pyright_deps module names (spec-derived)",
    )
    ap.add_argument(
        "--lib-pkg",
        default="",
        help="the Bazel package holding the modules' pyright_library targets "
        "(the lib package one level up; pyright_deps are written against it)",
    )
    ap.add_argument(
        "--pyi",
        default="",
        help="path to the grounding specification .pyi file",
    )
    ap.add_argument(
        "--scaffold",
        action="store_true",
        help="generate test skeleton for missing or uninitialized test module and exit",
    )
    args = ap.parse_args()

    if args.module_path is not None:
        args.build_path = args.build_path_or_module
    elif args.build_path_or_module.endswith(".py"):
        args.module_path = args.build_path_or_module
        args.build_path = None
    else:
        args.module_path = None
        args.build_path = args.build_path_or_module

    if args.module_path is None:
        return 0

    if not args.lib_pkg:
        abs_mod = os.path.abspath(args.module_path)
        lib_dir = os.path.join(os.path.dirname(os.path.dirname(abs_mod)), "lib")
        if os.path.isdir(lib_dir):
            curr = lib_dir
            repo_root = ""
            while curr and curr != os.path.dirname(curr):
                if any(
                    os.path.isfile(os.path.join(curr, marker))
                    for marker in ("MODULE.bazel", "pyproject.toml", "cleanroom_roles.toml")
                ):
                    repo_root = curr
                    break
                curr = os.path.dirname(curr)
            if repo_root:
                args.lib_pkg = os.path.relpath(lib_dir, repo_root).replace("\\", "/")
            else:
                args.lib_pkg = lib_dir
        else:
            args.lib_pkg = "lib"

    package = package_of(args.build_path) if args.build_path else ""
    stem = module_stem(args.module_path)
    srcs = module_file(args.module_path)
    deps = [d for d in args.deps.split(",") if d and not d.endswith("_ext")]

    impl_stem = stem[:-5] if stem.endswith("_test") else stem
    dir_name = os.path.dirname(args.module_path) or package or "."

    pyi_path = args.pyi
    if not pyi_path or not os.path.isfile(pyi_path):
        pyi_path = find_spec_pyi(args.module_path)
    if pyi_path and not args.pyi:
        args.pyi = pyi_path

    if args.scaffold:
        if pyi_path and os.path.isfile(pyi_path) and impl_stem.endswith("_impl"):
            skeleton = generate_test_skeleton(pyi_path, stem, impl_stem, args.lib_pkg)
            if skeleton:
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                write_text(args.module_path, skeleton)
                return 0
        sys.stderr.write(
            f"test_lint: Cannot scaffold {args.module_path}: specification .pyi not found\n"
        )
        return 1

    if args.build_path is None:
        if not os.path.isfile(args.module_path):
            sys.stderr.write(f"test_lint: File not found: {args.module_path}\n")
            return 1
        mod_content = read_text(args.module_path)
        if pyi_path and is_uninitialized_test_module(mod_content):
            sys.stderr.write(f"test_lint: {args.module_path} is uninitialized\n")
            return 1
    elif os.path.isfile(args.module_path):
        mod_content = read_text(args.module_path)
        if pyi_path and is_uninitialized_test_module(mod_content):
            sys.stderr.write(f"test_lint: {args.module_path} is uninitialized\n")
            return 1

    if args.build_path is None:
        allowed_deps = compute_allowed_spec_deps(
            pyi_path,
            impl_stem,
            is_test=True,
            sibling_stems=None,
            raw_deps=deps,
        )

        if os.path.exists(args.module_path):
            strip_dependency_header(args.module_path)
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

    pkg_build_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(args.build_path))),
        "BUILD.bazel",
    )
    pkg_deps = None
    if os.path.isfile(pkg_build_path):
        pkg_deps = parse_package_build_dependencies(
            pkg_build_path, impl_stem, resolve_cross_package=True
        )

    if pkg_deps is not None:
        info = compute_test_derived_info(
            parent_build_file=pkg_build_path,
            test_name=stem,
            build_file=args.build_path,
            lib_pkg=args.lib_pkg,
            mod_path=args.module_path,
            pyi_path=pyi_path,
            rewrite_imports=True,
        )
        if info is None:
            test_lib_deps = [f"//{args.lib_pkg}:{impl_stem}"]
            allowed_deps = {impl_stem}
            target_deps = []
            uses_lifecycle = False
        else:
            test_lib_deps = info.expected_deps
            allowed_deps = info.allowed_deps
            target_deps = info.target_deps
            uses_lifecycle = info.uses_lifecycle

        has_pip_req = any(d.startswith("requirement(") for d in target_deps)

        if not os.path.exists(args.build_path):
            d = os.path.dirname(args.build_path)
            if d:
                os.makedirs(d, exist_ok=True)
            header = (
                "# " + (package + "/BUILD.bazel" if package else "BUILD.bazel") + "\n"
            )
            write_text(args.build_path, header + load_line(["pyright_test"]) + "\n")
        orig_text = read_text(args.build_path)
        text = orig_text
        text = ensure_load(text, ["pyright_test"])
        if has_pip_req:
            text = ensure_pip_load(text)
        text = ensure_target(
            text,
            RULE,
            stem,
            srcs,
            test_lib_deps,
            args.lib_pkg,
            target_deps=target_deps,
            exact_deps=True,
        )
        if text != orig_text:
            try:
                write_text(args.build_path, text)
            except (PermissionError, OSError) as e:
                actual_targets = parse_targets_by_rule(args.build_path, RULE)
                actual_deps = actual_targets.get(stem)
                if actual_deps is not None:
                    missing = set(test_lib_deps) - set(actual_deps)
                    if not missing:
                        pass
                    else:
                        sys.stderr.write(
                            f"test_lint: Cannot update read-only BUILD file: {args.build_path} (missing deps: {sorted(missing)})\n"
                        )
                        return 1
                else:
                    sys.stderr.write(
                        f"test_lint: Cannot update read-only BUILD file: {args.build_path} ({e})\n"
                    )
                    return 1
    else:
        allowed_deps = {impl_stem}

        for d in deps:
            m = re.search(r'requirement\(["\']([^"\']+)["\']\)', d)
            if m:
                allowed_deps.add(m.group(1))
            elif ":" in d:
                allowed_deps.add(d.split(":")[-1])
            elif d and not d.startswith("//"):
                allowed_deps.add(d)

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
            header = (
                "# " + (package + "/BUILD.bazel" if package else "BUILD.bazel") + "\n"
            )
            write_text(args.build_path, header + load_line(["pyright_test"]) + "\n")
        orig_text = read_text(args.build_path)
        text = orig_text
        text = ensure_load(text, ["pyright_test"])
        roots = sorted(set(deps + local_imports(args.lib_pkg, args.module_path)))
        deps = transitive_closure(args.lib_pkg, roots)
        text = ensure_target(text, RULE, stem, srcs, deps, args.lib_pkg)
        if text != orig_text:
            try:
                write_text(args.build_path, text)
            except (PermissionError, OSError) as e:
                actual_targets = parse_targets_by_rule(args.build_path, RULE)
                actual_deps = actual_targets.get(stem)
                if actual_deps is not None:
                    expected_labels = set()
                    for d in deps:
                        if d.startswith("//"):
                            expected_labels.add(d)
                        elif d.startswith(":"):
                            expected_labels.add(
                                f"//{args.lib_pkg}:{d.lstrip(':')}"
                                if args.lib_pkg
                                else d
                            )
                        else:
                            expected_labels.add(
                                f"//{args.lib_pkg}:{d}" if args.lib_pkg else f":{d}"
                            )
                    missing = expected_labels - set(actual_deps)
                    if not missing:
                        pass
                    else:
                        sys.stderr.write(
                            f"test_lint: Cannot update read-only BUILD file: {args.build_path} (missing deps: {sorted(missing)})\n"
                        )
                        return 1
                else:
                    sys.stderr.write(
                        f"test_lint: Cannot update read-only BUILD file: {args.build_path} ({e})\n"
                    )
                    return 1

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
