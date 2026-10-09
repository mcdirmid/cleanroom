# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T04:44:11Z
# CHANGE: Assert missing attributes on parameter objects leave placeholders unrendered
# CODE_HASH: c65de8ced2c4
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for template_format_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Any, Dict, List, Mapping

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_session import agent_session
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
    """Returns non-blank lines with surrounding whitespace removed.

    Blank-line normalization and whitespace left behind by stripped directive
    comments are not contracted precisely, so structural assertions compare
    the ordered sequence of non-blank content lines.
    """
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


class TemplateFormatImplTest(unittest.TestCase):
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
        """CUJ: Verify initial component presence and singleton resolution."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)
            self.assertIsInstance(formatter, TemplateFormatter)
            by_interface = scope.get_singleton(template_format.TemplateFormatter)
            self.assertIs(formatter, by_interface)

    def test_plain_text_unchanged(self) -> None:
        """Postcondition: Text without placeholders or directives is reproduced."""
        result = self._format("Just plain text.", {})
        self.assertEqual(result.strip(), "Just plain text.")

    def test_placeholder_substitution(self) -> None:
        """Postcondition: Bound angle-bracket placeholders are substituted."""
        result = self._format(
            "Hello <name>, you have <count> tasks.",
            {"name": "Ada", "count": 3},
        )
        self.assertEqual(result.strip(), "Hello Ada, you have 3 tasks.")

    def test_placeholder_uses_string_representation(self) -> None:
        """Postcondition: Substitution uses the value's string representation."""
        result = self._format("Ratio: <ratio>", {"ratio": 0.5})
        self.assertEqual(result.strip(), "Ratio: 0.5")

    def test_dot_separated_placeholder_resolution(self) -> None:
        """Postcondition: Dot-separated parameter paths resolve nested bindings."""
        result = self._format(
            "Role: <user.role>",
            {"user": {"role": "admin"}},
        )
        self.assertEqual(result.strip(), "Role: admin")

    def test_unbound_placeholder_preserved(self) -> None:
        """Postcondition: Placeholders whose keys are absent remain unrendered."""
        result = self._format(
            "Hello <name>, see <missing> and <other.path>.",
            {"name": "Ada"},
        )
        self.assertEqual(
            result.strip(), "Hello Ada, see <missing> and <other.path>."
        )

    def test_block_conditional_truthy_includes_content(self) -> None:
        """Postcondition: Truthy condition keys include enclosed block content."""
        template = "Start\n<!-- IF show -->\nShown <name>\n<!-- ENDIF -->\nEnd\n"
        result = self._format(template, {"show": True, "name": "Ada"})
        self.assertEqual(_content_lines(result), ["Start", "Shown Ada", "End"])
        self.assertNotIn("<!--", result)
        self.assertNotIn("-->", result)

    def test_block_conditional_falsy_omits_content(self) -> None:
        """Postcondition: Falsy condition keys omit enclosed block content."""
        template = "Start\n<!-- IF show -->\nShown\n<!-- ENDIF -->\nEnd\n"
        for falsy in (False, 0, "", []):
            with self.subTest(value=falsy):
                result = self._format(template, {"show": falsy})
                self.assertEqual(_content_lines(result), ["Start", "End"])
                self.assertNotIn("Shown", result)
                self.assertNotIn("<!--", result)

    def test_block_conditional_absent_includes_content(self) -> None:
        """Postcondition: Absent condition keys include enclosed block content."""
        template = "Start\n<!-- IF show -->\nShown\n<!-- ENDIF -->\nEnd\n"
        result = self._format(template, {})
        self.assertEqual(_content_lines(result), ["Start", "Shown", "End"])
        self.assertNotIn("<!--", result)

    def test_line_conditional_truthy_retains_line(self) -> None:
        """Postcondition: Truthy line-suffix conditionals retain the line."""
        template = "- first <!-- IF show -->\n- second\n"
        result = self._format(template, {"show": "yes"})
        self.assertEqual(_content_lines(result), ["- first", "- second"])
        self.assertNotIn("<!--", result)

    def test_line_conditional_falsy_omits_line(self) -> None:
        """Postcondition: Falsy line-suffix conditionals omit the line."""
        template = "- first <!-- IF show -->\n- second\n"
        result = self._format(template, {"show": False})
        self.assertEqual(_content_lines(result), ["- second"])
        self.assertNotIn("first", result)
        self.assertNotIn("<!--", result)

    def test_line_conditional_absent_retains_line(self) -> None:
        """Postcondition: Absent line-suffix conditionals retain the line."""
        template = "- first <!-- IF show -->\n- second\n"
        result = self._format(template, {})
        self.assertEqual(_content_lines(result), ["- first", "- second"])
        self.assertNotIn("<!--", result)

    def test_block_loop_expands_items(self) -> None:
        """Postcondition: Loop blocks repeat per sequence element binding the item."""
        template = "Items:\n<!-- FOR item IN items -->\n- <item>\n<!-- ENDFOR -->\nDone\n"
        result = self._format(template, {"items": ["a", "b", "c"]})
        self.assertEqual(
            _content_lines(result), ["Items:", "- a", "- b", "- c", "Done"]
        )
        self.assertNotIn("<!--", result)
        self.assertNotIn("<item>", result)

    def test_block_loop_binds_nested_item_paths(self) -> None:
        """Postcondition: Loop item variables resolve dot-separated item fields."""
        template = (
            "<!-- FOR task IN tasks -->\n"
            "- <task.name>: <task.state>\n"
            "<!-- ENDFOR -->\n"
        )
        result = self._format(
            template,
            {
                "tasks": [
                    {"name": "build", "state": "done"},
                    {"name": "test", "state": "pending"},
                ]
            },
        )
        self.assertEqual(
            _content_lines(result), ["- build: done", "- test: pending"]
        )
        self.assertNotIn("<!--", result)

    def test_block_loop_empty_sequence_yields_no_items(self) -> None:
        """Postcondition: Loop blocks repeat once per element; none for empty."""
        template = "Items:\n<!-- FOR item IN items -->\n- <item>\n<!-- ENDFOR -->\nDone\n"
        result = self._format(template, {"items": []})
        self.assertEqual(_content_lines(result), ["Items:", "Done"])
        self.assertNotIn("<!--", result)

    def test_attribute_traversal_on_parameter_object(self) -> None:
        """Postcondition: Parameter resolution traverses object attributes via dot paths."""
        project = _Project(owner=_User("Ada", "Admin"), title="Engine")
        result = self._format(
            "Project: <project.title>, Owner: <project.owner.name> (<project.owner.role>)",
            {"project": project},
        )
        self.assertEqual(result.strip(), "Project: Engine, Owner: Ada (Admin)")

    def test_attribute_traversal_in_loop(self) -> None:
        """Postcondition: Loop item attribute resolution traverses object attributes."""
        tasks = [_Task("Build", 1), _Task("Test", 2)]
        template = "<!-- FOR t IN tasks -->\n- <t.title>: <t.priority>\n<!-- ENDFOR -->\n"
        result = self._format(template, {"tasks": tasks})
        self.assertEqual(_content_lines(result), ["- Build: 1", "- Test: 2"])

    def test_attribute_traversal_missing_attribute_leaves_placeholder_unrendered(self) -> None:
        """Postcondition: Missing object attributes during dot path traversal leave placeholder unrendered."""
        project = _Project(owner=_User("Ada", "Admin"), title="Engine")
        result = self._format(
            "Project: <project.title>, Missing: <project.missing_attr>, NestedMissing: <project.owner.missing_field>",
            {"project": project},
        )
        self.assertEqual(
            result.strip(),
            "Project: Engine, Missing: <project.missing_attr>, NestedMissing: <project.owner.missing_field>",
        )

    def test_attribute_traversal_in_loop_missing_attribute_leaves_placeholder_unrendered(self) -> None:
        """Postcondition: Missing object attributes during loop item traversal leave placeholder unrendered."""
        tasks = [_Task("Build", 1)]
        template = "<!-- FOR t IN tasks -->\n- <t.title>: <t.missing_prop>\n<!-- ENDFOR -->\n"
        result = self._format(template, {"tasks": tasks})
        self.assertEqual(_content_lines(result), ["- Build: <t.missing_prop>"])

    def test_nested_block_conditionals(self) -> None:
        """Postcondition: Nested block conditionals evaluate according to their respective truthiness."""
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
        # Both true
        res1 = self._format(template, {"outer": True, "inner": True})
        self.assertEqual(_content_lines(res1), ["Start", "Outer", "Inner", "End"])

        # Outer true, inner false
        res2 = self._format(template, {"outer": True, "inner": False})
        self.assertEqual(_content_lines(res2), ["Start", "Outer", "End"])

        # Outer false
        res3 = self._format(template, {"outer": False, "inner": True})
        self.assertEqual(_content_lines(res3), ["Start", "End"])

    def test_nested_loops(self) -> None:
        """Postcondition: Nested loops expand inner items for each outer element."""
        template = (
            "<!-- FOR group IN groups -->\n"
            "Group: <group.name>\n"
            "<!-- FOR item IN group.items -->\n"
            "- <item>\n"
            "<!-- ENDFOR -->\n"
            "<!-- ENDFOR -->\n"
        )
        data = {
            "groups": [
                {"name": "G1", "items": ["i1", "i2"]},
                {"name": "G2", "items": ["i3"]},
            ]
        }
        result = self._format(template, data)
        self.assertEqual(
            _content_lines(result),
            ["Group: G1", "- i1", "- i2", "Group: G2", "- i3"],
        )

    def test_conditional_inside_loop(self) -> None:
        """Postcondition: Conditionals within loops filter elements based on condition truthiness."""
        template = (
            "<!-- FOR task IN tasks -->\n"
            "<!-- IF task.active -->\n"
            "- <task.name>\n"
            "<!-- ENDIF -->\n"
            "<!-- ENDFOR -->\n"
        )
        tasks = [
            {"name": "Task1", "active": True},
            {"name": "Task2", "active": False},
            {"name": "Task3", "active": True},
        ]
        result = self._format(template, {"tasks": tasks})
        self.assertEqual(_content_lines(result), ["- Task1", "- Task3"])

    def test_loop_inside_conditional(self) -> None:
        """Postcondition: Loops within conditionals are rendered or omitted by condition."""
        template = (
            "<!-- IF show -->\n"
            "<!-- FOR item IN items -->\n"
            "- <item>\n"
            "<!-- ENDFOR -->\n"
            "<!-- ENDIF -->\n"
        )
        res_shown = self._format(template, {"show": True, "items": ["x", "y"]})
        self.assertEqual(_content_lines(res_shown), ["- x", "- y"])

        res_hidden = self._format(template, {"show": False, "items": ["x", "y"]})
        self.assertEqual(_content_lines(res_hidden), [])

    def test_single_line_loop_expansion(self) -> None:
        """Postcondition: Line-suffix loop directives expand repeated lines for each sequence item."""
        template = "- <item> <!-- FOR item IN items -->\n"
        result = self._format(template, {"items": ["apple", "banana", "cherry"]})
        self.assertEqual(
            _content_lines(result), ["- apple", "- banana", "- cherry"]
        )
        self.assertNotIn("<!--", result)

    def test_single_line_loop_empty_sequence(self) -> None:
        """Postcondition: Line-suffix loop directives omit line when sequence is empty."""
        template = "Prefix\n- <item> <!-- FOR item IN items -->\nSuffix\n"
        result = self._format(template, {"items": []})
        self.assertEqual(_content_lines(result), ["Prefix", "Suffix"])
        self.assertNotIn("<!--", result)

    def test_single_line_loop_with_attribute_traversal(self) -> None:
        """Postcondition: Line-suffix loop directives resolve attribute paths on items."""
        tasks = [_Task("Build", 1), _Task("Deploy", 2)]
        template = "| <t.title> | <t.priority> | <!-- FOR t IN tasks -->\n"
        result = self._format(template, {"tasks": tasks})
        self.assertEqual(
            _content_lines(result),
            ["| Build | 1 |", "| Deploy | 2 |"],
        )
        self.assertNotIn("<!--", result)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
