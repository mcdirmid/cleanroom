# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_205321_gemini-3_8-flash_semver_solver_pretense_baseline
# Timestamp: 2026-10-29T20:53:21.278852+00:00
# Benchmark Task: semver_solver
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: antigravity
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 619,029
#   Cached Inbound Tokens:   14,286,990
#   Outbound Tokens:         136,020
#   Total Tokens:            15,042,039
#   Financial Cost ($USD):   $0.4735
#   Wall Clock Duration:     1173.41s
#   Step Latencies (s):      []
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
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum

# Requirements specified in semver_solver.pyi

@dataclass
class SemVerError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    raw_text: str


@dataclass
class InvalidRangeError(SemVerError):
    raw_range: str


@dataclass
class ResolutionConflictError(SemVerError):
    conflicting_packages: Tuple[str, ...]
    explanation: str


@dataclass
class PackageNotFoundError(SemVerError):
    package_name: str


class ComparatorOp(enum.Enum):
    EQ = '=='
    NE = '!='
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        return len(self.prerelease) > 0

    def format(self) -> str:
        res = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            res = f"{res}-{'.'.join(self.prerelease)}"
        if self.build:
            res = f"{res}+{'.'.join(self.build)}"
        return res

    def __str__(self) -> str:
        return self.format()


@dataclass(frozen=True)
class VersionRange:
    raw_text: str

    def __str__(self) -> str:
        return self.raw_text


@dataclass(frozen=True)
class PackageDependency:
    name: str
    range_constraint: VersionRange


@dataclass(frozen=True)
class PackageRelease:
    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@dataclass(frozen=True)
class ResolutionOutcome:
    selected_versions: Mapping[str, Version]
    derivation_steps: Tuple[str, ...]


class VersionEngine(Protocol):
    def parse_version(self, text: str) -> Version:
        ...

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        ...

    def parse_range(self, text: str) -> VersionRange:
        ...

    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool = False) -> bool:
        ...


class PackageRepository(Protocol):
    def register_package(self, release: PackageRelease) -> None:
        ...

    def get_releases(self, name: str) -> List[PackageRelease]:
        ...

    def has_package(self, name: str) -> bool:
        ...

    def all_packages(self) -> Set[str]:
        ...


class DependencySolver(Protocol):
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T21:12:52Z
# LAST_CHANGED: 2026-10-29T21:12:52Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 587e87302c6a
# COVERAGE_AUDIT: 2026-10-29T21:12:52Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T21:12:52Z
# PRETENSE_QA_AUDIT: 2026-10-29T21:12:52Z
# QA_AUDIT: 2026-10-29T21:12:52Z
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

import enum
from functools import cmp_to_key
import re

SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|[0-9a-zA-Z-]*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|[0-9a-zA-Z-]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_BARE_PARTIAL_REGEX = re.compile(r"^\d+(\.\d+)?$")
_LEADING_ZERO_COMPONENT_REGEX = re.compile(r"(^|\.)0\d+")
_WILDCARD_MAJOR_REGEX = re.compile(r"^(?P<major>0|[1-9]\d*)\.[xX\*]$")
_WILDCARD_MINOR_REGEX = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.[xX\*]$")
_OPERATORS = ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~")


def _is_wildcard(text: str) -> bool:
    return (
        text in ("*", "x", "X")
        or _WILDCARD_MAJOR_REGEX.match(text) is not None
        or _WILDCARD_MINOR_REGEX.match(text) is not None
    )


def _validate_operand(operand: str, raw_range: str) -> None:
    if _BARE_PARTIAL_REGEX.match(operand):
        raise semver_solver.InvalidRangeError(
            message=f"Bare partial version lacking wildcard not permitted: {operand}",
            raw_range=raw_range,
        )
    if _is_wildcard(operand):
        return
    if SEMVER_REGEX.match(operand) is None:
        raise semver_solver.InvalidRangeError(
            message=f"Invalid version format in range: {operand}",
            raw_range=raw_range,
        )


def _normalize_comparator(op: str, operand: str) -> List[Tuple[str, str]]:
    if operand in ("*", "x", "X"):
        return [(">=", "0.0.0")]
    m_major = _WILDCARD_MAJOR_REGEX.match(operand)
    if m_major is not None:
        major = int(m_major.group("major"))
        return [(">=", f"{major}.0.0"), ("<", f"{major + 1}.0.0")]
    m_minor = _WILDCARD_MINOR_REGEX.match(operand)
    if m_minor is not None:
        major = int(m_minor.group("major"))
        minor = int(m_minor.group("minor"))
        return [(">=", f"{major}.{minor}.0"), ("<", f"{major}.{minor + 1}.0")]
    return [(op, operand)]


class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        pass

    def parse_version(self, text: str) -> semver_solver.Version:
        match = SEMVER_REGEX.match(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version: {text}",
                raw_text=text,
            )
        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))
        prerelease_raw = match.group("prerelease")
        build_raw = match.group("build")

        prerelease = tuple(prerelease_raw.split(".")) if prerelease_raw is not None else ()
        build = tuple(build_raw.split(".")) if build_raw is not None else ()

        return semver_solver.Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
            build=build,
        )

    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1

        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease and v2.prerelease:
            return 1
        if v1.prerelease and not v2.prerelease:
            return -1

        for id1, id2 in zip(v1.prerelease, v2.prerelease):
            if id1 == id2:
                continue
            id1_is_num = id1.isdigit()
            id2_is_num = id2.isdigit()
            if id1_is_num and id2_is_num:
                n1, n2 = int(id1), int(id2)
                if n1 != n2:
                    return -1 if n1 < n2 else 1
            elif id1_is_num and not id2_is_num:
                return -1
            elif not id1_is_num and id2_is_num:
                return 1
            else:
                return -1 if id1 < id2 else 1

        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

        return 0

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        if not text or not text.strip():
            raise semver_solver.InvalidRangeError(message="Range text cannot be empty", raw_range=text)
        if "," in text:
            raise semver_solver.InvalidRangeError(message="Commas not permitted in range", raw_range=text)

        raw_clauses = text.split("||")
        trimmed_clauses: List[str] = []
        for c in raw_clauses:
            clause = c.strip()
            if not clause:
                raise semver_solver.InvalidRangeError(
                    message="Empty clause in range expression",
                    raw_range=text,
                )
            self._parse_clause(clause, raw_range=text)
            trimmed_clauses.append(clause)

        return semver_solver.VersionRange(raw_text=" || ".join(trimmed_clauses))

    def _parse_clause(self, clause: str, raw_range: str) -> List[Tuple[str, str]]:
        words = clause.split()
        if "-" in words:
            hyphen_idx = words.index("-")
            if hyphen_idx == 0 or hyphen_idx == len(words) - 1:
                raise semver_solver.InvalidRangeError(message="Dangling hyphen range", raw_range=raw_range)
            left = words[hyphen_idx - 1]
            right = words[hyphen_idx + 1]
            for op in _OPERATORS:
                if left.startswith(op) or right.startswith(op):
                    raise semver_solver.InvalidRangeError(
                        message="Operators not permitted on hyphen range bounds",
                        raw_range=raw_range,
                    )
            _validate_operand(left, raw_range)
            _validate_operand(right, raw_range)

            comparators: List[Tuple[str, str]] = []
            comparators.extend(_normalize_comparator(">=", left))
            comparators.extend(_normalize_comparator("<=", right))

            remaining_words = words[: hyphen_idx - 1] + words[hyphen_idx + 2 :]
            if remaining_words:
                comparators.extend(self._tokenize_words(remaining_words, raw_range))
            return comparators

        return self._tokenize_words(words, raw_range)

    def _tokenize_words(self, words: List[str], raw_range: str) -> List[Tuple[str, str]]:
        comparators: List[Tuple[str, str]] = []
        i = 0
        while i < len(words):
            w = words[i]
            matched_op: Optional[str] = None
            if w in _OPERATORS:
                matched_op = w
                i += 1
                if i >= len(words):
                    raise semver_solver.InvalidRangeError(
                        message=f"Dangling operator '{matched_op}' without operand",
                        raw_range=raw_range,
                    )
                operand = words[i]
            else:
                for op in _OPERATORS:
                    if w.startswith(op):
                        matched_op = op
                        operand = w[len(op) :]
                        break
                else:
                    matched_op = ""
                    operand = w

            for op in _OPERATORS:
                if operand.startswith(op):
                    raise semver_solver.InvalidRangeError(
                        message=f"Consecutive operators found: '{matched_op}' and '{operand}'",
                        raw_range=raw_range,
                    )

            _validate_operand(operand, raw_range)
            comparators.extend(_normalize_comparator(matched_op, operand))
            i += 1
        return comparators

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        clauses_raw = range_constraint.raw_text.split("||")
        for c in clauses_raw:
            clause = c.strip()
            comparators = self._parse_clause(clause, raw_range=range_constraint.raw_text)

            # Check prerelease acceptance rule for clause
            if version.is_prerelease and not include_prerelease:
                targets_prerelease = False
                for _, operand in comparators:
                    target_v = self.parse_version(operand)
                    if (
                        target_v.is_prerelease
                        and (target_v.major, target_v.minor, target_v.patch)
                        == (version.major, version.minor, version.patch)
                    ):
                        targets_prerelease = True
                        break
                if not targets_prerelease:
                    continue

            # Evaluate each comparator
            clause_satisfied = True
            for op, operand in comparators:
                if not self._eval_comparator(version, op, operand):
                    clause_satisfied = False
                    break

            if clause_satisfied:
                return True

        return False

    def _eval_comparator(self, v: semver_solver.Version, op: str, operand: str) -> bool:
        target_v = self.parse_version(operand)
        cmp_val = self.compare_precedence(v, target_v)

        if op in ("", "=", "=="):
            return cmp_val == 0
        elif op == "!=":
            return cmp_val != 0
        elif op == "<":
            return cmp_val < 0
        elif op == "<=":
            return cmp_val <= 0
        elif op == ">":
            return cmp_val > 0
        elif op == ">=":
            return cmp_val >= 0
        elif op == "^":
            if cmp_val < 0:
                return False
            if target_v.major > 0:
                upper = semver_solver.Version(target_v.major + 1, 0, 0)
            elif target_v.minor > 0:
                upper = semver_solver.Version(0, target_v.minor + 1, 0)
            elif target_v.patch > 0:
                upper = semver_solver.Version(0, 0, target_v.patch + 1)
            else:
                upper = semver_solver.Version(0, 0, 1)
            return self.compare_precedence(v, upper) < 0
        else:
            if cmp_val < 0:
                return False
            upper = semver_solver.Version(target_v.major, target_v.minor + 1, 0)
            return self.compare_precedence(v, upper) < 0


class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        name = release.name
        if name not in self._packages:
            self._packages[name] = []
        self._packages[name].append(release)
        version_engine = get_singleton(semver_solver.VersionEngine)
        self._packages[name].sort(
            key=cmp_to_key(lambda r1, r2: version_engine.compare_precedence(r1.version, r2.version)),
            reverse=True,
        )

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' not found in repository",
                package_name=name,
            )
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        return name in self._packages

    def all_packages(self) -> Set[str]:
        return set(self._packages.keys())


class DependencySolver(semver_solver.DependencySolver):
    tier = system

    def __init__(self) -> None:
        pass

    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        repo = get_singleton(semver_solver.PackageRepository)
        engine = get_singleton(semver_solver.VersionEngine)

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
                try:
                    available = repo.get_releases(pkg)
                except semver_solver.PackageNotFoundError:
                    available = []
                viable = [
                    rel
                    for rel in available
                    if all(engine.satisfies(rel.version, rng) for _, rng in accumulated_constraints[pkg])
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
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
                )
                return False

            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        if not engine.satisfies(assignment[dep.name].version, dep.range_constraint):
                            conflict_detected = True
                            conflicting_packages.add(selected_pkg)
                            conflicting_packages.add(dep.name)
                            conflict_trail.append(
                                f"Conflict: '{selected_pkg}' requires {dep.name} {getattr(dep.range_constraint, 'raw_text', '')}"
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

        success = backtrack()
        if not success:
            explanation = "\n".join(conflict_trail)
            pkgs = tuple(sorted(p for p in conflicting_packages if p != "root"))
            raise semver_solver.ResolutionConflictError(
                message=f"Dependency resolution conflict:\n{explanation}",
                conflicting_packages=pkgs or (tuple(sorted(conflicting_packages)) if conflicting_packages else ()),
                explanation=explanation,
            )

        selected_versions = {pkg: rel.version for pkg, rel in assignment.items()}
        return semver_solver.ResolutionOutcome(
            selected_versions=selected_versions,
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T21:12:52Z
# LAST_CHANGED: 2026-10-29T21:12:52Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: cf95cf430d7a
# COVERAGE_AUDIT: 2026-10-29T21:12:52Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T21:12:52Z
# PRETENSE_QA_AUDIT: 2026-10-29T21:12:52Z
# QA_AUDIT: 2026-10-29T21:12:52Z
# --- END CLEANROOM METADATA ---
