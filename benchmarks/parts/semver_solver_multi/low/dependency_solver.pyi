"""Low-level interface specification for package repository and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type
import semver_core
import semver_range


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
        - [slug:dependency_solver.repo.register_release]: MUST register the package release into the repository.
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
        - [slug:dependency_solver.repo.missing_package]: WHEN name is not registered, MUST raise PackageNotFoundError.

        POSTCONDITIONS:
        - [slug:dependency_solver.repo.descending_releases]: MUST yield all registered releases for package name ordered by version precedence descending.
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
        - [slug:dependency_solver.repo.has_membership]: MUST evaluate to True when package name exists in repository, and False otherwise.
        """
        ...

    @operation
    def all_packages(self) -> Set[str]:
        """Provides the set of all registered package names.

        Returns:
            Set of registered package name strings.

        POSTCONDITIONS:
        - [slug:dependency_solver.repo.all_names]: MUST produce the set of all registered package names.
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
        - [slug:dependency_solver.solver.unsatisfiable_conflict]: WHEN dependency constraints are unsatisfiable, MUST raise ResolutionConflictError identifying conflicting packages.
        - [slug:dependency_solver.solver.missing_package_conflict]: WHEN a dependency references a package absent from the repository, MUST raise ResolutionConflictError without allowing PackageNotFoundError to escape.

        POSTCONDITIONS:
        - [slug:dependency_solver.solver.compatible_assignment]: MUST compute a mutually compatible version assignment satisfying all transitive package dependencies.
        - [slug:dependency_solver.solver.highest_precedence]: MUST select the highest precedence compatible release for each required package.
        - [slug:dependency_solver.solver.derivation_report]: MUST produce a ResolutionOutcome containing the selected version mapping and derivation steps.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T19:00:00Z
# LAST_CHANGED: 2026-10-30T19:00:00Z
# CHANGE: Update imports to semver_core and semver_range
# CODE_HASH: 000000000000
# SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
# --- END CLEANROOM METADATA ---
