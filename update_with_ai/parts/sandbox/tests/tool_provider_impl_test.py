# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: c9a1f473eb7c
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Unit tests for tool_provider_impl aligned with grounding specifications."""

import unittest
from typing import Any, Mapping, Set, cast
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib.tool_provider import (
    ConversionErrorMessage,
    MissingMessage,
    ParameterConversionError,
    ParameterDescription,
    ParameterName,
    ParameterType,
    SomeParameterActualType,
    Tool,
    ToolDescription,
    ToolManager,
    ToolName,
    ToolParameter,
    ToolReminder,
    ToolResponse,
    ToolResponseContent,
    WireType,
)
from update_with_ai.parts.sandbox.lib.tool_provider_impl import (
    ToolManager as ToolManagerImpl,
    __initialize__,
)


class MockParameterType(ParameterType[Any, Any]):
    def __init__(
        self, actual_type: type[Any] = str, wire_type: type[Any] = str
    ) -> None:
        self._actual_type = actual_type
        self._wire_type = wire_type

    @property
    def actual_type(self) -> type[Any]:
        return self._actual_type

    @property
    def wire_type(self) -> type[Any]:
        return self._wire_type

    def convert(self, wire_value: Any) -> Any:
        return self._actual_type(wire_value)


class FailingParameterType(ParameterType[Any, Any]):
    @property
    def actual_type(self) -> type[Any]:
        return str

    @property
    def wire_type(self) -> type[Any]:
        return str

    def convert(self, wire_value: Any) -> Any:
        raise ParameterConversionError(message=ConversionErrorMessage("Invalid value"))


STRING_PARAMETER_TYPE = MockParameterType(str, str)
INTEGER_PARAMETER_TYPE = MockParameterType(int, int)
BOOLEAN_PARAMETER_TYPE = MockParameterType(bool, bool)
FLOAT_PARAMETER_TYPE = MockParameterType(float, float)


class DummyTool:
    def __init__(self, name: str, parameters: Set[ToolParameter[Any, Any]]) -> None:
        self._name = name
        self._parameters = parameters
        self.last_bindings: (
            Mapping[ToolParameter[Any, Any], SomeParameterActualType] | None
        ) = None

    @property
    def name(self) -> ToolName:
        return ToolName(self._name)

    @property
    def description(self) -> ToolDescription:
        return ToolDescription(f"Dummy tool {self._name}")

    @property
    def parameters(self) -> Mapping[ParameterName, ToolParameter[Any, Any]]:
        return {p.name: p for p in self._parameters}

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            ToolParameter[Any, Any], SomeParameterActualType
        ],
    ) -> ToolResponse:
        self.last_bindings = actual_parameter_bindings
        return ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=ToolResponseContent("dummy executed"),
            reminder=ToolReminder("remember this"),
        )


class ToolProviderImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parameter_type_converters(self) -> None:
        """CUJ: Converting values using parameter types."""
        str_type = MockParameterType(str, str)
        self.assertEqual(str_type.actual_type, str)
        self.assertEqual(str_type.wire_type, str)
        self.assertEqual(str_type.convert("test_string"), "test_string")

        int_type = MockParameterType(int, int)
        self.assertEqual(int_type.actual_type, int)
        self.assertEqual(int_type.wire_type, int)
        self.assertEqual(int_type.convert(123), 123)

        bool_type = MockParameterType(bool, bool)
        self.assertEqual(bool_type.actual_type, bool)
        self.assertEqual(bool_type.wire_type, bool)
        self.assertTrue(bool_type.convert(True))
        self.assertFalse(bool_type.convert(False))

        float_type = MockParameterType(float, float)
        self.assertEqual(float_type.actual_type, float)
        self.assertEqual(float_type.wire_type, float)
        self.assertEqual(float_type.convert(3.14), 3.14)

    def test_tool_manager_install_and_execute_success(self) -> None:
        """CUJ: Installing and successfully executing a tool."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)

            param = ToolParameter(
                name=ParameterName("arg1"),
                description=ParameterDescription("an argument"),
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=True,
            )
            tool = DummyTool("my_tool", {param})
            manager.install_tool(tool)

            self.assertIn(tool.name, manager.installed_tools)
            self.assertEqual(manager.installed_tools[tool.name], tool)

            wire_bindings: Mapping[ParameterName, WireType] = {
                ParameterName("arg1"): "val1"
            }
            resp = manager.execute_tool(ToolName("my_tool"), wire_bindings)

            # Requirement: When parameter mappings are successfully resolved, executing a tool by name executes the matching tool with the resolved actual parameter bindings and returns the tool's response.
            # Requirement: [ToolManager] Executing a tool by name with wire parameter bindings produces the tool response upon resolving parameter conversions.
            self.assertFalse(resp.is_failed)
            self.assertEqual(resp.content, "dummy executed")
            self.assertIsNotNone(tool.last_bindings)
            assert tool.last_bindings is not None
            self.assertEqual(tool.last_bindings[param], "val1")

    def test_tool_manager_unknown_tool(self) -> None:
        """CUJ: Executing a tool that is not installed fails."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            resp = manager.execute_tool(ToolName("nonexistent"), {})
            # Requirement: Executing a tool by name fails if no installed tool matches the requested name.
            self.assertTrue(resp.is_failed)

    def test_tool_manager_unknown_parameter(self) -> None:
        """CUJ: Executing a tool with an unrecognized parameter fails."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            tool = DummyTool("tool_no_params", set())
            manager.install_tool(tool)

            resp = manager.execute_tool(
                ToolName("tool_no_params"), {ParameterName("bogus"): "val"}
            )
            # Requirement: Executing a tool by name fails if a parameter name does not match any parameter of the tool, and reminds the agent that only declared parameters of the tool can be provided.
            self.assertTrue(resp.is_failed)
            self.assertIsNotNone(resp.reminder)

    def test_tool_manager_missing_required_parameter(self) -> None:
        """CUJ: Executing a tool without supplying a required parameter fails."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            param = ToolParameter(
                name=ParameterName("req_arg"),
                description=ParameterDescription("required"),
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=True,
            )
            tool = DummyTool("tool_req", {param})
            manager.install_tool(tool)

            resp = manager.execute_tool(ToolName("tool_req"), {})
            # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
            self.assertTrue(resp.is_failed)
            self.assertIsNotNone(resp.reminder)

    def test_tool_manager_missing_parameter_with_constant_missing_message(self) -> None:
        """CUJ: Executing a tool omitting a required parameter with constant missing_message evaluates function."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            param = ToolParameter(
                name=ParameterName("req_arg"),
                description=ParameterDescription("required"),
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=True,
                missing_message=lambda _: MissingMessage("custom guidance"),
            )
            tool = DummyTool("tool_req_msg", {param})
            manager.install_tool(tool)

            resp = manager.execute_tool(ToolName("tool_req_msg"), {})
            # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
            self.assertTrue(resp.is_failed)
            self.assertIn("custom guidance", resp.content)
            self.assertIsNotNone(resp.reminder)

    def test_tool_manager_missing_parameter_with_dynamic_missing_message(self) -> None:
        """CUJ: Executing a tool omitting a required parameter evaluates missing_message with supplied parameter names."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            req_param = ToolParameter(
                name=ParameterName("req_arg"),
                description=ParameterDescription("required"),
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=True,
                missing_message=lambda s: MissingMessage(
                    "flag present" if ParameterName("flag") in s else "flag omitted"
                ),
            )
            opt_param = ToolParameter(
                name=ParameterName("flag"),
                description=ParameterDescription("optional flag"),
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=False,
            )
            tool = DummyTool("tool_dyn_msg", {req_param, opt_param})
            manager.install_tool(tool)

            # Test 1: flag omitted
            resp1 = manager.execute_tool(ToolName("tool_dyn_msg"), {})
            # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
            self.assertTrue(resp1.is_failed)
            self.assertIn("flag omitted", resp1.content)

            # Test 2: flag present
            resp2 = manager.execute_tool(
                ToolName("tool_dyn_msg"), {ParameterName("flag"): "true"}
            )
            # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
            self.assertTrue(resp2.is_failed)
            self.assertIn("flag present", resp2.content)

    def test_tool_manager_default_parameter_value(self) -> None:
        """CUJ: Executing a tool omitting an optional parameter uses its default value."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            param = ToolParameter(
                name=ParameterName("batch_size"),
                description=ParameterDescription("batch size"),
                parameter_type=INTEGER_PARAMETER_TYPE,
                is_required=False,
                default_value=5,
            )
            tool = DummyTool("tool_with_default", {param})
            manager.install_tool(tool)

            resp = manager.execute_tool(ToolName("tool_with_default"), {})
            # Requirement: When an argument is omitted for a parameter that is not required and has a default value, the tool manager binds the default value as the actual parameter value.
            self.assertFalse(resp.is_failed)
            assert tool.last_bindings is not None
            self.assertEqual(tool.last_bindings[param], 5)

    def test_tool_manager_parameter_conversion_error(self) -> None:
        """CUJ: Parameter conversion error fails tool execution with diagnostic."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            param = ToolParameter(
                name=ParameterName("bad_arg"),
                description=ParameterDescription("bad argument"),
                parameter_type=FailingParameterType(),
                is_required=True,
            )
            tool = DummyTool("failing_tool", {param})
            manager.install_tool(tool)

            resp = manager.execute_tool(
                ToolName("failing_tool"), {ParameterName("bad_arg"): "val"}
            )
            self.assertTrue(resp.is_failed)
            self.assertIn("Invalid value", resp.content)
            self.assertIsNotNone(resp.reminder)

    def test_tool_manager_execute_tool_with_arguments(self) -> None:
        """CUJ: Executing a tool using raw arguments mapping."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            tool = DummyTool("dummy_tool", set())
            manager.install_tool(tool)
            # Requirement: Executing a tool by name with raw arguments produces the tool response.
            resp = cast(Any, manager).execute_tool_with_arguments(
                ToolName("dummy_tool"), {}
            )
            self.assertFalse(resp.is_failed)
            self.assertEqual(resp.content, "dummy executed")


if __name__ == "__main__":
    unittest.main()
