"""Unit tests for tool_provider_impl aligned with grounding specifications."""

import unittest
from typing import Set
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib.tool_provider import (
    ActualParameterBindings,
    Boolean,
    BooleanParameterConverter,
    Integer,
    IntegerParameterConverter,
    Parameter,
    Response,
    String,
    StringParameterConverter,
    Tool,
    ToolManager,
    WireParameterBindings,
)
from update_with_ai.parts.sandbox.lib.tool_provider_impl import (
    BooleanParameterConverter as BooleanParameterConverterImpl,
    IntegerParameterConverter as IntegerParameterConverterImpl,
    StringParameterConverter as StringParameterConverterImpl,
    ToolManager as ToolManagerImpl,
    __initialize__,
)


class DummyTool:
    def __init__(self, name: str, parameters: Set[Parameter]) -> None:
        self._name = name
        self._parameters = parameters
        self.last_bindings: ActualParameterBindings | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Dummy tool {self._name}"

    @property
    def parameters(self) -> Set[Parameter]:
        return self._parameters

    def execute_tool(
        self, actual_parameter_bindings: ActualParameterBindings
    ) -> Response:
        self.last_bindings = actual_parameter_bindings
        return Response(is_failed=False, is_terminated=False, content="dummy executed")


class ToolProviderImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_string_parameter_converter(self) -> None:
        """CUJ: Converting string parameter values."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            converter = scope.get_singleton(StringParameterConverter)
            self.assertEqual(converter.actual_type, str)
            self.assertEqual(converter.wire_type, String())
            # Requirement: Converting a wire type string produces that string directly as its actual value.
            self.assertEqual(converter.convert("test_string"), "test_string")

    def test_integer_parameter_converter(self) -> None:
        """CUJ: Converting integer parameter values."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            converter = scope.get_singleton(IntegerParameterConverter)
            self.assertEqual(converter.actual_type, int)
            self.assertEqual(converter.wire_type, Integer())
            # Requirement: Converting a wire type integer produces that integer directly as its actual value.
            self.assertEqual(converter.convert(123), 123)

    def test_boolean_parameter_converter(self) -> None:
        """CUJ: Converting boolean parameter values."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            converter = scope.get_singleton(BooleanParameterConverter)
            self.assertEqual(converter.actual_type, bool)
            self.assertEqual(converter.wire_type, Boolean())
            # Requirement: Converting a wire type boolean produces that boolean directly as its actual value.
            self.assertTrue(converter.convert(True))
            self.assertFalse(converter.convert(False))

    def test_tool_manager_install_and_execute_success(self) -> None:
        """CUJ: Installing and successfully executing a tool."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            str_conv = scope.get_singleton(StringParameterConverter)

            param = Parameter(
                name="arg1",
                description="an argument",
                parameter_converter=str_conv,
                is_required=True,
            )
            tool = DummyTool("my_tool", {param})
            manager.install_tool(tool)

            self.assertIn(tool, manager.installed_tools)

            wire_bindings = WireParameterBindings(bindings={("arg1", "val1")})
            resp = manager.execute_tool("my_tool", wire_bindings)

            # Requirement: When parameter mappings are successfully resolved, executing a tool by name delegates to the matching tool with the resolved actual parameter bindings and returns the tool's response.
            # Requirement: [ToolManager] Executing a tool by name with wire parameter bindings produces the tool response upon resolving parameter conversions.
            self.assertFalse(resp.is_failed)
            self.assertEqual(resp.content, "dummy executed")
            self.assertIsNotNone(tool.last_bindings)
            assert tool.last_bindings is not None
            binding_dict = dict(tool.last_bindings.bindings)
            self.assertEqual(binding_dict[param], "val1")

    def test_tool_manager_unknown_tool(self) -> None:
        """CUJ: Executing a tool that is not installed fails."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            resp = manager.execute_tool(
                "nonexistent", WireParameterBindings(bindings=set())
            )
            # Requirement: Executing a tool by name fails if no installed tool matches the requested name.
            self.assertTrue(resp.is_failed)

    def test_tool_manager_unknown_parameter(self) -> None:
        """CUJ: Executing a tool with an unrecognized parameter fails."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            tool = DummyTool("tool_no_params", set())
            manager.install_tool(tool)

            resp = manager.execute_tool(
                "tool_no_params", WireParameterBindings(bindings={("bogus", "val")})
            )
            # Requirement: Executing a tool by name fails if a parameter name does not match any parameter of the tool, and reminds the agent that only declared parameters of the tool can be provided.
            self.assertTrue(resp.is_failed)
            self.assertEqual(
                resp.reminder, "Only declared parameters of the tool can be provided."
            )

    def test_tool_manager_missing_required_parameter(self) -> None:
        """CUJ: Executing a tool without supplying a required parameter fails."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            str_conv = scope.get_singleton(StringParameterConverter)
            param = Parameter(
                name="req_arg",
                description="required",
                parameter_converter=str_conv,
                is_required=True,
            )
            tool = DummyTool("tool_req", {param})
            manager.install_tool(tool)

            resp = manager.execute_tool(
                "tool_req", WireParameterBindings(bindings=set())
            )
            # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, and reminds the agent that required parameters of the tool must be supplied.
            self.assertTrue(resp.is_failed)
            self.assertEqual(
                resp.reminder, "Required parameters of the tool must be supplied."
            )


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
