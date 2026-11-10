# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_165917_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-11-08T16:59:17.264258+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 298,954
#   Cached Inbound Tokens:   23,176,064
#   Outbound Tokens:         264,254
#   Total Tokens:            23,739,272
#   Financial Cost ($USD):   $0.2729
#   Wall Clock Duration:     1552.84s
#   Step Latencies (s):      [367.0, 450.9, 134.5, 205.9, 20.2, 116.1, 124.7, 155.4, 10.1, 83.6, 104.1, 20.3, 83.6, 61.2, 20.2, 53.0, 53.1, 20.2, 10.0]
#   Role Execution Rounds:   lib: 2, pretense: 6, pretense_coverage: 5, pretense_qa: 6 (Total: 19)
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
"""Library interface specification for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __post_init__(self) -> None:
        # Reify the diagnostic message into the underlying Exception state so that
        # standard exception machinery (args, tracebacks, pickling) remains intact.
        Exception.__init__(self, self.message)

    def __str__(self) -> str:
        # Exception diagnostics surface the contracted message verbatim.
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered.

    Args:
        message: Diagnostic description of the error.
        raw_text: Original unparseable version string.
    """

    raw_text: str


@dataclass
class InvalidRangeError(SemVerError):
    """Raised when a version range expression contains malformed syntax.

    Args:
        message: Diagnostic description of the error.
        raw_range: Original malformed range expression string.
    """

    raw_range: str


@dataclass
class ResolutionConflictError(SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually.

    Args:
        message: Diagnostic description of the conflict.
        conflicting_packages: Sequence of package names involved in the conflict.
        explanation: Detailed diagnostic derivation of the unsatisfiable conflict.
    """

    conflicting_packages: Tuple[str, ...]
    explanation: str


@dataclass
class PackageNotFoundError(SemVerError):
    """Raised when a referenced package name does not exist in the repository.

    Args:
        message: Diagnostic description of the missing package.
        package_name: Name of the missing package.
    """

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
    """Immutable semantic version representation conforming to SemVer 2.0.0.

    Args:
        major: Non-negative integer major version.
        minor: Non-negative integer minor version.
        patch: Non-negative integer patch version.
        prerelease: Ordered tuple of dot-separated pre-release identifiers.
        build: Ordered tuple of dot-separated build metadata identifiers.
    """

    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        """Indicates whether this version contains pre-release identifiers."""
        # A version is a prerelease exactly when prerelease identifiers are present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        # Canonical rendering of major.minor.patch with optional -prerelease and +build.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression.

    Args:
        raw_text: Canonical text representation of the range expression.
    """

    raw_text: str

    def __str__(self) -> str:
        """Returns the raw range text representation."""
        return self.raw_text


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range.

    Args:
        name: Name of the required package.
        range_constraint: Acceptable version range constraint.
    """

    name: str
    range_constraint: VersionRange


@data_type
@dataclass(frozen=True)
class PackageRelease:
    """Immutable publication record of a package at a specific semantic version.

    Args:
        name: Name of the package.
        version: Semantic version of this release.
        dependencies: Declared prerequisite package dependencies.
    """

    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run.

    Args:
        selected_versions: Mapping of package names to their selected semantic versions.
        derivation_steps: Ordered sequence of decision and deduction steps.
    """

    selected_versions: Mapping[str, Version]
    derivation_steps: Tuple[str, ...]


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing, precedence comparison, and range matching."""

    @operation
    def parse_version(self, text: str) -> Version:
        """Parses a version string conforming to SemVer 2.0.0.

        Args:
            text: Raw version string to parse.

        Returns:
            The parsed immutable Version record.

        Raises:
            InvalidVersionError: If text violates SemVer 2.0.0 grammar or contains leading zeroes.
        """
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions.

        Args:
            v1: First semantic version.
            v2: Second semantic version.

        Returns:
            Negative integer if v1 < v2, zero if v1 == v2, positive integer if v1 > v2.
        """
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record.

        Args:
            text: Raw range expression text.

        Returns:
            The parsed VersionRange.

        Raises:
            InvalidRangeError: If text contains malformed range syntax.
        """
        ...

    @operation
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint.

        Args:
            version: Candidate semantic version to test.
            range_constraint: Version range to evaluate against.
            include_prerelease: Whether to allow pre-release versions to match non-prerelease ranges.

        Returns:
            True if the version satisfies the range, False otherwise.
        """
        ...


@poly_type
class PackageRepository(Protocol):
    """Maintains indexed package publications and release histories."""

    @operation
    def register_package(self, release: PackageRelease) -> None:
        """Registers a package release with its declared dependencies.

        Args:
            release: Package release publication to register.
        """
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending.

        Args:
            name: Package name to look up.

        Returns:
            List of package releases ordered by version precedence descending.

        Raises:
            PackageNotFoundError: If name is not registered in the repository.
        """
        ...

    @operation
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository.

        Args:
            name: Package name to check.

        Returns:
            True if the package exists, False otherwise.
        """
        ...

    @operation
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names.

        Returns:
            Set of registered package name strings.
        """
        ...


@poly_type
class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    @operation
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies.

        Args:
            root_dependencies: Initial package dependencies to satisfy.

        Returns:
            ResolutionOutcome recording selected package versions and derivation steps.

        Raises:
            ResolutionConflictError: If dependencies cannot be satisfied mutually.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:06:51Z
# LAST_CHANGED: 2026-11-08T17:06:51Z
# CHANGE: Implement SemVer 2.0 interface: dataclass exceptions with message/raw attributes and __str__, frozen data types (Version with is_prerelease/format/__str__, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome), comparator enum, and flat Protocol stubs for VersionEngine, PackageRepository, and DependencySolver matching low/semver_solver.pyi.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Library implementation of SemVer 2.0 parsing, range matching, and dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_solver


# SemVer 2.0.0 grammar: non-negative numeric components without leading zeroes,
# optional dot-separated pre-release identifiers, and optional build metadata.
_SEMVER_PATTERN = (
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
_VERSION_RE = re.compile(_SEMVER_PATTERN)

# Wildcard identifiers standing in for an unspecified numeric component.
_WILDCARD_CHARS = frozenset({"x", "X", "*"})

# Relational and prefix operators accepted by range expressions, longest first so
# that multi-character operators are consumed before their single-character prefixes.
_COMPARATOR_PREFIXES = (">=", "<=", "==", "!=", "^", "~", ">", "<", "=")
_OPERATOR_TOKENS = frozenset(_COMPARATOR_PREFIXES)

# A hyphen range connects two whitespace-separated bounds with a spaced hyphen.
_HYPHEN_CLAUSE_RE = re.compile(r"(\S+)\s+-\s+(\S+)")

# A clause is a conjunction of comparators; alternatives are its disjunction.
_Clause = List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]
_Alternatives = List[_Clause]

# `< 0.0.0-0` can never hold; it encodes wildcard comparators matching no version.
_IMPOSSIBLE_COMPARATOR: Tuple[semver_solver.ComparatorOp, semver_solver.Version] = (
    semver_solver.ComparatorOp.LT,
    semver_solver.Version(major=0, minor=0, patch=0, prerelease=("0",)),
)


def _compare_versions(left: semver_solver.Version, right: semver_solver.Version) -> int:
    """Compares two versions by SemVer 2.0.0 precedence, ignoring build metadata."""
    # Major, minor, and patch compare numerically in sequence.
    if left.major != right.major:
        return -1 if left.major < right.major else 1
    if left.minor != right.minor:
        return -1 if left.minor < right.minor else 1
    if left.patch != right.patch:
        return -1 if left.patch < right.patch else 1
    # A normal version ranks higher than every prerelease with the same numbers.
    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1
    # Prerelease identifiers compare position by position.
    for left_identifier, right_identifier in zip(left.prerelease, right.prerelease):
        left_numeric = left_identifier.isdigit()
        right_numeric = right_identifier.isdigit()
        if left_numeric and right_numeric:
            left_value = int(left_identifier)
            right_value = int(right_identifier)
            if left_value != right_value:
                return -1 if left_value < right_value else 1
        elif left_numeric:
            # Numeric identifiers rank below alphanumeric identifiers.
            return -1
        elif right_numeric:
            return 1
        elif left_identifier != right_identifier:
            # Alphanumeric identifiers compare in ASCII lexicographic order.
            return -1 if left_identifier < right_identifier else 1
    # A longer identifier sequence ranks higher when every common prefix matches.
    if len(left.prerelease) != len(right.prerelease):
        return 1 if len(left.prerelease) > len(right.prerelease) else -1
    return 0


def _try_parse_version(text: str) -> Optional[semver_solver.Version]:
    """Parses text as a full SemVer 2.0.0 version, returning None when it does not conform."""
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        return None
    prerelease = tuple(match.group("prerelease").split(".")) if match.group("prerelease") else ()
    build = tuple(match.group("build").split(".")) if match.group("build") else ()
    return semver_solver.Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=prerelease,
        build=build,
    )


def _parse_version_text(text: str) -> semver_solver.Version:
    """Parses a SemVer 2.0.0 version string, raising InvalidVersionError on malformed input."""
    version = _try_parse_version(text)
    if version is None:
        raise semver_solver.InvalidVersionError(
            message=f"invalid SemVer 2.0.0 version string: {text!r}",
            raw_text=text,
        )
    return version


def _parse_wildcard(token: str) -> Optional[Tuple[Optional[int], Optional[int], Optional[int]]]:
    """Parses a wildcard expression such as '1.x' or '1.2.*' into per-component bounds."""
    parts = token.split(".")
    if not 1 <= len(parts) <= 3:
        return None
    components: List[Optional[int]] = []
    wildcard_seen = False
    has_wildcard = False
    for part in parts:
        if part in _WILDCARD_CHARS:
            wildcard_seen = True
            has_wildcard = True
            components.append(None)
            continue
        if wildcard_seen:
            # Numeric components may not follow a wildcard component.
            return None
        if not part.isdigit():
            return None
        if len(part) > 1 and part.startswith("0"):
            # Leading zeroes are never permitted in numeric identifiers.
            return None
        components.append(int(part))
    if not has_wildcard:
        # Bare partial versions lacking a wildcard are not range expressions.
        return None
    while len(components) < 3:
        components.append(None)
    return (components[0], components[1], components[2])


def _wildcard_upper(major: int, minor: Optional[int]) -> semver_solver.Version:
    """Computes the exclusive upper bound of a wildcard expression with a known major."""
    if minor is None:
        return semver_solver.Version(major=major + 1, minor=0, patch=0)
    return semver_solver.Version(major=major, minor=minor + 1, patch=0)


def _caret_upper(
    major: int,
    minor: Optional[int],
    patch: Optional[int],
) -> semver_solver.Version:
    """Computes the exclusive caret upper bound from the first non-zero component."""
    if minor is None:
        return semver_solver.Version(major=major + 1, minor=0, patch=0)
    if major > 0:
        return semver_solver.Version(major=major + 1, minor=0, patch=0)
    if patch is None:
        return semver_solver.Version(major=0, minor=minor + 1, patch=0)
    if minor > 0:
        return semver_solver.Version(major=0, minor=minor + 1, patch=0)
    return semver_solver.Version(major=0, minor=0, patch=patch + 1)


def _tilde_upper(major: int, minor: Optional[int]) -> semver_solver.Version:
    """Computes the exclusive tilde upper bound at the next minor (or major) boundary."""
    if minor is None:
        return semver_solver.Version(major=major + 1, minor=0, patch=0)
    return semver_solver.Version(major=major, minor=minor + 1, patch=0)


def _conjoin(left: _Alternatives, right: _Alternatives) -> _Alternatives:
    """Conjoins two alternative sets by distributing every clause combination."""
    combined: _Alternatives = []
    for left_clause in left:
        for right_clause in right:
            combined.append(left_clause + right_clause)
    return combined


def _expand_hyphen_bound(token: str, is_lower: bool, raw_range: str) -> _Alternatives:
    """Expands one hyphen range bound into inclusive lower or exclusive upper comparators."""
    operator = semver_solver.ComparatorOp
    exact = _try_parse_version(token)
    if exact is not None:
        return [[(operator.GE if is_lower else operator.LE, exact)]]
    wildcard = _parse_wildcard(token)
    if wildcard is None:
        raise semver_solver.InvalidRangeError(
            message=f"invalid hyphen range bound {token!r} in range expression {raw_range!r}",
            raw_range=raw_range,
        )
    major, minor, _ = wildcard
    if major is None:
        # A fully wildcard bound leaves its side of the range unbounded.
        return [[]]
    if is_lower:
        lower = semver_solver.Version(major=major, minor=minor or 0, patch=0)
        return [[(operator.GE, lower)]]
    return [[(operator.LT, _wildcard_upper(major, minor))]]


def _expand_comparator(operator_token: str, token: str, raw_range: str) -> _Alternatives:
    """Expands one comparator (or prefix/wildcard expression) into alternative clauses."""
    operator = semver_solver.ComparatorOp
    exact = _try_parse_version(token)
    if exact is not None:
        if operator_token == "!=":
            return [[(operator.NE, exact)]]
        if operator_token in ("", "=", "=="):
            return [[(operator.EQ, exact)]]
        if operator_token == "<":
            return [[(operator.LT, exact)]]
        if operator_token == "<=":
            return [[(operator.LE, exact)]]
        if operator_token == ">":
            return [[(operator.GT, exact)]]
        if operator_token == ">=":
            return [[(operator.GE, exact)]]
        upper = (
            _caret_upper(exact.major, exact.minor, exact.patch)
            if operator_token == "^"
            else _tilde_upper(exact.major, exact.minor)
        )
        # Both prefix ranges expand into an inclusive lower and an exclusive upper bound.
        return [[(operator.GE, exact), (operator.LT, upper)]]
    wildcard = _parse_wildcard(token)
    if wildcard is None:
        raise semver_solver.InvalidRangeError(
            message=f"invalid version or wildcard expression {token!r} in range expression {raw_range!r}",
            raw_range=raw_range,
        )
    major, minor, patch = wildcard
    if major is None:
        # A wildcard in the major position denotes every version.
        if operator_token in (">", "<", "!="):
            return [[_IMPOSSIBLE_COMPARATOR]]
        return [[]]
    lower = semver_solver.Version(major=major, minor=minor or 0, patch=patch or 0)
    upper = _wildcard_upper(major, minor)
    if operator_token in ("", "=", "=="):
        return [[(operator.GE, lower), (operator.LT, upper)]]
    if operator_token == "!=":
        # A negated wildcard spans everything below and above the wildcard interval.
        return [[(operator.LT, lower)], [(operator.GE, upper)]]
    if operator_token == ">=":
        return [[(operator.GE, lower)]]
    if operator_token == ">":
        return [[(operator.GE, upper)]]
    if operator_token == "<":
        return [[(operator.LT, lower)]]
    if operator_token == "<=":
        return [[(operator.LT, upper)]]
    if operator_token == "^":
        return [[(operator.GE, lower), (operator.LT, _caret_upper(major, minor, patch))]]
    return [[(operator.GE, lower), (operator.LT, _tilde_upper(major, minor))]]


def _compile_clause(clause: str, raw_range: str) -> _Alternatives:
    """Compiles one whitespace-delimited clause into alternative comparator sets."""
    hyphen_match = _HYPHEN_CLAUSE_RE.fullmatch(clause)
    if hyphen_match is not None:
        lower = _expand_hyphen_bound(hyphen_match.group(1), True, raw_range)
        upper = _expand_hyphen_bound(hyphen_match.group(2), False, raw_range)
        return _conjoin(lower, upper)
    if "," in clause:
        raise semver_solver.InvalidRangeError(
            message=f"commas are not permitted as comparator delimiters in range expression {raw_range!r}",
            raw_range=raw_range,
        )
    # Comparators within a clause are delimited strictly by whitespace.
    tokens = clause.split()
    items: List[Tuple[str, str]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATOR_TOKENS:
            if index + 1 >= len(tokens):
                raise semver_solver.InvalidRangeError(
                    message=f"operator {token!r} is not followed by a version in range expression {raw_range!r}",
                    raw_range=raw_range,
                )
            items.append((token, tokens[index + 1]))
            index += 2
            continue
        # Every non-empty token is scanned for an optional operator prefix; a token
        # without one is a bare version or wildcard target.
        operator_token = ""
        target = token
        for prefix in _COMPARATOR_PREFIXES:
            if token.startswith(prefix):
                operator_token = prefix
                target = token[len(prefix):]
                break
        items.append((operator_token, target))
        index += 1
    alternatives: _Alternatives = [[]]
    for operator_token, token in items:
        alternatives = _conjoin(alternatives, _expand_comparator(operator_token, token, raw_range))
    return alternatives


def _parse_range_text(text: str) -> _Alternatives:
    """Parses and validates a range expression into alternative comparator sets."""
    trimmed = text.strip()
    if not trimmed:
        raise semver_solver.InvalidRangeError(
            message="version range expression must not be empty",
            raw_range=text,
        )
    alternatives: _Alternatives = []
    # Union alternatives are separated by '||'; empty clauses are malformed.
    for union_clause in trimmed.split("||"):
        clause = union_clause.strip()
        if not clause:
            raise semver_solver.InvalidRangeError(
                message=f"empty union clause in range expression {trimmed!r}",
                raw_range=text,
            )
        alternatives.extend(_compile_clause(clause, text))
    return alternatives


def _test_comparator(
    version: semver_solver.Version,
    operator: semver_solver.ComparatorOp,
    bound: semver_solver.Version,
) -> bool:
    """Tests one comparator against the candidate version using precedence ordering."""
    comparison = _compare_versions(version, bound)
    if operator is semver_solver.ComparatorOp.EQ:
        return comparison == 0
    if operator is semver_solver.ComparatorOp.NE:
        return comparison != 0
    if operator is semver_solver.ComparatorOp.LT:
        return comparison < 0
    if operator is semver_solver.ComparatorOp.LE:
        return comparison <= 0
    if operator is semver_solver.ComparatorOp.GT:
        return comparison > 0
    return comparison >= 0


def _evaluate_clauses(
    version: semver_solver.Version,
    alternatives: _Alternatives,
    include_prerelease: bool,
) -> bool:
    """Evaluates the candidate version against alternative comparator sets."""
    for clause in alternatives:
        # A clause matches when every comparator in it holds.
        if not all(_test_comparator(version, operator, bound) for operator, bound in clause):
            continue
        if version.is_prerelease and not include_prerelease:
            # Prerelease candidates are filtered out unless the clause targets their
            # exact major, minor, and patch numbers with a prerelease identifier.
            targets_prerelease = any(
                bound.prerelease
                and (bound.major, bound.minor, bound.patch) == (version.major, version.minor, version.patch)
                for _, bound in clause
            )
            if not targets_prerelease:
                continue
        return True
    return False


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine.

    GROUNDING:
    - Realizes SemVer 2.0.0 regular expression grammar, precedence comparison, and range expansion algebra.
    """

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # Grammar validation and extraction treat leading zeroes as malformed input.
        return _parse_version_text(text)

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # Numeric components, prerelease segments, and build metadata exclusion.
        return _compare_versions(v1, v2)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Validate the whole expression eagerly; retain only its surrounding trim.
        _parse_range_text(text)
        return semver_solver.VersionRange(raw_text=text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Compile to disjunctive normal form and match the candidate clause by clause.
        alternatives = _parse_range_text(range_constraint.raw_text)
        return _evaluate_clauses(version, alternatives, include_prerelease)


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing.

    GROUNDING:
    - Maintains _packages dictionary mapping package names to lists of semver_solver.PackageRelease.
    - Coordinates with semver_solver.VersionEngine for release sorting.
    """

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # Insert into the release list for the package name.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # Re-sort in descending version precedence order using the version engine.
        engine = get_singleton(semver_solver.VersionEngine)
        releases.sort(
            key=cmp_to_key(lambda left, right: -engine.compare_precedence(left.version, right.version))
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # A missing package name is a contracted precondition violation.
        releases = self._packages.get(name)
        if releases is None:
            raise semver_solver.PackageNotFoundError(
                message=f"package {name!r} is not registered in the repository",
                package_name=name,
            )
        # Repeat callers observe an isolated shallow copy of the sorted release list.
        return list(releases)

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # Membership is defined by the presence of the package name key.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # Expose exactly the registered package name keys.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver.

    GROUNDING:
    - Coordinates with semver_solver.VersionEngine and semver_solver.PackageRepository to resolve compatible release assignments.
    - Implements depth-first search with Minimum Remaining Values ordering, descending precedence exploration, and conflict trail collection.
    """

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to the (requester, range) pairs
        # imposed on it; a requester of None marks a root dependency.
        constraints: Dict[str, List[Tuple[Optional[str], semver_solver.VersionRange]]] = {}
        for root_dependency in root_dependencies:
            constraints.setdefault(root_dependency.name, []).append((None, root_dependency.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(package: str) -> List[semver_solver.PackageRelease]:
            """Returns releases satisfying every accumulated constraint, highest precedence first."""
            if not repository.has_package(package):
                # Unregistered packages are treated as having zero candidate releases so
                # that PackageNotFoundError never escapes the solver.
                conflict_trail.append(f"Package '{package}' is not registered in the repository")
                return []
            releases = repository.get_releases(package)
            viable = [
                release
                for release in releases
                if all(
                    engine.satisfies(release.version, range_constraint, False)
                    for _, range_constraint in constraints[package]
                )
            ]
            # Explore viable candidate releases in descending precedence order.
            viable.sort(
                key=cmp_to_key(lambda left, right: -engine.compare_precedence(left.version, right.version))
            )
            return viable

        def search() -> bool:
            """Depth-first search; returns True once a complete assignment is found."""
            unassigned = [package for package in constraints if package not in assignment]
            if not unassigned:
                return True
            candidates: Dict[str, List[semver_solver.PackageRelease]] = {}
            for package in unassigned:
                candidates[package] = viable_releases(package)
            # Minimum Remaining Values selection, with lexical tie-breaking.
            selected = min(unassigned, key=lambda package: (len(candidates[package]), package))
            viable = candidates[selected]
            if not viable:
                requesters = sorted(
                    requester
                    for requester, _ in constraints[selected]
                    if requester is not None
                )
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                if requesters:
                    conflict_trail.append(
                        f"No viable release for '{selected}' satisfying constraints from {', '.join(requesters)}"
                    )
                else:
                    conflict_trail.append(
                        f"No viable release for '{selected}' satisfying the root dependency constraints"
                    )
                return False
            for release in viable:
                assignment[selected] = release
                derivation_steps.append(f"Assign '{selected}' to {release.version}")
                added_constraints: List[Tuple[str, Tuple[Optional[str], semver_solver.VersionRange]]] = []
                conflicted = False
                for dependency in release.dependencies:
                    if dependency.name in assignment:
                        # Forward checking: an already assigned package must still satisfy
                        # the dependency range, otherwise this branch conflicts immediately.
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflicted = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' {release.version} requires "
                                f"'{dependency.name}' {dependency.range_constraint.raw_text} but "
                                f"'{dependency.name}' is assigned {assignment[dependency.name].version}"
                            )
                            break
                        continue
                    entry: Tuple[Optional[str], semver_solver.VersionRange] = (
                        selected,
                        dependency.range_constraint,
                    )
                    constraints.setdefault(dependency.name, []).append(entry)
                    added_constraints.append((dependency.name, entry))
                if not conflicted and search():
                    return True
                # Undo this branch before trying the next candidate release.
                for package_name, entry in added_constraints:
                    constraints[package_name].remove(entry)
                    if not constraints[package_name]:
                        del constraints[package_name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not search():
            explanation = (
                "; ".join(conflict_trail)
                if conflict_trail
                else "no mutually compatible version assignment exists"
            )
            raise semver_solver.ResolutionConflictError(
                message=f"dependency resolution failed: {explanation}",
                conflicting_packages=tuple(sorted(conflicting_packages)),
                explanation=explanation,
            )
        # Compile the successful assignment and its decision sequence into an outcome.
        selected_versions: Dict[str, semver_solver.Version] = {
            package: release.version for package, release in assignment.items()
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
# LAST_CLEANED: 2026-11-08T17:25:06Z
# LAST_CHANGED: 2026-11-08T17:16:34Z
# CHANGE: Address unreachable-guard feedback: prune the dead malformed-comparator InvalidRangeError branch in _compile_clause. The optional-group prefix regex is replaced by an explicit longest-first operator-prefix scan (_COMPARATOR_PREFIXES), so every non-empty whitespace-delimited token is partitioned into an operator plus target with no structurally unreachable None branch; malformed targets are still rejected downstream by the version and wildcard validation paths. Comparator parsing behavior is preserved (>, >=, <, <=, =, ==, !=, ^, ~ prefixes unchanged), and the now-unused _COMPARATOR_PREFIX_RE is removed.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:25:06Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:24:45Z
# --- END AUTOFAB METADATA ---
