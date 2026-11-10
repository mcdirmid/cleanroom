# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261107_032153_deepseek-flash_semver_solver_multi_pretense
# Timestamp: 2026-11-07T03:21:53.092934+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 486,849
#   Cached Inbound Tokens:   56,876,160
#   Outbound Tokens:         466,166
#   Total Tokens:            57,829,175
#   Financial Cost ($USD):   $0.5234
#   Wall Clock Duration:     2932.95s
#   Step Latencies (s):      [398.9, 723.0, 671.3, 83.7, 41.7, 771.6, 43.3, 129.2, 41.7, 183.3, 54.0, 41.9, 236.2, 108.4, 43.5, 171.6, 41.7, 20.6, 258.5, 66.1, 75.0, 106.6, 41.6, 41.4]
#   Role Execution Rounds:   lib: 2, pretense: 7, pretense_coverage: 5, pretense_qa: 10 (Total: 24)
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
# LAST_CLEANED: 2026-11-07T03:28:26Z
# LAST_CHANGED: 2026-11-07T03:28:26Z
# CHANGE: Implement repository/solver interface: error dataclasses, PackageDependency/PackageRelease/ResolutionOutcome data types, PackageRepository and DependencySolver protocols
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
import functools

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi


@singleton_type('system')
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_core.VersionEngine)

        # POSTCONDITIONS: keep releases ordered by descending version precedence.
        def descending(
            left: dependency_solver.PackageRelease,
            right: dependency_solver.PackageRelease,
        ) -> int:
            return engine.compare_precedence(right.version, left.version)

        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=functools.cmp_to_key(descending))

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        """Retrieves releases for a package ordered by version precedence descending."""
        # PRECONDITIONS: an unregistered package raises PackageNotFoundError.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository.",
                name,
            )
        # POSTCONDITIONS: yield a shallow copy of the descending sorted release list.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        # POSTCONDITIONS: membership test over the indexed package names.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names."""
        # POSTCONDITIONS: produce the set of all registered package names.
        return set(self._packages.keys())


@singleton_type('system')
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
        range_engine = get_singleton(semver_range.RangeEngine)
        repository = get_singleton(dependency_solver.PackageRepository)

        # Search state: accumulated constraints map package names to (requester, range) pairs.
        accumulated_constraints: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated_constraints.setdefault(dependency.name, []).append(
                ('root', dependency.range_constraint)
            )

        # Partial assignment of package names to concrete release records.
        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def requirement_satisfied(
            release: dependency_solver.PackageRelease,
            constraint: semver_range.VersionRange,
        ) -> bool:
            return range_engine.satisfies(release.version, constraint, False)

        def viable_releases(name: str) -> List[dependency_solver.PackageRelease]:
            try:
                available = repository.get_releases(name)
            except dependency_solver.PackageNotFoundError:
                # Packages absent from the repository have zero candidate releases.
                available = []
            # Forward checking: a candidate MUST satisfy every accumulated constraint.
            return [
                release
                for release in available
                if all(
                    requirement_satisfied(release, constraint)
                    for _, constraint in accumulated_constraints[name]
                )
            ]

        def record_conflict(name: str) -> None:
            requesters = [
                requested_by for requested_by, _ in accumulated_constraints[name]
            ]
            conflicting_packages.add(name)
            conflicting_packages.update(
                requested_by for requested_by in requesters if requested_by != 'root'
            )
            conflict_trail.append(
                f"No viable releases for '{name}' satisfying constraints from {requesters}"
            )

        def backtrack() -> bool:
            # Minimum Remaining Values variable selection over unassigned packages.
            unassigned = [
                name for name in accumulated_constraints if name not in assignment
            ]
            if not unassigned:
                return True
            candidates_by_name: Dict[str, List[dependency_solver.PackageRelease]] = {}
            for name in unassigned:
                candidates_by_name[name] = viable_releases(name)
            selected = min(
                unassigned, key=lambda name: (len(candidates_by_name[name]), name)
            )
            candidates = candidates_by_name[selected]
            if not candidates:
                record_conflict(selected)
                return False
            # Value ordering: explore candidate releases in descending precedence.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # An already assigned package that violates a requirement conflicts.
                        if not requirement_satisfied(
                            assignment[dependency.name], dependency.range_constraint
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} {dependency.range_constraint}"
                            )
                            break
                    else:
                        # Merge newly introduced requirements into accumulated constraints.
                        constraint_entry = (selected, dependency.range_constraint)
                        accumulated_constraints.setdefault(dependency.name, []).append(
                            constraint_entry
                        )
                        newly_added.append((dependency.name, constraint_entry))

                if not conflict_detected and backtrack():
                    return True

                # Backtracking: undo introduced constraints, assignment, and derivation step.
                for name, constraint_entry in newly_added:
                    accumulated_constraints[name].remove(constraint_entry)
                    if not accumulated_constraints[name]:
                        del accumulated_constraints[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if backtrack():
            # POSTCONDITIONS: compile the selected release mapping and decision sequence.
            selected_versions: Dict[str, semver_core.Version] = {
                name: release.version for name, release in assignment.items()
            }
            return dependency_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        # PRECONDITIONS: unsatisfiable or missing dependencies raise ResolutionConflictError.
        explanation = (
            '; '.join(conflict_trail)
            if conflict_trail
            else 'Dependency resolution exhausted every candidate branch.'
        )
        raise dependency_solver.ResolutionConflictError(
            f'Dependency resolution failed: {explanation}',
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
# LAST_CLEANED: 2026-11-07T04:07:25Z
# LAST_CHANGED: 2026-11-07T03:28:43Z
# CHANGE: Implement PackageRepository (descending-precedence release index, PackageNotFoundError, copies) and DependencySolver (MRV backtracking with descending candidate order, forward checking, conflict trail, ResolutionConflictError for unsatisfiable/missing packages)
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T04:07:25Z
# PRETENSE_QA_AUDIT: 2026-11-07T04:07:05Z
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
        # POSTCONDITIONS: diagnostics render the structured message payload.
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
        """Indicates whether this version contains pre-release identifiers."""
        # POSTCONDITIONS: True exactly when pre-release identifiers are present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        # POSTCONDITIONS: canonical major.minor.patch[-prerelease][+build] rendering.
        text = f'{self.major}.{self.minor}.{self.patch}'
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
        # POSTCONDITIONS: equivalent to format().
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
# LAST_CLEANED: 2026-11-07T03:28:16Z
# LAST_CHANGED: 2026-11-07T03:28:16Z
# CHANGE: Implement SemVer 2.0 interface: dataclass errors with __str__ (non-frozen), ComparatorOp, frozen Version with is_prerelease/format/__str__, and VersionEngine protocol stubs
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations
from typing import Optional
import re

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 regular expression: numeric components without leading zeroes,
# optional dot-separated pre-release identifiers, and optional build metadata.
_SEMVER_PATTERN = re.compile(
    r'^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)'
    r'(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)'
    r'(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?'
    r'(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'
)


@singleton_type('system')
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    def parse_version(self, text: str) -> semver_core.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # PRECONDITIONS: grammar violations or numeric leading zeroes raise InvalidVersionError.
        matched = _SEMVER_PATTERN.match(text)
        if matched is None:
            raise semver_core.InvalidVersionError(
                f"Invalid semantic version: '{text}'", text
            )
        prerelease_text = matched.group('prerelease')
        build_text = matched.group('build')
        # POSTCONDITIONS: produce an immutable Version record with parsed component tuples.
        return semver_core.Version(
            major=int(matched.group('major')),
            minor=int(matched.group('minor')),
            patch=int(matched.group('patch')),
            prerelease=tuple(prerelease_text.split('.')) if prerelease_text else (),
            build=tuple(build_text.split('.')) if build_text else (),
        )

    def compare_precedence(self, v1: semver_core.Version, v2: semver_core.Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        # POSTCONDITIONS: compare major, minor, and patch numerically in sequence.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return -1 if left < right else 1
        left_prerelease = v1.prerelease
        right_prerelease = v2.prerelease
        # POSTCONDITIONS: rank normal versions above pre-release versions.
        if not left_prerelease and not right_prerelease:
            return 0
        if not left_prerelease:
            return 1
        if not right_prerelease:
            return -1
        # POSTCONDITIONS: walk pre-release segments comparing each position.
        for left_segment, right_segment in zip(left_prerelease, right_prerelease):
            left_numeric = left_segment.isdigit()
            right_numeric = right_segment.isdigit()
            if left_numeric and right_numeric:
                # numeric segments compare as integers
                left_value = int(left_segment)
                right_value = int(right_segment)
                if left_value != right_value:
                    return -1 if left_value < right_value else 1
            elif left_numeric:
                # POSTCONDITIONS: numeric segments rank below string segments.
                return -1
            elif right_numeric:
                return 1
            elif left_segment != right_segment:
                # string segments compare by ASCII code points
                return -1 if left_segment < right_segment else 1
        # POSTCONDITIONS: longer pre-release sequences rank above matching common prefixes.
        if len(left_prerelease) != len(right_prerelease):
            return -1 if len(left_prerelease) < len(right_prerelease) else 1
        # POSTCONDITIONS: build metadata is excluded entirely from precedence.
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
# LAST_CLEANED: 2026-11-07T04:01:38Z
# LAST_CHANGED: 2026-11-07T03:28:32Z
# CHANGE: Implement VersionEngine: SemVer 2.0 regex parsing raising InvalidVersionError on grammar/leading-zero violations, and RFC precedence comparison over major/minor/patch, prerelease segments (numeric<alphanumeric, length rule), ignoring build metadata
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T04:01:38Z
# PRETENSE_QA_AUDIT: 2026-11-07T04:01:19Z
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
        """Returns the raw range text representation."""
        # POSTCONDITIONS: renders the canonical raw range text.
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
# LAST_CLEANED: 2026-11-07T03:28:21Z
# LAST_CHANGED: 2026-11-07T03:28:21Z
# CHANGE: Implement range interface: InvalidRangeError dataclass, frozen VersionRange with __str__, RangeEngine protocol with parse_range/satisfies stubs
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import re

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

# Comparator over an immutable boundary version.
_Comparator = Tuple[semver_core.ComparatorOp, semver_core.Version]
# Conjunction of comparators that MUST all hold.
_Clause = List[_Comparator]
# Disjunctive normal form: a disjunction of comparator conjunctions.
_Dnf = List[_Clause]

_WILDCARD_SEGMENTS = frozenset({'x', 'X', '*'})
_OPERATOR_PREFIXES = ('==', '!=', '<=', '>=', '=', '<', '>', '^', '~')
_NUMERIC_SEGMENT = re.compile(r'^(?:0|[1-9]\d*)$')
_BASIC_OPERATORS: Dict[str, semver_core.ComparatorOp] = {
    '==': semver_core.ComparatorOp.EQ,
    '!=': semver_core.ComparatorOp.NE,
    '<': semver_core.ComparatorOp.LT,
    '<=': semver_core.ComparatorOp.LE,
    '>': semver_core.ComparatorOp.GT,
    '>=': semver_core.ComparatorOp.GE,
}


@singleton_type('system')
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    def parse_range(self, text: str) -> semver_range.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        engine = get_singleton(semver_core.VersionEngine)
        # POSTCONDITIONS: validate the trimmed range expression before producing the record.
        self._compile(text, engine)
        return semver_range.VersionRange(raw_text=text.strip())

    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        engine = get_singleton(semver_core.VersionEngine)
        # POSTCONDITIONS: compile the range into disjunctive normal form comparator sets.
        clauses = self._compile(range_constraint.raw_text, engine)
        for clause in clauses:
            # POSTCONDITIONS: candidate MUST satisfy all comparators in at least one clause.
            if not all(self._compare(engine, version, op, bound) for op, bound in clause):
                continue
            # POSTCONDITIONS: filter candidate pre-releases unless the range targets them.
            if version.is_prerelease and not include_prerelease:
                if not self._targets_prerelease(clause, version):
                    continue
            return True
        # POSTCONDITIONS: evaluate to False when every clause fails.
        return False

    def _targets_prerelease(
        self,
        clause: _Clause,
        version: semver_core.Version,
    ) -> bool:
        # A pre-release candidate is only admissible when a boundary declares a
        # pre-release identifier at the exact same major, minor, and patch numbers.
        for _, bound in clause:
            if not bound.is_prerelease:
                continue
            if (bound.major, bound.minor, bound.patch) == (
                version.major,
                version.minor,
                version.patch,
            ):
                return True
        return False

    def _compare(
        self,
        engine: semver_core.VersionEngine,
        version: semver_core.Version,
        op: semver_core.ComparatorOp,
        bound: semver_core.Version,
    ) -> bool:
        # POSTCONDITIONS: test each comparator using precedence ordering only.
        ordering = engine.compare_precedence(version, bound)
        if op is semver_core.ComparatorOp.EQ:
            return ordering == 0
        if op is semver_core.ComparatorOp.NE:
            return ordering != 0
        if op is semver_core.ComparatorOp.LT:
            return ordering < 0
        if op is semver_core.ComparatorOp.LE:
            return ordering <= 0
        if op is semver_core.ComparatorOp.GT:
            return ordering > 0
        return ordering >= 0

    def _compile(self, text: str, engine: semver_core.VersionEngine) -> _Dnf:
        trimmed = text.strip()
        if not trimmed:
            raise self._invalid(
                'Version range expression MUST NOT be empty or whitespace only.',
                text,
            )
        if ',' in trimmed:
            raise self._invalid(
                'Version range comparators MUST be delimited by whitespace; commas are not permitted.',
                text,
            )
        # POSTCONDITIONS: union alternatives separated by '||' expand into separate clauses.
        compiled: _Dnf = []
        for alternative in trimmed.split('||'):
            clause_text = alternative.strip()
            if not clause_text:
                raise self._invalid(
                    'Version range union alternatives MUST NOT be empty.',
                    text,
                )
            compiled.extend(self._parse_clause(clause_text, engine, text))
        return compiled

    def _parse_clause(
        self,
        clause_text: str,
        engine: semver_core.VersionEngine,
        raw_text: str,
    ) -> _Dnf:
        # POSTCONDITIONS: delimit comparators within a clause strictly by whitespace,
        # accepting optional whitespace between operators and their target tokens.
        merged: List[Tuple[str, str]] = []
        tokens = clause_text.split()
        index = 0
        while index < len(tokens):
            operation_token, remainder = self._split_operator(tokens[index])
            if remainder == '' and operation_token != '':
                if index + 1 >= len(tokens):
                    raise self._invalid(
                        f"Operator '{operation_token}' MUST be followed by a version or wildcard target.",
                        raw_text,
                    )
                merged.append((operation_token, tokens[index + 1]))
                index += 2
                continue
            merged.append((operation_token, remainder))
            index += 1

        if any(target == '-' for _, target in merged):
            if (
                len(merged) != 3
                or merged[1][1] != '-'
                or merged[0][0] != ''
                or merged[2][0] != ''
            ):
                raise self._invalid(
                    'Hyphen ranges MUST connect exactly two unmodified bounds.',
                    raw_text,
                )
            # POSTCONDITIONS: hyphen ranges normalize into paired comparator inequalities.
            return self._hyphen_clause(merged[0][1], merged[2][1], engine, raw_text)

        clauses: _Dnf = [[]]
        for operation_token, version_token in merged:
            expanded = self._expand(operation_token, version_token, engine, raw_text)
            combined: _Dnf = []
            for existing in clauses:
                for addition in expanded:
                    combined.append(existing + addition)
            clauses = combined
            if not clauses:
                return []
        return clauses

    def _hyphen_clause(
        self,
        lower_text: str,
        upper_text: str,
        engine: semver_core.VersionEngine,
        raw_text: str,
    ) -> _Dnf:
        lower_exact, lower_floor, lower_specified = self._parse_bound(
            lower_text, engine, raw_text
        )
        upper_exact, upper_floor, upper_specified = self._parse_bound(
            upper_text, engine, raw_text
        )
        comparators: _Clause = []
        if lower_exact is not None:
            comparators.append((semver_core.ComparatorOp.GE, lower_exact))
        elif lower_specified > 0:
            comparators.append((semver_core.ComparatorOp.GE, lower_floor))
        if upper_exact is not None:
            comparators.append((semver_core.ComparatorOp.LE, upper_exact))
        elif upper_specified > 0:
            components = (upper_floor.major, upper_floor.minor, upper_floor.patch)
            comparators.append(
                (semver_core.ComparatorOp.LT, self._bump(components, upper_specified - 1))
            )
        return [comparators]

    def _expand(
        self,
        operation_token: str,
        version_token: str,
        engine: semver_core.VersionEngine,
        raw_text: str,
    ) -> _Dnf:
        operation = self._normalize_operator(operation_token)
        exact, floor_bound, specified = self._parse_bound(version_token, engine, raw_text)
        if exact is not None:
            components = (exact.major, exact.minor, exact.patch)
            if operation == '^':
                # POSTCONDITIONS: expand caret prefixes from the first non-zero component.
                ceiling = self._caret_ceiling(components, 3)
                return [[
                    (semver_core.ComparatorOp.GE, exact),
                    (semver_core.ComparatorOp.LT, ceiling),
                ]]
            if operation == '~':
                # POSTCONDITIONS: expand tilde prefixes into minor boundaries.
                ceiling = self._tilde_ceiling(components, 3)
                return [[
                    (semver_core.ComparatorOp.GE, exact),
                    (semver_core.ComparatorOp.LT, ceiling),
                ]]
            return [[(_BASIC_OPERATORS[operation], exact)]]

        if specified == 0:
            # POSTCONDITIONS: '*' and '>=*' are satisfied by all versions; other
            # operators applied to an unbounded wildcard are unsatisfiable.
            if operation in ('==', '^', '~', '>=', '<='):
                return [[]]
            return []

        components = (floor_bound.major, floor_bound.minor, floor_bound.patch)
        ceiling = self._bump(components, specified - 1)
        if operation == '==':
            return [[
                (semver_core.ComparatorOp.GE, floor_bound),
                (semver_core.ComparatorOp.LT, ceiling),
            ]]
        if operation == '!=':
            # POSTCONDITIONS: '!=1.x' expands to '<1.0.0 || >=2.0.0'.
            return [
                [(semver_core.ComparatorOp.LT, floor_bound)],
                [(semver_core.ComparatorOp.GE, ceiling)],
            ]
        if operation == '>':
            return [[(semver_core.ComparatorOp.GE, ceiling)]]
        if operation == '>=':
            return [[(semver_core.ComparatorOp.GE, floor_bound)]]
        if operation == '<':
            return [[(semver_core.ComparatorOp.LT, floor_bound)]]
        if operation == '<=':
            return [[(semver_core.ComparatorOp.LT, ceiling)]]
        if operation == '^':
            return [[
                (semver_core.ComparatorOp.GE, floor_bound),
                (semver_core.ComparatorOp.LT, self._caret_ceiling(components, specified)),
            ]]
        return [[
            (semver_core.ComparatorOp.GE, floor_bound),
            (semver_core.ComparatorOp.LT, self._tilde_ceiling(components, specified)),
        ]]

    def _parse_bound(
        self,
        text: str,
        engine: semver_core.VersionEngine,
        raw_text: str,
    ) -> Tuple[Optional[semver_core.Version], semver_core.Version, int]:
        # PRECONDITIONS: bound tokens are always non-empty because clauses are whitespace tokenized.
        core_text, build_text = self._split_once(text, '+')
        core_text, prerelease_text = self._split_once(core_text, '-')
        segments = core_text.split('.')
        if len(segments) > 3:
            raise self._invalid(
                f"Malformed version bound '{text}' in range expression.",
                raw_text,
            )
        numeric: List[int] = []
        wildcard_index: Optional[int] = None
        for position, segment in enumerate(segments):
            if segment in _WILDCARD_SEGMENTS:
                if wildcard_index is None:
                    wildcard_index = position
                continue
            if wildcard_index is not None:
                raise self._invalid(
                    f"Wildcard segments MUST be trailing in version bound '{text}'.",
                    raw_text,
                )
            if not _NUMERIC_SEGMENT.match(segment):
                raise self._invalid(
                    f"Malformed version bound '{text}' in range expression.",
                    raw_text,
                )
            numeric.append(int(segment))

        if wildcard_index is None:
            # PRECONDITIONS: bare partial versions lacking wildcards are rejected.
            if len(segments) != 3:
                raise self._invalid(
                    f"Bare partial version bound '{text}' MUST use wildcard characters.",
                    raw_text,
                )
            try:
                exact = engine.parse_version(text)
            except semver_core.InvalidVersionError as error:
                raise self._invalid(
                    f"Malformed version bound '{text}' in range expression: {error.message}.",
                    raw_text,
                ) from error
            return (exact, exact, 3)

        if prerelease_text is not None or build_text is not None:
            raise self._invalid(
                f"Wildcard version bound '{text}' MUST NOT declare pre-release or build metadata.",
                raw_text,
            )
        padded = (numeric + [0, 0, 0])[:3]
        floor = semver_core.Version(
            major=padded[0],
            minor=padded[1],
            patch=padded[2],
        )
        return (None, floor, wildcard_index)

    def _caret_ceiling(self, components: Tuple[int, int, int], specified: int) -> semver_core.Version:
        # POSTCONDITIONS: bump the first non-zero specified component.
        for position in range(specified):
            if components[position] != 0:
                return self._bump(components, position)
        if specified >= 3:
            return self._bump(components, 2)
        return self._bump(components, specified - 1)

    def _tilde_ceiling(self, components: Tuple[int, int, int], specified: int) -> semver_core.Version:
        # POSTCONDITIONS: expand into lower and upper minor boundaries.
        if specified >= 2:
            return self._bump(components, 1)
        return self._bump(components, 0)

    @staticmethod
    def _bump(components: Tuple[int, int, int], position: int) -> semver_core.Version:
        values = [components[0], components[1], components[2]]
        values[position] += 1
        for later in range(position + 1, 3):
            values[later] = 0
        return semver_core.Version(major=values[0], minor=values[1], patch=values[2])

    @staticmethod
    def _normalize_operator(operation_token: str) -> str:
        if operation_token in ('', '='):
            return '=='
        return operation_token

    @staticmethod
    def _split_operator(token: str) -> Tuple[str, str]:
        for prefix in _OPERATOR_PREFIXES:
            if token.startswith(prefix):
                return (prefix, token[len(prefix):])
        return ('', token)

    @staticmethod
    def _split_once(text: str, separator: str) -> Tuple[str, Optional[str]]:
        head, found, tail = text.partition(separator)
        if not found:
            return (text, None)
        return (head, tail)

    @staticmethod
    def _invalid(message: str, raw_text: str) -> semver_range.InvalidRangeError:
        return semver_range.InvalidRangeError(message, raw_text)


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
# LAST_CLEANED: 2026-11-07T04:10:10Z
# LAST_CHANGED: 2026-11-07T04:08:51Z
# CHANGE: Prune unreachable empty version-bound guard in _parse_bound: bound text always originates from non-empty whitespace-delimited clause tokens, and empty/whitespace-only range input is still rejected earlier by _compile in parse_range/satisfies (InvalidRangeError preserved)
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T04:10:10Z
# PRETENSE_QA_AUDIT: 2026-11-07T04:09:27Z
# --- END AUTOFAB METADATA ---
