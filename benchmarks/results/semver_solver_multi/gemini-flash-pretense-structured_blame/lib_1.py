# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_185746_gemini-flash_semver_solver_multi_pretense
# Timestamp: 2026-11-13T18:57:46.544572+00:00
# Benchmark Task: semver_solver_multi
# Model: gemini-flash (Tier 2)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 1,690,009
#   Cached Inbound Tokens:   50,841,620
#   Outbound Tokens:         299,768
#   Total Tokens:            52,831,397
#   Financial Cost ($USD):   $1.5599
#   Wall Clock Duration:     3114.50s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 2, pretense: 10, pretense_coverage: 11, pretense_qa: 15 (Total: 38)
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
"""Interface specification for package repository and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
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
# LAST_CLEANED: 2026-11-13T19:03:48Z
# LAST_CHANGED: 2026-11-13T19:03:48Z
# CHANGE: Implement dependency solver interfaces, data types, and exceptions
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Implementation of package repository and dependency resolution."""

from __future__ import annotations

import functools
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
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
        self._version_engine: Optional[semver_core.VersionEngine] = None

    def _get_version_engine(self) -> semver_core.VersionEngine:
        if self._version_engine is None:
            self._version_engine = get_singleton(semver_core.VersionEngine)
        return self._version_engine

    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        version_engine = self._get_version_engine()
        release_list = self._packages.setdefault(release.name, [])
        release_list.append(release)

        def cmp_releases(r1: dependency_solver.PackageRelease, r2: dependency_solver.PackageRelease) -> int:
            return -version_engine.compare_precedence(r1.version, r2.version)

        release_list.sort(key=functools.cmp_to_key(cmp_releases))

    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
        return list(self._packages[name])

    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    @override
    def all_packages(self) -> Set[str]:
        """Returns the set of all registered package names."""
        return set(self._packages.keys())


@singleton
class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = "system"

    def __init__(self) -> None:
        self._repo: Optional[dependency_solver.PackageRepository] = None
        self._range_engine: Optional[semver_range.RangeEngine] = None

    def _get_repo(self) -> dependency_solver.PackageRepository:
        if self._repo is None:
            self._repo = get_singleton(dependency_solver.PackageRepository)
        return self._repo

    def _get_range_engine(self) -> semver_range.RangeEngine:
        if self._range_engine is None:
            self._range_engine = get_singleton(semver_range.RangeEngine)
        return self._range_engine

    @override
    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        repo = self._get_repo()
        range_engine = self._get_range_engine()

        # Accumulated constraints map: package_name -> list of (requester, range_constraint)
        accumulated_constraints: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dep in root_dependencies:
            accumulated_constraints.setdefault(dep.name, []).append(("root", dep.range_constraint))

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def satisfies(v: semver_core.Version, rng: semver_range.VersionRange) -> bool:
            return range_engine.satisfies(v, rng, include_prerelease=False)

        def backtrack() -> bool:
            unassigned = [p for p in accumulated_constraints if p not in assignment]
            if not unassigned:
                return True

            candidates_map: Dict[str, List[dependency_solver.PackageRelease]] = {}
            for pkg in unassigned:
                try:
                    available = repo.get_releases(pkg)
                except dependency_solver.PackageNotFoundError:
                    available = []
                viable = [
                    rel for rel in available
                    if all(satisfies(rel.version, rng) for _, rng in accumulated_constraints[pkg])
                ]
                candidates_map[pkg] = viable

            # Minimum Remaining Values (MRV) heuristic with deterministic lexical tie-breaking
            selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
                conflicting_packages.add(selected_pkg)
                conflicting_packages.update(src for src in requesters if src != "root")
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
                )
                return False

            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        if not satisfies(assignment[dep.name].version, dep.range_constraint):
                            conflict_detected = True
                            conflicting_packages.add(selected_pkg)
                            conflicting_packages.add(dep.name)
                            conflict_trail.append(
                                f"Conflict: '{selected_pkg}' requires {dep.name} {getattr(dep.range_constraint, 'raw_text', '')}"
                            )
                            break
                    else:
                        constraint_entry = (selected_pkg, dep.range_constraint)
                        accumulated_constraints.setdefault(dep.name, []).append(constraint_entry)
                        newly_added.append((dep.name, constraint_entry))

                if not conflict_detected and backtrack():
                    return True

                # Undo newly added constraints upon backtracking
                for pkg_name, constraint_entry in newly_added:
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]

                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        success = backtrack()
        if not success:
            sorted_conflict_pkgs = tuple(sorted(conflicting_packages))
            explanation_text = "\n".join(conflict_trail) if conflict_trail else "No compatible version assignment found."
            raise dependency_solver.ResolutionConflictError(
                message=f"Dependency resolution failed due to conflict on {', '.join(sorted_conflict_pkgs)}",
                conflicting_packages=sorted_conflict_pkgs,
                explanation=explanation_text,
            )

        selected_versions = {pkg: rel.version for pkg, rel in assignment.items()}
        return dependency_solver.ResolutionOutcome(
            selected_versions=selected_versions,
            derivation_steps=tuple(derivation_steps),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T19:36:51Z
# LAST_CHANGED: 2026-11-13T19:08:40Z
# CHANGE: Implement PackageRepository and DependencySolver with MRV backtracking and conflict explanation
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T19:36:51Z
# PRETENSE_QA_AUDIT: 2026-11-13T19:34:57Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""Interface specification and core data types for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""
    message: str

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

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
        res = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            res = f"{res}-{'.'.join(self.prerelease)}"
        if self.build:
            res = f"{res}+{'.'.join(self.build)}"
        return res

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
# LAST_CLEANED: 2026-11-13T19:01:13Z
# LAST_CHANGED: 2026-11-13T19:01:13Z
# CHANGE: Implement SemVer 2.0 interface, exceptions, and Version data type
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Implementation of SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

import re
from support.lib.framework import override
from support.lib.lifecycle import singleton
from . import semver_core
from .semver_core import InvalidVersionError, Version


SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


@singleton
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = "system"

    def __init__(self) -> None:
        pass

    @override
    def parse_version(self, text: str) -> Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        match = SEMVER_REGEX.match(text)
        if not match:
            raise InvalidVersionError(
                message=f"Invalid semantic version: {text}",
                raw_text=text,
            )

        major_str, minor_str, patch_str, prerelease_str, build_str = match.groups()
        prerelease = tuple(prerelease_str.split(".")) if prerelease_str else ()
        build = tuple(build_str.split(".")) if build_str else ()

        return Version(
            major=int(major_str),
            minor=int(minor_str),
            patch=int(patch_str),
            prerelease=prerelease,
            build=build,
        )

    @override
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        if v1.major != v2.major:
            return 1 if v1.major > v2.major else -1
        if v1.minor != v2.minor:
            return 1 if v1.minor > v2.minor else -1
        if v1.patch != v2.patch:
            return 1 if v1.patch > v2.patch else -1

        # Evaluate pre-release presence when numeric components are identical
        if v1.is_prerelease and not v2.is_prerelease:
            return -1
        if not v1.is_prerelease and v2.is_prerelease:
            return 1
        if not v1.is_prerelease and not v2.is_prerelease:
            return 0

        # Both versions have pre-release identifiers; compare segments
        min_len = min(len(v1.prerelease), len(v2.prerelease))
        for i in range(min_len):
            id1 = v1.prerelease[i]
            id2 = v2.prerelease[i]
            if id1 == id2:
                continue
            id1_is_num = id1.isdigit()
            id2_is_num = id2.isdigit()
            if id1_is_num and id2_is_num:
                int1 = int(id1)
                int2 = int(id2)
                return 1 if int1 > int2 else -1
            if id1_is_num and not id2_is_num:
                return -1
            if not id1_is_num and id2_is_num:
                return 1
            # Both are string identifiers
            return 1 if id1 > id2 else -1

        if len(v1.prerelease) != len(v2.prerelease):
            return 1 if len(v1.prerelease) > len(v2.prerelease) else -1

        return 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T19:30:34Z
# LAST_CHANGED: 2026-11-13T19:02:18Z
# CHANGE: Implement VersionEngine with SemVer 2.0 regex parsing and precedence comparison
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T19:30:34Z
# PRETENSE_QA_AUDIT: 2026-11-13T19:30:00Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Interface specification for version range parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
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
# LAST_CLEANED: 2026-11-13T19:02:54Z
# LAST_CHANGED: 2026-11-13T19:02:54Z
# CHANGE: Implement VersionRange interface, InvalidRangeError, and RangeEngine protocol
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Implementation of version range parsing and matching engine."""

from __future__ import annotations

import itertools
import re
from typing import Any, List, Optional, Sequence, Tuple
from support.lib.framework import override, unreachable
from support.lib.lifecycle import get_singleton, singleton
from . import semver_core
from . import semver_range
from .semver_core import InvalidVersionError, Version
from .semver_range import InvalidRangeError, VersionRange


SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

OP_TWO = ("==", "!=", "<=", ">=")
OP_ONE = ("<", ">", "=", "^", "~")
ALL_OPS = set(OP_TWO + OP_ONE)


class _Wildcard:
    """Represents a wildcard version pattern (*, x, X)."""

    def __init__(self, kind: str, major: Optional[int] = None, minor: Optional[int] = None) -> None:
        self.kind = kind  # 'all', 'major', 'minor'
        self.major = major
        self.minor = minor


class _AtomicComparator:
    """Atomic relational comparator against a concrete Version."""

    def __init__(self, op: str, target: Version) -> None:
        self.op = op
        self.target = target


class _DNFClause:
    """Conjunction of atomic comparators forming a single clause."""

    def __init__(self, comparators: List[_AtomicComparator]) -> None:
        self.comparators = comparators
        self.prerelease_targets = {
            (c.target.major, c.target.minor, c.target.patch)
            for c in comparators
            if c.target.is_prerelease
        }


@singleton
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = "system"

    def __init__(self) -> None:
        self._version_engine: Optional[semver_core.VersionEngine] = None

    def _get_version_engine(self) -> semver_core.VersionEngine:
        if self._version_engine is None:
            self._version_engine = get_singleton(semver_core.VersionEngine)
        return self._version_engine

    def _parse_target(self, target_str: str, raw_range: str) -> Version | _Wildcard:
        """Parses a target string into a concrete Version or _Wildcard record."""
        # Check wildcard forms
        if target_str in ("*", "x", "X"):
            return _Wildcard(kind="all")

        # Check major wildcard (e.g. 1.*, 1.x)
        if (target_str.endswith(".*") or target_str.endswith(".x") or target_str.endswith(".X")) and target_str.count(".") == 1:
            major_part = target_str[:-2]
            if not major_part.isdigit() or (len(major_part) > 1 and major_part.startswith("0")):
                raise InvalidRangeError(
                    message=f"Invalid major version in wildcard: {target_str}",
                    raw_range=raw_range,
                )
            return _Wildcard(kind="major", major=int(major_part))

        # Check minor wildcard (e.g. 1.2.*, 1.2.x)
        if (target_str.endswith(".*") or target_str.endswith(".x") or target_str.endswith(".X")) and target_str.count(".") == 2:
            parts = target_str.split(".")
            major_part, minor_part = parts[0], parts[1]
            if not major_part.isdigit() or (len(major_part) > 1 and major_part.startswith("0")):
                raise InvalidRangeError(
                    message=f"Invalid major version in wildcard: {target_str}",
                    raw_range=raw_range,
                )
            if not minor_part.isdigit() or (len(minor_part) > 1 and minor_part.startswith("0")):
                raise InvalidRangeError(
                    message=f"Invalid minor version in wildcard: {target_str}",
                    raw_range=raw_range,
                )
            return _Wildcard(kind="minor", major=int(major_part), minor=int(minor_part))

        # Check for bare partial versions without wildcards
        # Bare partials like '1', '1.2', '0.0' have fewer than 3 dot components
        dot_count = target_str.count(".")
        if dot_count < 2:
            raise InvalidRangeError(
                message=f"Bare partial version lacking wildcards is prohibited: {target_str}",
                raw_range=raw_range,
            )

        # Full version match
        match = SEMVER_REGEX.match(target_str)
        if not match:
            raise InvalidRangeError(
                message=f"Malformed semantic version in range: {target_str}",
                raw_range=raw_range,
            )

        major_str, minor_str, patch_str, prerelease_str, build_str = match.groups()
        prerelease = tuple(prerelease_str.split(".")) if prerelease_str else ()
        build = tuple(build_str.split(".")) if build_str else ()
        return Version(
            major=int(major_str),
            minor=int(minor_str),
            patch=int(patch_str),
            prerelease=prerelease,
            build=build,
        )

    def _expand_comparator(
        self,
        op: str,
        target: Version | _Wildcard,
    ) -> List[List[_AtomicComparator]]:
        """Expands a single operator and target into alternative lists of atomic comparators."""
        if isinstance(target, Version):
            if op in ("==", "="):
                return [[_AtomicComparator("==", target)]]
            if op == "!=":
                return [[_AtomicComparator("!=", target)]]
            if op == "<":
                return [[_AtomicComparator("<", target)]]
            if op == "<=":
                return [[_AtomicComparator("<=", target)]]
            if op == ">":
                return [[_AtomicComparator(">", target)]]
            if op == ">=":
                return [[_AtomicComparator(">=", target)]]
            if op == "^":
                # Caret range on full version
                lower = _AtomicComparator(">=", target)
                if target.major > 0:
                    upper = _AtomicComparator("<", Version(target.major + 1, 0, 0))
                elif target.minor > 0:
                    upper = _AtomicComparator("<", Version(0, target.minor + 1, 0))
                else:
                    upper = _AtomicComparator("<", Version(0, 0, target.patch + 1))
                return [[lower, upper]]
            if op == "~":
                # Tilde range on full version
                lower = _AtomicComparator(">=", target)
                upper = _AtomicComparator("<", Version(target.major, target.minor + 1, 0))
                return [[lower, upper]]
            # Bare version without operator
            return [[_AtomicComparator("==", target)]]

        # Target is a wildcard
        if target.kind == "all":
            if op in ("", "==", "=", ">=", "<=", "~", "^"):
                return [[_AtomicComparator(">=", Version(0, 0, 0))]]
            # < *, > *, != * are unsatisfiable
            return []

        if target.kind == "major":
            assert target.major is not None
            m = target.major
            if op in ("", "==", "="):
                return [[_AtomicComparator(">=", Version(m, 0, 0)), _AtomicComparator("<", Version(m + 1, 0, 0))]]
            if op == "!=":
                # Disjunctive split: < m.0.0 || >= (m+1).0.0
                return [
                    [_AtomicComparator("<", Version(m, 0, 0))],
                    [_AtomicComparator(">=", Version(m + 1, 0, 0))],
                ]
            if op == ">=":
                return [[_AtomicComparator(">=", Version(m, 0, 0))]]
            if op == "<=":
                return [[_AtomicComparator("<", Version(m + 1, 0, 0))]]
            if op == ">":
                return [[_AtomicComparator(">=", Version(m + 1, 0, 0))]]
            if op == "<":
                return [[_AtomicComparator("<", Version(m, 0, 0))]]
            if op in ("~", "^"):
                return [[_AtomicComparator(">=", Version(m, 0, 0)), _AtomicComparator("<", Version(m + 1, 0, 0))]]

        if target.kind == "minor":
            assert target.major is not None and target.minor is not None
            m, n = target.major, target.minor
            if op in ("", "==", "="):
                return [[_AtomicComparator(">=", Version(m, n, 0)), _AtomicComparator("<", Version(m, n + 1, 0))]]
            if op == "!=":
                return [
                    [_AtomicComparator("<", Version(m, n, 0))],
                    [_AtomicComparator(">=", Version(m, n + 1, 0))],
                ]
            if op == ">=":
                return [[_AtomicComparator(">=", Version(m, n, 0))]]
            if op == "<=":
                return [[_AtomicComparator("<", Version(m, n + 1, 0))]]
            if op == ">":
                return [[_AtomicComparator(">=", Version(m, n + 1, 0))]]
            if op == "<":
                return [[_AtomicComparator("<", Version(m, n, 0))]]
            if op == "~":
                return [[_AtomicComparator(">=", Version(m, n, 0)), _AtomicComparator("<", Version(m, n + 1, 0))]]
            if op == "^":
                lower = _AtomicComparator(">=", Version(m, n, 0))
                if m > 0:
                    upper = _AtomicComparator("<", Version(m + 1, 0, 0))
                elif n > 0:
                    upper = _AtomicComparator("<", Version(0, n + 1, 0))
                else:
                    upper = _AtomicComparator("<", Version(0, 1, 0))
                return [[lower, upper]]

        with unreachable:
            return []

    def _expand_hyphen(
        self,
        b1: Version | _Wildcard,
        b2: Version | _Wildcard,
    ) -> List[_AtomicComparator]:
        """Expands a hyphen range bound1 - bound2 into atomic comparators."""
        comps: List[_AtomicComparator] = []
        if isinstance(b1, Version):
            comps.append(_AtomicComparator(">=", b1))
        elif b1.kind == "all":
            comps.append(_AtomicComparator(">=", Version(0, 0, 0)))
        elif b1.kind == "major":
            assert b1.major is not None
            comps.append(_AtomicComparator(">=", Version(b1.major, 0, 0)))
        elif b1.kind == "minor":
            assert b1.major is not None and b1.minor is not None
            comps.append(_AtomicComparator(">=", Version(b1.major, b1.minor, 0)))

        if isinstance(b2, Version):
            comps.append(_AtomicComparator("<=", b2))
        elif b2.kind == "major":
            assert b2.major is not None
            comps.append(_AtomicComparator("<", Version(b2.major + 1, 0, 0)))
        elif b2.kind == "minor":
            assert b2.major is not None and b2.minor is not None
            comps.append(_AtomicComparator("<", Version(b2.major, b2.minor + 1, 0)))
        # b2.kind == 'all' leaves upper bound unconstrained

        return comps

    def _compile_clause(self, clause_text: str, raw_range: str) -> List[_DNFClause]:
        """Compiles a single clause into a disjunction of DNF clauses."""
        tokens = clause_text.split()
        if not tokens:
            with unreachable:
                raise InvalidRangeError(message="Empty clause in range expression", raw_range=raw_range)

        # Parse tokens into items (comparators and hyphen ranges)
        items_branches: List[List[List[_AtomicComparator]]] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Check if standalone operator
            if token in ALL_OPS:
                if i + 1 >= len(tokens):
                    raise InvalidRangeError(
                        message=f"Operator '{token}' missing target version",
                        raw_range=raw_range,
                    )
                next_token = tokens[i + 1]
                if next_token in ALL_OPS or next_token == "-":
                    raise InvalidRangeError(
                        message=f"Operator '{token}' followed by operator '{next_token}'",
                        raw_range=raw_range,
                    )
                target = self._parse_target(next_token, raw_range)
                branches = self._expand_comparator(token, target)
                items_branches.append(branches)
                i += 2
                continue

            # Check hyphen range
            if i + 2 < len(tokens) and tokens[i + 1] == "-":
                b1 = self._parse_target(token, raw_range)
                b2 = self._parse_target(tokens[i + 2], raw_range)
                hyphen_comps = self._expand_hyphen(b1, b2)
                items_branches.append([[c for c in hyphen_comps]])
                i += 3
                continue

            if token == "-":
                raise InvalidRangeError(
                    message="Malformed hyphen range missing lower bound",
                    raw_range=raw_range,
                )

            # Check if token starts with 2-char operator
            op_matched: Optional[str] = None
            target_str: Optional[str] = None
            for op in OP_TWO:
                if token.startswith(op):
                    op_matched = op
                    target_str = token[len(op):]
                    break

            if op_matched is None:
                for op in OP_ONE:
                    if token.startswith(op):
                        op_matched = op
                        target_str = token[len(op):]
                        break

            if op_matched is not None:
                assert target_str is not None
                if not target_str:
                    with unreachable:
                        raise InvalidRangeError(
                            message=f"Operator '{op_matched}' missing target version",
                            raw_range=raw_range,
                        )
                target = self._parse_target(target_str, raw_range)
                branches = self._expand_comparator(op_matched, target)
                items_branches.append(branches)
                i += 1
                continue

            # Bare version or wildcard
            target = self._parse_target(token, raw_range)
            branches = self._expand_comparator("", target)
            items_branches.append(branches)
            i += 1

        # Product across items to form DNF clauses
        clause_results: List[_DNFClause] = []
        for combination in itertools.product(*items_branches):
            flat_comps: List[_AtomicComparator] = []
            for comp_list in combination:
                flat_comps.extend(comp_list)
            clause_results.append(_DNFClause(flat_comps))

        return clause_results

    def _compile_range(self, range_text: str) -> List[_DNFClause]:
        """Compiles a full range expression into a list of DNF clauses."""
        if not range_text or not range_text.strip():
            raise InvalidRangeError(message="Range text is empty", raw_range=range_text)

        if "," in range_text:
            raise InvalidRangeError(
                message="Commas are prohibited in range expressions",
                raw_range=range_text,
            )

        clauses_raw = range_text.split("||")
        all_clauses: List[_DNFClause] = []
        for c_raw in clauses_raw:
            trimmed = c_raw.strip()
            if not trimmed:
                raise InvalidRangeError(
                    message="Empty clause in range expression",
                    raw_range=range_text,
                )
            dnf_clauses = self._compile_clause(trimmed, range_text)
            all_clauses.extend(dnf_clauses)

        return all_clauses

    @override
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # Compile range to validate syntax and produce trimmed canonical text
        self._compile_range(text)
        cleaned_clauses = [c.strip() for c in text.split("||")]
        trimmed_text = " || ".join(cleaned_clauses)
        return VersionRange(raw_text=trimmed_text)

    @override
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        version_engine = self._get_version_engine()
        dnf_clauses = self._compile_range(range_constraint.raw_text)

        for clause in dnf_clauses:
            # When candidate version is a prerelease and include_prerelease is False,
            # reject unless the clause explicitly specifies a prerelease on the same major, minor, patch
            if version.is_prerelease and not include_prerelease:
                key = (version.major, version.minor, version.patch)
                if key not in clause.prerelease_targets:
                    continue

            # Evaluate each atomic comparator in the clause
            clause_satisfied = True
            for comp in clause.comparators:
                cmp = version_engine.compare_precedence(version, comp.target)
                if comp.op in ("==", "="):
                    if cmp != 0:
                        clause_satisfied = False
                        break
                elif comp.op == "!=":
                    if cmp == 0:
                        clause_satisfied = False
                        break
                elif comp.op == "<":
                    if cmp >= 0:
                        clause_satisfied = False
                        break
                elif comp.op == "<=":
                    if cmp > 0:
                        clause_satisfied = False
                        break
                elif comp.op == ">":
                    if cmp <= 0:
                        clause_satisfied = False
                        break
                elif comp.op == ">=":
                    if cmp < 0:
                        clause_satisfied = False
                        break

            if clause_satisfied:
                return True

        return False

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T19:49:38Z
# LAST_CHANGED: 2026-11-13T19:48:34Z
# CHANGE: Quarantine unreachable defensive clauses under parser contract closure using with unreachable
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T19:49:38Z
# PRETENSE_QA_AUDIT: 2026-11-13T19:49:12Z
# --- END AUTOFAB METADATA ---
