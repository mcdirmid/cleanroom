# === File: dependency_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DependencySolver."""

from __future__ import annotations

from typing import Any, List, Optional
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
from benchmark_3.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
    SAMPLE_RELEASES,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver_impl import DependencySolver, PackageRepository
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine observing repository and solver services."""

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert isinstance(ret, list)
        for release in ret:
            assert isinstance(release, PackageRelease)
            assert release.name == name
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        assert isinstance(ret, set)
        for name in ret:
            assert isinstance(name, str)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: List[PackageDependency],
    ) -> Any:
        repository: PackageRepository = sut(PackageRepository)
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert isinstance(ret, ResolutionOutcome)
        assert isinstance(ret.derivation_steps, tuple)
        for selected_name in ret.selected_versions:
            assert isinstance(selected_name, str)
            assert repository.has_package(selected_name)
        return ret


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDependencySolverImplReal(unittest.TestCase):
    """Verifies that the concrete repository and solver satisfy their contracts."""

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
            singletons={PackageRepository: self.packagerepository, DependencySolver: self.dependencysolver}
        )
        self.checked_repository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_solver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_register_and_query_repository(self) -> None:
        assert self.checked_repository.register_package(SAMPLE_RELEASES[0]) is None
        assert self.checked_repository.register_package(SAMPLE_RELEASES[1]) is None
        assert self.checked_repository.register_package(SAMPLE_RELEASES[2]) is None
        assert self.checked_repository.has_package("alpha") is True
        assert self.checked_repository.has_package("missing") is False
        assert self.checked_repository.all_packages() == {"alpha", "beta"}
        releases = self.checked_repository.get_releases("alpha")
        assert [release.version for release in releases] == [Version(1, 1, 0), Version(1, 0, 0)]

    def test_resolve_selects_highest_compatible_release(self) -> None:
        self.checked_repository.register_package(SAMPLE_RELEASES[0])
        self.checked_repository.register_package(SAMPLE_RELEASES[1])
        requested = [PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=1.0.0"))]
        outcome = self.checked_solver.resolve(requested)
        assert outcome.selected_versions["alpha"] == Version(1, 1, 0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_transitive_dependencies(self) -> None:
        self.checked_repository.register_package(SAMPLE_RELEASES[0])
        self.checked_repository.register_package(SAMPLE_RELEASES[1])
        self.checked_repository.register_package(SAMPLE_RELEASES[2])
        requested = [PackageDependency(name="beta", range_constraint=VersionRange(raw_text="^2.0.0"))]
        outcome = self.checked_solver.resolve(requested)
        assert outcome.selected_versions["beta"] == Version(2, 0, 0)
        assert outcome.selected_versions["alpha"] == Version(1, 1, 0)

    def test_resolve_combines_multiple_root_constraints(self) -> None:
        self.checked_repository.register_package(SAMPLE_RELEASES[0])
        self.checked_repository.register_package(SAMPLE_RELEASES[1])
        self.checked_repository.register_package(SAMPLE_RELEASES[2])
        requested = [
            PackageDependency(name="beta", range_constraint=VersionRange(raw_text="==2.0.0")),
            PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=1.0.0")),
        ]
        outcome = self.checked_solver.resolve(requested)
        assert outcome.selected_versions["beta"] == Version(2, 0, 0)
        assert outcome.selected_versions["alpha"] == Version(1, 1, 0)

    def test_resolve_backtracks_to_later_viable_release(self) -> None:
        self.checked_repository.register_package(SAMPLE_RELEASES[0])
        self.checked_repository.register_package(SAMPLE_RELEASES[1])
        self.checked_repository.register_package(SAMPLE_RELEASES[3])
        self.checked_repository.register_package(SAMPLE_RELEASES[2])
        self.checked_repository.register_package(SAMPLE_RELEASES[4])
        self.checked_repository.register_package(SAMPLE_RELEASES[5])
        requested = [
            PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=1.0.0")),
            PackageDependency(name="beta", range_constraint=VersionRange(raw_text=">=1.0.0")),
        ]
        outcome = self.checked_solver.resolve(requested)
        assert outcome.selected_versions["alpha"] == Version(1, 1, 0)
        assert outcome.selected_versions["beta"] == Version(2, 0, 0)

    def test_get_releases_unregistered_raises(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("missing")

    def test_resolve_absent_package_reports_conflict(self) -> None:
        requested = [PackageDependency(name="missing", range_constraint=VersionRange(raw_text=">=1.0.0"))]
        with self.assertRaises(ResolutionConflictError) as context:
            self.dependencysolver.resolve(requested)
        assert "missing" in context.exception.conflicting_packages
        assert len(context.exception.explanation) > 0

    def test_resolve_unsatisfiable_requirements_reports_conflict(self) -> None:
        self.checked_repository.register_package(SAMPLE_RELEASES[0])
        self.checked_repository.register_package(SAMPLE_RELEASES[3])
        requested = [
            PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=2.0.0")),
            PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="<2.0.0")),
        ]
        with self.assertRaises(ResolutionConflictError) as context:
            self.dependencysolver.resolve(requested)
        assert "alpha" in context.exception.conflicting_packages
        assert len(context.exception.explanation) > 0

    def test_resolve_retracts_transitive_requirements_on_backtrack(self) -> None:
        self.checked_repository.register_package(SAMPLE_RELEASES[6])
        self.checked_repository.register_package(SAMPLE_RELEASES[7])
        self.checked_repository.register_package(SAMPLE_RELEASES[8])
        self.checked_repository.register_package(SAMPLE_RELEASES[9])
        requested = [
            PackageDependency(name="beta", range_constraint=VersionRange(raw_text=">=1.6.0")),
            PackageDependency(name="gamma", range_constraint=VersionRange(raw_text=">=8.0.0")),
        ]
        outcome = self.checked_solver.resolve(requested)
        assert outcome.selected_versions["beta"] == Version(1, 6, 0)
        assert outcome.selected_versions["gamma"] == Version(9, 0, 0)

    def test_resolve_retracts_sole_transitive_requirement_on_backtrack(self) -> None:
        self.checked_repository.register_package(SAMPLE_RELEASES[6])
        self.checked_repository.register_package(SAMPLE_RELEASES[7])
        self.checked_repository.register_package(SAMPLE_RELEASES[8])
        self.checked_repository.register_package(SAMPLE_RELEASES[9])
        requested = [PackageDependency(name="beta", range_constraint=VersionRange(raw_text=">=1.6.0"))]
        outcome = self.checked_solver.resolve(requested)
        assert outcome.selected_versions["beta"] == Version(1, 6, 0)
        assert "gamma" not in outcome.selected_versions
        assert len(outcome.derivation_steps) == 1


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DependencySolverSUT:
    """Aggregate SUT exposing the repository and solver services to the fuzzer."""

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
        self.__dict__["_services"] = (self.packagerepository, self.dependencysolver)

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
# LAST_CLEANED: 2026-11-05T17:39:13Z
# LAST_CHANGED: 2026-11-05T17:36:45Z
# CHANGE: Add a sole-requester retraction scenario: only beta is a root requirement, while registered beta 2.1.0 depends on gamma ^1.0.0 (unsatisfiable against registered gamma 9.0.0/8.0.0) and beta 1.6.0 has no dependencies. The higher candidate introduces gamma as a brand-new accumulated requirement, the branch fails, and backtracking retracts that sole requirement entirely (no residual gamma constraint), after which beta 1.6.0 succeeds. The test asserts beta 1.6.0 is selected, gamma is absent from selected_versions, and only one derivation step remains, verifying full restoration of accumulated state end to end.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:39:13Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:38:50Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DependencySolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
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
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
)
from benchmark_3.parts.semver_solver_multi.pretense.semver_range_pretense import (
    compare_versions,
    version_satisfies_text,
)


# Representative releases exercised by the package registration transition. The
# beta release depends transitively on alpha so resolution scenarios can be
# generated without violating the repository precondition.
SAMPLE_RELEASES: List[PackageRelease] = [
    PackageRelease(name="alpha", version=Version(1, 0, 0)),
    PackageRelease(name="alpha", version=Version(1, 1, 0)),
    PackageRelease(
        name="beta",
        version=Version(2, 0, 0),
        dependencies=(
            PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="^1.0.0")),
        ),
    ),
    PackageRelease(name="alpha", version=Version(2, 0, 0)),
    PackageRelease(
        name="beta",
        version=Version(1, 0, 0),
        dependencies=(
            PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="^1.0.0")),
        ),
    ),
    PackageRelease(
        name="beta",
        version=Version(1, 5, 0),
        dependencies=(
            PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="^1.0.0")),
        ),
    ),
    PackageRelease(
        name="beta",
        version=Version(2, 1, 0),
        dependencies=(
            PackageDependency(name="gamma", range_constraint=VersionRange(raw_text="^1.0.0")),
        ),
    ),
    PackageRelease(name="beta", version=Version(1, 6, 0)),
    PackageRelease(name="gamma", version=Version(9, 0, 0)),
    PackageRelease(name="gamma", version=Version(8, 0, 0)),
]

SAMPLE_NAMES: List[str] = ["alpha", "beta", "gamma"]


def ordered_releases(releases: List[PackageRelease]) -> List[PackageRelease]:
    """Orders releases by descending version precedence (highest first)."""
    ordered: List[PackageRelease] = []
    for release in releases:
        position = 0
        placed = False
        for existing in ordered:
            if compare_versions(release.version, existing.version) > 0:
                ordered.insert(position, release)
                placed = True
                break
            position += 1
        if not placed:
            ordered.append(release)
    return ordered


def solve_dependencies(
    root_dependencies: List[PackageDependency],
    packages: Dict[str, List[PackageRelease]],
) -> Tuple[Dict[str, Version], Tuple[str, ...], List[str], Tuple[str, ...]]:
    """Runs the reference MRV depth-first search with backtracking and conflict trail."""
    accumulated: Dict[str, List[Tuple[str, VersionRange]]] = {}
    for dependency in root_dependencies:
        accumulated.setdefault(dependency.name, []).append(("root", dependency.range_constraint))
    assignment: Dict[str, PackageRelease] = {}
    conflict_trail: List[str] = []
    derivation_steps: List[str] = []
    conflicting_packages: Set[str] = set()

    def backtrack() -> bool:
        unassigned: List[str] = []
        for name in accumulated:
            if name not in assignment:
                unassigned.append(name)
        if not unassigned:
            return True
        candidates_map: Dict[str, List[PackageRelease]] = {}
        for name in unassigned:
            viable: List[PackageRelease] = []
            for release in ordered_releases(packages.get(name, [])):
                satisfies_all = True
                for requester, constraint in accumulated[name]:
                    if not version_satisfies_text(release.version, constraint.raw_text, False):
                        satisfies_all = False
                        break
                if satisfies_all:
                    viable.append(release)
            candidates_map[name] = viable
        selected_name = ""
        selected_count = -1
        for name in unassigned:
            count = len(candidates_map[name])
            if selected_count < 0 or count < selected_count or (count == selected_count and name < selected_name):
                selected_count = count
                selected_name = name
        candidates = candidates_map[selected_name]
        if not candidates:
            requesters: List[str] = []
            for requester, constraint in accumulated[selected_name]:
                requesters.append(requester)
            conflicting_packages.add(selected_name)
            for requester in requesters:
                conflicting_packages.add(requester)
            conflict_trail.append(
                "No viable releases for '" + selected_name + "' satisfying constraints from " + str(requesters)
            )
            return False
        for candidate in candidates:
            assignment[selected_name] = candidate
            derivation_steps.append("Assign '" + selected_name + "' to " + str(candidate.version))
            conflict_detected = False
            newly_added: List[Tuple[str, Tuple[str, VersionRange]]] = []
            for dependency in candidate.dependencies:
                if dependency.name in assignment:
                    if not version_satisfies_text(
                        assignment[dependency.name].version,
                        dependency.range_constraint.raw_text,
                        False,
                    ):
                        conflict_detected = True
                        conflicting_packages.add(selected_name)
                        conflicting_packages.add(dependency.name)
                        conflict_trail.append(
                            "Conflict: '"
                            + selected_name
                            + "' requires "
                            + dependency.name
                            + " "
                            + dependency.range_constraint.raw_text
                        )
                        break
                else:
                    entry = (selected_name, dependency.range_constraint)
                    accumulated.setdefault(dependency.name, []).append(entry)
                    newly_added.append((dependency.name, entry))
            if not conflict_detected and backtrack():
                return True
            for name, entry in newly_added:
                accumulated[name].remove(entry)
                if not accumulated[name]:
                    del accumulated[name]
            del assignment[selected_name]
            derivation_steps.pop()
        return False

    success = backtrack()
    selected_versions: Dict[str, Version] = {}
    if success:
        for name in assignment:
            selected_versions[name] = assignment[name].version
    return (selected_versions, tuple(derivation_steps), conflict_trail, tuple(sorted(conflicting_packages)))


def _dependency_sort_key(dependency: PackageDependency) -> Tuple[str, str]:
    return (dependency.name, dependency.range_constraint.raw_text)


def satisfiable_requests(
    candidates: Set[PackageDependency],
    packages: Dict[str, List[PackageRelease]],
) -> List[List[PackageDependency]]:
    """Enumerates root dependency bundles that the modeled repository can satisfy."""
    ordered: List[PackageDependency] = []
    for dependency in sorted(candidates, key=_dependency_sort_key):
        ordered.append(dependency)
    requests: List[List[PackageDependency]] = [[]]
    for dependency in ordered:
        selection, _steps, _trail, _conflicting = solve_dependencies([dependency], packages)
        if selection:
            requests.append([dependency])
    for first in range(len(ordered)):
        for second in range(first + 1, len(ordered)):
            forward = [ordered[first], ordered[second]]
            selection, _steps, _trail, _conflicting = solve_dependencies(forward, packages)
            if selection:
                requests.append(forward)
                requests.append([ordered[second], ordered[first]])
    return requests


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class DependencySolverState:
    """Canonical model state for repository and dependency resolution operations."""
    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    latest_versions: Dict[str, Version] = field(default_factory=dict)
    available_dependencies: Set[PackageDependency] = field(default_factory=set)
    outcomes: List[ResolutionOutcome] = field(default_factory=list)


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense state machine modeling repository and solver protocols."""

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
        require_arg(release, Domain.sampled_from(SAMPLE_RELEASES))
        fake_return = None
        ret = make_return_value(fake_return)
        registered = self.state.packages.get(release.name)
        if registered is None:
            self.state.packages[release.name] = [release]
        else:
            registered.append(release)
        dependencies_available = True
        for dependency in release.dependencies:
            satisfying = False
            for candidate in self.state.packages.get(dependency.name, []):
                if version_satisfies_text(candidate.version, dependency.range_constraint.raw_text, False):
                    satisfying = True
                    break
            if not satisfying:
                dependencies_available = False
                break
        if not release.version.is_prerelease and dependencies_available:
            version_text = str(release.version.major) + "." + str(release.version.minor) + "." + str(release.version.patch)
            lowered = (release.version.major, release.version.minor, release.version.patch)
            current = self.state.latest_versions.get(release.name)
            is_latest = current is None or lowered > (current.major, current.minor, current.patch)
            if is_latest:
                retained = {
                    dep
                    for dep in self.state.available_dependencies
                    if dep.name != release.name or dep.range_constraint.raw_text.startswith(">=")
                }
                self.state.available_dependencies = retained
                self.state.latest_versions[release.name] = release.version
                for prefix in ("==", "^", "~"):
                    self.state.available_dependencies.add(
                        PackageDependency(name=release.name, range_constraint=VersionRange(raw_text=prefix + version_text))
                    )
            self.state.available_dependencies.add(
                PackageDependency(name=release.name, range_constraint=VersionRange(raw_text=">=" + version_text))
            )
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.in_set(self.state.packages.keys()))
        fake_return = ordered_releases(self.state.packages.get(name, []))
        ret = make_return_value(fake_return)
        assert ret == fake_return
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=SAMPLE_NAMES)
        fake_return = name in self.state.packages
        ret = make_return_value(fake_return)
        assert ret == fake_return
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        fake_return = set(self.state.packages.keys())
        ret = make_return_value(fake_return)
        assert ret == fake_return
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: List[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            Domain.sampled_from(satisfiable_requests(self.state.available_dependencies, self.state.packages)),
        )
        selected_versions, derivation_steps, _conflict_trail, _conflicting_packages = solve_dependencies(
            root_dependencies,
            self.state.packages,
        )
        fake_return = ResolutionOutcome(selected_versions=selected_versions, derivation_steps=derivation_steps)
        ret = make_return_value(fake_return)
        self.state.outcomes.append(fake_return)
        assert ret == fake_return
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed the model state so operations become available during fuzzing."""
        self.state.initialized = True


proto = DependencySolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageRepository, DependencySolver]:
    """Synthesizes sharing fakes for the repository and solver interfaces."""
    fake = FakeDependencySolver(state=state or DependencySolverState())
    return (fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all declared transitions."""

    def setUp(self) -> None:
        repository, solver = make_dependency_solver_fakes()
        self.repository = repository
        self.solver = solver
        self.sm = DependencySolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every transition and seeding transition on the fake."""
        self.sm.seed_initial()
        alpha_100 = PackageRelease(name="alpha", version=Version(1, 0, 0))
        alpha_110 = PackageRelease(name="alpha", version=Version(1, 1, 0))
        assert self.repository.register_package(alpha_100) is None
        assert self.repository.register_package(alpha_110) is None
        assert self.repository.has_package("alpha") is True
        assert self.repository.has_package("missing") is False
        assert self.repository.all_packages() == {"alpha"}
        releases = self.repository.get_releases("alpha")
        assert [release.version for release in releases] == [Version(1, 1, 0), Version(1, 0, 0)]
        requested = [PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=1.0.0"))]
        outcome = self.solver.resolve(requested)
        assert outcome.selected_versions["alpha"] == Version(1, 1, 0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_transitive_dependencies(self) -> None:
        """Resolution selects the highest release of each transitively required package."""
        assert self.repository.register_package(SAMPLE_RELEASES[0]) is None
        assert self.repository.register_package(SAMPLE_RELEASES[1]) is None
        assert self.repository.register_package(SAMPLE_RELEASES[2]) is None
        requested = [PackageDependency(name="beta", range_constraint=VersionRange(raw_text="^2.0.0"))]
        outcome = self.solver.resolve(requested)
        assert outcome.selected_versions["beta"] == Version(2, 0, 0)
        assert outcome.selected_versions["alpha"] == Version(1, 1, 0)

    def test_resolve_exact_release(self) -> None:
        """An exact constraint pins the requested release even below the newest release."""
        assert self.repository.register_package(SAMPLE_RELEASES[0]) is None
        requested = [PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="==1.0.0"))]
        outcome = self.solver.resolve(requested)
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)
        assert len(outcome.derivation_steps) > 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:38:05Z
# LAST_CHANGED: 2026-11-05T17:30:40Z
# CHANGE: Add retraction-sample releases (beta 2.1.0 depending on gamma ^1.0.0; beta 1.6.0 without dependencies; gamma 9.0.0 and gamma 8.0.0) so deterministic scenarios can exercise backtracking that retracts newly introduced transitive requirements before a lower-precedence candidate succeeds. The resolve require_arg satisfiability gate remains in place for fuzzing.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for VersionEngine."""

from __future__ import annotations

from typing import Any, Optional
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
from benchmark_3.parts.semver_solver_multi.pretense.semver_core_pretense import (
    SemverCoreState,
    SemverCoreStateMachine,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import VersionEngine
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine observing the concrete VersionEngine."""

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert isinstance(ret, Version)
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        anti_symmetric = target.compare_precedence(v2, v1)
        assert isinstance(anti_symmetric, int)
        assert (ret > 0 and anti_symmetric < 0) or (ret < 0 and anti_symmetric > 0) or (ret == 0 and anti_symmetric == 0)
        return ret


proto = SemverCoreImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverCoreImplReal(unittest.TestCase):
    """Verifies that the concrete VersionEngine satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _sc_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(VersionEngine)
        self.sm = SemverCoreImplPseudoStateMachine(singletons={VersionEngine: self.real})
        self.checked = self.sm.as_checked(VersionEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version(self) -> None:
        plain = self.checked.parse_version("1.2.3")
        assert plain == Version(1, 2, 3)
        prerelease = self.checked.parse_version("1.2.3-rc.1+build.5")
        assert prerelease == Version(1, 2, 3, ("rc", "1"), ("build", "5"))
        assert prerelease.prerelease == ("rc", "1")
        assert prerelease.build == ("build", "5")

    def test_compare_precedence(self) -> None:
        assert self.checked.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)) == 0
        assert self.checked.compare_precedence(Version(1, 2, 3), Version(2, 0, 0)) < 0
        assert self.checked.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)) > 0
        assert self.checked.compare_precedence(Version(1, 0, 0), Version(1, 0, 1)) < 0
        assert self.checked.compare_precedence(Version(1, 10, 0), Version(1, 9, 0)) > 0

    def test_compare_prerelease_precedence(self) -> None:
        normal = Version(1, 0, 0)
        alpha = Version(1, 0, 0, ("alpha",))
        alpha_one = Version(1, 0, 0, ("alpha", "1"))
        alpha_beta = Version(1, 0, 0, ("alpha", "beta"))
        assert self.checked.compare_precedence(normal, alpha) > 0
        assert self.checked.compare_precedence(alpha, normal) < 0
        assert self.checked.compare_precedence(alpha, alpha_one) < 0
        assert self.checked.compare_precedence(alpha_one, alpha_beta) < 0

    def test_build_metadata_ignored(self) -> None:
        with_build = Version(1, 2, 3, (), ("build", "9"))
        without_build = Version(1, 2, 3)
        assert self.checked.compare_precedence(with_build, without_build) == 0

    def test_parse_version_rejects_malformed_input(self) -> None:
        for text in ("01.2.3", "1.2", "not-a-version", "1.2.3.4"):
            with self.assertRaises(InvalidVersionError) as context:
                self.real.parse_version(text)
            assert context.exception.raw_text == text

    def test_compare_numeric_prerelease_identifiers(self) -> None:
        assert self.checked.compare_precedence(Version(1, 0, 0, ("10",)), Version(1, 0, 0, ("9",))) > 0
        assert self.checked.compare_precedence(Version(1, 0, 0, ("2",)), Version(1, 0, 0, ("2",))) == 0
        assert self.checked.compare_precedence(Version(1, 0, 0, ("2",)), Version(1, 0, 0, ("10",))) < 0

    def test_compare_textual_prerelease_identifiers(self) -> None:
        assert self.checked.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))) < 0
        assert self.checked.compare_precedence(Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("alpha",))) > 0

    def test_identical_prerelease_sequences_compare_equal(self) -> None:
        left = Version(1, 2, 3, ("rc", "1"), ("build", "7"))
        right = Version(1, 2, 3, ("rc", "1"), ("build", "9"))
        assert self.checked.compare_precedence(left, right) == 0


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> VersionEngine:
    registry = LifecycleRegistry()
    _sc_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(VersionEngine)


SemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverCoreState,
    name="SemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:35:29Z
# LAST_CHANGED: 2026-11-05T17:32:00Z
# CHANGE: Restore deterministic coverage of the parse_version contracted error precondition by driving the concrete engine directly with rejected texts: leading-zero numeric identifiers (01.2.3), truncated components (1.2), grammar violations (not-a-version), and extra components (1.2.3.4) each assert InvalidVersionError and verify the exception carries the original unparseable raw_text. Conforming-input precedence coverage (numeric/textual prerelease and identical sequences) remains.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:35:29Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:33:19Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemVer core."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
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
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version, VersionEngine


# Valid SemVer 2.0.0 strings used to exercise the parsing transition. Invalid
# grammar is a caller precondition (InvalidVersionError) and is never generated.
VERSION_SAMPLES: List[str] = [
    "0.0.1",
    "1.0.0",
    "1.2.3",
    "2.10.3",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.2.3-beta.2",
    "1.2.3+build.5",
    "1.2.3-rc.1+build.5",
]

PREFERRED_VERSIONS: List[Version] = [
    Version(0, 0, 1),
    Version(1, 0, 0),
    Version(1, 2, 3),
    Version(1, 0, 0, ("alpha",)),
]


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverCoreState:
    """Canonical model state for SemVer core operations."""
    initialized: bool = True
    parsed_versions: List[Version] = field(default_factory=list)
    comparison_count: int = 0


class SemverCoreStateMachine(StateMachine[SemverCoreState]):
    """Unified Pretense state machine modeling the VersionEngine protocol."""

    def __init__(
        self,
        state: Optional[SemverCoreState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverCoreState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(VERSION_SAMPLES))
        core_and_build = text.partition("+")
        core = core_and_build[0].partition("-")
        numbers = core[0].split(".")
        prerelease = tuple(core[2].split(".")) if core[2] else ()
        build = tuple(core_and_build[2].split(".")) if core_and_build[2] else ()
        fake_return = Version(
            major=int(numbers[0]),
            minor=int(numbers[1]),
            patch=int(numbers[2]),
            prerelease=prerelease,
            build=build,
        )
        ret = make_return_value(fake_return)
        self.state.parsed_versions.append(fake_return)
        assert ret == fake_return
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version), preferred=PREFERRED_VERSIONS)
        require_arg(v2, Domain.type(Version), preferred=PREFERRED_VERSIONS)
        comparison = 0
        if v1.major != v2.major:
            comparison = 1 if v1.major > v2.major else -1
        elif v1.minor != v2.minor:
            comparison = 1 if v1.minor > v2.minor else -1
        elif v1.patch != v2.patch:
            comparison = 1 if v1.patch > v2.patch else -1
        else:
            left = v1.prerelease
            right = v2.prerelease
            if not left and right:
                comparison = 1
            elif left and not right:
                comparison = -1
            else:
                matched = True
                limit = min(len(left), len(right))
                for index in range(limit):
                    left_part = left[index]
                    right_part = right[index]
                    left_numeric = left_part.isdigit()
                    right_numeric = right_part.isdigit()
                    if left_numeric and right_numeric:
                        if int(left_part) != int(right_part):
                            comparison = 1 if int(left_part) > int(right_part) else -1
                            matched = False
                            break
                    elif left_numeric != right_numeric:
                        comparison = -1 if left_numeric else 1
                        matched = False
                        break
                    elif left_part != right_part:
                        comparison = 1 if left_part > right_part else -1
                        matched = False
                        break
                if matched and len(left) != len(right):
                    comparison = 1 if len(left) > len(right) else -1
        fake_return = comparison
        ret = make_return_value(fake_return)
        self.state.comparison_count += 1
        assert ret == fake_return
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed the model state so operations become available during fuzzing."""
        self.state.initialized = True


proto = SemverCoreStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverCore = synthesize_fake(SemverCoreStateMachine)


def make_semver_core_fake(state: Optional[SemverCoreState] = None) -> VersionEngine:
    """Synthesizes a fake VersionEngine backed by the SemVer state machine."""
    return FakeSemverCore(state=state or SemverCoreState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverCoreFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all declared transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_core_fake()
        self.sm = SemverCoreStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every transition and seeding transition on the fake."""
        self.sm.seed_initial()
        parsed = self.fake.parse_version("1.2.3-rc.1+build.5")
        assert parsed.major == 1
        assert parsed.minor == 2
        assert parsed.patch == 3
        assert parsed.prerelease == ("rc", "1")
        assert parsed.build == ("build", "5")
        assert self.fake.compare_precedence(Version(1, 0, 0), Version(1, 0, 0)) == 0
        assert self.fake.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)) < 0
        assert self.fake.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)) < 0
        assert self.fake.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "2"))) < 0
        assert self.fake.compare_precedence(Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("alpha",))) > 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverCoreState,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:58:35Z
# LAST_CHANGED: 2026-11-05T16:58:35Z
# CHANGE: Model VersionEngine parse_version/compare_precedence transitions with canonical SemVer precedence logic, valid-input domains, synthesized VersionEngine fake, fixed fake coverage, and Hypothesis fake fuzzing.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RangeEngine."""

from __future__ import annotations

from typing import Any, Optional
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
from benchmark_3.parts.semver_solver_multi.pretense.semver_range_pretense import (
    SemverRangeState,
    SemverRangeStateMachine,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import RangeEngine
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverRangeImplPseudoStateMachine(SemverRangeStateMachine):
    """Implementation pseudo-state machine observing the concrete RangeEngine."""

    @transition(RangeEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> Any:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(target.parse_range(text))
        assert isinstance(ret, VersionRange)
        assert isinstance(ret.raw_text, str)
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Any:
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
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(RangeEngine)
        self.sm = SemverRangeImplPseudoStateMachine(singletons={RangeEngine: self.real})
        self.checked = self.sm.as_checked(RangeEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_range_trims_whitespace(self) -> None:
        parsed = self.checked.parse_range("  >= 1.0.0  ")
        assert parsed.raw_text == ">= 1.0.0"

    def test_caret_and_tilde_ranges(self) -> None:
        caret = self.checked.parse_range("^1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), caret, False) is True
        assert self.checked.satisfies(Version(1, 9, 0), caret, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), caret, False) is False
        assert self.checked.satisfies(Version(1, 2, 2), caret, False) is False
        tilde = self.checked.parse_range("~1.2.3")
        assert self.checked.satisfies(Version(1, 2, 9), tilde, False) is True
        assert self.checked.satisfies(Version(1, 3, 0), tilde, False) is False

    def test_wildcard_hyphen_and_union_ranges(self) -> None:
        star = self.checked.parse_range("*")
        assert self.checked.satisfies(Version(0, 1, 2), star, False) is True
        minor = self.checked.parse_range("1.2.x")
        assert self.checked.satisfies(Version(1, 2, 9), minor, False) is True
        assert self.checked.satisfies(Version(1, 3, 0), minor, False) is False
        hyphen = self.checked.parse_range("1.2.3 - 2.3.4")
        assert self.checked.satisfies(Version(1, 2, 3), hyphen, False) is True
        assert self.checked.satisfies(Version(2, 3, 4), hyphen, False) is True
        assert self.checked.satisfies(Version(2, 3, 5), hyphen, False) is False
        union = self.checked.parse_range(">=1.0.0 || <0.5.0")
        assert self.checked.satisfies(Version(0, 4, 0), union, False) is True
        assert self.checked.satisfies(Version(1, 0, 0), union, False) is True
        assert self.checked.satisfies(Version(0, 6, 0), union, False) is False

    def test_basic_comparators_and_conjunction(self) -> None:
        bounded = self.checked.parse_range(">=1.0.0 <2.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), bounded, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), bounded, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), bounded, False) is False
        exact = self.checked.parse_range("==1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), exact, False) is True
        assert self.checked.satisfies(Version(1, 2, 4), exact, False) is False

    def test_prerelease_matching_rules(self) -> None:
        stable = self.checked.parse_range(">=1.0.0")
        alpha_below = Version(1, 0, 0, ("alpha",))
        beta_above = Version(1, 1, 0, ("beta",))
        assert self.checked.satisfies(alpha_below, stable, False) is False
        assert self.checked.satisfies(beta_above, stable, False) is False
        assert self.checked.satisfies(alpha_below, stable, True) is False
        assert self.checked.satisfies(beta_above, stable, True) is True
        explicit = self.checked.parse_range(">=1.0.0-alpha")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha",)), explicit, False) is True

    def test_parse_range_rejects_invalid_expressions(self) -> None:
        malformed = ("", "   ", "1.0.0, <2.0.0", ">=1.0.0 ||", "|| <2.0.0", "1", "1.2", "^0.0", "1.2 - 2.3", "=>1.0.0")
        for text in malformed:
            with self.assertRaises(InvalidRangeError) as context:
                self.real.parse_range(text)
            assert context.exception.raw_range == text

    def test_wildcard_caret_and_tilde_prefixes(self) -> None:
        any_caret = self.checked.parse_range("^*")
        assert self.checked.satisfies(Version(1, 2, 3), any_caret, False) is True
        any_tilde = self.checked.parse_range("~*")
        assert self.checked.satisfies(Version(1, 2, 3), any_tilde, False) is True
        minor_caret = self.checked.parse_range("^1.2.x")
        assert self.checked.satisfies(Version(1, 2, 0), minor_caret, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), minor_caret, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), minor_caret, False) is False
        minor_tilde = self.checked.parse_range("~1.2.x")
        assert self.checked.satisfies(Version(1, 2, 9), minor_tilde, False) is True
        assert self.checked.satisfies(Version(1, 3, 0), minor_tilde, False) is False

    def test_zero_major_caret_wildcard_ranges(self) -> None:
        zero_minor = self.checked.parse_range("^0.2.x")
        assert self.checked.satisfies(Version(0, 2, 0), zero_minor, False) is True
        assert self.checked.satisfies(Version(0, 2, 9), zero_minor, False) is True
        assert self.checked.satisfies(Version(0, 3, 0), zero_minor, False) is False
        zero_patch = self.checked.parse_range("^0.0.x")
        assert self.checked.satisfies(Version(0, 0, 5), zero_patch, False) is True
        assert self.checked.satisfies(Version(0, 1, 0), zero_patch, False) is False

    def test_full_version_comparators(self) -> None:
        not_equal = self.checked.parse_range("!=1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), not_equal, False) is False
        assert self.checked.satisfies(Version(1, 2, 4), not_equal, False) is True
        greater = self.checked.parse_range(">1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), greater, False) is False
        assert self.checked.satisfies(Version(1, 2, 4), greater, False) is True
        less_or_equal = self.checked.parse_range("<=1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), less_or_equal, False) is True
        assert self.checked.satisfies(Version(1, 2, 4), less_or_equal, False) is False

    def test_wildcard_major_and_minor_boundaries(self) -> None:
        major_wildcard = self.checked.parse_range("1.x")
        assert self.checked.satisfies(Version(1, 0, 0), major_wildcard, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), major_wildcard, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), major_wildcard, False) is False
        star_wildcard = self.checked.parse_range("1.*")
        assert self.checked.satisfies(Version(1, 0, 0), star_wildcard, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), star_wildcard, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), star_wildcard, False) is False
        patch_wildcard = self.checked.parse_range("1.2.*")
        assert self.checked.satisfies(Version(1, 2, 0), patch_wildcard, False) is True
        assert self.checked.satisfies(Version(1, 2, 9), patch_wildcard, False) is True
        assert self.checked.satisfies(Version(1, 3, 0), patch_wildcard, False) is False

    def test_relational_comparators_with_wildcard_targets(self) -> None:
        assert isinstance(self.checked.satisfies(Version(1, 5, 0), self.checked.parse_range(">=1.x"), False), bool)
        assert isinstance(self.checked.satisfies(Version(2, 0, 0), self.checked.parse_range(">1.x"), False), bool)
        assert isinstance(self.checked.satisfies(Version(1, 9, 9), self.checked.parse_range("<=1.x"), False), bool)
        assert isinstance(self.checked.satisfies(Version(0, 9, 9), self.checked.parse_range("<1.x"), False), bool)
        assert isinstance(self.checked.satisfies(Version(2, 0, 0), self.checked.parse_range("!=1.x"), False), bool)
        assert isinstance(self.checked.satisfies(Version(1, 0, 0), self.checked.parse_range(">*"), False), bool)
        assert isinstance(self.checked.satisfies(Version(1, 0, 0), self.checked.parse_range("<*"), False), bool)
        assert isinstance(self.checked.satisfies(Version(1, 0, 0), self.checked.parse_range("!=*"), False), bool)
        assert isinstance(self.checked.satisfies(Version(1, 0, 0), self.checked.parse_range(">=*"), False), bool)
        assert isinstance(self.checked.satisfies(Version(1, 0, 0), self.checked.parse_range("<=*"), False), bool)

    def test_caret_zero_major_ranges(self) -> None:
        zero_minor = self.checked.parse_range("^0.2.3")
        assert self.checked.satisfies(Version(0, 2, 3), zero_minor, False) is True
        assert self.checked.satisfies(Version(0, 2, 9), zero_minor, False) is True
        assert self.checked.satisfies(Version(0, 3, 0), zero_minor, False) is False
        zero_patch = self.checked.parse_range("^0.0.3")
        assert self.checked.satisfies(Version(0, 0, 3), zero_patch, False) is True
        assert self.checked.satisfies(Version(0, 0, 4), zero_patch, False) is False

    def test_caret_and_tilde_with_wildcard_targets(self) -> None:
        caret_wildcard = self.checked.parse_range("^1.x")
        assert isinstance(self.checked.satisfies(Version(1, 9, 0), caret_wildcard, False), bool)
        tilde_wildcard = self.checked.parse_range("~1.x")
        assert isinstance(self.checked.satisfies(Version(1, 9, 0), tilde_wildcard, False), bool)

    def test_hyphen_ranges_with_wildcard_endpoints(self) -> None:
        hyphen = self.checked.parse_range("1.x - 2.x")
        assert isinstance(self.checked.satisfies(Version(2, 5, 0), hyphen, False), bool)
        assert isinstance(self.checked.satisfies(Version(3, 0, 0), hyphen, False), bool)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> RangeEngine:
    registry = LifecycleRegistry()
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
# LAST_CLEANED: 2026-11-05T17:39:15Z
# LAST_CHANGED: 2026-11-05T17:37:46Z
# CHANGE: Add test_zero_major_caret_wildcard_ranges exercising the zero-major patch-wildcard caret branches: ^0.2.x admits 0.2.0/0.2.9 and rejects 0.3.0, and ^0.0.x admits 0.0.5 and rejects 0.1.0, covering the minor-bumped upper boundary selected when the major is zero. Both expressions were added to the model's admitted RANGE_SAMPLES/RANGE_CONSTRAINTS and the model caret expansion was corrected to bump the minor in that case.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T17:39:15Z
# PRETENSE_QA_AUDIT: 2026-11-05T17:38:52Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for version ranges."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
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
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import InvalidRangeError, RangeEngine, VersionRange


# Valid range expression strings used to exercise the parsing transition. Empty,
# comma-separated, and bare partial expressions are caller preconditions
# (InvalidRangeError) and are never generated.
RANGE_SAMPLES: List[str] = [
    "1.2.3",
    "^1.2.3",
    "~1.2.3",
    "==1.2.3",
    "!=1.2.3",
    ">=1.0.0",
    "> 1.0.0",
    "<=2.0.0",
    "<2.0.0",
    ">=1.0.0 <2.0.0",
    "1.x",
    "1.*",
    "1.2.x",
    "1.2.*",
    "*",
    "1.2.3 - 2.3.4",
    "1.x - 2.x",
    ">=1.0.0 || <0.5.0",
    ">=1.x",
    ">1.x",
    "<=1.x",
    "<1.x",
    "!=1.x",
    ">*",
    "<*",
    "!=*",
    ">=*",
    "<=*",
    "^0.2.3",
    "^0.0.3",
    "^0.2.x",
    "^0.0.x",
    "^1.x",
    "~1.x",
    "^*",
    "~*",
    "^1.2.x",
    "~1.2.x",
    ">1.2.3",
    "<=1.2.3",
    "  >= 1.0.0  ",
    ">=1.0.0-alpha",
]

# Ranges fed to the satisfaction transition must already be normalized (no
# surrounding whitespace); parsing is responsible for trimming.
RANGE_CONSTRAINTS: List[VersionRange] = [
    VersionRange(raw_text=sample) for sample in RANGE_SAMPLES if sample == sample.strip()
]

PREFERRED_VERSIONS: List[Version] = [
    Version(0, 0, 1),
    Version(1, 0, 0),
    Version(1, 2, 3),
    Version(2, 0, 0),
    Version(1, 0, 0, ("alpha",)),
]


# ==============================================================================
# Pure range algebra shared by the model (and reusable by solver modeling).
# ==============================================================================

def compare_versions(left: Version, right: Version) -> int:
    """Compares two versions by SemVer 2.0.0 precedence, ignoring build metadata."""
    if left.major != right.major:
        return 1 if left.major > right.major else -1
    if left.minor != right.minor:
        return 1 if left.minor > right.minor else -1
    if left.patch != right.patch:
        return 1 if left.patch > right.patch else -1
    left_parts = left.prerelease
    right_parts = right.prerelease
    if not left_parts and not right_parts:
        return 0
    if not left_parts:
        return 1
    if not right_parts:
        return -1
    limit = min(len(left_parts), len(right_parts))
    for index in range(limit):
        left_part = left_parts[index]
        right_part = right_parts[index]
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            if int(left_part) != int(right_part):
                return 1 if int(left_part) > int(right_part) else -1
        elif left_numeric != right_numeric:
            return -1 if left_numeric else 1
        elif left_part != right_part:
            return 1 if left_part > right_part else -1
    if len(left_parts) != len(right_parts):
        return 1 if len(left_parts) > len(right_parts) else -1
    return 0


@dataclass(frozen=True)
class _Bound:
    """Parsed comparator target with partial wildcard markers."""
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...]
    wildcard: int


def _parse_bound(text: str) -> _Bound:
    """Parses a full or partial version target ('*'/'x'/'X' mark wildcards)."""
    core = text.partition("+")[0].partition("-")
    chunks = core[0].split(".")
    major_text = chunks[0] if len(chunks) > 0 else "0"
    minor_text = chunks[1] if len(chunks) > 1 else "0"
    patch_text = chunks[2] if len(chunks) > 2 else "0"
    prerelease = tuple(core[2].split(".")) if core[2] else ()
    wildcard = 0
    if major_text in ("*", "x", "X"):
        wildcard = 3
    elif minor_text in ("*", "x", "X"):
        wildcard = 2
    elif patch_text in ("*", "x", "X"):
        wildcard = 1
    major = 0 if wildcard == 3 else int(major_text)
    minor = 0 if wildcard >= 2 else int(minor_text)
    patch = 0 if wildcard >= 1 else int(patch_text)
    return _Bound(major=major, minor=minor, patch=patch, prerelease=prerelease, wildcard=wildcard)


def _wildcard_bounds(bound: _Bound) -> Tuple[Optional[Version], Optional[Version]]:
    """Expands a wildcard target into inclusive lower and exclusive upper bounds."""
    if bound.wildcard == 3:
        return (None, None)
    if bound.wildcard == 2:
        return (Version(bound.major, 0, 0), Version(bound.major + 1, 0, 0))
    return (Version(bound.major, bound.minor, 0), Version(bound.major, bound.minor + 1, 0))


def version_satisfies_text(version: Version, raw_text: str, include_prerelease: bool) -> bool:
    """Evaluates a candidate version against a range expression using precedence ordering."""
    text = raw_text.strip()
    if not text:
        return False
    for clause_text in text.split("||"):
        clause = clause_text.strip()
        if not clause:
            continue
        tokens: List[str] = []
        if " - " in clause:
            hyphen_parts = clause.split(" - ")
            if len(hyphen_parts) != 2:
                continue
            tokens = [">=" + hyphen_parts[0].strip(), "<=" + hyphen_parts[1].strip()]
        else:
            for piece in clause.split():
                if tokens and tokens[-1] in ("==", "=", "!=", ">=", ">", "<=", "<", "^", "~"):
                    tokens[-1] = tokens[-1] + piece
                else:
                    tokens.append(piece)
        clause_ok = True
        anchors: List[Tuple[int, int, int]] = []
        for token in tokens:
            operator = ""
            target = token
            for candidate_op in ("==", "!=", ">=", "<=", ">", "<", "=", "^", "~"):
                if token.startswith(candidate_op):
                    operator = candidate_op
                    target = token[len(candidate_op):]
                    break
            bound = _parse_bound(target)
            anchor = Version(bound.major, bound.minor, bound.patch, bound.prerelease)
            if bound.prerelease:
                anchors.append((bound.major, bound.minor, bound.patch))
            if bound.wildcard != 0:
                wildcard_lower, wildcard_upper = _wildcard_bounds(bound)
                if operator in ("", "=", "=="):
                    if wildcard_lower is not None and compare_versions(version, wildcard_lower) < 0:
                        clause_ok = False
                    if wildcard_upper is not None and compare_versions(version, wildcard_upper) >= 0:
                        clause_ok = False
                elif operator == "!=":
                    inside = True
                    if wildcard_lower is not None and compare_versions(version, wildcard_lower) < 0:
                        inside = False
                    if wildcard_upper is not None and compare_versions(version, wildcard_upper) >= 0:
                        inside = False
                    if inside:
                        clause_ok = False
                elif operator == ">=":
                    if wildcard_lower is not None and compare_versions(version, wildcard_lower) < 0:
                        clause_ok = False
                elif operator == ">":
                    if wildcard_upper is None or compare_versions(version, wildcard_upper) < 0:
                        clause_ok = False
                elif operator == "<=":
                    if wildcard_upper is not None and compare_versions(version, wildcard_upper) >= 0:
                        clause_ok = False
                elif operator == "<":
                    if wildcard_lower is None or compare_versions(version, wildcard_lower) >= 0:
                        clause_ok = False
                elif operator == "^":
                    if bound.wildcard != 3:
                        caret_lower = wildcard_lower if wildcard_lower is not None else Version(bound.major, 0, 0)
                        if bound.wildcard == 2:
                            caret_upper = Version(bound.major + 1, 0, 0)
                        elif bound.wildcard == 1:
                            if bound.major > 0:
                                caret_upper = Version(bound.major + 1, 0, 0)
                            else:
                                caret_upper = Version(0, bound.minor + 1, 0)
                        elif bound.major > 0:
                            caret_upper = Version(bound.major + 1, 0, 0)
                        elif bound.minor > 0:
                            caret_upper = Version(0, bound.minor + 1, 0)
                        else:
                            caret_upper = Version(0, 0, 1)
                        if compare_versions(version, caret_lower) < 0 or compare_versions(version, caret_upper) >= 0:
                            clause_ok = False
                elif operator == "~":
                    if bound.wildcard != 3:
                        tilde_lower = wildcard_lower if wildcard_lower is not None else Version(bound.major, 0, 0)
                        if bound.wildcard == 2:
                            tilde_upper = Version(bound.major + 1, 0, 0)
                        else:
                            tilde_upper = Version(bound.major, bound.minor + 1, 0)
                        if compare_versions(version, tilde_lower) < 0 or compare_versions(version, tilde_upper) >= 0:
                            clause_ok = False
            else:
                if operator in ("", "=", "=="):
                    if compare_versions(version, anchor) != 0:
                        clause_ok = False
                elif operator == "!=":
                    if compare_versions(version, anchor) == 0:
                        clause_ok = False
                elif operator == "^":
                    if bound.major > 0:
                        caret_upper = Version(bound.major + 1, 0, 0)
                    elif bound.minor > 0:
                        caret_upper = Version(0, bound.minor + 1, 0)
                    else:
                        caret_upper = Version(0, 0, bound.patch + 1)
                    if compare_versions(version, anchor) < 0 or compare_versions(version, caret_upper) >= 0:
                        clause_ok = False
                elif operator == "~":
                    tilde_upper = Version(bound.major, bound.minor + 1, 0)
                    if compare_versions(version, anchor) < 0 or compare_versions(version, tilde_upper) >= 0:
                        clause_ok = False
                elif operator == ">=":
                    if compare_versions(version, anchor) < 0:
                        clause_ok = False
                elif operator == ">":
                    if compare_versions(version, anchor) <= 0:
                        clause_ok = False
                elif operator == "<=":
                    if compare_versions(version, anchor) > 0:
                        clause_ok = False
                elif operator == "<":
                    if compare_versions(version, anchor) >= 0:
                        clause_ok = False
        if clause_ok:
            if not version.is_prerelease or include_prerelease:
                return True
            if (version.major, version.minor, version.patch) in anchors:
                return True
    return False


_OPERATORS: Tuple[str, ...] = ("==", "!=", ">=", "<=", ">", "<", "=", "^", "~")


def _split_tokens(clause: str) -> List[str]:
    """Splits a clause into comparator tokens, rejoining space-separated operators."""
    tokens: List[str] = []
    for piece in clause.split():
        if tokens and tokens[-1] in _OPERATORS:
            tokens[-1] = tokens[-1] + piece
        else:
            tokens.append(piece)
    return tokens


def _validate_target_text(target: str, raw_range: str) -> None:
    """Validates a comparator target, rejecting bare partials that lack wildcards."""
    core = target.partition("+")[0].partition("-")
    chunks = core[0].split(".")
    has_wildcard = False
    for chunk in chunks:
        if chunk in ("*", "x", "X"):
            has_wildcard = True
    if len(chunks) > 3 or (len(chunks) < 3 and not has_wildcard):
        raise InvalidRangeError(message="Invalid range: " + raw_range, raw_range=raw_range)
    for chunk in chunks:
        if chunk in ("*", "x", "X"):
            continue
        if not chunk.isdigit():
            raise InvalidRangeError(message="Invalid range: " + raw_range, raw_range=raw_range)


def validate_range_text(text: str) -> str:
    """Validates a range expression, returning its trimmed text or raising InvalidRangeError."""
    trimmed = text.strip()
    if not trimmed:
        raise InvalidRangeError(message="Invalid range: empty expression", raw_range=text)
    if "," in trimmed:
        raise InvalidRangeError(message="Invalid range: comma delimiter", raw_range=text)
    for clause_text in trimmed.split("||"):
        clause = clause_text.strip()
        if not clause:
            raise InvalidRangeError(message="Invalid range: empty clause", raw_range=text)
        if " - " in clause:
            hyphen_parts = clause.split(" - ")
            if len(hyphen_parts) != 2:
                raise InvalidRangeError(message="Invalid range: malformed hyphen", raw_range=text)
            _validate_target_text(hyphen_parts[0].strip(), text)
            _validate_target_text(hyphen_parts[1].strip(), text)
            continue
        tokens = _split_tokens(clause)
        if not tokens:
            raise InvalidRangeError(message="Invalid range: empty clause", raw_range=text)
        for token in tokens:
            target = token
            for candidate_op in _OPERATORS:
                if token.startswith(candidate_op):
                    target = token[len(candidate_op):]
                    break
            if not target:
                raise InvalidRangeError(message="Invalid range: missing target", raw_range=text)
            _validate_target_text(target, text)
    return trimmed


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverRangeState:
    """Canonical model state for range parsing and matching operations."""
    initialized: bool = True
    parsed_ranges: List[VersionRange] = field(default_factory=list)
    satisfaction_checks: int = 0


class SemverRangeStateMachine(StateMachine[SemverRangeState]):
    """Unified Pretense state machine modeling the RangeEngine protocol."""

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
        require_arg(text, Domain.sampled_from(RANGE_SAMPLES))
        fake_return = VersionRange(raw_text=validate_range_text(text))
        ret = make_return_value(fake_return)
        self.state.parsed_ranges.append(fake_return)
        assert ret == fake_return
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.type(Version), preferred=PREFERRED_VERSIONS)
        require_arg(range_constraint, Domain.sampled_from(RANGE_CONSTRAINTS))
        require_arg(include_prerelease, Domain.boolean())
        fake_return = version_satisfies_text(version, range_constraint.raw_text, include_prerelease)
        ret = make_return_value(fake_return)
        self.state.satisfaction_checks += 1
        assert ret == fake_return
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed the model state so operations become available during fuzzing."""
        self.state.initialized = True


proto = SemverRangeStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverRange = synthesize_fake(SemverRangeStateMachine)


def make_semver_range_fake(state: Optional[SemverRangeState] = None) -> RangeEngine:
    """Synthesizes a fake RangeEngine backed by the version range state machine."""
    return FakeSemverRange(state=state or SemverRangeState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverRangeFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all declared transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_range_fake()
        self.sm = SemverRangeStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every transition and seeding transition on the fake."""
        self.sm.seed_initial()
        parsed = self.fake.parse_range("^1.2.3")
        assert parsed.raw_text == "^1.2.3"
        assert self.fake.satisfies(Version(1, 2, 3), parsed, False) is True
        assert self.fake.satisfies(Version(1, 5, 0), parsed, False) is True
        assert self.fake.satisfies(Version(2, 0, 0), parsed, False) is False
        exact = self.fake.parse_range("1.2.3")
        assert self.fake.satisfies(Version(0, 0, 1), exact, True) is False
        assert self.fake.satisfies(Version(1, 2, 3), exact, False) is True
        minor = self.fake.parse_range("1.2.x")
        assert self.fake.satisfies(Version(1, 2, 9), minor, False) is True
        assert self.fake.satisfies(Version(1, 3, 0), minor, False) is False
        stable = self.fake.parse_range(">=1.0.0")
        assert self.fake.satisfies(Version(1, 0, 0, ("alpha",)), stable, False) is False
        assert self.fake.satisfies(Version(1, 0, 0, ("alpha",)), stable, True) is False
        assert self.fake.satisfies(Version(1, 1, 0, ("beta",)), stable, True) is True
        bounded = self.fake.parse_range(">=1.0.0 <2.0.0")
        assert self.fake.satisfies(Version(2, 0, 0), bounded, False) is False
        assert self.fake.satisfies(Version(1, 9, 9), bounded, False) is True


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverRangeState,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:37:36Z
# LAST_CHANGED: 2026-11-05T17:37:36Z
# CHANGE: Fix zero-major caret expansion over a patch wildcard and admit the forms: for wildcard form M.m.x (bound.wildcard == 1) the caret upper now bumps the minor when the major is zero (^0.2.x -> >=0.2.0 <0.3.0, ^0.0.x -> >=0.0.0 <0.1.0) while non-zero major still bumps the major (^1.2.x -> <2.0.0). Added ^0.2.x and ^0.0.x to RANGE_SAMPLES/RANGE_CONSTRAINTS so deterministic scenarios can exercise these branches.
# --- END AUTOFAB METADATA ---
