# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_225945_deepseek-flash_semver_solver_multi_combined
# Timestamp: 2026-11-09T22:59:45.102168+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 764,958
#   Cached Inbound Tokens:   56,009,216
#   Outbound Tokens:         633,976
#   Total Tokens:            57,408,150
#   Financial Cost ($USD):   $0.6632
#   Wall Clock Duration:     3339.28s
#   Step Latencies (s):      [446.4, 454.6, 100.8, 58.7, 56.4, 23.4, 639.2, 137.2, 69.6, 102.3, 10.1, 56.0, 347.3, 32.3, 236.0, 74.6, 21.3, 176.8, 20.9, 71.2, 184.6, 55.6, 20.9, 20.9, 237.0, 23.3, 218.1, 148.2, 110.9, 180.9, 23.5, 24.1, 23.4, 153.2, 20.9, 485.1, 20.8, 420.1, 10.1, 290.6, 386.6, 20.8, 76.4, 97.8, 20.9, 10.0]
#   Role Execution Rounds:   coverage: 4, lib: 6, pretense: 7, pretense_coverage: 7, pretense_qa: 11, qa: 6, test: 5 (Total: 46)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       55
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
    package_name: str


@dataclass
class ResolutionConflictError(semver_core.SemVerError):
    conflicting_packages: Tuple[str, ...]
    explanation: str


@data_type
@dataclass(frozen=True)
class PackageDependency:
    name: str
    range_constraint: semver_range.VersionRange


@data_type
@dataclass(frozen=True)
class PackageRelease:
    name: str
    version: semver_core.Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    selected_versions: Mapping[str, semver_core.Version]
    derivation_steps: Tuple[str, ...]


@poly_type
class PackageRepository(Protocol):
    @operation
    def register_package(self, release: PackageRelease) -> None:
        # POSTCONDITIONS: release is registered into the repository.
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        # PRECONDITIONS: unregistered name raises PackageNotFoundError.
        # POSTCONDITIONS: releases are ordered by descending version precedence.
        ...

    @operation
    def has_package(self, name: str) -> bool:
        # POSTCONDITIONS: True exactly when name is registered.
        ...

    @operation
    def all_packages(self) -> Set[str]:
        # POSTCONDITIONS: the set of all registered package names.
        ...


@poly_type
class DependencySolver(Protocol):
    @operation
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        # PRECONDITIONS: unsatisfiable or missing-package dependencies raise
        # ResolutionConflictError (PackageNotFoundError never escapes).
        # POSTCONDITIONS: a mutually compatible highest-precedence assignment with
        # derivation steps is produced in a ResolutionOutcome.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:03:09Z
# LAST_CHANGED: 2026-11-09T23:03:09Z
# CHANGE: Make PackageNotFoundError/ResolutionConflictError mutable dataclass exceptions; annotate PackageDependency/PackageRelease/ResolutionOutcome as data types and protocols as poly types
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
from __future__ import annotations
from functools import cmp_to_key
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi

# Requester label recorded for constraints introduced directly by the caller's roots.
_ROOT_REQUESTER = "root"


def _resolve_precedence() -> Callable[[semver_core.Version, semver_core.Version], int]:
    # Caller precondition: the version engine singleton is registered by its own module.
    engine = get_singleton(semver_core.VersionEngine)
    return lambda v1, v2: engine.compare_precedence(v1, v2)


def _descending_key(
    compare: Callable[[semver_core.Version, semver_core.Version], int],
) -> Callable[[dependency_solver.PackageRelease], Any]:
    # Sorts releases by version precedence from highest to lowest.
    return cmp_to_key(lambda left, right: -compare(left.version, right.version))


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # POSTCONDITIONS: the release is inserted and the package list stays sorted
        # by descending version precedence.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=_descending_key(_resolve_precedence()))

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        releases = self._packages.get(name)
        # PRECONDITIONS: an unregistered name raises PackageNotFoundError.
        if releases is None:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package not found: {name!r}",
                package_name=name,
            )
        # POSTCONDITIONS: descending-precedence releases in a shallow copy.
        return list(releases)

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # POSTCONDITIONS: True exactly when the package name is registered.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # POSTCONDITIONS: the set of all registered package names.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(dependency_solver.DependencySolver):
    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        # Accumulated constraints: package name to (requester, range) requirements.
        accumulated: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                (_ROOT_REQUESTER, dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def satisfies(
            version: semver_core.Version,
            range_constraint: semver_range.VersionRange,
        ) -> bool:
            return range_engine.satisfies(version, range_constraint, False)

        def viable_candidates(name: str) -> List[dependency_solver.PackageRelease]:
            try:
                available = repository.get_releases(name)
            except dependency_solver.PackageNotFoundError:
                # Missing packages are treated as having zero candidate releases.
                return []
            return [
                release
                for release in available
                if all(
                    satisfies(release.version, constraint)
                    for _, constraint in accumulated[name]
                )
            ]

        def record_conflict(name: str) -> None:
            requesters = [requester for requester, _ in accumulated[name]]
            conflicting_packages.add(name)
            for requester in requesters:
                if requester != _ROOT_REQUESTER:
                    conflicting_packages.add(requester)
            conflict_trail.append(
                f"No viable releases for '{name}' satisfying constraints from {requesters}"
            )

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True

            # Minimum Remaining Values heuristic with lexical tie-breaking.
            candidates_map = {
                name: viable_candidates(name) for name in unassigned
            }
            selected = min(
                unassigned,
                key=lambda name: (len(candidates_map[name]), name),
            )
            candidates = candidates_map[selected]
            if not candidates:
                record_conflict(selected)
                return False

            # Explore viable releases in descending version precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # Forward checking: an assigned version must satisfy the
                        # newly discovered requirement.
                        if not satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and backtrack():
                    return True

                # Undo the assignment and any constraints introduced by this branch.
                for package_name, entry in newly_added:
                    accumulated[package_name].remove(entry)
                    if not accumulated[package_name]:
                        del accumulated[package_name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if backtrack():
            selected_versions: Dict[str, semver_core.Version] = {
                name: release.version for name, release in assignment.items()
            }
            # POSTCONDITIONS: compatible highest-precedence assignment plus the
            # ordered decision sequence.
            return dependency_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        # PRECONDITIONS: unsatisfiable or missing-package dependencies raise
        # ResolutionConflictError instead of letting PackageNotFoundError escape.
        # A failed search always records at least one conflict entry, so the trail
        # is non-empty and provides the diagnostic derivation directly.
        raise dependency_solver.ResolutionConflictError(
            message="Unable to resolve package dependencies",
            conflicting_packages=tuple(sorted(conflicting_packages)),
            explanation="; ".join(conflict_trail),
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
# LAST_CLEANED: 2026-11-09T23:41:22Z
# LAST_CHANGED: 2026-11-09T23:26:19Z
# CHANGE: Resolve pretense_coverage feedback dependency_solver.solver.unsatisfiable_conflict (unreachable logic: empty conflict trail explanation fallback). The 'No viable release candidates were found.' fallback was dead: any False return from backtrack() necessarily appends to conflict_trail, either via record_conflict when the selected package has no viable candidates, via the forward-checking conflict branch, or by induction through recursive branch failures. The conflict trail is therefore never empty on the unsatisfiable path, so the fallback branch was pruned and the explanation is now passed directly as '; '.join(conflict_trail), preserving the ResolutionConflictError message, conflicting_packages, and non-empty diagnostic derivation behavior.
# COVERAGE_AUDIT: 2026-11-09T23:27:07Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T23:41:22Z
# PRETENSE_QA_AUDIT: 2026-11-09T23:41:10Z
# QA_AUDIT: 2026-11-09T23:26:39Z
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
    message: str

    def __str__(self) -> str:
        # Diagnostic representation delegates to the canonical message.
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    raw_text: str


class ComparatorOp(enum.Enum):
    EQ = '=='
    NE = '!='
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='


@data_type
@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        # A version is a prerelease precisely when prerelease identifiers are present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Canonical SemVer 2.0.0 rendering: numeric triple, optional prerelease, optional build.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += "-" + ".".join(self.prerelease)
        if self.build:
            text += "+" + ".".join(self.build)
        return text

    def __str__(self) -> str:
        # Equivalent to format().
        return self.format()


@poly_type
class VersionEngine(Protocol):
    @operation
    def parse_version(self, text: str) -> Version:
        # PRECONDITIONS: leading zeroes or grammar violations raise InvalidVersionError.
        # POSTCONDITIONS: valid SemVer 2.0.0 text yields a Version record.
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # POSTCONDITIONS: tri-state precedence under SemVer 2.0.0 rules.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:02:00Z
# LAST_CHANGED: 2026-11-09T23:02:00Z
# CHANGE: Implement SemVerError/InvalidVersionError as mutable dataclass exceptions with str(message); implement Version.is_prerelease/format/__str__ and annotate Version/VersionEngine with framework decorators
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations
import re
from typing import Optional
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 grammar: numeric triple without leading zeroes, optional prerelease,
# and optional build metadata; prerelease numeric identifiers also forbid leading zeroes.
_VERSION_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        # PRECONDITIONS: leading zeroes or grammar violations raise InvalidVersionError.
        match = _VERSION_PATTERN.fullmatch(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                message=f"Invalid semantic version: {text!r}",
                raw_text=text,
            )
        # POSTCONDITIONS: valid SemVer 2.0.0 text yields a Version record.
        prerelease_text = match.group(4)
        build_text = match.group(5)
        prerelease: tuple[str, ...] = (
            tuple(prerelease_text.split(".")) if prerelease_text else ()
        )
        build: tuple[str, ...] = tuple(build_text.split(".")) if build_text else ()
        return semver_core.Version(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=prerelease,
            build=build,
        )

    @operation
    @override
    def compare_precedence(self, v1: semver_core.Version, v2: semver_core.Version) -> int:
        # POSTCONDITIONS: major, minor, and patch compare numerically in sequence.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return -1 if left < right else 1

        # POSTCONDITIONS: normal versions rank higher than prerelease versions.
        pre1 = v1.prerelease
        pre2 = v2.prerelease
        if not pre1 and not pre2:
            return 0
        if not pre1:
            return 1
        if not pre2:
            return -1

        # POSTCONDITIONS: numeric segments compare numerically and rank below string
        # segments, string segments compare ASCII-lexicographically, and longer
        # sequences rank higher when the common prefix matches.
        for left, right in zip(pre1, pre2):
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                left_value = int(left)
                right_value = int(right)
                if left_value != right_value:
                    return -1 if left_value < right_value else 1
            elif left_numeric:
                return -1
            elif right_numeric:
                return 1
            elif left != right:
                return -1 if left < right else 1

        if len(pre1) != len(pre2):
            return -1 if len(pre1) < len(pre2) else 1
        # POSTCONDITIONS: build metadata is excluded entirely from comparison.
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
# LAST_CLEANED: 2026-11-09T23:18:13Z
# LAST_CHANGED: 2026-11-09T23:02:40Z
# CHANGE: Implement VersionEngine.parse_version via SemVer 2.0.0 regex (leading-zero rejection, prerelease/build tuples) and compare_precedence (numeric triples, prerelease ranking, build exclusion); annotate singleton with tier
# COVERAGE_AUDIT: 2026-11-09T23:18:13Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T23:16:40Z
# PRETENSE_QA_AUDIT: 2026-11-09T23:16:03Z
# QA_AUDIT: 2026-11-09T23:18:00Z
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
    raw_range: str


@data_type
@dataclass(frozen=True)
class VersionRange:
    raw_text: str

    def __str__(self) -> str:
        # Canonical representation is the trimmed raw range text.
        return self.raw_text


@poly_type
class RangeEngine(Protocol):
    @operation
    def parse_range(self, text: str) -> VersionRange:
        # PRECONDITIONS: bare partial versions, empty/whitespace input, empty union
        # clauses, commas, or malformed syntax raise InvalidRangeError.
        # POSTCONDITIONS: trimmed range text is stored in VersionRange.raw_text.
        ...

    @operation
    def satisfies(self, version: semver_core.Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        # POSTCONDITIONS: boolean match honoring prerelease filtering and precedence.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:02:54Z
# LAST_CHANGED: 2026-11-09T23:02:54Z
# CHANGE: Make InvalidRangeError a mutable dataclass exception; implement VersionRange.__str__; annotate VersionRange/RangeEngine with framework decorators
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

# SemVer 2.0.0 grammar shared with the version engine: numeric triple without
# leading zeroes, optional prerelease identifiers, and optional build metadata.
_VERSION_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)

_PREFIX_PATTERN = re.compile(r"^(>=|<=|==|!=|=|>|<|\^|~)(.*)$")

_PURE_OPERATORS = frozenset({">=", "<=", "==", "!=", ">", "<", "=", "^", "~"})

_WILDCARD_SEGMENTS = frozenset({"x", "X", "*"})

# A compiled comparator is an operator paired with its concrete boundary version.
_Comparator = Tuple[str, semver_core.Version]
# A group is a disjunction of comparators; a clause is a conjunction of groups.
_Group = List[_Comparator]
_Clause = List[_Group]


@dataclass(frozen=True)
class _Spec:
    numbers: Tuple[int, ...]
    prerelease: Tuple[str, ...]
    build: Tuple[str, ...]
    wildcard: bool


def _invalid(raw_text: str) -> semver_range.InvalidRangeError:
    return semver_range.InvalidRangeError(
        message=f"Invalid version range: {raw_text!r}",
        raw_range=raw_text,
    )


def _parse_number(segment: str, raw_text: str) -> int:
    # Numeric identifiers forbid leading zeroes just like SemVer numeric components.
    if not segment.isdigit() or (len(segment) > 1 and segment.startswith("0")):
        raise _invalid(raw_text)
    return int(segment)


def _parse_spec(spec_text: str, raw_text: str) -> _Spec:
    segments = spec_text.split(".")
    wildcard_index: Optional[int] = None
    for index, segment in enumerate(segments):
        if segment in _WILDCARD_SEGMENTS:
            wildcard_index = index
            break
    # Wildcards may only replace minor/patch components, so a wildcard expression
    # carries at most two leading numeric segments. Longer wildcard forms are
    # malformed and fall through to the strict version grammar below for rejection.
    if wildcard_index is not None and wildcard_index <= 2:
        # Wildcards must terminate the expression and may only replace minor/patch.
        if any(segment not in _WILDCARD_SEGMENTS for segment in segments[wildcard_index:]):
            raise _invalid(raw_text)
        numbers = tuple(
            _parse_number(segment, raw_text) for segment in segments[:wildcard_index]
        )
        return _Spec(numbers=numbers, prerelease=(), build=(), wildcard=True)
    # Bare partial expressions lacking wildcards (for example '1' or '1.2') are invalid.
    match = _VERSION_PATTERN.fullmatch(spec_text)
    if match is None:
        raise _invalid(raw_text)
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    build = tuple(match.group(5).split(".")) if match.group(5) else ()
    return _Spec(
        numbers=(int(match.group(1)), int(match.group(2)), int(match.group(3))),
        prerelease=prerelease,
        build=build,
        wildcard=False,
    )


def _full_version(spec: _Spec) -> semver_core.Version:
    numbers = spec.numbers
    return semver_core.Version(
        numbers[0],
        numbers[1],
        numbers[2],
        spec.prerelease,
        spec.build,
    )


def _lower_version(spec: _Spec) -> Optional[semver_core.Version]:
    # '*' and 'x' have no lower numeric bound; partial wildcards pad missing components with zero.
    if spec.wildcard and not spec.numbers:
        return None
    numbers = spec.numbers + (0,) * (3 - len(spec.numbers))
    return semver_core.Version(numbers[0], numbers[1], numbers[2])


def _wildcard_upper(spec: _Spec) -> Optional[semver_core.Version]:
    # Exclusive upper bound of a wildcard band: '1.x' -> 2.0.0, '1.2.x' -> 1.3.0.
    count = len(spec.numbers)
    if count == 0:
        return None
    if count == 1:
        return semver_core.Version(spec.numbers[0] + 1, 0, 0)
    return semver_core.Version(spec.numbers[0], spec.numbers[1] + 1, 0)


def _caret_upper_full(version: semver_core.Version) -> semver_core.Version:
    # Caret allows changes that do not modify the left-most non-zero component.
    if version.major > 0:
        return semver_core.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_core.Version(0, version.minor + 1, 0)
    return semver_core.Version(0, 0, version.patch + 1)


def _caret_upper_wildcard(spec: _Spec) -> Optional[semver_core.Version]:
    # Caret on a wildcard expands from the first specified non-zero component boundary.
    count = len(spec.numbers)
    if count == 0:
        # A bare wildcard caret ('^*') is universal and imposes no finite upper bound.
        return None
    if count == 1:
        return semver_core.Version(spec.numbers[0] + 1, 0, 0)
    if spec.numbers[0] > 0:
        return semver_core.Version(spec.numbers[0] + 1, 0, 0)
    return semver_core.Version(0, spec.numbers[1] + 1, 0)


def _tilde_upper_full(version: semver_core.Version) -> semver_core.Version:
    # Tilde allows patch-level changes when a minor component is specified.
    return semver_core.Version(version.major, version.minor + 1, 0)


def _tilde_upper_wildcard(spec: _Spec) -> Optional[semver_core.Version]:
    # Tilde on a wildcard expands to the next minor (or next major for '~N.x').
    count = len(spec.numbers)
    if count == 0:
        # A bare wildcard tilde ('~*') is universal and imposes no finite upper bound.
        return None
    if count == 1:
        return semver_core.Version(spec.numbers[0] + 1, 0, 0)
    return semver_core.Version(spec.numbers[0], spec.numbers[1] + 1, 0)


def _expand(
    operator: str,
    spec: _Spec,
) -> Tuple[_Clause, List[semver_core.Version]]:
    if not spec.wildcard:
        version = _full_version(spec)
        referenced = [version]
        if operator in ("", "=", "=="):
            return [[("==", version)]], referenced
        if operator == "!=":
            return [[("!=", version)]], referenced
        if operator in ("<", "<=", ">", ">="):
            return [[(operator, version)]], referenced
        if operator == "^":
            return [[(">=", version)], [("<", _caret_upper_full(version))]], referenced
        # '~' expands to a lower bound plus the next minor upper bound.
        return [[(">=", version)], [("<", _tilde_upper_full(version))]], referenced

    lower = _lower_version(spec)
    upper = _wildcard_upper(spec)
    if operator in ("", "=", "=="):
        if lower is None or upper is None:
            # '==*' accepts every version, so it imposes no clause constraints.
            return [], []
        return [[(">=", lower)], [("<", upper)]], []
    if operator == "!=":
        if lower is None or upper is None:
            # '!=*' excludes every version via an unsatisfiable empty disjunction.
            return [[]], []
        return [[("<", lower), (">=", upper)]], []
    if operator == ">=":
        if lower is None:
            return [], []
        return [[(">=", lower)]], []
    if operator == ">":
        if upper is None:
            return [[]], []
        # Strictly greater than every version in the wildcard band.
        return [[(">=", upper)]], []
    if operator == "<":
        if lower is None:
            return [[]], []
        return [[("<", lower)]], []
    if operator == "<=":
        if upper is None:
            return [], []
        return [[("<", upper)]], []
    if operator == "^":
        caret_upper = _caret_upper_wildcard(spec)
        if caret_upper is None:
            # '^*' is universal: every version satisfies it, so no constraints.
            return [], []
        caret_lower = lower if lower is not None else semver_core.Version(0, 0, 0)
        return [[(">=", caret_lower)], [("<", caret_upper)]], []
    # '~' on a wildcard expands to lower plus the next minor/major boundary.
    tilde_upper = _tilde_upper_wildcard(spec)
    if tilde_upper is None:
        # '~*' is universal: every version satisfies it, so no constraints.
        return [], []
    tilde_lower = lower if lower is not None else semver_core.Version(0, 0, 0)
    return [[(">=", tilde_lower)], [("<", tilde_upper)]], []


def _compile_comparator(
    token: str,
    raw_text: str,
) -> Tuple[_Clause, List[semver_core.Version]]:
    match = _PREFIX_PATTERN.match(token)
    if match is not None:
        operator = match.group(1)
        spec_text = match.group(2).strip()
    else:
        operator = ""
        spec_text = token
    if not spec_text:
        raise _invalid(raw_text)
    return _expand(operator, _parse_spec(spec_text, raw_text))


def _compile_hyphen(
    lower_text: str,
    upper_text: str,
    raw_text: str,
) -> Tuple[_Clause, List[semver_core.Version]]:
    lower_spec = _parse_spec(lower_text, raw_text)
    upper_spec = _parse_spec(upper_text, raw_text)
    groups: _Clause = []
    referenced: List[semver_core.Version] = []
    if lower_spec.wildcard:
        lower = _lower_version(lower_spec)
        if lower is not None:
            groups.append([(">=", lower)])
    else:
        lower_version = _full_version(lower_spec)
        groups.append([(">=", lower_version)])
        referenced.append(lower_version)
    if upper_spec.wildcard:
        upper = _wildcard_upper(upper_spec)
        if upper is not None:
            groups.append([("<", upper)])
    else:
        upper_version = _full_version(upper_spec)
        groups.append([("<=", upper_version)])
        referenced.append(upper_version)
    return groups, referenced


def _merge_tokens(tokens: List[str]) -> List[str]:
    # Relational and prefix operators may be separated from their target by whitespace.
    merged: List[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _PURE_OPERATORS and index + 1 < len(tokens):
            # Attach a standalone operator to the operand that follows it; a
            # trailing operator lacks an operand and is rejected by the
            # comparator compilation grammar.
            merged.append(token + tokens[index + 1])
            index += 2
            continue
        merged.append(token)
        index += 1
    return merged


def _compile_clause(
    clause_text: str,
    raw_text: str,
) -> Tuple[_Clause, List[semver_core.Version]]:
    tokens = clause_text.split()
    if "-" in tokens:
        # Hyphen ranges connect exactly two bounds and cannot mix with other comparators.
        if len(tokens) != 3 or tokens[1] != "-":
            raise _invalid(raw_text)
        return _compile_hyphen(tokens[0], tokens[2], raw_text)
    groups: _Clause = []
    referenced: List[semver_core.Version] = []
    for token in _merge_tokens(tokens):
        comparator_groups, comparator_referenced = _compile_comparator(token, raw_text)
        groups.extend(comparator_groups)
        referenced.extend(comparator_referenced)
    return groups, referenced


def _compile_range(
    raw_text: str,
) -> Tuple[List[_Clause], set[Tuple[int, int, int]]]:
    clauses: List[_Clause] = []
    prerelease_targets: set[Tuple[int, int, int]] = set()
    for clause_text in raw_text.split("||"):
        clause_text = clause_text.strip()
        if not clause_text:
            raise _invalid(raw_text)
        groups, referenced = _compile_clause(clause_text, raw_text)
        clauses.append(groups)
        for version in referenced:
            if version.prerelease:
                prerelease_targets.add((version.major, version.minor, version.patch))
    return clauses, prerelease_targets


def _resolve_precedence() -> Callable[[semver_core.Version, semver_core.Version], int]:
    # Caller precondition: the version engine singleton is registered by its own module.
    engine = get_singleton(semver_core.VersionEngine)
    return lambda v1, v2: engine.compare_precedence(v1, v2)


def _compare_satisfies(operator: str, comparison: int) -> bool:
    if operator == "==":
        return comparison == 0
    if operator == "!=":
        return comparison != 0
    if operator == "<":
        return comparison < 0
    if operator == "<=":
        return comparison <= 0
    if operator == ">":
        return comparison > 0
    return comparison >= 0


def _clause_satisfied(
    clause: _Clause,
    version: semver_core.Version,
    compare: Callable[[semver_core.Version, semver_core.Version], int],
) -> bool:
    for group in clause:
        # Each group is a disjunction; a single matching comparator satisfies it.
        if not any(
            _compare_satisfies(operator, compare(version, boundary))
            for operator, boundary in group
        ):
            return False
    return True


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    tier = system

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        trimmed = text.strip()
        # PRECONDITIONS: empty, whitespace-only, empty-clause, and comma-delimited
        # expressions are malformed.
        if not trimmed or "," in trimmed:
            raise _invalid(text)
        # Validates every clause and comparator, raising InvalidRangeError on any defect.
        # The raised error preserves the original malformed expression text, not the
        # trimmed spelling, per the raw_range contract.
        try:
            _compile_range(trimmed)
        except semver_range.InvalidRangeError as error:
            raise _invalid(text) from error
        # POSTCONDITIONS: VersionRange holds the trimmed range expression.
        return semver_range.VersionRange(raw_text=trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        clauses, prerelease_targets = _compile_range(range_constraint.raw_text)
        # POSTCONDITIONS: prereleases are filtered unless explicitly targeted by a
        # comparator with prerelease identifiers on the same major/minor/patch triple.
        if version.is_prerelease and not include_prerelease:
            triple = (version.major, version.minor, version.patch)
            if triple not in prerelease_targets:
                return False
        engine_compare = _resolve_precedence()
        # POSTCONDITIONS: True when any union alternative is fully satisfied.
        for clause in clauses:
            if _clause_satisfied(clause, version, engine_compare):
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
# LAST_CLEANED: 2026-11-09T23:55:20Z
# LAST_CHANGED: 2026-11-09T23:25:34Z
# CHANGE: Resolve coverage feedback on semver_range.parse_range.malformed_syntax by removing the two uncontracted defensive validation guards while preserving InvalidRangeError behavior. (1) Over-long wildcard component-count guard: _parse_spec now enters the wildcard branch only when the wildcard index is <= 2 (i.e. wildcards replace only minor/patch); forms with extra numeric components such as '1.2.3.x' fall through to the strict SemVer grammar (_VERSION_PATTERN.fullmatch) which rejects them via the contracted malformed-syntax path. (2) Operator-adjacency empty-operand guard: _merge_tokens no longer raises directly for a trailing standalone operator; it lets the bare operator token flow to _compile_comparator, whose contracted empty-operand check raises InvalidRangeError. The now-unused raw_text parameter was dropped from _merge_tokens. Observable behavior is unchanged for all malformed inputs (same error type, message, and raw_range), and no uncontracted validation branches remain.
# COVERAGE_AUDIT: 2026-11-09T23:27:13Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T23:55:20Z
# PRETENSE_QA_AUDIT: 2026-11-09T23:54:57Z
# QA_AUDIT: 2026-11-09T23:26:42Z
# --- END AUTOFAB METADATA ---
