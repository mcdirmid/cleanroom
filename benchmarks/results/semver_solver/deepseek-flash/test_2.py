"""Unit tests for semver_solver_impl per its low-level grounding specification.

Covers the three singleton services (VersionEngine, PackageRepository,
DependencySolver) registered by the implementation module. Each test resolves
the target singleton from an isolated LifecycleRegistry inside a single
``enter_phase(system, ...)`` scope, then asserts the postconditions contracted
in ``low/semver_solver_impl.pyi`` and ``low/semver_solver.pyi``.
"""

from __future__ import annotations

import unittest
from pathlib import Path
import sys
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

# Ensure the component package root is importable regardless of checkout layout.
_PARTS_ROOT = str(Path(__file__).resolve().parents[2])
if _PARTS_ROOT not in sys.path:
    sys.path.insert(0, _PARTS_ROOT)

from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
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


def make_version(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> Version:
    """Wraps primitive components into an immutable domain Version record."""
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def make_range(raw_text: str) -> VersionRange:
    """Wraps a raw range expression into an immutable domain VersionRange record."""
    return VersionRange(raw_text=raw_text)


def make_dependency(name: str, raw_range: str) -> PackageDependency:
    """Wraps a package name and raw range expression into a PackageDependency."""
    return PackageDependency(name=name, range_constraint=make_range(raw_range))


def make_release(
    name: str,
    major: int,
    minor: int,
    patch: int,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Wraps a name, version components, and dependencies into a PackageRelease."""
    return PackageRelease(
        name=name,
        version=make_version(major, minor, patch),
        dependencies=dependencies,
    )


class VersionEngineTest(unittest.TestCase):
    """Tests VersionEngine SemVer 2.0.0 parsing, precedence, and range semantics."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_records_all_components(self) -> None:
        """POSTCONDITIONS: parse_version yields a Version with every component tuple."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            full = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(full, make_version(1, 2, 3, ("alpha", "1"), ("build", "5")))
            self.assertEqual(full.major, 1)
            self.assertEqual(full.minor, 2)
            self.assertEqual(full.patch, 3)
            self.assertEqual(full.prerelease, ("alpha", "1"))
            self.assertEqual(full.build, ("build", "5"))

            plain = engine.parse_version("10.20.30")
            self.assertEqual(plain, make_version(10, 20, 30))
            self.assertEqual(plain.prerelease, ())
            self.assertEqual(plain.build, ())

            prerelease_only = engine.parse_version("0.0.0-rc.2")
            self.assertEqual(prerelease_only.prerelease, ("rc", "2"))
            self.assertEqual(prerelease_only.build, ())

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """WHEN numeric identifiers have leading zeroes, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            for text in ("01.2.3", "1.02.3", "1.2.03"):
                with self.assertRaises(InvalidVersionError) as ctx:
                    engine.parse_version(text)
                self.assertEqual(ctx.exception.raw_text, text)

    def test_parse_version_rejects_malformed_grammar(self) -> None:
        """WHEN text violates SemVer 2.0.0 grammar, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            for text in ("1.2", "1.2.3.4", "1.2.3-", "1.2.3+", "not-a-version", " 1.2.3"):
                with self.assertRaises(InvalidVersionError) as ctx:
                    engine.parse_version(text)
                self.assertEqual(ctx.exception.raw_text, text)

    def test_compare_precedence_numeric_components(self) -> None:
        """POSTCONDITIONS: numeric components compare numerically, sign encodes ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            self.assertLess(
                engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 4)), 0
            )
            self.assertLess(
                engine.compare_precedence(make_version(1, 2, 3), make_version(1, 3, 0)), 0
            )
            self.assertLess(
                engine.compare_precedence(make_version(1, 9, 9), make_version(2, 0, 0)), 0
            )
            self.assertEqual(
                engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 3)), 0
            )
            self.assertGreater(
                engine.compare_precedence(make_version(2, 0, 0), make_version(1, 9, 9)), 0
            )
            self.assertGreater(
                engine.compare_precedence(make_version(1, 10, 0), make_version(1, 9, 9)), 0
            )

    def test_compare_precedence_prerelease_ordering(self) -> None:
        """POSTCONDITIONS: prerelease ranks below normal, numeric below string, longer
        sequences higher.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            # Normal version outranks a prerelease sharing major/minor/patch.
            self.assertGreater(
                engine.compare_precedence(make_version(1, 0, 0), make_version(1, 0, 0, ("alpha",))),
                0,
            )
            # Prerelease sequence from the SemVer 2.0.0 specification.
            ordered = [
                make_version(1, 0, 0, ("alpha",)),
                make_version(1, 0, 0, ("alpha", "1")),
                make_version(1, 0, 0, ("alpha", "beta")),
                make_version(1, 0, 0, ("beta",)),
                make_version(1, 0, 0, ("beta", "2")),
                make_version(1, 0, 0, ("beta", "11")),
                make_version(1, 0, 0, ("rc", "1")),
                make_version(1, 0, 0),
            ]
            for lower, higher in zip(ordered, ordered[1:]):
                self.assertLess(engine.compare_precedence(lower, higher), 0)
                self.assertGreater(engine.compare_precedence(higher, lower), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: build metadata is excluded entirely from precedence comparison."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            plain = make_version(1, 2, 3)
            built = make_version(1, 2, 3, (), ("build", "9"))
            self.assertEqual(engine.compare_precedence(plain, built), 0)
            self.assertEqual(engine.compare_precedence(built, plain), 0)

    def test_parse_range_trims_surrounding_whitespace(self) -> None:
        """POSTCONDITIONS: surrounding whitespace is trimmed and stored in raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            trimmed = engine.parse_range("  >=1.0.0  ")
            self.assertEqual(trimmed.raw_text, ">=1.0.0")

            tabbed = engine.parse_range("\t^1.2.3\n")
            self.assertEqual(tabbed.raw_text, "^1.2.3")

    def test_parse_range_accepts_contracted_syntax(self) -> None:
        """POSTCONDITIONS: comparators, caret, tilde, wildcards, hyphens, and unions parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            for text in (
                "==1.2.3",
                "=1.2.3",
                "!=1.2.3",
                "<1.2.3",
                "<=1.2.3",
                ">1.2.3",
                ">=1.2.3",
                "^1.2.3",
                "~1.2.3",
                "1.x",
                "1.*",
                "1.2.x",
                "1.2.*",
                "1.2.3 - 2.3.4",
                ">=1.0.0 <2.0.0",
                "1.x || 3.x",
            ):
                parsed = engine.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

            # Optional whitespace between a relational operator and its target is accepted.
            spaced = engine.parse_range(">= 1.0.0")
            self.assertEqual(spaced.raw_text.replace(" ", ""), ">=1.0.0")

    def test_parse_range_accepts_unbounded_wildcards(self) -> None:
        """POSTCONDITIONS: bare unbounded wildcard forms ('*', 'x', 'X') parse successfully."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            star = engine.parse_range("*")
            self.assertEqual(star.raw_text, "*")

            for text in ("x", "X"):
                parsed = engine.parse_range(text)
                self.assertIn(parsed.raw_text.strip().lower(), ("x", "*"))

    def test_parse_range_rejects_invalid_expressions(self) -> None:
        """WHEN range text is empty, has empty clauses, commas, bare partials, or is
        malformed, MUST raise InvalidRangeError carrying the original raw range.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            invalid = (
                "",
                "   ",
                ">=1.0.0 ||",
                "|| >=1.0.0",
                ">=1.0.0 || || <2.0.0",
                ">=1.0.0, <2.0.0",
                "1",
                "1.2",
                "^0.0",
                "~1.2",
                "1.2 - 2.3",
                ">=1.0.0 <<2.0.0",
                "abc",
                # Unbounded wildcards are not valid hyphen-range operands.
                "1.2.3 - *",
                "* - 2.0.0",
                # Unbounded wildcards cannot be combined with these operators.
                "!=*",
                ">*",
                "<*",
                "^*",
                "~*",
                # Hyphen clauses must have the LOW - HIGH shape.
                "1.2.3 - 2.3.4 - 3.4.5",
                # Operator tokens require an operand.
                ">=",
                ">",
                "<",
                "<=",
                "=",
                "==",
                "!=",
                "~",
                "^",
            )
            for text in invalid:
                with self.assertRaises(InvalidRangeError) as ctx:
                    engine.parse_range(text)
                self.assertEqual(ctx.exception.raw_range, text)

    def test_satisfies_comparator_branches(self) -> None:
        """POSTCONDITIONS: each comparator evaluates candidates against its boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            candidate = make_version(1, 5, 0)

            self.assertTrue(engine.satisfies(candidate, engine.parse_range(">=1.0.0"), False))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range("<1.0.0"), False))
            self.assertTrue(engine.satisfies(candidate, engine.parse_range(">1.0.0"), False))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range("<=1.0.0"), False))

            exact = make_version(1, 2, 3)
            self.assertTrue(engine.satisfies(exact, engine.parse_range("==1.2.3"), False))
            self.assertTrue(engine.satisfies(exact, engine.parse_range("=1.2.3"), False))
            self.assertTrue(engine.satisfies(exact, engine.parse_range("<=1.2.3"), False))
            self.assertFalse(engine.satisfies(exact, engine.parse_range("!=1.2.3"), False))
            self.assertFalse(engine.satisfies(exact, engine.parse_range(">1.2.3"), False))

    def test_satisfies_expands_prefix_and_set_notation(self) -> None:
        """POSTCONDITIONS: caret, tilde, wildcard, hyphen, conjunctive, and union ranges
        expand into comparator boundaries.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            # Caret expands around the first non-zero component boundary.
            self.assertTrue(
                engine.satisfies(make_version(1, 2, 3), engine.parse_range("^1.2.0"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(1, 9, 9), engine.parse_range("^1.2.0"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(2, 0, 0), engine.parse_range("^1.2.0"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(0, 2, 4), engine.parse_range("^0.2.3"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(0, 3, 0), engine.parse_range("^0.2.3"), False)
            )

            # Tilde expands into minor boundaries.
            self.assertTrue(
                engine.satisfies(make_version(1, 2, 9), engine.parse_range("~1.2.3"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(1, 3, 0), engine.parse_range("~1.2.3"), False)
            )

            # Wildcards normalize into paired comparator inequalities.
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), engine.parse_range("1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), engine.parse_range("1.x"), False))
            self.assertTrue(
                engine.satisfies(make_version(1, 2, 7), engine.parse_range("1.2.*"), False)
            )

            # Hyphen ranges become lower/upper bounds.
            self.assertTrue(
                engine.satisfies(make_version(1, 2, 3), engine.parse_range("1.2.3 - 2.3.4"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(2, 3, 4), engine.parse_range("1.2.3 - 2.3.4"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(2, 3, 5), engine.parse_range("1.2.3 - 2.3.4"), False)
            )

            # Conjunctive comparators and disjunctive union alternatives.
            self.assertTrue(
                engine.satisfies(make_version(1, 5, 0), engine.parse_range(">=1.0.0 <2.0.0"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(2, 0, 0), engine.parse_range(">=1.0.0 <2.0.0"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(3, 1, 0), engine.parse_range("1.x || 3.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(2, 0, 0), engine.parse_range("1.x || 3.x"), False)
            )

    def test_satisfies_zero_major_caret_and_tilde_wildcards(self) -> None:
        """POSTCONDITIONS: caret expansion bounds zero-major operands by their first non-zero
        component, and tilde expansion bounds operands whose minor is a wildcard.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            # ^0.x bounds the whole zero-major block.
            self.assertTrue(
                engine.satisfies(make_version(0, 5, 0), engine.parse_range("^0.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(1, 0, 0), engine.parse_range("^0.x"), False)
            )

            # ^0.0.x bounds the patch block of a zero-major, zero-minor operand.
            self.assertTrue(
                engine.satisfies(make_version(0, 0, 7), engine.parse_range("^0.0.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(0, 1, 0), engine.parse_range("^0.0.x"), False)
            )

            # ^0.0.3 bounds a concrete patch by its immediate successor.
            self.assertTrue(
                engine.satisfies(make_version(0, 0, 3), engine.parse_range("^0.0.3"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(0, 0, 4), engine.parse_range("^0.0.3"), False)
            )

            # A wildcard minor also bounds a non-zero major caret.
            self.assertTrue(
                engine.satisfies(make_version(1, 5, 0), engine.parse_range("^1.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(2, 0, 0), engine.parse_range("^1.x"), False)
            )

            # ~1.x leaves the minor unspecified and bounds the next major.
            self.assertTrue(
                engine.satisfies(make_version(1, 9, 9), engine.parse_range("~1.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(2, 0, 0), engine.parse_range("~1.x"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(1, 2, 5), engine.parse_range("~1.2.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(1, 3, 0), engine.parse_range("~1.2.x"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(0, 9, 9), engine.parse_range("~0.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(1, 0, 0), engine.parse_range("~0.x"), False)
            )

    def test_satisfies_relational_and_exclusion_wildcard_operands(self) -> None:
        """POSTCONDITIONS: a relational comparison against a wildcard block normalizes to an
        inequality at the next block boundary, and '!=' wildcards exclude an entire minor or
        patch block.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            self.assertTrue(engine.satisfies(make_version(1, 0, 0), engine.parse_range(">=1.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), engine.parse_range(">=1.x"), False))

            self.assertFalse(engine.satisfies(make_version(1, 9, 9), engine.parse_range(">1.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), engine.parse_range(">1.x"), False))

            self.assertTrue(engine.satisfies(make_version(0, 9, 9), engine.parse_range("<1.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), engine.parse_range("<1.x"), False))

            self.assertTrue(engine.satisfies(make_version(1, 9, 9), engine.parse_range("<=1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), engine.parse_range("<=1.x"), False))

            self.assertTrue(
                engine.satisfies(make_version(1, 2, 0), engine.parse_range(">=1.2.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(1, 1, 9), engine.parse_range(">=1.2.x"), False)
            )

            self.assertFalse(
                engine.satisfies(make_version(1, 2, 9), engine.parse_range(">1.2.x"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(1, 3, 0), engine.parse_range(">1.2.x"), False)
            )

            self.assertTrue(
                engine.satisfies(make_version(1, 1, 9), engine.parse_range("<1.2.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(1, 2, 0), engine.parse_range("<1.2.x"), False)
            )

            self.assertTrue(
                engine.satisfies(make_version(1, 2, 9), engine.parse_range("<=1.2.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(1, 3, 0), engine.parse_range("<=1.2.x"), False)
            )

            # '!=' with a wildcard excludes the entire bounded block.
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), engine.parse_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 9), engine.parse_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), engine.parse_range("!=1.x"), False))
            self.assertFalse(
                engine.satisfies(make_version(1, 2, 5), engine.parse_range("!=1.2.x"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(1, 1, 9), engine.parse_range("!=1.2.x"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(1, 3, 0), engine.parse_range("!=1.2.x"), False)
            )

    def test_satisfies_hyphen_range_with_wildcard_upper_bound(self) -> None:
        """POSTCONDITIONS: hyphen ranges accept wildcard upper operands and bound the next block."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            self.assertTrue(
                engine.satisfies(make_version(1, 2, 3), engine.parse_range("1.2.3 - 2.x"), False)
            )
            self.assertTrue(
                engine.satisfies(make_version(2, 9, 9), engine.parse_range("1.2.3 - 2.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(3, 0, 0), engine.parse_range("1.2.3 - 2.x"), False)
            )

            self.assertTrue(
                engine.satisfies(make_version(2, 3, 9), engine.parse_range("1.2.3 - 2.3.x"), False)
            )
            self.assertFalse(
                engine.satisfies(make_version(2, 4, 0), engine.parse_range("1.2.3 - 2.3.x"), False)
            )

    def test_satisfies_prerelease_excluded_unless_targeted(self) -> None:
        """WHEN a candidate is a prerelease and include_prerelease is False, MUST evaluate to
        False unless the range explicitly targets that prerelease.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            candidate = make_version(1, 0, 0, ("alpha",))

            self.assertFalse(engine.satisfies(candidate, engine.parse_range(">=0.9.0"), False))
            # A normal candidate is unaffected by prerelease filtering.
            self.assertTrue(
                engine.satisfies(make_version(1, 0, 0), engine.parse_range(">=0.9.0"), False)
            )
            # Explicit prerelease targeting shares the same major/minor/patch numbers.
            self.assertTrue(
                engine.satisfies(candidate, engine.parse_range(">=1.0.0-alpha"), False)
            )

    def test_satisfies_prerelease_included_by_precedence(self) -> None:
        """WHEN include_prerelease is True, MUST compare prereleases directly against the
        comparator boundaries without shifting numerical boundaries.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            # 1.0.0-alpha ranks strictly lower than 1.0.0, so it does not satisfy >=1.0.0.
            self.assertFalse(
                engine.satisfies(make_version(1, 0, 0, ("alpha",)), engine.parse_range(">=1.0.0"), True)
            )
            self.assertTrue(
                engine.satisfies(
                    make_version(1, 0, 0, ("alpha",)), engine.parse_range(">=1.0.0-alpha"), True
                )
            )
            self.assertFalse(
                engine.satisfies(
                    make_version(1, 0, 0, ("alpha",)), engine.parse_range(">=1.0.0-beta"), True
                )
            )
            self.assertTrue(
                engine.satisfies(make_version(1, 2, 3, ("beta",)), engine.parse_range(">=1.0.0"), True)
            )


class PackageRepositoryTest(unittest.TestCase):
    """Tests PackageRepository release storage, ordering, and lookup contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_register_and_get_releases_sorted_descending(self) -> None:
        """POSTCONDITIONS: get_releases yields every registered release ordered descending."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)

            repository.register_package(make_release("pkg", 1, 0, 0))
            repository.register_package(make_release("pkg", 2, 0, 0))
            repository.register_package(make_release("pkg", 1, 5, 0))
            repository.register_package(make_release("other", 9, 0, 0))

            releases = repository.get_releases("pkg")
            self.assertEqual(
                [release.version for release in releases],
                [make_version(2, 0, 0), make_version(1, 5, 0), make_version(1, 0, 0)],
            )
            self.assertEqual([release.name for release in releases], ["pkg", "pkg", "pkg"])

    def test_get_releases_preserves_dependencies(self) -> None:
        """POSTCONDITIONS: registered dependency declarations are retained with the release."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            dependency = make_dependency("dep", "^2.0.0")
            release = make_release("pkg", 3, 1, 0, (dependency,))

            repository.register_package(release)

            releases = repository.get_releases("pkg")
            self.assertEqual(len(releases), 1)
            self.assertEqual(releases[0].version, make_version(3, 1, 0))
            self.assertEqual(releases[0].dependencies, (dependency,))

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITIONS: get_releases produces a shallow copy of the sorted release list."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("pkg", 1, 0, 0))

            first = repository.get_releases("pkg")
            first.append(make_release("pkg", 9, 9, 9))

            second = repository.get_releases("pkg")
            self.assertEqual(len(second), 1)
            self.assertEqual(second[0].version, make_version(1, 0, 0))

    def test_get_releases_unknown_package_raises(self) -> None:
        """WHEN the package name is not registered, MUST raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)

            with self.assertRaises(PackageNotFoundError) as ctx:
                repository.get_releases("missing")
            self.assertEqual(ctx.exception.package_name, "missing")

    def test_has_package_and_all_packages(self) -> None:
        """POSTCONDITIONS: has_package reports membership and all_packages enumerates names."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertEqual(repository.all_packages(), set())

            repository.register_package(make_release("alpha", 1, 0, 0))
            repository.register_package(make_release("beta", 1, 0, 0))
            repository.register_package(make_release("alpha", 2, 0, 0))

            self.assertTrue(repository.has_package("alpha"))
            self.assertTrue(repository.has_package("beta"))
            self.assertFalse(repository.has_package("gamma"))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})


class DependencySolverTest(unittest.TestCase):
    """Tests DependencySolver backtracking resolution and conflict reporting contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_resolve_selects_highest_compatible_versions(self) -> None:
        """POSTCONDITIONS: resolve returns a ResolutionOutcome selecting the highest precedence
        compatible release for each package, including transitive dependencies.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            repository.register_package(make_release("a", 1, 0, 0))
            repository.register_package(make_release("a", 2, 0, 0))
            repository.register_package(make_release("b", 1, 0, 0, (make_dependency("a", "^1.0.0"),)))
            repository.register_package(make_release("b", 1, 5, 0, (make_dependency("a", "^2.0.0"),)))

            outcome = solver.resolve([make_dependency("b", "^1.0.0")])

            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(outcome.selected_versions["b"], make_version(1, 5, 0))
            self.assertEqual(outcome.selected_versions["a"], make_version(2, 0, 0))
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_respects_multiple_root_constraints(self) -> None:
        """POSTCONDITIONS: resolve intersects every root constraint on a shared package."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            repository.register_package(make_release("a", 1, 0, 0))
            repository.register_package(make_release("a", 1, 5, 0))
            repository.register_package(make_release("a", 2, 0, 0))

            outcome = solver.resolve(
                [
                    make_dependency("a", ">=1.0.0"),
                    make_dependency("a", "<2.0.0"),
                ]
            )

            self.assertEqual(outcome.selected_versions["a"], make_version(1, 5, 0))

    def test_resolve_backtracks_and_finds_alternative(self) -> None:
        """POSTCONDITIONS: when the highest candidate conflicts, backtracking selects a lower
        compatible release rather than failing.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            repository.register_package(make_release("a", 1, 0, 0))
            repository.register_package(make_release("a", 2, 0, 0))
            repository.register_package(make_release("b", 1, 0, 0, (make_dependency("a", "^1.0.0"),)))
            repository.register_package(make_release("b", 2, 0, 0, (make_dependency("a", "^3.0.0"),)))

            outcome = solver.resolve(
                [
                    make_dependency("a", ">=1.0.0"),
                    make_dependency("b", ">=1.0.0"),
                ]
            )

            self.assertEqual(outcome.selected_versions["a"], make_version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["b"], make_version(1, 0, 0))

    def test_resolve_rolls_back_transitive_constraints(self) -> None:
        """POSTCONDITIONS: a candidate release's transitive dependencies merge into the
        accumulated constraint mapping and that mapping is restored when the branch backtracks.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            repository.register_package(make_release("p", 1, 0, 0, (make_dependency("q", ">=0.5.0"),)))
            repository.register_package(make_release("p", 2, 0, 0, (make_dependency("q", ">=1.0.0"),)))
            repository.register_package(make_release("q", 0, 5, 0))

            outcome = solver.resolve([make_dependency("p", ">=1.0.0")])

            # Selecting p 2.0.0 imposes q >=1.0.0, which has no viable release; the stale
            # transitive constraint must be removed before p 1.0.0 allows q 0.5.0.
            self.assertEqual(outcome.selected_versions["p"], make_version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["q"], make_version(0, 5, 0))

    def test_resolve_reports_transitive_requester_in_conflict(self) -> None:
        """WHEN a transitive dependency conflicts, MUST report every requesting package
        involved rather than only the dependency target.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            repository.register_package(make_release("c", 1, 0, 0))
            repository.register_package(make_release("b", 1, 0, 0, (make_dependency("c", ">=2.0.0"),)))

            with self.assertRaises(ResolutionConflictError) as ctx:
                solver.resolve([make_dependency("b", ">=1.0.0")])

            self.assertIn("c", ctx.exception.conflicting_packages)
            self.assertIn("b", ctx.exception.conflicting_packages)
            self.assertGreater(len(ctx.exception.explanation), 0)

    def test_resolve_with_empty_root_dependencies(self) -> None:
        """POSTCONDITIONS: an empty requirement collection yields an empty assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)

            outcome = solver.resolve([])

            self.assertEqual(dict(outcome.selected_versions), {})
            self.assertEqual(outcome.derivation_steps, ())

    def test_resolve_unsatisfiable_conflict_raises(self) -> None:
        """WHEN constraints are mutually unsatisfiable, MUST raise ResolutionConflictError with
        conflicting packages and a derivation explanation.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            repository.register_package(make_release("a", 1, 0, 0))
            repository.register_package(make_release("a", 2, 0, 0))
            repository.register_package(make_release("b", 1, 0, 0, (make_dependency("a", "<2.0.0"),)))

            with self.assertRaises(ResolutionConflictError) as ctx:
                solver.resolve(
                    [
                        make_dependency("a", ">=2.0.0"),
                        make_dependency("b", "1.0.0"),
                    ]
                )

            self.assertIn("a", ctx.exception.conflicting_packages)
            self.assertGreater(len(ctx.exception.explanation), 0)

    def test_resolve_unregistered_package_reports_conflict(self) -> None:
        """WHEN a dependency references an unregistered package, MUST raise
        ResolutionConflictError rather than leaking PackageNotFoundError.
        """
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)

            with self.assertRaises(ResolutionConflictError) as ctx:
                solver.resolve([make_dependency("ghost", ">=1.0.0")])

            self.assertIn("ghost", ctx.exception.conflicting_packages)
            self.assertGreater(len(ctx.exception.explanation), 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T00:51:39Z
# LAST_CHANGED: 2026-11-05T00:46:58Z
# CHANGE: Add the grammar/error and expansion assertions the feedback identified as uncovered: (1) parse_range now asserts bare unbounded wildcards '*'/'x'/'X' parse, and InvalidRangeError for unbounded wildcards as either hyphen operand, '!=*' / '>*' / '<*', '^*' / '~*', non-LOW-HIGH hyphen clauses, and operator tokens missing operands (all asserting raw_range carries the original text); (2) satisfies now covers zero-major caret upper boundaries (^0.x, ^0.0.x, ^0.0.3), wildcard-minor carets/tildes (^1.x, ~1.x, ~1.2.x, ~0.x), relational comparators against wildcard blocks (>, >=, <, <= with M.x and M.m.x normalizing to the next block boundary), wildcard '!=' block exclusion (!=1.x, !=1.2.x), and hyphen ranges with wildcard upper operands (1.2.3 - 2.x, 1.2.3 - 2.3.x); (3) DependencySolver now drives a branch whose newly merged transitive constraint (q >=1.0.0 from p 2.0.0) must be rolled back before p 1.0.0 succeeds with q 0.5.0, and asserts a transitive requester ('b') appears alongside the dependency target ('c') in ResolutionConflictError.conflicting_packages.
# COVERAGE_AUDIT: 2026-11-05T00:51:39Z
# QA_AUDIT: 2026-11-05T00:51:26Z
# --- END AUTOFAB METADATA ---
