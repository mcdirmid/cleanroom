#!/usr/bin/env python3
"""check_build_derived.py — Verify that targets in lib/BUILD.bazel or tests/BUILD.bazel
are strictly derived from the parent part/*/BUILD.bazel file.

Ensures:
1. Target Completeness: All units declared in the parent BUILD.bazel exist in the child
   BUILD.bazel, and no extraneous orphan targets exist.
2. Target Derivation: Every dependency in pyright_deps is derived from the parent
   BUILD.bazel specification, matching lib_lint.py / test_lint.py rules.
3. Import Validity: Any module imported by the source/test file must be reachable from
   the parent BUILD.bazel specification.

Usage:
  python3 check_build_derived.py --kind lib --build-file <path_to_lib_BUILD.bazel>
  python3 check_build_derived.py --kind test --build-file <path_to_tests_BUILD.bazel>
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Setup environment for hermetic execution under Bazel test sandbox
test_srcdir = os.environ.get("TEST_SRCDIR")
if test_srcdir:
    test_workspace = os.environ.get("TEST_WORKSPACE", "_main")
    ws_dir = os.path.join(test_srcdir, test_workspace)
    if os.path.isdir(ws_dir):
        if ws_dir not in sys.path:
            sys.path.insert(0, ws_dir)
        os.chdir(ws_dir)

try:
    from update_with_ai.support.lib.build_lint_common import (
        _dep_sort_key,
        _parse_build_targets,
        build_module_resolution_map,
        extract_imported_stems,
        find_workspace_root,
        package_of,
        parse_package_build_dependencies,
        parse_spec_build_dependencies,
        read_text,
        rewrite_test_imports,
    )
except ImportError:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from update_with_ai.support.lib.build_lint_common import (
        _dep_sort_key,
        _parse_build_targets,
        build_module_resolution_map,
        extract_imported_stems,
        find_workspace_root,
        package_of,
        parse_package_build_dependencies,
        parse_spec_build_dependencies,
        read_text,
        rewrite_test_imports,
    )


def parse_part_units(pkg_build_path: str) -> dict[str, list[str]]:
    """Extract units defined via update_python_with_ai in the part BUILD.bazel."""
    if not os.path.isfile(pkg_build_path):
        return {}
    try:
        content = read_text(pkg_build_path)
        tree = ast.parse(content, filename=pkg_build_path)
    except (OSError, SyntaxError):
        return {}

    units: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            func_name = call.func.id if isinstance(call.func, ast.Name) else ""
            if func_name == "update_python_with_ai":
                name: Optional[str] = None
                deps: list[str] = []
                for kw in call.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        name = str(kw.value.value)
                    elif kw.arg in ("module_deps", "unit_deps") and isinstance(
                        kw.value, (ast.List, ast.Tuple)
                    ):
                        for elt in kw.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                deps.append(elt.value)
                if (
                    name is None
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                ):
                    name = str(call.args[0].value)
                if name:
                    units[name] = deps
    return units


def parse_targets_by_rule(
    build_path: str, rule_name: str
) -> dict[str, list[str]]:
    """Parse targets of a specific rule from a BUILD file, returning name -> pyright_deps."""
    if not os.path.isfile(build_path):
        return {}
    try:
        content = read_text(build_path)
        tree = ast.parse(content, filename=build_path)
    except (OSError, SyntaxError):
        return {}

    targets: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            func_name = call.func.id if isinstance(call.func, ast.Name) else ""
            if func_name == rule_name:
                name: Optional[str] = None
                deps: list[str] = []
                for kw in call.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        name = str(kw.value.value)
                    elif kw.arg == "pyright_deps" and isinstance(
                        kw.value, (ast.List, ast.Tuple)
                    ):
                        for elt in kw.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                deps.append(elt.value)
                if name:
                    targets[name] = deps
    return targets


def check_lib_targets(
    build_file: str,
    parent_build_file: str,
    workspace_root: Optional[str] = None,
) -> list[str]:
    """Verify lib/BUILD.bazel targets and dependencies against part/*/BUILD.bazel."""
    errors: list[str] = []

    if not os.path.isfile(parent_build_file):
        return [f"Parent part BUILD file not found: {parent_build_file}"]
    if not os.path.isfile(build_file):
        return [f"Library BUILD file not found: {build_file}"]

    units = parse_part_units(parent_build_file)
    actual_targets = parse_targets_by_rule(build_file, "pyright_library")

    parent_pkg = package_of(parent_build_file)
    package = package_of(build_file)
    lib_dir = os.path.dirname(os.path.abspath(build_file))
    part_dir = os.path.dirname(os.path.abspath(parent_build_file))
    grounding_dir = os.path.join(part_dir, "grounding")

    # 1. Existence checks (exclude _ext units which do not produce lib implementations)
    missing_units = {
        u for u in units.keys() if not u.endswith("_ext")
    } - set(actual_targets.keys())
    if missing_units:
        errors.append(
            f"Missing pyright_library target(s) in {build_file} for unit(s) declared in {parent_build_file}: "
            f"{sorted(missing_units)}"
        )

    extra_targets = set(actual_targets.keys()) - set(units.keys())
    if extra_targets:
        errors.append(
            f"Target(s) in {build_file} do not correspond to any unit declared in {parent_build_file}: "
            f"{sorted(extra_targets)}"
        )

    # 2. Dependency derivation checks
    for stem, actual_deps in actual_targets.items():
        if stem not in units:
            continue

        pkg_deps = parse_package_build_dependencies(
            parent_build_file,
            stem,
            resolve_cross_package=False,
            workspace_root=workspace_root,
        )
        if pkg_deps is None:
            errors.append(
                f"Target '{stem}' could not resolve package dependencies from {parent_build_file}"
            )
            continue

        mod_path = os.path.join(lib_dir, f"{stem}.py")
        pyi_path = os.path.join(grounding_dir, f"{stem}.pyi")
        mod_content = read_text(mod_path) if os.path.isfile(mod_path) else ""
        pyi_content = read_text(pyi_path) if os.path.isfile(pyi_path) else ""

        uses_lifecycle = (
            "support.lib.lifecycle" in mod_content
            or re.search(
                r"\b(LifecycleRegistry|LifecycleTier|Singleton|get_singleton|get_default_registry)\b",
                mod_content,
            )
            is not None
            or stem.endswith("_impl")
            or "@singleton_type" in pyi_content
            or "LifecycleTier" in pyi_content
        )

        lib_deps: list[str] = []
        for d in pkg_deps:
            stem_d = d.split(":")[-1]
            if stem_d.endswith("_ext"):
                continue
            if d.startswith("//"):
                raw = d[2:]
                p_part, t_part = (
                    raw.split(":", 1)
                    if ":" in raw
                    else (raw, os.path.basename(raw))
                )
                if p_part == parent_pkg:
                    lib_label = f":{t_part}"
                else:
                    p_lib = (
                        p_part if p_part.endswith("/lib") else f"{p_part}/lib"
                    )
                    lib_label = f"//{p_lib}:{t_part}"
                lib_deps.append(lib_label)
            elif d.startswith(":"):
                lib_deps.append(f":{d[1:]}")
            else:
                lib_deps.append(f":{d}")

        if uses_lifecycle:
            lib_deps.append("//update_python_with_ai/support/lib:lifecycle")
            if stem != "agent_session":
                lib_deps.append("//update_with_ai/parts/agent/lib:agent_session")

        # Canonicalize per ensure_target
        want_list = []
        for d in lib_deps:
            if d.startswith("//"):
                if package and d.startswith("//" + package + ":"):
                    want_list.append(":" + d.split(":")[-1])
                else:
                    want_list.append(d)
            elif d.startswith(":"):
                want_list.append(d)
            else:
                want_list.append(":" + d)
        expected_deps = sorted(set(want_list), key=_dep_sort_key)

        if actual_deps != expected_deps:
            missing = [d for d in expected_deps if d not in actual_deps]
            unexpected = [d for d in actual_deps if d not in expected_deps]
            errors.append(
                f"Target '{stem}' in {build_file} has pyright_deps not derived from {parent_build_file}:\n"
                f"  Missing derived deps:   {missing}\n"
                f"  Unexpected / extra deps: {unexpected}\n"
                f"  Actual:   {actual_deps}\n"
                f"  Expected: {expected_deps}"
            )

    return errors


def check_test_targets(
    build_file: str,
    parent_build_file: str,
    workspace_root: Optional[str] = None,
) -> list[str]:
    """Verify tests/BUILD.bazel targets and dependencies against part/*/BUILD.bazel."""
    errors: list[str] = []

    if not os.path.isfile(parent_build_file):
        return [f"Parent part BUILD file not found: {parent_build_file}"]
    if not os.path.isfile(build_file):
        return [f"Tests BUILD file not found: {build_file}"]

    units = parse_part_units(parent_build_file)
    actual_targets = parse_targets_by_rule(build_file, "pyright_test")

    parent_pkg = package_of(parent_build_file)
    lib_pkg = f"{parent_pkg}/lib" if parent_pkg else "lib"
    test_dir = os.path.dirname(os.path.abspath(build_file))
    part_dir = os.path.dirname(os.path.abspath(parent_build_file))
    grounding_dir = os.path.join(part_dir, "grounding")

    # 1. Existence checks
    expected_test_stems = {
        u
        for u in units.keys()
        if u.endswith("_impl")
        or os.path.isfile(os.path.join(test_dir, f"{u}_test.py"))
    }
    expected_test_names = {f"{stem}_test" for stem in expected_test_stems}

    missing_tests = expected_test_names - set(actual_targets.keys())
    if missing_tests:
        errors.append(
            f"Missing pyright_test target(s) in {build_file} for unit(s) declared in {parent_build_file}: "
            f"{sorted(missing_tests)}"
        )

    extra_tests = set(actual_targets.keys()) - expected_test_names
    if extra_tests:
        errors.append(
            f"Target(s) in {build_file} do not correspond to any unit declared in {parent_build_file}: "
            f"{sorted(extra_tests)}"
        )

    # 2. Dependency derivation checks
    for test_name, actual_deps in actual_targets.items():
        impl_stem = test_name[:-5] if test_name.endswith("_test") else test_name
        if impl_stem not in units:
            continue

        pkg_deps = parse_package_build_dependencies(
            parent_build_file,
            impl_stem,
            resolve_cross_package=True,
            workspace_root=workspace_root,
        )
        if pkg_deps is None:
            errors.append(
                f"Target '{test_name}' could not resolve package dependencies from {parent_build_file}"
            )
            continue

        mod_path = os.path.join(test_dir, f"{test_name}.py")
        pyi_path = os.path.join(grounding_dir, f"{impl_stem}.pyi")
        content = read_text(mod_path) if os.path.isfile(mod_path) else ""
        pyi_content = read_text(pyi_path) if os.path.isfile(pyi_path) else ""

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
                raw.split(":", 1)
                if ":" in raw
                else (raw, os.path.basename(raw))
            )
            if t_part.endswith("_ext"):
                continue
            if p_part == parent_pkg:
                lib_label = f"//{lib_pkg}:{t_part}"
            else:
                p_lib = p_part if p_part.endswith("/lib") else f"{p_part}/lib"
                lib_label = f"//{p_lib}:{t_part}"
            reachable_map[t_part] = lib_label

        target_targets = _parse_build_targets(parent_build_file)

        target_under_test = f"//{lib_pkg}:{impl_stem}"
        reachable_map[impl_stem] = target_under_test
        direct_deps_list.append(target_under_test)
        if impl_stem.endswith("_impl"):
            iface_stem = impl_stem[:-5]
            if iface_stem in units or iface_stem in target_targets:
                iface_target = f"//{lib_pkg}:{iface_stem}"
                reachable_map[iface_stem] = iface_target
                direct_deps_list.append(iface_target)

        for d in target_targets.get(impl_stem, []):
            st = d.split(":")[-1]
            if st.endswith("_ext"):
                continue
            if st in reachable_map and reachable_map[st] not in direct_deps_list:
                direct_deps_list.append(reachable_map[st])

        import_map, _, _ = build_module_resolution_map(
            build_file, lib_pkg, list(reachable_map.values())
        )
        imported_stems: list[str] = []
        if os.path.exists(mod_path):
            _, imported_stems = rewrite_test_imports(mod_path, import_map)

        test_lib_deps = list(direct_deps_list)
        for s in imported_stems:
            if s in reachable_map and reachable_map[s] not in test_lib_deps:
                test_lib_deps.append(reachable_map[s])
        if os.path.exists(mod_path):
            for _, s in extract_imported_stems(mod_path):
                if s in reachable_map and reachable_map[s] not in test_lib_deps:
                    test_lib_deps.append(reachable_map[s])

        if uses_lifecycle:
            lifecycle_label = "//update_python_with_ai/support/lib:lifecycle"
            if lifecycle_label not in test_lib_deps:
                test_lib_deps.append(lifecycle_label)

        # Canonicalize per ensure_target
        want_list = []
        for d in test_lib_deps:
            if d.startswith("//"):
                want_list.append(d)
            elif d.startswith(":"):
                want_list.append("//" + lib_pkg + ":" + d.lstrip(":"))
            else:
                want_list.append("//" + lib_pkg + ":" + d)
        expected_deps = sorted(set(want_list), key=_dep_sort_key)

        if actual_deps != expected_deps:
            missing = [d for d in expected_deps if d not in actual_deps]
            unexpected = [d for d in actual_deps if d not in expected_deps]
            errors.append(
                f"Target '{test_name}' in {build_file} has pyright_deps not derived from {parent_build_file}:\n"
                f"  Missing derived deps:   {missing}\n"
                f"  Unexpected / extra deps: {unexpected}\n"
                f"  Actual:   {actual_deps}\n"
                f"  Expected: {expected_deps}"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify targets in child BUILD.bazel are derived from parent part/*/BUILD.bazel."
    )
    parser.add_argument(
        "--kind",
        choices=["lib", "test"],
        required=True,
        help="Whether verifying lib/BUILD.bazel or tests/BUILD.bazel",
    )
    parser.add_argument(
        "--build-file",
        required=True,
        help="Path to the child BUILD.bazel file (e.g. update_with_ai/parts/sandbox/lib/BUILD.bazel)",
    )
    parser.add_argument(
        "--parent-build-file",
        default="",
        help="Path to parent part BUILD.bazel (inferred from --build-file if omitted)",
    )
    parser.add_argument(
        "--workspace-root",
        default="",
        help="Workspace root path (inferred if omitted)",
    )
    args = parser.parse_args()

    build_file = os.path.abspath(args.build_file)
    parent_build_file = args.parent_build_file
    if not parent_build_file:
        parent_build_file = os.path.join(
            os.path.dirname(os.path.dirname(build_file)), "BUILD.bazel"
        )
    parent_build_file = os.path.abspath(parent_build_file)

    workspace_root = (
        os.path.abspath(args.workspace_root)
        if args.workspace_root
        else find_workspace_root(build_file)
    )

    if args.kind == "lib":
        errors = check_lib_targets(
            build_file, parent_build_file, workspace_root=workspace_root
        )
    else:
        errors = check_test_targets(
            build_file, parent_build_file, workspace_root=workspace_root
        )

    if errors:
        sys.stderr.write(
            f"FAIL: Verification failed for {args.build_file} against {parent_build_file}:\n"
        )
        for err in errors:
            sys.stderr.write(f"\n{err}\n")
        return 1

    print(
        f"PASS: All targets in {args.build_file} are correctly derived from {parent_build_file}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
