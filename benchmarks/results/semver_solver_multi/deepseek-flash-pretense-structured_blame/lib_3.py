# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261115_040930_deepseek-flash_semver_solver_multi_pretense
# Timestamp: 2026-11-15T04:09:30.273551+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 318,176
#   Cached Inbound Tokens:   30,402,048
#   Outbound Tokens:         281,676
#   Total Tokens:            31,001,900
#   Financial Cost ($USD):   $0.3079
#   Wall Clock Duration:     1516.90s
#   Step Latencies (s):      [333.0, 10.1, 10.1, 672.3, 13.6, 194.2, 52.7, 150.2, 20.8, 44.2, 22.9, 42.0, 156.7, 12.3, 20.8, 71.8, 10.2, 65.4, 20.8, 97.0, 20.6, 41.7, 63.0, 10.1, 20.7]
#   Role Execution Rounds:   lib: 3, pretense: 6, pretense_coverage: 7, pretense_qa: 9 (Total: 25)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       15
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
"""Interface specification for package repositories and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type
from . import semver_core, semver_range

__all__ = [
    "DependencySolver",
    "PackageDependency",
    "PackageNotFoundError",
    "PackageRelease",
    "PackageRepository",
    "ResolutionConflictError",
    "ResolutionOutcome",
]


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
        """Registers a package release with its declared dependencies.

        Args:
            release: Package release publication to register.
        """
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        """Retrieves all registered releases for a package name by precedence, descending.

        Args:
            name: Package name to look up.

        Returns:
            List of package releases ordered by version precedence descending.

        Raises:
            PackageNotFoundError: If the name is not registered in the repository.
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
            root_dependencies: Initial collection of package requirements.

        Returns:
            A ResolutionOutcome containing the selected versions and derivation steps.

        Raises:
            ResolutionConflictError: If dependencies cannot be satisfied mutually or
                reference missing packages.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:14:56Z
# LAST_CHANGED: 2026-11-15T04:14:56Z
# CHANGE: Author dependency_solver interface: PackageNotFoundError/ResolutionConflictError records, frozen PackageDependency/PackageRelease/ResolutionOutcome value types, and PackageRepository/DependencySolver protocol stubs
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Concrete realization of package release storage and dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
from typing import Collection, Dict, List, Set, Tuple

from support.lib.framework import unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dependency_solver, semver_core, semver_range

__all__ = ["DependencySolver", "PackageRepository"]


@singleton
class PackageRepository(dependency_solver.PackageRepository):
    tier = "system"

    def __init__(self) -> None:
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        engine = get_singleton(semver_core.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)

        # Keep every release list ordered by descending version precedence.
        def compare(
            left: dependency_solver.PackageRelease,
            right: dependency_solver.PackageRelease,
        ) -> int:
            return engine.compare_precedence(right.version, left.version)

        releases.sort(key=cmp_to_key(compare))

    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        releases = self._packages.get(name)
        if releases is None:
            raise dependency_solver.PackageNotFoundError(
                f"Package {name!r} is not registered in the repository", name
            )
        # Expose a shallow copy so callers cannot mutate the repository index.
        return list(releases)

    def has_package(self, name: str) -> bool:
        return name in self._packages

    def all_packages(self) -> Set[str]:
        return set(self._packages.keys())


@singleton
class DependencySolver(dependency_solver.DependencySolver):
    tier = "system"

    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        # Accumulated constraints map each package to its requesters and required ranges.
        constraints: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(name: str) -> List[dependency_solver.PackageRelease]:
            # Packages absent from the repository simply have no candidate releases.
            if not repository.has_package(name):
                return []
            required = constraints[name]
            return [
                release
                for release in repository.get_releases(name)
                if all(
                    range_engine.satisfies(release.version, constraint, False)
                    for _, constraint in required
                )
            ]

        def backtrack() -> bool:
            unassigned = [name for name in constraints if name not in assignment]
            if not unassigned:
                return True

            # Minimum Remaining Values selection with lexical tie-breaking.
            candidates: Dict[str, List[dependency_solver.PackageRelease]] = {
                name: viable_releases(name) for name in unassigned
            }
            selected = min(unassigned, key=lambda name: (len(candidates[name]), name))
            options = candidates[selected]
            if not options:
                requesters = [source for source, _ in constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(
                    source for source in requesters if source != "root"
                )
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False

            for release in options:
                assignment[selected] = release
                derivation_steps.append(f"Assign '{selected}' to {release.version}")
                introduced: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []
                conflicted = False

                # Forward check every declared dependency of the candidate release.
                for dependency in release.dependencies:
                    if dependency.name in assignment:
                        assigned = assignment[dependency.name]
                        if not range_engine.satisfies(
                            assigned.version, dependency.range_constraint, False
                        ):
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{dependency.name}' "
                                f"{dependency.range_constraint}"
                            )
                            conflicted = True
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(entry)
                        introduced.append((dependency.name, entry))

                if not conflicted and backtrack():
                    return True

                # Undo the assignment and every constraint it introduced before retrying.
                for name, entry in introduced:
                    constraints[name].remove(entry)
                    if not constraints[name]:
                        del constraints[name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if backtrack():
            selected_versions: Dict[str, semver_core.Version] = {
                name: release.version for name, release in assignment.items()
            }
            return dependency_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        explanation = "\n".join(conflict_trail)
        if not explanation:
            # Exhausting the search always records at least one conflict trail entry.
            with unreachable("failed searches always record conflict trail entries"):
                explanation = (
                    "No compatible release assignment satisfied the requested dependencies."
                )
        involved = tuple(sorted(conflicting_packages))
        raise dependency_solver.ResolutionConflictError(
            f"Dependency resolution failed for packages: {involved}", involved, explanation
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:30:30Z
# LAST_CHANGED: 2026-11-15T04:27:50Z
# CHANGE: Quarantine the empty conflict-trail explanation fallback with with unreachable(...), since every failed backtracking search records at least one conflict trail entry before ResolutionConflictError is raised; runtime behavior preserved
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T04:30:30Z
# PRETENSE_QA_AUDIT: 2026-11-15T04:29:53Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""Interface specification for semantic version parsing and precedence comparison."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type

__all__ = [
    "ComparatorOp",
    "InvalidVersionError",
    "SemVerError",
    "Version",
    "VersionEngine",
]


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str


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
    """Immutable semantic version record conforming to SemVer 2.0.0.

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
            text = text + "-" + ".".join(self.prerelease)
        if self.build:
            text = text + "+" + ".".join(self.build)
        return text

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
        return self.format()


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing and precedence comparison."""

    @operation
    def parse_version(self, text: str) -> Version:
        """Parses a version string conforming to SemVer 2.0.0.

        Args:
            text: Raw version string to parse.

        Returns:
            The parsed immutable Version record.

        Raises:
            InvalidVersionError: If the text violates the SemVer 2.0.0 grammar.
        """
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions.

        Args:
            v1: First semantic version.
            v2: Second semantic version.

        Returns:
            A negative integer when v1 precedes v2, zero when they are equal in
            precedence, and a positive integer when v1 follows v2.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:14:33Z
# LAST_CHANGED: 2026-11-15T04:14:33Z
# CHANGE: Author semver_core interface: SemVerError/InvalidVersionError records, ComparatorOp, frozen Version data type with canonical format and prerelease predicate, and VersionEngine protocol stubs
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Concrete realization of semantic version parsing and precedence comparison."""

from __future__ import annotations

import re

from support.lib.lifecycle import singleton

from . import semver_core
from .semver_core import InvalidVersionError, Version

__all__ = ["VersionEngine"]


_SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


def _is_numeric_identifier(identifier: str) -> bool:
    """Reports whether a pre-release identifier consists solely of ASCII digits."""
    return identifier.isascii() and identifier.isdigit()


def _compare_identifiers(left: str, right: str) -> int:
    """Compares two pre-release identifiers according to SemVer precedence rules."""
    left_numeric = _is_numeric_identifier(left)
    right_numeric = _is_numeric_identifier(right)
    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        if left_value < right_value:
            return -1
        if left_value > right_value:
            return 1
        return 0
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


@singleton
class VersionEngine(semver_core.VersionEngine):
    tier = "system"

    def parse_version(self, text: str) -> Version:
        match = _SEMVER_PATTERN.fullmatch(text)
        if match is None:
            raise InvalidVersionError(
                f"Invalid semantic version string {text!r}", text
            )
        prerelease_text = match.group("prerelease")
        build_text = match.group("build")
        return Version(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=tuple(prerelease_text.split(".")) if prerelease_text else (),
            build=tuple(build_text.split(".")) if build_text else (),
        )

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # Numeric components dominate the ordering and are compared in sequence.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left < right:
                return -1
            if left > right:
                return 1

        # A normal version outranks any pre-release with the same numeric components.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # Compare the shared pre-release prefix, then rank the longer sequence higher.
        shared = min(len(v1.prerelease), len(v2.prerelease))
        for index in range(shared):
            comparison = _compare_identifiers(v1.prerelease[index], v2.prerelease[index])
            if comparison != 0:
                return comparison
        if len(v1.prerelease) < len(v2.prerelease):
            return -1
        if len(v1.prerelease) > len(v2.prerelease):
            return 1
        return 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:28:57Z
# LAST_CHANGED: 2026-11-15T04:14:39Z
# CHANGE: Author semver_core_impl: regex-validated SemVer 2.0.0 parser rejecting leading zeroes and grammar violations, plus tri-state precedence comparison honoring prerelease ordering and ignoring build metadata
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T04:28:57Z
# PRETENSE_QA_AUDIT: 2026-11-15T04:27:12Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Interface specification for version range parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type
from . import semver_core

__all__ = [
    "InvalidRangeError",
    "RangeEngine",
    "VersionRange",
]


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
        """Parses a version range expression into an immutable VersionRange record.

        Args:
            text: Raw range expression text.

        Returns:
            The parsed VersionRange.

        Raises:
            InvalidRangeError: If the text contains malformed range syntax.
        """
        ...

    @operation
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint.

        Args:
            version: Candidate semantic version to test.
            range_constraint: Version range to evaluate against.
            include_prerelease: Whether pre-release versions may match a range
                that does not explicitly target them.

        Returns:
            True if the version satisfies the range, False otherwise.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:14:45Z
# LAST_CHANGED: 2026-11-15T04:14:45Z
# CHANGE: Author semver_range interface: InvalidRangeError record, frozen VersionRange value type, and RangeEngine protocol stubs for parsing and satisfaction
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Concrete realization of version range parsing and constraint matching."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from support.lib.framework import unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import semver_core, semver_range
from .semver_range import InvalidRangeError, VersionRange

__all__ = ["RangeEngine"]


_NUMERIC_PART = re.compile(r"0|[1-9][0-9]*")

_WILDCARD_PARTS = frozenset({"x", "X", "*"})

_OPERATOR_TOKENS: Dict[str, str] = {
    "==": "==",
    "=": "==",
    "!=": "!=",
    "<": "<",
    "<=": "<=",
    ">": ">",
    ">=": ">=",
    "^": "^",
    "~": "~",
}

# A compiled comparator pairs a normalized operator with its concrete boundary version.
_Comparator = Tuple[str, semver_core.Version]
# A parsed bound holds the count of specified numeric components and its concrete lower version.
_Bound = Tuple[int, semver_core.Version]


@singleton
class RangeEngine(semver_range.RangeEngine):
    tier = "system"

    def parse_range(self, text: str) -> VersionRange:
        engine = get_singleton(semver_core.VersionEngine)
        trimmed = text.strip()
        # Compiling validates the whole expression before it is stored verbatim.
        self._compile(trimmed, engine)
        return VersionRange(raw_text=trimmed)

    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        engine = get_singleton(semver_core.VersionEngine)
        clauses = self._compile(range_constraint.raw_text, engine)
        # Pre-release candidates only match when a comparator names that exact release line.
        if version.is_prerelease and not include_prerelease:
            if not self._targets_prerelease(clauses, version):
                return False
        for clause in clauses:
            if all(self._matches(engine, version, operator, boundary) for operator, boundary in clause):
                return True
        return False

    def _compile(
        self, text: str, engine: semver_core.VersionEngine
    ) -> List[List[_Comparator]]:
        trimmed = text.strip()
        if not trimmed:
            raise InvalidRangeError("Version range expression is empty", text)
        # Comparators are delimited by whitespace only; commas are never permitted.
        if "," in trimmed:
            raise InvalidRangeError(
                f"Comma delimiters are not permitted in range {text!r}", text
            )
        clauses: List[List[_Comparator]] = []
        for clause_text in trimmed.split("||"):
            clause = clause_text.strip()
            if not clause:
                raise InvalidRangeError(
                    f"Range expression contains an empty union clause: {text!r}", text
                )
            clauses.extend(self._compile_clause(clause, engine, text))
        return clauses

    def _compile_clause(
        self, clause: str, engine: semver_core.VersionEngine, raw_range: str
    ) -> List[List[_Comparator]]:
        tokens = clause.split()
        if "-" in tokens:
            # A hyphen clause joins exactly two bounds and nothing else.
            if len(tokens) != 3 or tokens[1] != "-":
                raise InvalidRangeError(
                    f"Malformed hyphen range clause {clause!r}", raw_range
                )
            lower = self._parse_bound(tokens[0], engine, raw_range)
            upper = self._parse_bound(tokens[2], engine, raw_range)
            return [self._hyphen_clause(lower, upper)]

        alternatives: List[List[_Comparator]] = [[]]
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in _OPERATOR_TOKENS:
                if index + 1 >= len(tokens):
                    raise InvalidRangeError(
                        f"Comparator operator {token!r} has no operand", raw_range
                    )
                operator = _OPERATOR_TOKENS[token]
                operand_text = tokens[index + 1]
                index += 2
            else:
                operator, operand_text = self._split_operator(token)
                index += 1
            if operand_text in _OPERATOR_TOKENS or operand_text == "-":
                raise InvalidRangeError(
                    f"Malformed comparator {token!r} in range {raw_range!r}", raw_range
                )
            bound = self._parse_bound(operand_text, engine, raw_range)
            expansion = self._expand(operator, bound)
            # Negated wildcards branch into disjunctive alternatives, so cross-multiply.
            alternatives = [left + right for left in alternatives for right in expansion]
        return alternatives

    def _split_operator(self, token: str) -> Tuple[str, str]:
        for prefix in ("==", "!=", "<=", ">="):
            if token.startswith(prefix) and len(token) > len(prefix):
                return _OPERATOR_TOKENS[prefix], token[len(prefix):]
        if len(token) > 1 and token[0] in "=<>^~":
            return _OPERATOR_TOKENS[token[0]], token[1:]
        return "==", token

    def _parse_bound(
        self, token: str, engine: semver_core.VersionEngine, raw_range: str
    ) -> _Bound:
        try:
            version = engine.parse_version(token)
        except semver_core.InvalidVersionError:
            # Anything that is not a full version must be an explicit wildcard expression.
            return self._parse_wildcard(token, raw_range)
        return (3, version)

    def _parse_wildcard(self, token: str, raw_range: str) -> _Bound:
        parts = token.split(".")
        if len(parts) > 3 or not parts:
            raise InvalidRangeError(
                f"Malformed version or wildcard {token!r} in range {raw_range!r}", raw_range
            )
        components: List[int] = []
        wildcard_seen = False
        for part in parts:
            if part in _WILDCARD_PARTS:
                wildcard_seen = True
                continue
            if wildcard_seen or _NUMERIC_PART.fullmatch(part) is None:
                raise InvalidRangeError(
                    f"Malformed version or wildcard {token!r} in range {raw_range!r}", raw_range
                )
            components.append(int(part))
        if not wildcard_seen:
            # Bare partial versions without a wildcard are never valid bounds.
            raise InvalidRangeError(
                f"Partial version {token!r} requires a wildcard; range {raw_range!r}", raw_range
            )
        filled = components + [0] * (3 - len(components))
        return (len(components), semver_core.Version(filled[0], filled[1], filled[2]))

    def _upper_bound(self, bound: _Bound) -> Optional[semver_core.Version]:
        precision, version = bound
        # Full versions and the empty prefix have no exclusive upper sibling.
        if precision == 3 or precision == 0:
            return None
        index = precision - 1
        values = [version.major, version.minor, version.patch]
        values[index] += 1
        for trailing in range(index + 1, 3):
            values[trailing] = 0
        return semver_core.Version(values[0], values[1], values[2])

    def _caret_upper(self, bound: _Bound) -> Optional[semver_core.Version]:
        precision, version = bound
        values = [version.major, version.minor, version.patch]
        if precision == 3:
            # A full version allows changes down to its first non-zero component.
            if version.major > 0:
                return semver_core.Version(values[0] + 1, 0, 0)
            if version.minor > 0:
                return semver_core.Version(0, values[1] + 1, 0)
            return semver_core.Version(0, 0, values[2] + 1)
        if precision == 0:
            return None
        index = 0
        while index < precision and values[index] == 0:
            index += 1
        if index >= precision:
            index = precision - 1
        values[index] += 1
        for trailing in range(index + 1, 3):
            values[trailing] = 0
        return semver_core.Version(values[0], values[1], values[2])

    def _expand(self, operator: str, bound: _Bound) -> List[List[_Comparator]]:
        precision, version = bound
        if precision == 3:
            if operator == "==":
                return [[("==", version)]]
            if operator == "!=":
                return [[("!=", version)]]
            if operator == "<":
                return [[("<", version)]]
            if operator == "<=":
                return [[("<=", version)]]
            if operator == ">":
                return [[(">", version)]]
            if operator == ">=":
                return [[(">=", version)]]
            upper = self._caret_upper(bound)
            if operator == "^":
                if upper is None:
                    # A full version always yields a caret upper bound.
                    with unreachable("full version caret bounds are never unbounded"):
                        return [[]]
                return [[(">=", version), ("<", upper)]]
            # Tilde keeps the major/minor line fixed and allows patch-level growth.
            return [[(">=", version), ("<", semver_core.Version(version.major, version.minor + 1, 0))]]

        upper = self._upper_bound(bound)
        if operator == "==":
            if upper is None:
                return [[(">=", version)]]
            return [[(">=", version), ("<", upper)]]
        if operator == "!=":
            if upper is None:
                # The empty prefix wildcard forbids every release, an unsatisfiable clause.
                unsatisfiable = semver_core.Version(0, 0, 0)
                return [[("==", unsatisfiable), ("!=", unsatisfiable)]]
            return [[("<", version)], [(">=", upper)]]
        if operator == ">=":
            return [[(">=", version)]]
        if operator == ">":
            if upper is None:
                return [[]]
            return [[(">=", upper)]]
        if operator == "<":
            return [[("<", version)]]
        if operator == "<=":
            if upper is None:
                return [[]]
            return [[("<", upper)]]
        if operator == "^":
            caret_upper = self._caret_upper(bound)
            if caret_upper is None:
                return [[]]
            return [[(">=", version), ("<", caret_upper)]]
        if precision == 0:
            return [[]]
        if precision == 1:
            return [[(">=", version), ("<", semver_core.Version(version.major + 1, 0, 0))]]
        return [[(">=", version), ("<", semver_core.Version(version.major, version.minor + 1, 0))]]

    def _hyphen_clause(self, lower: _Bound, upper: _Bound) -> List[_Comparator]:
        clause: List[_Comparator] = [(">=", lower[1])]
        if upper[0] == 3:
            clause.append(("<=", upper[1]))
        else:
            exclusive_upper = self._upper_bound(upper)
            if exclusive_upper is not None:
                clause.append(("<", exclusive_upper))
        return clause

    def _targets_prerelease(
        self, clauses: List[List[_Comparator]], version: semver_core.Version
    ) -> bool:
        release_line = (version.major, version.minor, version.patch)
        for clause in clauses:
            for _, boundary in clause:
                if not boundary.is_prerelease:
                    continue
                if (boundary.major, boundary.minor, boundary.patch) == release_line:
                    return True
        return False

    def _matches(
        self,
        engine: semver_core.VersionEngine,
        version: semver_core.Version,
        operator: str,
        boundary: semver_core.Version,
    ) -> bool:
        comparison = engine.compare_precedence(version, boundary)
        if operator == "==":
            return comparison == 0
        if operator == "!=":
            return comparison != 0
        if operator == "<":
            return comparison < 0
        if operator == "<=":
            return comparison <= 0
        if operator == ">":
            return comparison > 0
        return comparison >= 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:34:35Z
# LAST_CHANGED: 2026-11-15T04:24:49Z
# CHANGE: Mark the caret upper-bound absence guard for full version operands as unreachable using with unreachable(...), since a full version always yields a caret upper bound; wildcard caret and hyphen None guards remain reachable
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T04:34:35Z
# PRETENSE_QA_AUDIT: 2026-11-15T04:34:20Z
# --- END AUTOFAB METADATA ---
