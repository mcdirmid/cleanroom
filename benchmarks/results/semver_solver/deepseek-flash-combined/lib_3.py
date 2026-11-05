# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_040017_deepseek-flash_semver_solver_combined
# Timestamp: 2026-11-05T04:00:17.239610+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 547,437
#   Cached Inbound Tokens:   47,295,615
#   Outbound Tokens:         524,785
#   Total Tokens:            48,367,837
#   Financial Cost ($USD):   $0.5389
#   Wall Clock Duration:     2225.04s
#   Step Latencies (s):      [246.9, 359.9, 10.5, 434.1, 151.4, 131.6, 10.7, 248.8, 84.4, 35.4, 44.7, 10.7, 10.8, 332.5, 10.3, 160.2, 224.5, 10.6, 118.6, 65.6, 10.7, 10.6, 115.3, 97.1, 84.6, 12.7, 10.7, 112.5, 110.8, 46.3, 10.7, 10.7, 102.5, 10.4, 55.0, 53.2, 10.4, 10.4]
#   Role Execution Rounds:   coverage: 6, lib: 4, pretense: 6, pretense_coverage: 5, pretense_qa: 7, qa: 6, test: 4 (Total: 38)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       38
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Library interface for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error. Verification suites MUST NOT assert on specific wording or prefixes within message, and MUST assert on exception types and structured attributes.
    """

    message: str

    def __post_init__(self) -> None:
        # Reify the diagnostic message into the underlying BaseException arguments.
        Exception.__init__(self, self.message)

    def __str__(self) -> str:
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
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += "-" + ".".join(self.prerelease)
        if self.build:
            text += "+" + ".".join(self.build)
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
# LAST_CLEANED: 2026-11-05T04:06:17Z
# LAST_CHANGED: 2026-11-05T04:06:17Z
# CHANGE: Implement SemVer 2.0 interface: dataclass error hierarchy with message/raw fields and __str__, ComparatorOp enum, frozen Version/VersionRange/PackageDependency/PackageRelease/ResolutionOutcome data types, and VersionEngine/PackageRepository/DependencySolver protocol stubs.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Library implementation for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

# SemVer 2.0.0 grammar: numeric components without leading zeroes, optional
# dot-separated pre-release identifiers, and optional build metadata.
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z"
)

# Wildcard partial versions: *, x, X, M.x, M.*, M.m.x, M.m.*
_ANY_WILDCARD = frozenset({"*", "x", "X"})
_WILDCARD_PATTERN = re.compile(r"^(\d+)(?:\.(\d+))?\.([*xX])$")

# Hyphen range endpoint pair separated by whitespace around the hyphen.
_HYPHEN_PATTERN = re.compile(r"^(\S+)\s+-\s+(\S+)$")

_OPERATORS: Tuple[str, ...] = (">=", "<=", "==", "!=", "^", "~", ">", "<", "=")

_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]
_RangeDnf = List[List[_Comparator]]

# Lowest possible semantic version: every other version ranks strictly above it.
_MINIMUM_VERSION = semver_solver.Version(0, 0, 0, ("0",))


def _ordering_operator(operator: Optional[str]) -> semver_solver.ComparatorOp:
    """Maps a contracted ordering operator token to its comparator operation."""
    if operator == ">":
        return semver_solver.ComparatorOp.GT
    if operator == ">=":
        return semver_solver.ComparatorOp.GE
    if operator == "<":
        return semver_solver.ComparatorOp.LT
    return semver_solver.ComparatorOp.LE


def _parse_full_version(text: str) -> Optional[semver_solver.Version]:
    """Matches text against the strict SemVer 2.0.0 grammar, or returns None."""
    match = _SEMVER_PATTERN.match(text)
    if match is None:
        return None
    prerelease: Tuple[str, ...] = tuple(match.group(4).split(".")) if match.group(4) else ()
    build: Tuple[str, ...] = tuple(match.group(5).split(".")) if match.group(5) else ()
    return semver_solver.Version(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
        prerelease=prerelease,
        build=build,
    )


def _wildcard_bounds(text: str) -> Optional[Tuple[semver_solver.Version, Optional[semver_solver.Version]]]:
    """Expands a wildcard token into an inclusive lower bound and exclusive upper bound."""
    if text in _ANY_WILDCARD:
        return semver_solver.Version(0, 0, 0), None
    match = _WILDCARD_PATTERN.match(text)
    if match is None:
        return None
    major = int(match.group(1))
    minor_text = match.group(2)
    if minor_text is None:
        return semver_solver.Version(major, 0, 0), semver_solver.Version(major + 1, 0, 0)
    minor = int(minor_text)
    return semver_solver.Version(major, minor, 0), semver_solver.Version(major, minor + 1, 0)


def _caret_upper_bound(version: semver_solver.Version) -> semver_solver.Version:
    """Computes the exclusive upper bound of a caret range from its lower bound."""
    # Caret ranges permit changes to the left-most non-zero component.
    if version.major > 0:
        return semver_solver.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_solver.Version(0, version.minor + 1, 0)
    return semver_solver.Version(0, 0, version.patch + 1)


def _tokenize_clause(clause: str, raw_range: str) -> List[Tuple[Optional[str], str]]:
    """Splits a clause into (prefix operator, version token) pairs delimited by whitespace."""
    tokens: List[Tuple[Optional[str], str]] = []
    index = 0
    length = len(clause)
    while index < length:
        if clause[index].isspace():
            index += 1
            continue
        operator: Optional[str] = None
        for candidate in _OPERATORS:
            if clause.startswith(candidate, index):
                operator = candidate
                index += len(candidate)
                break
        # Optional whitespace between the operator and its target version.
        while index < length and clause[index].isspace():
            index += 1
        start = index
        while index < length and not clause[index].isspace():
            index += 1
        version_text = clause[start:index]
        if not version_text:
            raise semver_solver.InvalidRangeError(
                message="Range comparator is missing a target version",
                raw_range=raw_range,
            )
        tokens.append((operator, version_text))
    return tokens


def _expand_wildcard_token(
    operator: Optional[str],
    lower: semver_solver.Version,
    upper: Optional[semver_solver.Version],
) -> _RangeDnf:
    """Expands a wildcard comparator into disjunctive comparator inequalities."""
    if operator in (None, "=", "==", "^", "~"):
        # Bare/caret/tilde wildcards denote the inclusive band [lower, upper).
        if upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]]
    if operator == "!=":
        # A negated wildcard membership splits into two disjunctive clauses.
        if upper is None:
            return [[(semver_solver.ComparatorOp.LT, _MINIMUM_VERSION)]]
        return [[(semver_solver.ComparatorOp.LT, lower)], [(semver_solver.ComparatorOp.GE, upper)]]
    if operator == ">=":
        # Greater-than-or-equal starts at the band's inclusive lower boundary.
        return [[]] if upper is None else [[(semver_solver.ComparatorOp.GE, lower)]]
    if operator == ">":
        # Greater-than the whole band starts at its exclusive upper boundary.
        if upper is None:
            return [[(semver_solver.ComparatorOp.LT, _MINIMUM_VERSION)]]
        return [[(semver_solver.ComparatorOp.GE, upper)]]
    if operator == "<":
        # Less-than the whole band ends at its inclusive lower boundary.
        if upper is None:
            return [[(semver_solver.ComparatorOp.LT, _MINIMUM_VERSION)]]
        return [[(semver_solver.ComparatorOp.LT, lower)]]
    # Less-than-or-equal covers the whole band below its upper boundary.
    return [[]] if upper is None else [[(semver_solver.ComparatorOp.LT, upper)]]


def _expand_token(operator: Optional[str], version_text: str, raw_range: str) -> _RangeDnf:
    """Expands a single comparator token into disjunctive comparator inequalities."""
    bounds = _wildcard_bounds(version_text)
    if bounds is not None:
        return _expand_wildcard_token(operator, bounds[0], bounds[1])
    version = _parse_full_version(version_text)
    if version is None:
        # Reject bare partial versions lacking wildcard characters across any comparator.
        raise semver_solver.InvalidRangeError(
            message=f"Malformed version '{version_text}' in range expression",
            raw_range=raw_range,
        )
    if operator in (None, "=", "=="):
        return [[(semver_solver.ComparatorOp.EQ, version)]]
    if operator == "!=":
        return [[(semver_solver.ComparatorOp.NE, version)]]
    if operator == "^":
        return [[(semver_solver.ComparatorOp.GE, version), (semver_solver.ComparatorOp.LT, _caret_upper_bound(version))]]
    if operator == "~":
        return [[
            (semver_solver.ComparatorOp.GE, version),
            (semver_solver.ComparatorOp.LT, semver_solver.Version(version.major, version.minor + 1, 0)),
        ]]
    return [[(_ordering_operator(operator), version)]]


def _compile_hyphen_range(low_text: str, high_text: str, raw_range: str) -> _RangeDnf:
    """Compiles an inclusive lower and upper hyphen range endpoint pair."""
    constraints: List[_Comparator] = []
    low_bounds = _wildcard_bounds(low_text)
    if low_bounds is not None:
        constraints.append((semver_solver.ComparatorOp.GE, low_bounds[0]))
    else:
        low_version = _parse_full_version(low_text)
        if low_version is None:
            raise semver_solver.InvalidRangeError(
                message=f"Malformed hyphen range lower bound '{low_text}'",
                raw_range=raw_range,
            )
        constraints.append((semver_solver.ComparatorOp.GE, low_version))
    high_bounds = _wildcard_bounds(high_text)
    if high_bounds is not None:
        high_lower, high_upper = high_bounds
        if high_upper is not None:
            constraints.append((semver_solver.ComparatorOp.LT, high_upper))
        else:
            constraints.append((semver_solver.ComparatorOp.GE, high_lower))
    else:
        high_version = _parse_full_version(high_text)
        if high_version is None:
            raise semver_solver.InvalidRangeError(
                message=f"Malformed hyphen range upper bound '{high_text}'",
                raw_range=raw_range,
            )
        constraints.append((semver_solver.ComparatorOp.LE, high_version))
    return [constraints]


def _compile_clause(clause: str, raw_range: str) -> _RangeDnf:
    """Compiles a whitespace-delimited conjunction clause into disjunctive normal form."""
    hyphen = _HYPHEN_PATTERN.match(clause)
    if hyphen is not None:
        return _compile_hyphen_range(hyphen.group(1), hyphen.group(2), raw_range)
    alternatives: _RangeDnf = [[]]
    for operator, version_text in _tokenize_clause(clause, raw_range):
        expansions = _expand_token(operator, version_text, raw_range)
        combined: _RangeDnf = []
        for prefix in alternatives:
            for expansion in expansions:
                combined.append(prefix + expansion)
        alternatives = combined
    return alternatives


def _compile_range(text: str) -> _RangeDnf:
    """Compiles a range expression into disjunctive normal form comparator sets."""
    trimmed = text.strip()
    if not trimmed:
        raise semver_solver.InvalidRangeError(
            message="Version range expression must not be empty",
            raw_range=text,
        )
    if "," in trimmed:
        raise semver_solver.InvalidRangeError(
            message="Comma delimiters are not permitted in version ranges",
            raw_range=text,
        )
    alternatives: _RangeDnf = []
    for raw_clause in trimmed.split("||"):
        clause = raw_clause.strip()
        if not clause:
            raise semver_solver.InvalidRangeError(
                message="Version range contains an empty union clause",
                raw_range=text,
            )
        alternatives.extend(_compile_clause(clause, text))
    return alternatives


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # MUST parse valid SemVer 2.0.0 strings, and WHEN text violates the grammar
        # (including leading zeroes) MUST raise InvalidVersionError.
        version = _parse_full_version(text)
        if version is None:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version '{text}'",
                raw_text=text,
            )
        return version

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # MUST compare major, minor, and patch numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1
        # MUST rank normal versions higher than prerelease versions.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # MUST compare prerelease segments in order, ranking numeric below string.
        for left_segment, right_segment in zip(v1.prerelease, v2.prerelease):
            if left_segment == right_segment:
                continue
            left_numeric = left_segment.isdigit()
            right_numeric = right_segment.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left_segment) < int(right_segment) else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left_segment < right_segment else 1
        # MUST rank longer prerelease segment sequences higher when prefixes match.
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return 1 if len(v1.prerelease) > len(v2.prerelease) else -1
        # Build metadata is excluded entirely from precedence comparison.

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # MUST validate the trimmed range expression and store the trimmed text.
        _compile_range(text)
        return semver_solver.VersionRange(raw_text=text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Compiles the range expression into disjunctive normal form comparator sets.
        alternatives = _compile_range(range_constraint.raw_text)
        # WHEN version is a prerelease and include_prerelease is False, only ranges
        # explicitly targeting that prerelease (same major, minor, patch) match.
        gated = version.is_prerelease and not include_prerelease
        for clause in alternatives:
            clause_satisfied = True
            for operator, boundary in clause:
                comparison = self.compare_precedence(version, boundary)
                if operator is semver_solver.ComparatorOp.EQ:
                    matches = comparison == 0
                elif operator is semver_solver.ComparatorOp.NE:
                    matches = comparison != 0
                elif operator is semver_solver.ComparatorOp.LT:
                    matches = comparison < 0
                elif operator is semver_solver.ComparatorOp.LE:
                    matches = comparison <= 0
                elif operator is semver_solver.ComparatorOp.GT:
                    matches = comparison > 0
                else:
                    matches = comparison >= 0
                if not matches:
                    clause_satisfied = False
                    break
            if not clause_satisfied:
                continue
            if not gated:
                # Evaluates to True if version satisfies all comparators in a clause.
                return True
            for _, boundary in clause:
                if (
                    boundary.is_prerelease
                    and boundary.major == version.major
                    and boundary.minor == version.minor
                    and boundary.patch == version.patch
                ):
                    return True
        # Evaluates to False if all clauses fail satisfaction.
        return False


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Private backing storage mapping package names to registered releases.
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # MUST register the release and keep the list ordered by descending precedence.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_solver.VersionEngine)
        releases.sort(
            key=cmp_to_key(lambda left, right: engine.compare_precedence(left.version, right.version)),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # WHEN name is not registered, MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered",
                package_name=name,
            )
        # MUST yield a shallow copy ordered by descending version precedence.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # MUST evaluate to True exactly when the package name is registered.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # MUST produce the set of all registered package names.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to the ranges requested of it.
        accumulated_constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated_constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def candidate_releases(package: str) -> List[semver_solver.PackageRelease]:
            # Unregistered packages absent from the repository have zero candidates.
            if not repository.has_package(package):
                return []
            available = repository.get_releases(package)
            viable: List[semver_solver.PackageRelease] = []
            for release in available:
                if all(
                    engine.satisfies(release.version, range_constraint, False)
                    for _, range_constraint in accumulated_constraints[package]
                ):
                    viable.append(release)
            return viable

        def backtrack() -> bool:
            unassigned = [package for package in accumulated_constraints if package not in assignment]
            if not unassigned:
                return True

            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for package in unassigned:
                candidates_map[package] = candidate_releases(package)

            # MRV selection with lexical tie-breaking on package name.
            selected = min(unassigned, key=lambda package: (len(candidates_map[package]), package))
            candidates = candidates_map[selected]
            if not candidates:
                requesters = [source for source, _ in accumulated_constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False

            # Value ordering: explore candidates in descending version precedence.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # An already assigned package violating a new requirement conflicts.
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} "
                                f"{dependency.range_constraint.raw_text}, incompatible with "
                                f"{assignment[dependency.name].version}"
                            )
                            break
                    else:
                        constraint_entry: Tuple[str, semver_solver.VersionRange] = (
                            selected,
                            dependency.range_constraint,
                        )
                        accumulated_constraints.setdefault(dependency.name, []).append(constraint_entry)
                        newly_added.append((dependency.name, constraint_entry))

                if not conflict_detected and backtrack():
                    return True

                # Undo this assignment and every constraint it introduced.
                for package_name, constraint_entry in newly_added:
                    accumulated_constraints[package_name].remove(constraint_entry)
                    if not accumulated_constraints[package_name]:
                        del accumulated_constraints[package_name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        # WHEN dependencies are unsatisfiable or reference unregistered packages,
        # MUST raise ResolutionConflictError without allowing PackageNotFoundError to escape.
        if not backtrack():
            explanation = "\n".join(conflict_trail) if conflict_trail else "No compatible assignment exists"
            raise semver_solver.ResolutionConflictError(
                message=f"Unable to resolve dependencies: {explanation}",
                conflicting_packages=tuple(sorted(conflicting_packages)),
                explanation=explanation,
            )

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
# LAST_CLEANED: 2026-11-05T04:37:17Z
# LAST_CHANGED: 2026-11-05T04:30:57Z
# CHANGE: Correct wildcard ordering-comparator normalization in _expand_wildcard_token: bare/caret/tilde wildcards expand to the inclusive band [lower, upper), '>' now starts at the band's exclusive upper boundary (so >1.x compiles to >=2.0.0 and rejects 1.9.9/1.0.0), '<=' ends at the exclusive upper boundary, '>=' uses the inclusive lower boundary, '<' uses the lower boundary, and '!=' complements the band. Added the absolute minimum version for empty-band cases and made the any-version wildcard cover all versions.
# COVERAGE_AUDIT: 2026-11-05T04:34:27Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:37:17Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:37:04Z
# QA_AUDIT: 2026-11-05T04:34:12Z
# --- END AUTOFAB METADATA ---
