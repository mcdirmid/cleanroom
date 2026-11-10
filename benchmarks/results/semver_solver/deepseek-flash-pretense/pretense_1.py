# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

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
from benchmark_2.parts.semver_solver.lib import semver_solver
from benchmark_2.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)
from benchmark_2.parts.semver_solver.pretense.semver_solver_pretense import (
    FakeSemverSolver,
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fake,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# Pseudo-state-machine overrides observe the real SUT through call_target pivots.
# Randomly generated arguments can violate caller preconditions (*Error) during
# exploratory fuzzing, so each override treats such a violation as an undefined
# exploratory input instead of letting it abort the property test.


class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> semver_solver.Version:
        target: VersionEngine = sut(VersionEngine)
        ret: semver_solver.Version
        try:
            ret = call_target(target.parse_version(text))
        except semver_solver.SemVerError:
            ret = semver_solver.Version(0, 0, 0)
        assert ret.major >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> semver_solver.VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret: semver_solver.VersionRange
        try:
            ret = call_target(target.parse_range(text))
        except semver_solver.SemVerError:
            ret = semver_solver.VersionRange("")
        assert isinstance(ret.raw_text, str)
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngine = sut(VersionEngine)
        ret: bool
        try:
            ret = call_target(
                target.satisfies(version, range_constraint, include_prerelease)
            )
        except semver_solver.SemVerError:
            ret = False
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: semver_solver.PackageRelease,
    ) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert target.has_package(release.name)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[semver_solver.PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret: List[semver_solver.PackageRelease]
        try:
            ret = call_target(target.get_releases(name))
        except semver_solver.SemVerError:
            ret = []
        assert isinstance(ret, list)
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
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret: semver_solver.ResolutionOutcome
        try:
            ret = call_target(target.resolve(root_dependencies))
        except semver_solver.SemVerError:
            ret = semver_solver.ResolutionOutcome(
                selected_versions={},
                derivation_steps=(),
            )
        assert isinstance(ret.selected_versions, Mapping)
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
        self.checked_versionengine = self.sm.as_checked(
            VersionEngine, self.versionengine
        )
        self.checked_packagerepository = self.sm.as_checked(
            PackageRepository, self.packagerepository
        )
        self.checked_dependencysolver = self.sm.as_checked(
            DependencySolver, self.dependencysolver
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version(self) -> None:
        """Parses canonical versions into ordered major/minor/patch records."""
        release = self.checked_versionengine.parse_version("1.2.3")
        assert release.major == 1
        assert release.minor == 2
        assert release.patch == 3
        assert release.prerelease == ()
        assert release.build == ()
        zeroed = self.checked_versionengine.parse_version("0.0.0")
        assert zeroed.major == 0
        assert zeroed.minor == 0
        assert zeroed.patch == 0
        tagged = self.checked_versionengine.parse_version("1.2.3-alpha.1+build.9")
        assert tagged.prerelease == ("alpha", "1")
        assert tagged.build == ("build", "9")
        build_only = self.checked_versionengine.parse_version("1.0.0+build.5")
        assert build_only.prerelease == ()
        assert build_only.build == ("build", "5")
        prerelease_only = self.checked_versionengine.parse_version("2.1.0-rc.2")
        assert prerelease_only.prerelease == ("rc", "2")
        assert prerelease_only.build == ()

    def test_compare_precedence(self) -> None:
        """Orders versions by SemVer numeric, prerelease, and build precedence rules."""
        older = self.checked_versionengine.parse_version("1.0.0")
        newer = self.checked_versionengine.parse_version("2.0.0")
        assert self.checked_versionengine.compare_precedence(older, newer) < 0
        assert self.checked_versionengine.compare_precedence(newer, older) > 0
        assert self.checked_versionengine.compare_precedence(older, older) == 0
        lower_minor = self.checked_versionengine.parse_version("1.0.1")
        assert self.checked_versionengine.compare_precedence(older, lower_minor) < 0
        alpha = self.checked_versionengine.parse_version("1.0.0-alpha")
        beta = self.checked_versionengine.parse_version("1.0.0-beta")
        assert self.checked_versionengine.compare_precedence(alpha, beta) < 0
        assert self.checked_versionengine.compare_precedence(alpha, older) < 0
        assert self.checked_versionengine.compare_precedence(older, alpha) > 0
        build_one = self.checked_versionengine.parse_version("1.0.0+build.1")
        build_two = self.checked_versionengine.parse_version("1.0.0+build.2")
        assert self.checked_versionengine.compare_precedence(build_one, build_two) == 0
        numeric_segment = semver_solver.Version(1, 0, 0, ("1",))
        alphanumeric_segment = semver_solver.Version(1, 0, 0, ("alpha",))
        assert (
            self.checked_versionengine.compare_precedence(
                numeric_segment, alphanumeric_segment
            )
            < 0
        )
        assert (
            self.checked_versionengine.compare_precedence(
                alphanumeric_segment, numeric_segment
            )
            > 0
        )
        shorter = semver_solver.Version(1, 0, 0, ("alpha",))
        longer = semver_solver.Version(1, 0, 0, ("alpha", "1"))
        assert self.checked_versionengine.compare_precedence(shorter, longer) < 0
        assert self.checked_versionengine.compare_precedence(longer, shorter) > 0
        numeric_two = semver_solver.Version(1, 0, 0, ("2",))
        numeric_ten = semver_solver.Version(1, 0, 0, ("10",))
        assert (
            self.checked_versionengine.compare_precedence(numeric_two, numeric_ten)
            < 0
        )
        assert (
            self.checked_versionengine.compare_precedence(numeric_ten, numeric_two)
            > 0
        )
        alpha_identifier = self.checked_versionengine.parse_version("1.0.0-alpha")
        gamma_identifier = self.checked_versionengine.parse_version("1.0.0-gamma")
        assert (
            self.checked_versionengine.compare_precedence(
                alpha_identifier, gamma_identifier
            )
            < 0
        )
        assert (
            self.checked_versionengine.compare_precedence(
                gamma_identifier, alpha_identifier
            )
            > 0
        )

    def test_parse_range_comparators(self) -> None:
        """Parses equality, inequality, and relational comparator expressions."""
        bare = self.checked_versionengine.parse_range("1.2.3")
        assert bare.raw_text == "1.2.3"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 3), bare, False
        ) is True
        double_equals = self.checked_versionengine.parse_range("==1.2.3")
        assert double_equals.raw_text == "==1.2.3"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 3), double_equals, False
        ) is True
        single_equals = self.checked_versionengine.parse_range("=1.2.3")
        assert single_equals.raw_text == "=1.2.3"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 3), single_equals, False
        ) is True
        not_equals = self.checked_versionengine.parse_range("!=1.2.3")
        assert not_equals.raw_text == "!=1.2.3"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 3), not_equals, False
        ) is False
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 4), not_equals, False
        ) is True
        less_than = self.checked_versionengine.parse_range("<2.0.0")
        assert less_than.raw_text == "<2.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 9, 9), less_than, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), less_than, False
        ) is False
        less_equal = self.checked_versionengine.parse_range("<=2.0.0")
        assert less_equal.raw_text == "<=2.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), less_equal, False
        ) is True
        greater_than = self.checked_versionengine.parse_range(">1.0.0")
        assert greater_than.raw_text == ">1.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 1), greater_than, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0), greater_than, False
        ) is False
        greater_equal = self.checked_versionengine.parse_range(">=1.0.0")
        assert greater_equal.raw_text == ">=1.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0), greater_equal, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 9, 9), greater_equal, False
        ) is False
        padded = self.checked_versionengine.parse_range("  >=1.0.0 <2.0.0  ")
        assert padded.raw_text == ">=1.0.0 <2.0.0"
        spaced = self.checked_versionengine.parse_range(">= 1.0.0")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0), spaced, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 9, 9), spaced, False
        ) is False

    def test_parse_range_caret_and_tilde(self) -> None:
        """Expands caret and tilde range prefixes into bounded comparator inequalities."""
        major_caret = self.checked_versionengine.parse_range("^1.2.3")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 3), major_caret, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 9, 9), major_caret, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), major_caret, False
        ) is False
        major_zero = self.checked_versionengine.parse_range("^0.1.0")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 1, 5), major_zero, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 2, 0), major_zero, False
        ) is False
        minor_zero = self.checked_versionengine.parse_range("^0.0.3")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 0, 3), minor_zero, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 0, 4), minor_zero, False
        ) is False
        spaced_caret = self.checked_versionengine.parse_range("^ 1.2.3")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 3), spaced_caret, False
        ) is True
        tilde = self.checked_versionengine.parse_range("~1.2.3")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 3), tilde, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 9), tilde, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 3, 0), tilde, False
        ) is False
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 2), tilde, False
        ) is False
        caret_wildcard = self.checked_versionengine.parse_range("^1.x")
        assert caret_wildcard.raw_text == "^1.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), caret_wildcard, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), caret_wildcard, False
        ) is False
        tilde_wildcard = self.checked_versionengine.parse_range("~1.x")
        assert tilde_wildcard.raw_text == "~1.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), tilde_wildcard, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), tilde_wildcard, False
        ) is False

    def test_parse_range_relational_wildcards(self) -> None:
        """Composes relational prefixes with wildcard major and minor operands."""
        at_least_major = self.checked_versionengine.parse_range(">=1.x")
        assert at_least_major.raw_text == ">=1.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), at_least_major, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 9, 9), at_least_major, False
        ) is False
        less_than_minor = self.checked_versionengine.parse_range("<1.2.x")
        assert less_than_minor.raw_text == "<1.2.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 1, 0), less_than_minor, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 0), less_than_minor, False
        ) is False
        at_most_major = self.checked_versionengine.parse_range("<=1.x")
        assert at_most_major.raw_text == "<=1.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0), at_most_major, False
        ) is True
        greater_major = self.checked_versionengine.parse_range(">1.x")
        assert greater_major.raw_text == ">1.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), greater_major, False
        ) is True

    def test_parse_range_universal_compositions(self) -> None:
        """Composes caret, tilde, and relational prefixes with a universal wildcard."""
        caret_universal = self.checked_versionengine.parse_range("^*")
        assert caret_universal.raw_text == "^*"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 0, 0), caret_universal, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), caret_universal, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(9, 9, 9), caret_universal, False
        ) is True
        tilde_universal = self.checked_versionengine.parse_range("~*")
        assert tilde_universal.raw_text == "~*"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 0, 0), tilde_universal, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), tilde_universal, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(9, 9, 9), tilde_universal, False
        ) is True
        at_least_universal = self.checked_versionengine.parse_range(">=*")
        assert at_least_universal.raw_text == ">=*"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 0, 0), at_least_universal, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(9, 9, 9), at_least_universal, False
        ) is True

    def test_parse_range_caret_zero_bands(self) -> None:
        """Expands caret over zero-major wildcard bands via first non-zero boundaries."""
        minor_band = self.checked_versionengine.parse_range("^0.1.x")
        assert minor_band.raw_text == "^0.1.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 1, 5), minor_band, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 0, 9), minor_band, False
        ) is False
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 2, 0), minor_band, False
        ) is False
        zero_minor_band = self.checked_versionengine.parse_range("^0.0.x")
        assert zero_minor_band.raw_text == "^0.0.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 0, 5), zero_minor_band, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 1, 0), zero_minor_band, False
        ) is False
        major_band = self.checked_versionengine.parse_range("^0.x")
        assert major_band.raw_text == "^0.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 5, 0), major_band, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0), major_band, False
        ) is False

    def test_parse_range_intersections(self) -> None:
        """Requires every comparator of a clause, including same-side bounds."""
        lower_intersection = self.checked_versionengine.parse_range(
            ">=1.0.0 >=1.5.0"
        )
        assert lower_intersection.raw_text == ">=1.0.0 >=1.5.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 4, 0), lower_intersection, False
        ) is False
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), lower_intersection, False
        ) is True
        upper_intersection = self.checked_versionengine.parse_range(
            "<1.9.0 <2.0.0"
        )
        assert upper_intersection.raw_text == "<1.9.0 <2.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 8, 0), upper_intersection, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 9, 0), upper_intersection, False
        ) is False
        coincident = self.checked_versionengine.parse_range(">1.5.0 <1.5.0")
        assert coincident.raw_text == ">1.5.0 <1.5.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), coincident, False
        ) is False
        identical_lower = self.checked_versionengine.parse_range(">=1.5.0 >=1.5.0")
        assert identical_lower.raw_text == ">=1.5.0 >=1.5.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), identical_lower, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 4, 9), identical_lower, False
        ) is False
        tighter_first_lower = self.checked_versionengine.parse_range(
            ">=1.5.0 >=1.0.0"
        )
        assert tighter_first_lower.raw_text == ">=1.5.0 >=1.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 4, 9), tighter_first_lower, False
        ) is False
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), tighter_first_lower, False
        ) is True
        band_then_looser = self.checked_versionengine.parse_range("1.2.x >=1.0.0")
        assert band_then_looser.raw_text == "1.2.x >=1.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 1, 0), band_then_looser, False
        ) is False
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 5), band_then_looser, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 3, 0), band_then_looser, False
        ) is False
        bounded_then_unbounded = self.checked_versionengine.parse_range(
            "<2.0.0 >1.0.0"
        )
        assert bounded_then_unbounded.raw_text == "<2.0.0 >1.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 9, 9), bounded_then_unbounded, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), bounded_then_unbounded, False
        ) is False
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0), bounded_then_unbounded, False
        ) is False
        tighter_second_upper = self.checked_versionengine.parse_range(
            "<2.0.0 <1.5.0"
        )
        assert tighter_second_upper.raw_text == "<2.0.0 <1.5.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 4, 9), tighter_second_upper, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), tighter_second_upper, False
        ) is False
        identical_upper = self.checked_versionengine.parse_range("<=1.5.0 <=1.5.0")
        assert identical_upper.raw_text == "<=1.5.0 <=1.5.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), identical_upper, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 1), identical_upper, False
        ) is False

    def test_parse_range_wildcards(self) -> None:
        """Expands every wildcard range form into bounded intervals."""
        any_star = self.checked_versionengine.parse_range("*")
        assert any_star.raw_text == "*"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(5, 4, 3), any_star, False
        ) is True
        any_x = self.checked_versionengine.parse_range("x")
        assert any_x.raw_text == "x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 0, 1), any_x, False
        ) is True
        any_upper = self.checked_versionengine.parse_range("X")
        assert any_upper.raw_text == "X"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(9, 9, 9), any_upper, False
        ) is True
        major_wildcard = self.checked_versionengine.parse_range("1.x")
        assert major_wildcard.raw_text == "1.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), major_wildcard, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), major_wildcard, False
        ) is False
        major_star = self.checked_versionengine.parse_range("1.*")
        assert major_star.raw_text == "1.*"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 9, 9), major_star, False
        ) is True
        minor_wildcard = self.checked_versionengine.parse_range("1.2.x")
        assert minor_wildcard.raw_text == "1.2.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 9), minor_wildcard, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 3, 0), minor_wildcard, False
        ) is False
        minor_star = self.checked_versionengine.parse_range("1.2.*")
        assert minor_star.raw_text == "1.2.*"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 2, 0), minor_star, False
        ) is True

    def test_parse_range_hyphen_and_unions(self) -> None:
        """Parses hyphen spans, wildcard endpoints, reversed spans, and unions."""
        hyphen = self.checked_versionengine.parse_range("1.2.3 - 2.0.0")
        assert hyphen.raw_text == "1.2.3 - 2.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), hyphen, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), hyphen, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 1), hyphen, False
        ) is False
        wildcard_endpoint = self.checked_versionengine.parse_range("1.2.x - 2.x")
        assert wildcard_endpoint.raw_text == "1.2.x - 2.x"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), wildcard_endpoint, False
        ) is True
        point_span = self.checked_versionengine.parse_range("1.5.0 - 1.5.0")
        assert point_span.raw_text == "1.5.0 - 1.5.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), point_span, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 1), point_span, False
        ) is False
        reversed_span = self.checked_versionengine.parse_range("2.0.0 - 1.0.0")
        assert reversed_span.raw_text == "2.0.0 - 1.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), reversed_span, False
        ) is False
        prerelease_span = self.checked_versionengine.parse_range(
            "1.0.0-alpha - 1.0.0"
        )
        assert prerelease_span.raw_text == "1.0.0-alpha - 1.0.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0, ("alpha",)), prerelease_span, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0, ("alpha",)), prerelease_span, True
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0), prerelease_span, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 9, 9), prerelease_span, False
        ) is False
        universal_span = self.checked_versionengine.parse_range("* - *")
        assert universal_span.raw_text == "* - *"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(5, 4, 3), universal_span, False
        ) is True
        union = self.checked_versionengine.parse_range(">=1.0.0 || ==2.5.0")
        assert union.raw_text == ">=1.0.0 || ==2.5.0"
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 3, 0), union, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 5, 0), union, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 4, 0), union, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(0, 9, 0), union, False
        ) is False

    def test_satisfies_bounds_and_wildcards(self) -> None:
        """Evaluates lower bounds, exclusive boundaries, and wildcard semantics."""
        lower_bound = self.checked_versionengine.parse_range(">=2.0.0")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 9, 9), lower_bound, False
        ) is False
        exclusive_upper = self.checked_versionengine.parse_range("<2.0.0")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), exclusive_upper, False
        ) is False
        exclusive_lower = self.checked_versionengine.parse_range(">1.0.0")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0), exclusive_lower, False
        ) is False
        wildcard = self.checked_versionengine.parse_range("1.x")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 0, 0), wildcard, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 99, 99), wildcard, False
        ) is True
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(2, 0, 0), wildcard, False
        ) is False
        unsatisfiable = self.checked_versionengine.parse_range(">2.0.0 <1.0.0")
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(1, 5, 0), unsatisfiable, False
        ) is False
        assert self.checked_versionengine.satisfies(
            semver_solver.Version(3, 0, 0), unsatisfiable, False
        ) is False

    def test_satisfies_prerelease_gating(self) -> None:
        """Gates prerelease candidates with and without same-core explicit targets."""
        plain = self.checked_versionengine.parse_range(">=1.0.0")
        prerelease_candidate = semver_solver.Version(1, 1, 0, ("beta",))
        assert self.checked_versionengine.satisfies(
            prerelease_candidate, plain, False
        ) is False
        assert self.checked_versionengine.satisfies(
            prerelease_candidate, plain, True
        ) is True
        targeted = self.checked_versionengine.parse_range(">=1.0.0-alpha <1.0.0")
        same_core = semver_solver.Version(1, 0, 0, ("alpha",))
        assert self.checked_versionengine.satisfies(
            same_core, targeted, False
        ) is True
        assert self.checked_versionengine.satisfies(
            same_core, targeted, True
        ) is True
        below = semver_solver.Version(0, 9, 0, ("alpha",))
        assert self.checked_versionengine.satisfies(
            below, plain, False
        ) is False

    def test_repository_release_ordering(self) -> None:
        """Registers releases and retrieves them in descending precedence order."""
        older = semver_solver.PackageRelease("alpha", semver_solver.Version(1, 0, 0), ())
        newer = semver_solver.PackageRelease("alpha", semver_solver.Version(2, 0, 0), ())
        self.checked_packagerepository.register_package(older)
        self.checked_packagerepository.register_package(newer)
        assert self.checked_packagerepository.has_package("alpha") is True
        assert self.checked_packagerepository.has_package("missing") is False
        releases = self.checked_packagerepository.get_releases("alpha")
        assert len(releases) == 2
        assert releases[0].version == semver_solver.Version(2, 0, 0)
        assert releases[1].version == semver_solver.Version(1, 0, 0)
        assert self.checked_packagerepository.all_packages() == {"alpha"}

    def test_resolve_root_dependency(self) -> None:
        """Resolves a direct dependency onto the highest compatible release."""
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease("alpha", semver_solver.Version(1, 0, 0), ())
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease("alpha", semver_solver.Version(1, 2, 0), ())
        )
        root = semver_solver.PackageDependency(
            "alpha", self.checked_versionengine.parse_range(">=1.0.0")
        )
        outcome = self.checked_dependencysolver.resolve([root])
        assert outcome.selected_versions["alpha"] == semver_solver.Version(1, 2, 0)
        assert len(outcome.selected_versions) == 1
        assert len(outcome.derivation_steps) >= 1

    def test_resolve_transitive_dependency(self) -> None:
        """Resolves transitive dependencies declared by a selected release."""
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease("alpha", semver_solver.Version(1, 2, 0), ())
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                "beta",
                semver_solver.Version(2, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "alpha", semver_solver.VersionRange("^1.0.0")
                    ),
                ),
            )
        )
        root = semver_solver.PackageDependency(
            "beta", self.checked_versionengine.parse_range(">=2.0.0")
        )
        outcome = self.checked_dependencysolver.resolve([root])
        assert outcome.selected_versions["beta"] == semver_solver.Version(2, 0, 0)
        assert outcome.selected_versions["alpha"] == semver_solver.Version(1, 2, 0)
        assert len(outcome.derivation_steps) >= 2

    def test_resolve_backtracks_over_unregistered_dependency(self) -> None:
        """Abandons a highest release whose transitive dependency is unregistered."""
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(2, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "ghost", semver_solver.VersionRange(">=1.0.0")
                    ),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease("app", semver_solver.Version(1, 0, 0), ())
        )
        root = semver_solver.PackageDependency(
            "app", self.checked_versionengine.parse_range(">=1.0.0")
        )
        outcome = self.checked_dependencysolver.resolve([root])
        assert outcome.selected_versions["app"] == semver_solver.Version(1, 0, 0)
        assert "ghost" not in outcome.selected_versions
        assert len(outcome.derivation_steps) >= 1

    def test_resolve_backtracks_over_unsatisfiable_dependency(self) -> None:
        """Abandons a highest release whose transitive dependency has no candidate."""
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease("lib", semver_solver.Version(1, 0, 0), ())
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(2, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "lib", semver_solver.VersionRange(">=2.0.0")
                    ),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease("app", semver_solver.Version(1, 0, 0), ())
        )
        root = semver_solver.PackageDependency(
            "app", self.checked_versionengine.parse_range(">=1.0.0")
        )
        outcome = self.checked_dependencysolver.resolve([root])
        assert outcome.selected_versions["app"] == semver_solver.Version(1, 0, 0)
        assert len(outcome.derivation_steps) >= 1

    def test_resolve_backtracks_against_assigned_release(self) -> None:
        """Recovers when a candidate conflicts with an already-assigned release."""
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease("lib", semver_solver.Version(2, 0, 0), ())
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(2, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "lib", semver_solver.VersionRange("<1.0.0")
                    ),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(1, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "lib", semver_solver.VersionRange(">=1.0.0")
                    ),
                ),
            )
        )
        app_root = semver_solver.PackageDependency(
            "app", self.checked_versionengine.parse_range(">=1.0.0")
        )
        lib_root = semver_solver.PackageDependency(
            "lib", self.checked_versionengine.parse_range(">=1.0.0")
        )
        outcome = self.checked_dependencysolver.resolve([app_root, lib_root])
        assert outcome.selected_versions["app"] == semver_solver.Version(1, 0, 0)
        assert outcome.selected_versions["lib"] == semver_solver.Version(2, 0, 0)
        assert len(outcome.derivation_steps) >= 2

    def test_resolve_backtracks_exhausted_intermediate(self) -> None:
        """Recovers after every candidate of an intermediate package is rejected."""
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease("leaf", semver_solver.Version(1, 0, 0), ())
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                "mid",
                semver_solver.Version(2, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "leaf", semver_solver.VersionRange(">=2.0.0")
                    ),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                "mid",
                semver_solver.Version(1, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "leaf", semver_solver.VersionRange(">=2.0.0")
                    ),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                "top",
                semver_solver.Version(2, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "mid", semver_solver.VersionRange(">=1.0.0")
                    ),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease("top", semver_solver.Version(1, 0, 0), ())
        )
        root = semver_solver.PackageDependency(
            "top", self.checked_versionengine.parse_range(">=1.0.0")
        )
        outcome = self.checked_dependencysolver.resolve([root])
        assert outcome.selected_versions["top"] == semver_solver.Version(1, 0, 0)
        assert "mid" not in outcome.selected_versions
        assert "leaf" not in outcome.selected_versions
        assert len(outcome.derivation_steps) >= 1


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
        self.__dict__["_services"] = (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
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
# LAST_CLEANED: 2026-11-04T22:20:47Z
# LAST_CHANGED: 2026-11-04T22:20:12Z
# CHANGE: Add the remaining conjunctive clause orderings: tighter lower bound stated first followed by a looser lower bound (retains the tighter bound, rejecting candidates between the bounds), and a bounded wildcard band stated first followed by a looser relational lower bound (retains the band's lower and upper bounds).
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T22:20:47Z
# PRETENSE_QA_AUDIT: 2026-11-04T22:20:36Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
import re
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
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
# 0. Abstract Model Helpers
# ==============================================================================
# The state machine models the abstract outcome of each operation. These helpers
# compute that outcome from model state and transition arguments; the pivot
# (``) realizes the concrete target result during checked and
# fuzz execution, so transitions never compare a realized return with an
# abstract stand-in.

_VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)
_HYPHEN_RE = re.compile(r"^(?P<low>\S+)\s+-\s+(?P<high>\S+)$")
_WILDCARDS = frozenset({"*", "x", "X"})

PartialParts = Tuple[List[int], Tuple[str, ...], Tuple[str, ...], bool]
Comparators = List[Tuple[str, Version]]


def _model_parse_version(text: str) -> Optional[Version]:
    """Parses SemVer text into an abstract Version, or None when unparseable."""
    match = _VERSION_RE.match(text.strip())
    if match is None:
        return None
    prerelease_text = match.group("prerelease") or ""
    build_text = match.group("build") or ""
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build = tuple(build_text.split(".")) if build_text else ()
    if any(segment == "" for segment in prerelease):
        return None
    return Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
        build,
    )


def _model_compare_versions(v1: Version, v2: Version) -> int:
    """Returns the SemVer precedence ordering sign between two versions."""
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
        if left.isdigit() and right.isdigit():
            if int(left) != int(right):
                return -1 if int(left) < int(right) else 1
        elif left.isdigit() != right.isdigit():
            return -1 if left.isdigit() else 1
        elif left != right:
            return -1 if left < right else 1
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


def _model_compare_releases(left: PackageRelease, right: PackageRelease) -> int:
    return _model_compare_versions(left.version, right.version)


def _model_sorted_releases(releases: Sequence[PackageRelease]) -> List[PackageRelease]:
    """Orders releases by descending version precedence."""
    return sorted(
        releases,
        key=cmp_to_key(_model_compare_releases),
        reverse=True,
    )


def _model_parse_partial(text: str) -> Optional[PartialParts]:
    """Parses a full version, a partial version, or a wildcard expression."""
    body = text.strip()
    if body in _WILDCARDS:
        return ([], (), (), True)
    match = _VERSION_RE.match(body)
    if match is not None:
        prerelease_text = match.group("prerelease") or ""
        build_text = match.group("build") or ""
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build = tuple(build_text.split(".")) if build_text else ()
        return (
            [
                int(match.group("major")),
                int(match.group("minor")),
                int(match.group("patch")),
            ],
            prerelease,
            build,
            False,
        )
    numbers: List[int] = []
    for segment in body.split("."):
        if segment in _WILDCARDS:
            return (numbers, (), (), True)
        if not segment.isdigit():
            return None
        numbers.append(int(segment))
    if not numbers:
        return None
    return (numbers, (), (), False)


def _model_lower_bound(numbers: Sequence[int]) -> Version:
    padded = list(numbers) + [0, 0, 0]
    return Version(padded[0], padded[1], padded[2])


def _model_upper_bound(numbers: Sequence[int]) -> Version:
    if not numbers:
        return Version(0, 0, 0)
    if len(numbers) == 1:
        return Version(numbers[0] + 1, 0, 0)
    return Version(numbers[0], numbers[1] + 1, 0)


def _model_prefix_comparators(body: str, kind: str) -> Optional[Comparators]:
    partial = _model_parse_partial(body)
    if partial is None:
        return None
    numbers, prerelease, build, wildcard = partial
    if wildcard or not numbers:
        return None
    if len(numbers) >= 3:
        lower = Version(numbers[0], numbers[1], numbers[2], prerelease, build)
    else:
        lower = _model_lower_bound(numbers)
    if kind == "caret":
        if len(numbers) == 1 or numbers[0] > 0:
            upper = Version(numbers[0] + 1, 0, 0)
        elif numbers[1] > 0:
            upper = Version(0, numbers[1] + 1, 0)
        elif len(numbers) >= 3:
            upper = Version(0, 0, numbers[2] + 1)
        else:
            upper = Version(0, 1, 0)
    else:
        if len(numbers) == 1:
            upper = Version(numbers[0] + 1, 0, 0)
        else:
            upper = Version(numbers[0], numbers[1] + 1, 0)
    return [(">=", lower), ("<", upper)]


def _model_token_comparators(token: str) -> Optional[Comparators]:
    """Expands one whitespace-delimited range token into comparators."""
    if token.startswith("^"):
        return _model_prefix_comparators(token[1:], "caret")
    if token.startswith("~"):
        return _model_prefix_comparators(token[1:], "tilde")
    operator = ""
    body = token
    for candidate in (">=", "<=", "==", "!=", ">", "<", "="):
        if body.startswith(candidate):
            operator = candidate
            body = body[len(candidate):]
            break
    if not body:
        return None
    partial = _model_parse_partial(body)
    if partial is None:
        return None
    numbers, prerelease, build, wildcard = partial
    if body.strip() in _WILDCARDS:
        return [(">=", Version(0, 0, 0))]
    if wildcard or len(numbers) < 3:
        lower = _model_lower_bound(numbers)
        upper = _model_upper_bound(numbers)
        if operator == "!=":
            return [("<", lower), (">=", upper)]
        if operator in (">", ">="):
            return [(operator, lower)]
        if operator in ("<", "<="):
            return [(operator, upper)]
        return [(">=", lower), ("<", upper)]
    version = Version(numbers[0], numbers[1], numbers[2], prerelease, build)
    if operator in ("", "=", "=="):
        return [("==", version)]
    return [(operator, version)]


def _model_clause_comparators(clause: str) -> Optional[Comparators]:
    """Expands one union clause into its conjunctive comparator set."""
    hyphen = _HYPHEN_RE.match(clause)
    if hyphen is not None:
        low = _model_parse_version(hyphen.group("low"))
        high = _model_parse_version(hyphen.group("high"))
        if low is None or high is None:
            return None
        return [(">=", low), ("<=", high)]
    comparators: Comparators = []
    for token in clause.split():
        expanded = _model_token_comparators(token)
        if expanded is None:
            return None
        comparators.extend(expanded)
    if not comparators:
        return None
    return comparators


def _model_check_comparator(version: Version, comparator: Tuple[str, Version]) -> bool:
    operator, bound = comparator
    result = _model_compare_versions(version, bound)
    if operator in ("=", "=="):
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


def _model_targets_prerelease(version: Version, comparators: Comparators) -> bool:
    for _, bound in comparators:
        if not bound.prerelease:
            continue
        if (bound.major, bound.minor, bound.patch) == (
            version.major,
            version.minor,
            version.patch,
        ):
            return True
    return False


def _model_satisfies(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    """Evaluates a candidate version against disjoint union comparator clauses."""
    text = range_constraint.raw_text.strip()
    if not text:
        return False
    for clause in text.split("||"):
        trimmed = clause.strip()
        if not trimmed:
            continue
        comparators = _model_clause_comparators(trimmed)
        if comparators is None:
            continue
        if not all(
            _model_check_comparator(version, comparator)
            for comparator in comparators
        ):
            continue
        if version.prerelease and not include_prerelease:
            if not _model_targets_prerelease(version, comparators):
                continue
        return True
    return False


def _model_search(
    packages: Mapping[str, List[PackageRelease]],
    constraints: Dict[str, List[VersionRange]],
    assignment: Dict[str, PackageRelease],
    steps: List[str],
) -> Optional[Tuple[Dict[str, PackageRelease], List[str]]]:
    """Depth-first minimum-remaining-values search over accumulated constraints."""
    unassigned = [name for name in constraints if name not in assignment]
    if not unassigned:
        return (dict(assignment), list(steps))
    candidates: Dict[str, List[PackageRelease]] = {}
    for name in unassigned:
        ranges = constraints[name]
        candidates[name] = [
            release
            for release in packages.get(name, [])
            if all(
                _model_satisfies(release.version, pending, False)
                for pending in ranges
            )
        ]
    chosen = min(unassigned, key=lambda item: (len(candidates[item]), item))
    for release in candidates[chosen]:
        next_assignment = dict(assignment)
        next_assignment[chosen] = release
        next_steps = list(steps) + [f"Assign '{chosen}' to {release.version}"]
        next_constraints = {
            name: list(ranges) for name, ranges in constraints.items()
        }
        conflict = False
        for dependency in release.dependencies:
            if dependency.name in next_assignment:
                assigned = next_assignment[dependency.name]
                if not _model_satisfies(
                    assigned.version, dependency.range_constraint, False
                ):
                    conflict = True
                    break
            else:
                next_constraints.setdefault(dependency.name, []).append(
                    dependency.range_constraint
                )
        if conflict:
            continue
        found = _model_search(
            packages, next_constraints, next_assignment, next_steps
        )
        if found is not None:
            return found
    return None


def _model_resolve(
    packages: Mapping[str, List[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome:
    """Selects the highest compatible release assignment for root dependencies."""
    constraints: Dict[str, List[VersionRange]] = {}
    for dependency in root_dependencies:
        constraints.setdefault(dependency.name, []).append(
            dependency.range_constraint
        )
    result = _model_search(packages, constraints, {}, [])
    if result is None:
        return ResolutionOutcome(selected_versions={}, derivation_steps=())
    assignment, steps = result
    selected = {
        name: release.version for name, release in assignment.items()
    }
    return ResolutionOutcome(selected_versions=selected, derivation_steps=tuple(steps))


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted outcomes live naturally inside the single
# transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real
# calls); use Domain.type(T) for open domains and preferred=[...] to bias fuzzing.


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    parsed_versions: List[Version] = field(default_factory=list)
    parsed_ranges: List[VersionRange] = field(default_factory=list)
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    prerelease_flags: List[bool] = field(default_factory=list)
    outcomes: List[ResolutionOutcome] = field(default_factory=list)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.type(str), preferred=["1.0.0", "2.3.4"])
        parsed = _model_parse_version(text)
        if parsed is None:
            parsed = Version(0, 0, 0)
        ret = self.inner_parse_version(text)
        self.state.parsed_versions.append(parsed)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version), preferred=[Version(1, 0, 0)])
        require_arg(v2, Domain.type(Version), preferred=[Version(2, 0, 0)])
        ordering = _model_compare_versions(v1, v2)
        ret = self.inner_compare_precedence(v1, v2)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.type(str), preferred=[">=1.0.0", "^1.2.0"])
        trimmed = text.strip()
        parsed = VersionRange(trimmed)
        ret = self.inner_parse_range(text)
        self.state.parsed_ranges.append(parsed)
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.type(Version), preferred=[Version(1, 0, 0)])
        require_arg(
            range_constraint,
            Domain.type(VersionRange),
            preferred=[VersionRange(">=1.0.0")],
        )
        require_arg(include_prerelease, Domain.boolean(), preferred=[False])
        matched = _model_satisfies(version, range_constraint, include_prerelease)
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        self.state.prerelease_flags.append(include_prerelease)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require_arg(
            release,
            Domain.type(PackageRelease),
            preferred=[PackageRelease("alpha", Version(1, 0, 0), ())],
        )
        bucket = self.state.packages.setdefault(release.name, [])
        bucket.append(release)
        bucket[:] = _model_sorted_releases(bucket)
        ret = self.inner_register_package(release)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["alpha"])
        releases = _model_sorted_releases(self.state.packages.get(name, []))
        ret = self.inner_get_releases(name)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["alpha"])
        present = name in self.state.packages
        ret = self.inner_has_package(name)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        names = set(self.state.packages.keys())
        ret = self.inner_all_packages()
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            Domain.type(Sequence[PackageDependency]),
            preferred=[[PackageDependency("alpha", VersionRange(">=1.0.0"))]],
        )
        outcome = _model_resolve(self.state.packages, root_dependencies)
        ret = self.inner_resolve(root_dependencies)
        self.state.outcomes.append(outcome)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Transition a blank state into an initialized model state."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(
    state: Optional[SemverSolverState] = None,
) -> Any:
    """Builds a synthesized fake double implementing the SemverSolver protocols."""
    return FakeSemverSolver(state=state or SemverSolverState())


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[Any, Any, Any]:
    """Builds fake doubles for the engine, repository, and solver contracts."""
    fake = make_semver_solver_fake(state)
    return (fake, fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_solver_fake()
        self.sm = SemverSolverStateMachine()

    def test_seeding_transition(self) -> None:
        """Exercises the seeding transition that initializes model state."""
        self.sm.seed_initial()
        assert self.sm.state.initialized

    def test_parse_version_transition(self) -> None:
        """Exercises the parsing transition and its identifier extraction."""
        parsed = self.fake.parse_version("1.2.3-alpha.1+build.9")
        assert parsed.major == 1
        assert parsed.minor == 2
        assert parsed.patch == 3
        assert parsed.prerelease == ("alpha", "1")
        assert parsed.build == ("build", "9")

    def test_compare_precedence_transition(self) -> None:
        """Exercises the precedence transition across numeric and prerelease ordering."""
        assert self.fake.compare_precedence(Version(0, 0, 0), Version(2, 0, 0)) < 0
        assert self.fake.compare_precedence(Version(2, 0, 0), Version(0, 0, 0)) > 0
        assert self.fake.compare_precedence(Version(1, 0, 0), Version(1, 0, 0)) == 0
        prerelease_ordering = self.fake.compare_precedence(
            Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)
        )
        assert prerelease_ordering < 0

    def test_parse_range_transition(self) -> None:
        """Exercises the range parsing transition and its whitespace trimming."""
        parsed = self.fake.parse_range("  >=1.0.0 <2.0.0  ")
        assert parsed.raw_text == ">=1.0.0 <2.0.0"

    def test_satisfies_transition(self) -> None:
        """Exercises the range evaluation transition and comparator boundaries."""
        bounded = VersionRange(">=1.0.0 <2.0.0")
        assert self.fake.satisfies(Version(1, 5, 0), bounded, False) is True
        assert self.fake.satisfies(Version(2, 0, 0), bounded, False) is False
        assert self.fake.satisfies(Version(0, 9, 0), bounded, False) is False

    def test_repository_transitions(self) -> None:
        """Exercises every PackageRepository transition on the fake."""
        self.fake.register_package(PackageRelease("alpha", Version(1, 0, 0), ()))
        self.fake.register_package(PackageRelease("alpha", Version(2, 0, 0), ()))
        assert self.fake.has_package("alpha") is True
        assert self.fake.has_package("missing") is False
        releases = self.fake.get_releases("alpha")
        assert len(releases) == 2
        assert releases[0].version == Version(2, 0, 0)
        assert releases[1].version == Version(1, 0, 0)
        assert self.fake.all_packages() == {"alpha"}

    def test_solver_transitions(self) -> None:
        """Exercises every DependencySolver transition on the fake."""
        self.fake.register_package(PackageRelease("alpha", Version(1, 0, 0), ()))
        self.fake.register_package(PackageRelease("alpha", Version(1, 2, 0), ()))
        outcome = self.fake.resolve(
            [PackageDependency("alpha", VersionRange(">=1.0.0"))]
        )
        assert outcome.selected_versions["alpha"] == Version(1, 2, 0)
        assert len(outcome.derivation_steps) >= 1


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T22:04:43Z
# LAST_CHANGED: 2026-11-04T22:04:43Z
# CHANGE: Remove self-referential conformance assertions from interface transitions; model abstract outcomes instead: SemVer parsing/identifier extraction, precedence ordering, whitespace-trimmed ranges, union/comparator/caret/tilde/wildcard/hyphen satisfies evaluation, descending-precedence release retrieval, and highest-compatible MRV dependency resolution with derivation steps. Pivots now hand abstract outcomes to inner_transition without comparing realized returns.
# --- END AUTOFAB METADATA ---
