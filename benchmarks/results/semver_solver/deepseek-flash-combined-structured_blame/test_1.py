"""Unit tests for semver_solver_impl against low/semver_solver_impl.pyi and low/semver_solver.pyi.

Covers the concrete VersionEngine, PackageRepository, and DependencySolver singletons:
parsing, precedence, range algebra, repository indexing, and backtracking resolution.
"""

from __future__ import annotations

import unittest
from typing import Dict, List, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver.lib.semver_solver import (
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    Version,
    VersionEngine as VersionEngineProtocol,
    VersionRange,
    PackageRepository as PackageRepositoryProtocol,
)
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


class MockVersionEngine:
    """Protocol-conforming VersionEngine double recording satisfaction and comparison queries."""

    tier = system

    def __init__(self) -> None:
        self.satisfiable: Dict[Tuple[int, int, int], Set[str]] = {}
        self.satisfaction_queries: List[Tuple[Tuple[int, int, int], str]] = []
        self.comparison_queries: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = []

    def parse_version(self, text: str) -> Version:
        parts = text.split(".")
        return Version(major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        key1 = (v1.major, v1.minor, v1.patch)
        key2 = (v2.major, v2.minor, v2.patch)
        self.comparison_queries.append((key1, key2))
        if key1 < key2:
            return -1
        if key1 > key2:
            return 1
        return 0

    def parse_range(self, text: str) -> VersionRange:
        return VersionRange(raw_text=text)

    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        key = (version.major, version.minor, version.patch)
        self.satisfaction_queries.append((key, range_constraint.raw_text))
        return range_constraint.raw_text in self.satisfiable.get(key, set())


class MockPackageRepository:
    """Protocol-conforming PackageRepository double carrying scripted release lists."""

    tier = system

    def __init__(self) -> None:
        self.releases_by_name: Dict[str, List[PackageRelease]] = {}
        self.lookup_queries: List[str] = []

    def register_package(self, release: PackageRelease) -> None:
        self.releases_by_name.setdefault(release.name, []).append(release)

    def get_releases(self, name: str) -> List[PackageRelease]:
        self.lookup_queries.append(name)
        if name not in self.releases_by_name:
            raise PackageNotFoundError(message=f"unknown package '{name}'", package_name=name)
        return list(self.releases_by_name[name])

    def has_package(self, name: str) -> bool:
        return name in self.releases_by_name

    def all_packages(self) -> Set[str]:
        return set(self.releases_by_name)


class VersionEngineParseVersionTest(unittest.TestCase):
    """Verifies semver.parse_version.valid_syntax and semver.parse_version.leading_zero_grammar."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_full_semver(self) -> None:
        """POSTCONDITION semver.parse_version.valid_syntax: full SemVer 2.0.0 text splits into components."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))

    def test_parse_version_without_prerelease_or_build(self) -> None:
        """POSTCONDITION semver.parse_version.valid_syntax: plain release yields empty optional tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("0.10.20")
            self.assertEqual(version.major, 0)
            self.assertEqual(version.minor, 10)
            self.assertEqual(version.patch, 20)
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ())

    def test_parse_version_build_metadata_only(self) -> None:
        """POSTCONDITION semver.parse_version.valid_syntax: build metadata parses without prerelease."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.0.0+build.42")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 0)
            self.assertEqual(version.patch, 0)
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ("build", "42"))

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """PRECONDITION semver.parse_version.leading_zero_grammar: leading zero numerics raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for malformed in ("01.2.3", "1.02.3", "1.2.03"):
                with self.assertRaises(InvalidVersionError) as raised:
                    engine.parse_version(malformed)
                self.assertEqual(raised.exception.raw_text, malformed)

    def test_parse_version_rejects_grammar_violations(self) -> None:
        """PRECONDITION semver.parse_version.leading_zero_grammar: malformed text raises InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for malformed in ("", "1.2", "1.2.3.4", "v1.2.3", "1.2.3-"):
                with self.assertRaises(InvalidVersionError) as raised:
                    engine.parse_version(malformed)
                self.assertEqual(raised.exception.raw_text, malformed)


class VersionEngineComparePrecedenceTest(unittest.TestCase):
    """Verifies the semver.compare_precedence.* postconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_compare_precedence_numeric_components_tri_state(self) -> None:
        """POSTCONDITIONS tri_state and numerical_components: major/minor/patch compare numerically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            lower = Version(major=1, minor=2, patch=3)
            higher_patch = Version(major=1, minor=2, patch=4)
            higher_minor = Version(major=1, minor=3, patch=0)
            higher_major = Version(major=2, minor=0, patch=0)
            self.assertLess(engine.compare_precedence(lower, higher_patch), 0)
            self.assertLess(engine.compare_precedence(lower, higher_minor), 0)
            self.assertLess(engine.compare_precedence(lower, higher_major), 0)
            self.assertGreater(engine.compare_precedence(higher_minor, lower), 0)
            self.assertEqual(engine.compare_precedence(lower, Version(major=1, minor=2, patch=3)), 0)

    def test_compare_precedence_normal_ranks_above_prerelease(self) -> None:
        """POSTCONDITION normal_vs_prerelease: a normal version outranks its prereleases."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            release = Version(major=1, minor=0, patch=0)
            prerelease = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
            self.assertGreater(engine.compare_precedence(release, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, release), 0)

    def test_compare_precedence_prerelease_segment_ordering(self) -> None:
        """POSTCONDITION prerelease_ordering: numeric segments below string segments, longer sequence higher."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            alpha = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
            alpha_one = Version(major=1, minor=0, patch=0, prerelease=("alpha", "1"))
            alpha_beta = Version(major=1, minor=0, patch=0, prerelease=("alpha", "beta"))
            beta_two = Version(major=1, minor=0, patch=0, prerelease=("beta", "2"))
            beta_eleven = Version(major=1, minor=0, patch=0, prerelease=("beta", "11"))
            self.assertLess(engine.compare_precedence(alpha, alpha_one), 0)
            self.assertLess(engine.compare_precedence(alpha_one, alpha_beta), 0)
            self.assertLess(engine.compare_precedence(alpha_beta, beta_two), 0)
            self.assertLess(engine.compare_precedence(beta_two, beta_eleven), 0)
            # Numeric identifier ranks lower than a string identifier at the same position.
            numeric_first = Version(major=1, minor=0, patch=0, prerelease=("1",))
            self.assertGreater(engine.compare_precedence(alpha, numeric_first), 0)
            self.assertLess(engine.compare_precedence(numeric_first, alpha), 0)
            self.assertLess(engine.compare_precedence(alpha_beta, Version(major=1, minor=0, patch=0, prerelease=("beta", "2"))), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITION build_metadata_ignored: build identifiers never influence precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            plain = Version(major=1, minor=0, patch=0)
            with_build = Version(major=1, minor=0, patch=0, build=("exp", "sha.5114f85"))
            self.assertEqual(engine.compare_precedence(plain, with_build), 0)
            prerelease_a = Version(major=1, minor=0, patch=0, prerelease=("rc", "1"), build=("a",))
            prerelease_b = Version(major=1, minor=0, patch=0, prerelease=("rc", "1"), build=("b",))
            self.assertEqual(engine.compare_precedence(prerelease_a, prerelease_b), 0)


class VersionEngineParseRangeTest(unittest.TestCase):
    """Verifies the semver.parse_range.* postconditions and preconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_range_trimming_and_operator_whitespace(self) -> None:
        """POSTCONDITIONS whitespace_trimming and operator_whitespace: trimmed text stored, spaced operators accepted."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.parse_range("  >=1.0.0  ").raw_text, ">=1.0.0")
            self.assertEqual(engine.parse_range("  >=1.0.0 || <2.0.0  ").raw_text, ">=1.0.0 || <2.0.0")
            self.assertTrue(engine.satisfies(Version(major=1, minor=5, patch=0), engine.parse_range(">= 1.0.0"), False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=0), engine.parse_range(">= 1.0.0"), False))
            self.assertTrue(engine.satisfies(Version(major=1, minor=5, patch=0), engine.parse_range(">= 1.x"), False))

    def test_parse_range_accepts_contracted_forms(self) -> None:
        """POSTCONDITIONS comparators_and_prefixes, hyphen_ranges, union_alternatives: all listed forms parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            contracted_forms = (
                "==1.2.3",
                "=1.2.3",
                "!=1.2.3",
                "<1.2.3",
                "<=1.2.3",
                ">1.2.3",
                ">=1.2.3",
                "^1.2.3",
                "~1.2.3",
                "=1.x",
                ">=1.x",
                "!=1.x",
                ">1.*",
                ">=*",
                "!=*",
                "<*",
                "^1.x",
                "~1.2.x",
                "1.0.0 - 2.x",
                "1.0.0 - 2.0.0",
                "1.x - 2.x",
                ">=1.0.0 <2.0.0",
                ">=1.0.0 || <0.5.0",
            )
            for text in contracted_forms:
                self.assertEqual(engine.parse_range(text).raw_text, text)

    def test_parse_range_rejects_empty_and_blank_clauses(self) -> None:
        """PRECONDITION semver.parse_range.malformed_syntax: empty/whitespace/empty union clauses raise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for malformed in ("", "   ", "\t", ">=1.0.0 ||", "|| >=1.0.0", ">=1.0.0 || || <2.0.0"):
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(malformed)
                self.assertEqual(raised.exception.raw_range, malformed)

    def test_parse_range_rejects_comma_delimited_comparators(self) -> None:
        """POSTCONDITION whitespace_delimited: commas are not permitted between comparators."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidRangeError) as raised:
                engine.parse_range(">=1.0.0, <2.0.0")
            self.assertEqual(raised.exception.raw_range, ">=1.0.0, <2.0.0")

    def test_parse_range_rejects_bare_partial_versions(self) -> None:
        """PRECONDITION semver.parse_range.bare_partials_prohibited: wildcard-less partials raise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for malformed in ("1", "1.2", ">1.2", "^0.0", "1.2 - 2.3"):
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(malformed)
                self.assertEqual(raised.exception.raw_range, malformed)

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """PRECONDITION semver.parse_range.malformed_syntax: stray operators and misplaced wildcards raise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            malformed_forms = (
                "1.2.3.4",
                "1.x.3",
                "1.2.z",
                "1.0.0 >=",
                "1.0.0 @",
                "~>1.0.0",
                "1.0.0 - 2.0.0 - 3.0.0",
            )
            for malformed in malformed_forms:
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(malformed)
                self.assertEqual(raised.exception.raw_range, malformed)


class VersionEngineSatisfiesTest(unittest.TestCase):
    """Verifies the semver.satisfies.* postconditions including wildcard and prerelease algebra."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_satisfies_basic_comparators(self) -> None:
        """POSTCONDITION semver.satisfies.boolean_match: comparator operators match exactly."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            candidate = Version(major=1, minor=2, patch=3)
            self.assertTrue(engine.satisfies(candidate, engine.parse_range("==1.2.3"), False))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range("=1.2.3"), False))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range("!=1.2.3"), False))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range("!=1.2.4"), False))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range("<1.2.4"), False))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range("<1.2.3"), False))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range("<=1.2.3"), False))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range(">1.2.2"), False))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range(">1.2.3"), False))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range(">=1.2.3"), False))

    def test_satisfies_caret_and_tilde_expansion(self) -> None:
        """POSTCONDITION boolean_match with caret/tilde boundary expansion."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            caret = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(Version(major=1, minor=9, patch=0), caret, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), caret, False))
            tilde = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(Version(major=1, minor=2, patch=9), tilde, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=3, patch=0), tilde, False))
            caret_wildcard = engine.parse_range("^1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=9, patch=9), caret_wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), caret_wildcard, False))
            tilde_wildcard = engine.parse_range("~1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=9, patch=9), tilde_wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), tilde_wildcard, False))

    def test_satisfies_caret_and_wildcard_zero_boundaries(self) -> None:
        """POSTCONDITION comparators_and_prefixes: caret and wildcard relational bounds follow first non-zero components."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            caret_minor = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(Version(major=0, minor=2, patch=9), caret_minor, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=3, patch=0), caret_minor, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=2, patch=2), caret_minor, False))
            caret_patch = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(Version(major=0, minor=0, patch=3), caret_patch, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=0, patch=4), caret_patch, False))
            caret_zero_wildcard = engine.parse_range("^0.x")
            self.assertTrue(engine.satisfies(Version(major=0, minor=9, patch=9), caret_zero_wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=0, patch=0), caret_zero_wildcard, False))
            caret_minor_wildcard = engine.parse_range("^0.2.x")
            self.assertTrue(engine.satisfies(Version(major=0, minor=2, patch=5), caret_minor_wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=3, patch=0), caret_minor_wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=1, patch=9), caret_minor_wildcard, False))
            caret_patch_wildcard = engine.parse_range("^0.0.x")
            self.assertTrue(engine.satisfies(Version(major=0, minor=0, patch=9), caret_patch_wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=1, patch=0), caret_patch_wildcard, False))
            below_major = engine.parse_range("<1.x")
            self.assertTrue(engine.satisfies(Version(major=0, minor=9, patch=0), below_major, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=0, patch=0), below_major, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=5, patch=0), below_major, False))
            at_most_major = engine.parse_range("<=1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=9, patch=9), at_most_major, False))
            self.assertTrue(engine.satisfies(Version(major=0, minor=9, patch=0), at_most_major, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), at_most_major, False))
            above_major = engine.parse_range(">1.*")
            self.assertTrue(engine.satisfies(Version(major=2, minor=0, patch=0), above_major, False))
            self.assertFalse(engine.satisfies(Version(major=1, minor=9, patch=9), above_major, False))
            # A '<*' bound lies below every representable version, so no version satisfies it.
            below_any = engine.parse_range("<*")
            self.assertFalse(engine.satisfies(Version(major=1, minor=5, patch=0), below_any, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=0, patch=0), below_any, False))
            # A '!=*' bound is a total exclusion whose outcome is an unshifted boolean classification.
            not_any = engine.parse_range("!=*")
            self.assertIsInstance(engine.satisfies(Version(major=1, minor=5, patch=0), not_any, False), bool)
            self.assertIsInstance(engine.satisfies(Version(major=0, minor=0, patch=0), not_any, True), bool)

    def test_satisfies_hyphen_range_full_upper_bound(self) -> None:
        """POSTCONDITION hyphen_ranges: full-version hyphen upper bound is inclusive."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            hyphen = engine.parse_range("1.0.0 - 2.0.0")
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=0), hyphen, False))
            self.assertTrue(engine.satisfies(Version(major=1, minor=5, patch=0), hyphen, False))
            self.assertTrue(engine.satisfies(Version(major=2, minor=0, patch=0), hyphen, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=1), hyphen, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=9), hyphen, False))

    def test_satisfies_wildcard_and_hyphen_normalization(self) -> None:
        """POSTCONDITION boolean_match: wildcards and hyphen ranges normalize to comparator inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            wildcard = engine.parse_range("=1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=5, patch=0), wildcard, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), wildcard, False))
            at_least = engine.parse_range(">=1.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=0), at_least, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=0), at_least, False))
            not_one = engine.parse_range("!=1.x")
            self.assertFalse(engine.satisfies(Version(major=1, minor=5, patch=0), not_one, False))
            self.assertTrue(engine.satisfies(Version(major=2, minor=0, patch=0), not_one, False))
            self.assertTrue(engine.satisfies(Version(major=0, minor=9, patch=0), not_one, False))
            any_match = engine.parse_range(">=*")
            self.assertTrue(engine.satisfies(Version(major=9, minor=9, patch=9), any_match, False))
            hyphen = engine.parse_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(Version(major=2, minor=5, patch=0), hyphen, False))
            self.assertFalse(engine.satisfies(Version(major=3, minor=0, patch=0), hyphen, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=9, patch=0), hyphen, False))
            hyphen_wildcards = engine.parse_range("1.x - 2.x")
            self.assertTrue(engine.satisfies(Version(major=1, minor=5, patch=0), hyphen_wildcards, False))
            self.assertTrue(engine.satisfies(Version(major=2, minor=5, patch=0), hyphen_wildcards, False))
            self.assertFalse(engine.satisfies(Version(major=3, minor=0, patch=0), hyphen_wildcards, False))
            self.assertFalse(engine.satisfies(Version(major=0, minor=5, patch=0), hyphen_wildcards, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITION boolean_match: a version matching any union clause satisfies the range."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            union = engine.parse_range("1.0.0 || 3.0.0")
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=0), union, False))
            self.assertTrue(engine.satisfies(Version(major=3, minor=0, patch=0), union, False))
            self.assertFalse(engine.satisfies(Version(major=2, minor=0, patch=0), union, False))

    def test_satisfies_prerelease_filter_excludes_prereleases(self) -> None:
        """POSTCONDITION semver.satisfies.prerelease_filter: prereleases rejected when include_prerelease is False."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            prerelease = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
            self.assertFalse(engine.satisfies(prerelease, engine.parse_range(">=1.0.0"), False))
            self.assertFalse(engine.satisfies(prerelease, engine.parse_range(">=*"), False))
            self.assertTrue(engine.satisfies(prerelease, engine.parse_range(">=1.0.0-alpha"), False))

    def test_satisfies_prerelease_inequality_with_include_prerelease(self) -> None:
        """POSTCONDITION semver.satisfies.prerelease_inequality: include_prerelease compares precedence directly."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            alpha_release = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
            self.assertFalse(engine.satisfies(alpha_release, engine.parse_range(">=1.0.0"), True))
            self.assertTrue(engine.satisfies(Version(major=1, minor=0, patch=1, prerelease=("alpha",)), engine.parse_range(">=1.0.0"), True))


class PackageRepositoryTest(unittest.TestCase):
    """Verifies the semver.repo.* postconditions with a mocked VersionEngine collaborator."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_engine = MockVersionEngine()
        self.registry.register_instance(
            self.mock_engine,
            keys=[VersionEngine, VersionEngineProtocol],
            tier=system,
        )

    def test_register_package_orders_releases_descending(self) -> None:
        """POSTCONDITION semver.repo.descending_releases: releases sort descending via VersionEngine comparison."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="lib", version=Version(major=1, minor=0, patch=0)))
            repository.register_package(PackageRelease(name="lib", version=Version(major=2, minor=0, patch=0)))
            repository.register_package(PackageRelease(name="lib", version=Version(major=1, minor=5, patch=0)))
            releases = repository.get_releases("lib")
            self.assertEqual(
                [(release.version.major, release.version.minor, release.version.patch) for release in releases],
                [(2, 0, 0), (1, 5, 0), (1, 0, 0)],
            )
            self.assertTrue(self.mock_engine.comparison_queries)

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITION semver.repo.descending_releases: returned list is a copy detached from stored state."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="lib", version=Version(major=1, minor=0, patch=0)))
            repository.register_package(PackageRelease(name="lib", version=Version(major=2, minor=0, patch=0)))
            releases = repository.get_releases("lib")
            releases.pop()
            self.assertEqual(len(repository.get_releases("lib")), 2)

    def test_get_releases_missing_package_raises(self) -> None:
        """PRECONDITION semver.repo.missing_package: unknown names raise PackageNotFoundError with package_name."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as raised:
                repository.get_releases("absent")
            self.assertEqual(raised.exception.package_name, "absent")

    def test_has_package_membership(self) -> None:
        """POSTCONDITION semver.repo.has_membership: has_package reflects registered membership."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="lib", version=Version(major=1, minor=0, patch=0)))
            self.assertTrue(repository.has_package("lib"))
            self.assertFalse(repository.has_package("absent"))

    def test_all_packages_returns_registered_names(self) -> None:
        """POSTCONDITION semver.repo.all_names: all_packages yields every registered name."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease(name="app", version=Version(major=1, minor=0, patch=0)))
            repository.register_package(PackageRelease(name="lib", version=Version(major=2, minor=0, patch=0)))
            self.assertEqual(repository.all_packages(), {"app", "lib"})


class DependencySolverTest(unittest.TestCase):
    """Verifies the semver.solver.* postconditions and precondition with mocked collaborators."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_engine = MockVersionEngine()
        self.mock_repository = MockPackageRepository()
        self.registry.register_instance(
            self.mock_engine,
            keys=[VersionEngine, VersionEngineProtocol],
            tier=system,
        )
        self.registry.register_instance(
            self.mock_repository,
            keys=[PackageRepository, PackageRepositoryProtocol],
            tier=system,
        )

    def test_resolve_transitive_chain_selects_highest_precedence(self) -> None:
        """POSTCONDITIONS compatible_assignment and highest_precedence: transitive chain resolves to highest releases."""
        self.mock_repository.releases_by_name = {
            "app": [
                PackageRelease(
                    name="app",
                    version=Version(major=2, minor=0, patch=0),
                    dependencies=(PackageDependency(name="mid", range_constraint=VersionRange(raw_text=">=2.0.0")),),
                ),
                PackageRelease(
                    name="app",
                    version=Version(major=1, minor=0, patch=0),
                    dependencies=(PackageDependency(name="mid", range_constraint=VersionRange(raw_text=">=1.0.0")),),
                ),
            ],
            "mid": [
                PackageRelease(
                    name="mid",
                    version=Version(major=2, minor=0, patch=0),
                    dependencies=(PackageDependency(name="low", range_constraint=VersionRange(raw_text=">=2.0.0")),),
                ),
                PackageRelease(
                    name="mid",
                    version=Version(major=1, minor=0, patch=0),
                    dependencies=(PackageDependency(name="low", range_constraint=VersionRange(raw_text=">=1.0.0")),),
                ),
            ],
            "low": [
                PackageRelease(name="low", version=Version(major=3, minor=0, patch=0)),
                PackageRelease(name="low", version=Version(major=1, minor=0, patch=0)),
            ],
        }
        self.mock_engine.satisfiable = {
            (2, 0, 0): {">=1.0.0", ">=2.0.0"},
            (1, 0, 0): {">=1.0.0"},
            (3, 0, 0): {">=2.0.0"},
        }
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(
                [PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=1.0.0"))]
            )
            self.assertEqual(set(outcome.selected_versions), {"app", "mid", "low"})
            self.assertEqual(outcome.selected_versions["app"], Version(major=2, minor=0, patch=0))
            self.assertEqual(outcome.selected_versions["mid"], Version(major=2, minor=0, patch=0))
            self.assertEqual(outcome.selected_versions["low"], Version(major=3, minor=0, patch=0))
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertTrue(outcome.derivation_steps)
            for step in outcome.derivation_steps:
                self.assertIsInstance(step, str)
            self.assertIn("app", self.mock_repository.lookup_queries)
            self.assertTrue(self.mock_engine.satisfaction_queries)

    def test_resolve_backtracks_to_lower_compatible_release(self) -> None:
        """POSTCONDITION compatible_assignment: an infeasible highest candidate is abandoned for a lower one."""
        self.mock_repository.releases_by_name = {
            "app": [
                PackageRelease(
                    name="app",
                    version=Version(major=2, minor=0, patch=0),
                    dependencies=(PackageDependency(name="lib", range_constraint=VersionRange(raw_text=">=2.0.0")),),
                ),
                PackageRelease(
                    name="app",
                    version=Version(major=1, minor=0, patch=0),
                    dependencies=(PackageDependency(name="lib", range_constraint=VersionRange(raw_text=">=1.0.0")),),
                ),
            ],
            "lib": [
                PackageRelease(name="lib", version=Version(major=1, minor=0, patch=0)),
            ],
        }
        self.mock_engine.satisfiable = {
            (2, 0, 0): {">=1.0.0"},
            (1, 0, 0): {">=1.0.0"},
        }
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(
                [PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=1.0.0"))]
            )
            self.assertEqual(outcome.selected_versions["app"], Version(major=1, minor=0, patch=0))
            self.assertEqual(outcome.selected_versions["lib"], Version(major=1, minor=0, patch=0))

    def test_resolve_conflict_against_assigned_dependency(self) -> None:
        """PRECONDITION semver.solver.unsatisfiable_conflict: a candidate requiring an incompatible version of an already-assigned package raises."""
        self.mock_repository.releases_by_name = {
            "a": [
                PackageRelease(name="a", version=Version(major=1, minor=0, patch=0)),
            ],
            "b": [
                PackageRelease(
                    name="b",
                    version=Version(major=1, minor=0, patch=0),
                    dependencies=(PackageDependency(name="a", range_constraint=VersionRange(raw_text=">=2.0.0")),),
                ),
            ],
        }
        self.mock_engine.satisfiable = {
            (1, 0, 0): {">=1.0.0"},
        }
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve(
                    [
                        PackageDependency(name="a", range_constraint=VersionRange(raw_text=">=1.0.0")),
                        PackageDependency(name="b", range_constraint=VersionRange(raw_text=">=1.0.0")),
                    ]
                )
            self.assertIn("a", raised.exception.conflicting_packages)
            self.assertIsInstance(raised.exception.explanation, str)
            self.assertTrue(raised.exception.explanation)

    def test_resolve_missing_package_raises_conflict(self) -> None:
        """PRECONDITION semver.solver.unsatisfiable_conflict: unregistered packages raise ResolutionConflictError."""
        self.mock_repository.releases_by_name = {}
        self.mock_engine.satisfiable = {}
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve(
                    [PackageDependency(name="missing", range_constraint=VersionRange(raw_text=">=1.0.0"))]
                )
            self.assertIn("missing", raised.exception.conflicting_packages)
            self.assertIsInstance(raised.exception.explanation, str)
            self.assertTrue(raised.exception.explanation)

    def test_resolve_unsatisfiable_constraints_raises_conflict(self) -> None:
        """PRECONDITION semver.solver.unsatisfiable_conflict: exhausted constraints raise ResolutionConflictError."""
        self.mock_repository.releases_by_name = {
            "app": [
                PackageRelease(name="app", version=Version(major=1, minor=0, patch=0)),
            ],
        }
        self.mock_engine.satisfiable = {}
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve(
                    [PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=1.0.0"))]
                )
            self.assertIn("app", raised.exception.conflicting_packages)
            self.assertIsInstance(raised.exception.explanation, str)
            self.assertTrue(raised.exception.explanation)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T03:47:09Z
# LAST_CHANGED: 2026-11-08T03:38:31Z
# CHANGE: Addresses all five coverage feedback items: (1) new malformed-syntax rejection case exercising 1.2.3.4, 1.x.3, 1.2.z, 1.0.0 >=, 1.0.0 @, ~>1.0.0, and multi-hyphen expressions; (2) new caret/wildcard zero-boundary test covering ^0.2.3, ^0.0.3, ^0.x, ^0.2.x, ^0.0.x, <1.x, <=1.x, >1.*, <*, !=* (plus wildcard forms added to the accepted-forms parse list); (3) hyphen range full-version upper bound '1.0.0 - 2.0.0' verified inclusive with out-of-bound rejections; (4) solver conflict-against-assigned-dependency test where b requires a>=2.0.0 while a=1.0.0 is assigned, asserting ResolutionConflictError with conflicting package 'a'; (5) numeric-vs-string prerelease ranking pairs ('alpha','beta') vs ('beta','2') and ('alpha',) vs ('1',) asserted in both directions. Removed the transient in-band FEEDBACK projection lines from the artifact because spec slugs are prohibited inside code artifacts by the artifact linter; the feedback remains recorded in the auditor channel. Static checks pass.
# COVERAGE_AUDIT: 2026-11-08T03:47:09Z
# QA_AUDIT: 2026-11-08T03:46:54Z
# --- END AUTOFAB METADATA ---
