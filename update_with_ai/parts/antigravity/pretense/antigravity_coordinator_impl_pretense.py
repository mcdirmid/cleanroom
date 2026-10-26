"""Pretense state machine, fake synthesis, unit tests, parity tests, and fuzzing for AntigravityCoordinatorGenerator."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.antigravity.lib import (
    antigravity_coordinator,
    antigravity_coordinator_impl,
)
from update_with_ai.parts.antigravity.lib.antigravity_coordinator import (
    AntigravityCoordinatorGenerator,
    CoordinatorSkillDocument,
    SubagentDispatchSpec,
    WakeNotificationMessage,
)
from update_with_ai.parts.subagent.lib.subagent_coordinator import RoleDispatch


@dataclass
class AntigravityCoordinatorState:
    """Canonical model state for AntigravityCoordinator."""
    last_dispatch: Optional[SubagentDispatchSpec] = None


proto = StateMachineProto[AntigravityCoordinatorState]()


# ==============================================================================
# 1. AntigravityCoordinatorGenerator Transitions
# ==============================================================================

@proto.transition(AntigravityCoordinatorGenerator.generate_coordinator_skill)
def generate_coordinator_skill(): pass

@generate_coordinator_skill.arguments
def _(
    state: AntigravityCoordinatorState,
    this: Any,
    dir_scope: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    ds = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    return (ds,)

@generate_coordinator_skill.returns
def _(
    state: AntigravityCoordinatorState,
    this: Any,
    dir_scope: str,
    outcome: object = NotBound,
) -> Optional[Outcome[CoordinatorSkillDocument]]:
    expected = CoordinatorSkillDocument(
        name="cleanroom_coordinator",
        description="Autonomous Cleanroom DAG convergence coordinator.",
        frontmatter="---\nname: cleanroom_coordinator\ndescription: Autonomous Cleanroom DAG convergence coordinator.\n---",
        content=f"# Cleanroom Coordinator Skill for {dir_scope}\n",
    )
    if isinstance(outcome, Value) and outcome.val.name == expected.name:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(AntigravityCoordinatorGenerator.format_dispatch_directive)
def format_dispatch_directive(): pass

@format_dispatch_directive.arguments
def _(
    state: AntigravityCoordinatorState,
    this: Any,
    dispatch: RoleDispatch | NotBoundType = NotBound,
    model: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[RoleDispatch, Optional[str]]]:
    if isinstance(dispatch, NotBoundType):
        disp = RoleDispatch(
            role_name="lib",
            workspace_dir="/ws/lib",
            ready_targets=["//parts/core:core#lib"],
            dir_scope="staging",
            batch_size=5,
        )
    else:
        disp = dispatch
    m = None if isinstance(model, NotBoundType) else model
    return (disp, m)

@format_dispatch_directive.returns
def _(
    state: AntigravityCoordinatorState,
    this: Any,
    dispatch: RoleDispatch,
    model: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[SubagentDispatchSpec]]:
    targets_str = ", ".join(dispatch.ready_targets) if dispatch.ready_targets else "all ready nodes"
    prompt = f"Execute autonomous Cleanroom round for role '{dispatch.role_name}' in scope '{dispatch.dir_scope}'. Nodes ready: {targets_str}."
    expected = SubagentDispatchSpec(
        type_name="cleanroom_worker",
        role=dispatch.role_name,
        prompt=prompt,
        workspace=dispatch.workspace_dir,
        model=model,
    )
    if isinstance(outcome, Value) and outcome.val.role == expected.role and outcome.val.workspace == expected.workspace:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(AntigravityCoordinatorGenerator.parse_wake_notification)
def parse_wake_notification(): pass

@parse_wake_notification.arguments
def _(
    state: AntigravityCoordinatorState,
    this: Any,
    message_text: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    msg = '{"action": "submit", "role": "lib", "submitted_targets": ["lib/core.py"]}' if isinstance(message_text, NotBoundType) else str(message_text)
    return (msg,)

@parse_wake_notification.returns
def _(
    state: AntigravityCoordinatorState,
    this: Any,
    message_text: str,
    outcome: object = NotBound,
) -> Optional[Outcome[WakeNotificationMessage]]:
    txt = message_text.strip()
    if not txt:
        expected = WakeNotificationMessage(action="idle", role="")
    else:
        # Search for JSON block
        json_matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", txt, re.DOTALL)
        cand = json_matches[0] if json_matches else None
        if not cand:
            m = re.search(r"(\{.*\})", txt, re.DOTALL)
            if m:
                cand = m.group(1)

        if cand:
            try:
                d = json.loads(cand)
                action = str(d.get("action") or d.get("status") or "complete")
                role = str(d.get("role") or "")
                subs = d.get("submitted_targets") or d.get("submitted") or []
                blms = d.get("blamed_targets") or d.get("blamed") or []
                reason = d.get("failure_reason") or d.get("reason")
                expected = WakeNotificationMessage(
                    action=action,
                    role=role,
                    submitted_targets=tuple(str(x) for x in subs),
                    blamed_targets=tuple(str(x) for x in blms),
                    failure_reason=str(reason) if reason else None,
                )
            except Exception:
                expected = WakeNotificationMessage(action="complete", role="", failure_reason=None)
        else:
            action = "idle"
            role = ""
            if "submitted" in txt.lower():
                action = "submit"
            elif "blamed" in txt.lower():
                action = "blame"
            elif "failed" in txt.lower():
                action = "fail"
            expected = WakeNotificationMessage(action=action, role=role)

    if isinstance(outcome, Value) and outcome.val.action == expected.action and outcome.val.role == expected.role:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 2. Helper Factory
# ==============================================================================

def make_antigravity_coordinator_fake(
    state: Optional[AntigravityCoordinatorState] = None,
) -> AntigravityCoordinatorGenerator:
    """Instantiate a synthesized AntigravityCoordinatorGenerator fake."""
    st = state or AntigravityCoordinatorState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(AntigravityCoordinatorGenerator)


# ==============================================================================
# 3. Unit Tests
# ==============================================================================

class TestAntigravityCoordinatorUnit(unittest.TestCase):
    """Unit tests for synthesized AntigravityCoordinator fake."""

    def setUp(self) -> None:
        self.fake = make_antigravity_coordinator_fake()

    def test_parse_wake_notification_json(self) -> None:
        msg = """```json
{
  "action": "submit",
  "role": "lib",
  "submitted_targets": ["parts/core/lib/demo.py"]
}
```"""
        parsed = self.fake.parse_wake_notification(msg)
        self.assertEqual(parsed.action, "submit")
        self.assertEqual(parsed.role, "lib")
        self.assertEqual(parsed.submitted_targets, ("parts/core/lib/demo.py",))

    def test_parse_wake_notification_empty(self) -> None:
        parsed = self.fake.parse_wake_notification("")
        self.assertEqual(parsed.action, "idle")

    def test_format_dispatch_directive(self) -> None:
        dispatch = RoleDispatch(
            role_name="lib",
            workspace_dir="/repo/staging/role_workspaces/lib",
            ready_targets=["//parts/core:core#lib"],
            dir_scope="staging",
        )
        spec = self.fake.format_dispatch_directive(dispatch, model="pro")
        self.assertEqual(spec.role, "lib")
        self.assertEqual(spec.workspace, "/repo/staging/role_workspaces/lib")
        self.assertEqual(spec.model, "pro")


# ==============================================================================
# 4. Parity Tests
# ==============================================================================

class TestAntigravityCoordinatorParity(unittest.TestCase):
    """Parity tests between fake and real AntigravityCoordinatorGenerator."""

    def setUp(self) -> None:
        self.fake = make_antigravity_coordinator_fake()
        self.real = antigravity_coordinator_impl.AntigravityCoordinatorGenerator()

    def test_parse_wake_notification_json_parity(self) -> None:
        msg = """```json
{
  "action": "blame",
  "role": "spec_qa",
  "blamed_targets": ["parts/core/low/demo.pyi"],
  "failure_reason": "Spec contract defect"
}
```"""
        fake_parsed = self.fake.parse_wake_notification(msg)
        real_parsed = self.real.parse_wake_notification(msg)
        self.assertEqual(fake_parsed.action, real_parsed.action)
        self.assertEqual(fake_parsed.role, real_parsed.role)
        self.assertEqual(tuple(fake_parsed.blamed_targets), tuple(real_parsed.blamed_targets))
        self.assertEqual(fake_parsed.failure_reason, real_parsed.failure_reason)


class TestAntigravityCoordinatorImplReal(unittest.TestCase):
    """Direct coverage tests for antigravity_coordinator_impl.py."""

    def setUp(self) -> None:
        import tempfile
        import shutil
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.antigravity.lib import antigravity_workspace

        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        antigravity_coordinator_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()

    def tearDown(self) -> None:
        import shutil
        self.phase_cm.__exit__(None, None, None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_configure_workspace(self) -> None:
        from update_with_ai.parts.antigravity.lib import antigravity_workspace
        configurer = self.scope.get_singleton(antigravity_workspace.AntigravityWorkspaceConfigurer)
        report = configurer.configure_workspace(
            workspace_dir=self.test_dir,
            role_name="lib",
            dir_scope="pkg_a",
        )
        self.assertTrue(report.is_confined)
        self.assertEqual(report.role_name, "lib")

    def test_generate_coordinator_skill(self) -> None:
        generator = self.scope.get_singleton(antigravity_coordinator.AntigravityCoordinatorGenerator)
        skill_doc = generator.generate_coordinator_skill(dir_scope="pkg_a")
        self.assertEqual(skill_doc.name, "cleanroom_coordinator")
        self.assertIn("name: cleanroom_coordinator", skill_doc.frontmatter)

    def test_format_dispatch_directive(self) -> None:
        generator = self.scope.get_singleton(antigravity_coordinator.AntigravityCoordinatorGenerator)
        dispatch = RoleDispatch(
            role_name="test",
            workspace_dir=self.test_dir,
            dir_scope="pkg_a",
            ready_targets=["tests/foo_test.py"],
            task_prompt="CRITICAL REMINDER: Unresolved targets must be concluded.",
        )
        spec = generator.format_dispatch_directive(dispatch, model="flash")
        self.assertEqual(spec.type_name, "cleanroom_worker")
        self.assertIn("CRITICAL REMINDER", spec.prompt)


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestAntigravityCoordinatorFuzz(unittest.TestCase):
    """Property fuzz testing for AntigravityCoordinator."""

    @settings(max_examples=30)
    @given(
        action=st.sampled_from(["submit", "blame", "fail", "idle"]),
        role=st.sampled_from(["high", "planning", "low", "lib", "test"]),
        target=st.text(min_size=1, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz_/."),
    )
    def test_json_roundtrip_parsing_invariants(self, action: str, role: str, target: str) -> None:
        fake = make_antigravity_coordinator_fake()
        payload = {
            "action": action,
            "role": role,
            "submitted_targets": [target] if action == "submit" else [],
            "blamed_targets": [target] if action == "blame" else [],
        }
        msg = f"Round completed:\n```json\n{json.dumps(payload)}\n```"
        parsed = fake.parse_wake_notification(msg)
        self.assertEqual(parsed.action, action)
        self.assertEqual(parsed.role, role)
