# === File: dependency_solver_impl_test.py ===
"""Unit tests for the PackageRepository and DependencySolver singletons in dependency_solver_impl.

Covers release storage/indexing, descending precedence retrieval, and backtracking
dependency resolution contracts declared in low/dependency_solver_impl.pyi and
inherited from low/dependency_solver.pyi.
"""

from __future__ import annotations

import unittest
from functools import cmp_to_key
from typing import Dict, List, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository as RepositoryProtocol,
    ResolutionConflictError,
)
from semver_solver_multi.lib.semver_core import Version, VersionEngine
from semver_solver_multi.lib.semver_range import RangeEngine, VersionRange
from semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)


def _parse_simple_version(text: str) -> Version:
    """Parses a full or partial numeric version string into a Version record."""
    core_text, _, build_text = text.partition("+")
    version_text, _, prerelease_text = core_text.partition("-")
    components: List[int] = [int(component) for component in version_text.split(".")]
    while len(components) < 3:
        components.append(0)
    prerelease: Tuple[str, ...] = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build: Tuple[str, ...] = tuple(build_text.split(".")) if build_text else ()
    return Version(
        major=components[0],
        minor=components[1],
        patch=components[2],
        prerelease=prerelease,
        build=build,
    )


def _compare_prerelease(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Compares pre-release identifier sequences using SemVer precedence rules."""
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for left_segment, right_segment in zip(left, right):
        if left_segment == right_segment:
            continue
        left_numeric = left_segment.isdigit()
        right_numeric = right_segment.isdigit()
        if left_numeric and right_numeric:
            return (int(left_segment) > int(right_segment)) - (int(left_segment) < int(right_segment))
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return (left_segment > right_segment) - (left_segment < right_segment)
    return (len(left) > len(right)) - (len(left) < len(right))


def _compare_versions(left: Version, right: Version) -> int:
    """Compares two versions using SemVer precedence rules."""
    left_key = (left.major, left.minor, left.patch)
    right_key = (right.major, right.minor, right.patch)
    if left_key != right_key:
        return (left_key > right_key) - (left_key < right_key)
    return _compare_prerelease(left.prerelease, right.prerelease)


def _satisfies_comparator(version: Version, token: str) -> bool:
    """Evaluates a single comparator token against a candidate version."""
    for operator in ("==", "!=", ">=", "<=", ">", "<"):
        if token.startswith(operator):
            bound = _parse_simple_version(token[len(operator):].strip())
            comparison = _compare_versions(version, bound)
            if operator == "==":
                return comparison == 0
            if operator == "!=":
                return comparison != 0
            if operator == ">=":
                return comparison >= 0
            if operator == "<=":
                return comparison <= 0
            if operator == ">":
                return comparison > 0
            if operator == "<":
                return comparison < 0
    return False


def _satisfies_clause(version: Version, clause: str) -> bool:
    """Evaluates all whitespace-delimited comparators inside one clause."""
    tokens = clause.split()
    if not tokens:
        return False
    return all(_satisfies_comparator(version, token) for token in tokens)


def _satisfies(version: Version, raw_range: str) -> bool:
    """Evaluates a candidate version against a simple comparator expression."""
    for clause in raw_range.split("||"):
        if _satisfies_clause(version, clause.strip()):
            return True
    return False


def _dependency(name: str, range_text: str) -> PackageDependency:
    """Builds a PackageDependency from a package name and range text."""
    return PackageDependency(name=name, range_constraint=VersionRange(raw_text=range_text))


def _release_descending(left: PackageRelease, right: PackageRelease) -> int:
    """Orders package releases by version precedence descending."""
    return _compare_versions(right.version, left.version)


class MockVersionEngine:
    """Collaborator double for semver_core.VersionEngine precedence ordering."""

    def __init__(self) -> None:
        self.compared: List[Tuple[Version, Version]] = []

    def parse_version(self, text: str) -> Version:
        return _parse_simple_version(text)

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        self.compared.append((v1, v2))
        return _compare_versions(v1, v2)


class MockRangeEngine:
    """Collaborator double for semver_range.RangeEngine constraint matching."""

    def __init__(self) -> None:
        self.requests: List[Tuple[Version, str, bool]] = []

    def parse_range(self, text: str) -> VersionRange:
        return VersionRange(raw_text=text)

    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        self.requests.append((version, range_constraint.raw_text, include_prerelease))
        return _satisfies(version, range_constraint.raw_text)


class MockPackageRepository:
    """Collaborator double for dependency_solver.PackageRepository."""

    def __init__(self) -> None:
        self._releases: Dict[str, List[PackageRelease]] = {}
        self.lookups: List[str] = []

    def add_release(self, release: PackageRelease) -> None:
        releases = self._releases.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=cmp_to_key(_release_descending))

    def register_package(self, release: PackageRelease) -> None:
        self.add_release(release)

    def get_releases(self, name: str) -> List[PackageRelease]:
        self.lookups.append(name)
        if name not in self._releases:
            raise PackageNotFoundError(
                message=f"Package '{name}' is not registered",
                package_name=name,
            )
        return list(self._releases[name])

    def has_package(self, name: str) -> bool:
        return name in self._releases

    def all_packages(self) -> Set[str]:
        return set(self._releases)


class PackageRepositoryTest(unittest.TestCase):
    """Verifies the PackageRepository singleton against the repository contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[VersionEngine],
            tier=system,
        )

    def test_register_package_stores_release(self) -> None:
        """Registers a release and surfaces it from get_releases and all_packages."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="lib", version=Version(1, 2, 3)))
            releases = repository.get_releases("lib")
            package_names = repository.all_packages()
        self.assertEqual(1, len(releases))
        self.assertEqual(Version(1, 2, 3), releases[0].version)
        self.assertEqual({"lib"}, package_names)

    def test_get_releases_returns_descending_precedence(self) -> None:
        """Returns all releases ordered by version precedence descending."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="lib", version=Version(1, 5, 0)))
            repository.register_package(PackageRelease(name="lib", version=Version(2, 0, 0)))
            repository.register_package(PackageRelease(name="lib", version=Version(0, 9, 9)))
            repository.register_package(PackageRelease(name="lib", version=Version(1, 0, 0, ("rc", "1"))))
            releases = repository.get_releases("lib")
        self.assertEqual(
            [
                Version(2, 0, 0),
                Version(1, 5, 0),
                Version(1, 0, 0, ("rc", "1")),
                Version(0, 9, 9),
            ],
            [release.version for release in releases],
        )

    def test_register_package_coordinates_with_version_engine(self) -> None:
        """Consults the semver_core VersionEngine while re-sorting registered releases."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="lib", version=Version(1, 0, 0)))
            repository.register_package(PackageRelease(name="lib", version=Version(2, 0, 0)))
        self.assertTrue(self.version_engine.compared)

    def test_has_package_reflects_registration(self) -> None:
        """Reports membership for registered names and absence for unknown names."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="lib", version=Version(1, 0, 0)))
            self.assertTrue(repository.has_package("lib"))
            self.assertFalse(repository.has_package("missing"))

    def test_all_packages_returns_registered_names(self) -> None:
        """Produces the set of every registered package name."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="app", version=Version(1, 0, 0)))
            repository.register_package(PackageRelease(name="lib", version=Version(1, 0, 0)))
            package_names = repository.all_packages()
        self.assertEqual({"app", "lib"}, package_names)

    def test_get_releases_returns_shallow_copy(self) -> None:
        """Returns a fresh list so callers cannot mutate internal repository state."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="lib", version=Version(1, 0, 0)))
            first = repository.get_releases("lib")
            second = repository.get_releases("lib")
            self.assertIsNot(first, second)
            first.clear()
            self.assertEqual(1, len(repository.get_releases("lib")))

    def test_get_releases_missing_package_raises(self) -> None:
        """Raises PackageNotFoundError carrying the missing package name."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as context:
                repository.get_releases("missing")
        self.assertEqual("missing", context.exception.package_name)


class DependencySolverTest(unittest.TestCase):
    """Verifies the DependencySolver singleton against the solver contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[VersionEngine],
            tier=system,
        )
        self.range_engine = MockRangeEngine()
        self.registry.register_instance(
            self.range_engine,
            keys=[RangeEngine],
            tier=system,
        )
        self.repository = MockPackageRepository()
        self.registry.register_instance(
            self.repository,
            keys=[PackageRepository, RepositoryProtocol],
            tier=system,
        )

    def _add_release(
        self,
        name: str,
        version: Version,
        dependencies: Tuple[PackageDependency, ...] = (),
    ) -> None:
        self.repository.add_release(
            PackageRelease(name=name, version=version, dependencies=dependencies)
        )

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """Selects the highest precedence release satisfying the requested constraint."""
        self._add_release("lib", Version(1, 0, 0))
        self._add_release("lib", Version(1, 5, 0))
        self._add_release("lib", Version(2, 0, 0))
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([_dependency("lib", "<2.0.0")])
        self.assertEqual(Version(1, 5, 0), outcome.selected_versions["lib"])
        self.assertTrue(self.range_engine.requests)
        self.assertTrue(self.repository.lookups)

    def test_resolve_transitive_dependencies(self) -> None:
        """Assigns compatible versions for transitive dependencies of a root package."""
        self._add_release("lib", Version(1, 0, 0))
        self._add_release("lib", Version(1, 5, 0))
        self._add_release("lib", Version(2, 0, 0))
        self._add_release("app", Version(1, 0, 0), (_dependency("lib", ">=1.0.0"),))
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([_dependency("app", ">=1.0.0")])
        self.assertEqual(Version(1, 0, 0), outcome.selected_versions["app"])
        self.assertEqual(Version(2, 0, 0), outcome.selected_versions["lib"])

    def test_resolve_reports_derivation_steps(self) -> None:
        """Produces an ordered tuple of derivation steps alongside the assignment."""
        self._add_release("lib", Version(1, 0, 0))
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([_dependency("lib", ">=1.0.0")])
        self.assertIsInstance(outcome.derivation_steps, tuple)
        self.assertTrue(outcome.derivation_steps)
        for step in outcome.derivation_steps:
            self.assertIsInstance(step, str)

    def test_resolve_produces_satisfying_assignment(self) -> None:
        """Produces a complete assignment whose versions satisfy all constraints."""
        self._add_release("lib", Version(1, 0, 0))
        self._add_release("lib", Version(1, 5, 0))
        self._add_release("app", Version(1, 0, 0), (_dependency("lib", ">=1.0.0"),))
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([_dependency("app", ">=1.0.0")])
        self.assertTrue(_satisfies(outcome.selected_versions["app"], ">=1.0.0"))
        self.assertTrue(_satisfies(outcome.selected_versions["lib"], ">=1.0.0"))

    def test_resolve_backtracks_on_assigned_release_conflict(self) -> None:
        """Backtracks to another candidate when a later dependency excludes an assigned release."""
        self._add_release("core", Version(2, 0, 0))
        self._add_release("app", Version(1, 5, 0), (_dependency("core", "<2.0.0"),))
        self._add_release("app", Version(1, 0, 0), (_dependency("core", ">=1.0.0"),))
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(
                [
                    _dependency("core", ">=1.0.0"),
                    _dependency("app", ">=1.0.0"),
                ]
            )
        self.assertEqual(Version(2, 0, 0), outcome.selected_versions["core"])
        self.assertEqual(Version(1, 0, 0), outcome.selected_versions["app"])

    def test_resolve_reselects_assigned_release_excluded_by_transitive_requirement(self) -> None:
        """Reassigns an earlier selection after a transitive requirement excludes it."""
        self._add_release("core", Version(1, 0, 0))
        self._add_release("core", Version(2, 0, 0))
        self._add_release("app", Version(1, 0, 0), (_dependency("core", "<2.0.0"),))
        self._add_release("app", Version(1, 1, 0), (_dependency("core", "<2.0.0"),))
        self._add_release("app", Version(1, 2, 0), (_dependency("core", "<2.0.0"),))
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(
                [
                    _dependency("core", ">=1.0.0"),
                    _dependency("app", ">=1.0.0"),
                ]
            )
        self.assertEqual(Version(1, 0, 0), outcome.selected_versions["core"])
        self.assertEqual(Version(1, 2, 0), outcome.selected_versions["app"])

    def test_resolve_missing_package_raises_conflict(self) -> None:
        """Raises ResolutionConflictError, never PackageNotFoundError, for missing packages."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([_dependency("missing", ">=1.0.0")])
        self.assertIn("missing", context.exception.conflicting_packages)
        self.assertIsInstance(context.exception.explanation, str)

    def test_resolve_unsatisfiable_intersection_raises_conflict(self) -> None:
        """Raises ResolutionConflictError when accumulated constraints share no release."""
        self._add_release("lib", Version(1, 0, 0))
        self._add_release("lib", Version(2, 0, 0))
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve(
                    [
                        _dependency("lib", ">=2.0.0"),
                        _dependency("lib", "<2.0.0"),
                    ]
                )
        self.assertIn("lib", context.exception.conflicting_packages)

    def test_resolve_transitive_conflict_raises(self) -> None:
        """Raises ResolutionConflictError when a transitive requirement cannot be met."""
        self._add_release("lib", Version(1, 0, 0))
        self._add_release("app", Version(1, 0, 0), (_dependency("lib", ">=2.0.0"),))
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([_dependency("app", ">=1.0.0")])
        self.assertIn("lib", context.exception.conflicting_packages)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:27:07Z
# LAST_CHANGED: 2026-11-09T23:13:17Z
# CHANGE: Add coverage for the assigned-release-versus-later-transitive-requirement branch: a resolver test where a later dependency conflicts with an already assigned release and backtracks to the next candidate, plus a test where the assigned release is excluded by a new transitive requirement and the solver reselects a compatible release.
# COVERAGE_AUDIT: 2026-11-09T23:27:07Z
# QA_AUDIT: 2026-11-09T23:26:39Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for the VersionEngine singleton in semver_core_impl.

Covers the SemVer 2.0.0 grammar validation and precedence comparison contracts
declared in low/semver_core_impl.pyi and inherited from low/semver_core.pyi.
"""

from __future__ import annotations

import unittest
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from semver_solver_multi.lib.semver_core_impl import VersionEngine, __initialize__


def _version(
    major: int,
    minor: int = 0,
    patch: int = 0,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> Version:
    """Builds a domain Version record from primitive component values."""
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


class VersionEngineTest(unittest.TestCase):
    """Verifies the VersionEngine singleton against the semver_core contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_yields_component_record(self) -> None:
        """Parses a plain version and exposes its numeric components."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("1.2.3")

        self.assertEqual(1, parsed.major)
        self.assertEqual(2, parsed.minor)
        self.assertEqual(3, parsed.patch)
        self.assertEqual((), parsed.prerelease)
        self.assertEqual((), parsed.build)
        self.assertFalse(parsed.is_prerelease)

    def test_parse_version_yields_prerelease_and_build_tuples(self) -> None:
        """Parses pre-release identifiers and build metadata into separate tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("1.2.3-alpha.1+build.5")

        self.assertEqual(1, parsed.major)
        self.assertEqual(2, parsed.minor)
        self.assertEqual(3, parsed.patch)
        self.assertEqual(("alpha", "1"), parsed.prerelease)
        self.assertEqual(("build", "5"), parsed.build)
        self.assertTrue(parsed.is_prerelease)
        self.assertEqual("1.2.3-alpha.1+build.5", parsed.format())

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """Rejects numeric identifiers that carry forbidden leading zeroes."""
        invalid_texts = ("01.2.3", "1.02.3", "1.2.03", "1.2.3-01")
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in invalid_texts:
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError) as context:
                        engine.parse_version(text)
                    self.assertEqual(text, context.exception.raw_text)

    def test_parse_version_rejects_grammar_violations(self) -> None:
        """Rejects version text that violates the SemVer grammar."""
        invalid_texts = ("", "1", "1.2", "1.2.3.4", "not-a-version")
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in invalid_texts:
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError) as context:
                        engine.parse_version(text)
                    self.assertEqual(text, context.exception.raw_text)

    def test_compare_precedence_is_tri_state(self) -> None:
        """Returns a negative, zero, or positive integer reflecting the ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(_version(1), _version(2)), 0)
            self.assertGreater(engine.compare_precedence(_version(2), _version(1)), 0)
            self.assertEqual(0, engine.compare_precedence(_version(1), _version(1)))

    def test_compare_precedence_compares_numerically(self) -> None:
        """Compares major, minor, and patch components numerically rather than lexically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(_version(1, 10, 0), _version(1, 9, 0)),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(_version(1, 0, 10), _version(1, 0, 9)),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(_version(10, 0, 0), _version(9, 99, 99)),
                0,
            )

    def test_compare_precedence_ranks_normal_above_prerelease(self) -> None:
        """Ranks a normal version above a pre-release sharing the same numeric triple."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(_version(1, 0, 0), _version(1, 0, 0, ("alpha",))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(_version(1, 0, 0, ("rc", "1")), _version(1, 0, 0)),
                0,
            )

    def test_compare_precedence_orders_prerelease_segments(self) -> None:
        """Orders pre-release segments numerically and lexically, ranking numeric below string."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(_version(1, 0, 0, ("alpha",)), _version(1, 0, 0, ("alpha", "1"))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(_version(1, 0, 0, ("alpha", "1")), _version(1, 0, 0, ("alpha", "beta"))),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(_version(1, 0, 0, ("beta", "11")), _version(1, 0, 0, ("beta", "2"))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(_version(1, 0, 0, ("1",)), _version(1, 0, 0, ("alpha",))),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(_version(1, 0, 0, ("alpha",)), _version(1, 0, 0, ("1",))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(_version(1, 0, 0, ("alpha",)), _version(1, 0, 0, ("beta",))),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(_version(1, 0, 0, ("beta",)), _version(1, 0, 0, ("alpha",))),
                0,
            )
            self.assertEqual(
                0,
                engine.compare_precedence(
                    _version(1, 0, 0, ("rc", "1")),
                    _version(1, 0, 0, ("rc", "1")),
                ),
            )

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """Ignores build metadata when determining precedence between versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                0,
                engine.compare_precedence(
                    _version(1, 0, 0, build=("build", "1")),
                    _version(1, 0, 0, build=("build", "2")),
                ),
            )
            self.assertEqual(
                0,
                engine.compare_precedence(
                    _version(1, 0, 0, ("alpha",), ("build", "1")),
                    _version(1, 0, 0, ("alpha",), ("build", "2")),
                ),
            )
            self.assertGreater(
                engine.compare_precedence(
                    _version(1, 0, 1, build=("build", "2")),
                    _version(1, 0, 0, build=("build", "1")),
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:18:13Z
# LAST_CHANGED: 2026-11-09T23:15:54Z
# CHANGE: Add prerelease-ordering coverage for the uncovered orderings: assert a string segment ranks above a numeric segment (alpha > 1, the reverse of the existing numeric-below-string check) and assert ASCII lexicographic ordering between string segments (alpha < beta and beta > alpha).
# COVERAGE_AUDIT: 2026-11-09T23:18:13Z
# QA_AUDIT: 2026-11-09T23:18:00Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for the RangeEngine singleton in semver_range_impl.

Covers range parsing, wildcard/prefix expansion, hyphen and union syntax, and
constraint satisfaction contracts declared in low/semver_range_impl.pyi and
inherited from low/semver_range.pyi.
"""

from __future__ import annotations

import unittest
from typing import List, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import Version, VersionEngine
from semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from semver_solver_multi.lib.semver_range_impl import RangeEngine, __initialize__


def _version(
    major: int,
    minor: int = 0,
    patch: int = 0,
    prerelease: Tuple[str, ...] = (),
) -> Version:
    """Builds a domain Version record from primitive component values."""
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
    )


def _parse_simple_version(text: str) -> Version:
    """Parses a full or partial numeric version string into a Version record."""
    core_text, _, build_text = text.partition("+")
    version_text, _, prerelease_text = core_text.partition("-")
    components: List[int] = [int(component) for component in version_text.split(".")]
    while len(components) < 3:
        components.append(0)
    prerelease: Tuple[str, ...] = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build: Tuple[str, ...] = tuple(build_text.split(".")) if build_text else ()
    return Version(
        major=components[0],
        minor=components[1],
        patch=components[2],
        prerelease=prerelease,
        build=build,
    )


def _compare_prerelease(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Compares pre-release identifier sequences using SemVer precedence rules."""
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for left_segment, right_segment in zip(left, right):
        if left_segment == right_segment:
            continue
        left_numeric = left_segment.isdigit()
        right_numeric = right_segment.isdigit()
        if left_numeric and right_numeric:
            return (int(left_segment) > int(right_segment)) - (int(left_segment) < int(right_segment))
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return (left_segment > right_segment) - (left_segment < right_segment)
    return (len(left) > len(right)) - (len(left) < len(right))


def _compare_versions(left: Version, right: Version) -> int:
    """Compares two versions using SemVer precedence rules."""
    left_key = (left.major, left.minor, left.patch)
    right_key = (right.major, right.minor, right.patch)
    if left_key != right_key:
        return (left_key > right_key) - (left_key < right_key)
    return _compare_prerelease(left.prerelease, right.prerelease)


class MockVersionEngine:
    """Collaborator double for semver_core.VersionEngine precedence ordering."""

    def __init__(self) -> None:
        self.compared: List[Tuple[Version, Version]] = []

    def parse_version(self, text: str) -> Version:
        return _parse_simple_version(text)

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        self.compared.append((v1, v2))
        return _compare_versions(v1, v2)


class RangeEngineTest(unittest.TestCase):
    """Verifies the RangeEngine singleton against the semver_range contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[VersionEngine],
            tier=system,
        )

    def test_parse_range_supports_basic_comparators(self) -> None:
        """Parses every declared relational comparator applied to a full version."""
        range_texts = (
            "==1.0.0",
            "=1.0.0",
            "!=1.0.0",
            "<1.0.0",
            "<=1.0.0",
            ">1.0.0",
            ">=1.0.0",
        )
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in range_texts:
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertIsInstance(parsed, VersionRange)
                    self.assertEqual(text, parsed.raw_text)

    def test_parse_range_supports_caret_and_tilde_prefixes(self) -> None:
        """Parses caret and tilde prefixes applied to full versions and wildcards."""
        range_texts = (
            "^1.0.0",
            "^1.x",
            "^0.x",
            "^0.1.x",
            "^1.2.x",
            "^*",
            "^0.1.2",
            "^0.0.3",
            "^0.0.0",
            "^0.2.3",
            "^1.2.0",
            "~1.2.3",
            "~1.2.x",
            "~1.x",
            "~*",
        )
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in range_texts:
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertEqual(text, parsed.raw_text)

    def test_parse_range_supports_wildcard_comparators(self) -> None:
        """Parses wildcard expressions behind relational and prefix operators."""
        range_texts = (
            ">=1.x",
            "!=1.x",
            ">1.*",
            "<1.x",
            "<=1.x",
            "<1.*",
            "<=1.*",
            "^1.x",
            "~1.2.x",
            ">=*",
        )
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in range_texts:
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertEqual(text, parsed.raw_text)

    def test_parse_range_supports_universal_wildcard_comparator_forms(self) -> None:
        """Parses an equality wildcard band and every universal wildcard comparator form."""
        range_texts = ("==1.x", "==*", "!=*", ">*", "<*", "<=*")
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in range_texts:
                with self.subTest(text=text):
                    self.assertIsInstance(engine.parse_range(text), VersionRange)

    def test_parse_range_supports_hyphen_ranges(self) -> None:
        """Parses hyphen ranges connecting full-version and wildcard bounds."""
        range_texts = ("1.0.0 - 2.x", "1.x - 2.x", "1.0.0 - 2.0.0")
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in range_texts:
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertEqual(text, parsed.raw_text)

    def test_parse_range_supports_union_alternatives(self) -> None:
        """Parses union alternatives delimited by the double-pipe token."""
        text = ">=1.0.0 <2.0.0 || >=3.0.0"
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(text)
        self.assertEqual(text, parsed.raw_text)

    def test_parse_range_trims_surrounding_whitespace(self) -> None:
        """Stores the trimmed range expression in the produced VersionRange."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("   >=1.0.0   ")
        self.assertEqual(">=1.0.0", parsed.raw_text)

    def test_parse_range_accepts_operator_whitespace(self) -> None:
        """Accepts optional whitespace between an operator and its operand."""
        range_texts = (">= 1.0.0", ">= 1.x", "~ 1.x", "^ 1.x")
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in range_texts:
                with self.subTest(text=text):
                    self.assertIsInstance(engine.parse_range(text), VersionRange)

    def test_parse_range_rejects_empty_input(self) -> None:
        """Rejects empty and whitespace-only range expressions."""
        invalid_texts = ("", "    ")
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in invalid_texts:
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as context:
                        engine.parse_range(text)
                    self.assertEqual(text, context.exception.raw_range)

    def test_parse_range_rejects_empty_union_clauses(self) -> None:
        """Rejects union expressions containing empty alternative clauses."""
        invalid_texts = (">=1.0.0 ||", "|| >=1.0.0", ">=1.0.0 ||  || >=2.0.0")
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in invalid_texts:
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as context:
                        engine.parse_range(text)
                    self.assertEqual(text, context.exception.raw_range)

    def test_parse_range_rejects_comma_delimited_comparators(self) -> None:
        """Rejects comma-delimited comparators inside a clause."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError) as context:
                engine.parse_range(">=1.0.0, <2.0.0")
        self.assertEqual(">=1.0.0, <2.0.0", context.exception.raw_range)

    def test_parse_range_rejects_bare_partial_versions(self) -> None:
        """Rejects partial versions that lack wildcard characters."""
        invalid_texts = ("1", "1.2", ">1.2", "^0.0", "1.2 - 2.3")
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in invalid_texts:
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as context:
                        engine.parse_range(text)
                    self.assertEqual(text, context.exception.raw_range)

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """Rejects range text that violates the range expression grammar."""
        invalid_texts = (
            ">>1.0.0",
            "abc",
            "1.0.0 -",
            ">= ",
            "1.x.3",
            "1.2.3.x",
            ">=1.2.3.x",
            "<=1.2.3.*",
            ">=1.2.3.4",
            "01.x",
            ">=>=1.0.0",
            "^^1.0.0",
        )
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in invalid_texts:
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as context:
                        engine.parse_range(text)
                    self.assertEqual(text, context.exception.raw_range)

    def test_satisfies_basic_comparators(self) -> None:
        """Evaluates candidate versions against relational comparator boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            self.assertTrue(engine.satisfies(_version(1, 2, 3), engine.parse_range(">=1.0.0"), False))
            self.assertTrue(engine.satisfies(_version(1, 2, 3), engine.parse_range(">1.2.2"), False))
            self.assertFalse(engine.satisfies(_version(1, 2, 3), engine.parse_range(">1.2.3"), False))
            self.assertTrue(engine.satisfies(_version(1, 2, 3), engine.parse_range("<=1.2.3"), False))
            self.assertFalse(engine.satisfies(_version(1, 2, 3), engine.parse_range("<1.2.3"), False))
            self.assertTrue(engine.satisfies(_version(1, 2, 3), engine.parse_range("==1.2.3"), False))
            self.assertTrue(engine.satisfies(_version(1, 2, 3), engine.parse_range("!=1.2.4"), False))

    def test_satisfies_caret_expansion(self) -> None:
        """Expands caret prefixes based on the first non-zero version component."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            caret_wildcard = engine.parse_range("^1.x")
            self.assertTrue(engine.satisfies(_version(1, 0, 0), caret_wildcard, False))
            self.assertTrue(engine.satisfies(_version(1, 9, 9), caret_wildcard, False))
            self.assertFalse(engine.satisfies(_version(2, 0, 0), caret_wildcard, False))
            self.assertFalse(engine.satisfies(_version(0, 9, 9), caret_wildcard, False))
            caret_full = engine.parse_range("^1.0.0")
            self.assertTrue(engine.satisfies(_version(1, 5, 0), caret_full, False))
            self.assertFalse(engine.satisfies(_version(2, 0, 0), caret_full, False))
            caret_zero_major = engine.parse_range("^0.x")
            self.assertTrue(engine.satisfies(_version(0, 5, 0), caret_zero_major, False))
            self.assertFalse(engine.satisfies(_version(1, 0, 0), caret_zero_major, False))
            caret_zero_minor = engine.parse_range("^0.1.x")
            self.assertTrue(engine.satisfies(_version(0, 1, 5), caret_zero_minor, False))
            self.assertFalse(engine.satisfies(_version(0, 2, 0), caret_zero_minor, False))
            caret_zero_minor_full = engine.parse_range("^0.1.2")
            self.assertTrue(engine.satisfies(_version(0, 1, 2), caret_zero_minor_full, False))
            self.assertTrue(engine.satisfies(_version(0, 1, 9), caret_zero_minor_full, False))
            self.assertFalse(engine.satisfies(_version(0, 2, 0), caret_zero_minor_full, False))
            self.assertFalse(engine.satisfies(_version(0, 1, 1), caret_zero_minor_full, False))
            caret_zero_minor_patch_full = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(_version(0, 0, 3), caret_zero_minor_patch_full, False))
            self.assertFalse(engine.satisfies(_version(0, 0, 2), caret_zero_minor_patch_full, False))
            caret_multi = engine.parse_range("^1.2.x")
            self.assertTrue(engine.satisfies(_version(1, 2, 5), caret_multi, False))
            self.assertTrue(engine.satisfies(_version(1, 9, 9), caret_multi, False))
            self.assertFalse(engine.satisfies(_version(2, 0, 0), caret_multi, False))
            caret_universal = engine.parse_range("^*")
            self.assertTrue(engine.satisfies(_version(1, 2, 3), caret_universal, False))
            self.assertTrue(engine.satisfies(_version(0, 0, 0), caret_universal, False))

    def test_satisfies_tilde_expansion(self) -> None:
        """Expands tilde prefixes into lower and upper minor boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            tilde_wildcard = engine.parse_range("~1.x")
            self.assertTrue(engine.satisfies(_version(1, 0, 0), tilde_wildcard, False))
            self.assertTrue(engine.satisfies(_version(1, 9, 9), tilde_wildcard, False))
            self.assertFalse(engine.satisfies(_version(2, 0, 0), tilde_wildcard, False))
            self.assertFalse(engine.satisfies(_version(0, 9, 9), tilde_wildcard, False))
            tilde_full = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(_version(1, 2, 3), tilde_full, False))
            self.assertTrue(engine.satisfies(_version(1, 2, 9), tilde_full, False))
            self.assertFalse(engine.satisfies(_version(1, 3, 0), tilde_full, False))
            self.assertFalse(engine.satisfies(_version(1, 2, 2), tilde_full, False))
            tilde_universal = engine.parse_range("~*")
            self.assertTrue(engine.satisfies(_version(1, 2, 3), tilde_universal, False))
            self.assertTrue(engine.satisfies(_version(0, 0, 0), tilde_universal, False))

    def test_satisfies_wildcard_inequality_expansion(self) -> None:
        """Expands wildcard comparators into paired lower and upper inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            at_least_wildcard = engine.parse_range(">=1.x")
            self.assertTrue(engine.satisfies(_version(1, 0, 0), at_least_wildcard, False))
            self.assertTrue(engine.satisfies(_version(2, 5, 0), at_least_wildcard, False))
            self.assertFalse(engine.satisfies(_version(0, 9, 9), at_least_wildcard, False))
            not_wildcard = engine.parse_range("!=1.x")
            self.assertFalse(engine.satisfies(_version(1, 0, 0), not_wildcard, False))
            self.assertFalse(engine.satisfies(_version(1, 9, 9), not_wildcard, False))
            self.assertTrue(engine.satisfies(_version(0, 9, 9), not_wildcard, False))
            self.assertTrue(engine.satisfies(_version(2, 0, 0), not_wildcard, False))
            less_than_wildcard = engine.parse_range("<1.x")
            self.assertTrue(engine.satisfies(_version(0, 9, 9), less_than_wildcard, False))
            self.assertFalse(engine.satisfies(_version(1, 0, 0), less_than_wildcard, False))
            self.assertFalse(engine.satisfies(_version(1, 5, 0), less_than_wildcard, False))
            less_or_equal_wildcard = engine.parse_range("<=1.x")
            self.assertTrue(engine.satisfies(_version(0, 9, 9), less_or_equal_wildcard, False))
            self.assertTrue(engine.satisfies(_version(1, 0, 0), less_or_equal_wildcard, False))
            self.assertTrue(engine.satisfies(_version(1, 9, 9), less_or_equal_wildcard, False))
            self.assertFalse(engine.satisfies(_version(2, 0, 0), less_or_equal_wildcard, False))

    def test_satisfies_universal_wildcard(self) -> None:
        """Treats the universal wildcard comparator as satisfied by every normal version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            universal = engine.parse_range(">=*")
            for candidate in (_version(0, 0, 0), _version(1, 2, 3), _version(99, 99, 99)):
                with self.subTest(candidate=candidate):
                    self.assertTrue(engine.satisfies(candidate, universal, False))

    def test_satisfies_universal_wildcard_comparator_forms(self) -> None:
        """Evaluates an equality wildcard band and every universal comparator variant."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            equality_band = engine.parse_range("==1.x")
            self.assertTrue(engine.satisfies(_version(1, 5, 0), equality_band, False))
            self.assertFalse(engine.satisfies(_version(2, 0, 0), equality_band, False))
            universal_forms = ("==*", "!=*", ">*", "<*", "<=*")
            for text in universal_forms:
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertIsInstance(
                        engine.satisfies(_version(1, 2, 3), parsed, False),
                        bool,
                    )

    def test_satisfies_hyphen_range_full_upper_bound(self) -> None:
        """Treats a full-version hyphen upper bound as an inclusive boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            hyphen = engine.parse_range("1.0.0 - 2.0.0")
            self.assertTrue(engine.satisfies(_version(1, 0, 0), hyphen, False))
            self.assertTrue(engine.satisfies(_version(2, 0, 0), hyphen, False))
            self.assertFalse(engine.satisfies(_version(2, 0, 1), hyphen, False))
            self.assertFalse(engine.satisfies(_version(0, 9, 9), hyphen, False))

    def test_satisfies_hyphen_range_expansion(self) -> None:
        """Expands hyphen ranges connecting full-version and wildcard bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            hyphen = engine.parse_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(_version(1, 0, 0), hyphen, False))
            self.assertTrue(engine.satisfies(_version(2, 9, 9), hyphen, False))
            self.assertFalse(engine.satisfies(_version(3, 0, 0), hyphen, False))
            self.assertFalse(engine.satisfies(_version(0, 9, 9), hyphen, False))

    def test_satisfies_union_alternatives(self) -> None:
        """Satisfies a union when any alternative clause is fully satisfied."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            union = engine.parse_range(">=1.0.0 <2.0.0 || >=3.0.0")
            self.assertTrue(engine.satisfies(_version(1, 5, 0), union, False))
            self.assertFalse(engine.satisfies(_version(2, 5, 0), union, False))
            self.assertTrue(engine.satisfies(_version(3, 1, 0), union, False))
            self.assertFalse(engine.satisfies(_version(0, 5, 0), union, False))

    def test_satisfies_filters_prerelease_versions(self) -> None:
        """Excludes pre-release candidates unless the range explicitly targets that version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            candidate = _version(1, 0, 0, ("alpha",))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range(">=0.0.0"), False))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range(">=0.0.0"), True))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range(">=1.0.0-alpha"), False))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range(">=2.0.0-alpha"), False))

    def test_satisfies_prerelease_boundary_inequality(self) -> None:
        """Ranks a pre-release strictly below its corresponding normal version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            candidate = _version(1, 0, 0, ("alpha",))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range(">=1.0.0"), True))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range("<1.0.0"), True))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range(">=1.0.0-alpha"), True))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:27:13Z
# LAST_CHANGED: 2026-11-09T23:25:20Z
# CHANGE: Cover remaining branch coverage: parse caret full versions on zero-major boundaries (^0.1.2, ^0.0.3, ^0.0.0, ^0.2.3, ^1.2.0) with satisfies boundary assertions; parse bounded wildcard inequalities (<1.x, <=1.x, <1.*, <=1.*) with satisfies checks; and reject over-long wildcard component counts (1.2.3.x, >=1.2.3.x, <=1.2.3.*) as InvalidRangeError.
# COVERAGE_AUDIT: 2026-11-09T23:27:13Z
# QA_AUDIT: 2026-11-09T23:26:42Z
# --- END AUTOFAB METADATA ---
