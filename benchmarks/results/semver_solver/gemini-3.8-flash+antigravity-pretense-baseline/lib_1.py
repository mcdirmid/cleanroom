# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261028_212810_gemini-3_8-flash_semver_solver_pretense_baseline
# Timestamp: 2026-10-28T21:28:10.000000+00:00
# Benchmark Task: semver_solver
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 381,580
#   Cached Inbound Tokens:   4,561,659
#   Outbound Tokens:         88,462
#   Total Tokens:            5,031,701
#   Financial Cost ($USD):   $0.1876
#   Wall Clock Duration:     684.50s
#   Step Latencies (s):      []
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       20
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          100.0%
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
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += "-" + ".".join(self.prerelease)
        if self.build:
            s += "+" + ".".join(self.build)
        return s

    def __str__(self) -> str:
        return self.format()


@dataclass(frozen=True)
class VersionRange:
    raw_text: str

    def __str__(self) -> str:
        return self.raw_text



@dataclass(frozen=True)
class PackageDependency:
    # TODO_PackageDependency_body
    name: str
    range_constraint: VersionRange


@dataclass(frozen=True)
class PackageRelease:
    # TODO_PackageRelease_body
    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@dataclass(frozen=True)
class ResolutionOutcome:
    # TODO_ResolutionOutcome_body
    selected_versions: Mapping[str, Version]
    derivation_steps: Tuple[str, ...]


class VersionEngine(Protocol):
    def parse_version(self, text: str) -> Version:
        # TODO_parse_version_body
        ...

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # TODO_compare_precedence_body
        ...

    def parse_range(self, text: str) -> VersionRange:
        # TODO_parse_range_body
        ...

    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool=False) -> bool:
        # TODO_satisfies_body
        ...


class PackageRepository(Protocol):
    def register_package(self, release: PackageRelease) -> None:
        # TODO_register_package_body
        ...

    def get_releases(self, name: str) -> List[PackageRelease]:
        # TODO_get_releases_body
        ...

    def has_package(self, name: str) -> bool:
        # TODO_has_package_body
        ...

    def all_packages(self) -> Set[str]:
        # TODO_all_packages_body
        ...


class DependencySolver(Protocol):
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        # TODO_resolve_body
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T21:39:31Z
# LAST_CHANGED: 2026-10-28T21:39:31Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: c60f0c97346b
# COVERAGE_AUDIT: 2026-10-28T21:39:31Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T21:39:31Z
# PRETENSE_QA_AUDIT: 2026-10-28T21:39:31Z
# QA_AUDIT: 2026-10-28T21:39:31Z
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from functools import cmp_to_key
import re
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

WILDCARD_X_REGEX = re.compile(r"^(\*|[xX])$")
WILDCARD_M_X_REGEX = re.compile(r"^(0|[1-9]\d*)\.(\*|[xX])$")
WILDCARD_M_M_X_REGEX = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(\*|[xX])$")


class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        pass

    def parse_version(self, text: str) -> semver_solver.Version:
        m = SEMVER_REGEX.match(text)
        if not m:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid SemVer 2.0.0 version string: '{text}'",
                raw_text=text,
            )
        maj_str, min_str, pat_str, pre_str, bld_str = m.groups()
        prerelease = tuple(pre_str.split(".")) if pre_str else ()
        build = tuple(bld_str.split(".")) if bld_str else ()
        return semver_solver.Version(
            major=int(maj_str),
            minor=int(min_str),
            patch=int(pat_str),
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

        if v1.prerelease and not v2.prerelease:
            return -1
        if not v1.prerelease and v2.prerelease:
            return 1
        if v1.prerelease and v2.prerelease:
            for p1, p2 in zip(v1.prerelease, v2.prerelease):
                if p1 == p2:
                    continue
                p1_is_num = p1.isdigit()
                p2_is_num = p2.isdigit()
                if p1_is_num and p2_is_num:
                    n1, n2 = int(p1), int(p2)
                    if n1 != n2:
                        return -1 if n1 < n2 else 1
                elif p1_is_num and not p2_is_num:
                    return -1
                elif not p1_is_num and p2_is_num:
                    return 1
                else:
                    return -1 if p1 < p2 else 1
            if len(v1.prerelease) != len(v2.prerelease):
                return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        return 0

    def _parse_range_clauses(self, text: str) -> List[List[Tuple[str, semver_solver.Version]]]:
        stripped = text.strip()
        if not stripped:
            raise semver_solver.InvalidRangeError(
                message="Range expression cannot be empty",
                raw_range=text,
            )
        if "," in text:
            raise semver_solver.InvalidRangeError(
                message="Comma delimiters are not permitted in range expressions",
                raw_range=text,
            )

        raw_clauses = text.split("||")
        clauses: List[List[Tuple[str, semver_solver.Version]]] = []
        for raw_c in raw_clauses:
            c = raw_c.strip()
            if not c:
                raise semver_solver.InvalidRangeError(
                    message="Empty union clause in range expression",
                    raw_range=text,
                )
            clauses.append(self._parse_clause(c, text))
        return clauses

    def _parse_clause(self, clause: str, original_text: str) -> List[Tuple[str, semver_solver.Version]]:
        # Hyphen range: M1.m1.p1 - M2.m2.p2
        if " - " in clause:
            parts = clause.split(" - ")
            if len(parts) != 2:
                raise semver_solver.InvalidRangeError(
                    message=f"Malformed hyphen range in: '{clause}'",
                    raw_range=original_text,
                )
            p1_str, p2_str = parts[0].strip(), parts[1].strip()
            try:
                v1 = self.parse_version(p1_str)
                v2 = self.parse_version(p2_str)
            except semver_solver.InvalidVersionError as e:
                raise semver_solver.InvalidRangeError(
                    message=f"Invalid version in hyphen range '{clause}': {e.message}",
                    raw_range=original_text,
                ) from e
            return [(">=", v1), ("<=", v2)]

        tokens = clause.split()
        combined_tokens: List[str] = []
        i = 0
        ops_set = {">=", "<=", "==", "!=", ">", "<", "=", "^", "~"}
        while i < len(tokens):
            tok = tokens[i]
            if tok in ops_set:
                if i + 1 >= len(tokens):
                    raise semver_solver.InvalidRangeError(
                        message=f"Operator '{tok}' missing target version in: '{clause}'",
                        raw_range=original_text,
                    )
                combined_tokens.append(tok + tokens[i + 1])
                i += 2
            else:
                combined_tokens.append(tok)
                i += 1

        comparators: List[Tuple[str, semver_solver.Version]] = []
        for tok in combined_tokens:
            op = None
            target = tok
            if tok.startswith((">=", "<=", "==", "!=")):
                op = tok[:2]
                target = tok[2:]
            elif tok.startswith((">", "<", "=", "^", "~")):
                op = tok[:1]
                target = tok[1:]

            # Wildcard: * or x or X
            if WILDCARD_X_REGEX.match(target):
                comparators.append((">=", semver_solver.Version(0, 0, 0)))
                continue

            # Wildcard: M.x or M.*
            m_mx = WILDCARD_M_X_REGEX.match(target)
            if m_mx:
                major_num = int(m_mx.group(1))
                v_low = semver_solver.Version(major_num, 0, 0)
                v_high = semver_solver.Version(major_num + 1, 0, 0)
                if op in (None, "=", "==", "^", "~"):
                    comparators.append((">=", v_low))
                    comparators.append(("<", v_high))
                elif op == ">=":
                    comparators.append((">=", v_low))
                elif op == ">":
                    comparators.append((">=", v_high))
                elif op == "<=":
                    comparators.append(("<", v_high))
                elif op == "<":
                    comparators.append(("<", v_low))
                continue

            # Wildcard: M.m.x or M.m.*
            m_mmx = WILDCARD_M_M_X_REGEX.match(target)
            if m_mmx:
                major_num = int(m_mmx.group(1))
                minor_num = int(m_mmx.group(2))
                v_low = semver_solver.Version(major_num, minor_num, 0)
                v_high = semver_solver.Version(major_num, minor_num + 1, 0)
                if op in (None, "=", "==", "^", "~"):
                    comparators.append((">=", v_low))
                    comparators.append(("<", v_high))
                elif op == ">=":
                    comparators.append((">=", v_low))
                elif op == ">":
                    comparators.append((">=", v_high))
                elif op == "<=":
                    comparators.append(("<", v_high))
                elif op == "<":
                    comparators.append(("<", v_low))
                continue

            # Full SemVer version target
            try:
                v = self.parse_version(target)
            except semver_solver.InvalidVersionError as e:
                raise semver_solver.InvalidRangeError(
                    message=f"Invalid version or bare partial version in range: '{target}'",
                    raw_range=original_text,
                ) from e

            if op == "^":
                comparators.append((">=", v))
                if v.major > 0:
                    comparators.append(("<", semver_solver.Version(v.major + 1, 0, 0)))
                elif v.minor > 0:
                    comparators.append(("<", semver_solver.Version(0, v.minor + 1, 0)))
                else:
                    comparators.append(("<", semver_solver.Version(0, 0, v.patch + 1)))
            elif op == "~":
                comparators.append((">=", v))
                comparators.append(("<", semver_solver.Version(v.major, v.minor + 1, 0)))
            elif op in (None, "=", "=="):
                comparators.append(("==", v))
            elif op in (">=", ">", "<=", "<", "!="):
                comparators.append((op, v))

        return comparators

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        self._parse_range_clauses(text)
        return semver_solver.VersionRange(raw_text=text.strip())

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        clauses = self._parse_range_clauses(range_constraint.raw_text)
        for clause in clauses:
            if version.is_prerelease and not include_prerelease:
                has_matching_prerelease = any(
                    comp_ver.is_prerelease
                    and (comp_ver.major, comp_ver.minor, comp_ver.patch) == (version.major, version.minor, version.patch)
                    for _, comp_ver in clause
                )
                if not has_matching_prerelease:
                    continue

            clause_satisfied = True
            for op, comp_ver in clause:
                c = self.compare_precedence(version, comp_ver)
                if op == "==":
                    if c != 0:
                        clause_satisfied = False
                        break
                elif op == "!=":
                    if c == 0:
                        clause_satisfied = False
                        break
                elif op == "<":
                    if c >= 0:
                        clause_satisfied = False
                        break
                elif op == "<=":
                    if c > 0:
                        clause_satisfied = False
                        break
                elif op == ">":
                    if c <= 0:
                        clause_satisfied = False
                        break
                elif op == ">=":
                    if c < 0:
                        clause_satisfied = False
                        break
            if clause_satisfied:
                return True
        return False


class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=cmp_to_key(lambda a, b: engine.compare_precedence(b.version, a.version)))

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' not found",
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
                try:
                    available = repo.get_releases(pkg)
                except semver_solver.PackageNotFoundError:
                    available = []
                viable = [
                    rel for rel in available
                    if all(engine.satisfies(rel.version, rng) for _, rng in accumulated_constraints[pkg])
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
                                f"Conflict: '{selected_pkg}' requires {dep.name} {dep.range_constraint.raw_text}"
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
            sorted_conflicts = tuple(sorted(conflicting_packages))
            raise semver_solver.ResolutionConflictError(
                message=f"Failed to resolve dependencies: {explanation}",
                conflicting_packages=sorted_conflicts,
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
# LAST_CLEANED: 2026-10-28T21:39:31Z
# LAST_CHANGED: 2026-10-28T21:39:31Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 7a5109e24358
# COVERAGE_AUDIT: 2026-10-28T21:39:31Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T21:39:31Z
# PRETENSE_QA_AUDIT: 2026-10-28T21:39:31Z
# QA_AUDIT: 2026-10-28T21:39:31Z
# --- END CLEANROOM METADATA ---
