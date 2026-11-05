# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_003353_deepseek-flash_semver_solver
# Timestamp: 2026-11-05T00:33:53.825858+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 192,389
#   Cached Inbound Tokens:   8,369,152
#   Outbound Tokens:         203,259
#   Total Tokens:            8,764,800
#   Financial Cost ($USD):   $0.1759
#   Wall Clock Duration:     1071.05s
#   Step Latencies (s):      [302.0, 313.2, 54.4, 42.4, 10.3, 232.9, 136.9, 10.3, 128.4, 115.4, 10.3, 10.4]
#   Role Execution Rounds:   coverage: 3, lib: 3, qa: 4, test: 2 (Total: 12)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       30
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Library interface for SemVer 2.0.0 parsing, ranges, and dependency resolution."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Collection, Dict, List, Mapping, Optional, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __str__(self) -> str:
        """Returns the diagnostic message."""
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
        - MUST trim surrounding whitespace around range expressions and store the trimmed expression in raw_text.
        - WHEN text is empty, contains only whitespace, contains empty union clauses, uses comma delimiters, or violates range syntax, MUST raise InvalidRangeError.
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
        - WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False unless range explicitly targets that prerelease.
        - WHEN include_prerelease is True, MUST evaluate candidate prerelease version directly against comparator boundary inequalities using precedence ordering without shifting numerical boundaries.
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
# LAST_CLEANED: 2026-11-05T00:38:44Z
# LAST_CHANGED: 2026-11-05T00:38:44Z
# CHANGE: Implemented interface data types, ComparatorOp, and protocol declarations with concrete Version/VersionRange formatting and dataclass exceptions
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from dataclasses import dataclass
from functools import cmp_to_key
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

_MINOR_WILDCARD_PATTERN = re.compile(r"^(?P<major>0|[1-9][0-9]*)\.(?P<wildcard>\*|x|X)$")
_PATCH_WILDCARD_PATTERN = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<wildcard>\*|x|X)$"
)

_OPERATORS: Tuple[str, ...] = (">=", "<=", "==", "!=", "=", ">", "<", "^", "~")

_WILDCARD_ANY: FrozenSet[str] = frozenset({"*", "x", "X"})

_Parts = Tuple[Optional[int], Optional[int], Optional[int]]
_Comparator = Tuple[
    semver_solver.ComparatorOp,
    semver_solver.Version,
    Optional[semver_solver.Version],
]


def _invalid_range(raw_range: str, detail: str) -> semver_solver.InvalidRangeError:
    """Builds an InvalidRangeError quoting the malformed range expression."""
    return semver_solver.InvalidRangeError(
        message=f"Malformed version range {raw_range!r}: {detail}",
        raw_range=raw_range,
    )


def _match_version_text(text: str) -> Optional[semver_solver.Version]:
    """Matches text against the SemVer 2.0.0 grammar without raising."""
    match = _SEMVER_PATTERN.fullmatch(text)
    if match is None:
        return None
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    return semver_solver.Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=tuple(prerelease_text.split(".")) if prerelease_text else (),
        build=tuple(build_text.split(".")) if build_text else (),
    )


def _parse_range_parts(
    text: str,
    raw_range: str,
) -> Tuple[_Parts, Tuple[str, ...], Tuple[str, ...]]:
    """Parses a range operand into concrete or wildcard components."""
    version = _match_version_text(text)
    if version is not None:
        return (
            (version.major, version.minor, version.patch),
            version.prerelease,
            version.build,
        )
    if text in _WILDCARD_ANY:
        return (None, None, None), (), ()
    minor_wildcard = _MINOR_WILDCARD_PATTERN.match(text)
    if minor_wildcard is not None:
        major = int(minor_wildcard.group("major"))
        return (major, None, None), (), ()
    patch_wildcard = _PATCH_WILDCARD_PATTERN.match(text)
    if patch_wildcard is not None:
        major = int(patch_wildcard.group("major"))
        minor = int(patch_wildcard.group("minor"))
        return (major, minor, None), (), ()
    # WHEN a bare partial version lacks wildcard characters (e.g. '1', '1.2'),
    # this branch raises InvalidRangeError.
    raise _invalid_range(raw_range, f"invalid version or wildcard operand {text!r}")


def _concrete_version(
    parts: _Parts,
    prerelease: Tuple[str, ...],
    build: Tuple[str, ...],
) -> semver_solver.Version:
    """Fills unspecified components with zero to build a concrete Version."""
    major = 0 if parts[0] is None else parts[0]
    minor = 0 if parts[1] is None else parts[1]
    patch = 0 if parts[2] is None else parts[2]
    return semver_solver.Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def _wildcard_bounds(
    parts: _Parts,
    prerelease: Tuple[str, ...],
    build: Tuple[str, ...],
    raw_range: str,
) -> Tuple[semver_solver.Version, Optional[semver_solver.Version]]:
    """Computes the inclusive lower and exclusive upper wildcard block bounds."""
    major, minor, patch = parts
    if major is None:
        raise _invalid_range(raw_range, "unbounded wildcard has no finite boundary")
    if minor is None:
        return (
            semver_solver.Version(major=major, minor=0, patch=0),
            semver_solver.Version(major=major + 1, minor=0, patch=0),
        )
    if patch is None:
        return (
            semver_solver.Version(major=major, minor=minor, patch=0),
            semver_solver.Version(major=major, minor=minor + 1, patch=0),
        )
    return (
        semver_solver.Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
            build=build,
        ),
        None,
    )


def _caret_upper(parts: _Parts, raw_range: str) -> semver_solver.Version:
    """Expands a caret prefix using the first non-zero component boundary."""
    major, minor, patch = parts
    if major is None:  # pragma: no cover (assumption: caller rejects unbounded wildcard operands)
        raise _invalid_range(raw_range, "caret range requires a bounded operand")
    if major > 0:
        return semver_solver.Version(major=major + 1, minor=0, patch=0)
    if minor is None:
        return semver_solver.Version(major=1, minor=0, patch=0)
    if minor > 0:
        return semver_solver.Version(major=0, minor=minor + 1, patch=0)
    if patch is None:
        return semver_solver.Version(major=0, minor=1, patch=0)
    return semver_solver.Version(major=0, minor=0, patch=patch + 1)


def _tilde_upper(parts: _Parts, raw_range: str) -> semver_solver.Version:
    """Expands a tilde prefix into the next minor boundary."""
    major, minor, _ = parts
    if major is None:  # pragma: no cover (assumption: caller rejects unbounded wildcard operands)
        raise _invalid_range(raw_range, "tilde range requires a bounded operand")
    if minor is None:
        return semver_solver.Version(major=major + 1, minor=0, patch=0)
    return semver_solver.Version(major=major, minor=minor + 1, patch=0)


def _compile_atom(atom: str, raw_range: str) -> List[_Comparator]:
    """Compiles one comparator atom into precedence comparators."""
    operator = ""
    remainder = atom
    for candidate in _OPERATORS:
        if atom.startswith(candidate):
            operator = candidate
            remainder = atom[len(candidate):]
            break
    parts, prerelease, build = _parse_range_parts(remainder, raw_range)
    is_any = parts == (None, None, None)
    comparators: List[_Comparator] = []

    if operator in ("", "=", "=="):
        if is_any:
            # '*' matches every version, so no comparator is required.
            return comparators
        lower, upper = _wildcard_bounds(parts, prerelease, build, raw_range)
        return [(semver_solver.ComparatorOp.EQ, lower, upper)]

    if operator == "!=":
        if is_any:
            raise _invalid_range(raw_range, "'!=' does not accept an unbounded wildcard")
        lower, upper = _wildcard_bounds(parts, prerelease, build, raw_range)
        return [(semver_solver.ComparatorOp.NE, lower, upper)]

    if operator in (">=", ">", "<", "<="):
        # Unbounded wildcards are standalone operands only; a relational
        # operator applied to one is malformed range syntax, which the
        # bounded-operand guard in _wildcard_bounds rejects.
        lower, upper = _wildcard_bounds(parts, prerelease, build, raw_range)
        if operator == ">=":
            return [(semver_solver.ComparatorOp.GE, lower, None)]
        if operator == ">":
            if upper is None:
                return [(semver_solver.ComparatorOp.GT, lower, None)]
            return [(semver_solver.ComparatorOp.GE, upper, None)]
        if operator == "<":
            return [(semver_solver.ComparatorOp.LT, lower, None)]
        if upper is None:
            return [(semver_solver.ComparatorOp.LE, lower, None)]
        return [(semver_solver.ComparatorOp.LT, upper, None)]

    if operator == "^":
        if is_any:
            raise _invalid_range(raw_range, "caret range requires a bounded operand")
        lower = _concrete_version(parts, prerelease, build)
        upper = _caret_upper(parts, raw_range)
        return [
            (semver_solver.ComparatorOp.GE, lower, None),
            (semver_solver.ComparatorOp.LT, upper, None),
        ]

    if operator == "~":
        if is_any:
            raise _invalid_range(raw_range, "tilde range requires a bounded operand")
        lower = _concrete_version(parts, prerelease, build)
        upper = _tilde_upper(parts, raw_range)
        return [
            (semver_solver.ComparatorOp.GE, lower, None),
            (semver_solver.ComparatorOp.LT, upper, None),
        ]

    # Every operator produced by the clause tokenizer is handled above; this
    # guard exists only to satisfy the static return contract.
    raise _invalid_range(  # pragma: no cover (assumption: operator comes from the _OPERATORS tokenizer)
        raw_range, f"unsupported operator {operator!r}"
    )


def _compile_clause(clause: str, raw_range: str) -> List[_Comparator]:
    """Compiles one whitespace-delimited comparator clause."""
    tokens = clause.split()
    if "-" in tokens:
        # Hyphen ranges have the sole shape 'LOW - HIGH'.
        if len(tokens) != 3 or tokens[1] != "-":
            raise _invalid_range(raw_range, "hyphen ranges must be 'LOW - HIGH'")
        low_parts, low_prerelease, low_build = _parse_range_parts(tokens[0], raw_range)
        high_parts, high_prerelease, high_build = _parse_range_parts(tokens[2], raw_range)
        low_version, _ = _wildcard_bounds(
            low_parts, low_prerelease, low_build, raw_range
        )
        high_version, high_upper = _wildcard_bounds(
            high_parts, high_prerelease, high_build, raw_range
        )
        comparators: List[_Comparator] = [
            (semver_solver.ComparatorOp.GE, low_version, None)
        ]
        if high_upper is None:
            comparators.append((semver_solver.ComparatorOp.LE, high_version, None))
        else:
            comparators.append((semver_solver.ComparatorOp.LT, high_upper, None))
        return comparators

    comparators = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATORS:
            if index + 1 >= len(tokens):
                raise _invalid_range(raw_range, f"missing operand after {token!r}")
            comparators.extend(_compile_atom(token + tokens[index + 1], raw_range))
            index += 2
        else:
            comparators.extend(_compile_atom(token, raw_range))
            index += 1
    return comparators


def _compile_range(text: str) -> List[List[_Comparator]]:
    """Compiles text into disjunctive normal form comparator clauses."""
    # Validation and trimming are distinct: the untrimmed caller text is
    # retained as the InvalidRangeError payload, while only the parsed
    # structure is whitespace-normalized.
    trimmed = text.strip()
    if not trimmed:
        raise _invalid_range(text, "range expression is empty")
    if "," in trimmed:
        raise _invalid_range(
            text, "commas are not permitted as comparator delimiters"
        )
    clauses = [clause.strip() for clause in trimmed.split("||")]
    compiled: List[List[_Comparator]] = []
    for clause in clauses:
        if not clause:
            raise _invalid_range(text, "empty union clause")
        compiled.append(_compile_clause(clause, text))
    return compiled


def _comparator_matches(
    engine: semver_solver.VersionEngine,
    operator: semver_solver.ComparatorOp,
    target: semver_solver.Version,
    block_upper: Optional[semver_solver.Version],
    version: semver_solver.Version,
) -> bool:
    """Tests one compiled comparator against a candidate version."""
    comparison = engine.compare_precedence(version, target)
    if operator is semver_solver.ComparatorOp.EQ:
        if block_upper is None:
            return comparison == 0
        return comparison >= 0 and engine.compare_precedence(version, block_upper) < 0
    if operator is semver_solver.ComparatorOp.NE:
        if block_upper is None:
            return comparison != 0
        return not (
            comparison >= 0 and engine.compare_precedence(version, block_upper) < 0
        )
    if operator is semver_solver.ComparatorOp.LT:
        return comparison < 0
    if operator is semver_solver.ComparatorOp.LE:
        return comparison <= 0
    if operator is semver_solver.ComparatorOp.GT:
        return comparison > 0
    return comparison >= 0


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        version = _match_version_text(text)
        # WHEN text violates the SemVer grammar or uses leading zeroes, MUST
        # raise InvalidVersionError; otherwise MUST yield a Version record.
        if version is None:
            raise semver_solver.InvalidVersionError(
                message=f"Malformed semantic version string: {text!r}",
                raw_text=text,
            )
        return version

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        # MUST compare major, minor, and patch numerically in sequence.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return -1 if left < right else 1

        # MUST rank normal versions higher than prerelease versions.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # MUST compare prerelease segments numerically when both numeric,
        # ASCII-lexicographically when string, and rank numeric below string.
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

        # A longer prerelease sequence ranks higher when the common prefix matches.
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        # MUST ignore build metadata entirely when comparing precedence.
        return 0

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # The compiler validates the full range grammar against the original
        # caller text, so InvalidRangeError.raw_range preserves it exactly;
        # only the accepted VersionRange payload is whitespace-trimmed.
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
        clauses = _compile_range(range_constraint.raw_text)
        for comparators in clauses:
            matched = True
            targets_prerelease = False
            for operator, target, block_upper in comparators:
                # MUST satisfy every comparator in at least one clause.
                if not _comparator_matches(
                    self, operator, target, block_upper, version
                ):
                    matched = False
                    break
                # A comparator explicitly targeting the candidate prerelease
                # shares its major, minor, and patch numbers.
                if target.is_prerelease and (
                    (target.major, target.minor, target.patch)
                    == (version.major, version.minor, version.patch)
                ):
                    targets_prerelease = True
            if not matched:
                continue
            # WHEN version is a prerelease and include_prerelease is False,
            # MUST reject unless the range explicitly targets that prerelease.
            if (
                version.is_prerelease
                and not include_prerelease
                and not targets_prerelease
            ):
                continue
            return True
        return False


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    tier = system

    _packages: Dict[str, List[semver_solver.PackageRelease]]

    def __init__(self) -> None:
        self._packages = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)

        def compare_releases(
            left: semver_solver.PackageRelease,
            right: semver_solver.PackageRelease,
        ) -> int:
            return engine.compare_precedence(left.version, right.version)

        # MUST re-sort the release list in descending precedence order.
        releases.sort(key=cmp_to_key(compare_releases), reverse=True)

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # WHEN name is not registered, MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package {name!r} is not registered in the repository",
                package_name=name,
            )
        # MUST yield a shallow copy of the descending precedence ordering.
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

        # Initialize accumulated constraints and the decision queue from the
        # root dependencies.
        accumulated: Dict[
            str, List[Tuple[str, semver_solver.VersionRange]]
        ] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def candidates_for(
            package_name: str,
        ) -> List[semver_solver.PackageRelease]:
            # Unregistered packages have zero candidate releases; a missing
            # PackageNotFoundError never escapes the resolver.
            if not repository.has_package(package_name):
                return []
            return [
                release
                for release in repository.get_releases(package_name)
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated[package_name]
                )
            ]

        def backtrack() -> bool:
            unassigned = [
                package_name
                for package_name in accumulated
                if package_name not in assignment
            ]
            if not unassigned:
                # Complete assignment found.
                return True

            candidates_map: Dict[
                str, List[semver_solver.PackageRelease]
            ] = {
                package_name: candidates_for(package_name)
                for package_name in unassigned
            }
            # Minimum Remaining Values selection with lexical tie-breaking.
            selected_name = min(
                unassigned,
                key=lambda package_name: (
                    len(candidates_map[package_name]),
                    package_name,
                ),
            )
            candidates = candidates_map[selected_name]
            if not candidates:
                requesters = [
                    requester
                    for requester, _ in accumulated[selected_name]
                ]
                conflicting_packages.add(selected_name)
                for requester in requesters:
                    if requester != "root":
                        conflicting_packages.add(requester)
                conflict_trail.append(
                    f"No viable releases for '{selected_name}' satisfying "
                    f"constraints from {requesters}"
                )
                return False

            # Explore viable releases in descending precedence order.
            for candidate in candidates:
                assignment[selected_name] = candidate
                derivation_steps.append(
                    f"Assign '{selected_name}' to {candidate.version.format()}"
                )
                conflict_detected = False
                newly_added: List[
                    Tuple[str, Tuple[str, semver_solver.VersionRange]]
                ] = []

                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # An already assigned package must satisfy the newly
                        # discovered requirement, otherwise backtrack.
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected_name)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected_name}' requires "
                                f"'{dependency.name}' "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected_name, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and backtrack():
                    return True

                # Pop the candidate decision and restore prior constraints.
                for package_name, entry in newly_added:
                    accumulated[package_name].remove(entry)
                    if not accumulated[package_name]:
                        del accumulated[package_name]
                del assignment[selected_name]
                derivation_steps.pop()

            return False

        if backtrack():
            selected_versions = {
                package_name: release.version
                for package_name, release in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        # WHEN dependencies are unsatisfiable, raise ResolutionConflictError
        # with the accumulated conflict trail as the derivation explanation.
        explanation = "; ".join(conflict_trail)
        raise semver_solver.ResolutionConflictError(
            message="Unable to resolve a compatible dependency assignment",
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
# LAST_CLEANED: 2026-11-05T00:51:39Z
# LAST_CHANGED: 2026-11-05T00:51:03Z
# CHANGE: Addressed coverage feedback: pruned the unreachable missing-operand guard in _compile_atom, the redundant empty-clause guard in _compile_clause, and the dead empty-conflict-trail fallback in resolve; removed the uncontracted relational unbounded-wildcard no-op acceptance so '>=*', '>*', '<*', '<=*' are rejected as malformed range syntax via the bounded-operand guard; annotated the caret/tilde operand-boundary guards and the unsupported-operator fallthrough with '# pragma: no cover (assumption: ...)' where static typing/invariants require them.
# COVERAGE_AUDIT: 2026-11-05T00:51:39Z
# QA_AUDIT: 2026-11-05T00:51:26Z
# --- END AUTOFAB METADATA ---
