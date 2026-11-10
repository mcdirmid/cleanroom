# === File: dependency_solver_impl_test.py ===
"""Unit tests for the dependency_solver_impl repository and solver against their low-level specification."""

from __future__ import annotations

import unittest
from typing import Dict, List, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
)
from semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)
from semver_solver_multi.lib.semver_core import (
    SemVerError,
    Version,
    VersionEngine as CoreVersionEngine,
)
from semver_solver_multi.lib.semver_range import RangeEngine as CoreRangeEngine, VersionRange


def _version_key(version: Version) -> Tuple[int, int, int, Tuple[str, ...], Tuple[str, ...]]:
    """Builds a hashable key for a domain Version record."""
    return (
        version.major,
        version.minor,
        version.patch,
        tuple(version.prerelease),
        tuple(version.build),
    )


def _numeric_component(text: str) -> int:
    """Converts a numeric version component, tolerating wildcard placeholders."""
    if text.isdigit():
        return int(text)
    return 0


def _parse_version_text(text: str) -> Version:
    """Parses a version-shaped string into a Version record for mock collaborator scripting."""
    trimmed = text.strip()
    core_and_rest = trimmed.split("+", 1)
    core_and_prerelease = core_and_rest[0]
    build: Tuple[str, ...] = ()
    if len(core_and_rest) == 2:
        build = tuple(part for part in core_and_rest[1].split(".") if part)
    core_pieces = core_and_prerelease.split("-", 1)
    numeric_parts = [_numeric_component(part) for part in core_pieces[0].split(".")]
    if len(numeric_parts) < 2:
        numeric_parts.append(0)
    if len(numeric_parts) < 3:
        numeric_parts.append(0)
    prerelease: Tuple[str, ...] = ()
    if len(core_pieces) == 2:
        prerelease = tuple(part for part in core_pieces[1].split(".") if part)
    return Version(numeric_parts[0], numeric_parts[1], numeric_parts[2], prerelease, build)


def _compare_identifiers(left: str, right: str) -> int:
    """Compares two pre-release identifiers using SemVer numeric-then-ASCII rules."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        if left_value > right_value:
            return 1
        if left_value < right_value:
            return -1
        return 0
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    if left > right:
        return 1
    if left < right:
        return -1
    return 0


def _compare_versions(first: Version, second: Version) -> int:
    """Computes SemVer 2.0.0 precedence between two Version records."""
    first_core = (first.major, first.minor, first.patch)
    second_core = (second.major, second.minor, second.patch)
    if first_core > second_core:
        return 1
    if first_core < second_core:
        return -1
    first_pre = tuple(first.prerelease)
    second_pre = tuple(second.prerelease)
    if not first_pre and not second_pre:
        return 0
    if not first_pre:
        return 1
    if not second_pre:
        return -1
    for left, right in zip(first_pre, second_pre):
        comparison = _compare_identifiers(left, right)
        if comparison != 0:
            return comparison
    if len(first_pre) > len(second_pre):
        return 1
    if len(first_pre) < len(second_pre):
        return -1
    return 0


class MockVersionEngine:
    """Lightweight test double realizing the semver_core.VersionEngine collaborator protocol."""

    def __init__(self) -> None:
        self.parse_calls: List[str] = []
        self.compare_calls: List[Tuple[Version, Version]] = []

    def parse_version(self, text: str) -> Version:
        """Records the requested version text and returns the equivalent Version record."""
        self.parse_calls.append(text)
        return _parse_version_text(text)

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Records the compared pair and returns its SemVer precedence ordering."""
        self.compare_calls.append((v1, v2))
        return _compare_versions(v1, v2)


class MockRangeEngine:
    """Lightweight test double realizing the semver_range.RangeEngine collaborator protocol."""

    def __init__(self) -> None:
        self.satisfaction_calls: List[Tuple[Version, str, bool]] = []
        self.parse_range_calls: List[str] = []
        self._scripted: Dict[Tuple[Tuple[int, int, int, Tuple[str, ...], Tuple[str, ...]], str], bool] = {}

    def script(self, version: Version, range_text: str, result: bool) -> None:
        """Registers the scripted satisfaction result for a candidate version and range text."""
        self._scripted[(_version_key(version), range_text)] = result

    def parse_range(self, text: str) -> VersionRange:
        """Records the range text and returns a VersionRange carrying its trimmed text."""
        self.parse_range_calls.append(text)
        return VersionRange(text.strip())

    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        """Records the satisfaction request and returns the scripted outcome (default False)."""
        self.satisfaction_calls.append((version, range_constraint.raw_text, include_prerelease))
        return self._scripted.get((_version_key(version), range_constraint.raw_text), False)


class PackageRepositoryTest(unittest.TestCase):
    """Verifies publication storage contracts of the system-tier PackageRepository singleton."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_core = MockVersionEngine()
        self.registry.register_instance(
            self.mock_core,
            keys=[CoreVersionEngine],
            tier=system,
        )

    def test_register_package_and_get_releases_descending(self) -> None:
        """POSTCONDITION repo.descending_releases: releases are ordered by precedence descending."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
            repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
            repository.register_package(PackageRelease("alpha", Version(1, 5, 0)))
            releases = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in releases],
                [Version(2, 0, 0), Version(1, 5, 0), Version(1, 0, 0)],
            )
            self.assertTrue(len(self.mock_core.compare_calls) > 0)

    def test_get_releases_preserves_declared_dependencies(self) -> None:
        """POSTCONDITION repo.register_release: dependency requirements are stored with the release."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            dependency = PackageDependency("beta", VersionRange(">=1.0.0"))
            repository.register_package(PackageRelease("alpha", Version(2, 0, 0), (dependency,)))
            releases = repository.get_releases("alpha")
            self.assertEqual(len(releases), 1)
            self.assertEqual(releases[0].name, "alpha")
            self.assertEqual(releases[0].dependencies, (dependency,))

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITION repo.descending_releases: the stored release list is not exposed directly."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
            releases = repository.get_releases("alpha")
            releases.append(PackageRelease("alpha", Version(9, 0, 0)))
            self.assertEqual(len(repository.get_releases("alpha")), 1)

    def test_get_releases_missing_package_raises(self) -> None:
        """PRECONDITION repo.missing_package: unknown package names MUST raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as context:
                repository.get_releases("ghost")
            self.assertEqual(context.exception.package_name, "ghost")
            self.assertIsInstance(context.exception, SemVerError)

    def test_has_package_and_all_packages(self) -> None:
        """POSTCONDITIONS repo.has_membership and repo.all_names: membership and name set are reflected."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("alpha"))
            self.assertEqual(repository.all_packages(), set())
            repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
            repository.register_package(PackageRelease("beta", Version(1, 0, 0)))
            self.assertTrue(repository.has_package("alpha"))
            self.assertTrue(repository.has_package("beta"))
            self.assertFalse(repository.has_package("gamma"))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})


class DependencySolverTest(unittest.TestCase):
    """Verifies resolution contracts of the system-tier DependencySolver singleton."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_core = MockVersionEngine()
        self.registry.register_instance(
            self.mock_core,
            keys=[CoreVersionEngine],
            tier=system,
        )
        self.mock_range = MockRangeEngine()
        self.registry.register_instance(
            self.mock_range,
            keys=[CoreRangeEngine],
            tier=system,
        )

    def test_resolve_selects_highest_precedence_release(self) -> None:
        """POSTCONDITIONS solver.compatible_assignment, solver.highest_precedence: highest release is selected."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(PackageRelease("lib", Version(2, 0, 0)))
            self.mock_range.script(Version(1, 0, 0), ">=1.0.0", True)
            self.mock_range.script(Version(2, 0, 0), ">=1.0.0", True)
            outcome = solver.resolve([PackageDependency("lib", VersionRange(">=1.0.0"))])
            self.assertEqual(dict(outcome.selected_versions), {"lib": Version(2, 0, 0)})
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertTrue(len(outcome.derivation_steps) > 0)
            self.assertTrue(
                any(
                    call[0] == Version(2, 0, 0) and call[1] == ">=1.0.0"
                    for call in self.mock_range.satisfaction_calls
                )
            )

    def test_resolve_transitive_dependency(self) -> None:
        """POSTCONDITION solver.compatible_assignment: transitive requirements are satisfied together."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(PackageRelease("lib", Version(2, 0, 0)))
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("lib", VersionRange(">=1.0.0")),),
                )
            )
            self.mock_range.script(Version(1, 0, 0), "1.0.0", True)
            self.mock_range.script(Version(1, 0, 0), ">=1.0.0", True)
            self.mock_range.script(Version(2, 0, 0), ">=1.0.0", True)
            outcome = solver.resolve([PackageDependency("app", VersionRange("1.0.0"))])
            self.assertEqual(
                dict(outcome.selected_versions),
                {"app": Version(1, 0, 0), "lib": Version(2, 0, 0)},
            )
            self.assertTrue(len(outcome.derivation_steps) >= 2)

    def test_resolve_backtracks_to_compatible_release(self) -> None:
        """POSTCONDITION solver.compatible_assignment: conflicting branches backtrack to a viable combination."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("lib", VersionRange("<2.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(2, 0, 0),
                    (PackageDependency("lib", VersionRange(">=2.0.0")),),
                )
            )
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(PackageRelease("lib", Version(2, 0, 0)))
            self.mock_range.script(Version(1, 0, 0), ">=1.0.0", True)
            self.mock_range.script(Version(2, 0, 0), ">=1.0.0", True)
            self.mock_range.script(Version(1, 0, 0), "<2.0.0", True)
            self.mock_range.script(Version(2, 0, 0), "<2.0.0", False)
            self.mock_range.script(Version(1, 0, 0), ">=2.0.0", False)
            self.mock_range.script(Version(2, 0, 0), ">=2.0.0", True)
            outcome = solver.resolve(
                [
                    PackageDependency("app", VersionRange(">=1.0.0")),
                    PackageDependency("lib", VersionRange("<2.0.0")),
                ]
            )
            self.assertEqual(
                dict(outcome.selected_versions),
                {"app": Version(1, 0, 0), "lib": Version(1, 0, 0)},
            )

    def test_resolve_rolls_back_failed_dependency_subtree(self) -> None:
        """POSTCONDITION solver.compatible_assignment: constraints from a failed candidate subtree are rolled back."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (
                        PackageDependency("extra", VersionRange(">=1.0.0")),
                        PackageDependency("lib", VersionRange(">=1.0.0")),
                    ),
                )
            )
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(2, 0, 0),
                    (
                        PackageDependency("extra", VersionRange(">=1.0.0")),
                        PackageDependency("lib", VersionRange(">=5.0.0")),
                    ),
                )
            )
            repository.register_package(PackageRelease("extra", Version(1, 0, 0)))
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            self.mock_range.script(Version(1, 0, 0), ">=1.0.0", True)
            self.mock_range.script(Version(1, 0, 0), ">=5.0.0", False)
            self.mock_range.script(Version(2, 0, 0), ">=1.0.0", True)
            outcome = solver.resolve([PackageDependency("app", VersionRange(">=1.0.0"))])
            self.assertEqual(
                dict(outcome.selected_versions),
                {
                    "app": Version(1, 0, 0),
                    "extra": Version(1, 0, 0),
                    "lib": Version(1, 0, 0),
                },
            )
            self.assertTrue(
                any(
                    call[0] == Version(1, 0, 0) and call[1] == ">=5.0.0"
                    for call in self.mock_range.satisfaction_calls
                )
            )

    def test_resolve_unsatisfiable_raises_conflict(self) -> None:
        """PRECONDITION solver.unsatisfiable_conflict: contradictory constraints MUST raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("pkg", Version(1, 0, 0)))
            repository.register_package(PackageRelease("pkg", Version(2, 0, 0)))
            self.mock_range.script(Version(1, 0, 0), "1.0.0", True)
            self.mock_range.script(Version(1, 0, 0), "2.0.0", False)
            self.mock_range.script(Version(2, 0, 0), "1.0.0", False)
            self.mock_range.script(Version(2, 0, 0), "2.0.0", True)
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve(
                    [
                        PackageDependency("pkg", VersionRange("1.0.0")),
                        PackageDependency("pkg", VersionRange("2.0.0")),
                    ]
                )
            self.assertIn("pkg", context.exception.conflicting_packages)
            self.assertIsInstance(context.exception.explanation, str)
            self.assertTrue(len(context.exception.explanation) > 0)

    def test_resolve_candidate_exhaustion_raises_conflict(self) -> None:
        """PRECONDITION solver.unsatisfiable_conflict: exhausting every candidate of a package raises a conflict."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("lib", VersionRange(">=5.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(2, 0, 0),
                    (PackageDependency("ghost", VersionRange(">=1.0.0")),),
                )
            )
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            self.mock_range.script(Version(1, 0, 0), ">=1.0.0", True)
            self.mock_range.script(Version(1, 0, 0), ">=5.0.0", False)
            self.mock_range.script(Version(2, 0, 0), ">=1.0.0", True)
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([PackageDependency("app", VersionRange(">=1.0.0"))])
            self.assertIn("app", context.exception.conflicting_packages)
            self.assertIsInstance(context.exception.explanation, str)
            self.assertTrue(len(context.exception.explanation) > 0)

    def test_resolve_missing_package_raises_conflict(self) -> None:
        """PRECONDITION solver.missing_package_conflict: missing packages MUST surface as resolution conflicts."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([PackageDependency("ghost", VersionRange(">=1.0.0"))])
            self.assertIn("ghost", context.exception.conflicting_packages)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:59:24Z
# LAST_CHANGED: 2026-11-08T12:57:11Z
# CHANGE: Resolve coverage feedback: add test_resolve_candidate_exhaustion_raises_conflict, where every candidate of the top-level 'app' package has a viable version range but its dependency subtree fails (highest candidate needs a missing 'ghost' package, lower candidate needs lib >=5.0.0 with no viable release). The search must roll back each failed subtree and, after exhausting all candidates, report a ResolutionConflictError with the involved packages. This exercises the candidate-exhaustion-under-unsatisfiable-subtree branch (missing span 189). Cleared the addressed feedback projection from the metadata block.
# COVERAGE_AUDIT: 2026-11-08T12:59:24Z
# QA_AUDIT: 2026-11-08T12:59:10Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for the semver_core_impl VersionEngine against its low-level specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from semver_solver_multi.lib.semver_core_impl import VersionEngine, __initialize__


class VersionEngineTest(unittest.TestCase):
    """Verifies parsing and precedence contracts of the system-tier VersionEngine singleton."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_valid_syntax(self) -> None:
        """POSTCONDITION parse_version.valid_syntax: valid strings yield complete Version records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ())
            self.assertFalse(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3")
            self.assertEqual(str(version), "1.2.3")

    def test_parse_version_prerelease_and_build(self) -> None:
        """POSTCONDITION parse_version.valid_syntax: dot-separated pre-release and build identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.7")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "7"))
            self.assertTrue(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3-alpha.1+build.7")
            self.assertEqual(str(version), "1.2.3-alpha.1+build.7")

    def test_parse_version_zero_components(self) -> None:
        """POSTCONDITION parse_version.valid_syntax: zero numeric components are valid SemVer."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("0.0.0")
            self.assertEqual((version.major, version.minor, version.patch), (0, 0, 0))
            self.assertFalse(version.is_prerelease)
            self.assertEqual(version.format(), "0.0.0")

    def test_parse_version_leading_zeroes_in_core_numbers(self) -> None:
        """PRECONDITION parse_version.leading_zero_grammar: leading zeroes MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("01.2.3", "1.02.3", "1.2.03", "00.0.0"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError) as context:
                        engine.parse_version(text)
                    self.assertEqual(context.exception.raw_text, text)

    def test_parse_version_leading_zeroes_in_prerelease_numbers(self) -> None:
        """PRECONDITION parse_version.leading_zero_grammar: numeric pre-release ids reject leading zeroes."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("1.2.3-01", "1.2.3-alpha.01"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError) as context:
                        engine.parse_version(text)
                    self.assertEqual(context.exception.raw_text, text)

    def test_parse_version_malformed_grammar(self) -> None:
        """PRECONDITION parse_version.leading_zero_grammar: grammar violations MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            malformed = (
                "",
                "1",
                "1.2",
                "1.2.3.4",
                "v1.2.3",
                "1.2.3-",
                "1.2.3+",
                "1..3",
                "1.2.3-alpha..1",
                "a.b.c",
            )
            for text in malformed:
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError) as context:
                        engine.parse_version(text)
                    self.assertEqual(context.exception.raw_text, text)

    def test_compare_precedence_numerical_components(self) -> None:
        """POSTCONDITION compare_precedence.numerical_components: major, minor, patch compare numerically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(Version(1, 2, 3), Version(2, 0, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 2, 3), Version(1, 3, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 3, 0), Version(1, 2, 9)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 4)), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 2, 4), Version(1, 2, 3)), 0)

    def test_compare_precedence_equal_versions(self) -> None:
        """POSTCONDITION compare_precedence.tri_state: equal precedence evaluates to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)
            self.assertEqual(engine.compare_precedence(Version(0, 0, 0), Version(0, 0, 0)), 0)

    def test_compare_precedence_normal_ranks_above_prerelease(self) -> None:
        """POSTCONDITION compare_precedence.normal_vs_prerelease: normal ranks higher than pre-release."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            normal = engine.parse_version("1.0.0")
            prerelease = engine.parse_version("1.0.0-alpha")
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)

    def test_compare_precedence_prerelease_ordering(self) -> None:
        """POSTCONDITION compare_precedence.prerelease_ordering: the SemVer 2.0.0 precedence chain."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            ordered = (
                "1.0.0-alpha",
                "1.0.0-alpha.1",
                "1.0.0-alpha.beta",
                "1.0.0-beta",
                "1.0.0-beta.2",
                "1.0.0-beta.11",
                "1.0.0-rc.1",
                "1.0.0",
            )
            versions = [engine.parse_version(text) for text in ordered]
            for lower, higher in zip(versions, versions[1:]):
                with self.subTest(lower=str(lower), higher=str(higher)):
                    self.assertLess(engine.compare_precedence(lower, higher), 0)
                    self.assertGreater(engine.compare_precedence(higher, lower), 0)

    def test_compare_precedence_numeric_ranks_below_string(self) -> None:
        """POSTCONDITION compare_precedence.prerelease_ordering: numeric pre-release ids rank below string ids."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            numeric = engine.parse_version("1.0.0-1")
            textual = engine.parse_version("1.0.0-alpha")
            self.assertLess(engine.compare_precedence(numeric, textual), 0)
            self.assertGreater(engine.compare_precedence(textual, numeric), 0)
            small = engine.parse_version("1.0.0-alpha.2")
            large = engine.parse_version("1.0.0-alpha.11")
            self.assertLess(engine.compare_precedence(small, large), 0)
            self.assertGreater(engine.compare_precedence(large, small), 0)

    def test_compare_precedence_build_metadata_ignored(self) -> None:
        """POSTCONDITION compare_precedence.build_metadata_ignored: build metadata never affects precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            left = engine.parse_version("1.0.0+build.1")
            right = engine.parse_version("1.0.0+build.2")
            self.assertEqual(left.build, ("build", "1"))
            self.assertEqual(right.build, ("build", "2"))
            self.assertEqual(engine.compare_precedence(left, right), 0)
            self.assertEqual(engine.compare_precedence(right, left), 0)
            self.assertEqual(
                engine.compare_precedence(Version(1, 0, 0, (), ("a",)), Version(1, 0, 0, (), ("b",))),
                0,
            )
            pre_left = engine.parse_version("1.0.0-alpha+x")
            pre_right = engine.parse_version("1.0.0-alpha+y")
            self.assertEqual(engine.compare_precedence(pre_left, pre_right), 0)

    def test_parse_and_compare_round_trip(self) -> None:
        """POSTCONDITION format: formatted versions re-parse into equivalent precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            original = "2.10.4-rc.2+build.9"
            parsed = engine.parse_version(original)
            self.assertEqual(parsed.format(), original)
            reparsed = engine.parse_version(parsed.format())
            self.assertEqual(engine.compare_precedence(parsed, reparsed), 0)
            self.assertEqual(reparsed, parsed)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:43:39Z
# LAST_CHANGED: 2026-11-08T12:41:44Z
# CHANGE: Resolve feedback: build metadata identifiers are dot-separated, so '1.0.0+build.1' now asserts build == ('build', '1') (and '1.0.0+build.2' -> ('build', '2')) instead of the unmandated single-identifier tuple; cleared the addressed feedback projection from the metadata block.
# COVERAGE_AUDIT: 2026-11-08T12:43:39Z
# QA_AUDIT: 2026-11-08T12:43:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for the semver_range_impl RangeEngine against its low-level specification."""

from __future__ import annotations

import unittest
from typing import List, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import Version, VersionEngine as CoreVersionEngine
from semver_solver_multi.lib.semver_range import InvalidRangeError
from semver_solver_multi.lib.semver_range_impl import RangeEngine, __initialize__


def _numeric_component(text: str) -> int:
    """Converts a numeric version component, tolerating wildcard placeholders."""
    if text.isdigit():
        return int(text)
    return 0


def _parse_version_text(text: str) -> Version:
    """Parses a version-shaped string into a Version record for mock collaborator scripting."""
    trimmed = text.strip()
    core_and_rest = trimmed.split("+", 1)
    core_and_prerelease = core_and_rest[0]
    build: Tuple[str, ...] = ()
    if len(core_and_rest) == 2:
        build = tuple(part for part in core_and_rest[1].split(".") if part)
    core_pieces = core_and_prerelease.split("-", 1)
    numeric_parts = [_numeric_component(part) for part in core_pieces[0].split(".")]
    if len(numeric_parts) < 2:
        numeric_parts.append(0)
    if len(numeric_parts) < 3:
        numeric_parts.append(0)
    prerelease: Tuple[str, ...] = ()
    if len(core_pieces) == 2:
        prerelease = tuple(part for part in core_pieces[1].split(".") if part)
    return Version(numeric_parts[0], numeric_parts[1], numeric_parts[2], prerelease, build)


def _compare_identifiers(left: str, right: str) -> int:
    """Compares two pre-release identifiers using SemVer numeric-then-ASCII rules."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        if left_value > right_value:
            return 1
        if left_value < right_value:
            return -1
        return 0
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    if left > right:
        return 1
    if left < right:
        return -1
    return 0


def _compare_versions(first: Version, second: Version) -> int:
    """Computes SemVer 2.0.0 precedence between two Version records."""
    first_core = (first.major, first.minor, first.patch)
    second_core = (second.major, second.minor, second.patch)
    if first_core > second_core:
        return 1
    if first_core < second_core:
        return -1
    first_pre = tuple(first.prerelease)
    second_pre = tuple(second.prerelease)
    if not first_pre and not second_pre:
        return 0
    if not first_pre:
        return 1
    if not second_pre:
        return -1
    for left, right in zip(first_pre, second_pre):
        comparison = _compare_identifiers(left, right)
        if comparison != 0:
            return comparison
    if len(first_pre) > len(second_pre):
        return 1
    if len(first_pre) < len(second_pre):
        return -1
    return 0


class MockVersionEngine:
    """Lightweight test double realizing the semver_core.VersionEngine collaborator protocol."""

    def __init__(self) -> None:
        self.parse_calls: List[str] = []
        self.compare_calls: List[Tuple[Version, Version]] = []

    def parse_version(self, text: str) -> Version:
        """Records the requested version text and returns the equivalent Version record."""
        self.parse_calls.append(text)
        return _parse_version_text(text)

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Records the compared pair and returns its SemVer precedence ordering."""
        self.compare_calls.append((v1, v2))
        return _compare_versions(v1, v2)


class RangeEngineTest(unittest.TestCase):
    """Verifies parsing and matching contracts of the system-tier RangeEngine singleton."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_core = MockVersionEngine()
        self.registry.register_instance(
            self.mock_core,
            keys=[CoreVersionEngine],
            tier=system,
        )

    def test_parse_range_comparator_forms(self) -> None:
        """POSTCONDITION parse_range.comparators_and_prefixes: basic comparators parse full versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for operator in ("==", "!=", "<", "<=", ">", ">="):
                with self.subTest(operator=operator):
                    parsed = engine.parse_range(operator + "1.2.3")
                    self.assertEqual(parsed.raw_text, operator + "1.2.3")
                    self.assertEqual(str(parsed), operator + "1.2.3")

    def test_parse_range_equals_alias(self) -> None:
        """POSTCONDITION parse_range.comparators_and_prefixes: bare '=' is accepted as an equality comparator."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("=1.2.3")
            self.assertIn("1.2.3", parsed.raw_text)

    def test_parse_range_caret_and_tilde_prefixes(self) -> None:
        """POSTCONDITION parse_range.comparators_and_prefixes: caret and tilde prefixes accept versions and wildcards."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("^1.2.3", "~1.2.3", "^1.x", "~1.2.x", "~1.2.3+build.4"):
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertEqual(parsed.raw_text, text)

    def test_parse_range_wildcard_forms(self) -> None:
        """POSTCONDITION parse_range.comparators_and_prefixes: wildcard expressions parse across comparators."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in (">=1.x", "!=1.x", ">1.*", ">=*", "1.x", "1.*"):
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertEqual(parsed.raw_text, text)

    def test_parse_range_hyphen_ranges(self) -> None:
        """POSTCONDITION parse_range.hyphen_ranges: hyphen ranges connect full versions and wildcards."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("1.0.0 - 2.x", "1.x - 2.x", "1.0.0 - 2.0.0"):
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertEqual(parsed.raw_text, text)

    def test_parse_range_union_alternatives(self) -> None:
        """POSTCONDITION parse_range.union_alternatives: '||' separates union alternatives."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("1.0.0 || 2.0.0 || 3.0.0")
            self.assertIn("||", parsed.raw_text)
            self.assertEqual(parsed.raw_text, "1.0.0 || 2.0.0 || 3.0.0")

    def test_parse_range_whitespace_trimming(self) -> None:
        """POSTCONDITION parse_range.whitespace_trimming: surrounding whitespace is trimmed from raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            self.assertEqual(engine.parse_range("  >=1.0.0  ").raw_text, ">=1.0.0")
            self.assertEqual(engine.parse_range(" >=1.0.0 || <2.0.0 ").raw_text, ">=1.0.0 || <2.0.0")

    def test_parse_range_operator_whitespace(self) -> None:
        """POSTCONDITION parse_range.operator_whitespace: operators tolerate optional following whitespace."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in (">= 1.0.0", ">= 1.x", "^ 1.2.3", "~ 1.2.x"):
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertIn("1", parsed.raw_text)

    def test_parse_range_bare_partials_raise(self) -> None:
        """PRECONDITION parse_range.bare_partials_prohibited: partial versions without wildcards MUST raise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("1", "1.2", ">1.2", "^0.0", "1.2 - 2.3", "<=1"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as context:
                        engine.parse_range(text)
                    self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_malformed_syntax_raises(self) -> None:
        """PRECONDITION parse_range.malformed_syntax: empty, whitespace, empty unions, and commas MUST raise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            malformed = (
                "",
                "   ",
                "||",
                "1.0.0 ||",
                "|| 1.0.0",
                "1.0.0 ||  || 2.0.0",
                "1.0.0, <2.0.0",
                ">=1.0.0,<2.0.0",
                "@1.0.0",
                "1.0.0 - ",
            )
            for text in malformed:
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as context:
                        engine.parse_range(text)
                    self.assertEqual(context.exception.raw_range, text)

    def test_satisfies_boolean_match(self) -> None:
        """POSTCONDITION satisfies.boolean_match: boolean True when version satisfies the range, False otherwise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">=1.0.0")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 0), constraint, False))
            self.assertTrue(len(self.mock_core.compare_calls) > 0)

    def test_satisfies_caret_range(self) -> None:
        """POSTCONDITION satisfies.boolean_match: caret ranges expand to lower/upper compatibility bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 5, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), constraint, False))

    def test_satisfies_conjunctive_clause(self) -> None:
        """POSTCONDITION satisfies.boolean_match: whitespace-delimited comparators must all hold."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 9, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), constraint, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITION satisfies.boolean_match: union alternatives match when any clause matches."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range("^1.0.0 || ^3.0.0")
            self.assertTrue(engine.satisfies(Version(1, 4, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(3, 1, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), constraint, False))

    def test_satisfies_prerelease_filtered(self) -> None:
        """POSTCONDITION satisfies.prerelease_filter: pre-releases are excluded from plain ranges by default."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(Version(1, 5, 0, ("alpha",)), constraint, False))

    def test_satisfies_prerelease_explicitly_targeted(self) -> None:
        """POSTCONDITION satisfies.prerelease_filter: a range naming the pre-release accepts that same version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range("1.5.0-alpha")
            self.assertTrue(engine.satisfies(Version(1, 5, 0, ("alpha",)), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 5, 1, ("alpha",)), constraint, False))

    def test_satisfies_prerelease_inequality_unshifted(self) -> None:
        """POSTCONDITION satisfies.prerelease_inequality: include_prerelease compares raw precedence boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(Version(1, 0, 0, ("alpha",)), constraint, True))
            self.assertTrue(engine.satisfies(Version(1, 0, 0, ("alpha",)), engine.parse_range(">=0.9.0"), True))
            self.assertTrue(engine.satisfies(Version(2, 0, 0, ("rc", "1")), constraint, True))

    def test_parse_range_malformed_wildcard_placement_raises(self) -> None:
        """PRECONDITION parse_range.malformed_syntax: wildcards followed by numeric components MUST raise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            malformed = (
                "1.x.3",
                "x.1.2",
                "1.*.2",
                "1.2.x.4",
                ">=1.x.3",
                "1.2.3.x",
                "1.2.3.*",
                ">=1.2.3.x",
            )
            for text in malformed:
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as context:
                        engine.parse_range(text)
                    self.assertEqual(context.exception.raw_range, text)

    def test_satisfies_caret_zero_major_and_wildcard_bounds(self) -> None:
        """POSTCONDITION parse_range.comparators_and_prefixes: caret upper bounds respect zero major and wildcards."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            zero_minor = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(Version(0, 2, 3), zero_minor, False))
            self.assertTrue(engine.satisfies(Version(0, 2, 9), zero_minor, False))
            self.assertFalse(engine.satisfies(Version(0, 3, 0), zero_minor, False))
            self.assertFalse(engine.satisfies(Version(0, 1, 9), zero_minor, False))
            zero_patch = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(Version(0, 0, 3), zero_patch, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 4), zero_patch, False))
            wildcard_minor = engine.parse_range("^0.x")
            self.assertTrue(engine.satisfies(Version(0, 9, 9), wildcard_minor, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), wildcard_minor, False))
            wildcard_patch = engine.parse_range("^0.0.x")
            self.assertTrue(engine.satisfies(Version(0, 0, 0), wildcard_patch, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), wildcard_patch, False))

    def test_satisfies_wildcard_relational_bounds(self) -> None:
        """POSTCONDITION parse_range.comparators_and_prefixes: wildcard relational bounds expand to inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            greater = engine.parse_range(">1.x")
            self.assertTrue(engine.satisfies(Version(2, 0, 0), greater, False))
            self.assertFalse(engine.satisfies(Version(1, 9, 9), greater, False))
            at_least = engine.parse_range(">=1.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), at_least, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), at_least, False))
            less = engine.parse_range("<1.x")
            self.assertTrue(engine.satisfies(Version(0, 9, 9), less, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), less, False))
            at_most = engine.parse_range("<=1.x")
            self.assertTrue(engine.satisfies(Version(1, 9, 9), at_most, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), at_most, False))
            minor_greater = engine.parse_range(">1.2.x")
            self.assertTrue(engine.satisfies(Version(1, 3, 0), minor_greater, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 9), minor_greater, False))

    def test_satisfies_wildcard_inequality_exclusions(self) -> None:
        """POSTCONDITION satisfies.boolean_match: '!=' wildcard and comparator inequalities exclude versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            excluded_major = engine.parse_range("!=1.x")
            self.assertTrue(engine.satisfies(Version(0, 9, 9), excluded_major, False))
            self.assertFalse(engine.satisfies(Version(1, 5, 0), excluded_major, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), excluded_major, False))
            excluded_minor = engine.parse_range("!=1.2.x")
            self.assertTrue(engine.satisfies(Version(1, 1, 0), excluded_minor, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 9), excluded_minor, False))
            self.assertTrue(engine.satisfies(Version(1, 3, 0), excluded_minor, False))
            exact = engine.parse_range("!=1.5.0")
            self.assertFalse(engine.satisfies(Version(1, 5, 0), exact, False))
            self.assertTrue(engine.satisfies(Version(1, 5, 1), exact, False))

    def test_satisfies_unsatisfiable_conjunction(self) -> None:
        """POSTCONDITION satisfies.boolean_match: contradictory comparator clauses match no version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">2.0.0 <1.0.0")
            self.assertFalse(engine.satisfies(Version(1, 5, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), constraint, False))

    def test_satisfies_universal_wildcard(self) -> None:
        """POSTCONDITION parse_range.comparators_and_prefixes: '>=*' is satisfied by all versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">=*")
            self.assertTrue(engine.satisfies(Version(0, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(9, 9, 9), constraint, False))

    def test_satisfies_caret_nonzero_major_wildcard_bound(self) -> None:
        """POSTCONDITION parse_range.comparators_and_prefixes: caret wildcard on a nonzero major bumps the major."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range("^1.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), constraint, False))
            minor_constraint = engine.parse_range("^1.2.x")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), minor_constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), minor_constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 1, 9), minor_constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), minor_constraint, False))
            star_constraint = engine.parse_range("^2.3.*")
            self.assertTrue(engine.satisfies(Version(2, 3, 0), star_constraint, False))
            self.assertTrue(engine.satisfies(Version(2, 9, 9), star_constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 2, 9), star_constraint, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), star_constraint, False))

    def test_satisfies_unsatisfiable_bare_wildcard_comparators(self) -> None:
        """POSTCONDITION satisfies.boolean_match: bare wildcard '<' and '>' comparators match no version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            greater = engine.parse_range(">*")
            self.assertFalse(engine.satisfies(Version(0, 0, 0), greater, False))
            self.assertFalse(engine.satisfies(Version(9, 9, 9), greater, False))
            less = engine.parse_range("<*")
            self.assertFalse(engine.satisfies(Version(0, 0, 0), less, False))
            self.assertFalse(engine.satisfies(Version(9, 9, 9), less, False))

    def test_satisfies_less_than_or_equal_comparator(self) -> None:
        """POSTCONDITION satisfies.boolean_match: '<=' comparator accepts the boundary and lower versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range("<=1.5.0")
            self.assertTrue(engine.satisfies(Version(1, 5, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 4, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 5, 1), constraint, False))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T13:04:08Z
# LAST_CHANGED: 2026-11-08T13:03:36Z
# CHANGE: Resolve coverage feedback: exercise two-component caret wildcard prefixes with a nonzero major. '^1.2.x' now asserts >=1.2.0 <2.0.0 (1.2.0 and 1.9.9 match; 1.1.9 and 2.0.0 do not) and '^2.3.*' asserts >=2.3.0 <3.0.0 (2.3.0 and 2.9.9 match; 2.2.9 and 3.0.0 do not), covering the caret wildcard bound branch (missing span 116). Cleared the addressed feedback projection from the metadata block.
# COVERAGE_AUDIT: 2026-11-08T13:04:08Z
# QA_AUDIT: 2026-11-08T13:03:55Z
# --- END AUTOFAB METADATA ---
