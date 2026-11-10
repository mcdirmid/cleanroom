# === File: dependency_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DependencySolver."""

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
from benchmark_1.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
)
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    __initialize__ as _ds_initialize,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import (
    __initialize__ as _sr_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# NOTE: The pseudo-state machine inherits the interface state machine (no new
# state dataclass, no require_arg duplication, no self.state mutation). Only the
# transitions that require observing the real SUT are overridden, pivoting on
# ret = call_target(target.method(*args)).

class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for DependencySolver."""

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


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDependencySolverImplReal(unittest.TestCase):
    """Verifies that the concrete dependency solver satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.sm = DependencySolverImplPseudoStateMachine(
            singletons={
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        release = PackageRelease("alpha", Version(1, 0, 0))
        self.checked_packagerepository.register_package(release)
        assert self.checked_packagerepository.has_package("alpha")
        assert not self.checked_packagerepository.has_package("absent")
        releases = self.checked_packagerepository.get_releases("alpha")
        assert len(releases) == 1
        assert releases[0].name == "alpha"
        assert releases[0].version == Version(1, 0, 0)
        assert self.checked_packagerepository.all_packages() == {"alpha"}
        outcome = self.checked_dependencysolver.resolve(())
        assert len(outcome.selected_versions) == 0

    def test_release_ordering(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("beta", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("beta", Version(2, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease("beta", Version(2, 0, 0, ("alpha",)))
        )
        self.checked_packagerepository.register_package(
            PackageRelease("beta", Version(2, 0, 0, ("1",)))
        )
        releases = self.checked_packagerepository.get_releases("beta")
        assert len(releases) == 4
        assert releases[0].version == Version(2, 0, 0)
        assert releases[1].version == Version(2, 0, 0, ("alpha",))
        assert releases[2].version == Version(2, 0, 0, ("1",))
        assert releases[3].version == Version(1, 0, 0)

    def test_register_release_with_dependencies(self) -> None:
        dependency = PackageDependency("alpha", VersionRange("^1.0.0"))
        release = PackageRelease("gamma", Version(1, 0, 0), (dependency,))
        self.checked_packagerepository.register_package(release)
        releases = self.checked_packagerepository.get_releases("gamma")
        assert len(releases) == 1
        assert len(releases[0].dependencies) == 1
        assert releases[0].dependencies[0].name == "alpha"

    def test_get_releases_reports_missing_package(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("absent")

    def test_resolve_selects_highest_compatible_release(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("core", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("core", Version(1, 2, 0)))
        self.checked_packagerepository.register_package(PackageRelease("core", Version(2, 0, 0)))
        outcome = self.dependencysolver.resolve(
            (PackageDependency("core", VersionRange("^1.0.0")),)
        )
        assert outcome.selected_versions["core"] == Version(1, 2, 0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_transitive_dependencies(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("core", Version(1, 2, 0)))
        core_dependency = PackageDependency("core", VersionRange("^1.0.0"))
        self.checked_packagerepository.register_package(
            PackageRelease("app", Version(1, 0, 0), (core_dependency,))
        )
        outcome = self.dependencysolver.resolve(
            (PackageDependency("app", VersionRange("^1.0.0")),)
        )
        assert outcome.selected_versions["app"] == Version(1, 0, 0)
        assert outcome.selected_versions["core"] == Version(1, 2, 0)

    def test_resolve_backtracks_to_viable_release(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("core", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("core", Version(2, 0, 0)))
        core_dependency = PackageDependency("core", VersionRange("^1.0.0"))
        self.checked_packagerepository.register_package(PackageRelease("app", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease("app", Version(2, 0, 0), (core_dependency,))
        )
        outcome = self.dependencysolver.resolve(
            (
                PackageDependency("app", VersionRange(">=1.0.0")),
                PackageDependency("core", VersionRange("^2.0.0")),
            )
        )
        assert outcome.selected_versions["core"] == Version(2, 0, 0)
        assert outcome.selected_versions["app"] == Version(1, 0, 0)

    def test_resolve_reports_unsatisfiable_constraints(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("core", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("core", Version(2, 0, 0)))
        with self.assertRaises(ResolutionConflictError) as raised:
            self.dependencysolver.resolve(
                (
                    PackageDependency("core", VersionRange("^1.0.0")),
                    PackageDependency("core", VersionRange("^2.0.0")),
                )
            )
        assert "core" in raised.exception.conflicting_packages

    def test_resolve_reports_missing_package(self) -> None:
        with self.assertRaises(ResolutionConflictError) as raised:
            self.dependencysolver.resolve(
                (PackageDependency("absent", VersionRange(">=1.0.0")),)
            )
        assert "absent" in raised.exception.conflicting_packages

    def test_resolve_withdraws_failed_branch_constraints(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("lib", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                (PackageDependency("lib", VersionRange("^1.0.0")),),
            )
        )
        self.checked_packagerepository.register_package(
            PackageRelease(
                "app",
                Version(2, 0, 0),
                (PackageDependency("lib", VersionRange("^2.0.0")),),
            )
        )
        self.checked_packagerepository.register_package(
            PackageRelease(
                "top",
                Version(1, 0, 0),
                (PackageDependency("app", VersionRange(">=1.0.0")),),
            )
        )
        outcome = self.dependencysolver.resolve(
            (PackageDependency("top", VersionRange("^1.0.0")),)
        )
        assert outcome.selected_versions["top"] == Version(1, 0, 0)
        assert outcome.selected_versions["app"] == Version(1, 0, 0)
        assert outcome.selected_versions["lib"] == Version(1, 0, 0)

    def test_resolve_exhausts_all_candidates_before_conflict(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("lib", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                (PackageDependency("lib", VersionRange("^3.0.0")),),
            )
        )
        self.checked_packagerepository.register_package(
            PackageRelease(
                "app",
                Version(2, 0, 0),
                (PackageDependency("lib", VersionRange("^2.0.0")),),
            )
        )
        self.checked_packagerepository.register_package(
            PackageRelease(
                "top",
                Version(1, 0, 0),
                (PackageDependency("app", VersionRange(">=1.0.0")),),
            )
        )
        with self.assertRaises(ResolutionConflictError) as raised:
            self.dependencysolver.resolve(
                (PackageDependency("top", VersionRange("^1.0.0")),)
            )
        assert "lib" in raised.exception.conflicting_packages


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DependencySolverSUT:
    """Aggregate SUT exposing component services for DependencySolver state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.__dict__["_services"] = (self.packagerepository, self.dependencysolver,)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

def make_sut() -> DependencySolverSUT:
    return DependencySolverSUT()


DependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DependencySolverState,
    name="DependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:18:48Z
# LAST_CHANGED: 2026-11-05T17:15:38Z
# CHANGE: Resolved backtracking-postcondition feedback. Added test_resolve_withdraws_failed_branch_constraints: top -> app >=1.0.0 where app 2.0.0 introduces the new transitive constraint lib ^2.0.0 whose branch fails (lib only 1.0.0), forcing the search to withdraw that failed branch's constraint before app 1.0.0 introduces lib ^1.0.0 and succeeds; asserting top/app/lib all resolve to 1.0.0 proves constraint withdrawal (a stale ^2.0.0 constraint would make lib unsatisfiable). Added test_resolve_exhausts_all_candidates_before_conflict: interior app has candidates 2.0.0 (lib ^2.0.0) and 1.0.0 (lib ^3.0.0), each pulling an unsatisfiable transitive dependency against lib 1.0.0, so every candidate is exhausted before ResolutionConflictError is raised, asserting lib appears in conflicting_packages. Both scenarios are driven against the real solver because the interface resolve domain intentionally gates unsatisfiable/conflicting roots out of generated calls.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:18:48Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:18:35Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DependencySolver."""

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
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException):
# ()) live naturally inside the single transition body
# (multi-transition splitting is prohibited). require_arg defines the caller
# precondition contract (checked at runtime on real calls).
#
# PackageNotFoundError is a checked precondition, so get_releases is gated on the
# model repository contents. ResolutionConflictError is likewise a checked
# precondition, so resolve only advertises trivially satisfiable dependency sets;
# rich conflict scenarios belong to companion scenario suites.

SAMPLE_RANGE: VersionRange = VersionRange(">=1.0.0")
SAMPLE_DEPENDENCY: PackageDependency = PackageDependency("alpha", SAMPLE_RANGE)
SAMPLE_RELEASE: PackageRelease = PackageRelease("alpha", Version(1, 0, 0))
SAMPLE_RELEASE_WITH_DEPS: PackageRelease = PackageRelease(
    "beta",
    Version(2, 0, 0),
    (SAMPLE_DEPENDENCY,),
)

# Module-level oracle payloads keep target-service construction out of the state
# machine itself while still giving the fake concrete return values.
EMPTY_RESOLUTION: ResolutionOutcome = ResolutionOutcome(
    selected_versions={},
    derivation_steps=(),
)
EMPTY_ROOT_DEPENDENCIES: Tuple[PackageDependency, ...] = ()


@dataclass
class DependencySolverState:
    """Canonical model state for DependencySolver operations."""

    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    resolutions: List[ResolutionOutcome] = field(default_factory=list)


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense State Machine for DependencySolver."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DependencySolverState(), singletons=singletons)

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require_arg(
            release,
            Domain.type(PackageRelease),
            preferred=[SAMPLE_RELEASE, SAMPLE_RELEASE_WITH_DEPS],
        )
        ret = self.inner_register_package(release)
        self.state.packages.setdefault(release.name, []).append(release)
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.in_set(set(self.state.packages.keys())))
        fake_ret = list(self.state.packages.get(name, []))
        ret = self.inner_get_releases(name)
        assert isinstance(ret, list)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["alpha"])
        fake_ret = name in self.state.packages
        ret = self.inner_has_package(name)
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        fake_ret = set(self.state.packages.keys())
        ret = self.inner_all_packages()
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            Domain.sampled_from([EMPTY_ROOT_DEPENDENCIES]),
            preferred=[EMPTY_ROOT_DEPENDENCIES],
        )
        fake_ret = EMPTY_RESOLUTION
        ret = self.inner_resolve(root_dependencies)
        assert isinstance(ret, ResolutionOutcome)
        self.state.resolutions.append(ret)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = DependencySolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fake(
    state: Optional[DependencySolverState] = None,
) -> DependencySolver:
    """Synthesizes the fake DependencySolver double sharing the canonical model state."""
    return FakeDependencySolver(state=state or DependencySolverState())


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageRepository, DependencySolver]:
    """Synthesizes fake repository and solver services sharing one model state."""
    shared_state = state or DependencySolverState()
    repository: PackageRepository = FakeDependencySolver(state=shared_state)
    solver: DependencySolver = FakeDependencySolver(state=shared_state)
    return (repository, solver)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.repository, self.solver = make_dependency_solver_fakes()
        self.sm = DependencySolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the model proto."""
        self.sm.seed_initial()
        self.sm.register_package(SAMPLE_RELEASE)
        self.sm.get_releases("alpha")
        self.sm.has_package("alpha")
        self.sm.all_packages()
        self.sm.resolve(EMPTY_ROOT_DEPENDENCIES)

    def test_fake_repository_scenarios(self) -> None:
        """Exercises the synthesized fake repository double on fixed scenarios."""
        self.repository.register_package(SAMPLE_RELEASE)
        assert self.repository.has_package("alpha")
        releases = self.repository.get_releases("alpha")
        assert len(releases) == 1
        assert releases[0].name == "alpha"
        assert self.repository.all_packages() == {"alpha"}

    def test_fake_solver_scenarios(self) -> None:
        """Exercises the synthesized fake solver double on fixed scenarios."""
        outcome = self.solver.resolve(EMPTY_ROOT_DEPENDENCIES)
        assert isinstance(outcome, ResolutionOutcome)
        assert len(outcome.selected_versions) == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:56:45Z
# LAST_CHANGED: 2026-11-05T16:56:45Z
# CHANGE: Implemented DependencySolver pretense interface state machine: package-qualified imports, model repository state backing register_package/get_releases domain gating (PackageNotFoundError precondition), has_package/all_packages oracles, resolve restricted to trivially satisfiable root dependency sets (ResolutionConflictError precondition), seed_initial seeding transition, singular and plural fake factories, and fixed fake transition-coverage suite plus FakeDependencySolverFuzzTest.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for VersionEngine."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    SemverCoreState,
    SemverCoreStateMachine,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import VersionEngine
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    __initialize__ as _ds_initialize,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import (
    __initialize__ as _sr_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# NOTE: The pseudo-state machine inherits the interface state machine (no new
# state dataclass, no require_arg duplication, no self.state mutation). Only the
# transitions that require observing the real SUT are overridden, pivoting on
# ret = call_target(target.method(*args)).

class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine for SemverCore."""

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        target: Version = sut(Version)
        ret = call_target(target.format())
        assert isinstance(ret, str)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(
        self,
    ) -> bool:
        target: Version = sut(Version)
        ret = call_target(target.is_prerelease)
        assert isinstance(ret, bool)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert isinstance(ret, Version)
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


proto = SemverCoreImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverCoreImplReal(unittest.TestCase):
    """Verifies that the concrete VersionEngine satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(VersionEngine)
        self.version = Version(1, 2, 3, ("alpha", "1"))
        self.sm = SemverCoreImplPseudoStateMachine(
            singletons={VersionEngine: self.real, Version: self.version}
        )
        self.checked = self.sm.as_checked(VersionEngine, self.real)
        self.checked_version = self.sm.as_checked(Version, self.version)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        parsed = self.checked.parse_version("1.2.3")
        assert parsed.major == 1
        assert parsed.minor == 2
        assert parsed.patch == 3
        assert parsed.prerelease == ()
        assert parsed.build == ()
        assert self.checked.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)) < 0
        assert self.checked.compare_precedence(Version(2, 0, 0), Version(2, 0, 0)) == 0
        assert self.checked.compare_precedence(Version(2, 1, 0), Version(2, 0, 9)) > 0

    def test_prerelease_parsing(self) -> None:
        parsed = self.checked.parse_version("2.0.0-alpha.1")
        assert parsed.major == 2
        assert parsed.minor == 0
        assert parsed.patch == 0
        assert parsed.prerelease == ("alpha", "1")
        assert parsed.build == ()

    def test_build_metadata_parsing(self) -> None:
        parsed = self.checked.parse_version("1.0.0+build.5")
        assert parsed.major == 1
        assert parsed.minor == 0
        assert parsed.patch == 0
        assert parsed.prerelease == ()
        assert parsed.build == ("build", "5")

    def test_multi_digit_component_parsing(self) -> None:
        parsed = self.checked.parse_version("10.20.30")
        assert parsed.major == 10
        assert parsed.minor == 20
        assert parsed.patch == 30

    def test_precedence_prerelease_rules(self) -> None:
        # A normal version outranks a prerelease sharing the same core numbers.
        assert self.checked.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, ("alpha",))) > 0
        assert self.checked.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)) < 0
        # Numeric prerelease identifiers rank below alphanumeric identifiers.
        assert (
            self.checked.compare_precedence(
                Version(1, 0, 0, ("1",)),
                Version(1, 0, 0, ("alpha",)),
            )
            < 0
        )
        assert (
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha",)),
                Version(1, 0, 0, ("1",)),
            )
            > 0
        )
        # Numeric identifiers compare numerically.
        assert (
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha", "2")),
            )
            < 0
        )
        assert (
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha", "2")),
                Version(1, 0, 0, ("alpha", "1")),
            )
            > 0
        )
        # Equal numeric prerelease identifiers and equal prerelease sequences
        # compare equal.
        assert (
            self.checked.compare_precedence(
                Version(1, 0, 0, ("1",)),
                Version(1, 0, 0, ("1",)),
            )
            == 0
        )
        assert (
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha", "1")),
            )
            == 0
        )
        # Unequal alphanumeric identifiers compare ASCII-lexicographically.
        assert (
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha",)),
                Version(1, 0, 0, ("beta",)),
            )
            < 0
        )
        assert (
            self.checked.compare_precedence(
                Version(1, 0, 0, ("beta",)),
                Version(1, 0, 0, ("alpha",)),
            )
            > 0
        )
        # Shorter prerelease sequences rank below longer shared-prefix sequences.
        assert (
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha",)),
                Version(1, 0, 0, ("alpha", "1")),
            )
            < 0
        )
        # Patch components compare numerically.
        assert self.checked.compare_precedence(Version(1, 0, 0), Version(1, 0, 1)) < 0
        assert self.checked.compare_precedence(Version(1, 0, 1), Version(1, 0, 0)) > 0
        # Build metadata is excluded from precedence.
        assert self.checked.compare_precedence(Version(1, 0, 0, (), ("build.1",)), Version(1, 0, 0)) == 0

    def test_version_data_operations(self) -> None:
        assert self.checked_version.format() == "1.2.3-alpha.1"
        assert self.checked_version.is_prerelease

    def test_parse_version_rejects_invalid_text(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("1.2")
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("01.2.3")
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("1.2.3.4")
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("not-a-version")


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class SemverCoreSUT:
    """Aggregate SUT exposing a real Version value and the VersionEngine service."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.version = Version(1, 2, 3, ("alpha", "1"), ("build", "5"))
        self.engine = get_singleton(VersionEngine)
        self.__dict__["_services"] = (self.version, self.engine,)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

def make_sut() -> SemverCoreSUT:
    return SemverCoreSUT()


SemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverCoreState,
    name="SemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:11:58Z
# LAST_CHANGED: 2026-11-05T17:09:29Z
# CHANGE: Resolved deterministic-coverage feedback for VersionEngine: added full SemVer precedence scenarios (normal above prerelease with identical core, numeric below alphanumeric in both directions, numeric identifiers compared numerically and equal numeric identifiers returning zero, unequal alphanumeric identifiers compared ASCII-lexicographically in both directions, shorter shared-prefix prerelease sequences ranking lower, differing patch components, equal prerelease sequences returning zero, build metadata excluded) and added deterministic parse_version failure scenarios asserting InvalidVersionError for grammar violations (missing patch, extra component, non-version text) and leading-zero violations ('01.2.3'), plus deterministic prerelease, build-metadata, and multi-digit component parsing postconditions. Error outcomes are driven against the real engine singleton because the state machine's precondition domains intentionally exclude invalid text from generated/fuzzed calls.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:11:58Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:11:36Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverCore."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version, VersionEngine


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException):
# ()) live naturally inside the single transition body
# (multi-transition splitting is prohibited). require_arg defines the caller
# precondition contract (checked at runtime on real calls).
#
# SemVer 2.0.0 grammar violations surface as InvalidVersionError, a checked
# precondition, so parsable version texts are restricted to a closed domain of
# well-formed payloads. numeric/relational arguments stay open via Domain.type.

VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.1",
    "1.2.3",
    "1.0.0+build.5",
    "2.0.0-alpha.1",
    "10.20.30",
)

SAMPLE_VERSIONS: Tuple[Version, ...] = (
    Version(0, 0, 1),
    Version(1, 0, 0),
    Version(1, 2, 3),
    Version(2, 0, 0),
    Version(1, 0, 0, ("alpha",)),
    Version(1, 0, 0, (), ("build",)),
)

# Module-level oracle payloads keep target-service construction out of the state
# machine itself while still giving the fake concrete return values.
FAKE_PARSED_VERSION: Version = Version(1, 2, 3)
FAKE_FORMATTED_VERSION: str = "1.2.3"
FAKE_COMPARISON: int = 0
FAKE_PRERELEASE: bool = False


@dataclass
class SemverCoreState:
    """Canonical model state for SemverCore operations."""

    initialized: bool = True
    parsed_versions: List[Version] = field(default_factory=list)
    comparisons: List[int] = field(default_factory=list)


class SemverCoreStateMachine(StateMachine[SemverCoreState]):
    """Unified Pretense State Machine for SemverCore."""

    def __init__(
        self,
        state: Optional[SemverCoreState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverCoreState(), singletons=singletons)

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        require(self.state.initialized)
        fake_ret = FAKE_FORMATTED_VERSION
        ret = self.inner_format()
        assert isinstance(ret, str)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.sampled_from(list(VERSION_TEXTS)),
            preferred=["1.2.3"],
        )
        fake_ret = FAKE_PARSED_VERSION
        ret = self.inner_parse_version(text)
        assert isinstance(ret, Version)
        self.state.parsed_versions.append(ret)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version), preferred=[SAMPLE_VERSIONS[1]])
        require_arg(v2, Domain.type(Version), preferred=[SAMPLE_VERSIONS[3]])
        fake_ret = FAKE_COMPARISON
        ret = self.inner_compare_precedence(v1, v2)
        assert isinstance(ret, int)
        self.state.comparisons.append(ret)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(
        self,
    ) -> bool:
        require(self.state.initialized)
        fake_ret = FAKE_PRERELEASE
        ret = self.inner_is_prerelease()
        assert isinstance(ret, bool)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverCoreStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverCore = synthesize_fake(SemverCoreStateMachine)


def make_semver_core_fake(
    state: Optional[SemverCoreState] = None,
) -> VersionEngine:
    """Synthesizes the fake VersionEngine double sharing the canonical model state."""
    return FakeSemverCore(state=state or SemverCoreState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverCoreFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_core_fake()
        self.sm = SemverCoreStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the model proto."""
        self.sm.seed_initial()
        self.sm.format()
        self.sm.parse_version("1.2.3")
        self.sm.compare_precedence(Version(1, 0, 0), Version(2, 0, 0))
        self.sm.is_prerelease()

    def test_fake_engine_scenarios(self) -> None:
        """Exercises the synthesized fake engine double on fixed scenarios."""
        parsed = self.fake.parse_version("1.2.3")
        assert isinstance(parsed, Version)
        assert self.fake.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)) == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverCoreState,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:56:36Z
# LAST_CHANGED: 2026-11-05T16:56:36Z
# CHANGE: Implemented SemverCore pretense interface state machine: package-qualified imports, concrete domains (closed valid-version text set for the InvalidVersionError precondition, open Version domain for precedence args), oracles for format/parse_version/compare_precedence/is_prerelease, seed_initial seeding transition, singular make_semver_core_fake factory, full fixed fake transition-coverage suite, and FakeSemverCoreFuzzTest compilation.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RangeEngine."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    SemverRangeState,
    SemverRangeStateMachine,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    VersionRange,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import RangeEngine
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    __initialize__ as _ds_initialize,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import (
    __initialize__ as _sr_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# NOTE: The pseudo-state machine inherits the interface state machine (no new
# state dataclass, no require_arg duplication, no self.state mutation). Only the
# transitions that require observing the real SUT are overridden, pivoting on
# ret = call_target(target.method(*args)).

class SemverRangeImplPseudoStateMachine(SemverRangeStateMachine):
    """Implementation pseudo-state machine for SemverRange."""

    @transition(RangeEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(target.parse_range(text))
        assert isinstance(ret, VersionRange)
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        assert isinstance(ret, bool)
        return ret


proto = SemverRangeImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverRangeImplReal(unittest.TestCase):
    """Verifies that the concrete RangeEngine satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(RangeEngine)
        self.sm = SemverRangeImplPseudoStateMachine(singletons={RangeEngine: self.real})
        self.checked = self.sm.as_checked(RangeEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        rng = self.checked.parse_range("^1.2.3")
        assert rng.raw_text == "^1.2.3"
        assert self.checked.satisfies(Version(1, 2, 3), rng, False)
        assert not self.checked.satisfies(Version(2, 0, 0), rng, False)

    def test_range_trimming(self) -> None:
        rng = self.checked.parse_range("  >=1.0.0 <2.0.0  ")
        assert rng.raw_text == ">=1.0.0 <2.0.0"
        assert self.checked.satisfies(Version(1, 5, 0), rng, False)
        assert not self.checked.satisfies(Version(2, 0, 0), rng, False)

    def test_wildcard_and_union_ranges(self) -> None:
        wildcard = self.checked.parse_range("1.2.*")
        assert self.checked.satisfies(Version(1, 2, 9), wildcard, False)
        assert not self.checked.satisfies(Version(1, 3, 0), wildcard, False)
        union = self.checked.parse_range("1.2.3 || >=2.0.0")
        assert self.checked.satisfies(Version(1, 2, 3), union, False)
        assert self.checked.satisfies(Version(2, 5, 0), union, False)
        assert not self.checked.satisfies(Version(1, 5, 0), union, False)

    def test_prerelease_gating(self) -> None:
        rng = self.checked.parse_range(">=1.0.0")
        assert not self.checked.satisfies(Version(1, 0, 0, ("alpha",)), rng, False)
        assert not self.checked.satisfies(Version(1, 0, 0, ("alpha",)), rng, True)

    def test_parse_range_rejects_malformed_text(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("   ")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range(">=1.0.0, <2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.3 ||")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("|| >=1.0.0")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("^0.0")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2 - 2.3")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.x.3")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.*-alpha")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.*+build")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.3 - ")

    def test_parse_prerelease_and_build_identifiers(self) -> None:
        rng = self.real.parse_range("1.2.3-alpha.1+build.5")
        assert rng.raw_text == "1.2.3-alpha.1+build.5"
        assert self.real.satisfies(Version(1, 2, 3, ("alpha", "1"), ("build", "5")), rng, True)

    def test_parse_hyphen_range(self) -> None:
        rng = self.real.parse_range("1.2.3 - 2.0.0")
        assert self.real.satisfies(Version(1, 2, 3), rng, False)
        assert self.real.satisfies(Version(1, 5, 0), rng, False)
        assert self.real.satisfies(Version(2, 0, 0), rng, False)
        assert not self.real.satisfies(Version(2, 0, 1), rng, False)
        assert not self.real.satisfies(Version(1, 2, 2), rng, False)

    def test_parse_wildcard_forms(self) -> None:
        major_wildcard = self.real.parse_range("1.x")
        assert self.real.satisfies(Version(1, 9, 9), major_wildcard, False)
        assert not self.real.satisfies(Version(2, 0, 0), major_wildcard, False)
        assert not self.real.satisfies(Version(0, 9, 0), major_wildcard, False)
        minor_wildcard = self.real.parse_range("1.2.x")
        assert self.real.satisfies(Version(1, 2, 9), minor_wildcard, False)
        assert not self.real.satisfies(Version(1, 3, 0), minor_wildcard, False)
        star_form = self.real.parse_range("1.*")
        assert self.real.satisfies(Version(1, 0, 0), star_form, False)
        assert self.real.satisfies(Version(1, 9, 9), star_form, False)
        assert not self.real.satisfies(Version(2, 0, 0), star_form, False)
        open_wildcard = self.real.parse_range("*")
        assert self.real.satisfies(Version(5, 4, 3), open_wildcard, False)

    def test_operator_target_whitespace(self) -> None:
        spaced = self.real.parse_range(">= 1.0.0")
        assert self.real.satisfies(Version(1, 5, 0), spaced, False)
        assert not self.real.satisfies(Version(0, 9, 0), spaced, False)
        caret_spaced = self.real.parse_range("^ 1.2.3")
        assert self.real.satisfies(Version(1, 5, 0), caret_spaced, False)
        assert not self.real.satisfies(Version(2, 0, 0), caret_spaced, False)

    def test_caret_expansion_boundaries(self) -> None:
        zero_minor = self.real.parse_range("^0.2.3")
        assert self.real.satisfies(Version(0, 2, 3), zero_minor, False)
        assert self.real.satisfies(Version(0, 2, 9), zero_minor, False)
        assert not self.real.satisfies(Version(0, 3, 0), zero_minor, False)
        assert not self.real.satisfies(Version(0, 2, 2), zero_minor, False)
        zero_patch = self.real.parse_range("^0.0.3")
        assert self.real.satisfies(Version(0, 0, 3), zero_patch, False)
        assert not self.real.satisfies(Version(0, 0, 4), zero_patch, False)
        major_wildcard = self.real.parse_range("^1.x")
        assert self.real.satisfies(Version(1, 0, 0), major_wildcard, False)
        assert self.real.satisfies(Version(1, 9, 9), major_wildcard, False)
        assert not self.real.satisfies(Version(2, 0, 0), major_wildcard, False)
        minor_wildcard = self.real.parse_range("^0.2.x")
        assert self.real.satisfies(Version(0, 2, 5), minor_wildcard, False)
        assert not self.real.satisfies(Version(0, 3, 0), minor_wildcard, False)

    def test_tilde_expansion(self) -> None:
        rng = self.real.parse_range("~1.2.3")
        assert self.real.satisfies(Version(1, 2, 3), rng, False)
        assert self.real.satisfies(Version(1, 2, 9), rng, False)
        assert not self.real.satisfies(Version(1, 3, 0), rng, False)
        assert not self.real.satisfies(Version(1, 2, 2), rng, False)

    def test_inequality_comparator(self) -> None:
        rng = self.real.parse_range("!=1.2.3")
        assert not self.real.satisfies(Version(1, 2, 3), rng, False)
        assert self.real.satisfies(Version(1, 2, 4), rng, False)

    def test_explicit_prerelease_targeting(self) -> None:
        rng = self.real.parse_range(">=1.0.0-alpha")
        assert self.real.satisfies(Version(1, 0, 0, ("alpha",)), rng, False)
        assert self.real.satisfies(Version(1, 0, 0, ("beta",)), rng, False)

    def test_include_prerelease_boundary_evaluation(self) -> None:
        upper = self.real.parse_range("<1.0.0")
        assert self.real.satisfies(Version(1, 0, 0, ("alpha",)), upper, True)
        assert not self.real.satisfies(Version(1, 0, 0, ("alpha",)), upper, False)
        lower = self.real.parse_range(">=1.0.0")
        assert not self.real.satisfies(Version(1, 0, 0, ("alpha",)), lower, True)

    def test_parse_range_rejects_invalid_identifiers(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.3-")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.3+")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.3-alpha_1")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.3-01")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.3.4")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.a.3")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.* - 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range("1.2.3 - 2.x")
        with self.assertRaises(InvalidRangeError):
            self.real.parse_range(">=")

    def test_prerelease_comparator_ordering(self) -> None:
        numeric = self.real.parse_range("<1.0.0-10")
        assert self.real.satisfies(Version(1, 0, 0, ("9",)), numeric, True)
        numeric_below_alpha = self.real.parse_range(">1.0.0-1")
        assert self.real.satisfies(Version(1, 0, 0, ("alpha",)), numeric_below_alpha, True)
        alpha_above_numeric = self.real.parse_range(">1.0.0-alpha")
        assert not self.real.satisfies(Version(1, 0, 0, ("1",)), alpha_above_numeric, True)
        longer_sequence = self.real.parse_range(">1.0.0-alpha")
        assert self.real.satisfies(Version(1, 0, 0, ("alpha", "1")), longer_sequence, True)
        shorter_sequence = self.real.parse_range("<1.0.0-alpha.1")
        assert self.real.satisfies(Version(1, 0, 0, ("alpha",)), shorter_sequence, True)
        normal_above_prerelease = self.real.parse_range(">1.0.0-alpha")
        assert self.real.satisfies(Version(1, 0, 0), normal_above_prerelease, False)

    def test_strict_greater_comparator(self) -> None:
        rng = self.real.parse_range(">1.2.3")
        assert self.real.satisfies(Version(1, 2, 4), rng, False)
        assert not self.real.satisfies(Version(1, 2, 3), rng, False)
        assert not self.real.satisfies(Version(1, 2, 2), rng, False)

    def test_relational_wildcard_forms(self) -> None:
        ge_wildcard = self.real.parse_range(">=1.x")
        assert self.real.satisfies(Version(1, 0, 0), ge_wildcard, False)
        assert not self.real.satisfies(Version(0, 0, 1), ge_wildcard, False)
        gt_wildcard = self.real.parse_range(">1.x")
        assert self.real.satisfies(Version(9, 9, 9), gt_wildcard, False)
        assert not self.real.satisfies(Version(0, 0, 1), gt_wildcard, False)
        lt_wildcard = self.real.parse_range("<2.x")
        assert self.real.satisfies(Version(0, 0, 1), lt_wildcard, False)
        assert not self.real.satisfies(Version(9, 9, 9), lt_wildcard, False)
        le_wildcard = self.real.parse_range("<=2.x")
        assert self.real.satisfies(Version(2, 0, 0), le_wildcard, False)
        assert not self.real.satisfies(Version(9, 9, 9), le_wildcard, False)
        ne_wildcard = self.real.parse_range("!=1.x")
        assert not self.real.satisfies(Version(1, 5, 0), ne_wildcard, False)
        assert self.real.satisfies(Version(9, 9, 9), ne_wildcard, False)
        ne_open_star = self.real.parse_range("!=*")
        assert not self.real.satisfies(Version(5, 4, 3), ne_open_star, False)
        ne_open_lower_x = self.real.parse_range("!=x")
        assert not self.real.satisfies(Version(5, 4, 3), ne_open_lower_x, False)
        ne_open_upper_x = self.real.parse_range("!=X")
        assert not self.real.satisfies(Version(5, 4, 3), ne_open_upper_x, False)
        open_caret = self.real.parse_range("^*")
        assert self.real.satisfies(Version(9, 9, 9), open_caret, False)

    def test_caret_major_minor_wildcard(self) -> None:
        rng = self.real.parse_range("^1.2.x")
        assert self.real.satisfies(Version(1, 2, 0), rng, False)
        assert self.real.satisfies(Version(1, 3, 0), rng, False)
        assert self.real.satisfies(Version(1, 9, 9), rng, False)
        assert not self.real.satisfies(Version(1, 1, 9), rng, False)
        assert not self.real.satisfies(Version(2, 0, 0), rng, False)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> RangeEngine:
    registry = LifecycleRegistry()
    _ds_initialize(registry)
    _sc_initialize(registry)
    _sr_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RangeEngine)


SemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverRangeState,
    name="SemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:21:05Z
# LAST_CHANGED: 2026-11-05T17:20:31Z
# CHANGE: Resolved open-wildcard inequality feedback: extended test_relational_wildcard_forms with the degenerate != applied to a bare open wildcard in all three spellings ('!=*', '!=x', '!=X'), parsing each range and asserting that a representative normal candidate Version(5,4,3) is rejected (satisfies -> False). This exercises the negated-universal-wildcard branch that the prior major/minor '!=1.x' scenario left uncovered, completing wildcard-inequality coverage for the satisfaction contract.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:21:05Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:20:52Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverRange."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import RangeEngine, VersionRange


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException):
# ()) live naturally inside the single transition body
# (multi-transition splitting is prohibited). require_arg defines the caller
# precondition contract (checked at runtime on real calls).
#
# InvalidRangeError is a checked precondition, so range texts are restricted to
# a closed domain of well-formed expressions. Candidate versions stay open.

RANGE_TEXTS: Tuple[str, ...] = (
    "1.2.3",
    "^1.0.0",
    "^1.2.3",
    "~1.2.0",
    ">=1.0.0",
    ">=1.0.0 <2.0.0",
    "  >=1.0.0 <2.0.0  ",
    "1.2.*",
    "1.2.3 - 2.0.0",
    "1.2.3 || >=2.0.0",
)

SAMPLE_RANGES: Tuple[VersionRange, ...] = (
    VersionRange("1.2.3"),
    VersionRange("^1.0.0"),
    VersionRange("^1.2.3"),
    VersionRange("~1.2.0"),
    VersionRange(">=1.0.0"),
    VersionRange(">=1.0.0 <2.0.0"),
    VersionRange("1.2.*"),
    VersionRange("1.2.3 - 2.0.0"),
    VersionRange("1.2.3 || >=2.0.0"),
)

SAMPLE_VERSIONS: Tuple[Version, ...] = (
    Version(1, 0, 0),
    Version(1, 2, 3),
    Version(1, 2, 4),
    Version(2, 0, 0),
    Version(1, 0, 0, ("alpha",)),
)

# Module-level oracle payloads keep target-service construction out of the state
# machine itself while still giving the fake concrete return values.
FAKE_RANGE: VersionRange = VersionRange("^1.0.0")
FAKE_SATISFACTION: bool = True


@dataclass
class SemverRangeState:
    """Canonical model state for SemverRange operations."""

    initialized: bool = True
    parsed_ranges: List[VersionRange] = field(default_factory=list)
    evaluations: List[bool] = field(default_factory=list)


class SemverRangeStateMachine(StateMachine[SemverRangeState]):
    """Unified Pretense State Machine for SemverRange."""

    def __init__(
        self,
        state: Optional[SemverRangeState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverRangeState(), singletons=singletons)

    @transition(RangeEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.sampled_from(list(RANGE_TEXTS)),
            preferred=["^1.0.0"],
        )
        fake_ret = FAKE_RANGE
        ret = self.inner_parse_range(text)
        assert isinstance(ret, VersionRange)
        self.state.parsed_ranges.append(ret)
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.type(Version), preferred=[SAMPLE_VERSIONS[1]])
        require_arg(
            range_constraint,
            Domain.sampled_from(list(SAMPLE_RANGES)),
            preferred=[SAMPLE_RANGES[1]],
        )
        require_arg(include_prerelease, Domain.boolean(), preferred=[False])
        fake_ret = FAKE_SATISFACTION
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert isinstance(ret, bool)
        self.state.evaluations.append(ret)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverRangeStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverRange = synthesize_fake(SemverRangeStateMachine)


def make_semver_range_fake(
    state: Optional[SemverRangeState] = None,
) -> RangeEngine:
    """Synthesizes the fake RangeEngine double sharing the canonical model state."""
    return FakeSemverRange(state=state or SemverRangeState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverRangeFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_range_fake()
        self.sm = SemverRangeStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the model proto."""
        self.sm.seed_initial()
        self.sm.parse_range("^1.0.0")
        self.sm.satisfies(SAMPLE_VERSIONS[1], SAMPLE_RANGES[1], False)

    def test_fake_engine_scenarios(self) -> None:
        """Exercises the synthesized fake engine double on fixed scenarios."""
        rng = self.fake.parse_range("^1.0.0")
        assert isinstance(rng, VersionRange)
        assert self.fake.satisfies(SAMPLE_VERSIONS[1], SAMPLE_RANGES[1], False)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverRangeState,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:56:42Z
# LAST_CHANGED: 2026-11-05T16:56:42Z
# CHANGE: Implemented SemverRange pretense interface state machine: package-qualified imports, concrete domains (closed valid range-text set gating the InvalidRangeError precondition, open Version domain, closed parsed-range set, boolean prerelease flag), oracles for parse_range/satisfies, seed_initial seeding transition, singular make_semver_range_fake factory, full fixed fake transition-coverage suite, and FakeSemverRangeFuzzTest compilation.
# --- END AUTOFAB METADATA ---
