# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_223821_gemini-argon_semver_solver_pretense
# Timestamp: 2026-11-13T22:38:21.568338+00:00
# Benchmark Task: semver_solver
# Model: gemini-argon (Tier 4)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 491,828
#   Cached Inbound Tokens:   2,712,428
#   Outbound Tokens:         118,549
#   Total Tokens:            3,322,805
#   Financial Cost ($USD):   $3.5254
#   Wall Clock Duration:     1171.33s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 2, pretense: 2, pretense_coverage: 2, pretense_qa: 2 (Total: 8)
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
"""Interface definitions for SemVer 2.0 parsing and dependency resolution."""

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

    message: str


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
        return bool(self.prerelease)

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            result += "-" + ".".join(self.prerelease)
        if self.build:
            result += "+" + ".".join(self.build)
        return result

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
# LAST_CLEANED: 2026-11-13T22:49:31Z
# LAST_CHANGED: 2026-11-13T22:49:31Z
# CHANGE: Implement SemVer 2.0 interface protocols, domain data types, and exceptions matching low/semver_solver.pyi
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete implementation of SemVer 2.0 parsing and dependency resolution."""

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
from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton
from . import semver_solver


_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
_WILDCARD_ALL_RE = re.compile(r"^(?:\*|x|X)(?:\.(?:\*|x|X)){0,2}$")
_WILDCARD_MAJOR_RE = re.compile(r"^(0|[1-9]\d*)\.(?:\*|x|X)(?:\.(?:\*|x|X))?$")
_WILDCARD_MINOR_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(?:\*|x|X)$")
_STANDALONE_OPS = frozenset({"==", "=", "!=", "<=", ">=", "<", ">", "^", "~"})
_OP_PREFIXES = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")
_UNSAT_CLAUSE: List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]] = [
    (semver_solver.ComparatorOp.LT, semver_solver.Version(0, 0, 0)),
    (semver_solver.ComparatorOp.GT, semver_solver.Version(0, 0, 0)),
]


@dataclass(frozen=True)
class _Bound:
    """Normalized representation of a full version or wildcard range bound."""

    exact: Optional[semver_solver.Version]
    low: Optional[semver_solver.Version]
    high: Optional[semver_solver.Version]
    caret_high: Optional[semver_solver.Version]
    tilde_high: Optional[semver_solver.Version]


@singleton
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = "system"

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Validate input against the full SemVer 2.0.0 grammar and leading zero rules.
        match = _SEMVER_RE.fullmatch(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version: '{text}'",
                raw_text=text,
            )
        major_s, minor_s, patch_s, prerelease_s, build_s = match.groups()
        prerelease = tuple(prerelease_s.split(".")) if prerelease_s else ()
        build = tuple(build_s.split(".")) if build_s else ()
        return semver_solver.Version(
            major=int(major_s),
            minor=int(minor_s),
            patch=int(patch_s),
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
        # Compare major, minor, and patch components numerically.
        num1 = (v1.major, v1.minor, v1.patch)
        num2 = (v2.major, v2.minor, v2.patch)
        if num1 != num2:
            return -1 if num1 < num2 else 1

        # Normal versions have higher precedence than pre-release versions.
        if bool(v1.prerelease) != bool(v2.prerelease):
            return 1 if not v1.prerelease else -1

        # Compare pre-release identifiers position by position.
        for seg1, seg2 in zip(v1.prerelease, v2.prerelease):
            if seg1 == seg2:
                continue
            is_num1 = seg1.isdigit()
            is_num2 = seg2.isdigit()
            if is_num1 and is_num2:
                return -1 if int(seg1) < int(seg2) else 1
            if is_num1 != is_num2:
                return -1 if is_num1 else 1
            return -1 if seg1 < seg2 else 1

        # A larger set of pre-release fields has higher precedence when prefixes match.
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        return 0

    def _parse_bound(self, token: str, raw_range: str) -> _Bound:
        """Parses a single version or wildcard bound token."""
        if _WILDCARD_ALL_RE.fullmatch(token):
            return _Bound(None, None, None, None, None)
        major_match = _WILDCARD_MAJOR_RE.fullmatch(token)
        if major_match is not None:
            major = int(major_match.group(1))
            low = semver_solver.Version(major, 0, 0)
            high = semver_solver.Version(major + 1, 0, 0)
            return _Bound(None, low, high, high, high)
        minor_match = _WILDCARD_MINOR_RE.fullmatch(token)
        if minor_match is not None:
            major = int(minor_match.group(1))
            minor = int(minor_match.group(2))
            low = semver_solver.Version(major, minor, 0)
            high = semver_solver.Version(major, minor + 1, 0)
            caret_high = semver_solver.Version(major + 1, 0, 0) if major > 0 else high
            return _Bound(None, low, high, caret_high, high)
        if _SEMVER_RE.fullmatch(token):
            ver = self.parse_version(token)
            caret_high = (
                semver_solver.Version(ver.major + 1, 0, 0)
                if ver.major > 0
                else (
                    semver_solver.Version(0, ver.minor + 1, 0)
                    if ver.minor > 0
                    else semver_solver.Version(0, 0, ver.patch + 1)
                )
            )
            tilde_high = semver_solver.Version(ver.major, ver.minor + 1, 0)
            return _Bound(ver, ver, None, caret_high, tilde_high)
        raise semver_solver.InvalidRangeError(
            message=f"Malformed version bound '{token}' in range '{raw_range}'",
            raw_range=raw_range,
        )

    def _expand_comparator(
        self,
        op: str,
        bound: _Bound,
    ) -> List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
        """Expands an operator and bound into disjunctive normal form comparator lists."""
        if op == "^":
            return (
                [[(semver_solver.ComparatorOp.GE, bound.low), (semver_solver.ComparatorOp.LT, bound.caret_high)]]
                if bound.low is not None and bound.caret_high is not None
                else [[]]
            )
        if op == "~":
            return (
                [[(semver_solver.ComparatorOp.GE, bound.low), (semver_solver.ComparatorOp.LT, bound.tilde_high)]]
                if bound.low is not None and bound.tilde_high is not None
                else [[]]
            )
        if op == ">=":
            return [[(semver_solver.ComparatorOp.GE, bound.low)]] if bound.low is not None else [[]]
        if op == "<":
            return [[(semver_solver.ComparatorOp.LT, bound.low)]] if bound.low is not None else [_UNSAT_CLAUSE]
        if op == "<=":
            return (
                [[(semver_solver.ComparatorOp.LE, bound.exact)]]
                if bound.exact is not None
                else ([[(semver_solver.ComparatorOp.LT, bound.high)]] if bound.high is not None else [[]])
            )
        if op == ">":
            return (
                [[(semver_solver.ComparatorOp.GT, bound.exact)]]
                if bound.exact is not None
                else ([[(semver_solver.ComparatorOp.GE, bound.high)]] if bound.high is not None else [_UNSAT_CLAUSE])
            )
        if op == "!=":
            return (
                [[(semver_solver.ComparatorOp.NE, bound.exact)]]
                if bound.exact is not None
                else (
                    [[(semver_solver.ComparatorOp.LT, bound.low)], [(semver_solver.ComparatorOp.GE, bound.high)]]
                    if bound.low is not None and bound.high is not None
                    else [_UNSAT_CLAUSE]
                )
            )
        # Default equality ('==' or '=') for exact versions or wildcard ranges.
        return (
            [[(semver_solver.ComparatorOp.EQ, bound.exact)]]
            if bound.exact is not None
            else (
                [[(semver_solver.ComparatorOp.GE, bound.low), (semver_solver.ComparatorOp.LT, bound.high)]]
                if bound.low is not None and bound.high is not None
                else [[]]
            )
        )

    def _compile_range(
        self,
        raw_text: str,
    ) -> Tuple[str, List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]]:
        """Validates and compiles a range expression into DNF comparator clauses."""
        raw_clauses = [c.strip() for c in raw_text.strip().split("||")]
        if "," in raw_text or any(not c for c in raw_clauses):
            raise semver_solver.InvalidRangeError(
                message=f"Invalid range syntax: '{raw_text}'",
                raw_range=raw_text,
            )

        dnf_clauses: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]] = []
        for clause_str in raw_clauses:
            tokens = clause_str.split()
            clause_branches: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]] = [[]]
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if i + 2 < len(tokens) and tokens[i + 1] == "-":
                    b1 = self._parse_bound(tok, raw_text)
                    b2 = self._parse_bound(tokens[i + 2], raw_text)
                    low_part = [(semver_solver.ComparatorOp.GE, b1.low)] if b1.low is not None else []
                    high_part = (
                        [(semver_solver.ComparatorOp.LE, b2.exact)]
                        if b2.exact is not None
                        else ([(semver_solver.ComparatorOp.LT, b2.high)] if b2.high is not None else [])
                    )
                    alternatives = [low_part + high_part]
                    i += 3
                elif tok in _STANDALONE_OPS:
                    next_tok = (
                        tokens[i + 1]
                        if i + 1 < len(tokens) and not (i + 2 < len(tokens) and tokens[i + 2] == "-")
                        else ""
                    )
                    bound = self._parse_bound(next_tok, raw_text)
                    alternatives = self._expand_comparator(tok, bound)
                    i += 2
                else:
                    matched_op = next((p for p in _OP_PREFIXES if tok.startswith(p)), None)
                    if matched_op is not None:
                        bound = self._parse_bound(tok[len(matched_op) :], raw_text)
                        alternatives = self._expand_comparator(matched_op, bound)
                    else:
                        bound = self._parse_bound(tok, raw_text)
                        alternatives = self._expand_comparator("==", bound)
                    i += 1

                clause_branches = [
                    existing + alt for existing in clause_branches for alt in alternatives
                ]

            dnf_clauses.extend(clause_branches)

        normalized_text = " || ".join(raw_clauses)
        return normalized_text, dnf_clauses

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        normalized_text, _ = self._compile_range(text)
        return semver_solver.VersionRange(raw_text=normalized_text)

    def _eval_comparator(
        self,
        version: semver_solver.Version,
        op: semver_solver.ComparatorOp,
        target: semver_solver.Version,
    ) -> bool:
        """Evaluates a single relational comparator against a candidate version."""
        cmp = self.compare_precedence(version, target)
        return (
            (cmp == 0 if op is semver_solver.ComparatorOp.EQ else cmp != 0)
            if op in (semver_solver.ComparatorOp.EQ, semver_solver.ComparatorOp.NE)
            else (
                (cmp < 0 if op is semver_solver.ComparatorOp.LT else cmp <= 0)
                if op in (semver_solver.ComparatorOp.LT, semver_solver.ComparatorOp.LE)
                else (cmp > 0 if op is semver_solver.ComparatorOp.GT else cmp >= 0)
            )
        )

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        _, dnf_clauses = self._compile_range(range_constraint.raw_text)
        for clause in dnf_clauses:
            # Filter out pre-release versions unless include_prerelease is True or the clause targets the same major.minor.patch pre-release.
            if version.is_prerelease and not include_prerelease:
                if not any(
                    target.is_prerelease
                    and (target.major, target.minor, target.patch)
                    == (version.major, version.minor, version.patch)
                    for _, target in clause
                ):
                    continue
            if all(self._eval_comparator(version, op, target) for op, target in clause):
                return True
        return False


@singleton
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = "system"

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
                message=f"Package '{name}' is not registered in the repository",
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


@singleton
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = "system"

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
            accumulated_constraints.setdefault(dep.name, []).append(("root", dep.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            pending = [
                p
                for p in accumulated_constraints
                if p not in assignment
                or not all(
                    engine.satisfies(assignment[p].version, rng, False)
                    for _, rng in accumulated_constraints[p]
                )
            ]
            if not pending:
                return True

            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for pkg in pending:
                try:
                    available = repo.get_releases(pkg)
                except semver_solver.PackageNotFoundError:
                    available = []
                candidates_map[pkg] = (
                    []
                    if pkg in assignment
                    else [
                        rel
                        for rel in available
                        if all(
                            engine.satisfies(rel.version, rng, False)
                            for _, rng in accumulated_constraints[pkg]
                        )
                    ]
                )

            selected_pkg = min(pending, key=lambda p: (len(candidates_map[p]), p))
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
                conflicting_packages.add(selected_pkg)
                conflicting_packages.update(src for src in requesters if src != "root")
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
                )
                return False

            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dep in candidate.dependencies:
                    constraint_entry = (selected_pkg, dep.range_constraint)
                    accumulated_constraints.setdefault(dep.name, []).append(constraint_entry)
                    newly_added.append((dep.name, constraint_entry))

                if backtrack():
                    return True

                for pkg_name, constraint_entry in newly_added:
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        if backtrack():
            selected_versions = {pkg: rel.version for pkg, rel in assignment.items()}
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        conflicting = tuple(sorted(conflicting_packages))
        explanation = "\n".join(conflict_trail)
        raise semver_solver.ResolutionConflictError(
            message=f"Unsatisfiable dependency conflict involving {conflicting}: {explanation}",
            conflicting_packages=conflicting,
            explanation=explanation,
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:57:49Z
# LAST_CHANGED: 2026-11-13T22:49:43Z
# CHANGE: Implement concrete VersionEngine, PackageRepository, and DependencySolver singletons matching low/semver_solver_impl.pyi
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:57:49Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:57:20Z
# --- END AUTOFAB METADATA ---
