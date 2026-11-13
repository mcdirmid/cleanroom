"""structured_blame.py — Structured blame parsing, validation, and zero-entropy embargo."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

try:
    from support.lib import experiments
except ImportError:
    try:
        from autofab.support.lib import experiments  # type: ignore
    except ImportError:
        import experiments  # type: ignore


# Specification slug patterns
SLUG_TAG_PATTERN = re.compile(r"\[slug:[^\]]+\]")
CANONICAL_SLUG_PATTERN = re.compile(
    r"^\[slug:[a-z0-9_.]+(?:#[a-z0-9_]+)?(?::[a-z0-9_]+)?\]$"
)


def extract_spec_slugs(content: str) -> List[str]:
    """Extracts all valid specification slug tags from content."""
    slugs: List[str] = []
    for line in content.splitlines():
        for match in SLUG_TAG_PATTERN.findall(line):
            if CANONICAL_SLUG_PATTERN.match(match):
                slugs.append(match)
    return slugs


# Canonical structured blame BNF elements:
# <BlameCritique>  ::= <SlugSection> " " <ViolationSection> " " <FacetSection> [ " " <WitnessSection> ]
# <SlugSection>    ::= "[slug:" <Identifier> ("." <Identifier>)* [ "#" <Identifier> ] "]"
# <ViolationSection>::= "[viol:" <AuditorPrefix> "." <ViolationName> "]"
# <FacetSection>   ::= "Facet: " <NounPhrase>
# <WitnessSection> ::= "Witness: " <LiteralKeyValueList>

# Auditor taxonomy prefixes
VALID_VIOLATION_PREFIXES: Set[str] = {
    "post",
    "pre",
    "inv",
    "test",
    "cov",
    "spec",
    "plan",
    "pret_qa",
    "pret_cov",
}

VIOLATION_TAG_PATTERN = re.compile(
    r"^\[viol:(post|pre|inv|test|cov|spec|plan|pret_qa|pret_cov)\.[a-z0-9_]+\]$"
)

# Forbidden action tokens in facet noun phrases (imperative verbs & modals)
FORBIDDEN_ACTION_TOKENS: Set[str] = {
    "fix",
    "change",
    "update",
    "delete",
    "remove",
    "add",
    "assert",
    "use",
    "make",
    "ensure",
    "replace",
    "modify",
    "check",
    "should",
    "must",
    "cannot",
    "need",
    "refactor",
    "do",
    "don't",
    "try",
    "please",
    "block",
    "blocks",
    "blocking",
}

# Regex to detect test symbol leaks in blame targeting library code
TEST_LEAK_PATTERNS: Sequence[re.Pattern[str]] = [
    re.compile(r"\btest_[a-zA-Z0-9_]+\b"),
    re.compile(r"\bTestCase\b"),
    re.compile(r"\bassert\s+"),
    re.compile(r"\bassert_"),
    re.compile(r"\bpytest\b"),
    re.compile(r"\bfixture\b"),
    re.compile(r"[a-zA-Z0-9_]+_test\.py:\d+"),
    re.compile(r"[a-zA-Z0-9_]+_pretense\.py:\d+"),
]

# Regex for structured blame parsing from single string (supports both [viol:...] and Violation: <phrase>, optional Lines:, and optional Witness:)
_RE_STRUCTURED_BLAME = re.compile(
    r"^(\[slug:[^\]]+\])\s+(?:(\[viol:[^\]]+\])|Violation:\s+([^\n\r]+?))\s+Facet:\s+([^\n\r]+?)(?:\s+(?:\[lines:([^\]]+)\]|Lines:\s*([0-9]+(?:-[0-9]+)?)))?(?:\s+(?:\[witness:([^\]]+)\]|Witness:\s+([^\n\r]+)))?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StructuredBlame:
    """Represents a validated, zero-entropy structured blame critique."""

    slug: str
    violation: str
    facet: str
    witness: Optional[str] = None
    lines: Optional[str] = None

    def to_critique_string(self) -> str:
        """Formats into canonical critique string representation."""
        viol_str = self.violation
        if not viol_str.startswith("[viol:") and not viol_str.lower().startswith(
            "violation:"
        ):
            viol_str = f"Violation: {viol_str}"
        base = f"{self.slug} {viol_str} Facet: {self.facet}"
        if self.lines:
            base += f" Lines: {self.lines}"
        if self.witness:
            base += f" Witness: {self.witness}"
        return base


def is_structured_blame_active() -> bool:
    """Returns True if the structured_blame experiment is active."""
    return experiments.is_experiment_active("structured_blame")


def parse_structured_blame(
    text: str,
    slug: Optional[str] = None,
    viol: Optional[str] = None,
    facet: Optional[str] = None,
    witness: Optional[str] = None,
    lines: Optional[str] = None,
) -> Tuple[Optional[StructuredBlame], List[str]]:
    """Parses a structured blame critique from either explicit CLI flags or a single formatted string.

    Returns:
        (StructuredBlame, []) on success, or (None, errors) on failure.
    """
    errors: List[str] = []

    # Priority 1: Explicit CLI parameters
    if slug or viol or facet:
        if not slug:
            errors.append("Missing required --slug option.")
        if not viol:
            errors.append("Missing required --viol option.")
        if not facet:
            errors.append("Missing required --facet option.")
        if errors:
            return None, errors

        norm_slug = slug.strip() if slug else ""
        if not norm_slug.startswith("[slug:"):
            norm_slug = f"[slug:{norm_slug.strip('[]')}]"

        norm_viol = viol.strip() if viol else ""
        if norm_viol.startswith("[viol:") or norm_viol.lower().startswith("violation:"):
            pass
        elif "." in norm_viol and any(
            norm_viol.startswith(p + ".") for p in VALID_VIOLATION_PREFIXES
        ):
            norm_viol = f"[viol:{norm_viol}]"
        elif not norm_viol.startswith("["):
            norm_viol = f"Violation: {norm_viol}"

        norm_facet = facet.strip() if facet else ""
        norm_witness = witness.strip() if witness else None
        norm_lines = lines.strip() if lines else None
        if norm_lines:
            if norm_lines.startswith("[lines:") and norm_lines.endswith("]"):
                norm_lines = norm_lines[7:-1].strip()
            elif norm_lines.lower().startswith("lines:"):
                norm_lines = norm_lines[6:].strip()

        return (
            StructuredBlame(
                slug=norm_slug,
                violation=norm_viol,
                facet=norm_facet,
                witness=norm_witness,
                lines=norm_lines,
            ),
            [],
        )

    # Priority 2: Parse from single formatted string
    clean_text = " ".join(text.strip().splitlines())
    if "--slug" in clean_text or "--spec-slug" in clean_text:
        try:
            import argparse
            import shlex

            p = argparse.ArgumentParser(add_help=False)
            p.add_argument("--slug", "--spec-slug", dest="slug")
            p.add_argument("--viol", "--violation", dest="viol")
            p.add_argument("--facet", dest="facet")
            p.add_argument("--witness", dest="witness")
            p.add_argument("--lines", dest="lines")
            tokens = shlex.split(clean_text)
            parsed_args, _ = p.parse_known_args(tokens)
            if parsed_args.slug and (parsed_args.viol or parsed_args.facet):
                return parse_structured_blame(
                    text="",
                    slug=parsed_args.slug,
                    viol=parsed_args.viol,
                    facet=parsed_args.facet,
                    witness=parsed_args.witness,
                    lines=parsed_args.lines,
                )
        except Exception:
            pass

    m = _RE_STRUCTURED_BLAME.match(clean_text)
    if not m:
        errors.append(
            "Critique does not conform to the structured blame format: "
            "'[slug:<spec.slug>] [viol:<prefix>.<violation>] Facet: <noun phrase> [Lines: <range>] [Witness: <values>]' or "
            "'[slug:<spec.slug>] Violation: <noun phrase> Facet: <noun phrase> [Lines: <range>] [Witness: <values>]'. "
            "Example: '[slug:semver.range.whitespace] Violation: postcondition divergence Facet: embedded operator whitespace Lines: 84 Witness: input='>= 1.0.0''"
        )
        return None, errors

    parsed_slug = m.group(1).strip()
    parsed_viol = (
        m.group(2).strip() if m.group(2) else f"Violation: {m.group(3).strip()}"
    )
    parsed_facet = m.group(4).strip()
    parsed_lines = (m.group(5) or m.group(6) or "").strip() or None
    parsed_witness = (m.group(7) or m.group(8) or "").strip() or None

    return (
        StructuredBlame(
            slug=parsed_slug,
            violation=parsed_viol,
            facet=parsed_facet,
            lines=parsed_lines,
            witness=parsed_witness,
        ),
        [],
    )


def validate_structured_blame(
    blame: StructuredBlame,
    culprit_file: str,
    repo_root: Optional[str] = None,
    workspace_root: Optional[str] = None,
    caller_role: Optional[str] = None,
) -> List[str]:
    """Validates a StructuredBlame instance against canonical rules, taxonomy, facets, and specifications."""
    errors: List[str] = []

    # 1. Validate specification slug syntax
    if not CANONICAL_SLUG_PATTERN.match(blame.slug):
        errors.append(
            f"Malformed specification slug '{blame.slug}'. "
            f"Must match '^[slug:[a-z0-9_.]+(#[a-z0-9_]+)?(:[a-z0-9_]+)?]$'"
        )

    # 2. Validate violation code taxonomy or generalized noun phrase
    if blame.violation.startswith("[viol:"):
        if not VIOLATION_TAG_PATTERN.match(blame.violation):
            errors.append(
                f"Malformed violation code '{blame.violation}'. "
                f"Prefix must be one of {sorted(VALID_VIOLATION_PREFIXES)} and match '^[viol:<prefix>.<name>]$'"
            )
    else:
        viol_text = blame.violation
        if viol_text.lower().startswith("violation:"):
            viol_text = viol_text[len("violation:") :].strip()
        viol_words = viol_text.split()
        if len(viol_words) > 8:
            errors.append(
                f"Violation exceeds maximum word count of 8 words ({len(viol_words)} words provided): '{blame.violation}'"
            )
        if len(viol_text) > 120:
            errors.append(
                f"Violation exceeds maximum length of 120 characters ({len(viol_text)} chars provided): '{blame.violation}'"
            )
        for word in re.findall(r"[a-zA-Z]+", viol_text):
            if word.lower() in FORBIDDEN_ACTION_TOKENS:
                forbidden_list = ", ".join(sorted(FORBIDDEN_ACTION_TOKENS))
                errors.append(
                    f"Violation contains forbidden imperative action token '{word}'. "
                    "Violations must be descriptive noun phrases of defect categories (e.g. 'precondition error omission'), "
                    f"not imperative instructions. Forbidden tokens: {forbidden_list}."
                )
                break

    # 3. Validate facet constraints (Noun phrase grammar)
    facet_words = blame.facet.split()
    if len(facet_words) > 8:
        errors.append(
            f"Facet exceeds maximum word count of 8 words ({len(facet_words)} words provided): '{blame.facet}'"
        )
    if len(blame.facet) > 120:
        errors.append(
            f"Facet exceeds maximum length of 120 characters ({len(blame.facet)} chars provided): '{blame.facet}'"
        )

    for word in re.findall(r"[a-zA-Z]+", blame.facet):
        if word.lower() in FORBIDDEN_ACTION_TOKENS:
            forbidden_list = ", ".join(sorted(FORBIDDEN_ACTION_TOKENS))
            errors.append(
                f"Facet contains forbidden imperative action token '{word}'. "
                "Facets must be descriptive noun phrases of domain entities/states (e.g. 'embedded operator whitespace'), "
                f"not imperative instructions. Forbidden tokens: {forbidden_list}."
            )
            break

    # 4. Validate lines component (strictly within culprit file)
    if blame.lines:
        m_lines = re.match(r"^(\d+)(?:-(\d+))?$", blame.lines.strip())
        if not m_lines:
            errors.append(
                f"Malformed lines component '{blame.lines}'. Must be a single line number (e.g. '42') "
                f"or a line range (e.g. '42-50')."
            )
        else:
            start_l = int(m_lines.group(1))
            end_l = int(m_lines.group(2)) if m_lines.group(2) else start_l
            if start_l <= 0:
                errors.append(
                    f"Line numbers must be positive integers (got {start_l})."
                )
            elif end_l < start_l:
                errors.append(
                    f"Invalid line range '{blame.lines}': end line ({end_l}) cannot precede start line ({start_l})."
                )
            else:
                culprit_lines = _count_file_lines(
                    culprit_file, repo_root, workspace_root
                )
                if culprit_lines is not None and (
                    start_l > culprit_lines or end_l > culprit_lines
                ):
                    errors.append(
                        f"Line range '{blame.lines}' exceeds length of target file '{culprit_file}' "
                        f"({culprit_lines} lines)."
                    )

    # 5. Validate witness constraints (literal key-value pairs)
    if blame.witness:
        clean_witness = blame.witness.strip()
        if len(clean_witness) > 250:
            errors.append(
                f"Witness exceeds maximum length of 250 characters ({len(clean_witness)} chars provided)."
            )
        if re.search(r"\bline[s]?\s*=\s*\d+|:\d+\b", clean_witness, re.IGNORECASE):
            errors.append(
                "Witness cannot contain source line numbers. Source line numbers must be placed "
                "in the dedicated 'Lines:' component (e.g. 'Lines: 42-50')."
            )
        if "=" not in clean_witness:
            errors.append(
                f"Witness must contain literal key-value pairs (e.g. 'exp=..., obs=...'): '{blame.witness}'"
            )

    # 6. Zero-entropy foreign file reference and symbol embargo check
    norm_culprit = culprit_file.replace("\\", "/").lower()
    culprit_name = Path(culprit_file).name.lower()
    full_critique = blame.to_critique_string()

    # Reject inline file:line citations
    if re.search(r"[a-zA-Z0-9_]+\.py:\d+", full_critique):
        errors.append(
            "Source line references must be placed in the dedicated 'Lines:' component (e.g. 'Lines: 42-50'), "
            "not as inline file path citations."
        )

    # Reject any foreign file references
    for m in re.finditer(
        r"\b([a-zA-Z0-9_]+\.(?:py|pyi|md|toml))\b", full_critique, re.IGNORECASE
    ):
        ref_file = m.group(1).lower()
        if ref_file != culprit_name:
            errors.append(
                f"Information leakage: critique references foreign file '{m.group(1)}'. "
                f"Critiques must refer strictly to the file being blamed ('{Path(culprit_file).name}')."
            )
            break

    is_lib_target = (
        "/lib/" in norm_culprit
        or norm_culprit.endswith(".py")
        and not norm_culprit.endswith(("_test.py", "_pretense.py"))
    )

    if is_lib_target:
        for pat in TEST_LEAK_PATTERNS:
            m = pat.search(full_critique)
            if m:
                errors.append(
                    f"Information leakage detected in blame targeting implementation: "
                    f"found test symbol or assertion '{m.group(0)}'. "
                    "Implementation critiques must reference contract specifications, not test mechanics."
                )
                break

    # 7. Check slug existence in low-level specifications (if discoverable)
    resolved_slugs = _discover_unit_slugs(culprit_file, repo_root, workspace_root)
    if resolved_slugs and blame.slug not in resolved_slugs:
        # Check base slug ignoring facet anchor
        base_slug = blame.slug.split("#")[0].rstrip("]") + "]"
        is_harness_wiring = (
            base_slug.endswith(".harness.wiring]")
            or base_slug == "[slug:harness.wiring]"
        )
        if not is_harness_wiring and base_slug not in resolved_slugs:
            errors.append(
                f"Specification slug '{blame.slug}' not declared in low-level specifications for '{culprit_file}'. "
                f"Declared specification slugs: {sorted(resolved_slugs)[:5]} (total {len(resolved_slugs)})"
            )

    return errors


def _count_file_lines(
    culprit_file: str,
    repo_root: Optional[str] = None,
    workspace_root: Optional[str] = None,
) -> Optional[int]:
    """Counts total lines in the culprit file if readable."""
    roots: List[Path] = []
    if workspace_root:
        roots.append(Path(workspace_root))
    if repo_root:
        roots.append(Path(repo_root))
    roots.append(Path.cwd())

    norm_culprit = Path(culprit_file)
    for r in roots:
        full_p = (
            (r / norm_culprit).resolve()
            if not norm_culprit.is_absolute()
            else norm_culprit
        )
        if full_p.is_file():
            try:
                return len(full_p.read_text(encoding="utf-8").splitlines())
            except OSError:
                pass
        parts = norm_culprit.parts
        for i in range(len(parts)):
            cand = (r / Path(*parts[i:])).resolve()
            if cand.is_file():
                try:
                    return len(cand.read_text(encoding="utf-8").splitlines())
                except OSError:
                    pass
    return None


def _discover_unit_slugs(
    culprit_file: str,
    repo_root: Optional[str] = None,
    workspace_root: Optional[str] = None,
) -> Set[str]:
    """Discovers all specification slugs declared in the unit's low/*.pyi files."""
    roots: List[Path] = []
    if workspace_root:
        roots.append(Path(workspace_root))
    if repo_root:
        roots.append(Path(repo_root))
    roots.append(Path.cwd())

    # Locate potential unit directory
    norm_culprit = Path(culprit_file)
    cand_low_dirs: List[Path] = []

    for r in roots:
        # Check if culprit is relative to root
        full_p = (
            (r / norm_culprit).resolve()
            if not norm_culprit.is_absolute()
            else norm_culprit
        )
        # Traverse upward to find parts/*/low or low/
        curr = full_p.parent
        for _ in range(4):
            if (curr / "low").is_dir():
                cand_low_dirs.append(curr / "low")
                break
            if curr.name == "low" and curr.is_dir():
                cand_low_dirs.append(curr)
                break
            if curr.parent == curr:
                break
            curr = curr.parent

        # Also search candidate benchmark / parts dirs
        for bench_p in r.glob("**/low/*.pyi"):
            if bench_p.parent not in cand_low_dirs:
                # If part matches culprit path parts
                if any(
                    part in str(bench_p)
                    for part in norm_culprit.parts
                    if part not in ("lib", "tests", "pretense")
                ):
                    cand_low_dirs.append(bench_p.parent)

    declared_slugs: Set[str] = set()
    for l_dir in cand_low_dirs:
        if not l_dir.is_dir():
            continue
        for pyi_file in l_dir.glob("*.pyi"):
            try:
                content = pyi_file.read_text(encoding="utf-8")
                for slug in extract_spec_slugs(content):
                    declared_slugs.add(slug)
            except OSError:
                pass

    return declared_slugs
