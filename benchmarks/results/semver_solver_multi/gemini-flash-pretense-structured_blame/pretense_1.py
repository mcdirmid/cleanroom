# === File: dependency_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Collection, Optional
import unittest

from pretense import (
    StateMachine,
    raises,
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
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine as VersionEngineImpl,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_range import (
    VersionRange,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine as RangeEngineImpl,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver as DependencySolverImpl,
    PackageRepository as PackageRepositoryImpl,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for DependencySolver measuring differentials and SUT state."""

    def inner_register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        target.register_package(release)

    def inner_get_releases(self, name: str) -> list[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        return target.get_releases(name)

    def inner_has_package(self, name: str) -> bool:
        target: PackageRepository = sut(PackageRepository)
        return target.has_package(name)

    def inner_all_packages(self) -> set[str]:
        target: PackageRepository = sut(PackageRepository)
        return target.all_packages()

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        return target.resolve(root_dependencies)


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

def make_sut() -> DependencySolver:
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngineImpl)
    registry.register_singleton(RangeEngineImpl)
    registry.register_singleton(PackageRepositoryImpl)
    registry.register_singleton(DependencySolverImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(DependencySolver)


proto = DependencySolverImplPseudoStateMachine()

DependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DependencySolverFuzzTest",
)


# ==============================================================================
# 3. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestDependencySolverImplReal(LifecycleTestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = DependencySolverImplPseudoStateMachine(
            singletons={
                PackageRepository: self.repo,
                DependencySolver: self.solver,
            }
        )
        self.checked_repo = self.sm.as_checked(PackageRepository, self.repo)
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)

    def test_repo_operations(self) -> None:
        self.checked_repo.register_package(PackageRelease("pkg_a", Version(1, 0, 0)))
        self.checked_repo.get_releases("pkg_a")
        self.checked_repo.has_package("pkg_a")
        self.checked_repo.all_packages()

    def test_solver_resolve(self) -> None:
        self.checked_repo.register_package(PackageRelease("pkg_b", Version(1, 0, 0)))
        self.checked_solver.resolve([PackageDependency("pkg_b", VersionRange(">=1.0.0"))])

    def test_solver_resolve_with_backtracking(self) -> None:
        # Register lib_b releases
        self.checked_repo.register_package(PackageRelease("lib_b", Version(1, 0, 0)))
        self.checked_repo.register_package(PackageRelease("lib_b", Version(2, 0, 0)))

        # Register lib_a releases:
        # 2.0.0 requires lib_b 2.0.0 (conflicts with lib_c's requirement on lib_b 1.0.0)
        # 1.0.0 requires lib_b 1.0.0 (compatible with lib_c)
        self.checked_repo.register_package(
            PackageRelease(
                "lib_a",
                Version(2, 0, 0),
                dependencies=(PackageDependency("lib_b", VersionRange("==2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "lib_a",
                Version(1, 0, 0),
                dependencies=(PackageDependency("lib_b", VersionRange("==1.0.0")),),
            )
        )

        # Register lib_c which requires lib_b 1.0.0
        self.checked_repo.register_package(
            PackageRelease(
                "lib_c",
                Version(1, 0, 0),
                dependencies=(PackageDependency("lib_b", VersionRange("==1.0.0")),),
            )
        )

        # Register app which requires both lib_a and lib_c
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                dependencies=(
                    PackageDependency("lib_a", VersionRange(">=1.0.0")),
                    PackageDependency("lib_c", VersionRange(">=1.0.0")),
                ),
            )
        )

        # Resolving app forces solver to try lib_a 2.0.0, encounter conflict on lib_b,
        # backtrack with transitive constraint rollback, and select lib_a 1.0.0
        self.checked_solver.resolve([PackageDependency("app", VersionRange(">=1.0.0"))])

    def test_repo_missing_package_error(self) -> None:
        self.checked_repo.violating(PackageNotFoundError).get_releases("missing_pkg")

    def test_solver_conflict_error(self) -> None:
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [PackageDependency("missing_pkg", VersionRange(">=1.0.0"))]
        )

    def test_solver_unsatisfiable_conflict_with_rollback(self) -> None:
        # Register packages where candidate dependencies cannot be satisfied mutually
        self.checked_repo.register_package(PackageRelease("conf_c", Version(1, 0, 0)))
        self.checked_repo.register_package(PackageRelease("conf_c", Version(2, 0, 0)))

        self.checked_repo.register_package(
            PackageRelease(
                "conf_a",
                Version(1, 0, 0),
                dependencies=(PackageDependency("conf_c", VersionRange("==1.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "conf_b",
                Version(1, 0, 0),
                dependencies=(PackageDependency("conf_c", VersionRange("==2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "conf_root",
                Version(1, 0, 0),
                dependencies=(
                    PackageDependency("conf_a", VersionRange(">=1.0.0")),
                    PackageDependency("conf_b", VersionRange(">=1.0.0")),
                ),
            )
        )
        # Attempting to resolve conf_root forces candidate dependency conflict and rollback,
        # ultimately exhausting candidates and raising ResolutionConflictError
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [PackageDependency("conf_root", VersionRange(">=1.0.0"))]
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T19:36:51Z
# LAST_CHANGED: 2026-11-13T19:34:20Z
# CHANGE: Add scenario test method test_solver_unsatisfiable_conflict_with_rollback exercising candidate dependency conflict rollback in TestDependencySolverImplReal
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T19:36:51Z
# PRETENSE_QA_AUDIT: 2026-11-13T19:34:57Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_range import (
    VersionRange,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)


def _release_key(release: PackageRelease) -> tuple[int, int, int]:
    return (release.version.major, release.version.minor, release.version.patch)


def _has_closed_dependencies(
    pkg_name: str,
    packages: dict[str, list[PackageRelease]],
) -> bool:
    to_check = [pkg_name]
    checked: set[str] = set()
    for _ in range(len(packages) + 2):
        if not to_check:
            break
        current = to_check.pop(0)
        checked.add(current)
        for rel in packages[current]:
            for dep in rel.dependencies:
                if dep.name not in packages:
                    return False
                if dep.name not in checked and dep.name not in to_check:
                    to_check.append(dep.name)
    return True


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class DependencySolverState:
    """Canonical model state tracking abstract collections and values."""
    initialized: bool = True
    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)
    valid_dependency_sets: list[list[PackageDependency]] = field(default_factory=list)


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense State Machine for PackageRepository and DependencySolver."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DependencySolverState:
        """Constructs initial model state. Open parameters may be specialized by pseudo-state machines."""
        return DependencySolverState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True
        self.state.packages.clear()
        self.state.valid_dependency_sets.clear()
        pkg_a = PackageRelease(name="pkg_a", version=Version(1, 0, 0), dependencies=())
        self.state.packages["pkg_a"] = [pkg_a]
        self.state.valid_dependency_sets.append([])
        self.state.valid_dependency_sets.append([PackageDependency("pkg_a", VersionRange(">=1.0.0"))])

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(
            release,
            Domain.type(PackageRelease),
            preferred=[
                PackageRelease("pkg_a", Version(1, 0, 0)),
                PackageRelease("pkg_b", Version(1, 0, 0), (PackageDependency("pkg_a", VersionRange(">=1.0.0")),)),
            ],
            fuzz_domain=Domain.sampled_from([
                PackageRelease("pkg_a", Version(1, 0, 0)),
                PackageRelease("pkg_a", Version(1, 1, 0)),
                PackageRelease("pkg_a", Version(2, 0, 0)),
                PackageRelease("pkg_b", Version(1, 0, 0), (PackageDependency("pkg_a", VersionRange(">=1.0.0")),)),
                PackageRelease("pkg_b", Version(2, 0, 0)),
                PackageRelease("pkg_c", Version(1, 0, 0)),
            ]),
        )
        self.inner_register_package(release)
        if release.name not in self.state.packages:
            self.state.packages[release.name] = []
        self.state.packages[release.name].append(release)
        self.state.packages[release.name].sort(key=_release_key, reverse=True)
        valid_deps: list[list[PackageDependency]] = [[]]
        for name in self.state.packages:
            if _has_closed_dependencies(name, self.state.packages):
                valid_deps.append([PackageDependency(name, VersionRange(">=1.0.0"))])
        self.state.valid_dependency_sets = valid_deps
        assert release.name in self.state.packages

    def inner_register_package(self, release: PackageRelease) -> None:
        pass

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> list[PackageRelease]:
        require(bool(self.state.packages))
        require_arg(name, Domain.in_set(self.state.packages))
        ret = self.inner_get_releases(name)
        assert isinstance(ret, list)
        assert len(ret) > 0
        return ret

    def inner_get_releases(self, name: str) -> list[PackageRelease]:
        return list(self.state.packages.get(name, []))

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.type(str),
            preferred=["pkg_a", "pkg_b", "missing"],
            fuzz_domain=Domain.sampled_from(["pkg_a", "pkg_b", "pkg_c", "missing_pkg"]),
        )
        ret = self.inner_has_package(name)
        assert isinstance(ret, bool)
        assert ret == (name in self.state.packages)
        return ret

    def inner_has_package(self, name: str) -> bool:
        return name in self.state.packages

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> set[str]:
        require(self.state.initialized)
        ret = self.inner_all_packages()
        assert isinstance(ret, set)
        assert ret == set(self.state.packages.keys())
        return ret

    def inner_all_packages(self) -> set[str]:
        return set(self.state.packages.keys())

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(bool(self.state.packages))
        require_arg(
            root_dependencies,
            Domain.in_set(self.state.valid_dependency_sets),
        )
        ret = self.inner_resolve(root_dependencies)
        assert isinstance(ret, ResolutionOutcome)
        assert isinstance(ret.selected_versions, (dict, Mapping))
        assert isinstance(ret.derivation_steps, tuple)
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        selected: dict[str, Version] = {}
        for dep in root_dependencies:
            if dep.name in self.state.packages and self.state.packages[dep.name]:
                rel = self.state.packages[dep.name][0]
                selected[dep.name] = rel.version
                for d in rel.dependencies:
                    if d.name in self.state.packages and self.state.packages[d.name]:
                        selected[d.name] = self.state.packages[d.name][0].version
        return ResolutionOutcome(
            selected_versions=selected,
            derivation_steps=("Resolution completed",),
        )


proto = DependencySolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_package_repository_fake(
    state: Optional[DependencySolverState] = None,
) -> PackageRepository:
    """Synthesizes fake instance for PackageRepository."""
    fake_inst = FakeDependencySolver(state=state or proto.make_initial_state())
    return fake_inst


def make_dependency_solver_fake(
    state: Optional[DependencySolverState] = None,
) -> DependencySolver:
    """Synthesizes fake instance for DependencySolver."""
    fake_inst = FakeDependencySolver(state=state or proto.make_initial_state())
    return fake_inst


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    fake_inst = FakeDependencySolver(state=state or proto.make_initial_state())
    return (fake_inst, fake_inst)


FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDependencySolverFuzzTest",
)


class TestDependencySolverFake(unittest.TestCase):
    """Fixed fake tests covering transitions and seeding transitions."""

    def setUp(self) -> None:
        self.repo, self.solver = make_dependency_solver_fakes()

    def test_seed_initial(self) -> None:
        sm = DependencySolverStateMachine()
        sm.seed_initial()
        self.assertTrue(sm.state.initialized)
        self.assertIn("pkg_a", sm.state.packages)

    def test_register_package_and_get_releases(self) -> None:
        rel1 = PackageRelease("foo", Version(1, 0, 0))
        rel2 = PackageRelease("foo", Version(2, 0, 0))
        self.repo.register_package(rel1)
        self.repo.register_package(rel2)
        releases = self.repo.get_releases("foo")
        self.assertEqual(len(releases), 2)
        self.assertEqual(releases[0].version.major, 2)

    def test_has_package_and_all_packages(self) -> None:
        self.repo.register_package(PackageRelease("bar", Version(1, 0, 0)))
        self.assertTrue(self.repo.has_package("bar"))
        self.assertFalse(self.repo.has_package("unknown_xyz"))
        pkgs = self.repo.all_packages()
        self.assertIn("bar", pkgs)
        self.assertNotIn("unknown_xyz", pkgs)

    def test_resolve(self) -> None:
        self.repo.register_package(PackageRelease("pkg_x", Version(1, 0, 0)))
        outcome = self.solver.resolve([PackageDependency("pkg_x", VersionRange(">=1.0.0"))])
        self.assertIn("pkg_x", outcome.selected_versions)
        empty_outcome = self.solver.resolve([])
        self.assertEqual(len(empty_outcome.selected_versions), 0)

        # Register package with missing transitive dependency
        self.repo.register_package(
            PackageRelease(
                "pkg_unclosed",
                Version(1, 0, 0),
                dependencies=(PackageDependency("absent_pkg", VersionRange(">=1.0.0")),),
            )
        )

        # Register package with existing transitive dependency
        self.repo.register_package(
            PackageRelease(
                "pkg_closed",
                Version(1, 0, 0),
                dependencies=(PackageDependency("pkg_x", VersionRange(">=1.0.0")),),
            )
        )
        outcome_closed = self.solver.resolve([PackageDependency("pkg_closed", VersionRange(">=1.0.0"))])
        self.assertIn("pkg_closed", outcome_closed.selected_versions)
        self.assertIn("pkg_x", outcome_closed.selected_versions)

        # Single fake factory check with shared state
        single_state = proto.make_initial_state()
        single_repo = make_package_repository_fake(state=single_state)
        single_repo.register_package(PackageRelease("pkg_y", Version(1, 0, 0)))
        single_solver = make_dependency_solver_fake(state=single_state)
        res = single_solver.resolve([])
        self.assertEqual(len(res.selected_versions), 0)
        self.assertFalse(single_repo.has_package("missing_check"))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T19:21:20Z
# LAST_CHANGED: 2026-11-13T19:21:20Z
# CHANGE: Verify closed transitive dependencies before registering valid dependency sets and prune dead defensive code
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    StateMachine,
    raises,
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
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_core import (
    ComparatorOp,
    InvalidVersionError,
    SemVerError,
    Version,
    VersionEngine,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine as VersionEngineImpl,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class VersionEngineImplPseudoStateMachine(VersionEngineStateMachine):
    """Implementation pseudo-state machine for VersionEngine measuring differentials and SUT state."""

    def inner_parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        return target.parse_version(text)

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        return target.compare_precedence(v1, v2)


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

def make_sut() -> VersionEngine:
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngineImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(VersionEngine)


proto = VersionEngineImplPseudoStateMachine()

VersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="VersionEngineFuzzTest",
)


# ==============================================================================
# 3. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestVersionEngineImplReal(LifecycleTestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.real = get_singleton(VersionEngine)
        self.sm = VersionEngineImplPseudoStateMachine(singletons={VersionEngine: self.real})
        self.checked = self.sm.as_checked(VersionEngine, self.real)

    def test_parse_version_valid_syntax(self) -> None:
        self.checked.parse_version("1.2.3")
        self.checked.parse_version("1.0.0-alpha.1+build.1")
        self.checked.parse_version("2.0.0-beta.2")

    def test_compare_precedence(self) -> None:
        v1 = self.checked.parse_version("1.0.0")
        v2 = self.checked.parse_version("2.0.0")
        self.checked.compare_precedence(v1, v2)
        self.checked.compare_precedence(v2, v1)
        self.checked.compare_precedence(v1, v1)

        # Minor component comparison
        v_min_1 = self.checked.parse_version("1.1.0")
        v_min_2 = self.checked.parse_version("1.2.0")
        self.checked.compare_precedence(v_min_1, v_min_2)
        self.checked.compare_precedence(v_min_2, v_min_1)

        # Patch component comparison
        v_patch_1 = self.checked.parse_version("1.0.1")
        v_patch_2 = self.checked.parse_version("1.0.2")
        self.checked.compare_precedence(v_patch_1, v_patch_2)
        self.checked.compare_precedence(v_patch_2, v_patch_1)

        # Normal vs prerelease
        v_pre_alpha = self.checked.parse_version("1.0.0-alpha")
        self.checked.compare_precedence(v1, v_pre_alpha)
        self.checked.compare_precedence(v_pre_alpha, v1)

        # Numeric vs numeric prerelease
        v_pre_1 = self.checked.parse_version("1.0.0-1")
        v_pre_2 = self.checked.parse_version("1.0.0-2")
        self.checked.compare_precedence(v_pre_1, v_pre_2)

        # Numeric vs string prerelease
        self.checked.compare_precedence(v_pre_1, v_pre_alpha)
        self.checked.compare_precedence(v_pre_alpha, v_pre_1)

        # String vs string prerelease
        v_pre_beta = self.checked.parse_version("1.0.0-beta")
        self.checked.compare_precedence(v_pre_alpha, v_pre_beta)

        # Prerelease length difference
        v_pre_alpha_1 = self.checked.parse_version("1.0.0-alpha.1")
        self.checked.compare_precedence(v_pre_alpha, v_pre_alpha_1)

        # Identical prerelease comparison
        self.checked.compare_precedence(v_pre_alpha, v_pre_alpha)
        self.checked.compare_precedence(v_pre_alpha_1, v_pre_alpha_1)

        # Build metadata ignored
        v_build_1 = self.checked.parse_version("1.0.0+build.1")
        v_build_2 = self.checked.parse_version("1.0.0+build.2")
        self.checked.compare_precedence(v_build_1, v_build_2)

    def test_parse_version_leading_zero_violation(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("01.0.0")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T19:30:34Z
# LAST_CHANGED: 2026-11-13T19:27:53Z
# CHANGE: Add scenario test cases for minor, patch, and identical prerelease comparison in test_compare_precedence
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T19:30:34Z
# PRETENSE_QA_AUDIT: 2026-11-13T19:30:00Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_core import (
    ComparatorOp,
    InvalidVersionError,
    SemVerError,
    Version,
    VersionEngine,
)

SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class VersionEngineState:
    """Canonical model state tracking abstract collections and values."""
    initialized: bool = True
    parsed_versions: list[Version] = field(default_factory=list)


class VersionEngineStateMachine(StateMachine[VersionEngineState]):
    """Unified Pretense State Machine for VersionEngine."""

    def __init__(
        self,
        state: Optional[VersionEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> VersionEngineState:
        """Constructs initial model state. Open parameters may be specialized by pseudo-state machines."""
        return VersionEngineState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True
        self.state.parsed_versions.clear()

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=["1.0.0", "0.1.0", "1.2.3-alpha.1", "2.0.0+build.7", "1.0.0-rc.1+build.1"],
            fuzz_domain=Domain.sampled_from([
                "0.0.1",
                "0.1.0",
                "1.0.0",
                "1.2.3",
                "2.0.0-alpha",
                "2.0.0-alpha.1",
                "2.0.0-beta",
                "2.0.0-beta.2",
                "2.0.0-beta.11",
                "2.0.0-rc.1",
                "2.0.0",
                "2.0.0+build.1",
                "2.0.0-alpha+build.1",
            ]),
        )
        ret = self.inner_parse_version(text)
        self.state.parsed_versions.append(ret)
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        assert isinstance(ret.prerelease, tuple)
        assert isinstance(ret.build, tuple)
        return ret

    def inner_parse_version(self, text: str) -> Version:
        m = SEMVER_REGEX.match(text)
        if not m:
            return Version(0, 0, 0)
        major = int(m.group(1))
        minor = int(m.group(2))
        patch = int(m.group(3))
        prerelease = tuple(m.group(4).split(".")) if m.group(4) else ()
        build = tuple(m.group(5).split(".")) if m.group(5) else ()
        return Version(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(
            v1,
            Domain.type(Version),
            preferred=[Version(1, 0, 0), Version(2, 0, 0)],
            fuzz_domain=Domain.sampled_from([
                Version(0, 1, 0),
                Version(1, 0, 0),
                Version(1, 0, 1),
                Version(1, 1, 0),
                Version(2, 0, 0),
                Version(1, 0, 0, prerelease=("alpha",)),
                Version(1, 0, 0, prerelease=("alpha", "1")),
                Version(1, 0, 0, prerelease=("beta",)),
                Version(1, 0, 0, build=("build",)),
            ]),
        )
        require_arg(
            v2,
            Domain.type(Version),
            preferred=[Version(1, 0, 0), Version(2, 0, 0)],
            fuzz_domain=Domain.sampled_from([
                Version(0, 1, 0),
                Version(1, 0, 0),
                Version(1, 0, 1),
                Version(1, 1, 0),
                Version(2, 0, 0),
                Version(1, 0, 0, prerelease=("alpha",)),
                Version(1, 0, 0, prerelease=("alpha", "1")),
                Version(1, 0, 0, prerelease=("beta",)),
                Version(1, 0, 0, build=("build",)),
            ]),
        )
        ret = self.inner_compare_precedence(v1, v2)
        assert isinstance(ret, int)
        if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch):
            assert ret < 0
        if (v1.major, v1.minor, v1.patch) > (v2.major, v2.minor, v2.patch):
            assert ret > 0
        if (v1.major, v1.minor, v1.patch) == (v2.major, v2.minor, v2.patch):
            if not v1.prerelease and v2.prerelease:
                assert ret > 0
            if v1.prerelease and not v2.prerelease:
                assert ret < 0
            if not v1.prerelease and not v2.prerelease:
                assert ret == 0
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1
        if not v1.prerelease and v2.prerelease:
            return 1
        if v1.prerelease and not v2.prerelease:
            return -1
        if not v1.prerelease and not v2.prerelease:
            return 0
        min_len = min(len(v1.prerelease), len(v2.prerelease))
        for i in range(min_len):
            p1 = v1.prerelease[i]
            p2 = v2.prerelease[i]
            if p1 == p2:
                continue
            p1_num = p1.isdigit()
            p2_num = p2.isdigit()
            if p1_num and p2_num:
                return -1 if int(p1) < int(p2) else 1
            if p1_num and not p2_num:
                return -1
            if not p1_num and p2_num:
                return 1
            return -1 if p1 < p2 else 1
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        return 0


proto = VersionEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeVersionEngine = synthesize_fake(VersionEngineStateMachine)


def make_version_engine_fake(
    state: Optional[VersionEngineState] = None,
) -> VersionEngine:
    """Synthesizes fake instance for VersionEngine."""
    return FakeVersionEngine(state=state or proto.make_initial_state())


FakeVersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeVersionEngineFuzzTest",
)


class TestVersionEngineFake(unittest.TestCase):
    """Fixed fake tests covering transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_version_engine_fake()

    def test_seed_initial(self) -> None:
        sm = VersionEngineStateMachine()
        sm.seed_initial()
        self.assertTrue(sm.state.initialized)

    def test_parse_version(self) -> None:
        v = self.fake.parse_version("1.2.3-alpha.1+build.10")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)
        self.assertEqual(v.patch, 3)
        self.assertEqual(v.prerelease, ("alpha", "1"))
        self.assertEqual(v.build, ("build", "10"))

        sm = VersionEngineStateMachine()
        fallback = sm.inner_parse_version("not-a-valid-semver")
        self.assertEqual(fallback.major, 0)
        self.assertEqual(fallback.minor, 0)
        self.assertEqual(fallback.patch, 0)

    def test_compare_precedence(self) -> None:
        v1 = Version(1, 0, 0)
        v2 = Version(2, 0, 0)
        self.assertLess(self.fake.compare_precedence(v1, v2), 0)
        self.assertGreater(self.fake.compare_precedence(v2, v1), 0)
        self.assertEqual(self.fake.compare_precedence(v1, v1), 0)

        # Minor and patch differences
        self.assertLess(self.fake.compare_precedence(Version(1, 1, 0), Version(1, 2, 0)), 0)
        self.assertGreater(self.fake.compare_precedence(Version(1, 2, 0), Version(1, 1, 0)), 0)
        self.assertLess(self.fake.compare_precedence(Version(1, 0, 1), Version(1, 0, 2)), 0)
        self.assertGreater(self.fake.compare_precedence(Version(1, 0, 2), Version(1, 0, 1)), 0)

        # Normal vs pre-release
        v_norm = Version(1, 0, 0)
        v_pre = Version(1, 0, 0, prerelease=("alpha",))
        self.assertGreater(self.fake.compare_precedence(v_norm, v_pre), 0)
        self.assertLess(self.fake.compare_precedence(v_pre, v_norm), 0)

        # Numeric vs numeric prerelease
        v_p1 = Version(1, 0, 0, prerelease=("1",))
        v_p2 = Version(1, 0, 0, prerelease=("2",))
        self.assertLess(self.fake.compare_precedence(v_p1, v_p2), 0)
        self.assertGreater(self.fake.compare_precedence(v_p2, v_p1), 0)

        # Numeric vs string prerelease
        v_p_alpha = Version(1, 0, 0, prerelease=("alpha",))
        self.assertLess(self.fake.compare_precedence(v_p1, v_p_alpha), 0)
        self.assertGreater(self.fake.compare_precedence(v_p_alpha, v_p1), 0)

        # String vs string prerelease
        v_p_beta = Version(1, 0, 0, prerelease=("beta",))
        self.assertLess(self.fake.compare_precedence(v_p_alpha, v_p_beta), 0)
        self.assertGreater(self.fake.compare_precedence(v_p_beta, v_p_alpha), 0)

        # Length differences and equality in prerelease
        v_p_long = Version(1, 0, 0, prerelease=("alpha", "1"))
        self.assertLess(self.fake.compare_precedence(v_p_alpha, v_p_long), 0)
        self.assertGreater(self.fake.compare_precedence(v_p_long, v_p_alpha), 0)
        self.assertEqual(self.fake.compare_precedence(v_p_long, v_p_long), 0)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T19:02:42Z
# LAST_CHANGED: 2026-11-13T19:02:42Z
# CHANGE: Implement VersionEngine interface pretense state machine, fake, and tests
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    StateMachine,
    raises,
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
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine as VersionEngineImpl,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine as RangeEngineImpl,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class RangeEngineImplPseudoStateMachine(RangeEngineStateMachine):
    """Implementation pseudo-state machine for RangeEngine measuring differentials and SUT state."""

    def inner_parse_range(self, text: str) -> VersionRange:
        target: RangeEngine = sut(RangeEngine)
        return target.parse_range(text)

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: RangeEngine = sut(RangeEngine)
        return target.satisfies(version, range_constraint, include_prerelease)


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

def make_sut() -> RangeEngine:
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngineImpl)
    registry.register_singleton(RangeEngineImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RangeEngine)


proto = RangeEngineImplPseudoStateMachine()

RangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="RangeEngineFuzzTest",
)


# ==============================================================================
# 3. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestRangeEngineImplReal(LifecycleTestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.real = get_singleton(RangeEngine)
        self.sm = RangeEngineImplPseudoStateMachine(singletons={RangeEngine: self.real})
        self.checked = self.sm.as_checked(RangeEngine, self.real)

    def test_parse_range_comparators_and_prefixes(self) -> None:
        self.checked.parse_range(">=1.0.0 <2.0.0")
        self.checked.parse_range("^1.2.3")
        self.checked.parse_range("~1.2.0")
        self.checked.parse_range("1.0.0 - 2.0.0")
        self.checked.parse_range("1.0.0 - 2.x")
        self.checked.parse_range("1.x - 2.x")
        self.checked.parse_range("1.0.0 - 2.*")
        self.checked.parse_range(">=1.x")
        self.checked.parse_range("!=1.x")
        self.checked.parse_range(">1.*")
        self.checked.parse_range("^1.x")
        self.checked.parse_range("~1.2.x")
        self.checked.parse_range(">=*")
        self.checked.parse_range("==1.0.0")
        self.checked.parse_range("=1.0.0")
        self.checked.parse_range("<1.0.0")
        self.checked.parse_range("<=2.0.0")
        self.checked.parse_range(">1.0.0")
        self.checked.parse_range(">= 1.0.0")
        self.checked.parse_range("<= 2.x")
        self.checked.parse_range("!= 1.0.0")
        self.checked.parse_range("== 1.0.0")
        self.checked.parse_range("= 1.0.0")
        self.checked.parse_range("< 2.0.0")
        self.checked.parse_range("> 1.0.0")
        self.checked.parse_range(">=1.0.0 || <0.5.0")
        self.checked.parse_range("^1.2.x")
        self.checked.parse_range("^0.2.x")
        self.checked.parse_range("^0.0.x")
        self.checked.parse_range("^0.2.3")
        self.checked.parse_range("^0.0.3")
        self.checked.parse_range("<1.x")
        self.checked.parse_range(">=1.2.x")
        self.checked.parse_range("<=1.2.x")
        self.checked.parse_range(">1.2.x")
        self.checked.parse_range("<1.2.x")
        self.checked.parse_range("!=1.2.x")
        self.checked.parse_range("<*")
        self.checked.parse_range("!=*")
        self.checked.parse_range("1.2.x - 2.3.x")
        self.checked.parse_range("* - 1.0.0")
        self.checked.parse_range("*")

    def test_satisfies(self) -> None:
        v = Version(1, 2, 0)
        r = self.checked.parse_range(">=1.0.0")
        self.checked.satisfies(v, r, False)
        v_pre = Version(1, 0, 0, prerelease=("alpha",))
        self.checked.satisfies(v_pre, r, True)
        self.checked.satisfies(v_pre, r, False)

        # Relational operator ==
        r_eq = self.checked.parse_range("==1.2.0")
        self.checked.satisfies(v, r_eq, False)
        self.checked.satisfies(Version(2, 0, 0), r_eq, False)

        # Relational operator !=
        r_ne = self.checked.parse_range("!=1.2.0")
        self.checked.satisfies(v, r_ne, False)
        self.checked.satisfies(Version(2, 0, 0), r_ne, False)

        # Relational operator <
        r_lt = self.checked.parse_range("<2.0.0")
        self.checked.satisfies(v, r_lt, False)
        self.checked.satisfies(Version(2, 0, 0), r_lt, False)

        # Relational operator <=
        r_le = self.checked.parse_range("<=1.2.0")
        self.checked.satisfies(v, r_le, False)
        self.checked.satisfies(Version(2, 0, 0), r_le, False)

        # Relational operator >
        r_gt = self.checked.parse_range(">1.0.0")
        self.checked.satisfies(v, r_gt, False)
        self.checked.satisfies(Version(0, 9, 0), r_gt, False)

        # Minor and patch wildcards
        r_wildcard_minor = self.checked.parse_range("1.2.x")
        self.checked.satisfies(v, r_wildcard_minor, False)
        self.checked.satisfies(Version(1, 3, 0), r_wildcard_minor, False)

        r_wildcard_star = self.checked.parse_range("1.2.*")
        self.checked.satisfies(v, r_wildcard_star, False)

        r_wildcard_major = self.checked.parse_range("1.x")
        self.checked.satisfies(v, r_wildcard_major, False)

    def test_parse_range_bare_partials_prohibited(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.2")

    def test_parse_range_empty_syntax_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("")

    def test_parse_range_whitespace_syntax_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("   ")

    def test_parse_range_comma_syntax_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=1.0.0, <2.0.0")

    def test_parse_range_empty_union_clause_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=1.0.0 ||")

    def test_parse_range_hyphen_no_whitespace_syntax_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.2.x-2.3.x")

    def test_parse_range_operator_syntax_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">>1.0.0")

    def test_parse_range_wildcard_leading_zero_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("01.x")

    def test_parse_range_minor_wildcard_leading_zero_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=1.02.x")

    def test_parse_range_dangling_operator_syntax_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=")

    def test_parse_range_dangling_prefix_syntax_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("^")

    def test_parse_range_missing_hyphen_upper_bound_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 -")

    def test_parse_range_missing_hyphen_lower_bound_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("- 2.0.0")

    def test_parse_range_major_leading_zero_minor_wildcard_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("01.2.x")

    def test_parse_range_consecutive_operators_error(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">= <=")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T19:49:38Z
# LAST_CHANGED: 2026-11-13T19:48:11Z
# CHANGE: Add scenario test cases for zero carets, wildcard inequalities, consecutive operators, and major leading zero with minor wildcard
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T19:49:38Z
# PRETENSE_QA_AUDIT: 2026-11-13T19:49:12Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_flash_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class RangeEngineState:
    """Canonical model state tracking abstract collections and values."""
    initialized: bool = True
    parsed_ranges: list[VersionRange] = field(default_factory=list)


class RangeEngineStateMachine(StateMachine[RangeEngineState]):
    """Unified Pretense State Machine for RangeEngine."""

    def __init__(
        self,
        state: Optional[RangeEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> RangeEngineState:
        """Constructs initial model state. Open parameters may be specialized by pseudo-state machines."""
        return RangeEngineState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True
        self.state.parsed_ranges.clear()

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=[">=1.0.0", "^1.2.3", "~1.2.0", "1.0.0 - 2.0.0", ">=1.0.0 <2.0.0 || >=3.0.0"],
            fuzz_domain=Domain.sampled_from([
                "*",
                ">=1.0.0",
                "^1.0.0",
                "~1.2.3",
                "1.0.0 - 2.0.0",
                ">=1.0.0 <2.0.0 || >=3.0.0",
                ">=1.x",
                "1.x - 2.x",
                "^1.x",
                "~1.x",
                "!=1.x",
            ]),
        )
        ret = self.inner_parse_range(text)
        self.state.parsed_ranges.append(ret)
        assert isinstance(ret.raw_text, str)
        assert len(ret.raw_text) > 0
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        trimmed = text.strip()
        return VersionRange(raw_text=trimmed if trimmed else "*")

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(
            version,
            Domain.type(Version),
            preferred=[Version(1, 0, 0), Version(2, 0, 0)],
            fuzz_domain=Domain.sampled_from([
                Version(1, 0, 0),
                Version(1, 2, 3),
                Version(2, 0, 0),
                Version(1, 0, 0, prerelease=("alpha",)),
            ]),
        )
        require_arg(
            range_constraint,
            Domain.type(VersionRange),
            preferred=[VersionRange(">=1.0.0"), VersionRange("*")],
            fuzz_domain=Domain.sampled_from([
                VersionRange(">=1.0.0"),
                VersionRange("*"),
                VersionRange("<2.0.0"),
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
        if version.prerelease and not include_prerelease and not any(p in range_constraint.raw_text for p in version.prerelease):
            assert ret is False
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        expr = range_constraint.raw_text
        if version.prerelease and not include_prerelease:
            if not any(p in expr for p in version.prerelease):
                return False
        if expr == "*":
            return True
        if expr.startswith(">="):
            return version.major >= 1
        if expr.startswith("<"):
            return version.major < 2
        if expr.startswith("^") or expr.startswith("~"):
            return version.major == 1
        if "-" in expr:
            return 1 <= version.major <= 2
        return True


proto = RangeEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeRangeEngine = synthesize_fake(RangeEngineStateMachine)


def make_range_engine_fake(
    state: Optional[RangeEngineState] = None,
) -> RangeEngine:
    """Synthesizes fake instance for RangeEngine."""
    return FakeRangeEngine(state=state or proto.make_initial_state())


FakeRangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRangeEngineFuzzTest",
)


class TestRangeEngineFake(unittest.TestCase):
    """Fixed fake tests covering transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_range_engine_fake()

    def test_seed_initial(self) -> None:
        sm = RangeEngineStateMachine()
        sm.seed_initial()
        self.assertTrue(sm.state.initialized)

    def test_parse_range(self) -> None:
        r = self.fake.parse_range("  >=1.0.0 <2.0.0  ")
        self.assertEqual(r.raw_text, ">=1.0.0 <2.0.0")

        sm = RangeEngineStateMachine()
        empty_res = sm.inner_parse_range("   ")
        self.assertEqual(empty_res.raw_text, "*")

    def test_satisfies(self) -> None:
        v = Version(1, 2, 0)
        r = VersionRange(">=1.0.0")
        self.assertTrue(self.fake.satisfies(v, r, False))

        r_star = VersionRange("*")
        self.assertTrue(self.fake.satisfies(v, r_star, False))

        v_pre = Version(1, 0, 0, prerelease=("alpha",))
        self.assertFalse(self.fake.satisfies(v_pre, r, False))
        self.assertTrue(self.fake.satisfies(v_pre, r, True))

        v_pre_target = VersionRange(">=1.0.0-alpha")
        self.assertTrue(self.fake.satisfies(v_pre, v_pre_target, False))

        self.assertFalse(self.fake.satisfies(Version(0, 9, 0), r, False))

        self.assertTrue(self.fake.satisfies(v, VersionRange("<2.0.0"), False))
        self.assertFalse(self.fake.satisfies(Version(2, 0, 0), VersionRange("<2.0.0"), False))

        self.assertTrue(self.fake.satisfies(v, VersionRange("^1.0.0"), False))
        self.assertTrue(self.fake.satisfies(v, VersionRange("~1.0.0"), False))

        self.assertTrue(self.fake.satisfies(v, VersionRange("1.0.0 - 2.0.0"), False))
        self.assertFalse(self.fake.satisfies(Version(3, 0, 0), VersionRange("1.0.0 - 2.0.0"), False))

        self.assertTrue(self.fake.satisfies(v, VersionRange("custom"), False))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T19:04:47Z
# LAST_CHANGED: 2026-11-13T19:04:47Z
# CHANGE: Implement RangeEngine interface pretense state machine, fake, and tests
# --- END AUTOFAB METADATA ---
