# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261107_192010_deepseek-flash_semver_solver
# Timestamp: 2026-11-07T19:20:10.375270+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 227,139
#   Cached Inbound Tokens:   9,192,320
#   Outbound Tokens:         197,145
#   Total Tokens:            9,616,604
#   Financial Cost ($USD):   $0.1799
#   Wall Clock Duration:     1247.14s
#   Step Latencies (s):      [193.6, 470.6, 42.5, 61.0, 40.6, 163.0, 93.7, 152.9, 40.6, 103.7, 81.4, 40.6, 40.6]
#   Role Execution Rounds:   coverage: 3, lib: 3, qa: 4, test: 3 (Total: 13)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       55
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Interface definitions for SemVer 2.0.0 parsing and dependency resolution."""

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
        """Returns the diagnostic message describing this error."""
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
        # POSTCONDITION: major.minor.patch plus optional prerelease and build suffixes.
        formatted = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            formatted = f"{formatted}-{'.'.join(self.prerelease)}"
        if self.build:
            formatted = f"{formatted}+{'.'.join(self.build)}"
        return formatted

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
    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
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
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T19:27:59Z
# LAST_CHANGED: 2026-11-07T19:27:59Z
# CHANGE: Implement SemVer 2.0 interface: concrete Version.format/is_prerelease/__str__, VersionRange.__str__, dataclass error classes with __str__, poly_type protocol stubs
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete realization of SemVer 2.0.0 parsing, precedence, and dependency resolution."""

from __future__ import annotations
from functools import cmp_to_key
import re
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

# SemVer 2.0.0 grammar (https://semver.org) enforcing numeric leading-zero constraints.
_SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)

# Wildcard expression grammar: up to three dot-separated numeric or wildcard components.
_WILDCARD_PATTERN = re.compile(
    r"(?P<major>0|[1-9]\d*|[xX*])"
    r"(?:\.(?P<minor>0|[1-9]\d*|[xX*]))?"
    r"(?:\.(?P<patch>0|[1-9]\d*|[xX*]))?"
)

_COMPARATOR_OPERATORS: Tuple[str, ...] = ('==', '!=', '<=', '>=', '<', '>', '=', '^', '~')
_OPERATOR_ALIASES: Dict[str, str] = {'=': '=='}
_WILDCARD_TOKENS: FrozenSet[str] = frozenset({'x', 'X', '*'})

# Clause token grammar: an optional relational/prefix operator followed by its operand.
_CLAUSE_TOKEN_PATTERN = re.compile(r"(==|!=|<=|>=|<|>|=|\^|~)?(\S+)")

# Comparator atom: (kind, operator, bound, upper bound) where kind is one of
# 'cmp', 'not_interval', 'always', or 'never'.
_Atom = Tuple[str, str, Optional[semver_solver.Version], Optional[semver_solver.Version]]
# Wildcard components as (major, minor, patch) where None marks a wildcard position.
_Components = Tuple[Optional[int], Optional[int], Optional[int]]


def _version_from_match(match: re.Match[str]) -> semver_solver.Version:
    """Builds an immutable Version record from a SemVer grammar match."""
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    prerelease: Tuple[str, ...] = tuple(prerelease_text.split('.')) if prerelease_text else ()
    build: Tuple[str, ...] = tuple(build_text.split('.')) if build_text else ()
    return semver_solver.Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=prerelease,
        build=build,
    )


def _compare_prerelease_identifiers(left: str, right: str) -> int:
    """Compares two pre-release identifiers using SemVer 2.0.0 precedence rules."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    # POSTCONDITION: numeric identifiers compare numerically and rank below alphanumeric ones.
    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        if left_value != right_value:
            return -1 if left_value < right_value else 1
        return 0
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    # POSTCONDITION: alphanumeric identifiers compare ASCII-lexicographically.
    if left == right:
        return 0
    return -1 if left < right else 1


def _filled_version(components: _Components) -> Optional[semver_solver.Version]:
    """Produces the inclusive lower bound of a wildcard expression, filling wildcards with zeroes."""
    major, minor, patch = components
    if major is None:
        return None
    return semver_solver.Version(major=major, minor=minor or 0, patch=patch or 0)


def _wildcard_upper(components: _Components) -> Optional[semver_solver.Version]:
    """Produces the exclusive upper bound of a wildcard expression."""
    if components[0] is None:
        return None
    for index in range(1, 3):
        if components[index] is None:
            numbers = [component if component is not None else 0 for component in components]
            numbers[index - 1] += 1
            for position in range(index, 3):
                numbers[position] = 0
            return semver_solver.Version(major=numbers[0], minor=numbers[1], patch=numbers[2])
    # Unreachable by the wildcard grammar: every wildcard target retains an unresolved component.
    return None  # pragma: no cover (assumption: wildcard targets always retain an unresolved component)


def _parse_target(token: str, raw_range: str) -> Tuple[_Components, Optional[semver_solver.Version]]:
    """Parses a comparator operand into wildcard components plus an exact Version when available."""
    version_match = _SEMVER_PATTERN.fullmatch(token)
    if version_match is not None:
        version = _version_from_match(version_match)
        return (version.major, version.minor, version.patch), version
    wildcard_match = _WILDCARD_PATTERN.fullmatch(token)
    if wildcard_match is None:
        raise semver_solver.InvalidRangeError(
            message=f"Malformed version or wildcard expression: {token!r}",
            raw_range=raw_range,
        )
    parsed: List[Optional[int]] = []
    explicit_wildcard = False
    for raw_component in (
        wildcard_match.group("major"),
        wildcard_match.group("minor"),
        wildcard_match.group("patch"),
    ):
        if raw_component is None:
            break
        if raw_component in _WILDCARD_TOKENS:
            # PRECONDITION: wildcard components must be trailing ('1.x' is valid, '1.x.2' is not).
            explicit_wildcard = True
            parsed.append(None)
        else:
            if any(component is None for component in parsed):
                raise semver_solver.InvalidRangeError(
                    message=f"Wildcard components must be trailing in {token!r}",
                    raw_range=raw_range,
                )
            parsed.append(int(raw_component))
    # PRECONDITION: bare partial versions ('1', '1.2') are malformed without wildcard characters.
    if not explicit_wildcard:
        raise semver_solver.InvalidRangeError(
            message=f"Partial version {token!r} must specify a wildcard component",
            raw_range=raw_range,
        )
    while len(parsed) < 3:
        parsed.append(None)
    return (parsed[0], parsed[1], parsed[2]), None


def _caret_atoms(components: _Components, exact_version: Optional[semver_solver.Version]) -> List[_Atom]:
    """Expands a caret range into lower and upper comparator atoms."""
    major, minor, patch = components
    # POSTCONDITION: caret ranges permit changes that do not modify the left-most non-zero component.
    if major is None:
        return [('always', '', None, None)]
    lower = exact_version if exact_version is not None else semver_solver.Version(
        major=major, minor=minor or 0, patch=patch or 0
    )
    if exact_version is not None:
        if major > 0:
            upper = semver_solver.Version(major=major + 1, minor=0, patch=0)
        elif minor is not None and minor > 0:
            upper = semver_solver.Version(major=0, minor=minor + 1, patch=0)
        else:
            upper = semver_solver.Version(major=0, minor=0, patch=(patch or 0) + 1)
    elif minor is None:
        upper = semver_solver.Version(major=major + 1, minor=0, patch=0)
    elif major == 0:
        upper = semver_solver.Version(major=0, minor=minor + 1, patch=0)
    else:
        upper = semver_solver.Version(major=major + 1, minor=0, patch=0)
    return [('cmp', '>=', lower, None), ('cmp', '<', upper, None)]


def _tilde_atoms(components: _Components, exact_version: Optional[semver_solver.Version]) -> List[_Atom]:
    """Expands a tilde range into lower and upper comparator atoms."""
    major, minor, _patch = components
    # POSTCONDITION: tilde ranges permit patch-level changes while holding the minor boundary.
    if major is None:
        return [('always', '', None, None)]
    lower = exact_version if exact_version is not None else semver_solver.Version(
        major=major, minor=minor or 0, patch=_patch or 0
    )
    if minor is None:
        upper = semver_solver.Version(major=major + 1, minor=0, patch=0)
    else:
        upper = semver_solver.Version(major=major, minor=minor + 1, patch=0)
    return [('cmp', '>=', lower, None), ('cmp', '<', upper, None)]


def _expand_comparator(operator: Optional[str], token: str, raw_range: str) -> List[_Atom]:
    """Expands a single comparator into conjunctive comparison atoms."""
    components, exact_version = _parse_target(token, raw_range)
    op = '==' if operator is None else _OPERATOR_ALIASES.get(operator, operator)
    if op == '^':
        return _caret_atoms(components, exact_version)
    if op == '~':
        return _tilde_atoms(components, exact_version)
    if exact_version is not None:
        return [('cmp', op, exact_version, None)]
    lower = _filled_version(components)
    upper = _wildcard_upper(components)
    if op == '==':
        # POSTCONDITION: wildcard equality denotes the half-open interval [lower, upper).
        atoms: List[_Atom] = []
        if lower is not None:
            atoms.append(('cmp', '>=', lower, None))
        if upper is not None:
            atoms.append(('cmp', '<', upper, None))
        if not atoms:
            atoms.append(('always', '', None, None))
        return atoms
    if op == '!=':
        # POSTCONDITION: wildcard inequality excludes the entire wildcard interval.
        if lower is None and upper is None:
            return [('never', '', None, None)]
        return [('not_interval', '', lower, upper)]
    if op == '>=':
        if lower is None:
            return [('always', '', None, None)]
        return [('cmp', '>=', lower, None)]
    if op == '>':
        if upper is None:
            return [('never', '', None, None)]
        return [('cmp', '>=', upper, None)]
    if op == '<':
        if lower is None:
            return [('never', '', None, None)]
        return [('cmp', '<', lower, None)]
    if op == '<=':
        if upper is None:
            return [('always', '', None, None)]
        return [('cmp', '<', upper, None)]
    raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: comparator operator set is closed)
        message=f"Unsupported comparator {op!r} for {token!r}",
        raw_range=raw_range,
    )


def _hyphen_atoms(left_token: str, right_token: str, raw_range: str) -> List[_Atom]:
    """Expands a hyphen range into inclusive lower and upper comparator atoms."""
    left_components, left_version = _parse_target(left_token, raw_range)
    right_components, right_version = _parse_target(right_token, raw_range)
    atoms: List[_Atom] = []
    lower = left_version if left_version is not None else _filled_version(left_components)
    # POSTCONDITION: hyphen ranges translate into '>= lower' and '<= upper' bounds.
    if lower is not None:
        atoms.append(('cmp', '>=', lower, None))
    if right_version is not None:
        atoms.append(('cmp', '<=', right_version, None))
    else:
        upper = _wildcard_upper(right_components)
        if upper is not None:
            atoms.append(('cmp', '<', upper, None))
    if not atoms:
        atoms.append(('always', '', None, None))
    return atoms


def _compile_clause(clause_text: str, raw_range: str) -> List[_Atom]:
    """Compiles one whitespace-delimited clause into a conjunction of comparison atoms."""
    tokens = clause_text.split()
    # POSTCONDITION: hyphen expressions connect exactly two bounds through a standalone '-' token.
    if '-' in tokens:
        if len(tokens) != 3 or tokens[1] != '-':
            raise semver_solver.InvalidRangeError(
                message=f"Malformed hyphen range: {clause_text!r}",
                raw_range=raw_range,
            )
        return _hyphen_atoms(tokens[0], tokens[2], raw_range)
    atoms: List[_Atom] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        # POSTCONDITION: a whitespace-delimited operator takes its operand from the next token,
        # so '>= 1.0.0' is equivalent to '>=1.0.0' for every relational and prefix operator.
        if token in _COMPARATOR_OPERATORS:
            if index + 1 >= len(tokens):
                raise semver_solver.InvalidRangeError(
                    message=f"Comparator {token!r} is missing an operand",
                    raw_range=raw_range,
                )
            atoms.extend(_expand_comparator(token, tokens[index + 1], raw_range))
            index += 2
            continue
        token_match = _CLAUSE_TOKEN_PATTERN.fullmatch(token)
        if token_match is None:
            raise semver_solver.InvalidRangeError(
                message=f"Malformed comparator token: {token!r}",
                raw_range=raw_range,
            )
        atoms.extend(_expand_comparator(token_match.group(1), token_match.group(2), raw_range))
        index += 1
    return atoms


def _compile_range(text: str) -> List[List[_Atom]]:
    """Compiles a range expression into disjunctive normal form comparator clauses."""
    stripped = text.strip()
    # PRECONDITION: empty or whitespace-only expressions are malformed.
    if not stripped:
        raise semver_solver.InvalidRangeError(
            message=f"Empty version range: {text!r}",
            raw_range=text,
        )
    # PRECONDITION: commas are not permitted as comparator delimiters.
    if ',' in stripped:
        raise semver_solver.InvalidRangeError(
            message=f"Comma-delimited range is not permitted: {text!r}",
            raw_range=text,
        )
    clauses: List[List[_Atom]] = []
    for alternative in stripped.split('||'):
        clause_text = alternative.strip()
        # PRECONDITION: empty union clauses between '||' separators are malformed.
        if not clause_text:
            raise semver_solver.InvalidRangeError(
                message=f"Empty union clause in version range: {text!r}",
                raw_range=text,
            )
        clauses.append(_compile_clause(clause_text, text))
    return clauses


def _atom_matches(atom: _Atom, version: semver_solver.Version, engine: semver_solver.VersionEngine) -> bool:
    """Evaluates a single comparison atom against a candidate version."""
    kind, operator, bound, upper = atom
    if kind == 'always':
        return True
    if kind == 'never':
        return False
    if kind == 'not_interval':
        assert bound is not None and upper is not None
        return engine.compare_precedence(version, bound) < 0 or engine.compare_precedence(version, upper) >= 0
    assert bound is not None
    comparison = engine.compare_precedence(version, bound)
    if operator == '==':
        return comparison == 0
    if operator == '!=':
        return comparison != 0
    if operator == '>=':
        return comparison >= 0
    if operator == '>':
        return comparison > 0
    if operator == '<=':
        return comparison <= 0
    return comparison < 0


def _clause_targets_prerelease(clause: Sequence[_Atom], version: semver_solver.Version) -> bool:
    """Checks whether a clause explicitly scopes a prerelease at the candidate's numeric base."""
    for kind, _operator, bound, _upper in clause:
        if kind != 'cmp' or bound is None or not bound.prerelease:
            continue
        if bound.major == version.major and bound.minor == version.minor and bound.patch == version.patch:
            return True
    return False


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # PRECONDITION: grammar violations and leading zeroes raise InvalidVersionError.
        match = _SEMVER_PATTERN.fullmatch(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version: {text!r}",
                raw_text=text,
            )
        # POSTCONDITION: valid text yields an immutable Version with parsed tuples.
        return _version_from_match(match)

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        # POSTCONDITION: major, minor, and patch compare numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1
        # POSTCONDITION: a normal version ranks above a prerelease with identical numeric components.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # POSTCONDITION: prerelease segments compare position by position, ignoring build metadata.
        for position in range(min(len(v1.prerelease), len(v2.prerelease))):
            comparison = _compare_prerelease_identifiers(v1.prerelease[position], v2.prerelease[position])
            if comparison != 0:
                return comparison
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # PRECONDITION: malformed syntax raises InvalidRangeError.
        _compile_range(text)
        # POSTCONDITION: successful parses store the trimmed range expression.
        return semver_solver.VersionRange(raw_text=text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        clauses = _compile_range(range_constraint.raw_text)
        # POSTCONDITION: prerelease candidates match directly when explicitly enabled.
        prerelease_permitted = include_prerelease or not version.is_prerelease
        for clause in clauses:
            if not all(_atom_matches(atom, version, self) for atom in clause):
                continue
            # POSTCONDITION: otherwise a prerelease needs an explicit boundary at its numeric base.
            if prerelease_permitted or _clause_targets_prerelease(clause, version):
                return True
        return False


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)

        def descending(left: semver_solver.PackageRelease, right: semver_solver.PackageRelease) -> int:
            return engine.compare_precedence(right.version, left.version)

        # POSTCONDITION: releases stay ordered by version precedence descending.
        releases.sort(key=cmp_to_key(descending))

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        releases = self._packages.get(name)
        # PRECONDITION: unregistered packages raise PackageNotFoundError.
        if releases is None:
            raise semver_solver.PackageNotFoundError(
                message=f"Package is not registered: {name!r}",
                package_name=name,
            )
        # POSTCONDITION: a shallow copy of the precedence-ordered release list is returned.
        return list(releases)

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names."""
        return set(self._packages)


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver."""

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map every required package to its (requester, range) pairs.
        constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(('root', dependency.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def available_releases(name: str) -> List[semver_solver.PackageRelease]:
            # POSTCONDITION: unregistered packages yield no candidates and never leak PackageNotFoundError.
            try:
                return repository.get_releases(name)
            except semver_solver.PackageNotFoundError:
                return []

        def viable_candidates(name: str) -> List[semver_solver.PackageRelease]:
            return [
                release
                for release in available_releases(name)
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _requester, constraint in constraints[name]
                )
            ]

        def search() -> bool:
            unassigned = [name for name in constraints if name not in assignment]
            if not unassigned:
                return True
            candidates_by_package: Dict[str, List[semver_solver.PackageRelease]] = {
                name: viable_candidates(name) for name in unassigned
            }
            # INVARIANT: Minimum Remaining Values selection with lexical tie-breaking.
            selected = min(unassigned, key=lambda name: (len(candidates_by_package[name]), name))
            candidates = candidates_by_package[selected]
            if not candidates:
                requesters = sorted({requester for requester, _constraint in constraints[selected]})
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            for candidate in candidates:
                # POSTCONDITION: values are explored in descending version precedence order.
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not engine.satisfies(assignment[dependency.name].version, dependency.range_constraint, False):
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{dependency.name}' "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            conflict_detected = True
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and search():
                    return True
                # INVARIANT: undo the candidate assignment and every constraint it introduced.
                for name, entry in newly_added:
                    constraints[name].remove(entry)
                    if not constraints[name]:
                        del constraints[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not search():
            # POSTCONDITION: exhausted search raises ResolutionConflictError with its derivation.
            raise semver_solver.ResolutionConflictError(
                message=f"Dependency resolution failed: {'; '.join(conflict_trail)}",
                conflicting_packages=tuple(sorted(conflicting_packages)),
                explanation='\n'.join(conflict_trail),
            )
        # POSTCONDITION: a complete assignment compiles into the resolution outcome report.
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
# LAST_CLEANED: 2026-11-07T19:40:23Z
# LAST_CHANGED: 2026-11-07T19:34:39Z
# CHANGE: Prune unreachable spans per spec closure: removed LifecycleError fallbacks (collaborators now resolved strictly via get_singleton inside active phase scopes, per contract), dropped the module-level _default_repository global and its constructor assignment, annotated the wildcard upper-bound fall-through with '# pragma: no cover (assumption: wildcard targets always retain an unresolved component)', and eliminated other always-true guard branches in caret/tilde expansion and the empty-clause guard
# COVERAGE_AUDIT: 2026-11-07T19:40:23Z
# QA_AUDIT: 2026-11-07T19:39:40Z
# --- END AUTOFAB METADATA ---
