"""
Tests for lib/bazel_agent_config_impl.py (BazelAgentConfigImpl).

Behavioral contract (see specs/bazel_agent_config_impl-low.md):

- parse_target splits canonical labels into (package_path, target_name):
  //pkg:name -> ("pkg", "name"), //pkg -> ("pkg", "pkg"); invalid or
  repository-qualified labels raise ConfigNotFoundError (an unexpected
  failure).
- find_config_file locates the generated {name}_config.py in runfiles first,
  then bazel-bin under the workspace root; raises ConfigNotFoundError with
  actionable guidance when not found.
- load_config imports the generated module and returns an AgentConfig.
- resolve_api_key uses the config-pinned API-key environment variable
  (api_key_env) when one is named — that variable alone, with no fallback —
  otherwise the plain AGENT_API_KEY variable; ApiKeyNotFoundError when no
  key is available.
- resolve_config_target priority: explicit arg > AGENT_CONFIG_TARGET >
  //agent_configs:default.
- build_agent_loop_config combines the config and resolved API key into an
  AgentLoopConfig (the model/URL/limits come from the target, never from
  hardcoded values in code).
"""

import contextlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Iterator, Optional
from unittest.mock import patch

from update_with_ai.lib.bazel_agent_config import (
    ApiKeyNotFoundError,
    AgentConfig,
    BazelAgentConfig,
    ConfigNotFoundError,
    DEFAULT_CONFIG_TARGET,
)
from update_with_ai.lib.bazel_agent_config_impl import BazelAgentConfigImpl
from update_with_ai.lib.agent_loop import AgentLoopConfig

PACKAGE = "agent_configs"
NAME = "default"


def _write_generated_config(
    root: Path,
    package: str,
    name: str,
    model: str = "fake-model",
    api_key_env: str = "",
) -> None:
    """Write a generated {name}_config.py into a fake bazel-bin tree under root."""
    pkg_dir = root / "bazel-bin" / package
    pkg_dir.mkdir(parents=True, exist_ok=True)
    # Built line-by-line: str.format would choke on the dict braces.
    lines = [
        "AGENT_CONFIG = {",
        '    "label": "//{}:{}",'.format(package, name),
        '    "name": "{}",'.format(name),
        '    "model": "{}",'.format(model),
        '    "base_url": "http://localhost:8000/v1",',
        '    "api_key_env": "{}",'.format(api_key_env),
        '    "max_iterations": 7,',
        '    "temperature": 0.3,',
        '    "timeout": 12.5,',
        '    "max_tokens": None,',
        "}",
        "",
    ]
    (pkg_dir / (name + "_config.py")).write_text("\n".join(lines), encoding="utf-8")


@contextlib.contextmanager
def _patch_env(**set_vars: str) -> Iterator[None]:
    """Isolate the loader's environment for a test and restore on exit."""
    keys = (
        "AGENT_CONFIG_TARGET",
        "AGENT_API_KEY",
        "CUSTOM_API_KEY",
        "RUNFILES_DIR",
        "BAZEL_RUNFILES",
        "BUILD_WORKSPACE_DIRECTORY",
    )
    saved: Dict[str, Optional[str]] = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            os.environ.pop(k, None)
        for k, v in set_vars.items():
            os.environ[k] = v
        yield
    finally:
        for k in keys:
            os.environ.pop(k, None)
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


class TestBazelAgentConfigImpl(unittest.TestCase):
    """Shared fixture for the impl-class tests."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="bazel_agent_config_test_")
        self._root = Path(self._tmp)
        self.impl = BazelAgentConfigImpl()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_implements_bazel_agent_config_protocol(self) -> None:
        """The impl exposes the protocol's operation (structural conformance)."""
        def _use_as_protocol(p: BazelAgentConfig) -> BazelAgentConfig:
            return p  # structural: the type annotation is the check

        self.assertIs(_use_as_protocol(self.impl), self.impl)
        self.assertTrue(callable(self.impl.build_agent_loop_config))


class TestParseTarget(TestBazelAgentConfigImpl):
    """parse_target label parsing."""

    def test_canonical_label(self) -> None:
        self.assertEqual(self.impl.parse_target("//agent_configs:default"), ("agent_configs", "default"))

    def test_nested_package(self) -> None:
        self.assertEqual(
            self.impl.parse_target("//models/experimental:fast"), ("models/experimental", "fast")
        )

    def test_package_only_label_uses_last_segment(self) -> None:
        self.assertEqual(self.impl.parse_target("//agent_configs"), ("agent_configs", "agent_configs"))
        self.assertEqual(self.impl.parse_target("//a/b"), ("a/b", "b"))

    def test_invalid_labels_raise(self) -> None:
        for bad in (
            "agent_configs:default",
            ":default",
            "//agent_configs:",
            "@repo//agent_configs:default",
        ):
            with self.assertRaises(ConfigNotFoundError):
                self.impl.parse_target(bad)


class TestFindAndLoad(TestBazelAgentConfigImpl):
    """find_config_file / load_config against a fake bazel-bin tree."""

    def test_find_config_file_in_bazel_bin(self) -> None:
        """The generated module is found under bazel-bin/<pkg>/."""
        _write_generated_config(self._root, PACKAGE, NAME)
        path = self.impl.find_config_file("//agent_configs:default", workspace_root=str(self._root))
        self.assertEqual(
            path, str(self._root / "bazel-bin" / PACKAGE / (NAME + "_config.py"))
        )

    def test_find_config_file_prefers_runfiles(self) -> None:
        """Runfiles take priority over bazel-bin when both exist."""
        _write_generated_config(self._root, PACKAGE, NAME)
        runfiles = self._root / "runfiles"
        (runfiles / PACKAGE).mkdir(parents=True)
        (runfiles / PACKAGE / (NAME + "_config.py")).write_text(
            "AGENT_CONFIG = {}\n", encoding="utf-8"
        )
        with _patch_env(RUNFILES_DIR=str(runfiles)):
            path = self.impl.find_config_file("//agent_configs:default", workspace_root=str(self._root))
        self.assertTrue(str(path).startswith(str(runfiles)))

    def test_find_config_file_missing_raises_with_guidance(self) -> None:
        """A not-built config raises ConfigNotFoundError mentioning bazel build."""
        with _patch_env():
            with self.assertRaises(ConfigNotFoundError) as ctx:
                self.impl.find_config_file("//agent_configs:staging", workspace_root=str(self._root))
        message = str(ctx.exception)
        self.assertIn("//agent_configs:staging", message)
        self.assertIn("bazel build //agent_configs:staging", message)

    def test_load_config_returns_agent_config(self) -> None:
        """load_config imports the generated module into an AgentConfig."""
        _write_generated_config(self._root, PACKAGE, NAME, model="loaded-model")
        config = self.impl.load_config("//agent_configs:default", workspace_root=str(self._root))
        self.assertIsInstance(config, AgentConfig)
        self.assertEqual(config.label, "//agent_configs:default")
        self.assertEqual(config.name, "default")
        self.assertEqual(config.model, "loaded-model")
        self.assertEqual(config.api_key_env, "")
        self.assertEqual(config.max_iterations, 7)
        self.assertEqual(config.temperature, 0.3)
        self.assertEqual(config.timeout, 12.5)
        self.assertIsNone(config.max_tokens)


class TestApiKeyResolution(TestBazelAgentConfigImpl):
    """resolve_api_key environment handling."""

    def test_plain_api_key_used_when_unpinned(self) -> None:
        with _patch_env(AGENT_API_KEY="fallback"):
            self.assertEqual(self.impl.resolve_api_key(""), "fallback")

    def test_missing_plain_key_raises(self) -> None:
        with _patch_env():
            with self.assertRaises(ApiKeyNotFoundError) as ctx:
                self.impl.resolve_api_key("")
        message = str(ctx.exception)
        self.assertIn("AGENT_API_KEY", message)

    def test_pinned_env_var_used_alone(self) -> None:
        """A config-pinned variable wins over AGENT_API_KEY."""
        with _patch_env(CUSTOM_API_KEY="custom-key", AGENT_API_KEY="fallback"):
            self.assertEqual(self.impl.resolve_api_key("CUSTOM_API_KEY"), "custom-key")

    def test_pinned_env_var_missing_raises(self) -> None:
        """A pinned variable is required: AGENT_API_KEY is NOT a fallback."""
        with _patch_env(AGENT_API_KEY="fallback"):
            with self.assertRaises(ApiKeyNotFoundError) as ctx:
                self.impl.resolve_api_key("CUSTOM_API_KEY")
        message = str(ctx.exception)
        self.assertIn("CUSTOM_API_KEY", message)
        # AGENT_API_KEY is not named: the pin is exclusive.
        self.assertNotIn("AGENT_API_KEY", message)


class TestConfigTargetResolution(TestBazelAgentConfigImpl):
    """resolve_config_target selection priority."""

    def test_explicit_arg_wins_over_env_and_default(self) -> None:
        with _patch_env(AGENT_CONFIG_TARGET="//agent_configs:from_env"):
            self.assertEqual(
                self.impl.resolve_config_target("//agent_configs:from_arg"),
                "//agent_configs:from_arg",
            )

    def test_env_wins_over_default(self) -> None:
        with _patch_env(AGENT_CONFIG_TARGET="//agent_configs:from_env"):
            self.assertEqual(self.impl.resolve_config_target(None), "//agent_configs:from_env")

    def test_default_convention(self) -> None:
        with _patch_env():
            self.assertEqual(self.impl.resolve_config_target(None), DEFAULT_CONFIG_TARGET)
            self.assertEqual(DEFAULT_CONFIG_TARGET, "//agent_configs:default")


class TestBuildAgentLoopConfig(TestBazelAgentConfigImpl):
    """build_agent_loop_config end-to-end (config target + env API key)."""

    def test_combines_config_and_api_key(self) -> None:
        """The built AgentLoopConfig carries target values + resolved key only."""
        _write_generated_config(self._root, PACKAGE, NAME, model="combined-model")
        with _patch_env(AGENT_API_KEY="secret-key"):
            config = self.impl.build_agent_loop_config(
                "//agent_configs:default", workspace_root=str(self._root)
            )
        self.assertIsInstance(config, AgentLoopConfig)
        self.assertEqual(config.model, "combined-model")
        self.assertEqual(config.base_url, "http://localhost:8000/v1")
        self.assertEqual(config.api_key, "secret-key")
        self.assertEqual(config.max_iterations, 7)
        self.assertEqual(config.temperature, 0.3)
        self.assertEqual(config.timeout, 12.5)
        self.assertIsNone(config.max_tokens)

    def test_no_key_raises(self) -> None:
        _write_generated_config(self._root, PACKAGE, NAME)
        with _patch_env():
            with self.assertRaises(ApiKeyNotFoundError):
                self.impl.build_agent_loop_config(
                    "//agent_configs:default", workspace_root=str(self._root)
                )

    def test_missing_target_raises(self) -> None:
        with _patch_env(AGENT_API_KEY="k"):
            with self.assertRaises(ConfigNotFoundError):
                self.impl.build_agent_loop_config(
                    "//agent_configs:staging", workspace_root=str(self._root)
                )

    def test_pinned_env_var_used_end_to_end(self) -> None:
        """A config naming an API-key env var uses that variable, not AGENT_API_KEY."""
        _write_generated_config(
            self._root, PACKAGE, NAME, model="pinned-model", api_key_env="CUSTOM_API_KEY"
        )
        with _patch_env(CUSTOM_API_KEY="pinned-key", AGENT_API_KEY="fallback"):
            config = self.impl.build_agent_loop_config(
                "//agent_configs:default", workspace_root=str(self._root)
            )
        self.assertEqual(config.model, "pinned-model")
        self.assertEqual(config.api_key, "pinned-key")

    def test_pinned_env_var_missing_end_to_end(self) -> None:
        """A missing pinned variable raises even when convention vars are set."""
        _write_generated_config(
            self._root, PACKAGE, NAME, api_key_env="CUSTOM_API_KEY"
        )
        with _patch_env(AGENT_API_KEY="fallback"):
            with self.assertRaises(ApiKeyNotFoundError):
                self.impl.build_agent_loop_config(
                    "//agent_configs:default", workspace_root=str(self._root)
                )

    def test_agent_config_to_agent_loop_config(self) -> None:
        """AgentConfig.to_agent_loop_config threads every field through."""
        cfg = AgentConfig(
            label="//agent_configs:default",
            name="default",
            model="m",
            base_url="http://x/v1",
            max_iterations=3,
            temperature=0.5,
            timeout=9.0,
            max_tokens=128,
        )
        loop_cfg = cfg.to_agent_loop_config("key")
        self.assertEqual(loop_cfg.api_key, "key")
        self.assertEqual(loop_cfg.max_tokens, 128)
        self.assertEqual(loop_cfg.max_iterations, 3)


if __name__ == "__main__":
    unittest.main()
