# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261107_032140_deepseek-flash_semver_solver
# Timestamp: 2026-11-07T03:21:40.243991+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 162,429
#   Cached Inbound Tokens:   7,325,440
#   Outbound Tokens:         137,574
#   Total Tokens:            7,625,443
#   Financial Cost ($USD):   $0.1289
#   Wall Clock Duration:     837.14s
#   Step Latencies (s):      [173.0, 358.0, 20.2, 154.4, 144.6, 193.6, 40.5, 40.5]
#   Role Execution Rounds:   coverage: 2, lib: 2, qa: 2, test: 2 (Total: 8)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       35
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Interface module for SemVer 2.0 parsing, range evaluation, and dependency resolution."""

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

    def __str__(self) -> str:
        # Custom exceptions mirror dataclass semantics while rendering their diagnostic text.
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

    EQ = '=='
    NE = '!='
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='


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
        # A version is a pre-release exactly when it carries pre-release identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        # Canonical form: numeric triplet, optional '-' prerelease, optional '+' build.
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
    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
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
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
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
# LAST_CLEANED: 2026-11-07T03:27:38Z
# LAST_CHANGED: 2026-11-07T03:27:38Z
# CHANGE: Implemented SemVer interface module: non-frozen dataclass exception hierarchy with message rendering, frozen data types (Version/VersionRange/PackageDependency/PackageRelease/ResolutionOutcome) with canonical format/is_prerelease/str implementations, and @poly_type protocol stubs with @operation members.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Implementation module for SemVer 2.0 parsing, precedence, range matching, and dependency resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cmp_to_key
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver


# Official SemVer 2.0.0 grammar with leading-zero constraints on numeric identifiers.
_SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)

# Wildcard markers accepted in place of a missing numeric component.
_WILDCARD_MARKERS = frozenset({"*", "x", "X"})

# Operator prefixes supported by range expressions, longest first for unambiguous splitting.
_OPERATOR_PREFIXES = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")

# A single comparator: relational operator plus the boundary version it compares against.
_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]

# A conjunction of comparators that must all hold together.
_Clause = List[_Comparator]

# A disjunction of clauses; at least one clause must hold for a version to satisfy the range.
_Disjunction = List[_Clause]


def _parse_semver(text: str) -> Optional[semver_solver.Version]:
    """Parses SemVer 2.0.0 text, returning None when the text violates the grammar."""
    match = _SEMVER_PATTERN.fullmatch(text)
    if match is None:
        return None
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    prerelease: Tuple[str, ...] = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build: Tuple[str, ...] = tuple(build_text.split(".")) if build_text else ()
    return semver_solver.Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
        build,
    )


def _is_wildcard_marker(text: str) -> bool:
    """Indicates whether a range component is a wildcard marker."""
    return text in _WILDCARD_MARKERS


def _is_numeric_component(text: str) -> bool:
    """Indicates whether a range component is a decimal integer literal."""
    return text.isdigit()


@dataclass(frozen=True)
class _RangeBound:
    """Parsed range bound: a full version, a wildcard expression, or the unbounded wildcard."""

    major: Optional[int]
    minor: Optional[int]
    patch: Optional[int]
    prerelease: Tuple[str, ...] = ()

    @property
    def is_unbounded(self) -> bool:
        """Indicates the '*' bound spanning every release."""
        return self.major is None

    @property
    def is_full(self) -> bool:
        """Indicates a complete numeric triplet bound."""
        return self.major is not None and self.minor is not None and self.patch is not None

    def low_version(self) -> semver_solver.Version:
        """Lower boundary of the region described by this bound."""
        # Wildcard components collapse to zero when materializing the lower boundary.
        return semver_solver.Version(self.major or 0, self.minor or 0, self.patch or 0, self.prerelease)

    def high_version(self) -> semver_solver.Version:
        """Exclusive upper boundary of the wildcard region described by this bound.

        Callers invoke this helper only for wildcard bounds (absent minor or patch
        component); a fully specified bound carries no exclusive upper boundary.
        """
        if self.minor is None:
            # '<major>.x' spans every minor and patch release of that major line.
            return semver_solver.Version((self.major or 0) + 1, 0, 0)
        # '<major>.<minor>.x' spans every patch release of that minor line.
        return semver_solver.Version(self.major or 0, self.minor + 1, 0)


def _parse_range_bound(text: str) -> _RangeBound:
    """Parses one bound of a range clause into a _RangeBound record."""
    version = _parse_semver(text)
    if version is not None:
        # Full semantic versions are valid bounds for comparators, carets, tildes, and hyphens.
        return _RangeBound(version.major, version.minor, version.patch, version.prerelease)
    if _is_wildcard_marker(text):
        # A bare wildcard produces comparator sets that match every release.
        return _RangeBound(None, None, None)
    components = text.split(".")
    if len(components) == 2 and _is_numeric_component(components[0]) and _is_wildcard_marker(components[1]):
        # '<major>.x' wildcard expression.
        return _RangeBound(int(components[0]), None, None)
    if len(components) == 3 and _is_numeric_component(components[0]):
        if _is_numeric_component(components[1]) and _is_wildcard_marker(components[2]):
            # '<major>.<minor>.x' wildcard expression.
            return _RangeBound(int(components[0]), int(components[1]), None)
        if _is_wildcard_marker(components[1]) and _is_wildcard_marker(components[2]):
            # '<major>.x.x' wildcard expression, equivalent to '<major>.x'.
            return _RangeBound(int(components[0]), None, None)
    # Bare partial versions lacking wildcard characters are rejected by contract.
    raise semver_solver.InvalidRangeError(
        message=f"Bare partial version '{text}' is not permitted in a version range",
        raw_range=text,
    )


def _caret_upper_bound(bound: _RangeBound) -> semver_solver.Version:
    """Upper boundary for a caret range, driven by the first non-zero component."""
    major = bound.major or 0
    if major > 0:
        # '^1.x' and '^1.2.3' allow changes up to the next major line.
        return semver_solver.Version(major + 1, 0, 0)
    if bound.minor is None:
        # '^0.x' allows flexibility across the whole 0.x line.
        return semver_solver.Version(1, 0, 0)
    if bound.minor > 0:
        # '^0.2.3' allows changes up to the next minor line of major zero.
        return semver_solver.Version(0, bound.minor + 1, 0)
    if bound.patch is None:
        # '^0.0.x' allows changes within the 0.0 line.
        return semver_solver.Version(0, 1, 0)
    # '^0.0.3' allows changes only to the patch line of 0.0.
    return semver_solver.Version(0, 0, (bound.patch or 0) + 1)


def _tilde_upper_bound(bound: _RangeBound) -> semver_solver.Version:
    """Upper boundary for a tilde range, driven by the minor boundary."""
    major = bound.major or 0
    if bound.minor is None:
        # '~1.x' allows changes up to the next major line.
        return semver_solver.Version(major + 1, 0, 0)
    # '~1.2.x' and '~1.2.3' allow changes up to the next minor line.
    return semver_solver.Version(major, bound.minor + 1, 0)


def _expand_hyphen(low_bound: _RangeBound, high_bound: _RangeBound) -> _Disjunction:
    """Expands a hyphen range into inclusive/exclusive comparator pairs."""
    clause: _Clause = [(semver_solver.ComparatorOp.GE, low_bound.low_version())]
    if not high_bound.is_unbounded:
        if high_bound.is_full:
            # A full upper bound is inclusive.
            clause.append((semver_solver.ComparatorOp.LE, high_bound.low_version()))
        else:
            # A wildcard upper bound is exclusive of the next line.
            clause.append((semver_solver.ComparatorOp.LT, high_bound.high_version()))
    return [clause]


def _expand_comparator(operator: str, bound: _RangeBound) -> _Disjunction:
    """Expands one operator/bound pair into disjunctive normal form comparator clauses."""
    if bound.is_unbounded:
        # '>=*', '<=*', '*', '^*', and '~*' are satisfied by every version.
        if operator in ("", "==", "=", "<=", ">=", "^", "~"):
            return [[]]
        # '!=*', '<*', and '>*' match no version at all.
        return []
    if bound.is_full:
        version = bound.low_version()
        if operator in ("", "==", "="):
            return [[(semver_solver.ComparatorOp.EQ, version)]]
        if operator == "!=":
            return [[(semver_solver.ComparatorOp.NE, version)]]
        if operator == "<":
            return [[(semver_solver.ComparatorOp.LT, version)]]
        if operator == "<=":
            return [[(semver_solver.ComparatorOp.LE, version)]]
        if operator == ">":
            return [[(semver_solver.ComparatorOp.GT, version)]]
        if operator == ">=":
            return [[(semver_solver.ComparatorOp.GE, version)]]
        if operator == "^":
            return [[
                (semver_solver.ComparatorOp.GE, version),
                (semver_solver.ComparatorOp.LT, _caret_upper_bound(bound)),
            ]]
        if operator == "~":
            return [[
                (semver_solver.ComparatorOp.GE, version),
                (semver_solver.ComparatorOp.LT, _tilde_upper_bound(bound)),
            ]]
        # Unreachable: the parser only emits contracted operators; retained for return typing.
        raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: parser only emits contracted operators)
            message=f"Unsupported operator '{operator}' for version range bound",
            raw_range=operator,
        )
    low_version = bound.low_version()
    high_version = bound.high_version()
    if operator in ("", "==", "="):
        # '<major>.x' expands to '>=<major>.0.0 <(<major>+1).0.0'.
        return [[
            (semver_solver.ComparatorOp.GE, low_version),
            (semver_solver.ComparatorOp.LT, high_version),
        ]]
    if operator == "!=":
        # '!=<major>.x' expands to '<major>.x' excluded from both sides of the wildcard region.
        return [
            [(semver_solver.ComparatorOp.LT, low_version)],
            [(semver_solver.ComparatorOp.GE, high_version)],
        ]
    if operator == "<":
        return [[(semver_solver.ComparatorOp.LT, low_version)]]
    if operator == "<=":
        return [[(semver_solver.ComparatorOp.LT, high_version)]]
    if operator == ">":
        return [[(semver_solver.ComparatorOp.GE, high_version)]]
    if operator == ">=":
        return [[(semver_solver.ComparatorOp.GE, low_version)]]
    if operator == "^":
        return [[
            (semver_solver.ComparatorOp.GE, low_version),
            (semver_solver.ComparatorOp.LT, _caret_upper_bound(bound)),
        ]]
    if operator == "~":
        return [[
            (semver_solver.ComparatorOp.GE, low_version),
            (semver_solver.ComparatorOp.LT, _tilde_upper_bound(bound)),
        ]]
    # Unreachable: the parser only emits contracted operators; retained for return typing.
    raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: parser only emits contracted operators)
        message=f"Unsupported operator '{operator}' for version range bound",
        raw_range=operator,
    )


def _split_operator(token: str) -> Tuple[str, str]:
    """Splits a whitespace-delimited token into its operator prefix and bound text."""
    for operator in _OPERATOR_PREFIXES:
        if token.startswith(operator):
            return operator, token[len(operator):]
    return "", token


def _compile_clause(text: str) -> _Disjunction:
    """Compiles a single whitespace-delimited clause into disjunctive normal form."""
    tokens = text.split()
    groups: List[_Disjunction] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "-":
            # A hyphen must connect two bounds on either side.
            raise semver_solver.InvalidRangeError(
                message=f"Malformed hyphen range in clause '{text}'",
                raw_range=text,
            )
        if index + 2 < len(tokens) and tokens[index + 1] == "-":
            # Hyphen range: '<bound> - <bound>'.
            groups.append(_expand_hyphen(_parse_range_bound(token), _parse_range_bound(tokens[index + 2])))
            index += 3
            continue
        if token in _OPERATOR_PREFIXES:
            # Operator separated from its target by optional whitespace.
            if index + 1 >= len(tokens):
                raise semver_solver.InvalidRangeError(
                    message=f"Operator '{token}' is missing a version target in clause '{text}'",
                    raw_range=text,
                )
            groups.append(_expand_comparator(token, _parse_range_bound(tokens[index + 1])))
            index += 2
            continue
        operator, target_text = _split_operator(token)
        groups.append(_expand_comparator(operator, _parse_range_bound(target_text)))
        index += 1
    disjunction: _Disjunction = [[]]
    for group in groups:
        if not group:
            # A contradictory expansion poisons the whole conjunction.
            return []
        disjunction = [prefix + clause for prefix in disjunction for clause in group]
    return disjunction


def _compile_range(text: str) -> _Disjunction:
    """Compiles a complete range expression into disjunctive normal form, validating syntax."""
    stripped = text.strip()
    if not stripped:
        raise semver_solver.InvalidRangeError(
            message="Version range expression must not be empty",
            raw_range=text,
        )
    if "," in stripped:
        # Comparators are delimited strictly by whitespace; commas are not permitted.
        raise semver_solver.InvalidRangeError(
            message=f"Commas are not permitted in version range '{text}'",
            raw_range=text,
        )
    disjunction: _Disjunction = []
    for clause_text in stripped.split("||"):
        trimmed = clause_text.strip()
        if not trimmed:
            raise semver_solver.InvalidRangeError(
                message=f"Empty union clause in version range '{text}'",
                raw_range=text,
            )
        disjunction.extend(_compile_clause(trimmed))
    return disjunction


def _comparison_matches(operator: semver_solver.ComparatorOp, ordering: int) -> bool:
    """Evaluates a relational operator against a precedence ordering result."""
    if operator is semver_solver.ComparatorOp.EQ:
        return ordering == 0
    if operator is semver_solver.ComparatorOp.NE:
        return ordering != 0
    if operator is semver_solver.ComparatorOp.LT:
        return ordering < 0
    if operator is semver_solver.ComparatorOp.LE:
        return ordering <= 0
    if operator is semver_solver.ComparatorOp.GT:
        return ordering > 0
    return ordering >= 0


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    def __init__(self) -> None:
        # The engine is stateless; it holds no private backing storage.
        pass

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # POSTCONDITION: valid grammar parses into a Version record with numeric and metadata tuples.
        version = _parse_semver(text)
        if version is None:
            # PRECONDITION: grammar violations and leading zeroes raise InvalidVersionError.
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version '{text}'",
                raw_text=text,
            )
        return version

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        # POSTCONDITION: major, minor, and patch compare numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1
        # POSTCONDITION: build metadata is ignored entirely when comparing precedence.
        if not v1.prerelease and not v2.prerelease:
            return 0
        # POSTCONDITION: normal versions rank above prerelease versions sharing the numeric triplet.
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        for index in range(min(len(v1.prerelease), len(v2.prerelease))):
            left_segment = v1.prerelease[index]
            right_segment = v2.prerelease[index]
            if left_segment == right_segment:
                continue
            left_numeric = left_segment.isdigit()
            right_numeric = right_segment.isdigit()
            if left_numeric and right_numeric:
                # POSTCONDITION: numeric prerelease segments compare numerically.
                return -1 if int(left_segment) < int(right_segment) else 1
            if left_numeric:
                # POSTCONDITION: numeric prerelease segments rank below alphanumeric segments.
                return -1
            if right_numeric:
                return 1
            # POSTCONDITION: alphanumeric prerelease segments compare ASCII-lexicographically.
            return -1 if left_segment < right_segment else 1
        # POSTCONDITION: longer prerelease sequences rank higher when the common prefix matches.
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # PRECONDITION: malformed syntax, empty clauses, and bare partial versions raise InvalidRangeError.
        _compile_range(text)
        # POSTCONDITION: surrounding whitespace is trimmed and stored in raw_text.
        return semver_solver.VersionRange(text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        # POSTCONDITION: the range compiles into disjunctive normal form comparator sets.
        disjunction = _compile_range(range_constraint.raw_text)
        for clause in disjunction:
            # POSTCONDITION: a version must satisfy every comparator in at least one clause.
            if not all(
                _comparison_matches(operator, self.compare_precedence(version, target))
                for operator, target in clause
            ):
                continue
            if version.is_prerelease and not include_prerelease:
                # POSTCONDITION: prereleases only satisfy ranges explicitly targeting that triplet.
                if not any(
                    target.is_prerelease
                    and target.major == version.major
                    and target.minor == version.minor
                    and target.patch == version.patch
                    for _, target in clause
                ):
                    continue
            return True
        # POSTCONDITION: all clauses failed satisfaction.
        return False


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Indexed package publications keyed by package name.
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)

        def descending_precedence(
            left: semver_solver.PackageRelease,
            right: semver_solver.PackageRelease,
        ) -> int:
            # POSTCONDITION: releases remain ordered by descending version precedence.
            return engine.compare_precedence(right.version, left.version)

        releases.sort(key=cmp_to_key(descending_precedence))

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            # PRECONDITION: unregistered package names raise PackageNotFoundError.
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
        # POSTCONDITION: a shallow copy of the descending-precedence release list is produced.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        # POSTCONDITION: membership in the package index determines existence.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names."""
        # POSTCONDITION: every registered package key appears in the produced set.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        # The solver keeps search state local to each resolve() invocation.
        pass

    @operation
    @override
    def resolve(self, root_dependencies: Collection[semver_solver.PackageDependency]) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints pair each requesting package with its required range.
        accumulated_constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated_constraints.setdefault(dependency.name, []).append(("root", dependency.range_constraint))

        # Partial assignment, derivation trail, and conflict diagnostics for the depth-first search.
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_candidates(package: str) -> List[semver_solver.PackageRelease]:
            # Unregistered packages expose zero candidate releases without leaking PackageNotFoundError.
            if not repository.has_package(package):
                return []
            return [
                release
                for release in repository.get_releases(package)
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated_constraints[package]
                )
            ]

        def backtrack() -> bool:
            unassigned = [package for package in accumulated_constraints if package not in assignment]
            if not unassigned:
                # POSTCONDITION: a complete assignment satisfies root and transitive dependencies.
                return True
            candidate_map = {package: viable_candidates(package) for package in unassigned}
            # Minimum Remaining Values selection with lexical tie-breaking.
            selected = min(unassigned, key=lambda package: (len(candidate_map[package]), package))
            candidates = candidate_map[selected]
            if not candidates:
                # Conflict trail records unsatisfied requirements for the exhausted package.
                requesters = [source for source, _ in accumulated_constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {sorted(requesters)}"
                )
                return False
            for candidate in candidates:
                # Value ordering explores candidates in descending precomputed precedence.
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not engine.satisfies(assignment[dependency.name].version, dependency.range_constraint, False):
                            # Forward checking rejects releases whose dependencies contradict the assignment.
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{dependency.name}' {dependency.range_constraint}"
                            )
                            break
                    else:
                        constraint_entry = (selected, dependency.range_constraint)
                        accumulated_constraints.setdefault(dependency.name, []).append(constraint_entry)
                        newly_added.append((dependency.name, constraint_entry))
                if not conflict_detected and backtrack():
                    return True
                # Backtracking restores the constraint mapping and partial assignment state.
                for package_name, constraint_entry in newly_added:
                    accumulated_constraints[package_name].remove(constraint_entry)
                    if not accumulated_constraints[package_name]:
                        del accumulated_constraints[package_name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if backtrack():
            # POSTCONDITION: the outcome records selected versions and the decision sequence.
            selected_versions = {
                package: release.version for package, release in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )
        explanation = "\n".join(conflict_trail)
        # PRECONDITION: unsatisfiable dependencies raise ResolutionConflictError with a derivation.
        raise semver_solver.ResolutionConflictError(
            message="Unable to resolve a mutually compatible set of package releases",
            conflicting_packages=tuple(sorted(conflicting_packages)),
            explanation=explanation,
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
# LAST_CLEANED: 2026-11-07T03:35:02Z
# LAST_CHANGED: 2026-11-07T03:33:47Z
# CHANGE: Resolved feedback: pruned the unreachable trailing 'return None' fallback from _RangeBound.high_version by making the helper non-optional (both wildcard upper-bound returns are reachable via '<major>.x' and '<major>.<minor>.x' forms) and simplified both call sites accordingly; also pruned sibling dead guards in the clause compiler and type-checking-only unreachable raises annotated with '# pragma: no cover (assumption: ...)' so statement coverage is attainable.
# COVERAGE_AUDIT: 2026-11-07T03:35:02Z
# QA_AUDIT: 2026-11-07T03:34:20Z
# --- END AUTOFAB METADATA ---
