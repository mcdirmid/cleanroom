# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261028_214622_gemini-3_8-flash_semver_solver_pretense
# Timestamp: 2026-10-28T21:46:22.968427+00:00
# Benchmark Task: semver_solver
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 3,343,649
#   Cached Inbound Tokens:   28,302,760
#   Outbound Tokens:         397,021
#   Total Tokens:            32,043,430
#   Financial Cost ($USD):   $1.2007
#   Wall Clock Duration:     2948.17s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 3, pretense: 6, pretense_coverage: 4, pretense_qa: 7 (Total: 20)
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

    def __post_init__(self) -> None:
        super().__init__(self.message)

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
# LAST_CLEANED: 2026-10-28T21:56:19Z
# LAST_CHANGED: 2026-10-28T21:56:19Z
# CHANGE: Implement non-frozen dataclass exceptions, Version properties and format, VersionRange str representation, and remove TODO stubs
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations

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

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)
from . import semver_solver

# Regular expression for SemVer 2.0.0 specification
SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# Wildcard patterns
WILDCARD_STAR = re.compile(r"^[*xX]$")
WILDCARD_MAJOR = re.compile(r"^(0|[1-9]\d*)\.[*xX]$")
WILDCARD_MINOR = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.[*xX]$")

# Relational and prefix operators
PREFIX_OPS = (">=", "<=", "==", "!=", ">", "<", "=", "^", "~")


class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        pass

    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # Match against SemVer 2.0.0 regex enforcing no leading zeroes in numeric segments
        m = SEMVER_REGEX.match(text)
        if not m:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid SemVer 2.0.0 version string: '{text}'",
                raw_text=text,
            )
        major = int(m.group("major"))
        minor = int(m.group("minor"))
        patch = int(m.group("patch"))
        raw_prerelease = m.group("prerelease")
        prerelease = tuple(raw_prerelease.split(".")) if raw_prerelease else ()
        raw_build = m.group("build")
        build = tuple(raw_build.split(".")) if raw_build else ()
        return semver_solver.Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
            build=build,
        )

    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        # Compares major, minor, and patch numbers numerically in sequence
        if v1.major != v2.major:
            return 1 if v1.major > v2.major else -1
        if v1.minor != v2.minor:
            return 1 if v1.minor > v2.minor else -1
        if v1.patch != v2.patch:
            return 1 if v1.patch > v2.patch else -1

        # Ranks normal version higher than pre-release version sharing major, minor, patch
        if not v1.prerelease and v2.prerelease:
            return 1
        if v1.prerelease and not v2.prerelease:
            return -1
        if not v1.prerelease and not v2.prerelease:
            return 0

        # Compares pre-release segments position by position
        for seg1, seg2 in zip(v1.prerelease, v2.prerelease):
            if seg1 == seg2:
                continue
            is_num1 = seg1.isdigit()
            is_num2 = seg2.isdigit()
            if is_num1 and is_num2:
                val1, val2 = int(seg1), int(seg2)
                if val1 != val2:
                    return 1 if val1 > val2 else -1
            elif is_num1 and not is_num2:
                # Numeric identifiers have lower precedence than non-numeric
                return -1
            elif not is_num1 and is_num2:
                # Non-numeric identifiers have higher precedence than numeric
                return 1
            else:
                # Lexical comparison in ASCII sort order
                if seg1 != seg2:
                    return 1 if seg1 > seg2 else -1

        # Longer pre-release segment sequence ranks higher when prefix matches
        if len(v1.prerelease) != len(v2.prerelease):
            return 1 if len(v1.prerelease) > len(v2.prerelease) else -1

        # Build metadata is completely excluded from comparison
        return 0

    def _parse_target(self, target_str: str, raw_range: str) -> Tuple[str, Any]:
        """Parses a target operand in a range clause into a version or wildcard specification."""
        if WILDCARD_STAR.match(target_str):
            return ("wildcard", (None, None))
        m_maj = WILDCARD_MAJOR.match(target_str)
        if m_maj:
            return ("wildcard", (int(m_maj.group(1)), None))
        m_min = WILDCARD_MINOR.match(target_str)
        if m_min:
            return ("wildcard", (int(m_min.group(1)), int(m_min.group(2))))

        try:
            ver = self.parse_version(target_str)
            return ("version", ver)
        except semver_solver.InvalidVersionError as e:
            raise semver_solver.InvalidRangeError(
                message=f"Invalid version or range target: '{target_str}'",
                raw_range=raw_range,
            ) from e

    def _compile_range(
        self,
        text: str,
    ) -> Tuple[str, List[Tuple[List[Tuple[str, Any]], Set[Tuple[int, int, int]]]]]:
        """Compiles a range expression string into canonical text and parsed clauses."""
        if "," in text:
            raise semver_solver.InvalidRangeError(
                message="Comma delimiters are not permitted in version ranges",
                raw_range=text,
            )

        trimmed = text.strip()
        if not trimmed:
            raise semver_solver.InvalidRangeError(
                message="Range expression cannot be empty or whitespace only",
                raw_range=text,
            )

        raw_clauses = text.split("||")
        clause_texts = [c.strip() for c in raw_clauses]
        if any(c == "" for c in clause_texts):
            raise semver_solver.InvalidRangeError(
                message="Empty union clause in range expression",
                raw_range=text,
            )

        canonical_raw_text = " || ".join(clause_texts)
        compiled_clauses: List[
            Tuple[List[Tuple[str, Any]], Set[Tuple[int, int, int]]]
        ] = []

        for clause_str in clause_texts:
            tokens = clause_str.split()
            atomic_comps: List[Tuple[str, Any]] = []
            targeted_prereleases: Set[Tuple[int, int, int]] = set()
            idx = 0
            n = len(tokens)

            while idx < n:
                tok = tokens[idx]

                # Check for hyphen range: lower_bound - upper_bound
                if idx + 1 < n and tokens[idx + 1] == "-":
                    if any(tok == op or tok.startswith(op) for op in PREFIX_OPS):
                        raise semver_solver.InvalidRangeError(
                            message=f"Hyphen range lower bound cannot have prefix operator: '{tok}'",
                            raw_range=text,
                        )
                    if idx + 2 >= n:
                        raise semver_solver.InvalidRangeError(
                            message=f"Hyphen range missing upper bound after '-': '{clause_str}'",
                            raw_range=text,
                        )
                    high_tok = tokens[idx + 2]
                    if any(high_tok == op or high_tok.startswith(op) for op in PREFIX_OPS):
                        raise semver_solver.InvalidRangeError(
                            message=f"Hyphen range upper bound cannot have prefix operator: '{high_tok}'",
                            raw_range=text,
                        )

                    low_kind, low_val = self._parse_target(tok, text)
                    high_kind, high_val = self._parse_target(high_tok, text)

                    if low_kind == "version":
                        if low_val.is_prerelease:
                            targeted_prereleases.add((low_val.major, low_val.minor, low_val.patch))
                        atomic_comps.append((">=", low_val))
                    else:
                        m_maj, m_min = low_val
                        if m_maj is None:
                            atomic_comps.append((">=", semver_solver.Version(0, 0, 0)))
                        elif m_min is None:
                            atomic_comps.append((">=", semver_solver.Version(m_maj, 0, 0)))
                        else:
                            atomic_comps.append((">=", semver_solver.Version(m_maj, m_min, 0)))

                    if high_kind == "version":
                        if high_val.is_prerelease:
                            targeted_prereleases.add((high_val.major, high_val.minor, high_val.patch))
                        atomic_comps.append(("<=", high_val))
                    else:
                        m_maj, m_min = high_val
                        if m_maj is not None:
                            if m_min is None:
                                atomic_comps.append(("<", semver_solver.Version(m_maj + 1, 0, 0)))
                            else:
                                atomic_comps.append(("<", semver_solver.Version(m_maj, m_min + 1, 0)))

                    idx += 3
                    continue

                if tok == "-":
                    raise semver_solver.InvalidRangeError(
                        message=f"Unexpected hyphen token in clause: '{clause_str}'",
                        raw_range=text,
                    )

                # Parse prefix operator or default to equality
                matched_op: Optional[str] = None
                target_str = ""
                for op in PREFIX_OPS:
                    if tok == op:
                        matched_op = op
                        target_str = ""
                        break
                    elif tok.startswith(op):
                        matched_op = op
                        target_str = tok[len(op):]
                        break

                if matched_op is not None:
                    if target_str == "":
                        if idx + 1 >= n:
                            raise semver_solver.InvalidRangeError(
                                message=f"Operator '{matched_op}' without target in clause: '{clause_str}'",
                                raw_range=text,
                            )
                        target_str = tokens[idx + 1]
                        idx += 2
                    else:
                        idx += 1
                else:
                    matched_op = "="
                    target_str = tok
                    idx += 1

                kind, val = self._parse_target(target_str, text)

                if kind == "version":
                    v: semver_solver.Version = val
                    if v.is_prerelease:
                        targeted_prereleases.add((v.major, v.minor, v.patch))

                    if matched_op in ("=", "=="):
                        atomic_comps.append(("==", v))
                    elif matched_op == "!=":
                        atomic_comps.append(("!=", v))
                    elif matched_op == "<":
                        atomic_comps.append(("<", v))
                    elif matched_op == "<=":
                        atomic_comps.append(("<=", v))
                    elif matched_op == ">":
                        atomic_comps.append((">", v))
                    elif matched_op == ">=":
                        atomic_comps.append((">=", v))
                    elif matched_op == "^":
                        atomic_comps.append((">=", v))
                        if v.major > 0:
                            upper = semver_solver.Version(v.major + 1, 0, 0)
                        elif v.minor > 0:
                            upper = semver_solver.Version(0, v.minor + 1, 0)
                        else:
                            upper = semver_solver.Version(0, 0, v.patch + 1)
                        atomic_comps.append(("<", upper))
                    elif matched_op == "~":
                        atomic_comps.append((">=", v))
                        upper = semver_solver.Version(v.major, v.minor + 1, 0)
                        atomic_comps.append(("<", upper))
                else:
                    m_maj, m_min = val
                    if matched_op in ("=", "=="):
                        if m_maj is None:
                            atomic_comps.append((">=", semver_solver.Version(0, 0, 0)))
                        elif m_min is None:
                            atomic_comps.append((">=", semver_solver.Version(m_maj, 0, 0)))
                            atomic_comps.append(("<", semver_solver.Version(m_maj + 1, 0, 0)))
                        else:
                            atomic_comps.append((">=", semver_solver.Version(m_maj, m_min, 0)))
                            atomic_comps.append(("<", semver_solver.Version(m_maj, m_min + 1, 0)))
                    elif matched_op == "!=":
                        if m_maj is None:
                            # != * is impossible for any semantic version to satisfy
                            atomic_comps.append(("impossible", None))
                        else:
                            atomic_comps.append(("!_wildcard", (m_maj, m_min)))
                    elif matched_op == ">":
                        if m_maj is None:
                            atomic_comps.append(("impossible", None))
                        elif m_min is None:
                            atomic_comps.append((">=", semver_solver.Version(m_maj + 1, 0, 0)))
                        else:
                            atomic_comps.append((">=", semver_solver.Version(m_maj, m_min + 1, 0)))
                    elif matched_op == ">=":
                        if m_maj is None:
                            atomic_comps.append((">=", semver_solver.Version(0, 0, 0)))
                        elif m_min is None:
                            atomic_comps.append((">=", semver_solver.Version(m_maj, 0, 0)))
                        else:
                            atomic_comps.append((">=", semver_solver.Version(m_maj, m_min, 0)))
                    elif matched_op == "<":
                        if m_maj is None:
                            atomic_comps.append(("impossible", None))
                        elif m_min is None:
                            atomic_comps.append(("<", semver_solver.Version(m_maj, 0, 0)))
                        else:
                            atomic_comps.append(("<", semver_solver.Version(m_maj, m_min, 0)))
                    elif matched_op == "<=":
                        if m_maj is None:
                            atomic_comps.append((">=", semver_solver.Version(0, 0, 0)))
                        elif m_min is None:
                            atomic_comps.append(("<", semver_solver.Version(m_maj + 1, 0, 0)))
                        else:
                            atomic_comps.append(("<", semver_solver.Version(m_maj, m_min + 1, 0)))
                    elif matched_op == "^":
                        if m_maj is None:
                            atomic_comps.append((">=", semver_solver.Version(0, 0, 0)))
                        elif m_min is None:
                            if m_maj > 0:
                                atomic_comps.append((">=", semver_solver.Version(m_maj, 0, 0)))
                                atomic_comps.append(("<", semver_solver.Version(m_maj + 1, 0, 0)))
                            else:
                                atomic_comps.append((">=", semver_solver.Version(0, 0, 0)))
                                atomic_comps.append(("<", semver_solver.Version(1, 0, 0)))
                        else:
                            if m_maj > 0:
                                atomic_comps.append((">=", semver_solver.Version(m_maj, m_min, 0)))
                                atomic_comps.append(("<", semver_solver.Version(m_maj + 1, 0, 0)))
                            elif m_min > 0:
                                atomic_comps.append((">=", semver_solver.Version(0, m_min, 0)))
                                atomic_comps.append(("<", semver_solver.Version(0, m_min + 1, 0)))
                            else:
                                atomic_comps.append((">=", semver_solver.Version(0, 0, 0)))
                                atomic_comps.append(("<", semver_solver.Version(0, 1, 0)))
                    elif matched_op == "~":
                        if m_maj is None:
                            atomic_comps.append((">=", semver_solver.Version(0, 0, 0)))
                        elif m_min is None:
                            atomic_comps.append((">=", semver_solver.Version(m_maj, 0, 0)))
                            atomic_comps.append(("<", semver_solver.Version(m_maj + 1, 0, 0)))
                        else:
                            atomic_comps.append((">=", semver_solver.Version(m_maj, m_min, 0)))
                            atomic_comps.append(("<", semver_solver.Version(m_maj, m_min + 1, 0)))

            compiled_clauses.append((atomic_comps, targeted_prereleases))

        return canonical_raw_text, compiled_clauses

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        canonical_raw_text, _ = self._compile_range(text)
        return semver_solver.VersionRange(raw_text=canonical_raw_text)

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        _, clauses = self._compile_range(range_constraint.raw_text)
        for atomic_comps, targeted_prereleases in clauses:
            # Filter pre-release versions when include_prerelease is False unless explicitly targeted
            if version.is_prerelease and not include_prerelease:
                if (version.major, version.minor, version.patch) not in targeted_prereleases:
                    continue

            # Tests candidate version against each comparator in a clause
            all_passed = True
            for op, target_v in atomic_comps:
                if op == "impossible":
                    all_passed = False
                    break
                elif op == "!_wildcard":
                    m_maj, m_min = target_v
                    if m_min is None:
                        in_range = (
                            self.compare_precedence(version, semver_solver.Version(m_maj, 0, 0)) >= 0
                            and self.compare_precedence(version, semver_solver.Version(m_maj + 1, 0, 0)) < 0
                        )
                    else:
                        in_range = (
                            self.compare_precedence(version, semver_solver.Version(m_maj, m_min, 0)) >= 0
                            and self.compare_precedence(version, semver_solver.Version(m_maj, m_min + 1, 0)) < 0
                        )
                    if in_range:
                        all_passed = False
                        break
                else:
                    cmp_val = self.compare_precedence(version, target_v)
                    if op == "==" and cmp_val != 0:
                        all_passed = False
                        break
                    elif op == "!=" and cmp_val == 0:
                        all_passed = False
                        break
                    elif op == "<" and cmp_val >= 0:
                        all_passed = False
                        break
                    elif op == "<=" and cmp_val > 0:
                        all_passed = False
                        break
                    elif op == ">" and cmp_val <= 0:
                        all_passed = False
                        break
                    elif op == ">=" and cmp_val < 0:
                        all_passed = False
                        break

            if all_passed:
                return True

        return False


class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        if release.name not in self._packages:
            self._packages[release.name] = []

        # Replace existing release with identical version or append new release
        releases = [r for r in self._packages[release.name] if r.version != release.version]
        releases.append(release)

        # Re-sorts release list in descending version precedence order
        releases.sort(
            key=functools.cmp_to_key(lambda a, b: engine.compare_precedence(a.version, b.version)),
            reverse=True,
        )
        self._packages[release.name] = releases

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    def all_packages(self) -> Set[str]:
        """Returns the set of all registered package names."""
        return set(self._packages.keys())


class DependencySolver(semver_solver.DependencySolver):
    tier = system

    def __init__(self) -> None:
        pass

    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
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
                    rel for rel in available
                    if all(engine.satisfies(rel.version, rng) for _, rng in accumulated_constraints[pkg])
                ]
                candidates_map[pkg] = viable

            # Minimum Remaining Values variable selection, tie-break by package name
            selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
                conflicting_packages.add(selected_pkg)
                conflicting_packages.update(requesters)
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

                for pkg_name, constraint_entry in reversed(newly_added):
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        success = backtrack()
        if success:
            selected_versions = {
                pkg: rel.version for pkg, rel in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        pkgs = tuple(sorted(p for p in conflicting_packages if p != "root"))
        explanation = "\n".join(conflict_trail)
        raise semver_solver.ResolutionConflictError(
            message=f"Failed to resolve dependencies for: {', '.join(d.name for d in root_dependencies)}",
            conflicting_packages=pkgs,
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T22:35:26Z
# LAST_CHANGED: 2026-10-28T22:25:29Z
# CHANGE: Support != comparator for universal and partial wildcards in _compile_range and satisfies, evaluating != * to False for all versions
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T22:35:26Z
# PRETENSE_QA_AUDIT: 2026-10-28T22:34:54Z
# --- END CLEANROOM METADATA ---
