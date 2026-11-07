from __future__ import annotations

import unittest
from typing import List, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver.lib.semver_solver import (
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
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


class VersionEngineTest(unittest.TestCase):
    """Unit tests for VersionEngine SemVer 2.0.0 parsing, precedence, and range satisfaction."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_standard_and_zero_releases(self) -> None:
        """Verifies POSTCONDITION: parse valid normal SemVer 2.0.0 strings into Version records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            v1 = engine.parse_version("1.2.3")
            self.assertEqual(v1, Version(major=1, minor=2, patch=3, prerelease=(), build=()))
            self.assertFalse(v1.is_prerelease)
            self.assertEqual(v1.format(), "1.2.3")
            self.assertEqual(str(v1), "1.2.3")

            v0 = engine.parse_version("0.0.0")
            self.assertEqual(v0, Version(major=0, minor=0, patch=0, prerelease=(), build=()))
            self.assertFalse(v0.is_prerelease)
            self.assertEqual(v0.format(), "0.0.0")

    def test_parse_version_with_prerelease_and_build_metadata(self) -> None:
        """Verifies POSTCONDITION: parse prerelease and build metadata tuples accurately."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            v_pre = engine.parse_version("1.0.0-alpha.1.01a-bc")
            self.assertEqual(v_pre.major, 1)
            self.assertEqual(v_pre.minor, 0)
            self.assertEqual(v_pre.patch, 0)
            self.assertEqual(v_pre.prerelease, ("alpha", "1", "01a-bc"))
            self.assertEqual(v_pre.build, ())
            self.assertTrue(v_pre.is_prerelease)
            self.assertEqual(v_pre.format(), "1.0.0-alpha.1.01a-bc")

            v_build = engine.parse_version("2.1.4+20130313.01.exp-sha")
            self.assertEqual(v_build.prerelease, ())
            self.assertEqual(v_build.build, ("20130313", "01", "exp-sha"))
            self.assertFalse(v_build.is_prerelease)
            self.assertEqual(v_build.format(), "2.1.4+20130313.01.exp-sha")

            v_both = engine.parse_version("1.0.0-beta.2+exp.sha.5114f85")
            self.assertEqual(v_both.prerelease, ("beta", "2"))
            self.assertEqual(v_both.build, ("exp", "sha", "5114f85"))
            self.assertTrue(v_both.is_prerelease)
            self.assertEqual(v_both.format(), "1.0.0-beta.2+exp.sha.5114f85")
            self.assertEqual(str(v_both), "1.0.0-beta.2+exp.sha.5114f85")

    def test_parse_version_leading_zeroes_raises_invalid_version_error(self) -> None:
        """Verifies PRECONDITION: WHEN text contains leading zeroes in numeric identifiers, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            invalid_Leading_zero_inputs: Tuple[str, ...] = (
                "01.2.3",
                "1.02.3",
                "1.2.03",
                "00.0.0",
                "1.0.0-01",
                "1.0.0-alpha.02",
            )
            for bad_text in invalid_Leading_zero_inputs:
                with self.assertRaises(InvalidVersionError) as ctx:
                    engine.parse_version(bad_text)
                self.assertEqual(ctx.exception.raw_text, bad_text)
                self.assertTrue(bool(ctx.exception.message))

    def test_parse_version_malformed_grammar_raises_invalid_version_error(self) -> None:
        """Verifies PRECONDITION: WHEN text violates SemVer 2.0.0 grammar, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            malformed_inputs: Tuple[str, ...] = (
                "",
                "   ",
                "1.2",
                "1.2.3.4",
                "v1.2.3",
                "-1.0.0",
                "1.2.3-",
                "1.2.3+",
                "1.2.3-alpha..1",
                "1.2.3+build..1",
                "1.2.3-alpha_1",
                "1.2.3+build_1",
                "1.2.3 -alpha",
            )
            for bad_text in malformed_inputs:
                with self.assertRaises(InvalidVersionError) as ctx:
                    engine.parse_version(bad_text)
                self.assertEqual(ctx.exception.raw_text, bad_text)
                self.assertTrue(bool(ctx.exception.message))

    def test_compare_precedence_numeric_and_prerelease_ordering(self) -> None:
        """Verifies POSTCONDITIONS: compare_precedence numeric, prerelease, and build metadata rules."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            # Ordered chain from SemVer 2.0.0 specification
            ordered_texts: Tuple[str, ...] = (
                "0.9.9",
                "1.0.0-0.3.7",
                "1.0.0-alpha",
                "1.0.0-alpha.1",
                "1.0.0-alpha.beta",
                "1.0.0-beta",
                "1.0.0-beta.2",
                "1.0.0-beta.11",
                "1.0.0-rc.1",
                "1.0.0",
                "2.0.0",
                "2.1.0",
                "2.1.1",
                "10.0.0",
            )
            versions: List[Version] = [engine.parse_version(t) for t in ordered_texts]

            for i in range(len(versions)):
                self.assertEqual(engine.compare_precedence(versions[i], versions[i]), 0)
                for j in range(i + 1, len(versions)):
                    self.assertLess(engine.compare_precedence(versions[i], versions[j]), 0)
                    self.assertGreater(engine.compare_precedence(versions[j], versions[i]), 0)

            # Build metadata must be ignored in precedence comparison
            v_build_a = engine.parse_version("1.0.0-alpha.1+build.1")
            v_build_b = engine.parse_version("1.0.0-alpha.1+build.999")
            self.assertEqual(engine.compare_precedence(v_build_a, v_build_b), 0)

            v_norm_a = engine.parse_version("1.2.3+20130313")
            v_norm_b = engine.parse_version("1.2.3+exp.sha.5114f85")
            self.assertEqual(engine.compare_precedence(v_norm_a, v_norm_b), 0)

    def test_parse_range_valid_syntaxes_and_trimming(self) -> None:
        """Verifies POSTCONDITIONS: parse_range supports comparators, prefixes, wildcards, hyphens, unions, and trims whitespace."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            valid_ranges: Tuple[str, ...] = (
                "1.2.3",
                "=1.2.3",
                "==1.2.3",
                "!=1.2.3",
                "<1.2.3",
                "<=1.2.3",
                ">1.2.3",
                ">=1.2.3",
                ">= 1.0.0 < 2.0.0",
                "^1.2.3",
                "^ 0.2.3",
                "^0.0.3",
                "~1.2.3",
                "~ 0.2.3",
                "*",
                "x",
                "X",
                "1.x",
                "1.*",
                "1.X",
                "1.2.x",
                "1.2.*",
                "1.2.X",
                "1.0.0 - 2.0.0",
                ">=1.0.0 <2.0.0 || >=3.0.0 <4.0.0",
            )
            for raw in valid_ranges:
                parsed = engine.parse_range(f"  {raw}  ")
                self.assertIsInstance(parsed, VersionRange)
                self.assertEqual(parsed.raw_text, raw.strip())
                self.assertEqual(str(parsed), parsed.raw_text)

    def test_parse_range_invalid_syntax_raises_invalid_range_error(self) -> None:
        """Verifies PRECONDITIONS: bare partials, empty clauses, commas, or malformed syntax raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            invalid_ranges: Tuple[str, ...] = (
                "",
                "   ",
                "1",
                "1.2",
                "^0.0",
                "^1.2",
                "~1.2",
                ">=1.2",
                "1.2 - 2.3",
                "1.0.0 - 2.3",
                "1.2 - 2.3.0",
                ">=1.0.0, <2.0.0",
                "|| >=1.0.0",
                ">=1.0.0 ||",
                ">=1.0.0 ||   || <2.0.0",
                "~=1.2.3",
                ">>1.0.0",
                "1.0.0 -",
                "- 2.0.0",
                "invalid",
            )
            for bad_range in invalid_ranges:
                with self.assertRaises(InvalidRangeError) as ctx:
                    engine.parse_range(bad_range)
                self.assertEqual(ctx.exception.raw_range, bad_range)
                self.assertTrue(bool(ctx.exception.message))

    def test_satisfies_comparators_caret_tilde_wildcard_hyphen_and_unions(self) -> None:
        """Verifies POSTCONDITION: satisfies evaluates comparator clauses, caret, tilde, wildcard, hyphen, and union ranges."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            # Basic comparators: ==, =, bare exact, !=, <, <=, >, >=
            for eq_expr in ("1.2.3", "=1.2.3", "==1.2.3"):
                r_eq = engine.parse_range(eq_expr)
                self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), r_eq, False))
                self.assertFalse(engine.satisfies(engine.parse_version("1.2.4"), r_eq, False))

            r_ne = engine.parse_range("!=1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.4"), r_ne, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.3"), r_ne, False))

            r_lt = engine.parse_range("<1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.2"), r_lt, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.3"), r_lt, False))

            r_le = engine.parse_range("<=1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), r_le, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.4"), r_le, False))

            r_gt = engine.parse_range(">1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.4"), r_gt, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.3"), r_gt, False))

            r_ge = engine.parse_range(">=1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), r_ge, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.2"), r_ge, False))

            # Caret ranges: ^1.2.3 -> >=1.2.3 <2.0.0, ^0.2.3 -> >=0.2.3 <0.3.0, ^0.0.3 -> >=0.0.3 <0.0.4
            r_caret_major = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), r_caret_major, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.9.0"), r_caret_major, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.2"), r_caret_major, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), r_caret_major, False))

            r_caret_minor = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("0.2.3"), r_caret_minor, False))
            self.assertTrue(engine.satisfies(engine.parse_version("0.2.9"), r_caret_minor, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.2.2"), r_caret_minor, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.3.0"), r_caret_minor, False))

            r_caret_patch = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(engine.parse_version("0.0.3"), r_caret_patch, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.0.2"), r_caret_patch, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.0.4"), r_caret_patch, False))

            # Tilde range: ~1.2.3 -> >=1.2.3 <1.3.0
            r_tilde = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.3"), r_tilde, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.9"), r_tilde, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.2.2"), r_tilde, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.3.0"), r_tilde, False))

            # Wildcards: *, 1.x, 1.2.*
            r_any = engine.parse_range("*")
            self.assertTrue(engine.satisfies(engine.parse_version("0.0.1"), r_any, False))
            self.assertTrue(engine.satisfies(engine.parse_version("5.4.3"), r_any, False))

            r_wild_major = engine.parse_range("1.x")
            self.assertTrue(engine.satisfies(engine.parse_version("1.0.0"), r_wild_major, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.9.9"), r_wild_major, False))
            self.assertFalse(engine.satisfies(engine.parse_version("0.9.9"), r_wild_major, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), r_wild_major, False))

            r_wild_minor = engine.parse_range("1.2.*")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.0"), r_wild_minor, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.7"), r_wild_minor, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.1.9"), r_wild_minor, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.3.0"), r_wild_minor, False))

            # Hyphen range and union with != and > comparators
            r_union = engine.parse_range("1.2.0 - 1.4.0 != 1.3.0 || > 2.0.0 <= 2.1.0")
            self.assertTrue(engine.satisfies(engine.parse_version("1.2.0"), r_union, False))
            self.assertTrue(engine.satisfies(engine.parse_version("1.4.0"), r_union, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.3.0"), r_union, False))
            self.assertFalse(engine.satisfies(engine.parse_version("1.5.0"), r_union, False))
            self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), r_union, False))
            self.assertTrue(engine.satisfies(engine.parse_version("2.0.5"), r_union, False))

    def test_satisfies_prerelease_filtering_and_inclusion_semantics(self) -> None:
        """Verifies POSTCONDITIONS: prerelease matching when include_prerelease is False vs True."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            v_pre_100 = engine.parse_version("1.0.0-alpha.1")
            v_pre_123_a1 = engine.parse_version("1.2.3-alpha.1")
            v_pre_123_a2 = engine.parse_version("1.2.3-alpha.2")
            v_pre_124_a1 = engine.parse_version("1.2.4-alpha.1")

            r_ge_100 = engine.parse_range(">=1.0.0 <2.0.0")
            # include_prerelease=False rejects prereleases when range has no prerelease on that M.m.p
            self.assertFalse(engine.satisfies(v_pre_123_a2, r_ge_100, False))

            # include_prerelease=True evaluates directly using SemVer precedence
            # 1.0.0-alpha.1 < 1.0.0, so it does NOT satisfy >=1.0.0 even when include_prerelease=True
            self.assertFalse(engine.satisfies(v_pre_100, r_ge_100, True))
            # 1.2.3-alpha.2 is >= 1.0.0 and < 2.0.0
            self.assertTrue(engine.satisfies(v_pre_123_a2, r_ge_100, True))

            # Explicit prerelease in range allows matching prerelease with same M.m.p when include_prerelease=False
            r_explicit_pre = engine.parse_range(">=1.2.3-alpha.1 <2.0.0")
            self.assertTrue(engine.satisfies(v_pre_123_a1, r_explicit_pre, False))
            self.assertTrue(engine.satisfies(v_pre_123_a2, r_explicit_pre, False))
            # Different M.m.p prerelease is still rejected when include_prerelease=False
            self.assertFalse(engine.satisfies(v_pre_124_a1, r_explicit_pre, False))
            # Allowed when include_prerelease=True
            self.assertTrue(engine.satisfies(v_pre_124_a1, r_explicit_pre, True))


class PackageRepositoryTest(unittest.TestCase):
    """Unit tests for PackageRepository registration, sorting, and lookup contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_register_and_query_packages_sorted_descending(self) -> None:
        """Verifies POSTCONDITIONS: register_package, has_package, all_packages, and descending get_releases."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repo = scope.get_singleton(PackageRepository)

            self.assertFalse(repo.has_package("http"))
            self.assertEqual(repo.all_packages(), set())

            rel_100 = PackageRelease(name="http", version=engine.parse_version("1.0.0"))
            rel_200 = PackageRelease(name="http", version=engine.parse_version("2.0.0"))
            rel_150_pre = PackageRelease(name="http", version=engine.parse_version("1.5.0-alpha.1"))
            rel_150 = PackageRelease(name="http", version=engine.parse_version("1.5.0"))
            rel_other = PackageRelease(name="json", version=engine.parse_version("0.1.0"))

            repo.register_package(rel_100)
            repo.register_package(rel_200)
            repo.register_package(rel_150_pre)
            repo.register_package(rel_150)
            repo.register_package(rel_other)

            self.assertTrue(repo.has_package("http"))
            self.assertTrue(repo.has_package("json"))
            self.assertFalse(repo.has_package("missing"))
            self.assertEqual(repo.all_packages(), {"http", "json"})

            releases = repo.get_releases("http")
            self.assertEqual(releases, [rel_200, rel_150, rel_150_pre, rel_100])

            # Mutating the returned list must not alter internal repository storage
            releases.pop()
            self.assertEqual(len(repo.get_releases("http")), 4)

    def test_get_releases_unregistered_package_raises_package_not_found_error(self) -> None:
        """Verifies PRECONDITION: WHEN name is not registered, get_releases MUST raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repo = scope.get_singleton(PackageRepository)

            with self.assertRaises(PackageNotFoundError) as ctx:
                repo.get_releases("unknown_pkg")
            self.assertEqual(ctx.exception.package_name, "unknown_pkg")
            self.assertTrue(bool(ctx.exception.message))


class DependencySolverTest(unittest.TestCase):
    """Unit tests for DependencySolver backtracking resolution, MRV ordering, and conflict reporting."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_resolve_empty_and_transitive_happy_path_selects_highest_precedence(self) -> None:
        """Verifies POSTCONDITIONS: resolve selects highest compatible versions across root and transitive dependencies."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repo = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            empty_outcome = solver.resolve([])
            self.assertIsInstance(empty_outcome, ResolutionOutcome)
            self.assertEqual(dict(empty_outcome.selected_versions), {})
            self.assertEqual(empty_outcome.derivation_steps, ())

            # Register packages: web -> router ^1.0.0 -> util >=1.0.0 <2.0.0
            repo.register_package(PackageRelease("util", engine.parse_version("1.0.0")))
            repo.register_package(PackageRelease("util", engine.parse_version("1.4.2")))
            repo.register_package(PackageRelease("util", engine.parse_version("2.0.0")))

            repo.register_package(
                PackageRelease(
                    "router",
                    engine.parse_version("1.2.0"),
                    (PackageDependency("util", engine.parse_range("^1.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    "web",
                    engine.parse_version("1.0.0"),
                    (PackageDependency("router", engine.parse_range("^1.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    "web",
                    engine.parse_version("1.1.0"),
                    (PackageDependency("router", engine.parse_range("^1.0.0")),),
                )
            )

            outcome = solver.resolve([PackageDependency("web", engine.parse_range("^1.0.0"))])
            self.assertEqual(
                dict(outcome.selected_versions),
                {
                    "web": engine.parse_version("1.1.0"),
                    "router": engine.parse_version("1.2.0"),
                    "util": engine.parse_version("1.4.2"),
                },
            )
            self.assertEqual(len(outcome.derivation_steps), 3)

    def test_resolve_backtracks_on_unassigned_and_already_assigned_conflicts(self) -> None:
        """Verifies POSTCONDITIONS: solver backtracks when highest candidate conflicts with unassigned or assigned packages."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repo = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            # Case 1: core has 1 release (1.0.0), plugin has 2 releases (2.0.0 requiring core >=2.0.0, 1.0.0 requiring core ^1.0.0).
            # MRV assigns core=1.0.0 first, then plugin 2.0.0 conflicts against already-assigned core=1.0.0 and backtracks to plugin=1.0.0.
            repo.register_package(PackageRelease("core", engine.parse_version("1.0.0")))
            repo.register_package(
                PackageRelease(
                    "plugin",
                    engine.parse_version("2.0.0"),
                    (PackageDependency("core", engine.parse_range(">=2.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    "plugin",
                    engine.parse_version("1.0.0"),
                    (PackageDependency("core", engine.parse_range("^1.0.0")),),
                )
            )

            outcome1 = solver.resolve(
                [
                    PackageDependency("core", engine.parse_range(">=1.0.0")),
                    PackageDependency("plugin", engine.parse_range(">=1.0.0")),
                ]
            )
            self.assertEqual(
                dict(outcome1.selected_versions),
                {
                    "core": engine.parse_version("1.0.0"),
                    "plugin": engine.parse_version("1.0.0"),
                },
            )

            # Case 2: app (2 releases) and codec (3 releases). MRV assigns app=2.0.0 first, adding constraint codec >=3.0.0.
            # Unassigned codec has 0 viable releases for >=3.0.0, triggering backtrack to app=1.0.0 which requires codec ^1.0.0.
            repo.register_package(PackageRelease("codec", engine.parse_version("2.0.0")))
            repo.register_package(PackageRelease("codec", engine.parse_version("1.5.0")))
            repo.register_package(PackageRelease("codec", engine.parse_version("1.0.0")))
            repo.register_package(
                PackageRelease(
                    "app",
                    engine.parse_version("2.0.0"),
                    (PackageDependency("codec", engine.parse_range(">=3.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    "app",
                    engine.parse_version("1.0.0"),
                    (PackageDependency("codec", engine.parse_range("^1.0.0")),),
                )
            )

            outcome2 = solver.resolve(
                [
                    PackageDependency("app", engine.parse_range(">=1.0.0")),
                    PackageDependency("codec", engine.parse_range(">=1.0.0")),
                ]
            )
            self.assertEqual(
                dict(outcome2.selected_versions),
                {
                    "app": engine.parse_version("1.0.0"),
                    "codec": engine.parse_version("1.5.0"),
                },
            )

    def test_resolve_unregistered_package_raises_resolution_conflict_error(self) -> None:
        """Verifies PRECONDITION: unregistered package raises ResolutionConflictError without leaking PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            solver = scope.get_singleton(DependencySolver)

            with self.assertRaises(ResolutionConflictError) as ctx:
                solver.resolve([PackageDependency("nonexistent_pkg", engine.parse_range("^1.0.0"))])
            self.assertIn("nonexistent_pkg", ctx.exception.conflicting_packages)
            self.assertTrue(bool(ctx.exception.explanation))
            self.assertTrue(bool(ctx.exception.message))

    def test_resolve_unsatisfiable_constraints_raises_resolution_conflict_error(self) -> None:
        """Verifies PRECONDITION: WHEN dependencies are mutually unsatisfiable, MUST raise ResolutionConflictError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            repo = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            repo.register_package(PackageRelease("shared", engine.parse_version("1.0.0")))
            repo.register_package(PackageRelease("shared", engine.parse_version("2.0.0")))
            repo.register_package(
                PackageRelease(
                    "left",
                    engine.parse_version("1.0.0"),
                    (PackageDependency("shared", engine.parse_range("^1.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    "right",
                    engine.parse_version("1.0.0"),
                    (PackageDependency("shared", engine.parse_range("^2.0.0")),),
                )
            )

            with self.assertRaises(ResolutionConflictError) as ctx:
                solver.resolve(
                    [
                        PackageDependency("left", engine.parse_range("^1.0.0")),
                        PackageDependency("right", engine.parse_range("^1.0.0")),
                    ]
                )
            self.assertIn("shared", ctx.exception.conflicting_packages)
            self.assertTrue(bool(ctx.exception.explanation))
            self.assertTrue(bool(ctx.exception.message))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T21:05:03Z
# LAST_CHANGED: 2026-11-06T20:29:49Z
# CHANGE: Exercise VersionEngine.satisfies against equality (==, =, exact version) and strictly greater-than (>) comparators
# COVERAGE_AUDIT: 2026-11-06T21:05:03Z
# QA_AUDIT: 2026-11-06T21:04:28Z
# --- END AUTOFAB METADATA ---
