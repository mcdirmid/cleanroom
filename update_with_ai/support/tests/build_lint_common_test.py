#!/usr/bin/env python3
"""build_lint_common_test.py — Unit tests for build_lint_common exception eating checks."""

import os
import tempfile
import unittest

from update_with_ai.support.lib.build_lint_common import (
    check_exception_eating,
    check_no_frozen_exceptions,
    check_no_private_imports,
    check_no_sys_modules_tampering,
    check_syntax,
    check_tautological_assertions,
    format_syntax_error,
)


class BuildLintCommonExceptionEatingTest(unittest.TestCase):
    def _check(self, source: str) -> list[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
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
        self.assertIn("broad exception eating detected: '(ValueError, Exception)'", errors[0])

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
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
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
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
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
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
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
            "# cleanroom: allow-private-import\n"
            "from my_pkg.impl import _private_fn\n"
        )
        errors = self._check(source)
        self.assertEqual(errors, [])

    def test_public_import_passes(self) -> None:
        source = "from my_pkg.impl import public_fn, __initialize__\n"
        errors = self._check(source)
        self.assertEqual(errors, [])


class BuildLintCommonTautologicalAssertionTest(unittest.TestCase):
    def _check(self, source: str, check_empty: bool = False) -> list[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
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
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
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
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
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


if __name__ == "__main__":
    unittest.main()
