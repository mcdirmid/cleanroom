# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261107_030345_deepseek-flash_semver_solver_baseline
# Timestamp: 2026-11-07T03:03:45.011785+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 47,002
#   Cached Inbound Tokens:   2,482,560
#   Outbound Tokens:         69,234
#   Total Tokens:            2,598,796
#   Financial Cost ($USD):   $0.0560
#   Wall Clock Duration:     453.34s
#   Step Latencies (s):      [444.1]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       28
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum

from support.lib.framework import data_type, operation, poly_type

# Requirements specified in semver_solver.pyi


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

    EQ = '=='
    NE = '!='
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='


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
        # POSTCONDITION: prerelease identifiers present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # POSTCONDITION: canonical SemVer 2.0.0 string representation.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += "-" + ".".join(self.prerelease)
        if self.build:
            text += "+" + ".".join(self.build)
        return text

    def __str__(self) -> str:
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
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
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        ...

    @operation
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        ...


@poly_type
class PackageRepository(Protocol):
    """Maintains indexed package publications and release histories."""

    @operation
    def register_package(self, release: PackageRelease) -> None:
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        ...

    @operation
    def has_package(self, name: str) -> bool:
        ...

    @operation
    def all_packages(self) -> Set[str]:
        ...


@poly_type
class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    @operation
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:11:18Z
# LAST_CHANGED: 2026-11-07T03:11:18Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 6d9953bd31e1
# COVERAGE_AUDIT: 2026-11-07T03:11:18Z
# QA_AUDIT: 2026-11-07T03:11:18Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_solver
import re

# Requirements specified in semver_solver_impl.pyi

# SemVer 2.0.0 grammar: numeric identifiers without leading zeroes, optional
# dot-separated pre-release identifiers, and optional dot-separated build metadata.
_VERSION_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
_PRERELEASE_RE = re.compile(
    r"(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*"
)
_BUILD_RE = re.compile(r"[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*")
_NUMERIC_RE = re.compile(r"[0-9]+")
_HYPHEN_RE = re.compile(r"([^\s]+)\s+-\s+([^\s]+)")
_OPERATORS = ("<=", ">=", "==", "!=", "=", "<", ">", "^", "~")
_WILDCARDS = ("*", "x", "X")

# A parsed version token: (major, minor, patch, prerelease).  A missing
# component (None) marks the trailing wildcard position of a range token.
_VersionSpec = Tuple[Optional[int], Optional[int], Optional[int], Tuple[str, ...]]
# A single comparable bound: (operator, boundary version).
_Comparator = Tuple["semver_solver.ComparatorOp", "semver_solver.Version"]
# Disjunctive normal form: alternatives of conjunctions of comparators.
_Alternatives = List[List["_Comparator"]]


def _invalid_range(raw: str) -> semver_solver.InvalidRangeError:
    return semver_solver.InvalidRangeError(f"Invalid version range: {raw}", raw)


def _parse_spec(token: str, raw: str) -> _VersionSpec:
    text = token
    prerelease: Tuple[str, ...] = ()
    has_build = False
    if "+" in text:
        text, build_text = text.split("+", 1)
        has_build = True
        if _BUILD_RE.fullmatch(build_text) is None:
            raise _invalid_range(raw)
    if "-" in text:
        text, prerelease_text = text.split("-", 1)
        if _PRERELEASE_RE.fullmatch(prerelease_text) is None:
            raise _invalid_range(raw)
        prerelease = tuple(prerelease_text.split("."))
    parts = text.split(".")
    if len(parts) > 3:
        raise _invalid_range(raw)
    values: List[Optional[int]] = []
    wildcard_seen = False
    for part in parts:
        if part in _WILDCARDS:
            if wildcard_seen:
                raise _invalid_range(raw)
            wildcard_seen = True
            values.append(None)
        else:
            if wildcard_seen:
                raise _invalid_range(raw)
            if _NUMERIC_RE.fullmatch(part) is None or (len(part) > 1 and part.startswith("0")):
                raise _invalid_range(raw)
            values.append(int(part))
    # Full versions require all three numeric components; wildcards stand in
    # for any trailing components and must not be combined with metadata.
    if not wildcard_seen and len(parts) != 3:
        raise _invalid_range(raw)
    if wildcard_seen and (prerelease or has_build):
        raise _invalid_range(raw)
    major = values[0]
    minor = values[1] if len(values) > 1 else None
    patch = values[2] if len(values) > 2 else None
    return (major, minor, patch, prerelease)


def _is_full(spec: _VersionSpec) -> bool:
    major, minor, patch, _ = spec
    return major is not None and minor is not None and patch is not None


def _spec_lower(spec: _VersionSpec) -> semver_solver.Version:
    major, minor, patch, prerelease = spec
    return semver_solver.Version(major or 0, minor or 0, patch or 0, prerelease)


def _spec_upper(spec: _VersionSpec) -> Optional[semver_solver.Version]:
    major, minor, patch, _ = spec
    if major is None:
        return None
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    if patch is None:
        return semver_solver.Version(major, minor + 1, 0)
    raise AssertionError(f"full version has no wildcard upper bound: {spec}")


def _caret_upper(spec: _VersionSpec) -> Optional[semver_solver.Version]:
    major, minor, patch, _ = spec
    values = [value for value in (major, minor, patch) if value is not None]
    if not values:
        return None
    # Bump the first non-zero specified component, or the last specified one.
    bump_index = len(values) - 1
    for index, value in enumerate(values):
        if value != 0:
            bump_index = index
            break
    bumped = values + [0] * (3 - len(values))
    bumped[bump_index] += 1
    for index in range(bump_index + 1, 3):
        bumped[index] = 0
    return semver_solver.Version(bumped[0], bumped[1], bumped[2])


def _tilde_upper(spec: _VersionSpec) -> Optional[semver_solver.Version]:
    major, minor, patch, _ = spec
    values = [value for value in (major, minor, patch) if value is not None]
    if not values:
        return None
    if len(values) == 1:
        return semver_solver.Version(values[0] + 1, 0, 0)
    return semver_solver.Version(values[0], values[1] + 1, 0)


def _split_operator(token: str) -> Tuple[Optional[str], str]:
    for operator in _OPERATORS:
        if token == operator:
            return operator, ""
        if token.startswith(operator):
            return operator, token[len(operator):]
    return None, token


def _split_terms(clause: str, raw: str) -> List[Tuple[Optional[str], _VersionSpec]]:
    tokens = clause.split()
    terms: List[Tuple[Optional[str], _VersionSpec]] = []
    index = 0
    while index < len(tokens):
        operator, version_text = _split_operator(tokens[index])
        if not version_text:
            # An operator separated from its operand by whitespace.
            index += 1
            if index >= len(tokens):
                raise _invalid_range(raw)
            version_text = tokens[index]
        terms.append((operator, _parse_spec(version_text, raw)))
        index += 1
    return terms


def _expand_term(operator: Optional[str], spec: _VersionSpec) -> _Alternatives:
    lower = _spec_lower(spec)
    if _is_full(spec):
        if operator is None or operator == "=" or operator == "==":
            return [[(semver_solver.ComparatorOp.EQ, lower)]]
        if operator == "!=":
            return [[(semver_solver.ComparatorOp.NE, lower)]]
        if operator == "<":
            return [[(semver_solver.ComparatorOp.LT, lower)]]
        if operator == "<=":
            return [[(semver_solver.ComparatorOp.LE, lower)]]
        if operator == ">":
            return [[(semver_solver.ComparatorOp.GT, lower)]]
        if operator == ">=":
            return [[(semver_solver.ComparatorOp.GE, lower)]]
        if operator == "^":
            caret_upper = _caret_upper(spec)
            assert caret_upper is not None
            return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, caret_upper)]]
        tilde_upper = _tilde_upper(spec)
        assert tilde_upper is not None
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, tilde_upper)]]

    upper = _spec_upper(spec)
    if operator is None or operator == "=" or operator == "==":
        if upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]]
    if operator == "!=":
        if upper is None:
            return []
        return [[(semver_solver.ComparatorOp.LT, lower)], [(semver_solver.ComparatorOp.GE, upper)]]
    if operator == ">":
        if upper is None:
            return []
        return [[(semver_solver.ComparatorOp.GE, upper)]]
    if operator == ">=":
        return [[(semver_solver.ComparatorOp.GE, lower)]]
    if operator == "<":
        return [[(semver_solver.ComparatorOp.LT, lower)]]
    if operator == "<=":
        if upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.LT, upper)]]
    if operator == "^":
        caret_upper = _caret_upper(spec)
        if caret_upper is None:
            return [[(semver_solver.ComparatorOp.GE, lower)]]
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, caret_upper)]]
    if operator == "~":
        tilde_upper = _tilde_upper(spec)
        if tilde_upper is None:
            return [[(semver_solver.ComparatorOp.GE, lower)]]
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, tilde_upper)]]
    raise AssertionError(f"unsupported comparator operator: {operator}")


def _combine(current: _Alternatives, extension: _Alternatives) -> _Alternatives:
    combined: _Alternatives = []
    for existing in current:
        for addition in extension:
            combined.append(existing + addition)
    return combined


def _compile_clause(clause: str, raw: str) -> _Alternatives:
    hyphen = _HYPHEN_RE.fullmatch(clause)
    if hyphen is not None:
        lower_spec = _parse_spec(hyphen.group(1), raw)
        upper_spec = _parse_spec(hyphen.group(2), raw)
        comparators: List[_Comparator] = [(semver_solver.ComparatorOp.GE, _spec_lower(lower_spec))]
        if _is_full(upper_spec):
            comparators.append((semver_solver.ComparatorOp.LE, _spec_lower(upper_spec)))
        else:
            upper = _spec_upper(upper_spec)
            if upper is not None:
                comparators.append((semver_solver.ComparatorOp.LT, upper))
        return [comparators]
    alternatives: _Alternatives = [[]]
    for operator, spec in _split_terms(clause, raw):
        alternatives = _combine(alternatives, _expand_term(operator, spec))
    return alternatives


def _compile_range(raw_text: str) -> _Alternatives:
    alternatives: _Alternatives = []
    for clause in raw_text.split("||"):
        alternatives.extend(_compile_clause(clause.strip(), raw_text))
    return alternatives


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # POSTCONDITION: valid SemVer 2.0.0 strings map to immutable Version records.
        match = _VERSION_RE.fullmatch(text)
        if match is None:
            # PRECONDITION: grammar violations and leading zeroes raise InvalidVersionError.
            raise semver_solver.InvalidVersionError(f"Invalid semantic version: {text}", text)
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        build = tuple(match.group(5).split(".")) if match.group(5) else ()
        return semver_solver.Version(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            prerelease,
            build,
        )

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # POSTCONDITION: major, minor, and patch compare numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return left - right
        # POSTCONDITION: normal versions rank above prerelease versions.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # POSTCONDITION: prerelease segments compare numerically, else ASCII order,
        # with numeric segments ranked below string segments.
        for left_segment, right_segment in zip(v1.prerelease, v2.prerelease):
            if left_segment == right_segment:
                continue
            left_numeric = left_segment.isdigit()
            right_numeric = right_segment.isdigit()
            if left_numeric and right_numeric:
                return int(left_segment) - int(right_segment)
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            if left_segment < right_segment:
                return -1
            return 1
        # POSTCONDITION: build metadata is excluded; longer common prefixes rank higher.
        return len(v1.prerelease) - len(v2.prerelease)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        trimmed = text.strip()
        # PRECONDITION: empty ranges, comma delimiters, and empty union clauses raise.
        if not trimmed:
            raise _invalid_range(text)
        if "," in trimmed:
            raise _invalid_range(text)
        clauses = [clause.strip() for clause in trimmed.split("||")]
        for clause in clauses:
            if not clause:
                raise _invalid_range(text)
        normalized = " || ".join(clauses)
        _compile_range(normalized)
        # POSTCONDITION: the trimmed range expression is stored in raw_text.
        return semver_solver.VersionRange(normalized)

    def _matches_comparator(self, version: semver_solver.Version, comparator: _Comparator) -> bool:
        operator, boundary = comparator
        order = self.compare_precedence(version, boundary)
        if operator is semver_solver.ComparatorOp.EQ:
            return order == 0
        if operator is semver_solver.ComparatorOp.NE:
            return order != 0
        if operator is semver_solver.ComparatorOp.LT:
            return order < 0
        if operator is semver_solver.ComparatorOp.LE:
            return order <= 0
        if operator is semver_solver.ComparatorOp.GT:
            return order > 0
        if operator is semver_solver.ComparatorOp.GE:
            return order >= 0
        raise AssertionError(f"unsupported comparator operator: {operator}")

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        alternatives = _compile_range(range_constraint.raw_text)
        boundaries = [comparator[1] for alternative in alternatives for comparator in alternative]
        # POSTCONDITION: prerelease candidates are excluded unless the range
        # explicitly targets a prerelease sharing major, minor, and patch.
        if version.is_prerelease and not include_prerelease:
            targets_prerelease = False
            for boundary in boundaries:
                if (
                    boundary.prerelease
                    and boundary.major == version.major
                    and boundary.minor == version.minor
                    and boundary.patch == version.patch
                ):
                    targets_prerelease = True
                    break
            if not targets_prerelease:
                return False
        # POSTCONDITION: satisfied when all comparators of at least one clause hold.
        for alternative in alternatives:
            matched = True
            for comparator in alternative:
                if not self._matches_comparator(version, comparator):
                    matched = False
                    break
            if matched:
                return True
        return False


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # POSTCONDITION: releases stay ordered by descending version precedence.
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        index = len(releases) - 1
        while index > 0 and engine.compare_precedence(releases[index - 1].version, releases[index].version) < 0:
            releases[index - 1], releases[index] = releases[index], releases[index - 1]
            index -= 1

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        if name not in self._packages:
            # PRECONDITION: unknown package names raise PackageNotFoundError.
            raise semver_solver.PackageNotFoundError(f"Package not registered: {name}", name)
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
    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def resolve(self, root_dependencies: Collection[semver_solver.PackageDependency]) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        accumulated_constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated_constraints.setdefault(dependency.name, []).append(("root", dependency.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_candidates(name: str) -> List[semver_solver.PackageRelease]:
            try:
                releases = repository.get_releases(name)
            except semver_solver.PackageNotFoundError:
                # Unregistered packages simply contribute zero candidates.
                return []
            return [
                release
                for release in releases
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated_constraints[name]
                )
            ]

        def search() -> bool:
            unassigned = [name for name in accumulated_constraints if name not in assignment]
            if not unassigned:
                return True
            candidates_by_name = {name: viable_candidates(name) for name in unassigned}
            # MRV heuristic with lexical tie-breaking.
            selected = min(unassigned, key=lambda name: (len(candidates_by_name[name]), name))
            candidates = candidates_by_name[selected]
            if not candidates:
                requesters = [source for source, _ in accumulated_constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not engine.satisfies(assignment[dependency.name].version, dependency.range_constraint, False):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        constraint_entry = (selected, dependency.range_constraint)
                        accumulated_constraints.setdefault(dependency.name, []).append(constraint_entry)
                        newly_added.append((dependency.name, constraint_entry))
                if not conflict_detected and search():
                    return True
                for name, constraint_entry in newly_added:
                    accumulated_constraints[name].remove(constraint_entry)
                    if not accumulated_constraints[name]:
                        del accumulated_constraints[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not search():
            explanation = "; ".join(conflict_trail)
            # PRECONDITION: unsatisfiable dependencies raise ResolutionConflictError,
            # never leaking PackageNotFoundError.
            raise semver_solver.ResolutionConflictError(
                f"Unable to resolve dependencies: {explanation}",
                tuple(sorted(conflicting_packages)),
                explanation,
            )
        return semver_solver.ResolutionOutcome(
            selected_versions={name: release.version for name, release in assignment.items()},
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:11:18Z
# LAST_CHANGED: 2026-11-07T03:11:18Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: d8548b6794c6
# COVERAGE_AUDIT: 2026-11-07T03:11:18Z
# QA_AUDIT: 2026-11-07T03:11:18Z
# --- END AUTOFAB METADATA ---
