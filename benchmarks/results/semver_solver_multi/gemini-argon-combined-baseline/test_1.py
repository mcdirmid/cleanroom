# === File: dependency_solver_impl_test.py ===
"""Unit tests for dependency_solver_impl."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib import dependency_solver
from semver_solver_multi.lib import semver_core
from semver_solver_multi.lib import semver_range
from semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)


class _StubVersionEngine(semver_core.VersionEngine):
    """Lightweight protocol test double for semver_core.VersionEngine."""

    def parse_version(self, text: str) -> semver_core.Version:
        parts = text.split(".")
        return semver_core.Version(int(parts[0]), int(parts[1]), int(parts[2]))

    def compare_precedence(
        self, v1: semver_core.Version, v2: semver_core.Version
    ) -> int:
        c1 = (v1.major, v1.minor, v1.patch)
        c2 = (v2.major, v2.minor, v2.patch)
        if c1 < c2:
            return -1
        if c1 > c2:
            return 1
        return 0


class _StubRangeEngine(semver_range.RangeEngine):
    """Lightweight protocol test double for semver_range.RangeEngine."""

    def parse_range(self, text: str) -> semver_range.VersionRange:
        return semver_range.VersionRange(raw_text=text.strip())

    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        raw = range_constraint.raw_text.strip()
        if raw == "*":
            return True
        if raw.startswith("^"):
            parts = [int(x) for x in raw[1:].split(".")]
            target = (parts[0], parts[1], parts[2])
            cand = (version.major, version.minor, version.patch)
            return target <= cand < (parts[0] + 1, 0, 0)
        if raw.startswith(">=") and "<" in raw:
            ge_part, lt_part = raw.split("<")
            low_p = [int(x) for x in ge_part.replace(">=", "").strip().split(".")]
            high_p = [int(x) for x in lt_part.strip().split(".")]
            cand = (version.major, version.minor, version.patch)
            return (low_p[0], low_p[1], low_p[2]) <= cand < (
                high_p[0],
                high_p[1],
                high_p[2],
            )
        if raw.startswith("=="):
            parts = [int(x) for x in raw[2:].strip().split(".")]
            return (version.major, version.minor, version.patch) == (
                parts[0],
                parts[1],
                parts[2],
            )
        parts = [int(x) for x in raw.split(".")]
        return (version.major, version.minor, version.patch) == (
            parts[0],
            parts[1],
            parts[2],
        )


class TestDependencySolverImpl(unittest.TestCase):
    """Verifies PackageRepository and DependencySolver contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = _StubVersionEngine()
        self.range_engine = _StubRangeEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[semver_core.VersionEngine],
            tier=system,
        )
        self.registry.register_instance(
            self.range_engine,
            keys=[semver_range.RangeEngine],
            tier=system,
        )
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.scope = self.phase_scope.__enter__()
        self.repo = self.scope.get_singleton(PackageRepository)
        self.solver = self.scope.get_singleton(DependencySolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_repository_registration_and_queries(self) -> None:
        """Verifies register_package sorting, get_releases, has_package, and all_packages."""
        self.assertFalse(self.repo.has_package("alpha"))
        self.assertEqual(self.repo.all_packages(), set())

        with self.assertRaises(dependency_solver.PackageNotFoundError) as ctx:
            self.repo.get_releases("alpha")
        self.assertEqual(ctx.exception.package_name, "alpha")

        r1 = dependency_solver.PackageRelease("alpha", semver_core.Version(1, 0, 0))
        r3 = dependency_solver.PackageRelease("alpha", semver_core.Version(2, 0, 0))
        r2 = dependency_solver.PackageRelease("alpha", semver_core.Version(1, 5, 0))
        self.repo.register_package(r1)
        self.repo.register_package(r3)
        self.repo.register_package(r2)

        self.assertTrue(self.repo.has_package("alpha"))
        self.assertEqual(self.repo.all_packages(), {"alpha"})
        releases = self.repo.get_releases("alpha")
        self.assertEqual(releases, [r3, r2, r1])

    def test_solver_backtracking_and_highest_precedence(self) -> None:
        """Verifies transitive resolution, backtracking on conflict, and already-assigned checks."""
        # Scenario where:
        # root requires app ^1.0.0 and core ^1.0.0
        # app 1.1.0 requires util ==2.0.0 and shared ==1.0.0
        # app 1.0.0 requires util ==1.0.0 and shared ==1.0.0
        # core 1.0.0 requires util ==1.0.0 and shared ==1.0.0
        # util 2.0.0 requires core ==2.0.0 (which conflicts with assigned core 1.0.0!)
        # util 1.0.0 has no dependencies
        # shared 1.0.0 has no dependencies
        self.repo.register_package(
            dependency_solver.PackageRelease(
                "core",
                semver_core.Version(1, 0, 0),
                dependencies=(
                    dependency_solver.PackageDependency(
                        "util", semver_range.VersionRange("==1.0.0")
                    ),
                    dependency_solver.PackageDependency(
                        "shared", semver_range.VersionRange("==1.0.0")
                    ),
                ),
            )
        )
        self.repo.register_package(
            dependency_solver.PackageRelease(
                "app",
                semver_core.Version(1, 1, 0),
                dependencies=(
                    dependency_solver.PackageDependency(
                        "core", semver_range.VersionRange("==2.0.0")
                    ),
                    dependency_solver.PackageDependency(
                        "extra", semver_range.VersionRange("==1.0.0")
                    ),
                ),
            )
        )
        self.repo.register_package(
            dependency_solver.PackageRelease(
                "app",
                semver_core.Version(1, 0, 0),
                dependencies=(
                    dependency_solver.PackageDependency(
                        "core", semver_range.VersionRange("==1.0.0")
                    ),
                    dependency_solver.PackageDependency(
                        "util", semver_range.VersionRange("==1.0.0")
                    ),
                    dependency_solver.PackageDependency(
                        "shared", semver_range.VersionRange("==1.0.0")
                    ),
                ),
            )
        )
        self.repo.register_package(
            dependency_solver.PackageRelease(
                "util", semver_core.Version(1, 0, 0)
            )
        )
        self.repo.register_package(
            dependency_solver.PackageRelease(
                "shared", semver_core.Version(1, 0, 0)
            )
        )
        self.repo.register_package(
            dependency_solver.PackageRelease(
                "extra", semver_core.Version(1, 0, 0)
            )
        )

        # Also test a branch that introduces a new constraint and then fails in recursive backtrack()
        # by adding a higher release app 1.2.0 that depends on extra ==1.0.0 and util ==2.0.0 (which has 0 viable candidates when core 1.0.0 requires util ==1.0.0)
        self.repo.register_package(
            dependency_solver.PackageRelease(
                "app",
                semver_core.Version(1, 2, 0),
                dependencies=(
                    dependency_solver.PackageDependency(
                        "extra", semver_range.VersionRange("==1.0.0")
                    ),
                    dependency_solver.PackageDependency(
                        "util", semver_range.VersionRange("==2.0.0")
                    ),
                ),
            )
        )

        outcome = self.solver.resolve(
            [
                dependency_solver.PackageDependency(
                    "core", semver_range.VersionRange("^1.0.0")
                ),
                dependency_solver.PackageDependency(
                    "app", semver_range.VersionRange("^1.0.0")
                ),
            ]
        )
        self.assertEqual(
            outcome.selected_versions,
            {
                "core": semver_core.Version(1, 0, 0),
                "app": semver_core.Version(1, 0, 0),
                "util": semver_core.Version(1, 0, 0),
                "shared": semver_core.Version(1, 0, 0),
            },
        )
        self.assertGreater(len(outcome.derivation_steps), 0)

    def test_solver_missing_package_and_unsatisfiable_conflict(self) -> None:
        """Verifies ResolutionConflictError when packages are missing or constraints conflict."""
        with self.assertRaises(dependency_solver.ResolutionConflictError) as ctx:
            self.solver.resolve(
                [
                    dependency_solver.PackageDependency(
                        "missing_pkg", semver_range.VersionRange("^1.0.0")
                    )
                ]
            )
        self.assertIn("missing_pkg", ctx.exception.conflicting_packages)
        self.assertTrue(len(ctx.exception.explanation) > 0)

        # Registered package whose candidates all lead to unsatisfiable transitive conflicts
        self.repo.register_package(
            dependency_solver.PackageRelease(
                "pkg_a",
                semver_core.Version(1, 0, 0),
                dependencies=(
                    dependency_solver.PackageDependency(
                        "pkg_b", semver_range.VersionRange("==2.0.0")
                    ),
                ),
            )
        )
        self.repo.register_package(
            dependency_solver.PackageRelease(
                "pkg_b", semver_core.Version(1, 0, 0)
            )
        )
        with self.assertRaises(dependency_solver.ResolutionConflictError) as ctx2:
            self.solver.resolve(
                [
                    dependency_solver.PackageDependency(
                        "pkg_a", semver_range.VersionRange("^1.0.0")
                    ),
                    dependency_solver.PackageDependency(
                        "pkg_b", semver_range.VersionRange("^1.0.0")
                    ),
                ]
            )
        self.assertIn("pkg_a", ctx2.exception.conflicting_packages)
        self.assertIn("pkg_b", ctx2.exception.conflicting_packages)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: a62215d74f81
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for semver_core_impl."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib import semver_core
from semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
    __initialize__,
)


class TestVersionEngine(unittest.TestCase):
    """Verifies SemVer 2.0.0 parsing and precedence comparison contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.scope = self.phase_scope.__enter__()
        self.engine = self.scope.get_singleton(VersionEngine)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_normal_prerelease_and_build_versions(self) -> None:
        """Verifies parsing valid SemVer 2.0.0 strings and Version formatting properties."""
        v_normal = self.engine.parse_version("1.2.3")
        self.assertEqual(v_normal, semver_core.Version(1, 2, 3))
        self.assertFalse(v_normal.is_prerelease)
        self.assertEqual(v_normal.format(), "1.2.3")
        self.assertEqual(str(v_normal), "1.2.3")

        v_pre = self.engine.parse_version("1.0.0-alpha.1.0a")
        self.assertEqual(
            v_pre,
            semver_core.Version(1, 0, 0, prerelease=("alpha", "1", "0a")),
        )
        self.assertTrue(v_pre.is_prerelease)
        self.assertEqual(v_pre.format(), "1.0.0-alpha.1.0a")

        v_build = self.engine.parse_version("2.1.0+20130313144700.exp.sha.5114f85")
        self.assertEqual(
            v_build,
            semver_core.Version(
                2, 1, 0, build=("20130313144700", "exp", "sha", "5114f85")
            ),
        )
        self.assertFalse(v_build.is_prerelease)
        self.assertEqual(str(v_build), "2.1.0+20130313144700.exp.sha.5114f85")

        v_full = self.engine.parse_version("0.1.0-rc.1+build.01")
        self.assertEqual(
            v_full,
            semver_core.Version(
                0, 1, 0, prerelease=("rc", "1"), build=("build", "01")
            ),
        )
        self.assertEqual(str(v_full), "0.1.0-rc.1+build.01")

    def test_parse_invalid_versions_raises_error(self) -> None:
        """Verifies InvalidVersionError when syntax or leading zero rules are violated."""
        invalid_inputs = [
            "",
            "1.2",
            "1.2.3.4",
            "v1.2.3",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2.3-01",
            "1.2.3-alpha..1",
            "1.2.3+",
            "1.2.3-alpha+build..1",
        ]
        for raw in invalid_inputs:
            with self.assertRaises(semver_core.InvalidVersionError) as ctx:
                self.engine.parse_version(raw)
            self.assertEqual(ctx.exception.raw_text, raw)
            self.assertEqual(str(ctx.exception), ctx.exception.message)

    def test_compare_precedence_rules(self) -> None:
        """Verifies SemVer 2.0.0 precedence ordering across core, prerelease, and build."""
        p = self.engine.parse_version

        # Major, minor, patch numerical ordering
        self.assertLess(self.engine.compare_precedence(p("1.0.0"), p("2.0.0")), 0)
        self.assertGreater(self.engine.compare_precedence(p("2.0.0"), p("1.0.0")), 0)
        self.assertLess(self.engine.compare_precedence(p("1.1.0"), p("1.2.0")), 0)
        self.assertLess(self.engine.compare_precedence(p("1.1.1"), p("1.1.2")), 0)
        self.assertEqual(self.engine.compare_precedence(p("1.2.3"), p("1.2.3")), 0)

        # Normal version ranks higher than prerelease
        self.assertGreater(
            self.engine.compare_precedence(p("1.0.0"), p("1.0.0-alpha")), 0
        )
        self.assertLess(
            self.engine.compare_precedence(p("1.0.0-alpha"), p("1.0.0")), 0
        )

        # Prerelease segment comparisons: numeric vs numeric, numeric vs string, string vs string, length
        chain = [
            "1.0.0-1",
            "1.0.0-2",
            "1.0.0-10",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        ]
        for i in range(len(chain) - 1):
            v_low = p(chain[i])
            v_high = p(chain[i + 1])
            self.assertLess(self.engine.compare_precedence(v_low, v_high), 0)
            self.assertGreater(self.engine.compare_precedence(v_high, v_low), 0)
            self.assertEqual(self.engine.compare_precedence(v_low, v_low), 0)

        # Build metadata ignored in precedence comparison
        self.assertEqual(
            self.engine.compare_precedence(
                p("1.0.0-alpha+001"), p("1.0.0-alpha+999")
            ),
            0,
        )
        self.assertEqual(
            self.engine.compare_precedence(p("1.0.0+2013"), p("1.0.0+2024")),
            0,
        )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: a3cba4d7e0d1
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for semver_range_impl."""

from __future__ import annotations

import re
from typing import Tuple
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib import semver_core
from semver_solver_multi.lib import semver_range
from semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
    __initialize__,
)


_MOCK_SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class _StubVersionEngine(semver_core.VersionEngine):
    """Lightweight protocol test double for semver_core.VersionEngine."""

    def parse_version(self, text: str) -> semver_core.Version:
        m = _MOCK_SEMVER_RE.fullmatch(text)
        if m is None:
            raise semver_core.InvalidVersionError(message="invalid", raw_text=text)
        maj, min_, pat, pre, bld = m.groups()
        pre_t: Tuple[str, ...] = tuple(pre.split(".")) if pre else ()
        for s in pre_t:
            if s.isdigit() and len(s) > 1 and s.startswith("0"):
                raise semver_core.InvalidVersionError(message="zero", raw_text=text)
        bld_t: Tuple[str, ...] = tuple(bld.split(".")) if bld else ()
        return semver_core.Version(int(maj), int(min_), int(pat), pre_t, bld_t)

    def compare_precedence(
        self, v1: semver_core.Version, v2: semver_core.Version
    ) -> int:
        c1 = (v1.major, v1.minor, v1.patch)
        c2 = (v2.major, v2.minor, v2.patch)
        if c1 != c2:
            return -1 if c1 < c2 else 1
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
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


class TestRangeEngine(unittest.TestCase):
    """Verifies version range parsing and constraint satisfaction contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = _StubVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[semver_core.VersionEngine],
            tier=system,
        )
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.scope = self.phase_scope.__enter__()
        self.engine = self.scope.get_singleton(RangeEngine)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _v(self, text: str) -> semver_core.Version:
        return self.version_engine.parse_version(text)

    def test_parse_range_valid_and_trimming(self) -> None:
        """Verifies valid range parsing, whitespace trimming, and str representation."""
        r = self.engine.parse_range("  >= 1.0.0 < 2.0.0 || ^3.0.0  ")
        self.assertEqual(r.raw_text, ">= 1.0.0 < 2.0.0 || ^3.0.0")
        self.assertEqual(str(r), ">= 1.0.0 < 2.0.0 || ^3.0.0")

        for expr in [
            "1.0.0",
            "=1.0.0",
            "== 1.0.0",
            "!= 1.0.0",
            "<2.0.0",
            "<= 2.0.0",
            "> 1.0.0",
            ">= 1.0.0",
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
            "1.0.0 - 2.0.0",
        ]:
            parsed = self.engine.parse_range(expr)
            self.assertEqual(parsed.raw_text, expr)

    def test_parse_range_invalid_raises_error(self) -> None:
        """Verifies InvalidRangeError on empty, comma-delimited, partial, or malformed ranges."""
        invalid_ranges = [
            "",
            "   ",
            ">=1.0.0, <2.0.0",
            "1.0.0 ||",
            "|| 1.0.0",
            "1.0.0 ||   || 2.0.0",
            "1",
            "1.2",
            "^0.0",
            "~1.2",
            "1.2 - 2.3",
            "1.0.0 -",
            "1.0.0 - 2.x",
            ">= 1.x",
            "invalid",
        ]
        for raw in invalid_ranges:
            with self.assertRaises(semver_range.InvalidRangeError) as ctx:
                self.engine.parse_range(raw)
            self.assertEqual(ctx.exception.raw_range, raw)

    def test_satisfies_comparators_caret_tilde_wildcards_hyphen_unions(self) -> None:
        """Verifies range satisfaction across all comparator and expansion constructs."""
        # Basic comparators
        r_eq = self.engine.parse_range("== 1.2.3")
        self.assertTrue(self.engine.satisfies(self._v("1.2.3"), r_eq, False))
        self.assertFalse(self.engine.satisfies(self._v("1.2.4"), r_eq, False))

        r_ne = self.engine.parse_range("!= 1.2.3")
        self.assertFalse(self.engine.satisfies(self._v("1.2.3"), r_ne, False))
        self.assertTrue(self.engine.satisfies(self._v("1.2.4"), r_ne, False))

        r_gt_le = self.engine.parse_range("> 1.0.0 <= 2.0.0")
        self.assertFalse(self.engine.satisfies(self._v("1.0.0"), r_gt_le, False))
        self.assertTrue(self.engine.satisfies(self._v("1.5.0"), r_gt_le, False))
        self.assertTrue(self.engine.satisfies(self._v("2.0.0"), r_gt_le, False))
        self.assertFalse(self.engine.satisfies(self._v("2.0.1"), r_gt_le, False))

        # Caret ranges (^M.m.p, ^0.m.p, ^0.0.p)
        r_caret_maj = self.engine.parse_range("^1.2.3")
        self.assertTrue(self.engine.satisfies(self._v("1.2.3"), r_caret_maj, False))
        self.assertTrue(self.engine.satisfies(self._v("1.9.0"), r_caret_maj, False))
        self.assertFalse(self.engine.satisfies(self._v("2.0.0"), r_caret_maj, False))

        r_caret_min = self.engine.parse_range("^0.2.3")
        self.assertTrue(self.engine.satisfies(self._v("0.2.3"), r_caret_min, False))
        self.assertTrue(self.engine.satisfies(self._v("0.2.9"), r_caret_min, False))
        self.assertFalse(self.engine.satisfies(self._v("0.3.0"), r_caret_min, False))

        r_caret_pat = self.engine.parse_range("^0.0.3")
        self.assertTrue(self.engine.satisfies(self._v("0.0.3"), r_caret_pat, False))
        self.assertFalse(self.engine.satisfies(self._v("0.0.4"), r_caret_pat, False))

        # Tilde range (~M.m.p)
        r_tilde = self.engine.parse_range("~1.2.3")
        self.assertTrue(self.engine.satisfies(self._v("1.2.3"), r_tilde, False))
        self.assertTrue(self.engine.satisfies(self._v("1.2.9"), r_tilde, False))
        self.assertFalse(self.engine.satisfies(self._v("1.3.0"), r_tilde, False))

        # Wildcards (*, M.x, M.m.*)
        r_any = self.engine.parse_range("*")
        self.assertTrue(self.engine.satisfies(self._v("0.0.0"), r_any, False))
        self.assertTrue(self.engine.satisfies(self._v("9.9.9"), r_any, False))

        r_maj_w = self.engine.parse_range("1.x")
        self.assertTrue(self.engine.satisfies(self._v("1.0.0"), r_maj_w, False))
        self.assertTrue(self.engine.satisfies(self._v("1.9.9"), r_maj_w, False))
        self.assertFalse(self.engine.satisfies(self._v("2.0.0"), r_maj_w, False))

        r_min_w = self.engine.parse_range("1.2.*")
        self.assertTrue(self.engine.satisfies(self._v("1.2.0"), r_min_w, False))
        self.assertTrue(self.engine.satisfies(self._v("1.2.8"), r_min_w, False))
        self.assertFalse(self.engine.satisfies(self._v("1.3.0"), r_min_w, False))

        # Hyphen and union ranges
        r_hyphen_union = self.engine.parse_range("1.0.0 - 1.2.0 || >= 2.0.0 < 2.1.0")
        self.assertTrue(
            self.engine.satisfies(self._v("1.1.0"), r_hyphen_union, False)
        )
        self.assertFalse(
            self.engine.satisfies(self._v("1.5.0"), r_hyphen_union, False)
        )
        self.assertTrue(
            self.engine.satisfies(self._v("2.0.5"), r_hyphen_union, False)
        )

    def test_satisfies_prerelease_semantics(self) -> None:
        """Verifies prerelease filtering when include_prerelease is False vs True."""
        r_normal = self.engine.parse_range(">=1.0.0 <2.0.0")
        # 1.0.0-alpha < 1.0.0 in precedence, so False for both include_prerelease=False and True
        self.assertFalse(
            self.engine.satisfies(self._v("1.0.0-alpha"), r_normal, False)
        )
        self.assertFalse(
            self.engine.satisfies(self._v("1.0.0-alpha"), r_normal, True)
        )

        # 1.2.0-alpha is within [1.0.0, 2.0.0), so False when include_prerelease=False, True when True
        self.assertFalse(
            self.engine.satisfies(self._v("1.2.0-alpha"), r_normal, False)
        )
        self.assertTrue(
            self.engine.satisfies(self._v("1.2.0-alpha"), r_normal, True)
        )

        # Explicit prerelease target on same major.minor.patch matches even when include_prerelease=False
        r_pre_target = self.engine.parse_range(">=1.2.0-alpha.1 <2.0.0")
        self.assertTrue(
            self.engine.satisfies(self._v("1.2.0-alpha.2"), r_pre_target, False)
        )
        self.assertFalse(
            self.engine.satisfies(self._v("1.3.0-alpha.1"), r_pre_target, False)
        )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: be6b70d7cd19
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---
