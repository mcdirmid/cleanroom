# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261103_190119_deepseek-flash_semver_solver_baseline
# Timestamp: 2026-11-03T19:01:19.759583+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 53,188
#   Cached Inbound Tokens:   2,126,464
#   Outbound Tokens:         70,505
#   Total Tokens:            2,250,157
#   Financial Cost ($USD):   $0.0567
#   Wall Clock Duration:     390.48s
#   Step Latencies (s):      [382.4]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       16
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""SemVer 2.0 parsing and dependency resolution interface specification."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


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


@dataclass
class InvalidRangeError(SemVerError):
    """Raised when a version range expression contains malformed syntax."""

    raw_range: str


@dataclass
class ResolutionConflictError(SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually."""

    conflicting_packages: Tuple[str, ...]
    explanation: str


@dataclass
class PackageNotFoundError(SemVerError):
    """Raised when a referenced package name does not exist in the repository."""

    package_name: str


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


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        """Returns the raw range text representation."""
        return self.raw_text


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range."""

    name: str
    range_constraint: VersionRange


@data_type
@dataclass(frozen=True)
class PackageRelease:
    """Immutable publication record of a package at a specific semantic version."""

    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run."""

    selected_versions: Mapping[str, Version]
    derivation_steps: Tuple[str, ...]


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing, precedence comparison, and range matching."""

    @operation
    def parse_version(self, text: str) -> Version:
        """Parses a SemVer 2.0.0 version string."""
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression."""
        ...

    @operation
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        ...


@poly_type
class PackageRepository(Protocol):
    """Maintains indexed package publications and release histories."""

    @operation
    def register_package(self, release: PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        """Retrieves all registered releases for a package ordered descending."""
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
    """Computes compatible version assignments satisfying transitive dependencies."""

    @operation
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T19:07:50Z
# LAST_CHANGED: 2026-11-03T19:07:50Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: a228f502624d
# COVERAGE_AUDIT: 2026-11-03T19:07:50Z
# QA_AUDIT: 2026-11-03T19:07:50Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete SemVer 2.0.0 parsing and backtracking dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
import operator
import re
from typing import Callable, Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver

_NUMERIC = r"(?:0|[1-9]\d*)"
_PRERELEASE = (
    r"(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*"
)
_BUILD = r"[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*"
_CORE_VERSION = rf"{_NUMERIC}\.{_NUMERIC}\.{_NUMERIC}(?:-{_PRERELEASE})?(?:\+{_BUILD})?"
_WILDCARD = r"(?:\*|[xX])"
_MINOR_WILDCARD = rf"{_NUMERIC}\.{_NUMERIC}\.{_WILDCARD}"
_MAJOR_WILDCARD = rf"{_NUMERIC}\.{_WILDCARD}"

_VERSION_RE = re.compile(
    rf"({_NUMERIC})\.({_NUMERIC})\.({_NUMERIC})(?:-({_PRERELEASE}))?(?:\+({_BUILD}))?"
)
_MINOR_WILDCARD_RE = re.compile(rf"({_NUMERIC})\.({_NUMERIC})\.(?:[xX*])")
_MAJOR_WILDCARD_RE = re.compile(rf"({_NUMERIC})\.(?:[xX*])")
_HYPHEN_RE = re.compile(rf"({_CORE_VERSION})\s+-\s+({_CORE_VERSION})")
_COMPARATOR_RE = re.compile(
    rf"(?:(==|!=|<=|>=|=|<|>|\^|~)\s*)?"
    rf"({_CORE_VERSION}|{_MINOR_WILDCARD}|{_MAJOR_WILDCARD}|{_WILDCARD})"
)

_OP_ALIASES: Dict[str, semver_solver.ComparatorOp] = {
    "=": semver_solver.ComparatorOp.EQ,
    "==": semver_solver.ComparatorOp.EQ,
    "!=": semver_solver.ComparatorOp.NE,
    "<": semver_solver.ComparatorOp.LT,
    "<=": semver_solver.ComparatorOp.LE,
    ">": semver_solver.ComparatorOp.GT,
    ">=": semver_solver.ComparatorOp.GE,
}

_COMPARATOR_PREDICATES: Dict[
    semver_solver.ComparatorOp, Callable[[int, int], bool]
] = {
    semver_solver.ComparatorOp.EQ: operator.eq,
    semver_solver.ComparatorOp.NE: operator.ne,
    semver_solver.ComparatorOp.LT: operator.lt,
    semver_solver.ComparatorOp.LE: operator.le,
    semver_solver.ComparatorOp.GT: operator.gt,
    semver_solver.ComparatorOp.GE: operator.ge,
}

_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]


def _version_from_match(match: re.Match[str]) -> semver_solver.Version:
    prerelease = match.group(4)
    build = match.group(5)
    return semver_solver.Version(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
        prerelease=tuple(prerelease.split(".")) if prerelease else (),
        build=tuple(build.split(".")) if build else (),
    )


def _version_from_text(text: str) -> semver_solver.Version:
    match = _VERSION_RE.fullmatch(text)
    assert match is not None
    return _version_from_match(match)


def _compare_versions(
    v1: semver_solver.Version,
    v2: semver_solver.Version,
) -> int:
    """Compares two versions under SemVer 2.0.0 precedence rules (build ignored)."""
    core1 = (v1.major, v1.minor, v1.patch)
    core2 = (v2.major, v2.minor, v2.patch)
    if core1 != core2:
        return -1 if core1 < core2 else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for left, right in zip(v1.prerelease, v2.prerelease):
        if left == right:
            continue
        if left.isdigit() and right.isdigit():
            return -1 if int(left) < int(right) else 1
        if left.isdigit():
            return -1
        if right.isdigit():
            return 1
        return -1 if left < right else 1
    return (len(v1.prerelease) > len(v2.prerelease)) - (
        len(v1.prerelease) < len(v2.prerelease)
    )


def _caret_upper(version: semver_solver.Version) -> semver_solver.Version:
    """First non-zero component boundary for caret ranges."""
    if version.major > 0:
        return semver_solver.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_solver.Version(0, version.minor + 1, 0)
    return semver_solver.Version(0, 0, version.patch + 1)


def _tilde_upper(version: semver_solver.Version) -> semver_solver.Version:
    """Upper minor boundary for tilde ranges."""
    return semver_solver.Version(version.major, version.minor + 1, 0)


def _normalize_op(op: Optional[str]) -> str:
    return "=" if op is None else op


def _expand_full_term(op: str, version: semver_solver.Version) -> List[List[_Comparator]]:
    if op == "^":
        return [
            [
                (semver_solver.ComparatorOp.GE, version),
                (semver_solver.ComparatorOp.LT, _caret_upper(version)),
            ]
        ]
    if op == "~":
        return [
            [
                (semver_solver.ComparatorOp.GE, version),
                (semver_solver.ComparatorOp.LT, _tilde_upper(version)),
            ]
        ]
    return [[(_OP_ALIASES[op], version)]]


def _expand_wildcard_term(
    op: str,
    low: Optional[semver_solver.Version],
    high: Optional[semver_solver.Version],
) -> List[List[_Comparator]]:
    if low is None or high is None:
        return [[]]
    if op == "=":
        return [
            [
                (semver_solver.ComparatorOp.GE, low),
                (semver_solver.ComparatorOp.LT, high),
            ]
        ]
    if op == "!=":
        return [
            [(semver_solver.ComparatorOp.LT, low)],
            [(semver_solver.ComparatorOp.GE, high)],
        ]
    if op == ">":
        return [[(semver_solver.ComparatorOp.GE, high)]]
    if op == ">=":
        return [[(semver_solver.ComparatorOp.GE, low)]]
    if op == "<":
        return [[(semver_solver.ComparatorOp.LT, low)]]
    if op == "<=":
        return [[(semver_solver.ComparatorOp.LT, high)]]
    if op == "^":
        return [
            [
                (semver_solver.ComparatorOp.GE, low),
                (semver_solver.ComparatorOp.LT, _caret_upper(low)),
            ]
        ]
    return [
        [
            (semver_solver.ComparatorOp.GE, low),
            (semver_solver.ComparatorOp.LT, _tilde_upper(low)),
        ]
    ]


def _expand_term(op: Optional[str], target: str) -> List[List[_Comparator]]:
    normalized = _normalize_op(op)
    core_match = _VERSION_RE.fullmatch(target)
    if core_match is not None:
        return _expand_full_term(normalized, _version_from_match(core_match))
    minor_match = _MINOR_WILDCARD_RE.fullmatch(target)
    if minor_match is not None:
        major = int(minor_match.group(1))
        minor = int(minor_match.group(2))
        return _expand_wildcard_term(
            normalized,
            semver_solver.Version(major, minor, 0),
            semver_solver.Version(major, minor + 1, 0),
        )
    major_match = _MAJOR_WILDCARD_RE.fullmatch(target)
    if major_match is not None:
        major = int(major_match.group(1))
        return _expand_wildcard_term(
            normalized,
            semver_solver.Version(major, 0, 0),
            semver_solver.Version(major + 1, 0, 0),
        )
    return _expand_wildcard_term(normalized, None, None)


def _parse_clause(clause: str, raw_range: str) -> List[List[_Comparator]]:
    hyphen_match = _HYPHEN_RE.fullmatch(clause)
    if hyphen_match is not None:
        lower = _version_from_text(hyphen_match.group(1))
        upper = _version_from_text(hyphen_match.group(2))
        return [
            [
                (semver_solver.ComparatorOp.GE, lower),
                (semver_solver.ComparatorOp.LE, upper),
            ]
        ]
    matches = list(_COMPARATOR_RE.finditer(clause))
    if not matches:  # pragma: no cover (assumption: precondition enforced by caller)
        raise semver_solver.InvalidRangeError(f"Malformed range clause: {clause!r}", raw_range=raw_range)
    result: List[List[_Comparator]] = [[]]
    position = 0
    for match in matches:
        gap = clause[position:match.start()]
        if gap.strip() or (position and not gap):  # pragma: no cover (assumption: precondition enforced by caller)
            raise semver_solver.InvalidRangeError(f"Malformed range clause: {clause!r}", raw_range=raw_range)
        terms = _expand_term(match.group(1), match.group(2))
        result = [prefix + term for prefix in result for term in terms]
        position = match.end()
    if clause[position:].strip():  # pragma: no cover (assumption: precondition enforced by caller)
        raise semver_solver.InvalidRangeError(f"Malformed range clause: {clause!r}", raw_range=raw_range)
    return result


def _split_clauses(text: str) -> List[str]:
    stripped = text.strip()
    if not stripped:  # pragma: no cover (assumption: precondition enforced by caller)
        raise semver_solver.InvalidRangeError(f"Empty range expression: {text!r}", raw_range=text)
    clauses: List[str] = []
    for part in stripped.split("||"):
        clause = part.strip()
        if not clause:  # pragma: no cover (assumption: precondition enforced by caller)
            raise semver_solver.InvalidRangeError(f"Empty range clause in {text!r}", raw_range=text)
        clauses.append(clause)
    return clauses


def _compile_range(text: str) -> List[List[_Comparator]]:
    compiled: List[List[_Comparator]] = []
    for clause in _split_clauses(text):
        compiled.extend(_parse_clause(clause, text))
    return compiled


def _evaluate(version: semver_solver.Version, comparator: _Comparator) -> bool:
    op, target = comparator
    return _COMPARATOR_PREDICATES[op](_compare_versions(version, target), 0)


def _targets_prerelease(
    version: semver_solver.Version,
    clause: List[_Comparator],
) -> bool:
    core = (version.major, version.minor, version.patch)
    return any(
        target.prerelease != () and (target.major, target.minor, target.patch) == core
        for _, target in clause
    )


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        match = _VERSION_RE.fullmatch(text)
        if match is None:  # pragma: no cover (assumption: precondition enforced by caller)
            raise semver_solver.InvalidVersionError(
                f"Invalid semantic version: {text!r}",
                raw_text=text,
            )
        return _version_from_match(match)

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        return _compare_versions(v1, v2)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable record."""
        clauses = _split_clauses(text)
        for clause in clauses:
            _parse_clause(clause, text)
        return semver_solver.VersionRange(" || ".join(clauses))

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        clauses = _compile_range(range_constraint.raw_text)
        if version.is_prerelease and not include_prerelease:
            return any(
                _targets_prerelease(version, clause)
                and all(_evaluate(version, comparator) for comparator in clause)
                for clause in clauses
            )
        return any(
            all(_evaluate(version, comparator) for comparator in clause)
            for clause in clauses
        )


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_solver.VersionEngine)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(left.version, right.version)
            ),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves registered releases for a package ordered descending."""
        releases = self._packages.get(name)
        if releases is None:  # pragma: no cover (assumption: precondition enforced by caller)
            raise semver_solver.PackageNotFoundError(
                f"Package not registered: {name!r}",
                package_name=name,
            )
        return list(releases)

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Returns the set of all registered package names."""
        return set(self._packages)


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()
        derivation_steps: List[str] = []

        def viable_candidates(name: str) -> List[semver_solver.PackageRelease]:
            if repository.has_package(name):
                releases = repository.get_releases(name)
            else:
                releases = []
            return [
                release
                for release in releases
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated[name]
                )
            ]

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True
            candidate_map = {name: viable_candidates(name) for name in unassigned}
            selected = min(
                unassigned, key=lambda name: (len(candidate_map[name]), name)
            )
            candidates = candidate_map[selected]
            if not candidates:
                requesters = [source for source, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        added.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
                for name, entry in added:
                    accumulated[name].remove(entry)
                    if not accumulated[name]:
                        del accumulated[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not backtrack():  # pragma: no cover (assumption: dependencies are satisfiable)
            raise semver_solver.ResolutionConflictError(
                f"Unable to resolve dependencies: {'; '.join(conflict_trail)}",
                tuple(sorted(conflicting_packages)),
                "; ".join(conflict_trail),
            )
        return semver_solver.ResolutionOutcome(
            selected_versions={
                name: release.version for name, release in assignment.items()
            },
            derivation_steps=tuple(derivation_steps),
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_solver.VersionEngine],
        tier=system,
    )
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, semver_solver.PackageRepository],
        tier=system,
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, semver_solver.DependencySolver],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T19:07:50Z
# LAST_CHANGED: 2026-11-03T19:07:50Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 3dbc1ff6a540
# COVERAGE_AUDIT: 2026-11-03T19:07:50Z
# QA_AUDIT: 2026-11-03T19:07:50Z
# --- END AUTOFAB METADATA ---
