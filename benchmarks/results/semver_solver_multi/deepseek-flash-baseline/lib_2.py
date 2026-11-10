# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261107_025944_deepseek-flash_semver_solver_multi_baseline
# Timestamp: 2026-11-07T02:59:44.481063+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 72,778
#   Cached Inbound Tokens:   5,545,088
#   Outbound Tokens:         104,702
#   Total Tokens:            5,722,568
#   Financial Cost ($USD):   $0.0904
#   Wall Clock Duration:     741.61s
#   Step Latencies (s):      [723.8]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       34
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
"""Package repository and dependency resolution interface specification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver.pyi


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
# LAST_CLEANED: 2026-11-07T03:12:05Z
# LAST_CHANGED: 2026-11-07T03:12:05Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 28c5784c400c
# COVERAGE_AUDIT: 2026-11-07T03:12:05Z
# QA_AUDIT: 2026-11-07T03:12:05Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Concrete package repository and backtracking dependency solver."""

from __future__ import annotations

from functools import cmp_to_key
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi


class PackageRepository(dependency_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        # Indexed release history: package name -> releases in descending precedence order.
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # MUST register the package release into the repository.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # Re-sort in descending version precedence order using the version engine.
        version_engine = get_singleton(semver_core.VersionEngine)
        precedence_key = cmp_to_key(version_engine.compare_precedence)
        releases.sort(key=lambda release: precedence_key(release.version), reverse=True)

    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # WHEN name is not registered, MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository.", name
            )
        # MUST yield a shallow copy of the releases ordered by descending precedence.
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        # MUST evaluate to True when the name exists in the repository, and False otherwise.
        return name in self._packages

    def all_packages(self) -> Set[str]:
        # MUST produce the set of all registered package names.
        return set(self._packages)


class DependencySolver(dependency_solver.DependencySolver):
    tier = system

    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        # Accumulated constraints: package name -> [(requesting package, range), ...].
        accumulated: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        # Partial assignment of concrete releases and its undo/derivation history.
        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            # A complete assignment satisfies every accumulated constraint.
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True

            # Determine viable candidates per unassigned package; unregistered packages
            # evaluate to an empty candidate list instead of leaking PackageNotFoundError.
            candidates: Dict[str, List[dependency_solver.PackageRelease]] = {}
            for name in unassigned:
                available = (
                    repository.get_releases(name) if repository.has_package(name) else []
                )
                candidates[name] = [
                    release
                    for release in available
                    if all(
                        range_engine.satisfies(release.version, constraint, False)
                        for _, constraint in accumulated[name]
                    )
                ]

            # Minimum Remaining Values selection; ties resolve by lexical package name.
            selected = min(unassigned, key=lambda candidate: (len(candidates[candidate]), candidate))
            options = candidates[selected]

            # When candidate options exhaust, record the conflict and backtrack.
            if not options:
                requesters = [requester for requester, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False

            # Explore viable releases in descending precedence order.
            for candidate_release in options:
                assignment[selected] = candidate_release
                derivation_steps.append(f"Assign '{selected}' to {candidate_release.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []

                # Forward checking: validate declared dependencies against the assignment.
                for dependency in candidate_release.dependencies:
                    if dependency.name in assignment:
                        if not range_engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            # Conflict with an already assigned package triggers backtracking.
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        # Merge newly introduced requirements into accumulated constraints.
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and backtrack():
                    return True

                # Undo the assignment and every constraint this branch introduced.
                for name, entry in newly_added:
                    accumulated[name].remove(entry)
                    if not accumulated[name]:
                        del accumulated[name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if backtrack():
            # Compile selected releases and decision sequence into a ResolutionOutcome.
            selected_versions = {
                name: release.version for name, release in assignment.items()
            }
            return dependency_solver.ResolutionOutcome(
                selected_versions, tuple(derivation_steps)
            )

        # Exhausted search: report the accumulated conflict trail.
        explanation = "; ".join(conflict_trail)
        raise dependency_solver.ResolutionConflictError(
            f"Dependency resolution failed: {explanation}",
            tuple(sorted(conflicting_packages)),
            explanation,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, dependency_solver.PackageRepository],
        tier=system,
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, dependency_solver.DependencySolver],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:12:05Z
# LAST_CHANGED: 2026-11-07T03:12:05Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 973029df3477
# COVERAGE_AUDIT: 2026-11-07T03:12:05Z
# QA_AUDIT: 2026-11-07T03:12:05Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""SemVer 2.0.0 parsing and precedence comparison interface specification."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type

# Requirements specified in semver_core.pyi


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __str__(self) -> str:
        # Exceptions expose exactly their diagnostic message when stringified.
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered."""

    raw_text: str


class ComparatorOp(enum.Enum):
    """Relational comparison operator for version constraints."""

    EQ = '=='
    NE = '!='
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='


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
        # A version is a pre-release exactly when it carries pre-release identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Canonical rendering: numeric core, then '-pre.release', then '+build.metadata'.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # Canonical string representation delegates directly to format().
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
# LAST_CLEANED: 2026-11-07T03:12:05Z
# LAST_CHANGED: 2026-11-07T03:12:05Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 5db036242b12
# COVERAGE_AUDIT: 2026-11-07T03:12:05Z
# QA_AUDIT: 2026-11-07T03:12:05Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Concrete SemVer 2.0.0 parsing and precedence engine."""

from __future__ import annotations

import re
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 grammar: non-negative numeric core without leading zeroes, an optional
# dot-separated pre-release identifier sequence, and optional dot-separated build metadata.
_SEMVER_GRAMMAR = re.compile(
    r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
    r'(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)'
    r'(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?'
    r'(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$'
)


class VersionEngine(semver_core.VersionEngine):
    tier = system

    def __init__(self) -> None:
        # Reuse the compiled grammar for every parse request (stateless engine cache).
        self._grammar = _SEMVER_GRAMMAR

    def parse_version(self, text: str) -> semver_core.Version:
        # Enforce the SemVer 2.0.0 grammar and leading-zero constraints before coercion.
        match = self._grammar.fullmatch(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                f"Invalid semantic version: {text!r}", text
            )
        major, minor, patch, prerelease, build = match.groups()
        # Split optional dot-separated identifier sequences into ordered tuples.
        return semver_core.Version(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=tuple(prerelease.split(".")) if prerelease else (),
            build=tuple(build.split(".")) if build else (),
        )

    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        # Numeric major, minor, and patch components dominate precedence.
        for first, second in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if first != second:
                return -1 if first < second else 1
        # Identical numeric cores: a normal version outranks a pre-release version.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # Compare pre-release identifiers position by position.
        for first, second in zip(v1.prerelease, v2.prerelease):
            if first == second:
                continue
            # Numeric identifiers compare numerically and rank below alphanumeric ones.
            if first.isdigit() and second.isdigit():
                return -1 if int(first) < int(second) else 1
            if first.isdigit():
                return -1
            if second.isdigit():
                return 1
            # Alphanumeric identifiers compare in ASCII lexicographical order.
            return -1 if first < second else 1
        # A longer pre-release sequence outranks a shared prefix; build metadata is ignored.
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_core.VersionEngine],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:12:05Z
# LAST_CHANGED: 2026-11-07T03:12:05Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9797f9ad7bcc
# COVERAGE_AUDIT: 2026-11-07T03:12:05Z
# QA_AUDIT: 2026-11-07T03:12:05Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Version range parsing and matching interface specification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type
from . import semver_core

# Requirements specified in semver_range.pyi


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
        # The raw range text is the canonical string representation.
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
# LAST_CLEANED: 2026-11-07T03:12:05Z
# LAST_CHANGED: 2026-11-07T03:12:05Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 76bd4c26ae82
# COVERAGE_AUDIT: 2026-11-07T03:12:05Z
# QA_AUDIT: 2026-11-07T03:12:05Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Concrete version range parsing and matching engine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

# Wildcard bound: an optional numeric major/minor prefix followed by wildcard components.
_WILDCARD_GRAMMAR = re.compile(r"^(?:(?:\d+)(?:\.\d+)?\.)?[xX*](?:\.[xX*])*$")
_WILDCARD_COMPONENTS = ("x", "X", "*")
_OPERATORS = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")
_CLAUSE_SEPARATOR = "||"
_HYPHEN = "-"


@dataclass(frozen=True)
class _VersionSpec:
    """Parsed range bound: numeric prefix plus an optional concrete version."""

    parts: Tuple[int, ...]
    version: Optional[semver_core.Version]

    @property
    def specified(self) -> int:
        # Number of explicitly supplied numeric components in the bound.
        return len(self.parts)


@dataclass(frozen=True)
class _Comparator:
    """Single relational predicate inside a conjunctive range clause."""

    op: semver_core.ComparatorOp
    version: semver_core.Version

    def matches(self, candidate: semver_core.Version, engine: semver_core.VersionEngine) -> bool:
        # Precedence ordering decides every relational comparator outcome.
        ordering = engine.compare_precedence(candidate, self.version)
        if self.op is semver_core.ComparatorOp.EQ:
            return ordering == 0
        if self.op is semver_core.ComparatorOp.NE:
            return ordering != 0
        if self.op is semver_core.ComparatorOp.LT:
            return ordering < 0
        if self.op is semver_core.ComparatorOp.LE:
            return ordering <= 0
        if self.op is semver_core.ComparatorOp.GT:
            return ordering > 0
        return ordering >= 0


def _pad(parts: Sequence[int]) -> semver_core.Version:
    # Missing numeric components default to zero for a concrete lower boundary.
    components = list(parts) + [0, 0, 0]
    return semver_core.Version(components[0], components[1], components[2])


def _next_prefix(parts: Sequence[int]) -> semver_core.Version:
    # Exclusive boundary immediately after a wildcard prefix (e.g. 1.x -> 2.0.0).
    if len(parts) == 1:
        return semver_core.Version(parts[0] + 1, 0, 0)
    return semver_core.Version(parts[0], parts[1] + 1, 0)


def _caret_upper(spec: _VersionSpec) -> semver_core.Version:
    # Caret compatibility stops at the first non-zero numeric component.
    if spec.version is not None:
        version = spec.version
        if version.major > 0:
            return semver_core.Version(version.major + 1, 0, 0)
        if version.minor > 0:
            return semver_core.Version(0, version.minor + 1, 0)
        return semver_core.Version(0, 0, version.patch + 1)
    # Wildcard caret prefixes expand on their supplied numeric components.
    if spec.specified == 1:
        return semver_core.Version(spec.parts[0] + 1, 0, 0)
    major, minor = spec.parts[0], spec.parts[1]
    if major > 0:
        return semver_core.Version(major + 1, 0, 0)
    if minor > 0:
        return semver_core.Version(0, minor + 1, 0)
    return semver_core.Version(0, 1, 0)


def _tilde_upper(spec: _VersionSpec) -> semver_core.Version:
    # Tilde compatibility allows patch-level changes below the next minor boundary.
    if spec.version is not None:
        return semver_core.Version(spec.version.major, spec.version.minor + 1, 0)
    if spec.specified == 1:
        return semver_core.Version(spec.parts[0] + 1, 0, 0)
    return semver_core.Version(spec.parts[0], spec.parts[1] + 1, 0)


def _split_operator(token: str) -> Tuple[str, str]:
    # Longest relational/prefix operators are matched before their prefixes.
    for operator in _OPERATORS:
        if token.startswith(operator):
            return operator, token[len(operator):]
    return "", token


def _parse_spec(
    text: str,
    engine: semver_core.VersionEngine,
    raw_range: str,
    prerelease_cores: Set[Tuple[int, int, int]],
) -> _VersionSpec:
    # Wildcard bounds carry an optional numeric prefix followed by wildcard components.
    if _WILDCARD_GRAMMAR.fullmatch(text):
        parts: List[int] = []
        for component in text.split("."):
            if component in _WILDCARD_COMPONENTS:
                break
            parts.append(int(component))
        return _VersionSpec(tuple(parts), None)
    # Full semantic version bounds are validated against SemVer 2.0.0 grammar.
    try:
        version = engine.parse_version(text)
    except semver_core.InvalidVersionError as error:
        raise semver_range.InvalidRangeError(
            f"Invalid version bound '{text}' in range expression '{raw_range}'", raw_range
        ) from error
    # Explicit prerelease bounds authorize prerelease candidates sharing that numeric core.
    if version.is_prerelease:
        prerelease_cores.add((version.major, version.minor, version.patch))
    return _VersionSpec((version.major, version.minor, version.patch), version)


def _expand_operator(operator: str, spec: _VersionSpec) -> List[List[_Comparator]]:
    # '*' wildcard: positive ranges accept every version, impossible bounds accept none.
    if spec.specified == 0:
        return [] if operator in ("!=", "<", ">") else [[]]
    lower = spec.version if spec.version is not None else _pad(spec.parts)
    if operator in ("", "=", "=="):
        if spec.version is not None:
            return [[_Comparator(semver_core.ComparatorOp.EQ, lower)]]
        return [
            [_Comparator(semver_core.ComparatorOp.GE, lower),
             _Comparator(semver_core.ComparatorOp.LT, _next_prefix(spec.parts))]
        ]
    if operator == "!=":
        if spec.version is not None:
            return [[_Comparator(semver_core.ComparatorOp.NE, lower)]]
        return [
            [_Comparator(semver_core.ComparatorOp.LT, lower)],
            [_Comparator(semver_core.ComparatorOp.GE, _next_prefix(spec.parts))],
        ]
    if operator == ">=":
        return [[_Comparator(semver_core.ComparatorOp.GE, lower)]]
    if operator == ">":
        if spec.version is not None:
            return [[_Comparator(semver_core.ComparatorOp.GT, lower)]]
        return [[_Comparator(semver_core.ComparatorOp.GE, _next_prefix(spec.parts))]]
    if operator == "<=":
        if spec.version is not None:
            return [[_Comparator(semver_core.ComparatorOp.LE, lower)]]
        return [[_Comparator(semver_core.ComparatorOp.LT, _next_prefix(spec.parts))]]
    if operator == "<":
        return [[_Comparator(semver_core.ComparatorOp.LT, lower)]]
    # Caret and tilde prefixes expand into a lower bound plus an exclusive upper boundary.
    if operator == "^":
        return [
            [_Comparator(semver_core.ComparatorOp.GE, lower),
             _Comparator(semver_core.ComparatorOp.LT, _caret_upper(spec))]
        ]
    return [
        [_Comparator(semver_core.ComparatorOp.GE, lower),
         _Comparator(semver_core.ComparatorOp.LT, _tilde_upper(spec))]
    ]


def _expand_hyphen(lower_spec: _VersionSpec, upper_spec: _VersionSpec) -> List[List[_Comparator]]:
    comparators: List[_Comparator] = []
    # Inclusive lower bound; wildcard prefixes pad missing numeric components with zero.
    if lower_spec.specified > 0:
        lower = lower_spec.version if lower_spec.version is not None else _pad(lower_spec.parts)
        comparators.append(_Comparator(semver_core.ComparatorOp.GE, lower))
    # Inclusive upper bound for full versions, exclusive for wildcard prefixes.
    if upper_spec.specified > 0:
        if upper_spec.version is not None:
            comparators.append(_Comparator(semver_core.ComparatorOp.LE, upper_spec.version))
        else:
            comparators.append(_Comparator(semver_core.ComparatorOp.LT, _next_prefix(upper_spec.parts)))
    return [comparators]


def _compile_clause(
    clause: str,
    engine: semver_core.VersionEngine,
    raw_range: str,
    prerelease_cores: Set[Tuple[int, int, int]],
) -> List[List[_Comparator]]:
    tokens = clause.split()
    # Hyphen ranges connect exactly two bounds with a standalone '-' separator.
    if _HYPHEN in tokens:
        if len(tokens) != 3 or tokens[1] != _HYPHEN:
            raise semver_range.InvalidRangeError("Malformed hyphen range expression.", raw_range)
        lower = _parse_spec(tokens[0], engine, raw_range, prerelease_cores)
        upper = _parse_spec(tokens[2], engine, raw_range, prerelease_cores)
        return _expand_hyphen(lower, upper)
    # Whitespace-delimited comparators combine conjunctively into one clause.
    comparators: List[List[_Comparator]] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATORS:
            # Optional whitespace between operator and bound consumes the following token.
            if index + 1 >= len(tokens):
                raise semver_range.InvalidRangeError("Operator is missing its version bound.", raw_range)
            operator = token
            bound_text = tokens[index + 1]
            index += 2
        else:
            operator, bound_text = _split_operator(token)
            index += 1
        spec = _parse_spec(bound_text, engine, raw_range, prerelease_cores)
        comparators = [
            existing + term
            for existing in comparators
            for term in _expand_operator(operator, spec)
        ]
    return comparators


def _compile(
    text: str,
    engine: semver_core.VersionEngine,
) -> Tuple[List[List[_Comparator]], Set[Tuple[int, int, int]]]:
    trimmed = text.strip()
    # PRECONDITIONS: empty expressions, comma-delimited lists, and empty union clauses are malformed.
    if not trimmed or "," in trimmed:
        raise semver_range.InvalidRangeError("Range expression must be non-empty and comma-free.", text)
    clauses: List[List[_Comparator]] = []
    prerelease_cores: Set[Tuple[int, int, int]] = set()
    for raw_clause in trimmed.split(_CLAUSE_SEPARATOR):
        clause = raw_clause.strip()
        if not clause:
            raise semver_range.InvalidRangeError("Range expression contains an empty clause.", text)
        clauses.extend(_compile_clause(clause, engine, text, prerelease_cores))
    return clauses, prerelease_cores


class RangeEngine(semver_range.RangeEngine):
    tier = system

    def parse_range(self, text: str) -> semver_range.VersionRange:
        # Validate the expression before recording its trimmed canonical text.
        engine = get_singleton(semver_core.VersionEngine)
        _compile(text, engine)
        return semver_range.VersionRange(text.strip())

    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        engine = get_singleton(semver_core.VersionEngine)
        clauses, prerelease_cores = _compile(range_constraint.raw_text, engine)
        numeric_core = (version.major, version.minor, version.patch)
        # DNF evaluation: the version satisfies at least one conjunctive clause.
        for clause in clauses:
            if all(comparator.matches(version, engine) for comparator in clause):
                # Prerelease candidates need explicit pre-release targeting unless allowed.
                if version.is_prerelease and not include_prerelease and numeric_core not in prerelease_cores:
                    return False
                return True
        return False


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RangeEngine,
        keys=[RangeEngine, semver_range.RangeEngine],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:12:05Z
# LAST_CHANGED: 2026-11-07T03:12:05Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 684545fd4071
# COVERAGE_AUDIT: 2026-11-07T03:12:05Z
# QA_AUDIT: 2026-11-07T03:12:05Z
# --- END AUTOFAB METADATA ---
