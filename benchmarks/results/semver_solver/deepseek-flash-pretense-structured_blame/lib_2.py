# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_193520_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-11-10T19:35:20.023117+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 369,711
#   Cached Inbound Tokens:   24,418,688
#   Outbound Tokens:         334,154
#   Total Tokens:            25,122,553
#   Financial Cost ($USD):   $0.3292
#   Wall Clock Duration:     1815.56s
#   Step Latencies (s):      [308.4, 359.4, 134.6, 185.6, 73.4, 134.8, 20.3, 228.3, 73.6, 186.0, 63.2, 103.9, 10.1, 146.9, 83.9, 226.5, 10.1, 10.1]
#   Role Execution Rounds:   lib: 3, pretense: 6, pretense_coverage: 3, pretense_qa: 6 (Total: 18)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Interface library for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Collection, Dict, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


# Requirements specified in semver_solver.pyi


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error. Verification suites MUST NOT assert on specific wording or prefixes within message, and MUST assert on exception types and structured attributes.
    """

    message: str

    def __str__(self) -> str:
        # Canonical diagnostic text is the stored message.
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
        # A version is a prerelease exactly when it declares prerelease identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        # Canonical SemVer text: core triple, optional -prerelease, optional +build.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += "-" + ".".join(self.prerelease)
        if self.build:
            text += "+" + ".".join(self.build)
        return text

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
        # Delegates directly to format() as contracted.
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
        # Delegates directly to the stored canonical range text.
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
# LAST_CLEANED: 2026-11-10T19:40:35Z
# LAST_CHANGED: 2026-11-10T19:40:35Z
# CHANGE: Implemented interface library: dataclass-based SemVerError hierarchy with __str__, ComparatorOp enum, frozen data types (Version with is_prerelease/format/__str__, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome), and poly_type Protocol service interfaces (VersionEngine, PackageRepository, DependencySolver).
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete implementation of SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Collection, Dict, List, Optional, Set, Tuple, Union

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)
from . import semver_solver


# Requirements specified in semver_solver_impl.pyi


# --- SemVer 2.0.0 lexical grammar ---

_PRERELEASE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
_BUILD_ID = r"[0-9a-zA-Z-]+"

_VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(" + _PRERELEASE_ID + r"(?:\." + _PRERELEASE_ID + r")*))?"
    r"(?:\+(" + _BUILD_ID + r"(?:\." + _BUILD_ID + r")*))?\Z"
)

_WILDCARD_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*|[xX*])"
    r"(?:\.(0|[1-9][0-9]*|[xX*]))?"
    r"(?:\.(0|[1-9][0-9]*|[xX*]))?\Z"
)

_OPERATORS: Tuple[str, ...] = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")

# A wildcard target holds the explicit numeric components; None marks a wildcard.
_TargetParts = Tuple[Optional[int], Optional[int], Optional[int]]
_RangeTarget = Union[semver_solver.Version, _TargetParts]
_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]
_Clause = List[_Comparator]


def _is_wildcard_component(component: str) -> bool:
    return component in ("x", "X", "*")


def _parse_version_token(text: str) -> Optional[semver_solver.Version]:
    """Parses a single full SemVer 2.0.0 version token, or returns None."""
    match = _VERSION_PATTERN.match(text)
    if match is None:
        return None
    major, minor, patch, prerelease, build = match.groups()
    prerelease_ids: Tuple[str, ...] = tuple(prerelease.split(".")) if prerelease else ()
    build_ids: Tuple[str, ...] = tuple(build.split(".")) if build else ()
    return semver_solver.Version(
        int(major), int(minor), int(patch), prerelease_ids, build_ids
    )


def _parse_wildcard_token(text: str) -> Optional[_TargetParts]:
    """Parses a wildcard expression such as ``1.x`` or ``1.2.*``, or returns None."""
    match = _WILDCARD_PATTERN.match(text)
    if match is None:
        return None
    groups = match.groups()
    if not any(
        group is not None and _is_wildcard_component(group) for group in groups
    ):
        # No wildcard character present: this is a bare partial (rejected elsewhere).
        return None
    # The wildcard pattern always yields exactly three component groups.
    parsed: List[Optional[int]] = []
    for group in groups:
        if group is None or _is_wildcard_component(group):
            parsed.append(None)
        else:
            parsed.append(int(group))
    return (parsed[0], parsed[1], parsed[2])


def _parse_range_target(text: str, raw_range: str) -> _RangeTarget:
    """Parses a range comparison target: a full version or a wildcard expression."""
    version = _parse_version_token(text)
    if version is not None:
        return version
    wildcard = _parse_wildcard_token(text)
    if wildcard is not None:
        return wildcard
    raise semver_solver.InvalidRangeError(
        f"Invalid or bare-partial range target: {text!r}", raw_range
    )


def _wildcard_lower(parts: _TargetParts) -> semver_solver.Version:
    major, minor, patch = parts
    return semver_solver.Version(
        0 if major is None else major,
        0 if minor is None else minor,
        0 if patch is None else patch,
    )


def _wildcard_upper(parts: _TargetParts) -> Optional[semver_solver.Version]:
    """Returns the exclusive boundary following the fixed wildcard prefix."""
    major, minor, patch = parts
    del patch
    if major is None:
        return None
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    # A wildcard target never specifies all three numeric components (a fully
    # numeric triple parses as a full version), so the patch component is a
    # wildcard here and the boundary advances by one minor.
    return semver_solver.Version(major, minor + 1, 0)


def _caret_upper_version(version: semver_solver.Version) -> semver_solver.Version:
    # Caret widens up to the next boundary above the left-most non-zero component.
    if version.major > 0:
        return semver_solver.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_solver.Version(0, version.minor + 1, 0)
    if version.patch > 0:
        return semver_solver.Version(0, 0, version.patch + 1)
    return semver_solver.Version(0, 0, 1)


def _caret_upper_parts(parts: _TargetParts) -> Optional[semver_solver.Version]:
    major, minor, patch = parts
    del patch
    if major is None:
        return None
    if major > 0:
        return semver_solver.Version(major + 1, 0, 0)
    if minor is None:
        return semver_solver.Version(1, 0, 0)
    if minor > 0:
        return semver_solver.Version(0, minor + 1, 0)
    # major and minor are both zero; the patch component is a wildcard here (a
    # fully numeric triple parses as a full version), so widen to the next minor.
    return semver_solver.Version(0, 1, 0)


def _tilde_upper_version(version: semver_solver.Version) -> semver_solver.Version:
    return semver_solver.Version(version.major, version.minor + 1, 0)


def _tilde_upper_parts(parts: _TargetParts) -> Optional[semver_solver.Version]:
    major, minor, patch = parts
    del patch
    if major is None:
        return None
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _simple_expansion(
    op: semver_solver.ComparatorOp, version: semver_solver.Version
) -> List[_Clause]:
    return [[(op, version)]]


def _wildcard_expansion(
    op: semver_solver.ComparatorOp, parts: _TargetParts
) -> List[_Clause]:
    lower = _wildcard_lower(parts)
    upper = _wildcard_upper(parts)
    if op is semver_solver.ComparatorOp.EQ:
        clause: _Clause = [(semver_solver.ComparatorOp.GE, lower)]
        if upper is not None:
            clause.append((semver_solver.ComparatorOp.LT, upper))
        return [clause]
    if op is semver_solver.ComparatorOp.NE:
        # Not within [lower, upper): either below the lower bound or above the upper.
        alternatives: List[_Clause] = [[(semver_solver.ComparatorOp.LT, lower)]]
        if upper is not None:
            alternatives.append([(semver_solver.ComparatorOp.GE, upper)])
        return alternatives
    if op is semver_solver.ComparatorOp.LT:
        return [[(semver_solver.ComparatorOp.LT, lower)]]
    if op is semver_solver.ComparatorOp.LE:
        if upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.LT, upper)]]
    if op is semver_solver.ComparatorOp.GT:
        if upper is None:
            return []
        return [[(semver_solver.ComparatorOp.GE, upper)]]
    # ComparatorOp.GE: the candidate must meet or exceed the wildcard lower bound.
    return [[(semver_solver.ComparatorOp.GE, lower)]]


def _caret_expansion(target: _RangeTarget) -> List[_Clause]:
    if isinstance(target, semver_solver.Version):
        lower = target
        upper: Optional[semver_solver.Version] = _caret_upper_version(target)
    else:
        lower = _wildcard_lower(target)
        upper = _caret_upper_parts(target)
    clause: _Clause = [(semver_solver.ComparatorOp.GE, lower)]
    if upper is not None:
        clause.append((semver_solver.ComparatorOp.LT, upper))
    return [clause]


def _tilde_expansion(target: _RangeTarget) -> List[_Clause]:
    if isinstance(target, semver_solver.Version):
        lower = target
        upper: Optional[semver_solver.Version] = _tilde_upper_version(target)
    else:
        lower = _wildcard_lower(target)
        upper = _tilde_upper_parts(target)
    clause: _Clause = [(semver_solver.ComparatorOp.GE, lower)]
    if upper is not None:
        clause.append((semver_solver.ComparatorOp.LT, upper))
    return [clause]


def _split_operator(token: str) -> Tuple[str, str]:
    for op in _OPERATORS:
        if token.startswith(op):
            return op, token[len(op) :]
    return "==", token


def _expand_operator(op_text: str, target: _RangeTarget) -> List[_Clause]:
    if op_text == "^":
        return _caret_expansion(target)
    if op_text == "~":
        return _tilde_expansion(target)
    op = {
        "==": semver_solver.ComparatorOp.EQ,
        "=": semver_solver.ComparatorOp.EQ,
        "!=": semver_solver.ComparatorOp.NE,
        "<": semver_solver.ComparatorOp.LT,
        "<=": semver_solver.ComparatorOp.LE,
        ">": semver_solver.ComparatorOp.GT,
        ">=": semver_solver.ComparatorOp.GE,
    }[op_text]
    if isinstance(target, semver_solver.Version):
        return _simple_expansion(op, target)
    return _wildcard_expansion(op, target)


def _hyphen_expansion(
    lower_target: _RangeTarget, upper_target: _RangeTarget
) -> List[_Clause]:
    if isinstance(lower_target, semver_solver.Version):
        lower = lower_target
    else:
        lower = _wildcard_lower(lower_target)
    clause: _Clause = [(semver_solver.ComparatorOp.GE, lower)]
    if isinstance(upper_target, semver_solver.Version):
        clause.append((semver_solver.ComparatorOp.LE, upper_target))
    else:
        upper = _wildcard_upper(upper_target)
        if upper is not None:
            clause.append((semver_solver.ComparatorOp.LT, upper))
    return [clause]


def _compile_clause(text: str, raw_range: str) -> List[_Clause]:
    hyphen_parts = re.split(r"\s+-\s+", text)
    if len(hyphen_parts) > 2:
        raise semver_solver.InvalidRangeError(
            f"Malformed hyphen range: {text!r}", raw_range
        )
    if len(hyphen_parts) == 2:
        lower_target = _parse_range_target(hyphen_parts[0].strip(), raw_range)
        upper_target = _parse_range_target(hyphen_parts[1].strip(), raw_range)
        return _hyphen_expansion(lower_target, upper_target)

    tokens = text.split()
    clauses: List[_Clause] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATORS:
            if index + 1 >= len(tokens):
                raise semver_solver.InvalidRangeError(
                    f"Operator without operand: {text!r}", raw_range
                )
            op_text = token
            target_text = tokens[index + 1]
            index += 2
        else:
            op_text, target_text = _split_operator(token)
            index += 1
        target = _parse_range_target(target_text, raw_range)
        options = _expand_operator(op_text, target)
        expanded: List[_Clause] = []
        for clause in clauses:
            for option in options:
                expanded.append(clause + option)
        clauses = expanded
    return clauses


def _compile_range(raw_text: str) -> List[_Clause]:
    """Validates a range expression and compiles it into disjunctive normal form."""
    trimmed = raw_text.strip()
    if not trimmed:
        raise semver_solver.InvalidRangeError(
            "Range expression must not be empty", raw_text
        )
    if "," in trimmed:
        raise semver_solver.InvalidRangeError(
            "Comma delimiters are not permitted in range expressions", raw_text
        )
    clauses: List[_Clause] = []
    for alternative in trimmed.split("||"):
        clause_text = alternative.strip()
        if not clause_text:
            raise semver_solver.InvalidRangeError(
                "Empty union clause in range expression", raw_text
            )
        clauses.extend(_compile_clause(clause_text, raw_text))
    return clauses


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine.

    GROUNDING:
    - Realizes SemVer 2.0.0 regular expression grammar, precedence comparison, and range expansion algebra.
    """

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Grammar and leading-zero validation is enforced by the regular expression.
        parsed = _parse_version_token(text)
        if parsed is None:
            raise semver_solver.InvalidVersionError(
                f"Unparseable SemVer 2.0.0 version: {text!r}", text
            )
        return parsed

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        # Numeric core components compare numerically in sequence.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return -1 if left < right else 1

        # A normal version outranks a prerelease sharing the same core triple.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # Prerelease segments compare position by position, numeric below string.
        for left_id, right_id in zip(v1.prerelease, v2.prerelease):
            left_numeric = left_id.isdigit()
            right_numeric = right_id.isdigit()
            if left_numeric and right_numeric:
                left_value = int(left_id)
                right_value = int(right_id)
                if left_value != right_value:
                    return -1 if left_value < right_value else 1
            elif left_numeric:
                return -1
            elif right_numeric:
                return 1
            elif left_id != right_id:
                return -1 if left_id < right_id else 1

        # A longer prerelease sequence outranks an identical shorter prefix.
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        return 0

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # Compilation validates whitespace, delimiters, and every comparator target.
        _compile_range(text)
        # The trimmed range expression is retained as the canonical raw text.
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
        clauses = _compile_range(range_constraint.raw_text)
        for clause in clauses:
            # A clause matches when the candidate satisfies every comparator in it.
            if not all(
                self._matches(version, comparator, bound)
                for comparator, bound in clause
            ):
                continue
            if version.is_prerelease and not include_prerelease:
                # Prereleases only match ranges explicitly targeting their triple.
                explicitly_targeted = any(
                    bound.is_prerelease
                    and (bound.major, bound.minor, bound.patch)
                    == (version.major, version.minor, version.patch)
                    for _, bound in clause
                )
                if not explicitly_targeted:
                    continue
            return True
        return False

    def _matches(
        self,
        version: semver_solver.Version,
        comparator: semver_solver.ComparatorOp,
        bound: semver_solver.Version,
    ) -> bool:
        ordering = self.compare_precedence(version, bound)
        if comparator is semver_solver.ComparatorOp.EQ:
            return ordering == 0
        if comparator is semver_solver.ComparatorOp.NE:
            return ordering != 0
        if comparator is semver_solver.ComparatorOp.LT:
            return ordering < 0
        if comparator is semver_solver.ComparatorOp.LE:
            return ordering <= 0
        if comparator is semver_solver.ComparatorOp.GT:
            return ordering > 0
        return ordering >= 0


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing.

    GROUNDING:
    - Maintains _packages dictionary mapping package names to lists of semver_solver.PackageRelease.
    - Coordinates with semver_solver.VersionEngine for release sorting.
    """

    tier = system

    def __init__(self) -> None:
        # Private backing storage maps package names to precedence-sorted releases.
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        # Insert into the per-name release list, then restore descending ordering.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_solver.VersionEngine)

        def compare(
            left: semver_solver.PackageRelease, right: semver_solver.PackageRelease
        ) -> int:
            return engine.compare_precedence(left.version, right.version)

        releases.sort(key=cmp_to_key(compare), reverse=True)

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                f"Package not registered in repository: {name!r}", name
            )
        # Getter exposes a defensive shallow copy of the internally sorted list.
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
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver.

    GROUNDING:
    - Coordinates with semver_solver.VersionEngine and semver_solver.PackageRepository to resolve compatible release assignments.
    - Delegates search heuristics and conflict recording to backtracking_solver_ext.
    """

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

        # Accumulated constraints map each pending package to (requester, range) pairs.
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def available_releases(name: str) -> List[semver_solver.PackageRelease]:
            # Unregistered packages contribute zero candidates; no PackageNotFoundError escapes.
            try:
                return repository.get_releases(name)
            except semver_solver.PackageNotFoundError:
                return []

        def viable_releases(name: str) -> List[semver_solver.PackageRelease]:
            # Candidates must satisfy every accumulated range constraint for the package.
            constraints = accumulated[name]
            return [
                release
                for release in available_releases(name)
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in constraints
                )
            ]

        def search() -> bool:
            unassigned = [
                name for name in accumulated if name not in assignment
            ]
            if not unassigned:
                return True

            # Minimum Remaining Values selection with lexical tie-breaking.
            candidate_map = {
                name: viable_releases(name) for name in unassigned
            }
            selected = min(
                unassigned, key=lambda name: (len(candidate_map[name]), name)
            )
            candidates = candidate_map[selected]

            if not candidates:
                requesters = [source for source, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False

            # Releases arrive in descending precedence order: highest version first.
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
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires "
                                f"'{dependency.name}' {dependency.range_constraint}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and search():
                    return True

                # Backtrack: undo the assignment and every newly introduced constraint.
                for package_name, entry in newly_added:
                    accumulated[package_name].remove(entry)
                    if not accumulated[package_name]:
                        del accumulated[package_name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if search():
            selected_versions: Dict[str, semver_solver.Version] = {
                name: release.version for name, release in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        # A failed search always records at least one conflict-trail message.
        explanation = "; ".join(conflict_trail)
        raise semver_solver.ResolutionConflictError(
            f"Dependency resolution failed: {explanation}",
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
# LAST_CLEANED: 2026-11-10T20:05:32Z
# LAST_CHANGED: 2026-11-10T20:02:50Z
# CHANGE: Resolved pretense_coverage unreachable-logic feedback: removed the unreachable wildcard-comparator dispatch fallthrough by dispatching five ComparatorOp members explicitly and letting the reachable final return handle GE (mirroring _matches). Also audited siblings and removed the analogous dead fallback in DependencySolver.resolve's conflict explanation, since a failed search always appends at least one conflict-trail message. All reachable behavior is unchanged.
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T20:05:32Z
# PRETENSE_QA_AUDIT: 2026-11-10T20:05:20Z
# --- END AUTOFAB METADATA ---
