# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-09T22:40:00Z
# CHANGE: Test unmodified submit with implement message succeeds without summary and feedback requires modification
# CODE_HASH: 2b786482148b
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for submit_impl."""

import unittest
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.control.lib import submit, verification
from update_with_ai.parts.control.lib.submit_impl import SubmissionCoordinator


class MockVerificationEvaluator:
    tier = agent_session.agent_session

    def __init__(self, is_passing=True, diagnostic=""):
        self.is_passing = is_passing
        self.diagnostic = diagnostic

    def evaluate_verification(self, target=None):
        return verification.VerificationResult(
            passed=self.is_passing,
            diagnostic_output=self.diagnostic,
            is_cached=False,
        )


class MockDagStorage:
    tier = system

    def __init__(self):
        self._dirty_nodes = set()
        self.messages = {}

    def is_dirty(self, node):
        return node in self._dirty_nodes

    def mark_node_clean(self, node, change_description=None):
        self._dirty_nodes.discard(node)

    def mark_node_dirty(self, node):
        self._dirty_nodes.add(node)

    def add_message(self, message, to):
        if to not in self.messages:
            self.messages[to] = []
        self.messages[to].append(message)


class MockRoleDef:
    def __init__(self, role_name="lib", is_auditor=False, audit_tag=None, src_pattern=""):
        self.role_name = role_name
        self.is_auditor = is_auditor
        self.audit_tag = audit_tag
        self.src_pattern = src_pattern


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(self):
        self.role_definitions = {
            "lib": MockRoleDef(role_name="lib", is_auditor=False, src_pattern="{unit_dir}/lib/{unit_name}.py"),
            "qa": MockRoleDef(role_name="qa", is_auditor=True, audit_tag="QA_AUDIT", src_pattern=""),
        }
        self.feedback: Optional[list[str]] = None


class ControlSubmitImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.coordinator = SubmissionCoordinator()
        self.registry.register_instance(
            self.coordinator,
            keys=[submit.SubmissionCoordinator, SubmissionCoordinator],
            tier=agent_session.agent_session,
        )
        self.storage = MockDagStorage()
        self.registry.register_instance(
            self.storage,
            keys=[dag_storage.DagStorage],
            tier=system,
        )
        self.cfg = MockNodeConfig()
        self.registry.register_instance(
            self.cfg,
            keys=[node_config.NodeConfig],
            tier=agent_session.agent_session,
        )

    def test_submit_fails_when_verification_fails(self) -> None:
        verif = MockVerificationEvaluator(is_passing=False, diagnostic="build error")
        self.registry.register_instance(
            verif,
            keys=[verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample"),
                role_address=dag_storage.RoleAddress("lib"),
            )
            outcome = self.coordinator.submit_target(target, change_summary="Fixed issue", has_modifications=True)
            self.assertFalse(outcome.accepted)
            self.assertIn("Verification is failing", outcome.message)

    def test_submit_change_summary_rules(self) -> None:
        verif = MockVerificationEvaluator(is_passing=True)
        self.registry.register_instance(
            verif,
            keys=[verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample"),
                role_address=dag_storage.RoleAddress("lib"),
            )
            self.storage.mark_node_dirty(target)

            # Modified files require summary
            outcome1 = self.coordinator.submit_target(target, change_summary=None, has_modifications=True)
            self.assertFalse(outcome1.accepted)
            self.assertIn("change_summary was not provided", outcome1.message)

            # Unmodified files forbid summary
            outcome2 = self.coordinator.submit_target(target, change_summary="Some summary", has_modifications=False)
            self.assertFalse(outcome2.accepted)
            self.assertIn("not permitted when submitting without workspace file modifications", outcome2.message)

            # Valid modified submission
            outcome3 = self.coordinator.submit_target(target, change_summary="Updated config", has_modifications=True)
            self.assertTrue(outcome3.accepted)
            self.assertFalse(self.storage.is_dirty(target))
            self.assertNotIn(target, self.storage.messages)

    def test_submit_auditor_forbids_summary(self) -> None:
        verif = MockVerificationEvaluator(is_passing=True)
        self.registry.register_instance(
            verif,
            keys=[verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample"),
                role_address=dag_storage.RoleAddress("qa"),
            )
            outcome = self.coordinator.submit_target(target, change_summary="Audit done", has_modifications=False)
            self.assertFalse(outcome.accepted)
            self.assertIn("not permitted for audit nodes", outcome.message)

            outcome_valid = self.coordinator.submit_target(target, change_summary=None, has_modifications=False)
            self.assertTrue(outcome_valid.accepted)

    def test_submit_unmodified_with_implement_message_succeeds_without_summary(self) -> None:
        verif = MockVerificationEvaluator(is_passing=True)
        self.registry.register_instance(
            verif,
            keys=[verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample"),
                role_address=dag_storage.RoleAddress("lib"),
            )
            self.storage.mark_node_dirty(target)
            self.storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("Implement task for unit 'sample' in role 'lib'.")
                ),
                to=target,
            )

            # Unmodified implementation node without feedback MUST succeed when submitted without summary
            outcome = self.coordinator.submit_target(target, change_summary=None, has_modifications=False)
            self.assertTrue(outcome.accepted)
            self.assertFalse(self.storage.is_dirty(target))

    def test_submit_unmodified_with_feedback_fails(self) -> None:
        verif = MockVerificationEvaluator(is_passing=True)
        self.registry.register_instance(
            verif,
            keys=[verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )
        self.cfg.feedback = ["Fix syntax error"]

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample"),
                role_address=dag_storage.RoleAddress("lib"),
            )
            self.storage.mark_node_dirty(target)
            outcome = self.coordinator.submit_target(target, change_summary=None, has_modifications=False)
            self.assertFalse(outcome.accepted)
            self.assertIn("Session feedback is present but no workspace files were modified", outcome.message)

    def test_submit_target_file_strips_code_hash_in_main_and_refreshes_in_workspace(self) -> None:
        import tempfile
        import json
        import os
        from update_with_ai.parts.metadata.lib import metadata_asm
        metadata_asm.__initialize__(registry=self.registry)

        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_root:
            main_lib = os.path.join(main_root, "staging", "parts", "sample", "lib")
            ws_lib = os.path.join(ws_root, "staging", "parts", "sample", "lib")
            os.makedirs(main_lib, exist_ok=True)
            os.makedirs(ws_lib, exist_ok=True)

            main_file = os.path.join(main_lib, "sample.py")
            ws_file = os.path.join(ws_lib, "sample.py")

            # Main file has last_cleaned, last_changed, change summary, and NO code_hash
            main_content = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-15T17:42:47Z\n"
                "# LAST_CHANGED: 2026-10-14T17:45:00Z\n"
                "# CHANGE: Initial implementation\n"
                "# --- END CLEANROOM METADATA ---\n"
                "x = 1\n"
            )
            with open(main_file, "w", encoding="utf-8") as f:
                f.write(main_content)

            # Workspace file has only change and baseline code hash
            from update_with_ai.parts.metadata.lib import src_metadata
            code_hash = src_metadata.compute_code_hash("x = 1\n", "sample.py")
            ws_content = (
                "# --- CLEANROOM METADATA ---\n"
                "# CHANGE: Initial implementation\n"
                f"# CODE_HASH: {code_hash}\n"
                "# --- END CLEANROOM METADATA ---\n"
                "x = 2\n"
            )
            with open(ws_file, "w", encoding="utf-8") as f:
                f.write(ws_content)

            with open(os.path.join(ws_root, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
                json.dump({"role": "lib", "dir_scope": "staging"}, f)

            with enter_phase(agent_session.agent_session, registry=self.registry):
                outcome = self.coordinator.submit_target_file(
                    target=ws_file,
                    summary="Updated x to 2",
                    repo_root=main_root,
                    workspace_root=ws_root,
                    role_name="lib",
                )
                self.assertTrue(outcome.accepted, outcome.message)

            with open(main_file, "r", encoding="utf-8") as f:
                mf_content = f.read()
            self.assertIn("CHANGE: Updated x to 2", mf_content)
            self.assertIn("LAST_CLEANED:", mf_content)
            self.assertIn("LAST_CHANGED:", mf_content)
            self.assertNotIn("CODE_HASH:", mf_content)
            self.assertIn("x = 2", mf_content)

            with open(ws_file, "r", encoding="utf-8") as f:
                wf_content = f.read()
            self.assertIn("CHANGE: Updated x to 2", wf_content)
            self.assertIn("CODE_HASH:", wf_content)
            self.assertNotIn("LAST_CLEANED:", wf_content)
            self.assertNotIn("LAST_CHANGED:", wf_content)
            new_hash = src_metadata.compute_code_hash("x = 2\n", "sample.py")
            self.assertIn(f"CODE_HASH: {new_hash}", wf_content)


if __name__ == "__main__":
    unittest.main()
