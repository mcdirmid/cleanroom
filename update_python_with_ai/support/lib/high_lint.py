#!/usr/bin/env python3
"""
high_lint.py — lightweight structural and boundary linter for High-Level Specifications.

Usage:
    python3 update_python_with_ai/support/lib/high_lint.py [files...]
    python3 update_python_with_ai/support/lib/high_lint.py [--deps dep1 dep2 ...] -- [target files...]

Checks:
  1. Header matches filename (# <name>).
  2. Front-matter ordering: `imports:` comes first (if any), followed by `types from <dep>:`, followed by `implements:` (if implementation/assembly).
  3. No `imports:` of `*_impl` or `*_asm` components in non-`*_asm` components.
  4. Every `types from <dep>:` corresponds to an imported module in `imports:`.
  5. Implementation specs (`*_impl.md`) must declare `implements: <type>` in front-matter.
  6. Closed section inventory: `## Purpose`, `## Types`, `## Behavior`.
"""

from __future__ import annotations

import ast
import os
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
MY_METHODOLOGY = f"//{Path(__file__).resolve().parent.parent.parent.name}"


def find_all_parts_dirs() -> list[Path]:
    dirs: list[Path] = []
    if not ROOT.exists():
        return dirs
    for entry in sorted(ROOT.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            p = entry / "parts"
            if p.is_dir():
                cfg = p / "cleanroom.toml"
                if cfg.is_file():
                    try:
                        with open(cfg, "rb") as f:
                            data = tomllib.load(f)
                        if data.get("methodology") == MY_METHODOLOGY:
                            dirs.append(p)
                    except Exception:
                        pass
    return dirs


def lint_high_file(file_path: Path) -> list[str]:
    errors: list[str] = []
    fname = file_path.name
    stem = file_path.stem
    is_impl = stem.endswith("_impl")
    is_asm = stem.endswith("_asm")
    is_ext = stem.endswith("_ext")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        return [f"{fname}:1: error: cannot read file: {e}"]

    if not lines:
        return [f"{fname}:1: error: empty specification file"]

    # 1. Header Check
    start_idx = 0
    while start_idx < len(lines) and not lines[start_idx].strip():
        start_idx += 1
    if start_idx < len(lines) and lines[start_idx].strip() == "<!-- CLEANROOM METADATA":
        while start_idx < len(lines) and lines[start_idx].strip() != "-->":
            start_idx += 1
        if start_idx < len(lines) and lines[start_idx].strip() == "-->":
            start_idx += 1

    first_non_empty = start_idx
    while first_non_empty < len(lines) and not lines[first_non_empty].strip():
        first_non_empty += 1

    if first_non_empty >= len(lines) or not lines[first_non_empty].startswith(
        f"# {stem}"
    ):
        actual = (
            lines[first_non_empty].strip() if first_non_empty < len(lines) else "EOF"
        )
        errors.append(
            f"{fname}:{first_non_empty + 1}: error: header must be '# {stem}' (found: '{actual}')"
        )

    # Front-matter Parsing
    header_lines = []
    idx = first_non_empty + 1
    while idx < len(lines):
        line_s = lines[idx].strip()
        if line_s.startswith("## "):
            break
        if line_s:
            header_lines.append((idx + 1, line_s))
        idx += 1

    imports_list: list[str] = []
    imports_l_num: int = 1
    types_from_map: dict[str, list[str]] = {}
    implements_type: str | None = None
    assembles_type: str | None = None
    instantiates_types: list[str] = []

    last_kind = 0  # 1: imports / assembles, 2: types from, 3: implements
    for l_num, line_s in header_lines:
        if line_s.startswith("assembles:"):
            if last_kind > 1:
                errors.append(
                    f"{fname}:{l_num}: error: 'assembles:' must come before 'types from' and 'implements:'"
                )
            last_kind = 1
            assembles_type = line_s[len("assembles:") :].strip()
        elif line_s.startswith("imports:"):
            if last_kind > 1:
                errors.append(
                    f"{fname}:{l_num}: error: 'imports:' must come before 'types from' and 'implements:'"
                )
            last_kind = 1
            imports_l_num = l_num
            raw_deps = line_s[len("imports:") :].strip()
            imports_list = [d.strip() for d in raw_deps.split(",") if d.strip()]

            # Check 3: No _impl or _asm imports in non-_asm
            if not is_asm:
                for dep in imports_list:
                    if dep.endswith("_impl"):
                        errors.append(
                            f"{fname}:{l_num}: error: non-assembly specification must not import implementation '{dep}'"
                        )
                    elif dep.endswith("_asm"):
                        errors.append(
                            f"{fname}:{l_num}: error: non-assembly specification must not import assembly '{dep}'"
                        )

        elif line_s.startswith("types from "):
            if last_kind > 2:
                errors.append(
                    f"{fname}:{l_num}: error: 'types from' must come before 'implements:'"
                )
            last_kind = 2
            m = re.match(r"^types from\s+([^:]+):\s*(.*)$", line_s)
            if not m:
                errors.append(
                    f"{fname}:{l_num}: error: malformed 'types from <module>: <types>' line"
                )
            else:
                dep_name = m.group(1).strip()
                types = [t.strip() for t in m.group(2).split(",") if t.strip()]
                types_from_map[dep_name] = types
                # Check 4: types from dep must be imported
                if dep_name not in imports_list:
                    errors.append(
                        f"{fname}:{l_num}: error: 'types from {dep_name}' but '{dep_name}' is not in 'imports:'"
                    )

        elif line_s.startswith("implements:"):
            last_kind = 3
            implements_type = line_s[len("implements:") :].strip()
        elif line_s.startswith("instantiates:"):
            last_kind = 4
            instantiates_types = [
                t.strip()
                for t in line_s[len("instantiates:") :].split(",")
                if t.strip()
            ]
        else:
            errors.append(
                f"{fname}:{l_num}: error: unknown front-matter line '{line_s}'"
            )

    # Check 5: Implementation specs must have implements, assembly specs must have assembles and implements:
    if is_impl and not implements_type:
        errors.append(
            f"{fname}:1: error: implementation specification must declare 'implements: <type>' in front-matter"
        )
    if is_asm and not assembles_type:
        errors.append(
            f"{fname}:1: error: assembly specification must declare 'assembles: <components>' in front-matter"
        )
    if is_asm and not implements_type:
        errors.append(
            f"{fname}:1: error: assembly specification must declare 'implements: <components>' in front-matter"
        )

    # Check 5b: Interface and implementation specifications import usage accountability
    if not is_asm and not is_ext and imports_list:
        low_path = file_path.parent.parent / "low" / f"{stem}.pyi"
        if not low_path.exists():
            parts_cand = file_path.parent.parent.parent if file_path.parent.parent.parent.name == "parts" else None
            candidates: list[Path] = []
            if parts_cand and parts_cand.is_dir():
                candidates = list(parts_cand.glob(f"*/low/{stem}.pyi"))
            if not candidates:
                for p in find_all_parts_dirs():
                    candidates.extend(p.glob(f"*/low/{stem}.pyi"))
                    if candidates:
                        break
            if candidates:
                low_path = candidates[0]

        if low_path.exists():
            try:
                low_text = low_path.read_text(encoding="utf-8")
                low_tree = ast.parse(low_text)
                low_imports: set[str] = set()
                for stmt in low_tree.body:
                    if isinstance(stmt, ast.Import):
                        for a in stmt.names:
                            low_imports.add(a.name)
                            low_imports.add(a.name.split(".")[-1])
                    elif isinstance(stmt, ast.ImportFrom):
                        if stmt.module:
                            low_imports.add(stmt.module)
                            low_imports.add(stmt.module.split(".")[-1])
                        for a in stmt.names:
                            low_imports.add(a.name)
                            low_imports.add(a.name.split(".")[-1])

                if not is_impl:
                    for dep in imports_list:
                        if dep not in low_imports:
                            errors.append(
                                f"{fname}:{imports_l_num}: error: interface specification imports '{dep}', but low-level specification '{low_path.name}' does not use it (unnecessary interface import)"
                            )
                else:
                    # Collect AST symbols (excluding import statements)
                    ast_symbols: set[str] = set()
                    for node in ast.walk(low_tree):
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            continue
                        if isinstance(node, ast.Name):
                            ast_symbols.add(node.id)
                        elif isinstance(node, ast.Attribute):
                            ast_symbols.add(node.attr)
                            val = node.value
                            while isinstance(val, ast.Attribute):
                                val = val.value
                            if isinstance(val, ast.Name):
                                ast_symbols.add(val.id)
                        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                            ast_symbols.add(node.value)

                    # Extract all text under GROUNDING: sections in docstrings
                    grounding_text = ""
                    for node in ast.walk(low_tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                            doc = ast.get_docstring(node)
                            if doc and "GROUNDING:" in doc:
                                in_g = False
                                for line in doc.splitlines():
                                    s = line.strip()
                                    if s == "GROUNDING:":
                                        in_g = True
                                    elif (s.endswith(":") and re.match(r"^[A-Z_]+:$", s)) or s in ("Args:", "Returns:", "Raises:", "Yields:"):
                                        in_g = False
                                    elif in_g:
                                        grounding_text += " " + s

                    def get_dep_exported_classes(dep_name: str) -> set[str]:
                        classes: set[str] = set()
                        candidates: list[Path] = []
                        parts_cand = file_path.parent.parent.parent if file_path.parent.parent.parent.name == "parts" else None
                        if parts_cand and parts_cand.is_dir():
                            candidates = list(parts_cand.glob(f"*/low/{dep_name}.pyi"))
                            if not candidates:
                                candidates = list(parts_cand.glob(f"*/low/{dep_name}_ext.pyi"))
                        if not candidates:
                            for p in find_all_parts_dirs():
                                candidates.extend(p.glob(f"*/low/{dep_name}.pyi"))
                                if not candidates:
                                    candidates.extend(p.glob(f"*/low/{dep_name}_ext.pyi"))
                                if candidates:
                                    break
                        for cand in candidates:
                            try:
                                c_tree = ast.parse(cand.read_text(encoding="utf-8"))
                                for s in c_tree.body:
                                    if isinstance(s, ast.ClassDef):
                                        classes.add(s.name)
                                    elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                        classes.add(s.name)
                                    elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                                        classes.add(s.target.id)
                                    elif isinstance(s, ast.Assign):
                                        for t in s.targets:
                                            if isinstance(t, ast.Name):
                                                classes.add(t.id)
                            except (SyntaxError, OSError):
                                pass
                        return classes

                    for dep in imports_list:
                        dep_classes = get_dep_exported_classes(dep)
                        in_ast = (dep in ast_symbols) or any(c in ast_symbols for c in dep_classes)
                        in_grounding = bool(re.search(r"\b" + re.escape(dep) + r"\b", grounding_text)) or any(
                            bool(re.search(r"\b" + re.escape(c) + r"\b", grounding_text)) for c in dep_classes
                        )
                        if not in_ast and not in_grounding:
                            errors.append(
                                f"{fname}:{imports_l_num}: error: implementation specification imports '{dep}', but '{dep}' is neither utilized in low-level AST nor cited in any GROUNDING: argument in '{low_path.name}'"
                            )
            except (SyntaxError, OSError):
                pass

    # Check 6: Section Headers and Behavior Structure
    if is_ext:
        valid_sections = {"Purpose", "Grounding Gaps Covered"}
    else:
        valid_sections = {"Purpose", "Types and Behavior", "Types", "Behavior"}
    current_section = None

    for l_idx, line in enumerate(lines[idx:], idx + 1):
        line_s = line.strip()
        if line_s.startswith("<!--") and "CLEANROOM METADATA" in line_s:
            break
        if line.startswith("## "):
            current_section = line_s[3:].strip()
            if current_section not in valid_sections:
                errors.append(
                    f"{fname}:{l_idx}: error: unknown section '## {current_section}'"
                )
        elif line.startswith("### "):
            errors.append(
                f"{fname}:{l_idx}: error: '###' sub-headers are prohibited in HLS specifications"
            )
        elif current_section in ("Types and Behavior", "Types", "Behavior"):
            for dep in imports_list:
                if "_" in dep:
                    pat = r"\b" + re.escape(dep) + r"\b"
                else:
                    pat = (
                        r"(`"
                        + re.escape(dep)
                        + r"`|\b"
                        + re.escape(dep)
                        + r"\s+component\b)"
                    )
                if re.search(pat, line):
                    errors.append(
                        f"{fname}:{l_idx}: error: imported component '{dep}' must not appear in '{current_section}'"
                    )

    return errors


lint_hls_file = lint_high_file


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

    expanded_targets: list[Path] = []
    for t in targets:
        if t.is_dir():
            if (t / "parts").is_dir():
                expanded_targets.extend(sorted((t / "parts").glob("*/high/*.md")))
            elif (t / "high").is_dir():
                expanded_targets.extend(sorted((t / "high").glob("*.md")))
            else:
                expanded_targets.extend(sorted(t.glob("*/high/*.md")))
        else:
            expanded_targets.append(t)

    if not targets:
        for p in find_all_parts_dirs():
            expanded_targets.extend(sorted(p.glob("*/high/*.md")))

    all_errors: list[str] = []
    for f in expanded_targets:
        errs = lint_high_file(f)
        all_errors.extend(errs)

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        print(
            f"\n[FAIL] Found {len(all_errors)} HLS structural errors.", file=sys.stderr
        )
        return 1

    print(f"[OK] {len(expanded_targets)} HLS specifications passed structural & boundary lint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
