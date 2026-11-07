# === File: dependency_solver_impl_test.py ===
from __future__ import annotations

import sys
import unittest
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


def _unify_package_aliases() -> None:
    lib_prefix = "benchmark_2.parts.semver_solver_multi"
    short_prefix = "semver_solver_multi"
    for suffix in (
        "",
        ".lib",
        ".lib.semver_core",
        ".lib.semver_core_impl",
        ".lib.semver_range",
        ".lib.semver_range_impl",
        ".lib.dependency_solver",
        ".lib.dependency_solver_impl",
    ):
        full_key = f"{lib_prefix}{suffix}"
        short_key = f"{short_prefix}{suffix}"
        if full_key in sys.modules:
            sys.modules[short_key] = sys.modules[full_key]
        elif short_key in sys.modules:
            sys.modules[full_key] = sys.modules[short_key]


_unify_package_aliases()
from semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
    VersionEngine,
)

_unify_package_aliases()
from semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)

_unify_package_aliases()
from semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
)

_unify_package_aliases()
from semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)

_unify_package_aliases()


class MockVersionEngine(VersionEngine):
    """Lightweight protocol test double implementing semver_core.VersionEngine."""

    def parse_version(self, text: str) -> Version:
        parts = text.strip().split("-", 1)
        nums = parts[0].split(".")
        if len(nums) != 3 or not all(n.isdigit() for n in nums):
            raise InvalidVersionError(message=f"Invalid version: {text}", raw_text=text)
        prerelease: Tuple[str, ...] = tuple(parts[1].split(".")) if len(parts) > 1 else ()
        return Version(
            major=int(nums[0]),
            minor=int(nums[1]),
            patch=int(nums[2]),
            prerelease=prerelease,
        )

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
            return -1 if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch) else 1
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease and v2.prerelease:
            return 1
        if v1.prerelease and not v2.prerelease:
            return -1
        for s1, s2 in zip(v1.prerelease, v2.prerelease):
            if s1 == s2:
                continue
            if s1.isdigit() and s2.isdigit():
                return -1 if int(s1) < int(s2) else 1
            if s1.isdigit():
                return -1
            if s2.isdigit():
                return 1
            return -1 if s1 < s2 else 1
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        return 0


class MockRangeEngine(RangeEngine):
    """Lightweight protocol test double implementing semver_range.RangeEngine."""

    def __init__(self, version_engine: MockVersionEngine) -> None:
        self.version_engine = version_engine

    def parse_range(self, text: str) -> VersionRange:
        trimmed = text.strip()
        if not trimmed:
            raise InvalidRangeError(message="Empty range", raw_range=text)
        return VersionRange(raw_text=trimmed)

    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        if version.prerelease and not include_prerelease:
            return False
        tokens = range_constraint.raw_text.strip().split()
        for token in tokens:
            if token == "*":
                continue
            if token.startswith(">="):
                target = self.version_engine.parse_version(token[2:])
                if self.version_engine.compare_precedence(version, target) < 0:
                    return False
            elif token.startswith("<="):
                target = self.version_engine.parse_version(token[2:])
                if self.version_engine.compare_precedence(version, target) > 0:
                    return False
            elif token.startswith("!="):
                target = self.version_engine.parse_version(token[2:])
                if self.version_engine.compare_precedence(version, target) == 0:
                    return False
            elif token.startswith("=="):
                target = self.version_engine.parse_version(token[2:])
                if self.version_engine.compare_precedence(version, target) != 0:
                    return False
            elif token.startswith(">"):
                target = self.version_engine.parse_version(token[1:])
                if self.version_engine.compare_precedence(version, target) <= 0:
                    return False
            elif token.startswith("<"):
                target = self.version_engine.parse_version(token[1:])
                if self.version_engine.compare_precedence(version, target) >= 0:
                    return False
            elif token.startswith("="):
                target = self.version_engine.parse_version(token[1:])
                if self.version_engine.compare_precedence(version, target) != 0:
                    return False
            else:
                target = self.version_engine.parse_version(token)
                if self.version_engine.compare_precedence(version, target) != 0:
                    return False
        return True


class PackageRepositoryTest(unittest.TestCase):
    """Unit tests for dependency_solver_impl.PackageRepository."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.range_engine = MockRangeEngine(self.version_engine)
        self.registry.register_instance(
            self.version_engine,
            keys=[VersionEngine],
            tier=system,
        )
        self.registry.register_instance(
            self.range_engine,
            keys=[RangeEngine],
            tier=system,
        )

    def test_register_and_query_packages_sorted_descending(self) -> None:
        """POSTCONDITIONS: MUST register releases, track package existence, and return releases sorted by precedence descending."""
        with enter_phase(system, registry=self.registry) as scope:
            repo = scope.get_singleton(PackageRepository)

            self.assertFalse(repo.has_package("alpha"))
            self.assertEqual(repo.all_packages(), set())

            rel_1_0 = PackageRelease(name="alpha", version=Version(1, 0, 0))
            rel_2_1 = PackageRelease(name="alpha", version=Version(2, 1, 0))
            rel_1_5_pre = PackageRelease(name="alpha", version=Version(1, 5, 0, prerelease=("rc", "1")))
            rel_1_5 = PackageRelease(name="alpha", version=Version(1, 5, 0))
            rel_beta = PackageRelease(name="beta", version=Version(0, 1, 0))

            repo.register_package(rel_1_0)
            repo.register_package(rel_2_1)
            repo.register_package(rel_1_5_pre)
            repo.register_package(rel_1_5)
            repo.register_package(rel_beta)

            self.assertTrue(repo.has_package("alpha"))
            self.assertTrue(repo.has_package("beta"))
            self.assertFalse(repo.has_package("gamma"))
            self.assertEqual(repo.all_packages(), {"alpha", "beta"})

            releases = repo.get_releases("alpha")
            self.assertEqual(releases, [rel_2_1, rel_1_5, rel_1_5_pre, rel_1_0])

            # Verify get_releases returns a defensive copy
            releases.pop()
            self.assertEqual(len(repo.get_releases("alpha")), 4)

    def test_get_releases_unregistered_package_raises_error(self) -> None:
        """PRECONDITIONS: WHEN name is not registered, MUST raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repo = scope.get_singleton(PackageRepository)

            with self.assertRaises(PackageNotFoundError) as ctx:
                repo.get_releases("missing-pkg")
            self.assertEqual(ctx.exception.package_name, "missing-pkg")
            self.assertTrue(len(ctx.exception.message) > 0)


class DependencySolverTest(unittest.TestCase):
    """Unit tests for dependency_solver_impl.DependencySolver."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.range_engine = MockRangeEngine(self.version_engine)
        self.registry.register_instance(
            self.version_engine,
            keys=[VersionEngine],
            tier=system,
        )
        self.registry.register_instance(
            self.range_engine,
            keys=[RangeEngine],
            tier=system,
        )

    def test_resolve_empty_dependencies(self) -> None:
        """POSTCONDITIONS: MUST return empty ResolutionOutcome when root_dependencies is empty."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([])
            self.assertEqual(outcome, ResolutionOutcome(selected_versions={}, derivation_steps=()))

    def test_resolve_compatible_transitive_dependencies_highest_precedence(self) -> None:
        """POSTCONDITIONS: MUST compute mutually compatible assignment selecting highest precedence release for each package."""
        with enter_phase(system, registry=self.registry) as scope:
            repo = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            repo.register_package(
                PackageRelease(
                    name="app",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency("lib", VersionRange(">=1.0.0 <2.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    name="app",
                    version=Version(2, 0, 0),
                    dependencies=(
                        PackageDependency("lib", VersionRange(">=1.0.0 <2.0.0")),
                        PackageDependency("util", VersionRange(">=1.0.0")),
                    ),
                )
            )
            repo.register_package(PackageRelease(name="lib", version=Version(1, 0, 0)))
            repo.register_package(
                PackageRelease(
                    name="lib",
                    version=Version(1, 2, 0),
                    dependencies=(PackageDependency("util", VersionRange(">=1.0.0 <2.0.0")),),
                )
            )
            repo.register_package(PackageRelease(name="lib", version=Version(2, 0, 0)))
            repo.register_package(PackageRelease(name="util", version=Version(1, 0, 0)))
            repo.register_package(PackageRelease(name="util", version=Version(1, 5, 0)))
            repo.register_package(PackageRelease(name="util", version=Version(2, 0, 0)))

            outcome = solver.resolve([PackageDependency("app", VersionRange(">=1.0.0"))])
            self.assertEqual(
                dict(outcome.selected_versions),
                {
                    "app": Version(2, 0, 0),
                    "lib": Version(1, 2, 0),
                    "util": Version(1, 5, 0),
                },
            )
            self.assertTrue(len(outcome.derivation_steps) >= 3)

    def test_resolve_backtracks_on_assigned_and_transitive_conflicts(self) -> None:
        """POSTCONDITIONS: MUST backtrack across both forward-check conflicts on assigned packages and dead-end transitive branches."""
        with enter_phase(system, registry=self.registry) as scope:
            repo = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            # Part 1: Forward-check conflict against already assigned package 'a'
            # 'a' has 1 release (1.0.0), so MRV picks 'a' before 'b' (which has 2 releases: 2.0.0 and 1.0.0).
            # 'b' 2.0.0 requires 'a >=2.0.0' (conflicts with assigned a=1.0.0), backtracking to 'b' 1.0.0.
            repo.register_package(PackageRelease(name="a", version=Version(1, 0, 0)))
            repo.register_package(
                PackageRelease(
                    name="b",
                    version=Version(2, 0, 0),
                    dependencies=(PackageDependency("a", VersionRange(">=2.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    name="b",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency("a", VersionRange(">=1.0.0")),),
                )
            )

            outcome1 = solver.resolve(
                [
                    PackageDependency("a", VersionRange(">=1.0.0")),
                    PackageDependency("b", VersionRange(">=1.0.0")),
                ]
            )
            self.assertEqual(
                dict(outcome1.selected_versions),
                {"a": Version(1, 0, 0), "b": Version(1, 0, 0)},
            )

            # Part 2: Deep backtracking when unassigned transitive dependency has 0 viable releases
            # 'web' 2.0.0 requires 'auth >=2.0.0' and 'db <2.0.0'
            # 'web' 1.0.0 requires 'auth >=1.0.0 <2.0.0'
            # 'auth' 2.0.0 requires 'db >=2.0.0' (causes 'db' to have 0 viable releases!)
            # 'auth' 1.0.0 requires 'db >=1.0.0 <2.0.0'
            # 'db' has 1.0.0 and 2.0.0
            repo.register_package(
                PackageRelease(
                    name="web",
                    version=Version(2, 0, 0),
                    dependencies=(
                        PackageDependency("auth", VersionRange(">=2.0.0")),
                        PackageDependency("db", VersionRange(">=1.0.0 <2.0.0")),
                    ),
                )
            )
            repo.register_package(
                PackageRelease(
                    name="web",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency("auth", VersionRange(">=1.0.0 <2.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    name="auth",
                    version=Version(2, 0, 0),
                    dependencies=(PackageDependency("db", VersionRange(">=2.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    name="auth",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency("db", VersionRange(">=1.0.0 <2.0.0")),),
                )
            )
            repo.register_package(PackageRelease(name="db", version=Version(1, 0, 0)))
            repo.register_package(PackageRelease(name="db", version=Version(2, 0, 0)))

            outcome2 = solver.resolve([PackageDependency("web", VersionRange(">=1.0.0"))])
            self.assertEqual(
                dict(outcome2.selected_versions),
                {
                    "web": Version(1, 0, 0),
                    "auth": Version(1, 0, 0),
                    "db": Version(1, 0, 0),
                },
            )

    def test_resolve_missing_package_raises_resolution_conflict_error(self) -> None:
        """PRECONDITIONS: WHEN a dependency references a package absent from the repository, MUST raise ResolutionConflictError without allowing PackageNotFoundError to escape."""
        with enter_phase(system, registry=self.registry) as scope:
            repo = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            # Missing root package
            with self.assertRaises(ResolutionConflictError) as ctx_root:
                solver.resolve([PackageDependency("nonexistent", VersionRange(">=1.0.0"))])
            self.assertIn("nonexistent", ctx_root.exception.conflicting_packages)
            self.assertTrue(len(ctx_root.exception.explanation) > 0)
            self.assertTrue(len(ctx_root.exception.message) > 0)

            # Missing transitive package
            repo.register_package(
                PackageRelease(
                    name="service",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency("ghost-dep", VersionRange(">=1.0.0")),),
                )
            )
            with self.assertRaises(ResolutionConflictError) as ctx_trans:
                solver.resolve([PackageDependency("service", VersionRange(">=1.0.0"))])
            self.assertIn("ghost-dep", ctx_trans.exception.conflicting_packages)
            self.assertIn("service", ctx_trans.exception.conflicting_packages)
            self.assertTrue(len(ctx_trans.exception.explanation) > 0)

    def test_resolve_unsatisfiable_constraints_raises_resolution_conflict_error(self) -> None:
        """PRECONDITIONS: WHEN dependency constraints are unsatisfiable, MUST raise ResolutionConflictError identifying conflicting packages."""
        with enter_phase(system, registry=self.registry) as scope:
            repo = scope.get_singleton(PackageRepository)
            solver = scope.get_singleton(DependencySolver)

            repo.register_package(
                PackageRelease(
                    name="left",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency("shared", VersionRange(">=2.0.0")),),
                )
            )
            repo.register_package(
                PackageRelease(
                    name="right",
                    version=Version(1, 0, 0),
                    dependencies=(PackageDependency("shared", VersionRange("<2.0.0")),),
                )
            )
            repo.register_package(PackageRelease(name="shared", version=Version(1, 0, 0)))
            repo.register_package(PackageRelease(name="shared", version=Version(2, 0, 0)))

            with self.assertRaises(ResolutionConflictError) as ctx:
                solver.resolve(
                    [
                        PackageDependency("left", VersionRange(">=1.0.0")),
                        PackageDependency("right", VersionRange(">=1.0.0")),
                    ]
                )
            self.assertIn("shared", ctx.exception.conflicting_packages)
            self.assertTrue(len(ctx.exception.explanation) > 0)
            self.assertTrue(len(ctx.exception.message) > 0)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:56Z
# LAST_CHANGED: 2026-11-06T20:39:44Z
# CHANGE: Order imports topologically and synchronize sys.modules package aliases between semver_solver_multi.lib and benchmark_2.parts.semver_solver_multi.lib so collaborator protocols, exceptions, and data types share canonical class identities
# COVERAGE_AUDIT: 2026-11-06T20:44:56Z
# QA_AUDIT: 2026-11-06T20:44:16Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
from __future__ import annotations

import sys
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


def _unify_package_aliases() -> None:
    lib_prefix = "benchmark_2.parts.semver_solver_multi"
    short_prefix = "semver_solver_multi"
    for suffix in (
        "",
        ".lib",
        ".lib.semver_core",
        ".lib.semver_core_impl",
        ".lib.semver_range",
        ".lib.semver_range_impl",
        ".lib.dependency_solver",
        ".lib.dependency_solver_impl",
    ):
        full_key = f"{lib_prefix}{suffix}"
        short_key = f"{short_prefix}{suffix}"
        if full_key in sys.modules:
            sys.modules[short_key] = sys.modules[full_key]
        elif short_key in sys.modules:
            sys.modules[full_key] = sys.modules[short_key]


_unify_package_aliases()
from semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
)

_unify_package_aliases()
from semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
    __initialize__,
)

_unify_package_aliases()


class VersionEngineTest(unittest.TestCase):
    """Unit tests for semver_core_impl.VersionEngine against semver_core.pyi and semver_core_impl.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_normal_versions(self) -> None:
        """POSTCONDITIONS: MUST parse valid SemVer 2.0.0 strings into Version records."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            v1 = engine.parse_version("1.2.3")
            self.assertEqual(v1, Version(major=1, minor=2, patch=3, prerelease=(), build=()))

            v0 = engine.parse_version("0.0.0")
            self.assertEqual(v0, Version(major=0, minor=0, patch=0, prerelease=(), build=()))

            v_large = engine.parse_version("10.200.3000")
            self.assertEqual(v_large, Version(major=10, minor=200, patch=3000, prerelease=(), build=()))

    def test_parse_version_with_prerelease_and_build_metadata(self) -> None:
        """POSTCONDITIONS: MUST parse valid SemVer 2.0.0 strings with prerelease and build tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            v_pre = engine.parse_version("1.0.0-alpha.1")
            self.assertEqual(
                v_pre,
                Version(major=1, minor=0, patch=0, prerelease=("alpha", "1"), build=()),
            )

            v_pre_alnum = engine.parse_version("1.0.0-0a.x-7-z.0")
            self.assertEqual(
                v_pre_alnum,
                Version(major=1, minor=0, patch=0, prerelease=("0a", "x-7-z", "0"), build=()),
            )

            v_build = engine.parse_version("1.0.0+20130313144700.01")
            self.assertEqual(
                v_build,
                Version(major=1, minor=0, patch=0, prerelease=(), build=("20130313144700", "01")),
            )

            v_both = engine.parse_version("2.1.0-beta.2+exp.sha.5114f85")
            self.assertEqual(
                v_both,
                Version(
                    major=2,
                    minor=1,
                    patch=0,
                    prerelease=("beta", "2"),
                    build=("exp", "sha", "5114f85"),
                ),
            )

    def test_parse_version_invalid_leading_zeroes_raises_error(self) -> None:
        """PRECONDITIONS: WHEN text contains leading zeroes in numeric identifiers, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            invalid_inputs = [
                "01.2.3",
                "1.02.3",
                "1.2.03",
                "00.0.0",
                "1.0.0-01",
                "1.0.0-alpha.01",
            ]
            for raw in invalid_inputs:
                with self.assertRaises(InvalidVersionError) as ctx:
                    engine.parse_version(raw)
                self.assertEqual(ctx.exception.raw_text, raw)
                self.assertTrue(len(ctx.exception.message) > 0)

    def test_parse_version_grammar_violations_raise_error(self) -> None:
        """PRECONDITIONS: WHEN text violates SemVer 2.0.0 grammar, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            invalid_inputs = [
                "",
                "1",
                "1.2",
                "1.2.3.4",
                "v1.2.3",
                "a.b.c",
                "-1.0.0",
                "1.0.0-",
                "1.0.0-alpha.",
                "1.0.0-.alpha",
                "1.0.0-alpha..1",
                "1.0.0-alpha_1",
                "1.0.0+",
                "1.0.0+build.",
                "1.0.0+.build",
                "1.0.0+build..1",
                "1.0.0+build_1",
                " 1.2.3 ",
            ]
            for raw in invalid_inputs:
                with self.assertRaises(InvalidVersionError) as ctx:
                    engine.parse_version(raw)
                self.assertEqual(ctx.exception.raw_text, raw)
                self.assertTrue(len(ctx.exception.message) > 0)

    def test_compare_precedence_major_minor_patch(self) -> None:
        """POSTCONDITIONS: MUST compare major, minor, and patch numerically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            self.assertLess(engine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(2, 0, 0), Version(1, 0, 0)), 0)

            self.assertLess(engine.compare_precedence(Version(1, 1, 0), Version(1, 2, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 10, 0), Version(1, 2, 0)), 0)

            self.assertLess(engine.compare_precedence(Version(1, 1, 1), Version(1, 1, 2)), 0)
            self.assertGreater(engine.compare_precedence(Version(1, 1, 10), Version(1, 1, 2)), 0)

            self.assertEqual(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)

    def test_compare_precedence_normal_vs_prerelease(self) -> None:
        """POSTCONDITIONS: MUST rank normal versions higher than prerelease versions sharing identical major, minor, and patch."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            v_pre = Version(1, 0, 0, prerelease=("alpha",))
            v_norm = Version(1, 0, 0)
            self.assertLess(engine.compare_precedence(v_pre, v_norm), 0)
            self.assertGreater(engine.compare_precedence(v_norm, v_pre), 0)

    def test_compare_precedence_prerelease_segments(self) -> None:
        """POSTCONDITIONS: MUST compare prerelease segments numerically, ASCII-lexicographically, numeric below string, and shorter below longer."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            # Numeric vs numeric compared as integers
            v_num2 = Version(1, 0, 0, prerelease=("beta", "2"))
            v_num11 = Version(1, 0, 0, prerelease=("beta", "11"))
            self.assertLess(engine.compare_precedence(v_num2, v_num11), 0)
            self.assertGreater(engine.compare_precedence(v_num11, v_num2), 0)

            # String vs string compared ASCII-lexicographically
            v_alpha = Version(1, 0, 0, prerelease=("alpha",))
            v_beta = Version(1, 0, 0, prerelease=("beta",))
            self.assertLess(engine.compare_precedence(v_alpha, v_beta), 0)
            self.assertGreater(engine.compare_precedence(v_beta, v_alpha), 0)

            # Numeric ranks below string
            v_num = Version(1, 0, 0, prerelease=("alpha", "1"))
            v_str = Version(1, 0, 0, prerelease=("alpha", "beta"))
            self.assertLess(engine.compare_precedence(v_num, v_str), 0)
            self.assertGreater(engine.compare_precedence(v_str, v_num), 0)

            # Shorter prefix ranks below longer sequence
            v_short = Version(1, 0, 0, prerelease=("alpha",))
            v_long = Version(1, 0, 0, prerelease=("alpha", "1"))
            self.assertLess(engine.compare_precedence(v_short, v_long), 0)
            self.assertGreater(engine.compare_precedence(v_long, v_short), 0)

            # Equal prerelease
            self.assertEqual(engine.compare_precedence(v_long, Version(1, 0, 0, prerelease=("alpha", "1"))), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: MUST ignore build metadata entirely when comparing precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)

            v_b1 = Version(1, 0, 0, prerelease=("alpha",), build=("001",))
            v_b2 = Version(1, 0, 0, prerelease=("alpha",), build=("999", "exp"))
            v_no_b = Version(1, 0, 0, prerelease=("alpha",), build=())

            self.assertEqual(engine.compare_precedence(v_b1, v_b2), 0)
            self.assertEqual(engine.compare_precedence(v_b1, v_no_b), 0)
            self.assertEqual(
                engine.compare_precedence(Version(1, 0, 0, build=("a",)), Version(1, 0, 0, build=("b",))),
                0,
            )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:59Z
# LAST_CHANGED: 2026-11-06T20:39:38Z
# CHANGE: Synchronize sys.modules package aliases between semver_solver_multi.lib and benchmark_2.parts.semver_solver_multi.lib before and after imports so Version and InvalidVersionError share canonical class identities
# COVERAGE_AUDIT: 2026-11-06T20:44:59Z
# QA_AUDIT: 2026-11-06T20:44:18Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
from __future__ import annotations

import re
import sys
import unittest
from typing import Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


def _unify_package_aliases() -> None:
    lib_prefix = "benchmark_2.parts.semver_solver_multi"
    short_prefix = "semver_solver_multi"
    for suffix in (
        "",
        ".lib",
        ".lib.semver_core",
        ".lib.semver_core_impl",
        ".lib.semver_range",
        ".lib.semver_range_impl",
        ".lib.dependency_solver",
        ".lib.dependency_solver_impl",
    ):
        full_key = f"{lib_prefix}{suffix}"
        short_key = f"{short_prefix}{suffix}"
        if full_key in sys.modules:
            sys.modules[short_key] = sys.modules[full_key]
        elif short_key in sys.modules:
            sys.modules[full_key] = sys.modules[short_key]


_unify_package_aliases()
from semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
    VersionEngine,
)

_unify_package_aliases()
from semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    VersionRange,
)

_unify_package_aliases()
from semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
    __initialize__,
)

_unify_package_aliases()

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


class MockVersionEngine(VersionEngine):
    """Lightweight protocol test double implementing semver_core.VersionEngine."""

    def parse_version(self, text: str) -> Version:
        match = _SEMVER_RE.match(text)
        if not match:
            raise InvalidVersionError(message=f"Invalid version: {text}", raw_text=text)
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        prerelease: Tuple[str, ...] = tuple(match.group(4).split(".")) if match.group(4) else ()
        build: Tuple[str, ...] = tuple(match.group(5).split(".")) if match.group(5) else ()
        return Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
            build=build,
        )

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
            return -1 if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch) else 1
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease and v2.prerelease:
            return 1
        if v1.prerelease and not v2.prerelease:
            return -1
        for s1, s2 in zip(v1.prerelease, v2.prerelease):
            if s1 == s2:
                continue
            n1 = s1.isdigit()
            n2 = s2.isdigit()
            if n1 and n2:
                return -1 if int(s1) < int(s2) else 1
            if n1 and not n2:
                return -1
            if not n1 and n2:
                return 1
            return -1 if s1 < s2 else 1
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
        return 0


class RangeEngineTest(unittest.TestCase):
    """Unit tests for semver_range_impl.RangeEngine against semver_range.pyi and semver_range_impl.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[VersionEngine],
            tier=system,
        )

    def test_parse_range_valid_expressions_and_whitespace_trimming(self) -> None:
        """POSTCONDITIONS: MUST parse valid range expressions and trim surrounding whitespace into raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)

            r_trimmed = engine.parse_range("   >=1.0.0 <2.0.0   ")
            self.assertEqual(r_trimmed, VersionRange(raw_text=">=1.0.0 <2.0.0"))

            valid_expressions = [
                "1.2.3",
                "=1.2.3",
                "==1.2.3",
                "!=1.2.3",
                "<2.0.0",
                "<=2.0.0",
                ">1.0.0",
                ">=1.0.0",
                ">= 1.0.0 < 2.0.0",
                "^1.2.3",
                "^0.2.3",
                "^0.0.3",
                "^ 1.2.3",
                "~1.2.3",
                "~ 1.2.3",
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
                ">=1.0.0 <1.5.0 || >=2.0.0 <2.5.0",
                "1.0.0-alpha.1",
                "^1.2.3-beta.1",
            ]
            for expr in valid_expressions:
                parsed = engine.parse_range(expr)
                self.assertIsInstance(parsed, VersionRange)
                self.assertTrue(len(parsed.raw_text) > 0)

    def test_parse_range_bare_partial_versions_raise_error(self) -> None:
        """PRECONDITIONS: WHEN text supplies bare partial versions lacking wildcard characters, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)

            bare_partials = [
                "1",
                "1.2",
                ">=1.2",
                "<2",
                "^1",
                "^1.2",
                "^0.0",
                "~1",
                "~1.2",
                "1.2 - 2.3",
                "1.0.0 - 2.3",
                "1.2 - 2.0.0",
            ]
            for raw in bare_partials:
                with self.assertRaises(InvalidRangeError) as ctx:
                    engine.parse_range(raw)
                self.assertEqual(ctx.exception.raw_range, raw)
                self.assertTrue(len(ctx.exception.message) > 0)

    def test_parse_range_empty_comma_and_malformed_syntax_raise_error(self) -> None:
        """PRECONDITIONS: WHEN text is empty, whitespace-only, has empty union clauses, uses commas, or violates syntax, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)

            malformed_inputs = [
                "",
                "   ",
                "||",
                "1.0.0 ||",
                "|| 1.0.0",
                "1.0.0 || || 2.0.0",
                "1.0.0 ||   || 2.0.0",
                ">=1.0.0, <2.0.0",
                "1.0.0,2.0.0",
                "~=1.2.3",
                "===1.2.3",
                ">=01.2.3",
                "^1.02.3",
                "1.0.0 -",
                "- 2.0.0",
                "not-a-range",
            ]
            for raw in malformed_inputs:
                with self.assertRaises(InvalidRangeError) as ctx:
                    engine.parse_range(raw)
                self.assertEqual(ctx.exception.raw_range, raw)
                self.assertTrue(len(ctx.exception.message) > 0)

    def test_satisfies_basic_comparators_conjunction_and_union(self) -> None:
        """POSTCONDITIONS: MUST evaluate basic comparators, conjunctions, optional operator whitespace, and || unions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)

            r_eq = engine.parse_range("= 1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), r_eq, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), r_eq, False))

            r_double_eq = engine.parse_range("==1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), r_double_eq, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), r_double_eq, False))

            r_ne = engine.parse_range("!= 1.2.3")
            self.assertFalse(engine.satisfies(Version(1, 2, 3), r_ne, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 4), r_ne, False))

            r_conj = engine.parse_range(">= 1.2.0 <= 2.0.0 != 1.5.0")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), r_conj, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), r_conj, False))
            self.assertFalse(engine.satisfies(Version(1, 5, 0), r_conj, False))
            self.assertFalse(engine.satisfies(Version(1, 1, 9), r_conj, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 1), r_conj, False))

            r_union = engine.parse_range(">1.0.0 <1.2.0 || >=2.0.0 <2.1.0")
            self.assertFalse(engine.satisfies(Version(1, 0, 0), r_union, False))
            self.assertTrue(engine.satisfies(Version(1, 1, 0), r_union, False))
            self.assertFalse(engine.satisfies(Version(1, 5, 0), r_union, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), r_union, False))
            self.assertFalse(engine.satisfies(Version(2, 1, 0), r_union, False))

    def test_satisfies_caret_tilde_wildcard_and_hyphen_ranges(self) -> None:
        """POSTCONDITIONS: MUST evaluate caret (^), tilde (~), wildcard (*, M.x, M.m.*), and hyphen ranges."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)

            # Caret non-zero major: ^1.2.3 -> >=1.2.3 <2.0.0
            r_caret_maj = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), r_caret_maj, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 0), r_caret_maj, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), r_caret_maj, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), r_caret_maj, False))

            # Caret zero major, non-zero minor: ^0.2.3 -> >=0.2.3 <0.3.0
            r_caret_min = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(Version(0, 2, 3), r_caret_min, False))
            self.assertTrue(engine.satisfies(Version(0, 2, 9), r_caret_min, False))
            self.assertFalse(engine.satisfies(Version(0, 2, 2), r_caret_min, False))
            self.assertFalse(engine.satisfies(Version(0, 3, 0), r_caret_min, False))

            # Caret zero major, zero minor: ^0.0.3 -> >=0.0.3 <0.0.4
            r_caret_pat = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(Version(0, 0, 3), r_caret_pat, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 2), r_caret_pat, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 4), r_caret_pat, False))

            # Tilde: ~1.2.3 -> >=1.2.3 <1.3.0
            r_tilde = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), r_tilde, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), r_tilde, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), r_tilde, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), r_tilde, False))

            # Wildcards: *, 1.x, 1.2.*
            r_any = engine.parse_range("*")
            self.assertTrue(engine.satisfies(Version(0, 0, 0), r_any, False))
            self.assertTrue(engine.satisfies(Version(5, 4, 3), r_any, False))

            r_maj_x = engine.parse_range("1.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), r_maj_x, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), r_maj_x, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), r_maj_x, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), r_maj_x, False))

            r_min_star = engine.parse_range("1.2.*")
            self.assertTrue(engine.satisfies(Version(1, 2, 0), r_min_star, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 8), r_min_star, False))
            self.assertFalse(engine.satisfies(Version(1, 1, 9), r_min_star, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), r_min_star, False))

            # Hyphen: 1.2.3 - 2.3.4 -> >=1.2.3 <=2.3.4
            r_hyphen = engine.parse_range("1.2.3 - 2.3.4")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), r_hyphen, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), r_hyphen, False))
            self.assertTrue(engine.satisfies(Version(2, 3, 4), r_hyphen, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), r_hyphen, False))
            self.assertFalse(engine.satisfies(Version(2, 3, 5), r_hyphen, False))

    def test_satisfies_prerelease_when_include_prerelease_is_false(self) -> None:
        """POSTCONDITIONS: WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False unless range explicitly targets same major.minor.patch prerelease."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)

            r_normal = engine.parse_range(">=1.0.0 <2.0.0")
            self.assertFalse(
                engine.satisfies(Version(1, 2, 3, prerelease=("alpha", "1")), r_normal, False)
            )

            r_star = engine.parse_range("*")
            self.assertFalse(
                engine.satisfies(Version(1, 0, 0, prerelease=("alpha",)), r_star, False)
            )

            r_pre = engine.parse_range(">=1.2.3-alpha.2 <2.0.0")
            # Same (1, 2, 3) tuple and >= alpha.2 -> True
            self.assertTrue(
                engine.satisfies(Version(1, 2, 3, prerelease=("alpha", "2")), r_pre, False)
            )
            self.assertTrue(
                engine.satisfies(Version(1, 2, 3, prerelease=("alpha", "3")), r_pre, False)
            )
            # Same (1, 2, 3) tuple but < alpha.2 -> False
            self.assertFalse(
                engine.satisfies(Version(1, 2, 3, prerelease=("alpha", "1")), r_pre, False)
            )
            # Different major.minor.patch (1, 2, 4) prerelease -> False when include_prerelease is False
            self.assertFalse(
                engine.satisfies(Version(1, 2, 4, prerelease=("alpha", "1")), r_pre, False)
            )
            # Normal version within range -> True
            self.assertTrue(engine.satisfies(Version(1, 2, 4), r_pre, False))

    def test_satisfies_prerelease_when_include_prerelease_is_true(self) -> None:
        """POSTCONDITIONS: WHEN include_prerelease is True, MUST evaluate candidate prerelease version directly against comparator boundary inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)

            r_range = engine.parse_range(">=1.0.0 <2.0.0")
            # 1.0.0-alpha < 1.0.0 so does not satisfy >=1.0.0
            self.assertFalse(
                engine.satisfies(Version(1, 0, 0, prerelease=("alpha",)), r_range, True)
            )
            # 1.0.1-alpha > 1.0.0 and < 2.0.0 -> True
            self.assertTrue(
                engine.satisfies(Version(1, 0, 1, prerelease=("alpha",)), r_range, True)
            )
            # 2.0.0-alpha < 2.0.0 by direct precedence ordering -> True
            self.assertTrue(
                engine.satisfies(Version(2, 0, 0, prerelease=("alpha",)), r_range, True)
            )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:45:01Z
# LAST_CHANGED: 2026-11-06T20:39:41Z
# CHANGE: Synchronize sys.modules package aliases between semver_solver_multi.lib and benchmark_2.parts.semver_solver_multi.lib in topological import order so VersionEngine, VersionRange, Version, and InvalidRangeError share canonical class identities
# COVERAGE_AUDIT: 2026-11-06T20:45:01Z
# QA_AUDIT: 2026-11-06T20:44:20Z
# --- END AUTOFAB METADATA ---
