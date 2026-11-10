# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_221341_deepseek-flash_semver_solver_combined
# Timestamp: 2026-11-09T22:13:41.018260+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 507,347
#   Cached Inbound Tokens:   26,469,888
#   Outbound Tokens:         405,776
#   Total Tokens:            27,383,011
#   Financial Cost ($USD):   $0.3990
#   Wall Clock Duration:     1674.18s
#   Step Latencies (s):      [189.0, 381.7, 418.6, 94.8, 117.7, 63.9, 20.4, 140.9, 10.0, 256.7, 190.1, 108.1, 188.5, 211.6, 10.1, 74.5, 154.2, 74.8, 118.5, 20.4, 12.5, 20.4, 118.0, 228.0, 20.3, 20.3]
#   Role Execution Rounds:   coverage: 3, lib: 2, pretense: 5, pretense_coverage: 3, pretense_qa: 5, qa: 4, test: 4 (Total: 26)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       42
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
        """Indicates whether this version contains pre-release identifiers."""
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        text = f'{self.major}.{self.minor}.{self.patch}'
        if self.prerelease:
            text = f'{text}-{".".join(self.prerelease)}'
        if self.build:
            text = f'{text}+{".".join(self.build)}'
        return text

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
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        ...

    @operation
    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
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
# LAST_CLEANED: 2026-11-09T22:20:53Z
# LAST_CHANGED: 2026-11-09T22:20:53Z
# CHANGE: Initialize the semver_solver interface module: define SemVerError/InvalidVersionError/InvalidRangeError/ResolutionConflictError/PackageNotFoundError as non-frozen dataclass exceptions with __str__ delegation, ComparatorOp enum, frozen @data_type records (Version with is_prerelease/format/__str__, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome), and @poly_type Protocol services (VersionEngine, PackageRepository, DependencySolver) with @operation stubs matching low/semver_solver.pyi.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
import re
from dataclasses import dataclass
from functools import cmp_to_key

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

# SemVer 2.0.0 grammar fragments (see low/semver_solver.pyi parse_version contract).
_NUMERIC_CORE = r'(?:0|[1-9][0-9]*)'
_PRERELEASE_IDENTIFIER = rf'(?:{_NUMERIC_CORE}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)'
_BUILD_IDENTIFIER = r'[0-9A-Za-z-]+'
_VERSION_PATTERN = re.compile(
    rf'^(?P<major>{_NUMERIC_CORE})'
    rf'\.(?P<minor>{_NUMERIC_CORE})'
    rf'\.(?P<patch>{_NUMERIC_CORE})'
    rf'(?:-(?P<prerelease>{_PRERELEASE_IDENTIFIER}(?:\.{_PRERELEASE_IDENTIFIER})*))?'
    rf'(?:\+(?P<build>{_BUILD_IDENTIFIER}(?:\.{_BUILD_IDENTIFIER})*))?$'
)
_DECIMAL_DIGITS = re.compile(r'^[0-9]+$')
_PRERELEASE_NUMERIC = re.compile(r'^(?:0|[1-9][0-9]*)$')
_PRERELEASE_ALPHANUMERIC = re.compile(r'^[0-9]*[A-Za-z-][0-9A-Za-z-]*$')
_BUILD_IDENTIFIER_PATTERN = re.compile(r'^[0-9A-Za-z-]+$')

_WILDCARD_TOKENS = frozenset(('x', 'X', '*'))


@dataclass(frozen=True)
class _RangeBound:
    """Parsed version or wildcard bound appearing inside a range expression."""

    components: Tuple[Optional[int], Optional[int], Optional[int]]
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_wildcard(self) -> bool:
        return any(component is None for component in self.components)


@dataclass(frozen=True)
class _Comparator:
    """Primitive comparator produced by normalizing a range expression."""

    op: semver_solver.ComparatorOp
    version: semver_solver.Version


# A compiled range is a disjunction (union) of conjunctive comparator clauses.
_DNF = List[List[_Comparator]]


def _invalid_range(message: str, raw_range: str) -> semver_solver.InvalidRangeError:
    return semver_solver.InvalidRangeError(message, raw_range)


def _invalid_version(message: str, raw_text: str) -> semver_solver.InvalidVersionError:
    return semver_solver.InvalidVersionError(message, raw_text)


def _parse_prerelease_identifiers(text: str, raw_range: str) -> Tuple[str, ...]:
    identifiers = text.split('.')
    for identifier in identifiers:
        if not identifier:
            raise _invalid_range(f"Empty pre-release identifier in '{raw_range}'", raw_range)
        if _PRERELEASE_NUMERIC.fullmatch(identifier):
            # Numeric pre-release identifiers are legal as long as they lack leading zeroes.
            continue
        if _PRERELEASE_ALPHANUMERIC.fullmatch(identifier):
            continue
        raise _invalid_range(f"Malformed pre-release identifier '{identifier}' in '{raw_range}'", raw_range)
    return tuple(identifiers)


def _parse_build_identifiers(text: str, raw_range: str) -> Tuple[str, ...]:
    identifiers = text.split('.')
    for identifier in identifiers:
        if not _BUILD_IDENTIFIER_PATTERN.fullmatch(identifier):
            raise _invalid_range(f"Malformed build identifier '{identifier}' in '{raw_range}'", raw_range)
    return tuple(identifiers)


def _parse_bound(text: str, raw_range: str) -> _RangeBound:
    """Parses a single version or wildcard bound, rejecting bare partial versions."""
    core = text
    build: Tuple[str, ...] = ()
    prerelease: Tuple[str, ...] = ()

    plus_index = core.find('+')
    if plus_index >= 0:
        build_text = core[plus_index + 1:]
        core = core[:plus_index]
        if not build_text:
            raise _invalid_range(f"Empty build metadata in '{raw_range}'", raw_range)
        build = _parse_build_identifiers(build_text, raw_range)

    hyphen_index = core.find('-')
    if hyphen_index >= 0:
        prerelease_text = core[hyphen_index + 1:]
        core = core[:hyphen_index]
        if not prerelease_text:
            raise _invalid_range(f"Empty pre-release identifier in '{raw_range}'", raw_range)
        prerelease = _parse_prerelease_identifiers(prerelease_text, raw_range)

    pieces = core.split('.')
    if len(pieces) > 3:
        raise _invalid_range(f"Too many version components in '{raw_range}'", raw_range)

    components: List[Optional[int]] = []
    wildcard_seen = False
    for piece in pieces:
        if piece in _WILDCARD_TOKENS:
            wildcard_seen = True
            components.append(None)
            continue
        if wildcard_seen:
            raise _invalid_range(f"Numeric component after wildcard in '{raw_range}'", raw_range)
        if not piece or not _DECIMAL_DIGITS.fullmatch(piece):
            raise _invalid_range(f"Malformed version component '{piece}' in '{raw_range}'", raw_range)
        if len(piece) > 1 and piece[0] == '0':
            raise _invalid_range(f"Leading zero in version component '{piece}' in '{raw_range}'", raw_range)
        components.append(int(piece))

    if wildcard_seen:
        # Wildcard expressions cannot carry pre-release or build metadata.
        if prerelease or build:
            raise _invalid_range(
                f"Wildcard bound cannot declare pre-release or build metadata in '{raw_range}'",
                raw_range,
            )
    elif len(components) != 3:
        # Bare partial versions lacking wildcard characters are prohibited.
        raise _invalid_range(
            f"Bare partial version '{text}' lacks a wildcard in '{raw_range}'",
            raw_range,
        )

    padded: Tuple[Optional[int], Optional[int], Optional[int]] = (
        components[0] if len(components) > 0 else None,
        components[1] if len(components) > 1 else None,
        components[2] if len(components) > 2 else None,
    )
    return _RangeBound(padded, prerelease, build)


def _bound_version(bound: _RangeBound) -> semver_solver.Version:
    major, minor, patch = bound.components
    return semver_solver.Version(
        0 if major is None else major,
        0 if minor is None else minor,
        0 if patch is None else patch,
        bound.prerelease,
        bound.build,
    )


def _wildcard_lower(bound: _RangeBound) -> semver_solver.Version:
    major, minor, patch = bound.components
    return semver_solver.Version(major or 0, minor or 0, patch or 0)


def _wildcard_upper(bound: _RangeBound) -> Optional[semver_solver.Version]:
    major, minor, _patch = bound.components
    if major is None:
        return None
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _caret_upper(bound: _RangeBound) -> semver_solver.Version:
    major, minor, patch = bound.components
    if major is None:  # unreachable (assumption: caret on '*' is handled by the caller)
        raise AssertionError("caret upper bound requires a concrete major component")
    if major > 0:
        return semver_solver.Version(major + 1, 0, 0)
    if minor is None:
        return semver_solver.Version(1, 0, 0)
    if minor > 0:
        return semver_solver.Version(0, minor + 1, 0)
    if patch is None:
        return semver_solver.Version(0, 1, 0)
    return semver_solver.Version(0, 0, patch + 1)


def _tilde_upper(bound: _RangeBound) -> semver_solver.Version:
    major, minor, _patch = bound.components
    if major is None:  # unreachable (assumption: tilde on '*' is handled by the caller)
        raise AssertionError("tilde upper bound requires a concrete major component")
    if minor is None:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _conjunction(*comparators: _Comparator) -> _DNF:
    return [list(comparators)]


def _cross(left: _DNF, right: _DNF) -> _DNF:
    return [left_clause + right_clause for left_clause in left for right_clause in right]


def _expand(kind: str, bound: _RangeBound) -> _DNF:
    """Normalizes one range term into disjunctive normal form comparator clauses."""
    op = semver_solver.ComparatorOp

    if not bound.is_wildcard:
        version = _bound_version(bound)
        if kind == '==':
            return _conjunction(_Comparator(op.EQ, version))
        if kind == '!=':
            return _conjunction(_Comparator(op.NE, version))
        if kind == '<':
            return _conjunction(_Comparator(op.LT, version))
        if kind == '<=':
            return _conjunction(_Comparator(op.LE, version))
        if kind == '>':
            return _conjunction(_Comparator(op.GT, version))
        if kind == '>=':
            return _conjunction(_Comparator(op.GE, version))
        if kind == '^':
            return _conjunction(_Comparator(op.GE, version), _Comparator(op.LT, _caret_upper(bound)))
        if kind == '~':
            return _conjunction(_Comparator(op.GE, version), _Comparator(op.LT, _tilde_upper(bound)))
        raise AssertionError(f"Unsupported range operator '{kind}'")  # unreachable (assumption: _split_operator yields only supported operators)

    major, _minor, _patch = bound.components
    lower = _wildcard_lower(bound)
    upper = _wildcard_upper(bound)

    if kind == '==':
        if upper is None:
            return [[]]
        return _conjunction(_Comparator(op.GE, lower), _Comparator(op.LT, upper))
    if kind == '!=':
        if upper is None:
            return []
        return [[_Comparator(op.LT, lower)], [_Comparator(op.GE, upper)]]
    if kind == '<':
        if major is None:
            return []
        return _conjunction(_Comparator(op.LT, lower))
    if kind == '<=':
        if upper is None:
            return [[]]
        return _conjunction(_Comparator(op.LT, upper))
    if kind == '>':
        if upper is None:
            return []
        return _conjunction(_Comparator(op.GE, upper))
    if kind == '>=':
        if major is None:
            return [[]]
        return _conjunction(_Comparator(op.GE, lower))
    if kind == '^':
        if major is None:
            return [[]]
        return _conjunction(_Comparator(op.GE, lower), _Comparator(op.LT, _caret_upper(bound)))
    if kind == '~':
        if major is None:
            return [[]]
        return _conjunction(_Comparator(op.GE, lower), _Comparator(op.LT, _tilde_upper(bound)))
    raise AssertionError(f"Unsupported range operator '{kind}'")  # unreachable (assumption: _split_operator yields only supported operators)


def _hyphen_lower(bound: _RangeBound) -> _DNF:
    op = semver_solver.ComparatorOp
    if bound.is_wildcard:
        if bound.components[0] is None:
            return [[]]
        return _conjunction(_Comparator(op.GE, _wildcard_lower(bound)))
    return _conjunction(_Comparator(op.GE, _bound_version(bound)))


def _hyphen_upper(bound: _RangeBound) -> _DNF:
    op = semver_solver.ComparatorOp
    if bound.is_wildcard:
        upper = _wildcard_upper(bound)
        if upper is None:
            return [[]]
        return _conjunction(_Comparator(op.LT, upper))
    return _conjunction(_Comparator(op.LE, _bound_version(bound)))


def _split_operator(token: str) -> Tuple[str, str]:
    for candidate in ('==', '!=', '<=', '>='):
        if token.startswith(candidate):
            return candidate, token[len(candidate):]
    for candidate in ('=', '<', '>', '^', '~'):
        if token.startswith(candidate):
            kind = '==' if candidate == '=' else candidate
            return kind, token[1:]
    return '==', token


def _compile_clause(text: str, raw_range: str) -> _DNF:
    # Callers pass a non-empty, whitespace-stripped clause, so tokenization always yields tokens.
    tokens = text.split()

    if '-' in tokens:
        if len(tokens) != 3 or tokens[1] != '-':
            raise _invalid_range(f"Malformed hyphen range in '{raw_range}'", raw_range)
        lower_bound = _parse_bound(tokens[0], raw_range)
        upper_bound = _parse_bound(tokens[2], raw_range)
        return _cross(_hyphen_lower(lower_bound), _hyphen_upper(upper_bound))

    parsed: List[Tuple[str, _RangeBound]] = []
    index = 0
    while index < len(tokens):
        kind, remainder = _split_operator(tokens[index])
        if not remainder:
            index += 1
            if index >= len(tokens):
                raise _invalid_range(f"Operator '{tokens[index - 1]}' lacks an operand in '{raw_range}'", raw_range)
            remainder = tokens[index]
        parsed.append((kind, _parse_bound(remainder, raw_range)))
        index += 1

    dnf: _DNF = [[]]
    for kind, bound in parsed:
        dnf = _cross(dnf, _expand(kind, bound))
    return dnf


def _compile_range(text: str) -> _DNF:
    """Validates a range expression and normalizes it to disjunctive normal form."""
    if not text.strip():
        raise _invalid_range("Version range must not be empty", text)
    if ',' in text:
        raise _invalid_range("Comma delimiters are not permitted in version ranges", text)

    dnf: _DNF = []
    for clause in text.split('||'):
        clause_text = clause.strip()
        if not clause_text:
            raise _invalid_range("Empty union clause in version range", text)
        dnf.extend(_compile_clause(clause_text, text))
    return dnf


def _is_numeric_identifier(identifier: str) -> bool:
    return _PRERELEASE_NUMERIC.fullmatch(identifier) is not None


def _compare_precedence(v1: semver_solver.Version, v2: semver_solver.Version) -> int:
    """Evaluates SemVer 2.0.0 precedence, ignoring build metadata."""
    if v1.major != v2.major:
        return v1.major - v2.major
    if v1.minor != v2.minor:
        return v1.minor - v2.minor
    if v1.patch != v2.patch:
        return v1.patch - v2.patch

    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1

    for left, right in zip(v1.prerelease, v2.prerelease):
        if left == right:
            continue
        left_numeric = _is_numeric_identifier(left)
        right_numeric = _is_numeric_identifier(right)
        if left_numeric and right_numeric:
            return int(left) - int(right)
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left < right else 1
    return len(v1.prerelease) - len(v2.prerelease)


def _parse_version_text(text: str) -> semver_solver.Version:
    """Parses a SemVer 2.0.0 string, enforcing the official grammar."""
    match = _VERSION_PATTERN.fullmatch(text)
    if match is None:
        raise _invalid_version(f"'{text}' does not conform to SemVer 2.0.0", text)

    prerelease_text = match.group('prerelease')
    build_text = match.group('build')
    return semver_solver.Version(
        int(match.group('major')),
        int(match.group('minor')),
        int(match.group('patch')),
        tuple(prerelease_text.split('.')) if prerelease_text else (),
        tuple(build_text.split('.')) if build_text else (),
    )


def _comparator_satisfied(version: semver_solver.Version, comparator: _Comparator) -> bool:
    precedence = _compare_precedence(version, comparator.version)
    op = comparator.op
    if op is semver_solver.ComparatorOp.EQ:
        return precedence == 0
    if op is semver_solver.ComparatorOp.NE:
        return precedence != 0
    if op is semver_solver.ComparatorOp.LT:
        return precedence < 0
    if op is semver_solver.ComparatorOp.LE:
        return precedence <= 0
    if op is semver_solver.ComparatorOp.GT:
        return precedence > 0
    if op is semver_solver.ComparatorOp.GE:
        return precedence >= 0
    return False  # unreachable (assumption: ComparatorOp is exhaustive)


def _clause_satisfied(
    version: semver_solver.Version,
    clause: Sequence[_Comparator],
    include_prerelease: bool,
) -> bool:
    for comparator in clause:
        if not _comparator_satisfied(version, comparator):
            return False

    # Pre-release filtering: a pre-release candidate only matches when the range
    # explicitly targets a pre-release sharing its major/minor/patch tuple.
    if version.is_prerelease and not include_prerelease:
        for comparator in clause:
            target = comparator.version
            if (
                target.prerelease
                and target.major == version.major
                and target.minor == version.minor
                and target.patch == version.patch
            ):
                return True
        return False
    return True


def _range_satisfied(
    version: semver_solver.Version,
    range_constraint: semver_solver.VersionRange,
    include_prerelease: bool,
) -> bool:
    for clause in _compile_range(range_constraint.raw_text):
        if _clause_satisfied(version, clause, include_prerelease):
            return True
    return False


@singleton_type('system')
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # Parse the text into an immutable Version record; grammar and leading-zero
        # violations propagate as InvalidVersionError.
        return _parse_version_text(text)

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # Tri-state comparison under SemVer precedence rules; build metadata never participates.
        return _compare_precedence(v1, v2)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Validate every clause eagerly, then retain the trimmed expression.
        _compile_range(text)
        return semver_solver.VersionRange(raw_text=text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # True when any union clause matches; pre-release filtering happens per clause.
        return _range_satisfied(version, range_constraint, include_prerelease)


@singleton_type('system')
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # Append the release, then keep the package list in precedence-descending order.
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)

        def descending(left: semver_solver.PackageRelease, right: semver_solver.PackageRelease) -> int:
            return engine.compare_precedence(right.version, left.version)

        releases.sort(key=cmp_to_key(descending))

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # Unknown package names raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(f"Package '{name}' is not registered", name)
        # Hand back a shallow copy of the sorted release list.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # Membership test over registered package names.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # Every registered package name.
        return set(self._packages.keys())


@singleton_type('system')
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        pass

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to (requester, range) obligations.
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(('root', dependency.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        attempt_log: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def candidates_for(package: str) -> List[semver_solver.PackageRelease]:
            try:
                available = repository.get_releases(package)
            except semver_solver.PackageNotFoundError:
                # Missing packages behave as packages with zero candidate releases.
                return []
            viable = [
                release
                for release in available
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated[package]
                )
            ]

            def descending(left: semver_solver.PackageRelease, right: semver_solver.PackageRelease) -> int:
                return engine.compare_precedence(right.version, left.version)

            # Value ordering: descending version precedence, highest version first.
            return sorted(viable, key=cmp_to_key(descending))

        def backtrack() -> bool:
            unassigned = [package for package in accumulated if package not in assignment]
            if not unassigned:
                return True

            candidates_by_package = {package: candidates_for(package) for package in unassigned}
            # Minimum Remaining Values heuristic with lexical tie-breaking.
            selected = min(unassigned, key=lambda package: (len(candidates_by_package[package]), package))
            candidates = candidates_by_package[selected]

            if not candidates:
                requesters = [requester for requester, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requester for requester in requesters if requester != 'root')
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False

            # Value ordering: descending version precedence as produced by the repository.
            for candidate in candidates:
                assignment[selected] = candidate
                step = f"Assign '{selected}' to {candidate.version}"
                derivation_steps.append(step)
                attempt_log.append(step)

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
                        entry: Tuple[str, semver_solver.VersionRange] = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and backtrack():
                    return True

                for package, entry in newly_added:
                    accumulated[package].remove(entry)
                    if not accumulated[package]:
                        del accumulated[package]
                del assignment[selected]
                derivation_steps.pop()

            return False

        if not backtrack():
            explanation_lines = list(conflict_trail)
            if attempt_log:
                explanation_lines.append('Attempted assignments:')
                explanation_lines.extend(attempt_log)
            raise semver_solver.ResolutionConflictError(
                "Dependency constraints cannot be satisfied mutually",
                tuple(sorted(conflicting_packages)),
                '\n'.join(explanation_lines),
            )

        # Descending candidate ordering yields the highest compatible versions.
        selected_versions = {
            package: assignment[package].version for package in sorted(assignment)
        }
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
# LAST_CLEANED: 2026-11-09T22:41:22Z
# LAST_CHANGED: 2026-11-09T22:30:00Z
# CHANGE: Resolve coverage feedback on unreachable logic in semver_solver_impl.py: prune the duplicate empty-operand guard in _parse_bound (callers always pass non-empty clause/operator tokens, so empty bounds cannot occur) and the duplicate empty-token guard in _compile_clause (clauses are already whitespace-stripped and non-empty before tokenization); malformed empty inputs still raise InvalidRangeError through the malformed-component path in _parse_bound. Annotate the unreachable internal invariant raises in _expand with '# unreachable (assumption: _split_operator yields only supported operators)'.
# COVERAGE_AUDIT: 2026-11-09T22:35:48Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:41:22Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:40:59Z
# QA_AUDIT: 2026-11-09T22:35:30Z
# --- END AUTOFAB METADATA ---
