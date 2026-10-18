"""Unit tests for support.lib.app_info."""
import os
import sys
import unittest
from unittest import mock

from update_python_with_ai.support.lib import app_info


class AppInfoTest(unittest.TestCase):
    def test_app_name_and_prefix(self) -> None:
        self.assertEqual(app_info.get_app_name(), app_info.APP_NAME)
        self.assertEqual(app_info.get_env_prefix(), app_info.ENV_PREFIX)
        self.assertEqual(app_info.ENV_PREFIX, app_info.APP_NAME.upper())

    def test_derived_file_names(self) -> None:
        self.assertEqual(app_info.DEFAULT_CONFIG_FILE, f"{app_info.APP_NAME}.toml")
        self.assertEqual(app_info.DEFAULT_ROLES_FILE, f"{app_info.APP_NAME}_roles.toml")
        self.assertEqual(app_info.DEFAULT_ROLE_DESCRIPTOR, f".{app_info.APP_NAME}_role.json")
        self.assertEqual(app_info.DEFAULT_LOG_FILE, f".{app_info.APP_NAME}.log")
        self.assertEqual(app_info.DEFAULT_PENDING_WORK_FILE, f".{app_info.APP_NAME}_pending_work.json")
        self.assertEqual(app_info.DEFAULT_BLAME_BUFFER_FILE, f".{app_info.APP_NAME}_blame_buffer.json")
        self.assertEqual(app_info.DEFAULT_AUDIT_BUFFER_FILE, f".{app_info.APP_NAME}_audit_buffer.json")

    def test_get_user_config_dir_env_override(self) -> None:
        with mock.patch.dict(os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "/custom/config/dir"}):
            self.assertEqual(app_info.get_user_config_dir(), "/custom/config/dir")

    def test_get_user_config_dir_xdg(self) -> None:
        env = {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "", "XDG_CONFIG_HOME": "/custom/xdg"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(app_info.get_user_config_dir(), f"/custom/xdg/{app_info.APP_NAME}")

    def test_get_user_config_dir_default_posix(self) -> None:
        with mock.patch.dict(os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "", "XDG_CONFIG_HOME": ""}):
            with mock.patch("sys.platform", "darwin"):
                home = os.path.expanduser("~")
                expected = os.path.join(home, ".config", app_info.APP_NAME)
                self.assertEqual(app_info.get_user_config_dir(), expected)

    def test_get_user_model_config_file(self) -> None:
        with mock.patch.dict(os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "/tmp/test_cfg"}):
            self.assertEqual(
                app_info.get_user_model_config_file(),
                "/tmp/test_cfg/model_configs.toml",
            )

    def test_get_user_credentials_file(self) -> None:
        with mock.patch.dict(os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "/tmp/test_cfg"}):
            self.assertEqual(
                app_info.get_user_credentials_file(),
                "/tmp/test_cfg/credentials.toml",
            )

    def test_load_credentials_missing_file(self) -> None:
        with mock.patch.dict(os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "/tmp/nonexistent_12345"}):
            self.assertEqual(app_info.load_credentials(), {})

    def test_load_credentials_existing_file(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            creds_file = os.path.join(tmp_dir, "credentials.toml")
            with open(creds_file, "w") as f:
                f.write('openai_api_key = "sk-test123"\nDEEPSEEK_API_KEY = "sk-deep456"\n')
            with mock.patch.dict(os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": tmp_dir}):
                creds = app_info.load_credentials()
                self.assertEqual(creds.get("OPENAI_API_KEY"), "sk-test123")
                self.assertEqual(creds.get("openai_api_key"), "sk-test123")
                self.assertEqual(creds.get("DEEPSEEK_API_KEY"), "sk-deep456")


if __name__ == "__main__":
    unittest.main()
