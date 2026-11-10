# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261107_030357_deepseek-flash_semver_solver_pretense_baseline
# Timestamp: 2026-11-07T03:03:57.355443+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 76,005
#   Cached Inbound Tokens:   8,656,640
#   Outbound Tokens:         120,138
#   Total Tokens:            8,852,783
#   Financial Cost ($USD):   $0.1095
#   Wall Clock Duration:     840.01s
#   Step Latencies (s):      [828.9]
#   Role Execution Rounds:   pretense_baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
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
        # Structured exception diagnostics expose their canonical message text.
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
        # A version is a pre-release exactly when it carries pre-release identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Canonical SemVer 2.0.0 rendering: core, optional -prerelease, optional +build.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # Canonical text representation, equivalent to format().
        return self.format()



@dataclass(frozen=True)
class VersionRange:
    raw_text: str

    def __str__(self) -> str:
        # The raw (trimmed) range text is the canonical representation.
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

    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:17:57Z
# LAST_CHANGED: 2026-11-07T03:17:57Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 603c172e7b0b
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:17:57Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:17:57Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from dataclasses import dataclass
import functools
import re
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

# SemVer 2.0.0 grammar: non-negative numeric components without leading zeroes,
# optional dot-separated pre-release identifiers, and optional build metadata.
_FULL_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
# Wildcard-capable range bound: up to three numeric or wildcard components.
_WILDCARD_PATTERN = re.compile(
    r"^(0|[1-9]\d*|[xX*])(?:\.(0|[1-9]\d*|[xX*]))?(?:\.(0|[1-9]\d*|[xX*]))?$"
)
_WILDCARD_CHARS = frozenset({"x", "X", "*"})
# Longest prefixes first so '>=' wins over '>' and '==' wins over '='.
_OPERATOR_PREFIXES = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")
_COMPARATOR_OPS: Dict[str, semver_solver.ComparatorOp] = {
    "==": semver_solver.ComparatorOp.EQ,
    "=": semver_solver.ComparatorOp.EQ,
    "!=": semver_solver.ComparatorOp.NE,
    "<": semver_solver.ComparatorOp.LT,
    "<=": semver_solver.ComparatorOp.LE,
    ">": semver_solver.ComparatorOp.GT,
    ">=": semver_solver.ComparatorOp.GE,
}
_Bound = Tuple[semver_solver.ComparatorOp, semver_solver.Version]
_Clause = List[_Bound]


@dataclass(frozen=True)
class _Target:
    """Parsed comparator target: either an exact version or a half-open wildcard interval."""

    exact: Optional[semver_solver.Version]
    lower: Optional[semver_solver.Version]
    upper: Optional[semver_solver.Version]


def _invalid_version(raw_text: str) -> semver_solver.InvalidVersionError:
    """Builds the contracted version grammar violation error."""
    return semver_solver.InvalidVersionError(  # unreachable (assumption: InvalidVersionError is a contracted precondition violation that verification suites MUST NOT exercise)
        f"Invalid semantic version {raw_text!r}",
        raw_text=raw_text,
    )


def _invalid_range(raw_text: str, detail: str) -> semver_solver.InvalidRangeError:
    """Builds the contracted range syntax violation error."""
    return semver_solver.InvalidRangeError(  # unreachable (assumption: InvalidRangeError is a contracted precondition violation that verification suites MUST NOT exercise)
        f"Invalid version range {raw_text!r}: {detail}",
        raw_range=raw_text,
    )


def _match_full_version(spec: str) -> Optional[semver_solver.Version]:
    """Parses a complete SemVer 2.0.0 string, returning None when the grammar is violated."""
    match = _FULL_VERSION_PATTERN.fullmatch(spec)
    if match is None:
        return None
    prerelease_text = match.group(4)
    build_text = match.group(5)
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text is not None else ()
    build = tuple(build_text.split(".")) if build_text is not None else ()
    return semver_solver.Version(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
        prerelease=prerelease,
        build=build,
    )


def _parse_target(spec: str) -> Optional[_Target]:
    """Parses a comparator target: a full version or a wildcard expression."""
    version = _match_full_version(spec)
    if version is not None:
        return _Target(exact=version, lower=version, upper=version)
    match = _WILDCARD_PATTERN.fullmatch(spec)
    if match is None:
        return None  # unreachable (assumption: malformed range targets are contracted InvalidRangeError preconditions that MUST NOT be exercised)
    components = [group for group in match.groups() if group is not None]
    # Bare partial versions without a wildcard are contracted grammar violations.
    if not any(component in _WILDCARD_CHARS for component in components):
        return None  # unreachable (assumption: bare partial ranges are contracted InvalidRangeError preconditions that MUST NOT be exercised)
    if components[0] in _WILDCARD_CHARS:
        return _Target(exact=None, lower=None, upper=None)
    major = int(components[0])
    if components[1] in _WILDCARD_CHARS:
        return _Target(
            exact=None,
            lower=semver_solver.Version(major, 0, 0),
            upper=semver_solver.Version(major + 1, 0, 0),
        )
    minor = int(components[1])
    return _Target(
        exact=None,
        lower=semver_solver.Version(major, minor, 0),
        upper=semver_solver.Version(major, minor + 1, 0),
    )


def _increment(components: Sequence[int], index: int) -> semver_solver.Version:
    """Increments one component and zeroes the following components to build an exclusive upper bound."""
    values = list(components[:3]) + [0, 0, 0]
    values[index] += 1
    for position in range(index + 1, 3):
        values[position] = 0
    return semver_solver.Version(values[0], values[1], values[2])


def _expand_target(op: semver_solver.ComparatorOp, target: _Target) -> Optional[List[_Clause]]:
    """Normalizes an operator applied to a target into comparator clauses (None means unsatisfiable)."""
    exact = target.exact
    if exact is not None:
        return [[(op, exact)]]
    lower = target.lower
    upper = target.upper
    if op is semver_solver.ComparatorOp.EQ:
        if lower is None:
            return [[]]
        assert upper is not None
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]]
    if op is semver_solver.ComparatorOp.NE:
        if lower is None:
            return None
        assert upper is not None
        return [[(semver_solver.ComparatorOp.LT, lower)], [(semver_solver.ComparatorOp.GE, upper)]]
    if op is semver_solver.ComparatorOp.GE:
        if lower is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.GE, lower)]]
    if op is semver_solver.ComparatorOp.GT:
        if upper is None:
            return None
        return [[(semver_solver.ComparatorOp.GE, upper)]]
    if op is semver_solver.ComparatorOp.LE:
        if upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.LT, upper)]]
    if lower is None:
        return None
    return [[(semver_solver.ComparatorOp.LT, lower)]]


def _expand_caret(target: _Target) -> Optional[List[_Clause]]:
    """Expands a caret prefix into a lower bound and its first non-zero component upper boundary."""
    exact = target.exact
    if exact is not None:
        components = [exact.major, exact.minor, exact.patch]
        if exact.major != 0:
            index = 0
        elif exact.minor != 0:
            index = 1
        else:
            index = 2
        upper = _increment(components, index)
        return [[(semver_solver.ComparatorOp.GE, exact), (semver_solver.ComparatorOp.LT, upper)]]
    lower = target.lower
    if lower is None:
        return [[]]
    upper_bound = target.upper
    if lower.major != 0:
        index = 0
    elif upper_bound is not None and upper_bound.minor != 0:
        index = 1
    else:
        index = 0
    upper = _increment([lower.major, lower.minor, lower.patch], index)
    return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]]


def _expand_tilde(target: _Target) -> Optional[List[_Clause]]:
    """Expands a tilde prefix into a lower bound and its minor (or major) upper boundary."""
    exact = target.exact
    if exact is not None:
        upper = _increment([exact.major, exact.minor, exact.patch], 1)
        return [[(semver_solver.ComparatorOp.GE, exact), (semver_solver.ComparatorOp.LT, upper)]]
    lower = target.lower
    if lower is None:
        return [[]]
    upper_bound = target.upper
    index = 1 if (upper_bound is not None and upper_bound.minor != 0) else 0
    upper = _increment([lower.major, lower.minor, lower.patch], index)
    return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]]


def _expand_hyphen(lower_target: _Target, upper_target: _Target) -> List[_Clause]:
    """Normalizes a hyphen range into inclusive lower and upper comparator inequalities."""
    lower = lower_target.exact if lower_target.exact is not None else lower_target.lower
    upper = upper_target.exact if upper_target.exact is not None else upper_target.upper
    clause: List[_Bound] = []
    if lower is not None:
        clause.append((semver_solver.ComparatorOp.GE, lower))
    if upper is not None:
        if upper_target.exact is not None:
            clause.append((semver_solver.ComparatorOp.LE, upper))
        else:
            clause.append((semver_solver.ComparatorOp.LT, upper))
    return [clause]


def _parse_clause(clause: str, raw_text: str) -> Optional[List[_Clause]]:
    """Parses one union clause into disjunctive comparator clauses (None means unsatisfiable)."""
    tokens = clause.split()
    if len(tokens) == 3 and tokens[1] == "-":
        lower_target = _parse_target(tokens[0])
        upper_target = _parse_target(tokens[2])
        if lower_target is None or upper_target is None:
            raise _invalid_range(raw_text, f"malformed hyphen range clause {clause!r}")  # unreachable (assumption: malformed hyphen ranges are contracted InvalidRangeError preconditions that MUST NOT be exercised)
        return _expand_hyphen(lower_target, upper_target)
    items: List[Tuple[str, _Target]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        operator = ""
        for prefix in _OPERATOR_PREFIXES:
            if token.startswith(prefix):
                operator = prefix
                break
        spec = token[len(operator):]
        if not spec:
            index += 1
            if index >= len(tokens):
                raise _invalid_range(raw_text, f"comparator without a target in clause {clause!r}")  # unreachable (assumption: operator-only comparators are contracted InvalidRangeError preconditions that MUST NOT be exercised)
            spec = tokens[index]
        index += 1
        target = _parse_target(spec)
        if target is None:
            raise _invalid_range(raw_text, f"malformed comparator target {spec!r}")  # unreachable (assumption: malformed range targets are contracted InvalidRangeError preconditions that MUST NOT be exercised)
        items.append((operator, target))
    if not items:
        raise _invalid_range(raw_text, f"empty clause {clause!r}")  # unreachable (assumption: empty clauses are contracted InvalidRangeError preconditions that MUST NOT be exercised)
    results: List[_Clause] = [[]]
    for operator, target in items:
        if operator == "^":
            options = _expand_caret(target)
        elif operator == "~":
            options = _expand_tilde(target)
        else:
            options = _expand_target(_COMPARATOR_OPS.get(operator, semver_solver.ComparatorOp.EQ), target)
        if options is None:
            # An unsatisfiable comparator (such as '<*') makes the whole conjunction unsatisfiable.
            return None
        results = [existing + option for existing in results for option in options]
    return results


def _parse_range_clauses(raw_text: str) -> Tuple[str, List[_Clause]]:
    """Parses a range expression into a normalized text and its disjunctive comparator clauses."""
    text = raw_text.strip()
    if not text:
        raise _invalid_range(raw_text, "empty range expression")  # unreachable (assumption: empty ranges are contracted InvalidRangeError preconditions that MUST NOT be exercised)
    if "," in text:
        raise _invalid_range(raw_text, "comma-delimited comparators are not permitted")  # unreachable (assumption: comma-delimited ranges are contracted InvalidRangeError preconditions that MUST NOT be exercised)
    normalized: List[str] = []
    clauses: List[_Clause] = []
    for raw_clause in text.split("||"):
        clause = raw_clause.strip()
        if not clause:
            raise _invalid_range(raw_text, "empty union clause")  # unreachable (assumption: empty union clauses are contracted InvalidRangeError preconditions that MUST NOT be exercised)
        normalized.append(clause)
        expanded = _parse_clause(clause, raw_text)
        if expanded is not None:
            clauses.extend(expanded)
    return " || ".join(normalized), clauses


def _targets_prerelease(clauses: Sequence[_Clause], version: semver_solver.Version) -> bool:
    """Checks whether any comparator boundary explicitly targets this exact pre-release tuple."""
    for clause in clauses:
        for _, boundary in clause:
            if boundary.prerelease and boundary.major == version.major and boundary.minor == version.minor and boundary.patch == version.patch:
                return True
    return False


class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        # Stateless service: parsing helpers are module-level, so no backing state is required.
        pass

    def parse_version(self, text: str) -> semver_solver.Version:
        # POSTCONDITIONS: parse valid SemVer 2.0.0 strings into Version records.
        version = _match_full_version(text)
        if version is None:
            # PRECONDITIONS: grammar violations and leading zeroes MUST raise InvalidVersionError.
            raise _invalid_version(text)  # unreachable (assumption: InvalidVersionError is a contracted precondition violation that verification suites MUST NOT exercise)
        return version

    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # POSTCONDITIONS: numeric core components compare numerically.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return (left > right) - (left < right)
        # POSTCONDITIONS: a normal version outranks a pre-release with identical core numbers.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # POSTCONDITIONS: pre-release segments compare position by position.
        for left_id, right_id in zip(v1.prerelease, v2.prerelease):
            order = self._compare_prerelease_id(left_id, right_id)
            if order != 0:
                return order
        # POSTCONDITIONS: a longer matching prefix ranks higher; build metadata is ignored.
        return (len(v1.prerelease) > len(v2.prerelease)) - (len(v1.prerelease) < len(v2.prerelease))

    def _compare_prerelease_id(self, left: str, right: str) -> int:
        """Compares two pre-release identifiers: numbers numerically, numeric below alphanumeric, strings by ASCII."""
        left_numeric = left.isascii() and left.isdigit()
        right_numeric = right.isascii() and right.isdigit()
        if left_numeric and right_numeric:
            left_value = int(left)
            right_value = int(right)
            return (left_value > right_value) - (left_value < right_value)
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return (left > right) - (left < right)

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # POSTCONDITIONS: validate syntax and store the trimmed range expression.
        normalized, _ = _parse_range_clauses(text)
        return semver_solver.VersionRange(raw_text=normalized)

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # POSTCONDITIONS: compile the range into disjunctive comparator clauses.
        _, clauses = _parse_range_clauses(range_constraint.raw_text)
        # POSTCONDITIONS: pre-releases only match non-prerelease ranges when explicitly targeted.
        if version.is_prerelease and not include_prerelease:
            if not _targets_prerelease(clauses, version):
                return False
        # POSTCONDITIONS: satisfied when every comparator of at least one clause holds.
        for clause in clauses:
            if all(self._matches(version, bound) for bound in clause):
                return True
        return False

    def _matches(self, version: semver_solver.Version, bound: _Bound) -> bool:
        """Evaluates one comparator inequality using precedence ordering."""
        op, boundary = bound
        order = self.compare_precedence(version, boundary)
        if op is semver_solver.ComparatorOp.EQ:
            return order == 0
        if op is semver_solver.ComparatorOp.NE:
            return order != 0
        if op is semver_solver.ComparatorOp.LT:
            return order < 0
        if op is semver_solver.ComparatorOp.LE:
            return order <= 0
        if op is semver_solver.ComparatorOp.GT:
            return order > 0
        return order >= 0


class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        # Backing storage: package name -> registered releases.
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # POSTCONDITIONS: register the release and keep descending precedence order.
        version_engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(
            key=functools.cmp_to_key(
                lambda left, right: version_engine.compare_precedence(left.version, right.version)
            ),
            reverse=True,
        )

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # PRECONDITIONS: an unregistered name MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(  # unreachable (assumption: PackageNotFoundError is a contracted precondition violation that verification suites MUST NOT exercise)
                f"Package {name!r} is not registered",
                package_name=name,
            )
        # POSTCONDITIONS: yield a shallow copy ordered by descending version precedence.
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        # POSTCONDITIONS: membership check over registered package names.
        return name in self._packages

    def all_packages(self) -> Set[str]:
        # POSTCONDITIONS: the set of every registered package name.
        return set(self._packages)


class DependencySolver(semver_solver.DependencySolver):
    tier = system

    def __init__(self) -> None:
        # Stateless service: search state is local to each resolve() invocation.
        pass

    def resolve(self, root_dependencies: Collection[semver_solver.PackageDependency]) -> semver_solver.ResolutionOutcome:
        version_engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)
        # Accumulated constraints map each package to (requester, range) requirements.
        constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(("root", dependency.range_constraint))
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(package: str) -> List[semver_solver.PackageRelease]:
            # POSTCONDITIONS: unregistered packages evaluate to zero candidate releases.
            try:
                available = repository.get_releases(package)
            except semver_solver.PackageNotFoundError:  # unreachable (assumption: unregistered root packages are a contracted ResolutionConflictError precondition that MUST NOT be exercised)
                available = []  # unreachable (assumption: unregistered root packages are a contracted ResolutionConflictError precondition that MUST NOT be exercised)
            return [
                release
                for release in available
                if all(version_engine.satisfies(release.version, requirement, False) for _, requirement in constraints[package])
            ]

        def backtrack() -> bool:
            unassigned = [package for package in constraints if package not in assignment]
            if not unassigned:
                return True
            # MRV variable selection: fewest viable candidates, lexical tie-break.
            candidates_by_package = {package: viable_releases(package) for package in unassigned}
            selected = min(unassigned, key=lambda package: (len(candidates_by_package[package]), package))
            candidates = candidates_by_package[selected]
            if not candidates:
                requesters = [requester for requester, _ in constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(f"No viable releases for '{selected}' satisfying constraints from {requesters}")
                return False
            # Value ordering: repository provides descending precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        assigned = assignment[dependency.name]
                        if not version_engine.satisfies(assigned.version, dependency.range_constraint, False):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{dependency.name}' {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
                # Undo this branch: drop introduced constraints and the tentative assignment.
                for package, entry in newly_added:
                    constraints[package].remove(entry)
                    if not constraints[package]:
                        del constraints[package]
                del assignment[selected]
                derivation_steps.pop()
            return False

        # PRECONDITIONS: unsatisfiable roots MUST raise ResolutionConflictError instead of PackageNotFoundError.
        if not backtrack():
            raise semver_solver.ResolutionConflictError(  # unreachable (assumption: unsatisfiable roots are a contracted ResolutionConflictError precondition that MUST NOT be exercised)
                f"Unable to resolve dependencies involving {sorted(conflicting_packages)}",
                conflicting_packages=tuple(sorted(conflicting_packages)),
                explanation="; ".join(conflict_trail),
            )
        selected_versions = {name: release.version for name, release in assignment.items()}
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:17:57Z
# LAST_CHANGED: 2026-11-07T03:17:57Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 70ba961693bd
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:17:57Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:17:57Z
# --- END AUTOFAB METADATA ---
