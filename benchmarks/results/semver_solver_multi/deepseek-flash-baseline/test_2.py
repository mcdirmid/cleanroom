# === File: dependency_solver_impl_test.py ===
"""Unit tests for the concrete package repository and backtracking dependency solver."""

from __future__ import annotations

import unittest
from typing import List, Sequence, Tuple
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
)
from semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)
from semver_solver_multi.lib.semver_core import Version, VersionEngine
from semver_solver_multi.lib.semver_range import RangeEngine, VersionRange


def make_release(
    name: str,
    version: Version,
    dependencies: Sequence[PackageDependency] = (),
) -> PackageRelease:
    """Wraps primitive release fields into a domain PackageRelease record."""
    return PackageRelease(name, version, tuple(dependencies))


def make_dependency(name: str, range_text: str) -> PackageDependency:
    """Wraps a primitive package name and range text into a domain PackageDependency."""
    return PackageDependency(name, VersionRange(range_text))


class MockVersionEngine:
    """Lightweight collaborator double for the semver_core.VersionEngine protocol."""

    tier = system

    def __init__(self) -> None:
        self.comparisons: List[Tuple[Version, Version]] = []

    def parse_version(self, text: str) -> Version:
        core, _, build = text.partition("+")
        core, _, prerelease = core.partition("-")
        major, minor, patch = core.split(".")
        return Version(
            int(major),
            int(minor),
            int(patch),
            tuple(prerelease.split(".")) if prerelease else (),
            tuple(build.split(".")) if build else (),
        )

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        self.comparisons.append((v1, v2))
        numeric1 = (v1.major, v1.minor, v1.patch)
        numeric2 = (v2.major, v2.minor, v2.patch)
        if numeric1 != numeric2:
            return -1 if numeric1 < numeric2 else 1
        if v1.prerelease == v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        return -1 if v1.prerelease < v2.prerelease else 1


class MockRangeEngine:
    """Lightweight collaborator double for the semver_range.RangeEngine protocol."""

    tier = system

    def __init__(self) -> None:
        self.checks: List[Tuple[Version, str, bool]] = []

    def parse_range(self, text: str) -> VersionRange:
        return VersionRange(text.strip())

    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        self.checks.append((version, range_constraint.raw_text, include_prerelease))
        operator = "=="
        bound_text = range_constraint.raw_text.strip()
        for candidate in (">=", "<=", "!=", "==", ">", "<", "="):
            if bound_text.startswith(candidate):
                operator = candidate
                bound_text = bound_text[len(candidate):].strip()
                break
        bound = tuple(int(part) for part in bound_text.split("."))
        actual = (version.major, version.minor, version.patch)
        if operator == ">=":
            return actual >= bound
        if operator == ">":
            return actual > bound
        if operator == "<=":
            return actual <= bound
        if operator == "<":
            return actual < bound
        if operator == "!=":
            return actual != bound
        return actual == bound


class DependencySolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.range_engine = MockRangeEngine()
        self.registry.register_instance(
            self.version_engine, keys=[VersionEngine], tier=system
        )
        self.registry.register_instance(
            self.range_engine, keys=[RangeEngine], tier=system
        )
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.repository = self.phase_scope.get_singleton(PackageRepository)
        self.solver = self.phase_scope.get_singleton(DependencySolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_register_package_orders_releases_by_descending_precedence(self) -> None:
        """POSTCONDITIONS: registered releases are indexed and ordered by descending precedence."""
        self.repository.register_package(make_release("alpha", Version(1, 0, 0)))
        self.repository.register_package(make_release("alpha", Version(2, 0, 0)))
        self.repository.register_package(make_release("alpha", Version(1, 5, 0)))
        releases = self.repository.get_releases("alpha")
        self.assertEqual(
            [release.version for release in releases],
            [Version(2, 0, 0), Version(1, 5, 0), Version(1, 0, 0)],
        )
        self.assertTrue(self.version_engine.comparisons)
        self.assertTrue(self.repository.has_package("alpha"))
        self.assertFalse(self.repository.has_package("beta"))
        self.assertEqual(self.repository.all_packages(), {"alpha"})

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITIONS: get_releases yields a copy so callers cannot mutate stored history."""
        self.repository.register_package(make_release("alpha", Version(1, 0, 0)))
        releases = self.repository.get_releases("alpha")
        releases.pop()
        self.assertEqual(len(self.repository.get_releases("alpha")), 1)

    def test_get_releases_rejects_unregistered_package(self) -> None:
        """PRECONDITIONS: WHEN name is not registered, MUST raise PackageNotFoundError."""
        with self.assertRaises(PackageNotFoundError) as context:
            self.repository.get_releases("ghost")
        self.assertEqual(context.exception.package_name, "ghost")

    def test_resolve_selects_highest_compatible_transitive_releases(self) -> None:
        """POSTCONDITIONS: select highest precedence compatible releases and report derivation steps."""
        self.repository.register_package(
            make_release("alpha", Version(2, 0, 0), [make_dependency("beta", ">=1.0.0")])
        )
        self.repository.register_package(make_release("alpha", Version(1, 0, 0)))
        self.repository.register_package(make_release("beta", Version(1, 5, 0)))
        self.repository.register_package(make_release("beta", Version(1, 0, 0)))
        outcome = self.solver.resolve([make_dependency("alpha", ">=1.0.0")])
        self.assertEqual(
            outcome.selected_versions,
            {"alpha": Version(2, 0, 0), "beta": Version(1, 5, 0)},
        )
        self.assertEqual(len(outcome.derivation_steps), 2)
        self.assertTrue(self.range_engine.checks)

    def test_resolve_backtracks_to_lower_release_satisfying_transitive_constraint(self) -> None:
        """POSTCONDITIONS: unsatisfiable candidate branches backtrack to lower viable releases."""
        self.repository.register_package(
            make_release("alpha", Version(2, 0, 0), [make_dependency("beta", ">=2.0.0")])
        )
        self.repository.register_package(
            make_release("alpha", Version(1, 0, 0), [make_dependency("beta", ">=1.0.0")])
        )
        self.repository.register_package(make_release("beta", Version(1, 0, 0)))
        outcome = self.solver.resolve([make_dependency("alpha", ">=1.0.0")])
        self.assertEqual(
            outcome.selected_versions,
            {"alpha": Version(1, 0, 0), "beta": Version(1, 0, 0)},
        )
        self.assertEqual(len(outcome.derivation_steps), 2)

    def test_resolve_reports_conflict_for_unregistered_package(self) -> None:
        """PRECONDITIONS: WHEN a dependency references an absent package, MUST raise ResolutionConflictError."""
        with self.assertRaises(ResolutionConflictError) as context:
            self.solver.resolve([make_dependency("ghost", ">=1.0.0")])
        self.assertIn("ghost", context.exception.conflicting_packages)
        self.assertTrue(context.exception.explanation)

    def test_resolve_reports_conflict_for_unsatisfiable_root_constraints(self) -> None:
        """PRECONDITIONS: WHEN root constraints are unsatisfiable, MUST raise ResolutionConflictError."""
        self.repository.register_package(make_release("alpha", Version(1, 0, 0)))
        with self.assertRaises(ResolutionConflictError) as context:
            self.solver.resolve(
                [
                    make_dependency("alpha", ">=1.0.0"),
                    make_dependency("alpha", ">=2.0.0"),
                ]
            )
        self.assertIn("alpha", context.exception.conflicting_packages)
        self.assertTrue(context.exception.explanation)

    def test_resolve_reports_conflict_on_already_assigned_release(self) -> None:
        """PRECONDITIONS: WHEN a candidate violates an assigned package, MUST raise ResolutionConflictError."""
        self.repository.register_package(make_release("alpha", Version(1, 0, 0)))
        self.repository.register_package(
            make_release("beta", Version(1, 0, 0), [make_dependency("alpha", ">=2.0.0")])
        )
        with self.assertRaises(ResolutionConflictError) as context:
            self.solver.resolve(
                [
                    make_dependency("alpha", ">=1.0.0"),
                    make_dependency("beta", ">=1.0.0"),
                ]
            )
        self.assertEqual(len(context.exception.conflicting_packages), 2)
        self.assertIn("alpha", context.exception.conflicting_packages)
        self.assertIn("beta", context.exception.conflicting_packages)
        self.assertTrue(context.exception.explanation)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:12:05Z
# LAST_CHANGED: 2026-11-07T03:12:05Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: d8dae925e2e1
# COVERAGE_AUDIT: 2026-11-07T03:12:05Z
# QA_AUDIT: 2026-11-07T03:12:05Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for the concrete SemVer 2.0.0 version engine."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from semver_solver_multi.lib.semver_core_impl import VersionEngine, __initialize__


class SemverCoreImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = self.phase_scope.get_singleton(VersionEngine)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_captures_prerelease_and_build(self) -> None:
        """POSTCONDITIONS: parse valid SemVer text into components and ordered identifier tuples."""
        parsed = self.engine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual(parsed, Version(1, 2, 3, ("alpha", "1"), ("build", "5")))
        self.assertTrue(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "1.2.3-alpha.1+build.5")
        self.assertEqual(str(parsed), parsed.format())

    def test_parse_version_core_only(self) -> None:
        """POSTCONDITIONS: parse bare numeric cores with empty prerelease and build tuples."""
        parsed = self.engine.parse_version("0.1.0")
        self.assertEqual(parsed, Version(0, 1, 0))
        self.assertFalse(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "0.1.0")
        self.assertEqual(str(parsed), "0.1.0")

    def test_parse_version_prerelease_only(self) -> None:
        """POSTCONDITIONS: capture dot-separated prerelease identifiers without build metadata."""
        parsed = self.engine.parse_version("1.0.0-rc.1")
        self.assertEqual(parsed.prerelease, ("rc", "1"))
        self.assertEqual(parsed.build, ())
        self.assertTrue(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "1.0.0-rc.1")

    def test_parse_version_build_metadata_only(self) -> None:
        """POSTCONDITIONS: capture plus-separated build identifiers while remaining non-prerelease."""
        parsed = self.engine.parse_version("2.0.0+exp.sha.5114f85")
        self.assertEqual(parsed.prerelease, ())
        self.assertEqual(parsed.build, ("exp", "sha", "5114f85"))
        self.assertFalse(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "2.0.0+exp.sha.5114f85")

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """PRECONDITIONS: WHEN numeric identifiers contain leading zeroes, MUST raise InvalidVersionError."""
        for text in ("01.2.3", "1.02.3", "1.2.03", "1.2.3-01"):
            with self.assertRaises(InvalidVersionError) as context:
                self.engine.parse_version(text)
            self.assertEqual(context.exception.raw_text, text)

    def test_parse_version_rejects_malformed_grammar(self) -> None:
        """PRECONDITIONS: WHEN text violates the SemVer grammar, MUST raise InvalidVersionError."""
        for text in ("1.2", "1.2.3.4", "v1.2.3", "1.2.3-", "1.2.3+bad_"):
            with self.assertRaises(InvalidVersionError) as context:
                self.engine.parse_version(text)
            self.assertEqual(context.exception.raw_text, text)

    def test_compare_precedence_orders_numeric_core(self) -> None:
        """POSTCONDITIONS: major, minor, and patch compare numerically in sequence."""
        self.assertLess(self.engine.compare_precedence(Version(1, 2, 3), Version(2, 0, 0)), 0)
        self.assertGreater(self.engine.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)), 0)
        self.assertLess(self.engine.compare_precedence(Version(1, 2, 3), Version(1, 3, 0)), 0)
        self.assertGreater(self.engine.compare_precedence(Version(1, 3, 0), Version(1, 2, 9)), 0)
        self.assertLess(self.engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 4)), 0)
        self.assertGreater(self.engine.compare_precedence(Version(1, 2, 4), Version(1, 2, 3)), 0)
        self.assertEqual(self.engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)

    def test_compare_precedence_ranks_normal_above_prerelease(self) -> None:
        """POSTCONDITIONS: a normal version outranks a prerelease sharing the same numeric core."""
        prerelease = Version(1, 0, 0, ("alpha",))
        self.assertGreater(self.engine.compare_precedence(Version(1, 0, 0), prerelease), 0)
        self.assertLess(self.engine.compare_precedence(prerelease, Version(1, 0, 0)), 0)

    def test_compare_precedence_orders_numeric_prerelease_identifiers(self) -> None:
        """POSTCONDITIONS: numeric prerelease identifiers compare numerically."""
        first = Version(1, 0, 0, ("alpha", "1"))
        second = Version(1, 0, 0, ("alpha", "2"))
        self.assertLess(self.engine.compare_precedence(first, second), 0)
        self.assertGreater(self.engine.compare_precedence(second, first), 0)
        self.assertEqual(self.engine.compare_precedence(first, Version(1, 0, 0, ("alpha", "1"))), 0)

    def test_compare_precedence_ranks_numeric_below_alphanumeric(self) -> None:
        """POSTCONDITIONS: numeric prerelease identifiers rank below alphanumeric identifiers."""
        numeric = Version(1, 0, 0, ("alpha", "1"))
        alphanumeric = Version(1, 0, 0, ("alpha", "beta"))
        self.assertLess(self.engine.compare_precedence(numeric, alphanumeric), 0)
        self.assertGreater(self.engine.compare_precedence(alphanumeric, numeric), 0)

    def test_compare_precedence_orders_alphanumeric_identifiers_lexicographically(self) -> None:
        """POSTCONDITIONS: string prerelease identifiers compare in ASCII lexicographical order."""
        alpha = Version(1, 0, 0, ("alpha",))
        beta = Version(1, 0, 0, ("beta",))
        self.assertLess(self.engine.compare_precedence(alpha, beta), 0)
        self.assertGreater(self.engine.compare_precedence(beta, alpha), 0)

    def test_compare_precedence_ranks_longer_prerelease_sequence_higher(self) -> None:
        """POSTCONDITIONS: a longer prerelease sequence outranks a matching shared prefix."""
        short = Version(1, 0, 0, ("alpha",))
        longer = Version(1, 0, 0, ("alpha", "1"))
        self.assertLess(self.engine.compare_precedence(short, longer), 0)
        self.assertGreater(self.engine.compare_precedence(longer, short), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: build metadata never contributes to precedence comparison."""
        self.assertEqual(
            self.engine.compare_precedence(
                Version(1, 0, 0, (), ("build", "1")),
                Version(1, 0, 0, (), ("build", "2")),
            ),
            0,
        )
        self.assertEqual(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha",), ("a",)),
                Version(1, 0, 0, ("alpha",), ("b",)),
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:12:05Z
# LAST_CHANGED: 2026-11-07T03:12:05Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 568569f3b4ab
# COVERAGE_AUDIT: 2026-11-07T03:12:05Z
# QA_AUDIT: 2026-11-07T03:12:05Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for the concrete version range parsing and matching engine."""

from __future__ import annotations

import re
import unittest
from typing import List, Tuple
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import InvalidVersionError, Version, VersionEngine
from semver_solver_multi.lib.semver_range import InvalidRangeError
from semver_solver_multi.lib.semver_range_impl import RangeEngine, __initialize__

_SEMVER_GRAMMAR = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def make_version(
    major: int,
    minor: int = 0,
    patch: int = 0,
    prerelease: Tuple[str, ...] = (),
) -> Version:
    """Wraps primitive version fields into a domain Version record."""
    return Version(major, minor, patch, prerelease)


class MockVersionEngine:
    """Lightweight collaborator double for the semver_core.VersionEngine protocol."""

    tier = system

    def __init__(self) -> None:
        self.comparisons: List[Tuple[Version, Version]] = []

    def parse_version(self, text: str) -> Version:
        match = _SEMVER_GRAMMAR.fullmatch(text)
        if match is None:
            raise InvalidVersionError(f"Invalid semantic version: {text!r}", text)
        major, minor, patch, prerelease, build = match.groups()
        return Version(
            int(major),
            int(minor),
            int(patch),
            tuple(prerelease.split(".")) if prerelease else (),
            tuple(build.split(".")) if build else (),
        )

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        self.comparisons.append((v1, v2))
        numeric1 = (v1.major, v1.minor, v1.patch)
        numeric2 = (v2.major, v2.minor, v2.patch)
        if numeric1 != numeric2:
            return -1 if numeric1 < numeric2 else 1
        if v1.prerelease == v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        return -1 if v1.prerelease < v2.prerelease else 1


class SemverRangeImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine, keys=[VersionEngine], tier=system
        )
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = self.phase_scope.get_singleton(RangeEngine)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _assert_satisfies(
        self,
        range_text: str,
        candidate: Version,
        expected: bool,
        include_prerelease: bool = False,
    ) -> None:
        constraint = self.engine.parse_range(range_text)
        actual = self.engine.satisfies(candidate, constraint, include_prerelease)
        self.assertEqual(actual, expected, f"{candidate.format()} against {range_text}")

    def test_parse_range_trims_and_preserves_expression(self) -> None:
        """POSTCONDITIONS: store the trimmed range expression as canonical raw_text."""
        self.assertEqual(
            self.engine.parse_range(" >=1.0.0 || <2.0.0 ").raw_text,
            ">=1.0.0 || <2.0.0",
        )
        self.assertEqual(str(self.engine.parse_range("1.x")), "1.x")

    def test_parse_range_rejects_empty_and_comma_syntax(self) -> None:
        """PRECONDITIONS: WHEN text is empty or uses commas, MUST raise InvalidRangeError."""
        for text in ("", "   ", ">=1.0.0, <2.0.0"):
            with self.assertRaises(InvalidRangeError) as context:
                self.engine.parse_range(text)
            self.assertEqual(context.exception.raw_range, text)

    def test_parse_range_rejects_empty_union_clauses(self) -> None:
        """PRECONDITIONS: WHEN text contains empty union clauses, MUST raise InvalidRangeError."""
        for text in (">=1.0.0 ||", "|| >=1.0.0"):
            with self.assertRaises(InvalidRangeError):
                self.engine.parse_range(text)

    def test_parse_range_rejects_bare_partial_versions(self) -> None:
        """PRECONDITIONS: WHEN bounds lack wildcards, MUST raise InvalidRangeError."""
        for text in ("1", "1.2", ">1.2", "^0.0", "1.2 - 2.3", "1.0.0.0"):
            with self.assertRaises(InvalidRangeError):
                self.engine.parse_range(text)

    def test_parse_range_rejects_malformed_clauses(self) -> None:
        """PRECONDITIONS: WHEN range syntax is malformed, MUST raise InvalidRangeError."""
        for text in (">=", "1.0.0 -", "1.0.0 - 2.0.0 - 3.0.0"):
            with self.assertRaises(InvalidRangeError):
                self.engine.parse_range(text)

    def test_parse_range_accepts_whitespace_around_operators(self) -> None:
        """POSTCONDITIONS: optional whitespace separates relational operators from bounds."""
        constraint = self.engine.parse_range(">= 1.0.0 < 2.0.0")
        self.assertEqual(constraint.raw_text, ">= 1.0.0 < 2.0.0")
        self.assertTrue(self.engine.satisfies(make_version(1, 5, 0), constraint, False))
        self.assertFalse(self.engine.satisfies(make_version(2, 0, 0), constraint, False))

    def test_satisfies_basic_comparators(self) -> None:
        """POSTCONDITIONS: relational comparators evaluate by version precedence."""
        self._assert_satisfies(">=1.0.0", make_version(1, 0, 0), True)
        self._assert_satisfies(">=1.0.0", make_version(0, 9, 9), False)
        self._assert_satisfies(">1.0.0", make_version(1, 0, 1), True)
        self._assert_satisfies(">1.0.0", make_version(1, 0, 0), False)
        self._assert_satisfies("<=2.0.0", make_version(2, 0, 0), True)
        self._assert_satisfies("<=2.0.0", make_version(2, 0, 1), False)
        self._assert_satisfies("<2.0.0", make_version(1, 9, 9), True)
        self._assert_satisfies("<2.0.0", make_version(2, 0, 0), False)
        self._assert_satisfies("==1.0.0", make_version(1, 0, 0), True)
        self._assert_satisfies("==1.0.0", make_version(1, 0, 1), False)
        self._assert_satisfies("=1.0.0", make_version(1, 0, 0), True)
        self._assert_satisfies("1.0.0", make_version(1, 0, 0), True)
        self._assert_satisfies("!=1.0.0", make_version(1, 0, 1), True)
        self._assert_satisfies("!=1.0.0", make_version(1, 0, 0), False)
        self.assertTrue(self.version_engine.comparisons)

    def test_satisfies_wildcard_ranges(self) -> None:
        """POSTCONDITIONS: wildcard bounds expand into paired comparator inequalities."""
        self._assert_satisfies("1.x", make_version(1, 2, 3), True)
        self._assert_satisfies("1.x", make_version(2, 0, 0), False)
        self._assert_satisfies("1.2.x", make_version(1, 2, 9), True)
        self._assert_satisfies("1.2.x", make_version(1, 3, 0), False)
        self._assert_satisfies("=1.x", make_version(1, 5, 0), True)
        self._assert_satisfies("=1.x", make_version(2, 0, 0), False)
        self._assert_satisfies("==1.2.x", make_version(1, 2, 0), True)
        self._assert_satisfies(">=1.x", make_version(1, 0, 0), True)
        self._assert_satisfies(">=1.x", make_version(0, 9, 9), False)
        self._assert_satisfies(">1.*", make_version(2, 0, 0), True)
        self._assert_satisfies(">1.*", make_version(1, 9, 9), False)
        self._assert_satisfies("<1.x", make_version(0, 9, 9), True)
        self._assert_satisfies("<1.x", make_version(1, 0, 0), False)
        self._assert_satisfies("<=1.x", make_version(1, 9, 9), True)
        self._assert_satisfies("<=1.x", make_version(2, 0, 0), False)
        self._assert_satisfies("!=1.x", make_version(2, 0, 0), True)
        self._assert_satisfies("!=1.x", make_version(0, 9, 9), True)
        self._assert_satisfies("!=1.x", make_version(1, 5, 0), False)
        self._assert_satisfies("!=1.2.x", make_version(1, 3, 0), True)
        self._assert_satisfies("!=1.2.x", make_version(1, 2, 9), False)
        self._assert_satisfies("*", make_version(1, 2, 3), True)
        self._assert_satisfies(">=*", make_version(1, 2, 3), True)
        self._assert_satisfies("<=*", make_version(1, 2, 3), True)
        self._assert_satisfies("!=*", make_version(1, 2, 3), False)
        self._assert_satisfies("<*", make_version(1, 2, 3), False)
        self._assert_satisfies(">*", make_version(1, 2, 3), False)

    def test_satisfies_caret_ranges(self) -> None:
        """POSTCONDITIONS: caret ranges bound compatibility by the first non-zero component."""
        self._assert_satisfies("^1.2.3", make_version(1, 2, 3), True)
        self._assert_satisfies("^1.2.3", make_version(1, 9, 9), True)
        self._assert_satisfies("^1.2.3", make_version(2, 0, 0), False)
        self._assert_satisfies("^1.2.3", make_version(1, 2, 2), False)
        self._assert_satisfies("^0.2.3", make_version(0, 2, 9), True)
        self._assert_satisfies("^0.2.3", make_version(0, 3, 0), False)
        self._assert_satisfies("^0.0.3", make_version(0, 0, 3), True)
        self._assert_satisfies("^0.0.3", make_version(0, 0, 4), False)
        self._assert_satisfies("^1.x", make_version(1, 9, 9), True)
        self._assert_satisfies("^1.x", make_version(2, 0, 0), False)
        self._assert_satisfies("^0.x", make_version(0, 9, 9), True)
        self._assert_satisfies("^0.x", make_version(1, 0, 0), False)
        self._assert_satisfies("^1.2.x", make_version(1, 3, 0), True)
        self._assert_satisfies("^1.2.x", make_version(2, 0, 0), False)
        self._assert_satisfies("^0.2.x", make_version(0, 2, 9), True)
        self._assert_satisfies("^0.2.x", make_version(0, 3, 0), False)
        self._assert_satisfies("^0.0.x", make_version(0, 0, 9), True)
        self._assert_satisfies("^0.0.x", make_version(0, 1, 0), False)

    def test_satisfies_tilde_ranges(self) -> None:
        """POSTCONDITIONS: tilde ranges bound compatibility by the next minor boundary."""
        self._assert_satisfies("~1.2.3", make_version(1, 2, 3), True)
        self._assert_satisfies("~1.2.3", make_version(1, 2, 9), True)
        self._assert_satisfies("~1.2.3", make_version(1, 3, 0), False)
        self._assert_satisfies("~1.2.3", make_version(1, 2, 2), False)
        self._assert_satisfies("~1.x", make_version(1, 9, 9), True)
        self._assert_satisfies("~1.x", make_version(2, 0, 0), False)
        self._assert_satisfies("~1.2.x", make_version(1, 2, 9), True)
        self._assert_satisfies("~1.2.x", make_version(1, 3, 0), False)

    def test_satisfies_hyphen_ranges(self) -> None:
        """POSTCONDITIONS: hyphen ranges normalize into inclusive and exclusive bounds."""
        self._assert_satisfies("1.0.0 - 2.x", make_version(1, 0, 0), True)
        self._assert_satisfies("1.0.0 - 2.x", make_version(2, 9, 9), True)
        self._assert_satisfies("1.0.0 - 2.x", make_version(3, 0, 0), False)
        self._assert_satisfies("1.0.0 - 2.x", make_version(0, 9, 9), False)
        self._assert_satisfies("1.x - 2.x", make_version(1, 0, 0), True)
        self._assert_satisfies("1.x - 2.0.0", make_version(2, 0, 0), True)
        self._assert_satisfies("1.x - 2.0.0", make_version(2, 0, 1), False)
        self._assert_satisfies("* - 2.x", make_version(0, 0, 1), True)
        self._assert_satisfies("* - 2.x", make_version(3, 0, 0), False)
        self._assert_satisfies("1.0.0 - *", make_version(9, 9, 9), True)
        self._assert_satisfies("1.0.0 - *", make_version(0, 9, 9), False)

    def test_satisfies_union_ranges(self) -> None:
        """POSTCONDITIONS: union alternatives satisfy when any clause matches."""
        self._assert_satisfies("<1.0.0 || >=2.0.0", make_version(0, 9, 9), True)
        self._assert_satisfies("<1.0.0 || >=2.0.0", make_version(2, 0, 0), True)
        self._assert_satisfies("<1.0.0 || >=2.0.0", make_version(1, 5, 0), False)

    def test_satisfies_prerelease_gating(self) -> None:
        """POSTCONDITIONS: prerelease candidates require explicit targeting when disallowed."""
        self._assert_satisfies(">=1.0.0", make_version(1, 1, 0, ("alpha",)), False)
        self._assert_satisfies(
            ">=1.0.0", make_version(1, 1, 0, ("alpha",)), True, include_prerelease=True
        )
        self._assert_satisfies(">=1.0.0-alpha", make_version(1, 0, 0, ("alpha", "2")), True)
        self._assert_satisfies(">=1.0.0-alpha", make_version(2, 1, 0, ("alpha",)), False)
        self._assert_satisfies(">=1.0.0", make_version(1, 5, 0), True)
        self._assert_satisfies(
            ">=1.0.0", make_version(0, 9, 9, ("alpha",)), False, include_prerelease=True
        )
        self._assert_satisfies("1.0.0-alpha - 2.0.0", make_version(1, 0, 0, ("beta",)), True)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:12:05Z
# LAST_CHANGED: 2026-11-07T03:12:05Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9d8d558d53d2
# COVERAGE_AUDIT: 2026-11-07T03:12:05Z
# QA_AUDIT: 2026-11-07T03:12:05Z
# --- END AUTOFAB METADATA ---
