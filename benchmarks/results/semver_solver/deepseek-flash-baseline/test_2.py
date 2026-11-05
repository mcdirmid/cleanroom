"""Unit tests for semver_solver_impl per its grounding specification."""

from __future__ import annotations

import os
import sys
import unittest
from typing import Tuple

_PARTS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PARTS_ROOT not in sys.path:
    sys.path.insert(0, _PARTS_ROOT)

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from semver_solver.lib.semver_solver import (
    PackageDependency,
    PackageRelease,
    Version,
)
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


def _make_release(
    engine: VersionEngine,
    name: str,
    version_text: str,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Builds a domain release record from primitive inputs."""
    return PackageRelease(
        name=name,
        version=engine.parse_version(version_text),
        dependencies=dependencies,
    )


def _dependency(engine: VersionEngine, name: str, range_text: str) -> PackageDependency:
    """Builds a domain dependency record from primitive inputs."""
    return PackageDependency(
        name=name,
        range_constraint=engine.parse_range(range_text),
    )


class SemverSolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_produces_canonical_records(self) -> None:
        """POSTCONDITION: valid SemVer 2.0.0 strings parse into Version records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(parsed.major, 1)
            self.assertEqual(parsed.minor, 2)
            self.assertEqual(parsed.patch, 3)
            self.assertEqual(parsed.prerelease, ("alpha", "1"))
            self.assertEqual(parsed.build, ("build", "5"))
            self.assertTrue(parsed.is_prerelease)
            self.assertEqual(parsed.format(), "1.2.3-alpha.1+build.5")
            self.assertEqual(str(parsed), "1.2.3-alpha.1+build.5")

    def test_parse_version_formats_optional_segments(self) -> None:
        """POSTCONDITION: format() renders prerelease and build metadata segments when present."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            plain = engine.parse_version("0.1.0")
            self.assertFalse(plain.is_prerelease)
            self.assertEqual(plain.format(), "0.1.0")
            self.assertEqual(str(plain), "0.1.0")
            prerelease_only = engine.parse_version("1.0.0-alpha")
            self.assertEqual(prerelease_only.format(), "1.0.0-alpha")
            build_only = engine.parse_version("1.0.0+build")
            self.assertEqual(build_only.format(), "1.0.0+build")

    def test_compare_precedence_numeric_components_and_build(self) -> None:
        """POSTCONDITION: numeric components compare in sequence and build metadata is ignored."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(
                engine.parse_version("1.0.0"), engine.parse_version("2.0.0")), 0)
            self.assertGreater(engine.compare_precedence(
                engine.parse_version("2.0.0"), engine.parse_version("1.0.0")), 0)
            self.assertLess(engine.compare_precedence(
                engine.parse_version("1.0.0"), engine.parse_version("1.1.0")), 0)
            self.assertLess(engine.compare_precedence(
                engine.parse_version("1.0.0"), engine.parse_version("1.0.1")), 0)
            self.assertEqual(engine.compare_precedence(
                engine.parse_version("1.0.0"), engine.parse_version("1.0.0")), 0)
            self.assertEqual(engine.compare_precedence(
                engine.parse_version("1.0.0+abc"), engine.parse_version("1.0.0+def")), 0)

    def test_compare_precedence_prerelease_ranking(self) -> None:
        """POSTCONDITION: prerelease segments rank numerically, lexicographically, and by length."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(engine.compare_precedence(
                engine.parse_version("1.0.0"), engine.parse_version("1.0.0-alpha")), 0)
            self.assertLess(engine.compare_precedence(
                engine.parse_version("1.0.0-alpha"), engine.parse_version("1.0.0")), 0)
            self.assertLess(engine.compare_precedence(
                engine.parse_version("1.0.0-alpha"), engine.parse_version("1.0.0-beta")), 0)
            self.assertGreater(engine.compare_precedence(
                engine.parse_version("1.0.0-beta"), engine.parse_version("1.0.0-alpha")), 0)
            self.assertLess(engine.compare_precedence(
                engine.parse_version("1.0.0-alpha.1"), engine.parse_version("1.0.0-alpha.2")), 0)
            self.assertLess(engine.compare_precedence(
                engine.parse_version("1.0.0-alpha.1"), engine.parse_version("1.0.0-alpha.beta")), 0)
            self.assertGreater(engine.compare_precedence(
                engine.parse_version("1.0.0-alpha.beta"), engine.parse_version("1.0.0-alpha.1")), 0)
            self.assertLess(engine.compare_precedence(
                engine.parse_version("1.0.0-alpha"), engine.parse_version("1.0.0-alpha.1")), 0)
            self.assertGreater(engine.compare_precedence(
                engine.parse_version("1.0.0-alpha.1"), engine.parse_version("1.0.0-alpha")), 0)
            self.assertEqual(engine.compare_precedence(
                engine.parse_version("1.0.0-alpha.1"), engine.parse_version("1.0.0-alpha.1")), 0)

    def test_compare_precedence_numeric_segments_equal_by_value(self) -> None:
        """POSTCONDITION: numeric prerelease segments compare by numeric value."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            padded = Version(major=1, minor=0, patch=0, prerelease=("alpha", "01"))
            plain = Version(major=1, minor=0, patch=0, prerelease=("alpha", "1"))
            self.assertEqual(engine.compare_precedence(plain, padded), 0)

    def test_parse_range_stores_trimmed_text(self) -> None:
        """POSTCONDITION: parse_range trims surrounding whitespace into raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("  >=1.0.0 <2.0.0  ")
            self.assertEqual(parsed.raw_text, ">=1.0.0 <2.0.0")
            self.assertEqual(str(parsed), ">=1.0.0 <2.0.0")

    def test_parse_range_supports_contracted_constructs(self) -> None:
        """POSTCONDITION: comparators, caret, tilde, wildcards, hyphens, and unions parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in (
                "==1.0.0",
                "=1.0.0",
                "!=1.0.0",
                "<1.0.0",
                "<=1.0.0",
                ">1.0.0",
                ">=1.0.0",
                "^1.2.3",
                "^0.2.3",
                "^0.0.3",
                "^0.0.0",
                "~1.2.3",
                "*",
                "1.x",
                "1.X",
                "1.*",
                "1.2.x",
                "1.2.*",
                "==1.x",
                "=1.x",
                ">=1.x",
                ">1.x",
                "<1.x",
                "<=1.x",
                "1.0.0 - 2.0.0",
                "1.0.0-alpha - 2.0.0",
                ">=1.0.0 <2.0.0",
                "1.0.0 || 2.0.0",
                "1.0.0 || >=2.0.0 <3.0.0",
                ">= 1.0.0",
                "^ 1.2.3",
                "~ 1.2.3",
                ">=1.0.0-alpha",
                "==1.0.0+build.1",
                "==1.0.0-alpha+build",
            ):
                self.assertEqual(engine.parse_range(text).raw_text, text)

    def test_satisfies_basic_comparators(self) -> None:
        """POSTCONDITION: comparator ranges evaluate against precedence ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.5.0")
            for range_text, expected in (
                ("==1.5.0", True),
                ("=1.5.0", True),
                ("!=1.5.0", False),
                ("!=1.4.0", True),
                ("<2.0.0", True),
                ("<1.5.0", False),
                ("<=1.5.0", True),
                ("<=1.4.0", False),
                (">1.0.0", True),
                (">1.5.0", False),
                (">=1.5.0", True),
                (">=1.6.0", False),
            ):
                self.assertIs(
                    engine.satisfies(version, engine.parse_range(range_text), False),
                    expected,
                )

    def test_satisfies_expanded_constructs(self) -> None:
        """POSTCONDITION: caret, tilde, wildcard, hyphen, and union ranges match candidates."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            cases = (
                ("1.9.0", "^1.2.3", True),
                ("2.0.0", "^1.2.3", False),
                ("1.2.9", "~1.2.3", True),
                ("1.3.0", "~1.2.3", False),
                ("1.5.0", "1.x", True),
                ("2.0.0", "1.x", False),
                ("2.0.0", "*", True),
                ("1.5.0", "1.0.0 - 2.0.0", True),
                ("2.5.0", "1.0.0 - 2.0.0", False),
                ("2.0.0", "1.0.0 || 2.0.0", True),
                ("3.0.0", "1.0.0 || 2.0.0", False),
                ("1.5.0", ">=1.x", True),
                ("2.0.0", ">1.x", True),
                ("0.5.0", "<1.x", True),
                ("1.5.0", "<=1.x", True),
            )
            for version_text, range_text, expected in cases:
                self.assertIs(
                    engine.satisfies(
                        engine.parse_version(version_text),
                        engine.parse_range(range_text),
                        False,
                    ),
                    expected,
                )

    def test_satisfies_prerelease_gating(self) -> None:
        """WHEN a prerelease candidate meets a gated range, matching depends on explicit targeting."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            candidate = engine.parse_version("1.5.0-alpha")
            self.assertFalse(
                engine.satisfies(candidate, engine.parse_range(">=1.0.0"), False))
            self.assertFalse(
                engine.satisfies(candidate, engine.parse_range("^1.0.0"), False))
            self.assertFalse(
                engine.satisfies(candidate, engine.parse_range(">=1.0.0-beta"), False))
            self.assertTrue(
                engine.satisfies(candidate, engine.parse_range(">=1.0.0-beta"), True))
            self.assertFalse(
                engine.satisfies(candidate, engine.parse_range("<2.0.0-beta"), False))
            self.assertFalse(
                engine.satisfies(candidate, engine.parse_range("<1.5.5-beta"), False))
            self.assertTrue(
                engine.satisfies(candidate, engine.parse_range(">=1.5.0-alpha"), False))
            self.assertFalse(
                engine.satisfies(candidate, engine.parse_range(">=1.5.0"), True))
            plain = engine.parse_version("1.5.0")
            self.assertTrue(
                engine.satisfies(plain, engine.parse_range(">=1.0.0"), False))

    def test_repository_registers_sorted_releases(self) -> None:
        """POSTCONDITION: releases are indexed and ordered by descending precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_make_release(engine, "alpha", "1.0.0"))
            repository.register_package(_make_release(engine, "alpha", "2.0.0"))
            repository.register_package(_make_release(engine, "alpha", "1.5.0"))
            releases = repository.get_releases("alpha")
            self.assertEqual(
                [release.version.format() for release in releases],
                ["2.0.0", "1.5.0", "1.0.0"],
            )
            releases.pop()
            self.assertEqual(len(repository.get_releases("alpha")), 3)

    def test_repository_membership_queries(self) -> None:
        """POSTCONDITION: membership and package-set queries reflect registered publications."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("missing"))
            repository.register_package(_make_release(engine, "alpha", "1.0.0"))
            self.assertTrue(repository.has_package("alpha"))
            self.assertEqual(repository.all_packages(), {"alpha"})

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """POSTCONDITION: resolution selects the highest precedence compatible release."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(_make_release(engine, "alpha", "1.0.0"))
            repository.register_package(_make_release(engine, "alpha", "2.0.0"))
            outcome = solver.resolve([_dependency(engine, "alpha", ">=1.0.0")])
            self.assertEqual(set(outcome.selected_versions), {"alpha"})
            self.assertEqual(outcome.selected_versions["alpha"].format(), "2.0.0")
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertEqual(len(outcome.derivation_steps), 1)

    def test_resolve_merges_transitive_dependencies(self) -> None:
        """POSTCONDITION: transitive dependencies merge into a compatible assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _make_release(
                    engine,
                    "alpha",
                    "1.0.0",
                    (_dependency(engine, "beta", "^1.0.0"),),
                )
            )
            repository.register_package(_make_release(engine, "beta", "1.0.0"))
            repository.register_package(_make_release(engine, "beta", "1.5.0"))
            outcome = solver.resolve([_dependency(engine, "alpha", ">=1.0.0")])
            self.assertEqual(set(outcome.selected_versions), {"alpha", "beta"})
            self.assertEqual(outcome.selected_versions["alpha"].format(), "1.0.0")
            self.assertEqual(outcome.selected_versions["beta"].format(), "1.5.0")
            self.assertEqual(len(outcome.derivation_steps), 2)

    def test_resolve_backtracks_away_from_missing_transitive_package(self) -> None:
        """WHEN a candidate references an unregistered package, the solver backtracks."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _make_release(
                    engine,
                    "alpha",
                    "2.0.0",
                    (_dependency(engine, "ghost", ">=1.0.0"),),
                )
            )
            repository.register_package(_make_release(engine, "alpha", "1.0.0"))
            outcome = solver.resolve([_dependency(engine, "alpha", ">=1.0.0")])
            self.assertEqual(set(outcome.selected_versions), {"alpha"})
            self.assertEqual(outcome.selected_versions["alpha"].format(), "1.0.0")

    def test_resolve_backtracks_to_lower_release_after_conflict(self) -> None:
        """WHEN a higher candidate conflicts with a retained constraint, a lower candidate is tried."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _make_release(
                    engine,
                    "alpha",
                    "2.0.0",
                    (_dependency(engine, "beta", ">=2.0.0"),),
                )
            )
            repository.register_package(_make_release(engine, "alpha", "1.0.0"))
            repository.register_package(_make_release(engine, "beta", "1.0.0"))
            repository.register_package(_make_release(engine, "beta", "1.5.0"))
            outcome = solver.resolve([
                _dependency(engine, "alpha", ">=1.0.0"),
                _dependency(engine, "beta", ">=1.0.0"),
            ])
            self.assertEqual(set(outcome.selected_versions), {"alpha", "beta"})
            self.assertEqual(outcome.selected_versions["alpha"].format(), "1.0.0")
            self.assertEqual(outcome.selected_versions["beta"].format(), "1.5.0")

    def test_resolve_accepts_satisfied_assigned_dependency(self) -> None:
        """POSTCONDITION: established assignments satisfying a later requirement are retained."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _make_release(
                    engine,
                    "alpha",
                    "1.0.0",
                    (
                        _dependency(engine, "beta", "==1.0.0"),
                        _dependency(engine, "gamma", "==1.0.0"),
                    ),
                )
            )
            repository.register_package(_make_release(engine, "beta", "1.0.0"))
            repository.register_package(
                _make_release(
                    engine,
                    "gamma",
                    "1.0.0",
                    (_dependency(engine, "beta", ">=1.0.0"),),
                )
            )
            outcome = solver.resolve([_dependency(engine, "alpha", ">=1.0.0")])
            self.assertEqual(
                set(outcome.selected_versions), {"alpha", "beta", "gamma"})
            self.assertEqual(outcome.selected_versions["beta"].format(), "1.0.0")
            self.assertEqual(outcome.selected_versions["gamma"].format(), "1.0.0")

    def test_resolve_backtracks_across_assigned_package_conflict(self) -> None:
        """WHEN a candidate conflicts with an established assignment, the search backtracks."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            conflicting = (_dependency(engine, "beta", "<2.0.0"),)
            repository.register_package(_make_release(engine, "beta", "1.0.0"))
            repository.register_package(_make_release(engine, "beta", "2.0.0"))
            repository.register_package(
                _make_release(engine, "zeta", "1.0.0", conflicting))
            repository.register_package(
                _make_release(engine, "zeta", "2.0.0", conflicting))
            outcome = solver.resolve([
                _dependency(engine, "beta", ">=1.0.0"),
                _dependency(engine, "zeta", ">=1.0.0"),
            ])
            self.assertEqual(set(outcome.selected_versions), {"beta", "zeta"})
            self.assertEqual(outcome.selected_versions["beta"].format(), "1.0.0")
            self.assertEqual(outcome.selected_versions["zeta"].format(), "2.0.0")


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:09:51Z
# LAST_CHANGED: 2026-11-05T04:09:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: fa288410def3
# COVERAGE_AUDIT: 2026-11-05T04:09:51Z
# QA_AUDIT: 2026-11-05T04:09:51Z
# --- END AUTOFAB METADATA ---
