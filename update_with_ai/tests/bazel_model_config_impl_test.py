"""Unit tests for bazel_model_config_impl aligned with grounding specifications."""

import os
import unittest
from lib.bazel_model_config_impl import (
    ModelConfig as ModelConfigImpl,
    __initialize__,
)
from lib.lifecycle import LifecycleRegistry, enter_phase
from lib.model_config import ModelConfig


class BazelModelConfigImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orig_env = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_default_configuration(self) -> None:
        """CUJ: Resolving default model configuration properties from ambient environment."""
        for var in [
            "OPENAI_MODEL",
            "OPENAI_BASE_URL",
            "OPENAI_API_KEY",
            "MODEL_TIMEOUT",
            "MODEL_CONVERSATION_LIMIT",
            "STEP_MODE",
            "STARTUP_READS",
        ]:
            os.environ.pop(var, None)

        reg = LifecycleRegistry()
        __initialize__(reg)

        with enter_phase("system", registry=reg) as scope:
            cfg = scope.get_singleton(ModelConfig)
            # Requirement: The model config provides the model name resolved from the target module.
            # Requirement: [ModelConfig] The model config provides a model name designating the target model.
            self.assertEqual(cfg.model_name, "gpt-4o")
            # Requirement: The model config provides the base url resolved from the target module.
            # Requirement: [ModelConfig] The model config provides a base url designating the remote model API endpoint address, or absent if default address resolution applies.
            self.assertIsNone(cfg.base_url)
            # Requirement: The model config reads authentication credentials from the designated environment variable specified in the target module.
            # Requirement: [ModelConfig] The model config provides an api key providing authentication credentials, or absent if ambient environment credentials apply.
            self.assertIsNone(cfg.api_key)
            # Requirement: The model config provides the timeout resolved from the target module.
            # Requirement: [ModelConfig] The model config provides a timeout specifying the maximum duration in seconds permitted for a model request.
            self.assertEqual(cfg.timeout, 60)
            # Requirement: The model config provides the conversation limit resolved from the target module.
            # Requirement: [ModelConfig] The model config provides the conversation limit bounding interaction turns.
            self.assertEqual(cfg.conversation_limit, 20)
            # Requirement: The model config provides whether the agent should use step mode to communicate a guide progressively from the target module.
            # Requirement: [ModelConfig] The model config provides whether the agent should use step mode to communicate a guide progressively.
            self.assertTrue(cfg.is_step_mode)
            # Requirement: The model config provides whether the agent should perform startup reads to inspect declared files at session start from the target module.
            # Requirement: [ModelConfig] The model config provides whether the agent should perform startup reads to inspect declared files at session start.
            self.assertTrue(cfg.is_startup_reads)

    def test_environment_overrides(self) -> None:
        """CUJ: Overriding configuration via explicit environment variables."""
        os.environ["OPENAI_MODEL"] = "custom-model"
        os.environ["OPENAI_BASE_URL"] = "http://localhost:8000/v1"
        os.environ["OPENAI_API_KEY"] = "secret-key-123"
        os.environ["MODEL_TIMEOUT"] = "120"
        os.environ["MODEL_CONVERSATION_LIMIT"] = "15"
        os.environ["STEP_MODE"] = "false"
        os.environ["STARTUP_READS"] = "0"

        reg = LifecycleRegistry()
        __initialize__(reg)

        with enter_phase("system", registry=reg) as scope:
            cfg = scope.get_singleton(ModelConfig)
            # Requirement: The model config provides the model name resolved from the target module.
            self.assertEqual(cfg.model_name, "custom-model")
            # Requirement: The model config provides the base url resolved from the target module.
            self.assertEqual(cfg.base_url, "http://localhost:8000/v1")
            # Requirement: The model config reads authentication credentials from the designated environment variable specified in the target module.
            self.assertEqual(cfg.api_key, "secret-key-123")
            # Requirement: The model config provides the timeout resolved from the target module.
            self.assertEqual(cfg.timeout, 120)
            # Requirement: The model config provides the conversation limit resolved from the target module.
            self.assertEqual(cfg.conversation_limit, 15)
            # Requirement: The model config provides whether the agent should use step mode to communicate a guide progressively from the target module.
            self.assertFalse(cfg.is_step_mode)
            # Requirement: The model config provides whether the agent should perform startup reads to inspect declared files at session start from the target module.
            self.assertFalse(cfg.is_startup_reads)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None

