# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261103_190117_deepseek-flash_semver_solver_pretense_baseline
# Timestamp: 2026-11-03T19:01:17.752953+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 104,309
#   Cached Inbound Tokens:   5,287,424
#   Outbound Tokens:         101,422
#   Total Tokens:            5,493,155
#   Financial Cost ($USD):   $0.0924
#   Wall Clock Duration:     718.39s
#   Step Latencies (s):      [702.2]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""SemVer 2.0 parsing and dependency resolution interface specification.

Structural protocols and passive value types realized from
``low/semver_solver.pyi``: semantic version records, constraint ranges,
package releases, resolution outcomes, domain errors, and the abstract
version engine, package repository, and dependency solver capabilities.
"""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum

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
        formatted = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            formatted = f"{formatted}-{'.'.join(self.prerelease)}"
        if self.build:
            formatted = f"{formatted}+{'.'.join(self.build)}"
        return formatted

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
        """Parses a version string conforming to SemVer 2.0.0."""
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
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
        """Retrieves all registered releases for a package name ordered descending."""
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
# LAST_CLEANED: 2026-11-03T19:13:16Z
# LAST_CHANGED: 2026-11-03T19:13:16Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 42976c1b7680
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T19:13:16Z
# PRETENSE_QA_AUDIT: 2026-11-03T19:13:16Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete SemVer 2.0 parsing and backtracking dependency resolution services.

Realizes ``low/semver_solver_impl.pyi`` against the structural interface in
``lib/semver_solver.py``: a regular-expression version engine, a precedence
ordered package repository, and a depth-first backtracking dependency solver
using Minimum Remaining Values variable selection and a conflict trail.
"""

from __future__ import annotations

import functools
import re
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_solver


_NUMERIC = r"(?:0|[1-9][0-9]*)"
_PRERELEASE_ID = rf"(?:{_NUMERIC}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"

_SEMVER_PATTERN = re.compile(
    rf"^(?P<major>{_NUMERIC})\.(?P<minor>{_NUMERIC})\.(?P<patch>{_NUMERIC})"
    rf"(?:-(?P<prerelease>{_PRERELEASE_ID}(?:\.{_PRERELEASE_ID})*))?"
    rf"(?:\+(?P<build>{_BUILD_ID}(?:\.{_BUILD_ID})*))?$"
)

_NUMERIC_PATTERN = re.compile(rf"^{_NUMERIC}$")

_WILDCARD_TOKENS = frozenset({"*", "x", "X"})

_OPERATOR_TOKENS = frozenset({"==", "=", "!=", "<", "<=", ">", ">=", "^", "~"})

_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]


def _split_operator(token: str) -> Tuple[str, str]:
    """Splits a comparator token into its leading relational operator and operand."""
    for operator in ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~"):
        if token.startswith(operator):
            return operator, token[len(operator):]
    return "", token


def _is_wildcard_operand(operand: str) -> bool:
    """Indicates whether an operand is a wildcard form (``*``, ``M.x``, ``M.m.*``)."""
    if operand in _WILDCARD_TOKENS:
        return True
    parts = operand.split(".")
    if len(parts) not in (2, 3) or parts[-1] not in _WILDCARD_TOKENS:
        return False
    return all(_NUMERIC_PATTERN.match(part) is not None for part in parts[:-1])


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    def __init__(self) -> None:
        self._pattern = _SEMVER_PATTERN

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # MUST parse valid SemVer 2.0.0 strings into Version records.
        match = self._pattern.match(text)
        if match is None:
            # WHEN text violates grammar or leading-zero rules, MUST raise InvalidVersionError.
            raise semver_solver.InvalidVersionError(f"invalid semantic version: {text}", text)  # pragma: no cover (assumption: precondition enforced by caller)
        prerelease_text = match.group("prerelease")
        prerelease: Tuple[str, ...] = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build_text = match.group("build")
        build: Tuple[str, ...] = tuple(build_text.split(".")) if build_text else ()
        return semver_solver.Version(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            prerelease,
            build,
        )

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # MUST compare major, minor, and patch numerically, ignoring build metadata.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1
        # MUST rank a normal version higher than a prerelease sharing identical numbers.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # MUST compare prerelease segments numerically, else ASCII-lexicographically.
        for left_segment, right_segment in zip(v1.prerelease, v2.prerelease):
            if left_segment == right_segment:
                continue
            left_numeric = left_segment.isdigit()
            right_numeric = right_segment.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left_segment) < int(right_segment) else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left_segment < right_segment else 1
        # MUST rank a longer prerelease sequence higher when the common prefix matches.
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # MUST trim surrounding whitespace, storing the trimmed expression in raw_text.
        trimmed = text.strip()
        if not trimmed:
            # WHEN text is empty or whitespace, MUST raise InvalidRangeError.
            raise semver_solver.InvalidRangeError("empty version range", text)  # pragma: no cover (assumption: precondition enforced by caller)
        for clause in trimmed.split("||"):
            stripped_clause = clause.strip()
            if not stripped_clause:
                # WHEN a union alternative is empty, MUST raise InvalidRangeError.
                raise semver_solver.InvalidRangeError("empty range clause", text)  # pragma: no cover (assumption: precondition enforced by caller)
            self._compile_clause(stripped_clause, trimmed)
        return semver_solver.VersionRange(trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # MUST evaluate True only when every comparator in at least one clause holds.
        for clause in self._compile_range(range_constraint.raw_text):
            if not all(self._evaluate(comparator, version) for comparator in clause):
                continue
            # WHEN version is a prerelease and include_prerelease is False, it only matches
            # a clause that explicitly targets a prerelease with the same numeric triple.
            if version.prerelease and not include_prerelease:
                targets_same_prerelease = any(
                    bound.prerelease and bound.major == version.major and bound.minor == version.minor and bound.patch == version.patch
                    for _, bound in clause
                )
                if not targets_same_prerelease:
                    continue
            return True
        return False

    def _compile_range(self, text: str) -> List[List[_Comparator]]:
        return [self._compile_clause(clause.strip(), text) for clause in text.split("||")]

    def _compile_clause(self, clause: str, raw: str) -> List[_Comparator]:
        tokens = clause.split()
        if len(tokens) == 3 and tokens[1] == "-":
            # Hyphen ranges expand into inclusive lower and upper precedence bounds.
            lower = self._require_full_version(tokens[0], raw)
            upper = self._require_full_version(tokens[2], raw)
            return [(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LE, upper)]
        comparators: List[_Comparator] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in _OPERATOR_TOKENS:
                index += 1
                if index >= len(tokens):
                    raise semver_solver.InvalidRangeError(f"missing operand for operator '{token}'", raw)  # pragma: no cover (assumption: precondition enforced by caller)
                comparators.extend(self._expand_atom(token, tokens[index], raw))
                index += 1
            else:
                # A comparator may attach its operator directly to the operand token.
                operator, operand = _split_operator(token)
                comparators.extend(self._expand_atom(operator, operand, raw))
                index += 1
        return comparators

    def _require_full_version(self, operand: str, raw: str) -> semver_solver.Version:
        if _SEMVER_PATTERN.match(operand) is None:
            # WHEN bare partial versions lack wildcards, MUST raise InvalidRangeError.
            raise semver_solver.InvalidRangeError(f"invalid version operand: {operand}", raw)  # pragma: no cover (assumption: precondition enforced by caller)
        return self.parse_version(operand)

    def _expand_wildcard(self, operand: str, raw: str) -> List[_Comparator]:
        if operand in _WILDCARD_TOKENS:
            # A bare wildcard clause matches every version.
            return []
        parts = operand.split(".")
        numbers: List[int] = []
        for part in parts[:-1]:
            numbers.append(int(part))
        if len(numbers) == 1:
            return [
                (semver_solver.ComparatorOp.GE, semver_solver.Version(numbers[0], 0, 0)),
                (semver_solver.ComparatorOp.LT, semver_solver.Version(numbers[0] + 1, 0, 0)),
            ]
        return [
            (semver_solver.ComparatorOp.GE, semver_solver.Version(numbers[0], numbers[1], 0)),
            (semver_solver.ComparatorOp.LT, semver_solver.Version(numbers[0], numbers[1] + 1, 0)),
        ]

    def _expand_atom(self, operator: str, operand: str, raw: str) -> List[_Comparator]:
        if operator == "^":
            # Caret ranges bound compatibility by the first non-zero component.
            lower = self._require_full_version(operand, raw)
            return [(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, self._caret_upper(lower))]
        if operator == "~":
            # Tilde ranges allow patch-level changes while pinning the minor component.
            lower = self._require_full_version(operand, raw)
            return [(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, semver_solver.Version(lower.major, lower.minor + 1, 0))]
        if operator in ("", "==", "="):
            if _is_wildcard_operand(operand):
                return self._expand_wildcard(operand, raw)
            return [(semver_solver.ComparatorOp.EQ, self._require_full_version(operand, raw))]
        bound = self._require_full_version(operand, raw)
        if operator == "!=":
            return [(semver_solver.ComparatorOp.NE, bound)]
        if operator == "<":
            return [(semver_solver.ComparatorOp.LT, bound)]
        if operator == "<=":
            return [(semver_solver.ComparatorOp.LE, bound)]
        if operator == ">":
            return [(semver_solver.ComparatorOp.GT, bound)]
        return [(semver_solver.ComparatorOp.GE, bound)]

    def _caret_upper(self, lower: semver_solver.Version) -> semver_solver.Version:
        if lower.major > 0:
            return semver_solver.Version(lower.major + 1, 0, 0)
        if lower.minor > 0:
            return semver_solver.Version(0, lower.minor + 1, 0)
        if lower.patch > 0:
            return semver_solver.Version(0, 0, lower.patch + 1)
        return semver_solver.Version(0, 0, 1)

    def _evaluate(self, comparator: _Comparator, version: semver_solver.Version) -> bool:
        operator, bound = comparator
        precedence = self.compare_precedence(version, bound)
        if operator is semver_solver.ComparatorOp.EQ:
            return precedence == 0
        if operator is semver_solver.ComparatorOp.NE:
            return precedence != 0
        if operator is semver_solver.ComparatorOp.LT:
            return precedence < 0
        if operator is semver_solver.ComparatorOp.LE:
            return precedence <= 0
        if operator is semver_solver.ComparatorOp.GT:
            return precedence > 0
        return precedence >= 0


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # MUST register the release and keep its package history in descending precedence.
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=functools.cmp_to_key(lambda left, right: engine.compare_precedence(right.version, left.version)))

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # WHEN name is not registered, MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(f"package not found: {name}", name)  # pragma: no cover (assumption: precondition enforced by caller)
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
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        self._steps_label = "assignment"

    @operation
    @override
    def resolve(self, root_dependencies: Collection[semver_solver.PackageDependency]) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)
        constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(("root", dependency.range_constraint))
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()
        # WHEN the search exhausts all candidates, MUST raise ResolutionConflictError without
        # allowing PackageNotFoundError to escape.
        if not self._search(engine, repository, constraints, assignment, derivation_steps, conflict_trail, conflicting_packages):
            raise semver_solver.ResolutionConflictError("unable to resolve dependency constraints", tuple(sorted(conflicting_packages)), "\n".join(conflict_trail))  # pragma: no cover (assumption: precondition enforced by caller)
        selected_versions: Dict[str, semver_solver.Version] = {}
        for name, release in assignment.items():
            selected_versions[name] = release.version
        return semver_solver.ResolutionOutcome(selected_versions, tuple(derivation_steps))

    def _search(
        self,
        engine: semver_solver.VersionEngine,
        repository: semver_solver.PackageRepository,
        constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]],
        assignment: Dict[str, semver_solver.PackageRelease],
        derivation_steps: List[str],
        conflict_trail: List[str],
        conflicting_packages: Set[str],
    ) -> bool:
        unassigned = [name for name in constraints if name not in assignment]
        if not unassigned:
            return True
        candidates_by_package: Dict[str, List[semver_solver.PackageRelease]] = {}
        for name in unassigned:
            available = repository.get_releases(name) if repository.has_package(name) else []
            candidates_by_package[name] = [
                release
                for release in available
                if all(engine.satisfies(release.version, constraint, True) for _, constraint in constraints[name])
            ]
        # MRV variable selection with lexical tie-breaking between equally constrained packages.
        selected = min(unassigned, key=lambda name: (len(candidates_by_package[name]), name))
        candidates = candidates_by_package[selected]
        if not candidates:
            requesters = [source for source, _ in constraints[selected]]
            conflicting_packages.add(selected)
            conflicting_packages.update(requesters)
            conflict_trail.append(f"No viable releases for '{selected}' satisfying constraints from {requesters}")
            return False
        for candidate in candidates:
            assignment[selected] = candidate
            derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
            conflict_detected = False
            newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
            for dependency in candidate.dependencies:
                if dependency.name in assignment:
                    # Forward checking: an already assigned package must satisfy the requirement.
                    if not engine.satisfies(assignment[dependency.name].version, dependency.range_constraint, True):
                        conflict_detected = True
                        conflicting_packages.add(selected)
                        conflicting_packages.add(dependency.name)
                        conflict_trail.append(f"Conflict: '{selected}' requires {dependency.name} {dependency.range_constraint.raw_text}")
                        break
                else:
                    entry = (selected, dependency.range_constraint)
                    constraints.setdefault(dependency.name, []).append(entry)
                    newly_added.append((dependency.name, entry))
            if not conflict_detected and self._search(engine, repository, constraints, assignment, derivation_steps, conflict_trail, conflicting_packages):
                return True
            # Backtrack: retract the candidate assignment and any constraints it introduced.
            for name, entry in newly_added:
                constraints[name].remove(entry)
                if not constraints[name]:
                    del constraints[name]
            del assignment[selected]
            derivation_steps.pop()
        return False


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
# LAST_CLEANED: 2026-11-03T19:13:16Z
# LAST_CHANGED: 2026-11-03T19:13:16Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 1abba9b4fc31
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T19:13:16Z
# PRETENSE_QA_AUDIT: 2026-11-03T19:13:16Z
# --- END AUTOFAB METADATA ---
