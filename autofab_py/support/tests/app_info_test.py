"""Unit tests for support.lib.app_info."""

import os
import sys
import unittest
from unittest import mock

from autofab_py.support.lib import app_info


class AppInfoTest(unittest.TestCase):
    def test_app_name_and_prefix(self) -> None:
        self.assertEqual(app_info.get_app_name(), app_info.APP_NAME)
        self.assertEqual(app_info.get_env_prefix(), app_info.ENV_PREFIX)
        self.assertEqual(app_info.ENV_PREFIX, app_info.APP_NAME.upper())
        self.assertEqual(app_info.get_app_title(), "Autofab")

    def test_derived_file_names(self) -> None:
        self.assertEqual(app_info.DEFAULT_CONFIG_FILE, f"{app_info.APP_NAME}.toml")
        self.assertEqual(app_info.DEFAULT_ROLES_FILE, f"{app_info.APP_NAME}_roles.toml")
        self.assertEqual(
            app_info.DEFAULT_ROLE_DESCRIPTOR, f".{app_info.APP_NAME}_role.json"
        )
        self.assertEqual(app_info.DEFAULT_LOG_FILE, f".{app_info.APP_NAME}.log")
        self.assertEqual(
            app_info.DEFAULT_PENDING_WORK_FILE,
            f".{app_info.APP_NAME}_pending_work.json",
        )
        self.assertEqual(
            app_info.DEFAULT_BLAME_BUFFER_FILE,
            f".{app_info.APP_NAME}_blame_buffer.json",
        )
        self.assertEqual(
            app_info.DEFAULT_AUDIT_BUFFER_FILE,
            f".{app_info.APP_NAME}_audit_buffer.json",
        )
        self.assertEqual(app_info.DEFAULT_STATE_DIR, f".{app_info.APP_NAME}")
        self.assertEqual(
            app_info.get_config_filenames(), (f"{app_info.APP_NAME}.toml",)
        )
        self.assertEqual(
            app_info.get_roles_filenames(), (f"{app_info.APP_NAME}_roles.toml",)
        )
        self.assertEqual(
            app_info.get_role_workspaces_containers(),
            (f"{app_info.APP_NAME}_role_workspaces",),
        )
        self.assertEqual(
            app_info.get_default_role_workspaces_container(),
            f"{app_info.APP_NAME}_role_workspaces",
        )
        self.assertEqual(
            app_info.get_role_descriptors(), (f".{app_info.APP_NAME}_role.json",)
        )
        self.assertEqual(app_info.get_state_dir_names(), (f".{app_info.APP_NAME}",))
        self.assertEqual(app_info.get_default_state_dir(), f".{app_info.APP_NAME}")
        self.assertEqual(app_info.get_log_filenames(), (f".{app_info.APP_NAME}.log",))
        self.assertEqual(
            app_info.get_pending_work_filenames(),
            (f".{app_info.APP_NAME}_pending_work.json",),
        )
        self.assertEqual(
            app_info.get_blame_buffer_filenames(),
            (f".{app_info.APP_NAME}_blame_buffer.json",),
        )
        self.assertEqual(
            app_info.get_audit_buffer_filenames(),
            (f".{app_info.APP_NAME}_audit_buffer.json",),
        )

    def test_naming_and_stubs(self) -> None:
        self.assertEqual(
            app_info.get_coordinator_skill_name(), f"{app_info.APP_NAME}_coordinator"
        )
        self.assertEqual(app_info.get_worker_type_name(), f"{app_info.APP_NAME}_worker")
        self.assertEqual(
            app_info.get_baseline_worker_type_name(),
            f"{app_info.APP_NAME}_baseline_worker",
        )
        self.assertEqual(
            app_info.get_stub_marker(), f"{app_info.APP_NAME.upper()} TEST STUB v4"
        )
        self.assertTrue(
            app_info.is_stub(
                f"# {app_info.APP_NAME.upper()} TEST STUB v4\nraise NotImplementedError"
            )
        )
        self.assertFalse(app_info.is_stub("normal python code"))

    def test_environment_accessors(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                f"{app_info.ENV_PREFIX}_VERIFY_TIMEOUT": "45.0",
                f"{app_info.ENV_PREFIX}_MAIN_ROOT": "/repo/root",
                f"{app_info.ENV_PREFIX}_ROLE": "lib",
                f"{app_info.ENV_PREFIX}_MODEL": "fast",
                f"{app_info.ENV_PREFIX}_MODEL_CONFIG_FILE": "/tmp/cfg.toml",
            },
        ):
            self.assertEqual(app_info.get_verify_timeout(), 45.0)
            self.assertEqual(app_info.get_main_root(), "/repo/root")
            self.assertEqual(app_info.get_role_name(), "lib")
            self.assertEqual(app_info.get_model_name(), "fast")
            self.assertEqual(app_info.get_model_config_file(), "/tmp/cfg.toml")

    def test_resolve_state_dir(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            state_dir = app_info.resolve_state_dir(td)
            self.assertEqual(state_dir, os.path.join(td, f".{app_info.APP_NAME}"))
            self.assertTrue(os.path.isdir(state_dir))

    def test_resolve_and_append_log(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            parts_d = os.path.join(td, "parts", "foo")
            os.makedirs(parts_d, exist_ok=True)
            log_p = app_info.resolve_log_path(
                os.path.join(parts_d, "lib", "bar.py"), repo_root=td
            )
            self.assertEqual(log_p, os.path.join(td, f".{app_info.APP_NAME}.log"))
            app_info.append_log(
                os.path.join(parts_d, "lib", "bar.py"),
                "[CHANGE] updated bar",
                repo_root=td,
            )
            with open(log_p, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[CHANGE] updated bar", content)

    def test_get_user_config_dir_env_override(self) -> None:
        with mock.patch.dict(
            os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "/custom/config/dir"}
        ):
            self.assertEqual(app_info.get_user_config_dir(), "/custom/config/dir")

    def test_get_user_config_dir_xdg(self) -> None:
        env = {
            f"{app_info.ENV_PREFIX}_CONFIG_DIR": "",
            "XDG_CONFIG_HOME": "/custom/xdg",
        }
        with mock.patch.dict(os.environ, env):
            self.assertEqual(
                app_info.get_user_config_dir(), f"/custom/xdg/{app_info.APP_NAME}"
            )

    def test_get_user_config_dir_default_posix(self) -> None:
        with mock.patch.dict(
            os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "", "XDG_CONFIG_HOME": ""}
        ):
            with mock.patch("sys.platform", "darwin"):
                home = os.path.expanduser("~")
                expected = os.path.join(home, ".config", app_info.APP_NAME)
                self.assertEqual(app_info.get_user_config_dir(), expected)

    def test_get_user_model_config_file(self) -> None:
        with mock.patch.dict(
            os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "/tmp/test_cfg"}
        ):
            self.assertEqual(
                app_info.get_user_model_config_file(),
                "/tmp/test_cfg/model_configs.toml",
            )

    def test_get_user_credentials_file(self) -> None:
        with mock.patch.dict(
            os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "/tmp/test_cfg"}
        ):
            self.assertEqual(
                app_info.get_user_credentials_file(),
                "/tmp/test_cfg/credentials.toml",
            )

    def test_load_credentials_missing_file(self) -> None:
        with mock.patch.dict(
            os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": "/tmp/nonexistent_12345"}
        ):
            self.assertEqual(app_info.load_credentials(), {})

    def test_load_credentials_existing_file(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            creds_file = os.path.join(tmp_dir, "credentials.toml")
            with open(creds_file, "w") as f:
                f.write(
                    'openai_api_key = "sk-test123"\nDEEPSEEK_API_KEY = "sk-deep456"\n'
                )
            with mock.patch.dict(
                os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": tmp_dir}
            ):
                creds = app_info.load_credentials()
                self.assertEqual(creds.get("OPENAI_API_KEY"), "sk-test123")
                self.assertEqual(creds.get("openai_api_key"), "sk-test123")
                self.assertEqual(creds.get("DEEPSEEK_API_KEY"), "sk-deep456")


if __name__ == "__main__":
    unittest.main()
