# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_052028_deepseek-flash_semver_solver_multi
# Timestamp: 2026-11-05T05:20:28.323311+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 243,283
#   Cached Inbound Tokens:   13,371,520
#   Outbound Tokens:         216,130
#   Total Tokens:            13,830,933
#   Financial Cost ($USD):   $0.2063
#   Wall Clock Duration:     1119.46s
#   Step Latencies (s):      [300.2, 474.6, 32.0, 64.7, 10.4, 100.5, 11.0, 216.9, 77.9, 113.3, 10.4, 109.5, 43.0, 10.4, 10.4]
#   Role Execution Rounds:   coverage: 3, lib: 3, qa: 5, test: 4 (Total: 15)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       59
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
"""Library interface for package repository and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, List, Mapping, Protocol, Set, Tuple

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
# LAST_CLEANED: 2026-11-05T05:27:55Z
# LAST_CHANGED: 2026-11-05T05:27:55Z
# CHANGE: Implement dependency solver interface: PackageNotFoundError and ResolutionConflictError with structured attributes, frozen PackageDependency/PackageRelease/ResolutionOutcome records, and PackageRepository/DependencySolver protocols.
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Library implementation of package repository and dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi

_ConstraintEntry = Tuple[str, semver_range.VersionRange]


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        """Initializes the private package index."""
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_core.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)

        def descending(
            left: dependency_solver.PackageRelease,
            right: dependency_solver.PackageRelease,
        ) -> int:
            return engine.compare_precedence(right.version, left.version)

        # Re-sort the release list in descending version precedence order.
        releases.sort(key=cmp_to_key(descending))

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
        # Produce a shallow copy so callers cannot mutate internal ordering state.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names."""
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

        # Accumulated constraints map each package to the requesting package and range.
        accumulated: Dict[str, List[_ConstraintEntry]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def satisfies_all(
            package_name: str,
            version: semver_core.Version,
        ) -> bool:
            return all(
                range_engine.satisfies(version, constraint, False)
                for _, constraint in accumulated[package_name]
            )

        def backtrack() -> bool:
            unassigned = [
                package_name
                for package_name in accumulated
                if package_name not in assignment
            ]
            if not unassigned:
                return True

            # Determine viable candidates for every unassigned package (MRV).
            candidates_by_package: Dict[
                str, List[dependency_solver.PackageRelease]
            ] = {}
            for package_name in unassigned:
                # Unregistered packages have zero candidate releases.
                available = (
                    repository.get_releases(package_name)
                    if repository.has_package(package_name)
                    else []
                )
                candidates_by_package[package_name] = [
                    release
                    for release in available
                    if satisfies_all(package_name, release.version)
                ]

            # Fewest remaining values first; ties break lexicographically.
            selected_name = min(
                unassigned,
                key=lambda candidate_name: (
                    len(candidates_by_package[candidate_name]),
                    candidate_name,
                ),
            )
            candidates = candidates_by_package[selected_name]

            if not candidates:
                requesters = [
                    requester for requester, _ in accumulated[selected_name]
                ]
                conflicting_packages.add(selected_name)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected_name}' satisfying constraints from {requesters}"
                )
                return False

            # Explore viable candidate releases in descending precedence order.
            for candidate in candidates:
                assignment[selected_name] = candidate
                derivation_steps.append(
                    f"Assign '{selected_name}' to {candidate.version}"
                )

                conflict_detected = False
                newly_added: List[Tuple[str, _ConstraintEntry]] = []

                # Forward-check candidate dependencies against partial assignment.
                for dependency in candidate.dependencies:
                    assigned = assignment.get(dependency.name)
                    if assigned is not None:
                        if not range_engine.satisfies(
                            assigned.version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected_name)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected_name}' requires "
                                f"{dependency.name} {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry: _ConstraintEntry = (
                            selected_name,
                            dependency.range_constraint,
                        )
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and backtrack():
                    return True

                # Undo the assignment and every constraint introduced by this branch.
                for package_name, entry in newly_added:
                    accumulated[package_name].remove(entry)
                    if not accumulated[package_name]:
                        del accumulated[package_name]
                del assignment[selected_name]
                derivation_steps.pop()

            return False

        if not backtrack():
            # Compose the accumulated conflict trail into a diagnostic explanation.
            explanation = (
                "\n".join(conflict_trail)
                if conflict_trail
                else "Dependency resolution exhausted all candidate branches"
            )
            raise dependency_solver.ResolutionConflictError(
                f"Unable to resolve dependencies: {explanation}",
                conflicting_packages=tuple(sorted(conflicting_packages)),
                explanation=explanation,
            )

        return dependency_solver.ResolutionOutcome(
            selected_versions={
                package_name: release.version
                for package_name, release in assignment.items()
            },
            derivation_steps=tuple(derivation_steps),
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
# LAST_CLEANED: 2026-11-05T05:34:13Z
# LAST_CHANGED: 2026-11-05T05:28:27Z
# CHANGE: Implement PackageRepository release indexing sorted descending by VersionEngine precedence, and DependencySolver MRV backtracking search with forward checking, conflict trail collection, missing-package handling via ResolutionConflictError, and resolution outcomes.
# COVERAGE_AUDIT: 2026-11-05T05:34:13Z
# QA_AUDIT: 2026-11-05T05:33:38Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""Library interface for SemVer 2.0.0 parsing and precedence comparison."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Protocol, Tuple

from support.lib.framework import data_type, operation, poly_type

# Requirements specified in semver_core.pyi


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __str__(self) -> str:
        """Returns the diagnostic message describing this error."""
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered."""

    raw_text: str


class ComparatorOp(enum.Enum):
    """Relational comparison operator for version constraints."""

    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


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
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
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
# LAST_CLEANED: 2026-11-05T05:27:46Z
# LAST_CHANGED: 2026-11-05T05:27:46Z
# CHANGE: Implement SemVer 2.0.0 interface: non-frozen dataclass error hierarchy with message formatting, ComparatorOp enum, frozen Version value type with is_prerelease/format/__str__, and VersionEngine protocol.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""Library implementation of SemVer 2.0.0 parsing and precedence comparison."""

from __future__ import annotations

import re
from typing import Optional, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_core

# Requirements specified in semver_core_impl.pyi

# SemVer 2.0.0 grammar: numeric identifiers without leading zeroes plus optional
# dot-separated pre-release identifiers and build metadata.
_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _compare_prerelease_identifiers(left: str, right: str) -> int:
    """Compares two pre-release identifiers using SemVer 2.0.0 precedence rules."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    # Numeric identifiers are compared numerically and rank below alphanumeric ones.
    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        if left_value < right_value:
            return -1
        if left_value > right_value:
            return 1
        return 0
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    # Alphanumeric identifiers are compared in ASCII lexicographical order.
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Validate the full grammar; leading zeroes in numeric identifiers fail here.
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                f"Invalid semantic version: {text}",
                raw_text=text,
            )
        prerelease_text: Optional[str] = match.group("prerelease")
        build_text: Optional[str] = match.group("build")
        prerelease: Tuple[str, ...] = (
            tuple(prerelease_text.split(".")) if prerelease_text else ()
        )
        build: Tuple[str, ...] = tuple(build_text.split(".")) if build_text else ()
        return semver_core.Version(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
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
        """Determines ordering precedence between two semantic versions."""
        # Major, minor, and patch are compared numerically in sequence.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left < right:
                return -1
            if left > right:
                return 1

        # A normal version ranks higher than a pre-release with identical numbers.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # Iterate over pre-release segments comparing each position.
        for left_id, right_id in zip(v1.prerelease, v2.prerelease):
            result = _compare_prerelease_identifiers(left_id, right_id)
            if result != 0:
                return result

        # A longer pre-release sequence ranks higher when the common prefix matches.
        if len(v1.prerelease) < len(v2.prerelease):
            return -1
        if len(v1.prerelease) > len(v2.prerelease):
            return 1

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
# LAST_CLEANED: 2026-11-05T05:34:15Z
# LAST_CHANGED: 2026-11-05T05:28:17Z
# CHANGE: Implement VersionEngine singleton: strict SemVer 2.0.0 regex parsing with leading-zero rejection and InvalidVersionError, plus numeric/prerelease/build-ignoring precedence comparison and lifecycle registration.
# COVERAGE_AUDIT: 2026-11-05T05:34:15Z
# QA_AUDIT: 2026-11-05T05:33:40Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Library interface for version range parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
# LAST_CLEANED: 2026-11-05T05:27:51Z
# LAST_CHANGED: 2026-11-05T05:27:51Z
# CHANGE: Implement version range interface: non-frozen InvalidRangeError with raw_range, frozen VersionRange value type with raw_text string projection, and RangeEngine protocol with parse_range/satisfies.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Library implementation of version range parsing and constraint matching."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

# Compiled representation: a disjunction of clauses, where each clause is a
# conjunction of comparator bounds.
_ComparatorBound = Tuple[semver_core.ComparatorOp, semver_core.Version]
_ComparatorClause = List[_ComparatorBound]

_WILDCARD_TOKENS = frozenset({"*", "x", "X"})
_NUMERIC_COMPONENT_PATTERN = re.compile(r"^(?:0|[1-9][0-9]*)$")
_HYPHEN_RANGE_PATTERN = re.compile(r"^(\S+)\s+-\s+(\S+)$")
_OPERATOR_PREFIXES: Tuple[str, ...] = (
    ">=",
    "<=",
    "==",
    "!=",
    "=",
    ">",
    "<",
    "^",
    "~",
)


def _caret_upper_bound(version: semver_core.Version) -> semver_core.Version:
    """Expands a caret prefix into the exclusive upper precedence boundary."""
    if version.major > 0:
        return semver_core.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_core.Version(0, version.minor + 1, 0)
    return semver_core.Version(0, 0, version.patch + 1)


def _comparator_holds(operator: semver_core.ComparatorOp, precedence: int) -> bool:
    """Evaluates a relational comparator against a resolved precedence delta."""
    if operator is semver_core.ComparatorOp.EQ:
        return precedence == 0
    if operator is semver_core.ComparatorOp.NE:
        return precedence != 0
    if operator is semver_core.ComparatorOp.LT:
        return precedence < 0
    if operator is semver_core.ComparatorOp.LE:
        return precedence <= 0
    if operator is semver_core.ComparatorOp.GT:
        return precedence > 0
    return precedence >= 0


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # Compiling the range validates comparators, prefixes, wildcards, and unions.
        self._compile_range(text)
        # Store the range expression with surrounding whitespace trimmed.
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
        engine = self._version_engine()
        # Compile the range expression into disjunctive normal form comparator sets.
        clauses = self._compile_range(range_constraint.raw_text)
        for clause in clauses:
            if self._clause_satisfied(engine, version, clause, include_prerelease):
                return True
        return False

    def _version_engine(self) -> semver_core.VersionEngine:
        """Resolves the semantic version engine collaborator on demand."""
        return get_singleton(semver_core.VersionEngine)

    def _parse_version_text(
        self,
        text: str,
        raw_range: str,
    ) -> semver_core.Version:
        """Parses a complete version token, translating grammar failures into range errors."""
        try:
            return self._version_engine().parse_version(text)
        except semver_core.InvalidVersionError as exc:
            raise semver_range.InvalidRangeError(
                f"Malformed version '{text}' in version range '{raw_range}'",
                raw_range=raw_range,
            ) from exc

    def _compile_range(self, text: str) -> List[_ComparatorClause]:
        """Compiles a range expression into disjunctive normal form comparator sets."""
        stripped = text.strip()
        # An empty or whitespace-only expression is malformed.
        if not stripped:
            raise semver_range.InvalidRangeError(
                "Version range expression must not be empty",
                raw_range=text,
            )
        # Comparators are delimited strictly by whitespace; commas are not permitted.
        if "," in stripped:
            raise semver_range.InvalidRangeError(
                f"Comma delimiters are not permitted in version range '{text}'",
                raw_range=text,
            )
        clauses: List[_ComparatorClause] = []
        for alternative in stripped.split("||"):
            clause_text = alternative.strip()
            # Empty union clauses are malformed.
            if not clause_text:
                raise semver_range.InvalidRangeError(
                    f"Empty union clause in version range '{text}'",
                    raw_range=text,
                )
            clauses.extend(self._compile_clause(clause_text, text))
        return clauses

    def _compile_clause(
        self,
        clause: str,
        raw_range: str,
    ) -> List[_ComparatorClause]:
        """Compiles a single whitespace-delimited comparator clause."""
        # A hyphen range normalizes into paired lower and upper comparator bounds.
        hyphen = _HYPHEN_RANGE_PATTERN.match(clause)
        if hyphen is not None:
            hyphen_clauses: List[_ComparatorClause] = [[]]
            # Route both operands through the ordinary complete-version-or-wildcard
            # validation and expansion path so bare partial operands (e.g. '1.2')
            # raise InvalidRangeError instead of leaking collaborator parser errors.
            for operator, operand in (
                (">=", hyphen.group(1)),
                ("<=", hyphen.group(2)),
            ):
                alternatives = self._expand_term(operator, operand, raw_range)
                hyphen_clauses = [
                    existing + alternative
                    for existing in hyphen_clauses
                    for alternative in alternatives
                ]
            return hyphen_clauses
        clauses: List[_ComparatorClause] = [[]]
        for operator, body in self._tokenize(clause, raw_range):
            alternatives = self._expand_term(operator, body, raw_range)
            # Intersect the term with every clause accumulated so far.
            clauses = [
                existing + alternative
                for existing in clauses
                for alternative in alternatives
            ]
            if not clauses:
                return []
        return clauses

    def _tokenize(
        self,
        clause: str,
        raw_range: str,
    ) -> List[Tuple[str, str]]:
        """Splits a clause into operator/version token pairs."""
        tokens: List[Tuple[str, str]] = []
        position = 0
        length = len(clause)
        while position < length:
            while position < length and clause[position].isspace():
                position += 1
            operator = ""
            for candidate in _OPERATOR_PREFIXES:
                if clause.startswith(candidate, position):
                    operator = candidate
                    position += len(candidate)
                    break
            # Optional whitespace is accepted between operator and target.
            while position < length and clause[position].isspace():
                position += 1
            body_start = position
            while position < length and not clause[position].isspace():
                position += 1
            body = clause[body_start:position]
            if not body:
                raise semver_range.InvalidRangeError(
                    f"Missing version target after operator '{operator}' in range '{raw_range}'",
                    raw_range=raw_range,
                )
            tokens.append((operator, body))
        if not tokens:
            raise semver_range.InvalidRangeError(
                f"Missing comparator in version range '{raw_range}'",
                raw_range=raw_range,
            )
        return tokens

    def _split_spec(
        self,
        body: str,
        raw_range: str,
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """Splits a version token into its numeric core, pre-release, and build parts."""
        core = body
        build: Optional[str] = None
        prerelease: Optional[str] = None
        if "+" in core:
            core, _, build_text = core.partition("+")
            build = build_text
            if not build:
                raise semver_range.InvalidRangeError(
                    f"Missing build metadata in range '{raw_range}'",
                    raw_range=raw_range,
                )
        if "-" in core:
            core, _, prerelease_text = core.partition("-")
            prerelease = prerelease_text
            if not prerelease:
                raise semver_range.InvalidRangeError(
                    f"Missing pre-release identifier in range '{raw_range}'",
                    raw_range=raw_range,
                )
        if not core:
            raise semver_range.InvalidRangeError(
                f"Missing version target in range '{raw_range}'",
                raw_range=raw_range,
            )
        return core, prerelease, build

    def _expand_term(
        self,
        operator: str,
        body: str,
        raw_range: str,
    ) -> List[_ComparatorClause]:
        """Expands one comparator term into its disjunctive normal form."""
        core, prerelease, build = self._split_spec(body, raw_range)
        components = core.split(".")
        if len(components) > 3:
            raise semver_range.InvalidRangeError(
                f"Malformed version '{body}' in range '{raw_range}'",
                raw_range=raw_range,
            )
        numbers: List[int] = []
        has_wildcard = False
        for index, component in enumerate(components):
            if component in _WILDCARD_TOKENS:
                # Wildcards are only permitted as the final component.
                if index != len(components) - 1:
                    raise semver_range.InvalidRangeError(
                        f"Wildcard must be the final component in '{body}' within range '{raw_range}'",
                        raw_range=raw_range,
                    )
                has_wildcard = True
                continue
            if has_wildcard:
                raise semver_range.InvalidRangeError(
                    f"Wildcard must be the final component in '{body}' within range '{raw_range}'",
                    raw_range=raw_range,
                )
            if _NUMERIC_COMPONENT_PATTERN.match(component) is None:
                raise semver_range.InvalidRangeError(
                    f"Malformed version component '{component}' in range '{raw_range}'",
                    raw_range=raw_range,
                )
            numbers.append(int(component))
        # Pre-release identifiers and build metadata require a complete version.
        if (prerelease is not None or build is not None) and (
            has_wildcard or len(numbers) != 3
        ):
            raise semver_range.InvalidRangeError(
                f"Partial version '{body}' in range '{raw_range}' must use wildcard characters",
                raw_range=raw_range,
            )
        if not has_wildcard:
            # Bare partial versions lacking wildcard characters are not permitted.
            if len(numbers) != 3:
                raise semver_range.InvalidRangeError(
                    f"Bare partial version '{body}' in range '{raw_range}' must use wildcard characters",
                    raw_range=raw_range,
                )
            version = self._parse_version_text(body, raw_range)
            return self._expand_complete_term(operator, version, raw_range)
        return self._expand_wildcard_term(operator, numbers, raw_range)

    def _expand_complete_term(
        self,
        operator: str,
        version: semver_core.Version,
        raw_range: str,
    ) -> List[_ComparatorClause]:
        """Expands a complete version term using relational, caret, or tilde semantics."""
        op = semver_core.ComparatorOp
        if operator in ("", "=", "=="):
            return [[(op.EQ, version)]]
        if operator == "!=":
            return [[(op.NE, version)]]
        if operator == "<":
            return [[(op.LT, version)]]
        if operator == "<=":
            return [[(op.LE, version)]]
        if operator == ">":
            return [[(op.GT, version)]]
        if operator == ">=":
            return [[(op.GE, version)]]
        if operator == "^":
            # Caret ranges bound changes below the left-most non-zero component.
            return [[(op.GE, version), (op.LT, _caret_upper_bound(version))]]
        if operator == "~":
            # Tilde ranges bound changes below the next minor boundary.
            upper = semver_core.Version(version.major, version.minor + 1, 0)
            return [[(op.GE, version), (op.LT, upper)]]
        raise semver_range.InvalidRangeError(
            f"Unsupported comparator '{operator}' in range '{raw_range}'",
            raw_range=raw_range,
        )

    def _expand_wildcard_term(
        self,
        operator: str,
        numbers: List[int],
        raw_range: str,
    ) -> List[_ComparatorClause]:
        """Expands a wildcard partial version into comparator inequalities."""
        op = semver_core.ComparatorOp
        numeric_count = len(numbers)
        # A bare wildcard covers every version.
        if numeric_count == 0:
            if operator in ("!=", "<", ">"):
                return []
            return [[]]
        lower = semver_core.Version(
            numbers[0],
            numbers[1] if numeric_count > 1 else 0,
            0,
        )
        if numeric_count > 1:
            upper = semver_core.Version(numbers[0], numbers[1] + 1, 0)
        else:
            upper = semver_core.Version(numbers[0] + 1, 0, 0)
        if operator in ("", "=", "==", "~"):
            return [[(op.GE, lower), (op.LT, upper)]]
        if operator == "^":
            # Caret expansion widens to the next major boundary for non-zero majors.
            if numeric_count > 1 and numbers[0] > 0:
                upper = semver_core.Version(numbers[0] + 1, 0, 0)
            return [[(op.GE, lower), (op.LT, upper)]]
        if operator == ">=":
            return [[(op.GE, lower)]]
        if operator == ">":
            return [[(op.GE, upper)]]
        if operator == "<":
            return [[(op.LT, lower)]]
        if operator == "<=":
            return [[(op.LT, upper)]]
        if operator == "!=":
            # Negation of a wildcard interval requires a union of two clauses.
            return [[(op.LT, lower)], [(op.GE, upper)]]
        raise semver_range.InvalidRangeError(
            f"Unsupported comparator '{operator}' in range '{raw_range}'",
            raw_range=raw_range,
        )

    def _clause_satisfied(
        self,
        engine: semver_core.VersionEngine,
        version: semver_core.Version,
        clause: _ComparatorClause,
        include_prerelease: bool,
    ) -> bool:
        """Tests a candidate version against one comparator clause."""
        if version.is_prerelease and not include_prerelease:
            # Pre-releases only match ranges explicitly targeting the same numbers.
            targets_prerelease = any(
                bound.is_prerelease
                and bound.major == version.major
                and bound.minor == version.minor
                and bound.patch == version.patch
                for _, bound in clause
            )
            if not targets_prerelease:
                return False
        for operator, bound in clause:
            precedence = engine.compare_precedence(version, bound)
            if not _comparator_holds(operator, precedence):
                return False
        return True


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
# LAST_CLEANED: 2026-11-05T05:39:02Z
# LAST_CHANGED: 2026-11-05T05:35:30Z
# CHANGE: Prune unreachable clause-compiler statements flagged by feedback: removed the dead empty-alternative guard after '>='/'<=' hyphen operand expansion and the unreachable end-of-input break in the tokenizer now that clauses are always trimmed; behavior unchanged for all conforming inputs.
# COVERAGE_AUDIT: 2026-11-05T05:39:02Z
# QA_AUDIT: 2026-11-05T05:38:48Z
# --- END AUTOFAB METADATA ---
