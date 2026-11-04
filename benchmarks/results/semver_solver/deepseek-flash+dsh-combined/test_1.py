"""Unit tests for semver_solver_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import cast

# The part package is rooted at the shared ``parts`` directory; expose it so the
# companion ``semver_solver`` package resolves under its canonical package path.
_PARTS_ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, _PARTS_ROOT)

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver.lib.semver_solver import (
    PackageDependency,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
)
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


def _release(
    name: str,
    version: Version,
    dependencies: tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Builds an immutable package release fixture for repository and solver tests."""
    return PackageRelease(name=name, version=version, dependencies=dependencies)


class VersionEngineTest(unittest.TestCase):
    registry: LifecycleRegistry

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_basic(self) -> None:
        """POSTCONDITIONS: valid SemVer text yields numeric components and empty tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("1.2.3")
        self.assertEqual(parsed, Version(1, 2, 3))
        self.assertFalse(parsed.is_prerelease)
        self.assertEqual(parsed.prerelease, ())
        self.assertEqual(parsed.build, ())
        self.assertEqual(parsed.format(), "1.2.3")
        self.assertEqual(str(parsed), "1.2.3")

    def test_parse_version_prerelease_and_build(self) -> None:
        """POSTCONDITIONS: prerelease and build metadata are split into ordered tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual(parsed, Version(1, 2, 3, ("alpha", "1"), ("build", "5")))
        self.assertTrue(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "1.2.3-alpha.1+build.5")

    def test_parse_version_zero_release(self) -> None:
        """POSTCONDITIONS: zero-valued numeric components are accepted without leading zeros."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("0.0.0")
        self.assertEqual(parsed, Version(0, 0, 0))
        self.assertFalse(parsed.is_prerelease)

    def test_compare_precedence_numeric_components(self) -> None:
        """POSTCONDITIONS: major, minor, and patch compare numerically in sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 2, 0), Version(1, 10, 0)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 0, 0), Version(1, 0, 1)), 0)
            self.assertEqual(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)

    def test_compare_precedence_normal_ranks_above_prerelease(self) -> None:
        """POSTCONDITIONS: a normal version outranks its prerelease counterpart."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            normal = Version(1, 0, 0)
            prerelease = Version(1, 0, 0, ("alpha",))
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)

    def test_compare_precedence_prerelease_segments(self) -> None:
        """POSTCONDITIONS: prerelease segments compare numerically, ASCII, and by length."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            numeric_a = Version(1, 0, 0, ("alpha", "2"))
            numeric_b = Version(1, 0, 0, ("alpha", "10"))
            self.assertLess(engine.compare_precedence(numeric_a, numeric_b), 0)
            numeric = Version(1, 0, 0, ("alpha", "1"))
            text = Version(1, 0, 0, ("alpha", "beta"))
            self.assertLess(engine.compare_precedence(numeric, text), 0)
            self.assertGreater(engine.compare_precedence(text, numeric), 0)
            self.assertLess(
                engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))),
                0,
            )
            longer = Version(1, 0, 0, ("alpha", "1"))
            prefix = Version(1, 0, 0, ("alpha",))
            self.assertLess(engine.compare_precedence(prefix, longer), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: build metadata is excluded entirely from precedence comparison."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(Version(1, 0, 0, (), ("build.1",)), Version(1, 0, 0, (), ("build.2",))),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha",), ("x",)),
                    Version(1, 0, 0, ("alpha",), ("y",)),
                ),
                0,
            )

    def test_parse_range_preserves_trimmed_text(self) -> None:
        """POSTCONDITIONS: surrounding whitespace is trimmed into raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            plain = engine.parse_range(">=1.0.0")
            padded = engine.parse_range("  >=1.0.0  ")
        self.assertEqual(plain.raw_text, ">=1.0.0")
        self.assertEqual(padded.raw_text, ">=1.0.0")
        self.assertEqual(str(plain), plain.raw_text)

    def test_parse_range_accepts_operator_whitespace(self) -> None:
        """POSTCONDITIONS: optional whitespace between operator and version is accepted."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            spaced = engine.parse_range(">= 1.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), spaced, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 0), spaced, False))

    def test_satisfies_basic_comparators(self) -> None:
        """POSTCONDITIONS: relational comparators evaluate by precedence ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            ge = engine.parse_range(">=1.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), ge, False))
            self.assertTrue(engine.satisfies(Version(2, 5, 0), ge, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), ge, False))
            lt = engine.parse_range("<2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 9, 9), lt, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), lt, False))
            eq = engine.parse_range("==1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), eq, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), eq, False))
            ne = engine.parse_range("!=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 4), ne, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 3), ne, False))

    def test_satisfies_single_equals_comparator(self) -> None:
        """POSTCONDITIONS: single '=' comparator is accepted as equality."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            eq = engine.parse_range("= 1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), eq, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), eq, False))

    def test_satisfies_le_and_gt_comparators(self) -> None:
        """POSTCONDITIONS: '<=' and '>' comparators evaluate by precedence ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            le = engine.parse_range("<=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), le, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 2), le, False))
            self.assertTrue(engine.satisfies(Version(0, 9, 0), le, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), le, False))
            gt = engine.parse_range(">1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 4), gt, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), gt, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 3), gt, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), gt, False))

    def test_satisfies_bare_complete_version_as_equality(self) -> None:
        """POSTCONDITIONS: a bare complete version parses and matches exact equality."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            bare = engine.parse_range("1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), bare, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), bare, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), bare, False))

    def test_satisfies_caret_ranges(self) -> None:
        """POSTCONDITIONS: caret ranges expand from the first non-zero component boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            major = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), major, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), major, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), major, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), major, False))
            minor = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(Version(0, 2, 9), minor, False))
            self.assertFalse(engine.satisfies(Version(0, 3, 0), minor, False))
            patch = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(Version(0, 0, 3), patch, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 4), patch, False))

    def test_satisfies_tilde_ranges(self) -> None:
        """POSTCONDITIONS: tilde ranges expand into lower and upper minor boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            tilde = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), tilde, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), tilde, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), tilde, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), tilde, False))

    def test_satisfies_wildcard_ranges(self) -> None:
        """POSTCONDITIONS: wildcard ranges match any version within the specified prefix."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            patch_wild = engine.parse_range("1.2.x")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), patch_wild, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), patch_wild, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), patch_wild, False))
            minor_wild = engine.parse_range("1.*")
            self.assertTrue(engine.satisfies(Version(1, 9, 9), minor_wild, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), minor_wild, False))
            star = engine.parse_range("*")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), star, False))

    def test_satisfies_hyphen_ranges(self) -> None:
        """POSTCONDITIONS: hyphen ranges normalize into inclusive paired comparators."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            hyphen = engine.parse_range("1.0.0 - 2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), hyphen, False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), hyphen, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), hyphen, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 1), hyphen, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), hyphen, False))

    def test_satisfies_union_ranges(self) -> None:
        """POSTCONDITIONS: a version satisfies the range when any union clause matches."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            union = engine.parse_range(">=2.0.0 || <1.0.0")
            self.assertTrue(engine.satisfies(Version(2, 1, 0), union, False))
            self.assertTrue(engine.satisfies(Version(0, 9, 0), union, False))
            self.assertFalse(engine.satisfies(Version(1, 5, 0), union, False))

    def test_satisfies_filters_prereleases_by_default(self) -> None:
        """POSTCONDITIONS: prereleases are filtered unless the range targets the same release."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            plain = engine.parse_range(">=1.0.0")
            targeted = engine.parse_range(">=1.0.0-alpha")
            candidate = Version(1, 0, 0, ("alpha",))
            self.assertFalse(engine.satisfies(candidate, plain, False))
            self.assertTrue(engine.satisfies(candidate, targeted, False))
            other_patch = Version(1, 0, 1, ("alpha",))
            self.assertFalse(engine.satisfies(other_patch, targeted, False))

    def test_satisfies_prerelease_direct_comparison_when_included(self) -> None:
        """POSTCONDITIONS: include_prerelease uses precedence without shifting numeric bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            plain = engine.parse_range(">=1.0.0")
            targeted = engine.parse_range(">=1.0.0-alpha")
            candidate = Version(1, 0, 0, ("alpha",))
            self.assertFalse(engine.satisfies(candidate, plain, True))
            self.assertTrue(engine.satisfies(candidate, targeted, True))


class PackageRepositoryTest(unittest.TestCase):
    registry: LifecycleRegistry

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_register_and_get_releases_sorted_descending(self) -> None:
        """POSTCONDITIONS: releases are indexed per package and ordered by descending precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_release("alpha", Version(1, 0, 0)))
            repository.register_package(_release("alpha", Version(2, 0, 0)))
            repository.register_package(_release("alpha", Version(1, 5, 0)))
            releases = repository.get_releases("alpha")
        self.assertEqual(
            [release.version for release in releases],
            [Version(2, 0, 0), Version(1, 5, 0), Version(1, 0, 0)],
        )
        self.assertEqual([release.name for release in releases], ["alpha", "alpha", "alpha"])

    def test_register_package_preserves_dependencies(self) -> None:
        """POSTCONDITIONS: declared dependencies are retained on registered release records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            dependency = PackageDependency(name="beta", range_constraint=engine.parse_range("^1.0.0"))
            repository.register_package(_release("alpha", Version(1, 0, 0), (dependency,)))
            releases = repository.get_releases("alpha")
        self.assertEqual(releases[0].dependencies, (dependency,))
        self.assertEqual(releases[0].dependencies[0].name, "beta")

    def test_has_package_reflects_registration(self) -> None:
        """POSTCONDITIONS: membership reflects package names registered in the repository."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("alpha"))
            repository.register_package(_release("alpha", Version(1, 0, 0)))
            self.assertTrue(repository.has_package("alpha"))
            self.assertFalse(repository.has_package("beta"))

    def test_all_packages_returns_registered_names(self) -> None:
        """POSTCONDITIONS: the set of all registered package names is produced."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_release("alpha", Version(1, 0, 0)))
            repository.register_package(_release("beta", Version(3, 2, 1)))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITIONS: mutation of the returned list does not alter stored releases."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_release("alpha", Version(1, 0, 0)))
            first = repository.get_releases("alpha")
            first.clear()
            second = repository.get_releases("alpha")
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0].version, Version(1, 0, 0))


class DependencySolverTest(unittest.TestCase):
    registry: LifecycleRegistry

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """POSTCONDITIONS: the highest compatible precedence version is selected per package."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(_release("alpha", Version(1, 0, 0)))
            repository.register_package(_release("alpha", Version(1, 5, 0)))
            repository.register_package(_release("alpha", Version(2, 0, 0)))
            outcome = solver.resolve(
                [PackageDependency(name="alpha", range_constraint=engine.parse_range(">=1.0.0"))]
            )
        self.assertIsInstance(outcome, ResolutionOutcome)
        self.assertEqual(dict(outcome.selected_versions), {"alpha": Version(2, 0, 0)})
        self.assertIsInstance(outcome.derivation_steps, tuple)
        self.assertGreaterEqual(len(outcome.derivation_steps), 1)
        self.assertTrue(all(isinstance(step, str) for step in outcome.derivation_steps))

    def test_resolve_merges_duplicate_package_constraints(self) -> None:
        """POSTCONDITIONS: all accumulated constraints on a package must be satisfied."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(_release("alpha", Version(1, 0, 0)))
            repository.register_package(_release("alpha", Version(1, 5, 0)))
            repository.register_package(_release("alpha", Version(2, 0, 0)))
            outcome = solver.resolve(
                [
                    PackageDependency(name="alpha", range_constraint=engine.parse_range(">=1.0.0")),
                    PackageDependency(name="alpha", range_constraint=engine.parse_range("<2.0.0")),
                ]
            )
        self.assertEqual(dict(outcome.selected_versions), {"alpha": Version(1, 5, 0)})

    def test_resolve_transitive_dependencies(self) -> None:
        """POSTCONDITIONS: transitive requirements are merged into the compatible assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            beta_range = engine.parse_range(">=1.0.0")
            repository.register_package(_release("alpha", Version(1, 0, 0), (PackageDependency("beta", beta_range),)))
            repository.register_package(_release("beta", Version(1, 0, 0)))
            repository.register_package(_release("beta", Version(2, 0, 0)))
            outcome = solver.resolve(
                [PackageDependency(name="alpha", range_constraint=engine.parse_range(">=1.0.0"))]
            )
        self.assertEqual(
            dict(outcome.selected_versions),
            {"alpha": Version(1, 0, 0), "beta": Version(2, 0, 0)},
        )

    def test_resolve_backtracks_on_conflicting_candidate(self) -> None:
        """POSTCONDITIONS: conflicting candidates are abandoned to find a compatible assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release(
                    "alpha",
                    Version(2, 0, 0),
                    (PackageDependency("beta", engine.parse_range(">=2.0.0")),),
                )
            )
            repository.register_package(
                _release(
                    "alpha",
                    Version(1, 0, 0),
                    (PackageDependency("beta", engine.parse_range(">=1.0.0")),),
                )
            )
            repository.register_package(
                _release(
                    "gamma",
                    Version(1, 0, 0),
                    (PackageDependency("beta", engine.parse_range("<2.0.0")),),
                )
            )
            repository.register_package(_release("beta", Version(1, 0, 0)))
            repository.register_package(_release("beta", Version(2, 0, 0)))
            outcome = solver.resolve(
                [
                    PackageDependency(name="alpha", range_constraint=engine.parse_range(">=1.0.0")),
                    PackageDependency(name="gamma", range_constraint=engine.parse_range(">=1.0.0")),
                ]
            )
        self.assertEqual(
            dict(outcome.selected_versions),
            {"alpha": Version(1, 0, 0), "beta": Version(1, 0, 0), "gamma": Version(1, 0, 0)},
        )

    def test_resolve_raises_conflict_for_unsatisfiable_constraints(self) -> None:
        """POSTCONDITIONS: mutually unsatisfiable constraints raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(_release("alpha", Version(1, 0, 0)))
            repository.register_package(_release("alpha", Version(2, 0, 0)))
            with self.assertRaises(Exception) as caught:
                solver.resolve(
                    [
                        PackageDependency("alpha", engine.parse_range(">=2.0.0")),
                        PackageDependency("alpha", engine.parse_range("<2.0.0")),
                    ]
                )
            self.assertIsInstance(caught.exception, ResolutionConflictError)
            conflict = cast(ResolutionConflictError, caught.exception)
        self.assertIn("alpha", conflict.conflicting_packages)
        self.assertTrue(conflict.explanation)

    def test_resolve_reports_unregistered_package_as_conflict(self) -> None:
        """POSTCONDITIONS: unregistered references surface as ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(Exception) as caught:
                solver.resolve(
                    [PackageDependency("ghost", engine.parse_range(">=1.0.0"))]
                )
            self.assertIsInstance(caught.exception, ResolutionConflictError)
            conflict = cast(ResolutionConflictError, caught.exception)
        self.assertIn("ghost", conflict.conflicting_packages)
        self.assertTrue(conflict.explanation)

    def test_resolve_records_conflict_when_package_has_no_viable_releases(self) -> None:
        """POSTCONDITIONS: a package with no viable releases is recorded in the conflict trail."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(_release("alpha", Version(1, 0, 0)))
            repository.register_package(_release("alpha", Version(1, 5, 0)))
            with self.assertRaises(Exception) as caught:
                solver.resolve(
                    [PackageDependency("alpha", engine.parse_range(">=2.0.0"))]
                )
            self.assertIsInstance(caught.exception, ResolutionConflictError)
            conflict = cast(ResolutionConflictError, caught.exception)
        self.assertIn("alpha", conflict.conflicting_packages)
        self.assertTrue(conflict.explanation)

    def test_resolve_raises_conflict_when_all_candidates_exhausted(self) -> None:
        """POSTCONDITIONS: exhausting every candidate branch raises ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release(
                    "alpha",
                    Version(2, 0, 0),
                    (PackageDependency("beta", engine.parse_range(">=3.0.0")),),
                )
            )
            repository.register_package(
                _release(
                    "alpha",
                    Version(1, 0, 0),
                    (PackageDependency("beta", engine.parse_range(">=4.0.0")),),
                )
            )
            repository.register_package(_release("beta", Version(1, 0, 0)))
            repository.register_package(_release("beta", Version(2, 0, 0)))
            with self.assertRaises(Exception) as caught:
                solver.resolve(
                    [PackageDependency("alpha", engine.parse_range(">=1.0.0"))]
                )
            self.assertIsInstance(caught.exception, ResolutionConflictError)
            conflict = cast(ResolutionConflictError, caught.exception)
        self.assertTrue(conflict.conflicting_packages)
        self.assertTrue(conflict.explanation)

    def test_resolve_restores_constraints_after_failed_candidate_branch(self) -> None:
        """POSTCONDITIONS: constraints added by a failed candidate are discarded on backtrack."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release(
                    "alpha",
                    Version(2, 0, 0),
                    (PackageDependency("gamma", engine.parse_range(">=2.0.0")),),
                )
            )
            repository.register_package(_release("alpha", Version(1, 0, 0)))
            repository.register_package(_release("gamma", Version(1, 0, 0)))
            outcome = solver.resolve(
                [PackageDependency("alpha", engine.parse_range(">=1.0.0"))]
            )
        self.assertEqual(dict(outcome.selected_versions), {"alpha": Version(1, 0, 0)})


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T22:06:08Z
# LAST_CHANGED: 2026-11-04T21:56:44Z
# CHANGE: Added coverage for '<=' and '>' comparators and bare complete version ranges evaluated as exact equality. Added DependencySolver conflict scenarios asserting ResolutionConflictError reporting (conflicting_packages and explanation) for unsatisfiable constraints, unregistered packages surfaced without PackageNotFoundError escaping, no viable releases (conflict trail), every candidate branch exhausted, and constraint restoration after a failed candidate branch.
# COVERAGE_AUDIT: 2026-11-04T22:06:08Z
# QA_AUDIT: 2026-11-04T22:05:53Z
# --- END AUTOFAB METADATA ---
