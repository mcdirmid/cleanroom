# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_040016_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-11-05T04:00:16.742359+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 341,079
#   Cached Inbound Tokens:   32,247,295
#   Outbound Tokens:         388,221
#   Total Tokens:            32,976,595
#   Financial Cost ($USD):   $0.3808
#   Wall Clock Duration:     2260.38s
#   Step Latencies (s):      [329.1, 410.8, 327.7, 132.8, 106.9, 200.6, 115.6, 253.1, 10.4, 54.7, 118.4, 10.4, 151.9, 98.6, 121.9, 53.1, 42.5, 10.3, 54.5, 42.7, 10.6, 10.4]
#   Role Execution Rounds:   lib: 3, pretense: 7, pretense_coverage: 4, pretense_qa: 8 (Total: 22)
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

from dataclasses import dataclass
import enum
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type

# Requirements specified in semver_solver.pyi


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __str__(self) -> str:
        # Error formatting delegates to the diagnostic message field.
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
        # A version is a prerelease when it carries at least one identifier.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Canonical SemVer string: numeric core, optional prerelease, optional build.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # String representation is equivalent to format().
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        # String representation delegates to the canonical raw range text.
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
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:05:38Z
# LAST_CHANGED: 2026-11-05T04:05:38Z
# CHANGE: Implemented SemVer interface types: non-frozen dataclass exceptions with __str__, frozen data types (Version with is_prerelease/format/__str__, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome), and @poly_type protocol stubs for VersionEngine, PackageRepository, DependencySolver.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Callable, Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

_SEMVER_PATTERN = re.compile(
    r"\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
)

_IDENTIFIER_PATTERN = re.compile(r"\A[0-9A-Za-z-]+\Z")

_RANGE_OP_PATTERN = re.compile(r"\A(>=|<=|==|!=|>|<|=|\^|~)")

_WILDCARD_TOKENS = frozenset({"*", "x", "X"})

# Parsed version specifier: (major, minor, patch, prerelease, build) where
# numeric components equal to None denote wildcard positions.
_VersionSpec = Tuple[
    Optional[int],
    Optional[int],
    Optional[int],
    Tuple[str, ...],
    Tuple[str, ...],
]

# Comparator: (operator, lower boundary, upper boundary). Every expanded
# comparator carries both boundaries; the upper value is consulted only by the
# negated-range operator that expresses wildcard exclusions.
_Comparator = Tuple[str, semver_solver.Version, semver_solver.Version]
_ComparatorClause = List[_Comparator]

# Sentinel boundaries for the unsatisfiable wildcard comparator.
_FALSE_COMPARATOR: _Comparator = (
    "false",
    semver_solver.Version(0, 0, 0),
    semver_solver.Version(0, 0, 0),
)


def _invalid_range(raw_range: str, detail: str) -> semver_solver.InvalidRangeError:
    """Builds an InvalidRangeError retaining the original malformed range text."""
    return semver_solver.InvalidRangeError(
        f"Invalid version range: {detail}", raw_range
    )


def _split_spec_text(
    text: str,
) -> Tuple[str, Tuple[str, ...], Tuple[str, ...]]:
    """Splits a version specifier into core text, prerelease, and build segments."""
    core = text
    build: Tuple[str, ...] = ()
    prerelease: Tuple[str, ...] = ()
    if "+" in core:
        core, build_text = core.split("+", 1)
        build = tuple(build_text.split("."))
    if "-" in core:
        core, prerelease_text = core.split("-", 1)
        prerelease = tuple(prerelease_text.split("."))
    return core, prerelease, build


def _parse_spec(text: str, raw_range: str) -> _VersionSpec:
    """Parses a comparator target into numeric components and identifier tuples.

    Wildcard characters fill remaining components with None. Bare partial
    versions without wildcards are malformed range syntax and are rejected.
    """
    core, prerelease, build = _split_spec_text(text)
    parts = core.split(".")
    if not parts or len(parts) > 3:
        raise _invalid_range(raw_range, f"malformed version specifier {text!r}")

    numbers: List[Optional[int]] = []
    wildcard_seen = False
    for part in parts:
        if part in _WILDCARD_TOKENS:
            wildcard_seen = True
            numbers.append(None)
            continue
        if wildcard_seen:
            raise _invalid_range(
                raw_range, f"numeric component after wildcard in {text!r}"
            )
        if not part.isdigit():
            raise _invalid_range(
                raw_range, f"malformed numeric component {part!r} in {text!r}"
            )
        if len(part) > 1 and part[0] == "0":
            raise _invalid_range(raw_range, f"leading zero in version specifier {text!r}")
        numbers.append(int(part))

    if len(numbers) < 3:
        if not wildcard_seen:
            raise _invalid_range(
                raw_range,
                f"partial version {text!r} lacks wildcard characters",
            )
        numbers.extend([None] * (3 - len(numbers)))

    for identifier in prerelease:
        if _IDENTIFIER_PATTERN.match(identifier) is None:
            raise _invalid_range(
                raw_range, f"malformed prerelease identifier {identifier!r}"
            )
        if identifier.isdigit() and len(identifier) > 1 and identifier[0] == "0":
            raise _invalid_range(
                raw_range, f"leading zero in prerelease identifier {identifier!r}"
            )
    for identifier in build:
        if _IDENTIFIER_PATTERN.match(identifier) is None:
            raise _invalid_range(
                raw_range, f"malformed build metadata identifier {identifier!r}"
            )

    if (prerelease or build) and any(number is None for number in numbers):
        raise _invalid_range(
            raw_range,
            f"prerelease or build metadata requires a full version in {text!r}",
        )

    return (numbers[0], numbers[1], numbers[2], prerelease, build)


def _floor_version(spec: _VersionSpec) -> Optional[semver_solver.Version]:
    """Returns the inclusive lower boundary of a specifier, or None when unbounded."""
    major, minor, patch, prerelease, _build = spec
    if major is None:
        return None
    return semver_solver.Version(major, minor or 0, patch or 0, prerelease, ())


def _wildcard_upper(spec: _VersionSpec) -> Optional[semver_solver.Version]:
    """Returns the exclusive upper boundary of a wildcard specifier.

    The component immediately preceding the first wildcard is incremented and all
    following components are reset to zero (e.g. 1.2.x -> 1.3.0, 1.x -> 2.0.0).
    """
    major, minor, _patch, _prerelease, _build = spec
    if major is None:
        return None
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _caret_upper(spec: _VersionSpec) -> Optional[semver_solver.Version]:
    """Expands a caret prefix to its exclusive upper boundary.

    The left-most non-zero component may not change; when every supplied component
    is zero (or wildcard), the boundary advances the position before the first
    wildcard, or the patch component for an all-zero full version.
    """
    major, minor, patch, _prerelease, _build = spec
    if major is None:
        return None
    if major > 0:
        return semver_solver.Version(major + 1, 0, 0)
    if minor is not None and minor > 0:
        return semver_solver.Version(0, minor + 1, 0)
    if patch is not None and patch > 0:
        return semver_solver.Version(0, 0, patch + 1)
    if minor is None:
        return semver_solver.Version(1, 0, 0)
    if patch is None:
        return semver_solver.Version(0, 1, 0)
    return semver_solver.Version(0, 0, patch + 1)


def _tilde_upper(spec: _VersionSpec) -> Optional[semver_solver.Version]:
    """Expands a tilde prefix to its exclusive upper minor boundary."""
    major, minor, _patch, _prerelease, _build = spec
    if major is None:
        return None
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _wildcard_range_items(spec: _VersionSpec) -> _ComparatorClause:
    """Normalizes an equality wildcard specifier into paired boundary inequalities."""
    lower = _floor_version(spec)
    if lower is None:
        # A universal wildcard admits every precedence ordering.
        return []
    items: _ComparatorClause = [(">=", lower, lower)]
    upper = _wildcard_upper(spec)
    if upper is not None:
        items.append(("<", upper, upper))
    return items


def _wildcard_exclude_items(spec: _VersionSpec) -> _ComparatorClause:
    """Normalizes a wildcard exclusion into a single negated range comparator."""
    lower = _floor_version(spec)
    upper = _wildcard_upper(spec)
    if lower is None or upper is None:
        # Negating the universal wildcard admits no version at all.
        return [_FALSE_COMPARATOR]
    return [("!range", lower, upper)]


def _comparator_items(operator: str, spec: _VersionSpec) -> _ComparatorClause:
    """Expands one range comparator token into an explicit comparator list."""
    major, minor, patch, prerelease, _build = spec
    version: Optional[semver_solver.Version] = None
    if major is not None and minor is not None and patch is not None:
        version = semver_solver.Version(major, minor, patch, prerelease, ())

    if operator in ("==", "="):
        if version is not None:
            return [("==", version, version)]
        return _wildcard_range_items(spec)
    if operator == "!=":
        if version is not None:
            return [("!=", version, version)]
        return _wildcard_exclude_items(spec)
    if operator == ">":
        if version is not None:
            return [(">", version, version)]
        upper = _wildcard_upper(spec)
        if upper is None:
            return [_FALSE_COMPARATOR]
        return [(">=", upper, upper)]
    if operator == ">=":
        if version is not None:
            return [(">=", version, version)]
        lower = _floor_version(spec)
        if lower is None:
            return []
        return [(">=", lower, lower)]
    if operator == "<":
        if version is not None:
            return [("<", version, version)]
        lower = _floor_version(spec)
        if lower is None:
            return [_FALSE_COMPARATOR]
        return [("<", lower, lower)]
    if operator == "<=":
        if version is not None:
            return [("<=", version, version)]
        upper = _wildcard_upper(spec)
        if upper is None:
            return []
        return [("<", upper, upper)]
    if operator == "^":
        lower = _floor_version(spec)
        upper = _caret_upper(spec)
        caret_items: _ComparatorClause = []
        if lower is not None:
            caret_items.append((">=", lower, lower))
        if upper is not None:
            caret_items.append(("<", upper, upper))
        return caret_items
    if operator == "~":
        lower = _floor_version(spec)
        upper = _tilde_upper(spec)
        tilde_items: _ComparatorClause = []
        if lower is not None:
            tilde_items.append((">=", lower, lower))
        if upper is not None:
            tilde_items.append(("<", upper, upper))
        return tilde_items
    raise AssertionError(f"unsupported comparator operator: {operator}")


def _hyphen_items(left: _VersionSpec, right: _VersionSpec) -> _ComparatorClause:
    """Normalizes a hyphen range into inclusive lower and upper boundaries."""
    items: _ComparatorClause = []
    lower = _floor_version(left)
    if lower is not None:
        items.append((">=", lower, lower))

    right_major, right_minor, right_patch, right_prerelease, _right_build = right
    if (
        right_major is not None
        and right_minor is not None
        and right_patch is not None
    ):
        upper = semver_solver.Version(
            right_major, right_minor, right_patch, right_prerelease, ()
        )
        items.append(("<=", upper, upper))
    else:
        wildcard_upper = _wildcard_upper(right)
        if wildcard_upper is not None:
            items.append(("<", wildcard_upper, wildcard_upper))
    return items


def _expand_clause(clause: str, raw_range: str) -> _ComparatorClause:
    """Validates a whitespace-delimited clause and expands it into comparators."""
    tokens = clause.split()

    comparators: _ComparatorClause = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "-":
            raise _invalid_range(raw_range, "misplaced hyphen range separator")

        # Hyphen ranges are recognized before generic comparator parsing so that
        # the standalone '-' separator is never mistaken for version metadata.
        if (
            index + 2 < len(tokens)
            and tokens[index + 1] == "-"
            and _RANGE_OP_PATTERN.match(token) is None
        ):
            left = _parse_spec(token, raw_range)
            right = _parse_spec(tokens[index + 2], raw_range)
            comparators.extend(_hyphen_items(left, right))
            index += 3
            continue

        operator = "=="
        spec_text = token
        operator_match = _RANGE_OP_PATTERN.match(token)
        if operator_match is not None:
            operator = operator_match.group(1)
            spec_text = token[len(operator):]
            if spec_text == "":
                # Optional whitespace is permitted between operator and target.
                index += 1
                if index >= len(tokens):
                    raise _invalid_range(
                        raw_range, f"operator {operator!r} lacks a version specifier"
                    )
                spec_text = tokens[index]

        comparators.extend(_comparator_items(operator, _parse_spec(spec_text, raw_range)))
        index += 1

    return comparators


def _expand_range(raw_range: str) -> List[_ComparatorClause]:
    """Validates a range expression and compiles it into disjunctive comparator sets."""
    trimmed = raw_range.strip()
    if not trimmed:
        raise _invalid_range(raw_range, "range expression must not be empty")
    if "," in trimmed:
        raise _invalid_range(raw_range, "comma delimiters are not permitted")

    clauses: List[_ComparatorClause] = []
    for clause_text in trimmed.split("||"):
        clause = clause_text.strip()
        if not clause:
            raise _invalid_range(raw_range, "range expression contains an empty union clause")
        clauses.append(_expand_clause(clause, raw_range))
    return clauses


def _comparator_matches(
    compare: Callable[[semver_solver.Version, semver_solver.Version], int],
    version: semver_solver.Version,
    comparator: _Comparator,
) -> bool:
    """Evaluates one expanded comparator against a candidate version."""
    operator, lower, upper = comparator
    if operator == "false":
        return False
    if operator == "!range":
        return not (
            compare(version, lower) >= 0 and compare(version, upper) < 0
        )
    ordering = compare(version, lower)
    if operator == "==":
        return ordering == 0
    if operator == "!=":
        return ordering != 0
    if operator == "<":
        return ordering < 0
    if operator == "<=":
        return ordering <= 0
    if operator == ">":
        return ordering > 0
    if operator == ">=":
        return ordering >= 0
    raise AssertionError(f"unsupported expanded comparator: {operator}")


def _clause_targets_prerelease(
    clause: _ComparatorClause,
    version: semver_solver.Version,
) -> bool:
    """Checks whether a clause explicitly targets the candidate prerelease version."""
    target = (version.major, version.minor, version.patch)
    for _operator, lower, upper in clause:
        for boundary in (lower, upper):
            if boundary is None or not boundary.is_prerelease:
                continue
            if (boundary.major, boundary.minor, boundary.patch) == target:
                return True
    return False


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # Validates full SemVer 2.0.0 grammar, including leading zero constraints.
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                f"Invalid semantic version string: {text!r}", text
            )
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        build = tuple(match.group(5).split(".")) if match.group(5) else ()
        return semver_solver.Version(major, minor, patch, prerelease, build)

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        # Numeric core components compare numerically in sequence.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return -1 if left < right else 1

        # A normal version outranks a prerelease sharing the same numeric core.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1

        # Positional prerelease segment comparison, ignoring build metadata.
        for left_identifier, right_identifier in zip(v1.prerelease, v2.prerelease):
            ordering = _compare_identifiers(left_identifier, right_identifier)
            if ordering != 0:
                return ordering
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return 1 if len(v1.prerelease) > len(v2.prerelease) else -1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Validate the whole expression, but retain the trimmed canonical text.
        _expand_range(text)
        return semver_solver.VersionRange(text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Compile the range into disjunctive normal form comparator sets.
        clauses = _expand_range(range_constraint.raw_text)
        for clause in clauses:
            if not all(
                _comparator_matches(self.compare_precedence, version, comparator)
                for comparator in clause
            ):
                continue
            # Prerelease candidates require explicit targeting when not opted in.
            if version.is_prerelease and not include_prerelease:
                if not _clause_targets_prerelease(clause, version):
                    continue
            return True
        return False


def _compare_identifiers(left: str, right: str) -> int:
    """Compares two prerelease identifiers with SemVer numeric/ASCII rules."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
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


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Private backing storage maps package names to precedence-sorted releases.
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # Register then restore descending precedence ordering via the engine.
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(
                    right.version, left.version
                )
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # Missing packages surface as a contracted PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                f"Package '{name}' is not registered", name
            )
        # Expose a shallow copy so callers cannot mutate internal ordering.
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
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraint mapping seeded from the root requirements.
        accumulated: Dict[
            str, List[Tuple[str, semver_solver.VersionRange]]
        ] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def candidates_for(name: str) -> List[semver_solver.PackageRelease]:
            # Unregistered packages have zero candidates instead of leaking errors.
            try:
                releases = repository.get_releases(name)
            except semver_solver.PackageNotFoundError:
                return []
            return [
                release
                for release in releases
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _requester, constraint in accumulated[name]
                )
            ]

        def backtrack() -> bool:
            unassigned = [
                name for name in accumulated if name not in assignment
            ]
            if not unassigned:
                return True

            # Minimum Remaining Values selection with lexical tie-breaking.
            viable: Dict[str, List[semver_solver.PackageRelease]] = {}
            for name in unassigned:
                viable[name] = candidates_for(name)
            selected = min(unassigned, key=lambda name: (len(viable[name]), name))
            candidates = viable[selected]

            if not candidates:
                requesters = sorted(
                    {requester for requester, _ in accumulated[selected]}
                )
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints "
                    f"from {requesters}"
                )
                return False

            # Value ordering explores the highest precedence candidates first.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(
                    f"Assign '{selected}' to {candidate.version}"
                )
                newly_added: List[
                    Tuple[str, Tuple[str, semver_solver.VersionRange]]
                ] = []
                conflict_detected = False

                # Forward checking merges candidate dependencies into constraints.
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires "
                                f"{dependency.name} "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and backtrack():
                    return True

                # Restore the accumulated constraints and pop the decision.
                for name, entry in newly_added:
                    accumulated[name].remove(entry)
                    if not accumulated[name]:
                        del accumulated[name]
                del assignment[selected]
                derivation_steps.pop()

            # All candidate releases failed to yield a complete assignment.
            conflicting_packages.add(selected)
            conflict_trail.append(
                f"Exhausted all releases for '{selected}' without a complete assignment"
            )
            return False

        if not backtrack():
            explanation = (
                "\n".join(conflict_trail)
                if conflict_trail
                else "No compatible release assignment found"
            )
            raise semver_solver.ResolutionConflictError(
                f"Dependency resolution failed: {explanation}",
                tuple(sorted(conflicting_packages)),
                explanation,
            )

        # Compile the successful assignment into the contracted outcome record.
        selected_versions: Dict[str, semver_solver.Version] = {
            name: release.version for name, release in assignment.items()
        }
        return semver_solver.ResolutionOutcome(
            selected_versions, tuple(derivation_steps)
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
# LAST_CLEANED: 2026-11-05T04:37:51Z
# LAST_CHANGED: 2026-11-05T04:35:34Z
# CHANGE: Fixed universal-wildcard negation: _wildcard_exclude_items now emits the unsatisfiable sentinel comparator when the excluded specifier has no finite boundaries (e.g. !=*), so a negated universal wildcard matches no version instead of vacuously matching everything. Audited sibling wildcard relational expansions for the same defect; !range still handles finite exclusions such as !=1.x. Static checks pass.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:37:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:37:39Z
# --- END AUTOFAB METADATA ---
