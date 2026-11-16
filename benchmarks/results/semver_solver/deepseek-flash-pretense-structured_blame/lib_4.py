# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261115_033241_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-11-15T03:32:41.231934+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 260,956
#   Cached Inbound Tokens:   22,869,504
#   Outbound Tokens:         337,102
#   Total Tokens:            23,467,562
#   Financial Cost ($USD):   $0.3100
#   Wall Clock Duration:     1804.47s
#   Step Latencies (s):      [393.7, 645.4, 20.3, 134.9, 237.7, 10.2, 204.6, 63.6, 289.2, 10.2, 92.0, 43.2, 123.1, 10.1, 20.3]
#   Role Execution Rounds:   lib: 3, pretense: 4, pretense_coverage: 4, pretense_qa: 4 (Total: 15)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       3
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Interface specification for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception raised by semantic versioning and dependency resolution code.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

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
        """Retrieves registered releases for a package ordered by version precedence descending.

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
# LAST_CLEANED: 2026-11-15T03:39:09Z
# LAST_CHANGED: 2026-11-15T03:39:09Z
# CHANGE: Implemented interface module: SemVerError hierarchy with structured attributes and string rendering, ComparatorOp enum, frozen data types Version (canonical formatting and prerelease detection), VersionRange, PackageDependency, PackageRelease, ResolutionOutcome, and Protocol service interfaces VersionEngine, PackageRepository, DependencySolver with contracted operation stubs.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Runtime implementation of SemVer 2.0 parsing and backtracking dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key
import re
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import semver_solver

_PRERELEASE_IDENTIFIER = r"(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_IDENTIFIER = r"[0-9A-Za-z-]+"

# Full SemVer 2.0.0 grammar: numeric components without leading zeroes, then
# optional dot-separated pre-release identifiers and plus-separated build metadata.
_SEMVER_PATTERN = re.compile(
    r"\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(" + _PRERELEASE_IDENTIFIER + r"(?:\." + _PRERELEASE_IDENTIFIER + r")*))?"
    r"(?:\+(" + _BUILD_IDENTIFIER + r"(?:\." + _BUILD_IDENTIFIER + r")*))?\Z"
)
_NUMERIC_PATTERN = re.compile(r"\A(?:0|[1-9][0-9]*)\Z")
_COMPARATOR_PREFIX_PATTERN = re.compile(r"\A(==|!=|<=|>=|=|<|>|\^|~)(.*)\Z")
_HYPHEN_PATTERN = re.compile(r"\A(.+?)\s+-\s+(.+)\Z")

_WILDCARD_TOKENS = frozenset({"*", "x", "X"})
_OPERATOR_TOKENS = frozenset({"==", "!=", "<=", ">=", "=", "<", ">", "^", "~"})

_SIMPLE_OPERATORS: Dict[str, semver_solver.ComparatorOp] = {
    "==": semver_solver.ComparatorOp.EQ,
    "=": semver_solver.ComparatorOp.EQ,
    "!=": semver_solver.ComparatorOp.NE,
    "<": semver_solver.ComparatorOp.LT,
    "<=": semver_solver.ComparatorOp.LE,
    ">": semver_solver.ComparatorOp.GT,
    ">=": semver_solver.ComparatorOp.GE,
}


@dataclass(frozen=True)
class _Bound:
    """Concrete leading version components of a comparator operand.

    The components tuple holds the numeric components supplied before any wildcard;
    an empty tuple denotes a fully wildcarded operand matching every version.
    """

    components: Tuple[int, ...]
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_full(self) -> bool:
        """Whether the operand specifies all three numeric version components."""
        return len(self.components) == 3

    @property
    def is_wildcard(self) -> bool:
        """Whether the operand leaves at least one numeric component open."""
        return len(self.components) < 3

    @property
    def matches_all(self) -> bool:
        """Whether the operand places no restriction on any numeric component."""
        return len(self.components) == 0

    def lower_version(self) -> semver_solver.Version:
        """Builds the inclusive lower bound by padding open components with zero."""
        values = list(self.components)
        while len(values) < 3:
            values.append(0)
        return semver_solver.Version(
            values[0], values[1], values[2], self.prerelease, self.build
        )

    def wildcard_upper(self) -> Optional[semver_solver.Version]:
        """Builds the exclusive boundary just past the wildcarded family."""
        if not self.components:
            return None
        values = list(self.components)
        values[-1] = values[-1] + 1
        while len(values) < 3:
            values.append(0)
        return semver_solver.Version(values[0], values[1], values[2])

    def caret_upper(self) -> Optional[semver_solver.Version]:
        """Builds the caret upper boundary from the first non-zero component."""
        if not self.components:
            return None
        major = self.components[0]
        if major > 0:
            return semver_solver.Version(major + 1, 0, 0)
        if len(self.components) == 1:
            return semver_solver.Version(1, 0, 0)
        minor = self.components[1]
        if minor > 0:
            return semver_solver.Version(0, minor + 1, 0)
        if len(self.components) == 2:
            return semver_solver.Version(0, 1, 0)
        return semver_solver.Version(0, 0, self.components[2] + 1)

    def tilde_upper(self) -> Optional[semver_solver.Version]:
        """Builds the tilde upper boundary at the next minor release."""
        if not self.components:
            return None
        major = self.components[0]
        if len(self.components) == 1:
            return semver_solver.Version(major + 1, 0, 0)
        return semver_solver.Version(major, self.components[1] + 1, 0)


@dataclass(frozen=True)
class _Comparator:
    """Single relational comparison against a concrete version boundary."""

    op: semver_solver.ComparatorOp
    version: semver_solver.Version


_Clause = Tuple[_Comparator, ...]


def _parse_version(text: str) -> semver_solver.Version:
    """Parses SemVer 2.0.0 text into an immutable version record."""
    match = _SEMVER_PATTERN.match(text)
    if match is None:
        raise semver_solver.InvalidVersionError(
            f"Invalid semantic version: {text!r}", text
        )
    prerelease_text = match.group(4)
    build_text = match.group(5)
    return semver_solver.Version(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        tuple(prerelease_text.split(".")) if prerelease_text else (),
        tuple(build_text.split(".")) if build_text else (),
    )


def _parse_bound(token: str) -> Optional[_Bound]:
    """Parses a comparator operand as a full version or wildcard expression."""
    if not token:
        # Clause tokenization never yields an empty operand.
        with unreachable:
            return None
    match = _SEMVER_PATTERN.match(token)
    if match is not None:
        prerelease_text = match.group(4)
        build_text = match.group(5)
        return _Bound(
            (int(match.group(1)), int(match.group(2)), int(match.group(3))),
            tuple(prerelease_text.split(".")) if prerelease_text else (),
            tuple(build_text.split(".")) if build_text else (),
        )
    parts = token.split(".")
    if not parts or len(parts) > 3:
        return None
    components: List[int] = []
    wildcard_seen = False
    for part in parts:
        if part in _WILDCARD_TOKENS:
            wildcard_seen = True
            break
        if _NUMERIC_PATTERN.match(part) is None:
            return None
        components.append(int(part))
    if not wildcard_seen:
        # Bare partial versions without a wildcard are not valid range operands.
        return None
    # Every component following the first wildcard must itself be a wildcard.
    for part in parts[len(components):]:
        if part not in _WILDCARD_TOKENS:
            return None
    return _Bound(tuple(components))


def _compare_versions(
    v1: semver_solver.Version, v2: semver_solver.Version
) -> int:
    """Compares two versions by SemVer 2.0.0 precedence, ignoring build metadata."""
    if v1.major != v2.major:
        return -1 if v1.major < v2.major else 1
    if v1.minor != v2.minor:
        return -1 if v1.minor < v2.minor else 1
    if v1.patch != v2.patch:
        return -1 if v1.patch < v2.patch else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for index in range(min(len(v1.prerelease), len(v2.prerelease))):
        left = v1.prerelease[index]
        right = v2.prerelease[index]
        left_numeric = left.isdigit()
        right_numeric = right.isdigit()
        if left_numeric and right_numeric:
            left_value = int(left)
            right_value = int(right)
            if left_value != right_value:
                return -1 if left_value < right_value else 1
        elif left_numeric:
            # Numeric pre-release identifiers rank below alphanumeric ones.
            return -1
        elif right_numeric:
            return 1
        elif left != right:
            return -1 if left < right else 1
    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
    return 0


def _expand_comparator(operator: str, bound: _Bound) -> List[_Clause]:
    """Normalizes one comparator into alternative conjunctive clauses."""
    lower = bound.lower_version()
    if operator == "^":
        upper = bound.caret_upper()
        if upper is None:
            return [()]
        return [
            (
                _Comparator(semver_solver.ComparatorOp.GE, lower),
                _Comparator(semver_solver.ComparatorOp.LT, upper),
            )
        ]
    if operator == "~":
        upper = bound.tilde_upper()
        if upper is None:
            return [()]
        return [
            (
                _Comparator(semver_solver.ComparatorOp.GE, lower),
                _Comparator(semver_solver.ComparatorOp.LT, upper),
            )
        ]
    comparison = _SIMPLE_OPERATORS[operator]
    if bound.matches_all:
        if comparison in (
            semver_solver.ComparatorOp.EQ,
            semver_solver.ComparatorOp.GE,
            semver_solver.ComparatorOp.LE,
        ):
            return [()]
        return []
    if not bound.is_wildcard:
        return [(_Comparator(comparison, lower),)]
    upper = bound.wildcard_upper()
    if comparison is semver_solver.ComparatorOp.EQ:
        if upper is None:
            # Fully wildcarded operands were handled above, so a boundary exists.
            with unreachable:
                return [()]
        return [
            (
                _Comparator(semver_solver.ComparatorOp.GE, lower),
                _Comparator(semver_solver.ComparatorOp.LT, upper),
            )
        ]
    if comparison is semver_solver.ComparatorOp.NE:
        # The complement of a wildcard family is a disjunction of two clauses.
        if upper is None:
            # Fully wildcarded operands were handled above, so a boundary exists.
            with unreachable:
                return []
        return [
            (_Comparator(semver_solver.ComparatorOp.LT, lower),),
            (_Comparator(semver_solver.ComparatorOp.GE, upper),),
        ]
    if comparison is semver_solver.ComparatorOp.LT:
        return [(_Comparator(semver_solver.ComparatorOp.LT, lower),)]
    if comparison is semver_solver.ComparatorOp.LE:
        if upper is None:
            # Fully wildcarded operands were handled above, so a boundary exists.
            with unreachable:
                return [()]
        return [(_Comparator(semver_solver.ComparatorOp.LT, upper),)]
    if comparison is semver_solver.ComparatorOp.GT:
        if upper is None:
            # Fully wildcarded operands were handled above, so a boundary exists.
            with unreachable:
                return []
        return [(_Comparator(semver_solver.ComparatorOp.GE, upper),)]
    return [(_Comparator(semver_solver.ComparatorOp.GE, lower),)]


def _combine_outcomes(
    outcomes: List[_Clause], additions: List[_Clause]
) -> List[_Clause]:
    """Forms the conjunction of accumulated clauses with fresh comparator expansions."""
    combined: List[_Clause] = []
    for outcome in outcomes:
        for addition in additions:
            combined.append(outcome + addition)
    return combined


def _expand_hyphen_range(
    lower_text: str, upper_text: str, raw_range: str
) -> _Clause:
    """Expands a hyphen range into an inclusive lower and upper comparator pair."""
    lower_bound = _parse_bound(lower_text)
    upper_bound = _parse_bound(upper_text)
    if lower_bound is None or upper_bound is None:
        raise semver_solver.InvalidRangeError(
            "Hyphen range bounds must be full versions or wildcard expressions",
            raw_range,
        )
    comparators: List[_Comparator] = []
    if not lower_bound.matches_all:
        comparators.append(
            _Comparator(semver_solver.ComparatorOp.GE, lower_bound.lower_version())
        )
    if upper_bound.is_full:
        comparators.append(
            _Comparator(semver_solver.ComparatorOp.LE, upper_bound.lower_version())
        )
    else:
        upper = upper_bound.wildcard_upper()
        if upper is not None:
            comparators.append(
                _Comparator(semver_solver.ComparatorOp.LT, upper)
            )
    return tuple(comparators)


def _parse_clause(clause: str, raw_range: str) -> List[_Clause]:
    """Parses one whitespace-delimited conjunction into alternative clauses."""
    hyphen = _HYPHEN_PATTERN.match(clause)
    if hyphen is not None:
        return [
            _expand_hyphen_range(
                hyphen.group(1).strip(), hyphen.group(2).strip(), raw_range
            )
        ]
    tokens = clause.split()
    outcomes: List[_Clause] = [()]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATOR_TOKENS:
            if index + 1 >= len(tokens):
                raise semver_solver.InvalidRangeError(
                    f"Comparator '{token}' is missing a target version", raw_range
                )
            operator = token
            operand = tokens[index + 1]
            index += 2
        else:
            prefix = _COMPARATOR_PREFIX_PATTERN.match(token)
            if prefix is None:
                operator = "="
                operand = token
            else:
                operator = prefix.group(1)
                operand = prefix.group(2)
                if not operand:
                    # Operator-only tokens are consumed by the branch above.
                    with unreachable:
                        raise semver_solver.InvalidRangeError(
                            f"Comparator '{token}' is missing a target version",
                            raw_range,
                        )
            index += 1
        bound = _parse_bound(operand)
        if bound is None:
            raise semver_solver.InvalidRangeError(
                f"Invalid or partial version expression '{operand}'", raw_range
            )
        outcomes = _combine_outcomes(outcomes, _expand_comparator(operator, bound))
    return outcomes


def _compile_range(text: str) -> Tuple[_Clause, ...]:
    """Compiles range text into disjunctive normal form comparator clauses."""
    trimmed = text.strip()
    if not trimmed:
        raise semver_solver.InvalidRangeError("Range expression is empty", text)
    if "," in trimmed:
        raise semver_solver.InvalidRangeError(
            "Comparators are delimited by whitespace, not commas", text
        )
    clauses: List[_Clause] = []
    for raw_clause in trimmed.split("||"):
        clause = raw_clause.strip()
        if not clause:
            raise semver_solver.InvalidRangeError(
                "Range expression contains an empty union clause", text
            )
        clauses.extend(_parse_clause(clause, text))
    return tuple(clauses)


def _satisfies_clause(version: semver_solver.Version, clause: _Clause) -> bool:
    """Checks every comparator within one conjunction against the candidate version."""
    for comparator in clause:
        order = _compare_versions(version, comparator.version)
        operation = comparator.op
        if operation is semver_solver.ComparatorOp.EQ and order != 0:
            return False
        if operation is semver_solver.ComparatorOp.NE and order == 0:
            return False
        if operation is semver_solver.ComparatorOp.LT and order >= 0:
            return False
        if operation is semver_solver.ComparatorOp.LE and order > 0:
            return False
        if operation is semver_solver.ComparatorOp.GT and order <= 0:
            return False
        if operation is semver_solver.ComparatorOp.GE and order < 0:
            return False
    return True


def _targets_prerelease(
    version: semver_solver.Version, clauses: Tuple[_Clause, ...]
) -> bool:
    """Detects whether any boundary explicitly names the candidate pre-release."""
    for clause in clauses:
        for comparator in clause:
            boundary = comparator.version
            if not boundary.prerelease:
                continue
            if (
                boundary.major == version.major
                and boundary.minor == version.minor
                and boundary.patch == version.patch
            ):
                return True
    return False


@singleton
class VersionEngine(semver_solver.VersionEngine):
    tier = "system"

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses SemVer 2.0.0 text, rejecting grammar and leading zero violations."""
        return _parse_version(text)

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Orders versions numerically, then by pre-release identifiers."""
        return _compare_versions(v1, v2)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Validates a range expression and stores its trimmed text."""
        _compile_range(text)
        return semver_solver.VersionRange(text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates the candidate version against the compiled range clauses."""
        clauses = _compile_range(range_constraint.raw_text)
        if version.is_prerelease and not include_prerelease:
            # Pre-releases only match ranges that name that exact pre-release line.
            if not _targets_prerelease(version, clauses):
                return False
        return any(_satisfies_clause(version, clause) for clause in clauses)


@singleton
class PackageRepository(semver_solver.PackageRepository):
    tier = "system"

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Stores the release and re-sorts its package history by descending precedence."""
        engine = get_singleton(semver_solver.VersionEngine)

        def precedence(
            left: semver_solver.PackageRelease,
            right: semver_solver.PackageRelease,
        ) -> int:
            """Orders releases by descending version precedence."""
            return engine.compare_precedence(left.version, right.version)

        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=cmp_to_key(precedence), reverse=True)

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Returns a shallow copy of the descending release history for a package."""
        releases = self._packages.get(name)
        if releases is None:
            raise semver_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository", name
            )
        return list(releases)

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether the package appears in the repository index."""
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Returns a fresh set of every registered package name."""
        return set(self._packages.keys())


@singleton
class DependencySolver(semver_solver.DependencySolver):
    tier = "system"

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Runs depth-first backtracking search with minimum remaining values ordering."""
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Each package name maps to the constraints contributed by depending packages.
        constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def descending_precedence(
            left: semver_solver.PackageRelease,
            right: semver_solver.PackageRelease,
        ) -> int:
            """Orders candidate releases by descending version precedence."""
            return engine.compare_precedence(left.version, right.version)

        def candidate_releases(name: str) -> List[semver_solver.PackageRelease]:
            """Lists releases satisfying every accumulated constraint for a package."""
            try:
                releases = repository.get_releases(name)
            except semver_solver.PackageNotFoundError:
                # Missing packages expose no candidates instead of escaping the solver.
                return []
            ordered = sorted(
                releases,
                key=cmp_to_key(descending_precedence),
                reverse=True,
            )
            return [
                release
                for release in ordered
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in constraints[name]
                )
            ]

        def search() -> bool:
            """Assigns the most constrained package, backtracking on dead ends."""
            unassigned = [
                name for name in constraints if name not in assignment
            ]
            if not unassigned:
                return True

            candidates: Dict[str, List[semver_solver.PackageRelease]] = {
                name: candidate_releases(name) for name in unassigned
            }
            selected = min(
                unassigned, key=lambda name: (len(candidates[name]), name)
            )
            options = candidates[selected]

            if not options:
                requesters = [
                    source
                    for source, _ in constraints[selected]
                    if source != "root"
                ]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False

            for candidate in options:
                assignment[selected] = candidate
                derivation_steps.append(
                    f"Assign '{selected}' to {candidate.version}"
                )

                dependency_conflict = False
                introduced: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                for dependency in candidate.dependencies:
                    assigned = assignment.get(dependency.name)
                    if assigned is not None:
                        if not engine.satisfies(
                            assigned.version, dependency.range_constraint, False
                        ):
                            dependency_conflict = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(entry)
                        introduced.append((dependency.name, entry))

                # Descend only when no already-assigned release is contradicted.
                if not dependency_conflict and search():
                    return True

                for dependency_name, entry in introduced:
                    constraints[dependency_name].remove(entry)
                    if not constraints[dependency_name]:
                        del constraints[dependency_name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if search():
            selected_versions = {
                name: assignment[name].version for name in sorted(assignment)
            }
            return semver_solver.ResolutionOutcome(
                selected_versions, tuple(derivation_steps)
            )

        explanation = (
            "\n".join(conflict_trail)
            if conflict_trail
            else "Every candidate branch was exhausted without a complete assignment."
        )
        names = tuple(sorted(conflicting_packages))
        summary = ", ".join(names) if names else "unknown packages"
        raise semver_solver.ResolutionConflictError(
            f"Dependency resolution failed for: {summary}", names, explanation
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:02:32Z
# LAST_CHANGED: 2026-11-15T04:00:44Z
# CHANGE: Resolved remaining pretense_coverage unreachable-logic facets for semver.parse_range.comparators_and_prefixes: quarantined the unreachable matches-all inclusive (LE) and greater-than (GT) wildcard-upper guards in _expand_comparator and the unreachable empty prefix-operand raise guard in _parse_clause with 'with unreachable:' blocks. All wildcard-upper dead guards in _expand_comparator are now consistently quarantined; reachable range parsing behavior is unchanged and static checks pass.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T04:02:32Z
# PRETENSE_QA_AUDIT: 2026-11-15T04:02:19Z
# --- END AUTOFAB METADATA ---
