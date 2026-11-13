# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_154640_deepseek-flash_semver_solver_multi_pretense
# Timestamp: 2026-11-13T15:46:40.575052+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 403,662
#   Cached Inbound Tokens:   45,114,752
#   Outbound Tokens:         382,208
#   Total Tokens:            45,900,622
#   Financial Cost ($USD):   $0.4252
#   Wall Clock Duration:     1920.43s
#   Step Latencies (s):      [578.1, 20.8, 696.4, 24.5, 245.8, 128.0, 20.8, 474.7, 20.9, 10.1, 48.7, 216.0, 109.4, 20.8, 183.9, 31.4, 78.7, 108.5, 20.7, 54.8, 44.3, 10.1, 20.6]
#   Role Execution Rounds:   lib: 3, pretense: 5, pretense_coverage: 5, pretense_qa: 10 (Total: 23)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       13
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
"""Interface specification for package repository and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from . import semver_core, semver_range
from support.lib.framework import data_type, operation, poly_type


@dataclass
class PackageNotFoundError(semver_core.SemVerError):
    """Raised when a referenced package name does not exist in the repository.

    Args:
        message: Diagnostic description of the missing package.
        package_name: Name of the missing package.
    """

    package_name: str


@dataclass
class ResolutionConflictError(semver_core.SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually.

    Args:
        message: Diagnostic description of the conflict.
        conflicting_packages: Sequence of package names involved in the conflict.
        explanation: Detailed diagnostic derivation of the unsatisfiable conflict.
    """

    conflicting_packages: Tuple[str, ...]
    explanation: str


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range.

    Args:
        name: Name of the required package.
        range_constraint: Acceptable version range constraint.
    """

    name: str
    range_constraint: semver_range.VersionRange


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
    version: semver_core.Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run.

    Args:
        selected_versions: Mapping of package names to their selected semantic versions.
        derivation_steps: Ordered sequence of decision and deduction steps.
    """

    selected_versions: Mapping[str, semver_core.Version]
    derivation_steps: Tuple[str, ...]


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
# LAST_CLEANED: 2026-11-13T15:56:12Z
# LAST_CHANGED: 2026-11-13T15:56:12Z
# CHANGE: Implemented dependency resolution interfaces: PackageNotFoundError and ResolutionConflictError, PackageDependency/PackageRelease/ResolutionOutcome frozen data types, and PackageRepository/DependencySolver protocols.
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Concrete realization of package repository storage and dependency resolution."""

from __future__ import annotations

from typing import Collection, Dict, List, Set, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dependency_solver, semver_core, semver_range

_PrereleaseKey = Tuple[int, Tuple[Tuple[int, int, str], ...]]
_VersionKey = Tuple[int, int, int, _PrereleaseKey]


def _precedence_key(version: semver_core.Version) -> _VersionKey:
    """Builds a sortable key reflecting SemVer precedence, ignoring build metadata."""
    if not version.prerelease:
        prerelease_key: _PrereleaseKey = (1, ())
    else:
        encoded = tuple(
            (0, int(identifier), "") if identifier.isdigit() else (1, 0, identifier)
            for identifier in version.prerelease
        )
        prerelease_key = (0, encoded)
    return (version.major, version.minor, version.patch, prerelease_key)


@singleton
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = "system"

    def __init__(self) -> None:
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=lambda item: _precedence_key(item.version), reverse=True)

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        """Retrieves registered releases ordered by version precedence descending."""
        releases = self._packages.get(name)
        if releases is None:
            raise dependency_solver.PackageNotFoundError(
                f"Package {name!r} is not registered in the repository.", name
            )
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


@singleton
class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of backtracking dependency resolution."""

    tier = "system"

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        accumulated: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for root_dependency in root_dependencies:
            accumulated.setdefault(root_dependency.name, []).append(
                ("root", root_dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def matches(
            version: semver_core.Version, constraint: semver_range.VersionRange
        ) -> bool:
            return range_engine.satisfies(version, constraint, False)

        def viable_releases(name: str) -> List[dependency_solver.PackageRelease]:
            try:
                available = repository.get_releases(name)
            except dependency_solver.PackageNotFoundError:
                return []
            return [
                release
                for release in available
                if all(
                    matches(release.version, constraint)
                    for _, constraint in accumulated[name]
                )
            ]

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True

            candidates_by_package = {
                name: viable_releases(name) for name in unassigned
            }
            selected = min(
                unassigned,
                key=lambda name: (len(candidates_by_package[name]), name),
            )
            candidates = candidates_by_package[selected]

            if not candidates:
                requesters = [source for source, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying "
                    f"constraints from {requesters}"
                )
                return False

            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(
                    f"Assign '{selected}' to {candidate.version}"
                )
                conflict_detected = False
                newly_added: List[
                    Tuple[str, Tuple[str, semver_range.VersionRange]]
                ] = []

                for requirement in candidate.dependencies:
                    if requirement.name in assignment:
                        if not matches(
                            assignment[requirement.name].version,
                            requirement.range_constraint,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(requirement.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires "
                                f"{requirement.name} "
                                f"{requirement.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, requirement.range_constraint)
                        accumulated.setdefault(requirement.name, []).append(entry)
                        newly_added.append((requirement.name, entry))

                if not conflict_detected and backtrack():
                    return True

                for name, entry in newly_added:
                    accumulated[name].remove(entry)
                    if not accumulated[name]:
                        del accumulated[name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if not backtrack():
            explanation = "; ".join(conflict_trail)
            if not explanation:
                with unreachable:
                    explanation = (
                        "No compatible version assignment exists for the requested "
                        "dependencies."
                    )
            raise dependency_solver.ResolutionConflictError(
                f"Dependency resolution failed: {explanation}",
                tuple(sorted(conflicting_packages)),
                explanation,
            )

        selected_versions = {
            name: release.version for name, release in assignment.items()
        }
        return dependency_solver.ResolutionOutcome(
            selected_versions, tuple(derivation_steps)
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T16:18:27Z
# LAST_CHANGED: 2026-11-13T16:16:15Z
# CHANGE: Fixed the conflict-failure path: the empty-conflict-trail quarantine is now placed inside the never-true guard so the ResolutionConflictError path is never intercepted by the unreachable tripwire; unsatisfiable constraints now raise ResolutionConflictError with the recorded conflict trail and conflicting packages as contracted.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T16:18:27Z
# PRETENSE_QA_AUDIT: 2026-11-13T16:18:14Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""Interface specification for semantic version parsing and precedence comparison."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Protocol, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver failures.

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


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing and precedence comparison."""

    @operation
    def parse_version(self, text: str) -> Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T15:55:47Z
# LAST_CHANGED: 2026-11-13T15:55:47Z
# CHANGE: Implemented SemVer 2.0.0 interfaces: error hierarchy (SemVerError, InvalidVersionError), ComparatorOp enum, frozen Version data type with formatting, and VersionEngine protocol.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Concrete realization of SemVer 2.0.0 parsing and precedence comparison."""

from __future__ import annotations

import re
from typing import Optional

from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import semver_core

_VERSION_PATTERN = re.compile(
    r"(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


def _compare_identifiers(left: str, right: str) -> int:
    """Compares two pre-release identifiers using numeric then ASCII ordering."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        return (left_value > right_value) - (left_value < right_value)
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    return (left > right) - (left < right)


def _optional_text(value: Optional[str]) -> tuple[str, ...]:
    """Splits an optional dotted identifier list into its component tuple."""
    if not value:
        return ()
    return tuple(value.split("."))


@singleton
class VersionEngine(semver_core.VersionEngine):
    """Concrete SemVer 2.0.0 parsing and precedence engine."""

    tier = "system"

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        match = _VERSION_PATTERN.fullmatch(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                f"Invalid semantic version: {text!r}", text
            )
        return semver_core.Version(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            _optional_text(match.group("prerelease")),
            _optional_text(match.group("build")),
        )

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        left_core = (v1.major, v1.minor, v1.patch)
        right_core = (v2.major, v2.minor, v2.patch)
        if left_core != right_core:
            return -1 if left_core < right_core else 1
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        for left_identifier, right_identifier in zip(v1.prerelease, v2.prerelease):
            result = _compare_identifiers(left_identifier, right_identifier)
            if result != 0:
                return result
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T16:11:08Z
# LAST_CHANGED: 2026-11-13T15:55:53Z
# CHANGE: Implemented concrete VersionEngine singleton: SemVer 2.0.0 grammar/regex parsing with leading-zero rejection, InvalidVersionError on malformed input, and full precedence comparison including prerelease identifier ordering with build metadata ignored.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T16:11:08Z
# PRETENSE_QA_AUDIT: 2026-11-13T16:10:00Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Interface specification for version range parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from . import semver_core
from support.lib.framework import data_type, operation, poly_type


@dataclass
class InvalidRangeError(semver_core.SemVerError):
    """Raised when a version range expression contains malformed syntax.

    Args:
        message: Diagnostic description of the error.
        raw_range: Original malformed range expression string.
    """

    raw_range: str


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


@poly_type
class RangeEngine(Protocol):
    """Provides version range parsing and constraint matching."""

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        ...

    @operation
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T15:56:00Z
# LAST_CHANGED: 2026-11-13T15:56:00Z
# CHANGE: Implemented version range interfaces: InvalidRangeError, frozen VersionRange with string formatting, and RangeEngine protocol for parsing and constraint satisfaction.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Concrete realization of version range parsing and constraint matching."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import singleton

from . import semver_core, semver_range

_WILDCARD_MARKERS = frozenset({"*", "x", "X"})
_COMPARATOR_PREFIXES = ("<=", ">=", "==", "!=", "<", ">", "=", "^", "~")

_FULL_VERSION_PATTERN = re.compile(
    r"(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)

_Comparator = Tuple[str, semver_core.Version]
_Clause = List[_Comparator]
_RangeClauses = List[_Clause]


@dataclass(frozen=True)
class _VersionSpec:
    """Decomposed version bound supporting wildcard components."""

    major: Optional[int]
    minor: Optional[int]
    patch: Optional[int]
    prerelease: Tuple[str, ...]
    build: Tuple[str, ...]
    wildcard: bool


def _split_identifiers(value: Optional[str]) -> Tuple[str, ...]:
    """Splits an optional dotted identifier list into its component tuple."""
    if not value:
        return ()
    return tuple(value.split("."))


def _compare_identifiers(left: str, right: str) -> int:
    """Compares two pre-release identifiers using numeric then ASCII ordering."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        return (left_value > right_value) - (left_value < right_value)
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    return (left > right) - (left < right)


def _compare_versions(left: semver_core.Version, right: semver_core.Version) -> int:
    """Compares two versions by SemVer 2.0.0 precedence, ignoring build metadata."""
    left_core = (left.major, left.minor, left.patch)
    right_core = (right.major, right.minor, right.patch)
    if left_core != right_core:
        return -1 if left_core < right_core else 1
    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1
    for left_identifier, right_identifier in zip(left.prerelease, right.prerelease):
        result = _compare_identifiers(left_identifier, right_identifier)
        if result != 0:
            return result
    if len(left.prerelease) == len(right.prerelease):
        return 0
    return -1 if len(left.prerelease) < len(right.prerelease) else 1


def _parse_wildcard_spec(parts: Sequence[str], error_text: str) -> _VersionSpec:
    """Parses a dot-separated bound containing wildcard components."""
    if len(parts) > 3:
        raise semver_range.InvalidRangeError(
            "Wildcard version bounds may declare at most three components.", error_text
        )
    values: List[Optional[int]] = []
    wildcard_seen = False
    for part in parts:
        if part in _WILDCARD_MARKERS:
            wildcard_seen = True
            values.append(None)
            continue
        if wildcard_seen or not (part.isascii() and part.isdigit()):
            raise semver_range.InvalidRangeError(
                "Malformed wildcard version bound in range expression.", error_text
            )
        if len(part) > 1 and part.startswith("0"):
            raise semver_range.InvalidRangeError(
                "Numeric range components must not contain leading zeroes.", error_text
            )
        values.append(int(part))
    while len(values) < 3:
        values.append(None)
    return _VersionSpec(values[0], values[1], values[2], (), (), True)


def _parse_spec(token: str, error_text: str) -> _VersionSpec:
    """Parses a complete version bound or a wildcard expression."""
    if not token:
        with unreachable:
            raise semver_range.InvalidRangeError(
                "Version range clause is missing a version bound.", error_text
            )
    parts = token.split(".")
    if any(part in _WILDCARD_MARKERS for part in parts):
        return _parse_wildcard_spec(parts, error_text)
    match = _FULL_VERSION_PATTERN.fullmatch(token)
    if match is None:
        raise semver_range.InvalidRangeError(
            f"Malformed version bound {token!r} in range expression.", error_text
        )
    return _VersionSpec(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        _split_identifiers(match.group("prerelease")),
        _split_identifiers(match.group("build")),
        False,
    )


def _floor(spec: _VersionSpec) -> semver_core.Version:
    """Computes the smallest version covered by a version bound."""
    return semver_core.Version(
        spec.major if spec.major is not None else 0,
        spec.minor if spec.minor is not None else 0,
        spec.patch if spec.patch is not None else 0,
        spec.prerelease,
        spec.build,
    )


def _ceiling(spec: _VersionSpec) -> Optional[semver_core.Version]:
    """Computes the exclusive upper bound of a wildcard expression when one exists."""
    major = spec.major
    if major is None:
        return None
    minor = spec.minor
    if minor is None:
        return semver_core.Version(major + 1, 0, 0)
    return semver_core.Version(major, minor + 1, 0)


def _caret_ceiling(spec: _VersionSpec) -> semver_core.Version:
    """Computes the exclusive upper bound implied by a caret prefix."""
    major = spec.major
    if major is None:
        raise AssertionError("Caret bounds always declare a major component.")
    minor = spec.minor
    patch = spec.patch
    if minor is None:
        return semver_core.Version(major + 1, 0, 0)
    if patch is None:
        if major > 0:
            return semver_core.Version(major + 1, 0, 0)
        if minor > 0:
            return semver_core.Version(0, minor + 1, 0)
        return semver_core.Version(0, 1, 0)
    if major > 0:
        return semver_core.Version(major + 1, 0, 0)
    if minor > 0:
        return semver_core.Version(0, minor + 1, 0)
    return semver_core.Version(0, 0, patch + 1)


def _tilde_ceiling(spec: _VersionSpec) -> semver_core.Version:
    """Computes the exclusive upper bound implied by a tilde prefix."""
    major = spec.major
    if major is None:
        raise AssertionError("Tilde bounds always declare a major component.")
    minor = spec.minor
    if minor is None:
        return semver_core.Version(major + 1, 0, 0)
    return semver_core.Version(major, minor + 1, 0)


def _expand_wildcard(
    operator: str, spec: _VersionSpec, error_text: str
) -> _RangeClauses:
    """Expands a comparator applied to a wildcard expression into comparator clauses."""
    major = spec.major
    if major is None:
        if operator in ("<", ">", "!="):
            return []
        return [[]]
    floor = _floor(spec)
    ceiling = _ceiling(spec)
    assert ceiling is not None
    if operator in ("=", "=="):
        return [[("GE", floor), ("LT", ceiling)]]
    if operator == "!=":
        return [[("LT", floor)], [("GE", ceiling)]]
    if operator == "<":
        return [[("LT", floor)]]
    if operator == "<=":
        return [[("LT", ceiling)]]
    if operator == ">":
        return [[("GE", ceiling)]]
    if operator == ">=":
        return [[("GE", floor)]]
    if operator == "^":
        return [[("GE", floor), ("LT", _caret_ceiling(spec))]]
    if operator == "~":
        return [[("GE", floor), ("LT", _tilde_ceiling(spec))]]
    with unreachable:
        raise semver_range.InvalidRangeError(
            f"Unsupported range operator {operator!r}.", error_text
        )


def _expand_version(
    operator: str, spec: _VersionSpec, error_text: str
) -> _RangeClauses:
    """Expands a comparator applied to a complete version into comparator clauses."""
    version = _floor(spec)
    if operator in ("=", "=="):
        return [[("EQ", version)]]
    if operator == "!=":
        return [[("NE", version)]]
    if operator == "<":
        return [[("LT", version)]]
    if operator == "<=":
        return [[("LE", version)]]
    if operator == ">":
        return [[("GT", version)]]
    if operator == ">=":
        return [[("GE", version)]]
    if operator == "^":
        return [[("GE", version), ("LT", _caret_ceiling(spec))]]
    if operator == "~":
        return [[("GE", version), ("LT", _tilde_ceiling(spec))]]
    with unreachable:
        raise semver_range.InvalidRangeError(
            f"Unsupported range operator {operator!r}.", error_text
        )


def _expand(operator: str, spec: _VersionSpec, error_text: str) -> _RangeClauses:
    """Expands a single comparator into equivalent disjunctive comparator clauses."""
    if spec.wildcard:
        return _expand_wildcard(operator, spec, error_text)
    return _expand_version(operator, spec, error_text)


def _compile_hyphen(tokens: Sequence[str], error_text: str) -> _RangeClauses:
    """Compiles a hyphen range connecting a lower and an upper bound."""
    if len(tokens) != 3 or tokens[1] != "-":
        raise semver_range.InvalidRangeError(
            "Hyphen ranges must connect exactly two version bounds.", error_text
        )
    lower = _parse_spec(tokens[0], error_text)
    upper = _parse_spec(tokens[2], error_text)
    clause: _Clause = [("GE", _floor(lower))]
    if upper.wildcard:
        ceiling = _ceiling(upper)
        if ceiling is not None:
            clause.append(("LT", ceiling))
    else:
        clause.append(("LE", _floor(upper)))
    return [clause]


def _compile_clause(clause_text: str, error_text: str) -> _RangeClauses:
    """Compiles one whitespace-delimited range clause into comparator alternatives."""
    tokens = clause_text.split()
    if "-" in tokens:
        return _compile_hyphen(tokens, error_text)
    alternatives: _RangeClauses = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _COMPARATOR_PREFIXES:
            operator = token
            index += 1
            if index >= len(tokens):
                raise semver_range.InvalidRangeError(
                    f"Operator {operator!r} is missing a version bound.", error_text
                )
            spec_text = tokens[index]
        else:
            operator = "="
            spec_text = token
            for prefix in _COMPARATOR_PREFIXES:
                if token.startswith(prefix):
                    operator = prefix
                    spec_text = token[len(prefix):]
                    break
            if not spec_text:
                with unreachable:
                    raise semver_range.InvalidRangeError(
                        f"Operator {operator!r} is missing a version bound.",
                        error_text,
                    )
        spec = _parse_spec(spec_text, error_text)
        expansions = _expand(operator, spec, error_text)
        combined: _RangeClauses = []
        for existing in alternatives:
            for expansion in expansions:
                combined.append(existing + expansion)
        alternatives = combined
        index += 1
    return alternatives


def _compile(raw: str, error_text: str) -> _RangeClauses:
    """Compiles a range expression into disjunctive normal form comparator sets."""
    if "," in raw:
        raise semver_range.InvalidRangeError(
            "Comma delimiters are not permitted in version ranges.", error_text
        )
    stripped = raw.strip()
    if not stripped:
        raise semver_range.InvalidRangeError(
            "Version range expression must not be empty.", error_text
        )
    clauses: _RangeClauses = []
    for part in stripped.split("||"):
        clause_text = part.strip()
        if not clause_text:
            raise semver_range.InvalidRangeError(
                "Version range contains an empty union alternative.", error_text
            )
        clauses.extend(_compile_clause(clause_text, error_text))
    return clauses


def _matches(
    version: semver_core.Version, operator: str, boundary: semver_core.Version
) -> bool:
    """Evaluates a candidate version against a single comparator boundary."""
    comparison = _compare_versions(version, boundary)
    if operator == "EQ":
        return comparison == 0
    if operator == "NE":
        return comparison != 0
    if operator == "LT":
        return comparison < 0
    if operator == "LE":
        return comparison <= 0
    if operator == "GT":
        return comparison > 0
    if operator == "GE":
        return comparison >= 0
    raise AssertionError(f"Unknown comparator operator: {operator}")


def _targets_prerelease(
    clause: Sequence[_Comparator], version: semver_core.Version
) -> bool:
    """Determines whether a clause explicitly targets the candidate pre-release."""
    for _, boundary in clause:
        if (
            boundary.prerelease
            and boundary.major == version.major
            and boundary.minor == version.minor
            and boundary.patch == version.patch
        ):
            return True
    return False


@singleton
class RangeEngine(semver_range.RangeEngine):
    """Concrete version range parsing and matching engine."""

    tier = "system"

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        trimmed = text.strip()
        _compile(trimmed, text)
        return semver_range.VersionRange(trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        clauses = _compile(range_constraint.raw_text, range_constraint.raw_text)
        for clause in clauses:
            if not all(
                _matches(version, operator, boundary)
                for operator, boundary in clause
            ):
                continue
            if version.is_prerelease and not include_prerelease:
                if not _targets_prerelease(clause, version):
                    continue
            return True
        return False

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T16:16:57Z
# LAST_CHANGED: 2026-11-13T16:16:22Z
# CHANGE: Audited the same quarantine defect pattern in the range engine: the unreachable empty version bound tripwire in _parse_spec is now enclosed inside its never-true guard rather than around it, so ordinary version bound parsing is not intercepted; all other 'with unreachable' sites remain on provably unreachable paths only.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T16:16:57Z
# PRETENSE_QA_AUDIT: 2026-11-13T16:16:36Z
# --- END AUTOFAB METADATA ---
