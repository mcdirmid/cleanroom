#!/usr/bin/env python3
"""Automated migration codemod for Cleanroom Lifecycle Revamp.

Transforms implementation modules, assembly modules, and test files from
imperative lifecycle registration blocks to declarative @singleton and
LifecycleTestCase architectures.

Usage:
    python3 bin/port_lifecycle.py <path_or_file> [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import difflib
import os
import re
import sys
from pathlib import Path
from typing import Optional, Set

AUTO_INIT_START = "# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---"
AUTO_INIT_END = "# --- END CLEANROOM AUTO-GENERATED ---"


def normalize_lifecycle_import(content: str, ensure_symbols: set[str]) -> str:
    """Replaces lifecycle imports with only the strictly needed symbols."""
    known = {
        "Singleton",
        "singleton",
        "system",
        "get_singleton",
        "enter_phase",
        "begin_phase",
        "auto_initialize",
        "LifecycleTestCase",
        "fake",
        "LifecycleRegistry",
        "LifecycleTier",
        "ChildTierOf",
        "SystemTier",
        "InTier",
        "Initializable",
        "LifecycleError",
        "LifecycleIsolationError",
        "LifecycleResolutionError",
        "LifecycleInitializationError",
        "LifecycleScope",
        "SingletonDescriptor",
        "get_active_scope",
        "get_ambient_system_scope",
        "get_default_registry",
        "get_tier",
    }
    # Remove existing top-level lifecycle import to find truly used symbols in body
    stripped = re.sub(
        r"^from support\.lib\.lifecycle import (?:\([^)]*\)|[^\n]+)\n?",
        "",
        content,
        flags=re.MULTILINE,
    )
    try:
        tree = ast.parse(stripped)
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    except Exception:
        used = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", stripped))

    needed = sorted((used.intersection(known)).union(ensure_symbols))
    if not needed:
        return stripped

    import_stmt = f"from support.lib.lifecycle import {', '.join(needed)}\n"
    if re.search(r"^from support\.lib\.lifecycle import", content, re.MULTILINE):
        return re.sub(
            r"^from support\.lib\.lifecycle import (?:\([^)]*\)|[^\n]+)\n?",
            import_stmt,
            content,
            count=1,
            flags=re.MULTILINE,
        )
    return import_stmt + content


def port_impl_file(file_path: Path, dry_run: bool = False) -> bool:
    """Ports an implementation file (*_impl.py) to declarative @singleton."""
    content = file_path.read_text(encoding="utf-8")
    original = content

    # 1. Strip AUTO_INIT block if present
    if AUTO_INIT_START in content and AUTO_INIT_END in content:
        start_idx = content.find(AUTO_INIT_START)
        end_idx = content.find(AUTO_INIT_END) + len(AUTO_INIT_END)
        content = content[:start_idx].rstrip() + "\n" + content[end_idx:].lstrip()

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError:
        return False

    # 2. Check for manual __initialize__ and _initialize_ functions
    init_nodes = [
        n
        for n in tree.body
        if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "__initialize__")
        or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("_initialize_", "__initialize__") for t in n.targets))
    ]
    if init_nodes:
        lines = content.splitlines(keepends=True)
        min_line = min(n.lineno for n in init_nodes)
        end_linenos = [n.end_lineno for n in init_nodes if n.end_lineno is not None]
        max_line = max(end_linenos) if end_linenos else min_line
        kept_lines = lines[: min_line - 1]
        after_lines = lines[max_line:]
        content = "".join(kept_lines).rstrip() + "\n"
        if any(l.strip() for l in after_lines):
            content += "".join(after_lines).rstrip() + "\n"
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            pass

    # 3. Find singleton classes to decorate
    modified_classes = False
    lines = content.splitlines()

    # Re-parse to get exact line numbers
    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError:
        return False

    classes_to_decorate: list[tuple[int, str]] = []  # (lineno, class_name)
    tier_lines_to_remove: set[int] = set()

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            has_singleton_dec = any(
                (isinstance(d, ast.Name) and d.id in ("singleton", "singleton_type"))
                or (isinstance(d, ast.Attribute) and d.attr in ("singleton", "singleton_type"))
                for d in node.decorator_list
            )
            is_singleton = (
                any(ast.unparse(b) in ("Singleton", "lifecycle.Singleton") for b in node.bases)
                or any(
                    (isinstance(item, ast.Assign) and any(getattr(t, "id", "") == "tier" for t in item.targets))
                    for item in node.body
                )
            )
            if is_singleton and not has_singleton_dec:
                classes_to_decorate.append((node.lineno, node.name))
                # Identify tier = ... line inside the class
                for item in node.body:
                    if isinstance(item, ast.Assign) and any(getattr(t, "id", "") == "tier" for t in item.targets):
                        tier_lines_to_remove.add(item.lineno)

    if classes_to_decorate:
        modified_classes = True
        # Insert @singleton before classes in reverse line order
        new_lines: list[str] = []
        for idx, line in enumerate(lines, start=1):
            if idx in tier_lines_to_remove:
                continue
            for c_line, _ in classes_to_decorate:
                if idx == c_line:
                    new_lines.append("@singleton")
                    break
            new_lines.append(line)
        content = "\n".join(new_lines) + "\n"

    # 4. Normalize support.lib.lifecycle imports cleanly and add auto_initialize shim
    ensure_syms = {"singleton", "auto_initialize"} if (modified_classes or "@singleton" in content) else set()
    content = normalize_lifecycle_import(content, ensure_syms)

    if (modified_classes or "@singleton" in content) and "__initialize__ = auto_initialize()" not in content:
        if "__initialize__ = auto_initialize\n" in content:
            content = content.replace(
                "__initialize__ = auto_initialize\n",
                "__initialize__ = auto_initialize()\n",
            )
        else:
            content = content.rstrip() + "\n\n__initialize__ = auto_initialize()\n_initialize_ = __initialize__\n"

    content = content.rstrip() + "\n"
    if content != original:
        if not dry_run:
            file_path.write_text(content, encoding="utf-8")
        return True
    return False


def port_asm_file(file_path: Path, dry_run: bool = False) -> bool:
    """Ports an assembly file (*_asm.py) to concise declarative structure."""
    content = file_path.read_text(encoding="utf-8")
    original = content

    # Check if CONSTITUENTS is defined
    if "CONSTITUENTS" in content:
        # Simplify manual loop in __initialize__ if present
        if "for constituent in CONSTITUENTS:" in content:
            content = re.sub(
                r"def __initialize__\([^)]*\)[^:]*:\s*(?:[^\n]+\n)+\s*_initialize_ = __initialize__",
                "__initialize__ = auto_initialize()\n_initialize_ = __initialize__",
                content,
            )
            content = normalize_lifecycle_import(content, {"auto_initialize"})

    content = content.rstrip() + "\n"
    if content != original:
        if not dry_run:
            file_path.write_text(content, encoding="utf-8")
        return True
    return False


def port_test_file(file_path: Path, dry_run: bool = False) -> bool:
    """Ports a test file (*_impl_test.py) to LifecycleTestCase and @fake."""
    content = file_path.read_text(encoding="utf-8")
    original = content

    # 1. Convert top-level class FooTest(unittest.TestCase) to class FooTest(LifecycleTestCase)
    converted_class = False
    if re.search(r"^class \w+\(unittest\.TestCase\):", content, re.MULTILINE):
        content = re.sub(
            r"^class (\w+)\(unittest\.TestCase\):",
            r"class \1(LifecycleTestCase):",
            content,
            flags=re.MULTILINE,
        )
        converted_class = True

    # 2. Clean up setUp in test classes using AST
    try:
        tree = ast.parse(content, filename=str(file_path))
        lines = content.splitlines(keepends=True)
        lines_to_remove: set[int] = set()
        lines_to_insert: dict[int, str] = {}

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == "setUp":
                            removable_stmts = []
                            other_stmts = []
                            for stmt in item.body:
                                is_removable = False
                                if isinstance(stmt, ast.Assign):
                                    t_str = ast.unparse(stmt.targets[0])
                                    v_str = ast.unparse(stmt.value)
                                    if t_str == "self.registry" and "LifecycleRegistry" in v_str:
                                        is_removable = True
                                elif isinstance(stmt, ast.Expr) and isinstance(
                                    stmt.value, ast.Call
                                ):
                                    func_str = ast.unparse(stmt.value.func)
                                    if func_str in ("__initialize__", "_initialize_"):
                                        is_removable = True
                                if is_removable:
                                    removable_stmts.append(stmt)
                                else:
                                    other_stmts.append(stmt)

                            if not other_stmts:
                                # Entire setUp can be removed
                                start_l = item.lineno
                                end_l = (
                                    item.end_lineno
                                    if item.end_lineno is not None
                                    else item.lineno
                                )
                                for l in range(start_l, end_l + 1):
                                    lines_to_remove.add(l)
                            else:
                                for stmt in removable_stmts:
                                    start_l = stmt.lineno
                                    end_l = (
                                        stmt.end_lineno
                                        if stmt.end_lineno is not None
                                        else stmt.lineno
                                    )
                                    for l in range(start_l, end_l + 1):
                                        lines_to_remove.add(l)
                                has_super = any(
                                    isinstance(s, ast.Expr)
                                    and isinstance(s.value, ast.Call)
                                    and "super().setUp" in ast.unparse(s.value)
                                    for s in other_stmts
                                )
                                if not has_super and item.body:
                                    first_l = item.body[0].lineno
                                    lines_to_insert[first_l] = "        super().setUp()\n"
                        elif item.name == "tearDown":
                            # Check if tearDown only called self.scope.close()
                            if len(item.body) == 1:
                                stmt = item.body[0]
                                if isinstance(stmt, ast.Expr) and isinstance(
                                    stmt.value, ast.Call
                                ):
                                    if ast.unparse(stmt.value) in (
                                        "self.scope.close()",
                                        "self.scope.close()",
                                    ):
                                        start_l = item.lineno
                                        end_l = (
                                            item.end_lineno
                                            if item.end_lineno is not None
                                            else item.lineno
                                        )
                                        for l in range(start_l, end_l + 1):
                                            lines_to_remove.add(l)

        if lines_to_remove or lines_to_insert:
            new_lines = []
            for idx, l in enumerate(lines, start=1):
                if idx in lines_to_insert:
                    new_lines.append(lines_to_insert[idx])
                if idx not in lines_to_remove:
                    new_lines.append(l)
            content = "".join(new_lines)
    except SyntaxError:
        pass

    if converted_class or "LifecycleTestCase" in content:
        content = normalize_lifecycle_import(content, {"LifecycleTestCase"})

    content = content.rstrip() + "\n"
    if content != original:
        if not dry_run:
            file_path.write_text(content, encoding="utf-8")
        return True
    return False


def port_path(target_path: Path, dry_run: bool = False, show_diff: bool = False) -> None:
    """Recursively ports all files under target_path."""
    if target_path.is_file():
        files = [target_path]
    else:
        files = list(target_path.rglob("*.py"))

    changed_count = 0
    for f in sorted(files):
        # Skip pycache and hidden dirs
        if any(part.startswith((".", "__pycache__")) for part in f.parts):
            continue
        fname = f.name
        changed = False
        original = f.read_text(encoding="utf-8")
        if fname.endswith("_impl.py"):
            changed = port_impl_file(f, dry_run=dry_run)
        elif fname.endswith("_asm.py"):
            changed = port_asm_file(f, dry_run=dry_run)
        elif fname.endswith("_test.py"):
            changed = port_test_file(f, dry_run=dry_run)

        if changed:
            changed_count += 1
            action = "Would port" if dry_run else "Ported"
            print(f"[{action}] {f}")
            if show_diff:
                new_content = f.read_text(encoding="utf-8") if not dry_run else ""
                # For dry_run, re-run in memory
                if dry_run:
                    if fname.endswith("_impl.py"):
                        port_impl_file(f, dry_run=True)
                    # compute diff from dry run
                diff = difflib.unified_diff(
                    original.splitlines(),
                    new_content.splitlines() if not dry_run else [],
                    fromfile=str(f),
                    tofile=str(f) + " (ported)",
                    lineterm="",
                )
                print("\n".join(diff))

    print(f"Total files updated: {changed_count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Port codebase to declarative lifecycle.")
    parser.add_argument("path", help="File or directory path to port")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without modifying files")
    parser.add_argument("--diff", action="store_true", help="Show unified diff of changes")
    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"Error: target path {target} does not exist", file=sys.stderr)
        return 1

    port_path(target, dry_run=args.dry_run, show_diff=args.diff)
    return 0


if __name__ == "__main__":
    sys.exit(main())
