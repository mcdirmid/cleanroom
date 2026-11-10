#!/usr/bin/env python3
"""build_lint_common_test.py — Unit tests for build_lint_common exception eating checks."""

import ast
import os
import tempfile
import unittest

from autofab_py.support.lib.build_lint_common import (
    check_banned_skips,
    check_exception_eating,
    check_impl_imports,
    check_no_error_testing,
    check_no_try_except_in_tests,
    check_no_lifecycle_scope_leaks,
    check_no_frozen_exceptions,
    check_no_private_imports,
    check_no_sys_modules_tampering,
    check_no_top_level_probes,
    check_singleton_registration,
    check_syntax,
    check_tautological_assertions,
    check_type_ignore,
    format_syntax_error,
)


class BuildLintCommonExceptionEatingTest(unittest.TestCase):
    def _check(self, source: str) -> list[str]:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            temp_path = f.name
        try:
            return check_exception_eating(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # --- Negative cases: suppression / eating failures ---

    def test_bare_except_pass_fails(self) -> None:
        source = """
try:
    do_something()
except:
    pass
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("broad exception eating detected: 'bare except'", errors[0])

    def test_broad_exception_pass_fails(self) -> None:
        source = """
try:
    do_something()
except Exception:
    pass
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("broad exception eating detected: 'Exception'", errors[0])

    def test_broad_base_exception_pass_fails(self) -> None:
        source = """
try:
    do_something()
except BaseException:
    pass
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("broad exception eating detected: 'BaseException'", errors[0])

    def test_broad_tuple_exception_pass_fails(self) -> None:
        source = """
try:
    do_something()
except (ValueError, Exception):
    pass
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "broad exception eating detected: '(ValueError, Exception)'", errors[0]
        )

    def test_broad_exception_unused_variable_fails(self) -> None:
        source = """
try:
    do_something()
except Exception as exc:
    pass
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)

    def test_broad_exception_return_constant_fails(self) -> None:
        source = """
try:
    do_something()
except Exception:
    return None
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)

    def test_broad_exception_print_fails(self) -> None:
        source = """
try:
    do_something()
except Exception as exc:
    print(exc)
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)

    # --- Positive cases: legitimate reification & structured capture ---

    def test_reified_attribute_assignment_passes(self) -> None:
        source = """
try:
    do_something()
except Exception as exc:
    _result.error = exc
"""
        self.assertEqual(self._check(source), [])

    def test_reified_subscript_assignment_passes(self) -> None:
        source = """
try:
    do_something()
except Exception as exc:
    results[node_id] = exc
"""
        self.assertEqual(self._check(source), [])

    def test_reified_call_argument_passes(self) -> None:
        source = """
try:
    action()
except Exception as exc:
    record_failure(node_id, exc)
"""
        self.assertEqual(self._check(source), [])

    def test_reified_call_keyword_passes(self) -> None:
        source = """
try:
    action()
except Exception as exc:
    res = NodeResult(state=NodeState.FAILED, error=exc)
    results[node_id] = res
"""
        self.assertEqual(self._check(source), [])

    def test_reified_append_passes(self) -> None:
        source = """
try:
    action()
except Exception as exc:
    errors.append(exc)
"""
        self.assertEqual(self._check(source), [])

    def test_reified_return_passes(self) -> None:
        source = """
try:
    action()
except Exception as exc:
    return False, exc
"""
        self.assertEqual(self._check(source), [])

    def test_reified_return_constructor_passes(self) -> None:
        source = """
try:
    action()
except Exception as exc:
    return NodeResult(state=NodeState.FAILED, error=str(exc))
"""
        self.assertEqual(self._check(source), [])

    def test_reified_yield_passes(self) -> None:
        source = """
try:
    yield action()
except Exception as exc:
    yield NodeResult(error=exc)
"""
        self.assertEqual(self._check(source), [])

    def test_reified_alias_propagation_passes(self) -> None:
        source = """
try:
    action()
except Exception as exc:
    error_msg = f"Task failed with error: {exc}"
    self.record_error(error_msg)
"""
        self.assertEqual(self._check(source), [])

    # --- Positive cases: pragma directives ---

    def test_pragma_cleanroom_allow_broad_exception_on_except_passes(self) -> None:
        source = """
try:
    foreign_callback()
except Exception:  # cleanroom: allow-broad-exception
    pass
"""
        self.assertEqual(self._check(source), [])

    def test_pragma_intentional_catch_inside_body_passes(self) -> None:
        source = """
try:
    foreign_callback()
except Exception:
    # intentional-catch
    return default_value
"""
        self.assertEqual(self._check(source), [])

    def test_pragma_above_except_passes(self) -> None:
        source = """
try:
    foreign_callback()
# allow-broad-exception
except Exception:
    pass
"""
        self.assertEqual(self._check(source), [])

    def test_pragma_on_try_line_passes(self) -> None:
        source = """
try:  # cleanroom: allow-broad-exception
    foreign_callback()
except Exception:
    pass
"""
        self.assertEqual(self._check(source), [])

    # --- Positive cases: standard re-raise & narrow exceptions ---

    def test_reraise_passes(self) -> None:
        source = """
try:
    action()
except Exception:
    cleanup()
    raise
"""
        self.assertEqual(self._check(source), [])

    def test_specific_exception_pass_passes(self) -> None:
        source = """
try:
    action()
except (KeyError, ValueError):
    pass
"""
        self.assertEqual(self._check(source), [])


class BuildLintCommonSyntaxCheckTest(unittest.TestCase):
    def test_valid_syntax_returns_empty(self) -> None:
        source = """
def valid_function(a: int) -> int:
    return a + 1
"""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            temp_path = f.name
        try:
            errors = check_syntax(temp_path)
            self.assertEqual(errors, [])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_syntax_error_returns_rich_diagnostic_with_caret(self) -> None:
        source = "def broken():\n    x = (1 + 2))\n    return x\n"
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            temp_path = f.name
        try:
            errors = check_syntax(temp_path)
            self.assertEqual(len(errors), 1)
            err = errors[0]
            self.assertIn("error: syntax error:", err)
            self.assertIn(f"{temp_path}:2:", err)
            self.assertIn(">    2 |     x = (1 + 2))", err)
            self.assertIn("^", err)
            self.assertIn("  1 | def broken():", err)
            self.assertIn("  3 |     return x", err)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_direct_source_string_syntax_check(self) -> None:
        source = "def broken_direct():\n    return (\n"
        errors = check_syntax(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("error: syntax error:", errors[0])
        self.assertIn("^", errors[0])

    def test_nonexistent_file_returns_empty(self) -> None:
        errors = check_syntax("/path/to/nonexistent/file_xyz_123.py")
        self.assertEqual(errors, [])


class BuildLintCommonPrivateImportTest(unittest.TestCase):
    def _check(self, source: str) -> list[str]:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            temp_path = f.name
        try:
            return check_no_private_imports(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_private_import_fails(self) -> None:
        source = "from my_pkg.impl import _private_fn\n"
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("prohibited private import '_private_fn'", errors[0])

    def test_private_import_with_pragma_passes(self) -> None:
        source = (
            "# cleanroom: allow-private-import\nfrom my_pkg.impl import _private_fn\n"
        )
        errors = self._check(source)
        self.assertEqual(errors, [])

    def test_public_import_passes(self) -> None:
        source = "from my_pkg.impl import public_fn, __initialize__\n"
        errors = self._check(source)
        self.assertEqual(errors, [])


class BuildLintCommonTautologicalAssertionTest(unittest.TestCase):
    def _check(self, source: str, check_empty: bool = False) -> list[str]:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            temp_path = f.name
        try:
            return check_tautological_assertions(temp_path, check_empty=check_empty)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_assert_true_true_fails(self) -> None:
        source = """
import unittest

class MyTest(unittest.TestCase):
    def test_something(self):
        self.assertTrue(True)
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("tautological assertion 'assertTrue(True)'", errors[0])

    def test_assert_equal_literals_fails(self) -> None:
        source = """
import unittest

class MyTest(unittest.TestCase):
    def test_something(self):
        self.assertEqual(1, 1)
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("tautological assertion 'assertEqual(1, 1)'", errors[0])

    def test_empty_test_method_fails(self) -> None:
        source = """
import unittest

class MyTest(unittest.TestCase):
    def test_empty(self):
        pass
"""
        errors = self._check(source, check_empty=True)
        self.assertEqual(len(errors), 1)
        self.assertIn("empty test method 'test_empty'", errors[0])

    def test_pragma_allows_tautology(self) -> None:
        source = """
import unittest

class MyTest(unittest.TestCase):
    def test_something(self):
        # cleanroom: allow-tautology
        self.assertTrue(True)
"""
        errors = self._check(source)
        self.assertEqual(errors, [])


class BuildLintCommonSysModulesTamperingTest(unittest.TestCase):
    def _check(self, source: str) -> list[str]:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            temp_path = f.name
        try:
            return check_no_sys_modules_tampering(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_del_sys_modules_fails(self) -> None:
        source = "import sys\ndel sys.modules['some_mod']\n"
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("prohibited sys.modules mutation", errors[0])

    def test_sys_modules_pop_fails(self) -> None:
        source = "import sys\nsys.modules.pop('some_mod', None)\n"
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("prohibited sys.modules.pop() call", errors[0])

    def test_pragma_allows_sys_modules(self) -> None:
        source = "# cleanroom: allow-sys-modules\ndel sys.modules['some_mod']\n"
        errors = self._check(source)
        self.assertEqual(errors, [])


class BuildLintCommonFrozenExceptionsTest(unittest.TestCase):
    def _check(self, source: str) -> list[str]:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            temp_path = f.name
        try:
            return check_no_frozen_exceptions(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_frozen_exception_fails(self) -> None:
        source = """
from dataclasses import dataclass

@dataclass(frozen=True)
class MyError(Exception):
    message: str
"""
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot be a frozen dataclass", errors[0])

    def test_mutable_dataclass_exception_passes(self) -> None:
        source = """
from dataclasses import dataclass

@dataclass
class MyError(Exception):
    message: str
"""
        errors = self._check(source)
        self.assertEqual(errors, [])

    def test_frozen_regular_class_passes(self) -> None:
        source = """
from dataclasses import dataclass

@dataclass(frozen=True)
class NormalData:
    x: int
"""
        errors = self._check(source)
        self.assertEqual(errors, [])


class CheckTypeIgnoreTest(unittest.TestCase):
    def _check(self, source: str) -> list[str]:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            temp_path = f.name
        try:
            return check_type_ignore(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_type_ignore_with_space_rejected(self) -> None:
        source = "x = 1  # type: ignore\n"
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("'# type: ignore' is prohibited", errors[0])

    def test_type_ignore_no_space_rejected(self) -> None:
        source = "x = 1  #type: ignore\n"
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("'# type: ignore' is prohibited", errors[0])

    def test_type_ignore_bracket_rejected(self) -> None:
        source = "x = 1  # type: ignore[attr-defined]\n"
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("'# type: ignore' is prohibited", errors[0])

    def test_pyright_ignore_rejected(self) -> None:
        source = "x = 1  # pyright: ignore\n"
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("'# type: ignore' is prohibited", errors[0])

    def test_pyright_ignore_bracket_rejected(self) -> None:
        source = "x = 1  # pyright: ignore[reportAttributeAccessIssue]\n"
        errors = self._check(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("'# type: ignore' is prohibited", errors[0])

    def test_regular_comments_pass(self) -> None:
        source = "# This is a normal comment\nx = 1  # type of variable is int\n# ignore this warning in prose\n"
        errors = self._check(source)
        self.assertEqual(errors, [])


class CheckBannedSkipsTest(unittest.TestCase):
    def test_skip_unless_rejected(self) -> None:
        source = (
            "import unittest\n"
            "@unittest.skipUnless(False, 'skipped')\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_foo(self) -> None:\n"
            "        pass\n"
        )
        tree = ast.parse(source)
        errors = check_banned_skips("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("TEST_LINT_NO_SKIP", errors[0])
        self.assertIn("unittest.skipUnless", errors[0])

    def test_skip_method_decorator_rejected(self) -> None:
        source = (
            "import unittest\n"
            "class MyTest(unittest.TestCase):\n"
            "    @unittest.skip('temporary')\n"
            "    def test_foo(self) -> None:\n"
            "        pass\n"
        )
        tree = ast.parse(source)
        errors = check_banned_skips("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("unittest.skip", errors[0])

    def test_setattr_unittest_skip_rejected(self) -> None:
        source = "setattr(MyTest, '__unittest_skip__', True)\n"
        tree = ast.parse(source)
        errors = check_banned_skips("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("__unittest_skip__", errors[0])

    def test_assign_unittest_skip_rejected(self) -> None:
        source = "MyTest.__unittest_skip__ = True\n"
        tree = ast.parse(source)
        errors = check_banned_skips("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("__unittest_skip__", errors[0])

    def test_pytest_skip_call_rejected(self) -> None:
        source = "import pytest\ndef test_bar():\n    pytest.skip('reason')\n"
        tree = ast.parse(source)
        errors = check_banned_skips("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("pytest.skip", errors[0])

    def test_valid_tests_pass(self) -> None:
        source = (
            "import unittest\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_foo(self) -> None:\n"
            "        self.assertTrue(True)\n"
        )
        tree = ast.parse(source)
        errors = check_banned_skips("test.py", tree=tree)
        self.assertEqual(errors, [])


class BuildLintCommonNoErrorTestingTest(unittest.TestCase):
    def test_assert_raises_error_rejected(self) -> None:
        source = (
            "import unittest\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_error(self):\n"
            "        with self.assertRaises(NodeNotFoundError):\n"
            "            dag.get_node('missing')\n"
        )
        tree = ast.parse(source)
        errors = check_no_error_testing("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("NO_ERROR_TESTING", errors[0])
        self.assertIn("NodeNotFoundError", errors[0])

    def test_pytest_raises_cycle_error_rejected(self) -> None:
        source = (
            "import pytest\n"
            "def test_cycle():\n"
            "    with pytest.raises(pkg.CycleError):\n"
            "        dag.validate()\n"
        )
        tree = ast.parse(source)
        errors = check_no_error_testing("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("CycleError", errors[0])

    def test_pretense_with_raises_error_rejected(self) -> None:
        source = (
            "from pretense import raises\n"
            "def test_trans():\n"
            "    with raises(CustomError):\n"
            "        self.inner_foo()\n"
        )
        tree = ast.parse(source)
        errors = check_no_error_testing("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("CustomError", errors[0])

    def test_exception_suffix_permitted(self) -> None:
        source = (
            "from pretense import raises\n"
            "def test_trans():\n"
            "    with raises(TimeoutException):\n"
            "        self.inner_foo()\n"
        )
        tree = ast.parse(source)
        errors = check_no_error_testing("test.py", tree=tree)
        self.assertEqual(errors, [])

    def test_pragma_allows_error_test(self) -> None:
        source = (
            "import unittest\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_error(self):\n"
            "        # pragma: allow-error-test\n"
            "        with self.assertRaises(NodeNotFoundError):\n"
            "            dag.get_node('missing')\n"
        )
        errors = check_no_error_testing("test.py")  # checks source lines
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            temp_path = f.name
        try:
            errors = check_no_error_testing(temp_path)
            self.assertEqual(errors, [])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_contracted_error_in_companion_spec_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            part_dir = os.path.join(td, "parts", "my_part")
            low_dir = os.path.join(part_dir, "low")
            tests_dir = os.path.join(part_dir, "tests")
            os.makedirs(low_dir, exist_ok=True)
            os.makedirs(tests_dir, exist_ok=True)

            pyi_path = os.path.join(low_dir, "my_part.pyi")
            with open(pyi_path, "w", encoding="utf-8") as f:
                f.write("class CustomContractedError(Exception):\n    message: str\n")

            test_file = os.path.join(tests_dir, "my_part_test.py")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(
                    "import unittest\n"
                    "class MyTest(unittest.TestCase):\n"
                    "    def test_err(self):\n"
                    "        with self.assertRaises(CustomContractedError):\n"
                    "            pass\n"
                )

            errors = check_no_error_testing(test_file)
            self.assertEqual(errors, [])


class BuildLintCommonTopLevelProbesTest(unittest.TestCase):
    def test_valid_module_passes(self) -> None:
        source = (
            '"""Module docstring."""\n'
            "import unittest\n"
            "from typing import Optional\n"
            "MY_CONST = 42\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_foo(self) -> None:\n"
            "        pass\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        tree = ast.parse(source)
        errors = check_no_top_level_probes("test.py", tree=tree)
        self.assertEqual(errors, [])

    def test_top_level_try_fails(self) -> None:
        source = "import unittest\ntry:\n    x = 1\nexcept Exception:\n    pass\n"
        tree = ast.parse(source)
        errors = check_no_top_level_probes("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("Top-level statement 'Try' is prohibited", errors[0])
        self.assertIn(
            "You are not allowed to execute the test suite or run ad-hoc probes",
            errors[0],
        )

    def test_top_level_raise_fails(self) -> None:
        source = "raise RuntimeError('PROBE failed')\n"
        tree = ast.parse(source)
        errors = check_no_top_level_probes("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("Top-level statement 'Raise' is prohibited", errors[0])

    def test_top_level_probe_variable_fails(self) -> None:
        source = "_PROBE_RESULT10 = 'propagated'\n"
        tree = ast.parse(source)
        errors = check_no_top_level_probes("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "Top-level probe variable '_PROBE_RESULT10' is prohibited", errors[0]
        )

    def test_top_level_probe_class_fails(self) -> None:
        source = "class _ProbeStateMachine:\n    pass\n"
        tree = ast.parse(source)
        errors = check_no_top_level_probes("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "Top-level probe class '_ProbeStateMachine' is prohibited", errors[0]
        )


class BuildLintCommonNoTryExceptInTestsTest(unittest.TestCase):
    def test_try_except_in_test_method_rejected(self) -> None:
        source = (
            "import unittest\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_error(self):\n"
            "        try:\n"
            "            foo()\n"
            "        except Exception:\n"
            "            pass\n"
        )
        tree = ast.parse(source)
        errors = check_no_try_except_in_tests("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("NO_TRY_EXCEPT_IN_TESTS", errors[0])
        self.assertIn("Test method 'test_error' uses a try/except block", errors[0])

    def test_try_except_in_standalone_test_rejected(self) -> None:
        source = (
            "def test_bar():\n"
            "    try:\n"
            "        foo()\n"
            "    except ValueError:\n"
            "        pass\n"
        )
        tree = ast.parse(source)
        errors = check_no_try_except_in_tests("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("NO_TRY_EXCEPT_IN_TESTS", errors[0])

    def test_try_except_in_error_helper_rejected(self) -> None:
        source = (
            "def _raises_any(fn):\n"
            "    try:\n"
            "        fn()\n"
            "    except Exception:\n"
            "        return True\n"
            "    return False\n"
        )
        tree = ast.parse(source)
        errors = check_no_try_except_in_tests("test.py", tree=tree)
        self.assertEqual(len(errors), 1)
        self.assertIn("NO_TRY_EXCEPT_IN_TESTS", errors[0])

    def test_try_finally_allowed(self) -> None:
        source = (
            "import unittest\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_cleanup(self):\n"
            "        try:\n"
            "            foo()\n"
            "        finally:\n"
            "            bar()\n"
        )
        tree = ast.parse(source)
        errors = check_no_try_except_in_tests("test.py", tree=tree)
        self.assertEqual(errors, [])

    def test_pragma_allow_try_except_suppresses_error(self) -> None:
        source = (
            "import unittest\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_allowed(self):\n"
            "        # pragma: allow-try-except\n"
            "        try:\n"
            "            foo()\n"
            "        except Exception:\n"
            "            pass\n"
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            temp_path = f.name
        try:
            errors = check_no_try_except_in_tests(temp_path)
            self.assertEqual(errors, [])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_try_except_in_non_test_method_allowed(self) -> None:
        source = (
            "class MockHelper:\n"
            "    def parse(self):\n"
            "        try:\n"
            "            return int('1')\n"
            "        except ValueError:\n"
            "            return 0\n"
        )
        tree = ast.parse(source)
        errors = check_no_try_except_in_tests("test.py", tree=tree)
        self.assertEqual(errors, [])

    def test_try_except_in_teardown_allowed(self) -> None:
        source = (
            "import unittest\n"
            "class MyTest(unittest.TestCase):\n"
            "    def tearDown(self):\n"
            "        try:\n"
            "            cleanup()\n"
            "        except OSError:\n"
            "            pass\n"
        )
        tree = ast.parse(source)
        errors = check_no_try_except_in_tests("test.py", tree=tree)
        self.assertEqual(errors, [])


class BuildLintCommonImplImportsAndSingletonTest(unittest.TestCase):
    def _write_temp(self, source: str) -> str:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            return f.name

    def test_sys_modules_get_impl_rejected(self) -> None:
        source = 'import sys\n_m = sys.modules.get("my_pkg.parts.foo.lib.bar_impl")\n'
        path = self._write_temp(source)
        try:
            errors = check_impl_imports(path)
            self.assertTrue(
                any(
                    "must not access implementation module via sys.modules" in e
                    for e in errors
                )
            )
        finally:
            os.remove(path)

    def test_sys_modules_subscript_impl_rejected(self) -> None:
        source = 'import sys\n_m = sys.modules["my_pkg.parts.foo.lib.bar_impl"]\n'
        path = self._write_temp(source)
        try:
            errors = check_impl_imports(path)
            self.assertTrue(
                any(
                    "must not access implementation module via sys.modules" in e
                    for e in errors
                )
            )
        finally:
            os.remove(path)

    def test_sys_modules_assign_impl_rejected(self) -> None:
        source = 'import sys\nsys.modules["my_pkg.parts.foo.lib.bar_impl"] = mod\n'
        path = self._write_temp(source)
        try:
            errors = check_impl_imports(path)
            self.assertTrue(
                any(
                    "must not assign implementation module to sys.modules" in e
                    for e in errors
                )
            )
        finally:
            os.remove(path)

    def test_foreign_initialize_call_rejected(self) -> None:
        source = "def helper():\n    other_mod.__initialize__()\n"
        path = self._write_temp(source)
        try:
            errors = check_impl_imports(path)
            self.assertTrue(
                any("must not invoke foreign '__initialize__'" in e for e in errors)
            )
        finally:
            os.remove(path)

    def test_foreign_initialize_hasattr_rejected(self) -> None:
        source = 'def helper():\n    if hasattr(other_mod, "__initialize__"):\n        pass\n'
        path = self._write_temp(source)
        try:
            errors = check_impl_imports(path)
            self.assertTrue(
                any("must not probe for foreign '__initialize__'" in e for e in errors)
            )
        finally:
            os.remove(path)

    def test_asm_initialize_call_allowed(self) -> None:
        source = "def helper():\n    foo_asm.__initialize__()\n"
        path = self._write_temp(source)
        try:
            errors = check_impl_imports(path)
            self.assertEqual(errors, [])
        finally:
            os.remove(path)

    def test_register_singleton_undefined_class_rejected(self) -> None:
        source = (
            "def __initialize__(registry=None):\n"
            "    reg.register_singleton(ForeignClass, keys=[ForeignClass])\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_singleton_registration(path)
            self.assertTrue(
                any(
                    "must not register singleton 'ForeignClass' not defined in this module"
                    in e
                    for e in errors
                )
            )
        finally:
            os.remove(path)

    def test_register_singleton_foreign_attr_rejected(self) -> None:
        source = (
            "def __initialize__(registry=None):\n"
            "    reg.register_singleton(foreign.MyClass, keys=[foreign.MyClass])\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_singleton_registration(path)
            self.assertTrue(
                any(
                    "must not register foreign singleton 'foreign.MyClass'" in e
                    for e in errors
                )
            )
        finally:
            os.remove(path)

    def test_register_singleton_outside_initialize_rejected(self) -> None:
        source = (
            "class LocalService:\n"
            "    def configure(self):\n"
            "        reg.register_singleton(LocalService)\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_singleton_registration(path)
            self.assertTrue(
                any(
                    "must only be called inside the auto-generated '__initialize__' function"
                    in e
                    for e in errors
                )
            )
        finally:
            os.remove(path)

    def test_valid_singleton_registration_allowed(self) -> None:
        source = (
            "class LocalService:\n"
            "    pass\n\n"
            "def __initialize__(registry=None):\n"
            "    reg.register_singleton(LocalService, keys=[LocalService])\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_singleton_registration(path)
            self.assertEqual(errors, [])
        finally:
            os.remove(path)


class BuildLintCommonLifecycleScopeLeakTest(unittest.TestCase):
    def _write_temp(self, content: str) -> str:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            f.flush()
            return f.name

    def test_returning_inside_with_enter_phase_fails(self) -> None:
        source = "def helper():\n    with enter_phase(system):\n        return 42\n"
        path = self._write_temp(source)
        try:
            errors = check_no_lifecycle_scope_leaks(path)
            self.assertTrue(
                any(
                    "Returning from inside 'with enter_phase(...)' closes the phase scope upon return"
                    in e
                    for e in errors
                )
            )
        finally:
            os.remove(path)

    def test_helper_method_opening_ephemeral_enter_phase_fails(self) -> None:
        source = (
            "class TestFoo(unittest.TestCase):\n"
            "    def _get_engine(self):\n"
            "        with enter_phase(system) as scope:\n"
            "            x = scope.get_singleton(Engine)\n"
            "        return x\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_no_lifecycle_scope_leaks(path)
            self.assertTrue(
                any(
                    "Test helper '_get_engine' opens an ephemeral 'with enter_phase(...)'"
                    in e
                    for e in errors
                )
            )
        finally:
            os.remove(path)

    def test_helper_method_ephemeral_enter_phase_without_return_fails(self) -> None:
        source = (
            "class TestFoo(unittest.TestCase):\n"
            "    def _setup_repo(self, releases):\n"
            "        with enter_phase(system) as scope:\n"
            "            repo = scope.get_singleton(Repo)\n"
            "            repo.register(releases)\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_no_lifecycle_scope_leaks(path)
            self.assertTrue(
                any(
                    "Test helper '_setup_repo' opens an ephemeral 'with enter_phase(...)'"
                    in e
                    for e in errors
                )
            )
        finally:
            os.remove(path)

    def test_test_method_with_enter_phase_allowed(self) -> None:
        source = (
            "class TestFoo(unittest.TestCase):\n"
            "    def test_something(self):\n"
            "        with enter_phase(system) as scope:\n"
            "            x = scope.get_singleton(Engine)\n"
            "            self.assertEqual(x.val, 1)\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_no_lifecycle_scope_leaks(path)
            self.assertEqual(errors, [])
        finally:
            os.remove(path)

    def test_context_manager_helper_allowed(self) -> None:
        source = (
            "from contextlib import contextmanager\n\n"
            "class TestFoo(unittest.TestCase):\n"
            "    @contextmanager\n"
            "    def _phase_scope(self):\n"
            "        with enter_phase(system):\n"
            "            yield\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_no_lifecycle_scope_leaks(path)
            self.assertEqual(errors, [])
        finally:
            os.remove(path)

    def test_allow_lifecycle_scope_leak_pragma_suppresses(self) -> None:
        source = (
            "def helper():\n"
            "    # allow-lifecycle-scope-leak\n"
            "    with enter_phase(system):\n"
            "        return 42\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_no_lifecycle_scope_leaks(path)
            self.assertEqual(errors, [])
        finally:
            os.remove(path)

    def test_setup_with_enter_phase_call_allowed(self) -> None:
        source = (
            "class TestFoo(unittest.TestCase):\n"
            "    def setUp(self):\n"
            "        self.phase_cm = enter_phase(system)\n"
            "    def tearDown(self):\n"
            "        self.phase_cm.__exit__(None, None, None)\n"
        )
        path = self._write_temp(source)
        try:
            errors = check_no_lifecycle_scope_leaks(path)
            self.assertEqual(errors, [])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
