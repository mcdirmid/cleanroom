# === File: dependency_solver_impl_test.py ===
"""Unit tests for dependency_solver_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import List, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
)
from semver_solver_multi.lib.semver_core import Version, VersionEngine
from semver_solver_multi.lib.semver_range import RangeEngine, VersionRange
from semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)


def version(text: str) -> Version:
    major, minor, patch = text.split(".")
    return Version(int(major), int(minor), int(patch))


def dependency(name: str, range_text: str) -> PackageDependency:
    return PackageDependency(name, VersionRange(range_text))


def release(
    name: str,
    version_text: str,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    return PackageRelease(name, version(version_text), dependencies)


class StubVersionEngine:
    """Lightweight VersionEngine collaborator providing SemVer precedence ordering."""

    def parse_version(self, text: str) -> Version:
        return version(text)

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        core1 = (v1.major, v1.minor, v1.patch)
        core2 = (v2.major, v2.minor, v2.patch)
        if core1 != core2:
            return 1 if core1 > core2 else -1
        if v1.prerelease == v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        return 1 if v1.prerelease > v2.prerelease else -1


class StubRangeEngine:
    """Scripted RangeEngine collaborator recording satisfaction queries."""

    def __init__(self) -> None:
        self.calls: List[Tuple[Version, VersionRange, bool]] = []
        self.rejected_versions: Set[str] = set()
        self.rejected_ranges: Set[str] = set()

    def parse_range(self, text: str) -> VersionRange:
        return VersionRange(text)

    def satisfies(
        self,
        candidate: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        self.calls.append((candidate, range_constraint, include_prerelease))
        if candidate.format() in self.rejected_versions:
            return False
        return range_constraint.raw_text not in self.rejected_ranges


class DependencySolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = StubVersionEngine()
        self.range_engine = StubRangeEngine()
        self.registry.register_instance(self.version_engine, keys=[VersionEngine], tier=system)
        self.registry.register_instance(self.range_engine, keys=[RangeEngine], tier=system)

    def test_repository_registers_and_orders_releases(self) -> None:
        """Happy path: releases register into the repository and order by descending precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(release("alpha", "1.0.0"))
            repository.register_package(release("alpha", "2.0.0"))
            repository.register_package(release("alpha", "1.5.0"))
            ordered = repository.get_releases("alpha")
            self.assertEqual([str(item.version) for item in ordered], ["2.0.0", "1.5.0", "1.0.0"])
            self.assertIsNot(ordered, repository.get_releases("alpha"))
            self.assertTrue(repository.has_package("alpha"))
            self.assertFalse(repository.has_package("beta"))
            self.assertEqual(repository.all_packages(), {"alpha"})

    def test_repository_missing_package_raises(self) -> None:
        """Checked precondition: unknown package names MUST raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("missing"))
            self.assertEqual(repository.all_packages(), set())
            with self.assertRaises(PackageNotFoundError) as caught:
                repository.get_releases("missing")
            self.assertEqual(caught.exception.package_name, "missing")

    def test_resolve_selects_highest_transitive_versions(self) -> None:
        """Postconditions: the highest compatible releases satisfy transitive requirements."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(release("a", "1.0.0"))
            repository.register_package(release("a", "2.0.0", (dependency("b", ">=1.0.0"),)))
            repository.register_package(release("b", "1.0.0"))
            repository.register_package(release("b", "2.0.0"))
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([dependency("a", ">=1.0.0")])
            self.assertEqual(str(outcome.selected_versions["a"]), "2.0.0")
            self.assertEqual(str(outcome.selected_versions["b"]), "2.0.0")
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_filters_incompatible_releases(self) -> None:
        """Postcondition: only releases satisfying the accumulated range constraints are selected."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(release("a", "1.0.0"))
            repository.register_package(release("a", "2.0.0"))
            self.range_engine.rejected_versions.add("1.0.0")
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([dependency("a", ">=1.0.0")])
            self.assertEqual(str(outcome.selected_versions["a"]), "2.0.0")

    def test_resolve_accepts_assigned_compatible_dependency(self) -> None:
        """Postcondition: an already assigned release satisfying a new requirement needs no new constraint."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(release("a", "1.0.0"))
            repository.register_package(release("a", "2.0.0", (dependency("b", ">=1.0.0"),)))
            repository.register_package(release("b", "1.0.0"))
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([dependency("b", ">=1.0.0"), dependency("a", ">=1.0.0")])
            self.assertEqual(str(outcome.selected_versions["a"]), "2.0.0")
            self.assertEqual(str(outcome.selected_versions["b"]), "1.0.0")

    def test_resolve_backtracks_on_assigned_conflict(self) -> None:
        """Postcondition: a candidate violating an already assigned dependency is rejected and retried."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(release("a", "1.0.0"))
            repository.register_package(release("a", "2.0.0", (dependency("b", "bad"),)))
            repository.register_package(release("b", "1.0.0"))
            self.range_engine.rejected_ranges.add("bad")
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([dependency("b", ">=1.0.0"), dependency("a", ">=1.0.0")])
            self.assertEqual(str(outcome.selected_versions["a"]), "1.0.0")
            self.assertEqual(str(outcome.selected_versions["b"]), "1.0.0")

    def test_resolve_backtracks_and_restores_transitive_constraint(self) -> None:
        """Postcondition: an unsatisfiable branch drops the constraints it introduced before retrying."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(release("a", "1.0.0"))
            repository.register_package(release("a", "2.0.0", (dependency("b", "bad"),)))
            repository.register_package(release("b", "1.0.0"))
            self.range_engine.rejected_ranges.add("bad")
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([dependency("a", ">=1.0.0")])
            self.assertEqual(str(outcome.selected_versions["a"]), "1.0.0")
            self.assertNotIn("b", outcome.selected_versions)

    def test_resolve_backtracks_preserving_other_constraints(self) -> None:
        """Postcondition: retracting one requirement preserves remaining constraints on the package."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(release("a", "1.0.0"))
            repository.register_package(release("a", "2.0.0", (dependency("b", "bad"),)))
            repository.register_package(release("b", "0.5.0"))
            repository.register_package(release("b", "1.0.0"))
            self.range_engine.rejected_ranges.add("bad")
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([dependency("b", ">=0.0.0"), dependency("a", ">=1.0.0")])
            self.assertEqual(str(outcome.selected_versions["a"]), "1.0.0")
            self.assertEqual(str(outcome.selected_versions["b"]), "1.0.0")

    def test_resolve_conflict_for_missing_package(self) -> None:
        """Checked precondition: missing packages MUST surface as ResolutionConflictError, not PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as caught:
                solver.resolve([dependency("ghost", ">=1.0.0")])
            self.assertIn("ghost", caught.exception.conflicting_packages)

    def test_resolve_conflict_when_candidates_exhausted(self) -> None:
        """Checked precondition: mutually unsatisfiable constraints MUST raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(release("a", "1.0.0", (dependency("b", "bad"),)))
            repository.register_package(release("a", "2.0.0", (dependency("b", "bad"),)))
            repository.register_package(release("b", "1.0.0"))
            self.range_engine.rejected_ranges.add("bad")
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as caught:
                solver.resolve([dependency("a", ">=1.0.0")])
            self.assertIn("b", caught.exception.conflicting_packages)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:00:47Z
# LAST_CHANGED: 2026-11-05T17:00:47Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 677d6b5f49f8
# COVERAGE_AUDIT: 2026-11-05T17:00:47Z
# QA_AUDIT: 2026-11-05T17:00:47Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for semver_core_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
    __initialize__,
)


class SemverCoreImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_release_version(self) -> None:
        """Happy path: valid release parses into numeric components with no prerelease or build."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ())
            self.assertFalse(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3")
            self.assertEqual(str(version), "1.2.3")

    def test_parse_prerelease_and_build_version(self) -> None:
        """Happy path: prerelease identifiers and build metadata are extracted as ordered tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("2.0.1-alpha.1+build.7")
            self.assertEqual(version.major, 2)
            self.assertEqual(version.minor, 0)
            self.assertEqual(version.patch, 1)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "7"))
            self.assertTrue(version.is_prerelease)
            self.assertEqual(version.format(), "2.0.1-alpha.1+build.7")
            self.assertEqual(str(version), "2.0.1-alpha.1+build.7")

    def test_parse_rejects_malformed_version(self) -> None:
        """Checked precondition: grammar violations MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidVersionError) as caught:
                engine.parse_version("1.2")
            self.assertEqual(caught.exception.raw_text, "1.2")

    def test_parse_rejects_leading_zeroes(self) -> None:
        """Checked precondition: leading zeroes in numeric identifiers MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidVersionError) as caught_core:
                engine.parse_version("01.2.3")
            self.assertEqual(caught_core.exception.raw_text, "01.2.3")
            with self.assertRaises(InvalidVersionError) as caught_prerelease:
                engine.parse_version("1.2.3-01")
            self.assertEqual(caught_prerelease.exception.raw_text, "1.2.3-01")

    def test_compare_numeric_components(self) -> None:
        """Postcondition: major, minor, and patch compare numerically in sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(2, 0, 0), Version(1, 0, 0)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 1, 0), Version(1, 2, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 2, 0), Version(1, 1, 0)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 4)), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 2, 4), Version(1, 2, 3)), 0)
            self.assertEqual(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)

    def test_compare_prerelease_precedence(self) -> None:
        """Postcondition: prerelease rules rank numeric below alphanumeric and normal releases highest."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            # Normal releases outrank prereleases sharing the same core numbers.
            self.assertGreater(engine.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, ("alpha",))), 0)
            self.assertLess(engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)), 0)
            # Numeric identifiers compare numerically.
            self.assertLess(engine.compare_precedence(Version(1, 0, 0, ("2",)), Version(1, 0, 0, ("10",))), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 0, 0, ("10",)), Version(1, 0, 0, ("2",))), 0)
            # Numeric identifiers rank below alphanumeric identifiers.
            self.assertLess(engine.compare_precedence(Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",))), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("1",))), 0)
            # Alphanumeric identifiers compare in ASCII order.
            self.assertLess(engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("alpha",))), 0)
            # Earlier equal identifiers fall through to the next differing identifier.
            self.assertLess(engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "2"))), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 0, 0, ("alpha", "2")), Version(1, 0, 0, ("alpha", "1"))), 0)
            # A longer identical-prefixed sequence outranks a shorter one.
            self.assertLess(engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1"))), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha",))), 0)
            # Identical prerelease sequences are equal.
            self.assertEqual(engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "1"))), 0)

    def test_compare_ignores_build_metadata(self) -> None:
        """Postcondition: build metadata is excluded from precedence comparison entirely."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.compare_precedence(Version(1, 2, 3, (), ("build",)), Version(1, 2, 3, (), ("other",))), 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:00:46Z
# LAST_CHANGED: 2026-11-05T17:00:46Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: d72dc7fbdad9
# COVERAGE_AUDIT: 2026-11-05T17:00:46Z
# QA_AUDIT: 2026-11-05T17:00:46Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for semver_range_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from semver_solver_multi.lib.semver_core import Version
from semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
    __initialize__,
)


def version(text: str) -> Version:
    core, separator, suffix = text.partition("-")
    major, minor, patch = core.split(".")
    prerelease = tuple(suffix.split(".")) if separator else ()
    return Version(int(major), int(minor), int(patch), prerelease)


def parsed(engine: RangeEngine, text: str) -> VersionRange:
    return engine.parse_range(text)


class SemverRangeImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_trims_surrounding_whitespace(self) -> None:
        """Postcondition: raw_text retains the trimmed range expression."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            result = parsed(engine, "  >= 1.0.0  ")
            self.assertEqual(result.raw_text, ">= 1.0.0")
            self.assertEqual(str(result), ">= 1.0.0")

    def test_parse_accepts_supported_grammar(self) -> None:
        """Postcondition: comparators, prefixes, wildcards, hyphen ranges, and unions parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            accepted = (
                ">=1.0.0",
                ">1.0.0",
                "<=1.0.0",
                "<1.0.0",
                "=1.0.0",
                "==1.0.0",
                "!=1.0.0",
                "1.0.0",
                "^1.2.3",
                "^0.2.3",
                "^0.0.3",
                "~1.2.3",
                "*",
                "x",
                "X",
                "1.x",
                "1.*",
                "1.2.x",
                "1.2.*",
                "1.2.3 - 2.3.4",
                ">=1.0.0 <2.0.0",
                "1.0.0 || 2.0.0",
                ">= 1.0.0",
                "= 1.0.0",
                "^ 1.2.3",
                "~ 1.2.3",
                "1.2.3+build.1",
                "1.2.3-alpha",
                ">=1.2.3-alpha",
                "=1.x",
                "<1.x",
                "<=1.x",
                ">1.x",
                "!=1.x",
                ">=1.x",
            )
            for text in accepted:
                self.assertEqual(parsed(engine, text).raw_text, text)

    def test_parse_rejects_empty_and_commas(self) -> None:
        """Checked precondition: empty input and comma delimiters MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("", "   ", ">=1.0.0, <2.0.0"):
                with self.assertRaises(InvalidRangeError) as caught:
                    parsed(engine, text)
                self.assertEqual(caught.exception.raw_range, text)

    def test_parse_rejects_partial_versions(self) -> None:
        """Checked precondition: bare partial versions without wildcards MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("1", "1.2", "^0.0", "~1.2", "1.2 - 2.3"):
                with self.assertRaises(InvalidRangeError) as caught:
                    parsed(engine, text)
                self.assertEqual(caught.exception.raw_range, text)

    def test_parse_rejects_malformed_syntax(self) -> None:
        """Checked precondition: malformed range syntax MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            malformed = (
                ">=",
                "^",
                "~",
                "abc",
                "1.2.3 -",
                "||",
                "1.0.0 ||",
                "|| 1.0.0",
                "1.0.0 || || 2.0.0",
                "01.x",
                "1.02.x",
                "x.1",
                "1.x.x",
                ">=*",
                "^1.x",
                "~1.x",
            )
            for text in malformed:
                with self.assertRaises(InvalidRangeError) as caught:
                    parsed(engine, text)
                self.assertEqual(caught.exception.raw_range, text)

    def test_satisfies_basic_comparators(self) -> None:
        """Postcondition: basic comparators evaluate candidate versions correctly."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            self.assertTrue(engine.satisfies(version("1.5.0"), parsed(engine, ">=1.0.0"), False))
            self.assertFalse(engine.satisfies(version("0.9.0"), parsed(engine, ">=1.0.0"), False))
            self.assertTrue(engine.satisfies(version("1.0.1"), parsed(engine, ">1.0.0"), False))
            self.assertFalse(engine.satisfies(version("1.0.0"), parsed(engine, ">1.0.0"), False))
            self.assertTrue(engine.satisfies(version("2.0.0"), parsed(engine, "<=2.0.0"), False))
            self.assertFalse(engine.satisfies(version("2.0.1"), parsed(engine, "<=2.0.0"), False))
            self.assertTrue(engine.satisfies(version("1.9.9"), parsed(engine, "<2.0.0"), False))
            self.assertFalse(engine.satisfies(version("2.0.0"), parsed(engine, "<2.0.0"), False))
            self.assertTrue(engine.satisfies(version("1.2.3"), parsed(engine, "==1.2.3"), False))
            self.assertFalse(engine.satisfies(version("1.2.4"), parsed(engine, "==1.2.3"), False))
            self.assertTrue(engine.satisfies(version("1.2.4"), parsed(engine, "!=1.2.3"), False))
            self.assertFalse(engine.satisfies(version("1.2.3"), parsed(engine, "!=1.2.3"), False))
            self.assertTrue(engine.satisfies(version("1.2.3"), parsed(engine, "1.2.3"), False))
            self.assertTrue(engine.satisfies(version("1.2.3"), parsed(engine, "= 1.2.3"), False))

    def test_satisfies_prefix_and_wildcard_ranges(self) -> None:
        """Postcondition: caret, tilde, and wildcard ranges expand into correct boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            self.assertTrue(engine.satisfies(version("1.2.3"), parsed(engine, "^1.2.3"), False))
            self.assertTrue(engine.satisfies(version("1.9.9"), parsed(engine, "^1.2.3"), False))
            self.assertFalse(engine.satisfies(version("2.0.0"), parsed(engine, "^1.2.3"), False))
            self.assertFalse(engine.satisfies(version("1.2.2"), parsed(engine, "^1.2.3"), False))
            self.assertTrue(engine.satisfies(version("0.2.9"), parsed(engine, "^0.2.3"), False))
            self.assertFalse(engine.satisfies(version("0.3.0"), parsed(engine, "^0.2.3"), False))
            self.assertTrue(engine.satisfies(version("0.0.3"), parsed(engine, "^0.0.3"), False))
            self.assertFalse(engine.satisfies(version("0.0.4"), parsed(engine, "^0.0.3"), False))
            self.assertTrue(engine.satisfies(version("1.2.9"), parsed(engine, "~1.2.3"), False))
            self.assertFalse(engine.satisfies(version("1.3.0"), parsed(engine, "~1.2.3"), False))
            self.assertTrue(engine.satisfies(version("1.0.0"), parsed(engine, "1.x"), False))
            self.assertTrue(engine.satisfies(version("1.9.9"), parsed(engine, "1.*"), False))
            self.assertFalse(engine.satisfies(version("2.0.0"), parsed(engine, "1.x"), False))
            self.assertTrue(engine.satisfies(version("1.2.9"), parsed(engine, "1.2.*"), False))
            self.assertFalse(engine.satisfies(version("1.3.0"), parsed(engine, "1.2.x"), False))
            self.assertTrue(engine.satisfies(version("0.0.0"), parsed(engine, "*"), False))
            self.assertTrue(engine.satisfies(version("9.9.9"), parsed(engine, "X"), False))

    def test_satisfies_relational_wildcards(self) -> None:
        """Postcondition: relational comparators applied to wildcards derive the contracted bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            self.assertFalse(engine.satisfies(version("1.0.0"), parsed(engine, "<1.x"), False))
            self.assertTrue(engine.satisfies(version("0.9.0"), parsed(engine, "<1.x"), False))
            self.assertTrue(engine.satisfies(version("1.9.9"), parsed(engine, "<=1.x"), False))
            self.assertFalse(engine.satisfies(version("2.0.0"), parsed(engine, "<=1.x"), False))
            self.assertTrue(engine.satisfies(version("2.0.0"), parsed(engine, ">1.x"), False))
            self.assertFalse(engine.satisfies(version("1.9.9"), parsed(engine, ">1.x"), False))
            self.assertTrue(engine.satisfies(version("1.0.0"), parsed(engine, ">=1.x"), False))
            self.assertFalse(engine.satisfies(version("0.9.0"), parsed(engine, ">=1.x"), False))
            self.assertFalse(engine.satisfies(version("1.5.0"), parsed(engine, "!=1.x"), False))
            self.assertTrue(engine.satisfies(version("0.9.0"), parsed(engine, "!=1.x"), False))
            self.assertTrue(engine.satisfies(version("2.0.0"), parsed(engine, "!=1.x"), False))

    def test_satisfies_hyphen_and_union_ranges(self) -> None:
        """Postcondition: hyphen ranges and union alternatives span the contracted intervals."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            hyphen = parsed(engine, "1.2.3 - 2.3.4")
            self.assertTrue(engine.satisfies(version("1.2.3"), hyphen, False))
            self.assertTrue(engine.satisfies(version("2.3.4"), hyphen, False))
            self.assertFalse(engine.satisfies(version("1.2.2"), hyphen, False))
            self.assertFalse(engine.satisfies(version("2.3.5"), hyphen, False))
            union = parsed(engine, "1.0.0 || 2.0.0")
            self.assertTrue(engine.satisfies(version("1.0.0"), union, False))
            self.assertTrue(engine.satisfies(version("2.0.0"), union, False))
            self.assertFalse(engine.satisfies(version("3.0.0"), union, False))
            bounded = parsed(engine, ">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(version("1.5.0"), bounded, False))
            self.assertFalse(engine.satisfies(version("2.0.0"), bounded, False))

    def test_satisfies_prerelease_rules(self) -> None:
        """Postcondition: prereleases match only when explicitly targeted or when included."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            release_range = parsed(engine, ">=1.0.0")
            self.assertFalse(engine.satisfies(version("1.0.0-alpha"), release_range, False))
            self.assertFalse(engine.satisfies(version("1.0.0-alpha"), release_range, True))
            targeted = parsed(engine, ">=1.0.0-alpha")
            self.assertTrue(engine.satisfies(version("1.0.0-alpha"), targeted, False))
            self.assertTrue(engine.satisfies(version("1.0.0-beta"), targeted, False))
            self.assertFalse(engine.satisfies(version("1.0.1-alpha"), targeted, False))
            self.assertTrue(engine.satisfies(version("1.0.0-alpha"), targeted, True))
            wildcard = parsed(engine, "*")
            self.assertFalse(engine.satisfies(version("1.0.0-alpha"), wildcard, False))
            self.assertTrue(engine.satisfies(version("1.0.0-alpha"), wildcard, True))
            exact = parsed(engine, "1.0.0")
            self.assertFalse(engine.satisfies(version("1.0.0-alpha"), exact, True))
            bounded = parsed(engine, ">=1.0.0-alpha <2.0.0")
            self.assertFalse(engine.satisfies(version("1.5.0-alpha"), bounded, False))
            self.assertTrue(engine.satisfies(version("1.5.0-alpha"), bounded, True))

    def test_satisfies_ignores_build_metadata(self) -> None:
        """Postcondition: build metadata never participates in range matching."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            self.assertTrue(engine.satisfies(version("1.2.3"), parsed(engine, "1.2.3+build.1"), False))
            self.assertTrue(engine.satisfies(version("1.2.4"), parsed(engine, ">=1.2.3+build.1"), False))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:00:46Z
# LAST_CHANGED: 2026-11-05T17:00:46Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 61b44a13cbbe
# COVERAGE_AUDIT: 2026-11-05T17:00:46Z
# QA_AUDIT: 2026-11-05T17:00:46Z
# --- END AUTOFAB METADATA ---
