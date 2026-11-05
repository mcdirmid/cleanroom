"""Unit tests for semver_solver_impl per its low-level grounding specification."""

from __future__ import annotations

import os
import sys
import unittest
from typing import cast

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system
from semver_solver.lib.semver_solver import (
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
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
    """Verifies VersionEngine, PackageRepository, and DependencySolver contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def _engine(self, scope: LifecycleScope) -> VersionEngine:
        return scope.get_singleton(VersionEngine)

    def _repository(self, scope: LifecycleScope) -> PackageRepository:
        return scope.get_singleton(PackageRepository)

    def _solver(self, scope: LifecycleScope) -> DependencySolver:
        return scope.get_singleton(DependencySolver)

    def _register(self, repository: PackageRepository, *releases: PackageRelease) -> None:
        for release in releases:
            repository.register_package(release)

    def test_parse_version_populates_components(self) -> None:
        """Happy path POSTCONDITIONS: parse_version yields major, minor, patch tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))
            self.assertTrue(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3-alpha.1+build.5")
            self.assertEqual(str(version), "1.2.3-alpha.1+build.5")

    def test_parse_version_without_prerelease_or_build(self) -> None:
        """Happy path POSTCONDITIONS: absent prerelease/build produce empty tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            version = engine.parse_version("0.1.0")
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ())
            self.assertFalse(version.is_prerelease)
            self.assertEqual(version.format(), "0.1.0")

    def test_parse_version_reports_contract_error(self) -> None:
        """WHEN grammar or leading zeroes are invalid, MUST report InvalidVersionError."""
        malformed = [
            "",
            "1.2",
            "1.2.3.4",
            "abc",
            "1.0.0-",
            "1.0.0+",
            "1.0.0-alpha..",
            "1.2.3-alpha_1",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.0.0-01",
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            for text in malformed:
                with self.subTest(text=text):
                    with self.assertRaises(Exception) as raised:
                        engine.parse_version(text)
                    self.assertIsInstance(raised.exception, InvalidVersionError)
                    error = cast(InvalidVersionError, raised.exception)
                    self.assertEqual(error.raw_text, text)

    def test_parse_range_reports_contract_error(self) -> None:
        """WHEN range text is malformed or partial, MUST report InvalidRangeError."""
        malformed = [
            "",
            "   ",
            "1.0.0 || ",
            "|| 1.0.0",
            ">=1.0.0,<2.0.0",
            "1",
            "1.2",
            "^0.0",
            ">=1",
            "1.2 - 2.3",
            "not-a-range",
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            for text in malformed:
                with self.subTest(text=text):
                    with self.assertRaises(Exception) as raised:
                        engine.parse_range(text)
                    self.assertIsInstance(raised.exception, InvalidRangeError)
                    error = cast(InvalidRangeError, raised.exception)
                    if text.strip():
                        self.assertEqual(error.raw_range, text)

    def test_resolve_reports_conflict_details(self) -> None:
        """WHEN constraints cannot be satisfied, MUST report ResolutionConflictError details."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            self._register(
                repository,
                PackageRelease(name="lib", version=Version(1, 0, 0)),
            )
            root = (PackageDependency(name="lib", range_constraint=engine.parse_range(">=2.0.0")),)
            with self.assertRaises(Exception) as raised:
                solver.resolve(root)
            self.assertIsInstance(raised.exception, ResolutionConflictError)
            error = cast(ResolutionConflictError, raised.exception)
            self.assertIn("lib", error.conflicting_packages)
            self.assertTrue(error.explanation.strip())

    def test_resolve_reports_conflict_for_unregistered_package(self) -> None:
        """WHEN a root dependency is absent, MUST report ResolutionConflictError details."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            self._register(
                repository,
                PackageRelease(name="lib", version=Version(1, 0, 0)),
            )
            root = (PackageDependency(name="ghost", range_constraint=engine.parse_range(">=1.0.0")),)
            with self.assertRaises(Exception) as raised:
                solver.resolve(root)
            self.assertIsInstance(raised.exception, ResolutionConflictError)
            error = cast(ResolutionConflictError, raised.exception)
            self.assertIn("ghost", error.conflicting_packages)
            self.assertTrue(error.explanation.strip())

    def test_resolve_reports_conflict_for_unsatisfiable_transitive_graph(self) -> None:
        """WHEN transitive constraints are unsatisfiable, MUST report conflicting details."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            app_dependency = PackageDependency(
                name="lib",
                range_constraint=engine.parse_range(">=2.0.0"),
            )
            self._register(
                repository,
                PackageRelease(name="lib", version=Version(1, 0, 0)),
                PackageRelease(name="lib", version=Version(1, 5, 0)),
                PackageRelease(
                    name="app",
                    version=Version(1, 0, 0),
                    dependencies=(app_dependency,),
                ),
            )
            root = (PackageDependency(name="app", range_constraint=engine.parse_range(">=1.0.0")),)
            with self.assertRaises(Exception) as raised:
                solver.resolve(root)
            self.assertIsInstance(raised.exception, ResolutionConflictError)
            error = cast(ResolutionConflictError, raised.exception)
            self.assertTrue(error.conflicting_packages)
            self.assertIn("lib", error.conflicting_packages)
            self.assertTrue(error.explanation.strip())

    def test_compare_precedence_numeric_components(self) -> None:
        """POSTCONDITIONS: major/minor/patch compare numerically and symmetrically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            self.assertLess(engine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(2, 0, 0), Version(1, 0, 0)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 2, 0), Version(1, 3, 0)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 4)), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 10, 0), Version(1, 9, 0)), 0)
            self.assertEqual(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)

    def test_compare_precedence_ranks_release_above_prerelease(self) -> None:
        """POSTCONDITIONS: normal version outranks prerelease with identical numbers."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            release = Version(1, 0, 0)
            prerelease = Version(1, 0, 0, ("alpha",))
            self.assertLess(engine.compare_precedence(prerelease, release), 0)
            self.assertGreater(engine.compare_precedence(release, prerelease), 0)

    def test_compare_precedence_prerelease_segment_rules(self) -> None:
        """POSTCONDITIONS: numeric < string segments, ASCII strings, longer sequences rank higher."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            numeric = Version(1, 0, 0, ("1",))
            alpha = Version(1, 0, 0, ("alpha",))
            self.assertLess(engine.compare_precedence(numeric, alpha), 0)
            self.assertGreater(engine.compare_precedence(alpha, numeric), 0)
            self.assertLess(engine.compare_precedence(Version(1, 0, 0, ("2",)), Version(1, 0, 0, ("10",))), 0)
            self.assertLess(engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))), 0)
            self.assertLess(
                engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1"))),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha",))),
                0,
            )

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: build metadata never affects precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            left = Version(1, 0, 0, (), ("build", "1"))
            right = Version(1, 0, 0, (), ("build", "2"))
            self.assertEqual(engine.compare_precedence(left, right), 0)
            self.assertEqual(engine.compare_precedence(right, left), 0)
            self.assertEqual(engine.compare_precedence(Version(1, 0, 0, ("alpha",), ("b",)), Version(1, 0, 0, ("alpha",))), 0)

    def test_parse_range_trims_and_formats_text(self) -> None:
        """POSTCONDITIONS: surrounding whitespace trimmed and stored in raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            constraint = engine.parse_range("  >=1.0.0  ")
            self.assertEqual(constraint.raw_text, ">=1.0.0")
            self.assertEqual(str(constraint), ">=1.0.0")
            self.assertTrue(engine.satisfies(Version(1, 5, 0), constraint, False))

    def test_parse_range_accepts_operator_whitespace(self) -> None:
        """POSTCONDITIONS: optional whitespace between operator and version is accepted."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            self.assertTrue(engine.satisfies(Version(1, 5, 0), engine.parse_range(">= 1.0.0"), False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), engine.parse_range("  ^ 1.2.3  "), False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), engine.parse_range("~ 1.2.3"), False))

    def test_satisfies_basic_comparators(self) -> None:
        """POSTCONDITIONS: relational comparators accept and reject expected versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            candidate = Version(1, 0, 0)
            cases = [
                (">=1.0.0", True),
                ("<=1.0.0", True),
                ("==1.0.0", True),
                ("=1.0.0", True),
                (">1.0.0", False),
                ("<1.0.0", False),
                ("!=1.0.0", False),
                (">0.9.0", True),
                ("<1.0.1", True),
            ]
            for text, expected in cases:
                with self.subTest(text=text):
                    self.assertEqual(engine.satisfies(candidate, engine.parse_range(text), False), expected)

    def test_satisfies_conjunctive_clause(self) -> None:
        """POSTCONDITIONS: every comparator in a whitespace-delimited clause must hold."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            constraint = engine.parse_range(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 5, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 0), constraint, False))

    def test_satisfies_caret_expansion(self) -> None:
        """POSTCONDITIONS: caret prefixes expand from the first non-zero component boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            major = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), major, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), major, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), major, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), major, False))
            minor = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(Version(0, 2, 9), minor, False))
            self.assertFalse(engine.satisfies(Version(0, 3, 0), minor, False))
            patch = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(Version(0, 0, 3), patch, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 4), patch, False))

    def test_satisfies_tilde_expansion(self) -> None:
        """POSTCONDITIONS: tilde prefixes expand into lower and upper minor boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            constraint = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), constraint, False))

    def test_satisfies_wildcard_expansion(self) -> None:
        """POSTCONDITIONS: wildcards normalize into bounded comparator inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            patch_wild = engine.parse_range("1.2.x")
            self.assertTrue(engine.satisfies(Version(1, 2, 7), patch_wild, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), patch_wild, False))
            minor_wild = engine.parse_range("1.x")
            self.assertTrue(engine.satisfies(Version(1, 9, 0), minor_wild, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), minor_wild, False))
            any_wild = engine.parse_range("*")
            self.assertTrue(engine.satisfies(Version(5, 0, 0), any_wild, False))

    def test_satisfies_wildcard_relational_comparators(self) -> None:
        """POSTCONDITIONS: relational and negated comparators accept wildcard targets."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            at_least = engine.parse_range(">=1.2.x")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), at_least, False))
            self.assertFalse(engine.satisfies(Version(1, 1, 9), at_least, False))
            at_most = engine.parse_range("<=1.2.X")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), at_most, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), at_most, False))
            above = engine.parse_range(">1.2.*")
            self.assertFalse(engine.satisfies(Version(1, 2, 0), above, False))
            self.assertTrue(engine.satisfies(Version(1, 3, 0), above, False))
            below = engine.parse_range("<1.2.x")
            self.assertTrue(engine.satisfies(Version(1, 1, 9), below, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 0), below, False))
            negated = engine.parse_range("!=1.2.x")
            self.assertFalse(engine.satisfies(Version(1, 2, 0), negated, False))
            self.assertTrue(engine.satisfies(Version(1, 3, 0), negated, False))
            self.assertTrue(engine.satisfies(Version(1, 1, 9), negated, False))

    def test_satisfies_any_version_wildcard_comparators(self) -> None:
        """POSTCONDITIONS: bare any-version wildcards normalize to unbounded/empty bands."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            candidates = [Version(0, 0, 0), Version(1, 2, 3), Version(9, 9, 9)]
            for wildcard in ["*", "x", "X"]:
                at_least = engine.parse_range(">=" + wildcard)
                at_most = engine.parse_range("<=" + wildcard)
                above = engine.parse_range(">" + wildcard)
                below = engine.parse_range("<" + wildcard)
                negated = engine.parse_range("!=" + wildcard)
                for candidate in candidates:
                    label = f"{wildcard}:{candidate.major}.{candidate.minor}.{candidate.patch}"
                    with self.subTest(candidate=label):
                        self.assertTrue(engine.satisfies(candidate, at_least, False))
                        self.assertTrue(engine.satisfies(candidate, at_most, False))
                        self.assertFalse(engine.satisfies(candidate, above, False))
                        self.assertFalse(engine.satisfies(candidate, below, False))
                        self.assertFalse(engine.satisfies(candidate, negated, False))

    def test_satisfies_hyphen_range(self) -> None:
        """POSTCONDITIONS: hyphen ranges normalize into paired comparator inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            constraint = engine.parse_range("1.2.3 - 2.3.4")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), constraint, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(2, 3, 4), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 3, 5), constraint, False))

    def test_satisfies_hyphen_range_with_wildcard_endpoints(self) -> None:
        """POSTCONDITIONS: wildcard hyphen endpoints normalize into bounded inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            constraint = engine.parse_range("1.2.x - 2.x")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(2, 9, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 1, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), constraint, False))
            bounded = engine.parse_range("1.x - 2.3.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), bounded, False))
            self.assertTrue(engine.satisfies(Version(2, 3, 9), bounded, False))
            self.assertFalse(engine.satisfies(Version(2, 4, 0), bounded, False))

    def test_satisfies_hyphen_range_with_unbounded_wildcard_upper(self) -> None:
        """POSTCONDITIONS: a bare '*' upper endpoint leaves the upper bound unbounded."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            unbounded = engine.parse_range("1.2.3 - *")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), unbounded, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 4), unbounded, False))
            self.assertTrue(engine.satisfies(Version(9, 9, 9), unbounded, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), unbounded, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 0), unbounded, False))
            wildcard_lower = engine.parse_range("1.2.x - *")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), wildcard_lower, False))
            self.assertTrue(engine.satisfies(Version(5, 0, 0), wildcard_lower, False))
            self.assertFalse(engine.satisfies(Version(1, 1, 9), wildcard_lower, False))

    def test_satisfies_union_alternatives(self) -> None:
        """POSTCONDITIONS: union clauses evaluate to True when any alternative matches."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            constraint = engine.parse_range("1.0.0 || 2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), constraint, False))

    def test_satisfies_excludes_prerelease_unless_targeted(self) -> None:
        """WHEN range is not prerelease-aware, prereleases MUST be filtered out."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            broad = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(Version(1, 0, 0, ("alpha",)), broad, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0, ("alpha",)), broad, False))
            targeted = engine.parse_range(">=1.0.0-alpha")
            self.assertTrue(engine.satisfies(Version(1, 0, 0, ("alpha",)), targeted, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 1, ("alpha",)), targeted, False))

    def test_satisfies_include_prerelease_uses_precedence(self) -> None:
        """WHEN include_prerelease is True, boundaries MUST not shift for prereleases."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            broad = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(Version(1, 0, 0, ("alpha",)), broad, True))
            self.assertTrue(engine.satisfies(Version(1, 0, 1, ("alpha",)), broad, True))
            upper = engine.parse_range("<1.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0, ("alpha",)), upper, True))

    def test_data_type_canonical_formatting(self) -> None:
        """POSTCONDITIONS: Version and VersionRange string formatting is canonical."""
        version = Version(1, 2, 3, ("alpha", "1"), ("build", "5"))
        self.assertEqual(version.format(), "1.2.3-alpha.1+build.5")
        self.assertEqual(str(version), version.format())
        self.assertTrue(version.is_prerelease)
        self.assertFalse(Version(1, 2, 3).is_prerelease)
        self.assertEqual(str(VersionRange(raw_text=">=1.0.0")), ">=1.0.0")

    def test_register_package_orders_releases_descending(self) -> None:
        """POSTCONDITIONS: registered releases are exposed in descending precedence order."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = self._repository(scope)
            self._register(
                repository,
                PackageRelease(name="alpha", version=Version(1, 0, 0)),
                PackageRelease(name="alpha", version=Version(1, 3, 0)),
                PackageRelease(name="alpha", version=Version(1, 1, 0)),
                PackageRelease(name="alpha", version=Version(1, 4, 0, ("rc", "1"))),
            )
            releases = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in releases],
                [
                    Version(1, 4, 0, ("rc", "1")),
                    Version(1, 3, 0),
                    Version(1, 1, 0),
                    Version(1, 0, 0),
                ],
            )
            self.assertEqual(releases[0].version, Version(1, 4, 0, ("rc", "1")))

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITIONS: callers receive a shallow copy of the sorted release list."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = self._repository(scope)
            self._register(
                repository,
                PackageRelease(name="alpha", version=Version(1, 0, 0)),
                PackageRelease(name="alpha", version=Version(1, 1, 0)),
            )
            first = repository.get_releases("alpha")
            first.clear()
            second = repository.get_releases("alpha")
            self.assertEqual(len(second), 2)

    def test_has_package_and_all_packages(self) -> None:
        """POSTCONDITIONS: membership checks and the registered package name set are accurate."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = self._repository(scope)
            self._register(
                repository,
                PackageRelease(name="alpha", version=Version(1, 0, 0)),
                PackageRelease(name="beta", version=Version(2, 0, 0)),
            )
            self.assertTrue(repository.has_package("alpha"))
            self.assertTrue(repository.has_package("beta"))
            self.assertFalse(repository.has_package("ghost"))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """POSTCONDITIONS: highest precedence compatible release per package is selected."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            self._register(
                repository,
                PackageRelease(name="lib", version=Version(1, 0, 0)),
                PackageRelease(name="lib", version=Version(1, 2, 0)),
                PackageRelease(name="lib", version=Version(2, 0, 0)),
            )
            root = (PackageDependency(name="lib", range_constraint=engine.parse_range(">=1.0.0 <2.0.0")),)
            outcome = solver.resolve(root)
            self.assertIn("lib", outcome.selected_versions)
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 2, 0))
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertTrue(outcome.derivation_steps)

    def test_resolve_merges_root_constraints(self) -> None:
        """POSTCONDITIONS: accumulated root constraints intersect before selection."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            self._register(
                repository,
                PackageRelease(name="lib", version=Version(1, 0, 0)),
                PackageRelease(name="lib", version=Version(1, 2, 0)),
                PackageRelease(name="lib", version=Version(1, 5, 0)),
            )
            root = (
                PackageDependency(name="lib", range_constraint=engine.parse_range(">=1.0.0")),
                PackageDependency(name="lib", range_constraint=engine.parse_range("<1.5.0")),
            )
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 2, 0))

    def test_resolve_satisfies_transitive_dependencies(self) -> None:
        """POSTCONDITIONS: transitive dependencies constrain the selected assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            app_dependency = PackageDependency(
                name="lib",
                range_constraint=engine.parse_range(">=1.0.0 <2.0.0"),
            )
            self._register(
                repository,
                PackageRelease(name="lib", version=Version(1, 0, 0)),
                PackageRelease(name="lib", version=Version(1, 2, 0)),
                PackageRelease(name="lib", version=Version(2, 0, 0)),
                PackageRelease(
                    name="app",
                    version=Version(1, 0, 0),
                    dependencies=(app_dependency,),
                ),
            )
            root = (PackageDependency(name="app", range_constraint=engine.parse_range(">=1.0.0")),)
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["app"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 2, 0))
            self.assertTrue(outcome.derivation_steps)

    def test_resolve_diamond_dependency_assignment(self) -> None:
        """POSTCONDITIONS: shared transitive dependencies receive one compatible release."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            core_range = engine.parse_range(">=1.0.0")
            self._register(
                repository,
                PackageRelease(name="core", version=Version(1, 0, 0)),
                PackageRelease(name="core", version=Version(1, 4, 0)),
                PackageRelease(
                    name="left",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency(name="core", range_constraint=core_range),),
                ),
                PackageRelease(
                    name="right",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency(name="core", range_constraint=core_range),),
                ),
            )
            root = (
                PackageDependency(name="left", range_constraint=engine.parse_range(">=1.0.0")),
                PackageDependency(name="right", range_constraint=engine.parse_range(">=1.0.0")),
            )
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["left"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["right"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["core"], Version(1, 4, 0))
            self.assertTrue(outcome.derivation_steps)

    def test_resolve_prefers_release_over_prerelease(self) -> None:
        """POSTCONDITIONS: descending precedence selection favors final releases."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            self._register(
                repository,
                PackageRelease(name="lib", version=Version(1, 0, 0, ("rc", "1"))),
                PackageRelease(name="lib", version=Version(1, 0, 0)),
            )
            root = (PackageDependency(name="lib", range_constraint=engine.parse_range(">=1.0.0")),)
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["lib"], Version(1, 0, 0))

    def test_resolve_backtracks_when_candidate_conflicts_with_assigned_release(self) -> None:
        """POSTCONDITIONS: a candidate clashing with an assigned release is replaced by backtracking."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            self._register(
                repository,
                PackageRelease(name="core", version=Version(1, 5, 0)),
                PackageRelease(name="core", version=Version(2, 5, 0)),
                PackageRelease(
                    name="app",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency(name="core", range_constraint=engine.parse_range(">=1.0.0")),),
                ),
                PackageRelease(
                    name="app",
                    version=Version(2, 0, 0),
                    dependencies=(PackageDependency(name="core", range_constraint=engine.parse_range(">=2.0.0")),),
                ),
                PackageRelease(
                    name="tool",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency(name="core", range_constraint=engine.parse_range("<2.0.0")),),
                ),
            )
            root = (
                PackageDependency(name="app", range_constraint=engine.parse_range(">=1.0.0")),
                PackageDependency(name="tool", range_constraint=engine.parse_range(">=1.0.0")),
            )
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["app"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["tool"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["core"], Version(1, 5, 0))

    def test_resolve_undoes_failed_candidate_constraints(self) -> None:
        """POSTCONDITIONS: a failed candidate's introduced constraints and decision are undone."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = self._engine(scope)
            repository = self._repository(scope)
            solver = self._solver(scope)
            self._register(
                repository,
                PackageRelease(name="lib", version=Version(1, 2, 0)),
                PackageRelease(name="lib", version=Version(2, 0, 0)),
                PackageRelease(
                    name="app",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency(name="lib", range_constraint=engine.parse_range(">=1.0.0")),),
                ),
                PackageRelease(
                    name="app",
                    version=Version(2, 0, 0),
                    dependencies=(PackageDependency(name="lib", range_constraint=engine.parse_range(">=5.0.0")),),
                ),
            )
            root = (PackageDependency(name="app", range_constraint=engine.parse_range(">=1.0.0")),)
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["app"], Version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["lib"], Version(2, 0, 0))
            self.assertTrue(outcome.derivation_steps)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:34:27Z
# LAST_CHANGED: 2026-11-05T04:33:55Z
# CHANGE: Extended wildcard-comparator coverage to the bare any-version wildcard: test_satisfies_any_version_wildcard_comparators applies >=, <=, >, <, and != to each of '*', 'x', and 'X' across low/middle/high candidate versions, asserting the unbounded-band operators (>=, <=) accept every version while the empty-band operators (>, <, !=) reject every version.
# COVERAGE_AUDIT: 2026-11-05T04:34:27Z
# QA_AUDIT: 2026-11-05T04:34:12Z
# --- END AUTOFAB METADATA ---
