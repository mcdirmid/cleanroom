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
    minor: int = 0,
    patch: int = 0,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> Version:
    return Version(major, minor, patch, prerelease, build)


def make_dependency(name: str, raw_range: str) -> PackageDependency:
    return PackageDependency(name, VersionRange(raw_range))


class SemverSolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_full(self) -> None:
        """CUJ: POSTCONDITION - valid SemVer 2.0.0 strings parse into Version records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("1.2.3")
            self.assertEqual(parsed, Version(1, 2, 3))
            self.assertEqual(parsed.prerelease, ())
            self.assertEqual(parsed.build, ())
            self.assertFalse(parsed.is_prerelease)
            self.assertEqual(parsed.format(), "1.2.3")
            self.assertEqual(str(parsed), "1.2.3")

    def test_parse_version_prerelease_and_build(self) -> None:
        """CUJ: POSTCONDITION - prerelease and build metadata become ordered tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(parsed.prerelease, ("alpha", "1"))
            self.assertEqual(parsed.build, ("build", "5"))
            self.assertTrue(parsed.is_prerelease)
            self.assertEqual(parsed.format(), "1.2.3-alpha.1+build.5")
            only_build = engine.parse_version("1.0.0+build")
            self.assertEqual(only_build.prerelease, ())
            self.assertEqual(only_build.build, ("build",))
            self.assertEqual(only_build.format(), "1.0.0+build")

    def test_parse_version_rejects_grammar_violations(self) -> None:
        """CUJ: PRECONDITION - leading zeroes and grammar violations raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in [
                "",
                "1.2",
                "1.2.3.4",
                "01.2.3",
                "1.02.3",
                "1.2.03",
                "1.2.3-01",
                "1.2.3-",
                "1.2.3+",
                "v1.2.3",
                "1.2.3 ",
            ]:
                with self.assertRaises(InvalidVersionError) as raised:
                    engine.parse_version(text)
                self.assertEqual(raised.exception.raw_text, text)

    def test_compare_precedence_numeric_components(self) -> None:
        """CUJ: POSTCONDITION - major, minor, and patch compare numerically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 4)), 0)
            self.assertGreater(engine.compare_precedence(make_version(1, 2, 4), make_version(1, 2, 3)), 0)
            self.assertLess(engine.compare_precedence(make_version(1, 2, 3), make_version(1, 3, 0)), 0)
            self.assertLess(engine.compare_precedence(make_version(1, 2, 3), make_version(2, 0, 0)), 0)
            self.assertEqual(engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 3)), 0)

    def test_compare_precedence_prerelease_ranking(self) -> None:
        """CUJ: POSTCONDITION - normal versions outrank prerelease versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            normal = make_version(1, 0, 0)
            prerelease = make_version(1, 0, 0, ("alpha",))
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)

    def test_compare_precedence_prerelease_segments(self) -> None:
        """CUJ: POSTCONDITION - prerelease segments rank numerically then lexically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(make_version(1, 0, 0, ("alpha",)), make_version(1, 0, 0, ("alpha", "1"))),
                0,
            )
            self.assertLess(
                engine.compare_precedence(make_version(1, 0, 0, ("alpha", "1")), make_version(1, 0, 0, ("alpha", "2"))),
                0,
            )
            self.assertLess(engine.compare_precedence(make_version(1, 0, 0, ("1",)), make_version(1, 0, 0, ("alpha",))), 0)
            self.assertGreater(
                engine.compare_precedence(make_version(1, 0, 0, ("alpha",)), make_version(1, 0, 0, ("1",))),
                0,
            )
            self.assertLess(engine.compare_precedence(make_version(1, 0, 0, ("alpha",)), make_version(1, 0, 0, ("beta",))), 0)
            self.assertGreater(
                engine.compare_precedence(make_version(1, 0, 0, ("beta",)), make_version(1, 0, 0, ("alpha",))),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(make_version(1, 0, 0, ("alpha", "1")), make_version(1, 0, 0, ("alpha", "1"))),
                0,
            )

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """CUJ: POSTCONDITION - build metadata never affects precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(make_version(1, 0, 0, build=("build.1",)), make_version(1, 0, 0, build=("build.2",))),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha",), ("build.1",)),
                    make_version(1, 0, 0, ("alpha",), ("build.2",)),
                ),
                0,
            )

    def test_parse_range_trims_and_normalizes(self) -> None:
        """CUJ: POSTCONDITION - trimmed range expression is stored in raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.parse_range("  >=1.0.0  ").raw_text, ">=1.0.0")
            self.assertEqual(str(engine.parse_range("  >=1.0.0  ")), ">=1.0.0")
            self.assertEqual(engine.parse_range(">= 1.0.0 < 2.0.0").raw_text, ">= 1.0.0 < 2.0.0")
            self.assertEqual(engine.parse_range(" >=1.0.0 || <0.5.0 ").raw_text, ">=1.0.0 || <0.5.0")

    def test_parse_range_accepts_supported_grammar(self) -> None:
        """CUJ: POSTCONDITION - comparators, prefixes, wildcards, hyphens, and unions parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in [
                "*",
                "x",
                "1.x",
                "1.2.x",
                "^1.x",
                "^1.2.3",
                "~1.2.x",
                "~1.2.3",
                ">=1.x",
                "!=1.x",
                ">1.*",
                "<1.x",
                "<=1.x",
                "==1.x",
                "1.x",
                ">=*",
                "==*",
                "<=*",
                "1.x - 2.x",
                "1.0.0 - 2.x",
                "1.0.0 - *",
                "1.2.3",
                "=1.2.3",
                "==1.2.3",
                "!=1.2.3",
                "<1.2.3",
                "<=1.2.3",
                ">1.2.3",
                ">=1.2.3",
                "1.0.0-alpha",
                "1.0.0+build",
            ]:
                self.assertEqual(engine.parse_range(text).raw_text, text)

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """CUJ: PRECONDITION - malformed ranges raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in [
                "",
                "   ",
                ">=1.0.0 ||",
                "|| >=1.0.0",
                ">=1.0.0 || || <2.0.0",
                ">=1.0.0,<2.0.0",
                "1",
                "1.2",
                ">1.2",
                "^0.0",
                "~1.2",
                "1.2 - 2.3",
                ">=1.0.0<2.0.0",
                "1.2.3.4",
                "1.x.2",
                "x.1",
                "1.x.x",
                "1.0.0-",
                "1.2.3+",
                "1.2.3+bad!",
                "1..0",
                ">=",
                "1.x-alpha",
                "1.x+build",
                "1.01.0",
            ]:
                with self.assertRaises(InvalidRangeError) as raised:
                    engine.parse_range(text)
                self.assertEqual(raised.exception.raw_range, text)

    def test_satisfies_basic_comparators(self) -> None:
        """CUJ: POSTCONDITION - basic comparators test bounds by precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), engine.parse_range(">=1.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), engine.parse_range(">=1.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), engine.parse_range(">=1.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), engine.parse_range("<2.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), engine.parse_range("<=2.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 1), engine.parse_range("<=2.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), engine.parse_range(">1.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(1, 0, 1), engine.parse_range(">1.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), engine.parse_range("==1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 4), engine.parse_range("==1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), engine.parse_range("=1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), engine.parse_range("!=1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 4), engine.parse_range("!=1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), engine.parse_range("1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 4), engine.parse_range("1.2.3"), False))

    def test_satisfies_wildcards(self) -> None:
        """CUJ: POSTCONDITION - wildcards normalize into paired inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), engine.parse_range(">=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 5, 0), engine.parse_range(">=1.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), engine.parse_range(">=1.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 9, 9), engine.parse_range(">1.*"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), engine.parse_range(">1.*"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), engine.parse_range("<=1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), engine.parse_range("<=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), engine.parse_range("1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), engine.parse_range("1.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), engine.parse_range("1.x"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), engine.parse_range("1.2.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), engine.parse_range("1.2.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 0), engine.parse_range("!=1.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), engine.parse_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), engine.parse_range("!=1.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 0, 1), engine.parse_range(">=*"), False))
            self.assertTrue(engine.satisfies(make_version(5, 0, 0), engine.parse_range(">=*"), False))
            self.assertTrue(engine.satisfies(make_version(3, 0, 0), engine.parse_range("==*"), False))
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), engine.parse_range("<=*"), False))
            self.assertFalse(engine.satisfies(make_version(100, 0, 0), engine.parse_range(">*"), False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), engine.parse_range("!=*"), False))
            self.assertTrue(engine.satisfies(make_version(3, 0, 0), engine.parse_range("*"), False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 0), engine.parse_range("<1.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), engine.parse_range("<1.x"), False))

    def test_satisfies_caret_ranges(self) -> None:
        """CUJ: POSTCONDITION - caret ranges expand on first non-zero boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), engine.parse_range("^1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 0), engine.parse_range("^1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), engine.parse_range("^1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), engine.parse_range("^1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(0, 2, 5), engine.parse_range("^0.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(0, 3, 0), engine.parse_range("^0.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(0, 0, 3), engine.parse_range("^0.0.3"), False))
            self.assertFalse(engine.satisfies(make_version(0, 0, 4), engine.parse_range("^0.0.3"), False))
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), engine.parse_range("^0.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(0, 0, 1), engine.parse_range("^0.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(0, 5, 0), engine.parse_range("^0.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), engine.parse_range("^0.x"), False))
            self.assertTrue(engine.satisfies(make_version(0, 0, 5), engine.parse_range("^0.0.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 1, 0), engine.parse_range("^0.0.x"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 0), engine.parse_range("^1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), engine.parse_range("^1.x"), False))
            self.assertTrue(engine.satisfies(make_version(4, 0, 0), engine.parse_range("^*"), False))

    def test_satisfies_tilde_ranges(self) -> None:
        """CUJ: POSTCONDITION - tilde ranges expand into lower and upper minor bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), engine.parse_range("~1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), engine.parse_range("~1.2.3"), False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), engine.parse_range("~1.2.3"), False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 0), engine.parse_range("~1.x"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), engine.parse_range("~1.x"), False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), engine.parse_range("~1.2.x"), False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), engine.parse_range("~1.2.x"), False))
            self.assertTrue(engine.satisfies(make_version(4, 0, 0), engine.parse_range("~*"), False))

    def test_satisfies_hyphen_ranges(self) -> None:
        """CUJ: POSTCONDITION - hyphen ranges become paired lower and upper inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), engine.parse_range("1.0.0 - 2.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 9, 9), engine.parse_range("1.0.0 - 2.x"), False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), engine.parse_range("1.0.0 - 2.x"), False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), engine.parse_range("1.0.0 - 2.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), engine.parse_range("1.0.0 - 2.0.0"), False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 1), engine.parse_range("1.0.0 - 2.0.0"), False))
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), engine.parse_range("1.x - 2.x"), False))
            self.assertTrue(engine.satisfies(make_version(2, 9, 9), engine.parse_range("1.x - 2.x"), False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), engine.parse_range("1.x - 2.x"), False))
            self.assertTrue(engine.satisfies(make_version(99, 0, 0), engine.parse_range("1.0.0 - *"), False))

    def test_satisfies_union_ranges(self) -> None:
        """CUJ: POSTCONDITION - union alternatives match when any clause is satisfied."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            union_range = engine.parse_range(">=2.0.0 || <1.0.0")
            self.assertTrue(engine.satisfies(make_version(2, 5, 0), union_range, False))
            self.assertTrue(engine.satisfies(make_version(0, 5, 0), union_range, False))
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), union_range, False))
            mixed = engine.parse_range("!=* || >=1.0.0")
            self.assertFalse(engine.satisfies(make_version(0, 5, 0), mixed, False))
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), mixed, False))

    def test_satisfies_prerelease_gating(self) -> None:
        """CUJ: POSTCONDITION - prereleases require explicit prerelease targets."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            candidate = make_version(1, 0, 0, ("alpha",))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range(">=0.9.0"), False))
            targeted = engine.parse_range(">=1.0.0-alpha")
            self.assertTrue(engine.satisfies(candidate, targeted, False))
            self.assertTrue(engine.satisfies(candidate, targeted, True))
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), targeted, False))
            self.assertFalse(engine.satisfies(candidate, engine.parse_range(">=1.0.0"), True))
            self.assertFalse(engine.satisfies(make_version(1, 0, 1, ("alpha",)), targeted, False))

    def test_repository_register_and_query(self) -> None:
        """CUJ: POSTCONDITION - releases are stored ordered by precedence descending."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("pkg", make_version(1, 0, 0)))
            repository.register_package(PackageRelease("pkg", make_version(1, 2, 0)))
            repository.register_package(PackageRelease("pkg", make_version(1, 1, 0)))
            releases = repository.get_releases("pkg")
            self.assertEqual(
                [release.version for release in releases],
                [make_version(1, 2, 0), make_version(1, 1, 0), make_version(1, 0, 0)],
            )
            releases.append(PackageRelease("pkg", make_version(9, 0, 0)))
            self.assertEqual(len(repository.get_releases("pkg")), 3)
            self.assertTrue(repository.has_package("pkg"))
            self.assertFalse(repository.has_package("missing"))
            self.assertEqual(repository.all_packages(), {"pkg"})

    def test_repository_missing_package_raises(self) -> None:
        """CUJ: PRECONDITION - unknown package names raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as raised:
                repository.get_releases("ghost")
            self.assertEqual(raised.exception.package_name, "ghost")

    def test_solver_resolve_simple(self) -> None:
        """CUJ: POSTCONDITION - highest precedence compatible release is selected."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("app", make_version(1, 0, 0)))
            repository.register_package(PackageRelease("app", make_version(1, 1, 0)))
            outcome = solver.resolve([make_dependency("app", ">=1.0.0")])
            self.assertEqual(dict(outcome.selected_versions), {"app": make_version(1, 1, 0)})
            self.assertEqual(len(outcome.derivation_steps), 1)
            self.assertIn("app", outcome.derivation_steps[0])

    def test_solver_resolve_transitive(self) -> None:
        """CUJ: POSTCONDITION - transitive dependencies are satisfied mutually."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("b", make_version(1, 0, 0)))
            repository.register_package(PackageRelease("b", make_version(2, 0, 0)))
            repository.register_package(
                PackageRelease("a", make_version(1, 0, 0), (make_dependency("b", ">=1.0.0"),))
            )
            outcome = solver.resolve([make_dependency("a", ">=1.0.0")])
            self.assertEqual(
                dict(outcome.selected_versions),
                {"a": make_version(1, 0, 0), "b": make_version(2, 0, 0)},
            )

    def test_solver_resolve_backtracks(self) -> None:
        """CUJ: POSTCONDITION - exhausted candidates backtrack to lower releases."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("b", make_version(1, 0, 0)))
            repository.register_package(
                PackageRelease("a", make_version(1, 0, 0), (make_dependency("b", ">=2.0.0"),))
            )
            repository.register_package(
                PackageRelease("a", make_version(0, 9, 0), (make_dependency("b", ">=1.0.0"),))
            )
            outcome = solver.resolve([make_dependency("a", ">=0.9.0")])
            self.assertEqual(
                dict(outcome.selected_versions),
                {"a": make_version(0, 9, 0), "b": make_version(1, 0, 0)},
            )
            self.assertEqual(len(outcome.derivation_steps), 2)

    def test_solver_resolve_backtracks_with_shared_constraints(self) -> None:
        """CUJ: POSTCONDITION - backtracking restores only the failed constraints."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("b", make_version(1, 0, 0)))
            repository.register_package(PackageRelease("b", make_version(2, 0, 0)))
            repository.register_package(
                PackageRelease("a", make_version(1, 0, 0), (make_dependency("b", ">=3.0.0"),))
            )
            repository.register_package(
                PackageRelease("a", make_version(0, 9, 0), (make_dependency("b", ">=1.0.0"),))
            )
            outcome = solver.resolve(
                [make_dependency("a", ">=0.9.0"), make_dependency("b", ">=1.0.0")]
            )
            self.assertEqual(
                dict(outcome.selected_versions),
                {"a": make_version(0, 9, 0), "b": make_version(2, 0, 0)},
            )

    def test_solver_resolve_reports_conflict(self) -> None:
        """CUJ: PRECONDITION - unsatisfiable dependencies raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease("a", make_version(1, 0, 0), (make_dependency("c", "==1.0.0"),))
            )
            repository.register_package(
                PackageRelease("b", make_version(1, 0, 0), (make_dependency("c", "==2.0.0"),))
            )
            repository.register_package(
                PackageRelease("b", make_version(2, 0, 0), (make_dependency("c", "==2.0.0"),))
            )
            repository.register_package(PackageRelease("c", make_version(1, 0, 0)))
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve(
                    [make_dependency("a", ">=1.0.0"), make_dependency("b", ">=1.0.0")]
                )
            self.assertIn("b", raised.exception.conflicting_packages)
            self.assertIn("c", raised.exception.conflicting_packages)
            self.assertTrue(raised.exception.explanation)

    def test_solver_resolve_missing_package_conflicts(self) -> None:
        """CUJ: PRECONDITION - unregistered packages surface as ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([make_dependency("ghost", ">=1.0.0")])
            self.assertIn("ghost", raised.exception.conflicting_packages)
            self.assertTrue(raised.exception.explanation)

    def test_solver_resolve_empty_dependencies(self) -> None:
        """CUJ: POSTCONDITION - an empty request resolves to an empty assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([])
            self.assertEqual(dict(outcome.selected_versions), {})
            self.assertEqual(outcome.derivation_steps, ())

    def test_solver_resolve_mrv_lexical_tie_break(self) -> None:
        """CUJ: POSTCONDITION - equal candidate counts break ties lexically."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(PackageRelease("zeta", make_version(1, 0, 0)))
            repository.register_package(PackageRelease("alpha", make_version(1, 0, 0)))
            outcome = solver.resolve(
                [make_dependency("zeta", ">=1.0.0"), make_dependency("alpha", ">=1.0.0")]
            )
            self.assertEqual(
                list(outcome.derivation_steps),
                ["Assign 'alpha' to 1.0.0", "Assign 'zeta' to 1.0.0"],
            )

    def test_solver_resolve_assigned_dependency_conflict(self) -> None:
        """CUJ: POSTCONDITION - assigned releases that violate a dependency trigger backtracking."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                PackageRelease("a", make_version(1, 0, 0), (make_dependency("c", "==1.0.0"),))
            )
            repository.register_package(
                PackageRelease("b", make_version(1, 0, 0), (make_dependency("c", ">=1.0.0"),))
            )
            repository.register_package(
                PackageRelease("b", make_version(2, 0, 0), (make_dependency("c", "==2.0.0"),))
            )
            repository.register_package(PackageRelease("c", make_version(1, 0, 0)))
            outcome = solver.resolve(
                [make_dependency("a", ">=1.0.0"), make_dependency("b", ">=1.0.0")]
            )
            self.assertEqual(
                dict(outcome.selected_versions),
                {"a": make_version(1, 0, 0), "b": make_version(1, 0, 0), "c": make_version(1, 0, 0)},
            )


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:11:18Z
# LAST_CHANGED: 2026-11-07T03:11:18Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 2af7136d4580
# COVERAGE_AUDIT: 2026-11-07T03:11:18Z
# QA_AUDIT: 2026-11-07T03:11:18Z
# --- END AUTOFAB METADATA ---
