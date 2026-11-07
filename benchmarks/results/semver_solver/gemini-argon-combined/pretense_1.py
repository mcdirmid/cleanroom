# === File: semver_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Collection, List, Set
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

from benchmark_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver as DependencySolverIface,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository as PackageRepositoryIface,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionEngine as VersionEngineIface,
    VersionRange,
)
from benchmark_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)
from benchmark_1.parts.semver_solver.pretense.semver_solver_pretense import (
    SemVerSolverState,
    SemVerSolverStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class SemVerSolverImplPseudoStateMachine(SemVerSolverStateMachine):
    """Implementation pseudo-state machine for SemVerSolver measuring differentials and SUT state."""

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.is_prerelease == (len(ret.prerelease) > 0)
        assert ret.format() == str(ret)
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
        assert str(ret) == ret.raw_text
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(
            target.satisfies(version, range_constraint, include_prerelease)
        )
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert target.has_package(release.name) is True
        assert release.name in target.all_packages()
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert len(ret) >= 1
        assert all(r.name == name for r in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert ret == (name in target.all_packages())
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
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
        for dep in root_dependencies:
            assert dep.name in ret.selected_versions
        return ret


proto = SemVerSolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestSemVerSolverImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = get_singleton(VersionEngine)
        self.repo = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = SemVerSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: self.engine,
                PackageRepository: self.repo,
                DependencySolver: self.solver,
                VersionEngineIface: self.engine,
                PackageRepositoryIface: self.repo,
                DependencySolverIface: self.solver,
            }
        )
        self.checked_engine = self.sm.as_checked(VersionEngine, self.engine)
        self.checked_repo = self.sm.as_checked(PackageRepository, self.repo)
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_version_parsing_and_precedence(self) -> None:
        v1 = self.checked_engine.parse_version("1.0.0")
        assert v1 == Version(1, 0, 0)
        v_pre = self.checked_engine.parse_version("1.0.0-alpha.1")
        assert v_pre == Version(1, 0, 0, prerelease=("alpha", "1"))
        v_pre_alnum = self.checked_engine.parse_version("1.0.0-01a")
        assert v_pre_alnum == Version(1, 0, 0, prerelease=("01a",))
        v_build = self.checked_engine.parse_version("1.0.0+20130313")
        assert v_build == Version(1, 0, 0, build=("20130313",))
        v_build_zero = self.checked_engine.parse_version("1.0.0+01.build-2")
        assert v_build_zero == Version(1, 0, 0, build=("01", "build-2"))
        v_full = self.checked_engine.parse_version("1.2.3-alpha.1+build.1")
        assert v_full == Version(1, 2, 3, prerelease=("alpha", "1"), build=("build", "1"))

        for bad_version in (
            "",
            "   ",
            " 1.0.0",
            "1.0.0 ",
            " 1.0.0 ",
            "01.0.0",
            "1.01.0",
            "1.0.01",
            "1.0",
            "1.0.0.0",
            "v1.0.0",
            "-1.0.0",
            "1.-1.0",
            "1.0.-1",
            "1..0",
            "a.b.c",
            "1.a.0",
            "1.0.a",
            "1.0.0-",
            "1.0.0-+build",
            "1.0.0-01",
            "1.0.0-alpha.01",
            "1.0.0-alpha..1",
            "1.0.0-.alpha",
            "1.0.0-alpha.",
            "1.0.0-alpha_1",
            "1.0.0-alpha@1",
            "1.0.0-α",
            "1.0.0+",
            "1.0.0-alpha+",
            "1.0.0+build..1",
            "1.0.0+.build",
            "1.0.0+build.",
            "1.0.0+build_1",
            "1.0.0+build+1",
            "1.0.0+β",
            "invalid",
        ):
            with self.assertRaises(InvalidVersionError) as exc_v:
                self.checked_engine.parse_version(bad_version)
            assert exc_v.exception.raw_text == bad_version

        # Major, minor, patch comparisons
        assert self.checked_engine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)) < 0
        assert self.checked_engine.compare_precedence(Version(2, 0, 0), Version(1, 0, 0)) > 0
        assert self.checked_engine.compare_precedence(Version(1, 0, 0), Version(1, 1, 0)) < 0
        assert self.checked_engine.compare_precedence(Version(1, 1, 0), Version(1, 0, 0)) > 0
        assert self.checked_engine.compare_precedence(Version(1, 0, 0), Version(1, 0, 1)) < 0
        assert self.checked_engine.compare_precedence(Version(1, 0, 1), Version(1, 0, 0)) > 0
        assert self.checked_engine.compare_precedence(Version(1, 0, 0), Version(1, 0, 0)) == 0

        # Build metadata ignored
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, build=("20130313",)),
                Version(1, 0, 0, build=("20140101",)),
            )
            == 0
        )

        # Normal vs prerelease
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha", "1")), Version(1, 0, 0)
            )
            < 0
        )
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0), Version(1, 0, 0, prerelease=("alpha", "1"))
            )
            > 0
        )

        # Prerelease segment rules: numeric vs numeric, numeric vs string, string vs string, length
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("1",)), Version(1, 0, 0, prerelease=("2",))
            )
            < 0
        )
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("2",)), Version(1, 0, 0, prerelease=("1",))
            )
            > 0
        )
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("1",)),
                Version(1, 0, 0, prerelease=("alpha",)),
            )
            < 0
        )
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha",)),
                Version(1, 0, 0, prerelease=("1",)),
            )
            > 0
        )
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha",)),
                Version(1, 0, 0, prerelease=("beta",)),
            )
            < 0
        )
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("beta",)),
                Version(1, 0, 0, prerelease=("alpha",)),
            )
            > 0
        )
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha",)),
                Version(1, 0, 0, prerelease=("alpha", "1")),
            )
            < 0
        )
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha", "1")),
                Version(1, 0, 0, prerelease=("alpha",)),
            )
            > 0
        )
        assert (
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha", "1")),
                Version(1, 0, 0, prerelease=("alpha", "1")),
            )
            == 0
        )

    def test_range_parsing_and_satisfaction(self) -> None:
        r_trimmed = self.checked_engine.parse_range("  >= 1.0.0 < 2.0.0  ")
        assert r_trimmed.raw_text == ">= 1.0.0 < 2.0.0"

        for r_txt in (
            "==1.0.0",
            "=1.0.0",
            "!=1.0.0",
            "<2.0.0",
            "<=2.0.0",
            ">1.0.0",
            ">=1.0.0",
            "^1.2.3",
            "^0.2.3",
            "^0.0.3",
            "~1.2.3",
            "*",
            "x",
            "X",
            "1.*",
            "1.x",
            "1.X",
            "1.2.*",
            "1.2.x",
            "1.2.X",
            "== *",
            "= 1.*",
            "== 1.2.*",
            "1.0.0 - 2.0.0",
            ">=1.0.0 <1.2.0 || >=2.0.0",
        ):
            parsed = self.checked_engine.parse_range(r_txt)
            assert parsed.raw_text == r_txt

        for bad_range in (
            "",
            "   ",
            "||",
            "1.0.0 ||",
            "|| 1.0.0",
            "1.0.0 ||   || 2.0.0",
            ">=1.0.0, <2.0.0",
            "==",
            "=",
            "!=",
            "<",
            "<=",
            ">",
            ">=",
            "^",
            "~",
            ">=1.0.0 <",
            "> <2.0.0",
            "-",
            "1.0.0 -",
            "- 2.0.0",
            "1.0.0 - 2.0",
            "1.0 - 2.0.0",
            "1.0.0 - *",
            "1",
            "1.2",
            "^0.0",
            "1.2 - 2.3",
            "01.*",
            "a.*",
            "01.2.*",
            "1.02.*",
            "a.2.*",
            "1.b.*",
            "1.2.3.*",
            "*.1.*",
            "1.*.0",
            ">1.*",
            ">=1.2.*",
            "^1.*",
            "~1.2.*",
            "invalid",
        ):
            with self.assertRaises(InvalidRangeError) as exc_r:
                self.checked_engine.parse_range(bad_range)
            assert exc_r.exception.raw_range == bad_range

        # Basic comparators
        assert self.checked_engine.satisfies(Version(1, 0, 0), VersionRange("==1.0.0"), False) is True
        assert self.checked_engine.satisfies(Version(1, 0, 1), VersionRange("==1.0.0"), False) is False
        assert self.checked_engine.satisfies(Version(1, 0, 0), VersionRange("=1.0.0"), False) is True
        assert self.checked_engine.satisfies(Version(1, 0, 1), VersionRange("!=1.0.0"), False) is True
        assert self.checked_engine.satisfies(Version(1, 0, 0), VersionRange("!=1.0.0"), False) is False
        assert self.checked_engine.satisfies(Version(1, 0, 0), VersionRange("<2.0.0"), False) is True
        assert self.checked_engine.satisfies(Version(2, 0, 0), VersionRange("<2.0.0"), False) is False
        assert self.checked_engine.satisfies(Version(2, 0, 0), VersionRange("<=2.0.0"), False) is True
        assert self.checked_engine.satisfies(Version(2, 0, 1), VersionRange("<=2.0.0"), False) is False
        assert self.checked_engine.satisfies(Version(1, 0, 1), VersionRange(">1.0.0"), False) is True
        assert self.checked_engine.satisfies(Version(1, 0, 0), VersionRange(">1.0.0"), False) is False
        assert self.checked_engine.satisfies(Version(1, 0, 0), VersionRange(">=1.0.0"), False) is True
        assert self.checked_engine.satisfies(Version(0, 9, 0), VersionRange(">=1.0.0"), False) is False

        # Caret ranges
        assert self.checked_engine.satisfies(Version(1, 2, 3), VersionRange("^1.2.3"), False) is True
        assert self.checked_engine.satisfies(Version(1, 9, 0), VersionRange("^1.2.3"), False) is True
        assert self.checked_engine.satisfies(Version(1, 2, 2), VersionRange("^1.2.3"), False) is False
        assert self.checked_engine.satisfies(Version(2, 0, 0), VersionRange("^1.2.3"), False) is False
        assert self.checked_engine.satisfies(Version(0, 2, 3), VersionRange("^0.2.3"), False) is True
        assert self.checked_engine.satisfies(Version(0, 2, 9), VersionRange("^0.2.3"), False) is True
        assert self.checked_engine.satisfies(Version(0, 3, 0), VersionRange("^0.2.3"), False) is False
        assert self.checked_engine.satisfies(Version(0, 0, 3), VersionRange("^0.0.3"), False) is True
        assert self.checked_engine.satisfies(Version(0, 0, 4), VersionRange("^0.0.3"), False) is False

        # Tilde ranges
        assert self.checked_engine.satisfies(Version(1, 2, 3), VersionRange("~1.2.3"), False) is True
        assert self.checked_engine.satisfies(Version(1, 2, 9), VersionRange("~1.2.3"), False) is True
        assert self.checked_engine.satisfies(Version(1, 3, 0), VersionRange("~1.2.3"), False) is False

        # Wildcards, hyphen, union
        assert self.checked_engine.satisfies(Version(1, 0, 0), VersionRange("*"), False) is True
        assert self.checked_engine.satisfies(Version(1, 5, 0), VersionRange("1.*"), False) is True
        assert self.checked_engine.satisfies(Version(2, 0, 0), VersionRange("1.*"), False) is False
        assert self.checked_engine.satisfies(Version(1, 2, 5), VersionRange("1.2.*"), False) is True
        assert self.checked_engine.satisfies(Version(1, 3, 0), VersionRange("1.2.*"), False) is False
        assert self.checked_engine.satisfies(Version(1, 5, 0), VersionRange("1.0.0 - 2.0.0"), False) is True
        assert self.checked_engine.satisfies(Version(2, 0, 1), VersionRange("1.0.0 - 2.0.0"), False) is False
        assert self.checked_engine.satisfies(Version(2, 0, 0), VersionRange(">=1.0.0 <1.2.0 || >=2.0.0"), False) is True
        assert self.checked_engine.satisfies(Version(1, 5, 0), VersionRange(">=1.0.0 <1.2.0 || >=2.0.0"), False) is False

        # Prerelease rules
        v_pre2 = Version(1, 0, 0, prerelease=("alpha", "2"))
        assert self.checked_engine.satisfies(v_pre2, VersionRange(">=0.9.0"), False) is False
        assert self.checked_engine.satisfies(v_pre2, VersionRange(">=0.9.0"), True) is True
        assert self.checked_engine.satisfies(v_pre2, VersionRange(">=1.0.0"), True) is False
        assert (
            self.checked_engine.satisfies(
                v_pre2, VersionRange(">=1.0.0-alpha.1 <2.0.0"), False
            )
            is True
        )
        assert (
            self.checked_engine.satisfies(
                v_pre2, VersionRange(">=0.9.0-alpha.1 <2.0.0"), False
            )
            is False
        )

    def test_repository_and_solver_resolution(self) -> None:
        assert self.checked_repo.has_package("pkg_a") is False
        assert self.checked_repo.all_packages() == set()
        with self.assertRaises(PackageNotFoundError) as exc_p:
            self.checked_repo.get_releases("pkg_a")
        assert exc_p.exception.package_name == "pkg_a"

        # Empty resolution
        empty_res = self.checked_solver.resolve(())
        assert empty_res.selected_versions == {}

        # Unregistered package conflict
        with self.assertRaises(ResolutionConflictError) as exc_c:
            self.checked_solver.resolve(
                (PackageDependency("missing_pkg", VersionRange("^1.0.0")),)
            )
        assert "missing_pkg" in exc_c.exception.conflicting_packages
        assert len(exc_c.exception.explanation) > 0

        # Register initial releases whose transitive dependencies cannot be satisfied
        # so that viable initial candidates all fail during backtracking.
        self.checked_repo.register_package(PackageRelease("pkg_a", Version(1, 0, 0)))
        self.checked_repo.register_package(
            PackageRelease(
                "pkg_b",
                Version(2, 0, 0),
                dependencies=(PackageDependency("pkg_a", VersionRange(">=2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "pkg_c",
                Version(2, 0, 0),
                dependencies=(PackageDependency("pkg_e", VersionRange(">=2.0.0")),),
            )
        )

        # Viable candidate pkg_b 2.0.0 fails during backtracking because pkg_a has only 1.0.0 (<2.0.0)
        with self.assertRaises(ResolutionConflictError) as exc_bt_b:
            self.checked_solver.resolve(
                (PackageDependency("pkg_b", VersionRange(">=1.0.0")),)
            )
        assert "pkg_a" in exc_bt_b.exception.conflicting_packages
        assert "pkg_b" in exc_bt_b.exception.conflicting_packages
        assert len(exc_bt_b.exception.explanation) > 0

        # Viable candidate pkg_a 1.0.0 is assigned first, then pkg_b 2.0.0 conflicts with already-assigned pkg_a
        with self.assertRaises(ResolutionConflictError) as exc_bt_ab:
            self.checked_solver.resolve(
                (
                    PackageDependency("pkg_a", VersionRange("^1.0.0")),
                    PackageDependency("pkg_b", VersionRange(">=1.0.0")),
                )
            )
        assert "pkg_a" in exc_bt_ab.exception.conflicting_packages
        assert "pkg_b" in exc_bt_ab.exception.conflicting_packages
        assert len(exc_bt_ab.exception.explanation) > 0

        # Viable candidate pkg_c 2.0.0 fails during backtracking because transitive dependency pkg_e is unregistered
        with self.assertRaises(ResolutionConflictError) as exc_bt_c:
            self.checked_solver.resolve(
                (PackageDependency("pkg_c", VersionRange(">=1.0.0")),)
            )
        assert "pkg_c" in exc_bt_c.exception.conflicting_packages
        assert "pkg_e" in exc_bt_c.exception.conflicting_packages
        assert len(exc_bt_c.exception.explanation) > 0

        # Register remaining releases and test successful backtracking + conflicts
        for rel in (
            PackageRelease("pkg_a", Version(1, 1, 0)),
            PackageRelease(
                "pkg_b",
                Version(1, 0, 0),
                dependencies=(PackageDependency("pkg_a", VersionRange("^1.0.0")),),
            ),
            PackageRelease(
                "pkg_c",
                Version(1, 0, 0),
                dependencies=(PackageDependency("pkg_e", VersionRange("^1.0.0")),),
            ),
            PackageRelease("pkg_e", Version(1, 0, 0)),
            PackageRelease("pkg_e", Version(1, 1, 0)),
        ):
            self.checked_repo.register_package(rel)

        releases_a = self.checked_repo.get_releases("pkg_a")
        assert len(releases_a) == 2
        assert releases_a[0].version == Version(1, 1, 0)

        # Backtracking when dep is already assigned (pkg_a assigned first via MRV, pkg_b 2.0.0 conflicts and backtracks to 1.0.0)
        res_ab = self.checked_solver.resolve(
            (
                PackageDependency("pkg_a", VersionRange("^1.0.0")),
                PackageDependency("pkg_b", VersionRange(">=1.0.0")),
            )
        )
        assert res_ab.selected_versions["pkg_a"] == Version(1, 1, 0)
        assert res_ab.selected_versions["pkg_b"] == Version(1, 0, 0)

        # Backtracking when transitive dependency has 0 candidates (pkg_c 2.0.0 requires pkg_e >=2.0.0, backtracks to pkg_c 1.0.0)
        res_c = self.checked_solver.resolve(
            (PackageDependency("pkg_c", VersionRange(">=1.0.0")),)
        )
        assert res_c.selected_versions["pkg_c"] == Version(1, 0, 0)
        assert res_c.selected_versions["pkg_e"] == Version(1, 1, 0)

        # Backtracking when transitive dependency already has a root constraint
        res_ce = self.checked_solver.resolve(
            (
                PackageDependency("pkg_c", VersionRange(">=1.0.0")),
                PackageDependency("pkg_e", VersionRange(">=1.0.0")),
            )
        )
        assert res_ce.selected_versions["pkg_c"] == Version(1, 0, 0)
        assert res_ce.selected_versions["pkg_e"] == Version(1, 1, 0)

        # Exhausted candidates conflict
        with self.assertRaises(ResolutionConflictError):
            self.checked_solver.resolve(
                (PackageDependency("pkg_e", VersionRange(">=3.0.0")),)
            )


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


class SemVerSolverSUT:
    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = get_singleton(VersionEngine)
        self.repo = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.__dict__["_services"] = (self.engine, self.repo, self.solver)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> SemVerSolverSUT:
    return SemVerSolverSUT()


SemVerSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemVerSolverState,
    name="SemVerSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T21:10:47Z
# LAST_CHANGED: 2026-11-06T21:09:20Z
# CHANGE: Remove trailing whitespace range '>= 1.0.0\u00a0' from bad_range in TestSemVerSolverImplReal.test_range_parsing_and_satisfaction
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T21:10:47Z
# PRETENSE_QA_AUDIT: 2026-11-06T21:09:58Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
import re
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
import unittest

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

from benchmark_1.parts.semver_solver.lib.semver_solver import (
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
    SemVerError,
    Version,
    VersionEngine,
    VersionRange,
)

_SEMVER_RE = re.compile(
    r"\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
)

_WILDCARD_RE = re.compile(
    r"\A(?:\*|x|X|(0|[1-9][0-9]*)\.(?:\*|x|X)|(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(?:\*|x|X))\Z"
)

_OP_RE = re.compile(r"\A(==|=|!=|<=|>=|<|>|\^|~)\s*(.+)\Z")


def _model_parse_version(text: str) -> Optional[Version]:
    if not text.isascii():
        return None
    match = _SEMVER_RE.match(text)
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    build = tuple(match.group(5).split(".")) if match.group(5) else ()
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def _model_compare_precedence(v1: Version, v2: Version) -> int:
    if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
        return -1 if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch) else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for s1, s2 in zip(v1.prerelease, v2.prerelease):
        if s1 == s2:
            continue
        is_num1 = s1.isascii() and s1.isdigit()
        is_num2 = s2.isascii() and s2.isdigit()
        if is_num1 and is_num2:
            return -1 if int(s1) < int(s2) else 1
        if is_num1 != is_num2:
            return -1 if is_num1 else 1
        return -1 if s1 < s2 else 1
    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
    return 0


def _compile_clause_comparators(
    clause_text: str,
) -> Optional[Tuple[List[Tuple[str, Version]], Set[Tuple[int, int, int]]]]:
    if not clause_text or not clause_text.isascii() or "," in clause_text:
        return None
    tokens = clause_text.split()
    if not tokens:
        return None

    normalized_tokens: List[str] = []
    idx = 0
    for _ in range(len(tokens)):
        if idx >= len(tokens):
            break
        tok = tokens[idx]
        if idx + 2 < len(tokens) and tokens[idx + 1] == "-":
            v_low = _model_parse_version(tok)
            v_high = _model_parse_version(tokens[idx + 2])
            if v_low is None or v_high is None:
                return None
            normalized_tokens.append(f">={tok}")
            normalized_tokens.append(f"<={tokens[idx + 2]}")
            idx += 3
        elif tok in ("==", "=", "!=", "<=", ">=", "<", ">", "^", "~"):
            if idx + 1 >= len(tokens):
                return None
            normalized_tokens.append(f"{tok}{tokens[idx + 1]}")
            idx += 2
        else:
            normalized_tokens.append(tok)
            idx += 1

    comparators: List[Tuple[str, Version]] = []
    prerelease_targets: Set[Tuple[int, int, int]] = set()

    for item in normalized_tokens:
        op_match = _OP_RE.match(item)
        if op_match:
            op = op_match.group(1)
            target_str = op_match.group(2).strip()
        else:
            op = "="
            target_str = item.strip()

        wc_match = _WILDCARD_RE.match(target_str)
        if wc_match:
            if op not in ("=", "=="):
                return None
            if wc_match.group(1) is not None:
                maj = int(wc_match.group(1))
                comparators.append((">=", Version(maj, 0, 0)))
                comparators.append(("<", Version(maj + 1, 0, 0)))
            elif wc_match.group(2) is not None and wc_match.group(3) is not None:
                maj = int(wc_match.group(2))
                min_v = int(wc_match.group(3))
                comparators.append((">=", Version(maj, min_v, 0)))
                comparators.append(("<", Version(maj, min_v + 1, 0)))
            else:
                comparators.append((">=", Version(0, 0, 0)))
            continue

        parsed_v = _model_parse_version(target_str)
        if parsed_v is None:
            return None
        if parsed_v.prerelease:
            prerelease_targets.add((parsed_v.major, parsed_v.minor, parsed_v.patch))

        if op in ("=", "=="):
            comparators.append(("==", parsed_v))
        elif op in ("!=", "<", "<=", ">", ">="):
            comparators.append((op, parsed_v))
        elif op == "^":
            comparators.append((">=", parsed_v))
            if parsed_v.major > 0:
                comparators.append(("<", Version(parsed_v.major + 1, 0, 0)))
            elif parsed_v.minor > 0:
                comparators.append(("<", Version(0, parsed_v.minor + 1, 0)))
            else:
                comparators.append(("<", Version(0, 0, parsed_v.patch + 1)))
        elif op == "~":
            comparators.append((">=", parsed_v))
            comparators.append(("<", Version(parsed_v.major, parsed_v.minor + 1, 0)))
        else:
            return None

    return comparators, prerelease_targets


def _model_parse_range(text: str) -> Optional[VersionRange]:
    if not text or not text.isascii() or not text.strip() or "," in text:
        return None
    raw_clauses = text.split("||")
    trimmed_clauses: List[str] = []
    for raw_clause in raw_clauses:
        c = raw_clause.strip()
        if not c:
            return None
        if _compile_clause_comparators(c) is None:
            return None
        trimmed_clauses.append(c)
    return VersionRange(raw_text=" || ".join(trimmed_clauses))


def _model_satisfies(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    raw_clauses = range_constraint.raw_text.split("||")
    for raw_clause in raw_clauses:
        compiled = _compile_clause_comparators(raw_clause.strip())
        if compiled is None:
            continue
        comparators, prerelease_targets = compiled
        if version.prerelease and not include_prerelease:
            if (version.major, version.minor, version.patch) not in prerelease_targets:
                continue
        clause_ok = True
        for op, target_v in comparators:
            cmp_val = _model_compare_precedence(version, target_v)
            if op == "==" and cmp_val != 0:
                clause_ok = False
                break
            if op == "!=" and cmp_val == 0:
                clause_ok = False
                break
            if op == "<" and cmp_val >= 0:
                clause_ok = False
                break
            if op == "<=" and cmp_val > 0:
                clause_ok = False
                break
            if op == ">" and cmp_val <= 0:
                clause_ok = False
                break
            if op == ">=" and cmp_val < 0:
                clause_ok = False
                break
        if clause_ok:
            return True
    return False


def _backtrack_step(
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]],
    assignment: Dict[str, PackageRelease],
    derivation_steps: List[str],
    conflict_trail: List[str],
    conflicting_packages: Set[str],
    packages: Dict[str, List[PackageRelease]],
) -> bool:
    unassigned = [p for p in accumulated_constraints if p not in assignment]
    if not unassigned:
        return True

    candidates_map: Dict[str, List[PackageRelease]] = {}
    for pkg in unassigned:
        available = packages.get(pkg, [])
        viable = [
            rel
            for rel in available
            if all(
                _model_satisfies(rel.version, rng, False)
                for _, rng in accumulated_constraints[pkg]
            )
        ]
        candidates_map[pkg] = viable

    selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
    candidates = candidates_map[selected_pkg]

    if not candidates:
        requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
        conflicting_packages.add(selected_pkg)
        for req in requesters:
            if req != "root":
                conflicting_packages.add(req)
        conflict_trail.append(
            f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
        )
        return False

    for candidate in candidates:
        assignment[selected_pkg] = candidate
        derivation_steps.append(
            f"Assign '{selected_pkg}' to {candidate.version.major}.{candidate.version.minor}.{candidate.version.patch}"
        )

        conflict_detected = False
        newly_added: List[Tuple[str, Tuple[str, VersionRange]]] = []

        for dep in candidate.dependencies:
            if dep.name in assignment:
                if not _model_satisfies(
                    assignment[dep.name].version, dep.range_constraint, False
                ):
                    conflict_detected = True
                    conflicting_packages.add(selected_pkg)
                    conflicting_packages.add(dep.name)
                    conflict_trail.append(
                        f"Conflict: '{selected_pkg}' requires {dep.name} {dep.range_constraint.raw_text}"
                    )
                    break
            else:
                constraint_entry = (selected_pkg, dep.range_constraint)
                accumulated_constraints.setdefault(dep.name, []).append(
                    constraint_entry
                )
                newly_added.append((dep.name, constraint_entry))

        if not conflict_detected and _backtrack_step(
            accumulated_constraints,
            assignment,
            derivation_steps,
            conflict_trail,
            conflicting_packages,
            packages,
        ):
            return True

        for pkg_name, constraint_entry in newly_added:
            accumulated_constraints[pkg_name].remove(constraint_entry)
            if not accumulated_constraints[pkg_name]:
                del accumulated_constraints[pkg_name]
        del assignment[selected_pkg]
        derivation_steps.pop()

    return False


def _model_resolve(
    root_dependencies: Collection[PackageDependency],
    packages: Dict[str, List[PackageRelease]],
) -> Tuple[Optional[ResolutionOutcome], Tuple[str, ...], str]:
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]] = {}
    for dep in root_dependencies:
        accumulated_constraints.setdefault(dep.name, []).append(
            ("root", dep.range_constraint)
        )

    assignment: Dict[str, PackageRelease] = {}
    conflict_trail: List[str] = []
    derivation_steps: List[str] = []
    conflicting_packages: Set[str] = set()

    success = _backtrack_step(
        accumulated_constraints,
        assignment,
        derivation_steps,
        conflict_trail,
        conflicting_packages,
        packages,
    )
    if success:
        selected = {pkg: rel.version for pkg, rel in assignment.items()}
        return (
            ResolutionOutcome(
                selected_versions=selected,
                derivation_steps=tuple(derivation_steps),
            ),
            (),
            "",
        )
    return (
        None,
        tuple(sorted(conflicting_packages)),
        "; ".join(conflict_trail) if conflict_trail else "Unsatisfiable dependencies",
    )


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class SemVerSolverState:
    """Canonical model state tracking registered package releases."""

    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)


SAMPLE_VERSIONS = [
    Version(0, 0, 2),
    Version(0, 0, 3),
    Version(0, 0, 4),
    Version(0, 2, 2),
    Version(0, 2, 3),
    Version(0, 2, 9),
    Version(0, 3, 0),
    Version(0, 9, 0),
    Version(1, 0, 0),
    Version(1, 0, 1),
    Version(1, 1, 0),
    Version(1, 2, 0),
    Version(1, 2, 2),
    Version(1, 2, 3),
    Version(1, 2, 5),
    Version(1, 2, 9),
    Version(1, 3, 0),
    Version(1, 5, 0),
    Version(1, 9, 0),
    Version(2, 0, 0),
    Version(2, 0, 1),
    Version(1, 0, 0, prerelease=("1",)),
    Version(1, 0, 0, prerelease=("2",)),
    Version(1, 0, 0, prerelease=("alpha",)),
    Version(1, 0, 0, prerelease=("alpha", "1")),
    Version(1, 0, 0, prerelease=("alpha", "2")),
    Version(1, 0, 0, prerelease=("beta",)),
    Version(1, 0, 0, build=("20130313",)),
    Version(1, 0, 0, build=("20140101",)),
    Version(1, 2, 3, prerelease=("alpha", "1"), build=("build", "1")),
]

SAMPLE_RANGES = [
    VersionRange("==1.0.0"),
    VersionRange("=1.0.0"),
    VersionRange("!=1.0.0"),
    VersionRange("<2.0.0"),
    VersionRange("<=2.0.0"),
    VersionRange(">1.0.0"),
    VersionRange(">=1.0.0"),
    VersionRange(">=0.9.0"),
    VersionRange(">=1.0.0 <2.0.0"),
    VersionRange("^1.0.0"),
    VersionRange("^1.2.3"),
    VersionRange("^0.2.3"),
    VersionRange("^0.0.3"),
    VersionRange("~1.1.0"),
    VersionRange("~1.2.3"),
    VersionRange("*"),
    VersionRange("x"),
    VersionRange("X"),
    VersionRange("1.*"),
    VersionRange("1.x"),
    VersionRange("1.X"),
    VersionRange("1.2.*"),
    VersionRange("1.2.x"),
    VersionRange("1.2.X"),
    VersionRange("1.0.0 - 2.0.0"),
    VersionRange(">=1.0.0 <1.2.0 || >=2.0.0"),
    VersionRange(">=1.0.0-alpha.1 <2.0.0"),
    VersionRange(">=0.9.0-alpha.1 <2.0.0"),
]

SAMPLE_RELEASES = [
    PackageRelease("pkg_a", Version(1, 0, 0)),
    PackageRelease("pkg_a", Version(1, 1, 0)),
    PackageRelease(
        "pkg_b",
        Version(1, 0, 0),
        dependencies=(PackageDependency("pkg_a", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "pkg_b",
        Version(2, 0, 0),
        dependencies=(PackageDependency("pkg_a", VersionRange(">=2.0.0")),),
    ),
    PackageRelease(
        "pkg_c",
        Version(1, 0, 0),
        dependencies=(PackageDependency("pkg_e", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "pkg_c",
        Version(2, 0, 0),
        dependencies=(PackageDependency("pkg_e", VersionRange(">=2.0.0")),),
    ),
    PackageRelease("pkg_e", Version(1, 0, 0)),
    PackageRelease("pkg_e", Version(1, 1, 0)),
]

SAMPLE_ROOT_DEPS: List[Collection[PackageDependency]] = [
    (),
    (PackageDependency("pkg_a", VersionRange("^1.0.0")),),
    (PackageDependency("pkg_b", VersionRange(">=1.0.0")),),
    (
        PackageDependency("pkg_a", VersionRange("^1.0.0")),
        PackageDependency("pkg_b", VersionRange(">=1.0.0")),
    ),
    (PackageDependency("pkg_c", VersionRange(">=1.0.0")),),
    (
        PackageDependency("pkg_c", VersionRange(">=1.0.0")),
        PackageDependency("pkg_e", VersionRange(">=1.0.0")),
    ),
    (PackageDependency("pkg_e", VersionRange(">=3.0.0")),),
    (PackageDependency("missing_pkg", VersionRange("^1.0.0")),),
]


def _compare_release_desc(a: PackageRelease, b: PackageRelease) -> int:
    return _model_compare_precedence(b.version, a.version)


_RELEASE_SORT_KEY = cmp_to_key(_compare_release_desc)


class SemVerSolverStateMachine(StateMachine[SemVerSolverState]):
    """Unified Pretense State Machine for SemVerSolver."""

    def __init__(
        self,
        state: Optional[SemVerSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemVerSolverState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require_arg(
            text,
            Domain.type(str),
            preferred=[
                "1.0.0",
                "1.2.3-alpha.1+build.1",
                "0.1.0",
                "2.0.0-rc.1",
                "01.0.0",
                "invalid",
            ],
        )
        expected = _model_parse_version(text)
        if expected is None:
            with raises(InvalidVersionError):
                ret = make_return_value(Version(0, 0, 0))
            return Version(0, 0, 0)
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(
            v1,
            Domain.sampled_from(SAMPLE_VERSIONS),
            preferred=[Version(1, 0, 0), Version(1, 0, 0, prerelease=("alpha", "1"))],
        )
        require_arg(
            v2,
            Domain.sampled_from(SAMPLE_VERSIONS),
            preferred=[Version(2, 0, 0), Version(1, 0, 0)],
        )
        expected = _model_compare_precedence(v1, v2)
        ret = make_return_value(expected)
        if expected < 0:
            assert ret < 0
        elif expected > 0:
            assert ret > 0
        else:
            assert ret == 0
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require_arg(
            text,
            Domain.type(str),
            preferred=[
                ">=1.0.0 <2.0.0",
                "^1.0.0",
                "~1.1.0",
                "1.*",
                "1.0.0 - 2.0.0",
                "1.2",
                "",
            ],
        )
        expected = _model_parse_range(text)
        if expected is None:
            with raises(InvalidRangeError):
                ret = make_return_value(VersionRange(""))
            return VersionRange("")
        ret = make_return_value(expected)
        assert ret.raw_text == ret.raw_text.strip()
        assert [c.strip() for c in ret.raw_text.split("||")] == [
            c.strip() for c in expected.raw_text.split("||")
        ]
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(
            version,
            Domain.sampled_from(SAMPLE_VERSIONS),
            preferred=[Version(1, 1, 0), Version(1, 0, 0, prerelease=("alpha", "2"))],
        )
        require_arg(
            range_constraint,
            Domain.sampled_from(SAMPLE_RANGES),
            preferred=[VersionRange("^1.0.0"), VersionRange(">=1.0.0 <2.0.0")],
        )
        require_arg(include_prerelease, Domain.type(bool), preferred=[False, True])
        expected = _model_satisfies(version, range_constraint, include_prerelease)
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(
            release,
            Domain.sampled_from(SAMPLE_RELEASES),
            preferred=[SAMPLE_RELEASES[0], SAMPLE_RELEASES[1], SAMPLE_RELEASES[2]],
        )
        ret = make_return_value(None)
        existing = list(self.state.packages.get(release.name, []))
        existing.append(release)
        existing.sort(key=_RELEASE_SORT_KEY)
        self.state.packages[release.name] = existing
        assert release.name in self.state.packages
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require_arg(
            name,
            Domain.type(str),
            preferred=["pkg_a", "pkg_b", "unknown_pkg"],
        )
        if name not in self.state.packages:
            with raises(PackageNotFoundError):
                ret = make_return_value([])
            return []
        expected = list(self.state.packages[name])
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(
            name,
            Domain.type(str),
            preferred=["pkg_a", "pkg_b", "unknown_pkg"],
        )
        expected = name in self.state.packages
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        expected = set(self.state.packages.keys())
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require_arg(
            root_dependencies,
            Domain.sampled_from(SAMPLE_ROOT_DEPS),
            preferred=[
                (PackageDependency("pkg_a", VersionRange("^1.0.0")),),
                (PackageDependency("missing_pkg", VersionRange("^1.0.0")),),
            ],
        )
        outcome, _, _ = _model_resolve(root_dependencies, self.state.packages)
        if outcome is None:
            with raises(ResolutionConflictError):
                ret = make_return_value(ResolutionOutcome({}, ()))
            return ResolutionOutcome({}, ())
        ret = make_return_value(outcome)
        assert ret.selected_versions == outcome.selected_versions
        return ret


proto = SemVerSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeSemVerSolver = synthesize_fake(SemVerSolverStateMachine)


def make_semver_solver_fake(
    state: Optional[SemVerSolverState] = None,
) -> Any:
    """Synthesizes fake instance for SemVerSolver services."""
    return FakeSemVerSolver(state=state or SemVerSolverState())


def make_semver_solver_fakes(
    state: Optional[SemVerSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances sharing model state."""
    fake = FakeSemVerSolver(state=state or SemVerSolverState())
    return (fake, fake, fake)


FakeSemVerSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemVerSolverState,
    name="FakeSemVerSolverFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestSemVerSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_solver_fake()

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions on the fake."""
        assert ComparatorOp.EQ.value == "=="
        assert issubclass(InvalidVersionError, SemVerError)

        v1 = self.fake.parse_version("1.0.0")
        v2 = self.fake.parse_version("1.1.0")
        assert self.fake.compare_precedence(v1, v2) < 0
        assert self.fake.compare_precedence(v2, v1) > 0
        assert self.fake.compare_precedence(v1, v1) == 0

        rng = self.fake.parse_range("^1.0.0")
        assert self.fake.satisfies(v2, rng, False) is True

        assert self.fake.has_package("pkg_a") is False
        self.fake.register_package(PackageRelease("pkg_a", v1))
        self.fake.register_package(PackageRelease("pkg_a", v2))
        assert self.fake.has_package("pkg_a") is True
        assert self.fake.all_packages() == {"pkg_a"}

        releases = self.fake.get_releases("pkg_a")
        assert len(releases) == 2
        assert releases[0].version == v2

        outcome = self.fake.resolve(
            (PackageDependency("pkg_a", VersionRange("^1.0.0")),)
        )
        assert outcome.selected_versions["pkg_a"] == v2

        with self.assertRaises(InvalidVersionError):
            self.fake.parse_version("01.0.0")
        with self.assertRaises(InvalidRangeError):
            self.fake.parse_range("1.2")
        with self.assertRaises(PackageNotFoundError):
            self.fake.get_releases("unknown_pkg")
        with self.assertRaises(ResolutionConflictError):
            self.fake.resolve(
                (PackageDependency("missing_pkg", VersionRange("^1.0.0")),)
            )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:37:00Z
# LAST_CHANGED: 2026-11-06T20:37:00Z
# CHANGE: Implement Pretense interface state machine, synthesized fake, fixed fake tests, and Hypothesis fuzzing for semver_solver
# --- END AUTOFAB METADATA ---
