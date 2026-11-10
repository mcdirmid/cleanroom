# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

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

from benchmark_3.parts.semver_solver.lib import semver_solver
from benchmark_3.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)
from benchmark_3.parts.semver_solver.pretense.semver_solver_pretense import (
    FakeSemverSolver,
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fakes,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: semver_solver.PackageRelease,
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
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> Any:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies its contracts."""

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
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _publish(
        self,
        name: str,
        version: semver_solver.Version,
        dependencies: Sequence[semver_solver.PackageDependency] = (),
    ) -> None:
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(name, version, tuple(dependencies))
        )

    def test_parse_version_components(self) -> None:
        simple = self.checked_versionengine.parse_version("1.2.3")
        assert simple.major == 1
        assert simple.minor == 2
        assert simple.patch == 3
        assert simple.prerelease == ()
        assert simple.build == ()
        extended = self.checked_versionengine.parse_version("1.2.3-alpha.1+build.5")
        assert extended.prerelease == ("alpha", "1")
        assert extended.build == ("build", "5")
        assert extended.is_prerelease
        assert str(extended) == "1.2.3-alpha.1+build.5"

    def test_compare_precedence_core(self) -> None:
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(2, 0, 0), semver_solver.Version(1, 0, 0)
        ) > 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0), semver_solver.Version(2, 0, 0)
        ) < 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 2, 0), semver_solver.Version(1, 1, 0)
        ) > 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 1, 0), semver_solver.Version(1, 2, 0)
        ) < 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 2), semver_solver.Version(1, 0, 1)
        ) > 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 1), semver_solver.Version(1, 0, 2)
        ) < 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0), semver_solver.Version(1, 0, 0)
        ) == 0

    def test_compare_precedence_prerelease(self) -> None:
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0), semver_solver.Version(1, 0, 0, ("alpha",))
        ) > 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("alpha",)), semver_solver.Version(1, 0, 0)
        ) < 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("1",)), semver_solver.Version(1, 0, 0, ("2",))
        ) < 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("2",)), semver_solver.Version(1, 0, 0, ("1",))
        ) > 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("1",)), semver_solver.Version(1, 0, 0, ("alpha",))
        ) < 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("alpha",)), semver_solver.Version(1, 0, 0, ("1",))
        ) > 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("alpha",)), semver_solver.Version(1, 0, 0, ("beta",))
        ) < 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("beta",)), semver_solver.Version(1, 0, 0, ("alpha",))
        ) > 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("alpha", "1")),
            semver_solver.Version(1, 0, 0, ("alpha", "2")),
        ) < 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("alpha",)), semver_solver.Version(1, 0, 0, ("alpha",))
        ) == 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("alpha",)),
            semver_solver.Version(1, 0, 0, ("alpha", "1")),
        ) < 0
        assert self.checked_versionengine.compare_precedence(
            semver_solver.Version(1, 0, 0, ("alpha", "1")),
            semver_solver.Version(1, 0, 0, ("alpha",)),
        ) > 0

    def test_parse_range_forms(self) -> None:
        assert self.checked_versionengine.parse_range(" >= 1.0.0 ").raw_text == ">= 1.0.0"
        assert self.checked_versionengine.parse_range("1.2.3").raw_text == "1.2.3"
        assert self.checked_versionengine.parse_range("=1.2.3").raw_text == "=1.2.3"
        assert self.checked_versionengine.parse_range("==1.2.3").raw_text == "==1.2.3"
        assert self.checked_versionengine.parse_range("!=1.2.3").raw_text == "!=1.2.3"
        assert self.checked_versionengine.parse_range("<2.0.0").raw_text == "<2.0.0"
        assert self.checked_versionengine.parse_range("<=2.0.0").raw_text == "<=2.0.0"
        assert self.checked_versionengine.parse_range(">1.0.0").raw_text == ">1.0.0"
        assert self.checked_versionengine.parse_range(">=1.0.0").raw_text == ">=1.0.0"
        assert self.checked_versionengine.parse_range("^1.2.3").raw_text == "^1.2.3"
        assert self.checked_versionengine.parse_range("^0.1.0").raw_text == "^0.1.0"
        assert self.checked_versionengine.parse_range("^0.0.3").raw_text == "^0.0.3"
        assert self.checked_versionengine.parse_range("~1.2.3").raw_text == "~1.2.3"
        assert self.checked_versionengine.parse_range("1.x").raw_text == "1.x"
        assert self.checked_versionengine.parse_range("1.*").raw_text == "1.*"
        assert self.checked_versionengine.parse_range("1.2.x").raw_text == "1.2.x"
        assert self.checked_versionengine.parse_range("1.2.*").raw_text == "1.2.*"
        assert self.checked_versionengine.parse_range("*").raw_text == "*"
        assert self.checked_versionengine.parse_range("x").raw_text == "x"
        assert self.checked_versionengine.parse_range("X").raw_text == "X"
        assert self.checked_versionengine.parse_range("1.2.3 - 2.0.0").raw_text == "1.2.3 - 2.0.0"
        assert (
            self.checked_versionengine.parse_range(">=1.0.0 || <0.5.0").raw_text
            == ">=1.0.0 || <0.5.0"
        )
        assert self.checked_versionengine.parse_range(">=1.0.0 <2.0.0").raw_text == ">=1.0.0 <2.0.0"

    def test_satisfies_forms(self) -> None:
        engine = self.checked_versionengine
        eq_range = engine.parse_range("==1.2.3")
        assert engine.satisfies(semver_solver.Version(1, 2, 3), eq_range, False)
        assert not engine.satisfies(semver_solver.Version(1, 2, 4), eq_range, False)
        assert engine.satisfies(
            semver_solver.Version(1, 2, 3), engine.parse_range("1.2.3"), False
        )
        assert engine.satisfies(
            semver_solver.Version(1, 2, 4), engine.parse_range("!=1.2.3"), False
        )
        assert not engine.satisfies(
            semver_solver.Version(1, 2, 3), engine.parse_range("!=1.2.3"), False
        )
        assert engine.satisfies(
            semver_solver.Version(1, 0, 0), engine.parse_range("<2.0.0"), False
        )
        assert engine.satisfies(
            semver_solver.Version(2, 0, 0), engine.parse_range("<=2.0.0"), False
        )
        assert engine.satisfies(
            semver_solver.Version(2, 0, 0), engine.parse_range(">1.0.0"), False
        )
        assert engine.satisfies(
            semver_solver.Version(1, 0, 0), engine.parse_range(">=1.0.0"), False
        )
        assert engine.satisfies(
            semver_solver.Version(1, 5, 0), engine.parse_range("^1.2.3"), False
        )
        assert not engine.satisfies(
            semver_solver.Version(2, 0, 0), engine.parse_range("^1.2.3"), False
        )
        assert engine.satisfies(
            semver_solver.Version(0, 1, 5), engine.parse_range("^0.1.0"), False
        )
        assert engine.satisfies(
            semver_solver.Version(0, 0, 3), engine.parse_range("^0.0.3"), False
        )
        assert engine.satisfies(
            semver_solver.Version(1, 2, 5), engine.parse_range("~1.2.3"), False
        )
        assert engine.satisfies(semver_solver.Version(1, 9, 0), engine.parse_range("1.x"), False)
        assert engine.satisfies(
            semver_solver.Version(1, 2, 9), engine.parse_range("1.2.x"), False
        )
        assert engine.satisfies(semver_solver.Version(7, 0, 0), engine.parse_range("*"), False)
        assert engine.satisfies(
            semver_solver.Version(1, 5, 0), engine.parse_range("1.2.3 - 2.0.0"), False
        )
        assert engine.satisfies(
            semver_solver.Version(3, 0, 0), engine.parse_range(">=2.0.0 || 1.x"), False
        )
        assert not engine.satisfies(
            semver_solver.Version(1, 5, 0), engine.parse_range(">=2.0.0 || 3.x"), False
        )
        assert engine.satisfies(
            semver_solver.Version(1, 5, 0), engine.parse_range(">=1.0.0 <2.0.0"), False
        )

    def test_satisfies_prerelease_policy(self) -> None:
        engine = self.checked_versionengine
        alpha = semver_solver.Version(1, 0, 0, ("alpha",))
        assert engine.satisfies(alpha, engine.parse_range(">=1.0.0-alpha"), False)
        assert not engine.satisfies(alpha, engine.parse_range(">=1.0.0"), False)
        assert not engine.satisfies(alpha, engine.parse_range("*"), False)
        assert not engine.satisfies(alpha, engine.parse_range(">=1.0.0"), True)

    def test_repository_ordering_and_lookup(self) -> None:
        self._publish("alpha", semver_solver.Version(1, 0, 0))
        self._publish("alpha", semver_solver.Version(2, 0, 0))
        self._publish("alpha", semver_solver.Version(1, 5, 0))
        self._publish(
            "beta",
            semver_solver.Version(3, 0, 0),
            (semver_solver.PackageDependency("alpha", semver_solver.VersionRange(">=1.0.0")),),
        )
        releases = self.checked_packagerepository.get_releases("alpha")
        assert [release.version.format() for release in releases] == ["2.0.0", "1.5.0", "1.0.0"]
        assert self.checked_packagerepository.has_package("alpha")
        assert not self.checked_packagerepository.has_package("missing")
        assert self.checked_packagerepository.all_packages() == {"alpha", "beta"}

    def test_resolve_direct_selection(self) -> None:
        self._publish("alpha", semver_solver.Version(1, 0, 0))
        self._publish("alpha", semver_solver.Version(1, 2, 0))
        outcome = self.checked_dependencysolver.resolve(
            (semver_solver.PackageDependency("alpha", semver_solver.VersionRange(">=1.0.0")),)
        )
        assert outcome.selected_versions["alpha"] == semver_solver.Version(1, 2, 0)
        assert len(outcome.derivation_steps) == 1

    def test_resolve_transitive_selection(self) -> None:
        self._publish("alpha", semver_solver.Version(1, 0, 0))
        self._publish(
            "beta",
            semver_solver.Version(2, 0, 0),
            (semver_solver.PackageDependency("alpha", semver_solver.VersionRange(">=1.0.0")),),
        )
        outcome = self.checked_dependencysolver.resolve(
            (semver_solver.PackageDependency("beta", semver_solver.VersionRange(">=2.0.0")),)
        )
        assert outcome.selected_versions["beta"] == semver_solver.Version(2, 0, 0)
        assert outcome.selected_versions["alpha"] == semver_solver.Version(1, 0, 0)

    def test_resolve_backtracks_forward_conflict(self) -> None:
        self._publish("alpha", semver_solver.Version(1, 0, 0))
        self._publish(
            "alpha",
            semver_solver.Version(2, 0, 0),
            (semver_solver.PackageDependency("beta", semver_solver.VersionRange(">=2.0.0")),),
        )
        self._publish("beta", semver_solver.Version(1, 0, 0))
        outcome = self.checked_dependencysolver.resolve(
            (
                semver_solver.PackageDependency("alpha", semver_solver.VersionRange(">=1.0.0")),
                semver_solver.PackageDependency("beta", semver_solver.VersionRange("==1.0.0")),
            )
        )
        assert outcome.selected_versions["alpha"] == semver_solver.Version(1, 0, 0)
        assert outcome.selected_versions["beta"] == semver_solver.Version(1, 0, 0)

    def test_resolve_backtracks_missing_and_unsatisfiable(self) -> None:
        self._publish("alpha", semver_solver.Version(1, 0, 0))
        self._publish(
            "alpha",
            semver_solver.Version(2, 0, 0),
            (semver_solver.PackageDependency("ghost", semver_solver.VersionRange(">=1.0.0")),),
        )
        self._publish(
            "alpha",
            semver_solver.Version(3, 0, 0),
            (semver_solver.PackageDependency("beta", semver_solver.VersionRange(">=9.0.0")),),
        )
        self._publish("beta", semver_solver.Version(1, 0, 0))
        outcome = self.checked_dependencysolver.resolve(
            (semver_solver.PackageDependency("alpha", semver_solver.VersionRange(">=1.0.0")),)
        )
        assert outcome.selected_versions["alpha"] == semver_solver.Version(1, 0, 0)

    def test_resolve_backtracks_with_existing_constraints(self) -> None:
        self._publish("alpha", semver_solver.Version(1, 0, 0))
        self._publish(
            "alpha",
            semver_solver.Version(2, 0, 0),
            (semver_solver.PackageDependency("beta", semver_solver.VersionRange(">=9.0.0")),),
        )
        self._publish("beta", semver_solver.Version(1, 0, 0))
        self._publish("beta", semver_solver.Version(2, 0, 0))
        self._publish("beta", semver_solver.Version(3, 0, 0))
        outcome = self.checked_dependencysolver.resolve(
            (
                semver_solver.PackageDependency("alpha", semver_solver.VersionRange(">=1.0.0")),
                semver_solver.PackageDependency("beta", semver_solver.VersionRange(">=1.0.0")),
            )
        )
        assert outcome.selected_versions["alpha"] == semver_solver.Version(1, 0, 0)
        assert outcome.selected_versions["beta"] == semver_solver.Version(3, 0, 0)

    def test_resolve_empty_root(self) -> None:
        outcome = self.checked_dependencysolver.resolve(())
        assert outcome.selected_versions == {}
        assert outcome.derivation_steps == ()


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
        self.packagerepository.register_package(
            semver_solver.PackageRelease("alpha", semver_solver.Version(1, 0, 0))
        )
        self.packagerepository.register_package(
            semver_solver.PackageRelease("alpha", semver_solver.Version(2, 0, 0))
        )
        self.packagerepository.register_package(
            semver_solver.PackageRelease("alpha", semver_solver.Version(3, 0, 0))
        )
        self.packagerepository.register_package(
            semver_solver.PackageRelease("beta", semver_solver.Version(1, 0, 0))
        )
        self.packagerepository.register_package(
            semver_solver.PackageRelease("beta", semver_solver.Version(2, 0, 0))
        )
        self.packagerepository.register_package(
            semver_solver.PackageRelease("beta", semver_solver.Version(3, 0, 0))
        )
        self.__dict__["_services"] = (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
        )

    def format(self) -> str:
        return self.versionengine.parse_version("1.2.3").format()

    def is_prerelease(self) -> bool:
        return self.versionengine.parse_version("1.2.3").is_prerelease

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
# LAST_CLEANED: 2026-11-05T04:11:11Z
# LAST_CHANGED: 2026-11-05T04:11:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: abd523262c79
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:11:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:11:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, List, Optional, Set, Tuple
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

from benchmark_3.parts.semver_solver.lib.semver_solver import (
    ComparatorOp,
    DependencySolver,
    InvalidVersionError,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)


# Valid SemVer 2.0.0 texts used to gate version parsing caller preconditions.
_VALID_VERSION_TEXTS = (
    "0.0.0",
    "1.0.0",
    "1.2.3",
    "1.2.3-alpha",
    "1.2.3-alpha.1",
    "1.2.3+build.5",
    "1.2.3-alpha.1+build.5",
    "2.10.3",
)

# Valid range expressions used to gate range parsing caller preconditions.
_VALID_RANGE_TEXTS = (
    " >= 1.0.0 ",
    ">= 1.0.0",
    "1.2.3",
    "=1.2.3",
    "==1.2.3",
    "!=1.2.3",
    "<2.0.0",
    "<=2.0.0",
    ">1.0.0",
    ">=1.0.0",
    "^1.2.3",
    "^0.1.0",
    "^0.0.3",
    "~1.2.3",
    "1.x",
    "1.*",
    "1.2.x",
    "1.2.*",
    "*",
    "x",
    "X",
    ">=1.0.0 <2.0.0",
    ">=1.0.0-alpha",
    "1.2.3 - 2.0.0",
    ">=1.0.0 || <0.5.0",
    ">=2.0.0 || 1.x",
    ">=2.0.0 || 3.x",
)

# Representative version ranges for open range parameters.
_RANGES = tuple(VersionRange(text) for text in _VALID_RANGE_TEXTS)

# Representative package release publications for open release parameters.
_RELEASES = (
    PackageRelease("alpha", Version(1, 0, 0)),
    PackageRelease(
        "beta",
        Version(2, 3, 4),
        (PackageDependency("alpha", VersionRange(">=1.0.0")),),
    ),
)

# Representative root dependency collections for open solver parameters.
_ROOT_DEPENDENCIES = (
    (),
    (PackageDependency("alpha", VersionRange(">=1.0.0")),),
    (PackageDependency("beta", VersionRange(">=2.0.0")),),
    (
        PackageDependency("alpha", VersionRange(">=1.0.0")),
        PackageDependency("beta", VersionRange("==1.0.0")),
    ),
    (
        PackageDependency("alpha", VersionRange(">=1.0.0")),
        PackageDependency("beta", VersionRange(">=1.0.0")),
    ),
)

# Registered package names used to gate release lookup caller preconditions.
_PACKAGE_NAMES = ("alpha", "beta")

# Representative return values for the fake transition oracles.
_SAMPLE_VERSION = Version(1, 2, 3)
_SAMPLE_OUTCOME = ResolutionOutcome(
    {"alpha": Version(1, 0, 0)}, ("Assign 'alpha' to 1.0.0",)
)


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    is_prerelease: bool = False


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(Version.format)
    def format(self) -> str:
        require(self.state.initialized)
        fake_ret = "1.2.3"
        ret: str = self.inner_format()
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.sampled_from(_VALID_VERSION_TEXTS),
            preferred=["1.2.3"],
        )
        fake_ret = _SAMPLE_VERSION
        ret: Version = self.inner_parse_version(text)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version))
        require_arg(v2, Domain.type(Version))
        fake_ret = 0
        ret: int = self.inner_compare_precedence(v1, v2)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.sampled_from(_VALID_RANGE_TEXTS),
            preferred=[">=1.0.0"],
        )
        fake_ret = VersionRange(">=1.0.0")
        ret: VersionRange = self.inner_parse_range(text)
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.type(Version))
        require_arg(
            range_constraint,
            Domain.sampled_from(_RANGES),
            preferred=[VersionRange(">=1.0.0")],
        )
        require_arg(include_prerelease, Domain.boolean())
        fake_ret = True
        ret: bool = self.inner_satisfies(version, range_constraint, include_prerelease)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.type(PackageRelease))
        ret = self.inner_register_package(release)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.sampled_from(_PACKAGE_NAMES),
            preferred=["alpha"],
        )
        fake_ret = [_RELEASES[0]]
        ret: List[PackageRelease] = self.inner_get_releases(name)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str))
        fake_ret = True
        ret: bool = self.inner_has_package(name)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        require(self.state.initialized)
        fake_ret: Set[str] = {"alpha"}
        ret: Set[str] = self.inner_all_packages()
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            Domain.sampled_from(_ROOT_DEPENDENCIES),
            preferred=[_ROOT_DEPENDENCIES[1]],
        )
        fake_ret = _SAMPLE_OUTCOME
        ret: ResolutionOutcome = self.inner_resolve(root_dependencies)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        fake_ret = True
        ret: bool = self.inner_is_prerelease()
        self.state.is_prerelease = ret
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake service instances sharing the model state."""
    fake = FakeSemverSolver(state=state or SemverSolverState())
    return (fake, fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake: Any = make_semver_solver_fakes()[0]
        self.sm = SemverSolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        _ = self.fake.is_prerelease
        self.fake.format()
        self.fake.parse_version("1.2.3")
        self.fake.compare_precedence(Version(1, 0, 0), Version(2, 0, 0))
        self.fake.parse_range(">=1.0.0")
        self.fake.satisfies(Version(1, 0, 0), VersionRange(">=1.0.0"), True)
        self.fake.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.fake.get_releases("alpha")
        self.fake.has_package("alpha")
        self.fake.all_packages()
        self.fake.resolve((PackageDependency("alpha", VersionRange(">=1.0.0")),))


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:11:11Z
# LAST_CHANGED: 2026-11-05T04:11:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 91b63db3817c
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:11:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:11:11Z
# --- END AUTOFAB METADATA ---
