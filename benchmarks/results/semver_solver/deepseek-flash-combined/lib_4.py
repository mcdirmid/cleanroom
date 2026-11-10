# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261107_004437_deepseek-flash_semver_solver_combined
# Timestamp: 2026-11-07T00:44:37.779559+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 500,517
#   Cached Inbound Tokens:   42,858,112
#   Outbound Tokens:         499,225
#   Total Tokens:            43,857,854
#   Financial Cost ($USD):   $0.5032
#   Wall Clock Duration:     2756.81s
#   Step Latencies (s):      [135.0, 382.8, 10.0, 528.1, 42.7, 202.2, 102.8, 190.5, 178.4, 148.9, 126.6, 51.2, 40.9, 94.1, 71.8, 288.0, 42.6, 40.9, 188.0, 555.4, 52.9, 83.8, 40.8, 114.3, 350.8, 40.9, 145.0, 104.4, 40.9, 40.7]
#   Role Execution Rounds:   coverage: 3, lib: 2, pretense: 7, pretense_coverage: 3, pretense_qa: 7, qa: 4, test: 4 (Total: 30)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       37
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Library interface for SemVer 2.0.0 parsing and dependency resolution.

Formalizes ``low/semver_solver.pyi``: domain records, exception classes, and the
abstract service protocols realized by ``semver_solver_impl``.
"""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from support.lib.framework import data_type, operation, poly_type

# Requirements specified in semver_solver.pyi


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors."""

    message: str

    def __str__(self) -> str:
        # Domain failures expose their diagnostic message as the canonical string form.
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
        """Indicates whether this version contains pre-release identifiers."""
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
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
        """Parses a version string conforming to SemVer 2.0.0.

        Raises:
            InvalidVersionError: If text violates SemVer 2.0.0 grammar or contains leading zeroes.

        PRECONDITIONS:
        - WHEN text contains leading zeroes in numeric identifiers or violates grammar, MUST raise InvalidVersionError.

        POSTCONDITIONS:
        - MUST parse valid SemVer 2.0.0 strings into Version records.
        """
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions.

        POSTCONDITIONS:
        - MUST evaluate to a negative integer when v1 < v2, zero when v1 == v2, and positive when v1 > v2.
        - MUST ignore build metadata entirely when comparing precedence.
        """
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record.

        Raises:
            InvalidRangeError: If text contains malformed range syntax.

        PRECONDITIONS:
        - WHEN text supplies bare partial versions lacking wildcard characters across any comparator or hyphen expression, MUST raise InvalidRangeError.
        - WHEN text is empty, contains only whitespace, contains empty union clauses, uses comma delimiters, or violates range syntax, MUST raise InvalidRangeError.

        POSTCONDITIONS:
        - MUST trim surrounding whitespace and store the trimmed range expression in raw_text.
        """
        ...

    @operation
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint.

        POSTCONDITIONS:
        - MUST evaluate to True when version satisfies range_constraint, and False otherwise.
        - WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False unless range explicitly targets that prerelease.
        """
        ...


@poly_type
class PackageRepository(Protocol):
    """Maintains indexed package publications and release histories."""

    @operation
    def register_package(self, release: PackageRelease) -> None:
        """Registers a package release with its declared dependencies.

        POSTCONDITIONS:
        - MUST register the package release into the repository.
        """
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending.

        Raises:
            PackageNotFoundError: If name is not registered in the repository.

        PRECONDITIONS:
        - WHEN name is not registered, MUST raise PackageNotFoundError.
        """
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
        """Computes a mutually compatible version assignment for root dependencies.

        Raises:
            ResolutionConflictError: If dependencies cannot be satisfied mutually.

        PRECONDITIONS:
        - WHEN dependencies are unsatisfiable or reference unregistered packages absent from repository, MUST raise ResolutionConflictError without allowing PackageNotFoundError to escape.

        POSTCONDITIONS:
        - MUST compute a mutually compatible set of package releases satisfying root and transitive dependencies.
        - MUST select the highest precedence compatible version for each package.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T00:51:06Z
# LAST_CHANGED: 2026-11-07T00:51:06Z
# CHANGE: Implemented interface module: non-frozen dataclass exception hierarchy with message-backed __str__, ComparatorOp enum, frozen Version/VersionRange/PackageDependency/PackageRelease/ResolutionOutcome records with concrete format/is_prerelease/__str__, and @poly_type service protocols (VersionEngine, PackageRepository, DependencySolver) with contracted operation stubs.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Library implementation of SemVer 2.0.0 parsing, range matching, and dependency resolution.

Realizes ``low/semver_solver_impl.pyi`` on top of the interfaces declared in
``lib/semver_solver.py``. Search heuristics and conflict recording follow the
mechanics documented by ``low/backtracking_solver_ext.pyi``.
"""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver

# Requirements specified in semver_solver_impl.pyi


_VERSION_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)
_NUMERIC_COMPONENT_PATTERN = re.compile(r"0|[1-9]\d*")
_NUMERIC_IDENTIFIER_PATTERN = re.compile(r"\d+")
_HYPHEN_RANGE_PATTERN = re.compile(r"(\S+)\s+-\s+(\S+)")

_WILDCARD_TOKENS = frozenset({"x", "X", "*"})
_OPERATOR_TOKENS = ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~")

# Parsed version specification: concrete components plus the exact version when fully specified.
_Spec = Tuple[Optional[int], Optional[int], Optional[int], Optional[semver_solver.Version]]
# Normalized comparator: relational operator applied to a concrete boundary version.
_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]


def _invalid_version(raw_text: str) -> semver_solver.InvalidVersionError:
    return semver_solver.InvalidVersionError(
        message=f"Version '{raw_text}' violates SemVer 2.0.0 grammar",
        raw_text=raw_text,
    )


def _invalid_range(raw_range: str, detail: str) -> semver_solver.InvalidRangeError:
    return semver_solver.InvalidRangeError(
        message=f"Version range '{raw_range}' is invalid: {detail}",
        raw_range=raw_range,
    )


def _parse_version_text(text: str) -> semver_solver.Version:
    """Parses a SemVer 2.0.0 string, enforcing grammar and numeric leading-zero rules."""
    matched = _VERSION_PATTERN.fullmatch(text)
    if matched is None:
        # PRECONDITIONS: grammar and leading-zero violations MUST raise InvalidVersionError.
        raise _invalid_version(text)
    prerelease_text = matched.group(4)
    build_text = matched.group(5)
    return semver_solver.Version(
        major=int(matched.group(1)),
        minor=int(matched.group(2)),
        patch=int(matched.group(3)),
        prerelease=tuple(prerelease_text.split(".")) if prerelease_text is not None else (),
        build=tuple(build_text.split(".")) if build_text is not None else (),
    )


def _compare_prerelease_identifier(left: str, right: str) -> int:
    """Compares two pre-release identifiers under SemVer 2.0.0 precedence rules."""
    left_numeric = _NUMERIC_IDENTIFIER_PATTERN.fullmatch(left) is not None
    right_numeric = _NUMERIC_IDENTIFIER_PATTERN.fullmatch(right) is not None
    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        if left_value == right_value:
            return 0
        return -1 if left_value < right_value else 1
    if left_numeric:
        # POSTCONDITIONS: numeric identifiers rank lower than alphanumeric identifiers.
        return -1
    if right_numeric:
        return 1
    if left == right:
        return 0
    # POSTCONDITIONS: alphanumeric identifiers compare by ASCII lexicographic order.
    return -1 if left < right else 1


def _compare_precedence(left: semver_solver.Version, right: semver_solver.Version) -> int:
    """Compares precedence of two versions, excluding build metadata entirely."""
    left_core = (left.major, left.minor, left.patch)
    right_core = (right.major, right.minor, right.patch)
    if left_core != right_core:
        # POSTCONDITIONS: major, minor, and patch compare numerically in sequence.
        return -1 if left_core < right_core else 1
    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        # POSTCONDITIONS: normal versions rank higher than prereleases with identical core numbers.
        return 1
    if not right.prerelease:
        return -1
    for left_identifier, right_identifier in zip(left.prerelease, right.prerelease):
        comparison = _compare_prerelease_identifier(left_identifier, right_identifier)
        if comparison != 0:
            return comparison
    if len(left.prerelease) == len(right.prerelease):
        return 0
    # POSTCONDITIONS: a longer prerelease sequence ranks higher when the common prefix matches.
    return -1 if len(left.prerelease) < len(right.prerelease) else 1


def _parse_spec(text: str, raw_range: str) -> _Spec:
    """Parses one comparator target as a full version or a wildcard expression."""
    matched = _VERSION_PATTERN.fullmatch(text)
    if matched is not None:
        prerelease_text = matched.group(4)
        build_text = matched.group(5)
        return (
            int(matched.group(1)),
            int(matched.group(2)),
            int(matched.group(3)),
            semver_solver.Version(
                major=int(matched.group(1)),
                minor=int(matched.group(2)),
                patch=int(matched.group(3)),
                prerelease=tuple(prerelease_text.split(".")) if prerelease_text is not None else (),
                build=tuple(build_text.split(".")) if build_text is not None else (),
            ),
        )
    components = text.split(".")
    if not 1 <= len(components) <= 3:
        raise _invalid_range(raw_range, f"'{text}' is not a full version or wildcard expression")
    parsed: List[Optional[int]] = []
    wildcard_seen = False
    for component in components:
        if component in _WILDCARD_TOKENS:
            wildcard_seen = True
            parsed.append(None)
            continue
        if wildcard_seen or _NUMERIC_COMPONENT_PATTERN.fullmatch(component) is None:
            raise _invalid_range(raw_range, f"'{text}' is not a full version or wildcard expression")
        parsed.append(int(component))
    if not wildcard_seen:
        # PRECONDITIONS: bare partial versions lacking wildcard characters MUST raise InvalidRangeError.
        raise _invalid_range(raw_range, f"'{text}' is a bare partial version lacking a wildcard character")
    while len(parsed) < 3:
        parsed.append(None)
    return (parsed[0], parsed[1], parsed[2], None)


def _spec_floor(spec: _Spec) -> semver_solver.Version:
    """Returns the lowest version covered by a wildcard specification."""
    major, minor, patch, _exact = spec
    return semver_solver.Version(
        major=0 if major is None else major,
        minor=0 if minor is None else minor,
        patch=0 if patch is None else patch,
    )


def _spec_upper(spec: _Spec) -> Optional[semver_solver.Version]:
    """Returns the exclusive upper boundary implied by a wildcard specification."""
    major, minor, patch, _exact = spec
    if major is None:
        return None
    if minor is None:
        return semver_solver.Version(major=major + 1, minor=0, patch=0)
    if patch is None:
        return semver_solver.Version(major=major, minor=minor + 1, patch=0)
    return None  # unreachable (assumption: a wildcard specification always leaves a component unspecified)


def _spec_lower_bound(spec: _Spec) -> semver_solver.Version:
    """Returns the inclusive lower boundary for a hyphen or wildcard specification."""
    exact = spec[3]
    if exact is not None:
        return exact
    return _spec_floor(spec)


def _hyphen_upper(spec: _Spec) -> Optional[_Comparator]:
    """Normalizes the upper bound of a hyphen range into a comparator."""
    exact = spec[3]
    if exact is not None:
        return (semver_solver.ComparatorOp.LE, exact)
    upper = _spec_upper(spec)
    if upper is None:
        return None
    return (semver_solver.ComparatorOp.LT, upper)


def _caret_upper(version: semver_solver.Version) -> semver_solver.Version:
    """Expands a caret prefix on a full version to its exclusive upper boundary."""
    if version.major != 0:
        return semver_solver.Version(major=version.major + 1, minor=0, patch=0)
    if version.minor != 0:
        return semver_solver.Version(major=0, minor=version.minor + 1, patch=0)
    return semver_solver.Version(major=0, minor=0, patch=version.patch + 1)


def _tilde_upper(version: semver_solver.Version) -> semver_solver.Version:
    """Expands a tilde prefix on a full version to its exclusive minor boundary."""
    return semver_solver.Version(major=version.major, minor=version.minor + 1, patch=0)


def _caret_upper_wildcard(spec: _Spec) -> Optional[semver_solver.Version]:
    """Expands a caret prefix on a wildcard expression using first non-zero boundaries."""
    major, minor, patch, _exact = spec
    if major is None:
        return None
    if major != 0:
        return semver_solver.Version(major=major + 1, minor=0, patch=0)
    if minor is None:
        return semver_solver.Version(major=1, minor=0, patch=0)
    if minor != 0:
        return semver_solver.Version(major=0, minor=minor + 1, patch=0)
    if patch is None:
        return semver_solver.Version(major=0, minor=1, patch=0)
    return semver_solver.Version(major=0, minor=0, patch=patch + 1)  # unreachable (assumption: fully concrete caret targets use the exact branch)


def _tilde_upper_wildcard(spec: _Spec) -> Optional[semver_solver.Version]:
    """Expands a tilde prefix on a wildcard expression to its exclusive boundary."""
    major, minor, _patch, _exact = spec
    if major is None:
        return None
    if minor is None:
        return semver_solver.Version(major=major + 1, minor=0, patch=0)
    return semver_solver.Version(major=major, minor=minor + 1, patch=0)


def _tokenize_clause(clause: str, raw_range: str) -> List[Tuple[str, str]]:
    """Splits a clause into operator/specification tokens delimited strictly by whitespace."""
    tokens: List[Tuple[str, str]] = []
    index = 0
    length = len(clause)
    while index < length:
        if clause[index].isspace():
            index += 1
            continue
        operator = ""
        for candidate in _OPERATOR_TOKENS:
            if clause.startswith(candidate, index):
                operator = candidate
                index += len(candidate)
                break
        # POSTCONDITIONS: optional whitespace is accepted between operators and their targets.
        while index < length and clause[index].isspace():
            index += 1
        start = index
        while index < length and not clause[index].isspace():
            index += 1
        specification = clause[start:index]
        if not specification:
            raise _invalid_range(raw_range, "a comparator operator must be followed by a version or wildcard")
        tokens.append((operator, specification))
    return tokens


def _expand_comparator(operator: str, spec: _Spec, raw_range: str) -> List[List[_Comparator]]:
    """Normalizes one comparator into alternative comparator sets (DNF alternatives)."""
    exact = spec[3]
    if exact is not None:
        if operator in ("", "=", "=="):
            return [[(semver_solver.ComparatorOp.EQ, exact)]]
        if operator == "!=":
            return [[(semver_solver.ComparatorOp.NE, exact)]]
        if operator == "<":
            return [[(semver_solver.ComparatorOp.LT, exact)]]
        if operator == "<=":
            return [[(semver_solver.ComparatorOp.LE, exact)]]
        if operator == ">":
            return [[(semver_solver.ComparatorOp.GT, exact)]]
        if operator == ">=":
            return [[(semver_solver.ComparatorOp.GE, exact)]]
        if operator == "^":
            # POSTCONDITIONS: ^1.2.3 expands to >=1.2.3 <2.0.0.
            return [[(semver_solver.ComparatorOp.GE, exact), (semver_solver.ComparatorOp.LT, _caret_upper(exact))]]
        if operator == "~":
            # POSTCONDITIONS: ~1.2.3 expands to >=1.2.3 <1.3.0.
            return [[(semver_solver.ComparatorOp.GE, exact), (semver_solver.ComparatorOp.LT, _tilde_upper(exact))]]
        raise _invalid_range(raw_range, f"unsupported operator '{operator}'")  # unreachable (assumption: tokenizer emits only contracted operators for full versions)

    # Wildcard targets normalize into concrete boundary comparators.
    lower = _spec_floor(spec)
    upper = _spec_upper(spec)
    major = spec[0]
    if operator in ("", "=", "=="):
        if upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, upper)]]
    if operator == "!=":
        if upper is None:
            return []
        # POSTCONDITIONS: !=1.x expands to <1.0.0 || >=2.0.0.
        return [[(semver_solver.ComparatorOp.LT, lower)], [(semver_solver.ComparatorOp.GE, upper)]]
    if operator == ">=":
        if major is None:
            # POSTCONDITIONS: >=* is satisfied by all versions.
            return [[]]
        return [[(semver_solver.ComparatorOp.GE, lower)]]
    if operator == ">":
        if upper is None:
            return []
        return [[(semver_solver.ComparatorOp.GE, upper)]]
    if operator == "<":
        if major is None:
            return []
        return [[(semver_solver.ComparatorOp.LT, lower)]]
    if operator == "<=":
        if upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.LT, upper)]]
    if operator == "^":
        caret_upper = _caret_upper_wildcard(spec)
        if caret_upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, caret_upper)]]
    if operator == "~":
        tilde_upper = _tilde_upper_wildcard(spec)
        if tilde_upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LT, tilde_upper)]]
    raise _invalid_range(raw_range, f"unsupported operator '{operator}'")  # unreachable (assumption: the tokenizer only emits contracted comparator operators)


def _expand_clause(clause: str, raw_range: str) -> List[List[_Comparator]]:
    """Expands one union clause into disjunctive normal form comparator sets."""
    hyphen = _HYPHEN_RANGE_PATTERN.fullmatch(clause)
    if hyphen is not None:
        lower_spec = _parse_spec(hyphen.group(1), raw_range)
        upper_spec = _parse_spec(hyphen.group(2), raw_range)
        comparators: List[_Comparator] = [(semver_solver.ComparatorOp.GE, _spec_lower_bound(lower_spec))]
        hyphen_upper = _hyphen_upper(upper_spec)
        if hyphen_upper is not None:
            comparators.append(hyphen_upper)
        return [comparators]
    tokens = _tokenize_clause(clause, raw_range)
    if not tokens:
        raise _invalid_range(raw_range, "empty clause")  # unreachable (assumption: empty union clauses are rejected before clause expansion)
    alternatives: List[List[_Comparator]] = [[]]
    for operator, specification in tokens:
        spec = _parse_spec(specification, raw_range)
        expanded = _expand_comparator(operator, spec, raw_range)
        if not expanded:
            return []
        alternatives = [prefix + addition for prefix in alternatives for addition in expanded]
    return alternatives


def _parse_range_expression(text: str) -> List[List[_Comparator]]:
    """Compiles a range expression into disjunctive normal form comparator sets."""
    stripped = text.strip()
    if not stripped:
        # PRECONDITIONS: empty range expressions MUST raise InvalidRangeError.
        raise _invalid_range(text, "range expression must not be empty")
    if "," in stripped:
        # PRECONDITIONS: comma delimiters MUST raise InvalidRangeError.
        raise _invalid_range(stripped, "commas are not permitted; delimit comparators with whitespace")
    clauses: List[List[_Comparator]] = []
    for alternative in stripped.split("||"):
        clause = alternative.strip()
        if not clause:
            # PRECONDITIONS: empty union clauses MUST raise InvalidRangeError.
            raise _invalid_range(stripped, "empty union clause")
        clauses.extend(_expand_clause(clause, stripped))
    return clauses


def _evaluate_comparator(
    version: semver_solver.Version,
    operator: semver_solver.ComparatorOp,
    bound: semver_solver.Version,
) -> bool:
    """Evaluates a single normalized comparator against a candidate version."""
    comparison = _compare_precedence(version, bound)
    if operator is semver_solver.ComparatorOp.EQ:
        return comparison == 0
    if operator is semver_solver.ComparatorOp.NE:
        return comparison != 0
    if operator is semver_solver.ComparatorOp.LT:
        return comparison < 0
    if operator is semver_solver.ComparatorOp.LE:
        return comparison <= 0
    if operator is semver_solver.ComparatorOp.GT:
        return comparison > 0
    return comparison >= 0


def _range_targets_prerelease(
    clauses: List[List[_Comparator]],
    version: semver_solver.Version,
) -> bool:
    """Checks whether any comparator explicitly targets the candidate's prerelease core."""
    for comparators in clauses:
        for _operator, bound in comparators:
            if (
                bound.prerelease
                and bound.major == version.major
                and bound.minor == version.minor
                and bound.patch == version.patch
            ):
                return True
    return False


def _satisfies_text(
    version: semver_solver.Version,
    raw_text: str,
    include_prerelease: bool,
) -> bool:
    """Evaluates a version against a textual range expression."""
    clauses = _parse_range_expression(raw_text)
    if version.is_prerelease and not include_prerelease:
        # POSTCONDITIONS: prereleases match only ranges that explicitly target the same major.minor.patch.
        if not _range_targets_prerelease(clauses, version):
            return False
    for comparators in clauses:
        # POSTCONDITIONS: a clause matches when every comparator in it is satisfied.
        if all(_evaluate_comparator(version, operator, bound) for operator, bound in comparators):
            return True
    return False


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine.

    GROUNDING:
    - Realizes SemVer 2.0.0 regular expression grammar, precedence comparison, and range expansion algebra.
    """

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        return _parse_version_text(text)

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions."""
        return _compare_precedence(v1, v2)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # Validation compiles the expression; raw_text stores the surrounding-trimmed expression.
        _parse_range_expression(text)
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
        return _satisfies_text(version, range_constraint.raw_text, include_prerelease)


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing.

    GROUNDING:
    - Maintains _packages mapping package names to lists of semver_solver.PackageRelease.
    - Coordinates with semver_solver.VersionEngine for release sorting.
    """

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        version_engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # POSTCONDITIONS: releases remain ordered by descending version precedence.
        releases.sort(key=cmp_to_key(lambda left, right: version_engine.compare_precedence(right.version, left.version)))

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        releases = self._packages.get(name)
        if releases is None:
            # PRECONDITIONS: unregistered package names MUST raise PackageNotFoundError.
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
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
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver.

    GROUNDING:
    - Coordinates with semver_solver.VersionEngine and semver_solver.PackageRepository.
    - Delegates search heuristics and conflict recording to backtracking_solver_ext mechanics.
    """

    tier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        version_engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Search state: accumulated constraints, partial assignment, decision stack, conflict trail.
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(("root", dependency.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(package_name: str) -> List[semver_solver.PackageRelease]:
            # Unregistered packages evaluate to an empty candidate list without raising PackageNotFoundError.
            if not repository.has_package(package_name):
                return []
            constraints = accumulated[package_name]
            return [
                release
                for release in repository.get_releases(package_name)
                if all(
                    version_engine.satisfies(release.version, constraint, False)
                    for _requester, constraint in constraints
                )
            ]

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                # Complete mutually compatible assignment found.
                return True
            candidates_by_package: Dict[str, List[semver_solver.PackageRelease]] = {
                name: viable_releases(name) for name in unassigned
            }
            # Minimum Remaining Values selection; ties resolve lexicographically by package name.
            selected = min(unassigned, key=lambda name: (len(candidates_by_package[name]), name))
            candidates = candidates_by_package[selected]
            if not candidates:
                requesters = [requester for requester, _constraint in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # Value ordering: explore releases in descending version precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                # Forward checking: candidate dependencies merge into accumulated constraints.
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not version_engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        constraint_entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(constraint_entry)
                        newly_added.append((dependency.name, constraint_entry))
                if not conflict_detected and backtrack():
                    return True
                # Backtracking: pop the decision and restore the previous constraint mapping.
                for package_name, constraint_entry in newly_added:
                    accumulated[package_name].remove(constraint_entry)
                    if not accumulated[package_name]:
                        del accumulated[package_name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not backtrack():
            # PRECONDITIONS: unsatisfiable or missing packages MUST surface as ResolutionConflictError.
            # Every failing search branch records a conflict message, so the trail explains the failure.
            explanation = "; ".join(conflict_trail)
            raise semver_solver.ResolutionConflictError(
                message=f"Dependency resolution failed: {explanation}",
                conflicting_packages=tuple(sorted(conflicting_packages)),
                explanation=explanation,
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
# LAST_CLEANED: 2026-11-07T01:29:59Z
# LAST_CHANGED: 2026-11-07T00:56:07Z
# CHANGE: Resolved unreachable-statement feedback by attaching effective inline '# unreachable (assumption: ...)' annotations directly to the five structurally unreachable statements: the wildcard upper-bound helper's final return None, the fully concrete caret-wildcard fallback bound, both unsupported-operator fallbacks, and the empty-clause guard. No behavioral logic changed; static checks pass.
# COVERAGE_AUDIT: 2026-11-07T01:04:21Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T01:29:59Z
# PRETENSE_QA_AUDIT: 2026-11-07T01:29:19Z
# QA_AUDIT: 2026-11-07T01:03:36Z
# --- END AUTOFAB METADATA ---
