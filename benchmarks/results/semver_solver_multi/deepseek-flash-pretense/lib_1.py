# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_164811_deepseek-flash_semver_solver_multi_pretense
# Timestamp: 2026-11-05T16:48:11.564663+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 345,475
#   Cached Inbound Tokens:   28,852,479
#   Outbound Tokens:         362,321
#   Total Tokens:            29,560,275
#   Financial Cost ($USD):   $0.3558
#   Wall Clock Duration:     1979.88s
#   Step Latencies (s):      [527.3, 525.4, 143.2, 104.1, 10.3, 142.2, 66.8, 439.4, 21.1, 110.0, 151.8, 75.2, 64.3, 10.8, 88.7, 43.1, 10.5, 10.3]
#   Role Execution Rounds:   lib: 3, pretense: 5, pretense_coverage: 4, pretense_qa: 6 (Total: 18)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       6
#   Unit Tests Failed:       0
#   Line Coverage:           99.0%
#   Branch Coverage:         99.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from support.lib.framework import data_type, operation, poly_type
from . import semver_core
from . import semver_range


@dataclass
class PackageNotFoundError(semver_core.SemVerError):
    """Raised when a referenced package name does not exist in the repository.

    Args:
        message: Diagnostic description of the missing package.
        package_name: Name of the missing package.
    """

    package_name: str


@dataclass
class ResolutionConflictError(semver_core.SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually.

    Args:
        message: Diagnostic description of the conflict.
        conflicting_packages: Sequence of package names involved in the conflict.
        explanation: Detailed diagnostic derivation of the unsatisfiable conflict.
    """

    conflicting_packages: Tuple[str, ...]
    explanation: str


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range.

    Args:
        name: Name of the required package.
        range_constraint: Acceptable version range constraint.
    """

    name: str
    range_constraint: semver_range.VersionRange


@data_type
@dataclass(frozen=True)
class PackageRelease:
    """Immutable publication record of a package at a specific semantic version.

    Args:
        name: Name of the package.
        version: Semantic version of this release.
        dependencies: Declared prerequisite package dependencies.
    """

    name: str
    version: semver_core.Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run.

    Args:
        selected_versions: Mapping of package names to their selected semantic versions.
        derivation_steps: Ordered sequence of decision and deduction steps.
    """

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
# LAST_CLEANED: 2026-11-05T16:57:08Z
# LAST_CHANGED: 2026-11-05T16:57:08Z
# CHANGE: Implement dependency solver interface: PackageNotFoundError/ResolutionConflictError dataclass exceptions, frozen PackageDependency/PackageRelease/ResolutionOutcome data types, and PackageRepository/DependencySolver protocols.
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
from __future__ import annotations

import re
from typing import Optional
from typing import Any, Collection, Dict, List, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dependency_solver
from . import semver_core
from . import semver_range

# SemVer 2.0.0 numeric prerelease identifiers are restricted to ASCII digits.
_NUMERIC_IDENTIFIER_PATTERN = re.compile(r"[0-9]+")


def _identifier_key(identifier: str) -> Tuple[int, Any]:
    """Builds an orderable key for a prerelease identifier."""
    # POSTCONDITIONS: only ASCII digits are numeric; every other identifier is
    # ranked through ASCII lexical comparison without numeric conversion.
    if _NUMERIC_IDENTIFIER_PATTERN.fullmatch(identifier) is not None:
        # Numeric identifiers order by magnitude: significant length, then the
        # digit sequence, avoiding integer conversion of arbitrarily long values.
        digits = identifier.lstrip("0")
        return (0, (len(digits), digits))
    return (1, identifier)


def _precedence_key(version: semver_core.Version) -> Tuple[int, int, int, int, Tuple[Tuple[int, Any], ...]]:
    """Builds a descending-precedence orderable key ignoring build metadata."""
    if version.prerelease:
        identifiers = tuple(_identifier_key(item) for item in version.prerelease)
        # POSTCONDITIONS: prereleases rank below normal versions sharing the same core.
        return (version.major, version.minor, version.patch, 0, identifiers)
    return (version.major, version.minor, version.patch, 1, ())


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # INVARIANTS: each registered name maps to its releases sorted in
        # descending version precedence order.
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # POSTCONDITIONS: re-sort releases into descending version precedence order.
        releases.sort(key=lambda item: _precedence_key(item.version), reverse=True)

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # PRECONDITIONS: unregistered names MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
        # POSTCONDITIONS: yield a shallow copy of the sorted release list.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
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
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        # Accumulated constraints map each package name to requesters and ranges.
        accumulated_constraints: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated_constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def satisfies(version: semver_core.Version, constraint: semver_range.VersionRange) -> bool:
            # Delegate range matching to the range engine collaborator.
            return range_engine.satisfies(version, constraint, False)

        def backtrack() -> bool:
            unassigned = [name for name in accumulated_constraints if name not in assignment]
            if not unassigned:
                return True
            # POSTCONDITIONS: absent packages evaluate to zero viable candidates.
            candidates: Dict[str, List[dependency_solver.PackageRelease]] = {}
            for name in unassigned:
                available = repository.get_releases(name) if repository.has_package(name) else []
                candidates[name] = [
                    release
                    for release in available
                    if all(
                        satisfies(release.version, constraint)
                        for _, constraint in accumulated_constraints[name]
                    )
                ]
            # POSTCONDITIONS: MRV heuristic picks the fewest viable candidates,
            # breaking ties through lexical package name comparison.
            selected = min(unassigned, key=lambda name: (len(candidates[name]), name))
            options = candidates[selected]
            if not options:
                requesters = [requester for requester, _ in accumulated_constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(
                    requester for requester in requesters if requester != "root"
                )
                # Record the unsatisfiable branch in the conflict trail.
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # POSTCONDITIONS: explore candidates in descending precedence order.
            for candidate in options:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []

                # Forward checking: verify declared dependencies against the assignment.
                for requirement in candidate.dependencies:
                    if requirement.name in assignment:
                        if not satisfies(
                            assignment[requirement.name].version,
                            requirement.range_constraint,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(requirement.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{requirement.name}' "
                                f"{requirement.range_constraint}"
                            )
                            break
                    else:
                        constraint_entry = (selected, requirement.range_constraint)
                        accumulated_constraints.setdefault(requirement.name, []).append(
                            constraint_entry
                        )
                        newly_added.append((requirement.name, constraint_entry))

                if not conflict_detected and backtrack():
                    return True

                # Restore the pre-assignment constraint mapping on branch failure.
                for name, constraint_entry in newly_added:
                    accumulated_constraints[name].remove(constraint_entry)
                    if not accumulated_constraints[name]:
                        del accumulated_constraints[name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if not backtrack():
            explanation = "\n".join(conflict_trail)
            # PRECONDITIONS: unsatisfiable constraints MUST raise ResolutionConflictError.
            raise dependency_solver.ResolutionConflictError(
                message=f"Dependency resolution failed: {explanation}",
                conflicting_packages=tuple(sorted(conflicting_packages)),
                explanation=explanation,
            )

        # POSTCONDITIONS: compile the selected version mapping and decision sequence.
        selected_versions: Dict[str, semver_core.Version] = {
            name: release.version for name, release in assignment.items()
        }
        return dependency_solver.ResolutionOutcome(
            selected_versions=selected_versions,
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
# LAST_CLEANED: 2026-11-05T17:18:48Z
# LAST_CHANGED: 2026-11-05T17:18:12Z
# CHANGE: Resolve fuzz feedback in _identifier_key: classify prerelease identifiers as numeric only when they match strict ASCII digits [0-9] via a compiled regex, so non-ASCII digit-like identifiers such as '¹' fall through to ASCII lexical alphanumeric ranking instead of raising ValueError from int(). Numeric ordering now compares significant length then digit sequence rather than converting to int, so registers never abort on directly constructed Version values, preserving descending-precedence release ordering in register_package/get_releases.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:18:48Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:18:35Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error. Verification suites MUST NOT assert on specific wording or prefixes within message, and MUST assert on exception types and structured attributes.
    """

    message: str

    def __str__(self) -> str:
        # Exceptions realized with dataclass semantics surface their diagnostic message.
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered.

    Args:
        message: Diagnostic description of the error.
        raw_text: Original unparseable version string.
    """

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
    """Immutable semantic version representation conforming to SemVer 2.0.0.

    Args:
        major: Non-negative integer major version.
        minor: Non-negative integer minor version.
        patch: Non-negative integer patch version.
        prerelease: Ordered tuple of dot-separated pre-release identifiers.
        build: Ordered tuple of dot-separated build metadata identifiers.
    """

    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        """Indicates whether this version contains pre-release identifiers."""
        # POSTCONDITIONS: true exactly when at least one prerelease identifier is present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        # POSTCONDITIONS: major.minor.patch with optional -prerelease and +build suffixes.
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
# LAST_CLEANED: 2026-11-05T16:55:49Z
# LAST_CHANGED: 2026-11-05T16:55:49Z
# CHANGE: Implement SemVer 2.0 interface: message-bearing excadd dataclass exceptions (SemVerError/InvalidVersionError with __str__), ComparatorOp enum, frozen Version data type with is_prerelease/format/__str__, and VersionEngine protocol.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations

import re
from typing import Optional

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import semver_core

# SemVer 2.0.0 grammar: no leading zeroes in numeric core components or numeric
# prerelease identifiers, and build metadata identifiers are unconstrained.
_VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z"
)
_NUMERIC_IDENTIFIER_PATTERN = re.compile(r"[0-9]+")


def _compare_identifiers(left: str, right: str) -> int:
    """Compares two prerelease identifiers under SemVer precedence rules."""
    left_numeric = _NUMERIC_IDENTIFIER_PATTERN.fullmatch(left) is not None
    right_numeric = _NUMERIC_IDENTIFIER_PATTERN.fullmatch(right) is not None
    if left_numeric and right_numeric:
        left_number = int(left)
        right_number = int(right)
        if left_number != right_number:
            return -1 if left_number < right_number else 1
        return 0
    # POSTCONDITIONS: numeric identifiers always rank below alphanumeric identifiers.
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    # POSTCONDITIONS: alphanumeric identifiers compare by ASCII code point.
    if left != right:
        return -1 if left < right else 1
    return 0


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        # PRECONDITIONS: grammar or leading-zero violations MUST raise InvalidVersionError.
        match = _VERSION_PATTERN.match(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                message=f"Version '{text}' does not conform to SemVer 2.0.0 grammar",
                raw_text=text,
            )
        major_text, minor_text, patch_text, prerelease_text, build_text = match.groups()
        # POSTCONDITIONS: build an immutable Version with parsed prerelease/build tuples.
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
    def compare_precedence(self, v1: semver_core.Version, v2: semver_core.Version) -> int:
        # POSTCONDITIONS: compare major, minor, and patch numerically in sequence.
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1
        # POSTCONDITIONS: rank normal versions above prereleases sharing the same core.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # POSTCONDITIONS: compare prerelease segments position by position.
        for left_identifier, right_identifier in zip(v1.prerelease, v2.prerelease):
            result = _compare_identifiers(left_identifier, right_identifier)
            if result != 0:
                return result
        # POSTCONDITIONS: a longer prerelease sequence ranks higher when prefixes match.
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
# LAST_CLEANED: 2026-11-05T17:11:58Z
# LAST_CHANGED: 2026-11-05T16:56:55Z
# CHANGE: Implement VersionEngine singleton: strict SemVer 2.0 grammar parsing with leading-zero rejection raising InvalidVersionError, plus precedence comparison over numeric core, prerelease ranking, and build exclusion.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:11:58Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:11:36Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from support.lib.framework import data_type, operation, poly_type
from . import semver_core


@dataclass
class InvalidRangeError(semver_core.SemVerError):
    """Raised when a version range expression contains malformed syntax.

    Args:
        message: Diagnostic description of the error.
        raw_range: Original malformed range expression string.
    """

    raw_range: str


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression.

    Args:
        raw_text: Canonical text representation of the range expression.
    """

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
# LAST_CLEANED: 2026-11-05T16:56:33Z
# LAST_CHANGED: 2026-11-05T16:56:33Z
# CHANGE: Implement version range interface: InvalidRangeError with raw_range, frozen VersionRange data type with raw_text and __str__, and RangeEngine protocol declaring parse_range/satisfies.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import FrozenSet, List, Optional, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import semver_core
from . import semver_range

# Comparators are delimited strictly by whitespace; comma delimiters are rejected.
_OPERATOR_PREFIXES: Tuple[str, ...] = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")
_WILDCARD_MARKERS: FrozenSet[str] = frozenset({"*", "x", "X"})
_CORE_NUMBER_PATTERN = re.compile(r"(0|[1-9][0-9]*)")
_IDENTIFIER_PATTERN = re.compile(r"[0-9A-Za-z-]+")
_NUMERIC_IDENTIFIER_PATTERN = re.compile(r"[0-9]+")

@dataclass(frozen=True)
class _VersionParts:
    """Parsed version components where ``None`` marks an open wildcard position."""

    major: Optional[int]
    minor: Optional[int]
    patch: Optional[int]
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_wildcard(self) -> bool:
        return self.major is None or self.minor is None or self.patch is None

    def to_version(self) -> semver_core.Version:
        """Materializes the parsed components into a concrete version record."""
        return semver_core.Version(
            major=self.major if self.major is not None else 0,
            minor=self.minor if self.minor is not None else 0,
            patch=self.patch if self.patch is not None else 0,
            prerelease=self.prerelease,
            build=self.build,
        )


_Atom = Tuple[str, semver_core.Version]
_Alternatives = List[List[_Atom]]
_Clause = List[Tuple[str, _VersionParts]]


def _split_operator(token: str) -> Tuple[str, str]:
    """Splits a relational/prefix operator from a comparator token."""
    for prefix in _OPERATOR_PREFIXES:
        if token.startswith(prefix):
            return prefix, token[len(prefix):]
    return "", token


def _parse_identifiers(text: str, *, forbid_leading_zeroes: bool) -> Tuple[str, ...]:
    """Parses a dot-separated prerelease or build metadata identifier sequence."""
    if not text:
        raise ValueError("identifier sequence is empty")
    identifiers = text.split(".")
    for identifier in identifiers:
        if _IDENTIFIER_PATTERN.fullmatch(identifier) is None:
            raise ValueError(f"identifier '{identifier}' contains disallowed characters")
        if (
            forbid_leading_zeroes
            and _NUMERIC_IDENTIFIER_PATTERN.fullmatch(identifier) is not None
            and len(identifier) > 1
            and identifier.startswith("0")
        ):
            raise ValueError(f"numeric identifier '{identifier}' has leading zeroes")
    return tuple(identifiers)


def _parse_version_parts(text: str) -> _VersionParts:
    """Parses a (possibly wildcard) version expression into its components."""
    core = text
    build: Tuple[str, ...] = ()
    plus_index = core.find("+")
    if plus_index >= 0:
        # Build metadata is split first because it may itself contain hyphens.
        build = _parse_identifiers(core[plus_index + 1:], forbid_leading_zeroes=False)
        core = core[:plus_index]
    prerelease: Tuple[str, ...] = ()
    dash_index = core.find("-")
    if dash_index >= 0:
        prerelease = _parse_identifiers(core[dash_index + 1:], forbid_leading_zeroes=True)
        core = core[:dash_index]
    pieces = core.split(".")
    if len(pieces) > 3:
        raise ValueError("version expression must have at most three core components")
    components: List[Optional[int]] = []
    wildcard_seen = False
    for piece in pieces:
        if piece in _WILDCARD_MARKERS:
            wildcard_seen = True
            components.append(None)
            continue
        if wildcard_seen:
            # Wildcards may only occupy trailing component positions.
            raise ValueError(f"numeric component '{piece}' follows a wildcard")
        if _CORE_NUMBER_PATTERN.fullmatch(piece) is None:
            raise ValueError(f"core component '{piece}' is not a valid number")
        components.append(int(piece))
    while len(components) < 3:
        components.append(None)
    # PRECONDITIONS: prerelease/build markers never combine with wildcard components.
    if wildcard_seen and (prerelease or build):
        raise ValueError("wildcard version expressions cannot carry prerelease or build metadata")
    # PRECONDITIONS: bare partial versions lacking wildcard characters are malformed.
    if not wildcard_seen and len(pieces) < 3:
        raise ValueError("partial version expressions require trailing wildcard characters")
    return _VersionParts(components[0], components[1], components[2], prerelease, build)


def _checked_version_parts(text: str, raw_range: str) -> _VersionParts:
    """Parses a version expression, reifying syntax errors as InvalidRangeError."""
    try:
        return _parse_version_parts(text)
    except ValueError as error:
        raise semver_range.InvalidRangeError(
            message=f"Invalid version expression '{text}' in range '{raw_range}': {error}",
            raw_range=raw_range,
        ) from error


def _parse_clause(clause: str, raw_range: str) -> _Clause:
    """Parses one union clause into an ordered conjunction of comparators."""
    tokens = clause.split()
    if "-" in tokens:
        # POSTCONDITIONS: hyphen ranges normalize into paired comparator inequalities.
        if len(tokens) != 3 or tokens[1] != "-":
            raise semver_range.InvalidRangeError(
                message=f"Hyphen range is malformed in range '{raw_range}'",
                raw_range=raw_range,
            )
        lower = _checked_version_parts(tokens[0], raw_range)
        upper = _checked_version_parts(tokens[2], raw_range)
        if lower.is_wildcard or upper.is_wildcard:
            raise semver_range.InvalidRangeError(
                message=f"Hyphen range requires full versions in range '{raw_range}'",
                raw_range=raw_range,
            )
        return [(">=", lower), ("<=", upper)]
    comparators: _Clause = []
    index = 0
    while index < len(tokens):
        operator, remainder = _split_operator(tokens[index])
        if not remainder:
            # POSTCONDITIONS: whitespace is accepted between an operator and its version.
            index += 1
            if index >= len(tokens):
                raise semver_range.InvalidRangeError(
                    message=f"Operator '{operator}' has no target version in range '{raw_range}'",
                    raw_range=raw_range,
                )
            remainder = tokens[index]
        comparators.append((operator, _checked_version_parts(remainder, raw_range)))
        index += 1
    return comparators


def _parse_clauses(text: str, raw_range: str) -> List[_Clause]:
    """Parses a full range expression into union clauses of comparators."""
    stripped = text.strip()
    # PRECONDITIONS: empty ranges and comma delimiters MUST raise InvalidRangeError.
    if not stripped:
        raise semver_range.InvalidRangeError(
            message="Version range expression is empty",
            raw_range=raw_range,
        )
    if "," in stripped:
        raise semver_range.InvalidRangeError(
            message=f"Comma delimiters are not permitted in range '{raw_range}'",
            raw_range=raw_range,
        )
    clauses: List[_Clause] = []
    for raw_clause in stripped.split("||"):
        clause = raw_clause.strip()
        # PRECONDITIONS: empty union clauses MUST raise InvalidRangeError.
        if not clause:
            raise semver_range.InvalidRangeError(
                message=f"Union in range '{raw_range}' contains an empty clause",
                raw_range=raw_range,
            )
        clauses.append(_parse_clause(clause, raw_range))
    return clauses


def _compare_identifiers(left: str, right: str) -> int:
    """Compares two prerelease identifiers under SemVer precedence rules."""
    left_numeric = _NUMERIC_IDENTIFIER_PATTERN.fullmatch(left) is not None
    right_numeric = _NUMERIC_IDENTIFIER_PATTERN.fullmatch(right) is not None
    if left_numeric and right_numeric:
        left_number = int(left)
        right_number = int(right)
        if left_number != right_number:
            return -1 if left_number < right_number else 1
        return 0
    # POSTCONDITIONS: numeric identifiers rank below alphanumeric identifiers.
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    if left != right:
        return -1 if left < right else 1
    return 0


def _compare_versions(left: semver_core.Version, right: semver_core.Version) -> int:
    """Compares two versions by precedence, ignoring build metadata."""
    # POSTCONDITIONS: compare major, minor, and patch numerically in sequence.
    if left.major != right.major:
        return -1 if left.major < right.major else 1
    if left.minor != right.minor:
        return -1 if left.minor < right.minor else 1
    if left.patch != right.patch:
        return -1 if left.patch < right.patch else 1
    # POSTCONDITIONS: normal versions rank above prereleases sharing the same core.
    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1
    for left_identifier, right_identifier in zip(left.prerelease, right.prerelease):
        result = _compare_identifiers(left_identifier, right_identifier)
        if result != 0:
            return result
    if len(left.prerelease) == len(right.prerelease):
        return 0
    return -1 if len(left.prerelease) < len(right.prerelease) else 1


def _expand_wildcard(operator: str, parts: _VersionParts) -> _Alternatives:
    """Normalizes a wildcard comparator into disjunctive atomic inequalities."""
    major = parts.major
    if major is None:
        # An open wildcard matches every version, so `!= *` matches nothing.
        if operator == "!=":
            return []
        return [[]]
    minor = parts.minor
    if minor is None:
        lower = semver_core.Version(major, 0, 0)
        upper = semver_core.Version(major + 1, 0, 0)
    else:
        lower = semver_core.Version(major, minor, 0)
        upper = semver_core.Version(major, minor + 1, 0)
    if operator == ">":
        return [[(">=", upper)]]
    if operator == ">=":
        return [[(">=", lower)]]
    if operator == "<":
        return [[("<", lower)]]
    if operator == "<=":
        return [[("<", upper)]]
    if operator == "!=":
        return [[("<", lower)], [(">=", upper)]]
    # POSTCONDITIONS: wildcard equality and tilde forms normalize into intervals.
    return [[(">=", lower), ("<", upper)]]


def _expand_caret(parts: _VersionParts) -> _Alternatives:
    """Expands a caret comparator into lower and upper boundaries."""
    major = parts.major
    if major is None:
        # An open caret wildcard matches every version.
        return [[]]
    lower = parts.to_version()
    minor = parts.minor
    if minor is None:
        # POSTCONDITIONS: `^M.x` spans the whole major line.
        return [[(">=", lower), ("<", semver_core.Version(major + 1, 0, 0))]]
    patch = parts.patch
    if patch is None:
        # POSTCONDITIONS: `^0.m.x` stays below the next minor, other majors advance.
        if major == 0:
            return [[(">=", lower), ("<", semver_core.Version(0, minor + 1, 0))]]
        return [[(">=", lower), ("<", semver_core.Version(major + 1, 0, 0))]]
    # POSTCONDITIONS: caret expands at the first non-zero core component boundary.
    if major > 0:
        upper = semver_core.Version(major + 1, 0, 0)
    elif minor > 0:
        upper = semver_core.Version(0, minor + 1, 0)
    else:
        upper = semver_core.Version(0, 0, patch + 1)
    return [[(">=", lower), ("<", upper)]]


def _expand_comparator(operator: str, parts: _VersionParts) -> _Alternatives:
    """Expands one parsed comparator into disjunctive atomic inequalities."""
    if operator == "^":
        return _expand_caret(parts)
    if parts.is_wildcard:
        return _expand_wildcard(operator, parts)
    version = parts.to_version()
    if operator in ("", "=", "=="):
        return [[("==", version)]]
    if operator == "!=":
        return [[("!=", version)]]
    if operator == "~":
        # POSTCONDITIONS: tilde expands into lower and upper minor boundaries.
        upper = semver_core.Version(version.major, version.minor + 1, 0)
        return [[(">=", version), ("<", upper)]]
    return [[(operator, version)]]


def _clause_alternatives(clause: _Clause) -> _Alternatives:
    """Compiles a clause into disjunctive normal form over atomic comparisons."""
    alternatives: _Alternatives = [[]]
    for operator, parts in clause:
        expanded = _expand_comparator(operator, parts)
        combined: _Alternatives = []
        for existing in alternatives:
            for alternative in expanded:
                combined.append(existing + alternative)
        alternatives = combined
    return alternatives


def _atom_holds(version: semver_core.Version, operator: str, bound: semver_core.Version) -> bool:
    """Evaluates a single atomic comparison using precedence ordering."""
    comparison = _compare_versions(version, bound)
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


def _targets_prerelease(parts: _VersionParts, version: semver_core.Version) -> bool:
    """Indicates whether a comparator explicitly targets the candidate prerelease core."""
    return (
        bool(parts.prerelease)
        and parts.major == version.major
        and parts.minor == version.minor
        and parts.patch == version.patch
    )


def _matches_clause(version: semver_core.Version, clause: _Clause, include_prerelease: bool) -> bool:
    """Evaluates a candidate version against one conjunction of comparators."""
    # POSTCONDITIONS: prereleases are filtered unless explicitly targeted by the clause.
    if version.is_prerelease and not include_prerelease:
        if not any(_targets_prerelease(parts, version) for _, parts in clause):
            return False
    # POSTCONDITIONS: a candidate satisfies a clause when every atomic comparison holds.
    for alternative in _clause_alternatives(clause):
        if all(_atom_holds(version, operator, bound) for operator, bound in alternative):
            return True
    return False


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        stripped = text.strip()
        # PRECONDITIONS: malformed syntax MUST raise InvalidRangeError.
        _parse_clauses(stripped, text)
        # POSTCONDITIONS: produce a VersionRange holding the trimmed range expression.
        return semver_range.VersionRange(raw_text=stripped)

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # POSTCONDITIONS: compile the expression into disjunctive comparator sets.
        clauses = _parse_clauses(range_constraint.raw_text, range_constraint.raw_text)
        # POSTCONDITIONS: true when any union clause is satisfied, false otherwise.
        for clause in clauses:
            if _matches_clause(version, clause, include_prerelease):
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
# LAST_CLEANED: 2026-11-05T17:21:05Z
# LAST_CHANGED: 2026-11-05T17:05:21Z
# CHANGE: Resolve unreachable-code coverage feedback: pruned the empty version-expression guard in _parse_version_parts (malformed core components already raise via the numeric-pattern guard) and the empty-comparator-list guard in _parse_clause (parse_range/satisfies only route non-empty trimmed clauses into clause parsing), and removed the always-false 'not pieces' condition. No conforming public call sequence can reach those spans, so behavior is unchanged while dead defensive code is eliminated.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:21:05Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:20:52Z
# --- END AUTOFAB METADATA ---
