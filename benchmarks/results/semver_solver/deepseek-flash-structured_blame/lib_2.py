# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_021825_deepseek-flash_semver_solver
# Timestamp: 2026-11-08T02:18:25.094984+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 227,124
#   Cached Inbound Tokens:   22,258,560
#   Outbound Tokens:         289,660
#   Total Tokens:            22,775,344
#   Financial Cost ($USD):   $0.2746
#   Wall Clock Duration:     1864.68s
#   Step Latencies (s):      [183.6, 1072.2, 124.0, 244.4, 10.0, 238.1, 135.2, 143.3, 10.1, 10.1]
#   Role Execution Rounds:   coverage: 2, lib: 2, qa: 3, test: 3 (Total: 10)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       37
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
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
        # Diagnostic rendering delegates to the structured message field.
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
        # Reports whether any pre-release identifiers are present.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Emits the canonical SemVer 2.0.0 textual representation.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # Canonical rendering is equivalent to format().
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        # Canonical rendering exposes the raw range text unchanged.
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

        Raises InvalidVersionError when text contains leading zeroes in numeric
        identifiers or otherwise violates the SemVer 2.0.0 grammar.

        Valid strings parse into Version records carrying major, minor, patch,
        prerelease, and build tuples.
        """
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions.

        Evaluates to a negative integer when v1 is smaller, zero when identical,
        and a positive integer when v1 is larger under SemVer 2.0.0 rules: major,
        minor, and patch are compared numerically, normal versions outrank
        prereleases sharing the same numeric components, prerelease segments are
        compared numerically or ASCII-lexicographically with numeric ranking below
        strings, and build metadata is ignored.
        """
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record.

        Raises InvalidRangeError when text supplies bare partial versions lacking
        wildcard characters across any comparator or hyphen expression (such as
        '1', '1.2', '>1.2', '^0.0', or '1.2 - 2.3'), when text is empty or only
        whitespace, when union alternatives are empty, when commas delimit
        comparators, or when the syntax is otherwise malformed.

        Supports basic comparators (==, =, !=, <, <=, >, >=), caret ranges (^),
        and tilde ranges (~) applied to full semantic versions or wildcard
        expressions, hyphen ranges connecting two bounds, union alternatives
        separated by '||', whitespace trimming, and optional whitespace between
        operators and their targets. The trimmed expression is stored in raw_text.
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

        Evaluates to True when version satisfies range_constraint and False
        otherwise. When version is a prerelease and include_prerelease is False,
        evaluates to False unless the range explicitly targets that prerelease by
        specifying a prerelease identifier sharing the same major, minor, and patch
        numbers. When include_prerelease is True, evaluates the candidate prerelease
        directly against comparator boundary inequalities without shifting
        numerical boundaries (1.0.0-alpha ranks strictly lower than 1.0.0 and does
        not satisfy >=1.0.0).
        """
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
        """Retrieves all registered releases for a package name ordered by version precedence descending.

        Raises PackageNotFoundError when name is not registered. Yields all
        registered releases for the package ordered by version precedence
        descending.
        """
        ...

    @operation
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository.

        Evaluates to True when the package name exists in the repository and
        False otherwise.
        """
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

        Raises ResolutionConflictError detailing conflicting packages and
        derivation explanation when dependencies are unsatisfiable or reference
        unregistered packages absent from the repository, without allowing
        PackageNotFoundError to escape. On success computes a mutually compatible
        set of package releases satisfying root and transitive dependencies,
        selecting the highest precedence compatible version for each package.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T02:36:17Z
# LAST_CHANGED: 2026-11-08T02:36:17Z
# CHANGE: Implement interface module: exceptions as mutable dataclasses with message rendering, frozen data types with concrete Version.format/is_prerelease/__str__ and VersionRange.__str__, and abstract VersionEngine/PackageRepository/DependencySolver protocols with stub operations.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
import re

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

# A compiled comparator pairs a relational operator with its boundary version.
_Comparator = Tuple[str, semver_solver.Version]

# Relational, caret, and tilde operator tokens recognized at the head of a comparator.
_OPERATORS: Tuple[str, ...] = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")

# Strict SemVer 2.0.0 grammar: three non-negative numeric components without leading
# zeroes, optional dot-separated pre-release identifiers, optional build metadata.
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

# Range version expression: numeric or wildcard components, optional pre-release
# identifiers, and optional build metadata.
_VERSION_EXPR_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*|\*|[xX])"
    r"(?:\.(0|[1-9][0-9]*|\*|[xX]))?"
    r"(?:\.(0|[1-9][0-9]*|\*|[xX]))?"
    r"(?:-([0-9A-Za-z.-]+))?"
    r"(?:\+([0-9A-Za-z.-]+))?$"
)

_IDENTIFIER_PATTERN = re.compile(r"^[0-9A-Za-z-]+$")

# Sentinel boundary that no non-negative version can be strictly less than.
_UNSATISFIABLE = semver_solver.Version(major=0, minor=0, patch=0)


@singleton_type("system")
class VersionEngine(semver_solver.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing, precedence, and range engine."""

    tier = system

    def __init__(self) -> None:
        # Stateless engine: parsing, precedence, and range algebra need no backing state.
        pass

    @operation
    @override
    def parse_version(self, text: str) -> semver_solver.Version:
        # Precondition: unparseable text violates the grammar, so raise InvalidVersionError.
        if not isinstance(text, str):
            raise semver_solver.InvalidVersionError(
                message=f"Version text must be a string, received {type(text).__name__}",
                raw_text=str(text),
            )
        # Grammar match enforces non-negative components without leading zeroes.
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            raise semver_solver.InvalidVersionError(
                message=f"Version {text!r} does not conform to the SemVer 2.0.0 grammar",
                raw_text=text,
            )
        prerelease = self._parse_prerelease(match.group(4), text)
        build_text = match.group(5)
        build: Tuple[str, ...] = () if build_text is None else tuple(build_text.split("."))
        # Postcondition: valid syntax yields immutable Version records with all components.
        return semver_solver.Version(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=prerelease,
            build=build,
        )

    @operation
    @override
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # Postcondition: major, minor, and patch compare numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1
        # Postcondition: normal versions rank higher than prereleases with equal numbers.
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        # Postcondition: prerelease segments compare position by position.
        for left_identifier, right_identifier in zip(v1.prerelease, v2.prerelease):
            result = self._compare_identifier(left_identifier, right_identifier)
            if result != 0:
                return result
        # Postcondition: a longer prerelease sequence ranks higher on a shared prefix;
        # build metadata is ignored entirely.
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    @operation
    @override
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Postcondition: the trimmed expression is validated and stored in raw_text.
        stripped, _ = self._compile_range(text)
        return semver_solver.VersionRange(raw_text=stripped)

    @operation
    @override
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Postcondition: store the range as disjunctive normal form comparator clauses.
        _, clauses = self._compile_range(range_constraint.raw_text)
        for clause in clauses:
            if self._clause_satisfied(version, clause, include_prerelease):
                return True
        # Postcondition: all clauses failed satisfaction.
        return False

    def _parse_prerelease(self, text: Optional[str], raw_version: str) -> Tuple[str, ...]:
        if text is None:
            return ()
        identifiers = tuple(text.split("."))
        for identifier in identifiers:
            # Precondition: numeric identifiers must not carry leading zeroes.
            if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
                raise semver_solver.InvalidVersionError(
                    message=f"Prerelease identifier {identifier!r} contains a leading zero",
                    raw_text=raw_version,
                )
        return identifiers

    def _compare_identifier(self, left: str, right: str) -> int:
        left_numeric = left.isdigit()
        right_numeric = right.isdigit()
        # Postcondition: numeric segments compare numerically and rank below strings.
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
        # Postcondition: string segments compare ASCII-lexicographically.
        if left == right:
            return 0
        return -1 if left < right else 1

    def _clause_satisfied(
        self,
        version: semver_solver.Version,
        clause: List[_Comparator],
        include_prerelease: bool,
    ) -> bool:
        # Postcondition: prerelease candidates are rejected unless the range explicitly
        # targets a prerelease sharing the same major, minor, and patch numbers.
        if version.is_prerelease and not include_prerelease:
            targeted = False
            for _, boundary in clause:
                if boundary.is_prerelease and (
                    boundary.major,
                    boundary.minor,
                    boundary.patch,
                ) == (version.major, version.minor, version.patch):
                    targeted = True
                    break
            if not targeted:
                return False
        # Postcondition: every comparator in the clause must hold by precedence ordering.
        for operator, boundary in clause:
            comparison = self.compare_precedence(version, boundary)
            if operator == "==" and comparison != 0:
                return False
            if operator == "!=" and comparison == 0:
                return False
            if operator == "<" and comparison >= 0:
                return False
            if operator == "<=" and comparison > 0:
                return False
            if operator == ">" and comparison <= 0:
                return False
            if operator == ">=" and comparison < 0:
                return False
        return True

    def _compile_range(self, text: str) -> Tuple[str, List[List[_Comparator]]]:
        # Precondition: a non-string or empty expression is malformed.
        if not isinstance(text, str):
            raise semver_solver.InvalidRangeError(
                message=f"Range text must be a string, received {type(text).__name__}",
                raw_range=str(text),
            )
        stripped = text.strip()
        if not stripped:
            raise semver_solver.InvalidRangeError(
                message="Range expression is empty",
                raw_range=text,
            )
        # Postcondition: comparators are delimited by whitespace, never by commas.
        if "," in stripped:
            raise semver_solver.InvalidRangeError(
                message="Range comparators must be delimited by whitespace, not commas",
                raw_range=text,
            )
        clauses: List[List[_Comparator]] = []
        for clause_text in stripped.split("||"):
            clause = clause_text.strip()
            # Precondition: union alternatives must not be empty.
            if not clause:
                raise semver_solver.InvalidRangeError(
                    message="Range contains an empty union alternative",
                    raw_range=text,
                )
            # Postcondition: union alternatives are disjoined into separate clauses.
            clauses.extend(self._compile_clause(clause, stripped))
        return stripped, clauses

    def _compile_clause(self, clause: str, raw_range: str) -> List[List[_Comparator]]:
        tokens = clause.split()
        if "-" in tokens:
            # Postcondition: hyphen ranges connect exactly two bounds.
            if len(tokens) != 3 or tokens[1] != "-":
                raise semver_solver.InvalidRangeError(
                    message=f"Malformed hyphen range {clause!r}",
                    raw_range=raw_range,
                )
            return [self._compile_hyphen(tokens[0], tokens[2], raw_range)]
        # Postcondition: operators may be separated from their targets by whitespace.
        merged: List[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in _OPERATORS:
                if index + 1 >= len(tokens):
                    raise semver_solver.InvalidRangeError(
                        message=f"Operator {token!r} lacks a target version",
                        raw_range=raw_range,
                    )
                merged.append(token + tokens[index + 1])
                index += 2
            else:
                merged.append(token)
                index += 1
        # Postcondition: comparators within a clause are conjoined, so alternatives multiply.
        combined: List[List[_Comparator]] = [[]]
        for part in merged:
            alternatives = self._compile_comparator(part, raw_range)
            expanded: List[List[_Comparator]] = []
            for existing in combined:
                for alternative in alternatives:
                    expanded.append(existing + alternative)
            combined = expanded
        return combined

    def _compile_comparator(self, part: str, raw_range: str) -> List[List[_Comparator]]:
        operator = ""
        remaining = part
        for candidate in _OPERATORS:
            if part.startswith(candidate):
                operator = candidate
                remaining = part[len(candidate):]
                break
        if not remaining:
            raise semver_solver.InvalidRangeError(
                message=f"Comparator {part!r} lacks a target version",
                raw_range=raw_range,
            )
        components, wildcard, prerelease = self._parse_version_expr(remaining, raw_range)
        if wildcard:
            # Postcondition: wildcards normalize into paired lower and upper bounds.
            return self._expand_wildcard(operator, components)
        # Bare partial versions lacking wildcards are prohibited, so three components exist.
        version = semver_solver.Version(
            major=components[0],
            minor=components[1],
            patch=components[2],
            prerelease=prerelease,
        )
        # Postcondition: equality, caret, and tilde prefixes expand into comparator clauses.
        if operator in ("", "=", "=="):
            return [[("==", version)]]
        if operator == "!=":
            return [[("!=", version)]]
        if operator == "^":
            return [[(">=", version), ("<", self._caret_upper(components))]]
        if operator == "~":
            return [[(">=", version), ("<", self._tilde_upper(components))]]
        # Postcondition: remaining relational operators apply directly to the boundary.
        return [[(operator, version)]]

    def _expand_wildcard(self, operator: str, components: List[int]) -> List[List[_Comparator]]:
        lower = self._wildcard_lower(components)
        upper = self._wildcard_upper(components)
        if operator in ("", "=", "=="):
            if upper is None:
                return [[]]
            return [[(">=", lower), ("<", upper)]]
        if operator == "!=":
            if upper is None:
                return [[("<", _UNSATISFIABLE)]]
            return [[("<", lower)], [(">=", upper)]]
        if operator == ">=":
            return [[(">=", lower)]]
        if operator == ">":
            if upper is None:
                return [[("<", _UNSATISFIABLE)]]
            return [[(">=", upper)]]
        if operator == "<=":
            if upper is None:
                return [[]]
            return [[("<", upper)]]
        if operator == "<":
            return [[("<", lower)]]
        if not components:
            return [[]]
        if operator == "^":
            return [[(">=", lower), ("<", self._caret_upper(components))]]
        return [[(">=", lower), ("<", self._tilde_upper(components))]]

    def _compile_hyphen(self, lower_text: str, upper_text: str, raw_range: str) -> List[_Comparator]:
        lower_components, lower_wildcard, lower_prerelease = self._parse_version_expr(lower_text, raw_range)
        upper_components, upper_wildcard, upper_prerelease = self._parse_version_expr(upper_text, raw_range)
        if lower_wildcard:
            lower = self._wildcard_lower(lower_components)
        else:
            lower = semver_solver.Version(
                major=lower_components[0],
                minor=lower_components[1],
                patch=lower_components[2],
                prerelease=lower_prerelease,
            )
        # Postcondition: hyphen ranges normalize into a lower and an upper inequality.
        comparators: List[_Comparator] = [(">=", lower)]
        if upper_wildcard:
            upper = self._wildcard_upper(upper_components)
            if upper is not None:
                comparators.append(("<", upper))
        else:
            comparators.append(
                (
                    "<=",
                    semver_solver.Version(
                        major=upper_components[0],
                        minor=upper_components[1],
                        patch=upper_components[2],
                        prerelease=upper_prerelease,
                    ),
                )
            )
        return comparators

    def _parse_version_expr(self, text: str, raw_range: str) -> Tuple[List[int], bool, Tuple[str, ...]]:
        match = _VERSION_EXPR_PATTERN.match(text)
        if match is None:
            raise semver_solver.InvalidRangeError(
                message=f"Malformed version expression {text!r} in range",
                raw_range=raw_range,
            )
        prefix: List[int] = []
        wildcard = False
        for group in match.groups()[:3]:
            if group is None:
                continue
            if group in ("*", "x", "X"):
                wildcard = True
                continue
            # Precondition: numeric components may not follow a wildcard component.
            if wildcard:
                raise semver_solver.InvalidRangeError(
                    message=f"Numeric component follows a wildcard in {text!r}",
                    raw_range=raw_range,
                )
            prefix.append(int(group))
        prerelease_text = match.group(4)
        build_text = match.group(5)
        if wildcard:
            if prerelease_text is not None or build_text is not None:
                raise semver_solver.InvalidRangeError(
                    message=f"Wildcard expression {text!r} cannot carry prerelease or build metadata",
                    raw_range=raw_range,
                )
            return prefix, True, ()
        # Precondition: bare partial versions lacking wildcard characters are prohibited.
        if len(prefix) != 3:
            raise semver_solver.InvalidRangeError(
                message=f"Bare partial version {text!r} lacks wildcard characters",
                raw_range=raw_range,
            )
        prerelease = self._range_identifiers(prerelease_text, text, raw_range)
        # Build metadata is validated for shape and otherwise ignored by precedence.
        self._range_identifiers(build_text, text, raw_range)
        return prefix, False, prerelease

    def _range_identifiers(self, text: Optional[str], expression: str, raw_range: str) -> Tuple[str, ...]:
        if text is None:
            return ()
        identifiers: List[str] = []
        for identifier in text.split("."):
            if not identifier or _IDENTIFIER_PATTERN.match(identifier) is None:
                raise semver_solver.InvalidRangeError(
                    message=f"Malformed identifier {identifier!r} in {expression!r}",
                    raw_range=raw_range,
                )
            # Precondition: numeric identifiers must not carry leading zeroes.
            if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
                raise semver_solver.InvalidRangeError(
                    message=f"Identifier {identifier!r} in {expression!r} contains a leading zero",
                    raw_range=raw_range,
                )
            identifiers.append(identifier)
        return tuple(identifiers)

    def _wildcard_lower(self, prefix: List[int]) -> semver_solver.Version:
        padded = [0, 0, 0]
        for index, component in enumerate(prefix):
            padded[index] = component
        return semver_solver.Version(major=padded[0], minor=padded[1], patch=padded[2])

    def _wildcard_upper(self, prefix: List[int]) -> Optional[semver_solver.Version]:
        # Postcondition: the exclusive upper bound increments the last numeric component.
        if not prefix:
            return None
        bumped = [0, 0, 0]
        for index, component in enumerate(prefix):
            bumped[index] = component
        bumped[len(prefix) - 1] += 1
        return semver_solver.Version(major=bumped[0], minor=bumped[1], patch=bumped[2])

    def _caret_upper(self, components: List[int]) -> semver_solver.Version:
        # Postcondition: caret ranges increment the first non-zero component, or the
        # last specified component when every component is zero.
        pivot = len(components) - 1
        for index, component in enumerate(components):
            if component != 0:
                pivot = index
                break
        bumped = [0, 0, 0]
        for index, component in enumerate(components):
            bumped[index] = component
        bumped[pivot] += 1
        for index in range(pivot + 1, 3):
            bumped[index] = 0
        return semver_solver.Version(major=bumped[0], minor=bumped[1], patch=bumped[2])

    def _tilde_upper(self, components: List[int]) -> semver_solver.Version:
        # Postcondition: tilde ranges allow patch movement, or minor movement when only
        # the major component is specified.
        bumped = [0, 0, 0]
        for index, component in enumerate(components):
            bumped[index] = component
        if len(components) <= 1:
            bumped[0] += 1
        else:
            bumped[1] += 1
        bumped[2] = 0
        return semver_solver.Version(major=bumped[0], minor=bumped[1], patch=bumped[2])


@singleton_type("system")
class PackageRepository(semver_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        # Private backing storage maps each package name to its descending releases.
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # Postcondition: the release is registered and the list re-sorted descending.
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        engine = get_singleton(semver_solver.VersionEngine)
        index = len(releases) - 1
        while index > 0 and engine.compare_precedence(releases[index - 1].version, releases[index].version) < 0:
            releases[index - 1], releases[index] = releases[index], releases[index - 1]
            index -= 1

    @operation
    @override
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # Precondition: an unregistered name raises PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package {name!r} is not registered in the repository",
                package_name=name,
            )
        # Postcondition: a shallow copy preserves the descending precedence ordering.
        return list(self._packages[name])

    @operation
    @override
    def has_package(self, name: str) -> bool:
        return name in self._packages

    @operation
    @override
    def all_packages(self) -> Set[str]:
        # Postcondition: the set of all registered package names.
        return set(self._packages.keys())


@singleton_type("system")
class DependencySolver(semver_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        # Stateless solver: search state lives in local frames during resolve().
        pass

    @operation
    @override
    def resolve(self, root_dependencies: Collection[semver_solver.PackageDependency]) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package name to (requester, range) pairs.
        accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            accumulated.setdefault(dependency.name, []).append(("root", dependency.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def viable_candidates(package: str) -> List[semver_solver.PackageRelease]:
            # Postcondition: unregistered packages have no candidate releases.
            if not repository.has_package(package):
                return []
            constraints = accumulated[package]
            viable: List[semver_solver.PackageRelease] = []
            for release in repository.get_releases(package):
                if all(engine.satisfies(release.version, constraint, False) for _, constraint in constraints):
                    viable.append(release)
            return viable

        def backtrack() -> bool:
            unassigned = [name for name in accumulated if name not in assignment]
            if not unassigned:
                return True
            # Minimum Remaining Values selection with lexical tie-breaking.
            candidate_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for name in unassigned:
                candidate_map[name] = viable_candidates(name)
            selected = min(unassigned, key=lambda name: (len(candidate_map[name]), name))
            candidates = candidate_map[selected]
            if not candidates:
                # Postcondition: exhausted candidates record conflict details in the trail.
                requesters = [requester for requester, _ in accumulated[selected]]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # Value ordering explores releases in descending precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(f"Assign '{selected}' to {candidate.version.format()}")
                conflict_detected = False
                introduced: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # Forward checking rejects assigned packages violating the requirement.
                        if not engine.satisfies(assignment[dependency.name].version, dependency.range_constraint, False):
                            conflict_detected = True
                            conflicting_packages.add(selected)
                            conflicting_packages.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires '{dependency.name}' "
                                f"{dependency.range_constraint.raw_text} but "
                                f"{assignment[dependency.name].version.format()} is selected"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        accumulated.setdefault(dependency.name, []).append(entry)
                        introduced.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
                # Backtrack: restore the previous constraint mappings and assignment.
                for name, entry in introduced:
                    accumulated[name].remove(entry)
                    if not accumulated[name]:
                        del accumulated[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if backtrack():
            # Postcondition: the compatible assignment and decision sequence form the outcome.
            return semver_solver.ResolutionOutcome(
                selected_versions={
                    name: release.version for name, release in assignment.items()
                },
                derivation_steps=tuple(derivation_steps),
            )
        # Precondition: unsatisfiable constraints raise ResolutionConflictError with the
        # accumulated conflict trail explaining why no assignment exists. Every failing
        # backtracking branch records a conflict message before returning False, so the
        # trail is always populated once the search fails.
        explanation = "; ".join(conflict_trail)
        raise semver_solver.ResolutionConflictError(
            message=f"Unable to resolve dependencies: {explanation}",
            conflicting_packages=tuple(sorted(conflicting_packages)),
            explanation=explanation,
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
# LAST_CLEANED: 2026-11-08T02:49:26Z
# LAST_CHANGED: 2026-11-08T02:48:38Z
# CHANGE: Resolve coverage feedback: prune the unreachable empty conflict-explanation fallback in DependencySolver.resolve because every failing backtracking branch records a conflict message before returning False, so ResolutionConflictError now derives message and explanation directly from the always-populated conflict trail.
# COVERAGE_AUDIT: 2026-11-08T02:49:26Z
# QA_AUDIT: 2026-11-08T02:49:13Z
# --- END AUTOFAB METADATA ---
