# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_003255_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-11-13T00:32:55.336873+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 233,957
#   Cached Inbound Tokens:   19,799,808
#   Outbound Tokens:         226,710
#   Total Tokens:            20,260,475
#   Financial Cost ($USD):   $0.2305
#   Wall Clock Duration:     1224.23s
#   Step Latencies (s):      [353.2, 546.8, 10.1, 117.3, 64.0, 143.5, 10.0, 147.6, 53.5, 94.5, 20.7, 53.3, 94.3, 10.1, 10.1]
#   Role Execution Rounds:   lib: 3, pretense: 4, pretense_coverage: 4, pretense_qa: 4 (Total: 15)
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
"""Semantic version parsing, precedence comparison, and dependency resolution interfaces."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base failure for semantic versioning and dependency resolution."""

    message: str

    def __str__(self) -> str:
        """Returns the diagnostic message."""
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when a version string violates the semantic version grammar."""

    raw_text: str


@dataclass
class InvalidRangeError(SemVerError):
    """Raised when a range expression is malformed."""

    raw_range: str


@dataclass
class ResolutionConflictError(SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually."""

    conflicting_packages: Tuple[str, ...]
    explanation: str


@dataclass
class PackageNotFoundError(SemVerError):
    """Raised when a package name is absent from the repository."""

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
    """Immutable semantic version conforming to SemVer 2.0.0."""

    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        """Indicates whether this version carries pre-release identifiers."""
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into its canonical SemVer 2.0.0 text."""
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        """Returns the canonical SemVer text representation."""
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        """Returns the raw text of the range expression."""
        return self.raw_text


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement on an external package and version range."""

    name: str
    range_constraint: VersionRange


@data_type
@dataclass(frozen=True)
class PackageRelease:
    """Publication record of a package at a specific semantic version."""

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
        """Parses a version range expression into an immutable record."""
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
        """Retrieves registered releases for a package ordered by descending precedence."""
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
# LAST_CLEANED: 2026-11-13T00:38:33Z
# LAST_CHANGED: 2026-11-13T00:38:33Z
# CHANGE: Implemented interface data types and service protocols: SemVer 2.0.0 Version formatting/prerelease access, VersionRange/PackageDependency/PackageRelease/ResolutionOutcome records, ComparatorOp enum, lifecycle errors with diagnostic __str__, and abstract VersionEngine/PackageRepository/DependencySolver protocols matching the low specification.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete SemVer engine, package repository, and dependency solver implementations."""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import semver_solver


_VERSION_RE = re.compile(
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)

# A comparator target is either a full semantic version or a wildcard expression.
_TARGET_PATTERN = r"[0-9A-Za-z.*+xX-]+"

_COMPARATOR_RE = re.compile(
    r"(?:(?P<op>\^|~|>=|<=|==|!=|=|>|<)\s*)?(?P<target>" + _TARGET_PATTERN + r")"
)

_HYPHEN_RANGE_RE = re.compile(
    r"(?P<lower>" + _TARGET_PATTERN + r")\s+-\s+(?P<upper>" + _TARGET_PATTERN + r")"
)

_WILDCARD_COMPONENTS = ("*", "x", "X")

# A target is an exact version or the components of a wildcard expression.
_Target = Tuple[Optional[semver_solver.Version], Tuple[Optional[int], ...]]
# A primitive inequality over a concrete version boundary.
_Comparator = Tuple[str, semver_solver.Version]
# A conjunction of primitive inequalities, where alternatives form a disjunction.
_Alternative = List[_Comparator]


def _invalid_range(text: str, detail: str) -> semver_solver.InvalidRangeError:
    """Builds a diagnostic error for a malformed range expression."""
    return semver_solver.InvalidRangeError(
        f"invalid version range {text!r}: {detail}", raw_range=text
    )


def _literal_version(text: str) -> Optional[semver_solver.Version]:
    """Parses a complete semantic version, rejecting grammar and leading zero violations."""
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        return None
    prerelease_text = match.group("prerelease")
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    for identifier in prerelease:
        # Numeric pre-release identifiers must not carry leading zeroes.
        if (
            identifier.isascii()
            and identifier.isdigit()
            and len(identifier) > 1
            and identifier.startswith("0")
        ):
            return None
    build_text = match.group("build")
    build = tuple(build_text.split(".")) if build_text else ()
    return semver_solver.Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=prerelease,
        build=build,
    )


def _wildcard_lower(components: Tuple[Optional[int], ...]) -> semver_solver.Version:
    """Computes the inclusive lower bound of a wildcard expression."""
    wildcard_index = next(index for index, value in enumerate(components) if value is None)
    major = components[0] or 0
    minor = components[1] or 0
    if wildcard_index == 0:
        return semver_solver.Version(0, 0, 0)
    if wildcard_index == 1:
        return semver_solver.Version(major, 0, 0)
    return semver_solver.Version(major, minor, 0)


def _wildcard_upper(components: Tuple[Optional[int], ...]) -> Optional[semver_solver.Version]:
    """Computes the exclusive upper bound of a wildcard expression."""
    wildcard_index = next(index for index, value in enumerate(components) if value is None)
    major = components[0] or 0
    minor = components[1] or 0
    if wildcard_index == 0:
        return None
    if wildcard_index == 1:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _caret_upper(target: _Target) -> Optional[semver_solver.Version]:
    """Computes the exclusive upper bound of a caret range from its first non-zero component."""
    version, components = target
    if version is not None:
        if version.major > 0:
            return semver_solver.Version(version.major + 1, 0, 0)
        if version.minor > 0:
            return semver_solver.Version(0, version.minor + 1, 0)
        return semver_solver.Version(0, 0, version.patch + 1)
    major = components[0]
    if major is None:
        # All-wildcard caret expressions are intercepted before bound construction.
        with unreachable:
            return None
    if major > 0:
        return semver_solver.Version(major + 1, 0, 0)
    minor = components[1]
    if minor is None:
        return semver_solver.Version(0, 1, 0)
    if minor > 0:
        return semver_solver.Version(0, minor + 1, 0)
    patch = components[2]
    if patch is None:
        return semver_solver.Version(0, 0, 1)
    # Wildcard grammar leaves the trailing patch component wildcard, so it is never present.
    with unreachable:
        return semver_solver.Version(0, 0, patch + 1)


def _tilde_upper(target: _Target) -> Optional[semver_solver.Version]:
    """Computes the exclusive upper bound of a tilde range at the minor boundary."""
    version, components = target
    if version is not None:
        return semver_solver.Version(version.major, version.minor + 1, 0)
    major = components[0]
    if major is None:
        # All-wildcard tilde expressions are intercepted before bound construction.
        with unreachable:
            return None
    minor = components[1]
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _parse_range_target(token: str, text: str) -> _Target:
    """Parses a comparator target as a full version or a wildcard expression."""
    version = _literal_version(token)
    if version is not None:
        return version, ()
    if "+" in token or "-" in token:
        raise _invalid_range(text, f"malformed comparator target {token!r}")
    parts = token.split(".")
    if not 1 <= len(parts) <= 3:
        raise _invalid_range(text, f"malformed comparator target {token!r}")
    components: List[Optional[int]] = []
    wildcard_seen = False
    for part in parts:
        if part in _WILDCARD_COMPONENTS:
            wildcard_seen = True
            components.append(None)
            continue
        if wildcard_seen:
            raise _invalid_range(text, f"malformed wildcard expression {token!r}")
        if not (part.isascii() and part.isdigit()):
            raise _invalid_range(text, f"malformed comparator target {token!r}")
        if len(part) > 1 and part.startswith("0"):
            raise _invalid_range(text, f"comparator target {token!r} carries a leading zero")
        components.append(int(part))
    if not wildcard_seen:
        raise _invalid_range(text, f"bare partial version {token!r} requires a wildcard")
    while len(components) < 3:
        components.append(None)
    return None, tuple(components)


def _interval(
    lower: semver_solver.Version,
    upper: Optional[semver_solver.Version],
) -> List[_Alternative]:
    """Builds the inclusive lower and exclusive upper bounds of an interval."""
    if upper is None:
        # Unbounded expressions are guarded by callers, so this open-ended interval is unreachable.
        with unreachable:
            return [[(">=", lower)]]
    return [[(">=", lower), ("<", upper)]]


def _expand_comparator(op: str, target: _Target, text: str) -> List[_Alternative]:
    """Translates one comparator into alternative conjunctions of primitive inequalities."""
    version, components = target
    if version is not None:
        if op in ("", "=", "=="):
            return [[(">=", version), ("<=", version)]]
        if op == "!=":
            return [[("<", version)], [(">", version)]]
        if op == ">":
            return [[(">", version)]]
        if op == ">=":
            return [[(">=", version)]]
        if op == "<":
            return [[("<", version)]]
        if op == "<=":
            return [[("<=", version)]]
        if op == "^":
            return _interval(version, _caret_upper(target))
        # Tilde ranges keep the lower bound but pin the minor boundary.
        return _interval(version, _tilde_upper(target))
    lower = _wildcard_lower(components)
    upper = _wildcard_upper(components)
    # An expression that leaves the leading component wildcard spans every version.
    if op in ("", "=", "=="):
        if upper is None:
            return [[]]
        return _interval(lower, upper)
    if op == "!=":
        if upper is None:
            return []
        return [[("<", lower)], [(">=", upper)]]
    if op == ">":
        if upper is None:
            return []
        return [[(">=", upper)]]
    if op == ">=":
        if components[0] is None:
            return [[]]
        return [[(">=", lower)]]
    if op == "<":
        if components[0] is None:
            return []
        return [[("<", lower)]]
    if op == "<=":
        if upper is None:
            return [[]]
        return [[("<", upper)]]
    if op == "^":
        if components[0] is None:
            return [[]]
        return _interval(lower, _caret_upper(target))
    if components[0] is None:
        return [[]]
    return _interval(lower, _tilde_upper(target))


def _parse_clause(clause: str, text: str) -> List[_Alternative]:
    """Compiles one clause into alternative conjunctions of primitive inequalities."""
    hyphen = _HYPHEN_RANGE_RE.fullmatch(clause)
    if hyphen is not None:
        lower_target = _parse_range_target(hyphen.group("lower"), text)
        upper_target = _parse_range_target(hyphen.group("upper"), text)
        comparators: List[_Comparator] = []
        lower_version = lower_target[0]
        if lower_version is not None:
            comparators.append((">=", lower_version))
        else:
            comparators.append((">=", _wildcard_lower(lower_target[1])))
        upper_version = upper_target[0]
        if upper_version is not None:
            comparators.append(("<=", upper_version))
        else:
            upper_bound = _wildcard_upper(upper_target[1])
            if upper_bound is not None:
                comparators.append(("<", upper_bound))
        return [comparators]
    alternatives: List[_Alternative] = [[]]
    position = 0
    matched_any = False
    for match in _COMPARATOR_RE.finditer(clause):
        if matched_any and match.start() == position:
            # Comparators must be delimited by whitespace, never concatenated.
            raise _invalid_range(text, f"comparators are not whitespace separated in {clause!r}")
        gap = clause[position:match.start()]
        if gap.strip():
            raise _invalid_range(text, f"unrecognized range syntax in {clause!r}")
        position = match.end()
        matched_any = True
        op = match.group("op") or ""
        target = _parse_range_target(match.group("target"), text)
        fragment = _expand_comparator(op, target, text)
        if not fragment:
            alternatives = []
            continue
        combined: List[_Alternative] = []
        for existing in alternatives:
            for addition in fragment:
                combined.append(existing + addition)
        alternatives = combined
    if clause[position:].strip():
        raise _invalid_range(text, f"unrecognized range syntax in {clause!r}")
    if not matched_any:
        # Clauses are never empty here: emptiness is rejected before compilation.
        with unreachable:
            raise _invalid_range(text, f"empty range clause in {text!r}")
    return alternatives


def _compile_range(text: str) -> List[_Alternative]:
    """Compiles a range expression into disjunctive normal form comparator sets."""
    stripped = text.strip()
    if not stripped:
        raise _invalid_range(text, "empty range expression")
    if "," in stripped:
        raise _invalid_range(text, "comma delimiters are not permitted")
    alternatives: List[_Alternative] = []
    for part in stripped.split("||"):
        clause = part.strip()
        if not clause:
            raise _invalid_range(text, "empty union clause")
        alternatives.extend(_parse_clause(clause, text))
    return alternatives


def _compare_identifier(left: str, right: str) -> int:
    """Compares two pre-release identifiers under SemVer precedence rules."""
    left_numeric = left.isascii() and left.isdigit()
    right_numeric = right.isascii() and right.isdigit()
    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        if left_value == right_value:
            return 0
        return -1 if left_value < right_value else 1
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    if left == right:
        return 0
    return -1 if left < right else 1


@singleton
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range matching."""

    tier = "system"

    def parse_version(self, text: str) -> semver_solver.Version:
        version = _literal_version(text)
        if version is None:
            # Grammar violations and leading zeroes in numeric identifiers are rejected.
            raise semver_solver.InvalidVersionError(
                f"invalid semantic version {text!r}", raw_text=text
            )
        return version

    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        # Core numeric components dominate precedence ordering.
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1
        # Build metadata never participates in precedence; only pre-release identifiers do.
        left = v1.prerelease
        right = v2.prerelease
        if not left and not right:
            return 0
        if not left:
            return 1
        if not right:
            return -1
        for left_identifier, right_identifier in zip(left, right):
            ordering = _compare_identifier(left_identifier, right_identifier)
            if ordering != 0:
                return ordering
        if len(left) == len(right):
            return 0
        return -1 if len(left) < len(right) else 1

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Validate the expression before recording its trimmed text.
        _compile_range(text)
        return semver_solver.VersionRange(raw_text=text.strip())

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        alternatives = _compile_range(range_constraint.raw_text)
        for comparators in alternatives:
            if self._matches(version, comparators, include_prerelease):
                return True
        return False

    def _matches(
        self,
        version: semver_solver.Version,
        comparators: List[_Comparator],
        include_prerelease: bool,
    ) -> bool:
        # Pre-releases only match ranges that name their exact numeric triple.
        if version.is_prerelease and not include_prerelease:
            triple = (version.major, version.minor, version.patch)
            targeted = any(
                boundary.is_prerelease
                and (boundary.major, boundary.minor, boundary.patch) == triple
                for _, boundary in comparators
            )
            if not targeted:
                return False
        for op, boundary in comparators:
            ordering = self.compare_precedence(version, boundary)
            if op == ">=" and ordering < 0:
                return False
            if op == ">" and ordering <= 0:
                return False
            if op == "<=" and ordering > 0:
                return False
            if op == "<" and ordering >= 0:
                return False
        return True


@singleton
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = "system"

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)

        # Keep each release history ordered by descending version precedence.
        def descending(left: semver_solver.PackageRelease, right: semver_solver.PackageRelease) -> int:
            return engine.compare_precedence(right.version, left.version)

        releases.sort(key=cmp_to_key(descending))

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                f"package {name!r} is not registered", package_name=name
            )
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        return name in self._packages

    def all_packages(self) -> Set[str]:
        return set(self._packages.keys())


@singleton
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking dependency solver."""

    tier = "system"

    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to the ranges required of it.
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(package: str) -> List[semver_solver.PackageRelease]:
            try:
                available = repository.get_releases(package)
            except semver_solver.PackageNotFoundError:
                # Unregistered packages contribute no candidates and surface as conflicts.
                return []
            return [
                release
                for release in available
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated[package]
                )
            ]

        def backtrack() -> bool:
            unassigned = [package for package in accumulated if package not in assignment]
            if not unassigned:
                return True
            candidates = {package: viable_releases(package) for package in unassigned}
            # Minimum Remaining Values selection with lexical tie-breaking.
            selected = min(unassigned, key=lambda package: (len(candidates[package]), package))
            if not candidates[selected]:
                requesters = sorted(
                    {source for source, _ in accumulated[selected] if source != "root"}
                )
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"no viable releases for '{selected}' satisfying requirements from {requesters or ['root']}"
                )
                return False
            for candidate in candidates[selected]:
                assignment[selected] = candidate
                derivation_steps.append(
                    f"assign '{selected}' to {candidate.version.format()}"
                )
                added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                conflict = False
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # Existing assignments are forward checked against new requirements.
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"'{selected}' requires '{dependency.name}' "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                        continue
                    entry = (selected, dependency.range_constraint)
                    accumulated.setdefault(dependency.name, []).append(entry)
                    added.append((dependency.name, entry))
                if not conflict and backtrack():
                    return True
                # Undo the candidate assignment together with every requirement it introduced.
                for package, entry in added:
                    accumulated[package].remove(entry)
                    if not accumulated[package]:
                        del accumulated[package]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if backtrack():
            selected_versions = {
                package: release.version for package, release in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )
        explanation = (
            "; ".join(conflict_trail)
            if conflict_trail
            else "no compatible release assignment exists"
        )
        raise semver_solver.ResolutionConflictError(
            f"dependency resolution failed: {explanation}",
            conflicting_packages=tuple(sorted(conflicting_packages)),
            explanation=explanation,
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:53:16Z
# LAST_CHANGED: 2026-11-13T00:49:45Z
# CHANGE: Quarantined the remaining statically-unreachable branches flagged by pretense_coverage while preserving their logic as tripwires: the all-wildcard caret and tilde major-None guards in _caret_upper/_tilde_upper (callers intercept all-wildcard expressions before bound construction), the caret patch-present fallback (wildcard grammar always leaves the trailing patch component wildcard), and the duplicate empty-clause guard in _parse_clause (emptiness is rejected before compilation). Static checks pass.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:53:16Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:53:03Z
# --- END AUTOFAB METADATA ---
