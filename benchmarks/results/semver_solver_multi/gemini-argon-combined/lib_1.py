# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261106_201950_gemini-argon_semver_solver_multi_combined
# Timestamp: 2026-11-06T20:19:50.925769+00:00
# Benchmark Task: semver_solver_multi
# Model: gemini-argon (Tier 4)
# Methodology: combined
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 875,649
#   Cached Inbound Tokens:   6,774,214
#   Outbound Tokens:         200,331
#   Total Tokens:            7,850,194
#   Financial Cost ($USD):   $7.1417
#   Wall Clock Duration:     1798.01s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 4, lib: 4, pretense: 1, pretense_qa: 3, qa: 3, test: 3 (Total: 18)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       28
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
"""Low-level interface specification for package repository and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)
from support.lib.framework import data_type, operation, poly_type
from benchmark_2.parts.semver_solver_multi.lib import semver_core
from benchmark_2.parts.semver_solver_multi.lib import semver_range


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
# LAST_CLEANED: 2026-11-06T20:27:56Z
# LAST_CHANGED: 2026-11-06T20:27:56Z
# CHANGE: Implement dependency_solver interface module
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Low-level implementation specification for package repository and dependency resolution."""

from __future__ import annotations

import functools
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton
from benchmark_2.parts.semver_solver_multi.lib import dependency_solver
from benchmark_2.parts.semver_solver_multi.lib import semver_core
from benchmark_2.parts.semver_solver_multi.lib import semver_range


@singleton_type("system")
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
        # Insert release into _packages list for release.name
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # Re-sort release list in descending version precedence order
        releases.sort(
            key=functools.cmp_to_key(
                lambda r1, r2: version_engine.compare_precedence(r1.version, r2.version)
            ),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        # Look up name in _packages and raise PackageNotFoundError if missing
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
        # Produce a shallow copy of the sorted release list
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


@singleton_type("system")
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

        # Initialize accumulated constraint mapping from root_dependencies
        accumulated_constraints: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dep in root_dependencies:
            accumulated_constraints.setdefault(dep.name, []).append(
                ("root", dep.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            unassigned = [p for p in accumulated_constraints if p not in assignment]
            if not unassigned:
                return True

            # Determine viable candidate releases for each unassigned package
            candidates_map: Dict[str, List[dependency_solver.PackageRelease]] = {}
            for pkg in unassigned:
                try:
                    available = repo.get_releases(pkg)
                except dependency_solver.PackageNotFoundError:
                    # Treat unregistered packages absent from repository as having zero candidates
                    available = []
                viable = [
                    rel
                    for rel in available
                    if all(
                        range_engine.satisfies(rel.version, rng, False)
                        for _, rng in accumulated_constraints[pkg]
                    )
                ]
                candidates_map[pkg] = viable

            # Select unassigned package with fewest viable candidate releases (MRV heuristic)
            selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
                conflicting_packages.add(selected_pkg)
                conflicting_packages.update(r for r in requesters if r != "root")
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
                )
                return False

            # Iterate through available releases in descending version precedence order
            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(
                    f"Assign '{selected_pkg}' to {candidate.version}"
                )

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        if not range_engine.satisfies(
                            assignment[dep.name].version,
                            dep.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected_pkg)
                            conflicting_packages.add(dep.name)
                            conflicting_packages.update(
                                src
                                for src, _ in accumulated_constraints.get(dep.name, [])
                                if src != "root"
                            )
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

                # Backtrack and restore previous constraint mappings
                for pkg_name, constraint_entry in newly_added:
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        if backtrack():
            return dependency_solver.ResolutionOutcome(
                selected_versions={
                    pkg: rel.version for pkg, rel in assignment.items()
                },
                derivation_steps=tuple(derivation_steps),
            )

        explanation = "; ".join(conflict_trail)
        raise dependency_solver.ResolutionConflictError(
            message=f"Dependency resolution failed: {explanation}",
            conflicting_packages=tuple(sorted(conflicting_packages)),
            explanation=explanation,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, dependency_solver.PackageRepository],
        tier='system',
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, dependency_solver.DependencySolver],
        tier='system',
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:56Z
# LAST_CHANGED: 2026-11-06T20:28:05Z
# CHANGE: Implement dependency_solver_impl module
# COVERAGE_AUDIT: 2026-11-06T20:44:56Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:21Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:41:20Z
# QA_AUDIT: 2026-11-06T20:44:16Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""Low-level interface specification for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)
from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

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
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base = f"{base}-{'.'.join(self.prerelease)}"
        if self.build:
            base = f"{base}+{'.'.join(self.build)}"
        return base

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
# LAST_CLEANED: 2026-11-06T20:27:51Z
# LAST_CHANGED: 2026-11-06T20:27:51Z
# CHANGE: Implement semver_core interface module
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Low-level implementation specification for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton
from benchmark_2.parts.semver_solver_multi.lib import semver_core

_SEMVER_REGEX = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = "system"

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Validate SemVer 2.0.0 grammar and numerical leading zero constraints
        match = _SEMVER_REGEX.fullmatch(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                message=f"Invalid semantic version string: '{text}'",
                raw_text=text,
            )

        major_str, minor_str, patch_str, prerelease_str, build_str = match.groups()
        # Extract optional dot-separated pre-release segments and plus-separated build metadata segments
        prerelease = tuple(prerelease_str.split(".")) if prerelease_str else ()
        build = tuple(build_str.split(".")) if build_str else ()

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
        # Compare major, minor, and patch numbers numerically in sequence
        if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
            return -1 if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch) else 1

        # Evaluate pre-release presence when numeric components are identical
        if not v1.prerelease and not v2.prerelease:
            return 0
        # Rank normal version higher than pre-release version
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # Iterate through pre-release segments comparing each position
        for seg1, seg2 in zip(v1.prerelease, v2.prerelease):
            if seg1 == seg2:
                continue
            is_num1 = seg1.isdigit()
            is_num2 = seg2.isdigit()
            if is_num1 and is_num2:
                # Compare numeric segments as integers
                return -1 if int(seg1) < int(seg2) else 1
            if is_num1 != is_num2:
                # Rank numeric segments lower than string segments
                return -1 if is_num1 else 1
            # Compare string segments as ASCII code points
            return -1 if seg1 < seg2 else 1

        # Rank longer pre-release segment sequences higher when common prefix segments match
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

        # Exclude build metadata entirely from comparison
        return 0


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_core.VersionEngine],
        tier='system',
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:59Z
# LAST_CHANGED: 2026-11-06T20:27:59Z
# CHANGE: Implement semver_core_impl module
# COVERAGE_AUDIT: 2026-11-06T20:44:59Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:34:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:29:30Z
# QA_AUDIT: 2026-11-06T20:44:18Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Low-level interface specification for version range parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)
from support.lib.framework import data_type, operation, poly_type
from benchmark_2.parts.semver_solver_multi.lib import semver_core


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
# LAST_CLEANED: 2026-11-06T20:27:54Z
# LAST_CHANGED: 2026-11-06T20:27:54Z
# CHANGE: Implement semver_range interface module
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Low-level implementation specification for version range parsing and matching."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton
from benchmark_2.parts.semver_solver_multi.lib import semver_core
from benchmark_2.parts.semver_solver_multi.lib import semver_range

_OP_SPACE_RE = re.compile(r"(?:^|(?<=\s))(==|!=|<=|>=|=|<|>|\^|~)\s+")
_NUM_SEG_RE = re.compile(r"^(0|[1-9][0-9]*)$")
_SEMVER_REGEX = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
_WILDCARD_TOKENS = frozenset({"*", "x", "X"})
_OP_MAP: Dict[str, semver_core.ComparatorOp] = {
    "": semver_core.ComparatorOp.EQ,
    "=": semver_core.ComparatorOp.EQ,
    "==": semver_core.ComparatorOp.EQ,
    "!=": semver_core.ComparatorOp.NE,
    "<": semver_core.ComparatorOp.LT,
    "<=": semver_core.ComparatorOp.LE,
    ">": semver_core.ComparatorOp.GT,
    ">=": semver_core.ComparatorOp.GE,
}


def _parse_exact_version(
    token: str,
    raw_range: str,
    version_engine: semver_core.VersionEngine,
) -> semver_core.Version:
    """Validates SemVer 2.0.0 syntax and parses an exact version or raises InvalidRangeError."""
    if _SEMVER_REGEX.fullmatch(token) is None:
        raise semver_range.InvalidRangeError(
            message=f"Invalid version '{token}' in range '{raw_range}'",
            raw_range=raw_range,
        )
    return version_engine.parse_version(token)


def _try_expand_wildcard(
    op_str: str,
    target: str,
    raw_range: str,
) -> Optional[List[Tuple[semver_core.ComparatorOp, semver_core.Version]]]:
    """Expands wildcard expressions into paired comparator inequalities if target contains wildcards."""
    if "-" in target or "+" in target:
        return None
    parts = target.split(".")
    if not any(part in _WILDCARD_TOKENS for part in parts):
        return None

    # Validate wildcard structure and operator compatibility (bare or equality-prefixed only)
    if op_str not in ("", "=", "==") or not (1 <= len(parts) <= 3):
        raise semver_range.InvalidRangeError(
            message=f"Malformed wildcard expression '{op_str}{target}' in range '{raw_range}'",
            raw_range=raw_range,
        )

    first_wild = next(i for i, part in enumerate(parts) if part in _WILDCARD_TOKENS)
    if any(part not in _WILDCARD_TOKENS for part in parts[first_wild:]):
        raise semver_range.InvalidRangeError(
            message=f"Invalid non-wildcard trailing segment in '{target}'",
            raw_range=raw_range,
        )
    if any(_NUM_SEG_RE.fullmatch(part) is None for part in parts[:first_wild]):
        raise semver_range.InvalidRangeError(
            message=f"Invalid numeric segment in wildcard '{target}'",
            raw_range=raw_range,
        )

    if first_wild == 0:
        return [(semver_core.ComparatorOp.GE, semver_core.Version(0, 0, 0))]
    if first_wild == 1:
        major = int(parts[0])
        return [
            (semver_core.ComparatorOp.GE, semver_core.Version(major, 0, 0)),
            (semver_core.ComparatorOp.LT, semver_core.Version(major + 1, 0, 0)),
        ]
    major = int(parts[0])
    minor = int(parts[1])
    return [
        (semver_core.ComparatorOp.GE, semver_core.Version(major, minor, 0)),
        (semver_core.ComparatorOp.LT, semver_core.Version(major, minor + 1, 0)),
    ]


def _parse_comparator_token(
    token: str,
    raw_range: str,
    version_engine: semver_core.VersionEngine,
) -> List[Tuple[semver_core.ComparatorOp, semver_core.Version]]:
    """Parses a single comparator, caret, tilde, or wildcard token into comparator pairs."""
    op_str = ""
    target = token
    for prefix in ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~"):
        if token.startswith(prefix):
            op_str = prefix
            target = token[len(prefix) :]
            break

    if not target:
        raise semver_range.InvalidRangeError(
            message=f"Missing version target after operator '{op_str}' in '{raw_range}'",
            raw_range=raw_range,
        )

    # Check if target is a wildcard expression
    wildcard_comps = _try_expand_wildcard(op_str, target, raw_range)
    if wildcard_comps is not None:
        return wildcard_comps

    # Parse full SemVer version (rejects bare partial versions lacking wildcards)
    ver = _parse_exact_version(target, raw_range, version_engine)

    # Expand tilde prefixes into lower and upper minor boundaries
    if op_str == "~":
        upper = semver_core.Version(ver.major, ver.minor + 1, 0)
        return [
            (semver_core.ComparatorOp.GE, ver),
            (semver_core.ComparatorOp.LT, upper),
        ]

    # Expand caret prefixes based on first non-zero component boundaries
    if op_str == "^":
        if ver.major > 0:
            upper = semver_core.Version(ver.major + 1, 0, 0)
        elif ver.minor > 0:
            upper = semver_core.Version(0, ver.minor + 1, 0)
        else:
            upper = semver_core.Version(0, 0, ver.patch + 1)
        return [
            (semver_core.ComparatorOp.GE, ver),
            (semver_core.ComparatorOp.LT, upper),
        ]

    return [(_OP_MAP[op_str], ver)]


def _compile_range(
    raw_range: str,
    version_engine: semver_core.VersionEngine,
) -> List[List[Tuple[semver_core.ComparatorOp, semver_core.Version]]]:
    """Compiles a range expression into disjunctive normal form comparator sets."""
    trimmed = raw_range.strip()
    # Reject empty strings, whitespace-only strings, or comma-delimited expressions
    if not trimmed or "," in trimmed:
        raise semver_range.InvalidRangeError(
            message=f"Invalid range expression: '{raw_range}'",
            raw_range=raw_range,
        )

    clauses: List[List[Tuple[semver_core.ComparatorOp, semver_core.Version]]] = []
    for raw_clause in trimmed.split("||"):
        clause_str = raw_clause.strip()
        if not clause_str:
            raise semver_range.InvalidRangeError(
                message=f"Empty union clause in range: '{raw_range}'",
                raw_range=raw_range,
            )

        # Normalize optional whitespace after relational or prefix operators
        normalized = _OP_SPACE_RE.sub(r"\1", clause_str)
        tokens = normalized.split()
        comparators: List[Tuple[semver_core.ComparatorOp, semver_core.Version]] = []
        i = 0
        while i < len(tokens):
            if i + 1 < len(tokens) and tokens[i + 1] == "-":
                if i + 2 >= len(tokens):
                    raise semver_range.InvalidRangeError(
                        message=f"Incomplete hyphen range in '{raw_range}'",
                        raw_range=raw_range,
                    )
                # Normalize hyphen range into paired comparator inequalities
                low_v = _parse_exact_version(tokens[i], raw_range, version_engine)
                high_v = _parse_exact_version(tokens[i + 2], raw_range, version_engine)
                comparators.append((semver_core.ComparatorOp.GE, low_v))
                comparators.append((semver_core.ComparatorOp.LE, high_v))
                i += 3
            else:
                comparators.extend(
                    _parse_comparator_token(tokens[i], raw_range, version_engine)
                )
                i += 1
        clauses.append(comparators)

    return clauses


def _matches_comparator(
    cmp_val: int,
    op: semver_core.ComparatorOp,
) -> bool:
    """Evaluates comparison result against relational operator."""
    if op == semver_core.ComparatorOp.EQ:
        return cmp_val == 0
    if op == semver_core.ComparatorOp.NE:
        return cmp_val != 0
    if op == semver_core.ComparatorOp.LT:
        return cmp_val < 0
    if op == semver_core.ComparatorOp.LE:
        return cmp_val <= 0
    if op == semver_core.ComparatorOp.GT:
        return cmp_val > 0
    return cmp_val >= 0


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = "system"

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        version_engine = get_singleton(semver_core.VersionEngine)
        # Validate syntax and compile clauses
        _compile_range(text, version_engine)
        trimmed_clauses = [clause.strip() for clause in text.strip().split("||")]
        return semver_range.VersionRange(raw_text=" || ".join(trimmed_clauses))

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
        clauses = _compile_range(range_constraint.raw_text, version_engine)

        for clause in clauses:
            # Filter out pre-release versions when include_prerelease is False unless explicitly targeted
            if version.is_prerelease and not include_prerelease:
                explicitly_targeted = any(
                    target_v.is_prerelease
                    and (target_v.major, target_v.minor, target_v.patch)
                    == (version.major, version.minor, version.patch)
                    for _, target_v in clause
                )
                if not explicitly_targeted:
                    continue

            # Test candidate version against each comparator in the clause
            if all(
                _matches_comparator(
                    version_engine.compare_precedence(version, target_v),
                    op,
                )
                for op, target_v in clause
            ):
                return True

        return False


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RangeEngine,
        keys=[RangeEngine, semver_range.RangeEngine],
        tier='system',
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:49:46Z
# LAST_CHANGED: 2026-11-06T20:42:01Z
# CHANGE: Validate SemVer 2.0.0 syntax prior to version_engine.parse_version, restrict wildcards to bare or equality-prefixed forms, and trim clause whitespace
# COVERAGE_AUDIT: 2026-11-06T20:45:01Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:49:46Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:48:50Z
# QA_AUDIT: 2026-11-06T20:44:20Z
# --- END AUTOFAB METADATA ---
