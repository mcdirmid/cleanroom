# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_195940_deepseek-flash_semver_solver_pretense_baseline
# Timestamp: 2026-10-29T19:59:40.638250+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 94,687
#   Cached Inbound Tokens:   8,263,296
#   Outbound Tokens:         123,127
#   Total Tokens:            8,481,110
#   Financial Cost ($USD):   $0.1129
#   Wall Clock Duration:     797.81s
#   Step Latencies (s):      [790.6]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
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
"""SemVer 2.0 parsing and dependency resolution interface specifications."""

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
        return len(self.prerelease) > 0

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += "-" + ".".join(self.prerelease)
        if self.build:
            text += "+" + ".".join(self.build)
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
        """Retrieves all registered releases ordered by version precedence descending."""
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
# LAST_CLEANED: 2026-10-29T20:12:58Z
# LAST_CHANGED: 2026-10-29T20:12:58Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 317f7880fcb7
# COVERAGE_AUDIT: 2026-10-29T20:12:58Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T20:12:58Z
# PRETENSE_QA_AUDIT: 2026-10-29T20:12:58Z
# QA_AUDIT: 2026-10-29T20:12:58Z
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete SemVer 2.0 parsing and dependency resolution implementations."""

from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)
from benchmark_2.parts.semver_solver.lib import semver_solver


_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_NUMERIC = r"(?:0|[1-9]\d*)"
_WILDCARD = r"(?:[xX*])"
_WILDCARD_ALL_PATTERN = re.compile(r"^[xX*]$")
_WILDCARD_MAJOR_PATTERN = re.compile(rf"^({_NUMERIC})\.{_WILDCARD}$")
_WILDCARD_MINOR_PATTERN = re.compile(rf"^({_NUMERIC})\.({_NUMERIC})\.{_WILDCARD}$")
_PARTIAL_VERSION_PATTERN = re.compile(rf"^{_NUMERIC}(?:\.{_NUMERIC})?$")
_HYPHEN_RANGE_PATTERN = re.compile(r"^(\S+)\s+-\s+(\S+)$")

_OPERATOR_PREFIXES: Tuple[str, ...] = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")

_OPERATOR_COMPARATORS: Dict[str, semver_solver.ComparatorOp] = {
    "==": semver_solver.ComparatorOp.EQ,
    "=": semver_solver.ComparatorOp.EQ,
    "!=": semver_solver.ComparatorOp.NE,
    "<": semver_solver.ComparatorOp.LT,
    "<=": semver_solver.ComparatorOp.LE,
    ">": semver_solver.ComparatorOp.GT,
    ">=": semver_solver.ComparatorOp.GE,
}

_Comparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]
_Clause = List[_Comparator]


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # POSTCONDITION: valid SemVer text parses into a Version with all five components.
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            # POSTCONDITION: grammar violations and leading zeroes raise InvalidVersionError.
            raise semver_solver.InvalidVersionError(
                f"Invalid semantic version: {text!r}", text
            )
        major_text, minor_text, patch_text, prerelease_text, build_text = match.groups()
        prerelease: Tuple[str, ...] = (
            tuple(prerelease_text.split(".")) if prerelease_text else ()
        )
        build: Tuple[str, ...] = tuple(build_text.split(".")) if build_text else ()
        return semver_solver.Version(
            int(major_text),
            int(minor_text),
            int(patch_text),
            prerelease,
            build,
        )

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        # POSTCONDITION: major, minor, and patch compare numerically in sequence.
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1
        # POSTCONDITION: a normal version ranks above a matching prerelease version.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        for left, right in zip(v1.prerelease, v2.prerelease):
            if left == right:
                continue
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            # POSTCONDITION: numeric segments compare numerically and rank below string segments.
            if left_numeric and right_numeric:
                return -1 if int(left) < int(right) else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left < right else 1
        # POSTCONDITION: longer prerelease sequences rank higher on a shared prefix.
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        # POSTCONDITION: build metadata is ignored entirely.
        return 0

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        trimmed = text.strip()
        # POSTCONDITION: empty or whitespace-only expressions raise InvalidRangeError.
        if not trimmed:
            raise semver_solver.InvalidRangeError("Version range is empty", text)
        # POSTCONDITION: commas are not permitted as comparator delimiters.
        if "," in trimmed:
            raise semver_solver.InvalidRangeError(
                f"Comma-delimited range is not permitted: {text!r}", text
            )
        # POSTCONDITION: every clause and comparator must be syntactically valid.
        self._compile_range(trimmed, text)
        # POSTCONDITION: raw_text stores the trimmed range expression.
        return semver_solver.VersionRange(trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        # POSTCONDITION: range expression compiles into disjunctive normal form clauses.
        clauses = self._compile_range(
            range_constraint.raw_text, range_constraint.raw_text
        )
        # POSTCONDITION: prereleases are filtered unless explicitly targeted or included.
        if version.is_prerelease and not include_prerelease:
            if not self._targets_prerelease(clauses, version):
                return False
        # POSTCONDITION: True when every comparator of at least one clause is satisfied.
        for clause in clauses:
            if all(
                self._compare_against(version, operator, bound) is True
                for operator, bound in clause
            ):
                return True
        return False

    def _compile_range(self, raw_text: str, original_text: str) -> List[_Clause]:
        """Compiles a validated range expression into disjunctive normal form clauses."""
        clauses: List[_Clause] = []
        for part in raw_text.split("||"):
            clause_text = part.strip()
            # POSTCONDITION: empty union clauses raise InvalidRangeError.
            if not clause_text:
                raise semver_solver.InvalidRangeError(
                    f"Empty union clause in range: {original_text!r}", original_text
                )
            clauses.extend(self._compile_clause(clause_text, original_text))
        return clauses

    def _compile_clause(self, clause_text: str, original_text: str) -> List[_Clause]:
        """Compiles a single whitespace-delimited clause into alternate comparator sets."""
        hyphen_match = _HYPHEN_RANGE_PATTERN.match(clause_text)
        if hyphen_match is not None:
            lower = self._parse_literal(hyphen_match.group(1), original_text)
            upper = self._parse_literal(hyphen_match.group(2), original_text)
            # POSTCONDITION: hyphen ranges normalize into paired inequalities.
            return [[(semver_solver.ComparatorOp.GE, lower), (semver_solver.ComparatorOp.LE, upper)]]
        tokens = self._merge_operator_tokens(clause_text, original_text)
        clauses: List[_Clause] = [[]]
        for token in tokens:
            operator, operand = self._split_operator(token, original_text)
            alternatives = self._expand_operand(operator, operand, original_text)
            clauses = [prefix + alternative for prefix in clauses for alternative in alternatives]
        return clauses

    def _merge_operator_tokens(self, clause_text: str, original_text: str) -> List[str]:
        """Joins bare operators with their operand so whitespace around operators is optional."""
        raw_tokens = clause_text.split()
        merged: List[str] = []
        index = 0
        while index < len(raw_tokens):
            token = raw_tokens[index]
            if token in _OPERATOR_PREFIXES:
                # POSTCONDITION: an operator must be followed by a target version or wildcard.
                if index + 1 >= len(raw_tokens):
                    raise semver_solver.InvalidRangeError(
                        f"Missing operand after operator {token!r} in range: {original_text!r}",
                        original_text,
                    )
                merged.append(token + raw_tokens[index + 1])
                index += 2
            else:
                merged.append(token)
                index += 1
        return merged

    def _split_operator(self, token: str, original_text: str) -> Tuple[str, str]:
        """Splits a merged comparator token into its operator prefix and operand."""
        for prefix in _OPERATOR_PREFIXES:
            if token.startswith(prefix):
                # Merge of bare operator tokens guarantees a non-empty operand here.
                return prefix, token[len(prefix):]
        return "==", token

    def _parse_literal(self, text: str, original_text: str) -> semver_solver.Version:
        """Parses a fully-qualified SemVer literal, rejecting partial or wildcard forms."""
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            raise semver_solver.InvalidRangeError(
                f"Expected a fully qualified version but found {text!r} in range: {original_text!r}",
                original_text,
            )
        major_text, minor_text, patch_text, prerelease_text, build_text = match.groups()
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build = tuple(build_text.split(".")) if build_text else ()
        return semver_solver.Version(
            int(major_text), int(minor_text), int(patch_text), prerelease, build
        )

    def _expand_operand(
        self, operator: str, operand: str, original_text: str
    ) -> List[_Clause]:
        """Expands a comparator operand into alternative comparator conjunctions."""
        components = self._parse_range_components(operand, original_text)
        if operator in ("^", "~"):
            return [self._expand_tilde_or_caret(operator, components)]
        return self._expand_plain_comparator(operator, components)

    def _parse_range_components(
        self, text: str, original_text: str
    ) -> Tuple[semver_solver.Version, Optional[semver_solver.Version], int]:
        """Parses an operand into a lower bound, upper bound, and specified component count."""
        if _WILDCARD_ALL_PATTERN.match(text):
            return semver_solver.Version(0, 0, 0), None, 0
        wildcard_major = _WILDCARD_MAJOR_PATTERN.match(text)
        if wildcard_major is not None:
            major = int(wildcard_major.group(1))
            return (
                semver_solver.Version(major, 0, 0),
                semver_solver.Version(major + 1, 0, 0),
                1,
            )
        wildcard_minor = _WILDCARD_MINOR_PATTERN.match(text)
        if wildcard_minor is not None:
            major = int(wildcard_minor.group(1))
            minor = int(wildcard_minor.group(2))
            return (
                semver_solver.Version(major, minor, 0),
                semver_solver.Version(major, minor + 1, 0),
                2,
            )
        literal_match = _SEMVER_PATTERN.match(text)
        if literal_match is not None:
            return self._parse_literal(text, original_text), None, 3
        # POSTCONDITION: bare partial versions lacking wildcard characters are invalid.
        if _PARTIAL_VERSION_PATTERN.match(text):
            raise semver_solver.InvalidRangeError(
                f"Partial version {text!r} requires an explicit wildcard in range: {original_text!r}",
                original_text,
            )
        raise semver_solver.InvalidRangeError(
            f"Malformed comparator operand {text!r} in range: {original_text!r}",
            original_text,
        )

    def _expand_plain_comparator(
        self,
        operator: str,
        components: Tuple[semver_solver.Version, Optional[semver_solver.Version], int],
    ) -> List[_Clause]:
        """Expands a basic comparator (equality, inequality, or relational) into bounds."""
        lower, upper, specified = components
        comparison = _OPERATOR_COMPARATORS[operator]
        if specified == 3:
            return [[(comparison, lower)]]
        if comparison is semver_solver.ComparatorOp.EQ:
            if upper is None:
                return [[(semver_solver.ComparatorOp.GE, lower)]]
            return [
                [
                    (semver_solver.ComparatorOp.GE, lower),
                    (semver_solver.ComparatorOp.LT, upper),
                ]
            ]
        if comparison is semver_solver.ComparatorOp.NE:
            if upper is None:
                return []
            # Inequality against a wildcard splits into the below-range and above-range unions.
            return [
                [(semver_solver.ComparatorOp.LT, lower)],
                [(semver_solver.ComparatorOp.GE, upper)],
            ]
        if comparison is semver_solver.ComparatorOp.GE:
            return [[(semver_solver.ComparatorOp.GE, lower)]]
        if comparison is semver_solver.ComparatorOp.LT:
            return [[(semver_solver.ComparatorOp.LT, lower)]]
        if comparison is semver_solver.ComparatorOp.GT:
            if upper is None:
                return []
            return [[(semver_solver.ComparatorOp.GE, upper)]]
        # LE: a wildcard range's inclusive upper bound is exclusive of the next component.
        if upper is None:
            return [[(semver_solver.ComparatorOp.GE, lower)]]
        return [[(semver_solver.ComparatorOp.LT, upper)]]

    def _expand_tilde_or_caret(
        self,
        operator: str,
        components: Tuple[semver_solver.Version, Optional[semver_solver.Version], int],
    ) -> _Clause:
        """Expands caret and tilde prefixes into lower and upper boundary inequalities."""
        lower, wildcard_upper, specified = components
        if operator == "~":
            # POSTCONDITION: tilde ranges cap at the next minor boundary.
            upper = wildcard_upper
            if upper is None:
                return [(semver_solver.ComparatorOp.GE, lower)]
            return [
                (semver_solver.ComparatorOp.GE, lower),
                (semver_solver.ComparatorOp.LT, upper),
            ]
        # POSTCONDITION: caret ranges expand from the first non-zero component boundary.
        if lower.major > 0:
            caret_upper = semver_solver.Version(lower.major + 1, 0, 0)
        elif lower.minor > 0:
            caret_upper = semver_solver.Version(0, lower.minor + 1, 0)
        elif lower.patch > 0:
            caret_upper = semver_solver.Version(0, 0, lower.patch + 1)
        elif specified == 0:
            return [(semver_solver.ComparatorOp.GE, lower)]
        elif specified == 1:
            caret_upper = semver_solver.Version(1, 0, 0)
        elif specified == 2:
            caret_upper = semver_solver.Version(0, 1, 0)
        else:
            caret_upper = semver_solver.Version(0, 0, 1)
        return [
            (semver_solver.ComparatorOp.GE, lower),
            (semver_solver.ComparatorOp.LT, caret_upper),
        ]

    def _compare_against(
        self,
        version: semver_solver.Version,
        operator: semver_solver.ComparatorOp,
        bound: semver_solver.Version,
    ) -> bool:
        """Tests a candidate version against a single comparator with precedence ordering."""
        ordering = self.compare_precedence(version, bound)
        if operator is semver_solver.ComparatorOp.EQ:
            return ordering == 0
        if operator is semver_solver.ComparatorOp.NE:
            return ordering != 0
        if operator is semver_solver.ComparatorOp.LT:
            return ordering < 0
        if operator is semver_solver.ComparatorOp.LE:
            return ordering <= 0
        if operator is semver_solver.ComparatorOp.GT:
            return ordering > 0
        return ordering >= 0

    def _targets_prerelease(
        self, clauses: List[_Clause], version: semver_solver.Version
    ) -> bool:
        """Detects whether a clause explicitly targets the candidate's prerelease tuple."""
        for clause in clauses:
            for _, bound in clause:
                if (
                    bound.prerelease
                    and bound.major == version.major
                    and bound.minor == version.minor
                    and bound.patch == version.patch
                ):
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
        # POSTCONDITION: the release registers into the repository under its package name.
        bucket = self._packages.setdefault(release.name, [])
        bucket.append(release)
        engine = get_singleton(semver_solver.VersionEngine)
        # POSTCONDITION: releases stay sorted by version precedence descending.
        bucket.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(
                    right.version, left.version
                )
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # POSTCONDITION: unregistered names raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                f"Package not found: {name!r}", name
            )
        # POSTCONDITION: produces a shallow copy of the descending sorted releases.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        # POSTCONDITION: True exactly when the package name exists in the repository.
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # POSTCONDITION: produces the set of all registered package names.
        return set(self._packages)


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
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        # POSTCONDITION: accumulated constraints initialize from the root dependencies.
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True
            # POSTCONDITION: MRV selects the unassigned package with fewest viable releases.
            candidates: Dict[str, List[semver_solver.PackageRelease]] = {}
            for name in unassigned:
                try:
                    available = repository.get_releases(name)
                except semver_solver.PackageNotFoundError:
                    # POSTCONDITION: unregistered packages carry zero candidates.
                    available = []
                candidates[name] = [
                    release
                    for release in available
                    if all(
                        engine.satisfies(release.version, constraint)
                        for _, constraint in accumulated[name]
                    )
                ]
            selected = min(unassigned, key=lambda name: (len(candidates[name]), name))
            options = candidates[selected]
            if not options:
                # POSTCONDITION: exhausted candidates record a conflict and backtrack.
                requesters = [source for source, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # POSTCONDITION: viable releases explore in descending precedence order.
            for candidate in options:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                # POSTCONDITION: candidate dependencies merge into accumulated constraints.
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                        ):
                            # POSTCONDITION: assigned version violations trigger backtracking.
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires "
                                f"{dependency.name} {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
                # Undo this branch's assignments and constraints before the next candidate.
                for name, entry in newly_added:
                    accumulated[name].remove(entry)
                    if not accumulated[name]:
                        del accumulated[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if backtrack():
            selected_versions = {
                name: release.version for name, release in assignment.items()
            }
            # POSTCONDITION: successful assignment compiles into a ResolutionOutcome.
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )
        # POSTCONDITION: exhausted search raises ResolutionConflictError with derivation steps.
        raise semver_solver.ResolutionConflictError(
            "Dependency resolution failed: " + "; ".join(conflict_trail),
            tuple(sorted(conflicting_packages)),
            "\n".join(conflict_trail),
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
# LAST_CLEANED: 2026-10-29T20:12:58Z
# LAST_CHANGED: 2026-10-29T20:12:58Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 151165b2d5b0
# COVERAGE_AUDIT: 2026-10-29T20:12:58Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T20:12:58Z
# PRETENSE_QA_AUDIT: 2026-10-29T20:12:58Z
# QA_AUDIT: 2026-10-29T20:12:58Z
# --- END CLEANROOM METADATA ---
