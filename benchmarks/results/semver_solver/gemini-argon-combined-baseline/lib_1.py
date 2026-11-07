# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261106_201957_gemini-argon_semver_solver_combined_baseline
# Timestamp: 2026-11-06T20:19:57.338566+00:00
# Benchmark Task: semver_solver
# Model: gemini-argon (Tier 4)
# Methodology: combined_baseline
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 279,964
#   Cached Inbound Tokens:   5,215,337
#   Outbound Tokens:         117,631
#   Total Tokens:            5,612,932
#   Financial Cost ($USD):   $4.3439
#   Wall Clock Duration:     1416.79s
#   Step Latencies (s):      []
#   Role Execution Rounds:   combined_baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       14
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Low-level interface specification for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)
from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str = ""

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered."""

    raw_text: str = ""


@dataclass
class InvalidRangeError(SemVerError):
    """Raised when a version range expression contains malformed syntax."""

    raw_range: str = ""


@dataclass
class ResolutionConflictError(SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually."""

    conflicting_packages: Tuple[str, ...] = ()
    explanation: str = ""


@dataclass
class PackageNotFoundError(SemVerError):
    """Raised when a referenced package name does not exist in the repository."""

    package_name: str = ""


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
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base += f"-{'.'.join(self.prerelease)}"
        if self.build:
            base += f"+{'.'.join(self.build)}"
        return base

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
# LAST_CLEANED: 2026-11-06T20:43:33Z
# LAST_CHANGED: 2026-11-06T20:43:33Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 1f705978f49b
# COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:43:33Z
# QA_AUDIT: 2026-11-06T20:43:33Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Low-level implementation for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import functools
import re
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_solver

_SEMVER_RE = re.compile(
    r"\A(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
)

_NUM_RE = re.compile(r"\A(?:0|[1-9][0-9]*)\Z")
_WILDCARD_TOKENS = frozenset({"*", "x", "X"})
_OPERATORS = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")


@dataclass(frozen=True)
class _Comparator:
    op: semver_solver.ComparatorOp
    target: semver_solver.Version


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Validate SemVer 2.0.0 grammar and numerical leading zero constraints
        match = _SEMVER_RE.match(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version: {text!r}",
                raw_text=text,
            )
        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))
        pre_str = match.group("prerelease")
        build_str = match.group("build")
        prerelease = tuple(pre_str.split(".")) if pre_str else ()
        build = tuple(build_str.split(".")) if build_str else ()
        return semver_solver.Version(
            major=major,
            minor=minor,
            patch=patch,
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
        """Determines ordering precedence between two semantic versions."""
        # Compare major, minor, and patch numbers numerically in sequence
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1

        # Evaluate pre-release presence when numeric components are identical
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # Iterate through pre-release segments comparing each position
        for seg1, seg2 in zip(v1.prerelease, v2.prerelease):
            if seg1 == seg2:
                continue
            is_num1 = seg1.isdigit()
            is_num2 = seg2.isdigit()
            if is_num1 and is_num2:
                n1, n2 = int(seg1), int(seg2)
                return -1 if n1 < n2 else 1
            if is_num1 != is_num2:
                # Numeric segments rank lower than string segments
                return -1 if is_num1 else 1
            return -1 if seg1 < seg2 else 1

        # Longer pre-release segment sequences rank higher when common prefix matches
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        return 0

    def _compile_wildcard(
        self,
        op_str: str,
        operand_str: str,
        raw_range: str,
    ) -> List[_Comparator]:
        """Expands wildcard expression into comparator inequalities."""
        parts = operand_str.split(".")
        if op_str in ("", "=", "==") and len(parts) == 1 and parts[0] in _WILDCARD_TOKENS:
            return [
                _Comparator(semver_solver.ComparatorOp.GE, semver_solver.Version(0, 0, 0))
            ]
        if (
            op_str in ("", "=", "==")
            and len(parts) == 2
            and _NUM_RE.match(parts[0])
            and parts[1] in _WILDCARD_TOKENS
        ):
            major = int(parts[0])
            return [
                _Comparator(
                    semver_solver.ComparatorOp.GE, semver_solver.Version(major, 0, 0)
                ),
                _Comparator(
                    semver_solver.ComparatorOp.LT,
                    semver_solver.Version(major + 1, 0, 0),
                ),
            ]
        if (
            op_str in ("", "=", "==")
            and len(parts) == 3
            and _NUM_RE.match(parts[0])
            and _NUM_RE.match(parts[1])
            and parts[2] in _WILDCARD_TOKENS
        ):
            major = int(parts[0])
            minor = int(parts[1])
            return [
                _Comparator(
                    semver_solver.ComparatorOp.GE,
                    semver_solver.Version(major, minor, 0),
                ),
                _Comparator(
                    semver_solver.ComparatorOp.LT,
                    semver_solver.Version(major, minor + 1, 0),
                ),
            ]
        raise semver_solver.InvalidRangeError(
            message=f"Invalid wildcard range: {raw_range!r}",
            raw_range=raw_range,
        )

    def _compile_token(
        self,
        op_str: str,
        operand_str: str,
        raw_range: str,
    ) -> List[_Comparator]:
        """Compiles a single operator and operand pair into comparators."""
        if any(part in _WILDCARD_TOKENS for part in operand_str.split(".")):
            return self._compile_wildcard(op_str, operand_str, raw_range)

        try:
            target = self.parse_version(operand_str)
        except semver_solver.InvalidVersionError as exc:
            raise semver_solver.InvalidRangeError(
                message=f"Invalid version in range {raw_range!r}: {exc.message}",
                raw_range=raw_range,
            ) from exc

        if op_str in ("", "=", "=="):
            return [_Comparator(semver_solver.ComparatorOp.EQ, target)]
        if op_str == "!=":
            return [_Comparator(semver_solver.ComparatorOp.NE, target)]
        if op_str == "<":
            return [_Comparator(semver_solver.ComparatorOp.LT, target)]
        if op_str == "<=":
            return [_Comparator(semver_solver.ComparatorOp.LE, target)]
        if op_str == ">":
            return [_Comparator(semver_solver.ComparatorOp.GT, target)]
        if op_str == ">=":
            return [_Comparator(semver_solver.ComparatorOp.GE, target)]
        if op_str == "^":
            # Expand caret prefix based on first non-zero component boundary
            if target.major > 0:
                upper = semver_solver.Version(target.major + 1, 0, 0)
            elif target.minor > 0:
                upper = semver_solver.Version(0, target.minor + 1, 0)
            else:
                upper = semver_solver.Version(0, 0, target.patch + 1)
            return [
                _Comparator(semver_solver.ComparatorOp.GE, target),
                _Comparator(semver_solver.ComparatorOp.LT, upper),
            ]
        # op_str == "~": expand tilde prefix into lower and upper minor boundaries
        upper = semver_solver.Version(target.major, target.minor + 1, 0)
        return [
            _Comparator(semver_solver.ComparatorOp.GE, target),
            _Comparator(semver_solver.ComparatorOp.LT, upper),
        ]

    def _compile_range(self, text: str) -> List[List[_Comparator]]:
        """Compiles range text into disjunctive normal form comparator clauses."""
        if "," in text:
            raise semver_solver.InvalidRangeError(
                message="Comma delimiters are not permitted in range expressions",
                raw_range=text,
            )
        trimmed = text.strip()
        if not trimmed:
            raise semver_solver.InvalidRangeError(
                message="Range expression cannot be empty",
                raw_range=text,
            )

        clauses: List[List[_Comparator]] = []
        for raw_clause in trimmed.split("||"):
            clause_str = raw_clause.strip()
            if not clause_str:
                raise semver_solver.InvalidRangeError(
                    message=f"Empty union clause in range expression: {text!r}",
                    raw_range=text,
                )
            tokens = clause_str.split()
            comparators: List[_Comparator] = []
            i = 0
            while i < len(tokens):
                if i + 2 < len(tokens) and tokens[i + 1] == "-":
                    try:
                        v_low = self.parse_version(tokens[i])
                        v_high = self.parse_version(tokens[i + 2])
                    except semver_solver.InvalidVersionError as exc:
                        raise semver_solver.InvalidRangeError(
                            message=f"Invalid hyphen range in {text!r}",
                            raw_range=text,
                        ) from exc
                    comparators.append(_Comparator(semver_solver.ComparatorOp.GE, v_low))
                    comparators.append(_Comparator(semver_solver.ComparatorOp.LE, v_high))
                    i += 3
                elif tokens[i] in _OPERATORS:
                    if i + 1 >= len(tokens):
                        raise semver_solver.InvalidRangeError(
                            message=f"Dangling operator {tokens[i]!r} in {text!r}",
                            raw_range=text,
                        )
                    comparators.extend(self._compile_token(tokens[i], tokens[i + 1], text))
                    i += 2
                else:
                    tok = tokens[i]
                    op_str = ""
                    operand_str = tok
                    for op in _OPERATORS:
                        if tok.startswith(op):
                            op_str = op
                            operand_str = tok[len(op) :]
                            break
                    comparators.extend(self._compile_token(op_str, operand_str, text))
                    i += 1
            clauses.append(comparators)
        return clauses

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        self._compile_range(text)
        return semver_solver.VersionRange(raw_text=text.strip())

    def _matches_comparator(
        self,
        version: semver_solver.Version,
        comp: _Comparator,
    ) -> bool:
        """Evaluates a single relational comparator using precedence ordering."""
        cmp = self.compare_precedence(version, comp.target)
        if comp.op is semver_solver.ComparatorOp.EQ:
            return cmp == 0
        if comp.op is semver_solver.ComparatorOp.NE:
            return cmp != 0
        if comp.op is semver_solver.ComparatorOp.LT:
            return cmp < 0
        if comp.op is semver_solver.ComparatorOp.LE:
            return cmp <= 0
        if comp.op is semver_solver.ComparatorOp.GT:
            return cmp > 0
        return cmp >= 0

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        clauses = self._compile_range(range_constraint.raw_text)
        for clause in clauses:
            # Filter out pre-release versions when include_prerelease is False unless explicitly targeted
            if version.is_prerelease and not include_prerelease:
                explicitly_targeted = any(
                    comp.target.is_prerelease
                    and comp.target.major == version.major
                    and comp.target.minor == version.minor
                    and comp.target.patch == version.patch
                    for comp in clause
                )
                if not explicitly_targeted:
                    continue
            if all(self._matches_comparator(version, comp) for comp in clause):
                return True
        return False


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
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(
            key=functools.cmp_to_key(
                lambda r1, r2: engine.compare_precedence(r1.version, r2.version)
            ),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package {name!r} is not registered in the repository",
                package_name=name,
            )
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
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        repo = get_singleton(semver_solver.PackageRepository)

        accumulated_constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dep in root_dependencies:
            accumulated_constraints.setdefault(dep.name, []).append(
                ("root", dep.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            unassigned = [p for p in accumulated_constraints if p not in assignment]
            if not unassigned:
                return True

            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for pkg in unassigned:
                try:
                    available = repo.get_releases(pkg)
                except semver_solver.PackageNotFoundError:
                    available = []
                viable = [
                    rel
                    for rel in available
                    if all(
                        engine.satisfies(rel.version, rng, False)
                        for _, rng in accumulated_constraints[pkg]
                    )
                ]
                candidates_map[pkg] = viable

            selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
                conflicting_packages.add(selected_pkg)
                conflicting_packages.update(r for r in requesters if r != "root")
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
                )
                return False

            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(
                    f"Assign '{selected_pkg}' to {candidate.version}"
                )

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        if not engine.satisfies(
                            assignment[dep.name].version,
                            dep.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected_pkg)
                            conflicting_packages.add(dep.name)
                            conflict_trail.append(
                                f"Conflict: '{selected_pkg}' requires {dep.name} {dep.range_constraint.raw_text}"
                            )
                            break
                    else:
                        constraint_entry = (selected_pkg, dep.range_constraint)
                        accumulated_constraints.setdefault(dep.name, []).append(
                            constraint_entry
                        )
                        newly_added.append((dep.name, constraint_entry))

                if not conflict_detected and backtrack():
                    return True

                for pkg_name, constraint_entry in newly_added:
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        if backtrack():
            selected_versions = {
                pkg: rel.version for pkg, rel in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        explanation = "; ".join(conflict_trail)
        sorted_conflicts = tuple(sorted(conflicting_packages))
        raise semver_solver.ResolutionConflictError(
            message=f"Resolution conflict for {sorted_conflicts}: {explanation}",
            conflicting_packages=sorted_conflicts,
            explanation=explanation,
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
# LAST_CLEANED: 2026-11-06T20:43:33Z
# LAST_CHANGED: 2026-11-06T20:43:33Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 8f920a027d90
# COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:43:33Z
# QA_AUDIT: 2026-11-06T20:43:33Z
# --- END AUTOFAB METADATA ---
