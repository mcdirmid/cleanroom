"""Unit tests for semver_solver_impl per its grounding specification.

Covers the contracted postconditions, invariants, and checked preconditions of
``VersionEngine``, ``PackageRepository``, and ``DependencySolver``.
"""

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
    VersionRange,
)
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


def make_release(
    engine: VersionEngine,
    name: str,
    version_text: str,
    dependencies: tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Builds a release record from primitive package name and version text."""
    return PackageRelease(
        name=name,
        version=engine.parse_version(version_text),
        dependencies=dependencies,
    )


def make_dependency(
    engine: VersionEngine,
    name: str,
    range_text: str,
) -> PackageDependency:
    """Builds a dependency record from primitive package name and range text."""
    return PackageDependency(
        name=name,
        range_constraint=engine.parse_range(range_text),
    )


class VersionEngineParsingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_numeric_components(self) -> None:
        """POSTCONDITION semver.parse_version.valid_syntax: numeric triple becomes a Version record."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3")
            self.assertEqual((version.major, version.minor, version.patch), (1, 2, 3))
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ())
            self.assertFalse(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3")
            self.assertEqual(str(version), "1.2.3")

    def test_parse_version_prerelease_and_build_identifiers(self) -> None:
        """POSTCONDITION semver.parse_version.valid_syntax: prerelease and build tuples are extracted."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("2.0.0-alpha.1+20130313144700")
            self.assertEqual((version.major, version.minor, version.patch), (2, 0, 0))
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("20130313144700",))
            self.assertTrue(version.is_prerelease)
            self.assertEqual(version.format(), "2.0.0-alpha.1+20130313144700")

    def test_parse_version_numeric_prerelease_identifiers(self) -> None:
        """POSTCONDITION semver.parse_version.valid_syntax: prerelease identifiers stay ordered text segments."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.0.0-alpha.11")
            self.assertEqual(version.prerelease, ("alpha", "11"))
            self.assertEqual(version.build, ())
            self.assertEqual(version.format(), "1.0.0-alpha.11")

    def test_parse_version_leading_zeroes_rejected(self) -> None:
        """PRECONDITION semver.parse_version.leading_zero_grammar: leading zeroes raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("01.2.3", "1.02.3", "1.2.03", "1.2.3-01", "1.2.3-alpha.01"):
                with self.assertRaises(InvalidVersionError) as raised:
                    engine.parse_version(text)
                self.assertEqual(raised.exception.raw_text, text)

    def test_parse_version_malformed_grammar_rejected(self) -> None:
        """PRECONDITION semver.parse_version.leading_zero_grammar: grammar violations raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("", "1", "1.2", "1.2.3.4", "v1.2.3", "1.2.3-", "1.2.3+", "1.2.3-alpha..1"):
                with self.assertRaises(InvalidVersionError) as raised:
                    engine.parse_version(text)
                self.assertEqual(raised.exception.raw_text, text)


class VersionEnginePrecedenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_compare_precedence_numeric_components(self) -> None:
        """POSTCONDITION semver.compare_precedence.numerical_components: numeric, not lexical, comparison."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            low = engine.parse_version("1.2.3")
            high = engine.parse_version("1.10.0")
            self.assertLess(engine.compare_precedence(low, high), 0)
            self.assertGreater(engine.compare_precedence(high, low), 0)
            self.assertEqual(engine.compare_precedence(low, low), 0)

    def test_compare_precedence_tri_state(self) -> None:
        """POSTCONDITION semver.compare_precedence.tri_state: negative, zero, and positive results."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            older = engine.parse_version("0.1.0")
            newer = engine.parse_version("0.2.0")
            self.assertLess(engine.compare_precedence(older, newer), 0)
            self.assertEqual(engine.compare_precedence(newer, newer), 0)
            self.assertGreater(engine.compare_precedence(newer, older), 0)

    def test_compare_precedence_normal_ranks_above_prerelease(self) -> None:
        """POSTCONDITION semver.compare_precedence.normal_vs_prerelease: normal version outranks prerelease."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            normal = engine.parse_version("1.0.0")
            prerelease = engine.parse_version("1.0.0-rc.1")
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)

    def test_compare_precedence_prerelease_ordering(self) -> None:
        """POSTCONDITION semver.compare_precedence.prerelease_ordering: RFC 9 pre-release sequence."""
        ordered = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            versions = [engine.parse_version(text) for text in ordered]
            for smaller, larger in zip(versions, versions[1:]):
                self.assertLess(engine.compare_precedence(smaller, larger), 0)
                self.assertGreater(engine.compare_precedence(larger, smaller), 0)

    def test_compare_precedence_build_metadata_ignored(self) -> None:
        """POSTCONDITION semver.compare_precedence.build_metadata_ignored: build metadata never affects order."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            first = engine.parse_version("1.0.0+build.1")
            second = engine.parse_version("1.0.0+build.2")
            self.assertEqual(engine.compare_precedence(first, second), 0)
            prerelease_first = engine.parse_version("1.0.0-rc.1+build.7")
            prerelease_second = engine.parse_version("1.0.0-rc.1+build.9")
            self.assertEqual(engine.compare_precedence(prerelease_first, prerelease_second), 0)


class VersionRangeParsingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_range_basic_comparators(self) -> None:
        """POSTCONDITION semver.parse_range.comparators_and_prefixes: basic comparators parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in (">=1.0.0", ">1.0.0", "<=2.3.4", "<2.3.4", "==1.2.3", "=1.2.3", "!=1.2.3"):
                parsed = engine.parse_range(text)
                self.assertIsInstance(parsed, VersionRange)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_prefix_and_wildcard_forms(self) -> None:
        """POSTCONDITION semver.parse_range.comparators_and_prefixes: caret, tilde, and wildcard forms parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("^1.x", "~1.2.x", ">=1.x", "!=1.x", ">1.*", ">=*", "^1.2.3", "~1.2.3"):
                parsed = engine.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_wildcard_first_component_forms(self) -> None:
        """POSTCONDITION semver.parse_range.comparators_and_prefixes: wildcard-first expressions parse for every operator."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("*", "==*", "!=*", "<*", "<=*", ">*", "^*", "~*"):
                parsed = engine.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_build_metadata_bounds(self) -> None:
        """POSTCONDITION semver.parse_range.comparators_and_prefixes: build metadata bounds are full versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in (">=1.2.3+build.1", "==1.2.3+build.1", "1.0.0+build.1 - 2.0.0+build.2"):
                parsed = engine.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_semver_grammar_violations_rejected(self) -> None:
        """PRECONDITION semver.parse_range.malformed_syntax: SemVer grammar violations raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in (
                ">=1.0.0-",
                ">=1.0.0-alpha..1",
                ">=1.0.0-alpha_1",
                ">=1.0.0-01",
                ">=1.2.3.4",
                "1.x.3",
                ">=1.a.0",
                ">=1.0.0+",
                ">=1.0.0+build..1",
                ">=1.0.0+build_1",
                "1.0.0 - 2.0.0+",
            ):
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(text)
                self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_hyphen_bounds(self) -> None:
        """POSTCONDITION semver.parse_range.hyphen_ranges: hyphen ranges over full or wildcard bounds parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("1.0.0 - 2.x", "1.x - 2.x", "1.0.0 - 2.0.0"):
                parsed = engine.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_union_alternatives(self) -> None:
        """POSTCONDITION semver.parse_range.union_alternatives: '||' separated alternatives parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("1.0.0 || >=2.x")
            self.assertEqual(parsed.raw_text, "1.0.0 || >=2.x")

    def test_parse_range_trims_whitespace(self) -> None:
        """POSTCONDITION semver.parse_range.whitespace_trimming: surrounding whitespace is trimmed."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("   1.0.0   ")
            self.assertEqual(parsed.raw_text, "1.0.0")
            self.assertEqual(str(parsed), "1.0.0")
            union = engine.parse_range("  1.0.0 || 2.0.0  ")
            self.assertEqual(union.raw_text, "1.0.0 || 2.0.0")

    def test_parse_range_operator_whitespace(self) -> None:
        """POSTCONDITION semver.parse_range.operator_whitespace: whitespace after operators is allowed."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            spaced = engine.parse_range(">= 1.0.0")
            self.assertEqual(spaced.raw_text, ">= 1.0.0")
            spaced_wildcard = engine.parse_range(">= 1.x")
            self.assertEqual(spaced_wildcard.raw_text, ">= 1.x")

    def test_parse_range_whitespace_delimited_comparators(self) -> None:
        """POSTCONDITION semver.parse_range.whitespace_delimited: comparator sets are whitespace delimited."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range(">=1.0.0 <2.0.0")
            self.assertEqual(parsed.raw_text, ">=1.0.0 <2.0.0")

    def test_parse_range_bare_partials_rejected(self) -> None:
        """PRECONDITION semver.parse_range.bare_partials_prohibited: bare partials raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("1", "1.2", ">1.2", "^0.0", "1.2 - 2.3"):
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(text)
                self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_malformed_syntax_rejected(self) -> None:
        """PRECONDITION semver.parse_range.malformed_syntax: empty, comma, and empty union clauses raise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("", "   ", "1.0.0 ||", "|| 1.0.0", "1.0.0 || || 2.0.0", ">=1.0.0,<2.0.0", "1.0.0, 2.0.0"):
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(text)
                self.assertEqual(raised.exception.raw_range, text)


class VersionSatisfiesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_satisfies_boolean_match(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: every comparator in a clause must hold."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(engine.parse_version("1.5.0"), parsed, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), parsed, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.9.9"), parsed, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: satisfying at least one clause suffices."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("1.0.0 || 2.x")
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0"), parsed, False))
            self.assertTrue(engine.satisfies(engine.parse_version("2.5.0"), parsed, False))
            self.assertFalse(engine.satisfies(engine.parse_version("3.0.0"), parsed, False))

    def test_satisfies_caret_expansion(self) -> None:
        """POSTCONDITION semver.satisfies: caret ranges expand at the highest non-zero component."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            wildcard = engine.parse_range("^1.x")
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0"), wildcard, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.9.9"), wildcard, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), wildcard, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.9.0"), wildcard, False))
            full = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), full, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.9.0"), full, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.2"), full, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), full, False))

    def test_satisfies_tilde_expansion(self) -> None:
        """POSTCONDITION semver.satisfies: tilde ranges expand at the minor boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            full = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), full, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.9"), full, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.3.0"), full, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.2"), full, False))
            wildcard = engine.parse_range("~1.x")
            self.assertTrue(engine.satisfies(engine.parse_version("1.9.0"), wildcard, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), wildcard, False))

    def test_satisfies_wildcard_normalization(self) -> None:
        """POSTCONDITION semver.satisfies: wildcard and negation comparators normalize to inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            inclusive = engine.parse_range(">=1.x")
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0"), inclusive, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.4.2"), inclusive, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.9.0"), inclusive, False))
            exclusion = engine.parse_range("!=1.x")
            self.assertTrue(engine.satisfies(engine.parse_version("0.9.0"), exclusion, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.4.2"), exclusion, False))
            self.assertTrue(engine.satisfies(engine.parse_version("2.0.0"), exclusion, False))
            universal = engine.parse_range(">=*")
            self.assertTrue(engine.satisfies(engine.parse_version("0.0.1"), universal, False))
            self.assertTrue(engine.satisfies(engine.parse_version("99.99.99"), universal, False))

    def test_satisfies_hyphen_range_normalization(self) -> None:
        """POSTCONDITION semver.satisfies: hyphen ranges normalize to paired inequality bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0"), parsed, False))
            self.assertTrue(engine.satisfies(engine.parse_version("2.9.9"), parsed, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.9.0"), parsed, False))
            self.assertFalse(engine.satisfies(engine.parse_version("3.0.0"), parsed, False))

    def test_satisfies_excludes_prerelease_by_default(self) -> None:
        """POSTCONDITION semver.satisfies.prerelease_filter: prerelease excluded unless include_prerelease."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(engine.parse_version("1.0.0-alpha"), parsed, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.3-rc.1"), parsed, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0"), parsed, False))

    def test_satisfies_prerelease_explicit_target_allowed(self) -> None:
        """POSTCONDITION semver.satisfies.prerelease_filter: explicitly targeted prerelease matches."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            targeted = engine.parse_range(">=1.0.0-alpha")
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0-alpha"), targeted, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0-beta"), targeted, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.9.9-alpha"), targeted, False))
            other_triple = engine.parse_range(">=1.0.0-0")
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0-alpha"), other_triple, False))

    def test_satisfies_prerelease_opt_in_uses_precedence(self) -> None:
        """POSTCONDITION semver.satisfies.prerelease_inequality: opt-in compares by precedence only."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(engine.parse_version("1.0.0-alpha"), parsed, True))
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.1-alpha"), parsed, True))
            self.assertTrue(engine.satisfies(engine.parse_version("2.0.0-beta"), parsed, True))

    def test_satisfies_relational_comparators(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: !=, <=, and > comparators evaluate membership."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            excluded = engine.parse_range("!=1.2.3")
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.3"), excluded, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.4"), excluded, False))
            at_most = engine.parse_range("<=1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), at_most, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.0"), at_most, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.4"), at_most, False))
            above = engine.parse_range(">1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.4"), above, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.3"), above, False))

    def test_satisfies_wildcard_first_component_expressions(self) -> None:
        """POSTCONDITION semver.satisfies: wildcard-first expressions normalize to comparator inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            candidate = engine.parse_version("1.2.3")
            for text in ("*", "==*", "<=*", "^*", "~*"):
                self.assertTrue(engine.satisfies(candidate, engine.parse_range(text), False))
            self.assertTrue(engine.satisfies(engine.parse_version("0.0.0"), engine.parse_range("*"), False))
            for text in ("!=*", "<*", ">*"):
                self.assertFalse(engine.satisfies(candidate, engine.parse_range(text), False))
                self.assertFalse(engine.satisfies(engine.parse_version("0.0.0"), engine.parse_range(text), False))

    def test_satisfies_caret_zero_major_boundaries(self) -> None:
        """POSTCONDITION semver.satisfies: caret expansion honors the first non-zero component for zero-major ranges."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            zero_major_wildcard = engine.parse_range("^0.x")
            self.assertTrue(engine.satisfies(engine.parse_version("0.0.0"), zero_major_wildcard, False))
            self.assertTrue(engine.satisfies(engine.parse_version("0.9.9"), zero_major_wildcard, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.0.0"), zero_major_wildcard, False))
            zero_minor = engine.parse_range("^0.2.x")
            self.assertTrue(engine.satisfies(engine.parse_version("0.2.0"), zero_minor, False))
            self.assertTrue(engine.satisfies(engine.parse_version("0.2.9"), zero_minor, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.3.0"), zero_minor, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.1.9"), zero_minor, False))
            full_patch = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(engine.parse_version("0.0.3"), full_patch, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.0.4"), full_patch, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.0.2"), full_patch, False))
            wildcard_patch = engine.parse_range("^0.0.x")
            self.assertTrue(engine.satisfies(engine.parse_version("0.0.0"), wildcard_patch, False))
            self.assertTrue(engine.satisfies(engine.parse_version("0.0.9"), wildcard_patch, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.1.0"), wildcard_patch, False))

    def test_satisfies_ignores_build_metadata(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: build metadata never affects satisfaction."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            lower_bound = engine.parse_range(">=1.2.3+build.1")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3+build.9"), lower_bound, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.2+build.9"), lower_bound, False))
            equality = engine.parse_range("==1.2.3+build.2")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3+build.1"), equality, False))
            hyphen = engine.parse_range("1.0.0+build.1 - 2.0.0+build.2")
            self.assertTrue(engine.satisfies(engine.parse_version("2.0.0+build.9"), hyphen, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.1+build.9"), hyphen, False))


class PackageRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_register_package_orders_releases_descending(self) -> None:
        """POSTCONDITION semver.repo.descending_releases: releases are ordered by precedence descending."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release(engine, "alpha", "1.0.0"))
            repository.register_package(make_release(engine, "alpha", "2.0.0-rc.1"))
            repository.register_package(make_release(engine, "alpha", "1.5.0"))
            repository.register_package(make_release(engine, "alpha", "2.0.0"))
            releases = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in releases],
                [
                    engine.parse_version("2.0.0"),
                    engine.parse_version("2.0.0-rc.1"),
                    engine.parse_version("1.5.0"),
                    engine.parse_version("1.0.0"),
                ],
            )
            self.assertEqual([release.name for release in releases], ["alpha", "alpha", "alpha", "alpha"])

    def test_register_package_keeps_declared_dependencies(self) -> None:
        """POSTCONDITION semver.repo.register_release: the release record with dependencies is retained."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            release = make_release(
                engine,
                "beta",
                "1.0.0",
                (make_dependency(engine, "alpha", ">=1.0.0"),),
            )
            repository.register_package(release)
            releases = repository.get_releases("beta")
            self.assertEqual(len(releases), 1)
            self.assertIs(releases[0], release)

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITION semver.repo.descending_releases: get_releases yields a shallow copy."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release(engine, "gamma", "1.0.0"))
            repository.register_package(make_release(engine, "gamma", "1.1.0"))
            first = repository.get_releases("gamma")
            first.clear()
            self.assertEqual(len(repository.get_releases("gamma")), 2)

    def test_get_releases_missing_package_raises(self) -> None:
        """PRECONDITION semver.repo.missing_package: unregistered names raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as raised:
                repository.get_releases("ghost")
            self.assertEqual(raised.exception.package_name, "ghost")

    def test_has_package_reports_membership(self) -> None:
        """POSTCONDITION semver.repo.has_membership: membership reflects registered names only."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release(engine, "delta", "0.1.0"))
            self.assertTrue(repository.has_package("delta"))
            self.assertFalse(repository.has_package("omega"))

    def test_all_packages_returns_registered_names(self) -> None:
        """POSTCONDITION semver.repo.all_names: all registered package names are produced as a set."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release(engine, "delta", "0.1.0"))
            repository.register_package(make_release(engine, "epsilon", "0.1.0"))
            self.assertEqual(repository.all_packages(), {"delta", "epsilon"})


class DependencySolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_resolve_assigns_transitive_dependencies(self) -> None:
        """POSTCONDITION semver.solver.compatible_assignment: root and transitive packages are assigned."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                make_release(engine, "app", "1.0.0", (make_dependency(engine, "lib", ">=1.0.0"),))
            )
            repository.register_package(make_release(engine, "lib", "1.0.0"))
            repository.register_package(make_release(engine, "lib", "2.0.0"))
            outcome = solver.resolve([make_dependency(engine, "app", ">=1.0.0")])
            self.assertEqual(outcome.selected_versions["app"], engine.parse_version("1.0.0"))
            self.assertEqual(outcome.selected_versions["lib"], engine.parse_version("2.0.0"))
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_selects_highest_compatible_precedence(self) -> None:
        """POSTCONDITION semver.solver.highest_precedence: the highest compatible release is selected."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(make_release(engine, "lib", "1.0.0"))
            repository.register_package(make_release(engine, "lib", "1.5.0"))
            repository.register_package(make_release(engine, "lib", "2.0.0"))
            outcome = solver.resolve([make_dependency(engine, "lib", "<2.0.0")])
            self.assertEqual(outcome.selected_versions["lib"], engine.parse_version("1.5.0"))

    def test_resolve_intersects_transitive_constraints(self) -> None:
        """POSTCONDITION semver.solver.compatible_assignment: intersecting constraints narrow the selection."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                make_release(engine, "app", "1.0.0", (make_dependency(engine, "core", ">=1.0.0"),))
            )
            repository.register_package(
                make_release(engine, "tool", "1.0.0", (make_dependency(engine, "core", "<2.0.0"),))
            )
            repository.register_package(make_release(engine, "core", "1.0.0"))
            repository.register_package(make_release(engine, "core", "1.9.0"))
            repository.register_package(make_release(engine, "core", "2.1.0"))
            outcome = solver.resolve(
                [
                    make_dependency(engine, "app", ">=1.0.0"),
                    make_dependency(engine, "tool", ">=1.0.0"),
                ]
            )
            self.assertEqual(outcome.selected_versions["core"], engine.parse_version("1.9.0"))

    def test_resolve_conflicting_constraints_raise(self) -> None:
        """PRECONDITION semver.solver.unsatisfiable_conflict: unsatisfiable dependencies raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                make_release(engine, "app", "1.0.0", (make_dependency(engine, "lib", "<1.0.0"),))
            )
            repository.register_package(make_release(engine, "lib", "1.0.0"))
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([make_dependency(engine, "app", ">=1.0.0")])
            conflict = raised.exception
            self.assertIsInstance(conflict.conflicting_packages, tuple)
            self.assertIsInstance(conflict.explanation, str)
            self.assertTrue(conflict.explanation)

    def test_resolve_unregistered_package_raises_conflict(self) -> None:
        """PRECONDITION semver.solver.unsatisfiable_conflict: unregistered packages raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([make_dependency(engine, "missing", ">=1.0.0")])
            conflict = raised.exception
            self.assertIsInstance(conflict.conflicting_packages, tuple)
            self.assertIn("missing", conflict.conflicting_packages)
            self.assertIsInstance(conflict.explanation, str)
            self.assertTrue(conflict.explanation)

    def test_resolve_forward_check_detects_assigned_conflict(self) -> None:
        """PRECONDITION semver.solver.unsatisfiable_conflict: dependency on an incompatible assigned package raises."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(make_release(engine, "alpha", "1.0.0"))
            repository.register_package(
                make_release(engine, "zeta", "2.0.0", (make_dependency(engine, "alpha", "<1.0.0"),))
            )
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve(
                    [
                        make_dependency(engine, "alpha", ">=1.0.0"),
                        make_dependency(engine, "zeta", ">=1.0.0"),
                    ]
                )
            conflict = raised.exception
            self.assertIsInstance(conflict.conflicting_packages, tuple)
            self.assertIn("alpha", conflict.conflicting_packages)
            self.assertIn("zeta", conflict.conflicting_packages)
            self.assertIsInstance(conflict.explanation, str)
            self.assertTrue(conflict.explanation)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T02:14:45Z
# LAST_CHANGED: 2026-11-08T02:13:28Z
# CHANGE: Address build-metadata grammar feedback: extend parse_range malformed-syntax rejection to cover version tokens with a trailing '+' separator and no build identifiers (>=1.0.0+, and hyphen bound 1.0.0 - 2.0.0+), empty build identifiers (>=1.0.0+build..1), and build identifiers with non-alphanumeric-hyphen characters (>=1.0.0+build_1), all asserting InvalidRangeError with raw_range preserved.
# COVERAGE_AUDIT: 2026-11-08T02:14:45Z
# QA_AUDIT: 2026-11-08T02:14:32Z
# --- END AUTOFAB METADATA ---
