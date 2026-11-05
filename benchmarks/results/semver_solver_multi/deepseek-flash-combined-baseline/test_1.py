# === File: dependency_solver_impl_test.py ===
"""Contract tests for the concrete package repository and backtracking dependency solver."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

# Resolve the benchmark parts root so the package-qualified unit imports below resolve
# identically under the harness dry-run and the pytest execution path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
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


class _VersionEngineDouble(VersionEngine):
    """Collaborator double supplying SemVer precedence ordering to the solver tests."""

    def parse_version(self, text: str) -> Version:
        return Version(0, 0, 0)

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        left_triple = (v1.major, v1.minor, v1.patch)
        right_triple = (v2.major, v2.minor, v2.patch)
        if left_triple != right_triple:
            return -1 if left_triple < right_triple else 1
        if v1.prerelease and not v2.prerelease:
            return -1
        if v2.prerelease and not v1.prerelease:
            return 1
        for left_id, right_id in zip(v1.prerelease, v2.prerelease):
            if left_id == right_id:
                continue
            left_numeric = left_id.isdigit()
            right_numeric = right_id.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left_id) < int(right_id) else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left_id < right_id else 1
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


class _RangeEngineDouble(RangeEngine):
    """Collaborator double interpreting 'any' as unconstrained and other text as exact."""

    def parse_range(self, text: str) -> VersionRange:
        return VersionRange(text.strip())

    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        if range_constraint.raw_text == "any":
            return True
        return version.format() == range_constraint.raw_text


def _dependency(name: str, constraint: str) -> PackageDependency:
    return PackageDependency(name, VersionRange(constraint))


class DependencySolverImplTest(unittest.TestCase):
    """Verifies repository indexing and solver contract postconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register_instance(
            _VersionEngineDouble(), keys=[VersionEngine], tier=system
        )
        self.registry.register_instance(
            _RangeEngineDouble(), keys=[RangeEngine], tier=system
        )

    def test_repository_register_package_orders_releases_descending(self) -> None:
        """Postcondition: get_releases yields all releases by descending precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("pkg", Version(1, 0, 0)))
            repository.register_package(PackageRelease("pkg", Version(2, 0, 0)))
            repository.register_package(PackageRelease("pkg", Version(1, 5, 0)))

            releases = repository.get_releases("pkg")
            self.assertEqual(
                [release.version.format() for release in releases],
                ["2.0.0", "1.5.0", "1.0.0"],
            )
            self.assertTrue(repository.has_package("pkg"))
            self.assertFalse(repository.has_package("other"))
            self.assertEqual(repository.all_packages(), {"pkg"})

    def test_repository_get_releases_missing_package_raises(self) -> None:
        """Precondition: an unregistered name raises PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as context:
                repository.get_releases("absent")
            self.assertEqual(context.exception.package_name, "absent")

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """Postcondition: the highest precedence compatible release is selected."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("pkg", Version(1, 0, 0)))
            repository.register_package(PackageRelease("pkg", Version(2, 0, 0)))
            solver = scope.get_singleton(DependencySolver)

            outcome = solver.resolve([_dependency("pkg", "any")])

            self.assertEqual(outcome.selected_versions["pkg"].format(), "2.0.0")
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_backtracks_on_conflicting_transitive_requirement(self) -> None:
        """Postcondition: a conflicting candidate is abandoned for a lower compatible one."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("q", Version(1, 0, 0)))
            repository.register_package(PackageRelease("q", Version(2, 0, 0)))
            repository.register_package(
                PackageRelease(
                    "pkg",
                    Version(2, 0, 0),
                    dependencies=(_dependency("q", "1.0.0"),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "pkg",
                    Version(1, 0, 0),
                    dependencies=(_dependency("q", "2.0.0"),),
                )
            )
            solver = scope.get_singleton(DependencySolver)

            outcome = solver.resolve(
                [_dependency("q", "2.0.0"), _dependency("pkg", "any")]
            )

            self.assertEqual(outcome.selected_versions["q"].format(), "2.0.0")
            self.assertEqual(outcome.selected_versions["pkg"].format(), "1.0.0")

    def test_resolve_backtracking_discards_introduced_constraints(self) -> None:
        """Sequencing: a failed candidate's introduced constraints are removed on backtrack."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                PackageRelease(
                    "pkg",
                    Version(2, 0, 0),
                    dependencies=(_dependency("ghost", "9.9.9"),),
                )
            )
            repository.register_package(PackageRelease("pkg", Version(1, 0, 0)))
            solver = scope.get_singleton(DependencySolver)

            outcome = solver.resolve([_dependency("pkg", "any")])

            self.assertEqual(outcome.selected_versions["pkg"].format(), "1.0.0")

    def test_resolve_raises_conflict_when_candidates_exhaust(self) -> None:
        """Postcondition: unsatisfiable dependencies raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                PackageRelease(
                    "pkg",
                    Version(2, 0, 0),
                    dependencies=(_dependency("ghost", "9.9.9"),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "pkg",
                    Version(1, 0, 0),
                    dependencies=(_dependency("ghost", "9.9.9"),),
                )
            )
            solver = scope.get_singleton(DependencySolver)

            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([_dependency("pkg", "any")])

            self.assertIn("pkg", context.exception.conflicting_packages)
            self.assertIn("ghost", context.exception.conflicting_packages)
            self.assertGreater(len(context.exception.explanation), 0)

    def test_resolve_raises_conflict_for_missing_root_package(self) -> None:
        """Postcondition: absent packages surface as ResolutionConflictError with no candidates."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)

            with self.assertRaises(ResolutionConflictError) as context:
                solver.resolve([_dependency("absent", "any")])

            self.assertIn("absent", context.exception.conflicting_packages)
            self.assertIn("root", context.exception.conflicting_packages)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b81d9e326a72
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Contract tests for the concrete SemVer 2.0.0 parsing and precedence engine."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

# Resolve the benchmark parts root so the package-qualified unit imports below resolve
# identically under the harness dry-run and the pytest execution path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from semver_solver_multi.lib.semver_core_impl import VersionEngine, __initialize__


class VersionEngineImplTest(unittest.TestCase):
    """Verifies SemVer 2.0.0 parsing and precedence postconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_produces_all_components(self) -> None:
        """Postcondition: valid strings parse into Version records with every component."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            plain = engine.parse_version("1.2.3")
            self.assertEqual(
                (plain.major, plain.minor, plain.patch), (1, 2, 3)
            )
            self.assertEqual(plain.prerelease, ())
            self.assertEqual(plain.build, ())
            tagged = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(tagged.prerelease, ("alpha", "1"))
            self.assertEqual(tagged.build, ("build", "5"))
            self.assertTrue(tagged.is_prerelease)
            self.assertEqual(tagged.format(), "1.2.3-alpha.1+build.5")

    def test_parse_version_rejects_grammar_and_leading_zeroes(self) -> None:
        """Precondition: grammar violations and leading zeroes raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for malformed in (
                "1.2",
                "1.2.3.4",
                "01.2.3",
                "1.2.3-01",
                "1.2.3+",
                "v1.2.3",
            ):
                with self.assertRaises(InvalidVersionError) as context:
                    engine.parse_version(malformed)
                self.assertEqual(context.exception.raw_text, malformed)

    def test_compare_precedence_numeric_components(self) -> None:
        """Postcondition: major, minor, and patch compare numerically in sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0
            )
            self.assertGreater(
                engine.compare_precedence(Version(1, 2, 0), Version(1, 1, 0)), 0
            )
            self.assertGreater(
                engine.compare_precedence(Version(1, 1, 2), Version(1, 1, 1)), 0
            )

    def test_compare_precedence_normal_outranks_prerelease(self) -> None:
        """Postcondition: normal versions outrank prereleases sharing the same triple."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(
                    Version(1, 0, 0), Version(1, 0, 0, ("alpha",))
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)
                ),
                0,
            )

    def test_compare_precedence_prerelease_identifiers(self) -> None:
        """Postcondition: prerelease segments compare numerically, then ASCII, numeric below string."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha", "1")),
                    Version(1, 0, 0, ("alpha", "2")),
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha", "10")),
                    Version(1, 0, 0, ("alpha", "2")),
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha", "1")),
                    Version(1, 0, 0, ("alpha", "beta")),
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha", "beta")),
                    Version(1, 0, 0, ("alpha", "1")),
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))
                ),
                0,
            )

    def test_compare_precedence_prerelease_length(self) -> None:
        """Postcondition: a longer prerelease sequence outranks its common prefix."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha",)),
                    Version(1, 0, 0, ("alpha", "1")),
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha", "1")),
                    Version(1, 0, 0, ("alpha",)),
                ),
                0,
            )

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """Postcondition: build metadata never affects precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(
                    Version(1, 0, 0, (), ("build", "1")),
                    Version(1, 0, 0, (), ("build", "2")),
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(Version(2, 3, 4), Version(2, 3, 4)), 0
            )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b6aa872b5b7b
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Contract tests for the concrete version range parsing and matching engine."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system

# Resolve the benchmark parts root so the package-qualified unit imports below resolve
# identically under the harness dry-run and the pytest execution path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from semver_solver_multi.lib.semver_core import Version, VersionEngine
from semver_solver_multi.lib.semver_range import InvalidRangeError
from semver_solver_multi.lib.semver_range_impl import RangeEngine, __initialize__


class _VersionEngineDouble(VersionEngine):
    """Collaborator double supplying SemVer precedence ordering to the range tests."""

    def parse_version(self, text: str) -> Version:
        return Version(0, 0, 0)

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        left_triple = (v1.major, v1.minor, v1.patch)
        right_triple = (v2.major, v2.minor, v2.patch)
        if left_triple != right_triple:
            return -1 if left_triple < right_triple else 1
        if v1.prerelease and not v2.prerelease:
            return -1
        if v2.prerelease and not v1.prerelease:
            return 1
        for left_id, right_id in zip(v1.prerelease, v2.prerelease):
            if left_id == right_id:
                continue
            left_numeric = left_id.isdigit()
            right_numeric = right_id.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left_id) < int(right_id) else 1
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return -1 if left_id < right_id else 1
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


class RangeEngineImplTest(unittest.TestCase):
    """Verifies range grammar parsing and constraint satisfaction postconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register_instance(
            _VersionEngineDouble(), keys=[VersionEngine], tier=system
        )

    def _check(
        self,
        scope: LifecycleScope,
        range_text: str,
        version: Version,
        expected: bool,
        include_prerelease: bool = False,
    ) -> None:
        engine = scope.get_singleton(RangeEngine)
        constraint = engine.parse_range(range_text)
        self.assertEqual(
            engine.satisfies(version, constraint, include_prerelease), expected
        )

    def test_parse_range_trims_expression(self) -> None:
        """Postcondition: surrounding whitespace is trimmed into raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range("  >=1.0.0  ")
            self.assertEqual(constraint.raw_text, ">=1.0.0")
            self.assertEqual(str(constraint), ">=1.0.0")

    def test_parse_range_supports_grammar_constructs(self) -> None:
        """Postcondition: comparators, prefixes, wildcards, hyphens, and unions parse."""
        valid = (
            "1.2.3",
            "==1.2.3",
            "=1.2.3",
            "!=1.2.3",
            "<1.2.3",
            "<=1.2.3",
            ">1.2.3",
            ">=1.2.3",
            ">= 1.2.3",
            "^1.2.3",
            "~1.2.3",
            "*",
            "x",
            "X",
            "==*",
            "1.x",
            "1.*",
            "1.2.x",
            "1.2.*",
            "==1.x",
            "!=1.x",
            ">=1.x",
            ">1.x",
            "<1.x",
            "<=1.x",
            "1.2.3 - 2.0.0",
            "* - 2.0.0",
            "1.0.0 - *",
            "1.x - 2.x",
            ">=1.0.0 <2.0.0",
            "1.0.0 || >=2.0.0",
            ">=1.0.0-alpha.1",
            "^1.2.3-alpha.1+build.5",
        )
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in valid:
                constraint = engine.parse_range(text)
                self.assertEqual(constraint.raw_text, text.strip())

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """Precondition: malformed expressions raise InvalidRangeError."""
        malformed = (
            "",
            "   ",
            "1",
            "1.2",
            "^0.0",
            "~1",
            "1.2 - 2.3",
            "1.0.0, <2.0.0",
            "1.0.0 || ",
            "|| 1.0.0",
            "01.0.0",
            "1.0.0+bad_1",
            "1.0.0-alpha..1",
            "1.0.0-",
            "1.0.*-alpha",
            "1.2.3.x",
            ">=",
            "^1.x",
            "~1.x",
            "!=*",
            ">=*",
            "<*",
            "1.0.0 - ",
            "1.0.0 - 2.0.0 - 3.0.0",
            "1.0.0 - 2.0.0 extra",
        )
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in malformed:
                with self.assertRaises(InvalidRangeError) as context:
                    engine.parse_range(text)
                self.assertEqual(context.exception.raw_range, text)

    def test_satisfies_comparator_operators(self) -> None:
        """Postcondition: every basic comparator evaluates boundary membership."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, "1.2.3", Version(1, 2, 3), True)
            self._check(scope, "1.2.3", Version(1, 2, 4), False)
            self._check(scope, "==1.2.3", Version(1, 2, 3), True)
            self._check(scope, "=1.2.3", Version(1, 2, 3), True)
            self._check(scope, "!=1.2.3", Version(1, 2, 3), False)
            self._check(scope, "!=1.2.3", Version(1, 2, 4), True)
            self._check(scope, "<2.0.0", Version(1, 9, 9), True)
            self._check(scope, "<2.0.0", Version(2, 0, 0), False)
            self._check(scope, "<=2.0.0", Version(2, 0, 0), True)
            self._check(scope, "<=2.0.0", Version(2, 0, 1), False)
            self._check(scope, ">1.0.0", Version(1, 0, 1), True)
            self._check(scope, ">1.0.0", Version(1, 0, 0), False)
            self._check(scope, ">=1.0.0", Version(1, 0, 0), True)
            self._check(scope, ">=1.0.0", Version(0, 9, 9), False)

    def test_satisfies_wildcard_patterns(self) -> None:
        """Postcondition: wildcards expand to their numeric prefix range."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, "*", Version(5, 0, 0), True)
            self._check(scope, "x", Version(5, 0, 0), True)
            self._check(scope, "X", Version(5, 0, 0), True)
            self._check(scope, "==*", Version(5, 0, 0), True)
            self._check(scope, "1.x", Version(1, 5, 0), True)
            self._check(scope, "1.x", Version(2, 0, 0), False)
            self._check(scope, "1.*", Version(1, 5, 0), True)
            self._check(scope, "1.2.x", Version(1, 2, 9), True)
            self._check(scope, "1.2.x", Version(1, 3, 0), False)
            self._check(scope, "1.2.*", Version(1, 2, 0), True)
            self._check(scope, "==1.x", Version(1, 5, 0), True)
            self._check(scope, "==1.x", Version(2, 0, 0), False)

    def test_satisfies_relational_wildcards(self) -> None:
        """Postcondition: relational wildcards shift to the range boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, ">=1.x", Version(1, 0, 0), True)
            self._check(scope, ">=1.x", Version(0, 9, 0), False)
            self._check(scope, "<1.x", Version(0, 9, 0), True)
            self._check(scope, "<1.x", Version(1, 0, 0), False)
            self._check(scope, ">1.x", Version(2, 0, 0), True)
            self._check(scope, ">1.x", Version(1, 9, 0), False)
            self._check(scope, "<=1.x", Version(1, 9, 0), True)
            self._check(scope, "<=1.x", Version(2, 0, 0), False)

    def test_satisfies_not_in_wildcard(self) -> None:
        """Postcondition: '!=' over a wildcard excludes the whole expanded interval."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, "!=1.x", Version(1, 5, 0), False)
            self._check(scope, "!=1.x", Version(2, 5, 0), True)
            self._check(scope, "!=1.x", Version(0, 5, 0), True)

    def test_satisfies_caret_ranges(self) -> None:
        """Postcondition: caret ranges cap at the first non-zero component boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, "^1.2.3", Version(1, 9, 9), True)
            self._check(scope, "^1.2.3", Version(2, 0, 0), False)
            self._check(scope, "^1.2.3", Version(1, 2, 2), False)
            self._check(scope, "^0.2.3", Version(0, 2, 9), True)
            self._check(scope, "^0.2.3", Version(0, 3, 0), False)
            self._check(scope, "^0.0.3", Version(0, 0, 3), True)
            self._check(scope, "^0.0.3", Version(0, 0, 4), False)

    def test_satisfies_tilde_ranges(self) -> None:
        """Postcondition: tilde ranges cap at the next minor boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, "~1.2.3", Version(1, 2, 9), True)
            self._check(scope, "~1.2.3", Version(1, 3, 0), False)
            self._check(scope, "~1.2.3", Version(1, 2, 2), False)

    def test_satisfies_hyphen_ranges(self) -> None:
        """Postcondition: hyphen ranges expand into lower and upper boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, "1.2.3 - 2.0.0", Version(1, 5, 0), True)
            self._check(scope, "1.2.3 - 2.0.0", Version(2, 0, 1), False)
            self._check(scope, "1.2.3 - 2.0.0", Version(1, 2, 2), False)
            self._check(scope, "* - 2.0.0", Version(0, 1, 0), True)
            self._check(scope, "* - 2.0.0", Version(2, 0, 1), False)
            self._check(scope, "1.0.0 - *", Version(3, 0, 0), True)
            self._check(scope, "1.x - 2.x", Version(1, 5, 0), True)
            self._check(scope, "1.x - 2.x", Version(2, 9, 0), True)
            self._check(scope, "1.x - 2.x", Version(3, 0, 0), False)
            self._check(scope, "1.2.3 - 2.x", Version(2, 9, 0), True)
            self._check(scope, "1.2.3 - 2.x", Version(3, 0, 0), False)

    def test_satisfies_union_clauses(self) -> None:
        """Postcondition: a version satisfies the union when one clause matches."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, "1.0.0 || >=2.0.0", Version(1, 0, 0), True)
            self._check(scope, "1.0.0 || >=2.0.0", Version(2, 5, 0), True)
            self._check(scope, "1.0.0 || >=2.0.0", Version(1, 5, 0), False)

    def test_satisfies_prerelease_handling(self) -> None:
        """Postcondition: prereleases require an explicit same-triple prerelease target."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, ">=1.0.0", Version(1, 0, 0, ("alpha",)), False)
            self._check(
                scope, ">=1.0.0", Version(1, 0, 0, ("alpha",)), False, True
            )
            self._check(
                scope, ">=1.0.0-alpha", Version(1, 0, 0, ("alpha",)), True
            )
            self._check(
                scope, ">0.9.0", Version(1, 0, 0, ("alpha",)), True, True
            )
            self._check(scope, "!=1.x", Version(1, 5, 0, ("alpha",)), False)
            self._check(scope, ">=1.0.0", Version(1, 5, 0), True)

    def test_satisfies_whitespace_between_operators(self) -> None:
        """Postcondition: optional whitespace separates operators from targets."""
        with enter_phase(system, registry=self.registry) as scope:
            self._check(scope, ">= 1.0.0", Version(1, 0, 0), True)
            self._check(scope, "^ 1.2.3", Version(1, 5, 0), True)
            self._check(scope, "~ 1.2.3", Version(1, 2, 9), True)
            self._check(scope, "1.0.0  -  2.0.0", Version(1, 5, 0), True)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T05:40:11Z
# LAST_CHANGED: 2026-11-05T05:40:11Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: ea9af48268d0
# COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T05:40:11Z
# PRETENSE_QA_AUDIT: 2026-11-05T05:40:11Z
# QA_AUDIT: 2026-11-05T05:40:11Z
# --- END AUTOFAB METADATA ---
