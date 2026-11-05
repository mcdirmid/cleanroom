# === File: dependency_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DependencySolver."""

from __future__ import annotations

from contextlib import suppress
from typing import Any, Collection
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
    FakeDependencySolver,
    make_dependency_solver_fakes,
)
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
)
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
)
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for DependencySolver."""

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret: Any = None
        with suppress(PackageNotFoundError):
            ret = call_target(target.get_releases(name))
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> Any:
        target: DependencySolver = sut(DependencySolver)
        ret: Any = None
        with suppress(ResolutionConflictError):
            ret = call_target(target.resolve(root_dependencies))
        return ret


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDependencySolverImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

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

    def test_real_conformance(self) -> None:
        """Postconditions: repository indexing and resolution agree end to end."""
        self.checked_packagerepository.register_package(
            PackageRelease("pkg", Version(1, 0, 0))
        )
        self.assertTrue(self.checked_packagerepository.has_package("pkg"))
        self.assertFalse(self.checked_packagerepository.has_package("other"))
        self.assertEqual(
            self.checked_packagerepository.all_packages(), {"pkg"}
        )
        releases = self.checked_packagerepository.get_releases("pkg")
        self.assertEqual(len(releases), 1)
        outcome = self.checked_dependencysolver.resolve(
            [PackageDependency("pkg", VersionRange("1.0.0"))]
        )
        self.assertEqual(outcome.selected_versions["pkg"].format(), "1.0.0")
        self.assertGreater(len(outcome.derivation_steps), 0)

    def test_real_backtracks_on_conflicting_candidate(self) -> None:
        """Postcondition: a conflicting candidate is abandoned for a compatible one."""
        self.checked_packagerepository.register_package(
            PackageRelease("q", Version(1, 0, 0))
        )
        self.checked_packagerepository.register_package(
            PackageRelease("q", Version(2, 0, 0))
        )
        self.checked_packagerepository.register_package(
            PackageRelease(
                "pkg",
                Version(2, 0, 0),
                (PackageDependency("q", VersionRange("1.0.0")),),
            )
        )
        self.checked_packagerepository.register_package(
            PackageRelease(
                "pkg",
                Version(1, 0, 0),
                (PackageDependency("q", VersionRange("2.0.0")),),
            )
        )
        outcome = self.checked_dependencysolver.resolve(
            [
                PackageDependency("q", VersionRange("2.0.0")),
                PackageDependency("pkg", VersionRange("*")),
            ]
        )
        self.assertEqual(outcome.selected_versions["q"].format(), "2.0.0")
        self.assertEqual(outcome.selected_versions["pkg"].format(), "1.0.0")

    def test_real_backtracking_discards_introduced_constraints(self) -> None:
        """Sequencing: a failed branch's introduced constraints are removed."""
        self.checked_packagerepository.register_package(
            PackageRelease(
                "pkg",
                Version(2, 0, 0),
                (PackageDependency("mid", VersionRange("2.0.0")),),
            )
        )
        self.checked_packagerepository.register_package(
            PackageRelease("pkg", Version(1, 0, 0))
        )
        self.checked_packagerepository.register_package(
            PackageRelease(
                "mid",
                Version(2, 0, 0),
                (PackageDependency("ghost", VersionRange("9.9.9")),),
            )
        )
        self.checked_packagerepository.register_package(
            PackageRelease("mid", Version(1, 0, 0))
        )
        outcome = self.checked_dependencysolver.resolve(
            [PackageDependency("pkg", VersionRange("*"))]
        )
        self.assertEqual(outcome.selected_versions["pkg"].format(), "1.0.0")
        self.assertNotIn("mid", outcome.selected_versions)

    def test_real_repository_missing_release_lookup(self) -> None:
        """Precondition: an unregistered name suppresses PackageNotFoundError."""
        self.assertIsNone(self.checked_packagerepository.get_releases("missing"))

    def test_real_unsatisfiable_resolution_reports_conflict(self) -> None:
        """Postcondition: an unsatisfiable assignment suppresses ResolutionConflictError."""
        self.assertIsNone(
            self.checked_dependencysolver.resolve(
                [PackageDependency("ghost", VersionRange("*"))]
            )
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: ef837d5482dd
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DependencySolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, List, Optional, Sequence, Set, Tuple
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

@dataclass
class DependencySolverState:
    """Canonical model state for DependencySolver operations."""

    initialized: bool = True
    registered_names: List[str] = field(default_factory=list)
    last_has_package: bool = False
    resolved_names: Set[str] = field(default_factory=set)


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
        )
        self.state.registered_names.append(release.name)
        ret = make_return_value(None)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.type(str),
            preferred=["pkg"],
        )
        ret: List[PackageRelease] = make_return_value([])
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.type(str),
            preferred=["pkg"],
        )
        ret: bool = make_return_value(self.state.last_has_package)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = make_return_value(set(self.state.registered_names))
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            Domain.type(Collection[PackageDependency]),
        )
        self.state.resolved_names.add("resolved")
        ret: ResolutionOutcome = make_return_value(None)
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


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageDependency, PackageRelease, ResolutionOutcome, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeDependencySolver(state=state or DependencySolverState())
    return (
        fake,
        fake,
        fake,
        fake,
        fake,
    )


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fakes = make_dependency_solver_fakes()
        self.sm = DependencySolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.sm.register_package(PackageRelease("pkg", Version(1, 0, 0)))
        self.sm.get_releases("pkg")
        self.sm.has_package("pkg")
        self.sm.all_packages()
        self.sm.resolve([PackageDependency("pkg", VersionRange("1.0.0"))])


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: aaf8be070928
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for VersionEngine."""

from __future__ import annotations

from contextlib import suppress
from typing import Any
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
    FakeSemverCore,
    SemverCoreState,
    SemverCoreStateMachine,
    make_semver_core_fakes,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import VersionEngine
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine for SemverCore."""

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret: Any = None
        with suppress(InvalidVersionError):
            ret = call_target(target.parse_version(text))
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        return ret


proto = SemverCoreImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverCoreImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

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

    def test_real_conformance(self) -> None:
        """Postconditions: parsing round-trips and precedence orders released versions."""
        parsed = self.checked.parse_version("1.2.3-beta.1+build.5")
        self.assertEqual(parsed.format(), "1.2.3-beta.1+build.5")
        self.assertLess(
            self.checked.compare_precedence(
                parsed, self.checked.parse_version("1.2.3")
            ),
            0,
        )
        self.assertEqual(self.checked.compare_precedence(parsed, parsed), 0)

    def test_real_parse_rejects_invalid_grammar(self) -> None:
        """Precondition: grammar violations suppress InvalidVersionError."""
        self.assertIsNone(self.checked.parse_version("01.2.3"))
        self.assertIsNone(self.checked.parse_version("1.2"))
        self.assertIsNone(self.checked.parse_version("1.2.3+"))

    def test_real_compare_numeric_components(self) -> None:
        """Postcondition: major, minor, and patch compare numerically."""
        self.assertLess(
            self.checked.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0
        )
        self.assertGreater(
            self.checked.compare_precedence(Version(1, 2, 0), Version(1, 1, 0)), 0
        )
        self.assertGreater(
            self.checked.compare_precedence(Version(1, 1, 2), Version(1, 1, 1)), 0
        )

    def test_real_compare_prerelease_ordering(self) -> None:
        """Postcondition: prerelease identifiers compare numerically, then ASCII."""
        self.assertLess(
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha", "2")),
            ),
            0,
        )
        self.assertLess(
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha", "beta")),
            ),
            0,
        )
        self.assertGreater(
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha", "beta")),
                Version(1, 0, 0, ("alpha", "1")),
            ),
            0,
        )
        self.assertLess(
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))
            ),
            0,
        )
        self.assertLess(
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha",)),
                Version(1, 0, 0, ("alpha", "1")),
            ),
            0,
        )
        self.assertGreater(
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha",)),
            ),
            0,
        )
        self.assertLess(
            self.checked.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)
            ),
            0,
        )
        self.assertGreater(
            self.checked.compare_precedence(
                Version(1, 0, 0), Version(1, 0, 0, ("alpha",))
            ),
            0,
        )

    def test_real_compare_ignores_build_metadata(self) -> None:
        """Postcondition: build metadata never affects precedence."""
        self.assertEqual(
            self.checked.compare_precedence(
                Version(1, 0, 0, (), ("build", "1")),
                Version(1, 0, 0, (), ("build", "2")),
            ),
            0,
        )
        self.assertEqual(
            self.checked.compare_precedence(Version(2, 3, 4), Version(2, 3, 4)), 0
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9663e04965b4
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverCore."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib.semver_core import ComparatorOp, Version, VersionEngine


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverCoreState:
    """Canonical model state for SemverCore operations."""

    initialized: bool = True
    parsed_versions: List[Version] = field(default_factory=list)
    last_comparison: int = 0
    prerelease_flag: bool = False


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
        fake_text = "1.2.3-alpha.1+build.7"
        ret: str = make_return_value(fake_text)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=["1.0.0", "1.2.3-alpha.1+build.7"],
        )
        ret: Version = make_return_value(None)
        self.state.parsed_versions.append(ret)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(
            v1,
            Domain.type(Version),
        )
        require_arg(
            v2,
            Domain.type(Version),
        )
        ret: int = make_return_value(0)
        self.state.last_comparison = ret
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        ret: bool = make_return_value(self.state.prerelease_flag)
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


def make_semver_core_fakes(
    state: Optional[SemverCoreState] = None,
) -> Tuple[ComparatorOp, Version, VersionEngine]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeSemverCore(state=state or SemverCoreState())
    return (
        fake,
        fake,
        fake,
    )


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverCoreFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fakes = make_semver_core_fakes()
        self.sm = SemverCoreStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.sm.is_prerelease()
        self.sm.format()
        self.sm.parse_version("1.0.0")
        self.sm.compare_precedence(Version(1, 0, 0), Version(2, 0, 0))


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverCoreState,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 3f6f2ff76081
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RangeEngine."""

from __future__ import annotations

from contextlib import suppress
from typing import Any
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
    FakeSemverRange,
    SemverRangeState,
    SemverRangeStateMachine,
    make_semver_range_fakes,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import RangeEngine
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverRangeImplPseudoStateMachine(SemverRangeStateMachine):
    """Implementation pseudo-state machine for SemverRange."""

    @transition(RangeEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> Any:
        target: RangeEngine = sut(RangeEngine)
        ret: Any = None
        with suppress(InvalidRangeError):
            ret = call_target(target.parse_range(text))
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
        return ret


proto = SemverRangeImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverRangeImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

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

    def _check(
        self,
        range_text: str,
        version: Version,
        expected: bool,
        include_prerelease: bool = False,
    ) -> None:
        constraint = self.checked.parse_range(range_text)
        self.assertEqual(
            self.checked.satisfies(version, constraint, include_prerelease), expected
        )

    def test_real_parse_range_trims_expression(self) -> None:
        """Postcondition: surrounding whitespace is trimmed into raw_text."""
        constraint = self.checked.parse_range("  >=1.0.0  ")
        self.assertEqual(constraint.raw_text, ">=1.0.0")
        self.assertEqual(str(constraint), ">=1.0.0")

    def test_real_parse_supports_grammar_constructs(self) -> None:
        """Postcondition: comparators, prefixes, wildcards, hyphens, and unions parse."""
        valid = (
            "1.2.3",
            "==1.2.3",
            "=1.2.3",
            "!=1.2.3",
            "<1.2.3",
            "<=1.2.3",
            ">1.2.3",
            ">=1.2.3",
            ">= 1.2.3",
            "^1.2.3",
            "~1.2.3",
            "*",
            "x",
            "X",
            "==*",
            "1.x",
            "1.*",
            "1.2.x",
            "1.2.*",
            "==1.x",
            "!=1.x",
            ">=1.x",
            ">1.x",
            "<1.x",
            "<=1.x",
            "1.2.3 - 2.0.0",
            "* - 2.0.0",
            "1.0.0 - *",
            "1.x - 2.x",
            ">=1.0.0 <2.0.0",
            "1.0.0 || >=2.0.0",
            ">=1.0.0-alpha.1",
            "^1.2.3-alpha.1+build.5",
        )
        for text in valid:
            constraint = self.checked.parse_range(text)
            self.assertEqual(constraint.raw_text, text.strip())

    def test_real_parse_rejects_malformed_syntax(self) -> None:
        """Precondition: malformed expressions suppress InvalidRangeError."""
        malformed = (
            "",
            "   ",
            "1",
            "1.2",
            "^0.0",
            "~1",
            "1.2 - 2.3",
            "1.0.0, <2.0.0",
            "1.0.0 || ",
            "|| 1.0.0",
            "01.0.0",
            "1.0.0+bad_1",
            "1.0.0-alpha..1",
            "1.0.0-",
            "1.0.*-alpha",
            "1.2.3.x",
            ">=",
            "^1.x",
            "~1.x",
            "!=*",
            ">=*",
            "<*",
            "1.0.0 - ",
            "1.0.0 - 2.0.0 - 3.0.0",
            "1.0.0 - 2.0.0 extra",
        )
        for text in malformed:
            self.assertIsNone(self.checked.parse_range(text))

    def test_real_satisfies_comparator_operators(self) -> None:
        """Postcondition: every basic comparator evaluates boundary membership."""
        self._check("1.2.3", Version(1, 2, 3), True)
        self._check("1.2.3", Version(1, 2, 4), False)
        self._check("==1.2.3", Version(1, 2, 3), True)
        self._check("=1.2.3", Version(1, 2, 3), True)
        self._check("!=1.2.3", Version(1, 2, 3), False)
        self._check("!=1.2.3", Version(1, 2, 4), True)
        self._check("<2.0.0", Version(1, 9, 9), True)
        self._check("<2.0.0", Version(2, 0, 0), False)
        self._check("<=2.0.0", Version(2, 0, 0), True)
        self._check("<=2.0.0", Version(2, 0, 1), False)
        self._check(">1.0.0", Version(1, 0, 1), True)
        self._check(">1.0.0", Version(1, 0, 0), False)
        self._check(">=1.0.0", Version(1, 0, 0), True)
        self._check(">=1.0.0", Version(0, 9, 9), False)

    def test_real_satisfies_wildcard_patterns(self) -> None:
        """Postcondition: wildcards expand to their numeric prefix range."""
        self._check("*", Version(5, 0, 0), True)
        self._check("x", Version(5, 0, 0), True)
        self._check("X", Version(5, 0, 0), True)
        self._check("==*", Version(5, 0, 0), True)
        self._check("1.x", Version(1, 5, 0), True)
        self._check("1.x", Version(2, 0, 0), False)
        self._check("1.*", Version(1, 5, 0), True)
        self._check("1.2.x", Version(1, 2, 9), True)
        self._check("1.2.x", Version(1, 3, 0), False)
        self._check("1.2.*", Version(1, 2, 0), True)
        self._check("==1.x", Version(1, 5, 0), True)
        self._check("==1.x", Version(2, 0, 0), False)

    def test_real_satisfies_relational_wildcards(self) -> None:
        """Postcondition: relational wildcards shift to the range boundary."""
        self._check(">=1.x", Version(1, 0, 0), True)
        self._check(">=1.x", Version(0, 9, 0), False)
        self._check("<1.x", Version(0, 9, 0), True)
        self._check("<1.x", Version(1, 0, 0), False)
        self._check(">1.x", Version(2, 0, 0), True)
        self._check(">1.x", Version(1, 9, 0), False)
        self._check("<=1.x", Version(1, 9, 0), True)
        self._check("<=1.x", Version(2, 0, 0), False)

    def test_real_satisfies_not_in_wildcard(self) -> None:
        """Postcondition: '!=' over a wildcard excludes the whole expanded interval."""
        self._check("!=1.x", Version(1, 5, 0), False)
        self._check("!=1.x", Version(2, 5, 0), True)
        self._check("!=1.x", Version(0, 5, 0), True)

    def test_real_satisfies_caret_ranges(self) -> None:
        """Postcondition: caret ranges cap at the first non-zero component boundary."""
        self._check("^1.2.3", Version(1, 9, 9), True)
        self._check("^1.2.3", Version(2, 0, 0), False)
        self._check("^1.2.3", Version(1, 2, 2), False)
        self._check("^0.2.3", Version(0, 2, 9), True)
        self._check("^0.2.3", Version(0, 3, 0), False)
        self._check("^0.0.3", Version(0, 0, 3), True)
        self._check("^0.0.3", Version(0, 0, 4), False)

    def test_real_satisfies_tilde_ranges(self) -> None:
        """Postcondition: tilde ranges cap at the next minor boundary."""
        self._check("~1.2.3", Version(1, 2, 9), True)
        self._check("~1.2.3", Version(1, 3, 0), False)
        self._check("~1.2.3", Version(1, 2, 2), False)

    def test_real_satisfies_hyphen_ranges(self) -> None:
        """Postcondition: hyphen ranges expand into lower and upper boundaries."""
        self._check("1.2.3 - 2.0.0", Version(1, 5, 0), True)
        self._check("1.2.3 - 2.0.0", Version(2, 0, 1), False)
        self._check("1.2.3 - 2.0.0", Version(1, 2, 2), False)
        self._check("* - 2.0.0", Version(0, 1, 0), True)
        self._check("* - 2.0.0", Version(2, 0, 1), False)
        self._check("1.0.0 - *", Version(3, 0, 0), True)
        self._check("1.x - 2.x", Version(1, 5, 0), True)
        self._check("1.x - 2.x", Version(2, 9, 0), True)
        self._check("1.x - 2.x", Version(3, 0, 0), False)
        self._check("1.2.3 - 2.x", Version(2, 9, 0), True)
        self._check("1.2.3 - 2.x", Version(3, 0, 0), False)

    def test_real_satisfies_union_clauses(self) -> None:
        """Postcondition: a version satisfies the union when one clause matches."""
        self._check("1.0.0 || >=2.0.0", Version(1, 0, 0), True)
        self._check("1.0.0 || >=2.0.0", Version(2, 5, 0), True)
        self._check("1.0.0 || >=2.0.0", Version(1, 5, 0), False)

    def test_real_satisfies_prerelease_handling(self) -> None:
        """Postcondition: prereleases require an explicit same-triple prerelease target."""
        self._check(">=1.0.0", Version(1, 0, 0, ("alpha",)), False)
        self._check(">=1.0.0", Version(1, 0, 0, ("alpha",)), False, True)
        self._check(">=1.0.0-alpha", Version(1, 0, 0, ("alpha",)), True)
        self._check(">0.9.0", Version(1, 0, 0, ("alpha",)), True, True)
        self._check("!=1.x", Version(1, 5, 0, ("alpha",)), False)
        self._check(">=1.0.0", Version(1, 5, 0), True)

    def test_real_satisfies_whitespace_between_operators(self) -> None:
        """Postcondition: optional whitespace separates operators from targets."""
        self._check(">= 1.0.0", Version(1, 0, 0), True)
        self._check("^ 1.2.3", Version(1, 5, 0), True)
        self._check("~ 1.2.3", Version(1, 2, 9), True)
        self._check("1.0.0  -  2.0.0", Version(1, 5, 0), True)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: ded9ae28650b
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverRange."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import RangeEngine, VersionRange


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverRangeState:
    """Canonical model state for SemverRange operations."""

    initialized: bool = True
    parsed_ranges: List[str] = field(default_factory=list)
    last_match: bool = False


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
            Domain.type(str),
            preferred=["1.0.0", ">=1.0.0 <2.0.0", "1.x", "1.0.0 - 2.0.0", "^1.2.3", "~1.2.3"],
        )
        self.state.parsed_ranges.append(text)
        ret: VersionRange = make_return_value(None)
        return ret

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
        )
        require_arg(
            range_constraint,
            Domain.type(VersionRange),
        )
        require_arg(
            include_prerelease,
            Domain.boolean(),
        )
        ret: bool = make_return_value(self.state.last_match)
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


def make_semver_range_fakes(
    state: Optional[SemverRangeState] = None,
) -> Tuple[VersionRange, RangeEngine]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeSemverRange(state=state or SemverRangeState())
    return (
        fake,
        fake,
    )


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverRangeFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fakes = make_semver_range_fakes()
        self.sm = SemverRangeStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.sm.parse_range("1.0.0")
        self.sm.satisfies(Version(1, 0, 0), VersionRange("1.0.0"), True)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverRangeState,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 5fda5c24dcaa
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---
