# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_015907_deepseek-flash_semver_solver
# Timestamp: 2026-11-08T01:59:07.273812+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 178,108
#   Cached Inbound Tokens:   8,903,552
#   Outbound Tokens:         151,059
#   Total Tokens:            9,232,719
#   Financial Cost ($USD):   $0.1441
#   Wall Clock Duration:     951.72s
#   Step Latencies (s):      [214.0, 389.2, 10.1, 177.1, 42.7, 152.7, 10.0, 85.4, 40.7, 83.6, 10.1, 20.3]
#   Role Execution Rounds:   coverage: 3, lib: 3, qa: 3, test: 3 (Total: 12)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       47
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum

from support.lib.framework import data_type, operation, poly_type

# Requirements specified in semver_solver.pyi

@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __post_init__(self) -> None:
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
        # A version is a pre-release exactly when it carries pre-release identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Canonical SemVer 2.0.0 rendering: numeric triple, then optional
        # '-'-prefixed pre-release identifiers, then optional '+'-prefixed build metadata.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
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
    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
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
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T02:05:41Z
# LAST_CHANGED: 2026-11-08T02:05:41Z
# CHANGE: Implement interface module: non-frozen dataclass exceptions with __str__/__post_init__, frozen @data_type Version/VersionRange/PackageDependency/PackageRelease/ResolutionOutcome with is_prerelease/format/__str__, ComparatorOp enum, and @poly_type VersionEngine/PackageRepository/DependencySolver protocols with operation stubs matching low/semver_solver.pyi
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, NamedTuple, Optional, Sequence, Set, Tuple
import re
from functools import cmp_to_key

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

# Matches the official SemVer 2.0.0 grammar: numeric components without leading
# zeroes, optional dot-separated pre-release identifiers (numeric identifiers
# without leading zeroes), and optional dot-separated build metadata identifiers.
_VERSION_RE = re.compile(
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)

_NUMERIC_IDENTIFIER_RE = re.compile(r"0|[1-9][0-9]*")
_ALPHANUMERIC_IDENTIFIER_RE = re.compile(r"[0-9a-zA-Z-]+")

# Operators may be separated from their target by optional whitespace; targets
# never contain whitespace, so comparators inside a clause are whitespace-delimited.
_TOKEN_RE = re.compile(r"\s*(==|!=|<=|>=|=|<|>|\^|~)?\s*([^\s]+)")

# A hyphen range connector is a '-' delimited by whitespace on both sides.
_HYPHEN_SEPARATOR_RE = re.compile(r"\s+-\s+")

_WILDCARD_TOKENS: FrozenSet[str] = frozenset({"x", "X", "*"})

_MAX_VERSION_COMPONENTS = 3

# An alternative is a conjunction of comparator/version pairs; a constraint is a
# disjunction of alternatives; a clause is a conjunction of constraints; a range
# is a disjunction of clauses (disjunctive normal form). An empty alternative
# list denotes an unsatisfiable constraint, while a single empty alternative
# denotes an unconstrained one.
_Alternative = List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]
_Constraint = List[_Alternative]
_Clause = List[_Constraint]
_Range = List[_Clause]


def _compare_precedence(v1: semver_solver.Version, v2: semver_solver.Version) -> int:
    """Orders versions by SemVer 2.0.0 precedence, ignoring build metadata."""
    # Major, minor, and patch are compared numerically in sequence.
    if v1.major != v2.major:
        return -1 if v1.major < v2.major else 1
    if v1.minor != v2.minor:
        return -1 if v1.minor < v2.minor else 1
    if v1.patch != v2.patch:
        return -1 if v1.patch < v2.patch else 1

    # A normal version ranks higher than any pre-release sharing the same triple.
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1

    # Pre-release segments compare position by position; numeric segments compare
    # as integers, string segments compare ASCII-lexicographically, and numeric
    # segments always rank below string segments.
    for left, right in zip(v1.prerelease, v2.prerelease):
        left_numeric = left.isdigit()
        right_numeric = right.isdigit()
        if left_numeric and right_numeric:
            left_value = int(left)
            right_value = int(right)
            if left_value != right_value:
                return -1 if left_value < right_value else 1
        elif left_numeric:
            return -1
        elif right_numeric:
            return 1
        elif left != right:
            return -1 if left < right else 1

    # A longer pre-release segment sequence ranks higher when the common prefix matches.
    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
    return 0


class _VersionPattern(NamedTuple):
    """Parsed version or wildcard expression used to expand range comparators."""

    components: Tuple[Optional[int], ...]
    prerelease: Tuple[str, ...]
    build: Tuple[str, ...]


def _parse_pattern(text: str) -> Optional[_VersionPattern]:
    """Parses a full version or wildcard expression, rejecting bare partial versions."""
    core = text
    build: Tuple[str, ...] = ()
    if "+" in core:
        core, build_text = core.split("+", 1)
        build_ids = build_text.split(".")
        if not build_text or not all(_ALPHANUMERIC_IDENTIFIER_RE.fullmatch(part) for part in build_ids):
            return None
        build = tuple(build_ids)

    prerelease: Tuple[str, ...] = ()
    if "-" in core:
        core, prerelease_text = core.split("-", 1)
        if not prerelease_text:
            return None
        prerelease_ids = prerelease_text.split(".")
        for identifier in prerelease_ids:
            if not _ALPHANUMERIC_IDENTIFIER_RE.fullmatch(identifier):
                return None
            # Numeric pre-release identifiers must not contain leading zeroes.
            if identifier.isdigit() and len(identifier) > 1 and identifier[0] == "0":
                return None
        prerelease = tuple(prerelease_ids)

    component_texts = core.split(".")
    if not component_texts or len(component_texts) > _MAX_VERSION_COMPONENTS:
        return None

    components: List[Optional[int]] = []
    wildcard_seen = False
    for token in component_texts:
        if token in _WILDCARD_TOKENS:
            wildcard_seen = True
            components.append(None)
            continue
        # Numeric components after a wildcard are malformed.
        if wildcard_seen:
            return None
        # Numeric components must be non-negative integers without leading zeroes.
        if not _NUMERIC_IDENTIFIER_RE.fullmatch(token):
            return None
        components.append(int(token))

    # Bare partial versions lacking wildcard characters are prohibited.
    if not wildcard_seen and len(components) != _MAX_VERSION_COMPONENTS:
        return None
    return _VersionPattern(tuple(components), prerelease, build)


def _known_components(pattern: _VersionPattern) -> List[int]:
    """Returns the leading numeric components preceding the first wildcard."""
    known: List[int] = []
    for component in pattern.components:
        if component is None:
            break
        known.append(component)
    return known


def _is_full_version(pattern: _VersionPattern) -> bool:
    """Indicates whether the pattern is a complete major.minor.patch version."""
    return len(pattern.components) == _MAX_VERSION_COMPONENTS and all(
        component is not None for component in pattern.components
    )


def _lower_version(pattern: _VersionPattern) -> semver_solver.Version:
    """Builds the inclusive lower bound of a pattern, zero-filling omitted components."""
    known = _known_components(pattern)
    major = known[0] if len(known) > 0 else 0
    minor = known[1] if len(known) > 1 else 0
    patch = known[2] if len(known) > 2 else 0
    return semver_solver.Version(major, minor, patch, pattern.prerelease)


def _next_boundary(pattern: _VersionPattern) -> Optional[semver_solver.Version]:
    """Builds the exclusive upper boundary just above a wildcard pattern."""
    known = _known_components(pattern)
    if not known:
        return None
    if len(known) == 1:
        return semver_solver.Version(known[0] + 1, 0, 0)
    if len(known) == 2:
        return semver_solver.Version(known[0], known[1] + 1, 0)
    return semver_solver.Version(known[0], known[1], known[2] + 1)


def _caret_upper(pattern: _VersionPattern) -> Optional[semver_solver.Version]:
    """Computes the caret upper boundary from the first non-zero component."""
    known = _known_components(pattern)
    if not known:
        return None
    if known[0] > 0:
        return semver_solver.Version(known[0] + 1, 0, 0)
    if len(known) >= 2 and known[1] > 0:
        return semver_solver.Version(0, known[1] + 1, 0)
    if len(known) >= 3:
        return semver_solver.Version(0, 0, known[2] + 1)
    if len(known) == 2:
        return semver_solver.Version(0, known[1] + 1, 0)
    return semver_solver.Version(known[0] + 1, 0, 0)


def _tilde_upper(pattern: _VersionPattern) -> Optional[semver_solver.Version]:
    """Computes the tilde upper boundary at the minor (or major) level."""
    known = _known_components(pattern)
    if not known:
        return None
    if len(known) >= 2:
        return semver_solver.Version(known[0], known[1] + 1, 0)
    return semver_solver.Version(known[0] + 1, 0, 0)


def _expand_operator(operator: Optional[str], pattern: _VersionPattern) -> _Constraint:
    """Expands one comparator into a disjunction of comparator conjunctions."""
    lower = _lower_version(pattern)
    boundary = _next_boundary(pattern)
    full = _is_full_version(pattern)
    eq = semver_solver.ComparatorOp.EQ
    ne = semver_solver.ComparatorOp.NE
    lt = semver_solver.ComparatorOp.LT
    ge = semver_solver.ComparatorOp.GE

    if operator is None or operator == "==":
        if full:
            return [[(eq, lower)]]
        if boundary is None:
            return [[]]
        # '==1.x' expands to the half-open interval [1.0.0, 2.0.0).
        return [[(ge, lower), (lt, boundary)]]

    if operator == "!=":
        if full:
            return [[(ne, lower)]]
        if boundary is None:
            return []
        # '!=1.x' expands to '<1.0.0 || >=2.0.0'.
        return [[(lt, lower)], [(ge, boundary)]]

    if operator == "<":
        if boundary is None:
            return []
        # '<1.x' expands to '<1.0.0'.
        return [[(lt, lower)]]

    if operator == "<=":
        if boundary is None:
            return [[]]
        # '<=1.x' expands to '<2.0.0'.
        return [[(lt, boundary)]]

    if operator == ">":
        if boundary is None:
            return []
        # '>1.x' expands to '>=2.0.0'.
        return [[(ge, boundary)]]

    if operator == ">=":
        if boundary is None:
            # '>=*' is satisfied by all versions.
            return [[]]
        # '>=1.x' expands to '>=1.0.0'.
        return [[(ge, lower)]]

    if operator == "^":
        upper = _caret_upper(pattern)
        if upper is None:
            return [[]]
        return [[(ge, lower), (lt, upper)]]

    if operator == "~":
        upper = _tilde_upper(pattern)
        if upper is None:
            return [[]]
        return [[(ge, lower), (lt, upper)]]

    return []  # unreachable (assumption: operator is restricted by the range clause grammar)


def _compile_clause(clause: str, raw_range: str) -> _Clause:
    """Compiles one whitespace-delimited clause into accumulated constraints."""
    hyphen_parts = _HYPHEN_SEPARATOR_RE.split(clause)
    if len(hyphen_parts) > 2:
        raise semver_solver.InvalidRangeError(
            message=f"hyphen range may bind only two versions: {clause!r}",
            raw_range=raw_range,
        )
    if len(hyphen_parts) == 2:
        lower_pattern = _parse_pattern(hyphen_parts[0].strip())
        upper_pattern = _parse_pattern(hyphen_parts[1].strip())
        if lower_pattern is None or upper_pattern is None:
            raise semver_solver.InvalidRangeError(
                message=f"hyphen range bound is not a full version or wildcard: {clause!r}",
                raw_range=raw_range,
            )
        # '1.0.0 - 2.x' expands to '>=1.0.0 <3.0.0'.
        ge = semver_solver.ComparatorOp.GE
        le = semver_solver.ComparatorOp.LE
        lt = semver_solver.ComparatorOp.LT
        clause_constraints: _Clause = [[[(ge, _lower_version(lower_pattern))]]]
        if _is_full_version(upper_pattern):
            clause_constraints.append([[(le, _lower_version(upper_pattern))]])
        else:
            upper_boundary = _next_boundary(upper_pattern)
            if upper_boundary is not None:
                clause_constraints.append([[(lt, upper_boundary)]])
        return clause_constraints

    constraints: _Clause = []
    position = 0
    while position < len(clause):
        match = _TOKEN_RE.match(clause, position)
        if match is None:
            raise semver_solver.InvalidRangeError(
                message=f"malformed range clause: {clause!r}",
                raw_range=raw_range,
            )
        operator_text = match.group(1)
        target_text = match.group(2)
        pattern = _parse_pattern(target_text)
        if pattern is None:
            raise semver_solver.InvalidRangeError(
                message=f"bare or malformed version expression in range clause: {target_text!r}",
                raw_range=raw_range,
            )
        operator = "==" if operator_text == "=" else operator_text
        constraints.append(_expand_operator(operator, pattern))
        position = match.end()
    return constraints


def _compile_range(text: str) -> _Range:
    """Compiles a range expression into disjunctive normal form comparator sets."""
    stripped = text.strip()
    if not stripped:
        raise semver_solver.InvalidRangeError(
            message="range expression is empty",
            raw_range=text,
        )
    # Commas are not permitted as comparator delimiters.
    if "," in stripped:
        raise semver_solver.InvalidRangeError(
            message="range expression must not use commas as comparator delimiters",
            raw_range=text,
        )
    ranges: _Range = []
    for raw_clause in stripped.split("||"):
        clause_text = raw_clause.strip()
        if not clause_text:
            raise semver_solver.InvalidRangeError(
                message="range expression contains an empty union clause",
                raw_range=text,
            )
        ranges.append(_compile_clause(clause_text, text))
    return ranges


def _evaluate_comparator(
    operator: semver_solver.ComparatorOp,
    boundary: semver_solver.Version,
    version: semver_solver.Version,
) -> bool:
    """Evaluates a single comparator boundary against a candidate version."""
    comparison = _compare_precedence(version, boundary)
    if operator is semver_solver.ComparatorOp.EQ:
        return comparison == 0
    if operator is semver_solver.ComparatorOp.NE:
        return comparison != 0
    if operator is semver_solver.ComparatorOp.LT:
        return comparison < 0
    if operator is semver_solver.ComparatorOp.LE:
        return comparison <= 0
    # Greater-than comparisons are normalized to the next GE boundary during range
    # compilation, so GE is the only operator remaining at this point.
    return comparison >= 0


def _clause_matches(clause: _Clause, version: semver_solver.Version) -> bool:
    """Evaluates whether a candidate satisfies all comparators of one clause."""
    combinations: List[_Alternative] = [[]]
    for constraint in clause:
        if not constraint:
            # An unsatisfiable comparator makes the whole clause unsatisfiable.
            return False
        expanded: List[_Alternative] = []
        for combination in combinations:
            for alternative in constraint:
                expanded.append(combination + alternative)
        combinations = expanded
    for combination in combinations:
        if all(
            _evaluate_comparator(operator, boundary, version)
            for operator, boundary in combination
        ):
            return True
    return False


def _range_targets_prerelease(ranges: _Range, version: semver_solver.Version) -> bool:
    """Indicates whether the range explicitly targets the candidate pre-release triple."""
    for clause in ranges:
        for constraint in clause:
            for alternative in constraint:
                for _operator, boundary in alternative:
                    if not boundary.prerelease:
                        continue
                    if (
                        boundary.major == version.major
                        and boundary.minor == version.minor
                        and boundary.patch == version.patch
                    ):
                        return True
    return False


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        match = _VERSION_RE.fullmatch(text)
        if match is None:
            # Grammar violations and leading zeroes surface as InvalidVersionError.
            raise semver_solver.InvalidVersionError(
                message=f"{text!r} is not a valid SemVer 2.0.0 version string",
                raw_text=text,
            )
        prerelease = tuple(match.group(4).split(".")) if match.group(4) is not None else ()
        build = tuple(match.group(5).split(".")) if match.group(5) is not None else ()
        return semver_solver.Version(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            prerelease,
            build,
        )

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        return _compare_precedence(v1, v2)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # Full grammar validation; malformed input raises InvalidRangeError.
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
        """Evaluates whether a semantic version satisfies a range constraint."""
        ranges = _compile_range(range_constraint.raw_text)
        # The candidate must satisfy all comparators of at least one clause.
        if not any(_clause_matches(clause, version) for clause in ranges):
            return False
        if not include_prerelease and version.is_prerelease:
            # Pre-releases are filtered out unless the range explicitly targets
            # a pre-release identifier for the same major/minor/patch triple.
            return _range_targets_prerelease(ranges, version)
        return True


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Private backing storage mapping package names to descending release lists.
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # Keep every package bucket ordered by descending version precedence.
        releases.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(left.version, right.version)
            ),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        releases = self._packages.get(name)
        if releases is None:
            raise semver_solver.PackageNotFoundError(
                message=f"package {name!r} is not registered in the repository",
                package_name=name,
            )
        # Shallow copy protects the internal ordering from caller mutation.
        return list(releases)

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names."""
        return set(self._packages)


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
        """Computes a mutually compatible version assignment for root dependencies."""
        # Collaborator singletons are resolved on demand.
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to the requirements requesting it.
        accumulated_constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated_constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        # Partial assignment of package names to concrete releases.
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            unassigned = [name for name in accumulated_constraints if name not in assignment]
            if not unassigned:
                return True

            # Minimum Remaining Values heuristic: viable candidates per package.
            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for name in unassigned:
                constraints = accumulated_constraints[name]
                try:
                    available = repository.get_releases(name)
                except semver_solver.PackageNotFoundError:
                    # Unregistered packages evaluate to zero candidate releases;
                    # PackageNotFoundError must never escape resolve().
                    available = []
                candidates_map[name] = [
                    release
                    for release in available
                    if all(
                        engine.satisfies(release.version, constraint, False)
                        for _source, constraint in constraints
                    )
                ]

            # Fewest candidates first, with lexical tie-breaking.
            selected = min(
                unassigned,
                key=lambda candidate_name: (len(candidates_map[candidate_name]), candidate_name),
            )
            candidates = candidates_map[selected]

            if not candidates:
                requesters = tuple(
                    source for source, _constraint in accumulated_constraints[selected]
                )
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for {selected!r} satisfying constraints from {requesters!r}"
                )
                return False

            # Value ordering: descending precedence candidates from the repository.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign {selected!r} to {candidate.version.format()}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                # Forward checking of the candidate's declared dependencies.
                for dependency in candidate.dependencies:
                    assigned = assignment.get(dependency.name)
                    if assigned is not None:
                        if not engine.satisfies(
                            assigned.version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: {selected!r} requires {dependency.name} "
                                f"{dependency.range_constraint.raw_text!r}"
                            )
                            break
                    else:
                        constraint_entry = (selected, dependency.range_constraint)
                        accumulated_constraints.setdefault(dependency.name, []).append(
                            constraint_entry
                        )
                        newly_added.append((dependency.name, constraint_entry))

                if not conflict_detected and backtrack():
                    return True

                # Undo the assignment and every constraint introduced by this branch.
                for name, constraint_entry in newly_added:
                    accumulated_constraints[name].remove(constraint_entry)
                    if not accumulated_constraints[name]:
                        del accumulated_constraints[name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if not backtrack():
            raise semver_solver.ResolutionConflictError(
                message=f"dependency resolution failed with {len(conflict_trail)} conflict(s)",
                conflicting_packages=tuple(sorted(conflicting_packages)),
                explanation="; ".join(conflict_trail),
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
# LAST_CLEANED: 2026-11-08T02:14:45Z
# LAST_CHANGED: 2026-11-08T02:14:09Z
# CHANGE: Address feedback (2 items): (1) pruned the structurally unreachable GT comparator evaluation branch in _evaluate_comparator together with the unused GT alias (and the equally unused LE alias) in _expand_operator, since greater-than comparators normalize to the next GE boundary during range compilation and hyphen-range full upper bounds are the sole LE producer, leaving GE as the final fallthrough with a comment documenting the normalization; (2) moved the exclusion annotation onto the return statement line itself: 'return []  # unreachable (assumption: operator is restricted by the range clause grammar)', so the fallback is properly excluded while preserving the declared non-Optional return type
# COVERAGE_AUDIT: 2026-11-08T02:14:45Z
# QA_AUDIT: 2026-11-08T02:14:32Z
# --- END AUTOFAB METADATA ---
