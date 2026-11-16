# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261115_195513_deepseek-flash_semver_solver_pretense
# Timestamp: 2026-11-15T19:55:13.734314+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 5
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 274,000
#   Cached Inbound Tokens:   11,886,976
#   Outbound Tokens:         283,620
#   Total Tokens:            12,444,596
#   Financial Cost ($USD):   $0.2469
#   Wall Clock Duration:     1539.64s
#   Step Latencies (s):      [383.9, 553.1, 204.6, 81.9, 71.5, 20.3, 317.8, 53.4, 92.3, 20.3, 63.4, 40.8, 20.3, 20.3]
#   Role Execution Rounds:   lib: 2, pretense_coverage: 3, pretense_impl: 4, pretense_intf: 1, pretense_qa: 4 (Total: 14)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       3
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Interface module for SemVer 2.0.0 parsing and dependency resolution."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __post_init__(self) -> None:
        # Keep the standard exception arguments aligned with the diagnostic message.
        Exception.__init__(self, self.message)


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
            text = text + "-" + ".".join(self.prerelease)
        if self.build:
            text = text + "+" + ".".join(self.build)
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T20:01:23Z
# LAST_CHANGED: 2026-11-15T20:01:23Z
# CHANGE: Implement SemVer interface module: dataclass exception hierarchy (SemVerError, InvalidVersionError, InvalidRangeError, ResolutionConflictError, PackageNotFoundError) with structured attributes and message-preserving str, ComparatorOp enum, frozen data types (Version with is_prerelease/format/__str__, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome), and @poly_type Protocol services (VersionEngine, PackageRepository, DependencySolver) with contracted operation stubs matching low/semver_solver.pyi.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Concrete realization of SemVer 2.0.0 parsing, precedence, and dependency resolution."""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import semver_solver


# Regular expression capturing the full SemVer 2.0.0 grammar. Numeric
# identifiers reject leading zeroes while build metadata identifiers accept them.
_SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9][0-9]*)"
    r"\.(?P<minor>0|[1-9][0-9]*)"
    r"\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>"
    r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*"
    r"))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)

# Characters that act as wildcard placeholders in a partial version expression.
_WILDCARD_PARTS = frozenset({"x", "X", "*"})

# Relational and prefix operators recognized on a range comparator.
_COMPARATOR_PATTERN = re.compile(r"(==|!=|<=|>=|=|<|>|\^|~)?(.*)")
_OPERATOR_TOKENS = frozenset({"==", "!=", "<=", ">=", "=", "<", ">", "^", "~"})
_NUMERIC_PART_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)")


def _match_version(text: str) -> Optional[re.Match[str]]:
    """Matches a complete SemVer 2.0.0 version string, returning the match or None."""
    return _SEMVER_PATTERN.fullmatch(text)


def _parse_version_or_none(text: str) -> Optional[semver_solver.Version]:
    """Parses a full semantic version, returning None when the text is not valid SemVer."""
    match = _match_version(text)
    if match is None:
        return None
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build = tuple(build_text.split(".")) if build_text else ()
    return semver_solver.Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
        build,
    )


def _parse_wildcard(text: str) -> Optional[Tuple[int, int, int, int]]:
    """Parses a wildcard partial expression into numeric prefix and prefix length."""
    parts = text.split(".")
    if not parts or len(parts) > 3:
        return None
    wildcard_index: Optional[int] = None
    for index, part in enumerate(parts):
        if part in _WILDCARD_PARTS:
            wildcard_index = index
            break
    if wildcard_index is None:
        return None
    # Any component after the first wildcard must itself be a wildcard placeholder.
    for part in parts[wildcard_index:]:
        if part not in _WILDCARD_PARTS:
            return None
    numbers: List[int] = []
    for part in parts[:wildcard_index]:
        if _NUMERIC_PART_PATTERN.fullmatch(part) is None:
            return None
        numbers.append(int(part))
    while len(numbers) < 3:
        numbers.append(0)
    return numbers[0], numbers[1], numbers[2], wildcard_index


def _wildcard_lower(major: int, minor: int, patch: int, prefix_length: int) -> Optional[semver_solver.Version]:
    """Returns the inclusive lower bound of the wildcard interval, when one exists."""
    if prefix_length == 0:
        return None
    return semver_solver.Version(major, minor, patch)


def _wildcard_upper(major: int, minor: int, prefix_length: int) -> Optional[semver_solver.Version]:
    """Returns the exclusive upper bound of the wildcard interval, when one exists."""
    if prefix_length == 0:
        return None
    if prefix_length == 1:
        return semver_solver.Version(major + 1, 0, 0)
    return semver_solver.Version(major, minor + 1, 0)


def _caret_upper(version: semver_solver.Version) -> semver_solver.Version:
    """Returns the exclusive caret upper bound based on the first non-zero component."""
    if version.major > 0:
        return semver_solver.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_solver.Version(0, version.minor + 1, 0)
    return semver_solver.Version(0, 0, version.patch + 1)


def _tilde_upper(version: semver_solver.Version) -> semver_solver.Version:
    """Returns the exclusive tilde upper bound pinned to the next minor version."""
    return semver_solver.Version(version.major, version.minor + 1, 0)


def _expand_full_version(
    op_text: str,
    version: semver_solver.Version,
) -> List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
    """Expands one comparator over a full version into alternative comparator sets."""
    if op_text == "^":
        return [[
            (semver_solver.ComparatorOp.GE, version),
            (semver_solver.ComparatorOp.LT, _caret_upper(version)),
        ]]
    if op_text == "~":
        return [[
            (semver_solver.ComparatorOp.GE, version),
            (semver_solver.ComparatorOp.LT, _tilde_upper(version)),
        ]]
    relational_ops = {
        "": semver_solver.ComparatorOp.EQ,
        "=": semver_solver.ComparatorOp.EQ,
        "==": semver_solver.ComparatorOp.EQ,
        "!=": semver_solver.ComparatorOp.NE,
        "<": semver_solver.ComparatorOp.LT,
        "<=": semver_solver.ComparatorOp.LE,
        ">": semver_solver.ComparatorOp.GT,
        ">=": semver_solver.ComparatorOp.GE,
    }
    return [[(relational_ops[op_text], version)]]


def _expand_wildcard(
    op_text: str,
    wildcard: Tuple[int, int, int, int],
) -> List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
    """Expands one comparator over a wildcard partial into alternative comparator sets."""
    major, minor, patch, prefix_length = wildcard
    lower = _wildcard_lower(major, minor, patch, prefix_length)
    upper = _wildcard_upper(major, minor, prefix_length)
    # Caret ranges bound by the major component when it is non-zero, otherwise by
    # the minor component, matching wildcard prefix semantics.
    if op_text == "^" and prefix_length == 2 and major > 0:
        upper = semver_solver.Version(major + 1, 0, 0)
    interval: List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]] = []
    if lower is not None:
        interval.append((semver_solver.ComparatorOp.GE, lower))
    if upper is not None:
        interval.append((semver_solver.ComparatorOp.LT, upper))
    if op_text in ("", "=", "=="):
        return [interval]
    if op_text == "!=":
        if lower is None or upper is None:
            return []
        return [[(semver_solver.ComparatorOp.LT, lower)], [(semver_solver.ComparatorOp.GE, upper)]]
    if op_text == ">=":
        if lower is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.GE, lower)]]
    if op_text == ">":
        if upper is None:
            return []
        return [[(semver_solver.ComparatorOp.GE, upper)]]
    if op_text == "<":
        if lower is None:
            return []
        return [[(semver_solver.ComparatorOp.LT, lower)]]
    if op_text == "<=":
        if upper is None:
            return [[]]
        return [[(semver_solver.ComparatorOp.LT, upper)]]
    # Caret and tilde share the plain wildcard interval form.
    return [interval]


def _expand_comparator(
    op_text: str,
    operand_text: str,
) -> List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
    """Expands a single comparator expression into alternative comparator sets."""
    wildcard = _parse_wildcard(operand_text)
    if wildcard is not None:
        return _expand_wildcard(op_text, wildcard)
    version = _parse_version_or_none(operand_text)
    if version is None:
        raise semver_solver.InvalidRangeError(
            f"Malformed version or wildcard expression '{operand_text}' in range.",
            operand_text,
        )
    return _expand_full_version(op_text, version)


def _lower_bound(text: str) -> Optional[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
    """Expands the lower bound of a hyphen range, returning None when malformed."""
    wildcard = _parse_wildcard(text)
    if wildcard is not None:
        major, minor, patch, prefix_length = wildcard
        if prefix_length == 0:
            return []
        return [(semver_solver.ComparatorOp.GE, semver_solver.Version(major, minor, patch))]
    version = _parse_version_or_none(text)
    if version is None:
        return None
    return [(semver_solver.ComparatorOp.GE, version)]


def _upper_bound(text: str) -> Optional[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
    """Expands the upper bound of a hyphen range, returning None when malformed."""
    wildcard = _parse_wildcard(text)
    if wildcard is not None:
        major, minor, _, prefix_length = wildcard
        upper = _wildcard_upper(major, minor, prefix_length)
        if upper is None:
            return []
        return [(semver_solver.ComparatorOp.LT, upper)]
    version = _parse_version_or_none(text)
    if version is None:
        return None
    return [(semver_solver.ComparatorOp.LE, version)]


def _parse_comparator_tokens(tokens: List[str]) -> List[Tuple[str, str]]:
    """Pairs operator tokens with operands, splitting tokens that embed both."""
    comparators: List[Tuple[str, str]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATOR_TOKENS:
            if index + 1 >= len(tokens):
                raise semver_solver.InvalidRangeError(
                    f"Operator '{token}' is missing a version operand.",
                    token,
                )
            comparators.append((token, tokens[index + 1]))
            index += 2
            continue
        match = _COMPARATOR_PATTERN.fullmatch(token)
        if match is None:
            # The comparator pattern matches any token, so a failed match is a
            # defensive tripwire rather than a reachable rejection path.
            with unreachable:
                raise semver_solver.InvalidRangeError(
                    f"Malformed range comparator '{token}'.",
                    token,
                )
        op_text = match.group(1)
        operand_text = match.group(2)
        if op_text is None:
            op_text = ""
        if not operand_text:
            # Bare operator tokens are handled above, so an empty operand can
            # only arise from an already rejected token shape.
            with unreachable:
                raise semver_solver.InvalidRangeError(
                    f"Range comparator '{token}' is missing a version operand.",
                    token,
                )
        comparators.append((op_text, operand_text))
        index += 1
    return comparators


def _expand_clause(
    clause: str,
) -> List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
    """Expands one whitespace-delimited clause into alternative comparator sets."""
    tokens = clause.split()
    if not tokens:
        # Blank clauses are rejected by the range trimming stage before any
        # clause expansion runs.
        with unreachable:
            raise semver_solver.InvalidRangeError("Empty version range clause.", clause)
    if len(tokens) == 3 and tokens[1] == "-":
        lower = _lower_bound(tokens[0])
        upper = _upper_bound(tokens[2])
        if lower is None or upper is None:
            raise semver_solver.InvalidRangeError(
                f"Malformed hyphen range bounds '{clause}'.",
                clause,
            )
        return [lower + upper]
    alternatives: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]] = [[]]
    for op_text, operand_text in _parse_comparator_tokens(tokens):
        expansion = _expand_comparator(op_text, operand_text)
        combined: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]] = []
        for prefix in alternatives:
            for conjunction in expansion:
                combined.append(prefix + conjunction)
        alternatives = combined
        if not alternatives:
            return []
    return alternatives


def _compile_range(text: str) -> List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
    """Compiles a union range expression into disjunctive normal form comparator sets."""
    compiled: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]] = []
    for raw_clause in text.split("||"):
        clause = raw_clause.strip()
        if not clause:
            # Range text is validated before compilation, so a blank clause is
            # a defensive tripwire rather than a reachable rejection path.
            with unreachable:
                raise semver_solver.InvalidRangeError("Empty version range clause.", text)
        compiled.extend(_expand_clause(clause))
    return compiled


def _trim_range(text: str) -> str:
    """Trims a range expression, validating that no union clause is empty."""
    stripped = text.strip()
    if not stripped:
        raise semver_solver.InvalidRangeError("Version range expression is empty.", text)
    if "," in stripped:
        raise semver_solver.InvalidRangeError(
            "Commas are not permitted as range comparators; use whitespace delimiters.",
            text,
        )
    for raw_clause in stripped.split("||"):
        if not raw_clause.strip():
            raise semver_solver.InvalidRangeError("Empty version range clause.", text)
    return stripped


def _matches_comparator(
    engine: semver_solver.VersionEngine,
    version: semver_solver.Version,
    op: semver_solver.ComparatorOp,
    boundary: semver_solver.Version,
) -> bool:
    """Evaluates one comparator against a candidate version using precedence ordering."""
    result = engine.compare_precedence(version, boundary)
    if op is semver_solver.ComparatorOp.EQ:
        return result == 0
    if op is semver_solver.ComparatorOp.NE:
        return result != 0
    if op is semver_solver.ComparatorOp.LT:
        return result < 0
    if op is semver_solver.ComparatorOp.LE:
        return result <= 0
    if op is semver_solver.ComparatorOp.GT:
        return result > 0
    return result >= 0


def _targets_prerelease(version: semver_solver.Version) -> bool:
    """Indicates whether a version carries pre-release identifiers."""
    return len(version.prerelease) > 0


@singleton
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = "system"

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        """Parses a version string conforming to SemVer 2.0.0."""
        match = _match_version(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                f"Version string '{text}' does not conform to SemVer 2.0.0 grammar.",
                text,
            )
        prerelease_text = match.group("prerelease")
        build_text = match.group("build")
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build = tuple(build_text.split(".")) if build_text else ()
        return semver_solver.Version(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
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
        """Determines ordering precedence between two semantic versions."""
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1
        # A normal version outranks any pre-release sharing the same numeric core.
        if v1.prerelease and not v2.prerelease:
            return -1
        if v2.prerelease and not v1.prerelease:
            return 1
        for left, right in zip(v1.prerelease, v2.prerelease):
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                if int(left) != int(right):
                    return -1 if int(left) < int(right) else 1
            elif left_numeric:
                return -1
            elif right_numeric:
                return 1
            elif left != right:
                return -1 if left < right else 1
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        return 0

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        trimmed = _trim_range(text)
        for clause in trimmed.split("||"):
            _expand_clause(clause.strip())
        return semver_solver.VersionRange(trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        compiled = _compile_range(range_constraint.raw_text)
        for clause in compiled:
            # Pre-releases only match a clause that explicitly names the same
            # numeric core with its own pre-release identifier.
            if _targets_prerelease(version) and not include_prerelease:
                explicitly_targeted = False
                for _, boundary in clause:
                    if (
                        _targets_prerelease(boundary)
                        and boundary.major == version.major
                        and boundary.minor == version.minor
                        and boundary.patch == version.patch
                    ):
                        explicitly_targeted = True
                        break
                if not explicitly_targeted:
                    continue
            if all(
                _matches_comparator(self, version, op, boundary)
                for op, boundary in clause
            ):
                return True
        return False


@singleton
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = "system"

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: -engine.compare_precedence(left.version, right.version)
            )
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by precedence descending."""
        releases = self._packages.get(name)
        if releases is None:
            raise semver_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in the repository.",
                name,
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


@singleton
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = "system"

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        """Computes a mutually compatible version assignment for root dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Each package maps to the ordered constraints imposed on it and their requester.
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_releases(name: str) -> List[semver_solver.PackageRelease]:
            # An unregistered package simply contributes no candidate releases.
            try:
                available = repository.get_releases(name)
            except semver_solver.PackageNotFoundError:
                return []
            viable: List[semver_solver.PackageRelease] = []
            for release in available:
                if all(
                    engine.satisfies(release.version, constraint, False)
                    for _, constraint in accumulated[name]
                ):
                    viable.append(release)
            return viable

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True
            candidate_map = {name: viable_releases(name) for name in unassigned}
            # Minimum Remaining Values ordering, breaking ties by package name.
            selected = min(
                unassigned,
                key=lambda name: (len(candidate_map[name]), name),
            )
            candidates = candidate_map[selected]
            if not candidates:
                requesters = [source for source, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints "
                    f"from {requesters}"
                )
                return False
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        assigned = assignment[dependency.name]
                        if not engine.satisfies(
                            assigned.version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' {candidate.version} requires "
                                f"'{dependency.name}' {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
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
            return semver_solver.ResolutionOutcome(
                selected_versions=selected_versions,
                derivation_steps=tuple(derivation_steps),
            )
        conflicting = tuple(sorted(conflicting_packages))
        explanation_parts = derivation_steps + conflict_trail
        explanation = "\n".join(explanation_parts)
        raise semver_solver.ResolutionConflictError(
            f"Unable to resolve dependencies for packages {list(conflicting)}.",
            conflicting,
            explanation,
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T20:20:44Z
# LAST_CHANGED: 2026-11-15T20:17:21Z
# CHANGE: Resolve pretense_coverage unreachable-logic feedback: quarantine the four defensive guard bodies (comparator pattern fullmatch failure, empty comparator operand, empty clause token list, empty compilation clause) in 'with unreachable:' blocks imported from support.lib.framework instead of leaving them as bare rejection paths, preserving the guards as tripwires while excluding unreachable logic from coverage; no behavioral change to reachable parse/range/solver logic.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T20:20:44Z
# PRETENSE_QA_AUDIT: 2026-11-15T20:20:19Z
# --- END AUTOFAB METADATA ---
