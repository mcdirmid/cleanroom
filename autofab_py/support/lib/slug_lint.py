"""slug_lint.py — Contract slug validator and anti-mechanistic auditor protection linter.

Verifies:
1. Low-level specification slugs in low/*.pyi adhere to canonical identifier grammar:
   ^[slug:[a-z0-9_.]+(#[a-z0-9_]+)?(:[a-z0-9_]+)?]$
2. Slugs declared in low/*.pyi are unique within each specification file.
3. Slugs belong strictly to the Specification Plane and Blame Channel: code artifacts
   (lib/, tests/, pretense/) are strictly prohibited from citing real, declared specification
   contract IDs in comments or docstrings. This prevents downstream auditors (QA, Coverage,
   Pretense QA) from mechanistically taking the file's word for what contract is implemented.
   Generic boilerplate syntax and hallucinated/non-existent contract IDs are ignored.
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

# Token matching any slug tag (including malformed tags with spaces or invalid chars)
SLUG_TAG_PATTERN = re.compile(r"\[slug:[^\]]+\]")

# Valid canonical slug syntax
CANONICAL_SLUG_PATTERN = re.compile(
    r"^\[slug:[a-z0-9_.]+(?:#[a-z0-9_]+)?(?::[a-z0-9_]+)?\]$"
)

# Extracts the inner slug ID from a canonical tag
CANONICAL_SLUG_ID_PATTERN = re.compile(
    r"\[slug:([a-z0-9_.]+(?:#[a-z0-9_]+)?(?::[a-z0-9_]+)?)\]"
)


def extract_spec_slugs(content: str) -> List[str]:
    """Extracts all valid specification slug tags from content."""
    slugs: List[str] = []
    for line in content.splitlines():
        for match in SLUG_TAG_PATTERN.findall(line):
            if CANONICAL_SLUG_PATTERN.match(match):
                slugs.append(match)
    return slugs


def extract_spec_slug_ids(content: str) -> Set[str]:
    """Extracts raw contract slug IDs (e.g. 'semver.compare_precedence.tri_state') from spec content."""
    slug_ids: Set[str] = set()
    for match in CANONICAL_SLUG_ID_PATTERN.findall(content):
        slug_ids.add(match)
        if "#" in match:
            slug_ids.add(match.split("#")[0])
        if ":" in match:
            slug_ids.add(match.split(":")[0])
    return slug_ids


def find_companion_spec_files(file_path: str) -> List[Path]:
    """Finds companion low/*.pyi specification files for a given code file."""
    p = Path(file_path).resolve()
    spec_files: List[Path] = []

    # 1. Check parent.parent / "low" (e.g. parts/foo/lib/bar.py -> parts/foo/low/*.pyi)
    if p.parent.parent.is_dir():
        low_dir = p.parent.parent / "low"
        if low_dir.is_dir():
            spec_files.extend(sorted(low_dir.glob("*.pyi")))

    # 2. Check parent / "low"
    if not spec_files and p.parent.is_dir():
        low_dir = p.parent / "low"
        if low_dir.is_dir():
            spec_files.extend(sorted(low_dir.glob("*.pyi")))

    # 3. Check upward ancestors for low/*.pyi
    if not spec_files:
        curr = p.parent
        while curr != curr.parent:
            low_cand = curr / "low"
            if low_cand.is_dir():
                found = sorted(low_cand.glob("*.pyi"))
                if found:
                    spec_files.extend(found)
                    break
            curr = curr.parent

    return spec_files


def validate_spec_slugs(content: str, fname: str) -> List[str]:
    """Validates syntax and local uniqueness of specification slugs declared in low/*.pyi."""
    errors: List[str] = []
    seen_slugs: dict[str, int] = {}

    for lineno, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        slug_matches = SLUG_TAG_PATTERN.findall(stripped)
        for slug_tag in slug_matches:
            if not CANONICAL_SLUG_PATTERN.match(slug_tag):
                errors.append(
                    f"{fname}:{lineno}: error: malformed specification slug '{slug_tag}'. "
                    f"Must match '^[slug:[a-z0-9_.]+(#[a-z0-9_]+)?(:[a-z0-9_]+)?]$'"
                )
                continue

            if slug_tag in seen_slugs:
                first_line = seen_slugs[slug_tag]
                errors.append(
                    f"{fname}:{lineno}: error: duplicate specification slug '{slug_tag}' "
                    f"(first declared on line {first_line})"
                )
            else:
                seen_slugs[slug_tag] = lineno

    return errors


def mask_inband_metadata(content: str) -> str:
    """Masks in-band metadata block lines with blank lines to preserve line numbers."""
    lines = content.splitlines(keepends=True)
    out: List[str] = []
    in_metadata = False
    for line in lines:
        stripped = line.strip()
        if stripped in (
            "# --- CLEANROOM METADATA ---",
            "# --- AUTOFAB METADATA ---",
            "<!-- CLEANROOM METADATA",
            "<!-- AUTOFAB METADATA",
        ):
            in_metadata = True
            out.append("\n")
            continue
        if in_metadata:
            if (
                stripped
                in (
                    "# --- END CLEANROOM METADATA ---",
                    "# --- END AUTOFAB METADATA ---",
                )
                or stripped == "-->"
            ):
                in_metadata = False
            out.append("\n")
            continue
        out.append(line)
    return "".join(out)


def check_no_slug_references(
    content: str,
    fname: str,
    declared_contract_ids: Optional[Set[str]] = None,
) -> List[str]:
    """Ensures code artifacts (lib/, tests/, pretense/) do not reference real specification contracts.

    Purpose: Anti-Mechanistic Auditor Protection. Prevents downstream auditors (QA, Coverage,
    Pretense QA) from mechanistically taking the author's word for what <contract> is implemented.
    Boilerplate syntax and hallucinated/non-existent contract IDs are ignored; only real, existing
    contract IDs declared in the unit's low/*.pyi specification are dangerous and strictly prohibited.
    """
    content = mask_inband_metadata(content)
    errors: List[str] = []

    if declared_contract_ids is None:
        spec_files = find_companion_spec_files(fname)
        if not spec_files:
            return errors
        declared_contract_ids = set()
        for sf in spec_files:
            try:
                declared_contract_ids.update(
                    extract_spec_slug_ids(sf.read_text(encoding="utf-8"))
                )
            except Exception:
                continue

    if not declared_contract_ids:
        return errors

    patterns = [
        (cid, re.compile(rf"\b{re.escape(cid)}\b", re.IGNORECASE))
        for cid in declared_contract_ids
    ]

    try:
        tokens = tokenize.tokenize(io.BytesIO(content.encode("utf-8")).readline)
        for tok in tokens:
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                for cid, pat in patterns:
                    if pat.search(tok.string):
                        errors.append(
                            f"{fname}:{tok.start[0]}: error: reference to declared specification contract '{cid}' "
                            f"in code comment/docstring is prohibited. Auditors must evaluate contracts through "
                            f"empirical execution, not self-attested in-code contract claims."
                        )
                        break
    except (tokenize.TokenError, IndentationError):
        for lineno, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or '"""' in stripped or "'''" in stripped:
                for cid, pat in patterns:
                    if pat.search(line):
                        errors.append(
                            f"{fname}:{lineno}: error: reference to declared specification contract '{cid}' "
                            f"in code comment/docstring is prohibited. Auditors must evaluate contracts through "
                            f"empirical execution, not self-attested in-code contract claims."
                        )
                        break

    return errors


def lint_file(file_path: str) -> List[str]:
    """Lints a file according to its plane (spec vs code artifact)."""
    p = Path(file_path)
    if not p.is_file():
        return [f"{file_path}: error: file not found"]

    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{file_path}: error reading file: {e}"]

    norm = file_path.replace("\\", "/")
    if norm.endswith(".pyi") or "/low/" in norm:
        return validate_spec_slugs(content, file_path)
    elif norm.endswith(".py"):
        return check_no_slug_references(content, file_path)
    return []


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    files = [a for a in argv if not a.startswith("-")]
    if not files:
        print("Usage: python -m slug_lint [files...]", file=sys.stderr)
        return 0

    all_errors: List[str] = []
    for f in files:
        errs = lint_file(f)
        all_errors.extend(errs)

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        print(
            f"[FAIL] {len(all_errors)} slug lint errors found across {len(files)} files.",
            file=sys.stderr,
        )
        return 1

    print(f"[OK] {len(files)} files passed slug lint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
