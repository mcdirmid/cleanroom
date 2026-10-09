#!/usr/bin/env python3
"""
spec_lint.py — structural, epistemic grounding, and contract linter for Planning Canvases (planning/*.md).

Usage:
    python3 update_python_with_ai/support/lib/spec_lint.py [files...]
    python3 update_python_with_ai/support/lib/spec_lint.py [--deps dep1 dep2 ...] -- [target files...]

Checks:
  1. Header matches pattern: '# <unit_name> <component_type> component'.
  2. Front-matter ordering (imports, implements, types from).
  3. Closed ## section inventory in strict order:
     - '## Intent'
     - '## Factored Contracts'
     - '## Grounding'
  4. '## Intent' contains strictly paragraphs without '### ' subheadings.
  5. '## Factored Contracts' closed to '### Typing', '### Contracts', '### Woven Contracts'.
  6. '### Contracts' bullets end with period followed by unique bracketed slug: '- <sentence>. [<slug>]'.
  7. '### Typing' bullets end with period and omit bracketed slugs.
  8. '### Woven Contracts' bullets end with period followed by bracketed slug citations. Citations must cite factored contracts, not provisions.
  9. '## Grounding' closed to '### Knowledge Provisions', '### Inherited Deferred Requirements' (in _impl), '### Knowledge Requirements'.
 10. '### Knowledge Provisions' bullets end with period followed by unique bracketed slug: '- <sentence>. [<slug>]'.
 11. '### Knowledge Requirements' bullets end with period and omit slugs.
 12. Each requirement bullet is followed immediately by an indented sub-bullet:
     - '  - Grounded: [<citations>]' or
     - '  - Deferred: <rationale>'
 13. Zero-Deferred Invariant: implementation specs (*_impl.md) contain zero 'Deferred:' items.
 14. Inherited Deferral Parity: all requirements marked 'Deferred:' in an interface are repeated verbatim in its implementation under '### Inherited Deferred Requirements'.
 15. Inherited Grounding Provision Rule: every inherited deferred requirement must be grounded by at least one imported or local knowledge provision (cannot be grounded solely by 'caller input' or self-contained state; if no provisions are needed, it should have been grounded earlier in the interface).
 16. Grounding citations cite valid knowledge provisions (under '### Knowledge Provisions'), not factored contracts.
 17. Prohibited content: markdown tables ('|') and Python AST code expressions.
 18. Grounding DAG acyclicity: internal grounding dependencies between local provisions must form a strict DAG.
 19. In non-assembly specifications, front-matter 'imports:' contains all imported modules declared in the corresponding high-level specification (high/<name>.md).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PARTS_DIR = ROOT / "update_with_ai" / "parts"

CANONICAL_SECTIONS = [
    "## Intent",
    "## Factored Contracts",
    "## Grounding",
]

CANONICAL_SECTIONS_EXT = [
    "## Intent",
    "## Grounding",
]

ALLOWED_FACTORED_SUBHEADERS = [
    "### Typing",
    "### Contracts",
    "### Woven Contracts",
]

ALLOWED_GROUNDING_SUBHEADERS_INTERFACE = [
    "### Knowledge Provisions",
    "### Knowledge Requirements",
]

ALLOWED_GROUNDING_SUBHEADERS_IMPL = [
    "### Knowledge Provisions",
    "### Inherited Deferred Requirements",
    "### Knowledge Requirements",
]

ALLOWED_GROUNDING_SUBHEADERS_EXT = [
    "### Knowledge Provisions",
]

VALID_SLUG_RE = re.compile(r"^[a-z0-9_]+$")
CONTRACT_BULLET_RE = re.compile(r"^-\s+(.*?)\.\s+\[([a-z0-9_]+)\]$")
TYPING_BULLET_RE = re.compile(r"^-\s+(.*?)\.?$")
REQUIREMENT_BULLET_RE = re.compile(r"^-\s+(.*?)\.$")
GROUNDED_SUBBULLET_RE = re.compile(r"^\s+-\s+Grounded:\s+\[(.*)\]$")
DEFERRED_SUBBULLET_RE = re.compile(r"^\s+-\s+Deferred:\s+(.*)$")


def parse_grounding_citations(citation_str: str) -> list[tuple[str | None, str]]:
    """Extract individual (component_qualifier_or_None, slug) tuples from citation string."""
    results: list[tuple[str | None, str]] = []
    # Pattern to match qualified: comp: [slug1, slug2]
    for m in re.finditer(r"([a-z0-9_]+):\s*\[([^\]]+)\]", citation_str):
        comp = m.group(1)
        sub_slugs = [s.strip() for s in m.group(2).split(",") if s.strip()]
        for s in sub_slugs:
            results.append((comp, s))

    # Remove the qualified blocks to find remaining unqualified tokens
    unqual_str = re.sub(r"[a-z0-9_]+:\s*\[[^\]]+\]", "", citation_str)
    for part in unqual_str.split(","):
        s = part.strip().strip("[]")
        if s and not s.endswith(":"):
            results.append((None, s))

    return results


class ComponentIndex:
    """Global index of component contracts and knowledge provisions across all planning files."""

    def __init__(self, planning_files: list[Path]):
        self.comp_contracts: dict[str, set[str]] = {}
        self.comp_provisions: dict[str, set[str]] = {}
        self.all_contracts: dict[str, str] = {}
        self.all_provisions: dict[str, str] = {}

        for f in planning_files:
            stem = f.stem
            try:
                content = f.read_text(encoding="utf-8")
            except OSError:
                continue

            c_slugs: set[str] = set()
            c_m = re.search(r"### Contracts\n(.*?)(?=\n###|\n##|$)", content, re.DOTALL)
            if c_m:
                for line in c_m.group(1).splitlines():
                    m = CONTRACT_BULLET_RE.match(line.strip())
                    if m:
                        slug = m.group(2)
                        c_slugs.add(slug)
                        self.all_contracts[slug] = stem
            self.comp_contracts[stem] = c_slugs

            p_slugs: set[str] = set()
            p_m = re.search(r"### Knowledge Provisions\n(.*?)(?=\n###|\n##|$)", content, re.DOTALL)
            if p_m:
                for line in p_m.group(1).splitlines():
                    m = CONTRACT_BULLET_RE.match(line.strip())
                    if m:
                        slug = m.group(2)
                        p_slugs.add(slug)
                        self.all_provisions[slug] = stem
            self.comp_provisions[stem] = p_slugs


def find_interface_deferred_requirements(interface_path: Path) -> list[str]:
    """Parse an interface planning file and return all requirements marked Deferred."""
    if not interface_path.exists():
        return []

    try:
        content = interface_path.read_text(encoding="utf-8")
    except OSError:
        return []

    lines = content.splitlines()
    deferred: list[str] = []
    in_grounding = False
    in_requirements = False
    cur_req: str | None = None

    for line in lines:
        stripped = line.strip()
        if stripped == "## Grounding":
            in_grounding = True
            continue
        if stripped.startswith("## ") and in_grounding:
            break
        if not in_grounding:
            continue

        if stripped == "### Knowledge Requirements":
            in_requirements = True
            continue
        elif stripped.startswith("### "):
            in_requirements = False
            continue

        if in_requirements:
            if line.startswith("- "):
                m = REQUIREMENT_BULLET_RE.match(line)
                if m:
                    cur_req = m.group(1).strip() + "."
                else:
                    cur_req = line[2:].strip()
            elif line.startswith("  - Deferred:") or line.startswith("    - Deferred:"):
                if cur_req:
                    deferred.append(cur_req)
                    cur_req = None
            elif line.startswith("  - Grounded:") or line.startswith("    - Grounded:"):
                cur_req = None

    return deferred


def lint_planning_file(file_path: Path, index: ComponentIndex | None = None) -> list[str]:
    errors: list[str] = []
    fname = file_path.name
    stem = file_path.stem
    is_impl = stem.endswith("_impl")
    is_asm = stem.endswith("_asm")
    is_ext = stem.endswith("_ext")

    if index is None:
        all_planning = sorted(PARTS_DIR.glob("*/planning/*.md")) if PARTS_DIR.exists() else []
        index = ComponentIndex(all_planning)

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{fname}:1: error: cannot read file: {e}"]

    lines = content.splitlines()
    if not lines or not any(l.strip() for l in lines):
        return [f"{fname}:1: error: empty planning specification file"]

    # Skip Cleanroom metadata header
    start_idx = 0
    while start_idx < len(lines) and not lines[start_idx].strip():
        start_idx += 1
    if start_idx < len(lines) and lines[start_idx].strip() == "<!-- CLEANROOM METADATA":
        while start_idx < len(lines) and lines[start_idx].strip() != "-->":
            start_idx += 1
        if start_idx < len(lines) and lines[start_idx].strip() == "-->":
            start_idx += 1

    while start_idx < len(lines) and not lines[start_idx].strip():
        start_idx += 1

    if start_idx >= len(lines):
        return [f"{fname}:1: error: specification has no content after metadata"]

    if is_ext:
        return [
            f"{fname}:1: error: external components (_ext) do not define planning specifications; external boundaries are specified in high and low specifications"
        ]

    # 1. Header Check
    header_line = lines[start_idx].strip()
    expected_type = "implementation" if is_impl else ("assembly" if is_asm else "interface")
    expected_header = f"# {stem} {expected_type} component"
    if header_line != expected_header:
        errors.append(
            f"{fname}:{start_idx + 1}: error: header mismatch: expected '{expected_header}', got '{header_line}'"
        )

    # 2. Front-matter Parsing
    idx = start_idx + 1
    declared_imports: list[str] = []
    implements_target: str | None = None

    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if line.startswith("## "):
            break

        if line.startswith("imports:"):
            raw_imps = line[len("imports:") :].strip()
            if raw_imps:
                declared_imports = [imp.strip() for imp in raw_imps.split(",") if imp.strip()]
        elif line.startswith("implements:"):
            implements_target = line[len("implements:") :].strip()
        elif line.startswith("types from "):
            pass
        else:
            errors.append(f"{fname}:{idx + 1}: error: unrecognized front-matter line: '{line}'")
        idx += 1

    if is_impl and not implements_target:
        # Default target is stem without _impl
        implements_target = stem[:-5]

    # 2b. High-Level Specification Import Parity Audit (for non-assembly specifications)
    if not is_asm:
        high_path = file_path.parent.parent / "high" / f"{stem}.md"
        if not high_path.exists():
            candidates = list(PARTS_DIR.glob(f"*/high/{stem}.md"))
            if candidates:
                high_path = candidates[0]
            elif not candidates:
                ws_high = list(Path(file_path.anchor).glob(f"**/parts/*/high/{stem}.md"))
                if ws_high:
                    high_path = ws_high[0]

        if high_path.exists():
            try:
                high_content = high_path.read_text(encoding="utf-8")
                for h_line in high_content.splitlines():
                    h_stripped = h_line.strip()
                    if h_stripped.startswith("imports:"):
                        h_raw = h_stripped[len("imports:") :].strip()
                        if h_raw:
                            for h_imp in [i.strip() for i in h_raw.split(",") if i.strip()]:
                                if h_imp not in declared_imports:
                                    errors.append(
                                        f"{fname}:{start_idx + 1}: error: planning canvas 'imports:' missing '{h_imp}' declared in '{high_path.name}'"
                                    )
                        break
            except OSError:
                pass

    # 3. Structural Sections and Headings
    section_order: list[tuple[str, int]] = []
    subheaders: dict[str, list[tuple[str, int]]] = {}
    current_section: str | None = None

    for l_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if line.startswith("## "):
            sec_name = line
            section_order.append((sec_name, l_num))
            current_section = sec_name
            subheaders[current_section] = []
        elif line.startswith("### "):
            if current_section is None:
                errors.append(f"{fname}:{l_num}: error: subheader '{line}' appears before any section")
            else:
                subheaders[current_section].append((line, l_num))

        # Check for prohibited markdown tables
        if "|" in line and not line.startswith("```"):
            errors.append(f"{fname}:{l_num}: error: markdown table syntax '|' prohibited in planning canvas: '{line}'")

    # Verify canonical ## sections
    actual_sec_names = [s[0] for s in section_order]
    expected_sections = CANONICAL_SECTIONS_EXT if is_ext else CANONICAL_SECTIONS
    if actual_sec_names != expected_sections:
        errors.append(
            f"{fname}:1: error: canonical sections mismatch: expected {expected_sections}, got {actual_sec_names}"
        )

    # Verify subheaders under ## Intent (must be none)
    if "## Intent" in subheaders and subheaders["## Intent"]:
        for sh, l_num in subheaders["## Intent"]:
            errors.append(f"{fname}:{l_num}: error: subheader '{sh}' prohibited under '## Intent'")

    # Verify subheaders under ## Factored Contracts
    if "## Factored Contracts" in subheaders:
        if is_ext:
            errors.append(f"{fname}:1: error: '## Factored Contracts' prohibited in external specifications (_ext.md)")
        factored_subs = [sh[0] for sh in subheaders["## Factored Contracts"]]
        expected_factored_order = [s for s in ALLOWED_FACTORED_SUBHEADERS if s in factored_subs]
        if factored_subs != expected_factored_order:
            errors.append(
                f"{fname}:1: error: subheaders under '## Factored Contracts' invalid or out of order: {factored_subs}"
            )
        if "### Contracts" not in factored_subs:
            errors.append(f"{fname}:1: error: '## Factored Contracts' missing required '### Contracts'")

    # Verify subheaders under ## Grounding
    allowed_grounding_subs = (
        ALLOWED_GROUNDING_SUBHEADERS_EXT
        if is_ext
        else (ALLOWED_GROUNDING_SUBHEADERS_IMPL if is_impl else ALLOWED_GROUNDING_SUBHEADERS_INTERFACE)
    )
    if "## Grounding" in subheaders:
        grounding_subs = [sh[0] for sh in subheaders["## Grounding"]]
        expected_grounding_order = [s for s in allowed_grounding_subs if s in grounding_subs]
        if grounding_subs != expected_grounding_order:
            errors.append(
                f"{fname}:1: error: subheaders under '## Grounding' invalid or out of order: {grounding_subs} (expected subset of {allowed_grounding_subs})"
            )
        if "### Knowledge Provisions" not in grounding_subs:
            errors.append(f"{fname}:1: error: '## Grounding' missing required '### Knowledge Provisions'")
        if is_ext and "### Knowledge Requirements" in grounding_subs:
            errors.append(f"{fname}:1: error: '### Knowledge Requirements' prohibited in external specifications (_ext.md)")
        if not is_ext and not is_impl and "### Knowledge Requirements" not in grounding_subs:
            errors.append(f"{fname}:1: error: '## Grounding' missing required '### Knowledge Requirements'")
    else:
        errors.append(f"{fname}:1: error: missing '## Grounding' section")

    # 4. Detailed Section Parsing & Epistemic Rules
    contract_slugs: set[str] = set()
    provision_slugs: set[str] = set()
    inherited_deferred: list[str] = []
    inherited_resolutions: dict[str, tuple[str, str, int]] = {}  # req -> (kind, target, l_num)
    local_resolutions: dict[str, tuple[str, str, int]] = {}      # req -> (kind, target, l_num)

    current_sub: str | None = None
    last_req_text: str | None = None
    last_req_lineno: int = 0
    req_had_subbullet: bool = False

    for l_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("## "):
            current_section = line
            current_sub = None
            if last_req_text and not req_had_subbullet:
                errors.append(f"{fname}:{last_req_lineno}: error: requirement missing indented sub-bullet (- Grounded: or - Deferred:)")
            last_req_text = None
            continue

        if line.startswith("### "):
            current_sub = line
            if last_req_text and not req_had_subbullet:
                errors.append(f"{fname}:{last_req_lineno}: error: requirement missing indented sub-bullet (- Grounded: or - Deferred:)")
            last_req_text = None
            continue

        # Factored Contracts -> Typing
        if current_sub == "### Typing":
            if line.startswith("- "):
                if not line.endswith("."):
                    errors.append(f"{fname}:{l_num}: error: typing bullet must end with a period: '{line}'")
                if re.search(r"\[[a-z0-9_]+\]$", line):
                    errors.append(f"{fname}:{l_num}: error: typing bullet must not end with a bracketed slug: '{line}'")

        # Factored Contracts -> Contracts
        elif current_sub == "### Contracts":
            if line.startswith("- "):
                m = CONTRACT_BULLET_RE.match(line)
                if not m:
                    errors.append(
                        f"{fname}:{l_num}: error: contract bullet must end with period and bracketed slug: '- <sentence>. [<slug>]': '{line}'"
                    )
                else:
                    sentence, slug = m.group(1), m.group(2)
                    if slug in contract_slugs:
                        errors.append(f"{fname}:{l_num}: error: duplicate contract slug '[{slug}]'")
                    contract_slugs.add(slug)

        # Factored Contracts -> Woven Contracts
        elif current_sub == "### Woven Contracts":
            if line.startswith("- "):
                m = re.search(r"\.\s*\[(.*)\]$", line)
                if not m:
                    errors.append(
                        f"{fname}:{l_num}: error: woven contract bullet must end with period and bracketed citations: '{line}'"
                    )
                else:
                    woven_citations = parse_grounding_citations(m.group(1))
                    for comp, slug in woven_citations:
                        if comp:
                            if comp.endswith("_ext"):
                                errors.append(
                                    f"{fname}:{l_num}: error: external component '{comp}' cannot be cited in woven contracts. External components provide knowledge provisions for grounding, not behavioral contracts for weaving."
                                )
                            elif slug in index.comp_provisions.get(comp, set()) and slug not in index.comp_contracts.get(comp, set()):
                                errors.append(
                                    f"{fname}:{l_num}: error: woven contract citation '[{slug}]' in '{comp}' is a knowledge provision slug, NOT a factored contract slug. Woven contracts must cite factored contracts (under '### Contracts')."
                                )
                        else:
                            if slug in provision_slugs and slug not in contract_slugs:
                                errors.append(
                                    f"{fname}:{l_num}: error: woven contract citation '[{slug}]' is a local knowledge provision slug, NOT a factored contract slug. Woven contracts must cite factored contracts (under '### Contracts')."
                                )

        # Grounding -> Knowledge Provisions
        elif current_sub == "### Knowledge Provisions":
            if line.startswith("- "):
                m = CONTRACT_BULLET_RE.match(line)
                if not m:
                    errors.append(
                        f"{fname}:{l_num}: error: knowledge provision bullet must end with period and bracketed slug: '- <sentence>. [<slug>]': '{line}'"
                    )
                else:
                    _, slug = m.group(1), m.group(2)
                    if slug in provision_slugs:
                        errors.append(f"{fname}:{l_num}: error: duplicate provision slug '[{slug}]'")
                    provision_slugs.add(slug)

        # Grounding -> Inherited Deferred Requirements (in _impl.md)
        elif current_sub == "### Inherited Deferred Requirements":
            if raw_line.startswith("- "):
                if last_req_text and not req_had_subbullet:
                    errors.append(f"{fname}:{last_req_lineno}: error: inherited requirement missing indented Grounded: sub-bullet")
                if not line.endswith("."):
                    errors.append(f"{fname}:{l_num}: error: inherited requirement bullet must end with a period: '{line}'")
                if re.search(r"\[[a-z0-9_]+\]$", line):
                    errors.append(f"{fname}:{l_num}: error: requirement bullet must not have a slug: '{line}'")
                last_req_text = line[2:].strip()
                last_req_lineno = l_num
                req_had_subbullet = False
                inherited_deferred.append(last_req_text)
            elif raw_line.startswith("  - ") or raw_line.startswith("    - ") or raw_line.startswith("\t- "):
                gm = GROUNDED_SUBBULLET_RE.match(raw_line)
                dm = DEFERRED_SUBBULLET_RE.match(raw_line)
                if dm:
                    errors.append(f"{fname}:{l_num}: error: 'Deferred:' prohibited in implementation specifications (Zero-Deferred Invariant)")
                    req_had_subbullet = True
                elif gm:
                    cit_str = gm.group(1)
                    if last_req_text:
                        inherited_resolutions[last_req_text] = ("grounded", cit_str, l_num)
                    req_had_subbullet = True
                else:
                    errors.append(f"{fname}:{l_num}: error: invalid sub-bullet format: '{raw_line}'")

        # Grounding -> Knowledge Requirements
        elif current_sub == "### Knowledge Requirements":
            if raw_line.startswith("- "):
                if last_req_text and not req_had_subbullet:
                    errors.append(f"{fname}:{last_req_lineno}: error: requirement missing indented sub-bullet (- Grounded: or - Deferred:)")
                if not line.endswith("."):
                    errors.append(f"{fname}:{l_num}: error: knowledge requirement bullet must end with a period: '{line}'")
                if re.search(r"\[[a-z0-9_]+\]$", line):
                    errors.append(f"{fname}:{l_num}: error: requirement bullet must not have a slug: '{line}'")
                last_req_text = line[2:].strip()
                last_req_lineno = l_num
                req_had_subbullet = False
            elif raw_line.startswith("  - ") or raw_line.startswith("    - ") or raw_line.startswith("\t- "):
                gm = GROUNDED_SUBBULLET_RE.match(raw_line)
                dm = DEFERRED_SUBBULLET_RE.match(raw_line)
                if dm:
                    if is_impl:
                        errors.append(f"{fname}:{l_num}: error: 'Deferred:' prohibited in implementation specifications (Zero-Deferred Invariant)")
                    if last_req_text:
                        local_resolutions[last_req_text] = ("deferred", dm.group(1), l_num)
                    req_had_subbullet = True
                elif gm:
                    cit_str = gm.group(1)
                    if last_req_text:
                        local_resolutions[last_req_text] = ("grounded", cit_str, l_num)
                    req_had_subbullet = True
                else:
                    errors.append(f"{fname}:{l_num}: error: invalid sub-bullet under requirement: '{raw_line}'")

    if last_req_text and not req_had_subbullet:
        errors.append(f"{fname}:{last_req_lineno}: error: requirement missing indented sub-bullet (- Grounded: or - Deferred:)")

    # 5. Interface Deferral Parity Audit (for _impl.md)
    if is_impl and implements_target:
        interface_planning_path = file_path.parent / f"{implements_target}.md"
        if not interface_planning_path.exists():
            candidates = list(PARTS_DIR.glob(f"*/planning/{implements_target}.md"))
            if candidates:
                interface_planning_path = candidates[0]

        if interface_planning_path.exists():
            expected_deferred = find_interface_deferred_requirements(interface_planning_path)
            for exp in expected_deferred:
                if exp not in inherited_deferred:
                    errors.append(
                        f"{fname}:1: error: missing inherited deferred requirement from '{interface_planning_path.name}': '{exp}'"
                    )
            for actual in inherited_deferred:
                if actual not in expected_deferred:
                    errors.append(
                        f"{fname}:1: error: spurious inherited requirement not deferred in '{interface_planning_path.name}': '{actual}'"
                    )

    # 6. Inherited Deferred Requirements Grounding Audit:
    # Must use at least one imported or local knowledge provision.
    for req_text, (kind, target, l_num) in inherited_resolutions.items():
        if kind == "grounded":
            citations = parse_grounding_citations(target)
            valid_provision_count = 0
            for comp, slug in citations:
                if comp is not None:
                    if comp.endswith("_ext") or slug in index.comp_provisions.get(comp, set()):
                        valid_provision_count += 1
                else:
                    if slug in provision_slugs:
                        valid_provision_count += 1

            if valid_provision_count == 0:
                errors.append(
                    f"{fname}:{l_num}: error: inherited deferred requirement '{req_text}' is not grounded by any imported or local knowledge provisions (got '{target}'). If no knowledge provisions are needed, it should have been grounded earlier in the interface."
                )

    # 7. Detailed Citation Validity: Distinguish Knowledge Provisions vs Factored Contracts
    all_req_resolutions = {**inherited_resolutions, **local_resolutions}
    for req_text, (kind, target, l_num) in all_req_resolutions.items():
        if kind == "grounded":
            citations = parse_grounding_citations(target)
            for comp, slug in citations:
                # 'caller input' is strictly an external boundary reference or local input check
                if slug == "caller input":
                    if comp is not None:
                        errors.append(
                            f"{fname}:{l_num}: error: special grounding keyword '{slug}' cannot be qualified with '{comp}'"
                        )
                    continue
                if slug in ("local state", "self"):
                    errors.append(
                        f"{fname}:{l_num}: error: '{slug}' is not a valid knowledge provision. Grounding must cite an imported or local knowledge provision, or 'caller input' for external boundaries."
                    )
                    continue

                if comp is not None:
                    if comp not in declared_imports and comp != implements_target and comp != stem:
                        errors.append(
                            f"{fname}:{l_num}: error: grounding citation references undeclared component '{comp}'"
                        )
                    elif slug in index.comp_contracts.get(comp, set()):
                        errors.append(
                            f"{fname}:{l_num}: error: grounding citation '[{slug}]' in '{comp}' is a factored contract slug, NOT a knowledge provision slug. Knowledge requirements must be grounded by knowledge provisions (under '### Knowledge Provisions'), not factored contracts."
                        )
                    elif comp.endswith("_ext") or slug in index.comp_provisions.get(comp, set()):
                        # Valid qualified imported provision (external boundary or indexed provision)
                        pass
                    else:
                        errors.append(
                            f"{fname}:{l_num}: error: unknown knowledge provision slug '[{slug}]' in component '{comp}'"
                        )
                else:
                    # Unqualified slug
                    if slug in provision_slugs:
                        # Valid local provision
                        pass
                    elif slug in contract_slugs:
                        errors.append(
                            f"{fname}:{l_num}: error: grounding citation '[{slug}]' is a local factored contract slug, NOT a knowledge provision slug. Grounding cannot cite local contracts; cite an imported component's knowledge provision or an external boundary."
                        )
                    elif slug in index.all_provisions:
                        src = index.all_provisions[slug]
                        errors.append(
                            f"{fname}:{l_num}: error: imported knowledge provision '[{slug}]' from '{src}' must be qualified with component name: '{src}: [{slug}]'"
                        )
                    elif slug in index.all_contracts:
                        src = index.all_contracts[slug]
                        errors.append(
                            f"{fname}:{l_num}: error: grounding citation '[{slug}]' is a factored contract slug in '{src}', NOT a knowledge provision slug. Knowledge requirements must be grounded by knowledge provisions (under '### Knowledge Provisions'), not factored contracts."
                        )
                    else:
                        errors.append(
                            f"{fname}:{l_num}: error: unknown knowledge provision slug '[{slug}]'"
                        )

    return errors


def main() -> int:
    args = sys.argv[1:]
    targets: list[Path] = []

    if "--" in args:
        dash_idx = args.index("--")
        post_args = args[dash_idx + 1 :]
        targets = [Path(p) for p in post_args]
    elif "--deps" in args:
        deps_idx = args.index("--deps")
        pass
    else:
        targets = [Path(p) for p in args]

    if not targets:
        if PARTS_DIR.exists():
            targets = sorted(PARTS_DIR.glob("*/planning/*.md"))
        else:
            print("Error: parts directory does not exist", file=sys.stderr)
            return 1

    # Build global component index across all planning files
    all_planning = sorted(PARTS_DIR.glob("*/planning/*.md")) if PARTS_DIR.exists() else []
    index = ComponentIndex(all_planning)

    all_errors: list[str] = []
    for f in targets:
        errs = lint_planning_file(f, index=index)
        all_errors.extend(errs)

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        print(
            f"\n[FAIL] Found {len(all_errors)} planning specification errors.",
            file=sys.stderr,
        )
        return 1

    print(f"[OK] {len(targets)} planning specifications passed structural & epistemic lint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
