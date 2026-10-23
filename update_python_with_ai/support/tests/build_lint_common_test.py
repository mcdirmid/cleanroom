#!/usr/bin/env python3
"""build_lint_common_test.py — Unit tests for build_lint_common exception eating checks."""

import os
import tempfile
import unittest

from update_python_with_ai.support.lib.build_lint_common import check_exception_eating


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


if __name__ == "__main__":
    unittest.main()
