# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261106_202003_gemini-argon_semver_solver_multi_combined_baseline
# Timestamp: 2026-11-06T20:20:03.299900+00:00
# Benchmark Task: semver_solver_multi
# Model: gemini-argon (Tier 4)
# Methodology: combined_baseline
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 952,951
#   Cached Inbound Tokens:   12,524,136
#   Outbound Tokens:         276,585
#   Total Tokens:            13,753,672
#   Financial Cost ($USD):   $10.9338
#   Wall Clock Duration:     1471.56s
#   Step Latencies (s):      []
#   Role Execution Rounds:   combined_baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       16
#   Unit Tests Failed:       0
#   Line Coverage:           99.0%
#   Branch Coverage:         99.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
"""Library interface for package repository and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, List, Mapping, Protocol, Set, Tuple
from support.lib.framework import data_type, operation, poly_type
from . import semver_core
from . import semver_range


@dataclass
class PackageNotFoundError(semver_core.SemVerError):
    """Raised when a referenced package name does not exist in the repository."""

    package_name: str = ""


@dataclass
class ResolutionConflictError(semver_core.SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually."""

    conflicting_packages: Tuple[str, ...] = ()
    explanation: str = ""


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
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b136f1b452ca
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Library implementation for package repository and dependency resolution."""

from __future__ import annotations

import functools
from typing import Collection, Dict, List, Optional, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)
from . import dependency_solver
from . import semver_core
from . import semver_range


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        version_engine = get_singleton(semver_core.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # Re-sort release list in descending version precedence order
        releases.sort(
            key=functools.cmp_to_key(
                lambda a, b: version_engine.compare_precedence(b.version, a.version)
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package {name!r} is not registered in the repository",
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


@singleton_type("system")
class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        repo = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        accumulated_constraints: Dict[
            str, List[Tuple[Optional[str], semver_range.VersionRange]]
        ] = {}
        for dep in root_dependencies:
            accumulated_constraints.setdefault(dep.name, []).append(
                (None, dep.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

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
                    rel
                    for rel in available
                    if all(
                        range_engine.satisfies(rel.version, rng, False)
                        for _, rng in accumulated_constraints[pkg]
                    )
                ]
                candidates_map[pkg] = viable

            # MRV heuristic with lexical tie-breaking
            selected_pkg = min(
                unassigned, key=lambda p: (len(candidates_map[p]), p)
            )
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [
                    src
                    for src, _ in accumulated_constraints[selected_pkg]
                    if src is not None
                ]
                conflicting_packages.add(selected_pkg)
                conflicting_packages.update(requesters)
                requester_labels = [
                    src or "root" for src, _ in accumulated_constraints[selected_pkg]
                ]
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints from {requester_labels}"
                )
                return False

            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(
                    f"Assign '{selected_pkg}' to {candidate.version}"
                )

                conflict_detected = False
                newly_added: List[
                    Tuple[str, Tuple[Optional[str], semver_range.VersionRange]]
                ] = []

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
            return dependency_solver.ResolutionOutcome(
                selected_versions={
                    pkg: rel.version for pkg, rel in assignment.items()
                },
                derivation_steps=tuple(derivation_steps),
            )

        conflict_pkgs = tuple(sorted(conflicting_packages))
        explanation = "\n".join(conflict_trail)
        raise dependency_solver.ResolutionConflictError(
            message=f"Resolution conflict for {conflict_pkgs}: {explanation}",
            conflicting_packages=conflict_pkgs,
            explanation=explanation,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        PackageRepository,
        keys=[dependency_solver.PackageRepository, PackageRepository],
        tier=system,
    )
    reg.register_singleton(
        DependencySolver,
        keys=[dependency_solver.DependencySolver, DependencySolver],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9a397c26657d
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""Library interface for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Protocol, Tuple
from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str = ""

    def __str__(self) -> str:
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered."""

    raw_text: str = ""


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
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: d03c35b3802d
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Library implementation for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

import re
from typing import Optional, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import semver_core


_SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Validate SemVer 2.0.0 grammar and numerical leading zero constraints
        match = _SEMVER_RE.fullmatch(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                message=f"Invalid semantic version syntax: {text!r}",
                raw_text=text,
            )

        major_str, minor_str, patch_str, prerelease_str, build_str = match.groups()
        prerelease: Tuple[str, ...] = ()
        if prerelease_str is not None:
            segments = tuple(prerelease_str.split("."))
            # Numeric identifiers in pre-release must not include leading zeroes
            for seg in segments:
                if seg.isascii() and seg.isdigit() and len(seg) > 1 and seg.startswith("0"):
                    raise semver_core.InvalidVersionError(
                        message=f"Pre-release numeric identifier has leading zero in {text!r}",
                        raw_text=text,
                    )
            prerelease = segments

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
        # Compare major, minor, and patch numbers numerically in sequence
        core1 = (v1.major, v1.minor, v1.patch)
        core2 = (v2.major, v2.minor, v2.patch)
        if core1 < core2:
            return -1
        if core1 > core2:
            return 1

        # Evaluate pre-release presence when numeric components are identical
        pre1 = v1.prerelease
        pre2 = v2.prerelease
        if not pre1 and not pre2:
            return 0
        # Normal version ranks higher than pre-release version
        if not pre1:
            return 1
        if not pre2:
            return -1

        # Iterate through pre-release segments comparing each position
        for seg1, seg2 in zip(pre1, pre2):
            if seg1 == seg2:
                continue
            num1 = seg1.isascii() and seg1.isdigit()
            num2 = seg2.isascii() and seg2.isdigit()
            if num1 and num2:
                # Compare numeric segments as integers
                n1, n2 = int(seg1), int(seg2)
                return -1 if n1 < n2 else 1
            if num1:
                # Numeric segments rank lower than string segments
                return -1
            if num2:
                return 1
            # Compare string segments as ASCII code points
            return -1 if seg1 < seg2 else 1

        # Rank longer pre-release segment sequences higher when common prefix matches
        if len(pre1) < len(pre2):
            return -1
        if len(pre1) > len(pre2):
            return 1
        return 0


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[semver_core.VersionEngine, VersionEngine],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 01050b08b8a5
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Library interface for version range parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from support.lib.framework import data_type, operation, poly_type
from . import semver_core


@dataclass
class InvalidRangeError(semver_core.SemVerError):
    """Raised when a version range expression contains malformed syntax."""

    raw_range: str = ""


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
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 70386c550bf4
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Library implementation for version range parsing and matching."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)
from . import semver_core
from . import semver_range


_OP_SPACE_RE = re.compile(r"(==|!=|<=|>=|<|>|=|\^|~)\s+")
_COMP_PREFIX_RE = re.compile(r"^(==|!=|<=|>=|<|>|=|\^|~)?(.*)$")
_WILDCARD_ANY = frozenset({"*", "x", "X", "*.*", "x.x", "X.X", "*.*.*", "x.x.x", "X.X.X"})
_WILDCARD_MAJOR_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(?:x|X|\*)(?:\.(?:x|X|\*))?$"
)
_WILDCARD_MINOR_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(?:x|X|\*)$"
)
_SEMVER_CHECK_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _is_valid_semver(text: str) -> bool:
    """Checks whether text conforms to SemVer 2.0.0 grammar."""
    return _SEMVER_CHECK_RE.fullmatch(text) is not None


def _parse_single_comparator(
    token: str,
    version_engine: semver_core.VersionEngine,
) -> Optional[List[Tuple[semver_core.ComparatorOp, semver_core.Version]]]:
    """Expands a single comparator, caret, tilde, or wildcard token into primitive comparators."""
    match = _COMP_PREFIX_RE.match(token)
    assert match is not None
    op_str = match.group(1) or ""
    operand = match.group(2)

    # Check wildcard expressions when no operator or equality operator is used
    if op_str in ("", "=", "=="):
        if operand in _WILDCARD_ANY:
            return [(semver_core.ComparatorOp.GE, semver_core.Version(0, 0, 0))]
        m_major = _WILDCARD_MAJOR_RE.fullmatch(operand)
        if m_major is not None:
            major = int(m_major.group(1))
            return [
                (semver_core.ComparatorOp.GE, semver_core.Version(major, 0, 0)),
                (semver_core.ComparatorOp.LT, semver_core.Version(major + 1, 0, 0)),
            ]
        m_minor = _WILDCARD_MINOR_RE.fullmatch(operand)
        if m_minor is not None:
            major = int(m_minor.group(1))
            minor = int(m_minor.group(2))
            return [
                (semver_core.ComparatorOp.GE, semver_core.Version(major, minor, 0)),
                (semver_core.ComparatorOp.LT, semver_core.Version(major, minor + 1, 0)),
            ]

    if not _is_valid_semver(operand):
        return None
    target = version_engine.parse_version(operand)

    if op_str in ("", "=", "=="):
        return [(semver_core.ComparatorOp.EQ, target)]
    if op_str == "!=":
        return [(semver_core.ComparatorOp.NE, target)]
    if op_str == "<":
        return [(semver_core.ComparatorOp.LT, target)]
    if op_str == "<=":
        return [(semver_core.ComparatorOp.LE, target)]
    if op_str == ">":
        return [(semver_core.ComparatorOp.GT, target)]
    if op_str == ">=":
        return [(semver_core.ComparatorOp.GE, target)]
    if op_str == "^":
        # Expand caret prefixes based on first non-zero component boundaries
        if target.major > 0:
            upper = semver_core.Version(target.major + 1, 0, 0)
        elif target.minor > 0:
            upper = semver_core.Version(0, target.minor + 1, 0)
        else:
            upper = semver_core.Version(0, 0, target.patch + 1)
        return [
            (semver_core.ComparatorOp.GE, target),
            (semver_core.ComparatorOp.LT, upper),
        ]
    # Expand tilde prefixes into lower and upper minor boundaries (op_str == "~")
    upper_tilde = semver_core.Version(target.major, target.minor + 1, 0)
    return [
        (semver_core.ComparatorOp.GE, target),
        (semver_core.ComparatorOp.LT, upper_tilde),
    ]


def _compile_range(
    raw_range: str,
    version_engine: semver_core.VersionEngine,
) -> Optional[Tuple[str, List[List[Tuple[semver_core.ComparatorOp, semver_core.Version]]]]]:
    """Validates and compiles a range string into DNF comparator clauses."""
    # Delimit comparators strictly by whitespace; reject comma-separated comparators
    if "," in raw_range:
        return None

    trimmed = raw_range.strip()
    if not trimmed:
        return None

    clauses: List[List[Tuple[semver_core.ComparatorOp, semver_core.Version]]] = []
    for raw_clause in trimmed.split("||"):
        clause = raw_clause.strip()
        if not clause:
            return None

        # Normalize optional whitespace between relational/prefix operators and operands
        normalized = _OP_SPACE_RE.sub(r"\1", clause)
        tokens = normalized.split()
        clause_comparators: List[Tuple[semver_core.ComparatorOp, semver_core.Version]] = []
        idx = 0
        while idx < len(tokens):
            if idx + 1 < len(tokens) and tokens[idx + 1] == "-":
                if (
                    idx + 2 >= len(tokens)
                    or not _is_valid_semver(tokens[idx])
                    or not _is_valid_semver(tokens[idx + 2])
                ):
                    return None
                low_ver = version_engine.parse_version(tokens[idx])
                high_ver = version_engine.parse_version(tokens[idx + 2])
                clause_comparators.append((semver_core.ComparatorOp.GE, low_ver))
                clause_comparators.append((semver_core.ComparatorOp.LE, high_ver))
                idx += 3
            else:
                comp = _parse_single_comparator(tokens[idx], version_engine)
                if comp is None:
                    return None
                clause_comparators.extend(comp)
                idx += 1
        clauses.append(clause_comparators)

    return trimmed, clauses


def _matches_comparator(
    version: semver_core.Version,
    op: semver_core.ComparatorOp,
    target: semver_core.Version,
    version_engine: semver_core.VersionEngine,
) -> bool:
    """Evaluates a single comparator against a candidate version."""
    cmp = version_engine.compare_precedence(version, target)
    if op == semver_core.ComparatorOp.EQ:
        return cmp == 0
    if op == semver_core.ComparatorOp.NE:
        return cmp != 0
    if op == semver_core.ComparatorOp.LT:
        return cmp < 0
    if op == semver_core.ComparatorOp.LE:
        return cmp <= 0
    if op == semver_core.ComparatorOp.GT:
        return cmp > 0
    return cmp >= 0


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        version_engine = get_singleton(semver_core.VersionEngine)
        compiled = _compile_range(text, version_engine)
        if compiled is None:
            raise semver_range.InvalidRangeError(
                message=f"Invalid version range expression: {text!r}",
                raw_range=text,
            )
        trimmed, _ = compiled
        return semver_range.VersionRange(raw_text=trimmed)

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
        compiled = _compile_range(range_constraint.raw_text, version_engine)
        clauses = compiled[1] if compiled is not None else []

        for clause in clauses:
            # Filter out pre-release versions when include_prerelease is False
            # unless the clause explicitly targets a pre-release on the same major.minor.patch
            if version.is_prerelease and not include_prerelease:
                has_matching_prerelease_target = any(
                    target.is_prerelease
                    and (target.major, target.minor, target.patch)
                    == (version.major, version.minor, version.patch)
                    for _, target in clause
                )
                if not has_matching_prerelease_target:
                    continue

            if all(
                _matches_comparator(version, op, target, version_engine)
                for op, target in clause
            ):
                return True

        return False


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RangeEngine,
        keys=[semver_range.RangeEngine, RangeEngine],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: c9a050ce0ca9
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---
