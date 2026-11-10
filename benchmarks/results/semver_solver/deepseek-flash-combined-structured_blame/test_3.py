"""Unit tests for semver_solver_impl singletons per their grounding specification.

Covers the contracted postconditions and checked preconditions of the semver_solver
interface specification realized by VersionEngine, PackageRepository, and
DependencySolver: SemVer 2.0.0 parsing, precedence comparison, range parsing and
matching, release registration ordering, and backtracking dependency resolution.

Every test executes its setup, operations, and assertions inside one active
lifecycle phase scope opened with ``enter_phase`` and closed on block exit.
"""

from __future__ import annotations

import unittest
from support.lib.lifecycle import (
    LifecycleRegistry,
    enter_phase,
    system,
)
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
    major: int = 0,
    minor: int = 0,
    patch: int = 0,
    prerelease: tuple[str, ...] = (),
    build: tuple[str, ...] = (),
) -> Version:
    """Wraps primitive version components into a domain Version record."""
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def make_range(raw_text: str) -> VersionRange:
    """Wraps a raw range expression into a domain VersionRange record."""
    return VersionRange(raw_text=raw_text)


def make_dependency(name: str, raw_range: str) -> PackageDependency:
    """Builds a PackageDependency from a package name and raw range text."""
    return PackageDependency(name=name, range_constraint=make_range(raw_range))


def make_release(
    name: str,
    version: Version,
    dependencies: tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Builds a PackageRelease publication record for repository and solver tests."""
    return PackageRelease(name=name, version=version, dependencies=dependencies)


class SemverSolverImplTest(unittest.TestCase):
    """Verifies VersionEngine, PackageRepository, and DependencySolver contracts."""

    registry: LifecycleRegistry

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    # ------------------------------------------------------------------
    # VersionEngine.parse_version (semver.parse_version.*)
    # ------------------------------------------------------------------
    def test_parse_version_valid_syntax(self) -> None:
        """POSTCONDITION: valid SemVer strings parse into full Version records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            basic = engine.parse_version("1.2.3")
            self.assertEqual(basic, make_version(1, 2, 3))
            self.assertEqual(basic.prerelease, ())
            self.assertEqual(basic.build, ())

            full = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(full.major, 1)
            self.assertEqual(full.minor, 2)
            self.assertEqual(full.patch, 3)
            self.assertEqual(full.prerelease, ("alpha", "1"))
            self.assertEqual(full.build, ("build", "5"))

            zero = engine.parse_version("0.0.0")
            self.assertEqual((zero.major, zero.minor, zero.patch), (0, 0, 0))

    def test_parse_version_format_and_str_roundtrip(self) -> None:
        """POSTCONDITION: format()/__str__ produce the canonical SemVer text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("1.2.3", "0.0.1", "1.2.3-alpha.1+build.5", "1.0.0-rc.1"):
                parsed = engine.parse_version(text)
                self.assertEqual(parsed.format(), text)
                self.assertEqual(str(parsed), text)
                self.assertEqual(parsed.format(), str(parsed))

            self.assertEqual(make_version(2, 0, 0, ("beta",)).format(), "2.0.0-beta")
            self.assertEqual(make_version(2, 0, 0, (), ("sha", "abc")).format(), "2.0.0+sha.abc")
            self.assertEqual(str(make_range("^1.x")), "^1.x")

    def test_parse_version_prerelease_flag(self) -> None:
        """POSTCONDITION: is_prerelease reflects the presence of identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertFalse(engine.parse_version("1.2.3").is_prerelease)
            self.assertFalse(make_version(1, 2, 3, (), ("build",)).is_prerelease)
            self.assertTrue(engine.parse_version("1.2.3-alpha").is_prerelease)
            self.assertTrue(make_version(0, 0, 0, ("0",)).is_prerelease)

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """PRECONDITION: leading zeroes in numeric identifiers raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("01.2.3", "1.02.3", "1.2.03", "00.0.0", "1.0.0-01"):
                with self.assertRaises(InvalidVersionError) as raised:
                    engine.parse_version(text)
                self.assertEqual(raised.exception.raw_text, text)

    def test_parse_version_rejects_grammar_violations(self) -> None:
        """PRECONDITION: grammar-violating version strings raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("", "1", "1.2", "1.2.3.4", "1.2.3-", "1.2.3+", "1.2.x", "not-a-version"):
                with self.assertRaises(InvalidVersionError) as raised:
                    engine.parse_version(text)
                self.assertEqual(raised.exception.raw_text, text)

    # ------------------------------------------------------------------
    # VersionEngine.compare_precedence (semver.compare_precedence.*)
    # ------------------------------------------------------------------
    def test_compare_precedence_numerical_components(self) -> None:
        """POSTCONDITION: tri-state result with numeric major/minor/patch comparison."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 4)), 0)
            self.assertGreater(engine.compare_precedence(make_version(1, 2, 4), make_version(1, 2, 3)), 0)
            self.assertLess(engine.compare_precedence(make_version(1, 2, 9), make_version(1, 3, 0)), 0)
            self.assertGreater(engine.compare_precedence(make_version(1, 10, 0), make_version(1, 9, 0)), 0)
            self.assertGreater(engine.compare_precedence(make_version(2, 0, 0), make_version(1, 99, 99)), 0)
            self.assertEqual(engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 3)), 0)

    def test_compare_precedence_normal_above_prerelease(self) -> None:
        """POSTCONDITION: normal versions rank above same-numbered prereleases."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            normal = make_version(1, 0, 0)
            pre = make_version(1, 0, 0, ("alpha",))
            self.assertGreater(engine.compare_precedence(normal, pre), 0)
            self.assertLess(engine.compare_precedence(pre, normal), 0)

    def test_compare_precedence_prerelease_ordering(self) -> None:
        """POSTCONDITION: prerelease numeric/ASCII ordering and prefix extension."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            chain = (
                "1.0.0-alpha",
                "1.0.0-alpha.1",
                "1.0.0-alpha.beta",
                "1.0.0-beta",
                "1.0.0-beta.2",
                "1.0.0-beta.11",
                "1.0.0-rc.1",
                "1.0.0",
            )
            parsed = [engine.parse_version(text) for text in chain]
            for lower, higher in zip(parsed, parsed[1:]):
                self.assertLess(engine.compare_precedence(lower, higher), 0)
                self.assertGreater(engine.compare_precedence(higher, lower), 0)

            # Numeric identifiers compare numerically and rank below string identifiers.
            self.assertLess(
                engine.compare_precedence(make_version(1, 0, 0, ("1",)), make_version(1, 0, 0, ("2",))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(make_version(1, 0, 0, ("1",)), make_version(1, 0, 0, ("alpha",))),
                0,
            )
            # ASCII lexicographic string ordering.
            self.assertLess(
                engine.compare_precedence(make_version(1, 0, 0, ("alpha",)), make_version(1, 0, 0, ("beta",))),
                0,
            )

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITION: build metadata never affects precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            left = make_version(1, 2, 3, (), ("build", "a"))
            right = make_version(1, 2, 3, (), ("build", "b"))
            self.assertEqual(engine.compare_precedence(left, right), 0)
            self.assertEqual(engine.compare_precedence(right, left), 0)

            pre_left = make_version(1, 0, 0, ("alpha",), ("x",))
            pre_right = make_version(1, 0, 0, ("alpha",), ("y",))
            self.assertEqual(engine.compare_precedence(pre_left, pre_right), 0)

    # ------------------------------------------------------------------
    # VersionEngine.parse_range (semver.parse_range.*)
    # ------------------------------------------------------------------
    def test_parse_range_comparators_and_prefixes(self) -> None:
        """POSTCONDITION: basic comparators, caret/tilde, and wildcards parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            texts = (
                "==1.2.3",
                "=1.2.3",
                "!=1.2.3",
                "<1.2.3",
                "<=1.2.3",
                ">1.2.3",
                ">=1.2.3",
                "^1.2.3",
                "~1.2.3",
                ">=1.x",
                "!=1.x",
                ">1.*",
                "^1.x",
                "~1.2.x",
                ">=*",
                "1.x",
                "1.*",
                "^1.2.3-alpha.1",
                "~1.2.3-alpha.1",
                ">=1.2.3-alpha.1",
                "==1.2.3-alpha.1",
                "<=1.2.3-alpha.1",
                "^1.2.3+build.5",
                "~1.2.3+build.5",
                ">=1.2.3+build.5",
                "==1.2.3+build.5",
                "!=*",
                "<*",
                "<=*",
                ">*",
                "^*",
                "~*",
            )
            for text in texts:
                parsed = engine.parse_range(text)
                self.assertIsInstance(parsed, VersionRange)
                self.assertEqual(parsed.raw_text, text)
                self.assertEqual(str(parsed), text)

    def test_parse_range_hyphen_ranges(self) -> None:
        """POSTCONDITION: hyphen ranges between full versions or wildcards parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("1.0.0 - 2.0.0", "1.0.0 - 2.x", "1.x - 2.x", "1.x - 2.3.4"):
                parsed = engine.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_union_alternatives(self) -> None:
        """POSTCONDITION: union alternatives separated by '||' parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("1.x || 2.x")
            self.assertEqual(parsed.raw_text, "1.x || 2.x")
            parsed = engine.parse_range(">=1.0.0 <1.2.0 || >=2.0.0")
            self.assertEqual(parsed.raw_text, ">=1.0.0 <1.2.0 || >=2.0.0")

    def test_parse_range_whitespace_trimming(self) -> None:
        """POSTCONDITION: surrounding whitespace is trimmed into raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("   >=1.0.0   ")
            self.assertEqual(parsed.raw_text, ">=1.0.0")
            parsed = engine.parse_range("  1.x || 2.x  ")
            self.assertEqual(parsed.raw_text, "1.x || 2.x")

    def test_parse_range_operator_whitespace_equivalence(self) -> None:
        """POSTCONDITION: operator whitespace is accepted and semantically equivalent."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            spaced = engine.parse_range(" >= 1.0.0 ")
            compact = engine.parse_range(">=1.0.0")
            candidate = make_version(1, 2, 3)
            self.assertTrue(engine.satisfies(candidate, spaced, False))
            self.assertTrue(engine.satisfies(candidate, compact, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), spaced, False))

            spaced_wildcard = engine.parse_range(">= 1.x")
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), spaced_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(0, 5, 0), spaced_wildcard, False))

    def test_parse_range_rejects_bare_partials(self) -> None:
        """PRECONDITION: bare partial versions lacking wildcards raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("1", "1.2", ">1.2", ">=1.2", "^0.0", "~1", "1.2 - 2.3", "<1", "!=1.2"):
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(text)
                self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """PRECONDITION: empty, blank, comma-delimited, or empty-clause ranges raise."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("", "   ", "1.x ||", "|| 2.x", "1.x || || 2.x", ">=1.0.0, <2.0.0", "1.x, 2.x", ">=1.0.0 <", "invalid"):
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(text)
                self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_rejects_malformed_bounds(self) -> None:
        """PRECONDITION: malformed version bounds raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in (
                # Empty or malformed pre-release identifiers.
                ">=1.2.3-",
                ">=1.2.3-alpha..1",
                ">=1.2.3-alpha.",
                # Leading zeroes in numeric pre-release identifiers.
                ">=1.2.3-01",
                ">=1.0.0-alpha.01",
                # Empty or malformed build metadata.
                ">=1.2.3+",
                ">=1.2.3+build..1",
                # Wrong numeric component count.
                ">=1.2.3.4",
                # Leading zeroes in numeric components.
                ">=01.2.3",
                ">=1.02.3",
                ">=1.2.03",
                # Non-numeric components following a wildcard.
                "1.x.2",
                "1.*.2",
                # Metadata attached to a wildcard bound.
                "1.x+build.1",
                ">=1.x+build.1",
                # Malformed hyphen ranges.
                "1.0.0 - ",
                "1.0.0 - 2.0.0 - 3.0.0",
            ):
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(text)
                self.assertEqual(raised.exception.raw_range, text)

    # ------------------------------------------------------------------
    # VersionEngine.satisfies (semver.satisfies.*)
    # ------------------------------------------------------------------
    def test_satisfies_boolean_match_comparators(self) -> None:
        """POSTCONDITION: boolean match for each basic comparator operator."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            candidate = make_version(1, 2, 3)
            self.assertTrue(engine.satisfies(candidate, make_range("==1.2.3"), False))
            self.assertTrue(engine.satisfies(candidate, make_range("=1.2.3"), False))
            self.assertTrue(engine.satisfies(candidate, make_range(">=1.2.3"), False))
            self.assertTrue(engine.satisfies(candidate, make_range("<=1.2.3"), False))
            self.assertTrue(engine.satisfies(candidate, make_range(">1.2.2"), False))
            self.assertTrue(engine.satisfies(candidate, make_range("<1.2.4"), False))
            self.assertFalse(engine.satisfies(candidate, make_range("!=1.2.3"), False))
            self.assertFalse(engine.satisfies(candidate, make_range(">1.2.3"), False))
            self.assertFalse(engine.satisfies(candidate, make_range("<1.2.3"), False))

    def test_satisfies_wildcard_expansions(self) -> None:
        """POSTCONDITION: wildcards normalize into comparator inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), make_range("1.x"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), make_range("1.*"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("1.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), make_range("1.*"), False))

            # >=1.x expands to >=1.0.0 (no upper bound).
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), make_range(">=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 5, 0), make_range(">=1.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), make_range(">=1.x"), False))

            # !=1.x expands to <1.0.0 || >=2.0.0.
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), make_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), make_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 0), make_range("!=1.x"), False))

            # >=* is satisfied by all versions.
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), make_range(">=*"), False))
            self.assertTrue(engine.satisfies(make_version(99, 0, 0), make_range(">=*"), False))

            # Explicit '*' wildcard comparator variants expand like their 'x' forms.
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), make_range(">=1.*"), False))
            self.assertTrue(engine.satisfies(make_version(2, 5, 0), make_range(">=1.*"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), make_range(">=1.*"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), make_range(">1.*"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), make_range(">1.*"), False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 9), make_range("<1.*"), False))
            self.assertFalse(engine.satisfies(make_version(2, 5, 0), make_range("<1.*"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), make_range("<=1.*"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("<=1.*"), False))
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), make_range("!=1.*"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), make_range("!=1.*"), False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 0), make_range("!=1.*"), False))
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), make_range("^1.*"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("^1.*"), False))
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), make_range("~1.*"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("~1.*"), False))
            # A bare '*' wildcard spans every version.
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), make_range("*"), False))
            self.assertTrue(engine.satisfies(make_version(9, 9, 9), make_range("*"), False))

            # Bare '*' operands expand per operator and still return a contracted boolean.
            probe = make_version(1, 2, 3)
            self.assertIsInstance(engine.satisfies(probe, make_range("!=*"), False), bool)
            self.assertIsInstance(engine.satisfies(probe, make_range("<*"), False), bool)
            self.assertTrue(engine.satisfies(probe, make_range("<=*"), False))
            self.assertIsInstance(engine.satisfies(probe, make_range(">*"), False), bool)
            self.assertIsInstance(engine.satisfies(probe, make_range("^*"), False), bool)
            self.assertIsInstance(engine.satisfies(probe, make_range("~*"), False), bool)

    def test_satisfies_caret_and_tilde_ranges(self) -> None:
        """POSTCONDITION: caret/tilde prefixes expand to lower and upper boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), make_range("^1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 0), make_range("^1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), make_range("^1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("^1.2.3"), False))

            self.assertTrue(engine.satisfies(make_version(0, 2, 5), make_range("^0.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(0, 3, 0), make_range("^0.2.3"), False))

            # ^1.x expands to >=1.0.0 <2.0.0.
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), make_range("^1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("^1.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), make_range("^1.x"), False))

            self.assertTrue(engine.satisfies(make_version(1, 2, 9), make_range("~1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), make_range("~1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), make_range("~1.2.3"), False))

            # ~1.x expands to >=1.0.0 <2.0.0; ~1.2.x expands to >=1.2.0 <1.3.0.
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), make_range("~1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), make_range("~1.x"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 5), make_range("~1.2.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), make_range("~1.2.x"), False))

    def test_satisfies_caret_zero_major_boundaries(self) -> None:
        """POSTCONDITION: caret expansion honours first non-zero component boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            # ^0.x expands to >=0.0.0 <1.0.0.
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), make_range("^0.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 9), make_range("^0.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), make_range("^0.x"), False))
            # ^0.0.x expands to >=0.0.0 <0.1.0.
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), make_range("^0.0.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 0, 9), make_range("^0.0.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 1, 0), make_range("^0.0.x"), False))
            # ^0.1.x expands to >=0.1.0 <0.2.0.
            self.assertTrue(engine.satisfies(make_version(0, 1, 0), make_range("^0.1.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 1, 9), make_range("^0.1.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 2, 0), make_range("^0.1.x"), False))
            # A zero-major full version honours the same boundary.
            self.assertTrue(engine.satisfies(make_version(0, 2, 3), make_range("^0.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(0, 2, 2), make_range("^0.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(0, 3, 0), make_range("^0.2.3"), False))
            # ^0.0.3 expands to >=0.0.3 <0.0.4 (first non-zero component is the patch).
            self.assertTrue(engine.satisfies(make_version(0, 0, 3), make_range("^0.0.3"), False))
            self.assertFalse(engine.satisfies(make_version(0, 0, 2), make_range("^0.0.3"), False))
            self.assertFalse(engine.satisfies(make_version(0, 0, 4), make_range("^0.0.3"), False))

    def test_satisfies_hyphen_ranges(self) -> None:
        """POSTCONDITION: hyphen ranges normalize into paired inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            ranged = make_range("1.0.0 - 2.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), ranged, False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), ranged, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 1), ranged, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), ranged, False))

            # 1.0.0 - 2.x expands to >=1.0.0 <3.0.0.
            wildcard_bound = make_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(make_version(2, 9, 0), wildcard_bound, False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), wildcard_bound, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), wildcard_bound, False))

            # 1.x - 2.3.4 expands to >=1.0.0 <=2.3.4 (open lower wildcard bound).
            lower_wildcard = make_range("1.x - 2.3.4")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), lower_wildcard, False))
            self.assertTrue(engine.satisfies(make_version(2, 3, 4), lower_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(2, 3, 5), lower_wildcard, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), lower_wildcard, False))

            # 1.x - 2.x expands to >=1.0.0 <3.0.0 (open lower and upper wildcards).
            both_wildcards = make_range("1.x - 2.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), both_wildcards, False))
            self.assertTrue(engine.satisfies(make_version(2, 9, 9), both_wildcards, False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), both_wildcards, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), both_wildcards, False))

            # A bare '*' lower bound is open downwards: * - 2.0.0 is <=2.0.0.
            star_lower = make_range("* - 2.0.0")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), star_lower, False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), star_lower, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 1), star_lower, False))

            # A bare '*' upper bound is open upwards: 1.0.0 - * is >=1.0.0.
            star_upper = make_range("1.0.0 - *")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), star_upper, False))
            self.assertTrue(engine.satisfies(make_version(99, 0, 0), star_upper, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), star_upper, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITION: a version matches when any union clause matches."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            union = make_range("1.x || 2.x")
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), union, False))
            self.assertTrue(engine.satisfies(make_version(2, 5, 0), union, False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), union, False))

            clauses = make_range(">=1.0.0 <1.2.0 || >=2.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 1, 0), clauses, False))
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), clauses, False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), clauses, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), clauses, False))

    def test_satisfies_prerelease_filter(self) -> None:
        """POSTCONDITION: prereleases are filtered unless the range targets them."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            prerelease = make_version(1, 0, 0, ("alpha",))
            self.assertFalse(engine.satisfies(prerelease, make_range(">=1.0.0"), False))
            self.assertFalse(engine.satisfies(prerelease, make_range("<1.0.0"), False))
            self.assertFalse(engine.satisfies(prerelease, make_range("1.x"), False))
            # Normal versions are unaffected by the prerelease filter.
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), make_range(">=1.0.0"), False))

    def test_satisfies_prerelease_explicit_targeting(self) -> None:
        """POSTCONDITION: a range targeting the same major/minor/patch admits it."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            prerelease = make_version(1, 0, 0, ("alpha",))
            self.assertTrue(engine.satisfies(prerelease, make_range(">=1.0.0-alpha"), False))
            self.assertTrue(engine.satisfies(prerelease, make_range("==1.0.0-alpha"), False))
            # A prerelease range for differing numeric components does not admit it.
            other = make_version(1, 2, 3, ("alpha",))
            self.assertFalse(engine.satisfies(other, make_range(">=1.0.0-alpha"), False))

    def test_satisfies_prerelease_inequalities_with_include_prerelease(self) -> None:
        """POSTCONDITION: include_prerelease applies precedence without shifted bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            prerelease = make_version(1, 0, 0, ("alpha",))
            # 1.0.0-alpha ranks strictly lower than 1.0.0.
            self.assertFalse(engine.satisfies(prerelease, make_range(">=1.0.0"), True))
            self.assertTrue(engine.satisfies(prerelease, make_range("<1.0.0"), True))
            self.assertTrue(engine.satisfies(prerelease, make_range(">=1.0.0-alpha"), True))
            # Numerical boundaries are not shifted for prereleases.
            self.assertTrue(engine.satisfies(make_version(1, 2, 3, ("alpha",)), make_range(">=1.0.0"), True))

    # ------------------------------------------------------------------
    # PackageRepository (semver.repo.*)
    # ------------------------------------------------------------------
    def test_register_package_and_get_releases_descending(self) -> None:
        """POSTCONDITION: registered releases are yielded descending by precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(1, 2, 0)))
            repository.register_package(make_release("alpha", make_version(1, 1, 0)))

            releases = repository.get_releases("alpha")
            self.assertEqual([release.version for release in releases], [make_version(1, 2, 0), make_version(1, 1, 0), make_version(1, 0, 0)])
            self.assertEqual([release.name for release in releases], ["alpha", "alpha", "alpha"])

            # A normal release outranks its prerelease, independent of insertion order.
            repository.register_package(make_release("beta", make_version(2, 0, 0, ("rc", "1"))))
            repository.register_package(make_release("beta", make_version(2, 0, 0)))
            beta = repository.get_releases("beta")
            self.assertEqual([release.version for release in beta], [make_version(2, 0, 0), make_version(2, 0, 0, ("rc", "1"))])

    def test_register_package_interleaved_packages(self) -> None:
        """POSTCONDITION: interleaved registrations keep per-package descending order."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("beta", make_version(3, 0, 0)))
            repository.register_package(make_release("alpha", make_version(1, 3, 0)))
            repository.register_package(make_release("beta", make_version(2, 0, 0)))

            self.assertEqual([release.version for release in repository.get_releases("alpha")], [make_version(1, 3, 0), make_version(1, 0, 0)])
            self.assertEqual([release.version for release in repository.get_releases("beta")], [make_version(3, 0, 0), make_version(2, 0, 0)])

    def test_has_package_membership(self) -> None:
        """POSTCONDITION: has_package reflects repository membership."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("alpha"))
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            self.assertTrue(repository.has_package("alpha"))
            self.assertFalse(repository.has_package("beta"))

    def test_all_packages(self) -> None:
        """POSTCONDITION: all_packages yields the set of registered names."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertEqual(repository.all_packages(), set())
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("beta", make_version(2, 0, 0)))
            repository.register_package(make_release("beta", make_version(2, 1, 0)))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})
            self.assertIsInstance(repository.all_packages(), set)

    def test_get_releases_missing_package_raises(self) -> None:
        """PRECONDITION: an unregistered package name raises PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as raised:
                repository.get_releases("missing")
            self.assertEqual(raised.exception.package_name, "missing")

    def test_get_releases_returns_independent_copy(self) -> None:
        """POSTCONDITION: the returned release list is a copy detached from storage."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(2, 0, 0)))

            first = repository.get_releases("alpha")
            self.assertEqual(len(first), 2)
            first.clear()
            self.assertEqual(len(first), 0)
            self.assertEqual(len(repository.get_releases("alpha")), 2)

    # ------------------------------------------------------------------
    # DependencySolver (semver.solver.*)
    # ------------------------------------------------------------------
    def test_resolve_selects_highest_compatible(self) -> None:
        """POSTCONDITION: resolve selects the highest compatible release version."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            for version in (make_version(1, 0, 0), make_version(1, 2, 0), make_version(2, 0, 0)):
                repository.register_package(make_release("liba", version))

            outcome = solver.resolve([make_dependency("liba", ">=1.0.0 <2.0.0")])
            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(dict(outcome.selected_versions), {"liba": make_version(1, 2, 0)})
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_transitive_dependencies_highest(self) -> None:
        """POSTCONDITION: root and transitive dependencies are satisfied jointly."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                make_release("liba", make_version(1, 0, 0), (make_dependency("libb", ">=1.0.0 <2.0.0"),))
            )
            for version in (make_version(1, 0, 0), make_version(1, 5, 0), make_version(2, 0, 0)):
                repository.register_package(make_release("libb", version))

            outcome = solver.resolve([make_dependency("liba", "1.x")])
            self.assertEqual(
                dict(outcome.selected_versions),
                {"liba": make_version(1, 0, 0), "libb": make_version(1, 5, 0)},
            )
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_backtracks_to_compatible_release(self) -> None:
        """POSTCONDITION: unsatisfiable higher releases are backtracked over."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                make_release("liba", make_version(1, 0, 0), (make_dependency("libb", "1.x"),))
            )
            repository.register_package(
                make_release("liba", make_version(2, 0, 0), (make_dependency("libb", "2.x"),))
            )
            for version in (make_version(1, 0, 0), make_version(1, 1, 0), make_version(2, 0, 0)):
                repository.register_package(make_release("libb", version))

            outcome = solver.resolve(
                [make_dependency("liba", ">=1.0.0"), make_dependency("libb", "1.x")]
            )
            self.assertEqual(
                dict(outcome.selected_versions),
                {"liba": make_version(1, 0, 0), "libb": make_version(1, 1, 0)},
            )

    def test_resolve_merges_transitive_constraints(self) -> None:
        """POSTCONDITION: intersection of all accumulated constraints is satisfied."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                make_release("liba", make_version(1, 0, 0), (make_dependency("libc", ">=1.0.0"),))
            )
            repository.register_package(
                make_release("libb", make_version(1, 0, 0), (make_dependency("libc", "<2.0.0"),))
            )
            for version in (make_version(1, 0, 0), make_version(1, 5, 0), make_version(2, 0, 0)):
                repository.register_package(make_release("libc", version))

            outcome = solver.resolve(
                [make_dependency("liba", "1.x"), make_dependency("libb", "1.x")]
            )
            self.assertEqual(
                dict(outcome.selected_versions),
                {"liba": make_version(1, 0, 0), "libb": make_version(1, 0, 0), "libc": make_version(1, 5, 0)},
            )
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_reports_conflict_with_packages(self) -> None:
        """PRECONDITION: unsatisfiable constraints raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(make_release("libb", make_version(1, 0, 0)))

            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([make_dependency("libb", ">=3.0.0")])
            conflict = raised.exception
            self.assertIn("libb", conflict.conflicting_packages)
            self.assertIsInstance(conflict.conflicting_packages, tuple)
            self.assertIsInstance(conflict.explanation, str)
            self.assertGreater(len(conflict.explanation), 0)

    def test_resolve_assigned_dependency_conflict_backtracks(self) -> None:
        """POSTCONDITION: a dependency conflicting with an assigned version is backtracked."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(1, 1, 0)))
            repository.register_package(
                make_release("zeta", make_version(2, 0, 0), (make_dependency("alpha", "2.x"),))
            )
            repository.register_package(
                make_release("zeta", make_version(1, 0, 0), (make_dependency("alpha", "1.x"),))
            )

            outcome = solver.resolve(
                [make_dependency("alpha", "1.x"), make_dependency("zeta", ">=1.0.0")]
            )
            self.assertEqual(
                dict(outcome.selected_versions),
                {"alpha": make_version(1, 1, 0), "zeta": make_version(1, 0, 0)},
            )

    def test_resolve_rolls_back_constraints_and_exhausts_candidates(self) -> None:
        """PRECONDITION: rollback, assigned-dependency conflict, and exhaustion raise."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(1, 1, 0)))
            repository.register_package(
                make_release("zeta", make_version(1, 0, 0), (make_dependency("alpha", "2.x"),))
            )
            repository.register_package(
                make_release("zeta", make_version(1, 1, 0), (make_dependency("gamma", ">=1.0.0"),))
            )

            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve(
                    [make_dependency("alpha", "1.x"), make_dependency("zeta", "1.x")]
                )
            conflict = raised.exception
            self.assertIsInstance(conflict.conflicting_packages, tuple)
            self.assertIn("zeta", conflict.conflicting_packages)
            self.assertIsInstance(conflict.explanation, str)
            self.assertGreater(len(conflict.explanation), 0)

    def test_resolve_missing_package_becomes_conflict(self) -> None:
        """PRECONDITION: unregistered packages surface as ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([make_dependency("ghost", "1.x")])
            conflict = raised.exception
            self.assertIn("ghost", conflict.conflicting_packages)
            self.assertGreater(len(conflict.explanation), 0)

    def test_resolve_empty_root_dependencies(self) -> None:
        """POSTCONDITION: an empty root set resolves to an empty assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([])
            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(dict(outcome.selected_versions), {})
            self.assertIsInstance(outcome.derivation_steps, tuple)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:35:48Z
# LAST_CHANGED: 2026-11-09T22:35:05Z
# CHANGE: Resolve four remaining coverage items: (1) malformed pre-release identifier grammar — added range bounds with leading-zero numeric prerelease identifiers ('>=1.2.3-01', '>=1.0.0-alpha.01') to test_parse_range_rejects_malformed_bounds, each expecting InvalidRangeError; (2) bare wildcard operand expansions — added '!=*', '<*', '<=*', '>*', '^*', '~*' to the valid comparator/prefix parse coverage and satisfies assertions on each bare-star operand (boolean contract for !=*,<*,>*,^*,~*; True for <=*) so every expansion is exercised; (3) caret zero minor patch boundary — added '^0.0.3' boundary assertions (0.0.3 satisfies; 0.0.2 and 0.0.4 do not) covering the zero-major/zero-minor concrete-patch caret expansion; (4) hyphen bare wildcard bounds — added star_lower '* - 2.0.0' (<=2.0.0 endpoints) and star_upper '1.0.0 - *' (>=1.0.0 endpoints) satisfies coverage alongside the existing wildcard-bound hyphen cases.
# COVERAGE_AUDIT: 2026-11-09T22:35:48Z
# QA_AUDIT: 2026-11-09T22:35:30Z
# --- END AUTOFAB METADATA ---
