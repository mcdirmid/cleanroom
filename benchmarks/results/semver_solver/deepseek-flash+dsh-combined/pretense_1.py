# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver.pretense.semver_solver_pretense import (
    SAMPLE_RELEASES,
    VALID_RANGE_CONSTRAINTS,
    FakeSemverSolver,
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fakes,
)
from benchmark_1.parts.semver_solver.lib.semver_solver import (
    PackageDependency,
    PackageRelease,
    ResolutionOutcome,
    Version,
    VersionRange,
)
from benchmark_1.parts.semver_solver.lib.semver_solver_impl import (
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
    def parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert isinstance(ret, Version)
        assert ret.major >= 0
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
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        assert isinstance(ret, VersionRange)
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
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
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
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert isinstance(ret, ResolutionOutcome)
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies its contracts."""

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

    def test_parse_version_forms(self) -> None:
        basic = self.checked_versionengine.parse_version("1.2.3")
        assert basic == Version(major=1, minor=2, patch=3)
        assert basic.prerelease == ()
        assert basic.build == ()
        assert basic.is_prerelease is False
        assert basic.format() == "1.2.3"

        prerelease = self.checked_versionengine.parse_version("1.2.3-alpha.1")
        assert prerelease.prerelease == ("alpha", "1")
        assert prerelease.is_prerelease is True
        assert prerelease.format() == "1.2.3-alpha.1"

        build = self.checked_versionengine.parse_version("1.0.0-beta+exp.sha.5114f85")
        assert build.major == 1
        assert build.prerelease == ("beta",)
        assert build.build == ("exp", "sha", "5114f85")

        zero = self.checked_versionengine.parse_version("0.0.0")
        assert zero.major == 0
        assert zero.minor == 0
        assert zero.patch == 0

    def test_compare_precedence_prerelease_ordering(self) -> None:
        normal = Version(major=1, minor=0, patch=0)
        prerelease = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
        numeric = Version(major=1, minor=0, patch=0, prerelease=("1",))
        alphanumeric = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
        shorter = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
        longer = Version(major=1, minor=0, patch=0, prerelease=("alpha", "1"))
        lower_numeric = Version(major=1, minor=0, patch=0, prerelease=("alpha", "1"))
        higher_numeric = Version(major=1, minor=0, patch=0, prerelease=("alpha", "2"))
        lower_alpha = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
        higher_alpha = Version(major=1, minor=0, patch=0, prerelease=("beta",))
        build_one = Version(major=1, minor=0, patch=0, prerelease=("alpha",), build=("build", "1"))
        build_two = Version(major=1, minor=0, patch=0, prerelease=("alpha",), build=("build", "2"))
        major_two = Version(major=2, minor=0, patch=0)

        assert self.checked_versionengine.compare_precedence(normal, prerelease) > 0
        assert self.checked_versionengine.compare_precedence(prerelease, normal) < 0
        assert self.checked_versionengine.compare_precedence(numeric, alphanumeric) < 0
        assert self.checked_versionengine.compare_precedence(alphanumeric, numeric) > 0
        assert self.checked_versionengine.compare_precedence(shorter, longer) < 0
        assert self.checked_versionengine.compare_precedence(longer, shorter) > 0
        assert self.checked_versionengine.compare_precedence(lower_numeric, higher_numeric) < 0
        assert self.checked_versionengine.compare_precedence(higher_numeric, lower_numeric) > 0
        assert self.checked_versionengine.compare_precedence(lower_alpha, higher_alpha) < 0
        assert self.checked_versionengine.compare_precedence(higher_alpha, lower_alpha) > 0
        assert self.checked_versionengine.compare_precedence(build_one, build_two) == 0
        assert self.checked_versionengine.compare_precedence(normal, major_two) < 0
        assert self.checked_versionengine.compare_precedence(major_two, normal) > 0

    def test_parse_range_comparator_families(self) -> None:
        assert self.checked_versionengine.parse_range("1.2.3").raw_text == "1.2.3"
        assert self.checked_versionengine.parse_range("=1.2.3").raw_text == "=1.2.3"
        assert self.checked_versionengine.parse_range("==1.0.0").raw_text == "==1.0.0"
        assert self.checked_versionengine.parse_range("!=1.0.0").raw_text == "!=1.0.0"
        assert self.checked_versionengine.parse_range(">1.0.0").raw_text == ">1.0.0"
        assert self.checked_versionengine.parse_range(">=1.0.0").raw_text == ">=1.0.0"
        assert self.checked_versionengine.parse_range("<2.0.0").raw_text == "<2.0.0"
        assert self.checked_versionengine.parse_range("<=2.0.0").raw_text == "<=2.0.0"
        assert self.checked_versionengine.parse_range("^1.2.0").raw_text == "^1.2.0"
        assert self.checked_versionengine.parse_range("~1.2.3").raw_text == "~1.2.3"
        assert self.checked_versionengine.parse_range("1.x").raw_text == "1.x"
        assert self.checked_versionengine.parse_range("1.2.x").raw_text == "1.2.x"
        assert self.checked_versionengine.parse_range("1.*").raw_text == "1.*"
        assert self.checked_versionengine.parse_range("*").raw_text == "*"
        assert self.checked_versionengine.parse_range("1.0.0 - 2.0.0").raw_text == "1.0.0 - 2.0.0"
        assert self.checked_versionengine.parse_range(">= 1.0.0").raw_text == ">= 1.0.0"
        assert self.checked_versionengine.parse_range(">=1.0.0 <2.0.0").raw_text == ">=1.0.0 <2.0.0"
        assert self.checked_versionengine.parse_range(">=1.0.0 || <0.5.0").raw_text == ">=1.0.0 || <0.5.0"

    def test_satisfies_prerelease_admission_and_union_fallthrough(self) -> None:
        plain = self.checked_versionengine.parse_range(">=1.0.0")
        union = self.checked_versionengine.parse_range(">=1.0.0 || <0.5.0")
        explicit = self.checked_versionengine.parse_range("1.2.3-alpha.1")

        stable = Version(major=1, minor=2, patch=3)
        candidate = Version(major=1, minor=2, patch=3, prerelease=("beta",))
        targeted = Version(major=1, minor=2, patch=3, prerelease=("alpha", "1"))
        older = Version(major=0, minor=1, patch=0)

        assert self.checked_versionengine.satisfies(stable, plain, False) is True
        assert self.checked_versionengine.satisfies(candidate, plain, False) is False
        assert self.checked_versionengine.satisfies(candidate, plain, True) is True
        assert self.checked_versionengine.satisfies(targeted, explicit, False) is True
        assert self.checked_versionengine.satisfies(older, union, False) is True
        assert self.checked_versionengine.satisfies(stable, union, False) is True

    def test_satisfies_comparator_families(self) -> None:
        greater = self.checked_versionengine.parse_range(">1.0.0")
        greater_equal = self.checked_versionengine.parse_range(">=1.0.0")
        less = self.checked_versionengine.parse_range("<2.0.0")
        less_equal = self.checked_versionengine.parse_range("<=2.0.0")
        not_equal = self.checked_versionengine.parse_range("!=1.0.0")
        equal = self.checked_versionengine.parse_range("==1.0.0")
        equal_single = self.checked_versionengine.parse_range("=1.2.3")
        bare = self.checked_versionengine.parse_range("1.2.3")
        caret = self.checked_versionengine.parse_range("^1.2.0")
        tilde = self.checked_versionengine.parse_range("~1.2.3")
        wild_major = self.checked_versionengine.parse_range("1.x")
        wild_minor = self.checked_versionengine.parse_range("1.2.x")
        wild_star = self.checked_versionengine.parse_range("1.*")
        bare_star = self.checked_versionengine.parse_range("*")
        hyphen = self.checked_versionengine.parse_range("1.0.0 - 2.0.0")

        lower = Version(major=1, minor=5, patch=0)
        upper = Version(major=2, minor=5, patch=0)
        exact = Version(major=1, minor=2, patch=3)
        patch_nine = Version(major=1, minor=2, patch=9)
        very_new = Version(major=9, minor=9, patch=9)

        assert self.checked_versionengine.satisfies(lower, greater, False) is True
        assert self.checked_versionengine.satisfies(lower, greater_equal, False) is True
        assert self.checked_versionengine.satisfies(lower, less, False) is True
        assert self.checked_versionengine.satisfies(lower, less_equal, False) is True
        assert self.checked_versionengine.satisfies(upper, less_equal, False) is False
        assert self.checked_versionengine.satisfies(lower, not_equal, False) is True
        assert self.checked_versionengine.satisfies(Version(major=1, minor=0, patch=0), equal, False) is True
        assert self.checked_versionengine.satisfies(exact, equal_single, False) is True
        assert self.checked_versionengine.satisfies(exact, bare, False) is True
        assert self.checked_versionengine.satisfies(lower, caret, False) is True
        assert self.checked_versionengine.satisfies(patch_nine, tilde, False) is True
        assert self.checked_versionengine.satisfies(lower, wild_major, False) is True
        assert self.checked_versionengine.satisfies(patch_nine, wild_minor, False) is True
        assert self.checked_versionengine.satisfies(lower, wild_star, False) is True
        assert self.checked_versionengine.satisfies(very_new, bare_star, False) is True
        assert self.checked_versionengine.satisfies(lower, hyphen, False) is True

    def test_satisfies_caret_component_boundaries(self) -> None:
        caret_major = self.checked_versionengine.parse_range("^1.2.0")
        caret_minor = self.checked_versionengine.parse_range("^0.2.3")
        caret_patch = self.checked_versionengine.parse_range("^0.0.3")
        caret_zero = self.checked_versionengine.parse_range("^0.0.0")

        assert self.checked_versionengine.satisfies(Version(major=1, minor=9, patch=0), caret_major, False) is True
        assert self.checked_versionengine.satisfies(Version(major=2, minor=0, patch=0), caret_major, False) is False
        assert self.checked_versionengine.satisfies(Version(major=0, minor=2, patch=9), caret_minor, False) is True
        assert self.checked_versionengine.satisfies(Version(major=0, minor=3, patch=0), caret_minor, False) is False
        assert self.checked_versionengine.satisfies(Version(major=0, minor=0, patch=3), caret_patch, False) is True
        assert self.checked_versionengine.satisfies(Version(major=0, minor=0, patch=4), caret_patch, False) is False
        assert self.checked_versionengine.satisfies(Version(major=0, minor=0, patch=0), caret_zero, False) is True
        assert self.checked_versionengine.satisfies(Version(major=0, minor=0, patch=1), caret_zero, False) is False

    def test_package_registration_and_lookup(self) -> None:
        release = SAMPLE_RELEASES[0]
        self.checked_packagerepository.register_package(release)
        assert self.checked_packagerepository.has_package("alpha") is True
        assert self.checked_packagerepository.has_package("missing") is False
        releases = self.checked_packagerepository.get_releases("alpha")
        assert len(releases) == 1
        assert releases[0].name == "alpha"
        assert "alpha" in self.checked_packagerepository.all_packages()

    def test_dependency_resolution_backtracks_and_records_steps(self) -> None:
        alpha_two = PackageRelease(
            name="alpha",
            version=Version(major=2, minor=0, patch=0),
            dependencies=(PackageDependency(name="gamma", range_constraint=VersionRange(raw_text=">=2.0.0")),),
        )
        alpha_one = PackageRelease(
            name="alpha",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(PackageDependency(name="gamma", range_constraint=VersionRange(raw_text="==1.2.3")),),
        )
        gamma_one = PackageRelease(name="gamma", version=Version(major=1, minor=2, patch=3), dependencies=())
        gamma_two = PackageRelease(name="gamma", version=Version(major=2, minor=0, patch=3), dependencies=())
        beta_one = PackageRelease(
            name="beta",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=1.0.0")),),
        )
        self.checked_packagerepository.register_package(alpha_two)
        self.checked_packagerepository.register_package(alpha_one)
        self.checked_packagerepository.register_package(gamma_one)
        self.checked_packagerepository.register_package(gamma_two)
        self.checked_packagerepository.register_package(beta_one)
        roots = [
            PackageDependency(name="beta", range_constraint=VersionRange(raw_text=">=1.0.0")),
            PackageDependency(name="gamma", range_constraint=VersionRange(raw_text="==1.2.3")),
        ]
        outcome = self.checked_dependencysolver.resolve(roots)
        assert outcome.selected_versions["beta"] == Version(major=1, minor=0, patch=0)
        assert outcome.selected_versions["alpha"] == Version(major=1, minor=0, patch=0)
        assert outcome.selected_versions["gamma"] == Version(major=1, minor=2, patch=3)
        assert len(outcome.derivation_steps) > 0

    def test_dependency_resolution_backtracks_when_package_has_no_release(self) -> None:
        alpha_two = PackageRelease(
            name="alpha",
            version=Version(major=2, minor=0, patch=0),
            dependencies=(PackageDependency(name="delta", range_constraint=VersionRange(raw_text="==9.9.9")),),
        )
        alpha_one = PackageRelease(name="alpha", version=Version(major=1, minor=0, patch=0), dependencies=())
        self.checked_packagerepository.register_package(alpha_two)
        self.checked_packagerepository.register_package(alpha_one)
        roots = [PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=1.0.0"))]
        outcome = self.checked_dependencysolver.resolve(roots)
        assert outcome.selected_versions["alpha"] == Version(major=1, minor=0, patch=0)
        assert "delta" not in outcome.selected_versions
        assert len(outcome.derivation_steps) > 0

    def test_dependency_resolution_withdraws_rejected_candidate_constraints(self) -> None:
        alpha_two = PackageRelease(
            name="alpha",
            version=Version(major=2, minor=0, patch=0),
            dependencies=(PackageDependency(name="delta", range_constraint=VersionRange(raw_text="==9.9.9")),),
        )
        alpha_one = PackageRelease(name="alpha", version=Version(major=1, minor=0, patch=0), dependencies=())
        beta_two = PackageRelease(
            name="beta",
            version=Version(major=2, minor=0, patch=0),
            dependencies=(PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="==2.0.0")),),
        )
        beta_one = PackageRelease(
            name="beta",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="==1.0.0")),),
        )
        self.checked_packagerepository.register_package(alpha_two)
        self.checked_packagerepository.register_package(alpha_one)
        self.checked_packagerepository.register_package(beta_two)
        self.checked_packagerepository.register_package(beta_one)
        roots = [PackageDependency(name="beta", range_constraint=VersionRange(raw_text=">=1.0.0"))]
        outcome = self.checked_dependencysolver.resolve(roots)
        assert outcome.selected_versions["beta"] == Version(major=1, minor=0, patch=0)
        assert outcome.selected_versions["alpha"] == Version(major=1, minor=0, patch=0)
        assert "delta" not in outcome.selected_versions
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

    def format(self) -> str:
        """Dispatches the Version.format operation against a real parsed Version."""
        version = self.versionengine.parse_version("1.0.0")
        return version.format()

    @property
    def is_prerelease(self) -> bool:
        """Dispatches the Version.is_prerelease property against a real parsed Version."""
        version = self.versionengine.parse_version("1.2.3-alpha.1")
        return version.is_prerelease


def make_sut() -> SemverSolverSUT:
    return SemverSolverSUT()


SemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverSolverState,
    name="SemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T22:11:18Z
# LAST_CHANGED: 2026-11-04T22:10:43Z
# CHANGE: Expanded real scenario coverage: evaluates satisfies across inequality/equality/caret/tilde/wildcard/hyphen families, exercises caret expansion at positive-major, zero-major, zero-minor, and zero-patch boundaries, verifies prerelease numeric-vs-alphanumeric, length, and ordering in both argument directions, and adds dependency-resolution scenarios for a package with zero candidate releases and for a package whose rejected candidates' constraints are withdrawn before a lower enclosing candidate resolves with non-empty derivation steps.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T22:11:18Z
# PRETENSE_QA_AUDIT: 2026-11-04T22:11:07Z
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
from benchmark_1.parts.semver_solver.lib.semver_solver import (
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


VALID_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "0.0.1",
    "0.1.0",
    "0.1.0-alpha",
    "1.0.0",
    "1.0.0-0.3.7",
    "1.0.0-beta+exp.sha.5114f85",
    "1.0.0-rc.1",
    "1.0.0-x.7.z.92",
    "1.0.0+20130313144700",
    "1.2.3",
    "1.2.3-alpha.1",
    "1.2.3-alpha.1+build.5",
    "1.2.3+build.5",
    "2.0.0",
    "2.1.3",
    "3.4.5-beta.2+build.99",
    "10.20.30",
)

VALID_RANGE_TEXTS: Tuple[str, ...] = (
    ">=1.0.0",
    ">1.0.0",
    "<=2.0.0",
    "<2.0.0",
    "==1.0.0",
    "!=1.0.0",
    "=1.2.3",
    "1.2.3",
    "1.2.3-alpha.1",
    "1.0.0-rc.1",
    ">=1.0.0-rc.1",
    "<2.0.0-beta.1",
    "1.0.0-beta.2 - 2.0.0-rc.1",
    ">= 1.0.0",
    "^1.2.0",
    "^0.2.3",
    "^0.0.3",
    "^0.0.0",
    "~1.2.3",
    "~0.2.3",
    "~0.0.3",
    "1.x",
    "1.2.x",
    "1.*",
    "*",
    ">=1.0.0 <2.0.0",
    "1.0.0 - 2.0.0",
    ">=1.0.0 || <0.5.0",
)

SAMPLE_VERSION = Version(major=1, minor=0, patch=0)
SAMPLE_PRERELEASE = Version(major=1, minor=2, patch=3, prerelease=("alpha", "1"), build=("build", "5"))

VALID_RANGE_CONSTRAINTS: Tuple[VersionRange, ...] = (
    VersionRange(raw_text=">=1.0.0"),
    VersionRange(raw_text=">1.0.0"),
    VersionRange(raw_text="<=2.0.0"),
    VersionRange(raw_text="<2.0.0"),
    VersionRange(raw_text="==1.0.0"),
    VersionRange(raw_text="!=1.0.0"),
    VersionRange(raw_text="=1.2.3"),
    VersionRange(raw_text="1.2.3"),
    VersionRange(raw_text="1.2.3-alpha.1"),
    VersionRange(raw_text="1.0.0-rc.1"),
    VersionRange(raw_text=">=1.0.0-rc.1"),
    VersionRange(raw_text="<2.0.0-beta.1"),
    VersionRange(raw_text="1.0.0-beta.2 - 2.0.0-rc.1"),
    VersionRange(raw_text=">= 1.0.0"),
    VersionRange(raw_text="^1.2.0"),
    VersionRange(raw_text="^0.2.3"),
    VersionRange(raw_text="^0.0.3"),
    VersionRange(raw_text="^0.0.0"),
    VersionRange(raw_text="~1.2.3"),
    VersionRange(raw_text="~0.2.3"),
    VersionRange(raw_text="~0.0.3"),
    VersionRange(raw_text="1.x"),
    VersionRange(raw_text="1.2.x"),
    VersionRange(raw_text="1.*"),
    VersionRange(raw_text="*"),
    VersionRange(raw_text=">=1.0.0 <2.0.0"),
    VersionRange(raw_text="1.0.0 - 2.0.0"),
    VersionRange(raw_text=">=1.0.0 || <0.5.0"),
)

SAMPLE_RELEASES: Tuple[PackageRelease, ...] = (
    PackageRelease(name="alpha", version=SAMPLE_VERSION, dependencies=()),
    PackageRelease(name="beta", version=Version(major=2, minor=3, patch=1), dependencies=()),
)


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    versions: List[Version] = field(default_factory=list)
    ranges: List[VersionRange] = field(default_factory=list)
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    dependencies: List[PackageDependency] = field(default_factory=list)
    outcomes: List[ResolutionOutcome] = field(default_factory=list)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(Version.format)
    def format(self) -> str:
        ret: str = make_return_value("0.0.1")
        assert ret is not None
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        ret: bool = make_return_value(False)
        assert ret is not None
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require_arg(text, Domain.sampled_from(VALID_VERSION_TEXTS))
        ret: Version = make_return_value(SAMPLE_VERSION)
        self.state.versions.append(ret)
        assert ret is not None
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require_arg(v1, Domain.type(Version))
        require_arg(v2, Domain.type(Version))
        ret: int = make_return_value(0)
        assert ret is not None
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require_arg(text, Domain.sampled_from(VALID_RANGE_TEXTS))
        ret: VersionRange = make_return_value(VALID_RANGE_CONSTRAINTS[0])
        self.state.ranges.append(ret)
        assert ret is not None
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(version, Domain.type(Version))
        require_arg(range_constraint, Domain.sampled_from(VALID_RANGE_CONSTRAINTS))
        require_arg(include_prerelease, Domain.boolean(), preferred=[True, False])
        ret: bool = make_return_value(True)
        assert ret is not None
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require_arg(release, Domain.type(PackageRelease))
        ret = make_return_value()
        releases = self.state.packages.setdefault(release.name, [])
        releases.append(release)
        constraint = VersionRange(
            raw_text="==" + f"{release.version.major}.{release.version.minor}.{release.version.patch}"
        )
        self.state.dependencies.append(PackageDependency(name=release.name, range_constraint=constraint))
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require_arg(name, Domain.in_set(tuple(self.state.packages.keys())))
        released = list(self.state.packages[name])
        ret: List[PackageRelease] = make_return_value(released)
        assert ret is not None
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require_arg(name, Domain.type(str))
        ret: bool = make_return_value(name in self.state.packages)
        assert ret is not None
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        ret: Set[str] = make_return_value(set(self.state.packages.keys()))
        assert ret is not None
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require_arg(root_dependencies, Domain.type(Collection[PackageDependency]))
        outcome = ResolutionOutcome(selected_versions={}, derivation_steps=())
        ret: ResolutionOutcome = make_return_value(outcome)
        self.state.outcomes.append(ret)
        assert ret is not None
        return ret


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(
    state: Optional[SemverSolverState] = None,
) -> Any:
    """Creates a synthesized fake modeling every SemverSolver interface transition."""
    return FakeSemverSolver(state=state or SemverSolverState())


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[Any, Any, Any, Any, Any, Any, Any, Any, Any]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = make_semver_solver_fake(state)
    return (fake, fake, fake, fake, fake, fake, fake, fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all declared interface transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_solver_fake()
        self.sm = SemverSolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition on the synthesized fake."""
        formatted = self.fake.format()
        assert formatted is not None
        assert self.sm.format() is not None
        assert self.fake.is_prerelease is not None
        assert self.sm.is_prerelease() is not None

        parsed = self.fake.parse_version("1.0.0")
        assert parsed.major == 1
        assert self.sm.parse_version("1.2.3-alpha.1+build.5").major == 1

        comparison = self.fake.compare_precedence(parsed, parsed)
        assert comparison == 0
        assert self.sm.compare_precedence(parsed, parsed) == 0

        parsed_range = self.fake.parse_range(">=1.0.0")
        assert parsed_range.raw_text == ">=1.0.0"
        assert self.sm.parse_range("1.x").raw_text == ">=1.0.0"

        matched = self.fake.satisfies(parsed, parsed_range, True)
        assert matched is True
        assert self.sm.satisfies(parsed, parsed_range, False) is True

        release = SAMPLE_RELEASES[0]
        assert self.fake.register_package(release) is None
        assert self.sm.register_package(release) is None

        releases = self.fake.get_releases("alpha")
        assert len(releases) == 1
        assert len(self.sm.get_releases("alpha")) >= 1

        assert self.fake.has_package("alpha") is True
        assert self.sm.has_package("alpha") is True

        names = self.fake.all_packages()
        assert "alpha" in names
        assert "alpha" in self.sm.all_packages()

        outcome = self.fake.resolve([])
        assert outcome is not None
        assert self.sm.resolve([]) is not None


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T22:10:28Z
# LAST_CHANGED: 2026-11-04T22:10:28Z
# CHANGE: Added zero-major and zero-major/minor caret range expressions (^0.2.3, ^0.0.3, ^0.0.0) plus matching tilde zero-boundary ranges to the valid-range corpora so caret component-boundary expansion is reachable through checked satisfies calls.
# --- END AUTOFAB METADATA ---
