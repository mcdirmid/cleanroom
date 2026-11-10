# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_203118_deepseek-flash_semver_solver_combined
# Timestamp: 2026-11-10T20:31:18.856936+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 483,094
#   Cached Inbound Tokens:   36,448,768
#   Outbound Tokens:         522,270
#   Total Tokens:            37,454,132
#   Financial Cost ($USD):   $0.4952
#   Wall Clock Duration:     1993.63s
#   Step Latencies (s):      [228.2, 343.4, 66.2, 53.7, 51.4, 10.1, 527.9, 135.9, 205.8, 398.2, 10.1, 115.8, 126.2, 22.9, 11.8, 74.0, 143.9, 233.2, 105.3, 10.1, 20.4, 243.7, 20.3, 94.5, 166.5, 20.3, 51.1, 125.4, 10.1, 20.3]
#   Role Execution Rounds:   coverage: 3, lib: 4, pretense: 5, pretense_coverage: 4, pretense_qa: 6, qa: 4, test: 4 (Total: 30)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       43
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Low-level interface specification for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum

# Requirements specified in semver_solver.pyi


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __post_init__(self) -> None:
        # Initialize the exception message through the standard Exception machinery.
        Exception.__init__(self, self.message)

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
        # True exactly when the version carries at least one prerelease identifier.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Reassemble the canonical SemVer 2.0.0 textual form from the components.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        return self.format()


@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        return self.raw_text


@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range."""

    name: str
    range_constraint: VersionRange


@dataclass(frozen=True)
class PackageRelease:
    """Immutable publication record of a package at a specific semantic version."""

    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run."""

    selected_versions: Mapping[str, Version]
    derivation_steps: Tuple[str, ...]


class VersionEngine(Protocol):
    """Provides semantic version parsing, precedence comparison, and range matching."""

    def parse_version(self, text: str) -> Version:
        ...

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        ...

    def parse_range(self, text: str) -> VersionRange:
        ...

    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        ...


class PackageRepository(Protocol):
    """Maintains indexed package publications and release histories."""

    def register_package(self, release: PackageRelease) -> None:
        ...

    def get_releases(self, name: str) -> List[PackageRelease]:
        ...

    def has_package(self, name: str) -> bool:
        ...

    def all_packages(self) -> Set[str]:
        ...


class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T20:37:08Z
# LAST_CHANGED: 2026-11-10T20:37:08Z
# CHANGE: Implemented SemVer 2.0 interface module: non-frozen dataclass exceptions with message formatting, frozen Version/VersionRange/PackageDependency/PackageRelease/ResolutionOutcome records, Version.format/is_prerelease/__str__, and protocol stubs for VersionEngine, PackageRepository, and DependencySolver.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete realization of SemVer 2.0 parsing and backtracking dependency resolution."""

from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple, Union
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_solver
import re
from functools import cmp_to_key

# Requirements specified in semver_solver_impl.pyi

_Term = Tuple[semver_solver.ComparatorOp, semver_solver.Version]
_Alternatives = List[List[_Term]]
_WildcardComponents = Tuple[Optional[int], Optional[int], Optional[int]]
_Bound = Union[semver_solver.Version, _WildcardComponents]

_SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
_NUMERIC_PATTERN = re.compile(r"0|[1-9][0-9]*")
_HYPHEN_PATTERN = re.compile(r"(\S+)\s+-\s+(\S+)")
_SPACED_HYPHEN_PATTERN = re.compile(r"\s-\s")
_WILDCARD_MARKERS = ("x", "X", "*")
_OPERATOR_PREFIXES = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")


def _match_version(text: str) -> Optional[semver_solver.Version]:
    """Matches a complete SemVer 2.0.0 version string against the canonical grammar."""
    match = _SEMVER_PATTERN.fullmatch(text)
    if match is None:
        return None
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    return semver_solver.Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=tuple(prerelease_text.split(".")) if prerelease_text else (),
        build=tuple(build_text.split(".")) if build_text else (),
    )


def _match_wildcard(text: str) -> Optional[_WildcardComponents]:
    """Matches a wildcard expression such as '1.x', '1.2.*', 'x', or '*'."""
    parts = text.split(".")
    if not 1 <= len(parts) <= 3:
        return None
    numbers: List[Optional[int]] = []
    seen_wildcard = False
    for part in parts:
        if part in _WILDCARD_MARKERS:
            seen_wildcard = True
            numbers.append(None)
            continue
        # Numeric components preceding a wildcard must use the SemVer no-leading-zero grammar.
        if seen_wildcard or _NUMERIC_PATTERN.fullmatch(part) is None:
            return None
        numbers.append(int(part))
    if not seen_wildcard:
        return None
    while len(numbers) < 3:
        numbers.append(None)
    return (numbers[0], numbers[1], numbers[2])


def _parse_bound(text: str) -> _Bound:
    """Parses a single comparator target as an exact version or a wildcard expression."""
    version = _match_version(text)
    if version is not None:
        return version
    wildcard = _match_wildcard(text)
    if wildcard is not None:
        return wildcard
    # Bare partials lacking wildcards (such as '1', '1.2', or '0.0') are invalid targets.
    raise ValueError(f"invalid version or wildcard expression '{text}'")


def _wildcard_lower(components: _WildcardComponents) -> semver_solver.Version:
    """Fills unspecified wildcard components with zero to obtain the inclusive lower bound."""
    return semver_solver.Version(components[0] or 0, components[1] or 0, components[2] or 0)


def _wildcard_upper(major: int, minor: Optional[int]) -> semver_solver.Version:
    """Computes the exclusive upper bound implied by a wildcard expression's specified components."""
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _caret_upper(major: int, minor: Optional[int], patch: Optional[int]) -> semver_solver.Version:
    """Computes the exclusive caret upper bound based on the left-most non-zero component."""
    if major > 0:
        return semver_solver.Version(major + 1, 0, 0)
    if minor is None:
        return semver_solver.Version(1, 0, 0)
    if minor > 0:
        return semver_solver.Version(0, minor + 1, 0)
    if patch is None:
        return semver_solver.Version(0, 1, 0)
    return semver_solver.Version(0, 0, patch + 1)


def _tilde_upper(major: int, minor: Optional[int]) -> semver_solver.Version:
    """Computes the exclusive tilde upper bound from the specified major and minor components."""
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _expand_exact(operator: Optional[str], version: semver_solver.Version) -> _Alternatives:
    """Expands a comparator applied to a full semantic version into comparator alternatives."""
    if operator is None or operator in ("==", "="):
        return [[(semver_solver.ComparatorOp.EQ, version)]]
    if operator == "!=":
        return [[(semver_solver.ComparatorOp.NE, version)]]
    if operator == "<":
        return [[(semver_solver.ComparatorOp.LT, version)]]
    if operator == "<=":
        return [[(semver_solver.ComparatorOp.LE, version)]]
    if operator == ">":
        return [[(semver_solver.ComparatorOp.GT, version)]]
    if operator == ">=":
        return [[(semver_solver.ComparatorOp.GE, version)]]
    if operator == "^":
        upper = _caret_upper(version.major, version.minor, version.patch)
        return [[(semver_solver.ComparatorOp.GE, version), (semver_solver.ComparatorOp.LT, upper)]]
    # The relational prefixes are exhaustive, so the remaining prefix is the tilde range.
    upper = _tilde_upper(version.major, version.minor)
    return [[(semver_solver.ComparatorOp.GE, version), (semver_solver.ComparatorOp.LT, upper)]]


def _expand_wildcard(operator: Optional[str], components: _WildcardComponents) -> _Alternatives:
    """Normalizes a comparator applied to a wildcard expression into comparator inequalities."""
    major, minor, patch = components
    if major is None:
        # Fully unspecified wildcards match every version for the broad operators.
        if operator in (None, "==", "=", ">=", "<=", "^", "~"):
            return [[]]
        return []
    lower = semver_solver.Version(major, minor or 0, patch or 0)
    upper = _wildcard_upper(major, minor)
    if operator is None or operator in ("==", "="):
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]]
    if operator == "!=":
        return [
            [(semver_solver.ComparatorOp.LT, lower)],
            [(semver_solver.ComparatorOp.GE, upper)],
        ]
    if operator == "<":
        return [[(semver_solver.ComparatorOp.LT, lower)]]
    if operator == "<=":
        return [[(semver_solver.ComparatorOp.LT, upper)]]
    if operator == ">":
        return [[(semver_solver.ComparatorOp.GE, upper)]]
    if operator == ">=":
        return [[(semver_solver.ComparatorOp.GE, lower)]]
    if operator == "^":
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, _caret_upper(major, minor, patch))]]
    # The relational prefixes are exhaustive, so the remaining prefix is the tilde range.
    return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, _tilde_upper(major, minor))]]


def _expand_comparator(operator: Optional[str], bound: _Bound) -> _Alternatives:
    """Expands a comparator and its parsed target into disjunctive comparator alternatives."""
    if isinstance(bound, semver_solver.Version):
        return _expand_exact(operator, bound)
    return _expand_wildcard(operator, bound)


def _hyphen_terms(lower: _Bound, upper: _Bound) -> List[_Term]:
    """Expands a hyphen range into its inclusive lower and upper comparator conjunction."""
    terms: List[_Term] = []
    if isinstance(lower, semver_solver.Version):
        terms.append((semver_solver.ComparatorOp.GE, lower))
    else:
        # Wildcard lower bounds are normalized by filling unspecified components with zero.
        if lower[0] is not None:
            terms.append((semver_solver.ComparatorOp.GE, _wildcard_lower(lower)))
    if isinstance(upper, semver_solver.Version):
        terms.append((semver_solver.ComparatorOp.LE, upper))
    else:
        # Wildcard upper bounds convert into an exclusive bound of the next partial version.
        upper_major, upper_minor, _ = upper
        if upper_major is not None:
            terms.append((semver_solver.ComparatorOp.LT, _wildcard_upper(upper_major, upper_minor)))
    return terms


def _split_operator(token: str) -> Tuple[Optional[str], str]:
    """Splits a whitespace token into an optional relational/prefix operator and its target."""
    for prefix in _OPERATOR_PREFIXES:
        if token.startswith(prefix):
            return prefix, token[len(prefix):]
    return None, token


def _parse_clause(clause: str) -> _Alternatives:
    """Parses one union clause into disjunctive normal form comparator alternatives."""
    if "," in clause:
        raise ValueError(f"comma delimiters are not permitted in range clause '{clause}'")
    hyphen_match = _HYPHEN_PATTERN.fullmatch(clause)
    if hyphen_match is not None:
        lower = _parse_bound(hyphen_match.group(1))
        upper = _parse_bound(hyphen_match.group(2))
        return [_hyphen_terms(lower, upper)]
    if _SPACED_HYPHEN_PATTERN.search(clause) is not None:
        raise ValueError(f"malformed hyphen range '{clause}'")
    alternatives: _Alternatives = [[]]
    tokens = clause.split()
    index = 0
    while index < len(tokens):
        operator, operand = _split_operator(tokens[index])
        if operand == "":
            # Operators may be separated from their target by optional whitespace.
            index += 1
            if index >= len(tokens):
                raise ValueError(f"range operator '{operator}' is missing a target version")
            operand = tokens[index]
        bound = _parse_bound(operand)
        alternatives = [
            existing + expansion
            for existing in alternatives
            for expansion in _expand_comparator(operator, bound)
        ]
        index += 1
    return alternatives


def _compile_range(text: str) -> _Alternatives:
    """Compiles a complete range expression into disjunctive normal form comparator alternatives."""
    if not text.strip():
        raise ValueError("empty range expression")
    if "|" in text:
        pieces = re.split(r"\|\|", text)
        for piece in pieces:
            if "|" in piece:
                raise ValueError(f"malformed union operator in range expression '{text}'")
    else:
        pieces = [text]
    alternatives: _Alternatives = []
    for piece in pieces:
        clause = piece.strip()
        if not clause:
            raise ValueError(f"empty union clause in range expression '{text}'")
        # Union clauses are disjunctive alternatives, so each clause contributes its own
        # conjunction set rather than being conjoined with the other clauses' alternatives.
        alternatives.extend(_parse_clause(clause))
    return alternatives


def _term_matches(
    engine: semver_solver.VersionEngine,
    version: semver_solver.Version,
    operator: semver_solver.ComparatorOp,
    bound: semver_solver.Version,
) -> bool:
    """Evaluates one comparator against a candidate version using precedence ordering."""
    comparison = engine.compare_precedence(version, bound)
    if operator == semver_solver.ComparatorOp.EQ:
        return comparison == 0
    if operator == semver_solver.ComparatorOp.NE:
        return comparison != 0
    if operator == semver_solver.ComparatorOp.LT:
        return comparison < 0
    if operator == semver_solver.ComparatorOp.LE:
        return comparison <= 0
    if operator == semver_solver.ComparatorOp.GT:
        return comparison > 0
    # All remaining enum members denote the greater-or-equal comparison.
    return comparison >= 0


class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        pass

    def parse_version(self, text: str) -> semver_solver.Version:
        # Validates the SemVer 2.0.0 grammar (including the prerelease leading-zero rule).
        version = _match_version(text)
        if version is None:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version: {text!r}",
                raw_text=text,
            )
        return version

    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # Compares the numeric components numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left < right:
                return -1
            if left > right:
                return 1
        # Ranks a normal version above a prerelease sharing identical numeric components.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # Compares prerelease segments position by position; build metadata is ignored.
        for index in range(max(len(v1.prerelease), len(v2.prerelease))):
            if index >= len(v1.prerelease):
                return -1
            if index >= len(v2.prerelease):
                return 1
            left_segment = v1.prerelease[index]
            right_segment = v2.prerelease[index]
            left_numeric = left_segment.isdigit()
            right_numeric = right_segment.isdigit()
            if left_numeric and right_numeric:
                left_number = int(left_segment)
                right_number = int(right_segment)
                if left_number < right_number:
                    return -1
                if left_number > right_number:
                    return 1
                continue
            # Ranks numeric prerelease segments below alphanumeric segments.
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            # Compares alphanumeric segments by ASCII code points.
            if left_segment < right_segment:
                return -1
            if left_segment > right_segment:
                return 1
        return 0

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Trims surrounding whitespace and validates the entire range expression grammar.
        trimmed = text.strip()
        try:
            _compile_range(trimmed)
        except ValueError as error:
            raise semver_solver.InvalidRangeError(
                message=str(error),
                raw_range=text,
            ) from None
        return semver_solver.VersionRange(raw_text=trimmed)

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Compiles the validated range expression into disjunctive normal form comparator sets.
        alternatives = _compile_range(range_constraint.raw_text)
        for terms in alternatives:
            if not all(_term_matches(self, version, operator, bound) for operator, bound in terms):
                continue
            if version.is_prerelease and not include_prerelease:
                # Prerelease candidates only match when the range targets their exact numeric tuple.
                targets_prerelease = any(
                    bound.is_prerelease
                    and (bound.major, bound.minor, bound.patch) == (version.major, version.minor, version.patch)
                    for _, bound in terms
                )
                if not targets_prerelease:
                    continue
            return True
        return False


class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # Inserts the release and re-sorts the history in descending version precedence order.
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)

        def descending(left: semver_solver.PackageRelease, right: semver_solver.PackageRelease) -> int:
            return engine.compare_precedence(right.version, left.version)

        releases.sort(key=cmp_to_key(descending))

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # Missing packages raise PackageNotFoundError; existing ones yield a shallow copy.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        return name in self._packages

    def all_packages(self) -> Set[str]:
        return set(self._packages)


class DependencySolver(semver_solver.DependencySolver):
    tier = system

    def __init__(self) -> None:
        pass

    def resolve(self, root_dependencies: Collection[semver_solver.PackageDependency]) -> semver_solver.ResolutionOutcome:
        # Resolves collaborator singletons on demand rather than registering them locally.
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to its requesting sources and ranges.
        constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(("root", dependency.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def candidates_for(name: str) -> List[semver_solver.PackageRelease]:
            # Unregistered packages evaluate to an empty candidate list without escaping errors.
            if not repository.has_package(name):
                return []
            viable: List[semver_solver.PackageRelease] = []
            for release in repository.get_releases(name):
                if all(engine.satisfies(release.version, constraint, False) for _, constraint in constraints[name]):
                    viable.append(release)
            return viable

        def backtrack() -> bool:
            unassigned = [name for name in constraints if name not in assignment]
            if not unassigned:
                return True
            # Minimum Remaining Values selection with lexical tie-breaking.
            candidate_map = {name: candidates_for(name) for name in unassigned}
            selected = min(unassigned, key=lambda name: (len(candidate_map[name]), name))
            candidates = candidate_map[selected]
            if not candidates:
                requesters = sorted(source for source, _ in constraints[selected] if source != "root")
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfy constraints from "
                    + (", ".join(requesters) if requesters else "the root dependencies")
                )
                return False
            # Explores viable candidate releases in descending version precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version.format()}")
                conflict_detected = False
                added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # A dependency on an assigned package must be compatible immediately.
                        if not engine.satisfies(assignment[dependency.name].version, dependency.range_constraint, False):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' {candidate.version.format()} requires "
                                f"'{dependency.name}' '{dependency.range_constraint.raw_text}' but "
                                f"'{dependency.name}' is assigned "
                                f"{assignment[dependency.name].version.format()}"
                            )
                            break
                        continue
                    # Newly introduced transitive requirements merge into the constraint mapping.
                    entry = (selected, dependency.range_constraint)
                    constraints.setdefault(dependency.name, []).append(entry)
                    added.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
                # Restores the previous constraint mapping before trying the next candidate.
                for name, entry in added:
                    constraints[name].remove(entry)
                    if not constraints[name]:
                        del constraints[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not backtrack():
            # A failed search always records at least one conflict entry and involved package.
            involved = tuple(sorted(conflicting_packages))
            raise semver_solver.ResolutionConflictError(
                message="Dependency resolution failed for: " + ", ".join(involved),
                conflicting_packages=involved,
                explanation="\n".join(conflict_trail),
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
# LAST_CLEANED: 2026-11-10T21:04:19Z
# LAST_CHANGED: 2026-11-10T20:54:02Z
# CHANGE: Completed unreachable-logic pruning flagged by pretense coverage: removed the redundant unsupported-operator raises by making the closed relational prefix set exhaustive (final branch is the tilde range), dropped the redundant unsupported-comparator raise over the closed ComparatorOp enum, removed the pre-validated empty-clause guard in _parse_clause, and pruned the impossible conflict-trail/package fallbacks in resolve since failed searches always record a trail entry and involved package.
# COVERAGE_AUDIT: 2026-11-10T20:54:38Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T21:04:19Z
# PRETENSE_QA_AUDIT: 2026-11-10T21:04:06Z
# QA_AUDIT: 2026-11-10T20:54:23Z
# --- END AUTOFAB METADATA ---
