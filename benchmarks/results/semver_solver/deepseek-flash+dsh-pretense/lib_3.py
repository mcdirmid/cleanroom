# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_205329_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-10-29T20:53:29.363703+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 281,248
#   Cached Inbound Tokens:   23,353,727
#   Outbound Tokens:         326,721
#   Total Tokens:            23,961,696
#   Financial Cost ($USD):   $0.3083
#   Wall Clock Duration:     1541.35s
#   Step Latencies (s):      [288.3, 360.0, 234.9, 91.8, 20.7, 102.5, 103.5, 297.6, 20.5, 102.2, 112.5, 81.7, 51.2, 41.0, 40.9, 20.4, 20.3]
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
"""Interface specification for SemVer 2.0 parsing and dependency resolution."""

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
        include_prerelease: bool = False,
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T20:58:11Z
# LAST_CHANGED: 2026-10-29T20:58:11Z
# CHANGE: Implement SemVer interface module: frozen data types (Version, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome), error hierarchy with structured attributes and message __str__, ComparatorOp enum, and VersionEngine/PackageRepository/DependencySolver protocols matching low/semver_solver.pyi
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
"""Implementation of SemVer 2.0 parsing, precedence, and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key
import re
from typing import Collection, Dict, List, Optional, Set, Tuple

from . import semver_solver
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)


_SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)

_CORE_IDENTIFIER = re.compile(r"0|[1-9][0-9]*")
_PRERELEASE_IDENTIFIER = re.compile(r"0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*")
_BUILD_IDENTIFIER = re.compile(r"[0-9a-zA-Z-]+")

_RANGE_OPERATORS = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")
_WILDCARD_PARTS = frozenset(("*", "x", "X"))

_RELATIONAL_COMPARATOR_OPERATIONS = {
    "<": semver_solver.ComparatorOp.LT,
    "<=": semver_solver.ComparatorOp.LE,
    ">": semver_solver.ComparatorOp.GT,
    ">=": semver_solver.ComparatorOp.GE,
}

_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]
_Clause = List[_Comparator]

# A comparator that no semantic version can satisfy; used for empty ranges.
_NOTHING_COMPARATOR: _Comparator = (
    semver_solver.ComparatorOp.LT,
    semver_solver.Version(0, 0, 0, ("0",)),
)


@dataclass(frozen=True)
class _VersionSpec:
    """Parsed version or wildcard token appearing inside a range expression."""

    core: Tuple[int, ...]
    wildcard: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    def to_version(self) -> semver_solver.Version:
        major = self.core[0] if len(self.core) > 0 else 0
        minor = self.core[1] if len(self.core) > 1 else 0
        patch = self.core[2] if len(self.core) > 2 else 0
        return semver_solver.Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=self.prerelease,
            build=self.build,
        )


def _invalid_range(raw_range: str, detail: str) -> semver_solver.InvalidRangeError:
    return semver_solver.InvalidRangeError(
        message=f"Invalid version range {raw_range!r}: {detail}",
        raw_range=raw_range,
    )


def _split_operator(token: str) -> Tuple[Optional[str], str]:
    for symbol in _RANGE_OPERATORS:
        if token.startswith(symbol):
            return symbol, token[len(symbol):]
    return None, token


def _parse_version_spec(text: str, raw_range: str) -> _VersionSpec:
    build_parts: Tuple[str, ...] = ()
    core_and_prerelease = text
    if "+" in core_and_prerelease:
        core_and_prerelease, build_text = core_and_prerelease.split("+", 1)
        if not build_text:
            raise _invalid_range(raw_range, f"empty build metadata in {text!r}")
        build_parts = tuple(build_text.split("."))
        for identifier in build_parts:
            if _BUILD_IDENTIFIER.fullmatch(identifier) is None:
                raise _invalid_range(raw_range, f"invalid build metadata in {text!r}")

    core_text = core_and_prerelease
    prerelease_parts: Tuple[str, ...] = ()
    if "-" in core_text:
        core_text, prerelease_text = core_text.split("-", 1)
        if not prerelease_text:
            raise _invalid_range(raw_range, f"empty pre-release in {text!r}")
        prerelease_parts = tuple(prerelease_text.split("."))
        for identifier in prerelease_parts:
            if _PRERELEASE_IDENTIFIER.fullmatch(identifier) is None:
                raise _invalid_range(raw_range, f"invalid pre-release in {text!r}")

    if not core_text:
        raise _invalid_range(raw_range, f"missing version core in {text!r}")

    parts = core_text.split(".")
    wildcard_index: Optional[int] = None
    for position, part in enumerate(parts):
        if part in _WILDCARD_PARTS:
            wildcard_index = position
            break

    if wildcard_index is None:
        # Bare partial versions lacking explicit wildcards are invalid.
        if len(parts) != 3:
            raise _invalid_range(
                raw_range,
                f"partial version {text!r} requires an explicit wildcard",
            )
        core_values: List[int] = []
        for part in parts:
            if _CORE_IDENTIFIER.fullmatch(part) is None:
                raise _invalid_range(raw_range, f"invalid version component in {text!r}")
            core_values.append(int(part))
        return _VersionSpec(
            core=tuple(core_values),
            wildcard=0,
            prerelease=prerelease_parts,
            build=build_parts,
        )

    if prerelease_parts or build_parts:
        raise _invalid_range(raw_range, f"wildcard version {text!r} cannot carry metadata")
    if len(parts) > 3 or wildcard_index > 2:
        raise _invalid_range(raw_range, f"malformed wildcard version {text!r}")
    for part in parts[wildcard_index:]:
        if part not in _WILDCARD_PARTS:
            raise _invalid_range(raw_range, f"malformed wildcard version {text!r}")
    prefix_values: List[int] = []
    for part in parts[:wildcard_index]:
        if _CORE_IDENTIFIER.fullmatch(part) is None:
            raise _invalid_range(raw_range, f"invalid version component in {text!r}")
        prefix_values.append(int(part))

    wildcard = 3 if wildcard_index == 0 else wildcard_index
    return _VersionSpec(core=tuple(prefix_values), wildcard=wildcard)


def _bump(spec: _VersionSpec) -> semver_solver.Version:
    if spec.wildcard == 1:
        return semver_solver.Version(spec.core[0] + 1, 0, 0)
    return semver_solver.Version(spec.core[0], spec.core[1] + 1, 0)


def _wildcard_range(spec: _VersionSpec) -> _Clause:
    return [
        (semver_solver.ComparatorOp.GE, spec.to_version()),
        (semver_solver.ComparatorOp.LT, _bump(spec)),
    ]


def _caret_range(spec: _VersionSpec) -> _Clause:
    lower = spec.to_version()
    if spec.wildcard == 0:
        major, minor, patch = spec.core
        if major > 0:
            upper = semver_solver.Version(major + 1, 0, 0)
        elif minor > 0:
            upper = semver_solver.Version(0, minor + 1, 0)
        else:
            upper = semver_solver.Version(0, 0, patch + 1)
    elif spec.wildcard == 1:
        major = spec.core[0]
        upper = semver_solver.Version(major + 1, 0, 0) if major > 0 else semver_solver.Version(1, 0, 0)
    else:
        major, minor = spec.core
        if major > 0:
            upper = semver_solver.Version(major + 1, 0, 0)
        elif minor > 0:
            upper = semver_solver.Version(0, minor + 1, 0)
        else:
            upper = semver_solver.Version(0, 1, 0)
    return [(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]


def _tilde_range(spec: _VersionSpec) -> _Clause:
    lower = spec.to_version()
    if spec.wildcard == 0:
        major, minor, _patch = spec.core
        upper = semver_solver.Version(major, minor + 1, 0)
    elif spec.wildcard == 1:
        upper = semver_solver.Version(spec.core[0] + 1, 0, 0)
    else:
        upper = semver_solver.Version(spec.core[0], spec.core[1] + 1, 0)
    return [(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]


def _expand_hyphen(lower: _VersionSpec, upper: _VersionSpec) -> _Clause:
    comparators: _Clause = []
    if lower.wildcard != 3:
        comparators.append((semver_solver.ComparatorOp.GE, lower.to_version()))
    if upper.wildcard == 0:
        comparators.append((semver_solver.ComparatorOp.LE, upper.to_version()))
    elif upper.wildcard != 3:
        comparators.append((semver_solver.ComparatorOp.LT, _bump(upper)))
    return comparators


def _relational_comparators(operator: str, spec: _VersionSpec) -> _Clause:
    lower = spec.to_version()
    if spec.wildcard == 0:
        return [(_RELATIONAL_COMPARATOR_OPERATIONS[operator], lower)]
    upper_exclusive = _bump(spec)
    # Wildcard relational comparators expand to inclusive/exclusive boundaries.
    wildcard_expansions: Dict[str, _Comparator] = {
        ">": (semver_solver.ComparatorOp.GE, upper_exclusive),
        ">=": (semver_solver.ComparatorOp.GE, lower),
        "<": (semver_solver.ComparatorOp.LT, lower),
        "<=": (semver_solver.ComparatorOp.LT, upper_exclusive),
    }
    return [wildcard_expansions[operator]]


def _expand_comparator(
    operator: Optional[str],
    spec: _VersionSpec,
) -> List[_Clause]:
    if spec.wildcard == 3:
        # A bare wildcard admits everything; < and > admit nothing.
        if operator in (None, "=", "==", ">=", "<="):
            return [[]]
        return [[_NOTHING_COMPARATOR]]

    if operator is None or operator in ("=", "=="):
        if spec.wildcard == 0:
            return [[(semver_solver.ComparatorOp.EQ, spec.to_version())]]
        return [_wildcard_range(spec)]

    if operator == "!=":
        if spec.wildcard == 0:
            return [[(semver_solver.ComparatorOp.NE, spec.to_version())]]
        lower = spec.to_version()
        upper = _bump(spec)
        return [
            [(semver_solver.ComparatorOp.LT, lower)],
            [(semver_solver.ComparatorOp.GE, upper)],
        ]

    if operator == "^":
        return [_caret_range(spec)]

    if operator == "~":
        return [_tilde_range(spec)]

    # Every remaining recognized operator is relational (<, <=, >, >=).
    return [_relational_comparators(operator, spec)]


def _merge(alternatives: List[_Clause], options: List[_Clause]) -> List[_Clause]:
    merged: List[_Clause] = []
    for alternative in alternatives:
        for option in options:
            merged.append(alternative + option)
    return merged


def _compile_clause(clause: str, raw_range: str) -> List[_Clause]:
    tokens = clause.split()
    alternatives: List[_Clause] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        operator, remainder = _split_operator(token)
        if operator is not None and not remainder:
            if index + 1 >= len(tokens):
                raise _invalid_range(raw_range, f"operator {token!r} has no target version")
            remainder = tokens[index + 1]
            index += 1
        if operator is None and remainder == "-":
            raise _invalid_range(raw_range, "hyphen range is missing a lower bound")
        if operator is None:
            if index + 2 < len(tokens) and tokens[index + 1] == "-":
                lower = _parse_version_spec(remainder, raw_range)
                upper = _parse_version_spec(tokens[index + 2], raw_range)
                alternatives = _merge(alternatives, [_expand_hyphen(lower, upper)])
                index += 3
                continue
            if index + 1 < len(tokens) and tokens[index + 1] == "-":
                raise _invalid_range(raw_range, "hyphen range is missing an upper bound")
        spec = _parse_version_spec(remainder, raw_range)
        alternatives = _merge(alternatives, _expand_comparator(operator, spec))
        index += 1
    return alternatives


def _compile_range(text: str, raw_range: str) -> List[_Clause]:
    stripped = text.strip()
    if not stripped:
        raise _invalid_range(raw_range, "empty range expression")
    if "," in stripped:
        raise _invalid_range(raw_range, "comma delimiters are not permitted")
    alternatives: List[_Clause] = []
    for clause_text in stripped.split("||"):
        clause = clause_text.strip()
        if not clause:
            raise _invalid_range(raw_range, "empty union clause")
        alternatives.extend(_compile_clause(clause, raw_range))
    return alternatives


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    def __init__(self) -> None:
        # Stateless engine: no backing state is required.
        pass

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        match = _SEMVER_PATTERN.fullmatch(text)
        if match is None:
            # Grammar or leading-zero violation.
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version string {text!r}",
                raw_text=text,
            )
        prerelease_text = match.group("prerelease")
        build_text = match.group("build")
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build = tuple(build_text.split(".")) if build_text else ()
        # Valid SemVer 2.0.0 strings become immutable Version records.
        return semver_solver.Version(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=prerelease,
            build=build,
        )

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        # Major, minor, and patch compare numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1

        # A normal version ranks higher than a pre-release sharing its core.
        if not v1.prerelease:
            return 0 if not v2.prerelease else 1
        if not v2.prerelease:
            return -1

        # Pre-release segments compare position by position.
        for left_identifier, right_identifier in zip(v1.prerelease, v2.prerelease):
            left_numeric = left_identifier.isdigit()
            right_numeric = right_identifier.isdigit()
            if left_numeric and right_numeric:
                left_value = int(left_identifier)
                right_value = int(right_identifier)
                if left_value != right_value:
                    return -1 if left_value < right_value else 1
            elif left_numeric:
                # Numeric identifiers rank below non-numeric identifiers.
                return -1
            elif right_numeric:
                return 1
            elif left_identifier != right_identifier:
                return -1 if left_identifier < right_identifier else 1

        # A longer pre-release sequence ranks higher when the common prefix matches.
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return 1 if len(v1.prerelease) > len(v2.prerelease) else -1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        trimmed = text.strip()
        # Validate the complete range expression, storing the trimmed text.
        _compile_range(trimmed, trimmed)
        return semver_solver.VersionRange(raw_text=trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        alternatives = _compile_range(range_constraint.raw_text, range_constraint.raw_text)
        for comparators in alternatives:
            # A candidate satisfies a clause when every comparator matches.
            matched = True
            for comparator_operation, boundary in comparators:
                precedence = self.compare_precedence(version, boundary)
                if comparator_operation is semver_solver.ComparatorOp.EQ:
                    matched = precedence == 0
                elif comparator_operation is semver_solver.ComparatorOp.NE:
                    matched = precedence != 0
                elif comparator_operation is semver_solver.ComparatorOp.LT:
                    matched = precedence < 0
                elif comparator_operation is semver_solver.ComparatorOp.LE:
                    matched = precedence <= 0
                elif comparator_operation is semver_solver.ComparatorOp.GT:
                    matched = precedence > 0
                else:
                    matched = precedence >= 0
                if not matched:
                    break
            if not matched:
                continue
            # Pre-release versions only match when the clause explicitly targets
            # a pre-release sharing the same major, minor, and patch numbers.
            if version.is_prerelease and not include_prerelease:
                targets_prerelease = any(
                    boundary.is_prerelease
                    and boundary.major == version.major
                    and boundary.minor == version.minor
                    and boundary.patch == version.patch
                    for _operation, boundary in comparators
                )
                if not targets_prerelease:
                    continue
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
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # Maintain descending version precedence order using the engine.
        releases.sort(
            key=cmp_to_key(lambda left, right: engine.compare_precedence(left.version, right.version)),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package {name!r} is not registered",
                package_name=name,
            )
        # Produce a shallow copy so callers cannot mutate internal ordering.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        return set(self._packages)


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints: package name -> (requester, version range).
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(("root", dependency.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(name: str) -> List[semver_solver.PackageRelease]:
            try:
                available = repository.get_releases(name)
            except semver_solver.PackageNotFoundError:
                # Unregistered packages evaluate to an empty candidate list.
                return []
            constraints = accumulated.get(name, [])
            viable = [
                release
                for release in available
                if all(engine.satisfies(release.version, rng) for _source, rng in constraints)
            ]
            # Explore values in descending version precedence order.
            viable.sort(
                key=cmp_to_key(lambda left, right: engine.compare_precedence(left.version, right.version)),
                reverse=True,
            )
            return viable

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True

            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {
                name: viable_releases(name) for name in unassigned
            }
            # Minimum Remaining Values heuristic with lexical tie-breaking.
            selected = min(unassigned, key=lambda name: (len(candidates_map[name]), name))
            candidates = candidates_map[selected]

            if not candidates:
                requesters = sorted({source for source, _rng in accumulated[selected]})
                conflicting_packages.add(selected)
                conflicting_packages.update(source for source in requesters if source != "root")
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False

            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                # Forward checking of the candidate's declared dependencies.
                for dependency in candidate.dependencies:
                    assigned_release = assignment.get(dependency.name)
                    if assigned_release is not None:
                        if not engine.satisfies(assigned_release.version, dependency.range_constraint):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} "
                                f"{dependency.range_constraint.raw_text} but "
                                f"{assigned_release.version} is assigned"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and backtrack():
                    return True

                # Undo this candidate's assignment and introduced constraints.
                for package_name, entry in newly_added:
                    package_constraints = accumulated.get(package_name)
                    if package_constraints is not None and entry in package_constraints:
                        package_constraints.remove(entry)
                        if not package_constraints:
                            del accumulated[package_name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if backtrack():
            selected_versions = {
                name: release.version for name, release in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        explanation = "\n".join(conflict_trail)
        raise semver_solver.ResolutionConflictError(
            message=f"Unable to resolve dependencies: {explanation}",
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
# LAST_CLEANED: 2026-10-29T21:18:59Z
# LAST_CHANGED: 2026-10-29T21:08:17Z
# CHANGE: Eliminate unreachable defensive raises in range operator dispatch: split relational comparison handling into a dedicated _relational_comparators helper covering <, <=, >, >= with a table-driven wildcard boundary expansion, so every recognized operator is dispatched by an actual branch and no dead defensive rejection remains. SemVer parsing, range expansion semantics, repository ordering, and backtracking solver behavior are unchanged
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T21:18:59Z
# PRETENSE_QA_AUDIT: 2026-10-29T21:18:40Z
# --- END CLEANROOM METADATA ---
