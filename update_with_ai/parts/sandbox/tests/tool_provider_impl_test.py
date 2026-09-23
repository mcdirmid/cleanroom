"""Unit tests for tool_provider_impl aligned with grounding specifications."""

import unittest
from typing import Set
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.sandbox.lib.tool_provider import (
    BOOLEAN_PARAMETER_TYPE,
    FLOAT_PARAMETER_TYPE,
    INTEGER_PARAMETER_TYPE,
    STRING_PARAMETER_TYPE,
    ActualParameterBindings,
    Boolean,
    Dictionary,
    DictionaryParameterType,
    Float,
    IdentityParameterType,
    Integer,
    List,
    ListParameterType,
    Parameter,
    Response,
    String,
    Tool,
    ToolManager,
    WireParameterBindings,
)
from update_with_ai.parts.sandbox.lib.tool_provider_impl import (
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
        return Response(
            is_failed=False,
            is_terminated=False,
            content="dummy executed",
            reminder="remember this",
        )


class ToolProviderImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_identity_parameter_types(self) -> None:
        """CUJ: Converting values using identity parameter types."""
        str_type = IdentityParameterType(str)
        self.assertEqual(str_type.actual_type, str)
        self.assertEqual(str_type.wire_type, str)
        self.assertEqual(str_type.convert("test_string"), "test_string")

        int_type = IdentityParameterType(int)
        self.assertEqual(int_type.actual_type, int)
        self.assertEqual(int_type.wire_type, int)
        self.assertEqual(int_type.convert(123), 123)

        bool_type = IdentityParameterType(bool)
        self.assertEqual(bool_type.actual_type, bool)
        self.assertEqual(bool_type.wire_type, bool)
        self.assertTrue(bool_type.convert(True))
        self.assertFalse(bool_type.convert(False))

        float_type = IdentityParameterType(float)
        self.assertEqual(float_type.actual_type, float)
        self.assertEqual(float_type.wire_type, float)
        self.assertEqual(float_type.convert(3.14), 3.14)

    def test_list_parameter_type(self) -> None:
        """CUJ: Converting list parameter values with item parameter types."""
        list_type = ListParameterType(item_type=STRING_PARAMETER_TYPE)
        self.assertEqual(list_type.actual_type, list)
        self.assertEqual(list_type.wire_type, list)
        self.assertEqual(list_type.convert(["a", "b"]), ["a", "b"])

    def test_dictionary_parameter_type(self) -> None:
        """CUJ: Converting dictionary parameter values with key and value parameter types."""
        dict_type = DictionaryParameterType(
            value_type=INTEGER_PARAMETER_TYPE, key_type=STRING_PARAMETER_TYPE
        )
        self.assertEqual(dict_type.actual_type, dict)
        self.assertEqual(dict_type.wire_type, dict)
        self.assertEqual(dict_type.convert({"k": 42}), {"k": 42})

    def test_tool_manager_install_and_execute_success(self) -> None:
        """CUJ: Installing and successfully executing a tool."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)

            param = Parameter(
                name="arg1",
                description="an argument",
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=True,
            )
            tool = DummyTool("my_tool", {param})
            manager.install_tool(tool)

            self.assertIn(tool, manager.installed_tools)

            wire_bindings = WireParameterBindings(bindings={("arg1", "val1")})
            resp = manager.execute_tool("my_tool", wire_bindings)

            # Requirement: When parameter mappings are successfully resolved, executing a tool by name executes the matching tool with the resolved actual parameter bindings and returns the tool's response.
            # Requirement: [ToolManager] Executing a tool by name with wire parameter bindings produces the tool response upon resolving parameter conversions.
            self.assertFalse(resp.is_failed)
            self.assertEqual(resp.content, "dummy executed")
            self.assertIsNotNone(tool.last_bindings)
            assert tool.last_bindings is not None
            binding_dict = dict(tool.last_bindings.bindings)
            self.assertEqual(binding_dict[param], "val1")

    def test_tool_manager_unknown_tool(self) -> None:
        """CUJ: Executing a tool that is not installed fails."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            resp = manager.execute_tool(
                "nonexistent", WireParameterBindings(bindings=set())
            )
            # Requirement: Executing a tool by name fails if no installed tool matches the requested name.
            self.assertTrue(resp.is_failed)

    def test_tool_manager_unknown_parameter(self) -> None:
        """CUJ: Executing a tool with an unrecognized parameter fails."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            tool = DummyTool("tool_no_params", set())
            manager.install_tool(tool)

            resp = manager.execute_tool(
                "tool_no_params", WireParameterBindings(bindings={("bogus", "val")})
            )
            # Requirement: Executing a tool by name fails if a parameter name does not match any parameter of the tool, and reminds the agent that only declared parameters of the tool can be provided.
            self.assertTrue(resp.is_failed)
            self.assertIsNotNone(resp.reminder)

    def test_tool_manager_missing_required_parameter(self) -> None:
        """CUJ: Executing a tool without supplying a required parameter fails."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            param = Parameter(
                name="req_arg",
                description="required",
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=True,
            )
            tool = DummyTool("tool_req", {param})
            manager.install_tool(tool)

            resp = manager.execute_tool(
                "tool_req", WireParameterBindings(bindings=set())
            )
            # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
            self.assertTrue(resp.is_failed)
            self.assertIsNotNone(resp.reminder)

    def test_tool_manager_missing_parameter_with_constant_missing_message(self) -> None:
        """CUJ: Executing a tool omitting a required parameter with constant missing_message evaluates function."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            param = Parameter(
                name="req_arg",
                description="required",
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=True,
                missing_message=lambda _: "custom guidance",
            )
            tool = DummyTool("tool_req_msg", {param})
            manager.install_tool(tool)

            resp = manager.execute_tool(
                "tool_req_msg", WireParameterBindings(bindings=set())
            )
            # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
            self.assertTrue(resp.is_failed)
            self.assertIn("custom guidance", resp.content)
            self.assertIsNotNone(resp.reminder)

    def test_tool_manager_missing_parameter_with_dynamic_missing_message(self) -> None:
        """CUJ: Executing a tool omitting a required parameter evaluates missing_message with supplied parameter names."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            req_param = Parameter(
                name="req_arg",
                description="required",
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=True,
                missing_message=lambda s: "flag present" if "flag" in s else "flag omitted",
            )
            opt_param = Parameter(
                name="flag",
                description="optional flag",
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=False,
            )
            tool = DummyTool("tool_dyn_msg", {req_param, opt_param})
            manager.install_tool(tool)

            # Test 1: flag omitted
            resp1 = manager.execute_tool(
                "tool_dyn_msg", WireParameterBindings(bindings=set())
            )
            # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
            self.assertTrue(resp1.is_failed)
            self.assertIn("flag omitted", resp1.content)

            # Test 2: flag present
            resp2 = manager.execute_tool(
                "tool_dyn_msg", WireParameterBindings(bindings={("flag", "true")})
            )
            # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
            self.assertTrue(resp2.is_failed)
            self.assertIn("flag present", resp2.content)

    def test_tool_manager_default_parameter_value(self) -> None:
        """CUJ: Executing a tool omitting an optional parameter uses its default value."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            param = Parameter(
                name="batch_size",
                description="batch size",
                parameter_type=INTEGER_PARAMETER_TYPE,
                is_required=False,
                default_value=5,
            )
            tool = DummyTool("tool_with_default", {param})
            manager.install_tool(tool)

            resp = manager.execute_tool(
                "tool_with_default", WireParameterBindings(bindings=set())
            )
            # Requirement: When an argument is omitted for a parameter that is not required and has a default value, the tool manager binds the default value as the actual parameter value.
            self.assertFalse(resp.is_failed)
            assert tool.last_bindings is not None
            binding_dict = dict(tool.last_bindings.bindings)
            self.assertEqual(binding_dict[param], 5)

    def test_tool_manager_execute_tool_with_arguments(self) -> None:
        """CUJ: Executing a tool directly with argument dictionary."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            param = Parameter(
                name="target",
                description="target",
                parameter_type=STRING_PARAMETER_TYPE,
                is_required=True,
            )
            tool = DummyTool("tool_with_args", {param})
            manager.install_tool(tool)

            # Requirement: Executing a tool with arguments converts raw argument mappings into wire parameter bindings and executes the tool by name.
            resp = manager.execute_tool_with_arguments("tool_with_args", {"target": "widget.pyi"})
            self.assertFalse(resp.is_failed)
            assert tool.last_bindings is not None
            binding_dict = dict(tool.last_bindings.bindings)
            self.assertEqual(binding_dict[param], "widget.pyi")


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
