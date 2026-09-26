"""Unit tests for cleanroom_dag_cli.py."""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from update_with_ai.support.lib import cleanroom_dag_cli


class CleanroomDagCliTest(unittest.TestCase):
    def test_normalize_addresses(self) -> None:
        self.assertEqual(cleanroom_dag_cli.normalize_role_address("test"), "//update_python_with_ai:test")
        self.assertEqual(cleanroom_dag_cli.normalize_role_address(":test"), "//update_python_with_ai:test")
        self.assertEqual(
            cleanroom_dag_cli.normalize_role_address("//update_python_with_ai:test"),
            "//update_python_with_ai:test",
        )
        self.assertEqual(
            cleanroom_dag_cli.normalize_unit_address("//update_with_ai/parts/systems/"),
            "//update_with_ai/parts/systems",
        )

    def test_resolve_roles_hierarchy(self) -> None:
        # High role has no dependencies
        self.assertEqual(
            cleanroom_dag_cli.resolve_roles("high", "//pkg/unit"),
            ["//update_python_with_ai:high"],
        )

        # Requirements role depends on high
        self.assertEqual(
            cleanroom_dag_cli.resolve_roles("requirements", "//pkg/unit"),
            ["//update_python_with_ai:high", "//update_python_with_ai:requirements"],
        )

        # Grounding role depends on requirements and high
        self.assertEqual(
            cleanroom_dag_cli.resolve_roles("grounding", "//pkg/unit"),
            [
                "//update_python_with_ai:high",
                "//update_python_with_ai:requirements",
                "//update_python_with_ai:grounding",
            ],
        )

        # Low role (backward-compatible alias) depends on requirements and high
        self.assertEqual(
            cleanroom_dag_cli.resolve_roles("low", "//pkg/unit"),
            [
                "//update_python_with_ai:high",
                "//update_python_with_ai:requirements",
                "//update_python_with_ai:low",
            ],
        )

        # Lib role depends on grounding, requirements, and high
        self.assertEqual(
            cleanroom_dag_cli.resolve_roles("lib", "//pkg/unit"),
            [
                "//update_python_with_ai:high",
                "//update_python_with_ai:requirements",
                "//update_python_with_ai:grounding",
                "//update_python_with_ai:lib",
            ],
        )

        # Test role depends on lib, grounding, requirements, high
        self.assertEqual(
            cleanroom_dag_cli.resolve_roles("test", "//pkg/unit"),
            [
                "//update_python_with_ai:high",
                "//update_python_with_ai:requirements",
                "//update_python_with_ai:grounding",
                "//update_python_with_ai:lib",
                "//update_python_with_ai:test",
            ],
        )

        # Coverage role depends on qa, test, lib, grounding, requirements, high
        roles_coverage = cleanroom_dag_cli.resolve_roles("coverage", "//pkg/unit")
        self.assertEqual(roles_coverage[-1], "//update_python_with_ai:coverage")
        self.assertIn("//update_python_with_ai:high", roles_coverage)
        self.assertIn("//update_python_with_ai:requirements", roles_coverage)
        self.assertIn("//update_python_with_ai:grounding", roles_coverage)
        self.assertIn("//update_python_with_ai:lib", roles_coverage)
        self.assertIn("//update_python_with_ai:test", roles_coverage)
        self.assertIn("//update_python_with_ai:qa", roles_coverage)

        # Unknown custom role
        self.assertEqual(
            cleanroom_dag_cli.resolve_roles("//custom:role", "//pkg/unit"),
            ["//custom:role"],
        )

    def test_inject_change(self) -> None:
        res = cleanroom_dag_cli.inject_change("//pkg/unit", "high", "Specification updated")
        self.assertIn(res["status"], ("injected", "recorded"))
        self.assertEqual(res["unit"], "//pkg/unit")
        self.assertEqual(res["role"], "//update_python_with_ai:high")
        self.assertEqual(res["message"], "Specification updated")

    def test_get_subgraph_status(self) -> None:
        res = cleanroom_dag_cli.get_subgraph_status("//pkg/unit", "test")
        self.assertEqual(res["unit"], "//pkg/unit")
        self.assertEqual(res["role"], "//update_python_with_ai:test")
        self.assertIn("is_complete", res)
        self.assertIsInstance(res["roles"], list)

    def test_main_cli_resolve_roles(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            ret = cleanroom_dag_cli.main(["resolve-roles", "--role", "test", "--unit", "//pkg/unit"])
            self.assertEqual(ret, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertEqual(data["target"]["role"], "//update_python_with_ai:test")
            self.assertEqual(data["target"]["unit"], "//pkg/unit")
            self.assertEqual(len(data["roles"]), 5)

    def test_main_cli_inject_change(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            ret = cleanroom_dag_cli.main([
                "inject-change",
                "--role", "high",
                "--unit", "pkg/unit",
                "--message", "HLS edit"
            ])
            self.assertEqual(ret, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertIn("status", data)

    def test_main_cli_status(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            ret = cleanroom_dag_cli.main(["status", "--role", "test", "--unit", "pkg/unit"])
            self.assertEqual(ret, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertEqual(data["role"], "//update_python_with_ai:test")


    def test_resolve_define_node_target(self) -> None:
        # Full package label with role suffix
        role, unit = cleanroom_dag_cli.resolve_define_node_target(
            "//testing/parts/sandbox:sandbox_asm_qa"
        )
        self.assertEqual(role, "//update_python_with_ai:qa")
        self.assertEqual(unit, "//testing/parts/sandbox:sandbox_asm")

        # Relative label with role suffix
        role, unit = cleanroom_dag_cli.resolve_define_node_target(":sandbox_asm_lib")
        self.assertEqual(role, "//update_python_with_ai:lib")
        self.assertEqual(unit, ":sandbox_asm")

        # Plain name with role suffix
        role, unit = cleanroom_dag_cli.resolve_define_node_target("sandbox_asm_high")
        self.assertEqual(role, "//update_python_with_ai:high")
        self.assertEqual(unit, ":sandbox_asm")

    def test_parse_target_args(self) -> None:
        # 1. Single define_node shortcut positional
        role, unit, target = cleanroom_dag_cli.parse_target_args(
            positional=["//testing/parts/sandbox:sandbox_asm_qa"]
        )
        self.assertEqual(role, "//update_python_with_ai:qa")
        self.assertEqual(unit, "//testing/parts/sandbox:sandbox_asm")
        self.assertEqual(target, "//testing/parts/sandbox:sandbox_asm_qa")

        # 2. Two positional arguments: [role, unit]
        role, unit, target = cleanroom_dag_cli.parse_target_args(
            positional=["//update_python_with_ai:qa", "//testing/parts/sandbox:sandbox_asm"]
        )
        self.assertEqual(role, "//update_python_with_ai:qa")
        self.assertEqual(unit, "//testing/parts/sandbox:sandbox_asm")
        self.assertIsNone(target)

        # 3. Two positional arguments reversed: [unit, role]
        role, unit, target = cleanroom_dag_cli.parse_target_args(
            positional=["//testing/parts/sandbox:sandbox_asm", "qa"]
        )
        self.assertEqual(role, "//update_python_with_ai:qa")
        self.assertEqual(unit, "//testing/parts/sandbox:sandbox_asm")
        self.assertIsNone(target)

        # 4. Target flag
        role, unit, target = cleanroom_dag_cli.parse_target_args(
            target="//testing/parts/sandbox:sandbox_asm_qa"
        )
        self.assertEqual(role, "//update_python_with_ai:qa")
        self.assertEqual(unit, "//testing/parts/sandbox:sandbox_asm")
        self.assertEqual(target, "//testing/parts/sandbox:sandbox_asm_qa")

    def test_main_cli_resolve_roles_shortcut(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            ret = cleanroom_dag_cli.main(["resolve-roles", "//testing/parts/sandbox:sandbox_asm_qa"])
            self.assertEqual(ret, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertEqual(data["target"]["role"], "//update_python_with_ai:qa")
            self.assertEqual(data["target"]["unit"], "//testing/parts/sandbox:sandbox_asm")
            self.assertEqual(data["target"]["node_target"], "//testing/parts/sandbox:sandbox_asm_qa")
            self.assertEqual(len(data["roles"]), 6)

    def test_main_cli_inject_change_shortcut(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            ret = cleanroom_dag_cli.main([
                "inject-change",
                "//testing/parts/sandbox:sandbox_asm_high",
                "Spec update via shortcut",
            ])
            self.assertEqual(ret, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertIn("status", data)
            self.assertEqual(data["role"], "//update_python_with_ai:high")
            self.assertEqual(data["unit"], "//testing/parts/sandbox:sandbox_asm")

    def test_main_cli_status_shortcut(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            ret = cleanroom_dag_cli.main(["status", "//testing/parts/sandbox:sandbox_asm_qa"])
            self.assertEqual(ret, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertEqual(data["role"], "//update_python_with_ai:qa")
            self.assertEqual(data["unit"], "//testing/parts/sandbox:sandbox_asm")

    def test_main_cli_next_batch(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            ret = cleanroom_dag_cli.main(["next-batch", "--role", "qa", "--unit", "//testing/parts/sandbox:sandbox_asm"])
            self.assertEqual(ret, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertEqual(data["role"], "//update_python_with_ai:qa")
            self.assertEqual(data["unit"], "//testing/parts/sandbox:sandbox_asm")
            self.assertIn("is_complete", data)
            self.assertIn("batch", data)

    def test_main_cli_next_batch_with_batch_size(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            ret = cleanroom_dag_cli.main([
                "next-batch",
                "--role", "qa",
                "--unit", "//testing/parts/sandbox:sandbox_asm",
                "--batch-size", "1",
            ])
            self.assertEqual(ret, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertIn("batch", data)
            if data["batch"]:
                self.assertLessEqual(len(data["batch"]), 1)


if __name__ == "__main__":
    unittest.main()
