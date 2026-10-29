# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261028_214627_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-10-28T21:46:27.654470+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 403,037
#   Cached Inbound Tokens:   55,850,240
#   Outbound Tokens:         405,964
#   Total Tokens:            56,659,241
#   Financial Cost ($USD):   $0.4716
#   Wall Clock Duration:     2186.90s
#   Step Latencies (s):      [338.5, 400.4, 61.8, 337.5, 51.0, 61.3, 51.4, 92.1, 61.3, 71.6, 30.6, 51.0, 20.6, 122.8, 134.1, 215.9, 40.9, 61.3, 20.3, 82.0, 61.9, 164.1, 40.9, 61.4, 20.5, 51.2, 71.4, 20.4, 40.8, 40.8, 20.5, 20.4]
#   Role Execution Rounds:   lib: 3, pretense: 12, pretense_coverage: 5, pretense_qa: 12 (Total: 32)
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
"""Interface specification for SemVer 2.0.0 parsing, range evaluation, and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __str__(self) -> str:
        """Returns the diagnostic message so str(exception) is human readable."""
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered.

    Args:
        message: Diagnostic description of the error.
        raw_text: Original unparseable version string.
    """

    raw_text: str


@dataclass
class InvalidRangeError(SemVerError):
    """Raised when a version range expression contains malformed syntax.

    Args:
        message: Diagnostic description of the error.
        raw_range: Original malformed range expression string.
    """

    raw_range: str


@dataclass
class ResolutionConflictError(SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually.

    Args:
        message: Diagnostic description of the conflict.
        conflicting_packages: Sequence of package names involved in the conflict.
        explanation: Detailed diagnostic derivation of the unsatisfiable conflict.
    """

    conflicting_packages: Tuple[str, ...]
    explanation: str


@dataclass
class PackageNotFoundError(SemVerError):
    """Raised when a referenced package name does not exist in the repository.

    Args:
        message: Diagnostic description of the missing package.
        package_name: Name of the missing package.
    """

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
    """Immutable semantic version representation conforming to SemVer 2.0.0.

    Args:
        major: Non-negative integer major version.
        minor: Non-negative integer minor version.
        patch: Non-negative integer patch version.
        prerelease: Ordered tuple of dot-separated pre-release identifiers.
        build: Ordered tuple of dot-separated build metadata identifiers.
    """

    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        """Indicates whether this version contains pre-release identifiers."""
        return bool(self.prerelease)

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
    """Immutable representation of a version constraint expression.

    Args:
        raw_text: Canonical text representation of the range expression.
    """

    raw_text: str

    def __str__(self) -> str:
        """Returns the raw range text representation."""
        return self.raw_text


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range.

    Args:
        name: Name of the required package.
        range_constraint: Acceptable version range constraint.
    """

    name: str
    range_constraint: VersionRange


@data_type
@dataclass(frozen=True)
class PackageRelease:
    """Immutable publication record of a package at a specific semantic version.

    Args:
        name: Name of the package.
        version: Semantic version of this release.
        dependencies: Declared prerequisite package dependencies.
    """

    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run.

    Args:
        selected_versions: Mapping of package names to their selected semantic versions.
        derivation_steps: Ordered sequence of decision and deduction steps.
    """

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
        include_prerelease: bool = False,
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T21:51:59Z
# LAST_CHANGED: 2026-10-28T21:51:59Z
# CHANGE: Implemented SemVer 2.0.0 interface: dataclass error hierarchy with __str__ diagnostics, ComparatorOp enum, frozen data types (Version with format/is_prerelease, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome), and VersionEngine/PackageRepository/DependencySolver protocol declarations matching low/semver_solver.pyi.
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete implementation of SemVer 2.0.0 parsing, range matching, and dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Callable, Collection, Dict, FrozenSet, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTier,
    get_default_registry,
    get_singleton,
    system,
)

from . import semver_solver

# SemVer 2.0.0 grammar: no leading zeroes, optional dot-separated pre-release and build segments.
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# Partial/wildcard grammar used by range tokens: one to three numeric or wildcard components.
_ANY_WILDCARD_COMPONENT = r"(?:0|[1-9][0-9]*|[xX*])"
_WILDCARD_PATTERN = re.compile(
    rf"^({_ANY_WILDCARD_COMPONENT})"
    rf"(?:\.({_ANY_WILDCARD_COMPONENT}))?"
    rf"(?:\.({_ANY_WILDCARD_COMPONENT}))?$"
)
_OPERATOR_TOKENS = frozenset({"==", "!=", "<=", ">=", "=", "<", ">", "^", "~"})
_WILDCARD_MARKERS = frozenset({"*", "x", "X"})
_COMPARATOR_OPERATORS: Dict[str, semver_solver.ComparatorOp] = {
    "==": semver_solver.ComparatorOp.EQ,
    "=": semver_solver.ComparatorOp.EQ,
    "!=": semver_solver.ComparatorOp.NE,
    "<": semver_solver.ComparatorOp.LT,
    "<=": semver_solver.ComparatorOp.LE,
    ">": semver_solver.ComparatorOp.GT,
    ">=": semver_solver.ComparatorOp.GE,
}

# A compiled clause pairs a conjunctive predicate with the version tuples that explicitly
# target a pre-release, enabling the caller's pre-release filtering rule.
_RangeClause = Tuple[Callable[[semver_solver.Version], bool], FrozenSet[Tuple[int, int, int]]]


def _split_comparator(part: str) -> Tuple[Optional[str], str]:
    """Splits a comparator token into its leading operator (if any) and version text."""
    # Two-character operators are tested before their one-character prefixes.
    for operator_text in ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~"):
        if part.startswith(operator_text):
            return operator_text, part[len(operator_text):]
    return None, part


def _compare_precedence(v1: semver_solver.Version, v2: semver_solver.Version) -> int:
    """Orders two versions under SemVer 2.0.0 precedence rules, ignoring build metadata."""
    # MUST compare major, minor, and patch numerically.
    for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
        if left != right:
            return -1 if left < right else 1

    # MUST rank normal versions higher than pre-release versions sharing numeric components.
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1

    # MUST compare pre-release segments numerically when both numeric, ASCII-lexicographically
    # when string, and rank numeric below string; a longer matching prefix ranks higher.
    for left_segment, right_segment in zip(v1.prerelease, v2.prerelease):
        left_numeric = left_segment.isdigit()
        right_numeric = right_segment.isdigit()
        if left_numeric and right_numeric:
            left_number = int(left_segment)
            right_number = int(right_segment)
            if left_number != right_number:
                return -1 if left_number < right_number else 1
        elif left_numeric:
            return -1
        elif right_numeric:
            return 1
        elif left_segment != right_segment:
            return -1 if left_segment < right_segment else 1

    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
    return 0


def _never(candidate: semver_solver.Version) -> bool:
    """Predicate for a comparator set that can never be satisfied."""
    return False


def _comparator_term(
    operator: semver_solver.ComparatorOp,
    boundary: semver_solver.Version,
) -> Callable[[semver_solver.Version], bool]:
    """Builds a predicate testing one relational comparator against a candidate version."""

    def term(candidate: semver_solver.Version) -> bool:
        comparison = _compare_precedence(candidate, boundary)
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

    return term


def _outside_interval_term(
    lower: semver_solver.Version,
    upper: semver_solver.Version,
) -> Callable[[semver_solver.Version], bool]:
    """Builds a predicate matching versions outside a half-open interval (negated wildcard)."""

    def term(candidate: semver_solver.Version) -> bool:
        return _compare_precedence(candidate, lower) < 0 or _compare_precedence(candidate, upper) >= 0

    return term


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range expansion."""

    tier: LifecycleTier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        # MUST parse valid SemVer 2.0.0 strings into Version records with typed segments.
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            # WHEN grammar is violated or numeric identifiers carry leading zeroes, raise.
            raise semver_solver.InvalidVersionError(f"Invalid semantic version string: {text!r}", text)
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        build = tuple(match.group(5).split(".")) if match.group(5) else ()
        return semver_solver.Version(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
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
        # MUST evaluate negative/zero/positive under SemVer precedence, excluding build metadata.
        return _compare_precedence(v1, v2)

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # Validate the full expression so malformed syntax raises InvalidRangeError here.
        self._compile_range(text)
        # MUST store the trimmed range expression in raw_text.
        return semver_solver.VersionRange(text.strip())

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        clauses = self._compile_range(range_constraint.raw_text)

        if version.is_prerelease and not include_prerelease:
            # WHEN candidate is a pre-release, it MUST match only a clause explicitly targeting
            # a pre-release identifier sharing the same major, minor, and patch numbers.
            version_tuple = (version.major, version.minor, version.patch)
            for clause_matches, prerelease_targets in clauses:
                if version_tuple in prerelease_targets and clause_matches(version):
                    return True
            return False

        # MUST evaluate to True when the version satisfies all comparators of any clause.
        for clause_matches, _prerelease_targets in clauses:
            if clause_matches(version):
                return True
        return False

    def _compile_range(self, text: str) -> List[_RangeClause]:
        """Compiles a range expression into disjunctive clauses of conjunctive predicates."""
        trimmed = text.strip()
        # WHEN text is empty or whitespace-only, MUST raise InvalidRangeError.
        if not trimmed:
            raise semver_solver.InvalidRangeError("Version range expression is empty", text)
        # Commas are not permitted as comparator delimiters.
        if "," in trimmed:
            raise semver_solver.InvalidRangeError(
                f"Comma delimiters are not permitted in range expression {text!r}",
                text,
            )

        clauses: List[_RangeClause] = []
        for clause_text in trimmed.split("||"):
            clause = clause_text.strip()
            # WHEN a union alternative is empty, MUST raise InvalidRangeError.
            if not clause:
                raise semver_solver.InvalidRangeError(
                    f"Empty range clause in expression {text!r}",
                    text,
                )
            clauses.append(self._compile_clause(clause, text))
        return clauses

    def _compile_clause(self, clause_text: str, original_text: str) -> _RangeClause:
        """Compiles one whitespace-delimited conjunction of range comparators."""
        tokens = clause_text.split()

        # Hyphen ranges declare an inclusive lower and upper boundary separated by a bare '-'.
        if "-" in tokens:
            if len(tokens) != 3 or tokens[1] != "-":
                raise semver_solver.InvalidRangeError(
                    f"Malformed hyphen range clause {clause_text!r} in expression {original_text!r}",
                    original_text,
                )
            return self._hyphen_clause(tokens[0], tokens[2], original_text)

        # Consolidate prefix operators separated from their targets by optional whitespace.
        parts: List[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in _OPERATOR_TOKENS:
                if index + 1 >= len(tokens):
                    raise semver_solver.InvalidRangeError(
                        f"Operator {token!r} is missing its target in expression {original_text!r}",
                        original_text,
                    )
                parts.append(token + tokens[index + 1])
                index += 2
            else:
                parts.append(token)
                index += 1

        terms: List[Callable[[semver_solver.Version], bool]] = []
        prerelease_targets: Set[Tuple[int, int, int]] = set()
        for part in parts:
            part_terms, part_targets = self._compile_comparator(part, original_text)
            terms.extend(part_terms)
            prerelease_targets.update(part_targets)

        def clause_matches(candidate: semver_solver.Version) -> bool:
            # MUST satisfy every comparator within the clause.
            return all(term(candidate) for term in terms)

        return clause_matches, frozenset(prerelease_targets)

    def _compile_comparator(
        self,
        part: str,
        original_text: str,
    ) -> Tuple[List[Callable[[semver_solver.Version], bool]], Set[Tuple[int, int, int]]]:
        """Compiles one comparator (optionally prefixed by an operator) into predicates."""
        operator_text, version_text = _split_comparator(part)
        version_text = version_text.strip()
        if not version_text:
            raise semver_solver.InvalidRangeError(
                f"Comparator {part!r} is missing a version in expression {original_text!r}",
                original_text,
            )

        wildcard = self._wildcard_components(version_text, original_text)

        # Caret and tilde prefixes expand into paired lower/upper boundary inequalities.
        if operator_text in ("^", "~"):
            if wildcard is None:
                boundary = self._parse_range_version(version_text, original_text)
                return self._caret_or_tilde_terms(operator_text, boundary)
            return self._prefixed_wildcard_terms(operator_text, wildcard)

        # Wildcards normalize into comparator inequality pairs.
        if wildcard is not None:
            return self._wildcard_terms(operator_text, wildcard)

        # MUST accept full versions only when no wildcard characters are present. A missing
        # operator prefix (or a bare '=') denotes exact equality.
        boundary = self._parse_range_version(version_text, original_text)
        operator = (
            semver_solver.ComparatorOp.EQ
            if operator_text is None
            else _COMPARATOR_OPERATORS[operator_text]
        )
        targets: Set[Tuple[int, int, int]] = set()
        if boundary.prerelease:
            targets.add((boundary.major, boundary.minor, boundary.patch))
        return [_comparator_term(operator, boundary)], targets

    def _hyphen_clause(self, lower_text: str, upper_text: str, original_text: str) -> _RangeClause:
        """Compiles a hyphen range into inclusive lower and upper boundary predicates."""
        terms: List[Callable[[semver_solver.Version], bool]] = []
        prerelease_targets: Set[Tuple[int, int, int]] = set()

        lower_wildcard = self._wildcard_components(lower_text, original_text)
        if lower_wildcard is None:
            lower_version = self._parse_range_version(lower_text, original_text)
            if lower_version.prerelease:
                prerelease_targets.add((lower_version.major, lower_version.minor, lower_version.patch))
        else:
            lower_version, _ignored_upper = self._expand_wildcard(lower_wildcard)
        terms.append(_comparator_term(semver_solver.ComparatorOp.GE, lower_version))

        upper_wildcard = self._wildcard_components(upper_text, original_text)
        if upper_wildcard is None:
            upper_version = self._parse_range_version(upper_text, original_text)
            if upper_version.prerelease:
                prerelease_targets.add((upper_version.major, upper_version.minor, upper_version.patch))
            terms.append(_comparator_term(semver_solver.ComparatorOp.LE, upper_version))
        else:
            _ignored_lower, upper_bound = self._expand_wildcard(upper_wildcard)
            if upper_bound is not None:
                terms.append(_comparator_term(semver_solver.ComparatorOp.LT, upper_bound))

        def clause_matches(candidate: semver_solver.Version) -> bool:
            return all(term(candidate) for term in terms)

        return clause_matches, frozenset(prerelease_targets)

    def _caret_or_tilde_terms(
        self,
        operator_text: str,
        boundary: semver_solver.Version,
    ) -> Tuple[List[Callable[[semver_solver.Version], bool]], Set[Tuple[int, int, int]]]:
        """Expands caret and tilde prefixes into bounded comparator sets."""
        if operator_text == "^":
            # Caret expands on the first non-zero component boundary.
            if boundary.major != 0:
                upper = semver_solver.Version(boundary.major + 1, 0, 0)
            elif boundary.minor != 0:
                upper = semver_solver.Version(0, boundary.minor + 1, 0)
            else:
                upper = semver_solver.Version(0, 0, boundary.patch + 1)
        else:
            # Tilde expands into lower and upper minor boundaries.
            upper = semver_solver.Version(boundary.major, boundary.minor + 1, 0)

        prerelease_targets: Set[Tuple[int, int, int]] = set()
        if boundary.prerelease:
            prerelease_targets.add((boundary.major, boundary.minor, boundary.patch))
        return [
            _comparator_term(semver_solver.ComparatorOp.GE, boundary),
            _comparator_term(semver_solver.ComparatorOp.LT, upper),
        ], prerelease_targets

    def _prefixed_wildcard_terms(
        self,
        operator_text: str,
        components: Tuple[Optional[int], ...],
    ) -> Tuple[List[Callable[[semver_solver.Version], bool]], Set[Tuple[int, int, int]]]:
        """Expands caret and tilde prefixes applied to wildcard partial versions."""
        lower, upper = self._expand_wildcard(components)
        if components[0] is None:
            # A root wildcard spans every version.
            return [], set()
        if operator_text == "~":
            if upper is None:  # pragma: no cover (assumption: specified major yields an upper bound)
                return [], set()
            return [
                _comparator_term(semver_solver.ComparatorOp.GE, lower),
                _comparator_term(semver_solver.ComparatorOp.LT, upper),
            ], set()
        caret_upper = self._caret_wildcard_upper(components[0], components[1:])
        return [
            _comparator_term(semver_solver.ComparatorOp.GE, lower),
            _comparator_term(semver_solver.ComparatorOp.LT, caret_upper),
        ], set()

    def _wildcard_terms(
        self,
        operator_text: Optional[str],
        components: Tuple[Optional[int], ...],
    ) -> Tuple[List[Callable[[semver_solver.Version], bool]], Set[Tuple[int, int, int]]]:
        """Normalizes wildcard partial versions into paired comparator inequalities."""
        lower, upper = self._expand_wildcard(components)

        # A root wildcard without a bounding operator matches every version.
        if components[0] is None:
            if operator_text in (None, "=", "==", ">=", "<="):
                return [], set()
            return [_never], set()

        if upper is None:  # pragma: no cover (assumption: non-root wildcards are bounded above)
            return [], set()

        if operator_text is None or operator_text in ("=", "=="):
            return [
                _comparator_term(semver_solver.ComparatorOp.GE, lower),
                _comparator_term(semver_solver.ComparatorOp.LT, upper),
            ], set()
        if operator_text == "!=":
            return [_outside_interval_term(lower, upper)], set()
        if operator_text == ">=":
            return [_comparator_term(semver_solver.ComparatorOp.GE, lower)], set()
        if operator_text == ">":
            return [_comparator_term(semver_solver.ComparatorOp.GE, upper)], set()
        if operator_text == "<=":
            return [_comparator_term(semver_solver.ComparatorOp.LT, upper)], set()
        if operator_text == "<":
            return [_comparator_term(semver_solver.ComparatorOp.LT, lower)], set()
        raise semver_solver.InvalidRangeError(  # pragma: no cover (assumption: operators pre-validated)
            f"Unsupported wildcard operator {operator_text!r}",
            operator_text,
        )

    def _wildcard_components(
        self,
        token: str,
        original_text: str,
    ) -> Optional[Tuple[Optional[int], ...]]:
        """Classifies a range token as a wildcard partial (components) or a plain version (None)."""
        match = _WILDCARD_PATTERN.match(token)
        if match is None:
            return None

        raw_components = [group for group in match.groups() if group is not None]
        wildcard_seen = False
        components: List[Optional[int]] = []
        for raw_component in raw_components:
            if raw_component in _WILDCARD_MARKERS:
                wildcard_seen = True
                components.append(None)
            else:
                if wildcard_seen:
                    raise semver_solver.InvalidRangeError(
                        f"Malformed wildcard version {token!r} in expression {original_text!r}",
                        original_text,
                    )
                components.append(int(raw_component))

        if wildcard_seen:
            return tuple(components)
        if len(raw_components) < 3:
            # WHEN a bare partial version lacks wildcard characters, MUST raise InvalidRangeError.
            raise semver_solver.InvalidRangeError(
                f"Partial version {token!r} requires an explicit wildcard in expression {original_text!r}",
                original_text,
            )
        # A complete numeric triple is a full version, handled by the version parser.
        return None

    def _expand_wildcard(
        self,
        components: Tuple[Optional[int], ...],
    ) -> Tuple[semver_solver.Version, Optional[semver_solver.Version]]:
        """Expands a wildcard partial into an inclusive lower and exclusive upper bound."""
        padded: List[Optional[int]] = list(components) + [None] * (3 - len(components))
        major = padded[0]
        minor = padded[1]
        patch = padded[2]

        lower = semver_solver.Version(
            major if major is not None else 0,
            minor if minor is not None else 0,
            patch if patch is not None else 0,
        )

        if major is None:
            upper: Optional[semver_solver.Version] = None
        elif minor is None:
            upper = semver_solver.Version(major + 1, 0, 0)
        elif patch is None:
            upper = semver_solver.Version(major, minor + 1, 0)
        else:  # pragma: no cover (assumption: wildcards always leave a component unspecified)
            upper = None
        return lower, upper

    def _caret_wildcard_upper(
        self,
        major: int,
        remaining_components: Tuple[Optional[int], ...],
    ) -> semver_solver.Version:
        """Computes the exclusive caret ceiling for a wildcard partial version."""
        minor = remaining_components[0]
        patch = remaining_components[1] if len(remaining_components) > 1 else None

        if minor is None:
            return semver_solver.Version(major + 1, 0, 0)
        if patch is None:
            if major != 0:
                return semver_solver.Version(major + 1, 0, 0)
            if minor != 0:
                return semver_solver.Version(0, minor + 1, 0)
            return semver_solver.Version(0, 1, 0)
        return semver_solver.Version(major + 1, 0, 0)  # pragma: no cover (assumption: no wildcard here)

    def _parse_range_version(self, token: str, original_text: str) -> semver_solver.Version:
        """Parses a full version token inside a range expression."""
        try:
            return self.parse_version(token)
        except semver_solver.InvalidVersionError as error:
            # Malformed range tokens surface as range errors rather than version errors.
            raise semver_solver.InvalidRangeError(
                f"Invalid version {token!r} in range expression {original_text!r}: {error.message}",
                original_text,
            ) from error


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier: LifecycleTier = system

    def __init__(self) -> None:
        """Initializes the package name to release list index."""
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)

        def compare_releases(
            left: semver_solver.PackageRelease,
            right: semver_solver.PackageRelease,
        ) -> int:
            return engine.compare_precedence(left.version, right.version)

        # MUST keep each package's releases ordered by descending version precedence.
        releases.sort(key=cmp_to_key(compare_releases), reverse=True)

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        if name not in self._packages:
            # WHEN name is not registered, MUST raise PackageNotFoundError.
            raise semver_solver.PackageNotFoundError(
                f"Package {name!r} is not registered in the repository",
                name,
            )
        # MUST produce a shallow copy of the precedence-sorted release list.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        # MUST evaluate to True only when the package name is indexed.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names."""
        # MUST produce the set of every indexed package name.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of the backtracking package dependency solver."""

    tier: LifecycleTier = system

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to (requesting package, range) requirements.
        accumulated_constraints: Dict[
            str,
            List[Tuple[Optional[str], semver_solver.VersionRange]],
        ] = {}
        for dependency in root_dependencies:
            accumulated_constraints.setdefault(dependency.name, []).append(
                (None, dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def available_releases(package_name: str) -> List[semver_solver.PackageRelease]:
            try:
                return repository.get_releases(package_name)
            except semver_solver.PackageNotFoundError:
                # Unregistered packages have zero candidate releases and MUST NOT leak this error.
                return []

        def backtrack() -> bool:
            unassigned = [name for name in accumulated_constraints if name not in assignment]
            if not unassigned:
                return True

            # Minimum Remaining Values: fewest viable candidates, lexical tie-break.
            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for package_name in unassigned:
                constraints = accumulated_constraints[package_name]
                candidates_map[package_name] = [
                    release
                    for release in available_releases(package_name)
                    if all(engine.satisfies(release.version, constraint) for _source, constraint in constraints)
                ]

            selected = min(
                unassigned,
                key=lambda package_name: (len(candidates_map[package_name]), package_name),
            )
            candidates = candidates_map[selected]

            if not candidates:
                requesters = [
                    source if source is not None else "root"
                    for source, _constraint in accumulated_constraints[selected]
                ]
                conflicting_packages.add(selected)
                conflicting_packages.update(
                    source
                    for source, _constraint in accumulated_constraints[selected]
                    if source is not None
                )
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False

            # Value ordering: explore descending precedence candidates from the repository.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[
                    Tuple[str, Tuple[Optional[str], semver_solver.VersionRange]]
                ] = []

                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # Forward checking: assigned versions violating a new requirement conflict.
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{dependency.name}' "
                                f"{dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        # Merge the new requirement into the accumulated constraint mapping.
                        entry = (selected, dependency.range_constraint)
                        accumulated_constraints.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))

                if not conflict_detected and backtrack():
                    return True

                # Undo the assignment and every constraint introduced by this candidate branch.
                for package_name, entry in newly_added:
                    accumulated_constraints[package_name].remove(entry)
                    if not accumulated_constraints[package_name]:
                        del accumulated_constraints[package_name]
                del assignment[selected]
                derivation_steps.pop()

            return False

        solved = backtrack()
        if solved:
            # MUST compile the selected release mapping and decision sequence into an outcome.
            selected_versions = {
                package_name: release.version
                for package_name, release in assignment.items()
            }
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )

        # WHEN unsatisfiable, MUST raise ResolutionConflictError with conflicting packages and derivation.
        explanation = "\n".join(conflict_trail)
        if not explanation:  # pragma: no cover (assumption: an exhausted search always records a conflict entry)
            explanation = "Dependency search exhausted every candidate assignment."
        conflicting = tuple(sorted(conflicting_packages))
        raise semver_solver.ResolutionConflictError(
            f"Dependency resolution failed for packages: {', '.join(conflicting)}",
            conflicting,
            explanation,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_solver.VersionEngine],
        tier=VersionEngine.tier,
    )
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, semver_solver.PackageRepository],
        tier=PackageRepository.tier,
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, semver_solver.DependencySolver],
        tier=DependencySolver.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T22:22:43Z
# LAST_CHANGED: 2026-10-28T22:15:56Z
# CHANGE: Eliminated the cited unreachable caret-wildcard fallback by restructuring rather than annotating: _caret_wildcard_upper now takes the caller-narrowed major component as a required int plus the remaining components, returns a non-optional Version, and no longer contains the dead 'major is None' branch; the caller passes components[0] (already proven non-None by its root-wildcard early return) and the now-unneeded optional caret-None check was removed too. Caret/tilde wildcard ceilings (^1.x, ^0.x, ^0.2.x, ^0.0.x, ^1.2.x, ~1.x, ~1.2.x, ^*) plus range validation, precedence, and resolver behavior are unchanged and regression-verified; the tool-generated lifecycle block was left untouched.
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T22:22:43Z
# PRETENSE_QA_AUDIT: 2026-10-28T22:22:33Z
# --- END CLEANROOM METADATA ---
