# === File: dependency_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Collection, List, Optional, Set, Tuple
import unittest

from pretense import (
    Env,
    StateMachine,
    require,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    fake,
    get_singleton,
    system,
)

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver as DependencySolverProtocol,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository as PackageRepositoryProtocol,
    ResolutionConflictError,
    ResolutionOutcome,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import Version
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range import VersionRange
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib import dependency_solver_impl
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    FIXTURE_RELEASES,
    DependencySolverStateMachine,
    PackageRepositoryStateMachine,
    expected_selection,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class DependencySolverImplPseudoStateMachine(
    PackageRepositoryStateMachine,
    DependencySolverStateMachine,
):
    """Implementation pseudo-state machine binding the concrete repository and solver.

    Inherits every interface transition, precondition, argument domain, and shared model
    state mutation from both implemented interface state machines; only the inner
    transitions are overridden to drive the concrete SUT singletons.
    """

    def inner_register_package(self, release: PackageRelease) -> None:
        """Registers the release on the concrete repository and verifies membership."""
        target: PackageRepository = sut(PackageRepository)
        ret = target.register_package(release)
        assert target.has_package(release.name)
        return ret

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        """Looks up concrete repository releases and verifies descending precedence."""
        target: PackageRepository = sut(PackageRepository)
        ret = target.get_releases(name)
        assert len(ret) > 0
        for index in range(len(ret)):
            assert ret[index].name == name
        for index in range(1, len(ret)):
            previous = ret[index - 1].version
            current = ret[index].version
            assert (previous.major, previous.minor, previous.patch) >= (
                current.major,
                current.minor,
                current.patch,
            )
        return ret

    def inner_has_package(self, name: str) -> bool:
        """Checks concrete repository membership consistently with enumeration."""
        target: PackageRepository = sut(PackageRepository)
        ret = target.has_package(name)
        assert ret == (name in target.all_packages())
        return ret

    def inner_all_packages(self) -> Set[str]:
        """Enumerates concrete repository package names consistently with membership."""
        target: PackageRepository = sut(PackageRepository)
        ret = target.all_packages()
        for name in ret:
            assert target.has_package(name)
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Resolves dependencies on the concrete solver and verifies the assignment."""
        target: DependencySolver = sut(DependencySolver)
        ret = target.resolve(root_dependencies)
        assert dict(ret.selected_versions) == expected_selection(root_dependencies)
        return ret


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


def _populate_repository(repository: PackageRepositoryProtocol) -> None:
    """Registers the shared package fixture into the concrete repository collaborator."""
    for release in FIXTURE_RELEASES:
        repository.register_package(release)


def make_sut() -> DependencySolverProtocol:
    """Creates and activates concrete engine, repository, and solver singletons."""
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngine)
    registry.register_singleton(RangeEngine)
    registry.register_singleton(PackageRepository)
    registry.register_singleton(DependencySolver)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    _populate_repository(get_singleton(PackageRepository))
    return get_singleton(DependencySolver)


DependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DependencySolverFuzzTest",
)


# ==============================================================================
# 3. Fixed Real-Implementation Scenarios (Implementation Components)
# ==============================================================================


class TestDependencySolverImplReal(LifecycleTestCase):
    """Verifies the concrete repository and solver against deterministic scenarios."""

    target = dependency_solver_impl

    def setUp(self) -> None:
        super().setUp()
        self.repository: PackageRepository = get_singleton(PackageRepository)
        self.solver: DependencySolver = get_singleton(DependencySolver)
        _populate_repository(self.repository)
        self.sm = DependencySolverImplPseudoStateMachine(
            singletons={
                PackageRepository: self.repository,
                DependencySolver: self.solver,
            },
        )
        self.checked = self.sm.as_checked(PackageRepository, self.repository)
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)

    def test_register_and_query(self) -> None:
        """Exercises registration, release lookup, membership, and enumeration transitions."""
        self.checked.register_package(FIXTURE_RELEASES[0])
        releases = self.checked.get_releases("a")
        self.assertEqual(len(releases), 4)
        self.assertTrue(self.checked.has_package("a"))
        self.assertFalse(self.checked.has_package("missing"))
        self.assertEqual(self.checked.all_packages(), {"a", "b", "c", "d"})

    def test_prerelease_release_ordering(self) -> None:
        """Exercises descending precedence ordering across prerelease and release versions."""
        prerelease_release = PackageRelease(
            name="d",
            version=Version(major=2, minor=0, patch=0, prerelease=("alpha",)),
            dependencies=(),
        )
        self.checked.register_package(prerelease_release)
        for release in FIXTURE_RELEASES:
            self.checked.register_package(release)
        releases = self.checked.get_releases("d")
        self.assertEqual(len(releases), 9)
        self.assertEqual(releases[0].version.major, 2)
        self.assertEqual(releases[0].version.prerelease, ())
        self.assertEqual(releases[2].version.prerelease, ("alpha",))
        self.assertEqual(releases[7].version.minor, 0)

    def test_resolve(self) -> None:
        """Exercises compatible dependency resolution against the fixture repository."""
        root_dependencies = (
            PackageDependency(name="b", range_constraint=VersionRange(raw_text=">=1.0.0")),
        )
        outcome = self.checked_solver.resolve(root_dependencies)
        self.assertEqual(dict(outcome.selected_versions)["b"].major, 2)

    def test_missing_package_violation(self) -> None:
        """Verifies unregistered package lookup surfaces PackageNotFoundError."""
        self.checked.violating(PackageNotFoundError).get_releases("missing")

    def test_absent_package_resolution_violation(self) -> None:
        """Verifies resolution over an absent repository entry surfaces ResolutionConflictError."""
        root_dependencies = (
            PackageDependency(name="missing", range_constraint=VersionRange(raw_text=">=1.0.0")),
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(root_dependencies)

    def test_unsatisfiable_resolution_violation(self) -> None:
        """Verifies mutually exclusive constraints surface ResolutionConflictError."""
        root_dependencies = (
            PackageDependency(name="a", range_constraint=VersionRange(raw_text="==1.0.0")),
            PackageDependency(name="a", range_constraint=VersionRange(raw_text="==2.0.0")),
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(root_dependencies)

    def test_assigned_conflict_resolution_violation(self) -> None:
        """Verifies an assigned release conflicting with a candidate dependency surfaces ResolutionConflictError."""
        root_dependencies = (
            PackageDependency(name="a", range_constraint=VersionRange(raw_text="==1.0.0")),
            PackageDependency(name="b", range_constraint=VersionRange(raw_text=">=2.0.0")),
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(root_dependencies)

    def test_transitive_rollback_resolution_violation(self) -> None:
        """Verifies transitive candidate constraints roll back on backtrack with a conflict error."""
        root_dependencies = (
            PackageDependency(name="a", range_constraint=VersionRange(raw_text="==1.0.0")),
            PackageDependency(name="c", range_constraint=VersionRange(raw_text="==2.0.0")),
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(root_dependencies)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T16:18:27Z
# LAST_CHANGED: 2026-11-13T16:18:02Z
# CHANGE: Add TestDependencySolverImplReal transitive-rollback scenario: violating ResolutionConflictError when root constraints pin a ==1.0.0 and c ==2.0.0, forcing c 2.0.0 to demand b >=2.0.0 and b 2.0.0 to demand a >=2.0.0, exercising transitive candidate-constraint rollback during backtracking before the search exhausts.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T16:18:27Z
# PRETENSE_QA_AUDIT: 2026-11-13T16:18:14Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
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
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import Version
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range import VersionRange
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
    ResolutionConflictError,
)


# ==============================================================================
# 1. Model Helpers (fixture repository and table-driven resolution outcomes)
# ==============================================================================


def _version(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...] = (),
) -> Version:
    """Constructs an immutable release version for the model."""
    return Version(major=major, minor=minor, patch=patch, prerelease=prerelease)


def _range(raw_text: str) -> VersionRange:
    """Constructs an immutable version range constraint for the model."""
    return VersionRange(raw_text=raw_text)


_VERSION_1_0_0 = _version(1, 0, 0)
_VERSION_1_1_0_ALPHA = _version(1, 1, 0, ("alpha",))
_VERSION_1_1_0 = _version(1, 1, 0)
_VERSION_2_0_0_ALPHA = _version(2, 0, 0, ("alpha",))
_VERSION_2_0_0 = _version(2, 0, 0)

_VERSION_RANK: Dict[Version, int] = {
    _VERSION_1_0_0: 0,
    _VERSION_1_1_0_ALPHA: 1,
    _VERSION_1_1_0: 2,
    _VERSION_2_0_0_ALPHA: 3,
    _VERSION_2_0_0: 4,
}

_DEP_A_EQ_1_0_0 = PackageDependency(name="a", range_constraint=_range("==1.0.0"))
_DEP_A_GE_1_0_0 = PackageDependency(name="a", range_constraint=_range(">=1.0.0"))
_DEP_A_GE_1_1_0 = PackageDependency(name="a", range_constraint=_range(">=1.1.0"))
_DEP_A_GE_2_0_0 = PackageDependency(name="a", range_constraint=_range(">=2.0.0"))
_DEP_B_EQ_1_0_0 = PackageDependency(name="b", range_constraint=_range("==1.0.0"))
_DEP_B_GE_1_0_0 = PackageDependency(name="b", range_constraint=_range(">=1.0.0"))
_DEP_B_GE_1_0_0_LT_2_0_0 = PackageDependency(name="b", range_constraint=_range(">=1.0.0 <2.0.0"))
_DEP_B_GE_2_0_0 = PackageDependency(name="b", range_constraint=_range(">=2.0.0"))
_DEP_C_CARET_1_0_0 = PackageDependency(name="c", range_constraint=_range("^1.0.0"))
_DEP_C_GE_1_0_0 = PackageDependency(name="c", range_constraint=_range(">=1.0.0"))

_RELEASE_A_1_0_0 = PackageRelease(name="a", version=_VERSION_1_0_0, dependencies=())
_RELEASE_A_1_1_0 = PackageRelease(name="a", version=_VERSION_1_1_0, dependencies=())
_RELEASE_A_2_0_0 = PackageRelease(name="a", version=_VERSION_2_0_0, dependencies=())
_RELEASE_B_1_0_0 = PackageRelease(name="b", version=_VERSION_1_0_0, dependencies=(_DEP_A_GE_1_0_0,))
_RELEASE_B_1_1_0 = PackageRelease(name="b", version=_VERSION_1_1_0, dependencies=(_DEP_A_GE_1_1_0,))
_RELEASE_B_2_0_0 = PackageRelease(name="b", version=_VERSION_2_0_0, dependencies=(_DEP_A_GE_2_0_0,))
_RELEASE_C_1_0_0 = PackageRelease(
    name="c", version=_VERSION_1_0_0, dependencies=(_DEP_B_GE_1_0_0_LT_2_0_0,)
)
_RELEASE_C_2_0_0 = PackageRelease(name="c", version=_VERSION_2_0_0, dependencies=(_DEP_B_GE_2_0_0,))
_RELEASE_D_1_0_0 = PackageRelease(name="d", version=_VERSION_1_0_0, dependencies=())
_RELEASE_D_1_1_0_ALPHA = PackageRelease(
    name="d", version=_VERSION_1_1_0_ALPHA, dependencies=()
)
_RELEASE_D_2_0_0_ALPHA = PackageRelease(
    name="d", version=_VERSION_2_0_0_ALPHA, dependencies=()
)
_RELEASE_D_2_0_0 = PackageRelease(name="d", version=_VERSION_2_0_0, dependencies=())

# Fixture repository shared by the model and downstream real-implementation audits.
FIXTURE_RELEASES: Tuple[PackageRelease, ...] = (
    _RELEASE_A_1_0_0,
    _RELEASE_A_1_1_0,
    _RELEASE_A_2_0_0,
    _RELEASE_B_1_0_0,
    _RELEASE_B_1_1_0,
    _RELEASE_B_2_0_0,
    _RELEASE_C_1_0_0,
    _RELEASE_C_2_0_0,
    _RELEASE_D_1_0_0,
    _RELEASE_D_1_1_0_ALPHA,
    _RELEASE_D_2_0_0_ALPHA,
    _RELEASE_D_2_0_0,
)

_SAMPLE_RELEASES: Tuple[PackageRelease, ...] = FIXTURE_RELEASES
_PACKAGE_NAMES: Tuple[str, ...] = ("a", "b", "c", "d")
_PACKAGE_NAME_CANDIDATES: Tuple[str, ...] = ("a", "b", "c", "d", "missing")


def _initial_packages() -> Dict[str, List[PackageRelease]]:
    """Constructs the shared fixture repository package index."""
    packages: Dict[str, List[PackageRelease]] = {}
    for release in FIXTURE_RELEASES:
        packages.setdefault(release.name, []).append(release)
    return packages


def _release_order_key(release: PackageRelease) -> int:
    """Ranks a release by semantic version precedence for descending ordering."""
    return _VERSION_RANK[release.version]


def _sorted_releases(releases: List[PackageRelease]) -> List[PackageRelease]:
    """Orders releases by version precedence descending, as the repository contract states."""
    return sorted(releases, key=_release_order_key, reverse=True)


_DEPS_EMPTY: Tuple[PackageDependency, ...] = ()
_DEPS_B_GE_1_0_0: Tuple[PackageDependency, ...] = (_DEP_B_GE_1_0_0,)
_DEPS_B_GE_1_0_0_LT_2_0_0: Tuple[PackageDependency, ...] = (_DEP_B_GE_1_0_0_LT_2_0_0,)
_DEPS_A_EQ_1_0_0: Tuple[PackageDependency, ...] = (_DEP_A_EQ_1_0_0,)
_DEPS_C_CARET_1_0_0: Tuple[PackageDependency, ...] = (_DEP_C_CARET_1_0_0,)
_DEPS_C_GE_1_0_0: Tuple[PackageDependency, ...] = (_DEP_C_GE_1_0_0,)
_DEPS_A_B_GE_1_0_0: Tuple[PackageDependency, ...] = (_DEP_A_GE_1_0_0, _DEP_B_GE_1_0_0)
_DEPS_A_B_EQ_1_0_0: Tuple[PackageDependency, ...] = (_DEP_A_EQ_1_0_0, _DEP_B_EQ_1_0_0)

_SAMPLE_DEPENDENCY_SETS: Tuple[Tuple[PackageDependency, ...], ...] = (
    _DEPS_EMPTY,
    _DEPS_B_GE_1_0_0,
    _DEPS_B_GE_1_0_0_LT_2_0_0,
    _DEPS_A_EQ_1_0_0,
    _DEPS_C_CARET_1_0_0,
    _DEPS_C_GE_1_0_0,
    _DEPS_A_B_GE_1_0_0,
    _DEPS_A_B_EQ_1_0_0,
)

_RESOLUTIONS: Dict[Tuple[Tuple[str, str], ...], Dict[str, Version]] = {
    (): {},
    (("b", ">=1.0.0"),): {"b": _VERSION_2_0_0, "a": _VERSION_2_0_0},
    (("b", ">=1.0.0 <2.0.0"),): {"b": _VERSION_1_1_0, "a": _VERSION_2_0_0},
    (("a", "==1.0.0"),): {"a": _VERSION_1_0_0},
    (("c", "^1.0.0"),): {"c": _VERSION_1_0_0, "b": _VERSION_1_1_0, "a": _VERSION_2_0_0},
    (("c", ">=1.0.0"),): {"c": _VERSION_2_0_0, "b": _VERSION_2_0_0, "a": _VERSION_2_0_0},
    (("a", ">=1.0.0"), ("b", ">=1.0.0")): {"a": _VERSION_2_0_0, "b": _VERSION_2_0_0},
    (("a", "==1.0.0"), ("b", "==1.0.0")): {"a": _VERSION_1_0_0, "b": _VERSION_1_0_0},
}


def dependency_signature(
    root_dependencies: Collection[PackageDependency],
) -> Tuple[Tuple[str, str], ...]:
    """Computes the canonical signature of a root dependency collection."""
    signature: List[Tuple[str, str]] = []
    for dependency in root_dependencies:
        signature.append((dependency.name, dependency.range_constraint.raw_text))
    return tuple(signature)


def expected_selection(
    root_dependencies: Collection[PackageDependency],
) -> Dict[str, Version]:
    """Computes the highest-precedence compatible version assignment for sampled inputs."""
    return dict(_RESOLUTIONS[dependency_signature(root_dependencies)])


def _selection_steps(selection: Mapping[str, Version]) -> Tuple[str, ...]:
    """Produces ordered derivation steps for a modeled resolution assignment."""
    steps: List[str] = []
    for name in selection:
        steps.append("selected " + name)
    return tuple(steps)


def expected_outcome(
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome:
    """Computes the modeled resolution outcome for sampled root dependencies."""
    selection = expected_selection(root_dependencies)
    return ResolutionOutcome(
        selected_versions=selection,
        derivation_steps=_selection_steps(selection),
    )


# ==============================================================================
# 2. State Machine Specifications (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class DependencySolverState:
    """Canonical model state tracking repository registrations and resolution outcomes."""
    packages: Dict[str, List[PackageRelease]] = field(default_factory=_initial_packages)
    register_count: int = 0
    resolution_count: int = 0
    last_selected: Dict[str, Version] = field(default_factory=dict)


class PackageRepositoryStateMachine(StateMachine[DependencySolverState]):
    """Pretense state machine modeling package registration and release lookup."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DependencySolverState:
        """Constructs the initial model state for an empty package repository."""
        return DependencySolverState()

    @transition.seeding
    def seed_repository(self) -> None:
        """Seeds the shared fixture repository state before generative fuzzing."""
        self.state.packages = _initial_packages()
        self.state.register_count = 0

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        """Registers a release, gating to known publication fixtures in fuzzing."""
        require_arg(
            release,
            Domain.sampled_from(_SAMPLE_RELEASES),
            preferred=[_RELEASE_A_1_0_0, _RELEASE_B_1_0_0],
        )
        ret = self.inner_register_package(release)
        self.state.register_count += 1
        self.state.packages.setdefault(release.name, []).append(release)
        assert release.name in self.state.packages
        return ret

    def inner_register_package(self, release: PackageRelease) -> None:
        """Registers a release into the fake repository state."""
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        """Looks up a package's releases, gating missing packages out of fuzzing."""
        require(bool(self.state.packages))
        require_arg(name, Domain.in_set(self.state.packages), error=PackageNotFoundError)
        ret = self.inner_get_releases(name)
        expected = _sorted_releases(self.state.packages[name])
        assert len(ret) == len(expected)
        for index in range(len(expected)):
            assert ret[index].name == expected[index].name
            assert ret[index].version.major == expected[index].version.major
            assert ret[index].version.minor == expected[index].version.minor
            assert ret[index].version.patch == expected[index].version.patch
        return ret

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        """Returns the fake repository's releases for a package in precedence order."""
        return _sorted_releases(self.state.packages[name])

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        """Reports package membership within the repository."""
        require_arg(
            name,
            Domain.sampled_from(_PACKAGE_NAME_CANDIDATES),
            preferred=["a", "missing"],
        )
        ret = self.inner_has_package(name)
        assert ret == (name in self.state.packages)
        return ret

    def inner_has_package(self, name: str) -> bool:
        """Reports fake repository package membership."""
        return name in self.state.packages

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        """Reports every registered package name."""
        ret = self.inner_all_packages()
        assert ret == set(self.state.packages.keys())
        return ret

    def inner_all_packages(self) -> Set[str]:
        """Returns the fake repository's package name set."""
        return set(self.state.packages.keys())


repository_proto = PackageRepositoryStateMachine()


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Pretense state machine modeling compatible dependency resolution."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DependencySolverState:
        """Constructs the initial model state for the dependency solver."""
        return DependencySolverState()

    @transition.seeding
    def seed_solver(self) -> None:
        """Seeds a blank solver state before generative fuzzing."""
        self.state.resolution_count = 0
        self.state.last_selected = {}

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Resolves root dependencies, gating unsupported/unsatisfiable fixtures out of fuzzing."""
        require_arg(
            root_dependencies,
            Domain.sampled_from(_SAMPLE_DEPENDENCY_SETS),
            preferred=[_DEPS_B_GE_1_0_0, _DEPS_C_GE_1_0_0],
            error=ResolutionConflictError,
        )
        ret = self.inner_resolve(root_dependencies)
        self.state.resolution_count += 1
        self.state.last_selected = dict(ret.selected_versions)
        expected = expected_selection(root_dependencies)
        assert dict(ret.selected_versions) == expected
        for name in expected:
            assert name in ret.selected_versions
            assert dict(ret.selected_versions)[name].major == expected[name].major
            assert dict(ret.selected_versions)[name].minor == expected[name].minor
            assert dict(ret.selected_versions)[name].patch == expected[name].patch
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Computes the fake resolution outcome for sampled root dependencies."""
        return expected_outcome(root_dependencies)


solver_proto = DependencySolverStateMachine()


# ==============================================================================
# 3. State Machine Protos & Fakes (Interface Components)
# ==============================================================================

FakePackageRepository = synthesize_fake(PackageRepositoryStateMachine)
FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_package_repository_fake(
    state: Optional[DependencySolverState] = None,
) -> PackageRepository:
    """Synthesizes a fake package repository for the interface state machine."""
    return FakePackageRepository(state=state or repository_proto.make_initial_state())


def make_dependency_solver_fake(
    state: Optional[DependencySolverState] = None,
) -> DependencySolver:
    """Synthesizes a fake dependency solver for the interface state machine."""
    return FakeDependencySolver(state=state or solver_proto.make_initial_state())


FakePackageRepositoryFuzzTest = compile_hypothesis_test_case(
    proto=repository_proto,
    initial_state_factory=repository_proto.make_initial_state,
    name="FakePackageRepositoryFuzzTest",
)

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=solver_proto,
    initial_state_factory=solver_proto.make_initial_state,
    name="FakeDependencySolverFuzzTest",
)


# ==============================================================================
# 4. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestPackageRepositoryFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all repository transitions."""

    def setUp(self) -> None:
        self.fake = make_package_repository_fake()
        self.sm = PackageRepositoryStateMachine(singletons={PackageRepository: self.fake})

    def test_register_and_query(self) -> None:
        """Exercises the seeding, registration, lookup, membership, and enumeration transitions."""
        self.sm.seed_repository()
        for release in _SAMPLE_RELEASES:
            self.sm.register_package(release)
        self.assertEqual(self.sm.all_packages(), {"a", "b", "c", "d"})
        self.assertTrue(self.sm.has_package("a"))
        self.assertFalse(self.sm.has_package("missing"))
        releases = self.sm.get_releases("b")
        self.assertEqual(len(releases), 6)
        self.assertEqual(releases[0].version.major, 2)
        self.assertEqual(releases[2].version.minor, 1)
        self.assertEqual(releases[5].version.minor, 0)

    def test_fake_register_and_query(self) -> None:
        """Exercises the same repository transitions directly on the synthesized fake."""
        for release in _SAMPLE_RELEASES:
            self.fake.register_package(release)
        self.assertEqual(self.fake.all_packages(), {"a", "b", "c", "d"})
        self.assertFalse(self.fake.has_package("missing"))
        fake_releases = self.fake.get_releases("c")
        self.assertEqual(len(fake_releases), 4)
        self.assertEqual(fake_releases[0].version.major, 2)


class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all solver transitions."""

    def setUp(self) -> None:
        self.fake = make_dependency_solver_fake()
        self.sm = DependencySolverStateMachine(singletons={DependencySolver: self.fake})

    def test_resolve(self) -> None:
        """Exercises the seeding and resolution transitions across sampled dependency sets."""
        self.sm.seed_solver()
        for root_dependencies in _SAMPLE_DEPENDENCY_SETS:
            outcome = self.sm.resolve(root_dependencies)
            self.assertEqual(dict(outcome.selected_versions), expected_selection(root_dependencies))

    def test_fake_resolve(self) -> None:
        """Exercises the resolution transition directly on the synthesized fake."""
        for root_dependencies in _SAMPLE_DEPENDENCY_SETS:
            fake_outcome = self.fake.resolve(root_dependencies)
            self.assertEqual(dict(fake_outcome.selected_versions), expected_selection(root_dependencies))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T16:14:00Z
# LAST_CHANGED: 2026-11-13T16:05:08Z
# CHANGE: Extend the shared fixture repository with package d prerelease releases (1.1.0-alpha, 2.0.0-alpha, 2.0.0) and update version precedence ranks, package name domains, seeding, and fake test expectations so downstream deterministic and fuzz coverage exercises prerelease ordering in release retrieval.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional, Tuple
import unittest

from pretense import (
    Env,
    StateMachine,
    require,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    fake,
    get_singleton,
    system,
)

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineStateMachine,
)


# ==============================================================================
# 0. Local Oracle Helpers (mirror the interface model's parsing/comparison)
# ==============================================================================


def _parse_expected(text: str) -> Version:
    """Computes the parsed version record modeled for a valid version string."""
    build: Tuple[str, ...] = ()
    if "+" in text:
        body, build_text = text.split("+", 1)
        build = tuple(build_text.split("."))
    else:
        body = text
    prerelease: Tuple[str, ...] = ()
    if "-" in body:
        body, prerelease_text = body.split("-", 1)
        prerelease = tuple(prerelease_text.split("."))
    numeric = body.split(".")
    return Version(
        major=int(numeric[0]),
        minor=int(numeric[1]),
        patch=int(numeric[2]),
        prerelease=prerelease,
        build=build,
    )


def _compare_identifiers_expected(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Compares dot-separated prerelease identifier sequences by SemVer 2.0 rules."""
    shared = min(len(left), len(right))
    for index in range(shared):
        left_part = left[index]
        right_part = right[index]
        if left_part == right_part:
            continue
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            left_number = int(left_part)
            right_number = int(right_part)
            if left_number < right_number:
                return -1
            if left_number > right_number:
                return 1
        elif left_numeric:
            return -1
        elif right_numeric:
            return 1
        elif left_part < right_part:
            return -1
        elif left_part > right_part:
            return 1
    if len(left) < len(right):
        return -1
    if len(left) > len(right):
        return 1
    return 0


def _compare_expected(left: Version, right: Version) -> int:
    """Computes the SemVer 2.0 precedence ordering of two version records."""
    left_numeric = (left.major, left.minor, left.patch)
    right_numeric = (right.major, right.minor, right.patch)
    if left_numeric < right_numeric:
        return -1
    if left_numeric > right_numeric:
        return 1
    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1
    return _compare_identifiers_expected(left.prerelease, right.prerelease)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class VersionEngineImplPseudoStateMachine(VersionEngineStateMachine):
    """Implementation pseudo-state machine binding the concrete VersionEngine singleton.

    Inherits every interface transition, precondition, argument domain, and model state
    mutation; only the inner transitions are overridden to drive the concrete SUT.
    """

    def inner_parse_version(self, text: str) -> Version:
        """Drives the concrete engine and verifies the parsed version record."""
        target: VersionEngine = sut(VersionEngine)
        ret = target.parse_version(text)
        expected = _parse_expected(text)
        assert ret.major == expected.major
        assert ret.minor == expected.minor
        assert ret.patch == expected.patch
        assert ret.prerelease == expected.prerelease
        assert ret.build == expected.build
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        """Drives the concrete engine and verifies tri-state precedence ordering."""
        target: VersionEngine = sut(VersionEngine)
        ret = target.compare_precedence(v1, v2)
        expected = _compare_expected(v1, v2)
        assert (ret < 0) == (expected < 0)
        assert (ret == 0) == (expected == 0)
        assert (ret > 0) == (expected > 0)
        return ret


proto = VersionEngineImplPseudoStateMachine()


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


def make_sut() -> VersionEngine:
    """Creates and activates a concrete VersionEngine singleton scope."""
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngine)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(VersionEngine)


VersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="VersionEngineFuzzTest",
)


# ==============================================================================
# 3. Fixed Real-Implementation Scenarios (Implementation Components)
# ==============================================================================


class TestVersionEngineImplReal(LifecycleTestCase):
    """Verifies the concrete version engine against deterministic scenarios."""

    target = VersionEngine

    def setUp(self) -> None:
        super().setUp()
        engine = get_singleton(VersionEngine)
        self.sm = VersionEngineImplPseudoStateMachine(singletons={VersionEngine: engine})
        self.checked = self.sm.as_checked(VersionEngine, engine)

    def test_parse_version(self) -> None:
        """Exercises parsing of prerelease and build metadata version strings."""
        self.checked.parse_version("1.2.3-rc.1+build.5")
        self.checked.parse_version("1.2.3-alpha.1")

    def test_compare_precedence(self) -> None:
        """Exercises numeric, prerelease, alphanumeric, length, and build-only comparisons."""
        self.checked.compare_precedence(
            Version(major=1, minor=2, patch=3),
            Version(major=2, minor=0, patch=0),
        )
        self.checked.compare_precedence(
            Version(major=10, minor=20, patch=30),
            Version(major=1, minor=2, patch=3),
        )
        self.checked.compare_precedence(
            Version(major=1, minor=2, patch=3),
            Version(major=1, minor=2, patch=3, prerelease=("alpha",)),
        )
        self.checked.compare_precedence(
            Version(major=1, minor=2, patch=3, prerelease=("alpha",)),
            Version(major=1, minor=2, patch=3),
        )
        self.checked.compare_precedence(
            Version(major=1, minor=2, patch=3, prerelease=("0", "3", "7")),
            Version(major=1, minor=2, patch=3, prerelease=("1",)),
        )
        self.checked.compare_precedence(
            Version(major=1, minor=2, patch=3, prerelease=("alpha", "1")),
            Version(major=1, minor=2, patch=3, prerelease=("alpha", "beta")),
        )
        self.checked.compare_precedence(
            Version(major=1, minor=2, patch=3, prerelease=("alpha",)),
            Version(major=1, minor=2, patch=3, prerelease=("alpha", "1")),
        )
        self.checked.compare_precedence(
            Version(major=1, minor=2, patch=3, prerelease=("alpha",)),
            Version(major=1, minor=2, patch=3, prerelease=("1",)),
        )
        self.checked.compare_precedence(
            Version(major=1, minor=2, patch=3, prerelease=("alpha",)),
            Version(major=1, minor=2, patch=3, prerelease=("alpha",)),
        )
        self.checked.compare_precedence(
            Version(major=1, minor=2, patch=3),
            Version(major=1, minor=2, patch=3, build=("build", "1")),
        )

    def test_invalid_version_violation(self) -> None:
        """Verifies leading-zero grammar violations surface InvalidVersionError."""
        self.checked.violating(InvalidVersionError).parse_version("01.2.3")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T16:11:08Z
# LAST_CHANGED: 2026-11-13T16:09:50Z
# CHANGE: Expand TestVersionEngineImplReal precedence scenarios: numeric core component pairs (1.2.3 vs 2.0.0, 10.20.30 vs 1.2.3), normal-versus-prerelease in both directions, alphanumeric-below-numeric (alpha vs 1), and identical prerelease sequence equality.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T16:11:08Z
# PRETENSE_QA_AUDIT: 2026-11-13T16:10:00Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
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
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
    VersionEngine,
)

# ==============================================================================
# 1. Model Helpers (pure data transformations shared by interface and impl)
# ==============================================================================


def _version(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> Version:
    """Constructs an immutable semantic version record for the model."""
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def _expected_version(text: str) -> Version:
    """Computes the semantic version record modeled by a valid version string."""
    build: Tuple[str, ...] = ()
    if "+" in text:
        body, build_text = text.split("+", 1)
        build = tuple(build_text.split("."))
    else:
        body = text
    prerelease: Tuple[str, ...] = ()
    if "-" in body:
        body, prerelease_text = body.split("-", 1)
        prerelease = tuple(prerelease_text.split("."))
    numeric = body.split(".")
    return Version(
        major=int(numeric[0]),
        minor=int(numeric[1]),
        patch=int(numeric[2]),
        prerelease=prerelease,
        build=build,
    )


def _compare_identifiers(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Compares dot-separated prerelease identifier sequences by SemVer 2.0 rules."""
    shared = min(len(left), len(right))
    for index in range(shared):
        left_part = left[index]
        right_part = right[index]
        if left_part == right_part:
            continue
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            left_number = int(left_part)
            right_number = int(right_part)
            if left_number < right_number:
                return -1
            if left_number > right_number:
                return 1
        elif left_numeric:
            return -1
        elif right_numeric:
            return 1
        elif left_part < right_part:
            return -1
        elif left_part > right_part:
            return 1
    if len(left) < len(right):
        return -1
    if len(left) > len(right):
        return 1
    return 0


def _compare_versions(left: Version, right: Version) -> int:
    """Computes the SemVer 2.0 precedence ordering of two version records."""
    left_numeric = (left.major, left.minor, left.patch)
    right_numeric = (right.major, right.minor, right.patch)
    if left_numeric < right_numeric:
        return -1
    if left_numeric > right_numeric:
        return 1
    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1
    return _compare_identifiers(left.prerelease, right.prerelease)


_VERSION_0_0_0 = _version(0, 0, 0)
_VERSION_0_9_9 = _version(0, 9, 9)
_VERSION_1_0_0 = _version(1, 0, 0)
_VERSION_1_2_3 = _version(1, 2, 3)
_VERSION_1_2_3_ALPHA = _version(1, 2, 3, ("alpha",))
_VERSION_1_2_3_ALPHA_1 = _version(1, 2, 3, ("alpha", "1"))
_VERSION_1_2_3_ALPHA_BETA = _version(1, 2, 3, ("alpha", "beta"))
_VERSION_1_2_3_0_3_7 = _version(1, 2, 3, ("0", "3", "7"))
_VERSION_1_2_3_ONE = _version(1, 2, 3, ("1",))
_VERSION_1_2_3_BETA = _version(1, 2, 3, ("beta",))
_VERSION_1_2_3_BUILD = _version(1, 2, 3, (), ("build", "1"))
_VERSION_1_2_3_RC_BUILD = _version(1, 2, 3, ("rc", "1"), ("build", "5"))
_VERSION_1_2_4 = _version(1, 2, 4)
_VERSION_1_3_0 = _version(1, 3, 0)
_VERSION_2_0_0 = _version(2, 0, 0)
_VERSION_2_0_0_ALPHA = _version(2, 0, 0, ("alpha",))
_VERSION_10_20_30 = _version(10, 20, 30)

_VALID_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "0.9.9",
    "1.0.0",
    "1.2.3",
    "1.2.3-alpha",
    "1.2.3-alpha.1",
    "1.2.3-alpha.beta",
    "1.2.3-0.3.7",
    "1.2.3+build.1",
    "1.2.3-rc.1+build.5",
    "2.0.0",
    "2.0.0-alpha",
    "10.20.30",
)

_SAMPLE_VERSIONS: Tuple[Version, ...] = (
    _VERSION_0_0_0,
    _VERSION_0_9_9,
    _VERSION_1_0_0,
    _VERSION_1_2_3,
    _VERSION_1_2_3_ALPHA,
    _VERSION_1_2_3_ALPHA_1,
    _VERSION_1_2_3_ALPHA_BETA,
    _VERSION_1_2_3_0_3_7,
    _VERSION_1_2_3_ONE,
    _VERSION_1_2_3_BETA,
    _VERSION_1_2_3_BUILD,
    _VERSION_1_2_3_RC_BUILD,
    _VERSION_1_2_4,
    _VERSION_1_3_0,
    _VERSION_2_0_0,
    _VERSION_2_0_0_ALPHA,
    _VERSION_10_20_30,
)


# ==============================================================================
# 2. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class VersionEngineState:
    """Canonical model state tracking parsed versions and comparison outcomes."""
    parse_count: int = 0
    last_version: Optional[Version] = None
    comparison_count: int = 0
    last_comparison: int = 0


class VersionEngineStateMachine(StateMachine[VersionEngineState]):
    """Pretense state machine modeling SemVer parsing and precedence comparison."""

    def __init__(
        self,
        state: Optional[VersionEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> VersionEngineState:
        """Constructs the initial model state for a blank version engine."""
        return VersionEngineState()

    @transition.seeding
    def seed_engine(self) -> None:
        """Seeds a blank version engine state before generative fuzzing."""
        self.state.parse_count = 0
        self.state.last_version = None
        self.state.comparison_count = 0
        self.state.last_comparison = 0

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        """Parses text into a version record, gating invalid grammar out of fuzzing."""
        require_arg(
            text,
            Domain.sampled_from(_VALID_VERSION_TEXTS),
            preferred=["1.2.3", "1.2.3-alpha.1", "1.2.3-rc.1+build.5"],
            error=InvalidVersionError,
        )
        ret = self.inner_parse_version(text)
        self.state.parse_count += 1
        self.state.last_version = ret
        expected = _expected_version(text)
        assert ret.major == expected.major
        assert ret.minor == expected.minor
        assert ret.patch == expected.patch
        assert ret.prerelease == expected.prerelease
        assert ret.build == expected.build
        return ret

    def inner_parse_version(self, text: str) -> Version:
        """Computes the fake parse result for a valid version string."""
        return _expected_version(text)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Compares two version records by SemVer 2.0 precedence."""
        require_arg(v1, Domain.sampled_from(_SAMPLE_VERSIONS), preferred=[_VERSION_1_2_3])
        require_arg(v2, Domain.sampled_from(_SAMPLE_VERSIONS), preferred=[_VERSION_1_2_4])
        ret = self.inner_compare_precedence(v1, v2)
        self.state.comparison_count += 1
        self.state.last_comparison = ret
        assert ret == _compare_versions(v1, v2)
        if v1.major < v2.major:
            assert ret < 0
        if v1.major > v2.major:
            assert ret > 0
        if (
            v1.major == v2.major
            and v1.minor == v2.minor
            and v1.patch == v2.patch
            and v1.prerelease == v2.prerelease
        ):
            assert ret == 0
        if (
            v1.major == v2.major
            and v1.minor == v2.minor
            and v1.patch == v2.patch
            and not v1.prerelease
            and bool(v2.prerelease)
        ):
            assert ret > 0
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        """Computes the fake precedence comparison result."""
        return _compare_versions(v1, v2)


proto = VersionEngineStateMachine()


# ==============================================================================
# 3. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeVersionEngine = synthesize_fake(VersionEngineStateMachine)


def make_version_engine_fake(
    state: Optional[VersionEngineState] = None,
) -> VersionEngine:
    """Synthesizes a fake version engine for the interface state machine."""
    return FakeVersionEngine(state=state or proto.make_initial_state())


FakeVersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeVersionEngineFuzzTest",
)


# ==============================================================================
# 4. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestVersionEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_version_engine_fake()
        self.sm = VersionEngineStateMachine(singletons={VersionEngine: self.fake})

    def test_parse_version(self) -> None:
        """Exercises the seeding and parse transitions, including prerelease and build data."""
        self.sm.seed_engine()
        parsed = self.sm.parse_version("1.2.3-rc.1+build.5")
        self.assertEqual(parsed.major, 1)
        self.assertEqual(parsed.minor, 2)
        self.assertEqual(parsed.patch, 3)
        self.assertEqual(parsed.prerelease, ("rc", "1"))
        self.assertEqual(parsed.build, ("build", "5"))
        self.assertEqual(_expected_version("1.2.3-rc.1+build.5").build, ("build", "5"))
        fake_parsed = self.fake.parse_version("1.2.3-rc.1+build.5")
        self.assertEqual(fake_parsed.major, 1)
        self.assertEqual(fake_parsed.prerelease, ("rc", "1"))
        plain = self.fake.parse_version("2.0.0")
        self.assertEqual(plain.prerelease, ())
        self.assertEqual(plain.build, ())

    def test_compare_precedence(self) -> None:
        """Exercises the precedence transition across numeric, prerelease, and build orderings."""
        self.sm.seed_engine()
        self.assertLess(self.sm.compare_precedence(_VERSION_1_2_3, _VERSION_1_2_4), 0)
        self.assertGreater(self.sm.compare_precedence(_VERSION_1_2_4, _VERSION_1_2_3), 0)
        self.assertEqual(self.sm.compare_precedence(_VERSION_1_2_3, _VERSION_1_2_3_BUILD), 0)
        self.assertEqual(self.sm.compare_precedence(_VERSION_1_2_3_RC_BUILD, _VERSION_1_2_3_RC_BUILD), 0)
        self.assertLess(self.fake.compare_precedence(_VERSION_1_2_3_ALPHA, _VERSION_1_2_3), 0)
        self.assertGreater(self.fake.compare_precedence(_VERSION_1_2_3, _VERSION_1_2_3_ALPHA), 0)
        self.assertEqual(self.fake.compare_precedence(_VERSION_1_2_3, _VERSION_1_2_3), 0)

    def test_prerelease_identifier_ordering(self) -> None:
        """Exercises numeric, alphanumeric, and sequence-length prerelease ordering rules."""
        self.sm.seed_engine()
        self.assertLess(self.sm.compare_precedence(_VERSION_1_2_3_0_3_7, _VERSION_1_2_3_ONE), 0)
        self.assertGreater(self.sm.compare_precedence(_VERSION_1_2_3_ONE, _VERSION_1_2_3_0_3_7), 0)
        self.assertLess(self.sm.compare_precedence(_VERSION_1_2_3_ALPHA_1, _VERSION_1_2_3_ALPHA_BETA), 0)
        self.assertGreater(self.sm.compare_precedence(_VERSION_1_2_3_ALPHA_BETA, _VERSION_1_2_3_ALPHA_1), 0)
        self.assertLess(self.sm.compare_precedence(_VERSION_1_2_3_ALPHA, _VERSION_1_2_3_BETA), 0)
        self.assertGreater(self.sm.compare_precedence(_VERSION_1_2_3_BETA, _VERSION_1_2_3_ALPHA), 0)
        self.assertLess(self.sm.compare_precedence(_VERSION_1_2_3_ALPHA, _VERSION_1_2_3_ALPHA_1), 0)
        self.assertGreater(self.sm.compare_precedence(_VERSION_1_2_3_ALPHA_1, _VERSION_1_2_3_ALPHA), 0)
        self.assertEqual(self.sm.compare_precedence(_VERSION_1_2_3_ALPHA, _VERSION_1_2_3_ALPHA), 0)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T15:57:30Z
# LAST_CHANGED: 2026-11-13T15:57:30Z
# CHANGE: Author SemVer core interface state machine: VersionEngineState/VersionEngineStateMachine with 1:1 parse_version and compare_precedence transitions, domain-gated InvalidVersionError preconditions, synthesized fake, fixed fake tests, and fake fuzz test.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    Env,
    StateMachine,
    require,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    fake,
    get_singleton,
    system,
)

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import Version
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    VersionRange,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineStateMachine,
    model_satisfies,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class RangeEngineImplPseudoStateMachine(RangeEngineStateMachine):
    """Implementation pseudo-state machine binding the concrete RangeEngine singleton.

    Inherits every interface transition, precondition, argument domain, and model state
    mutation; only the inner transitions are overridden to drive the concrete SUT.
    """

    def inner_parse_range(self, text: str) -> VersionRange:
        """Drives the concrete engine and verifies the trimmed range record."""
        target: RangeEngine = sut(RangeEngine)
        ret = target.parse_range(text)
        assert ret.raw_text == text.strip()
        assert ret.raw_text != ""
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Drives the concrete engine and verifies satisfaction against the model."""
        target: RangeEngine = sut(RangeEngine)
        ret = target.satisfies(version, range_constraint, include_prerelease)
        assert ret == model_satisfies(version, range_constraint, include_prerelease)
        return ret


proto = RangeEngineImplPseudoStateMachine()


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


def make_sut() -> RangeEngine:
    """Creates and activates concrete RangeEngine and VersionEngine singletons."""
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngine)
    registry.register_singleton(RangeEngine)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RangeEngine)


RangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="RangeEngineFuzzTest",
)


# ==============================================================================
# 3. Fixed Real-Implementation Scenarios (Implementation Components)
# ==============================================================================


class TestRangeEngineImplReal(LifecycleTestCase):
    """Verifies the concrete range engine against deterministic scenarios."""

    target = RangeEngine

    def setUp(self) -> None:
        super().setUp()
        engine = get_singleton(RangeEngine)
        self.sm = RangeEngineImplPseudoStateMachine(singletons={RangeEngine: engine})
        self.checked = self.sm.as_checked(RangeEngine, engine)

    def test_parse_range(self) -> None:
        """Exercises comparator, caret, tilde, wildcard, and hyphen range parsing."""
        for text in (
            "1.x",
            ">=1.0.0",
            ">= 1.0.0",
            "1.0.0 - 2.x",
            "1.0.0 - 2.0.0",
            "1.0.0 - *",
            "1.x || >=3.0.0",
            "^1.2.3",
            "~1.2.3",
            "^0.x",
            "^1.2.x",
            "^0.2.x",
            "^0.0.x",
            "^0.2.3",
            "^0.0.3",
            "~1.x",
            "!=1.x",
            ">=*",
            ">=1.0.0 <2.0.0",
            "==1.2.3-alpha",
            ">=1.2.3-0.3.7",
            ">=1.x",
            "<1.x",
            "<=1.x",
            ">1.x",
            "*",
            "<*",
            ">*",
            "!=*",
        ):
            self.checked.parse_range(text)

    def test_caret_and_tilde_boundaries(self) -> None:
        """Exercises caret and tilde zero-major boundary expansion."""
        self.checked.satisfies(
            Version(major=0, minor=0, patch=0),
            VersionRange(raw_text="^0.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=9, patch=9),
            VersionRange(raw_text="^0.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=0, patch=0),
            VersionRange(raw_text="^0.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=0),
            VersionRange(raw_text="^1.2.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=9, patch=9),
            VersionRange(raw_text="^1.2.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=2, minor=0, patch=0),
            VersionRange(raw_text="^1.2.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=2, patch=0),
            VersionRange(raw_text="^0.2.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=3, patch=0),
            VersionRange(raw_text="^0.2.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=0, patch=1),
            VersionRange(raw_text="^0.0.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=1, patch=0),
            VersionRange(raw_text="^0.0.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=2, patch=3),
            VersionRange(raw_text="^0.2.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=2, patch=0),
            VersionRange(raw_text="^0.2.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=3, patch=0),
            VersionRange(raw_text="^0.2.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=0, patch=0),
            VersionRange(raw_text="~1.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=2, minor=0, patch=0),
            VersionRange(raw_text="~1.x"),
            False,
        )

    def test_wildcard_and_open_hyphen(self) -> None:
        """Exercises wildcard-only bounds and open hyphen expansion."""
        self.checked.satisfies(
            Version(major=0, minor=9, patch=9),
            VersionRange(raw_text="*"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=9, patch=9),
            VersionRange(raw_text=">=*"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=9, patch=9),
            VersionRange(raw_text="1.0.0 - *"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=0, patch=0),
            VersionRange(raw_text="1.0.0 - *"),
            False,
        )
        self.checked.satisfies(
            Version(major=3, minor=0, patch=0),
            VersionRange(raw_text="1.0.0 - *"),
            False,
        )

    def test_prerelease_filtering(self) -> None:
        """Exercises prerelease filtering for both include_prerelease settings."""
        candidate = Version(major=1, minor=2, patch=3, prerelease=("alpha",))
        self.checked.satisfies(candidate, VersionRange(raw_text=">=1.0.0"), True)
        self.checked.satisfies(candidate, VersionRange(raw_text=">=1.0.0"), False)
        self.checked.satisfies(candidate, VersionRange(raw_text="==1.2.3-alpha"), False)
        self.checked.satisfies(candidate, VersionRange(raw_text=">=1.2.3-alpha"), False)

    def test_prerelease_identifier_ordering(self) -> None:
        """Exercises numeric, alphanumeric, and sequence-length prerelease ordering."""
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3, prerelease=("0", "3", "7")),
            VersionRange(raw_text=">=1.2.3-0.3.7"),
            True,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3, prerelease=("1",)),
            VersionRange(raw_text=">=1.2.3-0.3.7"),
            True,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3, prerelease=("alpha",)),
            VersionRange(raw_text=">=1.2.3-0.3.7"),
            True,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3, prerelease=("0", "3", "7")),
            VersionRange(raw_text=">=1.2.3-alpha"),
            True,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3, prerelease=("alpha", "1")),
            VersionRange(raw_text=">=1.2.3-alpha"),
            True,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3, prerelease=("beta",)),
            VersionRange(raw_text=">=1.2.3-alpha"),
            True,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3),
            VersionRange(raw_text=">=1.2.3-alpha"),
            True,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3, prerelease=("alpha",)),
            VersionRange(raw_text="==1.2.3"),
            True,
        )

    def test_partial_major_wildcard_comparators(self) -> None:
        """Exercises partial-major wildcard comparator satisfaction families."""
        self.checked.satisfies(
            Version(major=0, minor=9, patch=9),
            VersionRange(raw_text="<1.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=0, patch=0),
            VersionRange(raw_text="<1.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=9, patch=9),
            VersionRange(raw_text="<=1.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=2, minor=0, patch=0),
            VersionRange(raw_text="<=1.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=9, patch=9),
            VersionRange(raw_text=">1.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=2, minor=0, patch=0),
            VersionRange(raw_text=">1.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=9, patch=9),
            VersionRange(raw_text=">=1.x"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=0, patch=0),
            VersionRange(raw_text=">=1.x"),
            False,
        )

    def test_full_version_comparators(self) -> None:
        """Exercises full-version comparator satisfaction families."""
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3),
            VersionRange(raw_text="!=1.2.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=4),
            VersionRange(raw_text="!=1.2.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3),
            VersionRange(raw_text="<=1.2.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=4),
            VersionRange(raw_text="<=1.2.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=3),
            VersionRange(raw_text=">1.2.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=2, patch=4),
            VersionRange(raw_text=">1.2.3"),
            False,
        )

    def test_full_version_hyphen_bound(self) -> None:
        """Exercises a hyphen range with a full-version upper bound."""
        self.checked.satisfies(
            Version(major=0, minor=9, patch=9),
            VersionRange(raw_text="1.0.0 - 2.0.0"),
            False,
        )
        self.checked.satisfies(
            Version(major=1, minor=0, patch=0),
            VersionRange(raw_text="1.0.0 - 2.0.0"),
            False,
        )
        self.checked.satisfies(
            Version(major=2, minor=0, patch=0),
            VersionRange(raw_text="1.0.0 - 2.0.0"),
            False,
        )
        self.checked.satisfies(
            Version(major=2, minor=5, patch=0),
            VersionRange(raw_text="1.0.0 - 2.0.0"),
            False,
        )

    def test_caret_zero_zero_patch_boundary(self) -> None:
        """Exercises the zero-major zero-minor caret patch boundary."""
        self.checked.satisfies(
            Version(major=0, minor=0, patch=1),
            VersionRange(raw_text="^0.0.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=0, patch=3),
            VersionRange(raw_text="^0.0.3"),
            False,
        )
        self.checked.satisfies(
            Version(major=0, minor=0, patch=4),
            VersionRange(raw_text="^0.0.3"),
            False,
        )

    def test_empty_range_violation(self) -> None:
        """Verifies an empty range expression surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("")

    def test_comma_range_violation(self) -> None:
        """Verifies comma-delimited comparators surface InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("1.0.0,2.0.0")

    def test_empty_union_violation(self) -> None:
        """Verifies an empty union clause surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("1.x || ")

    def test_missing_bound_violation(self) -> None:
        """Verifies a hyphen range missing its upper bound surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 - ")

    def test_bare_partial_major_violation(self) -> None:
        """Verifies a bare partial major version surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("1")

    def test_bare_partial_minor_violation(self) -> None:
        """Verifies a bare partial minor version surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("1.2")

    def test_bare_partial_comparator_violation(self) -> None:
        """Verifies a bare partial comparator target surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range(">1.2")

    def test_bare_partial_caret_violation(self) -> None:
        """Verifies a bare partial caret target surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("^0.0")

    def test_bare_partial_hyphen_violation(self) -> None:
        """Verifies a bare partial hyphen bound surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("1.2 - 2.3")

    def test_trailing_operator_violation(self) -> None:
        """Verifies a trailing relational operator surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range(">=")

    def test_malformed_wildcard_patch_violation(self) -> None:
        """Verifies a wildcard following a full patch component surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("1.2.3.x")

    def test_malformed_wildcard_minor_trailing_violation(self) -> None:
        """Verifies a component after a wildcard minor surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("1.x.2")

    def test_leading_zero_wildcard_violation(self) -> None:
        """Verifies a leading-zero wildcard major surfaces InvalidRangeError."""
        self.checked.violating(InvalidRangeError).parse_range("01.x")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T16:16:57Z
# LAST_CHANGED: 2026-11-13T16:13:13Z
# CHANGE: Add TestRangeEngineImplReal scenarios for prerelease identifier ordering (numeric vs numeric, numeric vs string, string vs numeric, differing identifiers/lengths, normal vs prerelease both ways), partial-major wildcard comparators (<1.x, <=1.x, >1.x, >=1.x), full-version comparators (!=1.2.3, <=1.2.3, >1.2.3), full-version hyphen bound (1.0.0 - 2.0.0), zero-major zero-minor caret boundary (^0.0.3), spaced operator form (>= 1.0.0), and terminal InvalidRangeError violations for trailing operator and malformed wildcard bounds (1.2.3.x, 1.x.2, 01.x).
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T16:16:57Z
# PRETENSE_QA_AUDIT: 2026-11-13T16:16:36Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
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
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import (
    SemVerError,
    Version,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)


# ==============================================================================
# 1. Model Helpers (table-driven SemVer range algebra over sampled domains)
# ==============================================================================


def _version(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> Version:
    """Constructs an immutable semantic version record for the model."""
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def _range(raw_text: str) -> VersionRange:
    """Constructs an immutable version range record for the model."""
    return VersionRange(raw_text=raw_text)


_VERSION_0_0_0 = _version(0, 0, 0)
_VERSION_0_0_1 = _version(0, 0, 1)
_VERSION_0_0_3 = _version(0, 0, 3)
_VERSION_0_0_4 = _version(0, 0, 4)
_VERSION_0_1_0 = _version(0, 1, 0)
_VERSION_0_2_0 = _version(0, 2, 0)
_VERSION_0_2_3 = _version(0, 2, 3)
_VERSION_0_3_0 = _version(0, 3, 0)
_VERSION_0_9_9 = _version(0, 9, 9)
_VERSION_1_0_0 = _version(1, 0, 0)
_VERSION_1_2_0 = _version(1, 2, 0)
_VERSION_1_2_3_0_3_7 = _version(1, 2, 3, ("0", "3", "7"))
_VERSION_1_2_3_1 = _version(1, 2, 3, ("1",))
_VERSION_1_2_3_ALPHA = _version(1, 2, 3, ("alpha",))
_VERSION_1_2_3_ALPHA_1 = _version(1, 2, 3, ("alpha", "1"))
_VERSION_1_2_3_ALPHA_BETA = _version(1, 2, 3, ("alpha", "beta"))
_VERSION_1_2_3_BETA = _version(1, 2, 3, ("beta",))
_VERSION_1_2_3 = _version(1, 2, 3)
_VERSION_1_2_3_BUILD = _version(1, 2, 3, (), ("build", "1"))
_VERSION_1_2_4 = _version(1, 2, 4)
_VERSION_1_3_0 = _version(1, 3, 0)
_VERSION_1_9_9 = _version(1, 9, 9)
_VERSION_2_0_0_ALPHA = _version(2, 0, 0, ("alpha",))
_VERSION_2_0_0 = _version(2, 0, 0)
_VERSION_2_5_0 = _version(2, 5, 0)
_VERSION_3_0_0 = _version(3, 0, 0)

# Total precedence rank over the sampled version domain (SemVer 2.0 ordering).
_VERSION_RANK: Dict[Version, int] = {
    _VERSION_0_0_0: 0,
    _VERSION_0_0_1: 1,
    _VERSION_0_0_3: 2,
    _VERSION_0_0_4: 3,
    _VERSION_0_1_0: 4,
    _VERSION_0_2_0: 5,
    _VERSION_0_2_3: 6,
    _VERSION_0_3_0: 7,
    _VERSION_0_9_9: 8,
    _VERSION_1_0_0: 9,
    _VERSION_1_2_0: 10,
    _VERSION_1_2_3_0_3_7: 11,
    _VERSION_1_2_3_1: 12,
    _VERSION_1_2_3_ALPHA: 13,
    _VERSION_1_2_3_ALPHA_1: 14,
    _VERSION_1_2_3_ALPHA_BETA: 15,
    _VERSION_1_2_3_BETA: 16,
    _VERSION_1_2_3: 17,
    _VERSION_1_2_3_BUILD: 17,
    _VERSION_1_2_4: 18,
    _VERSION_1_3_0: 19,
    _VERSION_1_9_9: 20,
    _VERSION_2_0_0_ALPHA: 21,
    _VERSION_2_0_0: 22,
    _VERSION_2_5_0: 23,
    _VERSION_3_0_0: 24,
}

_SAMPLE_VERSIONS: Tuple[Version, ...] = (
    _VERSION_0_0_0,
    _VERSION_0_0_1,
    _VERSION_0_0_3,
    _VERSION_0_0_4,
    _VERSION_0_1_0,
    _VERSION_0_2_0,
    _VERSION_0_2_3,
    _VERSION_0_3_0,
    _VERSION_0_9_9,
    _VERSION_1_0_0,
    _VERSION_1_2_0,
    _VERSION_1_2_3_0_3_7,
    _VERSION_1_2_3_1,
    _VERSION_1_2_3_ALPHA,
    _VERSION_1_2_3_ALPHA_1,
    _VERSION_1_2_3_ALPHA_BETA,
    _VERSION_1_2_3_BETA,
    _VERSION_1_2_3,
    _VERSION_1_2_3_BUILD,
    _VERSION_1_2_4,
    _VERSION_1_3_0,
    _VERSION_1_9_9,
    _VERSION_2_0_0_ALPHA,
    _VERSION_2_0_0,
    _VERSION_2_5_0,
    _VERSION_3_0_0,
)

_RANGE_GE_1_0_0 = _range(">=1.0.0")
_RANGE_GT_1_2_3 = _range(">1.2.3")
_RANGE_LE_1_2_3 = _range("<=1.2.3")
_RANGE_LT_2_0_0 = _range("<2.0.0")
_RANGE_EQ_1_2_3 = _range("==1.2.3")
_RANGE_NE_1_2_3 = _range("!=1.2.3")
_RANGE_CARET_1_2_3 = _range("^1.2.3")
_RANGE_TILDE_1_2_3 = _range("~1.2.3")
_RANGE_GE_1X = _range(">=1.x")
_RANGE_NE_1X = _range("!=1.x")
_RANGE_CARET_1X = _range("^1.x")
_RANGE_TILDE_1X = _range("~1.x")
_RANGE_HYPHEN_1_0_0_2X = _range("1.0.0 - 2.x")
_RANGE_CONJUNCTION = _range(">=1.0.0 <2.0.0")
_RANGE_UNION = _range("1.x || >=3.0.0")
_RANGE_ANY = _range("*")
_RANGE_GE_ANY = _range(">=*")
_RANGE_EQ_1_2_3_ALPHA = _range("==1.2.3-alpha")
_RANGE_GE_1_2_3_ALPHA = _range(">=1.2.3-alpha")
_RANGE_SPACED = _range(">= 1.0.0")
_RANGE_CARET_0X = _range("^0.x")
_RANGE_CARET_1_2X = _range("^1.2.x")
_RANGE_CARET_0_2X = _range("^0.2.x")
_RANGE_CARET_0_0X = _range("^0.0.x")
_RANGE_CARET_0_2_3 = _range("^0.2.3")
_RANGE_HYPHEN_OPEN = _range("1.0.0 - *")
_RANGE_LT_1X = _range("<1.x")
_RANGE_LE_1X = _range("<=1.x")
_RANGE_GT_1X = _range(">1.x")
_RANGE_HYPHEN_1_0_0_2_0_0 = _range("1.0.0 - 2.0.0")
_RANGE_CARET_0_0_3 = _range("^0.0.3")
_RANGE_GE_1_2_3_0_3_7 = _range(">=1.2.3-0.3.7")

_SAMPLE_RANGES: Tuple[VersionRange, ...] = (
    _RANGE_GE_1_0_0,
    _RANGE_GT_1_2_3,
    _RANGE_LE_1_2_3,
    _RANGE_LT_2_0_0,
    _RANGE_EQ_1_2_3,
    _RANGE_NE_1_2_3,
    _RANGE_CARET_1_2_3,
    _RANGE_TILDE_1_2_3,
    _RANGE_GE_1X,
    _RANGE_NE_1X,
    _RANGE_CARET_1X,
    _RANGE_TILDE_1X,
    _RANGE_HYPHEN_1_0_0_2X,
    _RANGE_CONJUNCTION,
    _RANGE_UNION,
    _RANGE_ANY,
    _RANGE_GE_ANY,
    _RANGE_EQ_1_2_3_ALPHA,
    _RANGE_GE_1_2_3_ALPHA,
    _RANGE_SPACED,
    _RANGE_CARET_0X,
    _RANGE_CARET_1_2X,
    _RANGE_CARET_0_2X,
    _RANGE_CARET_0_0X,
    _RANGE_CARET_0_2_3,
    _RANGE_HYPHEN_OPEN,
    _RANGE_LT_1X,
    _RANGE_LE_1X,
    _RANGE_GT_1X,
    _RANGE_HYPHEN_1_0_0_2_0_0,
    _RANGE_CARET_0_0_3,
    _RANGE_GE_1_2_3_0_3_7,
)

_VALID_RANGE_TEXTS: Tuple[str, ...] = (
    "1.x",
    ">=1.0.0",
    ">= 1.0.0",
    "  >=1.0.0  ",
    "1.0.0 - 2.x",
    "1.0.0 - *",
    "1.0.0 - 2.0.0",
    "1.x || >=3.0.0",
    "^1.2.3",
    "~1.2.3",
    "^0.x",
    "^1.2.x",
    "^0.2.x",
    "^0.0.x",
    "^0.2.3",
    "^0.0.3",
    "~1.x",
    "!=1.x",
    ">=*",
    ">=1.0.0 <2.0.0",
    "==1.2.3-alpha",
    ">=1.2.3-0.3.7",
    ">=1.x",
    "<1.x",
    "<=1.x",
    ">1.x",
    "*",
    "<*",
    ">*",
    "!=*",
)

_Comparator = Tuple[str, Version]
_Clause = Tuple[_Comparator, ...]

# Disjunctive normal form comparator sets for each sampled range expression.
_RANGE_CLAUSES: Dict[str, Tuple[_Clause, ...]] = {
    ">=1.0.0": (((">=", _VERSION_1_0_0),),),
    ">1.2.3": (((">", _VERSION_1_2_3),),),
    "<=1.2.3": ((("<=", _VERSION_1_2_3),),),
    "<2.0.0": ((("<", _VERSION_2_0_0),),),
    "==1.2.3": ((("==", _VERSION_1_2_3),),),
    "!=1.2.3": ((("!=", _VERSION_1_2_3),),),
    "^1.2.3": (((">=", _VERSION_1_2_3), ("<", _VERSION_2_0_0)),),
    "~1.2.3": (((">=", _VERSION_1_2_3), ("<", _VERSION_1_3_0)),),
    ">=1.x": (((">=", _VERSION_1_0_0),),),
    "!=1.x": ((("<", _VERSION_1_0_0),), ((">=", _VERSION_2_0_0),)),
    "^1.x": (((">=", _VERSION_1_0_0), ("<", _VERSION_2_0_0)),),
    "~1.x": (((">=", _VERSION_1_0_0), ("<", _VERSION_2_0_0)),),
    "1.0.0 - 2.x": (((">=", _VERSION_1_0_0), ("<", _VERSION_3_0_0)),),
    ">=1.0.0 <2.0.0": (((">=", _VERSION_1_0_0), ("<", _VERSION_2_0_0)),),
    "1.x || >=3.0.0": (
        ((">=", _VERSION_1_0_0), ("<", _VERSION_2_0_0)),
        ((">=", _VERSION_3_0_0),),
    ),
    "*": ((),),
    ">=*": ((),),
    "==1.2.3-alpha": ((("==", _VERSION_1_2_3_ALPHA),),),
    ">=1.2.3-alpha": (((">=", _VERSION_1_2_3_ALPHA),),),
    ">= 1.0.0": (((">=", _VERSION_1_0_0),),),
    "^0.x": (((">=", _VERSION_0_0_0), ("<", _VERSION_1_0_0)),),
    "^1.2.x": (((">=", _VERSION_1_2_0), ("<", _VERSION_2_0_0)),),
    "^0.2.x": (((">=", _VERSION_0_2_0), ("<", _VERSION_0_3_0)),),
    "^0.0.x": (((">=", _VERSION_0_0_0), ("<", _VERSION_0_1_0)),),
    "^0.2.3": (((">=", _VERSION_0_2_3), ("<", _VERSION_0_3_0)),),
    "1.0.0 - *": (((">=", _VERSION_1_0_0),),),
    "<1.x": ((("<", _VERSION_1_0_0),),),
    "<=1.x": ((("<", _VERSION_2_0_0),),),
    ">1.x": (((">=", _VERSION_2_0_0),),),
    "1.0.0 - 2.0.0": (((">=", _VERSION_1_0_0), ("<=", _VERSION_2_0_0)),),
    "^0.0.3": (((">=", _VERSION_0_0_3), ("<", _VERSION_0_0_4)),),
    ">=1.2.3-0.3.7": (((">=", _VERSION_1_2_3_0_3_7),),),
}


def _compare_versions(left: Version, right: Version) -> int:
    """Computes the modeled precedence ordering of two sampled version records."""
    left_rank = _VERSION_RANK[left]
    right_rank = _VERSION_RANK[right]
    if left_rank < right_rank:
        return -1
    if left_rank > right_rank:
        return 1
    return 0


def _clause_matches(version: Version, clause: _Clause) -> bool:
    """Evaluates whether a version satisfies every comparator within one clause."""
    matched = True
    for op, bound in clause:
        if op == "==":
            matched = matched and _compare_versions(version, bound) == 0
        elif op == "!=":
            matched = matched and _compare_versions(version, bound) != 0
        elif op == ">=":
            matched = matched and _compare_versions(version, bound) >= 0
        elif op == ">":
            matched = matched and _compare_versions(version, bound) > 0
        elif op == "<=":
            matched = matched and _compare_versions(version, bound) <= 0
        elif op == "<":
            matched = matched and _compare_versions(version, bound) < 0
    return matched


def _targets_prerelease(version: Version, clause: _Clause) -> bool:
    """Detects an explicit same major/minor/patch prerelease comparator boundary."""
    targeted = False
    for _op, bound in clause:
        if (
            bound.prerelease
            and bound.major == version.major
            and bound.minor == version.minor
            and bound.patch == version.patch
        ):
            targeted = True
    return targeted


def model_satisfies(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    """Computes the modeled satisfaction result for a sampled version and range."""
    clauses = _RANGE_CLAUSES[range_constraint.raw_text]
    matched = False
    targeted = False
    for clause in clauses:
        if _clause_matches(version, clause):
            matched = True
        if _targets_prerelease(version, clause):
            targeted = True
    if version.prerelease and not include_prerelease and not targeted:
        return False
    return matched


# ==============================================================================
# 2. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class RangeEngineState:
    """Canonical model state tracking parsed ranges and satisfaction outcomes."""
    parse_count: int = 0
    last_range: Optional[VersionRange] = None
    satisfy_count: int = 0
    last_result: bool = False


class RangeEngineStateMachine(StateMachine[RangeEngineState]):
    """Pretense state machine modeling range parsing and constraint matching."""

    def __init__(
        self,
        state: Optional[RangeEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> RangeEngineState:
        """Constructs the initial model state for a blank range engine."""
        return RangeEngineState()

    @transition.seeding
    def seed_engine(self) -> None:
        """Seeds a blank range engine state before generative fuzzing."""
        self.state.parse_count = 0
        self.state.last_range = None
        self.state.satisfy_count = 0
        self.state.last_result = False

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        """Parses a range expression, gating malformed syntax out of fuzzing."""
        require_arg(
            text,
            Domain.sampled_from(_VALID_RANGE_TEXTS),
            preferred=["1.x", ">=1.0.0", "1.0.0 - 2.x"],
            error=InvalidRangeError,
        )
        ret = self.inner_parse_range(text)
        self.state.parse_count += 1
        self.state.last_range = ret
        assert ret.raw_text == text.strip()
        assert ret.raw_text != ""
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        """Computes the fake parse result for a valid range expression."""
        return _range(text.strip())

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates constraint satisfaction, gating to modeled version/range domains."""
        require_arg(version, Domain.sampled_from(_SAMPLE_VERSIONS), preferred=[_VERSION_1_2_3])
        require_arg(
            range_constraint,
            Domain.sampled_from(_SAMPLE_RANGES),
            preferred=[_RANGE_GE_1_0_0, _RANGE_CARET_1_2_3],
        )
        require_arg(include_prerelease, Domain.sampled_from([True, False]), preferred=[False])
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        self.state.satisfy_count += 1
        self.state.last_result = ret
        assert ret == model_satisfies(version, range_constraint, include_prerelease)
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Computes the fake satisfaction result for a sampled version and range."""
        return model_satisfies(version, range_constraint, include_prerelease)


proto = RangeEngineStateMachine()


# ==============================================================================
# 3. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeRangeEngine = synthesize_fake(RangeEngineStateMachine)


def make_range_engine_fake(state: Optional[RangeEngineState] = None) -> RangeEngine:
    """Synthesizes a fake range engine for the interface state machine."""
    return FakeRangeEngine(state=state or proto.make_initial_state())


FakeRangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRangeEngineFuzzTest",
)


# ==============================================================================
# 4. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestRangeEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_range_engine_fake()
        self.sm = RangeEngineStateMachine(singletons={RangeEngine: self.fake})

    def test_parse_range(self) -> None:
        """Exercises the seeding and parse transitions across range expression families."""
        self.sm.seed_engine()
        for text in _VALID_RANGE_TEXTS:
            parsed = self.sm.parse_range(text)
            self.assertEqual(parsed.raw_text, text.strip())
        fake_parsed = self.fake.parse_range(">=1.0.0 <2.0.0")
        self.assertEqual(fake_parsed.raw_text, ">=1.0.0 <2.0.0")

    def test_satisfies(self) -> None:
        """Exercises the satisfaction transition across the sampled version/range matrix."""
        self.sm.seed_engine()
        for range_constraint in _SAMPLE_RANGES:
            for version in _SAMPLE_VERSIONS:
                for include_prerelease in (True, False):
                    result = self.sm.satisfies(version, range_constraint, include_prerelease)
                    self.assertEqual(result, model_satisfies(version, range_constraint, include_prerelease))
        fake_result = self.fake.satisfies(_VERSION_1_2_3, _RANGE_CARET_1_2_3, False)
        self.assertTrue(fake_result)
        self.assertFalse(self.fake.satisfies(_VERSION_2_5_0, _RANGE_CARET_1_2_3, False))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T16:13:06Z
# LAST_CHANGED: 2026-11-13T16:13:06Z
# CHANGE: Extend range model with partial-major wildcard comparator families (<1.x, <=1.x, >1.x, >=1.x), full-version hyphen bounds (1.0.0 - 2.0.0), the zero-major zero-minor caret patch boundary (^0.0.3), and numeric prerelease boundaries (>=1.2.3-0.3.7), with matching zero-patch and numeric-prerelease sample versions/ranks so deterministic and fuzz coverage exercises these families.
# --- END AUTOFAB METADATA ---
