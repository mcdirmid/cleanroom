"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
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
    SemVerError,
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
# Helper Reference Functions for Model Oracles
# ==============================================================================

def _compare_identifiers(id1: str, id2: str) -> int:
    is_num1 = id1.isdigit()
    is_num2 = id2.isdigit()
    if is_num1 and is_num2:
        val1 = int(id1)
        val2 = int(id2)
        if val1 < val2:
            return -1
        elif val1 > val2:
            return 1
        return 0
    elif is_num1:
        return -1
    elif is_num2:
        return 1
    else:
        if id1 < id2:
            return -1
        elif id1 > id2:
            return 1
        return 0


def _compare_version_precedence(v1: Version, v2: Version) -> int:
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
    if v1.prerelease and v2.prerelease:
        for p1, p2 in zip(v1.prerelease, v2.prerelease):
            comp = _compare_identifiers(p1, p2)
            if comp != 0:
                return comp
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    return 0


def _model_parse_version(text: str) -> Version | Raised:
    match = re.match(
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
        r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$",
        text,
    )
    if not match:
        return Raised(InvalidVersionError(f"Invalid SemVer string: {text!r}", text))
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    prerelease_str = match.group(4)
    build_str = match.group(5)

    prerelease: Tuple[str, ...] = ()
    if prerelease_str is not None:
        parts = tuple(prerelease_str.split("."))
        for part in parts:
            if part.isdigit() and len(part) > 1 and part.startswith("0"):
                return Raised(InvalidVersionError(f"Leading zero in prerelease: {part!r}", text))
        prerelease = parts

    build: Tuple[str, ...] = ()
    if build_str is not None:
        build = tuple(build_str.split("."))

    return Version(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)


def _model_parse_range(text: str) -> VersionRange | Raised:
    trimmed = text.strip()
    if not trimmed:
        return Raised(InvalidRangeError("Empty range expression", text))
    if "," in text:
        return Raised(InvalidRangeError("Commas are not permitted in range expressions", text))
    if re.search(r"(?<!\|)\|(?!\|)", text):
        return Raised(InvalidRangeError("Single pipe delimiters are not permitted", text))
    clauses = [c.strip() for c in trimmed.split("||")]
    if any(not c for c in clauses):
        return Raised(InvalidRangeError("Empty union clause in range expression", text))
    for clause in clauses:
        if " - " in clause:
            parts = clause.split(" - ")
            if len(parts) != 2:
                return Raised(InvalidRangeError("Malformed hyphen expression", text))
            if not parts[0].strip() or not parts[1].strip():
                return Raised(InvalidRangeError("Malformed hyphen expression missing boundary", text))
            for p in (parts[0].strip(), parts[1].strip()):
                if re.match(r"^(\d+|\d+\.\d+)$", p):
                    return Raised(InvalidRangeError(f"Bare partial version lacking wildcard in hyphen: {p}", text))
            v1 = _model_parse_version(parts[0].strip())
            v2 = _model_parse_version(parts[1].strip())
            if isinstance(v1, Raised) or isinstance(v2, Raised):
                return Raised(InvalidRangeError("Invalid version in hyphen expression", text))
            continue
        if clause.startswith("- ") or clause.endswith(" -"):
            return Raised(InvalidRangeError("Malformed hyphen expression", text))

        normalized = re.sub(r"(==|=|!=|<=|>=|<|>|\^|~)\s+", r"\1", clause)
        tokens = normalized.split()
        for token in tokens:
            if token in (">=", "<=", ">", "<", "==", "!=", "=", "^", "~"):
                return Raised(InvalidRangeError(f"Missing target for operator: {token}", text))

            m = re.match(r"^(==|=|!=|<=|>=|<|>|\^|~)?(.*)$", token)
            if not m:
                return Raised(InvalidRangeError(f"Malformed token: {token}", text))
            op, target = m.group(1), m.group(2)
            if not target:
                return Raised(InvalidRangeError(f"Missing target after operator in token: {token}", text))

            is_wildcard = target in ("*", "x", "X") or bool(
                re.match(r"^\d+\.(x|\*)$", target) or re.match(r"^\d+\.\d+\.(x|\*)$", target)
            )
            if is_wildcard:
                continue

            if re.match(r"^\^?0\.0$", target) or re.match(r"^\d+(\.\d+)?$", target):
                return Raised(InvalidRangeError(f"Bare partial version lacking wildcard: {token}", text))

            parsed_v = _model_parse_version(target)
            if isinstance(parsed_v, Raised):
                return Raised(InvalidRangeError(f"Invalid embedded version: {target}", text))

    return VersionRange(raw_text=trimmed)


def _evaluate_single_comparator(version: Version, comp: str, include_prerelease: bool) -> bool:
    comp = comp.strip()
    if not comp or comp in ("*", "x", "X"):
        return not version.is_prerelease or include_prerelease

    m = re.match(r"^(==|=|!=|<=|>=|<|>|\^|~)?\s*(.*)$", comp)
    if not m:
        return False
    op = m.group(1) or "=="
    target_str = m.group(2).strip()

    if target_str in ("*", "x", "X"):
        if op in ("<", ">", "!="):
            return False
        return not version.is_prerelease or include_prerelease

    m_major = re.match(r"^(\d+)\.(x|\*)$", target_str)
    if m_major:
        major = int(m_major.group(1))
        if op in ("==", "="):
            return _compare_version_precedence(version, Version(major, 0, 0)) >= 0 and \
                   _compare_version_precedence(version, Version(major + 1, 0, 0)) < 0
        elif op == "!=":
            return _compare_version_precedence(version, Version(major, 0, 0)) < 0 or \
                   _compare_version_precedence(version, Version(major + 1, 0, 0)) >= 0
        elif op == ">=":
            return _compare_version_precedence(version, Version(major, 0, 0)) >= 0
        elif op == "<=":
            return _compare_version_precedence(version, Version(major + 1, 0, 0)) < 0
        elif op == ">":
            return _compare_version_precedence(version, Version(major + 1, 0, 0)) >= 0
        elif op == "<":
            return _compare_version_precedence(version, Version(major, 0, 0)) < 0
        elif op == "^":
            upper_major = major + 1 if major > 0 else 1
            return _compare_version_precedence(version, Version(major, 0, 0)) >= 0 and \
                   _compare_version_precedence(version, Version(upper_major, 0, 0)) < 0
        elif op == "~":
            return _compare_version_precedence(version, Version(major, 0, 0)) >= 0 and \
                   _compare_version_precedence(version, Version(major + 1, 0, 0)) < 0

    m_minor = re.match(r"^(\d+)\.(\d+)\.(x|\*)$", target_str)
    if m_minor:
        major = int(m_minor.group(1))
        minor = int(m_minor.group(2))
        if op in ("==", "="):
            return _compare_version_precedence(version, Version(major, minor, 0)) >= 0 and \
                   _compare_version_precedence(version, Version(major, minor + 1, 0)) < 0
        elif op == "!=":
            return _compare_version_precedence(version, Version(major, minor, 0)) < 0 or \
                   _compare_version_precedence(version, Version(major, minor + 1, 0)) >= 0
        elif op == ">=":
            return _compare_version_precedence(version, Version(major, minor, 0)) >= 0
        elif op == "<=":
            return _compare_version_precedence(version, Version(major, minor + 1, 0)) < 0
        elif op == ">":
            return _compare_version_precedence(version, Version(major, minor + 1, 0)) >= 0
        elif op == "<":
            return _compare_version_precedence(version, Version(major, minor, 0)) < 0
        elif op == "^":
            lower = Version(major, minor, 0)
            if major > 0:
                upper = Version(major + 1, 0, 0)
            elif minor > 0:
                upper = Version(0, minor + 1, 0)
            else:
                upper = Version(0, 1, 0)
            return _compare_version_precedence(version, lower) >= 0 and \
                   _compare_version_precedence(version, upper) < 0
        elif op == "~":
            return _compare_version_precedence(version, Version(major, minor, 0)) >= 0 and \
                   _compare_version_precedence(version, Version(major, minor + 1, 0)) < 0

    if op == "^":
        target_v = _model_parse_version(target_str)
        if not isinstance(target_v, Version):
            return False
        if target_v.major > 0:
            upper = Version(target_v.major + 1, 0, 0)
        elif target_v.minor > 0:
            upper = Version(0, target_v.minor + 1, 0)
        else:
            upper = Version(0, 0, target_v.patch + 1)
        return _compare_version_precedence(version, target_v) >= 0 and \
               _compare_version_precedence(version, upper) < 0

    if op == "~":
        target_v = _model_parse_version(target_str)
        if not isinstance(target_v, Version):
            return False
        upper = Version(target_v.major, target_v.minor + 1, 0)
        return _compare_version_precedence(version, target_v) >= 0 and \
               _compare_version_precedence(version, upper) < 0

    target_v = _model_parse_version(target_str)
    if not isinstance(target_v, Version):
        return False
    cmp = _compare_version_precedence(version, target_v)
    if op in ("==", "="):
        return cmp == 0
    elif op == "!=":
        return cmp != 0
    elif op == "<":
        return cmp < 0
    elif op == "<=":
        return cmp <= 0
    elif op == ">":
        return cmp > 0
    elif op == ">=":
        return cmp >= 0

    return False



def _model_satisfies(version: Version, range_constraint: VersionRange, include_prerelease: bool = False) -> bool:
    raw = range_constraint.raw_text.strip()
    if version.is_prerelease and not include_prerelease:
        v_target = f"{version.major}.{version.minor}.{version.patch}"
        if not (v_target in raw and version.prerelease and version.prerelease[0] in raw):
            return False

    clauses = [c.strip() for c in raw.split("||")]
    for clause in clauses:
        if not clause:
            continue
        if " - " in clause:
            h_parts = clause.split(" - ")
            if len(h_parts) == 2:
                v_low = _model_parse_version(h_parts[0].strip())
                v_high = _model_parse_version(h_parts[1].strip())
                if isinstance(v_low, Version) and isinstance(v_high, Version):
                    if _compare_version_precedence(version, v_low) >= 0 and _compare_version_precedence(version, v_high) <= 0:
                        return True
                    continue
        normalized = re.sub(r"(==|=|!=|<=|>=|<|>|\^|~)\s+", r"\1", clause)
        terms = normalized.split()
        if terms and all(_evaluate_single_comparator(version, term, include_prerelease) for term in terms):
            return True
    return False


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""
    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)
    parsed_versions: dict[str, Version] = field(default_factory=dict)
    parsed_ranges: dict[str, VersionRange] = field(default_factory=dict)
    initialized: bool = True


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    def _add_release(self, release: PackageRelease) -> None:
        releases = self.state.packages.setdefault(release.name, [])
        for i, r in enumerate(releases):
            if r.version == release.version:
                releases[i] = release
                break
        else:
            releases.append(release)
        releases.sort(
            key=lambda r: (r.version.major, r.version.minor, r.version.patch),
            reverse=True,
        )

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        ctx: TransitionContext[VersionEngine, [str], Version],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: st.sampled_from(['1.0.0', '2.1.3', '0.1.0', '1.0.0-alpha.1', '1.0.0-beta+exp.sha.5114f85', '0.0.1', '3.0.0-rc.2+20261028']), validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text: _model_parse_version(text))
        ctx.ensures(
            lambda res, target, check, text: (
                check(isinstance(res, Version), "parse_version must return a Version instance"),
                check(res.major >= 0 and res.minor >= 0 and res.patch >= 0, "Components must be non-negative"),
                check.equal(res.is_prerelease, len(res.prerelease) > 0, "is_prerelease matches prerelease tuple"),
                check.equal(res.format(), str(res), "format() matches __str__()"),
                check.equal(target.compare_precedence(res, res), 0, "Reflexive precedence comparison"),
            )
        )
        ctx.update(
            lambda res, text: (
                self.state.parsed_versions.update({text: res})
                if isinstance(res, Version)
                else None
            )
        )

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [Version, Version], int],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    v1=Domain(strategy=lambda: st.sampled_from([Version(1, 0, 0), Version(1, 0, 0, prerelease=('alpha',)), Version(1, 2, 3), Version(2, 0, 0), Version(1, 0, 0, prerelease=('alpha', '1')), Version(1, 0, 0, prerelease=('beta',))]), validator=lambda v1: isinstance(v1, Version)),
                    v2=Domain(strategy=lambda: st.sampled_from([Version(1, 0, 0), Version(2, 0, 0), Version(1, 0, 0, prerelease=('alpha',)), Version(1, 2, 3), Version(1, 0, 0, prerelease=('beta',))]), validator=lambda v2: isinstance(v2, Version)),
                )
        ctx.returns(lambda v1, v2: _compare_version_precedence(v1, v2))
        ctx.ensures(
            lambda res, target, check, v1, v2: (
                check(isinstance(res, int), "compare_precedence must return int"),
                check.equal(target.compare_precedence(v1, v1), 0, "Reflexive comparison"),
                check.equal(
                    1 if res > 0 else (-1 if res < 0 else 0),
                    _compare_version_precedence(v1, v2),
                    "Matches model precedence",
                ),
            )
        )
        ctx.update(lambda res, v1, v2: None)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[VersionEngine, [str], VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: st.sampled_from(['>=1.0.0', '^1.2.3', '~2.0.0', '1.0.0 - 2.0.0', '*', '1.x', '>=1.0.0 <2.0.0', '>=1.0.0 || <0.5.0']), validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text: _model_parse_range(text))
        ctx.ensures(
            lambda res, target, check, text: (
                check(isinstance(res, VersionRange), "parse_range must return a VersionRange"),
                check.equal(res.raw_text, text.strip(), "Stores trimmed expression in raw_text"),
                check.equal(str(res), res.raw_text, "__str__() matches raw_text"),
            )
        )
        ctx.update(
            lambda res, text: (
                self.state.parsed_ranges.update({text: res})
                if isinstance(res, VersionRange)
                else None
            )
        )

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [Version, VersionRange, bool], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    version=Domain(strategy=lambda: st.sampled_from([Version(1, 0, 0), Version(1, 2, 3), Version(2, 0, 0), Version(1, 0, 0, prerelease=('alpha',))]), validator=lambda version: isinstance(version, Version)),
                    range_constraint=Domain(strategy=lambda: st.sampled_from([VersionRange('>=1.0.0'), VersionRange('^1.0.0'), VersionRange('*'), VersionRange('1.0.0 - 2.0.0')]), validator=lambda range_constraint: isinstance(range_constraint, VersionRange)),
                    include_prerelease=Domain(strategy=lambda: st.booleans(), validator=lambda include_prerelease: isinstance(include_prerelease, bool)),
                )
        ctx.returns(
            lambda version, range_constraint, include_prerelease=False: _model_satisfies(
                version, range_constraint, include_prerelease
            )
        )
        ctx.ensures(
            lambda res, target, check, version, range_constraint, include_prerelease=False: (
                check(isinstance(res, bool), "satisfies must return bool"),
                (
                    check.equal(res, False, "Prerelease rejected without include_prerelease")
                    if version.is_prerelease
                    and not include_prerelease
                    and not (
                        f"{version.major}.{version.minor}.{version.patch}" in range_constraint.raw_text
                        and version.prerelease
                        and version.prerelease[0] in range_constraint.raw_text
                    )
                    else None
                ),
                (
                    check.equal(res, True, "Wildcard or >=0.0.0 satisfies normal version")
                    if range_constraint.raw_text in ("*", ">=0.0.0") and not version.is_prerelease
                    else None
                ),
                check.equal(
                    res,
                    _model_satisfies(version, range_constraint, include_prerelease),
                    "satisfies must evaluate correctly for both satisfied and unsatisfied constraints",
                ),
            )
        )
        ctx.update(lambda res, version, range_constraint, include_prerelease=False: None)

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [PackageRelease], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(release=Domain(strategy=lambda: st.builds(PackageRelease, name=st.sampled_from(['pkg_a', 'pkg_b', 'pkg_c', 'lib_x', 'lib_y']), version=st.sampled_from([Version(1, 0, 0), Version(1, 1, 0), Version(2, 0, 0)]), dependencies=st.sampled_from([(), (PackageDependency('pkg_b', VersionRange('>=1.0.0')),)])), validator=lambda release: isinstance(release, PackageRelease)))
        ctx.returns(lambda release: None)
        ctx.ensures(
            lambda res, target, check, release: (
                check(target.has_package(release.name), "Repository must have registered package"),
                check(release.name in target.all_packages(), "all_packages contains registered package"),
                check(
                    any(
                        r.version == release.version and r.dependencies == release.dependencies
                        for r in target.get_releases(release.name)
                    ),
                    "get_releases includes registered release with current dependencies",
                ),
            )
        )
        ctx.update(lambda res, release: self._add_release(release))

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain(strategy=lambda: st.sampled_from(['pkg_a', 'pkg_b', 'pkg_c', 'lib_x', 'lib_y']), validator=lambda name: isinstance(name, str)))
        ctx.returns(
            lambda name: (
                list(self.state.packages[name])
                if name in self.state.packages
                else Raised(PackageNotFoundError(f"Package '{name}' not found", name))
            )
        )
        ctx.ensures(
            lambda res, target, check, name: (
                check(isinstance(res, list), "get_releases must return list"),
                check(target.has_package(name), "has_package is True for package with releases"),
                check(name in target.all_packages(), "package is in all_packages"),
                check(all(r.name == name for r in res), "All releases match queried package name"),
                check(
                    all(
                        (
                            target.compare_precedence(res[i].version, res[i + 1].version) >= 0
                            if hasattr(target, "compare_precedence")
                            else _compare_version_precedence(res[i].version, res[i + 1].version) >= 0
                        )
                        for i in range(len(res) - 1)
                    ),
                    "Releases must be ordered by descending version precedence",
                ),
            )
        )
        ctx.update(lambda res, name: None)

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain(strategy=lambda: st.sampled_from(['pkg_a', 'pkg_b', 'pkg_c', 'lib_x', 'nonexistent_pkg']), validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name: name in self.state.packages)
        ctx.ensures(
            lambda res, target, check, name: (
                check(isinstance(res, bool), "has_package must return bool"),
                check.equal(res, name in target.all_packages(), "has_package parity with all_packages"),
            )
        )
        ctx.update(lambda res, name: None)

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
        ctx: TransitionContext[PackageRepository, [], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda: set(self.state.packages.keys()))
        ctx.ensures(
            lambda res, target, check: (
                check(isinstance(res, set), "all_packages must return a set"),
                check(all(target.has_package(name) for name in res), "has_package True for all all_packages entries"),
            )
        )
        ctx.update(lambda res: None)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[DependencySolver, [Collection[PackageDependency]], ResolutionOutcome],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: st.sampled_from([[], [PackageDependency('pkg_a', VersionRange('>=1.0.0'))], [PackageDependency('pkg_b', VersionRange('>=1.0.0'))]]), validator=lambda root_dependencies: isinstance(root_dependencies, (list, tuple, set))))
        ctx.returns(
            lambda root_dependencies: (
                Raised(
                    ResolutionConflictError(
                        "Missing packages",
                        tuple(d.name for d in root_dependencies if d.name not in self.state.packages),
                        "Unregistered packages",
                    )
                )
                if any(d.name not in self.state.packages for d in root_dependencies)
                else ResolutionOutcome(
                    selected_versions={
                        d.name: self.state.packages[d.name][0].version
                        for d in root_dependencies
                        if self.state.packages.get(d.name)
                    },
                    derivation_steps=tuple(
                        f"Assign '{d.name}'"
                        for d in root_dependencies
                        if self.state.packages.get(d.name)
                    ),
                )
            )
        )
        ctx.ensures(
            lambda res, target, check, root_dependencies: (
                check(isinstance(res, ResolutionOutcome), "resolve must return ResolutionOutcome"),
                check(hasattr(res.selected_versions, "__getitem__"), "selected_versions is mapping"),
                check(isinstance(res.derivation_steps, tuple), "derivation_steps is tuple"),
                check(
                    all(dep.name in res.selected_versions for dep in root_dependencies),
                    "All root dependencies must be assigned",
                ),
                check(
                    all(
                        (
                            target.satisfies(res.selected_versions[dep.name], dep.range_constraint)
                            if hasattr(target, "satisfies")
                            else _model_satisfies(res.selected_versions[dep.name], dep.range_constraint)
                        )
                        for dep in root_dependencies
                    ),
                    "Assigned versions must satisfy root dependencies",
                ),
                check(
                    all(
                        (
                            target.has_package(pkg)
                            if hasattr(target, "has_package")
                            else True
                        )
                        for pkg in res.selected_versions
                    ),
                    "Assigned packages must exist in repository",
                ),
            )
        )
        ctx.update(lambda res, root_dependencies: None)


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

proto = SemverSolverStateMachine()


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
        self.assertEqual(len(self.state.packages), 0)

    def test_fake_parse_version_valid(self) -> None:
        res = self.versionengine.parse_version("1.2.3")
        self.assertEqual(res.major, 1)
        self.assertEqual(res.minor, 2)
        self.assertEqual(res.patch, 3)
        self.assertIn("1.2.3", self.state.parsed_versions)

    def test_fake_parse_version_prerelease(self) -> None:
        res = self.versionengine.parse_version("2.0.0-alpha.1+build.42")
        self.assertEqual(res.prerelease, ("alpha", "1"))
        self.assertEqual(res.build, ("build", "42"))
        self.assertTrue(res.is_prerelease)

    def test_fake_parse_version_invalid_raises(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.0.0")

    def test_fake_compare_precedence(self) -> None:
        v1 = Version(1, 0, 0)
        v2 = Version(2, 0, 0)
        self.assertLess(self.versionengine.compare_precedence(v1, v2), 0)
        self.assertGreater(self.versionengine.compare_precedence(v2, v1), 0)
        self.assertEqual(self.versionengine.compare_precedence(v1, v1), 0)

    def test_fake_compare_precedence_prerelease(self) -> None:
        v_norm = Version(1, 0, 0)
        v_pre = Version(1, 0, 0, prerelease=("alpha",))
        self.assertGreater(self.versionengine.compare_precedence(v_norm, v_pre), 0)

    def test_fake_parse_range_valid(self) -> None:
        res = self.versionengine.parse_range("  >=1.0.0 <2.0.0  ")
        self.assertEqual(res.raw_text, ">=1.0.0 <2.0.0")
        self.assertIn("  >=1.0.0 <2.0.0  ", self.state.parsed_ranges)

    def test_fake_parse_range_invalid_raises(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("   ")

    def test_fake_satisfies(self) -> None:
        v = Version(1, 5, 0)
        r = VersionRange(">=1.0.0")
        self.assertTrue(self.versionengine.satisfies(v, r, False))

    def test_fake_package_repository_lifecycle(self) -> None:
        rel1 = PackageRelease("pkg_a", Version(1, 0, 0))
        rel2 = PackageRelease("pkg_a", Version(2, 0, 0))
        self.packagerepository.register_package(rel1)
        self.packagerepository.register_package(rel2)
        self.assertTrue(self.packagerepository.has_package("pkg_a"))
        self.assertIn("pkg_a", self.packagerepository.all_packages())
        releases = self.packagerepository.get_releases("pkg_a")
        self.assertEqual(len(releases), 2)
        self.assertEqual(releases[0].version, Version(2, 0, 0))

    def test_fake_get_releases_missing_raises(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("nonexistent")

    def test_fake_has_package_false(self) -> None:
        self.assertFalse(self.packagerepository.has_package("missing_pkg"))

    def test_fake_resolve_success(self) -> None:
        rel = PackageRelease("pkg_a", Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        dep = PackageDependency("pkg_a", VersionRange(">=1.0.0"))
        outcome = self.dependencysolver.resolve([dep])
        self.assertEqual(outcome.selected_versions["pkg_a"], Version(1, 0, 0))

    def test_fake_resolve_missing_raises_conflict(self) -> None:
        dep = PackageDependency("unknown_pkg", VersionRange(">=1.0.0"))
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve([dep])

    def test_fake_parse_version_leading_zero_prerelease(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-01")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-alpha.01")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-00")

    def test_fake_compare_precedence_patch_diff(self) -> None:
        v1 = Version(1, 0, 1)
        v2 = Version(1, 0, 2)
        self.assertLess(self.versionengine.compare_precedence(v1, v2), 0)
        self.assertGreater(self.versionengine.compare_precedence(v2, v1), 0)

    def test_fake_compare_precedence_mixed_numeric_string_prerelease(self) -> None:
        v_num = Version(1, 0, 0, prerelease=("1",))
        v_str = Version(1, 0, 0, prerelease=("alpha",))
        self.assertLess(self.versionengine.compare_precedence(v_num, v_str), 0)
        self.assertGreater(self.versionengine.compare_precedence(v_str, v_num), 0)

    def test_fake_compare_precedence_common_prefix_different_length(self) -> None:
        v_short = Version(1, 0, 0, prerelease=("alpha",))
        v_long = Version(1, 0, 0, prerelease=("alpha", "1"))
        self.assertLess(self.versionengine.compare_precedence(v_short, v_long), 0)
        self.assertGreater(self.versionengine.compare_precedence(v_long, v_short), 0)

    def test_fake_parse_range_whitespace_and_wildcards(self) -> None:
        r1 = self.versionengine.parse_range(">= 1.0.0")
        self.assertEqual(r1.raw_text, ">= 1.0.0")
        r2 = self.versionengine.parse_range("<=  2.0.0")
        self.assertEqual(r2.raw_text, "<=  2.0.0")
        r3 = self.versionengine.parse_range("*")
        self.assertEqual(r3.raw_text, "*")
        r4 = self.versionengine.parse_range(">=1.x")
        self.assertEqual(r4.raw_text, ">=1.x")
        r5 = self.versionengine.parse_range("<=2.0.x")
        self.assertEqual(r5.raw_text, "<=2.0.x")
        r6 = self.versionengine.parse_range(">1.*")
        self.assertEqual(r6.raw_text, ">1.*")
        r7 = self.versionengine.parse_range("<2.0.*")
        self.assertEqual(r7.raw_text, "<2.0.*")
        r8 = self.versionengine.parse_range("^0.2.3")
        self.assertEqual(r8.raw_text, "^0.2.3")
        r9 = self.versionengine.parse_range("^0.0.3")
        self.assertEqual(r9.raw_text, "^0.0.3")

    def test_fake_parse_range_syntax_errors(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0 | <2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("|")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - ")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("- 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2.0.0 - 3.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("<")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("~")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=01.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=not-a-ver")

    def test_fake_satisfies_failing_relational_inequalities(self) -> None:
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("<1.0.0"), False))
        self.assertFalse(self.versionengine.satisfies(Version(2, 0, 0), VersionRange("<1.0.0"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange(">1.0.0"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!=1.0.0"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("==2.0.0"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange(">=2.0.0"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("<=0.9.0"), False))
        self.assertFalse(self.versionengine.satisfies(Version(2, 5, 0), VersionRange("^1.0.0"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 3, 0), VersionRange("~1.2.0"), False))
        self.assertFalse(self.versionengine.satisfies(Version(3, 0, 0), VersionRange("1.0.0 - 2.0.0"), False))

    def test_fake_register_package_replaces_same_version(self) -> None:
        rel1 = PackageRelease("replace_pkg", Version(1, 0, 0), ())
        dep = PackageDependency("dep_x", VersionRange(">=1.0.0"))
        rel2 = PackageRelease("replace_pkg", Version(1, 0, 0), (dep,))
        self.packagerepository.register_package(rel1)
        self.packagerepository.register_package(rel2)
        releases = self.packagerepository.get_releases("replace_pkg")
        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0].dependencies, (dep,))

    def test_fake_compare_precedence_ascii_lexicographical_prerelease(self) -> None:
        v_alpha = Version(1, 0, 0, prerelease=("alpha",))
        v_beta = Version(1, 0, 0, prerelease=("beta",))
        v_rc = Version(1, 0, 0, prerelease=("rc",))
        self.assertLess(self.versionengine.compare_precedence(v_alpha, v_beta), 0)
        self.assertLess(self.versionengine.compare_precedence(v_beta, v_rc), 0)
        self.assertGreater(self.versionengine.compare_precedence(v_beta, v_alpha), 0)
        self.assertGreater(self.versionengine.compare_precedence(v_rc, v_beta), 0)

    def test_fake_parse_range_hyphen_bare_partial_invalid(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.3")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2.3")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1 - 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1 - 2")

    def test_fake_parse_range_wildcards_relational_and_carets(self) -> None:
        r1 = self.versionengine.parse_range("<*")
        self.assertEqual(r1.raw_text, "<*")
        r2 = self.versionengine.parse_range(">*")
        self.assertEqual(r2.raw_text, ">*")
        r3 = self.versionengine.parse_range("!=*")
        self.assertEqual(r3.raw_text, "!=*")
        r4 = self.versionengine.parse_range("<x")
        self.assertEqual(r4.raw_text, "<x")
        r5 = self.versionengine.parse_range(">x")
        self.assertEqual(r5.raw_text, ">x")
        r6 = self.versionengine.parse_range("!=x")
        self.assertEqual(r6.raw_text, "!=x")
        r7 = self.versionengine.parse_range("<=1.x")
        self.assertEqual(r7.raw_text, "<=1.x")
        r8 = self.versionengine.parse_range("<1.x")
        self.assertEqual(r8.raw_text, "<1.x")
        r9 = self.versionengine.parse_range("<=1.*")
        self.assertEqual(r9.raw_text, "<=1.*")
        r10 = self.versionengine.parse_range("<1.*")
        self.assertEqual(r10.raw_text, "<1.*")
        r11 = self.versionengine.parse_range(">=1.2.x")
        self.assertEqual(r11.raw_text, ">=1.2.x")
        r12 = self.versionengine.parse_range(">1.2.x")
        self.assertEqual(r12.raw_text, ">1.2.x")
        r13 = self.versionengine.parse_range(">=1.2.*")
        self.assertEqual(r13.raw_text, ">=1.2.*")
        r14 = self.versionengine.parse_range(">1.2.*")
        self.assertEqual(r14.raw_text, ">1.2.*")
        r15 = self.versionengine.parse_range("^1.2.x")
        self.assertEqual(r15.raw_text, "^1.2.x")
        r16 = self.versionengine.parse_range("^0.2.x")
        self.assertEqual(r16.raw_text, "^0.2.x")
        r17 = self.versionengine.parse_range("^0.0.x")
        self.assertEqual(r17.raw_text, "^0.0.x")
        r18 = self.versionengine.parse_range("^1.2.*")
        self.assertEqual(r18.raw_text, "^1.2.*")
        r19 = self.versionengine.parse_range("^0.2.*")
        self.assertEqual(r19.raw_text, "^0.2.*")
        r20 = self.versionengine.parse_range("^0.0.*")
        self.assertEqual(r20.raw_text, "^0.0.*")

    def test_fake_satisfies_wildcards_and_carets(self) -> None:
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("<*"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange(">*"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!=*"), False))
        self.assertTrue(self.versionengine.satisfies(Version(1, 5, 0), VersionRange("<=1.x"), False))
        self.assertFalse(self.versionengine.satisfies(Version(2, 0, 0), VersionRange("<=1.x"), False))
        self.assertTrue(self.versionengine.satisfies(Version(0, 9, 0), VersionRange("<1.x"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("<1.x"), False))
        self.assertTrue(self.versionengine.satisfies(Version(1, 2, 5), VersionRange(">=1.2.x"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 1, 9), VersionRange(">=1.2.x"), False))
        self.assertTrue(self.versionengine.satisfies(Version(1, 3, 0), VersionRange(">1.2.x"), False))
        self.assertFalse(self.versionengine.satisfies(Version(1, 2, 9), VersionRange(">1.2.x"), False))
        self.assertTrue(self.versionengine.satisfies(Version(1, 5, 0), VersionRange("^1.2.x"), False))
        self.assertFalse(self.versionengine.satisfies(Version(2, 0, 0), VersionRange("^1.2.x"), False))
        self.assertTrue(self.versionengine.satisfies(Version(0, 2, 5), VersionRange("^0.2.x"), False))
        self.assertFalse(self.versionengine.satisfies(Version(0, 3, 0), VersionRange("^0.2.x"), False))
        self.assertTrue(self.versionengine.satisfies(Version(0, 0, 5), VersionRange("^0.0.x"), False))
        self.assertFalse(self.versionengine.satisfies(Version(0, 1, 0), VersionRange("^0.0.x"), False))


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
        self.sm = SemverSolverStateMachine(
            singletons={
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_parse_version_standard(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.2.3")
        self.sm.dispatch_transition("parse_version", "0.0.1")
        self.sm.dispatch_transition("parse_version", "10.20.30")

    def test_real_parse_version_prerelease_and_build(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.0.0-alpha.1")
        self.sm.dispatch_transition("parse_version", "1.0.0+20130313144700")
        self.sm.dispatch_transition("parse_version", "1.0.0-beta+exp.sha.5114f85")
        self.sm.dispatch_transition("parse_version", "2.0.0-rc.1.2.3")

    def test_real_parse_version_invalid(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.0.0")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.02.0")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.03")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("v1.0.0")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("not-a-semver")

    def test_real_compare_precedence_numeric(self) -> None:
        v1 = Version(1, 0, 0)
        v2 = Version(2, 0, 0)
        self.sm.dispatch_transition("compare_precedence", v1, v2)
        self.sm.dispatch_transition("compare_precedence", v2, v1)
        self.sm.dispatch_transition("compare_precedence", v1, v1)

    def test_real_compare_precedence_prerelease(self) -> None:
        v_norm = Version(1, 0, 0)
        v_pre = Version(1, 0, 0, prerelease=("alpha",))
        self.sm.dispatch_transition("compare_precedence", v_norm, v_pre)
        self.sm.dispatch_transition("compare_precedence", v_pre, v_norm)
        v_pre1 = Version(1, 0, 0, prerelease=("alpha", "1"))
        v_pre2 = Version(1, 0, 0, prerelease=("alpha", "2"))
        self.sm.dispatch_transition("compare_precedence", v_pre1, v_pre2)
        v_build1 = Version(1, 0, 0, build=("build1",))
        v_build2 = Version(1, 0, 0, build=("build2",))
        self.sm.dispatch_transition("compare_precedence", v_build1, v_build2)

    def test_real_parse_range_expressions(self) -> None:
        self.sm.dispatch_transition("parse_range", ">=1.0.0")
        self.sm.dispatch_transition("parse_range", "^1.2.3")
        self.sm.dispatch_transition("parse_range", "~2.0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0")
        self.sm.dispatch_transition("parse_range", "*")
        self.sm.dispatch_transition("parse_range", "1.x")
        self.sm.dispatch_transition("parse_range", "1.0.x")
        self.sm.dispatch_transition("parse_range", ">=1.0.0 <2.0.0 || >=3.0.0")

    def test_real_parse_range_invalid(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("    ")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0, <2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("|| >=1.0.0")

    def test_real_satisfies_evaluation(self) -> None:
        v = Version(1, 5, 0)
        r1 = VersionRange(">=1.0.0 <2.0.0")
        self.sm.dispatch_transition("satisfies", v, r1, False)
        r2 = VersionRange("^1.0.0")
        self.sm.dispatch_transition("satisfies", v, r2, False)
        v_pre = Version(1, 5, 0, prerelease=("alpha", "1"))
        self.sm.dispatch_transition("satisfies", v_pre, r1, False)
        self.sm.dispatch_transition("satisfies", v_pre, r1, True)

    def test_real_package_repository_operations(self) -> None:
        self.sm.dispatch_transition("all_packages")
        rel1 = PackageRelease("demo_lib", Version(1, 0, 0))
        rel2 = PackageRelease("demo_lib", Version(1, 2, 0))
        rel3 = PackageRelease("other_lib", Version(0, 1, 0))
        self.sm.dispatch_transition("register_package", rel1)
        self.sm.dispatch_transition("register_package", rel2)
        self.sm.dispatch_transition("register_package", rel3)
        self.sm.dispatch_transition("has_package", "demo_lib")
        self.sm.dispatch_transition("has_package", "unknown")
        self.sm.dispatch_transition("get_releases", "demo_lib")
        self.sm.dispatch_transition("all_packages")

    def test_real_package_repository_missing(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("missing_package")

    def test_real_solver_resolution(self) -> None:
        dep_b = PackageDependency("dep_b", VersionRange(">=1.0.0"))
        rel_a = PackageRelease("app_a", Version(1, 0, 0), (dep_b,))
        rel_b1 = PackageRelease("dep_b", Version(1, 0, 0))
        rel_b2 = PackageRelease("dep_b", Version(1, 1, 0))
        self.sm.dispatch_transition("register_package", rel_a)
        self.sm.dispatch_transition("register_package", rel_b1)
        self.sm.dispatch_transition("register_package", rel_b2)
        root_dep = PackageDependency("app_a", VersionRange(">=1.0.0"))
        self.sm.dispatch_transition("resolve", [root_dep])

    def test_real_solver_conflict_unregistered_package(self) -> None:
        root_dep = PackageDependency("unregistered", VersionRange(">=1.0.0"))
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve([root_dep])

    def test_real_solver_conflict_incompatible_ranges(self) -> None:
        rel_a1 = PackageRelease("pkg_a", Version(1, 0, 0), (PackageDependency("common", VersionRange("==1.0.0")),))
        rel_b1 = PackageRelease("pkg_b", Version(1, 0, 0), (PackageDependency("common", VersionRange("==2.0.0")),))
        rel_c1 = PackageRelease("common", Version(1, 0, 0))
        rel_c2 = PackageRelease("common", Version(2, 0, 0))
        self.sm.dispatch_transition("register_package", rel_a1)
        self.sm.dispatch_transition("register_package", rel_b1)
        self.sm.dispatch_transition("register_package", rel_c1)
        self.sm.dispatch_transition("register_package", rel_c2)
        root_deps = [
            PackageDependency("pkg_a", VersionRange(">=1.0.0")),
            PackageDependency("pkg_b", VersionRange(">=1.0.0")),
        ]
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(root_deps)

    def test_real_parse_version_leading_zero_prerelease(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-01")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-alpha.01")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-00")

    def test_real_compare_precedence_patch_diff(self) -> None:
        v1 = Version(1, 0, 1)
        v2 = Version(1, 0, 2)
        self.sm.dispatch_transition("compare_precedence", v1, v2)
        self.sm.dispatch_transition("compare_precedence", v2, v1)

    def test_real_compare_precedence_mixed_numeric_string_prerelease(self) -> None:
        v_num = Version(1, 0, 0, prerelease=("1",))
        v_str = Version(1, 0, 0, prerelease=("alpha",))
        self.sm.dispatch_transition("compare_precedence", v_num, v_str)
        self.sm.dispatch_transition("compare_precedence", v_str, v_num)

    def test_real_compare_precedence_common_prefix_different_length(self) -> None:
        v_short = Version(1, 0, 0, prerelease=("alpha",))
        v_long = Version(1, 0, 0, prerelease=("alpha", "1"))
        self.sm.dispatch_transition("compare_precedence", v_short, v_long)
        self.sm.dispatch_transition("compare_precedence", v_long, v_short)

    def test_real_parse_range_whitespace_and_wildcards(self) -> None:
        self.sm.dispatch_transition("parse_range", ">= 1.0.0")
        self.sm.dispatch_transition("parse_range", "<=  2.0.0")
        self.sm.dispatch_transition("parse_range", "> 1.0.0")
        self.sm.dispatch_transition("parse_range", "< 2.0.0")
        self.sm.dispatch_transition("parse_range", "*")
        self.sm.dispatch_transition("parse_range", ">=1.x")
        self.sm.dispatch_transition("parse_range", "<=2.0.x")
        self.sm.dispatch_transition("parse_range", ">1.*")
        self.sm.dispatch_transition("parse_range", "<2.0.*")
        self.sm.dispatch_transition("parse_range", "^0.2.3")
        self.sm.dispatch_transition("parse_range", "^0.0.3")

    def test_real_parse_range_syntax_errors(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0 | <2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("|")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - ")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("- 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2.0.0 - 3.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("<")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("~")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=01.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=not-a-ver")

    def test_real_satisfies_failing_relational_inequalities(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("<1.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange("<1.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange(">1.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=1.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("==2.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange(">=2.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("<=0.9.0"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 5, 0), VersionRange("^1.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 3, 0), VersionRange("~1.2.0"), False)
        self.sm.dispatch_transition("satisfies", Version(3, 0, 0), VersionRange("1.0.0 - 2.0.0"), False)

    def test_real_package_repository_replaces_same_version(self) -> None:
        rel1 = PackageRelease("replace_pkg", Version(1, 0, 0), ())
        dep = PackageDependency("dep_x", VersionRange(">=1.0.0"))
        rel2 = PackageRelease("replace_pkg", Version(1, 0, 0), (dep,))
        self.sm.dispatch_transition("register_package", rel1)
        self.sm.dispatch_transition("register_package", rel2)
        self.sm.dispatch_transition("get_releases", "replace_pkg")

    def test_real_compare_precedence_ascii_lexicographical_prerelease(self) -> None:
        v_alpha = Version(1, 0, 0, prerelease=("alpha",))
        v_beta = Version(1, 0, 0, prerelease=("beta",))
        v_rc = Version(1, 0, 0, prerelease=("rc",))
        self.sm.dispatch_transition("compare_precedence", v_alpha, v_beta)
        self.sm.dispatch_transition("compare_precedence", v_beta, v_rc)
        self.sm.dispatch_transition("compare_precedence", v_beta, v_alpha)
        self.sm.dispatch_transition("compare_precedence", v_rc, v_beta)

    def test_real_parse_range_hyphen_bare_partial_invalid(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.3")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2.3")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1 - 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1 - 2")

    def test_real_parse_range_wildcards_relational_and_carets(self) -> None:
        self.sm.dispatch_transition("parse_range", "<*")
        self.sm.dispatch_transition("parse_range", ">*")
        self.sm.dispatch_transition("parse_range", "!=*")
        self.sm.dispatch_transition("parse_range", "<x")
        self.sm.dispatch_transition("parse_range", ">x")
        self.sm.dispatch_transition("parse_range", "!=x")
        self.sm.dispatch_transition("parse_range", "<=1.x")
        self.sm.dispatch_transition("parse_range", "<1.x")
        self.sm.dispatch_transition("parse_range", "<=1.*")
        self.sm.dispatch_transition("parse_range", "<1.*")
        self.sm.dispatch_transition("parse_range", ">=1.2.x")
        self.sm.dispatch_transition("parse_range", ">1.2.x")
        self.sm.dispatch_transition("parse_range", ">=1.2.*")
        self.sm.dispatch_transition("parse_range", ">1.2.*")
        self.sm.dispatch_transition("parse_range", "^1.2.x")
        self.sm.dispatch_transition("parse_range", "^0.2.x")
        self.sm.dispatch_transition("parse_range", "^0.0.x")
        self.sm.dispatch_transition("parse_range", "^1.2.*")
        self.sm.dispatch_transition("parse_range", "^0.2.*")
        self.sm.dispatch_transition("parse_range", "^0.0.*")

    def test_real_satisfies_wildcards_and_carets(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("<*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange(">*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("<=1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange("<=1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 9, 0), VersionRange("<1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("<1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 5), VersionRange(">=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 1, 9), VersionRange(">=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 3, 0), VersionRange(">1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 9), VersionRange(">1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("^1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange("^1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 2, 5), VersionRange("^0.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 3, 0), VersionRange("^0.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 0, 5), VersionRange("^0.0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 1, 0), VersionRange("^0.0.x"), False)


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
        proto.singletons = {
            VersionEngine: self.versionengine,
            PackageRepository: self.packagerepository,
            DependencySolver: self.dependencysolver,
        }

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
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
# LAST_CLEANED: 2026-10-29T03:18:22Z
# LAST_CHANGED: 2026-10-29T03:16:20Z
# CHANGE: Add test cases and transition logic for ASCII prerelease comparison, hyphen bare partial syntax errors, bare wildcards with relational operators, major/minor wildcard upper and lower bounds, and caret expressions on minor wildcards across zero and non-zero components
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T03:18:22Z
# PRETENSE_QA_AUDIT: 2026-10-29T03:17:33Z
# --- END CLEANROOM METADATA ---
