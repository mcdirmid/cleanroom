# === File: semver_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Collection, Dict, List, Optional, Set, Tuple

from pretense import (
    StateMachine,
    require,
    require_env,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from semver_solver_deepseek_flash_2.parts.semver_solver.lib import semver_solver, semver_solver_impl
from semver_solver_deepseek_flash_2.parts.semver_solver.pretense.semver_solver_pretense import (
    SemVerSolverState,
    SemVerSolverStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class SemVerSolverImplPseudoStateMachine(SemVerSolverStateMachine):
    """Implementation pseudo-state machine binding the concrete SemVer services as the SUT."""

    # Zero state dataclasses and zero require_arg statements: the interface state
    # machine owns model state, preconditions, domains, and postcondition assertions.

    def inner_parse_version(self, text: str) -> semver_solver.Version:
        target: semver_solver.VersionEngine = sut(semver_solver.VersionEngine)
        version = target.parse_version(text)
        assert version.format() == text
        return version

    def inner_compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        target: semver_solver.VersionEngine = sut(semver_solver.VersionEngine)
        return target.compare_precedence(v1, v2)

    def inner_parse_range(self, text: str) -> semver_solver.VersionRange:
        target: semver_solver.VersionEngine = sut(semver_solver.VersionEngine)
        parsed = target.parse_range(text)
        assert parsed.raw_text == text.strip()
        return parsed

    def inner_satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: semver_solver.VersionEngine = sut(semver_solver.VersionEngine)
        return target.satisfies(version, range_constraint, include_prerelease)

    def inner_register_package(self, release: semver_solver.PackageRelease) -> None:
        target: semver_solver.PackageRepository = sut(semver_solver.PackageRepository)
        target.register_package(release)
        assert target.has_package(release.name)

    def inner_get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        target: semver_solver.PackageRepository = sut(semver_solver.PackageRepository)
        releases = target.get_releases(name)
        assert all(release.name == name for release in releases)
        return releases

    def inner_has_package(self, name: str) -> bool:
        target: semver_solver.PackageRepository = sut(semver_solver.PackageRepository)
        return target.has_package(name)

    def inner_all_packages(self) -> Set[str]:
        target: semver_solver.PackageRepository = sut(semver_solver.PackageRepository)
        return target.all_packages()

    def inner_resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        target: semver_solver.DependencySolver = sut(semver_solver.DependencySolver)
        return target.resolve(root_dependencies)


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on the Real Implementation (Implementation Components)
# ==============================================================================

def make_sut() -> Dict[type[Any], Any]:
    """Enters a fresh lifecycle scope registering the concrete SemVer services."""
    registry = LifecycleRegistry()
    registry.register_singleton(
        semver_solver_impl.VersionEngine,
        keys=[semver_solver.VersionEngine],
        tier=system,
    )
    registry.register_singleton(
        semver_solver_impl.PackageRepository,
        keys=[semver_solver.PackageRepository],
        tier=system,
    )
    registry.register_singleton(
        semver_solver_impl.DependencySolver,
        keys=[semver_solver.DependencySolver],
        tier=system,
    )
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return {
        semver_solver.VersionEngine: get_singleton(semver_solver.VersionEngine),
        semver_solver.PackageRepository: get_singleton(semver_solver.PackageRepository),
        semver_solver.DependencySolver: get_singleton(semver_solver.DependencySolver),
    }


impl_proto = SemVerSolverImplPseudoStateMachine()


SemVerSolverFuzzTest = compile_hypothesis_test_case(
    proto=impl_proto,
    sut_factory=make_sut,
    initial_state_factory=impl_proto.make_initial_state,
    name="SemVerSolverFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenario Tests (Implementation Components, requested by coverage)
# ==============================================================================

class TestSemVerSolverImplReal(LifecycleTestCase):
    """Fixed scenarios covering every SemVer contract facet beside conformance fuzzing."""

    target = semver_solver_impl

    def setUp(self) -> None:
        super().setUp()
        engine = get_singleton(semver_solver.VersionEngine)
        repository = get_singleton(semver_solver.PackageRepository)
        solver = get_singleton(semver_solver.DependencySolver)
        self.sm = SemVerSolverImplPseudoStateMachine(
            singletons={
                semver_solver.VersionEngine: engine,
                semver_solver.PackageRepository: repository,
                semver_solver.DependencySolver: solver,
            }
        )
        self.sm.seed_initial()
        self.engine = self.sm.as_checked(semver_solver.VersionEngine, engine)
        self.repository = self.sm.as_checked(semver_solver.PackageRepository, repository)
        self.solver = self.sm.as_checked(semver_solver.DependencySolver, solver)

    # --- VersionEngine.parse_version: valid_syntax / leading_zero_grammar ---

    def test_parse_version_valid_syntax(self) -> None:
        version = self.engine.parse_version("1.0.0")
        self.assertEqual((version.major, version.minor, version.patch), (1, 0, 0))
        self.assertEqual(version.prerelease, ())
        self.assertEqual(version.build, ())

    def test_parse_version_prerelease_and_build(self) -> None:
        version = self.engine.parse_version("2.10.3-alpha.1+build.42")
        self.assertEqual((version.major, version.minor, version.patch), (2, 10, 3))
        self.assertEqual(version.prerelease, ("alpha", "1"))
        self.assertEqual(version.build, ("build", "42"))

    def test_parse_version_leading_zero_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidVersionError).parse_version("01.0.0")

    def test_parse_version_malformed_grammar_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidVersionError).parse_version("1.0")

    # --- VersionEngine.compare_precedence: tri_state / prerelease_ordering / build_metadata_ignored ---

    def test_compare_precedence_tri_state(self) -> None:
        self.assertLess(
            self.engine.compare_precedence(
                semver_solver.Version(1, 0, 0),
                semver_solver.Version(2, 0, 0),
            ),
            0,
        )
        self.assertGreater(
            self.engine.compare_precedence(
                semver_solver.Version(2, 0, 0),
                semver_solver.Version(1, 0, 0),
            ),
            0,
        )
        self.assertEqual(
            self.engine.compare_precedence(
                semver_solver.Version(1, 0, 0),
                semver_solver.Version(1, 0, 0),
            ),
            0,
        )

        self.assertLess(
            self.engine.compare_precedence(
                semver_solver.Version(1, 0, 0),
                semver_solver.Version(1, 0, 1),
            ),
            0,
        )

    def test_compare_precedence_normal_above_prerelease(self) -> None:
        self.assertGreater(
            self.engine.compare_precedence(
                semver_solver.Version(1, 0, 0),
                semver_solver.Version(1, 0, 0, ("alpha",)),
            ),
            0,
        )

    def test_compare_precedence_prerelease_ordering(self) -> None:
        self.assertLess(
            self.engine.compare_precedence(
                semver_solver.Version(1, 0, 0, ("1",)),
                semver_solver.Version(1, 0, 0, ("alpha",)),
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                semver_solver.Version(1, 0, 0, ("alpha", "1")),
                semver_solver.Version(1, 0, 0, ("alpha", "2")),
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                semver_solver.Version(1, 0, 0, ("alpha",)),
                semver_solver.Version(1, 0, 0, ("beta",)),
            ),
            0,
        )

        self.assertLess(
            self.engine.compare_precedence(
                semver_solver.Version(1, 0, 0, ("alpha",)),
                semver_solver.Version(1, 0, 0, ("alpha", "1")),
            ),
            0,
        )

    def test_compare_precedence_build_metadata_ignored(self) -> None:
        self.assertEqual(
            self.engine.compare_precedence(
                semver_solver.Version(1, 0, 0, (), ("build.1",)),
                semver_solver.Version(1, 0, 0, (), ("build.2",)),
            ),
            0,
        )

    # --- VersionEngine.parse_range: comparators_and_prefixes / hyphen_ranges / union_alternatives ---

    def test_parse_range_comparators_and_prefixes(self) -> None:
        self.assertEqual(
            self.engine.parse_range(">=1.0.0 <2.0.0").raw_text, ">=1.0.0 <2.0.0"
        )
        self.assertEqual(self.engine.parse_range("^1.2.3").raw_text, "^1.2.3")
        self.assertEqual(self.engine.parse_range("~1.2.3").raw_text, "~1.2.3")
        self.assertEqual(self.engine.parse_range("!=1.x").raw_text, "!=1.x")
        self.assertEqual(self.engine.parse_range("1.2.x").raw_text, "1.2.x")
        self.assertEqual(self.engine.parse_range("^*").raw_text, "^*")
        self.assertEqual(self.engine.parse_range("^0.x").raw_text, "^0.x")
        self.assertEqual(self.engine.parse_range("^0.2.x").raw_text, "^0.2.x")
        self.assertEqual(self.engine.parse_range("^0.0.x").raw_text, "^0.0.x")
        self.assertEqual(self.engine.parse_range("^0.0.3").raw_text, "^0.0.3")
        self.assertEqual(self.engine.parse_range("~*").raw_text, "~*")
        self.assertEqual(self.engine.parse_range("~1.x").raw_text, "~1.x")
        self.assertEqual(self.engine.parse_range("<1.x").raw_text, "<1.x")
        self.assertEqual(self.engine.parse_range("<=1.x").raw_text, "<=1.x")
        self.assertEqual(self.engine.parse_range(">1.x").raw_text, ">1.x")
        self.assertEqual(self.engine.parse_range(">=1.x").raw_text, ">=1.x")
        self.assertEqual(self.engine.parse_range(">=*").raw_text, ">=*")
        self.assertEqual(self.engine.parse_range("!=*").raw_text, "!=*")

    def test_parse_range_operator_whitespace(self) -> None:
        self.assertEqual(self.engine.parse_range(">= 1.0.0").raw_text, ">= 1.0.0")

    def test_parse_range_hyphen_ranges(self) -> None:
        self.assertEqual(
            self.engine.parse_range("1.0.0 - 2.x").raw_text, "1.0.0 - 2.x"
        )
        self.assertEqual(
            self.engine.parse_range("1.0.0 - *").raw_text, "1.0.0 - *"
        )
        self.assertEqual(
            self.engine.parse_range("1.0.0 - 2.0.0").raw_text, "1.0.0 - 2.0.0"
        )

    def test_parse_range_union_alternatives(self) -> None:
        self.assertEqual(
            self.engine.parse_range("1.x || >=3.0.0").raw_text, "1.x || >=3.0.0"
        )

    def test_parse_range_whitespace_trimming(self) -> None:
        self.assertEqual(
            self.engine.parse_range(" >=1.0.0 <2.0.0 ").raw_text, ">=1.0.0 <2.0.0"
        )

    def test_parse_range_bare_partial_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range("1.2")

    def test_parse_range_comma_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range("1.0.0,2.0.0")

    def test_parse_range_empty_union_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range("1.0.0 || ")

    def test_parse_range_excess_component_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range("1.2.3.4")

    def test_parse_range_non_numeric_component_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range("1.a")

    def test_parse_range_component_after_wildcard_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range("1.x.3")

    def test_parse_range_dangling_comparator_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range(">=")

    def test_parse_range_prefix_without_operand_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range("^")

    def test_parse_range_empty_text_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range("")

    def test_parse_range_bare_partial_hyphen_rejected(self) -> None:
        self.engine.violating(semver_solver.InvalidRangeError).parse_range("1.2 - 2.3")

    # --- VersionEngine.satisfies: boolean_match / prerelease_filter / prerelease_inequality ---

    def test_satisfies_boolean_match(self) -> None:
        constraint = semver_solver.VersionRange(raw_text=">=1.0.0 <2.0.0")
        self.assertTrue(
            self.engine.satisfies(semver_solver.Version(1, 5, 0), constraint, False)
        )
        self.assertFalse(
            self.engine.satisfies(semver_solver.Version(3, 0, 0), constraint, False)
        )
        self.assertTrue(
            self.engine.satisfies(
                semver_solver.Version(1, 0, 0),
                semver_solver.VersionRange(raw_text="==1.0.0"),
                False,
            )
        )
        self.assertFalse(
            self.engine.satisfies(
                semver_solver.Version(2, 0, 0),
                semver_solver.VersionRange(raw_text="==1.0.0"),
                False,
            )
        )
        self.assertTrue(
            self.engine.satisfies(
                semver_solver.Version(2, 0, 0),
                semver_solver.VersionRange(raw_text="!=1.0.0"),
                False,
            )
        )
        self.assertFalse(
            self.engine.satisfies(
                semver_solver.Version(1, 0, 0),
                semver_solver.VersionRange(raw_text="!=1.0.0"),
                False,
            )
        )
        self.assertFalse(
            self.engine.satisfies(
                semver_solver.Version(2, 0, 0),
                semver_solver.VersionRange(raw_text="<=1.0.0"),
                False,
            )
        )
        self.assertFalse(
            self.engine.satisfies(
                semver_solver.Version(1, 0, 0),
                semver_solver.VersionRange(raw_text=">1.0.0"),
                False,
            )
        )

    def test_satisfies_constraint_set_alternatives(self) -> None:
        self.assertTrue(
            self.engine.satisfies(
                semver_solver.Version(1, 5, 0),
                semver_solver.VersionRange(raw_text="1.x || >=3.0.0"),
                False,
            )
        )
        self.assertFalse(
            self.engine.satisfies(
                semver_solver.Version(2, 0, 0),
                semver_solver.VersionRange(raw_text="1.x || >=3.0.0"),
                False,
            )
        )

    def test_satisfies_prerelease_filter(self) -> None:
        candidate = semver_solver.Version(1, 0, 0, ("alpha",))
        self.assertFalse(
            self.engine.satisfies(
                candidate,
                semver_solver.VersionRange(raw_text=">=1.0.0"),
                False,
            )
        )
        self.assertTrue(
            self.engine.satisfies(
                candidate,
                semver_solver.VersionRange(raw_text=">=1.0.0-alpha"),
                False,
            )
        )

    def test_satisfies_prerelease_inequality(self) -> None:
        candidate = semver_solver.Version(1, 0, 0, ("alpha",))
        self.assertFalse(
            self.engine.satisfies(
                candidate,
                semver_solver.VersionRange(raw_text=">=1.0.0"),
                True,
            )
        )
        self.assertTrue(
            self.engine.satisfies(
                candidate,
                semver_solver.VersionRange(raw_text=">=1.0.0-alpha"),
                True,
            )
        )

    # --- PackageRepository: register_release / descending_releases / has_membership / all_names ---

    def test_register_release_and_descending_releases(self) -> None:
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(1, 0, 0))
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(2, 0, 0))
        )
        releases = self.repository.get_releases("pkg")
        self.assertEqual(
            [release.version for release in releases],
            [semver_solver.Version(2, 0, 0), semver_solver.Version(1, 0, 0)],
        )

    def test_has_package_membership(self) -> None:
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(1, 0, 0))
        )
        self.assertTrue(self.repository.has_package("pkg"))
        self.assertFalse(self.repository.has_package("absent"))

    def test_all_packages_names(self) -> None:
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(1, 0, 0))
        )
        self.assertEqual(self.repository.all_packages(), {"pkg"})

    def test_get_releases_missing_package(self) -> None:
        self.repository.violating(semver_solver.PackageNotFoundError).get_releases("absent")

    # --- DependencySolver.resolve: compatible_assignment / highest_precedence / unsatisfiable_conflict ---

    def test_solver_highest_precedence_selection(self) -> None:
        self.repository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(1, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "pkg",
                        semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(1, 0, 0))
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(2, 0, 0))
        )
        outcome = self.solver.resolve([
            semver_solver.PackageDependency(
                "pkg",
                semver_solver.VersionRange(raw_text=">=0.0.0"),
            ),
        ])
        self.assertEqual(
            outcome.selected_versions["pkg"], semver_solver.Version(2, 0, 0)
        )

    def test_solver_transitive_compatible_assignment(self) -> None:
        self.repository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(1, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "pkg",
                        semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(1, 0, 0))
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(2, 0, 0))
        )
        outcome = self.solver.resolve([
            semver_solver.PackageDependency(
                "app",
                semver_solver.VersionRange(raw_text=">=1.0.0"),
            ),
        ])
        self.assertEqual(
            outcome.selected_versions["app"], semver_solver.Version(1, 0, 0)
        )
        self.assertEqual(
            outcome.selected_versions["pkg"], semver_solver.Version(2, 0, 0)
        )

    def test_solver_nested_failure_constraint_rollback(self) -> None:
        self.repository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(1, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "pkg",
                        semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        self.repository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(2, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "pkg",
                        semver_solver.VersionRange(raw_text="==1.0.0"),
                    ),
                    semver_solver.PackageDependency(
                        "lib",
                        semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(1, 0, 0))
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(2, 0, 0))
        )
        self.repository.register_package(
            semver_solver.PackageRelease(
                "lib",
                semver_solver.Version(1, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "core",
                        semver_solver.VersionRange(raw_text="==1.0.0"),
                    ),
                ),
            )
        )
        outcome = self.solver.resolve([
            semver_solver.PackageDependency(
                "app",
                semver_solver.VersionRange(raw_text=">=1.0.0"),
            ),
        ])
        self.assertEqual(
            outcome.selected_versions["app"], semver_solver.Version(1, 0, 0)
        )
        self.assertEqual(
            outcome.selected_versions["pkg"], semver_solver.Version(2, 0, 0)
        )
        self.assertNotIn("core", outcome.selected_versions)

    def test_solver_backtrack_constraint_rollback(self) -> None:
        self.repository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(1, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "pkg",
                        semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        self.repository.register_package(
            semver_solver.PackageRelease(
                "app",
                semver_solver.Version(2, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "pkg",
                        semver_solver.VersionRange(raw_text="==1.0.0"),
                    ),
                    semver_solver.PackageDependency(
                        "lib",
                        semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(1, 0, 0))
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(2, 0, 0))
        )
        outcome = self.solver.resolve([
            semver_solver.PackageDependency(
                "app",
                semver_solver.VersionRange(raw_text=">=1.0.0"),
            ),
            semver_solver.PackageDependency(
                "pkg",
                semver_solver.VersionRange(raw_text="==2.0.0"),
            ),
        ])
        self.assertEqual(
            outcome.selected_versions["app"], semver_solver.Version(1, 0, 0)
        )
        self.assertEqual(
            outcome.selected_versions["pkg"], semver_solver.Version(2, 0, 0)
        )

    def test_solver_unsatisfiable_conflict(self) -> None:
        self.repository.register_package(
            semver_solver.PackageRelease(
                "tool",
                semver_solver.Version(1, 0, 0),
                (
                    semver_solver.PackageDependency(
                        "pkg",
                        semver_solver.VersionRange(raw_text="==1.0.0"),
                    ),
                ),
            )
        )
        self.repository.register_package(
            semver_solver.PackageRelease("pkg", semver_solver.Version(2, 0, 0))
        )
        self.solver.violating(semver_solver.ResolutionConflictError).resolve([
            semver_solver.PackageDependency(
                "tool",
                semver_solver.VersionRange(raw_text=">=1.0.0"),
            ),
            semver_solver.PackageDependency(
                "pkg",
                semver_solver.VersionRange(raw_text="==2.0.0"),
            ),
        ])

    def test_solver_unregistered_package_conflict(self) -> None:
        self.solver.violating(semver_solver.ResolutionConflictError).resolve([
            semver_solver.PackageDependency(
                "missing",
                semver_solver.VersionRange(raw_text=">=1.0.0"),
            ),
        ])

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:02:32Z
# LAST_CHANGED: 2026-11-15T04:02:00Z
# CHANGE: Resolve third [from:pretense_coverage] round: add zero-major multi-component caret parse_range scenarios (^0.2.x, ^0.0.x, ^0.0.3); add test_solver_unregistered_package_conflict exercising ResolutionConflictError reification for an unregistered package reference; add test_solver_nested_failure_constraint_rollback where app 2.0.0 introduces pkg==1.0.0 and lib>=1.0.0 constraints, lib 1.0.0's core==1.0.0 requirement fails deep in recursion, the introduced constraints are rolled back, and app 1.0.0 resolves pkg 2.0.0 successfully. Transitive scenario now resolves app 1.0.0 to pkg 2.0.0 without the trap releases, and app 2.0.0 registrations include its lib dependency to match the seeded release contract.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T04:02:32Z
# PRETENSE_QA_AUDIT: 2026-11-15T04:02:19Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
import unittest

from pretense import (
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

from semver_solver_deepseek_flash_2.parts.semver_solver.lib import semver_solver


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class SemVerSolverState:
    """Model state for the version engine, package repository, and dependency solver services."""
    initialized: bool = True
    version_texts: List[str] = field(default_factory=list)
    version_values: List[semver_solver.Version] = field(default_factory=list)
    range_texts: List[str] = field(default_factory=list)
    range_values: List[semver_solver.VersionRange] = field(default_factory=list)
    release_values: List[semver_solver.PackageRelease] = field(default_factory=list)
    dependency_sets: List[List[semver_solver.PackageDependency]] = field(default_factory=list)
    parsed_versions: List[semver_solver.Version] = field(default_factory=list)
    parsed_ranges: List[semver_solver.VersionRange] = field(default_factory=list)
    version_pairs: List[Tuple[semver_solver.Version, semver_solver.Version]] = field(default_factory=list)
    satisfaction_queries: List[Tuple[semver_solver.Version, semver_solver.VersionRange, bool, bool]] = field(default_factory=list)
    required_releases: List[semver_solver.PackageRelease] = field(default_factory=list)
    registered_releases: List[semver_solver.PackageRelease] = field(default_factory=list)
    registered_names: List[str] = field(default_factory=list)
    releases: Dict[str, List[semver_solver.PackageRelease]] = field(default_factory=dict)
    outcomes: List[semver_solver.ResolutionOutcome] = field(default_factory=list)


class SemVerSolverStateMachine(StateMachine[SemVerSolverState]):
    """Unified Pretense state machine modeling the SemVer engine, repository, and solver."""

    def __init__(
        self,
        state: Optional[SemVerSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> SemVerSolverState:
        """Constructs the blank model state transitioned by seeding transitions."""
        return SemVerSolverState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds grammar-valid argument domains for fuzzing from a blank initial state."""
        self.state.version_texts.extend(["1.0.0", "2.10.3-alpha.1+build.42"])
        self.state.version_values.extend([
            semver_solver.Version(1, 0, 0),
            semver_solver.Version(1, 0, 1),
            semver_solver.Version(2, 0, 0),
            semver_solver.Version(1, 5, 0),
            semver_solver.Version(3, 0, 0),
            semver_solver.Version(2, 10, 3, ("alpha", "1"), ("build", "42")),
            semver_solver.Version(1, 0, 0, ("alpha",)),
            semver_solver.Version(1, 0, 0, ("alpha", "1")),
            semver_solver.Version(1, 0, 0, ("alpha", "2")),
            semver_solver.Version(1, 0, 0, ("1",)),
            semver_solver.Version(1, 0, 0, ("beta",)),
            semver_solver.Version(1, 0, 0, (), ("build.1",)),
            semver_solver.Version(1, 0, 0, (), ("build.2",)),
        ])
        self.state.range_texts.extend([
            ">=1.0.0",
            ">=1.0.0 <2.0.0",
            "1.0.0 - 2.x",
            "^1.2.3",
            "~1.2.3",
            "~1.x",
            ">=1.x",
            "!=1.x",
            ">1.*",
            "^1.x",
            "1.x || >=3.0.0",
            ">=*",
            "==1.0.0",
            "!=1.0.0",
            "<1.0.0",
            "<=1.0.0",
            ">1.0.0",
            "1.0.0",
            "1.x",
            "1.2.x",
            "1.2.3",
            ">=1.0.0-alpha",
            " >=1.0.0 <2.0.0 ",
            "^*",
            "^0.x",
            "^0.2.x",
            "^0.0.x",
            "^0.0.3",
            "~*",
            "<1.x",
            "<=1.x",
            ">1.x",
            ">= 1.0.0",
            "1.0.0 - *",
            "1.0.0 - 2.0.0",
            "!=*",
        ])
        self.state.range_values.extend([
            semver_solver.VersionRange(raw_text=">=1.0.0"),
            semver_solver.VersionRange(raw_text=">=1.0.0 <2.0.0"),
            semver_solver.VersionRange(raw_text="1.0.0 - 2.x"),
            semver_solver.VersionRange(raw_text="^1.2.3"),
            semver_solver.VersionRange(raw_text="~1.2.3"),
            semver_solver.VersionRange(raw_text="~1.x"),
            semver_solver.VersionRange(raw_text=">=1.x"),
            semver_solver.VersionRange(raw_text="!=1.x"),
            semver_solver.VersionRange(raw_text=">1.*"),
            semver_solver.VersionRange(raw_text="^1.x"),
            semver_solver.VersionRange(raw_text="1.x || >=3.0.0"),
            semver_solver.VersionRange(raw_text=">=*"),
            semver_solver.VersionRange(raw_text="==1.0.0"),
            semver_solver.VersionRange(raw_text="!=1.0.0"),
            semver_solver.VersionRange(raw_text="<1.0.0"),
            semver_solver.VersionRange(raw_text="<=1.0.0"),
            semver_solver.VersionRange(raw_text=">1.0.0"),
            semver_solver.VersionRange(raw_text="1.0.0"),
            semver_solver.VersionRange(raw_text="1.x"),
            semver_solver.VersionRange(raw_text="1.2.x"),
            semver_solver.VersionRange(raw_text="1.2.3"),
            semver_solver.VersionRange(raw_text=">=1.0.0-alpha"),
        ])
        self.state.release_values.extend([
            semver_solver.PackageRelease(
                name="app",
                version=semver_solver.Version(1, 0, 0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="pkg",
                        range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            ),
            semver_solver.PackageRelease(
                name="app",
                version=semver_solver.Version(2, 0, 0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="pkg",
                        range_constraint=semver_solver.VersionRange(raw_text="==1.0.0"),
                    ),
                    semver_solver.PackageDependency(
                        name="lib",
                        range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            ),
            semver_solver.PackageRelease(name="pkg", version=semver_solver.Version(1, 0, 0)),
            semver_solver.PackageRelease(name="pkg", version=semver_solver.Version(2, 0, 0)),
            semver_solver.PackageRelease(
                name="lib",
                version=semver_solver.Version(1, 0, 0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="core",
                        range_constraint=semver_solver.VersionRange(raw_text="==1.0.0"),
                    ),
                ),
            ),
            semver_solver.PackageRelease(
                name="tool",
                version=semver_solver.Version(1, 0, 0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="pkg",
                        range_constraint=semver_solver.VersionRange(raw_text="==1.0.0"),
                    ),
                ),
            ),
        ])
        self.state.required_releases.extend([
            semver_solver.PackageRelease(
                name="app",
                version=semver_solver.Version(1, 0, 0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="pkg",
                        range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            ),
            semver_solver.PackageRelease(name="pkg", version=semver_solver.Version(2, 0, 0)),
        ])
        self.state.dependency_sets.extend([
            [],
            [semver_solver.PackageDependency(
                name="pkg",
                range_constraint=semver_solver.VersionRange(raw_text=">=0.0.0"),
            )],
            [semver_solver.PackageDependency(
                name="app",
                range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
            )],
            [
                semver_solver.PackageDependency(
                    name="app",
                    range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
                ),
                semver_solver.PackageDependency(
                    name="pkg",
                    range_constraint=semver_solver.VersionRange(raw_text="==2.0.0"),
                ),
            ],
        ])

    @transition(semver_solver.VersionEngine.parse_version)
    def parse_version(self, text: str) -> semver_solver.Version:
        require_arg(text, self.state.version_texts, error=semver_solver.InvalidVersionError)
        ret = self.inner_parse_version(text)
        self.state.parsed_versions.append(ret)
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        return ret

    @transition(semver_solver.VersionEngine.compare_precedence)
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        require_arg(v1, self.state.version_values)
        require_arg(v2, self.state.version_values)
        ret = self.inner_compare_precedence(v1, v2)
        self.state.version_pairs.append((v1, v2))
        reverse = self.inner_compare_precedence(v2, v1)
        assert (ret > 0) == (reverse < 0)
        assert (ret < 0) == (reverse > 0)
        assert (ret == 0) == (reverse == 0)
        return ret

    @transition(semver_solver.VersionEngine.parse_range)
    def parse_range(self, text: str) -> semver_solver.VersionRange:
        require_arg(text, self.state.range_texts, error=semver_solver.InvalidRangeError)
        ret = self.inner_parse_range(text)
        self.state.parsed_ranges.append(ret)
        assert ret.raw_text == text.strip()
        return ret

    @transition(semver_solver.VersionEngine.satisfies)
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(version, self.state.version_values)
        require_arg(range_constraint, self.state.range_values)
        require_arg(include_prerelease, bool)
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        self.state.satisfaction_queries.append(
            (version, range_constraint, include_prerelease, ret)
        )
        assert ret == self.inner_satisfies(version, range_constraint, include_prerelease)
        return ret

    @transition(semver_solver.PackageRepository.register_package)
    def register_package(self, release: semver_solver.PackageRelease) -> None:
        require_arg(release, self.state.release_values)
        self.inner_register_package(release)
        self.state.registered_names.append(release.name)
        self.state.registered_releases.append(release)
        self.state.releases.setdefault(release.name, []).append(release)
        assert self.state.releases[release.name][-1] == release
        assert release.name in self.state.registered_names

    @transition(semver_solver.PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        require(bool(self.state.registered_names))
        require_arg(name, self.state.registered_names, error=semver_solver.PackageNotFoundError)
        ret = self.inner_get_releases(name)
        assert len(ret) == len(self.state.releases[name])
        assert set(ret) == set(self.state.releases[name])
        return ret

    @transition(semver_solver.PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(name, str)
        ret = self.inner_has_package(name)
        assert ret == (name in self.state.releases)
        return ret

    @transition(semver_solver.PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        ret = self.inner_all_packages()
        assert ret == set(self.state.releases)
        return ret

    @transition(semver_solver.DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        require(set(self.state.registered_releases) >= set(self.state.required_releases))
        require_arg(root_dependencies, self.state.dependency_sets, error=semver_solver.ResolutionConflictError)
        ret = self.inner_resolve(root_dependencies)
        self.state.outcomes.append(ret)
        assert set(ret.selected_versions) >= {
            dependency.name for dependency in root_dependencies
        }
        return ret

    # Inner transitions compute expected fake behavior (no state mutation, no asserts):
    def inner_parse_version(self, text: str) -> semver_solver.Version:
        return semver_solver.Version(0, 0, 0)

    def inner_compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        return 0

    def inner_parse_range(self, text: str) -> semver_solver.VersionRange:
        return semver_solver.VersionRange(raw_text=text.strip())

    def inner_satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        return True

    def inner_register_package(self, release: semver_solver.PackageRelease) -> None:
        return None

    def inner_get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        return list(self.state.releases[name])

    def inner_has_package(self, name: str) -> bool:
        return name in self.state.releases

    def inner_all_packages(self) -> Set[str]:
        return set(self.state.releases)

    def inner_resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        return semver_solver.ResolutionOutcome(
            selected_versions={
                dependency.name: semver_solver.Version(0, 0, 0)
                for dependency in root_dependencies
            },
            derivation_steps=(),
        )


proto = SemVerSolverStateMachine()


# ==============================================================================
# 2. Fakes (Interface Components)
# ==============================================================================

FakeSemVerSolver = synthesize_fake(SemVerSolverStateMachine)


FakeSemVerSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemVerSolverFuzzTest",
)


class TestSemVerSolverFake(unittest.TestCase):
    """Fixed fake scenarios covering the resolve edge branch not reached by fuzzing gates."""

    def setUp(self) -> None:
        self.sm = SemVerSolverStateMachine()
        self.sm.seed_initial()

    def test_resolve_with_registered_repository(self) -> None:
        self.sm.register_package(
            semver_solver.PackageRelease(
                name="app",
                version=semver_solver.Version(1, 0, 0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="pkg",
                        range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        self.sm.register_package(
            semver_solver.PackageRelease(
                name="pkg",
                version=semver_solver.Version(2, 0, 0),
            )
        )
        outcome = self.sm.resolve([
            semver_solver.PackageDependency(
                name="app",
                range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
            ),
        ])
        self.assertIn("app", outcome.selected_versions)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T04:01:53Z
# LAST_CHANGED: 2026-11-15T04:01:53Z
# CHANGE: Seed the zero-major multi-component caret scenarios (^0.2.x, ^0.0.x, ^0.0.3) in the parse_range domain, give app 2.0.0 a second lib dependency and add a lib 1.0.0 release that transitively requires the unregistered core package, enabling nested-failure rollback scenarios while keeping the resolve gate (app 1.0.0 + pkg 2.0.0 registered) safe for all seeded dependency sets; fake verification and 100% coverage remain intact.
# --- END AUTOFAB METADATA ---
