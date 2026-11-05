# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_164824_deepseek-flash_semver_solver_multi_pretense_baseline
# Timestamp: 2026-11-05T16:48:24.864471+00:00
# Benchmark Task: semver_solver_multi
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 91,075
#   Cached Inbound Tokens:   9,237,376
#   Outbound Tokens:         110,503
#   Total Tokens:            9,438,954
#   Financial Cost ($USD):   $0.1077
#   Wall Clock Duration:     686.42s
#   Step Latencies (s):      [662.6]
#   Role Execution Rounds:   pretense_baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       6
#   Unit Tests Failed:       0
#   Line Coverage:           99.0%
#   Branch Coverage:         99.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dependency_solver.py ===
"""Package repository and dependency resolution interface specifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, List, Mapping, Protocol, Set, Tuple

from support.lib.framework import data_type, operation, poly_type

from . import semver_core
from . import semver_range


@dataclass
class PackageNotFoundError(semver_core.SemVerError):
    """Raised when a referenced package name does not exist in the repository.

    Args:
        message: Diagnostic description of the missing package.
        package_name: Name of the missing package.
    """

    package_name: str


@dataclass
class ResolutionConflictError(semver_core.SemVerError):
    """Raised when dependency constraints cannot be satisfied mutually.

    Args:
        message: Diagnostic description of the conflict.
        conflicting_packages: Sequence of package names involved in the conflict.
        explanation: Detailed diagnostic derivation of the unsatisfiable conflict.
    """

    conflicting_packages: Tuple[str, ...]
    explanation: str


@data_type
@dataclass(frozen=True)
class PackageDependency:
    """Requirement specification on an external package and version range.

    Args:
        name: Name of the required package.
        range_constraint: Acceptable version range constraint.
    """

    name: str
    range_constraint: semver_range.VersionRange


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
    version: semver_core.Version
    dependencies: Tuple[PackageDependency, ...] = ()


@data_type
@dataclass(frozen=True)
class ResolutionOutcome:
    """Outcome report of a successful dependency resolution run.

    Args:
        selected_versions: Mapping of package names to their selected semantic versions.
        derivation_steps: Ordered sequence of decision and deduction steps.
    """

    selected_versions: Mapping[str, semver_core.Version]
    derivation_steps: Tuple[str, ...]


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

        PRECONDITIONS:
        - WHEN name is not registered, MUST raise PackageNotFoundError.

        POSTCONDITIONS:
        - MUST yield all registered releases for package name ordered by version precedence descending.
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
            root_dependencies: Initial collection of package requirements.

        Returns:
            A ResolutionOutcome containing the selected versions and derivation steps.

        Raises:
            ResolutionConflictError: If dependencies cannot be satisfied mutually or reference missing packages.

        PRECONDITIONS:
        - WHEN dependency constraints are unsatisfiable, MUST raise ResolutionConflictError identifying conflicting packages.
        - WHEN a dependency references a package absent from the repository, MUST raise ResolutionConflictError without allowing PackageNotFoundError to escape.

        POSTCONDITIONS:
        - MUST compute a mutually compatible version assignment satisfying all transitive package dependencies.
        - MUST select the highest precedence compatible release for each required package.
        - MUST produce a ResolutionOutcome containing the selected version mapping and derivation steps.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: cc68f61c7ce8
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_impl.py ===
"""Package repository and dependency resolution implementation."""

from __future__ import annotations

from functools import cmp_to_key
from typing import Collection, Dict, List, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)

from . import dependency_solver
from . import semver_core
from . import semver_range


@singleton_type("system")
class PackageRepository(dependency_solver.PackageRepository):
    """Concrete realization of package release storage and indexing."""

    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[dependency_solver.PackageRelease]] = {}

    @operation
    @override
    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        # Inserts the release and re-sorts the bucket in descending precedence order.
        bucket = self._packages.setdefault(release.name, [])
        bucket.append(release)
        engine = get_singleton(semver_core.VersionEngine)
        bucket.sort(
            key=cmp_to_key(
                lambda left, right: engine.compare_precedence(
                    left.version, right.version
                )
            ),
            reverse=True,
        )

    @operation
    @override
    def get_releases(self, name: str) -> List[dependency_solver.PackageRelease]:
        # Raises PackageNotFoundError when the package is absent from the repository.
        if name not in self._packages:
            raise dependency_solver.PackageNotFoundError(
                f"Package '{name}' is not registered", name
            )
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
class DependencySolver(dependency_solver.DependencySolver):
    """Concrete realization of backtracking package dependency solver."""

    tier = system

    def __init__(self) -> None:
        self._repository: Optional[dependency_solver.PackageRepository] = None

    @operation
    @override
    def resolve(
        self,
        root_dependencies: Collection[dependency_solver.PackageDependency],
    ) -> dependency_solver.ResolutionOutcome:
        repository = get_singleton(dependency_solver.PackageRepository)
        range_engine = get_singleton(semver_range.RangeEngine)
        constraints: Dict[
            str, List[Tuple[str, semver_range.VersionRange]]
        ] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                ("root", dependency.range_constraint)
            )
        assignment: Dict[str, dependency_solver.PackageRelease] = {}
        derivation_steps: List[str] = []
        conflict_trail: List[str] = []
        conflicting: Set[str] = set()

        def candidates_for(
            name: str,
        ) -> List[dependency_solver.PackageRelease]:
            # Missing packages evaluate to zero candidates rather than escaping.
            try:
                releases = repository.get_releases(name)
            except dependency_solver.PackageNotFoundError:
                return []
            return [
                release
                for release in releases
                if all(
                    range_engine.satisfies(release.version, constraint, False)
                    for _, constraint in constraints[name]
                )
            ]

        def backtrack() -> bool:
            # Minimum remaining values variable selection with lexical tie-breaking.
            unassigned = [
                name for name in constraints if name not in assignment
            ]
            if not unassigned:
                return True
            candidates_by_package: Dict[
                str, List[dependency_solver.PackageRelease]
            ] = {name: candidates_for(name) for name in unassigned}
            selected = min(
                unassigned,
                key=lambda name: (len(candidates_by_package[name]), name),
            )
            candidates = candidates_by_package[selected]
            if not candidates:
                requesters = [
                    source for source, _ in constraints[selected]
                ]
                conflicting.add(selected)
                conflicting.update(
                    source for source in requesters if source != "root"
                )
                conflict_trail.append(
                    f"No viable releases for '{selected}' satisfying constraints from {requesters}"
                )
                return False
            # Value ordering: explore candidates in descending precedence order.
            for candidate in candidates:
                assignment[selected] = candidate
                derivation_steps.append(
                    f"Assign '{selected}' to {candidate.version}"
                )
                conflict_detected = False
                newly_added: List[
                    Tuple[str, Tuple[str, semver_range.VersionRange]]
                ] = []
                for dependency in candidate.dependencies:
                    if dependency.name in assignment:
                        # Forward checking against already assigned versions.
                        if not range_engine.satisfies(
                            assignment[dependency.name].version,
                            dependency.range_constraint,
                            False,
                        ):
                            conflict_detected = True
                            conflicting.add(selected)
                            conflicting.add(dependency.name)
                            conflict_trail.append(
                                f"Conflict: '{selected}' requires {dependency.name} {dependency.range_constraint.raw_text}"
                            )
                            break
                    else:
                        entry = (selected, dependency.range_constraint)
                        constraints.setdefault(dependency.name, []).append(
                            entry
                        )
                        newly_added.append((dependency.name, entry))
                if not conflict_detected and backtrack():
                    return True
                # Undo the decision and its newly introduced constraints.
                for name, entry in newly_added:
                    constraints[name].remove(entry)
                    if not constraints[name]:
                        del constraints[name]
                del assignment[selected]
                derivation_steps.pop()
            return False

        if backtrack():
            return dependency_solver.ResolutionOutcome(
                selected_versions={
                    name: release.version
                    for name, release in assignment.items()
                },
                derivation_steps=tuple(derivation_steps),
            )
        explanation = "; ".join(conflict_trail)
        raise dependency_solver.ResolutionConflictError(
            explanation,
            tuple(sorted(conflicting)),
            explanation,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, dependency_solver.PackageRepository],
        tier=system,
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, dependency_solver.DependencySolver],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 89a16fe3f18b
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---


# === File: semver_core.py ===
"""SemVer 2.0.0 parsing and precedence comparison interface specifications."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Protocol, Tuple

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
            text = f"{text}-{'.'.join(self.prerelease)}"
        if self.build:
            text = f"{text}+{'.'.join(self.build)}"
        return text

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
        return self.format()


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing and precedence comparison."""

    @operation
    def parse_version(self, text: str) -> Version:
        """Parses a version string conforming to SemVer 2.0.0.

        Args:
            text: Raw version string to parse.

        Returns:
            The parsed immutable Version record.

        Raises:
            InvalidVersionError: If text violates SemVer 2.0.0 grammar or contains leading zeroes.

        PRECONDITIONS:
        - WHEN text contains leading zeroes in numeric identifiers or violates grammar, MUST raise InvalidVersionError.

        POSTCONDITIONS:
        - MUST parse valid SemVer 2.0.0 strings into Version records with major, minor, patch, prerelease, and build tuples.
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 3ecbceefeb71
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl.py ===
"""SemVer 2.0.0 parsing and precedence comparison implementation."""

from __future__ import annotations

import re
from typing import Optional, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)

from . import semver_core


_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine."""

    tier = system

    def __init__(self) -> None:
        self._pattern = _SEMVER_PATTERN

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        # SemVer 2.0.0 grammar: rejects malformed text and leading zeroes in numeric identifiers.
        match = self._pattern.fullmatch(text)
        if match is None:
            raise semver_core.InvalidVersionError(
                f"Invalid semantic version: {text!r}", text
            )
        prerelease: Tuple[str, ...] = ()
        if match.group("prerelease") is not None:
            prerelease = tuple(match.group("prerelease").split("."))
        build: Tuple[str, ...] = ()
        if match.group("build") is not None:
            build = tuple(match.group("build").split("."))
        # Produces an immutable semver_core.Version record.
        return semver_core.Version(
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
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        # Compare major, minor, and patch numerically in sequence.
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1
        p1 = v1.prerelease
        p2 = v2.prerelease
        # Rank normal versions higher than prerelease versions.
        if not p1 and not p2:
            return 0
        if not p1:
            return 1
        if not p2:
            return -1
        # Iterate through pre-release segments comparing each position.
        for first, second in zip(p1, p2):
            if first == second:
                continue
            first_numeric = first.isdigit()
            second_numeric = second.isdigit()
            if first_numeric and second_numeric:
                return -1 if int(first) < int(second) else 1
            if first_numeric:
                return -1
            if second_numeric:
                return 1
            return -1 if first < second else 1
        # Rank longer pre-release segment sequences higher when common prefix segments match.
        if len(p1) == len(p2):
            return 0
        return -1 if len(p1) < len(p2) else 1


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_core.VersionEngine],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: a003ffe9f16b
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---


# === File: semver_range.py ===
"""Version range parsing and satisfaction interface specifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from support.lib.framework import data_type, operation, poly_type

from . import semver_core


@dataclass
class InvalidRangeError(semver_core.SemVerError):
    """Raised when a version range expression contains malformed syntax.

    Args:
        message: Diagnostic description of the error.
        raw_range: Original malformed range expression string.
    """

    raw_range: str


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


@poly_type
class RangeEngine(Protocol):
    """Provides version range parsing and constraint matching."""

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record.

        Args:
            text: Raw range expression text.

        Returns:
            The parsed VersionRange.

        Raises:
            InvalidRangeError: If text contains malformed range syntax.

        PRECONDITIONS:
        - WHEN text supplies bare partial versions lacking wildcard characters across any comparator or hyphen expression (such as '1', '1.2', '^0.0', or '1.2 - 2.3'), MUST raise InvalidRangeError.
        - WHEN text is empty, contains only whitespace, contains empty union clauses, uses comma delimiters, or violates range syntax, MUST raise InvalidRangeError.

        POSTCONDITIONS:
        - MUST parse range expression text supporting basic comparators (==, =, !=, <, <=, >, >=), caret ranges (^), tilde ranges (~), wildcards (*, x, X, M.x, M.*, M.m.x, M.m.*), hyphen ranges (M1.m1.p1 - M2.m2.p2), and unions (||).
        - MUST trim surrounding whitespace around range expressions and individual clauses, storing the trimmed range expression in raw_text.
        - MUST accept optional whitespace between relational/prefix operators and target versions or wildcards (e.g. '>= 1.0.0' is equivalent to '>=1.0.0').
        - MUST delimit comparators within clauses strictly by whitespace; commas are not permitted.
        """
        ...

    @operation
    def satisfies(
        self,
        version: semver_core.Version,
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: bf5c5f4611f8
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl.py ===
"""Version range parsing and constraint satisfaction implementation."""

from __future__ import annotations

from typing import List, Optional, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)

from . import semver_core
from . import semver_range


_OPERATORS = (">=", "<=", "==", "!=", ">", "<", "=", "^", "~")
_WILDCARDS = ("*", "x", "X")

_Comparator = Tuple[str, semver_core.Version, Optional[semver_core.Version]]
_Clause = List[_Comparator]


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine."""

    tier = system

    def __init__(self) -> None:
        self._operators = _OPERATORS

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        # Trim surrounding whitespace and store the trimmed expression.
        trimmed = text.strip()
        if not trimmed:
            raise semver_range.InvalidRangeError(
                "Version range must not be empty", text
            )
        self._compile(trimmed, text)
        return semver_range.VersionRange(trimmed)

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        # Compile range expression into disjunctive normal form comparator sets.
        clauses = self._compile(range_constraint.raw_text, range_constraint.raw_text)
        engine = get_singleton(semver_core.VersionEngine)
        # When pre-release versions are excluded, only explicitly targeted pre-releases match.
        if version.is_prerelease and not include_prerelease:
            if not self._targets_prerelease(version, clauses):
                return False
        # A version satisfies the range when all comparators in at least one clause hold.
        for clause in clauses:
            if all(self._evaluate(version, comparator, engine) for comparator in clause):
                return True
        return False

    def _compile(self, trimmed: str, raw: str) -> List[_Clause]:
        clauses: List[_Clause] = []
        for clause_text in trimmed.split("||"):
            clause = clause_text.strip()
            if not clause:
                raise semver_range.InvalidRangeError(
                    "Version range contains an empty clause", raw
                )
            clauses.append(self._compile_clause(clause, raw))
        return clauses

    def _compile_clause(self, clause: str, raw: str) -> _Clause:
        # Comparators are delimited strictly by whitespace; commas are not permitted.
        if "," in clause:
            raise semver_range.InvalidRangeError(
                "Version range comparators must be whitespace-delimited", raw
            )
        tokens = clause.split()
        # Hyphen ranges pair two full versions into lower and upper inequalities.
        if len(tokens) == 3 and tokens[1] == "-":
            return self._compile_hyphen(tokens[0], tokens[2], raw)
        comparators: _Clause = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in self._operators:
                if index + 1 >= len(tokens):
                    raise semver_range.InvalidRangeError(
                        f"Missing version after operator {token!r}", raw
                    )
                operator = token
                target = tokens[index + 1]
                index += 2
            else:
                operator = self._prefix_operator(token)
                if operator is None:
                    operator = "=="
                    target = token
                else:
                    target = token[len(operator):]
                index += 1
            comparators.extend(self._expand(operator, target, raw))
        return comparators

    def _compile_hyphen(self, lower_text: str, upper_text: str, raw: str) -> _Clause:
        lower = self._exact_version(lower_text, raw)
        upper = self._exact_version(upper_text, raw)
        return [(">=", lower, None), ("<=", upper, None)]

    def _prefix_operator(self, token: str) -> Optional[str]:
        for operator in self._operators:
            if token.startswith(operator):
                return operator
        return None

    def _expand(self, operator: str, target: str, raw: str) -> _Clause:
        if operator == "=":
            operator = "=="
        wildcard = self._wildcard_components(target, raw)
        if wildcard is not None:
            major, minor, patch, level = wildcard
            return self._expand_wildcard(operator, major, minor, patch, level, raw)
        version = self._exact_version(target, raw)
        return self._expand_exact(operator, version, raw)

    def _expand_exact(
        self, operator: str, version: semver_core.Version, raw: str
    ) -> _Clause:
        if operator == "^":
            upper = self._caret_upper(
                version.major, version.minor, version.patch, 3
            )
            return [(">=", version, None), ("<", upper, None)]
        if operator == "~":
            upper = self._tilde_upper(
                version.major, version.minor, version.patch, 3
            )
            return [(">=", version, None), ("<", upper, None)]
        # All remaining operators are basic relational comparators.
        return [(operator, version, None)]

    def _expand_wildcard(
        self,
        operator: str,
        major: int,
        minor: int,
        patch: int,
        level: int,
        raw: str,
    ) -> _Clause:
        lower = semver_core.Version(major, minor, patch)
        if operator in ("^", "~"):
            if level == 0:
                return [(">=", semver_core.Version(0, 0, 0), None)]
            if operator == "^":
                upper = self._caret_upper(major, minor, patch, level)
            else:
                upper = self._tilde_upper(major, minor, patch, level)
            return [(">=", lower, None), ("<", upper, None)]
        upper = self._wildcard_upper(major, minor, patch, level)
        if operator == "==":
            comparators: _Clause = [(">=", lower, None)]
            if upper is not None:
                comparators.append(("<", upper, None))
            return comparators
        if operator == "!=":
            return [("not_in", lower, upper)]
        if operator == ">=":
            return [(">=", lower, None)]
        if operator == "<=":
            if upper is None:
                return [(">=", semver_core.Version(0, 0, 0), None)]
            return [("<", upper, None)]
        if operator == ">":
            if upper is None:
                return [("<", semver_core.Version(0, 0, 0), None)]
            return [(">=", upper, None)]
        # The only remaining relational operator is a strict lower bound.
        return [("<", lower, None)]

    def _wildcard_components(
        self, target: str, raw: str
    ) -> Optional[Tuple[int, int, int, int]]:
        parts = target.split(".")
        wildcard_index: Optional[int] = None
        for index, part in enumerate(parts):
            if part in _WILDCARDS:
                wildcard_index = index
                break
        if wildcard_index is None:
            return None
        if wildcard_index > 2:
            raise semver_range.InvalidRangeError(
                f"Invalid wildcard version {target!r}", raw
            )
        numeric = parts[:wildcard_index]
        for part in parts[wildcard_index:]:
            if part not in _WILDCARDS:
                raise semver_range.InvalidRangeError(
                    f"Invalid wildcard version {target!r}", raw
                )
        components = [0, 0, 0]
        for index, part in enumerate(numeric):
            components[index] = self._numeric_component(part, raw)
        return components[0], components[1], components[2], wildcard_index

    def _numeric_component(self, text: str, raw: str) -> int:
        if not text.isdigit():
            raise semver_range.InvalidRangeError(
                f"Invalid numeric component {text!r} in range", raw
            )
        if len(text) > 1 and text.startswith("0"):
            raise semver_range.InvalidRangeError(
                f"Numeric component {text!r} must not have leading zeroes", raw
            )
        return int(text)

    def _exact_version(self, text: str, raw: str) -> semver_core.Version:
        engine = get_singleton(semver_core.VersionEngine)
        try:
            return engine.parse_version(text)
        except semver_core.InvalidVersionError:
            raise semver_range.InvalidRangeError(
                f"Invalid version {text!r} in range", raw
            )

    def _wildcard_upper(
        self, major: int, minor: int, patch: int, level: int
    ) -> Optional[semver_core.Version]:
        if level == 0:
            return None
        if level == 1:
            return semver_core.Version(major + 1, 0, 0)
        return semver_core.Version(major, minor + 1, 0)

    def _caret_upper(
        self, major: int, minor: int, patch: int, level: int
    ) -> semver_core.Version:
        if level == 1:
            return semver_core.Version(major + 1, 0, 0)
        if level == 2:
            if major > 0:
                return semver_core.Version(major + 1, 0, 0)
            return semver_core.Version(0, minor + 1, 0)
        if major > 0:
            return semver_core.Version(major + 1, 0, 0)
        if minor > 0:
            return semver_core.Version(0, minor + 1, 0)
        return semver_core.Version(0, 0, patch + 1)

    def _tilde_upper(
        self, major: int, minor: int, patch: int, level: int
    ) -> semver_core.Version:
        if level == 1:
            return semver_core.Version(major + 1, 0, 0)
        return semver_core.Version(major, minor + 1, 0)

    def _targets_prerelease(
        self, version: semver_core.Version, clauses: List[_Clause]
    ) -> bool:
        for clause in clauses:
            for _operator, target, upper in clause:
                for candidate in (target, upper):
                    if candidate is None or not candidate.prerelease:
                        continue
                    if (
                        candidate.major == version.major
                        and candidate.minor == version.minor
                        and candidate.patch == version.patch
                    ):
                        return True
        return False

    def _evaluate(
        self,
        version: semver_core.Version,
        comparator: _Comparator,
        engine: semver_core.VersionEngine,
    ) -> bool:
        operator, target, upper = comparator
        if operator == "not_in":
            below = engine.compare_precedence(version, target) < 0
            if upper is None:
                return below
            return below or engine.compare_precedence(version, upper) >= 0
        comparison = engine.compare_precedence(version, target)
        if operator == "==":
            return comparison == 0
        if operator == "!=":
            return comparison != 0
        if operator == "<":
            return comparison < 0
        if operator == "<=":
            return comparison <= 0
        if operator == ">":
            return comparison > 0
        return comparison >= 0


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RangeEngine,
        keys=[RangeEngine, semver_range.RangeEngine],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 4d0385b11dfb
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---
