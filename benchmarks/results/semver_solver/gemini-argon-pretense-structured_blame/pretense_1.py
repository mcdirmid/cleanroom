# === File: semver_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Collection, List, Set

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_default_registry,
    get_singleton,
    system,
)

from semver_solver_gemini_argon_1.parts.semver_solver.lib.semver_solver import (
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
from semver_solver_gemini_argon_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
)
from semver_solver_gemini_argon_1.parts.semver_solver.pretense.semver_solver_pretense import (
    SemVerSolverStateMachine,
)


class SemVerSolverImplPseudoStateMachine(SemVerSolverStateMachine):
    """Implementation pseudo-state machine binding concrete SemVerSolver services."""

    def inner_parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = target.parse_version(text)
        assert ret.is_prerelease == bool(ret.prerelease)
        assert ret.format() == str(ret)
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = target.compare_precedence(v1, v2)
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret = target.parse_range(text)
        assert str(ret) == ret.raw_text
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngine = sut(VersionEngine)
        ret = target.satisfies(version, range_constraint, include_prerelease)
        return ret

    def inner_register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = target.register_package(release)
        return ret

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = target.get_releases(name)
        return ret

    def inner_has_package(self, name: str) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = target.has_package(name)
        return ret

    def inner_all_packages(self) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret = target.all_packages()
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = target.resolve(root_dependencies)
        return ret


proto = SemVerSolverImplPseudoStateMachine()


class TestSemVerSolverImplReal(LifecycleTestCase):
    """Verifies concrete implementation conformance and contracted error conditions."""

    def setUp(self) -> None:
        super().setUp()
        engine = get_singleton(VersionEngine)
        repo = get_singleton(PackageRepository)
        solver = get_singleton(DependencySolver)
        sm = SemVerSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: engine,
                PackageRepository: repo,
                DependencySolver: solver,
            }
        )
        self.checked_engine = sm.as_checked(VersionEngine, engine)
        self.checked_repo = sm.as_checked(PackageRepository, repo)
        self.checked_solver = sm.as_checked(DependencySolver, solver)

    def test_version_and_range_conformance(self) -> None:
        v0 = self.checked_engine.parse_version("0.0.4")
        v_minor = self.checked_engine.parse_version("0.2.3")
        v1 = self.checked_engine.parse_version("1.0.0")
        v1_build = self.checked_engine.parse_version("1.0.0+20130313")
        v_pre1 = self.checked_engine.parse_version("1.0.0-alpha.1")
        v_pre2 = self.checked_engine.parse_version("1.0.0-alpha.2")
        v_pre_beta = self.checked_engine.parse_version("1.0.0-beta.1")
        v_pre_str = self.checked_engine.parse_version("1.0.0-alpha.beta")
        v_pre_short = self.checked_engine.parse_version("1.0.0-alpha")
        v2 = self.checked_engine.parse_version("2.0.0")

        self.checked_engine.compare_precedence(v0, v_minor)
        self.checked_engine.compare_precedence(v2, v1)
        self.checked_engine.compare_precedence(v1, v1_build)
        self.checked_engine.compare_precedence(v1, v_pre1)
        self.checked_engine.compare_precedence(v_pre1, v1)
        self.checked_engine.compare_precedence(v_pre1, v_pre2)
        self.checked_engine.compare_precedence(v_pre2, v_pre1)
        self.checked_engine.compare_precedence(v_pre1, v_pre_beta)
        self.checked_engine.compare_precedence(v_pre_beta, v_pre1)
        self.checked_engine.compare_precedence(v_pre1, v_pre_str)
        self.checked_engine.compare_precedence(v_pre_str, v_pre1)
        self.checked_engine.compare_precedence(v_pre_str, v_pre_short)
        self.checked_engine.compare_precedence(v_pre_short, v_pre_str)

        for expr in [
            "*",
            ">=*",
            "^1.0.0",
            "^0.2.3",
            "^0.0.4",
            "^1.x",
            "^1.2.x",
            "^0.2.x",
            "~1.2.0",
            "~1.x",
            "~1.2.x",
            "1.0.0 - 2.0.0",
            "1.0.0 - 2.x",
            "1.x - 2.x",
            "1.0.x - 1.2.x",
            ">=1.x",
            "!=1.x",
            ">1.x",
            "<=1.x",
            "<1.x",
            "==1.2.x",
            "==1.0.0",
            "=1.0.0",
            "!=1.0.0",
            "<2.0.0",
            "<=1.0.0",
            ">1.0.0",
            ">= 1.0.0 < 2.0.0",
            ">=1.0.0-alpha.1 <1.0.0",
            "==1.0.0 || >=2.0.0",
        ]:
            rng = self.checked_engine.parse_range(expr)
            self.checked_engine.satisfies(v0, rng, False)
            self.checked_engine.satisfies(v1, rng, False)
            self.checked_engine.satisfies(v2, rng, False)
            self.checked_engine.satisfies(v_pre1, rng, False)
            self.checked_engine.satisfies(v_pre1, rng, True)

    def test_backtracking_resolution_conformance(self) -> None:
        r_c1 = PackageRelease("c", Version(1, 0, 0), ())
        r_c2 = PackageRelease("c", Version(2, 0, 0), ())
        r_d2 = PackageRelease(
            "d",
            Version(2, 0, 0),
            (PackageDependency("c", VersionRange("==1.0.0")),),
        )
        r_d1 = PackageRelease(
            "d",
            Version(1, 0, 0),
            (PackageDependency("c", VersionRange("==2.0.0")),),
        )
        r_b1 = PackageRelease(
            "b",
            Version(1, 0, 0),
            (
                PackageDependency("c", VersionRange("==1.0.0")),
                PackageDependency("missing_dep", VersionRange("==1.0.0")),
            ),
        )
        r_a2 = PackageRelease(
            "a",
            Version(2, 0, 0),
            (
                PackageDependency("b", VersionRange("==1.0.0")),
                PackageDependency("c", VersionRange(">=1.0.0")),
            ),
        )
        r_a1 = PackageRelease(
            "a",
            Version(1, 0, 0),
            (PackageDependency("c", VersionRange("==1.0.0")),),
        )
        self.checked_repo.register_package(r_c1)
        self.checked_repo.register_package(r_c2)
        self.checked_repo.register_package(r_d2)
        self.checked_repo.register_package(r_d1)
        self.checked_repo.register_package(r_b1)
        self.checked_repo.register_package(r_a2)
        self.checked_repo.register_package(r_a1)
        self.checked_repo.has_package("c")
        self.checked_repo.has_package("missing")
        self.checked_repo.all_packages()
        self.checked_repo.get_releases("c")
        self.checked_solver.resolve(
            [
                PackageDependency("c", VersionRange("==2.0.0")),
                PackageDependency("d", VersionRange(">=1.0.0")),
            ]
        )
        self.checked_solver.resolve(
            [
                PackageDependency("a", VersionRange(">=1.0.0")),
            ]
        )

    def test_invalid_version_leading_zero(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("01.0.0")

    def test_invalid_version_malformed(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("1.0")

    def test_invalid_version_prerelease_leading_zero(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("1.0.0-01")

    def test_invalid_version_empty_build(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("1.0.0+")

    def test_invalid_range_empty(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("   ")

    def test_invalid_range_empty_union_clause(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">=1.0.0 || ")

    def test_invalid_range_comma_delimiter(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">=1.0.0, <2.0.0")

    def test_invalid_range_bare_partial(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.2")

    def test_invalid_range_bare_partial_comparator(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">1.2")

    def test_invalid_range_bare_partial_caret(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("^0.0")

    def test_invalid_range_bare_partial_hyphen(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.2 - 2.3")

    def test_invalid_range_malformed_syntax(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("~=1.0.0")

    def test_repo_missing_package_error(self) -> None:
        self.checked_repo.violating(PackageNotFoundError).get_releases("missing_pkg")

    def test_solver_unregistered_package_conflict(self) -> None:
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [PackageDependency("unregistered", VersionRange(">=1.0.0"))]
        )

    def test_solver_unsatisfiable_backtracking_conflict(self) -> None:
        self.checked_repo.register_package(PackageRelease("c", Version(2, 0, 0), ()))
        self.checked_repo.register_package(
            PackageRelease(
                "d",
                Version(2, 0, 0),
                (PackageDependency("c", VersionRange("==1.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "d",
                Version(1, 0, 0),
                (PackageDependency("c", VersionRange("==1.0.0")),),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [
                PackageDependency("c", VersionRange(">=1.0.0")),
                PackageDependency("d", VersionRange(">=1.0.0")),
            ]
        )


def make_sut() -> DependencySolver:
    """Initializes lifecycle scope for SemVerSolver singletons under test."""
    registry = get_default_registry()
    registry.register_singleton(VersionEngine)
    registry.register_singleton(PackageRepository)
    registry.register_singleton(DependencySolver)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(DependencySolver)


SemVerSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="SemVerSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:57:49Z
# LAST_CHANGED: 2026-11-13T22:56:39Z
# CHANGE: Add deterministic TestSemVerSolverImplReal coverage for ASCII-lexicographic prerelease string segment comparison and transitive constraint retraction during backtracking
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:57:49Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:57:20Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import functools
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from semver_solver_gemini_argon_1.parts.semver_solver.lib.semver_solver import (
    ComparatorOp,
    DependencySolver,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
    SemVerError,
    Version,
    VersionEngine,
    VersionRange,
)


# ==============================================================================
# Pure SemVer 2.0.0 Model Helpers (Zero while/lambda/nested-def/raise/try)
# ==============================================================================


def _format_version_raw(v: Version) -> str:
    return f"{v.major}.{v.minor}.{v.patch}"


def _parse_version_helper(text: str) -> Version:
    cleaned = text.strip()
    if "+" in cleaned:
        main_and_pre, build_str = cleaned.split("+", 1)
        build = tuple(build_str.split("."))
    else:
        main_and_pre = cleaned
        build = ()
    if "-" in main_and_pre:
        core_str, pre_str = main_and_pre.split("-", 1)
        prerelease = tuple(pre_str.split("."))
    else:
        core_str = main_and_pre
        prerelease = ()
    parts = core_str.split(".")
    return Version(
        major=int(parts[0]),
        minor=int(parts[1]),
        patch=int(parts[2]),
        prerelease=prerelease,
        build=build,
    )


def _compare_precedence_helper(v1: Version, v2: Version) -> int:
    c1 = (v1.major, v1.minor, v1.patch)
    c2 = (v2.major, v2.minor, v2.patch)
    if c1 < c2:
        return -1
    if c1 > c2:
        return 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for s1, s2 in zip(v1.prerelease, v2.prerelease):
        if s1 == s2:
            continue
        n1 = s1.isdigit()
        n2 = s2.isdigit()
        if n1 and n2:
            return -1 if int(s1) < int(s2) else 1
        if n1:
            return -1
        if n2:
            return 1
        return -1 if s1 < s2 else 1
    if len(v1.prerelease) < len(v2.prerelease):
        return -1
    if len(v1.prerelease) > len(v2.prerelease):
        return 1
    return 0


def _compare_releases_desc(r1: PackageRelease, r2: PackageRelease) -> int:
    return _compare_precedence_helper(r2.version, r1.version)


def _parse_atom(
    atom: str,
) -> Tuple[Optional[int], Optional[int], Optional[int], Tuple[str, ...]]:
    main_and_pre = atom.split("+", 1)[0]
    if "-" in main_and_pre:
        core_str, pre_str = main_and_pre.split("-", 1)
        prerelease: Tuple[str, ...] = tuple(pre_str.split("."))
    else:
        core_str = main_and_pre
        prerelease = ()
    parts = core_str.split(".")
    p0 = parts[0]
    if p0 in ("*", "x", "X"):
        return (None, None, None, ())
    major = int(p0)
    p1 = parts[1]
    if p1 in ("*", "x", "X"):
        return (major, None, None, ())
    minor = int(p1)
    p2 = parts[2]
    if p2 in ("*", "x", "X"):
        return (major, minor, None, ())
    return (major, minor, int(p2), prerelease)


def _normalize_clause_tokens(clause: str) -> Tuple[List[str], List[Tuple[int, int, int]]]:
    raw_tokens = clause.strip().split()
    merged: List[str] = []
    skip_until = -1
    for idx, tok in enumerate(raw_tokens):
        if idx < skip_until:
            continue
        if tok in (">=", "<=", "!=", "==", "=", ">", "<", "^", "~") and idx + 1 < len(raw_tokens):
            merged.append(tok + raw_tokens[idx + 1])
            skip_until = idx + 2
        else:
            merged.append(tok)

    expanded: List[str] = []
    pre_targets: List[Tuple[int, int, int]] = []
    skip_hyphen = -1
    for idx, tok in enumerate(merged):
        if idx < skip_hyphen:
            continue
        if idx + 2 < len(merged) and merged[idx + 1] == "-":
            low_tok = tok
            high_tok = merged[idx + 2]
            lmaj, lmin, lpat, lpre = _parse_atom(low_tok)
            if lmaj is not None:
                if lmin is None:
                    expanded.append(f">={lmaj}.0.0")
                elif lpat is None:
                    expanded.append(f">={lmaj}.{lmin}.0")
                else:
                    expanded.append(f">={low_tok}")
                    if lpre:
                        pre_targets.append((lmaj, lmin, lpat))
            hmaj, hmin, hpat, hpre = _parse_atom(high_tok)
            if hmaj is not None:
                if hmin is None:
                    expanded.append(f"<{hmaj + 1}.0.0")
                elif hpat is None:
                    expanded.append(f"<{hmaj}.{hmin + 1}.0")
                else:
                    expanded.append(f"<={high_tok}")
                    if hpre:
                        pre_targets.append((hmaj, hmin, hpat))
            skip_hyphen = idx + 3
        else:
            expanded.append(tok)
    return expanded, pre_targets


def _eval_single_token(
    version: Version,
    tok: str,
) -> Tuple[bool, Optional[Tuple[int, int, int]]]:
    if tok.startswith("^"):
        maj, min_v, pat, pre = _parse_atom(tok[1:])
        if maj is None:
            return True, None
        if min_v is None:
            low_v = Version(maj, 0, 0)
            high_v = Version(maj + 1, 0, 0)
            ok = (
                _compare_precedence_helper(version, low_v) >= 0
                and _compare_precedence_helper(version, high_v) < 0
            )
            return ok, None
        if pat is None:
            low_v = Version(maj, min_v, 0)
            high_v = Version(maj + 1, 0, 0) if maj > 0 else Version(0, min_v + 1, 0)
            ok = (
                _compare_precedence_helper(version, low_v) >= 0
                and _compare_precedence_helper(version, high_v) < 0
            )
            return ok, None
        low_v = Version(maj, min_v, pat, pre)
        if maj > 0:
            high_v = Version(maj + 1, 0, 0)
        elif min_v > 0:
            high_v = Version(0, min_v + 1, 0)
        else:
            high_v = Version(0, 0, pat + 1)
        ok = (
            _compare_precedence_helper(version, low_v) >= 0
            and _compare_precedence_helper(version, high_v) < 0
        )
        return ok, ((maj, min_v, pat) if pre else None)

    if tok.startswith("~"):
        maj, min_v, pat, pre = _parse_atom(tok[1:])
        if maj is None:
            return True, None
        if min_v is None:
            low_v = Version(maj, 0, 0)
            high_v = Version(maj + 1, 0, 0)
            ok = (
                _compare_precedence_helper(version, low_v) >= 0
                and _compare_precedence_helper(version, high_v) < 0
            )
            return ok, None
        low_v = Version(maj, min_v, pat or 0, pre if pat is not None else ())
        high_v = Version(maj, min_v + 1, 0)
        ok = (
            _compare_precedence_helper(version, low_v) >= 0
            and _compare_precedence_helper(version, high_v) < 0
        )
        return ok, ((maj, min_v, pat) if (pat is not None and pre) else None)

    op = "=="
    rest = tok
    for prefix in (">=", "<=", "!=", "==", ">", "<", "="):
        if tok.startswith(prefix):
            op = "==" if prefix == "=" else prefix
            rest = tok[len(prefix) :]
            break

    maj, min_v, pat, pre = _parse_atom(rest)
    if maj is None:
        return (op in ("==", ">=", "<=")), None
    if min_v is None or pat is None:
        low_v = Version(maj, min_v or 0, 0)
        high_v = Version(maj + 1, 0, 0) if min_v is None else Version(maj, min_v + 1, 0)
        c_low = _compare_precedence_helper(version, low_v)
        c_high = _compare_precedence_helper(version, high_v)
        if op == "==":
            return (c_low >= 0 and c_high < 0), None
        if op == "!=":
            return (c_low < 0 or c_high >= 0), None
        if op == ">=":
            return c_low >= 0, None
        if op == ">":
            return c_high >= 0, None
        if op == "<=":
            return c_high < 0, None
        return c_low < 0, None

    target_v = Version(maj, min_v, pat, pre)
    cmp_val = _compare_precedence_helper(version, target_v)
    pre_target = (maj, min_v, pat) if pre else None
    if op == "==":
        return cmp_val == 0, pre_target
    if op == "!=":
        return cmp_val != 0, pre_target
    if op == "<":
        return cmp_val < 0, pre_target
    if op == "<=":
        return cmp_val <= 0, pre_target
    if op == ">":
        return cmp_val > 0, pre_target
    return cmp_val >= 0, pre_target


def _satisfies_helper(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    clauses = range_constraint.raw_text.split("||")
    for clause in clauses:
        tokens, pre_targets = _normalize_clause_tokens(clause)
        clause_ok = True
        for tok in tokens:
            tok_ok, pre_t = _eval_single_token(version, tok)
            if pre_t is not None:
                pre_targets.append(pre_t)
            if not tok_ok:
                clause_ok = False
        if clause_ok:
            if version.prerelease and not include_prerelease:
                v_tuple = (version.major, version.minor, version.patch)
                if v_tuple not in pre_targets:
                    continue
            return True
    return False


def _backtrack_solve(
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]],
    assignment: Dict[str, PackageRelease],
    derivation_steps: List[str],
    packages: Mapping[str, Sequence[PackageRelease]],
) -> bool:
    unassigned = [p for p in accumulated_constraints if p not in assignment]
    if not unassigned:
        return True

    candidates_map: Dict[str, List[PackageRelease]] = {}
    for pkg in unassigned:
        available = list(packages.get(pkg, ()))
        viable: List[PackageRelease] = []
        for rel in available:
            ok = True
            for _, rng in accumulated_constraints[pkg]:
                if not _satisfies_helper(rel.version, rng, False):
                    ok = False
                    break
            if ok:
                viable.append(rel)
        candidates_map[pkg] = viable

    selected_pkg = unassigned[0]
    selected_key = (len(candidates_map[selected_pkg]), selected_pkg)
    for pkg in unassigned[1:]:
        cand_key = (len(candidates_map[pkg]), pkg)
        if cand_key < selected_key:
            selected_pkg = pkg
            selected_key = cand_key

    candidates = candidates_map[selected_pkg]
    if not candidates:
        return False

    for candidate in candidates:
        assignment[selected_pkg] = candidate
        derivation_steps.append(
            f"Assign '{selected_pkg}' to {_format_version_raw(candidate.version)}"
        )
        conflict_detected = False
        newly_added: List[Tuple[str, Tuple[str, VersionRange]]] = []
        for dep in candidate.dependencies:
            if dep.name in assignment:
                if not _satisfies_helper(
                    assignment[dep.name].version,
                    dep.range_constraint,
                    False,
                ):
                    conflict_detected = True
                    break
            else:
                entry = (selected_pkg, dep.range_constraint)
                accumulated_constraints.setdefault(dep.name, []).append(entry)
                newly_added.append((dep.name, entry))

        if not conflict_detected and _backtrack_solve(
            accumulated_constraints,
            assignment,
            derivation_steps,
            packages,
        ):
            return True

        for pkg_name, entry in newly_added:
            accumulated_constraints[pkg_name].remove(entry)
            if not accumulated_constraints[pkg_name]:
                del accumulated_constraints[pkg_name]
        del assignment[selected_pkg]
        derivation_steps.pop()

    return False


def _resolve_helper(
    root_dependencies: Collection[PackageDependency],
    packages: Mapping[str, Sequence[PackageRelease]],
) -> ResolutionOutcome:
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]] = {}
    for dep in root_dependencies:
        accumulated_constraints.setdefault(dep.name, []).append(
            ("root", dep.range_constraint)
        )
    assignment: Dict[str, PackageRelease] = {}
    derivation_steps: List[str] = []
    _backtrack_solve(accumulated_constraints, assignment, derivation_steps, packages)
    selected_versions: Dict[str, Version] = {
        pkg: rel.version for pkg, rel in assignment.items()
    }
    return ResolutionOutcome(
        selected_versions=selected_versions,
        derivation_steps=tuple(derivation_steps),
    )


def _compute_resolvable_dep_sets(
    packages: Mapping[str, Sequence[PackageRelease]],
) -> List[List[PackageDependency]]:
    dep_sets: List[List[PackageDependency]] = []
    for pkg_name in sorted(packages.keys()):
        candidate_deps = [
            PackageDependency(pkg_name, VersionRange(">=0.0.0")),
        ]
        accumulated: Dict[str, List[Tuple[str, VersionRange]]] = {
            pkg_name: [("root", VersionRange(">=0.0.0"))]
        }
        assignment: Dict[str, PackageRelease] = {}
        steps: List[str] = []
        if _backtrack_solve(accumulated, assignment, steps, packages):
            dep_sets.append(candidate_deps)
    return dep_sets


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class SemVerSolverState:
    """Canonical model state tracking registered package releases and domain fixtures."""

    initialized: bool = True
    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)
    valid_version_texts: list[str] = field(default_factory=list)
    valid_versions: list[Version] = field(default_factory=list)
    valid_range_texts: list[str] = field(default_factory=list)
    valid_ranges: list[VersionRange] = field(default_factory=list)
    candidate_releases: list[PackageRelease] = field(default_factory=list)
    unregistered_releases: list[PackageRelease] = field(default_factory=list)
    candidate_package_names: list[str] = field(default_factory=list)
    resolvable_dep_sets: list[list[PackageDependency]] = field(default_factory=list)


class SemVerSolverStateMachine(StateMachine[SemVerSolverState]):
    """Unified Pretense State Machine for SemVerSolver services."""

    def __init__(
        self,
        state: Optional[SemVerSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state or self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> SemVerSolverState:
        """Constructs initial model state with parameterized fixture pools."""
        version_texts = [
            "0.0.4",
            "0.2.3",
            "1.0.0-alpha.1",
            "1.0.0-alpha.2",
            "1.0.0-alpha.beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0+20130313144700",
            "1.0.0",
            "1.2.0",
            "1.2.3",
            "2.0.0",
        ]
        versions = [_parse_version_helper(t) for t in version_texts]
        range_texts = [
            ">=1.0.0 <2.0.0",
            "^1.0.0",
            "^0.2.3",
            "^0.0.4",
            "^1.x",
            "^1.2.x",
            "^0.2.x",
            "~1.2.0",
            "~1.x",
            "~1.2.x",
            "1.0.0 - 2.0.0",
            "1.0.0 - 2.x",
            "1.x - 2.x",
            "1.0.x - 1.2.x",
            ">=1.x",
            "!=1.x",
            ">1.x",
            "<=1.x",
            "<1.x",
            "==1.2.x",
            "*",
            "!=1.0.0",
            "<=1.2.0",
            ">1.0.0",
            "=1.0.0",
            ">= 1.0.0 < 2.0.0",
            ">=1.0.0-alpha.1 <1.0.0",
            "1.0.0-alpha.1 - 1.0.0-beta.11",
            "^1.0.0-alpha.1",
            "~1.0.0-alpha.1",
            "==1.0.0 || >=2.0.0",
        ]
        ranges = [VersionRange(t.strip()) for t in range_texts]

        releases: list[PackageRelease] = []
        for idx in range(25):
            releases.append(
                PackageRelease(
                    name="core",
                    version=Version(1, idx, 0),
                    dependencies=(),
                )
            )
        for idx in range(20):
            releases.append(
                PackageRelease(
                    name="utils",
                    version=Version(1, idx, 0),
                    dependencies=(
                        PackageDependency("core", VersionRange("^1.0.0")),
                    ),
                )
            )
        for idx in range(15):
            releases.append(
                PackageRelease(
                    name="app",
                    version=Version(1, idx, 0),
                    dependencies=(
                        PackageDependency("utils", VersionRange(">=1.0.0")),
                        PackageDependency("core", VersionRange("^1.0.0")),
                    ),
                )
            )

        return SemVerSolverState(
            initialized=True,
            packages={},
            valid_version_texts=version_texts,
            valid_versions=versions,
            valid_range_texts=range_texts,
            valid_ranges=ranges,
            candidate_releases=list(releases),
            unregistered_releases=list(releases),
            candidate_package_names=["core", "utils", "app", "missing_pkg"],
            resolvable_dep_sets=[],
        )

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.text(min_size=1),
            preferred=self.state.valid_version_texts,
            fuzz_domain=Domain.sampled_from(self.state.valid_version_texts),
        )
        ret = self.inner_parse_version(text)
        expected = _parse_version_helper(text)
        assert isinstance(ret, Version)
        assert ret == expected
        return ret

    def inner_parse_version(self, text: str) -> Version:
        return _parse_version_helper(text)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(
            v1,
            Domain.type(Version),
            preferred=self.state.valid_versions,
            fuzz_domain=Domain.sampled_from(self.state.valid_versions),
        )
        require_arg(
            v2,
            Domain.type(Version),
            preferred=self.state.valid_versions,
            fuzz_domain=Domain.sampled_from(self.state.valid_versions),
        )
        ret = self.inner_compare_precedence(v1, v2)
        expected = _compare_precedence_helper(v1, v2)
        if expected < 0:
            assert ret < 0
        elif expected > 0:
            assert ret > 0
        else:
            assert ret == 0
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        return _compare_precedence_helper(v1, v2)

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.text(min_size=1),
            preferred=self.state.valid_range_texts,
            fuzz_domain=Domain.sampled_from(self.state.valid_range_texts),
        )
        ret = self.inner_parse_range(text)
        assert isinstance(ret, VersionRange)
        assert ret.raw_text == ret.raw_text.strip()
        assert bool(ret.raw_text)
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        return VersionRange(raw_text=text.strip())

    @transition(VersionEngine.satisfies)
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
            preferred=self.state.valid_versions,
            fuzz_domain=Domain.sampled_from(self.state.valid_versions),
        )
        require_arg(
            range_constraint,
            Domain.type(VersionRange),
            preferred=self.state.valid_ranges,
            fuzz_domain=Domain.sampled_from(self.state.valid_ranges),
        )
        require_arg(
            include_prerelease,
            Domain.type(bool),
            preferred=[False, True],
            fuzz_domain=Domain.sampled_from([False, True]),
        )
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        expected = _satisfies_helper(version, range_constraint, include_prerelease)
        assert ret == expected
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        return _satisfies_helper(version, range_constraint, include_prerelease)

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(bool(self.state.unregistered_releases))
        require_arg(
            release,
            Domain.type(PackageRelease),
            preferred=self.state.unregistered_releases,
            fuzz_domain=Domain.sampled_from(self.state.unregistered_releases),
        )
        ret = self.inner_register_package(release)
        if release in self.state.unregistered_releases:
            self.state.unregistered_releases.remove(release)
        existing = list(self.state.packages.get(release.name, []))
        existing.append(release)
        existing.sort(key=functools.cmp_to_key(_compare_releases_desc))
        self.state.packages[release.name] = existing
        self.state.resolvable_dep_sets = _compute_resolvable_dep_sets(
            self.state.packages
        )
        assert release.name in self.state.packages
        return ret

    def inner_register_package(self, release: PackageRelease) -> None:
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(bool(self.state.packages))
        require_arg(name, Domain.in_set(self.state.packages))
        ret = self.inner_get_releases(name)
        assert ret == self.state.packages[name]
        return ret

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        return list(self.state.packages[name])

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.text(min_size=1),
            preferred=self.state.candidate_package_names,
            fuzz_domain=Domain.sampled_from(self.state.candidate_package_names),
        )
        ret = self.inner_has_package(name)
        assert ret == (name in self.state.packages)
        return ret

    def inner_has_package(self, name: str) -> bool:
        return name in self.state.packages

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        require(self.state.initialized)
        ret = self.inner_all_packages()
        assert ret == set(self.state.packages.keys())
        return ret

    def inner_all_packages(self) -> Set[str]:
        return set(self.state.packages.keys())

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(bool(self.state.resolvable_dep_sets))
        require_arg(
            root_dependencies,
            Domain.collection(Domain.type(PackageDependency)),
            preferred=self.state.resolvable_dep_sets,
            fuzz_domain=Domain.sampled_from(self.state.resolvable_dep_sets),
        )
        ret = self.inner_resolve(root_dependencies)
        expected = _resolve_helper(root_dependencies, self.state.packages)
        assert dict(ret.selected_versions) == dict(expected.selected_versions)
        assert isinstance(ret.derivation_steps, tuple)
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        return _resolve_helper(root_dependencies, self.state.packages)


proto = SemVerSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeSemVerSolver = synthesize_fake(SemVerSolverStateMachine)


def make_semver_solver_fake(
    state: Optional[SemVerSolverState] = None,
) -> Any:
    """Synthesizes fake instance for SemVerSolver."""
    return FakeSemVerSolver(state=state or proto.make_initial_state())


def make_semver_solver_fakes(
    state: Optional[SemVerSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    fake_instance = FakeSemVerSolver(state=state or proto.make_initial_state())
    return (fake_instance, fake_instance, fake_instance)


FakeSemVerSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemVerSolverFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestSemVerSolverFake(unittest.TestCase):
    """Fixed fake tests exercising transitions and branch edge cases not guaranteed by fuzzing."""

    def setUp(self) -> None:
        self.engine, self.repo, self.solver = make_semver_solver_fakes()
        self.sm = SemVerSolverStateMachine(
            singletons={
                VersionEngine: self.engine,
                PackageRepository: self.repo,
                DependencySolver: self.solver,
            }
        )

    def test_fake_transitions_and_helper_branches(self) -> None:
        """Exercises seeding, range edge cases, precedence comparisons, and backtracking."""
        self.sm.seed_initial()
        _ = make_semver_solver_fake()

        v_plain = self.engine.parse_version("1.0.0")
        v_pre1 = self.engine.parse_version("1.0.0-alpha.1")
        v_pre2 = self.engine.parse_version("1.0.0-alpha.2")
        v_pre_str = self.engine.parse_version("1.0.0-alpha.beta")
        v_pre_short = self.engine.parse_version("1.0.0-alpha")
        v_build = self.engine.parse_version("1.0.0+build.1")
        v_high = self.engine.parse_version("2.0.0")

        assert self.engine.compare_precedence(v_plain, v_high) < 0
        assert self.engine.compare_precedence(v_high, v_plain) > 0
        assert self.engine.compare_precedence(v_plain, v_build) == 0
        assert self.engine.compare_precedence(v_plain, v_pre1) > 0
        assert self.engine.compare_precedence(v_pre1, v_plain) < 0
        assert self.engine.compare_precedence(v_pre1, v_pre2) < 0
        assert self.engine.compare_precedence(v_pre2, v_pre1) > 0
        assert self.engine.compare_precedence(v_pre1, v_pre_str) < 0
        assert self.engine.compare_precedence(v_pre_str, v_pre1) > 0
        assert self.engine.compare_precedence(v_pre_str, v_pre_short) > 0
        assert self.engine.compare_precedence(v_pre_short, v_pre_str) < 0
        assert self.engine.compare_precedence(v_pre1, v_pre1) == 0
        assert (
            self.engine.compare_precedence(
                Version(1, 0, 0, ("beta",), ()),
                Version(1, 0, 0, ("alpha",), ()),
            )
            > 0
        )

        for rng_text in [
            "*",
            "^*",
            "~*",
            "^1.x",
            "^1.2.x",
            "^0.2.x",
            "^1.0.0",
            "^0.2.3",
            "^0.0.4",
            "~1.x",
            "~1.2.x",
            "~1.2.3",
            "==1.x",
            "!=1.x",
            ">=1.x",
            ">1.x",
            "<=1.x",
            "<1.x",
            "==1.2.x",
            "==1.0.0",
            "!=1.0.0",
            "<2.0.0",
            "<=1.0.0",
            ">0.5.0",
            ">=1.0.0",
            "=1.0.0",
            ">= 1.0.0 < 2.0.0",
            "* - *",
            "1.x - 2.x",
            "1.0.x - 1.2.x",
            "1.0.0 - 2.0.0",
            "1.0.0-alpha.1 - 1.0.0-beta.1",
            ">=1.0.0-alpha.1 <1.0.0",
            "^1.0.0-alpha.1",
            "~1.0.0-alpha.1",
        ]:
            rng = self.engine.parse_range(rng_text)
            self.engine.satisfies(v_plain, rng, False)
            self.engine.satisfies(v_pre1, rng, False)
            self.engine.satisfies(v_pre1, rng, True)

        # Backtracking conflict branch coverage on fake
        r_c1 = PackageRelease("c", Version(1, 0, 0), ())
        r_c2 = PackageRelease("c", Version(2, 0, 0), ())
        r_a = PackageRelease(
            "a",
            Version(1, 0, 0),
            (
                PackageDependency("c", VersionRange(">=1.0.0")),
                PackageDependency("b", VersionRange("==1.0.0")),
            ),
        )
        r_b = PackageRelease(
            "b",
            Version(1, 0, 0),
            (PackageDependency("c", VersionRange("==1.0.0")),),
        )
        self.repo.register_package(r_c1)
        self.repo.register_package(r_c2)
        self.repo.register_package(r_a)
        self.repo.register_package(r_b)
        assert self.repo.has_package("a")
        assert not self.repo.has_package("nonexistent")
        assert "a" in self.repo.all_packages()
        assert len(self.repo.get_releases("c")) == 2

        outcome = self.solver.resolve(
            [
                PackageDependency("a", VersionRange("==1.0.0")),
                PackageDependency("b", VersionRange("==1.0.0")),
            ]
        )
        assert outcome.selected_versions["c"] == Version(1, 0, 0)

        # Unsatisfiable helper path for coverage of empty candidates / exhaust
        empty_outcome = _resolve_helper(
            [PackageDependency("missing", VersionRange(">=1.0.0"))],
            {},
        )
        assert dict(empty_outcome.selected_versions) == {}

        exhaust_outcome = _resolve_helper(
            [
                PackageDependency("c", VersionRange(">=1.0.0")),
                PackageDependency("d", VersionRange(">=1.0.0")),
            ],
            {
                "c": [r_c2],
                "d": [
                    PackageRelease(
                        "d",
                        Version(2, 0, 0),
                        (PackageDependency("c", VersionRange("==1.0.0")),),
                    ),
                    PackageRelease(
                        "d",
                        Version(1, 0, 0),
                        (PackageDependency("c", VersionRange("==1.0.0")),),
                    ),
                ],
            },
        )
        assert dict(exhaust_outcome.selected_versions) == {}

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:46:35Z
# LAST_CHANGED: 2026-11-13T22:46:35Z
# CHANGE: Implement SemVerSolverStateMachine, synthesized fakes, fake fuzzing, and 100% branch-covered fake tests
# --- END AUTOFAB METADATA ---
