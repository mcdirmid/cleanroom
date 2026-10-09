# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: d6995ec38e7e
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Unit tests for control_verification_impl."""

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.control.lib import control_verification
from update_with_ai.parts.control.lib.control_verification_impl import (
    VerificationEvaluator,
)


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(self, checks=None, read_write_files=None) -> None:
        self.verification_checks = checks or []
        self.read_write_files = read_write_files or []


class MockCheck:
    def __init__(self, is_passing=True, diagnostic="", command=None):
        self.is_passing = is_passing
        self.diagnostic = diagnostic
        self.command = command

    def verify(self):
        return self.is_passing, self.diagnostic


class ControlVerificationImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.evaluator = VerificationEvaluator()
        self.registry.register_instance(
            self.evaluator,
            keys=[control_verification.VerificationEvaluator, VerificationEvaluator],
            tier=agent_session.agent_session,
        )

    def test_clean_diagnostic_noise(self) -> None:
        raw_text = (
            "Loading: \n"
            "Analyzing: target //update_with_ai/parts/control:lib\n"
            "INFO: Analyzed target //update_with_ai/parts/control:lib\n"
            "bazel-bin/test.log\n"
            "Error: name 'foo' is not defined\n"
            "Executed 0 out of 1 test: 1 fail\n"
        )
        cleaned = self.evaluator.clean_diagnostic_noise(raw_text)
        self.assertEqual(cleaned, "Error: name 'foo' is not defined")

    def test_evaluate_verification_passing_and_caching(self) -> None:
        mock_cfg = MockNodeConfig(checks=[MockCheck(is_passing=True)])
        self.registry.register_instance(
            mock_cfg,
            keys=[agent_node_config.NodeConfig],
            tier=agent_session.agent_session,
        )

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample_unit"),
                role_address=dag_storage.RoleAddress("sample_role"),
            )
            res1 = self.evaluator.evaluate_verification(target=target)
            self.assertTrue(res1.passed)
            self.assertFalse(res1.is_cached)

            # Subsequent evaluation with unchanged hash should be cached
            res2 = self.evaluator.evaluate_verification(target=target)
            self.assertTrue(res2.passed)
            self.assertTrue(res2.is_cached)

    def test_evaluate_verification_failing(self) -> None:
        mock_cfg = MockNodeConfig(
            checks=[MockCheck(is_passing=False, diagnostic="SyntaxError: invalid syntax")]
        )
        self.registry.register_instance(
            mock_cfg,
            keys=[agent_node_config.NodeConfig],
            tier=agent_session.agent_session,
        )

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample_unit_2"),
                role_address=dag_storage.RoleAddress("sample_role"),
            )
            res = self.evaluator.evaluate_verification(target=target)
            self.assertFalse(res.passed)
            self.assertIn("SyntaxError: invalid syntax", res.diagnostic_output)


if __name__ == "__main__":
    unittest.main()
