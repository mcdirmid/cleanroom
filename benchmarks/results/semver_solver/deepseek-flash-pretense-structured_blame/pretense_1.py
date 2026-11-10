# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

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
from benchmark_2.parts.semver_solver.pretense.semver_solver_pretense import (
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fake,
)
from benchmark_2.parts.semver_solver.lib.semver_solver import (
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
from benchmark_2.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.major >= 0 and ret.minor >= 0 and ret.patch >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        assert ret.raw_text == text.strip()
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
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert len(ret) >= 1
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert isinstance(ret, ResolutionOutcome)
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
        self.checked_versionengine = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_parse_version(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3-alpha.1+build.5")
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prerelease == ("alpha", "1")
        assert version.build == ("build", "5")
        assert version.is_prerelease

    def test_real_compare_precedence(self) -> None:
        alpha = self.checked_versionengine.parse_version("1.0.0-alpha")
        stable = self.checked_versionengine.parse_version("1.0.0")
        later = self.checked_versionengine.parse_version("1.1.0")
        assert self.checked_versionengine.compare_precedence(alpha, stable) < 0
        assert self.checked_versionengine.compare_precedence(stable, alpha) > 0
        assert self.checked_versionengine.compare_precedence(stable, stable) == 0
        assert self.checked_versionengine.compare_precedence(stable, later) < 0

    def test_real_parse_range(self) -> None:
        constraint = self.checked_versionengine.parse_range("  >=1.0.0 <2.0.0  ")
        assert constraint.raw_text == ">=1.0.0 <2.0.0"
        caret = self.checked_versionengine.parse_range("^1.2.3")
        assert caret.raw_text == "^1.2.3"
        alternative = self.checked_versionengine.parse_range("1.0.0 || 2.0.0")
        assert alternative.raw_text == "1.0.0 || 2.0.0"

    def test_real_satisfies(self) -> None:
        constraint = self.checked_versionengine.parse_range(">=1.0.0 <2.0.0")
        inside = self.checked_versionengine.parse_version("1.5.0")
        outside = self.checked_versionengine.parse_version("2.0.0")
        prerelease = self.checked_versionengine.parse_version("1.5.0-rc.1")
        assert self.checked_versionengine.satisfies(inside, constraint, False)
        assert not self.checked_versionengine.satisfies(outside, constraint, False)
        assert not self.checked_versionengine.satisfies(prerelease, constraint, False)
        assert self.checked_versionengine.satisfies(prerelease, constraint, True)

    def test_real_register_and_query(self) -> None:
        first = PackageRelease("alpha", self.checked_versionengine.parse_version("1.0.0"))
        second = PackageRelease("alpha", self.checked_versionengine.parse_version("2.0.0"))
        self.checked_packagerepository.register_package(first)
        self.checked_packagerepository.register_package(second)
        assert self.checked_packagerepository.has_package("alpha")
        assert "alpha" in self.checked_packagerepository.all_packages()
        releases = self.checked_packagerepository.get_releases("alpha")
        assert len(releases) == 2
        assert releases[0].version.major == 2
        assert releases[1].version.major == 1

    def test_real_resolve(self) -> None:
        release = PackageRelease("beta", self.checked_versionengine.parse_version("1.1.0"))
        self.checked_packagerepository.register_package(release)
        dependency = PackageDependency("beta", VersionRange(">=1.1.0"))
        outcome = self.checked_dependencysolver.resolve((dependency,))
        assert "beta" in outcome.selected_versions
        assert outcome.selected_versions["beta"].major == 1
        empty_outcome = self.checked_dependencysolver.resolve(())
        assert len(empty_outcome.selected_versions) == 0

    def test_real_patch_and_prerelease_ordering(self) -> None:
        patch_low = self.versionengine.parse_version("1.2.3")
        patch_high = self.versionengine.parse_version("1.2.10")
        assert self.versionengine.compare_precedence(patch_low, patch_high) < 0
        assert self.versionengine.compare_precedence(patch_high, patch_low) > 0
        assert self.versionengine.compare_precedence(patch_low, patch_low) == 0
        minor_low = self.versionengine.parse_version("1.2.0")
        minor_high = self.versionengine.parse_version("1.3.0")
        assert self.versionengine.compare_precedence(minor_low, minor_high) < 0
        numeric_first = self.versionengine.parse_version("1.0.0-alpha.1")
        numeric_second = self.versionengine.parse_version("1.0.0-alpha.2")
        assert self.versionengine.compare_precedence(numeric_first, numeric_second) < 0
        numeric_identifier = self.versionengine.parse_version("1.0.0-alpha.1")
        string_identifier = self.versionengine.parse_version("1.0.0-alpha.beta")
        assert self.versionengine.compare_precedence(numeric_identifier, string_identifier) < 0
        short_prefix = self.versionengine.parse_version("1.0.0-alpha")
        long_prefix = self.versionengine.parse_version("1.0.0-alpha.1")
        string_alpha = self.versionengine.parse_version("1.0.0-alpha")
        string_beta = self.versionengine.parse_version("1.0.0-beta")
        assert self.versionengine.compare_precedence(string_alpha, string_beta) < 0
        numeric_rank = self.versionengine.parse_version("1.0.0-1")
        alphanumeric_rank = self.versionengine.parse_version("1.0.0-alpha")
        assert self.versionengine.compare_precedence(numeric_rank, alphanumeric_rank) < 0
        assert self.versionengine.compare_precedence(alphanumeric_rank, numeric_rank) > 0
        assert self.versionengine.compare_precedence(short_prefix, long_prefix) < 0
        normal = self.versionengine.parse_version("1.0.0")
        assert self.versionengine.compare_precedence(string_alpha, normal) < 0
        build_one = self.versionengine.parse_version("1.0.0+build.1")
        build_two = self.versionengine.parse_version("1.0.0+build.2")
        assert self.versionengine.compare_precedence(build_one, build_two) == 0

    def test_real_caret_and_tilde_boundaries(self) -> None:
        caret_full = self.versionengine.parse_range("^1.2.3")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.3"), caret_full, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.9.9"), caret_full, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.2.2"), caret_full, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), caret_full, False)
        caret_wildcard = self.versionengine.parse_range("^1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), caret_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.9.0"), caret_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), caret_wildcard, False)
        tilde_full = self.versionengine.parse_range("~1.2.3")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.3"), tilde_full, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.9"), tilde_full, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.3.0"), tilde_full, False)
        tilde_wildcard = self.versionengine.parse_range("~1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.5.0"), tilde_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), tilde_wildcard, False)
        caret_zero_major_wildcard = self.versionengine.parse_range("^0.1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.1.0"), caret_zero_major_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.1.9"), caret_zero_major_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.0.9"), caret_zero_major_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.2.0"), caret_zero_major_wildcard, False)
        tilde_component_wildcard = self.versionengine.parse_range("~1.2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.0"), tilde_component_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.9"), tilde_component_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.1.9"), tilde_component_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.3.0"), tilde_component_wildcard, False)

    def test_real_two_component_wildcard_bounds(self) -> None:
        patch_wildcard = self.versionengine.parse_range("1.2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.0"), patch_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.9"), patch_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.1.9"), patch_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.3.0"), patch_wildcard, False)
        ge_patch_wildcard = self.versionengine.parse_range(">=1.2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.0"), ge_patch_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), ge_patch_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.1.9"), ge_patch_wildcard, False)
        gt_patch_wildcard = self.versionengine.parse_range(">1.2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.3.0"), gt_patch_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.2.9"), gt_patch_wildcard, False)
        lt_patch_wildcard = self.versionengine.parse_range("<1.2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.1.9"), lt_patch_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.2.0"), lt_patch_wildcard, False)
        le_patch_wildcard = self.versionengine.parse_range("<=1.2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.9"), le_patch_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.3.0"), le_patch_wildcard, False)
        ne_patch_wildcard = self.versionengine.parse_range("!=1.2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.1.9"), ne_patch_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.2.5"), ne_patch_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.3.0"), ne_patch_wildcard, False)

    def test_real_wildcard_and_union_ranges(self) -> None:
        ge_wildcard = self.versionengine.parse_range(">=1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), ge_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.9.9"), ge_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.9.0"), ge_wildcard, False)
        ne_wildcard = self.versionengine.parse_range("!=1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.9.0"), ne_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.5.0"), ne_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), ne_wildcard, False)
        any_range = self.versionengine.parse_range(">=*")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.0.1"), any_range, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("7.5.9"), any_range, False)
        union = self.versionengine.parse_range("1.0.0 || 2.0.0")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), union, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), union, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.5.0"), union, False)

    def test_real_hyphen_range_bounds(self) -> None:
        hyphen_full = self.versionengine.parse_range("1.0.0 - 2.0.0")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), hyphen_full, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), hyphen_full, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), hyphen_full, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.0.1"), hyphen_full, False)
        hyphen_upper_wildcard = self.versionengine.parse_range("1.0.0 - 2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), hyphen_upper_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.5.0"), hyphen_upper_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("3.0.0"), hyphen_upper_wildcard, False)
        hyphen_both_wildcards = self.versionengine.parse_range("1.x - 2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.5.0"), hyphen_both_wildcards, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.5.0"), hyphen_both_wildcards, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.9.0"), hyphen_both_wildcards, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("3.0.0"), hyphen_both_wildcards, False)

    def test_real_comparator_and_wildcard_boundaries(self) -> None:
        not_equal = self.versionengine.parse_range("!=1.0.0")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.1"), not_equal, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), not_equal, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), not_equal, False)
        at_most = self.versionengine.parse_range("<=1.0.0")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), at_most, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), at_most, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.0.1"), at_most, False)
        greater_than = self.versionengine.parse_range(">1.0.0")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.1"), greater_than, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), greater_than, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), greater_than, False)
        bare_wildcard = self.versionengine.parse_range("1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), bare_wildcard, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.9.9"), bare_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), bare_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), bare_wildcard, False)
        exclusive_lower_wildcard = self.versionengine.parse_range(">1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), exclusive_lower_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.9.9"), exclusive_lower_wildcard, False)
        exclusive_upper_wildcard = self.versionengine.parse_range("<1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), exclusive_upper_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), exclusive_upper_wildcard, False)
        inclusive_upper_wildcard = self.versionengine.parse_range("<=1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.9.9"), inclusive_upper_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), inclusive_upper_wildcard, False)
        impossible_relational = self.versionengine.parse_range(">*")
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.0.1"), impossible_relational, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("9.9.9"), impossible_relational, False)
        impossible_negation = self.versionengine.parse_range("!=*")
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.0.1"), impossible_negation, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("9.9.9"), impossible_negation, False)
        caret_zero_minor = self.versionengine.parse_range("^0.1.2")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.1.2"), caret_zero_minor, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.1.9"), caret_zero_minor, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.2.0"), caret_zero_minor, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.1.1"), caret_zero_minor, False)
        caret_zero_patch = self.versionengine.parse_range("^0.0.3")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.0.3"), caret_zero_patch, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.0.4"), caret_zero_patch, False)
        hyphen_wildcard_lower = self.versionengine.parse_range("x - 2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.0.0"), hyphen_wildcard_lower, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.9.9"), hyphen_wildcard_lower, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("3.0.0"), hyphen_wildcard_lower, False)

    def test_real_operator_whitespace_equivalence(self) -> None:
        spaced = self.versionengine.parse_range(">= 1.0.0")
        tight = self.versionengine.parse_range(">=1.0.0")
        for text in ("0.9.0", "1.0.0", "1.5.0", "2.0.0"):
            version = self.versionengine.parse_version(text)
            assert self.versionengine.satisfies(version, spaced, False) == self.versionengine.satisfies(version, tight, False)

    def test_real_prerelease_range_filtering(self) -> None:
        plain_range = self.versionengine.parse_range(">=1.0.0")
        prerelease = self.versionengine.parse_version("1.5.0-rc.1")
        assert not self.versionengine.satisfies(prerelease, plain_range, False)
        assert self.versionengine.satisfies(prerelease, plain_range, True)
        explicit_range = self.versionengine.parse_range(">=1.5.0-rc.1")
        assert self.versionengine.satisfies(prerelease, explicit_range, False)
        other_prerelease = self.versionengine.parse_version("1.6.0-rc.1")
        assert not self.versionengine.satisfies(other_prerelease, explicit_range, False)

    def test_real_invalid_version_errors(self) -> None:
        self.assertRaises(InvalidVersionError, self.versionengine.parse_version, "01.2.3")
        self.assertRaises(InvalidVersionError, self.versionengine.parse_version, "1.02.3")
        self.assertRaises(InvalidVersionError, self.versionengine.parse_version, "1.2.03")
        self.assertRaises(InvalidVersionError, self.versionengine.parse_version, "1.2")
        self.assertRaises(InvalidVersionError, self.versionengine.parse_version, "1.2.3-")
        self.assertRaises(InvalidVersionError, self.versionengine.parse_version, "1.2.3-01")
        self.assertRaises(InvalidVersionError, self.versionengine.parse_version, "not-a-version")
        self.assertRaises(InvalidVersionError, self.versionengine.parse_version, "")

    def test_real_invalid_range_errors(self) -> None:
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "   ")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "1")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "1.2")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, ">1.2")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "^0.0")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "1.2 - 2.3")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, ">=1.0.0, <2.0.0")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "1.0.0 ||")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "|| 1.0.0")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "1.2.3.4")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "1.x.2")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "1.zz")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, "1.02.x")
        self.assertRaises(InvalidRangeError, self.versionengine.parse_range, ">=")

    def test_real_missing_package_error(self) -> None:
        assert not self.packagerepository.has_package("absent")
        assert self.packagerepository.all_packages() == set()
        self.assertRaises(PackageNotFoundError, self.packagerepository.get_releases, "absent")

    def test_real_resolution_conflict_errors(self) -> None:
        self.packagerepository.register_package(PackageRelease("core", self.versionengine.parse_version("2.0.0")))
        self.assertRaises(
            ResolutionConflictError,
            self.dependencysolver.resolve,
            [PackageDependency("core", VersionRange(">=1.0.0")), PackageDependency("core", VersionRange("<2.0.0"))],
        )
        self.assertRaises(
            ResolutionConflictError,
            self.dependencysolver.resolve,
            [PackageDependency("absent", VersionRange(">=1.0.0"))],
        )

    def test_real_transitive_resolution(self) -> None:
        self.packagerepository.register_package(PackageRelease("core", self.versionengine.parse_version("1.4.0")))
        self.packagerepository.register_package(
            PackageRelease(
                "lib",
                self.versionengine.parse_version("1.0.0"),
                (PackageDependency("core", VersionRange(">=1.0.0")),),
            )
        )
        self.packagerepository.register_package(
            PackageRelease(
                "app",
                self.versionengine.parse_version("1.0.0"),
                (PackageDependency("lib", VersionRange(">=1.0.0")),),
            )
        )
        outcome = self.dependencysolver.resolve((PackageDependency("app", VersionRange(">=1.0.0")),))
        assert outcome.selected_versions["app"] == Version(1, 0, 0)
        assert outcome.selected_versions["lib"] == Version(1, 0, 0)
        assert outcome.selected_versions["core"] == Version(1, 4, 0)

    def test_real_transitive_backtracking_resolution(self) -> None:
        self.packagerepository.register_package(PackageRelease("core", self.versionengine.parse_version("1.0.0")))
        self.packagerepository.register_package(
            PackageRelease(
                "lib",
                self.versionengine.parse_version("2.0.0"),
                (PackageDependency("core", VersionRange(">=2.0.0")),),
            )
        )
        self.packagerepository.register_package(
            PackageRelease(
                "lib",
                self.versionengine.parse_version("1.0.0"),
                (PackageDependency("core", VersionRange(">=1.0.0")),),
            )
        )
        self.packagerepository.register_package(
            PackageRelease(
                "app",
                self.versionengine.parse_version("1.0.0"),
                (PackageDependency("lib", VersionRange(">=1.0.0")),),
            )
        )
        outcome = self.dependencysolver.resolve((PackageDependency("app", VersionRange(">=1.0.0")),))
        assert set(outcome.selected_versions.keys()) == {"app", "lib", "core"}
        assert outcome.selected_versions["app"] == Version(1, 0, 0)
        assert outcome.selected_versions["lib"] == Version(1, 0, 0)
        assert outcome.selected_versions["core"] == Version(1, 0, 0)

    def test_real_forward_checking_conflict(self) -> None:
        self.packagerepository.register_package(PackageRelease("a", self.versionengine.parse_version("1.0.0")))
        self.packagerepository.register_package(
            PackageRelease(
                "b",
                self.versionengine.parse_version("1.0.0"),
                (PackageDependency("a", VersionRange(">=2.0.0")),),
            )
        )
        with self.assertRaises(ResolutionConflictError) as conflict:
            self.dependencysolver.resolve(
                (
                    PackageDependency("a", VersionRange("==1.0.0")),
                    PackageDependency("b", VersionRange("==1.0.0")),
                )
            )
        error = conflict.exception
        assert isinstance(error, ResolutionConflictError)
        assert len(error.conflicting_packages) > 0
        assert len(error.explanation) > 0
        assert "a" in error.conflicting_packages or "b" in error.conflicting_packages

    def test_real_compatible_forward_checking_resolution(self) -> None:
        self.packagerepository.register_package(PackageRelease("a", self.versionengine.parse_version("1.0.0")))
        self.packagerepository.register_package(
            PackageRelease(
                "b",
                self.versionengine.parse_version("1.0.0"),
                (PackageDependency("a", VersionRange(">=1.0.0")),),
            )
        )
        outcome = self.dependencysolver.resolve(
            (
                PackageDependency("a", VersionRange("==1.0.0")),
                PackageDependency("b", VersionRange("==1.0.0")),
            )
        )
        assert set(outcome.selected_versions.keys()) == {"a", "b"}
        assert outcome.selected_versions["a"] == Version(1, 0, 0)
        assert outcome.selected_versions["b"] == Version(1, 0, 0)

    def test_real_nested_search_exhaustion_conflict(self) -> None:
        self.packagerepository.register_package(PackageRelease("b", self.versionengine.parse_version("1.0.0")))
        self.packagerepository.register_package(
            PackageRelease(
                "a",
                self.versionengine.parse_version("2.0.0"),
                (PackageDependency("b", VersionRange(">=2.0.0")),),
            )
        )
        self.packagerepository.register_package(
            PackageRelease(
                "a",
                self.versionengine.parse_version("1.0.0"),
                (PackageDependency("b", VersionRange(">=2.0.0")),),
            )
        )
        with self.assertRaises(ResolutionConflictError) as conflict:
            self.dependencysolver.resolve((PackageDependency("a", VersionRange(">=1.0.0")),))
        error = conflict.exception
        assert isinstance(error, ResolutionConflictError)
        assert len(error.conflicting_packages) > 0
        assert len(error.explanation) > 0
        assert "a" in error.conflicting_packages or "b" in error.conflicting_packages


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
# LAST_CLEANED: 2026-11-08T17:25:06Z
# LAST_CHANGED: 2026-11-08T17:24:28Z
# CHANGE: Address fifth coverage round: add the accepting side of forward checking as a deterministic scenario. Target a 1.0.0 has no dependencies and dependent b 1.0.0 requires a>=1.0.0; roots a==1.0.0 and b==1.0.0 assign a first (MRV plus lexical tie-break), then b is selected, its declared range on the already assigned a is merged and satisfies the assignment, and the search continues to a complete mutually compatible outcome selecting a 1.0.0 and b 1.0.0.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:25:06Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:24:45Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

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
from benchmark_2.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)


# ==============================================================================
# Shared Domain Samples
# ==============================================================================

SAMPLE_VERSION_TEXTS: Tuple[str, ...] = (
    "0.1.0",
    "1.0.0",
    "1.1.0",
    "1.2.3",
    "1.5.0",
    "2.0.0",
    "1.0.0-alpha",
    "1.5.0-rc.1",
    "2.0.0-alpha.1",
    "1.2.3+build.5",
    "1.0.0-rc.1+build.2",
    "1.2.3-alpha.1+build.5",
)

SAMPLE_RANGE_TEXTS: Tuple[str, ...] = (
    "1.0.0",
    ">=1.0.0",
    ">=1.0.0 <2.0.0",
    "  >=1.0.0 <2.0.0  ",
    "1.0.0 - 2.0.0",
    "^1.2.3",
    "~1.2.3",
    ">=1.x",
    "!=1.x",
    "1.0.0 || 2.0.0",
    ">=*",
)

SAMPLE_VERSIONS: Tuple[Version, ...] = (
    Version(0, 1, 0),
    Version(1, 0, 0),
    Version(1, 1, 0),
    Version(1, 2, 3),
    Version(1, 5, 0),
    Version(2, 0, 0),
    Version(1, 0, 0, ("alpha",)),
    Version(1, 5, 0, ("rc", "1")),
    Version(2, 0, 0, ("alpha", "1")),
    Version(1, 2, 3, (), ("build", "5")),
    Version(1, 0, 0, ("rc", "1"), ("build", "2")),
    Version(1, 2, 3, ("alpha", "1"), ("build", "5")),
)

SAMPLE_RANGES: Tuple[VersionRange, ...] = tuple(VersionRange(raw) for raw in SAMPLE_RANGE_TEXTS)

SAMPLE_RELEASES: Tuple[PackageRelease, ...] = (
    PackageRelease("alpha", Version(1, 0, 0)),
    PackageRelease("alpha", Version(2, 0, 0)),
    PackageRelease("beta", Version(1, 1, 0)),
    PackageRelease("gamma", Version(0, 3, 1)),
)


def _release_key(release: PackageRelease) -> Tuple[int, int, int]:
    """Orders package releases by numeric version components."""
    return (release.version.major, release.version.minor, release.version.patch)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    engine_ready: bool = False
    parsed_versions: List[Version] = field(default_factory=list)
    parsed_ranges: List[VersionRange] = field(default_factory=list)
    registered: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    resolutions: List[ResolutionOutcome] = field(default_factory=list)
    dependency_options: List[Tuple[PackageDependency, ...]] = field(default_factory=list)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require_arg(text, Domain.sampled_from(SAMPLE_VERSION_TEXTS))
        parsed = Version(major=0, minor=0, patch=0)
        ret: Version = make_return_value(parsed)
        self.state.parsed_versions.append(ret)
        assert len(self.state.parsed_versions) > 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(v1, Domain.sampled_from(SAMPLE_VERSIONS))
        require_arg(v2, Domain.sampled_from(SAMPLE_VERSIONS))
        ret: int = make_return_value(0)
        assert isinstance(ret, int)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require_arg(text, Domain.sampled_from(SAMPLE_RANGE_TEXTS))
        parsed = VersionRange(raw_text=text.strip())
        ret: VersionRange = make_return_value(parsed)
        self.state.parsed_ranges.append(ret)
        assert ret.raw_text == text.strip()
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(version, Domain.sampled_from(SAMPLE_VERSIONS))
        require_arg(range_constraint, Domain.sampled_from(SAMPLE_RANGES))
        require_arg(include_prerelease, Domain.boolean())
        ret: bool = make_return_value(False)
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(release, Domain.sampled_from(SAMPLE_RELEASES))
        ret = make_return_value(None)
        self.state.registered.setdefault(release.name, []).append(release)
        no_dependencies: Tuple[PackageDependency, ...] = ()
        if no_dependencies not in self.state.dependency_options:
            self.state.dependency_options.append(no_dependencies)
        constraint = VersionRange(
            f">={release.version.major}.{release.version.minor}.{release.version.patch}"
        )
        self.state.dependency_options.append((PackageDependency(release.name, constraint),))
        assert release.name in self.state.registered
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(len(self.state.registered) > 0)
        require_arg(name, Domain.in_set(self.state.registered.keys()))
        ordered = sorted(self.state.registered[name], key=_release_key, reverse=True)
        ret: List[PackageRelease] = make_return_value(ordered)
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(name, Domain.type(str), preferred=["alpha", "beta"])
        ret: bool = make_return_value(name in self.state.registered)
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        ret: Set[str] = make_return_value(set(self.state.registered.keys()))
        assert ret == set(self.state.registered.keys())
        return ret

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        require(len(self.state.registered) > 0)
        require_arg(root_dependencies, Domain.in_set(self.state.dependency_options))
        resolved = ResolutionOutcome(
            selected_versions={},
            derivation_steps=(),
        )
        ret: ResolutionOutcome = make_return_value(resolved)
        self.state.resolutions.append(ret)
        assert isinstance(ret, ResolutionOutcome)
        return ret

    @transition.seeding
    def seed_engine_ready(self) -> None:
        """Seeds the model engine readiness flag for blank initial states."""
        self.state.engine_ready = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(
    state: Optional[SemverSolverState] = None,
) -> Any:
    """Builds a synthesized fake double sharing the model state."""
    return FakeSemverSolver(state=state or SemverSolverState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies the synthesized fake double across every declared transition."""

    def setUp(self) -> None:
        self.fake = make_semver_solver_fake()
        self.sm = SemverSolverStateMachine()

    def test_seeding_transition(self) -> None:
        self.sm.seed_engine_ready()

    def test_parse_version(self) -> None:
        version = self.fake.parse_version("1.2.3")
        assert version is not None

    def test_compare_precedence(self) -> None:
        comparison = self.fake.compare_precedence(SAMPLE_VERSIONS[0], SAMPLE_VERSIONS[1])
        assert isinstance(comparison, int)

    def test_parse_range(self) -> None:
        constraint = self.fake.parse_range(">=1.0.0")
        assert constraint is not None

    def test_satisfies(self) -> None:
        matched = self.fake.satisfies(SAMPLE_VERSIONS[0], SAMPLE_RANGES[1], True)
        assert isinstance(matched, bool)

    def test_register_package(self) -> None:
        self.fake.register_package(SAMPLE_RELEASES[0])
        assert self.fake.has_package("alpha")

    def test_get_releases(self) -> None:
        self.fake.register_package(SAMPLE_RELEASES[2])
        releases = self.fake.get_releases("beta")
        assert len(releases) >= 1

    def test_has_package(self) -> None:
        assert not self.fake.has_package("delta")

    def test_all_packages(self) -> None:
        self.fake.register_package(SAMPLE_RELEASES[0])
        names = self.fake.all_packages()
        assert "alpha" in names

    def test_resolve(self) -> None:
        self.fake.register_package(SAMPLE_RELEASES[0])
        outcome = self.fake.resolve(())
        assert outcome is not None


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:12:05Z
# LAST_CHANGED: 2026-11-08T17:12:05Z
# CHANGE: Resolve feedback: replace the transition-local candidates list (unresolvable by Pretense domain evaluation) with a state-derived argument domain. Model state now tracks dependency_options as a list of resolvable root-dependency sets; register_package appends the empty set and a satisfiable single-package constraint for each registered release, and resolve gates root_dependencies via Domain.in_set(self.state.dependency_options), so fuzz generation resolves the domain at generation time, never raises NameError, and only offers dependency sets whose packages exist in the repository mirror.
# --- END AUTOFAB METADATA ---
