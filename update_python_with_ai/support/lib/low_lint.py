#!/usr/bin/env python3
"""
low_lint.py — structural and contract linter for Low-Level Specifications (low/*.pyi).

Usage:
    python3 update_python_with_ai/support/lib/low_lint.py [files...]
    python3 update_python_with_ai/support/lib/low_lint.py [--deps dep1 dep2 ...] -- [target files...]

Checks:
  1. File type handling:
     - External specs (*_ext.pyi): Strictly a module docstring with required markdown sections, no Python AST statements.
     - Assembly specs (*_asm.pyi): Strictly imports, optional module docstring, and `def __initialize__() -> None:` with `CONSTITUENTS:`.
     - Standard specs (*.pyi, *_impl.pyi): Pure structural stubs without executable statements.
  2. Free-floating `#` comments outside docstrings are prohibited.
  3. Classes must be decorated with ontological markers: `@singleton_type`, `@poly_type`, `@data_type`, `@variant`, or `@dataclass`.
  4. Service classes (@singleton_type, @poly_type) members must be decorated with either `@property` or `@operation` (and optionally `@override`).
  5. Property methods must take strictly `self`; operation methods must take `self` as the first parameter.
  6. Method parameters and return types must declare explicit type annotations; bodies must be strictly `...`.
  7. Docstrings are closed strictly to allowed sections (`Args:`, `Returns:`, `CONSTITUENTS:`, `INVARIANTS:`, `PRECONDITIONS:`, `POSTCONDITIONS:`).
  8. Prohibited legacy sections (`REQUIREMENTS:`, `ASSUMPTIONS:`, `NEW_PREDICATES:`, `RULES:`, `GROUNDING_*`) are rejected.
  9. Contract entries under `CONSTITUENTS:`, `INVARIANTS:`, `PRECONDITIONS:`, `POSTCONDITIONS:` must start with `- `.
 10. Contract sentences under `INVARIANTS:`, `PRECONDITIONS:`, and `POSTCONDITIONS:` must end with a period (`.`).
 11. Class invariants must not be repeated as operation preconditions in the same class.
 12. In implementation specifications (*_impl.pyi), top-level imports declare all non-external modules specified in front-matter 'imports:' of the planning specification (planning/<name>_impl.md).
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PARTS_DIR = ROOT / "update_with_ai" / "parts"

ALLOWED_DOCSTRING_SECTIONS = {
    "Args:",
    "Returns:",
    "CONSTITUENTS:",
    "INVARIANTS:",
    "PRECONDITIONS:",
    "POSTCONDITIONS:",
    "GROUNDING:",
    "Raises:",
    "Yields:",
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
}

CLASS_DECORATORS = {
    "singleton_type",
    "poly_type",
    "data_type",
    "variant",
    "dataclass",
}


def _check_comments(content: str, fname: str) -> list[str]:
    """Ensures no free-floating # comments outside docstrings."""
    errors: list[str] = []
    in_triple = False
    triple_delim = ""
    in_metadata = False

    for line_no, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if stripped == "# --- CLEANROOM METADATA ---":
            in_metadata = True
            continue
        if in_metadata:
            if stripped == "# --- END CLEANROOM METADATA ---":
                in_metadata = False
            continue
        # Track triple-quote boundary
        idx = 0
        while idx < len(stripped):
            if not in_triple:
                if stripped[idx : idx + 3] in ('"""', "'''"):
                    in_triple = True
                    triple_delim = stripped[idx : idx + 3]
                    idx += 3
                    continue
                elif stripped[idx] == "#":
                    errors.append(
                        f"{fname}:{line_no}: error: free-floating '#' comment prohibited in low-level specifications: '{stripped}'"
                    )
                    break
            else:
                if stripped[idx : idx + 3] == triple_delim:
                    in_triple = False
                    triple_delim = ""
                    idx += 3
                    continue
            idx += 1

    return errors


def _is_enum_class(node: ast.ClassDef) -> bool:
    """Checks whether a class inherits from Enum."""
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Enum":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Enum":
            return True
    return False


def _check_docstring_contracts(
    doc: str, fname: str, node_name: str, node_lineno: int, is_impl: bool = False
) -> tuple[list[str], set[str], set[str]]:
    """Validates docstring section structure, bullet format, and period terminations.

    Returns (errors, invariants_set, preconditions_set).
    """
    errors: list[str] = []
    invariants: set[str] = set()
    preconditions: set[str] = set()

    lines = doc.splitlines()
    cur_section: str | None = None
    cur_bullet: str | None = None
    cur_bullet_lineno: int = 0

    def finish_bullet():
        nonlocal cur_bullet, cur_bullet_lineno
        if cur_bullet is not None:
            if cur_section in ("INVARIANTS:", "PRECONDITIONS:", "POSTCONDITIONS:", "GROUNDING:"):
                if not cur_bullet.endswith("."):
                    errors.append(
                        f"{fname}:{cur_bullet_lineno}: error: sentence under '{cur_section}' must end with a period: '{cur_bullet}'"
                    )
            if cur_section == "INVARIANTS:":
                invariants.add(cur_bullet)
            elif cur_section == "PRECONDITIONS:":
                preconditions.add(cur_bullet)
            cur_bullet = None

    for offset, raw_line in enumerate(lines):
        line = raw_line.strip()
        line_num = node_lineno + offset

        if not line:
            finish_bullet()
            continue

        # Detect potential section headers
        if line in PROHIBITED_DOCSTRING_SECTIONS:
            finish_bullet()
            errors.append(
                f"{fname}:{line_num}: error: prohibited docstring section '{line}' in '{node_name}'"
            )
            cur_section = None
            continue

        if (line.endswith(":") and re.match(r"^[A-Z_]+:$", line)) or line in (
            "Args:",
            "Returns:",
            "Raises:",
            "Yields:",
        ):
            finish_bullet()
            if line in ALLOWED_DOCSTRING_SECTIONS:
                if line == "GROUNDING:" and not is_impl:
                    errors.append(
                        f"{fname}:{line_num}: error: 'GROUNDING:' section only permitted in implementation specifications (*_impl.pyi) in '{node_name}'"
                    )
                    cur_section = None
                else:
                    cur_section = line
            else:
                errors.append(
                    f"{fname}:{line_num}: error: unknown docstring section '{line}' in '{node_name}'"
                )
                cur_section = None
            continue

        if cur_section in (
            "INVARIANTS:",
            "PRECONDITIONS:",
            "POSTCONDITIONS:",
            "CONSTITUENTS:",
            "GROUNDING:",
        ):
            if line.startswith("- "):
                finish_bullet()
                cur_bullet = line[2:].strip()
                cur_bullet_lineno = line_num
            elif cur_bullet is not None and (raw_line.startswith("  ") or raw_line.startswith("\t") or raw_line.startswith("    ")):
                cur_bullet += " " + line
            else:
                finish_bullet()
                errors.append(
                    f"{fname}:{line_num}: error: entry under '{cur_section}' must start with '- ': '{line}'"
                )

    finish_bullet()
    return errors, invariants, preconditions


def lint_low_file(file_path: Path) -> list[str]:
    fname = file_path.name
    stem = file_path.stem
    is_ext = stem.endswith("_ext")
    is_asm = stem.endswith("_asm")
    is_impl = stem.endswith("_impl")

    errors: list[str] = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{fname}:1: error: cannot read file: {e}"]

    if not content.strip():
        return [f"{fname}:1: error: empty low-level specification file"]

    # 1. Comment checks (no free-floating # comments)
    errors.extend(_check_comments(content, fname))

    # 2. AST parsing
    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return [f"{fname}:{e.lineno or 1}: error: syntax error: {e.msg}"]

    # 3. External Specification handling (*_ext.pyi)
    if is_ext:
        non_doc_stmts = [
            s
            for s in tree.body
            if not (
                isinstance(s, ast.Expr)
                and isinstance(s.value, ast.Constant)
                and isinstance(s.value.value, str)
            )
        ]
        if non_doc_stmts:
            first_non_doc = non_doc_stmts[0]
            errors.append(
                f"{fname}:{first_non_doc.lineno}: error: external specification stubs (_ext.pyi) must contain strictly a module docstring without Python AST code"
            )
        doc = ast.get_docstring(tree) or ""
        required_ext_sections = [
            "## External Mechanics & API Documentation",
            "## Build Dependencies",
            "## Usage Snippets",
        ]
        for sec in required_ext_sections:
            if sec not in doc:
                errors.append(
                    f"{fname}:1: error: external specification missing required section '{sec}'"
                )
        return errors

    # 4. Assembly Specification handling (*_asm.pyi)
    if is_asm:
        has_init = False
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            if isinstance(node, ast.FunctionDef) and node.name == "__initialize__":
                has_init = True
                if node.decorator_list:
                    errors.append(
                        f"{fname}:{node.lineno}: error: assembly '__initialize__()' must have no decorators"
                    )
                if node.args.args:
                    errors.append(
                        f"{fname}:{node.lineno}: error: assembly '__initialize__()' must take no parameters"
                    )
                if node.returns is None or ast.unparse(node.returns) != "None":
                    errors.append(
                        f"{fname}:{node.lineno}: error: assembly '__initialize__()' return type annotation must be 'None'"
                    )
                doc = ast.get_docstring(node)
                if not doc or "CONSTITUENTS:" not in doc:
                    errors.append(
                        f"{fname}:{node.lineno}: error: assembly '__initialize__()' docstring must contain 'CONSTITUENTS:' section"
                    )
                else:
                    d_errs, _, _ = _check_docstring_contracts(
                        doc, fname, "__initialize__", node.lineno
                    )
                    errors.extend(d_errs)
                # Check body is strictly ...
                body_stmts = [
                    s
                    for s in node.body
                    if not (
                        isinstance(s, ast.Expr)
                        and isinstance(s.value, ast.Constant)
                        and isinstance(s.value.value, str)
                    )
                ]
                if not (
                    len(body_stmts) == 1
                    and isinstance(body_stmts[0], ast.Expr)
                    and isinstance(body_stmts[0].value, ast.Constant)
                    and body_stmts[0].value.value is ...
                ):
                    errors.append(
                        f"{fname}:{node.lineno}: error: assembly '__initialize__()' body must be strictly '...'"
                    )
            else:
                errors.append(
                    f"{fname}:{node.lineno}: error: assembly specification may only declare imports and 'def __initialize__() -> None:'"
                )

        if not has_init:
            errors.append(
                f"{fname}:1: error: assembly specification missing 'def __initialize__() -> None:'"
            )
        return errors

    # 5. Standard Specification handling (*.pyi and *_impl.pyi)
    # Validate module docstring if present
    module_doc = ast.get_docstring(tree)
    if module_doc:
        d_errs, _, _ = _check_docstring_contracts(module_doc, fname, "module", 1, is_impl=is_impl)
        errors.extend(d_errs)

    # 5a. Implementation Specification Planning Import Parity Audit (*_impl.pyi)
    if is_impl:
        plan_path = file_path.parent.parent / "planning" / f"{stem}.md"
        if not plan_path.exists():
            candidates = list(PARTS_DIR.glob(f"*/planning/{stem}.md"))
            if candidates:
                plan_path = candidates[0]
            elif not candidates:
                ws_plan = list(Path(file_path.anchor).glob(f"**/parts/*/planning/{stem}.md"))
                if ws_plan:
                    plan_path = ws_plan[0]

        if plan_path.exists():
            tree_imports: set[str] = set()
            for stmt in tree.body:
                if isinstance(stmt, ast.Import):
                    for a in stmt.names:
                        tree_imports.add(a.name)
                elif isinstance(stmt, ast.ImportFrom):
                    if stmt.module:
                        tree_imports.add(stmt.module)

            try:
                plan_content = plan_path.read_text(encoding="utf-8")
                for p_line in plan_content.splitlines():
                    p_stripped = p_line.strip()
                    if p_stripped.startswith("imports:"):
                        p_raw = p_stripped[len("imports:") :].strip()
                        if p_raw:
                            for p_imp in [i.strip() for i in p_raw.split(",") if i.strip()]:
                                if not p_imp.endswith("_ext") and p_imp not in tree_imports:
                                    errors.append(
                                        f"{fname}:1: error: implementation stub missing import for '{p_imp}' declared in '{plan_path.name}'"
                                    )
                        break
            except OSError:
                pass

    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, getattr(ast, "TypeAlias", ()))):
            # Type alias or constant
            continue
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "__orphan__":
            # Top-level orphan contract
            doc = ast.get_docstring(stmt)
            if not doc:
                errors.append(
                    f"{fname}:{stmt.lineno}: error: '__orphan__()' must have a docstring with 'POSTCONDITIONS:'"
                )
            else:
                d_errs, _, _ = _check_docstring_contracts(
                    doc, fname, "__orphan__", stmt.lineno, is_impl=is_impl
                )
                errors.extend(d_errs)
            continue
        if not isinstance(stmt, ast.ClassDef):
            errors.append(
                f"{fname}:{stmt.lineno}: error: unsupported top-level statement: {type(stmt).__name__}"
            )
            continue

        # Class validation
        cls_node = stmt
        is_enum = _is_enum_class(cls_node)
        decs: list[str] = []
        for d in cls_node.decorator_list:
            if isinstance(d, ast.Name):
                decs.append(d.id)
            elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name):
                decs.append(d.func.id)

        recognized_decs = [d for d in decs if d in CLASS_DECORATORS]
        if not recognized_decs and not is_enum:
            errors.append(
                f"{fname}:{cls_node.lineno}: error: class '{cls_node.name}' missing Cleanroom structural decorator (@singleton_type, @poly_type, @data_type, @variant, or @dataclass)"
            )

        is_service = any(d in ("singleton_type", "poly_type") for d in recognized_decs)

        # Validate class docstring contracts
        cls_doc = ast.get_docstring(cls_node)
        cls_invariants: set[str] = set()
        if cls_doc:
            d_errs, cls_invariants, _ = _check_docstring_contracts(
                cls_doc, fname, cls_node.name, cls_node.lineno, is_impl=is_impl
            )
            errors.extend(d_errs)

        # Validate members
        for member in cls_node.body:
            if is_enum:
                if isinstance(member, (ast.Assign, ast.AnnAssign, ast.Expr)):
                    continue
            if (
                isinstance(member, ast.Expr)
                and isinstance(member.value, ast.Constant)
                and isinstance(member.value.value, str)
            ):
                continue
            if (
                isinstance(member, ast.Expr)
                and isinstance(member.value, ast.Constant)
                and member.value.value is ...
            ):
                continue
            if isinstance(member, ast.AnnAssign):
                continue
            if not isinstance(member, ast.FunctionDef):
                errors.append(
                    f"{fname}:{member.lineno}: error: unsupported member statement in class '{cls_node.name}': {type(member).__name__}"
                )
                continue

            # Method validation
            func = member
            m_decs: list[str] = []
            for d in func.decorator_list:
                if isinstance(d, ast.Name):
                    m_decs.append(d.id)
                elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name):
                    m_decs.append(d.func.id)

            has_prop = "property" in m_decs
            has_op = "operation" in m_decs

            if is_service:
                if not (has_prop or has_op):
                    errors.append(
                        f"{fname}:{func.lineno}: error: service member '{cls_node.name}.{func.name}' must be decorated with either @property or @operation"
                    )
                elif has_prop and has_op:
                    errors.append(
                        f"{fname}:{func.lineno}: error: member '{cls_node.name}.{func.name}' cannot be decorated with both @property and @operation"
                    )

            if has_prop:
                arg_names = [a.arg for a in func.args.args]
                if arg_names != ["self"]:
                    errors.append(
                        f"{fname}:{func.lineno}: error: @property '{cls_node.name}.{func.name}' must take strictly 'self'"
                    )

            if has_op:
                arg_names = [a.arg for a in func.args.args]
                if not arg_names or arg_names[0] != "self":
                    errors.append(
                        f"{fname}:{func.lineno}: error: @operation '{cls_node.name}.{func.name}' must take 'self' as first parameter"
                    )

            # Check parameter type annotations
            for arg in func.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                if arg.annotation is None:
                    errors.append(
                        f"{fname}:{func.lineno}: error: parameter '{arg.arg}' of '{cls_node.name}.{func.name}' missing type annotation"
                    )

            # Check return type annotation
            if func.returns is None:
                errors.append(
                    f"{fname}:{func.lineno}: error: member '{cls_node.name}.{func.name}' missing return type annotation"
                )

            # Check method body is strictly ...
            m_body_stmts = [
                s
                for s in func.body
                if not (
                    isinstance(s, ast.Expr)
                    and isinstance(s.value, ast.Constant)
                    and isinstance(s.value.value, str)
                )
            ]
            if not (
                len(m_body_stmts) == 1
                and isinstance(m_body_stmts[0], ast.Expr)
                and isinstance(m_body_stmts[0].value, ast.Constant)
                and m_body_stmts[0].value.value is ...
            ):
                errors.append(
                    f"{fname}:{func.lineno}: error: member '{cls_node.name}.{func.name}' body must be strictly '...'"
                )

            # Validate method docstrings
            m_doc = ast.get_docstring(func)
            if m_doc:
                d_errs, _, m_preconditions = _check_docstring_contracts(
                    m_doc, fname, f"{cls_node.name}.{func.name}", func.lineno, is_impl=is_impl
                )
                errors.extend(d_errs)

                # Check invariant repetition in preconditions
                repeated = cls_invariants.intersection(m_preconditions)
                if repeated:
                    for rep in repeated:
                        errors.append(
                            f"{fname}:{func.lineno}: error: type invariant repeated as precondition in '{cls_node.name}.{func.name}': '{rep}'"
                        )

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
            targets = sorted(PARTS_DIR.glob("*/low/*.pyi"))
        else:
            print("Error: parts directory does not exist", file=sys.stderr)
            return 1

    all_errors: list[str] = []
    for f in targets:
        errs = lint_low_file(f)
        all_errors.extend(errs)

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        print(
            f"\n[FAIL] Found {len(all_errors)} low-level specification errors.",
            file=sys.stderr,
        )
        return 1

    print(
        f"[OK] {len(targets)} low-level specifications passed structural & contract lint."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
