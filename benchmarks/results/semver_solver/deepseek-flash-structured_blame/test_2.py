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
    Version,
    VersionRange,
)
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


class SemverLifecycleTestCase(unittest.TestCase):
    """Base test case creating an isolated lifecycle registry for every test."""

    engine: VersionEngine
    repository: PackageRepository
    solver: DependencySolver

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def _version(self, text: str) -> Version:
        return self.engine.parse_version(text)

    def _range(self, text: str) -> VersionRange:
        return self.engine.parse_range(text)

    def _release(
        self,
        name: str,
        version: str,
        dependencies: Tuple[PackageDependency, ...] = (),
    ) -> PackageRelease:
        return PackageRelease(
            name=name,
            version=self._version(version),
            dependencies=dependencies,
        )

    def _dependency(self, name: str, range_text: str) -> PackageDependency:
        return PackageDependency(name=name, range_constraint=self._range(range_text))


class VersionEngineParseVersionTest(SemverLifecycleTestCase):
    """Verifies semver.parse_version.valid_syntax and leading_zero_grammar."""

    def test_parse_version_valid_syntax(self) -> None:
        """POSTCONDITIONS semver.parse_version.valid_syntax: a full SemVer string parses into a Version record."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            parsed = self.engine.parse_version("1.2.3")
            self.assertEqual(parsed, Version(major=1, minor=2, patch=3, prerelease=(), build=()))
            self.assertEqual(parsed.major, 1)
            self.assertEqual(parsed.minor, 2)
            self.assertEqual(parsed.patch, 3)
            self.assertEqual(parsed.prerelease, ())
            self.assertEqual(parsed.build, ())

    def test_parse_version_prerelease_and_build_segments(self) -> None:
        """POSTCONDITIONS semver.parse_version.valid_syntax: prerelease and build metadata tuples are extracted."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            parsed = self.engine.parse_version("0.1.2-alpha.1+build.7")
            self.assertEqual(parsed.major, 0)
            self.assertEqual(parsed.minor, 1)
            self.assertEqual(parsed.patch, 2)
            self.assertEqual(parsed.prerelease, ("alpha", "1"))
            self.assertEqual(parsed.build, ("build", "7"))

    def test_parse_version_leading_zeroes_rejected(self) -> None:
        """PRECONDITIONS semver.parse_version.leading_zero_grammar: leading zeroes MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            for text in ("01.2.3", "1.02.3", "1.2.03"):
                with self.assertRaises(InvalidVersionError) as raised:
                    self.engine.parse_version(text)
                self.assertEqual(raised.exception.raw_text, text)

    def test_parse_version_malformed_grammar_rejected(self) -> None:
        """PRECONDITIONS semver.parse_version.leading_zero_grammar: grammar violations MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            for text in ("", "1", "1.2", "v1.2.3", "1.2.3.4", "1.2.3-", "1..3"):
                with self.assertRaises(InvalidVersionError) as raised:
                    self.engine.parse_version(text)
                self.assertEqual(raised.exception.raw_text, text)


class VersionEngineComparePrecedenceTest(SemverLifecycleTestCase):
    """Verifies the compare_precedence postconditions across SemVer precedence rules."""

    def test_compare_numerical_components(self) -> None:
        """POSTCONDITIONS semver.compare_precedence.numerical_components and tri_state."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            self.assertLess(self.engine.compare_precedence(self._version("1.0.0"), self._version("2.0.0")), 0)
            self.assertLess(self.engine.compare_precedence(self._version("1.0.0"), self._version("1.1.0")), 0)
            self.assertLess(self.engine.compare_precedence(self._version("1.0.0"), self._version("1.0.1")), 0)
            self.assertEqual(self.engine.compare_precedence(self._version("1.0.0"), self._version("1.0.0")), 0)
            self.assertGreater(self.engine.compare_precedence(self._version("2.0.0"), self._version("1.9.9")), 0)

    def test_compare_normal_version_higher_than_prerelease(self) -> None:
        """POSTCONDITIONS semver.compare_precedence.normal_vs_prerelease."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            normal = self._version("1.0.0")
            prerelease = self._version("1.0.0-alpha")
            self.assertGreater(self.engine.compare_precedence(normal, prerelease), 0)
            self.assertLess(self.engine.compare_precedence(prerelease, normal), 0)

    def test_compare_prerelease_numeric_lower_than_string(self) -> None:
        """POSTCONDITIONS semver.compare_precedence.prerelease_ordering: numeric ranks below string."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            numeric = self._version("1.0.0-1")
            textual = self._version("1.0.0-alpha")
            self.assertLess(self.engine.compare_precedence(numeric, textual), 0)
            self.assertGreater(self.engine.compare_precedence(textual, numeric), 0)

    def test_compare_prerelease_numeric_segments_numerically(self) -> None:
        """POSTCONDITIONS semver.compare_precedence.prerelease_ordering: numeric segments compare as integers."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            lower = self._version("1.0.0-alpha.2")
            higher = self._version("1.0.0-alpha.10")
            self.assertLess(self.engine.compare_precedence(lower, higher), 0)
            self.assertGreater(self.engine.compare_precedence(higher, lower), 0)

    def test_compare_prerelease_string_segments_ascii(self) -> None:
        """POSTCONDITIONS semver.compare_precedence.prerelease_ordering: string segments compare ASCII-lexicographically."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                self.engine.compare_precedence(self._version("1.0.0-alpha"), self._version("1.0.0-beta")),
                0,
            )
            self.assertGreater(
                self.engine.compare_precedence(self._version("1.0.0-beta"), self._version("1.0.0-alpha")),
                0,
            )

    def test_compare_prerelease_longer_sequence_higher(self) -> None:
        """POSTCONDITIONS semver.compare_precedence.prerelease_ordering: a longer matching sequence ranks higher."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            shorter = self._version("1.0.0-alpha")
            longer = self._version("1.0.0-alpha.1")
            self.assertLess(self.engine.compare_precedence(shorter, longer), 0)
            self.assertGreater(self.engine.compare_precedence(longer, shorter), 0)

    def test_compare_equal_prerelease_identifiers(self) -> None:
        """POSTCONDITIONS semver.compare_precedence.tri_state and prerelease_ordering: equal identifiers compare equal."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            self.assertEqual(self.engine.compare_precedence(self._version("1.0.0-1"), self._version("1.0.0-1")), 0)
            self.assertEqual(
                self.engine.compare_precedence(self._version("1.0.0-alpha"), self._version("1.0.0-alpha")),
                0,
            )
            self.assertEqual(
                self.engine.compare_precedence(self._version("1.0.0-alpha.1"), self._version("1.0.0-alpha.1")),
                0,
            )

    def test_compare_build_metadata_ignored(self) -> None:
        """POSTCONDITIONS semver.compare_precedence.build_metadata_ignored."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            with_build_one = self._version("1.0.0+build.1")
            with_build_two = self._version("1.0.0+build.2")
            self.assertEqual(self.engine.compare_precedence(with_build_one, with_build_two), 0)
            self.assertEqual(self.engine.compare_precedence(with_build_two, with_build_one), 0)


class VersionEngineParseRangeTest(SemverLifecycleTestCase):
    """Verifies the parse_range postconditions and the bare-partial/malformed preconditions."""

    def test_parse_range_comparators_and_prefixes(self) -> None:
        """POSTCONDITIONS semver.parse_range.comparators_and_prefixes."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            for text in (
                "==1.2.3",
                "=1.2.4",
                "!=1.2.5",
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
                "^0.1.0",
                "~1.2.3",
            ):
                parsed = self.engine.parse_range(text)
                self.assertEqual(parsed.raw_text, text.strip())

    def test_parse_range_hyphen_ranges(self) -> None:
        """POSTCONDITIONS semver.parse_range.hyphen_ranges."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            hyphen_range = self.engine.parse_range("1.0.0 - 2.x")
            self.assertEqual(hyphen_range.raw_text, "1.0.0 - 2.x")
            wildcard_hyphen = self.engine.parse_range("1.x - 2.x")
            self.assertEqual(wildcard_hyphen.raw_text, "1.x - 2.x")
            full_hyphen = self.engine.parse_range("1.0.0 - 2.0.0")
            self.assertEqual(full_hyphen.raw_text, "1.0.0 - 2.0.0")

    def test_parse_range_union_alternatives(self) -> None:
        """POSTCONDITIONS semver.parse_range.union_alternatives."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            union = self.engine.parse_range(">=1.0.0 || <2.0.0")
            self.assertEqual(union.raw_text, ">=1.0.0 || <2.0.0")

    def test_parse_range_trims_surrounding_whitespace(self) -> None:
        """POSTCONDITIONS semver.parse_range.whitespace_trimming."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            trimmed = self.engine.parse_range("  >=1.0.0  ")
            self.assertEqual(trimmed.raw_text, ">=1.0.0")
            trimmed_union = self.engine.parse_range("  >=1.0.0 || <2.0.0  ")
            self.assertEqual(trimmed_union.raw_text, ">=1.0.0 || <2.0.0")

    def test_parse_range_accepts_operator_whitespace(self) -> None:
        """POSTCONDITIONS semver.parse_range.operator_whitespace."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            for text in (">= 1.0.0", ">= 1.x", "^ 1.2.3", "~ 1.2.3", "!= 1.x"):
                parsed = self.engine.parse_range(text)
                self.assertEqual(parsed.raw_text, text.strip())

    def test_parse_range_wildcard_operand_forms(self) -> None:
        """POSTCONDITIONS semver.parse_range.comparators_and_prefixes: wildcard operands with comparators, caret, and tilde parse."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            for text in (
                "*",
                "1.x",
                "!=*",
                ">*",
                "<=*",
                "<=1.x",
                "<1.x",
                "^*",
                "~*",
                "~1.x",
                "^1.x",
                ">1.*",
            ):
                parsed = self.engine.parse_range(text)
                self.assertEqual(parsed.raw_text, text.strip())

    def test_parse_range_bare_partials_rejected(self) -> None:
        """PRECONDITIONS semver.parse_range.bare_partials_prohibited."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            for text in ("1", "1.2", ">1.2", "^0.0", "~1.2", "1.2 - 2.3"):
                with self.assertRaises(InvalidRangeError) as raised:
                    self.engine.parse_range(text)
                self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_malformed_syntax_rejected(self) -> None:
        """PRECONDITIONS semver.parse_range.malformed_syntax."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidRangeError):
                self.engine.parse_range("")
            with self.assertRaises(InvalidRangeError):
                self.engine.parse_range("   ")
            for text in (">=1.0.0 ||", "|| >=1.0.0", ">=1.0.0, <2.0.0", ">=1.0.0 <"):
                with self.assertRaises(InvalidRangeError) as raised:
                    self.engine.parse_range(text)
                self.assertEqual(raised.exception.raw_range, text)


class VersionEngineSatisfiesTest(SemverLifecycleTestCase):
    """Verifies the satisfies postconditions for match, prerelease filtering, and prerelease inequality."""

    def test_satisfies_boolean_match(self) -> None:
        """POSTCONDITIONS semver.satisfies.boolean_match."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), self._range(">=1.0.0 <2.0.0"), False))
            self.assertFalse(self.engine.satisfies(self._version("2.0.0"), self._range(">=1.0.0 <2.0.0"), False))
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), self._range(">=1.x"), False))
            self.assertFalse(self.engine.satisfies(self._version("1.5.0"), self._range("!=1.x"), False))
            self.assertTrue(self.engine.satisfies(self._version("2.5.0"), self._range("!=1.x"), False))
            self.assertTrue(self.engine.satisfies(self._version("0.0.1"), self._range(">=*"), False))

    def test_satisfies_prefix_and_hyphen_expansions(self) -> None:
        """POSTCONDITIONS semver.satisfies.boolean_match: caret, tilde, and hyphen expansions."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            caret = self._range("^1.2.0")
            self.assertTrue(self.engine.satisfies(self._version("1.9.9"), caret, False))
            self.assertFalse(self.engine.satisfies(self._version("2.0.0"), caret, False))
            self.assertFalse(self.engine.satisfies(self._version("1.1.0"), caret, False))
            tilde = self._range("~1.2.0")
            self.assertTrue(self.engine.satisfies(self._version("1.2.9"), tilde, False))
            self.assertFalse(self.engine.satisfies(self._version("1.3.0"), tilde, False))
            hyphen = self._range("1.0.0 - 2.x")
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), hyphen, False))
            self.assertFalse(self.engine.satisfies(self._version("3.0.0"), hyphen, False))
            full_hyphen = self._range("1.0.0 - 2.0.0")
            self.assertTrue(self.engine.satisfies(self._version("1.0.0"), full_hyphen, False))
            self.assertTrue(self.engine.satisfies(self._version("2.0.0"), full_hyphen, False))
            self.assertFalse(self.engine.satisfies(self._version("2.0.1"), full_hyphen, False))
            self.assertFalse(self.engine.satisfies(self._version("0.9.9"), full_hyphen, False))

    def test_satisfies_relational_comparator_boundaries(self) -> None:
        """POSTCONDITIONS semver.satisfies.boolean_match: equality mismatch, inclusive-upper overshoot, and strict-greater equality."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            equal = self._range("==1.0.0")
            self.assertTrue(self.engine.satisfies(self._version("1.0.0"), equal, False))
            self.assertFalse(self.engine.satisfies(self._version("2.0.0"), equal, False))
            self.assertTrue(self.engine.satisfies(self._version("1.0.0"), self._range("=1.0.0"), False))
            inclusive_upper = self._range("<=1.0.0")
            self.assertTrue(self.engine.satisfies(self._version("1.0.0"), inclusive_upper, False))
            self.assertFalse(self.engine.satisfies(self._version("2.0.0"), inclusive_upper, False))
            strict_greater = self._range(">1.0.0")
            self.assertFalse(self.engine.satisfies(self._version("1.0.0"), strict_greater, False))
            self.assertTrue(self.engine.satisfies(self._version("1.0.1"), strict_greater, False))
            self.assertTrue(self.engine.satisfies(self._version("1.0.0"), self._range(">=1.0.0"), False))
            self.assertFalse(self.engine.satisfies(self._version("1.0.0"), self._range("<1.0.0"), False))
            self.assertFalse(self.engine.satisfies(self._version("1.0.0"), self._range("!=1.0.0"), False))

    def test_satisfies_wildcard_and_prefix_expansion_boundaries(self) -> None:
        """POSTCONDITIONS semver.satisfies.boolean_match: wildcard, caret, and tilde operand expansion boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            any_version = self._range("*")
            self.assertTrue(self.engine.satisfies(self._version("0.0.1"), any_version, False))
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), any_version, False))
            major_wildcard = self._range("1.x")
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), major_wildcard, False))
            self.assertFalse(self.engine.satisfies(self._version("0.9.9"), major_wildcard, False))
            self.assertFalse(self.engine.satisfies(self._version("2.0.0"), major_wildcard, False))
            not_any = self._range("!=*")
            self.assertFalse(self.engine.satisfies(self._version("0.0.1"), not_any, False))
            self.assertFalse(self.engine.satisfies(self._version("1.5.0"), not_any, False))
            greater_than_any = self._range(">*")
            self.assertFalse(self.engine.satisfies(self._version("0.0.1"), greater_than_any, False))
            self.assertFalse(self.engine.satisfies(self._version("1.5.0"), greater_than_any, False))
            at_most_any = self._range("<=*")
            self.assertTrue(self.engine.satisfies(self._version("0.0.1"), at_most_any, False))
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), at_most_any, False))
            at_most_major_wildcard = self._range("<=1.x")
            self.assertTrue(self.engine.satisfies(self._version("0.0.1"), at_most_major_wildcard, False))
            self.assertTrue(self.engine.satisfies(self._version("1.9.9"), at_most_major_wildcard, False))
            self.assertFalse(self.engine.satisfies(self._version("2.0.0"), at_most_major_wildcard, False))
            less_than_major_wildcard = self._range("<1.x")
            self.assertTrue(self.engine.satisfies(self._version("0.9.9"), less_than_major_wildcard, False))
            self.assertFalse(self.engine.satisfies(self._version("1.0.0"), less_than_major_wildcard, False))
            caret_any = self._range("^*")
            self.assertTrue(self.engine.satisfies(self._version("0.0.1"), caret_any, False))
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), caret_any, False))
            tilde_any = self._range("~*")
            self.assertTrue(self.engine.satisfies(self._version("0.0.1"), tilde_any, False))
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), tilde_any, False))
            tilde_major_wildcard = self._range("~1.x")
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), tilde_major_wildcard, False))
            self.assertFalse(self.engine.satisfies(self._version("0.9.9"), tilde_major_wildcard, False))
            self.assertFalse(self.engine.satisfies(self._version("2.0.0"), tilde_major_wildcard, False))
            greater_than_patch_wildcard = self._range(">1.*")
            self.assertTrue(self.engine.satisfies(self._version("2.0.0"), greater_than_patch_wildcard, False))
            self.assertFalse(self.engine.satisfies(self._version("1.9.9"), greater_than_patch_wildcard, False))
            caret_major_wildcard = self._range("^1.x")
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), caret_major_wildcard, False))
            self.assertFalse(self.engine.satisfies(self._version("2.0.0"), caret_major_wildcard, False))
            tilde_patch_wildcard = self._range("~1.2.x")
            self.assertTrue(self.engine.satisfies(self._version("1.2.9"), tilde_patch_wildcard, False))
            self.assertFalse(self.engine.satisfies(self._version("1.3.0"), tilde_patch_wildcard, False))
            greater_than_wildcard = self._range(">=1.x")
            self.assertTrue(self.engine.satisfies(self._version("1.5.0"), greater_than_wildcard, False))
            self.assertTrue(self.engine.satisfies(self._version("2.5.0"), greater_than_wildcard, False))
            not_major_wildcard = self._range("!=1.x")
            self.assertFalse(self.engine.satisfies(self._version("1.5.0"), not_major_wildcard, False))
            self.assertTrue(self.engine.satisfies(self._version("2.5.0"), not_major_wildcard, False))
            greater_than_all = self._range(">=*")
            self.assertTrue(self.engine.satisfies(self._version("0.0.1"), greater_than_all, False))

    def test_satisfies_prerelease_filter(self) -> None:
        """POSTCONDITIONS semver.satisfies.prerelease_filter."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            alpha = self._version("1.0.0-alpha")
            self.assertFalse(self.engine.satisfies(alpha, self._range(">=1.0.0"), False))
            self.assertTrue(self.engine.satisfies(alpha, self._range(">=1.0.0-alpha"), False))
            self.assertFalse(self.engine.satisfies(alpha, self._range("!=1.0.0-alpha"), False))

    def test_satisfies_prerelease_inequality_without_boundary_shift(self) -> None:
        """POSTCONDITIONS semver.satisfies.prerelease_inequality."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            alpha = self._version("1.0.0-alpha")
            self.assertFalse(self.engine.satisfies(alpha, self._range(">=1.0.0"), True))
            self.assertTrue(self.engine.satisfies(alpha, self._range(">=1.0.0-alpha"), True))
            self.assertTrue(self.engine.satisfies(alpha, self._range("<1.0.0"), True))
            self.assertTrue(self.engine.satisfies(alpha, self._range(">=*"), True))


class PackageRepositoryTest(SemverLifecycleTestCase):
    """Verifies repository registration, indexing, lookup failure, and copy semantics."""

    def test_register_package_and_get_releases_descending(self) -> None:
        """POSTCONDITIONS semver.repo.register_release and semver.repo.descending_releases."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            self.repository = scope.get_singleton(PackageRepository)
            self.repository.register_package(self._release("pkg", "1.0.0"))
            self.repository.register_package(self._release("pkg", "2.0.0"))
            self.repository.register_package(self._release("pkg", "1.5.0"))
            versions = [release.version for release in self.repository.get_releases("pkg")]
            self.assertEqual(
                versions,
                [Version(2, 0, 0), Version(1, 5, 0), Version(1, 0, 0)],
            )

    def test_register_package_preserves_dependencies(self) -> None:
        """POSTCONDITIONS semver.repo.register_release preserves declared dependencies on lookup."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            self.repository = scope.get_singleton(PackageRepository)
            dependency = self._dependency("lib", ">=1.0.0 <2.0.0")
            self.repository.register_package(self._release("app", "1.0.0", (dependency,)))
            releases = self.repository.get_releases("app")
            self.assertEqual(len(releases), 1)
            self.assertEqual(releases[0].dependencies, (dependency,))

    def test_has_package_and_all_packages(self) -> None:
        """POSTCONDITIONS semver.repo.has_membership and semver.repo.all_names."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            self.repository = scope.get_singleton(PackageRepository)
            self.assertFalse(self.repository.has_package("pkg"))
            self.repository.register_package(self._release("pkg", "1.0.0"))
            self.repository.register_package(self._release("other", "1.0.0"))
            self.assertTrue(self.repository.has_package("pkg"))
            self.assertFalse(self.repository.has_package("missing"))
            self.assertEqual(self.repository.all_packages(), {"pkg", "other"})

    def test_get_releases_missing_package_raises(self) -> None:
        """PRECONDITIONS semver.repo.missing_package."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as raised:
                repository.get_releases("ghost")
            self.assertEqual(raised.exception.package_name, "ghost")

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITIONS semver.repo.descending_releases: callers receive a shallow copy of the list."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(self._release("pkg", "1.0.0"))
            repository.register_package(self._release("pkg", "2.0.0"))
            releases = repository.get_releases("pkg")
            releases.clear()
            self.assertEqual(len(repository.get_releases("pkg")), 2)


class DependencySolverTest(SemverLifecycleTestCase):
    """Verifies solver happy paths, highest-precedence selection, and conflict reporting."""

    def test_resolve_compatible_assignment_highest_precedence(self) -> None:
        """POSTCONDITIONS semver.solver.compatible_assignment and semver.solver.highest_precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                self._release("app", "1.0.0", (self._dependency("lib", ">=1.0.0 <2.0.0"),))
            )
            repository.register_package(
                self._release("app", "2.0.0", (self._dependency("lib", ">=2.0.0"),))
            )
            repository.register_package(self._release("lib", "1.0.0"))
            repository.register_package(self._release("lib", "2.0.0"))
            outcome = solver.resolve([self._dependency("app", ">=1.0.0")])
            self.assertEqual(outcome.selected_versions["app"], Version(2, 0, 0))
            self.assertEqual(outcome.selected_versions["lib"], Version(2, 0, 0))
            self.assertGreaterEqual(len(outcome.derivation_steps), 2)

    def test_resolve_prefers_highest_compatible_transitive_release(self) -> None:
        """POSTCONDITIONS semver.solver.compatible_assignment and semver.solver.highest_precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                self._release("app", "1.0.0", (self._dependency("lib", ">=1.0.0 <2.0.0"),))
            )
            repository.register_package(self._release("lib", "1.0.0"))
            repository.register_package(self._release("lib", "1.5.0"))
            repository.register_package(self._release("lib", "2.0.0"))
            outcome = solver.resolve([self._dependency("app", ">=1.0.0")])
            self.assertEqual(outcome.selected_versions["app"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 5, 0))
            self.assertGreaterEqual(len(outcome.derivation_steps), 2)

    def test_resolve_unsatisfiable_root_constraints_reports_conflict(self) -> None:
        """PRECONDITIONS semver.solver.unsatisfiable_conflict."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(self._release("app", "1.0.0"))
            repository.register_package(self._release("app", "2.0.0"))
            root = [
                self._dependency("app", ">=2.0.0"),
                self._dependency("app", "<1.0.0"),
            ]
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve(root)
            self.assertIn("app", raised.exception.conflicting_packages)
            self.assertTrue(raised.exception.explanation)

    def test_resolve_transitive_conflict_reports_conflict(self) -> None:
        """PRECONDITIONS semver.solver.unsatisfiable_conflict: transitive conflicts backtrack into a conflict."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(self._release("dep", "1.0.0"))
            repository.register_package(
                self._release("top", "1.0.0", (self._dependency("dep", ">=2.0.0"),))
            )
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([self._dependency("top", ">=1.0.0")])
            self.assertIn("dep", raised.exception.conflicting_packages)
            self.assertTrue(raised.exception.explanation)

    def test_resolve_assigned_dependency_range_violation_reports_conflict(self) -> None:
        """PRECONDITIONS semver.solver.unsatisfiable_conflict: a dependency on an already-assigned package with a violating range backtracks and reports conflict."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(self._release("a", "1.0.0"))
            repository.register_package(
                self._release("b", "1.0.0", (self._dependency("a", ">=2.0.0"),))
            )
            root = [
                self._dependency("a", ">=1.0.0"),
                self._dependency("b", ">=1.0.0"),
            ]
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve(root)
            self.assertIn("a", raised.exception.conflicting_packages)
            self.assertIn("b", raised.exception.conflicting_packages)
            self.assertTrue(raised.exception.explanation)

    def test_resolve_missing_package_reports_conflict_not_lookup_error(self) -> None:
        """PRECONDITIONS semver.solver.unsatisfiable_conflict: missing packages surface as ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            self.engine = scope.get_singleton(VersionEngine)
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([self._dependency("missing", ">=1.0.0")])
            self.assertIn("missing", raised.exception.conflicting_packages)
            self.assertTrue(raised.exception.explanation)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T02:49:26Z
# LAST_CHANGED: 2026-11-08T02:48:48Z
# CHANGE: Resolved all five coverage feedback items: added equal-numeric/equal-string/equal-sequence prerelease precedence endpoints; relational comparator mismatch branches (equality mismatch, inclusive-upper overshoot, strict-greater equality, >= equality, < and != mismatch); wildcard/caret/tilde operand expansion boundaries (*, 1.x, !=*, >*, <=*, <=1.x, <1.x, ^*, ~*, ~1.x, >1.*, ^1.x, ~1.2.x, >=1.x, !=1.x, >=*) with parse_range acceptance for those operand forms; hyphen range with a full-version inclusive upper bound (1.0.0 - 2.0.0); and a solver scenario where a candidate release depends on an already-assigned package with a violating range, forcing the assigned-dependency conflict branch to backtrack and report ResolutionConflictError.
# COVERAGE_AUDIT: 2026-11-08T02:49:26Z
# QA_AUDIT: 2026-11-08T02:49:13Z
# --- END AUTOFAB METADATA ---
