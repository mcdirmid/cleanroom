"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
import re
from typing import Any, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.semver_solver.lib import semver_solver
from benchmark_2.parts.semver_solver.lib.semver_solver_impl import (
    VersionEngine,
    PackageRepository,
    DependencySolver,
    __initialize__,
)


# ==============================================================================
# Helper Model Utilities (Oracles for Pretense Fakes & Verification)
# ==============================================================================

_VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _model_parse_version(text: str) -> semver_solver.Version:
    match = _VERSION_RE.match(text)
    if not match:
        raise semver_solver.InvalidVersionError(
            message=f"Invalid semantic version string: '{text}'",
            raw_text=text,
        )

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))

    raw_prerelease = match.group("prerelease")
    prerelease_parts: Tuple[str, ...] = ()
    if raw_prerelease:
        parts = raw_prerelease.split(".")
        for part in parts:
            if not part or (part.isdigit() and len(part) > 1 and part.startswith("0")):
                raise semver_solver.InvalidVersionError(
                    message=f"Invalid pre-release identifier: '{part}' in '{text}'",
                    raw_text=text,
                )
        prerelease_parts = tuple(parts)

    raw_build = match.group("build")
    build_parts: Tuple[str, ...] = ()
    if raw_build:
        parts = raw_build.split(".")
        for part in parts:
            if not part:
                raise semver_solver.InvalidVersionError(
                    message=f"Invalid build metadata: '{part}' in '{text}'",
                    raw_text=text,
                )
        build_parts = tuple(parts)

    return semver_solver.Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease_parts,
        build=build_parts,
    )


def _model_compare_precedence(v1: semver_solver.Version, v2: semver_solver.Version) -> int:
    if v1.major != v2.major:
        return -1 if v1.major < v2.major else 1
    if v1.minor != v2.minor:
        return -1 if v1.minor < v2.minor else 1
    if v1.patch != v2.patch:
        return -1 if v1.patch < v2.patch else 1

    if not v1.is_prerelease and v2.is_prerelease:
        return 1
    if v1.is_prerelease and not v2.is_prerelease:
        return -1
    if not v1.is_prerelease and not v2.is_prerelease:
        return 0

    min_len = min(len(v1.prerelease), len(v2.prerelease))
    for i in range(min_len):
        p1 = v1.prerelease[i]
        p2 = v2.prerelease[i]
        if p1 == p2:
            continue
        p1_is_num = p1.isdigit()
        p2_is_num = p2.isdigit()
        if p1_is_num and p2_is_num:
            n1, n2 = int(p1), int(p2)
            if n1 != n2:
                return -1 if n1 < n2 else 1
        elif p1_is_num and not p2_is_num:
            return -1
        elif not p1_is_num and p2_is_num:
            return 1
        else:
            if p1 != p2:
                return -1 if p1 < p2 else 1

    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    return 0


def _model_satisfies(
    version: semver_solver.Version,
    range_constraint: semver_solver.VersionRange,
    include_prerelease: bool = False,
) -> bool:
    clauses = [c.strip() for c in range_constraint.raw_text.split("||")]
    for clause in clauses:
        if not clause:
            continue
        tokens = clause.split()
        clause_ok = True
        explicit_prerelease = False

        for tok in tokens:
            op = "="
            op_str = tok
            for candidate_op in ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~"):
                if tok.startswith(candidate_op):
                    op = candidate_op
                    op_str = tok[len(candidate_op):]
                    break

            if op_str in ("*", "x", "X"):
                if op in ("<", ">", "!="):
                    clause_ok = False
                    break
                continue

            # Major wildcard M.x
            m_maj = re.match(r"^(0|[1-9]\d*)\.[*xX]$", op_str)
            if m_maj:
                maj = int(m_maj.group(1))
                if op in ("==", "=", "~", "^"):
                    if not (version.major == maj):
                        clause_ok = False
                        break
                elif op == ">=":
                    if not (version.major >= maj):
                        clause_ok = False
                        break
                elif op == ">":
                    if not (version.major > maj):
                        clause_ok = False
                        break
                elif op == "<=":
                    if not (version.major <= maj):
                        clause_ok = False
                        break
                elif op == "<":
                    if not (version.major < maj):
                        clause_ok = False
                        break
                elif op == "!=":
                    if version.major == maj:
                        clause_ok = False
                        break
                continue

            # Version operand
            try:
                target_ver = _model_parse_version(op_str)
            except Exception:
                clause_ok = False
                break

            if target_ver.is_prerelease and (target_ver.major, target_ver.minor, target_ver.patch) == (version.major, version.minor, version.patch):
                explicit_prerelease = True

            cmp = _model_compare_precedence(version, target_ver)
            if op in ("==", "="):
                if cmp != 0:
                    clause_ok = False
                    break
            elif op == "!=":
                if cmp == 0:
                    clause_ok = False
                    break
            elif op == "<":
                if not (cmp < 0):
                    clause_ok = False
                    break
            elif op == "<=":
                if not (cmp <= 0):
                    clause_ok = False
                    break
            elif op == ">":
                if not (cmp > 0):
                    clause_ok = False
                    break
            elif op == ">=":
                if not (cmp >= 0):
                    clause_ok = False
                    break
            elif op == "~":
                upper = semver_solver.Version(target_ver.major, target_ver.minor + 1, 0)
                if not (cmp >= 0 and _model_compare_precedence(version, upper) < 0):
                    clause_ok = False
                    break
            elif op == "^":
                if target_ver.major > 0:
                    upper = semver_solver.Version(target_ver.major + 1, 0, 0)
                elif target_ver.minor > 0:
                    upper = semver_solver.Version(0, target_ver.minor + 1, 0)
                else:
                    upper = semver_solver.Version(0, 0, target_ver.patch + 1)
                if not (cmp >= 0 and _model_compare_precedence(version, upper) < 0):
                    clause_ok = False
                    break

        if not clause_ok:
            continue

        if version.is_prerelease and not include_prerelease and not explicit_prerelease:
            continue

        return True

    return False


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""
    registered_packages: Dict[str, List[semver_solver.PackageRelease]] = field(default_factory=dict)


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
        ctx: TransitionContext[VersionEngine, [str], semver_solver.Version],
    ) -> None:
        ctx.arguments(text=Domain(strategy=lambda: st.sampled_from(['1.0.0', '0.1.0', '1.2.3', '2.0.0-alpha.1', '0.0.1+build']), validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text="": _model_parse_version(text))
        ctx.ensures(lambda res, target, check, text="": (
            check(isinstance(res, semver_solver.Version), "Must return Version"),
            check.equal(res.major, _model_parse_version(text).major),
            check.equal(res.minor, _model_parse_version(text).minor),
            check.equal(res.patch, _model_parse_version(text).patch),
            check.equal(res.prerelease, _model_parse_version(text).prerelease),
            check.equal(res.build, _model_parse_version(text).build),
            check.equal(res.is_prerelease, len(res.prerelease) > 0),
            check.equal(str(res), res.format()),
        ))

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [semver_solver.Version, semver_solver.Version], int],
    ) -> None:
        ctx.arguments(
                    v1=Domain(strategy=lambda: st.sampled_from([semver_solver.Version(1, 0, 0), semver_solver.Version(2, 0, 0), semver_solver.Version(1, 0, 0, ('alpha',))]), validator=lambda v1: isinstance(v1, semver_solver.Version)),
                    v2=Domain(strategy=lambda: st.sampled_from([semver_solver.Version(1, 0, 0), semver_solver.Version(2, 0, 0), semver_solver.Version(1, 0, 0, ('beta',))]), validator=lambda v2: isinstance(v2, semver_solver.Version)),
                )
        ctx.returns(lambda v1=semver_solver.Version(0, 0, 0), v2=semver_solver.Version(0, 0, 0): _model_compare_precedence(v1, v2))
        ctx.ensures(lambda res, target, check, v1=semver_solver.Version(0, 0, 0), v2=semver_solver.Version(0, 0, 0): (
            check(res in (-1, 0, 1), "Result must be -1, 0, or 1"),
            check.equal(res, _model_compare_precedence(v1, v2)),
            check.equal(res == 0, _model_compare_precedence(v2, v1) == 0),
        ))

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[VersionEngine, [str], semver_solver.VersionRange],
    ) -> None:
        ctx.arguments(text=Domain(strategy=lambda: st.sampled_from(['>=1.0.0 <2.0.0', '^1.2.3', '~1.0.0', '1.0.0 - 2.0.0', '*', '1.x', '>=2.0.0 || <1.0.0']), validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text="": semver_solver.VersionRange(
            raw_text=" || ".join(c.strip() for c in text.strip().split("||"))
        ))
        ctx.ensures(lambda res, target, check, text="": (
            check(isinstance(res, semver_solver.VersionRange), "Must return VersionRange"),
            check.equal(res.raw_text, " || ".join(c.strip() for c in text.strip().split("||"))),
            check.equal(str(res), res.raw_text),
        ))

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [semver_solver.Version, semver_solver.VersionRange, bool], bool],
    ) -> None:
        ctx.arguments(
                    version=Domain(strategy=lambda: st.sampled_from([semver_solver.Version(1, 0, 0), semver_solver.Version(1, 2, 0), semver_solver.Version(2, 0, 0), semver_solver.Version(1, 0, 0, ('alpha',))]), validator=lambda version: isinstance(version, semver_solver.Version)),
                    range_constraint=Domain(strategy=lambda: st.sampled_from([semver_solver.VersionRange('>=1.0.0'), semver_solver.VersionRange('<2.0.0'), semver_solver.VersionRange('*'), semver_solver.VersionRange('>=1.0.0-alpha')]), validator=lambda range_constraint: isinstance(range_constraint, semver_solver.VersionRange)),
                    include_prerelease=Domain(strategy=lambda: st.booleans(), validator=lambda include_prerelease: isinstance(include_prerelease, bool)),
                )
        ctx.returns(lambda version=semver_solver.Version(0, 0, 0), range_constraint=semver_solver.VersionRange("*"), include_prerelease=False: (
            _model_satisfies(version, range_constraint, include_prerelease)
        ))
        ctx.ensures(lambda res, target, check, version=semver_solver.Version(0, 0, 0), range_constraint=semver_solver.VersionRange("*"), include_prerelease=False: (
            check(isinstance(res, bool), "Must return bool"),
        ))

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [semver_solver.PackageRelease], None],
    ) -> None:
        ctx.arguments(release=Domain(strategy=lambda: st.sampled_from([semver_solver.PackageRelease(name='pkgA', version=semver_solver.Version(1, 0, 0)), semver_solver.PackageRelease(name='pkgA', version=semver_solver.Version(2, 0, 0)), semver_solver.PackageRelease(name='pkgB', version=semver_solver.Version(1, 0, 0))]), validator=lambda release: isinstance(release, semver_solver.PackageRelease)))
        ctx.returns(lambda release=semver_solver.PackageRelease("", semver_solver.Version(0, 0, 0)): None)
        ctx.update(lambda res, release=semver_solver.PackageRelease("", semver_solver.Version(0, 0, 0)): (
            self._update_register(release)
        ))
        ctx.ensures(lambda res, target, check, release=semver_solver.PackageRelease("", semver_solver.Version(0, 0, 0)): (
            check(target.has_package(release.name), f"Package {release.name} must be present"),
            check(release.name in target.all_packages(), f"{release.name} must be in all_packages"),
            check(len(target.get_releases(release.name)) > 0, f"{release.name} must have releases"),
        ))

    def _update_register(self, release: semver_solver.PackageRelease) -> None:
        if not release.name:
            return
        rels = self.state.registered_packages.setdefault(release.name, [])
        rels.append(release)

        def _cmp_releases(r1: semver_solver.PackageRelease, r2: semver_solver.PackageRelease) -> int:
            return _model_compare_precedence(r1.version, r2.version)

        rels.sort(key=cmp_to_key(_cmp_releases), reverse=True)

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[semver_solver.PackageRelease]],
    ) -> None:
        ctx.arguments(name=Domain(strategy=lambda: st.sampled_from(list(self.state.registered_packages.keys()) if self.state.registered_packages else ['pkgA']), validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name="": (
            list(self.state.registered_packages[name])
            if name in self.state.registered_packages
            else Raised(semver_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            ))
        ))
        ctx.ensures(lambda res, target, check, name="": (
            check(isinstance(res, list), "Must return list"),
            check.equal(len(res), len(self.state.registered_packages[name])),
            check(all(r.name == name for r in res), f"All releases must have name {name}"),
        ))

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.arguments(name=Domain(strategy=lambda: st.sampled_from(['pkgA', 'pkgB', 'nonexistent']), validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name="": name in self.state.registered_packages)
        ctx.ensures(lambda res, target, check, name="": (
            check(isinstance(res, bool), "Must return bool"),
            check.equal(res, name in self.state.registered_packages),
        ))

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
        ctx: TransitionContext[PackageRepository, [], Set[str]],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: set(self.state.registered_packages.keys()))
        ctx.ensures(lambda res, target, check: (
            check(isinstance(res, set), "Must return set"),
            check.equal(res, set(self.state.registered_packages.keys())),
        ))

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[DependencySolver, [Collection[semver_solver.PackageDependency]], semver_solver.ResolutionOutcome],
    ) -> None:
        ctx.arguments(root_dependencies=Domain(strategy=lambda: st.sampled_from([(), (semver_solver.PackageDependency(name='pkgA', range_constraint=semver_solver.VersionRange('>=1.0.0')),)]), validator=lambda root_dependencies: isinstance(root_dependencies, (list, tuple))))
        ctx.returns(lambda root_dependencies=(): self._model_resolve(root_dependencies))
        ctx.ensures(lambda res, target, check, root_dependencies=(): (
            check(isinstance(res, semver_solver.ResolutionOutcome), "Must return ResolutionOutcome"),
            check(isinstance(res.selected_versions, (dict, Mapping)), "selected_versions must be mapping"),
            check(isinstance(res.derivation_steps, tuple), "derivation_steps must be tuple"),
            self._ensures_resolve(res, check, root_dependencies),
        ))

    def _model_resolve(self, root_dependencies: Collection[semver_solver.PackageDependency]) -> Any:
        if not root_dependencies:
            return semver_solver.ResolutionOutcome(
                selected_versions={},
                derivation_steps=(),
            )
        selected: Dict[str, semver_solver.Version] = {}
        for dep in root_dependencies:
            if dep.name not in self.state.registered_packages:
                return Raised(semver_solver.ResolutionConflictError(
                    message=f"Missing package: '{dep.name}'",
                    conflicting_packages=(dep.name,),
                    explanation=f"Package '{dep.name}' not registered",
                ))
            matching = [
                rel for rel in self.state.registered_packages[dep.name]
                if _model_satisfies(rel.version, dep.range_constraint)
            ]
            if not matching:
                return Raised(semver_solver.ResolutionConflictError(
                    message=f"No viable release for '{dep.name}'",
                    conflicting_packages=(dep.name,),
                    explanation=f"No viable release for '{dep.name}'",
                ))
            selected[dep.name] = matching[0].version
        return semver_solver.ResolutionOutcome(
            selected_versions=selected,
            derivation_steps=("Resolved from state",),
        )

    def _ensures_resolve(
        self,
        res: semver_solver.ResolutionOutcome,
        check: Any,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> None:
        for dep in root_dependencies:
            check(dep.name in res.selected_versions, f"Missing {dep.name}")
            check(
                _model_satisfies(res.selected_versions[dep.name], dep.range_constraint),
                f"Version for {dep.name} satisfies constraint",
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
        self.assertEqual(len(self.state.registered_packages), 0)

    def test_fake_parse_version(self) -> None:
        v = self.versionengine.parse_version("1.2.3")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)
        self.assertEqual(v.patch, 3)

    def test_fake_compare_precedence(self) -> None:
        v1 = semver_solver.Version(1, 0, 0)
        v2 = semver_solver.Version(2, 0, 0)
        res = self.versionengine.compare_precedence(v1, v2)
        self.assertEqual(res, -1)

    def test_fake_parse_range(self) -> None:
        rng = self.versionengine.parse_range("^1.2.3")
        self.assertEqual(rng.raw_text, "^1.2.3")

    def test_fake_satisfies(self) -> None:
        v = semver_solver.Version(1, 2, 0)
        rng = semver_solver.VersionRange("^1.0.0")
        res = self.versionengine.satisfies(v, rng, False)
        self.assertTrue(res)

    def test_fake_register_package(self) -> None:
        rel = semver_solver.PackageRelease(name="pkgA", version=semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        self.assertIn("pkgA", self.state.registered_packages)

    def test_fake_get_releases(self) -> None:
        rel = semver_solver.PackageRelease(name="pkgA", version=semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        releases = self.packagerepository.get_releases("pkgA")
        self.assertEqual(len(releases), 1)

    def test_fake_get_releases_missing_raises(self) -> None:
        with self.assertRaises(semver_solver.PackageNotFoundError):
            self.packagerepository.get_releases("missing_pkg")

    def test_fake_has_package(self) -> None:
        rel = semver_solver.PackageRelease(name="pkgA", version=semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        self.assertTrue(self.packagerepository.has_package("pkgA"))
        self.assertFalse(self.packagerepository.has_package("pkgB"))

    def test_fake_all_packages(self) -> None:
        rel = semver_solver.PackageRelease(name="pkgA", version=semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        self.assertEqual(self.packagerepository.all_packages(), {"pkgA"})

    def test_fake_resolve_empty(self) -> None:
        outcome = self.dependencysolver.resolve([])
        self.assertEqual(len(outcome.selected_versions), 0)

    def test_fake_resolve_registered(self) -> None:
        rel = semver_solver.PackageRelease(name="pkgA", version=semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        dep = semver_solver.PackageDependency(name="pkgA", range_constraint=semver_solver.VersionRange(">=1.0.0"))
        outcome = self.dependencysolver.resolve([dep])
        self.assertEqual(outcome.selected_versions["pkgA"], semver_solver.Version(1, 0, 0))

    def test_fake_resolve_missing_raises(self) -> None:
        dep = semver_solver.PackageDependency(name="pkg_missing", range_constraint=semver_solver.VersionRange("*"))
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve([dep])


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
        self.sm = SemverSolverStateMachine(singletons={
            VersionEngine: self.versionengine,
            PackageRepository: self.packagerepository,
            DependencySolver: self.dependencysolver,
        })

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    # --- Version Parsing Tests ---

    def test_real_parse_version_standard(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.2.3")
        self.sm.dispatch_transition("parse_version", "0.0.0")
        self.sm.dispatch_transition("parse_version", "10.20.30")

    def test_real_parse_version_prerelease(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.2.3-alpha.1")
        self.sm.dispatch_transition("parse_version", "1.0.0-beta.0")
        self.sm.dispatch_transition("parse_version", "2.0.0-x-y-z.-")

    def test_real_parse_version_build(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.2.3+20130313144700")
        self.sm.dispatch_transition("parse_version", "1.0.0+exp.sha.5114f85")
        self.sm.dispatch_transition("parse_version", "1.0.0+01.02")

    def test_real_parse_version_both(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.2.3-beta.11+build.2023")

    def test_real_parse_version_invalid_format_raises(self) -> None:
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.2")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.2.3.4")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("v1.2.3")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("abc")

    def test_real_parse_version_leading_zero_raises(self) -> None:
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("01.2.3")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.02.3")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.2.03")

    def test_real_parse_version_invalid_prerelease_raises(self) -> None:
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.2.3-..")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.2.3-01")

    def test_real_parse_version_invalid_build_raises(self) -> None:
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.2.3+..")

    # --- Precedence Comparison Tests ---

    def test_real_compare_precedence_numeric(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0),
            semver_solver.Version(2, 0, 0),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(2, 0, 0),
            semver_solver.Version(1, 0, 0),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 1, 0),
            semver_solver.Version(1, 2, 0),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 2, 0),
            semver_solver.Version(1, 1, 0),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 1, 1),
            semver_solver.Version(1, 1, 2),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 1, 2),
            semver_solver.Version(1, 1, 1),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 1, 1),
            semver_solver.Version(1, 1, 1),
        )

    def test_real_compare_precedence_normal_vs_prerelease(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0),
            semver_solver.Version(1, 0, 0, ("alpha",)),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("alpha",)),
            semver_solver.Version(1, 0, 0),
        )

    def test_real_compare_precedence_prerelease_rules(self) -> None:
        # Numeric vs numeric
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("1",)),
            semver_solver.Version(1, 0, 0, ("2",)),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("2",)),
            semver_solver.Version(1, 0, 0, ("1",)),
        )
        # Numeric vs string
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("1",)),
            semver_solver.Version(1, 0, 0, ("alpha",)),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("alpha",)),
            semver_solver.Version(1, 0, 0, ("1",)),
        )
        # String vs string
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("alpha",)),
            semver_solver.Version(1, 0, 0, ("beta",)),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("beta",)),
            semver_solver.Version(1, 0, 0, ("alpha",)),
        )
        # Length differences with matching prefix
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("alpha",)),
            semver_solver.Version(1, 0, 0, ("alpha", "1")),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("alpha", "1")),
            semver_solver.Version(1, 0, 0, ("alpha",)),
        )
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, ("alpha", "1")),
            semver_solver.Version(1, 0, 0, ("alpha", "1")),
        )

    def test_real_compare_precedence_build_ignored(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            semver_solver.Version(1, 0, 0, (), ("build1",)),
            semver_solver.Version(1, 0, 0, (), ("build2",)),
        )

    # --- Range Parsing & Satisfaction Tests ---

    def test_real_parse_range_operators(self) -> None:
        self.sm.dispatch_transition("parse_range", "==1.0.0")
        self.sm.dispatch_transition("parse_range", "= 1.0.0")
        self.sm.dispatch_transition("parse_range", "!=1.0.0")
        self.sm.dispatch_transition("parse_range", "<2.0.0")
        self.sm.dispatch_transition("parse_range", "<=2.0.0")
        self.sm.dispatch_transition("parse_range", ">1.0.0")
        self.sm.dispatch_transition("parse_range", ">=1.0.0")
        self.sm.dispatch_transition("parse_range", ">= 1.0.0 < 2.0.0")

    def test_real_parse_range_caret(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.2.3")
        self.sm.dispatch_transition("parse_range", "^0.2.3")
        self.sm.dispatch_transition("parse_range", "^0.0.3")
        self.sm.dispatch_transition("parse_range", "^1.x")
        self.sm.dispatch_transition("parse_range", "^0.x")
        self.sm.dispatch_transition("parse_range", "^1.2.x")
        self.sm.dispatch_transition("parse_range", "^0.2.x")
        self.sm.dispatch_transition("parse_range", "^0.0.x")
        self.sm.dispatch_transition("parse_range", "^*")

    def test_real_parse_range_tilde(self) -> None:
        self.sm.dispatch_transition("parse_range", "~1.2.3")
        self.sm.dispatch_transition("parse_range", "~0.2.3")
        self.sm.dispatch_transition("parse_range", "~1.x")
        self.sm.dispatch_transition("parse_range", "~1.2.x")
        self.sm.dispatch_transition("parse_range", "~*")

    def test_real_parse_range_wildcards(self) -> None:
        self.sm.dispatch_transition("parse_range", "*")
        self.sm.dispatch_transition("parse_range", "x")
        self.sm.dispatch_transition("parse_range", "X")
        self.sm.dispatch_transition("parse_range", "1.x")
        self.sm.dispatch_transition("parse_range", "1.*")
        self.sm.dispatch_transition("parse_range", "1.2.x")
        self.sm.dispatch_transition("parse_range", "1.2.*")
        self.sm.dispatch_transition("parse_range", "> 1.x")
        self.sm.dispatch_transition("parse_range", "< 1.x")
        self.sm.dispatch_transition("parse_range", "<= 1.x")
        self.sm.dispatch_transition("parse_range", ">= 1.x")
        self.sm.dispatch_transition("parse_range", "> 1.2.x")
        self.sm.dispatch_transition("parse_range", "< 1.2.x")
        self.sm.dispatch_transition("parse_range", "<= 1.2.x")
        self.sm.dispatch_transition("parse_range", ">= 1.2.x")
        self.sm.dispatch_transition("parse_range", "> *")
        self.sm.dispatch_transition("parse_range", "< *")
        self.sm.dispatch_transition("parse_range", "!= *")
        self.sm.dispatch_transition("parse_range", "!= 1.x")
        self.sm.dispatch_transition("parse_range", "!= 1.2.x")

    def test_real_parse_range_hyphen_and_unions(self) -> None:
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.x")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.3.x")
        self.sm.dispatch_transition("parse_range", "1.0.0 - *")
        self.sm.dispatch_transition("parse_range", "1.0.0 || >=2.0.0")

    def test_real_parse_range_invalid_syntax_raises(self) -> None:
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("   ")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0, 2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 ||")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("|| 1.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 || || 2.0.0")

    def test_real_parse_range_bare_partial_raises(self) -> None:
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.2")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("^0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("~1.2")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">= 1")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.3")

    def test_real_parse_range_malformed_tokens_raises(self) -> None:
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">=")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("> < 1.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">= <= 1.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("- 1.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 -")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">= 1.0.0 - 2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - >= 2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("><1.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("abc")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - invalid")

    def test_real_satisfies_scenarios(self) -> None:
        v = semver_solver.Version(1, 5, 0)
        rng = semver_solver.VersionRange("^1.0.0")
        self.sm.dispatch_transition("satisfies", v, rng, False)
        v2 = semver_solver.Version(2, 0, 0)
        self.sm.dispatch_transition("satisfies", v2, rng, False)

        rng_ne = semver_solver.VersionRange("!=1.0.0")
        self.sm.dispatch_transition("satisfies", v, rng_ne, False)
        rng_gt = semver_solver.VersionRange(">1.0.0")
        self.sm.dispatch_transition("satisfies", v, rng_gt, False)

    def test_real_satisfies_prerelease_rules(self) -> None:
        v_pre = semver_solver.Version(1, 2, 3, ("alpha", "1"))
        rng_normal = semver_solver.VersionRange(">=1.0.0 <2.0.0")
        self.sm.dispatch_transition("satisfies", v_pre, rng_normal, False)

        rng_target = semver_solver.VersionRange(">=1.2.3-alpha.0 <1.2.4")
        self.sm.dispatch_transition("satisfies", v_pre, rng_target, False)

        rng_diff = semver_solver.VersionRange(">=1.2.0-alpha.0")
        self.sm.dispatch_transition("satisfies", v_pre, rng_diff, False)

        rng_bound = semver_solver.VersionRange(">=1.0.0")
        v_pre1 = semver_solver.Version(1, 0, 0, ("alpha",))
        self.sm.dispatch_transition("satisfies", v_pre1, rng_bound, True)

        v_pre2 = semver_solver.Version(1, 1, 0, ("alpha",))
        self.sm.dispatch_transition("satisfies", v_pre2, rng_bound, True)

    # --- Package Repository Tests ---

    def test_real_repository_operations(self) -> None:
        rel1 = semver_solver.PackageRelease("foo", semver_solver.Version(1, 0, 0))
        rel2 = semver_solver.PackageRelease("foo", semver_solver.Version(2, 0, 0))
        self.sm.dispatch_transition("register_package", rel1)
        self.sm.dispatch_transition("register_package", rel2)
        self.sm.dispatch_transition("get_releases", "foo")
        self.sm.dispatch_transition("has_package", "foo")
        self.sm.dispatch_transition("has_package", "bar")
        self.sm.dispatch_transition("all_packages")

    def test_real_repository_missing_package_raises(self) -> None:
        with self.assertRaises(semver_solver.PackageNotFoundError):
            self.packagerepository.get_releases("nonexistent_pkg")

    # --- Dependency Solver Tests ---

    def test_real_solver_empty_roots(self) -> None:
        self.sm.dispatch_transition("resolve", [])

    def test_real_solver_single_package(self) -> None:
        rel = semver_solver.PackageRelease("foo", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel)
        dep = semver_solver.PackageDependency("foo", semver_solver.VersionRange("^1.0.0"))
        self.sm.dispatch_transition("resolve", [dep])

    def test_real_solver_transitive_dependencies(self) -> None:
        rel_b = semver_solver.PackageRelease("bar", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel_b)
        rel_a = semver_solver.PackageRelease(
            "foo",
            semver_solver.Version(3, 0, 0),
            dependencies=(semver_solver.PackageDependency("bar", semver_solver.VersionRange(">=1.0.0")),),
        )
        self.sm.dispatch_transition("register_package", rel_a)
        dep_a = semver_solver.PackageDependency("foo", semver_solver.VersionRange(">=3.0.0"))
        self.sm.dispatch_transition("resolve", [dep_a])

    def test_real_solver_backtracking_resolution(self) -> None:
        # baz 2.0.0 requires bar >= 2.0.0; baz 1.0.0 requires bar <= 1.0.0
        rel_c1 = semver_solver.PackageRelease(
            "baz",
            semver_solver.Version(2, 0, 0),
            dependencies=(semver_solver.PackageDependency("bar", semver_solver.VersionRange(">=2.0.0")),),
        )
        rel_c2 = semver_solver.PackageRelease(
            "baz",
            semver_solver.Version(1, 0, 0),
            dependencies=(semver_solver.PackageDependency("bar", semver_solver.VersionRange("<=1.0.0")),),
        )
        self.sm.dispatch_transition("register_package", rel_c1)
        self.sm.dispatch_transition("register_package", rel_c2)
        rel_b = semver_solver.PackageRelease("bar", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel_b)

        dep_b = semver_solver.PackageDependency("bar", semver_solver.VersionRange("==1.0.0"))
        dep_c = semver_solver.PackageDependency("baz", semver_solver.VersionRange(">=1.0.0"))
        self.sm.dispatch_transition("resolve", [dep_b, dep_c])

    def test_real_solver_backtracking_with_forward_checking_undo(self) -> None:
        rel_alpha2 = semver_solver.PackageRelease(
            "alpha",
            semver_solver.Version(2, 0, 0),
            dependencies=(semver_solver.PackageDependency("beta", semver_solver.VersionRange(">=2.0.0")),),
        )
        rel_alpha1 = semver_solver.PackageRelease(
            "alpha",
            semver_solver.Version(1, 0, 0),
            dependencies=(semver_solver.PackageDependency("beta", semver_solver.VersionRange(">=1.0.0")),),
        )
        rel_beta = semver_solver.PackageRelease("beta", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel_alpha2)
        self.sm.dispatch_transition("register_package", rel_alpha1)
        self.sm.dispatch_transition("register_package", rel_beta)

        dep_alpha = semver_solver.PackageDependency("alpha", semver_solver.VersionRange(">=1.0.0"))
        self.sm.dispatch_transition("resolve", [dep_alpha])

    def test_real_solver_all_candidates_exhaust_raises(self) -> None:
        rel_alpha2 = semver_solver.PackageRelease(
            "pkgX",
            semver_solver.Version(2, 0, 0),
            dependencies=(semver_solver.PackageDependency("pkgY", semver_solver.VersionRange(">=2.0.0")),),
        )
        rel_alpha1 = semver_solver.PackageRelease(
            "pkgX",
            semver_solver.Version(1, 0, 0),
            dependencies=(semver_solver.PackageDependency("pkgY", semver_solver.VersionRange(">=2.0.0")),),
        )
        rel_beta = semver_solver.PackageRelease("pkgY", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel_alpha2)
        self.sm.dispatch_transition("register_package", rel_alpha1)
        self.sm.dispatch_transition("register_package", rel_beta)

        dep_x = semver_solver.PackageDependency("pkgX", semver_solver.VersionRange(">=1.0.0"))
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve([dep_x])

    def test_real_solver_conflict_raises(self) -> None:
        rel_b = semver_solver.PackageRelease("bar", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel_b)
        dep_conflict = semver_solver.PackageDependency("bar", semver_solver.VersionRange(">=5.0.0"))
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve([dep_conflict])

    def test_real_solver_missing_package_conflict_raises(self) -> None:
        dep_missing = semver_solver.PackageDependency("unregistered_pkg", semver_solver.VersionRange("*"))
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve([dep_missing])

    # --- Value and Exception Formatting Tests ---

    def test_real_exceptions_and_records(self) -> None:
        exc1 = semver_solver.SemVerError("base error")
        self.assertIn("base error", str(exc1))
        exc2 = semver_solver.InvalidVersionError("bad ver", "1.2")
        self.assertIn("bad ver", str(exc2))
        exc3 = semver_solver.InvalidRangeError("bad rng", "abc")
        self.assertIn("bad rng", str(exc3))
        exc4 = semver_solver.ResolutionConflictError("conflict", ("pkgA",), "deriv")
        self.assertIn("conflict", str(exc4))
        exc5 = semver_solver.PackageNotFoundError("not found", "pkgA")
        self.assertIn("not found", str(exc5))

        v = semver_solver.Version(1, 0, 0, (), ("build",))
        self.assertEqual(str(v), "1.0.0+build")
        self.assertFalse(v.is_prerelease)


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
        self.__dict__["_services"] = (self.versionengine, self.packagerepository, self.dependencysolver)

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
# LAST_CLEANED: 2026-10-29T02:43:21Z
# LAST_CHANGED: 2026-10-29T02:43:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 878034b0c00e
# COVERAGE_AUDIT: 2026-10-29T02:43:21Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T02:43:21Z
# PRETENSE_QA_AUDIT: 2026-10-29T02:43:21Z
# QA_AUDIT: 2026-10-29T02:43:21Z
# --- END CLEANROOM METADATA ---
