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
from benchmark_3.parts.semver_solver.pretense.semver_solver_pretense import (
    FakeSemverSolver,
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fakes,
)
from benchmark_3.parts.semver_solver.lib.semver_solver import (
    PackageDependency,
    PackageRelease,
    ResolutionOutcome,
    Version,
    VersionRange,
)
from benchmark_3.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# REFERENCE PATTERNS:
#   # Implementation pseudo-state machine transition override with call_target:
#   @transition(TargetClass.method)
#   def method(self, *args) -> Any:
#       target: TargetClass = sut(TargetClass)
#       old_val = target.property
#       ret = call_target(target.method(*args))
#       assert target.property == old_val
#       return ret

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.major >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        assert isinstance(ret.raw_text, str)
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert target.has_package(release.name)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> Any:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert isinstance(ret, ResolutionOutcome)
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

_RELEASES: Tuple[PackageRelease, ...] = (
    PackageRelease("alpha", Version(1, 0, 0)),
    PackageRelease(
        "alpha",
        Version(1, 5, 0),
        (PackageDependency("beta", VersionRange(">=1.0.0")),),
    ),
    PackageRelease(
        "alpha",
        Version(2, 0, 0),
        (
            PackageDependency("delta", VersionRange(">=1.0.0")),
            PackageDependency("beta", VersionRange("<2.0.0")),
        ),
    ),
    PackageRelease("beta", Version(1, 0, 0)),
    PackageRelease("beta", Version(2, 0, 0)),
    PackageRelease("gamma", Version(0, 5, 0)),
    PackageRelease(
        "gamma",
        Version(1, 0, 0),
        (
            PackageDependency("alpha", VersionRange(">=1.5.0")),
            PackageDependency("epsilon", VersionRange(">=1.0.0")),
        ),
    ),
    PackageRelease(
        "epsilon",
        Version(1, 0, 0),
        (PackageDependency("zeta", VersionRange(">=1.0.0")),),
    ),
)

_ROOT_ALPHA = PackageDependency("alpha", VersionRange(">=0.0.0"))
_ROOT_BETA = PackageDependency("beta", VersionRange(">=2.0.0"))
_ROOT_GAMMA = PackageDependency("gamma", VersionRange(">=0.0.0"))


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
        self.checked_packagerepository = self.sm.as_checked(
            PackageRepository, self.packagerepository
        )
        self.checked_dependencysolver = self.sm.as_checked(
            DependencySolver, self.dependencysolver
        )
        for release in _RELEASES:
            self.checked_packagerepository.register_package(release)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version(self) -> None:
        for text in (
            "0.0.1",
            "1.0.0",
            "1.2.3",
            "2.0.0+build.5",
            "1.2.3-alpha.1",
            "1.2.3-alpha.1+build.2",
        ):
            parsed = self.checked_versionengine.parse_version(text)
            assert parsed.format() == text
        assert Version(1, 2, 3, ("rc",), ("b",)).format() == "1.2.3-rc+b"
        assert Version(1, 0, 0).is_prerelease is False
        assert Version(1, 0, 0, ("rc",)).is_prerelease is True
        assert str(Version(1, 2, 3)) == "1.2.3"
        assert str(VersionRange("^1.0.0")) == "^1.0.0"

    def test_compare_precedence(self) -> None:
        cases = (
            (Version(2, 0, 0), Version(1, 0, 0)),
            (Version(1, 2, 3), Version(1, 0, 0)),
            (Version(1, 0, 1), Version(1, 0, 0)),
            (Version(1, 0, 0), Version(1, 0, 0)),
            (Version(1, 2, 3), Version(1, 2, 3, ("alpha",))),
            (Version(1, 2, 3, ("alpha",)), Version(1, 2, 3)),
            (Version(1, 2, 3, ("1",)), Version(1, 2, 3, ("2",))),
            (Version(1, 2, 3, ("1",)), Version(1, 2, 3, ("alpha",))),
            (Version(1, 2, 3, ("alpha",)), Version(1, 2, 3, ("1",))),
            (Version(1, 2, 3, ("alpha",)), Version(1, 2, 3, ("beta",))),
            (Version(1, 2, 3, ("beta",)), Version(1, 2, 3, ("alpha",))),
            (Version(1, 2, 3, ("alpha", "1")), Version(1, 2, 3, ("alpha",))),
        )
        for left, right in cases:
            self.checked_versionengine.compare_precedence(left, right)

    def test_parse_range(self) -> None:
        for text in (
            ">=1.0.0",
            "==1.2.3",
            "=1.2.3",
            "!=1.2.3",
            ">1.0.0",
            "<2.0.0",
            "<=2.0.0",
            "^1.0.0",
            "~1.2.3",
            "*",
            "x",
            "X",
            "1.x",
            "1.2.*",
            "1.0.0 - 2.0.0",
            ">=1.0.0 <2.0.0",
            ">=1.0.0 || <0.5.0",
            "^1.2.3-alpha.1",
            ">= 1.0.0",
        ):
            self.checked_versionengine.parse_range(text)
        trimmed = self.checked_versionengine.parse_range("  >= 1.0.0  ")
        assert trimmed.raw_text == ">= 1.0.0"

    def test_satisfies(self) -> None:
        cases = (
            (Version(1, 2, 3), VersionRange("1.2.3"), False, True),
            (Version(2, 0, 0), VersionRange("1.2.3"), False, False),
            (Version(1, 2, 3), VersionRange("==1.2.3"), False, True),
            (Version(1, 2, 3), VersionRange("=1.2.3"), False, True),
            (Version(1, 5, 0), VersionRange("!=1.2.3"), False, True),
            (Version(1, 2, 3), VersionRange("!=1.2.3"), False, False),
            (Version(2, 5, 0), VersionRange(">1.0.0"), False, True),
            (Version(1, 0, 0), VersionRange(">1.0.0"), False, False),
            (Version(1, 2, 3), VersionRange(">=1.0.0"), False, True),
            (Version(0, 0, 1), VersionRange(">=1.0.0"), False, False),
            (Version(1, 0, 0), VersionRange("<2.0.0"), False, True),
            (Version(2, 5, 0), VersionRange("<2.0.0"), False, False),
            (Version(2, 0, 0), VersionRange("<=2.0.0"), False, True),
            (Version(2, 5, 0), VersionRange("<=2.0.0"), False, False),
            (Version(1, 5, 0), VersionRange("^1.0.0"), False, True),
            (Version(2, 0, 0), VersionRange("^1.0.0"), False, False),
            (Version(0, 1, 0), VersionRange("^0.1.0"), False, True),
            (Version(1, 0, 0), VersionRange("^0.1.0"), False, False),
            (Version(0, 0, 1), VersionRange("^0.0.1"), False, True),
            (Version(0, 1, 0), VersionRange("^0.0.1"), False, False),
            (Version(1, 2, 3), VersionRange("~1.2.3"), False, True),
            (Version(1, 5, 0), VersionRange("~1.2.3"), False, False),
            (Version(1, 2, 3), VersionRange("*"), False, True),
            (Version(1, 5, 0), VersionRange("1.x"), False, True),
            (Version(2, 0, 0), VersionRange("1.x"), False, False),
            (Version(1, 2, 3), VersionRange("1.2.*"), False, True),
            (Version(1, 5, 0), VersionRange("1.2.*"), False, False),
            (Version(1, 5, 0), VersionRange("1.0.0 - 2.0.0"), False, True),
            (Version(2, 5, 0), VersionRange("1.0.0 - 2.0.0"), False, False),
            (Version(1, 5, 0), VersionRange(">=1.0.0 <2.0.0"), False, True),
            (Version(2, 5, 0), VersionRange(">=1.0.0 <2.0.0"), False, False),
            (Version(1, 0, 0), VersionRange(">=2.0.0 || <0.5.0"), False, False),
            (Version(5, 0, 0), VersionRange(">=1.0.0 || <0.5.0"), False, True),
            (Version(0, 0, 1), VersionRange(">=1.0.0 || <0.5.0"), False, True),
            (Version(1, 2, 3, ("alpha",)), VersionRange(">=1.0.0"), False, False),
            (Version(1, 2, 3, ("alpha", "1")), VersionRange("^1.2.3-alpha.1"), False, True),
            (Version(1, 2, 3, ("alpha",)), VersionRange(">=1.0.0"), True, True),
            (Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), True, False),
            (Version(1, 2, 3, ("alpha",)), VersionRange("1.0.0 - 2.0.0"), False, False),
            (Version(1, 2, 3, ("alpha",)), VersionRange("*"), False, False),
            (Version(1, 2, 3, ("alpha",)), VersionRange("1.2.*"), False, False),
            (Version(1, 2, 3, ("alpha",)), VersionRange(">=1.0.0 || ^1.2.3-alpha.1"), False, True),
            (Version(2, 0, 0), VersionRange("!=1.x"), False, True),
            (Version(1, 5, 0), VersionRange("!=1.x"), False, False),
            (Version(2, 0, 0), VersionRange(">1.x"), False, True),
            (Version(1, 5, 0), VersionRange(">1.x"), False, False),
            (Version(1, 0, 0), VersionRange(">=1.x"), False, True),
            (Version(0, 1, 0), VersionRange("<1.x"), False, True),
            (Version(1, 5, 0), VersionRange("<=1.x"), False, True),
            (Version(1, 5, 0), VersionRange("^1.x"), False, True),
            (Version(1, 5, 0), VersionRange("~1.x"), False, True),
        )
        for version, range_constraint, include_prerelease, expected in cases:
            with self.subTest(
                version=version,
                range_constraint=range_constraint,
                include_prerelease=include_prerelease,
            ):
                satisfied = self.checked_versionengine.satisfies(
                    version, range_constraint, include_prerelease
                )
                assert satisfied is expected

    def test_repository(self) -> None:
        assert self.checked_packagerepository.has_package("alpha") is True
        assert self.checked_packagerepository.has_package("delta") is False
        assert self.checked_packagerepository.all_packages() == {
            "alpha",
            "beta",
            "epsilon",
            "gamma",
        }
        releases = self.checked_packagerepository.get_releases("alpha")
        assert [release.version for release in releases] == [
            Version(2, 0, 0),
            Version(1, 5, 0),
            Version(1, 0, 0),
        ]

    def test_resolve_empty(self) -> None:
        outcome = self.checked_dependencysolver.resolve([])
        assert outcome.selected_versions == {}
        assert outcome.derivation_steps == ()

    def test_resolve_backtracks(self) -> None:
        outcome = self.checked_dependencysolver.resolve([_ROOT_ALPHA])
        assert outcome.selected_versions == {
            "alpha": Version(1, 5, 0),
            "beta": Version(2, 0, 0),
        }
        assert len(outcome.derivation_steps) > 0

    def test_resolve_forward_checking(self) -> None:
        outcome = self.checked_dependencysolver.resolve([_ROOT_ALPHA, _ROOT_BETA])
        assert outcome.selected_versions == {
            "alpha": Version(1, 5, 0),
            "beta": Version(2, 0, 0),
        }

    def test_resolve_transitive(self) -> None:
        outcome = self.checked_dependencysolver.resolve([_ROOT_GAMMA])
        assert outcome.selected_versions == {
            "gamma": Version(0, 5, 0),
        }


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
# LAST_CLEANED: 2026-11-04T21:58:02Z
# LAST_CHANGED: 2026-11-04T21:58:02Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 12e49bc38185
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T21:58:02Z
# PRETENSE_QA_AUDIT: 2026-11-04T21:58:02Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, FrozenSet, List, Optional, Set, Tuple, cast
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
from benchmark_3.parts.semver_solver.lib.semver_solver import (
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
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException): ())
# live naturally inside the single transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).

_PACKAGE_NAMES: Tuple[str, ...] = ("alpha", "beta", "gamma")

_VERSIONS: Tuple[Version, ...] = (
    Version(0, 0, 1),
    Version(0, 1, 0),
    Version(1, 0, 0),
    Version(1, 0, 1),
    Version(1, 0, 0, ("alpha",)),
    Version(1, 2, 3),
    Version(1, 5, 0),
    Version(2, 0, 0),
    Version(2, 5, 0),
    Version(5, 0, 0),
    Version(1, 2, 3, ("alpha",)),
    Version(1, 2, 3, ("alpha", "1")),
    Version(1, 2, 3, ("1",)),
    Version(1, 2, 3, ("2",)),
    Version(1, 2, 3, ("beta",)),
    Version(1, 2, 3, (), ("build", "1")),
)

_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.1",
    "1.0.0",
    "1.2.3",
    "2.0.0+build.5",
    "1.2.3-alpha.1",
    "1.2.3-alpha.1+build.2",
)

_RANGES: Tuple[VersionRange, ...] = (
    VersionRange("1.2.3"),
    VersionRange("==1.2.3"),
    VersionRange("=1.2.3"),
    VersionRange("!=1.2.3"),
    VersionRange(">1.0.0"),
    VersionRange(">=1.0.0"),
    VersionRange("<2.0.0"),
    VersionRange("<=2.0.0"),
    VersionRange("^0.0.1"),
    VersionRange("^0.1.0"),
    VersionRange("^1.0.0"),
    VersionRange("~1.2.3"),
    VersionRange("*"),
    VersionRange("1.x"),
    VersionRange("1.2.*"),
    VersionRange("1.0.0 - 2.0.0"),
    VersionRange(">=1.0.0 <2.0.0"),
    VersionRange(">=1.0.0 || <0.5.0"),
    VersionRange(">=2.0.0 || <0.5.0"),
    VersionRange(">=1.0.0 || ^1.2.3-alpha.1"),
    VersionRange("^1.2.3-alpha.1"),
    VersionRange(">=1.2.3-alpha.1"),
    VersionRange("!=1.x"),
    VersionRange(">1.x"),
    VersionRange(">=1.x"),
    VersionRange("<1.x"),
    VersionRange("<=1.x"),
    VersionRange("~1.x"),
    VersionRange("^1.x"),
)

_RANGE_TEXTS: Tuple[str, ...] = tuple(str(value) for value in _RANGES) + (
    "  >= 1.0.0  ",
    ">= 1.0.0",
    "1.0.0 - 2.0.0",
    "x",
    "X",
)

# Fixed oracle outcomes synthesized by the fake (no target service is instantiated in transitions).
_FAKE_VERSION: Version = Version(0, 0, 0)
_FAKE_RANGE: VersionRange = VersionRange("*")
_FAKE_OUTCOME: ResolutionOutcome = ResolutionOutcome(selected_versions={}, derivation_steps=())

_DEPENDENCIES: Tuple[PackageDependency, ...] = (
    PackageDependency("alpha", VersionRange(">=0.0.0")),
    PackageDependency("beta", VersionRange(">=0.0.0")),
    PackageDependency("beta", VersionRange(">=2.0.0")),
    PackageDependency("gamma", VersionRange(">=0.0.0")),
)

_RELEASES: Tuple[PackageRelease, ...] = (
    PackageRelease("alpha", Version(1, 0, 0)),
    PackageRelease(
        "alpha",
        Version(1, 5, 0),
        (PackageDependency("beta", VersionRange(">=1.0.0")),),
    ),
    PackageRelease(
        "alpha",
        Version(2, 0, 0),
        (
            PackageDependency("delta", VersionRange(">=1.0.0")),
            PackageDependency("beta", VersionRange("<2.0.0")),
        ),
    ),
    PackageRelease("beta", Version(1, 0, 0)),
    PackageRelease("beta", Version(2, 0, 0)),
    PackageRelease("gamma", Version(0, 5, 0)),
    PackageRelease(
        "gamma",
        Version(1, 0, 0),
        (
            PackageDependency("alpha", VersionRange(">=1.5.0")),
            PackageDependency("epsilon", VersionRange(">=1.0.0")),
        ),
    ),
    PackageRelease(
        "epsilon",
        Version(1, 0, 0),
        (PackageDependency("zeta", VersionRange(">=1.0.0")),),
    ),
)

_RELEASE_KEYS: FrozenSet[Tuple[str, Version]] = frozenset(
    (release.name, release.version) for release in _RELEASES
)


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    registered: Set[Tuple[str, Version]] = field(default_factory=set)
    ready: bool = False


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
        require_arg(text, Domain.sampled_from(_VERSION_TEXTS))
        ret: Version = self.inner_parse_version(text)
        assert ret.major >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(v1, Domain.sampled_from(_VERSIONS))
        require_arg(v2, Domain.sampled_from(_VERSIONS))
        ret: int = self.inner_compare_precedence(v1, v2)
        assert isinstance(ret, int)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require_arg(text, Domain.sampled_from(_RANGE_TEXTS))
        ret: VersionRange = self.inner_parse_range(text)
        assert isinstance(ret.raw_text, str)
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(version, Domain.sampled_from(_VERSIONS))
        require_arg(range_constraint, Domain.sampled_from(_RANGES))
        require_arg(include_prerelease, Domain.boolean())
        ret: bool = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(release, Domain.sampled_from(_RELEASES))
        self.state.packages.setdefault(release.name, []).append(release)
        self.state.registered.add((release.name, release.version))
        self.state.ready = _RELEASE_KEYS.issubset(self.state.registered)
        ret = self.inner_register_package(release)
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.packages)
        require_arg(name, Domain.in_set(tuple(self.state.packages.keys())))
        releases = list(self.state.packages[name])
        ret: List[PackageRelease] = self.inner_get_releases(name)
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(name, Domain.type(str))
        present = name in self.state.packages
        ret: bool = self.inner_has_package(name)
        assert ret is present
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        names = set(self.state.packages.keys())
        ret: Set[str] = self.inner_all_packages()
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        require(self.state.ready)
        require_arg(
            root_dependencies,
            cast(Any, Domain.list_of(Domain.sampled_from(_DEPENDENCIES))),
        )
        ret: ResolutionOutcome = self.inner_resolve(root_dependencies)
        assert isinstance(ret, ResolutionOutcome)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds a blank repository state for fuzz exploration."""
        self.state.packages.clear()
        self.state.registered.clear()
        self.state.ready = False


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
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fakes = make_semver_solver_fakes()
        self.fake: Any = self.fakes[0]
        self.sm = SemverSolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.fake.parse_version(_VERSION_TEXTS[0])
        self.fake.compare_precedence(_VERSIONS[0], _VERSIONS[1])
        self.fake.parse_range(_RANGE_TEXTS[0])
        self.fake.satisfies(_VERSIONS[1], _RANGES[0], False)
        for release in _RELEASES:
            self.fake.register_package(release)
        self.fake.get_releases(_PACKAGE_NAMES[0])
        self.fake.has_package(_PACKAGE_NAMES[0])
        self.fake.all_packages()
        self.fake.resolve(list(_DEPENDENCIES[:1]))


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:58:02Z
# LAST_CHANGED: 2026-11-04T21:58:02Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b1d93534c3a3
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T21:58:02Z
# PRETENSE_QA_AUDIT: 2026-11-04T21:58:02Z
# --- END AUTOFAB METADATA ---
