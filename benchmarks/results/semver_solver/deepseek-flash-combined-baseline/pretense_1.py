# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, List, Optional, Set, Tuple
import unittest

from pretense import call_target, sut, transition
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.semver_solver.pretense.semver_solver_pretense import (
    SemverSolverState,
    SemverSolverStateMachine,
)
from benchmark_4.parts.semver_solver.lib.semver_solver import (
    PackageDependency,
    PackageRelease,
    ResolutionOutcome,
    Version,
    VersionRange,
)
from benchmark_4.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine observing the concrete SemverSolver services."""

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(
            target.satisfies(version, range_constraint, include_prerelease)
        )
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        return ret

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> Any:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        return ret


proto = SemverSolverImplPseudoStateMachine()


def _release(
    name: str,
    version: Version,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Builds a domain PackageRelease value for scenario setup."""
    return PackageRelease(name, version, dependencies)


def _dependency(name: str, range_text: str) -> PackageDependency:
    """Builds a domain PackageDependency value for scenario setup."""
    return PackageDependency(name, VersionRange(range_text))


class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies its contracted postconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = get_singleton(VersionEngine)
        self.repository = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: self.engine,
                PackageRepository: self.repository,
                DependencySolver: self.solver,
            }
        )
        self.checked_engine = self.sm.as_checked(VersionEngine, self.engine)
        self.checked_repository = self.sm.as_checked(
            PackageRepository, self.repository
        )
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_conformance(self) -> None:
        # POST: valid SemVer strings parse into immutable Version records.
        self.assertEqual(
            self.checked_engine.parse_version("1.2.3"), Version(1, 2, 3)
        )
        self.assertEqual(
            self.checked_engine.parse_version("0.0.0"), Version(0, 0, 0)
        )
        self.assertEqual(
            self.checked_engine.parse_version("1.0.0-alpha.1+build.5"),
            Version(1, 0, 0, ("alpha", "1"), ("build", "5")),
        )
        self.assertEqual(
            self.checked_engine.parse_version("2.1.0-rc.1"),
            Version(2, 1, 0, ("rc", "1")),
        )

    def test_compare_precedence_conformance(self) -> None:
        # POST: SemVer 2.0.0 precedence ordering is honored.
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0), Version(2, 0, 0)
            ),
            -1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(2, 0, 0), Version(1, 0, 0)
            ),
            1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 1, 0), Version(1, 2, 0)
            ),
            -1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 2, 0), Version(1, 1, 0)
            ),
            1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 1), Version(1, 0, 2)
            ),
            -1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 2), Version(1, 0, 1)
            ),
            1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0), Version(1, 0, 0)
            ),
            0,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)
            ),
            -1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0), Version(1, 0, 0, ("alpha",))
            ),
            1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))
            ),
            -1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("alpha",))
            ),
            1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha", "2")),
            ),
            -1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "2")),
                Version(1, 0, 0, ("alpha", "1")),
            ),
            1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1"))
            ),
            -1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha",))
            ),
            1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",))
            ),
            -1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("1",))
            ),
            1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("2",)), Version(1, 0, 0, ("10",))
            ),
            -1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("10",)), Version(1, 0, 0, ("2",))
            ),
            1,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha",))
            ),
            0,
        )
        self.assertEqual(
            self.checked_engine.compare_precedence(
                Version(1, 2, 3, (), ("build", "7")), Version(1, 2, 3)
            ),
            0,
        )

    def test_parse_range_conformance(self) -> None:
        # POST: comparators, caret, tilde, wildcards, hyphens, and unions parse.
        for expression in (
            "==1.0.0",
            "=1.0.0",
            "!=1.0.0",
            "<1.0.0",
            "<=1.0.0",
            ">1.0.0",
            ">=1.0.0",
            "^1.2.3",
            "^0.2.3",
            "^0.0.3",
            "~1.2.3",
            "*",
            "x",
            "X",
            "1.x",
            "1.*",
            "1.2.x",
            "1.2.*",
            "1.2.3 - 2.3.4",
            "1.2.3 - 2.3.x",
            "1.2.3 - 2.x",
            "1.x - 2.3.4",
            "1.2.3 - *",
            ">=1.0.0 || <0.5.0",
            ">= 1.0.0 < 2.0.0",
            "!=1.x",
            ">=1.x",
            ">1.x",
            "<1.x",
            "<=1.x",
            "!=*",
            ">=*",
        ):
            with self.subTest(expression=expression):
                self.assertEqual(
                    self.checked_engine.parse_range(expression).raw_text,
                    expression,
                )

    def test_parse_range_trims_whitespace(self) -> None:
        # POST: surrounding whitespace is trimmed into raw_text.
        parsed = self.checked_engine.parse_range("  >= 1.0.0   < 2.0.0  ")
        self.assertEqual(parsed.raw_text, ">= 1.0.0   < 2.0.0")
        self.assertEqual(str(parsed), ">= 1.0.0   < 2.0.0")

    def test_satisfies_relational_conformance(self) -> None:
        # POST: primitive relational comparators match by precedence.
        for range_text, version_text, expected in (
            ("==1.0.0", "1.0.0", True),
            ("==1.0.0", "1.0.1", False),
            ("=1.0.0", "1.0.0", True),
            ("!=1.0.0", "1.0.1", True),
            ("!=1.0.0", "1.0.0", False),
            ("<1.0.0", "0.9.0", True),
            ("<1.0.0", "1.0.0", False),
            ("<=1.0.0", "1.0.0", True),
            ("<=1.0.0", "1.0.1", False),
            (">1.0.0", "1.0.1", True),
            (">1.0.0", "1.0.0", False),
            (">=1.0.0", "1.0.0", True),
            (">=1.0.0", "0.9.0", False),
        ):
            with self.subTest(range_text=range_text, version=version_text):
                self.assertEqual(
                    self.checked_engine.satisfies(
                        self.checked_engine.parse_version(version_text),
                        self.checked_engine.parse_range(range_text),
                        False,
                    ),
                    expected,
                )

    def test_satisfies_caret_tilde_conformance(self) -> None:
        # POST: caret and tilde prefixes expand into boundary comparators.
        for range_text, version_text, expected in (
            ("^1.2.3", "1.9.0", True),
            ("^1.2.3", "2.0.0", False),
            ("^1.2.3", "1.2.2", False),
            ("^0.2.3", "0.2.9", True),
            ("^0.2.3", "0.3.0", False),
            ("^0.0.3", "0.0.3", True),
            ("^0.0.3", "0.0.4", False),
            ("~1.2.3", "1.2.9", True),
            ("~1.2.3", "1.3.0", False),
            ("~1.2.3", "1.2.2", False),
        ):
            with self.subTest(range_text=range_text, version=version_text):
                self.assertEqual(
                    self.checked_engine.satisfies(
                        self.checked_engine.parse_version(version_text),
                        self.checked_engine.parse_range(range_text),
                        False,
                    ),
                    expected,
                )

    def test_satisfies_wildcard_hyphen_conformance(self) -> None:
        # POST: wildcards and hyphen ranges normalize into inequalities.
        for range_text, version_text, expected in (
            ("*", "5.0.0", True),
            ("x", "5.0.0", True),
            ("1.x", "1.5.0", True),
            ("1.x", "2.0.0", False),
            ("1.*", "1.5.0", True),
            ("1.2.x", "1.2.9", True),
            ("1.2.x", "1.3.0", False),
            ("1.2.*", "1.2.9", True),
            ("!=1.x", "2.0.0", True),
            ("!=1.x", "1.5.0", False),
            (">=1.x", "1.0.0", True),
            (">=1.x", "0.9.0", False),
            (">1.x", "2.0.0", True),
            (">1.x", "1.5.0", False),
            ("<1.x", "0.5.0", True),
            ("<1.x", "1.0.0", False),
            ("<=1.x", "1.9.9", True),
            ("<=1.x", "2.0.0", False),
            ("!=*", "1.0.0", False),
            (">*", "1.0.0", False),
            ("<*", "1.0.0", False),
            (">=*", "1.0.0", True),
            ("<=*", "1.0.0", True),
            ("1.2.3 - 2.3.4", "1.2.3", True),
            ("1.2.3 - 2.3.4", "2.3.4", True),
            ("1.2.3 - 2.3.4", "2.3.5", False),
            ("1.2.3 - 2.3.4", "1.2.2", False),
            ("1.2.3 - 2.3.x", "2.3.9", True),
            ("1.2.3 - 2.3.x", "2.4.0", False),
            ("1.2.3 - 2.x", "2.9.9", True),
            ("1.2.3 - 2.x", "3.0.0", False),
            ("1.x - 2.3.4", "1.0.0", True),
            ("1.x - 2.3.4", "0.9.0", False),
            ("1.2.3 - *", "5.0.0", True),
        ):
            with self.subTest(range_text=range_text, version=version_text):
                self.assertEqual(
                    self.checked_engine.satisfies(
                        self.checked_engine.parse_version(version_text),
                        self.checked_engine.parse_range(range_text),
                        False,
                    ),
                    expected,
                )

    def test_satisfies_union_conformance(self) -> None:
        # POST: a version satisfies the range when any union clause matches.
        parsed = self.checked_engine.parse_range(">=1.0.0 || <0.5.0")
        self.assertTrue(
            self.checked_engine.satisfies(Version(1, 5, 0), parsed, False)
        )
        self.assertTrue(
            self.checked_engine.satisfies(Version(0, 4, 0), parsed, False)
        )
        self.assertFalse(
            self.checked_engine.satisfies(Version(0, 7, 0), parsed, False)
        )

    def test_satisfies_prerelease_conformance(self) -> None:
        # WHEN include_prerelease is False, only targeted prereleases match.
        plain = self.checked_engine.parse_range(">=1.0.0")
        targeted = self.checked_engine.parse_range(">=1.0.0-alpha <2.0.0")
        self.assertFalse(
            self.checked_engine.satisfies(
                Version(1, 0, 0, ("alpha",)), plain, False
            )
        )
        self.assertFalse(
            self.checked_engine.satisfies(
                Version(1, 0, 0, ("alpha",)), plain, True
            )
        )
        self.assertTrue(
            self.checked_engine.satisfies(
                Version(1, 0, 0, ("beta",)), targeted, False
            )
        )
        self.assertFalse(
            self.checked_engine.satisfies(
                Version(1, 2, 0, ("beta",)), targeted, False
            )
        )
        self.assertTrue(
            self.checked_engine.satisfies(
                Version(1, 2, 0, ("beta",)), targeted, True
            )
        )
        self.assertTrue(
            self.checked_engine.satisfies(Version(1, 0, 0), targeted, False)
        )
        self.assertFalse(
            self.checked_engine.satisfies(
                Version(0, 9, 0, ("alpha",)), targeted, False
            )
        )

    def test_repository_conformance(self) -> None:
        # POST: releases are indexed and ordered by descending precedence.
        self.checked_repository.register_package(
            _release("alpha", Version(1, 0, 0))
        )
        self.checked_repository.register_package(
            _release("alpha", Version(1, 2, 0))
        )
        self.checked_repository.register_package(
            _release("alpha", Version(0, 9, 0))
        )
        releases = self.checked_repository.get_releases("alpha")
        self.assertEqual(
            [release.version for release in releases],
            [Version(1, 2, 0), Version(1, 0, 0), Version(0, 9, 0)],
        )
        releases.append(_release("alpha", Version(9, 0, 0)))
        self.assertEqual(len(self.checked_repository.get_releases("alpha")), 3)
        self.assertTrue(self.checked_repository.has_package("alpha"))
        self.assertFalse(self.checked_repository.has_package("beta"))
        self.assertEqual(self.checked_repository.all_packages(), {"alpha"})

    def test_solver_highest_conformance(self) -> None:
        # POST: the highest precedence compatible release is selected.
        self.checked_repository.register_package(_release("alpha", Version(1, 0, 0)))
        self.checked_repository.register_package(_release("alpha", Version(1, 2, 0)))
        self.checked_repository.register_package(_release("alpha", Version(2, 0, 0)))
        outcome = self.checked_solver.resolve(
            [PackageDependency("alpha", VersionRange("^1.0.0"))]
        )
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 2, 0))
        self.assertEqual(len(outcome.derivation_steps), 1)

    def test_solver_transitive_conformance(self) -> None:
        # POST: transitive dependencies merge into accumulated constraints.
        self.checked_repository.register_package(
            _release(
                "alpha",
                Version(1, 1, 0),
                (_dependency("beta", "^2.0.0"),),
            )
        )
        self.checked_repository.register_package(
            _release(
                "alpha",
                Version(1, 0, 0),
                (_dependency("beta", "^2.0.0"),),
            )
        )
        self.checked_repository.register_package(_release("beta", Version(2, 0, 0)))
        self.checked_repository.register_package(_release("beta", Version(2, 1, 0)))
        outcome = self.checked_solver.resolve(
            [PackageDependency("alpha", VersionRange("^1.0.0"))]
        )
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 1, 0))
        self.assertEqual(outcome.selected_versions["beta"], Version(2, 1, 0))

    def test_solver_empty_conformance(self) -> None:
        # POST: no root dependencies resolves to an empty assignment.
        outcome = self.checked_solver.resolve([])
        self.assertEqual(outcome.selected_versions, {})
        self.assertEqual(outcome.derivation_steps, ())

    def test_solver_backtracking_conformance(self) -> None:
        # POST: conflicting candidate dependencies backtrack to lower candidates.
        self.checked_repository.register_package(
            _release(
                "alpha",
                Version(2, 0, 0),
                (_dependency("beta", "==2.0.0"),),
            )
        )
        self.checked_repository.register_package(
            _release(
                "alpha",
                Version(1, 0, 0),
                (_dependency("beta", "==1.0.0"),),
            )
        )
        self.checked_repository.register_package(_release("beta", Version(1, 0, 0)))
        outcome = self.checked_solver.resolve(
            [
                PackageDependency("alpha", VersionRange("*")),
                PackageDependency("beta", VersionRange("*")),
            ]
        )
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 0, 0))
        self.assertEqual(outcome.selected_versions["beta"], Version(1, 0, 0))

    def test_solver_forwarded_constraints_conformance(self) -> None:
        # POST: constraints forwarded by a failed candidate are rolled back.
        self.checked_repository.register_package(
            _release(
                "alpha",
                Version(2, 0, 0),
                (_dependency("beta", "==2.0.0"),),
            )
        )
        self.checked_repository.register_package(_release("alpha", Version(1, 0, 0)))
        self.checked_repository.register_package(
            _release(
                "beta",
                Version(2, 0, 0),
                (_dependency("gamma", ">=9.0.0"),),
            )
        )
        outcome = self.checked_solver.resolve(
            [PackageDependency("alpha", VersionRange("*"))]
        )
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 0, 0))
        self.assertNotIn("beta", outcome.selected_versions)
        self.assertNotIn("gamma", outcome.selected_versions)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:10:45Z
# LAST_CHANGED: 2026-11-05T04:10:45Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 89d8adb97f99
# COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:10:45Z
# QA_AUDIT: 2026-11-05T04:10:45Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple, cast
import unittest

from pretense import (
    Domain,
    StateMachine,
    require,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_4.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
    PackageRepository,
)


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    packages: Dict[str, List[str]] = field(default_factory=dict)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        fake_ret = False
        ret = self.inner_is_prerelease()
        return ret

    @transition(Version.format)
    def format(self) -> str:
        require(self.state.initialized)
        fake_ret = "1.0.0"
        ret = self.inner_format()
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.type(str), preferred=["1.2.3"])
        fake_ret = cast(Version, None)
        ret = self.inner_parse_version(text)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version))
        require_arg(v2, Domain.type(Version))
        fake_ret = 0
        ret = self.inner_compare_precedence(v1, v2)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.type(str), preferred=[">=1.0.0"])
        fake_ret = cast(VersionRange, None)
        ret = self.inner_parse_range(text)
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
        require_arg(range_constraint, Domain.type(VersionRange))
        require_arg(include_prerelease, Domain.boolean())
        fake_ret = False
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.type(PackageRelease))
        ret = self.inner_register_package(release)
        self.state.packages.setdefault(release.name, []).append(
            release.version.format()
        )
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["alpha"])
        fake_ret: List[PackageRelease] = []
        ret = self.inner_get_releases(name)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["alpha"])
        fake_ret = name in self.state.packages
        ret = self.inner_has_package(name)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        require(self.state.initialized)
        fake_ret = set(self.state.packages.keys())
        ret = self.inner_all_packages()
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            cast(
                Domain[Collection[PackageDependency]],
                Domain.list_of(Domain.type(PackageDependency)),
            ),
        )
        fake_ret = cast(ResolutionOutcome, None)
        ret = self.inner_resolve(root_dependencies)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(
    state: Optional[SemverSolverState] = None,
) -> Any:
    """Creates a synthesized fake sharing the canonical model state."""
    return FakeSemverSolver(state=state or SemverSolverState())


class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.sm = SemverSolverStateMachine()
        self.fake = make_semver_solver_fake()
        self.assertIsNotNone(self.fake)

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.assertFalse(self.sm.is_prerelease())
        self.assertEqual(self.sm.format(), "1.0.0")
        self.assertIsNone(self.sm.parse_version("1.2.3"))
        self.assertEqual(
            self.sm.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)),
            0,
        )
        self.assertIsNone(self.sm.parse_range(">=1.0.0"))
        self.assertFalse(
            self.sm.satisfies(Version(1, 0, 0), VersionRange("*"), False)
        )
        self.sm.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.assertEqual(self.sm.get_releases("alpha"), [])
        self.assertTrue(self.sm.has_package("alpha"))
        self.assertEqual(self.sm.all_packages(), {"alpha"})
        self.assertIsNone(self.sm.resolve([]))


FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:10:45Z
# LAST_CHANGED: 2026-11-05T04:10:45Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9492fcc4e760
# COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:10:45Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:10:45Z
# QA_AUDIT: 2026-11-05T04:10:45Z
# --- END AUTOFAB METADATA ---
