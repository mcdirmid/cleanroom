# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T03:03:42Z
# CHANGE: Rewrote tool_provider_impl tests with recording mock Tool, mock ParameterTypes (incl. one raising ParameterConversionError) and missing-note callback; covers install_tool/installed_tools and every execute_tool postcondition: unknown tool, unknown parameter (+reminder), missing required with/without note (+reminder, note receives present params), default binding, conversion error (+reminder), and successful dispatch with converted bindings returning the tool response.
# CODE_HASH: 6cf845de04da
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for tool_provider_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Any, Callable, Dict, List, Mapping, Optional, Set

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib import tool_provider
from update_with_ai.parts.sandbox.lib.tool_provider_impl import (
    ToolManager,
    __initialize__,
)


UNKNOWN_PARAMETER_REMINDER = "Only declared parameters of the tool can be provided."
MISSING_PARAMETER_REMINDER = "Required parameters of the tool must be supplied."
CONVERSION_REMINDER = "Parameters must match their declared wire types."


def _make_tool_name(name: str) -> tool_provider.ToolName:
    return tool_provider.ToolName(name)


def _make_param_name(name: str) -> tool_provider.ParameterName:
    return tool_provider.ParameterName(name)


def _make_response(content: str) -> tool_provider.ToolResponse:
    return tool_provider.ToolResponse(
        is_failed=False,
        is_terminated=False,
        content=tool_provider.ToolResponseContent(content),
        reminder=None,
        suppression_key=None,
        follow_up_tool_call=None,
    )


class _RecordingStrToIntType:
    """ParameterType converting string wire values to ints, recording calls."""

    def __init__(self) -> None:
        self.converted: List[str] = []

    @property
    def actual_type(self) -> type[int]:
        return int

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> int:
        self.converted.append(wire_value)
        return int(wire_value) * 10


class _RecordingStrType:
    """ParameterType converting string wire values to upper-cased strings."""

    def __init__(self) -> None:
        self.converted: List[str] = []

    @property
    def actual_type(self) -> type[str]:
        return str

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> str:
        self.converted.append(wire_value)
        return wire_value.upper()


class _FailingType:
    """ParameterType whose conversion always raises ParameterConversionError."""

    def __init__(self, message: str) -> None:
        self.message = message
        self.converted: List[str] = []

    @property
    def actual_type(self) -> type[int]:
        return int

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> int:
        self.converted.append(wire_value)
        raise tool_provider.ParameterConversionError(
            message=tool_provider.ConversionErrorMessage(self.message)
        )


class _RecordingMissingNote:
    """Missing-message callback recording the present parameter names it receives."""

    def __init__(self, note: str) -> None:
        self.note = note
        self.calls: List[Set[tool_provider.ParameterName]] = []

    def __call__(self, present: Set[tool_provider.ParameterName]) -> tool_provider.MissingMessage:
        self.calls.append(set(present))
        return tool_provider.MissingMessage(self.note)


def _make_parameter(
    name: str,
    parameter_type: tool_provider.ParameterType[Any, Any],
    is_required: bool,
    default_value: Optional[Any] = None,
    missing_message: Optional[
        Callable[[Set[tool_provider.ParameterName]], tool_provider.MissingMessage]
    ] = None,
) -> tool_provider.ToolParameter[Any, Any]:
    return tool_provider.ToolParameter(
        name=_make_param_name(name),
        description=tool_provider.ParameterDescription(f"{name} parameter"),
        parameter_type=parameter_type,
        is_required=is_required,
        default_value=default_value,
        missing_message=missing_message,
    )


class _RecordingTool:
    """Mock Tool recording every execution's actual parameter bindings."""

    def __init__(
        self,
        name: str,
        parameters: List[tool_provider.ToolParameter[Any, Any]],
        response: tool_provider.ToolResponse,
    ) -> None:
        self._name = _make_tool_name(name)
        self._parameters: Dict[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {
            p.name: p for p in parameters
        }
        self._response = response
        self.calls: List[
            Dict[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
        ] = []

    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    @property
    def description(self) -> tool_provider.ToolDescription:
        return tool_provider.ToolDescription(f"{self._name} description")

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        self.calls.append(dict(actual_parameter_bindings))
        return self._response


class ToolProviderImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence and singleton resolution."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            self.assertIsInstance(manager, ToolManager)
            self.assertIs(scope.get_singleton(tool_provider.ToolManager), manager)

    def test_install_tool_exposes_installed_tools(self) -> None:
        """Postcondition: install_tool MUST install the tool; installed_tools maps tool.name to the tool."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            self.assertEqual(dict(manager.installed_tools), {})
            alpha = _RecordingTool("alpha", [], _make_response("a"))
            beta = _RecordingTool("beta", [], _make_response("b"))
            manager.install_tool(alpha)
            manager.install_tool(beta)
            installed = manager.installed_tools
            self.assertEqual(set(installed.keys()), {_make_tool_name("alpha"), _make_tool_name("beta")})
            self.assertIs(installed[_make_tool_name("alpha")], alpha)
            self.assertIs(installed[_make_tool_name("beta")], beta)
            self.assertEqual(alpha.calls, [])
            self.assertEqual(beta.calls, [])

    def test_execute_unknown_tool(self) -> None:
        """Postcondition: WHEN no installed tool matches name, MUST fail citing the unknown tool and installed tools."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            tool = _RecordingTool("alpha", [], _make_response("a"))
            manager.install_tool(tool)
            response = manager.execute_tool(_make_tool_name("ghost"), {})
            self.assertTrue(response.is_failed)
            prefix = "Error: Unknown tool 'ghost'. Installed tools: "
            self.assertTrue(response.content.startswith(prefix), response.content)
            self.assertIn("alpha", response.content[len(prefix):])
            self.assertEqual(tool.calls, [])

    def test_execute_unknown_parameter(self) -> None:
        """Postcondition: WHEN bindings contain an undeclared parameter, MUST fail with unknown parameter error and reminder."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            count_type = _RecordingStrToIntType()
            label_type = _RecordingStrType()
            tool = _RecordingTool(
                "echo",
                [
                    _make_parameter("count", count_type, is_required=False, default_value=1),
                    _make_parameter("label", label_type, is_required=False, default_value="x"),
                ],
                _make_response("ok"),
            )
            manager.install_tool(tool)
            bindings: Dict[tool_provider.ParameterName, tool_provider.WireType] = {
                _make_param_name("bogus"): "1",
            }
            response = manager.execute_tool(_make_tool_name("echo"), bindings)
            self.assertTrue(response.is_failed)
            prefix = "Error: Unknown parameter 'bogus' for tool 'echo'. Valid parameters: "
            self.assertTrue(response.content.startswith(prefix), response.content)
            valid_listing = response.content[len(prefix):]
            self.assertIn("count", valid_listing)
            self.assertIn("label", valid_listing)
            self.assertEqual(response.reminder, UNKNOWN_PARAMETER_REMINDER)
            self.assertEqual(tool.calls, [])

    def test_execute_missing_required_parameter_with_note(self) -> None:
        """Postcondition: WHEN a required parameter with a missing note is omitted, MUST fail citing parameter and note."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            note = _RecordingMissingNote("path is needed when mode is set")
            tool = _RecordingTool(
                "edit",
                [
                    _make_parameter("path", _RecordingStrType(), is_required=True, missing_message=note),
                    _make_parameter("mode", _RecordingStrType(), is_required=True),
                ],
                _make_response("ok"),
            )
            manager.install_tool(tool)
            bindings: Dict[tool_provider.ParameterName, tool_provider.WireType] = {
                _make_param_name("mode"): "w",
            }
            response = manager.execute_tool(_make_tool_name("edit"), bindings)
            self.assertTrue(response.is_failed)
            self.assertEqual(
                response.content,
                "Error: Required parameter 'path' missing for tool 'edit'. "
                "Note: path is needed when mode is set",
            )
            self.assertEqual(response.reminder, MISSING_PARAMETER_REMINDER)
            self.assertEqual(note.calls, [{_make_param_name("mode")}])
            self.assertEqual(tool.calls, [])

    def test_execute_missing_required_parameter_without_note(self) -> None:
        """Postcondition: WHEN a required parameter lacking a missing note is omitted, MUST fail citing the parameter."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            tool = _RecordingTool(
                "edit",
                [
                    _make_parameter("path", _RecordingStrType(), is_required=True),
                    _make_parameter("mode", _RecordingStrType(), is_required=True),
                ],
                _make_response("ok"),
            )
            manager.install_tool(tool)
            bindings: Dict[tool_provider.ParameterName, tool_provider.WireType] = {
                _make_param_name("mode"): "w",
            }
            response = manager.execute_tool(_make_tool_name("edit"), bindings)
            self.assertTrue(response.is_failed)
            self.assertEqual(
                response.content,
                "Error: Required parameter 'path' missing for tool 'edit'.",
            )
            self.assertEqual(response.reminder, MISSING_PARAMETER_REMINDER)
            self.assertEqual(tool.calls, [])

    def test_execute_binds_default_for_omitted_optional_parameter(self) -> None:
        """Postcondition: WHEN a non-required parameter with a default is omitted, MUST bind the default value."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            label_type = _RecordingStrType()
            count_type = _RecordingStrToIntType()
            label = _make_parameter("label", label_type, is_required=True)
            count = _make_parameter("count", count_type, is_required=False, default_value=7)
            expected = _make_response("defaulted")
            tool = _RecordingTool("echo", [label, count], expected)
            manager.install_tool(tool)
            bindings: Dict[tool_provider.ParameterName, tool_provider.WireType] = {
                _make_param_name("label"): "hi",
            }
            response = manager.execute_tool(_make_tool_name("echo"), bindings)
            self.assertIs(response, expected)
            self.assertEqual(len(tool.calls), 1)
            actual = tool.calls[0]
            self.assertEqual(actual[count], 7)
            self.assertEqual(actual[label], "HI")
            self.assertEqual(label_type.converted, ["hi"])

    def test_execute_conversion_error(self) -> None:
        """Postcondition: WHEN conversion raises ParameterConversionError, MUST fail with invalid argument error and reminder."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            failing = _FailingType("expected digits")
            tool = _RecordingTool(
                "calc",
                [_make_parameter("amount", failing, is_required=True)],
                _make_response("ok"),
            )
            manager.install_tool(tool)
            bindings: Dict[tool_provider.ParameterName, tool_provider.WireType] = {
                _make_param_name("amount"): "abc",
            }
            response = manager.execute_tool(_make_tool_name("calc"), bindings)
            self.assertTrue(response.is_failed)
            self.assertEqual(
                response.content,
                "Error: Invalid argument for parameter 'amount': expected digits",
            )
            self.assertEqual(response.reminder, CONVERSION_REMINDER)
            self.assertEqual(failing.converted, ["abc"])
            self.assertEqual(tool.calls, [])

    def test_execute_tool_success(self) -> None:
        """Postcondition: WHEN parameters resolve, MUST execute the tool with resolved actual bindings and return its response."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ToolManager)
            count_type = _RecordingStrToIntType()
            label_type = _RecordingStrType()
            count = _make_parameter("count", count_type, is_required=True)
            label = _make_parameter("label", label_type, is_required=False, default_value="dflt")
            expected = _make_response("done")
            tool = _RecordingTool("echo", [count, label], expected)
            other = _RecordingTool("other", [], _make_response("other"))
            manager.install_tool(tool)
            manager.install_tool(other)
            bindings: Dict[tool_provider.ParameterName, tool_provider.WireType] = {
                _make_param_name("count"): "4",
                _make_param_name("label"): "abc",
            }
            response = manager.execute_tool(_make_tool_name("echo"), bindings)
            self.assertIs(response, expected)
            self.assertEqual(count_type.converted, ["4"])
            self.assertEqual(label_type.converted, ["abc"])
            self.assertEqual(len(tool.calls), 1)
            self.assertEqual(tool.calls[0], {count: 40, label: "ABC"})
            self.assertEqual(other.calls, [])


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
