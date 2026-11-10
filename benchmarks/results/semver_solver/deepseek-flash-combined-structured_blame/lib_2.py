# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_045230_deepseek-flash_semver_solver_combined
# Timestamp: 2026-11-08T04:52:30.868775+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 569,430
#   Cached Inbound Tokens:   55,564,928
#   Outbound Tokens:         518,403
#   Total Tokens:            56,652,761
#   Financial Cost ($USD):   $0.5632
#   Wall Clock Duration:     2815.94s
#   Step Latencies (s):      [176.6, 353.1, 10.1, 457.7, 221.8, 84.3, 304.5, 187.3, 10.1, 30.6, 40.9, 10.1, 10.1, 237.8, 10.1, 85.8, 43.0, 10.1, 10.1, 365.1, 176.2, 248.3, 114.6, 102.6, 83.9, 186.8, 20.4, 145.3, 176.6, 10.2, 51.0, 94.4, 20.4, 10.1]
#   Role Execution Rounds:   coverage: 4, lib: 3, pretense: 8, pretense_coverage: 4, pretense_qa: 8, qa: 4, test: 3 (Total: 34)
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
"""Library interface for SemVer 2.0.0 parsing, precedence comparison, and dependency resolution."""

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

    def __str__(self) -> str:
        """Returns the diagnostic message carried by this error."""
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
        return bool(self.prerelease)

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        # Canonical form is major.minor.patch followed by optional -prerelease and +build.
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
# LAST_CLEANED: 2026-11-08T04:58:29Z
# LAST_CHANGED: 2026-11-08T04:58:29Z
# CHANGE: Implement interface module: non-frozen dataclass exceptions with message __str__, frozen data types (Version with format/__str__/is_prerelease, VersionRange with __str__) and @poly_type protocol stubs for VersionEngine, PackageRepository, and DependencySolver matching the low-level specification.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete realization of SemVer 2.0.0 parsing, precedence, and dependency resolution."""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)
from . import semver_solver

_Comparator = Tuple[str, semver_solver.Version]
_Alternatives = List[List[_Comparator]]

_NUMERIC_IDENTIFIER = r"(?:0|[1-9]\d*)"
_PRERELEASE_IDENTIFIER = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_IDENTIFIER = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    rf"(?P<major>{_NUMERIC_IDENTIFIER})"
    rf"\.(?P<minor>{_NUMERIC_IDENTIFIER})"
    rf"\.(?P<patch>{_NUMERIC_IDENTIFIER})"
    rf"(?:-(?P<prerelease>{_PRERELEASE_IDENTIFIER}(?:\.{_PRERELEASE_IDENTIFIER})*))?"
    rf"(?:\+(?P<build>{_BUILD_IDENTIFIER}(?:\.{_BUILD_IDENTIFIER})*))?"
)

_WILDCARD_COMPONENT = r"(?:\*|[xX]|0|[1-9]\d*)"
_WILDCARD_RE = re.compile(rf"{_WILDCARD_COMPONENT}(?:\.{_WILDCARD_COMPONENT})*")

_PURE_OPERATORS = ("==", "!=", ">=", "<=", ">", "<", "=", "^", "~")


def _match_version(text: str) -> Optional[semver_solver.Version]:
    """Matches text against the SemVer 2.0.0 grammar without raising."""
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        return None
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    # POSTCONDITION: decompose into numeric and tuple fields.
    return semver_solver.Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=tuple(prerelease_text.split(".")) if prerelease_text else (),
        build=tuple(build_text.split(".")) if build_text else (),
    )


def _parse_wildcard(text: str) -> Optional[Tuple[int, ...]]:
    """Parses a wildcard expression into the numeric prefix preceding the first wildcard."""
    if _WILDCARD_RE.fullmatch(text) is None:
        return None
    parts = text.split(".")
    if len(parts) > 3:
        return None
    prefix: List[int] = []
    wildcard_seen = False
    for part in parts:
        if part in ("*", "x", "X"):
            wildcard_seen = True
            continue
        if wildcard_seen:
            return None
        prefix.append(int(part))
    if not wildcard_seen:
        return None
    return tuple(prefix)


def _pad3(prefix: Tuple[int, ...]) -> Tuple[int, int, int]:
    """Pads a numeric wildcard prefix with zeroes up to three components."""
    values = [0, 0, 0]
    for index, component in enumerate(prefix):
        values[index] = component
    return (values[0], values[1], values[2])


def _wildcard_lower(prefix: Tuple[int, ...]) -> semver_solver.Version:
    """Produces the inclusive lower bound covered by a wildcard expression."""
    major, minor, patch = _pad3(prefix)
    return semver_solver.Version(major, minor, patch)


def _wildcard_upper(prefix: Tuple[int, ...]) -> Optional[semver_solver.Version]:
    """Produces the exclusive upper bound covered by a wildcard expression."""
    if not prefix:
        return None
    if len(prefix) == 1:
        return semver_solver.Version(prefix[0] + 1, 0, 0)
    return semver_solver.Version(prefix[0], prefix[1] + 1, 0)


def _caret_upper(version: semver_solver.Version) -> semver_solver.Version:
    """Computes the exclusive upper bound of a caret range over a full version."""
    # Boundary is the first non-zero numeric component per SemVer caret semantics.
    if version.major != 0:
        return semver_solver.Version(version.major + 1, 0, 0)
    if version.minor != 0:
        return semver_solver.Version(0, version.minor + 1, 0)
    if version.patch != 0:
        return semver_solver.Version(0, 0, version.patch + 1)
    return semver_solver.Version(0, 0, 1)


def _tilde_upper(version: semver_solver.Version) -> semver_solver.Version:
    """Computes the exclusive upper minor bound of a tilde range over a full version."""
    return semver_solver.Version(version.major, version.minor + 1, 0)


def _caret_upper_for_prefix(prefix: Tuple[int, ...]) -> Optional[semver_solver.Version]:
    """Computes the exclusive upper bound of a caret range over a wildcard expression."""
    if not prefix:
        return None
    padded = _pad3(prefix)
    for index, component in enumerate(padded):
        if component != 0:
            upper = [padded[0], padded[1], padded[2]]
            upper[index] += 1
            for trailing in range(index + 1, 3):
                upper[trailing] = 0
            return semver_solver.Version(upper[0], upper[1], upper[2])
    # All specified components are zero: advance the last specified boundary.
    upper = [padded[0], padded[1], padded[2]]
    boundary = len(prefix) - 1
    upper[boundary] += 1
    for trailing in range(boundary + 1, 3):
        upper[trailing] = 0
    return semver_solver.Version(upper[0], upper[1], upper[2])


def _tilde_upper_for_prefix(prefix: Tuple[int, ...]) -> Optional[semver_solver.Version]:
    """Computes the exclusive upper bound of a tilde range over a wildcard expression."""
    if not prefix:
        return None
    padded = _pad3(prefix)
    upper = [padded[0], padded[1], padded[2]]
    boundary = len(prefix) - 1
    upper[boundary] += 1
    for trailing in range(boundary + 1, 3):
        upper[trailing] = 0
    return semver_solver.Version(upper[0], upper[1], upper[2])


def _expand_version_op(
    op: str,
    version: semver_solver.Version,
    raw_range: str,
) -> _Alternatives:
    """Expands a comparator or prefix operator applied to a full semantic version."""
    if op in ("", "=", "=="):
        return [[("==", version)]]
    if op == "!=":
        return [[("!=", version)]]
    if op in ("<", "<=", ">", ">="):
        return [[(op, version)]]
    if op == "^":
        return [[(">=", version), ("<", _caret_upper(version))]]
    if op == "~":
        return [[(">=", version), ("<", _tilde_upper(version))]]
    raise semver_solver.InvalidRangeError(  # unreachable (assumption: operators are validated before expansion)
        f"Unsupported operator '{op}' in range '{raw_range}'",
        raw_range,
    )


def _expand_wildcard_op(
    op: str,
    prefix: Tuple[int, ...],
    raw_range: str,
) -> _Alternatives:
    """Expands a comparator or prefix operator applied to a wildcard expression."""
    lower = _wildcard_lower(prefix)
    upper = _wildcard_upper(prefix)
    if op in ("", "=", "=="):
        if upper is None:
            return [[]]
        return [[(">=", lower), ("<", upper)]]
    if op == "!=":
        if upper is None:
            return []
        return [[("<", lower)], [(">=", upper)]]
    if op == ">=":
        if upper is None:
            return [[]]
        return [[(">=", lower)]]
    if op == ">":
        if upper is None:
            return []
        return [[(">=", upper)]]
    if op == "<":
        if upper is None:
            return []
        return [[("<", lower)]]
    if op == "<=":
        if upper is None:
            return [[]]
        return [[("<", upper)]]
    if op == "^":
        caret_upper = _caret_upper_for_prefix(prefix)
        if caret_upper is None:
            return [[]]
        return [[(">=", lower), ("<", caret_upper)]]
    if op == "~":
        tilde_upper = _tilde_upper_for_prefix(prefix)
        if tilde_upper is None:
            return [[]]
        return [[(">=", lower), ("<", tilde_upper)]]
    raise semver_solver.InvalidRangeError(  # unreachable (assumption: operators are validated before expansion)
        f"Unsupported operator '{op}' in range '{raw_range}'",
        raw_range,
    )


def _hyphen_alternative(left_text: str, right_text: str, raw_range: str) -> _Alternatives:
    """Expands a hyphen range ('bound1 - bound2') into a single comparator conjunction."""
    comparators: List[_Comparator] = []
    left_prefix = _parse_wildcard(left_text)
    if left_prefix is not None:
        comparators.append((">=", _wildcard_lower(left_prefix)))
    else:
        left_version = _match_version(left_text)
        if left_version is None:
            raise semver_solver.InvalidRangeError(
                f"Malformed lower bound '{left_text}' in range '{raw_range}'",
                raw_range,
            )
        comparators.append((">=", left_version))
    right_prefix = _parse_wildcard(right_text)
    if right_prefix is not None:
        right_upper = _wildcard_upper(right_prefix)
        if right_upper is not None:
            comparators.append(("<", right_upper))
    else:
        right_version = _match_version(right_text)
        if right_version is None:
            raise semver_solver.InvalidRangeError(
                f"Malformed upper bound '{right_text}' in range '{raw_range}'",
                raw_range,
            )
        comparators.append(("<=", right_version))
    return [comparators]


def _split_operator(token: str) -> Tuple[str, str]:
    """Splits a leading relational or prefix operator from a range token."""
    for candidate in _PURE_OPERATORS:
        if token.startswith(candidate):
            return candidate, token[len(candidate):]
    return "", token


def _parse_clause_alternatives(clause: str, raw_range: str) -> _Alternatives:
    """Compiles one whitespace-delimited clause into disjunctive normal form."""
    tokens = clause.split()
    # A standalone '-' token introduces a hyphen range whose bounds are separated by spaces.
    if "-" in tokens:
        if len(tokens) != 3 or tokens[1] != "-":
            raise semver_solver.InvalidRangeError(
                f"Malformed hyphen range '{clause}' in range '{raw_range}'",
                raw_range,
            )
        return _hyphen_alternative(tokens[0], tokens[2], raw_range)
    alternatives: _Alternatives = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _PURE_OPERATORS:
            op = token
            if index + 1 >= len(tokens):
                raise semver_solver.InvalidRangeError(
                    f"Missing operand for operator '{op}' in range '{raw_range}'",
                    raw_range,
                )
            operand_text = tokens[index + 1]
            index += 2
        else:
            op, operand_text = _split_operator(token)
            index += 1
        prefix = _parse_wildcard(operand_text)
        if prefix is not None:
            atom_alternatives = _expand_wildcard_op(op, prefix, raw_range)
        else:
            version = _match_version(operand_text)
            if version is None:
                raise semver_solver.InvalidRangeError(
                    f"Malformed version or wildcard '{operand_text}' in range '{raw_range}'",
                    raw_range,
                )
            atom_alternatives = _expand_version_op(op, version, raw_range)
        combined: _Alternatives = []
        for existing in alternatives:
            for alternative in atom_alternatives:
                combined.append(existing + alternative)
        alternatives = combined
    return alternatives


def _compile_range(raw_text: str) -> _Alternatives:
    """Compiles a raw range expression into disjunctive normal form comparator sets."""
    trimmed = raw_text.strip()
    if not trimmed:
        raise semver_solver.InvalidRangeError(
            "Version range expression must not be empty",
            raw_text,
        )
    if "," in trimmed:
        raise semver_solver.InvalidRangeError(
            f"Comma delimiters are not permitted in range '{raw_text}'",
            raw_text,
        )
    parts = trimmed.split("||")
    if any(not part.strip() for part in parts):
        raise semver_solver.InvalidRangeError(
            f"Empty union clause in range '{raw_text}'",
            raw_text,
        )
    alternatives: _Alternatives = []
    for part in parts:
        alternatives.extend(_parse_clause_alternatives(part.strip(), raw_text))
    return alternatives


def _compare(
    engine: semver_solver.VersionEngine,
    version: semver_solver.Version,
    op: str,
    bound: semver_solver.Version,
) -> bool:
    """Evaluates one normalized comparator against a candidate version."""
    result = engine.compare_precedence(version, bound)
    if op == "==":
        return result == 0
    if op == "!=":
        return result != 0
    if op == "<":
        return result < 0
    if op == "<=":
        return result <= 0
    if op == ">":
        return result > 0
    if op == ">=":
        return result >= 0
    return False  # unreachable (assumption: comparators are normalized during compilation)


def _targets_prerelease(
    alternatives: _Alternatives,
    version: semver_solver.Version,
) -> bool:
    """Checks whether the range explicitly targets the candidate's prerelease version tuple."""
    for comparators in alternatives:
        for _, bound in comparators:
            if (
                bound.prerelease
                and bound.major == version.major
                and bound.minor == version.minor
                and bound.patch == version.patch
            ):
                return True
    return False


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        version = _match_version(text)
        if version is None:
            # PRECONDITION: grammar or leading zero violations raise.
            raise semver_solver.InvalidVersionError(
                f"Invalid semantic version: '{text}'",
                text,
            )
        return version

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        # POSTCONDITION: compare numeric components in sequence.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return left - right
        # POSTCONDITION: build metadata is never inspected.
        prerelease_left = v1.prerelease
        prerelease_right = v2.prerelease
        # POSTCONDITION: normal ranks above prerelease.
        if not prerelease_left and not prerelease_right:
            return 0
        if not prerelease_left:
            return 1
        if not prerelease_right:
            return -1
        # POSTCONDITION: numeric vs string segment ordering.
        for left, right in zip(prerelease_left, prerelease_right):
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                left_value = int(left)
                right_value = int(right)
                if left_value != right_value:
                    return left_value - right_value
            elif left_numeric:
                return -1
            elif right_numeric:
                return 1
            elif left != right:
                return -1 if left < right else 1
        if len(prerelease_left) != len(prerelease_right):
            # A longer prerelease sequence with a matching prefix ranks higher.
            return len(prerelease_left) - len(prerelease_right)
        return 0

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # POSTCONDITION: raw_text stores the trimmed expression.
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
        """Evaluates whether a semantic version satisfies a range constraint."""
        alternatives = _compile_range(range_constraint.raw_text)
        # POSTCONDITION: prereleases match only explicitly targeted ranges.
        if version.is_prerelease and not include_prerelease:
            if not _targets_prerelease(alternatives, version):
                return False
        # POSTCONDITION: true when every comparator of one clause holds.
        for comparators in alternatives:
            if all(_compare(self, version, op, bound) for op, bound in comparators):
                return True
        return False


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    def __init__(self) -> None:
        """Initializes the package name to release list index."""
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        # POSTCONDITION: insert and re-sort descending by precedence.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_solver.VersionEngine)

        def _descending(
            left: semver_solver.PackageRelease,
            right: semver_solver.PackageRelease,
        ) -> int:
            return engine.compare_precedence(right.version, left.version)

        releases.sort(key=cmp_to_key(_descending))

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        # PRECONDITION: unregistered names raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository",
                name,
            )
        # POSTCONDITION: expose a shallow copy of the sorted releases.
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
        # POSTCONDITION: all indexed package names.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        repository = get_singleton(semver_solver.PackageRepository)
        engine = get_singleton(semver_solver.VersionEngine)
        accumulated_constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated_constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def _viable_releases(name: str) -> List[semver_solver.PackageRelease]:
            # Unregistered packages evaluate to zero candidates without leaking PackageNotFoundError.
            if not repository.has_package(name):
                return []
            return [
                release
                for release in repository.get_releases(name)
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated_constraints[name]
                )
            ]

        def _backtrack() -> bool:
            unassigned = [
                name for name in accumulated_constraints if name not in assignment
            ]
            if not unassigned:
                return True
            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for name in unassigned:
                candidates_map[name] = _viable_releases(name)
            # Minimum Remaining Values selection with lexical tie-breaking.
            selected = min(unassigned, key=lambda name: (len(candidates_map[name]), name))
            candidates = candidates_map[selected]
            if not candidates:
                requesters = [source for source, _ in accumulated_constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # Value ordering: explore candidates in descending version precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
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
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated_constraints.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and _backtrack():
                    return True
                # Backtrack: undo assignments and constraints introduced by this candidate.
                for package_name, entry in newly_added:
                    accumulated_constraints[package_name].remove(entry)
                    if not accumulated_constraints[package_name]:
                        del accumulated_constraints[package_name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if _backtrack():
            selected_versions = {
                name: release.version for name, release in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )
        # PRECONDITION: unsatisfiable searches raise a conflict.
        explanation = " | ".join(conflict_trail)
        raise semver_solver.ResolutionConflictError(
            f"Unable to resolve dependencies: {explanation}",
            tuple(sorted(conflicting_packages)),
            explanation,
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
# LAST_CLEANED: 2026-11-08T05:39:22Z
# LAST_CHANGED: 2026-11-08T05:11:11Z
# CHANGE: Prune the duplicated empty-clause token guard in _parse_clause_alternatives: range compilation already rejects every empty union clause with InvalidRangeError and dispatches each trimmed clause, so the guard was structurally unreachable under the contracted range grammar.
# COVERAGE_AUDIT: 2026-11-08T05:11:42Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T05:39:22Z
# PRETENSE_QA_AUDIT: 2026-11-08T05:39:01Z
# QA_AUDIT: 2026-11-08T05:11:29Z
# --- END AUTOFAB METADATA ---
