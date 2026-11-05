# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_164946_deepseek-flash_semver_solver_multi_baseline
# Timestamp: 2026-11-05T16:49:46.057372+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 59,615
#   Cached Inbound Tokens:   4,124,283
#   Outbound Tokens:         119,137
#   Total Tokens:            4,303,035
#   Financial Cost ($USD):   $0.0928
#   Wall Clock Duration:     661.02s
#   Step Latencies (s):      [640.6]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       28
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
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
        # MUST register the package release into the repository.
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        # MUST yield releases ordered by descending version precedence; raises PackageNotFoundError when absent.
        ...

    @operation
    def has_package(self, name: str) -> bool:
        # True exactly when package name exists in the repository.
        ...

    @operation
    def all_packages(self) -> Set[str]:
        # MUST produce the set of all registered package names.
        ...


@poly_type
class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    @operation
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        # MUST produce a highest-precedence mutually compatible assignment or raise ResolutionConflictError.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:00:47Z
# LAST_CHANGED: 2026-11-05T17:00:47Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 97e7f842aed7
# COVERAGE_AUDIT: 2026-11-05T17:00:47Z
# QA_AUDIT: 2026-11-05T17:00:47Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Backing store maps each package name to its release list.
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # POSTCONDITION: the release is stored and its list re-ordered by descending precedence.
        engine = get_singleton(semver_core.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        position = 0
        while (
            position < len(releases)
            and engine.compare_precedence(releases[position].version, release.version) >= 0
        ):
            position += 1
        releases.insert(position, release)

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # PRECONDITION: unknown names MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                f"Package not registered: {name}",
                package_name=name,
            )
        # POSTCONDITION: yields a shallow copy of the precedence-ordered release list.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # POSTCONDITION: True exactly when the package exists in the repository.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # POSTCONDITION: the set of all registered package names.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        # Accumulated constraints: package -> [(requesting package, range constraint)].
        constraints: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(package: str) -> List[dependency_solver.PackageRelease]:
            # Missing packages contribute zero candidates instead of surfacing PackageNotFoundError.
            try:
                available = repository.get_releases(package)
            except dependency_solver.PackageNotFoundError:
                available = []
            return [
                release
                for release in available
                if all(
                    range_engine.satisfies(release.version, constraint, False)
                    for _, constraint in constraints[package]
                )
            ]

        def backtrack() -> bool:
            unassigned = [package for package in constraints if package not in assignment]
            if not unassigned:
                return True
            candidate_map: Dict[str, List[dependency_solver.PackageRelease]] = {
                package: viable_releases(package) for package in unassigned
            }
            # Minimum Remaining Values selection with lexical tie-breaking.
            selected = min(
                unassigned,
                key=lambda package: (len(candidate_map[package]), package),
            )
            candidates = candidate_map[selected]
            if not candidates:
                requesters = [source for source, _ in constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # Value ordering: releases arrive in descending precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict = False
                added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # Forward check: reject an assigned version that violates the requirement.
                        if not range_engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} {dependency.range_constraint}"
                            )
                            break
                    else:
                        # Merge the new requirement into the accumulated constraints.
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(entry)
                        added.append((dependency.name, entry))
                if not conflict and backtrack():
                    return True
                # Undo this branch: restore constraints, assignment, and derivation trace.
                for package_name, entry in added:
                    constraints[package_name].remove(entry)
                    if not constraints[package_name]:
                        del constraints[package_name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if backtrack():
            selected_versions = {
                name: release.version for name, release in assignment.items()
            }
            return dependency_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )
        explanation = "\n".join(conflict_trail)
        raise dependency_solver.ResolutionConflictError(
            "Dependency resolution failed",
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
# LAST_CLEANED: 2026-11-05T17:00:47Z
# LAST_CHANGED: 2026-11-05T17:00:47Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 4b4e8355a16c
# COVERAGE_AUDIT: 2026-11-05T17:00:47Z
# QA_AUDIT: 2026-11-05T17:00:47Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum
from support.lib.framework import data_type, operation, poly_type

# Requirements specified in semver_core.pyi


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
        # Invariant: a version is a prerelease exactly when it carries prerelease identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Canonical form: core numbers, optional dash-prerelease, optional plus-build.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # MUST be equivalent to format().
        return self.format()


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing and precedence comparison."""

    @operation
    def parse_version(self, text: str) -> Version:
        # Parses text according to the SemVer 2.0.0 grammar; raises InvalidVersionError on violation.
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # Negative when v1 < v2, zero when equal, positive when v1 > v2 under SemVer 2.0.0 rules.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:00:47Z
# LAST_CHANGED: 2026-11-05T17:00:47Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9ec9cef307d5
# COVERAGE_AUDIT: 2026-11-05T17:00:47Z
# QA_AUDIT: 2026-11-05T17:00:47Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations
import re
from typing import Optional, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 grammar: three dot-separated numeric components without leading zeroes,
# an optional dash-prefixed prerelease, and an optional plus-prefixed build suffix.
_VERSION_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?",
    re.ASCII,
)


def _compare_prerelease_ids(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Compares prerelease identifier sequences under SemVer 2.0.0 precedence rules."""
    for left_id, right_id in zip(left, right):
        if left_id == right_id:
            continue
        left_numeric = left_id.isdigit()
        right_numeric = right_id.isdigit()
        # Numeric identifiers always rank below alphanumeric identifiers.
        if left_numeric and right_numeric:
            return 1 if int(left_id) > int(right_id) else -1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        # Alphanumeric identifiers compare in ASCII lexicographic order.
        return 1 if left_id > right_id else -1
    # A larger set of identical-prefixed fields has higher precedence.
    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        # PRECONDITION: grammar or leading-zero violations MUST raise InvalidVersionError.
        match = _VERSION_PATTERN.fullmatch(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                f"Invalid semantic version: {text}",
                raw_text=text,
            )
        # POSTCONDITION: valid text yields major, minor, patch, prerelease, and build components.
        major_text, minor_text, patch_text, prerelease_text, build_text = match.groups()
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build = tuple(build_text.split(".")) if build_text else ()
        return semver_core.Version(
            major=int(major_text),
            minor=int(minor_text),
            patch=int(patch_text),
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
        # Numeric components dominate precedence in sequence.
        if v1.major != v2.major:
            return 1 if v1.major > v2.major else -1
        if v1.minor != v2.minor:
            return 1 if v1.minor > v2.minor else -1
        if v1.patch != v2.patch:
            return 1 if v1.patch > v2.patch else -1
        # Normal releases rank higher than prereleases sharing the same core numbers.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        return _compare_prerelease_ids(v1.prerelease, v2.prerelease)


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
# LAST_CLEANED: 2026-11-05T17:00:47Z
# LAST_CHANGED: 2026-11-05T17:00:47Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: a186debe8f04
# COVERAGE_AUDIT: 2026-11-05T17:00:47Z
# QA_AUDIT: 2026-11-05T17:00:47Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
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
        # MUST return the raw range text representation.
        return self.raw_text


@poly_type
class RangeEngine(Protocol):
    """Provides version range parsing and constraint matching."""

    @operation
    def parse_range(self, text: str) -> VersionRange:
        # Parses a range expression; raises InvalidRangeError on malformed syntax.
        ...

    @operation
    def satisfies(self, version: semver_core.Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        # True exactly when version satisfies range_constraint under the contracted prerelease rules.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:00:47Z
# LAST_CHANGED: 2026-11-05T17:00:47Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 0b9d48b61728
# COVERAGE_AUDIT: 2026-11-05T17:00:47Z
# QA_AUDIT: 2026-11-05T17:00:47Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations
import re
from typing import Any, List, Optional, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

_VERSION_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?",
    re.ASCII,
)

_WILDCARD_TOKENS = ("*", "x", "X")

# A compiled comparison is (operator, lower bound, upper bound).  The "outside"
# operator treats the bounds as an excluded half-open interval.
_Comparison = Tuple[str, semver_core.Version, semver_core.Version]


def _precedence_key(version: semver_core.Version) -> Tuple[Any, ...]:
    """Builds a total-order key honoring SemVer 2.0.0 precedence rules."""
    if version.prerelease:
        return (
            version.major,
            version.minor,
            version.patch,
            0,
            tuple(
                (0, int(part)) if part.isdigit() else (1, part)
                for part in version.prerelease
            ),
        )
    return (version.major, version.minor, version.patch, 1)


def _compare(left: semver_core.Version, right: semver_core.Version) -> int:
    left_key = _precedence_key(left)
    right_key = _precedence_key(right)
    if left_key == right_key:
        return 0
    return 1 if left_key > right_key else -1


def _same_core(left: semver_core.Version, right: semver_core.Version) -> bool:
    return left.major == right.major and left.minor == right.minor and left.patch == right.patch


def _numeric(text: str, raw_range: str) -> int:
    # PRECONDITION: wildcard numeric components must be canonical non-negative integers.
    if not text.isdigit() or (len(text) > 1 and text[0] == "0"):
        raise semver_range.InvalidRangeError(
            f"Invalid numeric identifier '{text}' in range '{raw_range}'",
            raw_range=raw_range,
        )
    return int(text)


def _parse_version(text: str, raw_range: str) -> semver_core.Version:
    match = _VERSION_PATTERN.fullmatch(text)
    if match is None:
        raise semver_range.InvalidRangeError(
            f"Invalid version '{text}' in range '{raw_range}'",
            raw_range=raw_range,
        )
    major_text, minor_text, patch_text, prerelease_text, build_text = match.groups()
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build = tuple(build_text.split(".")) if build_text else ()
    return semver_core.Version(
        major=int(major_text),
        minor=int(minor_text),
        patch=int(patch_text),
        prerelease=prerelease,
        build=build,
    )


def _wildcard_bounds(
    text: str,
    raw_range: str,
) -> Optional[Tuple[Optional[int], Optional[int]]]:
    parts = text.split(".")
    if len(parts) == 1 and parts[0] in _WILDCARD_TOKENS:
        return (None, None)
    if len(parts) == 2 and parts[1] in _WILDCARD_TOKENS:
        return (_numeric(parts[0], raw_range), None)
    if len(parts) == 3 and parts[2] in _WILDCARD_TOKENS:
        return (_numeric(parts[0], raw_range), _numeric(parts[1], raw_range))
    return None


def _wildcard_range(
    bounds: Tuple[Optional[int], Optional[int]],
) -> Optional[Tuple[semver_core.Version, semver_core.Version]]:
    major, minor = bounds
    if major is None:
        return None
    if minor is None:
        return (
            semver_core.Version(major, 0, 0),
            semver_core.Version(major + 1, 0, 0),
        )
    return (
        semver_core.Version(major, minor, 0),
        semver_core.Version(major, minor + 1, 0),
    )


def _caret_upper(version: semver_core.Version) -> semver_core.Version:
    if version.major > 0:
        return semver_core.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_core.Version(0, version.minor + 1, 0)
    return semver_core.Version(0, 0, version.patch + 1)


def _compile_wildcard(
    operator: Optional[str],
    bounds: Tuple[Optional[int], Optional[int]],
    raw_range: str,
) -> List[_Comparison]:
    wildcard_range = _wildcard_range(bounds)
    if operator in (None, "=", "=="):
        if wildcard_range is None:
            return []
        lower, upper = wildcard_range
        return [(">=", lower, lower), ("<", upper, upper)]
    # Caret and tilde prefixes require a fully specified version, never a wildcard.
    if operator in ("^", "~"):
        raise semver_range.InvalidRangeError(
            f"Unsupported prefix '{operator}' over wildcard in range '{raw_range}'",
            raw_range=raw_range,
        )
    if wildcard_range is None:
        raise semver_range.InvalidRangeError(
            f"Unsupported comparator '{operator}' over wildcard in range '{raw_range}'",
            raw_range=raw_range,
        )
    lower, upper = wildcard_range
    if operator == "<":
        return [("<", lower, lower)]
    if operator == "<=":
        return [("<", upper, upper)]
    if operator == ">":
        return [(">=", upper, upper)]
    if operator == "!=":
        return [("outside", lower, upper)]
    return [(">=", lower, lower)]


def _compile_atom(
    operator: Optional[str],
    target: str,
    raw_range: str,
) -> List[_Comparison]:
    bounds = _wildcard_bounds(target, raw_range)
    if bounds is not None:
        return _compile_wildcard(operator, bounds, raw_range)
    version = _parse_version(target, raw_range)
    if operator in (None, "=", "=="):
        return [("==", version, version)]
    if operator == "!=":
        return [("!=", version, version)]
    if operator == "<":
        return [("<", version, version)]
    if operator == "<=":
        return [("<=", version, version)]
    if operator == ">":
        return [(">", version, version)]
    if operator == ">=":
        return [(">=", version, version)]
    if operator == "^":
        upper = _caret_upper(version)
        return [(">=", version, version), ("<", upper, upper)]
    # The only remaining prefix operator is tilde.
    upper = semver_core.Version(version.major, version.minor + 1, 0)
    return [(">=", version, version), ("<", upper, upper)]


def _split_operator(token: str) -> Tuple[Optional[str], str]:
    for prefix in (">=", "<=", "==", "!="):
        if token.startswith(prefix):
            return prefix, token[len(prefix):]
    for prefix in (">", "<", "=", "^", "~"):
        if token.startswith(prefix):
            return prefix, token[len(prefix):]
    return None, token


def _compile_clause(clause: str, raw_range: str) -> List[_Comparison]:
    parts = clause.split()
    # A hyphen range is exactly lower, separator, upper.
    if len(parts) == 3 and parts[1] == "-":
        lower = _parse_version(parts[0], raw_range)
        upper = _parse_version(parts[2], raw_range)
        return [(">=", lower, lower), ("<=", upper, upper)]
    comparisons: List[_Comparison] = []
    index = 0
    while index < len(parts):
        operator, target = _split_operator(parts[index])
        if target == "":
            # Whitespace is permitted between an operator and its target.
            index += 1
            if index >= len(parts):
                raise semver_range.InvalidRangeError(
                    f"Dangling operator in range '{raw_range}'",
                    raw_range=raw_range,
                )
            target = parts[index]
        comparisons.extend(_compile_atom(operator, target, raw_range))
        index += 1
    return comparisons


def _compile_range(text: str) -> List[List[_Comparison]]:
    trimmed = text.strip()
    if not trimmed or "," in trimmed:
        raise semver_range.InvalidRangeError(
            f"Invalid range expression '{text}'",
            raw_range=text,
        )
    clauses: List[List[_Comparison]] = []
    for chunk in trimmed.split("||"):
        clause_text = chunk.strip()
        if not clause_text:
            raise semver_range.InvalidRangeError(
                f"Empty union clause in range '{text}'",
                raw_range=text,
            )
        clauses.append(_compile_clause(clause_text, text))
    return clauses


def _matches(comparison: _Comparison, candidate: semver_core.Version) -> bool:
    operator, lower, upper = comparison
    if operator == "outside":
        return _compare(candidate, lower) < 0 or _compare(candidate, upper) >= 0
    ordering = _compare(candidate, lower)
    if operator == "<":
        return ordering < 0
    if operator == "<=":
        return ordering <= 0
    if operator == ">":
        return ordering > 0
    if operator == ">=":
        return ordering >= 0
    if operator == "==":
        return ordering == 0
    return ordering != 0


def _targets_prerelease(
    comparison: _Comparison,
    candidate: semver_core.Version,
) -> bool:
    _, lower, upper = comparison
    if lower.prerelease and _same_core(lower, candidate):
        return True
    return bool(upper.prerelease) and _same_core(upper, candidate)


def _clause_matches(clause: List[_Comparison], candidate: semver_core.Version) -> bool:
    for comparison in clause:
        if not _matches(comparison, candidate):
            return False
    return True


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        # PRECONDITION: malformed syntax MUST raise InvalidRangeError.
        _compile_range(text)
        # POSTCONDITION: the trimmed expression is retained verbatim.
        return semver_range.VersionRange(raw_text=text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        clauses = _compile_range(range_constraint.raw_text)
        for clause in clauses:
            if _clause_matches(clause, version):
                # POSTCONDITION: prereleases match only an explicitly targeted prerelease.
                if not version.is_prerelease or include_prerelease:
                    return True
                if any(_targets_prerelease(comparison, version) for comparison in clause):
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
# LAST_CLEANED: 2026-11-05T17:00:47Z
# LAST_CHANGED: 2026-11-05T17:00:47Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 576bdacdf03d
# COVERAGE_AUDIT: 2026-11-05T17:00:47Z
# QA_AUDIT: 2026-11-05T17:00:47Z
# --- END AUTOFAB METADATA ---
