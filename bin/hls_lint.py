#!/usr/bin/env python3
"""
hls_lint.py — lint high-level specification files per guides/high_level_spec.md.

Usage:
    python3 bin/hls_lint.py [files...]     # default: all *-high.md under specs/

Checks (E = error, exits nonzero; W = warning, does not affect exit code):
  E  filename/header mismatch
  E  unknown front-matter key
  E  `terms (owned)` in an implementation spec (terms are owned by interfaces)
  E  `terms (owned)` without an `## Owned definitions` section, or vice versa
  E  `terms (from X)` where X has no spec, or the term is not owned by X
  E  `terms (refined)` term not owned by the fulfilled interface or a listed owner
  E  refined term without a refinement detail (impl: `### Refined terms`; interface: mentioned in Owned definitions / Observable dataflow)
  E  multi-word term used in the body without being owned, referenced, or refined
  E  table in a file without a sanctioned table (agent_loop logger events, agent_node_clean_logic_impl outcome mapping)
  E  non-rectangular table (row column count differs from the header)
  E  "client" appears in an implementation spec
  E  "returns" appears anywhere (prohibited; use provides/signals/delegates)
  E  Observable dataflow line states preservation ("unchanged", "as declared", "as stored", "the declared/recorded X", "exactly as")
  E  old-format markers (HTML dependency comments, "## Interface:", exports/imports sections, "does not restate")
  E  backticked import that is not an existing spec
  E  interface spec without `## Contract`; implementation spec without `## Deltas beyond the`
  E  interface spec (filename without "impl") containing `fulfills:`; implementation spec (`*_impl*` filename) missing `fulfills:`
  E  `fulfills:` or `imports:` referencing the file itself (self-dependency)
  E  section order deviates from the canonical order for the spec kind
  W  `## Unported` section present (unported knowledge remains)
  W  no `## Non-concerns` section
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "update_with_ai" / "specs"

# Files whose tables are sanctioned rectangular matrices (guide: Reading Model).
SANCTIONED_TABLES = {"agent_loop-high.md", "agent_node_clean_logic_impl-high.md"}

# Single-word terms distinctive enough to enforce like multi-word terms.
STRONG_TERMS = {"blame", "dirty", "cleaning", "stub"}

# Preservation phrases prohibited in the Observable dataflow section (guide:
# "no mention means no change"); the Contract may assert fidelity.
_DATAFLOW_PRESERVATION_RE = re.compile(
    r"\b(?:as declared|as stored|unchanged|the declared|the recorded|exactly as)\b",
    re.IGNORECASE,
)
# "run" (agent_loop) is checked only in nominal usage: verbs like "run a cleaning
# pass" are ordinary English and must not be flagged.
RUN_PATTERN = re.compile(r"\b(?:a|an|the|agent|this|that|each|every|one|a single)\s+run\b", re.I)

FRONT_MATTER_KEY = re.compile(
    r"^(fulfills|imports|terms \(owned\)|terms \(refined\)|terms \(from [\w]+\)):"
)
TERMS_FROM = re.compile(r"^terms \(from ([\w]+)\): (.*)$")
CANONICAL_INTERFACE_SECTIONS = [
    "Purpose", "Owned definitions", "Observable dataflow", "Contract", "Non-concerns",
]
CANONICAL_IMPL_SECTIONS = ["Deltas beyond the", "Non-concerns"]
OLD_FORMAT_MARKERS = [
    "<!-- Dependencies",
    "## Interface:",
    "## Implementation:",
    "**This implementation exports:**",
    "**This implementation imports:**",
    "does not restate it here",
]

errors: list[str] = []
warnings: list[str] = []


def err(f: Path, msg: str) -> None:
    errors.append(f"{f.name}: {msg}")


def warn(f: Path, msg: str) -> None:
    warnings.append(f"{f.name}: {msg}")


def stem_of(path: Path) -> str:
    return path.stem[:-5] if path.stem.endswith("-high") else path.stem


def spec_map(files: list[Path] | None = None) -> dict[str, Path]:
    paths = files if files is not None else sorted(SPECS_DIR.glob("*-high.md"))
    return {stem_of(p): p for p in paths}


# ---------------------------------------------------------------- parsing

def split_front_matter(text: str) -> tuple[str, str]:
    """Return (front matter, body); front matter is lines before the first '## '."""
    lines = text.splitlines()
    fm: list[str] = []
    i = 1  # skip '# name'
    while i < len(lines) and not lines[i].startswith("## "):
        if lines[i].strip():
            fm.append(lines[i])
        i += 1
    return "\n".join(fm), "\n".join(lines[i:])


def sections(body: str) -> list[tuple[str, str]]:
    """Return [(heading, section_text)] for each '## ' section."""
    out = []
    cur = None
    for line in body.splitlines():
        m = re.match(r"^## (.*)$", line)
        if m:
            cur = m.group(1)
            out.append((cur, ""))
        elif cur is not None:
            out[-1] = (cur, out[-1][1] + line + "\n")
    return out


def get_section(body: str, heading: str) -> str | None:
    for h, text in sections(body):
        if h == heading:
            return text
    return None


def read_all_owned(files: list[Path] | None = None) -> dict[str, str]:
    """term -> owning spec name (without -high), across the given (or all) specs."""
    owned_by: dict[str, str] = {}
    for name, p in spec_map(files).items():
        m = re.search(r"^terms \(owned\): (.+)$", p.read_text(encoding="utf-8"), re.M)
        if m:
            for term in m.group(1).split(","):
                term = term.strip()
                if term:
                    owned_by.setdefault(term, name)
    return owned_by


def parse_refined(value: str) -> set[str]:
    """Parse 'a -> desc, b -> desc' into term names {a, b}."""
    return {t.strip() for t in re.findall(r"([\w ]+?) ->", value)}


def term_in_text(term: str, text: str) -> bool:
    """True if the term appears as a standalone word (not inside a hyphenated compound)."""
    return re.search(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", text, re.I) is not None


# ---------------------------------------------------------------- checks

def check_front_matter(f: Path, text: str) -> tuple[set[str], dict[str, set[str]], set[str]]:
    """Returns (owned, terms_from, refined); validates front-matter keys."""
    fm, _ = split_front_matter(text)
    owned: set[str] = set()
    terms_from: dict[str, set[str]] = {}
    refined: set[str] = set()
    for line in fm.splitlines():
        line = line.strip()
        if not line:
            continue
        if not FRONT_MATTER_KEY.match(line):
            err(f, f"unknown front-matter line: {line!r}")
            continue
        key, _, value = line.partition(":")
        if key == "terms (owned)":
            owned = {t.strip() for t in value.split(",") if t.strip()}
        elif key == "terms (refined)":
            refined = parse_refined(value)
        elif key.startswith("terms (from "):
            m = TERMS_FROM.match(line)
            terms_from[m.group(1)] = {t.strip() for t in m.group(2).split(",") if t.strip()}
        # fulfills / imports validated elsewhere
    return owned, terms_from, refined


def check_terms(f: Path, text: str, owned: set[str], terms_from: dict[str, set[str]], refined: set[str], is_impl: bool, files: list[Path] | None = None) -> None:
    names = set(spec_map(files))
    owned_by = read_all_owned(files)

    if is_impl and owned:
        err(f, f"implementation spec declares `terms (owned)`; terms are owned by interfaces: {sorted(owned)}")

    has_defs = "## Owned definitions" in text
    if owned and not has_defs:
        err(f, "`terms (owned)` present but no `## Owned definitions` section")
    if has_defs and not owned:
        err(f, "`## Owned definitions` present but no `terms (owned)` front-matter line")
    if owned and has_defs:
        defs_text = get_section(split_front_matter(text)[1], "Owned definitions") or ""
        for term in owned:
            if not re.search(rf"^-\s*\**{re.escape(term)}\**\s*:", defs_text, re.M | re.I):
                err(f, f"owned term '{term}' has no definition line in `## Owned definitions`")

    for owner, terms in terms_from.items():
        if owner not in names:
            err(f, f"`terms (from {owner})` but no spec {owner}-high.md")
            continue
        owner_owned = {t for t, o in owned_by.items() if o == owner}
        for term in terms:
            if term not in owner_owned:
                err(f, f"`terms (from {owner})` lists '{term}', which {owner}-high.md does not own")

    allowed_owners = set(terms_from.keys())
    fm, body = split_front_matter(text)
    m = re.search(r"^fulfills: (.+)$", fm, re.M)
    if m:
        allowed_owners.add(m.group(1).strip().strip("`"))
    for term in refined:
        if term not in owned_by:
            err(f, f"refined term '{term}' is not owned by any interface")
            continue
        if owned_by[term] not in allowed_owners and owned_by[term] != stem_of(f):
            err(f, f"refined term '{term}' is owned by {owned_by[term]}, not by the fulfilled interface or a listed owner")
    if refined:
        if is_impl:
            if "### Refined terms" not in text:
                err(f, "`terms (refined)` present but no `### Refined terms` section in the Deltas")
        else:
            detail = (get_section(body, "Owned definitions") or "") + (get_section(body, "Observable dataflow") or "")
            for term in refined:
                if not term_in_text(term, detail):
                    err(f, f"refined term '{term}' not detailed in Owned definitions or Observable dataflow")

    allowed = owned | {t for ts in terms_from.values() for t in ts} | refined
    body_without_defs = "\n".join(txt for h, txt in sections(body) if h != "Owned definitions")
    for term, owner in owned_by.items():
        if owner == stem_of(f) or term in allowed:
            continue
        if " " in term:
            matched = term_in_text(term, body_without_defs)
        elif term in STRONG_TERMS:
            matched = term_in_text(term, body_without_defs)
        elif term == "run":
            matched = RUN_PATTERN.search(body_without_defs) is not None
        else:
            continue
        if matched:
            err(f, f"uses '{term}' (owned by {owner}-high.md) without listing it in `terms (from {owner})`")


def _is_impl(f: Path) -> bool:
    """Implementation specs are named `*_impl*` (dag_impl-high.md,
    bazel_graph_storage_impl-low.md); every other file is an interface spec."""
    return "impl" in f.stem


def check_structure(f: Path, text: str, files: list[Path] | None = None) -> tuple[bool, str]:
    """Returns (is_impl, body); checks structural rules.

    Interface-vs-implementation is decided by filename ("impl" in the stem),
    not by content: a spec that fulfills an interface must say so in its name.
    """
    fm, body = split_front_matter(text)
    m = re.search(r"^fulfills: (.+)$", fm, re.M)
    is_impl = _is_impl(f)
    names = set(spec_map(files))
    if is_impl:
        if m is None:
            err(f, "implementation spec missing `fulfills:`; an implementation fulfills exactly one interface")
        else:
            target = m.group(1).strip().strip("`")
            if target not in names:
                err(f, f"fulfills: unknown spec '{target}'")
            elif target == stem_of(f):
                err(f, f"fulfills: spec cannot fulfill itself ('{target}')")
        if "## Contract" in body:
            err(f, "implementation spec contains `## Contract`; the contract is inherited from the fulfilled interface")
        if "## Deltas beyond the" not in body:
            err(f, "implementation spec missing `## Deltas beyond the <interface> contract`")
    else:
        if m is not None:
            err(f, "interface spec contains `fulfills:`; only implementation specs (named *_impl*) fulfill an interface")
        if "## Contract" not in body:
            err(f, "interface spec missing `## Contract`")
        if "## Deltas beyond the" in body:
            err(f, "interface spec contains a Deltas section")

    canon = CANONICAL_IMPL_SECTIONS if is_impl else CANONICAL_INTERFACE_SECTIONS
    heads = [h for h, _ in sections(body)]
    present = [c for c in canon if any(h.startswith(c) for h in heads)]
    actual = [next(c for c in canon if h.startswith(c)) for h in heads if any(h.startswith(c) for c in canon)]
    if actual != present:
        err(f, f"section order {actual} deviates from canonical {present}")

    if "## Unported" in [h for h, _ in sections(body)]:
        warn(f, "`## Unported` section present (unported knowledge remains)")
    if "Non-concerns" not in [h for h, _ in sections(body)]:
        warn(f, "no `## Non-concerns` section")

    if is_impl and re.search(r"\bclient\b", body, re.I):
        err(f, "implementation spec mentions 'client'")
    return is_impl, body


def check_dataflow(f: Path, body: str) -> None:
    """Flag preservation/echo lines in the Observable dataflow section.

    Guide: each dataflow line states one change; preservation lines
    ("unchanged", "as declared", "as stored", "the declared/recorded X",
    "exactly as") are prohibited — no mention means no change. The Contract
    may assert fidelity; this check is scoped to the dataflow section only.
    """
    dataflow = get_section(body, "Observable dataflow")
    if not dataflow:
        return
    for line in dataflow.splitlines():
        if _DATAFLOW_PRESERVATION_RE.search(line):
            err(f, f"Observable dataflow preservation line (prohibited): {line.strip()}")


def check_language(f: Path, text: str) -> None:
    if re.search(r"\breturns\b", text, re.I):
        err(f, "'returns' is prohibited (use provides/signals/delegates)")
    for marker in OLD_FORMAT_MARKERS:
        if marker in text:
            err(f, f"old-format marker present: {marker!r}")
    for tok in ("True", "False", "None"):
        if re.search(r"`" + tok + r"`", text):
            err(f, f"pseudo-code literal `` {tok} `` belongs in the LLS")


def check_imports(f: Path, fm: str, files: list[Path] | None = None) -> None:
    m = re.search(r"^imports: (.*)$", fm, re.M)
    if not m:
        return
    names = set(spec_map(files))
    for item in m.group(1).split(","):
        bt = re.search(r"`([\w]+)`", item.strip())
        if bt and bt.group(1) not in names:
            err(f, f"imports backticked name '{bt.group(1)}' is not an existing spec")
        name = item.strip().split(" ", 1)[0].strip("`")
        if name == stem_of(f):
            err(f, f"imports: spec cannot import itself ('{name}')")


def check_tables(f: Path, text: str) -> None:
    table_lines = [l for l in text.splitlines() if l.startswith("|")]
    if not table_lines:
        return
    if f.name not in SANCTIONED_TABLES:
        err(f, f"table present in {len(table_lines)} lines; tables are restricted to rectangular matrices in {sorted(SANCTIONED_TABLES)}")
        return
    header_cells = len([c for c in table_lines[0].strip("|").split("|")])
    for line in table_lines[1:]:
        if "---" in line:
            continue
        cells = len([c for c in line.strip("|").split("|")])
        if cells != header_cells:
            err(f, f"non-rectangular table row: {line[:60]!r} ({cells} cells, header has {header_cells})")


def check_header(f: Path, text: str) -> None:
    first = text.splitlines()[0] if text.splitlines() else ""
    expected = "# " + stem_of(f)
    if first != expected:
        err(f, f"header {first!r} does not match filename stem {expected!r}")


# ---------------------------------------------------------------- main

def _spec_refs(fm: str) -> set[str]:
    """Specs a file's front matter references: terms (from X) owners,
    fulfills targets, and backticked imports."""
    refs: set[str] = set()
    for line in fm.splitlines():
        m = re.match(r"terms \(from ([^)]+)\):", line.strip())
        if m:
            refs.add(m.group(1).strip())
    m = re.search(r"fulfills:\s*([^\n]+)", fm)
    if m:
        for name in m.group(1).split(","):
            name = name.strip()
            if name:
                refs.add(name)
    m = re.search(r"imports:\s*(.*)", fm)
    if m:
        for name in re.findall(r"`([^`]+)`", m.group(1)):
            refs.add(name)
    return refs


def _stem_from_spec_path(path: str) -> str:
    """Derive a spec stem from a spec file path (dag_storage-high.md -> dag_storage)."""
    return Path(path).stem.removesuffix("-high")


def check_contract_subsections(f: Path, text: str, is_impl: bool) -> None:
    """Interface specs' ## Contract must contain its core sub-sections.

    The guide's Document Structure requires Contract sub-sections for client
    actions, guarantees, and assumptions; a missing sub-section (e.g. a
    trimmed `component guarantees`) is a structure error.
    """
    if is_impl:
        return
    contract = get_section(text, "Contract")
    if contract is None:
        return  # a missing Contract is reported by check_structure
    for sub in ("**The client may:**", "**The component guarantees:**", "**The component assumes:**"):
        if sub not in contract:
            err(f, f"## Contract is missing its '{sub}' sub-section")


def check_sync(f: Path, fm: str, deps: list[str]) -> None:
    """Verify the spec's text references are covered by its spec_deps.

    Every spec referenced in the file's front matter (terms-from owners,
    fulfills targets, imports) must be among the spec_deps closure passed via
    --deps (or be the file itself); otherwise the agent context could not read
    the referenced spec.
    """
    available = {stem_of(f)} | {_stem_from_spec_path(d) for d in deps}
    for name in sorted(_spec_refs(fm)):
        if name not in available:
            err(f, f"references spec '{name}' in its text but '{name}' is not among the node's spec_deps; add it to spec_deps (or to a spec dep's closure)")


def main(argv: list[str]) -> int:
    # --deps <spec file paths...>: the spec_deps closure (optional). When
    # provided, each linted file's text references must be covered by it.
    deps: list[str] = []
    rest: list[str] = []
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--deps":
            i += 1
            while i < len(argv) and argv[i] != "--":
                deps.append(argv[i])
                i += 1
        elif arg == "--":
            # Separator: everything after "--" is a target file.
            rest.extend(argv[i + 1 :])
            break
        else:
            rest.append(argv[i])
        i += 1

    files = [Path(p) for p in rest] or sorted(SPECS_DIR.glob("*-high.md"))
    # Reference corpus: the canonical specs. A single-file lint run (e.g. a
    # node's verify gate) resolves `terms (from X)` / `fulfills:` / import
    # references against the corpus, so the lone target file is validated
    # without spurious "no spec X" errors; corpus files themselves are not
    # linted or reported.
    reference_files = sorted(SPECS_DIR.glob("*-high.md"))
    all_files = sorted(set(files) | set(reference_files))
    for f in files:
        text = f.read_text(encoding="utf-8")
        check_header(f, text)
        fm, _ = split_front_matter(text)
        owned, terms_from, refined = check_front_matter(f, text)
        is_impl, body = check_structure(f, text, all_files)
        check_terms(f, text, owned, terms_from, refined, is_impl, all_files)
        check_language(f, text)
        check_dataflow(f, body)
        check_imports(f, fm, all_files)
        check_tables(f, text)
        check_contract_subsections(f, text, is_impl)
        if deps:
            check_sync(f, fm, deps)
        if not body.strip():
            err(f, "empty body")

    for w in warnings:
        print(f"W {w}")
    for e in errors:
        print(f"E {e}")
    print(f"\n{len(files)} files, {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
