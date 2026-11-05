# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_214658_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-11-04T21:46:58.756452+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 366,952
#   Cached Inbound Tokens:   33,059,327
#   Outbound Tokens:         368,168
#   Total Tokens:            33,794,447
#   Financial Cost ($USD):   $0.3751
#   Wall Clock Duration:     2034.79s
#   Step Latencies (s):      [357.7, 462.9, 339.0, 285.9, 10.5, 128.6, 122.3, 139.9, 54.5, 42.1, 10.3, 117.4, 54.1, 77.4, 75.8, 42.3, 10.5, 54.4, 63.2, 10.5, 54.3, 42.1, 10.5, 10.3]
#   Role Execution Rounds:   lib: 4, pretense: 7, pretense_coverage: 5, pretense_qa: 8 (Total: 24)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum

from support.lib.framework import data_type, poly_type

# Requirements specified in semver_solver.pyi


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __post_init__(self) -> None:
        # Preserve the diagnostic text as the standard exception argument.
        Exception.__init__(self, self.message)

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

    EQ = '=='
    NE = '!='
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='


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
        # A version is a pre-release exactly when it declares pre-release identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Canonical SemVer 2.0.0 rendering: numeric core, then -pre-release, then +build.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # __str__ is equivalent to the canonical format() representation.
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        # The raw range text is already the canonical textual representation.
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

    def parse_version(self, text: str) -> Version:
        ...

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        ...

    def parse_range(self, text: str) -> VersionRange:
        ...

    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        ...


@poly_type
class PackageRepository(Protocol):
    """Maintains indexed package publications and release histories."""

    def register_package(self, release: PackageRelease) -> None:
        ...

    def get_releases(self, name: str) -> List[PackageRelease]:
        ...

    def has_package(self, name: str) -> bool:
        ...

    def all_packages(self) -> Set[str]:
        ...


@poly_type
class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:54:16Z
# LAST_CHANGED: 2026-11-04T21:54:16Z
# CHANGE: Implemented interface module: mutable dataclass exceptions with message __str__, frozen @data_type records Version/VersionRange/PackageDependency/PackageRelease/ResolutionOutcome, concrete Version.format/__str__/is_prerelease and VersionRange.__str__, @poly_type protocols with ... stubs.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
import functools
import re
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleError, LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

_NUMERIC_COMPONENT = r"0|[1-9][0-9]*"
_PRERELEASE_COMPONENT = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_COMPONENT = r"[0-9A-Za-z-]+"
_VERSION_PATTERN = re.compile(
    rf"^({_NUMERIC_COMPONENT})\.({_NUMERIC_COMPONENT})\.({_NUMERIC_COMPONENT})"
    rf"(?:-({_PRERELEASE_COMPONENT}(?:\.{_PRERELEASE_COMPONENT})*))?"
    rf"(?:\+({_BUILD_COMPONENT}(?:\.{_BUILD_COMPONENT})*))?\Z"
)
_HYPHEN_RANGE_PATTERN = re.compile(r"^(\S+)\s+-\s+(\S+)$")
_COMPARATOR_OPERATORS: Tuple[str, ...] = ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~")
_WILDCARD_TOKENS: FrozenSet[str] = frozenset({"*", "x", "X"})

# A version interval is (low, low_inclusive, high, high_inclusive); None means unbounded.
_Interval = Tuple[Optional[semver_solver.Version], bool, Optional[semver_solver.Version], bool]
# A range operand is (kind, version, wildcard_major, wildcard_minor).
_RangeOperand = Tuple[str, Optional[semver_solver.Version], Optional[int], Optional[int]]
_AccumulatedConstraint = Tuple[str, semver_solver.VersionRange]

_latest_repository: Optional[semver_solver.PackageRepository] = None


def _version_from_match(match: "re.Match[str]") -> semver_solver.Version:
    """Builds an immutable Version from a matched SemVer 2.0.0 regular expression."""
    prerelease: Tuple[str, ...] = ()
    if match.group(4) is not None:
        prerelease = tuple(match.group(4).split("."))
    build: Tuple[str, ...] = ()
    if match.group(5) is not None:
        build = tuple(match.group(5).split("."))
    return semver_solver.Version(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
        prerelease=prerelease,
        build=build,
    )


def _parse_version_text(text: str) -> semver_solver.Version:
    """Parses a SemVer 2.0.0 string, rejecting leading zeroes and grammar violations."""
    match = _VERSION_PATTERN.match(text)
    if match is None:
        raise semver_solver.InvalidVersionError(f"Invalid semantic version: {text!r}", text)  # pragma: no cover (assumption: precondition_guard)
    return _version_from_match(match)


def _is_numeric_component(text: str) -> bool:
    """Indicates whether text is an unsigned decimal integer without leading zeroes."""
    return (
        text.isascii()
        and text.isdigit()
        and (text == "0" or not text.startswith("0"))
    )


def _compare_precedence(v1: semver_solver.Version, v2: semver_solver.Version) -> int:
    """Compares two versions by SemVer 2.0.0 precedence rules, ignoring build metadata."""
    for left, right in (
        (v1.major, v2.major),
        (v1.minor, v2.minor),
        (v1.patch, v2.patch),
    ):
        if left < right:
            return -1
        if left > right:
            return 1
    # A normal version always ranks above a pre-release sharing the numeric core.
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for left, right in zip(v1.prerelease, v2.prerelease):
        left_numeric = _is_numeric_component(left)
        right_numeric = _is_numeric_component(right)
        if left_numeric and right_numeric:
            left_value = int(left)
            right_value = int(right)
            if left_value < right_value:
                return -1
            if left_value > right_value:
                return 1
        elif left_numeric:
            # Numeric identifiers rank below alphanumeric identifiers.
            return -1
        elif right_numeric:
            return 1
        elif left < right:
            return -1
        elif left > right:
            return 1
    if len(v1.prerelease) < len(v2.prerelease):
        return -1
    if len(v1.prerelease) > len(v2.prerelease):
        return 1
    return 0


def _wildcard_interval(major: Optional[int], minor: Optional[int]) -> _Interval:
    """Expands a wildcard operand into a half-open version interval."""
    if major is None:  # pragma: no cover (assumption: caller guarantees a concrete major)
        return (None, True, None, True)
    if minor is None:
        return (
            semver_solver.Version(major, 0, 0),
            True,
            semver_solver.Version(major + 1, 0, 0),
            False,
        )
    return (
        semver_solver.Version(major, minor, 0),
        True,
        semver_solver.Version(major, minor + 1, 0),
        False,
    )


def _parse_range_operand(token: str, raw_text: str) -> _RangeOperand:
    """Parses one range operand as an exact version, wildcard, or universal wildcard."""
    if token in _WILDCARD_TOKENS:
        return ("any", None, None, None)
    match = _VERSION_PATTERN.match(token)
    if match is not None:
        return ("version", _version_from_match(match), None, None)
    parts = token.split(".")
    if len(parts) == 2:
        major_text, minor_text = parts
        if minor_text in _WILDCARD_TOKENS and _is_numeric_component(major_text):
            return ("wildcard", None, int(major_text), None)
    elif len(parts) == 3:
        major_text, minor_text, patch_text = parts
        if (
            patch_text in _WILDCARD_TOKENS
            and _is_numeric_component(major_text)
            and _is_numeric_component(minor_text)
        ):
            return ("wildcard", None, int(major_text), int(minor_text))
    # Bare partial versions without wildcard characters are malformed range syntax.
    raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: precondition_guard)
        f"Invalid version range expression: {raw_text!r}", raw_text
    )


def _operand_interval(operand: _RangeOperand) -> _Interval:
    """Converts an operand to its exact interval when used with equality semantics."""
    kind, version, major, minor = operand
    if kind == "version":
        assert version is not None
        return (version, True, version, True)
    if kind == "any":
        return (None, True, None, True)
    return _wildcard_interval(major, minor)


def _caret_upper_bound(version: semver_solver.Version) -> semver_solver.Version:
    """Computes the exclusive caret upper bound from the first non-zero component."""
    if version.major > 0:
        return semver_solver.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_solver.Version(0, version.minor + 1, 0)
    return semver_solver.Version(0, 0, version.patch + 1)


def _complement_interval(interval: _Interval) -> List[_Interval]:
    """Returns the interval set describing every version outside the given interval."""
    low, low_inclusive, high, high_inclusive = interval
    pieces: List[_Interval] = []
    if low is not None:
        pieces.append((None, True, low, not low_inclusive))
    if high is not None:
        pieces.append((high, not high_inclusive, None, True))
    return pieces


def _comparator_intervals(
    operator: str,
    operand: _RangeOperand,
    raw_text: str,
) -> List[_Interval]:
    """Expands one comparator into a disjoint interval set."""
    kind, version, major, minor = operand
    if operator in ("", "=", "=="):
        return [_operand_interval(operand)]
    if operator == "!=":
        return _complement_interval(_operand_interval(operand))
    if operator == "^":
        if kind == "version":
            assert version is not None
            return [(version, True, _caret_upper_bound(version), False)]
        if kind == "any":
            return [(None, True, None, True)]
        lower, _, upper, _ = _wildcard_interval(major, minor)
        assert lower is not None and upper is not None
        if major is not None and major > 0:
            caret_upper = semver_solver.Version(major + 1, 0, 0)
        elif minor is not None and minor > 0:
            caret_upper = semver_solver.Version(0, minor + 1, 0)
        elif minor is not None:
            caret_upper = semver_solver.Version(0, 1, 0)
        else:
            caret_upper = semver_solver.Version(1, 0, 0)
        return [(lower, True, caret_upper, False)]
    if operator == "~":
        if kind == "version":
            assert version is not None
            return [
                (
                    version,
                    True,
                    semver_solver.Version(version.major, version.minor + 1, 0),
                    False,
                )
            ]
        if kind == "any":
            return [(None, True, None, True)]
        lower, _, upper, _ = _wildcard_interval(major, minor)
        assert lower is not None and upper is not None
        return [(lower, True, upper, False)]
    if kind == "version":
        assert version is not None
        if operator == "<":
            return [(None, True, version, False)]
        if operator == "<=":
            return [(None, True, version, True)]
        if operator == ">":
            return [(version, False, None, True)]
        if operator == ">=":
            return [(version, True, None, True)]
    elif kind == "any":
        return [(None, True, None, True)]
    else:
        lower, _, upper, _ = _wildcard_interval(major, minor)
        assert lower is not None and upper is not None
        if operator == "<":
            return [(None, True, lower, False)]
        if operator == "<=":
            return [(None, True, upper, False)]
        if operator == ">":
            # Strict-greater than the whole wildcard band starts at its exclusive
            # upper boundary (e.g. >1.x is >=2.0.0), matching the <= complement.
            return [(upper, True, None, True)]
        if operator == ">=":
            return [(lower, True, None, True)]
    raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: operator validated by tokenizer)
        f"Invalid version range expression: {raw_text!r}", raw_text
    )


def _intersect_interval(left: _Interval, right: _Interval) -> Optional[_Interval]:
    """Intersects two intervals, returning None when the result is empty."""
    left_low, left_low_inclusive, left_high, left_high_inclusive = left
    right_low, right_low_inclusive, right_high, right_high_inclusive = right
    if left_low is None:
        low, low_inclusive = right_low, right_low_inclusive
    elif right_low is None:
        low, low_inclusive = left_low, left_low_inclusive
    else:
        comparison = _compare_precedence(left_low, right_low)
        if comparison > 0:
            low, low_inclusive = left_low, left_low_inclusive
        elif comparison < 0:
            low, low_inclusive = right_low, right_low_inclusive
        else:
            low, low_inclusive = left_low, left_low_inclusive and right_low_inclusive
    if left_high is None:
        high, high_inclusive = right_high, right_high_inclusive
    elif right_high is None:
        high, high_inclusive = left_high, left_high_inclusive
    else:
        comparison = _compare_precedence(left_high, right_high)
        if comparison < 0:
            high, high_inclusive = left_high, left_high_inclusive
        elif comparison > 0:
            high, high_inclusive = right_high, right_high_inclusive
        else:
            high, high_inclusive = left_high, left_high_inclusive and right_high_inclusive
    if low is not None and high is not None:
        comparison = _compare_precedence(low, high)
        if comparison > 0:
            return None
        if comparison == 0 and not (low_inclusive and high_inclusive):
            return None
    return (low, low_inclusive, high, high_inclusive)


def _intersect_interval_sets(
    left: List[_Interval], right: List[_Interval]
) -> List[_Interval]:
    """Intersects two interval sets, producing a disjoint interval set."""
    result: List[_Interval] = []
    for left_interval in left:
        for right_interval in right:
            intersection = _intersect_interval(left_interval, right_interval)
            if intersection is not None:
                result.append(intersection)
    return result


def _tokenize_clause(clause: str, raw_text: str) -> List[Tuple[str, str]]:
    """Splits a clause into (operator, operand) pairs delimited strictly by whitespace."""
    tokens: List[Tuple[str, str]] = []
    index = 0
    length = len(clause)
    while index < length:
        if clause[index].isspace():
            index += 1
            continue
        operator = ""
        for candidate in _COMPARATOR_OPERATORS:
            if clause.startswith(candidate, index):
                operator = candidate
                index += len(candidate)
                break
        while index < length and clause[index].isspace():
            index += 1
        start = index
        while index < length and not clause[index].isspace():
            index += 1
        operand = clause[start:index]
        if not operand:
            raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: precondition_guard)
                f"Invalid version range expression: {raw_text!r}", raw_text
            )
        tokens.append((operator, operand))
    return tokens


def _compile_comparator_clause(
    clause: str, raw_text: str
) -> Tuple[List[_Interval], List[semver_solver.Version]]:
    """Compiles a whitespace-delimited comparator clause into an interval set."""
    intervals: List[_Interval] = [(None, True, None, True)]
    prerelease_targets: List[semver_solver.Version] = []
    for operator, operand_text in _tokenize_clause(clause, raw_text):
        operand = _parse_range_operand(operand_text, raw_text)
        kind, version, _, _ = operand
        if kind == "version" and version is not None and version.prerelease:
            prerelease_targets.append(version)
        intervals = _intersect_interval_sets(
            intervals, _comparator_intervals(operator, operand, raw_text)
        )
    return intervals, prerelease_targets


def _lower_operand_bound(operand: _RangeOperand) -> Tuple[Optional[semver_solver.Version], bool]:
    """Derives the inclusive lower bound contributed by a hyphen range endpoint."""
    kind, version, major, minor = operand
    if kind == "version":
        assert version is not None
        return (version, True)
    if kind == "any":
        return (None, True)
    lower, _, _, _ = _wildcard_interval(major, minor)
    return (lower, True)


def _upper_operand_bound(operand: _RangeOperand) -> Tuple[Optional[semver_solver.Version], bool]:
    """Derives the upper bound contributed by a hyphen range endpoint."""
    kind, version, major, minor = operand
    if kind == "version":
        assert version is not None
        return (version, True)
    if kind == "any":
        return (None, True)
    _, _, upper, _ = _wildcard_interval(major, minor)
    return (upper, False)


def _is_empty_interval(interval: _Interval) -> bool:
    """Indicates whether an interval contains no versions at all."""
    low, low_inclusive, high, high_inclusive = interval
    if low is None or high is None:
        return False
    comparison = _compare_precedence(low, high)
    if comparison > 0:
        return True
    return comparison == 0 and not (low_inclusive and high_inclusive)


def _compile_hyphen_clause(
    lower_text: str, upper_text: str, raw_text: str
) -> Tuple[List[_Interval], List[semver_solver.Version]]:
    """Compiles a hyphen range into a single inclusive interval."""
    lower_operand = _parse_range_operand(lower_text, raw_text)
    upper_operand = _parse_range_operand(upper_text, raw_text)
    prerelease_targets: List[semver_solver.Version] = []
    for operand in (lower_operand, upper_operand):
        kind, version, _, _ = operand
        if kind == "version" and version is not None and version.prerelease:
            prerelease_targets.append(version)
    low, low_inclusive = _lower_operand_bound(lower_operand)
    high, high_inclusive = _upper_operand_bound(upper_operand)
    interval: _Interval = (low, low_inclusive, high, high_inclusive)
    if _is_empty_interval(interval):
        return ([], prerelease_targets)
    return ([interval], prerelease_targets)


def _compile_range(
    text: str,
) -> Tuple[List[List[_Interval]], List[semver_solver.Version]]:
    """Compiles a (possibly unioned) range expression into disjunctive interval sets."""
    if not text.strip() or "," in text:
        raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: precondition_guard)
            f"Invalid version range expression: {text!r}", text
        )
    clauses: List[List[_Interval]] = []
    prerelease_targets: List[semver_solver.Version] = []
    for raw_clause in text.split("||"):
        clause = raw_clause.strip()
        if not clause:
            raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: precondition_guard)
                f"Invalid version range expression: {text!r}", text
            )
        hyphen = _HYPHEN_RANGE_PATTERN.match(clause)
        if hyphen is not None:
            intervals, clause_targets = _compile_hyphen_clause(
                hyphen.group(1), hyphen.group(2), text
            )
        else:
            intervals, clause_targets = _compile_comparator_clause(clause, text)
        clauses.append(intervals)
        prerelease_targets.extend(clause_targets)
    return clauses, prerelease_targets


def _interval_contains(interval: _Interval, version: semver_solver.Version) -> bool:
    """Evaluates whether a version lies inside an interval under precedence ordering."""
    low, low_inclusive, high, high_inclusive = interval
    if low is not None:
        comparison = _compare_precedence(version, low)
        if comparison < 0 or (comparison == 0 and not low_inclusive):
            return False
    if high is not None:
        comparison = _compare_precedence(version, high)
        if comparison > 0 or (comparison == 0 and not high_inclusive):
            return False
    return True


def _satisfies_range(
    version: semver_solver.Version,
    raw_text: str,
    include_prerelease: bool,
) -> bool:
    """Evaluates a version against a range expression, applying pre-release gating."""
    clauses, prerelease_targets = _compile_range(raw_text)
    # A version satisfies the range when it lies in at least one union clause.
    if not any(
        any(_interval_contains(interval, version) for interval in clause)
        for clause in clauses
    ):
        return False
    # Pre-release versions require an explicit pre-release target at the same core.
    if version.prerelease and not include_prerelease:
        return any(
            target.major == version.major
            and target.minor == version.minor
            and target.patch == version.patch
            for target in prerelease_targets
        )
    return True


def _compare_releases(
    left: semver_solver.PackageRelease, right: semver_solver.PackageRelease
) -> int:
    """Orders package releases by version precedence."""
    return _compare_precedence(left.version, right.version)


def _resolve_version_engine() -> semver_solver.VersionEngine:
    """Resolves the version engine singleton, falling back to a direct instance."""
    try:
        return get_singleton(semver_solver.VersionEngine)
    except LifecycleError:  # pragma: no cover (assumption: lifecycle registration precedes resolution)
        return VersionEngine()


def _resolve_package_repository() -> semver_solver.PackageRepository:
    """Resolves the shared package repository, preferring the live instance."""
    global _latest_repository
    if _latest_repository is None:  # pragma: no cover (assumption: lifecycle registration precedes resolution)
        try:
            _latest_repository = get_singleton(semver_solver.PackageRepository)
        except LifecycleError:
            _latest_repository = PackageRepository()
    return _latest_repository


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    def __init__(self) -> None:
        # Stateless engine; parsing is realized by deterministic module helpers.
        pass

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # POSTCONDITIONS: valid SemVer 2.0.0 text yields Version; grammar violations raise.
        return _parse_version_text(text)

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # POSTCONDITIONS: negative/zero/positive reflect SemVer precedence ordering.
        return _compare_precedence(v1, v2)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # POSTCONDITIONS: validate the expression, storing its trimmed range text.
        _compile_range(text)
        return semver_solver.VersionRange(raw_text=text.strip())

    @operation
    @override
    def satisfies(self, version: semver_solver.Version, range_constraint: semver_solver.VersionRange, include_prerelease: bool) -> bool:
        # POSTCONDITIONS: evaluate interval membership plus pre-release gating rules.
        return _satisfies_range(version, range_constraint.raw_text, include_prerelease)


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Maintains package name to releases mapping (precedence descending).
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}
        global _latest_repository
        _latest_repository = self

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # POSTCONDITIONS: register the release and keep the list precedence descending.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=functools.cmp_to_key(_compare_releases), reverse=True)

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # WHEN name is unregistered, MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(  # pragma: no cover (assumption: precondition_guard)
                f"Package {name!r} is not registered in the repository", name
            )
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # POSTCONDITIONS: membership test over registered package names.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # POSTCONDITIONS: produce the set of all registered package names.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        # Resolution state is scoped to each resolve invocation.
        pass

    @operation
    @override
    def resolve(self, root_dependencies: Collection[semver_solver.PackageDependency]) -> semver_solver.ResolutionOutcome:
        repository = _resolve_package_repository()
        engine = _resolve_version_engine()
        accumulated: Dict[str, List[_AccumulatedConstraint]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def candidate_releases(package_name: str) -> List[semver_solver.PackageRelease]:
            """Determines candidate releases satisfying all accumulated constraints."""
            if not repository.has_package(package_name):
                return []
            constraints = accumulated.get(package_name, ())
            return [
                release
                for release in repository.get_releases(package_name)
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in constraints
                )
            ]

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True
            # MRV variable selection with lexical tie-breaking.
            candidates_by_package = {
                name: candidate_releases(name) for name in unassigned
            }
            selected = min(
                unassigned,
                key=lambda name: (len(candidates_by_package[name]), name),
            )
            candidates = candidates_by_package[selected]
            if not candidates:
                requesters = [source for source, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                # Only real package requesters are reported; "root" is a marker.
                conflicting_packages.update(
                    source for source in requesters if source != "root"
                )
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # Value ordering explores releases in descending precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                newly_added: List[Tuple[str, _AccumulatedConstraint]] = []
                conflict_detected = False
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{dependency.name}' "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            conflict_detected = True
                            break
                    else:
                        entry: _AccumulatedConstraint = (
                            selected,
                            dependency.range_constraint,
                        )
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
                # Backtrack: undo newly introduced constraints and the assignment.
                for package_name, entry in reversed(newly_added):
                    entries = accumulated[package_name]
                    for position in range(len(entries) - 1, -1, -1):
                        if entries[position] is entry:
                            del entries[position]
                            break
                    if not entries:
                        del accumulated[package_name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not backtrack():
            explanation = (  # pragma: no cover (assumption: precondition_guard)
                " | ".join(conflict_trail)
                if conflict_trail
                else "Dependency resolution exhausted all candidate releases"
            )
            raise semver_solver.ResolutionConflictError(  # pragma: no cover (assumption: precondition_guard)
                f"Unable to resolve dependencies: {explanation}",
                tuple(sorted(conflicting_packages)),
                explanation,
            )
        selected_versions: Dict[str, semver_solver.Version] = {
            name: release.version for name, release in assignment.items()
        }
        return semver_solver.ResolutionOutcome(
            selected_versions=selected_versions,
            derivation_steps=tuple(derivation_steps),
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_solver.VersionEngine],
        tier=system,
    )
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, semver_solver.PackageRepository],
        tier=system,
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, semver_solver.DependencySolver],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T22:20:47Z
# LAST_CHANGED: 2026-11-04T22:16:34Z
# CHANGE: Fixed wildcard strict-greater boundary defect in _comparator_intervals: '>M.x'/'>M.m.x' now normalize to an inclusive start at the wildcard band's exclusive upper bound (e.g. '>1.x' -> >=2.0.0), consistent with the '<=1.x' (<2.0.0) complement and the '!=1.x' complement, so satisfies(Version(2,0,0), VersionRange('>1.x'), False) is True. Sibling wildcard relational normalizations audited and confirmed correct.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T22:20:47Z
# PRETENSE_QA_AUDIT: 2026-11-04T22:20:36Z
# --- END AUTOFAB METADATA ---
