# === File: semver_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Collection, List, Set

from pretense import StateMachine, sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from semver_solver_gemini_carbon_1.parts.semver_solver.lib import semver_solver_impl
from semver_solver_gemini_carbon_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)
from semver_solver_gemini_carbon_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver as DependencySolverImpl,
    PackageRepository as PackageRepositoryImpl,
    VersionEngine as VersionEngineImpl,
)
from semver_solver_gemini_carbon_1.parts.semver_solver.pretense.semver_solver_pretense import (
    SemverSolverStateMachine,
    VALID_RANGE_STRINGS,
)


class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine driving concrete semver_solver_impl singletons."""

    def inner_parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = target.parse_version(text)
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = target.compare_precedence(v1, v2)
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret = target.parse_range(text)
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


proto = SemverSolverImplPseudoStateMachine()


def make_sut() -> dict[type[Any], Any]:
    """Constructs isolated lifecycle scope with concrete SemVer singletons."""
    registry = LifecycleRegistry()
    registry.register_singleton(
        VersionEngineImpl,
        keys=[VersionEngineImpl, VersionEngine],
        tier=system,
    )
    registry.register_singleton(
        PackageRepositoryImpl,
        keys=[PackageRepositoryImpl, PackageRepository],
        tier=system,
    )
    registry.register_singleton(
        DependencySolverImpl,
        keys=[DependencySolverImpl, DependencySolver],
        tier=system,
    )
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return {
        VersionEngine: get_singleton(VersionEngine),
        PackageRepository: get_singleton(PackageRepository),
        DependencySolver: get_singleton(DependencySolver),
    }


SemverSolverImplFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="SemverSolverImplFuzzTest",
)


class TestSemverSolverImplReal(LifecycleTestCase):
    """Fixed scenario tests verifying concrete implementation branches, backtracking, and contracted errors."""

    target = semver_solver_impl

    def setUp(self) -> None:
        super().setUp()
        eng = get_singleton(VersionEngine)
        repo = get_singleton(PackageRepository)
        solver = get_singleton(DependencySolver)
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: eng,
                PackageRepository: repo,
                DependencySolver: solver,
            }
        )
        self.checked_engine = self.sm.as_checked(VersionEngine, eng)
        self.checked_repo = self.sm.as_checked(PackageRepository, repo)
        self.checked_solver = self.sm.as_checked(DependencySolver, solver)

    def test_version_parsing_and_precedence_scenarios(self) -> None:
        v_zero = self.checked_engine.parse_version("0.0.0")
        v_pre_a = self.checked_engine.parse_version("1.0.0-alpha")
        v_pre_a1 = self.checked_engine.parse_version("1.0.0-alpha.1")
        v_pre_ab = self.checked_engine.parse_version("1.0.0-alpha.beta")
        v_pre_b = self.checked_engine.parse_version("1.0.0-beta")
        v_pre_b2 = self.checked_engine.parse_version("1.0.0-beta.2")
        v_pre_b11 = self.checked_engine.parse_version("1.0.0-beta.11")
        v_norm = self.checked_engine.parse_version("1.0.0")
        v_build1 = self.checked_engine.parse_version("1.0.0+20130313144700")
        v_build2 = self.checked_engine.parse_version("1.0.0-beta+exp.sha.5114f85")
        v_two = self.checked_engine.parse_version("2.0.0")

        self.checked_engine.compare_precedence(v_zero, v_norm)
        self.checked_engine.compare_precedence(v_two, v_norm)
        self.checked_engine.compare_precedence(Version(1, 1, 0), Version(1, 2, 0))
        self.checked_engine.compare_precedence(Version(1, 2, 0), Version(1, 1, 0))
        self.checked_engine.compare_precedence(Version(1, 2, 1), Version(1, 2, 3))
        self.checked_engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 1))
        self.checked_engine.compare_precedence(v_pre_a, v_norm)
        self.checked_engine.compare_precedence(v_norm, v_pre_a)
        # String vs string prerelease ordering (both directions & equal)
        self.checked_engine.compare_precedence(v_pre_a, v_pre_b)
        self.checked_engine.compare_precedence(v_pre_b, v_pre_a)
        self.checked_engine.compare_precedence(v_pre_a, v_pre_a)
        # Prefix length ordering
        self.checked_engine.compare_precedence(v_pre_a, v_pre_a1)
        self.checked_engine.compare_precedence(v_pre_a1, v_pre_a)
        # Numeric vs string prerelease ordering
        self.checked_engine.compare_precedence(v_pre_a1, v_pre_ab)
        self.checked_engine.compare_precedence(v_pre_ab, v_pre_a1)
        # Numeric vs numeric prerelease ordering (both directions & equal)
        self.checked_engine.compare_precedence(v_pre_b2, v_pre_b11)
        self.checked_engine.compare_precedence(v_pre_b11, v_pre_b2)
        self.checked_engine.compare_precedence(v_pre_b2, v_pre_b2)
        # Build metadata ignored
        self.checked_engine.compare_precedence(v_norm, v_build1)
        self.checked_engine.compare_precedence(v_build2, v_pre_b2)
        self.checked_engine.compare_precedence(v_build2, v_pre_b)

    def test_range_parsing_and_satisfaction_scenarios(self) -> None:
        parsed_ranges = [
            self.checked_engine.parse_range(raw) for raw in VALID_RANGE_STRINGS
        ]
        candidate_versions = (
            Version(0, 0, 0),
            Version(0, 0, 1),
            Version(0, 1, 0),
            Version(1, 0, 0, prerelease=("alpha",)),
            Version(1, 0, 0, prerelease=("alpha", "1")),
            Version(1, 0, 0, prerelease=("beta",)),
            Version(1, 0, 0),
            Version(1, 2, 0),
            Version(1, 2, 3),
            Version(1, 3, 0),
            Version(2, 0, 0, prerelease=("alpha",)),
            Version(2, 0, 0, prerelease=("beta",)),
            Version(2, 0, 0),
            Version(3, 0, 0),
        )
        for rng in parsed_ranges:
            for ver in candidate_versions:
                self.checked_engine.satisfies(ver, rng, False)
                self.checked_engine.satisfies(ver, rng, True)

    def test_repository_and_solver_compatible_assignment_with_backtracking(self) -> None:
        self.checked_repo.has_package("util")
        self.checked_repo.all_packages()
        self.checked_solver.resolve([])

        # Register releases that exercise MRV selection, descending precedence, and backtracking:
        # 'app' 1.0.0 requires 'core' >=1.0.0 and 'util' ^1.0.0.
        # 'core' 2.0.0 (tried first due to higher precedence) requires 'util' ^2.0.0 -> conflicts & backtracks to 'core' 1.0.0!
        self.checked_repo.register_package(
            PackageRelease("util", Version(1, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease("util", Version(1, 2, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease("util", Version(2, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease(
                "core",
                Version(1, 0, 0),
                (PackageDependency("util", VersionRange("^1.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "core",
                Version(2, 0, 0),
                (PackageDependency("util", VersionRange("^2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                (
                    PackageDependency("core", VersionRange(">=1.0.0")),
                    PackageDependency("util", VersionRange("^1.0.0")),
                ),
            )
        )

        self.checked_repo.has_package("util")
        self.checked_repo.all_packages()
        self.checked_repo.get_releases("util")
        self.checked_solver.resolve([PackageDependency("app", VersionRange("*"))])

    def test_solver_forward_check_conflict_backtracking(self) -> None:
        # 'entry' 1.0.0 depends on 'p' (*) and 'q' (*).
        # 'p' has 1 release (1.0.0) -> MRV selects 'p' before 'q' (2 releases)!
        # Then 'q' 2.0.0 requires 'p' >=2.0.0 (already assigned 'p'=1.0.0 fails forward check!),
        # backtracks to 'q' 1.0.0 requiring 'p' >=1.0.0 -> succeeds!
        self.checked_repo.register_package(
            PackageRelease("p", Version(1, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease(
                "q",
                Version(2, 0, 0),
                (PackageDependency("p", VersionRange(">=2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "q",
                Version(1, 0, 0),
                (PackageDependency("p", VersionRange(">=1.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "entry",
                Version(1, 0, 0),
                (
                    PackageDependency("p", VersionRange("*")),
                    PackageDependency("q", VersionRange("*")),
                ),
            )
        )
        self.checked_solver.resolve([PackageDependency("entry", VersionRange("*"))])

    def test_invalid_version_leading_zero_error(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("01.0.0")

    def test_invalid_version_malformed_grammar_error(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("1.0")

    def test_invalid_version_prerelease_leading_zero_error(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("1.0.0-01")

    def test_invalid_range_bare_partial_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.2")

    def test_invalid_range_bare_single_major_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1")

    def test_invalid_range_caret_bare_partial_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("^0.0")

    def test_invalid_range_operator_bare_partial_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">1.2")

    def test_invalid_range_hyphen_bare_partial_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.2 - 2.3")

    def test_invalid_range_hyphen_right_bare_partial_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.0.0 - 2.3")

    def test_invalid_range_dangling_hyphen_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.0.0 -")

    def test_invalid_range_leading_hyphen_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("- 1.0.0")

    def test_invalid_range_bare_hyphen_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("-")

    def test_invalid_range_dangling_operator_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">=")

    def test_invalid_range_double_operator_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("> >=1.0.0")

    def test_invalid_range_operator_hyphen_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">= 1.0.0 - 2.0.0")

    def test_invalid_range_unknown_operator_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("===1.0.0")

    def test_invalid_range_wildcard_before_number_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("*.1.0")

    def test_invalid_range_major_wildcard_patch_number_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.x.0")

    def test_invalid_range_wildcard_with_prerelease_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.x-alpha")

    def test_invalid_range_four_segments_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.0.0.0")

    def test_invalid_range_leading_zero_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">=01.0.0")

    def test_invalid_range_comma_delimiter_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">=1.0.0, <2.0.0")

    def test_invalid_range_empty_union_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.0.0 || ")

    def test_invalid_range_leading_union_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("|| 1.0.0")

    def test_invalid_range_empty_string_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("")

    def test_invalid_range_empty_whitespace_error(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("   ")

    def test_repository_missing_package_error(self) -> None:
        self.checked_repo.violating(PackageNotFoundError).get_releases("missing_pkg")

    def test_solver_unregistered_package_conflict_error(self) -> None:
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [PackageDependency("unregistered_pkg", VersionRange(">=1.0.0"))]
        )

    def test_solver_mutually_incompatible_conflict_error(self) -> None:
        self.checked_repo.register_package(
            PackageRelease("util", Version(1, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease(
                "left",
                Version(1, 0, 0),
                (PackageDependency("util", VersionRange(">=2.0.0")),),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [PackageDependency("left", VersionRange("*"))]
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T23:07:18Z
# LAST_CHANGED: 2026-11-13T23:05:40Z
# CHANGE: Exercise string prerelease precedence ordering, all wildcard relational comparators, hyphen prerelease bounds, and comprehensive InvalidRangeError malformed syntax scenarios in TestSemverSolverImplReal
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T23:07:18Z
# PRETENSE_QA_AUDIT: 2026-11-13T23:06:37Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

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

from semver_solver_gemini_carbon_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)


# ==============================================================================
# 0. Pure SemVer 2.0.0 Reference Algebra Helpers (No while loops, no lambdas)
# ==============================================================================


def _is_non_neg_int(token: str) -> bool:
    return bool(token) and token.isdigit() and token.isascii() and (len(token) == 1 or not token.startswith("0"))


def _is_ident_chars(token: str) -> bool:
    return bool(token) and all(ch.isascii() and (ch.isalnum() or ch == "-") for ch in token)


def _is_prerelease_ident(token: str) -> bool:
    return _is_non_neg_int(token) if (token.isdigit() and token.isascii()) else _is_ident_chars(token)


def parse_semver_text(text: str) -> Optional[Version]:
    """Parses valid SemVer 2.0.0 version string or returns None."""
    if not text or text != text.strip():
        return None
    build_parts: Tuple[str, ...] = ()
    rest = text
    if "+" in rest:
        before_plus, after_plus = rest.split("+", 1)
        raw_builds = after_plus.split(".")
        if not after_plus or not all(_is_ident_chars(b) for b in raw_builds):
            return None
        build_parts = tuple(raw_builds)
        rest = before_plus

    prerelease_parts: Tuple[str, ...] = ()
    if "-" in rest:
        before_dash, after_dash = rest.split("-", 1)
        raw_pres = after_dash.split(".")
        if not after_dash or not all(_is_prerelease_ident(p) for p in raw_pres):
            return None
        prerelease_parts = tuple(raw_pres)
        rest = before_dash

    core_parts = rest.split(".")
    if len(core_parts) != 3 or not all(_is_non_neg_int(c) for c in core_parts):
        return None
    return Version(
        major=int(core_parts[0]),
        minor=int(core_parts[1]),
        patch=int(core_parts[2]),
        prerelease=prerelease_parts,
        build=build_parts,
    )


def compare_semver(v1: Version, v2: Version) -> int:
    """Computes SemVer 2.0.0 precedence (-1, 0, or 1), ignoring build metadata."""
    core1 = (v1.major, v1.minor, v1.patch)
    core2 = (v2.major, v2.minor, v2.patch)
    if core1 != core2:
        return -1 if core1 < core2 else 1

    pre1, pre2 = v1.prerelease, v2.prerelease
    if not pre1 and not pre2:
        return 0
    if not pre1 or not pre2:
        return 1 if not pre1 else -1

    for s1, s2 in zip(pre1, pre2):
        if s1 == s2:
            continue
        n1 = s1.isdigit() and s1.isascii()
        n2 = s2.isdigit() and s2.isascii()
        if n1 and n2:
            return -1 if int(s1) < int(s2) else 1
        if n1 != n2:
            return -1 if n1 else 1
        return -1 if s1 < s2 else 1

    if len(pre1) == len(pre2):
        return 0
    return -1 if len(pre1) < len(pre2) else 1


def sort_releases_descending(releases: Sequence[PackageRelease]) -> List[PackageRelease]:
    """Sorts PackageRelease sequence in descending version precedence order."""
    result: List[PackageRelease] = []
    for rel in releases:
        pos = len(result)
        for idx, existing in enumerate(result):
            if compare_semver(rel.version, existing.version) > 0:
                pos = idx
                break
        result.insert(pos, rel)
    return result


@dataclass(frozen=True)
class _TargetSpec:
    kind: str  # "any", "major_w", "minor_w", "full"
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: Tuple[str, ...] = ()


_WILDCARDS = ("*", "x", "X")
_OPERATORS = ("==", "!=", ">=", "<=", "=", ">", "<", "^", "~")


def _parse_target_spec(token: str) -> Optional[_TargetSpec]:
    if token in _WILDCARDS:
        return _TargetSpec(kind="any")
    full = parse_semver_text(token)
    if full is not None:
        return _TargetSpec("full", full.major, full.minor, full.patch, full.prerelease)
    if not token or "-" in token or "+" in token:
        return None
    parts = token.split(".")
    if len(parts) == 2 and parts[1] in _WILDCARDS:
        if parts[0] in _WILDCARDS:
            return _TargetSpec(kind="any")
        if _is_non_neg_int(parts[0]):
            return _TargetSpec(kind="major_w", major=int(parts[0]))
    if len(parts) == 3 and parts[2] in _WILDCARDS:
        if parts[0] in _WILDCARDS and parts[1] in _WILDCARDS:
            return _TargetSpec(kind="any")
        if _is_non_neg_int(parts[0]) and parts[1] in _WILDCARDS:
            return _TargetSpec(kind="major_w", major=int(parts[0]))
        if _is_non_neg_int(parts[0]) and _is_non_neg_int(parts[1]):
            return _TargetSpec(kind="minor_w", major=int(parts[0]), minor=int(parts[1]))
    return None


@dataclass(frozen=True)
class _AtomCmp:
    op: str  # "==", "!=", "<", "<=", ">", ">=", "NONE"
    target: Version


def _lower_bound(tgt: _TargetSpec) -> Version:
    if tgt.kind == "any":
        return Version(0, 0, 0)
    if tgt.kind == "major_w":
        return Version(tgt.major, 0, 0)
    if tgt.kind == "minor_w":
        return Version(tgt.major, tgt.minor, 0)
    return Version(tgt.major, tgt.minor, tgt.patch, tgt.prerelease)


def _upper_excl_wildcard(tgt: _TargetSpec) -> Version:
    if tgt.kind == "major_w":
        return Version(tgt.major + 1, 0, 0)
    return Version(tgt.major, tgt.minor + 1, 0)


def _expand_prefixed(op: str, tgt: _TargetSpec) -> List[List[_AtomCmp]]:
    v0 = Version(0, 0, 0)
    norm_op = "==" if op in ("", "=") else op

    if tgt.kind == "any":
        if norm_op in ("!=", ">", "<"):
            return [[_AtomCmp("NONE", v0)]]
        return [[_AtomCmp(">=", v0)]]

    low = _lower_bound(tgt)
    if tgt.kind in ("major_w", "minor_w"):
        high = _upper_excl_wildcard(tgt)
        if norm_op in ("==", "~"):
            return [[_AtomCmp(">=", low), _AtomCmp("<", high)]]
        if norm_op == "!=":
            return [[_AtomCmp("<", low)], [_AtomCmp(">=", high)]]
        if norm_op == ">=":
            return [[_AtomCmp(">=", low)]]
        if norm_op == ">":
            return [[_AtomCmp(">=", high)]]
        if norm_op == "<=":
            return [[_AtomCmp("<", high)]]
        if norm_op == "<":
            return [[_AtomCmp("<", low)]]
        # norm_op == "^"
        caret_high = (
            Version(tgt.major + 1, 0, 0)
            if (tgt.kind == "major_w" or tgt.major > 0)
            else Version(0, tgt.minor + 1, 0)
        )
        return [[_AtomCmp(">=", low), _AtomCmp("<", caret_high)]]

    # tgt.kind == "full"
    if norm_op in ("==", "!=", ">=", ">", "<=", "<"):
        return [[_AtomCmp(norm_op, low)]]
    if norm_op == "~":
        return [[_AtomCmp(">=", low), _AtomCmp("<", Version(tgt.major, tgt.minor + 1, 0))]]
    # norm_op == "^"
    if tgt.major > 0:
        c_high = Version(tgt.major + 1, 0, 0)
    elif tgt.minor > 0:
        c_high = Version(0, tgt.minor + 1, 0)
    else:
        c_high = Version(0, 0, tgt.patch + 1)
    return [[_AtomCmp(">=", low), _AtomCmp("<", c_high)]]


def _expand_hyphen(b1: _TargetSpec, b2: _TargetSpec) -> List[List[_AtomCmp]]:
    low_atom = _AtomCmp(">=", _lower_bound(b1))
    if b2.kind == "any":
        return [[low_atom]]
    if b2.kind in ("major_w", "minor_w"):
        return [[low_atom, _AtomCmp("<", _upper_excl_wildcard(b2))]]
    return [[low_atom, _AtomCmp("<=", _lower_bound(b2))]]


def _parse_clause_to_dnf(clause_str: str) -> Optional[List[List[_AtomCmp]]]:
    raw_tokens = clause_str.split()

    items: List[Tuple[str, str, Optional[str]]] = []
    skip = 0
    n = len(raw_tokens)
    for i, tok in enumerate(raw_tokens):
        if skip > 0:
            skip -= 1
            continue
        if i + 2 < n and raw_tokens[i + 1] == "-":
            items.append(("HYPHEN", tok, raw_tokens[i + 2]))
            skip = 2
        elif tok == "-":
            return None
        elif tok in _OPERATORS:
            if i + 1 >= n or raw_tokens[i + 1] in _OPERATORS or raw_tokens[i + 1] == "-":
                return None
            items.append((tok, raw_tokens[i + 1], None))
            skip = 1
        else:
            matched_op = ""
            rest_tok = tok
            for op in _OPERATORS:
                if tok.startswith(op):
                    matched_op = op
                    rest_tok = tok[len(op) :]
                    break
            items.append((matched_op, rest_tok, None))

    clauses_dnf: List[List[_AtomCmp]] = [[]]
    for kind_or_op, t1_str, t2_str in items:
        b1 = _parse_target_spec(t1_str)
        if b1 is None:
            return None
        if kind_or_op == "HYPHEN":
            b2 = _parse_target_spec(t2_str or "")
            if b2 is None:
                return None
            item_dnf = _expand_hyphen(b1, b2)
        else:
            item_dnf = _expand_prefixed(kind_or_op, b1)
        clauses_dnf = [conj + branch for conj in clauses_dnf for branch in item_dnf]
    return clauses_dnf


def compile_range_dnf(text: str) -> Optional[List[List[_AtomCmp]]]:
    """Compiles a SemVer range expression to DNF atom clauses, or None if malformed."""
    trimmed = text.strip()
    if not trimmed or "," in trimmed:
        return None
    all_dnf: List[List[_AtomCmp]] = []
    for part in trimmed.split("||"):
        c_str = part.strip()
        if not c_str:
            return None
        c_dnf = _parse_clause_to_dnf(c_str)
        if c_dnf is None:
            return None
        all_dnf.extend(c_dnf)
    return all_dnf


def _atom_matches(v: Version, atom: _AtomCmp) -> bool:
    if atom.op == "NONE":
        return False
    cmp = compare_semver(v, atom.target)
    return (
        (atom.op == "==" and cmp == 0)
        or (atom.op == "!=" and cmp != 0)
        or (atom.op == "<" and cmp < 0)
        or (atom.op == "<=" and cmp <= 0)
        or (atom.op == ">" and cmp > 0)
        or (atom.op == ">=" and cmp >= 0)
    )


def satisfies_semver_range(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    """Evaluates SemVer range satisfaction with pre-release filtering rules."""
    dnf = compile_range_dnf(range_constraint.raw_text)
    if dnf is None:
        return False
    is_pre = len(version.prerelease) > 0
    for conj in dnf:
        if not all(_atom_matches(version, atom) for atom in conj):
            continue
        if is_pre and not include_prerelease:
            has_explicit_pre = any(
                len(atom.target.prerelease) > 0
                and (atom.target.major, atom.target.minor, atom.target.patch)
                == (version.major, version.minor, version.patch)
                for atom in conj
            )
            if not has_explicit_pre:
                continue
        return True
    return False


def _select_mrv_package(
    unassigned: Sequence[str],
    candidates_map: Dict[str, List[PackageRelease]],
) -> str:
    best_pkg = unassigned[0]
    for pkg in unassigned[1:]:
        if (len(candidates_map[pkg]), pkg) < (len(candidates_map[best_pkg]), best_pkg):
            best_pkg = pkg
    return best_pkg


def _solve_step(
    packages: Dict[str, List[PackageRelease]],
    accumulated: Dict[str, List[VersionRange]],
    assignment: Dict[str, PackageRelease],
    steps: List[str],
) -> bool:
    unassigned = [p for p in accumulated if p not in assignment]
    if not unassigned:
        return True

    candidates_map: Dict[str, List[PackageRelease]] = {}
    for pkg in unassigned:
        available = sort_releases_descending(packages.get(pkg, []))
        candidates_map[pkg] = [
            rel
            for rel in available
            if all(satisfies_semver_range(rel.version, rng, False) for rng in accumulated[pkg])
        ]

    selected_pkg = _select_mrv_package(unassigned, candidates_map)
    for candidate in candidates_map[selected_pkg]:
        assignment[selected_pkg] = candidate
        steps.append(
            f"Assign {selected_pkg} {candidate.version.major}.{candidate.version.minor}.{candidate.version.patch}"
        )
        conflict = False
        newly_added: List[Tuple[str, VersionRange]] = []
        for dep in candidate.dependencies:
            if dep.name in assignment:
                if not satisfies_semver_range(
                    assignment[dep.name].version, dep.range_constraint, False
                ):
                    conflict = True
                    break
            else:
                accumulated.setdefault(dep.name, []).append(dep.range_constraint)
                newly_added.append((dep.name, dep.range_constraint))

        if not conflict and _solve_step(packages, accumulated, assignment, steps):
            return True

        for dep_name, rng_entry in newly_added:
            accumulated[dep_name].remove(rng_entry)
            if not accumulated[dep_name]:
                del accumulated[dep_name]
        del assignment[selected_pkg]
        steps.pop()

    return False


def solve_dependencies_model(
    packages: Dict[str, List[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> Optional[ResolutionOutcome]:
    """Reference MRV + descending precedence backtracking solver."""
    accumulated: Dict[str, List[VersionRange]] = {}
    for dep in root_dependencies:
        accumulated.setdefault(dep.name, []).append(dep.range_constraint)
    assignment: Dict[str, PackageRelease] = {}
    steps: List[str] = []
    if _solve_step(packages, accumulated, assignment, steps):
        selected = {name: rel.version for name, rel in assignment.items()}
        return ResolutionOutcome(selected_versions=selected, derivation_steps=tuple(steps))
    return None


def compute_satisfiable_dependency_sets(
    packages: Dict[str, List[PackageRelease]],
) -> List[List[PackageDependency]]:
    """Computes satisfiable root dependency sets from current repository state."""
    options: List[List[PackageDependency]] = [[]]
    for pkg_name, releases in packages.items():
        for rel in releases:
            if len(rel.version.prerelease) == 0:
                cand = [PackageDependency(pkg_name, VersionRange("*"))]
                if cand not in options and solve_dependencies_model(packages, cand) is not None:
                    options.append(cand)
    return options


# ==============================================================================
# 1. Domain Candidate Pools & Model State
# ==============================================================================

VALID_VERSION_STRINGS: Tuple[str, ...] = (
    "0.0.0",
    "0.1.0",
    "0.2.3",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0",
    "1.0.0+20130313144700",
    "1.0.0-beta+exp.sha.5114f85",
    "1.2.0",
    "1.2.3",
    "2.0.0",
)

SAMPLE_VERSIONS: Tuple[Version, ...] = (
    Version(0, 0, 0),
    Version(0, 1, 0),
    Version(0, 0, 2),
    Version(1, 0, 0, prerelease=("alpha",)),
    Version(1, 0, 0, prerelease=("alpha", "1")),
    Version(1, 0, 0, prerelease=("beta", "2")),
    Version(1, 0, 0, prerelease=("beta", "11")),
    Version(1, 0, 0),
    Version(1, 0, 0, build=("build1",)),
    Version(1, 0, 0, build=("build2",)),
    Version(1, 2, 0),
    Version(1, 2, 3),
    Version(2, 0, 0),
)

VALID_RANGE_STRINGS: Tuple[str, ...] = (
    "*",
    "x.x",
    "X.X.X",
    ">=*",
    "!=*",
    ">*",
    "<=*",
    "<*",
    "~*",
    "^*",
    ">=1.0.0",
    ">1.0.0",
    "<=2.0.0",
    "<2.0.0",
    "!=1.0.0",
    ">= 1.0.0 < 2.0.0",
    "  ^1.0.0  ",
    "^0.1.0",
    "^0.0.1",
    "^1.x",
    "^1.2.x",
    "^0.1.x",
    "~1.2.0",
    "~1.2.x",
    "~1.x",
    "1.x",
    "1.x.x",
    "1.2.x",
    ">=1.x",
    ">=1.2.x",
    "!=1.x",
    "!=1.2.x",
    ">1.*",
    ">1.2.*",
    "<=1.x",
    "<=1.2.x",
    "<2.x",
    "<1.2.x",
    "=1.x",
    "=1.2.x",
    "=*",
    "^0.0.x",
    "~0.x",
    "1.0.0 - 2.0.0",
    "1.0.0-alpha - 2.0.0",
    "1.0.0 - 2.0.0-beta",
    "1.0.0-alpha - 1.0.0-beta",
    "1.0.0 - 2.x",
    "1.0.0 - *",
    "* - 2.0.0",
    "* - *",
    "1.x - 2.x",
    "1.2.x - 1.3.x",
    "==1.0.0 || ==2.0.0",
    "!=1.0.0-alpha",
    "=1.0.0-alpha",
    ">=1.0.0-alpha <1.0.0",
)

SAMPLE_RANGES: Tuple[VersionRange, ...] = tuple(
    VersionRange(s.strip()) for s in VALID_RANGE_STRINGS
)

SAMPLE_PACKAGE_NAMES: Tuple[str, ...] = ("app", "core", "util", "net")

SAMPLE_RELEASES: Tuple[PackageRelease, ...] = (
    PackageRelease("util", Version(1, 0, 0), ()),
    PackageRelease("util", Version(1, 2, 0), ()),
    PackageRelease("util", Version(2, 0, 0), ()),
    PackageRelease(
        "core",
        Version(1, 0, 0),
        (PackageDependency("util", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "core",
        Version(2, 0, 0),
        (PackageDependency("util", VersionRange("^2.0.0")),),
    ),
    PackageRelease(
        "app",
        Version(1, 0, 0),
        (
            PackageDependency("core", VersionRange(">=1.0.0")),
            PackageDependency("util", VersionRange("^1.0.0")),
        ),
    ),
    PackageRelease("net", Version(1, 0, 0), ()),
)


@dataclass
class SemverSolverState:
    """Canonical model state for VersionEngine, PackageRepository, and DependencySolver."""

    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemVer 2.0 parsing, repository, and dependency resolution."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> SemverSolverState:
        """Constructs blank initial model state."""
        return SemverSolverState()

    # --- Seeding Transition ---

    @transition.seeding
    def seed_repository(self) -> None:
        """Seeds standard compatible releases into the repository state for fuzzing."""
        for rel in SAMPLE_RELEASES:
            existing = self.state.packages.get(rel.name, [])
            self.state.packages[rel.name] = sort_releases_descending([*existing, rel])

    # --- VersionEngine Transitions ---

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require_arg(
            text,
            Domain.sampled_from(VALID_VERSION_STRINGS),
            error=InvalidVersionError,
            preferred=["1.0.0", "1.0.0-beta+exp.sha.5114f85", "0.1.0"],
            fuzz_domain=Domain.sampled_from(VALID_VERSION_STRINGS),
        )
        ret = self.inner_parse_version(text)
        expected = parse_semver_text(text)
        assert expected is not None
        assert ret.major == expected.major
        assert ret.minor == expected.minor
        assert ret.patch == expected.patch
        assert ret.prerelease == expected.prerelease
        assert ret.build == expected.build
        return ret

    def inner_parse_version(self, text: str) -> Version:
        parsed = parse_semver_text(text)
        return parsed if parsed is not None else Version(0, 0, 0)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(
            v1,
            Domain.type(Version),
            preferred=[Version(1, 0, 0), Version(1, 0, 0, prerelease=("alpha",))],
            fuzz_domain=Domain.sampled_from(SAMPLE_VERSIONS),
        )
        require_arg(
            v2,
            Domain.type(Version),
            preferred=[Version(1, 0, 0), Version(2, 0, 0)],
            fuzz_domain=Domain.sampled_from(SAMPLE_VERSIONS),
        )
        ret = self.inner_compare_precedence(v1, v2)
        expected = compare_semver(v1, v2)
        if expected < 0:
            assert ret < 0
        elif expected > 0:
            assert ret > 0
        else:
            assert ret == 0
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        return compare_semver(v1, v2)

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require_arg(
            text,
            Domain.sampled_from(VALID_RANGE_STRINGS),
            error=InvalidRangeError,
            preferred=["^1.0.0", ">= 1.0.0 < 2.0.0", "  ^1.0.0  "],
            fuzz_domain=Domain.sampled_from(VALID_RANGE_STRINGS),
        )
        ret = self.inner_parse_range(text)
        assert ret.raw_text == text.strip()
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
        require_arg(
            version,
            Domain.type(Version),
            preferred=[Version(1, 2, 0), Version(1, 0, 0, prerelease=("alpha",))],
            fuzz_domain=Domain.sampled_from(SAMPLE_VERSIONS),
        )
        require_arg(
            range_constraint,
            Domain.sampled_from(SAMPLE_RANGES),
            preferred=[VersionRange("^1.0.0"), VersionRange(">=1.0.0-alpha <1.0.0")],
            fuzz_domain=Domain.sampled_from(SAMPLE_RANGES),
        )
        require_arg(
            include_prerelease,
            Domain.sampled_from((False, True)),
            preferred=[False, True],
        )
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        expected = satisfies_semver_range(version, range_constraint, include_prerelease)
        assert ret == expected
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        return satisfies_semver_range(version, range_constraint, include_prerelease)

    # --- PackageRepository Transitions ---

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(
            release,
            Domain.type(PackageRelease),
            preferred=[SAMPLE_RELEASES[0], SAMPLE_RELEASES[3]],
            fuzz_domain=Domain.sampled_from(SAMPLE_RELEASES),
        )
        ret = self.inner_register_package(release)
        existing = self.state.packages.get(release.name, [])
        self.state.packages[release.name] = sort_releases_descending([*existing, release])
        assert release in self.state.packages[release.name]
        return ret

    def inner_register_package(self, release: PackageRelease) -> None:
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(bool(self.state.packages), PackageNotFoundError)
        require_arg(
            name,
            Domain.in_set(self.state.packages),
            error=PackageNotFoundError,
        )
        ret = self.inner_get_releases(name)
        expected = self.state.packages[name]
        assert len(ret) == len(expected)
        for idx, item in enumerate(ret):
            assert item.name == name
            assert compare_semver(item.version, expected[idx].version) == 0
            assert item.dependencies == expected[idx].dependencies
        return ret

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        return list(self.state.packages.get(name, []))

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(
            name,
            Domain.type(str),
            preferred=["util", "missing_pkg"],
            fuzz_domain=Domain.sampled_from((*SAMPLE_PACKAGE_NAMES, "missing_pkg")),
        )
        ret = self.inner_has_package(name)
        assert ret == (name in self.state.packages)
        return ret

    def inner_has_package(self, name: str) -> bool:
        return name in self.state.packages

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        ret = self.inner_all_packages()
        assert ret == set(self.state.packages.keys())
        return ret

    def inner_all_packages(self) -> Set[str]:
        return set(self.state.packages.keys())

    # --- DependencySolver Transitions ---

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require_arg(
            root_dependencies,
            Domain.sampled_from(compute_satisfiable_dependency_sets(self.state.packages)),
            error=ResolutionConflictError,
            fuzz_domain=Domain.sampled_from(
                compute_satisfiable_dependency_sets(self.state.packages)
            ),
        )
        ret = self.inner_resolve(root_dependencies)
        expected = solve_dependencies_model(self.state.packages, root_dependencies)
        assert expected is not None
        for dep in root_dependencies:
            assert dep.name in ret.selected_versions
            selected_ver = ret.selected_versions[dep.name]
            assert satisfies_semver_range(selected_ver, dep.range_constraint, False)
        assert set(ret.selected_versions.keys()) == set(expected.selected_versions.keys())
        for pkg_name, exp_ver in expected.selected_versions.items():
            assert pkg_name in self.state.packages
            assert compare_semver(ret.selected_versions[pkg_name], exp_ver) == 0
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        outcome = solve_dependencies_model(self.state.packages, root_dependencies)
        return outcome if outcome is not None else ResolutionOutcome({}, ())


proto = SemverSolverStateMachine()

# ==============================================================================
# 2. Synthesized Fake & Hypothesis Fuzzing
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances sharing canonical SemverSolverState."""
    shared_fake = FakeSemverSolver(
        state=state if state is not None else proto.make_initial_state()
    )
    return (shared_fake, shared_fake, shared_fake)


FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemverSolverFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Edge Branches Not Reached by Random Sampling)
# ==============================================================================


class TestSemverSolverFake(unittest.TestCase):
    """Covers helper rejection branches and multi-service fake factory."""

    def test_fakes_and_edge_branches(self) -> None:
        eng, repo, solver = make_semver_solver_fakes()
        v = eng.parse_version("1.0.0-beta+exp.sha.5114f85")
        self.assertEqual(v.major, 1)

        # Exercise parser and comparator edge branches for 100% helper coverage
        self.assertEqual(
            compare_semver(
                Version(1, 0, 0, prerelease=("1",)),
                Version(1, 0, 0, prerelease=("alpha",)),
            ),
            -1,
        )
        self.assertEqual(
            compare_semver(
                Version(1, 0, 0, prerelease=("alpha",)),
                Version(1, 0, 0, prerelease=("1",)),
            ),
            1,
        )
        self.assertEqual(
            compare_semver(
                Version(1, 0, 0, prerelease=("10",)),
                Version(1, 0, 0, prerelease=("2",)),
            ),
            1,
        )
        for bad_v in ("", " 1.0.0", "1.0", "01.0.0", "1.0.0-", "1.0.0-01", "1.0.0+", "1.0.0+!"):
            self.assertIsNone(parse_semver_text(bad_v))

        for bad_r in (
            "",
            " , ",
            "1.0.0 || ",
            "-",
            ">",
            ">=",
            "> =",
            "> -",
            "1.0",
            "1.0.0 - 2.0",
            "1.0 - 2.0.0",
            "1.x-alpha",
            "1.0.0.0",
        ):
            self.assertIsNone(compile_range_dnf(bad_r))
            self.assertFalse(satisfies_semver_range(v, VersionRange(bad_r), False))

        # Exercise all range operators on Fake
        for rng_str in VALID_RANGE_STRINGS:
            vr = eng.parse_range(rng_str)
            eng.satisfies(Version(1, 0, 0), vr, False)
            eng.satisfies(Version(0, 0, 1), vr, False)
            eng.satisfies(Version(1, 0, 0, prerelease=("alpha",)), vr, False)
            eng.satisfies(Version(1, 0, 0, prerelease=("alpha",)), vr, True)

        # Exercise solver backtracking, forward conflict, and None outcome in model helper
        for rel in SAMPLE_RELEASES:
            repo.register_package(rel)
        self.assertTrue(repo.has_package("app"))
        self.assertIn("app", repo.all_packages())
        self.assertEqual(len(repo.get_releases("util")), 3)
        outcome = solver.resolve([PackageDependency("app", VersionRange("*"))])
        self.assertEqual(outcome.selected_versions["util"], Version(1, 2, 0))

        # Backtracking when an already assigned package conflicts with a candidate's dependency
        backtrack_pkgs = {
            "p": [PackageRelease("p", Version(1, 0, 0), ())],
            "q": [
                PackageRelease("q", Version(2, 0, 0), (PackageDependency("p", VersionRange(">=2.0.0")),)),
                PackageRelease("q", Version(1, 0, 0), (PackageDependency("p", VersionRange(">=1.0.0")),)),
            ],
        }
        bt_res = solve_dependencies_model(
            backtrack_pkgs,
            [
                PackageDependency("p", VersionRange("*")),
                PackageDependency("q", VersionRange("*")),
            ],
        )
        self.assertIsNotNone(bt_res)

        # Backtracking undo of newly added transitive constraints when sub-branch fails
        undo_pkgs = {
            "root_pkg": [
                PackageRelease("root_pkg", Version(2, 0, 0), (PackageDependency("dead", VersionRange("*")),)),
                PackageRelease("root_pkg", Version(1, 0, 0), ()),
            ],
        }
        undo_res = solve_dependencies_model(
            undo_pkgs,
            [PackageDependency("root_pkg", VersionRange("*"))],
        )
        self.assertIsNotNone(undo_res)

        self.assertIsNone(
            solve_dependencies_model(
                {"a": [PackageRelease("a", Version(1, 0, 0), ())]},
                [PackageDependency("missing", VersionRange("*"))],
            )
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T23:05:21Z
# LAST_CHANGED: 2026-11-13T23:05:21Z
# CHANGE: Expand VALID_RANGE_STRINGS domain with wildcard relational comparators (>=1.x, >=1.2.x, !=1.x, >1.2.*, =1.x, ^0.0.x, ~0.x) and hyphen prerelease bounds (1.0.0-alpha - 2.0.0, 1.0.0 - 2.0.0-beta, 1.0.0 - 2.x)
# --- END AUTOFAB METADATA ---
