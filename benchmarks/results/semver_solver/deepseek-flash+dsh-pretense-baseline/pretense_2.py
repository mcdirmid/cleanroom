"""Pretense state machine, fake synthesis, and verification for the SemVer dependency solver.

The module models SemVer 2.0.0 version parsing, precedence ordering, range algebra,
repository indexing, and dependency resolution against the contracts in
`low/semver_solver.pyi` and `low/semver_solver_impl.pyi`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.semver_solver.lib.semver_solver import (
    ComparatorOp,
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
from benchmark_2.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# Model Oracles
# ==============================================================================

_VERSION_TEXT = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

_MAJOR_WILDCARD_TEXT = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<wildcard>[*xX])$")
_MINOR_WILDCARD_TEXT = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<wildcard>[*xX])$"
)

_ALL_WILDCARD_TEXT = frozenset({"*", "x", "X"})

_COMPARATOR_TEXTS: Tuple[Tuple[str, ComparatorOp], ...] = (
    ("==", ComparatorOp.EQ),
    ("!=", ComparatorOp.NE),
    ("<=", ComparatorOp.LE),
    (">=", ComparatorOp.GE),
    ("=", ComparatorOp.EQ),
    ("<", ComparatorOp.LT),
    (">", ComparatorOp.GT),
)

_PREFIX_TEXTS = frozenset({"==", "!=", "<=", ">=", "=", "<", ">", "^", "~"})


def _match_version_text(text: str) -> Optional[Version]:
    """Reference oracle parsing SemVer 2.0.0 text into a Version record."""
    match = _VERSION_TEXT.match(text)
    if match is None:
        return None
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    return Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        tuple(prerelease_text.split(".")) if prerelease_text else (),
        tuple(build_text.split(".")) if build_text else (),
    )


def _compare_versions(v1: Version, v2: Version) -> int:
    """Reference oracle implementing SemVer 2.0.0 precedence ordering."""
    if v1.major != v2.major:
        return -1 if v1.major < v2.major else 1
    if v1.minor != v2.minor:
        return -1 if v1.minor < v2.minor else 1
    if v1.patch != v2.patch:
        return -1 if v1.patch < v2.patch else 1
    left = v1.prerelease
    right = v2.prerelease
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for left_segment, right_segment in zip(left, right):
        if left_segment == right_segment:
            continue
        left_numeric = left_segment.isdigit()
        right_numeric = right_segment.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_segment) < int(right_segment) else 1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left_segment < right_segment else 1
    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1


def _sign(value: int) -> int:
    """Normalizes a comparison result to its sign."""
    return (value > 0) - (value < 0)


def _sorted_releases(releases: Sequence[PackageRelease]) -> List[PackageRelease]:
    """Orders releases by descending version precedence."""
    return sorted(
        releases,
        key=cmp_to_key(lambda left, right: _compare_versions(right.version, left.version)),
    )


def _expand_wildcard_text(token: str) -> Optional[List[Tuple[ComparatorOp, Version]]]:
    """Reference oracle expanding wildcard text into numeric bounds."""
    if token in _ALL_WILDCARD_TEXT:
        return []
    major_match = _MAJOR_WILDCARD_TEXT.match(token)
    if major_match is not None:
        major = int(major_match.group("major"))
        return [
            (ComparatorOp.GE, Version(major, 0, 0)),
            (ComparatorOp.LT, Version(major + 1, 0, 0)),
        ]
    minor_match = _MINOR_WILDCARD_TEXT.match(token)
    if minor_match is not None:
        major = int(minor_match.group("major"))
        minor = int(minor_match.group("minor"))
        return [
            (ComparatorOp.GE, Version(major, minor, 0)),
            (ComparatorOp.LT, Version(major, minor + 1, 0)),
        ]
    return None


def _expand_token_text(token: str) -> Optional[List[Tuple[ComparatorOp, Version]]]:
    """Reference oracle expanding one range token into primitive comparators."""
    wildcard = _expand_wildcard_text(token)
    if wildcard is not None:
        return wildcard
    if token.startswith("^"):
        operand = _match_version_text(token[1:])
        if operand is None:
            return None
        if operand.major > 0:
            upper = Version(operand.major + 1, 0, 0)
        elif operand.minor > 0:
            upper = Version(0, operand.minor + 1, 0)
        else:
            upper = Version(0, 0, operand.patch + 1)
        return [(ComparatorOp.GE, operand), (ComparatorOp.LT, upper)]
    if token.startswith("~"):
        operand = _match_version_text(token[1:])
        if operand is None:
            return None
        return [
            (ComparatorOp.GE, operand),
            (ComparatorOp.LT, Version(operand.major, operand.minor + 1, 0)),
        ]
    for prefix, op in _COMPARATOR_TEXTS:
        if token.startswith(prefix):
            operand = _match_version_text(token[len(prefix):])
            if operand is None:
                return None
            return [(op, operand)]
    operand = _match_version_text(token)
    if operand is None:
        return None
    return [(ComparatorOp.EQ, operand)]


def _parse_clause_text(clause_text: str) -> Optional[List[Tuple[ComparatorOp, Version]]]:
    """Reference oracle parsing one whitespace-delimited clause."""
    tokens = clause_text.split()
    if "-" in tokens:
        if len(tokens) != 3:
            return None
        lower = _match_version_text(tokens[0])
        upper = _match_version_text(tokens[2])
        if lower is None or upper is None:
            return None
        return [(ComparatorOp.GE, lower), (ComparatorOp.LE, upper)]
    comparators: List[Tuple[ComparatorOp, Version]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _PREFIX_TEXTS:
            if index + 1 >= len(tokens):
                return None
            token = token + tokens[index + 1]
            index += 2
        else:
            index += 1
        expanded = _expand_token_text(token)
        if expanded is None:
            return None
        comparators.extend(expanded)
    return comparators


def _parse_range_text(text: str) -> Optional[List[List[Tuple[ComparatorOp, Version]]]]:
    """Reference oracle parsing range text into a disjunction of comparator clauses."""
    trimmed = text.strip()
    if not trimmed or "," in trimmed:
        return None
    clauses: List[List[Tuple[ComparatorOp, Version]]] = []
    for raw_clause in trimmed.split("||"):
        clause_text = raw_clause.strip()
        if not clause_text:
            return None
        clause = _parse_clause_text(clause_text)
        if clause is None:
            return None
        clauses.append(clause)
    return clauses


def _matches_comparator_text(
    version: Version, op: ComparatorOp, bound: Version
) -> bool:
    """Reference oracle testing one primitive comparator against a version."""
    order = _compare_versions(version, bound)
    if op is ComparatorOp.EQ:
        return order == 0
    if op is ComparatorOp.NE:
        return order != 0
    if op is ComparatorOp.LT:
        return order < 0
    if op is ComparatorOp.LE:
        return order <= 0
    if op is ComparatorOp.GT:
        return order > 0
    return order >= 0


def _satisfies_text(
    version: Version, range_text: str, include_prerelease: bool = False
) -> bool:
    """Reference oracle evaluating a version against range text."""
    clauses = _parse_range_text(range_text)
    if clauses is None:
        return False
    for clause in clauses:
        if version.is_prerelease and not include_prerelease:
            targets_prerelease = any(
                bound.is_prerelease
                and (bound.major, bound.minor, bound.patch)
                == (version.major, version.minor, version.patch)
                for _, bound in clause
            )
            if not targets_prerelease:
                continue
        if all(
            _matches_comparator_text(version, op, bound) for op, bound in clause
        ):
            return True
    return False


def _reference_resolve(
    packages: Mapping[str, Sequence[PackageRelease]],
    root_dependencies: Sequence[PackageDependency],
) -> Optional[Dict[str, Version]]:
    """Reference oracle solving dependency constraints by depth-first search."""
    constraints: Dict[str, List[VersionRange]] = {}
    for dependency in root_dependencies:
        constraints.setdefault(dependency.name, []).append(
            dependency.range_constraint
        )
    assignment: Dict[str, PackageRelease] = {}

    def backtrack() -> bool:
        unassigned = [name for name in constraints if name not in assignment]
        if not unassigned:
            return True
        candidate_map: Dict[str, List[PackageRelease]] = {}
        for name in unassigned:
            candidate_map[name] = [
                release
                for release in _sorted_releases(packages.get(name, ()))
                if all(
                    _satisfies_text(release.version, constraint.raw_text)
                    for constraint in constraints[name]
                )
            ]
        selected = min(
            unassigned, key=lambda name: (len(candidate_map[name]), name)
        )
        for candidate in candidate_map[selected]:
            assignment[selected] = candidate
            added: List[Tuple[str, VersionRange]] = []
            conflict = False
            for dependency in candidate.dependencies:
                if dependency.name in assignment:
                    if not _satisfies_text(
                        assignment[dependency.name].version,
                        dependency.range_constraint.raw_text,
                    ):
                        conflict = True
                        break
                else:
                    constraints.setdefault(dependency.name, []).append(
                        dependency.range_constraint
                    )
                    added.append((dependency.name, dependency.range_constraint))
            if not conflict and backtrack():
                return True
            for name, constraint in added:
                constraints[name].remove(constraint)
                if not constraints[name]:
                    del constraints[name]
            del assignment[selected]
        return False

    if backtrack():
        return {name: release.version for name, release in assignment.items()}
    return None


# ==============================================================================
# Property Fuzzing Strategies
# ==============================================================================

_PACKAGE_NAMES = ("alpha", "beta", "gamma")

_VERSION_STRATEGY: st.SearchStrategy[Version] = st.builds(
    Version,
    st.integers(0, 20),
    st.integers(0, 20),
    st.integers(0, 20),
    st.one_of(
        st.just(()),
        st.lists(
            st.sampled_from(["alpha", "beta", "rc", "1", "2"]),
            min_size=1,
            max_size=3,
        ).map(tuple),
    ),
    st.one_of(
        st.just(()),
        st.lists(
            st.sampled_from(["build", "001"]),
            min_size=1,
            max_size=2,
        ).map(tuple),
    ),
)

_VERSION_TEXT_STRATEGY: st.SearchStrategy[str] = st.builds(
    lambda major, minor, patch: f"{major}.{minor}.{patch}",
    st.integers(0, 20),
    st.integers(0, 20),
    st.integers(0, 20),
)

_RANGE_TEXT_POOL = (
    "*",
    "x",
    "X",
    "1.x",
    "1.*",
    "1.2.x",
    "1.2.*",
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
    "1.0.0 - 2.0.0",
    ">=1.0.0 <2.0.0",
    "1.0.0 || 2.0.0",
    ">=1.0.0-alpha",
    "1.0.0-alpha.1",
    ">= 1.0.0",
    "1.2.3+build.5",
)

_RANGE_TEXT_STRATEGY: st.SearchStrategy[str] = st.sampled_from(_RANGE_TEXT_POOL)
_RANGE_CONSTRAINT_STRATEGY: st.SearchStrategy[VersionRange] = (
    _RANGE_TEXT_STRATEGY.map(VersionRange)
)
_PACKAGE_NAME_STRATEGY: st.SearchStrategy[str] = st.sampled_from(_PACKAGE_NAMES)
_RELEASE_STRATEGY: st.SearchStrategy[PackageRelease] = st.builds(
    PackageRelease, _PACKAGE_NAME_STRATEGY, _VERSION_STRATEGY
)
_ROOT_DEPENDENCIES_STRATEGY: st.SearchStrategy[List[PackageDependency]] = st.lists(
    st.builds(
        PackageDependency,
        st.sampled_from(["alpha", "beta"]),
        _RANGE_CONSTRAINT_STRATEGY,
    ),
    max_size=2,
)


# ==============================================================================
# 1. Model State & Transitions
# ==============================================================================

@dataclass
class SemverSolverState:
    """Model state tracking registered package releases."""

    ready: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """State machine modeling the version engine, repository, and dependency solver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(
        self, ctx: TransitionContext[VersionEngine, [str], Version]
    ) -> None:
        ctx.requires(lambda check: check(self.state.ready, "model state ready"))
        ctx.arguments(text=Domain(strategy=lambda: _VERSION_TEXT_STRATEGY))
        ctx.returns(self._expected_parse_version)
        ctx.ensures(self._check_parse_version)
        ctx.update(lambda res, text: None)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self, ctx: TransitionContext[VersionEngine, [Version, Version], int]
    ) -> None:
        ctx.requires(lambda check: check(self.state.ready, "model state ready"))
        ctx.arguments(
                    v1=Domain(strategy=lambda: _VERSION_STRATEGY),
                    v2=Domain(strategy=lambda: _VERSION_STRATEGY),
                )
        ctx.returns(self._expected_compare)
        ctx.ensures(self._check_compare)
        ctx.update(lambda res, v1, v2: None)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self, ctx: TransitionContext[VersionEngine, [str], VersionRange]
    ) -> None:
        ctx.requires(lambda check: check(self.state.ready, "model state ready"))
        ctx.arguments(text=Domain(strategy=lambda: _RANGE_TEXT_STRATEGY))
        ctx.returns(self._expected_parse_range)
        ctx.ensures(self._check_parse_range)
        ctx.update(lambda res, text: None)

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[
            VersionEngine, [Version, VersionRange, bool], bool
        ],
    ) -> None:
        ctx.requires(lambda check: check(self.state.ready, "model state ready"))
        ctx.arguments(
                    version=Domain(strategy=lambda: _VERSION_STRATEGY),
                    range_constraint=Domain(strategy=lambda: _RANGE_CONSTRAINT_STRATEGY),
                    include_prerelease=Domain(strategy=lambda: st.booleans()),
                )
        ctx.returns(self._expected_satisfies)
        ctx.ensures(self._check_satisfies)
        ctx.update(lambda res, version, range_constraint, include_prerelease: None)

    @transition(PackageRepository.register_package)
    def register_package(
        self, ctx: TransitionContext[PackageRepository, [PackageRelease], None]
    ) -> None:
        ctx.requires(lambda check: check(self.state.ready, "model state ready"))
        ctx.arguments(release=Domain(strategy=lambda: _RELEASE_STRATEGY))
        ctx.returns(lambda release: None)
        ctx.ensures(self._check_register)
        ctx.update(self._record_release)

    @transition(PackageRepository.get_releases)
    def get_releases(
        self, ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]]
    ) -> None:
        ctx.requires(lambda check: check(self.state.ready, "model state ready"))
        ctx.arguments(name=Domain(strategy=lambda: _PACKAGE_NAME_STRATEGY))
        ctx.returns(self._expected_releases)
        ctx.ensures(self._check_releases)
        ctx.update(lambda res, name: None)

    @transition(PackageRepository.has_package)
    def has_package(
        self, ctx: TransitionContext[PackageRepository, [str], bool]
    ) -> None:
        ctx.requires(lambda check: check(self.state.ready, "model state ready"))
        ctx.arguments(name=Domain(strategy=lambda: _PACKAGE_NAME_STRATEGY))
        ctx.returns(lambda name: Value(name in self.state.packages))
        ctx.ensures(self._check_has_package)
        ctx.update(lambda res, name: None)

    @transition(PackageRepository.all_packages)
    def all_packages(
        self, ctx: TransitionContext[PackageRepository, [], Set[str]]
    ) -> None:
        ctx.requires(lambda check: check(self.state.ready, "model state ready"))
        ctx.arguments()
        ctx.returns(lambda: Value(set(self.state.packages)))
        ctx.ensures(self._check_all_packages)
        ctx.update(lambda res: None)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[
            DependencySolver, [List[PackageDependency]], ResolutionOutcome
        ],
    ) -> None:
        ctx.requires(lambda check: check(self.state.ready, "model state ready"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: _ROOT_DEPENDENCIES_STRATEGY))
        ctx.returns(self._expected_resolve)
        ctx.ensures(self._check_resolve)
        ctx.update(lambda res, root_dependencies: None)

    # -- Expected outcomes synthesized by the model (fake behavior) ------------

    def _expected_parse_version(self, text: str) -> Outcome[Version]:
        version = _match_version_text(text)
        if version is None:
            return Raised(
                InvalidVersionError(f"Invalid semantic version: {text}", text)
            )
        return Value(version)

    def _expected_compare(self, v1: Version, v2: Version) -> Outcome[int]:
        return Value(_compare_versions(v1, v2))

    def _expected_parse_range(self, text: str) -> Outcome[VersionRange]:
        if _parse_range_text(text) is None:
            return Raised(InvalidRangeError(f"Invalid version range: {text}", text))
        return Value(VersionRange(text.strip()))

    def _expected_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Outcome[bool]:
        return Value(
            _satisfies_text(
                version, range_constraint.raw_text, include_prerelease
            )
        )

    def _expected_releases(self, name: str) -> Outcome[List[PackageRelease]]:
        if name not in self.state.packages:
            return Raised(
                PackageNotFoundError(f"Package not found: {name}", name)
            )
        return Value(_sorted_releases(self.state.packages[name]))

    def _expected_resolve(
        self, root_dependencies: List[PackageDependency]
    ) -> Outcome[ResolutionOutcome]:
        selected = _reference_resolve(self.state.packages, root_dependencies)
        if selected is None:
            involved = tuple(
                sorted({dependency.name for dependency in root_dependencies})
            )
            return Raised(
                ResolutionConflictError(
                    "Unable to resolve dependencies",
                    involved,
                    "constraints unsatisfiable",
                )
            )
        steps = tuple(
            f"Assign '{name}' to {version}" for name, version in selected.items()
        )
        return Value(ResolutionOutcome(selected, steps))

    # -- Postcondition checks verified against real singletons ----------------

    def _check_parse_version(
        self, res: Version, target: Any, check: Any, text: str
    ) -> None:
        expected = _match_version_text(text)
        check(expected is not None, "valid SemVer text")
        check.equal(res, expected)
        check.equal(res.format(), text)

    def _check_compare(
        self, res: int, target: Any, check: Any, v1: Version, v2: Version
    ) -> None:
        check.equal(_sign(res), _sign(_compare_versions(v1, v2)))
        check.equal(_sign(res), -_sign(_compare_versions(v2, v1)))

    def _check_parse_range(
        self, res: VersionRange, target: Any, check: Any, text: str
    ) -> None:
        expected = text.strip()
        check.equal(res.raw_text, expected)
        check.equal(str(res), expected)

    def _check_satisfies(
        self,
        res: bool,
        target: Any,
        check: Any,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> None:
        check.equal(
            res,
            _satisfies_text(
                version, range_constraint.raw_text, include_prerelease
            ),
        )

    def _check_register(
        self, res: None, target: Any, check: Any, release: PackageRelease
    ) -> None:
        check(target.has_package(release.name), "package registered")
        releases = target.get_releases(release.name)
        check(any(entry == release for entry in releases), "release present")
        for earlier, later in zip(releases, releases[1:]):
            check(
                _compare_versions(earlier.version, later.version) >= 0,
                "releases ordered by descending precedence",
            )

    def _check_releases(
        self, res: List[PackageRelease], target: Any, check: Any, name: str
    ) -> None:
        check.equal(list(res), _sorted_releases(self.state.packages[name]))

    def _check_has_package(
        self, res: bool, target: Any, check: Any, name: str
    ) -> None:
        check.equal(res, name in self.state.packages)

    def _check_all_packages(
        self, res: Set[str], target: Any, check: Any
    ) -> None:
        check.equal(res, set(self.state.packages))

    def _check_resolve(
        self,
        res: ResolutionOutcome,
        target: Any,
        check: Any,
        root_dependencies: List[PackageDependency],
    ) -> None:
        selected = dict(res.selected_versions)
        for dependency in root_dependencies:
            check(dependency.name in selected, "root dependency selected")
            if dependency.name in selected:
                check(
                    _satisfies_text(
                        selected[dependency.name],
                        dependency.range_constraint.raw_text,
                    ),
                    "root constraint satisfied",
                )
        for name, version in selected.items():
            releases = self.state.packages.get(name, [])
            matching = [entry for entry in releases if entry.version == version]
            check(len(matching) >= 1, "selected release exists in repository")
            for dependency in matching[0].dependencies:
                check(dependency.name in selected, "transitive dependency selected")
                if dependency.name in selected:
                    check(
                        _satisfies_text(
                            selected[dependency.name],
                            dependency.range_constraint.raw_text,
                        ),
                        "transitive constraint satisfied",
                    )
        if root_dependencies:
            check(len(res.derivation_steps) > 0, "derivation steps recorded")

    def _record_release(self, res: Any, release: PackageRelease) -> None:
        self.state.packages.setdefault(release.name, []).append(release)


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

proto = SemverSolverStateMachine()


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake services sharing one model state instance."""
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
    """Verifies that synthesized fakes conform to the modeled specification."""

    def setUp(self) -> None:
        self.state = SemverSolverState()
        (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
        ) = make_semver_solver_fakes(self.state)

    def test_fake_parse_version(self) -> None:
        parsed = self.versionengine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual(parsed, Version(1, 2, 3, ("alpha", "1"), ("build", "5")))
        self.assertTrue(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "1.2.3-alpha.1+build.5")

    def test_fake_parse_version_invalid(self) -> None:
        with self.assertRaises(InvalidVersionError) as raised:
            self.versionengine.parse_version("01.2.3")
        self.assertEqual(raised.exception.raw_text, "01.2.3")

    def test_fake_compare_precedence(self) -> None:
        self.assertLess(
            self.versionengine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)
            ),
            0,
        )
        self.assertGreater(
            self.versionengine.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)),
            0,
        )
        self.assertEqual(
            self.versionengine.compare_precedence(
                Version(1, 0, 0, ("a",)), Version(1, 0, 0, ("a",))
            ),
            0,
        )

    def test_fake_parse_range(self) -> None:
        parsed = self.versionengine.parse_range("  >= 1.0.0  ")
        self.assertEqual(parsed.raw_text, ">= 1.0.0")
        self.assertEqual(str(parsed), ">= 1.0.0")

    def test_fake_parse_range_invalid(self) -> None:
        with self.assertRaises(InvalidRangeError) as raised:
            self.versionengine.parse_range("1.2")
        self.assertEqual(raised.exception.raw_range, "1.2")

    def test_fake_satisfies(self) -> None:
        range_constraint = self.versionengine.parse_range("^1.2.3")
        self.assertTrue(
            self.versionengine.satisfies(Version(1, 5, 0), range_constraint)
        )
        self.assertFalse(
            self.versionengine.satisfies(Version(2, 0, 0), range_constraint)
        )

    def test_fake_register_and_query(self) -> None:
        self.packagerepository.register_package(
            PackageRelease("alpha", Version(1, 0, 0))
        )
        self.packagerepository.register_package(
            PackageRelease("alpha", Version(2, 0, 0))
        )
        releases = self.packagerepository.get_releases("alpha")
        self.assertEqual([entry.version for entry in releases], [
            Version(2, 0, 0),
            Version(1, 0, 0),
        ])
        self.assertTrue(self.packagerepository.has_package("alpha"))
        self.assertEqual(self.packagerepository.all_packages(), {"alpha"})

    def test_fake_get_releases_missing(self) -> None:
        with self.assertRaises(PackageNotFoundError) as raised:
            self.packagerepository.get_releases("missing")
        self.assertEqual(raised.exception.package_name, "missing")

    def test_fake_resolve(self) -> None:
        self.packagerepository.register_package(
            PackageRelease("alpha", Version(1, 0, 0))
        )
        self.packagerepository.register_package(
            PackageRelease("alpha", Version(2, 0, 0))
        )
        outcome = self.dependencysolver.resolve(
            [PackageDependency("alpha", self.versionengine.parse_range("^1.0.0"))]
        )
        self.assertEqual(dict(outcome.selected_versions), {"alpha": Version(1, 0, 0)})

    def test_fake_resolve_conflict(self) -> None:
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(
                [PackageDependency("alpha", self.versionengine.parse_range("^1.0.0"))]
            )


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies the concrete implementation by dispatching state machine transitions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.sm = SemverSolverStateMachine(
            singletons={
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _register(self, release: PackageRelease) -> None:
        self.sm.dispatch_transition("register_package", release)

    def _version(self, text: str) -> Version:
        version = _match_version_text(text)
        assert version is not None
        return version

    def _range(self, text: str) -> VersionRange:
        return VersionRange(text)

    def test_parse_version_valid(self) -> None:
        for text in (
            "0.0.0",
            "1.2.3",
            "10.20.30",
            "1.2.3-alpha.1+build.5",
            "1.0.0+build.001",
        ):
            self.sm.dispatch_transition("parse_version", text)

    def test_parse_version_rejects_leading_zero(self) -> None:
        for text in ("01.2.3", "1.02.3", "1.2.03", "1.2.3-01"):
            self.sm.dispatch_transition("parse_version", text)

    def test_parse_version_rejects_malformed(self) -> None:
        for text in ("", "1.2", "1.2.3.4", "v1.2.3", "1.2.3-", "1.2.3+"):
            self.sm.dispatch_transition("parse_version", text)

    def test_compare_precedence_numeric(self) -> None:
        for left, right in (
            ("1.0.0", "2.0.0"),
            ("2.0.0", "1.0.0"),
            ("1.0.0", "1.0.0"),
            ("1.0.0", "1.1.0"),
            ("1.1.0", "1.0.1"),
            ("1.0.1", "1.0.0"),
        ):
            self.sm.dispatch_transition(
                "compare_precedence", self._version(left), self._version(right)
            )

    def test_compare_precedence_prerelease(self) -> None:
        for left, right in (
            ("1.0.0-alpha", "1.0.0"),
            ("1.0.0", "1.0.0-alpha"),
            ("1.0.0-alpha", "1.0.0-beta"),
            ("1.0.0-1", "1.0.0-alpha"),
            ("1.0.0-alpha", "1.0.0-alpha.1"),
            ("1.0.0-alpha.2", "1.0.0-alpha.1"),
            ("1.0.0-rc.1", "1.0.0-rc.1"),
        ):
            self.sm.dispatch_transition(
                "compare_precedence", self._version(left), self._version(right)
            )

    def test_compare_precedence_ignores_build(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            self._version("1.0.0+build.1"),
            self._version("1.0.0+build.2"),
        )

    def test_parse_range_comparators(self) -> None:
        for text in (
            "==1.2.3",
            "=1.2.3",
            "!=1.2.3",
            "<2.0.0",
            "<=2.0.0",
            ">1.0.0",
            ">=1.0.0",
            "1.2.3",
            ">= 1.0.0",
        ):
            self.sm.dispatch_transition("parse_range", text)

    def test_parse_range_caret(self) -> None:
        for text in ("^1.2.3", "^0.2.3", "^0.0.3"):
            self.sm.dispatch_transition("parse_range", text)

    def test_parse_range_tilde(self) -> None:
        self.sm.dispatch_transition("parse_range", "~1.2.3")

    def test_parse_range_wildcards(self) -> None:
        for text in ("*", "x", "X", "1.x", "1.*", "1.2.x", "1.2.*", "1.2.X"):
            self.sm.dispatch_transition("parse_range", text)

    def test_parse_range_hyphen_and_union(self) -> None:
        for text in (
            "1.0.0 - 2.0.0",
            ">=1.0.0 <2.0.0",
            "1.0.0 || 2.0.0",
            " ^1.0.0 || ~2.0.0 ",
        ):
            self.sm.dispatch_transition("parse_range", text)

    def test_parse_range_rejects_invalid(self) -> None:
        for text in (
            "",
            "   ",
            "1",
            "1.2",
            "^0.0",
            "1.2 - 2.3",
            ">=1.0.0,<2.0.0",
            "1.0.0 || ",
            ">= ",
            "1.0.0 - 2.0.0 - 3.0.0",
            "^",
            "~",
            "~0.0",
            "^bad",
            "1.2.3 - 2.0",
            "hello",
            ">1.x",
        ):
            self.sm.dispatch_transition("parse_range", text)

    def test_satisfies_comparators(self) -> None:
        for version, text in (
            ("1.2.3", "==1.2.3"),
            ("1.2.3", "=1.2.3"),
            ("1.2.3", "!=1.2.4"),
            ("1.0.0", "<2.0.0"),
            ("2.0.0", "<=2.0.0"),
            ("2.0.1", ">1.0.0"),
            ("1.0.0", ">=1.0.0"),
            ("1.2.3", "1.2.3"),
        ):
            self.sm.dispatch_transition(
                "satisfies", self._version(version), self._range(text), False
            )

    def test_satisfies_ranges(self) -> None:
        for version, text in (
            ("1.5.0", "^1.2.3"),
            ("2.0.0", "^1.2.3"),
            ("1.2.9", "~1.2.3"),
            ("1.3.0", "~1.2.3"),
            ("1.9.9", "1.x"),
            ("1.2.9", "1.2.x"),
            ("0.9.0", "*"),
            ("1.5.0", "1.0.0 - 2.0.0"),
            ("3.0.0", "1.0.0 - 2.0.0"),
        ):
            self.sm.dispatch_transition(
                "satisfies", self._version(version), self._range(text), False
            )

    def test_satisfies_prerelease_filtering(self) -> None:
        for version, text, include_prerelease in (
            ("1.0.0-rc.1", ">=1.0.0", False),
            ("1.0.0-rc.1", ">=1.0.0-0", False),
            ("1.0.0-rc.1", "1.0.0-rc.1", False),
            ("1.2.0-rc.1", ">=1.0.0-0", False),
            ("1.0.0-rc.1", ">=1.0.0", True),
            ("1.0.0-rc.1", ">=0.9.0", True),
        ):
            self.sm.dispatch_transition(
                "satisfies",
                self._version(version),
                self._range(text),
                include_prerelease,
            )

    def test_repository_register_and_query(self) -> None:
        self._register(PackageRelease("alpha", self._version("1.0.0")))
        self._register(PackageRelease("alpha", self._version("2.0.0")))
        self._register(PackageRelease("alpha", self._version("1.5.0")))
        self._register(PackageRelease("beta", self._version("0.1.0")))
        self.sm.dispatch_transition("get_releases", "alpha")
        self.sm.dispatch_transition("has_package", "alpha")
        self.sm.dispatch_transition("has_package", "gamma")
        self.sm.dispatch_transition("all_packages")

    def test_repository_get_releases_missing(self) -> None:
        self.sm.dispatch_transition("get_releases", "missing")

    def test_resolve_empty_roots(self) -> None:
        self.sm.dispatch_transition("resolve", [])

    def test_resolve_direct_success(self) -> None:
        self._register(PackageRelease("alpha", self._version("1.0.0")))
        self._register(PackageRelease("alpha", self._version("1.5.0")))
        self._register(PackageRelease("alpha", self._version("2.0.0")))
        self.sm.dispatch_transition(
            "resolve", [PackageDependency("alpha", self._range("^1.0.0"))]
        )

    def test_resolve_transitive_success(self) -> None:
        self._register(PackageRelease("beta", self._version("1.0.0")))
        self._register(PackageRelease("beta", self._version("1.5.0")))
        self._register(
            PackageRelease(
                "alpha",
                self._version("1.0.0"),
                (PackageDependency("beta", self._range("^1.0.0")),),
            )
        )
        self.sm.dispatch_transition(
            "resolve", [PackageDependency("alpha", self._range("^1.0.0"))]
        )

    def test_resolve_unregistered_package(self) -> None:
        self.sm.dispatch_transition(
            "resolve", [PackageDependency("missing", self._range("*"))]
        )

    def test_resolve_unsatisfiable_range(self) -> None:
        self._register(PackageRelease("alpha", self._version("1.0.0")))
        self.sm.dispatch_transition(
            "resolve", [PackageDependency("alpha", self._range("^2.0.0"))]
        )

    def test_resolve_backtracking(self) -> None:
        self._register(PackageRelease("beta", self._version("1.0.0")))
        self._register(
            PackageRelease(
                "alpha",
                self._version("1.0.0"),
                (PackageDependency("beta", self._range("^1.0.0")),),
            )
        )
        self._register(
            PackageRelease(
                "alpha",
                self._version("2.0.0"),
                (PackageDependency("beta", self._range("^2.0.0")),),
            )
        )
        self.sm.dispatch_transition(
            "resolve", [PackageDependency("alpha", self._range("*"))]
        )

    def test_resolve_appended_constraint_conflict(self) -> None:
        self._register(PackageRelease("delta", self._version("1.0.0")))
        self._register(
            PackageRelease(
                "alpha",
                self._version("1.0.0"),
                (PackageDependency("delta", self._range("^2.0.0")),),
            )
        )
        self.sm.dispatch_transition(
            "resolve",
            [
                PackageDependency("alpha", self._range("^1.0.0")),
                PackageDependency("delta", self._range("^1.0.0")),
            ],
        )

    def test_resolve_assigned_dependency_conflict(self) -> None:
        self._register(PackageRelease("alpha", self._version("1.0.0")))
        self._register(
            PackageRelease(
                "beta",
                self._version("1.0.0"),
                (PackageDependency("alpha", self._range("^2.0.0")),),
            )
        )
        self.sm.dispatch_transition(
            "resolve",
            [
                PackageDependency("alpha", self._range("^1.0.0")),
                PackageDependency("beta", self._range("^1.0.0")),
            ],
        )


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing the constituent services for property fuzzing."""

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
        self.__dict__["_services"] = (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
        )

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> SemverSolverSUT:
    """Builds a freshly initialized system-tier aggregate SUT."""
    return SemverSolverSUT()


SemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverSolverState,
    name="SemverSolverFuzzTest",
)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T04:59:56Z
# LAST_CHANGED: 2026-10-29T04:59:56Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 84c4ce5b67d9
# COVERAGE_AUDIT: 2026-10-29T04:59:56Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T04:59:56Z
# PRETENSE_QA_AUDIT: 2026-10-29T04:59:56Z
# QA_AUDIT: 2026-10-29T04:59:56Z
# --- END CLEANROOM METADATA ---
