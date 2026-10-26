#!/usr/bin/env python3
"""pretense_lint_test.py — Unit tests for pretense scaffolding and lint verification."""

from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest

def find_repo_root() -> str:
    ws = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if ws and os.path.isdir(os.path.join(ws, "update_python_with_ai")):
        return ws
    cur = os.path.abspath(os.path.dirname(__file__))
    while cur and cur != os.path.dirname(cur):
        if os.path.isdir(os.path.join(cur, "update_python_with_ai")):
            return cur
        cur = os.path.dirname(cur)
    return os.getcwd()


REPO_ROOT = find_repo_root()
for p in [
    REPO_ROOT,
    os.path.join(REPO_ROOT, "update_python_with_ai"),
    os.path.join(REPO_ROOT, "update_python_with_ai", "support", "lib"),
]:
    if p not in sys.path and os.path.isdir(p):
        sys.path.insert(0, p)

from update_python_with_ai.support.lib.pretense_lint import (
    check_pretense_imports,
    check_pretense_structure,
    generate_pretense_scaffold,
    is_uninitialized_pretense_module,
)


class PretenseLintTest(unittest.TestCase):
    def test_single_service_scaffold(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".pyi", delete=False) as f:
            f.write(
                "from support.lib.lifecycle import Singleton, system\n\n"
                "class SingleService:\n"
                "    def do_work(self, item_id: str, count: int = 1) -> bool: ...\n"
            )
            pyi_path = f.name
        try:
            scaffold = generate_pretense_scaffold(
                pyi_path=pyi_path,
                stem="single_service_impl_pretense",
                impl_stem="single_service_impl",
                lib_pkg="my_pkg",
            )
            # Must parse without syntax errors
            tree = ast.parse(scaffold)
            self.assertEqual(len(check_pretense_structure(tree)), 0)
            self.assertEqual(len(check_pretense_imports(scaffold)), 0)
            self.assertIn("class SingleServiceState:", scaffold)
            self.assertIn("def make_single_service_fake(", scaffold)
            self.assertIn("def make_sut() -> SingleService:", scaffold)
            self.assertIn("@proto.transition(SingleService.do_work)", scaffold)
            self.assertIn('"sample_item_id"', scaffold)
            self.assertIn("1", scaffold)
        finally:
            os.unlink(pyi_path)

    def test_multi_service_aggregate_scaffold(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".pyi", delete=False) as f:
            f.write(
                "from support.lib.lifecycle import Singleton, system\n\n"
                "class ServiceAlpha:\n"
                "    def step_a(self, node_id: str) -> None: ...\n\n"
                "class ServiceBeta:\n"
                "    def step_b(self, flag: bool = True) -> int: ...\n\n"
                "class ServiceError(Exception):\n"
                "    pass\n"
            )
            pyi_path = f.name
        try:
            scaffold = generate_pretense_scaffold(
                pyi_path=pyi_path,
                stem="pipeline_engine_impl_pretense",
                impl_stem="pipeline_engine_impl",
                lib_pkg="pipeline_pkg",
            )
            tree = ast.parse(scaffold)
            self.assertEqual(len(check_pretense_structure(tree)), 0)
            self.assertEqual(len(check_pretense_imports(scaffold)), 0)

            # Both services must be imported, error class excluded from transitions
            self.assertIn("from pipeline_pkg.pipeline_engine_impl import ServiceAlpha, ServiceBeta, __initialize__", scaffold)
            self.assertNotIn("@proto.transition(ServiceError", scaffold)

            # Transitions for both services
            self.assertIn("@proto.transition(ServiceAlpha.step_a)", scaffold)
            self.assertIn("@proto.transition(ServiceBeta.step_b)", scaffold)

            # Multi-service fakes factory
            self.assertIn("def make_pipeline_engine_fakes(", scaffold)
            self.assertIn("Tuple[ServiceAlpha, ServiceBeta]", scaffold)

            # Aggregate SUT
            self.assertIn("class PipelineEngineSUT:", scaffold)
            self.assertIn("tier = system", scaffold)
            self.assertIn('self.__dict__["_services"] = ()', scaffold)
            self.assertIn("def make_sut() -> PipelineEngineSUT:", scaffold)
        finally:
            os.unlink(pyi_path)

    def test_uninitialized_module_detection(self) -> None:
        self.assertTrue(is_uninitialized_pretense_module(""))
        self.assertTrue(is_uninitialized_pretense_module("# empty comment\n"))
        self.assertTrue(is_uninitialized_pretense_module("from __future__ import annotations\n<TargetClass>"))
        # Valid module
        valid_code = (
            "from dataclasses import dataclass\n"
            "import unittest\n"
            "@dataclass\n"
            "class DummyState:\n"
            "    pass\n"
            "class TestDummy(unittest.TestCase):\n"
            "    pass\n"
        )
        self.assertFalse(is_uninitialized_pretense_module(valid_code))


if __name__ == "__main__":
    unittest.main()
