# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, List, Set
import unittest

from pretense import (
    call_target,
    sut,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.semver_solver.pretense.semver_solver_pretense import (
    CANONICAL_RELEASES,
    CANONICAL_RANGES,
    CANONICAL_VERSIONS,
    ROOT_DEPENDENCY_SETS,
    VALID_RANGE_TEXTS,
    VALID_VERSION_TEXTS,
    SemverSolverState,
    SemverSolverStateMachine,
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
# Pseudo-state machine transitions override the interface transitions that require
# observing the concrete SUT.  Model preconditions and model state mutations are
# executed automatically by the inherited interface transition; overrides only
# define the call_target AST pivot and postcondition assertions.


class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        if v1 == v2:
            assert ret == 0
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
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
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert target.has_package(release.name)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert isinstance(ret.selected_versions, dict)
        return ret

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        target: Version = sut(Version)
        ret = call_target(target.format())
        assert isinstance(ret, str)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        target: Version = sut(Version)
        ret = call_target(target.is_prerelease)
        assert isinstance(ret, bool)
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
        self.version = CANONICAL_VERSIONS[0]
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
                Version: self.version,
            }
        )
        self.checked_versionengine = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)
        self.checked_version = self.sm.as_checked(Version, self.version)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_version_engine_conformance(self) -> None:
        released = self.checked_versionengine.parse_version(VALID_VERSION_TEXTS[1])
        assert (released.major, released.minor, released.patch) == (1, 2, 3)
        assert released.prerelease == ()
        assert released.build == ()
        assert released.format() == "1.2.3"
        assert str(released) == "1.2.3"
        assert not released.is_prerelease
        prerelease = self.checked_versionengine.parse_version(VALID_VERSION_TEXTS[3])
        assert prerelease.prerelease == ("alpha", "1")
        assert prerelease.build == ("build", "5")
        assert prerelease.format() == "2.0.0-alpha.1+build.5"
        assert prerelease.is_prerelease
        assert self.checked_version.format() == "0.0.0"
        assert self.checked_versionengine.compare_precedence(CANONICAL_VERSIONS[5], CANONICAL_VERSIONS[2]) > 0
        assert self.checked_versionengine.compare_precedence(CANONICAL_VERSIONS[2], CANONICAL_VERSIONS[5]) < 0
        later = self.checked_versionengine.parse_version(VALID_VERSION_TEXTS[4])
        assert self.checked_versionengine.compare_precedence(released, later) < 0
        assert self.checked_versionengine.compare_precedence(later, released) > 0
        assert self.checked_versionengine.compare_precedence(released, released) == 0
        assert self.checked_versionengine.compare_precedence(released, prerelease) < 0
        caret = self.checked_versionengine.parse_range(VALID_RANGE_TEXTS[1])
        assert caret.raw_text == VALID_RANGE_TEXTS[1]
        assert self.checked_versionengine.satisfies(CANONICAL_VERSIONS[1], caret, False)
        assert not self.checked_versionengine.satisfies(CANONICAL_VERSIONS[4], caret, False)
        assert not self.checked_versionengine.satisfies(CANONICAL_VERSIONS[5], caret, False)
        wide = self.checked_versionengine.parse_range(VALID_RANGE_TEXTS[0])
        assert self.checked_versionengine.satisfies(CANONICAL_VERSIONS[2], wide, True)
        assert not self.checked_versionengine.satisfies(CANONICAL_VERSIONS[2], wide, False)
        assert self.checked_versionengine.satisfies(CANONICAL_VERSIONS[0], CANONICAL_RANGES[2], False)
        assert self.checked_versionengine.satisfies(CANONICAL_VERSIONS[1], CANONICAL_RANGES[2], False)
        assert not self.checked_versionengine.satisfies(CANONICAL_VERSIONS[2], CANONICAL_RANGES[2], False)
        assert self.checked_versionengine.satisfies(CANONICAL_VERSIONS[2], CANONICAL_RANGES[2], True)

    def test_repository_conformance(self) -> None:
        assert not self.checked_packagerepository.has_package("alpha")
        assert self.checked_packagerepository.all_packages() == set()
        self.checked_packagerepository.register_package(CANONICAL_RELEASES[0])
        self.checked_packagerepository.register_package(CANONICAL_RELEASES[1])
        self.checked_packagerepository.register_package(CANONICAL_RELEASES[2])
        assert self.checked_packagerepository.has_package("alpha")
        assert self.checked_packagerepository.has_package("beta")
        assert not self.checked_packagerepository.has_package("gamma")
        assert self.checked_packagerepository.all_packages() == {"alpha", "beta"}
        alpha_releases = self.checked_packagerepository.get_releases("alpha")
        assert len(alpha_releases) == 2
        assert alpha_releases[0].version == CANONICAL_RELEASES[1].version
        assert alpha_releases[1].version == CANONICAL_RELEASES[0].version
        beta_releases = self.checked_packagerepository.get_releases("beta")
        assert len(beta_releases) == 1
        assert beta_releases[0].name == "beta"

    def test_solver_conformance(self) -> None:
        self.checked_packagerepository.register_package(CANONICAL_RELEASES[0])
        self.checked_packagerepository.register_package(CANONICAL_RELEASES[1])
        self.checked_packagerepository.register_package(CANONICAL_RELEASES[2])
        empty_outcome = self.checked_dependencysolver.resolve(ROOT_DEPENDENCY_SETS[0])
        assert empty_outcome.selected_versions == {}
        single_outcome = self.checked_dependencysolver.resolve(ROOT_DEPENDENCY_SETS[1])
        assert single_outcome.selected_versions["alpha"] == CANONICAL_RELEASES[1].version
        assert single_outcome.derivation_steps == ("Assign 'alpha' to 2.0.0",)
        pair_outcome = self.checked_dependencysolver.resolve(ROOT_DEPENDENCY_SETS[2])
        assert pair_outcome.selected_versions["alpha"] == CANONICAL_RELEASES[1].version
        assert pair_outcome.selected_versions["beta"] == CANONICAL_RELEASES[2].version
        assert pair_outcome.derivation_steps == (
            "Assign 'beta' to 1.2.3",
            "Assign 'alpha' to 2.0.0",
        )

    def test_range_parser_contract(self) -> None:
        for accepted_range in (
            "^1.2.3",
            "^0.2.3",
            "^0.0.3",
            "~1.2.0",
            "*",
            "1.x",
            "1.*",
            "1.2.x",
            "1.2.3 - 2.3.4",
            "1.x || >=2.5.0",
            "!=1.x",
            ">1.x",
            ">=1.x",
            "<1.x",
            "1.x - 2.x",
            "1.2.x - 1.4.x",
            ">=*",
            ">*",
            "<*",
            "<=*",
            "!=*",
            "1.2.3 - *",
            ">= 1.0.0",
            "<= 2.0.0",
            "=1.2.3",
            "!=1.2.3",
            "  >=1.0.0 <2.0.0  ",
        ):
            parsed = self.versionengine.parse_range(accepted_range)
            assert parsed.raw_text == accepted_range.strip()

    def test_satisfies_comparator_contract(self) -> None:
        released = self.versionengine.parse_version("1.2.3")
        greater = self.versionengine.parse_version("1.2.4")
        lesser = self.versionengine.parse_version("1.2.2")
        equality = self.versionengine.parse_range("=1.2.3")
        inequality = self.versionengine.parse_range("!=1.2.3")
        at_most = self.versionengine.parse_range("<=1.2.3")
        above = self.versionengine.parse_range(">1.2.3")
        at_least = self.versionengine.parse_range(">=1.2.3")
        assert self.versionengine.satisfies(released, equality, False)
        assert not self.versionengine.satisfies(greater, equality, False)
        assert not self.versionengine.satisfies(released, inequality, False)
        assert self.versionengine.satisfies(greater, inequality, False)
        assert self.versionengine.satisfies(released, at_most, False)
        assert not self.versionengine.satisfies(greater, at_most, False)
        assert self.versionengine.satisfies(greater, above, False)
        assert not self.versionengine.satisfies(released, above, False)
        assert self.versionengine.satisfies(released, at_least, False)
        assert not self.versionengine.satisfies(lesser, at_least, False)

    def test_satisfies_expansion_contract(self) -> None:
        caret = self.versionengine.parse_range("^1.2.3")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.9.9"), caret, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), caret, False)
        zero_minor_caret = self.versionengine.parse_range("^0.2.3")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.2.9"), zero_minor_caret, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.3.0"), zero_minor_caret, False)
        zero_patch_caret = self.versionengine.parse_range("^0.0.3")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.0.3"), zero_patch_caret, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.0.4"), zero_patch_caret, False)
        tilde = self.versionengine.parse_range("~1.2.0")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.9"), tilde, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.3.0"), tilde, False)
        major_wildcard = self.versionengine.parse_range("1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.9.9"), major_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), major_wildcard, False)
        minor_wildcard = self.versionengine.parse_range("1.2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.9"), minor_wildcard, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.3.0"), minor_wildcard, False)
        hyphen = self.versionengine.parse_range("1.2.3 - 2.3.4")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.3"), hyphen, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.3.4"), hyphen, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.3.5"), hyphen, False)
        union = self.versionengine.parse_range("1.x || >=2.5.0")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.5.0"), union, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.6.0"), union, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("2.4.0"), union, False)
        spaced = self.versionengine.parse_range(">= 1.0.0")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), spaced, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.9.0"), spaced, False)

    def test_satisfies_wildcard_comparator_contract(self) -> None:
        negated = self.versionengine.parse_range("!=1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), negated, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), negated, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), negated, False)
        above = self.versionengine.parse_range(">1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), above, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.9.9"), above, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), above, False)
        at_least = self.versionengine.parse_range(">=1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), at_least, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.5.0"), at_least, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), at_least, False)
        below = self.versionengine.parse_range("<1.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), below, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), below, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.5.0"), below, False)

    def test_satisfies_any_wildcard_comparator_contract(self) -> None:
        baseline = self.versionengine.parse_version("0.0.0")
        released = self.versionengine.parse_version("1.5.0")
        any_at_least = self.versionengine.parse_range(">=*")
        assert self.versionengine.satisfies(baseline, any_at_least, False)
        assert self.versionengine.satisfies(released, any_at_least, False)
        any_above = self.versionengine.parse_range(">*")
        assert not self.versionengine.satisfies(baseline, any_above, False)
        any_below = self.versionengine.parse_range("<*")
        assert not self.versionengine.satisfies(baseline, any_below, False)
        assert not self.versionengine.satisfies(released, any_below, False)
        any_at_most = self.versionengine.parse_range("<=*")
        assert self.versionengine.satisfies(baseline, any_at_most, False)
        any_not = self.versionengine.parse_range("!=*")
        assert not self.versionengine.satisfies(baseline, any_not, False)
        assert not self.versionengine.satisfies(released, any_not, False)

    def test_satisfies_wildcard_hyphen_contract(self) -> None:
        span = self.versionengine.parse_range("1.x - 2.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.0.0"), span, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.5.0"), span, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("2.0.0"), span, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("0.9.9"), span, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("3.0.0"), span, False)
        narrow = self.versionengine.parse_range("1.2.x - 1.4.x")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.0"), narrow, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.3.5"), narrow, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.1.0"), narrow, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.5.0"), narrow, False)
        unbounded = self.versionengine.parse_range("1.2.3 - *")
        assert self.versionengine.satisfies(self.versionengine.parse_version("1.2.3"), unbounded, False)
        assert self.versionengine.satisfies(self.versionengine.parse_version("5.0.0"), unbounded, False)
        assert not self.versionengine.satisfies(self.versionengine.parse_version("1.2.2"), unbounded, False)

    def test_precedence_prerelease_contract(self) -> None:
        numeric = self.versionengine.parse_version("1.0.0-2")
        textual = self.versionengine.parse_version("1.0.0-alpha")
        extended = self.versionengine.parse_version("1.0.0-alpha.1")
        assert self.checked_versionengine.compare_precedence(numeric, textual) < 0
        assert self.checked_versionengine.compare_precedence(textual, extended) < 0
        assert self.checked_versionengine.compare_precedence(numeric, extended) < 0
        assert self.checked_versionengine.compare_precedence(textual, numeric) > 0
        assert self.checked_versionengine.compare_precedence(extended, textual) > 0
        numeric_later = self.versionengine.parse_version("1.0.0-10")
        textual_later = self.versionengine.parse_version("1.0.0-beta")
        assert self.checked_versionengine.compare_precedence(numeric, numeric_later) < 0
        assert self.checked_versionengine.compare_precedence(numeric_later, numeric) > 0
        assert self.checked_versionengine.compare_precedence(textual, textual_later) < 0
        assert self.checked_versionengine.compare_precedence(textual_later, textual) > 0
        numeric_extended = self.versionengine.parse_version("1.0.0-alpha.2")
        numeric_extended_later = self.versionengine.parse_version("1.0.0-alpha.10")
        assert self.checked_versionengine.compare_precedence(numeric_extended, numeric_extended_later) < 0
        assert self.checked_versionengine.compare_precedence(numeric_extended_later, numeric_extended) > 0

    def test_satisfies_prerelease_contract(self) -> None:
        candidate = self.versionengine.parse_version("2.0.0-alpha.1")
        targeted = self.versionengine.parse_range("2.0.0-alpha.1")
        wide = self.versionengine.parse_range(">=1.0.0")
        assert self.versionengine.satisfies(candidate, targeted, False)
        assert self.versionengine.satisfies(candidate, wide, True)
        assert not self.versionengine.satisfies(candidate, wide, False)

    def test_solver_search_contract(self) -> None:
        alpha_one = self.versionengine.parse_version("1.0.0")
        alpha_two = self.versionengine.parse_version("2.0.0")
        delta_one = self.versionengine.parse_version("1.5.0")
        any_range = self.versionengine.parse_range("*")
        alpha_at_least_one = self.versionengine.parse_range(">=1.0.0")
        alpha_at_least_two = self.versionengine.parse_range(">=2.0.0")
        alpha_below_two = self.versionengine.parse_range("<2.0.0")
        delta_series = self.versionengine.parse_range("1.x")
        self.packagerepository.register_package(
            PackageRelease(name="alpha", version=alpha_one, dependencies=())
        )
        self.packagerepository.register_package(
            PackageRelease(name="alpha", version=alpha_two, dependencies=())
        )
        self.packagerepository.register_package(
            PackageRelease(name="delta", version=delta_one, dependencies=())
        )
        self.packagerepository.register_package(
            PackageRelease(
                name="gamma",
                version=alpha_two,
                dependencies=(
                    PackageDependency(name="alpha", range_constraint=alpha_at_least_two),
                ),
            )
        )
        self.packagerepository.register_package(
            PackageRelease(
                name="gamma",
                version=alpha_one,
                dependencies=(
                    PackageDependency(name="alpha", range_constraint=alpha_at_least_one),
                    PackageDependency(name="delta", range_constraint=delta_series),
                ),
            )
        )
        transitive = self.dependencysolver.resolve(
            (
                PackageDependency(name="alpha", range_constraint=alpha_below_two),
                PackageDependency(name="gamma", range_constraint=any_range),
            )
        )
        assert transitive.selected_versions["alpha"] == alpha_one
        assert transitive.selected_versions["gamma"] == alpha_one
        assert transitive.selected_versions["delta"] == delta_one
        assert transitive.derivation_steps == (
            "Assign 'alpha' to 1.0.0",
            "Assign 'gamma' to 1.0.0",
            "Assign 'delta' to 1.5.0",
        )
        highest = self.dependencysolver.resolve(
            (PackageDependency(name="gamma", range_constraint=any_range),)
        )
        assert highest.selected_versions["gamma"] == alpha_two
        assert highest.selected_versions["alpha"] == alpha_two
        assert highest.derivation_steps == (
            "Assign 'gamma' to 2.0.0",
            "Assign 'alpha' to 2.0.0",
        )

    def test_solver_backtracking_restoration_contract(self) -> None:
        alpha_one = self.versionengine.parse_version("1.0.0")
        delta_one = self.versionengine.parse_version("1.5.0")
        any_range = self.versionengine.parse_range("*")
        alpha_below_two = self.versionengine.parse_range("<2.0.0")
        impossible_delta = self.versionengine.parse_range(">=3.0.0")
        delta_series = self.versionengine.parse_range("1.x")
        self.packagerepository.register_package(
            PackageRelease(name="alpha", version=alpha_one, dependencies=())
        )
        self.packagerepository.register_package(
            PackageRelease(name="delta", version=delta_one, dependencies=())
        )
        self.packagerepository.register_package(
            PackageRelease(
                name="gamma",
                version=self.versionengine.parse_version("2.0.0"),
                dependencies=(
                    PackageDependency(name="delta", range_constraint=impossible_delta),
                ),
            )
        )
        self.packagerepository.register_package(
            PackageRelease(
                name="gamma",
                version=alpha_one,
                dependencies=(
                    PackageDependency(name="delta", range_constraint=delta_series),
                ),
            )
        )
        restored = self.dependencysolver.resolve(
            (
                PackageDependency(name="alpha", range_constraint=alpha_below_two),
                PackageDependency(name="gamma", range_constraint=any_range),
            )
        )
        assert restored.selected_versions["alpha"] == alpha_one
        assert restored.selected_versions["gamma"] == alpha_one
        assert restored.selected_versions["delta"] == delta_one
        assert restored.derivation_steps == (
            "Assign 'alpha' to 1.0.0",
            "Assign 'gamma' to 1.0.0",
            "Assign 'delta' to 1.5.0",
        )

    def test_version_engine_error_contract(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.2.3")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.02.3")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.2.03")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.2")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.2.3.4")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("not-a-version")

    def test_range_parser_error_contract(self) -> None:
        for rejected_range in (
            "",
            "   ",
            "||",
            ">=1.0.0 ||",
            ">=1.0.0, <2.0.0",
            ">=",
            "~",
            "1",
            "1.2",
            "^0.0",
            "1.2 - 2.3",
            "1.2.3 - 2.3",
        ):
            with self.assertRaises(InvalidRangeError):
                self.versionengine.parse_range(rejected_range)

    def test_repository_error_contract(self) -> None:
        assert not self.packagerepository.has_package("omega")
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("omega")

    def test_solver_error_contract(self) -> None:
        alpha_one = self.versionengine.parse_version("1.0.0")
        alpha_two = self.versionengine.parse_version("2.0.0")
        any_range = self.versionengine.parse_range("*")
        alpha_at_least_two = self.versionengine.parse_range(">=2.0.0")
        alpha_above_one = self.versionengine.parse_range(">=1.5.0")
        alpha_below_two = self.versionengine.parse_range("<2.0.0")
        self.packagerepository.register_package(
            PackageRelease(name="alpha", version=alpha_one, dependencies=())
        )
        self.packagerepository.register_package(
            PackageRelease(name="alpha", version=alpha_two, dependencies=())
        )
        self.packagerepository.register_package(
            PackageRelease(
                name="gamma",
                version=alpha_two,
                dependencies=(
                    PackageDependency(name="alpha", range_constraint=alpha_at_least_two),
                ),
            )
        )
        self.packagerepository.register_package(
            PackageRelease(
                name="gamma",
                version=alpha_one,
                dependencies=(
                    PackageDependency(name="alpha", range_constraint=alpha_above_one),
                ),
            )
        )
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(
                (PackageDependency(name="omega", range_constraint=any_range),)
            )
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(
                (
                    PackageDependency(name="alpha", range_constraint=alpha_at_least_two),
                    PackageDependency(name="alpha", range_constraint=alpha_below_two),
                )
            )
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(
                (
                    PackageDependency(name="alpha", range_constraint=alpha_below_two),
                    PackageDependency(name="gamma", range_constraint=any_range),
                )
            )


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
        self.version = CANONICAL_VERSIONS[0]
        self.__dict__["_services"] = (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
            self.version,
        )

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
# LAST_CLEANED: 2026-11-05T04:37:17Z
# LAST_CHANGED: 2026-11-05T04:36:45Z
# CHANGE: Closed the three remaining contract branches. (1) The inequality comparator now parses and evaluates against the full any-version wildcard band: !=* is added to the accepted-range grammar and asserted unsatisfiable for both 0.0.0 and 1.5.0, covering the negated empty-band case. (2) The ordering less-than comparator now applies to a bounded wildcard band: <1.x is added to the accepted-range grammar and asserted to satisfy 0.9.9 while rejecting 1.0.0 and 1.5.0, completing the bounded-wildcard comparator family alongside !=1.x, >1.x and >=1.x. (3) The hyphen rejection contract now covers a well-formed lower endpoint with a bare partial upper endpoint lacking wildcards: parse_range('1.2.3 - 2.3') is asserted to raise InvalidRangeError, alongside the existing malformed lower-endpoint case '1.2 - 2.3'.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:37:17Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:37:04Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
import unittest

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
from benchmark_2.parts.semver_solver.lib.semver_solver import (
    ComparatorOp,
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
# 0. Contractual Input Catalog
# ==============================================================================
# SemVer parsing and range parsing are contractually checked preconditions: invalid
# text raises a *Error that callers must never trigger.  The catalog below bounds the
# caller contract to well formed inputs so fuzzing explores valid protocol usage.

VALID_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "1.2.3",
    "2.0.0-alpha.1",
    "2.0.0-alpha.1+build.5",
    "10.20.30",
)

VALID_RANGE_TEXTS: Tuple[str, ...] = (
    ">=1.0.0",
    "^1.2.3",
    "~1.2.0",
    "1.x",
    ">=1.0.0 <2.0.0",
    "*",
)

PARSED_VERSIONS: Dict[str, Version] = {
    "0.0.0": Version(major=0, minor=0, patch=0),
    "1.2.3": Version(major=1, minor=2, patch=3),
    "2.0.0-alpha.1": Version(major=2, minor=0, patch=0, prerelease=("alpha", "1")),
    "2.0.0-alpha.1+build.5": Version(
        major=2,
        minor=0,
        patch=0,
        prerelease=("alpha", "1"),
        build=("build", "5"),
    ),
    "10.20.30": Version(major=10, minor=20, patch=30),
}

CANONICAL_VERSIONS: Tuple[Version, ...] = (
    Version(major=0, minor=0, patch=0),
    Version(major=1, minor=2, patch=3),
    Version(major=2, minor=0, patch=0, prerelease=("alpha", "1")),
    Version(major=2, minor=0, patch=0, prerelease=("alpha", "11")),
    Version(major=2, minor=1, patch=0, build=("build", "5")),
    Version(major=2, minor=0, patch=0),
)

CANONICAL_RANGES: Tuple[VersionRange, ...] = (
    VersionRange(raw_text=">=1.0.0"),
    VersionRange(raw_text="^1.2.3"),
    VersionRange(raw_text="*"),
)

CANONICAL_RELEASES: Tuple[PackageRelease, ...] = (
    PackageRelease(name="alpha", version=Version(major=1, minor=0, patch=0)),
    PackageRelease(name="alpha", version=Version(major=2, minor=0, patch=0)),
    PackageRelease(name="beta", version=Version(major=1, minor=2, patch=3)),
)

ROOT_DEPENDENCY_SETS: Tuple[Tuple[PackageDependency, ...], ...] = (
    (),
    (PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="*")),),
    (
        PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="*")),
        PackageDependency(name="beta", range_constraint=VersionRange(raw_text="*")),
    ),
)

REQUIRED_PACKAGES: frozenset[str] = frozenset({"alpha", "beta"})

# The value surface instance bound into the SUT fixture; value-type transitions
# (Version.format / Version.is_prerelease) model exactly this instance.
VALUE_SURFACE_VERSION: Version = CANONICAL_VERSIONS[0]

# ==============================================================================
# 0b. SemVer Model Algebra
# ==============================================================================
# These helpers implement the abstract SemVer precedence and range algebra used by
# the model transitions.  They operate on abstract version components and encoded
# comparator bounds so that the state machine never instantiates target services.

ComparatorBound = Tuple[str, int, int, int, Tuple[str, ...]]
VersionKey = Tuple[Tuple[int, int, int], int, Tuple[Tuple[int, int, str], ...]]


def _version_key(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...],
) -> VersionKey:
    """Encodes precedence ordering: core numbers, then normal-above-prerelease, then segments."""
    segments = tuple(
        (0, int(segment), "") if segment.isdigit() else (1, 0, segment)
        for segment in prerelease
    )
    return ((major, minor, patch), 0 if prerelease else 1, segments)


def _format_version(version: Version) -> str:
    """Renders the canonical SemVer 2.0.0 text for a version record."""
    formatted = ".".join((str(version.major), str(version.minor), str(version.patch)))
    if version.prerelease:
        formatted = formatted + "-" + ".".join(version.prerelease)
    if version.build:
        formatted = formatted + "+" + ".".join(version.build)
    return formatted


def _release_key(release: PackageRelease) -> VersionKey:
    """Precedence ordering key for a package release."""
    return _version_key(
        release.version.major,
        release.version.minor,
        release.version.patch,
        release.version.prerelease,
    )


def _sorted_releases(releases: List[PackageRelease]) -> List[PackageRelease]:
    """Orders releases by descending version precedence."""
    return sorted(releases, key=_release_key, reverse=True)


def _parse_components(
    text: str,
) -> Optional[Tuple[Optional[int], Optional[int], Optional[int], Tuple[str, ...]]]:
    """Parses major/minor/patch components plus prerelease identifiers, tolerating wildcards."""
    core = text.strip().partition("+")[0]
    number_text = core.partition("-")[0]
    prerelease_text = core.partition("-")[2]
    parts = number_text.split(".")
    if len(parts) > 3:
        return None
    values: List[Optional[int]] = []
    for part in parts:
        if part in ("x", "X", "*", ""):
            values.append(None)
        elif part.isdigit():
            values.append(int(part))
        else:
            return None
    if len(values) == 1:
        values = [values[0], None, None]
    elif len(values) == 2:
        values = [values[0], values[1], None]
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    return (values[0], values[1], values[2], prerelease)


def _wildcard_bounds(
    major: int,
    minor: Optional[int],
    patch: Optional[int],
) -> List[ComparatorBound]:
    """Expands a wildcard-flexible range into lower and upper comparator bounds."""
    if minor is None:
        return [
            (">=", major, 0, 0, ()),
            ("<", major + 1, 0, 0, ()),
        ]
    if patch is None:
        return [
            (">=", major, minor, 0, ()),
            ("<", major, minor + 1, 0, ()),
        ]
    return [("==", major, minor, patch, ())]


def _caret_bounds(
    major: int,
    minor: Optional[int],
    patch: Optional[int],
    prerelease: Tuple[str, ...],
) -> List[ComparatorBound]:
    """Expands a caret prefix at the first non-zero component boundary."""
    if minor is None:
        return [
            (">=", major, 0, 0, ()),
            ("<", major + 1, 0, 0, ()),
        ]
    if patch is None:
        if major > 0:
            return [(">=", major, minor, 0, ()), ("<", major + 1, 0, 0, ())]
        return [(">=", 0, minor, 0, ()), ("<", 0, minor + 1, 0, ())]
    if major > 0:
        return [(">=", major, minor, patch, prerelease), ("<", major + 1, 0, 0, ())]
    if minor > 0:
        return [(">=", 0, minor, patch, prerelease), ("<", 0, minor + 1, 0, ())]
    return [(">=", 0, 0, patch, prerelease), ("<", 0, 0, patch + 1, ())]


def _tilde_bounds(
    major: int,
    minor: Optional[int],
    patch: Optional[int],
    prerelease: Tuple[str, ...],
) -> List[ComparatorBound]:
    """Expands a tilde prefix into lower and upper minor boundaries."""
    if minor is None:
        return [(">=", major, 0, 0, ()), ("<", major + 1, 0, 0, ())]
    return [
        (">=", major, minor, patch or 0, prerelease),
        ("<", major, minor + 1, 0, ()),
    ]


def _expand_token(token: str) -> List[ComparatorBound]:
    """Expands one comparator token into encoded bounds."""
    operator = "=="
    body = token
    for prefix in (">=", "<=", "==", "!=", ">", "<", "=", "^", "~"):
        if token.startswith(prefix):
            operator = prefix
            body = token[len(prefix):]
            break
    components = _parse_components(body)
    if components is None:
        return []
    major, minor, patch, prerelease = components
    if major is None:
        return [(">=", 0, 0, 0, ())]
    if operator == "^":
        return _caret_bounds(major, minor, patch, prerelease)
    if operator == "~":
        return _tilde_bounds(major, minor, patch, prerelease)
    if minor is None or patch is None:
        return _wildcard_bounds(major, minor, patch)
    effective_operator = "==" if operator == "=" else operator
    return [(effective_operator, major, minor, patch, prerelease)]


def _expand_clause(clause: str) -> List[ComparatorBound]:
    """Expands one whitespace-delimited comparator clause (including hyphen ranges)."""
    tokens = [token for token in clause.strip().split() if token]
    if "-" in tokens:
        separator = tokens.index("-")
        if separator > 0 and separator < len(tokens) - 1:
            lower = _parse_components(tokens[separator - 1])
            upper = _parse_components(tokens[separator + 1])
            bounds: List[ComparatorBound] = []
            if lower is not None and lower[0] is not None:
                bounds.append((">=", lower[0], lower[1] or 0, lower[2] or 0, lower[3]))
            if upper is not None and upper[0] is not None:
                if upper[1] is None or upper[2] is None:
                    bounds.extend(_wildcard_bounds(upper[0], upper[1], upper[2]))
                else:
                    bounds.append(("<=", upper[0], upper[1], upper[2], upper[3]))
            return bounds
    bounds: List[ComparatorBound] = []
    for token in tokens:
        bounds.extend(_expand_token(token))
    return bounds


def _comparators_match(comparators: List[ComparatorBound], version: Version) -> bool:
    """Tests a candidate version against every comparator in a clause."""
    candidate = _version_key(
        version.major,
        version.minor,
        version.patch,
        version.prerelease,
    )
    for operator, major, minor, patch, prerelease in comparators:
        bound = _version_key(major, minor, patch, prerelease)
        if operator == ">=":
            if not candidate >= bound:
                return False
        elif operator == ">":
            if not candidate > bound:
                return False
        elif operator == "<=":
            if not candidate <= bound:
                return False
        elif operator == "<":
            if not candidate < bound:
                return False
        elif operator == "!=":
            if not candidate != bound:
                return False
        elif candidate != bound:
            return False
    return True


def _range_satisfies(
    raw_text: str,
    version: Version,
    include_prerelease: bool,
) -> bool:
    """Evaluates a candidate version against a range expression using comparator bounds."""
    for clause in raw_text.split("||"):
        comparators = _expand_clause(clause)
        if not _comparators_match(comparators, version):
            continue
        if version.prerelease and not include_prerelease:
            targeted = False
            for operator, major, minor, patch, prerelease in comparators:
                if prerelease and (major, minor, patch) == (
                    version.major,
                    version.minor,
                    version.patch,
                ):
                    targeted = True
                    break
            if not targeted:
                continue
        return True
    return False


def _solve(
    packages: Dict[str, List[PackageRelease]],
    constraints: Dict[str, List[VersionRange]],
    assignment: Dict[str, PackageRelease],
    steps: List[str],
) -> bool:
    """Depth-first MRV resolution with descending precedence value ordering and step logging."""
    unassigned = [name for name in constraints if name not in assignment]
    if not unassigned:
        return True
    candidates: Dict[str, List[PackageRelease]] = {}
    for name in unassigned:
        viable: List[PackageRelease] = []
        for release in _sorted_releases(packages.get(name, [])):
            satisfied = True
            for range_constraint in constraints[name]:
                if not _range_satisfies(range_constraint.raw_text, release.version, False):
                    satisfied = False
                    break
            if satisfied:
                viable.append(release)
        candidates[name] = viable
    selected_name = min(unassigned, key=lambda name: (len(candidates[name]), name))
    if not candidates[selected_name]:
        return False
    for candidate in candidates[selected_name]:
        assignment[selected_name] = candidate
        steps.append(
            "Assign '" + selected_name + "' to " + _format_version(candidate.version)
        )
        conflict = False
        added: Dict[str, List[VersionRange]] = {}
        for dependency in candidate.dependencies:
            if dependency.name in assignment:
                if not _range_satisfies(
                    dependency.range_constraint.raw_text,
                    assignment[dependency.name].version,
                    False,
                ):
                    conflict = True
                    break
            else:
                constraints.setdefault(dependency.name, []).append(dependency.range_constraint)
                added.setdefault(dependency.name, []).append(dependency.range_constraint)
        if not conflict and _solve(packages, constraints, assignment, steps):
            return True
        for name in list(added.keys()):
            for range_constraint in added[name]:
                constraints[name].remove(range_constraint)
            if not constraints[name]:
                del constraints[name]
        del assignment[selected_name]
        steps.pop()
    return False


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException):
# ()) live naturally inside the single transition body
# (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real
# calls).  require(...) inspects only model state.


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    versions: Dict[str, Version] = field(default_factory=dict)
    ranges: Dict[str, VersionRange] = field(default_factory=dict)
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)


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
        formatted = _format_version(VALUE_SURFACE_VERSION)
        ret = self.inner_format()
        assert ret == formatted
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.sampled_from(VALID_VERSION_TEXTS),
            preferred=["1.2.3", "2.0.0-alpha.1"],
        )
        version = PARSED_VERSIONS.get(text, VALUE_SURFACE_VERSION)
        self.state.versions[text] = version
        ret = self.inner_parse_version(text)
        assert ret.major == version.major
        assert ret.minor == version.minor
        assert ret.patch == version.patch
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version), preferred=list(CANONICAL_VERSIONS))
        require_arg(v2, Domain.type(Version), preferred=list(CANONICAL_VERSIONS))
        key1 = _version_key(v1.major, v1.minor, v1.patch, v1.prerelease)
        key2 = _version_key(v2.major, v2.minor, v2.patch, v2.prerelease)
        result = 0
        if key1 < key2:
            result = -1
        elif key1 > key2:
            result = 1
        ret = self.inner_compare_precedence(v1, v2)
        assert (ret < 0) == (result < 0)
        assert (ret > 0) == (result > 0)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.sampled_from(VALID_RANGE_TEXTS),
            preferred=[">=1.0.0", "^1.2.3"],
        )
        trimmed = text.strip()
        range_constraint = VersionRange(raw_text=trimmed)
        self.state.ranges[trimmed] = range_constraint
        ret = self.inner_parse_range(text)
        assert ret.raw_text == trimmed
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(
            version,
            Domain.sampled_from(CANONICAL_VERSIONS),
            preferred=list(CANONICAL_VERSIONS),
        )
        require_arg(
            range_constraint,
            Domain.sampled_from(CANONICAL_RANGES),
            preferred=list(CANONICAL_RANGES),
        )
        require_arg(include_prerelease, Domain.boolean())
        satisfied = _range_satisfies(
            range_constraint.raw_text,
            version,
            include_prerelease,
        )
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert ret == satisfied
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require_arg(
            release,
            Domain.sampled_from(CANONICAL_RELEASES),
            preferred=list(CANONICAL_RELEASES),
        )
        self.state.packages.setdefault(release.name, []).append(release)
        ret = self.inner_register_package(release)
        assert release.name in self.state.packages
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.in_set(self.state.packages.keys()),
            preferred=["alpha", "beta"],
        )
        releases = _sorted_releases(list(self.state.packages[name]))
        ret = self.inner_get_releases(name)
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["alpha", "beta"])
        result = name in self.state.packages
        ret = self.inner_has_package(name)
        assert ret == result
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        names = set(self.state.packages.keys())
        ret = self.inner_all_packages()
        assert ret == names
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require(self.state.packages.keys() >= REQUIRED_PACKAGES)
        require_arg(
            root_dependencies,
            Domain.sampled_from(ROOT_DEPENDENCY_SETS),
            preferred=[ROOT_DEPENDENCY_SETS[0], ROOT_DEPENDENCY_SETS[1]],
        )
        constraints: Dict[str, List[VersionRange]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(dependency.range_constraint)
        assignment: Dict[str, PackageRelease] = {}
        steps: List[str] = []
        resolved = _solve(self.state.packages, constraints, assignment, steps)
        selected: Dict[str, Version] = {}
        for name, release in assignment.items():
            selected[name] = release.version
        outcome = ResolutionOutcome(
            selected_versions=selected,
            derivation_steps=tuple(steps),
        )
        ret = self.inner_resolve(root_dependencies)
        assert resolved
        assert ret.selected_versions == selected
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        flag = len(VALUE_SURFACE_VERSION.prerelease) > 0
        ret = self.inner_is_prerelease()
        assert ret == flag
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
) -> Tuple[
    ComparatorOp,
    Version,
    VersionRange,
    PackageDependency,
    PackageRelease,
    ResolutionOutcome,
    VersionEngine,
    PackageRepository,
    DependencySolver,
]:
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
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.sm = SemverSolverStateMachine()
        self.fakes = make_semver_solver_fakes()
        self.fake = FakeSemverSolver(state=SemverSolverState())

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.sm.register_package(CANONICAL_RELEASES[0])
        self.sm.register_package(CANONICAL_RELEASES[1])
        self.sm.register_package(CANONICAL_RELEASES[2])
        self.fake.register_package(CANONICAL_RELEASES[0])
        self.fake.register_package(CANONICAL_RELEASES[1])
        self.fake.register_package(CANONICAL_RELEASES[2])
        parsed_sm = self.sm.parse_version(VALID_VERSION_TEXTS[1])
        parsed_fake = self.fake.parse_version(VALID_VERSION_TEXTS[1])
        assert (parsed_sm.major, parsed_sm.minor, parsed_sm.patch) == (1, 2, 3)
        assert (parsed_fake.major, parsed_fake.minor, parsed_fake.patch) == (1, 2, 3)
        assert self.sm.compare_precedence(parsed_sm, CANONICAL_VERSIONS[0]) > 0
        assert self.fake.compare_precedence(parsed_fake, CANONICAL_VERSIONS[0]) > 0
        assert self.sm.compare_precedence(CANONICAL_VERSIONS[5], CANONICAL_VERSIONS[2]) > 0
        assert self.fake.compare_precedence(CANONICAL_VERSIONS[5], CANONICAL_VERSIONS[2]) > 0
        sm_range = self.sm.parse_range(VALID_RANGE_TEXTS[0])
        fake_range = self.fake.parse_range(VALID_RANGE_TEXTS[0])
        assert sm_range.raw_text == ">=1.0.0"
        assert fake_range.raw_text == ">=1.0.0"
        assert self.sm.satisfies(CANONICAL_VERSIONS[1], sm_range, False)
        assert self.fake.satisfies(CANONICAL_VERSIONS[1], fake_range, False)
        assert self.sm.satisfies(CANONICAL_VERSIONS[0], CANONICAL_RANGES[2], False)
        assert self.fake.satisfies(CANONICAL_VERSIONS[0], CANONICAL_RANGES[2], False)
        assert not self.sm.satisfies(CANONICAL_VERSIONS[2], CANONICAL_RANGES[2], False)
        assert self.sm.satisfies(CANONICAL_VERSIONS[2], CANONICAL_RANGES[2], True)
        assert not self.sm.satisfies(CANONICAL_VERSIONS[5], CANONICAL_RANGES[1], False)
        assert self.sm.has_package("alpha")
        assert self.fake.has_package("alpha")
        assert not self.sm.has_package("gamma")
        assert self.sm.all_packages() == {"alpha", "beta"}
        assert self.fake.all_packages() == {"alpha", "beta"}
        assert len(self.sm.get_releases("alpha")) == 2
        assert len(self.fake.get_releases("alpha")) == 2
        sm_outcome = self.sm.resolve(ROOT_DEPENDENCY_SETS[1])
        fake_outcome = self.fake.resolve(ROOT_DEPENDENCY_SETS[1])
        assert sm_outcome.selected_versions["alpha"] == CANONICAL_RELEASES[1].version
        assert fake_outcome.selected_versions["alpha"] == CANONICAL_RELEASES[1].version
        assert sm_outcome.derivation_steps == ("Assign 'alpha' to 2.0.0",)
        assert fake_outcome.derivation_steps == ("Assign 'alpha' to 2.0.0",)
        assert self.sm.resolve(ROOT_DEPENDENCY_SETS[0]).selected_versions == {}
        assert not self.sm.is_prerelease()
        assert self.sm.format() == "0.0.0"
        assert self.fake.format() == "0.0.0"


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:17:17Z
# LAST_CHANGED: 2026-11-05T04:17:17Z
# CHANGE: Resolved feedback by replacing the shallow satisfaction/resolution models with faithful SemVer algebra: satisfies now compiles the range into disjunctive comparator clauses, expands caret/tilde/wildcard/hyphen bounds, evaluates the candidate by precedence, and applies include_prerelease plus the same-major/minor/patch prerelease-target exception (so 0.0.0 vs '*' with include_prerelease False is True, and 2.0.0-alpha.1 vs '*' is False unless include_prerelease); resolve now runs depth-first MRV selection over releases ordered by descending precedence, merges transitive dependency constraints, backtracks on conflicts, and records the documented "Assign '<pkg>' to <version>" derivation steps, so alpha 1.0.0/2.0.0 with alpha '*' selects 2.0.0. get_releases now yields descending precedence order. Fixed fake scenarios cover the wildcard, prerelease-exclusion, and highest-precedence counterexamples.
# --- END AUTOFAB METADATA ---
