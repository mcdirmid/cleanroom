"""Unit tests for semver_solver_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system
from semver_solver.lib.semver_solver import (
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionRange,
)
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


def make_version(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> Version:
    """Wraps primitive version components into an immutable domain Version record."""
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def make_range(raw_text: str) -> VersionRange:
    """Wraps a raw constraint expression into a domain VersionRange record."""
    return VersionRange(raw_text=raw_text)


def make_dependency(name: str, range_constraint: VersionRange) -> PackageDependency:
    """Wraps a package name and range into a domain PackageDependency record."""
    return PackageDependency(name=name, range_constraint=range_constraint)


def make_release(
    name: str,
    version: Version,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Wraps a package name, version, and dependency tuple into a PackageRelease record."""
    return PackageRelease(name=name, version=version, dependencies=dependencies)


class VersionEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def engine(self, scope: LifecycleScope) -> VersionEngine:
        return scope.get_singleton(VersionEngine)

    def test_parse_version_parses_full_semver(self) -> None:
        """POSTCONDITION semver.parse_version.valid_syntax: full versions yield component records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))
            plain = engine.parse_version("0.0.1")
            self.assertEqual(plain.prerelease, ())
            self.assertEqual(plain.build, ())

    def test_parse_version_parses_numeric_prerelease_and_build(self) -> None:
        """POSTCONDITION semver.parse_version.valid_syntax: numeric prerelease and build tuples preserved."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            version = engine.parse_version("1.0.0-0.beta.2+20130313144700")
            self.assertEqual(version.prerelease, ("0", "beta", "2"))
            self.assertEqual(version.build, ("20130313144700",))

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """PRECONDITION semver.parse_version.leading_zero_grammar: leading zeroes raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            for text in ["01.2.3", "1.02.3", "1.2.03", "1.2.3-01"]:
                with self.assertRaises(InvalidVersionError) as ctx:
                    engine.parse_version(text)
                self.assertEqual(ctx.exception.raw_text, text)

    def test_parse_version_rejects_malformed_syntax(self) -> None:
        """PRECONDITION semver.parse_version.leading_zero_grammar: grammar violations raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            for text in ["", "1.2", "1.2.3.4", "v1.2.3", "1.2.3-", "1.2.3+"]:
                with self.assertRaises(InvalidVersionError):
                    engine.parse_version(text)

    def test_compare_precedence_compares_numeric_components(self) -> None:
        """POSTCONDITION semver.compare_precedence.numerical_components: major/minor/patch compared numerically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            self.assertLess(engine.compare_precedence(make_version(1, 0, 0), make_version(2, 0, 0)), 0)
            self.assertGreater(engine.compare_precedence(make_version(2, 0, 0), make_version(1, 9, 9)), 0)
            self.assertLess(engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 4)), 0)
            self.assertGreater(engine.compare_precedence(make_version(1, 3, 0), make_version(1, 2, 9)), 0)
            self.assertEqual(engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 3)), 0)

    def test_compare_precedence_ranks_normal_above_prerelease(self) -> None:
        """POSTCONDITION semver.compare_precedence.normal_vs_prerelease: normal outranks prerelease."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            normal = make_version(1, 0, 0)
            prerelease = make_version(1, 0, 0, ("alpha",))
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)

    def test_compare_precedence_orders_prerelease_segments(self) -> None:
        """POSTCONDITION semver.compare_precedence.prerelease_ordering: numeric below string, longer sequence higher."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            alpha = make_version(1, 0, 0, ("alpha",))
            alpha_one = make_version(1, 0, 0, ("alpha", "1"))
            alpha_two = make_version(1, 0, 0, ("alpha", "2"))
            alpha_ten = make_version(1, 0, 0, ("alpha", "10"))
            beta = make_version(1, 0, 0, ("beta",))
            numeric = make_version(1, 0, 0, ("1",))
            self.assertLess(engine.compare_precedence(alpha, alpha_one), 0)
            self.assertGreater(engine.compare_precedence(alpha_one, alpha), 0)
            self.assertLess(engine.compare_precedence(alpha_two, alpha_ten), 0)
            self.assertGreater(engine.compare_precedence(alpha_ten, alpha_two), 0)
            self.assertLess(engine.compare_precedence(alpha, beta), 0)
            self.assertGreater(engine.compare_precedence(beta, alpha), 0)
            self.assertLess(engine.compare_precedence(numeric, alpha), 0)
            self.assertGreater(engine.compare_precedence(alpha, numeric), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITION semver.compare_precedence.build_metadata_ignored: build metadata excluded from ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            left = make_version(1, 0, 0, (), ("build", "1"))
            right = make_version(1, 0, 0, (), ("build", "2"))
            self.assertEqual(engine.compare_precedence(left, right), 0)
            self.assertLess(engine.compare_precedence(left, make_version(1, 0, 1)), 0)

    def test_parse_range_accepts_comparators_prefixes_and_wildcards(self) -> None:
        """POSTCONDITION semver.parse_range.comparators_and_prefixes: comparators, caret, tilde, wildcards parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            for text in [
                "==1.2.3",
                "=1.2.3",
                "!=1.2.3",
                "<2.0.0",
                "<=2.0.0",
                ">1.0.0",
                ">=1.0.0",
                "^1.2.3",
                "~1.2.3",
                ">=1.x",
                "!=1.x",
                ">1.*",
                "^1.x",
                "~1.2.x",
                ">=*",
            ]:
                parsed = engine.parse_range(text)
                self.assertIsInstance(parsed, VersionRange)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_accepts_wildcard_operator_forms(self) -> None:
        """POSTCONDITION semver.parse_range.comparators_and_prefixes: wildcard relational forms compile and evaluate."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            for text in ["1.x", "*", "!=*", ">*", "<*", "<=*", "<1.x", "<=1.x", "^*", "~*"]:
                parsed = engine.parse_range(text)
                self.assertIsInstance(parsed, VersionRange)
                self.assertEqual(parsed.raw_text, text)
                self.assertIsInstance(engine.satisfies(make_version(1, 2, 3), parsed, False), bool)
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), engine.parse_range("1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), engine.parse_range("1.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 9), engine.parse_range("<1.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), engine.parse_range("<1.x"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), engine.parse_range("<=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), engine.parse_range("*"), False))
            self.assertTrue(engine.satisfies(make_version(5, 0, 0), engine.parse_range("*"), False))

    def test_parse_range_caret_tilde_wildcard_boundaries(self) -> None:
        """POSTCONDITION semver.parse_range.comparators_and_prefixes: caret and tilde wildcard boundaries expand."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            for text in ["^0.0.0", "^0.x", "^0.0.x", "^*", "~*"]:
                parsed = engine.parse_range(text)
                self.assertIsInstance(parsed, VersionRange)
                self.assertEqual(parsed.raw_text, text)
                self.assertIsInstance(engine.satisfies(make_version(0, 0, 0), parsed, False), bool)
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), engine.parse_range("^0.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(0, 0, 1), engine.parse_range("^0.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(0, 5, 0), engine.parse_range("^0.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), engine.parse_range("^0.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 0, 5), engine.parse_range("^0.0.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 1, 0), engine.parse_range("^0.0.x"), False))

    def test_parse_range_trims_whitespace_and_operator_spacing(self) -> None:
        """POSTCONDITION semver.parse_range.whitespace_trimming: surrounding and clause whitespace trimmed."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            self.assertEqual(engine.parse_range("  >=1.0.0  ").raw_text, ">=1.0.0")
            self.assertEqual(engine.parse_range("  >=1.0.0 || <2.0.0  ").raw_text, ">=1.0.0 || <2.0.0")
            self.assertIsInstance(engine.parse_range(">= 1.0.0"), VersionRange)
            self.assertIsInstance(engine.parse_range(">= 1.x"), VersionRange)

    def test_parse_range_accepts_hyphen_ranges_and_unions(self) -> None:
        """POSTCONDITION semver.parse_range.hyphen_ranges/union_alternatives: compound expressions parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            for text in ["1.0.0 - 2.x", "1.x - 2.x", ">=1.0.0 || <0.5.0", "^1.0.0 || ~2.0.0"]:
                self.assertIsInstance(engine.parse_range(text), VersionRange)

    def test_parse_range_rejects_bare_partials(self) -> None:
        """PRECONDITION semver.parse_range.bare_partials_prohibited: bare partials raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            for text in ["1", "1.2", ">1.2", "^0.0", "1.2 - 2.3", "1.0.0 - 2.3"]:
                with self.assertRaises(InvalidRangeError) as ctx:
                    engine.parse_range(text)
                self.assertEqual(ctx.exception.raw_range, text)

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """PRECONDITION semver.parse_range.malformed_syntax: empty, blank, comma, or dangling unions raise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            for text in ["", "   ", ">=1.0.0 ||", "|| >=1.0.0", ">=1.0.0, <2.0.0", "^1.2.3.4", "1.x.5"]:
                with self.assertRaises(InvalidRangeError):
                    engine.parse_range(text)
            with self.assertRaises(InvalidRangeError) as ctx:
                engine.parse_range(">=1.0.0, <2.0.0")
            self.assertEqual(ctx.exception.raw_range, ">=1.0.0, <2.0.0")

    def test_satisfies_basic_comparators(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: relational comparators match by precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), make_range(">=1.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), make_range(">=1.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), make_range("<2.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("<2.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), make_range("<=2.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 1), make_range("<=2.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(1, 0, 1), make_range(">1.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), make_range(">1.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), make_range("==1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 4), make_range("==1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 4), make_range("!=1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), make_range("!=1.2.3"), False))

    def test_satisfies_wildcard_expansion(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: wildcards normalize into comparator inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), make_range(">=1.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), make_range(">=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), make_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 0), make_range("!=1.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), make_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(4, 5, 6), make_range(">=*"), False))

    def test_satisfies_caret_and_tilde_expansion(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: caret and tilde expand on component boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), make_range("^1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("^1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), make_range("^1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(0, 2, 9), make_range("^0.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(0, 3, 0), make_range("^0.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(0, 0, 3), make_range("^0.0.3"), False))
            self.assertFalse(engine.satisfies(make_version(0, 0, 4), make_range("^0.0.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), make_range("^1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("^1.x"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), make_range("~1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), make_range("~1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), make_range("~1.2.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), make_range("~1.2.x"), False))

    def test_satisfies_hyphen_range(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: hyphen ranges expand into paired inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            constraint = make_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), constraint, False))
            self.assertTrue(engine.satisfies(make_version(2, 9, 9), constraint, False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), constraint, False))
            bounded = make_range("1.0.0 - 2.0.0")
            self.assertIsInstance(engine.parse_range("1.0.0 - 2.0.0"), VersionRange)
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), bounded, False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), bounded, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 1), bounded, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), bounded, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: union matches when any clause is satisfied."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            constraint = make_range(">=2.0.0 || >=1.0.0 <1.5.0")
            self.assertTrue(engine.satisfies(make_version(2, 1, 0), constraint, False))
            self.assertTrue(engine.satisfies(make_version(1, 4, 0), constraint, False))
            self.assertFalse(engine.satisfies(make_version(1, 6, 0), constraint, False))

    def test_satisfies_filters_prerelease_when_excluded(self) -> None:
        """POSTCONDITION semver.satisfies.prerelease_filter: prereleases filtered unless include_prerelease."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            candidate = make_version(1, 0, 0, ("alpha",))
            self.assertFalse(engine.satisfies(candidate, make_range(">=0.9.0"), False))
            self.assertTrue(engine.satisfies(candidate, make_range(">=0.9.0"), True))

    def test_satisfies_explicit_prerelease_constraint(self) -> None:
        """POSTCONDITION semver.satisfies.prerelease_filter: same tuple prerelease identifiers explicitly targeted."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            constraint = make_range(">=1.0.0-alpha <1.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0, ("alpha",)), constraint, False))
            self.assertTrue(engine.satisfies(make_version(1, 0, 0, ("beta",)), constraint, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0, ("alpha",)), constraint, False))

    def test_satisfies_prerelease_inequality_with_include(self) -> None:
        """POSTCONDITION semver.satisfies.prerelease_inequality: include_prerelease keeps boundary ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self.engine(scope)
            candidate = make_version(1, 0, 0, ("alpha",))
            self.assertFalse(engine.satisfies(candidate, make_range(">=1.0.0"), True))
            self.assertTrue(engine.satisfies(candidate, make_range("<1.0.0"), True))


class PackageRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_register_package_then_get_releases_descending(self) -> None:
        """POSTCONDITION semver.repo.register_release/descending_releases: releases sorted descending."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(2, 0, 0)))
            repository.register_package(make_release("alpha", make_version(1, 5, 0)))
            releases = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in releases],
                [make_version(2, 0, 0), make_version(1, 5, 0), make_version(1, 0, 0)],
            )

    def test_get_releases_orders_prereleases_by_precedence(self) -> None:
        """POSTCONDITION semver.repo.descending_releases: prerelease ordering uses version precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0, ("alpha",))))
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(0, 9, 9)))
            releases = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in releases],
                [make_version(1, 0, 0), make_version(1, 0, 0, ("alpha",)), make_version(0, 9, 9)],
            )

    def test_get_releases_returns_defensive_copy(self) -> None:
        """POSTCONDITION semver.repo.descending_releases: caller mutation does not corrupt repository order."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(2, 0, 0)))
            first = repository.get_releases("alpha")
            first.clear()
            second = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in second],
                [make_version(2, 0, 0), make_version(1, 0, 0)],
            )

    def test_get_releases_raises_for_missing_package(self) -> None:
        """PRECONDITION semver.repo.missing_package: unknown package raises PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as ctx:
                repository.get_releases("ghost")
            self.assertEqual(ctx.exception.package_name, "ghost")

    def test_has_package_reports_membership(self) -> None:
        """POSTCONDITION semver.repo.has_membership: membership reflects registered packages only."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            self.assertTrue(repository.has_package("alpha"))
            self.assertFalse(repository.has_package("ghost"))

    def test_all_packages_reports_registered_names(self) -> None:
        """POSTCONDITION semver.repo.all_names: all registered package names are reported."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("beta", make_version(1, 0, 0)))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})

    def test_all_packages_empty_for_fresh_repository(self) -> None:
        """POSTCONDITION semver.repo.all_names: fresh repository reports no names."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertEqual(repository.all_packages(), set())


class DependencySolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_resolve_selects_highest_compatible_version(self) -> None:
        """POSTCONDITION semver.solver.compatible_assignment/highest_precedence: highest compatible wins."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(1, 5, 0)))
            repository.register_package(make_release("alpha", make_version(2, 0, 0)))
            outcome = solver.resolve([make_dependency("alpha", engine.parse_range(">=1.0.0 <2.0.0"))])
            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(outcome.selected_versions["alpha"], make_version(1, 5, 0))
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_satisfies_transitive_dependencies(self) -> None:
        """POSTCONDITION semver.solver.compatible_assignment: transitive requirements are assigned."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                make_release(
                    "alpha",
                    make_version(1, 0, 0),
                    (make_dependency("beta", make_range(">=1.0.0")),),
                )
            )
            repository.register_package(make_release("beta", make_version(1, 0, 0)))
            repository.register_package(make_release("beta", make_version(2, 0, 0)))
            outcome = solver.resolve([make_dependency("alpha", engine.parse_range(">=1.0.0"))])
            self.assertEqual(outcome.selected_versions["alpha"], make_version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["beta"], make_version(2, 0, 0))

    def test_resolve_backtracks_from_conflicting_higher_release(self) -> None:
        """POSTCONDITION semver.solver.compatible_assignment: backtracking replaces a conflicting higher release."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                make_release(
                    "alpha",
                    make_version(1, 0, 0),
                    (make_dependency("beta", make_range(">=1.0.0")),),
                )
            )
            repository.register_package(
                make_release(
                    "alpha",
                    make_version(2, 0, 0),
                    (make_dependency("beta", make_range(">=2.0.0")),),
                )
            )
            repository.register_package(make_release("beta", make_version(1, 0, 0)))
            outcome = solver.resolve(
                [
                    make_dependency("alpha", engine.parse_range(">=1.0.0")),
                    make_dependency("beta", engine.parse_range(">=1.0.0")),
                ]
            )
            self.assertEqual(outcome.selected_versions["alpha"], make_version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["beta"], make_version(1, 0, 0))

    def test_resolve_accepts_wildcard_root_range(self) -> None:
        """POSTCONDITION semver.solver.highest_precedence: wildcard ranges select the highest matching release."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(1, 9, 0)))
            repository.register_package(make_release("alpha", make_version(2, 0, 0)))
            outcome = solver.resolve([make_dependency("alpha", engine.parse_range("^1.x"))])
            self.assertEqual(outcome.selected_versions["alpha"], make_version(1, 9, 0))

    def test_resolve_raises_conflict_for_unsatisfiable_constraints(self) -> None:
        """PRECONDITION semver.solver.unsatisfiable_conflict: exhausted candidates raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(1, 5, 0)))
            with self.assertRaises(ResolutionConflictError) as ctx:
                solver.resolve([make_dependency("alpha", engine.parse_range(">=2.0.0"))])
            self.assertIn("alpha", ctx.exception.conflicting_packages)
            self.assertNotEqual(ctx.exception.explanation, "")

    def test_resolve_raises_conflict_for_unregistered_package(self) -> None:
        """PRECONDITION semver.solver.unsatisfiable_conflict: unregistered packages conflict without leaking PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as ctx:
                solver.resolve([make_dependency("missing", engine.parse_range(">=1.0.0"))])
            self.assertIn("missing", ctx.exception.conflicting_packages)
            self.assertNotEqual(ctx.exception.explanation, "")

    def test_resolve_raises_conflict_for_unsatisfiable_transitive_dependency(self) -> None:
        """PRECONDITION semver.solver.unsatisfiable_conflict: unsatisfiable transitive constraints conflict."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                make_release(
                    "alpha",
                    make_version(1, 0, 0),
                    (make_dependency("beta", make_range(">=3.0.0")),),
                )
            )
            repository.register_package(make_release("beta", make_version(1, 0, 0)))
            with self.assertRaises(ResolutionConflictError) as ctx:
                solver.resolve([make_dependency("alpha", engine.parse_range(">=1.0.0"))])
            self.assertNotEqual(ctx.exception.explanation, "")


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T05:11:42Z
# LAST_CHANGED: 2026-11-08T05:07:04Z
# CHANGE: Cover bounded wildcard less/less-equal comparators: added <1.x and <=1.x to the wildcard operator form matrix and asserted precedence bounds (<1.x satisfied by 0.9.9 but not 1.0.0; <=1.x satisfied by 1.9.9).
# COVERAGE_AUDIT: 2026-11-08T05:11:42Z
# QA_AUDIT: 2026-11-08T05:11:29Z
# --- END AUTOFAB METADATA ---
