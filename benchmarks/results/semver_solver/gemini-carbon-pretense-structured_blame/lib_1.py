# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_223217_gemini-carbon_semver_solver_pretense
# Timestamp: 2026-11-13T22:32:17.515811+00:00
# Benchmark Task: semver_solver
# Model: gemini-carbon (Tier 4)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 875,708
#   Cached Inbound Tokens:   8,052,935
#   Outbound Tokens:         168,044
#   Total Tokens:            9,096,687
#   Financial Cost ($USD):   $4.2371
#   Wall Clock Duration:     2104.20s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 3, pretense: 9, pretense_coverage: 3, pretense_qa: 4 (Total: 19)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Interface definitions and data types for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)
from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered."""

    raw_text: str


@dataclass
class InvalidRangeError(SemVerError):
    """Raised when a version range expression contains malformed syntax."""

    raw_range: str


@dataclass
class ResolutionConflictError(SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually."""

    conflicting_packages: Tuple[str, ...]
    explanation: str


@dataclass
class PackageNotFoundError(SemVerError):
    """Raised when a referenced package name does not exist in the repository."""

    package_name: str


class ComparatorOp(enum.Enum):
    """Relational comparison operator for version constraints."""

    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


@data_type
@dataclass(frozen=True)
class Version:
    """Immutable semantic version representation conforming to SemVer 2.0.0."""

    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        """Indicates whether this version contains pre-release identifiers."""
        return bool(self.prerelease)

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        core = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            core = f"{core}-" + ".".join(self.prerelease)
        if self.build:
            core = f"{core}+" + ".".join(self.build)
        return core

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        """Returns the raw range text representation."""
        return self.raw_text


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range."""

    name: str
    range_constraint: VersionRange


@data_type
@dataclass(frozen=True)
class PackageRelease:
    """Immutable publication record of a package at a specific semantic version."""

    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run."""

    selected_versions: Mapping[str, Version]
    derivation_steps: Tuple[str, ...]


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing, precedence comparison, and range matching."""

    @operation
    def parse_version(self, text: str) -> Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        ...

    @operation
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        ...


@poly_type
class PackageRepository(Protocol):
    """Maintains indexed package publications and release histories."""

    @operation
    def register_package(self, release: PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        ...

    @operation
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        ...

    @operation
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names."""
        ...


@poly_type
class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    @operation
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:51:45Z
# LAST_CHANGED: 2026-11-13T22:51:45Z
# CHANGE: Implement SemVer 2.0 interface protocols, exceptions, ComparatorOp, and immutable value records
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete implementation of SemVer 2.0 parsing, range matching, and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from functools import cmp_to_key
import re
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)
from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton
from . import semver_solver


_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z"
)

_NON_NEG_INT_PATTERN = re.compile(r"^(?:0|[1-9][0-9]*)\Z")
_WILDCARD_TOKENS = frozenset({"*", "x", "X"})
_OPERATORS_ORDERED: Tuple[str, ...] = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")
_OPERATOR_SET = frozenset(_OPERATORS_ORDERED)
_BASIC_COMPARATOR_OPS: Dict[str, semver_solver.ComparatorOp] = {
    "=": semver_solver.ComparatorOp.EQ,
    "==": semver_solver.ComparatorOp.EQ,
    "!=": semver_solver.ComparatorOp.NE,
    "<": semver_solver.ComparatorOp.LT,
    "<=": semver_solver.ComparatorOp.LE,
    ">": semver_solver.ComparatorOp.GT,
    ">=": semver_solver.ComparatorOp.GE,
}


class _TargetKind(enum.Enum):
    """Internal classification for parsed range bound targets."""

    EXACT = "exact"
    ANY = "any"
    MAJOR_WILDCARD = "major_wildcard"
    MINOR_WILDCARD = "minor_wildcard"


@dataclass(frozen=True)
class _TargetSpec:
    """Internal representation of a concrete version or wildcard bound."""

    kind: _TargetKind
    major: Optional[int] = None
    minor: Optional[int] = None
    version: Optional[semver_solver.Version] = None


@dataclass(frozen=True)
class _Comparator:
    """Internal atomic comparator testing a candidate version against a boundary."""

    op: semver_solver.ComparatorOp
    boundary: semver_solver.Version


@dataclass(frozen=True)
class _CompiledClause:
    """Internal compiled union branch holding DNF conjunctions and explicit prerelease targets."""

    dnf_conjunctions: Tuple[Tuple[_Comparator, ...], ...]
    prerelease_triples: FrozenSet[Tuple[int, int, int]]


def _is_numeric_identifier(segment: str) -> bool:
    """Checks whether a segment consists strictly of ASCII digits."""
    return bool(segment) and all("0" <= ch <= "9" for ch in segment)


def _parse_version_strict(text: str) -> semver_solver.Version:
    """Parses a strict SemVer 2.0.0 version string or raises InvalidVersionError."""
    match = _SEMVER_PATTERN.match(text)
    if match is None:
        raise semver_solver.InvalidVersionError(
            message=f"Invalid semantic version: '{text}'",
            raw_text=text,
        )
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    prerelease_raw = match.group("prerelease")
    build_raw = match.group("build")
    prerelease = tuple(prerelease_raw.split(".")) if prerelease_raw is not None else ()
    build = tuple(build_raw.split(".")) if build_raw is not None else ()
    return semver_solver.Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def _parse_target(token: str, raw_range: str) -> _TargetSpec:
    """Parses a range bound token as either a full SemVer 2.0.0 version or a wildcard expression."""
    # Reject pre-release or build suffixes attached to wildcard expressions; full versions parse directly.
    if "-" in token or "+" in token:
        try:
            parsed = _parse_version_strict(token)
        except semver_solver.InvalidVersionError as exc:
            raise semver_solver.InvalidRangeError(
                message=f"Invalid version '{token}' in range '{raw_range}'",
                raw_range=raw_range,
            ) from exc
        return _TargetSpec(kind=_TargetKind.EXACT, version=parsed)

    parts = token.split(".")
    if len(parts) > 3 or any(not p for p in parts):
        raise semver_solver.InvalidRangeError(
            message=f"Invalid version or wildcard '{token}' in range '{raw_range}'",
            raw_range=raw_range,
        )

    has_wildcard = any(p in _WILDCARD_TOKENS for p in parts)
    if not has_wildcard:
        # Bare partial versions without wildcards (1 or 2 segments) are prohibited.
        if len(parts) != 3:
            raise semver_solver.InvalidRangeError(
                message=f"Bare partial version '{token}' without wildcard is prohibited in '{raw_range}'",
                raw_range=raw_range,
            )
        try:
            parsed = _parse_version_strict(token)
        except semver_solver.InvalidVersionError as exc:
            raise semver_solver.InvalidRangeError(
                message=f"Invalid version '{token}' in range '{raw_range}'",
                raw_range=raw_range,
            ) from exc
        return _TargetSpec(kind=_TargetKind.EXACT, version=parsed)

    # Validate wildcard ordering: once a wildcard appears, all following segments must also be wildcards.
    seen_wildcard = False
    for part in parts:
        if part in _WILDCARD_TOKENS:
            seen_wildcard = True
        elif seen_wildcard or _NON_NEG_INT_PATTERN.match(part) is None:
            raise semver_solver.InvalidRangeError(
                message=f"Malformed wildcard target '{token}' in range '{raw_range}'",
                raw_range=raw_range,
            )

    if parts[0] in _WILDCARD_TOKENS:
        return _TargetSpec(kind=_TargetKind.ANY)

    major_val = int(parts[0])
    if parts[1] in _WILDCARD_TOKENS:
        return _TargetSpec(kind=_TargetKind.MAJOR_WILDCARD, major=major_val)

    minor_val = int(parts[1])
    return _TargetSpec(kind=_TargetKind.MINOR_WILDCARD, major=major_val, minor=minor_val)


def _expand_interval(
    op_str: str,
    lower: semver_solver.Version,
    upper: semver_solver.Version,
    caret_upper: semver_solver.Version,
) -> List[List[_Comparator]]:
    """Expands an operator over a half-open wildcard version interval [lower, upper)."""
    op_enum = semver_solver.ComparatorOp
    if op_str in ("=", "==", "~"):
        return [[_Comparator(op_enum.GE, lower), _Comparator(op_enum.LT, upper)]]
    if op_str == "^":
        return [[_Comparator(op_enum.GE, lower), _Comparator(op_enum.LT, caret_upper)]]
    if op_str == "!=":
        return [[_Comparator(op_enum.LT, lower)], [_Comparator(op_enum.GE, upper)]]
    if op_str == ">=":
        return [[_Comparator(op_enum.GE, lower)]]
    if op_str == "<=":
        return [[_Comparator(op_enum.LT, upper)]]
    if op_str == "<":
        return [[_Comparator(op_enum.LT, lower)]]
    # '>' on wildcard requires versions strictly beyond the wildcard interval.
    return [[_Comparator(op_enum.GE, upper)]]


def _expand_operator(
    op_str: str,
    target: _TargetSpec,
) -> Tuple[List[List[_Comparator]], Set[Tuple[int, int, int]]]:
    """Expands a prefix/relational operator and target into DNF comparator conjunctions."""
    op_enum = semver_solver.ComparatorOp
    ver = semver_solver.Version
    prerelease_triples: Set[Tuple[int, int, int]] = set()

    if target.kind == _TargetKind.EXACT:
        v = target.version
        assert v is not None
        if v.is_prerelease:
            prerelease_triples.add((v.major, v.minor, v.patch))

        if op_str in _BASIC_COMPARATOR_OPS:
            return [[_Comparator(_BASIC_COMPARATOR_OPS[op_str], v)]], prerelease_triples
        if op_str == "^":
            if v.major > 0:
                upper = ver(v.major + 1, 0, 0)
            elif v.minor > 0:
                upper = ver(0, v.minor + 1, 0)
            else:
                upper = ver(0, 0, v.patch + 1)
            return [[_Comparator(op_enum.GE, v), _Comparator(op_enum.LT, upper)]], prerelease_triples
        # Tilde (~) on full version bounds patch updates within the declared minor series.
        upper = ver(v.major, v.minor + 1, 0)
        return [[_Comparator(op_enum.GE, v), _Comparator(op_enum.LT, upper)]], prerelease_triples

    if target.kind == _TargetKind.ANY:
        if op_str in ("=", "==", ">=", "<=", "^", "~"):
            return [[]], prerelease_triples
        # Strict inequality or negation against universal wildcard has no satisfying versions.
        return [], prerelease_triples

    if target.kind == _TargetKind.MAJOR_WILDCARD:
        major = target.major
        assert major is not None
        lower = ver(major, 0, 0)
        upper = ver(major + 1, 0, 0)
        return _expand_interval(op_str, lower, upper, upper), prerelease_triples

    major = target.major
    minor = target.minor
    assert major is not None and minor is not None
    lower = ver(major, minor, 0)
    minor_upper = ver(major, minor + 1, 0)
    caret_upper = ver(major + 1, 0, 0) if major > 0 else minor_upper
    return _expand_interval(op_str, lower, minor_upper, caret_upper), prerelease_triples


def _expand_hyphen(
    bound1: _TargetSpec,
    bound2: _TargetSpec,
) -> Tuple[List[List[_Comparator]], Set[Tuple[int, int, int]]]:
    """Expands a hyphen range 'bound1 - bound2' into comparator inequalities."""
    op_enum = semver_solver.ComparatorOp
    ver = semver_solver.Version
    conjunction: List[_Comparator] = []
    prerelease_triples: Set[Tuple[int, int, int]] = set()

    if bound1.kind == _TargetKind.EXACT:
        assert bound1.version is not None
        if bound1.version.is_prerelease:
            prerelease_triples.add((bound1.version.major, bound1.version.minor, bound1.version.patch))
        conjunction.append(_Comparator(op_enum.GE, bound1.version))
    elif bound1.kind == _TargetKind.MAJOR_WILDCARD:
        assert bound1.major is not None
        conjunction.append(_Comparator(op_enum.GE, ver(bound1.major, 0, 0)))
    elif bound1.kind == _TargetKind.MINOR_WILDCARD:
        assert bound1.major is not None and bound1.minor is not None
        conjunction.append(_Comparator(op_enum.GE, ver(bound1.major, bound1.minor, 0)))

    if bound2.kind == _TargetKind.EXACT:
        assert bound2.version is not None
        if bound2.version.is_prerelease:
            prerelease_triples.add((bound2.version.major, bound2.version.minor, bound2.version.patch))
        conjunction.append(_Comparator(op_enum.LE, bound2.version))
    elif bound2.kind == _TargetKind.MAJOR_WILDCARD:
        assert bound2.major is not None
        conjunction.append(_Comparator(op_enum.LT, ver(bound2.major + 1, 0, 0)))
    elif bound2.kind == _TargetKind.MINOR_WILDCARD:
        assert bound2.major is not None and bound2.minor is not None
        conjunction.append(_Comparator(op_enum.LT, ver(bound2.major, bound2.minor + 1, 0)))

    return [conjunction], prerelease_triples


def _compile_clause(clause: str, raw_range: str) -> _CompiledClause:
    """Parses and compiles a single whitespace-delimited range clause into DNF."""
    tokens = clause.split()
    dnf: List[List[_Comparator]] = [[]]
    prerelease_triples: Set[Tuple[int, int, int]] = set()

    idx = 0
    num_tokens = len(tokens)
    while idx < num_tokens:
        tok = tokens[idx]
        if tok == "-":
            raise semver_solver.InvalidRangeError(
                message=f"Unexpected hyphen token in range '{raw_range}'",
                raw_range=raw_range,
            )

        # Check for hyphen expression 'bound1 - bound2'.
        if idx + 1 < num_tokens and tokens[idx + 1] == "-":
            if idx + 2 >= num_tokens:
                raise semver_solver.InvalidRangeError(
                    message=f"Incomplete hyphen range in '{raw_range}'",
                    raw_range=raw_range,
                )
            b1 = _parse_target(tok, raw_range)
            b2 = _parse_target(tokens[idx + 2], raw_range)
            item_dnf, item_pre = _expand_hyphen(b1, b2)
            idx += 3
        elif tok in _OPERATOR_SET:
            # Standalone operator separated by whitespace from its target.
            if idx + 1 >= num_tokens:
                raise semver_solver.InvalidRangeError(
                    message=f"Dangling operator '{tok}' in range '{raw_range}'",
                    raw_range=raw_range,
                )
            target = _parse_target(tokens[idx + 1], raw_range)
            item_dnf, item_pre = _expand_operator(tok, target)
            idx += 2
        else:
            matched_op: Optional[str] = None
            for candidate_op in _OPERATORS_ORDERED:
                if tok.startswith(candidate_op):
                    matched_op = candidate_op
                    break

            if matched_op is not None:
                target = _parse_target(tok[len(matched_op) :], raw_range)
                item_dnf, item_pre = _expand_operator(matched_op, target)
            else:
                target = _parse_target(tok, raw_range)
                item_dnf, item_pre = _expand_operator("=", target)
            idx += 1

        prerelease_triples.update(item_pre)
        dnf = [existing + branch for existing in dnf for branch in item_dnf]

    return _CompiledClause(
        dnf_conjunctions=tuple(tuple(conj) for conj in dnf),
        prerelease_triples=frozenset(prerelease_triples),
    )


def _parse_and_compile_range(text: str) -> Tuple[str, Tuple[_CompiledClause, ...]]:
    """Validates a raw range string, producing canonical trimmed text and compiled union clauses."""
    if "," in text:
        raise semver_solver.InvalidRangeError(
            message=f"Comma delimiters are prohibited in version range '{text}'",
            raw_range=text,
        )

    trimmed = text.strip()
    if not trimmed:
        raise semver_solver.InvalidRangeError(
            message="Version range cannot be empty or whitespace",
            raw_range=text,
        )

    raw_clauses = trimmed.split("||")
    clauses = [c.strip() for c in raw_clauses]
    if any(not c for c in clauses):
        raise semver_solver.InvalidRangeError(
            message=f"Empty union clause in version range '{text}'",
            raw_range=text,
        )

    compiled = tuple(_compile_clause(c, text) for c in clauses)
    canonical_text = " || ".join(clauses)
    return canonical_text, compiled


@singleton
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = "system"

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        return _parse_version_strict(text)

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        # Compare numeric major, minor, and patch components sequentially.
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1

        # Normal releases take higher precedence over pre-release versions with matching core numbers.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease and v2.prerelease:
            return 1
        if v1.prerelease and not v2.prerelease:
            return -1

        # Compare dot-separated pre-release identifiers position by position.
        for seg1, seg2 in zip(v1.prerelease, v2.prerelease):
            num1 = _is_numeric_identifier(seg1)
            num2 = _is_numeric_identifier(seg2)
            if num1 and num2:
                int1 = int(seg1)
                int2 = int(seg2)
                if int1 != int2:
                    return -1 if int1 < int2 else 1
            elif num1 and not num2:
                return -1
            elif not num1 and num2:
                return 1
            elif seg1 != seg2:
                return -1 if seg1 < seg2 else 1

        # Longer pre-release sequences rank higher when all shared prefix identifiers match.
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

        # Build metadata is ignored for version precedence.
        return 0

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        canonical_text, _ = _parse_and_compile_range(text)
        return semver_solver.VersionRange(raw_text=canonical_text)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        _, compiled = _parse_and_compile_range(range_constraint.raw_text)
        version_triple = (version.major, version.minor, version.patch)

        for union_clause in compiled:
            # Filter pre-release versions unless include_prerelease is True or the clause targets this core triple.
            if (
                version.is_prerelease
                and not include_prerelease
                and version_triple not in union_clause.prerelease_triples
            ):
                continue

            for conjunction in union_clause.dnf_conjunctions:
                if all(self._matches_comparator(version, comp) for comp in conjunction):
                    return True

        return False

    def _matches_comparator(
        self,
        version: semver_solver.Version,
        comparator: _Comparator,
    ) -> bool:
        """Evaluates a single atomic comparator using SemVer precedence rules."""
        cmp_val = self.compare_precedence(version, comparator.boundary)
        op = comparator.op
        if op is semver_solver.ComparatorOp.EQ:
            return cmp_val == 0
        if op is semver_solver.ComparatorOp.NE:
            return cmp_val != 0
        if op is semver_solver.ComparatorOp.LT:
            return cmp_val < 0
        if op is semver_solver.ComparatorOp.LE:
            return cmp_val <= 0
        if op is semver_solver.ComparatorOp.GT:
            return cmp_val > 0
        return cmp_val >= 0


@singleton
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = "system"

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(
            key=cmp_to_key(lambda r1, r2: engine.compare_precedence(r1.version, r2.version)),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' does not exist in repository",
                package_name=name,
            )
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Returns the set of all registered package names."""
        return set(self._packages.keys())


@singleton
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = "system"

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        accumulated_constraints: Dict[str, List[Tuple[Optional[str], semver_solver.VersionRange]]] = {}
        for dep in root_dependencies:
            accumulated_constraints.setdefault(dep.name, []).append((None, dep.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            unassigned = [pkg for pkg in accumulated_constraints if pkg not in assignment]
            if not unassigned:
                return True

            # Evaluate candidate releases per unassigned package for Minimum Remaining Values ordering.
            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            missing_packages: Set[str] = set()
            for pkg in unassigned:
                try:
                    available = repository.get_releases(pkg)
                except semver_solver.PackageNotFoundError:
                    available = []
                    missing_packages.add(pkg)

                viable = [
                    rel
                    for rel in available
                    if all(
                        engine.satisfies(rel.version, rng, False)
                        for _, rng in accumulated_constraints[pkg]
                    )
                ]
                candidates_map[pkg] = viable

            selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
            candidates = candidates_map[selected_pkg]

            if not candidates:
                conflicting_packages.add(selected_pkg)
                requester_labels: List[str] = []
                for src, rng in accumulated_constraints[selected_pkg]:
                    if src is not None:
                        conflicting_packages.add(src)
                        requester_labels.append(f"{src} ({rng.raw_text})")
                    else:
                        requester_labels.append(f"root ({rng.raw_text})")

                if selected_pkg in missing_packages:
                    conflict_trail.append(
                        f"Package '{selected_pkg}' is not registered in repository "
                        f"(required by {', '.join(requester_labels)})"
                    )
                else:
                    conflict_trail.append(
                        f"No compatible releases for '{selected_pkg}' satisfying "
                        f"{', '.join(requester_labels)}"
                    )
                return False

            # Explore viable candidates in descending version precedence order.
            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

                conflict_detected = False
                newly_added_pkgs: List[str] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        assigned_rel = assignment[dep.name]
                        if not engine.satisfies(assigned_rel.version, dep.range_constraint, False):
                            conflict_detected = True
                            conflicting_packages.add(selected_pkg)
                            conflicting_packages.add(dep.name)
                            conflict_trail.append(
                                f"Conflict: '{selected_pkg}' {candidate.version} requires "
                                f"'{dep.name}' {dep.range_constraint.raw_text}, "
                                f"but '{dep.name}' is assigned {assigned_rel.version}"
                            )
                            break
                    else:
                        accumulated_constraints.setdefault(dep.name, []).append(
                            (selected_pkg, dep.range_constraint)
                        )
                        newly_added_pkgs.append(dep.name)

                if not conflict_detected and backtrack():
                    return True

                # Undo accumulated constraints and partial assignment before advancing to next candidate.
                for pkg_name in reversed(newly_added_pkgs):
                    accumulated_constraints[pkg_name].pop()
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        if backtrack():
            selected_versions = {pkg: rel.version for pkg, rel in assignment.items()}
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        explanation = "\n".join(conflict_trail)
        sorted_conflicts = tuple(sorted(conflicting_packages))
        raise semver_solver.ResolutionConflictError(
            message=f"Unable to resolve dependencies due to conflicts in: {', '.join(sorted_conflicts)}",
            conflicting_packages=sorted_conflicts,
            explanation=explanation,
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T23:07:18Z
# LAST_CHANGED: 2026-11-13T22:52:06Z
# CHANGE: Implement VersionEngine, PackageRepository, and MRV backtracking DependencySolver
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T23:07:18Z
# PRETENSE_QA_AUDIT: 2026-11-13T23:06:37Z
# --- END AUTOFAB METADATA ---
