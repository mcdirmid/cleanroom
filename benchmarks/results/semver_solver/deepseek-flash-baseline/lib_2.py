# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_040027_deepseek-flash_semver_solver_baseline
# Timestamp: 2026-11-05T04:00:27.146304+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 64,656
#   Cached Inbound Tokens:   6,375,296
#   Outbound Tokens:         94,976
#   Total Tokens:            6,534,928
#   Financial Cost ($USD):   $0.0858
#   Wall Clock Duration:     564.64s
#   Step Latencies (s):      [456.3, 93.8]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       18
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
"""Low-level interface specification for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error. Verification suites MUST NOT assert on specific wording or prefixes within message, and MUST assert on exception types and structured attributes.
    """

    message: str

    def __str__(self) -> str:
        """Returns the diagnostic message."""
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
        """Parses a version string conforming to SemVer 2.0.0.

        Args:
            text: Raw version string to parse.

        Returns:
            The parsed immutable Version record.

        Raises:
            InvalidVersionError: If text violates SemVer 2.0.0 grammar or contains leading zeroes.

        POSTCONDITIONS:
        - MUST parse valid SemVer 2.0.0 strings into Version records with major, minor, patch, prerelease, and build tuples.
        - WHEN text contains leading zeroes in numeric identifiers or violates grammar, MUST raise InvalidVersionError.
        """
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions.

        Args:
            v1: First semantic version.
            v2: Second semantic version.

        Returns:
            Negative integer if v1 < v2, zero if v1 == v2, positive integer if v1 > v2.

        POSTCONDITIONS:
        - MUST evaluate to a negative integer when v1 < v2, zero when v1 == v2, and a positive integer when v1 > v2 under SemVer 2.0.0 RFC rules.
        - MUST compare major, minor, and patch numerically.
        - MUST rank normal versions higher than prerelease versions sharing identical major, minor, and patch numbers.
        - MUST compare prerelease segments numerically when both numeric, ASCII-lexicographically when string, and rank numeric below string.
        - MUST ignore build metadata entirely when comparing precedence.
        """
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record.

        Args:
            text: Raw range expression text.

        Returns:
            The parsed VersionRange.

        Raises:
            InvalidRangeError: If text contains malformed range syntax.

        POSTCONDITIONS:
        - MUST parse range expression text supporting basic comparators (==, =, !=, <, <=, >, >=), caret ranges (^), tilde ranges (~), wildcards (*, x, X, M.x, M.*, M.m.x, M.m.*), hyphen ranges (M1.m1.p1 - M2.m2.p2), and unions (||).
        - MUST trim surrounding whitespace around range expressions and individual clauses, storing the trimmed range expression in raw_text.
        - MUST accept optional whitespace between relational/prefix operators and target versions or wildcards (e.g. '>= 1.0.0' is equivalent to '>=1.0.0').
        - MUST delimit comparators within clauses strictly by whitespace; commas are not permitted.
        - WHEN text supplies bare partial versions lacking wildcard characters across any comparator or hyphen expression (such as '1', '1.2', '^0.0', or '1.2 - 2.3'), MUST raise InvalidRangeError.
        - WHEN text is empty, contains only whitespace, contains empty union clauses, uses comma delimiters, or violates range syntax, MUST raise InvalidRangeError.
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

        Args:
            version: Candidate semantic version to test.
            range_constraint: Version range to evaluate against.
            include_prerelease: Whether to allow pre-release versions to match non-prerelease ranges.

        Returns:
            True if the version satisfies the range, False otherwise.

        POSTCONDITIONS:
        - MUST evaluate to True when version satisfies range_constraint, and False otherwise.
        - WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False unless range explicitly targets that prerelease by specifying a prerelease identifier sharing the same major, minor, and patch numbers.
        - WHEN include_prerelease is True, MUST evaluate candidate prerelease version directly against comparator boundary inequalities using precedence ordering without shifting numerical boundaries (e.g. 1.0.0-alpha ranks strictly lower than 1.0.0 and does not satisfy >=1.0.0).
        """
        ...


@poly_type
class PackageRepository(Protocol):
    """Maintains indexed package publications and release histories."""

    @operation
    def register_package(self, release: PackageRelease) -> None:
        """Registers a package release with its declared dependencies.

        Args:
            release: Package release publication to register.

        POSTCONDITIONS:
        - MUST register the package release into the repository.
        """
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending.

        Args:
            name: Package name to look up.

        Returns:
            List of package releases ordered by version precedence descending.

        Raises:
            PackageNotFoundError: If name is not registered in the repository.

        POSTCONDITIONS:
        - MUST yield all registered releases for package name ordered by version precedence descending.
        - WHEN name is not registered, MUST raise PackageNotFoundError.
        """
        ...

    @operation
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository.

        Args:
            name: Package name to check.

        Returns:
            True if the package exists, False otherwise.

        POSTCONDITIONS:
        - MUST evaluate to True when package name exists in repository, and False otherwise.
        """
        ...

    @operation
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names.

        Returns:
            Set of registered package name strings.

        POSTCONDITIONS:
        - MUST produce the set of all registered package names.
        """
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

        Args:
            root_dependencies: Initial package dependencies to satisfy.

        Returns:
            ResolutionOutcome recording selected package versions and derivation steps.

        Raises:
            ResolutionConflictError: If dependencies cannot be satisfied mutually.

        POSTCONDITIONS:
        - MUST compute a mutually compatible set of package releases satisfying root and transitive dependencies.
        - MUST select the highest precedence compatible version for each package.
        - WHEN dependencies are unsatisfiable or reference unregistered packages absent from repository, MUST raise ResolutionConflictError detailing conflicting packages and derivation explanation without allowing PackageNotFoundError to escape.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:09:51Z
# LAST_CHANGED: 2026-11-05T04:09:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 26907f3f9e95
# COVERAGE_AUDIT: 2026-11-05T04:09:51Z
# QA_AUDIT: 2026-11-05T04:09:51Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
"""Low-level implementation specification for SemVer 2.0 parsing and dependency resolution."""

from __future__ import annotations

from functools import cmp_to_key
import re
from typing import Collection, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import semver_solver


_Comparator = Tuple[str, semver_solver.Version]

_VERSION_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)
_IDENTIFIER_PATTERN = re.compile(r"^[0-9A-Za-z-]+$")
_NUMERIC_PATTERN = re.compile(r"^(0|[1-9]\d*)$")
_WILDCARD_TOKENS = frozenset({"*", "x", "X"})
_OPERATOR_PREFIXES = ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~")
_WILDCARD_CEILING = 1_000_000_000


def _split_operator(token: str) -> Tuple[str, str]:
    """Splits a leading relational or prefix operator from a comparator token."""
    for prefix in _OPERATOR_PREFIXES:
        if token.startswith(prefix):
            return prefix, token[len(prefix):]
    return "", token


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
        # Grammar validation: non-negative numeric components without leading zeroes.
        match = _VERSION_PATTERN.fullmatch(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version: {text}",
                raw_text=text,
            )
        major = match.group(1)
        minor = match.group(2)
        patch = match.group(3)
        prerelease_text = match.group(4)
        build_text = match.group(5)
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build = tuple(build_text.split(".")) if build_text else ()
        return semver_solver.Version(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
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
        # Numeric components compare first, in sequence.
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return -1 if left < right else 1
        # A normal version outranks a prerelease sharing the same numeric components.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # Compare prerelease segments position by position.
        for first, second in zip(v1.prerelease, v2.prerelease):
            if first == second:
                continue
            first_numeric = first.isdigit()
            second_numeric = second.isdigit()
            if first_numeric and second_numeric:
                first_value = int(first)
                second_value = int(second)
                if first_value != second_value:
                    return -1 if first_value < second_value else 1
                continue
            if first_numeric != second_numeric:
                return -1 if first_numeric else 1
            return -1 if first < second else 1
        # A longer prerelease sequence outranks a shorter matching prefix.
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        """Parses a version range expression into an immutable VersionRange record."""
        # Trim surrounding whitespace before storing the canonical expression.
        trimmed = text.strip()
        self._compile_range(trimmed)
        return semver_solver.VersionRange(raw_text=trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint."""
        for clause in self._compile_range(range_constraint.raw_text):
            if not self._all_comparators_match(version, clause):
                continue
            # Prereleases only match clauses explicitly targeting their numeric triple.
            if version.is_prerelease and not include_prerelease:
                if not self._targets_prerelease(version, clause):
                    continue
            return True
        return False

    def _compile_range(self, raw_text: str) -> List[List[_Comparator]]:
        """Compiles a raw range expression into disjunctive normal form comparator clauses."""
        text = raw_text.strip()
        if not text:
            raise semver_solver.InvalidRangeError(
                message="Range expression must not be empty",
                raw_range=raw_text,
            )
        clauses: List[List[_Comparator]] = []
        for clause in text.split("||"):
            stripped = clause.strip()
            if not stripped or "," in stripped:
                raise semver_solver.InvalidRangeError(
                    message=f"Malformed range expression: {raw_text}",
                    raw_range=raw_text,
                )
            clauses.append(self._compile_clause(stripped, raw_text))
        return clauses

    def _compile_clause(self, clause: str, raw_range: str) -> List[_Comparator]:
        """Compiles a single union clause into its conjunctive comparator list."""
        parts = self._split_clause_tokens(clause, raw_range)
        if "-" in parts:
            if len(parts) != 3 or parts[1] != "-":
                raise semver_solver.InvalidRangeError(
                    message=f"Malformed hyphen range: {raw_range}",
                    raw_range=raw_range,
                )
            lower_components, lower_prerelease, lower_build, lower_wildcard = (
                self._parse_version_spec(parts[0], raw_range)
            )
            upper_components, upper_prerelease, upper_build, upper_wildcard = (
                self._parse_version_spec(parts[2], raw_range)
            )
            if lower_wildcard or upper_wildcard:
                raise semver_solver.InvalidRangeError(
                    message=f"Hyphen range operands must be complete versions: {raw_range}",
                    raw_range=raw_range,
                )
            lower = self._make_version(
                lower_components, lower_prerelease, lower_build, raw_range
            )
            upper = self._make_version(
                upper_components, upper_prerelease, upper_build, raw_range
            )
            return [(">=", lower), ("<=", upper)]
        comparators: List[_Comparator] = []
        for part in parts:
            comparators.extend(self._compile_comparator(part, raw_range))
        return comparators

    def _split_clause_tokens(self, clause: str, raw_range: str) -> List[str]:
        """Splits a clause into comparator tokens, joining spaced operators to operands."""
        tokens = clause.split()
        parts: List[str] = []
        index = 0
        while index < len(tokens):
            operator, remainder = _split_operator(tokens[index])
            if not remainder and operator:
                if index + 1 >= len(tokens):
                    raise semver_solver.InvalidRangeError(
                        message=f"Missing comparator operand: {raw_range}",
                        raw_range=raw_range,
                    )
                parts.append(operator + tokens[index + 1])
                index += 2
            else:
                parts.append(tokens[index])
                index += 1
        return parts

    def _compile_comparator(self, part: str, raw_range: str) -> List[_Comparator]:
        """Compiles one comparator token into normalized range comparators."""
        operator, remainder = _split_operator(part)
        if not remainder:
            raise semver_solver.InvalidRangeError(
                message=f"Missing comparator operand: {raw_range}",
                raw_range=raw_range,
            )
        components, prerelease, build, wildcard = self._parse_version_spec(
            remainder, raw_range
        )
        if wildcard:
            return self._expand_wildcard(components, operator, raw_range)
        version = self._make_version(components, prerelease, build, raw_range)
        if operator == "^":
            return self._expand_caret(version)
        if operator == "~":
            return self._expand_tilde(version)
        if operator == "" or operator == "=":
            return [("==", version)]
        return [(operator, version)]

    def _parse_version_spec(
        self,
        text: str,
        raw_range: str,
    ) -> Tuple[List[Optional[int]], Tuple[str, ...], Tuple[str, ...], bool]:
        """Parses a version or wildcard operand into components, prerelease, build, wildcard flag."""
        core = text
        build: Tuple[str, ...] = ()
        if "+" in core:
            core, build_text = core.split("+", 1)
            build = self._parse_identifiers(build_text, raw_range)
        prerelease: Tuple[str, ...] = ()
        if "-" in core:
            core, prerelease_text = core.split("-", 1)
            prerelease = self._parse_identifiers(prerelease_text, raw_range)
        parts = core.split(".")
        if not 1 <= len(parts) <= 3:
            raise semver_solver.InvalidRangeError(
                message=f"Malformed version operand: {raw_range}",
                raw_range=raw_range,
            )
        components: List[Optional[int]] = []
        wildcard = False
        for part in parts:
            if part in _WILDCARD_TOKENS:
                wildcard = True
                components.append(None)
            elif wildcard or _NUMERIC_PATTERN.match(part) is None:
                raise semver_solver.InvalidRangeError(
                    message=f"Malformed version operand: {raw_range}",
                    raw_range=raw_range,
                )
            else:
                components.append(int(part))
        while len(components) < 3:
            components.append(None)
        return components, prerelease, build, wildcard

    def _parse_identifiers(self, text: str, raw_range: str) -> Tuple[str, ...]:
        """Parses dot-separated prerelease or build identifiers."""
        identifiers = text.split(".")
        for identifier in identifiers:
            if _IDENTIFIER_PATTERN.match(identifier) is None:
                raise semver_solver.InvalidRangeError(
                    message=f"Malformed version operand: {raw_range}",
                    raw_range=raw_range,
                )
        return tuple(identifiers)

    def _full_components(
        self,
        components: Sequence[Optional[int]],
        raw_range: str,
    ) -> Tuple[int, int, int]:
        """Requires a fully specified numeric component triple."""
        major, minor, patch = components
        if major is None or minor is None or patch is None:
            raise semver_solver.InvalidRangeError(
                message=f"Version operand must be complete: {raw_range}",
                raw_range=raw_range,
            )
        return major, minor, patch

    def _make_version(
        self,
        components: Sequence[Optional[int]],
        prerelease: Tuple[str, ...],
        build: Tuple[str, ...],
        raw_range: str,
    ) -> semver_solver.Version:
        """Builds a Version from validated components."""
        major, minor, patch = self._full_components(components, raw_range)
        return semver_solver.Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
            build=build,
        )

    def _expand_wildcard(
        self,
        components: Sequence[Optional[int]],
        operator: str,
        raw_range: str,
    ) -> List[_Comparator]:
        """Normalizes a wildcard operand into paired comparator inequalities."""
        major = components[0]
        minor = components[1]
        if major is None:
            lower = semver_solver.Version(major=0, minor=0, patch=0)
            upper = semver_solver.Version(major=_WILDCARD_CEILING, minor=0, patch=0)
        elif minor is None:
            lower = semver_solver.Version(major=major, minor=0, patch=0)
            upper = semver_solver.Version(major=major + 1, minor=0, patch=0)
        else:
            lower = semver_solver.Version(major=major, minor=minor, patch=0)
            upper = semver_solver.Version(major=major, minor=minor + 1, patch=0)
        if operator == "" or operator == "==" or operator == "=":
            return [(">=", lower), ("<", upper)]
        if operator == ">=":
            return [(">=", lower)]
        if operator == ">":
            return [(">=", upper)]
        if operator == "<":
            return [("<", lower)]
        if operator == "<=":
            return [("<", upper)]
        raise semver_solver.InvalidRangeError(
            message=f"Unsupported wildcard comparator: {raw_range}",
            raw_range=raw_range,
        )

    def _expand_caret(self, version: semver_solver.Version) -> List[_Comparator]:
        """Expands a caret range at the first non-zero component boundary."""
        if version.major > 0:
            upper = semver_solver.Version(major=version.major + 1, minor=0, patch=0)
        elif version.minor > 0:
            upper = semver_solver.Version(major=0, minor=version.minor + 1, patch=0)
        elif version.patch > 0:
            upper = semver_solver.Version(major=0, minor=0, patch=version.patch + 1)
        else:
            upper = semver_solver.Version(major=0, minor=0, patch=1)
        return [(">=", version), ("<", upper)]

    def _expand_tilde(self, version: semver_solver.Version) -> List[_Comparator]:
        """Expands a tilde range into lower and upper minor boundaries."""
        upper = semver_solver.Version(major=version.major, minor=version.minor + 1, patch=0)
        return [(">=", version), ("<", upper)]

    def _all_comparators_match(
        self,
        version: semver_solver.Version,
        clause: Sequence[_Comparator],
    ) -> bool:
        """Tests a candidate version against every comparator in a clause."""
        return all(
            self._test_comparator(version, operator, bound)
            for operator, bound in clause
        )

    def _targets_prerelease(
        self,
        version: semver_solver.Version,
        clause: Sequence[_Comparator],
    ) -> bool:
        """Detects a clause comparator explicitly targeting the candidate prerelease triple."""
        return any(
            bound.is_prerelease
            and bound.major == version.major
            and bound.minor == version.minor
            and bound.patch == version.patch
            for _, bound in clause
        )

    def _test_comparator(
        self,
        version: semver_solver.Version,
        operator: str,
        bound: semver_solver.Version,
    ) -> bool:
        """Tests a candidate version against a single precedence comparator."""
        precedence = self.compare_precedence(version, bound)
        if operator == "==":
            return precedence == 0
        if operator == "!=":
            return precedence != 0
        if operator == "<":
            return precedence < 0
        if operator == "<=":
            return precedence <= 0
        if operator == ">":
            return precedence > 0
        return precedence >= 0


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing.

    GROUNDING:
    - Maintains _packages dictionary mapping package names to lists of semver_solver.PackageRelease.
    - Coordinates with semver_solver.VersionEngine for release sorting.
    """

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        """Registers a package release with its declared dependencies."""
        engine = get_singleton(semver_solver.VersionEngine)

        def descending(
            left: semver_solver.PackageRelease,
            right: semver_solver.PackageRelease,
        ) -> int:
            return engine.compare_precedence(right.version, left.version)

        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # Re-sort in descending precedence order using version engine comparison.
        releases.sort(key=cmp_to_key(descending))

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        """Retrieves all registered releases for a package name ordered by version precedence descending."""
        releases = self._packages.get(name)
        if releases is None:
            raise semver_solver.PackageNotFoundError(
                message=f"Package not found: {name}",
                package_name=name,
            )
        # Produce a shallow copy of the sorted release list.
        return list(releases)

    @operation
    @override
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository."""
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        """Returns the set of all registered package names."""
        return set(self._packages)


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver.

    GROUNDING:
    - Coordinates with semver_solver.VersionEngine and semver_solver.PackageRepository to resolve compatible release assignments.
    - Delegates search heuristics and conflict recording to backtracking_solver_ext.
    """

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
        constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_candidates(package: str) -> List[semver_solver.PackageRelease]:
            # Unregistered packages evaluate to zero candidate releases.
            try:
                available = repository.get_releases(package)
            except semver_solver.PackageNotFoundError:
                return []
            return [
                release
                for release in available
                if all(
                    engine.satisfies(release.version, range_constraint, False)
                    for _, range_constraint in constraints[package]
                )
            ]

        def backtrack() -> bool:
            # Minimum Remaining Values variable selection with lexical tie-breaking.
            unassigned = [name for name in constraints if name not in assignment]
            if not unassigned:
                return True
            candidates_by_package = {
                name: viable_candidates(name) for name in unassigned
            }
            selected = min(
                unassigned,
                key=lambda name: (len(candidates_by_package[name]), name),
            )
            candidates = candidates_by_package[selected]
            if not candidates:
                requesters = [source for source, _ in constraints[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # Descending precedence value ordering.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # Forward checking against the current partial assignment.
                        if not engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
                # Restore the constraint mapping and assignment before trying alternatives.
                for name, entry in newly_added:
                    constraints[name].remove(entry)
                    if not constraints[name]:
                        del constraints[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not backtrack():
            raise semver_solver.ResolutionConflictError(
                message="Dependency resolution failed",
                conflicting_packages=tuple(sorted(conflicting_packages)),
                explanation="; ".join(conflict_trail),
            )
        selected_versions = {
            name: release.version for name, release in assignment.items()
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
# LAST_CLEANED: 2026-11-05T04:09:51Z
# LAST_CHANGED: 2026-11-05T04:09:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b4f3078e73ec
# COVERAGE_AUDIT: 2026-11-05T04:09:51Z
# QA_AUDIT: 2026-11-05T04:09:51Z
# --- END AUTOFAB METADATA ---
