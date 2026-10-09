#!/usr/bin/env python3
"""linter_gates_test.py — Python test wrapper for Cleanroom specification linters."""

import os
import subprocess
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))


class LinterGatesTest(unittest.TestCase):
    def test_high_lint_gate(self) -> None:
        """Runs high_lint_test.sh validation cases."""
        sh_path = os.path.join(DIR, "high_lint_test.sh")
        proc = subprocess.run(["bash", sh_path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")

    def test_low_lint_gate(self) -> None:
        """Runs low_lint_test.sh validation cases."""
        sh_path = os.path.join(DIR, "low_lint_test.sh")
        proc = subprocess.run(["bash", sh_path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")

    def test_lib_lint_gate(self) -> None:
        """Runs lib_lint_test.sh validation cases."""
        sh_path = os.path.join(DIR, "lib_lint_test.sh")
        proc = subprocess.run(["bash", sh_path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")

    def test_test_lint_gate(self) -> None:
        """Runs test_lint_test.sh validation cases."""
        sh_path = os.path.join(DIR, "test_lint_test.sh")
        proc = subprocess.run(["bash", sh_path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")


if __name__ == "__main__":
    unittest.main()
