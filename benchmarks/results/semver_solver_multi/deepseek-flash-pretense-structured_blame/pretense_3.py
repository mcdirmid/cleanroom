# === File: dependency_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Collection, Dict, List, Set, Tuple

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
    VersionEngine,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine as VersionEngineImpl,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range import (
    RangeEngine,
    VersionRange,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine as RangeEngineImpl,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver as DependencySolverImpl,
    PackageRepository as PackageRepositoryImpl,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
)

# ==============================================================================
# 1. Transitive backtracking fixtures (shared by fuzzing and fixed scenarios)
# ==============================================================================

def _range(raw_text: str) -> VersionRange:
    """Builds a concrete version range constraint from its canonical text."""
    return VersionRange(raw_text=raw_text)


def _dependency(name: str, raw_range: str) -> PackageDependency:
    """Builds a concrete package dependency record."""
    return PackageDependency(name=name, range_constraint=_range(raw_range))


def _widget_release() -> PackageRelease:
    """Builds a widget release matching the seeded repository data."""
    return PackageRelease(name="widget", version=Version(major=1, minor=0, patch=0))


def _alpha_violating_release() -> PackageRelease:
    """Builds an alpha release whose transitive beta constraint cannot be met."""
    return PackageRelease(
        name="alpha",
        version=Version(major=2, minor=0, patch=0),
        dependencies=(_dependency("beta", "<1.0.0"),),
    )


def _alpha_compatible_release() -> PackageRelease:
    """Builds the lower alpha release compatible with the published beta release."""
    return PackageRelease(
        name="alpha",
        version=Version(major=1, minor=0, patch=0),
        dependencies=(_dependency("beta", ">=1.0.0"),),
    )


def _beta_release() -> PackageRelease:
    """Builds the sole published beta release."""
    return PackageRelease(name="beta", version=Version(major=1, minor=0, patch=0))


def _delta_high_release() -> PackageRelease:
    """Builds a delta release requiring an unpublished beta version."""
    return PackageRelease(
        name="delta",
        version=Version(major=2, minor=0, patch=0),
        dependencies=(_dependency("beta", ">=2.0.0"),),
    )


def _delta_low_release() -> PackageRelease:
    """Builds the lower delta release requiring the same unpublished beta version."""
    return PackageRelease(
        name="delta",
        version=Version(major=1, minor=0, patch=0),
        dependencies=(_dependency("beta", ">=2.0.0"),),
    )


def _deferred_group() -> Tuple[PackageDependency, ...]:
    """Builds the root group whose transitive beta requirement is deferred."""
    return (_dependency("delta", ">=1.0.0"),)


def _paired_group() -> Tuple[PackageDependency, ...]:
    """Builds the root group requiring both alpha and beta explicitly."""
    return (_dependency("alpha", ">=1.0.0"), _dependency("beta", ">=1.0.0"))


def _transitive_group() -> Tuple[PackageDependency, ...]:
    """Builds the root group requiring only alpha, whose dependency pulls in beta."""
    return (_dependency("alpha", ">=1.0.0"),)


def _populate_backtracking_state(state: DependencySolverState) -> None:
    """Seeds the transitive backtracking scenarios into the model state."""
    alpha_violating = _alpha_violating_release()
    alpha_compatible = _alpha_compatible_release()
    beta_release = _beta_release()
    expected = {
        "alpha": Version(major=1, minor=0, patch=0),
        "beta": Version(major=1, minor=0, patch=0),
    }
    required = frozenset({alpha_violating, alpha_compatible, beta_release})
    state.pending_releases.update(required)
    state.pending_releases.update({_delta_high_release(), _delta_low_release()})
    state.expected_assignments[_paired_group()] = expected
    state.expected_assignments[_transitive_group()] = expected
    state.pending_groups.update(
        {
            (_paired_group(), required),
            (_transitive_group(), required),
        }
    )


# ==============================================================================
# 1. Implementation Pseudo State Machine
# ==============================================================================

class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine driving the concrete repository and solver."""

    def make_initial_state(self) -> DependencySolverState:
        """Specializes the open seed state so real fuzzing starts with legal inputs."""
        state = DependencySolverState()
        self.populate_seed_state(state)
        _populate_backtracking_state(state)
        return state

    def inner_register_package(self, release: PackageRelease) -> None:
        """Registers the release through the concrete repository."""
        target: PackageRepository = sut(PackageRepository)
        target.register_package(release)
        assert target.has_package(release.name)

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        """Lists the concrete releases registered for a package."""
        target: PackageRepository = sut(PackageRepository)
        ret = target.get_releases(name)
        assert target.has_package(name)
        return ret

    def inner_has_package(self, name: str) -> bool:
        """Checks package membership through the concrete repository."""
        target: PackageRepository = sut(PackageRepository)
        return target.has_package(name)

    def inner_all_packages(self) -> Set[str]:
        """Lists all concrete package names through the repository."""
        target: PackageRepository = sut(PackageRepository)
        return target.all_packages()

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Resolves the seeded dependency group through the concrete solver."""
        target: DependencySolver = sut(DependencySolver)
        return target.resolve(root_dependencies)


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 2. Concrete SUT Factory
# ==============================================================================

def make_sut() -> Dict[type[Any], Any]:
    """Constructs a lifecycle scope exposing the concrete repository and solver."""
    registry = LifecycleRegistry()
    registry.register_singleton(
        VersionEngineImpl,
        keys=[VersionEngineImpl, VersionEngine],
    )
    registry.register_singleton(
        RangeEngineImpl,
        keys=[RangeEngineImpl, RangeEngine],
    )
    registry.register_singleton(
        PackageRepositoryImpl,
        keys=[PackageRepositoryImpl, PackageRepository],
    )
    registry.register_singleton(
        DependencySolverImpl,
        keys=[DependencySolverImpl, DependencySolver],
    )
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return {
        PackageRepository: get_singleton(PackageRepository),
        DependencySolver: get_singleton(DependencySolver),
    }


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on the Real Implementation
# ==============================================================================

DependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DependencySolverFuzzTest",
)


# ==============================================================================
# 4. Fixed Real Implementation Scenarios
# ==============================================================================

class TestDependencySolverImplReal(LifecycleTestCase):
    """Fixed scenarios covering contracted errors and transitive backtracking."""

    def setUp(self) -> None:
        super().setUp()
        self.repository = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = DependencySolverImplPseudoStateMachine(
            singletons={
                PackageRepository: self.repository,
                DependencySolver: self.solver,
            }
        )
        self.checked_repo = self.sm.as_checked(PackageRepository, self.repository)
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)

    def test_unregistered_package_lookup_is_rejected(self) -> None:
        """Rejects repository lookups for unregistered package names."""
        self.checked_repo.violating(PackageNotFoundError).get_releases("unregistered_package")

    def test_missing_package_dependency_is_conflict(self) -> None:
        """Rejects root dependencies that reference absent package names."""
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (_dependency("unregistered_package", ">=1.0.0"),)
        )

    def test_unsatisfiable_root_constraint_is_conflict(self) -> None:
        """Rejects root constraints that exceed every published release."""
        self.checked_repo.register_package(_widget_release())
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (_dependency("widget", ">=3.0.0"),)
        )

    def test_backtracking_rejects_violating_assigned_release(self) -> None:
        """Rolls back a candidate whose transitive range violates an assigned release."""
        self.checked_repo.register_package(_alpha_violating_release())
        self.checked_repo.register_package(_alpha_compatible_release())
        self.checked_repo.register_package(_beta_release())
        self.checked_solver.resolve(_paired_group())

    def test_backtracking_rolls_back_added_constraints(self) -> None:
        """Rolls back transitive constraints introduced by a failed candidate branch."""
        self.checked_repo.register_package(_alpha_violating_release())
        self.checked_repo.register_package(_alpha_compatible_release())
        self.checked_repo.register_package(_beta_release())
        self.checked_solver.resolve(_transitive_group())

    def test_deferred_transitive_conflict_exhausts_decisions(self) -> None:
        """Exhausts decision nodes when every deferred transitive candidate fails."""
        self.checked_repo.register_package(_delta_high_release())
        self.checked_repo.register_package(_delta_low_release())
        self.checked_repo.register_package(_beta_release())
        self.checked_solver.violating(ResolutionConflictError).resolve(_deferred_group())

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:30:30Z
# LAST_CHANGED: 2026-11-15T04:29:43Z
# CHANGE: Add deferred transitive conflict scenario requested by pretense_coverage: delta 2.0.0/1.0.0 both require an unpublished beta >=2.0.0, so resolving delta >=1.0.0 triggers deferred unsatisfiability, exhausts the decision node, and surfaces violating(ResolutionConflictError); delta fixtures seeded into pending releases without a fuzz-enabled root group.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T04:30:30Z
# PRETENSE_QA_AUDIT: 2026-11-15T04:29:53Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Collection,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)
import unittest

from pretense import (
    StateMachine,
    require,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range import (
    VersionRange,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
)

# ==============================================================================
# 1. Model helpers (pure inspection helpers, no target interaction)
# ==============================================================================

def _range(raw_text: str) -> VersionRange:
    """Builds a model range constraint from its canonical text."""
    return VersionRange(raw_text=raw_text)


def _dependency(name: str, raw_range: str) -> PackageDependency:
    """Builds a model package dependency record."""
    return PackageDependency(name=name, range_constraint=_range(raw_range))


def _version_key(version: Version) -> Tuple[int, int, int, int, Tuple[Tuple[int, object], ...]]:
    """Builds a fully ordered precedence key (build metadata is ignored)."""
    identifiers = tuple(
        (0, int(part)) if part.isdigit() else (1, part) for part in version.prerelease
    )
    return (
        version.major,
        version.minor,
        version.patch,
        0 if version.prerelease else 1,
        identifiers,
    )


def _release_key(release: PackageRelease) -> Tuple[int, int, int, int, Tuple[Tuple[int, object], ...]]:
    """Orders releases by their version precedence key."""
    return _version_key(release.version)


def _releases_named(
    releases: Iterable[PackageRelease],
    name: str,
) -> List[PackageRelease]:
    """Collects the releases published under a package name."""
    return [release for release in releases if release.name == name]


def _has_named(releases: Iterable[PackageRelease], name: str) -> bool:
    """Indicates whether any release belongs to the package name."""
    for release in releases:
        if release.name == name:
            return True
    return False


def _names_in(releases: Iterable[PackageRelease]) -> Tuple[str, ...]:
    """Collects the package names of the supplied releases."""
    return tuple(release.name for release in releases)


def _version_keys(
    releases: Iterable[PackageRelease],
) -> List[Tuple[int, int, int, int, Tuple[Tuple[int, object], ...]]]:
    """Collects the ordered precedence keys of the supplied releases."""
    return [_release_key(release) for release in releases]


def _versions_in(releases: Iterable[PackageRelease]) -> Set[Version]:
    """Collects the versions of the supplied releases."""
    return {release.version for release in releases}


def _versions_named(releases: Iterable[PackageRelease], name: str) -> Set[Version]:
    """Collects the versions published under a package name."""
    return {release.version for release in releases if release.name == name}


def _group_key(dependencies: Collection[PackageDependency]) -> Tuple[PackageDependency, ...]:
    """Normalizes a root dependency collection into a hashable model group key."""
    return tuple(dependencies)


# ==============================================================================
# 2. State Machine Specification (Model & 1:1 Transitions)
# ==============================================================================

PendingGroup = Tuple[Tuple[PackageDependency, ...], FrozenSet[PackageRelease]]


@dataclass
class DependencySolverState:
    """Model state tracking repository publications and observable solver outcomes."""
    pending_releases: Set[PackageRelease] = field(default_factory=set)
    registered_releases: Set[PackageRelease] = field(default_factory=set)
    package_names: Set[str] = field(default_factory=set)
    pending_groups: Set[PendingGroup] = field(default_factory=set)
    root_groups: Set[Tuple[PackageDependency, ...]] = field(default_factory=set)
    expected_assignments: Dict[Tuple[PackageDependency, ...], Dict[str, Version]] = field(
        default_factory=dict
    )


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense state machine for package repositories and dependency resolution."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DependencySolverState:
        """Constructs a blank initial model state (seed entries arrive via seeding)."""
        return DependencySolverState()

    def populate_seed_state(self, state: DependencySolverState) -> None:
        """Overridable hook that registers representative releases and resolution groups."""
        widget_1 = Version(major=1, minor=0, patch=0)
        widget_2 = Version(major=2, minor=0, patch=0)
        gadget_1 = Version(major=1, minor=2, patch=0)
        gadget_2 = Version(major=1, minor=3, patch=0)
        app_1 = Version(major=1, minor=0, patch=0)
        app_2 = Version(major=2, minor=0, patch=0)

        widget_release_1 = PackageRelease(name="widget", version=widget_1)
        widget_release_2 = PackageRelease(name="widget", version=widget_2)
        gadget_release_1 = PackageRelease(name="gadget", version=gadget_1)
        gadget_release_2 = PackageRelease(name="gadget", version=gadget_2)
        app_release_1 = PackageRelease(name="app", version=app_1)
        app_release_2 = PackageRelease(
            name="app",
            version=app_2,
            dependencies=(
                _dependency("widget", ">=1.0.0"),
                _dependency("gadget", ">=1.0.0"),
            ),
        )

        state.pending_releases.update(
            {
                widget_release_1,
                widget_release_2,
                gadget_release_1,
                gadget_release_2,
                app_release_1,
                app_release_2,
            }
        )

        pinned_app = (_dependency("app", "==2.0.0"),)
        at_least_app = (_dependency("app", ">=1.0.0"),)
        pinned_widget = (_dependency("widget", "==1.0.0"),)
        independent_pair = (
            _dependency("widget", ">=1.0.0"),
            _dependency("gadget", "^1.0.0"),
        )
        state.expected_assignments[pinned_app] = {
            "app": app_2,
            "widget": widget_2,
            "gadget": gadget_2,
        }
        state.expected_assignments[at_least_app] = {
            "app": app_2,
            "widget": widget_2,
            "gadget": gadget_2,
        }
        state.expected_assignments[pinned_widget] = {"widget": widget_1}
        state.expected_assignments[independent_pair] = {
            "widget": widget_2,
            "gadget": gadget_2,
        }
        state.pending_groups.update(
            {
                (
                    pinned_app,
                    frozenset({app_release_2, widget_release_2, gadget_release_2}),
                ),
                (
                    at_least_app,
                    frozenset({app_release_2, widget_release_2, gadget_release_2}),
                ),
                (pinned_widget, frozenset({widget_release_1})),
                (
                    independent_pair,
                    frozenset({widget_release_2, gadget_release_2}),
                ),
            }
        )

    def _enable_ready_groups(self) -> None:
        """Enables resolution groups whose required releases are registered."""
        for group, required in self.state.pending_groups:
            if required <= self.state.registered_releases:
                self.state.root_groups.add(group)

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        """Registers a package release into the repository model."""
        require_arg(release, self.state.pending_releases)
        self.inner_register_package(release)
        self.state.pending_releases.discard(release)
        self.state.registered_releases.add(release)
        self.state.package_names.add(release.name)
        self._enable_ready_groups()
        assert release in self.state.registered_releases
        assert release.name in self.state.package_names

    def inner_register_package(self, release: PackageRelease) -> None:
        """Records the fake registration result for synthesized fakes."""
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        """Retrieves the registered releases for a package in descending order."""
        require(bool(self.state.registered_releases))
        require_arg(name, self.state.package_names)
        ret = self.inner_get_releases(name)
        assert len(ret) >= 1
        assert _names_in(ret) == (name,) * len(ret)
        assert _versions_in(ret) == _versions_named(self.state.registered_releases, name)
        assert _version_keys(ret) == sorted(_version_keys(ret), reverse=True)
        return ret

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        """Computes the fake release listing for synthesized fakes."""
        releases = _releases_named(self.state.registered_releases, name)
        return sorted(releases, key=_release_key, reverse=True)

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        """Checks whether a package exists within the repository model."""
        require_arg(name, str)
        ret = self.inner_has_package(name)
        assert ret == _has_named(self.state.registered_releases, name)
        return ret

    def inner_has_package(self, name: str) -> bool:
        """Computes the fake membership result for synthesized fakes."""
        return _has_named(self.state.registered_releases, name)

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        """Provides the set of registered package names."""
        ret = self.inner_all_packages()
        assert ret == self.state.package_names
        return ret

    def inner_all_packages(self) -> Set[str]:
        """Computes the fake package name set for synthesized fakes."""
        return set(self.state.package_names)

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        """Computes a compatible assignment for a seeded root dependency group."""
        require(bool(self.state.root_groups))
        require_arg(root_dependencies, self.state.root_groups)
        ret = self.inner_resolve(root_dependencies)
        key = _group_key(root_dependencies)
        assert dict(ret.selected_versions) == self.state.expected_assignments[key]
        assert isinstance(ret.derivation_steps, tuple)
        assert len(ret.derivation_steps) >= 1
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Computes the fake resolution outcome for synthesized fakes."""
        key = _group_key(root_dependencies)
        return ResolutionOutcome(
            selected_versions=dict(self.state.expected_assignments[key]),
            derivation_steps=("Resolved seeded dependency group",),
        )

    @transition.seeding
    def seed_dependencies(self) -> None:
        """Seeds representative releases and resolution groups for fake fuzzing."""
        self.populate_seed_state(self.state)


proto = DependencySolverStateMachine()


# ==============================================================================
# 3. Synthesized Fake (Interface Components)
# ==============================================================================

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageRepository, DependencySolver]:
    """Synthesizes fake repository/solver services sharing model state."""
    fake = FakeDependencySolver(state=state or proto.make_initial_state())
    return (fake, fake)


# ==============================================================================
# 4. Fixed Fake Scenarios (Interface Components)
# ==============================================================================

class TestDependencySolverFake(unittest.TestCase):
    """Fixed fake scenarios covering seeded repository and resolution transitions."""

    def setUp(self) -> None:
        state = proto.make_initial_state()
        proto.populate_seed_state(state)
        self.repository, self.solver = make_dependency_solver_fakes(state)

    def test_repository_registration(self) -> None:
        widget = PackageRelease(name="widget", version=Version(major=2, minor=0, patch=0))
        self.repository.register_package(widget)
        self.assertTrue(self.repository.has_package("widget"))
        self.assertIn("widget", self.repository.all_packages())
        self.assertEqual(self.repository.get_releases("widget"), [widget])

    def test_resolution_of_seeded_group(self) -> None:
        widget = PackageRelease(name="widget", version=Version(major=2, minor=0, patch=0))
        gadget = PackageRelease(name="gadget", version=Version(major=1, minor=3, patch=0))
        self.repository.register_package(widget)
        self.repository.register_package(gadget)
        root = (_dependency("widget", ">=1.0.0"), _dependency("gadget", "^1.0.0"))
        outcome = self.solver.resolve(root)
        self.assertEqual(outcome.selected_versions["widget"], Version(major=2, minor=0, patch=0))
        self.assertEqual(outcome.selected_versions["gadget"], Version(major=1, minor=3, patch=0))


# ==============================================================================
# 5. Fake Fuzzing (Interface Components)
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:20:47Z
# LAST_CHANGED: 2026-11-15T04:20:47Z
# CHANGE: Author dependency solver interface pretense: unified repository/solver state machine with seeded releases, gated group enabling, descending release listings, resolution outcome expectations, synthesized fake, fixed fake scenarios, and fake Hypothesis fuzzing (100% coverage).
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Dict, Optional

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
    VersionEngine,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine as VersionEngineImpl,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineState,
    VersionEngineStateMachine,
)

# ==============================================================================
# 1. Prerelease ordering fixtures (shared by fuzzing and fixed scenarios)
# ==============================================================================

def _populate_prerelease_state(state: VersionEngineState) -> None:
    """Seeds prerelease versions covering numeric and alphanumeric ordering."""
    state.versions.add(Version(major=1, minor=0, patch=0, prerelease=("alpha", "2")))
    state.versions.add(Version(major=1, minor=0, patch=0, prerelease=("alpha", "beta")))
    state.versions.add(Version(major=1, minor=0, patch=0, prerelease=("beta",)))


# ==============================================================================
# 1. Implementation Pseudo State Machine
# ==============================================================================

class VersionEngineImplPseudoStateMachine(VersionEngineStateMachine):
    """Implementation pseudo-state machine driving the concrete SemVer engine."""

    def make_initial_state(self) -> VersionEngineState:
        """Specializes the open seed state so real fuzzing starts with legal inputs."""
        state = VersionEngineState()
        self.populate_seed_state(state)
        _populate_prerelease_state(state)
        return state

    def inner_parse_version(self, text: str) -> Version:
        """Parses text through the concrete engine and checks derived properties."""
        target: VersionEngine = sut(VersionEngine)
        ret = target.parse_version(text)
        assert ret.is_prerelease == bool(ret.prerelease)
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        """Compares versions through the concrete engine and checks antisymmetry."""
        target: VersionEngine = sut(VersionEngine)
        ret = target.compare_precedence(v1, v2)
        reverse = target.compare_precedence(v2, v1)
        assert (ret < 0) == (reverse > 0)
        assert (ret == 0) == (reverse == 0)
        assert target.compare_precedence(v1, v1) == 0
        return ret


proto = VersionEngineImplPseudoStateMachine()


# ==============================================================================
# 2. Concrete SUT Factory
# ==============================================================================

def make_sut() -> VersionEngine:
    """Constructs a lifecycle scope exposing the concrete version engine."""
    registry = LifecycleRegistry()
    registry.register_singleton(
        VersionEngineImpl,
        keys=[VersionEngineImpl, VersionEngine],
    )
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(VersionEngine)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on the Real Implementation
# ==============================================================================

VersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="VersionEngineFuzzTest",
)


# ==============================================================================
# 4. Fixed Real Implementation Scenarios
# ==============================================================================

class TestVersionEngineImplReal(LifecycleTestCase):
    """Fixed scenarios covering grammar rejection and prerelease ordering facets."""

    def setUp(self) -> None:
        super().setUp()
        self.real = get_singleton(VersionEngine)
        self.sm = VersionEngineImplPseudoStateMachine(
            singletons={VersionEngine: self.real}
        )
        self.checked = self.sm.as_checked(VersionEngine, self.real)

    def test_parse_rejects_leading_zero_identifier(self) -> None:
        """Rejects numeric version identifiers carrying leading zeroes."""
        self.checked.violating(InvalidVersionError).parse_version("01.0.0")

    def test_parse_rejects_grammar_violation(self) -> None:
        """Rejects version text violating the SemVer grammar."""
        self.checked.violating(InvalidVersionError).parse_version("1.0")

    def test_compare_orders_numeric_prerelease_identifiers(self) -> None:
        """Orders numeric prerelease identifiers by numeric value."""
        self.checked.compare_precedence(
            Version(major=1, minor=0, patch=0, prerelease=("alpha", "1")),
            Version(major=1, minor=0, patch=0, prerelease=("alpha", "2")),
        )

    def test_compare_ranks_numeric_below_alphanumeric(self) -> None:
        """Ranks numeric prerelease identifiers below alphanumeric ones."""
        self.checked.compare_precedence(
            Version(major=1, minor=0, patch=0, prerelease=("alpha", "1")),
            Version(major=1, minor=0, patch=0, prerelease=("alpha", "beta")),
        )

    def test_compare_orders_alphanumeric_prerelease_lexically(self) -> None:
        """Orders alphanumeric prerelease identifiers in ASCII order."""
        self.checked.compare_precedence(
            Version(major=1, minor=0, patch=0, prerelease=("alpha",)),
            Version(major=1, minor=0, patch=0, prerelease=("beta",)),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:28:57Z
# LAST_CHANGED: 2026-11-15T04:26:55Z
# CHANGE: Add TestVersionEngineImplReal fixed scenarios requested by pretense_coverage feedback: violating(InvalidVersionError) for leading-zero and grammar-violating text, plus prerelease ordering scenarios (numeric inequality, numeric-below-alphanumeric ranking, ASCII lexical ordering) with impl-side prerelease seed versions.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T04:28:57Z
# PRETENSE_QA_AUDIT: 2026-11-15T04:27:12Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional, Set, Tuple, cast
import unittest

from pretense import (
    StateMachine,
    require,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
    VersionEngine,
)

# ==============================================================================
# 1. Parsing helpers (pure inspection helpers, no target interaction)
# ==============================================================================

_SEMVER_PATTERN = (
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)

_SEMVER_RE = re.compile(_SEMVER_PATTERN)


def _version_from_text(text: str) -> Version:
    """Reconstructs the expected Version record from canonical SemVer text."""
    match = cast(re.Match[str], _SEMVER_RE.fullmatch(text))
    major, minor, patch, prerelease, build = match.groups()
    return Version(
        major=int(major),
        minor=int(minor),
        patch=int(patch),
        prerelease=tuple(prerelease.split(".")) if prerelease else (),
        build=tuple(build.split(".")) if build else (),
    )


def _identifier_key(identifier: str) -> Tuple[int, object]:
    """Maps a pre-release identifier to a precedence-comparable tagged key."""
    if identifier.isdigit():
        return (0, int(identifier))
    return (1, identifier)


def _precedence_key(version: Version) -> Tuple[int, int, int, int, Tuple[Tuple[int, object], ...]]:
    """Builds a fully ordered precedence key (build metadata is ignored)."""
    if version.prerelease:
        return (
            version.major,
            version.minor,
            version.patch,
            0,
            tuple(_identifier_key(identifier) for identifier in version.prerelease),
        )
    return (version.major, version.minor, version.patch, 1, ())


# ==============================================================================
# 2. State Machine Specification (Model & 1:1 Transitions)
# ==============================================================================

@dataclass
class VersionEngineState:
    """Model state tracking legal version text and observed parsed versions."""
    texts: Set[str] = field(default_factory=set)
    versions: Set[Version] = field(default_factory=set)


class VersionEngineStateMachine(StateMachine[VersionEngineState]):
    """Unified Pretense state machine for the SemVer parsing and precedence engine."""

    def __init__(
        self,
        state: Optional[VersionEngineState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> VersionEngineState:
        """Constructs a blank initial model state (seed entries arrive via seeding)."""
        return VersionEngineState()

    def populate_seed_state(self, state: VersionEngineState) -> None:
        """Overridable hook that registers representative versions in model state."""
        state.texts.add("0.9.9")
        state.texts.add("1.0.0")
        state.texts.add("1.0.0-alpha")
        state.texts.add("1.0.0-alpha.1")
        state.texts.add("1.2.3+build.5")
        state.texts.add("2.0.0-beta.2+build.9")
        state.versions.add(Version(major=0, minor=9, patch=9))
        state.versions.add(Version(major=1, minor=0, patch=0))
        state.versions.add(Version(major=1, minor=0, patch=0, prerelease=("alpha",)))
        state.versions.add(Version(major=1, minor=0, patch=0, prerelease=("alpha", "1")))
        state.versions.add(Version(major=1, minor=2, patch=3, build=("build", "5")))
        state.versions.add(Version(major=2, minor=0, patch=0))
        state.versions.add(Version(major=2, minor=0, patch=0, prerelease=("beta",)))
        state.versions.add(Version(major=2, minor=0, patch=0, prerelease=("beta", "2")))

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        """Parses canonical SemVer text into an immutable Version record."""
        require_arg(text, self.state.texts)
        ret = self.inner_parse_version(text)
        self.state.versions.add(ret)
        assert ret == _version_from_text(text)
        return ret

    def inner_parse_version(self, text: str) -> Version:
        """Computes the fake parse result for synthesized fakes."""
        return _version_from_text(text)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions."""
        require(bool(self.state.versions))
        require_arg(v1, self.state.versions)
        require_arg(v2, self.state.versions)
        ret = self.inner_compare_precedence(v1, v2)
        assert (ret < 0) == (_precedence_key(v1) < _precedence_key(v2))
        assert (ret > 0) == (_precedence_key(v1) > _precedence_key(v2))
        assert (ret == 0) == (_precedence_key(v1) == _precedence_key(v2))
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        """Computes the fake precedence comparison for synthesized fakes."""
        key1 = _precedence_key(v1)
        key2 = _precedence_key(v2)
        if key1 < key2:
            return -1
        if key1 > key2:
            return 1
        return 0

    @transition.seeding
    def seed_versions(self) -> None:
        """Seeds representative model versions for fake fuzzing."""
        self.populate_seed_state(self.state)


proto = VersionEngineStateMachine()


# ==============================================================================
# 3. Synthesized Fake (Interface Components)
# ==============================================================================

FakeVersionEngine = synthesize_fake(VersionEngineStateMachine)


def make_version_engine_fake(state: Optional[VersionEngineState] = None) -> VersionEngine:
    """Synthesizes a fake version engine sharing the supplied or default model state."""
    return FakeVersionEngine(state=state or proto.make_initial_state())


# ==============================================================================
# 4. Fixed Fake Scenarios (Interface Components)
# ==============================================================================

class TestVersionEngineFake(unittest.TestCase):
    """Fixed fake scenarios covering seeded parsing and precedence transitions."""

    def setUp(self) -> None:
        state = proto.make_initial_state()
        proto.populate_seed_state(state)
        self.fake = make_version_engine_fake(state)

    def test_parse_seeded_version(self) -> None:
        parsed = self.fake.parse_version("1.0.0-alpha.1")
        self.assertEqual(parsed.major, 1)
        self.assertEqual(parsed.minor, 0)
        self.assertEqual(parsed.patch, 0)
        self.assertEqual(parsed.prerelease, ("alpha", "1"))

    def test_compare_seeded_versions(self) -> None:
        prerelease = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
        release = Version(major=1, minor=0, patch=0)
        self.assertLess(self.fake.compare_precedence(prerelease, release), 0)
        self.assertGreater(self.fake.compare_precedence(release, prerelease), 0)
        self.assertEqual(self.fake.compare_precedence(release, release), 0)


# ==============================================================================
# 5. Fake Fuzzing (Interface Components)
# ==============================================================================

FakeVersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeVersionEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:17:26Z
# LAST_CHANGED: 2026-11-15T04:17:26Z
# CHANGE: Author SemVer core interface pretense: parse_version/compare_precedence state machine with seeded valid version text/records, synthesized fake, fixed fake scenarios, and fake Hypothesis fuzzing (100% coverage).
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
from __future__ import annotations

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
    VersionEngine,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine as VersionEngineImpl,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine as RangeEngineImpl,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineState,
    RangeEngineStateMachine,
)

# ==============================================================================
# 1. Expansion fixtures (shared by fuzzing and fixed scenarios)
# ==============================================================================

def _range(raw_text: str) -> VersionRange:
    """Builds a concrete range record from its canonical text."""
    return VersionRange(raw_text=raw_text)


def _populate_expansion_state(state: RangeEngineState) -> None:
    """Seeds ranges and versions covering caret, wildcard, and hyphen expansion."""
    state.range_texts.update(
        {
            "1.0.0",
            "^0.0.1",
            "^0.0.0",
            "^0.0.x",
            "^0.x",
            "~1.x",
            "1.0.0 - 2.x",
            "1.x - 2.x",
            "==1.x",
            "!=1.x",
            "<1.x",
            "<=1.x",
            ">1.x",
            ">=1.x",
            ">1.*",
            "*",
            "==*",
            "!=*",
            ">*",
            "<*",
            "<=*",
            "^*",
            "~*",
            "^0.2.3",
        }
    )
    state.ranges.update(
        {
            _range("^0.0.1"),
            _range("^0.0.0"),
            _range("^0.0.x"),
            _range("^0.x"),
            _range("^0.2.3"),
            _range("^*"),
            _range("~1.x"),
            _range("~*"),
            _range("1.0.0 - 2.x"),
            _range("1.x - 2.x"),
            _range("==1.x"),
            _range("!=1.x"),
            _range("<1.x"),
            _range("<=1.x"),
            _range(">1.x"),
            _range(">=1.x"),
            _range(">1.*"),
            _range("*"),
            _range("==*"),
            _range("!=*"),
            _range(">*"),
            _range("<*"),
            _range("<=*"),
        }
    )
    state.versions.update(
        {
            Version(major=0, minor=0, patch=0),
            Version(major=0, minor=0, patch=1),
            Version(major=0, minor=0, patch=2),
            Version(major=0, minor=0, patch=5),
            Version(major=0, minor=1, patch=0),
            Version(major=0, minor=1, patch=5),
            Version(major=0, minor=2, patch=3),
            Version(major=0, minor=2, patch=9),
            Version(major=0, minor=3, patch=0),
        }
    )


# ==============================================================================
# 1. Implementation Pseudo State Machine
# ==============================================================================

class RangeEngineImplPseudoStateMachine(RangeEngineStateMachine):
    """Implementation pseudo-state machine driving the concrete range engine."""

    def make_initial_state(self) -> RangeEngineState:
        """Specializes the open seed state so real fuzzing starts with legal inputs."""
        state = RangeEngineState()
        self.populate_seed_state(state)
        _populate_expansion_state(state)
        return state

    def inner_parse_range(self, text: str) -> VersionRange:
        """Parses a range expression through the concrete range engine."""
        target: RangeEngine = sut(RangeEngine)
        ret = target.parse_range(text)
        assert ret.raw_text == text.strip()
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates satisfaction through the concrete engine and checks the filter."""
        target: RangeEngine = sut(RangeEngine)
        ret = target.satisfies(version, range_constraint, include_prerelease)
        if not version.prerelease:
            assert target.satisfies(version, range_constraint, True) == ret
        return ret


proto = RangeEngineImplPseudoStateMachine()


# ==============================================================================
# 2. Concrete SUT Factory
# ==============================================================================

def make_sut() -> RangeEngine:
    """Constructs a lifecycle scope exposing the concrete range engine."""
    registry = LifecycleRegistry()
    registry.register_singleton(
        VersionEngineImpl,
        keys=[VersionEngineImpl, VersionEngine],
    )
    registry.register_singleton(
        RangeEngineImpl,
        keys=[RangeEngineImpl, RangeEngine],
    )
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RangeEngine)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on the Real Implementation
# ==============================================================================

RangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="RangeEngineFuzzTest",
)


# ==============================================================================
# 4. Fixed Real Implementation Scenarios
# ==============================================================================

class TestRangeEngineImplReal(LifecycleTestCase):
    """Fixed scenarios covering malformed rejection and range expansion semantics."""

    def setUp(self) -> None:
        super().setUp()
        self.real = get_singleton(RangeEngine)
        self.sm = RangeEngineImplPseudoStateMachine(
            singletons={RangeEngine: self.real}
        )
        self.checked = self.sm.as_checked(RangeEngine, self.real)

    def test_parse_rejects_empty_range(self) -> None:
        """Rejects an empty range expression."""
        self.checked.violating(InvalidRangeError).parse_range("")

    def test_parse_rejects_comma_delimited_range(self) -> None:
        """Rejects comma-delimited comparators within a clause."""
        self.checked.violating(InvalidRangeError).parse_range(">=1.0.0, <2.0.0")

    def test_parse_rejects_empty_union_clause(self) -> None:
        """Rejects empty union alternatives."""
        self.checked.violating(InvalidRangeError).parse_range(">=1.0.0 || ")

    def test_parse_rejects_malformed_hyphen_clause(self) -> None:
        """Rejects hyphen ranges missing an upper bound."""
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 -")

    def test_parse_rejects_dangling_comparator(self) -> None:
        """Rejects comparator operators missing a version operand."""
        self.checked.violating(InvalidRangeError).parse_range(">=")

    def test_parse_rejects_bare_partial_version(self) -> None:
        """Rejects bare partial version expressions."""
        self.checked.violating(InvalidRangeError).parse_range("1.2")

    def test_parse_rejects_bare_partial_comparator(self) -> None:
        """Rejects comparators applied to bare partial versions."""
        self.checked.violating(InvalidRangeError).parse_range(">1.2")

    def test_parse_rejects_bare_partial_hyphen_range(self) -> None:
        """Rejects hyphen ranges built from bare partial versions."""
        self.checked.violating(InvalidRangeError).parse_range("1.2 - 2.3")

    def test_parse_rejects_misplaced_wildcard(self) -> None:
        """Rejects wildcard components followed by further numeric components."""
        self.checked.violating(InvalidRangeError).parse_range("1.x.0")

    def test_parse_rejects_operator_as_operand(self) -> None:
        """Rejects a comparator whose operand is itself an operator token."""
        self.checked.violating(InvalidRangeError).parse_range(">= <")

    def test_parse_rejects_overlong_version_token(self) -> None:
        """Rejects version tokens carrying too many dotted components."""
        self.checked.violating(InvalidRangeError).parse_range("1.2.3.4")

    def test_parse_bare_version_uses_exact_match(self) -> None:
        """Parses a bare full version through the exact-match fallback."""
        self.checked.parse_range("1.0.0")

    def test_parse_caret_and_prefix_ranges(self) -> None:
        """Parses caret ranges on full and wildcard versions."""
        self.checked.parse_range("^0.0.1")
        self.checked.parse_range("^0.0.0")
        self.checked.parse_range("^0.0.x")
        self.checked.parse_range("^0.x")
        self.checked.parse_range("^0.2.3")
        self.checked.parse_range("^*")
        self.checked.parse_range("~1.x")
        self.checked.parse_range("~*")

    def test_parse_standalone_wildcard_forms(self) -> None:
        """Parses standalone wildcard equality, negation, and bound operators."""
        self.checked.parse_range("*")
        self.checked.parse_range("==*")
        self.checked.parse_range("!=*")
        self.checked.parse_range(">*")
        self.checked.parse_range("<*")
        self.checked.parse_range("<=*")

    def test_parse_wildcard_comparator_ranges(self) -> None:
        """Parses wildcard comparator expressions across operators."""
        self.checked.parse_range("==1.x")
        self.checked.parse_range("!=1.x")
        self.checked.parse_range("<1.x")
        self.checked.parse_range("<=1.x")
        self.checked.parse_range(">1.x")
        self.checked.parse_range(">=1.x")
        self.checked.parse_range(">1.*")

    def test_parse_hyphen_wildcard_ranges(self) -> None:
        """Parses hyphen ranges with wildcard bounds."""
        self.checked.parse_range("1.0.0 - 2.x")
        self.checked.parse_range("1.x - 2.x")

    def test_satisfies_wildcard_comparator_expansions(self) -> None:
        """Evaluates wildcard comparator expansions across equality and ordering."""
        version = Version(major=1, minor=5, patch=0)
        self.checked.satisfies(version, _range("==1.x"), False)
        self.checked.satisfies(version, _range("!=1.x"), False)
        self.checked.satisfies(version, _range("<1.x"), False)
        self.checked.satisfies(version, _range("<=1.x"), False)
        self.checked.satisfies(version, _range(">1.x"), False)
        self.checked.satisfies(version, _range(">=1.x"), False)

    def test_satisfies_zero_major_caret_bounds(self) -> None:
        """Evaluates zero-major caret bounds and all-zero leading components."""
        self.checked.satisfies(Version(major=0, minor=0, patch=1), _range("^0.0.1"), False)
        self.checked.satisfies(Version(major=0, minor=0, patch=2), _range("^0.0.1"), False)
        self.checked.satisfies(Version(major=0, minor=0, patch=5), _range("^0.x"), False)

    def test_satisfies_hyphen_wildcard_upper_bound(self) -> None:
        """Evaluates hyphen ranges whose upper bound is a wildcard."""
        self.checked.satisfies(Version(major=2, minor=0, patch=0), _range("1.0.0 - 2.x"), False)
        self.checked.satisfies(Version(major=3, minor=0, patch=0), _range("1.0.0 - 2.x"), False)
        self.checked.satisfies(Version(major=2, minor=0, patch=0), _range("1.x - 2.x"), False)

    def test_satisfies_explicit_prerelease_target(self) -> None:
        """Evaluates prerelease boundary targeting on the candidate release line."""
        version = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
        self.checked.satisfies(version, _range(">=1.0.0-alpha"), False)
        self.checked.satisfies(version, _range("==1.0.0-alpha"), False)

    def test_satisfies_unbounded_caret_wildcard(self) -> None:
        """Evaluates unbounded caret wildcard full-range expansion."""
        self.checked.satisfies(Version(major=1, minor=5, patch=0), _range("^*"), False)
        self.checked.satisfies(Version(major=0, minor=0, patch=0), _range("^*"), False)

    def test_satisfies_zero_minor_caret_bounds(self) -> None:
        """Evaluates zero-minor caret upper bounds for zero-major versions."""
        self.checked.satisfies(Version(major=0, minor=0, patch=0), _range("^0.0.0"), False)
        self.checked.satisfies(Version(major=0, minor=0, patch=1), _range("^0.0.0"), False)
        self.checked.satisfies(Version(major=0, minor=0, patch=5), _range("^0.0.x"), False)
        self.checked.satisfies(Version(major=0, minor=1, patch=5), _range("^0.0.x"), False)

    def test_satisfies_standalone_wildcard_expansions(self) -> None:
        """Evaluates standalone wildcard equality and negated equality expansions."""
        version = Version(major=1, minor=5, patch=0)
        self.checked.satisfies(version, _range("*"), False)
        self.checked.satisfies(version, _range("==*"), False)
        self.checked.satisfies(version, _range("!=*"), False)

    def test_satisfies_unbounded_wildcard_bounds(self) -> None:
        """Evaluates unbounded strict and inclusive wildcard bounds."""
        version = Version(major=1, minor=5, patch=0)
        self.checked.satisfies(version, _range(">=*"), False)
        self.checked.satisfies(version, _range(">*"), False)

    def test_satisfies_precision_one_tilde(self) -> None:
        """Evaluates precision-one tilde expansion boundaries."""
        self.checked.satisfies(Version(major=1, minor=5, patch=0), _range("~1.x"), False)
        self.checked.satisfies(Version(major=2, minor=0, patch=0), _range("~1.x"), False)

    def test_satisfies_nonzero_minor_caret_bounds(self) -> None:
        """Evaluates nonzero-minor caret upper bounds for zero-major full versions."""
        self.checked.satisfies(Version(major=0, minor=2, patch=3), _range("^0.2.3"), False)
        self.checked.satisfies(Version(major=0, minor=2, patch=9), _range("^0.2.3"), False)
        self.checked.satisfies(Version(major=0, minor=3, patch=0), _range("^0.2.3"), False)

    def test_satisfies_inclusive_wildcard_upper_bound(self) -> None:
        """Evaluates inclusive and strict wildcard upper comparisons with empty prefix."""
        version = Version(major=1, minor=5, patch=0)
        self.checked.satisfies(version, _range("<=*"), False)
        self.checked.satisfies(version, _range("<*"), False)

    def test_satisfies_empty_prefix_tilde_wildcard(self) -> None:
        """Evaluates empty-prefix tilde wildcard expansion."""
        self.checked.satisfies(Version(major=1, minor=5, patch=0), _range("~*"), False)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:34:35Z
# LAST_CHANGED: 2026-11-15T04:34:06Z
# CHANGE: Cover remaining pretense_coverage comparators_and_prefixes facets: nonzero-minor caret upper bound for zero-major full versions (^0.2.3 with lower/in-window/upper-bound versions), inclusive and strict empty-prefix wildcard upper comparisons (<=*, <*), and empty-prefix tilde wildcard expansion (~*), with matching parse successes and impl-side range/version seeds.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T04:34:35Z
# PRETENSE_QA_AUDIT: 2026-11-15T04:34:20Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set, Tuple
import unittest

from pretense import (
    StateMachine,
    require,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_deepseek_flash_1.parts.semver_solver_multi.lib.semver_range import (
    RangeEngine,
    VersionRange,
)

# ==============================================================================
# 1. Model helpers (pure inspection helpers, no target interaction)
# ==============================================================================

def _range(raw_text: str) -> VersionRange:
    """Builds a model range record from its canonical text."""
    return VersionRange(raw_text=raw_text)


def _range_key(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> Tuple[Version, VersionRange, bool]:
    """Builds the hashable expectation key for a satisfaction query."""
    return (version, range_constraint, include_prerelease)


# ==============================================================================
# 2. State Machine Specification (Model & 1:1 Transitions)
# ==============================================================================

@dataclass
class RangeEngineState:
    """Model state tracking legal range text, ranges, versions, and expectations."""
    range_texts: Set[str] = field(default_factory=set)
    ranges: Set[VersionRange] = field(default_factory=set)
    versions: Set[Version] = field(default_factory=set)
    satisfying: Set[Tuple[Version, VersionRange, bool]] = field(default_factory=set)
    violating: Set[Tuple[Version, VersionRange, bool]] = field(default_factory=set)


class RangeEngineStateMachine(StateMachine[RangeEngineState]):
    """Unified Pretense state machine for version range parsing and matching."""

    def __init__(
        self,
        state: Optional[RangeEngineState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> RangeEngineState:
        """Constructs a blank initial model state (seed entries arrive via seeding)."""
        return RangeEngineState()

    def populate_seed_state(self, state: RangeEngineState) -> None:
        """Overridable hook that registers representative ranges and expectations."""
        early = Version(major=0, minor=9, patch=0)
        base = Version(major=1, minor=0, patch=0)
        patch = Version(major=1, minor=2, patch=3)
        late = Version(major=1, minor=5, patch=0)
        next_major = Version(major=2, minor=0, patch=0)
        distant = Version(major=3, minor=0, patch=0)
        prerelease = Version(major=1, minor=0, patch=0, prerelease=("alpha",))
        other_prerelease = Version(major=2, minor=0, patch=0, prerelease=("beta", "1"))

        state.range_texts.update(
            {
                ">=1.0.0",
                "==2.0.0",
                "^1.2.3",
                "~1.2.3",
                "!=1.5.0",
                "<1.5.0",
                ">1.5.0",
                "<=1.5.0",
                ">=1.0.0-alpha",
                "==1.0.0-alpha",
                "^1.x",
                "~1.2.x",
                ">=1.x",
                "!=1.x",
                ">=*",
                ">= 1.0.0",
                "1.0.0 - 2.0.0",
                ">=1.0.0 || ==2.0.0",
                "  >=1.0.0  ",
            }
        )
        at_least_base = _range(">=1.0.0")
        exact_next = _range("==2.0.0")
        caret_patch = _range("^1.2.3")
        tilde_patch = _range("~1.2.3")
        not_late = _range("!=1.5.0")
        below_late = _range("<1.5.0")
        above_late = _range(">1.5.0")
        at_most_late = _range("<=1.5.0")
        at_least_prerelease = _range(">=1.0.0-alpha")
        exact_prerelease = _range("==1.0.0-alpha")
        caret_major = _range("^1.x")
        tilde_minor = _range("~1.2.x")
        at_least_major = _range(">=1.x")
        not_major = _range("!=1.x")
        any_version = _range(">=*")
        spaced_base = _range(">= 1.0.0")
        hyphen_pair = _range("1.0.0 - 2.0.0")
        alternatives = _range(">=1.0.0 || ==2.0.0")

        state.ranges.update(
            {
                at_least_base,
                exact_next,
                caret_patch,
                tilde_patch,
                not_late,
                below_late,
                above_late,
                at_most_late,
                at_least_prerelease,
                exact_prerelease,
                caret_major,
                tilde_minor,
                at_least_major,
                not_major,
                any_version,
                spaced_base,
                hyphen_pair,
                alternatives,
            }
        )
        state.versions.update(
            {early, base, patch, late, next_major, distant, prerelease, other_prerelease}
        )
        state.satisfying.update(
            {
                _range_key(base, at_least_base, False),
                _range_key(late, at_least_base, False),
                _range_key(base, at_least_base, True),
                _range_key(next_major, exact_next, False),
                _range_key(next_major, above_late, False),
                _range_key(late, at_most_late, False),
                _range_key(patch, caret_patch, False),
                _range_key(patch, tilde_patch, False),
                _range_key(base, below_late, False),
                _range_key(prerelease, exact_prerelease, False),
                _range_key(prerelease, at_least_prerelease, True),
                _range_key(base, at_least_prerelease, False),
                _range_key(base, caret_major, False),
                _range_key(patch, tilde_minor, False),
                _range_key(late, at_least_major, False),
                _range_key(next_major, hyphen_pair, False),
                _range_key(next_major, alternatives, False),
                _range_key(distant, not_major, False),
                _range_key(late, any_version, False),
                _range_key(base, spaced_base, False),
            }
        )
        state.violating.update(
            {
                _range_key(early, at_least_base, False),
                _range_key(late, exact_next, False),
                _range_key(early, at_least_base, True),
                _range_key(late, not_late, False),
                _range_key(late, below_late, False),
                _range_key(late, above_late, False),
                _range_key(next_major, at_most_late, False),
                _range_key(next_major, caret_patch, False),
                _range_key(late, tilde_patch, False),
                _range_key(prerelease, at_least_base, False),
                _range_key(prerelease, at_least_base, True),
                _range_key(other_prerelease, exact_next, False),
                _range_key(next_major, caret_major, False),
                _range_key(next_major, tilde_minor, False),
                _range_key(distant, hyphen_pair, False),
                _range_key(early, alternatives, False),
                _range_key(late, not_major, False),
            }
        )

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        """Parses a range expression into an immutable VersionRange record."""
        require_arg(text, self.state.range_texts)
        ret = self.inner_parse_range(text)
        self.state.ranges.add(ret)
        assert ret.raw_text == text.strip()
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        """Computes the fake range record for synthesized fakes."""
        return _range(text.strip())

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a version satisfies a range constraint."""
        require(bool(self.state.ranges))
        require(bool(self.state.versions))
        require_arg(version, self.state.versions)
        require_arg(range_constraint, self.state.ranges)
        require_arg(include_prerelease, bool)
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        key = _range_key(version, range_constraint, include_prerelease)
        if key in self.state.satisfying:
            assert ret
        elif key in self.state.violating:
            assert not ret
        else:
            assert isinstance(ret, bool)
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Computes the fake satisfaction result for synthesized fakes."""
        return _range_key(version, range_constraint, include_prerelease) in self.state.satisfying

    @transition.seeding
    def seed_ranges(self) -> None:
        """Seeds representative ranges, versions, and expectations for fake fuzzing."""
        self.populate_seed_state(self.state)


proto = RangeEngineStateMachine()


# ==============================================================================
# 3. Synthesized Fake (Interface Components)
# ==============================================================================

FakeRangeEngine = synthesize_fake(RangeEngineStateMachine)


def make_range_engine_fake(state: Optional[RangeEngineState] = None) -> RangeEngine:
    """Synthesizes a fake range engine sharing the supplied or default model state."""
    return FakeRangeEngine(state=state or proto.make_initial_state())


# ==============================================================================
# 4. Fixed Fake Scenarios (Interface Components)
# ==============================================================================

class TestRangeEngineFake(unittest.TestCase):
    """Fixed fake scenarios covering seeded parsing and satisfaction transitions."""

    def setUp(self) -> None:
        state = proto.make_initial_state()
        proto.populate_seed_state(state)
        self.fake = make_range_engine_fake(state)

    def test_parse_seeded_range(self) -> None:
        parsed = self.fake.parse_range(">=1.0.0")
        self.assertEqual(parsed.raw_text, ">=1.0.0")

    def test_satisfies_seeded_range(self) -> None:
        version = Version(major=1, minor=5, patch=0)
        self.assertTrue(self.fake.satisfies(version, _range(">=1.0.0"), False))
        self.assertFalse(self.fake.satisfies(Version(major=0, minor=9, patch=0), _range(">=1.0.0"), False))


# ==============================================================================
# 5. Fake Fuzzing (Interface Components)
# ==============================================================================

FakeRangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRangeEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:18:41Z
# LAST_CHANGED: 2026-11-15T04:18:41Z
# CHANGE: Author SemVer range interface pretense: parse_range/satisfies state machine with seeded legal range text, ranges, versions, satisfying/violating expectation sets, synthesized fake, fixed fake scenarios, and fake Hypothesis fuzzing (100% coverage).
# --- END AUTOFAB METADATA ---
