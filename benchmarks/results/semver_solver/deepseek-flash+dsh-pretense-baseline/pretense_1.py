"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SemverSolver.

Maps the operational postconditions of ``low/semver_solver.pyi`` and
``low/semver_solver_impl.pyi`` onto transitions over the version engine, the
package repository, and the backtracking dependency solver.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_7.parts.semver_solver.lib.semver_solver import (
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionRange,
)
from benchmark_7.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    releases: Dict[str, List[Version]] = field(default_factory=dict)
    resolution: Dict[str, Version] = field(default_factory=dict)


def _model_version(text: str) -> Version:
    """Parses a minimally formatted version into a model record."""
    core, _, build_text = text.partition("+")
    core, _, prerelease_text = core.partition("-")
    major_text, minor_text, patch_text = core.split(".")
    return Version(
        major=int(major_text),
        minor=int(minor_text),
        patch=int(patch_text),
        prerelease=tuple(prerelease_text.split(".")) if prerelease_text else (),
        build=tuple(build_text.split(".")) if build_text else (),
    )


def _model_compare(left: Version, right: Version) -> int:
    """Model precedence comparison used by synthesized fakes."""
    left_key = (left.major, left.minor, left.patch)
    right_key = (right.major, right.minor, right.patch)
    if left_key != right_key:
        return -1 if left_key < right_key else 1
    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1
    for left_part, right_part in zip(left.prerelease, right.prerelease):
        if left_part == right_part:
            continue
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_part) < int(right_part) else 1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left_part < right_part else 1
    if len(left.prerelease) == len(right.prerelease):
        return 0
    return -1 if len(left.prerelease) < len(right.prerelease) else 1


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        ctx: TransitionContext[VersionEngine, [str], Version],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: '1.2.3', validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text=None: _model_version(text or "1.2.3"))
        ctx.ensures(
            lambda res, target, check, text=None: check.equal(
                res.format(), text, "parse_version must round-trip the canonical text"
            )
        )
        ctx.update(lambda res, text=None: None)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [Version, Version], int],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    v1=Domain(strategy=lambda: Version(1, 0, 0), validator=lambda v1: isinstance(v1, Version)),
                    v2=Domain(strategy=lambda: Version(2, 0, 0), validator=lambda v2: isinstance(v2, Version)),
                )
        ctx.returns(lambda v1=None, v2=None: _model_compare(v1, v2))
        ctx.ensures(
            lambda res, target, check, v1=None, v2=None: check.equal(
                res,
                -target.compare_precedence(v2, v1),
                "precedence comparison must be antisymmetric",
            )
        )
        ctx.update(lambda res, v1=None, v2=None: None)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[VersionEngine, [str], VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: '>=1.0.0', validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text=None: VersionRange(raw_text=(text or "").strip()))
        ctx.ensures(
            lambda res, target, check, text=None: check.equal(
                res.raw_text,
                " || ".join(
                    clause.strip() for clause in (text or "").strip().split("||")
                ),
                "parse_range must store the trimmed range expression",
            )
        )
        ctx.update(lambda res, text=None: None)

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [Version, VersionRange, bool], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    version=Domain(strategy=lambda: Version(1, 2, 3), validator=lambda version: isinstance(version, Version)),
                    range_constraint=Domain(strategy=lambda: VersionRange('>=1.0.0'), validator=lambda range_constraint: isinstance(range_constraint, VersionRange)),
                    include_prerelease=Domain(strategy=lambda: False),
                )
        ctx.returns(
            lambda version=None, range_constraint=None, include_prerelease=False: True
        )
        ctx.ensures(self._ensure_satisfies)
        ctx.update(
            lambda res, version=None, range_constraint=None, include_prerelease=False: None
        )

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [PackageRelease], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(release=Domain(strategy=lambda: PackageRelease(name='pkg-a', version=Version(1, 0, 0)), validator=lambda release: isinstance(release, PackageRelease)))
        ctx.returns(lambda release=None: None)
        ctx.ensures(self._ensure_registered)
        ctx.update(
            lambda res, release=None: self.state.releases.setdefault(
                release.name, []
            ).append(release.version)
        )

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain(strategy=lambda: 'pkg-a', validator=lambda name: isinstance(name, str)))
        ctx.returns(
            lambda name=None: [
                PackageRelease(name=name or "pkg-a", version=version)
                for version in self.state.releases.get(name or "pkg-a", [])
            ]
        )
        ctx.ensures(self._ensure_releases)
        ctx.update(lambda res, name=None: None)

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain(strategy=lambda: 'pkg-a', validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name=None: (name or "") in self.state.releases)
        ctx.ensures(
            lambda res, target, check, name=None: check.equal(
                res,
                name in target.all_packages(),
                "has_package must agree with the registered package set",
            )
        )
        ctx.update(lambda res, name=None: None)

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
        ctx: TransitionContext[PackageRepository, [], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda: set(self.state.releases))
        ctx.ensures(self._ensure_all_packages)
        ctx.update(lambda res: None)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[DependencySolver, [Sequence[PackageDependency]], ResolutionOutcome],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: (), validator=lambda root_dependencies: root_dependencies is not None))
        ctx.returns(
            lambda root_dependencies=None: ResolutionOutcome(
                selected_versions=dict(self.state.resolution),
                derivation_steps=tuple(
                    f"Assign '{name}' to {version}"
                    for name, version in self.state.resolution.items()
                ),
            )
        )
        ctx.ensures(self._ensure_resolution)
        ctx.update(lambda res, root_dependencies=None: None)

    def _ensure_satisfies(
        self,
        res: bool,
        target: VersionEngine,
        check: Any,
        version: Optional[Version] = None,
        range_constraint: Optional[VersionRange] = None,
        include_prerelease: bool = False,
    ) -> None:
        if version is None or range_constraint is None:
            return
        text = range_constraint.raw_text.strip()
        if text in ("*", "x", "X") and not version.is_prerelease:
            check.equal(res, True, "an any-version range admits normal versions")
            return
        if version.is_prerelease and not include_prerelease and res:
            marker = f"{version.major}.{version.minor}.{version.patch}-"
            check(
                marker in text,
                "prerelease admission requires an explicit prerelease target",
            )
        if not version.is_prerelease:
            check.equal(
                res,
                target.satisfies(version, range_constraint),
                "normal versions are unaffected by prerelease inclusion",
            )

    def _ensure_registered(
        self,
        res: Any,
        target: PackageRepository,
        check: Any,
        release: Optional[PackageRelease] = None,
    ) -> None:
        if release is None:
            return
        check(target.has_package(release.name), "registered package must be present")
        check(
            release.version in [item.version for item in target.get_releases(release.name)],
            "registered release must appear in the package history",
        )

    def _ensure_releases(
        self,
        res: List[PackageRelease],
        target: PackageRepository,
        check: Any,
        name: Optional[str] = None,
    ) -> None:
        if name is None:
            return
        check(
            all(item.name == name for item in res),
            "release history entries must belong to the requested package",
        )
        for newer, older in zip(res, res[1:]):
            check(
                self._compare_versions(newer.version, older.version) >= 0,
                "release history must be ordered by descending precedence",
            )

    def _compare_versions(self, left: Version, right: Version) -> int:
        return _model_compare(left, right)

    def _ensure_all_packages(
        self,
        res: Set[str],
        target: PackageRepository,
        check: Any,
    ) -> None:
        for name in res:
            check(
                target.has_package(name),
                "every reported package must be recognized by the repository",
            )

    def _ensure_resolution(
        self,
        res: ResolutionOutcome,
        target: DependencySolver,
        check: Any,
        root_dependencies: Optional[Sequence[PackageDependency]] = None,
    ) -> None:
        engine: Any = target if hasattr(target, "satisfies") else check.get(VersionEngine)
        for dependency in root_dependencies or ():
            check(
                dependency.name in res.selected_versions,
                "every root dependency must be selected in a successful outcome",
            )
            check(
                engine.satisfies(
                    res.selected_versions[dependency.name], dependency.range_constraint
                ),
                "selected releases must satisfy their accumulated constraints",
            )
        check(
            len(res.derivation_steps) >= len(res.selected_versions),
            "each assignment must contribute a derivation step",
        )


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    sm = SemverSolverStateMachine(state or SemverSolverState())
    return (
        sm.as_fake(VersionEngine),
        sm.as_fake(PackageRepository),
        sm.as_fake(DependencySolver),
    )


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestSemverSolverUnit(unittest.TestCase):
    """Verifies that synthesized fakes conform to state machine specification."""

    def setUp(self) -> None:
        self.state = SemverSolverState()
        self.versionengine, self.packagerepository, self.dependencysolver = make_semver_solver_fakes(self.state)

    def test_fake_initial_state(self) -> None:
        self.assertTrue(self.state.initialized)

    def test_fake_parse_version(self) -> None:
        res = self.versionengine.parse_version("1.2.3")
        self.assertEqual(res.format(), "1.2.3")

    def test_fake_compare_precedence(self) -> None:
        res = self.versionengine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0))
        self.assertLess(res, 0)

    def test_fake_parse_range(self) -> None:
        res = self.versionengine.parse_range(">=1.0.0")
        self.assertEqual(res.raw_text, ">=1.0.0")

    def test_fake_satisfies(self) -> None:
        res = self.versionengine.satisfies(Version(1, 2, 3), VersionRange(">=1.0.0"))
        self.assertTrue(res)

    def test_fake_register_package(self) -> None:
        self.packagerepository.register_package(
            PackageRelease(name="pkg-a", version=Version(1, 0, 0))
        )
        self.assertTrue(self.packagerepository.has_package("pkg-a"))

    def test_fake_get_releases(self) -> None:
        self.packagerepository.register_package(
            PackageRelease(name="pkg-a", version=Version(1, 0, 0))
        )
        res = self.packagerepository.get_releases("pkg-a")
        self.assertEqual([item.version for item in res], [Version(1, 0, 0)])

    def test_fake_has_package(self) -> None:
        self.packagerepository.register_package(
            PackageRelease(name="pkg-a", version=Version(1, 0, 0))
        )
        self.assertTrue(self.packagerepository.has_package("pkg-a"))
        self.assertFalse(self.packagerepository.has_package("pkg-b"))

    def test_fake_all_packages(self) -> None:
        self.packagerepository.register_package(
            PackageRelease(name="pkg-a", version=Version(1, 0, 0))
        )
        self.assertIn("pkg-a", self.packagerepository.all_packages())

    def test_fake_resolve(self) -> None:
        res = self.dependencysolver.resolve(())
        self.assertEqual(dict(res.selected_versions), {})


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.sm = SemverSolverStateMachine(singletons={VersionEngine: self.versionengine, PackageRepository: self.packagerepository, DependencySolver: self.dependencysolver})

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    # --- VersionEngine.parse_version ---

    def test_real_parse_version_with_extras(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.2.3-alpha.1+build.5")

    def test_real_parse_version_plain(self) -> None:
        self.sm.dispatch_transition("parse_version", "10.20.30")

    def test_real_parse_version_invalid(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.0.0")

    def test_real_parse_version_malformed(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("not-a-version")

    # --- VersionEngine.compare_precedence ---

    def test_real_compare_major(self) -> None:
        self.sm.dispatch_transition("compare_precedence", Version(1, 0, 0), Version(2, 0, 0))
        self.sm.dispatch_transition("compare_precedence", Version(2, 0, 0), Version(1, 0, 0))

    def test_real_compare_minor(self) -> None:
        self.sm.dispatch_transition("compare_precedence", Version(1, 1, 0), Version(1, 2, 0))
        self.sm.dispatch_transition("compare_precedence", Version(1, 2, 0), Version(1, 1, 0))

    def test_real_compare_patch(self) -> None:
        self.sm.dispatch_transition("compare_precedence", Version(1, 0, 1), Version(1, 0, 2))
        self.sm.dispatch_transition("compare_precedence", Version(1, 0, 2), Version(1, 0, 1))

    def test_real_compare_equal_versions(self) -> None:
        self.sm.dispatch_transition("compare_precedence", Version(1, 2, 3), Version(1, 2, 3))

    def test_real_compare_build_metadata_ignored(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, build=("a",)),
            Version(1, 0, 0, build=("b",)),
        )

    def test_real_compare_normal_ranks_above_prerelease(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence", Version(1, 0, 0, prerelease=("alpha",)), Version(1, 0, 0)
        )
        self.sm.dispatch_transition(
            "compare_precedence", Version(1, 0, 0), Version(1, 0, 0, prerelease=("alpha",))
        )

    def test_real_compare_prerelease_strings(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, prerelease=("alpha",)),
            Version(1, 0, 0, prerelease=("beta",)),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, prerelease=("beta",)),
            Version(1, 0, 0, prerelease=("alpha",)),
        )

    def test_real_compare_prerelease_numeric(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, prerelease=("alpha", "1")),
            Version(1, 0, 0, prerelease=("alpha", "2")),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, prerelease=("alpha", "2")),
            Version(1, 0, 0, prerelease=("alpha", "1")),
        )

    def test_real_compare_numeric_ranks_below_string(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, prerelease=("alpha", "1")),
            Version(1, 0, 0, prerelease=("alpha", "beta")),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, prerelease=("alpha", "beta")),
            Version(1, 0, 0, prerelease=("alpha", "1")),
        )

    def test_real_compare_prerelease_length(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, prerelease=("alpha",)),
            Version(1, 0, 0, prerelease=("alpha", "1")),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, prerelease=("alpha", "1")),
            Version(1, 0, 0, prerelease=("alpha",)),
        )

    def test_real_compare_prerelease_shared_prefix(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, prerelease=("alpha", "1")),
            Version(1, 0, 0, prerelease=("alpha", "1")),
        )

    # --- VersionEngine.parse_range ---

    def test_real_parse_range_simple(self) -> None:
        self.sm.dispatch_transition("parse_range", ">=1.0.0")

    def test_real_parse_range_trimmed(self) -> None:
        self.sm.dispatch_transition("parse_range", "  >= 1.0.0   ||   < 2.0.0  ")

    def test_real_parse_range_hyphen(self) -> None:
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0")

    def test_real_parse_range_wildcards(self) -> None:
        self.sm.dispatch_transition("parse_range", "1.x")
        self.sm.dispatch_transition("parse_range", "1.2.*")
        self.sm.dispatch_transition("parse_range", "*")

    def test_real_parse_range_caret_tilde(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.2.3")
        self.sm.dispatch_transition("parse_range", "~1.2.3")

    def test_real_parse_range_exact_version(self) -> None:
        self.sm.dispatch_transition("parse_range", "1.0.0")

    def test_real_parse_range_empty(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("")

    def test_real_parse_range_whitespace_only(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("   ")

    def test_real_parse_range_comma(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0, <2.0.0")

    def test_real_parse_range_empty_clause(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0 || ")

    def test_real_parse_range_operator_without_target(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=")

    def test_real_parse_range_relational_wildcard(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=*")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.x")

    def test_real_parse_range_partial_version(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2")

    def test_real_parse_range_partial_hyphen(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.3")

    def test_real_parse_range_malformed_version(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0.0")

    # --- VersionEngine.satisfies ---

    def test_real_satisfies_ge(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange(">=1.0.0"))

    def test_real_satisfies_lt(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("<2.0.0"))

    def test_real_satisfies_le(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("<=1.2.3"))

    def test_real_satisfies_gt(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange(">1.0.0"))

    def test_real_satisfies_eq(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("==1.2.3"))
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("1.2.3"))

    def test_real_satisfies_ne(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("!=1.2.3"))

    def test_real_satisfies_wildcards(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("1.x"))
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("1.2.*"))
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("*"))

    def test_real_satisfies_union(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(2, 5, 0), VersionRange(">=1.0.0 <2.0.0 || >=2.0.0")
        )

    def test_real_satisfies_hyphen(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("1.0.0 - 2.0.0"))

    def test_real_satisfies_caret(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("^1.2.3"))

    def test_real_satisfies_caret_zero_minor(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(0, 2, 5), VersionRange("^0.2.3"))

    def test_real_satisfies_caret_zero_patch(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(0, 0, 3), VersionRange("^0.0.3"))

    def test_real_satisfies_caret_zero(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(0, 0, 0), VersionRange("^0.0.0"))

    def test_real_satisfies_tilde(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 9), VersionRange("~1.2.3"))

    def test_real_satisfies_prerelease_explicit(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 0, 0, prerelease=("alpha",)), VersionRange(">=1.0.0-alpha")
        )

    def test_real_satisfies_prerelease_filtered(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 0, 0, prerelease=("alpha",)), VersionRange(">=1.0.0")
        )
        self.sm.dispatch_transition(
            "satisfies",
            Version(1, 0, 1, prerelease=("alpha",)),
            VersionRange(">=1.0.0"),
        )

    def test_real_satisfies_prerelease_included(self) -> None:
        self.sm.dispatch_transition(
            "satisfies",
            Version(1, 0, 1, prerelease=("alpha",)),
            VersionRange(">=1.0.0"),
            True,
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 0, 0, prerelease=("alpha",)), VersionRange("*"), True
        )

    def test_real_satisfies_prerelease_wildcard(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 0, 0, prerelease=("alpha",)), VersionRange("*")
        )

    # --- PackageRepository ---

    def _register(self, name: str, version: Version) -> None:
        self.sm.dispatch_transition(
            "register_package", PackageRelease(name=name, version=version)
        )

    def test_real_repository_ordering(self) -> None:
        self._register("pkg-a", Version(1, 0, 0))
        self._register("pkg-a", Version(3, 0, 0))
        self._register("pkg-a", Version(2, 0, 0))
        self.sm.dispatch_transition("get_releases", "pkg-a")

    def test_real_repository_has_package(self) -> None:
        self._register("pkg-a", Version(1, 0, 0))
        self.sm.dispatch_transition("has_package", "pkg-a")
        self.sm.dispatch_transition("has_package", "pkg-b")

    def test_real_repository_all_packages(self) -> None:
        self._register("pkg-a", Version(1, 0, 0))
        self._register("pkg-b", Version(1, 0, 0))
        self.sm.dispatch_transition("all_packages")

    def test_real_repository_missing_release(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("pkg-missing")

    # --- DependencySolver ---

    def _dependency(self, name: str, raw_range: str) -> PackageDependency:
        return PackageDependency(name=name, range_constraint=VersionRange(raw_range))

    def test_real_solver_highest_version(self) -> None:
        self._register("pkg-a", Version(1, 0, 0))
        self._register("pkg-a", Version(2, 0, 0))
        self.sm.dispatch_transition(
            "resolve", (self._dependency("pkg-a", "*"),)
        )

    def test_real_solver_empty_roots(self) -> None:
        self.sm.dispatch_transition("resolve", ())

    def test_real_solver_transitive(self) -> None:
        self.sm.dispatch_transition(
            "register_package",
            PackageRelease(
                name="pkg-a",
                version=Version(1, 0, 0),
                dependencies=(self._dependency("pkg-b", ">=1.0.0"),),
            ),
        )
        self._register("pkg-b", Version(1, 5, 0))
        self.sm.dispatch_transition(
            "resolve", (self._dependency("pkg-a", "*"),)
        )

    def test_real_solver_backtracks_to_lower_release(self) -> None:
        self.sm.dispatch_transition(
            "register_package",
            PackageRelease(
                name="pkg-a",
                version=Version(2, 0, 0),
                dependencies=(self._dependency("pkg-b", ">=2.0.0"),),
            ),
        )
        self.sm.dispatch_transition(
            "register_package",
            PackageRelease(
                name="pkg-a",
                version=Version(1, 0, 0),
                dependencies=(self._dependency("pkg-b", ">=1.0.0"),),
            ),
        )
        self._register("pkg-b", Version(1, 0, 0))
        self.sm.dispatch_transition(
            "resolve", (self._dependency("pkg-a", "*"),)
        )

    def test_real_solver_forward_check_conflict(self) -> None:
        self.sm.dispatch_transition(
            "register_package",
            PackageRelease(
                name="pkg-a",
                version=Version(2, 0, 0),
                dependencies=(self._dependency("pkg-c", ">=2.0.0"),),
            ),
        )
        self.sm.dispatch_transition(
            "register_package",
            PackageRelease(
                name="pkg-a",
                version=Version(1, 0, 0),
                dependencies=(self._dependency("pkg-c", ">=1.0.0"),),
            ),
        )
        self._register("pkg-c", Version(1, 0, 0))
        self.sm.dispatch_transition(
            "resolve",
            (self._dependency("pkg-a", "*"), self._dependency("pkg-c", "*")),
        )

    def test_real_solver_missing_package(self) -> None:
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve((self._dependency("pkg-missing", "*"),))

    def test_real_solver_no_viable_release(self) -> None:
        self._register("pkg-a", Version(1, 0, 0))
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve((self._dependency("pkg-a", ">=2.0.0"),))

    def test_real_solver_unsatisfiable_dependency(self) -> None:
        self.sm.dispatch_transition(
            "register_package",
            PackageRelease(
                name="pkg-a",
                version=Version(2, 0, 0),
                dependencies=(self._dependency("pkg-c", ">=2.0.0"),),
            ),
        )
        self._register("pkg-c", Version(1, 0, 0))
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(
                (self._dependency("pkg-a", "*"), self._dependency("pkg-c", "*"))
            )


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing component services for Hypothesis fuzzing."""

    tier = system

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
            PackageRelease(name="pkg-a", version=Version(1, 0, 0))
        )
        self.__dict__["_services"] = (self.versionengine, self.packagerepository, self.dependencysolver,)

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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T21:35:36Z
# LAST_CHANGED: 2026-10-28T21:35:36Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: d4106a7a4b43
# COVERAGE_AUDIT: 2026-10-28T21:35:36Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T21:35:36Z
# PRETENSE_QA_AUDIT: 2026-10-28T21:35:36Z
# QA_AUDIT: 2026-10-28T21:35:36Z
# --- END CLEANROOM METADATA ---
