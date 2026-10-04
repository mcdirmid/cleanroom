#!/usr/bin/env python3
"""
grounding_lint.py — structural and contract linter for Static Python Grounding (grounding/*.py).

Usage:
    python3 update_python_with_ai/support/lib/grounding_lint.py [files...]
    python3 update_python_with_ai/support/lib/grounding_lint.py [--deps dep1 dep2 ...] -- [target files...]

Checks:
  1. No control flow statements (If, IfExp, For, AsyncFor, While, Try, With, Match, Yield, Assert, comprehensions).
  2. No return statements (ast.Return); outcomes must be assigned to local variables and terminate with raise NotImplementedError.
  3. No ellipsis (...) in executable bodies; ellipsis is only allowed in type annotations (e.g. Callable[..., T]).
  4. Every function and method (except __init__ and __initialize__) must terminate strictly with `raise NotImplementedError`.
  5. No dead code statements after terminal `raise NotImplementedError`.
  6. No direct self-recursion (self.foo(...) inside foo).
  7. Every parameter (except self, cls) and return type must have explicit type annotations.
  8. Docstrings are closed strictly to allowed sections (COVERED:, DEFERRED:, DISCHARGED:, etc.).
  9. Prohibited docstring sections (REQUIREMENTS:, ASSUMPTIONS:, etc.) are rejected.
 10. Bullets under requirement sections must start with '- ' and end with a period ('.').
 11. Methods claiming COVERED: must contain proof statements before terminal raise (cannot be bare raise).
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PARTS_DIR = ROOT / "update_with_ai" / "parts"

ALLOWED_DOCSTRING_SECTIONS = {
    "Args:",
    "Returns:",
    "Raises:",
    "Yields:",
    "COVERED:",
    "DEFERRED:",
    "UNCOVERABLE IN GROUNDING (RUNTIME CONTROL FLOW IN LIB):",  # Deprecated; retained for backward compatibility
    "DISCHARGED:",
    "CONSTITUENTS:",
    "INVARIANTS:",
    "PRECONDITIONS:",
    "POSTCONDITIONS:",
}

PROHIBITED_DOCSTRING_SECTIONS = {
    "REQUIREMENTS:",
    "ASSUMPTIONS:",
    "NEW_PREDICATES:",
    "RULES:",
    "GROUNDING_PROVISIONS:",
    "GROUNDING_REQUIREMENTS:",
    "GROUNDING_ASSUMPTIONS:",
    "GROUNDING_IMPLEMENTS:",
    "GROUNDING_ARGUMENT:",
}


def _check_docstring_contracts(
    doc: str, fname: str, node_name: str, node_lineno: int
) -> tuple[list[str], bool, bool]:
    """Validates docstring section structure, bullet format, and period terminations.

    Returns (errors, has_covered, has_deferred).
    """
    errors: list[str] = []
    has_covered = False
    has_deferred = False

    lines = doc.splitlines()
    cur_section: str | None = None

    for offset, raw_line in enumerate(lines):
        line = raw_line.strip()
        line_num = node_lineno + offset

        if not line:
            continue

        # Detect potential section headers
        if line in PROHIBITED_DOCSTRING_SECTIONS:
            errors.append(
                f"{fname}:{line_num}: error: prohibited docstring section '{line}' in '{node_name}'"
            )
            cur_section = None
            continue

        if (line.endswith(":") and re.match(r"^[A-Z_ ]+(\([A-Z_ ]+\))?:$", line)) or line in (
            "Args:",
            "Returns:",
            "Raises:",
            "Yields:",
        ):
            if line in ALLOWED_DOCSTRING_SECTIONS:
                cur_section = line
                if line == "COVERED:":
                    has_covered = True
                elif line == "DEFERRED:":
                    has_deferred = True
            else:
                errors.append(
                    f"{fname}:{line_num}: error: unknown docstring section '{line}' in '{node_name}'"
                )
                cur_section = None
            continue

        if cur_section in (
            "COVERED:",
            "DEFERRED:",
            "UNCOVERABLE IN GROUNDING (RUNTIME CONTROL FLOW IN LIB):",
            "DISCHARGED:",
            "CONSTITUENTS:",
            "INVARIANTS:",
            "PRECONDITIONS:",
            "POSTCONDITIONS:",
        ):
            if not line.startswith("- "):
                # Allow indented sub-bullets or continuation lines if they are bullet points
                if not line.startswith("-"):
                    errors.append(
                        f"{fname}:{line_num}: error: entry under '{cur_section}' must start with '- ': '{line}'"
                    )
            elif cur_section in (
                "COVERED:",
                "DEFERRED:",
                "UNCOVERABLE IN GROUNDING (RUNTIME CONTROL FLOW IN LIB):",
                "DISCHARGED:",
                "INVARIANTS:",
                "PRECONDITIONS:",
                "POSTCONDITIONS:",
            ):
                if not line.endswith("."):
                    errors.append(
                        f"{fname}:{line_num}: error: sentence under '{cur_section}' must end with a period: '{line}'"
                    )

    return errors, has_covered, has_deferred


def _find_ellipsis_in_code(node: ast.AST, fname: str) -> list[str]:
    """Finds ast.Constant(value=Ellipsis) in executable code, ignoring type annotations."""
    errors: list[str] = []

    def visit(n: ast.AST) -> None:
        if isinstance(n, ast.AnnAssign):
            visit(n.target)
            if n.value:
                visit(n.value)
            # Skip n.annotation (type annotation)
            return

        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in n.args.defaults + [kd for kd in n.args.kw_defaults if kd]:
                visit(d)
            # Skip n.returns and arg annotations
            for stmt in n.body:
                visit(stmt)
            return

        # Check for Ellipsis
        if isinstance(n, ast.Constant) and n.value is Ellipsis:
            errors.append(
                f"{fname}:{n.lineno}: error: ellipsis '...' is prohibited in grounding specifications; write straight-line feasibility proofs or 'raise NotImplementedError'"
            )

        for child in ast.iter_child_nodes(n):
            visit(child)

    visit(node)
    return errors


def _check_terminal_raise(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef, fname: str, has_covered: bool
) -> list[str]:
    """Ensures method ends with `raise NotImplementedError` and has proof statements if claiming COVERED:."""
    errors: list[str] = []

    # __init__ and __initialize__ return None and may omit terminal raise
    if func_node.name in ("__init__", "__initialize__"):
        return errors

    body = func_node.body
    # Exclude leading docstring if present
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        executable_stmts = body[1:]
    else:
        executable_stmts = body

    if not executable_stmts:
        errors.append(
            f"{fname}:{func_node.lineno}: error: method '{func_node.name}' must terminate with 'raise NotImplementedError'"
        )
        return errors

    # Check for early raise statements leaving dead code
    for stmt in executable_stmts[:-1]:
        if isinstance(stmt, ast.Raise):
            errors.append(
                f"{fname}:{stmt.lineno}: error: early 'raise' statement is prohibited; grounding proofs are straight-line dataflows"
            )

    last_stmt = executable_stmts[-1]
    if not isinstance(last_stmt, ast.Raise):
        errors.append(
            f"{fname}:{last_stmt.lineno}: error: method '{func_node.name}' must terminate with 'raise NotImplementedError'"
        )
        return errors

    exc = last_stmt.exc
    exc_name: str | None = None
    if isinstance(exc, ast.Name):
        exc_name = exc.id
    elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
        exc_name = exc.func.id

    if exc_name != "NotImplementedError":
        errors.append(
            f"{fname}:{last_stmt.lineno}: error: method '{func_node.name}' must raise 'NotImplementedError', not '{exc_name or 'unnamed exception'}'"
        )

    # Check COVERED: proof statements
    proof_stmts = [
        s for s in executable_stmts if not (isinstance(s, ast.Raise) and s is last_stmt)
    ]
    if has_covered and not proof_stmts:
        errors.append(
            f"{fname}:{func_node.lineno}: error: method '{func_node.name}' claims 'COVERED:' but has no proof statements before 'raise NotImplementedError'; use 'DEFERRED:' if uncovering abstract member"
        )

    return errors


def _check_self_recursion(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef, fname: str
) -> list[str]:
    """Ensures method does not directly call itself (self.foo(...))."""
    errors: list[str] = []
    if not func_node.args.args or func_node.args.args[0].arg != "self":
        return errors

    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
            ):
                if node.func.attr == func_node.name:
                    errors.append(
                        f"{fname}:{node.lineno}: error: direct self-recursion 'self.{func_node.name}(...)' is prohibited in grounding specifications"
                    )
    return errors


def _check_control_flow(tree: ast.AST, fname: str) -> list[str]:
    """Ensures no conditional, loop, try, with, match, yield, assert, or comprehension statements."""
    errors: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            errors.append(
                f"{fname}:{node.lineno}: error: conditional statement 'if' is prohibited in grounding specifications; straight-line feasibility proofs only"
            )
        elif isinstance(node, ast.IfExp):
            errors.append(
                f"{fname}:{node.lineno}: error: conditional ternary expression '... if ... else ...' is prohibited in grounding specifications; straight-line feasibility proofs only"
            )
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            errors.append(
                f"{fname}:{node.lineno}: error: loop statement 'for' is prohibited in grounding specifications; use single-element collection helpers (key, value, only_elem)"
            )
        elif isinstance(node, ast.While):
            errors.append(
                f"{fname}:{node.lineno}: error: loop statement 'while' is prohibited in grounding specifications; use single-element collection helpers (key, value, only_elem)"
            )
        elif isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            # Only flag Try inside function/method bodies (allow module-level import fallback)
            # Find if enclosing scope is a function
            lineno = getattr(node, "lineno", 0)
            errors.append(
                f"{fname}:{lineno}: error: 'try' block is prohibited in grounding specifications; straight-line feasibility proofs only"
            )
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            errors.append(
                f"{fname}:{node.lineno}: error: 'with' statement is prohibited in grounding specifications; straight-line feasibility proofs only"
            )
        elif isinstance(node, getattr(ast, "Match", (type(None),))):
            lineno = getattr(node, "lineno", 0)
            errors.append(
                f"{fname}:{lineno}: error: 'match' statement is prohibited in grounding specifications; straight-line feasibility proofs only"
            )
        elif isinstance(node, (ast.Yield, ast.YieldFrom)):
            errors.append(
                f"{fname}:{node.lineno}: error: 'yield' expression is prohibited in grounding specifications; straight-line feasibility proofs only"
            )
        elif isinstance(node, ast.Assert):
            errors.append(
                f"{fname}:{node.lineno}: error: 'assert' statement is prohibited in grounding specifications; assign condition evaluations to typed local variables instead"
            )
        elif isinstance(
            node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            errors.append(
                f"{fname}:{node.lineno}: error: comprehension is prohibited in grounding specifications; use single-element collection helpers"
            )
        elif isinstance(node, ast.Return):
            errors.append(
                f"{fname}:{node.lineno}: error: 'return' statement is prohibited in grounding specifications; assign proof values to local variables and terminate with 'raise NotImplementedError'"
            )

    return errors


def lint_grounding_file(file_path: Path) -> list[str]:
    fname = file_path.name
    stem = file_path.stem
    is_asm = stem.endswith("_asm")
    is_ext = stem.endswith("_ext")

    errors: list[str] = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{fname}:1: error: cannot read file: {e}"]

    if not content.strip():
        return [f"{fname}:1: error: empty grounding specification file"]

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return [f"{fname}:{e.lineno or 1}: error: syntax error: {e.msg}"]

    # 1. Check prohibited control flow and return statements
    # Note: For assembly specs, allow module-level try/except for import fallback
    control_flow_errors = _check_control_flow(tree, fname)
    if is_asm:
        # Filter out module-level Try from assembly files (used for relative vs absolute import fallback)
        filtered_cf: list[str] = []
        for err in control_flow_errors:
            if "error: 'try' block is prohibited" in err:
                # Check line number to see if it is top-level
                match = re.search(r":(\d+):", err)
                if match:
                    lineno = int(match.group(1))
                    for stmt in tree.body:
                        if isinstance(stmt, ast.Try) and stmt.lineno == lineno:
                            break
                    else:
                        filtered_cf.append(err)
            else:
                filtered_cf.append(err)
        control_flow_errors = filtered_cf

    errors.extend(control_flow_errors)

    # 2. Check prohibited ellipsis (...)
    errors.extend(_find_ellipsis_in_code(tree, fname))

    # 3. Check functions and methods
    for node in tree.body:
        # Module-level docstring
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            doc_errs, _, _ = _check_docstring_contracts(
                node.value.value, fname, fname, node.lineno
            )
            errors.extend(doc_errs)
            continue

        # Top-level functions (e.g. __initialize__ or _ext functions)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check type annotations
            if node.returns is None:
                errors.append(
                    f"{fname}:{node.lineno}: error: function '{node.name}' is missing return type annotation"
                )
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                if arg.arg not in ("self", "cls") and arg.annotation is None:
                    errors.append(
                        f"{fname}:{arg.lineno}: error: parameter '{arg.arg}' in function '{node.name}' is missing type annotation"
                    )

            # Check docstrings
            doc = ast.get_docstring(node, clean=False)
            has_covered = False
            if doc:
                d_errs, has_covered, _ = _check_docstring_contracts(
                    doc, fname, node.name, node.lineno
                )
                errors.extend(d_errs)

            # Check terminal raise
            errors.extend(_check_terminal_raise(node, fname, has_covered))

        # Classes
        elif isinstance(node, ast.ClassDef):
            # Class docstring
            cls_doc = ast.get_docstring(node, clean=False)
            if cls_doc:
                d_errs, _, _ = _check_docstring_contracts(
                    cls_doc, fname, node.name, node.lineno
                )
                errors.extend(d_errs)

            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check type annotations
                    if member.returns is None:
                        errors.append(
                            f"{fname}:{member.lineno}: error: method '{node.name}.{member.name}' is missing return type annotation"
                        )
                    for arg in (
                        member.args.posonlyargs
                        + member.args.args
                        + member.args.kwonlyargs
                    ):
                        if arg.arg not in ("self", "cls") and arg.annotation is None:
                            errors.append(
                                f"{fname}:{arg.lineno}: error: parameter '{arg.arg}' in '{node.name}.{member.name}' is missing type annotation"
                            )

                    # Check docstrings
                    m_doc = ast.get_docstring(member, clean=False)
                    m_has_covered = False
                    if m_doc:
                        d_errs, m_has_covered, _ = _check_docstring_contracts(
                            m_doc, fname, f"{node.name}.{member.name}", member.lineno
                        )
                        errors.extend(d_errs)

                    # Check terminal raise
                    errors.extend(
                        _check_terminal_raise(member, fname, m_has_covered)
                    )

                    # Check self recursion
                    errors.extend(_check_self_recursion(member, fname))

    return errors


def main() -> int:
    args = sys.argv[1:]
    deps: list[Path] = []
    targets: list[Path] = []

    if "--" in args:
        dash_idx = args.index("--")
        pre_args = args[:dash_idx]
        post_args = args[dash_idx + 1 :]
        if "--deps" in pre_args:
            deps_idx = pre_args.index("--deps")
            deps = [Path(p) for p in pre_args[deps_idx + 1 :]]
        targets = [Path(p) for p in post_args]
    elif "--deps" in args:
        deps_idx = args.index("--deps")
        deps = [Path(p) for p in args[deps_idx + 1 :]]
    else:
        targets = [Path(p) for p in args]

    if not targets:
        if PARTS_DIR.exists():
            targets = sorted(PARTS_DIR.glob("*/grounding/*.py"))
        else:
            print("Error: parts directory does not exist", file=sys.stderr)
            return 1

    all_errors: list[str] = []
    for f in targets:
        errs = lint_grounding_file(f)
        all_errors.extend(errs)

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        print(
            f"\n[FAIL] Found {len(all_errors)} grounding specification errors.",
            file=sys.stderr,
        )
        return 1

    print(
        f"[OK] {len(targets)} grounding specifications passed structural & contract lint."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
