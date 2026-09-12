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
            self.assertEqual(result, expected)

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


if __name__ == "__main__":
    unittest.main()
