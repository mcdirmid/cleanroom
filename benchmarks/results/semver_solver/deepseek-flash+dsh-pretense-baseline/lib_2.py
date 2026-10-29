# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_044829_deepseek-flash_semver_solver_pretense_baseline
# Timestamp: 2026-10-29T04:48:29.958061+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 62,739
#   Cached Inbound Tokens:   5,199,232
#   Outbound Tokens:         102,226
#   Total Tokens:            5,364,197
#   Financial Cost ($USD):   $0.0863
#   Wall Clock Duration:     687.30s
#   Step Latencies (s):      [678.6]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
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
"""Interface specification for SemVer 2.0 parsing, range algebra, and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error. Verification suites MUST NOT assert on specific wording or prefixes within message, and MUST assert on exception types and structured attributes.
    """

    message: str

    def __str__(self) -> str:
        """Returns the human-readable diagnostic message."""
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

        POSTCONDITIONS:
        - MUST parse valid SemVer 2.0.0 strings into Version records with major, minor, patch, prerelease, and build tuples.
        - WHEN text contains leading zeroes in numeric identifiers or violates grammar, MUST raise InvalidVersionError.
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

        POSTCONDITIONS:
        - MUST evaluate to a negative integer when v1 < v2, zero when v1 == v2, and a positive integer when v1 > v2 under SemVer 2.0.0 RFC rules.
        - MUST compare major, minor, and patch numerically.
        - MUST rank normal versions higher than prerelease versions sharing identical major, minor, and patch numbers.
        - MUST compare prerelease segments numerically when both numeric, ASCII-lexicographically when string, and rank numeric below string.
        - MUST ignore build metadata entirely when comparing precedence.
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

        POSTCONDITIONS:
        - MUST parse range expression text supporting basic comparators (==, =, !=, <, <=, >, >=), caret ranges (^), tilde ranges (~), wildcards (*, x, X, M.x, M.*, M.m.x, M.m.*), hyphen ranges (M1.m1.p1 - M2.m2.p2), and unions (||).
        - MUST trim surrounding whitespace around range expressions and individual clauses, storing the trimmed range expression in raw_text.
        - MUST accept optional whitespace between relational/prefix operators and target versions or wildcards (e.g. '>= 1.0.0' is equivalent to '>=1.0.0').
        - MUST delimit comparators within clauses strictly by whitespace; commas are not permitted.
        - WHEN text supplies bare partial versions lacking wildcard characters across any comparator or hyphen expression (such as '1', '1.2', '^0.0', or '1.2 - 2.3'), MUST raise InvalidRangeError.
        - WHEN text is empty, contains only whitespace, contains empty union clauses, uses comma delimiters, or violates range syntax, MUST raise InvalidRangeError.
        """
        ...

    @operation
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint.

        Args:
            version: Candidate semantic version to test.
            range_constraint: Version range to evaluate against.
            include_prerelease: Whether to allow pre-release versions to match non-prerelease ranges.

        Returns:
            True if the version satisfies the range, False otherwise.

        POSTCONDITIONS:
        - MUST evaluate to True when version satisfies range_constraint, and False otherwise.
        - WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False unless range explicitly targets that prerelease by specifying a prerelease identifier sharing the same major, minor, and patch numbers.
        - WHEN include_prerelease is True, MUST evaluate candidate prerelease version directly against comparator boundary inequalities using precedence ordering without shifting numerical boundaries (e.g. 1.0.0-alpha ranks strictly lower than 1.0.0 and does not satisfy >=1.0.0).
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

        POSTCONDITIONS:
        - MUST register the package release into the repository.
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

        POSTCONDITIONS:
        - MUST yield all registered releases for package name ordered by version precedence descending.
        - WHEN name is not registered, MUST raise PackageNotFoundError.
        """
        ...

    @operation
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository.

        Args:
            name: Package name to check.

        Returns:
            True if the package exists, False otherwise.

        POSTCONDITIONS:
        - MUST evaluate to True when package name exists in repository, and False otherwise.
        """
        ...

    @operation
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names.

        Returns:
            Set of registered package name strings.

        POSTCONDITIONS:
        - MUST produce the set of all registered package names.
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

        POSTCONDITIONS:
        - MUST compute a mutually compatible set of package releases satisfying root and transitive dependencies.
        - MUST select the highest precedence compatible version for each package.
        - WHEN dependencies are unsatisfiable or reference unregistered packages absent from repository, MUST raise ResolutionConflictError detailing conflicting packages and derivation explanation without allowing PackageNotFoundError to escape.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T04:59:56Z
# LAST_CHANGED: 2026-10-29T04:59:56Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 01f011321caf
# COVERAGE_AUDIT: 2026-10-29T04:59:56Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T04:59:56Z
# PRETENSE_QA_AUDIT: 2026-10-29T04:59:56Z
# QA_AUDIT: 2026-10-29T04:59:56Z
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete realization of SemVer 2.0 parsing, precedence, range algebra, and dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver
from .semver_solver import (
    ComparatorOp,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionRange,
)


_VERSION_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

_MAJOR_WILDCARD_PATTERN = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<wildcard>[*xX])$")
_MINOR_WILDCARD_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<wildcard>[*xX])$"
)

_ALL_WILDCARDS = frozenset({"*", "x", "X"})

# Longest operators are matched first so that '<=' is not read as '<' plus '=...'.
_COMPARATOR_PREFIXES: Tuple[Tuple[str, ComparatorOp], ...] = (
    ("==", ComparatorOp.EQ),
    ("!=", ComparatorOp.NE),
    ("<=", ComparatorOp.LE),
    (">=", ComparatorOp.GE),
    ("=", ComparatorOp.EQ),
    ("<", ComparatorOp.LT),
    (">", ComparatorOp.GT),
)

_PREFIX_OPERATORS = frozenset(
    {"==", "!=", "<=", ">=", "=", "<", ">", "^", "~"}
)

_CARET = "^"
_TILDE = "~"
_HYPHEN = "-"


def _match_version(text: str) -> Optional[Version]:
    """Matches text against the SemVer 2.0.0 grammar, returning a Version or None."""
    match = _VERSION_PATTERN.match(text)
    if match is None:
        return None
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build = tuple(build_text.split(".")) if build_text else ()
    return Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
        build,
    )


def _expand_caret(version: Version) -> List[Tuple[ComparatorOp, Version]]:
    """Expands a caret prefix into lower and compatible upper bounds."""
    if version.major > 0:
        upper = Version(version.major + 1, 0, 0)
    elif version.minor > 0:
        upper = Version(0, version.minor + 1, 0)
    else:
        upper = Version(0, 0, version.patch + 1)
    return [(ComparatorOp.GE, version), (ComparatorOp.LT, upper)]


def _expand_tilde(version: Version) -> List[Tuple[ComparatorOp, Version]]:
    """Expands a tilde prefix into lower and minor upper bounds."""
    upper = Version(version.major, version.minor + 1, 0)
    return [(ComparatorOp.GE, version), (ComparatorOp.LT, upper)]


def _expand_hyphen(
    tokens: List[str], raw_range: str
) -> List[Tuple[ComparatorOp, Version]]:
    """Expands a hyphen range clause into inclusive lower and upper bounds."""
    if len(tokens) != 3:
        raise InvalidRangeError(
            f"Malformed hyphen range expression: {raw_range}", raw_range
        )
    lower = _match_version(tokens[0])
    upper = _match_version(tokens[2])
    if lower is None or upper is None:
        raise InvalidRangeError(
            f"Hyphen range endpoints must be complete versions: {raw_range}", raw_range
        )
    return [(ComparatorOp.GE, lower), (ComparatorOp.LE, upper)]


def _expand_wildcard(token: str) -> Optional[List[Tuple[ComparatorOp, Version]]]:
    """Expands a wildcard token into numeric bounds, or None when it is not a wildcard."""
    if token in _ALL_WILDCARDS:
        return []
    major_match = _MAJOR_WILDCARD_PATTERN.match(token)
    if major_match is not None:
        major = int(major_match.group("major"))
        return [
            (ComparatorOp.GE, Version(major, 0, 0)),
            (ComparatorOp.LT, Version(major + 1, 0, 0)),
        ]
    minor_match = _MINOR_WILDCARD_PATTERN.match(token)
    if minor_match is not None:
        major = int(minor_match.group("major"))
        minor = int(minor_match.group("minor"))
        return [
            (ComparatorOp.GE, Version(major, minor, 0)),
            (ComparatorOp.LT, Version(major, minor + 1, 0)),
        ]
    return None


def _expand_token(
    token: str, raw_range: str
) -> List[Tuple[ComparatorOp, Version]]:
    """Expands a single clause token into primitive comparator constraints."""
    wildcard = _expand_wildcard(token)
    if wildcard is not None:
        return wildcard
    if token.startswith(_CARET):
        operand = _match_version(token[len(_CARET):])
        if operand is None:
            raise InvalidRangeError(
                f"Malformed caret range expression: {raw_range}", raw_range
            )
        return _expand_caret(operand)
    if token.startswith(_TILDE):
        operand = _match_version(token[len(_TILDE):])
        if operand is None:
            raise InvalidRangeError(
                f"Malformed tilde range expression: {raw_range}", raw_range
            )
        return _expand_tilde(operand)
    for prefix, op in _COMPARATOR_PREFIXES:
        if token.startswith(prefix):
            operand = _match_version(token[len(prefix):])
            if operand is None:
                raise InvalidRangeError(
                    f"Malformed comparator expression: {raw_range}", raw_range
                )
            return [(op, operand)]
    operand = _match_version(token)
    if operand is None:
        raise InvalidRangeError(
            f"Malformed version range expression: {raw_range}", raw_range
        )
    return [(ComparatorOp.EQ, operand)]


def _parse_clause(
    clause_text: str, raw_range: str
) -> List[Tuple[ComparatorOp, Version]]:
    """Parses a single whitespace-delimited union clause into comparators."""
    tokens = clause_text.split()
    if _HYPHEN in tokens:
        return _expand_hyphen(tokens, raw_range)
    comparators: List[Tuple[ComparatorOp, Version]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _PREFIX_OPERATORS:
            if index + 1 >= len(tokens):
                raise InvalidRangeError(
                    f"Comparator operator lacks an operand: {raw_range}", raw_range
                )
            token = token + tokens[index + 1]
            index += 2
        else:
            index += 1
        comparators.extend(_expand_token(token, raw_range))
    return comparators


def _parse_range_clauses(text: str) -> List[List[Tuple[ComparatorOp, Version]]]:
    """Parses range text into a disjunctive normal form of comparator clauses."""
    trimmed = text.strip()
    if not trimmed:
        raise InvalidRangeError("Version range must not be empty", text)
    if "," in trimmed:
        raise InvalidRangeError("Commas are not permitted in version ranges", text)
    clauses: List[List[Tuple[ComparatorOp, Version]]] = []
    for raw_clause in trimmed.split("||"):
        clause_text = raw_clause.strip()
        if not clause_text:
            raise InvalidRangeError(
                "Version range contains an empty union clause", text
            )
        clauses.append(_parse_clause(clause_text, text))
    return clauses


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # POSTCONDITIONS: valid grammar yields a Version; violations raise InvalidVersionError.
        version = _match_version(text)
        if version is None:
            raise InvalidVersionError(f"Invalid semantic version: {text}", text)
        return version

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        # POSTCONDITIONS: compare numeric components in sequence.
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1
        # POSTCONDITIONS: a normal version ranks above a pre-release sharing numeric components.
        left = v1.prerelease
        right = v2.prerelease
        if not left and not right:
            return 0
        if not left:
            return 1
        if not right:
            return -1
        for left_segment, right_segment in zip(left, right):
            if left_segment == right_segment:
                continue
            left_numeric = left_segment.isdigit()
            right_numeric = right_segment.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left_segment) < int(right_segment) else 1
            # POSTCONDITIONS: numeric pre-release segments rank below string segments.
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left_segment < right_segment else 1
        # POSTCONDITIONS: a longer pre-release sequence ranks higher on a shared prefix.
        if len(left) == len(right):
            return 0
        return 1 if len(left) > len(right) else -1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # POSTCONDITIONS: validate the range algebra and store the trimmed expression.
        _parse_range_clauses(text)
        return VersionRange(text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        clauses = _parse_range_clauses(range_constraint.raw_text)
        for clause in clauses:
            # POSTCONDITIONS: pre-releases match only ranges targeting their numeric triple.
            if version.is_prerelease and not include_prerelease:
                targets_prerelease = any(
                    bound.is_prerelease
                    and (bound.major, bound.minor, bound.patch)
                    == (version.major, version.minor, version.patch)
                    for _, bound in clause
                )
                if not targets_prerelease:
                    continue
            if all(
                self._matches_comparator(version, op, bound) for op, bound in clause
            ):
                return True
        return False

    def _matches_comparator(
        self, version: semver_solver.Version, op: ComparatorOp, bound: semver_solver.Version
    ) -> bool:
        """Tests a candidate version against one primitive comparator."""
        order = self.compare_precedence(version, bound)
        if op is ComparatorOp.EQ:
            return order == 0
        if op is ComparatorOp.NE:
            return order != 0
        if op is ComparatorOp.LT:
            return order < 0
        if op is ComparatorOp.LE:
            return order <= 0
        if op is ComparatorOp.GT:
            return order > 0
        return order >= 0


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        # POSTCONDITIONS: register the release and keep its history precedence-descending.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_solver.VersionEngine)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(
                    right.version, left.version
                )
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        # POSTCONDITIONS: unknown names raise PackageNotFoundError.
        if name not in self._packages:
            raise PackageNotFoundError(f"Package not found: {name}", name)
        return list(self._packages[name])

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
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)
        accumulated: Dict[str, List[Tuple[str, VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            # MRV: choose the constrained package with the fewest viable candidates.
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True
            candidate_map: Dict[str, List[PackageRelease]] = {}
            for package in unassigned:
                # POSTCONDITIONS: unregistered packages have zero candidates.
                available = (
                    repository.get_releases(package)
                    if repository.has_package(package)
                    else []
                )
                candidate_map[package] = [
                    release
                    for release in available
                    if all(
                        engine.satisfies(release.version, constraint)
                        for _, constraint in accumulated[package]
                    )
                ]
            selected = min(
                unassigned, key=lambda package: (len(candidate_map[package]), package)
            )
            candidates = candidate_map[selected]
            if not candidates:
                requesters = sorted(
                    {source for source, _ in accumulated[selected]}
                )
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # Value ordering: explore highest precedence first, then backtrack on conflict.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(
                    f"Assign '{selected}' to {candidate.version}"
                )
                conflict = False
                newly_added: List[Tuple[str, Tuple[str, VersionRange]]] = []
                for dependency in candidate.dependencies:
                    # Forward checking against already assigned packages.
                    if dependency.name in assignment:
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                        ):
                            conflict = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires "
                                f"{dependency.name} {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict and backtrack():
                    return True
                # Undo the candidate's assignment and any newly introduced constraints.
                for package_name, entry in newly_added:
                    accumulated[package_name].remove(entry)
                    if not accumulated[package_name]:
                        del accumulated[package_name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not backtrack():
            # POSTCONDITIONS: unsatisfiable searches raise ResolutionConflictError.
            raise ResolutionConflictError(
                "Unable to resolve dependencies: " + "; ".join(conflict_trail),
                tuple(sorted(conflicting_packages)),
                "\n".join(conflict_trail),
            )
        selected_versions = {
            name: release.version for name, release in assignment.items()
        }
        return ResolutionOutcome(selected_versions, tuple(derivation_steps))


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_solver.VersionEngine],
        tier=VersionEngine.tier,
    )
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, semver_solver.PackageRepository],
        tier=PackageRepository.tier,
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, semver_solver.DependencySolver],
        tier=DependencySolver.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T04:59:56Z
# LAST_CHANGED: 2026-10-29T04:59:56Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: c29927784b35
# COVERAGE_AUDIT: 2026-10-29T04:59:56Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T04:59:56Z
# PRETENSE_QA_AUDIT: 2026-10-29T04:59:56Z
# QA_AUDIT: 2026-10-29T04:59:56Z
# --- END CLEANROOM METADATA ---
