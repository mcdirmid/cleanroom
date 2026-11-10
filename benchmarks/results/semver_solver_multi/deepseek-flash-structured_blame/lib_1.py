# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_123409_deepseek-flash_semver_solver_multi
# Timestamp: 2026-11-08T12:34:09.968889+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 293,359
#   Cached Inbound Tokens:   23,321,472
#   Outbound Tokens:         254,988
#   Total Tokens:            23,869,819
#   Financial Cost ($USD):   $0.2670
#   Wall Clock Duration:     1811.96s
#   Step Latencies (s):      [281.9, 336.3, 62.4, 191.9, 64.9, 73.0, 422.3, 145.6, 20.6, 212.6, 115.2, 171.7, 22.6, 95.6, 72.7, 10.1, 64.6, 41.5, 10.0, 20.4]
#   Role Execution Rounds:   coverage: 5, lib: 4, qa: 5, test: 6 (Total: 20)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       51
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

    def __str__(self) -> str:
        # Diagnostics are formatted from the structured message field.
        return self.message


@dataclass
class ResolutionConflictError(semver_core.SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually."""

    conflicting_packages: Tuple[str, ...]
    explanation: str

    def __str__(self) -> str:
        # Diagnostics are formatted from the structured message field.
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
# LAST_CLEANED: 2026-11-08T12:36:24Z
# LAST_CHANGED: 2026-11-08T12:36:24Z
# CHANGE: Implement dependency_solver interface: data record types and poly-type protocols with exception diagnostics
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

_RootRequester = "root"


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Private backing storage maps package names to release lists.
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # Releases stay ordered by descending version precedence for candidate selection.
        engine = get_singleton(semver_core.VersionEngine)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(
                    right.version, left.version
                )
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        # Missing package names surface as PackageNotFoundError with the structured name.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package not found in repository: {name!r}",
                package_name=name,
            )
        # Callers receive a shallow copy and cannot mutate the indexed release list.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Returns the set of all registered package names."""
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
        """Computes a mutually compatible version assignment for root dependencies."""
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        # Accumulated constraints map each package to (requester, required range) pairs.
        constraints: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                (_RootRequester, dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(name: str) -> List[dependency_solver.PackageRelease]:
            """Candidate releases satisfying every accumulated constraint for a package."""
            try:
                available = repository.get_releases(name)
            except dependency_solver.PackageNotFoundError:
                # Missing packages evaluate to zero candidates without escaping the solver.
                conflict_trail.append(
                    f"Package '{name}' is not registered in the repository"
                )
                conflicting_packages.add(name)
                return []
            required = constraints[name]
            return [
                release
                for release in available
                if all(
                    range_engine.satisfies(
                        release.version, constraint, False
                    )
                    for _, constraint in required
                )
            ]

        def search() -> bool:
            """Depth-first backtracking search over unassigned packages."""
            unassigned = [name for name in constraints if name not in assignment]
            if not unassigned:
                return True

            # Minimum Remaining Values selection with lexical tie-breaking.
            candidate_map = {name: viable_releases(name) for name in unassigned}
            selected = min(
                unassigned,
                key=lambda name: (len(candidate_map[name]), name),
            )
            candidates = candidate_map[selected]

            if not candidates:
                requesters = [source for source, _ in constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(
                    source for source in requesters if source != _RootRequester
                )
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints "
                    f"from {requesters}"
                )
                return False

            # Candidates are explored in descending version precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(
                    f"Assign '{selected}' to {candidate.version}"
                )

                conflict_detected = False
                newly_added: List[
                    Tuple[str, Tuple[str, semver_range.VersionRange]]
                ] = []

                # Forward checking: declared dependencies merge into accumulated constraints.
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not range_engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' {candidate.version} "
                                f"requires '{dependency.name}' "
                                f"{dependency.range_constraint}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and search():
                    return True

                # Backtrack: undo the assignment and all constraints it introduced.
                for name, entry in newly_added:
                    constraints[name].remove(entry)
                    if not constraints[name]:
                        del constraints[name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if search():
            # Successful assignment compiles selected versions and decision sequence.
            return dependency_solver.ResolutionOutcome(
                selected_versions={
                    name: release.version for name, release in assignment.items()
                },
                derivation_steps=tuple(derivation_steps),
            )

        # Every failed search branch recorded a diagnostic, so the trail explains the conflict.
        explanation = "\n".join(conflict_trail)
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
# LAST_CLEANED: 2026-11-08T12:59:24Z
# LAST_CHANGED: 2026-11-08T12:52:26Z
# CHANGE: Remove the unreachable conflict-explanation fallback so a failed dependency search always reports the accumulated conflict trail, since every failing branch records a diagnostic before backtracking
# COVERAGE_AUDIT: 2026-11-08T12:59:24Z
# QA_AUDIT: 2026-11-08T12:59:10Z
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
        # Diagnostics are formatted from the structured message field.
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered."""

    raw_text: str

    def __str__(self) -> str:
        # Diagnostics are formatted from the structured message field.
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
        # A version is a prerelease exactly when it carries pre-release identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Canonical SemVer 2.0.0 rendering: numeric core, optional '-prerelease', optional '+build'.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # String conversion delegates directly to the canonical format() representation.
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
# LAST_CLEANED: 2026-11-08T12:36:17Z
# LAST_CHANGED: 2026-11-08T12:36:17Z
# CHANGE: Implement semver_core interface: concrete Version data type methods and non-frozen dataclass exceptions with __str__ diagnostics
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations
import re
from typing import Optional
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 grammar: numeric core without leading zeroes, optional dot-separated
# pre-release identifiers, and optional dot-separated build metadata identifiers.
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Grammar validation: leading zeroes or malformed syntax must raise InvalidVersionError.
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                message=f"Invalid semantic version text: {text!r}",
                raw_text=text,
            )

        # Structural extraction of numeric core, pre-release segments, and build metadata.
        prerelease_text = match.group(4)
        build_text = match.group(5)
        prerelease: tuple[str, ...] = (
            tuple(prerelease_text.split(".")) if prerelease_text is not None else ()
        )
        build: tuple[str, ...] = (
            tuple(build_text.split(".")) if build_text is not None else ()
        )

        # Produces the immutable Version record for a valid input.
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
        """Determines ordering precedence between two semantic versions."""
        # Numeric core comparison in major, minor, patch order.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return -1 if left < right else 1

        # A normal version outranks any pre-release version with the same numeric core.
        if v1.is_prerelease != v2.is_prerelease:
            return -1 if v1.is_prerelease else 1
        if not v1.is_prerelease and not v2.is_prerelease:
            return 0

        # Pre-release identifier comparison position by position.
        for left_id, right_id in zip(v1.prerelease, v2.prerelease):
            if left_id == right_id:
                continue
            left_numeric = left_id.isdigit()
            right_numeric = right_id.isdigit()
            # Numeric identifiers always rank lower than alphanumeric identifiers.
            if left_numeric and right_numeric:
                return -1 if int(left_id) < int(right_id) else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            # Alphanumeric identifiers compare in ASCII lexicographical order.
            return -1 if left_id < right_id else 1

        # When common identifiers match, the longer identifier sequence ranks higher.
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

        # Build metadata is excluded from precedence entirely.
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
# LAST_CLEANED: 2026-11-08T12:43:39Z
# LAST_CHANGED: 2026-11-08T12:39:47Z
# CHANGE: Implement SemVer 2.0.0 VersionEngine: regex grammar validation with InvalidVersionError, structured version parsing, and precedence comparison honoring numeric, prerelease, and build-metadata rules
# COVERAGE_AUDIT: 2026-11-08T12:43:39Z
# QA_AUDIT: 2026-11-08T12:43:11Z
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

    def __str__(self) -> str:
        # Diagnostics are formatted from the structured message field.
        return self.message


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        # String conversion delegates directly to the canonical raw range text.
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
# LAST_CLEANED: 2026-11-08T12:36:21Z
# LAST_CHANGED: 2026-11-08T12:36:21Z
# CHANGE: Implement semver_range interface: concrete VersionRange string representation and exception diagnostics
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

_Comparator = Tuple[semver_core.ComparatorOp, semver_core.Version]
_Clause = List[_Comparator]

# A clause token is an optional relational/prefix operator followed by its target
# expression; leading whitespace belongs to the token so operators after a space
# separator bind to their own target.
_CLAUSE_TOKEN_PATTERN = re.compile(r"\s*(>=|<=|==|!=|=|>|<|\^|~)?\s*([^\s]+)")
_WILDCARD_TOKENS = frozenset({"x", "X", "*"})
_NUMERIC_COMPONENT_PATTERN = re.compile(r"^(0|[1-9]\d*)$")
# Complete SemVer 2.0.0 grammar for range bounds: exactly three numeric core
# components without leading zeroes plus optional pre-release and build metadata.
_FULL_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
_SIMPLE_OPERATORS: Dict[str, semver_core.ComparatorOp] = {
    "": semver_core.ComparatorOp.EQ,
    "=": semver_core.ComparatorOp.EQ,
    "==": semver_core.ComparatorOp.EQ,
    "!=": semver_core.ComparatorOp.NE,
    "<": semver_core.ComparatorOp.LT,
    "<=": semver_core.ComparatorOp.LE,
    ">": semver_core.ComparatorOp.GT,
    ">=": semver_core.ComparatorOp.GE,
}


@dataclass(frozen=True)
class _RangeTarget:
    """Compiled range bound: a concrete version or a wildcard numeric prefix."""

    version: Optional[semver_core.Version] = None
    prefix: Tuple[int, ...] = ()


def _target_error(text: str, target: str) -> semver_range.InvalidRangeError:
    # Range syntax defects are reified as InvalidRangeError with the original range text.
    return semver_range.InvalidRangeError(
        message=f"Malformed range target {target!r} in range {text!r}",
        raw_range=text,
    )


def _parse_target(target: str, text: str, engine: semver_core.VersionEngine) -> _RangeTarget:
    """Parses a comparator/hyphen bound into a concrete version or wildcard prefix."""
    components = target.split(".")
    has_wildcard = target in _WILDCARD_TOKENS or any(
        component in _WILDCARD_TOKENS for component in components
    )

    if not has_wildcard:
        # Bare partial versions lack wildcards and are rejected syntactically here so
        # that rejection does not depend on collaborator parsing behavior.
        if _FULL_VERSION_PATTERN.match(target) is None:
            raise _target_error(text, target)
        # Full versions are then realized through the on-demand version engine; the
        # locally validated grammar guarantees the collaborator accepts the bound.
        return _RangeTarget(version=engine.parse_version(target))

    prefix: List[int] = []
    wildcard_seen = False
    for component in components:
        if component in _WILDCARD_TOKENS:
            wildcard_seen = True
            continue
        # Numeric components are only legal before the first wildcard component.
        if wildcard_seen or _NUMERIC_COMPONENT_PATTERN.match(component) is None:
            raise _target_error(text, target)
        prefix.append(int(component))
    if len(prefix) > 2:
        raise _target_error(text, target)
    return _RangeTarget(prefix=tuple(prefix))


def _wildcard_lower(prefix: Tuple[int, ...]) -> semver_core.Version:
    """Lower bound of a wildcard expression, zero-filling unspecified components."""
    major = prefix[0] if len(prefix) > 0 else 0
    minor = prefix[1] if len(prefix) > 1 else 0
    return semver_core.Version(major=major, minor=minor, patch=0)


def _wildcard_upper(prefix: Tuple[int, ...]) -> semver_core.Version:
    """Exclusive upper bound of a wildcard expression, bumped at its last numeric component."""
    if len(prefix) == 1:
        return semver_core.Version(major=prefix[0] + 1, minor=0, patch=0)
    return semver_core.Version(major=prefix[0], minor=prefix[1] + 1, patch=0)


def _caret_upper(version: semver_core.Version) -> semver_core.Version:
    """Caret upper bound bumps the first non-zero numeric component."""
    if version.major > 0:
        return semver_core.Version(major=version.major + 1, minor=0, patch=0)
    if version.minor > 0:
        return semver_core.Version(major=0, minor=version.minor + 1, patch=0)
    return semver_core.Version(major=0, minor=0, patch=version.patch + 1)


def _caret_wildcard_upper(prefix: Tuple[int, ...]) -> semver_core.Version:
    """Caret upper bound over a wildcard prefix uses its first non-zero component boundary."""
    if len(prefix) == 1:
        return semver_core.Version(major=prefix[0] + 1, minor=0, patch=0)
    if prefix[0] > 0:
        return semver_core.Version(major=prefix[0] + 1, minor=0, patch=0)
    return semver_core.Version(major=0, minor=prefix[1] + 1, patch=0)


def _tilde_upper(version: semver_core.Version) -> semver_core.Version:
    """Tilde upper bound advances the minor component."""
    return semver_core.Version(major=version.major, minor=version.minor + 1, patch=0)


def _expand_comparator(
    operator: str,
    target: _RangeTarget,
) -> List[_Clause]:
    """Expands one comparator expression into disjunctive comparator clauses."""
    op = semver_core.ComparatorOp

    if target.version is not None:
        version = target.version
        simple = _SIMPLE_OPERATORS.get(operator)
        if simple is not None:
            return [[(simple, version)]]
        if operator == "^":
            return [[(op.GE, version), (op.LT, _caret_upper(version))]]
        # Tilde is the only remaining prefix operator admitted by the tokenizer.
        return [[(op.GE, version), (op.LT, _tilde_upper(version))]]

    prefix = target.prefix
    lower = _wildcard_lower(prefix)

    # A bare wildcard with an inclusive prefix matches every candidate version.
    if len(prefix) == 0:
        if operator in ("", "=", "==", ">=", "^", "~"):
            return [[]]
        return []

    upper = _wildcard_upper(prefix)
    if operator in ("", "=", "=="):
        return [[(op.GE, lower), (op.LT, upper)]]
    if operator == "!=":
        return [[(op.LT, lower)], [(op.GE, upper)]]
    if operator == ">=":
        return [[(op.GE, lower)]]
    if operator == ">":
        return [[(op.GE, upper)]]
    if operator == "<":
        return [[(op.LT, lower)]]
    if operator == "<=":
        return [[(op.LT, upper)]]
    if operator == "^":
        return [[(op.GE, lower), (op.LT, _caret_wildcard_upper(prefix))]]
    # Tilde is the only remaining prefix operator admitted by the tokenizer.
    return [[(op.GE, lower), (op.LT, upper)]]


def _tokenize_clause(clause_text: str) -> List[Tuple[str, str]]:
    """Splits a clause into whitespace-delimited (operator, target) pairs."""
    parts: List[Tuple[str, str]] = []
    for match in _CLAUSE_TOKEN_PATTERN.finditer(clause_text):
        parts.append((match.group(1) or "", match.group(2)))
    return parts


def _hyphen_clause(
    low_target: str,
    high_target: str,
    text: str,
    engine: semver_core.VersionEngine,
) -> _Clause:
    """Expands a hyphen range into lower and upper comparator bounds."""
    op = semver_core.ComparatorOp
    low = _parse_target(low_target, text, engine)
    high = _parse_target(high_target, text, engine)
    comparators: _Clause = []
    if low.version is not None:
        comparators.append((op.GE, low.version))
    else:
        comparators.append((op.GE, _wildcard_lower(low.prefix)))
    if high.version is not None:
        comparators.append((op.LE, high.version))
    elif len(high.prefix) > 0:
        comparators.append((op.LT, _wildcard_upper(high.prefix)))
    return comparators


def _compile_clause(clause_text: str, text: str, engine: semver_core.VersionEngine) -> List[_Clause]:
    """Compiles one union clause into disjunctive comparator clauses."""
    parts = _tokenize_clause(clause_text)

    # A three part clause whose middle token is '-' denotes a hyphen range.
    if (
        len(parts) == 3
        and parts[1] == ("", "-")
        and parts[0][0] == ""
        and parts[2][0] == ""
    ):
        return [_hyphen_clause(parts[0][1], parts[2][1], text, engine)]

    # Comparators are delimited strictly by whitespace and composed conjunctively.
    alternatives: List[_Clause] = [[]]
    for raw_operator, target_text in parts:
        target = _parse_target(target_text, text, engine)
        token_alternatives = _expand_comparator(raw_operator, target)
        alternatives = [
            existing + alternative
            for existing in alternatives
            for alternative in token_alternatives
        ]
        # An unsatisfiable comparator contributes no clauses and settles the clause.
        if not alternatives:
            break
    return alternatives


def _compile_range(text: str, engine: semver_core.VersionEngine) -> List[_Clause]:
    """Compiles a range expression into disjunctive normal form comparator clauses."""
    trimmed = text.strip()
    if not trimmed:
        raise semver_range.InvalidRangeError(
            message=f"Empty version range: {text!r}",
            raw_range=text,
        )
    # Comma delimiters are prohibited; comparators are whitespace delimited.
    if "," in trimmed:
        raise semver_range.InvalidRangeError(
            message=f"Commas are not permitted in version range: {text!r}",
            raw_range=text,
        )

    clauses: List[_Clause] = []
    for union_part in trimmed.split("||"):
        clause_text = union_part.strip()
        # Empty union clauses are malformed range syntax.
        if not clause_text:
            raise semver_range.InvalidRangeError(
                message=f"Empty union clause in version range: {text!r}",
                raw_range=text,
            )
        clauses.extend(_compile_clause(clause_text, text, engine))
    return clauses


def _comparator_holds(
    comparator: _Comparator,
    version: semver_core.Version,
    engine: semver_core.VersionEngine,
) -> bool:
    """Evaluates a single comparator against a candidate version using precedence ordering."""
    op = semver_core.ComparatorOp
    operator, bound = comparator
    ordering = engine.compare_precedence(version, bound)
    if operator is op.EQ:
        return ordering == 0
    if operator is op.NE:
        return ordering != 0
    if operator is op.LT:
        return ordering < 0
    if operator is op.LE:
        return ordering <= 0
    if operator is op.GT:
        return ordering > 0
    return ordering >= 0


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # Collaborator engine resolved on demand rather than registered by this module.
        engine = get_singleton(semver_core.VersionEngine)
        # Compiles the trimmed expression, raising InvalidRangeError on malformed syntax.
        _compile_range(text, engine)
        # Stores the trimmed range expression, preserving clause whitespace.
        return semver_range.VersionRange(raw_text=text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        # Collaborator engine resolved on demand rather than registered by this module.
        engine = get_singleton(semver_core.VersionEngine)
        clauses = _compile_range(range_constraint.raw_text, engine)
        if not clauses:
            return False

        # Pre-release candidates are filtered unless the range explicitly targets that
        # pre-release version by sharing the same major, minor, and patch numbers.
        if version.is_prerelease and not include_prerelease:
            targeted = any(
                bound.is_prerelease
                and bound.major == version.major
                and bound.minor == version.minor
                and bound.patch == version.patch
                for clause in clauses
                for _, bound in clause
            )
            if not targeted:
                return False

        # The candidate satisfies the range when it satisfies every comparator in
        # at least one disjunctive clause.
        for clause in clauses:
            if all(
                _comparator_holds(comparator, version, engine)
                for comparator in clause
            ):
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
# LAST_CLEANED: 2026-11-08T13:04:08Z
# LAST_CHANGED: 2026-11-08T12:58:11Z
# CHANGE: Prune defensive dead code from range compilation per coverage feedback: drop the unused _RangeTarget.is_wildcard property, make the tilde expansion the explicit default after the simple and caret operator cases, collapse the wildcard upper-bound helper to only its reachable one- and two-component cases, and remove the redundant tokenizer position guards; also drop the unexercisable InvalidVersionError catch around collaborator parse_version since local SemVer grammar validation already guarantees acceptance
# COVERAGE_AUDIT: 2026-11-08T13:04:08Z
# QA_AUDIT: 2026-11-08T13:03:55Z
# --- END AUTOFAB METADATA ---
