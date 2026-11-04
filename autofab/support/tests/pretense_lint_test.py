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
    if ws and os.path.isdir(os.path.join(ws, "autofab_py")):
        return ws
    cur = os.path.abspath(os.path.dirname(__file__))
    while cur and cur != os.path.dirname(cur):
        if os.path.isdir(os.path.join(cur, "autofab_py")):
            return cur
        cur = os.path.dirname(cur)
    return os.getcwd()


REPO_ROOT = find_repo_root()
for p in [
    REPO_ROOT,
    os.path.join(REPO_ROOT, "autofab_py"),
    os.path.join(REPO_ROOT, "autofab_py", "support", "lib"),
]:
    if p not in sys.path and os.path.isdir(p):
        sys.path.insert(0, p)

from autofab_py.support.lib.build_lint_common import check_no_top_level_probes
from autofab_py.support.lib.pretense_lint import (
    check_interface_transition_coverage,
    check_lifted_expr_usage,
    check_multi_interface_inheritance,
    check_multi_transition_disambiguation,
    check_no_call_target_in_interface,
    check_no_pre_seeding,
    check_no_relative_parent_imports,
    check_no_scaffold_placeholders,
    check_pretense_imports,
    check_pretense_next_transition,
    check_pretense_structure,
    check_pretense_target_internals,
    check_transition_protocol_properties,
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
        from autofab_py.support.lib.pretense_lint import main

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
        from autofab_py.support.lib.pretense_lint import main

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
        from autofab_py.support.lib.pretense_lint import main

        code = (
            "from dataclasses import dataclass\n"
            "from typing import Any\n"
            "import unittest\n"
            "from pretense import StateMachine, transition, Domain, make_return_value\n"
            "@dataclass\n"
            "class SvcState:\n"
            "    initialized: bool = True\n"
            "class SvcProto:\n"
            "    def compute(self, x: int) -> int: ...\n"
            "class SvcMachine(StateMachine[SvcState]):\n"
            "    @transition(SvcProto.compute)\n"
            "    def compute_pos(self, x: int) -> None:\n"
            "        ret = make_return_value(x)\n"
            "        assert ret is not None\n"
            "    @transition(SvcProto.compute)\n"
            "    def compute_neg(self, x: int) -> None:\n"
            "        ret = make_return_value(-x)\n"
            "        assert ret is not None\n"
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
                self.assertEqual(exit_code, 1)
                output = stderr_capture.getvalue()
                self.assertIn("PN_STRICT_1_TO_1", output)
        finally:
            if os.path.exists(good_path):
                os.remove(good_path)

    def test_state_machine_instantiating_target_service_detected(self) -> None:
        import io
        from unittest.mock import patch
        from autofab_py.support.lib.pretense_lint import main

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
        from autofab_py.support.lib.pretense_lint import main

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
        from autofab_py.support.lib.pretense_lint import main

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

    def test_lifted_expr_usage_lint(self) -> None:
        bad_code = (
            "from dataclasses import dataclass\n"
            "from pretense import Domain, Expr, StateMachine, TransitionContext, transition\n"
            "@dataclass\n"
            "class RegState:\n"
            "    items: list[str]\n"
            "class Reg:\n"
            "    def add(self, k: str) -> bool: ...\n"
            "class RegSM(StateMachine[RegState]):\n"
            "    @transition(Reg.add)\n"
            "    def add_ok(self, k: Expr[str], ret: Expr[bool], ctx: TransitionContext[Reg]) -> None:\n"
            "        k.constrain(Domain.string(min_size=1))\n"
            "        raw_k = k.value()\n"
            "        self.state.items.append(raw_k)\n"
            "        ret.constrain(True)\n"
        )
        bad_tree = ast.parse(bad_code)
        errs = check_lifted_expr_usage(bad_tree, "reg_pretense.py")
        self.assertEqual(len(errs), 2)
        self.assertTrue(any("calls 'k.value()' outside 'if ctx.updates:', 'if ctx.target:'" in e for e in errs))
        self.assertTrue(any("mutates 'self.state' outside 'if ctx.updates:'" in e for e in errs))

        good_code = (
            "from dataclasses import dataclass\n"
            "from pretense import Domain, Expr, StateMachine, TransitionContext, transition\n"
            "@dataclass\n"
            "class RegState:\n"
            "    items: list[str]\n"
            "class Reg:\n"
            "    def add(self, k: str) -> bool: ...\n"
            "class RegSM(StateMachine[RegState]):\n"
            "    @transition(Reg.add)\n"
            "    def add_ok(self, k: Expr[str], ret: Expr[bool], ctx: TransitionContext[Reg]) -> None:\n"
            "        k.constrain(Domain.string(min_size=1))\n"
            "        ret.constrain(True)\n"
            "        if ctx.updates:\n"
            "            self.state.items.append(k.value())\n"
            "        if ctx.target:\n"
            "            ctx.check(k.value() in self.state.items)\n"
        )
        good_tree = ast.parse(good_code)
        self.assertEqual(check_lifted_expr_usage(good_tree, "reg_pretense.py"), [])

    def test_lifted_multi_transition_disambiguation_and_interface_impl_structure(self) -> None:
        iface_code = (
            "from dataclasses import dataclass\n"
            "from pretense import Domain, StateMachine, transition, make_return_value\n"
            "@dataclass\n"
            "class RegState:\n"
            "    items: set[str]\n"
            "class Reg:\n"
            "    def add(self, k: str) -> bool: ...\n"
            "class RegSM(StateMachine[RegState]):\n"
            "    @transition(Reg.add)\n"
            "    def add(self, k: str) -> None:\n"
            "        ret = make_return_value(True)\n"
            "        assert ret is not None\n"
        )
        iface_tree = ast.parse(iface_code)
        self.assertFalse(is_uninitialized_pretense_module(iface_code))
        self.assertEqual(check_pretense_structure(iface_tree, "parts/reg/pretense/reg_pretense.py"), [])
        self.assertEqual(check_multi_transition_disambiguation(iface_tree, "parts/reg/pretense/reg_pretense.py"), [])

        impl_code = (
            "import unittest\n"
            "from pretense.compiler import compile_hypothesis_test_case\n"
            "class TestRegImplReal(unittest.TestCase):\n"
            "    def test_scenario(self) -> None:\n"
            "        pass\n"
            "RegFuzzTest = compile_hypothesis_test_case(proto=None, sut_factory=lambda: None, initial_state_factory=lambda: None)\n"
        )
        impl_tree = ast.parse(impl_code)
        self.assertFalse(is_uninitialized_pretense_module(impl_code))
        self.assertEqual(check_pretense_structure(impl_tree, "parts/reg_impl/pretense/reg_impl_pretense.py"), [])

    def test_disallowed_relative_parent_imports(self) -> None:
        bad_code = (
            "from __future__ import annotations\n"
            "from ..lib.ring_buffer import RingBuffer, BufferEmptyError\n"
        )
        bad_tree = ast.parse(bad_code)
        errs = check_no_relative_parent_imports("parts/ring_buffer/pretense/ring_buffer_pretense.py", bad_tree)
        self.assertEqual(len(errs), 1)
        self.assertIn("prohibited relative parent import '..lib.ring_buffer'", errs[0])

        good_code = (
            "from __future__ import annotations\n"
            "from . import peer_pretense\n"
            "from my_pkg.parts.ring_buffer.lib.ring_buffer import RingBuffer, BufferEmptyError\n"
        )
        good_tree = ast.parse(good_code)
        good_errs = check_no_relative_parent_imports("parts/ring_buffer/pretense/ring_buffer_pretense.py", good_tree)
        self.assertEqual(good_errs, [])

    def test_type_ignore_rejected_in_pretense_lint(self) -> None:
        import subprocess
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(
                "import unittest\n"
                "from pretense.compiler import compile_hypothesis_test_case\n"
                "class TestFooReal(unittest.TestCase):\n"
                "    def test_scenario(self) -> None:\n"
                "        x = 1  # type: ignore[attr-defined]\n"
                "FooFuzzTest = compile_hypothesis_test_case(proto=None, sut_factory=lambda: None, initial_state_factory=lambda: None)\n"
            )
            f_path = f.name
        try:
            lint_mod = os.path.join(REPO_ROOT, "autofab_py", "support", "lib", "pretense_lint.py")
            res = subprocess.run([sys.executable, lint_mod, f_path], capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("'# type: ignore' is prohibited", res.stderr)
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_bare_lib_import_rejected(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            parts_dir = os.path.join(td, "parts", "foo")
            lib_dir = os.path.join(parts_dir, "lib")
            pretense_dir = os.path.join(parts_dir, "pretense")
            os.makedirs(lib_dir, exist_ok=True)
            os.makedirs(pretense_dir, exist_ok=True)
            # Create dummy autofab.toml and cleanroom.toml at root
            with open(os.path.join(td, "autofab.toml"), "w") as f:
                f.write("# dummy\n")
            with open(os.path.join(lib_dir, "foo_impl.py"), "w") as f:
                f.write("class Foo: pass\n")
            pret_path = os.path.join(pretense_dir, "foo_impl_pretense.py")
            with open(pret_path, "w") as f:
                f.write(
                    "import unittest\n"
                    "from lib.foo_impl import Foo\n"
                    "from pretense.compiler import compile_hypothesis_test_case\n"
                    "class TestFooReal(unittest.TestCase):\n"
                    "    def test_scenario(self) -> None:\n"
                    "        self.assertIsNotNone(Foo)\n"
                    "FooFuzzTest = compile_hypothesis_test_case(proto=None, sut_factory=lambda: None, initial_state_factory=lambda: None)\n"
                )
            lint_mod = os.path.join(REPO_ROOT, "autofab_py", "support", "lib", "pretense_lint.py")
            res = subprocess.run(
                [sys.executable, lint_mod, pret_path, "--lib-pkg", os.path.join(parts_dir, "lib")],
                capture_output=True,
                text=True,
                cwd=td,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("bare 'lib' imports are disallowed", res.stderr)

    def test_uncalled_expr_value_rejected(self) -> None:
        code = (
            "from pretense import Expr, TransitionContext, transition\n"
            "class S:\n"
            "    @transition\n"
            "    def step(self, capacity: Expr[int], ret: Expr[None], ctx: TransitionContext) -> None:\n"
            "        if capacity.value > 0:\n"
            "            pass\n"
        )
        tree = ast.parse(code)
        errs = check_lifted_expr_usage(tree, "dummy.py")
        self.assertTrue(len(errs) > 0)
        self.assertTrue(any("references 'capacity.value' as an attribute" in e for e in errs))

    def test_protocol_property_transition_rejected(self) -> None:
        code = (
            "from pretense import transition\n"
            "class ProtoSM:\n"
            "    @transition(MyProto.capacity)\n"
            "    def prop_capacity(self) -> None:\n"
            "        pass\n"
        )
        tree = ast.parse(code)
        pyi_elem = {
            "classes": [
                {"name": "MyProto", "is_protocol": True, "properties": ["capacity"], "methods": []}
            ]
        }
        errs = check_transition_protocol_properties(tree, "dummy.py", pyi_elem)
        self.assertEqual(len(errs), 1)
        self.assertIn("accesses property 'capacity' on Protocol class 'MyProto'", errs[0])
        self.assertIn("Use '@transition(name=\"capacity\")' instead", errs[0])

    def test_self_target_in_transition_rejected(self) -> None:
        tree = ast.parse(
            "from pretense import transition\n"
            "class SM:\n"
            "    @transition('op')\n"
            "    def op(self, ret, ctx) -> None:\n"
            "        if ctx.target:\n"
            "            print(self.target.size)\n"
        )
        errors = check_lifted_expr_usage(tree, "dummy_pretense.py")
        self.assertTrue(any("references 'self.target'" in e for e in errors))

    def test_state_mutation_inside_lambda_rejected(self) -> None:
        tree = ast.parse(
            "from pretense import transition\n"
            "class SM:\n"
            "    @transition('op')\n"
            "    def op(self, ret, ctx) -> None:\n"
            "        ret.constrain(lambda: self.state.items.popitem(last=False))\n"
        )
        errors = check_lifted_expr_usage(tree, "dummy_pretense.py")
        self.assertTrue(any("mutates 'self.state' outside 'if ctx.updates:'" in e for e in errors))

    def test_pretense_next_linear_transition_lint(self) -> None:
        valid_code = (
            "@transition(Target.method)\n"
            "def method(self, x: int) -> None:\n"
            "    require(self.state.initialized)\n"
            "    require_arg(x, Domain.range(1, 10), preferred=[5])\n"
            "    self.state.x = x\n"
            "    ret: int = make_return_value(x)\n"
            "    assert ret == x\n"
        )
        tree = ast.parse(valid_code)
        fn_node = tree.body[0]
        assert isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef))
        self.assertEqual(len(check_pretense_next_transition(fn_node, "test.py")), 0)

        # PN008: Default parameter rejected
        bad_default = (
            "@transition(Target.method)\n"
            "def method(self, x: int = 1) -> None:\n"
            "    ret = make_return_value(x)\n"
        )
        tree = ast.parse(bad_default)
        fn_node_bad_default = tree.body[0]
        assert isinstance(fn_node_bad_default, (ast.FunctionDef, ast.AsyncFunctionDef))
        errs = check_pretense_next_transition(fn_node_bad_default, "test.py")
        self.assertTrue(any("PN008_NO_DEFAULT_ARGUMENTS" in e for e in errs))

        # PN003: Target parameter prohibited
        bad_target = (
            "@transition(Target.method)\n"
            "def method(self, target: Target, x: int) -> None:\n"
            "    ret = make_return_value(x)\n"
        )
        tree = ast.parse(bad_target)
        fn_node_bad_target = tree.body[0]
        assert isinstance(fn_node_bad_target, (ast.FunctionDef, ast.AsyncFunctionDef))
        errs = check_pretense_next_transition(fn_node_bad_target, "test.py")
        self.assertTrue(any("PN003_NO_TARGET_PARAM" in e for e in errs))

        # PRE_LINT_NO_LEGACY_ENSURE: ensure rejected
        bad_ensure = (
            "@transition(Target.method)\n"
            "def method(self, x: int) -> None:\n"
            "    ret = make_return_value(x)\n"
            "    ensure(ret == x)\n"
        )
        tree = ast.parse(bad_ensure)
        fn_node_bad_ensure = tree.body[0]
        assert isinstance(fn_node_bad_ensure, (ast.FunctionDef, ast.AsyncFunctionDef))
        errs = check_pretense_next_transition(fn_node_bad_ensure, "test.py")
        self.assertTrue(any("PRE_LINT_NO_LEGACY_ENSURE" in e for e in errs))

        # PRE_LINT_NO_LEGACY_ENSURE_RET: ensure_ret rejected
        bad_ensure_ret = (
            "@transition(Target.method)\n"
            "def method(self, x: int) -> None:\n"
            "    ret: int = ensure_ret(x)\n"
        )
        tree = ast.parse(bad_ensure_ret)
        fn_node_bad_ret = tree.body[0]
        assert isinstance(fn_node_bad_ret, (ast.FunctionDef, ast.AsyncFunctionDef))
        errs = check_pretense_next_transition(fn_node_bad_ret, "test.py")
        self.assertTrue(any("PRE_LINT_NO_LEGACY_ENSURE_RET" in e for e in errs))

        # PN_IMPL_NO_REQUIRE_ARG: require_arg in impl pseudo-SM rejected
        bad_impl_req_arg = (
            "@transition(Target.method)\n"
            "def method(self, x: int) -> None:\n"
            "    require_arg(x, Domain.integers())\n"
            "    ret = call_target(Target.method(x))\n"
        )
        tree = ast.parse(bad_impl_req_arg)
        fn_node_bad_impl = tree.body[0]
        assert isinstance(fn_node_bad_impl, (ast.FunctionDef, ast.AsyncFunctionDef))
        errs = check_pretense_next_transition(fn_node_bad_impl, "test_impl_pretense.py", is_impl=True)
        self.assertTrue(any("PN_IMPL_NO_REQUIRE_ARG" in e for e in errs))

        # PN_IMPL_CALL_TARGET_ARG_REQUIRED: zero-argument call_target() rejected
        bad_impl_zero_arg = (
            "@transition(Target.method)\n"
            "def method(self, x: int) -> None:\n"
            "    ret = call_target()\n"
        )
        tree = ast.parse(bad_impl_zero_arg)
        fn_node_zero_arg = tree.body[0]
        assert isinstance(fn_node_zero_arg, (ast.FunctionDef, ast.AsyncFunctionDef))
        errs = check_pretense_next_transition(fn_node_zero_arg, "test_impl_pretense.py", is_impl=True)
        self.assertTrue(any("PN_IMPL_CALL_TARGET_ARG_REQUIRED" in e for e in errs))

        # PN_SUT_ARG_REQUIRED: zero-argument sut() rejected
        bad_sut_zero_arg = (
            "@transition(Target.method)\n"
            "def method(self, x: int) -> None:\n"
            "    target = sut()\n"
            "    ret = call_target(target.method(x))\n"
        )
        tree = ast.parse(bad_sut_zero_arg)
        fn_node_sut_zero_arg = tree.body[0]
        assert isinstance(fn_node_sut_zero_arg, (ast.FunctionDef, ast.AsyncFunctionDef))
        errs = check_pretense_next_transition(fn_node_sut_zero_arg, "test_impl_pretense.py", is_impl=True)
        self.assertTrue(any("PN_SUT_ARG_REQUIRED" in e for e in errs))

        # PN_IMPL_NO_REQUIRE_ARG_IMPORT: importing require_arg in impl pretense rejected
        bad_impl_import = "from pretense import StateMachine, call_target, require_arg\n"
        errs = check_pretense_imports(bad_impl_import, is_impl=True, file_path="test_impl_pretense.py")
        self.assertTrue(any("PN_IMPL_NO_REQUIRE_ARG_IMPORT" in e for e in errs))

        # Interface SM imports and require_arg are valid
        valid_iface_import = "from pretense import StateMachine, make_return_value, require_arg\n"
        self.assertEqual(len(check_pretense_imports(valid_iface_import, is_impl=False)), 0)

    def test_banned_skips_rejected(self) -> None:
        from autofab_py.support.lib.build_lint_common import check_banned_skips

        code_skip_unless = (
            "import unittest\n"
            "@unittest.skipUnless(False, 'not available')\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_foo(self) -> None:\n"
            "        pass\n"
        )
        errs = check_banned_skips("dummy_test.py", tree=ast.parse(code_skip_unless), error_code="PRE_LINT_NO_SKIP")
        self.assertEqual(len(errs), 1)
        self.assertIn("PRE_LINT_NO_SKIP", errs[0])
        self.assertIn("unittest.skipUnless", errs[0])

        code_setattr = (
            "setattr(MyTest, '__unittest_skip__', True)\n"
        )
        errs = check_banned_skips("dummy_test.py", tree=ast.parse(code_setattr), error_code="PRE_LINT_NO_SKIP")
        self.assertEqual(len(errs), 1)
        self.assertIn("PRE_LINT_NO_SKIP", errs[0])
        self.assertIn("__unittest_skip__", errs[0])

        code_skip_call = (
            "def test_bar():\n"
            "    pytest.skip('not implemented')\n"
        )
        errs = check_banned_skips("dummy_test.py", tree=ast.parse(code_skip_call), error_code="PRE_LINT_NO_SKIP")
        self.assertEqual(len(errs), 1)
        self.assertIn("PRE_LINT_NO_SKIP", errs[0])
        self.assertIn("pytest.skip", errs[0])

    def test_impl_pseudo_state_machine_no_state_mutation(self) -> None:
        code_mutating = (
            "from pretense import transition, call_target, sut\n"
            "class DummyImpl(DummyStateMachine):\n"
            "    @transition(Target.push)\n"
            "    def push(self, item: str) -> None:\n"
            "        target = sut(Target)\n"
            "        ret = call_target(target.push(item))\n"
            "        self.state.items.append(item)\n"
            "        return ret\n"
        )
        tree = ast.parse(code_mutating)
        errs = check_lifted_expr_usage(tree, "dummy_impl_pretense.py", is_impl=True)
        self.assertTrue(any("PN_IMPL_NO_STATE_MUTATION" in e for e in errs))

        code_non_mutating = (
            "from pretense import transition, call_target, sut\n"
            "class DummyImpl(DummyStateMachine):\n"
            "    @transition(Target.push)\n"
            "    def push(self, item: str) -> None:\n"
            "        target = sut(Target)\n"
            "        ret = call_target(target.push(item))\n"
            "        assert ret is None\n"
            "        return ret\n"
        )
        tree_clean = ast.parse(code_non_mutating)
        errs_clean = check_lifted_expr_usage(tree_clean, "dummy_impl_pretense.py", is_impl=True)
        self.assertFalse(any("PN_IMPL_NO_STATE_MUTATION" in e for e in errs_clean))

    def test_pre_seeding_with_state_args_rejected(self) -> None:
        code_bad = (
            "def make_sut() -> Allocator:\n"
            "    vault = make_vault_fake(VaultState(balance=1000))\n"
            "    return get_singleton(Allocator)\n"
        )
        errs = check_no_pre_seeding(ast.parse(code_bad), "test.py")
        self.assertTrue(any("PRE_LINT_NO_PRE_SEEDING" in e and "passing state arguments" in e for e in errs))

        code_good = (
            "def make_sut() -> Allocator:\n"
            "    vault = make_vault_fake()\n"
            "    return get_singleton(Allocator)\n"
        )
        errs_good = check_no_pre_seeding(ast.parse(code_good), "test.py")
        self.assertEqual(len(errs_good), 0)

    def test_state_poking_in_test_cases_rejected(self) -> None:
        code_poking_assign = (
            "import unittest\n"
            "class TestTaskWorkerReal(unittest.TestCase):\n"
            "    def test_poke(self) -> None:\n"
            "        self.sm.state.queue_available = False\n"
        )
        errs = check_no_pre_seeding(ast.parse(code_poking_assign), "test.py")
        self.assertTrue(any("PRE_LINT_NO_STATE_POKING" in e for e in errs))

        code_poking_call = (
            "import unittest\n"
            "class TestTaskWorkerReal(unittest.TestCase):\n"
            "    def test_poke(self) -> None:\n"
            "        self.sm.state.queue_pending.append('task-1')\n"
        )
        errs_call = check_no_pre_seeding(ast.parse(code_poking_call), "test.py")
        self.assertTrue(any("PRE_LINT_NO_STATE_POKING" in e for e in errs_call))

        code_clean = (
            "import unittest\n"
            "class TestTaskWorkerReal(unittest.TestCase):\n"
            "    def test_clean(self) -> None:\n"
            "        self.checked.submit('task-1', 'alpha')\n"
            "        self.checked.execute('task-1', 'alpha')\n"
        )
        errs_clean = check_no_pre_seeding(ast.parse(code_clean), "test.py")
        self.assertEqual(len(errs_clean), 0)

    def test_call_target_in_interface_rejected(self) -> None:
        code_bad = (
            "from pretense import StateMachine, transition, call_target, sut\n"
            "class StreamReaderStateMachine(StateMachine[StreamReaderState]):\n"
            "    @transition\n"
            "    def read(self) -> str:\n"
            "        target = sut(StreamReader)\n"
            "        return call_target(target.read())\n"
        )
        errs = check_no_call_target_in_interface(ast.parse(code_bad), "stream_reader_pretense.py", is_interface=True)
        self.assertTrue(any("PRE_LINT_NO_CALL_TARGET_IN_INTERFACE" in e for e in errs))

        errs_impl = check_no_call_target_in_interface(ast.parse(code_bad), "stream_reader_impl_pretense.py", is_interface=False)
        self.assertEqual(len(errs_impl), 0)

    def test_interface_transition_coverage_missing_or_incomplete(self) -> None:
        code_missing_suite = (
            "from pretense import StateMachine, transition\n"
            "class VaultStateMachine(StateMachine[VaultState]):\n"
            "    @transition\n"
            "    def deposit(self, amount: int) -> None:\n"
            "        pass\n"
        )
        errs = check_interface_transition_coverage(ast.parse(code_missing_suite), "vault_pretense.py", is_interface=True)
        self.assertTrue(any("PRE_LINT_INTERFACE_TRANSITION_COVERAGE" in e and "missing a fixed test suite" in e for e in errs))

        code_incomplete = (
            "import unittest\n"
            "from pretense import StateMachine, transition\n"
            "class VaultStateMachine(StateMachine[VaultState]):\n"
            "    @transition\n"
            "    def deposit(self, amount: int) -> None:\n"
            "        pass\n"
            "    @transition\n"
            "    def withdraw(self, amount: int) -> None:\n"
            "        pass\n"
            "    @transition.seeding\n"
            "    def seed_active(self, active: bool) -> None:\n"
            "        pass\n"
            "class TestVaultFake(unittest.TestCase):\n"
            "    def test_only_deposit(self) -> None:\n"
            "        self.fake.deposit(10)\n"
        )
        errs_inc = check_interface_transition_coverage(ast.parse(code_incomplete), "vault_pretense.py", is_interface=True)
        self.assertTrue(any("transition 'withdraw'" in e for e in errs_inc))
        self.assertTrue(any("transition 'seed_active'" in e for e in errs_inc))
        self.assertTrue(all("Advice: Ensure its required conditions can be properly reached" in e for e in errs_inc))

    def test_interface_transition_coverage_passing(self) -> None:
        code_complete = (
            "import unittest\n"
            "from pretense import StateMachine, transition\n"
            "class VaultStateMachine(StateMachine[VaultState]):\n"
            "    @transition\n"
            "    def deposit(self, amount: int) -> None:\n"
            "        pass\n"
            "    @transition\n"
            "    def withdraw(self, amount: int) -> None:\n"
            "        pass\n"
            "    @transition.seeding\n"
            "    def seed_active(self, active: bool) -> None:\n"
            "        pass\n"
            "class TestVaultFake(unittest.TestCase):\n"
            "    def test_all(self) -> None:\n"
            "        self.sm.seed_active(True)\n"
            "        self.fake.deposit(10)\n"
            "        self.fake.withdraw(5)\n"
            "        _ = self.fake.total\n"
        )
        errs = check_interface_transition_coverage(ast.parse(code_complete), "vault_pretense.py", is_interface=True)
        self.assertEqual(len(errs), 0)

    def test_interface_scaffold_generation(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".pyi", delete=False) as f:
            f.write(
                "class KeyVault:\n"
                "    def store_key(self, key_id: str, secret: str) -> None: ...\n"
                "    def retrieve_key(self, key_id: str) -> str: ...\n"
                "    @property\n"
                "    def key_count(self) -> int: ...\n"
            )
            pyi_path = f.name
        try:
            scaffold = generate_pretense_scaffold(
                pyi_path=pyi_path,
                stem="key_vault_pretense",
                impl_stem="key_vault",
                lib_pkg="vault_pkg",
                is_interface=True,
            )
            tree = ast.parse(scaffold)
            self.assertIn("import unittest", scaffold)
            self.assertIn("class TestKeyVaultFake(unittest.TestCase):", scaffold)
            self.assertIn("def test_transitions_coverage(self) -> None:", scaffold)
            self.assertIn("self.sm.seed_initial()", scaffold)
            self.assertIn("self.fake.store_key(", scaffold)
            self.assertIn("self.fake.retrieve_key(", scaffold)
            self.assertIn("self.fake.key_count", scaffold)

            # Interface transition coverage check must pass cleanly on scaffold
            cov_errs = check_interface_transition_coverage(tree, "key_vault_pretense.py", is_interface=True)
            self.assertEqual(cov_errs, [])

            # State poking check must not flag seed_initial in StateMachine
            poke_errs = check_no_pre_seeding(tree, "key_vault_pretense.py")
            self.assertEqual(poke_errs, [])
        finally:
            os.unlink(pyi_path)

    def test_pretense_top_level_probe_rejected(self) -> None:
        source = (
            "from __future__ import annotations\n"
            "import unittest\n"
            "_PROBE_RESULT10 = 'propagated'\n"
            "try:\n"
            "    raise RuntimeError('PROBE')\n"
            "except Exception:\n"
            "    pass\n"
        )
        tree = ast.parse(source)
        errors = check_no_top_level_probes("test_pretense.py", tree=tree, error_code="PRE_LINT_NO_TOP_LEVEL_PROBE")
        self.assertTrue(len(errors) >= 2)
        self.assertTrue(any("PRE_LINT_NO_TOP_LEVEL_PROBE" in e for e in errors))
        self.assertTrue(any("You are not allowed to execute the test suite or run ad-hoc probes" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
