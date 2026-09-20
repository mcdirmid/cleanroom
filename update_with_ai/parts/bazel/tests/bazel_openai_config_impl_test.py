"""Unit tests for bazel_openai_config_impl aligned with grounding specifications."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.dag.lib.dag_config import DagConfig
from update_with_ai.parts.openai.lib.openai_config import OpenaiConfig
from update_with_ai.parts.bazel.lib.bazel_openai_config_impl import (
    OpenaiConfig as OpenaiConfigImpl,
    ModelConfig as ModelConfigImpl,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


class BazelOpenaiConfigImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orig_env = dict(os.environ)
        self.orig_argv = list(sys.argv)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.orig_env)
        sys.argv = list(self.orig_argv)

    def test_default_configuration(self) -> None:
        """CUJ: Resolving default model configuration properties from ambient environment."""
        for var in [
            "MODEL_CONFIG_TARGET",
            "AGENT_CONFIG_TARGET",
            "OPENAI_MODEL",
            "OPENAI_BASE_URL",
            "OPENAI_API_KEY",
            "AGENT_API_KEY",
            "MODEL_TIMEOUT",
            "MODEL_CONVERSATION_LIMIT",
            "STEP_MODE",
            "STARTUP_READS",
            "INJECT_FOLLOWUPS",
            "MCP_MODE",
            "RUNFILES_DIR",
            "BAZEL_RUNFILES",
            "BUILD_WORKSPACE_DIRECTORY",
        ]:
            os.environ.pop(var, None)
        sys.argv = ["script.py"]

        reg = LifecycleRegistry()
        __initialize__(reg)

        with enter_phase("system", registry=reg) as scope:
            cfg = scope.get_singleton(ModelConfigImpl)
            openai_cfg = scope.get_singleton(OpenaiConfig)
            agent_cfg = scope.get_singleton(AgentConfig)
            dag_cfg = scope.get_singleton(DagConfig)

            # Requirement: The openai config, agent config, and dag config resolve the target configuration from the MODEL_CONFIG_TARGET environment variable, the AGENT_CONFIG_TARGET environment variable, or the --config command-line argument, defaulting to the standard //model_configs:default target.
            # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
            self.assertEqual(openai_cfg.model_name, "gpt-4o")
            self.assertEqual(cfg.model_name, "gpt-4o")
            # Requirement: [OpenaiConfig] The openai config provides a base url designating the remote model API endpoint address when custom endpoint routing applies.
            self.assertIsNone(openai_cfg.base_url)
            self.assertIsNone(cfg.base_url)
            # Requirement: [OpenaiConfig] The openai config provides an api key providing authentication credentials when designated environment secrets apply.
            self.assertIsNone(openai_cfg.api_key)
            self.assertIsNone(cfg.api_key)
            # Requirement: [OpenaiConfig] The openai config provides a timeout specifying the maximum duration in seconds permitted for a model request.
            self.assertEqual(openai_cfg.timeout, 60)
            self.assertEqual(cfg.timeout, 60)
            # Requirement: [AgentConfig] The agent config provides the conversation limit bounding interaction turns.
            self.assertEqual(agent_cfg.conversation_limit, 20)
            self.assertEqual(cfg.conversation_limit, 20)
            # Requirement: [AgentConfig] The agent config provides whether the agent should use step mode to communicate a guide progressively.
            self.assertTrue(agent_cfg.is_step_mode)
            self.assertTrue(cfg.is_step_mode)
            # Requirement: [AgentConfig] The agent config provides whether the agent should perform startup reads to inspect declared files at session start.
            self.assertTrue(agent_cfg.is_startup_reads)
            self.assertTrue(cfg.is_startup_reads)
            # Requirement: [AgentConfig] The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.
            self.assertTrue(agent_cfg.inject_followups)
            self.assertTrue(cfg.inject_followups)
            # Requirement: [AgentConfig] The agent config provides whether editing tools should produce delta output.
            self.assertFalse(agent_cfg.edit_delta_output)
            self.assertFalse(cfg.edit_delta_output)
            # Requirement: [AgentConfig] The agent config provides whether the agent should operate in mcp mode.
            self.assertFalse(agent_cfg.is_mcp_mode)
            self.assertFalse(cfg.is_mcp_mode)
            # Requirement: [OpenaiConfig] The openai config provides a temperature specifying the sampling temperature for model requests.
            self.assertEqual(openai_cfg.temperature, 0.0)
            self.assertEqual(cfg.temperature, 0.0)
            # Requirement: [OpenaiConfig] The openai config provides a max tokens upper bound specifying the maximum number of response tokens permitted per request when token generation is constrained.
            self.assertIsNone(openai_cfg.max_tokens)
            self.assertIsNone(cfg.max_tokens)
            # Requirement: [DagConfig] The dag config provides the node visit limit bounding node visits during graph cleaning.
            self.assertEqual(dag_cfg.node_visit_limit, 500)
            self.assertEqual(cfg.node_visit_limit, 500)
            # Requirement: [DagConfig] The dag config provides the batch size bounding dirty nodes processed together in an agent session.
            self.assertEqual(dag_cfg.batch_size, 1)
            self.assertEqual(cfg.batch_size, 1)

    def test_environment_overrides(self) -> None:
        """CUJ: Overriding configuration via explicit ambient environment variables."""
        for var in [
            "MODEL_CONFIG_TARGET",
            "AGENT_CONFIG_TARGET",
            "RUNFILES_DIR",
            "BAZEL_RUNFILES",
        ]:
            os.environ.pop(var, None)
        os.environ["OPENAI_MODEL"] = "custom-model"
        os.environ["OPENAI_BASE_URL"] = "http://localhost:8000/v1"
        os.environ["OPENAI_API_KEY"] = "secret-key-123"
        os.environ["MODEL_TIMEOUT"] = "120"
        os.environ["MODEL_CONVERSATION_LIMIT"] = "15"
        os.environ["MODEL_TEMPERATURE"] = "0.7"
        os.environ["MODEL_MAX_TOKENS"] = "4096"
        os.environ["STEP_MODE"] = "false"
        os.environ["STARTUP_READS"] = "0"
        os.environ["INJECT_FOLLOWUPS"] = "false"
        os.environ["EDIT_DELTA_OUTPUT"] = "true"
        os.environ["MCP_MODE"] = "true"
        os.environ["NODE_VISIT_LIMIT"] = "42"
        os.environ["BATCH_SIZE"] = "3"
        sys.argv = ["script.py"]

        reg = LifecycleRegistry()
        __initialize__(reg)

        with enter_phase("system", registry=reg) as scope:
            cfg = scope.get_singleton(ModelConfigImpl)
            # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
            self.assertEqual(cfg.model_name, "custom-model")
            # Requirement: [OpenaiConfig] The openai config provides a base url designating the remote model API endpoint address when custom endpoint routing applies.
            self.assertEqual(cfg.base_url, "http://localhost:8000/v1")
            # Requirement: [OpenaiConfig] The openai config provides an api key providing authentication credentials when designated environment secrets apply.
            self.assertEqual(cfg.api_key, "secret-key-123")
            # Requirement: [OpenaiConfig] The openai config provides a timeout specifying the maximum duration in seconds permitted for a model request.
            self.assertEqual(cfg.timeout, 120)
            # Requirement: [AgentConfig] The agent config provides the conversation limit bounding interaction turns.
            self.assertEqual(cfg.conversation_limit, 15)
            # Requirement: [OpenaiConfig] The openai config provides a temperature specifying the sampling temperature for model requests.
            self.assertEqual(cfg.temperature, 0.7)
            # Requirement: [OpenaiConfig] The openai config provides a max tokens upper bound specifying the maximum number of response tokens permitted per request when token generation is constrained.
            self.assertEqual(cfg.max_tokens, 4096)
            # Requirement: [AgentConfig] The agent config provides whether the agent should use step mode to communicate a guide progressively.
            self.assertFalse(cfg.is_step_mode)
            # Requirement: [AgentConfig] The agent config provides whether the agent should perform startup reads to inspect declared files at session start.
            self.assertFalse(cfg.is_startup_reads)
            # Requirement: [AgentConfig] The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.
            self.assertFalse(cfg.inject_followups)
            # Requirement: [AgentConfig] The agent config provides whether editing tools should produce delta output.
            self.assertTrue(cfg.edit_delta_output)
            # Requirement: [AgentConfig] The agent config provides whether the agent should operate in mcp mode.
            self.assertTrue(cfg.is_mcp_mode)
            # Requirement: [DagConfig] The dag config provides the node visit limit bounding node visits during graph cleaning.
            self.assertEqual(cfg.node_visit_limit, 42)
            # Requirement: [DagConfig] The dag config provides the batch size bounding dirty nodes processed together in an agent session.
            self.assertEqual(cfg.batch_size, 3)

    def test_target_module_resolution_model_config_target(self) -> None:
        """CUJ: Resolving configuration from target module file via MODEL_CONFIG_TARGET."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = os.path.join(tmpdir, "model_configs")
            os.makedirs(pkg_dir)
            cfg_file = os.path.join(pkg_dir, "custom_config.json")
            data = {
                "model": "qwen-35b",
                "base_url": "http://localhost:8000/v1",
                "api_key_env": "CUSTOM_KEY_ENV",
                "timeout": 100.0,
                "max_iterations": 45,
                "temperature": 0.7,
                "max_tokens": 4096,
                "do_step_mode": False,
                "session_start_reads": False,
                "inject_followups": False,
                "edit_delta_output": True,
                "mcp_mode": True,
                "node_visit_limit": 450,
                "batch_size": 4,
            }
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            os.environ["RUNFILES_DIR"] = tmpdir
            os.environ["MODEL_CONFIG_TARGET"] = "//model_configs:custom"
            os.environ["CUSTOM_KEY_ENV"] = "target-key-999"

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                cfg = scope.get_singleton(ModelConfigImpl)
                # Requirement: The openai config, agent config, and dag config load execution parameters and authentication credentials for language model agent runs from the target module.
                # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
                self.assertEqual(cfg.model_name, "qwen-35b")
                # Requirement: [OpenaiConfig] The openai config provides a base url designating the remote model API endpoint address when custom endpoint routing applies.
                self.assertEqual(cfg.base_url, "http://localhost:8000/v1")
                # Requirement: [OpenaiConfig] The openai config provides an api key providing authentication credentials when designated environment secrets apply.
                self.assertEqual(cfg.api_key, "target-key-999")
                # Requirement: [OpenaiConfig] The openai config provides a timeout specifying the maximum duration in seconds permitted for a model request.
                self.assertEqual(cfg.timeout, 100)
                # Requirement: [AgentConfig] The agent config provides the conversation limit bounding interaction turns.
                self.assertEqual(cfg.conversation_limit, 45)
                # Requirement: [OpenaiConfig] The openai config provides a temperature specifying the sampling temperature for model requests.
                self.assertEqual(cfg.temperature, 0.7)
                # Requirement: [OpenaiConfig] The openai config provides a max tokens upper bound specifying the maximum number of response tokens permitted per request when token generation is constrained.
                self.assertEqual(cfg.max_tokens, 4096)
                # Requirement: [AgentConfig] The agent config provides whether the agent should use step mode to communicate a guide progressively.
                self.assertFalse(cfg.is_step_mode)
                # Requirement: [AgentConfig] The agent config provides whether the agent should perform startup reads to inspect declared files at session start.
                self.assertFalse(cfg.is_startup_reads)
                # Requirement: [AgentConfig] The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.
                self.assertFalse(cfg.inject_followups)
                # Requirement: [AgentConfig] The agent config provides whether editing tools should produce delta output.
                self.assertTrue(cfg.edit_delta_output)
                # Requirement: [AgentConfig] The agent config provides whether the agent should operate in mcp mode.
                self.assertTrue(cfg.is_mcp_mode)
                # Requirement: [DagConfig] The dag config provides the node visit limit bounding node visits during graph cleaning.
                self.assertEqual(cfg.node_visit_limit, 450)
                # Requirement: [DagConfig] The dag config provides the batch size bounding dirty nodes processed together in an agent session.
                self.assertEqual(cfg.batch_size, 4)

    def test_target_module_resolution_agent_config_target(self) -> None:
        """CUJ: Resolving configuration from target module file via AGENT_CONFIG_TARGET."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = os.path.join(tmpdir, "_main", "model_configs")
            os.makedirs(pkg_dir)
            cfg_file = os.path.join(pkg_dir, "legacy_config.json")
            data = {
                "model": "legacy-model",
                "base_url": "http://localhost:8001/v1",
                "api_key_env": "",
                "timeout": 75.0,
                "max_iterations": 30,
                "step_sections": True,
                "session_start_reads": True,
            }
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            os.environ.pop("MODEL_CONFIG_TARGET", None)
            os.environ["AGENT_CONFIG_TARGET"] = "//model_configs:legacy"
            os.environ["BAZEL_RUNFILES"] = tmpdir
            os.environ["AGENT_API_KEY"] = "agent-api-key-val"

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                cfg = scope.get_singleton(ModelConfigImpl)
                # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
                self.assertEqual(cfg.model_name, "legacy-model")
                # Requirement: [OpenaiConfig] The openai config provides a base url designating the remote model API endpoint address when custom endpoint routing applies.
                self.assertEqual(cfg.base_url, "http://localhost:8001/v1")
                # Requirement: [OpenaiConfig] The openai config provides an api key providing authentication credentials when designated environment secrets apply.
                self.assertEqual(cfg.api_key, "agent-api-key-val")
                # Requirement: [OpenaiConfig] The openai config provides a timeout specifying the maximum duration in seconds permitted for a model request.
                self.assertEqual(cfg.timeout, 75)
                # Requirement: [AgentConfig] The agent config provides the conversation limit bounding interaction turns.
                self.assertEqual(cfg.conversation_limit, 30)
                # Requirement: [AgentConfig] The agent config provides whether the agent should use step mode to communicate a guide progressively.
                self.assertTrue(cfg.is_step_mode)
                # Requirement: [AgentConfig] The agent config provides whether the agent should perform startup reads to inspect declared files at session start.
                self.assertTrue(cfg.is_startup_reads)
                # Requirement: [AgentConfig] The agent config provides whether editing tools should produce delta output.
                self.assertFalse(cfg.edit_delta_output)

    def test_target_module_resolution_cli_args(self) -> None:
        """CUJ: Resolving configuration from target module via --config and --config= CLI args."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_dir = os.path.join(tmpdir, "ws")
            bin_dir = os.path.join(ws_dir, "bazel-bin", "model_configs")
            os.makedirs(bin_dir)
            cfg_file = os.path.join(bin_dir, "cli-target_config.json")
            data = {
                "model": "cli-model",
                "base_url": "http://localhost:8002/v1",
                "timeout": 45,
                "max_iterations": 10,
            }
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            os.environ.pop("MODEL_CONFIG_TARGET", None)
            os.environ.pop("AGENT_CONFIG_TARGET", None)
            os.environ.pop("RUNFILES_DIR", None)
            os.environ.pop("BAZEL_RUNFILES", None)
            os.environ["BUILD_WORKSPACE_DIRECTORY"] = ws_dir

            # Test --config <label>
            sys.argv = ["prog", "--config", "//model_configs:cli-target"]
            reg = LifecycleRegistry()
            __initialize__(reg)
            with enter_phase("system", registry=reg) as scope:
                cfg = scope.get_singleton(ModelConfigImpl)
                # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
                self.assertEqual(cfg.model_name, "cli-model")
                # Requirement: [OpenaiConfig] The openai config provides a base url designating the remote model API endpoint address when custom endpoint routing applies.
                self.assertEqual(cfg.base_url, "http://localhost:8002/v1")

            # Test --config=<label>
            sys.argv = ["prog", "--config=//model_configs:cli-target"]
            reg2 = LifecycleRegistry()
            __initialize__(reg2)
            with enter_phase("system", registry=reg2) as scope:
                cfg2 = scope.get_singleton(ModelConfigImpl)
                # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
                self.assertEqual(cfg2.model_name, "cli-model")

    def test_target_label_syntax_variants(self) -> None:
        """CUJ: Parsing various Bazel label syntax variants (@@//, @//, @pkg:name, :name, shorthand)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = os.path.join(tmpdir, "model_configs")
            os.makedirs(pkg_dir)
            cfg_file = os.path.join(pkg_dir, "variant_config.json")
            data = {"model": "variant-model", "base_url": "http://variant:8000/v1"}
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            os.environ["RUNFILES_DIR"] = tmpdir
            os.environ.pop("MODEL_CONFIG_TARGET", None)
            os.environ.pop("AGENT_CONFIG_TARGET", None)

            # @@//model_configs:variant
            with patch(
                "update_with_ai.parts.bazel.lib.bazel_openai_config_impl.sys.argv",
                ["prog", "--config", "@@//model_configs:variant"],
            ):
                reg = LifecycleRegistry()
                __initialize__(reg)
                with enter_phase("system", registry=reg) as scope:
                    cfg = scope.get_singleton(ModelConfigImpl)
                    # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
                    self.assertEqual(cfg.model_name, "variant-model")

            # @//model_configs:variant
            with patch(
                "update_with_ai.parts.bazel.lib.bazel_openai_config_impl.sys.argv",
                ["prog", "--config", "@//model_configs:variant"],
            ):
                reg = LifecycleRegistry()
                __initialize__(reg)
                with enter_phase("system", registry=reg) as scope:
                    cfg = scope.get_singleton(ModelConfigImpl)
                    # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
                    self.assertEqual(cfg.model_name, "variant-model")

            # @model_configs:variant
            with patch(
                "update_with_ai.parts.bazel.lib.bazel_openai_config_impl.sys.argv",
                ["prog", "--config", "@model_configs:variant"],
            ):
                reg = LifecycleRegistry()
                __initialize__(reg)
                with enter_phase("system", registry=reg) as scope:
                    cfg = scope.get_singleton(ModelConfigImpl)
                    # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
                    self.assertEqual(cfg.model_name, "variant-model")

            # :variant
            with patch(
                "update_with_ai.parts.bazel.lib.bazel_openai_config_impl.sys.argv",
                ["prog", "--config", ":variant"],
            ):
                reg = LifecycleRegistry()
                __initialize__(reg)
                with enter_phase("system", registry=reg) as scope:
                    cfg = scope.get_singleton(ModelConfigImpl)
                    # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
                    self.assertEqual(cfg.model_name, "variant-model")

            # Shorthand //model_configs/variant
            with patch(
                "update_with_ai.parts.bazel.lib.bazel_openai_config_impl.sys.argv",
                ["prog", "--config", "//model_configs/variant"],
            ):
                reg = LifecycleRegistry()
                __initialize__(reg)
                with enter_phase("system", registry=reg) as scope:
                    cfg = scope.get_singleton(ModelConfigImpl)
                    # Requirement: [OpenaiConfig] The openai config provides a model name designating the target model.
                    self.assertEqual(cfg.model_name, "variant-model")


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
