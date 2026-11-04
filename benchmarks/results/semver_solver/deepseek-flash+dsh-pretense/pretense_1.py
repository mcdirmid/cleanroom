# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver.

Inherits the interface state machine from ``semver_solver_pretense`` and overrides
the transitions whose behavior must be observed on the concrete ``VersionEngine``,
``PackageRepository``, and ``DependencySolver`` singletons. Scenario tests drive
the real services through checked adapters so that every transition verifies its
model preconditions and postconditions at runtime.
"""

from __future__ import annotations

from typing import Any, Collection, List, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.semver_solver.pretense.semver_solver_pretense import (SemverSolverStateMachine, SemverSolverState, FakeSemverSolver, make_semver_solver_fakes)
from benchmark_2.parts.semver_solver.lib.semver_solver import Version, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome
from benchmark_2.parts.semver_solver.lib.semver_solver_impl import VersionEngine, PackageRepository, DependencySolver, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        current = self.state.current_version
        ret = call_target(current.format())
        expected = f"{current.major}.{current.minor}.{current.patch}"
        if current.prerelease:
            expected = expected + "-" + ".".join(current.prerelease)
        if current.build:
            expected = expected + "+" + ".".join(current.build)
        assert ret == expected
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        current = self.state.current_version
        ret = call_target(current.is_prerelease)
        assert ret is bool(current.prerelease)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
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
        self.sm = SemverSolverImplPseudoStateMachine(singletons={VersionEngine: self.versionengine, PackageRepository: self.packagerepository, DependencySolver: self.dependencysolver})
        self.checked_versionengine = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_components(self) -> None:
        parsed = self.checked_versionengine.parse_version("1.2.3-alpha.1+build.5")
        assert parsed.major == 1
        assert parsed.minor == 2
        assert parsed.patch == 3
        assert parsed.prerelease == ("alpha", "1")
        assert parsed.build == ("build", "5")

    def test_parse_version_plain_release(self) -> None:
        parsed = self.checked_versionengine.parse_version("2.0.0")
        assert parsed.major == 2
        assert parsed.prerelease == ()

    def test_compare_precedence_orders_versions(self) -> None:
        low = Version(1, 0, 0)
        high = Version(2, 0, 0)
        assert self.checked_versionengine.compare_precedence(low, high) < 0
        assert self.checked_versionengine.compare_precedence(high, low) > 0
        assert self.checked_versionengine.compare_precedence(low, low) == 0

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        assert self.checked_versionengine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3, build=("build.1",))) == 0

    def test_parse_range_canonical_text(self) -> None:
        parsed = self.checked_versionengine.parse_range(">=1.0.0")
        assert parsed.raw_text == ">=1.0.0"

    def test_satisfies_comparator_range(self) -> None:
        range_constraint = VersionRange(">=1.0.0")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), range_constraint, False)
        assert not self.checked_versionengine.satisfies(Version(2, 1, 0, prerelease=("alpha",)), range_constraint, False)

    def test_satisfies_includes_prerelease_when_requested(self) -> None:
        range_constraint = VersionRange(">=1.0.0")
        assert self.checked_versionengine.satisfies(Version(2, 1, 0, prerelease=("alpha",)), range_constraint, True)

    def test_register_and_query_repository(self) -> None:
        release = PackageRelease("alpha", Version(1, 2, 3))
        self.checked_packagerepository.register_package(release)
        assert self.checked_packagerepository.has_package("alpha")
        assert "alpha" in self.checked_packagerepository.all_packages()
        releases = self.checked_packagerepository.get_releases("alpha")
        assert len(releases) == 1

    def test_all_packages_tracks_registration(self) -> None:
        assert self.checked_packagerepository.all_packages() == set()
        self.checked_packagerepository.register_package(PackageRelease("delta", Version(1, 0, 0)))
        assert self.checked_packagerepository.all_packages() == {"delta"}
        assert not self.checked_packagerepository.has_package("beta")

    def test_resolve_selects_registered_versions(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 2, 3)))
        self.checked_packagerepository.register_package(PackageRelease("beta", Version(2, 0, 0)))
        self.sm.state.root_dependencies.extend(
            [
                PackageDependency("alpha", VersionRange(">=1.0.0")),
                PackageDependency("beta", VersionRange(">=1.0.0")),
            ]
        )
        outcome = self.checked_dependencysolver.resolve(
            [
                PackageDependency("alpha", VersionRange(">=1.0.0")),
                PackageDependency("beta", VersionRange(">=1.0.0")),
            ]
        )
        assert set(outcome.selected_versions.keys()) == {"alpha", "beta"}
        assert outcome.selected_versions["alpha"] == Version(1, 2, 3)
        assert outcome.selected_versions["beta"] == Version(2, 0, 0)

    def test_resolve_empty_dependencies(self) -> None:
        outcome = self.checked_dependencysolver.resolve([])
        assert outcome.selected_versions == {}

    def test_parse_range_operator_whitespace(self) -> None:
        parsed = self.checked_versionengine.parse_range(">= 1.2.3")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), parsed, False)
        assert not self.checked_versionengine.satisfies(Version(1, 0, 0), parsed, False)

    def test_satisfies_equality_comparators(self) -> None:
        double_equals = self.checked_versionengine.parse_range("==1.2.3")
        single_equals = self.checked_versionengine.parse_range("=1.2.3")
        not_equals = self.checked_versionengine.parse_range("!=1.2.3")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), double_equals, False)
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), single_equals, False)
        assert not self.checked_versionengine.satisfies(Version(1, 2, 3), not_equals, False)
        assert self.checked_versionengine.satisfies(Version(1, 2, 9), not_equals, False)

    def test_satisfies_less_than_boundaries(self) -> None:
        strict = self.checked_versionengine.parse_range("<1.2.3")
        inclusive = self.checked_versionengine.parse_range("<=1.2.3")
        assert not self.checked_versionengine.satisfies(Version(1, 2, 3), strict, False)
        assert self.checked_versionengine.satisfies(Version(1, 0, 0), strict, False)
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), inclusive, False)
        assert not self.checked_versionengine.satisfies(Version(1, 2, 9), inclusive, False)

    def test_satisfies_greater_than_boundaries(self) -> None:
        strict = self.checked_versionengine.parse_range(">1.2.3")
        inclusive = self.checked_versionengine.parse_range(">=1.2.3")
        assert not self.checked_versionengine.satisfies(Version(1, 2, 3), strict, False)
        assert self.checked_versionengine.satisfies(Version(1, 2, 9), strict, False)
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), inclusive, False)
        assert not self.checked_versionengine.satisfies(Version(1, 0, 0), inclusive, False)

    def test_caret_expands_major_boundary(self) -> None:
        caret = self.checked_versionengine.parse_range("^1.2.3")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), caret, False)
        assert self.checked_versionengine.satisfies(Version(1, 9, 9), caret, False)
        assert not self.checked_versionengine.satisfies(Version(2, 0, 0), caret, False)

    def test_caret_expands_minor_boundary(self) -> None:
        caret = self.checked_versionengine.parse_range("^0.2.3")
        assert self.checked_versionengine.satisfies(Version(0, 2, 3), caret, False)
        assert self.checked_versionengine.satisfies(Version(0, 2, 9), caret, False)
        assert not self.checked_versionengine.satisfies(Version(0, 3, 0), caret, False)

    def test_caret_expands_patch_boundary(self) -> None:
        caret = self.checked_versionengine.parse_range("^0.0.3")
        assert self.checked_versionengine.satisfies(Version(0, 0, 3), caret, False)
        assert not self.checked_versionengine.satisfies(Version(0, 0, 4), caret, False)

    def test_tilde_expands_to_next_minor(self) -> None:
        tilde = self.checked_versionengine.parse_range("~1.2.3")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), tilde, False)
        assert self.checked_versionengine.satisfies(Version(1, 2, 9), tilde, False)
        assert not self.checked_versionengine.satisfies(Version(1, 3, 0), tilde, False)

    def test_wildcard_minor_component(self) -> None:
        wildcard = self.checked_versionengine.parse_range("1.2.x")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), wildcard, False)
        assert self.checked_versionengine.satisfies(Version(1, 2, 9), wildcard, False)
        assert not self.checked_versionengine.satisfies(Version(1, 3, 0), wildcard, False)

    def test_wildcard_major_component(self) -> None:
        wildcard = self.checked_versionengine.parse_range("1.*")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), wildcard, False)
        assert self.checked_versionengine.satisfies(Version(1, 9, 9), wildcard, False)
        assert not self.checked_versionengine.satisfies(Version(2, 0, 0), wildcard, False)

    def test_hyphen_range_boundaries(self) -> None:
        hyphen = self.checked_versionengine.parse_range("1.2.3 - 2.0.0")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), hyphen, False)
        assert self.checked_versionengine.satisfies(Version(1, 5, 0), hyphen, False)
        assert self.checked_versionengine.satisfies(Version(2, 0, 0), hyphen, False)
        assert not self.checked_versionengine.satisfies(Version(2, 1, 0), hyphen, False)

    def test_union_alternatives(self) -> None:
        union = self.checked_versionengine.parse_range(">=2.0.0 || <1.0.0")
        assert self.checked_versionengine.satisfies(Version(2, 0, 0), union, False)
        assert self.checked_versionengine.satisfies(Version(0, 5, 0), union, False)
        assert not self.checked_versionengine.satisfies(Version(1, 5, 0), union, False)

    def test_multi_comparator_conjunction(self) -> None:
        conjunction = self.checked_versionengine.parse_range(">=1.2.3 <2.0.0")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), conjunction, False)
        assert self.checked_versionengine.satisfies(Version(1, 9, 9), conjunction, False)
        assert not self.checked_versionengine.satisfies(Version(2, 0, 0), conjunction, False)
        assert not self.checked_versionengine.satisfies(Version(1, 0, 0), conjunction, False)

    def test_prerelease_filtered_without_flag(self) -> None:
        inclusive = self.checked_versionengine.parse_range(">=1.0.0")
        assert not self.checked_versionengine.satisfies(Version(2, 0, 0, prerelease=("rc", "1")), inclusive, False)
        assert not self.checked_versionengine.satisfies(Version(2, 1, 0, prerelease=("alpha",)), inclusive, False)

    def test_prerelease_evaluated_with_flag(self) -> None:
        inclusive = self.checked_versionengine.parse_range(">=1.0.0")
        assert self.checked_versionengine.satisfies(Version(2, 0, 0, prerelease=("rc", "1")), inclusive, True)
        assert self.checked_versionengine.satisfies(Version(2, 1, 0, prerelease=("alpha",)), inclusive, True)
        assert not self.checked_versionengine.satisfies(Version(1, 0, 0, prerelease=("alpha",)), inclusive, True)

    def test_prerelease_explicitly_targeted(self) -> None:
        targeted = self.checked_versionengine.parse_range("2.0.0-rc.1")
        assert self.checked_versionengine.satisfies(Version(2, 0, 0, prerelease=("rc", "1")), targeted, False)

    def test_range_target_carries_prerelease(self) -> None:
        targeted = self.checked_versionengine.parse_range(">=1.0.0-alpha")
        assert self.checked_versionengine.satisfies(Version(1, 0, 0, prerelease=("alpha",)), targeted, False)

    def test_range_target_carries_build_metadata(self) -> None:
        targeted = self.checked_versionengine.parse_range(">=1.2.3+build.5")
        assert self.checked_versionengine.satisfies(Version(1, 2, 3), targeted, False)
        assert self.checked_versionengine.satisfies(Version(1, 2, 3, build=("build.5",)), targeted, False)

    def test_compare_precedence_numeric_below_string(self) -> None:
        numeric = Version(1, 0, 0, prerelease=("1",))
        alphabetic = Version(1, 0, 0, prerelease=("alpha",))
        assert self.checked_versionengine.compare_precedence(numeric, alphabetic) < 0
        assert self.checked_versionengine.compare_precedence(alphabetic, numeric) > 0

    def test_compare_precedence_prerelease_length(self) -> None:
        shorter = Version(1, 0, 0, prerelease=("alpha",))
        longer = Version(1, 0, 0, prerelease=("alpha", "1"))
        assert self.checked_versionengine.compare_precedence(shorter, longer) < 0
        assert self.checked_versionengine.compare_precedence(longer, shorter) > 0

    def test_compare_precedence_normal_above_prerelease(self) -> None:
        normal = Version(1, 0, 0)
        prerelease = Version(1, 0, 0, prerelease=("alpha",))
        assert self.checked_versionengine.compare_precedence(normal, prerelease) > 0
        assert self.checked_versionengine.compare_precedence(prerelease, normal) < 0

    def test_compare_precedence_numeric_segment_values(self) -> None:
        lower = Version(1, 0, 0, prerelease=("2",))
        higher = Version(1, 0, 0, prerelease=("10",))
        assert self.checked_versionengine.compare_precedence(lower, higher) < 0
        assert self.checked_versionengine.compare_precedence(higher, lower) > 0

    def test_compare_precedence_continues_after_shared_prefix(self) -> None:
        lower = Version(1, 0, 0, prerelease=("1", "2"))
        higher = Version(1, 0, 0, prerelease=("1", "3"))
        assert self.checked_versionengine.compare_precedence(lower, higher) < 0
        assert self.checked_versionengine.compare_precedence(higher, lower) > 0

    def test_compare_precedence_alphanumeric_code_point_order(self) -> None:
        upper = Version(1, 0, 0, prerelease=("B",))
        lower = Version(1, 0, 0, prerelease=("a",))
        assert self.checked_versionengine.compare_precedence(upper, lower) < 0
        assert self.checked_versionengine.compare_precedence(lower, upper) > 0

    def test_get_releases_descending_precedence(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 5, 0)))
        releases = self.checked_packagerepository.get_releases("alpha")
        assert [release.version for release in releases] == [Version(2, 0, 0), Version(1, 5, 0), Version(1, 0, 0)]

    def test_get_releases_returns_shallow_copy(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        releases = self.checked_packagerepository.get_releases("alpha")
        releases.append(PackageRelease("alpha", Version(9, 9, 9)))
        fresh = self.checked_packagerepository.get_releases("alpha")
        assert len(fresh) == 1
        assert fresh[0].version == Version(1, 0, 0)

    def test_resolve_transitive_dependency_merge(self) -> None:
        alpha_old = PackageRelease("alpha", Version(1, 0, 0), (PackageDependency("gamma", VersionRange(">=1.0.0")),))
        alpha_new = PackageRelease("alpha", Version(2, 0, 0), (PackageDependency("gamma", VersionRange(">=2.0.0")),))
        gamma_old = PackageRelease("gamma", Version(1, 5, 0))
        gamma_new = PackageRelease("gamma", Version(2, 1, 0))
        self.sm.state.releases.extend([alpha_old, alpha_new, gamma_old, gamma_new])
        self.checked_packagerepository.register_package(alpha_old)
        self.checked_packagerepository.register_package(alpha_new)
        self.checked_packagerepository.register_package(gamma_old)
        self.checked_packagerepository.register_package(gamma_new)
        self.sm.state.root_dependencies.extend(
            [
                PackageDependency("alpha", VersionRange(">=1.0.0")),
                PackageDependency("gamma", VersionRange(">=1.0.0")),
            ]
        )
        outcome = self.checked_dependencysolver.resolve(
            [
                PackageDependency("alpha", VersionRange(">=1.0.0")),
                PackageDependency("gamma", VersionRange(">=1.0.0")),
            ]
        )
        assert outcome.selected_versions["alpha"] == Version(2, 0, 0)
        assert outcome.selected_versions["gamma"] == Version(2, 1, 0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_backtracks_to_alternative_release(self) -> None:
        alpha_old = PackageRelease("alpha", Version(1, 0, 0), (PackageDependency("gamma", VersionRange(">=1.0.0")),))
        alpha_new = PackageRelease("alpha", Version(2, 0, 0), (PackageDependency("gamma", VersionRange(">=2.0.0")),))
        gamma_only = PackageRelease("gamma", Version(1, 5, 0))
        self.sm.state.releases.extend([alpha_old, alpha_new, gamma_only])
        self.checked_packagerepository.register_package(alpha_old)
        self.checked_packagerepository.register_package(alpha_new)
        self.checked_packagerepository.register_package(gamma_only)
        self.sm.state.root_dependencies.extend(
            [
                PackageDependency("alpha", VersionRange(">=1.0.0")),
                PackageDependency("gamma", VersionRange(">=1.0.0")),
            ]
        )
        outcome = self.checked_dependencysolver.resolve(
            [
                PackageDependency("alpha", VersionRange(">=1.0.0")),
                PackageDependency("gamma", VersionRange(">=1.0.0")),
            ]
        )
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)
        assert outcome.selected_versions["gamma"] == Version(1, 5, 0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_retreats_from_unsatisfiable_transitive_candidate(self) -> None:
        alpha_old = PackageRelease("alpha", Version(1, 0, 0), (PackageDependency("gamma", VersionRange(">=1.0.0")),))
        alpha_new = PackageRelease(
            "alpha",
            Version(2, 0, 0),
            (
                PackageDependency("omega", VersionRange(">=1.0.0")),
                PackageDependency("gamma", VersionRange(">=3.0.0")),
            ),
        )
        gamma_only = PackageRelease("gamma", Version(1, 5, 0))
        self.sm.state.releases.extend([alpha_old, alpha_new, gamma_only])
        self.checked_packagerepository.register_package(alpha_old)
        self.checked_packagerepository.register_package(alpha_new)
        self.checked_packagerepository.register_package(gamma_only)
        self.sm.state.root_dependencies.extend(
            [
                PackageDependency("alpha", VersionRange(">=1.0.0")),
                PackageDependency("gamma", VersionRange(">=1.0.0")),
            ]
        )
        outcome = self.checked_dependencysolver.resolve(
            [
                PackageDependency("alpha", VersionRange(">=1.0.0")),
                PackageDependency("gamma", VersionRange(">=1.0.0")),
            ]
        )
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)
        assert outcome.selected_versions["gamma"] == Version(1, 5, 0)
        assert "omega" not in outcome.selected_versions
        assert len(outcome.derivation_steps) > 0

    def test_resolve_retreats_when_transitive_package_is_absent(self) -> None:
        alpha_old = PackageRelease("alpha", Version(1, 0, 0), (PackageDependency("gamma", VersionRange(">=1.0.0")),))
        alpha_new = PackageRelease("alpha", Version(2, 0, 0), (PackageDependency("omega", VersionRange(">=1.0.0")),))
        gamma_only = PackageRelease("gamma", Version(1, 5, 0))
        self.sm.state.releases.extend([alpha_old, alpha_new, gamma_only])
        self.checked_packagerepository.register_package(alpha_old)
        self.checked_packagerepository.register_package(alpha_new)
        self.checked_packagerepository.register_package(gamma_only)
        roots = [
            PackageDependency("alpha", VersionRange(">=1.0.0")),
            PackageDependency("gamma", VersionRange(">=1.0.0")),
        ]
        self.sm.state.root_dependencies.extend(roots)
        outcome = self.checked_dependencysolver.resolve(roots)
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)
        assert outcome.selected_versions["gamma"] == Version(1, 5, 0)
        assert "omega" not in outcome.selected_versions
        assert all("omega" not in step for step in outcome.derivation_steps)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_exhausts_intermediate_candidates_before_retreat(self) -> None:
        alpha_old = PackageRelease("alpha", Version(1, 0, 0), (PackageDependency("gamma", VersionRange(">=1.0.0")),))
        alpha_new = PackageRelease("alpha", Version(2, 0, 0), (PackageDependency("beta", VersionRange(">=1.0.0")),))
        beta_old = PackageRelease("beta", Version(1, 0, 0), (PackageDependency("sigma", VersionRange(">=1.0.0")),))
        beta_new = PackageRelease("beta", Version(2, 0, 0), (PackageDependency("omega", VersionRange(">=1.0.0")),))
        gamma_only = PackageRelease("gamma", Version(1, 5, 0))
        self.sm.state.releases.extend([alpha_old, alpha_new, beta_old, beta_new, gamma_only])
        for release in (alpha_old, alpha_new, beta_old, beta_new, gamma_only):
            self.checked_packagerepository.register_package(release)
        roots = [
            PackageDependency("alpha", VersionRange(">=1.0.0")),
            PackageDependency("gamma", VersionRange(">=1.0.0")),
        ]
        self.sm.state.root_dependencies.extend(roots)
        outcome = self.checked_dependencysolver.resolve(roots)
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)
        assert outcome.selected_versions["gamma"] == Version(1, 5, 0)
        assert "beta" not in outcome.selected_versions
        assert "omega" not in outcome.selected_versions
        assert "sigma" not in outcome.selected_versions
        assert len(outcome.derivation_steps) > 0


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
    initial_state_factory=SemverSolverState,
    name="SemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T19:00:07Z
# LAST_CHANGED: 2026-11-03T18:59:11Z
# CHANGE: Add two resolution scenarios: (1) the highest-precedence candidate's only dead end is a transitive requirement on a package absent from the repository, so the search retreats to the lower candidate with the absent package absent from selected versions and derivation steps; (2) every candidate release of an intermediate package dead-ends on absent packages, exhausting that level before the search retreats to a lower-precedence root candidate and reports the successful assignment's versions and derivation steps.
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T19:00:07Z
# PRETENSE_QA_AUDIT: 2026-11-03T18:59:34Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver.

Models the SemVer 2.0 interface surface from ``low/semver_solver.pyi``:
``Version`` formatting/pre-release inspection, ``VersionEngine`` parsing and
precedence, ``PackageRepository`` registration and queries, and
``DependencySolver`` resolution. Model state tracks known versions, known
ranges, the candidate release pool, and the repository registrations observed
through the state machine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Set, Tuple, cast

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_2.parts.semver_solver.lib.semver_solver import ComparatorOp, Version, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome, VersionEngine, PackageRepository, DependencySolver


# ==============================================================================
# 0. SemVer Grammar and Model Helpers
# ==============================================================================

_PRERELEASE_IDENTIFIER = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_PRERELEASE_TEXT = r"-" + _PRERELEASE_IDENTIFIER + r"(?:\." + _PRERELEASE_IDENTIFIER + r")*"
_BUILD_TEXT = r"\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_BASE_VERSION_TEXT = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"

_SEMVER_PATTERN = (
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>" + _PRERELEASE_IDENTIFIER + r"(?:\." + _PRERELEASE_IDENTIFIER + r")*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_SEMVER_RE = re.compile(_SEMVER_PATTERN)

_RANGE_VERSION_TEXT = _BASE_VERSION_TEXT + r"(?:" + _PRERELEASE_TEXT + r")?(?:" + _BUILD_TEXT + r")?"
_WILDCARD_TEXT = r"(?:[xX*]|(?:0|[1-9][0-9]*)\.(?:[xX*]|(?:0|[1-9][0-9]*)\.(?:[xX*])))"
_COMPARATOR_TEXT = (
    r"(?:(?:\^|~)\s*" + _RANGE_VERSION_TEXT + r""
    r"|(?:==|=)?\s*(?:" + _RANGE_VERSION_TEXT + r"|" + _WILDCARD_TEXT + r")"
    r"|(?:!=|<=|>=|<|>)\s*" + _RANGE_VERSION_TEXT + r")"
)
_CLAUSE_TEXT = (
    r"(?:" + _RANGE_VERSION_TEXT + r"\s+-\s+" + _RANGE_VERSION_TEXT + r""
    r"|" + _COMPARATOR_TEXT + r"(?:\s+" + _COMPARATOR_TEXT + r")*)"
)
_RANGE_PATTERN = r"^\s*" + _CLAUSE_TEXT + r"(?:\s*\|\|\s*" + _CLAUSE_TEXT + r")*\s*$"

_RANGE_PATTERN_PREFERRED = [
    ">=1.0.0",
    "^1.2.0",
    "~1.2.3",
    "1.0.0 - 2.0.0",
    ">=1.0.0 <2.0.0",
    "1.2.x",
    "1.2.*",
    ">=1.0.0 || <0.5.0",
]


def _render_version(version: Version) -> str:
    """Renders a version record into canonical SemVer 2.0.0 text."""
    text = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        text = text + "-" + ".".join(version.prerelease)
    if version.build:
        text = text + "+" + ".".join(version.build)
    return text


def _parse_version_text(text: str) -> Version:
    """Parses valid SemVer text into a model ``Version`` record."""
    match = _SEMVER_RE.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"unparseable semantic version token: {text!r}")
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()
    if prerelease_text is not None:
        prerelease = tuple(prerelease_text.split("."))
    if build_text is not None:
        build = tuple(build_text.split("."))
    return Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
        build,
    )


def _compare_versions(v1: Version, v2: Version) -> int:
    """Compares two versions following SemVer 2.0.0 precedence rules."""
    if v1.major != v2.major:
        return -1 if v1.major < v2.major else 1
    if v1.minor != v2.minor:
        return -1 if v1.minor < v2.minor else 1
    if v1.patch != v2.patch:
        return -1 if v1.patch < v2.patch else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for left, right in zip(v1.prerelease, v2.prerelease):
        left_numeric = left.isdigit()
        right_numeric = right.isdigit()
        if left_numeric and right_numeric:
            left_value = int(left)
            right_value = int(right)
            if left_value != right_value:
                return -1 if left_value < right_value else 1
        elif left_numeric != right_numeric:
            return -1 if left_numeric else 1
        elif left != right:
            return -1 if left < right else 1
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


_COMPARATOR_OPERATORS = ("==", "!=", "<=", ">=", "=", "<", ">")


def _caret_upper(version: Version) -> Version:
    """Computes the exclusive upper bound of a caret range."""
    if version.major > 0:
        return Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return Version(0, version.minor + 1, 0)
    return Version(0, 0, version.patch + 1)


_WILDCARD_TOKENS = ("*", "x", "X")
_NUMERIC_COMPONENT_RE = re.compile(r"(?:0|[1-9][0-9]*)")


def _is_wildcard_expression(text: str) -> bool:
    """Indicates whether text is a wildcard version expression."""
    parts = text.split(".")
    if not parts:
        return False
    has_wildcard = False
    for part in parts:
        if part in _WILDCARD_TOKENS:
            has_wildcard = True
            continue
        if _NUMERIC_COMPONENT_RE.fullmatch(part) is None:
            return False
    return has_wildcard


def _wildcard_comparators(text: str) -> List[Tuple[str, Version]]:
    """Normalizes wildcard components into paired comparator inequalities."""
    parts = text.split(".")
    if not parts or parts[0] in _WILDCARD_TOKENS:
        return []
    major = int(parts[0])
    if len(parts) < 2 or parts[1] in _WILDCARD_TOKENS:
        return [(">=", Version(major, 0, 0)), ("<", Version(major + 1, 0, 0))]
    minor = int(parts[1])
    return [(">=", Version(major, minor, 0)), ("<", Version(major, minor + 1, 0))]


def _token_comparators(text: str) -> List[Tuple[str, Version]]:
    """Expands one whitespace-delimited comparator or prefix clause."""
    if text.startswith("^"):
        version = _parse_version_text(text[1:].strip())
        return [(">=", version), ("<", _caret_upper(version))]
    if text.startswith("~"):
        version = _parse_version_text(text[1:].strip())
        return [(">=", version), ("<", Version(version.major, version.minor + 1, 0))]
    operator = "=="
    remainder = text
    for candidate in _COMPARATOR_OPERATORS:
        if text.startswith(candidate):
            operator = "==" if candidate in ("==", "=") else candidate
            remainder = text[len(candidate):].strip()
            break
    if _is_wildcard_expression(remainder):
        return _wildcard_comparators(remainder)
    return [(operator, _parse_version_text(remainder))]


def _clause_comparators(clause: str) -> List[Tuple[str, Version]]:
    """Parses one union clause into its conjunctive comparator set."""
    tokens = clause.strip().split()
    if "-" in tokens:
        separator = tokens.index("-")
        lower_text = "".join(tokens[:separator])
        upper_text = "".join(tokens[separator + 1:])
        return [
            (">=", _parse_version_text(lower_text)),
            ("<=", _parse_version_text(upper_text)),
        ]
    comparators: List[Tuple[str, Version]] = []
    pending = ""
    for token in tokens:
        if token in _COMPARATOR_OPERATORS or token in ("^", "~"):
            pending = token
            continue
        comparators.extend(_token_comparators(pending + token))
        pending = ""
    return comparators


def _comparison_holds(version: Version, operator: str, boundary: Version) -> bool:
    """Evaluates one relational comparator against a candidate version."""
    result = _compare_versions(version, boundary)
    if operator == "==":
        return result == 0
    if operator == "!=":
        return result != 0
    if operator == "<":
        return result < 0
    if operator == "<=":
        return result <= 0
    if operator == ">":
        return result > 0
    if operator == ">=":
        return result >= 0
    return False


def _range_matches(version: Version, range_text: str, include_prerelease: bool) -> bool:
    """Evaluates a candidate version against a range expression."""
    clause_comparators = [_clause_comparators(clause) for clause in range_text.split("||")]
    targets_prerelease = any(
        boundary.prerelease and (boundary.major, boundary.minor, boundary.patch) == (version.major, version.minor, version.patch)
        for comparators in clause_comparators
        for _, boundary in comparators
    )
    if version.prerelease and not include_prerelease and not targets_prerelease:
        return False
    for comparators in clause_comparators:
        if all(_comparison_holds(version, operator, boundary) for operator, boundary in comparators):
            return True
    return False


def _build_version_state() -> List[Version]:
    """Builds the shared pool of model versions used by transition domains."""
    return [
        Version(0, 0, 3),
        Version(0, 0, 4),
        Version(0, 2, 3),
        Version(0, 2, 9),
        Version(0, 3, 0),
        Version(0, 5, 0),
        Version(1, 0, 0),
        Version(1, 0, 0, prerelease=("1",)),
        Version(1, 0, 0, prerelease=("alpha",)),
        Version(1, 0, 0, prerelease=("alpha", "1")),
        Version(1, 0, 0, prerelease=("beta",)),
        Version(1, 2, 3),
        Version(1, 2, 3, build=("build.1",)),
        Version(1, 2, 3, build=("build.5",)),
        Version(1, 2, 9),
        Version(1, 3, 0),
        Version(1, 5, 0),
        Version(1, 9, 9),
        Version(2, 0, 0),
        Version(2, 0, 0, prerelease=("rc", "1")),
        Version(2, 1, 0),
        Version(2, 1, 0, prerelease=("alpha",)),
    ]


def _build_range_state() -> List[VersionRange]:
    """Builds the shared pool of model ranges used by transition domains."""
    return [
        VersionRange(">=1.0.0"),
        VersionRange("^1.0.0"),
        VersionRange("1.0.0 - 2.0.0"),
    ]


def _build_release_state() -> List[PackageRelease]:
    """Builds the shared pool of release records used by transition domains."""
    return [
        PackageRelease("alpha", Version(1, 0, 0)),
        PackageRelease("alpha", Version(1, 2, 3)),
        PackageRelease("alpha", Version(1, 5, 0)),
        PackageRelease("alpha", Version(2, 0, 0)),
        PackageRelease("beta", Version(2, 0, 0)),
        PackageRelease("delta", Version(1, 0, 0)),
    ]


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    current_version: Version = field(default_factory=lambda: Version(1, 0, 0))
    known_versions: List[Version] = field(default_factory=_build_version_state)
    known_ranges: List[VersionRange] = field(default_factory=_build_range_state)
    releases: List[PackageRelease] = field(default_factory=_build_release_state)
    registered: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    root_dependencies: List[PackageDependency] = field(default_factory=list)
    last_outcome: Optional[ResolutionOutcome] = None


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        require(self.state.initialized)
        rendered = _render_version(self.state.current_version)
        ret: str = make_return_value(rendered)
        assert ret == rendered
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.regex(_SEMVER_PATTERN),
            preferred=["1.0.0", "2.1.3", "1.2.3-alpha.1+build.5"],
        )
        version = _parse_version_text(text)
        ret: Version = make_return_value(version)
        self.state.current_version = ret
        assert ret.major >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version), preferred=self.state.known_versions)
        require_arg(v2, Domain.type(Version), preferred=self.state.known_versions)
        expected = _compare_versions(v1, v2)
        ret: int = make_return_value(expected)
        self.state.current_version = v2 if expected < 0 else v1
        assert (ret < 0) == (expected < 0)
        assert (ret > 0) == (expected > 0)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.regex(_RANGE_PATTERN), preferred=_RANGE_PATTERN_PREFERRED)
        result = VersionRange(text.strip())
        ret: VersionRange = make_return_value(result)
        if ret not in self.state.known_ranges:
            self.state.known_ranges.append(ret)
        assert isinstance(ret.raw_text, str)
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.type(Version), preferred=self.state.known_versions)
        require_arg(
            range_constraint,
            Domain.object(VersionRange, raw_text=Domain.regex(_RANGE_PATTERN)),
            preferred=self.state.known_ranges,
        )
        require_arg(include_prerelease, Domain.type(bool))
        expected = _range_matches(version, range_constraint.raw_text, include_prerelease)
        ret: bool = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.type(PackageRelease), preferred=self.state.releases)
        bucket = self.state.registered.setdefault(release.name, [])
        bucket.append(release)
        ret = make_return_value()
        assert release.name in self.state.registered
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.in_set(self.state.registered.keys()))
        ret: List[PackageRelease] = make_return_value(list(self.state.registered[name]))
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["alpha", "beta", "delta"])
        expected = name in self.state.registered
        ret: bool = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        names = set(self.state.registered.keys())
        ret: Set[str] = make_return_value(names)
        assert ret == names
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            cast(Any, Domain.list_of(Domain.in_set(self.state.root_dependencies), min_size=0, max_size=3)),
        )
        selected: Dict[str, Version] = {}
        for dependency in root_dependencies:
            candidates = self.state.registered.get(dependency.name, [])
            if not candidates:
                continue
            best = candidates[0]
            for candidate in candidates[1:]:
                if _compare_versions(candidate.version, best.version) > 0:
                    best = candidate
            selected[dependency.name] = best.version
        steps = tuple(
            f"select {name}@{_render_version(version)}"
            for name, version in sorted(selected.items())
        )
        outcome = ResolutionOutcome(selected_versions=selected, derivation_steps=steps)
        ret: ResolutionOutcome = make_return_value(outcome)
        self.state.last_outcome = ret
        assert set(ret.selected_versions.keys()) == set(selected.keys())
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        expected = bool(self.state.current_version.prerelease)
        ret: bool = make_return_value(expected)
        assert ret == expected
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[ComparatorOp, Version, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome, VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeSemverSolver(state=state or SemverSolverState())
    return (
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
    )


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T18:51:36Z
# LAST_CHANGED: 2026-11-03T18:51:36Z
# CHANGE: Make the range evaluator whitespace-agnostic to match the admitted domain: hyphen separators are detected from Unicode-whitespace tokens, unparsable version tokens raise instead of coercing to 0.0.0, bare/major/two-component wildcards normalize without int-converting wildcard tokens, and satisfies compares its return by value against the expected model outcome.
# --- END AUTOFAB METADATA ---
