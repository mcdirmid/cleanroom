"""Unit tests for model_config_impl aligned with grounding specifications."""

import os
import sys
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, LifecycleTestCase, enter_phase
from support.lib import app_info
from autofab.parts.agent.lib.agent_config import AgentConfig
from autofab.parts.dag.lib.dag_config import DagConfig
from autofab.parts.uv.lib.model_config_impl import (
    AgentConfig as AgentConfigImpl,
    DagConfig as DagConfigImpl,
    __initialize__,
)


class UvModelConfigImplTest(LifecycleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.orig_cwd = os.getcwd()
        self.orig_env = dict(os.environ)
        self.orig_argv = list(sys.argv)
        self.tmp_config_dir = tempfile.TemporaryDirectory()
        os.environ[f"{app_info.ENV_PREFIX}_CONFIG_DIR"] = self.tmp_config_dir.name

    def tearDown(self) -> None:
        os.chdir(self.orig_cwd)
        os.environ.clear()
        os.environ.update(self.orig_env)
        sys.argv = list(self.orig_argv)
        self.tmp_config_dir.cleanup()

    def test_default_configuration(self) -> None:
        """Resolving default model configuration properties when no TOML or env vars exist."""
        for var in [
            f"{app_info.ENV_PREFIX}_MODEL",
            f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE",
            "MODEL_CONFIG_TARGET",
        ]:
            os.environ.pop(var, None)
        sys.argv = [app_info.APP_NAME]

        # Ensure no accidental TOML file is read by pointing to nonexistent file
        os.environ[f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE"] = (
            "/tmp/nonexistent_models_12345.toml"
        )

        reg = LifecycleRegistry()
        __initialize__(reg)

        with enter_phase("system", registry=reg) as scope:
            agent_cfg = scope.get_singleton(AgentConfig)
            dag_cfg = scope.get_singleton(DagConfig)

            self.assertIsInstance(agent_cfg, AgentConfigImpl)
            self.assertIsInstance(dag_cfg, DagConfigImpl)

            self.assertEqual(agent_cfg.conversation_limit, 20)
            self.assertTrue(agent_cfg.inject_followups)
            self.assertTrue(agent_cfg.is_step_mode)
            self.assertTrue(agent_cfg.is_startup_reads)
            self.assertTrue(agent_cfg.edit_delta_output)
            self.assertEqual(agent_cfg.supersede_arg_keep, 1000)

            self.assertEqual(dag_cfg.node_visit_limit, 100)
            self.assertEqual(dag_cfg.batch_size, 1)

    def test_environment_variable_overrides(self) -> None:
        """Overriding model configuration via environment variables."""
        toml_content = """
default = "first"

[models.first]
conversation_limit = 20

[models.custom-env]
conversation_limit = 45
node_visit_limit = 150
"""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            os.environ[f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE"] = temp_path
            os.environ[f"{app_info.ENV_PREFIX}_MODEL"] = "custom-env"

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                agent_cfg = scope.get_singleton(AgentConfig)
                dag_cfg = scope.get_singleton(DagConfig)

                self.assertEqual(agent_cfg.conversation_limit, 45)
                self.assertTrue(agent_cfg.is_step_mode)
                self.assertEqual(dag_cfg.node_visit_limit, 150)
                self.assertEqual(dag_cfg.batch_size, 1)
        finally:
            os.unlink(temp_path)

    def test_load_from_toml_file(self) -> None:
        """Loading named model configurations from a TOML configuration file."""
        toml_content = """
default = "my-test-model"

[models.my-test-model]
max_iterations = 60
node_visit_limit = 200
batch_size = 2

[models.fallback-model]
conversation_limit = 10
"""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            os.environ[f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE"] = temp_path

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                agent_cfg = scope.get_singleton(AgentConfig)
                dag_cfg = scope.get_singleton(DagConfig)

                self.assertEqual(agent_cfg.conversation_limit, 60)
                self.assertEqual(dag_cfg.node_visit_limit, 200)
                self.assertEqual(dag_cfg.batch_size, 2)
        finally:
            os.unlink(temp_path)

    def test_cli_and_autofab_model_selection(self) -> None:
        """Selecting model configuration via --config flag or AUTOFAB_MODEL."""
        toml_content = """
default = "first"

[models.first]
conversation_limit = 10

[models.second]
conversation_limit = 30
"""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            os.environ[f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE"] = temp_path
            sys.argv = [app_info.APP_NAME, "--config", "second"]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                agent_cfg = scope.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg.conversation_limit, 30)

            # Now test AUTOFAB_MODEL env var
            sys.argv = [app_info.APP_NAME]
            os.environ[f"{app_info.ENV_PREFIX}_MODEL"] = "first"

            reg2 = LifecycleRegistry()
            __initialize__(reg2)
            with enter_phase("system", registry=reg2) as scope2:
                agent_cfg2 = scope2.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg2.conversation_limit, 10)

            # Test MODEL_CONFIG_TARGET with bazel style label //model_configs:second
            os.environ.pop(f"{app_info.ENV_PREFIX}_MODEL", None)
            os.environ["MODEL_CONFIG_TARGET"] = "//model_configs:second"

            reg3 = LifecycleRegistry()
            __initialize__(reg3)
            with enter_phase("system", registry=reg3) as scope3:
                agent_cfg3 = scope3.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg3.conversation_limit, 30)

            # Test --config=name syntax and //slash target syntax
            sys.argv = [app_info.APP_NAME, "--config=second"]
            reg4 = LifecycleRegistry()
            __initialize__(reg4)
            with enter_phase("system", registry=reg4) as scope4:
                agent_cfg4 = scope4.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg4.conversation_limit, 30)

            sys.argv = [app_info.APP_NAME]
            os.environ["MODEL_CONFIG_TARGET"] = "//second"
            reg5 = LifecycleRegistry()
            __initialize__(reg5)
            with enter_phase("system", registry=reg5) as scope5:
                agent_cfg5 = scope5.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg5.conversation_limit, 30)
        finally:
            os.unlink(temp_path)

    def test_top_level_table_and_alternate_keys(self) -> None:
        """Loading configuration from top-level tables and alternate field names."""
        toml_content = """
[standalone]
conversation_limit = 8
"""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            os.environ[f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE"] = temp_path
            sys.argv = [app_info.APP_NAME, "--config", "standalone"]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                agent_cfg = scope.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg.conversation_limit, 8)
        finally:
            os.unlink(temp_path)

    def test_workspace_model_configs_toml_discovery(self) -> None:
        """Discovering workspace model_configs.toml naturally without explicit path env var."""
        with tempfile.TemporaryDirectory() as tmp_root:
            with open(os.path.join(tmp_root, "model_configs.toml"), "w") as f:
                f.write(
                    'default = "workspace-model"\n[models.workspace-model]\nconversation_limit = 42\n'
                )
            os.chdir(tmp_root)
            os.environ.pop(f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE", None)
            os.environ.pop(f"{app_info.ENV_PREFIX}_MODEL", None)
            os.environ.pop("MODEL_CONFIG_TARGET", None)
            sys.argv = [app_info.APP_NAME]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                agent_cfg = scope.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg.conversation_limit, 42)

    def test_parent_directory_discovery(self) -> None:
        """Discovering model_configs.toml by walking up parent directories."""
        with tempfile.TemporaryDirectory() as tmp_root:
            with open(os.path.join(tmp_root, "model_configs.toml"), "w") as f:
                f.write(
                    'default = "parent-model"\n[models.parent-model]\nconversation_limit = 55\n'
                )
            sub_dir = os.path.join(tmp_root, "a", "b", "c")
            os.makedirs(sub_dir)
            os.chdir(sub_dir)
            os.environ.pop(f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE", None)
            os.environ.pop(f"{app_info.ENV_PREFIX}_MODEL", None)
            os.environ.pop("MODEL_CONFIG_TARGET", None)
            sys.argv = [app_info.APP_NAME]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                agent_cfg = scope.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg.conversation_limit, 55)

    def test_home_directory_discovery(self) -> None:
        """Discovering models.toml under ~/.autofab when repo config is absent."""
        with tempfile.TemporaryDirectory() as tmp_home:
            autofab_dir = os.path.join(tmp_home, f".{app_info.APP_NAME}")
            os.makedirs(autofab_dir, exist_ok=True)
            with open(os.path.join(autofab_dir, "models.toml"), "w") as f:
                f.write(
                    'default = "home-model"\n[models.home-model]\nconversation_limit = 77\n'
                )

            with tempfile.TemporaryDirectory() as empty_dir:
                os.chdir(empty_dir)
                os.environ["HOME"] = tmp_home
                os.environ.pop(f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE", None)
                os.environ.pop(f"{app_info.ENV_PREFIX}_MODEL", None)
                os.environ.pop("MODEL_CONFIG_TARGET", None)
                sys.argv = [app_info.APP_NAME]

                reg = LifecycleRegistry()
                __initialize__(reg)

                with enter_phase("system", registry=reg) as scope:
                    agent_cfg = scope.get_singleton(AgentConfig)
                    self.assertEqual(agent_cfg.conversation_limit, 77)

    def test_autofab_toml_discovery(self) -> None:
        """Discovering config in autofab.toml only if it contains models or default."""
        with tempfile.TemporaryDirectory() as tmp_root:
            autofab_toml = os.path.join(tmp_root, app_info.DEFAULT_CONFIG_FILE)
            with open(autofab_toml, "w") as f:
                f.write('project = "other"\n')
            os.chdir(tmp_root)
            os.environ.pop(f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE", None)
            os.environ.pop(f"{app_info.ENV_PREFIX}_MODEL", None)
            os.environ.pop("MODEL_CONFIG_TARGET", None)
            sys.argv = [app_info.APP_NAME]

            reg = LifecycleRegistry()
            __initialize__(reg)
            with enter_phase("system", registry=reg) as scope:
                agent_cfg = scope.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg.conversation_limit, 20)

            with open(autofab_toml, "w") as f:
                f.write(
                    'default = "cr-model"\n[models.cr-model]\nconversation_limit = 99\n'
                )

            reg2 = LifecycleRegistry()
            __initialize__(reg2)
            with enter_phase("system", registry=reg2) as scope2:
                agent_cfg2 = scope2.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg2.conversation_limit, 99)

    def test_step_mode_disabled_via_toml(self) -> None:
        """Verifying that is_step_mode = false in TOML explicitly disables step mode."""
        toml_content = """
default = "no-step"

[models.no-step]
is_step_mode = false
"""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            os.environ[f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE"] = temp_path
            sys.argv = [app_info.APP_NAME]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                agent_cfg = scope.get_singleton(AgentConfig)
                self.assertFalse(agent_cfg.is_step_mode)
                self.assertTrue(agent_cfg.inject_followups)
                self.assertTrue(agent_cfg.is_startup_reads)
                self.assertTrue(agent_cfg.edit_delta_output)
        finally:
            os.unlink(temp_path)

    def test_user_model_configs_toml_discovery(self) -> None:
        """Discovering model_configs.toml in user config directory when repo config is absent."""
        user_cfg = os.path.join(self.tmp_config_dir.name, "model_configs.toml")
        with open(user_cfg, "w") as f:
            f.write(
                'default = "user-global-model"\n[models.user-global-model]\nconversation_limit = 88\n'
            )

        with tempfile.TemporaryDirectory() as empty_dir:
            os.chdir(empty_dir)
            for var in [
                f"{app_info.ENV_PREFIX}_MODEL",
                f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE",
                "MODEL_CONFIG_TARGET",
            ]:
                os.environ.pop(var, None)
            sys.argv = [app_info.APP_NAME]

            reg = LifecycleRegistry()
            __initialize__(reg)

            with enter_phase("system", registry=reg) as scope:
                agent_cfg = scope.get_singleton(AgentConfig)
                self.assertEqual(agent_cfg.conversation_limit, 88)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-18T01:04:33Z
# LAST_CHANGED: 2026-10-29T16:00:00Z
# CHANGE: remove OpenAIConfig tests
# COVERAGE_AUDIT: 2026-10-18T01:04:33Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
