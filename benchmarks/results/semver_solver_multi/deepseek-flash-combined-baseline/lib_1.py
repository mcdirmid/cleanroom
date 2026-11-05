# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_052003_deepseek-flash_semver_solver_multi_combined_baseline
# Timestamp: 2026-11-05T05:20:03.761008+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: combined_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 129,171
#   Cached Inbound Tokens:   23,849,344
#   Outbound Tokens:         175,146
#   Total Tokens:            24,153,661
#   Financial Cost ($USD):   $0.1960
#   Wall Clock Duration:     1208.37s
#   Step Latencies (s):      [414.8, 763.6]
#   Role Execution Rounds:   combined_baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       33
#   Unit Tests Failed:       0
#   Line Coverage:           99.0%
#   Branch Coverage:         99.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
"""Package repository and dependency resolution value types and protocols."""

from __future__ import annotations
from typing import Collection, List, Mapping, Protocol, Set, Tuple
from dataclasses import dataclass

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
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        ...

    @operation
    def has_package(self, name: str) -> bool:
        ...

    @operation
    def all_packages(self) -> Set[str]:
        ...


@poly_type
class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    @operation
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 867abd613f82
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Concrete package repository and backtracking dependency solver."""

from __future__ import annotations
from typing import Collection, Dict, List, Optional, Set, Tuple
from functools import cmp_to_key

from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi


class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # Postcondition: store the release and keep releases sorted by descending precedence.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_core.VersionEngine)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(left.version, right.version)
            ),
            reverse=True,
        )

    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # Postcondition: yield a copy of the descending release list, or raise when absent.
        if name in self._packages:
            return list(self._packages[name])
        raise dependency_solver.PackageNotFoundError(
            f"Package '{name}' is not registered in the repository.", name
        )

    def has_package(self, name: str) -> bool:
        # Postcondition: membership reflects the registered package names.
        return name in self._packages

    def all_packages(self) -> Set[str]:
        # Postcondition: yield the set of all registered package names.
        return set(self._packages)


class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        # Sequencing: accumulate root constraints, then run MRV backtracking search.
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)
        accumulated: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        resolved = self._search(
            accumulated,
            assignment,
            derivation_steps,
            conflict_trail,
            conflicting_packages,
            repository,
            range_engine,
        )
        if not resolved:
            # Postcondition: unsatisfiable constraints raise the contracted conflict error.
            explanation = "; ".join(conflict_trail)
            raise dependency_solver.ResolutionConflictError(
                f"Dependency resolution failed: {explanation}",
                tuple(sorted(conflicting_packages)),
                explanation,
            )
        # Postcondition: compile the selected mapping and decision sequence.
        selected_versions = {
            name: release.version for name, release in assignment.items()
        }
        return dependency_solver.ResolutionOutcome(
            selected_versions, tuple(derivation_steps)
        )

    def _search(
        self,
        accumulated: Dict[str, List[Tuple[str, semver_range.VersionRange]]],
        assignment: Dict[str, dependency_solver.PackageRelease],
        derivation_steps: List[str],
        conflict_trail: List[str],
        conflicting_packages: Set[str],
        repository: dependency_solver.PackageRepository,
        range_engine: semver_range.RangeEngine,
    ) -> bool:
        # Sequencing: select the unassigned package with the fewest viable releases.
        unassigned = [name for name in accumulated if name not in assignment]
        if not unassigned:
            return True
        candidates: Dict[str, List[dependency_solver.PackageRelease]] = {}
        for name in unassigned:
            available: List[dependency_solver.PackageRelease]
            if repository.has_package(name):
                available = repository.get_releases(name)
            else:
                # Contract: absent packages contribute no candidates, never escaping errors.
                available = []
            candidates[name] = [
                release
                for release in available
                if all(
                    range_engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated[name]
                )
            ]
        selected_name = min(
            unassigned,
            key=lambda candidate_name: (
                len(candidates[candidate_name]),
                candidate_name,
            ),
        )
        options = candidates[selected_name]
        if not options:
            # Conflicts are recorded in the trail before backtracking.
            requesters = [requester for requester, _ in accumulated[selected_name]]
            conflicting_packages.add(selected_name)
            conflicting_packages.update(requesters)
            conflict_trail.append(
                f"No viable releases for '{selected_name}' satisfying constraints from {requesters}"
            )
            return False
        # Value ordering: explore candidates in descending precedence order.
        for release in options:
            assignment[selected_name] = release
            derivation_steps.append(
                f"Assign '{selected_name}' to {release.version}"
            )
            conflict_detected = False
            newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []
            for dependency in release.dependencies:
                if dependency.name in assignment:
                    # Forward checking: assigned releases must satisfy the requirement.
                    if not range_engine.satisfies(
                        assignment[dependency.name].version,
                        dependency.range_constraint,
                        False,
                    ):
                        conflict_detected = True
                        conflicting_packages.add(selected_name)
                        conflicting_packages.add(dependency.name)
                        conflict_trail.append(
                            f"Conflict: '{selected_name}' requires {dependency.name} {dependency.range_constraint}"
                        )
                        break
                else:
                    constraint_entry = (selected_name, dependency.range_constraint)
                    accumulated.setdefault(dependency.name, []).append(
                        constraint_entry
                    )
                    newly_added.append((dependency.name, constraint_entry))
            if not conflict_detected and self._search(
                accumulated,
                assignment,
                derivation_steps,
                conflict_trail,
                conflicting_packages,
                repository,
                range_engine,
            ):
                return True
            # Backtrack: undo the assignment, decision step, and merged constraints.
            for introduced_name, introduced_constraint in newly_added:
                accumulated[introduced_name].remove(introduced_constraint)
                if not accumulated[introduced_name]:
                    del accumulated[introduced_name]
            del assignment[selected_name]
            derivation_steps.pop()
        return False


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
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 31ac0a7c08b8
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""SemVer 2.0.0 value types, diagnostics, and parsing/comparison protocol."""

from __future__ import annotations
from typing import Protocol, Tuple
from dataclasses import dataclass
import enum

from support.lib.framework import data_type, operation, poly_type

# Requirements specified in semver_core.pyi


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __str__(self) -> str:
        # Contract: diagnostics render as the recorded message.
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
        # Postcondition: true exactly when pre-release identifiers are present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Postcondition: canonical SemVer 2.0.0 rendering of all components.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = text + "-" + ".".join(self.prerelease)
        if self.build:
            text = text + "+" + ".".join(self.build)
        return text

    def __str__(self) -> str:
        # Postcondition: string form is equivalent to format().
        return self.format()


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing and precedence comparison."""

    @operation
    def parse_version(self, text: str) -> Version:
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 96d770739f3d
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Concrete SemVer 2.0.0 parser and precedence comparison engine."""

from __future__ import annotations
import re
from typing import Optional

from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    def parse_version(self, text: str) -> semver_core.Version:
        # Precondition: text must match the SemVer 2.0.0 grammar.
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                f"Invalid semantic version: {text}", text
            )
        prerelease_text = match.group("prerelease")
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build_text = match.group("build")
        build = tuple(build_text.split(".")) if build_text else ()
        return semver_core.Version(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            prerelease,
            build,
        )

    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        # Postcondition: numeric components compare first, in major/minor/patch order.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return left - right
        # Postcondition: a normal version outranks a pre-release of the same triple.
        if v1.prerelease and not v2.prerelease:
            return -1
        if v2.prerelease and not v1.prerelease:
            return 1
        # Postcondition: compare pre-release identifiers position by position.
        for left_id, right_id in zip(v1.prerelease, v2.prerelease):
            if left_id == right_id:
                continue
            left_numeric = left_id.isdigit()
            right_numeric = right_id.isdigit()
            if left_numeric and right_numeric:
                return int(left_id) - int(right_id)
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left_id < right_id else 1
        # Postcondition: longer pre-release sequences outrank their common prefix.
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
# LAST_CLEANED: 2026-11-05T05:40:12Z
# LAST_CHANGED: 2026-11-05T05:40:12Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: e7487c6052e1
# COVERAGE_AUDIT: 2026-11-05T05:40:12Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:12Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:12Z
# QA_AUDIT: 2026-11-05T05:40:12Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Version range value type, diagnostics, and parse/match protocol."""

from __future__ import annotations
from typing import Protocol
from dataclasses import dataclass

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
        # Postcondition: string form is the stored range text.
        return self.raw_text


@poly_type
class RangeEngine(Protocol):
    """Provides version range parsing and constraint matching."""

    @operation
    def parse_range(self, text: str) -> VersionRange:
        ...

    @operation
    def satisfies(self, version: semver_core.Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: c4f641f2b9b0
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Concrete version range parsing and constraint matching engine."""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

_NUMERIC = re.compile(r"^(?:0|[1-9]\d*)$")
_PRERELEASE_ID = re.compile(r"^(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)$")
_BUILD_ID = re.compile(r"^[0-9a-zA-Z-]+$")
_HYPHEN = re.compile(r"^(\S+)\s+-\s+(\S+)$")
_WILDCARDS = frozenset({"*", "x", "X"})
_OPERATORS = ("<=", ">=", "==", "!=", "<", ">", "=", "^", "~")


@dataclass(frozen=True)
class _Pattern:
    """Parsed version pattern: numeric components with an optional trailing wildcard."""

    parts: Tuple[int, ...]
    wildcard: bool
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()


@dataclass(frozen=True)
class _Bound:
    """Single clause predicate over a semantic version."""

    op: str
    version: semver_core.Version
    upper: Optional[semver_core.Version] = None


def _invalid(text: str, raw_range: str) -> semver_range.InvalidRangeError:
    return semver_range.InvalidRangeError(
        f"Invalid version range '{text}'", raw_range
    )


def _parse_pattern(text: str, raw_range: str) -> _Pattern:
    if text in _WILDCARDS:
        return _Pattern((), True)
    body = text
    build: Tuple[str, ...] = ()
    if "+" in body:
        body, build_text = body.split("+", 1)
        build = tuple(build_text.split("."))
        for identifier in build:
            if _BUILD_ID.match(identifier) is None:
                raise _invalid(text, raw_range)
    prerelease: Tuple[str, ...] = ()
    if "-" in body:
        body, prerelease_text = body.split("-", 1)
        prerelease = tuple(prerelease_text.split("."))
        for identifier in prerelease:
            if _PRERELEASE_ID.match(identifier) is None:
                raise _invalid(text, raw_range)
    components = body.split(".")
    wildcard = components[-1] in _WILDCARDS
    numeric_components = components[:-1] if wildcard else components
    parts: List[int] = []
    for component in numeric_components:
        if _NUMERIC.match(component) is None:
            raise _invalid(text, raw_range)
        parts.append(int(component))
    if wildcard:
        if prerelease or build or len(parts) > 2:
            raise _invalid(text, raw_range)
        return _Pattern(tuple(parts), True)
    if len(parts) != 3:
        raise _invalid(text, raw_range)
    return _Pattern(tuple(parts), False, prerelease, build)


def _zero_version(pattern: _Pattern) -> semver_core.Version:
    major = pattern.parts[0] if len(pattern.parts) > 0 else 0
    minor = pattern.parts[1] if len(pattern.parts) > 1 else 0
    patch = pattern.parts[2] if len(pattern.parts) > 2 else 0
    return semver_core.Version(major, minor, patch)


def _full_version(pattern: _Pattern) -> semver_core.Version:
    return semver_core.Version(
        pattern.parts[0],
        pattern.parts[1],
        pattern.parts[2],
        pattern.prerelease,
        pattern.build,
    )


def _wildcard_upper(pattern: _Pattern) -> Optional[semver_core.Version]:
    if len(pattern.parts) == 0:
        return None
    if len(pattern.parts) == 1:
        return semver_core.Version(pattern.parts[0] + 1, 0, 0)
    return semver_core.Version(pattern.parts[0], pattern.parts[1] + 1, 0)


def _caret_upper(pattern: _Pattern) -> semver_core.Version:
    major, minor, patch = pattern.parts
    if major > 0:
        return semver_core.Version(major + 1, 0, 0)
    if minor > 0:
        return semver_core.Version(0, minor + 1, 0)
    return semver_core.Version(0, 0, patch + 1)


def _bounds_for(
    operator: Optional[str], target: str, raw_range: str
) -> List[_Bound]:
    pattern = _parse_pattern(target, raw_range)
    if operator is None or operator == "==" or operator == "=":
        if pattern.wildcard:
            if not pattern.parts:
                return []
            lower = _zero_version(pattern)
            upper = _wildcard_upper(pattern)
            return [_Bound("GE", lower), _Bound("LT", upper)] if upper else []
        return [_Bound("EQ", _full_version(pattern))]
    if operator == "!=":
        if pattern.wildcard:
            if not pattern.parts:
                raise _invalid(target, raw_range)
            upper = _wildcard_upper(pattern)
            return [_Bound("NOT_IN", _zero_version(pattern), upper)]
        return [_Bound("NE", _full_version(pattern))]
    if operator == "^":
        if pattern.wildcard:
            raise _invalid(target, raw_range)
        return [
            _Bound("GE", _full_version(pattern)),
            _Bound("LT", _caret_upper(pattern)),
        ]
    if operator == "~":
        if pattern.wildcard:
            raise _invalid(target, raw_range)
        full = _full_version(pattern)
        return [
            _Bound("GE", full),
            _Bound("LT", semver_core.Version(full.major, full.minor + 1, 0)),
        ]
    if pattern.wildcard:
        if not pattern.parts:
            raise _invalid(target, raw_range)
        lower = _zero_version(pattern)
        upper = _wildcard_upper(pattern)
        assert upper is not None
        if operator == ">=":
            return [_Bound("GE", lower)]
        if operator == ">":
            return [_Bound("GE", upper)]
        if operator == "<=":
            return [_Bound("LT", upper)]
        return [_Bound("LT", lower)]
    full = _full_version(pattern)
    if operator == ">=":
        return [_Bound("GE", full)]
    if operator == ">":
        return [_Bound("GT", full)]
    if operator == "<=":
        return [_Bound("LE", full)]
    return [_Bound("LT", full)]


def _expand_hyphen(
    lower_text: str, upper_text: str, raw_range: str
) -> List[_Bound]:
    lower_pattern = _parse_pattern(lower_text, raw_range)
    upper_pattern = _parse_pattern(upper_text, raw_range)
    bounds: List[_Bound] = []
    if lower_pattern.wildcard:
        if lower_pattern.parts:
            bounds.append(_Bound("GE", _zero_version(lower_pattern)))
    else:
        bounds.append(_Bound("GE", _full_version(lower_pattern)))
    if upper_pattern.wildcard:
        upper = _wildcard_upper(upper_pattern)
        if upper is not None:
            bounds.append(_Bound("LT", upper))
    else:
        bounds.append(_Bound("LE", _full_version(upper_pattern)))
    return bounds


def _expand_clause(clause: str, raw_range: str) -> List[_Bound]:
    hyphen = _HYPHEN.match(clause)
    if hyphen is not None:
        return _expand_hyphen(hyphen.group(1), hyphen.group(2), raw_range)
    bounds: List[_Bound] = []
    tokens = clause.split()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        operator: Optional[str] = None
        target = token
        for candidate in _OPERATORS:
            if token == candidate:
                if index + 1 >= len(tokens):
                    raise _invalid(clause, raw_range)
                operator = candidate
                target = tokens[index + 1]
                index += 2
                break
            if token.startswith(candidate) and len(token) > len(candidate):
                operator = candidate
                target = token[len(candidate):]
                index += 1
                break
        else:
            index += 1
        bounds.extend(_bounds_for(operator, target, raw_range))
    return bounds


def _compile_range(text: str) -> List[List[_Bound]]:
    stripped = text.strip()
    if not stripped:
        raise _invalid(text, text)
    if "," in stripped:
        raise _invalid(text, text)
    clauses: List[List[_Bound]] = []
    for raw_clause in stripped.split("||"):
        clause = raw_clause.strip()
        if not clause:
            raise _invalid(text, text)
        clauses.append(_expand_clause(clause, text))
    return clauses


def _prerelease_boundaries(clauses: List[List[_Bound]]) -> List[semver_core.Version]:
    boundaries: List[semver_core.Version] = []
    for clause in clauses:
        for bound in clause:
            boundaries.append(bound.version)
            if bound.upper is not None:
                boundaries.append(bound.upper)
    return boundaries


def _matches(
    engine: semver_core.VersionEngine,
    version: semver_core.Version,
    bound: _Bound,
) -> bool:
    comparison = engine.compare_precedence(version, bound.version)
    if bound.op == "EQ":
        return comparison == 0
    if bound.op == "NE":
        return comparison != 0
    if bound.op == "LT":
        return comparison < 0
    if bound.op == "LE":
        return comparison <= 0
    if bound.op == "GT":
        return comparison > 0
    if bound.op == "GE":
        return comparison >= 0
    if comparison < 0:
        return True
    return bound.upper is not None and engine.compare_precedence(
        version, bound.upper
    ) >= 0


class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    def parse_range(self, text: str) -> semver_range.VersionRange:
        # Postcondition: validate the expression, then store the trimmed range text.
        _compile_range(text)
        return semver_range.VersionRange(text.strip())

    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        engine = get_singleton(semver_core.VersionEngine)
        clauses = _compile_range(range_constraint.raw_text)
        # Postcondition: pre-release candidates require an explicit pre-release target.
        if version.is_prerelease and not include_prerelease:
            targets = _prerelease_boundaries(clauses)
            targeted = any(
                target.is_prerelease
                and (target.major, target.minor, target.patch)
                == (version.major, version.minor, version.patch)
                for target in targets
            )
            if not targeted:
                return False
        # Postcondition: match when every predicate in at least one clause holds.
        for clause in clauses:
            if all(_matches(engine, version, bound) for bound in clause):
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
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: f887db0b4e03
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---
