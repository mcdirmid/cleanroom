# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_044856_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-10-29T04:48:56.137174+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 340,131
#   Cached Inbound Tokens:   40,490,752
#   Outbound Tokens:         391,264
#   Total Tokens:            41,222,147
#   Financial Cost ($USD):   $0.4073
#   Wall Clock Duration:     1950.98s
#   Step Latencies (s):      [401.0, 656.9, 174.2, 235.1, 163.5, 194.3, 30.9, 153.7, 123.9, 134.5, 61.4, 71.7, 30.7, 41.1, 61.5, 30.7, 20.4]
#   Role Execution Rounds:   lib: 2, pretense: 6, pretense_coverage: 3, pretense_qa: 6 (Total: 17)
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
"""Interface specification for SemVer 2.0 parsing and dependency resolution.

This module defines the passive value records, domain exceptions, and the
polymorphic service protocols realized by ``semver_solver_impl``.
"""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __post_init__(self) -> None:
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
# LAST_CLEANED: 2026-10-29T04:55:31Z
# LAST_CHANGED: 2026-10-29T04:55:31Z
# CHANGE: Implement SemVer interface module: domain exceptions with __str__, ComparatorOp, frozen data records (Version/VersionRange/PackageDependency/PackageRelease/ResolutionOutcome), and VersionEngine/PackageRepository/DependencySolver protocol stubs matching low/semver_solver.pyi.
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete realization of SemVer 2.0 parsing and backtracking dependency resolution.

The module implements the ``semver_solver`` interface protocols as system-tier
singletons.  Search heuristics (Minimum Remaining Values variable ordering,
descending precedence value ordering, and conflict trail collection) follow the
algorithmic reference mechanics documented in ``backtracking_solver_ext``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cmp_to_key
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)

from benchmark_3.parts.semver_solver.lib import semver_solver


_NUMERIC_IDENTIFIER = r"(?:0|[1-9][0-9]*)"
_PRERELEASE_IDENTIFIER = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_PRERELEASE_PATTERN = (
    _PRERELEASE_IDENTIFIER
    + r"(?:\."
    + _PRERELEASE_IDENTIFIER
    + r")*"
)
_SEMVER_RE = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(" + _PRERELEASE_PATTERN + r"))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
_NUMBER_RE = re.compile(r"0|[1-9][0-9]*")
_PRERELEASE_RE = re.compile(_PRERELEASE_PATTERN)
_BUILD_RE = re.compile(r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*")

_OPERATOR_CHARS = "=!<>^~"
_ALLOWED_OPERATORS = frozenset({"", "=", "==", "!=", "<", "<=", ">", ">=", "^", "~"})
_WILDCARD_CHARS = frozenset({"*", "x", "X"})

_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]
_Clause = List[_Comparator]


@dataclass(frozen=True)
class _Operand:
    """Parsed range operand retaining wildcard positions and prerelease metadata."""

    numerics: Tuple[int, ...]
    wildcard: bool
    parts: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()


def _invalid_range(raw: str, detail: str) -> semver_solver.InvalidRangeError:
    return semver_solver.InvalidRangeError(
        f"Invalid version range {detail}: {raw!r}", raw
    )


def _parse_semver(text: str) -> semver_solver.Version:
    """Parse a strict SemVer 2.0.0 string into a Version record."""
    match = _SEMVER_RE.fullmatch(text)
    if match is None:
        raise semver_solver.InvalidVersionError(
            f"Invalid semantic version string: {text!r}", text
        )
    # Build and pre-release identifiers are optional capture groups.
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    build = tuple(match.group(5).split(".")) if match.group(5) else ()
    return semver_solver.Version(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        prerelease,
        build,
    )


def _is_numeric_identifier(identifier: str) -> bool:
    return identifier.isascii() and identifier.isdigit()


def _compare_versions(v1: semver_solver.Version, v2: semver_solver.Version) -> int:
    """Compare two versions using SemVer 2.0.0 precedence rules."""
    # POSTCONDITION: major, minor, and patch compare numerically.
    numeric_1 = (v1.major, v1.minor, v1.patch)
    numeric_2 = (v2.major, v2.minor, v2.patch)
    if numeric_1 < numeric_2:
        return -1
    if numeric_1 > numeric_2:
        return 1

    prerelease_1 = v1.prerelease
    prerelease_2 = v2.prerelease
    # POSTCONDITION: a normal version ranks above a pre-release version.
    if not prerelease_1 and not prerelease_2:
        return 0
    if not prerelease_1:
        return 1
    if not prerelease_2:
        return -1

    # POSTCONDITION: numeric identifiers compare numerically, alphanumeric
    # identifiers compare ASCII-lexicographically, numeric ranks below string.
    for left, right in zip(prerelease_1, prerelease_2):
        if left == right:
            continue
        left_numeric = _is_numeric_identifier(left)
        right_numeric = _is_numeric_identifier(right)
        if left_numeric and right_numeric:
            # Conforming numeric identifiers are canonical, so distinct
            # identifiers never compare equal as integers.
            return -1 if int(left) < int(right) else 1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left < right else 1

    # POSTCONDITION: a longer pre-release series ranks higher when the
    # common prefix matches (e.g. 1.0.0-alpha < 1.0.0-alpha.1).
    if len(prerelease_1) < len(prerelease_2):
        return -1
    if len(prerelease_1) > len(prerelease_2):
        return 1
    return 0


def _parse_operand(token: str) -> _Operand:
    """Parse a single comparator operand into numeric and wildcard components."""
    base = token
    build: Tuple[str, ...] = ()
    if "+" in base:
        build_parts = base.split("+")
        if len(build_parts) != 2:
            raise _invalid_range(token, "has malformed build metadata")
        base, build_text = build_parts
        if not build_text or _BUILD_RE.fullmatch(build_text) is None:
            raise _invalid_range(token, "has malformed build metadata")
        build = tuple(build_text.split("."))

    prerelease: Tuple[str, ...] = ()
    if "-" in base:
        base, prerelease_text = base.split("-", 1)
        if not prerelease_text or _PRERELEASE_RE.fullmatch(prerelease_text) is None:
            raise _invalid_range(token, "has malformed pre-release identifiers")
        prerelease = tuple(prerelease_text.split("."))

    parts = base.split(".")
    if len(parts) > 3:
        raise _invalid_range(token, "has too many version components")

    if any(part in _WILDCARD_CHARS for part in parts):
        # Wildcard operands are trailing placeholders and carry no metadata.
        if prerelease or build:
            raise _invalid_range(token, "combines wildcards with version metadata")
        numerics: List[int] = []
        seen_wildcard = False
        for part in parts:
            if part in _WILDCARD_CHARS:
                seen_wildcard = True
                continue
            if seen_wildcard:
                raise _invalid_range(token, "has a numeric component after a wildcard")
            if _NUMBER_RE.fullmatch(part) is None:
                raise _invalid_range(token, "has an invalid numeric component")
            numerics.append(int(part))
        return _Operand(tuple(numerics), True, len(parts), (), ())

    # POSTCONDITION: bare partial versions lacking wildcard characters are rejected.
    if len(parts) != 3:
        raise _invalid_range(token, "is a partial version without a wildcard")
    for part in parts:
        if _NUMBER_RE.fullmatch(part) is None:
            raise _invalid_range(token, "has an invalid numeric component")
    return _Operand(
        (int(parts[0]), int(parts[1]), int(parts[2])), False, 3, prerelease, build
    )


def _operand_version(operand: _Operand) -> semver_solver.Version:
    """Return the lowest concrete version represented by an operand."""
    numbers = list(operand.numerics)
    while len(numbers) < 3:
        numbers.append(0)
    return semver_solver.Version(
        numbers[0], numbers[1], numbers[2], operand.prerelease, operand.build
    )


def _wildcard_upper(operand: _Operand) -> semver_solver.Version:
    """Return the exclusive upper bound implied by a trailing wildcard."""
    numbers = list(operand.numerics)
    numbers[-1] += 1
    while len(numbers) < 3:
        numbers.append(0)
    return semver_solver.Version(numbers[0], numbers[1], numbers[2])


def _caret_upper(operand: _Operand, wildcard: bool) -> semver_solver.Version:
    """Expand a caret range to its exclusive upper bound."""
    if wildcard:
        positive_index: Optional[int] = None
        for index, value in enumerate(operand.numerics):
            if value > 0:
                positive_index = index
                break
        if positive_index is not None:
            numbers = list(operand.numerics[: positive_index + 1])
            numbers[positive_index] += 1
            while len(numbers) < 3:
                numbers.append(0)
            return semver_solver.Version(numbers[0], numbers[1], numbers[2])
        # All supplied numeric components are zero: bump the innermost one.
        if len(operand.numerics) == 2:
            return semver_solver.Version(0, 1, 0)
        return semver_solver.Version(1, 0, 0)

    major, minor, patch = operand.numerics
    if major > 0:
        return semver_solver.Version(major + 1, 0, 0)
    if minor > 0:
        return semver_solver.Version(0, minor + 1, 0)
    return semver_solver.Version(0, 0, patch + 1)


def _tilde_upper(operand: _Operand, wildcard: bool) -> semver_solver.Version:
    """Expand a tilde range to its exclusive upper bound."""
    if wildcard:
        numbers = list(operand.numerics)
        if len(numbers) >= 2:
            return semver_solver.Version(numbers[0], numbers[1] + 1, 0)
        return semver_solver.Version(numbers[0] + 1, 0, 0)
    major, minor, _ = operand.numerics
    return semver_solver.Version(major, minor + 1, 0)


def _never() -> _Clause:
    """Return a comparator set that no version can satisfy."""
    version = semver_solver.Version(0, 0, 0)
    return [
        (semver_solver.ComparatorOp.EQ, version),
        (semver_solver.ComparatorOp.NE, version),
    ]


def _expand_operand(operator: str, operand: _Operand) -> List[_Clause]:
    """Expand one comparator operand into disjunctive comparator-set alternatives."""
    op = semver_solver.ComparatorOp

    if not operand.wildcard:
        version = _operand_version(operand)
        if operator in ("", "=", "=="):
            return [[(op.EQ, version)]]
        if operator == "!=":
            return [[(op.NE, version)]]
        if operator == "<":
            return [[(op.LT, version)]]
        if operator == "<=":
            return [[(op.LE, version)]]
        if operator == ">":
            return [[(op.GT, version)]]
        if operator == ">=":
            return [[(op.GE, version)]]
        if operator == "^":
            return [[(op.GE, version), (op.LT, _caret_upper(operand, False))]]
        if operator == "~":
            return [[(op.GE, version), (op.LT, _tilde_upper(operand, False))]]
        raise _invalid_range(operator, "uses an unsupported operator")  # pragma: no cover (assumption: operator is validated by _ALLOWED_OPERATORS)

    # Wildcard operands express a half-open interval [lower, upper).
    if not operand.numerics:
        # A bare wildcard matches everything; only monotone bounds keep it.
        if operator in ("", "=", "==", "<=", ">="):
            return [[]]
        return [_never()]

    lower = _operand_version(operand)
    upper = _wildcard_upper(operand)
    if operator in ("", "=", "=="):
        return [[(op.GE, lower), (op.LT, upper)]]
    if operator == "!=":
        return [[(op.LT, lower)], [(op.GE, upper)]]
    if operator == "<":
        return [[(op.LT, lower)]]
    if operator == "<=":
        return [[(op.LT, upper)]]
    if operator == ">":
        return [[(op.GE, upper)]]
    if operator == ">=":
        return [[(op.GE, lower)]]
    if operator == "^":
        return [[(op.GE, lower), (op.LT, _caret_upper(operand, True))]]
    if operator == "~":
        return [[(op.GE, lower), (op.LT, _tilde_upper(operand, True))]]
    raise _invalid_range(operator, "uses an unsupported operator")  # pragma: no cover (assumption: operator is validated by _ALLOWED_OPERATORS)


def _tokenize(clause: str) -> List[Tuple[str, str]]:
    """Split a clause into whitespace-delimited (operator, operand) tokens."""
    tokens: List[Tuple[str, str]] = []
    index = 0
    length = len(clause)
    while index < length:
        if clause[index].isspace():
            index += 1
            continue
        operator = ""
        if clause[index] in _OPERATOR_CHARS:
            start = index
            while index < length and clause[index] in _OPERATOR_CHARS:
                index += 1
            operator = clause[start:index]
            if operator not in _ALLOWED_OPERATORS:
                raise _invalid_range(clause, "uses an unsupported operator")
            while index < length and clause[index].isspace():
                index += 1
            if index >= length:
                raise _invalid_range(clause, "has a missing version operand")
        start = index
        while index < length and not clause[index].isspace():
            index += 1
        operand = clause[start:index]
        if any(char in _OPERATOR_CHARS for char in operand):
            raise _invalid_range(clause, "has adjacent comparators without whitespace")
        tokens.append((operator, operand))
    return tokens


def _expand_hyphen(left_text: str, right_text: str) -> List[_Clause]:
    """Expand a hyphen range into inclusive lower and upper comparators."""
    if any(char in _OPERATOR_CHARS for char in left_text + right_text):
        raise _invalid_range(f"{left_text} - {right_text}", "has an operator in a hyphen endpoint")
    low = _parse_operand(left_text.strip())
    high = _parse_operand(right_text.strip())
    comparators: _Clause = []
    if not low.wildcard or low.numerics:
        comparators.append((semver_solver.ComparatorOp.GE, _operand_version(low)))
    if not high.wildcard:
        comparators.append((semver_solver.ComparatorOp.LE, _operand_version(high)))
    elif high.numerics:
        comparators.append(
            (semver_solver.ComparatorOp.LT, _wildcard_upper(high))
        )
    return [comparators]


def _expand_clause(clause: str) -> List[_Clause]:
    """Expand a single union clause into disjunctive comparator-set alternatives."""
    hyphen_parts = re.split(r"\s+-\s+", clause)
    if len(hyphen_parts) == 2:
        return _expand_hyphen(hyphen_parts[0], hyphen_parts[1])
    if len(hyphen_parts) > 2:
        raise _invalid_range(clause, "has more than one hyphen range")

    alternatives: List[_Clause] = [[]]
    for operator, operand_text in _tokenize(clause):
        operand = _parse_operand(operand_text)
        expanded = _expand_operand(operator, operand)
        combined: List[_Clause] = []
        for existing in alternatives:
            for addition in expanded:
                combined.append(existing + addition)
        alternatives = combined
    return alternatives


def _parse_expression(text: str) -> List[List[_Clause]]:
    """Parse a range expression into union clauses of comparator-set alternatives."""
    if not text:
        raise _invalid_range(text, "is empty")
    if "," in text:
        raise _invalid_range(text, "uses comma delimiters")
    clauses: List[List[_Clause]] = []
    for raw_clause in text.split("||"):
        clause = raw_clause.strip()
        if not clause:
            raise _invalid_range(text, "has an empty union clause")
        clauses.append(_expand_clause(clause))
    return clauses


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    def __init__(self) -> None:
        # Stateless engine; no private backing state is required.
        pass

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # POSTCONDITION: valid strings yield a Version; grammar or leading-zero
        # violations raise InvalidVersionError.
        return _parse_semver(text)

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        # POSTCONDITION: build metadata is ignored entirely by precedence.
        return _compare_versions(v1, v2)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # POSTCONDITION: raw_text stores the trimmed range expression.
        stripped = text.strip()
        try:
            _parse_expression(stripped)
        except semver_solver.InvalidRangeError as exc:
            raise semver_solver.InvalidRangeError(exc.message, text) from None
        return semver_solver.VersionRange(stripped)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        for alternatives in _parse_expression(range_constraint.raw_text.strip()):
            for comparators in alternatives:
                # POSTCONDITION: pre-release candidates are filtered out unless
                # the clause explicitly targets the same major/minor/patch tuple.
                if version.prerelease and not include_prerelease:
                    targets_prerelease = any(
                        bound.prerelease
                        and bound.major == version.major
                        and bound.minor == version.minor
                        and bound.patch == version.patch
                        for _, bound in comparators
                    )
                    if not targets_prerelease:
                        continue

                matched = True
                for operator, bound in comparators:
                    order = self.compare_precedence(version, bound)
                    if operator is semver_solver.ComparatorOp.EQ:
                        matched = order == 0
                    elif operator is semver_solver.ComparatorOp.NE:
                        matched = order != 0
                    elif operator is semver_solver.ComparatorOp.LT:
                        matched = order < 0
                    elif operator is semver_solver.ComparatorOp.LE:
                        matched = order <= 0
                    elif operator is semver_solver.ComparatorOp.GT:
                        matched = order > 0
                    else:
                        matched = order >= 0
                    if not matched:
                        break
                if matched:
                    return True
        return False


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        # POSTCONDITION: the release is indexed and kept in descending precedence.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: _compare_versions(
                    right.version, left.version
                )
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered descending."""
        # POSTCONDITION: unregistered names raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository.", name
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
        """Provides the set of all registered package names."""
        return set(self._packages)


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        # The search state is local to each resolve() invocation.
        pass

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to (requester, range) pairs.
        constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_candidates(package: str) -> List[semver_solver.PackageRelease]:
            # Unregistered packages evaluate to an empty candidate list; never
            # allow PackageNotFoundError to escape the solver boundary.
            if not repository.has_package(package):
                return []
            requirements = constraints[package]
            return [
                release
                for release in repository.get_releases(package)
                if all(
                    engine.satisfies(release.version, required)
                    for _, required in requirements
                )
            ]

        def backtrack() -> bool:
            unassigned = [name for name in constraints if name not in assignment]
            if not unassigned:
                return True

            # MRV variable selection: fewest viable candidates, then lexical name.
            candidate_map = {
                name: viable_candidates(name) for name in unassigned
            }
            selected = min(
                unassigned, key=lambda name: (len(candidate_map[name]), name)
            )
            candidates = candidate_map[selected]

            if not candidates:
                requesters = sorted(
                    {requester for requester, _ in constraints[selected]}
                )
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                if repository.has_package(selected):
                    conflict_trail.append(
                        f"No viable releases for '{selected}' satisfying "
                        f"constraints from {requesters}"
                    )
                else:
                    conflict_trail.append(
                        f"Package '{selected}' is not registered in the repository"
                    )
                return False

            # Value ordering: repository releases are already descending.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(
                    f"Assign '{selected}' to {candidate.version}"
                )

                conflict_detected = False
                newly_added: List[
                    Tuple[str, Tuple[str, semver_solver.VersionRange]]
                ] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        assigned = assignment[dependency.name]
                        if not engine.satisfies(
                            assigned.version, dependency.range_constraint
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires "
                                f"{dependency.name} "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and backtrack():
                    return True

                # Restore the constraint mapping and assignment for the next branch.
                for package_name, entry in newly_added:
                    constraints[package_name].remove(entry)
                    if not constraints[package_name]:
                        del constraints[package_name]
                del assignment[selected]
                derivation_steps.pop()

            conflicting_packages.add(selected)
            conflict_trail.append(
                f"All candidate releases for '{selected}' exhausted"
            )
            return False

        # POSTCONDITION: unsatisfiable searches surface ResolutionConflictError.
        if not backtrack():
            explanation = (
                "\n".join(conflict_trail)
                if conflict_trail
                else "No compatible resolution exists."
            )
            raise semver_solver.ResolutionConflictError(
                "Unable to resolve dependencies: " + explanation,
                tuple(sorted(conflicting_packages)),
                explanation,
            )

        # POSTCONDITION: successful search reports selected versions and decisions.
        selected_versions = {
            name: release.version for name, release in assignment.items()
        }
        return semver_solver.ResolutionOutcome(
            selected_versions, tuple(derivation_steps)
        )


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
# LAST_CLEANED: 2026-10-29T05:21:15Z
# LAST_CHANGED: 2026-10-29T05:17:04Z
# CHANGE: Remove contract-unreachable spans: total numeric prerelease comparison without equal-value continue; drop redundant empty/operator operand guards; trim caret/tilde wildcard fallbacks to reachable one/two-component cases; streamline tokenizer by removing trailing-whitespace break and empty-token guard; remove pre-empted clause comma guard; and pragma-annotate the two validated-operator fallbacks. Runtime behavior unchanged and re-verified.
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T05:21:15Z
# PRETENSE_QA_AUDIT: 2026-10-29T05:21:03Z
# --- END CLEANROOM METADATA ---
