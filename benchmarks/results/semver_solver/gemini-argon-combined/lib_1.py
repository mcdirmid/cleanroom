# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261106_201944_gemini-argon_semver_solver_combined
# Timestamp: 2026-11-06T20:19:44.903533+00:00
# Benchmark Task: semver_solver
# Model: gemini-argon (Tier 4)
# Methodology: combined
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 1,462,505
#   Cached Inbound Tokens:   12,627,543
#   Outbound Tokens:         301,962
#   Total Tokens:            14,392,010
#   Financial Cost ($USD):   $12.2584
#   Wall Clock Duration:     3064.83s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 5, lib: 5, pretense: 3, pretense_coverage: 2, pretense_qa: 5, qa: 4, test: 3 (Total: 27)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       16
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""SemVer 2.0 parsing and dependency resolution interface module."""

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
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error. Verification suites MUST NOT assert on specific wording or prefixes within message, and MUST assert on exception types and structured attributes.
    """

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered.

    Args:
        message: Diagnostic description of the error.
        raw_text: Original unparseable version string.
    """

    raw_text: str


@dataclass
class InvalidRangeError(SemVerError):
    """Raised when a version range expression contains malformed syntax.

    Args:
        message: Diagnostic description of the error.
        raw_range: Original malformed range expression string.
    """

    raw_range: str


@dataclass
class ResolutionConflictError(SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually.

    Args:
        message: Diagnostic description of the conflict.
        conflicting_packages: Sequence of package names involved in the conflict.
        explanation: Detailed diagnostic derivation of the unsatisfiable conflict.
    """

    conflicting_packages: Tuple[str, ...]
    explanation: str


@dataclass
class PackageNotFoundError(SemVerError):
    """Raised when a referenced package name does not exist in the repository.

    Args:
        message: Diagnostic description of the missing package.
        package_name: Name of the missing package.
    """

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
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base += "-" + ".".join(self.prerelease)
        if self.build:
            base += "+" + ".".join(self.build)
        return base

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
        return self.format()


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


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range.

    Args:
        name: Name of the required package.
        range_constraint: Acceptable version range constraint.
    """

    name: str
    range_constraint: VersionRange


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
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run.

    Args:
        selected_versions: Mapping of package names to their selected semantic versions.
        derivation_steps: Ordered sequence of decision and deduction steps.
    """

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
# LAST_CLEANED: 2026-11-06T20:24:57Z
# LAST_CHANGED: 2026-11-06T20:24:57Z
# CHANGE: Implement semver_solver interface protocols, data types, and error classes matching low/semver_solver.pyi
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete implementation for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
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
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
)
from . import semver_solver


_NUMERIC_RE = re.compile(r"\A(0|[1-9][0-9]*)\Z")
_SEMVER_RE = re.compile(
    r"\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z"
)
_WILDCARD_TOKENS = {"*", "x", "X"}


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = "system"

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # PRECONDITION: WHEN text contains leading zeroes in numeric identifiers or violates grammar, MUST raise InvalidVersionError.
        match = _SEMVER_RE.match(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid version string: {text!r}",
                raw_text=text,
            )

        pre_str, build_str = match.group(4), match.group(5)
        # POSTCONDITION: MUST parse valid SemVer 2.0.0 strings into Version records.
        return semver_solver.Version(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=tuple(pre_str.split(".")) if pre_str else (),
            build=tuple(build_str.split(".")) if build_str else (),
        )

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        # POSTCONDITION: MUST compare major, minor, and patch numerically.
        for a, b in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if a < b:
                return -1
            if a > b:
                return 1

        # POSTCONDITION: MUST rank normal versions higher than prerelease versions sharing identical major, minor, and patch numbers.
        pre1 = v1.prerelease
        pre2 = v2.prerelease
        if not pre1 and not pre2:
            return 0
        if not pre1 and pre2:
            return 1
        if pre1 and not pre2:
            return -1

        # POSTCONDITION: MUST compare prerelease segments numerically when both numeric, ASCII-lexicographically when string, and rank numeric below string.
        for s1, s2 in zip(pre1, pre2):
            if s1 == s2:
                continue
            is_num1 = s1.isdigit()
            is_num2 = s2.isdigit()
            if is_num1 and is_num2:
                n1, n2 = int(s1), int(s2)
                return -1 if n1 < n2 else 1
            if is_num1 and not is_num2:
                return -1
            if not is_num1 and is_num2:
                return 1
            return -1 if s1 < s2 else 1

        # Ranks longer pre-release segment sequences higher when common prefix segments match.
        if len(pre1) < len(pre2):
            return -1
        if len(pre1) > len(pre2):
            return 1
        return 0

    def _compile_range(
        self,
        text: str,
    ) -> Tuple[str, List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]]:
        """Validates and compiles a range string into trimmed text and DNF comparator clauses."""
        # PRECONDITION: WHEN text is empty, contains only whitespace, contains empty union clauses, uses comma delimiters, or violates range syntax, MUST raise InvalidRangeError.
        trimmed = text.strip()
        if not trimmed or "," in trimmed:
            raise semver_solver.InvalidRangeError(
                message=f"Empty or comma-containing range expression: {text!r}",
                raw_range=text,
            )

        raw_clauses = trimmed.split("||")
        compiled_clauses: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]] = []

        for raw_clause in raw_clauses:
            clause_str = raw_clause.strip()
            if not clause_str:
                raise semver_solver.InvalidRangeError(
                    message=f"Empty union clause in range expression: {text!r}",
                    raw_range=text,
                )
            compiled_clauses.append(self._parse_clause(clause_str, text))

        return trimmed, compiled_clauses

    def _parse_clause(
        self,
        clause_str: str,
        raw_range: str,
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        """Parses a single whitespace-delimited conjunctive clause into primitive comparators."""
        raw_tokens = clause_str.split()
        # Normalize tokens: merge dangling operators with following token, and handle hyphen ranges
        comparators: List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]] = []
        i = 0
        n = len(raw_tokens)
        while i < n:
            tok = raw_tokens[i]
            # Check for hyphen range: <v1> - <v2>
            if i + 2 < n and raw_tokens[i + 1] == "-":
                left_tok = tok
                right_tok = raw_tokens[i + 2]
                comparators.extend(self._expand_hyphen(left_tok, right_tok, raw_range))
                i += 3
                continue

            # If token is a standalone operator followed by an operand, merge with next token
            if (
                tok in ("==", "=", "!=", "<=", ">=", "<", ">", "^", "~")
                and i + 1 < n
                and raw_tokens[i + 1] != "-"
            ):
                tok = tok + raw_tokens[i + 1]
                i += 1

            comparators.extend(self._expand_single_token(tok, raw_range))
            i += 1

        return comparators

    def _parse_wildcard_or_version(
        self,
        target: str,
        raw_range: str,
    ) -> Tuple[str, Optional[semver_solver.Version], int, int]:
        """Classifies target as 'all_wildcard', 'major_wildcard', 'minor_wildcard', or 'exact'."""
        if target in _WILDCARD_TOKENS:
            return ("all_wildcard", None, 0, 0)

        # If there is no '-' or '+', check for M.x or M.m.x wildcards
        if "-" not in target and "+" not in target:
            parts = target.split(".")
            if len(parts) == 2 and parts[1] in _WILDCARD_TOKENS and _NUMERIC_RE.match(parts[0]):
                return ("major_wildcard", None, int(parts[0]), 0)
            if (
                len(parts) == 3
                and parts[2] in _WILDCARD_TOKENS
                and _NUMERIC_RE.match(parts[0])
                and _NUMERIC_RE.match(parts[1])
            ):
                return ("minor_wildcard", None, int(parts[0]), int(parts[1]))

        ver = self._parse_version_in_range(target, raw_range)
        return ("exact", ver, ver.major, ver.minor)

    def _parse_version_in_range(
        self,
        target: str,
        raw_range: str,
    ) -> semver_solver.Version:
        """Parses a full semantic version inside a range expression, raising InvalidRangeError on failure."""
        try:
            return self.parse_version(target)
        except semver_solver.InvalidVersionError as exc:
            raise semver_solver.InvalidRangeError(
                message=f"Invalid version {target!r} in range: {raw_range!r}",
                raw_range=raw_range,
            ) from exc

    def _expand_hyphen(
        self,
        left_tok: str,
        right_tok: str,
        raw_range: str,
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        """Expands M1.m1.p1 - M2.m2.p2 hyphen range into >= and <= bounds."""
        l_ver = self._parse_version_in_range(left_tok, raw_range)
        r_ver = self._parse_version_in_range(right_tok, raw_range)
        return [
            (semver_solver.ComparatorOp.GE, l_ver),
            (semver_solver.ComparatorOp.LE, r_ver),
        ]

    def _expand_single_token(
        self,
        token: str,
        raw_range: str,
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        """Expands a single comparator, caret, tilde, or wildcard token."""
        if token.startswith("^"):
            target = token[1:]
            ver = self._parse_version_in_range(target, raw_range)
            if ver.major > 0:
                upper_ver = semver_solver.Version(ver.major + 1, 0, 0)
            elif ver.minor > 0:
                upper_ver = semver_solver.Version(0, ver.minor + 1, 0)
            else:
                upper_ver = semver_solver.Version(0, 0, ver.patch + 1)
            return [
                (semver_solver.ComparatorOp.GE, ver),
                (semver_solver.ComparatorOp.LT, upper_ver),
            ]

        if token.startswith("~"):
            target = token[1:]
            ver = self._parse_version_in_range(target, raw_range)
            return [
                (semver_solver.ComparatorOp.GE, ver),
                (semver_solver.ComparatorOp.LT, semver_solver.Version(ver.major, ver.minor + 1, 0)),
            ]

        op: Optional[semver_solver.ComparatorOp] = None
        target = token
        for prefix, comp_op in (
            ("==", semver_solver.ComparatorOp.EQ),
            ("!=", semver_solver.ComparatorOp.NE),
            ("<=", semver_solver.ComparatorOp.LE),
            (">=", semver_solver.ComparatorOp.GE),
            ("=", semver_solver.ComparatorOp.EQ),
            ("<", semver_solver.ComparatorOp.LT),
            (">", semver_solver.ComparatorOp.GT),
        ):
            if token.startswith(prefix):
                op = comp_op
                target = token[len(prefix) :]
                break

        kind, ver, maj, min_ = self._parse_wildcard_or_version(target, raw_range)
        if kind == "exact":
            assert ver is not None
            effective_op = op if op is not None else semver_solver.ComparatorOp.EQ
            return [(effective_op, ver)]

        # Wildcard handling
        if op in (None, semver_solver.ComparatorOp.EQ):
            if kind == "all_wildcard":
                return [(semver_solver.ComparatorOp.GE, semver_solver.Version(0, 0, 0))]
            if kind == "major_wildcard":
                return [
                    (semver_solver.ComparatorOp.GE, semver_solver.Version(maj, 0, 0)),
                    (semver_solver.ComparatorOp.LT, semver_solver.Version(maj + 1, 0, 0)),
                ]
            return [
                (semver_solver.ComparatorOp.GE, semver_solver.Version(maj, min_, 0)),
                (semver_solver.ComparatorOp.LT, semver_solver.Version(maj, min_ + 1, 0)),
            ]

        raise semver_solver.InvalidRangeError(
            message=f"Relational operator with wildcard {token!r} is invalid in range: {raw_range!r}",
            raw_range=raw_range,
        )

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # Validates syntax and trims range expression.
        trimmed, _ = self._compile_range(text)
        return semver_solver.VersionRange(raw_text=trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        _, clauses = self._compile_range(range_constraint.raw_text)

        for clause in clauses:
            # POSTCONDITION: WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False unless range explicitly targets that prerelease by specifying a prerelease identifier sharing the same major, minor, and patch numbers.
            if version.is_prerelease and not include_prerelease:
                has_matching_prerelease_tuple = any(
                    comp_ver.is_prerelease
                    and comp_ver.major == version.major
                    and comp_ver.minor == version.minor
                    and comp_ver.patch == version.patch
                    for _, comp_ver in clause
                )
                if not has_matching_prerelease_tuple:
                    continue

            if all(self._eval_comparator(version, op, comp_ver) for op, comp_ver in clause):
                return True

        return False

    def _eval_comparator(
        self,
        version: semver_solver.Version,
        op: semver_solver.ComparatorOp,
        target: semver_solver.Version,
    ) -> bool:
        """Evaluates a single primitive comparator using compare_precedence."""
        cmp = self.compare_precedence(version, target)
        if op == semver_solver.ComparatorOp.EQ:
            return cmp == 0
        if op == semver_solver.ComparatorOp.NE:
            return cmp != 0
        if op == semver_solver.ComparatorOp.LT:
            return cmp < 0
        if op == semver_solver.ComparatorOp.LE:
            return cmp <= 0
        if op == semver_solver.ComparatorOp.GT:
            return cmp > 0
        return cmp >= 0


@singleton_type("system")
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
        # Sort in descending version precedence order
        releases.sort(
            key=cmp_to_key(lambda r1, r2: engine.compare_precedence(r1.version, r2.version)),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        # PRECONDITION: WHEN name is not registered, MUST raise PackageNotFoundError.
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
            unassigned = [p for p in accumulated_constraints if p not in assignment]
            if not unassigned:
                return True

            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for pkg in unassigned:
                if repo.has_package(pkg):
                    available = repo.get_releases(pkg)
                else:
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
                for req in requesters:
                    if req != "root":
                        conflicting_packages.add(req)
                details = ", ".join(
                    f"{src} ({rng.raw_text})" for src, rng in accumulated_constraints[selected_pkg]
                )
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints: {details}"
                )
                return False

            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

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
                                f"Conflict: '{selected_pkg}' ({candidate.version}) requires {dep.name} {dep.range_constraint.raw_text}, which conflicts with assigned {dep.name} {assignment[dep.name].version}"
                            )
                            break
                    else:
                        constraint_entry = (selected_pkg, dep.range_constraint)
                        accumulated_constraints.setdefault(dep.name, []).append(constraint_entry)
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
                pkg: rel.version for pkg, rel in sorted(assignment.items())
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        explanation = "; ".join(conflict_trail)
        raise semver_solver.ResolutionConflictError(
            message=f"Resolution failed: {explanation}",
            conflicting_packages=tuple(sorted(conflicting_packages)),
            explanation=explanation,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_solver.VersionEngine],
        tier='system',
    )
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, semver_solver.PackageRepository],
        tier='system',
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, semver_solver.DependencySolver],
        tier='system',
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T21:10:47Z
# LAST_CHANGED: 2026-11-06T21:03:49Z
# CHANGE: Consolidate SemVer 2.0.0 grammar validation into a single regular expression in parse_version and prune unreachable and redundant defensive branches in VersionEngine range parsing
# COVERAGE_AUDIT: 2026-11-06T21:05:03Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T21:10:47Z
# PRETENSE_QA_AUDIT: 2026-11-06T21:09:58Z
# QA_AUDIT: 2026-11-06T21:04:28Z
# --- END AUTOFAB METADATA ---
