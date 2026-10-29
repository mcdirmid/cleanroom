# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261028_212814_deepseek-flash_semver_solver_pretense_baseline
# Timestamp: 2026-10-28T21:28:14.320933+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 58,832
#   Cached Inbound Tokens:   2,381,696
#   Outbound Tokens:         74,246
#   Total Tokens:            2,514,774
#   Financial Cost ($USD):   $0.0605
#   Wall Clock Duration:     442.22s
#   Step Latencies (s):      [435.3]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""SemVer 2.0 parsing and dependency resolution interface contracts.

Translates ``low/semver_solver.pyi`` into concrete passive data types, error
records, and the abstract service protocols realized by ``semver_solver_impl``.
"""

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
            text += "-" + ".".join(self.prerelease)
        if self.build:
            text += "+" + ".".join(self.build)
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
        include_prerelease: bool = False,
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
    """Computes compatible version assignments satisfying transitive package dependencies."""

    @operation
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T21:35:36Z
# LAST_CHANGED: 2026-10-28T21:35:36Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 3bb93d9ea931
# COVERAGE_AUDIT: 2026-10-28T21:35:36Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T21:35:36Z
# PRETENSE_QA_AUDIT: 2026-10-28T21:35:36Z
# QA_AUDIT: 2026-10-28T21:35:36Z
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete SemVer 2.0 parsing and dependency resolution services.

Realizes ``low/semver_solver_impl.pyi``: a grammar-driven version engine, an
indexed package release repository, and a backtracking dependency solver using
Minimum Remaining Values variable selection and a conflict trail.
"""

from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from benchmark_7.parts.semver_solver.lib import semver_solver


_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_WILDCARD_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(?:(0|[1-9]\d*)\.)?[xX*]$")

_OPERATOR_PREFIXES = (">=", "<=", "==", "!=", ">", "<", "=", "^", "~")

_BASIC_OPERATORS: Dict[str, semver_solver.ComparatorOp] = {
    ">=": semver_solver.ComparatorOp.GE,
    "<=": semver_solver.ComparatorOp.LE,
    "==": semver_solver.ComparatorOp.EQ,
    "!=": semver_solver.ComparatorOp.NE,
    ">": semver_solver.ComparatorOp.GT,
    "<": semver_solver.ComparatorOp.LT,
    "=": semver_solver.ComparatorOp.EQ,
}


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # Validate the complete SemVer 2.0.0 grammar; numeric identifiers reject leading zeroes.
        match = _VERSION_PATTERN.match(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                f"Invalid semantic version string '{text}'", raw_text=text
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
        # Compare major, minor, and patch numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left < right:
                return -1
            if left > right:
                return 1
        # A normal version ranks higher than any prerelease sharing the same numbers.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # Compare prerelease identifiers position by position; build metadata is ignored.
        for left, right in zip(v1.prerelease, v2.prerelease):
            if left == right:
                continue
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                left_value = int(left)
                right_value = int(right)
                return -1 if left_value < right_value else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left < right else 1
        # A longer prerelease sequence ranks higher when the shared prefix matches.
        if len(v1.prerelease) < len(v2.prerelease):
            return -1
        if len(v1.prerelease) > len(v2.prerelease):
            return 1
        return 0

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Validate every union clause before normalizing the trimmed range expression.
        self._compile_clauses(text)
        normalized = " || ".join(
            clause.strip() for clause in text.strip().split("||")
        )
        return semver_solver.VersionRange(raw_text=normalized)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        # Compile the range expression into disjunctive normal form comparator sets.
        clauses = self._compile_clauses(range_constraint.raw_text)
        # Filter prerelease candidates unless explicitly targeted by the range.
        if (
            version.is_prerelease
            and not include_prerelease
            and not self._targets_prerelease(clauses, version)
        ):
            return False
        # A version satisfies the range when one clause has all comparators satisfied.
        for clause in clauses:
            if all(self._matches(version, operator, bound) for operator, bound in clause):
                return True
        return False

    def _compile_clauses(
        self, text: str
    ) -> List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
        """Validates a range expression and expands it into comparator clauses."""
        if not text.strip():
            raise semver_solver.InvalidRangeError(
                "Version range expression must not be empty", raw_range=text
            )
        if "," in text:
            raise semver_solver.InvalidRangeError(
                "Version range comparators must be separated by whitespace, not commas",
                raw_range=text,
            )
        compiled: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]] = []
        for clause in text.split("||"):
            stripped = clause.strip()
            if not stripped:
                raise semver_solver.InvalidRangeError(
                    "Version range contains an empty union clause", raw_range=text
                )
            compiled.append(self._compile_clause(stripped, text))
        return compiled

    def _compile_clause(
        self, clause: str, original: str
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        """Expands a whitespace-delimited clause into concrete comparators."""
        tokens = clause.split()
        # Hyphen ranges use two full versions separated by a standalone hyphen.
        if len(tokens) == 3 and tokens[1] == "-":
            return [
                (
                    semver_solver.ComparatorOp.GE,
                    self._parse_range_version(tokens[0], original),
                ),
                (
                    semver_solver.ComparatorOp.LE,
                    self._parse_range_version(tokens[2], original),
                ),
            ]
        compiled: List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in _OPERATOR_PREFIXES:
                if index + 1 >= len(tokens):
                    raise semver_solver.InvalidRangeError(
                        "Operator is missing a target version", raw_range=original
                    )
                symbol = token
                target = tokens[index + 1]
                index += 2
            else:
                symbol = ""
                target = token
                for prefix in _OPERATOR_PREFIXES:
                    if token.startswith(prefix):
                        symbol = prefix
                        target = token[len(prefix):]
                        break
                index += 1
            compiled.extend(self._expand_comparator(symbol, target, original))
        return compiled

    def _expand_comparator(
        self, symbol: str, target: str, original: str
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        """Expands a caret, tilde, wildcard, or relational comparator."""
        if target in ("*", "x", "X"):
            if symbol not in ("", "=", "=="):
                raise semver_solver.InvalidRangeError(
                    "Wildcard cannot be combined with a relational operator",
                    raw_range=original,
                )
            return []
        wildcard = _WILDCARD_PATTERN.match(target)
        if wildcard is not None:
            if symbol not in ("", "=", "=="):
                raise semver_solver.InvalidRangeError(
                    "Wildcard cannot be combined with a relational operator",
                    raw_range=original,
                )
            major = int(wildcard.group(1))
            minor_text = wildcard.group(2)
            if minor_text is None:
                lower = semver_solver.Version(major=major, minor=0, patch=0)
                upper = semver_solver.Version(major=major + 1, minor=0, patch=0)
            else:
                minor = int(minor_text)
                lower = semver_solver.Version(major=major, minor=minor, patch=0)
                upper = semver_solver.Version(major=major, minor=minor + 1, patch=0)
            return [
                (semver_solver.ComparatorOp.GE, lower),
                (semver_solver.ComparatorOp.LT, upper),
            ]
        version = self._parse_range_version(target, original)
        if symbol == "^":
            return self._expand_caret(version)
        if symbol == "~":
            return self._expand_tilde(version)
        operator = _BASIC_OPERATORS[symbol] if symbol else semver_solver.ComparatorOp.EQ
        return [(operator, version)]

    def _parse_range_version(self, text: str, original: str) -> semver_solver.Version:
        """Parses a full version inside a range, reporting range-level errors."""
        try:
            return self.parse_version(text)
        except semver_solver.InvalidVersionError as error:
            raise semver_solver.InvalidRangeError(
                "Version range expression contains a malformed version",
                raw_range=original,
            ) from error

    def _expand_caret(
        self, version: semver_solver.Version
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        """Expands a caret range from the first non-zero component."""
        if version.major != 0:
            upper = semver_solver.Version(major=version.major + 1, minor=0, patch=0)
        elif version.minor != 0:
            upper = semver_solver.Version(major=0, minor=version.minor + 1, patch=0)
        elif version.patch != 0:
            upper = semver_solver.Version(major=0, minor=0, patch=version.patch + 1)
        else:
            upper = semver_solver.Version(major=0, minor=0, patch=1)
        return [
            (semver_solver.ComparatorOp.GE, version),
            (semver_solver.ComparatorOp.LT, upper),
        ]

    def _expand_tilde(
        self, version: semver_solver.Version
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        """Expands a tilde range into lower and minor-bound upper bounds."""
        upper = semver_solver.Version(
            major=version.major, minor=version.minor + 1, patch=0
        )
        return [
            (semver_solver.ComparatorOp.GE, version),
            (semver_solver.ComparatorOp.LT, upper),
        ]

    def _targets_prerelease(
        self,
        clauses: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]],
        version: semver_solver.Version,
    ) -> bool:
        """Checks whether any comparator explicitly targets this prerelease tuple."""
        for clause in clauses:
            for _, bound in clause:
                if (
                    bound.is_prerelease
                    and bound.major == version.major
                    and bound.minor == version.minor
                    and bound.patch == version.patch
                ):
                    return True
        return False

    def _matches(
        self,
        version: semver_solver.Version,
        operator: semver_solver.ComparatorOp,
        bound: semver_solver.Version,
    ) -> bool:
        """Evaluates one comparator against the candidate version."""
        ordering = self.compare_precedence(version, bound)
        if operator is semver_solver.ComparatorOp.EQ:
            return ordering == 0
        if operator is semver_solver.ComparatorOp.NE:
            return ordering != 0
        if operator is semver_solver.ComparatorOp.LT:
            return ordering < 0
        if operator is semver_solver.ComparatorOp.LE:
            return ordering <= 0
        if operator is semver_solver.ComparatorOp.GT:
            return ordering > 0
        return ordering >= 0


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # Insert the release, then keep the package history in descending precedence order.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_solver.VersionEngine)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: -engine.compare_precedence(left.version, right.version)
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # Missing packages are a contracted repository failure.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository", package_name=name
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
    """Concrete realization of the backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)
        # Seed accumulated constraints with the root requirements.
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            # A complete assignment satisfies every accumulated constraint.
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True
            # Minimum Remaining Values selection with lexical tie-breaking.
            candidate_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for name in unassigned:
                if repository.has_package(name):
                    available = repository.get_releases(name)
                else:
                    # Unregistered packages have zero candidates rather than escaping PackageNotFoundError.
                    available = []
                    conflicting_packages.add(name)
                candidate_map[name] = [
                    release
                    for release in available
                    if all(
                        engine.satisfies(release.version, constraint)
                        for _, constraint in accumulated[name]
                    )
                ]
            selected = min(
                unassigned, key=lambda package: (len(candidate_map[package]), package)
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
            # Explore viable releases in descending precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # Forward checking rejects releases violating an existing assignment.
                        if not engine.satisfies(
                            assignment[dependency.name].version, dependency.range_constraint
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{dependency.name}' "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
                # Restore the accumulated constraints introduced by this candidate.
                for name, entry in newly_added:
                    accumulated[name].remove(entry)
                    if not accumulated[name]:
                        del accumulated[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if backtrack():
            selected_versions = {
                name: release.version for name, release in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )
        raise semver_solver.ResolutionConflictError(
            message="Dependency resolution failed",
            conflicting_packages=tuple(sorted(conflicting_packages)),
            explanation="; ".join(conflict_trail),
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_solver.VersionEngine],
        tier=VersionEngine.tier,
    )
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, semver_solver.PackageRepository],
        tier=PackageRepository.tier,
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, semver_solver.DependencySolver],
        tier=DependencySolver.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T21:35:36Z
# LAST_CHANGED: 2026-10-28T21:35:36Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 4fa6d24519b3
# COVERAGE_AUDIT: 2026-10-28T21:35:36Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T21:35:36Z
# PRETENSE_QA_AUDIT: 2026-10-28T21:35:36Z
# QA_AUDIT: 2026-10-28T21:35:36Z
# --- END CLEANROOM METADATA ---
