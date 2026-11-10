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


def make_version(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> Version:
    """Wraps primitive version components into an immutable Version record."""
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def make_range(raw_text: str) -> VersionRange:
    """Wraps raw range text into an immutable VersionRange record."""
    return VersionRange(raw_text=raw_text)


def make_dependency(name: str, raw_text: str) -> PackageDependency:
    """Wraps a package name and raw range text into a PackageDependency record."""
    return PackageDependency(name=name, range_constraint=make_range(raw_text))


class VersionEngineParseVersionTest(unittest.TestCase):
    """Verifies VersionEngine.parse_version postconditions and checked preconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_release_version(self) -> None:
        """POSTCONDITIONS: valid SemVer 2.0.0 strings parse into Version records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3")
            self.assertEqual(version, make_version(1, 2, 3))
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ())
            self.assertFalse(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3")
            self.assertEqual(str(version), "1.2.3")

    def test_parse_prerelease_and_build_metadata(self) -> None:
        """POSTCONDITIONS: prerelease and build identifiers are captured as tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))
            self.assertTrue(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3-alpha.1+build.5")
            self.assertEqual(str(version), "1.2.3-alpha.1+build.5")

    def test_parse_build_metadata_only(self) -> None:
        """POSTCONDITIONS: build metadata alone does not mark a version as prerelease."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("2.0.0+build.7")
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ("build", "7"))
            self.assertFalse(version.is_prerelease)
            self.assertEqual(version.format(), "2.0.0+build.7")

    def test_parse_version_leading_zero_raises(self) -> None:
        """PRECONDITIONS: leading zeroes in numeric identifiers raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidVersionError) as context:
                engine.parse_version("01.2.3")
            self.assertEqual(context.exception.raw_text, "01.2.3")
            with self.assertRaises(InvalidVersionError) as context:
                engine.parse_version("1.02.3")
            self.assertEqual(context.exception.raw_text, "1.02.3")
            with self.assertRaises(InvalidVersionError):
                engine.parse_version("1.2.03")

    def test_parse_version_malformed_raises(self) -> None:
        """PRECONDITIONS: grammar-violating strings raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidVersionError) as context:
                engine.parse_version("not-a-version")
            self.assertEqual(context.exception.raw_text, "not-a-version")
            with self.assertRaises(InvalidVersionError) as context:
                engine.parse_version("1.2")
            self.assertEqual(context.exception.raw_text, "1.2")
            with self.assertRaises(InvalidVersionError):
                engine.parse_version("")


class VersionEngineComparePrecedenceTest(unittest.TestCase):
    """Verifies VersionEngine.compare_precedence postconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_compare_numeric_components(self) -> None:
        """POSTCONDITIONS: major, minor, and patch compare numerically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(make_version(1, 0, 0), make_version(2, 0, 0)), 0)
            self.assertGreater(engine.compare_precedence(make_version(2, 0, 0), make_version(1, 0, 0)), 0)
            self.assertLess(engine.compare_precedence(make_version(1, 0, 0), make_version(1, 1, 0)), 0)
            self.assertLess(engine.compare_precedence(make_version(1, 1, 0), make_version(1, 1, 1)), 0)
            self.assertEqual(engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 3)), 0)

    def test_compare_normal_version_above_prerelease(self) -> None:
        """POSTCONDITIONS: normal versions rank above prereleases sharing numeric components."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            prerelease = make_version(1, 0, 0, ("alpha",))
            normal = make_version(1, 0, 0)
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)

    def test_compare_prerelease_identifiers(self) -> None:
        """POSTCONDITIONS: prerelease segments compare by length, numerics, and ASCII order."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha",)),
                    make_version(1, 0, 0, ("alpha", "1")),
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha", "1")),
                    make_version(1, 0, 0, ("alpha", "beta")),
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha", "beta")),
                    make_version(1, 0, 0, ("beta",)),
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("beta", "2")),
                    make_version(1, 0, 0, ("beta", "11")),
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("rc", "1")),
                    make_version(1, 0, 0),
                ),
                0,
            )

    def test_compare_equal_prerelease_identifiers(self) -> None:
        """POSTCONDITIONS: identical numeric prerelease identifiers compare equal."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("1",)),
                    make_version(1, 0, 0, ("1",)),
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha", "2")),
                    make_version(1, 0, 0, ("alpha", "2")),
                ),
                0,
            )

    def test_compare_numeric_prerelease_ranks_below_alphanumeric(self) -> None:
        """POSTCONDITIONS: numeric prerelease segments rank lower than string segments."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("1",)),
                    make_version(1, 0, 0, ("alpha",)),
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha",)),
                    make_version(1, 0, 0, ("1",)),
                ),
                0,
            )

    def test_compare_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: build metadata is ignored entirely for precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(
                    make_version(1, 0, 0, build=("x",)),
                    make_version(1, 0, 0, build=("y",)),
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    make_version(1, 0, 0),
                    make_version(1, 0, 0, build=("y",)),
                ),
                0,
            )


class VersionEngineParseRangeTest(unittest.TestCase):
    """Verifies VersionEngine.parse_range postconditions and checked preconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_range_trims_surrounding_whitespace(self) -> None:
        """POSTCONDITIONS: raw_text stores the trimmed range expression."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = engine.parse_range("  >=1.0.0 <2.0.0  ")
            self.assertEqual(version_range.raw_text, ">=1.0.0 <2.0.0")
            self.assertEqual(str(version_range), ">=1.0.0 <2.0.0")

    def test_parse_range_accepts_operator_whitespace(self) -> None:
        """POSTCONDITIONS: optional whitespace between operator and version is accepted."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = engine.parse_range(">= 1.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), version_range, False))

    def test_parse_range_accepts_supported_forms(self) -> None:
        """POSTCONDITIONS: comparators, caret, tilde, wildcards, hyphen, and unions parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for raw_text in (
                "==1.0.0",
                "=1.0.0",
                "!=1.0.0",
                "<1.0.0",
                "<=1.0.0",
                ">1.0.0",
                ">=1.0.0",
                "^1.2.3",
                "^0.0.0",
                "^0.0.3",
                "~1.2.3",
                ">=1.x",
                "!=1.x",
                "^1.x",
                "^0.2.x",
                "^1.2.x",
                "~1.2.x",
                ">=*",
                "^*",
                "~*",
                "!=*",
                "*",
                "=*",
                ">*",
                "<*",
                "<=*",
                "1.x",
                "==1.x",
                ">1.x",
                "<1.x",
                "<=1.x",
                ">= 1.x",
                "1.0.0 - 2.x",
                "1.0.0 - 2.0.0",
                "1.x - 2.x",
                "* - *",
                "1.0.0 || 2.0.0",
            ):
                self.assertIsInstance(engine.parse_range(raw_text), VersionRange)

    def test_parse_range_empty_raises(self) -> None:
        """PRECONDITIONS: empty or whitespace-only range text raises InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidRangeError) as context:
                engine.parse_range("")
            self.assertEqual(context.exception.raw_range, "")
            with self.assertRaises(InvalidRangeError) as context:
                engine.parse_range("   ")
            self.assertEqual(context.exception.raw_range, "   ")

    def test_parse_range_comma_raises(self) -> None:
        """PRECONDITIONS: comma-delimited comparators raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidRangeError) as context:
                engine.parse_range(">=1.0.0, <2.0.0")
            self.assertEqual(context.exception.raw_range, ">=1.0.0, <2.0.0")

    def test_parse_range_empty_union_clause_raises(self) -> None:
        """PRECONDITIONS: empty union clauses raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidRangeError) as context:
                engine.parse_range(">=1.0.0 || ")
            self.assertEqual(context.exception.raw_range, ">=1.0.0 || ")

    def test_parse_range_bare_partial_raises(self) -> None:
        """PRECONDITIONS: bare partial versions lacking wildcards raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidRangeError) as context:
                engine.parse_range("1")
            self.assertEqual(context.exception.raw_range, "1")
            with self.assertRaises(InvalidRangeError):
                engine.parse_range("1.2")
            with self.assertRaises(InvalidRangeError):
                engine.parse_range(">1.2")
            with self.assertRaises(InvalidRangeError):
                engine.parse_range("^0.0")
            with self.assertRaises(InvalidRangeError):
                engine.parse_range("1.2 - 2.3")


class VersionEngineSatisfiesTest(unittest.TestCase):
    """Verifies VersionEngine.satisfies postconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_satisfies_comparator_operators(self) -> None:
        """POSTCONDITIONS: relational and equality comparators match by precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), make_range("==1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), make_range("=1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 4), make_range("==1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), make_range("!=1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 4), make_range("!=1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 2), make_range("<1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), make_range("<1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), make_range("<=1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 4), make_range("<=1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 4), make_range(">1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), make_range(">1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), make_range(">=1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), make_range(">=1.2.3"), False))

    def test_satisfies_clause_requires_all_comparators(self) -> None:
        """POSTCONDITIONS: a clause matches only when every comparator is satisfied."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), version_range, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITIONS: at least one satisfied union clause makes the range match."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            exact_union = make_range("1.0.0 || 2.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), exact_union, False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), exact_union, False))
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), exact_union, False))
            clause_union = make_range(">=1.0.0 <2.0.0 || >=3.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), clause_union, False))
            self.assertFalse(engine.satisfies(make_version(2, 5, 0), clause_union, False))
            self.assertTrue(engine.satisfies(make_version(3, 5, 0), clause_union, False))

    def test_satisfies_wildcard_lower_bounds(self) -> None:
        """POSTCONDITIONS: '>=1.x' expands to >=1.0.0 and '>=*' matches all versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            at_least_major_one = make_range(">=1.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), at_least_major_one, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), at_least_major_one, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), at_least_major_one, False))
            any_version = make_range(">=*")
            self.assertTrue(engine.satisfies(make_version(0, 0, 1), any_version, False))
            self.assertTrue(engine.satisfies(make_version(99, 99, 99), any_version, False))

    def test_satisfies_caret_wildcard(self) -> None:
        """POSTCONDITIONS: '^1.x' expands to >=1.0.0 <2.0.0."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range("^1.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), version_range, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), version_range, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), version_range, False))

    def test_satisfies_tilde_wildcard(self) -> None:
        """POSTCONDITIONS: '~1.x' expands to >=1.0.0 <2.0.0."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range("~1.x")
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), version_range, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), version_range, False))

    def test_satisfies_not_equal_wildcard(self) -> None:
        """POSTCONDITIONS: '!=1.x' expands to <1.0.0 || >=2.0.0."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range("!=1.x")
            self.assertTrue(engine.satisfies(make_version(0, 5, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), version_range, False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), version_range, False))

    def test_satisfies_caret_full_version(self) -> None:
        """POSTCONDITIONS: caret expands to the first non-zero component boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            major_caret = make_range("^1.2.3")
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), major_caret, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), major_caret, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), major_caret, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), major_caret, False))
            minor_caret = make_range("^0.2.3")
            self.assertTrue(engine.satisfies(make_version(0, 2, 3), minor_caret, False))
            self.assertTrue(engine.satisfies(make_version(0, 2, 9), minor_caret, False))
            self.assertFalse(engine.satisfies(make_version(0, 3, 0), minor_caret, False))
            self.assertFalse(engine.satisfies(make_version(0, 2, 2), minor_caret, False))

    def test_satisfies_tilde_full_version(self) -> None:
        """POSTCONDITIONS: tilde expands to lower bound and next minor boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range("~1.2.3")
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), version_range, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), version_range, False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), version_range, False))

    def test_satisfies_hyphen_range_with_wildcard(self) -> None:
        """POSTCONDITIONS: '1.0.0 - 2.x' expands to >=1.0.0 <3.0.0."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), version_range, False))
            self.assertTrue(engine.satisfies(make_version(2, 9, 9), version_range, False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), version_range, False))

    def test_satisfies_caret_all_zero_numeric_base(self) -> None:
        """POSTCONDITIONS: caret on an all-zero base uses the patch component boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            zero_caret = make_range("^0.0.0")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), zero_caret, False))
            self.assertFalse(engine.satisfies(make_version(0, 0, 1), zero_caret, False))
            self.assertFalse(engine.satisfies(make_version(0, 1, 0), zero_caret, False))
            patch_caret = make_range("^0.0.3")
            self.assertTrue(engine.satisfies(make_version(0, 0, 3), patch_caret, False))
            self.assertFalse(engine.satisfies(make_version(0, 0, 4), patch_caret, False))
            self.assertFalse(engine.satisfies(make_version(0, 1, 0), patch_caret, False))

    def test_satisfies_caret_wildcard_operands(self) -> None:
        """POSTCONDITIONS: caret on partial wildcards expands at first non-zero boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            minor_caret = make_range("^0.2.x")
            self.assertTrue(engine.satisfies(make_version(0, 2, 0), minor_caret, False))
            self.assertTrue(engine.satisfies(make_version(0, 2, 9), minor_caret, False))
            self.assertFalse(engine.satisfies(make_version(0, 3, 0), minor_caret, False))
            self.assertFalse(engine.satisfies(make_version(0, 1, 9), minor_caret, False))
            major_caret = make_range("^1.2.x")
            self.assertTrue(engine.satisfies(make_version(1, 2, 0), major_caret, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), major_caret, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), major_caret, False))
            self.assertFalse(engine.satisfies(make_version(1, 1, 9), major_caret, False))
            fully_wildcarded = make_range("^*")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), fully_wildcarded, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), fully_wildcarded, False))
            self.assertTrue(engine.satisfies(make_version(99, 0, 0), fully_wildcarded, False))

    def test_satisfies_tilde_fully_wildcarded_operand(self) -> None:
        """POSTCONDITIONS: tilde on a fully wildcarded operand matches every version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range("~*")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), version_range, False))
            self.assertTrue(engine.satisfies(make_version(5, 0, 0), version_range, False))
            self.assertTrue(engine.satisfies(make_version(99, 99, 99), version_range, False))

    def test_satisfies_wildcard_equality(self) -> None:
        """POSTCONDITIONS: wildcard equality normalizes to a paired lower/upper range."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            bare_wildcard = make_range("1.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), bare_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), bare_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), bare_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), bare_wildcard, False))
            equality_wildcard = make_range("==1.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), equality_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), equality_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), equality_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), equality_wildcard, False))

    def test_satisfies_wildcard_relational_operators(self) -> None:
        """POSTCONDITIONS: >, <, and <= on wildcards normalize to paired inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            greater_wildcard = make_range(">1.x")
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), greater_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(1, 9, 9), greater_wildcard, False))
            less_wildcard = make_range("<1.x")
            self.assertTrue(engine.satisfies(make_version(0, 9, 9), less_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), less_wildcard, False))
            le_wildcard = make_range("<=1.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), le_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), le_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), le_wildcard, False))

    def test_satisfies_wildcard_inequality_over_all_versions_is_empty(self) -> None:
        """POSTCONDITIONS: '!=*' normalizes to the empty set that matches no version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range("!=*")
            self.assertFalse(engine.satisfies(make_version(0, 0, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), version_range, False))
            self.assertFalse(engine.satisfies(make_version(99, 0, 0), version_range, False))

    def test_satisfies_fully_wildcarded_operand_comparators(self) -> None:
        """POSTCONDITIONS: each comparator on a fully wildcarded operand normalizes its set."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            equality_wildcard = make_range("*")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), equality_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), equality_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(99, 0, 0), equality_wildcard, False))
            equals_wildcard = make_range("=*")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), equals_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), equals_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(99, 0, 0), equals_wildcard, False))
            greater_wildcard = make_range(">*")
            self.assertFalse(engine.satisfies(make_version(0, 0, 0), greater_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), greater_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(99, 0, 0), greater_wildcard, False))
            less_wildcard = make_range("<*")
            self.assertFalse(engine.satisfies(make_version(0, 0, 0), less_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), less_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(99, 0, 0), less_wildcard, False))
            le_wildcard = make_range("<=*")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), le_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), le_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(99, 0, 0), le_wildcard, False))

    def test_satisfies_contradictory_clause_matches_nothing(self) -> None:
        """POSTCONDITIONS: an unsatisfiable clause matches no candidate version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range(">2.0.0 <1.0.0")
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(0, 5, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(2, 5, 0), version_range, False))

    def test_satisfies_hyphen_exact_upper_bound(self) -> None:
        """POSTCONDITIONS: a full-version upper hyphen bound is inclusive."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version_range = make_range("1.0.0 - 2.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), version_range, False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), version_range, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 1), version_range, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), version_range, False))

    def test_satisfies_fully_wildcarded_hyphen_range(self) -> None:
        """POSTCONDITIONS: a fully wildcarded hyphen range matches every version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            any_version = make_range("* - *")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), any_version, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), any_version, False))
            self.assertTrue(engine.satisfies(make_version(99, 0, 0), any_version, False))
            wildcard_lower = make_range("1.x - 2.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), wildcard_lower, False))
            self.assertTrue(engine.satisfies(make_version(2, 9, 9), wildcard_lower, False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), wildcard_lower, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), wildcard_lower, False))

    def test_satisfies_operator_whitespace_with_wildcard(self) -> None:
        """POSTCONDITIONS: '>= 1.x' is equivalent to '>=1.x'."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            spaced = engine.parse_range(">= 1.x")
            compact = engine.parse_range(">=1.x")
            for version in (
                make_version(1, 0, 0),
                make_version(1, 9, 9),
                make_version(0, 9, 9),
                make_version(2, 0, 0),
            ):
                self.assertEqual(
                    engine.satisfies(version, spaced, False),
                    engine.satisfies(version, compact, False),
                )
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), spaced, False))
            self.assertFalse(engine.satisfies(make_version(0, 5, 0), spaced, False))

    def test_satisfies_excludes_prerelease_without_opt_in(self) -> None:
        """POSTCONDITIONS: prereleases fail non-prerelease ranges unless explicitly targeted."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertFalse(
                engine.satisfies(make_version(1, 0, 0, ("alpha",)), make_range(">=1.0.0"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(1, 2, 0, ("beta",)), make_range(">=1.0.0"), False)
            )
            self.assertTrue(
                engine.satisfies(
                    make_version(1, 0, 0, ("alpha",)),
                    make_range(">=1.0.0-alpha"),
                    False,
                )
            )

    def test_satisfies_prerelease_opt_in_uses_precedence(self) -> None:
        """POSTCONDITIONS: include_prerelease compares prereleases without shifting bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertFalse(
                engine.satisfies(make_version(1, 0, 0, ("alpha",)), make_range(">=1.0.0"), True)
            )
            self.assertTrue(
                engine.satisfies(make_version(1, 2, 0, ("beta",)), make_range(">=1.0.0"), True)
            )
            self.assertTrue(
                engine.satisfies(make_version(1, 0, 0, ("alpha",)), make_range("<1.0.0"), True)
            )


class PackageRepositoryTest(unittest.TestCase):
    """Verifies PackageRepository postconditions and checked preconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_register_package_and_get_releases_descending(self) -> None:
        """POSTCONDITIONS: releases are returned in descending version precedence order."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="alpha", version=make_version(1, 0, 0)))
            repository.register_package(PackageRelease(name="alpha", version=make_version(2, 0, 0)))
            repository.register_package(PackageRelease(name="alpha", version=make_version(1, 5, 0)))
            releases = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in releases],
                [make_version(2, 0, 0), make_version(1, 5, 0), make_version(1, 0, 0)],
            )
            self.assertEqual([release.name for release in releases], ["alpha", "alpha", "alpha"])

    def test_register_package_keeps_prerelease_ordering(self) -> None:
        """POSTCONDITIONS: prereleases sort below their normal release counterparts."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                PackageRelease(name="beta", version=make_version(1, 0, 0, ("alpha",)))
            )
            repository.register_package(PackageRelease(name="beta", version=make_version(1, 0, 0)))
            releases = repository.get_releases("beta")
            self.assertEqual(
                [release.version for release in releases],
                [make_version(1, 0, 0), make_version(1, 0, 0, ("alpha",))],
            )

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITIONS: mutating the returned list does not alter the repository."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="gamma", version=make_version(1, 0, 0)))
            releases = repository.get_releases("gamma")
            releases.append(PackageRelease(name="gamma", version=make_version(9, 9, 9)))
            self.assertEqual(len(releases), 2)
            self.assertEqual(len(repository.get_releases("gamma")), 1)

    def test_get_releases_unknown_package_raises(self) -> None:
        """PRECONDITIONS: unregistered package names raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as context:
                repository.get_releases("missing")
            self.assertEqual(context.exception.package_name, "missing")

    def test_has_package(self) -> None:
        """POSTCONDITIONS: has_package reflects repository membership."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("delta"))
            repository.register_package(PackageRelease(name="delta", version=make_version(1, 0, 0)))
            self.assertTrue(repository.has_package("delta"))
            self.assertFalse(repository.has_package("epsilon"))

    def test_all_packages(self) -> None:
        """POSTCONDITIONS: all_packages yields every registered package name."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertEqual(repository.all_packages(), set())
            repository.register_package(PackageRelease(name="zeta", version=make_version(1, 0, 0)))
            repository.register_package(PackageRelease(name="eta", version=make_version(2, 0, 0)))
            self.assertEqual(repository.all_packages(), {"zeta", "eta"})


class DependencySolverTest(unittest.TestCase):
    """Verifies DependencySolver.resolve postconditions and checked preconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_resolve_selects_highest_precedence_compatible_version(self) -> None:
        """POSTCONDITIONS: resolution selects the highest compatible version for each package."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease(name="core", version=make_version(1, 0, 0)))
            repository.register_package(PackageRelease(name="core", version=make_version(2, 0, 0)))
            repository.register_package(PackageRelease(name="util", version=make_version(1, 0, 0)))
            outcome = solver.resolve(
                [
                    make_dependency("core", ">=1.0.0"),
                    make_dependency("util", ">=1.0.0"),
                ]
            )
            self.assertIsNotNone(outcome)
            self.assertEqual(outcome.selected_versions["core"], make_version(2, 0, 0))
            self.assertEqual(outcome.selected_versions["util"], make_version(1, 0, 0))
            self.assertIsInstance(outcome.derivation_steps, tuple)

    def test_resolve_honors_transitive_constraints(self) -> None:
        """POSTCONDITIONS: transitive dependency constraints restrict selected versions."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease(name="core", version=make_version(1, 0, 0)))
            repository.register_package(PackageRelease(name="core", version=make_version(1, 5, 0)))
            repository.register_package(PackageRelease(name="core", version=make_version(2, 0, 0)))
            repository.register_package(
                PackageRelease(
                    name="app",
                    version=make_version(1, 0, 0),
                    dependencies=(make_dependency("core", ">=1.0.0 <2.0.0"),),
                )
            )
            outcome = solver.resolve([make_dependency("app", ">=1.0.0")])
            self.assertEqual(outcome.selected_versions["app"], make_version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["core"], make_version(1, 5, 0))
            self.assertIsInstance(outcome.derivation_steps, tuple)

    def test_resolve_backtracks_to_alternative_candidate(self) -> None:
        """POSTCONDITIONS: conflicting candidate constraints are undone and alternatives tried."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease(name="core", version=make_version(1, 0, 0)))
            repository.register_package(PackageRelease(name="core", version=make_version(1, 5, 0)))
            repository.register_package(PackageRelease(name="core", version=make_version(2, 0, 0)))
            repository.register_package(
                PackageRelease(
                    name="app",
                    version=make_version(2, 0, 0),
                    dependencies=(make_dependency("core", ">=2.0.0"),),
                )
            )
            repository.register_package(
                PackageRelease(
                    name="app",
                    version=make_version(1, 0, 0),
                    dependencies=(make_dependency("core", ">=1.0.0 <2.0.0"),),
                )
            )
            outcome = solver.resolve(
                [
                    make_dependency("app", ">=1.0.0"),
                    make_dependency("core", ">=1.0.0 <2.0.0"),
                ]
            )
            self.assertEqual(outcome.selected_versions["app"], make_version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["core"], make_version(1, 5, 0))
            self.assertIsInstance(outcome.derivation_steps, tuple)

    def test_resolve_exhausted_backtracking_raises_conflict(self) -> None:
        """PRECONDITIONS: exhausting backtracked alternatives raises ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease(name="core", version=make_version(1, 0, 0)))
            repository.register_package(PackageRelease(name="core", version=make_version(2, 0, 0)))
            repository.register_package(
                PackageRelease(
                    name="app",
                    version=make_version(2, 0, 0),
                    dependencies=(make_dependency("core", ">=3.0.0"),),
                )
            )
            repository.register_package(
                PackageRelease(
                    name="app",
                    version=make_version(1, 0, 0),
                    dependencies=(make_dependency("core", ">=4.0.0"),),
                )
            )
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve(
                    [
                        make_dependency("app", ">=1.0.0"),
                        make_dependency("core", ">=1.0.0"),
                    ]
                )
            self.assertIsInstance(context.exception.conflicting_packages, tuple)
            self.assertIsInstance(context.exception.explanation, str)
            self.assertGreater(len(context.exception.explanation), 0)

    def test_resolve_rejects_candidate_conflicting_with_selected_version(self) -> None:
        """POSTCONDITIONS: candidate rejected when a dependency excludes an already selected version."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease(name="core", version=make_version(1, 0, 0)))
            repository.register_package(PackageRelease(name="core", version=make_version(2, 0, 0)))
            repository.register_package(
                PackageRelease(
                    name="app",
                    version=make_version(2, 0, 0),
                    dependencies=(make_dependency("core", "<2.0.0"),),
                )
            )
            repository.register_package(
                PackageRelease(
                    name="app",
                    version=make_version(1, 0, 0),
                    dependencies=(make_dependency("core", ">=2.0.0"),),
                )
            )
            outcome = solver.resolve(
                [
                    make_dependency("app", ">=1.0.0"),
                    make_dependency("core", ">=2.0.0"),
                ]
            )
            self.assertEqual(outcome.selected_versions["core"], make_version(2, 0, 0))
            self.assertEqual(outcome.selected_versions["app"], make_version(1, 0, 0))
            self.assertIsInstance(outcome.derivation_steps, tuple)

    def test_resolve_backtracking_removes_newly_introduced_constraints(self) -> None:
        """POSTCONDITIONS: constraints introduced by a failed candidate are undone before retry."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease(name="extra", version=make_version(1, 0, 0)))
            repository.register_package(
                PackageRelease(
                    name="app",
                    version=make_version(2, 0, 0),
                    dependencies=(make_dependency("extra", ">=2.0.0"),),
                )
            )
            repository.register_package(PackageRelease(name="app", version=make_version(1, 0, 0)))
            outcome = solver.resolve([make_dependency("app", ">=1.0.0")])
            self.assertEqual(outcome.selected_versions["app"], make_version(1, 0, 0))
            self.assertNotIn("extra", outcome.selected_versions)
            self.assertIsInstance(outcome.derivation_steps, tuple)

    def test_resolve_unsatisfiable_raises_conflict(self) -> None:
        """PRECONDITIONS: mutually unsatisfiable constraints raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease(name="core", version=make_version(1, 0, 0)))
            repository.register_package(
                PackageRelease(
                    name="app",
                    version=make_version(1, 0, 0),
                    dependencies=(make_dependency("core", "<2.0.0"),),
                )
            )
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve(
                    [
                        make_dependency("app", ">=1.0.0"),
                        make_dependency("core", ">=2.0.0"),
                    ]
                )
            self.assertIsInstance(context.exception.conflicting_packages, tuple)
            self.assertIsInstance(context.exception.explanation, str)
            self.assertGreater(len(context.exception.explanation), 0)

    def test_resolve_absent_package_raises_conflict(self) -> None:
        """PRECONDITIONS: absent packages raise ResolutionConflictError without PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([make_dependency("ghost", ">=1.0.0")])
            self.assertIsInstance(context.exception.conflicting_packages, tuple)
            self.assertIsInstance(context.exception.explanation, str)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T19:40:23Z
# LAST_CHANGED: 2026-11-07T19:39:11Z
# CHANGE: Address feedback: exercise every comparator on a fully wildcarded operand ('*' and '=*' match all versions, '>*' and '<*' normalize to the empty set matching none, '<=*' matches all) plus parse acceptance; add DependencySolver backtracking tests where a candidate whose transitive dependency excludes an already selected version is rejected and an alternative resolves, and where a failed candidate's newly introduced constraint is undone so the next candidate succeeds without the stale package assignment.
# COVERAGE_AUDIT: 2026-11-07T19:40:23Z
# QA_AUDIT: 2026-11-07T19:39:40Z
# --- END AUTOFAB METADATA ---
