# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, List, Set
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmarks.runs.semver_solver_deepseek_flash_1.parts.semver_solver.pretense.semver_solver_pretense import (
    FakeSemverSolver,
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fake,
)
from benchmarks.runs.semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver as DependencySolverInterface,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository as PackageRepositoryInterface,
    ResolutionConflictError,
    ResolutionOutcome,
    SemVerError,
    Version,
    VersionEngine as VersionEngineInterface,
    VersionRange,
)
from benchmarks.runs.semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# The pseudo-state machine inherits every interface transition (domain guards and
# model state mutations included) and overrides only the inner transitions so the
# concrete SUT computes the return values that the inherited assertions verify.

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    def inner_parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngineInterface = sut(VersionEngine)
        ret: Version = call_target(target.parse_version(text))
        return ret

    def inner_compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        target: VersionEngineInterface = sut(VersionEngine)
        ret: int = call_target(target.compare_precedence(v1, v2))
        return ret

    def inner_parse_range(
        self,
        text: str,
    ) -> VersionRange:
        target: VersionEngineInterface = sut(VersionEngine)
        ret: VersionRange = call_target(target.parse_range(text))
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngineInterface = sut(VersionEngine)
        ret: bool = call_target(target.satisfies(version, range_constraint, include_prerelease))
        return ret

    def inner_register_package(
        self,
        release: PackageRelease,
    ) -> None:
        target: PackageRepositoryInterface = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        repository: PackageRepositoryInterface = sut(PackageRepository)
        assert repository.has_package(release.name)
        return ret

    def inner_get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        target: PackageRepositoryInterface = sut(PackageRepository)
        ret: List[PackageRelease] = call_target(target.get_releases(name))
        return ret

    def inner_has_package(
        self,
        name: str,
    ) -> bool:
        target: PackageRepositoryInterface = sut(PackageRepository)
        ret: bool = call_target(target.has_package(name))
        return ret

    def inner_all_packages(
        self,
    ) -> Set[str]:
        target: PackageRepositoryInterface = sut(PackageRepository)
        ret: Set[str] = call_target(target.all_packages())
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolverInterface = sut(DependencySolver)
        ret: ResolutionOutcome = call_target(target.resolve(root_dependencies))
        repository: PackageRepositoryInterface = sut(PackageRepository)
        assert all(repository.has_package(dependency.name) for dependency in root_dependencies)
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )
        self.checked_versionengine: Any = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository: Any = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver: Any = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_parses_prerelease_and_build_metadata(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prerelease, ("alpha", "1"))
        self.assertEqual(version.build, ("build", "5"))
        self.assertTrue(version.is_prerelease)
        self.assertEqual(version.format(), "1.2.3-alpha.1+build.5")

    def test_parse_version_parses_plain_release(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3")
        self.assertEqual(version, Version(1, 2, 3))
        self.assertFalse(version.is_prerelease)
        self.assertEqual(str(version), "1.2.3")

    def test_parse_version_rejects_leading_zero_identifiers(self) -> None:
        self.checked_versionengine.violating(InvalidVersionError).parse_version("01.2.3")

    def test_compare_precedence_orders_numeric_components(self) -> None:
        smaller = self.checked_versionengine.parse_version("1.2.3")
        larger = self.checked_versionengine.parse_version("2.0.0")
        self.assertLess(self.checked_versionengine.compare_precedence(smaller, larger), 0)
        self.assertGreater(self.checked_versionengine.compare_precedence(larger, smaller), 0)
        self.assertEqual(self.checked_versionengine.compare_precedence(smaller, smaller), 0)

    def test_compare_precedence_ranks_prerelease_below_release(self) -> None:
        prerelease = self.checked_versionengine.parse_version("2.0.0-alpha.1")
        release = self.checked_versionengine.parse_version("2.0.0")
        self.assertLess(self.checked_versionengine.compare_precedence(prerelease, release), 0)
        self.assertGreater(self.checked_versionengine.compare_precedence(release, prerelease), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        plain = self.checked_versionengine.parse_version("1.2.3-alpha.1")
        built = self.checked_versionengine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual(self.checked_versionengine.compare_precedence(built, plain), 0)

    def test_compare_precedence_orders_prerelease_segments(self) -> None:
        numeric = self.checked_versionengine.parse_version("1.2.3-1")
        textual = self.checked_versionengine.parse_version("1.2.3-alpha")
        longer = self.checked_versionengine.parse_version("1.2.3-alpha.2")
        self.assertLess(self.checked_versionengine.compare_precedence(numeric, textual), 0)
        self.assertGreater(self.checked_versionengine.compare_precedence(longer, textual), 0)

    def test_parse_range_trims_whitespace_and_preserves_expression(self) -> None:
        parsed = self.checked_versionengine.parse_range("  >=1.x || <1.2.3  ")
        self.assertEqual(parsed.raw_text, ">=1.x || <1.2.3")
        self.assertEqual(str(parsed), ">=1.x || <1.2.3")

    def test_parse_range_accepts_hyphen_range(self) -> None:
        parsed = self.checked_versionengine.parse_range("1.0.0 - 2.x")
        self.assertEqual(parsed.raw_text, "1.0.0 - 2.x")

    def test_parse_range_rejects_bare_partial_versions(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range("1.2")

    def test_satisfies_matches_wildcard_range(self) -> None:
        constraint = self.checked_versionengine.parse_range("^1.x")
        inside = self.checked_versionengine.parse_version("1.2.3")
        outside = self.checked_versionengine.parse_version("2.0.0")
        self.assertTrue(self.checked_versionengine.satisfies(inside, constraint, False))
        self.assertFalse(self.checked_versionengine.satisfies(outside, constraint, False))

    def test_satisfies_filters_prerelease_candidates(self) -> None:
        constraint = self.checked_versionengine.parse_range(">=1.0.0")
        candidate = self.checked_versionengine.parse_version("2.0.0-alpha.1")
        self.assertFalse(self.checked_versionengine.satisfies(candidate, constraint, False))
        self.assertTrue(self.checked_versionengine.satisfies(candidate, constraint, True))

    def test_satisfies_matches_wildcard_comparator(self) -> None:
        constraint = self.checked_versionengine.parse_range(">=1.x")
        inside = self.checked_versionengine.parse_version("2.0.0")
        candidate = self.checked_versionengine.parse_version("1.2.3-alpha.1")
        self.assertTrue(self.checked_versionengine.satisfies(inside, constraint, False))
        self.assertTrue(self.checked_versionengine.satisfies(candidate, constraint, True))

    def test_satisfies_expands_tilde_and_hyphen_ranges(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3")
        tilde = self.checked_versionengine.parse_range("~1.2.x")
        hyphen = self.checked_versionengine.parse_range("1.0.0 - 2.x")
        union = self.checked_versionengine.parse_range(">=1.x || <1.2.3")
        outside_tilde = self.checked_versionengine.parse_version("2.0.0")
        self.assertTrue(self.checked_versionengine.satisfies(version, tilde, False))
        self.assertTrue(self.checked_versionengine.satisfies(version, hyphen, False))
        self.assertTrue(self.checked_versionengine.satisfies(outside_tilde, union, False))

    def test_satisfies_matches_prerelease_targeting_range(self) -> None:
        constraint = self.checked_versionengine.parse_range(">=1.2.3-alpha.1")
        candidate = self.checked_versionengine.parse_version("1.2.3-alpha.1")
        self.assertTrue(self.checked_versionengine.satisfies(candidate, constraint, False))

    def test_repository_tracks_registered_releases(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.assertTrue(self.checked_packagerepository.has_package("alpha"))
        self.assertFalse(self.checked_packagerepository.has_package("gamma"))
        self.assertEqual(self.checked_packagerepository.all_packages(), {"alpha"})
        releases = self.checked_packagerepository.get_releases("alpha")
        self.assertEqual([release.version for release in releases], [Version(2, 0, 0), Version(1, 0, 0)])

    def test_repository_reports_missing_package(self) -> None:
        self.checked_packagerepository.violating(PackageNotFoundError).get_releases("gamma")

    def test_resolve_selects_highest_compatible_release(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease("beta", Version(2, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),))
        )
        outcome = self.checked_dependencysolver.resolve((PackageDependency("beta", VersionRange(">=1.0.0")),))
        self.assertEqual(outcome.selected_versions["beta"], Version(2, 0, 0))
        self.assertEqual(outcome.selected_versions["alpha"], Version(2, 0, 0))
        self.assertTrue(outcome.derivation_steps)

    def test_resolve_reports_conflict_for_unregistered_package(self) -> None:
        self.checked_dependencysolver.violating(ResolutionConflictError).resolve(
            (PackageDependency("gamma", VersionRange(">=1.0.0")),)
        )

    def test_parse_version_rejects_minor_leading_zero(self) -> None:
        self.checked_versionengine.violating(InvalidVersionError).parse_version("1.02.3")

    def test_parse_version_rejects_patch_leading_zero(self) -> None:
        self.checked_versionengine.violating(InvalidVersionError).parse_version("1.2.03")

    def test_parse_version_rejects_prerelease_leading_zero(self) -> None:
        self.checked_versionengine.violating(InvalidVersionError).parse_version("1.2.3-01")

    def test_parse_version_rejects_incomplete_version(self) -> None:
        self.checked_versionengine.violating(InvalidVersionError).parse_version("1.2")

    def test_parse_range_rejects_empty_expression(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range("")

    def test_parse_range_rejects_whitespace_only_expression(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range("   ")

    def test_parse_range_rejects_comma_delimited_comparators(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range(">=1.0.0,<2.0.0")

    def test_parse_range_rejects_empty_union_clause(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range(">=1.0.0 || ")

    def test_parse_range_rejects_malformed_union(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range(">=1.0.0 || || <2.0.0")

    def test_parse_range_rejects_malformed_hyphen_range(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range("1.0.0 -")

    def test_parse_range_rejects_overlong_wildcard(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range("1.2.3.x")

    def test_parse_range_rejects_component_after_wildcard(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range("1.x.3")

    def test_parse_range_rejects_operator_without_target(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range(">=")

    def test_parse_range_accepts_operator_whitespace(self) -> None:
        spaced = self.checked_versionengine.parse_range(">= 1.0.0")
        spaced_wildcard = self.checked_versionengine.parse_range(">= 1.x")
        self.assertEqual(spaced.raw_text, ">= 1.0.0")
        self.assertEqual(spaced_wildcard.raw_text, ">= 1.x")

    def test_satisfies_matches_exact_comparators(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3")
        higher = self.checked_versionengine.parse_version("2.0.0")
        equal = self.checked_versionengine.parse_range("==1.2.3")
        single_equal = self.checked_versionengine.parse_range("=1.2.3")
        not_equal = self.checked_versionengine.parse_range("!=1.2.3")
        at_most = self.checked_versionengine.parse_range("<=1.2.3")
        greater = self.checked_versionengine.parse_range(">1.2.3")
        self.assertTrue(self.checked_versionengine.satisfies(version, equal, False))
        self.assertFalse(self.checked_versionengine.satisfies(higher, equal, False))
        self.assertTrue(self.checked_versionengine.satisfies(version, single_equal, False))
        self.assertTrue(self.checked_versionengine.satisfies(higher, not_equal, False))
        self.assertFalse(self.checked_versionengine.satisfies(version, not_equal, False))
        self.assertTrue(self.checked_versionengine.satisfies(version, at_most, False))
        self.assertFalse(self.checked_versionengine.satisfies(higher, at_most, False))
        self.assertTrue(self.checked_versionengine.satisfies(higher, greater, False))
        self.assertFalse(self.checked_versionengine.satisfies(version, greater, False))

    def test_satisfies_matches_wildcard_comparators(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3")
        higher = self.checked_versionengine.parse_version("2.0.0")
        lower = self.checked_versionengine.parse_version("0.1.0")
        base = self.checked_versionengine.parse_version("1.0.0")
        equal = self.checked_versionengine.parse_range("==1.x")
        not_equal = self.checked_versionengine.parse_range("!=1.x")
        less = self.checked_versionengine.parse_range("<1.x")
        at_most = self.checked_versionengine.parse_range("<=1.x")
        greater = self.checked_versionengine.parse_range(">1.*")
        self.assertTrue(self.checked_versionengine.satisfies(version, equal, False))
        self.assertFalse(self.checked_versionengine.satisfies(higher, equal, False))
        self.assertTrue(self.checked_versionengine.satisfies(higher, not_equal, False))
        self.assertFalse(self.checked_versionengine.satisfies(version, not_equal, False))
        self.assertTrue(self.checked_versionengine.satisfies(lower, less, False))
        self.assertFalse(self.checked_versionengine.satisfies(base, less, False))
        self.assertTrue(self.checked_versionengine.satisfies(base, at_most, False))
        self.assertFalse(self.checked_versionengine.satisfies(higher, at_most, False))
        self.assertTrue(self.checked_versionengine.satisfies(higher, greater, False))
        self.assertFalse(self.checked_versionengine.satisfies(base, greater, False))

    def test_satisfies_matches_caret_and_tilde_prefixes(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3")
        latest = self.checked_versionengine.parse_version("2.0.0")
        origin = self.checked_versionengine.parse_version("0.0.0")
        base = self.checked_versionengine.parse_version("1.0.0")
        caret = self.checked_versionengine.parse_range("^1.2.3")
        tilde = self.checked_versionengine.parse_range("~1.2.3")
        zero_caret = self.checked_versionengine.parse_range("^0.x")
        major_tilde = self.checked_versionengine.parse_range("~1.x")
        self.assertTrue(self.checked_versionengine.satisfies(version, caret, False))
        self.assertFalse(self.checked_versionengine.satisfies(latest, caret, False))
        self.assertTrue(self.checked_versionengine.satisfies(version, tilde, False))
        self.assertFalse(self.checked_versionengine.satisfies(latest, tilde, False))
        self.assertTrue(self.checked_versionengine.satisfies(origin, zero_caret, False))
        self.assertFalse(self.checked_versionengine.satisfies(base, zero_caret, False))
        self.assertTrue(self.checked_versionengine.satisfies(version, major_tilde, False))
        self.assertFalse(self.checked_versionengine.satisfies(latest, major_tilde, False))

    def test_satisfies_matches_hyphen_bound_combinations(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3")
        upper = self.checked_versionengine.parse_version("2.0.0")
        lower = self.checked_versionengine.parse_version("0.1.0")
        exact_bounds = self.checked_versionengine.parse_range("1.0.0 - 2.0.0")
        wildcard_lower = self.checked_versionengine.parse_range("1.x - 2.0.0")
        self.assertTrue(self.checked_versionengine.satisfies(version, exact_bounds, False))
        self.assertTrue(self.checked_versionengine.satisfies(upper, exact_bounds, False))
        self.assertFalse(self.checked_versionengine.satisfies(lower, exact_bounds, False))
        self.assertTrue(self.checked_versionengine.satisfies(version, wildcard_lower, False))
        self.assertTrue(self.checked_versionengine.satisfies(upper, wildcard_lower, False))
        self.assertFalse(self.checked_versionengine.satisfies(lower, wildcard_lower, False))

    def test_satisfies_matches_fully_unspecified_wildcards(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3")
        origin = self.checked_versionengine.parse_version("0.0.0")
        all_versions = self.checked_versionengine.parse_range(">=*")
        less_than_all = self.checked_versionengine.parse_range("<*")
        greater_than_all = self.checked_versionengine.parse_range(">*")
        self.assertTrue(self.checked_versionengine.satisfies(version, all_versions, False))
        self.assertFalse(self.checked_versionengine.satisfies(origin, less_than_all, False))
        self.assertFalse(self.checked_versionengine.satisfies(origin, greater_than_all, False))

    def test_compare_precedence_orders_ascii_identifiers(self) -> None:
        earlier = self.checked_versionengine.parse_version("1.2.3-alpha")
        later = self.checked_versionengine.parse_version("1.2.3-beta")
        self.assertLess(self.checked_versionengine.compare_precedence(earlier, later), 0)
        self.assertGreater(self.checked_versionengine.compare_precedence(later, earlier), 0)

    def test_compare_precedence_orders_longer_prerelease_prefix(self) -> None:
        shorter = self.checked_versionengine.parse_version("1.2.3-alpha")
        longer = self.checked_versionengine.parse_version("1.2.3-alpha.1")
        self.assertLess(self.checked_versionengine.compare_precedence(shorter, longer), 0)
        self.assertGreater(self.checked_versionengine.compare_precedence(longer, shorter), 0)

    def test_compare_precedence_orders_numeric_prerelease_segments(self) -> None:
        earlier = self.checked_versionengine.parse_version("1.2.3-alpha.1")
        later = self.checked_versionengine.parse_version("1.2.3-alpha.2")
        numeric = self.checked_versionengine.parse_version("1.2.3-1")
        textual = self.checked_versionengine.parse_version("1.2.3-alpha")
        self.assertLess(self.checked_versionengine.compare_precedence(earlier, later), 0)
        self.assertGreater(self.checked_versionengine.compare_precedence(later, earlier), 0)
        self.assertLess(self.checked_versionengine.compare_precedence(numeric, textual), 0)
        self.assertGreater(self.checked_versionengine.compare_precedence(textual, numeric), 0)

    def test_resolve_reports_diamond_range_conflict(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease("delta", Version(1, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),))
        )
        self.checked_packagerepository.register_package(
            PackageRelease("epsilon", Version(1, 0, 0), (PackageDependency("alpha", VersionRange("<1.1.0")),))
        )
        self.checked_dependencysolver.violating(ResolutionConflictError).resolve(
            (
                PackageDependency("delta", VersionRange(">=1.0.0")),
                PackageDependency("epsilon", VersionRange(">=1.0.0")),
            )
        )

    def test_resolve_reports_assigned_dependency_conflict(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease("zeta", Version(1, 0, 0), (PackageDependency("alpha", VersionRange(">=2.0.0")),))
        )
        self.checked_dependencysolver.violating(ResolutionConflictError).resolve(
            (
                PackageDependency("alpha", VersionRange("<2.0.0")),
                PackageDependency("zeta", VersionRange(">=1.0.0")),
            )
        )

    def test_resolve_backtracks_rejected_candidate(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease("theta", Version(1, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),))
        )
        self.checked_packagerepository.register_package(
            PackageRelease("theta", Version(2, 0, 0), (PackageDependency("alpha", VersionRange("<1.0.0")),))
        )
        outcome = self.checked_dependencysolver.resolve((PackageDependency("theta", VersionRange(">=1.0.0")),))
        self.assertEqual(outcome.selected_versions["theta"], Version(1, 0, 0))
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 0, 0))

    def test_satisfies_matches_zero_major_caret_boundaries(self) -> None:
        minor = self.checked_versionengine.parse_version("0.2.5")
        major = self.checked_versionengine.parse_version("1.0.0")
        patch = self.checked_versionengine.parse_version("0.0.5")
        base = self.checked_versionengine.parse_version("0.1.0")
        exact = self.checked_versionengine.parse_version("0.0.3")
        minor_caret = self.checked_versionengine.parse_range("^0.2.x")
        wildcard_patch_caret = self.checked_versionengine.parse_range("^0.0.x")
        patch_caret = self.checked_versionengine.parse_range("^0.0.3")
        self.assertTrue(self.checked_versionengine.satisfies(minor, minor_caret, False))
        self.assertFalse(self.checked_versionengine.satisfies(major, minor_caret, False))
        self.assertTrue(self.checked_versionengine.satisfies(patch, wildcard_patch_caret, False))
        self.assertFalse(self.checked_versionengine.satisfies(base, wildcard_patch_caret, False))
        self.assertTrue(self.checked_versionengine.satisfies(exact, patch_caret, False))
        self.assertFalse(self.checked_versionengine.satisfies(patch, patch_caret, False))

    def test_parse_range_rejects_hyphen_range_with_trailing_token(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range("1.0.0 - 2.0.0 3.0.0")

    def test_parse_range_rejects_lone_pipe_union(self) -> None:
        self.checked_versionengine.violating(InvalidRangeError).parse_range(">=1.0.0 | <2.0.0")

    def test_resolve_accepts_bounded_root_with_compatible_transitive_range(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease("beta", Version(2, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),))
        )
        outcome = self.checked_dependencysolver.resolve((PackageDependency("beta", VersionRange(">=1.0.0 <3.0.0")),))
        self.assertEqual(outcome.selected_versions["beta"], Version(2, 0, 0))
        self.assertEqual(outcome.selected_versions["alpha"], Version(2, 0, 0))

    def test_parse_version_error_projects_message_string(self) -> None:
        self.checked_versionengine.violating(InvalidVersionError).parse_version("01.2.3")
        invalid = InvalidVersionError("invalid semantic version syntax", "01.2.3")
        self.assertIsInstance(invalid.message, str)
        self.assertEqual(invalid.raw_text, "01.2.3")
        self.assertTrue(str(invalid))
        self.assertTrue(str(SemVerError("semantic versioning failure")))

    def test_resolve_accepts_bounded_root_assigned_before_dependent(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease("beta", Version(1, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),))
        )
        self.checked_packagerepository.register_package(
            PackageRelease("beta", Version(2, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),))
        )
        outcome = self.checked_dependencysolver.resolve(
            (
                PackageDependency("alpha", VersionRange(">=2.0.0 <3.0.0")),
                PackageDependency("beta", VersionRange(">=1.0.0")),
            )
        )
        self.assertEqual(outcome.selected_versions["alpha"], Version(2, 0, 0))
        self.assertEqual(outcome.selected_versions["beta"], Version(2, 0, 0))


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing component services for SemverSolver state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.__dict__["_services"] = (self.versionengine, self.packagerepository, self.dependencysolver,)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> SemverSolverSUT:
    return SemverSolverSUT()


SemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="SemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T21:04:19Z
# LAST_CHANGED: 2026-11-10T21:03:51Z
# CHANGE: Resolved both remaining [from:pretense_coverage] defects: (1) semver.solver.compatible_assignment ordering 'bounded_root_selected_first,transitive_range_satisfied' — added test_resolve_accepts_bounded_root_assigned_before_dependent, which registers alpha 1.0.0/2.0.0 and both beta releases, then resolves a two-root set (alpha bounded '>=2.0.0 <3.0.0', beta '>=1.0.0'); the bounded alpha root has a single candidate so the dependency is assigned first and beta's transitive alpha>=1.0.0 range is validated against the already-assigned alpha 2.0.0, asserting both selections. (2) semver.parse_version.leading_zero_grammar error string conversion projection — extended test_parse_version_error_projects_message_string to construct the contract error records positionally (avoiding keyword-construction differences) and exercise str() conversion for both InvalidVersionError and SemVerError alongside the message/raw_text structured-attribute assertions.
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T21:04:19Z
# PRETENSE_QA_AUDIT: 2026-11-10T21:04:06Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmarks.runs.semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver import (
    ComparatorOp,
    DependencySolver,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)


# ==============================================================================
# 1. Model Reference Data and Oracles
# ==============================================================================
# The model keeps a small table of canonical SemVer texts, ranges, versions, and
# releases. Transitions constrain their parameter domains to these tables so the
# generative property tests only exercise contracted (valid) inputs, while the
# contracted *Error branches are covered by fixed scenarios through `violating`.

_MODEL_DEPENDENCY_RANGE = VersionRange(">=1.0.0")

_MODEL_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "0.0.3",
    "0.0.5",
    "0.1.0",
    "0.2.5",
    "1.0.0",
    "1.1.0",
    "1.2.3",
    "2.0.0",
    "1.2.3-alpha",
    "1.2.3-beta",
    "1.2.3-1",
    "1.2.3-alpha.1",
    "1.2.3-alpha.2",
    "2.0.0-alpha.1",
    "1.2.3+build.5",
    "1.2.3-alpha.1+build.5",
)

_MODEL_RANGE_TEXTS: Tuple[str, ...] = (
    ">=1.0.0",
    ">=1.x",
    ">=1.2.3-alpha.1",
    ">=*",
    "<*",
    ">*",
    "^1.x",
    "^1.2.3",
    "^0.x",
    "^0.2.x",
    "^0.0.x",
    "^0.0.3",
    "~1.x",
    "~1.2.x",
    "~1.2.3",
    "=1.2.3",
    "==1.2.3",
    "!=1.2.3",
    "<=1.2.3",
    ">1.2.3",
    "==1.x",
    "!=1.x",
    "<1.x",
    "<=1.x",
    ">1.*",
    "1.0.0 - 2.x",
    "1.0.0 - 2.0.0",
    "1.x - 2.0.0",
    ">=1.x || <1.2.3",
)

_MODEL_VERSIONS: Tuple[Version, ...] = (
    Version(0, 0, 0),
    Version(0, 0, 3),
    Version(0, 0, 5),
    Version(0, 1, 0),
    Version(0, 2, 5),
    Version(1, 0, 0),
    Version(1, 1, 0),
    Version(1, 2, 3),
    Version(2, 0, 0),
    Version(1, 2, 3, ("alpha",)),
    Version(1, 2, 3, ("beta",)),
    Version(1, 2, 3, ("1",)),
    Version(1, 2, 3, ("alpha", "1")),
    Version(1, 2, 3, ("alpha", "2")),
    Version(2, 0, 0, ("alpha", "1")),
    Version(1, 2, 3, (), ("build", "5")),
    Version(1, 2, 3, ("alpha", "1"), ("build", "5")),
)

_MODEL_RANGES: Tuple[VersionRange, ...] = (
    VersionRange(">=1.0.0"),
    VersionRange(">=1.x"),
    VersionRange(">=1.2.3-alpha.1"),
    VersionRange(">=*"),
    VersionRange("<*"),
    VersionRange(">*"),
    VersionRange("^1.x"),
    VersionRange("^1.2.3"),
    VersionRange("^0.x"),
    VersionRange("^0.2.x"),
    VersionRange("^0.0.x"),
    VersionRange("^0.0.3"),
    VersionRange("~1.x"),
    VersionRange("~1.2.x"),
    VersionRange("~1.2.3"),
    VersionRange("=1.2.3"),
    VersionRange("==1.2.3"),
    VersionRange("!=1.2.3"),
    VersionRange("<=1.2.3"),
    VersionRange(">1.2.3"),
    VersionRange("==1.x"),
    VersionRange("!=1.x"),
    VersionRange("<1.x"),
    VersionRange("<=1.x"),
    VersionRange(">1.*"),
    VersionRange("1.0.0 - 2.x"),
    VersionRange("1.0.0 - 2.0.0"),
    VersionRange("1.x - 2.0.0"),
    VersionRange(">=1.x || <1.2.3"),
)

_MODEL_RELEASES: Tuple[PackageRelease, ...] = (
    PackageRelease("alpha", Version(1, 0, 0)),
    PackageRelease("alpha", Version(1, 1, 0)),
    PackageRelease("alpha", Version(2, 0, 0)),
    PackageRelease("beta", Version(1, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),)),
    PackageRelease("beta", Version(2, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),)),
    PackageRelease("gamma", Version(1, 0, 0)),
    PackageRelease("delta", Version(1, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),)),
    PackageRelease("epsilon", Version(1, 0, 0), (PackageDependency("alpha", VersionRange("<1.1.0")),)),
    PackageRelease("zeta", Version(1, 0, 0), (PackageDependency("alpha", VersionRange(">=2.0.0")),)),
    PackageRelease("theta", Version(1, 0, 0), (PackageDependency("alpha", VersionRange(">=1.0.0")),)),
    PackageRelease("theta", Version(2, 0, 0), (PackageDependency("alpha", VersionRange("<1.0.0")),)),
)


def _model_padded_texts(texts: Tuple[str, ...]) -> Tuple[str, ...]:
    """Derives text variants whose surrounding whitespace trimming contracts accept."""
    variants: List[str] = []
    for text in texts:
        for leading in ("", " ", "  "):
            for trailing in ("", " ", "  "):
                variants.append(f"{leading}{text}{trailing}")
    return tuple(variants)


def _model_version_satisfies(version: Version, raw_text: str) -> bool:
    """Evaluates a whitespace-delimited comparator clause against a version."""
    tokens = raw_text.split()
    if not tokens:
        return False
    return all(_model_comparator_satisfied(version, token) for token in tokens)


def _model_comparator_satisfied(version: Version, token: str) -> bool:
    """Evaluates one comparator token of a dependency range against a version."""
    for operator in ("==", ">=", "<=", "!=", "=", ">", "<"):
        if not token.startswith(operator):
            continue
        target_text = token[len(operator):].strip()
        if not target_text:
            return False
        try:
            target = _model_parse_version(target_text)
        except ValueError:
            return False
        comparison = _model_compare(version, target)
        if operator in ("==", "="):
            return comparison == 0
        if operator == "!=":
            return comparison != 0
        if operator == ">=":
            return comparison >= 0
        if operator == "<=":
            return comparison <= 0
        if operator == ">":
            return comparison > 0
        return comparison < 0
    return False


_MODEL_RANGE_TEXT_VARIANTS: Tuple[str, ...] = (
    ">= 1.0.0",
    ">= 1.x",
    ">= 1.2.3-alpha.1",
    "^ 1.x",
    "~ 1.2.x",
    "^ 0.0.x",
    ">= 1.x || <1.2.3",
)

_MODEL_RANGE_INPUT_TEXTS: Tuple[str, ...] = _model_padded_texts(_MODEL_RANGE_TEXTS + _MODEL_RANGE_TEXT_VARIANTS)


def _model_parse_version(text: str) -> Version:
    """Derives the expected Version record for a canonical SemVer text."""
    core_text, _, build_text = text.strip().partition("+")
    core_text, _, prerelease_text = core_text.partition("-")
    major_text, minor_text, patch_text = core_text.split(".")
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build = tuple(build_text.split(".")) if build_text else ()
    return Version(int(major_text), int(minor_text), int(patch_text), prerelease, build)


def _model_format_version(version: Version) -> str:
    """Derives the canonical SemVer string for a Version record."""
    text = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        text = f"{text}-{'.'.join(version.prerelease)}"
    if version.build:
        text = f"{text}+{'.'.join(version.build)}"
    return text


def _model_precedence_key(version: Version) -> Tuple[int, int, int, int, Tuple[Tuple[int, int, str], ...]]:
    """Derives a total-order key implementing SemVer 2.0.0 precedence rules."""
    segment_keys = tuple(
        (0, int(identifier), "") if identifier.isdigit() else (1, 0, identifier)
        for identifier in version.prerelease
    )
    return (
        version.major,
        version.minor,
        version.patch,
        0 if version.prerelease else 1,
        segment_keys,
    )


def _model_compare(v1: Version, v2: Version) -> int:
    """Derives the expected precedence sign for two Version records."""
    key1 = _model_precedence_key(v1)
    key2 = _model_precedence_key(v2)
    if key1 < key2:
        return -1
    if key1 > key2:
        return 1
    return 0


def _model_release_key(release: PackageRelease) -> Tuple[int, int, int, int, Tuple[Tuple[int, int, str], ...]]:
    """Derives the precedence ordering key of a package release publication."""
    return _model_precedence_key(release.version)


# ==============================================================================
# 2. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Contract violations (*Error) are caller preconditions gated by require(...) and
# require_arg(..., error=ExpectedError); they are exercised in fixed scenarios via
# checked.violating(...). This interface has no operational *Exception contracts,
# so the module intentionally contains no `with raises(...)` blocks.

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    focus_version: Version = Version(1, 0, 0)
    versions: List[Version] = field(default_factory=list)
    ranges: List[VersionRange] = field(default_factory=list)
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    outcomes: List[ResolutionOutcome] = field(default_factory=list)
    resolver_roots: Tuple[Tuple[PackageDependency, ...], ...] = ()
    valid_version_texts: Tuple[str, ...] = _MODEL_VERSION_TEXTS
    valid_range_texts: Tuple[str, ...] = _MODEL_RANGE_INPUT_TEXTS
    known_versions: Tuple[Version, ...] = _MODEL_VERSIONS
    valid_ranges: Tuple[VersionRange, ...] = _MODEL_RANGES
    known_releases: Tuple[PackageRelease, ...] = _MODEL_RELEASES


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> SemverSolverState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return SemverSolverState()

    def _model_package_resolvable(self, name: str, seen: Tuple[str, ...]) -> bool:
        """Reports whether some registered release of name has satisfiable dependencies."""
        if name in seen:
            return False
        releases = self.state.packages.get(name)
        if not releases:
            return False
        return any(
            self._model_release_resolvable(release, seen + (name,))
            for release in releases
        )

    def _model_release_resolvable(self, release: PackageRelease, seen: Tuple[str, ...]) -> bool:
        """Reports whether every dependency of a release can be satisfied."""
        return all(
            self._model_dependency_resolvable(dependency, seen)
            for dependency in release.dependencies
        )

    def _model_dependency_resolvable(self, dependency: PackageDependency, seen: Tuple[str, ...]) -> bool:
        """Reports whether a dependency range has a registered satisfying release."""
        candidates = self.state.packages.get(dependency.name, [])
        satisfiable = any(
            _model_version_satisfies(candidate.version, dependency.range_constraint.raw_text)
            for candidate in candidates
        )
        return satisfiable and self._model_package_resolvable(dependency.name, seen)

    def _model_release_dependencies_satisfied_by(self, release: PackageRelease, assigned: Dict[str, Version]) -> bool:
        """Reports whether every dependency of a release accepts an assigned version."""
        return all(
            dependency.name in assigned
            and _model_version_satisfies(assigned[dependency.name], dependency.range_constraint.raw_text)
            for dependency in release.dependencies
        )

    def _model_resolver_roots(self) -> Tuple[Tuple[PackageDependency, ...], ...]:
        """Derives single-package root dependency sets the model knows are satisfiable."""
        roots: List[Tuple[PackageDependency, ...]] = []
        for name in sorted(self.state.packages):
            releases = self.state.packages[name]
            if not releases:
                continue
            if self._model_package_resolvable(name, ()):
                roots.append((PackageDependency(name, _MODEL_DEPENDENCY_RANGE),))
            highest = releases[0].version
            bounded_text = f">=1.0.0 <{highest.major + 1}.0.0"
            if any(
                _model_version_satisfies(release.version, bounded_text)
                and self._model_release_resolvable(release, ())
                for release in releases
            ):
                roots.append((PackageDependency(name, VersionRange(bounded_text)),))
            dependency_name = self._model_single_dependency_name(releases)
            if dependency_name is None:
                continue
            dependency_releases = self.state.packages.get(dependency_name, [])
            if not dependency_releases or any(release.dependencies for release in dependency_releases):
                continue
            dependency_version = dependency_releases[0].version
            dependency_bound = f">={dependency_version.major}.0.0 <{dependency_version.major + 1}.0.0"
            if not _model_version_satisfies(dependency_version, dependency_bound):
                continue
            assigned = {dependency_name: dependency_version}
            if any(
                _model_version_satisfies(release.version, _MODEL_DEPENDENCY_RANGE.raw_text)
                and self._model_release_dependencies_satisfied_by(release, assigned)
                for release in releases
            ):
                roots.append(
                    (
                        PackageDependency(dependency_name, VersionRange(dependency_bound)),
                        PackageDependency(name, _MODEL_DEPENDENCY_RANGE),
                    )
                )
        return tuple(roots)

    def _model_single_dependency_name(self, releases: List[PackageRelease]) -> Optional[str]:
        """Derives the sole dependency name shared by every release, when it exists."""
        names = tuple(
            dependency.name
            for release in releases
            for dependency in release.dependencies
        )
        if not names:
            return None
        if any(len(release.dependencies) != 1 for release in releases):
            return None
        if len(set(names)) != 1:
            return None
        return names[0]


    @transition(name="format")
    def format(self) -> str:
        require(self.state.initialized)
        ret: str = self.inner_format()
        assert ret == _model_format_version(self.state.focus_version)
        return ret

    def inner_format(self) -> str:
        return _model_format_version(self.state.focus_version)

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        ret: bool = self.inner_is_prerelease()
        assert ret == bool(self.state.focus_version.prerelease)
        return ret

    def inner_is_prerelease(self) -> bool:
        return bool(self.state.focus_version.prerelease)

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.in_set(self.state.valid_version_texts), error=InvalidVersionError)
        ret: Version = self.inner_parse_version(text)
        self.state.versions.append(ret)
        self.state.focus_version = ret
        assert ret == _model_parse_version(text)
        return ret

    def inner_parse_version(
        self,
        text: str,
    ) -> Version:
        return _model_parse_version(text)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.in_set(self.state.known_versions))
        require_arg(v2, Domain.in_set(self.state.known_versions))
        ret: int = self.inner_compare_precedence(v1, v2)
        observed = (ret > 0) - (ret < 0)
        assert observed == _model_compare(v1, v2)
        return ret

    def inner_compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        return _model_compare(v1, v2)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.in_set(self.state.valid_range_texts), error=InvalidRangeError)
        ret: VersionRange = self.inner_parse_range(text)
        self.state.ranges.append(ret)
        assert ret.raw_text == text.strip()
        return ret

    def inner_parse_range(
        self,
        text: str,
    ) -> VersionRange:
        return VersionRange(text.strip())

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.in_set(self.state.known_versions))
        require_arg(range_constraint, Domain.in_set(self.state.valid_ranges))
        require_arg(include_prerelease, Domain.boolean())
        ret: bool = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert isinstance(ret, bool)
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        if version.prerelease and not include_prerelease:
            return False
        return _model_compare(version, Version(1, 0, 0)) >= 0

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.in_set(self.state.known_releases))
        before = len(self.state.packages.get(release.name, []))
        ret = self.inner_register_package(release)
        releases = self.state.packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=_model_release_key, reverse=True)
        self.state.resolver_roots = self._model_resolver_roots()
        assert len(self.state.packages[release.name]) == before + 1
        assert releases == sorted(releases, key=_model_release_key, reverse=True)
        return ret

    def inner_register_package(
        self,
        release: PackageRelease,
    ) -> None:
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require(bool(self.state.packages))
        require_arg(name, Domain.in_set(tuple(self.state.packages)), error=PackageNotFoundError)
        ret: List[PackageRelease] = self.inner_get_releases(name)
        assert ret == self.state.packages[name]
        return ret

    def inner_get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        return list(self.state.packages.get(name, []))

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str))
        ret: bool = self.inner_has_package(name)
        assert ret == (name in self.state.packages)
        return ret

    def inner_has_package(
        self,
        name: str,
    ) -> bool:
        return name in self.state.packages

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = self.inner_all_packages()
        assert ret == set(self.state.packages)
        return ret

    def inner_all_packages(
        self,
    ) -> Set[str]:
        return set(self.state.packages)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require(bool(self.state.resolver_roots))
        require_arg(root_dependencies, Domain.in_set(self.state.resolver_roots), error=ResolutionConflictError)
        ret: ResolutionOutcome = self.inner_resolve(root_dependencies)
        self.state.outcomes.append(ret)
        assert {dependency.name for dependency in root_dependencies} <= set(ret.selected_versions)
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        selected: Dict[str, Version] = {}
        steps: List[str] = []
        for dependency in root_dependencies:
            releases = self.state.packages.get(dependency.name, [])
            if releases:
                selected[dependency.name] = releases[0].version
                steps.append(f"selected {dependency.name} at {_model_format_version(releases[0].version)}")
        return ResolutionOutcome(selected_versions=selected, derivation_steps=tuple(steps))

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds blank model state so generated transitions have reachable preconditions."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 3. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(state: Optional[SemverSolverState] = None) -> Any:
    """Creates a fake SemverSolver sharing the model state machine verdicts."""
    return FakeSemverSolver(state=state or proto.make_initial_state())


# ==============================================================================
# 4. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.sm = SemverSolverStateMachine()
        self.fake = make_semver_solver_fake()

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition and seeding transition."""
        self.sm.seed_initial()
        self.sm.format()
        self.sm.is_prerelease()
        self.sm.parse_version("1.2.3-alpha.1+build.5")
        self.sm.compare_precedence(Version(1, 2, 3, ("alpha", "1")), Version(1, 2, 3))
        self.sm.parse_range("^1.x")
        self.sm.satisfies(Version(1, 2, 3), VersionRange("^1.x"), False)
        self.sm.register_package(_MODEL_RELEASES[0])
        self.sm.get_releases("alpha")
        self.sm.has_package("alpha")
        self.sm.all_packages()
        self.sm.resolve((PackageDependency("alpha", _MODEL_DEPENDENCY_RANGE),))

    def test_fake_parses_versions_and_ranges(self) -> None:
        """Verifies the fake mirrors the interface parsing contracts."""
        self.assertEqual(self.fake.parse_version("1.2.3-alpha.1+build.5"), Version(1, 2, 3, ("alpha", "1"), ("build", "5")))
        self.assertEqual(self.fake.parse_range("  ^1.x  ").raw_text, "^1.x")
        self.assertEqual(self.fake.compare_precedence(Version(1, 2, 3), Version(2, 0, 0)), -1)

    def test_fake_satisfies_filters_prereleases(self) -> None:
        """Verifies the fake honors the prerelease filter contract."""
        self.assertTrue(self.fake.satisfies(Version(1, 2, 3), VersionRange("^1.x"), False))
        self.assertFalse(self.fake.satisfies(Version(1, 2, 3, ("alpha", "1")), VersionRange("^1.x"), False))

    def test_fake_repository_tracks_registered_releases(self) -> None:
        """Verifies the fake repository publication bookkeeping."""
        self.fake.register_package(_MODEL_RELEASES[0])
        self.fake.register_package(_MODEL_RELEASES[2])
        self.assertTrue(self.fake.has_package("alpha"))
        self.assertFalse(self.fake.has_package("gamma"))
        self.assertEqual(self.fake.all_packages(), {"alpha"})
        releases = self.fake.get_releases("alpha")
        self.assertEqual([release.version for release in releases], [Version(2, 0, 0), Version(1, 0, 0)])

    def test_fake_resolves_registered_dependencies(self) -> None:
        """Verifies the fake reports the highest registered release as selected."""
        self.fake.register_package(_MODEL_RELEASES[0])
        self.fake.register_package(_MODEL_RELEASES[2])
        outcome = self.fake.resolve((PackageDependency("alpha", _MODEL_DEPENDENCY_RANGE),))
        self.assertEqual(outcome.selected_versions["alpha"], Version(2, 0, 0))
        self.assertTrue(outcome.derivation_steps)


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T21:03:43Z
# LAST_CHANGED: 2026-11-10T21:03:43Z
# CHANGE: Added multi-package resolver roots so the 'dependency assigned before depending package' ordering is model-supported: _model_single_dependency_name detects packages that depend on exactly one dependency name, and _model_resolver_roots now emits a bounded-partner pair root (partner bounded to its highest release's major interval, depending package rooted at >=1.0.0) only when a release of the depending package both satisfies its root range and has every dependency accepted by the assigned partner version (_model_release_dependencies_satisfied_by). Pairs remain provably satisfiable, so generative/checked calls keep expecting success only where the model can prove a compatible assignment.
# --- END AUTOFAB METADATA ---
