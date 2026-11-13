# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_044023_gemini-flash_semver_solver_pretense
# Timestamp: 2026-11-13T04:40:23.430316+00:00
# Benchmark Task: semver_solver
# Model: gemini-flash (Tier 2)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 1,475,993
#   Cached Inbound Tokens:   30,778,269
#   Outbound Tokens:         298,715
#   Total Tokens:            32,552,977
#   Financial Cost ($USD):   $1.0365
#   Wall Clock Duration:     2570.83s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 5, pretense: 7, pretense_coverage: 7, pretense_qa: 8 (Total: 27)
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
"""Library interface defining SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

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
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            result = f"{result}-{'.'.join(self.prerelease)}"
        if self.build:
            result = f"{result}+{'.'.join(self.build)}"
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
# LAST_CLEANED: 2026-11-13T04:50:01Z
# LAST_CHANGED: 2026-11-13T04:50:01Z
# CHANGE: Initial implementation of SemVer 2.0 interface contracts, exceptions, value objects, and service protocols
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Library implementation of SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key
import itertools
import re
from typing import (
    Collection,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton
from . import semver_solver

_NUMERIC_ID = r"(?:0|[1-9]\d*)"
_NON_NUMERIC_ID = r"(?:\d*[a-zA-Z-][0-9a-zA-Z-]*)"
_PRERELEASE_ID = rf"(?:{_NUMERIC_ID}|{_NON_NUMERIC_ID})"
_PRERELEASE_PART = rf"(?:-(?P<prerelease>{_PRERELEASE_ID}(?:\.{_PRERELEASE_ID})*))"
_BUILD_ID = r"[0-9a-zA-Z-]+"
_BUILD_PART = rf"(?:\+(?P<build>{_BUILD_ID}(?:\.{_BUILD_ID})*))"
_VERSION_REGEX = re.compile(
    rf"^(?P<major>{_NUMERIC_ID})\.(?P<minor>{_NUMERIC_ID})\.(?P<patch>{_NUMERIC_ID}){_PRERELEASE_PART}?{_BUILD_PART}?$"
)

_RE_STAR = re.compile(r"^[*xX]$")
_RE_MAJOR_STAR = re.compile(r"^(?P<major>0|[1-9]\d*)\.[*xX]$")
_RE_MINOR_STAR = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.[*xX]$")
_RE_BARE_PARTIAL = re.compile(r"^(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*))?$")
_RE_OP = re.compile(r"^(==|!=|<=|>=|=|<|>|\^|~)\s*")


@dataclass(frozen=True)
class _SimpleComparator:
    op: str
    target: semver_solver.Version
    impossible: bool = False
    matches_all_non_prerelease: bool = False

    def check(self, candidate: semver_solver.Version, engine: semver_solver.VersionEngine) -> bool:
        if self.impossible:
            return False
        if self.matches_all_non_prerelease:
            return True
        cmp = engine.compare_precedence(candidate, self.target)
        if self.op == "==":
            return cmp == 0
        elif self.op == "!=":
            return cmp != 0
        elif self.op == "<":
            return cmp < 0
        elif self.op == "<=":
            return cmp <= 0
        elif self.op == ">":
            return cmp > 0
        elif self.op == ">=":
            return cmp >= 0
        with unreachable:
            return False


@dataclass(frozen=True)
class _Clause:
    comparators: Tuple[_SimpleComparator, ...]

    def satisfies(
        self,
        candidate: semver_solver.Version,
        include_prerelease: bool,
        engine: semver_solver.VersionEngine,
    ) -> bool:
        if candidate.is_prerelease and not include_prerelease:
            targeted = any(
                comp.target.is_prerelease
                and (comp.target.major, comp.target.minor, comp.target.patch)
                == (candidate.major, candidate.minor, candidate.patch)
                for comp in self.comparators
                if not comp.matches_all_non_prerelease and not comp.impossible
            )
            if not targeted:
                return False

        for comp in self.comparators:
            if not comp.check(candidate, engine):
                return False
        return True


def _expand_comparator(
    op: str, target_str: str, raw_range: str, engine: semver_solver.VersionEngine
) -> List[List[_SimpleComparator]]:
    if _RE_BARE_PARTIAL.match(target_str):
        raise semver_solver.InvalidRangeError(
            f"Bare partial versions lacking wildcards are prohibited: {target_str}",
            raw_range=raw_range,
        )

    if _RE_STAR.match(target_str):
        if op in {"", "=", "==", ">=", "<=", "^", "~"}:
            return [
                [
                    _SimpleComparator(
                        ">=",
                        semver_solver.Version(0, 0, 0),
                        matches_all_non_prerelease=True,
                    )
                ]
            ]
        elif op in {"<", ">", "!="}:
            return [
                [
                    _SimpleComparator(
                        "<", semver_solver.Version(0, 0, 0), impossible=True
                    )
                ]
            ]
        else:
            with unreachable:
                raise semver_solver.InvalidRangeError(
                    f"Unsupported operator: {op}", raw_range=raw_range
                )

    match = _RE_MAJOR_STAR.match(target_str)
    if match:
        major = int(match.group("major"))
        lower = semver_solver.Version(major, 0, 0)
        upper = semver_solver.Version(major + 1, 0, 0)
        if op in {"", "=", "==", "^", "~"}:
            return [[_SimpleComparator(">=", lower), _SimpleComparator("<", upper)]]
        elif op == ">=":
            return [[_SimpleComparator(">=", lower)]]
        elif op == "<=":
            return [[_SimpleComparator("<", upper)]]
        elif op == ">":
            return [[_SimpleComparator(">=", upper)]]
        elif op == "<":
            return [[_SimpleComparator("<", lower)]]
        elif op == "!=":
            return [[_SimpleComparator("<", lower)], [_SimpleComparator(">=", upper)]]
        else:
            with unreachable:
                raise semver_solver.InvalidRangeError(
                    f"Unsupported operator: {op}", raw_range=raw_range
                )

    match = _RE_MINOR_STAR.match(target_str)
    if match:
        major = int(match.group("major"))
        minor = int(match.group("minor"))
        lower = semver_solver.Version(major, minor, 0)
        upper = semver_solver.Version(major, minor + 1, 0)
        if op in {"", "=", "==", "~"}:
            return [[_SimpleComparator(">=", lower), _SimpleComparator("<", upper)]]
        elif op == "^":
            if major > 0:
                caret_upper = semver_solver.Version(major + 1, 0, 0)
            elif minor > 0:
                caret_upper = semver_solver.Version(0, minor + 1, 0)
            else:
                caret_upper = semver_solver.Version(0, 1, 0)
            return [[_SimpleComparator(">=", lower), _SimpleComparator("<", caret_upper)]]
        elif op == ">=":
            return [[_SimpleComparator(">=", lower)]]
        elif op == "<=":
            return [[_SimpleComparator("<", upper)]]
        elif op == ">":
            return [[_SimpleComparator(">=", upper)]]
        elif op == "<":
            return [[_SimpleComparator("<", lower)]]
        elif op == "!=":
            return [[_SimpleComparator("<", lower)], [_SimpleComparator(">=", upper)]]
        else:
            with unreachable:
                raise semver_solver.InvalidRangeError(
                    f"Unsupported operator: {op}", raw_range=raw_range
                )

    try:
        v = engine.parse_version(target_str)
    except semver_solver.InvalidVersionError:
        raise semver_solver.InvalidRangeError(
            f"Invalid version syntax in range: {target_str}", raw_range=raw_range
        )

    if op in {"", "=", "=="}:
        return [[_SimpleComparator("==", v)]]
    elif op == "!=":
        return [[_SimpleComparator("!=", v)]]
    elif op in {"<", "<=", ">", ">="}:
        return [[_SimpleComparator(op, v)]]
    elif op == "^":
        if v.major > 0:
            upper = semver_solver.Version(v.major + 1, 0, 0)
        elif v.minor > 0:
            upper = semver_solver.Version(0, v.minor + 1, 0)
        else:
            upper = semver_solver.Version(0, 0, v.patch + 1)
        return [[_SimpleComparator(">=", v), _SimpleComparator("<", upper)]]
    elif op == "~":
        upper = semver_solver.Version(v.major, v.minor + 1, 0)
        return [[_SimpleComparator(">=", v), _SimpleComparator("<", upper)]]
    else:
        with unreachable:
            raise semver_solver.InvalidRangeError(
                f"Unsupported operator: {op}", raw_range=raw_range
            )


def _expand_hyphen_range(
    bound1_str: str,
    bound2_str: str,
    raw_range: str,
    engine: semver_solver.VersionEngine,
) -> List[_SimpleComparator]:
    if _RE_BARE_PARTIAL.match(bound1_str) or _RE_BARE_PARTIAL.match(bound2_str):
        raise semver_solver.InvalidRangeError(
            "Bare partial versions lacking wildcards are prohibited in hyphen range",
            raw_range=raw_range,
        )

    if _RE_STAR.match(bound1_str):
        lower_comp = _SimpleComparator(
            ">=", semver_solver.Version(0, 0, 0), matches_all_non_prerelease=True
        )
    elif match1 := _RE_MAJOR_STAR.match(bound1_str):
        major1 = int(match1.group("major"))
        lower_comp = _SimpleComparator(">=", semver_solver.Version(major1, 0, 0))
    elif match1 := _RE_MINOR_STAR.match(bound1_str):
        major1 = int(match1.group("major"))
        minor1 = int(match1.group("minor"))
        lower_comp = _SimpleComparator(">=", semver_solver.Version(major1, minor1, 0))
    else:
        try:
            v1 = engine.parse_version(bound1_str)
            lower_comp = _SimpleComparator(">=", v1)
        except semver_solver.InvalidVersionError:
            raise semver_solver.InvalidRangeError(
                f"Invalid version bound in hyphen range: {bound1_str}",
                raw_range=raw_range,
            )

    upper_comp: Optional[_SimpleComparator] = None
    if _RE_STAR.match(bound2_str):
        upper_comp = None
    elif match2 := _RE_MAJOR_STAR.match(bound2_str):
        major2 = int(match2.group("major"))
        upper_comp = _SimpleComparator("<", semver_solver.Version(major2 + 1, 0, 0))
    elif match2 := _RE_MINOR_STAR.match(bound2_str):
        major2 = int(match2.group("major"))
        minor2 = int(match2.group("minor"))
        upper_comp = _SimpleComparator("<", semver_solver.Version(major2, minor2 + 1, 0))
    else:
        try:
            v2 = engine.parse_version(bound2_str)
            upper_comp = _SimpleComparator("<=", v2)
        except semver_solver.InvalidVersionError:
            raise semver_solver.InvalidRangeError(
                f"Invalid version bound in hyphen range: {bound2_str}",
                raw_range=raw_range,
            )

    comps = [lower_comp]
    if upper_comp is not None:
        comps.append(upper_comp)
    return comps


def _compile_clause(
    clause_str: str, raw_range: str, engine: semver_solver.VersionEngine
) -> List[_Clause]:
    if re.search(r"\s+-\s+", clause_str):
        parts = re.split(r"\s+-\s+", clause_str.strip())
        if len(parts) != 2:
            raise semver_solver.InvalidRangeError(
                "Invalid hyphen range syntax", raw_range=raw_range
            )
        b1, b2 = parts[0].strip(), parts[1].strip()
        if " " in b1 or " " in b2:
            raise semver_solver.InvalidRangeError(
                "Whitespace not permitted within hyphen range bounds",
                raw_range=raw_range,
            )
        if _RE_OP.match(b1) or _RE_OP.match(b2):
            raise semver_solver.InvalidRangeError(
                "Operators not permitted in hyphen range bounds", raw_range=raw_range
            )
        comps = _expand_hyphen_range(b1, b2, raw_range, engine)
        return [_Clause(tuple(comps))]

    items: List[List[List[_SimpleComparator]]] = []
    i = 0
    n = len(clause_str)
    while i < n:
        while i < n and clause_str[i].isspace():
            i += 1
        if i >= n:
            with unreachable:
                break
        op_match = _RE_OP.match(clause_str[i:])
        if op_match:
            op = op_match.group(1)
            i += op_match.end()
            if i >= n or clause_str[i].isspace():
                raise semver_solver.InvalidRangeError(
                    f"Operator '{op}' missing target version", raw_range=raw_range
                )
            target_start = i
            while i < n and not clause_str[i].isspace():
                i += 1
            target_str = clause_str[target_start:i]
        else:
            op = ""
            target_start = i
            while i < n and not clause_str[i].isspace():
                i += 1
            target_str = clause_str[target_start:i]

        alt_lists = _expand_comparator(op, target_str, raw_range, engine)
        items.append(alt_lists)

    if not items:
        with unreachable:
            raise semver_solver.InvalidRangeError(
                "Empty clause in range", raw_range=raw_range
            )

    clauses: List[_Clause] = []
    for combo in itertools.product(*items):
        flat_comps: List[_SimpleComparator] = []
        for comp_list in combo:
            flat_comps.extend(comp_list)
        clauses.append(_Clause(tuple(flat_comps)))
    return clauses


@singleton
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = "system"

    def __init__(self) -> None:
        self._range_cache: Dict[str, List[_Clause]] = {}

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        match = _VERSION_REGEX.match(text)
        if not match:
            raise semver_solver.InvalidVersionError(
                f"Version string violates SemVer 2.0.0 grammar: {text}",
                raw_text=text,
            )

        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))

        prerelease_str = match.group("prerelease")
        prerelease = tuple(prerelease_str.split(".")) if prerelease_str else ()

        build_str = match.group("build")
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
                if id1 != id2:
                    return -1 if id1 < id2 else 1

        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

        return 0

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        if not isinstance(text, str) or not text.strip():
            raise semver_solver.InvalidRangeError(
                "Version range text cannot be empty or whitespace",
                raw_range=text if isinstance(text, str) else "",
            )

        if "," in text:
            raise semver_solver.InvalidRangeError(
                "Comma delimiters are not permitted in version ranges",
                raw_range=text,
            )

        raw_clauses = text.split("||")
        if any(not c.strip() for c in raw_clauses):
            raise semver_solver.InvalidRangeError(
                "Empty union clauses separated by '||' are not permitted",
                raw_range=text,
            )

        trimmed_clauses = [c.strip() for c in raw_clauses]
        trimmed_range = " || ".join(trimmed_clauses)

        compiled_clauses: List[_Clause] = []
        for c in trimmed_clauses:
            compiled = _compile_clause(c, text, self)
            compiled_clauses.extend(compiled)

        self._range_cache[trimmed_range] = compiled_clauses
        return semver_solver.VersionRange(trimmed_range)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        raw_text = range_constraint.raw_text
        if raw_text not in self._range_cache:
            self.parse_range(raw_text)

        clauses = self._range_cache[raw_text]
        return any(
            clause.satisfies(version, include_prerelease, self)
            for clause in clauses
        )


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

        for i, existing in enumerate(releases):
            if existing.version == release.version:
                releases[i] = release
                break
        else:
            releases.append(release)

        def comp(r1: semver_solver.PackageRelease, r2: semver_solver.PackageRelease) -> int:
            return engine.compare_precedence(r1.version, r2.version)

        releases.sort(key=cmp_to_key(comp), reverse=True)

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository.",
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
        version_engine = get_singleton(semver_solver.VersionEngine)
        package_repo = get_singleton(semver_solver.PackageRepository)

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
                    available = package_repo.get_releases(pkg)
                except semver_solver.PackageNotFoundError:
                    available = []
                viable = [
                    rel
                    for rel in available
                    if all(
                        version_engine.satisfies(rel.version, rng, False)
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
                derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version.format()}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        if not version_engine.satisfies(
                            assignment[dep.name].version, dep.range_constraint, False
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
        if not success:
            explanation = "\n".join(conflict_trail)
            sorted_conflicts = tuple(sorted(conflicting_packages))
            raise semver_solver.ResolutionConflictError(
                f"Failed to resolve dependencies: {explanation}",
                conflicting_packages=sorted_conflicts,
                explanation=explanation,
            )

        selected_versions = {pkg: rel.version for pkg, rel in assignment.items()}
        return semver_solver.ResolutionOutcome(
            selected_versions=selected_versions,
            derivation_steps=tuple(derivation_steps),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T05:23:11Z
# LAST_CHANGED: 2026-11-13T05:22:10Z
# CHANGE: Quarantine unreachable trailing whitespace break guard in _compile_clause using with unreachable
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T05:23:11Z
# PRETENSE_QA_AUDIT: 2026-11-13T05:22:46Z
# --- END AUTOFAB METADATA ---
