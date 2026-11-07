"""Unit tests for semver_solver_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

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


def _version_range(text: str) -> VersionRange:
    """Wraps raw range text into a domain VersionRange record."""
    return VersionRange(raw_text=text)


def _dependency(name: str, range_text: str) -> PackageDependency:
    """Wraps a package name and raw range text into a PackageDependency."""
    return PackageDependency(name=name, range_constraint=_version_range(range_text))


def _release(
    name: str,
    version: Version,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Wraps a name, version, and dependency tuple into a PackageRelease."""
    return PackageRelease(name=name, version=version, dependencies=dependencies)


class SemverSolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_full_record(self) -> None:
        """POSTCONDITIONS: parse valid SemVer into major, minor, patch, prerelease, and build tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))

    def test_parse_version_without_prerelease_or_build(self) -> None:
        """POSTCONDITIONS: parse plain and multi-digit versions with empty optional tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("10.20.30")
            self.assertEqual(version, Version(major=10, minor=20, patch=30))
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ())

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """PRECONDITIONS: numeric identifiers with leading zeroes raise InvalidVersionError."""
        invalid_texts = ["01.2.3", "1.02.3", "1.2.03"]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in invalid_texts:
                with self.assertRaises(InvalidVersionError) as context:
                    engine.parse_version(text)
                self.assertEqual(context.exception.raw_text, text)

    def test_parse_version_rejects_grammar_violations(self) -> None:
        """PRECONDITIONS: grammar-violating version strings raise InvalidVersionError."""
        invalid_texts = ["1.2", "1", "1.2.3.4", "v1.2.3", "1.2.3-", "1.2.3+"]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in invalid_texts:
                with self.assertRaises(InvalidVersionError) as context:
                    engine.parse_version(text)
                self.assertEqual(context.exception.raw_text, text)

    def test_compare_precedence_numeric_components(self) -> None:
        """POSTCONDITIONS: compare major, minor, and patch numerically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            v100 = Version(major=1, minor=0, patch=0)
            v200 = Version(major=2, minor=0, patch=0)
            v110 = Version(major=1, minor=1, patch=0)
            v101 = Version(major=1, minor=0, patch=1)
            self.assertLess(engine.compare_precedence(v100, v200), 0)
            self.assertGreater(engine.compare_precedence(v200, v100), 0)
            self.assertLess(engine.compare_precedence(v100, v110), 0)
            self.assertLess(engine.compare_precedence(v100, v101), 0)
            self.assertEqual(engine.compare_precedence(v100, Version(major=1, minor=0, patch=0)), 0)

    def test_compare_precedence_numeric_prerelease_segments(self) -> None:
        """POSTCONDITIONS: numeric prerelease segments compare as integers, equal numeric prefixes continue to later segments, and identical sequences compare equal."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            two = Version(major=1, minor=0, patch=0, prerelease=("2",))
            ten = Version(major=1, minor=0, patch=0, prerelease=("10",))
            alpha = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
            self.assertLess(engine.compare_precedence(two, ten), 0)
            self.assertGreater(engine.compare_precedence(ten, two), 0)
            self.assertLess(engine.compare_precedence(two, alpha), 0)
            self.assertGreater(engine.compare_precedence(alpha, two), 0)

            one_two = Version(major=1, minor=0, patch=0, prerelease=("1", "2"))
            one_ten = Version(major=1, minor=0, patch=0, prerelease=("1", "10"))
            self.assertLess(engine.compare_precedence(one_two, one_ten), 0)
            self.assertGreater(engine.compare_precedence(one_ten, one_two), 0)

            one_alpha = Version(major=1, minor=0, patch=0, prerelease=("1", "alpha"))
            one_beta = Version(major=1, minor=0, patch=0, prerelease=("1", "beta"))
            self.assertLess(engine.compare_precedence(one_alpha, one_beta), 0)
            self.assertGreater(engine.compare_precedence(one_beta, one_alpha), 0)

            identical = Version(major=1, minor=0, patch=0, prerelease=("1", "alpha"))
            self.assertEqual(engine.compare_precedence(one_alpha, identical), 0)

    def test_compare_precedence_normal_above_prerelease_and_prefixes(self) -> None:
        """POSTCONDITIONS: normal ranks above prerelease and longer prerelease prefixes rank higher."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            normal = Version(major=1, minor=0, patch=0)
            alpha = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
            alpha_one = Version(major=1, minor=0, patch=0, prerelease=("alpha", "1"))
            self.assertGreater(engine.compare_precedence(normal, alpha), 0)
            self.assertLess(engine.compare_precedence(alpha, normal), 0)
            self.assertLess(engine.compare_precedence(alpha, alpha_one), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: build metadata is ignored entirely during precedence comparison."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            first = Version(major=1, minor=0, patch=0, build=("build", "1"))
            second = Version(major=1, minor=0, patch=0, build=("build", "2"))
            self.assertEqual(engine.compare_precedence(first, second), 0)

    def test_parse_range_accepts_supported_syntax(self) -> None:
        """POSTCONDITIONS: parse comparators, caret, tilde, wildcards, hyphen ranges, and unions."""
        valid_ranges = [
            "*",
            "=*",
            "1.0.0",
            "==1.0.0",
            "=1.0.0",
            "!=1.0.0",
            "<1.0.0",
            "<=1.0.0",
            ">1.0.0",
            ">=1.0.0 <2.0.0",
            ">= 1.x",
            "^1.2.3",
            "~1.2.3",
            "~1.2.x",
            "~1.x",
            ">=1.x",
            "!=1.x",
            ">1.*",
            ">=*",
            "^*",
            "~*",
            "^0.2.3",
            "^0.0.3",
            "^0.x",
            "^0.2.x",
            "^0.0.x",
            "1.0.0 - 2.0.0",
            "1.0.0 - 2.x",
            "1.0.0 - *",
            "1.x - 2.x",
            ">=1.0.0 <2.0.0 || >=3.0.0",
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in valid_ranges:
                parsed = engine.parse_range(text)
                self.assertIsInstance(parsed, VersionRange)
                self.assertIsInstance(parsed.raw_text, str)
                self.assertTrue(parsed.raw_text)

    def test_parse_range_trims_surrounding_whitespace(self) -> None:
        """POSTCONDITIONS: trim surrounding whitespace and store the trimmed expression in raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("   >=1.0.0   ")
            self.assertEqual(parsed.raw_text, ">=1.0.0")

    def test_parse_range_rejects_bare_partial_versions(self) -> None:
        """PRECONDITIONS: partial versions lacking wildcards raise InvalidRangeError."""
        invalid_ranges = ["1", "1.2", ">1.2", "^0.0", "1.2 - 2.3"]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in invalid_ranges:
                with self.assertRaises(InvalidRangeError) as context:
                    engine.parse_range(text)
                self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_rejects_empty_and_comma_syntax(self) -> None:
        """PRECONDITIONS: empty text, empty union clauses, and comma delimiters raise InvalidRangeError."""
        invalid_ranges = ["", "   ", ">=1.0.0 ||", "|| >=1.0.0", ">=1.0.0, <2.0.0"]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in invalid_ranges:
                with self.assertRaises(InvalidRangeError) as context:
                    engine.parse_range(text)
                self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """PRECONDITIONS: extra dotted components, misplaced wildcards, non-numeric components, and dangling operators raise InvalidRangeError."""
        invalid_ranges = [
            ">=1.2.3.4",
            ">=1.x.0",
            ">=1.a.0",
            ">=1.0.0 >=",
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in invalid_ranges:
                with self.assertRaises(InvalidRangeError) as context:
                    engine.parse_range(text)
                self.assertEqual(context.exception.raw_range, text)

    def test_satisfies_basic_comparators(self) -> None:
        """POSTCONDITIONS: every basic comparator accepts satisfying versions and rejects others."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            bounded = _version_range(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(Version(major=1, minor=5, patch=0), bounded, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), bounded, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=0), bounded, False))

            exact_eq = _version_range("==1.2.3")
            self.assertTrue(engine.satisfies(Version(major=1, minor=2, patch=3), exact_eq, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=2, patch=4), exact_eq, False))
            exact_alias = _version_range("=1.2.3")
            self.assertTrue(engine.satisfies(Version(major=1, minor=2, patch=3), exact_alias, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=2, patch=4), exact_alias, False))

            not_equal = _version_range("!=1.2.3")
            self.assertFalse(engine.satisfies(Version(major=1, minor=2, patch=3), not_equal, False))
            self.assertTrue(engine.satisfies(Version(major=1, minor=2, patch=4), not_equal, False))

            less = _version_range("<2.0.0")
            self.assertTrue(engine.satisfies(Version(major=1, minor=9, patch=9), less, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), less, False))

            less_equal = _version_range("<=2.0.0")
            self.assertTrue(engine.satisfies(Version(major=2, minor=0, patch=0), less_equal, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=1), less_equal, False))

            greater = _version_range(">1.0.0")
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=1), greater, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=0, patch=0), greater, False))

            greater_equal = _version_range(">=1.0.0")
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=0), greater_equal, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=9), greater_equal, False))

    def test_satisfies_relational_wildcards(self) -> None:
        """POSTCONDITIONS: relational operators applied to wildcards expand to the grounded boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            less = _version_range("<1.x")
            self.assertFalse(engine.satisfies(Version(major=1, minor=0, patch=0), less, False))
            self.assertTrue(engine.satisfies(Version(major=0, minor=9, patch=9), less, False))

            less_equal = _version_range("<=1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=9, patch=9), less_equal, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), less_equal, False))

            greater_equal = _version_range(">=1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=0), greater_equal, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=9), greater_equal, False))

            greater = _version_range(">1.x")
            self.assertFalse(engine.satisfies(Version(major=1, minor=9, patch=9), greater, False))
            self.assertTrue(engine.satisfies(Version(major=2, minor=0, patch=0), greater, False))

            wildcard_equal = _version_range("=1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=5, patch=0), wildcard_equal, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), wildcard_equal, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=0), wildcard_equal, False))

    def test_satisfies_universal_wildcards(self) -> None:
        """POSTCONDITIONS: universal wildcards accept every version while prohibitive universal targets reject all."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ["*", "=*", ">=*", "<=*", "^*", "~*"]:
                universal = _version_range(text)
                self.assertTrue(engine.satisfies(Version(major=0, minor=0, patch=0), universal, False))
                self.assertTrue(engine.satisfies(Version(major=0, minor=0, patch=1), universal, False))
                self.assertTrue(engine.satisfies(Version(major=5, minor=5, patch=5), universal, False))
            for text in ["!=*", ">*", "<*"]:
                prohibitive = _version_range(text)
                self.assertFalse(engine.satisfies(Version(major=0, minor=0, patch=0), prohibitive, False))
                self.assertFalse(engine.satisfies(Version(major=1, minor=0, patch=0), prohibitive, False))

    def test_satisfies_caret_zero_major_boundaries(self) -> None:
        """POSTCONDITIONS: caret on zero-major full versions and wildcards uses the first non-zero component boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            caret_minor = _version_range("^0.2.3")
            self.assertTrue(engine.satisfies(Version(major=0, minor=2, patch=3), caret_minor, False))
            self.assertTrue(engine.satisfies(Version(major=0, minor=2, patch=99), caret_minor, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=3, patch=0), caret_minor, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=2, patch=2), caret_minor, False))

            caret_patch = _version_range("^0.0.3")
            self.assertTrue(engine.satisfies(Version(major=0, minor=0, patch=3), caret_patch, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=0, patch=4), caret_patch, False))

            caret_major_wildcard = _version_range("^0.x")
            self.assertTrue(engine.satisfies(Version(major=0, minor=9, patch=0), caret_major_wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=0, patch=0), caret_major_wildcard, False))

            caret_minor_wildcard = _version_range("^0.2.x")
            self.assertTrue(engine.satisfies(Version(major=0, minor=2, patch=5), caret_minor_wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=3, patch=0), caret_minor_wildcard, False))

            caret_patch_wildcard = _version_range("^0.0.x")
            self.assertTrue(engine.satisfies(Version(major=0, minor=0, patch=5), caret_patch_wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=1, patch=0), caret_patch_wildcard, False))

    def test_satisfies_tilde_full_and_minor_ranges(self) -> None:
        """POSTCONDITIONS: tilde expansion covers full versions and minor-only wildcards."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            tilde_full = _version_range("~1.2.3")
            self.assertTrue(engine.satisfies(Version(major=1, minor=2, patch=3), tilde_full, False))
            self.assertTrue(engine.satisfies(Version(major=1, minor=2, patch=9), tilde_full, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=3, patch=0), tilde_full, False))

            tilde_minor = _version_range("~1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=0), tilde_minor, False))
            self.assertTrue(engine.satisfies(Version(major=1, minor=9, patch=0), tilde_minor, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), tilde_minor, False))

    def test_satisfies_hyphen_range_bounds(self) -> None:
        """POSTCONDITIONS: hyphen ranges accept inclusive full upper bounds and unbounded wildcard upper bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            full_upper = _version_range("1.0.0 - 2.0.0")
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=0), full_upper, False))
            self.assertTrue(engine.satisfies(Version(major=2, minor=0, patch=0), full_upper, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=1), full_upper, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=9), full_upper, False))

            unbounded_upper = _version_range("1.0.0 - *")
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=0), unbounded_upper, False))
            self.assertTrue(engine.satisfies(Version(major=99, minor=0, patch=0), unbounded_upper, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=9), unbounded_upper, False))

    def test_satisfies_wildcard_caret_tilde_and_hyphen_expansions(self) -> None:
        """POSTCONDITIONS: wildcard, caret, tilde, and hyphen expansions match grounded boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            all_versions = _version_range(">=*")
            self.assertTrue(engine.satisfies(Version(major=0, minor=0, patch=1), all_versions, False))

            caret = _version_range("^1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=9, patch=0), caret, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), caret, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=0), caret, False))

            tilde = _version_range("~1.2.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=2, patch=5), tilde, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=3, patch=0), tilde, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=1, patch=9), tilde, False))

            not_one = _version_range("!=1.x")
            self.assertFalse(engine.satisfies(Version(major=1, minor=5, patch=0), not_one, False))
            self.assertTrue(engine.satisfies(Version(major=0, minor=9, patch=0), not_one, False))
            self.assertTrue(engine.satisfies(Version(major=2, minor=1, patch=0), not_one, False))

            hyphen = _version_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(Version(major=2, minor=9, patch=0), hyphen, False))
            self.assertFalse(engine.satisfies(Version(major=3, minor=0, patch=0), hyphen, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=0), hyphen, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITIONS: union alternatives accept versions matching any clause."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            union = _version_range(">=1.0.0 <2.0.0 || >=3.0.0")
            self.assertTrue(engine.satisfies(Version(major=1, minor=5, patch=0), union, False))
            self.assertTrue(engine.satisfies(Version(major=3, minor=1, patch=0), union, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=5, patch=0), union, False))

    def test_satisfies_excludes_prerelease_by_default(self) -> None:
        """POSTCONDITIONS: prerelease versions are rejected unless explicitly targeted or included."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            bounded = _version_range(">=1.0.0")
            candidate = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
            self.assertFalse(engine.satisfies(candidate, bounded, False))
            self.assertFalse(engine.satisfies(candidate, bounded, True))

    def test_satisfies_included_prerelease_uses_precedence_bounds(self) -> None:
        """POSTCONDITIONS: include_prerelease compares precedence directly without shifting numerical boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            bounded = _version_range(">=1.0.0-alpha")
            beta = Version(major=1, minor=0, patch=0, prerelease=("beta",))
            alpha = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
            self.assertTrue(engine.satisfies(beta, bounded, True))
            self.assertTrue(engine.satisfies(alpha, bounded, True))
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=0), bounded, True))

    def test_satisfies_explicit_prerelease_targeting(self) -> None:
        """POSTCONDITIONS: a prerelease is accepted only when the range targets the same major, minor, and patch."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            targeted = _version_range(">=1.0.0-alpha")
            same_base = Version(major=1, minor=0, patch=0, prerelease=("beta",))
            other_base = Version(major=2, minor=0, patch=0, prerelease=("alpha",))
            self.assertTrue(engine.satisfies(same_base, targeted, False))
            self.assertFalse(engine.satisfies(other_base, targeted, False))

    def test_repository_orders_releases_descending(self) -> None:
        """POSTCONDITIONS: get_releases yields all releases ordered by precedence descending."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_release("letters", Version(major=1, minor=0, patch=0)))
            repository.register_package(_release("letters", Version(major=2, minor=0, patch=0)))
            repository.register_package(_release("letters", Version(major=1, minor=5, patch=0)))
            versions = [release.version for release in repository.get_releases("letters")]
            self.assertEqual(
                versions,
                [
                    Version(major=2, minor=0, patch=0),
                    Version(major=1, minor=5, patch=0),
                    Version(major=1, minor=0, patch=0),
                ],
            )

    def test_repository_get_releases_returns_copy(self) -> None:
        """POSTCONDITIONS: get_releases produces a shallow copy detached from repository storage."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_release("letters", Version(major=1, minor=0, patch=0)))
            releases = repository.get_releases("letters")
            releases.append(_release("letters", Version(major=9, minor=9, patch=9)))
            self.assertEqual(len(repository.get_releases("letters")), 1)

    def test_repository_get_releases_missing_package(self) -> None:
        """PRECONDITIONS: unregistered package names raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as context:
                repository.get_releases("ghost")
            self.assertEqual(context.exception.package_name, "ghost")

    def test_repository_membership_queries(self) -> None:
        """POSTCONDITIONS: has_package and all_packages reflect registered package names."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertEqual(repository.all_packages(), set())
            self.assertFalse(repository.has_package("letters"))
            repository.register_package(_release("letters", Version(major=1, minor=0, patch=0)))
            repository.register_package(_release("numbers", Version(major=1, minor=0, patch=0)))
            self.assertTrue(repository.has_package("letters"))
            self.assertFalse(repository.has_package("ghost"))
            self.assertEqual(repository.all_packages(), {"letters", "numbers"})

    def test_solver_selects_highest_compatible_version(self) -> None:
        """POSTCONDITIONS: resolve selects the highest precedence compatible release for each package."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_release("letters", Version(major=1, minor=0, patch=0)))
            repository.register_package(_release("letters", Version(major=1, minor=2, patch=0)))
            repository.register_package(_release("letters", Version(major=2, minor=0, patch=0)))
            outcome = solver.resolve([_dependency("letters", ">=1.0.0 <2.0.0")])
            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(outcome.selected_versions["letters"], Version(major=1, minor=2, patch=0))
            self.assertIsInstance(outcome.derivation_steps, tuple)

    def test_solver_resolves_transitive_dependencies(self) -> None:
        """POSTCONDITIONS: resolve satisfies root and transitive dependencies with highest compatible releases."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                _release(
                    "letters",
                    Version(major=1, minor=0, patch=0),
                    (_dependency("numbers", ">=1.0.0"),),
                )
            )
            repository.register_package(_release("numbers", Version(major=1, minor=0, patch=0)))
            repository.register_package(_release("numbers", Version(major=1, minor=1, patch=0)))
            outcome = solver.resolve([_dependency("letters", ">=1.0.0 <2.0.0")])
            self.assertEqual(outcome.selected_versions["letters"], Version(major=1, minor=0, patch=0))
            self.assertEqual(outcome.selected_versions["numbers"], Version(major=1, minor=1, patch=0))

    def test_solver_reports_unsatisfiable_conflict(self) -> None:
        """PRECONDITIONS: mutually unsatisfiable constraints raise ResolutionConflictError with structured details."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                _release(
                    "letters",
                    Version(major=1, minor=0, patch=0),
                    (_dependency("numbers", ">=2.0.0"),),
                )
            )
            repository.register_package(_release("numbers", Version(major=1, minor=0, patch=0)))
            repository.register_package(_release("numbers", Version(major=2, minor=0, patch=0)))
            root_dependencies = [
                _dependency("letters", ">=1.0.0 <2.0.0"),
                _dependency("numbers", "<2.0.0"),
            ]
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve(root_dependencies)
            conflict = context.exception
            self.assertIsInstance(conflict.conflicting_packages, tuple)
            self.assertIsInstance(conflict.explanation, str)
            self.assertIn("letters", conflict.conflicting_packages)
            self.assertIn("numbers", conflict.conflicting_packages)

    def test_solver_backtracks_from_conflicting_candidate(self) -> None:
        """POSTCONDITIONS: a candidate whose dependency conflicts with an accumulated constraint is rejected and lower candidates still resolve."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                _release(
                    "letters",
                    Version(major=2, minor=0, patch=0),
                    (_dependency("numbers", ">=2.0.0"),),
                )
            )
            repository.register_package(
                _release(
                    "letters",
                    Version(major=1, minor=0, patch=0),
                    (_dependency("numbers", "<2.0.0"),),
                )
            )
            repository.register_package(_release("numbers", Version(major=1, minor=0, patch=0)))
            repository.register_package(_release("numbers", Version(major=1, minor=5, patch=0)))
            repository.register_package(_release("numbers", Version(major=2, minor=0, patch=0)))
            root_dependencies = [
                _dependency("letters", ">=1.0.0 <3.0.0"),
                _dependency("numbers", "<2.0.0"),
            ]
            outcome = solver.resolve(root_dependencies)
            self.assertEqual(outcome.selected_versions["letters"], Version(major=1, minor=0, patch=0))
            self.assertEqual(outcome.selected_versions["numbers"], Version(major=1, minor=5, patch=0))
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertGreaterEqual(len(outcome.derivation_steps), 1)
            for step in outcome.derivation_steps:
                self.assertIsInstance(step, str)

    def test_solver_rejects_candidate_conflicting_with_already_assigned_package(self) -> None:
        """POSTCONDITIONS: with the dependency target assigned first (single viable candidate), a dependent candidate violating its accumulated constraint is rejected and the next lower candidate resolves."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                _release(
                    "letters",
                    Version(major=2, minor=0, patch=0),
                    (_dependency("numbers", ">=2.0.0"),),
                )
            )
            repository.register_package(
                _release(
                    "letters",
                    Version(major=1, minor=0, patch=0),
                    (_dependency("numbers", "<2.0.0"),),
                )
            )
            repository.register_package(_release("numbers", Version(major=1, minor=0, patch=0)))
            repository.register_package(_release("numbers", Version(major=2, minor=0, patch=0)))
            root_dependencies = [
                _dependency("letters", ">=1.0.0 <3.0.0"),
                _dependency("numbers", "<2.0.0"),
            ]
            outcome = solver.resolve(root_dependencies)
            self.assertEqual(outcome.selected_versions["numbers"], Version(major=1, minor=0, patch=0))
            self.assertEqual(outcome.selected_versions["letters"], Version(major=1, minor=0, patch=0))
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertGreaterEqual(len(outcome.derivation_steps), 1)
            for step in outcome.derivation_steps:
                self.assertIsInstance(step, str)

    def test_solver_reports_conflict_when_all_candidates_violate_assigned_package(self) -> None:
        """PRECONDITIONS: when every dependent candidate violates the already-assigned package constraint, the conflict names both packages."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                _release(
                    "letters",
                    Version(major=2, minor=0, patch=0),
                    (_dependency("numbers", ">=2.0.0"),),
                )
            )
            repository.register_package(
                _release(
                    "letters",
                    Version(major=1, minor=5, patch=0),
                    (_dependency("numbers", ">=2.0.0"),),
                )
            )
            repository.register_package(_release("numbers", Version(major=1, minor=0, patch=0)))
            repository.register_package(_release("numbers", Version(major=2, minor=0, patch=0)))
            root_dependencies = [
                _dependency("letters", ">=1.0.0 <3.0.0"),
                _dependency("numbers", "<2.0.0"),
            ]
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve(root_dependencies)
            conflict = context.exception
            self.assertIn("letters", conflict.conflicting_packages)
            self.assertIn("numbers", conflict.conflicting_packages)

    def test_solver_conflict_on_transitive_dependency_with_zero_candidates(self) -> None:
        """PRECONDITIONS: a transitive dependency with zero viable releases restores the constraint mapping and names both packages."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                _release(
                    "letters",
                    Version(major=1, minor=0, patch=0),
                    (_dependency("numbers", ">=2.0.0"),),
                )
            )
            repository.register_package(_release("numbers", Version(major=1, minor=0, patch=0)))
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([_dependency("letters", ">=1.0.0")])
            conflict = context.exception
            self.assertIn("letters", conflict.conflicting_packages)
            self.assertIn("numbers", conflict.conflicting_packages)

    def test_solver_reports_unregistered_package_as_conflict(self) -> None:
        """PRECONDITIONS: unregistered packages are reported as conflict without leaking PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([_dependency("ghost", ">=1.0.0")])
            self.assertIsInstance(context.exception.conflicting_packages, tuple)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T01:04:21Z
# LAST_CHANGED: 2026-11-07T01:03:07Z
# CHANGE: Addressed feedback: (1) prerelease precedence now also covers equal numeric leading identifiers, asserting later numeric segments compare as integers ((1,2) < (1,10)), later string segments decide ((1,alpha) < (1,beta)), and fully identical sequences report equality; (2) reconstructed the already-assigned-package scenario so the dependency target has strictly fewer viable candidates (numbers held to 1.0.0 by root <2.0.0 while letters has two candidates) and is selected/assigned first, then added a success test asserting the conflicting letters 2.0.0 candidate is rejected and lower letters 1.0.0 resolves (with non-empty derivation steps) plus a conflict test where every letters candidate violates the assigned numbers constraint and ResolutionConflictError names both packages in conflicting_packages.
# COVERAGE_AUDIT: 2026-11-07T01:04:21Z
# QA_AUDIT: 2026-11-07T01:03:36Z
# --- END AUTOFAB METADATA ---
