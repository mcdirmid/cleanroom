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


class SemverSolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialize_registers_system_singletons(self) -> None:
        """Module initialization registers the three system singletons for scope resolution."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            self.assertIs(engine, scope.get_singleton(VersionEngine))
            self.assertIs(repository, scope.get_singleton(PackageRepository))
            self.assertIs(solver, scope.get_singleton(DependencySolver))

    def test_parse_version_valid_syntax(self) -> None:
        """Valid SemVer text parses into a Version record with numeric components."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.parse_version("1.2.3"), Version(1, 2, 3))
            self.assertEqual(engine.parse_version("0.0.0"), Version(0, 0, 0))
            self.assertEqual(engine.parse_version("10.20.30"), Version(10, 20, 30))

    def test_parse_version_prerelease_and_build(self) -> None:
        """Pre-release and build identifiers are extracted as ordered tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.parse_version("1.2.3-alpha.1+build.5"),
                Version(1, 2, 3, ("alpha", "1"), ("build", "5")),
            )
            self.assertEqual(
                engine.parse_version("1.0.0-rc.1"),
                Version(1, 0, 0, ("rc", "1")),
            )
            self.assertEqual(
                engine.parse_version("2.0.0+build.7"),
                Version(2, 0, 0, (), ("build", "7")),
            )

    def test_parse_version_rejects_grammar_violations(self) -> None:
        """Grammar-violating version text raises InvalidVersionError carrying the raw text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("", "1.2", "1.2.3.4", "not-a-version", "1.2.3-"):
                with self.assertRaises(InvalidVersionError) as caught:
                    engine.parse_version(text)
                self.assertEqual(caught.exception.raw_text, text)

    def test_parse_version_rejects_numeric_leading_zeroes(self) -> None:
        """Numeric identifiers with leading zeroes raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("01.2.3", "1.02.3", "1.2.03", "1.2.3-01"):
                with self.assertRaises(InvalidVersionError) as caught:
                    engine.parse_version(text)
                self.assertEqual(caught.exception.raw_text, text)

    def test_compare_precedence_tri_state(self) -> None:
        """Ordering result is negative, zero, or positive for lower, equal, and higher versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            low = Version(1, 0, 0)
            high = Version(2, 0, 0)
            self.assertLess(engine.compare_precedence(low, high), 0)
            self.assertGreater(engine.compare_precedence(high, low), 0)
            self.assertEqual(engine.compare_precedence(low, Version(1, 0, 0)), 0)

    def test_compare_precedence_numerical_components(self) -> None:
        """Major, minor, and patch compare numerically rather than lexicographically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(engine.compare_precedence(Version(1, 10, 0), Version(1, 9, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 2, 10), Version(1, 2, 9)), 0)
            self.assertGreater(engine.compare_precedence(Version(2, 0, 0), Version(1, 99, 99)), 0)

    def test_compare_precedence_normal_vs_prerelease(self) -> None:
        """A normal version ranks above a pre-release version with identical numbers."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            normal = Version(1, 0, 0)
            prerelease = Version(1, 0, 0, ("alpha",))
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)

    def test_compare_precedence_prerelease_ordering(self) -> None:
        """Pre-release segments follow the RFC priority chain, ranking numeric below string."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            chain = [
                Version(1, 0, 0, ("alpha",)),
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha", "beta")),
                Version(1, 0, 0, ("beta",)),
                Version(1, 0, 0, ("beta", "2")),
                Version(1, 0, 0, ("beta", "11")),
                Version(1, 0, 0, ("rc", "1")),
                Version(1, 0, 0),
            ]
            for lower, higher in zip(chain, chain[1:]):
                self.assertLess(engine.compare_precedence(lower, higher), 0)
                self.assertGreater(engine.compare_precedence(higher, lower), 0)

    def test_compare_precedence_build_metadata_ignored(self) -> None:
        """Build metadata does not affect precedence ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(
                    Version(1, 0, 0, (), ("build", "1")),
                    Version(1, 0, 0, (), ("build", "2")),
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha",), ("a",)),
                    Version(1, 0, 0, ("alpha",), ("b",)),
                ),
                0,
            )

    def test_compare_precedence_equal_components(self) -> None:
        """Versions with identical numeric and pre-release components compare equal."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)
            self.assertEqual(
                engine.compare_precedence(Version(1, 2, 3, ("1",)), Version(1, 2, 3, ("1",))),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    Version(1, 2, 3, ("alpha", "1")),
                    Version(1, 2, 3, ("alpha", "1")),
                ),
                0,
            )

    def test_parse_range_valid_expressions(self) -> None:
        """Comparator, caret, tilde, wildcard, hyphen, and union range forms all parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            expressions = [
                "==1.0.0",
                "=1.0.0",
                "!=1.0.0",
                "<1.0.0",
                "<=1.0.0",
                ">1.0.0",
                ">=1.0.0",
                ">=1.x",
                "!=1.x",
                ">1.*",
                "^1.x",
                "~1.2.x",
                ">=*",
                "1.0.0 - 2.x",
                "1.x - 2.x",
                ">=1.0.0 <2.0.0 || >=3.0.0",
            ]
            for expression in expressions:
                parsed = engine.parse_range(expression)
                self.assertIsInstance(parsed, VersionRange)

    def test_parse_range_trims_surrounding_whitespace(self) -> None:
        """Surrounding whitespace is trimmed and optional operator spacing is accepted."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.parse_range("   >=1.0.0   ").raw_text, ">=1.0.0")
            self.assertEqual(engine.parse_range(">= 1.0.0").raw_text, ">= 1.0.0")
            self.assertEqual(engine.parse_range("  >= 1.x  ").raw_text, ">= 1.x")

    def test_parse_range_rejects_invalid_expressions(self) -> None:
        """Bare partial versions, comma delimiters, and empty union clauses raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            expressions = [
                "",
                "   ",
                "1",
                "1.2",
                ">1.2",
                "^0.0",
                "1.2 - 2.3",
                ">=1.0.0, <2.0.0",
                ">=1.0.0 || ",
                " || >=1.0.0",
            ]
            for expression in expressions:
                with self.assertRaises(InvalidRangeError) as caught:
                    engine.parse_range(expression)
                self.assertEqual(caught.exception.raw_range, expression)

    def test_parse_range_rejects_malformed_wildcards(self) -> None:
        """Wildcard characters in non-final positions are malformed range expressions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            expressions = ["1.x.3", "1.*.2", ">=1.x.3", "^1.x.3", "1.2.x.4"]
            for expression in expressions:
                with self.assertRaises(InvalidRangeError) as caught:
                    engine.parse_range(expression)
                self.assertEqual(caught.exception.raw_range, expression)

    def test_satisfies_boolean_match_and_boundaries(self) -> None:
        """Versions inside the range evaluate to True and versions outside evaluate to False."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = engine.parse_range(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), constraint, False))

    def test_satisfies_equality_comparators(self) -> None:
        """The '=' and '!=' comparators match on exact precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(Version(1, 0, 0), engine.parse_range("=1.0.0"), False))
            self.assertFalse(engine.satisfies(Version(1, 0, 1), engine.parse_range("=1.0.0"), False))
            self.assertTrue(engine.satisfies(Version(1, 0, 1), engine.parse_range("!=1.0.0"), False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), engine.parse_range("!=1.0.0"), False))

    def test_satisfies_le_comparator(self) -> None:
        """The '<=' comparator includes its boundary and rejects larger versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = engine.parse_range("<=1.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(0, 9, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 1), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), engine.parse_range("<1.0.0"), False))

    def test_satisfies_wildcard_equality(self) -> None:
        """An equality comparator applied to a wildcard accepts the whole wildcard span."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = engine.parse_range("==1.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), constraint, False))

    def test_satisfies_lt_le_wildcard(self) -> None:
        """Strict '<' and inclusive '<=' wildcard comparators bound the wildcard span."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            strict = engine.parse_range("<1.x")
            self.assertTrue(engine.satisfies(Version(0, 9, 9), strict, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), strict, False))
            inclusive = engine.parse_range("<=1.x")
            self.assertTrue(engine.satisfies(Version(0, 9, 9), inclusive, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), inclusive, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), inclusive, False))

    def test_satisfies_wildcard_expansion(self) -> None:
        """Caret, tilde, and wildcard expressions expand into comparator inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(Version(1, 9, 9), engine.parse_range("^1.x"), False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), engine.parse_range("^1.x"), False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), engine.parse_range("^1.2.3"), False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), engine.parse_range("^1.2.3"), False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), engine.parse_range("~1.x"), False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), engine.parse_range("~1.x"), False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), engine.parse_range("~1.2.x"), False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), engine.parse_range("~1.2.x"), False))
            self.assertFalse(engine.satisfies(Version(1, 1, 9), engine.parse_range("~1.2.x"), False))
            self.assertTrue(engine.satisfies(Version(5, 0, 0), engine.parse_range(">=1.x"), False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), engine.parse_range(">=1.x"), False))
            self.assertFalse(engine.satisfies(Version(1, 5, 0), engine.parse_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(Version(0, 5, 0), engine.parse_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), engine.parse_range("!=1.x"), False))

    def test_parse_range_caret_zero_components(self) -> None:
        """Caret expansion on zero-rooted versions follows the first non-zero component boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            minor = engine.parse_range("^0.2.x")
            self.assertTrue(engine.satisfies(Version(0, 2, 0), minor, False))
            self.assertTrue(engine.satisfies(Version(0, 2, 9), minor, False))
            self.assertFalse(engine.satisfies(Version(0, 3, 0), minor, False))
            self.assertFalse(engine.satisfies(Version(0, 1, 9), minor, False))
            patch = engine.parse_range("^0.0.x")
            self.assertTrue(engine.satisfies(Version(0, 0, 9), patch, False))
            self.assertFalse(engine.satisfies(Version(0, 1, 0), patch, False))
            exact = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(Version(0, 2, 3), exact, False))
            self.assertTrue(engine.satisfies(Version(0, 2, 9), exact, False))
            self.assertFalse(engine.satisfies(Version(0, 3, 0), exact, False))
            self.assertFalse(engine.satisfies(Version(0, 2, 2), exact, False))
            unspecified_minor = engine.parse_range("^0.x")
            self.assertTrue(engine.satisfies(Version(0, 0, 0), unspecified_minor, False))
            self.assertTrue(engine.satisfies(Version(0, 9, 9), unspecified_minor, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), unspecified_minor, False))
            zero_zero_patch = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(Version(0, 0, 3), zero_zero_patch, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 4), zero_zero_patch, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 2), zero_zero_patch, False))

    def test_parse_range_tilde_exact_version(self) -> None:
        """Tilde expansion on an exact version pins the lower bound to that version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), constraint, False))

    def test_satisfies_universal_wildcard(self) -> None:
        """Universal wildcard forms are satisfied by every version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraints = [
                engine.parse_range("*"),
                engine.parse_range(">=*"),
                engine.parse_range("<=*"),
            ]
            for constraint in constraints:
                for version in (Version(0, 0, 0), Version(1, 2, 3), Version(99, 99, 99)):
                    self.assertTrue(engine.satisfies(version, constraint, True))

    def test_satisfies_universal_wildcard_strict_and_inequality(self) -> None:
        """Strict and inequality operators over the universal wildcard admit no version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraints = [
                engine.parse_range("<*"),
                engine.parse_range(">*"),
                engine.parse_range("!=*"),
            ]
            for constraint in constraints:
                for version in (Version(0, 0, 0), Version(1, 2, 3), Version(99, 99, 99)):
                    self.assertFalse(engine.satisfies(version, constraint, True))

    def test_satisfies_hyphen_range(self) -> None:
        """A hyphen range expands into an inclusive lower and exclusive upper bound."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = engine.parse_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(2, 9, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), constraint, False))

    def test_satisfies_hyphen_range_bounds(self) -> None:
        """Hyphen ranges normalize wildcard and exact bounds into comparator pairs."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            wildcard_bounds = engine.parse_range("1.x - 2.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), wildcard_bounds, False))
            self.assertTrue(engine.satisfies(Version(2, 9, 9), wildcard_bounds, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), wildcard_bounds, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), wildcard_bounds, False))
            exact_bounds = engine.parse_range("1.2.0 - 2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), exact_bounds, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), exact_bounds, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 1), exact_bounds, False))
            self.assertFalse(engine.satisfies(Version(1, 1, 9), exact_bounds, False))
            mixed_bounds = engine.parse_range("1.x - 2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), mixed_bounds, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 1), mixed_bounds, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), mixed_bounds, False))

    def test_satisfies_union_alternatives(self) -> None:
        """Satisfying any union alternative yields True."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = engine.parse_range(">=1.0.0 <2.0.0 || >=3.0.0")
            self.assertTrue(engine.satisfies(Version(1, 5, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(3, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 5, 0), constraint, False))

    def test_satisfies_prerelease_filter(self) -> None:
        """Pre-release candidates are excluded unless include_prerelease is True."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(Version(1, 2, 3, ("alpha",)), constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 3, ("alpha",)), constraint, True))
            self.assertFalse(
                engine.satisfies(Version(1, 0, 0, ("alpha",)), engine.parse_range(">=1.0.0"), True)
            )

    def test_satisfies_explicit_prerelease_range(self) -> None:
        """A range naming the pre-release identifier admits it even when include_prerelease is False."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            constraint = engine.parse_range(">=1.0.0-alpha <1.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0, ("beta",)), constraint, False))
            self.assertFalse(
                engine.satisfies(Version(1, 0, 0, ("beta",)), engine.parse_range(">0.0.1"), False)
            )

    def test_register_package_sorts_releases_descending(self) -> None:
        """Releases are ordered by precedence descending with pre-releases ranked below normals."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
            repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
            repository.register_package(PackageRelease("alpha", Version(1, 0, 0, ("beta",))))
            repository.register_package(PackageRelease("alpha", Version(1, 5, 0)))
            releases = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in releases],
                [Version(2, 0, 0), Version(1, 5, 0), Version(1, 0, 0), Version(1, 0, 0, ("beta",))],
            )
            self.assertTrue(all(release.name == "alpha" for release in releases))

    def test_register_package_preserves_dependencies(self) -> None:
        """A registered release retains its declared dependencies."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            dependency = PackageDependency("lib", VersionRange(">=1.0.0"))
            repository.register_package(
                PackageRelease("app", Version(1, 0, 0), (dependency,))
            )
            releases = repository.get_releases("app")
            self.assertEqual(releases[0].version, Version(1, 0, 0))
            self.assertEqual(releases[0].dependencies, (dependency,))

    def test_get_releases_returns_copy(self) -> None:
        """get_releases returns a shallow copy so caller mutation cannot corrupt the index."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("beta", Version(1, 0, 0)))
            releases = repository.get_releases("beta")
            releases.append(PackageRelease("beta", Version(9, 0, 0)))
            self.assertEqual(len(repository.get_releases("beta")), 1)

    def test_get_releases_missing_package_raises(self) -> None:
        """An unknown package name raises PackageNotFoundError carrying the package name."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as caught:
                repository.get_releases("missing")
            self.assertEqual(caught.exception.package_name, "missing")

    def test_has_package_and_all_packages(self) -> None:
        """Membership checks and the name index reflect registrations."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("alpha"))
            repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
            repository.register_package(PackageRelease("beta", Version(2, 0, 0)))
            self.assertTrue(repository.has_package("alpha"))
            self.assertTrue(repository.has_package("beta"))
            self.assertFalse(repository.has_package("gamma"))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})

    def test_resolve_selects_highest_compatible_versions(self) -> None:
        """Transitive resolution selects the highest compatible release for each package."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            lib_requirement = PackageDependency("lib", engine.parse_range("^1.0.0"))
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(PackageRelease("lib", Version(1, 2, 0)))
            repository.register_package(PackageRelease("lib", Version(2, 0, 0)))
            repository.register_package(PackageRelease("app", Version(1, 0, 0)))
            repository.register_package(
                PackageRelease("app", Version(1, 1, 0), (lib_requirement,))
            )
            repository.register_package(PackageRelease("app", Version(2, 0, 0)))
            root = [PackageDependency("app", engine.parse_range(">=1.0.0 <2.0.0"))]
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["app"], Version(1, 1, 0))
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 2, 0))
            self.assertTrue(outcome.derivation_steps)

    def test_resolve_empty_root_dependencies(self) -> None:
        """Empty root dependencies resolve to an empty assignment without conflicts."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([])
            self.assertEqual(len(outcome.selected_versions), 0)
            self.assertEqual(outcome.derivation_steps, ())

    def test_resolve_unsatisfiable_conflict_raises(self) -> None:
        """Contradictory constraints raise ResolutionConflictError with conflict diagnostics."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("app", Version(1, 0, 0)))
            repository.register_package(PackageRelease("app", Version(2, 0, 0)))
            root = [
                PackageDependency("app", engine.parse_range(">=1.0.0 <2.0.0")),
                PackageDependency("app", engine.parse_range(">=2.0.0 <3.0.0")),
            ]
            with self.assertRaises(ResolutionConflictError) as caught:
                solver.resolve(root)
            self.assertIn("app", caught.exception.conflicting_packages)
            self.assertTrue(caught.exception.explanation)

    def test_resolve_unregistered_package_conflict(self) -> None:
        """Unregistered packages become conflicts rather than escaping PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            solver = scope.get_singleton(DependencySolver)
            root = [PackageDependency("ghost", engine.parse_range(">=1.0.0"))]
            with self.assertRaises(ResolutionConflictError) as caught:
                solver.resolve(root)
            self.assertIn("ghost", caught.exception.conflicting_packages)
            self.assertTrue(caught.exception.explanation)

    def test_resolve_transitive_conflict_raises(self) -> None:
        """Conflicting transitive requirements raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            lib_requirement = PackageDependency("lib", engine.parse_range("^2.0.0"))
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(
                PackageRelease("app", Version(1, 0, 0), (lib_requirement,))
            )
            root = [
                PackageDependency("app", engine.parse_range(">=1.0.0")),
                PackageDependency("lib", engine.parse_range(">=1.0.0")),
            ]
            with self.assertRaises(ResolutionConflictError) as caught:
                solver.resolve(root)
            self.assertIn("lib", caught.exception.conflicting_packages)
            self.assertTrue(caught.exception.explanation)
    def test_resolve_recovers_from_assigned_package_conflict(self) -> None:
        """A dependency that violates an already assigned package retries the next admissible candidate."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("aaa", Version(1, 0, 0)))
            repository.register_package(
                PackageRelease(
                    "zzz",
                    Version(2, 0, 0),
                    (PackageDependency("aaa", engine.parse_range("^2.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "zzz",
                    Version(1, 5, 0),
                    (PackageDependency("aaa", engine.parse_range("^1.0.0")),),
                )
            )
            root = [
                PackageDependency("aaa", engine.parse_range("^1.0.0")),
                PackageDependency("zzz", engine.parse_range(">=1.0.0")),
            ]
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["aaa"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["zzz"], Version(1, 5, 0))

    def test_resolve_backtracks_through_exhausted_candidates(self) -> None:
        """Exhausted candidate branches unwind their constraints so lower candidates can succeed."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            repository.register_package(
                PackageRelease(
                    "mid",
                    Version(1, 0, 0),
                    (PackageDependency("lib", engine.parse_range("^2.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(2, 0, 0),
                    (PackageDependency("mid", engine.parse_range("^1.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("lib", engine.parse_range("^1.0.0")),),
                )
            )
            root = [PackageDependency("app", engine.parse_range(">=1.0.0"))]
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["app"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 0, 0))
            self.assertNotIn("mid", outcome.selected_versions)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T20:54:38Z
# LAST_CHANGED: 2026-11-10T20:52:07Z
# CHANGE: Resolved remaining coverage witnesses. Caret zero-major branches: '^0.x' (unspecified minor) expands to >=0.0.0 <1.0.0 and '^0.0.3' (zero major/minor, exact patch) expands to >=0.0.3 <0.0.4. Universal wildcard strict/inequality operators: '<*', '>*', and '!=*' normalize to ranges admitting no version (asserted False for 0.0.0, 1.2.3, 99.99.99 with prereleases enabled). Solver assigned-release conflict: aaa is selected first by MRV and assigned 1.0.0; zzz's higher candidate 2.0.0 requires aaa ^2.0.0 and conflicts with the assignment, so the search retries zzz 1.5.0, whose aaa ^1.0.0 requirement is admissible, yielding aaa 1.0.0 and zzz 1.5.0.
# COVERAGE_AUDIT: 2026-11-10T20:54:38Z
# QA_AUDIT: 2026-11-10T20:54:23Z
# --- END AUTOFAB METADATA ---
