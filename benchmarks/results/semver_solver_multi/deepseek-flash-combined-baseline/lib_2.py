# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261107_032205_deepseek-flash_semver_solver_multi_combined_baseline
# Timestamp: 2026-11-07T03:22:05.185049+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: combined_baseline
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 92,523
#   Cached Inbound Tokens:   9,269,504
#   Outbound Tokens:         101,496
#   Total Tokens:            9,463,523
#   Financial Cost ($USD):   $0.1026
#   Wall Clock Duration:     758.96s
#   Step Latencies (s):      [729.0]
#   Role Execution Rounds:   combined_baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       36
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
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: c754f37852d9
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
from __future__ import annotations
from functools import cmp_to_key
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from support.lib.framework import singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dependency_solver
from . import semver_core
from . import semver_range

# Requirements specified in dependency_solver_impl.pyi

@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Indexed release histories keyed by package name.
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # POSTCONDITIONS: insert the release and keep descending precedence order.
        version_engine = get_singleton(semver_core.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: version_engine.compare_precedence(right.version, left.version)
            )
        )

    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # PRECONDITIONS: WHEN name is not registered, MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                f"package '{name}' is not registered", name
            )
        # POSTCONDITIONS: shallow copy of the descending-precedence release list.
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        # POSTCONDITIONS: True exactly when the package name is registered.
        return name in self._packages

    def all_packages(self) -> Set[str]:
        # POSTCONDITIONS: set of all registered package names.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        # No cross-call state is retained between independent resolution runs.
        pass

    def resolve(
        self, root_dependencies: Collection[dependency_solver.PackageDependency]
    ) -> dependency_solver.ResolutionOutcome:
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)

        # Accumulated constraints map each package to (requester, range) requirements.
        accumulated: Dict[str, List[Tuple[str, semver_range.VersionRange]]] = {}
        for dep in root_dependencies:
            accumulated.setdefault(dep.name, []).append(("root", dep.range_constraint))

        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(name: str) -> List[dependency_solver.PackageRelease]:
            # Missing packages possess zero candidate releases.
            if not repository.has_package(name):
                return []
            return [
                release
                for release in repository.get_releases(name)
                if all(
                    range_engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated[name]
                )
            ]

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                # Complete mutually compatible assignment found.
                return True

            candidates: Dict[str, List[dependency_solver.PackageRelease]] = {
                name: viable_releases(name) for name in unassigned
            }
            # MRV variable selection with lexical tie-breaking.
            selected = min(unassigned, key=lambda name: (len(candidates[name]), name))
            options = candidates[selected]
            if not options:
                requesters = sorted({source for source, _ in accumulated[selected]})
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"no viable release for '{selected}' required by {', '.join(requesters)}"
                )
                return False

            # Value ordering: explore releases in descending precedence order.
            for candidate in options:
                assignment[selected] = candidate
                derivation_steps.append(f"assign '{selected}' to {candidate.version}")

                blocked = False
                added: List[Tuple[str, Tuple[str, semver_range.VersionRange]]] = []
                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        if not range_engine.satisfies(
                            assignment[dep.name].version, dep.range_constraint, False
                        ):
                            blocked = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dep.name)
                            conflict_trail.append(
                                f"'{selected}' requires '{dep.name}' {dep.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dep.range_constraint)
                        accumulated.setdefault(dep.name, []).append(entry)
                        added.append((dep.name, entry))

                if not blocked and backtrack():
                    return True

                for dep_name, entry in added:
                    accumulated[dep_name].remove(entry)
                    if not accumulated[dep_name]:
                        del accumulated[dep_name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if not backtrack():
            raise dependency_solver.ResolutionConflictError(
                "dependency resolution failed",
                tuple(sorted(conflicting_packages)),
                "; ".join(conflict_trail),
            )

        selected_versions = {
            name: release.version for name, release in assignment.items()
        }
        return dependency_solver.ResolutionOutcome(
            selected_versions, tuple(derivation_steps)
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
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 6ae02979e1a2
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
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
        """Returns the diagnostic message for this error."""
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
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base = f"{base}-{'.'.join(self.prerelease)}"
        if self.build:
            base = f"{base}+{'.'.join(self.build)}"
        return base

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
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: fc2c9b547c48
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
from __future__ import annotations
import re
from typing import Optional

from support.lib.framework import singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_core

# Requirements specified in semver_core_impl.pyi

_NUMERIC = r"(?:0|[1-9][0-9]*)"
_IDENTIFIER = r"(?:[0-9A-Za-z-]+)"

_VERSION_PATTERN = re.compile(
    rf"^({_NUMERIC})\.({_NUMERIC})\.({_NUMERIC})"
    rf"(?:-({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?"
    rf"(?:\+({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?$"
)


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    def __init__(self) -> None:
        # The engine is stateless; parsing and comparison use module grammar.
        pass

    def parse_version(self, text: str) -> semver_core.Version:
        # PRECONDITIONS: grammar violations and numeric leading zeroes raise InvalidVersionError.
        match = _VERSION_PATTERN.match(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                f"invalid semantic version '{text}'", text
            )
        # POSTCONDITIONS: split optional dot-separated prerelease and build tuples.
        major, minor, patch, prerelease, build = match.groups()
        return semver_core.Version(
            int(major),
            int(minor),
            int(patch),
            tuple(prerelease.split(".")) if prerelease else (),
            tuple(build.split(".")) if build else (),
        )

    def compare_precedence(
        self, v1: semver_core.Version, v2: semver_core.Version
    ) -> int:
        # POSTCONDITIONS: compare major, minor, and patch numerically in sequence.
        if v1.major != v2.major:
            return v1.major - v2.major
        if v1.minor != v2.minor:
            return v1.minor - v2.minor
        if v1.patch != v2.patch:
            return v1.patch - v2.patch

        # A normal version outranks a prerelease sharing the same numeric core.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # Compare prerelease identifiers left to right.
        for left, right in zip(v1.prerelease, v2.prerelease):
            if left == right:
                continue
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                return int(left) - int(right)
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left < right else 1

        # A longer prerelease sequence outranks a shorter matching prefix.
        return len(v1.prerelease) - len(v2.prerelease)


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
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9f15214e62c3
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
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
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 3d38c6185072
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
from __future__ import annotations
import re
from typing import List, Optional, Tuple

from support.lib.framework import singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_core
from . import semver_range

# Requirements specified in semver_range_impl.pyi

_NUMERIC = r"(?:0|[1-9][0-9]*)"
_WILDCARD = r"(?:[xX*])"
_COMPONENT = rf"(?:{_NUMERIC}|{_WILDCARD})"
_IDENTIFIER = r"(?:[0-9A-Za-z-]+)"

_FULL_VERSION_PATTERN = re.compile(
    rf"^({_NUMERIC})\.({_NUMERIC})\.({_NUMERIC})"
    rf"(?:-({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?"
    rf"(?:\+({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?$"
)
_PARTIAL_VERSION_PATTERN = re.compile(
    rf"^({_COMPONENT})(?:\.({_COMPONENT}))?(?:\.({_COMPONENT}))?$"
)
_OPERATOR_PATTERN = re.compile(r"^(==|!=|<=|>=|=|<|>|\^|~)(.*)$")
_HYPHEN_SEPARATOR = re.compile(r"\s+-\s+")
_STANDALONE_OPERATORS = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")

_Comparator = Tuple[str, semver_core.Version]


class _InvalidSyntax(Exception):
    """Internal marker for malformed range syntax."""

    pass


def _is_wildcard(text: str) -> bool:
    return text in ("x", "X", "*")


def _parse_target(
    text: str,
) -> Tuple[str, semver_core.Version, Optional[semver_core.Version]]:
    """Classifies a range target as an exact version or a wildcard interval."""
    full = _FULL_VERSION_PATTERN.match(text)
    if full is not None:
        major, minor, patch, prerelease, build = full.groups()
        return (
            "version",
            semver_core.Version(
                int(major),
                int(minor),
                int(patch),
                tuple(prerelease.split(".")) if prerelease else (),
                tuple(build.split(".")) if build else (),
            ),
            None,
        )

    partial = _PARTIAL_VERSION_PATTERN.match(text)
    if partial is None:
        raise _InvalidSyntax()
    components = partial.groups()
    numbers = [0, 0, 0]
    wildcard_index = -1
    for index, component in enumerate(components):
        if component is None:
            continue
        if _is_wildcard(component):
            if wildcard_index < 0:
                wildcard_index = index
            continue
        if wildcard_index >= 0:
            raise _InvalidSyntax()
        numbers[index] = int(component)
    if wildcard_index < 0:
        # Bare partial version lacking any wildcard character is malformed.
        raise _InvalidSyntax()

    lower = semver_core.Version(numbers[0], numbers[1], numbers[2])
    upper: Optional[semver_core.Version]
    if wildcard_index == 0:
        upper = None
    elif wildcard_index == 1:
        upper = semver_core.Version(numbers[0] + 1, 0, 0)
    else:
        upper = semver_core.Version(numbers[0], numbers[1] + 1, 0)
    return ("wildcard", lower, upper)


def _interval_clause(
    lower: semver_core.Version, upper: Optional[semver_core.Version]
) -> List[List[_Comparator]]:
    if upper is None:
        return [[(">=", lower)]]
    return [[(">=", lower), ("<", upper)]]


def _comparator_clause(
    operator: str,
    kind: str,
    lower: semver_core.Version,
    upper: Optional[semver_core.Version],
) -> List[List[_Comparator]]:
    if kind == "version":
        return [[(operator, lower)]]
    if operator == "==":
        return _interval_clause(lower, upper)
    if operator == "!=":
        if upper is None:
            return []
        return [[("<", lower)], [(">=", upper)]]
    if operator == "<":
        return [[("<", lower)]]
    if operator == "<=":
        if upper is None:
            return [[]]
        return [[("<", upper)]]
    if operator == ">":
        if upper is None:
            return []
        return [[(">=", upper)]]
    return [[(">=", lower)]]


def _caret_upper(lower: semver_core.Version) -> semver_core.Version:
    if lower.major > 0:
        return semver_core.Version(lower.major + 1, 0, 0)
    if lower.minor > 0:
        return semver_core.Version(0, lower.minor + 1, 0)
    return semver_core.Version(0, 0, lower.patch + 1)


def _caret_clause(
    kind: str,
    lower: semver_core.Version,
    upper: Optional[semver_core.Version],
) -> List[List[_Comparator]]:
    if kind == "version":
        return [[(">=", lower), ("<", _caret_upper(lower))]]
    if lower.major > 0 or lower.minor > 0:
        return [[(">=", lower), ("<", _caret_upper(lower))]]
    if upper is None:
        return [[(">=", lower)]]
    return [[(">=", lower), ("<", upper)]]


def _tilde_clause(
    kind: str,
    lower: semver_core.Version,
    upper: Optional[semver_core.Version],
) -> List[List[_Comparator]]:
    if kind == "version":
        return [
            [(">=", lower), ("<", semver_core.Version(lower.major, lower.minor + 1, 0))]
        ]
    return _interval_clause(lower, upper)


def _expand_token(token: str) -> List[List[_Comparator]]:
    match = _OPERATOR_PATTERN.match(token)
    if match is None:
        kind, lower, upper = _parse_target(token)
        if kind == "version":
            return [[("==", lower)]]
        return _interval_clause(lower, upper)

    operator = match.group(1)
    kind, lower, upper = _parse_target(match.group(2).strip())
    if operator == "^":
        return _caret_clause(kind, lower, upper)
    if operator == "~":
        return _tilde_clause(kind, lower, upper)
    if operator == "=":
        operator = "=="
    return _comparator_clause(operator, kind, lower, upper)


def _parse_clause_tokens(tokens: List[str]) -> List[List[_Comparator]]:
    alternatives: List[List[_Comparator]] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _STANDALONE_OPERATORS:
            if index + 1 >= len(tokens):
                raise _InvalidSyntax()
            token = token + tokens[index + 1]
            index += 2
        else:
            index += 1
        fragment = _expand_token(token)
        if not fragment:
            return []
        alternatives = [left + right for left in alternatives for right in fragment]
    return alternatives


def _expand_hyphen(left_text: str, right_text: str) -> List[List[_Comparator]]:
    _, left_lower, _ = _parse_target(left_text)
    right_kind, right_lower, right_upper = _parse_target(right_text)
    comparators: List[_Comparator] = [(">=", left_lower)]
    if right_kind == "version":
        comparators.append(("<=", right_lower))
        return [comparators]
    if right_upper is None:
        return [comparators]
    comparators.append(("<", right_upper))
    return [comparators]


def _parse_clause(text: str) -> List[List[_Comparator]]:
    stripped = text.strip()
    if not stripped:
        raise _InvalidSyntax()
    if "," in stripped:
        raise _InvalidSyntax()
    hyphen_parts = _HYPHEN_SEPARATOR.split(stripped)
    if len(hyphen_parts) > 1:
        if len(hyphen_parts) != 2:
            raise _InvalidSyntax()
        return _expand_hyphen(hyphen_parts[0].strip(), hyphen_parts[1].strip())
    return _parse_clause_tokens(stripped.split())


def _compile(text: str) -> List[List[_Comparator]]:
    """Compiles range text into disjunctive normal form comparator sets."""
    trimmed = text.strip()
    if not trimmed:
        raise _InvalidSyntax()
    clauses: List[List[_Comparator]] = []
    for alternative in trimmed.split("||"):
        clauses.extend(_parse_clause(alternative))
    return clauses


def _targets_prerelease(
    clauses: List[List[_Comparator]], version: semver_core.Version
) -> bool:
    for clause in clauses:
        for _, boundary in clause:
            if (
                boundary.is_prerelease
                and boundary.major == version.major
                and boundary.minor == version.minor
                and boundary.patch == version.patch
            ):
                return True
    return False


def _matches(
    version_engine: semver_core.VersionEngine,
    version: semver_core.Version,
    operator: str,
    boundary: semver_core.Version,
) -> bool:
    ordering = version_engine.compare_precedence(version, boundary)
    if operator == "==":
        return ordering == 0
    if operator == "!=":
        return ordering != 0
    if operator == "<":
        return ordering < 0
    if operator == "<=":
        return ordering <= 0
    if operator == ">":
        return ordering > 0
    return ordering >= 0


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    def __init__(self) -> None:
        # The engine is stateless; range compilation is derived from raw text.
        pass

    def parse_range(self, text: str) -> semver_range.VersionRange:
        trimmed = text.strip()
        try:
            _compile(trimmed)
        except _InvalidSyntax as error:
            raise semver_range.InvalidRangeError(
                f"invalid version range '{text}'", text
            ) from error
        # POSTCONDITIONS: store the trimmed range expression in raw_text.
        return semver_range.VersionRange(trimmed)

    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        version_engine = get_singleton(semver_core.VersionEngine)
        clauses = _compile(range_constraint.raw_text)

        # Prerelease candidates only match ranges explicitly targeting that core.
        if version.is_prerelease and not include_prerelease:
            if not _targets_prerelease(clauses, version):
                return False

        for clause in clauses:
            if all(
                _matches(version_engine, version, operator, boundary)
                for operator, boundary in clause
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
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 5de30b98a67a
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---
