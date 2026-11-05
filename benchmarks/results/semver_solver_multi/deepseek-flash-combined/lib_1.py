# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_164930_deepseek-flash_semver_solver_multi_combined
# Timestamp: 2026-11-05T16:49:30.941067+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 683,220
#   Cached Inbound Tokens:   92,872,063
#   Outbound Tokens:         585,360
#   Total Tokens:            94,140,643
#   Financial Cost ($USD):   $0.7323
#   Wall Clock Duration:     2987.76s
#   Step Latencies (s):      [313.4, 507.7, 21.7, 565.3, 39.9, 116.3, 35.6, 143.1, 200.0, 13.2, 149.1, 220.5, 68.1, 12.4, 10.7, 69.7, 142.3, 10.4, 102.2, 428.1, 112.1, 164.4, 78.4, 98.4, 67.3, 98.6, 10.4, 123.7, 231.2, 65.3, 43.4, 12.4, 10.8, 49.4, 61.4, 36.8, 10.8, 11.2, 148.6, 21.5, 10.6]
#   Role Execution Rounds:   coverage: 5, lib: 4, pretense: 9, pretense_coverage: 4, pretense_qa: 10, qa: 5, test: 4 (Total: 41)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       49
#   Unit Tests Failed:       0
#   Line Coverage:           99.0%
#   Branch Coverage:         99.0%
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

    # Structured attribute carrying the name of the missing package.
    package_name: str

    def __str__(self) -> str:
        return self.message


@dataclass
class ResolutionConflictError(semver_core.SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually."""

    # Structured attributes carrying the involved packages and the derivation.
    conflicting_packages: Tuple[str, ...]
    explanation: str

    def __str__(self) -> str:
        return self.message


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
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:57:37Z
# LAST_CHANGED: 2026-11-05T16:57:37Z
# CHANGE: Implement dependency solver interface: PackageNotFoundError/ResolutionConflictError dataclasses with structured diagnostics, PackageDependency/PackageRelease/ResolutionOutcome frozen value records, and PackageRepository/DependencySolver protocols for repository indexing and resolution.
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
from __future__ import annotations
from functools import cmp_to_key
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

# Requirements specified in dependency_solver_impl.pyi

# A pending requirement: (requesting package name, required version range).
_Constraint = Tuple[str, semver_range.VersionRange]


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Backing store keyed by package name, each value ordered by descending
        # version precedence.
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # Postcondition: the release is registered and its package release list
        # is re-sorted by descending version precedence using the version engine.
        engine = get_singleton(semver_core.VersionEngine)

        def compare_releases(
            left: dependency_solver.PackageRelease,
            right: dependency_solver.PackageRelease,
        ) -> int:
            return engine.compare_precedence(left.version, right.version)

        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=cmp_to_key(compare_releases), reverse=True)

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # Precondition: unregistered package names MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                f"Package {name!r} is not registered in the repository", name
            )
        # Postcondition: a shallow copy of the descending-precedence release list.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # Postcondition: membership in the package index.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # Postcondition: the set of all registered package names.
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
        # Collaborators are resolved on demand from the lifecycle registry.
        repository = get_singleton(dependency_solver.PackageRepository)
        ranges = get_singleton(semver_range.RangeEngine)

        # Accumulated constraints: package name -> requirements with their requester.
        accumulated: Dict[str, List[_Constraint]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def candidates_for(name: str) -> List[dependency_solver.PackageRelease]:
            # Unregistered packages evaluate to zero candidate releases instead
            # of letting PackageNotFoundError escape the resolution run.
            try:
                available = repository.get_releases(name)
            except dependency_solver.PackageNotFoundError:
                return []
            return [
                release
                for release in available
                if all(
                    ranges.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated[name]
                )
            ]

        def search() -> bool:
            # Postcondition: no unassigned package remains once search succeeds.
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True

            # Minimum Remaining Values selection with lexical tie-breaking.
            candidate_map = {name: candidates_for(name) for name in unassigned}
            selected = min(
                unassigned, key=lambda name: (len(candidate_map[name]), name)
            )
            viable = candidate_map[selected]

            if not viable:
                # Conflict trail records the unsatisfied requirement and the
                # requesting packages, then the branch backtracks.
                requesters = [source for source, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(
                    source for source in requesters if source != "root"
                )
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints "
                    f"from {requesters}"
                )
                return False

            # Value ordering: candidate releases in descending precedence order.
            for candidate in viable:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, _Constraint]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # Forward check: a requirement on an already assigned
                        # package must hold immediately or the branch fails.
                        if not ranges.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires "
                                f"'{dependency.name}' {dependency.range_constraint}"
                            )
                            break
                    else:
                        entry: _Constraint = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and search():
                    return True

                # Undo the branch: drop introduced constraints and the assignment
                # so the next candidate can be explored.
                for name, entry in newly_added:
                    accumulated[name].remove(entry)
                    if not accumulated[name]:
                        del accumulated[name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if search():
            # Postcondition: the outcome reports the selected versions and the
            # ordered sequence of decision steps.
            selected_versions = {
                name: release.version for name, release in assignment.items()
            }
            return dependency_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        # Postcondition: an exhaustive failed search raises ResolutionConflictError
        # carrying the involved packages and the accumulated explanation. Every
        # failing search path first records a conflict-trail entry, so the trail
        # is necessarily non-empty here.
        explanation = "\n".join(conflict_trail)
        raise dependency_solver.ResolutionConflictError(
            f"Unable to resolve dependencies: {explanation}",
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
# LAST_CLEANED: 2026-11-05T17:39:13Z
# LAST_CHANGED: 2026-11-05T17:00:24Z
# CHANGE: Prune unreachable empty-conflict-trail fallback: every failing search path records a conflict-trail entry before returning False, so the exhaustive-failure ResolutionConflictError now derives explanation directly from the accumulated trail (no dead branch), per the feedback.
# COVERAGE_AUDIT: 2026-11-05T17:02:59Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:39:13Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:38:50Z
# QA_AUDIT: 2026-11-05T17:02:43Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum
import re

from support.lib.framework import data_type, operation, poly_type

# Requirements specified in semver_core.pyi

# SemVer 2.0.0 grammar: numeric identifiers without leading zeroes, optional
# dot-separated pre-release identifiers, and optional dot-separated build metadata.
_SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)

# Numeric pre-release identifiers are compared as integers, never as text.
_NUMERIC_IDENTIFIER = re.compile(r"^[0-9]+$")


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    # Postcondition: string rendering exposes the diagnostic message verbatim.
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered."""

    # Structured attribute carrying the original rejected version text.
    raw_text: str

    def __str__(self) -> str:
        return self.message


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
        # Postcondition: a version is a pre-release exactly when it declares
        # one or more pre-release identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Postcondition: canonical SemVer 2.0.0 rendering of the numeric
        # components plus optional pre-release and build metadata segments.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += "-" + ".".join(self.prerelease)
        if self.build:
            text += "+" + ".".join(self.build)
        return text

    def __str__(self) -> str:
        # Postcondition: string rendering is equivalent to format().
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
# LAST_CLEANED: 2026-11-05T16:57:09Z
# LAST_CHANGED: 2026-11-05T16:57:09Z
# CHANGE: Implement SemVer 2.0.0 interface: immutable Version record with is_prerelease/format/__str__, ComparatorOp enum, dataclass SemVerError/InvalidVersionError with message diagnostics, and abstract VersionEngine protocol via @poly_type.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations
import re
from typing import Optional
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 grammar: non-negative numeric identifiers without leading zeroes,
# optional dot-separated pre-release identifiers, and optional build metadata.
_SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)

# Numeric pre-release identifiers are compared as integers, never as text.
_NUMERIC_IDENTIFIER = re.compile(r"^[0-9]+$")


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        # Precondition: malformed text or numeric identifiers with leading zeroes
        # MUST raise InvalidVersionError.
        match = _SEMVER_PATTERN.fullmatch(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                f"Invalid semantic version string: {text!r}", text
            )

        # Postcondition: valid text parses into major, minor, patch, pre-release,
        # and build metadata components of an immutable Version record.
        prerelease_text = match.group("prerelease")
        build_text = match.group("build")
        return semver_core.Version(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=tuple(prerelease_text.split(".")) if prerelease_text else (),
            build=tuple(build_text.split(".")) if build_text else (),
        )

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        # Postcondition: major, minor, and patch are compared numerically first.
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1

        # Postcondition: build metadata is ignored entirely, so only the
        # pre-release segment sequences decide the remaining precedence.
        left = v1.prerelease
        right = v2.prerelease

        # Postcondition: a normal version outranks an otherwise identical
        # pre-release version.
        if not left and not right:
            return 0
        if not left:
            return 1
        if not right:
            return -1

        # Postcondition: pre-release segments compare position by position,
        # numerically when both are numeric, ASCII-lexicographically when both
        # are textual, and numeric ranks below textual.
        for left_id, right_id in zip(left, right):
            left_numeric = _NUMERIC_IDENTIFIER.fullmatch(left_id) is not None
            right_numeric = _NUMERIC_IDENTIFIER.fullmatch(right_id) is not None
            if left_numeric and right_numeric:
                left_value = int(left_id)
                right_value = int(right_id)
                if left_value != right_value:
                    return -1 if left_value < right_value else 1
            elif left_numeric:
                return -1
            elif right_numeric:
                return 1
            elif left_id != right_id:
                return -1 if left_id < right_id else 1

        # Postcondition: when the common prefix matches, the longer pre-release
        # segment sequence ranks higher.
        if len(left) != len(right):
            return -1 if len(left) < len(right) else 1
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
# LAST_CLEANED: 2026-11-05T17:35:29Z
# LAST_CHANGED: 2026-11-05T16:57:59Z
# CHANGE: Implement VersionEngine singleton: SemVer 2.0.0 grammar regex parsing rejecting malformed text and leading zeroes with InvalidVersionError, plus full precedence comparison of numeric components, prerelease ranking (normal above prerelease, numeric below text, longer sequences higher), and build-metadata exclusion.
# COVERAGE_AUDIT: 2026-11-05T16:59:01Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:35:29Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:33:19Z
# QA_AUDIT: 2026-11-05T16:58:35Z
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

    # Structured attribute carrying the original rejected range expression.
    raw_range: str

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        # Postcondition: string rendering exposes the raw range text representation.
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
# LAST_CLEANED: 2026-11-05T16:57:31Z
# LAST_CHANGED: 2026-11-05T16:57:31Z
# CHANGE: Implement range interface: InvalidRangeError with raw_range diagnostic, frozen VersionRange value object with canonical __str__, and abstract RangeEngine protocol for range parsing and constraint satisfaction.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations
import re
from dataclasses import dataclass
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

# Requirements specified in semver_range_impl.pyi

# A single relational comparator: (operator, boundary version).
_Comparator = Tuple[semver_core.ComparatorOp, semver_core.Version]

# A clause compiles to a disjunction of comparators conjunctions (disjunctive
# normal form); the whole range is the union of all clause alternatives.
_Alternatives = List[List[_Comparator]]

# Wildcard targets: bare wildcards, major wildcards, and minor wildcards.
_WILDCARD_ANY_PATTERN = re.compile(r"(?:\*|[xX])")
_WILDCARD_MAJOR_PATTERN = re.compile(r"(0|[1-9]\d*)\.[xX*]")
_WILDCARD_MINOR_PATTERN = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.[xX*]")

# Hyphen ranges require whitespace around the separator so that pre-release
# hyphens (e.g. 1.0.0-alpha) are never mistaken for range separators.
_HYPHEN_RANGE_PATTERN = re.compile(r"(\S+)\s+-\s+(\S+)")

# Comparators within a clause are delimited strictly by whitespace; an optional
# relational/prefix operator may be separated from its target by whitespace too.
_CLAUSE_TOKEN_PATTERN = re.compile(r"\s*(?:(==|>=|<=|!=|=|<|>|\^|~)\s*)?(\S+)")


@dataclass(frozen=True)
class _Target:
    """Parsed range target: a full version or a wildcard-truncated numeric prefix."""
    version: Optional[semver_core.Version]
    major: Optional[int]
    minor: Optional[int]


def _invalid(source: str, detail: str) -> semver_range.InvalidRangeError:
    # Postcondition: malformed range syntax raises InvalidRangeError carrying the
    # original rejected expression in raw_range.
    return semver_range.InvalidRangeError(
        f"Invalid version range expression {source!r}: {detail}", source
    )


def _version_engine() -> semver_core.VersionEngine:
    """Resolves the collaborating version engine used for parsing and precedence."""
    return get_singleton(semver_core.VersionEngine)


def _parse_target(text: str, engine: semver_core.VersionEngine, source: str) -> _Target:
    # Postcondition: wildcards (*, x, X, M.x, M.*, M.m.x, M.m.*) are accepted.
    if _WILDCARD_ANY_PATTERN.fullmatch(text):
        return _Target(None, None, None)
    minor_match = _WILDCARD_MINOR_PATTERN.fullmatch(text)
    if minor_match is not None:
        return _Target(None, int(minor_match.group(1)), int(minor_match.group(2)))
    major_match = _WILDCARD_MAJOR_PATTERN.fullmatch(text)
    if major_match is not None:
        return _Target(None, int(major_match.group(1)), None)

    # Precondition: bare partial versions lacking wildcard characters (such as
    # '1', '1.2', '^0.0', or '1.2 - 2.3') MUST raise InvalidRangeError, which is
    # reported here because full SemVer parsing rejects them.
    try:
        version = engine.parse_version(text)
    except semver_core.InvalidVersionError as error:
        raise _invalid(source, f"malformed version {text!r}") from error
    return _Target(version, version.major, version.minor)


def _target_lower(target: _Target) -> semver_core.Version:
    # Inclusive lower boundary of a wildcard prefix; a full version is its own
    # boundary (pre-release identifiers included).
    if target.version is not None:
        return target.version
    if target.major is None:
        return semver_core.Version(0, 0, 0)
    if target.minor is None:
        return semver_core.Version(target.major, 0, 0)
    return semver_core.Version(target.major, target.minor, 0)


def _target_upper(target: _Target) -> Optional[semver_core.Version]:
    # Exclusive upper boundary of a wildcard prefix; None denotes "unbounded".
    if target.version is not None or target.major is None:
        return None
    if target.minor is None:
        return semver_core.Version(target.major + 1, 0, 0)
    return semver_core.Version(target.major, target.minor + 1, 0)


def _any_alternatives() -> _Alternatives:
    # Vacuously satisfied conjunction: matches every candidate version.
    return [[]]


def _impossible_alternatives() -> _Alternatives:
    # Contradictory conjunction: >= 0.0.0 and < 0.0.0 is never satisfiable.
    return [[
        (semver_core.ComparatorOp.GE, semver_core.Version(0, 0, 0)),
        (semver_core.ComparatorOp.LT, semver_core.Version(0, 0, 0)),
    ]]


def _caret_alternatives(target: _Target) -> _Alternatives:
    # Caret prefixes expand around the first non-zero numeric component.
    if target.version is not None:
        version = target.version
        if version.major > 0:
            upper = semver_core.Version(version.major + 1, 0, 0)
        elif version.minor > 0:
            upper = semver_core.Version(version.major, version.minor + 1, 0)
        else:
            upper = semver_core.Version(version.major, version.minor, version.patch + 1)
        return [[(semver_core.ComparatorOp.GE, version), (semver_core.ComparatorOp.LT, upper)]]
    if target.major is None:
        return _any_alternatives()
    if target.minor is None:
        return [[
            (semver_core.ComparatorOp.GE, semver_core.Version(target.major, 0, 0)),
            (semver_core.ComparatorOp.LT, semver_core.Version(target.major + 1, 0, 0)),
        ]]
    # Major and minor known, patch wildcard: the first non-zero component still
    # decides the upper boundary, so a non-zero major bumps the major boundary
    # (e.g. ^1.2.x is >=1.2.0 <2.0.0) while a zero major bumps the minor one
    # (e.g. ^0.0.x is >=0.0.0 <0.1.0).
    if target.major > 0:
        patch_wildcard_upper = semver_core.Version(target.major + 1, 0, 0)
    else:
        patch_wildcard_upper = semver_core.Version(target.major, target.minor + 1, 0)
    return [[
        (semver_core.ComparatorOp.GE, semver_core.Version(target.major, target.minor, 0)),
        (semver_core.ComparatorOp.LT, patch_wildcard_upper),
    ]]


def _tilde_alternatives(target: _Target) -> _Alternatives:
    # Tilde prefixes expand into lower and upper minor boundaries.
    if target.version is not None:
        version = target.version
        upper = semver_core.Version(version.major, version.minor + 1, 0)
        return [[(semver_core.ComparatorOp.GE, version), (semver_core.ComparatorOp.LT, upper)]]
    if target.major is None:
        return _any_alternatives()
    if target.minor is None:
        return [[
            (semver_core.ComparatorOp.GE, semver_core.Version(target.major, 0, 0)),
            (semver_core.ComparatorOp.LT, semver_core.Version(target.major + 1, 0, 0)),
        ]]
    return [[
        (semver_core.ComparatorOp.GE, semver_core.Version(target.major, target.minor, 0)),
        (semver_core.ComparatorOp.LT, semver_core.Version(target.major, target.minor + 1, 0)),
    ]]


def _expand_comparator(prefix: str, target: _Target) -> _Alternatives:
    # Caret and tilde prefixes expand into paired comparator inequalities.
    if prefix == "^":
        return _caret_alternatives(target)
    if prefix == "~":
        return _tilde_alternatives(target)

    upper = _target_upper(target)
    lower = _target_lower(target)

    if prefix in ("=", "=="):
        # Equality with a wildcard prefix normalizes into range membership.
        if target.version is not None:
            return [[(semver_core.ComparatorOp.EQ, target.version)]]
        if upper is None:
            return _any_alternatives()
        return [[(semver_core.ComparatorOp.GE, lower), (semver_core.ComparatorOp.LT, upper)]]

    if prefix == "!=":
        # Inequality with a wildcard prefix is the complement of the prefix range,
        # which is representable as a union of two alternatives.
        if target.version is not None:
            return [[(semver_core.ComparatorOp.NE, target.version)]]
        if upper is None:
            return _impossible_alternatives()
        return [
            [(semver_core.ComparatorOp.LT, lower)],
            [(semver_core.ComparatorOp.GE, upper)],
        ]

    if prefix == ">=":
        if target.version is not None:
            return [[(semver_core.ComparatorOp.GE, target.version)]]
        if upper is None:
            return _any_alternatives()
        return [[(semver_core.ComparatorOp.GE, lower)]]

    if prefix == ">":
        if target.version is not None:
            return [[(semver_core.ComparatorOp.GT, target.version)]]
        if upper is None:
            return _impossible_alternatives()
        return [[(semver_core.ComparatorOp.GE, upper)]]

    if prefix == "<=":
        if target.version is not None:
            return [[(semver_core.ComparatorOp.LE, target.version)]]
        if upper is None:
            return _any_alternatives()
        return [[(semver_core.ComparatorOp.LT, upper)]]

    # Strict less-than: the last relational operator produced by the tokenizer.
    if prefix == "<":
        if target.version is not None:
            return [[(semver_core.ComparatorOp.LT, target.version)]]
        if upper is None:
            return _impossible_alternatives()
        return [[(semver_core.ComparatorOp.LT, lower)]]

    # Unreachable: the clause tokenizer only yields the operators handled above.
    return _impossible_alternatives()  # pragma: no cover (assumption: tokenizer-restricted operator set)


def _hyphen_alternatives(
    low_text: str,
    high_text: str,
    engine: semver_core.VersionEngine,
    source: str,
) -> _Alternatives:
    # A hyphen range normalizes into a paired lower/upper inequality.
    low = _parse_target(low_text, engine, source)
    high = _parse_target(high_text, engine, source)
    comparators: List[_Comparator] = [(semver_core.ComparatorOp.GE, _target_lower(low))]
    if high.version is not None:
        comparators.append((semver_core.ComparatorOp.LE, high.version))
    else:
        high_upper = _target_upper(high)
        if high_upper is not None:
            comparators.append((semver_core.ComparatorOp.LT, high_upper))
    return [comparators]


def _compile_clause(
    clause: str,
    engine: semver_core.VersionEngine,
    source: str,
) -> _Alternatives:
    hyphen = _HYPHEN_RANGE_PATTERN.fullmatch(clause)
    if hyphen is not None:
        return _hyphen_alternatives(hyphen.group(1), hyphen.group(2), engine, source)

    # Conjunction of whitespace-delimited comparators; a relational/prefix
    # operator may be separated from its target by optional whitespace.
    alternatives: _Alternatives = [[]]
    position = 0
    while position < len(clause):
        token = _CLAUSE_TOKEN_PATTERN.match(clause, position)
        # Unreachable: a stripped clause always yields a leading token because the
        # token pattern consumes the optional prefix and any non-space remainder.
        if token is None:  # pragma: no cover (assumption: stripped clauses always yield a leading token)
            raise _invalid(source, f"malformed clause {clause!r}")
        prefix = token.group(1) or "="
        target_text = token.group(2)
        target = _parse_target(target_text, engine, source)
        token_alternatives = _expand_comparator(prefix, target)
        alternatives = [
            existing + addition
            for existing in alternatives
            for addition in token_alternatives
        ]
        position = token.end()
    return alternatives


def _compile_range(text: str, engine: semver_core.VersionEngine) -> _Alternatives:
    # Postcondition: surrounding whitespace is trimmed; empty expressions, empty
    # union clauses, and comma delimiters are rejected.
    source = text
    trimmed = text.strip()
    if not trimmed:
        raise _invalid(source, "empty range expression")
    if "," in trimmed:
        raise _invalid(source, "comma delimiters are not permitted")

    alternatives: _Alternatives = []
    for raw_clause in trimmed.split("||"):
        clause = raw_clause.strip()
        if not clause:
            raise _invalid(source, "empty union clause")
        alternatives.extend(_compile_clause(clause, engine, source))
    return alternatives


def _holds(
    engine: semver_core.VersionEngine,
    version: semver_core.Version,
    operator: semver_core.ComparatorOp,
    boundary: semver_core.Version,
) -> bool:
    # Comparator evaluation delegates precedence decisions to the version engine.
    order = engine.compare_precedence(version, boundary)
    if operator is semver_core.ComparatorOp.EQ:
        return order == 0
    if operator is semver_core.ComparatorOp.NE:
        return order != 0
    if operator is semver_core.ComparatorOp.LT:
        return order < 0
    if operator is semver_core.ComparatorOp.LE:
        return order <= 0
    if operator is semver_core.ComparatorOp.GT:
        return order > 0
    return order >= 0


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        # Postcondition: the trimmed range expression is stored verbatim in the
        # produced VersionRange record; malformed syntax raises InvalidRangeError
        # carrying the original supplied text.
        engine = _version_engine()
        _compile_range(text, engine)
        return semver_range.VersionRange(raw_text=text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Postcondition: the candidate satisfies all comparators of at least one
        # union clause, using precedence ordering for every boundary test.
        engine = _version_engine()
        alternatives = _compile_range(range_constraint.raw_text, engine)
        for comparators in alternatives:
            if not all(
                _holds(engine, version, operator, boundary)
                for operator, boundary in comparators
            ):
                continue
            if version.is_prerelease and not include_prerelease:
                # Postcondition: a pre-release candidate matches only when the
                # range explicitly targets it by naming a pre-release identifier
                # sharing the same major, minor, and patch numbers.
                targeted = any(
                    boundary.prerelease
                    and boundary.major == version.major
                    and boundary.minor == version.minor
                    and boundary.patch == version.patch
                    for _, boundary in comparators
                )
                if not targeted:
                    continue
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
# LAST_CLEANED: 2026-11-05T17:39:15Z
# LAST_CHANGED: 2026-11-05T17:34:51Z
# CHANGE: Fix caret expansion for M.m.x/M.m.* wildcard targets to honor first-non-zero component boundaries: ^1.2.x now compiles to >=1.2.0 <2.0.0 (satisfies 1.9.9, rejects 2.0.0), while ^0.0.x yields >=0.0.0 <0.1.0; tilde wildcard form ~1.2.x retains >=1.2.0 <1.3.0 and ^1.x retains >=1.0.0 <2.0.0.
# COVERAGE_AUDIT: 2026-11-05T17:36:56Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:39:15Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:38:52Z
# QA_AUDIT: 2026-11-05T17:36:42Z
# --- END AUTOFAB METADATA ---
