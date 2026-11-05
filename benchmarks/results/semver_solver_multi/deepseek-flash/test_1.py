# === File: dependency_solver_impl_test.py ===
"""Unit tests for dependency_solver_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_2.parts.semver_solver_multi.lib import (
    dependency_solver,
    dependency_solver_impl,
    semver_core,
    semver_range,
)


class MockVersionEngine:
    """Collaborator double implementing the semver_core.VersionEngine protocol."""

    tier = system

    def parse_version(self, text: str) -> semver_core.Version:
        without_build, _, build_text = text.partition("+")
        core_text, _, prerelease_text = without_build.partition("-")
        parts = core_text.split(".")
        return semver_core.Version(
            int(parts[0]),
            int(parts[1]),
            int(parts[2]),
            tuple(prerelease_text.split(".")) if prerelease_text else (),
            tuple(build_text.split(".")) if build_text else (),
        )

    def compare_precedence(
        self, v1: semver_core.Version, v2: semver_core.Version
    ) -> int:
        core1 = (v1.major, v1.minor, v1.patch)
        core2 = (v2.major, v2.minor, v2.patch)
        if core1 != core2:
            return -1 if core1 < core2 else 1
        return self._compare_prerelease(v1.prerelease, v2.prerelease)

    def _compare_prerelease(
        self, first: Tuple[str, ...], second: Tuple[str, ...]
    ) -> int:
        if not first and not second:
            return 0
        if not first:
            return 1
        if not second:
            return -1
        for left, right in zip(first, second):
            if left == right:
                continue
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left) < int(right) else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left < right else 1
        if len(first) == len(second):
            return 0
        return -1 if len(first) < len(second) else 1


class MockRangeEngine:
    """Collaborator double implementing the semver_range.RangeEngine protocol."""

    tier = system

    def __init__(self, version_engine: MockVersionEngine) -> None:
        self.version_engine = version_engine
        self.satisfaction_calls = 0

    def parse_range(self, text: str) -> semver_range.VersionRange:
        return semver_range.VersionRange(text)

    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        self.satisfaction_calls += 1
        clauses = [clause.strip() for clause in range_constraint.raw_text.split("||")]
        return any(self._matches_clause(version, clause) for clause in clauses)

    def _matches_clause(
        self, version: semver_core.Version, clause: str
    ) -> bool:
        return all(self._matches_token(version, token) for token in clause.split())

    def _matches_token(
        self, version: semver_core.Version, token: str
    ) -> bool:
        for operator in (">=", "<=", "==", "!=", ">", "<"):
            if token.startswith(operator):
                boundary = self.version_engine.parse_version(
                    token[len(operator):].strip()
                )
                order = self.version_engine.compare_precedence(version, boundary)
                if operator == ">=":
                    return order >= 0
                if operator == "<=":
                    return order <= 0
                if operator == "==":
                    return order == 0
                if operator == "!=":
                    return order != 0
                if operator == ">":
                    return order > 0
                return order < 0
        boundary = self.version_engine.parse_version(token)
        return self.version_engine.compare_precedence(version, boundary) == 0


class DependencySolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        dependency_solver_impl.__initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.range_engine = MockRangeEngine(self.version_engine)
        self.registry.register_instance(
            self.version_engine,
            keys=[semver_core.VersionEngine],
            tier=system,
        )
        self.registry.register_instance(
            self.range_engine,
            keys=[semver_range.RangeEngine],
            tier=system,
        )

    def test_register_package_and_has_package(self) -> None:
        """POSTCONDITION: registered releases are discoverable by package name."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            release = dependency_solver.PackageRelease(
                name="alpha", version=semver_core.Version(1, 0, 0)
            )
            repository.register_package(release)
            self.assertTrue(repository.has_package("alpha"))
            self.assertFalse(repository.has_package("beta"))
            self.assertEqual(repository.all_packages(), {"alpha"})
            self.assertEqual(repository.get_releases("alpha"), [release])

    def test_all_packages_reports_registered_names(self) -> None:
        """POSTCONDITION: all_packages returns every registered package name."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha", version=semver_core.Version(1, 0, 0)
                )
            )
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="beta", version=semver_core.Version(2, 0, 0)
                )
            )
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})

    def test_get_releases_orders_descending_precedence(self) -> None:
        """POSTCONDITION: releases are ordered by version precedence descending."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha", version=semver_core.Version(1, 0, 0)
                )
            )
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha", version=semver_core.Version(2, 0, 0)
                )
            )
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha", version=semver_core.Version(1, 5, 0)
                )
            )
            versions = [
                release.version
                for release in repository.get_releases("alpha")
            ]
            self.assertEqual(
                versions,
                [
                    semver_core.Version(2, 0, 0),
                    semver_core.Version(1, 5, 0),
                    semver_core.Version(1, 0, 0),
                ],
            )

    def test_get_releases_unknown_package_raises(self) -> None:
        """POSTCONDITION: WHEN a name is not registered, MUST raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            with self.assertRaises(dependency_solver.PackageNotFoundError) as raised:
                repository.get_releases("missing")
            self.assertEqual(raised.exception.package_name, "missing")

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITION: get_releases yields a shallow copy of the sorted release list."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha", version=semver_core.Version(1, 0, 0)
                )
            )
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha", version=semver_core.Version(2, 0, 0)
                )
            )
            releases = repository.get_releases("alpha")
            releases.clear()
            self.assertEqual(len(repository.get_releases("alpha")), 2)

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """POSTCONDITION: the highest precedence compatible release is selected."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            solver = scope.get_singleton(dependency_solver_impl.DependencySolver)
            for version in ((1, 0, 0), (1, 9, 0), (1, 10, 0)):
                repository.register_package(
                    dependency_solver.PackageRelease(
                        name="alpha",
                        version=semver_core.Version(*version),
                    )
                )
            root = [
                dependency_solver.PackageDependency(
                    name="alpha",
                    range_constraint=semver_range.VersionRange(">=1.0.0"),
                )
            ]
            outcome = solver.resolve(root)
            self.assertEqual(
                outcome.selected_versions,
                {"alpha": semver_core.Version(1, 10, 0)},
            )
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_assigns_transitive_dependencies(self) -> None:
        """POSTCONDITION: transitive dependencies are resolved and assigned within one outcome."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            solver = scope.get_singleton(dependency_solver_impl.DependencySolver)
            beta_10 = dependency_solver.PackageRelease(
                name="beta", version=semver_core.Version(1, 0, 0)
            )
            beta_12 = dependency_solver.PackageRelease(
                name="beta", version=semver_core.Version(1, 2, 0)
            )
            repository.register_package(beta_10)
            repository.register_package(beta_12)
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha",
                    version=semver_core.Version(1, 5, 0),
                    dependencies=(
                        dependency_solver.PackageDependency(
                            name="beta",
                            range_constraint=semver_range.VersionRange(">=1.0.0"),
                        ),
                    ),
                )
            )
            root = [
                dependency_solver.PackageDependency(
                    name="alpha",
                    range_constraint=semver_range.VersionRange(">=1.0.0"),
                )
            ]
            outcome = solver.resolve(root)
            self.assertEqual(
                outcome.selected_versions,
                {
                    "alpha": semver_core.Version(1, 5, 0),
                    "beta": semver_core.Version(1, 2, 0),
                },
            )

    def test_resolve_backtracks_to_compatible_release(self) -> None:
        """POSTCONDITION: backtracking abandons a conflicting high release for a compatible one."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            solver = scope.get_singleton(dependency_solver_impl.DependencySolver)
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="beta", version=semver_core.Version(1, 0, 0)
                )
            )
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha",
                    version=semver_core.Version(2, 0, 0),
                    dependencies=(
                        dependency_solver.PackageDependency(
                            name="beta",
                            range_constraint=semver_range.VersionRange("==9.0.0"),
                        ),
                    ),
                )
            )
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha",
                    version=semver_core.Version(1, 0, 0),
                    dependencies=(
                        dependency_solver.PackageDependency(
                            name="beta",
                            range_constraint=semver_range.VersionRange(">=1.0.0"),
                        ),
                    ),
                )
            )
            root = [
                dependency_solver.PackageDependency(
                    name="alpha",
                    range_constraint=semver_range.VersionRange(">=1.0.0"),
                )
            ]
            outcome = solver.resolve(root)
            self.assertEqual(
                outcome.selected_versions,
                {
                    "alpha": semver_core.Version(1, 0, 0),
                    "beta": semver_core.Version(1, 0, 0),
                },
            )

    def test_resolve_conflicts_with_assigned_release_and_backtracks(self) -> None:
        """POSTCONDITION: a dependency on an already assigned package that violates its range triggers backtracking."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            solver = scope.get_singleton(dependency_solver_impl.DependencySolver)
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha", version=semver_core.Version(2, 0, 0)
                )
            )
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha", version=semver_core.Version(1, 0, 0)
                )
            )
            for beta_version, required_alpha in (
                ((3, 0, 0), "==1.0.0"),
                ((2, 0, 0), "==1.0.0"),
                ((1, 0, 0), ">=1.0.0"),
            ):
                repository.register_package(
                    dependency_solver.PackageRelease(
                        name="beta",
                        version=semver_core.Version(*beta_version),
                        dependencies=(
                            dependency_solver.PackageDependency(
                                name="alpha",
                                range_constraint=semver_range.VersionRange(
                                    required_alpha
                                ),
                            ),
                        ),
                    )
                )
            root = [
                dependency_solver.PackageDependency(
                    name="alpha",
                    range_constraint=semver_range.VersionRange(">=1.0.0"),
                ),
                dependency_solver.PackageDependency(
                    name="beta",
                    range_constraint=semver_range.VersionRange(">=1.0.0"),
                ),
            ]
            outcome = solver.resolve(root)
            self.assertEqual(
                outcome.selected_versions,
                {
                    "alpha": semver_core.Version(2, 0, 0),
                    "beta": semver_core.Version(1, 0, 0),
                },
            )

    def test_resolve_exhausts_every_candidate_and_raises_conflict(self) -> None:
        """POSTCONDITION: WHEN every candidate branch fails, resolve MUST raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            solver = scope.get_singleton(dependency_solver_impl.DependencySolver)
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="beta", version=semver_core.Version(1, 0, 0)
                )
            )
            for alpha_version, required_beta in (
                ((2, 0, 0), "==9.0.0"),
                ((1, 0, 0), "==8.0.0"),
            ):
                repository.register_package(
                    dependency_solver.PackageRelease(
                        name="alpha",
                        version=semver_core.Version(*alpha_version),
                        dependencies=(
                            dependency_solver.PackageDependency(
                                name="beta",
                                range_constraint=semver_range.VersionRange(
                                    required_beta
                                ),
                            ),
                        ),
                    )
                )
            root = [
                dependency_solver.PackageDependency(
                    name="alpha",
                    range_constraint=semver_range.VersionRange(">=1.0.0"),
                )
            ]
            with self.assertRaises(
                dependency_solver.ResolutionConflictError
            ) as raised:
                solver.resolve(root)
            self.assertIn("alpha", raised.exception.conflicting_packages)
            self.assertIn("beta", raised.exception.conflicting_packages)
            self.assertTrue(raised.exception.explanation)

    def test_resolve_unsatisfiable_raises_conflict(self) -> None:
        """POSTCONDITION: WHEN constraints are unsatisfiable, MUST raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(dependency_solver_impl.PackageRepository)
            solver = scope.get_singleton(dependency_solver_impl.DependencySolver)
            repository.register_package(
                dependency_solver.PackageRelease(
                    name="alpha", version=semver_core.Version(1, 0, 0)
                )
            )
            root = [
                dependency_solver.PackageDependency(
                    name="alpha",
                    range_constraint=semver_range.VersionRange(">=2.0.0"),
                )
            ]
            with self.assertRaises(
                dependency_solver.ResolutionConflictError
            ) as raised:
                solver.resolve(root)
            self.assertIn("alpha", raised.exception.conflicting_packages)
            self.assertTrue(raised.exception.explanation)

    def test_resolve_missing_package_raises_conflict(self) -> None:
        """POSTCONDITION: WHEN a package is absent, MUST raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(dependency_solver_impl.DependencySolver)
            root = [
                dependency_solver.PackageDependency(
                    name="missing",
                    range_constraint=semver_range.VersionRange(">=1.0.0"),
                )
            ]
            with self.assertRaises(
                dependency_solver.ResolutionConflictError
            ) as raised:
                solver.resolve(root)
            self.assertIn("missing", raised.exception.conflicting_packages)
            self.assertTrue(raised.exception.explanation)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:34:13Z
# LAST_CHANGED: 2026-11-05T05:32:48Z
# CHANGE: Add resolve scenarios covering conflict against an already assigned release that backtracks to a lower-precedence compatible candidate, and exhaustion of every viable candidate branch raising ResolutionConflictError with conflicting packages and explanation
# COVERAGE_AUDIT: 2026-11-05T05:34:13Z
# QA_AUDIT: 2026-11-05T05:33:38Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for semver_core_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_2.parts.semver_solver_multi.lib import semver_core, semver_core_impl


class SemverCoreImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        semver_core_impl.__initialize__(self.registry)

    def test_parse_version_full(self) -> None:
        """POSTCONDITION: a valid SemVer string parses into all five fields."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertIsInstance(version, semver_core.Version)
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))

    def test_parse_version_minimal(self) -> None:
        """POSTCONDITION: core-only versions parse with empty pre-release/build tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            version = engine.parse_version("0.0.0")
            self.assertEqual(version, semver_core.Version(0, 0, 0, (), ()))
            self.assertFalse(version.is_prerelease)

    def test_parse_version_prerelease_flag(self) -> None:
        """POSTCONDITION: parsed pre-release identifiers mark the version as a pre-release."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            version = engine.parse_version("2.0.0-rc.1")
            self.assertTrue(version.is_prerelease)

    def test_parse_version_leading_zero_major_raises(self) -> None:
        """PRECONDITION: a numeric identifier with a leading zero MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            with self.assertRaises(semver_core.InvalidVersionError) as raised:
                engine.parse_version("01.2.3")
            self.assertEqual(raised.exception.raw_text, "01.2.3")

    def test_parse_version_leading_zero_prerelease_raises(self) -> None:
        """PRECONDITION: a leading-zero numeric pre-release identifier MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            with self.assertRaises(semver_core.InvalidVersionError) as raised:
                engine.parse_version("1.0.0-01")
            self.assertEqual(raised.exception.raw_text, "1.0.0-01")

    def test_parse_version_missing_patch_raises(self) -> None:
        """PRECONDITION: partial versions violating the grammar MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            with self.assertRaises(semver_core.InvalidVersionError) as raised:
                engine.parse_version("1.2")
            self.assertEqual(raised.exception.raw_text, "1.2")

    def test_parse_version_extra_core_component_raises(self) -> None:
        """PRECONDITION: four numeric core components MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            with self.assertRaises(semver_core.InvalidVersionError) as raised:
                engine.parse_version("1.2.3.4")
            self.assertEqual(raised.exception.raw_text, "1.2.3.4")

    def test_parse_version_garbage_raises(self) -> None:
        """PRECONDITION: text outside the SemVer grammar MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            with self.assertRaises(semver_core.InvalidVersionError) as raised:
                engine.parse_version("not-a-version")
            self.assertEqual(raised.exception.raw_text, "not-a-version")

    def test_compare_precedence_numeric_core(self) -> None:
        """POSTCONDITION: major, minor, and patch compare numerically in sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            v1 = engine.parse_version("1.2.3")
            v2 = engine.parse_version("2.0.0")
            self.assertLess(engine.compare_precedence(v1, v2), 0)
            self.assertGreater(engine.compare_precedence(v2, v1), 0)
            self.assertLess(engine.compare_precedence(v1, engine.parse_version("1.10.0")), 0)
            self.assertLess(engine.compare_precedence(v1, engine.parse_version("1.2.10")), 0)

    def test_compare_precedence_equal_versions(self) -> None:
        """POSTCONDITION: identical precedence evaluates to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            v1 = engine.parse_version("1.2.3")
            v2 = engine.parse_version("1.2.3")
            self.assertEqual(engine.compare_precedence(v1, v2), 0)

    def test_compare_precedence_normal_outranks_prerelease(self) -> None:
        """POSTCONDITION: a normal version outranks a pre-release sharing its core numbers."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            release = engine.parse_version("1.0.0")
            prerelease = engine.parse_version("1.0.0-alpha")
            self.assertGreater(engine.compare_precedence(release, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, release), 0)

    def test_compare_precedence_prerelease_segments(self) -> None:
        """POSTCONDITION: pre-release segments compare in sequence with numeric/string ranking."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            alpha = engine.parse_version("1.0.0-alpha")
            alpha1 = engine.parse_version("1.0.0-alpha.1")
            beta = engine.parse_version("1.0.0-beta")
            self.assertLess(engine.compare_precedence(alpha, alpha1), 0)
            self.assertLess(engine.compare_precedence(alpha1, beta), 0)
            self.assertLess(
                engine.compare_precedence(
                    engine.parse_version("1.0.0-1"),
                    engine.parse_version("1.0.0-alpha"),
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    engine.parse_version("1.0.0-alpha.2"),
                    engine.parse_version("1.0.0-alpha.10"),
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    engine.parse_version("1.0.0-alpha.10"),
                    engine.parse_version("1.0.0-alpha.2"),
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    engine.parse_version("1.0.0-beta"),
                    engine.parse_version("1.0.0-alpha"),
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    engine.parse_version("1.0.0-alpha"),
                    engine.parse_version("1.0.0-1"),
                ),
                0,
            )

    def test_compare_precedence_equal_prerelease_sequences(self) -> None:
        """POSTCONDITION: identical pre-release sequences evaluate to zero precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            self.assertEqual(
                engine.compare_precedence(
                    engine.parse_version("1.0.0-alpha.1"),
                    engine.parse_version("1.0.0-alpha.1"),
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    engine.parse_version("1.0.0-1.2"),
                    engine.parse_version("1.0.0-1.2"),
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    engine.parse_version("1.0.0-2"),
                    engine.parse_version("1.0.0-2"),
                ),
                0,
            )

    def test_compare_precedence_longer_prerelease_ranks_higher(self) -> None:
        """POSTCONDITION: a longer pre-release sequence outranks its matching common prefix."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            short = engine.parse_version("1.0.0-alpha")
            long = engine.parse_version("1.0.0-alpha.1")
            self.assertLess(engine.compare_precedence(short, long), 0)
            self.assertGreater(engine.compare_precedence(long, short), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITION: build metadata is excluded entirely from precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_core_impl.VersionEngine)
            v1 = engine.parse_version("1.2.3+build.1")
            v2 = engine.parse_version("1.2.3+build.2")
            self.assertEqual(engine.compare_precedence(v1, v2), 0)
            self.assertEqual(engine.compare_precedence(v1, engine.parse_version("1.2.3")), 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:34:15Z
# LAST_CHANGED: 2026-11-05T05:33:16Z
# CHANGE: Add symmetric greater-than precedence cases for numeric and alphanumeric pre-release identifiers, string-over-numeric ranking, longer-sequence-first ordering, and zero-precedence cases for identical pre-release sequences and equal numeric identifiers
# COVERAGE_AUDIT: 2026-11-05T05:34:15Z
# QA_AUDIT: 2026-11-05T05:33:40Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for semver_range_impl per its grounding specification."""

from __future__ import annotations

import re
import unittest
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_2.parts.semver_solver_multi.lib import semver_core, semver_range, semver_range_impl


_SEMVER_TOKEN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class MockVersionEngine:
    """Collaborator double implementing the semver_core.VersionEngine protocol."""

    tier = system

    def parse_version(self, text: str) -> semver_core.Version:
        match = _SEMVER_TOKEN.match(text)
        if match is None:
            raise semver_core.InvalidVersionError("invalid semantic version", text)
        prerelease_text = match.group(4)
        build_text = match.group(5)
        return semver_core.Version(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            tuple(prerelease_text.split(".")) if prerelease_text else (),
            tuple(build_text.split(".")) if build_text else (),
        )

    def compare_precedence(
        self, v1: semver_core.Version, v2: semver_core.Version
    ) -> int:
        core1 = (v1.major, v1.minor, v1.patch)
        core2 = (v2.major, v2.minor, v2.patch)
        if core1 != core2:
            return -1 if core1 < core2 else 1
        return self._compare_prerelease(v1.prerelease, v2.prerelease)

    def _compare_prerelease(
        self, first: Tuple[str, ...], second: Tuple[str, ...]
    ) -> int:
        if not first and not second:
            return 0
        if not first:
            return 1
        if not second:
            return -1
        for left, right in zip(first, second):
            if left == right:
                continue
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left) < int(right) else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left < right else 1
        if len(first) == len(second):
            return 0
        return -1 if len(first) < len(second) else 1


class SemverRangeImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        semver_range_impl.__initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[semver_core.VersionEngine],
            tier=system,
        )

    def test_parse_range_basic_comparators(self) -> None:
        """POSTCONDITION: basic relational comparators parse into trimmed range records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            for text in ("==1.2.3", "=1.2.3", "!=1.2.3", "<2.0.0", "<=2.0.0", ">1.0.0", ">=1.0.0"):
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertIsInstance(parsed, semver_range.VersionRange)
                    self.assertEqual(parsed.raw_text, text)

    def test_parse_range_prefix_operators(self) -> None:
        """POSTCONDITION: caret and tilde prefix ranges parse successfully."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            for text in ("^1.2.3", "~1.2.3"):
                with self.subTest(text=text):
                    self.assertEqual(engine.parse_range(text).raw_text, text)

    def test_parse_range_wildcards(self) -> None:
        """POSTCONDITION: wildcard range forms parse successfully."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            for text in ("*", "x", "X", "1.x", "1.*", "1.2.x", "1.2.*"):
                with self.subTest(text=text):
                    self.assertEqual(engine.parse_range(text).raw_text, text)

    def test_parse_range_hyphen(self) -> None:
        """POSTCONDITION: hyphen ranges parse successfully."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            self.assertEqual(
                engine.parse_range("1.2.3 - 2.0.0").raw_text, "1.2.3 - 2.0.0"
            )

    def test_parse_range_union(self) -> None:
        """POSTCONDITION: union alternatives parse successfully."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            parsed = engine.parse_range("1.2.3 || >=2.0.0")
            self.assertIsInstance(parsed, semver_range.VersionRange)
            self.assertIn("1.2.3", parsed.raw_text)
            self.assertIn("2.0.0", parsed.raw_text)

    def test_parse_range_trims_surrounding_whitespace(self) -> None:
        """POSTCONDITION: surrounding whitespace is trimmed from the stored expression."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            self.assertEqual(engine.parse_range("   >=1.0.0   ").raw_text, ">=1.0.0")

    def test_parse_range_accepts_operator_whitespace(self) -> None:
        """POSTCONDITION: optional whitespace between operator and version is accepted."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            parsed = engine.parse_range(">= 1.0.0")
            self.assertIn("1.0.0", parsed.raw_text)

    def test_parse_range_empty_raises(self) -> None:
        """PRECONDITION: empty or whitespace-only text MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            for text in ("", "   "):
                with self.subTest(text=text):
                    with self.assertRaises(semver_range.InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_comma_delimiter_raises(self) -> None:
        """PRECONDITION: comma-delimited comparators MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            text = ">=1.0.0, <2.0.0"
            with self.assertRaises(semver_range.InvalidRangeError) as raised:
                engine.parse_range(text)
            self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_bare_partial_raises(self) -> None:
        """PRECONDITION: bare partial versions lacking wildcards MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            for text in ("1", "1.2", "^0.0"):
                with self.subTest(text=text):
                    with self.assertRaises(semver_range.InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_bare_partial_hyphen_raises(self) -> None:
        """PRECONDITION: hyphen ranges with bare partial versions MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            text = "1.2 - 2.3"
            with self.assertRaises(semver_range.InvalidRangeError) as raised:
                engine.parse_range(text)
            self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_empty_union_clause_raises(self) -> None:
        """PRECONDITION: empty union clauses MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            for text in (">=1.0.0 ||", "|| >=1.0.0", ">=1.0.0 || || <2.0.0"):
                with self.subTest(text=text):
                    with self.assertRaises(semver_range.InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_satisfies_exact_comparator(self) -> None:
        """POSTCONDITION: equality constraints match only the exact version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range("==1.2.3")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 3), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 4), constraint, False)
            )

    def test_satisfies_bounded_intersection(self) -> None:
        """POSTCONDITION: conjunctive comparators require every boundary to hold."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range(">=1.2.3 <2.0.0")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 3), constraint, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 9, 9), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(2, 0, 0), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 2), constraint, False)
            )

    def test_satisfies_caret(self) -> None:
        """POSTCONDITION: caret ranges expand to compatible same-major boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range("^1.2.3")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 3), constraint, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 9, 0), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(2, 0, 0), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 2), constraint, False)
            )

    def test_satisfies_tilde(self) -> None:
        """POSTCONDITION: tilde ranges expand to the same minor version band."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range("~1.2.3")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 3), constraint, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 9), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 3, 0), constraint, False)
            )

    def test_satisfies_wildcard(self) -> None:
        """POSTCONDITION: wildcard ranges accept versions within the wildcard band."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range("1.2.x")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 5), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 3, 0), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(2, 0, 0), constraint, False)
            )

    def test_satisfies_hyphen(self) -> None:
        """POSTCONDITION: hyphen ranges include both endpoints of the interval."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range("1.2.3 - 2.0.0")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 5, 0), constraint, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(2, 0, 0), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(2, 0, 1), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 2), constraint, False)
            )

    def test_satisfies_union(self) -> None:
        """POSTCONDITION: union alternatives satisfy when any clause matches."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range("1.2.3 || >=2.0.0")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 3), constraint, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(2, 5, 0), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 5, 0), constraint, False)
            )

    def test_satisfies_not_equal_comparator(self) -> None:
        """POSTCONDITION: inequality constraints reject only the excluded version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range("!=1.2.3")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 4), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 3), constraint, False)
            )

    def test_satisfies_prerelease_excluded_by_default(self) -> None:
        """POSTCONDITION: prereleases are filtered out unless the range targets them."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range(">=1.0.0")
            self.assertFalse(
                engine.satisfies(
                    semver_core.Version(1, 5, 0, ("beta",)), constraint, False
                )
            )

    def test_satisfies_prerelease_explicit_target(self) -> None:
        """POSTCONDITION: a range naming a prerelease accepts that exact prerelease."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range(">=1.5.0-beta")
            self.assertTrue(
                engine.satisfies(
                    semver_core.Version(1, 5, 0, ("beta",)), constraint, False
                )
            )

    def test_satisfies_include_prerelease_true(self) -> None:
        """POSTCONDITION: include_prerelease compares prereleases against numeric boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            lower = engine.parse_range(">=1.0.0")
            self.assertFalse(
                engine.satisfies(
                    semver_core.Version(1, 0, 0, ("alpha",)), lower, True
                )
            )
            self.assertTrue(
                engine.satisfies(
                    semver_core.Version(1, 5, 0, ("beta",)), lower, True
                )
            )
            above = engine.parse_range(">=0.9.0")
            self.assertTrue(
                engine.satisfies(
                    semver_core.Version(1, 0, 0, ("alpha",)), above, True
                )
            )

    def test_satisfies_caret_zero_major_boundaries(self) -> None:
        """POSTCONDITION: caret on zero-major versions uses the first non-zero component as its upper boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            minor_band = engine.parse_range("^0.2.3")
            self.assertTrue(
                engine.satisfies(semver_core.Version(0, 2, 3), minor_band, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(0, 2, 9), minor_band, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(0, 3, 0), minor_band, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(0, 2, 2), minor_band, False)
            )
            patch_band = engine.parse_range("^0.0.3")
            self.assertTrue(
                engine.satisfies(semver_core.Version(0, 0, 3), patch_band, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(0, 0, 4), patch_band, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(0, 0, 2), patch_band, False)
            )

    def test_satisfies_greater_than_comparator(self) -> None:
        """POSTCONDITION: a strict '>' comparator matches only versions above its boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            constraint = engine.parse_range(">1.2.3")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 4), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 3), constraint, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 2), constraint, False)
            )

    def test_parse_range_invalid_version_token_raises(self) -> None:
        """PRECONDITION: grammar-violating version tokens MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            for text in (
                ">=not-a-version",
                ">=1.2.3.4",
                "^1.2.3.4",
                "1.2.3 - not-a-version",
            ):
                with self.subTest(text=text):
                    with self.assertRaises(semver_range.InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_rejects_invalid_identifier_tokens(self) -> None:
        """PRECONDITION: complete versions with grammar-invalid identifiers MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            for text in (">=1.2.3-alpha_1", ">=1.2.3+build_1"):
                with self.subTest(text=text):
                    with self.assertRaises(semver_range.InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_build_metadata_matches_by_precedence(self) -> None:
        """POSTCONDITION: build metadata is parsed in ranges but excluded from precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            lower = engine.parse_range(">=1.2.3+build.5")
            self.assertIsInstance(lower, semver_range.VersionRange)
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 3), lower, False)
            )
            self.assertTrue(
                engine.satisfies(
                    semver_core.Version(1, 2, 4, (), ("build", "9")), lower, False
                )
            )
            exact = engine.parse_range("==1.2.3+abc")
            self.assertTrue(
                engine.satisfies(
                    semver_core.Version(1, 2, 3, (), ("xyz",)), exact, False
                )
            )

    def test_parse_range_trailing_plus_raises(self) -> None:
        """PRECONDITION: a version token supplying '+' with no build identifiers MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            text = ">=1.2.3+"
            with self.assertRaises(semver_range.InvalidRangeError) as raised:
                engine.parse_range(text)
            self.assertEqual(raised.exception.raw_range, text)

    def test_satisfies_caret_wildcard_partials(self) -> None:
        """POSTCONDITION: caret applied to wildcard partials expands around the first non-zero major."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            non_zero_major = engine.parse_range("^1.x")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 0, 0), non_zero_major, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 9, 9), non_zero_major, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(2, 0, 0), non_zero_major, False)
            )
            zero_major = engine.parse_range("^0.x")
            self.assertTrue(
                engine.satisfies(semver_core.Version(0, 0, 0), zero_major, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(0, 9, 9), zero_major, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 0, 0), zero_major, False)
            )

    def test_satisfies_relational_wildcard_bands(self) -> None:
        """POSTCONDITION: relational comparators treat wildcard partials as half-open version bands."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            at_least = engine.parse_range(">=1.2.x")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 0), at_least, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 3, 0), at_least, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 1, 9), at_least, False)
            )
            above = engine.parse_range(">1.2.x")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 3, 0), above, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 9), above, False)
            )
            below = engine.parse_range("<1.2.x")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 1, 9), below, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 5), below, False)
            )
            at_most = engine.parse_range("<=1.2.x")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 2, 9), at_most, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 3, 0), at_most, False)
            )
            not_equal = engine.parse_range("!=1.2.x")
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 1, 9), not_equal, False)
            )
            self.assertTrue(
                engine.satisfies(semver_core.Version(1, 3, 0), not_equal, False)
            )
            self.assertFalse(
                engine.satisfies(semver_core.Version(1, 2, 5), not_equal, False)
            )

    def test_satisfies_relational_bare_wildcard(self) -> None:
        """POSTCONDITION: relational bare wildcards are accepted; only unbounded forms match versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(semver_range_impl.RangeEngine)
            candidate = semver_core.Version(4, 5, 6)
            self.assertTrue(engine.satisfies(candidate, engine.parse_range(">=*"), False))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range("<=*"), False))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range(">*"), False))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range("<*"), False))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:39:02Z
# LAST_CHANGED: 2026-11-05T05:38:34Z
# CHANGE: Add parse_range scenario asserting complete major.minor.patch tokens with grammar-invalid pre-release or build identifiers raise InvalidRangeError with raw_range preserved
# COVERAGE_AUDIT: 2026-11-05T05:39:02Z
# QA_AUDIT: 2026-11-05T05:38:48Z
# --- END AUTOFAB METADATA ---
