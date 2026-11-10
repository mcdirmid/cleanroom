"""Unit tests for semver_solver_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver.lib.semver_solver import (
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    Version,
    VersionRange,
)
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


class SemverVersionEngineTest(unittest.TestCase):
    """Verifies VersionEngine parsing, precedence, range, and matching contracts."""

    def setUp(self) -> None:
        self.registry: LifecycleRegistry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_full_record(self) -> None:
        """POSTCONDITION: valid SemVer text parses into a Version with prerelease and build tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))
            self.assertTrue(version.is_prerelease)

    def test_parse_version_without_prerelease(self) -> None:
        """POSTCONDITION: minimal SemVer text parses with empty prerelease and build tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("0.0.0")
            self.assertEqual(version, Version(0, 0, 0))
            self.assertFalse(version.is_prerelease)

    def test_version_format_matches_str(self) -> None:
        """POSTCONDITION: format() produces canonical SemVer text equivalent to __str__() and round-trips."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(version.format(), "1.2.3-alpha.1+build.5")
            self.assertEqual(str(version), version.format())
            self.assertEqual(engine.parse_version(version.format()), version)

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """PRECONDITION: leading zeroes in numeric identifiers MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidVersionError) as context:
                engine.parse_version("01.2.3")
            self.assertEqual(context.exception.raw_text, "01.2.3")

    def test_parse_version_rejects_grammar_violations(self) -> None:
        """PRECONDITION: malformed SemVer grammar MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("1.2", "1.2.3.4", "abc"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError):
                        engine.parse_version(text)

    def test_compare_precedence_numeric_components(self) -> None:
        """POSTCONDITION: major, minor, and patch compare numerically with negative/zero/positive results."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 4)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 9, 9), Version(2, 0, 0)), 0)
            self.assertEqual(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)
            self.assertGreater(engine.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)), 0)

    def test_compare_precedence_prerelease_ordering(self) -> None:
        """POSTCONDITION: prerelease segments compare numerically, then ASCII-wise, with numeric below string."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1"))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "beta"))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(Version(1, 0, 0, ("alpha", "9")), Version(1, 0, 0, ("alpha", "10"))),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("alpha", "beta"))),
                0,
            )

    def test_compare_precedence_alphanumeric_outranks_numeric(self) -> None:
        """POSTCONDITION: the converse ranking holds, so an alphanumeric segment outranks a numeric segment."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(Version(1, 0, 0, ("alpha", "beta")), Version(1, 0, 0, ("alpha", "1"))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "beta"))),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(Version(1, 0, 0, ("rc",)), Version(1, 0, 0, ("2",))),
                0,
            )

    def test_compare_precedence_normal_above_prerelease(self) -> None:
        """POSTCONDITION: a normal version outranks the prerelease sharing identical numeric components."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, ("rc", "1"))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(Version(1, 0, 0, ("rc", "1")), Version(1, 0, 0)),
                0,
            )

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITION: build metadata is ignored entirely during precedence comparison."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(Version(1, 0, 0, build=("001",)), Version(1, 0, 0, build=("002",))),
                0,
            )

    def test_parse_range_trims_expression(self) -> None:
        """POSTCONDITION: surrounding whitespace is trimmed and stored in raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("   >=1.0.0   ")
            self.assertEqual(parsed.raw_text, ">=1.0.0")
            self.assertEqual(str(parsed), ">=1.0.0")

    def test_parse_range_accepts_supported_forms(self) -> None:
        """POSTCONDITION: comparators, caret, tilde, wildcard, hyphen, and union forms parse successfully."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in (
                ">=1.0.0",
                "==1.2.3",
                "=1.2.3",
                "!=1.2.3",
                "<1.2.3",
                "<=1.2.3",
                ">1.2.3",
                ">= 1.0.0",
                ">=1.x",
                "!=1.x",
                ">1.*",
                "1.x",
                "1.x.x",
                "<1.x",
                "<=1.x",
                "<=1.2.x",
                "^1.x",
                "^1.2.3",
                "^0.x",
                "^0.0.x",
                "^0.0.3",
                "~1.2.x",
                "~1.2.3",
                ">=*",
                "<*",
                ">*",
                "!=*",
                "1.0.0 - 2.x",
                "1.0.0 - 2.0.0",
                "1.x - 2.x",
                ">=1.0.0 || <0.5.0",
            ):
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertEqual(parsed.raw_text.strip(), parsed.raw_text)
                    self.assertIsInstance(parsed.raw_text, str)

    def test_parse_range_rejects_bare_partial_versions(self) -> None:
        """PRECONDITION: bare partial versions lacking wildcards MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("1", "1.2", ">1.2", "^0.0", "1.2 - 2.3"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError):
                        engine.parse_range(text)

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """PRECONDITION: empty, whitespace-only, comma-delimited, and empty-clause ranges MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("", "   ", ">=1.0.0, <2.0.0", ">=1.0.0 ||", "|| >=1.0.0"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as context:
                        engine.parse_range(text)
                    self.assertEqual(context.exception.raw_range, text)

    def test_satisfies_basic_comparators(self) -> None:
        """POSTCONDITION: a version matching all comparators in a clause satisfies the range."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = VersionRange(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 5, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), constraint, False))

    def test_satisfies_full_version_comparators(self) -> None:
        """POSTCONDITION: each relational comparator is evaluated as a satisfaction predicate on full versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            equality = VersionRange("==1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), equality, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), equality, False))
            alias_equality = VersionRange("=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), alias_equality, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), alias_equality, False))
            inequality = VersionRange("!=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 4), inequality, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 3), inequality, False))
            less_than = VersionRange("<1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 2), less_than, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 3), less_than, False))
            less_or_equal = VersionRange("<=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), less_or_equal, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), less_or_equal, False))
            greater_than = VersionRange(">1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 4), greater_than, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 3), greater_than, False))
            greater_or_equal = VersionRange(">=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), greater_or_equal, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), greater_or_equal, False))

    def test_satisfies_caret_expansion(self) -> None:
        """POSTCONDITION: caret prefixes expand from the first non-zero component boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            major_caret = VersionRange("^1.x")
            self.assertTrue(engine.satisfies(Version(1, 9, 9), major_caret, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), major_caret, False))
            minor_caret = VersionRange("^0.2.3")
            self.assertTrue(engine.satisfies(Version(0, 2, 5), minor_caret, False))
            self.assertFalse(engine.satisfies(Version(0, 3, 0), minor_caret, False))
            zero_major_wildcard = VersionRange("^0.x")
            self.assertTrue(engine.satisfies(Version(0, 5, 0), zero_major_wildcard, False))
            self.assertTrue(engine.satisfies(Version(0, 0, 1), zero_major_wildcard, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), zero_major_wildcard, False))
            zero_triple_wildcard = VersionRange("^0.0.x")
            self.assertTrue(engine.satisfies(Version(0, 0, 5), zero_triple_wildcard, False))
            self.assertFalse(engine.satisfies(Version(0, 1, 0), zero_triple_wildcard, False))
            zero_minor_full = VersionRange("^0.0.3")
            self.assertTrue(engine.satisfies(Version(0, 0, 3), zero_minor_full, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 2), zero_minor_full, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 4), zero_minor_full, False))

    def test_satisfies_tilde_expansion(self) -> None:
        """POSTCONDITION: tilde prefixes expand into lower and upper minor boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            tilde_wildcard = VersionRange("~1.2.x")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), tilde_wildcard, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), tilde_wildcard, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), tilde_wildcard, False))
            tilde_major = VersionRange("~1.x")
            self.assertTrue(engine.satisfies(Version(1, 9, 9), tilde_major, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), tilde_major, False))
            tilde_full = VersionRange("~1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), tilde_full, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), tilde_full, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), tilde_full, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), tilde_full, False))

    def test_satisfies_wildcard_normalization(self) -> None:
        """POSTCONDITION: wildcard comparators normalize into paired comparator inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            ge_wildcard = VersionRange(">=1.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), ge_wildcard, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), ge_wildcard, False))
            ne_wildcard = VersionRange("!=1.x")
            self.assertTrue(engine.satisfies(Version(0, 9, 0), ne_wildcard, False))
            self.assertFalse(engine.satisfies(Version(1, 5, 0), ne_wildcard, False))
            self.assertTrue(engine.satisfies(Version(2, 1, 0), ne_wildcard, False))
            any_wildcard = VersionRange(">=*")
            self.assertTrue(engine.satisfies(Version(0, 0, 1), any_wildcard, False))
            self.assertTrue(engine.satisfies(Version(99, 0, 0), any_wildcard, False))
            bare_wildcard = VersionRange("1.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), bare_wildcard, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), bare_wildcard, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), bare_wildcard, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), bare_wildcard, False))
            double_wildcard = VersionRange("1.x.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), double_wildcard, False))
            self.assertTrue(engine.satisfies(Version(1, 4, 2), double_wildcard, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), double_wildcard, False))
            less_wildcard = VersionRange("<1.x")
            self.assertTrue(engine.satisfies(Version(0, 9, 0), less_wildcard, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), less_wildcard, False))
            less_or_equal_wildcard = VersionRange("<=1.x")
            self.assertTrue(engine.satisfies(Version(1, 9, 9), less_or_equal_wildcard, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), less_or_equal_wildcard, False))
            less_or_equal_minor_wildcard = VersionRange("<=1.2.x")
            self.assertTrue(engine.satisfies(Version(1, 2, 9), less_or_equal_minor_wildcard, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), less_or_equal_minor_wildcard, False))
            less_unbounded = VersionRange("<*")
            self.assertFalse(engine.satisfies(Version(0, 0, 0), less_unbounded, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), less_unbounded, False))
            greater_unbounded = VersionRange(">*")
            self.assertFalse(engine.satisfies(Version(0, 0, 0), greater_unbounded, False))
            self.assertFalse(engine.satisfies(Version(99, 0, 0), greater_unbounded, False))
            not_equal_unbounded = VersionRange("!=*")
            self.assertFalse(engine.satisfies(Version(0, 0, 0), not_equal_unbounded, False))
            self.assertFalse(engine.satisfies(Version(1, 5, 0), not_equal_unbounded, False))

    def test_satisfies_hyphen_range(self) -> None:
        """POSTCONDITION: hyphen ranges normalize into lower and upper comparator bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = VersionRange("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(2, 9, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 0), constraint, False))
            full_bounds = VersionRange("1.0.0 - 2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), full_bounds, False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), full_bounds, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), full_bounds, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 1), full_bounds, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), full_bounds, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITION: a version satisfies a union when it satisfies at least one clause."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = VersionRange(">=1.0.0 <2.0.0 || >=3.0.0")
            self.assertTrue(engine.satisfies(Version(1, 5, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(3, 1, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 5, 0), constraint, False))

    def test_satisfies_filters_prerelease_candidates(self) -> None:
        """POSTCONDITION: prereleases are filtered out unless the range explicitly targets them."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertFalse(
                engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=0.1.0"), False)
            )
            self.assertTrue(
                engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0-alpha"), False)
            )

    def test_satisfies_include_prerelease_uses_direct_precedence(self) -> None:
        """POSTCONDITION: include_prerelease compares prereleases directly without shifting boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertFalse(
                engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), True)
            )
            self.assertTrue(
                engine.satisfies(Version(1, 0, 1, ("beta",)), VersionRange(">=1.0.0"), True)
            )


class SemverPackageRepositoryTest(unittest.TestCase):
    """Verifies PackageRepository registration and indexed release retrieval contracts."""

    def setUp(self) -> None:
        self.registry: LifecycleRegistry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_get_releases_orders_descending_precedence(self) -> None:
        """POSTCONDITION: registered releases are retrieved ordered by descending version precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("pkg", Version(1, 0, 0)))
            repository.register_package(PackageRelease("pkg", Version(2, 0, 0)))
            repository.register_package(PackageRelease("pkg", Version(1, 2, 0)))
            repository.register_package(PackageRelease("pkg", Version(2, 0, 0, ("rc", "1"))))
            releases = repository.get_releases("pkg")
            self.assertEqual(len(releases), 4)
            self.assertEqual(
                [release.version for release in releases],
                [
                    Version(2, 0, 0),
                    Version(2, 0, 0, ("rc", "1")),
                    Version(1, 2, 0),
                    Version(1, 0, 0),
                ],
            )

    def test_register_package_preserves_dependencies(self) -> None:
        """POSTCONDITION: declared dependencies are retained on the registered release."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            dependencies = (PackageDependency("leaf", VersionRange("^1.0.0")),)
            repository.register_package(PackageRelease("pkg", Version(1, 0, 0), dependencies))
            released = repository.get_releases("pkg")
            self.assertEqual(len(released), 1)
            self.assertEqual(released[0].dependencies, dependencies)
            self.assertEqual(released[0].name, "pkg")

    def test_get_releases_missing_package(self) -> None:
        """PRECONDITION: an unregistered package name MUST raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as context:
                repository.get_releases("missing")
            self.assertEqual(context.exception.package_name, "missing")

    def test_has_package_reports_membership(self) -> None:
        """POSTCONDITION: has_package reports True exactly when the package is registered."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("pkg"))
            repository.register_package(PackageRelease("pkg", Version(1, 0, 0)))
            self.assertTrue(repository.has_package("pkg"))
            self.assertFalse(repository.has_package("other"))

    def test_all_packages_returns_registered_names(self) -> None:
        """POSTCONDITION: all_packages produces the set of every registered package name."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertEqual(repository.all_packages(), set())
            repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
            repository.register_package(PackageRelease("beta", Version(2, 0, 0)))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITION: the returned release list is a shallow copy independent of repository state."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("pkg", Version(1, 0, 0)))
            releases = repository.get_releases("pkg")
            releases.clear()
            self.assertEqual(len(repository.get_releases("pkg")), 1)


class SemverDependencySolverTest(unittest.TestCase):
    """Verifies DependencySolver backtracking resolution and conflict reporting contracts."""

    def setUp(self) -> None:
        self.registry: LifecycleRegistry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_resolve_selects_highest_compatible_transitive_versions(self) -> None:
        """POSTCONDITION: resolution includes transitive dependencies and picks the highest compatible version."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("lib", VersionRange("^1.0.0")),),
                )
            )
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(PackageRelease("lib", Version(1, 4, 0)))
            repository.register_package(PackageRelease("lib", Version(2, 0, 0)))
            outcome = solver.resolve([PackageDependency("app", VersionRange("^1.0.0"))])
            self.assertEqual(outcome.selected_versions["app"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 4, 0))
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_backtracks_from_conflicting_candidate(self) -> None:
        """POSTCONDITION: a conflicting higher release is abandoned in favor of a compatible lower release."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(2, 0, 0),
                    (PackageDependency("lib", VersionRange("^2.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 5, 0),
                    (PackageDependency("lib", VersionRange("^1.0.0")),),
                )
            )
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(PackageRelease("lib", Version(1, 4, 0)))
            repository.register_package(PackageRelease("lib", Version(2, 0, 0)))
            outcome = solver.resolve(
                [
                    PackageDependency("app", VersionRange(">=1.0.0")),
                    PackageDependency("lib", VersionRange("^1.0.0")),
                ]
            )
            self.assertEqual(outcome.selected_versions["app"], Version(1, 5, 0))
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 4, 0))

    def test_resolve_raises_conflict_for_unsatisfiable_constraints(self) -> None:
        """PRECONDITION: mutually unsatisfiable constraints MUST raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("lib", VersionRange("^1.0.0")),),
                )
            )
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(PackageRelease("lib", Version(2, 0, 0)))
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve(
                    [
                        PackageDependency("app", VersionRange("^1.0.0")),
                        PackageDependency("lib", VersionRange("^2.0.0")),
                    ]
                )
            self.assertIn("lib", context.exception.conflicting_packages)
            self.assertIsInstance(context.exception.explanation, str)
            self.assertGreater(len(context.exception.explanation), 0)

    def test_resolve_raises_conflict_for_unregistered_package(self) -> None:
        """PRECONDITION: an unregistered package MUST raise ResolutionConflictError, never PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([PackageDependency("missing", VersionRange("^1.0.0"))])
            self.assertIn("missing", context.exception.conflicting_packages)

    def test_resolve_rejects_candidate_conflicting_with_selected_release(self) -> None:
        """POSTCONDITION: a candidate whose dependency contradicts an already-selected release is rejected in favor of a compatible lower release."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(2, 0, 0),
                    (PackageDependency("lib", VersionRange("^2.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 5, 0),
                    (PackageDependency("lib", VersionRange("^1.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("lib", VersionRange("^1.0.0")),),
                )
            )
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(PackageRelease("lib", Version(1, 4, 0)))
            repository.register_package(PackageRelease("lib", Version(2, 0, 0)))
            outcome = solver.resolve(
                [
                    PackageDependency("lib", VersionRange("^1.0.0")),
                    PackageDependency("app", VersionRange(">=1.0.0")),
                ]
            )
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 4, 0))
            self.assertEqual(outcome.selected_versions["app"], Version(1, 5, 0))

    def test_resolve_restores_constraints_after_multilevel_conflict(self) -> None:
        """POSTCONDITION: a conflicting transitive branch is discarded so the restored constraints resolve to lower releases."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(2, 0, 0),
                    (PackageDependency("mid", VersionRange("^2.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("mid", VersionRange("^1.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "mid",
                    Version(2, 0, 0),
                    (PackageDependency("deep", VersionRange("^2.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "mid",
                    Version(1, 0, 0),
                    (PackageDependency("deep", VersionRange("^1.0.0")),),
                )
            )
            repository.register_package(PackageRelease("deep", Version(1, 0, 0)))
            outcome = solver.resolve(
                [
                    PackageDependency("app", VersionRange(">=1.0.0")),
                    PackageDependency("deep", VersionRange("^1.0.0")),
                ]
            )
            self.assertEqual(outcome.selected_versions["app"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["mid"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["deep"], Version(1, 0, 0))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:35:02Z
# LAST_CHANGED: 2026-11-07T03:32:48Z
# CHANGE: Resolved coverage feedback: added explicit ==, =, !=, <, <=, >, >= full-version satisfaction predicates; ~1.2.3 full-version tilde; ^0.x, ^0.0.x, ^0.0.3 first-non-zero caret boundaries; bare 1.x wildcard, 1.x.x double-trailing wildcard, <1.x / <=1.x / <=1.2.x comparator wildcards, and unbounded <*, >*, !=* that match no version; 1.0.0 - 2.0.0 inclusive hyphen range; converse prerelease ranking where alphanumeric outranks numeric; Version.format()/__str__ round-trip; and solver scenarios rejecting a candidate whose dependency contradicts an already-selected release, plus a multi-level conflict introducing a new transitive package whose constraints are restored so lower releases resolve. All new syntax forms also exercise parse_range acceptance.
# COVERAGE_AUDIT: 2026-11-07T03:35:02Z
# QA_AUDIT: 2026-11-07T03:34:20Z
# --- END AUTOFAB METADATA ---
