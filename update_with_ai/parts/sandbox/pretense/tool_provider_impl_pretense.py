"""Pretense test suite for sandbox tool_provider_impl.

Tests ToolManager and AliasManagerType.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Set

from hypothesis import given, settings
from hypothesis import strategies as st

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import file_alias
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.sandbox.lib import tool_provider, tool_provider_impl
from update_with_ai.parts.sandbox.lib.tool_provider_impl import (
    AliasManagerType,
    ToolManager,
)


class MockAliasManager:
    tier = agent_session

    def __init__(self) -> None:
        self.workspace_root = file_alias.file_paths.WorkspaceRoot(
            file_alias.file_paths.PathString("/workspace")
        )

    def to_alias(self, path: str) -> file_alias.FileAlias:
        return file_alias.FileAlias(file_alias.RelativePath(path))


class MockIntParamType(tool_provider.ParameterType[int, str]):
    @property
    def actual_type(self) -> type[int]:
        return int

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> int:
        try:
            return int(wire_value)
        except (ValueError, TypeError) as e:
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(f"Invalid integer: {wire_value}")
            ) from e


class MockCustomTool(tool_provider.Tool):
    tier = agent_session

    def __init__(
        self,
        name: str = "custom",
        parameters: Optional[Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]] = None,
    ) -> None:
        self._name = tool_provider.ToolName(name)
        self._description = tool_provider.ToolDescription("A custom test tool")
        self._parameters = parameters or {}
        self.last_actual_bindings: Optional[Mapping[tool_provider.ToolParameter[Any, Any], Any]] = None

    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        self.last_actual_bindings = dict(actual_parameter_bindings)
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent("Executed successfully"),
        )


class TestToolProviderReal(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        tool_provider_impl.__initialize__(self.registry)

        self.mock_alias_mgr = MockAliasManager()
        self.registry.register_instance(self.mock_alias_mgr, keys=[file_alias.AliasManager], tier=agent_session)

    def test_alias_manager_type(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            amt = scope.get_singleton(AliasManagerType)
            self.assertEqual(amt.actual_type, file_alias.FileAlias)
            self.assertEqual(amt.wire_type, str)

            alias = amt.convert("src/main.py")
            self.assertEqual(str(alias.relative_path), "src/main.py")

            with self.assertRaises(tool_provider.ParameterConversionError):
                amt.convert(12345)  # type: ignore

    def test_tool_manager_installation_and_unknown_tool(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(ToolManager)
            tool = MockCustomTool(name="test_tool")
            mgr.install_tool(tool)

            self.assertIn(tool_provider.ToolName("test_tool"), mgr.installed_tools)
            self.assertEqual(mgr.installed_tools[tool_provider.ToolName("test_tool")], tool)

            # Unknown tool
            resp = mgr.execute_tool(tool_provider.ToolName("unknown_tool"), {})
            self.assertTrue(resp.is_failed)
            self.assertIn("Unknown tool 'unknown_tool'", str(resp.content))
            self.assertIn("test_tool", str(resp.content))

    def test_tool_manager_unknown_parameter(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(ToolManager)
            param = tool_provider.ToolParameter[int, str](
                name=tool_provider.ParameterName("count"),
                description=tool_provider.ParameterDescription("Count item"),
                parameter_type=MockIntParamType(),
                is_required=True,
                default_value=None,
            )
            tool = MockCustomTool(name="test_tool", parameters={param.name: param})
            mgr.install_tool(tool)

            resp = mgr.execute_tool(
                tool_provider.ToolName("test_tool"),
                {tool_provider.ParameterName("bad_arg"): "val"},  # type: ignore
            )
            self.assertTrue(resp.is_failed)
            self.assertIn("Unknown parameter 'bad_arg'", str(resp.content))
            self.assertIn("Valid parameters: count", str(resp.content))

    def test_tool_manager_missing_required_parameter(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(ToolManager)

            # 1. Missing without missing_message callback
            param1 = tool_provider.ToolParameter[int, str](
                name=tool_provider.ParameterName("req1"),
                description=tool_provider.ParameterDescription("Required 1"),
                parameter_type=MockIntParamType(),
                is_required=True,
                default_value=None,
            )
            tool1 = MockCustomTool(name="tool1", parameters={param1.name: param1})
            mgr.install_tool(tool1)

            resp = mgr.execute_tool(tool_provider.ToolName("tool1"), {})
            self.assertTrue(resp.is_failed)
            self.assertIn("Required parameter 'req1' missing", str(resp.content))

            # 2. Missing with missing_message callback
            param2 = tool_provider.ToolParameter[int, str](
                name=tool_provider.ParameterName("req2"),
                description=tool_provider.ParameterDescription("Required 2"),
                parameter_type=MockIntParamType(),
                is_required=True,
                default_value=None,
                missing_message=lambda present: tool_provider.MissingMessage("Custom missing note"),
            )
            tool2 = MockCustomTool(name="tool2", parameters={param2.name: param2})
            mgr.install_tool(tool2)

            resp = mgr.execute_tool(tool_provider.ToolName("tool2"), {})
            self.assertTrue(resp.is_failed)
            self.assertIn("Required parameter 'req2' missing", str(resp.content))
            self.assertIn("Custom missing note", str(resp.content))

    def test_tool_manager_conversion_and_default_value(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(ToolManager)

            param_req = tool_provider.ToolParameter[int, str](
                name=tool_provider.ParameterName("count"),
                description=tool_provider.ParameterDescription("Count item"),
                parameter_type=MockIntParamType(),
                is_required=True,
                default_value=None,
            )
            param_opt = tool_provider.ToolParameter[int, str](
                name=tool_provider.ParameterName("limit"),
                description=tool_provider.ParameterDescription("Optional limit"),
                parameter_type=MockIntParamType(),
                is_required=False,
                default_value=42,
            )
            tool = MockCustomTool(name="calc", parameters={param_req.name: param_req, param_opt.name: param_opt})
            mgr.install_tool(tool)

            # Conversion error
            resp = mgr.execute_tool(
                tool_provider.ToolName("calc"),
                {tool_provider.ParameterName("count"): "not-an-int"},  # type: ignore
            )
            self.assertTrue(resp.is_failed)
            self.assertIn("Invalid argument for parameter 'count'", str(resp.content))

            # Success with conversion and default value applied
            resp = mgr.execute_tool(
                tool_provider.ToolName("calc"),
                {tool_provider.ParameterName("count"): "100"},  # type: ignore
            )
            self.assertFalse(resp.is_failed)
            self.assertIsNotNone(tool.last_actual_bindings)
            assert tool.last_actual_bindings is not None
            self.assertEqual(tool.last_actual_bindings[param_req], 100)
            self.assertEqual(tool.last_actual_bindings[param_opt], 42)


class TestToolProviderFuzz(unittest.TestCase):
    @settings(max_examples=25)
    @given(val=st.integers())
    def test_mock_int_conversion(self, val: int) -> None:
        p = MockIntParamType()
        self.assertEqual(p.convert(str(val)), val)
