# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_215959_gemini-carbon_semver_solver_multi_pretense
# Timestamp: 2026-11-13T21:59:59.050580+00:00
# Benchmark Task: semver_solver_multi
# Model: gemini-carbon (Tier 4)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 1,221,073
#   Cached Inbound Tokens:   24,064,996
#   Outbound Tokens:         148,338
#   Total Tokens:            25,434,407
#   Financial Cost ($USD):   $6.3320
#   Wall Clock Duration:     2868.61s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 3, pretense: 6, pretense_coverage: 9, pretense_qa: 14 (Total: 32)
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
"""Interface definitions for package repository and dependency resolution."""

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
# LAST_CLEANED: 2026-11-13T22:06:26Z
# LAST_CHANGED: 2026-11-13T22:06:26Z
# CHANGE: Implement dependency solver and package repository interfaces, errors, and data types
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Concrete implementation for package repository and dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
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
        releases.append(release)
        # Sort releases in descending version precedence order.
        releases.sort(
            key=cmp_to_key(
                lambda r1, r2: version_engine.compare_precedence(r1.version, r2.version)
            ),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository.",
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
        """Provides the set of all registered package names."""
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
        repository = get_singleton(dependency_solver.PackageRepository)
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

        def _satisfies_constraint(
            version: semver_core.Version,
            constraint: semver_range.VersionRange,
        ) -> bool:
            return range_engine.satisfies(
                version=version,
                range_constraint=constraint,
                include_prerelease=False,
            )

        def _available_releases(pkg_name: str) -> List[dependency_solver.PackageRelease]:
            # Treat unregistered packages as having zero candidate releases without letting PackageNotFoundError escape.
            try:
                return repository.get_releases(pkg_name)
            except dependency_solver.PackageNotFoundError:
                return []

        def _backtrack() -> bool:
            unassigned = [pkg for pkg in accumulated_constraints if pkg not in assignment]
            if not unassigned:
                return True

            # Evaluate viable candidate releases for all unassigned packages under accumulated constraints.
            candidates_map: Dict[str, List[dependency_solver.PackageRelease]] = {}
            for pkg in unassigned:
                available = _available_releases(pkg)
                viable = [
                    rel
                    for rel in available
                    if all(
                        _satisfies_constraint(rel.version, rng)
                        for _, rng in accumulated_constraints[pkg]
                    )
                ]
                candidates_map[pkg] = viable

            # Select unassigned package with fewest candidate releases (MRV), breaking ties lexically.
            selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
                conflicting_packages.add(selected_pkg)
                for req in requesters:
                    if req != "root":
                        conflicting_packages.add(req)
                constraints_desc = ", ".join(
                    f"{src} ({rng.raw_text})" for src, rng in accumulated_constraints[selected_pkg]
                )
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints: {constraints_desc}."
                )
                return False

            # Explore candidate releases in descending version precedence order.
            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(
                    f"Select '{selected_pkg}' version {candidate.version} satisfying "
                    + ", ".join(
                        f"{src} ({rng.raw_text})"
                        for src, rng in accumulated_constraints[selected_pkg]
                    )
                )

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        assigned_rel = assignment[dep.name]
                        if not _satisfies_constraint(
                            assigned_rel.version, dep.range_constraint
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected_pkg)
                            conflicting_packages.add(dep.name)
                            conflict_trail.append(
                                f"Conflict: '{selected_pkg}' {candidate.version} requires "
                                f"'{dep.name}' {dep.range_constraint.raw_text}, "
                                f"but '{dep.name}' is already assigned {assigned_rel.version}."
                            )
                            break
                    else:
                        constraint_entry = (selected_pkg, dep.range_constraint)
                        accumulated_constraints.setdefault(dep.name, []).append(
                            constraint_entry
                        )
                        newly_added.append((dep.name, constraint_entry))

                if not conflict_detected and _backtrack():
                    return True

                # Undo newly added constraints and assignment upon conflict before trying next candidate.
                for pkg_name, constraint_entry in newly_added:
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        if _backtrack():
            selected_versions: Dict[str, semver_core.Version] = {
                pkg: rel.version for pkg, rel in sorted(assignment.items())
            }
            return dependency_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        explanation = "\n".join(conflict_trail)
        sorted_conflicts = tuple(sorted(conflicting_packages))
        raise dependency_solver.ResolutionConflictError(
            message=f"Dependency resolution failed due to conflicts involving: {', '.join(sorted_conflicts)}.",
            conflicting_packages=sorted_conflicts,
            explanation=explanation,
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:40:56Z
# LAST_CHANGED: 2026-11-13T22:16:28Z
# CHANGE: Retain all registered package releases in register_package without filtering duplicate versions
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:40:56Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:40:16Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""Interface definitions for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Protocol, Tuple

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
            base += "-" + ".".join(self.prerelease)
        if self.build:
            base += "+" + ".".join(self.build)
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
# LAST_CLEANED: 2026-11-13T22:06:18Z
# LAST_CHANGED: 2026-11-13T22:06:18Z
# CHANGE: Implement SemVer 2.0 core interface, error types, comparator enum, and Version data type
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Concrete implementation for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

import re
from typing import Tuple

from support.lib.framework import operation, override
from support.lib.lifecycle import singleton
from . import semver_core


_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
)


@singleton
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = "system"

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Reject non-ASCII or malformed syntax against strict SemVer 2.0.0 regular expression.
        match = _SEMVER_RE.match(text)
        if not match or not text.isascii():
            raise semver_core.InvalidVersionError(
                message=f"Invalid semantic version string: '{text}'",
                raw_text=text,
            )

        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))

        prerelease_str = match.group(4)
        prerelease: Tuple[str, ...] = tuple(prerelease_str.split(".")) if prerelease_str else ()

        build_str = match.group(5)
        build: Tuple[str, ...] = tuple(build_str.split(".")) if build_str else ()

        return semver_core.Version(
            major=major,
            minor=minor,
            patch=patch,
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
        # Compare major, minor, and patch numbers numerically in order.
        if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
            return -1 if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch) else 1

        # Handle pre-release presence: normal versions rank higher than pre-release versions.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease and v2.prerelease:
            return 1
        if v1.prerelease and not v2.prerelease:
            return -1

        # Compare pre-release identifiers segment by segment, ignoring build metadata.
        for seg1, seg2 in zip(v1.prerelease, v2.prerelease):
            if seg1 == seg2:
                continue
            num1 = seg1.isdigit() and seg1.isascii()
            num2 = seg2.isdigit() and seg2.isascii()
            if num1 and num2:
                return -1 if int(seg1) < int(seg2) else 1
            if num1 and not num2:
                # Numeric identifiers always have lower precedence than non-numeric identifiers.
                return -1
            if not num1 and num2:
                return 1
            # Both identifiers are non-numeric; compare lexically in ASCII sort order.
            return -1 if seg1 < seg2 else 1

        # A larger set of pre-release fields has higher precedence if all preceding identifiers match.
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

        return 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:28:01Z
# LAST_CHANGED: 2026-11-13T22:06:30Z
# CHANGE: Implement VersionEngine singleton with SemVer 2.0 parsing and precedence comparison
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:28:01Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:27:00Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Interface definitions for version range parsing and matching."""

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
# LAST_CLEANED: 2026-11-13T22:06:22Z
# LAST_CHANGED: 2026-11-13T22:06:22Z
# CHANGE: Implement version range interface, InvalidRangeError, and VersionRange data type
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Concrete implementation for version range parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional, Tuple

from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton
from . import semver_core
from . import semver_range


_WILDCARD_TOKENS = {"*", "x", "X"}
_OPERATOR_PREFIX_RE = re.compile(r"^(==|!=|<=|>=|<|>|=|\^|~)\s*(.*)$")
_NUMERIC_ID_RE = re.compile(r"^(0|[1-9]\d*)\Z")


@dataclass(frozen=True)
class _ParsedTarget:
    major: Optional[int]
    minor: Optional[int]
    patch: Optional[int]
    is_wildcard: bool
    version: Optional[semver_core.Version]


@dataclass(frozen=True)
class _AtomicComparator:
    op: semver_core.ComparatorOp
    bound: semver_core.Version
    match_all: bool = False
    match_none: bool = False


def _parse_version_or_wildcard(
    token: str,
    raw_range: str,
    version_engine: semver_core.VersionEngine,
) -> _ParsedTarget:
    """Parses a single version or wildcard target, rejecting bare partial versions."""
    if token in _WILDCARD_TOKENS:
        return _ParsedTarget(
            major=None,
            minor=None,
            patch=None,
            is_wildcard=True,
            version=None,
        )

    # Check if token contains wildcard segments; wildcards cannot carry prerelease or build suffixes.
    parts = token.split(".")
    has_wildcard = any(p in _WILDCARD_TOKENS for p in parts)
    if has_wildcard:
        if len(parts) not in (2, 3):
            raise semver_range.InvalidRangeError(
                message=f"Invalid wildcard version '{token}' in range '{raw_range}'.",
                raw_range=raw_range,
            )
        if parts[0] in _WILDCARD_TOKENS:
            if not all(p in _WILDCARD_TOKENS for p in parts):
                raise semver_range.InvalidRangeError(
                    message=f"Numeric segment cannot follow wildcard in '{token}'.",
                    raw_range=raw_range,
                )
            return _ParsedTarget(
                major=None,
                minor=None,
                patch=None,
                is_wildcard=True,
                version=None,
            )

        if not _NUMERIC_ID_RE.match(parts[0]) or not parts[0].isascii():
            raise semver_range.InvalidRangeError(
                message=f"Invalid major version in wildcard '{token}'.",
                raw_range=raw_range,
            )
        major = int(parts[0])

        if parts[1] in _WILDCARD_TOKENS:
            if len(parts) == 3 and parts[2] not in _WILDCARD_TOKENS:
                raise semver_range.InvalidRangeError(
                    message=f"Numeric patch cannot follow wildcard minor in '{token}'.",
                    raw_range=raw_range,
                )
            return _ParsedTarget(
                major=major,
                minor=None,
                patch=None,
                is_wildcard=True,
                version=None,
            )

        # Here len(parts) == 3 and parts[2] is a wildcard, so parts[1] must be a valid numeric segment.
        if not _NUMERIC_ID_RE.match(parts[1]) or not parts[1].isascii():
            raise semver_range.InvalidRangeError(
                message=f"Malformed wildcard target '{token}' in range '{raw_range}'.",
                raw_range=raw_range,
            )
        minor = int(parts[1])
        return _ParsedTarget(
            major=major,
            minor=minor,
            patch=None,
            is_wildcard=True,
            version=None,
        )

    # Full semantic version required (bare partials without wildcards are rejected by parse_version).
    try:
        parsed_ver = version_engine.parse_version(token)
    except semver_core.InvalidVersionError as exc:
        raise semver_range.InvalidRangeError(
            message=f"Invalid version '{token}' in range '{raw_range}': {exc.message}",
            raw_range=raw_range,
        ) from exc

    return _ParsedTarget(
        major=parsed_ver.major,
        minor=parsed_ver.minor,
        patch=parsed_ver.patch,
        is_wildcard=False,
        version=parsed_ver,
    )


def _wildcard_bounds(
    target: _ParsedTarget,
) -> Tuple[Optional[semver_core.Version], Optional[semver_core.Version]]:
    """Computes inclusive lower bound and exclusive upper bound for a wildcard target."""
    if target.major is None:
        return None, None
    if target.minor is None:
        return (
            semver_core.Version(target.major, 0, 0),
            semver_core.Version(target.major + 1, 0, 0),
        )
    return (
        semver_core.Version(target.major, target.minor, 0),
        semver_core.Version(target.major, target.minor + 1, 0),
    )


def _expand_hyphen(
    left: _ParsedTarget,
    right: _ParsedTarget,
) -> List[List[_AtomicComparator]]:
    """Expands a hyphen range 'left - right' into disjunctive comparator clauses."""
    conjunction: List[_AtomicComparator] = []

    if left.is_wildcard:
        low, _ = _wildcard_bounds(left)
        if low is not None:
            conjunction.append(_AtomicComparator(semver_core.ComparatorOp.GE, low))
        else:
            conjunction.append(
                _AtomicComparator(
                    semver_core.ComparatorOp.GE,
                    semver_core.Version(0, 0, 0),
                    match_all=True,
                )
            )
    else:
        assert left.version is not None
        conjunction.append(_AtomicComparator(semver_core.ComparatorOp.GE, left.version))

    if right.is_wildcard:
        _, high = _wildcard_bounds(right)
        if high is not None:
            conjunction.append(_AtomicComparator(semver_core.ComparatorOp.LT, high))
        else:
            conjunction.append(
                _AtomicComparator(
                    semver_core.ComparatorOp.GE,
                    semver_core.Version(0, 0, 0),
                    match_all=True,
                )
            )
    else:
        assert right.version is not None
        conjunction.append(_AtomicComparator(semver_core.ComparatorOp.LE, right.version))

    return [conjunction]


def _expand_prefixed_item(
    op_str: str,
    target: _ParsedTarget,
) -> List[List[_AtomicComparator]]:
    """Expands a single operator + target into DNF alternatives (list of conjunctions)."""
    all_cmp = _AtomicComparator(
        semver_core.ComparatorOp.GE,
        semver_core.Version(0, 0, 0),
        match_all=True,
    )
    none_cmp = _AtomicComparator(
        semver_core.ComparatorOp.EQ,
        semver_core.Version(0, 0, 0),
        match_none=True,
    )

    if op_str == "^":
        if target.is_wildcard:
            if target.major is None:
                return [[all_cmp]]
            if target.minor is None:
                # ^M.x -> >=M.0.0 <(M+1).0.0
                return [[
                    _AtomicComparator(semver_core.ComparatorOp.GE, semver_core.Version(target.major, 0, 0)),
                    _AtomicComparator(semver_core.ComparatorOp.LT, semver_core.Version(target.major + 1, 0, 0)),
                ]]
            # ^M.m.x
            lower = semver_core.Version(target.major, target.minor, 0)
            if target.major > 0:
                upper = semver_core.Version(target.major + 1, 0, 0)
            else:
                upper = semver_core.Version(0, target.minor + 1, 0)
            return [[
                _AtomicComparator(semver_core.ComparatorOp.GE, lower),
                _AtomicComparator(semver_core.ComparatorOp.LT, upper),
            ]]

        assert target.version is not None
        ver = target.version
        if ver.major > 0:
            upper = semver_core.Version(ver.major + 1, 0, 0)
        elif ver.minor > 0:
            upper = semver_core.Version(0, ver.minor + 1, 0)
        else:
            upper = semver_core.Version(0, 0, ver.patch + 1)
        return [[
            _AtomicComparator(semver_core.ComparatorOp.GE, ver),
            _AtomicComparator(semver_core.ComparatorOp.LT, upper),
        ]]

    if op_str == "~":
        if target.is_wildcard:
            if target.major is None:
                return [[all_cmp]]
            if target.minor is None:
                # ~M.x -> >=M.0.0 <(M+1).0.0
                return [[
                    _AtomicComparator(semver_core.ComparatorOp.GE, semver_core.Version(target.major, 0, 0)),
                    _AtomicComparator(semver_core.ComparatorOp.LT, semver_core.Version(target.major + 1, 0, 0)),
                ]]
            # ~M.m.x -> >=M.m.0 <M.(m+1).0
            return [[
                _AtomicComparator(semver_core.ComparatorOp.GE, semver_core.Version(target.major, target.minor, 0)),
                _AtomicComparator(semver_core.ComparatorOp.LT, semver_core.Version(target.major, target.minor + 1, 0)),
            ]]

        assert target.version is not None
        ver = target.version
        return [[
            _AtomicComparator(semver_core.ComparatorOp.GE, ver),
            _AtomicComparator(semver_core.ComparatorOp.LT, semver_core.Version(ver.major, ver.minor + 1, 0)),
        ]]

    # Relational operators: "", "=", "==", "!=", "<", "<=", ">", ">="
    normalized_op = "==" if op_str in ("", "=") else op_str

    if not target.is_wildcard:
        assert target.version is not None
        op_enum = semver_core.ComparatorOp(normalized_op)
        return [[_AtomicComparator(op_enum, target.version)]]

    low, high = _wildcard_bounds(target)
    if normalized_op == "==":
        if low is None and high is None:
            return [[all_cmp]]
        assert low is not None and high is not None
        return [[
            _AtomicComparator(semver_core.ComparatorOp.GE, low),
            _AtomicComparator(semver_core.ComparatorOp.LT, high),
        ]]

    if normalized_op == "!=":
        if low is None and high is None:
            return [[none_cmp]]
        assert low is not None and high is not None
        return [
            [_AtomicComparator(semver_core.ComparatorOp.LT, low)],
            [_AtomicComparator(semver_core.ComparatorOp.GE, high)],
        ]

    if normalized_op == ">=":
        if low is None:
            return [[all_cmp]]
        return [[_AtomicComparator(semver_core.ComparatorOp.GE, low)]]

    if normalized_op == ">":
        if high is None:
            return [[none_cmp]]
        return [[_AtomicComparator(semver_core.ComparatorOp.GE, high)]]

    if normalized_op == "<=":
        if high is None:
            return [[all_cmp]]
        return [[_AtomicComparator(semver_core.ComparatorOp.LT, high)]]

    # normalized_op == "<"
    if low is None:
        return [[none_cmp]]
    return [[_AtomicComparator(semver_core.ComparatorOp.LT, low)]]


def _compile_clause(
    clause_text: str,
    raw_range: str,
    version_engine: semver_core.VersionEngine,
) -> List[List[_AtomicComparator]]:
    """Tokenizes and compiles a single whitespace-delimited intersection clause into DNF."""
    raw_tokens = clause_text.split()
    # Merge standalone operator tokens with the subsequent token so optional operator whitespace is supported.
    merged_tokens: List[str] = []
    idx = 0
    standalone_ops = {"==", "!=", "<=", ">=", "<", ">", "=", "^", "~"}
    while idx < len(raw_tokens):
        tok = raw_tokens[idx]
        if tok in standalone_ops:
            if idx + 1 >= len(raw_tokens) or raw_tokens[idx + 1] == "-":
                raise semver_range.InvalidRangeError(
                    message=f"Dangling operator '{tok}' in range '{raw_range}'.",
                    raw_range=raw_range,
                )
            merged_tokens.append(tok + raw_tokens[idx + 1])
            idx += 2
        else:
            merged_tokens.append(tok)
            idx += 1

    # Group hyphen ranges 'bound1 - bound2' and standalone comparator items.
    dnf_clauses: List[List[_AtomicComparator]] = [[]]
    pos = 0
    while pos < len(merged_tokens):
        if pos + 1 < len(merged_tokens) and merged_tokens[pos + 1] == "-":
            if pos + 2 >= len(merged_tokens):
                raise semver_range.InvalidRangeError(
                    message=f"Incomplete hyphen range in '{raw_range}'.",
                    raw_range=raw_range,
                )
            left_tok = merged_tokens[pos]
            right_tok = merged_tokens[pos + 2]
            # Hyphen bounds cannot carry relational or prefix operators, and chained hyphens are malformed.
            if (
                _OPERATOR_PREFIX_RE.match(left_tok)
                or _OPERATOR_PREFIX_RE.match(right_tok)
                or (pos + 3 < len(merged_tokens) and merged_tokens[pos + 3] == "-")
            ):
                raise semver_range.InvalidRangeError(
                    message=f"Malformed hyphen range in '{raw_range}'.",
                    raw_range=raw_range,
                )
            left_target = _parse_version_or_wildcard(left_tok, raw_range, version_engine)
            right_target = _parse_version_or_wildcard(right_tok, raw_range, version_engine)
            item_alternatives = _expand_hyphen(left_target, right_target)
            pos += 3
        else:
            tok = merged_tokens[pos]
            if tok == "-":
                raise semver_range.InvalidRangeError(
                    message=f"Unexpected hyphen token in range '{raw_range}'.",
                    raw_range=raw_range,
                )
            op_match = _OPERATOR_PREFIX_RE.match(tok)
            if op_match:
                op_str = op_match.group(1)
                rest = op_match.group(2)
                target = _parse_version_or_wildcard(rest, raw_range, version_engine)
                item_alternatives = _expand_prefixed_item(op_str, target)
            else:
                target = _parse_version_or_wildcard(tok, raw_range, version_engine)
                item_alternatives = _expand_prefixed_item("", target)
            pos += 1

        # Cross-product current DNF conjunctions with new item alternatives.
        next_dnf: List[List[_AtomicComparator]] = []
        for existing in dnf_clauses:
            for alt in item_alternatives:
                next_dnf.append(existing + alt)
        dnf_clauses = next_dnf

    return dnf_clauses


def _compile_range(
    raw_text: str,
    version_engine: semver_core.VersionEngine,
) -> List[List[_AtomicComparator]]:
    """Validates and compiles a complete range expression into DNF comparator sets."""
    trimmed = raw_text.strip()
    if not trimmed:
        raise semver_range.InvalidRangeError(
            message="Version range cannot be empty or whitespace.",
            raw_range=raw_text,
        )
    if "," in trimmed:
        raise semver_range.InvalidRangeError(
            message=f"Comma delimiters are prohibited in version range '{raw_text}'.",
            raw_range=raw_text,
        )

    union_parts = trimmed.split("||")
    # Also reject stray single '|' characters inside clauses.
    all_conjunctions: List[List[_AtomicComparator]] = []
    for raw_clause in union_parts:
        clause = raw_clause.strip()
        if not clause or "|" in clause:
            raise semver_range.InvalidRangeError(
                message=f"Malformed union clause in range '{raw_text}'.",
                raw_range=raw_text,
            )
        all_conjunctions.extend(_compile_clause(clause, raw_text, version_engine))

    return all_conjunctions


def _evaluate_comparator(
    version: semver_core.Version,
    cmp: _AtomicComparator,
    version_engine: semver_core.VersionEngine,
) -> bool:
    """Evaluates a single atomic comparator against a candidate version using precedence rules."""
    if cmp.match_none:
        return False
    if cmp.match_all:
        return True

    diff = version_engine.compare_precedence(version, cmp.bound)
    if cmp.op == semver_core.ComparatorOp.EQ:
        return diff == 0
    if cmp.op == semver_core.ComparatorOp.NE:
        return diff != 0
    if cmp.op == semver_core.ComparatorOp.LT:
        return diff < 0
    if cmp.op == semver_core.ComparatorOp.LE:
        return diff <= 0
    if cmp.op == semver_core.ComparatorOp.GT:
        return diff > 0
    return diff >= 0


@singleton
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = "system"

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        version_engine = get_singleton(semver_core.VersionEngine)
        # Validate full range syntax and expand comparators; raises InvalidRangeError on malformed syntax.
        _compile_range(text, version_engine)
        return semver_range.VersionRange(raw_text=text.strip())

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
        conjunctions = _compile_range(range_constraint.raw_text, version_engine)

        for clause in conjunctions:
            if not all(_evaluate_comparator(version, cmp, version_engine) for cmp in clause):
                continue

            # When candidate is a pre-release and include_prerelease is False, require at least one
            # comparator in the matching clause to explicitly specify a pre-release on the same major.minor.patch.
            if version.is_prerelease and not include_prerelease:
                explicit_prerelease_target = any(
                    not cmp.match_all
                    and not cmp.match_none
                    and cmp.bound.is_prerelease
                    and (cmp.bound.major, cmp.bound.minor, cmp.bound.patch)
                    == (version.major, version.minor, version.patch)
                    for cmp in clause
                )
                if not explicit_prerelease_target:
                    continue

            return True

        return False

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:47:46Z
# LAST_CHANGED: 2026-11-13T22:09:01Z
# CHANGE: Implement RangeEngine singleton for SemVer 2.0 range parsing, DNF expansion, and constraint matching
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:47:46Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:46:59Z
# --- END AUTOFAB METADATA ---
