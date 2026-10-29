"""Pretense model, synthesized fakes, and property tests for the SemVer 2.0 solver.

Specification mapping (``low/semver_solver.pyi`` and ``low/semver_solver_impl.pyi``):
- ``VersionEngine`` parses SemVer 2.0.0 strings, compares precedence, parses ranges,
  and evaluates range satisfaction.
- ``PackageRepository`` stores releases per package name in descending precedence order.
- ``DependencySolver`` resolves root dependencies into a mutually compatible assignment,
  raising ``ResolutionConflictError`` for unregistered or unsatisfiable requirements.

The module is organized into the five canonical Pretense sections: model state and
transitions, fake synthesis, fake unit tests, real implementation tests, and bounded
Hypothesis property fuzzing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import cmp_to_key
import re
import unittest
from typing import Any, Callable, Collection, Dict, List, Optional, Set, Tuple

from hypothesis import strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import Raised
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_3.parts.semver_solver.lib.semver_solver import (
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
from benchmark_3.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# Reference Oracle Helpers (module-level oracles, never target services)
# ==============================================================================

_NAME_POOL: Tuple[str, ...] = ("alpha", "beta", "gamma")

_EMPTY_IDENTIFIERS: Tuple[str, ...] = ()
_PRERELEASE_SAMPLES: Tuple[Tuple[str, ...], ...] = (
    (),
    ("alpha",),
    ("beta", "2"),
    ("1",),
    ("alpha", "1"),
    ("rc", "2"),
)
_BUILD_SAMPLES: Tuple[Tuple[str, ...], ...] = (
    (),
    ("build",),
    ("ci", "42"),
)

_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z"
)

_OPERATOR_PATTERN = re.compile(r"(>=|<=|==|!=|>|<|=|\^|~)\s+")

_INVALID_VERSION_TEXTS: Tuple[str, ...] = (
    "",
    "1",
    "1.2",
    "01.2.3",
    "1.02.3",
    "1.2.03",
    "1.2.3-",
    "1.2.3-alpha..1",
    "1.2.3.4",
    "1.2.3+build..5",
    "1.2.3+",
    "v1.2.3",
    " 1.2.3",
    "1.2.3+build.4.5 ",
)

_INVALID_RANGE_TEXTS: Tuple[str, ...] = (
    "",
    "   ",
    "1",
    "1.2",
    "^0.0",
    "~1.2",
    "1.2 - 2.3",
    "1.2.3, <2.0.0",
    ">=1.0.0 ||",
    "|| >=1.0.0",
    "abc",
    ">=",
    "^",
    "~",
    "!=",
    ">>1.0.0",
    "1.0.0>=",
    "=<1.0.0",
    ">=1.0.0<2.0.0",
    ">=1.2.3-",
    ">=1.2.3-alpha..1",
    ">=1.2.3.4",
    ">=1.2.a",
    ">=1.x.3",
    ">=1.2.3+build..5",
    ">=1.2.3+",
    ">=1.2.3+build+extra",
    "==1.2.3+build.5+extra",
    ">=1.2.x-alpha",
    ">=1.2.x+build.5",
    "1.2.*-rc.1",
    ">=a.x",
    "~a.1.x",
    "^a.*",
    ">=1.0.0 - 2.0.0",
    "1.0.0 - 2.0.0 - 3.0.0",
)


def _is_valid_version_text(text: str) -> bool:
    """Reports whether text conforms to the SemVer 2.0.0 grammar."""
    return _SEMVER_PATTERN.match(text) is not None


def _reference_parse_version(text: str) -> Version:
    """Reference SemVer 2.0.0 parser used as an oracle, independent of the target engine."""
    match = _SEMVER_PATTERN.match(text)
    if match is None:
        raise InvalidVersionError(f"invalid semantic version: {text}", text)
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else _EMPTY_IDENTIFIERS
    build = tuple(build_text.split(".")) if build_text else _EMPTY_IDENTIFIERS
    return Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
        build,
    )


def _make_version(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...],
    build: Tuple[str, ...],
) -> Version:
    """Builds a Version record from strategy-drawn components."""
    return Version(major, minor, patch, prerelease, build)


def _format_version(version: Version) -> str:
    """Formats a Version record canonically without depending on the target engine."""
    text = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        text += "-" + ".".join(version.prerelease)
    if version.build:
        text += "+" + ".".join(version.build)
    return text


def _precedence(v1: Version, v2: Version) -> int:
    """Reference SemVer 2.0.0 precedence comparison oracle (build metadata excluded)."""
    if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
        first = (v1.major, v1.minor, v1.patch)
        second = (v2.major, v2.minor, v2.patch)
        return -1 if first < second else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for left, right in zip(v1.prerelease, v2.prerelease):
        if left == right:
            continue
        left_numeric = left.isdigit()
        right_numeric = right.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left) < int(right) else 1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left < right else 1
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


def _caret_upper(version: Version) -> Version:
    """Computes the exclusive upper boundary of a caret range."""
    if version.major > 0:
        return Version(version.major + 1, 0, 0)
    if version.minor > 0:
        return Version(0, version.minor + 1, 0)
    return Version(0, 0, version.patch + 1)


def _wildcard_bounds(token: str) -> Optional[Tuple[Tuple[str, Version], ...]]:
    """Expands wildcard tokens (``*``, ``1.x``, ``1.2.*``) into paired inequalities."""
    if token in ("*", "x", "X"):
        return ()
    parts = token.split(".")
    if len(parts) < 2 or parts[-1] not in ("x", "X", "*"):
        return None
    prefix = parts[:-1]
    if not prefix or not all(part.isdigit() for part in prefix):
        return None
    numbers = [int(part) for part in prefix]
    if len(numbers) == 1:
        return (
            (">=", Version(numbers[0], 0, 0)),
            ("<", Version(numbers[0] + 1, 0, 0)),
        )
    if len(numbers) == 2:
        return (
            (">=", Version(numbers[0], numbers[1], 0)),
            ("<", Version(numbers[0], numbers[1] + 1, 0)),
        )
    return None


def _compile_hyphen_range(
    lower_text: str,
    upper_text: str,
) -> Tuple[Tuple[str, Version], ...]:
    """Compiles a hyphen range whose endpoints may carry wildcards."""
    comparators: List[Tuple[str, Version]] = []
    lower_wildcard = _wildcard_bounds(lower_text)
    if lower_wildcard is None:
        comparators.append((">=", _reference_parse_version(lower_text)))
    elif lower_wildcard:
        comparators.append((">=", lower_wildcard[0][1]))
    upper_wildcard = _wildcard_bounds(upper_text)
    if upper_wildcard is None:
        comparators.append(("<=", _reference_parse_version(upper_text)))
    elif upper_wildcard:
        comparators.append(("<", upper_wildcard[1][1]))
    return tuple(comparators)


def _compile_range_clause(clause: str) -> Tuple[Tuple[str, Version], ...]:
    """Compiles one union-free range clause into comparator tuples."""
    normalized = _OPERATOR_PATTERN.sub(r"\1", clause.strip())
    if " - " in normalized:
        lower_text, upper_text = normalized.split(" - ", 1)
        return _compile_hyphen_range(lower_text.strip(), upper_text.strip())
    comparators: List[Tuple[str, Version]] = []
    for token in normalized.split():
        wildcard = _wildcard_bounds(token)
        if wildcard is not None:
            comparators.extend(wildcard)
            continue
        op = "=="
        for candidate in (">=", "<=", "==", "!=", ">", "<", "=", "^", "~"):
            if token.startswith(candidate):
                op = candidate
                token = token[len(candidate):]
                break
        prefixed_wildcard = _wildcard_bounds(token)
        if prefixed_wildcard is not None:
            # Prefix operators (caret/tilde) accept wildcard operands.
            if not prefixed_wildcard:
                if op in ("==", "=", "^", "~"):
                    continue
                comparators.append((op, Version(0, 0, 0)))
                continue
            lower = prefixed_wildcard[0][1]
            if op in ("==", "=", "~"):
                comparators.extend(prefixed_wildcard)
            elif op == "^":
                comparators.append((">=", lower))
                comparators.append(("<", _caret_upper(lower)))
            else:
                comparators.append((op, lower))
            continue
        boundary = _reference_parse_version(token)
        if op == "=":
            op = "=="
        if op == "^":
            comparators.append((">=", boundary))
            comparators.append(("<", _caret_upper(boundary)))
        elif op == "~":
            comparators.append((">=", boundary))
            comparators.append(("<", Version(boundary.major, boundary.minor + 1, 0)))
        else:
            comparators.append((op, boundary))
    return tuple(comparators)


def _compile_range_clauses(raw_text: str) -> Tuple[Tuple[Tuple[str, Version], ...], ...]:
    """Compiles a range expression into disjunctive normal form comparator sets."""
    return tuple(
        _compile_range_clause(clause)
        for clause in raw_text.strip().split("||")
    )


def _is_valid_range_text(text: str) -> bool:
    """Reports whether text is an acceptable range expression under the contracts."""
    stripped = text.strip()
    if not stripped or "," in stripped:
        return False
    for clause in stripped.split("||"):
        if not clause.strip():
            return False
        try:
            _compile_range_clause(clause)
        except (InvalidVersionError, ValueError, IndexError):
            return False
    return True


def _evaluate_comparator(version: Version, op: str, boundary: Version) -> bool:
    """Evaluates a single comparator against a candidate version."""
    comparison = _precedence(version, boundary)
    if op == "==":
        return comparison == 0
    if op == "!=":
        return comparison != 0
    if op == "<":
        return comparison < 0
    if op == "<=":
        return comparison <= 0
    if op == ">":
        return comparison > 0
    if op == ">=":
        return comparison >= 0
    return True


def _reference_satisfies(version: Version, raw_text: str, include_prerelease: bool) -> bool:
    """Reference range satisfaction oracle over the documented range grammar."""
    clauses = _compile_range_clauses(raw_text)
    if version.prerelease and not include_prerelease:
        targets_prerelease = any(
            boundary.prerelease
            and (boundary.major, boundary.minor, boundary.patch)
            == (version.major, version.minor, version.patch)
            for clause in clauses
            for _, boundary in clause
        )
        if not targets_prerelease:
            return False
    return any(
        all(_evaluate_comparator(version, op, boundary) for op, boundary in clause)
        for clause in clauses
    )


def _include_prerelease_flag(value: Any) -> bool:
    """Normalizes an omitted optional include_prerelease argument to False."""
    return value if isinstance(value, bool) else False


def _sign(value: int) -> int:
    """Normalizes a comparison result to -1, 0, or 1."""
    return (value > 0) - (value < 0)


def _is_dependency_collection(value: Any) -> bool:
    """Reports whether value is a collection of PackageDependency records."""
    if not isinstance(value, (list, tuple, set, frozenset)):
        return False
    return all(isinstance(item, PackageDependency) for item in value)


def _model_constraints(
    root_dependencies: Collection[PackageDependency],
) -> Dict[str, List[VersionRange]]:
    """Groups root dependency range constraints by package name."""
    constraints: Dict[str, List[VersionRange]] = {}
    for dependency in root_dependencies:
        constraints.setdefault(dependency.name, []).append(dependency.range_constraint)
    return constraints


def _model_viable_releases(
    state: "SemverSolverState",
    name: str,
    constraints: List[VersionRange],
) -> List[PackageRelease]:
    """Selects releases of a package that satisfy every accumulated constraint."""
    return [
        release
        for release in state.packages.get(name, [])
        if all(
            _reference_satisfies(release.version, constraint.raw_text, False)
            for constraint in constraints
        )
    ]


def _model_resolution_kind(
    state: "SemverSolverState",
    root_dependencies: Any,
) -> str:
    """Classifies a resolve call as success, unregistered, or unsatisfiable."""
    if not _is_dependency_collection(root_dependencies):
        return "invalid"
    constraints = _model_constraints(root_dependencies)
    if not constraints:
        return "success"
    if any(name not in state.packages for name in constraints):
        return "unregistered"
    for name, ranges in constraints.items():
        if not _model_viable_releases(state, name, ranges):
            return "unsatisfiable"
    return "success"


def _model_resolution(
    state: "SemverSolverState",
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome:
    """Synthesizes a resolution outcome directly from registered model state."""
    if not _is_dependency_collection(root_dependencies):
        return ResolutionOutcome({}, ())
    constraints = _model_constraints(root_dependencies)
    selected: Dict[str, Version] = {}
    steps: List[str] = []
    for name in sorted(constraints):
        for release in state.packages.get(name, []):
            if all(
                _reference_satisfies(release.version, constraint.raw_text, False)
                for constraint in constraints[name]
            ):
                selected[name] = release.version
                steps.append(f"Assign '{name}' to {_format_version(release.version)}")
                break
    return ResolutionOutcome(selected, tuple(steps))


def _model_record_version(
    state: "SemverSolverState",
    text: Optional[str],
    version: Optional[Version],
) -> None:
    """Records a parsed version into model state."""
    if isinstance(text, str) and isinstance(version, Version):
        state.parsed_versions[text] = version


def _model_register(state: "SemverSolverState", release: Optional[PackageRelease]) -> None:
    """Registers a release into model state, keeping descending precedence order."""
    if not isinstance(release, PackageRelease):
        return
    releases = state.packages.setdefault(release.name, [])
    releases.append(release)
    releases.sort(key=cmp_to_key(lambda left, right: _precedence(right.version, left.version)))


def _model_record_resolution(
    state: "SemverSolverState",
    outcome: Optional[ResolutionOutcome],
) -> None:
    """Records a successful resolution outcome into model state."""
    if isinstance(outcome, ResolutionOutcome):
        state.resolutions.append(outcome)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for the SemVer solver services."""

    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    parsed_versions: Dict[str, Version] = field(default_factory=dict)
    resolutions: List[ResolutionOutcome] = field(default_factory=list)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense state machine modelling the SemVer solver services."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state if state is not None else SemverSolverState(), singletons=singletons)

    # -- VersionEngine.parse_version -------------------------------------------

    @transition(VersionEngine.parse_version)
    def parse_version_valid(
        self,
        ctx: TransitionContext[VersionEngine, [str], Version],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(text=Domain(strategy=lambda: st.builds(_format_version, _version_strategy()), validator=lambda text: isinstance(text, str) and _is_valid_version_text(text)))
        ctx.returns(lambda text=None: _reference_parse_version(text))
        ctx.ensures(
            lambda res, target, check, text=None: _ensure_parsed_version(res, target, check, text)
        )
        ctx.update(lambda res, text=None: _model_record_version(self.state, text, res))

    @transition(VersionEngine.parse_version)
    def parse_version_invalid(
        self,
        ctx: TransitionContext[VersionEngine, [str], Version],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(text=Domain(strategy=lambda: st.sampled_from(_INVALID_VERSION_TEXTS), validator=lambda text: not (isinstance(text, str) and _is_valid_version_text(text))))
        ctx.raises(InvalidVersionError)

    # -- VersionEngine.compare_precedence --------------------------------------

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [Version, Version], int],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(
                    v1=Domain(strategy=lambda: _version_strategy(), validator=lambda v1: isinstance(v1, Version)),
                    v2=Domain(strategy=lambda: _version_strategy(), validator=lambda v2: isinstance(v2, Version)),
                )
        ctx.returns(lambda v1=None, v2=None: _precedence(v1, v2))
        ctx.ensures(
            lambda res, target, check, v1=None, v2=None: _ensure_precedence(res, target, check, v1, v2)
        )

    # -- VersionEngine.parse_range ---------------------------------------------

    @transition(VersionEngine.parse_range)
    def parse_range_valid(
        self,
        ctx: TransitionContext[VersionEngine, [str], VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(text=Domain(strategy=lambda: _parse_range_text_strategy(), validator=lambda text: isinstance(text, str) and _is_valid_range_text(text)))
        ctx.returns(lambda text=None: VersionRange(text.strip()))
        ctx.ensures(
            lambda res, target, check, text=None: _ensure_parsed_range(res, target, check, text)
        )

    @transition(VersionEngine.parse_range)
    def parse_range_invalid(
        self,
        ctx: TransitionContext[VersionEngine, [str], VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(text=Domain(strategy=lambda: st.sampled_from(_INVALID_RANGE_TEXTS), validator=lambda text: not (isinstance(text, str) and _is_valid_range_text(text))))
        ctx.raises(InvalidRangeError)

    # -- VersionEngine.satisfies -----------------------------------------------

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [Version, VersionRange, bool], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(
                    version=Domain(strategy=lambda: _version_strategy(), validator=lambda version: isinstance(version, Version)),
                    range_constraint=Domain(strategy=lambda: _range_strategy(), validator=lambda range_constraint: isinstance(range_constraint, VersionRange)),
                    include_prerelease=Domain(strategy=lambda: st.booleans()),
                )
        ctx.returns(
            lambda version=None, range_constraint=None, include_prerelease=False: _reference_satisfies(
                version,
                range_constraint.raw_text,
                _include_prerelease_flag(include_prerelease),
            )
        )
        ctx.ensures(
            lambda res, target, check, version=None, range_constraint=None, include_prerelease=False: _ensure_satisfies(
                res,
                target,
                check,
                version,
                range_constraint,
                _include_prerelease_flag(include_prerelease),
            )
        )

    # -- PackageRepository.register_package ------------------------------------

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [PackageRelease], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(release=Domain(strategy=lambda: st.builds(PackageRelease, st.sampled_from(_NAME_POOL), _normal_version_strategy(), st.just(())), validator=lambda release: isinstance(release, PackageRelease)))
        ctx.returns(lambda release=None: None)
        ctx.ensures(
            lambda res, target, check, release=None: _ensure_registered(res, target, check, release)
        )
        ctx.update(lambda res, release=None: _model_register(self.state, release))

    # -- PackageRepository.get_releases ----------------------------------------

    @transition(PackageRepository.get_releases)
    def get_releases_found(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(name=Domain(strategy=lambda: st.sampled_from(_NAME_POOL), validator=lambda name: isinstance(name, str) and name in self.state.packages))
        ctx.returns(
            lambda name=None: list(self.state.packages.get(name, []))
        )
        ctx.ensures(
            lambda res, target, check, name=None: _ensure_releases(res, target, check, name, self.state)
        )

    @transition(PackageRepository.get_releases)
    def get_releases_missing(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(name=Domain(strategy=lambda: st.sampled_from(_NAME_POOL), validator=lambda name: not (isinstance(name, str) and name in self.state.packages)))
        ctx.raises(PackageNotFoundError)

    # -- PackageRepository.has_package -----------------------------------------

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(name=Domain(strategy=lambda: st.sampled_from(_NAME_POOL), validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name=None: name in self.state.packages)
        ctx.ensures(
            lambda res, target, check, name=None: _ensure_has_package(res, target, check, name, self.state)
        )

    # -- PackageRepository.all_packages ----------------------------------------

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
        ctx: TransitionContext[PackageRepository, [], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments()
        ctx.returns(lambda: set(self.state.packages))
        ctx.ensures(
            lambda res, target, check: _ensure_all_packages(res, target, check, self.state)
        )

    # -- DependencySolver.resolve ----------------------------------------------

    @transition(DependencySolver.resolve)
    def resolve_success(
        self,
        ctx: TransitionContext[DependencySolver, [Collection[PackageDependency]], ResolutionOutcome],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: _dependency_collection_strategy(), validator=lambda root_dependencies: _model_resolution_kind(self.state, root_dependencies) == 'success'))
        ctx.returns(
            lambda root_dependencies=None: _model_resolution(self.state, root_dependencies)
        )
        ctx.ensures(
            lambda res, target, check, root_dependencies=None: _ensure_resolved(
                res, target, check, root_dependencies, self.state
            )
        )
        ctx.update(
            lambda res, root_dependencies=None: _model_record_resolution(self.state, res)
        )

    @transition(DependencySolver.resolve)
    def resolve_unregistered(
        self,
        ctx: TransitionContext[DependencySolver, [Collection[PackageDependency]], ResolutionOutcome],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: _dependency_collection_strategy(), validator=lambda root_dependencies: _model_resolution_kind(self.state, root_dependencies) == 'unregistered'))
        ctx.raises(ResolutionConflictError)

    @transition(DependencySolver.resolve)
    def resolve_unsatisfiable(
        self,
        ctx: TransitionContext[DependencySolver, [Collection[PackageDependency]], ResolutionOutcome],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "SemVer solver services are initialized"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: _dependency_collection_strategy(), validator=lambda root_dependencies: _model_resolution_kind(self.state, root_dependencies) == 'unsatisfiable'))
        ctx.raises(ResolutionConflictError)


# ==============================================================================
# Hypothesis Search Strategies
# ==============================================================================

def _normal_version_strategy() -> st.SearchStrategy[Version]:
    """Draws non-prerelease, build-metadata-free versions."""
    return st.builds(
        _make_version,
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=0, max_value=20),
        st.just(_EMPTY_IDENTIFIERS),
        st.just(_EMPTY_IDENTIFIERS),
    )


def _version_strategy() -> st.SearchStrategy[Version]:
    """Draws arbitrary well-formed versions including prerelease and build identifiers."""
    return st.builds(
        _make_version,
        st.integers(min_value=0, max_value=10),
        st.integers(min_value=0, max_value=10),
        st.integers(min_value=0, max_value=10),
        st.sampled_from(_PRERELEASE_SAMPLES),
        st.sampled_from(_BUILD_SAMPLES),
    )


def _range_text_strategy() -> st.SearchStrategy[str]:
    """Draws syntactically valid range expressions across the documented grammar."""
    boundary = _normal_version_strategy()
    return st.one_of(
        st.just("*"),
        st.builds(lambda version: ">=" + _format_version(version), boundary),
        st.builds(lambda version: "<" + _format_version(version), boundary),
        st.builds(lambda version: ">" + _format_version(version), boundary),
        st.builds(lambda version: "<=" + _format_version(version), boundary),
        st.builds(lambda version: "==" + _format_version(version), boundary),
        st.builds(lambda version: "^" + _format_version(version), boundary),
        st.builds(lambda version: "~" + _format_version(version), boundary),
        st.builds(
            lambda upper, lower: f"{_format_version(lower)} - {_format_version(upper)}",
            boundary,
            boundary,
        ),
        st.builds(
            lambda upper, lower: f">={_format_version(lower)} <{_format_version(upper)}",
            boundary,
            boundary,
        ),
        st.builds(
            lambda upper, lower: f">={_format_version(lower)} || <{_format_version(upper)}",
            boundary,
            boundary,
        ),
        st.builds(lambda major: f"{major}.x", st.integers(min_value=0, max_value=5)),
        st.builds(
            lambda major, minor: f"{major}.{minor}.*",
            st.integers(min_value=0, max_value=5),
            st.integers(min_value=0, max_value=5),
        ),
        st.builds(lambda version: f"  >= {_format_version(version)}  ", boundary),
    )


def _parse_range_text_strategy() -> st.SearchStrategy[str]:
    """Draws valid range expressions including prefix operators over wildcard operands."""
    return st.one_of(
        _range_text_strategy(),
        st.builds(
            lambda major, minor: f"^{major}.{minor}.x",
            st.integers(min_value=0, max_value=5),
            st.integers(min_value=0, max_value=5),
        ),
        st.builds(
            lambda major: f"^{major}.*",
            st.integers(min_value=0, max_value=5),
        ),
        st.builds(
            lambda major, minor: f"~{major}.{minor}.x",
            st.integers(min_value=0, max_value=5),
            st.integers(min_value=0, max_value=5),
        ),
        st.builds(
            lambda major, version: f"{_format_version(version)} - {major}.x",
            st.integers(min_value=0, max_value=5),
            _normal_version_strategy(),
        ),
        st.builds(
            lambda major, version: f"{major}.x - {_format_version(version)}",
            st.integers(min_value=0, max_value=5),
            _normal_version_strategy(),
        ),
    )


def _range_strategy() -> st.SearchStrategy[VersionRange]:
    """Draws parsed range records directly for satisfaction queries."""
    return st.builds(VersionRange, _range_text_strategy())


def _dependency_strategy() -> st.SearchStrategy[PackageDependency]:
    """Draws root dependency requirements over the shared package name pool."""
    return st.builds(
        PackageDependency,
        st.sampled_from(_NAME_POOL),
        st.one_of(
            st.just(VersionRange("*")),
            st.builds(lambda version: VersionRange(">=" + _format_version(version)), _normal_version_strategy()),
            st.builds(lambda version: VersionRange("^" + _format_version(version)), _normal_version_strategy()),
        ),
    )


def _dependency_collection_strategy() -> st.SearchStrategy[Tuple[PackageDependency, ...]]:
    """Draws a bounded tuple of root dependency requirements."""
    return st.lists(_dependency_strategy(), min_size=0, max_size=3).map(tuple)


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake service instances backed by one shared state machine."""
    shared_state = state if state is not None else SemverSolverState()
    state_machine = SemverSolverStateMachine(state=shared_state)
    return (
        state_machine.as_fake(VersionEngine),
        state_machine.as_fake(PackageRepository),
        state_machine.as_fake(DependencySolver),
    )


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestSemverSolverUnit(unittest.TestCase):
    """Verifies that synthesized fakes execute the contracted state transitions."""

    def setUp(self) -> None:
        self.state = SemverSolverState()
        self.engine, self.repository, self.solver = make_semver_solver_fakes(self.state)

    def _expect_contracted_failure(
        self,
        expected_type: type[BaseException],
        operation: Callable[[], Any],
    ) -> None:
        """Verifies an operation reports a contracted exception outcome."""
        try:
            outcome = operation()
        except expected_type:
            return
        self.assertIsInstance(outcome, Raised)

    def test_fake_parse_version(self) -> None:
        parsed = self.engine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual(parsed, Version(1, 2, 3, ("alpha", "1"), ("build", "5")))
        self.assertEqual(self.state.parsed_versions["1.2.3-alpha.1+build.5"], parsed)

    def test_fake_parse_version_rejects_invalid(self) -> None:
        self._expect_contracted_failure(
            InvalidVersionError,
            lambda: self.engine.parse_version("1.2"),
        )
        self.assertNotIn("1.2", self.state.parsed_versions)

    def test_fake_compare_precedence_numeric(self) -> None:
        self.assertLess(self.engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 4)), 0)
        self.assertGreater(self.engine.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)), 0)
        self.assertEqual(self.engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)

    def test_fake_compare_precedence_prerelease(self) -> None:
        self.assertLess(
            self.engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "2"))),
            0,
        )
        self.assertEqual(
            self.engine.compare_precedence(Version(1, 0, 0, (), ("build",)), Version(1, 0, 0)),
            0,
        )

    def test_fake_parse_range_trims_expression(self) -> None:
        parsed = self.engine.parse_range("  >= 1.0.0  ")
        self.assertEqual(parsed.raw_text, ">= 1.0.0")
        self.assertEqual(str(parsed), ">= 1.0.0")

    def test_fake_parse_range_rejects_invalid(self) -> None:
        self._expect_contracted_failure(
            InvalidRangeError,
            lambda: self.engine.parse_range("1.2"),
        )

    def test_fake_satisfies_wildcard(self) -> None:
        self.assertTrue(self.engine.satisfies(Version(3, 4, 5), VersionRange("*")))
        self.assertFalse(self.engine.satisfies(Version(3, 4, 5, ("alpha",)), VersionRange("*")))
        self.assertTrue(self.engine.satisfies(Version(3, 4, 5, ("alpha",)), VersionRange("*"), True))

    def test_fake_satisfies_caret_boundaries(self) -> None:
        self.assertTrue(self.engine.satisfies(Version(1, 9, 0), VersionRange("^1.2.3")))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), VersionRange("^1.2.3")))
        self.assertFalse(self.engine.satisfies(Version(1, 2, 2), VersionRange("^1.2.3")))
        self.assertTrue(self.engine.satisfies(Version(0, 2, 9), VersionRange("^0.2.3")))
        self.assertFalse(self.engine.satisfies(Version(0, 3, 0), VersionRange("^0.2.3")))

    def test_fake_register_and_query(self) -> None:
        self.repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.assertTrue(self.repository.has_package("alpha"))
        self.assertEqual(self.repository.all_packages(), {"alpha"})
        releases = self.repository.get_releases("alpha")
        self.assertEqual([release.version for release in releases], [Version(2, 0, 0), Version(1, 0, 0)])

    def test_fake_get_releases_missing(self) -> None:
        self._expect_contracted_failure(
            PackageNotFoundError,
            lambda: self.repository.get_releases("ghost"),
        )

    def test_fake_resolve_success(self) -> None:
        self.repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.repository.register_package(PackageRelease("alpha", Version(1, 5, 0)))
        outcome = self.solver.resolve((PackageDependency("alpha", VersionRange("^1.0.0")),))
        self.assertEqual(dict(outcome.selected_versions), {"alpha": Version(1, 5, 0)})
        self.assertEqual(len(outcome.derivation_steps), 1)

    def test_fake_resolve_unregistered(self) -> None:
        self._expect_contracted_failure(
            ResolutionConflictError,
            lambda: self.solver.resolve((PackageDependency("ghost", VersionRange("*")),)),
        )

    def test_fake_resolve_unsatisfiable(self) -> None:
        self.repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self._expect_contracted_failure(
            ResolutionConflictError,
            lambda: self.solver.resolve((PackageDependency("alpha", VersionRange(">=2.0.0")),)),
        )


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that the concrete services satisfy the mandated contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.state = SemverSolverState()
        self.engine = get_singleton(VersionEngine)
        self.repository = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = SemverSolverStateMachine(
            state=self.state,
            singletons={
                VersionEngine: self.engine,
                PackageRepository: self.repository,
                DependencySolver: self.solver,
            },
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    # -- VersionEngine.parse_version -------------------------------------------

    def test_parse_version_core(self) -> None:
        parsed = self.engine.parse_version("1.2.3")
        self.assertEqual((parsed.major, parsed.minor, parsed.patch), (1, 2, 3))
        self.assertEqual(parsed.prerelease, ())
        self.assertEqual(parsed.build, ())
        self.assertFalse(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "1.2.3")
        self.assertEqual(str(parsed), "1.2.3")

    def test_parse_version_identifiers(self) -> None:
        parsed = self.engine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual((parsed.major, parsed.minor, parsed.patch), (1, 2, 3))
        self.assertEqual(parsed.prerelease, ("alpha", "1"))
        self.assertEqual(parsed.build, ("build", "5"))
        self.assertTrue(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "1.2.3-alpha.1+build.5")
        self.assertEqual(str(parsed), "1.2.3-alpha.1+build.5")

    def test_parse_version_zero_components(self) -> None:
        parsed = self.engine.parse_version("0.0.0")
        self.assertEqual((parsed.major, parsed.minor, parsed.patch), (0, 0, 0))
        self.assertEqual(parsed.format(), "0.0.0")

    def test_parse_version_rejects_invalid(self) -> None:
        for text in (
            "1.2",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2.3-",
            "1.2.3.4",
            "1.2.3+build..5",
            "1.2.3+",
            "v1.2.3",
            "1.2.3-alpha..1",
            "",
        ):
            with self.assertRaises(InvalidVersionError) as context:
                self.engine.parse_version(text)
            self.assertEqual(context.exception.raw_text, text)

    # -- VersionEngine.compare_precedence --------------------------------------

    def test_compare_precedence_numeric(self) -> None:
        self.assertLess(self.engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 4)), 0)
        self.assertGreater(self.engine.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)), 0)
        self.assertEqual(self.engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)
        self.assertLess(self.engine.compare_precedence(Version(0, 0, 1), Version(0, 0, 2)), 0)

    def test_compare_precedence_prerelease(self) -> None:
        self.assertGreater(
            self.engine.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, ("alpha",))),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "2"))
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "1", "extra"))
            ),
            0,
        )
        self.assertGreater(
            self.engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("1",))),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))),
            0,
        )

    def test_compare_precedence_numeric_prerelease_identifiers(self) -> None:
        self.assertLess(
            self.engine.compare_precedence(Version(1, 0, 0, ("2",)), Version(1, 0, 0, ("10",))),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",))),
            0,
        )
        self.assertGreater(
            self.engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("1",))),
            0,
        )

    def test_compare_precedence_antisymmetry(self) -> None:
        smaller = Version(1, 2, 3)
        larger = Version(1, 10, 0)
        self.assertEqual(
            _sign(self.engine.compare_precedence(smaller, larger)),
            -_sign(self.engine.compare_precedence(larger, smaller)),
        )

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        self.assertEqual(
            self.engine.compare_precedence(
                Version(1, 0, 0, (), ("build",)), Version(1, 0, 0, (), ("other",))
            ),
            0,
        )
        self.assertEqual(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha",), ("build",)), Version(1, 0, 0, ("alpha",))
            ),
            0,
        )

    # -- VersionEngine.parse_range ---------------------------------------------

    def test_parse_range_trims_expression(self) -> None:
        parsed = self.engine.parse_range("  >= 1.0.0  ")
        self.assertEqual(parsed.raw_text, ">= 1.0.0")
        self.assertEqual(str(parsed), ">= 1.0.0")

    def test_parse_range_supported_grammar(self) -> None:
        for text in (
            ">=1.0.0",
            "> 1.2.3",
            "<=2.0.0",
            "<2.0.0",
            "==1.2.3",
            "=1.2.3",
            "!=1.2.3",
            ">=1.0.0 <2.0.0",
            "^1.2.3",
            "^0.2.3",
            "~1.2.3",
            "*",
            "1.x",
            "1.2.x",
            "1.2.*",
            "^1.2.x",
            "~1.2.x",
            "1.0.0 - 2.0.0",
            ">=1.0.0 || <0.5.0",
        ):
            parsed = self.engine.parse_range(text)
            self.assertEqual(parsed.raw_text, text.strip())

    def test_parse_range_build_metadata_operands(self) -> None:
        for text in (
            ">=1.2.3+build.5",
            "<=2.0.0+ci.42",
            "==1.2.3+build.5",
            "1.2.3+build.5 - 2.0.0+build.6",
        ):
            parsed = self.engine.parse_range(text)
            self.assertEqual(parsed.raw_text, text)
        self.assertTrue(self.engine.satisfies(Version(1, 2, 4), VersionRange(">=1.2.3+build.5")))
        self.assertFalse(self.engine.satisfies(Version(1, 2, 2), VersionRange(">=1.2.3+build.5")))

    def test_parse_range_caret_wildcard_zero_components(self) -> None:
        for text in ("^0.x", "^0.0.x", "^0.*"):
            parsed = self.engine.parse_range(text)
            self.assertEqual(parsed.raw_text, text)
        self.assertTrue(self.engine.satisfies(Version(0, 0, 0), VersionRange("^0.x")))
        self.assertFalse(self.engine.satisfies(Version(1, 0, 0), VersionRange("^0.x")))
        self.assertTrue(self.engine.satisfies(Version(0, 0, 0), VersionRange("^0.0.x")))
        self.assertFalse(self.engine.satisfies(Version(0, 1, 0), VersionRange("^0.0.x")))

    def test_parse_range_tilde_single_component_wildcard(self) -> None:
        for text in ("~1.*", "~1.x"):
            parsed = self.engine.parse_range(text)
            self.assertEqual(parsed.raw_text, text)
        self.assertTrue(self.engine.satisfies(Version(1, 0, 0), VersionRange("~1.*")))
        self.assertTrue(self.engine.satisfies(Version(1, 9, 9), VersionRange("~1.*")))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), VersionRange("~1.*")))
        self.assertFalse(self.engine.satisfies(Version(0, 9, 9), VersionRange("~1.*")))

    def test_parse_range_wildcard_relational_operands(self) -> None:
        for text in ("!=*", "!=1.x", ">1.x", ">=1.x", "<1.x", "<=1.x"):
            parsed = self.engine.parse_range(text)
            self.assertEqual(parsed.raw_text, text)

    def test_parse_range_rejects_invalid(self) -> None:
        for text in (
            "1",
            "1.2",
            "^0.0",
            "1.2 - 2.3",
            "1.2.3, <2.0.0",
            ">=1.0.0 ||",
            "|| >=1.0.0",
            "",
        ):
            with self.assertRaises(InvalidRangeError) as context:
                self.engine.parse_range(text)
            self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_rejects_blank_expression(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range("   ")

    def test_parse_range_rejects_malformed_operators(self) -> None:
        for text in (">=", "^", "~", "!=", ">>1.0.0", "1.0.0>=", "=<1.0.0"):
            with self.assertRaises(InvalidRangeError) as context:
                self.engine.parse_range(text)
            self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_rejects_malformed_operand_segments(self) -> None:
        for text in (
            ">=1.2.3-",
            ">=1.2.3-alpha..1",
            ">=1.2.3.4",
            ">=1.2.a",
            ">=1.x.3",
            ">=1.2.3+build..5",
            ">=1.2.3+",
        ):
            with self.assertRaises(InvalidRangeError) as context:
                self.engine.parse_range(text)
            self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_rejects_adjacent_comparators(self) -> None:
        with self.assertRaises(InvalidRangeError) as context:
            self.engine.parse_range(">=1.0.0<2.0.0")
        self.assertEqual(context.exception.raw_range, ">=1.0.0<2.0.0")

    def test_parse_range_rejects_multiple_build_separators(self) -> None:
        for text in (">=1.2.3+build+extra", "==1.2.3+build.5+extra"):
            with self.assertRaises(InvalidRangeError) as context:
                self.engine.parse_range(text)
            self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_rejects_decorated_wildcards(self) -> None:
        for text in (">=1.2.x-alpha", ">=1.2.x+build.5", "1.2.*-rc.1"):
            with self.assertRaises(InvalidRangeError) as context:
                self.engine.parse_range(text)
            self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_rejects_non_numeric_wildcard_prefix(self) -> None:
        for text in (">=a.x", "~a.1.x", "^a.*"):
            with self.assertRaises(InvalidRangeError) as context:
                self.engine.parse_range(text)
            self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_wildcard_hyphen_endpoints(self) -> None:
        for text in ("1.0.0 - 2.x", "1.x - 2.0.0", "1.2.x - 2.3.*", "1.0.0 - 2.*"):
            parsed = self.engine.parse_range(text)
            self.assertEqual(parsed.raw_text, text)

    def test_parse_range_rejects_invalid_hyphen_endpoints(self) -> None:
        for text in (">=1.0.0 - 2.0.0", "1.2 - 2.3", "1.0.0 - 2.0.0 - 3.0.0"):
            with self.assertRaises(InvalidRangeError) as context:
                self.engine.parse_range(text)
            self.assertEqual(context.exception.raw_range, text)

    # -- VersionEngine.satisfies -----------------------------------------------

    def test_satisfies_relational_comparators(self) -> None:
        self.assertTrue(self.engine.satisfies(Version(1, 2, 3), VersionRange(">=1.0.0")))
        self.assertFalse(self.engine.satisfies(Version(0, 9, 0), VersionRange(">=1.0.0")))
        self.assertTrue(self.engine.satisfies(Version(1, 2, 3), VersionRange("<2.0.0")))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), VersionRange("<2.0.0")))
        self.assertTrue(self.engine.satisfies(Version(1, 2, 3), VersionRange("<=1.2.3")))
        self.assertTrue(self.engine.satisfies(Version(1, 2, 4), VersionRange(">1.2.3")))
        self.assertTrue(self.engine.satisfies(Version(1, 2, 3), VersionRange("==1.2.3")))
        self.assertFalse(self.engine.satisfies(Version(1, 2, 3), VersionRange("!=1.2.3")))
        self.assertTrue(self.engine.satisfies(Version(1, 5, 0), VersionRange(">=1.0.0 <2.0.0")))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), VersionRange(">=1.0.0 <2.0.0")))

    def test_satisfies_caret(self) -> None:
        self.assertTrue(self.engine.satisfies(Version(1, 9, 0), VersionRange("^1.2.3")))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), VersionRange("^1.2.3")))
        self.assertFalse(self.engine.satisfies(Version(1, 2, 2), VersionRange("^1.2.3")))
        self.assertTrue(self.engine.satisfies(Version(0, 2, 9), VersionRange("^0.2.3")))
        self.assertFalse(self.engine.satisfies(Version(0, 3, 0), VersionRange("^0.2.3")))
        self.assertTrue(self.engine.satisfies(Version(0, 0, 3), VersionRange("^0.0.3")))
        self.assertFalse(self.engine.satisfies(Version(0, 0, 4), VersionRange("^0.0.3")))

    def test_satisfies_tilde(self) -> None:
        self.assertTrue(self.engine.satisfies(Version(1, 2, 9), VersionRange("~1.2.3")))
        self.assertFalse(self.engine.satisfies(Version(1, 3, 0), VersionRange("~1.2.3")))
        self.assertTrue(self.engine.satisfies(Version(0, 1, 5), VersionRange("~0.1.0")))
        self.assertFalse(self.engine.satisfies(Version(0, 2, 0), VersionRange("~0.1.0")))

    def test_satisfies_wildcards(self) -> None:
        self.assertTrue(self.engine.satisfies(Version(3, 4, 5), VersionRange("*")))
        self.assertTrue(self.engine.satisfies(Version(1, 9, 9), VersionRange("1.x")))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), VersionRange("1.x")))
        self.assertTrue(self.engine.satisfies(Version(1, 2, 9), VersionRange("1.2.x")))
        self.assertFalse(self.engine.satisfies(Version(1, 3, 0), VersionRange("1.2.x")))

    def test_satisfies_hyphen_and_union(self) -> None:
        self.assertTrue(self.engine.satisfies(Version(1, 5, 0), VersionRange("1.0.0 - 2.0.0")))
        self.assertTrue(self.engine.satisfies(Version(2, 0, 0), VersionRange("1.0.0 - 2.0.0")))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 1), VersionRange("1.0.0 - 2.0.0")))
        self.assertTrue(self.engine.satisfies(Version(0, 4, 0), VersionRange(">=1.0.0 || <0.5.0")))
        self.assertTrue(self.engine.satisfies(Version(1, 5, 0), VersionRange(">=1.0.0 || <0.5.0")))
        self.assertFalse(self.engine.satisfies(Version(0, 6, 0), VersionRange(">=1.0.0 || <0.5.0")))

    def test_satisfies_excludes_prerelease_by_default(self) -> None:
        self.assertFalse(
            self.engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=0.0.0"))
        )
        self.assertFalse(self.engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange("*")))
        self.assertFalse(
            self.engine.satisfies(Version(2, 0, 0, ("rc", "1")), VersionRange("1.0.0 - 3.0.0"))
        )

    def test_satisfies_includes_prerelease_when_requested(self) -> None:
        self.assertTrue(self.engine.satisfies(Version(2, 0, 0, ("alpha",)), VersionRange("*"), True))
        self.assertFalse(
            self.engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), True)
        )
        self.assertTrue(
            self.engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange("<1.0.0"), True)
        )
        self.assertTrue(
            self.engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0-alpha"), True)
        )

    def test_satisfies_targets_matching_prerelease(self) -> None:
        self.assertTrue(
            self.engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0-alpha"))
        )

    # -- PackageRepository -----------------------------------------------------

    def test_repository_register_and_query(self) -> None:
        self.assertIsNone(self.repository.register_package(PackageRelease("alpha", Version(1, 0, 0))))
        self.repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.repository.register_package(PackageRelease("beta", Version(0, 1, 0)))
        self.assertTrue(self.repository.has_package("alpha"))
        self.assertFalse(self.repository.has_package("missing"))
        self.assertEqual(self.repository.all_packages(), {"alpha", "beta"})
        releases = self.repository.get_releases("alpha")
        self.assertEqual([release.version for release in releases], [Version(2, 0, 0), Version(1, 0, 0)])
        self.assertTrue(all(release.name == "alpha" for release in releases))

    def test_repository_sorts_descending_precedence(self) -> None:
        for version in (
            Version(1, 0, 0),
            Version(1, 0, 0, ("alpha",)),
            Version(1, 0, 0, ("alpha", "1")),
            Version(2, 0, 0),
        ):
            self.repository.register_package(PackageRelease("gamma", version))
        self.assertEqual(
            [release.version for release in self.repository.get_releases("gamma")],
            [
                Version(2, 0, 0),
                Version(1, 0, 0),
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha",)),
            ],
        )

    def test_repository_get_releases_returns_copy(self) -> None:
        self.repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        releases = self.repository.get_releases("alpha")
        releases.append(PackageRelease("alpha", Version(2, 0, 0)))
        self.assertEqual(len(self.repository.get_releases("alpha")), 1)

    def test_repository_get_releases_missing(self) -> None:
        with self.assertRaises(PackageNotFoundError) as context:
            self.repository.get_releases("ghost")
        self.assertEqual(context.exception.package_name, "ghost")

    # -- DependencySolver ------------------------------------------------------

    def test_resolve_empty_dependencies(self) -> None:
        outcome = self.solver.resolve(())
        self.assertEqual(dict(outcome.selected_versions), {})
        self.assertEqual(tuple(outcome.derivation_steps), ())

    def test_resolve_selects_highest_compatible(self) -> None:
        self.repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.repository.register_package(PackageRelease("alpha", Version(1, 5, 0)))
        self.repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.repository.register_package(PackageRelease("beta", Version(1, 0, 0)))
        self.repository.register_package(PackageRelease("beta", Version(3, 0, 0)))
        outcome = self.solver.resolve(
            (
                PackageDependency("alpha", VersionRange("^1.0.0")),
                PackageDependency("beta", VersionRange(">=1.0.0")),
            )
        )
        self.assertEqual(
            dict(outcome.selected_versions),
            {"alpha": Version(1, 5, 0), "beta": Version(3, 0, 0)},
        )
        self.assertTrue(outcome.derivation_steps)
        self.assertTrue(
            self.engine.satisfies(outcome.selected_versions["alpha"], VersionRange("^1.0.0"))
        )
        self.assertTrue(
            self.engine.satisfies(outcome.selected_versions["beta"], VersionRange(">=1.0.0"))
        )

    def test_resolve_transitive_dependencies(self) -> None:
        self.repository.register_package(
            PackageRelease(
                "alpha",
                Version(1, 1, 0),
                (PackageDependency("beta", VersionRange("^2.0.0")),),
            )
        )
        self.repository.register_package(PackageRelease("beta", Version(2, 0, 0)))
        self.repository.register_package(PackageRelease("beta", Version(1, 0, 0)))
        outcome = self.solver.resolve((PackageDependency("alpha", VersionRange("^1.0.0")),))
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 1, 0))
        self.assertEqual(outcome.selected_versions["beta"], Version(2, 0, 0))

    def test_resolve_backtracks_over_unsatisfiable_candidate(self) -> None:
        self.repository.register_package(
            PackageRelease(
                "alpha",
                Version(1, 2, 0),
                (PackageDependency("gamma", VersionRange("^1.0.0")),),
            )
        )
        self.repository.register_package(
            PackageRelease(
                "alpha",
                Version(1, 1, 0),
                (PackageDependency("beta", VersionRange("^2.0.0")),),
            )
        )
        self.repository.register_package(PackageRelease("beta", Version(2, 0, 0)))
        self.repository.register_package(PackageRelease("beta", Version(1, 0, 0)))
        outcome = self.solver.resolve((PackageDependency("alpha", VersionRange("^1.0.0")),))
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 1, 0))
        self.assertEqual(outcome.selected_versions["beta"], Version(2, 0, 0))

    def test_resolve_unregistered_package(self) -> None:
        with self.assertRaises(ResolutionConflictError) as context:
            self.solver.resolve((PackageDependency("ghost", VersionRange(">=1.0.0")),))
        self.assertIn("ghost", context.exception.conflicting_packages)
        self.assertTrue(context.exception.explanation)

    def test_resolve_unsatisfiable_constraint(self) -> None:
        self.repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        with self.assertRaises(ResolutionConflictError) as context:
            self.solver.resolve((PackageDependency("alpha", VersionRange(">=2.0.0")),))
        self.assertIn("alpha", context.exception.conflicting_packages)
        self.assertTrue(context.exception.explanation)

    def test_resolve_conflicting_transitive_constraints(self) -> None:
        self.repository.register_package(
            PackageRelease(
                "alpha",
                Version(1, 0, 0),
                (PackageDependency("beta", VersionRange("^1.0.0")),),
            )
        )
        self.repository.register_package(
            PackageRelease(
                "gamma",
                Version(1, 0, 0),
                (PackageDependency("beta", VersionRange("^2.0.0")),),
            )
        )
        self.repository.register_package(PackageRelease("beta", Version(1, 0, 0)))
        self.repository.register_package(PackageRelease("beta", Version(2, 0, 0)))
        with self.assertRaises(ResolutionConflictError) as context:
            self.solver.resolve(
                (
                    PackageDependency("alpha", VersionRange("^1.0.0")),
                    PackageDependency("gamma", VersionRange("^1.0.0")),
                )
            )
        self.assertIn("beta", context.exception.conflicting_packages)
        self.assertTrue(context.exception.explanation)


# ==============================================================================
# Verification Helper Postconditions
# ==============================================================================

def _ensure_parsed_version(
    res: Any,
    target: "VersionEngine",
    check: Any,
    text: Optional[str],
) -> None:
    """Verifies the parsed version mirrors the SemVer reference parse."""
    if not isinstance(text, str) or not isinstance(res, Version):
        return
    reference = _reference_parse_version(text)
    check.equal(res.major, reference.major)
    check.equal(res.minor, reference.minor)
    check.equal(res.patch, reference.patch)
    check.equal(res.prerelease, reference.prerelease)
    check.equal(res.build, reference.build)
    check.equal(res.format(), text)
    check.equal(str(res), res.format())
    check(target.compare_precedence(res, res) == 0, "a parsed version is ordered equal to itself")


def _ensure_precedence(
    res: Any,
    target: "VersionEngine",
    check: Any,
    v1: Optional[Version],
    v2: Optional[Version],
) -> None:
    """Verifies precedence antisymmetry, reflexivity, and build-metadata exclusion."""
    if not isinstance(v1, Version) or not isinstance(v2, Version) or not isinstance(res, int):
        return
    check.equal(_sign(res), _sign(_precedence(v1, v2)))
    check.equal(_sign(res), -_sign(target.compare_precedence(v2, v1)))
    check.equal(target.compare_precedence(v1, v1), 0)
    check.equal(target.compare_precedence(v1, replace(v1, build=("build",))), 0)
    check.equal(target.compare_precedence(v2, replace(v2, build=("other", "metadata"))), 0)


def _ensure_parsed_range(
    res: Any,
    target: "VersionEngine",
    check: Any,
    text: Optional[str],
) -> None:
    """Verifies range parsing stores the trimmed expression and matches the reference."""
    if not isinstance(text, str) or not isinstance(res, VersionRange):
        return
    check.equal(res.raw_text, text.strip())
    check.equal(str(res), res.raw_text)
    probe = Version(0, 0, 0)
    check.equal(
        target.satisfies(probe, res, True),
        _reference_satisfies(probe, res.raw_text, True),
    )


def _ensure_satisfies(
    res: Any,
    target: "VersionEngine",
    check: Any,
    version: Optional[Version],
    range_constraint: Optional[VersionRange],
    include_prerelease: Optional[bool],
) -> None:
    """Verifies satisfaction agrees with the reference and precedence boundaries."""
    if (
        not isinstance(version, Version)
        or not isinstance(range_constraint, VersionRange)
        or not isinstance(include_prerelease, bool)
        or not isinstance(res, bool)
    ):
        return
    check.equal(
        res,
        _reference_satisfies(version, range_constraint.raw_text, include_prerelease),
    )
    # A wildcard range never excludes normal versions and excludes prereleases unless asked.
    wildcard_expected = include_prerelease or not version.prerelease
    check.equal(target.satisfies(version, VersionRange("*"), include_prerelease), wildcard_expected)
    # Precedence boundaries are not shifted for prerelease candidates.
    formatted = _format_version(
        Version(version.major, version.minor, version.patch, version.prerelease)
    )
    check.equal(target.satisfies(version, VersionRange(f">{formatted}"), include_prerelease), False)
    check.equal(target.satisfies(version, VersionRange(f"<={formatted}"), include_prerelease), True)
    check.equal(target.satisfies(version, VersionRange(f"=={formatted}"), include_prerelease), True)


def _ensure_registered(
    res: Any,
    target: "PackageRepository",
    check: Any,
    release: Optional[PackageRelease],
) -> None:
    """Verifies a registered release is retrievable and repository order is descending."""
    if not isinstance(release, PackageRelease) or not isinstance(res, type(None)):
        return
    check(target.has_package(release.name), "a registered package is reported present")
    check(release.name in target.all_packages(), "a registered package appears in all packages")
    releases = target.get_releases(release.name)
    check(
        any(candidate.version == release.version for candidate in releases),
        "the registered release is retrievable by name",
    )
    for earlier, later in zip(releases, releases[1:]):
        check(
            _precedence(earlier.version, later.version) >= 0,
            "repository releases are ordered by descending precedence",
        )


def _ensure_releases(
    res: Any,
    target: "PackageRepository",
    check: Any,
    name: Optional[str],
    state: SemverSolverState,
) -> None:
    """Verifies retrieved releases match the model and keep descending precedence."""
    if not isinstance(name, str) or not isinstance(res, list):
        return
    expected = list(state.packages.get(name, []))
    check.equal([release.version for release in res], [release.version for release in expected])
    for release in res:
        check.equal(release.name, name)
    for earlier, later in zip(res, res[1:]):
        check(
            _precedence(earlier.version, later.version) >= 0,
            "retrieved releases are ordered by descending precedence",
        )


def _ensure_has_package(
    res: Any,
    target: "PackageRepository",
    check: Any,
    name: Optional[str],
    state: SemverSolverState,
) -> None:
    """Verifies membership queries agree with the model and the package index."""
    if not isinstance(name, str) or not isinstance(res, bool):
        return
    check.equal(res, name in state.packages)
    check.equal(res, name in target.all_packages())


def _ensure_all_packages(
    res: Any,
    target: "PackageRepository",
    check: Any,
    state: SemverSolverState,
) -> None:
    """Verifies the reported package set equals the model and indexes every member."""
    if not isinstance(res, set):
        return
    check.equal(res, set(state.packages))
    for name in res:
        check(target.has_package(name), "every reported package is indexed")


def _ensure_resolved(
    res: Any,
    target: "DependencySolver",
    check: Any,
    root_dependencies: Optional[Collection[PackageDependency]],
    state: SemverSolverState,
) -> None:
    """Verifies resolution satisfies root constraints and stays consistent with model state."""
    if root_dependencies is None or not isinstance(res, ResolutionOutcome) or not _is_dependency_collection(root_dependencies):
        return
    for dependency in root_dependencies:
        check(
            dependency.name in res.selected_versions,
            "each root dependency receives a selected version",
        )
        selected = res.selected_versions.get(dependency.name)
        if not isinstance(selected, Version):
            continue
        check(
            _reference_satisfies(selected, dependency.range_constraint.raw_text, False),
            "the selected version satisfies the root constraint",
        )
    for name, version in res.selected_versions.items():
        check(
            any(candidate.version == version for candidate in state.packages.get(name, [])),
            "each selected version refers to a model-registered release",
        )
    # Highest-precedence selection is only fully determined when no transitive
    # dependency constraints exist in the registry; otherwise backtracking may
    # legitimately pick a lower compatible release.
    registry_constrained = any(
        release.dependencies
        for releases in state.packages.values()
        for release in releases
    )
    if not registry_constrained:
        for dependency in root_dependencies:
            root_ranges = [
                item.range_constraint
                for item in root_dependencies
                if item.name == dependency.name
            ]
            viable = [
                release.version
                for release in state.packages.get(dependency.name, [])
                if all(
                    _reference_satisfies(release.version, constraint.raw_text, False)
                    for constraint in root_ranges
                )
            ]
            if viable:
                highest = viable[0]
                for candidate in viable[1:]:
                    if _precedence(candidate, highest) > 0:
                        highest = candidate
                check.equal(res.selected_versions.get(dependency.name), highest)
    if root_dependencies:
        check(len(res.derivation_steps) >= 1, "a resolution records derivation steps")


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================

class SemverSolverSUT:
    """Aggregate system under test exposing the solver services for fuzzing."""

    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.__dict__["_services"] = (
            get_singleton(VersionEngine),
            get_singleton(PackageRepository),
            get_singleton(DependencySolver),
        )

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> SemverSolverSUT:
    """Creates a freshly initialized aggregate system under test."""
    return SemverSolverSUT()


SemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverSolverState,
    name="SemverSolverFuzzTest",
)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T05:21:15Z
# LAST_CHANGED: 2026-10-29T05:20:44Z
# CHANGE: Added the three missing operand-level InvalidRangeError scenarios to the real suite, each asserting the contracted exception type and raw_range: (1) test_parse_range_rejects_multiple_build_separators covers malformed build metadata with more than one '+' separator in a comparator operand ('>=1.2.3+build+extra', '==1.2.3+build.5+extra'); (2) test_parse_range_rejects_decorated_wildcards covers wildcard operands combined with pre-release or build metadata ('>=1.2.x-alpha', '>=1.2.x+build.5', '1.2.*-rc.1'); (3) test_parse_range_rejects_non_numeric_wildcard_prefix covers a non-numeric component preceding a wildcard placeholder ('>=a.x', '~a.1.x', '^a.*'). The same forms were added to _INVALID_RANGE_TEXTS so fake/fuzz invalid-transition generation matches; inline verification confirms all 36 pool entries are rejected by the reference validator while valid controls (wildcard hyphen endpoints, build-metadata comparators, caret/tilde wildcards) remain accepted.
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T05:21:15Z
# PRETENSE_QA_AUDIT: 2026-10-29T05:21:03Z
# --- END CLEANROOM METADATA ---
