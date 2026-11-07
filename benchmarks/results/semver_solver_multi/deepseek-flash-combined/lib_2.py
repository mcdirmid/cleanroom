# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261107_014900_deepseek-flash_semver_solver_multi_combined
# Timestamp: 2026-11-07T01:49:00.194821+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 550,496
#   Cached Inbound Tokens:   53,267,456
#   Outbound Tokens:         543,527
#   Total Tokens:            54,361,479
#   Financial Cost ($USD):   $0.5685
#   Wall Clock Duration:     2332.56s
#   Step Latencies (s):      [372.8, 385.3, 20.7, 194.5, 656.9, 112.4, 55.2, 44.2, 205.8, 44.3, 42.4, 76.2, 167.7, 52.9, 42.0, 352.1, 46.1, 42.4, 212.7, 685.2, 41.9, 75.9, 42.1, 230.3, 63.7, 43.9, 156.5, 44.1, 90.5, 42.1, 65.2, 43.7, 42.0, 43.7, 65.0, 86.3, 41.9, 41.8]
#   Role Execution Rounds:   coverage: 6, lib: 4, pretense: 6, pretense_coverage: 6, pretense_qa: 7, qa: 6, test: 3 (Total: 38)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       78
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
from . import semver_core
from . import semver_range

from support.lib.framework import data_type, operation, poly_type

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
        # POSTCONDITIONS: MUST register the package release into the repository.
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        # PRECONDITIONS: WHEN name is not registered, MUST raise PackageNotFoundError.
        ...

    @operation
    def has_package(self, name: str) -> bool:
        # POSTCONDITIONS: True when the package exists, False otherwise.
        ...

    @operation
    def all_packages(self) -> Set[str]:
        # POSTCONDITIONS: the set of all registered package names.
        ...


@poly_type
class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    @operation
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        # PRECONDITIONS: unsatisfiable or missing dependencies raise ResolutionConflictError.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T01:55:36Z
# LAST_CHANGED: 2026-11-07T01:55:36Z
# CHANGE: Implement dependency solver interface: non-frozen PackageNotFoundError/ResolutionConflictError with structured attributes, frozen PackageDependency/PackageRelease/ResolutionOutcome records, and PackageRepository/DependencySolver protocol stubs aligned with dependency_solver.pyi.
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
from __future__ import annotations
from functools import cmp_to_key
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi

class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # INVARIANTS: _packages maps each package name to its descending-precedence releases.
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # POSTCONDITIONS: MUST register the package release into the repository.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_core.VersionEngine)
        # Re-sorts the release list in descending version precedence order.
        releases.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(right.version, left.version)
            )
        )

    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # PRECONDITIONS: WHEN name is not registered, MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package {name!r} is not registered in the repository",
                package_name=name,
            )
        # POSTCONDITIONS: yields a shallow copy of the sorted release list.
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        # POSTCONDITIONS: True when package name exists in repository, False otherwise.
        return name in self._packages

    def all_packages(self) -> Set[str]:
        # POSTCONDITIONS: produces the set of all registered package names.
        return set(self._packages.keys())


class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        # The solver is stateless across resolution runs; no private backing state is required.
        pass

    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        def satisfies(
            version: semver_core.Version,
            constraint: semver_range.VersionRange,
        ) -> bool:
            return range_engine.satisfies(version, constraint, False)

        # Initializes accumulated constraint mapping and decision queue from root_dependencies.
        accumulated_constraints: Dict[
            str, List[Tuple[str, semver_range.VersionRange]]
        ] = {}
        for dependency in root_dependencies:
            accumulated_constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            unassigned = [
                name for name in accumulated_constraints if name not in assignment
            ]
            if not unassigned:
                # Complete assignment found.
                return True

            candidates_map: Dict[str, List[dependency_solver.PackageRelease]] = {}
            for name in unassigned:
                try:
                    available = repository.get_releases(name)
                except dependency_solver.PackageNotFoundError:
                    # Unregistered packages absent from the repository have zero candidates.
                    available = []
                candidates_map[name] = [
                    release
                    for release in available
                    if all(
                        satisfies(release.version, constraint)
                        for _, constraint in accumulated_constraints[name]
                    )
                ]

            # MRV: selects the package with the fewest viable candidates, ties broken lexically.
            selected = min(unassigned, key=lambda name: (len(candidates_map[name]), name))
            candidates = candidates_map[selected]

            if not candidates:
                requesters = sorted(
                    {
                        source
                        for source, _ in accumulated_constraints[selected]
                        if source != "root"
                    }
                )
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for {selected!r} satisfying constraints from "
                    f"{requesters or ['root requirements']}"
                )
                return False

            # Explores viable candidates in descending version precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign {selected!r} to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []

                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: {selected!r} requires {dependency.name} "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        constraint_entry = (selected, dependency.range_constraint)
                        accumulated_constraints.setdefault(dependency.name, []).append(
                            constraint_entry
                        )
                        newly_added.append((dependency.name, constraint_entry))

                if not conflict_detected and backtrack():
                    return True

                # Backtracks: restores previous constraint mappings and advances to the next branch.
                for package_name, constraint_entry in newly_added:
                    accumulated_constraints[package_name].remove(constraint_entry)
                    if not accumulated_constraints[package_name]:
                        del accumulated_constraints[package_name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if backtrack():
            # Compiles the selected release mapping and decision sequence into the outcome.
            selected_versions = {
                name: release.version for name, release in assignment.items()
            }
            return dependency_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )
        # Raises ResolutionConflictError with the accumulated derivation steps.
        explanation = "\n".join(conflict_trail) or "Dependency constraints are unsatisfiable"
        raise dependency_solver.ResolutionConflictError(
            message=explanation,
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
# LAST_CLEANED: 2026-11-07T02:05:35Z
# LAST_CHANGED: 2026-11-07T01:55:42Z
# CHANGE: Implement PackageRepository singleton with descending-precedence release indexing, PackageNotFoundError on missing names, and copy-on-read; implement DependencySolver singleton backtracking search with MRV selection, descending candidate exploration, forward-checked constraint merging, conflict trail collection and ResolutionConflictError reporting for unsatisfiable or missing packages.
# COVERAGE_AUDIT: 2026-11-07T02:01:59Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T02:05:35Z
# PRETENSE_QA_AUDIT: 2026-11-07T02:05:21Z
# QA_AUDIT: 2026-11-07T02:01:12Z
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
        # Custom exceptions with dataclass semantics render their diagnostic message.
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
        # POSTCONDITIONS: indicates whether pre-release identifiers are present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # POSTCONDITIONS: canonical SemVer 2.0.0 textual form.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # POSTCONDITIONS: equivalent to format().
        return self.format()



@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing and precedence comparison."""

    @operation
    def parse_version(self, text: str) -> Version:
        # PRECONDITIONS: grammar violations or leading zeroes raise InvalidVersionError.
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # POSTCONDITIONS: negative when v1 < v2, zero when equal, positive when v1 > v2.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T01:55:15Z
# LAST_CHANGED: 2026-11-07T01:55:15Z
# CHANGE: Implement SemVer 2.0 core interface: non-frozen dataclass error types with __str__, frozen Version value object with is_prerelease/format/__str__, ComparatorOp enum, and VersionEngine protocol stubs aligned with semver_core.pyi.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations
from typing import Optional, Tuple
import re
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 regular expression grammar: numeric identifiers reject leading zeroes,
# pre-release identifiers are dot-separated and build metadata is dot-separated.
_VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _is_numeric(identifier: str) -> bool:
    # Pre-release numeric identifiers consist solely of ASCII digits.
    return identifier.isdigit()


def _compare_prerelease_identifiers(left: str, right: str) -> int:
    left_numeric = _is_numeric(left)
    right_numeric = _is_numeric(right)
    if left_numeric and right_numeric:
        # Both numeric: compare as integers.
        left_value = int(left)
        right_value = int(right)
        if left_value < right_value:
            return -1
        if left_value > right_value:
            return 1
        return 0
    if left_numeric:
        # POSTCONDITIONS: numeric identifiers rank below string identifiers.
        return -1
    if right_numeric:
        return 1
    # Both string: compare ASCII lexicographically.
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    def __init__(self) -> None:
        # The engine is stateless; no private backing state is required.
        pass

    def parse_version(self, text: str) -> semver_core.Version:
        # POSTCONDITIONS: parse valid SemVer 2.0.0 strings into Version records.
        match = _VERSION_PATTERN.match(text)
        if match is None:
            # PRECONDITIONS: WHEN text contains leading zeroes or violates grammar,
            # MUST raise InvalidVersionError.
            raise semver_core.InvalidVersionError(
                message=f"Invalid semantic version string: {text!r}",
                raw_text=text,
            )
        major_text, minor_text, patch_text, prerelease_text, build_text = match.groups()
        prerelease: Tuple[str, ...] = ()
        if prerelease_text:
            prerelease = tuple(prerelease_text.split("."))
        build: Tuple[str, ...] = ()
        if build_text:
            build = tuple(build_text.split("."))
        return semver_core.Version(
            major=int(major_text),
            minor=int(minor_text),
            patch=int(patch_text),
            prerelease=prerelease,
            build=build,
        )

    def compare_precedence(self, v1: semver_core.Version, v2: semver_core.Version) -> int:
        # POSTCONDITIONS: compare major, minor, and patch numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left < right:
                return -1
            if left > right:
                return 1
        # POSTCONDITIONS: rank normal versions above pre-release versions.
        if not v1.is_prerelease and not v2.is_prerelease:
            return 0
        if not v1.is_prerelease:
            return 1
        if not v2.is_prerelease:
            return -1
        # POSTCONDITIONS: iterate through pre-release segments comparing each position.
        for left_identifier, right_identifier in zip(v1.prerelease, v2.prerelease):
            comparison = _compare_prerelease_identifiers(left_identifier, right_identifier)
            if comparison != 0:
                return comparison
        # POSTCONDITIONS: a longer pre-release sequence ranks higher when the common prefix matches.
        if len(v1.prerelease) < len(v2.prerelease):
            return -1
        if len(v1.prerelease) > len(v2.prerelease):
            return 1
        # POSTCONDITIONS: build metadata is excluded entirely from precedence comparison.
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
# LAST_CLEANED: 2026-11-07T02:22:58Z
# LAST_CHANGED: 2026-11-07T01:55:21Z
# CHANGE: Implement SemVer 2.0 VersionEngine singleton: strict SemVer regex parsing with leading-zero rejection raising InvalidVersionError(raw_text), and RFC precedence comparison over major/minor/patch, prerelease numeric-vs-ASCII ordering, and build-metadata exclusion.
# COVERAGE_AUDIT: 2026-11-07T02:02:02Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T02:22:58Z
# PRETENSE_QA_AUDIT: 2026-11-07T02:22:38Z
# QA_AUDIT: 2026-11-07T02:01:14Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
from . import semver_core

from support.lib.framework import data_type, operation, poly_type

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
        # POSTCONDITIONS: returns the raw range text representation.
        return self.raw_text



@poly_type
class RangeEngine(Protocol):
    """Provides version range parsing and constraint matching."""

    @operation
    def parse_range(self, text: str) -> VersionRange:
        # PRECONDITIONS: malformed or partial range syntax raises InvalidRangeError.
        ...

    @operation
    def satisfies(self, version: semver_core.Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        # POSTCONDITIONS: True when the version satisfies the range, False otherwise.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T01:55:26Z
# LAST_CHANGED: 2026-11-07T01:55:26Z
# CHANGE: Implement range interface: non-frozen InvalidRangeError(raw_range) with inherited __str__, frozen VersionRange value object whose __str__ returns raw_text, and RangeEngine protocol stubs aligned with semver_range.pyi.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import re
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

# Comparators within a clause are delimited strictly by whitespace; commas are rejected.
_OPERATOR_SPACING = re.compile(r"(==|!=|<=|>=|=|<|>|\^|~)\s+")
# A hyphen range connects exactly two whitespace-delimited bounds with ' - '.
_HYPHEN_RANGE = re.compile(r"^(\S+)\s+-\s+(\S+)$")
_WILDCARD_TOKENS = ("x", "X", "*")
_OPERATORS = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")


@dataclass(frozen=True)
class _Bound:
    """Parsed comparator bound: a full version or a wildcard expression."""

    version: semver_core.Version
    matched: int
    wildcard: bool


def _split_operator(token: str) -> Tuple[str, str]:
    for operator in _OPERATORS:
        if token.startswith(operator):
            return operator, token[len(operator):]
    return "", token


def _parse_wildcard_components(text: str) -> Optional[List[int]]:
    # Wildcard expressions carry numeric leading components plus wildcard markers.
    parts = text.split(".")
    if not 1 <= len(parts) <= 3:
        return None
    specified: List[int] = []
    wildcard_seen = False
    for part in parts:
        if part in _WILDCARD_TOKENS:
            wildcard_seen = True
            continue
        if wildcard_seen:
            # Numeric components cannot follow a wildcard marker.
            return None
        if not part.isdigit():
            return None
        if len(part) > 1 and part[0] == "0":
            # SemVer 2.0.0 numeric identifiers reject leading zeroes.
            return None
        specified.append(int(part))
    if not wildcard_seen:
        return None
    return specified


def _make_bound(
    engine: semver_core.VersionEngine,
    text: str,
    raw: str,
) -> _Bound:
    if "-" not in text and "+" not in text:
        specified = _parse_wildcard_components(text)
        if specified is not None:
            major = specified[0] if len(specified) >= 1 else 0
            minor = specified[1] if len(specified) >= 2 else 0
            patch = specified[2] if len(specified) >= 3 else 0
            return _Bound(
                version=semver_core.Version(major, minor, patch),
                matched=len(specified),
                wildcard=True,
            )
    try:
        version = engine.parse_version(text)
    except semver_core.InvalidVersionError as error:
        # PRECONDITIONS: bare partial versions and grammar violations raise InvalidRangeError.
        raise semver_range.InvalidRangeError(
            message=f"Malformed version bound {text!r} in range {raw!r}: {error.message}",
            raw_range=raw,
        ) from error
    return _Bound(version=version, matched=3, wildcard=False)


def _wildcard_upper(bound: _Bound) -> semver_core.Version:
    version = bound.version
    if bound.matched <= 1:
        return semver_core.Version(version.major + 1, 0, 0)
    return semver_core.Version(version.major, version.minor + 1, 0)


def _caret_upper(bound: _Bound) -> semver_core.Version:
    # Caret bounds expand at the first non-zero component.
    version = bound.version
    if bound.matched <= 1:
        if version.major > 0:
            return semver_core.Version(version.major + 1, 0, 0)
        return semver_core.Version(1, 0, 0)
    if version.major > 0:
        return semver_core.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_core.Version(0, version.minor + 1, 0)
    return semver_core.Version(0, 1, 0)


def _caret_upper_full(version: semver_core.Version) -> semver_core.Version:
    # Caret bounds on a full version expand at the first non-zero component.
    if version.major > 0:
        return semver_core.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_core.Version(0, version.minor + 1, 0)
    if version.patch > 0:
        return semver_core.Version(0, 0, version.patch + 1)
    return semver_core.Version(0, 0, 1)


def _tilde_upper(bound: _Bound) -> semver_core.Version:
    # Tilde bounds on wildcards expand at the wildcard position.
    version = bound.version
    if bound.matched <= 1:
        return semver_core.Version(version.major + 1, 0, 0)
    return semver_core.Version(version.major, version.minor + 1, 0)


def _tilde_upper_full(version: semver_core.Version) -> semver_core.Version:
    # Tilde bounds on full versions allow patch-level changes only.
    return semver_core.Version(version.major, version.minor + 1, 0)


def _expand_atom(
    operator: str,
    bound: _Bound,
    raw: str,
) -> List[List[Tuple[str, semver_core.Version]]]:
    if bound.wildcard:
        if bound.matched == 0:
            # A bare wildcard is satisfied by all versions.
            return [[]]
        base = bound.version
        upper = _wildcard_upper(bound)
        if operator in ("", "=", "=="):
            return [[(">=", base), ("<", upper)]]
        if operator == "!=":
            # Normalizes to <base OR >=upper.
            return [[("<", base)], [(">=", upper)]]
        if operator == ">":
            return [[(">=", upper)]]
        if operator == ">=":
            return [[(">=", base)]]
        if operator == "<":
            return [[("<", base)]]
        if operator == "<=":
            return [[("<", upper)]]
        if operator == "^":
            return [[(">=", base), ("<", _caret_upper(bound))]]
        if operator == "~":
            return [[(">=", base), ("<", _tilde_upper(bound))]]
        return [[]]  # pragma: no cover (assumption: operators are validated against the contracted operator set)
    version = bound.version
    if operator in ("", "=", "=="):
        return [[("==", version)]]
    if operator == "!=":
        return [[("!=", version)]]
    if operator == "<":
        return [[("<", version)]]
    if operator == "<=":
        return [[("<=", version)]]
    if operator == ">":
        return [[(">", version)]]
    if operator == ">=":
        return [[(">=", version)]]
    if operator == "^":
        return [[(">=", version), ("<", _caret_upper_full(version))]]
    if operator == "~":
        return [[(">=", version), ("<", _tilde_upper_full(version))]]
    return [[]]  # pragma: no cover (assumption: operators are validated against the contracted operator set)


def _compile_clause(
    engine: semver_core.VersionEngine,
    clause: str,
    raw: str,
) -> List[List[Tuple[str, semver_core.Version]]]:
    hyphen = _HYPHEN_RANGE.match(clause)
    if hyphen is not None:
        # POSTCONDITIONS: hyphen ranges normalize into paired comparator inequalities.
        lower = _make_bound(engine, hyphen.group(1), raw)
        upper = _make_bound(engine, hyphen.group(2), raw)
        comparators: List[Tuple[str, semver_core.Version]] = []
        if not (lower.wildcard and lower.matched == 0):
            comparators.append((">=", lower.version))
        if upper.wildcard:
            if upper.matched > 0:
                comparators.append(("<", _wildcard_upper(upper)))
        else:
            comparators.append(("<=", upper.version))
        return [comparators]
    if " - " in clause:
        # A hyphen range must connect exactly two bounds.
        raise semver_range.InvalidRangeError(
            message=f"Malformed hyphen range in {raw!r}",
            raw_range=raw,
        )
    # Comparators within a clause are delimited strictly by whitespace. The clause is
    # already stripped and non-empty (empty union clauses raise during union validation),
    # so it always yields at least one non-whitespace comparator token.
    atoms = _OPERATOR_SPACING.sub(r"\1", clause).split()
    alternatives: List[List[Tuple[str, semver_core.Version]]] = [[]]
    for atom in atoms:
        operator, text = _split_operator(atom)
        if not text:
            raise semver_range.InvalidRangeError(
                message=f"Comparator {atom!r} lacks a version in range {raw!r}",
                raw_range=raw,
            )
        bound = _make_bound(engine, text, raw)
        expanded = _expand_atom(operator, bound, raw)
        combined: List[List[Tuple[str, semver_core.Version]]] = []
        for existing in alternatives:
            for addition in expanded:
                combined.append(existing + addition)
        alternatives = combined
    return alternatives


def _normalize_range_text(text: str) -> str:
    # POSTCONDITIONS: trims surrounding whitespace around the range and its clauses.
    return " || ".join(clause.strip() for clause in text.split("||"))


def _compile(
    engine: semver_core.VersionEngine,
    text: str,
    raw: str,
) -> List[Tuple[List[Tuple[str, semver_core.Version]], Set[Tuple[int, int, int]]]]:
    # `text` is the expression to compile; `raw` is the original caller-supplied
    # expression attributed to InvalidRangeError.raw_range (never trimmed).
    compiled: List[Tuple[List[Tuple[str, semver_core.Version]], Set[Tuple[int, int, int]]]] = []
    for clause_text in text.split("||"):
        clause = clause_text.strip()
        if not clause:
            raise semver_range.InvalidRangeError(
                message=f"Empty union clause in range {raw!r}",
                raw_range=raw,
            )
        for comparators in _compile_clause(engine, clause, raw):
            targets = {
                (boundary.major, boundary.minor, boundary.patch)
                for _, boundary in comparators
                if boundary.is_prerelease
            }
            compiled.append((comparators, targets))
    return compiled


def _clause_satisfied(
    engine: semver_core.VersionEngine,
    version: semver_core.Version,
    comparators: List[Tuple[str, semver_core.Version]],
    targets: Set[Tuple[int, int, int]],
    include_prerelease: bool,
) -> bool:
    # WHEN version is a prerelease and include_prerelease is False, evaluate to False
    # unless the range explicitly targets that prerelease by major, minor, and patch.
    if version.is_prerelease and not include_prerelease:
        if (version.major, version.minor, version.patch) not in targets:
            return False
    for operator, boundary in comparators:
        comparison = engine.compare_precedence(version, boundary)
        if operator == "==":
            if comparison != 0:
                return False
        elif operator == "!=":
            if comparison == 0:
                return False
        elif operator == "<":
            if comparison >= 0:
                return False
        elif operator == "<=":
            if comparison > 0:
                return False
        elif operator == ">":
            if comparison <= 0:
                return False
        elif operator == ">=":
            if comparison < 0:
                return False
        else:
            return False  # pragma: no cover (assumption: operators are validated against the contracted operator set)
    return True


class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    def __init__(self) -> None:
        # The engine is stateless; no private backing state is required.
        pass

    def parse_range(self, text: str) -> semver_range.VersionRange:
        # PRECONDITIONS: WHEN text is empty, whitespace-only, or uses comma delimiters,
        # MUST raise InvalidRangeError.
        if not text.strip():
            raise semver_range.InvalidRangeError(
                message="Range expression must not be empty",
                raw_range=text,
            )
        if "," in text:
            raise semver_range.InvalidRangeError(
                message=f"Range comparators are delimited by whitespace, not commas: {text!r}",
                raw_range=text,
            )
        engine = get_singleton(semver_core.VersionEngine)
        normalized = _normalize_range_text(text)
        # Validates syntax of comparators, caret, tilde, wildcard, and hyphen expressions;
        # errors attribute the original caller-supplied expression to raw_range.
        _compile(engine, normalized, text)
        # POSTCONDITIONS: stores the trimmed range expression in raw_text.
        return semver_range.VersionRange(raw_text=normalized)

    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        engine = get_singleton(semver_core.VersionEngine)
        # Compiles the range expression into disjunctive normal form comparator sets.
        clauses = _compile(engine, range_constraint.raw_text, range_constraint.raw_text)
        for comparators, targets in clauses:
            if _clause_satisfied(engine, version, comparators, targets, include_prerelease):
                # True if version satisfies all comparators in at least one clause.
                return True
        # Evaluates to False if all clauses fail satisfaction.
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
# LAST_CLEANED: 2026-11-07T02:27:16Z
# LAST_CHANGED: 2026-11-07T02:23:17Z
# CHANGE: Fix feedback: InvalidRangeError.raw_range now always preserves the original caller-supplied expression. _compile takes the original raw expression separately from the expression being compiled, parse_range passes the untrimmed caller text as the error attribution while still compiling the trimmed/re-joined text for the successful VersionRange.raw_text, and satisfies attributes its VersionRange.raw_text. Trimming is therefore confined to the parsed result, and malformed inputs such as '1.x ||' or '1.0.0 - ' raise InvalidRangeError with raw_range equal to the original input.
# COVERAGE_AUDIT: 2026-11-07T02:24:40Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T02:27:16Z
# PRETENSE_QA_AUDIT: 2026-11-07T02:26:32Z
# QA_AUDIT: 2026-11-07T02:23:54Z
# --- END AUTOFAB METADATA ---
