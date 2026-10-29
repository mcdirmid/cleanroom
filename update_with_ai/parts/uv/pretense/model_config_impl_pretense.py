"""Pretense specifications and tests for model_config_impl."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from pretense import StateMachine, TransitionContext, transition
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.dag.lib.dag_config import DagConfig
from update_with_ai.parts.openai.lib.openai_config import OpenAIConfig
from update_with_ai.parts.uv.lib.model_config_impl import (
    AgentConfig as AgentConfigImpl,
    DagConfig as DagConfigImpl,
    OpenAIConfig as OpenAIConfigImpl,
    __initialize__,
)


# ==============================================================================
# 1. Pretense State Definitions
# ==============================================================================

@dataclass
class DagConfigState:
    node_visit_limit: int = 100
    batch_size: int = 1


class DagConfigStateMachine(StateMachine[DagConfigState]):
    """Pretense StateMachine for DagConfig."""

    def __init__(self, state: Optional[DagConfigState] = None):
        super().__init__(state=state or DagConfigState())

    # ==============================================================================
    # 2. DagConfig Transitions
    # ==============================================================================

    @transition(getattr(DagConfig, "node_visit_limit"))
    def node_visit_limit(
        self,
        ctx: TransitionContext[DagConfig, [], int],
    ) -> None:
        ctx.returns(lambda: self.state.node_visit_limit)

    @transition(getattr(DagConfig, "batch_size"))
    def batch_size(
        self,
        ctx: TransitionContext[DagConfig, [], int],
    ) -> None:
        ctx.returns(lambda: self.state.batch_size)


proto = DagConfigStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_dag_config_fake(state: Optional[DagConfigState] = None) -> DagConfig:
    """Instantiate a synthesized DagConfig fake."""
    sm = DagConfigStateMachine(state)
    return sm.as_fake(DagConfig)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestDagConfigUnit(unittest.TestCase):
    """Unit tests for synthesized DagConfig fake."""

    def setUp(self) -> None:
        self.state = DagConfigState(node_visit_limit=42, batch_size=2)
        self.fake = make_dag_config_fake(self.state)

    def test_dag_config_properties(self) -> None:
        self.assertEqual(self.fake.node_visit_limit, 42)
        self.assertEqual(self.fake.batch_size, 2)


class TestModelConfigImplReal(unittest.TestCase):
    """Direct unit tests for model_config_impl.py."""

    def setUp(self) -> None:
        self.orig_cwd = os.getcwd()
        self.orig_env = dict(os.environ)
        self.orig_argv = list(sys.argv)
        self.tmp_config_dir = tempfile.TemporaryDirectory()
        os.environ["CLEANROOM_CONFIG_DIR"] = self.tmp_config_dir.name

    def tearDown(self) -> None:
        os.chdir(self.orig_cwd)
        os.environ.clear()
        os.environ.update(self.orig_env)
        sys.argv = list(self.orig_argv)
        self.tmp_config_dir.cleanup()

    def test_default_model_config(self) -> None:
        for var in [
            "CLEANROOM_MODEL",
            "CLEANROOM_MODEL_CONFIG_FILE",
            "MODEL_CONFIG_TARGET",
            "OPENAI_MODEL",
            "OPENAI_BASE_URL",
            "OPENAI_API_KEY",
        ]:
            os.environ.pop(var, None)
        sys.argv = ["cleanroom-loop"]
        os.environ["CLEANROOM_MODEL_CONFIG_FILE"] = "/tmp/nonexistent_models_12345.toml"

        reg = LifecycleRegistry()
        __initialize__(reg)

        with enter_phase("system", registry=reg) as scope:
            openai_cfg = scope.get_singleton(OpenAIConfig)
            agent_cfg = scope.get_singleton(AgentConfig)
            dag_cfg = scope.get_singleton(DagConfig)

            self.assertIsInstance(openai_cfg, OpenAIConfigImpl)
            self.assertIsInstance(agent_cfg, AgentConfigImpl)
            self.assertIsInstance(dag_cfg, DagConfigImpl)

            self.assertEqual(openai_cfg.model_name, "gpt-4o")
            self.assertIsNone(openai_cfg.base_url)
            self.assertIsNone(openai_cfg.api_key)
            self.assertEqual(openai_cfg.timeout, 60.0)
            self.assertEqual(openai_cfg.temperature, 0.7)
            self.assertIsNone(openai_cfg.max_tokens)

            self.assertEqual(agent_cfg.conversation_limit, 20)
            self.assertTrue(agent_cfg.inject_followups)
            self.assertTrue(agent_cfg.is_step_mode)
            self.assertTrue(agent_cfg.is_startup_reads)
            self.assertTrue(agent_cfg.edit_delta_output)
            self.assertEqual(agent_cfg.supersede_arg_keep, 1000)

            self.assertEqual(dag_cfg.node_visit_limit, 100)
            self.assertEqual(dag_cfg.batch_size, 1)

    def test_env_var_overrides_and_toml(self) -> None:
        toml_path = os.path.join(self.tmp_config_dir.name, "models.toml")
        with open(toml_path, "w", encoding="utf-8") as f:
            f.write(
                """
[models.custom]
model = "custom-from-toml"
base_url = "http://toml-host:8000/v1"
timeout = 120.0
temperature = 0.2
max_tokens = 4096
conversation_limit = 50
node_visit_limit = 200
batch_size = 5
is_step_mode = false
is_startup_reads = false
edit_delta_output = false
supersede_arg_keep = 500
"""
            )

        os.environ["CLEANROOM_MODEL_CONFIG_FILE"] = toml_path
        os.environ["CLEANROOM_MODEL"] = "custom"

        reg = LifecycleRegistry()
        __initialize__(reg)

        with enter_phase("system", registry=reg) as scope:
            openai_cfg = scope.get_singleton(OpenAIConfig)
            agent_cfg = scope.get_singleton(AgentConfig)
            dag_cfg = scope.get_singleton(DagConfig)

            self.assertEqual(openai_cfg.model_name, "custom-from-toml")
            self.assertEqual(openai_cfg.base_url, "http://toml-host:8000/v1")
            self.assertEqual(openai_cfg.timeout, 120.0)
            self.assertEqual(openai_cfg.temperature, 0.2)
            self.assertEqual(openai_cfg.max_tokens, 4096)

            self.assertEqual(agent_cfg.conversation_limit, 50)
            self.assertFalse(agent_cfg.is_step_mode)
            self.assertFalse(agent_cfg.is_startup_reads)
            self.assertFalse(agent_cfg.edit_delta_output)
            self.assertEqual(agent_cfg.supersede_arg_keep, 500)

            self.assertEqual(dag_cfg.node_visit_limit, 200)
            self.assertEqual(dag_cfg.batch_size, 5)
