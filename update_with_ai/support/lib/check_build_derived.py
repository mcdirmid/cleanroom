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
import os
import sys

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
    from update_python_with_ai.support.lib.build_lint_common import (
        DerivedLibInfo,
        DerivedTestInfo,
        check_lib_targets,
        check_test_targets,
        compute_expected_lib_deps,
        compute_expected_test_deps,
        compute_lib_derived_info,
        compute_test_derived_info,
        ensure_or_update_lib_build,
        ensure_or_update_test_build,
        find_ext_spec_paths,
        find_workspace_root,
        generate_lib_build_content,
        generate_test_build_content,
        package_of,
        parse_part_units,
        parse_targets_by_rule,
    )
except ImportError:
    try:
        from update_with_ai.support.lib.build_lint_common import (
            DerivedLibInfo,
            DerivedTestInfo,
            check_lib_targets,
            check_test_targets,
            compute_expected_lib_deps,
            compute_expected_test_deps,
            compute_lib_derived_info,
            compute_test_derived_info,
            ensure_or_update_lib_build,
            ensure_or_update_test_build,
            find_ext_spec_paths,
            find_workspace_root,
            generate_lib_build_content,
            generate_test_build_content,
            package_of,
            parse_part_units,
            parse_targets_by_rule,
        )
    except ImportError:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from update_python_with_ai.support.lib.build_lint_common import (
            DerivedLibInfo,
            DerivedTestInfo,
            check_lib_targets,
            check_test_targets,
            compute_expected_lib_deps,
            compute_expected_test_deps,
            compute_lib_derived_info,
            compute_test_derived_info,
            ensure_or_update_lib_build,
            ensure_or_update_test_build,
            find_ext_spec_paths,
            find_workspace_root,
            generate_lib_build_content,
            generate_test_build_content,
            package_of,
            parse_part_units,
            parse_targets_by_rule,
        )


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
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update or generate the child BUILD.bazel file if out of date",
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

    if args.update:
        if args.kind == "lib":
            updated = ensure_or_update_lib_build(
                build_file, parent_build_file, workspace_root=workspace_root
            )
        else:
            updated = ensure_or_update_test_build(
                build_file, parent_build_file, workspace_root=workspace_root
            )
        if updated:
            print(f"UPDATED: {args.build_file} from {parent_build_file}.")
        else:
            print(
                f"UP TO DATE: {args.build_file} is already derived from {parent_build_file}."
            )
        return 0

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
