#!/usr/bin/env python3
"""import_boundaries_lint_test.py — Automated verification of Cleanroom import boundaries.

Guarantees across the canonical codebase (update_with_ai and update_python_with_ai):
1. Zero staging imports in any Python or specification file.
2. Library encapsulation: Non-assembly modules (lib/*.py) never import foreign *_impl modules.
3. Test isolation: Test modules (tests/*_test.py) only import their target under test.
4. Build derivation: All lib/BUILD.bazel targets are strictly derived from parent specifications.
5. Test build derivation: All tests/BUILD.bazel targets are strictly derived from parent specifications.
"""

import glob
import os
import sys
import unittest


def find_repo_root() -> str:
    # 1. BUILD_WORKSPACE_DIRECTORY (set by bazel run)
    ws = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if ws and os.path.isdir(os.path.join(ws, "update_with_ai")):
        return ws
    # 2. TEST_SRCDIR / TEST_WORKSPACE (set by bazel test)
    srcdir = os.environ.get("TEST_SRCDIR")
    if srcdir:
        test_ws = os.environ.get("TEST_WORKSPACE", "_main")
        candidate = os.path.join(srcdir, test_ws)
        if os.path.isdir(os.path.join(candidate, "update_with_ai")):
            return candidate
    # 3. Walk up from __file__
    cur = os.path.abspath(os.path.dirname(__file__))
    while cur and cur != os.path.dirname(cur):
        if os.path.isdir(os.path.join(cur, "update_with_ai")) and (
            os.path.isfile(os.path.join(cur, "MODULE.bazel"))
            or os.path.isfile(os.path.join(cur, "WORKSPACE"))
        ):
            return cur
        cur = os.path.dirname(cur)
    return os.getcwd()


REPO_ROOT = find_repo_root()
for p in [
    REPO_ROOT,
    os.path.join(REPO_ROOT, "update_python_with_ai"),
    os.path.join(REPO_ROOT, "update_with_ai"),
    os.path.join(REPO_ROOT, "update_python_with_ai", "support", "lib"),
    os.path.join(REPO_ROOT, "update_with_ai", "support", "lib"),
]:
    if p not in sys.path and os.path.isdir(p):
        sys.path.insert(0, p)

import ast

def _scan_for_staging_imports(file_path: str) -> list[str]:
    errors: list[str] = []
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (OSError, SyntaxError):
        return errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "staging" in alias.name.split("."):
                    errors.append(f"{file_path}:{node.lineno}: error: prohibited import of staging module '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module and "staging" in node.module.split("."):
                errors.append(f"{file_path}:{node.lineno}: error: prohibited import from staging module '{node.module}'")
            for alias in node.names:
                if alias.name == "staging":
                    errors.append(f"{file_path}:{node.lineno}: error: prohibited import of staging module '{alias.name}'")
        elif isinstance(node, ast.Call):
            func = node.func
            is_import_call = (
                (isinstance(func, ast.Name) and func.id == "__import__")
                or (isinstance(func, ast.Attribute) and func.attr == "import_module" and isinstance(func.value, ast.Name) and func.value.id == "importlib")
            )
            if is_import_call and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    if "staging" in arg0.value.split("."):
                        errors.append(f"{file_path}:{node.lineno}: error: prohibited dynamic import of staging module '{arg0.value}'")
    return errors


from build_lint_common import (  # type: ignore[import-not-found]
    check_impl_imports,
    check_lib_targets,
    check_test_impl_imports,
    check_test_targets,
)


class ImportBoundariesLintTest(unittest.TestCase):
    def test_no_staging_imports_in_canonical_code(self) -> None:
        """Rule 1: Prohibit any static or dynamic import of staging/ in canonical code."""
        errors: list[str] = []
        for root_dir in ["update_with_ai", "update_python_with_ai"]:
            abs_root = os.path.join(REPO_ROOT, root_dir)
            if not os.path.isdir(abs_root):
                continue
            for ext in ["py", "pyi"]:
                pattern = os.path.join(abs_root, "**", f"*.{ext}")
                for file_path in glob.glob(pattern, recursive=True):
                    if "staging" in file_path.split(os.sep):
                        continue
                    errors.extend(_scan_for_staging_imports(file_path))

        if errors:
            self.fail(
                f"Discovered {len(errors)} prohibited staging import(s):\n"
                + "\n".join(errors)
            )

    def test_library_implementation_encapsulation(self) -> None:
        """Rule 2: Interface modules and non-assembly implementation modules must not import foreign *_impl."""
        errors: list[str] = []
        for root_dir in ["update_with_ai", "update_python_with_ai"]:
            pattern = os.path.join(REPO_ROOT, root_dir, "parts", "*", "lib", "*.py")
            for file_path in glob.glob(pattern):
                errors.extend(check_impl_imports(file_path))

        if errors:
            self.fail(
                f"Discovered {len(errors)} prohibited library implementation import(s):\n"
                + "\n".join(errors)
            )

    def test_test_implementation_isolation(self) -> None:
        """Rule 3: Unit tests must only import their target under test and never foreign *_impl."""
        errors: list[str] = []
        for root_dir in ["update_with_ai", "update_python_with_ai"]:
            pattern = os.path.join(REPO_ROOT, root_dir, "parts", "*", "tests", "*_test.py")
            for file_path in glob.glob(pattern):
                part_dir = os.path.dirname(os.path.dirname(file_path))
                lib_pkg = os.path.join(os.path.relpath(part_dir, REPO_ROOT), "lib")
                errors.extend(check_test_impl_imports(lib_pkg, file_path))

        if errors:
            self.fail(
                f"Discovered {len(errors)} prohibited test implementation import(s):\n"
                + "\n".join(errors)
            )

    def test_all_lib_build_targets_derived(self) -> None:
        """Rule 4: All lib/BUILD.bazel targets and pyright_deps must be strictly derived."""
        errors: list[str] = []
        for root_dir in ["update_with_ai", "update_python_with_ai"]:
            pattern = os.path.join(REPO_ROOT, root_dir, "parts", "*", "lib", "BUILD.bazel")
            for build_file in glob.glob(pattern):
                parent_build = os.path.join(os.path.dirname(os.path.dirname(build_file)), "BUILD.bazel")
                if os.path.isfile(parent_build):
                    errors.extend(check_lib_targets(build_file, parent_build, workspace_root=REPO_ROOT))

        if errors:
            self.fail(
                f"Discovered {len(errors)} underived library target error(s):\n"
                + "\n".join(errors)
            )

    def test_all_test_build_targets_derived(self) -> None:
        """Rule 5: All tests/BUILD.bazel targets and pyright_deps must be strictly derived."""
        errors: list[str] = []
        for root_dir in ["update_with_ai", "update_python_with_ai"]:
            pattern = os.path.join(REPO_ROOT, root_dir, "parts", "*", "tests", "BUILD.bazel")
            for build_file in glob.glob(pattern):
                parent_build = os.path.join(os.path.dirname(os.path.dirname(build_file)), "BUILD.bazel")
                if os.path.isfile(parent_build):
                    errors.extend(check_test_targets(build_file, parent_build, workspace_root=REPO_ROOT))

        if errors:
            self.fail(
                f"Discovered {len(errors)} underived test target error(s):\n"
                + "\n".join(errors)
            )


if __name__ == "__main__":
    unittest.main()
