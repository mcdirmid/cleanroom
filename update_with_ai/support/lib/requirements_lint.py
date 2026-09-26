#!/usr/bin/env python3
"""requirements_lint.py — structural and boundary linter for Requirements Specifications.

Usage:
    python3 update_with_ai/support/lib/requirements_lint.py [files...]
    python3 update_with_ai/support/lib/requirements_lint.py [--deps dep1 dep2 ...] -- [target files...]

Checks:
  1. Header matches '# <stem> <component_type> component' (interface or implementation).
  2. Front-matter ordering: 'imports:' first (if any), followed by 'implements:' (required for implementation).
  3. Interface components must not declare 'implements:'.
  4. Closed section inventory: strictly '## Assumptions and Requirements' with subsections '### Assumptions' (optional) and '### Requirements'.
  5. Every assumption and requirement sentence must end with a period.
  6. No formula notation or quantifiers ('for any', 'there exists', 'v_call', 'v_param', '==', '!=').
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PARTS_DIR = ROOT / "update_with_ai" / "parts"

PROHIBITED_FORMULA_PATTERNS = [
    (re.compile(r"\bfor any\b"), "universal quantifier 'for any'"),
    (re.compile(r"\bthere exists\b"), "existential quantifier 'there exists'"),
    (re.compile(r"\bv_call\b"), "formula variable 'v_call'"),
    (re.compile(r"\bv_param\b"), "formula variable 'v_param'"),
    (re.compile(r"=="), "equality operator '=='"),
    (re.compile(r"!="), "inequality operator '!='"),
]


def lint_requirements_file(file_path: Path) -> list[str]:
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
        return [f"{fname}:1: error: empty requirements specification file"]

    # 1. Header Check
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    if idx >= len(lines):
        return [f"{fname}:1: error: file contains no content"]

    header_line = lines[idx].strip()
    expected_comp_type = (
        "implementation"
        if is_impl
        else ("assembly" if is_asm else ("external" if is_ext else "interface"))
    )
    expected_header = f"# {stem} {expected_comp_type} component"
    if header_line != expected_header:
        errors.append(
            f"{fname}:{idx + 1}: error: header must be '{expected_header}' (found: '{header_line}')"
        )
    idx += 1

    # 2. Front-matter Check
    front_matter_keys: list[tuple[str, int]] = []
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if line.startswith("## "):
            break
        if ":" in line:
            key = line.split(":", 1)[0].strip()
            if key not in ("imports", "implements", "assembles"):
                errors.append(
                    f"{fname}:{idx + 1}: error: invalid front-matter key: '{key}'"
                )
            front_matter_keys.append((key, idx + 1))
        else:
            errors.append(
                f"{fname}:{idx + 1}: error: unexpected line in front-matter: '{line}'"
            )
        idx += 1

    keys_only = [k for k, _ in front_matter_keys]
    if is_impl and "implements" not in keys_only:
        errors.append(
            f"{fname}:1: error: implementation component must declare 'implements:'"
        )
    if not is_impl and not is_asm and "implements" in keys_only:
        errors.append(
            f"{fname}:1: error: interface component must not declare 'implements:'"
        )
    if "imports" in keys_only and "implements" in keys_only:
        if keys_only.index("imports") > keys_only.index("implements"):
            errors.append(
                f"{fname}:1: error: 'imports:' must precede 'implements:' in front-matter"
            )

    # 3. Section and Item Checks
    current_section = ""
    current_subsection = ""
    has_assumptions_and_requirements = False
    has_requirements_subsection = False

    while idx < len(lines):
        raw_line = lines[idx]
        line = raw_line.strip()
        line_num = idx + 1
        idx += 1

        if not line:
            continue

        if line.startswith("## "):
            section_title = line[3:].strip()
            if section_title not in ("Assumptions and Requirements", "Grounding Facts"):
                errors.append(
                    f"{fname}:{line_num}: error: invalid section '{line}'; section inventory is closed to '## Assumptions and Requirements' and optional '## Grounding Facts'"
                )
            elif section_title == "Assumptions and Requirements":
                has_assumptions_and_requirements = True
            elif section_title == "Grounding Facts":
                if not has_assumptions_and_requirements:
                    errors.append(
                        f"{fname}:{line_num}: error: '## Grounding Facts' must follow '## Assumptions and Requirements'"
                    )
            current_section = section_title
            current_subsection = ""
            continue

        if line.startswith("### "):
            sub_title = line[4:].strip()
            if current_section == "Assumptions and Requirements":
                if sub_title not in ("Assumptions", "Requirements"):
                    errors.append(
                        f"{fname}:{line_num}: error: invalid subsection '{line}' in '{current_section}'; subsections are closed strictly to '### Assumptions' and '### Requirements'"
                    )
                if sub_title == "Requirements":
                    has_requirements_subsection = True
                if sub_title == "Assumptions" and has_requirements_subsection:
                    errors.append(
                        f"{fname}:{line_num}: error: '### Assumptions' must precede '### Requirements'"
                    )
            elif current_section == "Grounding Facts":
                if not any(sub_title.startswith(prefix) for prefix in ("Knowledge", "Action")):
                    errors.append(
                        f"{fname}:{line_num}: error: invalid subsection '{line}' in '## Grounding Facts'; subsections describe '### Knowledge Needed' or '### Actions Needed'"
                    )
            current_subsection = sub_title
            continue

        if line.startswith("#"):
            errors.append(
                f"{fname}:{line_num}: error: unsupported heading level: '{line}'"
            )
            continue

        # Item line checks
        if current_section == "Assumptions and Requirements" and current_subsection in (
            "Assumptions",
            "Requirements",
        ):
            if not line.endswith("."):
                errors.append(
                    f"{fname}:{line_num}: error: requirement or assumption sentence must end with a period: '{line}'"
                )
            for pat, desc in PROHIBITED_FORMULA_PATTERNS:
                if pat.search(line):
                    errors.append(
                        f"{fname}:{line_num}: error: prohibited {desc} in requirement sentence: '{line}'"
                    )

    if not has_assumptions_and_requirements:
        errors.append(
            f"{fname}:1: error: missing required section '## Assumptions and Requirements'"
        )
    if not has_requirements_subsection:
        errors.append(f"{fname}:1: error: missing required subsection '### Requirements'")

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
            targets = sorted(PARTS_DIR.glob("*/requirements/*.md"))
        else:
            print("Error: parts directory does not exist", file=sys.stderr)
            return 1

    all_errors: list[str] = []
    for f in targets:
        errs = lint_requirements_file(f)
        all_errors.extend(errs)

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        print(
            f"\n[FAIL] Found {len(all_errors)} requirements structural errors.",
            file=sys.stderr,
        )
        return 1

    print(
        f"[OK] {len(targets)} requirements specifications passed structural lint."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
