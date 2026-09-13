import unittest
from lib.template_format import TemplateFormatter
from lib.template_format_impl import (
    TemplateFormatter as TemplateFormatterImpl,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


class TemplateFormatImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_variable_interpolation(self) -> None:
        """CUJ: Variable substitution with dot lookup and preservation of unbound parameters."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)
            self.assertIsInstance(formatter, TemplateFormatterImpl)

            template = "# <service_name>\nPackage: <pkg.name>\nOwner: <pkg.lead.user>\nUnknown: <unbound_param>"
            params = {
                "service_name": "AuthService",
                "pkg": {
                    "name": "auth_core",
                    "lead": {"user": "alice"},
                },
            }

            result = formatter.format_template(template, params)
            expected = "# AuthService\nPackage: auth_core\nOwner: alice\nUnknown: <unbound_param>"
            # Requirement: Replaces parameter placeholder tokens matching dot-separated keys in the parameters with string representations of their resolved values.
            self.assertEqual(result, expected)

            # Object attribute lookup
            class Lead:
                def __init__(self, username: str) -> None:
                    self.username = username

            obj_params = {"team": Lead("charlie")}
            obj_result = formatter.format_template("Lead: <team.username>", obj_params)
            # Requirement: Replaces parameter placeholder tokens matching dot-separated keys in the parameters with string representations of their resolved values.
            self.assertEqual(obj_result, "Lead: charlie")

    def test_line_suffix_conditional(self) -> None:
        """CUJ: Single-line conditional inclusion and exclusion."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)

            template = (
                "Header\n"
                "Line 1 <!-- if: show_line_1 -->\n"
                "Line 2 <!-- if: hide_line_2 -->\n"
                "Line 3 <!-- if: missing_flag -->\n"
                "Footer"
            )
            params = {
                "show_line_1": True,
                "hide_line_2": False,
            }

            result = formatter.format_template(template, params)
            expected = "Header\nLine 1\nLine 3\nFooter"
            self.assertEqual(result, expected)

    def test_line_suffix_loop(self) -> None:
        """CUJ: Single-line loop repetition for bullet lists and table rows."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)

            template = (
                "## Dependencies\n"
                "- `<dep>` <!-- for: dep in dependencies -->\n"
                "| Name | Type |\n"
                "| --- | --- |\n"
                "| `<col.name>` | `<col.type>` | <!-- for: col in columns -->"
            )
            params = {
                "dependencies": ["lib_a", "lib_b"],
                "columns": [
                    {"name": "id", "type": "int"},
                    {"name": "name", "type": "str"},
                ],
            }

            result = formatter.format_template(template, params)
            expected = (
                "## Dependencies\n"
                "- `lib_a`\n"
                "- `lib_b`\n"
                "| Name | Type |\n"
                "| --- | --- |\n"
                "| `id` | `int` |\n"
                "| `name` | `str` |"
            )
            self.assertEqual(result, expected)

    def test_block_conditional(self) -> None:
        """CUJ: Multi-line block conditional evaluation."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)

            template = (
                "Intro\n"
                "<!-- if: has_terms -->\n"
                "## Terms\n"
                "- <term>: definition\n"
                "<!-- endif -->\n"
                "<!-- if: has_notes -->\n"
                "## Notes\n"
                "- note\n"
                "<!-- endif -->\n"
                "Outro"
            )
            params = {
                "has_terms": True,
                "has_notes": False,
                "term": "auth_token",
            }

            result = formatter.format_template(template, params)
            expected = "Intro\n## Terms\n- auth_token: definition\nOutro"
            self.assertEqual(result, expected)

    def test_block_loop(self) -> None:
        """CUJ: Multi-line block loop repetition across elements."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)

            template = (
                "# Operations\n"
                "<!-- for: op in operations -->\n"
                "### `<op.name>`\n"
                "**Purpose:** <op.purpose>\n"
                "<!-- endfor -->"
            )
            params = {
                "operations": [
                    {"name": "login", "purpose": "Authenticate user"},
                    {"name": "logout", "purpose": "End session"},
                ]
            }

            result = formatter.format_template(template, params)
            expected = (
                "# Operations\n"
                "### `login`\n"
                "**Purpose:** Authenticate user\n"
                "### `logout`\n"
                "**Purpose:** End session"
            )
            self.assertEqual(result, expected)

    def test_formatter_whitespace_normalization(self) -> None:
        """CUJ: Surviving extra blank lines injected around HTML comments by formatters."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)

            # Prettier typically formats block comments with surrounding blank lines
            formatted_template = (
                "# Header\n"
                "\n"
                "<!-- for: item in items -->\n"
                "\n"
                "- `<item>`\n"
                "\n"
                "<!-- endfor -->\n"
                "\n"
                "## Footer"
            )
            params = {"items": ["item1", "item2"]}

            result = formatter.format_template(formatted_template, params)
            expected = "# Header\n\n- `item1`\n- `item2`\n\n## Footer"
            self.assertEqual(result, expected)

    def test_nested_and_unbound_loops(self) -> None:
        """CUJ: Nested loops and unbound loop variable handling."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)

            # Unbound line-suffix loop: retains line and placeholder
            line_tmpl = "- <item> <!-- for: item in missing_items -->"
            # Requirement: Identifies line-suffix loop comments matching collection iteration markers, repeating the preceding line content for each item in the resolved sequence with the item variable bound in the parameter context.
            # Requirement: Retains parameter placeholder tokens whose keys do not resolve to values in the parameters without modification.
            res_line = formatter.format_template(line_tmpl, {})
            self.assertEqual(res_line, "- <item>")

            # Nested block loop
            nested_tmpl = (
                "<!-- for: group in groups -->\n"
                "Group: <group.name>\n"
                "<!-- for: member in group.members -->\n"
                "- <member>\n"
                "<!-- endfor -->\n"
                "<!-- endfor -->"
            )
            nested_params = {
                "groups": [
                    {"name": "Admins", "members": ["alice", "bob"]},
                ]
            }
            # Requirement: Identifies block loop markers enclosing multi-line sections, repeating enclosed lines for each element in the resolved sequence with the loop variable bound in the parameter context.
            res_nested = formatter.format_template(nested_tmpl, nested_params)
            self.assertEqual(res_nested, "Group: Admins\n- alice\n- bob")

            # Unbound block loop: renders body with unbound context
            unbound_block_tmpl = (
                "<!-- for: x in absent_list -->\n"
                "Item: <x>\n"
                "<!-- endfor -->"
            )
            # Requirement: Identifies block loop markers enclosing multi-line sections, repeating enclosed lines for each element in the resolved sequence with the loop variable bound in the parameter context.
            res_unbound_block = formatter.format_template(unbound_block_tmpl, {})
            self.assertEqual(res_unbound_block, "Item: <x>")

    def test_nested_and_unbound_conditionals(self) -> None:
        """CUJ: Nested conditionals and unbound condition variable handling."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            formatter = scope.get_singleton(TemplateFormatter)

            # Nested block if
            nested_if_tmpl = (
                "<!-- if: outer_flag -->\n"
                "Outer\n"
                "<!-- if: inner_flag -->\n"
                "Inner\n"
                "<!-- endif -->\n"
                "<!-- endif -->"
            )
            # Requirement: Identifies block conditional markers enclosing multi-line sections, including enclosed lines when the condition key evaluates to true and omitting enclosed lines when false.
            res_nested_if = formatter.format_template(
                nested_if_tmpl, {"outer_flag": True, "inner_flag": True}
            )
            self.assertEqual(res_nested_if, "Outer\nInner")

            # Unbound block if: retains body content
            unbound_if_tmpl = (
                "<!-- if: absent_flag -->\n"
                "Default text\n"
                "<!-- endif -->"
            )
            # Requirement: Identifies block conditional markers enclosing multi-line sections, including enclosed lines when the condition key evaluates to true and omitting enclosed lines when false.
            res_unbound_if = formatter.format_template(unbound_if_tmpl, {})
            self.assertEqual(res_unbound_if, "Default text")


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
