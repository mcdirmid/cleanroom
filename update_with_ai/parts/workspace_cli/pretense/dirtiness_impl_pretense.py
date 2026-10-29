"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceDirtinessEvaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
from update_with_ai.parts.workspace_cli.lib.dirtiness import (
    UnitDirtinessResult,
    WorkspaceDirtinessEvaluator,
)


@dataclass
class DirtinessState:
    """Canonical model state for WorkspaceDirtinessEvaluator."""
    dirty_units: PretenseSet[str] = field(default_factory=PretenseSet)
    reasons: PretenseDict[str, List[str]] = field(default_factory=PretenseDict)
    contract_files: PretenseDict[str, List[str]] = field(default_factory=PretenseDict)
    dependencies: PretenseDict[str, List[Tuple[str, str]]] = field(default_factory=PretenseDict)


class WorkspaceDirtinessStateMachine(StateMachine[DirtinessState]):
    """Unified Pretense State Machine for WorkspaceDirtinessEvaluator."""

    def __init__(
        self,
        state: Optional[DirtinessState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DirtinessState(), singletons=singletons)

    @transition.seeding(name="seed_unit_dirtiness")
    def seed_unit_dirtiness(
        self,
        ctx: TransitionContext[Any, [str, bool, Optional[Sequence[str]]], None],
    ) -> None:
        ctx.arguments(
                    unit_key=Domain(strategy=lambda: 'parts/core:core#lib'),
                    is_dirty=Domain(strategy=lambda: True),
                    reasons=Domain(strategy=lambda: ()),
                )
        ctx.returns(lambda unit_key="parts/core:core#lib", is_dirty=True, reasons=None: None)
        ctx.update(lambda res, unit_key="parts/core:core#lib", is_dirty=True, reasons=None: (
            (self.state.dirty_units.add(unit_key), self.state.reasons.__setitem__(unit_key, list(reasons or ())))
            if is_dirty else
            (self.state.dirty_units.discard(unit_key), self.state.reasons.pop(unit_key, None))
        ))

    @transition(WorkspaceDirtinessEvaluator.evaluate_unit_dirty)
    def evaluate_unit_dirty(
        self,
        ctx: TransitionContext[WorkspaceDirtinessEvaluator, [str, str, str, str, Optional[str]], UnitDirtinessResult],
    ) -> None:
        ctx.arguments(
                    ws_root=Domain(strategy=lambda: '/repo/staging/role_workspaces/lib'),
                    part_dir=Domain(strategy=lambda: 'parts/core'),
                    unit_name=Domain(strategy=lambda: 'core'),
                    eval_role=Domain(strategy=lambda: 'lib'),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda ws_root, part_dir, unit_name, eval_role, repo_root=None: (
            UnitDirtinessResult(
                is_dirty=f"{part_dir}:{unit_name}#{eval_role}" in self.state.dirty_units,
                dirtiness_reasons=tuple(self.state.reasons.get(f"{part_dir}:{unit_name}#{eval_role}", ())),
                dependency_files=(),
                contract_files=(),
            )
        ))
        ctx.update(lambda res, ws_root, part_dir, unit_name, eval_role, repo_root=None: None)

    @transition(WorkspaceDirtinessEvaluator.resolve_contract_files)
    def resolve_contract_files(
        self,
        ctx: TransitionContext[WorkspaceDirtinessEvaluator, [str, str, Optional[str], Optional[str]], Sequence[str]],
    ) -> None:
        ctx.arguments(
                    target_file=Domain(strategy=lambda: 'parts/core/lib/demo.py'),
                    ws_root=Domain(strategy=lambda: '/repo'),
                    main_root=Domain(strategy=lambda: None),
                    role_name=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda target_file, ws_root, main_root=None, role_name=None: tuple(self.state.contract_files.get(target_file, ())))
        ctx.update(lambda res, target_file, ws_root, main_root=None, role_name=None: None)

    @transition(WorkspaceDirtinessEvaluator.extract_cross_unit_dependencies)
    def extract_cross_unit_dependencies(
        self,
        ctx: TransitionContext[WorkspaceDirtinessEvaluator, [str, str, str], Sequence[Tuple[str, str]]],
    ) -> None:
        ctx.arguments(
                    repo_root=Domain(strategy=lambda: '/repo'),
                    part_dir=Domain(strategy=lambda: 'parts/core'),
                    unit_name=Domain(strategy=lambda: 'core'),
                )
        ctx.returns(lambda repo_root, part_dir, unit_name: tuple(self.state.dependencies.get(f"{part_dir}:{unit_name}", ())))
        ctx.update(lambda res, repo_root, part_dir, unit_name: None)


proto = WorkspaceDirtinessStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_dirtiness_evaluator_fake(state: Optional[DirtinessState] = None) -> WorkspaceDirtinessEvaluator:
    """Instantiate a synthesized WorkspaceDirtinessEvaluator fake."""
    st = state or DirtinessState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceDirtinessEvaluator)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceDirtinessEvaluatorUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceDirtinessEvaluator fake."""

    def setUp(self) -> None:
        self.state = DirtinessState()
        self.sm = proto.make_state_machine(self.state)
        self.sm.seed_unit_dirtiness(
            "parts/core:core#lib",
            is_dirty=True,
            reasons=["low specification changed"],
        )
        self.fake: WorkspaceDirtinessEvaluator = self.sm.as_fake(WorkspaceDirtinessEvaluator)

    def test_evaluate_unit_dirty_true(self) -> None:
        res = self.fake.evaluate_unit_dirty("/ws", "parts/core", "core", "lib")
        self.assertTrue(res.is_dirty)
        self.assertEqual(res.dirtiness_reasons, ("low specification changed",))

    def test_evaluate_unit_dirty_false(self) -> None:
        res = self.fake.evaluate_unit_dirty("/ws", "parts/dag", "dag", "lib")
        self.assertFalse(res.is_dirty)
        self.assertEqual(res.dirtiness_reasons, ())


class TestWorkspaceDirtinessEvaluatorImplReal(unittest.TestCase):
    """Direct unit tests for dirtiness_impl.py."""

    def setUp(self) -> None:
        import os
        import tempfile
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.metadata.lib import src_metadata_impl
        from update_with_ai.parts.workspace.lib import role_registry_impl, roles_impl
        from update_with_ai.parts.workspace_cli.lib import dirtiness, dirtiness_impl

        self.registry = LifecycleRegistry()
        src_metadata_impl.__initialize__(self.registry)
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        dirtiness_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.evaluator = self.scope.get_singleton(dirtiness_impl.WorkspaceDirtinessEvaluator)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_evaluate_dirtiness_missing_and_clean(self) -> None:
        import os
        import tempfile
        from update_with_ai.parts.metadata.lib import src_metadata

        with tempfile.TemporaryDirectory() as tmp_root:
            roles_file = os.path.join(tmp_root, "cleanroom_roles.toml")
            with open(roles_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.low]\n'
                    'name = "low"\n'
                    'src_pattern = "{unit_dir}/low/{unit_name}.pyi"\n\n'
                    '[roles.lib]\n'
                    'name = "lib"\n'
                    'src_pattern = "{unit_dir}/lib/{unit_name}.py"\n'
                    'role_deps = ["low"]\n'
                )

            unit_dir = os.path.join(tmp_root, "parts", "sample")
            os.makedirs(os.path.join(unit_dir, "lib"), exist_ok=True)
            os.makedirs(os.path.join(unit_dir, "low"), exist_ok=True)

            lib_f = os.path.join(unit_dir, "lib", "sample.py")
            low_f = os.path.join(unit_dir, "low", "sample.pyi")

            # 1. Missing target is dirty
            res_missing = self.evaluator.evaluate_unit_dirty(
                ws_root=tmp_root,
                part_dir=os.path.join(tmp_root, "parts", "sample"),
                unit_name="sample",
                eval_role="lib",
                repo_root=tmp_root,
            )
            self.assertTrue(res_missing.is_dirty)

            # 2. Created clean
            with open(low_f, "w", encoding="utf-8") as f:
                f.write("def foo() -> int: ...\n")
            src_metadata.record_change(low_f, "initial low")

            with open(lib_f, "w", encoding="utf-8") as f:
                f.write("def foo() -> int:\n    return 42\n")
            src_metadata.record_change(lib_f, "initial lib")

            res_clean = self.evaluator.evaluate_unit_dirty(
                ws_root=tmp_root,
                part_dir=os.path.join(tmp_root, "parts", "sample"),
                unit_name="sample",
                eval_role="lib",
                repo_root=tmp_root,
            )
            self.assertFalse(res_clean.is_dirty)

            # 3. Dirty flag
            src_metadata.update_metadata(lib_f, dirty="syntax error")
            res_dirty = self.evaluator.evaluate_unit_dirty(
                ws_root=tmp_root,
                part_dir=os.path.join(tmp_root, "parts", "sample"),
                unit_name="sample",
                eval_role="lib",
                repo_root=tmp_root,
            )
            self.assertTrue(res_dirty.is_dirty)

            # 4. Upstream modified
            src_metadata.update_metadata(
                lib_f,
                last_cleaned="2026-10-10T12:00:00Z",
                last_changed="2026-10-10T12:00:00Z",
                clear_dirty=True,
            )
            src_metadata.update_metadata(
                low_f,
                last_cleaned="2026-10-10T14:00:00Z",
                last_changed="2026-10-10T14:00:00Z",
                clear_dirty=True,
            )
            res_up = self.evaluator.evaluate_unit_dirty(
                ws_root=tmp_root,
                part_dir=os.path.join(tmp_root, "parts", "sample"),
                unit_name="sample",
                eval_role="lib",
                repo_root=tmp_root,
            )
            self.assertTrue(res_up.is_dirty)

    def test_extract_cross_unit_dependencies(self) -> None:
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_root:
            high_dir = os.path.join(tmp_root, "parts", "foo", "high")
            os.makedirs(high_dir, exist_ok=True)
            spec_file = os.path.join(high_dir, "bar.md")
            with open(spec_file, "w", encoding="utf-8") as f:
                f.write("# bar spec\n\nimports: //parts/baz:qux\n\n## Purpose\n")

            deps = self.evaluator.extract_cross_unit_dependencies(
                repo_root=tmp_root,
                part_dir="parts/foo",
                unit_name="bar",
            )
            self.assertEqual(list(deps), [("parts/baz", "qux")])




# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceDirtinessEvaluatorFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceDirtinessEvaluator."""

    @settings(max_examples=30)
    @given(
        is_dirty=st.booleans(),
        reason=st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _"),
    )
    def test_dirtiness_invariants(self, is_dirty: bool, reason: str) -> None:
        state = DirtinessState()
        sm = proto.make_state_machine(state)
        sm.seed_unit_dirtiness("parts/test:test#lib", is_dirty=is_dirty, reasons=[reason] if is_dirty else [])

        fake = sm.as_fake(WorkspaceDirtinessEvaluator)
        res = fake.evaluate_unit_dirty("/ws", "parts/test", "test", "lib")
        self.assertEqual(res.is_dirty, is_dirty)
        if is_dirty:
            self.assertEqual(res.dirtiness_reasons, (reason,))
        else:
            self.assertEqual(res.dirtiness_reasons, ())
