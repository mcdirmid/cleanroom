# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 57e3149ecc1c
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Unit tests for uv_model_config_impl aligned with grounding specifications."""

import os
import sys
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.dag.lib.dag_config import DagConfig
from update_with_ai.parts.openai.lib.openai_config import OpenAIConfig
from update_with_ai.parts.uv.lib.uv_model_config_impl import (
    OpenAIConfig as OpenAIConfigImpl,
    AgentConfig as AgentConfigImpl,
    DagConfig as DagConfigImpl,
    __initialize__,
)


class UvModelConfigImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orig_cwd = os.getcwd()
        self.orig_env = dict(os.environ)
        self.orig_argv = list(sys.argv)

    def tearDown(self) -> None:
        os.chdir(self.orig_cwd)
        os.environ.clear()
        os.environ.update(self.orig_env)
        sys.argv = list(self.orig_argv)

    def test_default_configuration(self) -> None:
        """Resolving default model configuration properties when no TOML or env vars exist."""
        for var in [
            "CLEANROOM_MODEL",
            "CLEANROOM_MODEL_CONFIG_FILE",
            "MODEL_CONFIG_TARGET",
            "AGENT_CONFIG_TARGET",
            "OPENAI_MODEL",
            "CLEANROOM_MODEL_NAME",
            "OPENAI_BASE_URL",
            "OPENAI_API_BASE",
            "OPENAI_API_KEY",
            "AGENT_API_KEY",
            "CLEANROOM_TIMEOUT",
            "CLEANROOM_TEMPERATURE",
            "CLEANROOM_MAX_TOKENS",
            "CLEANROOM_CONVERSATION_LIMIT",
            "CLEANROOM_NODE_VISIT_LIMIT",
            "CLEANROOM_BATCH_SIZE",
        ]:
            os.environ.pop(var, None)
        sys.argv = ["cleanroom-loop"]

        # Ensure no accidental TOML file is read by pointing to nonexistent file
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
            self.assertFalse(agent_cfg.is_step_mode)
            self.assertTrue(agent_cfg.is_startup_reads)
            self.assertTrue(agent_cfg.edit_delta_output)
            self.assertEqual(agent_cfg.supersede_arg_keep, 1000)

            self.assertEqual(dag_cfg.node_visit_limit, 100)
            self.assertEqual(dag_cfg.batch_size, 1)

    def test_environment_variable_overrides(self) -> None:
        """Overriding configuration parameters via direct ambient environment variables."""
        os.environ["CLEANROOM_MODEL_CONFIG_FILE"] = "/tmp/nonexistent_models_12345.toml"
        os.environ["OPENAI_MODEL"] = "custom-test-model"
        os.environ["OPENAI_BASE_URL"] = "http://localhost:9999/v1"
        os.environ["OPENAI_API_KEY"] = "sk-custom-secret"
        os.environ["CLEANROOM_TIMEOUT"] = "45.5"
        os.environ["CLEANROOM_TEMPERATURE"] = "0.2"
        os.environ["CLEANROOM_MAX_TOKENS"] = "2048"
        os.environ["CLEANROOM_CONVERSATION_LIMIT"] = "15"
        os.environ["CLEANROOM_NODE_VISIT_LIMIT"] = "50"
        os.environ["CLEANROOM_BATCH_SIZE"] = "3"

        reg = LifecycleRegistry()
        __initialize__(reg)

        with enter_phase("system", registry=reg) as scope:
            openai_cfg = scope.get_singleton(OpenAIConfig)
            agent_cfg = scope.get_singleton(AgentConfig)
            dag_cfg = scope.get_singleton(DagConfig)

            self.assertEqual(openai_cfg.model_name, "custom-test-model")
            self.assertEqual(openai_cfg.base_url, "http://localhost:9999/v1")
            self.assertEqual(openai_cfg.api_key, "sk-custom-secret")
            self.assertEqual(openai_cfg.timeout, 45.5)
            self.assertEqual(openai_cfg.temperature, 0.2)
            self.assertEqual(openai_cfg.max_tokens, 2048)

            self.assertEqual(agent_cfg.conversation_limit, 15)
            self.assertEqual(dag_cfg.node_visit_limit, 50)
            self.assertEqual(dag_cfg.batch_size, 3)

    def test_load_from_toml_file(self) -> None:
        """Loading named model configurations from a TOML configuration file."""
        toml_content = """
default = "my-test-model"

[models.my-test-model]
model = "Qwen-Test-35B"
base_url = "http://localhost:8000/v1"
timeout_seconds = 120.0
temperature = 0.5
max_tokens = 8192
max_iterations = 60
node_visit_limit = 200
batch_size = 2
api_key_env = "SPECIAL_API_KEY"

[models.fallback-model]
model = "Fallback-Model-7B"
timeout = 30.0
temperature = 0.0
conversation_limit = 10
"""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            os.environ["CLEANROOM_MODEL_CONFIG_FILE"] = temp_path
            os.environ["SPECIAL_API_KEY"] = "special-secret-key"

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                openai_cfg = scope.get_singleton(OpenAIConfig)
                agent_cfg = scope.get_singleton(AgentConfig)
                dag_cfg = scope.get_singleton(DagConfig)

                self.assertEqual(openai_cfg.model_name, "Qwen-Test-35B")
                self.assertEqual(openai_cfg.base_url, "http://localhost:8000/v1")
                self.assertEqual(openai_cfg.api_key, "special-secret-key")
                self.assertEqual(openai_cfg.timeout, 120.0)
                self.assertEqual(openai_cfg.temperature, 0.5)
                self.assertEqual(openai_cfg.max_tokens, 8192)

                self.assertEqual(agent_cfg.conversation_limit, 60)
                self.assertEqual(dag_cfg.node_visit_limit, 200)
                self.assertEqual(dag_cfg.batch_size, 2)
        finally:
            os.unlink(temp_path)

    def test_cli_and_cleanroom_model_selection(self) -> None:
        """Selecting model configuration via --config flag or CLEANROOM_MODEL."""
        toml_content = """
default = "first"

[models.first]
model = "model-one"

[models.second]
model = "model-two"
"""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            os.environ["CLEANROOM_MODEL_CONFIG_FILE"] = temp_path
            sys.argv = ["cleanroom-loop", "--config", "second"]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                openai_cfg = scope.get_singleton(OpenAIConfig)
                self.assertEqual(openai_cfg.model_name, "model-two")

            # Now test CLEANROOM_MODEL env var
            sys.argv = ["cleanroom-loop"]
            os.environ["CLEANROOM_MODEL"] = "first"

            reg2 = LifecycleRegistry()
            __initialize__(reg2)
            with enter_phase("system", registry=reg2) as scope2:
                openai_cfg2 = scope2.get_singleton(OpenAIConfig)
                self.assertEqual(openai_cfg2.model_name, "model-one")

            # Test MODEL_CONFIG_TARGET with bazel style label //model_configs:second
            os.environ.pop("CLEANROOM_MODEL", None)
            os.environ["MODEL_CONFIG_TARGET"] = "//model_configs:second"

            reg3 = LifecycleRegistry()
            __initialize__(reg3)
            with enter_phase("system", registry=reg3) as scope3:
                openai_cfg3 = scope3.get_singleton(OpenAIConfig)
                self.assertEqual(openai_cfg3.model_name, "model-two")

            # Test --config=name syntax and //slash target syntax
            sys.argv = ["cleanroom-loop", "--config=second"]
            reg4 = LifecycleRegistry()
            __initialize__(reg4)
            with enter_phase("system", registry=reg4) as scope4:
                openai_cfg4 = scope4.get_singleton(OpenAIConfig)
                self.assertEqual(openai_cfg4.model_name, "model-two")

            sys.argv = ["cleanroom-loop"]
            os.environ["MODEL_CONFIG_TARGET"] = "//second"
            reg5 = LifecycleRegistry()
            __initialize__(reg5)
            with enter_phase("system", registry=reg5) as scope5:
                openai_cfg5 = scope5.get_singleton(OpenAIConfig)
                self.assertEqual(openai_cfg5.model_name, "model-two")
        finally:
            os.unlink(temp_path)

    def test_top_level_table_and_alternate_keys(self) -> None:
        """Loading configuration from top-level tables and alternate field names."""
        toml_content = """
[standalone]
model_name = "standalone-model"
api_base = "http://localhost:5555/v1"
timeout = 25.0
temperature = 0.3
conversation_limit = 8
api_key = "direct-key"
"""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            os.environ["CLEANROOM_MODEL_CONFIG_FILE"] = temp_path
            os.environ.pop("OPENAI_MODEL", None)
            os.environ.pop("OPENAI_BASE_URL", None)
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("AGENT_API_KEY", None)
            sys.argv = ["cleanroom-loop", "--config", "standalone"]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                openai_cfg = scope.get_singleton(OpenAIConfig)
                agent_cfg = scope.get_singleton(AgentConfig)

                self.assertEqual(openai_cfg.model_name, "standalone-model")
                self.assertEqual(openai_cfg.base_url, "http://localhost:5555/v1")
                self.assertEqual(openai_cfg.api_key, "direct-key")
                self.assertEqual(openai_cfg.timeout, 25.0)
                self.assertEqual(openai_cfg.temperature, 0.3)
                self.assertEqual(agent_cfg.conversation_limit, 8)
        finally:
            os.unlink(temp_path)

    def test_workspace_model_configs_toml_discovery(self) -> None:
        """Discovering workspace model_configs.toml naturally without explicit path env var."""
        with tempfile.TemporaryDirectory() as tmp_root:
            with open(os.path.join(tmp_root, "model_configs.toml"), "w") as f:
                f.write('default = "workspace-model"\n[models.workspace-model]\nmodel = "Discovered-Model"\n')
            os.chdir(tmp_root)
            os.environ.pop("CLEANROOM_MODEL_CONFIG_FILE", None)
            os.environ.pop("CLEANROOM_MODEL", None)
            os.environ.pop("MODEL_CONFIG_TARGET", None)
            os.environ.pop("AGENT_CONFIG_TARGET", None)
            os.environ.pop("OPENAI_MODEL", None)
            sys.argv = ["cleanroom-loop"]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                openai_cfg = scope.get_singleton(OpenAIConfig)
                self.assertEqual(openai_cfg.model_name, "Discovered-Model")

    def test_parent_directory_discovery(self) -> None:
        """Discovering model_configs.toml by walking up parent directories."""
        with tempfile.TemporaryDirectory() as tmp_root:
            with open(os.path.join(tmp_root, "model_configs.toml"), "w") as f:
                f.write('default = "parent-model"\n[models.parent-model]\nmodel = "Parent-Discovered-Model"\n')
            sub_dir = os.path.join(tmp_root, "a", "b", "c")
            os.makedirs(sub_dir)
            os.chdir(sub_dir)
            os.environ.pop("CLEANROOM_MODEL_CONFIG_FILE", None)
            os.environ.pop("CLEANROOM_MODEL", None)
            os.environ.pop("MODEL_CONFIG_TARGET", None)
            os.environ.pop("OPENAI_MODEL", None)
            sys.argv = ["cleanroom-loop"]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                openai_cfg = scope.get_singleton(OpenAIConfig)
                self.assertEqual(openai_cfg.model_name, "Parent-Discovered-Model")


    def test_home_directory_discovery(self) -> None:
        """Discovering models.toml under ~/.cleanroom when repo config is absent."""
        with tempfile.TemporaryDirectory() as tmp_home:
            cleanroom_dir = os.path.join(tmp_home, ".cleanroom")
            os.makedirs(cleanroom_dir, exist_ok=True)
            with open(os.path.join(cleanroom_dir, "models.toml"), "w") as f:
                f.write('default = "home-model"\n[models.home-model]\nmodel = "Home-Qwen-Model"\n')

            with tempfile.TemporaryDirectory() as empty_dir:
                os.chdir(empty_dir)
                os.environ["HOME"] = tmp_home
                os.environ.pop("CLEANROOM_MODEL_CONFIG_FILE", None)
                os.environ.pop("CLEANROOM_MODEL", None)
                os.environ.pop("MODEL_CONFIG_TARGET", None)
                os.environ.pop("OPENAI_MODEL", None)
                sys.argv = ["cleanroom-loop"]

                reg = LifecycleRegistry()
                __initialize__(reg)

                with enter_phase("system", registry=reg) as scope:
                    openai_cfg = scope.get_singleton(OpenAIConfig)
                    self.assertEqual(openai_cfg.model_name, "Home-Qwen-Model")

    def test_cleanroom_toml_discovery(self) -> None:
        """Discovering config in cleanroom.toml only if it contains models or default."""
        with tempfile.TemporaryDirectory() as tmp_root:
            cleanroom_toml = os.path.join(tmp_root, "cleanroom.toml")
            with open(cleanroom_toml, "w") as f:
                f.write('project = "other"\n')
            os.chdir(tmp_root)
            os.environ.pop("CLEANROOM_MODEL_CONFIG_FILE", None)
            os.environ.pop("CLEANROOM_MODEL", None)
            os.environ.pop("MODEL_CONFIG_TARGET", None)
            os.environ.pop("OPENAI_MODEL", None)
            sys.argv = ["cleanroom-loop"]

            reg = LifecycleRegistry()
            __initialize__(reg)
            with enter_phase("system", registry=reg) as scope:
                openai_cfg = scope.get_singleton(OpenAIConfig)
                self.assertEqual(openai_cfg.model_name, "gpt-4o")

            with open(cleanroom_toml, "w") as f:
                f.write('default = "cr-model"\n[models.cr-model]\nmodel = "Cleanroom-Config-Model"\n')

            reg2 = LifecycleRegistry()
            __initialize__(reg2)
            with enter_phase("system", registry=reg2) as scope2:
                openai_cfg2 = scope2.get_singleton(OpenAIConfig)
                self.assertEqual(openai_cfg2.model_name, "Cleanroom-Config-Model")




if __name__ == "__main__":
    unittest.main()
