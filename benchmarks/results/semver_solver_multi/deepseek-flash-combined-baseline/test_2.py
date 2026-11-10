# === File: dependency_solver_impl_test.py ===
"""Unit tests for dependency_solver_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Callable, Dict, List, Tuple

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


class _VersionEngineStub:
    """Lightweight collaborator stub comparing numeric version cores."""

    def parse_version(self, text: str) -> Version:
        parts = text.split(".")
        return Version(int(parts[0]), int(parts[1]), int(parts[2]))

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        left = (v1.major, v1.minor, v1.patch)
        right = (v2.major, v2.minor, v2.patch)
        if left == right:
            return 0
        return -1 if left < right else 1


class _RangeEngineStub:
    """Lightweight collaborator stub scripting satisfaction predicates per range text."""

    def __init__(self) -> None:
        self.constraints: Dict[str, Callable[[Version], bool]] = {}
        self.observed_prerelease_flags: List[bool] = []

    def parse_range(self, text: str) -> VersionRange:
        return VersionRange(text)

    def satisfies(
        self, version: Version, range_constraint: VersionRange, include_prerelease: bool
    ) -> bool:
        self.observed_prerelease_flags.append(include_prerelease)
        predicate = self.constraints.get(range_constraint.raw_text)
        if predicate is None:
            return True
        return predicate(version)


def _version(major: int, minor: int = 0, patch: int = 0) -> Version:
    return Version(major, minor, patch)


def _dependency(name: str, range_text: str) -> PackageDependency:
    return PackageDependency(name, VersionRange(range_text))


def _release(
    name: str, version: Version, dependencies: Tuple[PackageDependency, ...] = ()
) -> PackageRelease:
    return PackageRelease(name, version, dependencies)


def _at_least(major: int) -> Callable[[Version], bool]:
    return lambda version: version.major >= major


class DependencySolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = _VersionEngineStub()
        self.range_engine = _RangeEngineStub()
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

    def test_register_package_orders_releases_descending(self) -> None:
        """POSTCONDITIONS: registration keeps releases ordered by descending precedence."""
        self.repository.register_package(_release("alpha", _version(1, 0, 0)))
        self.repository.register_package(_release("alpha", _version(2, 0, 0)))
        self.repository.register_package(_release("alpha", _version(1, 5, 0)))
        releases = self.repository.get_releases("alpha")
        self.assertEqual([release.version for release in releases], [
            _version(2, 0, 0),
            _version(1, 5, 0),
            _version(1, 0, 0),
        ])

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITIONS: returned release lists do not alias repository storage."""
        self.repository.register_package(_release("alpha", _version(1, 0, 0)))
        releases = self.repository.get_releases("alpha")
        releases.append(_release("alpha", _version(9, 0, 0)))
        self.assertEqual(len(self.repository.get_releases("alpha")), 1)

    def test_get_releases_missing_package_raises(self) -> None:
        """PRECONDITIONS: WHEN name is not registered, MUST raise PackageNotFoundError."""
        with self.assertRaises(PackageNotFoundError) as captured:
            self.repository.get_releases("missing")
        self.assertEqual(captured.exception.package_name, "missing")

    def test_has_package_and_all_packages(self) -> None:
        """POSTCONDITIONS: membership and package-name enumeration reflect registrations."""
        self.repository.register_package(_release("alpha", _version(1, 0, 0)))
        self.repository.register_package(_release("beta", _version(1, 0, 0)))
        self.assertTrue(self.repository.has_package("alpha"))
        self.assertFalse(self.repository.has_package("gamma"))
        self.assertEqual(self.repository.all_packages(), {"alpha", "beta"})

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """POSTCONDITIONS: the highest precedence compatible release is selected."""
        self.range_engine.constraints[">=1.0.0"] = _at_least(1)
        self.repository.register_package(_release("alpha", _version(1, 0, 0)))
        self.repository.register_package(_release("alpha", _version(2, 0, 0)))
        outcome = self.solver.resolve([_dependency("alpha", ">=1.0.0")])
        self.assertEqual(outcome.selected_versions, {"alpha": _version(2, 0, 0)})
        self.assertEqual(len(outcome.derivation_steps), 1)
        self.assertIn(False, self.range_engine.observed_prerelease_flags)

    def test_resolve_empty_roots(self) -> None:
        """POSTCONDITIONS: resolving no root dependencies yields an empty assignment."""
        outcome = self.solver.resolve([])
        self.assertEqual(outcome.selected_versions, {})
        self.assertEqual(outcome.derivation_steps, ())

    def test_resolve_prefers_fewest_candidates(self) -> None:
        """POSTCONDITIONS: the package with the fewest viable releases is assigned first."""
        self.repository.register_package(_release("alpha", _version(1, 0, 0)))
        self.repository.register_package(_release("alpha", _version(2, 0, 0)))
        self.repository.register_package(_release("beta", _version(1, 0, 0)))
        outcome = self.solver.resolve([
            _dependency("alpha", ">=1.0.0"),
            _dependency("beta", ">=1.0.0"),
        ])
        self.assertEqual(outcome.selected_versions, {
            "alpha": _version(2, 0, 0),
            "beta": _version(1, 0, 0),
        })
        self.assertIn("beta", outcome.derivation_steps[0])

    def test_resolve_backtracks_to_compatible_release(self) -> None:
        """POSTCONDITIONS: failing branches are undone so compatible assignments are found."""
        self.repository.register_package(_release(
            "alpha",
            _version(2, 0, 0),
            (_dependency("beta", ">=2.0.0"),),
        ))
        self.repository.register_package(_release(
            "alpha",
            _version(1, 0, 0),
            (_dependency("beta", ">=1.0.0"),),
        ))
        self.repository.register_package(_release("beta", _version(1, 0, 0)))
        self.range_engine.constraints[">=2.0.0"] = _at_least(2)
        self.range_engine.constraints[">=1.0.0"] = _at_least(1)
        outcome = self.solver.resolve([_dependency("alpha", ">=1.0.0")])
        self.assertEqual(outcome.selected_versions, {
            "alpha": _version(1, 0, 0),
            "beta": _version(1, 0, 0),
        })

    def test_resolve_detects_constraint_conflict_with_assigned_package(self) -> None:
        """POSTCONDITIONS: dependencies conflicting with prior assignments force alternatives."""
        self.repository.register_package(_release("beta", _version(1, 0, 0)))
        self.repository.register_package(_release(
            "alpha",
            _version(2, 0, 0),
            (_dependency("beta", ">=2.0.0"),),
        ))
        self.repository.register_package(_release(
            "alpha",
            _version(1, 0, 0),
            (_dependency("beta", ">=1.0.0"),),
        ))
        self.range_engine.constraints[">=2.0.0"] = _at_least(2)
        self.range_engine.constraints[">=1.0.0"] = _at_least(1)
        outcome = self.solver.resolve([
            _dependency("alpha", ">=1.0.0"),
            _dependency("beta", ">=1.0.0"),
        ])
        self.assertEqual(outcome.selected_versions, {
            "alpha": _version(1, 0, 0),
            "beta": _version(1, 0, 0),
        })

    def test_resolve_missing_package_raises_conflict(self) -> None:
        """PRECONDITIONS: missing packages raise ResolutionConflictError, never PackageNotFoundError."""
        with self.assertRaises(ResolutionConflictError) as captured:
            self.solver.resolve([_dependency("missing", ">=1.0.0")])
        self.assertIn("missing", captured.exception.conflicting_packages)
        self.assertTrue(captured.exception.explanation)

    def test_resolve_unsatisfiable_constraint_raises_conflict(self) -> None:
        """PRECONDITIONS: unsatisfiable constraints raise ResolutionConflictError."""
        self.repository.register_package(_release("alpha", _version(1, 0, 0)))
        self.range_engine.constraints[">=2.0.0"] = _at_least(2)
        with self.assertRaises(ResolutionConflictError) as captured:
            self.solver.resolve([_dependency("alpha", ">=2.0.0")])
        self.assertIn("alpha", captured.exception.conflicting_packages)
        self.assertTrue(captured.exception.explanation)

    def test_resolve_transitive_conflict_raises_conflict(self) -> None:
        """PRECONDITIONS: constraints left over from a failed branch are restored before failing."""
        self.repository.register_package(_release(
            "alpha",
            _version(1, 0, 0),
            (_dependency("beta", ">=2.0.0"),),
        ))
        self.repository.register_package(_release("beta", _version(1, 0, 0)))
        self.range_engine.constraints[">=2.0.0"] = _at_least(2)
        with self.assertRaises(ResolutionConflictError) as captured:
            self.solver.resolve([
                _dependency("alpha", ">=1.0.0"),
                _dependency("beta", ">=1.0.0"),
            ])
        self.assertIn("beta", captured.exception.conflicting_packages)
        self.assertTrue(captured.exception.explanation)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9109b65ffbe5
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for semver_core_impl per its grounding specification."""

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

    def test_parse_version_populates_all_components(self) -> None:
        """POSTCONDITIONS: parse full versions into major/minor/patch/prerelease/build tuples."""
        version = self.engine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prerelease, ("alpha", "1"))
        self.assertEqual(version.build, ("build", "5"))
        self.assertTrue(version.is_prerelease)
        self.assertEqual(version.format(), "1.2.3-alpha.1+build.5")
        self.assertEqual(str(version), "1.2.3-alpha.1+build.5")

    def test_parse_version_without_optional_segments(self) -> None:
        """POSTCONDITIONS: versions without prerelease/build yield empty tuples."""
        version = self.engine.parse_version("0.0.0")
        self.assertEqual(version.major, 0)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.prerelease, ())
        self.assertEqual(version.build, ())
        self.assertFalse(version.is_prerelease)
        self.assertEqual(version.format(), "0.0.0")

    def test_parse_version_rejects_malformed_grammar(self) -> None:
        """PRECONDITIONS: grammar violations raise InvalidVersionError with raw_text."""
        with self.assertRaises(InvalidVersionError) as captured:
            self.engine.parse_version("1.2")
        self.assertEqual(captured.exception.raw_text, "1.2")

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """PRECONDITIONS: numeric leading zeroes raise InvalidVersionError."""
        with self.assertRaises(InvalidVersionError) as captured:
            self.engine.parse_version("01.2.3")
        self.assertEqual(captured.exception.raw_text, "01.2.3")

    def test_compare_precedence_numeric_components(self) -> None:
        """POSTCONDITIONS: major, minor, and patch compare numerically in sequence."""
        self.assertLess(self.engine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0)
        self.assertLess(self.engine.compare_precedence(Version(1, 1, 0), Version(1, 2, 0)), 0)
        self.assertLess(self.engine.compare_precedence(Version(1, 1, 1), Version(1, 1, 2)), 0)
        self.assertGreater(self.engine.compare_precedence(Version(2, 0, 0), Version(1, 0, 0)), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: build metadata is excluded from precedence comparison."""
        left = Version(1, 0, 0, (), ("build", "1"))
        right = Version(1, 0, 0, (), ("build", "2"))
        self.assertEqual(self.engine.compare_precedence(left, right), 0)

    def test_compare_precedence_normal_outranks_prerelease(self) -> None:
        """POSTCONDITIONS: normal versions rank higher than prereleases of the same core."""
        normal = Version(1, 0, 0)
        prerelease = Version(1, 0, 0, ("alpha",))
        self.assertGreater(self.engine.compare_precedence(normal, prerelease), 0)
        self.assertLess(self.engine.compare_precedence(prerelease, normal), 0)

    def test_compare_precedence_prerelease_segments(self) -> None:
        """POSTCONDITIONS: numeric identifiers rank below string identifiers and compare numerically."""
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",))
            ),
            0,
        )
        self.assertGreater(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("1",))
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("2",))
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))
            ),
            0,
        )
        self.assertGreater(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("alpha",))
            ),
            0,
        )

    def test_compare_precedence_equal_identifier_prefixes(self) -> None:
        """POSTCONDITIONS: a longer prerelease sequence outranks a shorter matching prefix."""
        self.assertEqual(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "1"))
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1"))
            ),
            0,
        )
        self.assertGreater(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha",))
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: fd14d4cc0cf0
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for semver_range_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import Version, VersionEngine
from semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from semver_solver_multi.lib.semver_range_impl import RangeEngine as RangeEngineImpl
from semver_solver_multi.lib.semver_range_impl import __initialize__


class _VersionEngineStub:
    """Lightweight collaborator stub realizing SemVer 2.0.0 precedence ordering."""

    def parse_version(self, text: str) -> Version:
        parts = text.split(".")
        return Version(int(parts[0]), int(parts[1]), int(parts[2]))

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        if v1.major != v2.major:
            return v1.major - v2.major
        if v1.minor != v2.minor:
            return v1.minor - v2.minor
        if v1.patch != v2.patch:
            return v1.patch - v2.patch
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
                return int(left) - int(right)
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left < right else 1
        return len(v1.prerelease) - len(v2.prerelease)


def _version(
    major: int, minor: int = 0, patch: int = 0, prerelease: Tuple[str, ...] = ()
) -> Version:
    return Version(major, minor, patch, prerelease)


class SemverRangeImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register_instance(
            _VersionEngineStub(), keys=[VersionEngine], tier=system
        )
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = self.phase_scope.get_singleton(RangeEngineImpl)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_range_accepts_supported_grammar(self) -> None:
        """POSTCONDITIONS: comparators, caret, tilde, wildcard, hyphen, and unions parse."""
        cases = [
            ("1.0.0", "1.0.0"),
            ("1.0.0-alpha.1+build.2", "1.0.0-alpha.1+build.2"),
            ("*", "*"),
            ("1.x", "1.x"),
            ("1.2.x", "1.2.x"),
            (">=1.0.0", ">=1.0.0"),
            ("> 1.0.0", "> 1.0.0"),
            ("==1.0.0", "==1.0.0"),
            ("=1.0.0", "=1.0.0"),
            ("!=1.0.0", "!=1.0.0"),
            ("<1.0.0", "<1.0.0"),
            ("<=1.0.0", "<=1.0.0"),
            (">1.0.0", ">1.0.0"),
            (">= 1.x", ">= 1.x"),
            ("<1.x", "<1.x"),
            ("<=1.x", "<=1.x"),
            (">1.x", ">1.x"),
            ("==1.x", "==1.x"),
            ("!=1.x", "!=1.x"),
            (">=*", ">=*"),
            ("<=*", "<=*"),
            (">*", ">*"),
            ("!=*", "!=*"),
            ("==*", "==*"),
            ("^1.2.3", "^1.2.3"),
            ("^0.2.3", "^0.2.3"),
            ("^0.0.3", "^0.0.3"),
            ("^1.x", "^1.x"),
            ("^0.2.x", "^0.2.x"),
            ("^0.0.x", "^0.0.x"),
            ("^*", "^*"),
            ("~1.2.3", "~1.2.3"),
            ("~1.x", "~1.x"),
            ("~*", "~*"),
            ("1.0.0 - 2.0.0", "1.0.0 - 2.0.0"),
            ("1.0.0 - 2.x", "1.0.0 - 2.x"),
            ("1.x - *", "1.x - *"),
            (">=1.0.0 <2.0.0", ">=1.0.0 <2.0.0"),
            ("1.x || 2.x", "1.x || 2.x"),
            ("  >=1.0.0  ", ">=1.0.0"),
        ]
        for text, expected in cases:
            parsed = self.engine.parse_range(text)
            self.assertIsInstance(parsed, VersionRange)
            self.assertEqual(str(parsed), expected)

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """PRECONDITIONS: malformed range syntax raises InvalidRangeError with raw_range."""
        cases = [
            "",
            "   ",
            "||",
            "1.x || ",
            "1.x,2.x",
            "1.2",
            ">1.2",
            "^0.0",
            "1.2 - 2.3",
            "1.0.0 - 2.0.0 - 3.0.0",
            ">=",
            ">=" + " ",
            "1.x.2",
            "1.2.3.4",
            "abc",
            "^",
            "foo1.x",
            "01.0.0",
        ]
        for text in cases:
            with self.assertRaises(InvalidRangeError) as captured:
                self.engine.parse_range(text)
            self.assertEqual(captured.exception.raw_range, text)

    def test_satisfies_comparators(self) -> None:
        """POSTCONDITIONS: comparator clauses evaluate using precedence ordering."""
        exact = self.engine.parse_range("1.0.0")
        self.assertTrue(self.engine.satisfies(_version(1, 0, 0), exact, False))
        self.assertFalse(self.engine.satisfies(_version(1, 0, 1), exact, False))
        unequal = self.engine.parse_range("!=1.0.0")
        self.assertTrue(self.engine.satisfies(_version(1, 0, 1), unequal, False))
        greater = self.engine.parse_range(">1.0.0")
        self.assertTrue(self.engine.satisfies(_version(1, 0, 1), greater, False))
        self.assertFalse(self.engine.satisfies(_version(1, 0, 0), greater, False))
        greater_equal = self.engine.parse_range(">=1.0.0")
        self.assertTrue(self.engine.satisfies(_version(1, 0, 0), greater_equal, False))
        less = self.engine.parse_range("<1.0.0")
        self.assertTrue(self.engine.satisfies(_version(0, 9, 0), less, False))
        self.assertFalse(self.engine.satisfies(_version(1, 0, 0), less, False))
        less_equal = self.engine.parse_range("<=1.0.0")
        self.assertTrue(self.engine.satisfies(_version(1, 0, 0), less_equal, False))

    def test_satisfies_wildcard_expansions(self) -> None:
        """POSTCONDITIONS: wildcards expand into paired comparator inequalities."""
        minor_wildcard = self.engine.parse_range("1.x")
        self.assertTrue(self.engine.satisfies(_version(1, 5, 0), minor_wildcard, False))
        self.assertFalse(self.engine.satisfies(_version(2, 0, 0), minor_wildcard, False))
        at_least = self.engine.parse_range(">=1.x")
        self.assertTrue(self.engine.satisfies(_version(1, 0, 0), at_least, False))
        self.assertTrue(self.engine.satisfies(_version(5, 0, 0), at_least, False))
        below = self.engine.parse_range("<1.x")
        self.assertTrue(self.engine.satisfies(_version(0, 9, 0), below, False))
        self.assertFalse(self.engine.satisfies(_version(1, 0, 0), below, False))
        at_most = self.engine.parse_range("<=1.x")
        self.assertTrue(self.engine.satisfies(_version(1, 9, 0), at_most, False))
        self.assertFalse(self.engine.satisfies(_version(2, 0, 0), at_most, False))
        above = self.engine.parse_range(">1.x")
        self.assertTrue(self.engine.satisfies(_version(2, 0, 0), above, False))
        self.assertFalse(self.engine.satisfies(_version(1, 9, 0), above, False))
        not_minor = self.engine.parse_range("!=1.x")
        self.assertTrue(self.engine.satisfies(_version(0, 9, 0), not_minor, False))
        self.assertTrue(self.engine.satisfies(_version(2, 0, 0), not_minor, False))
        self.assertFalse(self.engine.satisfies(_version(1, 5, 0), not_minor, False))

    def test_satisfies_unbounded_wildcards(self) -> None:
        """POSTCONDITIONS: unbounded wildcards yield vacuous or unsatisfiable clauses."""
        everything = self.engine.parse_range("<=*")
        self.assertTrue(self.engine.satisfies(_version(9, 9, 9), everything, False))
        nothing = self.engine.parse_range(">*")
        self.assertFalse(self.engine.satisfies(_version(9, 9, 9), nothing, False))
        any_version = self.engine.parse_range("==*")
        self.assertTrue(self.engine.satisfies(_version(3, 0, 0), any_version, False))
        never = self.engine.parse_range("!=*")
        self.assertFalse(self.engine.satisfies(_version(3, 0, 0), never, False))

    def test_satisfies_caret_and_tilde(self) -> None:
        """POSTCONDITIONS: caret and tilde prefixes bound upper precedence ranges."""
        caret_major = self.engine.parse_range("^1.2.3")
        self.assertTrue(self.engine.satisfies(_version(1, 9, 0), caret_major, False))
        self.assertFalse(self.engine.satisfies(_version(2, 0, 0), caret_major, False))
        caret_minor = self.engine.parse_range("^0.2.3")
        self.assertTrue(self.engine.satisfies(_version(0, 2, 9), caret_minor, False))
        self.assertFalse(self.engine.satisfies(_version(0, 3, 0), caret_minor, False))
        caret_patch = self.engine.parse_range("^0.0.3")
        self.assertTrue(self.engine.satisfies(_version(0, 0, 3), caret_patch, False))
        self.assertFalse(self.engine.satisfies(_version(0, 0, 4), caret_patch, False))
        caret_wildcard = self.engine.parse_range("^1.x")
        self.assertTrue(self.engine.satisfies(_version(1, 4, 0), caret_wildcard, False))
        self.assertFalse(self.engine.satisfies(_version(2, 0, 0), caret_wildcard, False))
        caret_zero_minor_wildcard = self.engine.parse_range("^0.2.x")
        self.assertTrue(self.engine.satisfies(_version(0, 2, 5), caret_zero_minor_wildcard, False))
        self.assertFalse(self.engine.satisfies(_version(0, 3, 0), caret_zero_minor_wildcard, False))
        caret_zero_zero_wildcard = self.engine.parse_range("^0.0.x")
        self.assertTrue(self.engine.satisfies(_version(0, 0, 5), caret_zero_zero_wildcard, False))
        self.assertFalse(self.engine.satisfies(_version(0, 1, 0), caret_zero_zero_wildcard, False))
        caret_any = self.engine.parse_range("^*")
        self.assertTrue(self.engine.satisfies(_version(0, 0, 0), caret_any, False))
        self.assertTrue(self.engine.satisfies(_version(5, 0, 0), caret_any, False))
        tilde_version = self.engine.parse_range("~1.2.3")
        self.assertTrue(self.engine.satisfies(_version(1, 2, 9), tilde_version, False))
        self.assertFalse(self.engine.satisfies(_version(1, 3, 0), tilde_version, False))
        tilde_wildcard = self.engine.parse_range("~1.x")
        self.assertTrue(self.engine.satisfies(_version(1, 9, 0), tilde_wildcard, False))
        self.assertFalse(self.engine.satisfies(_version(2, 0, 0), tilde_wildcard, False))
        tilde_any = self.engine.parse_range("~*")
        self.assertTrue(self.engine.satisfies(_version(1, 0, 0), tilde_any, False))

    def test_satisfies_hyphen_ranges(self) -> None:
        """POSTCONDITIONS: hyphen ranges connect inclusive lower and upper bounds."""
        version_hyphen = self.engine.parse_range("1.0.0 - 2.0.0")
        self.assertTrue(self.engine.satisfies(_version(1, 5, 0), version_hyphen, False))
        self.assertTrue(self.engine.satisfies(_version(2, 0, 0), version_hyphen, False))
        self.assertFalse(self.engine.satisfies(_version(2, 0, 1), version_hyphen, False))
        wildcard_hyphen = self.engine.parse_range("1.0.0 - 2.x")
        self.assertTrue(self.engine.satisfies(_version(2, 9, 0), wildcard_hyphen, False))
        self.assertFalse(self.engine.satisfies(_version(3, 0, 0), wildcard_hyphen, False))
        open_hyphen = self.engine.parse_range("1.x - *")
        self.assertTrue(self.engine.satisfies(_version(9, 9, 9), open_hyphen, False))
        self.assertFalse(self.engine.satisfies(_version(0, 9, 0), open_hyphen, False))

    def test_satisfies_unions_and_conjunctions(self) -> None:
        """POSTCONDITIONS: one satisfied clause is sufficient and every comparator must hold."""
        union = self.engine.parse_range("1.x || 2.x")
        self.assertTrue(self.engine.satisfies(_version(2, 5, 0), union, False))
        self.assertFalse(self.engine.satisfies(_version(3, 0, 0), union, False))
        conjunction = self.engine.parse_range(">=1.0.0 <2.0.0")
        self.assertTrue(self.engine.satisfies(_version(1, 5, 0), conjunction, False))
        self.assertFalse(self.engine.satisfies(_version(2, 5, 0), conjunction, False))

    def test_satisfies_prerelease_filtering(self) -> None:
        """POSTCONDITIONS: prereleases only match ranges explicitly targeting their core."""
        release_range = self.engine.parse_range(">=1.0.0")
        self.assertFalse(
            self.engine.satisfies(_version(1, 0, 0, ("alpha",)), release_range, False)
        )
        targeting = self.engine.parse_range(">=1.0.0-alpha")
        self.assertTrue(
            self.engine.satisfies(_version(1, 0, 0, ("beta",)), targeting, False)
        )
        self.assertFalse(
            self.engine.satisfies(_version(1, 0, 0, ("beta",)), release_range, True)
        )
        self.assertFalse(
            self.engine.satisfies(_version(1, 0, 0, ("alpha",)), release_range, True)
        )


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:34:44Z
# LAST_CHANGED: 2026-11-07T03:34:44Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: f950b8dfcc11
# COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:34:44Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:34:44Z
# QA_AUDIT: 2026-11-07T03:34:44Z
# --- END AUTOFAB METADATA ---
