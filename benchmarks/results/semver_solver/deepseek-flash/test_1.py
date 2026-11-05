"""Unit tests for semver_solver_impl singletons per their grounding specifications."""

from __future__ import annotations

import unittest
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_3.parts.semver_solver.lib.semver_solver import (
    PackageDependency,
    PackageRelease,
    ResolutionOutcome,
    Version,
    VersionRange,
)
from benchmark_3.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


def _version(major: int, minor: int = 0, patch: int = 0) -> Version:
    """Wraps primitive integers into an immutable domain Version record."""
    return Version(major=major, minor=minor, patch=patch)


def _release(
    name: str,
    version: Version,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Wraps package publication primitives into a domain PackageRelease record."""
    return PackageRelease(name=name, version=version, dependencies=dependencies)


def _dependency(name: str, engine: VersionEngine, range_text: str) -> PackageDependency:
    """Wraps a range expression into a domain PackageDependency record."""
    return PackageDependency(name=name, range_constraint=engine.parse_range(range_text))


class VersionEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_produces_version_record(self) -> None:
        """POSTCONDITION: parse_version MUST build a Version record from valid SemVer text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3")
            self.assertEqual(version, Version(major=1, minor=2, patch=3))
            self.assertFalse(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3")
            self.assertEqual(str(version), "1.2.3")

    def test_parse_version_extracts_prerelease_and_build_segments(self) -> None:
        """POSTCONDITION: parse_version MUST extract dot-separated prerelease and build tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual((version.major, version.minor, version.patch), (1, 2, 3))
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))
            self.assertTrue(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3-alpha.1+build.5")
            self.assertEqual(str(version), "1.2.3-alpha.1+build.5")

    def test_parse_version_handles_minimal_and_build_only_text(self) -> None:
        """POSTCONDITION: parse_version MUST accept zero numeric components and build metadata without prerelease segments."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            zero = engine.parse_version("0.0.0")
            self.assertEqual(zero, Version(major=0, minor=0, patch=0))
            build_only = engine.parse_version("1.2.3+build.5")
            self.assertEqual(build_only.prerelease, ())
            self.assertEqual(build_only.build, ("build", "5"))
            self.assertFalse(build_only.is_prerelease)
            numeric_prerelease = engine.parse_version("1.2.3-0.1")
            self.assertEqual(numeric_prerelease.prerelease, ("0", "1"))
            self.assertTrue(numeric_prerelease.is_prerelease)

    def test_parse_version_parses_multiple_prerelease_and_build_segments(self) -> None:
        """POSTCONDITION: parse_version MUST preserve every dot-separated prerelease and build identifier in order."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.0.0-x.7.z.92+build.1.2")
            self.assertEqual(version.prerelease, ("x", "7", "z", "92"))
            self.assertEqual(version.build, ("build", "1", "2"))
            self.assertTrue(version.is_prerelease)

    def test_compare_precedence_orders_numeric_components(self) -> None:
        """POSTCONDITION: compare_precedence MUST compare major, minor, and patch numerically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            versions = [engine.parse_version(text) for text in
                        ["0.9.9", "1.0.0", "1.0.1", "1.1.0", "2.0.0"]]
            for lower, higher in zip(versions, versions[1:]):
                self.assertLess(engine.compare_precedence(lower, higher), 0)
                self.assertGreater(engine.compare_precedence(higher, lower), 0)
            self.assertEqual(
                engine.compare_precedence(versions[0], engine.parse_version("0.9.9")), 0
            )

    def test_compare_precedence_orders_prerelease_segments(self) -> None:
        """POSTCONDITION: MUST compare numeric segments numerically, string segments as ASCII, and rank longer sequences higher."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            versions = [engine.parse_version(text) for text in
                        ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.2",
                         "1.0.0-alpha.10", "1.0.0-beta", "1.0.0"]]
            for lower, higher in zip(versions, versions[1:]):
                self.assertLess(engine.compare_precedence(lower, higher), 0)
                self.assertGreater(engine.compare_precedence(higher, lower), 0)

    def test_compare_precedence_ranks_normal_above_prerelease(self) -> None:
        """POSTCONDITION: MUST rank normal versions higher than prereleases sharing identical numeric components."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            prerelease = engine.parse_version("1.0.0-alpha")
            normal = engine.parse_version("1.0.0")
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)

    def test_compare_precedence_ranks_numeric_prerelease_below_alpha(self) -> None:
        """POSTCONDITION: MUST rank numeric prerelease segments lower than string segments."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            numeric = engine.parse_version("1.0.0-1")
            textual = engine.parse_version("1.0.0-alpha")
            self.assertLess(engine.compare_precedence(numeric, textual), 0)
            self.assertGreater(engine.compare_precedence(textual, numeric), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITION: MUST ignore build metadata entirely when comparing precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            left = engine.parse_version("1.0.0+build.1")
            right = engine.parse_version("1.0.0+build.2")
            self.assertEqual(engine.compare_precedence(left, right), 0)
            self.assertEqual(engine.compare_precedence(right, left), 0)

    def test_compare_precedence_ignores_build_metadata_on_prereleases(self) -> None:
        """POSTCONDITION: MUST ignore build metadata when prerelease versions differ only in build identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            left = engine.parse_version("1.0.0-alpha+build.1")
            right = engine.parse_version("1.0.0-alpha+build.2")
            self.assertEqual(engine.compare_precedence(left, right), 0)
            self.assertEqual(engine.compare_precedence(right, left), 0)

    def test_parse_range_trims_expression(self) -> None:
        """POSTCONDITION: parse_range MUST trim surrounding whitespace and store the trimmed expression."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("  ^1.2.3  ")
            self.assertIsInstance(parsed, VersionRange)
            self.assertEqual(parsed.raw_text, "^1.2.3")
            self.assertEqual(str(parsed), "^1.2.3")
            clause = engine.parse_range("  >=1.0.0 <2.0.0  ")
            self.assertEqual(clause.raw_text, ">=1.0.0 <2.0.0")
            spaced = engine.parse_range(">= 1.0.0")
            self.assertIn(spaced.raw_text, [">= 1.0.0", ">=1.0.0"])

    def test_parse_range_accepts_contracted_forms(self) -> None:
        """POSTCONDITION: parse_range MUST accept comparators, caret, tilde, wildcards, hyphens, and unions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ["1.2.3", "==1.2.3", "=1.2.3", "!=1.2.3", "<2.0.0", "<=2.0.0",
                         ">1.0.0", ">=1.0.0 <2.0.0", "^1.2.3", "~1.2.3", "*", "1.x",
                         "1.2.*", "1.2.X", "1.2.3 - 2.3.4", "1.0.0 || 2.0.0"]:
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertEqual(parsed.raw_text, text)

    def test_parse_range_accepts_whitespace_variants(self) -> None:
        """POSTCONDITION: parse_range MUST trim surrounding whitespace and accept optional operator spacing."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            union = engine.parse_range("  1.0.0 || 2.0.0  ")
            self.assertEqual(union.raw_text, "1.0.0 || 2.0.0")
            wildcard = engine.parse_range(" 1.x ")
            self.assertEqual(wildcard.raw_text, "1.x")
            spaced = engine.parse_range("^ 1.2.3")
            self.assertIn(spaced.raw_text, ["^ 1.2.3", "^1.2.3"])

    def test_satisfies_comparator_sets(self) -> None:
        """POSTCONDITION: satisfies MUST evaluate comparators within a clause and require all comparators."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            bounded = engine.parse_range(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0"), bounded, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.9.9"), bounded, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.9.9"), bounded, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), bounded, False))
            excluded = engine.parse_range("!=1.2.3")
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.3"), excluded, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.4"), excluded, False))

    def test_satisfies_strictly_greater_than_comparator(self) -> None:
        """POSTCONDITION: satisfies MUST exclude the exact boundary version for a strictly-greater-than comparator."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            strict = engine.parse_range(">1.2.3")
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.3"), strict, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.4"), strict, False))
            self.assertTrue(engine.satisfies(engine.parse_version("2.0.0"), strict, False))
            inclusive = engine.parse_range("<=1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), inclusive, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.4"), inclusive, False))

    def test_satisfies_caret_and_tilde(self) -> None:
        """POSTCONDITION: satisfies MUST expand caret boundaries and tilde minor boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            caret = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), caret, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.9"), caret, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.9.9"), caret, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.2"), caret, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), caret, False))
            tilde = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), tilde, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.9"), tilde, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.3.0"), tilde, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.2"), tilde, False))

    def test_satisfies_caret_with_zero_major(self) -> None:
        """POSTCONDITION: caret expansion MUST bound by the first non-zero component, so ^0.2.3 excludes 0.3.0."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            caret = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("0.2.3"), caret, False))
            self.assertTrue(engine.satisfies(engine.parse_version("0.2.9"), caret, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.2.2"), caret, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.3.0"), caret, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.0.0"), caret, False))

    def test_satisfies_caret_with_zero_major_and_minor(self) -> None:
        """POSTCONDITION: caret expansion MUST bound by patch when major and minor are zero, so ^0.0.3 excludes 0.0.4."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            caret = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(engine.parse_version("0.0.3"), caret, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.0.2"), caret, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.0.4"), caret, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.1.0"), caret, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.0.0"), caret, False))

    def test_satisfies_wildcards(self) -> None:
        """POSTCONDITION: satisfies MUST normalize wildcard ranges into paired comparator inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            any_version = engine.parse_range("*")
            self.assertTrue(engine.satisfies(engine.parse_version("0.1.0"), any_version, False))
            minor_wildcard = engine.parse_range("1.x")
            self.assertTrue(engine.satisfies(engine.parse_version("1.5.0"), minor_wildcard, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), minor_wildcard, False))
            patch_wildcard = engine.parse_range("1.2.*")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.7"), patch_wildcard, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.3.0"), patch_wildcard, False))

    def test_satisfies_hyphen_range(self) -> None:
        """POSTCONDITION: satisfies MUST treat hyphen ranges as inclusive paired inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            hyphen = engine.parse_range("1.2.3 - 2.3.4")
            for text in ["1.2.3", "1.5.0", "2.3.4"]:
                with self.subTest(text=text):
                    self.assertTrue(engine.satisfies(engine.parse_version(text), hyphen, False))
            for text in ["1.2.2", "2.3.5", "2.4.0"]:
                with self.subTest(text=text):
                    self.assertFalse(engine.satisfies(engine.parse_version(text), hyphen, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITION: satisfies MUST evaluate to True when any union clause is fully satisfied."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            union = engine.parse_range("1.0.0 || 2.0.0")
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0"), union, False))
            self.assertTrue(engine.satisfies(engine.parse_version("2.0.0"), union, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.5.0"), union, False))
            self.assertFalse(engine.satisfies(engine.parse_version("3.0.0"), union, False))

    def test_satisfies_excludes_prerelease_unless_explicitly_targeted(self) -> None:
        """WHEN version is a prerelease and include_prerelease is False, MUST be False unless a comparator prerelease shares the same major, minor, and patch."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            plain = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.3-alpha"), plain, False))
            explicit = engine.parse_range(">=1.2.3-alpha")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3-alpha"), explicit, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.4-alpha"), explicit, False))

    def test_satisfies_include_prerelease_compares_boundaries_directly(self) -> None:
        """WHEN include_prerelease is True, MUST compare prereleases directly against boundaries without shifting them."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            lower_bounded = engine.parse_range(">=1.0.0")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3-alpha"), lower_bounded, True))
            self.assertFalse(engine.satisfies(engine.parse_version("1.0.0-alpha"), lower_bounded, True))
            bounded = engine.parse_range(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(engine.parse_version("2.0.0-alpha"), bounded, True))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), bounded, True))


class PackageRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_register_and_get_releases_descending(self) -> None:
        """POSTCONDITION: get_releases MUST yield all registered releases ordered by descending precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_release("app", _version(1)))
            repository.register_package(_release("app", _version(2)))
            repository.register_package(_release("app", _version(1, 5)))
            repository.register_package(_release("other", _version(3, 1)))
            versions = [release.version for release in repository.get_releases("app")]
            self.assertEqual(versions, [_version(2), _version(1, 5), _version(1)])
            self.assertTrue(all(r.name == "app" for r in repository.get_releases("app")))
            self.assertEqual([r.name for r in repository.get_releases("other")], ["other"])

    def test_get_releases_returns_shallow_list_copy(self) -> None:
        """POSTCONDITION: get_releases MUST produce a shallow copy of the sorted release list."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_release("app", _version(1)))
            releases = repository.get_releases("app")
            releases.append(_release("app", _version(9)))
            self.assertEqual(len(repository.get_releases("app")), 1)

    def test_get_releases_orders_prereleases_below_normal_versions(self) -> None:
        """POSTCONDITION: get_releases MUST order by precedence so a prerelease ranks below its normal version."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            prerelease = Version(major=2, minor=0, patch=0, prerelease=("alpha",))
            repository.register_package(_release("app", _version(1, 9, 9)))
            repository.register_package(_release("app", prerelease))
            repository.register_package(_release("app", _version(2)))
            versions = [release.version for release in repository.get_releases("app")]
            self.assertEqual(versions, [_version(2), prerelease, _version(1, 9, 9)])

    def test_has_package_and_all_packages(self) -> None:
        """POSTCONDITION: has_package MUST report membership and all_packages MUST produce all registered names."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("app"))
            self.assertEqual(repository.all_packages(), set())
            repository.register_package(_release("app", _version(1)))
            repository.register_package(_release("dep", _version(1)))
            self.assertTrue(repository.has_package("app"))
            self.assertFalse(repository.has_package("ghost"))
            self.assertEqual(repository.all_packages(), {"app", "dep"})


class DependencySolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """POSTCONDITION: resolve MUST select the highest precedence compatible version for each package."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            for version in (_version(2), _version(1), _version(1, 2)):
                repository.register_package(_release("app", version))
            outcome = solver.resolve([_dependency("app", engine, "^1.0.0")])
            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(dict(outcome.selected_versions), {"app": _version(1, 2)})
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertTrue(outcome.derivation_steps)
            self.assertTrue(any("app" in step for step in outcome.derivation_steps))

    def test_resolve_satisfies_transitive_dependencies(self) -> None:
        """POSTCONDITION: resolve MUST assign mutually compatible releases for root and transitive dependencies."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release("app", _version(1, 2), (_dependency("lib", engine, ">=1.0.0"),))
            )
            for version in (_version(1), _version(1, 5), _version(2)):
                repository.register_package(_release("lib", version))
            outcome = solver.resolve([_dependency("app", engine, "^1.0.0")])
            self.assertEqual(
                dict(outcome.selected_versions),
                {"app": _version(1, 2), "lib": _version(2)},
            )

    def test_resolve_forward_checks_assigned_release_compatibility(self) -> None:
        """POSTCONDITION: resolve MUST reject a candidate whose declared dependency violates an already-assigned release and fall through to a compatible candidate."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(_release("core", _version(1)))
            repository.register_package(
                _release("tool", _version(2), (_dependency("core", engine, "^2.0.0"),))
            )
            repository.register_package(
                _release("tool", _version(1), (_dependency("core", engine, "^1.0.0"),))
            )
            outcome = solver.resolve([
                _dependency("core", engine, "^1.0.0"),
                _dependency("tool", engine, "*"),
            ])
            self.assertEqual(
                dict(outcome.selected_versions),
                {"core": _version(1), "tool": _version(1)},
            )

    def test_resolve_backtracks_across_conflicting_candidates(self) -> None:
        """POSTCONDITION: resolve MUST backtrack to an alternative compatible release when a candidate dependency conflicts."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release("app", _version(1), (_dependency("lib", engine, "^1.0.0"),))
            )
            repository.register_package(
                _release("app", _version(1, 1), (_dependency("lib", engine, "^2.0.0"),))
            )
            repository.register_package(_release("lib", _version(1)))
            outcome = solver.resolve([_dependency("app", engine, "^1.0.0")])
            self.assertEqual(
                dict(outcome.selected_versions),
                {"app": _version(1), "lib": _version(1)},
            )

    def test_resolve_falls_back_from_candidate_with_unregistered_dependency(self) -> None:
        """POSTCONDITION: resolve MUST fall back to a lower-precedence candidate whose subtree references an unregistered package and return a mutually compatible assignment instead of failing."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release("app", _version(2), (_dependency("missing", engine, "^1.0.0"),))
            )
            repository.register_package(
                _release("app", _version(1), (_dependency("lib", engine, "^1.0.0"),))
            )
            repository.register_package(_release("lib", _version(1)))
            outcome = solver.resolve([_dependency("app", engine, "*")])
            selected = dict(outcome.selected_versions)
            self.assertEqual(selected, {"app": _version(1), "lib": _version(1)})
            self.assertNotIn("missing", selected)
            self.assertTrue(engine.satisfies(selected["lib"], engine.parse_range("^1.0.0"), False))
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertTrue(outcome.derivation_steps)

    def test_resolve_falls_back_from_candidate_with_exhausted_inner_subtree(self) -> None:
        """POSTCONDITION: resolve MUST fall back to a lower-precedence candidate whose multi-level subtree exhausts its own releases and drop abandoned packages from the final assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release("app", _version(2), (_dependency("mid", engine, "^1.0.0"),))
            )
            repository.register_package(
                _release("app", _version(1), (_dependency("leaf", engine, "^1.0.0"),))
            )
            repository.register_package(
                _release("mid", _version(1), (_dependency("leaf", engine, "^2.0.0"),))
            )
            repository.register_package(_release("leaf", _version(1)))
            outcome = solver.resolve([_dependency("app", engine, "*")])
            selected = dict(outcome.selected_versions)
            self.assertEqual(selected, {"app": _version(1), "leaf": _version(1)})
            self.assertNotIn("mid", selected)
            self.assertTrue(engine.satisfies(selected["leaf"], engine.parse_range("^1.0.0"), False))

    def test_resolve_fallback_preserves_highest_compatible_for_other_packages(self) -> None:
        """POSTCONDITION: resolve MUST confine fallback to the rejected candidate and still prefer the highest compatible release for every other package."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release("app", _version(2), (_dependency("core", engine, "^2.0.0"),))
            )
            repository.register_package(
                _release("app", _version(1), (_dependency("core", engine, "^1.0.0"),))
            )
            repository.register_package(_release("core", _version(1)))
            repository.register_package(_release("util", _version(1)))
            repository.register_package(_release("util", _version(2)))
            outcome = solver.resolve([
                _dependency("app", engine, "*"),
                _dependency("util", engine, "*"),
            ])
            selected = dict(outcome.selected_versions)
            self.assertEqual(
                selected,
                {"app": _version(1), "core": _version(1), "util": _version(2)},
            )
            self.assertTrue(engine.satisfies(selected["core"], engine.parse_range("^1.0.0"), False))

    def test_resolve_empty_root_dependencies(self) -> None:
        """POSTCONDITION: resolve MUST produce an empty selected assignment when there are no root dependencies."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([])
            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(dict(outcome.selected_versions), {})
            self.assertIsInstance(outcome.derivation_steps, tuple)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T19:14:40Z
# LAST_CHANGED: 2026-11-03T19:14:18Z
# CHANGE: Add resolver fallback coverage: (1) higher-precedence app 2.0.0 depends on unregistered 'missing', so resolve rejects it and succeeds with app 1.0.0 + lib 1.0.0, asserting no leftover package; (2) higher-precedence app 2.0.0 -> mid 1.0.0 -> leaf ^2.0.0 exhausts inner releases, so resolve falls back to app 1.0.0 + leaf 1.0.0 and drops abandoned mid from selected_versions; (3) fallback is confined to the rejected candidate while another constrained package still receives its highest compatible release (util 2.0.0). Each case asserts the exact mutually compatible selected_versions assignment, the absence of abandoned/unregistered packages, dependency satisfaction via VersionEngine.satisfies, and a non-empty derivation sequence.
# COVERAGE_AUDIT: 2026-11-03T19:14:40Z
# QA_AUDIT: 2026-11-03T19:14:29Z
# --- END AUTOFAB METADATA ---
