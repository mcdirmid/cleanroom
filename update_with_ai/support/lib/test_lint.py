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

from build_lint_common import (
    _parse_build_targets,
    build_module_resolution_map,
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
    load_line,
    local_imports,
    module_file,
    module_stem,
    package_of,
    parse_dependency_header,
    parse_package_build_dependencies,
    parse_pyi_dependencies,
    parse_spec_build_dependencies,
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
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name.startswith("test_")
                ):
                    test_methods.append(item)
        if not test_classes or not test_methods:
            return True
    except SyntaxError:
        if "<" in content and ">" in content:
            return True
    return False


def extract_requirements_from_pyi(pyi_path: str) -> list[str]:
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
            if stripped in ("FRESH_REQUIREMENTS:", "REQUIREMENTS:"):
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

    return requirements


def generate_test_skeleton(
    pyi_path: str, stem: str, impl_stem: str, lib_pkg: str
) -> str:
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
            lines.append("        # Singletons are resolved within an active phase scope:")
            lines.append('        # with enter_phase(agent_session, registry=self.registry) as scope:')
            lines.append(f"        #     instance = scope.get_singleton({sorted(impl_classes)[0]})")
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
    dir_name = os.path.dirname(args.module_path) or package or "."

    pyi_path = args.pyi
    if not pyi_path or not os.path.isfile(pyi_path):
        inferred = os.path.join(
            os.path.dirname(args.lib_pkg.rstrip("/")),
            "grounding",
            f"{impl_stem}.pyi",
        )
        if os.path.isfile(inferred):
            pyi_path = inferred
    if pyi_path and not args.pyi:
        args.pyi = pyi_path

    if pyi_path and os.path.isfile(pyi_path):
        mod_exists = os.path.isfile(args.module_path)
        mod_content = read_text(args.module_path) if mod_exists else ""
        if not mod_exists or is_uninitialized_test_module(mod_content):
            skeleton = generate_test_skeleton(pyi_path, stem, impl_stem, args.lib_pkg)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            write_text(args.module_path, skeleton)

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
        parent_pkg = package_of(pkg_build_path)
        content = (
            read_text(args.module_path) if os.path.isfile(args.module_path) else ""
        )
        pyi_content = (
            read_text(pyi_path) if pyi_path and os.path.isfile(pyi_path) else ""
        )
        uses_lifecycle = (
            "support.lib.lifecycle" in content
            or re.search(
                r"\b(LifecycleRegistry|Singleton|get_singleton|get_default_registry|enter_phase)\b",
                content,
            )
            is not None
            or "@singleton_type" in pyi_content
        )

        reachable_map: dict[str, str] = {}
        direct_deps_list: list[str] = []

        for label in pkg_deps:
            raw = label[2:] if label.startswith("//") else label
            p_part, t_part = (
                raw.split(":", 1) if ":" in raw else (raw, os.path.basename(raw))
            )
            if t_part.endswith("_ext"):
                continue
            if p_part == parent_pkg:
                lib_label = f"//{args.lib_pkg}:{t_part}"
            else:
                p_lib = p_part if p_part.endswith("/lib") else f"{p_part}/lib"
                lib_label = f"//{p_lib}:{t_part}"
            reachable_map[t_part] = lib_label

        target_under_test = f"//{args.lib_pkg}:{impl_stem}"
        reachable_map[impl_stem] = target_under_test
        direct_deps_list.append(target_under_test)
        if impl_stem.endswith("_impl"):
            iface_stem = impl_stem[:-5]
            iface_target = f"//{args.lib_pkg}:{iface_stem}"
            reachable_map[iface_stem] = iface_target
            direct_deps_list.append(iface_target)

        allowed_deps: set[str] = {d for d in reachable_map.keys() if not d.endswith("_ext")}
        if uses_lifecycle:
            allowed_deps.add("lifecycle")
        if pyi_path and os.path.isfile(pyi_path):
            for d in parse_pyi_dependencies(pyi_path):
                if not d.endswith("_ext"):
                    allowed_deps.add(d)

        # Direct deps declared on impl_stem in parent BUILD.bazel
        target_targets = _parse_build_targets(pkg_build_path)
        for d in target_targets.get(impl_stem, []):
            st = d.split(":")[-1]
            if st.endswith("_ext"):
                continue
            if st in reachable_map and reachable_map[st] not in direct_deps_list:
                direct_deps_list.append(reachable_map[st])

        target_deps = (
            parse_spec_build_dependencies(pyi_path) if pyi_path else []
        )
        has_pip_req = any(d.startswith("requirement(") for d in target_deps)

        if os.path.exists(args.module_path):
            strip_dependency_header(args.module_path)

        import_map, _, _ = build_module_resolution_map(
            args.build_path, args.lib_pkg, list(reachable_map.values())
        )
        imported_stems: list[str] = []
        if os.path.exists(args.module_path):
            _, imported_stems = rewrite_test_imports(args.module_path, import_map)

        test_lib_deps = list(direct_deps_list)
        for s in imported_stems:
            if s in reachable_map and reachable_map[s] not in test_lib_deps:
                test_lib_deps.append(reachable_map[s])
        if os.path.exists(args.module_path):
            for _, s in extract_imported_stems(args.module_path):
                if s in reachable_map and reachable_map[s] not in test_lib_deps:
                    test_lib_deps.append(reachable_map[s])

        if uses_lifecycle:
            lifecycle_label = "//update_python_with_ai/support/lib:lifecycle"
            if lifecycle_label not in test_lib_deps:
                test_lib_deps.append(lifecycle_label)

        if not os.path.exists(args.build_path):
            d = os.path.dirname(args.build_path)
            if d:
                os.makedirs(d, exist_ok=True)
            header = (
                "# " + (package + "/BUILD.bazel" if package else "BUILD.bazel") + "\n"
            )
            write_text(args.build_path, header + load_line(["pyright_test"]) + "\n")
        text = read_text(args.build_path)
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
        write_text(args.build_path, text)
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
            header = "# " + (package + "/BUILD.bazel" if package else "BUILD.bazel") + "\n"
            write_text(args.build_path, header + load_line(["pyright_test"]) + "\n")
        text = read_text(args.build_path)
        text = ensure_load(text, ["pyright_test"])
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
