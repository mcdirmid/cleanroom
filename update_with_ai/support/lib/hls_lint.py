#!/usr/bin/env python3
"""
hls_lint.py — lightweight structural and boundary linter for High-Level Specifications.

Usage:
    python3 update_with_ai/support/lib/hls_lint.py [files...]
    python3 update_with_ai/support/lib/hls_lint.py [--deps dep1 dep2 ...] -- [target files...]

Checks:
  1. Header matches filename (# <name>).
  2. Front-matter ordering: `imports:` comes first (if any), followed by `types from <dep>:`, followed by `implements:` (if implementation/assembly).
  3. No `imports:` of `*_impl` or `*_asm` components in non-`*_asm` components.
  4. Every `types from <dep>:` corresponds to an imported module in `imports:`.
  5. Implementation specs (`*_impl.md`) must declare `implements: <type>` in front-matter.
  6. Closed section inventory: `## Purpose`, `## Types`, `## Behavior`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SPECS_DIR = ROOT / "update_with_ai" / "specs" / "high"


def lint_hls_file(file_path: Path) -> list[str]:
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
    first_non_empty = 0
    while first_non_empty < len(lines) and not lines[first_non_empty].strip():
        first_non_empty += 1
        
    if first_non_empty >= len(lines) or not lines[first_non_empty].startswith(f"# {stem}"):
        actual = lines[first_non_empty].strip() if first_non_empty < len(lines) else "EOF"
        errors.append(f"{fname}:{first_non_empty+1}: error: header must be '# {stem}' (found: '{actual}')")

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
    types_from_map: dict[str, list[str]] = {}
    implements_type: str | None = None
    assembles_type: str | None = None
    instantiates_types: list[str] = []

    last_kind = 0  # 1: imports, 2: types from, 3: implements
    for l_num, line_s in header_lines:
        if line_s.startswith("imports:"):
            if last_kind > 1:
                errors.append(f"{fname}:{l_num}: error: 'imports:' must come before 'types from' and 'implements:'")
            last_kind = 1
            raw_deps = line_s[len("imports:"):].strip()
            imports_list = [d.strip() for d in raw_deps.split(",") if d.strip()]
            
            # Check 3: No _impl or _asm imports in non-_asm
            if not is_asm:
                for dep in imports_list:
                    if dep.endswith("_impl"):
                        errors.append(f"{fname}:{l_num}: error: non-assembly specification must not import implementation '{dep}'")
                    elif dep.endswith("_asm"):
                        errors.append(f"{fname}:{l_num}: error: non-assembly specification must not import assembly '{dep}'")
                        
        elif line_s.startswith("types from "):
            if last_kind > 2:
                errors.append(f"{fname}:{l_num}: error: 'types from' must come before 'implements:'")
            last_kind = 2
            m = re.match(r"^types from\s+([^:]+):\s*(.*)$", line_s)
            if not m:
                errors.append(f"{fname}:{l_num}: error: malformed 'types from <module>: <types>' line")
            else:
                dep_name = m.group(1).strip()
                types = [t.strip() for t in m.group(2).split(",") if t.strip()]
                types_from_map[dep_name] = types
                # Check 4: types from dep must be imported
                if dep_name not in imports_list:
                    errors.append(f"{fname}:{l_num}: error: 'types from {dep_name}' but '{dep_name}' is not in 'imports:'")
                    
        elif line_s.startswith("assembles:"):
            last_kind = 3
            assembles_type = line_s[len("assembles:"):].strip()
        elif line_s.startswith("implements:"):
            last_kind = 3
            implements_type = line_s[len("implements:"):].strip()
        elif line_s.startswith("instantiates:"):
            last_kind = 4
            instantiates_types = [t.strip() for t in line_s[len("instantiates:"):].split(",") if t.strip()]
        else:
            errors.append(f"{fname}:{l_num}: error: unknown front-matter line '{line_s}'")

    # Check 5: Implementation and assembly specs must have assembles:
    target_assemble = assembles_type or implements_type
    if (is_impl or is_asm) and not target_assemble:
        spec_kind = "assembly" if is_asm else "implementation"
        errors.append(f"{fname}:1: error: {spec_kind} specification must declare 'assembles: <type>' in front-matter")


    # Check 6: Section Headers and Behavior Structure
    if is_ext:
        valid_sections = {"Purpose", "Grounding Gaps Covered"}
    else:
        valid_sections = {"Purpose", "Types and Behavior", "Types", "Behavior"}
    current_section = None

    for l_idx, line in enumerate(lines[idx:], idx + 1):
        line_s = line.strip()
        if line.startswith("## "):
            current_section = line_s[3:].strip()
            if current_section not in valid_sections:
                errors.append(f"{fname}:{l_idx}: error: unknown section '## {current_section}'")
        elif line.startswith("### "):
            errors.append(f"{fname}:{l_idx}: error: '###' sub-headers are prohibited in HLS specifications")
        elif current_section in ("Types and Behavior", "Types", "Behavior"):
            for dep in imports_list:
                if "_" in dep:
                    pat = r"\b" + re.escape(dep) + r"\b"
                else:
                    pat = r"(`" + re.escape(dep) + r"`|\b" + re.escape(dep) + r"\s+component\b)"
                if re.search(pat, line):
                    errors.append(f"{fname}:{l_idx}: error: imported component '{dep}' must not appear in '{current_section}'")

    return errors


def main() -> int:
    args = sys.argv[1:]
    deps: list[Path] = []
    targets: list[Path] = []

    if "--" in args:
        dash_idx = args.index("--")
        pre_args = args[:dash_idx]
        post_args = args[dash_idx + 1:]
        if "--deps" in pre_args:
            deps_idx = pre_args.index("--deps")
            deps = [Path(p) for p in pre_args[deps_idx + 1:]]
        targets = [Path(p) for p in post_args]
    elif "--deps" in args:
        deps_idx = args.index("--deps")
        deps = [Path(p) for p in args[deps_idx + 1:]]
    else:
        targets = [Path(p) for p in args]

    if not targets:
        if not SPECS_DIR.exists():
            print(f"Error: specs directory {SPECS_DIR} does not exist", file=sys.stderr)
            return 1
        targets = sorted(SPECS_DIR.glob("*.md"))

    all_errors: list[str] = []
    for f in targets:
        errs = lint_hls_file(f)
        all_errors.extend(errs)

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        print(f"\n[FAIL] Found {len(all_errors)} HLS structural errors.", file=sys.stderr)
        return 1

    print(f"[OK] {len(targets)} HLS specifications passed structural & boundary lint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
