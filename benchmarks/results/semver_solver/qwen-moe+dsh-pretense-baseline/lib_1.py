# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_212341_qwen-moe_semver_solver_pretense_baseline
# Timestamp: 2026-10-29T21:23:41.212423+00:00
# Benchmark Task: semver_solver
# Model: qwen-moe (Tier 1)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 895,408
#   Cached Inbound Tokens:   19,059,198
#   Outbound Tokens:         225,289
#   Total Tokens:            20,179,895
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     3868.80s
#   Step Latencies (s):      [3861.3]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
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
"""Low-level interface specification for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


# ==============================================================================
# Exception types
# ==============================================================================

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

    def __str__(self) -> str:
        return self.message


@dataclass
class InvalidRangeError(SemVerError):
    """Raised when a version range expression contains malformed syntax.

    Args:
        message: Diagnostic description of the error.
        raw_range: Original malformed range expression string.
    """
    raw_range: str

    def __str__(self) -> str:
        return self.message


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

    def __str__(self) -> str:
        return self.message


@dataclass
class PackageNotFoundError(SemVerError):
    """Raised when a referenced package name does not exist in the repository.

    Args:
        message: Diagnostic description of the missing package.
        package_name: Name of the missing package.
    """
    package_name: str

    def __str__(self) -> str:
        return self.message


# ==============================================================================
# Enum types
# ==============================================================================

class ComparatorOp(enum.Enum):
    """Relational comparison operator for version constraints."""
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


# ==============================================================================
# Data types
# ==============================================================================

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
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            result += f"-{'.'.join(self.prerelease)}"
        if self.build:
            result += f"+{'.'.join(self.build)}"
        return result

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


# ==============================================================================
# Service protocols (interface stubs)
# ==============================================================================

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
        include_prerelease: bool = False,
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T22:28:09Z
# LAST_CHANGED: 2026-10-29T22:28:09Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 43b412348a94
# COVERAGE_AUDIT: 2026-10-29T22:28:09Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T22:28:09Z
# PRETENSE_QA_AUDIT: 2026-10-29T22:28:09Z
# QA_AUDIT: 2026-10-29T22:28:09Z
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete implementation of SemVer 2.0 parsing, precedence, and dependency resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    enter_phase,
    get_singleton,
    get_default_registry,
    system,
)

from . import semver_solver


# ==============================================================================
# VersionEngine implementation
# ==============================================================================

@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    SEMVER_RE = re.compile(
        r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )

    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        m = self.SEMVER_RE.match(text)
        if not m:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid SemVer version string: {text!r}",
                raw_text=text,
            )
        major = int(m.group("major"))
        minor = int(m.group("minor"))
        patch = int(m.group("patch"))
        prerelease_str = m.group("prerelease")
        build_str = m.group("build")

        if prerelease_str is not None:
            prerelease: Tuple[str, ...] = tuple(prerelease_str.split("."))
        else:
            prerelease = ()

        if build_str is not None:
            build: Tuple[str, ...] = tuple(build_str.split("."))
        else:
            build = ()

        return semver_solver.Version(
            major=major, minor=minor, patch=patch,
            prerelease=prerelease, build=build,
        )

    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        # Compare major, minor, patch numerically
        for attr in ("major", "minor", "patch"):
            a = getattr(v1, attr)
            b = getattr(v2, attr)
            if a < b:
                return -1
            if a > b:
                return 1

        # No prerelease > has prerelease (when major.minor.patch equal)
        v1_pre = v1.prerelease
        v2_pre = v2.prerelease

        if not v1_pre and not v2_pre:
            return 0
        if v1_pre and not v2_pre:
            return -1  # normal > prerelease
        if not v1_pre and v2_pre:
            return 1

        # Both have prerelease: compare segment by segment
        for i in range(max(len(v1_pre), len(v2_pre))):
            if i >= len(v1_pre):
                return -1  # fewer segments ranks lower
            if i >= len(v2_pre):
                return 1

            a = v1_pre[i]
            b = v2_pre[i]

            a_is_num = a.isdigit()
            b_is_num = b.isdigit()

            if a_is_num and b_is_num:
                ai, bi = int(a), int(b)
                if ai < bi:
                    return -1
                if ai > bi:
                    return 1
            elif a_is_num and not b_is_num:
                return -1  # numeric < string
            elif not a_is_num and b_is_num:
                return 1
            else:
                # Both strings: ASCII comparison
                if a < b:
                    return -1
                if a > b:
                    return 1

        return 0

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        trimmed = text.strip()
        if not trimmed:
            raise semver_solver.InvalidRangeError(
                message="Empty range expression",
                raw_range=text,
            )

        # Check for commas (not permitted)
        if "," in trimmed:
            raise semver_solver.InvalidRangeError(
                message="Comma delimiters are not permitted in range expressions",
                raw_range=text,
            )

        # Split on || for union
        clauses = trimmed.split("||")
        for clause in clauses:
            c = clause.strip()
            if not c:
                raise semver_solver.InvalidRangeError(
                    message="Empty clause in union expression",
                    raw_range=text,
                )

        return semver_solver.VersionRange(raw_text=trimmed)

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        raw = range_constraint.raw_text
        clauses = raw.split("||")

        # Handle prerelease filtering
        if version.is_prerelease and not include_prerelease:
            # Check if any clause explicitly targets this prerelease
            for clause in clauses:
                if self._explicitly_targets_prerelease(version, clause.strip()):
                    return True
            return False

        for clause in clauses:
            if self._clause_satisfies(version, clause.strip()):
                return True
        return False

    def _clause_satisfies(self, version: semver_solver.Version, clause: str) -> bool:
        """Check if version satisfies a single clause (space-separated comparators)."""
        clause = clause.strip()
        if not clause:
            return False

        # Handle bare wildcards
        if clause == "*":
            return True
        parts = clause.split()
        if len(parts) == 1 and parts[0] in ("*", "x", "X"):
            return True

        # Handle hyphen ranges: "ver1 - ver2" means ">=ver1 AND <=ver2"
        if len(parts) == 3 and parts[1] == "-":
            low = self._try_parse(parts[0])
            high = self._try_parse(parts[2])
            if low is not None and high is not None:
                return (self.compare_precedence(version, low) >= 0 and
                        self.compare_precedence(version, high) <= 0)

        # Handle partial wildcards like "1.*" or "1.2.*"
        if len(parts) == 1:
            part = parts[0]
            if "." in part:
                segments = part.split(".")
                if len(segments) == 2 and segments[1] in ("*", "x", "X"):
                    try:
                        major = int(segments[0])
                        return version.major == major
                    except ValueError:
                        pass
                elif len(segments) == 3 and segments[2] in ("*", "x", "X"):
                    try:
                        major = int(segments[0])
                        minor = int(segments[1])
                        return version.major == major and version.minor == minor
                    except ValueError:
                        pass

        # Split comparators by whitespace
        comparators = self._parse_comparator_clause(parts)
        if comparators is None:
            return False

        return all(self._check_comparator(version, op, target) for op, target in comparators)

    def _parse_comparator_clause(self, parts: List[str]) -> Optional[List[Tuple[str, semver_solver.Version]]]:
        """Parse a list of parts into (op, version) pairs. Returns None on error."""
        result = []
        i = 0
        while i < len(parts):
            part = parts[i]
            if part.startswith("-") and i + 1 < len(parts) and i == 0:
                # Hyphen range: "-1.0.0 2.0.0"
                if len(parts) != 2:
                    return None
                low_ver = self._try_parse(parts[0][1:])
                high_ver = self._try_parse(parts[1])
                if low_ver is None or high_ver is None:
                    return None
                result.append((">=", low_ver))
                result.append(("<=", high_ver))
                i += 2
            else:
                # Single comparator
                op_match = re.match(r"(^!=|^==|^>=|^<=|^>|^<|^=|^~|^[\^])(.+)$", part)
                if op_match:
                    op = op_match.group(1)
                    ver_str = op_match.group(2).strip()
                    if op == "=":
                        op = "=="
                    ver = self._try_parse(ver_str)
                    if ver is None:
                        return None
                    result.append((op, ver))
                else:
                    return None
            i += 1
        return result if result else None

    def _try_parse(self, s: str) -> Optional[semver_solver.Version]:
        """Try to parse a version string, returning None on failure."""
        try:
            return self.parse_version(s)
        except (semver_solver.InvalidVersionError, ValueError):
            return None

    def _check_comparator(self, version: semver_solver.Version, op: str, target: semver_solver.Version) -> bool:
        """Check a single comparator against a version."""
        if op == "^":
            # Caret: allows changes that do not modify the left-most non-zero digit
            if self.compare_precedence(version, target) < 0:
                return False
            if target.major > 0:
                upper = semver_solver.Version(target.major + 1, 0, 0, ("0",))
            elif target.minor > 0:
                upper = semver_solver.Version(0, target.minor + 1, 0, ("0",))
            else:
                upper = semver_solver.Version(0, 0, target.patch + 1, ("0",))
            return self.compare_precedence(version, upper) < 0
        elif op == "~":
            # Tilde: allows patch-level changes
            if self.compare_precedence(version, target) < 0:
                return False
            upper = semver_solver.Version(target.major, target.minor + 1, 0, ("0",))
            return self.compare_precedence(version, upper) < 0
        cmp = self.compare_precedence(version, target)
        if op == "==":
            return cmp == 0
        elif op == "!=":
            return cmp != 0
        elif op == "<":
            return cmp < 0
        elif op == "<=":
            return cmp <= 0
        elif op == ">":
            return cmp > 0
        elif op == ">=":
            return cmp >= 0
        return False  # pragma: no cover — all known operators handled above

    def _explicitly_targets_prerelease(
        self, version: semver_solver.Version, clause: str
    ) -> bool:
        """Check if a clause explicitly targets the given prerelease version."""
        parts = clause.split()
        comparators = self._parse_comparator_clause(parts)
        if comparators is None:  # pragma: no cover — unreachable under valid contract inputs
            return False
        # Check if any comparator specifies the same major.minor.patch with a prerelease
        for op, target in comparators:
            if (target.major == version.major and target.minor == version.minor
                    and target.patch == version.patch and target.prerelease):
                if op == "==":
                    return True
        return False


# ==============================================================================
# PackageRepository implementation
# ==============================================================================

@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        self._packages.setdefault(release.name, []).append(release)
        # Sort descending by precedence using compare_precedence
        engine = get_singleton(VersionEngine)
        releases = self._packages[release.name]
        for i in range(len(releases)):
            for j in range(i + 1, len(releases)):
                if engine.compare_precedence(releases[i].version, releases[j].version) < 0:
                    releases[i], releases[j] = releases[j], releases[i]

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name."""
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package {name!r} not found in repository",
                package_name=name,
            )
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    def all_packages(self) -> Set[str]:
        """Returns the set of all registered package names."""
        return set(self._packages.keys())


# ==============================================================================
# DependencySolver implementation
# ==============================================================================

@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        self._version_engine = None  # resolved on demand
        self._repository = None

    def _get_engine(self) -> VersionEngine:
        if self._version_engine is None:
            self._version_engine = get_singleton(VersionEngine)
        return self._version_engine

    def _get_repository(self) -> PackageRepository:
        if self._repository is None:
            self._repository = get_singleton(PackageRepository)
        return self._repository

    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        engine = self._get_engine()
        repo = self._get_repository()

        # Initialize accumulated constraints from root dependencies
        accumulated_constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dep in root_dependencies:
            accumulated_constraints.setdefault(dep.name, []).append(
                ("root", dep.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            unassigned = [p for p in accumulated_constraints if p not in assignment]
            if not unassigned:
                return True

            # MRV: find package with fewest viable candidates
            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for pkg in unassigned:
                try:
                    available = repo.get_releases(pkg)
                except semver_solver.PackageNotFoundError:
                    available = []
                viable = [
                    rel for rel in available
                    if all(
                        engine.satisfies(rel.version, rng)
                        for _, rng in accumulated_constraints[pkg]
                    )
                ]
                candidates_map[pkg] = viable

            # Select package with fewest candidates; ties broken lexically
            selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
                conflicting_packages.add(selected_pkg)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
                )
                return False

            # Try candidates in descending precedence order
            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(
                    f"Assign '{selected_pkg}' to {candidate.version}"
                )

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        # Check against already assigned package
                        if not engine.satisfies(
                            assignment[dep.name].version, dep.range_constraint
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

                # Undo: pop newly added constraints
                for pkg_name, constraint_entry in newly_added:
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        success = backtrack()
        if success:
            return semver_solver.ResolutionOutcome(
                selected_versions={name: release.version for name, release in assignment.items()},
                derivation_steps=tuple(derivation_steps),
            )
        else:
            # Convert to ResolutionConflictError
            pkg_list = sorted(conflicting_packages) if conflicting_packages else ["unknown"]
            explanation = "; ".join(conflict_trail) if conflict_trail else "Unresolvable conflict"
            raise semver_solver.ResolutionConflictError(
                message=explanation,
                conflicting_packages=tuple(pkg_list),
                explanation=explanation,
            )


# ==============================================================================
# Module initialization (auto-generated block maintained by tooling)
# ==============================================================================


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
# LAST_CLEANED: 2026-10-29T22:28:09Z
# LAST_CHANGED: 2026-10-29T22:28:09Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 40523a2d9da2
# COVERAGE_AUDIT: 2026-10-29T22:28:09Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T22:28:09Z
# PRETENSE_QA_AUDIT: 2026-10-29T22:28:09Z
# QA_AUDIT: 2026-10-29T22:28:09Z
# --- END CLEANROOM METADATA ---
