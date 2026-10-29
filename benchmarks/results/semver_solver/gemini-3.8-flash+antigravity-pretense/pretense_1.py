"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
import re
from typing import Any, Collection, List, Mapping, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)
from benchmark_1.parts.semver_solver.lib.semver_solver import (
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


# ==============================================================================
# Specification Helpers & Reference Oracles
# ==============================================================================

_SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def _compare_identifiers(id1: str, id2: str) -> int:
    is_num1 = id1.isdigit()
    is_num2 = id2.isdigit()
    if is_num1 and is_num2:
        val1, val2 = int(id1), int(id2)
        return (val1 > val2) - (val1 < val2)
    elif is_num1:
        return -1
    elif is_num2:
        return 1
    else:
        return (id1 > id2) - (id1 < id2)


def _compare_version_precedence(v1: Version, v2: Version) -> int:
    if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
        t1 = (v1.major, v1.minor, v1.patch)
        t2 = (v2.major, v2.minor, v2.patch)
        return (t1 > t2) - (t1 < t2)

    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease and v2.prerelease:
        return 1
    if v1.prerelease and not v2.prerelease:
        return -1

    for p1, p2 in zip(v1.prerelease, v2.prerelease):
        cmp = _compare_identifiers(p1, p2)
        if cmp != 0:
            return cmp

    len1, len2 = len(v1.prerelease), len(v2.prerelease)
    return (len1 > len2) - (len1 < len2)


def _parse_version_helper(text: str) -> Version:
    m = _SEMVER_REGEX.match(text)
    if not m:
        raise InvalidVersionError(f"Invalid semantic version: {text!r}", raw_text=text)
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    prerelease: tuple[str, ...] = tuple(m.group(4).split(".")) if m.group(4) else ()
    build: tuple[str, ...] = tuple(m.group(5).split(".")) if m.group(5) else ()
    return Version(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)


def _fake_parse_version(text: str) -> Version | Raised:
    try:
        return _parse_version_helper(text)
    except InvalidVersionError as err:
        return Raised(err)


def _is_full_version(token: str) -> bool:
    return _SEMVER_REGEX.match(token) is not None


def _is_valid_range_target(token: str) -> bool:
    if token in ("*", "x", "X"):
        return True
    if re.match(r"^\d+\.(x|\*|X)$", token):
        return True
    if re.match(r"^\d+\.\d+\.(x|\*|X)$", token):
        return True
    if re.match(r"^\d+$", token) or re.match(r"^\d+\.\d+$", token):
        return False
    return _is_full_version(token)


def _is_valid_range_fake(text: str) -> bool:
    if not text or not text.strip():
        return False
    if "," in text:
        return False
    clauses = text.split("||")
    for clause in clauses:
        trimmed_clause = clause.strip()
        if not trimmed_clause:
            return False
        tokens = trimmed_clause.split()
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token == "-":
                return False
            if i + 1 < len(tokens) and tokens[i + 1] == "-":
                if i + 2 >= len(tokens):
                    return False
                left = tokens[i]
                right = tokens[i + 2]
                if re.match(r"^(>=|<=|>|<|==|=|!=|\^|~)", left) or re.match(r"^(>=|<=|>|<|==|=|!=|\^|~)", right):
                    return False
                if not _is_valid_range_target(left) or not _is_valid_range_target(right):
                    return False
                i += 3
                continue

            op_match = re.match(r"^(>=|<=|>|<|==|=|!=|\^|~)(.*)$", token)
            if op_match:
                op, rest = op_match.groups()
                if not rest:
                    if i + 1 >= len(tokens):
                        return False
                    i += 1
                    rest = tokens[i]
                if not _is_valid_range_target(rest):
                    return False
            else:
                if not _is_valid_range_target(token):
                    return False
            i += 1
    return True


def _fake_parse_range(text: str) -> VersionRange | Raised:
    if not _is_valid_range_fake(text):
        return Raised(InvalidRangeError(f"Invalid range expression: {text!r}", raw_range=text))
    return VersionRange(raw_text=text.strip())


def _satisfies_wildcard(v: Version, op: str, wildcard_str: str, include_prerelease: bool) -> bool:
    if v.is_prerelease and not include_prerelease:
        return False

    if wildcard_str in ("*", "x", "X"):
        if op in ("=", "==", "*", "x", "X", ""):
            return True
        elif op == "!=":
            return False
        elif op in (">=", "<="):
            return True
        elif op in (">", "<"):
            return False
        elif op in ("^", "~"):
            return True
        return True

    m_major = re.match(r"^(\d+)\.(x|\*|X)$", wildcard_str)
    if m_major:
        major = int(m_major.group(1))
        if op in ("=", "==", ""):
            return v.major == major
        elif op == "!=":
            return v.major != major
        elif op == ">=":
            return v.major >= major
        elif op == ">":
            return v.major > major
        elif op == "<=":
            return v.major <= major
        elif op == "<":
            return v.major < major
        elif op in ("^", "~"):
            return v.major == major
        return v.major == major

    m_minor = re.match(r"^(\d+)\.(\d+)\.(x|\*|X)$", wildcard_str)
    if m_minor:
        major = int(m_minor.group(1))
        minor = int(m_minor.group(2))
        if op in ("=", "==", ""):
            return v.major == major and v.minor == minor
        elif op == "!=":
            return not (v.major == major and v.minor == minor)
        elif op == ">=":
            return (v.major > major) or (v.major == major and v.minor >= minor)
        elif op == ">":
            return (v.major > major) or (v.major == major and v.minor > minor)
        elif op == "<=":
            return (v.major < major) or (v.major == major and v.minor <= minor)
        elif op == "<":
            return (v.major < major) or (v.major == major and v.minor < minor)
        elif op == "~":
            return v.major == major and v.minor == minor
        elif op == "^":
            if major > 0:
                return v.major == major and v.minor >= minor
            elif minor > 0:
                return v.major == 0 and v.minor == minor
            else:
                return v.major == 0 and v.minor == 0
        return v.major == major and v.minor == minor

    return False


def _satisfies_single_comparator(v: Version, op: str, target_str: str, include_prerelease: bool) -> bool:
    if target_str in ("*", "x", "X") or re.match(r"^\d+\.(x|\*|X)$", target_str) or re.match(r"^\d+\.\d+\.(x|\*|X)$", target_str):
        return _satisfies_wildcard(v, op, target_str, include_prerelease)

    target = _parse_version_helper(target_str)

    if v.is_prerelease and not include_prerelease:
        if not (target.is_prerelease and (v.major, v.minor, v.patch) == (target.major, target.minor, target.patch)):
            return False

    cmp = _compare_version_precedence(v, target)
    if op in ("=", "==", ""):
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


def _satisfies_hyphen_left(v: Version, left: str, include_prerelease: bool) -> bool:
    if left in ("*", "x", "X"):
        return True
    m_major = re.match(r"^(\d+)\.(x|\*|X)$", left)
    if m_major:
        major = int(m_major.group(1))
        return _satisfies_single_comparator(v, ">=", f"{major}.0.0", include_prerelease)
    m_minor = re.match(r"^(\d+)\.(\d+)\.(x|\*|X)$", left)
    if m_minor:
        major = int(m_minor.group(1))
        minor = int(m_minor.group(2))
        return _satisfies_single_comparator(v, ">=", f"{major}.{minor}.0", include_prerelease)
    return _satisfies_single_comparator(v, ">=", left, include_prerelease)


def _satisfies_hyphen_right(v: Version, right: str, include_prerelease: bool) -> bool:
    if right in ("*", "x", "X"):
        return True
    m_major = re.match(r"^(\d+)\.(x|\*|X)$", right)
    if m_major:
        major = int(m_major.group(1))
        return _satisfies_single_comparator(
            v, "<", f"{major + 1}.0.0-0", include_prerelease=True if v.is_prerelease else include_prerelease
        )
    m_minor = re.match(r"^(\d+)\.(\d+)\.(x|\*|X)$", right)
    if m_minor:
        major = int(m_minor.group(1))
        minor = int(m_minor.group(2))
        return _satisfies_single_comparator(
            v, "<", f"{major}.{minor + 1}.0-0", include_prerelease=True if v.is_prerelease else include_prerelease
        )
    return _satisfies_single_comparator(v, "<=", right, include_prerelease)


def _clause_targets_prerelease(clause_text: str, v: Version) -> bool:
    if not v.is_prerelease:
        return False
    for m in re.finditer(r"\b(\d+\.\d+\.\d+(?:-[0-9a-zA-Z-.]+)?)", clause_text):
        ver_str = m.group(1)
        try:
            cand = _parse_version_helper(ver_str)
            if cand.is_prerelease and (cand.major, cand.minor, cand.patch) == (v.major, v.minor, v.patch):
                return True
        except Exception:
            pass
    return False


def _eval_clause(v: Version, clause_text: str, include_prerelease: bool) -> bool:
    effective_inc_pre = include_prerelease or _clause_targets_prerelease(clause_text, v)
    tokens = clause_text.strip().split()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if i + 2 < len(tokens) and tokens[i + 1] == "-":
            left = tokens[i]
            right = tokens[i + 2]
            if not _satisfies_hyphen_left(v, left, effective_inc_pre):
                return False
            if not _satisfies_hyphen_right(v, right, effective_inc_pre):
                return False
            i += 3
            continue

        if token.startswith("^"):
            ver_str = token[1:]
            if not ver_str:
                i += 1
                ver_str = tokens[i]
            if ver_str in ("*", "x", "X") or re.match(r"^\d+\.(x|\*|X)$", ver_str) or re.match(r"^\d+\.\d+\.(x|\*|X)$", ver_str):
                if not _satisfies_wildcard(v, "^", ver_str, effective_inc_pre):
                    return False
            else:
                target = _parse_version_helper(ver_str)
                if not _satisfies_single_comparator(v, ">=", ver_str, effective_inc_pre):
                    return False
                if target.major > 0:
                    upper = f"{target.major + 1}.0.0-0"
                    if not _satisfies_single_comparator(
                        v, "<", upper, include_prerelease=True if v.is_prerelease else effective_inc_pre
                    ):
                        return False
                elif target.minor > 0:
                    upper = f"0.{target.minor + 1}.0-0"
                    if not _satisfies_single_comparator(
                        v, "<", upper, include_prerelease=True if v.is_prerelease else effective_inc_pre
                    ):
                        return False
                else:
                    upper = f"0.0.{target.patch + 1}-0"
                    if not _satisfies_single_comparator(
                        v, "<", upper, include_prerelease=True if v.is_prerelease else effective_inc_pre
                    ):
                        return False
            i += 1
            continue

        if token.startswith("~"):
            ver_str = token[1:]
            if not ver_str:
                i += 1
                ver_str = tokens[i]
            if ver_str in ("*", "x", "X") or re.match(r"^\d+\.(x|\*|X)$", ver_str) or re.match(r"^\d+\.\d+\.(x|\*|X)$", ver_str):
                if not _satisfies_wildcard(v, "~", ver_str, effective_inc_pre):
                    return False
            else:
                target = _parse_version_helper(ver_str)
                if not _satisfies_single_comparator(v, ">=", ver_str, effective_inc_pre):
                    return False
                upper = f"{target.major}.{target.minor + 1}.0-0"
                if not _satisfies_single_comparator(
                    v, "<", upper, include_prerelease=True if v.is_prerelease else effective_inc_pre
                ):
                    return False
            i += 1
            continue

        op_match = re.match(r"^(>=|<=|>|<|==|=|!=)(.*)$", token)
        if op_match:
            op, rest = op_match.groups()
            if not rest:
                i += 1
                rest = tokens[i]
            if not _satisfies_single_comparator(v, op, rest, effective_inc_pre):
                return False
        else:
            if not _satisfies_single_comparator(v, "==", token, effective_inc_pre):
                return False
        i += 1
    return True


def _eval_satisfies(v: Version, range_constraint: VersionRange, include_prerelease: bool = False) -> bool:
    clauses = range_constraint.raw_text.split("||")
    for clause in clauses:
        if _eval_clause(v, clause, include_prerelease):
            return True
    return False


def _fake_get_releases(
    state: SemverSolverState,
    name: str,
) -> list[PackageRelease] | Raised:
    if name not in state.packages:
        return Raised(PackageNotFoundError(f"Package '{name}' not found", package_name=name))
    return list(state.packages[name])


def _fake_resolve(
    state: SemverSolverState,
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome | Raised:
    if not root_dependencies:
        return ResolutionOutcome(selected_versions={}, derivation_steps=())

    selected: dict[str, Version] = {}
    derivation_steps: list[str] = []
    conflicts: list[str] = []

    queue: list[tuple[str, PackageDependency]] = [("root", dep) for dep in root_dependencies]
    visited_deps: set[tuple[str, str, str]] = set()

    while queue:
        requester, dep = queue.pop(0)
        dep_key = (requester, dep.name, dep.range_constraint.raw_text)
        if dep_key in visited_deps:
            continue
        visited_deps.add(dep_key)

        if dep.name in selected:
            assigned_ver = selected[dep.name]
            if not _eval_satisfies(assigned_ver, dep.range_constraint, False):
                conflicts.append(dep.name)
                if requester != "root":
                    conflicts.append(requester)
                continue
        else:
            if dep.name not in state.packages:
                conflicts.append(dep.name)
                if requester != "root":
                    conflicts.append(requester)
                continue

            matching = [
                r for r in state.packages[dep.name]
                if _eval_satisfies(r.version, dep.range_constraint, False)
            ]
            if not matching:
                conflicts.append(dep.name)
                if requester != "root":
                    conflicts.append(requester)
                continue

            chosen_rel = matching[0]
            selected[dep.name] = chosen_rel.version
            derivation_steps.append(f"Assign '{dep.name}' to {chosen_rel.version}")

            for trans_dep in chosen_rel.dependencies:
                queue.append((dep.name, trans_dep))

    if conflicts:
        return Raised(
            ResolutionConflictError(
                f"Dependency resolution conflict for: {', '.join(conflicts)}",
                conflicting_packages=tuple(sorted(set(conflicts))),
                explanation=f"No viable release satisfying constraints for {conflicts}",
            )
        )
    return ResolutionOutcome(selected_versions=selected, derivation_steps=tuple(derivation_steps))


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""
    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    def _record_package_release(self, release: PackageRelease) -> None:
        existing = [r for r in self.state.packages.get(release.name, []) if r.version != release.version]
        existing.append(release)
        existing.sort(key=lambda r: cmp_to_key(_compare_version_precedence)(r.version), reverse=True)
        self.state.packages[release.name] = existing

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        ctx: TransitionContext[VersionEngine, [str], Version],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(text=Domain(strategy=lambda: '1.0.0', validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text: _fake_parse_version(text))
        ctx.ensures(
            lambda res, target, check, text: (
                check(res.major >= 0, "major must be non-negative"),
                check(res.minor >= 0, "minor must be non-negative"),
                check(res.patch >= 0, "patch must be non-negative"),
                check.equal(res.is_prerelease, len(res.prerelease) > 0),
                check.equal(res, _parse_version_helper(text)),
            )
        )
        ctx.update(lambda res, text: None)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [Version, Version], int],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(
                    v1=Domain(strategy=lambda: Version(1, 0, 0), validator=lambda v1: isinstance(v1, Version)),
                    v2=Domain(strategy=lambda: Version(2, 0, 0), validator=lambda v2: isinstance(v2, Version)),
                )
        ctx.returns(lambda v1, v2: _compare_version_precedence(v1, v2))
        ctx.ensures(
            lambda res, target, check, v1, v2: (
                check(
                    (res < 0 and _compare_version_precedence(v1, v2) < 0)
                    or (res == 0 and _compare_version_precedence(v1, v2) == 0)
                    or (res > 0 and _compare_version_precedence(v1, v2) > 0),
                    f"compare_precedence sign mismatch against reference oracle: {res}",
                ),
                check.equal(target.compare_precedence(v1, v1), 0),
            )
        )
        ctx.update(lambda res, v1, v2: None)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[VersionEngine, [str], VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(text=Domain(strategy=lambda: '>=1.0.0', validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text: _fake_parse_range(text))
        ctx.ensures(
            lambda res, target, check, text: (
                check(isinstance(res, VersionRange), "Result must be VersionRange"),
                check.equal(str(res), res.raw_text),
                check(len(res.raw_text) > 0, "raw_text must not be empty"),
                check.equal(res.raw_text, text.strip()),
            )
        )
        ctx.update(lambda res, text: None)

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [Version, VersionRange, bool], bool],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(
                    version=Domain(strategy=lambda: Version(1, 0, 0), validator=lambda version: isinstance(version, Version)),
                    range_constraint=Domain(strategy=lambda: VersionRange('>=1.0.0'), validator=lambda range_constraint: isinstance(range_constraint, VersionRange)),
                    include_prerelease=Domain(strategy=lambda: False, validator=lambda include_prerelease: isinstance(include_prerelease, bool)),
                )
        ctx.returns(
            lambda version, range_constraint, include_prerelease=False: _eval_satisfies(
                version, range_constraint, include_prerelease
            )
        )
        ctx.ensures(
            lambda res, target, check, version, range_constraint, include_prerelease=False: check.equal(
                res, _eval_satisfies(version, range_constraint, include_prerelease)
            )
        )
        ctx.update(lambda res, version, range_constraint, include_prerelease=False: None)

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [PackageRelease], None],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(release=Domain(strategy=lambda: PackageRelease(name='pkg_a', version=Version(1, 0, 0)), validator=lambda release: isinstance(release, PackageRelease)))
        ctx.returns(lambda release: None)
        ctx.ensures(
            lambda res, target, check, release: (
                check(target.has_package(release.name), f"Repository must contain {release.name}"),
                check(
                    any(r.version == release.version for r in target.get_releases(release.name)),
                    f"Release {release.version} must be present in get_releases",
                ),
            )
        )
        ctx.update(lambda res, release: self._record_package_release(release))

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(name=Domain(strategy=lambda: next(iter(self.state.packages.keys()), 'pkg_a'), validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name: _fake_get_releases(self.state, name))
        ctx.ensures(
            lambda res, target, check, name: (
                check(all(r.name == name for r in res), "All releases must match package name"),
                check(
                    all(
                        _compare_version_precedence(res[i].version, res[i + 1].version) >= 0
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
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(name=Domain(strategy=lambda: next(iter(self.state.packages.keys()), 'pkg_a'), validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name: name in self.state.packages)
        ctx.ensures(
            lambda res, target, check, name: check.equal(res, name in self.state.packages)
        )
        ctx.update(lambda res, name: None)

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
        ctx: TransitionContext[PackageRepository, [], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments()
        ctx.returns(lambda: set(self.state.packages.keys()))
        ctx.ensures(
            lambda res, target, check: check.equal(res, set(self.state.packages.keys()))
        )
        ctx.update(lambda res: None)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[DependencySolver, [Collection[PackageDependency]], ResolutionOutcome],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: [], validator=lambda root_dependencies: isinstance(root_dependencies, (list, tuple, set, frozenset))))
        ctx.returns(lambda root_dependencies: _fake_resolve(self.state, root_dependencies))
        ctx.ensures(
            lambda res, target, check, root_dependencies: self._ensure_resolve_postconditions(
                res, target, check, root_dependencies
            )
        )
        ctx.update(lambda res, root_dependencies: None)

    def _ensure_resolve_postconditions(
        self,
        res: ResolutionOutcome,
        target: Any,
        check: Any,
        root_dependencies: Collection[PackageDependency],
    ) -> None:
        check(isinstance(res, ResolutionOutcome), "Result must be ResolutionOutcome")
        check(isinstance(res.selected_versions, (dict, Mapping)), "selected_versions must be Mapping")
        check(isinstance(res.derivation_steps, tuple), "derivation_steps must be tuple")

        version_engine: Optional[VersionEngine] = None
        repo: Optional[PackageRepository] = None

        try:
            version_engine = check.get(VersionEngine)
        except Exception:
            pass
        if version_engine is None and hasattr(target, "versionengine"):
            version_engine = getattr(target, "versionengine")
        if version_engine is None and self.singletons:
            version_engine = self.singletons.get(VersionEngine)

        try:
            repo = check.get(PackageRepository)
        except Exception:
            pass
        if repo is None and hasattr(target, "packagerepository"):
            repo = getattr(target, "packagerepository")
        if repo is None and self.singletons:
            repo = self.singletons.get(PackageRepository)

        for dep in root_dependencies:
            check(dep.name in res.selected_versions, f"Root dependency {dep.name} must be in selected_versions")
            selected_ver = res.selected_versions[dep.name]
            if version_engine is not None:
                check(
                    version_engine.satisfies(selected_ver, dep.range_constraint),
                    f"Selected version {selected_ver} must satisfy root constraint {dep.range_constraint}",
                )
            else:
                check(
                    _eval_satisfies(selected_ver, dep.range_constraint, False),
                    f"Selected version {selected_ver} must satisfy root constraint {dep.range_constraint}",
                )

        for pkg_name, selected_ver in res.selected_versions.items():
            if repo is not None:
                releases = repo.get_releases(pkg_name)
            else:
                releases = self.state.packages.get(pkg_name, [])
            rel = next((r for r in releases if r.version == selected_ver), None)
            check(rel is not None, f"Selected release {selected_ver} for {pkg_name} must exist in repository")
            if rel:
                for trans_dep in rel.dependencies:
                    check(
                        trans_dep.name in res.selected_versions,
                        f"Transitive dependency {trans_dep.name} must be in selected_versions",
                    )
                    trans_ver = res.selected_versions[trans_dep.name]
                    if version_engine is not None:
                        check(
                            version_engine.satisfies(trans_ver, trans_dep.range_constraint),
                            f"Selected version {trans_ver} must satisfy transitive constraint {trans_dep.range_constraint}",
                        )
                    else:
                        check(
                            _eval_satisfies(trans_ver, trans_dep.range_constraint, False),
                            f"Selected version {trans_ver} must satisfy transitive constraint {trans_dep.range_constraint}",
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
        self.assertEqual(len(self.state.packages), 0)

    def test_fake_parse_version_valid(self) -> None:
        v = self.versionengine.parse_version("1.2.3-alpha.1+build.42")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)
        self.assertEqual(v.patch, 3)
        self.assertEqual(v.prerelease, ("alpha", "1"))
        self.assertEqual(v.build, ("build", "42"))

    def test_fake_parse_version_invalid_syntax(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.2")

    def test_fake_parse_version_leading_zero(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.2.3")

    def test_fake_compare_precedence(self) -> None:
        v1 = Version(1, 0, 0)
        v2 = Version(2, 0, 0)
        self.assertLess(self.versionengine.compare_precedence(v1, v2), 0)
        self.assertGreater(self.versionengine.compare_precedence(v2, v1), 0)
        self.assertEqual(self.versionengine.compare_precedence(v1, v1), 0)

    def test_fake_compare_precedence_prerelease(self) -> None:
        v_norm = Version(1, 0, 0)
        v_pre = Version(1, 0, 0, ("alpha",))
        self.assertGreater(self.versionengine.compare_precedence(v_norm, v_pre), 0)
        self.assertLess(self.versionengine.compare_precedence(v_pre, v_norm), 0)

    def test_fake_parse_range_valid(self) -> None:
        rng = self.versionengine.parse_range("  >= 1.0.0 < 2.0.0  ")
        self.assertEqual(rng.raw_text, ">= 1.0.0 < 2.0.0")

    def test_fake_parse_range_invalid(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0, <2.0.0")

    def test_fake_satisfies(self) -> None:
        v = Version(1, 2, 0)
        rng = VersionRange("^1.0.0")
        self.assertTrue(self.versionengine.satisfies(v, rng))
        v2 = Version(2, 0, 0)
        self.assertFalse(self.versionengine.satisfies(v2, rng))

    def test_fake_register_and_get_releases(self) -> None:
        rel1 = PackageRelease("pkg_a", Version(1, 0, 0))
        rel2 = PackageRelease("pkg_a", Version(2, 0, 0))
        self.packagerepository.register_package(rel1)
        self.packagerepository.register_package(rel2)
        releases = self.packagerepository.get_releases("pkg_a")
        self.assertEqual(len(releases), 2)
        self.assertEqual(releases[0].version, Version(2, 0, 0))
        self.assertEqual(releases[1].version, Version(1, 0, 0))
        self.assertTrue(self.packagerepository.has_package("pkg_a"))
        self.assertFalse(self.packagerepository.has_package("pkg_b"))
        self.assertIn("pkg_a", self.packagerepository.all_packages())

    def test_fake_get_releases_not_found(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("missing_pkg")

    def test_fake_resolve_empty(self) -> None:
        outcome = self.dependencysolver.resolve([])
        self.assertEqual(outcome.selected_versions, {})

    def test_fake_resolve_success(self) -> None:
        rel = PackageRelease("pkg_a", Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        dep = PackageDependency("pkg_a", VersionRange(">=1.0.0"))
        outcome = self.dependencysolver.resolve([dep])
        self.assertEqual(outcome.selected_versions, {"pkg_a": Version(1, 0, 0)})

    def test_fake_resolve_conflict(self) -> None:
        dep = PackageDependency("unregistered_pkg", VersionRange(">=1.0.0"))
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve([dep])

    def test_fake_compare_precedence_ascii_lexical(self) -> None:
        v_alpha = Version(1, 0, 0, ("alpha",))
        v_beta = Version(1, 0, 0, ("beta",))
        v_rc = Version(1, 0, 0, ("rc",))
        self.assertLess(self.versionengine.compare_precedence(v_alpha, v_beta), 0)
        self.assertGreater(self.versionengine.compare_precedence(v_beta, v_alpha), 0)
        self.assertLess(self.versionengine.compare_precedence(v_beta, v_rc), 0)
        self.assertGreater(self.versionengine.compare_precedence(v_rc, v_beta), 0)

    def test_fake_parse_range_syntax_error_branches(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0 - 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - <=2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">1.0.0 - 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 -")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("- 1.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("-")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("<=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("<")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("~")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("==")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("!=")

    def test_fake_parse_range_hyphen_wildcard_and_prerelease_bounds(self) -> None:
        self.assertEqual(self.versionengine.parse_range("1.x - 2.0.0").raw_text, "1.x - 2.0.0")
        self.assertEqual(self.versionengine.parse_range("1.2.x - 2.0.0").raw_text, "1.2.x - 2.0.0")
        self.assertEqual(self.versionengine.parse_range("* - 2.0.0").raw_text, "* - 2.0.0")
        self.assertEqual(self.versionengine.parse_range("1.0.0 - 2.3.x").raw_text, "1.0.0 - 2.3.x")
        self.assertEqual(self.versionengine.parse_range("1.0.0 - 2.3.*").raw_text, "1.0.0 - 2.3.*")
        self.assertEqual(self.versionengine.parse_range("1.0.0 - 2.0.0-beta.1").raw_text, "1.0.0 - 2.0.0-beta.1")

    def test_fake_parse_range_wildcards_with_operators(self) -> None:
        self.assertEqual(self.versionengine.parse_range(">=*").raw_text, ">=*")
        self.assertEqual(self.versionengine.parse_range("<=*").raw_text, "<=*")
        self.assertEqual(self.versionengine.parse_range("~*").raw_text, "~*")
        self.assertEqual(self.versionengine.parse_range("^*").raw_text, "^*")
        self.assertEqual(self.versionengine.parse_range("!=*").raw_text, "!=*")
        self.assertEqual(self.versionengine.parse_range("^0.x").raw_text, "^0.x")
        self.assertEqual(self.versionengine.parse_range("^0.2.x").raw_text, "^0.2.x")
        self.assertEqual(self.versionengine.parse_range("^0.0.x").raw_text, "^0.0.x")
        self.assertEqual(self.versionengine.parse_range("^0.0.1").raw_text, "^0.0.1")
        self.assertEqual(self.versionengine.parse_range("^1.0.x").raw_text, "^1.0.x")
        self.assertEqual(self.versionengine.parse_range("~0.x").raw_text, "~0.x")
        self.assertEqual(self.versionengine.parse_range("~0.2.x").raw_text, "~0.2.x")

    def test_fake_satisfies_hyphen_prerelease_and_wildcard_bounds(self) -> None:
        v_pre = Version(1, 0, 0, ("alpha", "2"))
        rng_pre = VersionRange("1.0.0-alpha.1 - 1.0.0")
        self.assertTrue(self.versionengine.satisfies(v_pre, rng_pre))
        v_mid = Version(2, 5, 0)
        rng_wild = VersionRange("1.0.0 - 2.x")
        self.assertTrue(self.versionengine.satisfies(v_mid, rng_wild))
        v_high = Version(3, 0, 0)
        self.assertFalse(self.versionengine.satisfies(v_high, rng_wild))
        self.assertTrue(self.versionengine.satisfies(Version(1, 5, 0), VersionRange("1.x - 2.0.0")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 9, 0), VersionRange("1.x - 2.0.0")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 2, 5), VersionRange("1.2.x - 2.0.0")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 1, 9), VersionRange("1.2.x - 2.0.0")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("* - 2.0.0")))
        self.assertFalse(self.versionengine.satisfies(Version(2, 5, 0), VersionRange("* - 2.0.0")))
        self.assertTrue(self.versionengine.satisfies(Version(2, 3, 5), VersionRange("1.0.0 - 2.3.x")))
        self.assertFalse(self.versionengine.satisfies(Version(2, 4, 0), VersionRange("1.0.0 - 2.3.x")))
        self.assertTrue(self.versionengine.satisfies(Version(2, 3, 5), VersionRange("1.0.0 - 2.3.*")))
        self.assertFalse(self.versionengine.satisfies(Version(2, 4, 0), VersionRange("1.0.0 - 2.3.*")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 5, 0), VersionRange("1.0.0 - 2.0.0-beta.1")))
        self.assertTrue(self.versionengine.satisfies(Version(2, 0, 0, ("alpha",)), VersionRange("1.0.0 - 2.0.0-beta.1")))
        self.assertFalse(self.versionengine.satisfies(Version(2, 0, 0, ("rc",)), VersionRange("1.0.0 - 2.0.0-beta.1")))
        self.assertFalse(self.versionengine.satisfies(Version(2, 0, 0), VersionRange("1.0.0 - 2.0.0-beta.1")))

    def test_fake_satisfies_wildcards_qualified_by_operators(self) -> None:
        v = Version(1, 2, 3)
        self.assertTrue(self.versionengine.satisfies(v, VersionRange(">=1.x")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange("<=1.x")))
        self.assertFalse(self.versionengine.satisfies(v, VersionRange(">1.x")))
        self.assertFalse(self.versionengine.satisfies(v, VersionRange("<1.x")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange("~1.x")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange("^1.x")))
        self.assertTrue(self.versionengine.satisfies(Version(2, 0, 0), VersionRange(">1.x")))
        self.assertTrue(self.versionengine.satisfies(Version(0, 9, 0), VersionRange("<1.x")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange(">=1.2.x")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange("<=1.2.x")))
        self.assertFalse(self.versionengine.satisfies(v, VersionRange(">1.2.x")))
        self.assertFalse(self.versionengine.satisfies(v, VersionRange("<1.2.x")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange("~1.2.x")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange("^1.2.x")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange(">=*")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange("<=*")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange("~*")))
        self.assertTrue(self.versionengine.satisfies(v, VersionRange("^*")))
        self.assertFalse(self.versionengine.satisfies(v, VersionRange("!=*")))
        self.assertTrue(self.versionengine.satisfies(Version(0, 5, 0), VersionRange("^0.x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("^0.x")))
        self.assertTrue(self.versionengine.satisfies(Version(0, 2, 5), VersionRange("^0.2.x")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 3, 0), VersionRange("^0.2.x")))
        self.assertTrue(self.versionengine.satisfies(Version(0, 0, 3), VersionRange("^0.0.x")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 1, 0), VersionRange("^0.0.x")))
        self.assertTrue(self.versionengine.satisfies(Version(0, 0, 1), VersionRange("^0.0.1")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 0, 2), VersionRange("^0.0.1")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 0, 5), VersionRange("^1.0.x")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 1, 0), VersionRange("^1.0.x")))
        self.assertFalse(self.versionengine.satisfies(Version(2, 0, 0), VersionRange("^1.0.x")))

    def test_fake_satisfies_negative_comparators(self) -> None:
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 1), VersionRange("==1.0.0")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!=1.0.0")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange(">1.0.0")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 9, 0), VersionRange(">1.0.0")))

    def test_fake_parse_range_inequality_wildcards(self) -> None:
        self.assertEqual(self.versionengine.parse_range("!=1.x").raw_text, "!=1.x")
        self.assertEqual(self.versionengine.parse_range("!= 1.x").raw_text, "!= 1.x")
        self.assertEqual(self.versionengine.parse_range("!=1.*").raw_text, "!=1.*")
        self.assertEqual(self.versionengine.parse_range("!= 1.*").raw_text, "!= 1.*")
        self.assertEqual(self.versionengine.parse_range("!=0.x").raw_text, "!=0.x")
        self.assertEqual(self.versionengine.parse_range("!= 0.x").raw_text, "!= 0.x")
        self.assertEqual(self.versionengine.parse_range("!=1.2.x").raw_text, "!=1.2.x")
        self.assertEqual(self.versionengine.parse_range("!= 1.2.x").raw_text, "!= 1.2.x")
        self.assertEqual(self.versionengine.parse_range("!=1.2.*").raw_text, "!=1.2.*")
        self.assertEqual(self.versionengine.parse_range("!= 1.2.*").raw_text, "!= 1.2.*")
        self.assertEqual(self.versionengine.parse_range("!=0.0.x").raw_text, "!=0.0.x")
        self.assertEqual(self.versionengine.parse_range("!= 0.0.x").raw_text, "!= 0.0.x")
        self.assertEqual(self.versionengine.parse_range("!=*").raw_text, "!=*")
        self.assertEqual(self.versionengine.parse_range("!= *").raw_text, "!= *")
        self.assertEqual(self.versionengine.parse_range("!=x").raw_text, "!=x")
        self.assertEqual(self.versionengine.parse_range("!= x").raw_text, "!= x")
        self.assertEqual(self.versionengine.parse_range("!=X").raw_text, "!=X")
        self.assertEqual(self.versionengine.parse_range("!= X").raw_text, "!= X")

    def test_fake_parse_range_strict_relational_star_wildcards(self) -> None:
        self.assertEqual(self.versionengine.parse_range(">*").raw_text, ">*")
        self.assertEqual(self.versionengine.parse_range("> *").raw_text, "> *")
        self.assertEqual(self.versionengine.parse_range(">x").raw_text, ">x")
        self.assertEqual(self.versionengine.parse_range("> x").raw_text, "> x")
        self.assertEqual(self.versionengine.parse_range(">X").raw_text, ">X")
        self.assertEqual(self.versionengine.parse_range("> X").raw_text, "> X")
        self.assertEqual(self.versionengine.parse_range("<*").raw_text, "<*")
        self.assertEqual(self.versionengine.parse_range("< *").raw_text, "< *")
        self.assertEqual(self.versionengine.parse_range("<x").raw_text, "<x")
        self.assertEqual(self.versionengine.parse_range("< x").raw_text, "< x")
        self.assertEqual(self.versionengine.parse_range("<X").raw_text, "<X")
        self.assertEqual(self.versionengine.parse_range("< X").raw_text, "< X")

    def test_fake_satisfies_inequality_wildcards(self) -> None:
        # Major wildcards with !=
        self.assertFalse(self.versionengine.satisfies(Version(1, 2, 3), VersionRange("!=1.x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!=1.x")))
        self.assertTrue(self.versionengine.satisfies(Version(2, 0, 0), VersionRange("!=1.x")))
        self.assertTrue(self.versionengine.satisfies(Version(0, 9, 0), VersionRange("!=1.x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 2, 3), VersionRange("!= 1.x")))
        self.assertTrue(self.versionengine.satisfies(Version(2, 0, 0), VersionRange("!= 1.x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 5, 0), VersionRange("!=1.*")))
        self.assertTrue(self.versionengine.satisfies(Version(2, 1, 0), VersionRange("!=1.*")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 5, 0), VersionRange("!= 1.*")))
        self.assertTrue(self.versionengine.satisfies(Version(2, 1, 0), VersionRange("!= 1.*")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 5, 0), VersionRange("!=0.x")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!=0.x")))

        # Minor wildcards with !=
        self.assertFalse(self.versionengine.satisfies(Version(1, 2, 3), VersionRange("!=1.2.x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 2, 0), VersionRange("!=1.2.x")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 3, 0), VersionRange("!=1.2.x")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 1, 9), VersionRange("!=1.2.x")))
        self.assertTrue(self.versionengine.satisfies(Version(2, 2, 0), VersionRange("!=1.2.x")))
        self.assertTrue(self.versionengine.satisfies(Version(0, 2, 0), VersionRange("!=1.2.x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 2, 3), VersionRange("!= 1.2.x")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 3, 0), VersionRange("!= 1.2.x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 2, 4), VersionRange("!=1.2.*")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 4, 0), VersionRange("!=1.2.*")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 2, 4), VersionRange("!= 1.2.*")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 4, 0), VersionRange("!= 1.2.*")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 0, 5), VersionRange("!=0.0.x")))
        self.assertTrue(self.versionengine.satisfies(Version(0, 1, 0), VersionRange("!=0.0.x")))
        self.assertTrue(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!=0.0.x")))

        # Star wildcards with !=
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!=*")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 0, 0), VersionRange("!=*")))
        self.assertFalse(self.versionengine.satisfies(Version(2, 5, 3), VersionRange("!=*")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!= *")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!=x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!= x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!=X")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("!= X")))

    def test_fake_satisfies_strict_relational_star_wildcards(self) -> None:
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange(">*")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 0, 0), VersionRange(">*")))
        self.assertFalse(self.versionengine.satisfies(Version(99, 99, 99), VersionRange(">*")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("> *")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange(">x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("> x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange(">X")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("> X")))

        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("<*")))
        self.assertFalse(self.versionengine.satisfies(Version(0, 0, 0), VersionRange("<*")))
        self.assertFalse(self.versionengine.satisfies(Version(99, 99, 99), VersionRange("<*")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("< *")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("<x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("< x")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("<X")))
        self.assertFalse(self.versionengine.satisfies(Version(1, 0, 0), VersionRange("< X")))

    def test_fake_solver_transitive_conflict_with_existing_assignment(self) -> None:
        rel_base = PackageRelease("aaa_base", Version(1, 0, 0))
        self.packagerepository.register_package(rel_base)
        dep_trans = PackageDependency("aaa_base", VersionRange(">=2.0.0"))
        rel_user = PackageRelease("zzz_user", Version(1, 0, 0), dependencies=(dep_trans,))
        self.packagerepository.register_package(rel_user)
        root_deps = [
            PackageDependency("aaa_base", VersionRange("==1.0.0")),
            PackageDependency("zzz_user", VersionRange("==1.0.0")),
        ]
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(root_deps)

    def test_fake_solver_shared_dependency_assignment_conflict(self) -> None:
        rel_shared_1 = PackageRelease("shared_lib", Version(1, 0, 0))
        rel_shared_2 = PackageRelease("shared_lib", Version(2, 0, 0))
        self.packagerepository.register_package(rel_shared_1)
        self.packagerepository.register_package(rel_shared_2)
        rel_client_a = PackageRelease(
            "client_a", Version(1, 0, 0), dependencies=(PackageDependency("shared_lib", VersionRange("==1.0.0")),)
        )
        rel_client_b = PackageRelease(
            "client_b", Version(1, 0, 0), dependencies=(PackageDependency("shared_lib", VersionRange("==2.0.0")),)
        )
        self.packagerepository.register_package(rel_client_a)
        self.packagerepository.register_package(rel_client_b)
        root_deps = [
            PackageDependency("client_a", VersionRange("==1.0.0")),
            PackageDependency("client_b", VersionRange("==1.0.0")),
        ]
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(root_deps)


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

    def test_real_parse_version_prerelease(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.0.0-alpha.1")

    def test_real_parse_version_build(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.0.0+20130313144700")

    def test_real_parse_version_prerelease_and_build(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.0.0-beta.2+exp.sha.5114f85")

    def test_real_parse_version_invalid_empty(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("")

    def test_real_parse_version_invalid_leading_zero_major(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.0.0")

    def test_real_parse_version_invalid_leading_zero_minor(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.02.0")

    def test_real_parse_version_invalid_leading_zero_patch(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.03")

    def test_real_parse_version_invalid_leading_zero_prerelease(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-01")

    def test_real_compare_precedence_numeric(self) -> None:
        self.sm.dispatch_transition("compare_precedence", Version(1, 0, 0), Version(2, 0, 0))
        self.sm.dispatch_transition("compare_precedence", Version(1, 1, 0), Version(1, 2, 0))
        self.sm.dispatch_transition("compare_precedence", Version(1, 0, 1), Version(1, 0, 2))

    def test_real_compare_precedence_equal(self) -> None:
        self.sm.dispatch_transition("compare_precedence", Version(1, 2, 3), Version(1, 2, 3))

    def test_real_compare_precedence_normal_vs_prerelease(self) -> None:
        self.sm.dispatch_transition("compare_precedence", Version(1, 0, 0), Version(1, 0, 0, ("alpha",)))

    def test_real_compare_precedence_prerelease_identifiers(self) -> None:
        self.sm.dispatch_transition("compare_precedence", Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",)))
        self.sm.dispatch_transition(
            "compare_precedence", Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "2"))
        )
        self.sm.dispatch_transition(
            "compare_precedence", Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1"))
        )

    def test_real_compare_precedence_ignore_build(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence", Version(1, 0, 0, (), ("build1",)), Version(1, 0, 0, (), ("build2",))
        )

    def test_real_parse_range_basic_comparators(self) -> None:
        self.sm.dispatch_transition("parse_range", "=1.0.0")
        self.sm.dispatch_transition("parse_range", "==1.0.0")
        self.sm.dispatch_transition("parse_range", "!=1.0.0")
        self.sm.dispatch_transition("parse_range", "<1.0.0")
        self.sm.dispatch_transition("parse_range", "<=1.0.0")
        self.sm.dispatch_transition("parse_range", ">1.0.0")
        self.sm.dispatch_transition("parse_range", ">=1.0.0")

    def test_real_parse_range_caret_and_tilde(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.2.3")
        self.sm.dispatch_transition("parse_range", "^0.2.3")
        self.sm.dispatch_transition("parse_range", "^0.0.3")
        self.sm.dispatch_transition("parse_range", "~1.2.3")
        self.sm.dispatch_transition("parse_range", "~0.2.3")

    def test_real_parse_range_wildcards_and_hyphen(self) -> None:
        self.sm.dispatch_transition("parse_range", "*")
        self.sm.dispatch_transition("parse_range", "1.x")
        self.sm.dispatch_transition("parse_range", "1.2.x")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0")

    def test_real_parse_range_unions(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.0.0 || ^2.0.0")

    def test_real_parse_range_whitespace_tolerance(self) -> None:
        self.sm.dispatch_transition("parse_range", "  >= 1.0.0   <= 2.0.0  ")

    def test_real_parse_range_invalid_empty(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("   ")

    def test_real_parse_range_invalid_commas(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0, <2.0.0")

    def test_real_parse_range_invalid_empty_union(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 ||")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("|| 1.0.0")

    def test_real_parse_range_invalid_bare_partial(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.3")

    def test_real_satisfies_caret_and_tilde(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("^1.2.0"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange("^1.2.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 5), VersionRange("~1.2.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 3, 0), VersionRange("~1.2.0"), False)

    def test_real_satisfies_prerelease_rules(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0-0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), True)

    def test_real_satisfies_wildcard_and_hyphen(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange("1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("1.0.0 - 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 5, 0), VersionRange("1.0.0 - 2.0.0"), False)

    def test_real_package_repository_lifecycle(self) -> None:
        r1 = PackageRelease("pkg_x", Version(1, 0, 0))
        r2 = PackageRelease("pkg_x", Version(2, 0, 0))
        self.sm.dispatch_transition("register_package", r1)
        self.sm.dispatch_transition("has_package", "pkg_x")
        self.sm.dispatch_transition("register_package", r2)
        self.sm.dispatch_transition("get_releases", "pkg_x")
        self.sm.dispatch_transition("all_packages")

    def test_real_package_repository_missing(self) -> None:
        self.sm.dispatch_transition("has_package", "non_existent_pkg")
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("non_existent_pkg")

    def test_real_solver_empty_root(self) -> None:
        self.sm.dispatch_transition("resolve", [])

    def test_real_solver_single_package(self) -> None:
        rel1 = PackageRelease("pkg_alpha", Version(1, 0, 0))
        rel2 = PackageRelease("pkg_alpha", Version(2, 0, 0))
        self.sm.dispatch_transition("register_package", rel1)
        self.sm.dispatch_transition("register_package", rel2)
        self.sm.dispatch_transition("resolve", [PackageDependency("pkg_alpha", VersionRange(">=1.0.0"))])

    def test_real_solver_transitive_dependencies(self) -> None:
        dep_b = PackageDependency("pkg_bravo", VersionRange("^1.0.0"))
        rel_a = PackageRelease("pkg_alpha", Version(1, 0, 0), dependencies=(dep_b,))
        rel_b = PackageRelease("pkg_bravo", Version(1, 2, 0))
        self.sm.dispatch_transition("register_package", rel_a)
        self.sm.dispatch_transition("register_package", rel_b)
        self.sm.dispatch_transition("resolve", [PackageDependency("pkg_alpha", VersionRange("^1.0.0"))])

    def test_real_solver_conflict_unregistered(self) -> None:
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve([PackageDependency("missing_pkg", VersionRange(">=1.0.0"))])

    def test_real_solver_conflict_unsatisfiable_version(self) -> None:
        rel = PackageRelease("pkg_charlie", Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel)
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve([PackageDependency("pkg_charlie", VersionRange(">=2.0.0"))])

    def test_real_solver_transitive_conflict(self) -> None:
        dep_unresolvable = PackageDependency("pkg_delta", VersionRange(">=3.0.0"))
        rel_c = PackageRelease("pkg_charlie", Version(2, 0, 0), dependencies=(dep_unresolvable,))
        rel_d = PackageRelease("pkg_delta", Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel_c)
        self.sm.dispatch_transition("register_package", rel_d)
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve([PackageDependency("pkg_charlie", VersionRange(">=2.0.0"))])

    def test_real_compare_precedence_ascii_lexical(self) -> None:
        self.sm.dispatch_transition("compare_precedence", Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",)))
        self.sm.dispatch_transition("compare_precedence", Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("rc",)))

    def test_real_parse_range_invalid_hyphen_prefix_operators(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0 - 2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - <=2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">1.0.0 - 2.0.0")

    def test_real_parse_range_invalid_hyphen_missing_upper(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 -")

    def test_real_parse_range_invalid_unexpected_hyphen(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("- 1.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("-")

    def test_real_parse_range_invalid_operators_without_target(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("<=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("<")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("~")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("==")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("!=")

    def test_real_parse_range_hyphen_wildcard_and_prerelease_bounds(self) -> None:
        self.sm.dispatch_transition("parse_range", "1.x - 2.0.0")
        self.sm.dispatch_transition("parse_range", "1.2.x - 2.0.0")
        self.sm.dispatch_transition("parse_range", "* - 2.0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.3.x")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.3.*")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0-beta.1")

    def test_real_parse_range_wildcards_with_operators(self) -> None:
        self.sm.dispatch_transition("parse_range", ">=*")
        self.sm.dispatch_transition("parse_range", "<=*")
        self.sm.dispatch_transition("parse_range", "~*")
        self.sm.dispatch_transition("parse_range", "^*")
        self.sm.dispatch_transition("parse_range", "!=*")
        self.sm.dispatch_transition("parse_range", "^0.x")
        self.sm.dispatch_transition("parse_range", "^0.2.x")
        self.sm.dispatch_transition("parse_range", "^0.0.x")
        self.sm.dispatch_transition("parse_range", "^0.0.1")
        self.sm.dispatch_transition("parse_range", "^1.0.x")
        self.sm.dispatch_transition("parse_range", "~0.x")
        self.sm.dispatch_transition("parse_range", "~0.2.x")

    def test_real_satisfies_hyphen_prerelease_and_wildcard_bounds(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 0, 0, ("alpha", "2")), VersionRange("1.0.0-alpha.1 - 1.0.0"), False
        )
        self.sm.dispatch_transition("satisfies", Version(2, 5, 0), VersionRange("1.0.0 - 2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(3, 0, 0), VersionRange("1.0.0 - 2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("1.x - 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 9, 0), VersionRange("1.x - 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 5), VersionRange("1.2.x - 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 1, 9), VersionRange("1.2.x - 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("* - 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 5, 0), VersionRange("* - 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 3, 5), VersionRange("1.0.0 - 2.3.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 4, 0), VersionRange("1.0.0 - 2.3.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 3, 5), VersionRange("1.0.0 - 2.3.*"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 4, 0), VersionRange("1.0.0 - 2.3.*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("1.0.0 - 2.0.0-beta.1"), False)
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0, ("alpha",)), VersionRange("1.0.0 - 2.0.0-beta.1"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0, ("rc",)), VersionRange("1.0.0 - 2.0.0-beta.1"), False
        )
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange("1.0.0 - 2.0.0-beta.1"), False)

    def test_real_satisfies_wildcards_qualified_by_operators(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange(">=1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("<=1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange(">1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("<1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("~1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("^1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange(">1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 9, 0), VersionRange("<1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange(">=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("<=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange(">1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("<1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("~1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("^1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange(">=*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("<=*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("~*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("^*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=*"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 5, 0), VersionRange("^0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("^0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 2, 5), VersionRange("^0.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 3, 0), VersionRange("^0.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 0, 3), VersionRange("^0.0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 1, 0), VersionRange("^0.0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 0, 1), VersionRange("^0.0.1"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 0, 2), VersionRange("^0.0.1"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 5), VersionRange("^1.0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 1, 0), VersionRange("^1.0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange("^1.0.x"), False)

    def test_real_satisfies_negative_comparators(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 0, 1), VersionRange("==1.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=1.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange(">1.0.0"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 9, 0), VersionRange(">1.0.0"), False)

    def test_real_parse_range_inequality_wildcards(self) -> None:
        self.sm.dispatch_transition("parse_range", "!=1.x")
        self.sm.dispatch_transition("parse_range", "!= 1.x")
        self.sm.dispatch_transition("parse_range", "!=1.*")
        self.sm.dispatch_transition("parse_range", "!= 1.*")
        self.sm.dispatch_transition("parse_range", "!=0.x")
        self.sm.dispatch_transition("parse_range", "!= 0.x")
        self.sm.dispatch_transition("parse_range", "!=1.2.x")
        self.sm.dispatch_transition("parse_range", "!= 1.2.x")
        self.sm.dispatch_transition("parse_range", "!=1.2.*")
        self.sm.dispatch_transition("parse_range", "!= 1.2.*")
        self.sm.dispatch_transition("parse_range", "!=0.0.x")
        self.sm.dispatch_transition("parse_range", "!= 0.0.x")
        self.sm.dispatch_transition("parse_range", "!=*")
        self.sm.dispatch_transition("parse_range", "!= *")
        self.sm.dispatch_transition("parse_range", "!=x")
        self.sm.dispatch_transition("parse_range", "!= x")
        self.sm.dispatch_transition("parse_range", "!=X")
        self.sm.dispatch_transition("parse_range", "!= X")

    def test_real_parse_range_strict_relational_star_wildcards(self) -> None:
        self.sm.dispatch_transition("parse_range", ">*")
        self.sm.dispatch_transition("parse_range", "> *")
        self.sm.dispatch_transition("parse_range", ">x")
        self.sm.dispatch_transition("parse_range", "> x")
        self.sm.dispatch_transition("parse_range", ">X")
        self.sm.dispatch_transition("parse_range", "> X")
        self.sm.dispatch_transition("parse_range", "<*")
        self.sm.dispatch_transition("parse_range", "< *")
        self.sm.dispatch_transition("parse_range", "<x")
        self.sm.dispatch_transition("parse_range", "< x")
        self.sm.dispatch_transition("parse_range", "<X")
        self.sm.dispatch_transition("parse_range", "< X")

    def test_real_satisfies_inequality_wildcards(self) -> None:
        # Major wildcards with !=
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("!=1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange("!=1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 9, 0), VersionRange("!=1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("!= 1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 0, 0), VersionRange("!= 1.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("!=1.*"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 1, 0), VersionRange("!=1.*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 5, 0), VersionRange("!= 1.*"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 1, 0), VersionRange("!= 1.*"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 5, 0), VersionRange("!=0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=0.x"), False)

        # Minor wildcards with !=
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("!=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 0), VersionRange("!=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 3, 0), VersionRange("!=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 1, 9), VersionRange("!=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 2, 0), VersionRange("!=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 2, 0), VersionRange("!=1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 3), VersionRange("!= 1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 3, 0), VersionRange("!= 1.2.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 4), VersionRange("!=1.2.*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 4, 0), VersionRange("!=1.2.*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 2, 4), VersionRange("!= 1.2.*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 4, 0), VersionRange("!= 1.2.*"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 0, 5), VersionRange("!=0.0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 1, 0), VersionRange("!=0.0.x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=0.0.x"), False)

        # Star wildcards with !=
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=*"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 0, 0), VersionRange("!=*"), False)
        self.sm.dispatch_transition("satisfies", Version(2, 5, 3), VersionRange("!=*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!= *"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!= x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!=X"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("!= X"), False)

    def test_real_satisfies_strict_relational_star_wildcards(self) -> None:
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange(">*"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 0, 0), VersionRange(">*"), False)
        self.sm.dispatch_transition("satisfies", Version(99, 99, 99), VersionRange(">*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("> *"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange(">x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("> x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange(">X"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("> X"), False)

        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("<*"), False)
        self.sm.dispatch_transition("satisfies", Version(0, 0, 0), VersionRange("<*"), False)
        self.sm.dispatch_transition("satisfies", Version(99, 99, 99), VersionRange("<*"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("< *"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("<x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("< x"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("<X"), False)
        self.sm.dispatch_transition("satisfies", Version(1, 0, 0), VersionRange("< X"), False)

    def test_real_solver_transitive_conflict_with_existing_assignment(self) -> None:
        rel_base = PackageRelease("aaa_base", Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel_base)
        dep_trans = PackageDependency("aaa_base", VersionRange(">=2.0.0"))
        rel_user = PackageRelease("zzz_user", Version(1, 0, 0), dependencies=(dep_trans,))
        self.sm.dispatch_transition("register_package", rel_user)
        root_deps = [
            PackageDependency("aaa_base", VersionRange("==1.0.0")),
            PackageDependency("zzz_user", VersionRange("==1.0.0")),
        ]
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(root_deps)

    def test_real_solver_shared_dependency_assignment_conflict(self) -> None:
        rel_shared_1 = PackageRelease("shared_pkg", Version(1, 0, 0))
        rel_shared_2 = PackageRelease("shared_pkg", Version(2, 0, 0))
        self.sm.dispatch_transition("register_package", rel_shared_1)
        self.sm.dispatch_transition("register_package", rel_shared_2)
        rel_a = PackageRelease(
            "client_pkg_a", Version(1, 0, 0), dependencies=(PackageDependency("shared_pkg", VersionRange("==1.0.0")),)
        )
        rel_b = PackageRelease(
            "client_pkg_b", Version(1, 0, 0), dependencies=(PackageDependency("shared_pkg", VersionRange("==2.0.0")),)
        )
        self.sm.dispatch_transition("register_package", rel_a)
        self.sm.dispatch_transition("register_package", rel_b)
        root_deps = [
            PackageDependency("client_pkg_a", VersionRange("==1.0.0")),
            PackageDependency("client_pkg_b", VersionRange("==1.0.0")),
        ]
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(root_deps)


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
        self.__dict__["singletons"] = {
            VersionEngine: self.versionengine,
            PackageRepository: self.packagerepository,
            DependencySolver: self.dependencysolver,
        }
        self.__dict__["_services"] = (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
        )

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> SemverSolverSUT:
    sut = SemverSolverSUT()
    proto.singletons = {
        VersionEngine: sut.versionengine,
        PackageRepository: sut.packagerepository,
        DependencySolver: sut.dependencysolver,
    }
    return sut


SemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverSolverState,
    name="SemverSolverFuzzTest",
)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T22:35:26Z
# LAST_CHANGED: 2026-10-28T22:33:59Z
# CHANGE: Add unit and real transition tests for inequality-qualified wildcards and strictly relational star wildcards
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T22:35:26Z
# PRETENSE_QA_AUDIT: 2026-10-28T22:34:54Z
# --- END CLEANROOM METADATA ---
