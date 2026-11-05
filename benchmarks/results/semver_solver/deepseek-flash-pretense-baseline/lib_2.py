# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_040026_deepseek-flash_semver_solver_pretense_baseline
# Timestamp: 2026-11-05T04:00:26.106996+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 79,517
#   Cached Inbound Tokens:   7,588,352
#   Outbound Tokens:         105,578
#   Total Tokens:            7,773,447
#   Financial Cost ($USD):   $0.0980
#   Wall Clock Duration:     645.53s
#   Step Latencies (s):      [633.2]
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
"""Interface types and service protocols for SemVer 2.0 parsing and dependency resolution."""

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
        # Diagnostics are carried by the structured message field.
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
        # A version is a pre-release exactly when pre-release identifiers are present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Canonical SemVer rendering: numeric core, optional pre-release, optional build.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = text + "-" + ".".join(self.prerelease)
        if self.build:
            text = text + "+" + ".".join(self.build)
        return text

    def __str__(self) -> str:
        # Canonical string representation is defined as format().
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        # Range stringification yields the stored raw range text.
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
# LAST_CLEANED: 2026-11-05T04:11:11Z
# LAST_CHANGED: 2026-11-05T04:11:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 4cfac5a18aaa
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:11:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:11:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete SemVer 2.0.0 engine, release repository, and backtracking dependency solver."""

from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver


# SemVer 2.0.0 grammar: numeric core without leading zeroes, optional pre-release, optional build.
_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_OPERATOR_PATTERN = re.compile(r"^(==|!=|<=|>=|<|>|=|\^|~)?(.*)$")

_RELATIONAL_OPERATORS: Dict[str, semver_solver.ComparatorOp] = {
    "<": semver_solver.ComparatorOp.LT,
    "<=": semver_solver.ComparatorOp.LE,
    ">": semver_solver.ComparatorOp.GT,
    ">=": semver_solver.ComparatorOp.GE,
}


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # Grammar-violating and leading-zero inputs are rejected as contracted.
        match = _VERSION_PATTERN.match(text)
        if match is None:
            raise semver_solver.InvalidVersionError(  # pragma: no cover (assumption: caller supplies grammar-valid version text)
                f"Invalid semantic version: {text}", text
            )
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        build = tuple(match.group(5).split(".")) if match.group(5) else ()
        return semver_solver.Version(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=prerelease,
            build=build,
        )

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        # Numeric core components dominate precedence ordering.
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1

        # A normal version outranks a pre-release sharing the same numeric core.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # Compare pre-release identifiers left to right until a difference is found.
        for left, right in zip(v1.prerelease, v2.prerelease):
            if left == right:
                continue
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left) < int(right) else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left < right else 1

        # A longer pre-release sequence outranks a matching shorter prefix.
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Surrounding whitespace around the expression and each clause is trimmed.
        trimmed = " || ".join(part.strip() for part in text.strip().split("||"))
        # Validation expands the expression into its comparator clauses; the result is discarded.
        self._compile_range(trimmed)
        return semver_solver.VersionRange(trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        clauses = self._compile_range(range_constraint.raw_text)
        for clause in clauses:
            # A clause succeeds when every comparator accepts the candidate.
            if not all(self._accepts(version, op, target) for op, target in clause):
                continue
            if version.is_prerelease and not include_prerelease:
                # Pre-releases are excluded unless a boundary targets the same numeric core.
                if not any(
                    target.is_prerelease
                    and target.major == version.major
                    and target.minor == version.minor
                    and target.patch == version.patch
                    for _, target in clause
                ):
                    continue
            return True
        return False

    def _compile_range(
        self, raw_text: str
    ) -> List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
        # Empty or whitespace-only expressions are malformed.
        if not raw_text:
            raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
                f"Invalid version range: {raw_text!r}", raw_text
            )
        # Comma-delimited comparator lists are not part of the range grammar.
        if "," in raw_text:
            raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
                f"Invalid version range: {raw_text!r}", raw_text
            )
        clauses: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]] = []
        for part in raw_text.split("||"):
            clause = part.strip()
            # Empty union clauses are malformed.
            if not clause:
                raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
                    f"Invalid version range: {raw_text!r}", raw_text
                )
            clauses.append(self._compile_clause(clause, raw_text))
        return clauses

    def _compile_clause(
        self,
        clause: str,
        raw_text: str,
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        tokens = self._tokenize_clause(clause)
        # Hyphen ranges pair a lower and upper full version bound.
        if "-" in tokens:
            if len(tokens) != 3 or tokens[1] != "-":
                raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
                    f"Invalid version range: {raw_text!r}", raw_text
                )
            return [
                (semver_solver.ComparatorOp.GE, self._version_token(tokens[0], raw_text)),
                (semver_solver.ComparatorOp.LE, self._version_token(tokens[2], raw_text)),
            ]
        comparators: List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]] = []
        for token in tokens:
            comparators.extend(self._expand_token(token, raw_text))
        return comparators

    def _tokenize_clause(self, clause: str) -> List[str]:
        # Comparators are delimited strictly by whitespace.
        raw_tokens = clause.split()
        tokens: List[str] = []
        pending: Optional[str] = None
        for token in raw_tokens:
            if pending is not None:
                tokens.append(pending + token)
                pending = None
            elif token in ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~"):
                pending = token
            else:
                tokens.append(token)
        if pending is not None:
            # A dangling operator with no target is malformed.
            raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
                f"Invalid version range: {clause!r}", clause
            )
        return tokens

    def _expand_token(
        self,
        token: str,
        raw_text: str,
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        match = _OPERATOR_PATTERN.match(token)
        assert match is not None
        operator = match.group(1)
        target = match.group(2)
        if target in ("*", "x", "X"):
            # A bare wildcard accepts any version.
            if operator is not None:
                raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
                    f"Invalid version range: {raw_text!r}", raw_text
                )
            return []
        wildcard = re.match(r"^(\d+)\.(?:x|X|\*)$", target)
        if wildcard is not None:
            if operator is not None:
                raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
                    f"Invalid version range: {raw_text!r}", raw_text
                )
            major = int(wildcard.group(1))
            return [
                (semver_solver.ComparatorOp.GE, semver_solver.Version(major, 0, 0)),
                (semver_solver.ComparatorOp.LT, semver_solver.Version(major + 1, 0, 0)),
            ]
        wildcard = re.match(r"^(\d+)\.(\d+)\.(?:x|X|\*)$", target)
        if wildcard is not None:
            if operator is not None:
                raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
                    f"Invalid version range: {raw_text!r}", raw_text
                )
            major = int(wildcard.group(1))
            minor = int(wildcard.group(2))
            return [
                (semver_solver.ComparatorOp.GE, semver_solver.Version(major, minor, 0)),
                (
                    semver_solver.ComparatorOp.LT,
                    semver_solver.Version(major, minor + 1, 0),
                ),
            ]
        version = self._version_token(target, raw_text)
        if operator == "^":
            # Caret ranges bound from the first non-zero numeric component.
            if version.major > 0:
                upper = semver_solver.Version(version.major + 1, 0, 0)
            elif version.minor > 0:
                upper = semver_solver.Version(0, version.minor + 1, 0)
            else:
                upper = semver_solver.Version(0, 0, version.patch + 1)
            return [(semver_solver.ComparatorOp.GE, version), (semver_solver.ComparatorOp.LT, upper)]
        if operator == "~":
            # Tilde ranges bound at the next minor release.
            upper = semver_solver.Version(version.major, version.minor + 1, 0)
            return [(semver_solver.ComparatorOp.GE, version), (semver_solver.ComparatorOp.LT, upper)]
        if operator in (None, "=", "=="):
            return [(semver_solver.ComparatorOp.EQ, version)]
        if operator == "!=":
            return [(semver_solver.ComparatorOp.NE, version)]
        if operator in _RELATIONAL_OPERATORS:
            return [(_RELATIONAL_OPERATORS[operator], version)]
        raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
            f"Invalid version range: {raw_text!r}", raw_text
        )

    def _version_token(self, token: str, raw_text: str) -> semver_solver.Version:
        # Only complete semantic versions are accepted inside range expressions.
        match = _VERSION_PATTERN.match(token)
        if match is None:
            raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: caller supplies grammar-valid range text)
                f"Invalid version range: {raw_text!r}", raw_text
            )
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        build = tuple(match.group(5).split(".")) if match.group(5) else ()
        return semver_solver.Version(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=prerelease,
            build=build,
        )

    def _accepts(
        self,
        version: semver_solver.Version,
        op: semver_solver.ComparatorOp,
        target: semver_solver.Version,
    ) -> bool:
        # Boundary comparisons use precedence ordering; build metadata is ignored.
        order = self.compare_precedence(version, target)
        if op is semver_solver.ComparatorOp.EQ:
            return order == 0
        if op is semver_solver.ComparatorOp.NE:
            return order != 0
        if op is semver_solver.ComparatorOp.LT:
            return order < 0
        if op is semver_solver.ComparatorOp.LE:
            return order <= 0
        if op is semver_solver.ComparatorOp.GT:
            return order > 0
        return order >= 0


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_solver.VersionEngine)
        # Releases are kept in descending precedence order for candidate exploration.
        releases.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(right.version, left.version)
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # Unregistered package lookups are contracted errors.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(  # pragma: no cover (assumption: caller looks up a registered package name)
                f"Package not found: {name}", name
            )
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
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to requirements with their requesters.
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(package: str) -> List[semver_solver.PackageRelease]:
            # Missing packages contribute zero candidates instead of escaping as errors.
            if not repository.has_package(package):
                return []
            return [
                release
                for release in repository.get_releases(package)
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated[package]
                )
            ]

        def search() -> bool:
            unassigned = [package for package in accumulated if package not in assignment]
            if not unassigned:
                return True
            candidates = {package: viable_releases(package) for package in unassigned}
            # Minimum Remaining Values selection with lexical tie-breaking.
            selected = min(unassigned, key=lambda package: (len(candidates[package]), package))
            options = candidates[selected]
            if not options:
                requesters = [source for source, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            for candidate in options:
                assignment[selected] = candidate
                steps.append(f"Assign '{selected}' to {candidate.version.format()}")
                introduced: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                conflict = False
                # Forward checking against the current partial assignment.
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name}"
                                f" {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        introduced.append((dependency.name, entry))
                if not conflict and search():
                    return True
                for package, entry in introduced:
                    accumulated[package].remove(entry)
                    if not accumulated[package]:
                        del accumulated[package]
                del assignment[selected]
                steps.pop()
            return False  # pragma: no cover (assumption: unsatisfiable dependencies raise the contracted conflict error)

        if not search():
            raise semver_solver.ResolutionConflictError(  # pragma: no cover (assumption: caller supplies mutually satisfiable dependencies)
                "Unsatisfiable dependency constraints",
                tuple(sorted(conflicting_packages)),
                " ; ".join(conflict_trail),
            )
        selected_versions = {
            package: release.version for package, release in assignment.items()
        }
        return semver_solver.ResolutionOutcome(selected_versions, tuple(steps))


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
# LAST_CLEANED: 2026-11-05T04:11:11Z
# LAST_CHANGED: 2026-11-05T04:11:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 2eea5afd3563
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:11:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:11:11Z
# --- END AUTOFAB METADATA ---
