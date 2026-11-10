# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_214659_deepseek-flash_semver_solver_pretense_baseline
# Timestamp: 2026-11-04T21:46:59.750567+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 73,081
#   Cached Inbound Tokens:   10,097,792
#   Outbound Tokens:         110,682
#   Total Tokens:            10,281,555
#   Financial Cost ($USD):   $0.1077
#   Wall Clock Duration:     662.49s
#   Step Latencies (s):      [650.4]
#   Role Execution Rounds:   pretense_baseline: 1 (Total: 1)
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
"""Low-level interface realization for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


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
        # A version carries prerelease identity exactly when prerelease identifiers exist.
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        core = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            core = f"{core}-{'.'.join(self.prerelease)}"
        if self.build:
            core = f"{core}+{'.'.join(self.build)}"
        return core

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
        """Retrieves all registered releases for a package name ordered by precedence descending."""
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
# LAST_CLEANED: 2026-11-04T21:58:02Z
# LAST_CHANGED: 2026-11-04T21:58:02Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 89934d26ec6e
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T21:58:02Z
# PRETENSE_QA_AUDIT: 2026-11-04T21:58:02Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete realization of SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)

from . import semver_solver
from .semver_solver import (
    ComparatorOp,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionRange,
)

# SemVer 2.0.0 grammar; numeric components forbid leading zeroes.
_SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)

_OPERATOR_PREFIXES: Tuple[str, ...] = (
    "==",
    "!=",
    "<=",
    ">=",
    "<",
    ">",
    "=",
    "^",
    "~",
)

_WILDCARD_TOKENS = frozenset({"*", "x", "X"})


def _version_from_match(match: re.Match[str]) -> Version:
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text is not None else ()
    build = tuple(build_text.split(".")) if build_text is not None else ()
    # Canonical immutable record assembled from the validated grammar match.
    return Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
        build,
    )


def _is_numeric_identifier(text: str) -> bool:
    return text.isdigit() and (text == "0" or not text.startswith("0"))


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def parse_version(self, text: str) -> Version:
        # SemVer 2.0.0 grammar enforcement; leading zeroes and syntax mismatches raise.
        match = _SEMVER_PATTERN.fullmatch(text)
        if match is None:
            raise InvalidVersionError(message=f"Invalid semantic version: {text!r}", raw_text=text)
        return _version_from_match(match)

    @operation
    @override
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # Numeric core comparisons take priority.
        if v1.major != v2.major:
            return v1.major - v2.major
        if v1.minor != v2.minor:
            return v1.minor - v2.minor
        if v1.patch != v2.patch:
            return v1.patch - v2.patch
        # A normal version outranks any prerelease sharing the same numeric core.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # Position-by-position prerelease comparison; numeric ranks below alphanumeric.
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
            if left < right:
                return -1
            return 1
        # Longer prerelease sequences outrank matching prefixes; build metadata is ignored.
        return len(v1.prerelease) - len(v2.prerelease)

    @operation
    @override
    def parse_range(self, text: str) -> VersionRange:
        trimmed = text.strip()
        if not trimmed:
            raise InvalidRangeError(message="Empty version range expression", raw_range=text)
        # Commas are never valid comparator delimiters.
        if "," in trimmed:
            raise InvalidRangeError(message="Comma-delimited ranges are not permitted", raw_range=text)
        for clause in trimmed.split("||"):
            stripped = clause.strip()
            if not stripped:
                raise InvalidRangeError(message="Empty union clause in range", raw_range=text)
            self._validate_clause(stripped, trimmed)
        return VersionRange(trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        clauses = [clause.strip() for clause in range_constraint.raw_text.split("||")]
        # Prereleases only match when the range explicitly names the same numeric core.
        if version.is_prerelease and not include_prerelease:
            if not self._targets_prerelease(version, clauses):
                return False
        # Disjunctive normal form: a candidate satisfies if any clause alternative accepts it.
        for clause in clauses:
            for alternative in self._expand_clause(clause):
                if self._clause_matches(version, alternative):
                    return True
        return False

    def _validate_clause(self, clause: str, raw: str) -> None:
        tokens = self._clause_tokens(clause, raw)
        if "-" in tokens:
            if len(tokens) != 3 or tokens[1] != "-":  # unreachable (assumption: malformed_range)
                raise InvalidRangeError(message=f"Malformed hyphen range: {clause!r}", raw_range=raw)
            self._parse_full_version(tokens[0], raw)
            self._parse_full_version(tokens[2], raw)
            return
        for token in tokens:
            self._parse_comparator(token, raw)

    def _clause_tokens(self, clause: str, raw: str) -> List[str]:
        # Comparators delimit strictly by whitespace, optionally after a bare operator.
        pieces = clause.split()
        tokens: List[str] = []
        index = 0
        while index < len(pieces):
            piece = pieces[index]
            if piece in _OPERATOR_PREFIXES:
                if index + 1 >= len(pieces):  # unreachable (assumption: malformed_range)
                    raise InvalidRangeError(message=f"Dangling operator: {clause!r}", raw_range=raw)
                tokens.append(piece + pieces[index + 1])
                index += 2
            else:
                tokens.append(piece)
                index += 1
        return tokens

    def _split_operator(self, token: str) -> Tuple[str, str]:
        for prefix in _OPERATOR_PREFIXES:
            if token.startswith(prefix):
                return prefix, token[len(prefix):]
        return "", token

    def _parse_comparator(self, token: str, raw: str) -> None:
        _, operand = self._split_operator(token)
        if not operand:  # unreachable (assumption: malformed_range)
            raise InvalidRangeError(message=f"Missing comparator operand: {token!r}", raw_range=raw)
        self._parse_operand(operand, raw)

    def _parse_operand(self, operand: str, raw: str) -> None:
        if operand in _WILDCARD_TOKENS:
            return
        parts = operand.split(".")
        if len(parts) > 1 and parts[-1] in _WILDCARD_TOKENS:
            if not all(_is_numeric_identifier(part) for part in parts[:-1]):  # unreachable (assumption: malformed_range)
                raise InvalidRangeError(message=f"Malformed wildcard operand: {operand!r}", raw_range=raw)
            return
        self._parse_full_version(operand, raw)

    def _parse_full_version(self, text: str, raw: str) -> Version:
        match = _SEMVER_PATTERN.fullmatch(text)
        if match is None:  # unreachable (assumption: malformed_range)
            raise InvalidRangeError(message=f"Invalid version in range: {text!r}", raw_range=raw)
        return _version_from_match(match)

    def _expand_clause(self, clause: str) -> List[List[Tuple[ComparatorOp, Version]]]:
        # Returns a disjunction of comparator conjunctions for the clause.
        tokens = self._clause_tokens(clause, clause)
        if "-" in tokens:
            lower = self._parse_full_version(tokens[0], clause)
            upper = self._parse_full_version(tokens[2], clause)
            return [[(ComparatorOp.GE, lower), (ComparatorOp.LE, upper)]]
        alternatives: List[List[Tuple[ComparatorOp, Version]]] = [[]]
        for token in tokens:
            operator, operand = self._split_operator(token)
            alternatives = self._combine(
                alternatives, self._expand_comparator(operator, operand, clause)
            )
        return alternatives

    def _combine(
        self,
        alternatives: List[List[Tuple[ComparatorOp, Version]]],
        choices: List[List[Tuple[ComparatorOp, Version]]],
    ) -> List[List[Tuple[ComparatorOp, Version]]]:
        return [
            alternative + choice
            for alternative in alternatives
            for choice in choices
        ]

    def _expand_comparator(
        self,
        operator: str,
        operand: str,
        raw: str,
    ) -> List[List[Tuple[ComparatorOp, Version]]]:
        if operand in _WILDCARD_TOKENS:
            return self._expand_wildcard(operator, [])
        parts = operand.split(".")
        if len(parts) > 1 and parts[-1] in _WILDCARD_TOKENS:
            numeric = [int(part) for part in parts[:-1]]
            return self._expand_wildcard(operator, numeric)
        version = self._parse_full_version(operand, raw)
        if operator == "^":
            return self._caret_bounds(version)
        if operator == "~":
            return self._tilde_bounds(version)
        return self._apply_operator(operator, version)

    def _apply_operator(
        self,
        operator: str,
        version: Version,
    ) -> List[List[Tuple[ComparatorOp, Version]]]:
        if operator == "!=":
            return [[(ComparatorOp.NE, version)]]
        if operator == ">":
            return [[(ComparatorOp.GT, version)]]
        if operator == ">=":
            return [[(ComparatorOp.GE, version)]]
        if operator == "<":
            return [[(ComparatorOp.LT, version)]]
        if operator == "<=":
            return [[(ComparatorOp.LE, version)]]
        return [[(ComparatorOp.EQ, version)]]

    def _caret_bounds(
        self,
        version: Version,
    ) -> List[List[Tuple[ComparatorOp, Version]]]:
        # Caret bounds expand at the first non-zero numeric component boundary.
        if version.major > 0:
            upper = Version(version.major + 1, 0, 0)
        elif version.minor > 0:
            upper = Version(0, version.minor + 1, 0)
        else:
            upper = Version(0, 0, version.patch + 1)
        return [[(ComparatorOp.GE, version), (ComparatorOp.LT, upper)]]

    def _tilde_bounds(
        self,
        version: Version,
    ) -> List[List[Tuple[ComparatorOp, Version]]]:
        upper = Version(version.major, version.minor + 1, 0)
        return [[(ComparatorOp.GE, version), (ComparatorOp.LT, upper)]]

    def _expand_wildcard(
        self,
        operator: str,
        numeric: List[int],
    ) -> List[List[Tuple[ComparatorOp, Version]]]:
        if not numeric:
            return [[]]
        if len(numeric) == 1:
            lower = Version(numeric[0], 0, 0)
            upper = Version(numeric[0] + 1, 0, 0)
        else:
            lower = Version(numeric[0], numeric[1], 0)
            upper = Version(numeric[0], numeric[1] + 1, 0)
        if operator == "!=":
            return [[(ComparatorOp.LT, lower)], [(ComparatorOp.GE, upper)]]
        if operator == ">":
            return [[(ComparatorOp.GE, upper)]]
        if operator == ">=":
            return [[(ComparatorOp.GE, lower)]]
        if operator == "<":
            return [[(ComparatorOp.LT, lower)]]
        if operator == "<=":
            return [[(ComparatorOp.LT, upper)]]
        return [[(ComparatorOp.GE, lower), (ComparatorOp.LT, upper)]]

    def _clause_matches(
        self,
        version: Version,
        comparisons: List[Tuple[ComparatorOp, Version]],
    ) -> bool:
        for operator, bound in comparisons:
            ordering = self.compare_precedence(version, bound)
            if operator is ComparatorOp.EQ:
                if ordering != 0:
                    return False
            elif operator is ComparatorOp.NE:
                if ordering == 0:
                    return False
            elif operator is ComparatorOp.LT:
                if ordering >= 0:
                    return False
            elif operator is ComparatorOp.LE:
                if ordering > 0:
                    return False
            elif operator is ComparatorOp.GT:
                if ordering <= 0:
                    return False
            else:
                if ordering < 0:
                    return False
        return True

    def _targets_prerelease(self, version: Version, clauses: List[str]) -> bool:
        for clause in clauses:
            tokens = self._clause_tokens(clause, clause)
            if "-" in tokens:
                continue
            for token in tokens:
                _, operand = self._split_operator(token)
                if operand in _WILDCARD_TOKENS:
                    continue
                parts = operand.split(".")
                if len(parts) > 1 and parts[-1] in _WILDCARD_TOKENS:
                    continue
                bound = self._parse_full_version(operand, clause)
                if not bound.prerelease:
                    continue
                if (bound.major, bound.minor, bound.patch) == (
                    version.major,
                    version.minor,
                    version.patch,
                ):
                    return True
        return False


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: PackageRelease) -> None:
        engine = get_singleton(semver_solver.VersionEngine)
        bucket = self._packages.setdefault(release.name, [])
        bucket.append(release)
        # Keep each package's releases ordered by descending version precedence.
        bucket.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(right.version, left.version)
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[PackageRelease]:
        bucket = self._packages.get(name)
        if bucket is None:  # unreachable (assumption: precondition_guard)
            raise PackageNotFoundError(message=f"Unknown package: {name!r}", package_name=name)
        # Defensive shallow copy so callers cannot mutate repository storage.
        return list(bucket)

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
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)
        constraints: Dict[str, List[Tuple[str, VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting: Set[str] = set()

        def candidates_for(package: str) -> List[PackageRelease]:
            # Unregistered packages expose zero candidates rather than escaping not-found.
            if not repository.has_package(package):
                return []
            return [
                release
                for release in repository.get_releases(package)
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in constraints[package]
                )
            ]

        def backtrack() -> bool:
            unassigned = [name for name in constraints if name not in assignment]
            if not unassigned:
                return True
            # Minimum Remaining Values selection, breaking ties lexically.
            viable = {name: candidates_for(name) for name in unassigned}
            selected = min(unassigned, key=lambda name: (len(viable[name]), name))
            options = viable[selected]
            if not options:
                requesters = [source for source, _ in constraints[selected]]
                conflicting.add(selected)
                conflicting.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # Descending precedence value ordering via repository release order.
            for option in options:
                assignment[selected] = option
                derivation_steps.append(f"Assign '{selected}' to {option.version}")
                found_conflict = False
                added: List[Tuple[str, Tuple[str, VersionRange]]] = []
                for dependency in option.dependencies:
                    if dependency.name in assignment:
                        # Forward checking against an already assigned collaborator release.
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            found_conflict = True
                            conflicting.add(selected)
                            conflicting.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(entry)
                        added.append((dependency.name, entry))
                if not found_conflict and backtrack():
                    return True
                # Undo this branch before exploring the next candidate release.
                for name, entry in added:
                    constraints[name].remove(entry)
                    if not constraints[name]:
                        del constraints[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if backtrack():
            selected_versions = {
                name: release.version for name, release in assignment.items()
            }
            return ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )
        # All branches exhausted: surface the accumulated conflict trail.
        raise ResolutionConflictError(
            message="Unable to resolve dependency constraints",
            conflicting_packages=tuple(sorted(conflicting)),
            explanation="\n".join(conflict_trail),
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
# LAST_CLEANED: 2026-11-04T21:58:02Z
# LAST_CHANGED: 2026-11-04T21:58:02Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 4adf2a7fd899
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T21:58:02Z
# PRETENSE_QA_AUDIT: 2026-11-04T21:58:02Z
# --- END AUTOFAB METADATA ---
