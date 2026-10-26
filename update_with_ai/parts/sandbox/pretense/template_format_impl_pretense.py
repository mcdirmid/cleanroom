"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for TemplateFormatter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.sandbox.lib import template_format
from update_with_ai.parts.sandbox.lib.template_format_impl import (
    TemplateFormatter,
    __initialize__,
)


def _make_template_text(text: str) -> template_format.TemplateText:
    return template_format.TemplateText(text)


def _make_template_key(key: str) -> template_format.TemplateKey:
    return template_format.TemplateKey(key)


def _make_parameters(values: Dict[str, Any]) -> Mapping[template_format.TemplateKey, Any]:
    params: Dict[template_format.TemplateKey, Any] = {}
    for key, value in values.items():
        params[_make_template_key(key)] = value
    return params


def _content_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


class _User:
    def __init__(self, name: str, role: str) -> None:
        self.name = name
        self.role = role


class _Project:
    def __init__(self, owner: _User, title: str) -> None:
        self.owner = owner
        self.title = title


class _Task:
    def __init__(self, title: str, priority: int) -> None:
        self.title = title
        self.priority = priority


# ==============================================================================
# 1. State Machine Protocol Definition
# ==============================================================================

@dataclass
class TemplateFormatterState:
    """Canonical model state for TemplateFormatter."""
    pass


proto = StateMachineProto[TemplateFormatterState]()


@proto.transition(template_format.TemplateFormatter.format_template)
def format_template(): pass

@format_template.arguments
def _(
    state: TemplateFormatterState,
    this: Any,
    text: template_format.TemplateText | NotBoundType = NotBound,
    parameters: Mapping[template_format.TemplateKey, Any] | NotBoundType = NotBound,
) -> Optional[Tuple[template_format.TemplateText, Mapping[template_format.TemplateKey, Any]]]:
    t = template_format.TemplateText("Hello <name>") if isinstance(text, NotBoundType) else text
    p = {template_format.TemplateKey("name"): "World"} if isinstance(parameters, NotBoundType) else parameters
    return (t, p)

@format_template.returns
def _(
    state: TemplateFormatterState,
    this: Any,
    text: template_format.TemplateText,
    parameters: Mapping[template_format.TemplateKey, Any],
    outcome: object = NotBound,
) -> Optional[Outcome[template_format.FormattedText]]:
    res = str(text)
    for k, v in parameters.items():
        res = res.replace(f"<{k}>", str(v))
    formatted = template_format.FormattedText(res)
    if isinstance(outcome, Value) and outcome.val == formatted:
        return outcome
    if outcome is NotBound:
        return Value(formatted)
    return None


# ==============================================================================
# 2. Comprehensive Non-Fuzz Tests
# ==============================================================================

class TestTemplateFormatReal(unittest.TestCase):
    """Direct verification of the real TemplateFormatter implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def _format(self, text: str, values: Dict[str, Any]) -> str:
        with enter_phase(agent_session, registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)
            result = formatter.format_template(
                _make_template_text(text), _make_parameters(values)
            )
        self.assertIsInstance(result, str)
        return str(result)

    def test_initialization(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)
            self.assertIsInstance(formatter, TemplateFormatter)
            by_interface = scope.get_singleton(template_format.TemplateFormatter)
            self.assertIs(formatter, by_interface)

    def test_plain_text_unchanged(self) -> None:
        result = self._format("Just plain text.", {})
        self.assertEqual(result.strip(), "Just plain text.")

    def test_placeholder_substitution(self) -> None:
        result = self._format(
            "Hello <name>, you have <count> tasks.",
            {"name": "Ada", "count": 3},
        )
        self.assertEqual(result.strip(), "Hello Ada, you have 3 tasks.")

    def test_placeholder_uses_string_representation(self) -> None:
        result = self._format("Ratio: <ratio>", {"ratio": 0.5})
        self.assertEqual(result.strip(), "Ratio: 0.5")

    def test_dot_separated_placeholder_resolution(self) -> None:
        result = self._format(
            "Role: <user.role>",
            {"user": {"role": "admin"}},
        )
        self.assertEqual(result.strip(), "Role: admin")

    def test_unbound_placeholder_preserved(self) -> None:
        result = self._format(
            "Hello <name>, see <missing> and <other.path>.",
            {"name": "Ada"},
        )
        self.assertEqual(
            result.strip(), "Hello Ada, see <missing> and <other.path>."
        )

    def test_block_conditional_truthy_includes_content(self) -> None:
        template = "Start\n<!-- IF show -->\nShown <name>\n<!-- ENDIF -->\nEnd\n"
        result = self._format(template, {"show": True, "name": "Ada"})
        self.assertEqual(_content_lines(result), ["Start", "Shown Ada", "End"])

    def test_block_conditional_falsy_omits_content(self) -> None:
        template = "Start\n<!-- IF show -->\nShown <name>\n<!-- ENDIF -->\nEnd\n"
        result = self._format(template, {"show": False, "name": "Ada"})
        self.assertEqual(_content_lines(result), ["Start", "End"])

    def test_block_conditional_absent_includes_content(self) -> None:
        template = "Start\n<!-- IF missing -->\nShown\n<!-- ENDIF -->\nEnd\n"
        result = self._format(template, {})
        self.assertEqual(_content_lines(result), ["Start", "Shown", "End"])

    def test_line_conditional_truthy_retains_line(self) -> None:
        template = "Keep\nActive line <!-- IF active -->\nAlso keep\n"
        result = self._format(template, {"active": True})
        self.assertEqual(_content_lines(result), ["Keep", "Active line", "Also keep"])

    def test_line_conditional_falsy_omits_line(self) -> None:
        template = "Keep\nActive line <!-- IF active -->\nAlso keep\n"
        result = self._format(template, {"active": False})
        self.assertEqual(_content_lines(result), ["Keep", "Also keep"])

    def test_line_conditional_absent_retains_line(self) -> None:
        template = "Keep\nLine <!-- IF absent -->\nAlso keep\n"
        result = self._format(template, {})
        self.assertEqual(_content_lines(result), ["Keep", "Line", "Also keep"])

    def test_block_loop_expands_items(self) -> None:
        template = "Items:\n<!-- FOR item IN items -->\n- <item>\n<!-- ENDFOR -->\nDone\n"
        result = self._format(template, {"items": ["apple", "banana"]})
        self.assertEqual(_content_lines(result), ["Items:", "- apple", "- banana", "Done"])

    def test_block_loop_binds_nested_item_paths(self) -> None:
        template = "Tasks:\n<!-- FOR task IN tasks -->\n<task.title> (p=<task.priority>)\n<!-- ENDFOR -->\n"
        tasks = [
            {"title": "Write spec", "priority": 1},
            {"title": "Implement", "priority": 2},
        ]
        result = self._format(template, {"tasks": tasks})
        self.assertEqual(
            _content_lines(result),
            ["Tasks:", "Write spec (p=1)", "Implement (p=2)"],
        )

    def test_block_loop_empty_sequence_yields_no_items(self) -> None:
        template = "Items:\n<!-- FOR item IN items -->\n- <item>\n<!-- ENDFOR -->\nDone\n"
        result = self._format(template, {"items": []})
        self.assertEqual(_content_lines(result), ["Items:", "Done"])

    def test_attribute_traversal_on_parameter_object(self) -> None:
        project = _Project(owner=_User(name="Ada", role="lead"), title="Cleanroom")
        result = self._format(
            "Project <project.title> led by <project.owner.name> (<project.owner.role>)",
            {"project": project},
        )
        self.assertEqual(
            result.strip(), "Project Cleanroom led by Ada (lead)"
        )

    def test_attribute_traversal_in_loop(self) -> None:
        tasks = [_Task("Spec", 1), _Task("Code", 2)]
        template = "<!-- FOR task IN tasks -->\n<task.title>=<task.priority>;\n<!-- ENDFOR -->"
        result = self._format(template, {"tasks": tasks})
        self.assertEqual(_content_lines(result), ["Spec=1;", "Code=2;"])

    def test_attribute_traversal_missing_attribute_leaves_placeholder(self) -> None:
        project = _Project(owner=_User(name="Ada", role="lead"), title="Cleanroom")
        result = self._format("Missing: <project.owner.missing_attr>", {"project": project})
        self.assertEqual(result.strip(), "Missing: <project.owner.missing_attr>")

    def test_nested_block_conditionals(self) -> None:
        template = (
            "Start\n"
            "<!-- IF outer -->\n"
            "Outer\n"
            "<!-- IF inner -->\n"
            "Inner\n"
            "<!-- ENDIF -->\n"
            "<!-- ENDIF -->\n"
            "End\n"
        )
        self.assertEqual(
            _content_lines(self._format(template, {"outer": True, "inner": True})),
            ["Start", "Outer", "Inner", "End"],
        )
        self.assertEqual(
            _content_lines(self._format(template, {"outer": True, "inner": False})),
            ["Start", "Outer", "End"],
        )
        self.assertEqual(
            _content_lines(self._format(template, {"outer": False, "inner": True})),
            ["Start", "End"],
        )

    def test_nested_loops(self) -> None:
        template = (
            "<!-- FOR group IN groups -->\n"
            "Group <group.name>:\n"
            "<!-- FOR item IN group.items -->\n"
            "- <item>\n"
            "<!-- ENDFOR -->\n"
            "<!-- ENDFOR -->\n"
        )
        groups = [
            {"name": "A", "items": ["a1", "a2"]},
            {"name": "B", "items": ["b1"]},
        ]
        result = self._format(template, {"groups": groups})
        self.assertEqual(
            _content_lines(result),
            ["Group A:", "- a1", "- a2", "Group B:", "- b1"],
        )

    def test_conditional_inside_loop(self) -> None:
        template = (
            "<!-- FOR item IN items -->\n"
            "<!-- IF item.active -->\n"
            "<item.name> is active\n"
            "<!-- ENDIF -->\n"
            "<!-- ENDFOR -->\n"
        )
        items = [
            {"name": "Task 1", "active": True},
            {"name": "Task 2", "active": False},
            {"name": "Task 3", "active": True},
        ]
        result = self._format(template, {"items": items})
        self.assertEqual(
            _content_lines(result),
            ["Task 1 is active", "Task 3 is active"],
        )

    def test_single_line_loop_expansion(self) -> None:
        template = "Item: <val> <!-- FOR val IN vals -->"
        result = self._format(template, {"vals": [1, 2, 3]})
        self.assertEqual(_content_lines(result), ["Item: 1", "Item: 2", "Item: 3"])



# ==============================================================================
# 3. Hypothesis Property Fuzz Testing
# ==============================================================================

class TestTemplateFormatFuzz(unittest.TestCase):
    """Property fuzz testing for TemplateFormatter."""

    @settings(max_examples=30)
    @given(
        name=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
        number=st.integers(min_value=0, max_value=1000),
    )
    def test_template_substitution_fuzz(self, name: str, number: int) -> None:
        registry = LifecycleRegistry()
        __initialize__(registry)
        with enter_phase(agent_session, registry=registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)
            out = formatter.format_template(
                _make_template_text("User: <user>, Count: <count>"),
                _make_parameters({"user": name, "count": number}),
            )
            self.assertEqual(str(out), f"User: {name}, Count: {number}")
