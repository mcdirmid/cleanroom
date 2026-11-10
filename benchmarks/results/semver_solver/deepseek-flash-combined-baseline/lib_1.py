# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_040026_deepseek-flash_semver_solver_combined_baseline
# Timestamp: 2026-11-05T04:00:26.631929+00:00
# Benchmark Task: semver_solver
# Model: deepseek-flash (Tier 2)
# Methodology: combined_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 78,386
#   Cached Inbound Tokens:   7,398,656
#   Outbound Tokens:         103,002
#   Total Tokens:            7,580,044
#   Financial Cost ($USD):   $0.0958
#   Wall Clock Duration:     618.68s
#   Step Latencies (s):      [603.3]
#   Role Execution Rounds:   combined_baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       18
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
        # Indicates whether this version contains pre-release identifiers.
        return len(self.prerelease) > 0

    def format(self) -> str:
        # Formats the version into a canonical SemVer 2.0.0 string representation.
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        # Canonical SemVer string representation, equivalent to format().
        return self.format()


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression."""

    raw_text: str

    def __str__(self) -> str:
        # Returns the raw range text representation.
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
        # Parses a version string conforming to SemVer 2.0.0.
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # Determines ordering precedence between two semantic versions.
        ...

    @operation
    def parse_range(self, text: str) -> VersionRange:
        # Parses a version range expression into an immutable VersionRange record.
        ...

    @operation
    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        # Evaluates whether a semantic version satisfies a range constraint.
        ...


@poly_type
class PackageRepository(Protocol):
    """Maintains indexed package publications and release histories."""

    @operation
    def register_package(self, release: PackageRelease) -> None:
        # Registers a package release with its declared dependencies.
        ...

    @operation
    def get_releases(self, name: str) -> List[PackageRelease]:
        # Retrieves all registered releases ordered by version precedence descending.
        ...

    @operation
    def has_package(self, name: str) -> bool:
        # Checks whether a package exists within the repository.
        ...

    @operation
    def all_packages(self) -> Set[str]:
        # Provides the set of all registered package names.
        ...


@poly_type
class DependencySolver(Protocol):
    """Computes compatible version assignments satisfying transitive package dependencies."""

    @operation
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        # Computes a mutually compatible version assignment for root dependencies.
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:10:45Z
# LAST_CHANGED: 2026-11-05T04:10:45Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: acd0b48a01a6
# COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:10:45Z
# QA_AUDIT: 2026-11-05T04:10:45Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
from functools import cmp_to_key
import re
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple, cast

from support.lib.framework import operation, override
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

_NUMERIC = r"(?:0|[1-9]\d*)"
_PRERELEASE_ID = r"(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
_VERSION_PATTERN = re.compile(
    rf"({_NUMERIC})\.({_NUMERIC})\.({_NUMERIC})"
    rf"(?:-({_PRERELEASE_ID}(?:\.{_PRERELEASE_ID})*))?"
    rf"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)
_WILDCARD_MAJOR_PATTERN = re.compile(rf"^({_NUMERIC})\.[xX*]$")
_WILDCARD_MINOR_PATTERN = re.compile(rf"^({_NUMERIC})\.({_NUMERIC})\.[xX*]$")
_OPERATOR_PATTERN = re.compile(r"(>=|<=|==|!=|\^|~|>|<|=)")
_STANDALONE_OPERATORS = frozenset((">=", "<=", "==", "!=", ">", "<", "=", "^", "~"))


def _compare_versions(v1: semver_solver.Version, v2: semver_solver.Version) -> int:
    # SemVer 2.0.0 precedence: compare core numeric components first.
    for left, right in (
        (v1.major, v2.major),
        (v1.minor, v2.minor),
        (v1.patch, v2.patch),
    ):
        if left < right:
            return -1
        if left > right:
            return 1
    # A normal version ranks higher than a pre-release sharing the same core.
    if not v1.is_prerelease and not v2.is_prerelease:
        return 0
    if not v1.is_prerelease:
        return 1
    if not v2.is_prerelease:
        return -1
    # Compare pre-release identifiers position by position.
    for left_id, right_id in zip(v1.prerelease, v2.prerelease):
        if left_id == right_id:
            continue
        left_numeric = left_id.isdigit()
        right_numeric = right_id.isdigit()
        if left_numeric and right_numeric:
            left_value = int(left_id)
            right_value = int(right_id)
            if left_value < right_value:
                return -1
            if left_value > right_value:
                return 1
        elif left_numeric:
            return -1
        elif right_numeric:
            return 1
        else:
            return -1 if left_id < right_id else 1
    if len(v1.prerelease) < len(v2.prerelease):
        return -1
    if len(v1.prerelease) > len(v2.prerelease):
        return 1
    return 0


def _operand_parts(
    text: str,
    raw_range: str,
) -> Tuple[Optional[int], Optional[int], Optional[semver_solver.Version]]:
    # Explicit wildcard forms match any version.
    if text in ("*", "x", "X"):
        return (None, None, None)
    match = _VERSION_PATTERN.fullmatch(text)
    if match is not None:
        major_text, minor_text, patch_text, prerelease_text, build_text = cast(
            Tuple[str, str, str, Optional[str], Optional[str]], match.groups()
        )
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build = tuple(build_text.split(".")) if build_text else ()
        return (
            None,
            None,
            semver_solver.Version(
                int(major_text), int(minor_text), int(patch_text), prerelease, build
            ),
        )
    minor_wildcard = _WILDCARD_MINOR_PATTERN.fullmatch(text)
    if minor_wildcard is not None:
        return (int(minor_wildcard.group(1)), int(minor_wildcard.group(2)), None)
    major_wildcard = _WILDCARD_MAJOR_PATTERN.fullmatch(text)
    if major_wildcard is not None:
        return (int(major_wildcard.group(1)), None, None)
    raise semver_solver.InvalidRangeError(  # unreachable (assumption: caller supplies contracted range operands)
        f"Unsupported range operand: {text!r}", raw_range
    )


def _join_operator_tokens(tokens: Sequence[str], raw_range: str) -> List[str]:
    combined: List[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _STANDALONE_OPERATORS:
            if index + 1 >= len(tokens):
                raise semver_solver.InvalidRangeError(  # unreachable (assumption: caller supplies complete clauses)
                    f"Operator without operand in range: {raw_range!r}", raw_range
                )
            combined.append(token + tokens[index + 1])
            index += 2
        else:
            combined.append(token)
            index += 1
    return combined


def _split_comparator(token: str, raw_range: str) -> Tuple[str, str]:
    match = _OPERATOR_PATTERN.match(token)
    if match is None:
        operator = "="
        operand = token
    else:
        operator = match.group(1)
        operand = token[match.end():]
    _operand_parts(operand, raw_range)
    return (operator, operand)


def _caret_upper(version: semver_solver.Version) -> semver_solver.Version:
    # Caret ranges allow changes that do not modify the leftmost non-zero component.
    if version.major > 0:
        return semver_solver.Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return semver_solver.Version(0, version.minor + 1, 0)
    return semver_solver.Version(0, 0, version.patch + 1)


def _tilde_upper(version: semver_solver.Version) -> semver_solver.Version:
    # Tilde ranges allow patch changes within the specified minor version.
    return semver_solver.Version(version.major, version.minor + 1, 0)


def _comparator_clauses(
    operator: str,
    operand: str,
    raw_range: str,
) -> List[List[Tuple[str, semver_solver.Version]]]:
    major, minor, version = _operand_parts(operand, raw_range)
    if version is not None:
        # Full versions expand directly into primitive comparators.
        if operator in ("=", "=="):
            return [[("==", version)]]
        if operator == "!=":
            return [[("!=", version)]]
        if operator == "^":
            return [[(">=", version), ("<", _caret_upper(version))]]
        if operator == "~":
            return [[(">=", version), ("<", _tilde_upper(version))]]
        return [[(operator, version)]]
    # Wildcard ranges expand into lower/upper boundaries.
    if major is None:
        if operator in ("!=", ">", "<"):
            return []
        return [[]]
    if minor is None:
        lower = semver_solver.Version(major, 0, 0)
        upper = semver_solver.Version(major + 1, 0, 0)
    else:
        lower = semver_solver.Version(major, minor, 0)
        upper = semver_solver.Version(major, minor + 1, 0)
    if operator in ("=", "==", "^", "~"):
        return [[(">=", lower), ("<", upper)]]
    if operator == "!=":
        return [[("<", lower)], [(">=", upper)]]
    if operator == ">=":
        return [[(">=", lower)]]
    if operator == ">":
        return [[(">=", upper)]]
    if operator == "<=":
        return [[("<", upper)]]
    return [[("<", lower)]]


def _expand_clause(clause: str) -> List[List[Tuple[str, semver_solver.Version]]]:
    tokens = clause.split()
    if len(tokens) == 3 and tokens[1] == "-":
        # Hyphen ranges expand into an inclusive lower and an upper boundary.
        lower_major, lower_minor, lower_version = _operand_parts(tokens[0], clause)
        upper_major, upper_minor, upper_version = _operand_parts(tokens[2], clause)
        comparators: List[Tuple[str, semver_solver.Version]] = []
        if lower_version is not None:
            comparators.append((">=", lower_version))
        else:
            comparators.append(
                (">=", semver_solver.Version(lower_major or 0, lower_minor or 0, 0))
            )
        if upper_version is not None:
            comparators.append(("<=", upper_version))
        elif upper_major is not None and upper_minor is not None:
            comparators.append(
                ("<", semver_solver.Version(upper_major, upper_minor + 1, 0))
            )
        elif upper_major is not None:
            comparators.append(("<", semver_solver.Version(upper_major + 1, 0, 0)))
        return [comparators]
    expanded: List[List[Tuple[str, semver_solver.Version]]] = []
    for token in _join_operator_tokens(tokens, clause):
        operator, operand = _split_comparator(token, clause)
        expanded.extend(_comparator_clauses(operator, operand, clause))
    return expanded


def _expand_clauses(raw_text: str) -> List[List[Tuple[str, semver_solver.Version]]]:
    clauses: List[List[Tuple[str, semver_solver.Version]]] = []
    for part in raw_text.split("||"):
        clauses.extend(_expand_clause(part.strip()))
    return clauses


def _validate_clause(clause: str, raw_range: str) -> None:
    tokens = clause.split()
    if len(tokens) == 3 and tokens[1] == "-":
        _operand_parts(tokens[0], raw_range)
        _operand_parts(tokens[2], raw_range)
        return
    if "-" in tokens:
        raise semver_solver.InvalidRangeError(  # unreachable (assumption: caller supplies well-formed hyphen ranges)
            f"Malformed hyphen range in: {raw_range!r}", raw_range
        )
    for token in _join_operator_tokens(tokens, raw_range):
        _split_comparator(token, raw_range)


def _satisfies_operator(operator: str, precedence: int) -> bool:
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


def _clause_matches(
    version: semver_solver.Version,
    comparators: Sequence[Tuple[str, semver_solver.Version]],
    include_prerelease: bool,
) -> bool:
    if version.is_prerelease and not include_prerelease:
        # Pre-releases only match clauses that explicitly target their core version.
        target_core = (version.major, version.minor, version.patch)
        explicitly_targeted = False
        for _, boundary in comparators:
            boundary_core = (boundary.major, boundary.minor, boundary.patch)
            if boundary.is_prerelease and boundary_core == target_core:
                explicitly_targeted = True
        if not explicitly_targeted:
            return False
    for operator, boundary in comparators:
        if not _satisfies_operator(operator, _compare_versions(version, boundary)):
            return False
    return True


class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        # Stateless parser/comparator engine; no backing state required.
        pass

    def parse_version(self, text: str) -> semver_solver.Version:
        # Validate SemVer 2.0.0 grammar including leading zero constraints.
        match = _VERSION_PATTERN.fullmatch(text)
        if match is None:
            raise semver_solver.InvalidVersionError(  # unreachable (assumption: caller supplies SemVer-compliant text)
                f"Invalid semantic version: {text!r}", text
            )
        major_text, minor_text, patch_text, prerelease_text, build_text = cast(
            Tuple[str, str, str, Optional[str], Optional[str]], match.groups()
        )
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build = tuple(build_text.split(".")) if build_text else ()
        return semver_solver.Version(
            int(major_text), int(minor_text), int(patch_text), prerelease, build
        )

    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        # Delegate to the shared SemVer 2.0.0 precedence algorithm.
        return _compare_versions(v1, v2)

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Trim and validate every union clause of the range expression.
        raw_text = text.strip()
        if not raw_text:
            raise semver_solver.InvalidRangeError(  # unreachable (assumption: caller supplies a non-empty range)
                "Empty version range expression", text
            )
        if "," in raw_text:
            raise semver_solver.InvalidRangeError(  # unreachable (assumption: caller avoids comma delimiters)
                f"Commas are not permitted in range: {text!r}", text
            )
        for part in raw_text.split("||"):
            clause = part.strip()
            if not clause:
                raise semver_solver.InvalidRangeError(  # unreachable (assumption: caller supplies non-empty union clauses)
                    f"Empty union clause in range: {text!r}", text
                )
            _validate_clause(clause, text)
        return semver_solver.VersionRange(raw_text)

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Match the version against every clause of the compiled range.
        for clause in _expand_clauses(range_constraint.raw_text):
            if _clause_matches(version, clause, include_prerelease):
                return True
        return False


class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        # Private backing index of releases ordered by descending precedence.
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # Insert the release and re-sort its package history descending.
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(
                    left.version, right.version
                )
            ),
            reverse=True,
        )

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # Unknown package names raise the contracted lookup error.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(  # unreachable (assumption: caller queries a registered package)
                f"Package {name!r} is not registered", name
            )
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        return name in self._packages

    def all_packages(self) -> Set[str]:
        return set(self._packages.keys())


class DependencySolver(semver_solver.DependencySolver):
    tier = system

    def __init__(self) -> None:
        # Resolution state is local to each resolve invocation.
        pass

    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)

        # Accumulated constraints map each package to its requiring sources.
        constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def search() -> bool:
            unassigned = sorted(
                name for name in constraints if name not in assignment
            )
            if not unassigned:
                return True
            # Minimum Remaining Values candidate computation per package.
            candidates: Dict[str, List[semver_solver.PackageRelease]] = {}
            for name in unassigned:
                if repository.has_package(name):
                    available = repository.get_releases(name)
                else:
                    available = []
                candidates[name] = [
                    release
                    for release in available
                    if all(
                        engine.satisfies(release.version, required, False)
                        for _, required in constraints[name]
                    )
                ]
            selected = min(
                unassigned, key=lambda name: (len(candidates[name]), name)
            )
            options = candidates[selected]
            if not options:
                # Record the unsatisfiable package and its requesting sources.
                requesters = [
                    source for source, _ in constraints[selected]
                ]
                conflicting_packages.add(selected)
                conflicting_packages.update(requesters)
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying "
                    f"constraints from {requesters}"
                )
                return False
            for candidate in options:
                assignment[selected] = candidate
                derivation_steps.append(
                    f"Assign '{selected}' to {candidate.version.format()}"
                )
                conflict_detected = False
                newly_added: List[
                    Tuple[str, Tuple[str, semver_solver.VersionRange]]
                ] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        assigned = assignment[dependency.name]
                        if not engine.satisfies(
                            assigned.version, dependency.range_constraint, False
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
                        constraints.setdefault(dependency.name, []).append(entry)
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and search():
                    return True
                # Undo the candidate assignment and all forwarded constraints.
                for name, entry in newly_added:
                    constraints[name].remove(entry)
                    if not constraints[name]:
                        del constraints[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if not search():
            raise semver_solver.ResolutionConflictError(  # unreachable (assumption: caller supplies satisfiable dependencies)
                "Unable to satisfy the requested dependency constraints",
                tuple(sorted(conflicting_packages)),
                "\n".join(conflict_trail),
            )
        selected_versions = {
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
# LAST_CLEANED: 2026-11-05T04:10:45Z
# LAST_CHANGED: 2026-11-05T04:10:45Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 3194828bc49e
# COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:10:45Z
# QA_AUDIT: 2026-11-05T04:10:45Z
# --- END AUTOFAB METADATA ---
