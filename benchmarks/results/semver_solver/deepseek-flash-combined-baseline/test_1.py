"""Unit tests for semver_solver_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from typing import List, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver.lib.semver_solver import (
    PackageDependency,
    PackageRelease,
    Version,
    VersionRange,
)
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


def _version(
    major: int,
    minor: int = 0,
    patch: int = 0,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> Version:
    """Builds a domain Version value for scenario setup."""
    return Version(major, minor, patch, prerelease, build)


def _release(
    name: str,
    version: Version,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Builds a domain PackageRelease value for repository setup."""
    return PackageRelease(name, version, dependencies)


def _dependency(name: str, range_text: str) -> PackageDependency:
    """Builds a domain PackageDependency value for scenario setup."""
    return PackageDependency(name, VersionRange(range_text))


class SemverSolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_accepts_valid_semver(self) -> None:
        # POST: valid SemVer strings parse into immutable Version records.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.parse_version("1.2.3"), _version(1, 2, 3))
            self.assertEqual(
                engine.parse_version("0.0.0"),
                _version(0, 0, 0),
            )
            self.assertEqual(
                engine.parse_version("1.0.0-alpha.1+build.5"),
                _version(1, 0, 0, ("alpha", "1"), ("build", "5")),
            )
            self.assertEqual(
                engine.parse_version("2.1.0-rc.1"),
                _version(2, 1, 0, ("rc", "1")),
            )

    def test_compare_precedence_orders_versions(self) -> None:
        # POST: numeric core, pre-release ordering, and numeric/string rules.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            cases = (
                ("1.0.0", "2.0.0", -1),
                ("2.0.0", "1.0.0", 1),
                ("1.1.0", "1.2.0", -1),
                ("1.2.0", "1.1.0", 1),
                ("1.0.1", "1.0.2", -1),
                ("1.0.2", "1.0.1", 1),
                ("1.0.0", "1.0.0", 0),
                ("1.0.0-alpha", "1.0.0", -1),
                ("1.0.0", "1.0.0-alpha", 1),
                ("1.0.0-alpha", "1.0.0-beta", -1),
                ("1.0.0-beta", "1.0.0-alpha", 1),
                ("1.0.0-alpha.1", "1.0.0-alpha.2", -1),
                ("1.0.0-alpha.2", "1.0.0-alpha.1", 1),
                ("1.0.0-alpha", "1.0.0-alpha.1", -1),
                ("1.0.0-alpha.1", "1.0.0-alpha", 1),
                ("1.0.0-1", "1.0.0-alpha", -1),
                ("1.0.0-alpha", "1.0.0-1", 1),
                ("1.0.0-2", "1.0.0-10", -1),
                ("1.0.0-10", "1.0.0-2", 1),
                ("1.0.0-alpha", "1.0.0-alpha", 0),
            )
            for left_text, right_text, expected in cases:
                with self.subTest(left=left_text, right=right_text):
                    left = engine.parse_version(left_text)
                    right = engine.parse_version(right_text)
                    self.assertEqual(
                        engine.compare_precedence(left, right), expected
                    )

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        # POST: build metadata is excluded from precedence comparison.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            left = _version(1, 2, 3, (), ("build", "7"))
            right = _version(1, 2, 3)
            self.assertEqual(engine.compare_precedence(left, right), 0)
            self.assertEqual(engine.compare_precedence(right, left), 0)

    def test_parse_range_accepts_supported_grammar(self) -> None:
        # POST: comparators, caret, tilde, wildcards, hyphens, and unions.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            expressions = (
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
                "~1.2.3",
                "*",
                "x",
                "X",
                "1.x",
                "1.*",
                "1.2.x",
                "1.2.*",
                "1.2.3 - 2.3.4",
                "1.2.3 - 2.3.x",
                "1.2.3 - 2.x",
                "1.x - 2.3.4",
                "1.2.3 - *",
                ">=1.0.0 || <0.5.0",
                ">= 1.0.0 < 2.0.0",
                "!=1.x",
                ">=1.x",
                ">1.x",
                "<1.x",
                "<=1.x",
                "!=*",
                ">=*",
            )
            for expression in expressions:
                with self.subTest(expression=expression):
                    self.assertEqual(
                        engine.parse_range(expression).raw_text, expression
                    )

    def test_parse_range_trims_surrounding_whitespace(self) -> None:
        # POST: surrounding whitespace is trimmed into raw_text.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range("  >= 1.0.0   < 2.0.0  ")
            self.assertEqual(parsed.raw_text, ">= 1.0.0   < 2.0.0")
            self.assertEqual(str(parsed), ">= 1.0.0   < 2.0.0")

    def test_satisfies_relational_operators(self) -> None:
        # POST: every primitive comparator operator matches by precedence.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            cases = (
                ("==1.0.0", "1.0.0", True),
                ("==1.0.0", "1.0.1", False),
                ("=1.0.0", "1.0.0", True),
                ("!=1.0.0", "1.0.1", True),
                ("!=1.0.0", "1.0.0", False),
                ("<1.0.0", "0.9.0", True),
                ("<1.0.0", "1.0.0", False),
                ("<=1.0.0", "1.0.0", True),
                ("<=1.0.0", "1.0.1", False),
                (">1.0.0", "1.0.1", True),
                (">1.0.0", "1.0.0", False),
                (">=1.0.0", "1.0.0", True),
                (">=1.0.0", "0.9.0", False),
            )
            for range_text, version_text, expected in cases:
                with self.subTest(range_text=range_text, version=version_text):
                    result = engine.satisfies(
                        engine.parse_version(version_text),
                        engine.parse_range(range_text),
                        False,
                    )
                    self.assertEqual(result, expected)

    def test_satisfies_caret_and_tilde_ranges(self) -> None:
        # POST: caret and tilde prefixes expand into boundary comparators.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            cases = (
                ("^1.2.3", "1.9.0", True),
                ("^1.2.3", "2.0.0", False),
                ("^1.2.3", "1.2.2", False),
                ("^0.2.3", "0.2.9", True),
                ("^0.2.3", "0.3.0", False),
                ("^0.0.3", "0.0.3", True),
                ("^0.0.3", "0.0.4", False),
                ("~1.2.3", "1.2.9", True),
                ("~1.2.3", "1.3.0", False),
                ("~1.2.3", "1.2.2", False),
            )
            for range_text, version_text, expected in cases:
                with self.subTest(range_text=range_text, version=version_text):
                    result = engine.satisfies(
                        engine.parse_version(version_text),
                        engine.parse_range(range_text),
                        False,
                    )
                    self.assertEqual(result, expected)

    def test_satisfies_wildcards_and_hyphen_ranges(self) -> None:
        # POST: wildcards and hyphen ranges normalize into inequalities.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            cases = (
                ("*", "5.0.0", True),
                ("x", "5.0.0", True),
                ("1.x", "1.5.0", True),
                ("1.x", "2.0.0", False),
                ("1.*", "1.5.0", True),
                ("1.2.x", "1.2.9", True),
                ("1.2.x", "1.3.0", False),
                ("1.2.*", "1.2.9", True),
                ("!=1.x", "2.0.0", True),
                ("!=1.x", "1.5.0", False),
                (">=1.x", "1.0.0", True),
                (">=1.x", "0.9.0", False),
                (">1.x", "2.0.0", True),
                (">1.x", "1.5.0", False),
                ("<1.x", "0.5.0", True),
                ("<1.x", "1.0.0", False),
                ("<=1.x", "1.9.9", True),
                ("<=1.x", "2.0.0", False),
                ("!=*", "1.0.0", False),
                (">*", "1.0.0", False),
                ("<*", "1.0.0", False),
                (">=*", "1.0.0", True),
                ("<=*", "1.0.0", True),
                ("1.2.3 - 2.3.4", "1.2.3", True),
                ("1.2.3 - 2.3.4", "2.3.4", True),
                ("1.2.3 - 2.3.4", "2.3.5", False),
                ("1.2.3 - 2.3.4", "1.2.2", False),
                ("1.2.3 - 2.3.x", "2.3.9", True),
                ("1.2.3 - 2.3.x", "2.4.0", False),
                ("1.2.3 - 2.x", "2.9.9", True),
                ("1.2.3 - 2.x", "3.0.0", False),
                ("1.x - 2.3.4", "1.0.0", True),
                ("1.x - 2.3.4", "0.9.0", False),
                ("1.2.3 - *", "5.0.0", True),
            )
            for range_text, version_text, expected in cases:
                with self.subTest(range_text=range_text, version=version_text):
                    result = engine.satisfies(
                        engine.parse_version(version_text),
                        engine.parse_range(range_text),
                        False,
                    )
                    self.assertEqual(result, expected)

    def test_satisfies_union_of_clauses(self) -> None:
        # POST: a version satisfies the range if any union clause matches.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_range(">=1.0.0 || <0.5.0")
            self.assertTrue(engine.satisfies(_version(1, 5, 0), parsed, False))
            self.assertTrue(engine.satisfies(_version(0, 4, 0), parsed, False))
            self.assertFalse(engine.satisfies(_version(0, 7, 0), parsed, False))

    def test_satisfies_prerelease_filtering(self) -> None:
        # WHEN include_prerelease is False, only explicitly targeted prereleases match.
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            plain = engine.parse_range(">=1.0.0")
            targeted = engine.parse_range(">=1.0.0-alpha <2.0.0")
            self.assertFalse(
                engine.satisfies(_version(1, 0, 0, ("alpha",)), plain, False)
            )
            self.assertFalse(
                engine.satisfies(_version(1, 0, 0, ("alpha",)), plain, True)
            )
            self.assertTrue(
                engine.satisfies(_version(1, 0, 0, ("beta",)), targeted, False)
            )
            self.assertFalse(
                engine.satisfies(_version(1, 2, 0, ("beta",)), targeted, False)
            )
            self.assertTrue(
                engine.satisfies(_version(1, 2, 0, ("beta",)), targeted, True)
            )
            self.assertTrue(engine.satisfies(_version(1, 0, 0, ()), targeted, False))
            self.assertFalse(
                engine.satisfies(_version(0, 9, 0, ("alpha",)), targeted, False)
            )

    def test_repository_registers_and_orders_releases(self) -> None:
        # POST: releases are ordered by version precedence descending.
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(_release("alpha", _version(1, 0, 0)))
            repository.register_package(_release("alpha", _version(1, 2, 0)))
            repository.register_package(_release("alpha", _version(0, 9, 0)))
            releases = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in releases],
                [_version(1, 2, 0), _version(1, 0, 0), _version(0, 9, 0)],
            )
            releases.append(_release("alpha", _version(9, 0, 0)))
            self.assertEqual(len(repository.get_releases("alpha")), 3)

    def test_repository_lookup_and_membership(self) -> None:
        # POST: has_package and all_packages reflect registered names.
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("alpha"))
            self.assertEqual(repository.all_packages(), set())
            repository.register_package(_release("alpha", _version(1, 0, 0)))
            repository.register_package(_release("beta", _version(2, 0, 0)))
            self.assertTrue(repository.has_package("alpha"))
            self.assertTrue(repository.has_package("beta"))
            self.assertFalse(repository.has_package("gamma"))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})

    def test_resolve_selects_highest_compatible_versions(self) -> None:
        # POST: highest precedence compatible release per package is selected.
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(_release("alpha", _version(1, 0, 0)))
            repository.register_package(_release("alpha", _version(1, 2, 0)))
            repository.register_package(_release("alpha", _version(2, 0, 0)))
            outcome = solver.resolve(
                [PackageDependency("alpha", VersionRange("^1.0.0"))]
            )
            self.assertEqual(outcome.selected_versions["alpha"], _version(1, 2, 0))
            self.assertEqual(len(outcome.derivation_steps), 1)

    def test_resolve_transitive_dependencies(self) -> None:
        # POST: transitive dependencies merge into accumulated constraints.
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release(
                    "alpha",
                    _version(1, 1, 0),
                    (_dependency("beta", "^2.0.0"),),
                )
            )
            repository.register_package(
                _release(
                    "alpha",
                    _version(1, 0, 0),
                    (_dependency("beta", "^2.0.0"),),
                )
            )
            repository.register_package(_release("beta", _version(2, 0, 0)))
            repository.register_package(_release("beta", _version(2, 1, 0)))
            outcome = solver.resolve(
                [PackageDependency("alpha", VersionRange("^1.0.0"))]
            )
            self.assertEqual(outcome.selected_versions["alpha"], _version(1, 1, 0))
            self.assertEqual(outcome.selected_versions["beta"], _version(2, 1, 0))

    def test_resolve_empty_roots_succeeds(self) -> None:
        # POST: no root dependencies resolves to an empty assignment.
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([])
            self.assertEqual(outcome.selected_versions, {})
            self.assertEqual(outcome.derivation_steps, ())

    def test_resolve_backtracks_candidate_dependencies(self) -> None:
        # POST: conflicting assignments trigger backtracking to lower candidates.
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release(
                    "alpha",
                    _version(2, 0, 0),
                    (_dependency("beta", "==2.0.0"),),
                )
            )
            repository.register_package(
                _release(
                    "alpha",
                    _version(1, 0, 0),
                    (_dependency("beta", "==1.0.0"),),
                )
            )
            repository.register_package(_release("beta", _version(1, 0, 0)))
            outcome = solver.resolve(
                [
                    PackageDependency("alpha", VersionRange("*")),
                    PackageDependency("beta", VersionRange("*")),
                ]
            )
            self.assertEqual(outcome.selected_versions["alpha"], _version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["beta"], _version(1, 0, 0))

    def test_resolve_backtracks_forwarded_constraints(self) -> None:
        # POST: constraints forwarded by a failed candidate are rolled back.
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)
            repository.register_package(
                _release(
                    "alpha",
                    _version(2, 0, 0),
                    (_dependency("beta", "==2.0.0"),),
                )
            )
            repository.register_package(_release("alpha", _version(1, 0, 0)))
            repository.register_package(
                _release(
                    "beta",
                    _version(2, 0, 0),
                    (_dependency("gamma", ">=9.0.0"),),
                )
            )
            outcome = solver.resolve([PackageDependency("alpha", VersionRange("*"))])
            self.assertEqual(outcome.selected_versions["alpha"], _version(1, 0, 0))
            self.assertNotIn("beta", outcome.selected_versions)
            self.assertNotIn("gamma", outcome.selected_versions)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:10:45Z
# LAST_CHANGED: 2026-11-05T04:10:45Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 65de6b3e4e86
# COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:10:45Z
# QA_AUDIT: 2026-11-05T04:10:45Z
# --- END AUTOFAB METADATA ---
