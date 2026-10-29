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
    check_no_scaffold_placeholders,
    check_pretense_imports,
    check_pretense_structure,
    check_pretense_target_internals,
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
            self.assertIn("@transition(SingleService.do_work)", scaffold)
            self.assertIn('Domain.required("item_id")', scaffold)
            self.assertIn('Domain.required("count")', scaffold)
            self.assertIn("_unimplemented_transition", scaffold)
            self.assertIn("self.fail(", scaffold)
            # Scaffold placeholders must be detected by check_no_scaffold_placeholders
            placeholders = check_no_scaffold_placeholders(tree)
            self.assertTrue(len(placeholders) > 0)
            self.assertTrue(any("Domain.required" in p for p in placeholders))
            self.assertTrue(any("_unimplemented_transition" in p for p in placeholders))
            self.assertTrue(any("self.fail" in p for p in placeholders))
            self.assertTrue(is_uninitialized_pretense_module(scaffold))
        finally:
            os.unlink(pyi_path)

    def test_scaffold_uses_domain_required_for_ambiguous_params(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".pyi", delete=False) as f:
            f.write(
                "from typing import Any\n"
                "from support.lib.lifecycle import Singleton, system\n\n"
                "class MysteryService:\n"
                "    def process_data(self, opaque_blob: Any, custom_spec: dict[str, Any]) -> None: ...\n"
            )
            pyi_path = f.name
        try:
            scaffold = generate_pretense_scaffold(
                pyi_path=pyi_path,
                stem="mystery_service_impl_pretense",
                impl_stem="mystery_service_impl",
                lib_pkg="my_pkg",
            )
            tree = ast.parse(scaffold)
            self.assertEqual(len(check_pretense_structure(tree)), 0)
            self.assertEqual(len(check_pretense_imports(scaffold)), 0)
            self.assertIn('Domain.required("opaque_blob")', scaffold)
            self.assertIn('Domain.required("custom_spec")', scaffold)
            self.assertNotIn("val_opaque_blob_a", scaffold)
            self.assertNotIn("val_custom_spec_a", scaffold)
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
            self.assertIn("@transition(ServiceAlpha.step_a)", scaffold)
            self.assertIn("@transition(ServiceBeta.step_b)", scaffold)

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


    def test_residual_notbound_sentinel_detected(self) -> None:
        import io
        from unittest.mock import patch
        from update_python_with_ai.support.lib.pretense_lint import main

        code = (
            "from dataclasses import dataclass\n"
            "from typing import Any\n"
            "import unittest\n"
            "from pretense import StateMachine, transition, TransitionContext, NotBound\n"
            "@dataclass\n"
            "class DummyState:\n"
            "    initialized: bool = True\n"
            "class DummyMachine(StateMachine[DummyState]):\n"
            "    @transition('do_action')\n"
            "    def do_action(self, ctx: TransitionContext[Any, [], Any]) -> None:\n"
            "        ctx.returns(lambda: NotBound)\n"
            "class TestDummyUnit(unittest.TestCase):\n"
            "    def test_stub(self) -> None:\n"
            "        self.assertNotEqual('dummy', NotBound)\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            bad_path = f.name
        try:
            stderr_capture = io.StringIO()
            with patch("sys.argv", ["pretense_lint", bad_path]), patch("sys.stderr", stderr_capture):
                exit_code = main()
                self.assertEqual(exit_code, 1)
                output = stderr_capture.getvalue()
                self.assertIn("returns sentinel 'NotBound'", output)
                self.assertIn("asserts on sentinel 'NotBound'", output)
        finally:
            if os.path.exists(bad_path):
                os.remove(bad_path)

    def test_multi_transition_disambiguation_detected(self) -> None:
        import io
        from unittest.mock import patch
        from update_python_with_ai.support.lib.pretense_lint import main

        code = (
            "from dataclasses import dataclass\n"
            "from typing import Any\n"
            "import unittest\n"
            "from pretense import StateMachine, transition, TransitionContext, Domain\n"
            "@dataclass\n"
            "class SvcState:\n"
            "    initialized: bool = True\n"
            "class SvcProto:\n"
            "    def compute(self, x: int) -> int: ...\n"
            "class SvcMachine(StateMachine[SvcState]):\n"
            "    @transition(SvcProto.compute)\n"
            "    def compute_1(self, ctx: TransitionContext[Any, [int], int]) -> None:\n"
            "        ctx.requires(lambda check: check(self.state.initialized, 'init'))\n"
            "        ctx.arguments(x=Domain(strategy=lambda: 1, validator=lambda x: True))\n"
            "        ctx.returns(lambda x: 1)\n"
            "    @transition(SvcProto.compute)\n"
            "    def compute_2(self, ctx: TransitionContext[Any, [int], int]) -> None:\n"
            "        ctx.requires(lambda check: check(self.state.initialized, 'init'))\n"
            "        ctx.arguments(x=Domain(strategy=lambda: 2, validator=lambda x: True))\n"
            "        ctx.returns(lambda x: 2)\n"
            "class TestSvcUnit(unittest.TestCase):\n"
            "    pass\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            bad_path = f.name
        try:
            stderr_capture = io.StringIO()
            with patch("sys.argv", ["pretense_lint", bad_path]), patch("sys.stderr", stderr_capture):
                exit_code = main()
                self.assertEqual(exit_code, 1)
                output = stderr_capture.getvalue()
                self.assertIn("Multiple transitions for 'SvcProto.compute'", output)
                self.assertIn("undifferentiated preconditions and argument recognizers", output)
        finally:
            if os.path.exists(bad_path):
                os.remove(bad_path)

    def test_multi_transition_differentiated_permitted(self) -> None:
        import io
        from unittest.mock import patch
        from update_python_with_ai.support.lib.pretense_lint import main

        code = (
            "from dataclasses import dataclass\n"
            "from typing import Any\n"
            "import unittest\n"
            "from pretense import StateMachine, transition, TransitionContext, Domain\n"
            "@dataclass\n"
            "class SvcState:\n"
            "    initialized: bool = True\n"
            "class SvcProto:\n"
            "    def compute(self, x: int) -> int: ...\n"
            "class SvcMachine(StateMachine[SvcState]):\n"
            "    @transition(SvcProto.compute)\n"
            "    def compute_pos(self, ctx: TransitionContext[Any, [int], int]) -> None:\n"
            "        ctx.requires(lambda check: check(self.state.initialized, 'init'))\n"
            "        ctx.arguments(x=Domain(strategy=lambda: 1, validator=lambda x: x > 0))\n"
            "        ctx.returns(lambda x: x)\n"
            "    @transition(SvcProto.compute)\n"
            "    def compute_neg(self, ctx: TransitionContext[Any, [int], int]) -> None:\n"
            "        ctx.requires(lambda check: check(self.state.initialized, 'init'))\n"
            "        ctx.arguments(x=Domain(strategy=lambda: -1, validator=lambda x: x <= 0))\n"
            "        ctx.returns(lambda x: -x)\n"
            "class TestSvcUnit(unittest.TestCase):\n"
            "    pass\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            good_path = f.name
        try:
            stderr_capture = io.StringIO()
            with patch("sys.argv", ["pretense_lint", good_path]), patch("sys.stderr", stderr_capture):
                exit_code = main()
                self.assertEqual(exit_code, 0)
        finally:
            if os.path.exists(good_path):
                os.remove(good_path)

    def test_state_machine_instantiating_target_service_detected(self) -> None:
        import io
        from unittest.mock import patch
        from update_python_with_ai.support.lib.pretense_lint import main

        code = (
            "from dataclasses import dataclass\n"
            "from typing import Any\n"
            "import unittest\n"
            "from pretense import StateMachine, transition, TransitionContext\n"
            "@dataclass\n"
            "class MyState:\n"
            "    initialized: bool = True\n"
            "class MyService:\n"
            "    def do_work(self) -> None: ...\n"
            "class MyMachine(StateMachine[MyState]):\n"
            "    @transition(MyService.do_work)\n"
            "    def do_work(self, ctx: TransitionContext[Any, [], Any]) -> None:\n"
            "        ctx.arguments()\n"
            "        def _returns():\n"
            "            svc = MyService()\n"
            "            return svc.do_work()\n"
            "        ctx.returns(_returns)\n"
            "class TestMyUnit(unittest.TestCase):\n"
            "    pass\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            bad_path = f.name
        try:
            stderr_capture = io.StringIO()
            with patch("sys.argv", ["pretense_lint", bad_path]), patch("sys.stderr", stderr_capture):
                exit_code = main()
                self.assertEqual(exit_code, 1)
                output = stderr_capture.getvalue()
                self.assertIn("instantiates target service 'MyService'", output)
        finally:
            if os.path.exists(bad_path):
                os.remove(bad_path)

    def test_state_machine_algorithmic_solver_detected(self) -> None:
        import io
        from unittest.mock import patch
        from update_python_with_ai.support.lib.pretense_lint import main

        code = (
            "from dataclasses import dataclass\n"
            "from typing import Any\n"
            "import unittest\n"
            "from pretense import StateMachine, transition, TransitionContext\n"
            "@dataclass\n"
            "class MyState:\n"
            "    initialized: bool = True\n"
            "class MyService:\n"
            "    def solve_problem(self) -> bool: ...\n"
            "class MyMachine(StateMachine[MyState]):\n"
            "    def _model_solve(self) -> bool:\n"
            "        def backtrack() -> bool:\n"
            "            return True\n"
            "        return backtrack()\n"
            "    @transition(MyService.solve_problem)\n"
            "    def solve_problem(self, ctx: TransitionContext[Any, [], Any]) -> None:\n"
            "        ctx.arguments()\n"
            "        ctx.returns(lambda: self._model_solve())\n"
            "class TestMyUnit(unittest.TestCase):\n"
            "    pass\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            bad_path = f.name
        try:
            stderr_capture = io.StringIO()
            with patch("sys.argv", ["pretense_lint", bad_path]), patch("sys.stderr", stderr_capture):
                exit_code = main()
                self.assertEqual(exit_code, 1)
                output = stderr_capture.getvalue()
                self.assertIn("defines nested algorithmic function 'backtrack'", output)
        finally:
            if os.path.exists(bad_path):
                os.remove(bad_path)

    def test_state_machine_while_in_transition_detected(self) -> None:
        import io
        from unittest.mock import patch
        from update_python_with_ai.support.lib.pretense_lint import main

        code = (
            "from dataclasses import dataclass\n"
            "from typing import Any\n"
            "import unittest\n"
            "from pretense import StateMachine, transition, TransitionContext\n"
            "@dataclass\n"
            "class MyState:\n"
            "    initialized: bool = True\n"
            "class MyService:\n"
            "    def poll(self) -> None: ...\n"
            "class MyMachine(StateMachine[MyState]):\n"
            "    @transition(MyService.poll)\n"
            "    def poll(self, ctx: TransitionContext[Any, [], Any]) -> None:\n"
            "        while True:\n"
            "            break\n"
            "class TestMyUnit(unittest.TestCase):\n"
            "    pass\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            bad_path = f.name
        try:
            stderr_capture = io.StringIO()
            with patch("sys.argv", ["pretense_lint", bad_path]), patch("sys.stderr", stderr_capture):
                exit_code = main()
                self.assertEqual(exit_code, 1)
                output = stderr_capture.getvalue()
                self.assertIn("contains a while loop", output)
        finally:
            if os.path.exists(bad_path):
                os.remove(bad_path)

    def test_target_internals_private_member_access(self) -> None:
        code = (
            "import unittest\n"
            "class VersionEngine:\n"
            "    def parse_version(self, text: str) -> None: ...\n"
            "class TestSemver(unittest.TestCase):\n"
            "    def setUp(self) -> None:\n"
            "        self.versionengine = VersionEngine()\n"
            "    def test_internal(self) -> None:\n"
            "        self.versionengine._is_version_like_token('*')\n"
            "    def test_class_internal(self) -> None:\n"
            "        VersionEngine._expand_wildcard('x')\n"
            "    def test_local_internal(self) -> None:\n"
            "        engine = VersionEngine()\n"
            "        engine._parse_version_token('abc')\n"
        )
        tree = ast.parse(code)
        pyi_elems = {
            "classes": [
                {
                    "name": "VersionEngine",
                    "methods": [{"name": "parse_version", "args": ["text"]}],
                    "properties": [],
                }
            ]
        }
        errs = check_pretense_target_internals(tree, "test_pretense.py", pyi_elems)
        self.assertEqual(len(errs), 3)
        self.assertTrue(any("_is_version_like_token" in e for e in errs))
        self.assertTrue(any("_expand_wildcard" in e for e in errs))
        self.assertTrue(any("_parse_version_token" in e for e in errs))

    def test_target_internals_reflection_forbidden(self) -> None:
        code = (
            "import unittest\n"
            "class VersionEngine:\n"
            "    def parse_version(self, text: str) -> None: ...\n"
            "class TestSemver(unittest.TestCase):\n"
            "    def setUp(self) -> None:\n"
            "        self.versionengine = VersionEngine()\n"
            "    def test_reflection_on_class(self) -> None:\n"
            "        fn = getattr(VersionEngine, 'some_method')\n"
            "    def test_reflection_on_instance(self) -> None:\n"
            "        fn = getattr(self.versionengine, 'some_method')\n"
            "    def test_permitted_patterns(self) -> None:\n"
            "        # self._helper is allowed\n"
            "        self._my_test_helper()\n"
            "        # public method call is allowed\n"
            "        self.versionengine.parse_version('1.0.0')\n"
            "    def _my_test_helper(self) -> None: pass\n"
        )
        tree = ast.parse(code)
        pyi_elems = {
            "classes": [
                {
                    "name": "VersionEngine",
                    "methods": [{"name": "parse_version", "args": ["text"]}],
                    "properties": [],
                }
            ]
        }
        errs = check_pretense_target_internals(tree, "test_pretense.py", pyi_elems)
        self.assertEqual(len(errs), 2)
        self.assertTrue(any("target class 'VersionEngine'" in e for e in errs))
        self.assertTrue(any("target instance 'self.versionengine'" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
