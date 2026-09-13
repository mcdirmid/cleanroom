#!/usr/bin/env python3
"""Cleanroom Grounding Specification Unified Tool (grounding_tool.py).

Unifies specification validation and code generation into a single pipeline:
1. Lint: Validates single-file AST syntax, pure ellipsis bodies, decorators, docstrings, and typing.
2. Link: Validates cross-module symbol imports, base class resolution, and lifecycle tier isolation.
3. Inherit & Sync: Idempotently synchronizes ancestor requirements, assumptions, and stubs in place.

Modes:
  --check    : Validates lint rules, import links, and verifies zero inheritance drift. (Default)
  --sync     : Validates lint/links, then synchronizes inherited requirements/stubs in place.
  --out-dir  : Emits compiled grounding specifications with inherited members to a directory.
  --lint-only: Runs only the static AST linter.
  --link-only: Runs only the cross-module linker.
"""

import argparse
import ast
import copy
import difflib
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, cast

PRIMARY_KINDS = {"singleton_type", "poly_type", "data_type", "variant"}
ALLOWED_MEMBER_DECORATORS = {"property", "operation", "override"}
BUILTIN_TYPES = {
    "str",
    "int",
    "bool",
    "float",
    "None",
    "Any",
    "Type",
    "type",
    "object",
    "bytes",
    "Optional",
    "Union",
    "Tuple",
    "List",
    "Set",
    "Dict",
    "Sequence",
    "Mapping",
    "Callable",
    "Iterable",
    "Exception",
    "Protocol",
}
COMMON_TYPING_SYMBOLS = {
    "Optional",
    "Union",
    "Tuple",
    "List",
    "Set",
    "Sequence",
    "Any",
    "Type",
    "Dict",
    "Callable",
    "Iterable",
    "Mapping",
    "Protocol",
}
COMMON_BUILTINS = {
    "int",
    "str",
    "bool",
    "float",
    "None",
    "bytes",
    "object",
    "Exception",
}
FRAMEWORK_SYMBOLS = {
    "singleton_type",
    "poly_type",
    "data_type",
    "variant",
    "operation",
    "override",
}
DATACLASS_SYMBOLS = {"dataclass"}


class Diagnostic:
    """Standard compiler diagnostic message."""

    def __init__(self, filename: str, line: int, col: int, message: str):
        self.filename = filename
        self.line = line
        self.col = col
        self.message = message

    def __str__(self) -> str:
        return f"{self.filename}:{self.line}:{self.col}: error: {self.message}"

    def __repr__(self) -> str:
        return (
            f"Diagnostic({self.filename!r}, {self.line}, {self.col}, {self.message!r})"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, Diagnostic):
            return False
        return (
            self.filename == other.filename
            and self.line == other.line
            and self.col == other.col
            and self.message == other.message
        )


# Backward compatibility alias
LinkDiagnostic = Diagnostic


class DocstringContract:
    """Parses and formats specification docstring sections."""

    def __init__(self, raw: str):
        self.raw = raw
        self.purpose: str = ""
        self.inheritance: List[str] = []
        self.fresh_assumptions: List[str] = []
        self.inherited_assumptions: Dict[str, List[str]] = {}
        self.fresh_requirements: List[str] = []
        self.inherited_requirements: Dict[str, List[str]] = {}
        self.grounding_argument: str = ""
        self._parse(raw)

    def _parse(self, doc: str):
        lines = [line.rstrip() for line in doc.strip().splitlines()]
        current_section = None
        current_ancestor = None
        purpose_lines = []
        grounding_arg_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped == "PURPOSE:":
                current_section = "PURPOSE"
                continue
            elif stripped == "INHERITANCE:":
                current_section = "INHERITANCE"
                continue
            elif stripped in ("FRESH_ASSUMPTIONS:", "ASSUMPTIONS:"):
                current_section = "FRESH_ASSUMPTIONS"
                continue
            elif stripped == "INHERITED_ASSUMPTIONS:":
                current_section = "INHERITED_ASSUMPTIONS"
                continue
            elif stripped in ("FRESH_REQUIREMENTS:", "REQUIREMENTS:"):
                current_section = "FRESH_REQUIREMENTS"
                continue
            elif stripped == "INHERITED_REQUIREMENTS:":
                current_section = "INHERITED_REQUIREMENTS"
                continue
            elif stripped == "GROUNDING_ARGUMENT:":
                current_section = "GROUNDING_ARGUMENT"
                continue
            elif stripped.startswith("INHERITED FROM "):
                current_section = "LEGACY_INHERITED_FROM"
                current_ancestor = stripped[len("INHERITED FROM ") :].rstrip(":")
                continue

            if current_section == "PURPOSE" or current_section is None:
                purpose_lines.append(stripped)
            elif current_section == "INHERITANCE":
                item = stripped[2:].strip() if stripped.startswith("- ") else stripped
                self.inheritance.append(item)
            elif current_section == "FRESH_ASSUMPTIONS":
                item = stripped[2:].strip() if stripped.startswith("- ") else stripped
                self.fresh_assumptions.append(item)
            elif current_section == "FRESH_REQUIREMENTS":
                item = stripped[2:].strip() if stripped.startswith("- ") else stripped
                self.fresh_requirements.append(item)
            elif current_section == "INHERITED_ASSUMPTIONS":
                m = re.match(r"^-\s*\[(.*?)\]\s*(.*)$", stripped)
                if m:
                    anc = m.group(1).strip()
                    stmt = m.group(2).strip()
                    self.inherited_assumptions.setdefault(anc, []).append(stmt)
                else:
                    item = (
                        stripped[2:].strip() if stripped.startswith("- ") else stripped
                    )
                    self.inherited_assumptions.setdefault("Parent", []).append(item)
            elif current_section == "INHERITED_REQUIREMENTS":
                m = re.match(r"^-\s*\[(.*?)\]\s*(.*)$", stripped)
                if m:
                    anc = m.group(1).strip()
                    stmt = m.group(2).strip()
                    self.inherited_requirements.setdefault(anc, []).append(stmt)
                else:
                    item = (
                        stripped[2:].strip() if stripped.startswith("- ") else stripped
                    )
                    self.inherited_requirements.setdefault("Parent", []).append(item)
            elif current_section == "GROUNDING_ARGUMENT":
                grounding_arg_lines.append(stripped)
            elif current_section == "LEGACY_INHERITED_FROM" and current_ancestor:
                item = stripped[2:].strip() if stripped.startswith("- ") else stripped
                self.inherited_requirements.setdefault(current_ancestor, []).append(
                    item
                )

        self.purpose = " ".join(purpose_lines)
        self.grounding_argument = "\n".join(grounding_arg_lines)

    def wipe_inherited(self):
        """Wipes all previously computed inherited assumptions and requirements."""
        self.inherited_assumptions.clear()
        self.inherited_requirements.clear()

    def to_docstring(self) -> str:
        sections = []
        if self.purpose:
            sections.append(f"PURPOSE:\n{self.purpose}")
        if self.inheritance:
            items = "\n".join(f"- {i}" for i in self.inheritance)
            sections.append(f"INHERITANCE:\n{items}")
        if self.fresh_assumptions:
            items = "\n".join(f"- {a}" for a in self.fresh_assumptions)
            sections.append(f"FRESH_ASSUMPTIONS:\n{items}")

        inh_assump_lines = []
        for anc, items in self.inherited_assumptions.items():
            for item in items:
                inh_assump_lines.append(f"- [{anc}] {item}")
        if inh_assump_lines:
            sections.append(f"INHERITED_ASSUMPTIONS:\n" + "\n".join(inh_assump_lines))

        if self.fresh_requirements:
            items = "\n".join(f"- {r}" for r in self.fresh_requirements)
            sections.append(f"FRESH_REQUIREMENTS:\n{items}")

        inh_req_lines = []
        for anc, items in self.inherited_requirements.items():
            for item in items:
                inh_req_lines.append(f"- [{anc}] {item}")
        if inh_req_lines:
            sections.append(f"INHERITED_REQUIREMENTS:\n" + "\n".join(inh_req_lines))

        if self.grounding_argument:
            sections.append(f"GROUNDING_ARGUMENT:\n{self.grounding_argument}")

        if not sections:
            return ""
        body = "\n\n".join(sections)
        return f"\n{body}\n"


class SpecLintVisitor(ast.NodeVisitor):
    """Pass 1: Static AST validator for grounding stubs."""

    def __init__(self, filename: str):
        self.filename = filename
        self.diagnostics: List[Diagnostic] = []
        self.declared_symbols: Set[str] = set()
        self.imported_symbols: Set[str] = set()
        self.imported_modules: Set[str] = set()
        self.class_kinds: Dict[str, str] = {}
        self.class_dataclass_init: Dict[str, Optional[bool]] = {}
        self.class_has_init: Dict[str, bool] = {}
        self.current_class: Optional[str] = None
        self.current_class_kind: Optional[str] = None
        self.current_class_properties: int = 0
        self.current_class_methods: int = 0
        self._current_module_body: List[ast.stmt] = []

    def add_error(self, node: ast.AST, message: str):
        line = getattr(node, "lineno", 1)
        col = getattr(node, "col_offset", 0)
        self.diagnostics.append(Diagnostic(self.filename, line, col, message))

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imported_modules.add(alias.asname or alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            name = alias.asname or alias.name
            self.imported_symbols.add(name)

    def _collect_top_level_symbols(self, tree: ast.Module):
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self.declared_symbols.add(node.name)

    def visit_Module(self, node: ast.Module):
        if str(self.filename).endswith("_ext.pyi"):
            doc = ast.get_docstring(node)
            if doc and "## External Mechanics & API Documentation" in doc:
                for req_sec in (
                    "## External Mechanics & API Documentation",
                    "## Build Dependencies",
                    "## Usage Snippets",
                ):
                    if req_sec not in doc:
                        self.add_error(
                            node,
                            f"External specification (_ext.pyi) missing required section '{req_sec}' in module docstring.",
                        )
                return

        self._current_module_body = node.body
        self._collect_top_level_symbols(node)

        orphan_count = 0
        for stmt in node.body:
            if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.ClassDef)):
                continue
            elif (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                continue  # Module docstring
            elif isinstance(stmt, ast.FunctionDef) and stmt.name == "__orphan__":
                orphan_count += 1
                if orphan_count > 1:
                    self.add_error(
                        stmt,
                        "Only one '__orphan__' function is permitted per specification module.",
                    )
                continue
            elif (
                isinstance(stmt, ast.FunctionDef)
                and stmt.name in ("__initialize__", "_initialize_")
                and str(self.filename).endswith("_asm.pyi")
            ):
                continue
            else:
                self.add_error(
                    stmt,
                    f"Prohibited top-level statement '{type(stmt).__name__}'. Only imports, class declarations, and '__orphan__' allowed.",
                )

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        prev_class = self.current_class
        prev_kind = self.current_class_kind
        prev_props = self.current_class_properties
        prev_methods = self.current_class_methods

        self.current_class = node.name
        self.current_class_properties = 0
        self.current_class_methods = 0

        # Decorators
        kinds = []
        has_dataclass = False
        dataclass_init: Optional[bool] = None
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                func_id = ""
                if isinstance(dec.func, ast.Name):
                    func_id = dec.func.id
                elif isinstance(dec.func, ast.Attribute):
                    func_id = dec.func.attr

                if func_id == "dataclass":
                    has_dataclass = True
                    for kw in dec.keywords:
                        if kw.arg == "init" and isinstance(kw.value, ast.Constant):
                            dataclass_init = bool(kw.value.value)
                    continue
                elif func_id == "singleton_type":
                    kinds.append("singleton_type")
                    if (
                        len(dec.args) == 1
                        and isinstance(dec.args[0], ast.Constant)
                        and dec.args[0].value in ("system", "agent_session")
                        and not dec.keywords
                    ):
                        pass
                    else:
                        self.add_error(
                            dec,
                            '@singleton_type must specify a valid lifecycle tier: @singleton_type("system") or @singleton_type("agent_session").',
                        )
                elif func_id == "poly_type":
                    kinds.append("poly_type")
                    self.add_error(
                        dec,
                        "@poly_type does not take lifecycle arguments because polymorphic types do not correspond to concrete runtime objects.",
                    )
                elif func_id in PRIMARY_KINDS:
                    kinds.append(func_id)
                    self.add_error(dec, f"@{func_id} does not take arguments.")
                else:
                    self.add_error(
                        dec, f"Unrecognized class decorator '@{func_id}(...)'."
                    )

            elif isinstance(dec, (ast.Name, ast.Attribute)):
                dec_id = dec.id if isinstance(dec, ast.Name) else dec.attr
                if dec_id == "dataclass":
                    has_dataclass = True
                    continue
                elif dec_id == "singleton_type":
                    kinds.append("singleton_type")
                    self.add_error(
                        dec,
                        '@singleton_type requires an explicit lifecycle argument: @singleton_type("system") or @singleton_type("agent_session").',
                    )
                elif dec_id in PRIMARY_KINDS:
                    kinds.append(dec_id)
                else:
                    self.add_error(dec, f"Unrecognized class decorator '@{dec_id}'.")
            else:
                self.add_error(dec, "Invalid class decorator.")

        if len(kinds) == 0:
            self.add_error(
                node,
                f"Class '{node.name}' must be decorated with exactly one ontological kind: @singleton_type, @poly_type, @data_type, or @variant.",
            )
            self.current_class_kind = None
        elif len(kinds) > 1:
            self.add_error(
                node,
                f"Class '{node.name}' has multiple ontological kinds: {kinds}. Exactly one required.",
            )
            self.current_class_kind = kinds[0]
        else:
            self.current_class_kind = kinds[0]
            self.class_kinds[node.name] = kinds[0]
            if has_dataclass and kinds[0] not in ("data_type", "variant"):
                self.add_error(
                    node,
                    f"@dataclass can only be applied to @data_type or @variant classes, not '{kinds[0]}'.",
                )

        if has_dataclass:
            if dataclass_init is None:
                dataclass_init = True
            self.class_dataclass_init[node.name] = dataclass_init
            self.class_has_init[node.name] = False

        # Check bases for obsolete classes
        for base in node.bases:
            base_id = ""
            if isinstance(base, ast.Name):
                base_id = base.id
            elif isinstance(base, ast.Attribute):
                base_id = base.attr
            if base_id in ("SystemService", "AgentSessionService"):
                self.add_error(
                    base,
                    f'Direct inheritance from \'{base_id}\' is obsolete and prohibited. Use @singleton_type("system") or @singleton_type("agent_session") instead.',
                )

        # Check docstring
        docstring = ast.get_docstring(node)
        if not docstring:
            self.add_error(
                node,
                f"Class '{node.name}' is missing a required specification docstring.",
            )
        else:
            self._validate_docstring(node, docstring, is_class=True)

        # Body statements
        for stmt in node.body:
            if (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                continue
            elif (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is Ellipsis
            ):
                continue
            elif isinstance(stmt, ast.FunctionDef):
                continue
            elif isinstance(stmt, ast.AnnAssign):
                continue
            else:
                self.add_error(
                    stmt,
                    f"Prohibited class statement '{type(stmt).__name__}' in '{node.name}'. Only properties, methods, or ellipsis allowed.",
                )

        # Visit members
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self.visit_FunctionDef(item)

        # No empty data types invariant
        if self.current_class_kind == "data_type":
            total_members = self.current_class_properties + self.current_class_methods
            has_bases = len(node.bases) > 0
            is_variant_root = any(
                isinstance(stmt, ast.ClassDef)
                and any(
                    (isinstance(d, ast.Name) and d.id == "variant")
                    for d in stmt.decorator_list
                )
                and any(
                    (isinstance(b, ast.Name) and b.id == node.name) for b in stmt.bases
                )
                for stmt in getattr(self, "_current_module_body", [])
            )
            if total_members == 0 and not has_bases and not is_variant_root:
                self.add_error(
                    node,
                    f"Data type '{node.name}' is empty. Data types participate in structural equality and must declare at least one property or base type.",
                )

        if (
            self.current_class_kind in ("data_type", "variant")
            and node.name in self.class_dataclass_init
        ):
            is_variant_root = any(
                isinstance(stmt, ast.ClassDef)
                and any(
                    (isinstance(d, ast.Name) and d.id == "variant")
                    for d in stmt.decorator_list
                )
                and any(
                    (isinstance(b, ast.Name) and b.id == node.name) for b in stmt.bases
                )
                for stmt in getattr(self, "_current_module_body", [])
            )
            if is_variant_root:
                if self.class_dataclass_init.get(node.name) is not False:
                    self.add_error(
                        node,
                        f"Base data type '{node.name}' has variants and must specify '@dataclass(frozen=True, init=False)' without an '__init__' constructor.",
                    )
                if self.class_has_init.get(node.name):
                    self.add_error(
                        node,
                        f"Base data type '{node.name}' has variants and must not declare constructor '__init__'.",
                    )
            else:
                if self.class_dataclass_init.get(
                    node.name
                ) is True and not self.class_has_init.get(node.name):
                    self.add_error(
                        node,
                        f"Data type '{node.name}' specifies 'init=True' (or default init) but does not declare constructor '__init__'. Either declare '__init__' or specify '@dataclass(frozen=True, init=False)'.",
                    )

        self.current_class = prev_class
        self.current_class_kind = prev_kind
        self.current_class_properties = prev_props
        self.current_class_methods = prev_methods

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name == "__orphan__":
            if self.current_class is not None:
                self.add_error(
                    node,
                    f"'__orphan__' must be a top-level function, not nested inside class '{self.current_class}'.",
                )
                return

            if node.decorator_list:
                self.add_error(node, "'__orphan__' must not have any decorators.")

            has_args = bool(
                node.args.args
                or getattr(node.args, "posonlyargs", None)
                or node.args.vararg
                or node.args.kwarg
                or node.args.kwonlyargs
            )
            if has_args:
                self.add_error(node, "'__orphan__' must take no arguments.")

            if node.returns is not None:
                is_none = (
                    isinstance(node.returns, ast.Constant)
                    and node.returns.value is None
                ) or (isinstance(node.returns, ast.Name) and node.returns.id == "None")
                if not is_none:
                    self.add_error(
                        node.returns, "Return type of '__orphan__' must be 'None'."
                    )

            body = node.body
            if not body:
                self.add_error(
                    node,
                    "Body of '__orphan__' cannot be empty; must contain ellipsis (...).",
                )
                return

            has_docstring = False
            doc_stmt = None
            if (
                isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                has_docstring = True
                doc_stmt = body[0]
                self._validate_docstring(
                    doc_stmt,
                    body[0].value.value,
                    is_class=False,
                    is_operation=False,
                    is_property=False,
                    is_orphan=True,
                )
            else:
                self.add_error(
                    node,
                    "'__orphan__' must have a docstring containing 'PURPOSE:' and 'FRESH_REQUIREMENTS:'.",
                )

            remaining = body[1:] if has_docstring else body
            if len(remaining) != 1:
                self.add_error(
                    node,
                    f"Body of '__orphan__' must contain only a docstring followed by an ellipsis (...). Found {len(remaining)} other statements.",
                )
            else:
                stmt = remaining[0]
                if isinstance(stmt, ast.Pass):
                    self.add_error(
                        stmt,
                        "Use of 'pass' in '__orphan__' is prohibited. Use ellipsis (...) instead.",
                    )
                elif not (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and stmt.value.value is Ellipsis
                ):
                    self.add_error(
                        stmt,
                        "Body of '__orphan__' must end with ellipsis (...). Executable statements are forbidden.",
                    )

            return

        if node.name in ("__initialize__", "_initialize_"):
            if not str(self.filename).endswith("_asm.pyi"):
                self.add_error(
                    node,
                    f"'{node.name}' is only permitted in assembly specifications (*_asm.pyi).",
                )
                return
            if self.current_class is not None:
                self.add_error(
                    node,
                    f"'{node.name}' must be a top-level function, not nested inside class '{self.current_class}'.",
                )
                return

            if node.decorator_list:
                self.add_error(node, f"'{node.name}' must not have any decorators.")

            has_args = bool(
                node.args.args
                or getattr(node.args, "posonlyargs", None)
                or node.args.vararg
                or node.args.kwarg
                or node.args.kwonlyargs
            )
            if has_args:
                self.add_error(node, f"'{node.name}' must take no arguments.")

            if node.returns is not None:
                is_none = (
                    isinstance(node.returns, ast.Constant)
                    and node.returns.value is None
                ) or (isinstance(node.returns, ast.Name) and node.returns.id == "None")
                if not is_none:
                    self.add_error(
                        node.returns, f"Return type of '{node.name}' must be 'None'."
                    )

            body = node.body
            if not body:
                self.add_error(
                    node,
                    f"Body of '{node.name}' cannot be empty; must contain ellipsis (...).",
                )
                return

            has_docstring = False
            doc_stmt = None
            if (
                isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                has_docstring = True
                doc_stmt = body[0]
                self._validate_docstring(
                    doc_stmt,
                    body[0].value.value,
                    is_class=False,
                    is_operation=False,
                    is_property=False,
                    is_orphan=False,
                    is_asm=True,
                )
            else:
                self.add_error(
                    node,
                    f"'{node.name}' must have a docstring containing 'PURPOSE:' and 'CONSTITUENTS:'.",
                )

            remaining = body[1:] if has_docstring else body
            if len(remaining) != 1:
                self.add_error(
                    node,
                    f"Body of '{node.name}' must contain only a docstring followed by an ellipsis (...). Found {len(remaining)} other statements.",
                )
            else:
                stmt = remaining[0]
                if isinstance(stmt, ast.Pass):
                    self.add_error(
                        stmt,
                        f"Use of 'pass' in '{node.name}' is prohibited. Use ellipsis (...) instead.",
                    )
                elif not (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and stmt.value.value is Ellipsis
                ):
                    self.add_error(
                        stmt,
                        f"Body of '{node.name}' must end with ellipsis (...). Executable statements are forbidden.",
                    )

            return

        if self.current_class is None:
            self.add_error(
                node,
                f"Top-level function '{node.name}' is prohibited. Only '__orphan__' and '__initialize__' are allowed at module level.",
            )
            return

        if node.name == "__init__":
            if self.current_class:
                self.class_has_init[self.current_class] = True
            if self.current_class_kind not in ("data_type", "variant"):
                self.add_error(
                    node,
                    f"Constructor '__init__' is only permitted on @data_type or @variant dataclasses, not '{self.current_class_kind}'.",
                )
            if (
                self.current_class
                and self.class_dataclass_init.get(self.current_class) is False
            ):
                self.add_error(
                    node,
                    f"Class '{self.current_class}' specifies 'init=False' and must not declare constructor '__init__'.",
                )
            if node.decorator_list:
                self.add_error(
                    node,
                    "Dataclass constructor '__init__' must not have any decorators.",
                )

            args = node.args
            if not args.args or args.args[0].arg != "self":
                self.add_error(
                    node,
                    "Constructor '__init__' must have 'self' as its first parameter.",
                )

            for arg in args.args[1:]:
                if arg.annotation is None:
                    self.add_error(
                        arg,
                        f"Parameter '{arg.arg}' in constructor '__init__' is missing a type annotation.",
                    )
                else:
                    self._check_type_annotation(arg.annotation)

            if node.returns is not None:
                is_none = (
                    isinstance(node.returns, ast.Constant)
                    and node.returns.value is None
                ) or (isinstance(node.returns, ast.Name) and node.returns.id == "None")
                if not is_none:
                    self.add_error(
                        node.returns,
                        "Return type of constructor '__init__' must be 'None'.",
                    )

            self.current_class_methods += 1

            body = node.body
            if not body:
                self.add_error(
                    node,
                    "Body of '__init__' cannot be empty; must contain ellipsis (...).",
                )
                return

            has_docstring = False
            doc_stmt = None
            if (
                isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                has_docstring = True
                doc_stmt = body[0]
                self._validate_docstring(
                    doc_stmt,
                    body[0].value.value,
                    is_class=False,
                    is_operation=False,
                    is_property=False,
                )

            remaining = body[1:] if has_docstring else body
            if len(remaining) != 1:
                self.add_error(
                    node,
                    f"Body of '__init__' must contain only an optional docstring followed by an ellipsis (...). Found {len(remaining)} other statements.",
                )
            else:
                stmt = remaining[0]
                if isinstance(stmt, ast.Pass):
                    self.add_error(
                        stmt,
                        "Use of 'pass' in '__init__' is prohibited. Use ellipsis (...) instead.",
                    )
                elif not (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and stmt.value.value is Ellipsis
                ):
                    self.add_error(
                        stmt,
                        "Body of '__init__' must end with ellipsis (...). Executable statements are forbidden.",
                    )
            return

        is_prop = False
        is_op = False
        is_override = False

        for dec in node.decorator_list:
            dec_id = ""
            if isinstance(dec, ast.Name):
                dec_id = dec.id
            elif isinstance(dec, ast.Attribute):
                dec_id = dec.attr

            if dec_id == "property":
                is_prop = True
            elif dec_id == "operation":
                is_op = True
            elif dec_id == "override":
                is_override = True
            else:
                self.add_error(
                    dec,
                    f"Unrecognized method decorator '@{dec_id}' on '{node.name}'. Allowed: @property, @operation, @override.",
                )

        if is_prop and is_op:
            self.add_error(
                node,
                f"Member '{node.name}' cannot be decorated with both @property and @operation.",
            )
        elif not is_prop and not is_op:
            self.add_error(
                node,
                f"Member '{node.name}' must be decorated with either @property or @operation.",
            )

        if is_prop:
            self.current_class_properties += 1
        else:
            self.current_class_methods += 1

        args = node.args
        if not args.args or args.args[0].arg != "self":
            self.add_error(
                node, f"Method '{node.name}' must have 'self' as its first parameter."
            )

        if is_prop:
            if len(args.args) != 1:
                self.add_error(node, f"Property '{node.name}' must take only 'self'.")
        else:
            for arg in args.args[1:]:
                if arg.annotation is None:
                    self.add_error(
                        arg,
                        f"Parameter '{arg.arg}' in method '{node.name}' is missing a type annotation.",
                    )
                else:
                    self._check_type_annotation(arg.annotation)

        if node.returns is None:
            self.add_error(
                node,
                f"Method or property '{node.name}' is missing a return type annotation.",
            )
        else:
            self._check_type_annotation(node.returns)

        body = node.body
        if not body:
            self.add_error(
                node,
                f"Body of '{node.name}' cannot be empty; must contain ellipsis (...).",
            )
            return

        has_docstring = False
        doc_stmt = None
        if (
            isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            has_docstring = True
            doc_stmt = body[0]
            self._validate_docstring(
                doc_stmt,
                body[0].value.value,
                is_class=False,
                is_operation=is_op,
                is_property=is_prop,
            )

        remaining = body[1:] if has_docstring else body
        if len(remaining) != 1:
            self.add_error(
                node,
                f"Body of '{node.name}' must contain only an optional docstring followed by an ellipsis (...). Found {len(remaining)} other statements.",
            )
        else:
            stmt = remaining[0]
            if isinstance(stmt, ast.Pass):
                self.add_error(
                    stmt,
                    f"Use of 'pass' in '{node.name}' is prohibited. Use ellipsis (...) instead.",
                )
            elif not (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is Ellipsis
            ):
                self.add_error(
                    stmt,
                    f"Body of '{node.name}' must end with ellipsis (...). Executable statements are forbidden.",
                )

    def _validate_docstring(
        self,
        node: ast.AST,
        doc: str,
        is_class: bool,
        is_operation: bool = False,
        is_property: bool = False,
        is_orphan: bool = False,
        is_asm: bool = False,
    ):
        lines = [line.strip() for line in doc.strip().splitlines()]
        if not lines or not lines[0]:
            self.add_error(node, "Docstring cannot be empty.")
            return

        upper_text = doc.upper()
        if "PURPOSE:" not in upper_text:
            self.add_error(node, "Docstring must start with 'PURPOSE:' section.")

        if is_orphan and "FRESH_REQUIREMENTS:" not in upper_text:
            self.add_error(
                node,
                "'__orphan__' docstring must contain a 'FRESH_REQUIREMENTS:' section.",
            )

        if is_asm and "CONSTITUENTS:" not in upper_text:
            self.add_error(
                node, "Assembly docstring must contain a 'CONSTITUENTS:' section."
            )

        if is_asm:
            ALLOWED_SECTIONS = {
                "PURPOSE:",
                "CONSTITUENTS:",
            }
            BULLETED_SECTIONS = {
                "CONSTITUENTS:",
            }
        else:
            ALLOWED_SECTIONS = {
                "PURPOSE:",
                "INHERITANCE:",
                "FRESH_ASSUMPTIONS:",
                "INHERITED_ASSUMPTIONS:",
                "FRESH_REQUIREMENTS:",
                "INHERITED_REQUIREMENTS:",
                "GROUNDING_ARGUMENT:",
            }
            BULLETED_SECTIONS = {
                "INHERITANCE:",
                "FRESH_ASSUMPTIONS:",
                "INHERITED_ASSUMPTIONS:",
                "FRESH_REQUIREMENTS:",
                "INHERITED_REQUIREMENTS:",
            }
        current_section = None
        for line in lines:
            if not line:
                continue
            if line in ("REQUIREMENTS:", "ASSUMPTIONS:") or line.startswith(
                "INHERITED FROM"
            ):
                self.add_error(
                    node,
                    f"Obsolete docstring section '{line}'. Use 'FRESH_REQUIREMENTS:' / 'INHERITED_REQUIREMENTS:' or 'FRESH_ASSUMPTIONS:' / 'INHERITED_ASSUMPTIONS:'.",
                )
                continue
            if line in ALLOWED_SECTIONS:
                current_section = line
                if is_orphan:
                    if line in (
                        "GROUNDING_ARGUMENT:",
                        "INHERITANCE:",
                        "INHERITED_REQUIREMENTS:",
                        "INHERITED_ASSUMPTIONS:",
                    ):
                        self.add_error(
                            node,
                            f"Docstring section '{line}' is not permitted in '__orphan__'.",
                        )
                    continue
                if line == "GROUNDING_ARGUMENT:":
                    is_impl = Path(self.filename).stem.endswith("_impl")
                    if not is_impl:
                        self.add_error(
                            node,
                            "'GROUNDING_ARGUMENT:' is only permitted in implementation components (*_impl.pyi).",
                        )
                    elif is_class:
                        if self.current_class_kind != "singleton_type":
                            self.add_error(
                                node,
                                f"'GROUNDING_ARGUMENT:' on classes is only permitted on @singleton_type, not '{self.current_class_kind}'.",
                            )
                    else:
                        if (
                            not is_operation and not is_property
                        ) or self.current_class_kind != "singleton_type":
                            self.add_error(
                                node,
                                "'GROUNDING_ARGUMENT:' on members is only permitted on operations or properties of a @singleton_type class.",
                            )
                continue
            if line.endswith(":") and line not in ALLOWED_SECTIONS:
                self.add_error(node, f"Unrecognized docstring section '{line}'.")
                continue
            if current_section in BULLETED_SECTIONS:
                if not line.startswith("- "):
                    self.add_error(
                        node,
                        f"Entries in docstring section '{current_section}' must start with '- ' (bullet point). Found: '{line}'.",
                    )

    def _check_type_annotation(self, node: ast.AST):
        if isinstance(node, ast.Name):
            self._check_type_name(node.id, node)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                mod = node.value.id
                if (
                    mod not in self.imported_modules
                    and mod not in self.imported_symbols
                ):
                    self.add_error(
                        node.value, f"Unknown module '{mod}'. (Not imported)"
                    )
        elif isinstance(node, ast.Subscript):
            self._check_type_annotation(node.value)
            if isinstance(node.slice, ast.Tuple):
                for elem in node.slice.elts:
                    self._check_type_annotation(elem)
            else:
                self._check_type_annotation(node.slice)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                ident = node.value.strip()
                if ident.isidentifier():
                    self._check_type_name(ident, node)
            elif node.value is None:
                pass
            else:
                self.add_error(
                    node, f"Invalid literal '{node.value}' in type annotation."
                )
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            self._check_type_annotation(node.left)
            self._check_type_annotation(node.right)
        elif isinstance(node, ast.Tuple):
            for elem in node.elts:
                self._check_type_annotation(elem)

    def _check_type_name(self, name: str, node: ast.AST):
        if (
            name in BUILTIN_TYPES
            or name in self.declared_symbols
            or name in self.imported_symbols
        ):
            return
        known = list(BUILTIN_TYPES | self.declared_symbols | self.imported_symbols)
        matches = difflib.get_close_matches(name, known, n=1, cutoff=0.7)
        if matches:
            self.add_error(
                node,
                f"Unknown type '{name}'. Did you mean '{matches[0]}'? (Not declared or imported)",
            )
        else:
            self.add_error(node, f"Unknown type '{name}'. (Not declared or imported)")


def lint_file(filepath: str) -> List[Diagnostic]:
    """Lints a single specification file via AST."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        return [Diagnostic(filepath, 1, 0, f"Failed to read file: {e}")]

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return [
            Diagnostic(filepath, e.lineno or 1, e.offset or 0, f"SyntaxError: {e.msg}")
        ]

    visitor = SpecLintVisitor(filepath)
    visitor.visit(tree)
    return visitor.diagnostics


class SpecRegistry:
    """Shared semantic registry for modules, classes, and inheritance."""

    def __init__(self):
        self.modules: Dict[str, ast.Module] = {}
        self.module_paths: Dict[str, Path] = {}
        self.module_classes: Dict[Tuple[str, str], ast.ClassDef] = {}
        self.class_to_modules: Dict[str, Set[str]] = {}
        self.imports: Dict[str, Dict[str, str]] = {}
        self.module_exports: Dict[str, Set[str]] = {}
        self.class_tiers: Dict[str, str] = {}
        self.class_bases: Dict[str, List[str]] = {}
        self.class_dataclass_init: Dict[str, Optional[bool]] = {}
        self.class_has_init: Dict[str, bool] = {}
        self.class_variants: Dict[str, Set[str]] = {}
        self.module_sources: Dict[str, str] = {}
        self.assembly_constituents: Dict[str, List[str]] = {}

    def load_file(self, filepath: Path) -> Optional[Diagnostic]:
        mod_name = filepath.stem
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(filepath))
        except Exception as e:
            return Diagnostic(str(filepath), 1, 0, f"Failed to parse: {e}")

        self.modules[mod_name] = tree
        self.module_sources[mod_name] = content
        self.module_paths[mod_name] = filepath
        self.imports[mod_name] = {}
        self.module_exports[mod_name] = set()

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self.module_classes[(mod_name, node.name)] = node
                self.class_to_modules.setdefault(node.name, set()).add(mod_name)
                self.module_exports[mod_name].add(node.name)

                bases = []
                for base in node.bases:
                    b_id = (
                        base.id
                        if isinstance(base, ast.Name)
                        else (base.attr if isinstance(base, ast.Attribute) else "")
                    )
                    if b_id:
                        bases.append(b_id)
                self.class_bases[node.name] = bases

                tier = "unknown"
                dataclass_init: Optional[bool] = None
                has_dataclass = False
                is_variant = False
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call):
                        func_id = (
                            dec.func.id
                            if isinstance(dec.func, ast.Name)
                            else (
                                dec.func.attr
                                if isinstance(dec.func, ast.Attribute)
                                else ""
                            )
                        )
                        if (
                            func_id == "singleton_type"
                            and dec.args
                            and isinstance(dec.args[0], ast.Constant)
                        ):
                            if dec.args[0].value == "system":
                                tier = "system"
                            elif dec.args[0].value == "agent_session":
                                tier = "session"
                        elif func_id == "dataclass":
                            has_dataclass = True
                            for kw in dec.keywords:
                                if kw.arg == "init" and isinstance(
                                    kw.value, ast.Constant
                                ):
                                    dataclass_init = bool(kw.value.value)
                    elif isinstance(dec, (ast.Name, ast.Attribute)):
                        dec_name = dec.id if isinstance(dec, ast.Name) else dec.attr
                        if dec_name in ("data_type", "variant"):
                            tier = "data"
                            if dec_name == "variant":
                                is_variant = True
                        elif dec_name == "poly_type":
                            tier = "poly"
                        elif dec_name == "dataclass":
                            has_dataclass = True
                self.class_tiers[node.name] = tier

                if has_dataclass:
                    if dataclass_init is None:
                        dataclass_init = True
                    self.class_dataclass_init[node.name] = dataclass_init
                    self.class_has_init[node.name] = any(
                        isinstance(item, ast.FunctionDef) and item.name == "__init__"
                        for item in node.body
                    )

                if is_variant:
                    for b in bases:
                        self.class_variants.setdefault(b, set()).add(node.name)

            elif isinstance(node, ast.ImportFrom):
                origin = node.module or ""
                for alias in node.names:
                    sym = alias.asname or alias.name
                    self.imports[mod_name][sym] = origin
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    sym = alias.asname or alias.name
                    self.imports[mod_name][sym] = alias.name
            elif isinstance(node, ast.FunctionDef) and node.name in (
                "__initialize__",
                "_initialize_",
            ):
                self.module_exports[mod_name].add(node.name)
                if mod_name.endswith("_asm"):
                    doc = ast.get_docstring(node) or ""
                    constituents = []
                    in_constituents = False
                    for line in doc.splitlines():
                        stripped = line.strip()
                        if stripped == "CONSTITUENTS:":
                            in_constituents = True
                            continue
                        elif stripped.endswith(":") and in_constituents:
                            break
                        elif in_constituents and stripped.startswith("- "):
                            constituents.append(stripped[2:].strip())
                    self.assembly_constituents[mod_name] = constituents

        return None

    def resolve_base_class(
        self, current_module: str, base_expr: ast.AST
    ) -> Optional[Tuple[str, ast.ClassDef, str]]:
        if isinstance(base_expr, ast.Attribute):
            mod_id = base_expr.value.id if isinstance(base_expr.value, ast.Name) else ""
            cls_name = base_expr.attr
            if (mod_id, cls_name) in self.module_classes:
                return cls_name, self.module_classes[(mod_id, cls_name)], mod_id
        elif isinstance(base_expr, ast.Name):
            base_name = base_expr.id
            if (current_module, base_name) in self.module_classes:
                return (
                    base_name,
                    self.module_classes[(current_module, base_name)],
                    current_module,
                )
            if base_name in self.imports.get(current_module, {}):
                orig_mod = self.imports[current_module][base_name]
                if (orig_mod, base_name) in self.module_classes:
                    return (
                        base_name,
                        self.module_classes[(orig_mod, base_name)],
                        orig_mod,
                    )
            mods = self.class_to_modules.get(base_name, set())
            non_impl = [m for m in mods if not m.endswith("_impl")]
            if non_impl:
                target_mod = non_impl[0]
                return (
                    base_name,
                    self.module_classes[(target_mod, base_name)],
                    target_mod,
                )
            elif mods:
                target_mod = next(iter(mods))
                return (
                    base_name,
                    self.module_classes[(target_mod, base_name)],
                    target_mod,
                )
        return None

    def get_ancestors_mro(
        self, mod_name: str, class_name: str
    ) -> List[Tuple[str, ast.ClassDef, str]]:
        if (mod_name, class_name) not in self.module_classes:
            return []
        cls_node = self.module_classes[(mod_name, class_name)]
        ancestors = []
        visited = set()

        queue = [(mod_name, base) for base in cls_node.bases]
        while queue:
            curr_mod, base_expr = queue.pop(0)
            res = self.resolve_base_class(curr_mod, base_expr)
            if res:
                b_name, b_node, b_mod = res
                key = (b_mod, b_name)
                if key not in visited:
                    visited.add(key)
                    ancestors.append((b_name, b_node, b_mod))
                    for next_base in b_node.bases:
                        queue.append((b_mod, next_base))
        return ancestors


def is_override_member(func: ast.FunctionDef) -> bool:
    for d in func.decorator_list:
        if isinstance(d, ast.Name) and d.id in ("override", "inherited"):
            return True
        elif isinstance(d, ast.Attribute) and d.attr in ("override", "inherited"):
            return True
    return False


def adjust_override_decorators(stub: ast.FunctionDef) -> list[ast.expr]:
    is_prop = False
    for d in stub.decorator_list:
        dec_id = ""
        if isinstance(d, ast.Name):
            dec_id = d.id
        elif isinstance(d, ast.Attribute):
            dec_id = d.attr
        elif isinstance(d, ast.Call):
            if isinstance(d.func, ast.Name):
                dec_id = d.func.id
            elif isinstance(d.func, ast.Attribute):
                dec_id = d.func.attr

        if dec_id == "property":
            is_prop = True

    new_decorators: list[ast.expr] = []
    if is_prop:
        new_decorators.append(ast.Name(id="property", ctx=ast.Load()))
    else:
        new_decorators.append(ast.Name(id="operation", ctx=ast.Load()))

    new_decorators.append(ast.Name(id="override", ctx=ast.Load()))
    return new_decorators


class ClosedWorldLinker:
    """Pass 2: Validates closed-world imports, symbol visibility, and tier isolation."""

    def __init__(self, registry: Optional[SpecRegistry] = None):
        self.registry = registry or SpecRegistry()
        self.diagnostics: List[Diagnostic] = []

    @property
    def modules(self) -> Dict[str, ast.Module]:
        return self.registry.modules

    @property
    def module_paths(self) -> Dict[str, Path]:
        return self.registry.module_paths

    @property
    def module_exports(self) -> Dict[str, Set[str]]:
        return self.registry.module_exports

    @property
    def class_tiers(self) -> Dict[str, str]:
        return self.registry.class_tiers

    @property
    def class_bases(self) -> Dict[str, List[str]]:
        return self.registry.class_bases

    def load_module(self, filepath: Path):
        diag = self.registry.load_file(filepath)
        if diag:
            self.diagnostics.append(diag)

    def _resolve_tiers(self):
        changed = True
        while changed:
            changed = False
            for cls_name, bases in self.registry.class_bases.items():
                if self.registry.class_tiers.get(cls_name) == "unknown":
                    for b in bases:
                        if self.registry.class_tiers.get(b) in ("system", "session"):
                            self.registry.class_tiers[cls_name] = (
                                self.registry.class_tiers[b]
                            )
                            changed = True
                            break
        for cls_name in self.registry.class_tiers:
            if self.registry.class_tiers[cls_name] == "unknown":
                self.registry.class_tiers[cls_name] = "session"

    def check_all(self) -> List[Diagnostic]:
        self._resolve_tiers()
        for mod_name, tree in self.registry.modules.items():
            path_str = str(self.registry.module_paths[mod_name])
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    origin = node.module or ""
                    if origin in ("framework", "typing", "dataclasses"):
                        continue
                    if origin not in self.registry.module_exports:
                        self.diagnostics.append(
                            Diagnostic(
                                path_str,
                                node.lineno,
                                node.col_offset,
                                f"Imported module '{origin}' does not exist in grounding specifications.",
                            )
                        )
                        continue
                    for alias in node.names:
                        sym = alias.name
                        if sym not in self.registry.module_exports[origin]:
                            self.diagnostics.append(
                                Diagnostic(
                                    path_str,
                                    node.lineno,
                                    node.col_offset,
                                    f"Symbol '{sym}' is not exported by specification '{origin}'.",
                                )
                            )

                elif isinstance(node, ast.ClassDef):
                    cls_tier = self.registry.class_tiers.get(node.name, "unknown")
                    if cls_tier == "system":
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                self._check_tier_isolation(path_str, item, node.name)

                    ancestors = self.registry.get_ancestors_mro(mod_name, node.name)
                    ancestor_member_names = set()
                    for _, anc_node, _ in ancestors:
                        for anc_item in anc_node.body:
                            if isinstance(anc_item, ast.FunctionDef):
                                ancestor_member_names.add(anc_item.name)

                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            if (
                                is_override_member(item)
                                and item.name not in ancestor_member_names
                            ):
                                m_doc = ast.get_docstring(item) or ""
                                m_contract = DocstringContract(m_doc)
                                if (
                                    m_contract.fresh_assumptions
                                    or m_contract.fresh_requirements
                                    or m_contract.grounding_argument
                                ):
                                    self.diagnostics.append(
                                        Diagnostic(
                                            path_str,
                                            item.lineno,
                                            item.col_offset,
                                            f"Overriding member '{item.name}' in class '{node.name}' has fresh contracts but does not match any member in supertypes.",
                                        )
                                    )

                    if node.name in self.registry.class_dataclass_init:
                        d_init = self.registry.class_dataclass_init[node.name]
                        has_init = self.registry.class_has_init.get(node.name, False)
                        has_variants = bool(self.registry.class_variants.get(node.name))

                        if has_variants:
                            if d_init is not False:
                                self.diagnostics.append(
                                    Diagnostic(
                                        path_str,
                                        node.lineno,
                                        node.col_offset,
                                        f"Base data type '{node.name}' has variants and must specify '@dataclass(frozen=True, init=False)' without an '__init__' constructor.",
                                    )
                                )
                            if has_init:
                                self.diagnostics.append(
                                    Diagnostic(
                                        path_str,
                                        node.lineno,
                                        node.col_offset,
                                        f"Base data type '{node.name}' has variants and must not declare constructor '__init__'.",
                                    )
                                )
                        else:
                            if d_init is True and not has_init:
                                self.diagnostics.append(
                                    Diagnostic(
                                        path_str,
                                        node.lineno,
                                        node.col_offset,
                                        f"Data type '{node.name}' specifies 'init=True' (or default init) but does not declare constructor '__init__'. Either declare '__init__' or specify '@dataclass(frozen=True, init=False)'.",
                                    )
                                )
                            elif d_init is False and has_init:
                                self.diagnostics.append(
                                    Diagnostic(
                                        path_str,
                                        node.lineno,
                                        node.col_offset,
                                        f"Data type '{node.name}' specifies 'init=False' and must not declare constructor '__init__'.",
                                    )
                                )

        for asm_name, constituents in self.registry.assembly_constituents.items():
            asm_path = str(self.registry.module_paths.get(asm_name, asm_name))
            if not constituents:
                self.diagnostics.append(
                    Diagnostic(
                        asm_path,
                        1,
                        0,
                        f"Assembly '{asm_name}' has an empty 'CONSTITUENTS:' list.",
                    )
                )
            for c in constituents:
                if c not in self.registry.modules:
                    self.diagnostics.append(
                        Diagnostic(
                            asm_path,
                            1,
                            0,
                            f"Constituent '{c}' of assembly '{asm_name}' does not exist in grounding specifications.",
                        )
                    )
                elif not (c.endswith("_impl") or c.endswith("_asm")):
                    self.diagnostics.append(
                        Diagnostic(
                            asm_path,
                            1,
                            0,
                            f"Constituent '{c}' of assembly '{asm_name}' must be an implementation (*_impl) or assembly (*_asm) component.",
                        )
                    )

        return self.diagnostics

    def _check_tier_isolation(self, path: str, func: ast.FunctionDef, cls_name: str):
        if func.returns:
            self._verify_not_session_service(path, func.returns, cls_name, func.name)
        for arg in func.args.args[1:]:
            if arg.annotation:
                self._verify_not_session_service(
                    path, arg.annotation, cls_name, func.name
                )

    def _verify_not_session_service(
        self, path: str, type_node: ast.AST, cls_name: str, member_name: str
    ):
        names = []
        if isinstance(type_node, ast.Name):
            names.append((type_node.id, type_node.lineno, type_node.col_offset))
        elif isinstance(type_node, ast.Attribute):
            names.append((type_node.attr, type_node.lineno, type_node.col_offset))
        elif isinstance(type_node, ast.Subscript):
            if isinstance(type_node.slice, ast.Tuple):
                for el in type_node.slice.elts:
                    self._verify_not_session_service(path, el, cls_name, member_name)
            else:
                self._verify_not_session_service(
                    path, type_node.slice, cls_name, member_name
                )

        for name, line, col in names:
            if self.registry.class_tiers.get(name) == "session":
                self.diagnostics.append(
                    Diagnostic(
                        path,
                        line,
                        col,
                        f"Lifecycle tier violation: System service '{cls_name}.{member_name}' references short-lived session service '{name}'.",
                    )
                )


def set_class_docstring(node: ast.ClassDef, doc: str):
    if not doc:
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body.pop(0)
        return
    doc_node = ast.Expr(value=ast.Constant(value=doc))
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        node.body[0] = doc_node
    else:
        node.body.insert(0, doc_node)


def set_function_docstring(node: ast.FunctionDef, doc: str):
    body_without_doc: list[ast.stmt] = []
    for stmt in node.body:
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue
        body_without_doc.append(stmt)

    if not body_without_doc:
        body_without_doc = [ast.Expr(value=ast.Constant(value=Ellipsis))]
    elif not any(
        isinstance(s, ast.Expr)
        and isinstance(s.value, ast.Constant)
        and s.value.value is Ellipsis
        for s in body_without_doc
    ):
        body_without_doc.append(ast.Expr(value=ast.Constant(value=Ellipsis)))

    if doc:
        node.body = [
            cast(ast.stmt, ast.Expr(value=ast.Constant(value=doc)))
        ] + body_without_doc
    else:
        node.body = body_without_doc


class TypeQualifier(ast.NodeTransformer):
    """Ensures types referenced in synthesized stubs from other modules are qualified."""

    def __init__(self, registry: SpecRegistry, current_mod: str, anc_mod: str):
        self.registry = registry
        self.current_mod = current_mod
        self.anc_mod = anc_mod
        self.local_symbols = set()
        for m, cls_name in registry.module_classes.keys():
            if m == current_mod:
                self.local_symbols.add(cls_name)
        for sym in registry.imports.get(current_mod, {}).keys():
            self.local_symbols.add(sym)

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        sym = node.id
        if (
            sym in COMMON_TYPING_SYMBOLS
            or sym in COMMON_BUILTINS
            or sym in FRAMEWORK_SYMBOLS
            or sym == "property"
        ):
            return node
        if sym in self.local_symbols:
            return node

        if (self.anc_mod, sym) in self.registry.module_classes:
            return ast.copy_location(
                ast.Attribute(
                    value=ast.Name(id=self.anc_mod, ctx=ast.Load()),
                    attr=sym,
                    ctx=node.ctx,
                ),
                node,
            )

        if sym in self.registry.imports.get(self.anc_mod, {}):
            orig_mod = self.registry.imports[self.anc_mod][sym]
            if (
                orig_mod
                and orig_mod not in ("typing", "builtins")
                and orig_mod != self.current_mod
            ):
                return ast.copy_location(
                    ast.Attribute(
                        value=ast.Name(id=orig_mod, ctx=ast.Load()),
                        attr=sym,
                        ctx=node.ctx,
                    ),
                    node,
                )

        if sym in self.registry.class_to_modules:
            mods = self.registry.class_to_modules[sym]
            non_impl = [m for m in mods if not m.endswith("_impl")]
            orig_mod = non_impl[0] if non_impl else next(iter(mods))
            if (
                orig_mod
                and orig_mod not in ("typing", "builtins")
                and orig_mod != self.current_mod
            ):
                return ast.copy_location(
                    ast.Attribute(
                        value=ast.Name(id=orig_mod, ctx=ast.Load()),
                        attr=sym,
                        ctx=node.ctx,
                    ),
                    node,
                )

        return node


def process_class_inheritance(
    registry: SpecRegistry, cls_node: ast.ClassDef, mod_name: str
) -> Tuple[ast.ClassDef, List[Diagnostic]]:
    new_cls = copy.deepcopy(cls_node)
    ancestors = registry.get_ancestors_mro(mod_name, cls_node.name)
    diagnostics: List[Diagnostic] = []

    cls_doc = ast.get_docstring(new_cls) or ""
    cls_contract = DocstringContract(cls_doc)
    cls_contract.wipe_inherited()

    for anc_name, anc_node, anc_mod in ancestors:
        anc_doc = ast.get_docstring(anc_node) or ""
        anc_contract = DocstringContract(anc_doc)

        for a in anc_contract.fresh_assumptions:
            if a not in cls_contract.inherited_assumptions.setdefault(anc_name, []):
                cls_contract.inherited_assumptions[anc_name].append(a)

        for r in anc_contract.fresh_requirements:
            if r not in cls_contract.inherited_requirements.setdefault(anc_name, []):
                cls_contract.inherited_requirements[anc_name].append(r)

    ancestor_members: Dict[str, Tuple[ast.FunctionDef, str]] = {}
    ancestor_fresh_assumptions: Dict[str, Dict[str, List[str]]] = {}
    ancestor_fresh_requirements: Dict[str, Dict[str, List[str]]] = {}

    for anc_name, anc_node, anc_mod in ancestors:
        for item in anc_node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name == "__init__":
                    continue
                m_name = item.name
                if m_name not in ancestor_members:
                    ancestor_members[m_name] = (item, anc_mod)
                m_doc = ast.get_docstring(item) or ""
                m_contract = DocstringContract(m_doc)
                for a in m_contract.fresh_assumptions:
                    if a not in ancestor_fresh_assumptions.setdefault(
                        m_name, {}
                    ).setdefault(anc_name, []):
                        ancestor_fresh_assumptions[m_name][anc_name].append(a)
                for r in m_contract.fresh_requirements:
                    if r not in ancestor_fresh_requirements.setdefault(
                        m_name, {}
                    ).setdefault(anc_name, []):
                        ancestor_fresh_requirements[m_name][anc_name].append(r)

    new_body: list[ast.stmt] = []
    seen_members: Set[str] = set()

    for item in new_cls.body:
        if not isinstance(item, ast.FunctionDef):
            if (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and isinstance(item.value.value, str)
            ):
                continue
            if (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and item.value.value is Ellipsis
            ):
                continue
            new_body.append(item)
            continue

        if item.name == "__init__":
            new_body.append(item)
            continue

        m_name = item.name
        seen_members.add(m_name)
        m_doc = ast.get_docstring(item) or ""
        m_contract = DocstringContract(m_doc)
        has_fresh = bool(
            m_contract.fresh_assumptions
            or m_contract.fresh_requirements
            or m_contract.grounding_argument
        )
        is_override = is_override_member(item)

        if m_name in ancestor_members:
            item.decorator_list = adjust_override_decorators(item)
            m_contract.wipe_inherited()
            for anc_name, ass_list in ancestor_fresh_assumptions.get(
                m_name, {}
            ).items():
                m_contract.inherited_assumptions[anc_name] = list(ass_list)
            for anc_name, req_list in ancestor_fresh_requirements.get(
                m_name, {}
            ).items():
                m_contract.inherited_requirements[anc_name] = list(req_list)
            set_function_docstring(item, m_contract.to_docstring())
            new_body.append(item)
        else:
            if is_override:
                if has_fresh:
                    diag_path = str(registry.module_paths.get(mod_name, mod_name))
                    diagnostics.append(
                        Diagnostic(
                            diag_path,
                            item.lineno,
                            item.col_offset,
                            f"Overriding member '{m_name}' in class '{cls_node.name}' has fresh contracts but does not match any member in supertypes.",
                        )
                    )
                    new_body.append(item)
                else:
                    # Stale override stub: remove it from body
                    pass
            else:
                m_contract.wipe_inherited()
                set_function_docstring(item, m_contract.to_docstring())
                new_body.append(item)

    # Synthesize missing members from ancestors
    for m_name, (anc_m, anc_mod) in ancestor_members.items():
        if m_name not in seen_members:
            stub = copy.deepcopy(anc_m)
            stub_doc = ast.get_docstring(anc_m) or ""
            stub_contract = DocstringContract(stub_doc)
            stub_contract.fresh_assumptions = []
            stub_contract.fresh_requirements = []
            stub_contract.grounding_argument = ""
            stub_contract.wipe_inherited()
            for anc_name, ass_list in ancestor_fresh_assumptions.get(
                m_name, {}
            ).items():
                stub_contract.inherited_assumptions[anc_name] = list(ass_list)
            for anc_name, req_list in ancestor_fresh_requirements.get(
                m_name, {}
            ).items():
                stub_contract.inherited_requirements[anc_name] = list(req_list)
            set_function_docstring(stub, stub_contract.to_docstring())
            stub.decorator_list = adjust_override_decorators(stub)
            if anc_mod != mod_name:
                qualifier = TypeQualifier(registry, mod_name, anc_mod)
                visited_stub = qualifier.visit(stub)
                if isinstance(visited_stub, ast.FunctionDef):
                    stub = visited_stub
            new_body.append(stub)

    new_cls.body = new_body
    set_class_docstring(new_cls, cls_contract.to_docstring())

    has_methods = any(isinstance(item, ast.FunctionDef) for item in new_cls.body)
    if not has_methods:
        has_ellipsis = any(
            isinstance(item, ast.Expr)
            and isinstance(item.value, ast.Constant)
            and item.value.value is Ellipsis
            for item in new_cls.body
        )
        if not has_ellipsis:
            new_cls.body.append(ast.Expr(value=ast.Constant(value=Ellipsis)))
    else:
        new_cls.body = [
            item
            for item in new_cls.body
            if not (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and item.value.value is Ellipsis
            )
        ]

    return new_cls, diagnostics


def compile_module_inheritance(
    registry: SpecRegistry, mod_name: str
) -> Tuple[str, List[Diagnostic]]:
    orig_tree = registry.modules[mod_name]
    if mod_name.endswith(("_ext", "_asm")):
        return registry.module_sources.get(mod_name, ast.unparse(orig_tree) + "\n"), []

    new_tree = copy.deepcopy(orig_tree)
    diagnostics: List[Diagnostic] = []

    new_body = []
    for item in new_tree.body:
        if isinstance(item, ast.ClassDef):
            expanded_cls, cls_diags = process_class_inheritance(
                registry, item, mod_name
            )
            diagnostics.extend(cls_diags)
            new_body.append(expanded_cls)
        else:
            new_body.append(item)

    new_tree.body = new_body

    used_framework = set()
    for node in ast.walk(new_tree):
        if isinstance(node, ast.Name) and node.id in FRAMEWORK_SYMBOLS:
            used_framework.add(node.id)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FRAMEWORK_SYMBOLS
        ):
            used_framework.add(node.func.id)

    found_framework_import = False
    for stmt in new_tree.body:
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "framework":
            stmt.names = [ast.alias(name=s) for s in sorted(used_framework)]
            found_framework_import = True
            break
    if not found_framework_import and used_framework:
        new_tree.body.insert(
            0,
            ast.ImportFrom(
                module="framework",
                names=[ast.alias(name=s) for s in sorted(used_framework)],
                level=0,
            ),
        )

    used_typing = set()
    for node in ast.walk(new_tree):
        if isinstance(node, ast.Name) and node.id in COMMON_TYPING_SYMBOLS:
            used_typing.add(node.id)

    found_typing = False
    for stmt in new_tree.body:
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "typing":
            existing = {a.name for a in stmt.names}
            all_typing = existing | used_typing
            stmt.names = [ast.alias(name=t) for t in sorted(all_typing)]
            found_typing = True
            break
    if not found_typing and used_typing:
        new_tree.body.insert(
            0,
            ast.ImportFrom(
                module="typing",
                names=[ast.alias(name=t) for t in sorted(used_typing)],
                level=0,
            ),
        )

    used_dataclasses = set()
    for node in ast.walk(new_tree):
        if isinstance(node, ast.Name) and node.id in DATACLASS_SYMBOLS:
            used_dataclasses.add(node.id)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in DATACLASS_SYMBOLS
        ):
            used_dataclasses.add(node.func.id)

    found_dataclasses = False
    for stmt in new_tree.body:
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "dataclasses":
            existing = {a.name for a in stmt.names}
            all_dc = existing | used_dataclasses
            stmt.names = [ast.alias(name=t) for t in sorted(all_dc)]
            found_dataclasses = True
            break
    if not found_dataclasses and used_dataclasses:
        insert_idx = 0
        for i, stmt in enumerate(new_tree.body):
            if isinstance(stmt, ast.ImportFrom) and stmt.module in (
                "framework",
                "typing",
            ):
                insert_idx = i + 1
        new_tree.body.insert(
            insert_idx,
            ast.ImportFrom(
                module="dataclasses",
                names=[ast.alias(name=t) for t in sorted(used_dataclasses)],
                level=0,
            ),
        )

    used_modules = set()
    for node in ast.walk(new_tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if any(m == node.value.id for (m, _) in registry.module_classes.keys()):
                used_modules.add(node.value.id)

    existing_module_imports = set()
    for stmt in new_tree.body:
        if isinstance(stmt, ast.Import):
            for a in stmt.names:
                existing_module_imports.add(a.name)

    needed_modules = sorted(used_modules - existing_module_imports)
    for mod in needed_modules:
        if mod != mod_name:
            insert_idx = 0
            for i, stmt in enumerate(new_tree.body):
                if isinstance(stmt, ast.ImportFrom) and stmt.module in (
                    "typing",
                    "framework",
                    "dataclasses",
                ):
                    insert_idx = i + 1
                elif isinstance(stmt, ast.Import):
                    insert_idx = i + 1
            new_tree.body.insert(insert_idx, ast.Import(names=[ast.alias(name=mod)]))

    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree) + "\n", diagnostics


def find_repo_root() -> Path:
    """Find the root workspace directory containing update_with_ai."""
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        p = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
        if (p / "update_with_ai" / "specs" / "grounding").is_dir():
            return p
    current = Path(__file__).resolve().parent
    for p in [
        current,
        current.parent,
        current.parent.parent,
        current.parent.parent.parent,
    ]:
        if (p / "update_with_ai" / "specs" / "grounding").is_dir():
            return p
    cwd = Path.cwd()
    if (cwd / "update_with_ai" / "specs" / "grounding").is_dir():
        return cwd
    return cwd


def collect_paths(file_args: List[str]) -> List[Path]:
    root = find_repo_root()
    if not file_args:
        spec_dir = root / "update_with_ai" / "specs" / "grounding"
        if spec_dir.is_dir():
            return sorted(spec_dir.glob("*.pyi"))
        parts_dir = root / "update_with_ai" / "parts"
        if parts_dir.is_dir():
            return sorted(parts_dir.glob("*/grounding/*.pyi"))
        return []

    paths = []
    for f in file_args:
        p = Path(f)
        if not p.is_absolute() and not p.exists() and (root / f).exists():
            p = root / f
        if p.is_file() and p.suffix == ".pyi":
            paths.append(p)
        elif p.is_dir():
            paths.extend(sorted(p.glob("**/*.pyi")))
    return sorted(set(paths))


def run_pipeline(
    paths: List[Path],
    mode: str = "check",
    out_dir: Optional[str] = None,
) -> int:
    """Runs the unified specification pipeline."""
    if not paths:
        print("No .pyi specification files found.", file=sys.stderr)
        return 0

    total_errors = 0

    # 1. Lint Pass
    if mode in ("check", "sync", "lint-only"):
        for path in paths:
            diags = lint_file(str(path))
            for d in diags:
                print(d, file=sys.stderr)
                total_errors += 1

        if mode == "lint-only":
            return 1 if total_errors > 0 else 0

    # If lint errors occurred, do not attempt link or inheritance
    if total_errors > 0 and mode != "sync":
        print(f"\n{total_errors} specification lint error(s) found.", file=sys.stderr)
        return 1

    # 2. Link Pass
    registry = SpecRegistry()
    for path in paths:
        diag = registry.load_file(path)
        if diag:
            print(diag, file=sys.stderr)
            total_errors += 1

    linker = ClosedWorldLinker(registry)
    link_diags = linker.check_all()
    for d in link_diags:
        print(d, file=sys.stderr)
        total_errors += 1

    if mode == "link-only":
        return 1 if total_errors > 0 else 0

    if total_errors > 0 and mode != "sync":
        print(
            f"\n{total_errors} error(s) found during specification linking.",
            file=sys.stderr,
        )
        return 1

    # 3. Inheritance & Drift Pass
    out_path = Path(out_dir) if out_dir else None
    if out_path:
        out_path.mkdir(parents=True, exist_ok=True)

    drift_count = 0
    inh_errors = 0
    for mod_name, orig_path in registry.module_paths.items():
        compiled_code, diags = compile_module_inheritance(registry, mod_name)
        for d in diags:
            print(d, file=sys.stderr)
            inh_errors += 1
            total_errors += 1

        if inh_errors > 0:
            continue

        if mode == "check":
            try:
                with open(orig_path, "r", encoding="utf-8") as f:
                    orig_code = f.read()
            except Exception as e:
                print(f"Failed to read {orig_path}: {e}", file=sys.stderr)
                drift_count += 1
                continue

            if orig_code != compiled_code:
                print(f"Drift detected in {orig_path}:", file=sys.stderr)
                diff = difflib.unified_diff(
                    orig_code.splitlines(),
                    compiled_code.splitlines(),
                    fromfile=str(orig_path),
                    tofile=f"{orig_path} (inherited)",
                )
                print("\n".join(diff), file=sys.stderr)
                drift_count += 1

        elif mode == "sync":
            with open(orig_path, "w", encoding="utf-8") as f:
                f.write(compiled_code)

        elif out_path:
            dest = out_path / f"{mod_name}.pyi"
            with open(dest, "w", encoding="utf-8") as f:
                f.write(compiled_code)

    if (mode == "check" and (total_errors > 0 or drift_count > 0)) or inh_errors > 0:
        print(
            f"\nFailed: {total_errors} diagnostic error(s), {drift_count} file(s) out of sync.",
            file=sys.stderr,
        )
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Cleanroom Grounding Specification Unified Tool (Lint, Link, Inherit)",
    )
    parser.add_argument(
        "files",
        nargs="*",
        default=[],
        help=".pyi specification files or directories to process (defaults to update_with_ai/specs/grounding/*.pyi)",
    )

    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--check",
        action="store_true",
        help="Validate lint, links, and verify zero inheritance drift (default)",
    )
    action_group.add_argument(
        "--sync",
        "--in-place",
        dest="sync",
        action="store_true",
        help="Lint, link, and synchronize inherited requirements/stubs directly in-place",
    )
    action_group.add_argument(
        "--lint-only",
        action="store_true",
        help="Run only AST static linting",
    )
    action_group.add_argument(
        "--link-only",
        action="store_true",
        help="Run only cross-module linking",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        help="Directory to emit fully resolved .pyi specifications",
    )

    args = parser.parse_args()

    paths = collect_paths(args.files)

    if args.sync:
        mode = "sync"
    elif args.lint_only:
        mode = "lint-only"
    elif args.link_only:
        mode = "link-only"
    elif args.out_dir:
        mode = "out-dir"
    else:
        mode = "check"

    exit_code = run_pipeline(
        paths,
        mode=mode,
        out_dir=args.out_dir,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
