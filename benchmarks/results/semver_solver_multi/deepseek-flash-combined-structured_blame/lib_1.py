# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_123418_deepseek-flash_semver_solver_multi_combined
# Timestamp: 2026-11-08T12:34:18.167035+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 658,504
#   Cached Inbound Tokens:   65,424,896
#   Outbound Tokens:         477,246
#   Total Tokens:            66,560,646
#   Financial Cost ($USD):   $0.5814
#   Wall Clock Duration:     2454.66s
#   Step Latencies (s):      [321.2, 366.1, 65.3, 511.4, 100.9, 180.3, 22.9, 191.3, 202.1, 10.1, 181.4, 96.2, 259.0, 10.1, 421.5, 59.5, 78.9, 44.5, 10.1, 20.8, 20.9, 289.4, 12.3, 184.7, 53.3, 10.1, 20.8, 20.8, 256.3, 55.0, 53.0, 178.6, 10.1, 129.2, 20.7, 86.4, 107.6, 20.7, 75.6, 65.2, 20.7, 10.1]
#   Role Execution Rounds:   coverage: 5, lib: 4, pretense: 8, pretense_coverage: 6, pretense_qa: 9, qa: 6, test: 4 (Total: 42)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       43
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
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
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:40:45Z
# LAST_CHANGED: 2026-11-08T12:40:45Z
# CHANGE: Implement dependency solver interface: PackageNotFoundError/ResolutionConflictError dataclasses, frozen PackageDependency/PackageRelease/ResolutionOutcome records, PackageRepository and DependencySolver protocols with operation stubs.
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
from __future__ import annotations
from functools import cmp_to_key
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi

# A constraint records its requesting package name (None for root requirements).
_Constraint = Tuple[Optional[str], semver_range.VersionRange]


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Private backing state maps package names to descending releases.
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # Inserts the release and re-sorts the package release list descending
        # by version precedence using the version engine comparison.
        engine = get_singleton(semver_core.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        self._packages[release.name] = sorted(
            releases,
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(left.version, right.version)
            ),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # Raises the contracted error when the package name is missing.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository",
                name,
            )
        # Produces a shallow copy of the sorted release list.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # Reports membership of the name in the repository index.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # Produces the set of all registered package names.
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
        # Collaborators are resolved on demand via the lifecycle registry.
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        # Initializes the accumulated constraint mapping from root dependencies.
        accumulated: Dict[str, List[_Constraint]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                (None, dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_candidates(
            package_name: str,
            constraints: List[_Constraint],
        ) -> List[dependency_solver.PackageRelease]:
            # Unregistered packages absent from the repository have zero candidates,
            # so a missing package is reified into a resolution conflict instead of
            # letting the repository lookup error escape.
            if not repository.has_package(package_name):
                return []
            releases = repository.get_releases(package_name)
            # Candidate releases must satisfy every accumulated constraint.
            return [
                release
                for release in releases
                if all(
                    range_engine.satisfies(release.version, constraint, False)
                    for _, constraint in constraints
                )
            ]

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True

            # Minimum Remaining Values variable selection with lexical tie-breaking.
            candidate_map: Dict[str, List[dependency_solver.PackageRelease]] = {}
            for package_name in unassigned:
                candidate_map[package_name] = viable_candidates(
                    package_name, accumulated[package_name]
                )
            selected = min(
                unassigned,
                key=lambda package_name: (len(candidate_map[package_name]), package_name),
            )
            candidates = candidate_map[selected]

            # Detects unsatisfiable empty candidate intersections.
            if not candidates:
                requesters = [source for source, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(
                    source for source in requesters if source is not None
                )
                requesters_text = ', '.join(
                    source if source is not None else 'root' for source in requesters
                )
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters_text}"
                )
                return False

            # Explores candidate releases in descending version precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, int]] = []

                # Forward checking: merges declared dependencies into the constraints.
                for dependency in candidate.dependencies:
                    assigned = assignment.get(dependency.name)
                    if assigned is not None:
                        # An assigned package violating the requirement conflicts immediately.
                        if not range_engine.satisfies(
                            assigned.version, dependency.range_constraint, False
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{dependency.name}' "
                                f"{dependency.range_constraint.raw_text}, but "
                                f"{assigned.version} is assigned"
                            )
                            break
                    else:
                        constraint_list = accumulated.setdefault(dependency.name, [])
                        constraint_list.append((selected, dependency.range_constraint))
                        newly_added.append((dependency.name, len(constraint_list) - 1))

                if not conflict_detected and backtrack():
                    return True

                # Restores the previous constraint mappings and assignment on backtracking.
                for package_name, constraint_index in reversed(newly_added):
                    restored = accumulated[package_name]
                    del restored[constraint_index]
                    if not restored:
                        del accumulated[package_name]
                del assignment[selected]
                derivation_steps.pop()

            # Candidate options exhausted for this package without a viable release.
            return False

        if backtrack():
            # Compiles the selected release mapping and decision sequence into an outcome.
            selected_versions: Dict[str, semver_core.Version] = {
                package_name: release.version
                for package_name, release in assignment.items()
            }
            return dependency_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        # Search exhausted every branch: report the accumulated conflict trail.
        explanation = '; '.join(conflict_trail) if conflict_trail else 'dependencies are unsatisfiable'
        derivation_text = ' | '.join(derivation_steps) if derivation_steps else 'no decisions'
        raise dependency_solver.ResolutionConflictError(
            f"Unable to resolve dependency constraints: {explanation}",
            tuple(sorted(conflicting_packages)),
            f"{explanation}. Derivation: {derivation_text}",
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
# LAST_CLEANED: 2026-11-08T13:04:20Z
# LAST_CHANGED: 2026-11-08T12:45:54Z
# CHANGE: Prune duplicate PackageNotFoundError guard in viable_candidates: membership is established via has_package and releases are never removed, so the handler was unreachable per cov.unreachable_under_spec; missing packages still yield zero candidates and are reified into ResolutionConflictError without letting PackageNotFoundError escape.
# COVERAGE_AUDIT: 2026-11-08T12:47:50Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:04:20Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:04:07Z
# QA_AUDIT: 2026-11-08T12:46:28Z
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
        return len(self.prerelease) > 0

    def format(self) -> str:
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += '-' + '.'.join(self.prerelease)
        if self.build:
            text += '+' + '.'.join(self.build)
        return text

    def __str__(self) -> str:
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
# LAST_CLEANED: 2026-11-08T12:37:57Z
# LAST_CHANGED: 2026-11-08T12:37:57Z
# CHANGE: Implement SemVer interface: concrete non-frozen dataclass exceptions with message formatting, immutable Version with canonical format/str and is_prerelease, VersionEngine protocol with operation stubs.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 grammar: three numeric components without leading zeroes, optional
# dot-separated pre-release identifiers, and optional dot-separated build identifiers.
_VERSION_PATTERN = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)"
    r"\.(?P<minor>0|[1-9][0-9]*)"
    r"\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

_NUMERIC_IDENTIFIER_PATTERN = re.compile(r"^[0-9]+$")


def _is_numeric_identifier(identifier: str) -> bool:
    """Checks whether a pre-release identifier is composed solely of ASCII digits."""
    return _NUMERIC_IDENTIFIER_PATTERN.match(identifier) is not None


def _compare_prerelease_identifier(left: str, right: str) -> int:
    """Compares one pre-release identifier per SemVer 2.0.0 precedence rules."""
    left_numeric = _is_numeric_identifier(left)
    right_numeric = _is_numeric_identifier(right)
    if left_numeric and right_numeric:
        # Both numeric identifiers compare numerically.
        left_value = int(left)
        right_value = int(right)
        if left_value == right_value:
            return 0
        return -1 if left_value < right_value else 1
    if left_numeric:
        # Numeric identifiers always rank lower than alphanumeric identifiers.
        return -1
    if right_numeric:
        return 1
    # Both alphanumeric identifiers compare ASCII lexicographically.
    if left == right:
        return 0
    return -1 if left < right else 1


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        # Validates SemVer 2.0.0 grammar and numerical leading zero constraints.
        match = _VERSION_PATTERN.match(text)
        if match is None:
            # Grammar violations, including leading zeroes in numeric identifiers,
            # raise the contracted domain error.
            raise semver_core.InvalidVersionError(
                f"Invalid semantic version text: {text!r}",
                text,
            )

        prerelease_text = match.group("prerelease")
        build_text = match.group("build")
        # Produces an immutable Version record with parsed component tuples.
        return semver_core.Version(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=tuple(prerelease_text.split('.')) if prerelease_text else (),
            build=tuple(build_text.split('.')) if build_text else (),
        )

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        # Major, minor, and patch numbers compare numerically in sequence.
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1

        # A normal version ranks higher than a pre-release version.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # Pre-release segments compare position by position.
        for left, right in zip(v1.prerelease, v2.prerelease):
            result = _compare_prerelease_identifier(left, right)
            if result != 0:
                return result

        # A longer pre-release sequence ranks higher when the common prefix matches.
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

        # Build metadata is excluded entirely from precedence comparison.
        return 0


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
# LAST_CLEANED: 2026-11-08T13:06:54Z
# LAST_CHANGED: 2026-11-08T12:38:01Z
# CHANGE: Implement VersionEngine: SemVer 2.0.0 regex parsing with leading-zero rejection and InvalidVersionError, numeric component comparison, prerelease numeric/lexicographic ordering with numeric-lower-than-string and longer-sequence precedence, build metadata ignored.
# COVERAGE_AUDIT: 2026-11-08T12:45:08Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:06:54Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:06:42Z
# QA_AUDIT: 2026-11-08T12:44:55Z
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
        return self.raw_text


@poly_type
class RangeEngine(Protocol):
    """Provides version range parsing and constraint matching."""

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        ...

    @operation
    def satisfies(self, version: semver_core.Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:39:10Z
# LAST_CHANGED: 2026-11-08T12:39:10Z
# CHANGE: Implement range interface: InvalidRangeError dataclass, immutable VersionRange with raw text str, RangeEngine protocol operation stubs.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

# Wildcard placeholders accepted in a range bound.
_WILDCARD_TOKENS = ('*', 'x', 'X')

# Relational and prefix operators, with two-character operators matched first.
_OPERATOR_PREFIXES: Tuple[str, ...] = ('==', '!=', '<=', '>=', '=', '<', '>', '^', '~')

# SemVer 2.0.0 grammar used to validate full version bounds in range expressions.
_FULL_VERSION_PATTERN = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)"
    r"\.(?P<minor>0|[1-9][0-9]*)"
    r"\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

# Numeric range component without leading zeroes.
_NUMERIC_COMPONENT_PATTERN = re.compile(r"^(?:0|[1-9][0-9]*)$")

# One comparator in an expanded clause, paired with its boundary version.
_Comparator = Tuple[semver_core.ComparatorOp, semver_core.Version]


@dataclass(frozen=True)
class _ExactTarget:
    """Expansion boundaries of a full semantic version bound."""

    version: semver_core.Version


@dataclass(frozen=True)
class _WildcardTarget:
    """Expansion boundaries of a bounded wildcard bound (e.g. '1.x', '1.2.*')."""

    lower: semver_core.Version
    upper: semver_core.Version
    caret_upper: semver_core.Version
    tilde_upper: semver_core.Version


@dataclass(frozen=True)
class _UnboundedTarget:
    """Expansion boundaries of the unbounded wildcard bound ('*')."""


# A parsed range bound: exact version, bounded wildcard, or unbounded wildcard.
_Target = Union[_ExactTarget, _WildcardTarget, _UnboundedTarget]


def _wildcard_target(major: int, minor: Optional[int]) -> _Target:
    """Builds the expansion boundaries of a validated wildcard bound."""
    if minor is None:
        # Major-qualified wildcard (e.g. '1.x'): boundaries advance to the next major.
        lower = semver_core.Version(major, 0, 0)
        upper = semver_core.Version(major + 1, 0, 0)
        return _WildcardTarget(lower, upper, upper, upper)
    # Minor-qualified wildcard (e.g. '1.2.x'): the wildcard upper advances to the next minor.
    lower = semver_core.Version(major, minor, 0)
    upper = semver_core.Version(major, minor + 1, 0)
    # The caret upper advances at the first non-zero component.
    caret_upper = upper if major == 0 else semver_core.Version(major + 1, 0, 0)
    return _WildcardTarget(lower, upper, caret_upper, upper)


def _parse_target(text: str) -> Optional[_Target]:
    """Parses a full semantic version or wildcard bound, returning None when malformed."""
    full = _FULL_VERSION_PATTERN.match(text)
    if full is not None:
        prerelease_text = full.group("prerelease")
        build_text = full.group("build")
        return _ExactTarget(
            semver_core.Version(
                major=int(full.group("major")),
                minor=int(full.group("minor")),
                patch=int(full.group("patch")),
                prerelease=tuple(prerelease_text.split('.')) if prerelease_text else (),
                build=tuple(build_text.split('.')) if build_text else (),
            )
        )

    parts = text.split('.')
    if not parts or len(parts) > 3:
        return None
    components: List[Optional[int]] = []
    saw_wildcard = False
    for index, part in enumerate(parts):
        if part in _WILDCARD_TOKENS:
            # A wildcard cannot be followed by another component group.
            if index == 0 and len(parts) > 1:
                return None
            saw_wildcard = True
            components.append(None)
            continue
        if saw_wildcard or _NUMERIC_COMPONENT_PATTERN.match(part) is None:
            return None
        components.append(int(part))
    if not saw_wildcard:
        # Bare partial versions lacking wildcard characters are prohibited.
        return None
    while len(components) < 3:
        components.append(None)
    major = components[0]
    if major is None:
        # The only fully wildcard bound accepted by the grammar is '*'.
        return _UnboundedTarget()
    return _wildcard_target(major, components[1])


def _expand_unbounded(operator: str) -> List[List[_Comparator]]:
    """Expands the unbounded wildcard bound across the closed operator set."""
    # A wildcard matching every version: monotone operators include all versions while
    # '!=' and the exclusive strict operators exclude every version.
    if operator in ('!=', '<', '>'):
        return []
    return [[]]


def _expand_wildcard(operator: str, target: _WildcardTarget) -> List[List[_Comparator]]:
    """Expands a bounded wildcard bound into disjunctive comparator alternatives."""
    lower: List[_Comparator] = [(semver_core.ComparatorOp.GE, target.lower)]
    if operator == '!=':
        # '!=1.x' expands to the union below the lower and above the upper boundary.
        return [
            [(semver_core.ComparatorOp.LT, target.lower)],
            [(semver_core.ComparatorOp.GE, target.upper)],
        ]
    if operator == '^':
        return [lower + [(semver_core.ComparatorOp.LT, target.caret_upper)]]
    if operator == '~':
        return [lower + [(semver_core.ComparatorOp.LT, target.tilde_upper)]]
    if operator == '>':
        return [[(semver_core.ComparatorOp.GE, target.upper)]]
    if operator == '<=':
        return [[(semver_core.ComparatorOp.LT, target.upper)]]
    if operator == '<':
        return [[(semver_core.ComparatorOp.LT, target.lower)]]
    if operator == '>=':
        return [lower]
    # '', '=' and '==': the wildcard expands to its inclusive/exclusive boundary pair.
    return [lower + [(semver_core.ComparatorOp.LT, target.upper)]]


def _full_caret_upper_bound(version: semver_core.Version) -> semver_core.Version:
    """Produces the exclusive upper boundary of a caret range on a full version."""
    if version.major > 0:
        return semver_core.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_core.Version(0, version.minor + 1, 0)
    if version.patch > 0:
        return semver_core.Version(0, 0, version.patch + 1)
    return semver_core.Version(0, 0, 1)


def _full_tilde_upper_bound(version: semver_core.Version) -> semver_core.Version:
    """Produces the exclusive upper boundary of a tilde range on a full version."""
    return semver_core.Version(version.major, version.minor + 1, 0)


def _expand_version(operator: str, target: _ExactTarget) -> List[List[_Comparator]]:
    """Expands a full version bound into disjunctive comparator alternatives."""
    version = target.version
    if operator == '!=':
        return [[(semver_core.ComparatorOp.NE, version)]]
    if operator == '>=':
        return [[(semver_core.ComparatorOp.GE, version)]]
    if operator == '>':
        return [[(semver_core.ComparatorOp.GT, version)]]
    if operator == '<=':
        return [[(semver_core.ComparatorOp.LE, version)]]
    if operator == '<':
        return [[(semver_core.ComparatorOp.LT, version)]]
    if operator == '^':
        # The caret upper advances at the first non-zero component.
        return [
            [
                (semver_core.ComparatorOp.GE, version),
                (semver_core.ComparatorOp.LT, _full_caret_upper_bound(version)),
            ]
        ]
    if operator == '~':
        # The tilde upper advances at the next minor version.
        return [
            [
                (semver_core.ComparatorOp.GE, version),
                (semver_core.ComparatorOp.LT, _full_tilde_upper_bound(version)),
            ]
        ]
    # '', '=' and '==': exact version equality.
    return [[(semver_core.ComparatorOp.EQ, version)]]


def _expand_target(operator: str, target: _Target) -> List[List[_Comparator]]:
    """Dispatches expansion to unbounded, wildcard, or full version algebra."""
    if isinstance(target, _UnboundedTarget):
        return _expand_unbounded(operator)
    if isinstance(target, _WildcardTarget):
        return _expand_wildcard(operator, target)
    return _expand_version(operator, target)


def _target_lower_bound(target: Union[_ExactTarget, _WildcardTarget]) -> semver_core.Version:
    """Produces the inclusive lower boundary of a bounded range target."""
    if isinstance(target, _WildcardTarget):
        return target.lower
    return target.version


def _expand_hyphen(
    lower_target: _Target,
    upper_target: _Target,
) -> List[List[_Comparator]]:
    """Expands a hyphen range into paired inclusive/exclusive comparator inequalities."""
    comparators: List[_Comparator] = []
    if not isinstance(lower_target, _UnboundedTarget):
        comparators.append((semver_core.ComparatorOp.GE, _target_lower_bound(lower_target)))
    if not isinstance(upper_target, _UnboundedTarget):
        if isinstance(upper_target, _WildcardTarget):
            comparators.append((semver_core.ComparatorOp.LT, upper_target.upper))
        else:
            comparators.append((semver_core.ComparatorOp.LE, upper_target.version))
    return [comparators]


def _split_operator(token: str) -> Tuple[Optional[str], str]:
    """Splits a comparator token into its operator prefix and target remainder."""
    for prefix in _OPERATOR_PREFIXES:
        if token.startswith(prefix):
            return prefix, token[len(prefix):]
    return None, token


def _validate_clause(clause: str, raw_range: str) -> None:
    """Validates one union clause, raising InvalidRangeError on malformed syntax."""
    # Empty and whitespace-only clauses are rejected by parse_range before
    # per-clause validation, so the token list is always non-empty here.
    tokens = clause.split()
    if '-' in tokens:
        # Hyphen ranges connect exactly two bounds and admit no other comparators.
        if len(tokens) != 3 or tokens[1] != '-':
            raise semver_range.InvalidRangeError(
                f"Malformed hyphen range clause: {clause!r}",
                raw_range,
            )
        if _parse_target(tokens[0]) is None or _parse_target(tokens[2]) is None:
            raise semver_range.InvalidRangeError(
                f"Malformed hyphen range bounds: {clause!r}",
                raw_range,
            )
        return

    index = 0
    while index < len(tokens):
        token = tokens[index]
        operator, remainder = _split_operator(token)
        if operator is None:
            target_text = token
            index += 1
        elif remainder == '':
            # Operators may be separated from their target by whitespace.
            if index + 1 >= len(tokens):
                raise semver_range.InvalidRangeError(
                    f"Comparator operator without a target version: {clause!r}",
                    raw_range,
                )
            target_text = tokens[index + 1]
            index += 2
        else:
            target_text = remainder
            index += 1
        if _parse_target(target_text) is None:
            raise semver_range.InvalidRangeError(
                f"Malformed version bound {target_text!r} in range: {raw_range!r}",
                raw_range,
            )


def _compile_clause(clause: str) -> List[List[_Comparator]]:
    """Compiles a validated clause into disjunctive comparator alternatives."""
    tokens = clause.split()
    if not tokens:  # unreachable (assumption: parse_range rejected empty clauses)
        return []

    if '-' in tokens:
        lower_target = _parse_target(tokens[0])
        upper_target = _parse_target(tokens[2])
        if lower_target is None or upper_target is None:  # unreachable (assumption: parse_range validated hyphen bounds)
            return []
        return _expand_hyphen(lower_target, upper_target)

    alternatives: List[List[_Comparator]] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        operator, remainder = _split_operator(token)
        if operator is None:
            target_text = token
            operator = ''
            index += 1
        elif remainder == '':
            target_text = tokens[index + 1]
            index += 2
        else:
            target_text = remainder
            index += 1
        target = _parse_target(target_text)
        if target is None:  # unreachable (assumption: parse_range validated comparator targets)
            return []
        expanded = _expand_target(operator, target)
        combined: List[List[_Comparator]] = []
        for base in alternatives:
            for alternative in expanded:
                combined.append(base + alternative)
        alternatives = combined
        if not alternatives:
            return []
    return alternatives


def _alternative_matches(
    version: semver_core.Version,
    alternative: List[_Comparator],
    engine: semver_core.VersionEngine,
) -> bool:
    """Evaluates a candidate version against every comparator in one alternative."""
    for operator, boundary in alternative:
        comparison = engine.compare_precedence(version, boundary)
        if operator is semver_core.ComparatorOp.EQ:
            if comparison != 0:
                return False
        elif operator is semver_core.ComparatorOp.NE:
            if comparison == 0:
                return False
        elif operator is semver_core.ComparatorOp.LT:
            if comparison >= 0:
                return False
        elif operator is semver_core.ComparatorOp.LE:
            if comparison > 0:
                return False
        elif operator is semver_core.ComparatorOp.GT:
            if comparison <= 0:
                return False
        elif operator is semver_core.ComparatorOp.GE:
            if comparison < 0:
                return False
    return True


def _targets_prerelease(version: semver_core.Version, alternative: List[_Comparator]) -> bool:
    """Detects whether a comparator set explicitly targets the candidate pre-release."""
    for _, boundary in alternative:
        if (
            boundary.prerelease
            and boundary.major == version.major
            and boundary.minor == version.minor
            and boundary.patch == version.patch
        ):
            return True
    return False


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        # Trims surrounding whitespace and stores the trimmed expression.
        trimmed = text.strip()
        if not trimmed:
            raise semver_range.InvalidRangeError(
                "Version range text must not be empty",
                text,
            )
        # Commas are not permitted as comparator delimiters.
        if ',' in trimmed:
            raise semver_range.InvalidRangeError(
                f"Commas are not permitted in version range: {text!r}",
                text,
            )

        clauses = trimmed.split('||')
        for clause in clauses:
            stripped_clause = clause.strip()
            if not stripped_clause:
                raise semver_range.InvalidRangeError(
                    f"Version range contains an empty union clause: {text!r}",
                    text,
                )
            _validate_clause(stripped_clause, text)

        return semver_range.VersionRange(trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Tests the candidate against each union clause using the version engine.
        engine = get_singleton(semver_core.VersionEngine)
        for clause in range_constraint.raw_text.split('||'):
            for alternative in _compile_clause(clause.strip()):
                if not _alternative_matches(version, alternative, engine):
                    continue
                if include_prerelease or not version.is_prerelease:
                    return True
                # Pre-release candidates match only when the range explicitly targets
                # a pre-release with the same major, minor, and patch numbers.
                if _targets_prerelease(version, alternative):
                    return True
        # All clauses failed satisfaction.
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
# LAST_CLEANED: 2026-11-08T13:15:08Z
# LAST_CHANGED: 2026-11-08T13:00:48Z
# CHANGE: Prune the unreachable empty-clause token guard in _validate_clause: empty and whitespace-only clauses are rejected by parse_range before per-clause validation, so the token list is always non-empty there; documented the invariant in a comment instead of a dead raise.
# COVERAGE_AUDIT: 2026-11-08T13:01:33Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:15:08Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:14:53Z
# QA_AUDIT: 2026-11-08T13:01:19Z
# --- END AUTOFAB METADATA ---
