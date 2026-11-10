# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_032225_deepseek-flash_semver_solver_combined
# Timestamp: 2026-11-08T03:22:25.124302+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 566,108
#   Cached Inbound Tokens:   61,468,800
#   Outbound Tokens:         586,035
#   Total Tokens:            62,620,943
#   Financial Cost ($USD):   $0.6209
#   Wall Clock Duration:     3386.49s
#   Step Latencies (s):      [279.1, 404.4, 63.4, 133.5, 10.1, 656.9, 129.2, 84.4, 226.3, 10.1, 20.4, 544.5, 174.3, 71.7, 12.1, 10.1, 65.5, 40.9, 73.7, 40.9, 71.7, 40.9, 83.9, 411.8, 20.4, 135.1, 392.0, 63.5, 63.4, 20.4, 124.9, 176.6, 20.4, 104.3, 53.4, 10.2, 10.1]
#   Role Execution Rounds:   coverage: 3, lib: 8, pretense: 6, pretense_coverage: 4, pretense_qa: 10, qa: 4, test: 2 (Total: 37)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       34
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
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error. Verification suites MUST NOT assert on specific wording or prefixes within message, and MUST assert on exception types and structured attributes.
    """

    message: str

    def __str__(self) -> str:
        # Realizes the custom exception message formatting contract.
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
        # Verifies whether any dot-separated pre-release identifiers are present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        # Canonical rendering: major.minor.patch[-prerelease][+build].
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
        # Delegates to the canonical string representation.
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
        # Delegates to the stored canonical range text.
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

        PRECONDITIONS:
        - WHEN text contains leading zeroes in numeric identifiers or violates grammar, MUST raise InvalidVersionError.

        POSTCONDITIONS:
        - MUST parse valid SemVer 2.0.0 strings into Version records with major, minor, patch, prerelease, and build tuples.
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

        PRECONDITIONS:
        - WHEN text supplies bare partial versions lacking wildcard characters across any comparator or hyphen expression (such as '1', '1.2', '>1.2', '^0.0', or '1.2 - 2.3'), MUST raise InvalidRangeError.
        - WHEN text is empty, contains only whitespace, contains empty union clauses, uses comma delimiters, or violates range syntax, MUST raise InvalidRangeError.

        POSTCONDITIONS:
        - MUST parse range expression text supporting basic comparators (==, =, !=, <, <=, >, >=), caret ranges (^), and tilde ranges (~) applied to either full semantic versions or wildcard expressions (e.g. '>=1.x', '!=1.x', '>1.*', '^1.x', '~1.2.x', '>=*').
        - MUST parse hyphen ranges connecting two version bounds ('bound1 - bound2'), where each bound is either a full semantic version or a wildcard expression (e.g. '1.0.0 - 2.x', '1.x - 2.x').
        - MUST parse union alternatives separated by '||'.
        - MUST trim surrounding whitespace around range expressions and individual clauses, storing the trimmed range expression in raw_text.
        - MUST accept optional whitespace between relational/prefix operators and target versions or wildcards (e.g. '>= 1.0.0' is equivalent to '>=1.0.0', '>= 1.x' is equivalent to '>=1.x').
        - MUST delimit comparators within clauses strictly by whitespace; commas are not permitted.
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

        PRECONDITIONS:
        - WHEN name is not registered, MUST raise PackageNotFoundError.

        POSTCONDITIONS:
        - MUST yield all registered releases for package name ordered by version precedence descending.
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

        PRECONDITIONS:
        - WHEN dependencies are unsatisfiable or reference unregistered packages absent from repository, MUST raise ResolutionConflictError detailing conflicting packages and derivation explanation without allowing PackageNotFoundError to escape.

        POSTCONDITIONS:
        - MUST compute a mutually compatible set of package releases satisfying root and transitive dependencies.
        - MUST select the highest precedence compatible version for each package.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T03:29:15Z
# LAST_CHANGED: 2026-11-08T03:29:15Z
# CHANGE: Implemented the SemVer interface module: non-frozen dataclass error hierarchy (SemVerError and subclasses with __str__ delegating to message), immutable @data_type records Version/VersionRange/PackageDependency/PackageRelease/ResolutionOutcome, concrete Version methods (is_prerelease, canonical format, __str__), ComparatorOp enum, and @poly_type protocol stubs for VersionEngine, PackageRepository, and DependencySolver matching the low-level specification.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
import functools
import re
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_COMPARATOR_PATTERN = re.compile(r"^(?P<operator>[<>=!~^]*)\s*(?P<operand>[0-9A-Za-z.*+_-]+)$")

_HYPHEN_RANGE_SEPARATOR = re.compile(r"\s+-\s+")

_NUMERIC_PART_PATTERN = re.compile(r"0|[1-9][0-9]*")

_WILDCARD_TOKENS = frozenset({"x", "X", "*"})

_OPERATOR_ONLY_TOKENS = frozenset({"==", "=", "!=", "<", "<=", ">", ">=", "^", "~"})

_VALID_OPERATORS = frozenset({"", "=", "==", "!=", "<", "<=", ">", ">=", "^", "~"})

_ZERO_VERSION = semver_solver.Version(0, 0, 0)

# Partial operand components: None denotes a wildcard component.
_Parts = Tuple[Optional[int], Optional[int], Optional[int]]

# A single comparator test is an operator paired with a boundary version.
_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]

# A clause is the conjunction of its comparators; a range is a disjunction of clauses.
_Clause = List[_Comparator]

_CompiledRange = List[_Clause]


def _invalid_range(raw_text: str, detail: str) -> semver_solver.InvalidRangeError:
    """Builds the contracted InvalidRangeError diagnostic for malformed range text."""
    return semver_solver.InvalidRangeError(
        f"Invalid version range {raw_text!r}: {detail}",
        raw_text,
    )


def _version_from_match(match: re.Match[str]) -> semver_solver.Version:
    """Builds an immutable Version record from a successful SemVer grammar match."""
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    return semver_solver.Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        tuple(prerelease_text.split(".")) if prerelease_text else (),
        tuple(build_text.split(".")) if build_text else (),
    )


def _is_numeric_identifier(text: str) -> bool:
    """Checks whether a prerelease identifier is a purely ASCII numeric segment."""
    return text.isascii() and text.isdigit()


def _parse_operand(
    operand: str,
    raw_text: str,
) -> Tuple[Optional[semver_solver.Version], _Parts]:
    """Parses a comparator operand into a full version or a wildcard partial bound.

    A full SemVer 2.0.0 version yields a concrete Version record. Otherwise the operand
    must be a wildcard expression (at least one x, X, or * component); bare partial
    versions lacking wildcards are rejected per the range preconditions.
    """
    match = _SEMVER_PATTERN.fullmatch(operand)
    if match is not None:
        version = _version_from_match(match)
        return version, (version.major, version.minor, version.patch)

    # Wildcard expressions are dot-separated numeric components followed by wildcards.
    raw_parts = operand.split(".")
    if len(raw_parts) > 3:
        raise _invalid_range(raw_text, f"operand {operand!r} has too many components")
    parts: List[Optional[int]] = []
    wildcard_seen = False
    for raw_part in raw_parts:
        if raw_part in _WILDCARD_TOKENS:
            wildcard_seen = True
            parts.append(None)
            continue
        if wildcard_seen:
            raise _invalid_range(raw_text, f"wildcard component must be trailing in {operand!r}")
        if _NUMERIC_PART_PATTERN.fullmatch(raw_part) is None:
            raise _invalid_range(raw_text, f"operand {operand!r} is not a valid version or wildcard")
        parts.append(int(raw_part))
    if not wildcard_seen:
        # Bare partial versions lacking wildcard characters are prohibited.
        raise _invalid_range(raw_text, f"bare partial version {operand!r} is missing a wildcard")
    while len(parts) < 3:
        parts.append(None)
    return None, (parts[0], parts[1], parts[2])


def _fill_parts(parts: _Parts) -> semver_solver.Version:
    """Fills wildcard components with zeroes to produce a concrete lower bound."""
    major, minor, patch = parts
    return semver_solver.Version(
        major if major is not None else 0,
        minor if minor is not None else 0,
        patch if patch is not None else 0,
    )


def _wildcard_upper(parts: _Parts) -> semver_solver.Version:
    """Computes the exclusive upper bound of a wildcard expression with a concrete major."""
    major, minor, _patch = parts
    # Callers only request an upper bound when the major component is concrete.
    assert major is not None
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _caret_upper_version(version: semver_solver.Version) -> semver_solver.Version:
    """Computes the caret range upper bound from the first non-zero full version component."""
    if version.major > 0:
        return semver_solver.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_solver.Version(0, version.minor + 1, 0)
    return semver_solver.Version(0, 0, version.patch + 1)


def _caret_upper_partial(parts: _Parts) -> semver_solver.Version:
    """Computes the caret range upper bound for a wildcard expression with a concrete major."""
    major, minor, patch = parts
    # Callers only request an upper bound when the major component is concrete.
    assert major is not None
    if major > 0:
        return semver_solver.Version(major + 1, 0, 0)
    if minor is None:
        return semver_solver.Version(1, 0, 0)
    if minor > 0:
        return semver_solver.Version(0, minor + 1, 0)
    # With a concrete major and minor, a wildcard operand carries a wildcard patch component.
    assert patch is None
    return semver_solver.Version(0, minor + 1, 0)


def _tilde_upper_version(version: semver_solver.Version) -> semver_solver.Version:
    """Computes the tilde range upper bound at the next minor boundary of a full version."""
    return semver_solver.Version(version.major, version.minor + 1, 0)


def _tilde_upper_partial(parts: _Parts) -> semver_solver.Version:
    """Computes the tilde range upper bound for a wildcard expression with a concrete major."""
    major, minor, _patch = parts
    # Callers only request an upper bound when the major component is concrete.
    assert major is not None
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _expand_comparator(
    operator: str,
    version: Optional[semver_solver.Version],
    parts: _Parts,
) -> List[_Clause]:
    """Expands a single comparator into disjunctive normal form comparator clauses.

    Wildcard equality, relational, caret, and tilde comparators normalize into paired
    lower/upper bound inequalities; wildcard inequality splits into two disjoint clauses.
    """
    if version is not None:
        # Full version comparators map directly onto comparison operators.
        if operator in ("", "=", "=="):
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
                (semver_solver.ComparatorOp.LT, _caret_upper_version(version)),
            ]]
        return [[
            (semver_solver.ComparatorOp.GE, version),
            (semver_solver.ComparatorOp.LT, _tilde_upper_version(version)),
        ]]

    major = parts[0]
    if major is None:
        # A fully unbounded wildcard matches every version; negation and strict
        # upper bounds on it are impossible to satisfy.
        if operator in ("!=", "<"):
            return [[(semver_solver.ComparatorOp.EQ, _ZERO_VERSION), (semver_solver.ComparatorOp.NE, _ZERO_VERSION)]]
        return [[]]

    lower = _fill_parts(parts)
    upper = _wildcard_upper(parts)
    # Wildcard equality covers the whole filled component block.
    if operator in ("", "=", "=="):
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]]
    # Wildcard inequality splits into the two disjoint ranges outside the block.
    if operator == "!=":
        return [
            [(semver_solver.ComparatorOp.LT, lower)],
            [(semver_solver.ComparatorOp.GE, upper)],
        ]
    if operator == ">=":
        return [[(semver_solver.ComparatorOp.GE, lower)]]
    if operator == ">":
        return [[(semver_solver.ComparatorOp.GE, upper)]]
    if operator == "<":
        return [[(semver_solver.ComparatorOp.LT, lower)]]
    if operator == "<=":
        return [[(semver_solver.ComparatorOp.LT, upper)]]
    if operator == "^":
        return [[
            (semver_solver.ComparatorOp.GE, lower),
            (semver_solver.ComparatorOp.LT, _caret_upper_partial(parts)),
        ]]
    return [[
        (semver_solver.ComparatorOp.GE, lower),
        (semver_solver.ComparatorOp.LT, _tilde_upper_partial(parts)),
    ]]


def _split_comparators(text: str, raw_text: str) -> List[str]:
    """Splits a whitespace-delimited clause into operator/operand comparator tokens.

    An operator token separated from its operand by whitespace is rejoined with the
    following token, realizing optional operator whitespace tolerances.
    """
    tokens = text.split()
    comparators: List[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATOR_ONLY_TOKENS:
            index += 1
            if index >= len(tokens):
                raise _invalid_range(raw_text, f"operator {token!r} is missing an operand")
            comparators.append(f"{token}{tokens[index]}")
        else:
            comparators.append(token)
        index += 1
    return comparators


def _compile_intersection(text: str, raw_text: str) -> List[_Clause]:
    """Compiles a whitespace-delimited comparator clause into DNF comparator clauses."""
    clauses: List[_Clause] = [[]]
    for token in _split_comparators(text, raw_text):
        match = _COMPARATOR_PATTERN.fullmatch(token)
        if match is None:
            raise _invalid_range(raw_text, f"malformed comparator {token!r}")
        operator = match.group("operator")
        operand = match.group("operand")
        if operator not in _VALID_OPERATORS:
            raise _invalid_range(raw_text, f"unsupported comparator operator {operator!r}")
        version, parts = _parse_operand(operand, raw_text)
        expansions = _expand_comparator(operator, version, parts)
        clauses = [clause + expansion for clause in clauses for expansion in expansions]
    return clauses


def _compile_hyphen_range(lower_text: str, upper_text: str, raw_text: str) -> List[_Clause]:
    """Compiles a hyphen range into inclusive lower/upper comparator inequalities."""
    lower_version, lower_parts = _parse_operand(lower_text, raw_text)
    upper_version, upper_parts = _parse_operand(upper_text, raw_text)
    clause: _Clause = []
    if lower_version is not None:
        clause.append((semver_solver.ComparatorOp.GE, lower_version))
    elif lower_parts[0] is not None:
        clause.append((semver_solver.ComparatorOp.GE, _fill_parts(lower_parts)))
    if upper_version is not None:
        clause.append((semver_solver.ComparatorOp.LE, upper_version))
    elif upper_parts[0] is not None:
        clause.append((semver_solver.ComparatorOp.LT, _wildcard_upper(upper_parts)))
    return [clause]


def _compile_clause(clause_text: str, raw_text: str) -> List[_Clause]:
    """Compiles one union alternative into DNF comparator clauses."""
    hyphen_parts = _HYPHEN_RANGE_SEPARATOR.split(clause_text)
    if len(hyphen_parts) == 1:
        return _compile_intersection(clause_text, raw_text)
    if len(hyphen_parts) != 2:
        raise _invalid_range(raw_text, "hyphen ranges must connect exactly two bounds")
    # The hyphen separator demands whitespace on both sides of an already stripped clause,
    # so both bounds are non-empty.
    lower_text = hyphen_parts[0].strip()
    upper_text = hyphen_parts[1].strip()
    return _compile_hyphen_range(lower_text, upper_text, raw_text)


@functools.lru_cache(maxsize=None)
def _compile_range(raw_text: str) -> _CompiledRange:
    """Compiles range text into disjunctive normal form comparator clauses."""
    trimmed = raw_text.strip()
    if not trimmed:
        raise _invalid_range(raw_text, "range expression is empty")
    if "," in trimmed:
        raise _invalid_range(raw_text, "commas are not permitted as comparator delimiters")
    compiled: _CompiledRange = []
    for raw_clause in trimmed.split("||"):
        clause_text = raw_clause.strip()
        if not clause_text:
            raise _invalid_range(raw_text, "range expression contains an empty union alternative")
        compiled.extend(_compile_clause(clause_text, raw_text))
    return compiled


def _evaluate_comparator(
    engine: semver_solver.VersionEngine,
    comparator: _Comparator,
    version: semver_solver.Version,
) -> bool:
    """Evaluates one comparator inequality against a candidate version's precedence."""
    operator, boundary = comparator
    precedence = engine.compare_precedence(version, boundary)
    if operator == semver_solver.ComparatorOp.EQ:
        return precedence == 0
    if operator == semver_solver.ComparatorOp.NE:
        return precedence != 0
    if operator == semver_solver.ComparatorOp.LT:
        return precedence < 0
    if operator == semver_solver.ComparatorOp.LE:
        return precedence <= 0
    if operator == semver_solver.ComparatorOp.GT:
        return precedence > 0
    return precedence >= 0


def _clause_matches(
    engine: semver_solver.VersionEngine,
    clause: _Clause,
    version: semver_solver.Version,
) -> bool:
    """Evaluates whether every comparator in a clause is satisfied by the candidate."""
    return all(_evaluate_comparator(engine, comparator, version) for comparator in clause)


def _targets_prerelease(
    clause: _Clause,
    version: semver_solver.Version,
) -> bool:
    """Checks whether a clause explicitly targets the candidate prerelease version triple."""
    for _operator, boundary in clause:
        if (
            boundary.is_prerelease
            and boundary.major == version.major
            and boundary.minor == version.minor
            and boundary.patch == version.patch
        ):
            return True
    return False


def _range_matches(
    engine: semver_solver.VersionEngine,
    compiled: _CompiledRange,
    version: semver_solver.Version,
    include_prerelease: bool,
) -> bool:
    """Evaluates a compiled range against a candidate version, filtering prereleases."""
    if include_prerelease:
        # Direct boundary inequality evaluation without numeric boundary shifting.
        return any(_clause_matches(engine, clause, version) for clause in compiled)
    if not version.is_prerelease:
        return any(_clause_matches(engine, clause, version) for clause in compiled)
    # A prerelease candidate only matches clauses that explicitly target its version triple.
    for clause in compiled:
        if _clause_matches(engine, clause, version) and _targets_prerelease(clause, version):
            return True
    return False


def _search_assignment(
    engine: semver_solver.VersionEngine,
    repository: semver_solver.PackageRepository,
    accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]],
    assignment: Dict[str, semver_solver.PackageRelease],
    derivation_steps: List[str],
    conflict_trail: List[str],
    conflicting_packages: Set[str],
) -> Optional[Tuple[Dict[str, semver_solver.PackageRelease], List[str]]]:
    """Performs MRV-ordered depth-first backtracking search over package releases."""
    unassigned = sorted(name for name in accumulated if name not in assignment)
    if not unassigned:
        # A complete consistent assignment satisfies all accumulated constraints.
        return assignment, derivation_steps

    candidate_map: Dict[str, List[semver_solver.PackageRelease]] = {}
    for name in unassigned:
        try:
            releases = repository.get_releases(name)
        except semver_solver.PackageNotFoundError:
            # Unregistered packages are treated as having zero candidate releases
            # so that PackageNotFoundError never escapes the solver.
            releases = []
            conflicting_packages.add(name)
        constraints = accumulated[name]
        candidate_map[name] = [
            release
            for release in releases
            if all(
                engine.satisfies(release.version, constraint, False)
                for _source, constraint in constraints
            )
        ]

    # Minimum Remaining Values selection with lexical tie-breaking for determinism.
    selected = min(unassigned, key=lambda name: (len(candidate_map[name]), name))
    candidates = candidate_map[selected]
    if not candidates:
        requesters = [source for source, _constraint in accumulated[selected]]
        conflicting_packages.add(selected)
        for requester in requesters:
            if requester != "root":
                conflicting_packages.add(requester)
        conflict_trail.append(
            f"No viable releases for '{selected}' satisfying constraints from {requesters}"
        )
        return None

    for candidate in candidates:
        # Assign the candidate and record the decision in the derivation sequence.
        next_assignment = dict(assignment)
        next_assignment[selected] = candidate
        next_steps = derivation_steps + [f"Assign '{selected}' to {candidate.version.format()}"]

        # Merge the candidate's declared dependencies into the accumulated constraints.
        next_accumulated = {
            name: list(constraints) for name, constraints in accumulated.items()
        }
        conflict_detected = False
        for dependency in candidate.dependencies:
            assigned = next_assignment.get(dependency.name)
            if assigned is not None:
                # A dependency on an assigned package must already be satisfied.
                if not engine.satisfies(assigned.version, dependency.range_constraint, False):
                    conflict_detected = True
                    conflicting_packages.add(selected)
                    conflicting_packages.add(dependency.name)
                    conflict_trail.append(
                        f"Conflict: '{selected}' {candidate.version.format()} requires "
                        f"'{dependency.name}' {dependency.range_constraint.raw_text} but "
                        f"{assigned.version.format()} is assigned"
                    )
                    break
            else:
                next_accumulated.setdefault(dependency.name, []).append(
                    (selected, dependency.range_constraint)
                )

        if conflict_detected:
            continue
        solution = _search_assignment(
            engine,
            repository,
            next_accumulated,
            next_assignment,
            next_steps,
            conflict_trail,
            conflicting_packages,
        )
        if solution is not None:
            return solution
        conflict_trail.append(f"Exhausted candidates for '{selected}'")

    return None


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # Validates SemVer 2.0.0 grammar and numeric leading-zero constraints, then
        # produces an immutable Version record capturing prerelease and build tuples.
        match = _SEMVER_PATTERN.fullmatch(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                f"Invalid semantic version {text!r}",
                text,
            )
        return _version_from_match(match)

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # Compares numeric components numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1
        # A normal version ranks higher than a prerelease sharing the same numbers.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # Compares prerelease segments positionally: numeric values numerically,
        # pre-release strings ASCII-lexicographically, numeric below string.
        for left_text, right_text in zip(v1.prerelease, v2.prerelease):
            if left_text == right_text:
                continue
            left_numeric = _is_numeric_identifier(left_text)
            right_numeric = _is_numeric_identifier(right_text)
            if left_numeric and right_numeric:
                # Conforming numeric identifiers cannot carry leading zeroes, so unequal
                # texts always denote unequal integer values.
                left_value = int(left_text)
                right_value = int(right_text)
                return -1 if left_value < right_value else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left_text < right_text else 1
        # A longer prerelease sequence ranks higher when the common prefix matches.
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Validates comparator, wildcard, caret, tilde, hyphen, and union syntax while
        # rejecting empty input, commas, empty union alternatives, and bare partials.
        # Compilation receives the exact caller-supplied text so that diagnostics retain
        # the original malformed range expression in InvalidRangeError.raw_range.
        _compile_range(text)
        # Stores the trimmed range expression as the canonical range text.
        return semver_solver.VersionRange(text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Compiles the range into disjunctive normal form comparator sets and tests
        # the candidate against every comparator in at least one clause.
        compiled = _compile_range(range_constraint.raw_text)
        return _range_matches(self, compiled, version, include_prerelease)


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexed release histories."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # Inserts the release and re-sorts the package history in descending
        # precedence order using version engine comparison.
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        index = len(releases) - 1
        while index > 0 and engine.compare_precedence(releases[index - 1].version, release.version) < 0:
            releases[index] = releases[index - 1]
            index -= 1
        releases[index] = release

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # Raises the contracted PackageNotFoundError for unregistered names.
        releases = self._packages.get(name)
        if releases is None:
            raise semver_solver.PackageNotFoundError(
                f"Package {name!r} is not registered in the repository",
                name,
            )
        # Produces a shallow copy of the descending sorted release list.
        return list(releases)

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # Checks membership of the package name in the release index.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # Produces the set of all registered package names.
        return set(self._packages)


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        # Coordinates with the version engine and package repository on demand.
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)
        # Initializes accumulated constraints from the root dependencies.
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()
        # Executes recursive backtracking depth-first search for a compatible assignment.
        solution = _search_assignment(
            engine,
            repository,
            accumulated,
            {},
            [],
            conflict_trail,
            conflicting_packages,
        )
        if solution is None:
            # Raises the contracted ResolutionConflictError with the derivation derived
            # from the accumulated conflict trail.
            explanation = (
                "; ".join(conflict_trail)
                if conflict_trail
                else "no compatible release assignment exists"
            )
            raise semver_solver.ResolutionConflictError(
                f"Dependencies cannot be satisfied: {explanation}",
                tuple(sorted(conflicting_packages)),
                explanation,
            )
        assignment, derivation_steps = solution
        # Compiles the selected package release mapping and decision sequence.
        selected_versions: Dict[str, semver_solver.Version] = {
            name: release.version for name, release in assignment.items()
        }
        return semver_solver.ResolutionOutcome(selected_versions, tuple(derivation_steps))


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
# LAST_CLEANED: 2026-11-08T04:18:47Z
# LAST_CHANGED: 2026-11-08T03:46:29Z
# CHANGE: No code change required: the target holds the complete, contract-compliant implementation (VersionEngine SemVer 2.0.0 parsing/precedence/range engine, PackageRepository descending-precedence storage, and MRV backtracking DependencySolver), restored to its last verified metadata-free content after the previous round's impasse. It passes static checks and the 'uninitialized' dirty reason is stale: the file contains no stub markers, defines every contracted class/operation, and retains its auto-generated __initialize__ registration block. The remaining pending verification feedback belongs to the companion pretense state machine, which is absent from this workspace and whose assertions contradict semver.compare_precedence.normal_vs_prerelease, semver.solver.compatible_assignment, and the Version.format contract; that escalation was already recorded via bin/fail and requires the pretense artifact to be corrected by its owning role. Re-delivering the verified implementation to clear the stale uninitialized state.
# COVERAGE_AUDIT: 2026-11-08T03:47:09Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T04:18:47Z
# PRETENSE_QA_AUDIT: 2026-11-08T04:18:36Z
# QA_AUDIT: 2026-11-08T03:46:54Z
# --- END AUTOFAB METADATA ---
