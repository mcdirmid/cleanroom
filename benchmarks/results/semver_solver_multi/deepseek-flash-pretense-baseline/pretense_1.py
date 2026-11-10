# === File: dependency_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for dependency solving."""

from __future__ import annotations

from typing import Collection, List, Set
import unittest

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverStateMachine,
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


class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for the concrete dependency solver."""

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        # Postcondition: the registered release becomes retrievable by package name.
        assert target.has_package(release.name)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        # Postcondition: every retrieved release belongs to the requested package.
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        # Postcondition: membership yields a boolean verdict.
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        # Postcondition: the collection of registered package names is a set of strings.
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self, root_dependencies: Collection[PackageDependency]
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        # Postcondition: derivation steps are recorded as an immutable sequence.
        assert isinstance(ret.derivation_steps, tuple)
        return ret


proto = DependencySolverImplPseudoStateMachine()


class TestDependencySolverImplReal(unittest.TestCase):
    """Verifies the concrete package repository and dependency solver against contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.repository = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = DependencySolverImplPseudoStateMachine(
            singletons={
                PackageRepository: self.repository,
                DependencySolver: self.solver,
            }
        )
        self.checked_repository = self.sm.as_checked(
            PackageRepository, self.repository
        )
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_register_and_query(self) -> None:
        self.checked_repository.register_package(
            PackageRelease("alpha", Version(1, 0, 0))
        )
        self.checked_repository.register_package(
            PackageRelease("alpha", Version(2, 0, 0))
        )
        self.checked_repository.register_package(
            PackageRelease("alpha", Version(1, 5, 0))
        )
        self.checked_repository.register_package(
            PackageRelease("beta", Version(1, 0, 0, ("alpha",)))
        )
        releases = self.checked_repository.get_releases("alpha")
        assert [release.version for release in releases] == [
            Version(2, 0, 0),
            Version(1, 5, 0),
            Version(1, 0, 0),
        ]
        assert self.checked_repository.has_package("alpha")
        assert not self.checked_repository.has_package("gamma")
        assert self.checked_repository.all_packages() == {"alpha", "beta"}

    def test_resolve_selects_highest_compatible(self) -> None:
        self.checked_repository.register_package(
            PackageRelease("alpha", Version(1, 0, 0))
        )
        self.checked_repository.register_package(
            PackageRelease("alpha", Version(2, 0, 0))
        )
        outcome = self.checked_solver.resolve(
            [PackageDependency("alpha", VersionRange(">=1.0.0"))]
        )
        assert outcome.selected_versions["alpha"] == Version(2, 0, 0)
        assert len(outcome.derivation_steps) >= 1

    def test_resolve_transitive_backtracking(self) -> None:
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(2, 0, 0),
                (PackageDependency("beta", VersionRange(">=2.0.0")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(1, 0, 0),
                (PackageDependency("beta", VersionRange(">=1.0.0")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease("beta", Version(1, 5, 0))
        )
        self.checked_repository.register_package(
            PackageRelease("beta", Version(1, 0, 0))
        )
        outcome = self.checked_solver.resolve(
            [PackageDependency("alpha", VersionRange(">=1.0.0"))]
        )
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)
        assert outcome.selected_versions["beta"] == Version(1, 5, 0)

    def test_resolve_missing_dependency_backtracks(self) -> None:
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(2, 0, 0),
                (PackageDependency("missing", VersionRange(">=1.0.0")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease("alpha", Version(1, 0, 0))
        )
        outcome = self.checked_solver.resolve(
            [PackageDependency("alpha", VersionRange(">=1.0.0"))]
        )
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)
        assert outcome.selected_versions.get("missing") is None

    def test_resolve_forward_check_against_assigned(self) -> None:
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(2, 0, 0),
                (PackageDependency("beta", VersionRange(">=2.0.0")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(1, 0, 0),
                (PackageDependency("beta", VersionRange(">=1.0.0")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease("beta", Version(1, 0, 0))
        )
        outcome = self.checked_solver.resolve(
            [
                PackageDependency("alpha", VersionRange(">=1.0.0")),
                PackageDependency("beta", VersionRange(">=1.0.0")),
            ]
        )
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)
        assert outcome.selected_versions["beta"] == Version(1, 0, 0)

    def test_resolve_nested_candidate_exhaustion(self) -> None:
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(2, 0, 0),
                (PackageDependency("beta", VersionRange(">=1.0.0")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease("alpha", Version(1, 0, 0))
        )
        self.checked_repository.register_package(
            PackageRelease(
                "beta",
                Version(1, 5, 0),
                (PackageDependency("gamma", VersionRange(">=2.0.0")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease(
                "beta",
                Version(1, 0, 0),
                (PackageDependency("gamma", VersionRange(">=3.0.0")),),
            )
        )
        outcome = self.checked_solver.resolve(
            [PackageDependency("alpha", VersionRange(">=1.0.0"))]
        )
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)
        assert outcome.selected_versions.get("beta") is None

    def test_resolve_unsatisfiable_conflict(self) -> None:
        self.checked_repository.register_package(
            PackageRelease("alpha", Version(1, 0, 0))
        )
        with self.assertRaises(ResolutionConflictError):
            self.checked_solver.resolve(
                [PackageDependency("alpha", VersionRange(">=2.0.0"))]
            )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: fd94e909ccf0
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for dependency solving."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
import unittest

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

from benchmark_2.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_2.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
)


@dataclass
class DependencySolverState:
    """Canonical model state for package repository and dependency solver operations."""

    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    outcomes: List[ResolutionOutcome] = field(default_factory=list)


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense state machine for the dependency solver interface."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DependencySolverState(), singletons=singletons)

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(release, Domain.type(PackageRelease))
        # Postcondition: the registered release becomes retrievable by its package name.
        ret = self.inner_register_package(release)
        self.state.packages.setdefault(release.name, []).append(release)
        assert release in self.state.packages[release.name]
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.packages)
        require_arg(name, Domain.type(str))
        # Postcondition: releases are returned in descending precedence order for a known package.
        ret = self.inner_get_releases(name)
        assert name in self.state.packages
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(name, Domain.type(str))
        # Postcondition: membership reflects whether the package is registered.
        ret = self.inner_has_package(name)
        assert ret == (name in self.state.packages)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        # Postcondition: the package name set matches the registered package keys.
        ret = self.inner_all_packages()
        assert ret == set(self.state.packages.keys())
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self, root_dependencies: Collection[PackageDependency]
    ) -> ResolutionOutcome:
        require_arg(
            root_dependencies,
            Domain.type(Collection[PackageDependency]),
        )
        # Postcondition: a successful resolution yields selected versions and derivation steps.
        ret: Any = self.inner_resolve(root_dependencies)
        self.state.outcomes.append(ret)
        assert self.state.outcomes[-1] == ret
        return ret

    @transition.seeding
    def seed_package(self) -> None:
        """Seeds a documented release into the blank package model state."""
        release: Any = self.inner_seed_package()
        self.state.packages.setdefault("sample", []).append(release)


proto = DependencySolverStateMachine()


FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageRepository, DependencySolver]:
    """Synthesizes a fake implementing every dependency solver target method."""
    fake = FakeDependencySolver(state=state or DependencySolverState())
    return (fake, fake)


class TestDependencySolverFake(unittest.TestCase):
    """Exercises every transition and seeding transition on the synthesized fake."""

    def setUp(self) -> None:
        self.fakes = make_dependency_solver_fakes()
        self.sm = DependencySolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_package()
        self.sm.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.sm.get_releases("alpha")
        self.sm.has_package("alpha")
        self.sm.all_packages()
        self.sm.resolve(
            [PackageDependency("alpha", VersionRange(">=1.0.0"))]
        )


FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 2058987ab284
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemVer core."""

from __future__ import annotations

import unittest

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.semver_solver_multi.pretense.semver_core_pretense import (
    SemverCoreStateMachine,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import VersionEngine
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)


class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine for the concrete SemVer core engine."""

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        # Postcondition: the canonical rendering round-trips the parsed version text.
        assert ret.format() == text
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        # Postcondition: precedence comparison is antisymmetric in sign.
        reverse = target.compare_precedence(v2, v1)
        assert (ret > 0 and reverse < 0) or (ret < 0 and reverse > 0) or (
            ret == 0 and reverse == 0
        )
        return ret


proto = SemverCoreImplPseudoStateMachine()


class TestSemverCoreImplReal(unittest.TestCase):
    """Verifies the concrete SemVer core engine against its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _sc_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(VersionEngine)
        self.sm = SemverCoreImplPseudoStateMachine(
            singletons={VersionEngine: self.real}
        )
        self.checked = self.sm.as_checked(VersionEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_variants(self) -> None:
        assert self.checked.parse_version("1.2.3") == Version(1, 2, 3)
        assert self.checked.parse_version("0.0.0") == Version(0, 0, 0)
        assert self.checked.parse_version("1.0.0-alpha.1") == Version(
            1, 0, 0, ("alpha", "1")
        )
        assert self.checked.parse_version("2.0.0+build.5") == Version(
            2, 0, 0, (), ("build", "5")
        )
        assert self.checked.parse_version("0.0.0-0.3.7+build.11") == Version(
            0, 0, 0, ("0", "3", "7"), ("build", "11")
        )
        assert self.checked.parse_version("1.0.0-alpha-x.0a") == Version(
            1, 0, 0, ("alpha-x", "0a")
        )

    def test_parse_version_rejects_invalid(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("1.0")

    def test_compare_precedence_ordering(self) -> None:
        assert self.checked.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)) < 0
        assert self.checked.compare_precedence(Version(2, 0, 0), Version(1, 0, 0)) > 0
        assert self.checked.compare_precedence(Version(1, 1, 0), Version(1, 2, 0)) < 0
        assert self.checked.compare_precedence(Version(1, 1, 2), Version(1, 1, 1)) > 0
        assert self.checked.compare_precedence(Version(1, 0, 0), Version(1, 0, 0)) == 0

    def test_compare_precedence_prerelease(self) -> None:
        assert self.checked.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, ("alpha",))) > 0
        assert self.checked.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)) < 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha", "2")), Version(1, 0, 0, ("alpha", "10"))
        ) < 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",))
        ) < 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("1",))
        ) > 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))
        ) < 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1"))
        ) < 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha",))
        ) > 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha",))
        ) == 0

    def test_compare_precedence_ignores_build(self) -> None:
        assert self.checked.compare_precedence(
            Version(1, 0, 0, (), ("build",)), Version(1, 0, 0)
        ) == 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha",), ("build",)),
            Version(1, 0, 0, ("alpha",)),
        ) == 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9ad6fc5f59e1
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
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
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from benchmark_2.parts.semver_solver_multi.lib.semver_core import Version, VersionEngine


@dataclass
class SemverCoreState:
    """Canonical model state for SemVer core operations."""

    formatted: List[str] = field(default_factory=list)
    prerelease_flags: List[bool] = field(default_factory=list)
    parsed: List[Version] = field(default_factory=list)
    comparisons: List[Tuple[Version, Version, int]] = field(default_factory=list)


class SemverCoreStateMachine(StateMachine[SemverCoreState]):
    """Unified Pretense state machine for the SemVer core interface."""

    def __init__(
        self,
        state: Optional[SemverCoreState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverCoreState(), singletons=singletons)

    @transition(Version.format)
    def format(self) -> str:
        # Postcondition: formatting yields the canonical SemVer string representation.
        ret = self.inner_format()
        self.state.formatted.append(ret)
        assert self.state.formatted[-1] == ret
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        # Postcondition: a version is a prerelease exactly when it carries prerelease identifiers.
        ret = self.inner_is_prerelease()
        self.state.prerelease_flags.append(ret)
        assert self.state.prerelease_flags[-1] == ret
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require_arg(
            text,
            Domain.type(str),
            preferred=["1.0.0", "2.0.0-alpha.1+build.5"],
        )
        # Postcondition: parsing a grammatically valid version yields an immutable Version record.
        ret: Any = self.inner_parse_version(text)
        self.state.parsed.append(ret)
        assert self.state.parsed[-1] == ret
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(v1, Domain.type(Version))
        require_arg(v2, Domain.type(Version))
        # Postcondition: precedence comparison yields a signed ordering integer.
        ret = self.inner_compare_precedence(v1, v2)
        self.state.comparisons.append((v1, v2, ret))
        assert self.state.comparisons[-1] == (v1, v2, ret)
        return ret

    @transition.seeding
    def seed_version(self) -> None:
        """Seeds a documented canonical version string into the blank model state."""
        self.state.formatted.append("1.2.3")


proto = SemverCoreStateMachine()


FakeSemverCore = synthesize_fake(SemverCoreStateMachine)


def make_semver_core_fakes(
    state: Optional[SemverCoreState] = None,
) -> Tuple[Version, VersionEngine]:
    """Synthesizes a fake implementing every SemVer core target method."""
    fake = FakeSemverCore(state=state or SemverCoreState())
    return (fake, fake)


class TestSemverCoreFake(unittest.TestCase):
    """Exercises every transition and seeding transition on the synthesized fake."""

    def setUp(self) -> None:
        self.fakes = make_semver_core_fakes()
        self.sm = SemverCoreStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_version()
        self.sm.format()
        self.sm.is_prerelease()
        self.sm.parse_version("1.0.0")
        self.sm.compare_precedence(Version(1, 0, 0), Version(2, 0, 0))


FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverCoreState,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 85a7caed5434
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for version ranges."""

from __future__ import annotations

import unittest

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.semver_solver_multi.pretense.semver_range_pretense import (
    SemverRangeStateMachine,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_2.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import RangeEngine as RangeEngineImpl
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import (
    __initialize__ as _sr_initialize,
)


class SemverRangeImplPseudoStateMachine(SemverRangeStateMachine):
    """Implementation pseudo-state machine for the concrete version range engine."""

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        target: RangeEngineImpl = sut(RangeEngineImpl)
        ret = call_target(target.parse_range(text))
        # Postcondition: the recorded raw text is the trimmed range expression.
        assert ret.raw_text == text.strip()
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: RangeEngineImpl = sut(RangeEngineImpl)
        ret = call_target(
            target.satisfies(version, range_constraint, include_prerelease)
        )
        # Postcondition: satisfaction yields a definite boolean verdict.
        assert isinstance(ret, bool)
        return ret


proto = SemverRangeImplPseudoStateMachine()


class TestSemverRangeImplReal(unittest.TestCase):
    """Verifies the concrete version range engine against its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(RangeEngineImpl)
        self.sm = SemverRangeImplPseudoStateMachine(
            singletons={RangeEngineImpl: self.real, RangeEngine: self.real}
        )
        self.checked = self.sm.as_checked(RangeEngineImpl, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_range_forms(self) -> None:
        assert self.checked.parse_range(" 1.0.0 ").raw_text == "1.0.0"
        assert self.checked.parse_range(">= 1.0.0").raw_text == ">= 1.0.0"
        assert self.checked.parse_range("^1.2.3").raw_text == "^1.2.3"
        assert self.checked.parse_range("~1.2.3").raw_text == "~1.2.3"
        assert self.checked.parse_range("1.2.x").raw_text == "1.2.x"
        assert self.checked.parse_range("1.x").raw_text == "1.x"
        assert self.checked.parse_range("1.2.3 - 2.3.4").raw_text == "1.2.3 - 2.3.4"
        assert self.checked.parse_range("1.x || 2.x").raw_text == "1.x || 2.x"
        assert self.checked.parse_range("*").raw_text == "*"
        assert self.checked.parse_range("=1.0.0").raw_text == "=1.0.0"
        assert self.checked.parse_range("==1.0.0").raw_text == "==1.0.0"
        assert self.checked.parse_range("!=1.0.0").raw_text == "!=1.0.0"
        assert self.checked.parse_range("<2.0.0").raw_text == "<2.0.0"
        assert self.checked.parse_range("<=2.0.0").raw_text == "<=2.0.0"
        assert self.checked.parse_range(">1.0.0").raw_text == ">1.0.0"
        assert self.checked.parse_range(">=1.0.0").raw_text == ">=1.0.0"
        assert self.checked.parse_range("^ 1.2.3").raw_text == "^ 1.2.3"
        assert self.checked.parse_range("~ 1.2.3").raw_text == "~ 1.2.3"

    def test_parse_range_rejects_malformed(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range("   ")
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range("1.0.0 || ")
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range(">=1.0.0, <2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range(">=")
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range("1.2.3.x")
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range("1.x.3")
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range("a.x")
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range("01.x")
        with self.assertRaises(InvalidRangeError):
            self.checked.parse_range("not-a-version")

    def test_satisfies_exact_and_basic(self) -> None:
        assert self.checked.satisfies(Version(1, 0, 0), VersionRange("1.0.0"), True)
        assert not self.checked.satisfies(Version(1, 0, 1), VersionRange("1.0.0"), True)
        assert self.checked.satisfies(Version(1, 0, 0), VersionRange("=1.0.0"), True)
        assert self.checked.satisfies(Version(1, 0, 0), VersionRange("==1.0.0"), True)
        assert self.checked.satisfies(Version(1, 0, 1), VersionRange("!=1.0.0"), True)
        assert not self.checked.satisfies(Version(1, 0, 0), VersionRange("!=1.0.0"), True)
        assert self.checked.satisfies(Version(1, 9, 9), VersionRange("<2.0.0"), True)
        assert self.checked.satisfies(Version(2, 0, 0), VersionRange("<=2.0.0"), True)
        assert self.checked.satisfies(Version(2, 0, 1), VersionRange(">2.0.0"), True)
        assert self.checked.satisfies(Version(2, 0, 0), VersionRange(">=2.0.0"), True)
        assert not self.checked.satisfies(Version(1, 0, 0), VersionRange(">=2.0.0"), True)

    def test_satisfies_wildcards_and_hyphen(self) -> None:
        assert self.checked.satisfies(Version(1, 2, 9), VersionRange("1.2.x"), True)
        assert not self.checked.satisfies(Version(1, 3, 0), VersionRange("1.2.x"), True)
        assert self.checked.satisfies(Version(1, 9, 0), VersionRange("1.x"), True)
        assert not self.checked.satisfies(Version(2, 0, 0), VersionRange("1.x"), True)
        assert self.checked.satisfies(Version(9, 9, 9), VersionRange("*"), True)
        assert self.checked.satisfies(
            Version(1, 5, 0), VersionRange("1.2.3 - 2.3.4"), True
        )
        assert not self.checked.satisfies(
            Version(2, 4, 0), VersionRange("1.2.3 - 2.3.4"), True
        )
        assert self.checked.satisfies(Version(20, 0, 0), VersionRange("1.x || 20.x"), True)
        assert self.checked.satisfies(Version(1, 2, 5), VersionRange("1.2.*"), True)
        assert self.checked.satisfies(Version(1, 2, 5), VersionRange("1.*"), True)
        assert not self.checked.satisfies(Version(1, 2, 5), VersionRange("!=1.2.x"), True)
        assert self.checked.satisfies(Version(2, 0, 0), VersionRange(">1.2.x"), True)
        assert self.checked.satisfies(Version(1, 1, 0), VersionRange("<=1.2.x"), True)
        assert self.checked.satisfies(Version(1, 2, 5), VersionRange("<=1.2.x"), True)
        assert not self.checked.satisfies(Version(1, 3, 0), VersionRange("<=1.2.x"), True)
        assert not self.checked.satisfies(Version(1, 2, 5), VersionRange("<1.2.x"), True)
        assert not self.checked.satisfies(Version(1, 2, 5), VersionRange(">*"), True)
        assert self.checked.satisfies(Version(1, 2, 5), VersionRange(">=*"), True)
        assert self.checked.satisfies(Version(1, 2, 5), VersionRange("<=*"), True)
        assert not self.checked.satisfies(Version(1, 2, 5), VersionRange("!=*"), True)
        assert self.checked.satisfies(Version(1, 9, 0), VersionRange("^1.2.x"), True)
        assert not self.checked.satisfies(Version(2, 0, 0), VersionRange("^1.2.x"), True)
        assert self.checked.satisfies(Version(0, 2, 5), VersionRange("^0.2.x"), True)
        assert not self.checked.satisfies(Version(0, 3, 0), VersionRange("^0.2.x"), True)

    def test_satisfies_caret_and_tilde(self) -> None:
        assert self.checked.satisfies(Version(1, 5, 0), VersionRange("^1.2.3"), True)
        assert not self.checked.satisfies(Version(2, 0, 0), VersionRange("^1.2.3"), True)
        assert self.checked.satisfies(Version(0, 2, 5), VersionRange("^0.2.3"), True)
        assert not self.checked.satisfies(Version(0, 3, 0), VersionRange("^0.2.3"), True)
        assert self.checked.satisfies(Version(0, 0, 3), VersionRange("^0.0.3"), True)
        assert not self.checked.satisfies(Version(0, 0, 4), VersionRange("^0.0.3"), True)
        assert self.checked.satisfies(Version(1, 2, 9), VersionRange("~1.2.3"), True)
        assert not self.checked.satisfies(Version(1, 3, 0), VersionRange("~1.2.3"), True)
        assert self.checked.satisfies(Version(1, 9, 0), VersionRange("~1.x"), True)
        assert not self.checked.satisfies(Version(2, 0, 0), VersionRange("~1.x"), True)
        assert self.checked.satisfies(Version(1, 2, 9), VersionRange("~1.2.x"), True)
        assert not self.checked.satisfies(Version(1, 3, 0), VersionRange("~1.2.x"), True)
        assert self.checked.satisfies(Version(1, 0, 0), VersionRange("^*"), True)
        assert self.checked.satisfies(Version(1, 0, 0), VersionRange("~*"), True)
        assert self.checked.satisfies(Version(1, 5, 0), VersionRange("^1.x"), True)
        assert not self.checked.satisfies(Version(2, 0, 0), VersionRange("^1.x"), True)
        assert self.checked.satisfies(Version(0, 5, 0), VersionRange("^0.x"), True)
        assert not self.checked.satisfies(Version(1, 0, 0), VersionRange("^0.x"), True)

    def test_satisfies_prerelease_policy(self) -> None:
        assert self.checked.satisfies(
            Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0-alpha"), False
        )
        assert self.checked.satisfies(
            Version(1, 0, 0, ("beta",)), VersionRange(">=1.0.0-alpha"), False
        )
        assert not self.checked.satisfies(
            Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), False
        )
        assert self.checked.satisfies(
            Version(1, 0, 0, ("alpha",)), VersionRange("1.0.0-alpha"), False
        )
        assert not self.checked.satisfies(
            Version(1, 0, 0, ("beta",)), VersionRange("1.0.0-alpha"), False
        )
        assert not self.checked.satisfies(
            Version(2, 0, 0, ("alpha",)), VersionRange("1.0.0-alpha"), False
        )
        assert self.checked.satisfies(
            Version(1, 0, 0, ("alpha",)), VersionRange("1.0.0-alpha"), True
        )
        assert self.checked.satisfies(
            Version(1, 0, 0, (), ("build",)), VersionRange("1.0.0"), True
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 357294318952
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
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
    RangeEngine,
    VersionRange,
)


@dataclass
class SemverRangeState:
    """Canonical model state for version range operations."""

    parsed: List[VersionRange] = field(default_factory=list)
    ranges: List[str] = field(default_factory=list)
    matches: List[Tuple[Version, VersionRange, bool]] = field(default_factory=list)


class SemverRangeStateMachine(StateMachine[SemverRangeState]):
    """Unified Pretense state machine for the version range interface."""

    def __init__(
        self,
        state: Optional[SemverRangeState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverRangeState(), singletons=singletons)

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require_arg(
            text,
            Domain.type(str),
            preferred=["1.0.0", "^1.2.3", "~1.2.3", ">=1.0.0 <2.0.0"],
        )
        # Postcondition: parsing well-formed range text yields an immutable VersionRange record.
        ret: Any = self.inner_parse_range(text)
        self.state.parsed.append(ret)
        assert self.state.parsed[-1] == ret
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(version, Domain.type(Version))
        require_arg(range_constraint, Domain.type(VersionRange))
        require_arg(include_prerelease, Domain.boolean())
        # Postcondition: satisfaction yields a boolean verdict for the candidate version.
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        self.state.matches.append((version, range_constraint, ret))
        assert self.state.matches[-1] == (version, range_constraint, ret)
        return ret

    @transition.seeding
    def seed_range(self) -> None:
        """Seeds a documented range expression into the blank model state."""
        self.state.ranges.append("1.0.0")


proto = SemverRangeStateMachine()


FakeSemverRange = synthesize_fake(SemverRangeStateMachine)


def make_semver_range_fakes(
    state: Optional[SemverRangeState] = None,
) -> Tuple[VersionRange, RangeEngine]:
    """Synthesizes a fake implementing every version range target method."""
    fake = FakeSemverRange(state=state or SemverRangeState())
    return (fake, fake)


class TestSemverRangeFake(unittest.TestCase):
    """Exercises every transition and seeding transition on the synthesized fake."""

    def setUp(self) -> None:
        self.fakes = make_semver_range_fakes()
        self.sm = SemverRangeStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_range()
        self.sm.parse_range("^1.2.3")
        self.sm.satisfies(Version(1, 2, 3), VersionRange("^1.2.3"), True)


FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverRangeState,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:51Z
# LAST_CHANGED: 2026-11-05T16:59:51Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: f826e48185c0
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T16:59:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T16:59:51Z
# --- END AUTOFAB METADATA ---
