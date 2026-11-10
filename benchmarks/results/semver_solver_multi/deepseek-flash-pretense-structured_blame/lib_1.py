# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_123423_deepseek-flash_semver_solver_multi_pretense
# Timestamp: 2026-11-08T12:34:23.931311+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 393,150
#   Cached Inbound Tokens:   52,219,392
#   Outbound Tokens:         347,440
#   Total Tokens:            52,959,982
#   Financial Cost ($USD):   $0.4241
#   Wall Clock Duration:     2113.58s
#   Step Latencies (s):      [515.0, 755.5, 73.1, 340.7, 411.7, 20.6, 98.8, 117.8, 20.7, 109.0, 20.6, 307.3, 12.2, 203.6, 75.9, 20.7, 162.0, 10.1, 74.9, 20.6, 96.1, 10.1]
#   Role Execution Rounds:   lib: 3, pretense: 5, pretense_coverage: 5, pretense_qa: 9 (Total: 22)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       6
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
        # Requirements specified by dependency_solver.PackageRepository.register_package.
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        # Requirements specified by dependency_solver.PackageRepository.get_releases.
        ...

    @operation
    def has_package(self, name: str) -> bool:
        # Requirements specified by dependency_solver.PackageRepository.has_package.
        ...

    @operation
    def all_packages(self) -> Set[str]:
        # Requirements specified by dependency_solver.PackageRepository.all_packages.
        ...


@poly_type
class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    @operation
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        # Requirements specified by dependency_solver.DependencySolver.resolve.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:43:06Z
# LAST_CHANGED: 2026-11-08T12:43:06Z
# CHANGE: Implement PackageNotFoundError and ResolutionConflictError as mutable dataclass exceptions with structured attributes, concretely realize PackageDependency, PackageRelease, ResolutionOutcome frozen records, and declare PackageRepository/DependencySolver protocol stubs with framework decorators.
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi

# An accumulated requirement: (requesting package name, required range constraint).
_Requirement = Tuple[str, semver_range.VersionRange]


def _insert_descending(
    ordered: List[dependency_solver.PackageRelease],
    release: dependency_solver.PackageRelease,
    engine: semver_core.VersionEngine,
) -> None:
    # Keeps a release list ordered by version precedence descending.
    index = 0
    while index < len(ordered) and engine.compare_precedence(ordered[index].version, release.version) >= 0:
        index += 1
    ordered.insert(index, release)


def _order_descending(
    releases: Sequence[dependency_solver.PackageRelease],
    engine: semver_core.VersionEngine,
) -> List[dependency_solver.PackageRelease]:
    # Value ordering: candidate releases are explored by version precedence descending.
    ordered: List[dependency_solver.PackageRelease] = []
    for release in releases:
        _insert_descending(ordered, release, engine)
    return ordered


def _viable_releases(
    name: str,
    requirements: Sequence[_Requirement],
    repository: dependency_solver.PackageRepository,
    range_engine: semver_range.RangeEngine,
    version_engine: semver_core.VersionEngine,
) -> List[dependency_solver.PackageRelease]:
    # Membership guard: unregistered packages evaluate to zero candidate releases, so the
    # repository lookup below cannot raise and no PackageNotFoundError escapes resolution.
    if not repository.has_package(name):
        return []
    releases = repository.get_releases(name)
    ordered = _order_descending(releases, version_engine)
    # A candidate is viable when it satisfies every accumulated constraint for the package.
    return [
        release
        for release in ordered
        if all(
            range_engine.satisfies(release.version, constraint, False)
            for _, constraint in requirements
        )
    ]


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Backing storage mapping package names to descending release lists.
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # POSTCONDITION (register_release): the release joins the package release history,
        # re-sorted into descending version precedence order.
        engine = get_singleton(semver_core.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        _insert_descending(releases, release, engine)

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # PRECONDITION (missing_package): unregistered names raise PackageNotFoundError.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                f"Package {name!r} is not registered in the repository.", name
            )
        # POSTCONDITION (descending_releases): shallow copy of the descending release list.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # POSTCONDITION (has_membership): membership test over registered package names.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # POSTCONDITION (all_names): the set of every registered package name.
        return set(self._packages)


@singleton_type("system")
class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(self, root_dependencies: Collection[dependency_solver.PackageDependency]) -> dependency_solver.ResolutionOutcome:
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)
        version_engine = get_singleton(semver_core.VersionEngine)
        # Initialize the accumulated constraint mapping from the root requirements.
        accumulated: Dict[str, List[_Requirement]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(('root', dependency.range_constraint))
        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()
        # Depth-first search with MRV variable selection and conflict trail collection.
        resolved = self._search(
            assignment,
            accumulated,
            derivation_steps,
            conflict_trail,
            conflicting_packages,
            repository,
            range_engine,
            version_engine,
        )
        if not resolved:
            # PRECONDITIONS (unsatisfiable_conflict, missing_package_conflict): exhausted
            # branches raise ResolutionConflictError identifying the conflicting packages.
            explanation = '\n'.join(conflict_trail)
            raise dependency_solver.ResolutionConflictError(
                explanation, tuple(sorted(conflicting_packages)), explanation
            )
        # POSTCONDITIONS (compatible_assignment, derivation_report): compiled outcome record.
        selected_versions: Dict[str, semver_core.Version] = {
            name: release.version for name, release in assignment.items()
        }
        return dependency_solver.ResolutionOutcome(selected_versions, tuple(derivation_steps))

    def _search(
        self,
        assignment: Dict[str, dependency_solver.PackageRelease],
        accumulated: Dict[str, List[_Requirement]],
        derivation_steps: List[str],
        conflict_trail: List[str],
        conflicting_packages: Set[str],
        repository: dependency_solver.PackageRepository,
        range_engine: semver_range.RangeEngine,
        version_engine: semver_core.VersionEngine,
    ) -> bool:
        unassigned = [name for name in accumulated if name not in assignment]
        if not unassigned:
            # Complete assignment: every constrained package has a release.
            return True
        # MRV variable selection: fewest viable candidates first, ties broken lexically.
        candidates: Dict[str, List[dependency_solver.PackageRelease]] = {}
        for name in unassigned:
            candidates[name] = _viable_releases(
                name, accumulated[name], repository, range_engine, version_engine
            )
        selected = min(unassigned, key=lambda name: (len(candidates[name]), name))
        viable = candidates[selected]
        if not viable:
            # No candidate survives the accumulated constraints: record and backtrack.
            requesters = sorted({requester for requester, _ in accumulated[selected]})
            conflicting_packages.add(selected)
            conflicting_packages.update(requesters)
            conflict_trail.append(
                f"No viable releases for {selected!r} satisfying constraints from {requesters!r}"
            )
            return False
        for candidate in viable:
            # Value ordering: explore the highest remaining precedence candidate first.
            assignment[selected] = candidate
            derivation_steps.append(f"Assign {selected!r} to {candidate.version.format()}")
            conflict_detected = False
            newly_added: List[Tuple[str, _Requirement]] = []
            # Forward checking: merge the candidate dependencies into the constraints.
            for dependency in candidate.dependencies:
                if dependency.name in assignment:
                    resolved = assignment[dependency.name]
                    if not range_engine.satisfies(
                        resolved.version, dependency.range_constraint, False
                    ):
                        # Existing assignment violates the new requirement: backtrack now.
                        conflict_detected = True
                        conflicting_packages.add(selected)
                        conflicting_packages.add(dependency.name)
                        conflict_trail.append(
                            f"Conflict: {selected!r} {candidate.version.format()} requires "
                            f"{dependency.name!r} {dependency.range_constraint.raw_text} but "
                            f"{resolved.version.format()} is already selected"
                        )
                        break
                else:
                    entry: _Requirement = (selected, dependency.range_constraint)
                    accumulated.setdefault(dependency.name, []).append(entry)
                    newly_added.append((dependency.name, entry))
            if not conflict_detected and self._search(
                assignment,
                accumulated,
                derivation_steps,
                conflict_trail,
                conflicting_packages,
                repository,
                range_engine,
                version_engine,
            ):
                return True
            # Undo the assignment and every constraint introduced by this candidate.
            while newly_added:
                dependency_name, entry = newly_added.pop()
                accumulated[dependency_name].remove(entry)
                if not accumulated[dependency_name]:
                    del accumulated[dependency_name]
            del assignment[selected]
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
# LAST_CLEANED: 2026-11-08T13:06:50Z
# LAST_CHANGED: 2026-11-08T12:59:22Z
# CHANGE: Prune the unreachable PackageNotFoundError except fallback in _viable_releases: the has_package membership guard already evaluates unregistered packages to zero candidate releases, so the redundant defensive branch was dead under the repo.missing_package contract; audited sibling branches (viable-candidate conflict path, backtracking undo, comparator dispatch) for the same unreachable-under-spec pattern and left the contracted reachable branches in place.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:06:50Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:06:37Z
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

    def __post_init__(self) -> None:
        # Realize dataclass-based exception semantics: expose the diagnostic message.
        Exception.__init__(self, self.message)

    def __str__(self) -> str:
        # Diagnostic failure responses format with the exact message template.
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
        # Unconditional postcondition: prerelease identifiers make a version a prerelease.
        return bool(self.prerelease)

    def format(self) -> str:
        # Unconditional postcondition: canonical SemVer 2.0.0 textual representation.
        text = f'{self.major}.{self.minor}.{self.patch}'
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # Equivalent to format().
        return self.format()


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing and precedence comparison."""

    @operation
    def parse_version(self, text: str) -> Version:
        # Requirements specified by semver_core.VersionEngine.parse_version.
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # Requirements specified by semver_core.VersionEngine.compare_precedence.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:42:42Z
# LAST_CHANGED: 2026-11-08T12:42:42Z
# CHANGE: Implement SemVerError/InvalidVersionError as mutable dataclass exceptions with message __str__ and args, and concretely realize Version (is_prerelease, canonical format(), __str__) plus decorated VersionEngine protocol stubs.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, Tuple

import re

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 grammar: numeric identifiers without leading zeroes, an optional
# dot-separated pre-release suffix, and an optional plus-separated build suffix.
_SEMVER_SYNTAX = re.compile(
    r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
    r'(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)'
    r'(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?'
    r'(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?'
)

_DIGITS = '0123456789'


def _compare_numeric(left: int, right: int) -> int:
    if left == right:
        return 0
    return -1 if left < right else 1


def _is_numeric_identifier(identifier: str) -> bool:
    # SemVer numeric identifiers are pure ASCII digit sequences.
    return bool(identifier) and all(character in _DIGITS for character in identifier)


def _compare_prerelease_identifier(left: str, right: str) -> int:
    left_numeric = _is_numeric_identifier(left)
    right_numeric = _is_numeric_identifier(right)
    if left_numeric and right_numeric:
        # Both numeric: compare as integers.
        return _compare_numeric(int(left), int(right))
    if left_numeric != right_numeric:
        # Numeric identifiers always rank below alphanumeric identifiers.
        return -1 if left_numeric else 1
    if left == right:
        return 0
    # Both alphanumeric: compare ASCII lexicographically.
    return -1 if left < right else 1


def _compare_core_numbers(v1: semver_core.Version, v2: semver_core.Version) -> int:
    # Numerical components compare numerically in major, minor, patch sequence.
    for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
        comparison = _compare_numeric(left, right)
        if comparison != 0:
            return comparison
    return 0


def _compare_prerelease_segments(v1: semver_core.Version, v2: semver_core.Version) -> int:
    # A normal version ranks higher than a prerelease sharing identical core numbers.
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for left, right in zip(v1.prerelease, v2.prerelease):
        comparison = _compare_prerelease_identifier(left, right)
        if comparison != 0:
            return comparison
    # A longer prerelease sequence ranks higher when the common prefix matches.
    return _compare_numeric(len(v1.prerelease), len(v2.prerelease))


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of the SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        # PRECONDITION (leading_zero_grammar): grammar violations and numeric identifiers
        # with leading zeroes MUST raise InvalidVersionError.
        match = _SEMVER_SYNTAX.fullmatch(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                f'Semantic version {text!r} violates the SemVer 2.0.0 grammar.', text
            )
        major_text, minor_text, patch_text, prerelease_text, build_text = match.groups()
        # POSTCONDITION (valid_syntax): populate all components of the Version record.
        prerelease: Tuple[str, ...] = tuple(prerelease_text.split('.')) if prerelease_text else ()
        build: Tuple[str, ...] = tuple(build_text.split('.')) if build_text else ()
        return semver_core.Version(
            int(major_text), int(minor_text), int(patch_text), prerelease, build
        )

    @operation
    @override
    def compare_precedence(self, v1: semver_core.Version, v2: semver_core.Version) -> int:
        # POSTCONDITION (numerical_components): major, minor, and patch compare numerically.
        core = _compare_core_numbers(v1, v2)
        if core != 0:
            return core
        # POSTCONDITIONS (normal_vs_prerelease, prerelease_ordering): build metadata is
        # excluded entirely (build_metadata_ignored), so only prerelease ordering remains.
        return _compare_prerelease_segments(v1, v2)


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
# LAST_CLEANED: 2026-11-08T13:01:35Z
# LAST_CHANGED: 2026-11-08T12:42:47Z
# CHANGE: Realize VersionEngine: regex SemVer 2.0.0 grammar validation raising InvalidVersionError with raw_text (leading zeroes, missing components, bad prerelease), and precedence comparison with numeric core ordering, normal-over-prerelease ranking, numeric-below-alphanumeric prerelease identifiers, ASCII lexicographic tie-breaks, longer-sequence ranking, and build metadata ignored.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:01:35Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:01:12Z
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
        # Unconditional postcondition: canonical raw range text representation.
        return self.raw_text


@poly_type
class RangeEngine(Protocol):
    """Provides version range parsing and constraint matching."""

    @operation
    def parse_range(self, text: str) -> VersionRange:
        # Requirements specified by semver_range.RangeEngine.parse_range.
        ...

    @operation
    def satisfies(self, version: semver_core.Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        # Requirements specified by semver_range.RangeEngine.satisfies.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:42:53Z
# LAST_CHANGED: 2026-11-08T12:42:53Z
# CHANGE: Implement InvalidRangeError as mutable dataclass exception carrying raw_range, concretely realize VersionRange (frozen record, __str__ delegating to raw_text), and declare RangeEngine protocol stubs with framework decorators.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

# A single relational comparator: (operator, boundary version).
_Comparator = Tuple[semver_core.ComparatorOp, semver_core.Version]
# A conjunction of comparators; an empty conjunction matches every version.
_Alternative = Tuple[_Comparator, ...]
# A parsed operand: (fixed numeric component count, lower bound, upper bound).
# A fixed count of 3 denotes a full semantic version (upper bound is unused).
_Operand = Tuple[int, semver_core.Version, Optional[semver_core.Version]]

_RELATIONAL_OPERATORS: Tuple[str, ...] = ('==', '!=', '>=', '<=', '>', '<', '=', '^', '~')
_WILDCARD_TOKENS: Tuple[str, ...] = ('x', 'X', '*')
_DIGITS = '0123456789'

_ANY: _Alternative = ()
# `0.0.0-0` is the lowest possible precedence, so `< 0.0.0-0` matches nothing.
_NEVER: _Alternative = ((semver_core.ComparatorOp.LT, semver_core.Version(0, 0, 0, ('0',))),)


def _invalid(raw_range: str, detail: str) -> semver_range.InvalidRangeError:
    return semver_range.InvalidRangeError(
        f'Invalid version range {raw_range!r}: {detail}', raw_range
    )


def _split_operator(token: str) -> Tuple[str, str]:
    # Relational and prefix operators may be attached to, or separated from, operands.
    for operator in _RELATIONAL_OPERATORS:
        if token.startswith(operator):
            return operator, token[len(operator):]
    return '', token


def _is_numeric_component(component: str) -> bool:
    # SemVer numeric components are digit sequences without leading zeroes.
    if not component or any(character not in _DIGITS for character in component):
        return False
    return len(component) == 1 or not component.startswith('0')


def _parse_wildcard_operand(
    components: List[str], operand_text: str, raw_range: str
) -> _Operand:
    fixed: List[int] = []
    wildcard_seen = False
    for component in components:
        if component in _WILDCARD_TOKENS:
            wildcard_seen = True
            continue
        if wildcard_seen:
            raise _invalid(
                raw_range,
                f'wildcard components must be trailing in wildcard expression {operand_text!r}',
            )
        if not _is_numeric_component(component):
            raise _invalid(
                raw_range,
                f'numeric component {component!r} is not valid in wildcard expression {operand_text!r}',
            )
        fixed.append(int(component))
    if len(fixed) > 2:
        raise _invalid(raw_range, f'wildcard expression {operand_text!r} has too many components')
    major = fixed[0] if len(fixed) > 0 else 0
    minor = fixed[1] if len(fixed) > 1 else 0
    lower = semver_core.Version(major, minor, 0)
    if len(fixed) == 0:
        # '*' matches every version; it has no upper boundary.
        return (0, lower, None)
    if len(fixed) == 1:
        return (1, lower, semver_core.Version(major + 1, 0, 0))
    return (2, lower, semver_core.Version(major, minor + 1, 0))


def _parse_operand(operand_text: str, raw_range: str) -> _Operand:
    components = operand_text.split('.')
    if any(component in _WILDCARD_TOKENS for component in components):
        return _parse_wildcard_operand(components, operand_text, raw_range)
    # PRECONDITION (bare_partials_prohibited): anything that is not a full semantic
    # version or a wildcard expression is a bare partial and is rejected.
    engine = get_singleton(semver_core.VersionEngine)
    try:
        version = engine.parse_version(operand_text)
    except semver_core.InvalidVersionError as error:
        raise _invalid(
            raw_range,
            f'{operand_text!r} is neither a full semantic version nor a wildcard expression',
        ) from error
    return (3, version, None)


def _wildcard_alternative(operand: _Operand) -> _Alternative:
    # Wildcard equality denotes a closed-open interval of matching versions; the `*`
    # wildcard has no upper boundary and therefore matches every version.
    _, lower, upper = operand
    if upper is None:
        return _ANY
    return (
        (semver_core.ComparatorOp.GE, lower),
        (semver_core.ComparatorOp.LT, upper),
    )


def _caret_upper_bound(operand: _Operand) -> semver_core.Version:
    # Caret ranges close on the first non-zero component boundary.
    fixed, lower, _ = operand
    major, minor, patch = lower.major, lower.minor, lower.patch
    if fixed == 1:
        return semver_core.Version(major + 1, 0, 0)
    if fixed == 2:
        if major > 0:
            return semver_core.Version(major + 1, 0, 0)
        return semver_core.Version(0, minor + 1, 0)
    if major > 0:
        return semver_core.Version(major + 1, 0, 0)
    if minor > 0:
        return semver_core.Version(0, minor + 1, 0)
    return semver_core.Version(0, 0, patch + 1)


def _caret_alternatives(operand: _Operand) -> Tuple[_Alternative, ...]:
    fixed, lower, _ = operand
    if fixed == 0:
        return (_ANY,)
    upper = _caret_upper_bound(operand)
    return (((semver_core.ComparatorOp.GE, lower), (semver_core.ComparatorOp.LT, upper)),)


def _tilde_alternatives(operand: _Operand) -> Tuple[_Alternative, ...]:
    # Tilde ranges expand into lower and upper minor boundaries.
    fixed, lower, _ = operand
    if fixed == 0:
        return (_ANY,)
    if fixed == 1:
        upper = semver_core.Version(lower.major + 1, 0, 0)
    else:
        upper = semver_core.Version(lower.major, lower.minor + 1, 0)
    return (((semver_core.ComparatorOp.GE, lower), (semver_core.ComparatorOp.LT, upper)),)


def _expand_comparator(operator: str, operand: _Operand) -> Tuple[_Alternative, ...]:
    fixed, lower, upper = operand
    full = fixed == 3
    if operator in ('', '==', '='):
        if full:
            return (((semver_core.ComparatorOp.EQ, lower),),)
        return (_wildcard_alternative(operand),)
    if operator == '!=':
        if full:
            return (((semver_core.ComparatorOp.NE, lower),),)
        if upper is None:
            return (_NEVER,)
        # A wildcard inequality spans two disjoint alternatives.
        return (
            ((semver_core.ComparatorOp.LT, lower),),
            ((semver_core.ComparatorOp.GE, upper),),
        )
    if operator == '>':
        if full:
            return (((semver_core.ComparatorOp.GT, lower),),)
        if upper is None:
            return (_NEVER,)
        return (((semver_core.ComparatorOp.GE, upper),),)
    if operator == '>=':
        if full:
            return (((semver_core.ComparatorOp.GE, lower),),)
        if upper is None:
            return (_ANY,)
        return (((semver_core.ComparatorOp.GE, lower),),)
    if operator == '<':
        return (((semver_core.ComparatorOp.LT, lower),),)
    if operator == '<=':
        if full:
            return (((semver_core.ComparatorOp.LE, lower),),)
        if upper is None:
            return (_ANY,)
        return (((semver_core.ComparatorOp.LT, upper),),)
    if operator == '^':
        return _caret_alternatives(operand)
    return _tilde_alternatives(operand)


def _hyphen_alternatives(lower: _Operand, upper: _Operand) -> Tuple[_Alternative, ...]:
    # A hyphen range conjoins an inclusive lower bound with an inclusive full-version
    # upper bound or an exclusive wildcard prefix boundary.
    _, lower_version, _ = lower
    upper_fixed, upper_version, upper_bound = upper
    comparators: List[_Comparator] = [(semver_core.ComparatorOp.GE, lower_version)]
    if upper_fixed == 3:
        comparators.append((semver_core.ComparatorOp.LE, upper_version))
    elif upper_bound is not None:
        comparators.append((semver_core.ComparatorOp.LT, upper_bound))
    return (tuple(comparators),)


def _compile_clause(clause: str, raw_range: str) -> Tuple[_Alternative, ...]:
    tokens = clause.split()
    if '-' in tokens:
        # Hyphen ranges connect exactly two bounds; each bound is a full version or wildcard.
        if len(tokens) != 3 or tokens[1] != '-':
            raise _invalid(raw_range, f'malformed hyphen range {clause!r}')
        return _hyphen_alternatives(
            _parse_operand(tokens[0], raw_range), _parse_operand(tokens[2], raw_range)
        )
    alternatives: Tuple[_Alternative, ...] = (_ANY,)
    index = 0
    while index < len(tokens):
        operator, operand_text = _split_operator(tokens[index])
        index += 1
        if not operand_text:
            # The operator was whitespace separated from its operand.
            if index >= len(tokens):
                raise _invalid(raw_range, f'missing version after operator {operator!r}')
            following_operator, following_text = _split_operator(tokens[index])
            if following_operator:
                raise _invalid(
                    raw_range,
                    f'unexpected operator {following_operator!r} after operator {operator!r}',
                )
            operand_text = following_text
            index += 1
        operand = _parse_operand(operand_text, raw_range)
        # Comparators delimited by whitespace conjoin within a clause.
        alternatives = tuple(
            alternative + expansion
            for alternative in alternatives
            for expansion in _expand_comparator(operator, operand)
        )
    return alternatives


def _compile_range_text(text: str, raw_range: str) -> Tuple[_Alternative, ...]:
    alternatives: List[_Alternative] = []
    for clause in text.split('||'):
        clause_text = clause.strip()
        # PRECONDITION (malformed_syntax): empty union clauses are malformed.
        if not clause_text:
            raise _invalid(raw_range, 'union expression contains an empty clause')
        alternatives.extend(_compile_clause(clause_text, raw_range))
    return tuple(alternatives)


def _comparator_satisfied(operator: semver_core.ComparatorOp, comparison: int) -> bool:
    if operator is semver_core.ComparatorOp.EQ:
        return comparison == 0
    if operator is semver_core.ComparatorOp.NE:
        return comparison != 0
    if operator is semver_core.ComparatorOp.LT:
        return comparison < 0
    if operator is semver_core.ComparatorOp.LE:
        return comparison <= 0
    if operator is semver_core.ComparatorOp.GT:
        return comparison > 0
    return comparison >= 0


def _matches_alternative(
    engine: semver_core.VersionEngine,
    version: semver_core.Version,
    alternative: _Alternative,
) -> bool:
    for operator, boundary in alternative:
        comparison = engine.compare_precedence(version, boundary)
        if not _comparator_satisfied(operator, comparison):
            return False
    return True


def _targets_prerelease(
    version: semver_core.Version, alternatives: Tuple[_Alternative, ...]
) -> bool:
    # A range explicitly targets a prerelease by naming a prerelease identifier that
    # shares the candidate's major, minor, and patch numbers.
    core = (version.major, version.minor, version.patch)
    for alternative in alternatives:
        for _, boundary in alternative:
            if boundary.prerelease and (
                boundary.major, boundary.minor, boundary.patch
            ) == core:
                return True
    return False


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of the version range parsing and matching engine."""

    tier = system

    def __init__(self) -> None:
        # Compiled disjunctive-normal-form alternatives keyed by trimmed range text.
        self._compiled: Dict[str, Tuple[_Alternative, ...]] = {}

    def _compile(self, text: str, raw_range: Optional[str] = None) -> Tuple[_Alternative, ...]:
        cached = self._compiled.get(text)
        if cached is not None:
            return cached
        compiled = _compile_range_text(text, text if raw_range is None else raw_range)
        self._compiled[text] = compiled
        return compiled

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        trimmed = text.strip()
        # PRECONDITION (malformed_syntax): empty or whitespace-only expressions are malformed.
        if not trimmed:
            raise _invalid(text, 'expression is empty')
        # PRECONDITION (malformed_syntax): commas are not permitted delimiters.
        if ',' in trimmed:
            raise _invalid(text, 'comma delimiters are not permitted')
        self._compile(trimmed, text)
        # POSTCONDITION (whitespace_trimming): raw_text stores the trimmed expression.
        return semver_range.VersionRange(trimmed)

    @operation
    @override
    def satisfies(self, version: semver_core.Version, range_constraint: semver_range.VersionRange, include_prerelease: bool) -> bool:
        alternatives = self._compile(range_constraint.raw_text)
        # POSTCONDITION (prerelease_filter): prerelease candidates are filtered out unless
        # the range explicitly targets their major, minor, and patch numbers.
        if version.is_prerelease and not include_prerelease:
            if not _targets_prerelease(version, alternatives):
                return False
        engine = get_singleton(semver_core.VersionEngine)
        # POSTCONDITION (boolean_match): satisfied when all comparators in one clause hold.
        return any(
            _matches_alternative(engine, version, alternative) for alternative in alternatives
        )


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
# LAST_CLEANED: 2026-11-08T13:09:33Z
# LAST_CHANGED: 2026-11-08T13:04:54Z
# CHANGE: Prune the dead full-version equality branch in the equality normalization helper: full-version equality is handled by _expand_comparator before the wildcard path, so the helper is now a pure wildcard range normalizer (_wildcard_alternative) covering [[>=lower,<upper]] intervals and the unbounded '*' case without an unreachable fixed==3 arm; audited sibling branch sites (caret/tilde upper bounds, wildcard parsing, hyphen bounds, comparator dispatch) for the same dead-under-caller-guard pattern.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:09:33Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:08:50Z
# --- END AUTOFAB METADATA ---
