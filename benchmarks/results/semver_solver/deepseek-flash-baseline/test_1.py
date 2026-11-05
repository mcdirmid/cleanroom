"""Unit tests for semver_solver_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_4.parts.semver_solver.lib.semver_solver import (
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    SemVerError,
    Version,
    VersionRange,
)
from benchmark_4.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


def _version(
    major: int,
    minor: int = 0,
    patch: int = 0,
    prerelease: tuple[str, ...] = (),
    build: tuple[str, ...] = (),
) -> Version:
    return Version(major, minor, patch, prerelease, build)


def _dependency(name: str, text: str) -> PackageDependency:
    return PackageDependency(name, VersionRange(text))


def _release(
    name: str,
    version: Version,
    dependencies: tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    return PackageRelease(name, version, dependencies)


class SemverSolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """CUJ: Verify singleton registration and resolution within a phase."""
        with enter_phase(system, registry=self.registry) as scope:
            self.assertIsInstance(scope.get_singleton(VersionEngine), VersionEngine)
            self.assertIsInstance(
                scope.get_singleton(PackageRepository), PackageRepository
            )
            self.assertIsInstance(
                scope.get_singleton(DependencySolver), DependencySolver
            )

    def test_version_value_semantics(self) -> None:
        """Version.format/is_prerelease/__str__ and VersionRange.__str__ postconditions."""
        plain = _version(1, 2, 3)
        self.assertFalse(plain.is_prerelease)
        self.assertEqual(plain.format(), "1.2.3")
        self.assertEqual(str(plain), "1.2.3")

        prerelease = _version(1, 2, 3, ("alpha", "1"))
        self.assertTrue(prerelease.is_prerelease)
        self.assertEqual(prerelease.format(), "1.2.3-alpha.1")

        build = _version(1, 2, 3, (), ("build", "5"))
        self.assertFalse(build.is_prerelease)
        self.assertEqual(build.format(), "1.2.3+build.5")

        both = _version(1, 2, 3, ("rc", "1"), ("build", "5"))
        self.assertEqual(str(both), "1.2.3-rc.1+build.5")
        self.assertEqual(str(VersionRange("1.2.3")), "1.2.3")

    def test_error_message_data_types(self) -> None:
        """Exception data types expose message text and structured attributes."""
        base = SemVerError("boom")
        self.assertEqual(str(base), "boom")
        self.assertEqual(base.message, "boom")

        invalid_version = InvalidVersionError("bad version", raw_text="1.2")
        self.assertEqual(str(invalid_version), "bad version")
        self.assertEqual(invalid_version.raw_text, "1.2")

        invalid_range = InvalidRangeError("bad range", raw_range="1.2 - 2.3")
        self.assertEqual(str(invalid_range), "bad range")
        self.assertEqual(invalid_range.raw_range, "1.2 - 2.3")

        conflict = ResolutionConflictError("conflict", ("a", "b"), "explanation")
        self.assertEqual(str(conflict), "conflict")
        self.assertEqual(conflict.conflicting_packages, ("a", "b"))
        self.assertEqual(conflict.explanation, "explanation")

        missing = PackageNotFoundError("missing", package_name="a")
        self.assertEqual(str(missing), "missing")
        self.assertEqual(missing.package_name, "a")

    def test_parse_version(self) -> None:
        """VersionEngine.parse_version parses core, prerelease, and build components."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            simple = engine.parse_version("1.2.3")
            self.assertEqual(simple.major, 1)
            self.assertEqual(simple.minor, 2)
            self.assertEqual(simple.patch, 3)
            self.assertEqual(simple.prerelease, ())
            self.assertEqual(simple.build, ())

            rich = engine.parse_version("0.10.20-alpha.1+build.5")
            self.assertEqual(rich.major, 0)
            self.assertEqual(rich.minor, 10)
            self.assertEqual(rich.patch, 20)
            self.assertEqual(rich.prerelease, ("alpha", "1"))
            self.assertEqual(rich.build, ("build", "5"))
            self.assertEqual(str(rich), "0.10.20-alpha.1+build.5")

    def test_parse_range_trims_whitespace(self) -> None:
        """VersionEngine.parse_range trims surrounding and clause whitespace."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.parse_range("  >=1.0.0  ").raw_text, ">=1.0.0")
            union = engine.parse_range(" >=1.0.0 || < 2.0.0 ")
            self.assertEqual(union.raw_text, ">=1.0.0 || < 2.0.0")
            self.assertEqual(str(engine.parse_range(">= 1.0.0")), ">= 1.0.0")

    def test_parse_range_accepts_contracted_syntax(self) -> None:
        """VersionEngine.parse_range accepts comparators, ranges, and unions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            ranges = [
                "1.2.3",
                "=1.2.3",
                "==1.2.3",
                "!=1.2.3",
                "<1.2.3",
                "<=1.2.3",
                ">1.2.3",
                ">=1.2.3",
                "^1.2.3",
                "~1.2.3",
                "*",
                "x",
                "X",
                "1.x",
                "1.*",
                "1.2.x",
                "1.2.*",
                "1.2.3 - 2.0.0",
                ">=1.0.0 <2.0.0",
                "1.2.3 || >=2.0.0",
            ]
            for text in ranges:
                with self.subTest(range_text=text):
                    self.assertEqual(engine.parse_range(text).raw_text, text)

    def test_compare_precedence(self) -> None:
        """VersionEngine.compare_precedence realizes SemVer 2.0.0 ordering rules."""
        stable = _version(1, 0, 0)
        cases: list[tuple[Version, Version, int]] = [
            (_version(1, 0, 0), _version(2, 0, 0), -1),
            (_version(2, 0, 0), _version(1, 0, 0), 1),
            (_version(1, 0, 0), _version(1, 1, 0), -1),
            (_version(1, 0, 0), _version(1, 0, 1), -1),
            (stable, _version(1, 0, 0), 0),
            (stable, _version(1, 0, 0, ("alpha",)), 1),
            (_version(1, 0, 0, ("alpha",)), stable, -1),
            (_version(1, 0, 0, ("alpha",)), _version(1, 0, 0, ("beta",)), -1),
            (_version(1, 0, 0, ("beta",)), _version(1, 0, 0, ("alpha",)), 1),
            (
                _version(1, 0, 0, ("alpha", "1")),
                _version(1, 0, 0, ("alpha", "2")),
                -1,
            ),
            (
                _version(1, 0, 0, ("alpha", "2")),
                _version(1, 0, 0, ("alpha", "1")),
                1,
            ),
            (_version(1, 0, 0, ("1",)), _version(1, 0, 0, ("alpha",)), -1),
            (_version(1, 0, 0, ("alpha",)), _version(1, 0, 0, ("1",)), 1),
            (_version(1, 0, 0, ("alpha",)), _version(1, 0, 0, ("alpha", "1")), -1),
            (_version(1, 0, 0, ("alpha", "1")), _version(1, 0, 0, ("alpha",)), 1),
            (
                _version(1, 0, 0, ("alpha", "1")),
                _version(1, 0, 0, ("alpha", "1")),
                0,
            ),
            (_version(1, 0, 0, (), ("build", "1")), stable, 0),
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for left, right, expected in cases:
                with self.subTest(left=str(left), right=str(right)):
                    actual = engine.compare_precedence(left, right)
                    self.assertEqual((actual > 0) - (actual < 0), expected)

    def test_satisfies_comparators(self) -> None:
        """VersionEngine.satisfies evaluates basic comparator clauses."""
        cases: list[tuple[str, Version, bool]] = [
            (">=1.0.0", _version(1, 0, 0), True),
            (">=1.0.0", _version(2, 0, 0), True),
            (">=1.0.0", _version(0, 9, 0), False),
            (">1.0.0", _version(1, 0, 0), False),
            (">1.0.0", _version(1, 0, 1), True),
            ("<=1.0.0", _version(1, 0, 0), True),
            ("<=1.0.0", _version(1, 0, 1), False),
            ("<1.0.0", _version(1, 0, 0), False),
            ("<1.0.0", _version(0, 9, 9), True),
            ("=1.0.0", _version(1, 0, 0), True),
            ("=1.0.0", _version(1, 0, 1), False),
            ("==1.0.0", _version(1, 0, 0), True),
            ("!=1.0.0", _version(1, 0, 0), False),
            ("!=1.0.0", _version(1, 0, 1), True),
            (">=1.0.0 <2.0.0", _version(1, 5, 0), True),
            (">=1.0.0 <2.0.0", _version(2, 0, 0), False),
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text, version, expected in cases:
                with self.subTest(range_text=text, version=str(version)):
                    self.assertEqual(
                        engine.satisfies(version, VersionRange(text), False), expected
                    )

    def test_satisfies_prefix_hyphen_and_union_ranges(self) -> None:
        """VersionEngine.satisfies expands caret, tilde, hyphen, and union ranges."""
        cases: list[tuple[str, Version, bool]] = [
            ("^1.2.3", _version(1, 2, 3), True),
            ("^1.2.3", _version(1, 9, 9), True),
            ("^1.2.3", _version(1, 2, 2), False),
            ("^1.2.3", _version(2, 0, 0), False),
            ("^0.2.3", _version(0, 2, 9), True),
            ("^0.2.3", _version(0, 3, 0), False),
            ("^0.0.3", _version(0, 0, 3), True),
            ("^0.0.3", _version(0, 0, 4), False),
            ("~1.2.3", _version(1, 2, 9), True),
            ("~1.2.3", _version(1, 2, 2), False),
            ("~1.2.3", _version(1, 3, 0), False),
            ("1.2.3 - 2.0.0", _version(1, 2, 3), True),
            ("1.2.3 - 2.0.0", _version(2, 0, 0), True),
            ("1.2.3 - 2.0.0", _version(2, 0, 1), False),
            ("1.2.3 - 2.0.0", _version(1, 2, 2), False),
            ("1.2.3 || >=2.0.0", _version(1, 2, 3), True),
            ("1.2.3 || >=2.0.0", _version(2, 5, 0), True),
            ("1.2.3 || >=2.0.0", _version(1, 5, 0), False),
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text, version, expected in cases:
                with self.subTest(range_text=text, version=str(version)):
                    self.assertEqual(
                        engine.satisfies(version, VersionRange(text), False), expected
                    )

    def test_satisfies_wildcards(self) -> None:
        """VersionEngine.satisfies normalizes wildcards into comparator inequalities."""
        cases: list[tuple[str, Version, bool]] = [
            ("*", _version(5, 0, 0), True),
            ("x", _version(0, 1, 0), True),
            ("X", _version(9, 9, 9), True),
            ("1.x", _version(1, 5, 0), True),
            ("1.x", _version(2, 0, 0), False),
            ("1.*", _version(1, 0, 0), True),
            ("1.2.x", _version(1, 2, 9), True),
            ("1.2.x", _version(1, 3, 0), False),
            ("1.2.*", _version(1, 2, 0), True),
            ("!=1.x", _version(2, 0, 0), True),
            ("!=1.x", _version(1, 5, 0), False),
            (">1.x", _version(2, 0, 0), True),
            (">1.x", _version(1, 9, 0), False),
            (">=1.x", _version(1, 0, 0), True),
            (">=1.x", _version(0, 9, 0), False),
            ("<1.x", _version(0, 9, 0), True),
            ("<1.x", _version(1, 0, 0), False),
            ("<=1.x", _version(1, 9, 9), True),
            ("<=1.x", _version(2, 0, 0), False),
            ("^1.x", _version(1, 5, 0), True),
            ("^1.x", _version(2, 0, 0), False),
            ("~1.2.x", _version(1, 2, 9), True),
            ("~1.2.x", _version(1, 3, 0), False),
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text, version, expected in cases:
                with self.subTest(range_text=text, version=str(version)):
                    self.assertEqual(
                        engine.satisfies(version, VersionRange(text), False), expected
                    )

    def test_satisfies_prerelease_handling(self) -> None:
        """Prerelease gating and direct comparison postconditions."""
        cases: list[tuple[str, Version, bool, bool]] = [
            (">=1.0.0-alpha", _version(1, 0, 0, ("alpha",)), False, True),
            (">=0.9.0", _version(1, 0, 0, ("alpha",)), False, False),
            (">=1.0.0", _version(1, 0, 0, ("alpha",)), False, False),
            ("<1.0.0-alpha", _version(1, 0, 0, ("beta",)), False, False),
            (">=1.0.0-alpha", _version(1, 0, 0, ("alpha",)), True, True),
            (">=1.0.0", _version(1, 0, 0, ("alpha",)), True, False),
            (">=0.5.0", _version(1, 0, 0, ("alpha",)), True, True),
        ]
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text, version, include, expected in cases:
                with self.subTest(range_text=text, include_prerelease=include):
                    self.assertEqual(
                        engine.satisfies(version, VersionRange(text), include), expected
                    )

    def test_repository_tracks_releases_in_precedence_order(self) -> None:
        """PackageRepository registration, ordering, membership, and lookup postconditions."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("alpha"))
            self.assertEqual(repository.all_packages(), set())

            repository.register_package(_release("alpha", _version(1, 0, 0)))
            repository.register_package(_release("alpha", _version(1, 2, 0)))
            repository.register_package(_release("alpha", _version(0, 9, 0)))
            repository.register_package(_release("beta", _version(2, 0, 0)))

            self.assertTrue(repository.has_package("alpha"))
            self.assertFalse(repository.has_package("gamma"))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})

            releases = repository.get_releases("alpha")
            self.assertEqual([release.version for release in releases], [
                _version(1, 2, 0),
                _version(1, 0, 0),
                _version(0, 9, 0),
            ])
            releases.append(_release("alpha", _version(9, 0, 0)))
            self.assertEqual(len(repository.get_releases("alpha")), 3)

    def test_resolve_selects_highest_compatible_versions(self) -> None:
        """DependencySolver.resolve selects the highest precedence compatible release."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(_release("alpha", _version(1, 0, 0)))
            repository.register_package(_release("alpha", _version(2, 0, 0)))
            repository.register_package(_release("beta", _version(1, 0, 0)))
            repository.register_package(_release("beta", _version(1, 5, 0)))
            repository.register_package(
                _release("gamma", _version(3, 0, 0), (_dependency("beta", ">=1.0.0"),))
            )

            outcome = solver.resolve((_dependency("gamma", "*"),))
            self.assertEqual(
                outcome.selected_versions,
                {
                    "gamma": _version(3, 0, 0),
                    "beta": _version(1, 5, 0),
                },
            )
            self.assertTrue(outcome.derivation_steps)

    def test_resolve_backtracks_with_mrv_and_constraint_retention(self) -> None:
        """DependencySolver.resolve backtracks using MRV when constraints conflict."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release("alpha", _version(2, 0, 0), (_dependency("gamma", ">=3.0.0"),))
            )
            repository.register_package(_release("alpha", _version(1, 0, 0)))
            repository.register_package(
                _release("beta", _version(1, 0, 0), (_dependency("gamma", ">=1.0.0"),))
            )
            repository.register_package(_release("gamma", _version(2, 0, 0)))
            repository.register_package(_release("gamma", _version(1, 0, 0)))

            outcome = solver.resolve(
                (_dependency("alpha", "*"), _dependency("beta", "*"))
            )
            self.assertEqual(
                outcome.selected_versions,
                {
                    "alpha": _version(1, 0, 0),
                    "beta": _version(1, 0, 0),
                    "gamma": _version(2, 0, 0),
                },
            )

    def test_resolve_exhausts_candidates_with_unregistered_packages(self) -> None:
        """DependencySolver.resolve treats unregistered packages as empty candidate sets."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release("alpha", _version(2, 0, 0), (_dependency("beta", ">=1.0.0"),))
            )
            repository.register_package(_release("alpha", _version(1, 0, 0)))
            repository.register_package(
                _release("beta", _version(1, 1, 0), (_dependency("delta", ">=1.0.0"),))
            )
            repository.register_package(
                _release("beta", _version(1, 0, 0), (_dependency("delta", ">=1.0.0"),))
            )

            outcome = solver.resolve((_dependency("alpha", "*"),))
            self.assertEqual(
                outcome.selected_versions,
                {"alpha": _version(1, 0, 0)},
            )

    def test_resolve_detects_forward_conflicts(self) -> None:
        """DependencySolver.resolve backtracks when a dependency violates assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release("alpha", _version(2, 0, 0), (_dependency("gamma", ">=2.0.0"),))
            )
            repository.register_package(_release("alpha", _version(1, 0, 0)))
            repository.register_package(_release("gamma", _version(1, 0, 0)))

            outcome = solver.resolve(
                (_dependency("alpha", "*"), _dependency("gamma", "*"))
            )
            self.assertEqual(
                outcome.selected_versions,
                {
                    "alpha": _version(1, 0, 0),
                    "gamma": _version(1, 0, 0),
                },
            )


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T19:07:50Z
# LAST_CHANGED: 2026-11-03T19:07:50Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: d34d4f65bcbc
# COVERAGE_AUDIT: 2026-11-03T19:07:50Z
# QA_AUDIT: 2026-11-03T19:07:50Z
# --- END AUTOFAB METADATA ---
