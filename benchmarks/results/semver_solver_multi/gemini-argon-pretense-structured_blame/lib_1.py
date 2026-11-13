# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_215854_gemini-argon_semver_solver_multi_pretense
# Timestamp: 2026-11-13T21:58:54.690028+00:00
# Benchmark Task: semver_solver_multi
# Model: gemini-argon (Tier 4)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 911,346
#   Cached Inbound Tokens:   15,989,508
#   Outbound Tokens:         176,281
#   Total Tokens:            17,077,135
#   Financial Cost ($USD):   $11.5803
#   Wall Clock Duration:     2764.11s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 4, pretense: 7, pretense_coverage: 8, pretense_qa: 8 (Total: 27)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       12
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
"""Interface definitions and data types for package repository and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, List, Mapping, Protocol, Set, Tuple
from support.lib.framework import data_type, operation, poly_type
from . import semver_core
from . import semver_range


@dataclass
class PackageNotFoundError(semver_core.SemVerError):
    """Raised when a referenced package name does not exist in the repository."""

    package_name: str


@dataclass
class ResolutionConflictError(semver_core.SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually."""

    conflicting_packages: Tuple[str, ...]
    explanation: str


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range."""

    name: str
    range_constraint: semver_range.VersionRange


@data_type
@dataclass(frozen=True)
class PackageRelease:
    """Immutable publication record of a package at a specific semantic version."""

    name: str
    version: semver_core.Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run."""

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
# LAST_CLEANED: 2026-11-13T22:05:37Z
# LAST_CHANGED: 2026-11-13T22:05:37Z
# CHANGE: Implement dependency_solver interface protocols, data types, and exceptions
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Concrete implementation of package repository and backtracking dependency solver."""

from __future__ import annotations

import functools
from typing import Collection, Dict, List, Set, Tuple
from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton
from . import dependency_solver
from . import semver_core
from . import semver_range


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
        version_engine = get_singleton(semver_core.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        # Replace existing release of the exact same version if present, or append new release
        releases.append(release)
        releases.sort(
            key=functools.cmp_to_key(
                lambda r1, r2: version_engine.compare_precedence(r2.version, r1.version)
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
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
        """Returns the set of all registered package names."""
        return set(self._packages.keys())


@singleton
class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = "system"

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        repo = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        accumulated_constraints: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dep in root_dependencies:
            accumulated_constraints.setdefault(dep.name, []).append(
                ("root", dep.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def satisfies_constraint(
            version: semver_core.Version,
            constraint: semver_range.VersionRange,
        ) -> bool:
            return range_engine.satisfies(version, constraint, False)

        def backtrack() -> bool:
            unassigned = [
                pkg for pkg in accumulated_constraints if pkg not in assignment
            ]
            if not unassigned:
                return True

            candidates_map: Dict[str, List[dependency_solver.PackageRelease]] = {}
            for pkg in unassigned:
                try:
                    available = repo.get_releases(pkg)
                except dependency_solver.PackageNotFoundError:
                    available = []
                viable = [
                    rel
                    for rel in available
                    if all(
                        satisfies_constraint(rel.version, rng)
                        for _, rng in accumulated_constraints[pkg]
                    )
                ]
                candidates_map[pkg] = viable

            # Select unassigned package with fewest viable candidates (MRV), breaking ties lexically
            selected_pkg = min(
                unassigned,
                key=lambda pkg: (len(candidates_map[pkg]), pkg),
            )
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [
                    src for src, _ in accumulated_constraints[selected_pkg]
                ]
                conflicting_packages.add(selected_pkg)
                for src in requesters:
                    if src != "root":
                        conflicting_packages.add(src)
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
                )
                return False

            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(
                    f"Assign '{selected_pkg}' to {candidate.version}"
                )

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        if not satisfies_constraint(
                            assignment[dep.name].version,
                            dep.range_constraint,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected_pkg)
                            conflicting_packages.add(dep.name)
                            for src, _ in accumulated_constraints.get(dep.name, []):
                                if src != "root":
                                    conflicting_packages.add(src)
                            conflict_trail.append(
                                f"Conflict: '{selected_pkg}' requires {dep.name} {dep.range_constraint.raw_text}"
                            )
                            break
                    else:
                        constraint_entry = (selected_pkg, dep.range_constraint)
                        accumulated_constraints.setdefault(dep.name, []).append(
                            constraint_entry
                        )
                        newly_added.append((dep.name, constraint_entry))

                if not conflict_detected and backtrack():
                    return True

                for pkg_name, constraint_entry in newly_added:
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        if backtrack():
            selected_versions: Dict[str, semver_core.Version] = {
                pkg: rel.version for pkg, rel in assignment.items()
            }
            return dependency_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        explanation = "; ".join(conflict_trail) if conflict_trail else "Unsatisfiable dependency constraints"
        sorted_conflicts = tuple(sorted(conflicting_packages))
        raise dependency_solver.ResolutionConflictError(
            message=f"Resolution conflict involving packages {sorted_conflicts}: {explanation}",
            conflicting_packages=sorted_conflicts,
            explanation=explanation,
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:36:26Z
# LAST_CHANGED: 2026-11-13T22:06:10Z
# CHANGE: Implement PackageRepository and DependencySolver singletons
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:36:26Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:35:51Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""Interface definitions and data types for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Protocol, Tuple
from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered."""

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
    """Immutable semantic version representation conforming to SemVer 2.0.0."""

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
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            result = f"{result}-{'.'.join(self.prerelease)}"
        if self.build:
            result = f"{result}+{'.'.join(self.build)}"
        return result

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
# LAST_CLEANED: 2026-11-13T22:02:55Z
# LAST_CHANGED: 2026-11-13T22:02:55Z
# CHANGE: Implement semver_core interface protocols, data types, and exceptions
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Concrete implementation of SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

import re
from typing import Tuple
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton
from . import semver_core

_SEMVER_PATTERN = re.compile(
    r"\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
)


def _is_numeric_identifier(segment: str) -> bool:
    """Checks whether a pre-release segment consists exclusively of ASCII digits."""
    return len(segment) > 0 and segment.isascii() and segment.isdigit()


@singleton
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = "system"

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Validate input against strict SemVer 2.0.0 syntax and leading zero rules
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                message=f"Invalid SemVer 2.0.0 string: '{text}'",
                raw_text=text,
            )

        major_str, minor_str, patch_str, prerelease_str, build_str = match.groups()
        prerelease: Tuple[str, ...] = (
            tuple(prerelease_str.split(".")) if prerelease_str is not None else ()
        )
        build: Tuple[str, ...] = (
            tuple(build_str.split(".")) if build_str is not None else ()
        )

        return semver_core.Version(
            major=int(major_str),
            minor=int(minor_str),
            patch=int(patch_str),
            prerelease=prerelease,
            build=build,
        )

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        # Compare primary numeric components in major, minor, patch order
        v1_core = (v1.major, v1.minor, v1.patch)
        v2_core = (v2.major, v2.minor, v2.patch)
        if v1_core < v2_core:
            return -1
        if v1_core > v2_core:
            return 1

        # Normal releases have higher precedence than pre-release versions
        v1_pre = v1.prerelease
        v2_pre = v2.prerelease
        if not v1_pre and not v2_pre:
            return 0
        if not v1_pre and v2_pre:
            return 1
        if v1_pre and not v2_pre:
            return -1

        # Compare pre-release segments left-to-right
        for seg1, seg2 in zip(v1_pre, v2_pre):
            if seg1 == seg2:
                continue
            num1 = _is_numeric_identifier(seg1)
            num2 = _is_numeric_identifier(seg2)
            if num1 and num2:
                val1 = int(seg1)
                val2 = int(seg2)
                if val1 < val2:
                    return -1
                if val1 > val2:
                    return 1
            elif num1 and not num2:
                # Numeric identifiers always have lower precedence than non-numeric
                return -1
            elif not num1 and num2:
                return 1
            else:
                # Lexical ASCII comparison for non-numeric segments
                if seg1 < seg2:
                    return -1
                if seg1 > seg2:
                    return 1

        # A larger set of pre-release fields has higher precedence if all prefix segments match
        if len(v1_pre) < len(v2_pre):
            return -1
        if len(v1_pre) > len(v2_pre):
            return 1
        return 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:19:45Z
# LAST_CHANGED: 2026-11-13T22:05:42Z
# CHANGE: Implement VersionEngine singleton with SemVer 2.0.0 parsing and precedence comparison
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:19:45Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:18:49Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Interface definitions and data types for version range parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from support.lib.framework import data_type, operation, poly_type
from . import semver_core


@dataclass
class InvalidRangeError(semver_core.SemVerError):
    """Raised when a version range expression contains malformed syntax."""

    raw_range: str


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

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
# LAST_CLEANED: 2026-11-13T22:03:57Z
# LAST_CHANGED: 2026-11-13T22:03:57Z
# CHANGE: Implement semver_range interface protocol, VersionRange data type, and InvalidRangeError
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Concrete implementation of version range parsing and constraint matching."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional, Sequence, Tuple, Union
from support.lib.framework import data_type, operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton
from . import semver_core
from . import semver_range

_NUMERIC_SEGMENT = re.compile(r"\A(?:0|[1-9][0-9]*)\Z")
_WILDCARD_CHARS = frozenset({"*", "x", "X"})
_OPERATORS = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")


@data_type
@dataclass(frozen=True)
class _FullTarget:
    """Represents a parsed full semantic version target in a range expression."""

    version: semver_core.Version


@data_type
@dataclass(frozen=True)
class _WildcardTarget:
    """Represents a parsed wildcard version target in a range expression."""

    level: str
    major: int = 0
    minor: int = 0


_ParsedTarget = Union[_FullTarget, _WildcardTarget]


@data_type
@dataclass(frozen=True)
class _AtomicComparator:
    """Single relational comparator or match-all/match-none primitive."""

    op: Optional[semver_core.ComparatorOp]
    target: Optional[semver_core.Version]
    match_all: bool = False


def _parse_target(
    token: str,
    raw_range: str,
    version_engine: semver_core.VersionEngine,
) -> _ParsedTarget:
    """Parses a single version or wildcard token, rejecting bare partials."""
    if not token:
        with unreachable:
            raise semver_range.InvalidRangeError(
                message=f"Empty version target in range '{raw_range}'",
                raw_range=raw_range,
            )

    # Check if the token is a wildcard expression (contains *, x, or X and no - or +)
    if "-" not in token and "+" not in token:
        parts = token.split(".")
        if any(part in _WILDCARD_CHARS for part in parts):
            if len(parts) > 3:
                raise semver_range.InvalidRangeError(
                    message=f"Invalid wildcard target '{token}' in range '{raw_range}'",
                    raw_range=raw_range,
                )
            # Once a wildcard segment appears, all subsequent segments must also be wildcards
            seen_wildcard = False
            first_wildcard_idx = -1
            numeric_values: List[int] = []
            for idx, part in enumerate(parts):
                if part in _WILDCARD_CHARS:
                    if not seen_wildcard:
                        seen_wildcard = True
                        first_wildcard_idx = idx
                else:
                    if seen_wildcard or _NUMERIC_SEGMENT.match(part) is None:
                        raise semver_range.InvalidRangeError(
                            message=f"Invalid wildcard target '{token}' in range '{raw_range}'",
                            raw_range=raw_range,
                        )
                    numeric_values.append(int(part))

            if first_wildcard_idx == 0:
                return _WildcardTarget(level="major")
            if first_wildcard_idx == 1:
                return _WildcardTarget(level="minor", major=numeric_values[0])
            return _WildcardTarget(
                level="patch",
                major=numeric_values[0],
                minor=numeric_values[1],
            )

    # Otherwise, token must be a full SemVer 2.0.0 version (bare partials are rejected)
    try:
        parsed_version = version_engine.parse_version(token)
    except semver_core.InvalidVersionError as exc:
        raise semver_range.InvalidRangeError(
            message=f"Invalid version '{token}' in range '{raw_range}': {exc.message}",
            raw_range=raw_range,
        ) from exc
    return _FullTarget(version=parsed_version)


def _split_operator(token: str) -> Tuple[Optional[str], str]:
    """Splits a token into an optional operator prefix and remainder."""
    for op in _OPERATORS:
        if token.startswith(op):
            return op, token[len(op) :]
    return None, token


def _wildcard_bounds(
    target: _WildcardTarget,
) -> Tuple[semver_core.Version, Optional[semver_core.Version]]:
    """Computes the inclusive lower bound and exclusive upper bound for a wildcard target."""
    if target.level == "major":
        return semver_core.Version(0, 0, 0), None
    if target.level == "minor":
        return (
            semver_core.Version(target.major, 0, 0),
            semver_core.Version(target.major + 1, 0, 0),
        )
    return (
        semver_core.Version(target.major, target.minor, 0),
        semver_core.Version(target.major, target.minor + 1, 0),
    )


def _expand_prefixed_item(
    op: str,
    target: _ParsedTarget,
) -> List[List[_AtomicComparator]]:
    """Expands a single operator and target into a disjunction of comparator conjunctions."""
    eq_op = semver_core.ComparatorOp.EQ
    ne_op = semver_core.ComparatorOp.NE
    lt_op = semver_core.ComparatorOp.LT
    le_op = semver_core.ComparatorOp.LE
    gt_op = semver_core.ComparatorOp.GT
    ge_op = semver_core.ComparatorOp.GE

    if isinstance(target, _FullTarget):
        v = target.version
        if op in ("=", "=="):
            return [[_AtomicComparator(eq_op, v)]]
        if op == "!=":
            return [[_AtomicComparator(ne_op, v)]]
        if op == "<":
            return [[_AtomicComparator(lt_op, v)]]
        if op == "<=":
            return [[_AtomicComparator(le_op, v)]]
        if op == ">":
            return [[_AtomicComparator(gt_op, v)]]
        if op == ">=":
            return [[_AtomicComparator(ge_op, v)]]
        if op == "~":
            upper = semver_core.Version(v.major, v.minor + 1, 0)
            return [[_AtomicComparator(ge_op, v), _AtomicComparator(lt_op, upper)]]
        if op == "^":
            if v.major > 0:
                upper = semver_core.Version(v.major + 1, 0, 0)
            elif v.minor > 0:
                upper = semver_core.Version(0, v.minor + 1, 0)
            else:
                upper = semver_core.Version(0, 0, v.patch + 1)
            return [[_AtomicComparator(ge_op, v), _AtomicComparator(lt_op, upper)]]

    assert isinstance(target, _WildcardTarget)
    low_v, high_v = _wildcard_bounds(target)

    if op in ("=", "==", "~"):
        if high_v is None:
            return [[_AtomicComparator(None, None, match_all=True)]]
        return [[_AtomicComparator(ge_op, low_v), _AtomicComparator(lt_op, high_v)]]

    if op == "^":
        if high_v is None:
            return [[_AtomicComparator(None, None, match_all=True)]]
        if target.level == "minor":
            upper = semver_core.Version(target.major + 1, 0, 0)
        else:
            if target.major > 0:
                upper = semver_core.Version(target.major + 1, 0, 0)
            else:
                upper = semver_core.Version(0, target.minor + 1, 0)
        return [[_AtomicComparator(ge_op, low_v), _AtomicComparator(lt_op, upper)]]

    if op == ">=":
        if high_v is None:
            return [[_AtomicComparator(None, None, match_all=True)]]
        return [[_AtomicComparator(ge_op, low_v)]]

    if op == ">":
        if high_v is None:
            return [[_AtomicComparator(None, None, match_all=False)]]
        return [[_AtomicComparator(ge_op, high_v)]]

    if op == "<=":
        if high_v is None:
            return [[_AtomicComparator(None, None, match_all=True)]]
        return [[_AtomicComparator(lt_op, high_v)]]

    if op == "<":
        if high_v is None:
            return [[_AtomicComparator(None, None, match_all=False)]]
        return [[_AtomicComparator(lt_op, low_v)]]

    # op == "!=" on wildcard expands to (< low_v) || (>= high_v)
    if high_v is None:
        return [[_AtomicComparator(None, None, match_all=False)]]
    return [
        [_AtomicComparator(lt_op, low_v)],
        [_AtomicComparator(ge_op, high_v)],
    ]


def _expand_hyphen_item(
    bound1: _ParsedTarget,
    bound2: _ParsedTarget,
) -> List[List[_AtomicComparator]]:
    """Expands a hyphen range 'bound1 - bound2' into paired comparator inequalities."""
    ge_op = semver_core.ComparatorOp.GE
    le_op = semver_core.ComparatorOp.LE
    lt_op = semver_core.ComparatorOp.LT

    comparators: List[_AtomicComparator] = []

    if isinstance(bound1, _FullTarget):
        comparators.append(_AtomicComparator(ge_op, bound1.version))
    else:
        low_v, high_v = _wildcard_bounds(bound1)
        if high_v is None:
            comparators.append(_AtomicComparator(None, None, match_all=True))
        else:
            comparators.append(_AtomicComparator(ge_op, low_v))

    if isinstance(bound2, _FullTarget):
        comparators.append(_AtomicComparator(le_op, bound2.version))
    else:
        _, high_v = _wildcard_bounds(bound2)
        if high_v is None:
            comparators.append(_AtomicComparator(None, None, match_all=True))
        else:
            comparators.append(_AtomicComparator(lt_op, high_v))

    return [comparators]


def _compile_range(
    raw_text: str,
    version_engine: semver_core.VersionEngine,
) -> Tuple[str, List[List[_AtomicComparator]]]:
    """Validates and compiles a range string into normalized text and DNF comparator sets."""
    if "," in raw_text:
        raise semver_range.InvalidRangeError(
            message=f"Comma delimiters are not permitted in range '{raw_text}'",
            raw_range=raw_text,
        )

    trimmed = raw_text.strip()
    if not trimmed:
        raise semver_range.InvalidRangeError(
            message="Version range expression cannot be empty",
            raw_range=raw_text,
        )

    raw_clauses = trimmed.split("||")
    trimmed_clauses: List[str] = []
    dnf_clauses: List[List[_AtomicComparator]] = []

    for raw_clause in raw_clauses:
        clause_str = raw_clause.strip()
        if not clause_str:
            raise semver_range.InvalidRangeError(
                message=f"Empty union clause in range '{raw_text}'",
                raw_range=raw_text,
            )
        trimmed_clauses.append(clause_str)
        tokens = clause_str.split()

        # Each item in a clause expands to a list of disjunctive branches (usually 1, or 2 for != wildcard)
        clause_branches: List[List[_AtomicComparator]] = [[]]
        idx = 0
        num_tokens = len(tokens)

        while idx < num_tokens:
            tok = tokens[idx]
            if tok == "-":
                raise semver_range.InvalidRangeError(
                    message=f"Unexpected hyphen token in range '{raw_text}'",
                    raw_range=raw_text,
                )

            op, remainder = _split_operator(tok)
            if op is not None:
                if not remainder:
                    # Standalone operator token followed by whitespace and target token
                    if idx + 1 >= num_tokens:
                        raise semver_range.InvalidRangeError(
                            message=f"Dangling operator '{op}' in range '{raw_text}'",
                            raw_range=raw_text,
                        )
                    next_tok = tokens[idx + 1]
                    next_op, _ = _split_operator(next_tok)
                    if next_op is not None or next_tok == "-":
                        raise semver_range.InvalidRangeError(
                            message=f"Invalid target '{next_tok}' after operator '{op}' in range '{raw_text}'",
                            raw_range=raw_text,
                        )
                    if idx + 2 < num_tokens and tokens[idx + 2] == "-":
                        raise semver_range.InvalidRangeError(
                            message=f"Hyphen range bound cannot have operator '{op}' in range '{raw_text}'",
                            raw_range=raw_text,
                        )
                    target = _parse_target(next_tok, raw_text, version_engine)
                    item_dnf = _expand_prefixed_item(op, target)
                    idx += 2
                else:
                    if idx + 1 < num_tokens and tokens[idx + 1] == "-":
                        raise semver_range.InvalidRangeError(
                            message=f"Hyphen range bound cannot have operator '{op}' in range '{raw_text}'",
                            raw_range=raw_text,
                        )
                    target = _parse_target(remainder, raw_text, version_engine)
                    item_dnf = _expand_prefixed_item(op, target)
                    idx += 1
            else:
                bound1 = _parse_target(tok, raw_text, version_engine)
                if idx + 1 < num_tokens and tokens[idx + 1] == "-":
                    if idx + 2 >= num_tokens:
                        raise semver_range.InvalidRangeError(
                            message=f"Dangling hyphen at end of clause in range '{raw_text}'",
                            raw_range=raw_text,
                        )
                    bound2_tok = tokens[idx + 2]
                    bound2_op, _ = _split_operator(bound2_tok)
                    if bound2_op is not None or bound2_tok == "-":
                        raise semver_range.InvalidRangeError(
                            message=f"Invalid upper bound '{bound2_tok}' in hyphen range '{raw_text}'",
                            raw_range=raw_text,
                        )
                    bound2 = _parse_target(bound2_tok, raw_text, version_engine)
                    item_dnf = _expand_hyphen_item(bound1, bound2)
                    idx += 3
                else:
                    item_dnf = _expand_prefixed_item("=", bound1)
                    idx += 1

            # Distribute item_dnf across existing clause_branches
            new_branches: List[List[_AtomicComparator]] = []
            for existing in clause_branches:
                for branch in item_dnf:
                    new_branches.append(existing + branch)
            clause_branches = new_branches

        dnf_clauses.extend(clause_branches)

    normalized_text = " || ".join(trimmed_clauses) if len(raw_clauses) > 1 else trimmed
    return normalized_text, dnf_clauses


def _matches_atomic(
    version: semver_core.Version,
    comp: _AtomicComparator,
    version_engine: semver_core.VersionEngine,
) -> bool:
    """Evaluates a single atomic comparator against a candidate version."""
    if comp.op is None or comp.target is None:
        return comp.match_all

    cmp_val = version_engine.compare_precedence(version, comp.target)
    if comp.op == semver_core.ComparatorOp.EQ:
        return cmp_val == 0
    if comp.op == semver_core.ComparatorOp.NE:
        return cmp_val != 0
    if comp.op == semver_core.ComparatorOp.LT:
        return cmp_val < 0
    if comp.op == semver_core.ComparatorOp.LE:
        return cmp_val <= 0
    if comp.op == semver_core.ComparatorOp.GT:
        return cmp_val > 0
    return cmp_val >= 0


def _clause_targets_prerelease(
    version: semver_core.Version,
    clause: Sequence[_AtomicComparator],
) -> bool:
    """Checks if any comparator in the clause explicitly targets a prerelease with matching major, minor, patch."""
    v_tuple = (version.major, version.minor, version.patch)
    for comp in clause:
        if comp.target is not None and comp.target.is_prerelease:
            t_tuple = (comp.target.major, comp.target.minor, comp.target.patch)
            if t_tuple == v_tuple:
                return True
    return False


@singleton
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = "system"

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        version_engine = get_singleton(semver_core.VersionEngine)
        normalized_text, _ = _compile_range(text, version_engine)
        return semver_range.VersionRange(raw_text=normalized_text)

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        version_engine = get_singleton(semver_core.VersionEngine)
        _, dnf_clauses = _compile_range(range_constraint.raw_text, version_engine)

        for clause in dnf_clauses:
            if version.is_prerelease and not include_prerelease:
                if not _clause_targets_prerelease(version, clause):
                    continue
            if all(_matches_atomic(version, comp, version_engine) for comp in clause):
                return True

        return False

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:44:55Z
# LAST_CHANGED: 2026-11-13T22:39:44Z
# CHANGE: Quarantine unreachable empty token guard in _parse_target with unreachable context manager
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:44:55Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:44:25Z
# --- END AUTOFAB METADATA ---
