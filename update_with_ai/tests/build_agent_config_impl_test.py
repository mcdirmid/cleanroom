"""Tests for build_agent_config_impl derived from LLS."""

import unittest
from lib.build_agent_config import AgentConfig
from lib.build_agent_config_impl import BuildAgentConfigResolverImpl


class BuildAgentConfigImplTest(unittest.TestCase):
    def test_agent_config_dataclass_defaults(self) -> None:
        """Tests Data Types: AgentConfig dataclass defaults and field types."""
        cfg = AgentConfig(
            model="test-model",
            base_url="https://api.example.com",
            iteration_limit=10,
        )
        self.assertEqual(cfg.model, "test-model")
        self.assertEqual(cfg.base_url, "https://api.example.com")
        self.assertEqual(cfg.iteration_limit, 10)
        self.assertEqual(cfg.temperature, 0.0)
        self.assertEqual(cfg.timeout_seconds, 60)
        self.assertIsNone(cfg.api_key_env_var)

    def test_resolve_default_config_without_target(self) -> None:
        """Tests CUJ for resolving configuration from system/workspace defaults when target is None.

        Checks postconditions: returns AgentConfig with default model, base_url, and positive iteration_limit.
        """
        resolver = BuildAgentConfigResolverImpl()
        config = resolver.resolve_config(None)
        self.assertIsInstance(config, AgentConfig)
        self.assertTrue(len(config.model) > 0)
        self.assertTrue(config.base_url.startswith("https://"))
        self.assertGreater(config.iteration_limit, 0)
        self.assertIsNotNone(config.api_key_env_var)

    def test_resolve_target_binds_gemini_credentials(self) -> None:
        """Tests CUJ for resolving agent config with Gemini process environment binding.

        Checks postconditions: returns AgentConfig with model name, base_url, iteration_limit, and GEMINI_API_KEY env binding.
        """
        resolver = BuildAgentConfigResolverImpl()
        config = resolver.resolve_config("//agent_configs:gemini-2.5-flash")
        self.assertIsInstance(config, AgentConfig)
        self.assertEqual(config.model, "gemini-2.5-flash")
        self.assertTrue(config.base_url.startswith("https://"))
        self.assertGreater(config.iteration_limit, 0)
        self.assertEqual(config.api_key_env_var, "GEMINI_API_KEY")

    def test_resolve_openai_target_binds_openai_credentials(self) -> None:
        """Tests CUJ for resolving OpenAI target configuration binding OPENAI_API_KEY.

        Checks postconditions: returns AgentConfig with OpenAI model and OPENAI_API_KEY binding.
        """
        resolver = BuildAgentConfigResolverImpl()
        config = resolver.resolve_config("//agent_configs:gpt-4o")
        self.assertIsInstance(config, AgentConfig)
        self.assertEqual(config.model, "gpt-4o")
        self.assertEqual(config.api_key_env_var, "OPENAI_API_KEY")


if __name__ == "__main__":
    unittest.main()
