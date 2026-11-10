# === File: dependency_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DependencySolver."""

from __future__ import annotations

from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple, cast
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
from benchmark_2.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
    FakeDependencySolver,
    make_dependency_solver_fake,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_2.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
)
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver_impl import (
    __initialize__ as _ds_initialize,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import (
    __initialize__ as _sr_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine observing the real repository and solver."""

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert ret is None
        assert target.has_package(release.name)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret: List[PackageRelease] = call_target(target.get_releases(name))
        assert isinstance(ret, list)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret: bool = call_target(target.has_package(name))
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret: Set[str] = call_target(target.all_packages())
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret: ResolutionOutcome = call_target(target.resolve(root_dependencies))
        assert isinstance(ret, ResolutionOutcome)
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
            singletons={
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )
        self.checked_packagerepository = self.sm.as_checked(
            PackageRepository, self.packagerepository
        )
        self.checked_dependencysolver = self.sm.as_checked(
            DependencySolver, self.dependencysolver
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_package_repository_conformance(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(PackageRelease(name="alpha", version=Version(1, 0, 0)))
        repository.register_package(
            PackageRelease(
                name="alpha",
                version=Version(2, 0, 0),
                dependencies=(
                    PackageDependency(
                        name="beta",
                        range_constraint=VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        repository.register_package(PackageRelease(name="beta", version=Version(1, 5, 0)))
        self.assertTrue(repository.has_package("alpha"))
        self.assertTrue(repository.has_package("beta"))
        self.assertFalse(repository.has_package("gamma"))
        self.assertEqual(repository.all_packages(), {"alpha", "beta"})
        releases = repository.get_releases("alpha")
        self.assertEqual(len(releases), 2)
        self.assertEqual(releases[0].version, Version(2, 0, 0))
        self.assertEqual(releases[1].version, Version(1, 0, 0))

    def test_dependency_resolution_conformance(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(PackageRelease(name="beta", version=Version(1, 5, 0)))
        repository.register_package(PackageRelease(name="alpha", version=Version(1, 0, 0)))
        repository.register_package(
            PackageRelease(
                name="alpha",
                version=Version(2, 0, 0),
                dependencies=(
                    PackageDependency(
                        name="beta",
                        range_constraint=VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        solver = self.checked_dependencysolver
        outcome = solver.resolve(
            [
                PackageDependency(
                    name="alpha",
                    range_constraint=VersionRange(raw_text=">=1.0.0"),
                ),
            ]
        )
        self.assertIn("alpha", outcome.selected_versions)
        self.assertEqual(outcome.selected_versions.get("alpha"), Version(2, 0, 0))
        self.assertIn("beta", outcome.selected_versions)
        self.assertEqual(outcome.selected_versions.get("beta"), Version(1, 5, 0))
        self.assertGreaterEqual(len(outcome.derivation_steps), 1)

    def test_backtracking_resolution_conformance(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(PackageRelease(name="alpha", version=Version(1, 0, 0)))
        repository.register_package(
            PackageRelease(
                name="alpha",
                version=Version(2, 0, 0),
                dependencies=(
                    PackageDependency(
                        name="beta",
                        range_constraint=VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        solver = self.checked_dependencysolver
        outcome = solver.resolve(
            [
                PackageDependency(
                    name="alpha",
                    range_constraint=VersionRange(raw_text=">=1.0.0"),
                ),
            ]
        )
        self.assertEqual(outcome.selected_versions.get("alpha"), Version(1, 0, 0))
        self.assertEqual(len(outcome.derivation_steps), 1)

    def test_unregistered_dependency_conflict(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(
            PackageRelease(
                name="gamma",
                version=Version(1, 0, 0),
                dependencies=(
                    PackageDependency(
                        name="delta",
                        range_constraint=VersionRange(raw_text=">=2.0.0"),
                    ),
                ),
            )
        )
        solver = self.checked_dependencysolver
        with self.assertRaises(ResolutionConflictError) as context:
            solver.resolve(
                [
                    PackageDependency(
                        name="gamma",
                        range_constraint=VersionRange(raw_text=">=1.0.0"),
                    ),
                ]
            )
        error = context.exception
        self.assertIsInstance(error, ResolutionConflictError)
        self.assertIn("gamma", error.conflicting_packages)
        self.assertIn("delta", error.conflicting_packages)
        self.assertTrue(error.explanation)

    def test_mutually_incompatible_selection_conflict(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(PackageRelease(name="delta", version=Version(1, 0, 0)))
        repository.register_package(
            PackageRelease(
                name="gamma",
                version=Version(1, 0, 0),
                dependencies=(
                    PackageDependency(
                        name="delta",
                        range_constraint=VersionRange(raw_text=">=2.0.0"),
                    ),
                ),
            )
        )
        solver = self.checked_dependencysolver
        with self.assertRaises(ResolutionConflictError) as context:
            solver.resolve(
                [
                    PackageDependency(
                        name="gamma",
                        range_constraint=VersionRange(raw_text=">=1.0.0"),
                    ),
                    PackageDependency(
                        name="delta",
                        range_constraint=VersionRange(raw_text=">=1.0.0"),
                    ),
                ]
            )
        error = context.exception
        self.assertIsInstance(error, ResolutionConflictError)
        self.assertIn("gamma", error.conflicting_packages)
        self.assertIn("delta", error.conflicting_packages)
        self.assertTrue(error.explanation)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================


class DependencySolverSUT:
    """Aggregate SUT exposing repository and solver services for fuzzing."""

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
# LAST_CLEANED: 2026-11-07T04:09:21Z
# LAST_CHANGED: 2026-11-07T04:06:54Z
# CHANGE: Add deterministic resolution-failure scenarios through the public registration/resolution boundary: (1) gamma depending on an unregistered delta >=2.0.0 exhausts every candidate branch and raises ResolutionConflictError, asserting the structured conflicting_packages tuple contains gamma and delta and a non-empty explanation; (2) a repository where delta 1.0.0 is selected by one requirement while a gamma release demands delta >=2.0.0 forces a forward-check conflict and full branch exhaustion, again raising ResolutionConflictError with the structured conflicting-package names and explanation attributes. No assertions on diagnostic wording.
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T04:07:25Z
# PRETENSE_QA_AUDIT: 2026-11-07T04:07:05Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DependencySolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Tuple, cast
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
from benchmark_2.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_2.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_2.parts.semver_solver_multi.pretense.semver_range_pretense import range_satisfies


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================

# Representative immutable records used by the model and by caller input domains.
SAMPLE_VERSION: Version = Version(1, 0, 0)
SAMPLE_RANGE: VersionRange = VersionRange(raw_text=">=1.0.0")
SAMPLE_DEPENDENCY: PackageDependency = PackageDependency(
    name="alpha", range_constraint=SAMPLE_RANGE
)
TRANSITIVE_DEPENDENCY: PackageDependency = PackageDependency(
    name="beta", range_constraint=SAMPLE_RANGE
)
GAMMA_DEPENDENCY: PackageDependency = PackageDependency(
    name="gamma", range_constraint=SAMPLE_RANGE
)
DELTA_DEPENDENCY: PackageDependency = PackageDependency(
    name="delta", range_constraint=SAMPLE_RANGE
)
STRICT_DELTA_DEPENDENCY: PackageDependency = PackageDependency(
    name="delta", range_constraint=VersionRange(raw_text=">=2.0.0")
)
SAMPLE_RELEASES: List[PackageRelease] = [
    PackageRelease(name="alpha", version=Version(1, 0, 0)),
    PackageRelease(
        name="alpha",
        version=Version(2, 0, 0),
        dependencies=(TRANSITIVE_DEPENDENCY,),
    ),
    PackageRelease(name="beta", version=Version(1, 5, 0)),
    PackageRelease(name="beta", version=Version(2, 1, 0)),
    PackageRelease(name="delta", version=Version(1, 0, 0)),
    PackageRelease(
        name="gamma",
        version=Version(1, 0, 0),
        dependencies=(STRICT_DELTA_DEPENDENCY,),
    ),
]
SAMPLE_DEPENDENCIES: List[PackageDependency] = [
    SAMPLE_DEPENDENCY,
    TRANSITIVE_DEPENDENCY,
    GAMMA_DEPENDENCY,
    DELTA_DEPENDENCY,
]

ConstraintEntry = Tuple[str, VersionRange]


def _format_version_text(version: Version) -> str:
    """Formats a version into the canonical spelling used by decision steps."""
    text = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        text = f"{text}-{'.'.join(version.prerelease)}"
    if version.build:
        text = f"{text}+{'.'.join(version.build)}"
    return text


def _viable_releases(
    name: str,
    accumulated_constraints: Dict[str, List[ConstraintEntry]],
    packages: Dict[str, Tuple[PackageRelease, ...]],
) -> List[PackageRelease]:
    """Determines the candidate releases satisfying every accumulated constraint."""
    viable: List[PackageRelease] = []
    for release in packages.get(name, ()):
        compatible = True
        for _source, range_constraint in accumulated_constraints.get(name, []):
            if not range_satisfies(release.version, range_constraint.raw_text, False):
                compatible = False
        if compatible:
            viable.append(release)
    return viable


def _select_minimum_remaining_values(
    unassigned: List[str],
    candidates_map: Dict[str, List[PackageRelease]],
) -> str:
    """Selects the unassigned package with fewest candidates, ties broken lexically."""
    selected = unassigned[0]
    selected_count = len(candidates_map[selected])
    for name in unassigned[1:]:
        candidate_count = len(candidates_map[name])
        if candidate_count < selected_count:
            selected = name
            selected_count = candidate_count
        elif candidate_count == selected_count and name < selected:
            selected = name
            selected_count = candidate_count
    return selected


def _search_assignment(
    accumulated_constraints: Dict[str, List[ConstraintEntry]],
    assignment: Dict[str, PackageRelease],
    conflict_trail: List[str],
    derivation_steps: List[str],
    packages: Dict[str, Tuple[PackageRelease, ...]],
) -> bool:
    """Performs MRV-ordered depth-first backtracking over accumulated constraints."""
    unassigned = [name for name in accumulated_constraints if name not in assignment]
    if not unassigned:
        return True
    candidates_map: Dict[str, List[PackageRelease]] = {}
    for name in unassigned:
        candidates_map[name] = _viable_releases(name, accumulated_constraints, packages)
    selected_pkg = _select_minimum_remaining_values(unassigned, candidates_map)
    candidates = candidates_map[selected_pkg]
    if not candidates:
        requesters = [source for source, _range in accumulated_constraints[selected_pkg]]
        conflict_trail.append(
            f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
        )
        return False
    for candidate in candidates:
        assignment[selected_pkg] = candidate
        derivation_steps.append(
            f"Assign '{selected_pkg}' to {_format_version_text(candidate.version)}"
        )
        conflict_detected = False
        newly_added: List[Tuple[str, ConstraintEntry]] = []
        for dependency in candidate.dependencies:
            if dependency.name in assignment:
                satisfied = range_satisfies(
                    assignment[dependency.name].version,
                    dependency.range_constraint.raw_text,
                    False,
                )
                if not satisfied:
                    conflict_detected = True
                    conflict_trail.append(
                        f"Conflict: '{selected_pkg}' requires {dependency.name} "
                        f"{dependency.range_constraint.raw_text}"
                    )
                    break
            else:
                constraint_entry: ConstraintEntry = (selected_pkg, dependency.range_constraint)
                accumulated_constraints.setdefault(dependency.name, []).append(constraint_entry)
                newly_added.append((dependency.name, constraint_entry))
        if not conflict_detected and _search_assignment(
            accumulated_constraints, assignment, conflict_trail, derivation_steps, packages
        ):
            return True
        for name, constraint_entry in newly_added:
            accumulated_constraints[name].remove(constraint_entry)
            if not accumulated_constraints[name]:
                del accumulated_constraints[name]
        del assignment[selected_pkg]
        derivation_steps.pop()
    return False


def solve_search(
    root_dependencies: Collection[PackageDependency],
    packages: Dict[str, Tuple[PackageRelease, ...]],
) -> Optional[ResolutionOutcome]:
    """Computes a mutually compatible assignment, or None when every branch fails."""
    accumulated_constraints: Dict[str, List[ConstraintEntry]] = {}
    for dependency in root_dependencies:
        accumulated_constraints.setdefault(dependency.name, []).append(
            ("root", dependency.range_constraint)
        )
    assignment: Dict[str, PackageRelease] = {}
    conflict_trail: List[str] = []
    derivation_steps: List[str] = []
    if not _search_assignment(
        accumulated_constraints, assignment, conflict_trail, derivation_steps, packages
    ):
        return None
    selected_versions = {
        name: release.version for name, release in assignment.items()
    }
    return ResolutionOutcome(
        selected_versions=selected_versions,
        derivation_steps=tuple(derivation_steps),
    )


@dataclass
class DependencySolverState:
    """Model state for package repository registration and dependency resolution."""

    packages: Dict[str, Tuple[PackageRelease, ...]] = field(default_factory=dict)
    resolution_count: int = 0


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """State machine modeling PackageRepository and DependencySolver operations 1:1."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DependencySolverState(), singletons=singletons)

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require_arg(release, Domain.sampled_from(SAMPLE_RELEASES))
        updated: List[PackageRelease] = []
        placed = False
        for candidate in self.state.packages.get(release.name, ()):
            if not placed and (
                (candidate.version.major, candidate.version.minor, candidate.version.patch)
                < (release.version.major, release.version.minor, release.version.patch)
            ):
                updated.append(release)
                placed = True
            updated.append(candidate)
        if not placed:
            updated.append(release)
        self.state.packages[release.name] = tuple(updated)
        ret: None = make_return_value(None)
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require_arg(name, Domain.type(str), preferred=["alpha"])
        if name not in self.state.packages:
            missing: List[PackageRelease] = []
            with raises(PackageNotFoundError):
                missing = make_return_value([])
            return missing
        releases = list(self.state.packages[name])
        ret: List[PackageRelease] = make_return_value(releases)
        assert ret == releases
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require_arg(name, Domain.type(str), preferred=["alpha"])
        fake_ret = name in self.state.packages
        ret: bool = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> set[str]:
        fake_ret = set(self.state.packages.keys())
        ret: set[str] = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require_arg(
            root_dependencies,
            cast(
                "Domain[Collection[PackageDependency]]",
                Domain.list_of(Domain.sampled_from(SAMPLE_DEPENDENCIES)),
            ),
        )
        resolved = solve_search(root_dependencies, self.state.packages)
        if resolved is None:
            conflicted: ResolutionOutcome = ResolutionOutcome(
                selected_versions={}, derivation_steps=()
            )
            with raises(ResolutionConflictError):
                conflicted = make_return_value(conflicted)
            return conflicted
        ret: ResolutionOutcome = make_return_value(resolved)
        self.state.resolution_count += 1
        assert ret == resolved
        return ret

    @transition.seeding
    def seed_blank_session(self) -> None:
        """Transitions model state back to a blank registration ledger baseline."""
        self.state.packages.clear()
        self.state.resolution_count = 0


proto = DependencySolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fake(state: Optional[DependencySolverState] = None) -> Any:
    """Synthesizes a fake covering the PackageRepository and DependencySolver interfaces."""
    return FakeDependencySolver(state=state or DependencySolverState())


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageRepository, DependencySolver]:
    """Synthesizes fake component services sharing one model state."""
    fake = make_dependency_solver_fake(state)
    return (fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.repository_fake, self.solver_fake = make_dependency_solver_fakes()
        self.sm = DependencySolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition against the synthesized fake."""
        release = SAMPLE_RELEASES[0]
        self.repository_fake.register_package(release)
        self.assertTrue(self.repository_fake.has_package(release.name))
        self.assertFalse(self.repository_fake.has_package("gamma"))
        self.assertEqual(self.repository_fake.all_packages(), {release.name})
        self.assertEqual(self.repository_fake.get_releases(release.name), [release])
        outcome = self.solver_fake.resolve([SAMPLE_DEPENDENCIES[0]])
        self.assertEqual(outcome.selected_versions[SAMPLE_DEPENDENCIES[0].name], SAMPLE_VERSION)

    def test_seeding_transitions(self) -> None:
        """Exercises every declared seeding transition."""
        self.sm.seed_blank_session()
        self.assertEqual(self.sm.all_packages(), set())


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T04:09:18Z
# LAST_CHANGED: 2026-11-07T04:06:50Z
# CHANGE: Extend the sampled registration/resolution domain with the conflicting repositories used by deterministic failure scenarios: a delta 1.0.0 release, a gamma 1.0.0 release strictly depending on delta >=2.0.0, and gamma/delta root requirement samples.
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
from benchmark_2.parts.semver_solver_multi.pretense.semver_core_pretense import (
    FakeSemverCore,
    SemverCoreState,
    SemverCoreStateMachine,
    make_semver_core_fake,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import VersionEngine
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver_impl import (
    __initialize__ as _ds_initialize,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import (
    __initialize__ as _sr_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine observing the real SemVer engine and version record."""

    @transition(Version.format)
    def format(self) -> str:
        target: Version = sut(Version)
        ret: str = call_target(target.format())
        assert isinstance(ret, str)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        target: Version = sut(Version)
        ret: bool = call_target(target.is_prerelease)
        assert isinstance(ret, bool)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret: Version = call_target(target.parse_version(text))
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
    ) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret: int = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        if v1 == v2:
            assert ret == 0
        if v1.major != v2.major:
            same_sign = (ret > 0) == (v1.major > v2.major)
            assert same_sign
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
        self.version_real = Version(1, 2, 3, ("alpha", "1"), ("build", "5"))
        self.sm = SemverCoreImplPseudoStateMachine(
            singletons={VersionEngine: self.real, Version: self.version_real}
        )
        self.checked = self.sm.as_checked(VersionEngine, self.real)
        self.checked_version = self.sm.as_checked(Version, self.version_real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_conformance(self) -> None:
        parsed = self.checked.parse_version("1.2.3")
        self.assertIsInstance(parsed, Version)
        self.assertEqual(parsed.major, 1)
        self.assertEqual(parsed.minor, 2)
        self.assertEqual(parsed.patch, 3)
        self.assertEqual(parsed.prerelease, ())
        self.assertEqual(parsed.build, ())
        self.assertFalse(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "1.2.3")

        prerelease = self.checked.parse_version("2.0.0-rc.1+build.5")
        self.assertEqual(prerelease.major, 2)
        self.assertEqual(prerelease.minor, 0)
        self.assertEqual(prerelease.patch, 0)
        self.assertEqual(prerelease.prerelease, ("rc", "1"))
        self.assertEqual(prerelease.build, ("build", "5"))
        self.assertTrue(prerelease.is_prerelease)
        self.assertEqual(prerelease.format(), "2.0.0-rc.1+build.5")

    def test_compare_precedence_conformance(self) -> None:
        normal = self.checked.parse_version("1.2.3")
        earlier = self.checked.parse_version("1.2.2")
        later = self.checked.parse_version("1.3.0")
        self.assertLess(self.checked.compare_precedence(earlier, normal), 0)
        self.assertGreater(self.checked.compare_precedence(later, normal), 0)
        self.assertEqual(self.checked.compare_precedence(normal, normal), 0)

    def test_prerelease_precedence_conformance(self) -> None:
        release = self.checked.parse_version("1.0.0")
        prerelease = self.checked.parse_version("1.0.0-alpha.1")
        self.assertGreater(self.checked.compare_precedence(release, prerelease), 0)
        self.assertLess(self.checked.compare_precedence(prerelease, release), 0)

    def test_build_metadata_is_ignored_by_precedence(self) -> None:
        plain = self.checked.parse_version("1.0.0")
        annotated = self.checked.parse_version("1.0.0+build.7")
        self.assertEqual(self.checked.compare_precedence(plain, annotated), 0)
        self.assertEqual(annotated.build, ("build", "7"))
        self.assertFalse(annotated.is_prerelease)

    def test_version_record_conformance(self) -> None:
        self.assertEqual(self.checked_version.format(), "1.2.3-alpha.1+build.5")
        self.assertTrue(self.checked_version.is_prerelease)

    def test_leading_zero_version_rejection(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("01.2.3")
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("1.02.3")
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("1.2.03")
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("1.2.3-01")

    def test_malformed_version_grammar_rejection(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("1.2")
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("1.2.3.4")
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("1.2.3-")
        recovered = self.checked.parse_version("1.2.3")
        self.assertEqual(self.checked.compare_precedence(recovered, recovered), 0)

    def test_prerelease_segment_precedence_conformance(self) -> None:
        numeric_one = Version(1, 0, 0, ("1",))
        numeric_two = Version(1, 0, 0, ("2",))
        numeric_ten = Version(1, 0, 0, ("10",))
        alphanumeric = Version(1, 0, 0, ("alpha",))
        later_alphanumeric = Version(1, 0, 0, ("beta",))
        longer = Version(1, 0, 0, ("alpha", "1"))
        built_one = Version(1, 0, 0, ("alpha",), ("build", "1"))
        built_two = Version(1, 0, 0, ("alpha",), ("build", "2"))
        self.assertLess(self.checked.compare_precedence(numeric_two, numeric_ten), 0)
        self.assertLess(self.checked.compare_precedence(numeric_one, alphanumeric), 0)
        self.assertLess(self.checked.compare_precedence(alphanumeric, later_alphanumeric), 0)
        self.assertLess(self.checked.compare_precedence(alphanumeric, longer), 0)
        self.assertEqual(self.checked.compare_precedence(built_one, built_two), 0)
        self.assertGreater(self.checked.compare_precedence(longer, alphanumeric), 0)
        self.assertGreater(self.checked.compare_precedence(alphanumeric, numeric_one), 0)
        self.assertLess(self.checked.compare_precedence(numeric_one, alphanumeric), 0)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================


class SemverCoreSUT:
    """Aggregate SUT exposing the version record and engine services for fuzzing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.version = self.versionengine.parse_version("1.2.3-alpha.1+build.5")
        self.__dict__["_services"] = (self.version, self.versionengine)

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
# LAST_CLEANED: 2026-11-07T04:01:38Z
# LAST_CHANGED: 2026-11-07T03:59:01Z
# CHANGE: Add the mirrored numeric-below-alphanumeric prerelease precedence scenario: compare the alphanumeric-bearing version against the numeric-bearing version (identical major/minor/patch) with both assertGreater(alpha, 1) and assertLess(1, alpha), establishing the contracted numeric-ranking symmetry in both argument orders.
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T04:01:38Z
# PRETENSE_QA_AUDIT: 2026-11-07T04:01:19Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverCore."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
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
from benchmark_2.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
    VersionEngine,
)


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================

# Version spellings sampled by the caller precondition contract: valid spellings
# exercise parsing and malformed spellings exercise the contracted
# InvalidVersionError grammar/leading-zero violation branch.
SAMPLE_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "1.0.0",
    "1.0.0-alpha.1",
    "1.0.0+build.7",
    "1.2.2",
    "1.2.3",
    "1.2.3-alpha.1",
    "1.3.0",
    "2.0.0",
    "2.0.0-rc.1+build.5",
    "01.2.3",
    "1.02.3",
    "1.2.03",
    "1.2.3-01",
    "1.2",
    "1.2.3.4",
    "1.2.3-",
)

# Representative immutable model values. State machine transitions project
# these rather than constructing target service records themselves.
REFERENCE_VERSION: Version = Version(1, 2, 3, ("alpha", "1"), ("build", "5"))
NORMAL_SAMPLE_VERSION: Version = Version(1, 0, 0)
PRERELEASE_SAMPLE_VERSION: Version = Version(1, 0, 0, ("rc", "1"))
HIGHER_SAMPLE_VERSION: Version = Version(2, 0, 0)
INVALID_VERSION_PLACEHOLDER: Version = Version(0, 0, 0)

REFERENCE_VERSIONS: List[Version] = [
    NORMAL_SAMPLE_VERSION,
    HIGHER_SAMPLE_VERSION,
    PRERELEASE_SAMPLE_VERSION,
    Version(1, 0, 0, ("1",)),
    Version(1, 0, 0, ("2",)),
    Version(1, 0, 0, ("10",)),
    Version(1, 0, 0, ("alpha",)),
    Version(1, 0, 0, ("alpha", "1")),
    Version(1, 0, 0, ("alpha",), ("build", "1")),
    Version(1, 0, 0, ("alpha",), ("build", "2")),
    Version(1, 0, 0, ("beta",)),
    Version(1, 0, 0, (), ("build", "7")),
    Version(1, 2, 2),
    Version(1, 2, 3),
    Version(1, 3, 0),
]


def _compare_prerelease(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Orders two prerelease identifier sequences under SemVer 2.0.0 rules."""
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    shared = min(len(left), len(right))
    for index in range(shared):
        left_part = left[index]
        right_part = right[index]
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            left_value = int(left_part)
            right_value = int(right_part)
            if left_value != right_value:
                return -1 if left_value < right_value else 1
        elif left_numeric:
            return -1
        elif right_numeric:
            return 1
        elif left_part != right_part:
            return -1 if left_part < right_part else 1
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def _compare_precedence(left: Version, right: Version) -> int:
    """Orders two versions by precedence, ignoring build metadata."""
    left_numbers = (left.major, left.minor, left.patch)
    right_numbers = (right.major, right.minor, right.patch)
    if left_numbers != right_numbers:
        return -1 if left_numbers < right_numbers else 1
    return _compare_prerelease(left.prerelease, right.prerelease)


def _parse_version_text(text: str) -> Version:
    """Parses a valid SemVer 2.0.0 spelling into the model version record."""
    literal = text.strip()
    core = literal
    build: Tuple[str, ...] = ()
    build_index = core.find("+")
    if build_index >= 0:
        build = tuple(core[build_index + 1 :].split("."))
        core = core[:build_index]
    prerelease: Tuple[str, ...] = ()
    prerelease_index = core.find("-")
    if prerelease_index >= 0:
        prerelease = tuple(core[prerelease_index + 1 :].split("."))
        core = core[:prerelease_index]
    components = core.split(".")
    return Version(int(components[0]), int(components[1]), int(components[2]), prerelease, build)


def _format_version(version: Version) -> str:
    """Formats a model version into its canonical SemVer 2.0.0 spelling."""
    text = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        text = f"{text}-{'.'.join(version.prerelease)}"
    if version.build:
        text = f"{text}+{'.'.join(version.build)}"
    return text


def _is_numeric_identifier(identifier: str) -> bool:
    """Checks a numeric identifier for digits and the no-leading-zero rule."""
    if not identifier or not identifier.isdigit():
        return False
    return identifier == "0" or not identifier.startswith("0")


def _is_identifier_character_valid(identifier: str) -> bool:
    """Checks that a prerelease/build identifier only uses permitted characters."""
    return bool(identifier) and all(character.isalnum() or character == "-" for character in identifier)


def _is_valid_version_text(text: str) -> bool:
    """Validates raw text against the SemVer 2.0.0 grammar contract."""
    if not text or text != text.strip():
        return False
    body = text
    build_index = body.find("+")
    if build_index >= 0:
        build = body[build_index + 1 :]
        body = body[:build_index]
        for identifier in build.split("."):
            if not _is_identifier_character_valid(identifier):
                return False
    prerelease_index = body.find("-")
    if prerelease_index >= 0:
        prerelease = body[prerelease_index + 1 :]
        body = body[:prerelease_index]
        for identifier in prerelease.split("."):
            if not _is_identifier_character_valid(identifier):
                return False
            if identifier.isdigit() and not _is_numeric_identifier(identifier):
                return False
    components = body.split(".")
    if len(components) != 3:
        return False
    for component in components:
        if not _is_numeric_identifier(component):
            return False
    return True


@dataclass
class SemverCoreState:
    """Model state for SemVer parsing, formatting, and precedence operations."""

    parsed_version_texts: List[str] = field(default_factory=list)
    formatted_texts: List[str] = field(default_factory=list)
    comparison_count: int = 0
    reference_version: Optional[Version] = None


class SemverCoreStateMachine(StateMachine[SemverCoreState]):
    """State machine modeling SemverCore operations 1:1 with the target interface."""

    def __init__(
        self,
        state: Optional[SemverCoreState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverCoreState(), singletons=singletons)

    @transition(Version.format)
    def format(self) -> str:
        reference = self.state.reference_version or REFERENCE_VERSION
        fake_ret = _format_version(reference)
        ret: str = make_return_value(fake_ret)
        self.state.formatted_texts.append(ret)
        assert ret == fake_ret
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        reference = self.state.reference_version or REFERENCE_VERSION
        fake_ret = len(reference.prerelease) > 0
        ret: bool = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require_arg(text, Domain.sampled_from(list(SAMPLE_VERSION_TEXTS)))
        if not _is_valid_version_text(text):
            invalid: Version = INVALID_VERSION_PLACEHOLDER
            with raises(InvalidVersionError):
                invalid = make_return_value(invalid)
            return invalid
        fake_ret = _parse_version_text(text)
        ret: Version = make_return_value(fake_ret)
        self.state.parsed_version_texts.append(text)
        assert ret == fake_ret
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require_arg(v1, Domain.sampled_from(REFERENCE_VERSIONS))
        require_arg(v2, Domain.sampled_from(REFERENCE_VERSIONS))
        fake_ret = _compare_precedence(v1, v2)
        ret: int = make_return_value(fake_ret)
        self.state.comparison_count += 1
        assert ret == fake_ret
        return ret

    @transition.seeding
    def seed_reference_version(self) -> None:
        """Transitions a blank model state into one carrying the reference version."""
        self.state.reference_version = REFERENCE_VERSION
        self.state.parsed_version_texts.clear()
        self.state.formatted_texts.clear()
        self.state.comparison_count = 0


proto = SemverCoreStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverCore = synthesize_fake(SemverCoreStateMachine)


def make_semver_core_fake(state: Optional[SemverCoreState] = None) -> Any:
    """Synthesizes a fake covering the Version and VersionEngine interfaces."""
    return FakeSemverCore(state=state or SemverCoreState())


def make_semver_core_fakes(
    state: Optional[SemverCoreState] = None,
) -> Tuple[Version, VersionEngine]:
    """Synthesizes fake component services sharing one model state."""
    fake = make_semver_core_fake(state)
    return (fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestSemverCoreFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.version_fake, self.engine_fake = make_semver_core_fakes()
        self.sm = SemverCoreStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition against the synthesized fake."""
        parsed = self.engine_fake.parse_version("1.2.3")
        self.assertEqual(parsed.major, 1)
        self.assertEqual(parsed.minor, 2)
        self.assertEqual(parsed.patch, 3)
        self.assertEqual(parsed.prerelease, ())
        decorated = self.engine_fake.parse_version("2.0.0-rc.1+build.5")
        self.assertEqual(decorated.prerelease, ("rc", "1"))
        self.assertEqual(decorated.build, ("build", "5"))
        self.assertLess(
            self.engine_fake.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)),
            0,
        )
        self.assertEqual(
            self.engine_fake.compare_precedence(Version(1, 0, 0), Version(1, 0, 0)),
            0,
        )
        self.assertGreater(
            self.engine_fake.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, ("alpha",))),
            0,
        )
        self.assertEqual(self.version_fake.format(), "1.2.3-alpha.1+build.5")
        self.assertTrue(self.version_fake.is_prerelease)

    def test_seeding_transitions(self) -> None:
        """Exercises every declared seeding transition."""
        self.sm.seed_reference_version()
        self.assertEqual(self.sm.format(), "1.2.3-alpha.1+build.5")
        self.assertTrue(self.sm.is_prerelease())


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverCoreState,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:56:25Z
# LAST_CHANGED: 2026-11-07T03:56:25Z
# CHANGE: Model the contracted InvalidVersionError branch: parse_version now validates the SemVer 2.0.0 grammar (numeric leading-zero rule, three numeric identifiers, prerelease/build identifier charset and numeric leading zeros) and models a raises(InvalidVersionError) pivot for malformed spellings; the caller domain samples malformed and leading-zero spellings in addition to valid ones. Precedence reference values now cover numeric-numeric magnitude, numeric-below-alphanumeric, alphanumeric ASCII ordering, mixed-length, and build-metadata-differing prerelease pairs.
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
from benchmark_2.parts.semver_solver_multi.pretense.semver_range_pretense import (
    FakeSemverRange,
    SemverRangeState,
    SemverRangeStateMachine,
    make_semver_range_fake,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_2.parts.semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import RangeEngine
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver_impl import (
    __initialize__ as _ds_initialize,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import (
    __initialize__ as _sr_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class SemverRangeImplPseudoStateMachine(SemverRangeStateMachine):
    """Implementation pseudo-state machine observing the real range engine."""

    @transition(RangeEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        target: RangeEngine = sut(RangeEngine)
        ret: VersionRange = call_target(target.parse_range(text))
        assert isinstance(ret, VersionRange)
        assert ret.raw_text == text.strip()
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: RangeEngine = sut(RangeEngine)
        matched: bool = call_target(
            target.satisfies(version, range_constraint, include_prerelease)
        )
        assert isinstance(matched, bool)
        return matched


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

    def test_parse_range_conformance(self) -> None:
        caret = self.checked.parse_range("^1.2.3")
        self.assertIsInstance(caret, VersionRange)
        self.assertEqual(caret.raw_text, "^1.2.3")
        trimmed = self.checked.parse_range("  >=1.0.0 <2.0.0  ")
        self.assertEqual(trimmed.raw_text, ">=1.0.0 <2.0.0")
        union = self.checked.parse_range(">=1.0.0 <2.0.0 || >=3.0.0")
        self.assertEqual(union.raw_text, ">=1.0.0 <2.0.0 || >=3.0.0")

    def test_satisfies_comparators(self) -> None:
        bounded = self.checked.parse_range(">=1.0.0 <2.0.0")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), bounded, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), bounded, False))
        self.assertFalse(self.checked.satisfies(Version(0, 9, 9), bounded, False))

    def test_satisfies_caret_and_tilde(self) -> None:
        caret = self.checked.parse_range("^1.2.3")
        self.assertTrue(self.checked.satisfies(Version(1, 9, 0), caret, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), caret, False))
        tilde = self.checked.parse_range("~1.2.3")
        self.assertTrue(self.checked.satisfies(Version(1, 2, 9), tilde, False))
        self.assertFalse(self.checked.satisfies(Version(1, 3, 0), tilde, False))

    def test_satisfies_wildcard_hyphen_and_union(self) -> None:
        wildcard = self.checked.parse_range("1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 4, 2), wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), wildcard, False))
        hyphen = self.checked.parse_range("1.0.0 - 2.x")
        self.assertTrue(self.checked.satisfies(Version(2, 5, 0), hyphen, False))
        self.assertFalse(self.checked.satisfies(Version(3, 0, 0), hyphen, False))
        union = self.checked.parse_range(">=1.0.0 <2.0.0 || >=3.0.0")
        self.assertTrue(self.checked.satisfies(Version(3, 1, 0), union, False))
        self.assertFalse(self.checked.satisfies(Version(2, 5, 0), union, False))

    def test_satisfies_prerelease_policy(self) -> None:
        bounded = self.checked.parse_range(">=1.0.0")
        candidate = Version(1, 2, 3, ("alpha",))
        self.assertFalse(self.checked.satisfies(candidate, bounded, False))
        self.assertTrue(self.checked.satisfies(candidate, bounded, True))
        targeted = self.checked.parse_range("1.2.3-alpha")
        self.assertTrue(self.checked.satisfies(candidate, targeted, False))

    def test_parse_range_invalid_syntax_rejection(self) -> None:
        invalid_texts = (
            "",
            "   ",
            "||",
            ">=1.0.0 ||",
            ">=1.0.0, <2.0.0",
            "1",
            "1.2",
            ">1.2",
            "^0.0",
            "1.2 - 2.3",
            "1.0.0 - 2.0.0 - 3.0.0",
            "1.2.3.4",
            "1.x.3",
            "1.a.0",
            "1.x-alpha",
            "1.x+build.1",
            "01.2.3",
            "1.2.3-01",
        )
        for invalid_text in invalid_texts:
            with self.assertRaises(InvalidRangeError):
                self.checked.parse_range(invalid_text)

    def test_parse_range_operator_whitespace_and_trimming(self) -> None:
        spaced = self.checked.parse_range(">= 1.0.0")
        self.assertEqual(spaced.raw_text, ">= 1.0.0")
        spaced_wildcard = self.checked.parse_range(">= 1.x")
        self.assertEqual(spaced_wildcard.raw_text, ">= 1.x")
        trimmed = self.checked.parse_range("  >=1.0.0 <2.0.0  ")
        self.assertEqual(trimmed.raw_text, ">=1.0.0 <2.0.0")

    def test_satisfies_wildcard_operator_expansions(self) -> None:
        at_least_wildcard = self.checked.parse_range(">= 1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 0, 0), at_least_wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(0, 9, 9), at_least_wildcard, False))
        greater_wildcard = self.checked.parse_range(">1.x")
        self.assertTrue(self.checked.satisfies(Version(2, 0, 0), greater_wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(1, 9, 0), greater_wildcard, False))
        less_wildcard = self.checked.parse_range("<1.x")
        self.assertTrue(self.checked.satisfies(Version(0, 9, 9), less_wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(1, 0, 0), less_wildcard, False))
        at_most_wildcard = self.checked.parse_range("<=1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 9, 0), at_most_wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), at_most_wildcard, False))
        caret_wildcard = self.checked.parse_range("^1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), caret_wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), caret_wildcard, False))

    def test_satisfies_unbounded_and_inequality_wildcards(self) -> None:
        anything = self.checked.parse_range(">=*")
        self.assertTrue(self.checked.satisfies(Version(3, 1, 0), anything, False))
        self.assertTrue(self.checked.satisfies(Version(0, 0, 0), anything, False))
        unsatisfiable = self.checked.parse_range("<*")
        self.assertFalse(self.checked.satisfies(Version(1, 0, 0), unsatisfiable, False))
        inequality = self.checked.parse_range("!=1.x")
        self.assertTrue(self.checked.satisfies(Version(0, 9, 9), inequality, False))
        self.assertFalse(self.checked.satisfies(Version(1, 5, 0), inequality, False))
        self.assertTrue(self.checked.satisfies(Version(2, 0, 0), inequality, False))

    def test_satisfies_hyphen_and_comparison_operators(self) -> None:
        full_hyphen = self.checked.parse_range("1.2.3 - 2.0.0")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), full_hyphen, False))
        self.assertTrue(self.checked.satisfies(Version(2, 0, 0), full_hyphen, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 1), full_hyphen, False))
        self.assertFalse(self.checked.satisfies(Version(1, 2, 2), full_hyphen, False))
        partial_hyphen = self.checked.parse_range("1.x - 2.x")
        self.assertTrue(self.checked.satisfies(Version(1, 0, 0), partial_hyphen, False))
        self.assertFalse(self.checked.satisfies(Version(3, 0, 0), partial_hyphen, False))
        equality = self.checked.parse_range("==1.2.3")
        self.assertTrue(self.checked.satisfies(Version(1, 2, 3), equality, False))
        self.assertFalse(self.checked.satisfies(Version(1, 2, 4), equality, False))
        inequality_full = self.checked.parse_range("!=1.2.3")
        self.assertTrue(self.checked.satisfies(Version(1, 2, 4), inequality_full, False))
        self.assertFalse(self.checked.satisfies(Version(1, 2, 3), inequality_full, False))
        at_most = self.checked.parse_range("<=2.0.0")
        self.assertTrue(self.checked.satisfies(Version(2, 0, 0), at_most, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 1), at_most, False))
        greater = self.checked.parse_range(">2.0.0")
        self.assertTrue(self.checked.satisfies(Version(2, 0, 1), greater, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), greater, False))

    def test_satisfies_zero_component_caret_and_tilde(self) -> None:
        caret = self.checked.parse_range("^0.0.0")
        self.assertTrue(self.checked.satisfies(Version(0, 0, 0), caret, False))
        self.assertFalse(self.checked.satisfies(Version(0, 0, 1), caret, False))
        tilde = self.checked.parse_range("~0.0.0")
        self.assertTrue(self.checked.satisfies(Version(0, 0, 1), tilde, False))
        self.assertFalse(self.checked.satisfies(Version(0, 1, 0), tilde, False))

    def test_satisfies_zero_wildcard_caret_and_single_wildcard_tilde(self) -> None:
        zero_major_caret = self.checked.parse_range("^0.x")
        self.assertTrue(self.checked.satisfies(Version(0, 5, 0), zero_major_caret, False))
        self.assertFalse(self.checked.satisfies(Version(1, 0, 0), zero_major_caret, False))
        zero_minor_caret = self.checked.parse_range("^0.0.x")
        self.assertTrue(self.checked.satisfies(Version(0, 0, 5), zero_minor_caret, False))
        self.assertFalse(self.checked.satisfies(Version(0, 1, 0), zero_minor_caret, False))
        single_wildcard_tilde = self.checked.parse_range("~1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), single_wildcard_tilde, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), single_wildcard_tilde, False))

    def test_parse_range_dangling_operator_rejection(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range(">=1.0.0 >=")
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range("1.0.0 ^")


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
# LAST_CLEANED: 2026-11-07T04:10:10Z
# LAST_CHANGED: 2026-11-07T04:09:00Z
# CHANGE: Add deterministic scenarios for the dangling-operator syntax violations (>=1.0.0 >=, 1.0.0 ^) raising InvalidRangeError, and for zero-component caret wildcards (^0.x satisfied at 0.5.0 but not 1.0.0; ^0.0.x satisfied at 0.0.5 but not 0.1.0) plus single-segment tilde wildcard (~1.x satisfied at 1.5.0 but not 2.0.0) asserting both expanded boundaries.
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T04:10:10Z
# PRETENSE_QA_AUDIT: 2026-11-07T04:09:27Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverRange."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
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
from benchmark_2.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_2.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================

# Range spellings sampled by the caller precondition contract: valid spellings
# exercise parsing/expansion and malformed spellings exercise the contracted
# InvalidRangeError syntax violations.
SAMPLE_RANGE_TEXTS: Tuple[str, ...] = (
    "1.x",
    "^1.2.3",
    "~1.2.3",
    ">=1.0.0",
    "  >=1.0.0 <2.0.0  ",
    ">=1.0.0 <2.0.0",
    ">=1.0.0 <2.0.0 || >=3.0.0",
    "1.0.0 - 2.x",
    "1.2.3-alpha",
    ">= 1.0.0",
    ">= 1.x",
    ">1.x",
    "<1.x",
    "<=1.x",
    "^1.x",
    "~1.x",
    ">=*",
    "<*",
    "!=1.x",
    "1.2.3 - 2.0.0",
    "1.x - 2.x",
    "==1.2.3",
    "!=1.2.3",
    "<=2.0.0",
    ">2.0.0",
    "^0.0.0",
    "~0.0.0",
    "^0.x",
    "^0.0.x",
    "",
    "   ",
    "||",
    ">=1.0.0 ||",
    ">=1.0.0, <2.0.0",
    ">=1.0.0 >=",
    "1.0.0 ^",
    "1",
    "1.2",
    ">1.2",
    "^0.0",
    "1.2 - 2.3",
    "1.0.0 - 2.0.0 - 3.0.0",
    "1.2.3.4",
    "1.x.3",
    "1.a.0",
    "1.x-alpha",
    "1.x+build.1",
    "01.2.3",
    "1.2.3-01",
)

CANDIDATE_VERSIONS: List[Version] = [
    Version(0, 0, 0),
    Version(0, 0, 1),
    Version(0, 0, 5),
    Version(0, 1, 0),
    Version(0, 5, 0),
    Version(0, 9, 9),
    Version(1, 0, 0),
    Version(1, 0, 0, ("alpha",)),
    Version(1, 2, 3),
    Version(1, 2, 3, ("alpha",)),
    Version(1, 2, 4),
    Version(1, 2, 2),
    Version(1, 2, 9),
    Version(1, 3, 0),
    Version(1, 4, 2),
    Version(1, 5, 0),
    Version(1, 9, 0),
    Version(2, 0, 0),
    Version(2, 0, 1),
    Version(2, 5, 0),
    Version(3, 0, 0),
    Version(3, 1, 0),
]

RANGE_SAMPLES: List[VersionRange] = [
    VersionRange(raw_text="1.x"),
    VersionRange(raw_text="^1.2.3"),
    VersionRange(raw_text="~1.2.3"),
    VersionRange(raw_text=">=1.0.0"),
    VersionRange(raw_text=">=1.0.0 <2.0.0"),
    VersionRange(raw_text=">=1.0.0 <2.0.0 || >=3.0.0"),
    VersionRange(raw_text="1.0.0 - 2.x"),
    VersionRange(raw_text="1.2.3-alpha"),
    VersionRange(raw_text=">= 1.0.0"),
    VersionRange(raw_text=">= 1.x"),
    VersionRange(raw_text=">1.x"),
    VersionRange(raw_text="<1.x"),
    VersionRange(raw_text="<=1.x"),
    VersionRange(raw_text="^1.x"),
    VersionRange(raw_text="~1.x"),
    VersionRange(raw_text=">=*"),
    VersionRange(raw_text="<*"),
    VersionRange(raw_text="!=1.x"),
    VersionRange(raw_text="1.2.3 - 2.0.0"),
    VersionRange(raw_text="1.x - 2.x"),
    VersionRange(raw_text="==1.2.3"),
    VersionRange(raw_text="!=1.2.3"),
    VersionRange(raw_text="<=2.0.0"),
    VersionRange(raw_text=">2.0.0"),
    VersionRange(raw_text="^0.0.0"),
    VersionRange(raw_text="~0.0.0"),
    VersionRange(raw_text="^0.x"),
    VersionRange(raw_text="^0.0.x"),
]

KNOWN_RANGE: VersionRange = VersionRange(raw_text=">=1.0.0")
INVALID_RANGE_PLACEHOLDER: VersionRange = VersionRange(raw_text="")

OPERATORS: Tuple[str, ...] = (">=", "<=", "==", "!=", ">", "<", "=", "^", "~")


def _is_numeric_component_token(token: str) -> bool:
    """Checks a numeric range component for digits and the no-leading-zero rule."""
    if not token or not token.isdigit():
        return False
    return token == "0" or not token.startswith("0")


def _is_identifier_token(token: str) -> bool:
    """Checks a prerelease/build identifier for the permitted character set."""
    return bool(token) and all(character.isalnum() or character == "-" for character in token)


def _is_valid_bound_text(text: str) -> bool:
    """Validates a comparator/hyphen operand against the contracted bound grammar."""
    literal = text.strip()
    if literal in ("", "*", "x", "X"):
        return True
    core = literal
    build: Tuple[str, ...] = ()
    build_index = core.find("+")
    if build_index >= 0:
        build = tuple(core[build_index + 1 :].split("."))
        core = core[:build_index]
    prerelease: Tuple[str, ...] = ()
    prerelease_index = core.find("-")
    if prerelease_index >= 0:
        prerelease = tuple(core[prerelease_index + 1 :].split("."))
        core = core[:prerelease_index]
    components = core.split(".")
    if not components or len(components) > 3:
        return False
    has_wildcard = False
    numeric_seen = 0
    for component in components:
        if component in ("x", "X", "*", ""):
            has_wildcard = True
            continue
        if has_wildcard:
            return False
        if not _is_numeric_component_token(component):
            return False
        numeric_seen += 1
    if has_wildcard:
        return not prerelease and not build
    if len(components) != 3 or numeric_seen != 3:
        return False
    for identifier in prerelease:
        if not _is_identifier_token(identifier):
            return False
        if identifier.isdigit() and not _is_numeric_component_token(identifier):
            return False
    for identifier in build:
        if not _is_identifier_token(identifier):
            return False
    return True


def _clause_tokens(clause: str) -> List[Tuple[str, str]]:
    """Splits a clause into (operator, operand) pairs, accepting operator whitespace."""
    pairs: List[Tuple[str, str]] = []
    pending = ""
    for token in clause.split():
        if token in OPERATORS:
            pending = token
            continue
        operator, operand = _split_operator(token)
        if pending:
            operator = pending
            operand = token
            pending = ""
        pairs.append((operator, operand))
    if pending:
        pairs.append((pending, ""))
    return pairs


def _is_valid_comparator_clause(clause: str) -> bool:
    """Validates one union clause against the contracted range grammar."""
    text = clause.strip()
    if not text or "," in text:
        return False
    if " - " in text:
        bounds = text.split(" - ")
        if len(bounds) != 2:
            return False
        return _is_valid_bound_text(bounds[0]) and _is_valid_bound_text(bounds[1])
    pairs = _clause_tokens(text)
    if not pairs:
        return False
    for operator, operand in pairs:
        if operator and operator not in OPERATORS:
            return False
        if operator and not operand:
            return False
        if not _is_valid_bound_text(operand):
            return False
    return True


def _is_valid_range_text(text: str) -> bool:
    """Validates raw range text against the SemVer range syntax contract."""
    stripped = text.strip()
    if not stripped or "," in stripped:
        return False
    for clause in stripped.split("||"):
        if not _is_valid_comparator_clause(clause):
            return False
    return True


def _compare_prerelease(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Orders two prerelease identifier sequences under SemVer 2.0.0 rules."""
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    shared = min(len(left), len(right))
    for index in range(shared):
        left_part = left[index]
        right_part = right[index]
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            left_value = int(left_part)
            right_value = int(right_part)
            if left_value != right_value:
                return -1 if left_value < right_value else 1
        elif left_numeric:
            return -1
        elif right_numeric:
            return 1
        elif left_part != right_part:
            return -1 if left_part < right_part else 1
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def _compare_precedence(left: Version, right: Version) -> int:
    """Orders two versions by precedence, ignoring build metadata."""
    left_numbers = (left.major, left.minor, left.patch)
    right_numbers = (right.major, right.minor, right.patch)
    if left_numbers != right_numbers:
        return -1 if left_numbers < right_numbers else 1
    return _compare_prerelease(left.prerelease, right.prerelease)


def _numeric_component(value: str) -> Optional[int]:
    """Converts a range component into an integer, mapping wildcards to None."""
    text = value.strip()
    if text in ("", "x", "X", "*"):
        return None
    if not text.isdigit():
        return None
    return int(text)


def _parse_bound(text: str) -> Tuple[Optional[int], Optional[int], Optional[int], Tuple[str, ...]]:
    """Parses a comparator operand into numeric components plus prerelease identifiers."""
    literal = text.strip()
    if literal in ("", "x", "X", "*"):
        return (None, None, None, ())
    core = literal
    build_index = core.find("+")
    if build_index >= 0:
        core = core[:build_index]
    prerelease: Tuple[str, ...] = ()
    prerelease_index = core.find("-")
    if prerelease_index >= 0:
        prerelease = tuple(core[prerelease_index + 1 :].split("."))
        core = core[:prerelease_index]
    components = core.split(".")
    major = _numeric_component(components[0])
    minor = _numeric_component(components[1]) if len(components) > 1 else None
    patch = _numeric_component(components[2]) if len(components) > 2 else None
    return (major, minor, patch, prerelease)


def _version(major: int, minor: int, patch: int, prerelease: Tuple[str, ...] = ()) -> Version:
    """Builds a model version boundary for comparator evaluation."""
    return Version(major, minor, patch, prerelease)


def _next_boundary(major: int, minor: Optional[int], patch: Optional[int]) -> Version:
    """Produces the exclusive upper boundary for a partial or wildcard component."""
    if minor is None:
        return _version(major + 1, 0, 0)
    if patch is None:
        return _version(major, minor + 1, 0)
    return _version(major, minor, patch + 1)


def _lower_bound(
    major: int,
    minor: Optional[int],
    patch: Optional[int],
    prerelease: Tuple[str, ...],
) -> Version:
    """Produces the inclusive lower boundary of a comparator operand."""
    return _version(major, minor if minor is not None else 0, patch if patch is not None else 0, prerelease)


def _caret_upper(major: int, minor: Optional[int], patch: Optional[int]) -> Version:
    """Produces the exclusive caret upper boundary per caret range algebra."""
    if major > 0 or minor is None:
        return _version(major + 1, 0, 0)
    if minor > 0 or patch is None:
        return _version(0, minor + 1, 0)
    return _version(0, 0, patch + 1)


def _tilde_upper(major: int, minor: Optional[int], patch: Optional[int]) -> Version:
    """Produces the exclusive tilde upper boundary per tilde range algebra."""
    if minor is None:
        return _version(major + 1, 0, 0)
    return _version(major, minor + 1, 0)


def _expand_comparator(operator: str, operand: str) -> List[List[Tuple[str, Version]]]:
    """Expands one comparator token into alternative conjunctions of primitive bounds."""
    major, minor, patch, prerelease = _parse_bound(operand)
    if major is None:
        if operator in ("<", ">", "!="):
            return []
        return [[]]
    upper = _next_boundary(major, minor, patch)
    lower = _lower_bound(major, minor, patch, prerelease)
    partial = minor is None or patch is None
    if operator in ("", "=", "=="):
        if partial:
            return [[(">=", lower), ("<", upper)]]
        return [[("==", lower)]]
    if operator == "!=":
        if partial:
            return [[("<", lower)], [(">=", upper)]]
        return [[("<", lower)], [(">", lower)]]
    if operator == ">=":
        return [[(">=", lower)]]
    if operator == ">":
        if partial:
            return [[(">=", upper)]]
        return [[(">", lower)]]
    if operator == "<":
        return [[("<", lower)]]
    if operator == "<=":
        if partial:
            return [[("<", upper)]]
        return [[("<=", lower)]]
    if operator == "^":
        return [[(">=", lower), ("<", _caret_upper(major, minor, patch))]]
    if operator == "~":
        return [[(">=", lower), ("<", _tilde_upper(major, minor, patch))]]
    return [[]]


def _split_operator(token: str) -> Tuple[str, str]:
    """Splits a comparator token into its relational prefix and operand."""
    for operator in OPERATORS:
        if token.startswith(operator):
            return operator, token[len(operator) :].strip()
    return "", token


def _matches_primitive(version: Version, operator: str, bound: Version) -> bool:
    """Evaluates one primitive comparator against a candidate version."""
    comparison = _compare_precedence(version, bound)
    if operator == "==":
        return comparison == 0
    if operator == "<":
        return comparison < 0
    if operator == "<=":
        return comparison <= 0
    if operator == ">":
        return comparison > 0
    if operator == ">=":
        return comparison >= 0
    if operator == "!=":
        return comparison != 0
    return False


def _clause_alternatives(clause: str) -> List[List[Tuple[str, Version]]]:
    """Expands one inclusive clause into alternative conjunctions of primitive bounds."""
    if " - " in clause:
        lower_text, upper_text = clause.split(" - ", 1)
        lower_alternatives = _expand_comparator(">=", lower_text)
        upper_major, upper_minor, upper_patch, upper_prerelease = _parse_bound(upper_text)
        if upper_major is None:
            return lower_alternatives
        if upper_minor is None or upper_patch is None:
            upper_alternatives = [[("<", _next_boundary(upper_major, upper_minor, upper_patch))]]
        else:
            upper_alternatives = [[("<=", _lower_bound(upper_major, upper_minor, upper_patch, upper_prerelease))]]
        combined: List[List[Tuple[str, Version]]] = []
        for lower in lower_alternatives:
            for upper in upper_alternatives:
                combined.append(lower + upper)
        return combined
    alternatives: List[List[Tuple[str, Version]]] = [[]]
    for operator, operand in _clause_tokens(clause):
        expansions = _expand_comparator(operator, operand)
        combined = []
        for alternative in alternatives:
            for expansion in expansions:
                combined.append(alternative + expansion)
        alternatives = combined
    return alternatives


def _prerelease_targets(text: str) -> Set[Tuple[int, int, int]]:
    """Collects the major/minor/patch triples explicitly targeted by prerelease bounds."""
    targets: Set[Tuple[int, int, int]] = set()
    normalized = text.replace("||", " ").replace(" - ", " ")
    for token in normalized.split():
        _operator, operand = _split_operator(token)
        major, minor, patch, prerelease = _parse_bound(operand)
        if prerelease and major is not None and minor is not None and patch is not None:
            targets.add((major, minor, patch))
    return targets


def range_satisfies(version: Version, range_text: str, include_prerelease: bool) -> bool:
    """Evaluates range semantics over a candidate version as a specification oracle."""
    text = range_text.strip()
    if version.prerelease and not include_prerelease:
        targeted = (version.major, version.minor, version.patch) in _prerelease_targets(text)
        if not targeted:
            return False
    for clause in text.split("||"):
        for alternative in _clause_alternatives(clause.strip()):
            matched = True
            for operator, bound in alternative:
                if not _matches_primitive(version, operator, bound):
                    matched = False
            if matched:
                return True
    return False


@dataclass
class SemverRangeState:
    """Model state for version range parsing and constraint matching operations."""

    parsed_range_texts: List[str] = field(default_factory=list)
    satisfaction_checks: int = 0
    known_range: Optional[VersionRange] = None


class SemverRangeStateMachine(StateMachine[SemverRangeState]):
    """State machine modeling SemverRange operations 1:1 with the target interface."""

    def __init__(
        self,
        state: Optional[SemverRangeState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverRangeState(), singletons=singletons)

    @transition(RangeEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require_arg(text, Domain.sampled_from(list(SAMPLE_RANGE_TEXTS)))
        if not _is_valid_range_text(text):
            invalid: VersionRange = INVALID_RANGE_PLACEHOLDER
            with raises(InvalidRangeError):
                invalid = make_return_value(invalid)
            return invalid
        fake_ret = VersionRange(raw_text=text.strip())
        ret: VersionRange = make_return_value(fake_ret)
        self.state.parsed_range_texts.append(fake_ret.raw_text)
        assert ret == fake_ret
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(version, Domain.sampled_from(CANDIDATE_VERSIONS))
        require_arg(range_constraint, Domain.sampled_from(RANGE_SAMPLES))
        require_arg(include_prerelease, Domain.boolean())
        fake_ret = range_satisfies(version, range_constraint.raw_text, include_prerelease)
        ret: bool = make_return_value(fake_ret)
        self.state.satisfaction_checks += 1
        assert ret == fake_ret
        return ret

    @transition.seeding
    def seed_known_range(self) -> None:
        """Transitions a blank model state into one carrying a known constraint."""
        self.state.known_range = KNOWN_RANGE
        self.state.parsed_range_texts.clear()
        self.state.satisfaction_checks = 0


proto = SemverRangeStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverRange = synthesize_fake(SemverRangeStateMachine)


def make_semver_range_fake(state: Optional[SemverRangeState] = None) -> Any:
    """Synthesizes a fake covering the VersionRange and RangeEngine interfaces."""
    return FakeSemverRange(state=state or SemverRangeState())


def make_semver_range_fakes(
    state: Optional[SemverRangeState] = None,
) -> Tuple[VersionRange, RangeEngine]:
    """Synthesizes fake component services sharing one model state."""
    fake = make_semver_range_fake(state)
    return (fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestSemverRangeFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.range_fake, self.engine_fake = make_semver_range_fakes()
        self.sm = SemverRangeStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition against the synthesized fake."""
        parsed = self.engine_fake.parse_range("^1.2.3")
        self.assertEqual(parsed.raw_text, "^1.2.3")
        self.assertTrue(self.engine_fake.satisfies(Version(1, 2, 3), RANGE_SAMPLES[1], False))
        self.assertFalse(self.engine_fake.satisfies(Version(2, 0, 0), RANGE_SAMPLES[1], False))
        self.assertFalse(self.engine_fake.satisfies(Version(0, 9, 9), RANGE_SAMPLES[0], False))
        self.assertFalse(
            self.engine_fake.satisfies(Version(1, 2, 3, ("alpha",)), RANGE_SAMPLES[3], False)
        )
        self.assertTrue(
            self.engine_fake.satisfies(Version(1, 2, 3, ("alpha",)), RANGE_SAMPLES[3], True)
        )
        self.assertTrue(self.engine_fake.satisfies(Version(1, 2, 3, ("alpha",)), RANGE_SAMPLES[7], False))

    def test_seeding_transitions(self) -> None:
        """Exercises every declared seeding transition."""
        self.sm.seed_known_range()
        self.assertEqual(self.sm.parse_range(">=1.0.0").raw_text, ">=1.0.0")


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverRangeState,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T04:08:57Z
# LAST_CHANGED: 2026-11-07T04:08:57Z
# CHANGE: Reject dangling operators: comparator clauses now require a non-empty operand after every operator, so '>=1.0.0 >=' and '1.0.0 ^' are modelled as InvalidRangeError syntax violations. The sampled domain and oracle samples also add single-segment tilde wildcard '~1.x' and zero-component caret wildcards '^0.x' and '^0.0.x' with their versions.
# --- END AUTOFAB METADATA ---
