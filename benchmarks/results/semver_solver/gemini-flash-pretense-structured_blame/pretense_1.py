# === File: semver_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Collection, List, Set, Tuple
import unittest

from pretense import sut, sut_state
from support.lib.lifecycle import LifecycleTestCase, get_singleton

from semver_solver_gemini_flash_1.parts.semver_solver.lib.semver_solver import (
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
from semver_solver_gemini_flash_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver as DependencySolverImpl,
    PackageRepository as PackageRepositoryImpl,
    VersionEngine as VersionEngineImpl,
)
from semver_solver_gemini_flash_1.parts.semver_solver.pretense.semver_solver_pretense import (
    SemVerSolverStateMachine,
)


class SemVerSolverImplPseudoStateMachine(SemVerSolverStateMachine):
    """Implementation pseudo-state machine for SemVer 2.0 dependency solver."""

    def inner_parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        return target.parse_version(text)

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        return target.compare_precedence(v1, v2)

    def inner_parse_range(self, text: str) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        return target.parse_range(text)

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngine = sut(VersionEngine)
        return target.satisfies(version, range_constraint, include_prerelease)

    def inner_register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        return target.register_package(release)

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        return target.get_releases(name)

    def inner_has_package(self, name: str) -> bool:
        target: PackageRepository = sut(PackageRepository)
        return target.has_package(name)

    def inner_all_packages(self) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        return target.all_packages()

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        return target.resolve(root_dependencies)


class TestSemVerSolverImplReal(LifecycleTestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.version_engine = get_singleton(VersionEngine)
        self.repo = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = SemVerSolverImplPseudoStateMachine(singletons={
            VersionEngine: self.version_engine,
            PackageRepository: self.repo,
            DependencySolver: self.solver,
        })
        self.checked_version_engine = self.sm.as_checked(VersionEngine, self.version_engine)
        self.checked_repo = self.sm.as_checked(PackageRepository, self.repo)
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)
        self.checked = self.checked_solver

    def test_parse_version_conformance(self) -> None:
        v1 = self.checked_version_engine.parse_version("1.2.3")
        assert v1.major == 1
        assert v1.minor == 2
        assert v1.patch == 3
        v2 = self.checked_version_engine.parse_version("2.0.0-alpha.1+build.01")
        assert v2.major == 2
        assert v2.prerelease == ("alpha", "1")
        assert v2.build == ("build", "01")

    def test_compare_precedence_conformance(self) -> None:
        v1 = self.checked_version_engine.parse_version("1.0.0")
        v2 = self.checked_version_engine.parse_version("2.0.0")
        v_pre = self.checked_version_engine.parse_version("1.0.0-alpha")
        v_build = self.checked_version_engine.parse_version("1.0.0+build1")
        assert self.checked_version_engine.compare_precedence(v1, v2) < 0
        assert self.checked_version_engine.compare_precedence(v2, v1) > 0
        assert self.checked_version_engine.compare_precedence(v1, v1) == 0
        assert self.checked_version_engine.compare_precedence(v_pre, v1) < 0
        assert self.checked_version_engine.compare_precedence(v1, v_pre) > 0
        assert self.checked_version_engine.compare_precedence(v1, v_build) == 0

    def test_identical_prerelease_identifier_equality(self) -> None:
        v1 = self.checked_version_engine.parse_version("1.0.0-alpha")
        v2 = self.checked_version_engine.parse_version("1.0.0-alpha")
        assert self.checked_version_engine.compare_precedence(v1, v2) == 0

    def test_compare_precedence_prerelease_ordering(self) -> None:
        v_num = self.checked_version_engine.parse_version("1.0.0-alpha.1")
        v_str = self.checked_version_engine.parse_version("1.0.0-alpha.beta")
        v_num2 = self.checked_version_engine.parse_version("1.0.0-alpha.2")
        v_str2 = self.checked_version_engine.parse_version("1.0.0-alpha.gamma")
        v_short = self.checked_version_engine.parse_version("1.0.0-alpha")

        # Numeric ranks lower than string:
        assert self.checked_version_engine.compare_precedence(v_num, v_str) < 0
        assert self.checked_version_engine.compare_precedence(v_str, v_num) > 0

        # Numeric compared numerically:
        assert self.checked_version_engine.compare_precedence(v_num, v_num2) < 0
        assert self.checked_version_engine.compare_precedence(v_num2, v_num) > 0

        # String compared lexicographically:
        assert self.checked_version_engine.compare_precedence(v_str, v_str2) < 0
        assert self.checked_version_engine.compare_precedence(v_str2, v_str) > 0

        # Shorter prerelease sequence ranks lower than longer:
        assert self.checked_version_engine.compare_precedence(v_short, v_num) < 0
        assert self.checked_version_engine.compare_precedence(v_num, v_short) > 0

    def test_parse_range_conformance(self) -> None:
        r1 = self.checked_version_engine.parse_range(">= 1.0.0")
        assert r1.raw_text == ">= 1.0.0"
        r2 = self.checked_version_engine.parse_range("^1.2.3")
        assert r2.raw_text == "^1.2.3"
        r3 = self.checked_version_engine.parse_range("~1.2.3")
        assert r3.raw_text == "~1.2.3"
        r4 = self.checked_version_engine.parse_range("1.0.0 - 2.x")
        assert r4.raw_text == "1.0.0 - 2.x"
        r5 = self.checked_version_engine.parse_range("1.x || 2.x")
        assert r5.raw_text == "1.x || 2.x"

    def test_range_wildcard_comparators_and_prefixes(self) -> None:
        r_gte = self.checked_version_engine.parse_range(">=1.x")
        v_match = self.checked_version_engine.parse_version("1.5.0")
        v_below = self.checked_version_engine.parse_version("0.9.0")
        assert self.checked_version_engine.satisfies(v_match, r_gte, False)
        assert not self.checked_version_engine.satisfies(v_below, r_gte, False)

        r_ne = self.checked_version_engine.parse_range("!=1.x")
        v_in_1 = self.checked_version_engine.parse_version("1.2.3")
        v_in_2 = self.checked_version_engine.parse_version("2.0.0")
        assert not self.checked_version_engine.satisfies(v_in_1, r_ne, False)
        assert self.checked_version_engine.satisfies(v_in_2, r_ne, False)

        r_gt_wildcard = self.checked_version_engine.parse_range(">1.*")
        assert not self.checked_version_engine.satisfies(v_in_1, r_gt_wildcard, False)
        assert self.checked_version_engine.satisfies(v_in_2, r_gt_wildcard, False)

        r_caret = self.checked_version_engine.parse_range("^1.x")
        assert self.checked_version_engine.satisfies(v_in_1, r_caret, False)
        assert not self.checked_version_engine.satisfies(v_in_2, r_caret, False)

        r_tilde = self.checked_version_engine.parse_range("~1.2.x")
        assert self.checked_version_engine.satisfies(v_in_1, r_tilde, False)
        assert not self.checked_version_engine.satisfies(self.checked_version_engine.parse_version("1.3.0"), r_tilde, False)

        r_star = self.checked_version_engine.parse_range(">=*")
        assert self.checked_version_engine.satisfies(v_in_1, r_star, False)
        assert self.checked_version_engine.satisfies(v_below, r_star, False)

    def test_relational_inequality_comparators(self) -> None:
        r_lt_star = self.checked_version_engine.parse_range("<*")
        v_any = self.checked_version_engine.parse_version("1.0.0")
        assert not self.checked_version_engine.satisfies(v_any, r_lt_star, False)

        r_ne_full = self.checked_version_engine.parse_range("!=1.2.3")
        v_target = self.checked_version_engine.parse_version("1.2.3")
        v_diff = self.checked_version_engine.parse_version("1.2.4")
        assert not self.checked_version_engine.satisfies(v_target, r_ne_full, False)
        assert self.checked_version_engine.satisfies(v_diff, r_ne_full, False)

        r_lte_full = self.checked_version_engine.parse_range("<=1.0.0")
        v_one = self.checked_version_engine.parse_version("1.0.0")
        v_below = self.checked_version_engine.parse_version("0.9.0")
        v_above = self.checked_version_engine.parse_version("1.0.1")
        assert self.checked_version_engine.satisfies(v_one, r_lte_full, False)
        assert self.checked_version_engine.satisfies(v_below, r_lte_full, False)
        assert not self.checked_version_engine.satisfies(v_above, r_lte_full, False)

        r_gt_wild = self.checked_version_engine.parse_range(">1.2.x")
        v_in_wild = self.checked_version_engine.parse_version("1.2.9")
        v_above_wild = self.checked_version_engine.parse_version("1.3.0")
        assert not self.checked_version_engine.satisfies(v_in_wild, r_gt_wild, False)
        assert self.checked_version_engine.satisfies(v_above_wild, r_gt_wild, False)

    def test_caret_zero_major_expansion(self) -> None:
        r_minor = self.checked_version_engine.parse_range("^0.2.3")
        v_cand = self.checked_version_engine.parse_version("0.2.5")
        v_upper = self.checked_version_engine.parse_version("0.3.0")
        v_lower = self.checked_version_engine.parse_version("0.2.2")
        assert self.checked_version_engine.satisfies(v_cand, r_minor, False)
        assert not self.checked_version_engine.satisfies(v_upper, r_minor, False)
        assert not self.checked_version_engine.satisfies(v_lower, r_minor, False)

        r_patch = self.checked_version_engine.parse_range("^0.0.3")
        v_patch_cand = self.checked_version_engine.parse_version("0.0.3")
        v_patch_upper = self.checked_version_engine.parse_version("0.0.4")
        assert self.checked_version_engine.satisfies(v_patch_cand, r_patch, False)
        assert not self.checked_version_engine.satisfies(v_patch_upper, r_patch, False)

        # ^0.2.x: expands to >=0.2.0 <0.3.0
        r_zero_minor_wild = self.checked_version_engine.parse_range("^0.2.x")
        v_zero_two = self.checked_version_engine.parse_version("0.2.0")
        assert self.checked_version_engine.satisfies(v_zero_two, r_zero_minor_wild, False)
        assert self.checked_version_engine.satisfies(v_cand, r_zero_minor_wild, False)
        assert not self.checked_version_engine.satisfies(v_upper, r_zero_minor_wild, False)
        assert not self.checked_version_engine.satisfies(self.checked_version_engine.parse_version("0.1.9"), r_zero_minor_wild, False)

        # ^0.0.x: expands to >=0.0.0 <0.1.0
        r_zero_zero_wild = self.checked_version_engine.parse_range("^0.0.x")
        v_zero_zero_one = self.checked_version_engine.parse_version("0.0.1")
        v_zero_one_zero = self.checked_version_engine.parse_version("0.1.0")
        assert self.checked_version_engine.satisfies(v_zero_zero_one, r_zero_zero_wild, False)
        assert not self.checked_version_engine.satisfies(v_zero_one_zero, r_zero_zero_wild, False)

    def test_whitespace_delimited_multiple_comparators(self) -> None:
        r_multi = self.checked_version_engine.parse_range(">=1.0.0 <2.0.0")
        v_mid = self.checked_version_engine.parse_version("1.5.0")
        v_low = self.checked_version_engine.parse_version("1.0.0")
        v_high = self.checked_version_engine.parse_version("2.0.0")
        v_under = self.checked_version_engine.parse_version("0.9.0")
        assert self.checked_version_engine.satisfies(v_mid, r_multi, False)
        assert self.checked_version_engine.satisfies(v_low, r_multi, False)
        assert not self.checked_version_engine.satisfies(v_high, r_multi, False)
        assert not self.checked_version_engine.satisfies(v_under, r_multi, False)

    def test_minor_wildcard_comparator_inequalities(self) -> None:
        # ^1.2.x: expands to >=1.2.0 <2.0.0
        r_caret = self.checked_version_engine.parse_range("^1.2.x")
        v_caret_match = self.checked_version_engine.parse_version("1.2.5")
        v_caret_under = self.checked_version_engine.parse_version("1.1.9")
        v_caret_over = self.checked_version_engine.parse_version("2.0.0")
        assert self.checked_version_engine.satisfies(v_caret_match, r_caret, False)
        assert not self.checked_version_engine.satisfies(v_caret_under, r_caret, False)
        assert not self.checked_version_engine.satisfies(v_caret_over, r_caret, False)

        # >=1.2.x: expands to >=1.2.0
        r_gte = self.checked_version_engine.parse_range(">=1.2.x")
        v_gte_match = self.checked_version_engine.parse_version("1.2.0")
        v_gte_over = self.checked_version_engine.parse_version("2.5.0")
        assert self.checked_version_engine.satisfies(v_gte_match, r_gte, False)
        assert self.checked_version_engine.satisfies(v_gte_over, r_gte, False)
        assert not self.checked_version_engine.satisfies(v_caret_under, r_gte, False)

        # !=1.2.x: expands to <1.2.0 || >=1.3.0
        r_ne = self.checked_version_engine.parse_range("!=1.2.x")
        v_ne_in = self.checked_version_engine.parse_version("1.2.9")
        v_ne_above = self.checked_version_engine.parse_version("1.3.0")
        assert not self.checked_version_engine.satisfies(v_ne_in, r_ne, False)
        assert self.checked_version_engine.satisfies(v_caret_under, r_ne, False)
        assert self.checked_version_engine.satisfies(v_ne_above, r_ne, False)

        # <1.x: expands to <1.0.0
        r_lt_major = self.checked_version_engine.parse_range("<1.x")
        v_zero = self.checked_version_engine.parse_version("0.9.9")
        v_one = self.checked_version_engine.parse_version("1.0.0")
        assert self.checked_version_engine.satisfies(v_zero, r_lt_major, False)
        assert not self.checked_version_engine.satisfies(v_one, r_lt_major, False)

        # <=1.x: expands to <2.0.0
        r_lte_major = self.checked_version_engine.parse_range("<=1.x")
        v_one_nine = self.checked_version_engine.parse_version("1.9.9")
        assert self.checked_version_engine.satisfies(v_one_nine, r_lte_major, False)
        assert not self.checked_version_engine.satisfies(v_caret_over, r_lte_major, False)

        # >1.0.0: expands to >1.0.0
        r_gt_exact = self.checked_version_engine.parse_range(">1.0.0")
        v_just_over = self.checked_version_engine.parse_version("1.0.1")
        assert self.checked_version_engine.satisfies(v_just_over, r_gt_exact, False)
        assert not self.checked_version_engine.satisfies(v_one, r_gt_exact, False)
        assert not self.checked_version_engine.satisfies(v_zero, r_gt_exact, False)

        # <=1.2.x, <1.2.x, >1.2.x
        r_lte = self.checked_version_engine.parse_range("<=1.2.x")
        v_match = self.checked_version_engine.parse_version("1.2.9")
        v_over = self.checked_version_engine.parse_version("1.3.0")
        assert self.checked_version_engine.satisfies(v_match, r_lte, False)
        assert not self.checked_version_engine.satisfies(v_over, r_lte, False)

        r_lt = self.checked_version_engine.parse_range("<1.2.x")
        v_prior = self.checked_version_engine.parse_version("1.1.9")
        assert self.checked_version_engine.satisfies(v_prior, r_lt, False)
        assert not self.checked_version_engine.satisfies(v_match, r_lt, False)

        r_gt = self.checked_version_engine.parse_range(">1.2.x")
        assert self.checked_version_engine.satisfies(v_over, r_gt, False)
        assert not self.checked_version_engine.satisfies(v_match, r_gt, False)

    def test_hyphen_range_expansion_with_wildcards(self) -> None:
        r_hyphen = self.checked_version_engine.parse_range("1.x - 2.x")
        v_cand = self.checked_version_engine.parse_version("2.1.0")
        v_low = self.checked_version_engine.parse_version("0.9.0")
        v_high = self.checked_version_engine.parse_version("3.0.0")
        assert self.checked_version_engine.satisfies(v_cand, r_hyphen, False)
        assert not self.checked_version_engine.satisfies(v_low, r_hyphen, False)
        assert not self.checked_version_engine.satisfies(v_high, r_hyphen, False)

        r_hyphen_mixed = self.checked_version_engine.parse_range("1.0.0 - 2.x")
        assert self.checked_version_engine.satisfies(v_cand, r_hyphen_mixed, False)
        assert not self.checked_version_engine.satisfies(self.checked_version_engine.parse_version("0.9.9"), r_hyphen_mixed, False)
        assert not self.checked_version_engine.satisfies(v_high, r_hyphen_mixed, False)

    def test_hyphen_range_wildcard_bound_combinations(self) -> None:
        r_star_upper = self.checked_version_engine.parse_range("* - 2.0.0")
        v_two = self.checked_version_engine.parse_version("2.0.0")
        v_two_one = self.checked_version_engine.parse_version("2.0.1")
        assert self.checked_version_engine.satisfies(v_two, r_star_upper, False)
        assert not self.checked_version_engine.satisfies(v_two_one, r_star_upper, False)

        r_lower_star = self.checked_version_engine.parse_range("1.0.0 - *")
        v_one = self.checked_version_engine.parse_version("1.0.0")
        v_zero = self.checked_version_engine.parse_version("0.9.9")
        assert self.checked_version_engine.satisfies(v_one, r_lower_star, False)
        assert not self.checked_version_engine.satisfies(v_zero, r_lower_star, False)

        r_wild_wild = self.checked_version_engine.parse_range("1.2.x - 2.3.x")
        v_mid = self.checked_version_engine.parse_version("2.3.9")
        v_low = self.checked_version_engine.parse_version("1.1.9")
        v_high = self.checked_version_engine.parse_version("2.4.0")
        assert self.checked_version_engine.satisfies(v_mid, r_wild_wild, False)
        assert not self.checked_version_engine.satisfies(v_low, r_wild_wild, False)
        assert not self.checked_version_engine.satisfies(v_high, r_wild_wild, False)

    def test_satisfies_conformance(self) -> None:
        v1 = self.checked_version_engine.parse_version("1.2.3")
        v_pre = self.checked_version_engine.parse_version("1.2.3-alpha")
        r1 = self.checked_version_engine.parse_range(">=1.0.0")
        assert self.checked_version_engine.satisfies(v1, r1, False)
        assert not self.checked_version_engine.satisfies(v_pre, r1, False)
        assert self.checked_version_engine.satisfies(v_pre, r1, True)

    def test_repository_conformance(self) -> None:
        rel1 = PackageRelease("pkg_repo", Version(1, 0, 0))
        rel2 = PackageRelease("pkg_repo", Version(2, 0, 0))
        self.checked_repo.register_package(rel1)
        self.checked_repo.register_package(rel2)
        assert self.checked_repo.has_package("pkg_repo")
        assert not self.checked_repo.has_package("unknown_pkg")
        assert "pkg_repo" in self.checked_repo.all_packages()
        releases = self.checked_repo.get_releases("pkg_repo")
        assert len(releases) == 2
        assert releases[0].version.major == 2
        assert releases[1].version.major == 1

    def test_duplicate_version_registration(self) -> None:
        rel1 = PackageRelease("pkg", Version(1, 0, 0))
        rel2 = PackageRelease("pkg", Version(1, 0, 0))
        self.checked_repo.register_package(rel1)
        self.checked_repo.register_package(rel2)
        releases = self.checked_repo.get_releases("pkg")
        assert len(releases) >= 1
        assert releases[0].version == Version(1, 0, 0)

    def test_dependency_solver_conformance(self) -> None:
        dep_b = PackageDependency("dep_b", VersionRange(">=1.0.0"))
        rel_a = PackageRelease("solv_a", Version(1, 0, 0), dependencies=(dep_b,))
        rel_b1 = PackageRelease("dep_b", Version(1, 0, 0))
        rel_b2 = PackageRelease("dep_b", Version(2, 0, 0))
        self.checked_repo.register_package(rel_a)
        self.checked_repo.register_package(rel_b1)
        self.checked_repo.register_package(rel_b2)
        outcome = self.checked_solver.resolve([
            PackageDependency("solv_a", VersionRange(">=1.0.0")),
        ])
        assert "solv_a" in outcome.selected_versions
        assert "dep_b" in outcome.selected_versions
        assert outcome.selected_versions["dep_b"].major == 2

    def test_backtracking_search_conflict_rollback(self) -> None:
        # A 2.0.0 requires B >= 2.0.0 (which cannot be satisfied because B only has 1.0.0)
        # A 1.0.0 requires B >= 1.0.0 (which is satisfied by B 1.0.0)
        dep_b_v2 = PackageDependency("pkg_b", VersionRange(">=2.0.0"))
        rel_a_v2 = PackageRelease("pkg_a", Version(2, 0, 0), dependencies=(dep_b_v2,))
        dep_b_v1 = PackageDependency("pkg_b", VersionRange(">=1.0.0"))
        rel_a_v1 = PackageRelease("pkg_a", Version(1, 0, 0), dependencies=(dep_b_v1,))
        rel_b_v1 = PackageRelease("pkg_b", Version(1, 0, 0))

        self.checked_repo.register_package(rel_a_v2)
        self.checked_repo.register_package(rel_a_v1)
        self.checked_repo.register_package(rel_b_v1)

        outcome = self.checked_solver.resolve([
            PackageDependency("pkg_a", VersionRange(">=1.0.0")),
        ])
        assert outcome.selected_versions["pkg_a"].major == 1
        assert outcome.selected_versions["pkg_b"].major == 1

    def test_solver_cross_package_conflict_assigned_pkg(self) -> None:
        # Root requires pkg_root
        # pkg_root requires pkg_y >= 1.0.0 and pkg_x >= 1.0.0
        # pkg_y has only 1 release: 1.0.0 (MRV picks pkg_y first with 1 candidate)
        # pkg_x has 2 releases: 2.0.0 and 1.0.0 (MRV picks pkg_x second)
        # pkg_x 2.0.0 requires pkg_y >= 2.0.0 (conflicts with already-assigned pkg_y 1.0.0)
        # pkg_x 1.0.0 requires pkg_y == 1.0.0 (compatible with assigned pkg_y 1.0.0)
        dep_y = PackageDependency("pkg_y", VersionRange(">=1.0.0"))
        dep_x = PackageDependency("pkg_x", VersionRange(">=1.0.0"))
        rel_root = PackageRelease("pkg_root", Version(1, 0, 0), dependencies=(dep_y, dep_x))

        rel_y_1 = PackageRelease("pkg_y", Version(1, 0, 0))

        dep_y_conflict = PackageDependency("pkg_y", VersionRange(">=2.0.0"))
        rel_x_2 = PackageRelease("pkg_x", Version(2, 0, 0), dependencies=(dep_y_conflict,))

        dep_y_compat = PackageDependency("pkg_y", VersionRange("==1.0.0"))
        rel_x_1 = PackageRelease("pkg_x", Version(1, 0, 0), dependencies=(dep_y_compat,))

        self.checked_repo.register_package(rel_root)
        self.checked_repo.register_package(rel_y_1)
        self.checked_repo.register_package(rel_x_2)
        self.checked_repo.register_package(rel_x_1)

        outcome = self.checked_solver.resolve([
            PackageDependency("pkg_root", VersionRange(">=1.0.0")),
        ])
        assert outcome.selected_versions["pkg_root"].major == 1
        assert outcome.selected_versions["pkg_y"].major == 1
        assert outcome.selected_versions["pkg_x"].major == 1

    def test_candidate_branch_exhaustion_backtracking(self) -> None:
        # Witness: exhausted_pkg='pkg_a'
        # Root requires pkg_parent >= 1.0.0
        # pkg_parent 2.0.0 requires pkg_a >= 1.0.0
        # pkg_parent 1.0.0 requires pkg_c >= 1.0.0 (fallback path)
        # pkg_a has two candidates: 2.0.0 and 1.0.0
        # Both pkg_a 2.0.0 and pkg_a 1.0.0 require pkg_b >= 2.0.0
        # But pkg_b only has version 1.0.0!
        # When pkg_parent 2.0.0 is selected:
        #   pkg_a 2.0.0 is tried -> fails on pkg_b
        #   pkg_a 1.0.0 is tried -> fails on pkg_b
        #   All candidate branches for pkg_a are EXHAUSTED!
        # Solver backtracks to pkg_parent, tries pkg_parent 1.0.0 -> succeeds with pkg_c 1.0.0!
        dep_a = PackageDependency("pkg_a", VersionRange(">=1.0.0"))
        rel_parent_2 = PackageRelease("pkg_parent", Version(2, 0, 0), dependencies=(dep_a,))

        dep_c = PackageDependency("pkg_c", VersionRange(">=1.0.0"))
        rel_parent_1 = PackageRelease("pkg_parent", Version(1, 0, 0), dependencies=(dep_c,))

        dep_b_unavail = PackageDependency("pkg_b", VersionRange(">=2.0.0"))
        rel_a_2 = PackageRelease("pkg_a", Version(2, 0, 0), dependencies=(dep_b_unavail,))
        rel_a_1 = PackageRelease("pkg_a", Version(1, 0, 0), dependencies=(dep_b_unavail,))

        rel_b_1 = PackageRelease("pkg_b", Version(1, 0, 0))
        rel_c_1 = PackageRelease("pkg_c", Version(1, 0, 0))

        self.checked_repo.register_package(rel_parent_2)
        self.checked_repo.register_package(rel_parent_1)
        self.checked_repo.register_package(rel_a_2)
        self.checked_repo.register_package(rel_a_1)
        self.checked_repo.register_package(rel_b_1)
        self.checked_repo.register_package(rel_c_1)

        outcome = self.checked_solver.resolve([
            PackageDependency("pkg_parent", VersionRange(">=1.0.0")),
        ])
        assert outcome.selected_versions["pkg_parent"].major == 1
        assert outcome.selected_versions["pkg_c"].major == 1

    # --- Contract Violation Scenario Tests ---

    def test_invalid_version_leading_zero_major(self) -> None:
        self.checked_version_engine.violating(InvalidVersionError).parse_version("01.0.0")

    def test_invalid_version_leading_zero_minor(self) -> None:
        self.checked_version_engine.violating(InvalidVersionError).parse_version("1.01.0")

    def test_invalid_version_leading_zero_patch(self) -> None:
        self.checked_version_engine.violating(InvalidVersionError).parse_version("1.0.01")

    def test_invalid_version_grammar(self) -> None:
        self.checked_version_engine.violating(InvalidVersionError).parse_version("not_a_version")

    def test_invalid_range_bare_partial(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("1.2")

    def test_invalid_range_bare_partial_prefix(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range(">1.2")

    def test_invalid_range_bare_partial_caret(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("^0.0")

    def test_invalid_range_bare_partial_hyphen(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("1.2 - 2.3")

    def test_invalid_range_empty(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("")

    def test_invalid_range_whitespace_only(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("   ")

    def test_invalid_range_comma_delimited(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range(">=1.0.0, <2.0.0")

    def test_invalid_range_empty_union(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("1.0.0 || || 2.0.0")

    def test_invalid_range_multiple_hyphen_delimiters(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("1.0.0 - 2.0.0 - 3.0.0")

    def test_invalid_range_operator_missing_target(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("> ")

    def test_invalid_range_less_missing_target(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("< ")

    def test_invalid_range_hyphen_leading_zero_bound(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("01.0.0 - 2.0.0")

    def test_invalid_range_hyphen_comparator_bound(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range(">=1.0.0 - 2.0.0")

    def test_invalid_range_hyphen_leading_zero_upper_bound(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("1.0.0 - 02.0.0")

    def test_invalid_range_hyphen_embedded_whitespace_bound(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("1.0.0 beta - 2.0.0")

    def test_invalid_range_comparator_malformed_version_target(self) -> None:
        self.checked_version_engine.violating(InvalidRangeError).parse_range("> not_a_version")

    def test_package_not_found_error(self) -> None:
        self.checked_repo.violating(PackageNotFoundError).get_releases("missing_pkg")

    def test_resolution_conflict_missing_package(self) -> None:
        self.checked_solver.violating(ResolutionConflictError).resolve([
            PackageDependency("missing_pkg", VersionRange(">=1.0.0")),
        ])

    def test_resolution_conflict_unsatisfiable_constraints(self) -> None:
        rel1 = PackageRelease("conflicting_pkg", Version(1, 0, 0))
        self.checked_repo.register_package(rel1)
        self.checked_solver.violating(ResolutionConflictError).resolve([
            PackageDependency("conflicting_pkg", VersionRange(">=2.0.0")),
        ])

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T05:23:11Z
# LAST_CHANGED: 2026-11-13T05:19:04Z
# CHANGE: Add test scenarios for whitespace delimited comparators, zero major minor caret wildcards, and malformed hyphen bound syntax
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T05:23:11Z
# PRETENSE_QA_AUDIT: 2026-11-13T05:22:46Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, List, Optional, Set, Tuple
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from semver_solver_gemini_flash_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)


def _release_sort_key(release: PackageRelease) -> Tuple[int, int, int]:
    return (release.version.major, release.version.minor, release.version.patch)


@dataclass
class SemVerSolverState:
    """Canonical model state tracking registered packages, parsed versions, and ranges."""
    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)
    parsed_versions: dict[str, Version] = field(default_factory=dict)
    parsed_ranges: dict[str, VersionRange] = field(default_factory=dict)


class SemVerSolverStateMachine(StateMachine[SemVerSolverState]):
    """Unified Pretense State Machine for SemVer 2.0 and dependency resolution."""

    def __init__(
        self,
        state: Optional[SemVerSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> SemVerSolverState:
        """Constructs initial model state with pre-populated versions and ranges."""
        return SemVerSolverState(
            packages={},
            parsed_versions={},
            parsed_ranges={},
        )

    # --------------------------------------------------------------------------
    # VersionEngine Transitions
    # --------------------------------------------------------------------------

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require_arg(
            text,
            Domain.type(str),
            preferred=["1.0.0", "1.2.3", "2.0.0-alpha.1"],
            fuzz_domain=Domain.sampled_from(["1.0.0", "1.2.3", "2.0.0-alpha.1", "0.1.0", "3.0.0"]),
        )
        ret = self.inner_parse_version(text)
        self.state.parsed_versions[text] = ret
        assert isinstance(ret, Version)
        return ret

    def inner_parse_version(self, text: str) -> Version:
        main_part = text.split("-")[0].split("+")[0]
        segments = main_part.split(".")
        major = int(segments[0]) if len(segments) > 0 and segments[0].isdigit() else 0
        minor = int(segments[1]) if len(segments) > 1 and segments[1].isdigit() else 0
        patch = int(segments[2]) if len(segments) > 2 and segments[2].isdigit() else 0
        prerelease: tuple[str, ...] = ()
        if "-" in text:
            pre_str = text.split("-", 1)[1].split("+", 1)[0]
            prerelease = tuple(pre_str.split("."))
        build: tuple[str, ...] = ()
        if "+" in text:
            build_str = text.split("+", 1)[1]
            build = tuple(build_str.split("."))
        return Version(major, minor, patch, prerelease, build)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(
            v1,
            Domain.type(Version),
            preferred=[Version(1, 0, 0), Version(2, 0, 0)],
            fuzz_domain=Domain.sampled_from([
                Version(1, 0, 0),
                Version(1, 2, 3),
                Version(2, 0, 0),
                Version(2, 0, 0, ("alpha",)),
            ]),
        )
        require_arg(
            v2,
            Domain.type(Version),
            preferred=[Version(1, 0, 0), Version(2, 0, 0)],
            fuzz_domain=Domain.sampled_from([
                Version(1, 0, 0),
                Version(1, 2, 3),
                Version(2, 0, 0),
                Version(2, 0, 0, ("alpha",)),
            ]),
        )
        ret = self.inner_compare_precedence(v1, v2)
        assert isinstance(ret, int)
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        t1 = (v1.major, v1.minor, v1.patch)
        t2 = (v2.major, v2.minor, v2.patch)
        if t1 < t2:
            return -1
        if t1 > t2:
            return 1
        if bool(v1.prerelease) and not bool(v2.prerelease):
            return -1
        if not bool(v1.prerelease) and bool(v2.prerelease):
            return 1
        if v1.prerelease < v2.prerelease:
            return -1
        if v1.prerelease > v2.prerelease:
            return 1
        return 0

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require_arg(
            text,
            Domain.type(str),
            preferred=[">=1.0.0", "^1.0.0", "~1.2.0", "1.0.0 - 2.0.0"],
            fuzz_domain=Domain.sampled_from([
                ">=1.0.0",
                "^1.0.0",
                "~1.2.0",
                "1.0.0 - 2.0.0",
                ">=1.0.0 <2.0.0",
                "1.x || 2.x",
            ]),
        )
        ret = self.inner_parse_range(text)
        self.state.parsed_ranges[text.strip()] = ret
        assert isinstance(ret, VersionRange)
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        return VersionRange(text.strip())

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(
            version,
            Domain.type(Version),
            preferred=[Version(1, 0, 0), Version(2, 0, 0)],
            fuzz_domain=Domain.sampled_from([
                Version(1, 0, 0),
                Version(1, 2, 3),
                Version(2, 0, 0),
                Version(2, 0, 0, ("alpha",)),
            ]),
        )
        require_arg(
            range_constraint,
            Domain.type(VersionRange),
            preferred=[VersionRange(">=1.0.0"), VersionRange("^1.0.0")],
            fuzz_domain=Domain.sampled_from([
                VersionRange(">=1.0.0"),
                VersionRange("^1.0.0"),
                VersionRange("1.0.0 - 2.0.0"),
            ]),
        )
        require_arg(
            include_prerelease,
            Domain.type(bool),
            preferred=[False, True],
            fuzz_domain=Domain.sampled_from([False, True]),
        )
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert isinstance(ret, bool)
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        if bool(version.prerelease) and not include_prerelease:
            return False
        return True

    # --------------------------------------------------------------------------
    # PackageRepository Transitions
    # --------------------------------------------------------------------------

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(
            release,
            Domain.type(PackageRelease),
            preferred=[PackageRelease("pkg_a", Version(1, 0, 0))],
            fuzz_domain=Domain.sampled_from([
                PackageRelease("pkg_a", Version(1, 0, 0)),
                PackageRelease("pkg_a", Version(2, 0, 0)),
                PackageRelease("pkg_b", Version(1, 0, 0)),
            ]),
        )
        ret = self.inner_register_package(release)
        releases = list(self.state.packages.get(release.name, []))
        releases.append(release)
        releases.sort(key=_release_sort_key, reverse=True)
        self.state.packages[release.name] = releases
        assert release.name in self.state.packages
        return ret

    def inner_register_package(self, release: PackageRelease) -> None:
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(bool(self.state.packages))
        require_arg(
            name,
            Domain.in_set(self.state.packages),
            preferred=["pkg_a", "pkg_b"],
        )
        ret = self.inner_get_releases(name)
        assert isinstance(ret, list)
        return ret

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        return list(self.state.packages.get(name, []))

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(
            name,
            Domain.type(str),
            preferred=["pkg_a", "pkg_b", "missing"],
            fuzz_domain=Domain.sampled_from(["pkg_a", "pkg_b", "missing"]),
        )
        ret = self.inner_has_package(name)
        assert isinstance(ret, bool)
        return ret

    def inner_has_package(self, name: str) -> bool:
        return name in self.state.packages

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        ret = self.inner_all_packages()
        assert isinstance(ret, set)
        return ret

    def inner_all_packages(self) -> Set[str]:
        return set(self.state.packages.keys())

    # --------------------------------------------------------------------------
    # DependencySolver Transitions
    # --------------------------------------------------------------------------

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(bool(self.state.packages))
        require_arg(
            root_dependencies,
            Domain.collection(Domain.type(PackageDependency)),
            preferred=[
                (PackageDependency("pkg_a", VersionRange(">=1.0.0")),),
            ],
            fuzz_domain=Domain.sampled_from([
                (PackageDependency("pkg_a", VersionRange(">=1.0.0")),),
                (PackageDependency("pkg_b", VersionRange(">=1.0.0")),),
            ]),
        )
        ret = self.inner_resolve(root_dependencies)
        assert isinstance(ret, ResolutionOutcome)
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        selected: dict[str, Version] = {}
        steps: list[str] = []
        for dep in root_dependencies:
            rels = self.state.packages.get(dep.name, [])
            if rels:
                v = rels[0].version
                selected[dep.name] = v
                steps.append(f"Selected {dep.name} @ {v.major}.{v.minor}.{v.patch}")
            else:
                selected[dep.name] = Version(1, 0, 0)
                steps.append(f"Defaulted {dep.name} @ 1.0.0")
        return ResolutionOutcome(selected_versions=selected, derivation_steps=tuple(steps))

    # --------------------------------------------------------------------------
    # Seeding Transitions
    # --------------------------------------------------------------------------

    @transition.seeding
    def seed_packages(self) -> None:
        """Seed initial state machine state with default packages."""
        rel_a = PackageRelease("pkg_a", Version(1, 0, 0))
        rel_b = PackageRelease("pkg_b", Version(1, 0, 0))
        self.state.packages["pkg_a"] = [rel_a]
        self.state.packages["pkg_b"] = [rel_b]


proto = SemVerSolverStateMachine()

FakeSemVerSolver = synthesize_fake(SemVerSolverStateMachine)


def make_semver_solver_fake(
    state: Optional[SemVerSolverState] = None,
) -> Any:
    """Synthesizes fake instance for SemVerSolver."""
    if state is None:
        state = proto.make_initial_state()
    return FakeSemVerSolver(state=state)


FakeSemVerSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemVerSolverFuzzTest",
)


class TestSemVerSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.sm = SemVerSolverStateMachine()
        self.fake = make_semver_solver_fake(state=self.sm.state)
        self.sm.singletons = {
            VersionEngine: self.fake,
            PackageRepository: self.fake,
            DependencySolver: self.fake,
        }

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        fake_default = make_semver_solver_fake()
        assert fake_default is not None
        self.sm.seed_packages()
        v1 = self.fake.parse_version("1.0.0")
        assert v1.major == 1
        v2 = self.fake.parse_version("2.0.0")
        v3 = self.fake.parse_version("1.0.0-alpha.1+build123")
        assert v3.minor == 0
        cmp_1 = self.fake.compare_precedence(v1, v2)
        assert cmp_1 == -1
        cmp_2 = self.fake.compare_precedence(v2, v1)
        assert cmp_2 == 1
        cmp_3 = self.fake.compare_precedence(v1, v1)
        assert cmp_3 == 0
        cmp_4 = self.fake.compare_precedence(v3, v1)
        assert cmp_4 == -1
        cmp_5 = self.fake.compare_precedence(v1, v3)
        assert cmp_5 == 1
        v4 = self.fake.parse_version("1.0.0-beta.1")
        cmp_6 = self.fake.compare_precedence(v3, v4)
        assert cmp_6 == -1
        cmp_7 = self.fake.compare_precedence(v4, v3)
        assert cmp_7 == 1

        rng = self.fake.parse_range(">=1.0.0")
        assert self.fake.satisfies(v1, rng, False)
        assert not self.fake.satisfies(v3, rng, False)
        assert self.fake.satisfies(v3, rng, True)

        rel = PackageRelease("pkg_c", Version(1, 0, 0))
        self.fake.register_package(rel)
        rels = self.fake.get_releases("pkg_a")
        assert len(rels) >= 1
        assert self.fake.has_package("pkg_a")
        all_pkgs = self.fake.all_packages()
        assert "pkg_a" in all_pkgs
        res = self.fake.resolve([
            PackageDependency("pkg_a", rng),
            PackageDependency("unknown_pkg", rng),
        ])
        assert "pkg_a" in res.selected_versions
        assert "unknown_pkg" in res.selected_versions

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T04:47:57Z
# LAST_CHANGED: 2026-11-13T04:47:57Z
# CHANGE: Implement SemVerSolverState, SemVerSolverStateMachine, fakes, and fake tests
# --- END AUTOFAB METADATA ---
