# === File: dependency_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DependencySolver."""

from __future__ import annotations

from typing import Any, List
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
from benchmark_3.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
)
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageRelease,
    PackageNotFoundError,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
)
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver_impl import (
    __initialize__ as _ds_initialize,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import (
    __initialize__ as _sr_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for DependencySolver."""

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        before = len(target.get_releases(release.name)) if target.has_package(release.name) else 0
        ret = call_target(target.register_package(release))
        assert len(target.get_releases(release.name)) == before + 1
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert [release.name for release in ret] == [name for _ in ret]
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
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
    def resolve(self, root_dependencies: Any) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert isinstance(ret, ResolutionOutcome)
        return ret


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

def _version(major: int, minor: int = 0, patch: int = 0) -> Version:
    return Version(major, minor, patch)


def _dependency(name: str, range_text: str) -> PackageDependency:
    return PackageDependency(name, VersionRange(range_text))


def _release(
    name: str, version: Version, dependencies: Any = ()
) -> PackageRelease:
    return PackageRelease(name, version, tuple(dependencies))


class TestDependencySolverImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

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
            singletons={PackageRepository: self.repository, DependencySolver: self.solver}
        )
        self.checked_repository = self.sm.as_checked(PackageRepository, self.repository)
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_repository_registration_and_lookup(self) -> None:
        """POSTCONDITIONS: releases remain ordered by descending precedence."""
        self.checked_repository.register_package(_release("alpha", _version(1, 0, 0)))
        self.checked_repository.register_package(_release("alpha", _version(2, 0, 0)))
        self.checked_repository.register_package(_release("alpha", _version(1, 5, 0)))
        releases = self.checked_repository.get_releases("alpha")
        self.assertEqual([release.version for release in releases], [
            _version(2, 0, 0),
            _version(1, 5, 0),
            _version(1, 0, 0),
        ])
        releases.append(_release("alpha", _version(9, 0, 0)))
        self.assertEqual(len(self.checked_repository.get_releases("alpha")), 3)
        self.assertTrue(self.checked_repository.has_package("alpha"))
        self.assertFalse(self.checked_repository.has_package("beta"))
        self.assertEqual(self.checked_repository.all_packages(), {"alpha"})

    def test_repository_missing_package(self) -> None:
        """PRECONDITIONS: WHEN name is not registered, MUST raise PackageNotFoundError."""
        with self.assertRaises(PackageNotFoundError):
            self.checked_repository.get_releases("missing")

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """POSTCONDITIONS: the highest precedence compatible release is selected."""
        self.checked_repository.register_package(_release("alpha", _version(1, 0, 0)))
        self.checked_repository.register_package(_release("alpha", _version(2, 0, 0)))
        outcome = self.checked_solver.resolve([_dependency("alpha", ">=1.0.0")])
        self.assertEqual(outcome.selected_versions, {"alpha": _version(2, 0, 0)})

    def test_resolve_empty_roots(self) -> None:
        """POSTCONDITIONS: resolving no root dependencies yields an empty assignment."""
        outcome = self.checked_solver.resolve([])
        self.assertEqual(outcome.selected_versions, {})
        self.assertEqual(outcome.derivation_steps, ())

    def test_resolve_prefers_fewest_candidates(self) -> None:
        """POSTCONDITIONS: the package with the fewest viable releases is assigned first."""
        self.checked_repository.register_package(_release("alpha", _version(1, 0, 0)))
        self.checked_repository.register_package(_release("alpha", _version(2, 0, 0)))
        self.checked_repository.register_package(_release("beta", _version(1, 0, 0)))
        outcome = self.checked_solver.resolve([
            _dependency("alpha", ">=1.0.0"),
            _dependency("beta", ">=1.0.0"),
        ])
        self.assertEqual(outcome.selected_versions, {
            "alpha": _version(2, 0, 0),
            "beta": _version(1, 0, 0),
        })
        self.assertIn("beta", outcome.derivation_steps[0])

    def test_resolve_backtracks_to_compatible_release(self) -> None:
        """POSTCONDITIONS: failing branches are undone so compatible assignments are found."""
        self.checked_repository.register_package(_release(
            "alpha", _version(2, 0, 0), (_dependency("beta", ">=2.0.0"),)
        ))
        self.checked_repository.register_package(_release(
            "alpha", _version(1, 0, 0), (_dependency("beta", ">=1.0.0"),)
        ))
        self.checked_repository.register_package(_release("beta", _version(1, 0, 0)))
        outcome = self.checked_solver.resolve([_dependency("alpha", ">=1.0.0")])
        self.assertEqual(outcome.selected_versions, {
            "alpha": _version(1, 0, 0),
            "beta": _version(1, 0, 0),
        })

    def test_resolve_detects_constraint_conflict_with_assigned_package(self) -> None:
        """POSTCONDITIONS: dependencies conflicting with prior assignments force alternatives."""
        self.checked_repository.register_package(_release("beta", _version(1, 0, 0)))
        self.checked_repository.register_package(_release(
            "alpha", _version(2, 0, 0), (_dependency("beta", ">=2.0.0"),)
        ))
        self.checked_repository.register_package(_release(
            "alpha", _version(1, 0, 0), (_dependency("beta", ">=1.0.0"),)
        ))
        outcome = self.checked_solver.resolve([
            _dependency("alpha", ">=1.0.0"),
            _dependency("beta", ">=1.0.0"),
        ])
        self.assertEqual(outcome.selected_versions, {
            "alpha": _version(1, 0, 0),
            "beta": _version(1, 0, 0),
        })

    def test_resolve_missing_package_raises_conflict(self) -> None:
        """PRECONDITIONS: missing packages raise ResolutionConflictError."""
        with self.assertRaises(ResolutionConflictError) as captured:
            self.checked_solver.resolve([_dependency("missing", ">=1.0.0")])
        self.assertIn("missing", captured.exception.conflicting_packages)

    def test_resolve_unsatisfiable_constraint_raises_conflict(self) -> None:
        """PRECONDITIONS: unsatisfiable constraints raise ResolutionConflictError."""
        self.checked_repository.register_package(_release("alpha", _version(1, 0, 0)))
        with self.assertRaises(ResolutionConflictError) as captured:
            self.checked_solver.resolve([_dependency("alpha", ">=2.0.0")])
        self.assertIn("alpha", captured.exception.conflicting_packages)

    def test_resolve_transitive_conflict_raises_conflict(self) -> None:
        """PRECONDITIONS: constraints from failed branches are restored before failing."""
        self.checked_repository.register_package(_release(
            "alpha", _version(1, 0, 0), (_dependency("beta", ">=2.0.0"),)
        ))
        self.checked_repository.register_package(_release("beta", _version(1, 0, 0)))
        with self.assertRaises(ResolutionConflictError) as captured:
            self.checked_solver.resolve([
                _dependency("alpha", ">=1.0.0"),
                _dependency("beta", ">=1.0.0"),
            ])
        self.assertIn("beta", captured.exception.conflicting_packages)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 53462a1df85d
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DependencySolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
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
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import VersionRange


@dataclass
class DependencySolverState:
    """Canonical model state for DependencySolver operations."""

    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    selected: Dict[str, Version] = field(default_factory=dict)
    steps: List[str] = field(default_factory=list)


def _sample_release() -> PackageRelease:
    return PackageRelease("alpha", Version(1, 0, 0), ())


def _sample_dependency() -> PackageDependency:
    return PackageDependency("alpha", VersionRange("1.x"))


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense State Machine for DependencySolver."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DependencySolverState(), singletons=singletons)

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(release, Domain.type(PackageRelease), preferred=[_sample_release()])
        ret = self.inner_register_package(release)
        self.state.packages.setdefault(release.name, []).append(release)
        self.state.steps.append(f"register '{release.name}'")
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require_arg(name, Domain.type(str), preferred=["alpha"])
        ret = self.inner_get_releases(name)
        assert isinstance(ret, list)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(name, Domain.type(str), preferred=["alpha"])
        ret = self.inner_has_package(name)
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        ret = self.inner_all_packages()
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: List[PackageDependency]) -> ResolutionOutcome:
        require_arg(
            root_dependencies,
            Domain.list_of(Domain.type(PackageDependency)),
            preferred=[[_sample_dependency()]],
        )
        ret = self.inner_resolve(root_dependencies)
        assert isinstance(ret, ResolutionOutcome)
        return ret

    @transition.seeding
    def seed_package(self) -> None:
        """Seeds a package release into blank model state."""
        self.state.packages.setdefault("alpha", []).append(_sample_release())


proto = DependencySolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fake(
    state: Optional[DependencySolverState] = None,
) -> Any:
    """Synthesizes a fake repository/solver double sharing model state."""
    return FakeDependencySolver(state=state or DependencySolverState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_dependency_solver_fake()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.fake.seed_package()
        self.fake.register_package(_sample_release())
        self.assertIsInstance(self.fake.get_releases("alpha"), list)
        self.assertIsInstance(self.fake.has_package("alpha"), bool)
        self.assertIsInstance(self.fake.all_packages(), set)
        self.assertIsInstance(self.fake.resolve([_sample_dependency()]), ResolutionOutcome)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 1929699a8d7a
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for VersionEngine."""

from __future__ import annotations

from typing import Any, Tuple
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
from benchmark_3.parts.semver_solver_multi.pretense.semver_core_pretense import (
    SemverCoreStateMachine,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import VersionEngine
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine for SemverCore."""

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.format() == text
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        return ret


proto = SemverCoreImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

def _version(
    major: int, minor: int = 0, patch: int = 0, prerelease: Tuple[str, ...] = ()
) -> Version:
    return Version(major, minor, patch, prerelease)


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

    def test_parse_version_populates_all_components(self) -> None:
        """POSTCONDITIONS: parse full versions into major/minor/patch/prerelease/build tuples."""
        version = self.checked.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prerelease, ("alpha", "1"))
        self.assertEqual(version.build, ("build", "5"))
        self.assertTrue(version.is_prerelease)
        self.assertEqual(version.format(), "1.2.3-alpha.1+build.5")

    def test_parse_version_without_optional_segments(self) -> None:
        """POSTCONDITIONS: versions without prerelease/build yield empty tuples."""
        version = self.checked.parse_version("0.0.0")
        self.assertEqual(version.prerelease, ())
        self.assertEqual(version.build, ())
        self.assertFalse(version.is_prerelease)

    def test_parse_version_rejects_malformed_grammar(self) -> None:
        """PRECONDITIONS: grammar violations raise InvalidVersionError."""
        with self.assertRaises(InvalidVersionError) as captured:
            self.checked.parse_version("1.2")
        self.assertEqual(captured.exception.raw_text, "1.2")

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """PRECONDITIONS: numeric leading zeroes raise InvalidVersionError."""
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("01.2.3")

    def test_compare_precedence_numeric_components(self) -> None:
        """POSTCONDITIONS: major, minor, and patch compare numerically in sequence."""
        self.assertLess(self.checked.compare_precedence(_version(1, 0, 0), _version(2, 0, 0)), 0)
        self.assertLess(self.checked.compare_precedence(_version(1, 1, 0), _version(1, 2, 0)), 0)
        self.assertLess(self.checked.compare_precedence(_version(1, 1, 1), _version(1, 1, 2)), 0)
        self.assertGreater(self.checked.compare_precedence(_version(2, 0, 0), _version(1, 0, 0)), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: build metadata is excluded from precedence comparison."""
        left = Version(1, 0, 0, (), ("build", "1"))
        right = Version(1, 0, 0, (), ("build", "2"))
        self.assertEqual(self.checked.compare_precedence(left, right), 0)

    def test_compare_precedence_normal_outranks_prerelease(self) -> None:
        """POSTCONDITIONS: normal versions rank higher than prereleases of the same core."""
        normal = _version(1, 0, 0)
        prerelease = _version(1, 0, 0, ("alpha",))
        self.assertGreater(self.checked.compare_precedence(normal, prerelease), 0)
        self.assertLess(self.checked.compare_precedence(prerelease, normal), 0)

    def test_compare_precedence_prerelease_segments(self) -> None:
        """POSTCONDITIONS: numeric identifiers rank below strings and compare numerically."""
        self.assertLess(
            self.checked.compare_precedence(
                _version(1, 0, 0, ("1",)), _version(1, 0, 0, ("alpha",))
            ),
            0,
        )
        self.assertGreater(
            self.checked.compare_precedence(
                _version(1, 0, 0, ("alpha",)), _version(1, 0, 0, ("1",))
            ),
            0,
        )
        self.assertLess(
            self.checked.compare_precedence(
                _version(1, 0, 0, ("1",)), _version(1, 0, 0, ("2",))
            ),
            0,
        )
        self.assertLess(
            self.checked.compare_precedence(
                _version(1, 0, 0, ("alpha",)), _version(1, 0, 0, ("beta",))
            ),
            0,
        )
        self.assertGreater(
            self.checked.compare_precedence(
                _version(1, 0, 0, ("beta",)), _version(1, 0, 0, ("alpha",))
            ),
            0,
        )

    def test_compare_precedence_equal_identifier_prefixes(self) -> None:
        """POSTCONDITIONS: a longer prerelease sequence outranks a shorter matching prefix."""
        self.assertEqual(
            self.checked.compare_precedence(
                _version(1, 0, 0, ("alpha", "1")), _version(1, 0, 0, ("alpha", "1"))
            ),
            0,
        )
        self.assertLess(
            self.checked.compare_precedence(
                _version(1, 0, 0, ("alpha",)), _version(1, 0, 0, ("alpha", "1"))
            ),
            0,
        )
        self.assertGreater(
            self.checked.compare_precedence(
                _version(1, 0, 0, ("alpha", "1")), _version(1, 0, 0, ("alpha",))
            ),
            0,
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 8d24a1c3db05
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverCore."""

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
from benchmark_3.parts.semver_solver_multi.lib.semver_core import (
    ComparatorOp,
    Version,
    VersionEngine,
)


@dataclass
class SemverCoreState:
    """Canonical model state for SemverCore operations."""

    versions: List[Version] = field(default_factory=list)
    prerelease: Tuple[str, ...] = ()


def _version(
    major: int, minor: int = 0, patch: int = 0, prerelease: Tuple[str, ...] = ()
) -> Version:
    return Version(major, minor, patch, prerelease)


class SemverCoreStateMachine(StateMachine[SemverCoreState]):
    """Unified Pretense State Machine for SemverCore."""

    def __init__(
        self,
        state: Optional[SemverCoreState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverCoreState(), singletons=singletons)

    @transition(Version.format)
    def format(self) -> str:
        require(len(self.state.versions) > 0)
        ret = self.inner_format()
        assert isinstance(ret, str)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(len(self.state.versions) > 0)
        ret = self.inner_is_prerelease()
        assert isinstance(ret, bool)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require_arg(text, Domain.type(str), preferred=["1.2.3"])
        ret = self.inner_parse_version(text)
        self.state.versions.append(ret)
        self.state.prerelease = ret.prerelease
        assert ret in self.state.versions
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(v1, Domain.type(Version), preferred=[_version(1, 0, 0)])
        require_arg(v2, Domain.type(Version), preferred=[_version(2, 0, 0)])
        ret = self.inner_compare_precedence(v1, v2)
        assert isinstance(ret, int)
        return ret

    @transition.seeding
    def seed_version(self) -> None:
        """Seeds a parsed version into blank model state."""
        self.state.versions.append(_version(1, 2, 3, ("alpha",)))
        self.state.prerelease = ("alpha",)


proto = SemverCoreStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverCore = synthesize_fake(SemverCoreStateMachine)


def make_semver_core_fake(state: Optional[SemverCoreState] = None) -> Any:
    """Synthesizes a fake version/engine double sharing model state."""
    return FakeSemverCore(state=state or SemverCoreState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverCoreFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_core_fake()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.fake.seed_version()
        self.assertIsInstance(self.fake.format(), str)
        self.assertIsInstance(self.fake.is_prerelease(), bool)
        self.assertIsInstance(self.fake.parse_version("1.2.3"), Version)
        self.assertIsInstance(self.fake.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), int)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverCoreState,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 249bdd669677
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RangeEngine."""

from __future__ import annotations

from typing import Any, Tuple
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
from benchmark_3.parts.semver_solver_multi.pretense.semver_range_pretense import (
    SemverRangeStateMachine,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    VersionRange,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import RangeEngine
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import (
    __initialize__ as _sr_initialize,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import (
    __initialize__ as _sc_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverRangeImplPseudoStateMachine(SemverRangeStateMachine):
    """Implementation pseudo-state machine for SemverRange."""

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> Any:
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
    ) -> Any:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        assert isinstance(ret, bool)
        return ret


proto = SemverRangeImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

def _version(
    major: int, minor: int = 0, patch: int = 0, prerelease: Tuple[str, ...] = ()
) -> Version:
    return Version(major, minor, patch, prerelease)


def _range(raw_text: str) -> VersionRange:
    return VersionRange(raw_text)


class TestSemverRangeImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _sr_initialize(self.registry)
        _sc_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(RangeEngine)
        self.sm = SemverRangeImplPseudoStateMachine(singletons={RangeEngine: self.real})
        self.checked = self.sm.as_checked(RangeEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_range_accepts_supported_grammar(self) -> None:
        """POSTCONDITIONS: comparators, caret, tilde, wildcard, hyphen, and unions parse."""
        cases = [
            "1.0.0",
            "1.0.0-alpha.1+build.2",
            "*",
            "1.x",
            "1.2.x",
            ">=1.0.0",
            "> 1.0.0",
            "==1.0.0",
            "=1.0.0",
            "!=1.0.0",
            "<1.0.0",
            "<=1.0.0",
            ">1.0.0",
            ">= 1.x",
            "<1.x",
            "<=1.x",
            ">1.x",
            "==1.x",
            "!=1.x",
            ">=*",
            "<=*",
            ">*",
            "!=*",
            "==*",
            "^1.2.3",
            "^0.2.3",
            "^0.0.3",
            "^1.x",
            "^0.2.x",
            "^0.0.x",
            "^*",
            "~1.2.3",
            "~1.x",
            "~*",
            "1.0.0 - 2.0.0",
            "1.0.0 - 2.x",
            "1.x - *",
            ">=1.0.0 <2.0.0",
            "1.x || 2.x",
            "  >=1.0.0  ",
        ]
        for text in cases:
            parsed = self.checked.parse_range(text)
            self.assertEqual(str(parsed), text.strip())

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """PRECONDITIONS: malformed range syntax raises InvalidRangeError with raw_range."""
        cases = [
            "",
            "   ",
            "||",
            "1.x || ",
            "1.x,2.x",
            "1.2",
            ">1.2",
            "^0.0",
            "1.2 - 2.3",
            "1.0.0 - 2.0.0 - 3.0.0",
            ">=",
            ">=" + " ",
            "1.x.2",
            "1.2.3.4",
            "abc",
            "^",
            "foo1.x",
            "01.0.0",
        ]
        for text in cases:
            with self.assertRaises(InvalidRangeError) as captured:
                self.checked.parse_range(text)
            self.assertEqual(captured.exception.raw_range, text)

    def test_satisfies_comparators(self) -> None:
        """POSTCONDITIONS: comparator clauses evaluate using precedence ordering."""
        self.assertTrue(self.checked.satisfies(_version(1, 0, 0), _range("1.0.0"), False))
        self.assertFalse(self.checked.satisfies(_version(1, 0, 1), _range("1.0.0"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 0, 1), _range("!=1.0.0"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 0, 1), _range(">1.0.0"), False))
        self.assertFalse(self.checked.satisfies(_version(1, 0, 0), _range(">1.0.0"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 0, 0), _range(">=1.0.0"), False))
        self.assertTrue(self.checked.satisfies(_version(0, 9, 0), _range("<1.0.0"), False))
        self.assertFalse(self.checked.satisfies(_version(1, 0, 0), _range("<1.0.0"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 0, 0), _range("<=1.0.0"), False))

    def test_satisfies_wildcard_expansions(self) -> None:
        """POSTCONDITIONS: wildcards expand into paired comparator inequalities."""
        self.assertTrue(self.checked.satisfies(_version(1, 5, 0), _range("1.x"), False))
        self.assertFalse(self.checked.satisfies(_version(2, 0, 0), _range("1.x"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 0, 0), _range(">=1.x"), False))
        self.assertTrue(self.checked.satisfies(_version(5, 0, 0), _range(">=1.x"), False))
        self.assertTrue(self.checked.satisfies(_version(0, 9, 0), _range("<1.x"), False))
        self.assertFalse(self.checked.satisfies(_version(1, 0, 0), _range("<1.x"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 9, 0), _range("<=1.x"), False))
        self.assertFalse(self.checked.satisfies(_version(2, 0, 0), _range("<=1.x"), False))
        self.assertTrue(self.checked.satisfies(_version(2, 0, 0), _range(">1.x"), False))
        self.assertFalse(self.checked.satisfies(_version(1, 9, 0), _range(">1.x"), False))
        self.assertTrue(self.checked.satisfies(_version(0, 9, 0), _range("!=1.x"), False))
        self.assertTrue(self.checked.satisfies(_version(2, 0, 0), _range("!=1.x"), False))
        self.assertFalse(self.checked.satisfies(_version(1, 5, 0), _range("!=1.x"), False))

    def test_satisfies_unbounded_wildcards(self) -> None:
        """POSTCONDITIONS: unbounded wildcards yield vacuous or unsatisfiable clauses."""
        self.assertTrue(self.checked.satisfies(_version(9, 9, 9), _range("<=*"), False))
        self.assertFalse(self.checked.satisfies(_version(9, 9, 9), _range(">*"), False))
        self.assertTrue(self.checked.satisfies(_version(3, 0, 0), _range("==*"), False))
        self.assertFalse(self.checked.satisfies(_version(3, 0, 0), _range("!=*"), False))

    def test_satisfies_caret_and_tilde(self) -> None:
        """POSTCONDITIONS: caret and tilde prefixes bound upper precedence ranges."""
        self.assertTrue(self.checked.satisfies(_version(1, 9, 0), _range("^1.2.3"), False))
        self.assertFalse(self.checked.satisfies(_version(2, 0, 0), _range("^1.2.3"), False))
        self.assertTrue(self.checked.satisfies(_version(0, 2, 9), _range("^0.2.3"), False))
        self.assertFalse(self.checked.satisfies(_version(0, 3, 0), _range("^0.2.3"), False))
        self.assertTrue(self.checked.satisfies(_version(0, 0, 3), _range("^0.0.3"), False))
        self.assertFalse(self.checked.satisfies(_version(0, 0, 4), _range("^0.0.3"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 4, 0), _range("^1.x"), False))
        self.assertFalse(self.checked.satisfies(_version(2, 0, 0), _range("^1.x"), False))
        self.assertTrue(self.checked.satisfies(_version(0, 2, 5), _range("^0.2.x"), False))
        self.assertFalse(self.checked.satisfies(_version(0, 3, 0), _range("^0.2.x"), False))
        self.assertTrue(self.checked.satisfies(_version(0, 0, 5), _range("^0.0.x"), False))
        self.assertFalse(self.checked.satisfies(_version(0, 1, 0), _range("^0.0.x"), False))
        self.assertTrue(self.checked.satisfies(_version(0, 0, 0), _range("^*"), False))
        self.assertTrue(self.checked.satisfies(_version(5, 0, 0), _range("^*"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 2, 9), _range("~1.2.3"), False))
        self.assertFalse(self.checked.satisfies(_version(1, 3, 0), _range("~1.2.3"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 9, 0), _range("~1.x"), False))
        self.assertFalse(self.checked.satisfies(_version(2, 0, 0), _range("~1.x"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 0, 0), _range("~*"), False))

    def test_satisfies_hyphen_ranges(self) -> None:
        """POSTCONDITIONS: hyphen ranges connect inclusive lower and upper bounds."""
        self.assertTrue(self.checked.satisfies(_version(1, 5, 0), _range("1.0.0 - 2.0.0"), False))
        self.assertTrue(self.checked.satisfies(_version(2, 0, 0), _range("1.0.0 - 2.0.0"), False))
        self.assertFalse(self.checked.satisfies(_version(2, 0, 1), _range("1.0.0 - 2.0.0"), False))
        self.assertTrue(self.checked.satisfies(_version(2, 9, 0), _range("1.0.0 - 2.x"), False))
        self.assertFalse(self.checked.satisfies(_version(3, 0, 0), _range("1.0.0 - 2.x"), False))
        self.assertTrue(self.checked.satisfies(_version(9, 9, 9), _range("1.x - *"), False))
        self.assertFalse(self.checked.satisfies(_version(0, 9, 0), _range("1.x - *"), False))

    def test_satisfies_unions_and_conjunctions(self) -> None:
        """POSTCONDITIONS: one satisfied clause suffices and every comparator must hold."""
        self.assertTrue(self.checked.satisfies(_version(2, 5, 0), _range("1.x || 2.x"), False))
        self.assertFalse(self.checked.satisfies(_version(3, 0, 0), _range("1.x || 2.x"), False))
        self.assertTrue(self.checked.satisfies(_version(1, 5, 0), _range(">=1.0.0 <2.0.0"), False))
        self.assertFalse(self.checked.satisfies(_version(2, 5, 0), _range(">=1.0.0 <2.0.0"), False))

    def test_satisfies_prerelease_filtering(self) -> None:
        """POSTCONDITIONS: prereleases only match ranges explicitly targeting their core."""
        self.assertFalse(
            self.checked.satisfies(_version(1, 0, 0, ("alpha",)), _range(">=1.0.0"), False)
        )
        self.assertTrue(
            self.checked.satisfies(_version(1, 0, 0, ("beta",)), _range(">=1.0.0-alpha"), False)
        )
        self.assertFalse(
            self.checked.satisfies(_version(1, 0, 0, ("beta",)), _range(">=1.0.0"), True)
        )
        self.assertFalse(
            self.checked.satisfies(_version(1, 0, 0, ("alpha",)), _range(">=1.0.0"), True)
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 575569dbedee
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverRange."""

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
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import VersionRange, RangeEngine


@dataclass
class SemverRangeState:
    """Canonical model state for SemverRange operations."""

    ranges: List[VersionRange] = field(default_factory=list)
    satisfied: bool = False


def _range(raw_text: str) -> VersionRange:
    return VersionRange(raw_text)


def _version(
    major: int, minor: int = 0, patch: int = 0, prerelease: Tuple[str, ...] = ()
) -> Version:
    return Version(major, minor, patch, prerelease)


class SemverRangeStateMachine(StateMachine[SemverRangeState]):
    """Unified Pretense State Machine for SemverRange."""

    def __init__(
        self,
        state: Optional[SemverRangeState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverRangeState(), singletons=singletons)

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require_arg(text, Domain.type(str), preferred=["1.x"])
        ret = self.inner_parse_range(text)
        self.state.ranges.append(ret)
        assert ret in self.state.ranges
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(version, Domain.type(Version), preferred=[_version(1, 0, 0)])
        require_arg(
            range_constraint, Domain.type(VersionRange), preferred=[_range("1.x")]
        )
        require_arg(include_prerelease, Domain.boolean(), preferred=[False])
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        self.state.satisfied = ret
        assert isinstance(ret, bool)
        return ret

    @transition.seeding
    def seed_range(self) -> None:
        """Seeds a parsed range into blank model state."""
        self.state.ranges.append(_range("1.x"))


proto = SemverRangeStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverRange = synthesize_fake(SemverRangeStateMachine)


def make_semver_range_fake(state: Optional[SemverRangeState] = None) -> Any:
    """Synthesizes a fake range double sharing model state."""
    return FakeSemverRange(state=state or SemverRangeState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverRangeFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_range_fake()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.fake.seed_range()
        self.assertIsInstance(self.fake.parse_range("1.x"), VersionRange)
        self.assertIsInstance(self.fake.satisfies(_version(1, 0, 0), _range("1.x"), False), bool)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverRangeState,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: a22f3b0212fd
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---
