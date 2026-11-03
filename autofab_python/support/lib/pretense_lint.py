#!/usr/bin/env python3
"""pretense_lint.py — verify and scaffold Pretense state machine test modules.

Usage:
  pretense_lint.py <module_pretense.py> [--pyi <spec.pyi>] [--impl <impl.py>]
  pretense_lint.py --scaffold <module_pretense.py> --pyi <spec.pyi> [--impl <impl.py>] [--lib-pkg <pkg>]
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from build_lint_common import (
        check_banned_skips,
        check_no_bare_parts_imports,
        check_no_frozen_exceptions,
        check_no_private_imports,
        check_no_relative_parent_imports,
        check_no_sys_modules_tampering,
        check_no_error_testing,
        check_syntax,
        check_tautological_assertions,
        check_test_dry_run,
        check_test_impl_imports,
        check_test_imports,
        check_type_ignore,
        find_spec_pyi,
        format_syntax_error,
        module_file,
        module_stem,
        package_of,
        read_text,
        write_text,
    )
except ImportError:
    from autofab_python.support.lib.build_lint_common import (  # type: ignore
        check_banned_skips,
        check_no_bare_parts_imports,
        check_no_frozen_exceptions,
        check_no_private_imports,
        check_no_relative_parent_imports,
        check_no_sys_modules_tampering,
        check_no_error_testing,
        check_syntax,
        check_tautological_assertions,
        check_test_dry_run,
        check_test_impl_imports,
        check_test_imports,
        check_type_ignore,
        find_spec_pyi,
        format_syntax_error,
        module_file,
        module_stem,
        package_of,
        read_text,
        write_text,
    )


def is_uninitialized_pretense_module(content: str) -> bool:
    """Returns True if the pretense module is empty, a placeholder, or lacks basic structure."""
    stripped = content.strip()
    if not stripped:
        return True
    if "<TargetClass>" in content or "<target_impl>" in content or "_unimplemented_transition" in content:
        return True
    try:
        tree = ast.parse(content)
        has_state = False
        has_sm = False
        has_fake_factory = False
        has_test = False
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if node.name.endswith("State"):
                    has_state = True
                for base in node.bases:
                    base_id = ""
                    if isinstance(base, ast.Name):
                        base_id = base.id
                    elif isinstance(base, ast.Attribute):
                        base_id = base.attr
                    elif isinstance(base, ast.Subscript):
                        if isinstance(base.value, ast.Name):
                            base_id = base.value.id
                        elif isinstance(base.value, ast.Attribute):
                            base_id = base.value.attr
                    if base_id in ("TestCase", "unittest.TestCase"):
                        has_test = True
                    elif base_id in ("StateMachine", "StateMachineProto"):
                        has_sm = True
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("make_") and ("fake" in node.name):
                    has_fake_factory = True
            elif isinstance(node, (ast.ImportFrom, ast.Import)):
                for alias in node.names:
                    if alias.name.endswith("State"):
                        has_state = True
                    elif alias.name.endswith("StateMachine"):
                        has_sm = True
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and "FuzzTest" in target.id:
                        has_test = True
        if (has_state and has_sm) or (has_state and has_test) or (has_sm and has_test):
            return False
        if has_test and "compile_hypothesis_test_case" in content:
            return False
        return True
    except SyntaxError:
        return False


def check_pretense_structure(
    tree: ast.AST,
    file_path: str = "",
    is_interface: bool = False,
) -> list[str]:
    """Validates that the pretense module defines model state/transitions (interface) or test cases (implementation)."""
    errors: list[str] = []
    if not is_interface and file_path:
        stem = os.path.basename(file_path)
        if stem.endswith("_pretense.py") and not stem.endswith("_impl_pretense.py"):
            is_interface = True

    body = getattr(tree, "body", [])
    classes = [n for n in body if isinstance(n, ast.ClassDef)]
    state_classes = [c for c in classes if c.name.endswith("State")]
    imported_state = False
    imported_sm = False
    has_fake_factory = False
    for node in body:
        if isinstance(node, (ast.ImportFrom, ast.Import)):
            mod_name = getattr(node, "module", "") or ""
            # Don't mistake base pretense framework symbols for component state/machine
            if mod_name != "pretense":
                for alias in node.names:
                    if alias.name.endswith("State") and alias.name != "State":
                        imported_state = True
                    elif alias.name.endswith("StateMachine") and alias.name not in ("StateMachine", "StateMachineProto"):
                        imported_sm = True
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("make_") and "fake" in node.name:
                has_fake_factory = True

    sm_classes = []
    test_classes = []
    for c in classes:
        for base in c.bases:
            base_id = ""
            if isinstance(base, ast.Name):
                base_id = base.id
            elif isinstance(base, ast.Attribute):
                base_id = base.attr
            elif isinstance(base, ast.Subscript):
                if isinstance(base.value, ast.Name):
                    base_id = base.value.id
                elif isinstance(base.value, ast.Attribute):
                    base_id = base.value.attr
            if base_id in ("TestCase", "unittest.TestCase"):
                test_classes.append(c)
            elif base_id in ("StateMachine", "StateMachineProto") or base_id.endswith("StateMachine"):
                sm_classes.append(c)

    # Also check for compiled hypothesis test case assignment
    compiled_tests = []
    for node in body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and "FuzzTest" in target.id:
                    compiled_tests.append(target.id)

    if is_interface:
        if not sm_classes and not imported_sm:
            errors.append("Missing Pretense StateMachine class in interface pretense module.")
        if not state_classes and not imported_state:
            errors.append("Missing Pretense model state class (interface must define a dataclass ending with 'State').")
        if test_classes:
            t_names = [c.name for c in test_classes]
            errors.append(
                f"Interface pretense module must not contain unit test classes ({', '.join(t_names)}). "
                "Fixed tests belong exclusively in the implementation pretense module (*_impl_pretense.py)."
            )
        return errors

    # Implementation pretense module
    if (imported_sm or imported_state) and state_classes:
        errors.append(
            f"{file_path}:{state_classes[0].lineno}: error [PN_IMPL_NO_STATE_CLASS]: "
            f"Implementation pretense module must not define State dataclasses ({', '.join(c.name for c in state_classes)}). "
            "The implementation pseudo-state machine defines zero state classes; it piggybacks on the interface StateMachine state."
        )

    if not state_classes and not imported_state and not (test_classes or compiled_tests):
        errors.append("Missing Pretense model state class (must define or import a dataclass ending with 'State').")

    if not test_classes and not compiled_tests:
        errors.append(
            "Missing Pretense test cases: module must define at least one unittest.TestCase class or compiled Hypothesis test case."
        )

    return errors


def check_pretense_imports(
    content: str,
    pyi_path: str | None = None,
    is_impl: bool = False,
    file_path: str = "",
) -> list[str]:
    """Validates required Pretense imports and rejects legacy symbols."""
    errors: list[str] = []
    if "pretense" not in content:
        errors.append("Missing pretense imports (must import from pretense).")
        return errors

    try:
        tree = ast.parse(content)
        prefix = f"{file_path}:" if file_path else ""
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "pretense" in node.module:
                    for alias in node.names:
                        if alias.name in ("ensure", "ensure_ret", "ensure_raises", "TransitionContext", "Expr"):
                            errors.append(
                                f"{prefix}{node.lineno}: error [PN_NO_LEGACY_IMPORT]: Importing legacy Pretense symbol '{alias.name}' is strictly prohibited in Pretense 1 Next. "
                                "Use 'make_return_value', 'call_target', 'raises', 'assert', 'sut', 'sut_state', or 'require'."
                            )
                        elif is_impl and alias.name == "require_arg":
                            errors.append(
                                f"{prefix}{node.lineno}: error [PN_IMPL_NO_REQUIRE_ARG_IMPORT]: Importing 'require_arg' is strictly prohibited in implementation pretense modules (*_impl_pretense.py). Domain constraints belong exclusively to the interface state machine."
                            )
                        elif is_impl and alias.name == "make_return_value":
                            errors.append(
                                f"{prefix}{node.lineno}: error [PN_IMPL_NO_MAKE_RETURN_VALUE_IMPORT]: Importing 'make_return_value' is strictly prohibited in implementation pretense modules (*_impl_pretense.py). Implementation pseudo-state machines must use 'call_target(...)', not 'make_return_value()'."
                            )
    except SyntaxError:
        pass

    return errors


def check_single_argument_assertions(tree: ast.AST, file_path: str = "") -> list[str]:
    """Enforces single-argument native assert statements (PRE_LINT_ASSERT_SINGLE_ARG)."""
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            if node.msg is not None:
                errors.append(
                    f"{file_path}:{node.lineno}: error [PRE_LINT_ASSERT_SINGLE_ARG]: "
                    "assert statement must take a single boolean argument with no failure message. "
                    "Got 'assert test, msg'. Use 'assert test' instead."
                )
            if isinstance(node.test, ast.Tuple):
                errors.append(
                    f"{file_path}:{node.lineno}: error [PRE_LINT_ASSERT_SINGLE_ARG]: "
                    "assert test cannot be a tuple 'assert (x, y)'. A non-empty tuple evaluates to True."
                )
    return errors



def check_transition_outcomes(tree: ast.AST, file_path: str = "") -> list[str]:
    """Validates that transitions do not declare conflicting raises/returns or invalid arguments."""
    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        is_transition = False
        for d in node.decorator_list:
            if isinstance(d, ast.Call):
                func = d.func
                if (isinstance(func, ast.Name) and func.id == "transition") or (
                    isinstance(func, ast.Attribute) and func.attr == "transition"
                ):
                    is_transition = True
                    break
            elif (isinstance(d, ast.Name) and d.id == "transition") or (
                isinstance(d, ast.Attribute) and d.attr == "transition"
            ):
                is_transition = True
                break

        if not is_transition:
            continue

        raw_params = [a.arg for a in node.args.args if a.arg != "self"]
        if not raw_params or raw_params[-1] != "ctx":
            # Pretense Next linear transition (handled by check_pretense_next_transition)
            continue

        has_raises = False
        has_returns = False
        raises_line = 0
        expr_constrain_vars: set[str] = set()
        expr_raises_vars: dict[str, int] = {}

        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                target_id = child.func.value.id if isinstance(child.func.value, ast.Name) else ""
                if child.func.attr == "raises":
                    if target_id == "ctx":
                        has_raises = True
                        raises_line = child.lineno
                    elif target_id:
                        expr_raises_vars[target_id] = child.lineno
                    for kw in child.keywords:
                        if kw.arg not in ("match",):
                            errors.append(
                                f"{file_path}:{child.lineno}: error: Invalid keyword argument '{kw.arg}' in {target_id or 'ctx'}.raises(...) for transition '{node.name}'. "
                                f"raises(...) only accepts (exc_type, match='')."
                            )
                elif child.func.attr == "returns" and target_id == "ctx":
                    has_returns = True
                elif child.func.attr == "constrain" and target_id:
                    expr_constrain_vars.add(target_id)

        if has_raises and has_returns:
            errors.append(
                f"{file_path}:{raises_line}: error: Transition '{node.name}' declares both ctx.raises(...) and ctx.returns(...). "
                f"These outcome declarations are mutually exclusive: use ctx.raises(...) for transitions that unconditionally raise an exception, "
                f"or return Raised(...) dynamically from ctx.returns(...)."
            )
        for v_name, r_line in expr_raises_vars.items():
            if v_name in expr_constrain_vars:
                errors.append(
                    f"{file_path}:{r_line}: error: Transition '{node.name}' calls both {v_name}.constrain(...) and {v_name}.raises(...). "
                    f"These outcome declarations are mutually exclusive."
                )
    return errors


def _is_ctx_gated_if(test_expr: ast.AST) -> bool:
    """Returns True if an `if` condition references `ctx.updates` or `ctx.target`."""
    for sub in ast.walk(test_expr):
        if isinstance(sub, ast.Attribute) and sub.attr in ("updates", "target"):
            if isinstance(sub.value, ast.Name) and sub.value.id == "ctx":
                return True
    return False


def _targets_self_state(expr: ast.AST) -> bool:
    """Returns True if expr is `self.state` or an attribute/subscript rooted at `self.state`."""
    curr = expr
    while isinstance(curr, (ast.Attribute, ast.Subscript)):
        if (
            isinstance(curr, ast.Attribute)
            and curr.attr == "state"
            and isinstance(curr.value, ast.Name)
            and curr.value.id == "self"
        ):
            return True
        curr = curr.value
    return False


def check_pretense_next_transition(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str = "",
    is_impl: bool = False,
) -> list[str]:
    """Validates Pretense Next linear transitions against rules PN001 - PN010."""
    errors: list[str] = []
    fn_name = node.name

    has_trans_dec = False
    is_seeding = False
    dec_call = None
    for d in node.decorator_list:
        if isinstance(d, ast.Call):
            func = d.func
            if (isinstance(func, ast.Name) and func.id == "transition") or (
                isinstance(func, ast.Attribute) and func.attr in ("transition", "seeding")
            ):
                has_trans_dec = True
                dec_call = d
                if (isinstance(func, ast.Attribute) and func.attr == "seeding") or any(kw.arg == "seeding" for kw in d.keywords):
                    is_seeding = True
                break
        elif (isinstance(d, ast.Name) and d.id == "transition") or (
            isinstance(d, ast.Attribute) and d.attr in ("transition", "seeding")
        ):
            has_trans_dec = True
            if isinstance(d, ast.Attribute) and d.attr == "seeding":
                is_seeding = True
            break

    if not has_trans_dec:
        return errors

    # PN001: Correct decorator
    if dec_call and not dec_call.args and not any(kw.arg in ("seeding", "name") for kw in dec_call.keywords) and getattr(dec_call.func, "attr", "") != "seeding":
        errors.append(
            f"{file_path}:{node.lineno}: error [PN001]: @transition decorator must specify target method, e.g. @transition(TargetClass.method)."
        )

    # PN008: No default arguments
    if node.args.defaults or any(d is not None for d in node.args.kw_defaults):
        errors.append(
            f"{file_path}:{node.lineno}: error [PN008_NO_DEFAULT_ARGUMENTS]: Default parameter bindings are strictly prohibited on transition methods. Every domain argument must be explicit."
        )

    param_names = [p.arg for p in node.args.args]
    if not is_seeding:
        # PN003: Parameters must match target method 1:1; target/sut/suts prohibited
        for p in param_names[1:]:
            if p in ("target", "sut", "suts"):
                errors.append(
                    f"{file_path}:{node.lineno}: error [PN003_NO_TARGET_PARAM]: Transition parameters must match the target method 1:1. "
                    f"'{p}' parameter is prohibited; access target or collaborators via sut(TargetClass) or sut_state(TargetClass)."
                )

    input_args = set(param_names[1:])

    # PN002: NO LAMBDAS
    for child in ast.walk(node):
        if isinstance(child, ast.Lambda):
            errors.append(
                f"{file_path}:{child.lineno}: error [PN002_NO_LAMBDAS]: Lambdas are prohibited in Pretense Next transitions. Write plain Python expressions."
            )

    # PN001: NO EXPR LIFTING
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in ("value", "constrain"):
            errors.append(
                f"{file_path}:{child.lineno}: error [PN001_NO_EXPR_LIFTING]: Lifted 'Expr' is prohibited in Pretense Next. Use plain variable directly."
            )

    # PN003: NO TWO PASS GATING
    for child in ast.walk(node):
        if isinstance(child, ast.If):
            for sub in ast.walk(child.test):
                if isinstance(sub, ast.Attribute) and sub.attr in ("updates", "target"):
                    if isinstance(sub.value, ast.Name) and sub.value.id == "ctx":
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN003_NO_TWO_PASS_GATING]: Two-pass gating ('ctx.updates' / 'ctx.target') is obsolete. Write linear statements."
                        )

    # Legacy macros prohibition & require purity
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func_id = child.func.id if isinstance(child.func, ast.Name) else getattr(child.func, "attr", "")
            if func_id == "ensure":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PRE_LINT_NO_LEGACY_ENSURE]: 'ensure(...)' is obsolete in Pretense 1 Next. Use native Python 'assert ...' instead."
                )
            elif func_id == "ensure_ret":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PRE_LINT_NO_LEGACY_ENSURE_RET]: 'ensure_ret(...)' is obsolete in Pretense 1 Next. In interface SM, use 'ret = make_return_value(...)'; in impl pseudo-SM, use 'ret = call_target()'."
                )
            elif func_id == "ensure_raises":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PRE_LINT_NO_LEGACY_ENSURE_RAISES]: 'ensure_raises(...)' is obsolete in Pretense 1 Next. Use 'with raises(ExpectedException): make_return_value()' or 'with raises(ExpectedException): call_target()'."
                )
            elif func_id == "require_arg":
                if is_impl:
                    errors.append(
                        f"{file_path}:{child.lineno}: error [PN_IMPL_NO_REQUIRE_ARG]: 'require_arg(...)' is strictly prohibited in implementation pseudo-state machines. Domain constraints and generation domains belong exclusively to the interface state machine."
                    )
            elif func_id == "require":
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Call) and (
                        (isinstance(sub.func, ast.Name) and sub.func.id in ("sut", "sut_state"))
                        or (isinstance(sub.func, ast.Attribute) and sub.func.attr in ("sut", "sut_state"))
                    ):
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN009_REQUIRE_PURITY]: require() cannot reference SUT via sut(...). It must only inspect 'self.state'."
                        )
                    elif isinstance(sub, ast.Name) and sub.id in input_args:
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN009_REQUIRE_PURITY]: require() cannot reference transition input argument '{sub.id}'. Preconditions only evaluate state. To constrain input arguments relative to state, use require_arg."
                        )

    # Pivot Node Verification (only for non-seeding transitions)
    if not is_seeding:
        has_make_return_value = any(
            isinstance(c, ast.Call)
            and (
                (isinstance(c.func, ast.Name) and c.func.id == "make_return_value")
                or (isinstance(c.func, ast.Attribute) and c.func.attr == "make_return_value")
            )
            for c in ast.walk(node)
        )
        call_target_calls = [
            c for c in ast.walk(node)
            if isinstance(c, ast.Call)
            and (
                (isinstance(c.func, ast.Name) and c.func.id == "call_target")
                or (isinstance(c.func, ast.Attribute) and c.func.attr == "call_target")
            )
        ]
        has_call_target = len(call_target_calls) > 0
        sut_calls = [
            c for c in ast.walk(node)
            if isinstance(c, ast.Call)
            and (
                (isinstance(c.func, ast.Name) and c.func.id == "sut")
                or (isinstance(c.func, ast.Attribute) and c.func.attr == "sut")
            )
        ]
        for sc in sut_calls:
            if len(sc.args) == 0 and len(sc.keywords) == 0:
                errors.append(
                    f"{file_path}:{sc.lineno}: error [PN_SUT_ARG_REQUIRED]: 'sut()' requires the target class as an argument (e.g. 'target = sut(TargetClass)'). Zero-argument 'sut()' is strictly prohibited."
                )
        if is_impl:
            mutating_methods = {
                "add", "remove", "discard", "pop", "popitem", "clear", "update",
                "append", "extend", "insert", "put", "assign", "set", "delete", "__setitem__",
            }

            def _is_self_state_target(n: ast.AST) -> bool:
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" and n.attr == "state":
                    return True
                if isinstance(n, ast.Attribute):
                    return _is_self_state_target(n.value)
                return False

            for child in ast.walk(node):
                if isinstance(child, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                    targets = [child.target] if hasattr(child, "target") else child.targets  # type: ignore
                    for t in targets:
                        if _is_self_state_target(t):
                            errors.append(
                                f"{file_path}:{child.lineno}: error [PN_IMPL_NO_STATE_MUTATION]: Transition '{fn_name}' in implementation pseudo-state machine must not mutate 'self.state'. Model state transitions are already executed by the inherited interface transition before delegating to 'call_target(...)'. Implementation transitions must only invoke 'call_target(...)' and assert postconditions."
                            )
                elif isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if child.func.attr in mutating_methods and _is_self_state_target(child.func.value):
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN_IMPL_NO_STATE_MUTATION]: Transition '{fn_name}' in implementation pseudo-state machine must not mutate 'self.state' (calling '{child.func.attr}()' on self.state). Model state transitions are already executed by the inherited interface transition before delegating to 'call_target(...)'. Implementation transitions must only invoke 'call_target(...)' and assert postconditions."
                        )

            if has_make_return_value:
                errors.append(
                    f"{file_path}:{node.lineno}: error [PN_IMPL_NO_MAKE_RETURN_VALUE]: Transition '{fn_name}' in implementation pseudo-state machine must not call 'make_return_value()'. Use 'ret = call_target(target.method(...))' and 'return ret'."
                )
            if not has_call_target:
                errors.append(
                    f"{file_path}:{node.lineno}: error [PN_IMPL_CALL_TARGET_REQUIRED]: Transition '{fn_name}' in implementation pseudo-state machine must invoke target method via 'call_target(target.method(...))' or 'call_target(ReturnType)'."
                )
            else:
                for ct in call_target_calls:
                    if len(ct.args) == 0 and len(ct.keywords) == 0:
                        errors.append(
                            f"{file_path}:{ct.lineno}: error [PN_IMPL_CALL_TARGET_ARG_REQUIRED]: 'call_target()' requires an argument wrapping the target invocation (e.g. 'call_target(target.method(...))') or expected return type. Zero-argument 'call_target()' is strictly prohibited."
                        )
        else:
            if not has_make_return_value:
                errors.append(
                    f"{file_path}:{node.lineno}: error [PN_IFACE_MAKE_RETURN_VALUE_REQUIRED]: Transition '{fn_name}' in interface state machine must define an AST pivot via 'make_return_value(...)'. For void methods returning None, invoke 'make_return_value()'."
                )

    return errors


def check_lifted_expr_usage(tree: ast.AST, file_path: str = "", is_impl: bool = False) -> list[str]:
    """Validates that lifted Expr.value() calls and self.state mutations are properly gated."""
    errors: list[str] = []
    mutating_methods = {
        "add", "remove", "discard", "pop", "popitem", "clear", "update",
        "append", "extend", "insert", "put", "assign", "set", "delete", "__setitem__",
    }

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        is_transition = False
        for d in node.decorator_list:
            if isinstance(d, ast.Call):
                func = d.func
                if (isinstance(func, ast.Name) and func.id == "transition") or (
                    isinstance(func, ast.Attribute) and func.attr in ("transition", "seeding")
                ):
                    is_transition = True
                    break
            elif (isinstance(d, ast.Name) and d.id == "transition") or (
                isinstance(d, ast.Attribute) and d.attr in ("transition", "seeding")
            ):
                is_transition = True
                break

        if not is_transition:
            continue

        fn_name = node.name
        raw_params = [a.arg for a in node.args.args if a.arg != "self"]
        if not raw_params or raw_params[-1] != "ctx":
            errors.extend(check_pretense_next_transition(node, file_path, is_impl=is_impl))
            continue

        expr_param_names = set(raw_params[:-1]) if len(raw_params) >= 2 else set()
        call_funcs = {c.func for c in ast.walk(node) if isinstance(c, ast.Call)}

        def _walk_stmt_or_expr(curr: ast.AST, in_gated_block: bool, in_updates_block: bool) -> None:
            if isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef)) and curr is not node:
                return
            if isinstance(curr, ast.Lambda):
                # Lambdas permit deferred .value() resolution, but forbid mutating self.state
                _walk_stmt_or_expr(curr.body, True, False)
                return
            if isinstance(curr, ast.If):
                is_gated = _is_ctx_gated_if(curr.test)
                is_updates = any(
                    isinstance(s, ast.Attribute)
                    and s.attr == "updates"
                    and isinstance(s.value, ast.Name)
                    and s.value.id == "ctx"
                    for s in ast.walk(curr.test)
                )
                _walk_stmt_or_expr(curr.test, in_gated_block, in_updates_block)
                for stmt in curr.body:
                    _walk_stmt_or_expr(stmt, in_gated_block or is_gated, in_updates_block or is_updates)
                for stmt in curr.orelse:
                    _walk_stmt_or_expr(stmt, in_gated_block, in_updates_block)
                return

            if (
                isinstance(curr, ast.Attribute)
                and curr.attr == "target"
                and isinstance(curr.value, ast.Name)
                and curr.value.id == "self"
            ):
                errors.append(
                    f"{file_path}:{curr.lineno}: error: Transition '{fn_name}' references 'self.target'. "
                    f"StateMachine has no 'target' attribute; access the concrete target instance via 'ctx.target' on TransitionContext."
                )

            if (
                isinstance(curr, ast.Attribute)
                and curr.attr == "value"
                and isinstance(curr.value, ast.Name)
                and curr.value.id in expr_param_names
                and curr not in call_funcs
            ):
                p_name = curr.value.id
                errors.append(
                    f"{file_path}:{curr.lineno}: error: Transition '{fn_name}' references '{p_name}.value' as an attribute. "
                    f"'value()' is a method on Expr; call '{p_name}.value()' (and only inside 'if ctx.updates:' or 'if ctx.target:')."
                )

            if isinstance(curr, ast.Call) and isinstance(curr.func, ast.Attribute):
                # Skip inside ctx.update(...) / ctx.consequent(...) / ctx.ensures(...)
                if (
                    isinstance(curr.func.value, ast.Name)
                    and curr.func.value.id == "ctx"
                    and curr.func.attr in ("update", "consequent", "ensures")
                ):
                    return
                if (
                    curr.func.attr == "value"
                    and not curr.args
                    and isinstance(curr.func.value, ast.Name)
                    and curr.func.value.id in expr_param_names
                    and not in_gated_block
                ):
                    p_name = curr.func.value.id
                    errors.append(
                        f"{file_path}:{curr.lineno}: error: Transition '{fn_name}' calls '{p_name}.value()' outside "
                        f"'if ctx.updates:', 'if ctx.target:', or a lambda. During Pass 1 constraint evaluation, Expr "
                        f"parameters are unbound; access .value() only inside 'if ctx.updates:' or 'if ctx.target:'."
                    )
                if (
                    curr.func.attr in mutating_methods
                    and _targets_self_state(curr.func.value)
                    and not in_updates_block
                ):
                    errors.append(
                        f"{file_path}:{curr.lineno}: error: Transition '{fn_name}' mutates 'self.state' outside "
                        f"'if ctx.updates:'. State mutations must be gated under 'if ctx.updates:'."
                    )

            if isinstance(curr, (ast.Assign, ast.AugAssign)) and not in_updates_block:
                targets = curr.targets if isinstance(curr, ast.Assign) else [curr.target]
                if any(_targets_self_state(t) for t in targets):
                    errors.append(
                        f"{file_path}:{curr.lineno}: error: Transition '{fn_name}' mutates 'self.state' outside "
                        f"'if ctx.updates:'. State mutations must be gated under 'if ctx.updates:'."
                    )

            for child in ast.iter_child_nodes(curr):
                _walk_stmt_or_expr(child, in_gated_block, in_updates_block)

        for stmt in node.body:
            _walk_stmt_or_expr(stmt, False, False)

    return errors


def check_no_residual_sentinels(tree: ast.AST, file_path: str = "") -> list[str]:
    """Validates that transitions and tests do not return or assert on residual NotBound sentinels."""
    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        is_transition = False
        for d in node.decorator_list:
            if isinstance(d, ast.Call):
                func = d.func
                if (isinstance(func, ast.Name) and func.id == "transition") or (
                    isinstance(func, ast.Attribute) and func.attr == "transition"
                ):
                    is_transition = True
                    break
            elif (isinstance(d, ast.Name) and d.id == "transition") or (
                isinstance(d, ast.Attribute) and d.attr == "transition"
            ):
                is_transition = True
                break

        if is_transition:
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == "returns":
                    if child.args:
                        ret_arg = child.args[0]
                        if isinstance(ret_arg, ast.Name) and ret_arg.id == "NotBound":
                            errors.append(
                                f"{file_path}:{child.lineno}: error: Transition '{node.name}' passes sentinel 'NotBound' to ctx.returns(...). "
                                f"Transitions must return concrete values, state expressions, or Raised(...) exceptions."
                            )
                        elif isinstance(ret_arg, ast.Lambda):
                            for sub in ast.walk(ret_arg.body):
                                if isinstance(sub, ast.Name) and sub.id == "NotBound":
                                    errors.append(
                                        f"{file_path}:{child.lineno}: error: Transition '{node.name}' returns sentinel 'NotBound' in ctx.returns(...). "
                                        f"Transitions must return concrete values, state expressions, or Raised(...) exceptions."
                                    )
                                    break
                elif isinstance(child, ast.Return) and isinstance(child.value, ast.Name) and child.value.id == "NotBound":
                    errors.append(
                        f"{file_path}:{child.lineno}: error: Transition '{node.name}' returns sentinel 'NotBound'. "
                        f"Transitions must return concrete values, state expressions, or Raised(...) exceptions."
                    )

        if node.name.startswith("test_"):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if child.func.attr in ("assertEqual", "assertNotEqual") and len(child.args) >= 2:
                        for a in child.args[:2]:
                            if isinstance(a, ast.Name) and a.id == "NotBound":
                                errors.append(
                                    f"{file_path}:{child.lineno}: error: Test '{node.name}' asserts on sentinel 'NotBound'. "
                                    f"Tests must verify concrete contract outcomes rather than sentinel placeholders."
                                )
                                break
    return errors


def _extract_transition_target(dec: ast.expr) -> str | None:
    """Extracts target identifier from a @transition decorator."""
    if isinstance(dec, ast.Call):
        func = dec.func
        is_trans = (isinstance(func, ast.Name) and func.id == "transition") or (
            isinstance(func, ast.Attribute) and func.attr == "transition"
        )
        if is_trans:
            if dec.args:
                first = dec.args[0]
                if isinstance(first, ast.Attribute):
                    val = first.value
                    prefix = val.id if isinstance(val, ast.Name) else ""
                    return f"{prefix}.{first.attr}" if prefix else first.attr
                elif isinstance(first, ast.Name):
                    return first.id
            for kw in dec.keywords:
                if kw.arg in ("name", "target") and isinstance(kw.value, ast.Constant):
                    return str(kw.value.value)
    elif isinstance(dec, ast.Name) and dec.id == "transition":
        return None
    return None


def _is_trivial_requirement(call: ast.Call) -> bool:
    """Returns True if a ctx.requires call has no condition or only checks self.state.initialized."""
    if not call.args:
        return True
    arg = call.args[0]
    if isinstance(arg, ast.Attribute) and arg.attr in ("initialized", "is_initialized"):
        if isinstance(arg.value, ast.Attribute) and arg.value.attr == "state":
            return True
        elif isinstance(arg.value, ast.Name) and arg.value.id == "state":
            return True
    if isinstance(arg, ast.Constant) and arg.value is True:
        return True
    if isinstance(arg, ast.Lambda):
        body = arg.body
        if isinstance(body, ast.Call):
            if body.args:
                cond = body.args[0]
                if isinstance(cond, ast.Attribute) and cond.attr in ("initialized", "is_initialized"):
                    if isinstance(cond.value, ast.Attribute) and cond.value.attr == "state":
                        return True
                    elif isinstance(cond.value, ast.Name) and cond.value.id == "state":
                        return True
                elif isinstance(cond, ast.Constant) and cond.value is True:
                    return True
    return False


def _is_trivial_recognizer(kw: ast.keyword) -> bool:
    """Returns True if recognize keyword is missing, None, or lambda: True."""
    val = kw.value
    if isinstance(val, ast.Constant) and val.value is True:
        return True
    if isinstance(val, ast.Lambda):
        if isinstance(val.body, ast.Constant) and val.body.value is True:
            return True
    return False


def _is_discriminating_domain_expr(val: ast.AST) -> bool:
    """Returns True if the AST expression represents a discriminative domain specification."""
    if isinstance(val, ast.Call):
        if isinstance(val.func, ast.Attribute):
            if val.func.attr in (
                "set",
                "in_set",
                "not_in",
                "subset_of",
                "sampled_from",
                "just",
                "range",
                "regex",
                "perturb",
                "of",
                "object",
                "newtype",
                "list_of",
                "mapping_of",
                "optional",
            ):
                return True
            if val.func.attr == "type":
                for kw in val.keywords:
                    if kw.arg == "validator":
                        return not _is_trivial_recognizer(kw)
                return False
        for kw in val.keywords:
            if kw.arg == "validator":
                return not _is_trivial_recognizer(kw)
        return False
    if isinstance(val, (ast.Set, ast.List, ast.Tuple, ast.Constant)):
        return True
    return False


def check_multi_transition_disambiguation(tree: ast.AST, file_path: str = "") -> list[str]:
    """Enforces strict 1:1 transitions (PN_STRICT_1_TO_1)."""
    errors: list[str] = []
    classes = [n for n in getattr(tree, "body", []) if isinstance(n, ast.ClassDef)]

    for cls in classes:
        target_map: dict[str, list[tuple[str, int]]] = {}

        for item in cls.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            target_name = None
            for d in item.decorator_list:
                target_name = _extract_transition_target(d)
                if target_name:
                    break

            if not target_name:
                continue

            target_map.setdefault(target_name, []).append((item.name, item.lineno))

        for target_name, transitions in target_map.items():
            if len(transitions) > 1:
                first_name, _ = transitions[0]
                for fn_name, lineno in transitions[1:]:
                    errors.append(
                        f"{file_path}:{lineno}: error [PN_STRICT_1_TO_1]: Multiple transitions for '{target_name}' ('{first_name}', '{fn_name}'). "
                        "Pretense 1 Next strictly enforces exactly one 1:1 transition per target method (multi-transitions with undifferentiated preconditions and argument recognizers are prohibited). "
                        "Branching logic and exceptions belong inside the single transition body."
                    )

    return errors


def check_no_algorithmic_state_machines(tree: ast.AST, file_path: str = "") -> list[str]:
    """Validates that StateMachine classes act as lightweight specification oracles rather than algorithmic engines."""
    errors: list[str] = []
    classes = [n for n in getattr(tree, "body", []) if isinstance(n, ast.ClassDef)]

    # Collect target service types decorated by @transition(...)
    transition_targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                target = _extract_transition_target(d)
                if target:
                    cls_prefix = target.split(".")[0]
                    if cls_prefix:
                        transition_targets.add(cls_prefix)

    for cls in classes:
        is_sm = False
        for base in cls.bases:
            base_id = ""
            if isinstance(base, ast.Name):
                base_id = base.id
            elif isinstance(base, ast.Attribute):
                base_id = base.attr
            elif isinstance(base, ast.Subscript):
                if isinstance(base.value, ast.Name):
                    base_id = base.value.id
                elif isinstance(base.value, ast.Attribute):
                    base_id = base.value.attr
            if base_id in ("StateMachine", "StateMachineProto"):
                is_sm = True
                break

        if not is_sm:
            continue

        for item in cls.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            is_transition = False
            for d in item.decorator_list:
                if _extract_transition_target(d):
                    is_transition = True
                    break

            for child in ast.walk(item):
                # Check 1: Target service instantiation or get_singleton call
                if isinstance(child, ast.Call):
                    fn = child.func
                    fn_name = ""
                    if isinstance(fn, ast.Name):
                        fn_name = fn.id
                    elif isinstance(fn, ast.Attribute):
                        fn_name = fn.attr

                    if fn_name == "get_singleton":
                        errors.append(
                            f"{file_path}:{child.lineno}: error: State machine '{cls.name}' calls 'get_singleton'. "
                            f"Pretense state machines must operate purely on abstract model state ('self.state') and must not access live singletons."
                        )
                    elif fn_name in transition_targets:
                        errors.append(
                            f"{file_path}:{child.lineno}: error: State machine '{cls.name}' instantiates target service '{fn_name}'. "
                            f"State machine Fakes must act as lightweight specification oracles modeling state, and must not instantiate or execute the target service under test."
                        )

                # Check 2: Nested algorithmic functions (backtrack, solve, search, etc.)
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not item:
                    lower_name = child.name.lower()
                    if any(algo_word in lower_name for algo_word in ("backtrack", "solve", "search", "recurse")):
                        errors.append(
                            f"{file_path}:{child.lineno}: error: State machine method '{item.name}' defines nested algorithmic function '{child.name}'. "
                            f"State machine Fakes must not implement complex algorithmic solving. Algorithmic verification belongs in real SUT tests."
                        )

                # Check 3: while loops inside transition methods
                if is_transition and isinstance(child, ast.While):
                    errors.append(
                        f"{file_path}:{child.lineno}: error: Transition method '{item.name}' contains a while loop. "
                        f"State machine transitions must be atomic updates to abstract state rather than iterative loops."
                    )

    return errors


def check_pretense_target_internals(
    tree: ast.AST,
    file_path: str = "",
    pyi_elements: dict[str, Any] | None = None,
) -> list[str]:
    """Check that pretense test suites adhere strictly to static public contracts in low/*.pyi.
    Tests must not access private members (_...) on target instances or target classes, and must
    not use dynamic reflection (getattr, hasattr) on target classes or instances to bypass public APIs."""
    errors: list[str] = []
    target_classes: set[str] = set()
    if pyi_elements and "classes" in pyi_elements:
        target_classes = {c["name"] for c in pyi_elements["classes"]}

    target_attr_names = {c.lower() for c in target_classes} | {"sut", "target", "engine", "service"}

    local_target_vars: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Call):
                fn = node.value.func
                target_name = None
                if isinstance(fn, ast.Name) and fn.id in target_classes:
                    target_name = fn.id
                elif isinstance(fn, ast.Attribute) and fn.attr in target_classes:
                    target_name = fn.attr
                if target_name:
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            local_target_vars.add(t.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("_") and not (attr.startswith("__") and attr.endswith("__")):
                val = node.value
                # Check self.<target>._private
                if isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name) and val.value.id == "self":
                    if val.attr.lower() in target_attr_names or (
                        val.attr != "state"
                        and not val.attr.startswith("_")
                        and not val.attr.startswith("mock_")
                        and any(tc.lower() in val.attr.lower() for tc in target_classes)
                    ):
                        errors.append(
                            f"{file_path}:{node.lineno}: error: pretense test must not access private member '{attr}' "
                            f"on target instance 'self.{val.attr}'; tests must adhere strictly to public contracts in low/*.pyi"
                        )
                elif isinstance(val, ast.Name) and val.id in target_classes:
                    errors.append(
                        f"{file_path}:{node.lineno}: error: pretense test must not access private member '{attr}' "
                        f"on target class '{val.id}'; tests must adhere strictly to public contracts in low/*.pyi"
                    )
                elif isinstance(val, ast.Name) and val.id in local_target_vars:
                    errors.append(
                        f"{file_path}:{node.lineno}: error: pretense test must not access private member '{attr}' "
                        f"on target instance '{val.id}'; tests must adhere strictly to public contracts in low/*.pyi"
                    )

        elif isinstance(node, ast.Call):
            fn_name = None
            if isinstance(node.func, ast.Name):
                fn_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fn_name = node.func.attr
            if fn_name in ("getattr", "hasattr") and len(node.args) >= 1:
                first_arg = node.args[0]
                is_target = False
                target_desc = ""
                if isinstance(first_arg, ast.Name) and first_arg.id in target_classes:
                    is_target = True
                    target_desc = f"target class '{first_arg.id}'"
                elif isinstance(first_arg, ast.Attribute) and isinstance(first_arg.value, ast.Name) and first_arg.value.id == "self":
                    if first_arg.attr.lower() in target_attr_names or any(tc.lower() in first_arg.attr.lower() for tc in target_classes):
                        is_target = True
                        target_desc = f"target instance 'self.{first_arg.attr}'"
                elif isinstance(first_arg, ast.Name) and first_arg.id in local_target_vars:
                    is_target = True
                    target_desc = f"target instance '{first_arg.id}'"
                if is_target:
                    errors.append(
                        f"{file_path}:{node.lineno}: error: pretense test must not use '{fn_name}()' "
                        f"on {target_desc}; tests must adhere strictly to static contracts in low/*.pyi"
                    )

    return errors


def check_no_scaffold_placeholders(tree: ast.AST, file_path: str = "") -> list[str]:
    """Validates that transitions and tests do not contain residual scaffold crash placeholders."""
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn_id = ""
            if isinstance(node.func, ast.Name):
                fn_id = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fn_id = node.func.attr
            if fn_id == "_unimplemented_transition":
                errors.append(
                    f"{file_path}:{node.lineno}: error: transition return handler still contains scaffold placeholder '_unimplemented_transition'. "
                    f"You must specify the concrete return oracle or outcome."
                )
            elif (
                fn_id == "required"
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "Domain"
            ):
                errors.append(
                    f"{file_path}:{node.lineno}: error: parameter domain still uses scaffold placeholder 'Domain.required'. "
                    f"You must specify a concrete parameter Domain."
                )
            elif (
                fn_id == "fail"
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
            ):
                if node.args and isinstance(node.args[0], ast.Constant) and "must be implemented" in str(node.args[0].value):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: test method still contains scaffold placeholder 'self.fail'. "
                        f"You must implement concrete test logic."
                    )
            elif (
                (fn_id in ("check", "ensure"))
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value is False
                and len(node.args) > 1
                and isinstance(node.args[1], ast.Constant)
                and "postconditions must be specified" in str(node.args[1].value)
            ):
                errors.append(
                    f"{file_path}:{node.lineno}: error: transition postconditions still contain scaffold placeholder '{fn_id}(False, ...)'. "
                    f"You must specify concrete postcondition invariants in ensure."
                )
    return errors


def extract_pyi_elements(pyi_path: str) -> dict[str, Any]:
    """Extracts target classes, methods, properties, and lifecycle metadata from a pyi file."""
    try:
        content = read_text(pyi_path)
        tree = ast.parse(content, filename=pyi_path)
    except (OSError, SyntaxError):
        return {"classes": [], "has_singleton": False}

    classes: list[dict[str, Any]] = []
    has_singleton = False

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for dec in node.decorator_list:
                dec_name = ""
                if isinstance(dec, ast.Name):
                    dec_name = dec.id
                elif isinstance(dec, ast.Attribute):
                    dec_name = dec.attr
                elif isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        dec_name = dec.func.id
                    elif isinstance(dec.func, ast.Attribute):
                        dec_name = dec.func.attr
                if dec_name == "singleton_type":
                    has_singleton = True

            methods: list[dict[str, Any]] = []
            properties: list[str] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("__") and item.name.endswith("__") and item.name != "__init__":
                        continue
                    is_prop = any(
                        (isinstance(d, ast.Name) and d.id == "property")
                        or (isinstance(d, ast.Attribute) and d.attr == "property")
                        for d in item.decorator_list
                    )
                    if is_prop:
                        properties.append(item.name)
                    else:
                        raw_args: list[ast.arg] = [a for a in item.args.args if a.arg != "self"]
                        raw_args.extend(getattr(item.args, "kwonlyargs", []))
                        arg_info: list[dict[str, str]] = []
                        for a in raw_args:
                            atype = ""
                            if a.annotation:
                                try:
                                    atype = ast.unparse(a.annotation)
                                except Exception:
                                    atype = ""
                            arg_info.append({"name": a.arg, "type": atype})
                        ret_type = "Any"
                        if item.returns:
                            try:
                                ret_type = ast.unparse(item.returns)
                            except Exception:
                                ret_type = "Any"
                        methods.append({
                            "name": item.name,
                            "args": [a["name"] for a in arg_info],
                            "arg_info": arg_info,
                            "return_type": ret_type,
                        })

            is_protocol = any(
                (isinstance(b, ast.Name) and b.id == "Protocol")
                or (isinstance(b, ast.Attribute) and b.attr == "Protocol")
                for b in node.bases
            )

            classes.append({
                "name": node.name,
                "methods": methods,
                "properties": properties,
                "is_protocol": is_protocol,
            })

    return {"classes": classes, "has_singleton": has_singleton}


def check_transition_protocol_properties(
    tree: ast.AST,
    file_path: str = "",
    pyi_elements: dict[str, Any] | None = None,
) -> list[str]:
    """Validates that transitions do not access properties on Protocol classes directly."""
    errors: list[str] = []
    if not pyi_elements or not pyi_elements.get("classes"):
        return errors

    protocol_props: dict[str, set[str]] = {}
    for c in pyi_elements["classes"]:
        if c.get("is_protocol") and c.get("properties"):
            protocol_props[c["name"]] = set(c["properties"])

    if not protocol_props:
        return errors

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if isinstance(d, ast.Call):
                func = d.func
                is_trans = (
                    (isinstance(func, ast.Name) and func.id == "transition")
                    or (isinstance(func, ast.Attribute) and func.attr == "transition")
                )
                if is_trans and d.args:
                    arg0 = d.args[0]
                    if isinstance(arg0, ast.Attribute) and isinstance(arg0.value, ast.Name):
                        cls_name = arg0.value.id
                        prop_name = arg0.attr
                        if cls_name in protocol_props and prop_name in protocol_props[cls_name]:
                            errors.append(
                                f"{file_path}:{d.lineno}: error: '@transition({cls_name}.{prop_name})' accesses property '{prop_name}' on Protocol class '{cls_name}'. "
                                f"Pyright disallows accessing protocol properties as class variables. Use '@transition(name=\"{prop_name}\")' instead."
                            )
    return errors


def _default_domain_arg(arg_name: str, arg_type: str = "") -> str:
    """Returns Domain.boolean() for boolean parameters, or Domain.required(...) for all other parameters.

    Dummy values, heuristic constants, or unconstrained type heuristics are strictly prohibited;
    unspecialized domains must crash at runtime to force authoring meaningful domain constraints.
    """
    lower_type = arg_type.lower().strip()
    if lower_type in ("bool", "boolean"):
        return "Domain.boolean()"
    return f'Domain.required("{arg_name}")'


def _sample_val_for_arg(arg_name: str, arg_type: str = "") -> str:
    """Returns a sample argument or Domain.required representation."""
    lower_type = arg_type.lower().strip()
    if lower_type in ("bool", "boolean"):
        return "True"
    return f'Domain.required("{arg_name}")'


def _default_arg_val(arg_name: str, arg_type: str = "") -> str:
    """Legacy helper returning declarative Domain representation."""
    return _default_domain_arg(arg_name, arg_type)


def generate_pretense_scaffold(
    pyi_path: str,
    stem: str,
    impl_stem: str,
    lib_pkg: str,
    impl_path: str | None = None,
    is_interface: bool | None = None,
) -> str:
    """Generates canonical Pretense state machine, fake, unit tests, and fuzzing skeleton."""
    elements = extract_pyi_elements(pyi_path)
    classes = elements["classes"]
    has_singleton = elements["has_singleton"] or impl_stem.endswith("_impl")

    # Filter service classes (exclude error, message, config, event, spec, state types)
    service_classes = [
        c for c in classes
        if not c["name"].endswith(("Error", "Message", "Config", "Event", "Spec", "State"))
    ]
    if not service_classes and classes:
        service_classes = classes

    clean_stem = impl_stem.replace("_impl", "").replace("_pretense", "")
    pascal_name = "".join(p.capitalize() for p in clean_stem.split("_"))
    if not pascal_name:
        pascal_name = "Target"

    if len(service_classes) == 1:
        target_cls_name = service_classes[0]["name"]
    else:
        target_cls_name = pascal_name

    state_cls_name = f"{pascal_name}State"
    iface_sm_cls_name = f"{pascal_name}StateMachine"
    impl_sm_cls_name = f"{pascal_name}ImplPseudoStateMachine"

    # Collect properties across all service classes (deduplicated)
    all_props: list[str] = []
    seen_props: set[str] = set()
    for sc in service_classes:
        for prop in sc["properties"]:
            if prop not in seen_props:
                seen_props.add(prop)
                all_props.append(prop)

    # Count method occurrences across service classes to disambiguate collisions
    from collections import Counter
    method_counts: Counter[str] = Counter()
    for sc in service_classes:
        for m in sc["methods"]:
            method_counts[m["name"]] += 1

    # Infer is_interface if not explicitly set
    if is_interface is None:
        if pyi_path and os.path.isfile(pyi_path):
            pyi_dir = os.path.dirname(os.path.abspath(pyi_path))
            pyi_base = os.path.basename(pyi_path)
            if pyi_base.endswith("_impl.pyi"):
                iface_pyi = os.path.join(pyi_dir, pyi_base.replace("_impl.pyi", ".pyi"))
                if os.path.isfile(iface_pyi):
                    is_interface = False
            else:
                impl_pyi = os.path.join(pyi_dir, pyi_base.replace(".pyi", "_impl.pyi"))
                if os.path.isfile(impl_pyi):
                    is_interface = True

    # --------------------------------------------------------------------------
    # 1. INTERFACE PRETEST MODULE SKELETON
    # --------------------------------------------------------------------------
    if is_interface is True:
        lines: list[str] = [
            f'"""Pretense state machine, fake synthesis, and property fuzzing for {target_cls_name}."""',
            "",
            "from __future__ import annotations",
            "",
            "from dataclasses import dataclass, field",
            "from typing import Any, List, Optional, Sequence, Set, Tuple",
            "",
            "from hypothesis import given, settings, strategies as st",
            "",
            "from pretense import (",
            "    Domain,",
            "    StateMachine,",
            "    make_return_value,",
            "    raises,",
            "    require,",
            "    require_arg,",
            "    sut,",
            "    sut_state,",
            "    synthesize_fake,",
            "    transition,",
            ")",
            "from pretense.compiler import compile_hypothesis_test_case",
        ]

        # Import interface types from lib package
        import_module = f"{lib_pkg}.{clean_stem}" if lib_pkg else clean_stem
        import_classes = [
            c["name"] for c in classes
            if not c["name"].endswith(("Error", "Exception"))
        ]
        if not import_classes:
            import_classes = [target_cls_name]
        lines.append(f"from {import_module} import {', '.join(import_classes)}")

        lines.extend([
            "",
            "",
            "# ==============================================================================",
            "# 1. State Machine Specification (Model & Transitions)",
            "# ==============================================================================",
            "# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).",
            "# Operational branches and contracted exceptions (with raises(ExpectedException): make_return_value())",
            "# live naturally inside the single transition body (multi-transition splitting is prohibited).",
            "# require_arg defines the caller precondition contract (checked at runtime on real calls).",
            "# Use Domain.type(T) or open domain; use preferred=[...] to cluster/bias fuzz inputs without restricting the contract.",
            "",
            "def _unimplemented_transition(name: str) -> Any:",
            '    """Placeholder for unmodeled transition return contracts that crashes at runtime."""',
            '    raise NotImplementedError(',
            '        f"Pretense transition \'{name}\' returns contract must be implemented; dummy returns are strictly prohibited."',
            '    )',
            "",
            "",
            "@dataclass",
            f"class {state_cls_name}:",
            f'    """Canonical model state for {target_cls_name} operations."""',
            "    initialized: bool = True",
        ])

        for prop in all_props:
            lines.append(f"    {prop}: Optional[Any] = None")

        lines.extend([
            "",
            "",
            f"class {iface_sm_cls_name}(StateMachine[{state_cls_name}]):",
            f'    """Unified Pretense State Machine for {pascal_name}."""',
            "",
            "    def __init__(",
            "        self,",
            f"        state: Optional[{state_cls_name}] = None,",
            "        singletons: Optional[dict[type[Any], Any]] = None,",
            "    ) -> None:",
            f"        super().__init__(state=state or {state_cls_name}(), singletons=singletons)",
        ])

        for sc in service_classes:
            cls_name = sc["name"]
            for m in sc["methods"]:
                mname = m["name"]
                arg_info = m.get("arg_info", [{"name": a, "type": "Any"} for a in m["args"]])
                ret_type = m.get("return_type", "Any")
                fn_name = mname if method_counts[mname] == 1 else f"{cls_name.lower()}_{mname}"
                lines.extend([
                    "",
                    f"    @transition({cls_name}.{mname})",
                    f"    def {fn_name}(",
                    "        self,",
                ])
                for ai in arg_info:
                    atype = ai["type"] if ai["type"] else "Any"
                    lines.append(f"        {ai['name']}: {atype},")
                lines.extend([
                    "    ) -> None:",
                    "        require(self.state.initialized)",
                ])
                for ai in arg_info:
                    dom_expr = _default_domain_arg(ai["name"], ai.get("type", ""))
                    lines.append(f"        require_arg({ai['name']}, {dom_expr})")
                if ret_type in ("None", "NoneType"):
                    lines.extend([
                        "        ret = make_return_value()",
                        "        assert ret is None",
                        "        return ret",
                    ])
                else:
                    lines.extend([
                        f"        ret: {ret_type} = make_return_value(_unimplemented_transition('{fn_name}'))",
                        "        assert ret is not None",
                        "        return ret",
                    ])

        for sc in service_classes:
            cls_name = sc["name"]
            for prop in sc.get("properties", []):
                fn_name = prop if method_counts[prop] == 0 else f"{cls_name.lower()}_{prop}"
                lines.extend([
                    "",
                    f'    @transition(name="{prop}")',
                    f"    def {fn_name}(self) -> None:",
                    "        require(self.state.initialized)",
                    f"        ret: Any = make_return_value(_unimplemented_transition('{fn_name}'))",
                    "        assert ret is not None",
                    "        return ret",
                ])

        lines.extend([
            "",
            "    @transition.seeding",
            "    def seed_initial(self) -> None:",
            '        """Seed state machine state for fake initialization."""',
            "        self.state.initialized = True",
        ])

        fake_cls_name = f"Fake{pascal_name}"
        lines.extend([
            "",
            "",
            f"proto = {iface_sm_cls_name}()",
            "",
            "",
            "# ==============================================================================",
            "# 2. State Machine Proto & Fakes",
            "# ==============================================================================",
            "",
            f"{fake_cls_name} = synthesize_fake({iface_sm_cls_name})",
            "",
        ])
        if len(service_classes) > 1:
            fake_ret_type = f"Tuple[{', '.join(c['name'] for c in service_classes)}]"
            lines.extend([
                f"def make_{clean_stem}_fakes(",
                f"    state: Optional[{state_cls_name}] = None,",
                f") -> {fake_ret_type}:",
                f'    """Synthesizes fake instances for component services sharing model state."""',
                f"    fake = {fake_cls_name}(state=state or {state_cls_name}())",
                f"    return (",
                f"        " + ",\n        ".join("fake" for _ in service_classes) + ",",
                f"    )",
            ])
        else:
            single_cls = service_classes[0]["name"] if service_classes else target_cls_name
            lines.extend([
                f"def make_{clean_stem}_fake(",
                f"    state: Optional[{state_cls_name}] = None,",
                f") -> {single_cls}:",
                f'    """Synthesizes fake instance for {single_cls}."""',
                f"    return {fake_cls_name}(state=state or {state_cls_name}())",
            ])

        lines.extend([
            "",
            "",
            "# ==============================================================================",
            "# 3. Hypothesis Stateful Fuzzing on Fake",
            "# ==============================================================================",
            "",
            f"Fake{pascal_name}FuzzTest = compile_hypothesis_test_case(",
            "    proto=proto,",
            f"    initial_state_factory={state_cls_name},",
            f'    name="Fake{pascal_name}FuzzTest",',
            ")",
            "",
        ])
        return "\n".join(lines)

    # --------------------------------------------------------------------------
    # 2. IMPLEMENTATION PRETEST MODULE SKELETON
    # --------------------------------------------------------------------------
    if is_interface is False:
        lines = [
            f'"""Pretense implementation pseudo-state machine and real test suite for {target_cls_name}."""',
            "",
            "from __future__ import annotations",
            "",
            "from typing import Any, List, Optional, Sequence, Set, Tuple",
            "import unittest",
            "",
            "from hypothesis import given, settings, strategies as st",
            "",
            "from pretense import (",
            "    call_target,",
            "    raises,",
            "    require,",
            "    sut,",
            "    sut_state,",
            "    transition,",
            ")",
            "from pretense.compiler import compile_hypothesis_test_case",
        ]

        if has_singleton:
            lines.append("from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system")

        pretense_pkg = lib_pkg.rsplit(".", 1)[0] + ".pretense" if lib_pkg else "pretense"
        iface_symbols = [iface_sm_cls_name, state_cls_name, f"Fake{pascal_name}"]
        if len(service_classes) > 1:
            iface_symbols.append(f"make_{clean_stem}_fakes")
        else:
            iface_symbols.append(f"make_{clean_stem}_fake")
        lines.append(f"from {pretense_pkg}.{clean_stem}_pretense import ({', '.join(iface_symbols)})")

        import_module = f"{lib_pkg}.{impl_stem}" if lib_pkg else impl_stem
        import_classes = [
            c["name"] for c in classes
            if not c["name"].endswith(("Error", "Exception"))
        ]
        if not import_classes:
            import_classes = [target_cls_name]
        import_symbols = list(import_classes)
        if has_singleton:
            import_symbols.append("__initialize__")
        lines.append(f"from {import_module} import {', '.join(import_symbols)}")

        lines.extend([
            "",
            "",
            "# ==============================================================================",
            "# 1. Implementation Pseudo-State Machine",
            "# ==============================================================================",
            "",
            f"class {impl_sm_cls_name}({iface_sm_cls_name}):",
            f'    """Implementation pseudo-state machine for {pascal_name}."""',
        ])

        for sc in service_classes:
            cls_name = sc["name"]
            for m in sc["methods"]:
                mname = m["name"]
                arg_info = m.get("arg_info", [{"name": a, "type": "Any"} for a in m["args"]])
                fn_name = mname if method_counts[mname] == 1 else f"{cls_name.lower()}_{mname}"
                call_args = ", ".join(ai["name"] for ai in arg_info)
                lines.extend([
                    "",
                    f"    @transition({cls_name}.{mname})",
                    f"    def {fn_name}(",
                    "        self,",
                ])
                for ai in arg_info:
                    atype = ai["type"] if ai["type"] else "Any"
                    lines.append(f"        {ai['name']}: {atype},")
                lines.extend([
                    "    ) -> Any:",
                    f"        target: {cls_name} = sut({cls_name})",
                    f"        ret = call_target(target.{mname}({call_args}))",
                    "        return ret",
                ])

        for sc in service_classes:
            cls_name = sc["name"]
            for prop in sc.get("properties", []):
                fn_name = prop if method_counts[prop] == 0 else f"{cls_name.lower()}_{prop}"
                lines.extend([
                    "",
                    f'    @transition(name="{prop}")',
                    f"    def {fn_name}(self) -> Any:",
                    f"        target: {cls_name} = sut({cls_name})",
                    f"        ret = call_target(getattr(target, \"{prop}\"))",
                    "        return ret",
                ])

        lines.extend([
            "",
            "",
            f"proto = {impl_sm_cls_name}()",
            "",
            "",
            "# ==============================================================================",
            "# 2. Real Implementation Tests",
            "# ==============================================================================",
            "",
            f"class Test{pascal_name}ImplReal(unittest.TestCase):",
            f'    """Verifies that concrete implementation satisfies contracts."""',
            "",
            "    def setUp(self) -> None:",
        ])

        if has_singleton:
            lines.extend([
                "        self.registry = LifecycleRegistry()",
                "        __initialize__(self.registry)",
                "        self.phase_scope = enter_phase(system, registry=self.registry)",
                "        self.phase_scope.__enter__()",
            ])
            if len(service_classes) > 1:
                for c in service_classes:
                    lines.append(f"        self.{c['name'].lower()} = get_singleton({c['name']})")
                svc_dict = ", ".join(f"{c['name']}: self.{c['name'].lower()}" for c in service_classes)
                lines.append(f"        self.sm = {impl_sm_cls_name}(singletons={{{svc_dict}}})")
                for c in service_classes:
                    lines.append(f"        self.checked_{c['name'].lower()} = self.sm.as_checked({c['name']}, self.{c['name'].lower()})")
            else:
                lines.append(f"        self.real = get_singleton({target_cls_name})")
                lines.append(f"        self.sm = {impl_sm_cls_name}(singletons={{{target_cls_name}: self.real}})")
                lines.append(f"        self.checked = self.sm.as_checked({target_cls_name}, self.real)")
            lines.extend([
                "",
                "    def tearDown(self) -> None:",
                "        self.phase_scope.__exit__(None, None, None)",
            ])
        else:
            if len(service_classes) > 1:
                for c in service_classes:
                    lines.append(f"        self.{c['name'].lower()} = {c['name']}()")
                svc_dict = ", ".join(f"{c['name']}: self.{c['name'].lower()}" for c in service_classes)
                lines.append(f"        self.sm = {impl_sm_cls_name}(singletons={{{svc_dict}}})")
                for c in service_classes:
                    lines.append(f"        self.checked_{c['name'].lower()} = self.sm.as_checked({c['name']}, self.{c['name'].lower()})")
            else:
                lines.append(f"        self.real = {target_cls_name}()")
                lines.append(f"        self.sm = {impl_sm_cls_name}(singletons={{{target_cls_name}: self.real}})")
                lines.append(f"        self.checked = self.sm.as_checked({target_cls_name}, self.real)")

        lines.extend([
            "",
            "    def test_real_conformance(self) -> None:",
            "        # Drive scenarios via self.checked.<method>(*args).",
            f'        self.fail("Test{pascal_name}ImplReal.test_real_conformance must be implemented with concrete scenarios.")',
            "",
            "",
            "# ==============================================================================",
            "# 3. Hypothesis Stateful Fuzzing on Real SUT",
            "# ==============================================================================",
            "",
        ])

        if len(service_classes) > 1:
            sut_cls_name = f"{pascal_name}SUT"
            lines.extend([
                f"class {sut_cls_name}:",
                f'    """Aggregate SUT exposing component services for {pascal_name} state machine testing."""',
                "",
                "    def __init__(self) -> None:",
                "        self.__dict__[\"_services\"] = ()",
            ])
            if has_singleton:
                lines.extend([
                    "        self.registry = LifecycleRegistry()",
                    "        __initialize__(self.registry)",
                    "        self.phase_scope = enter_phase(system, registry=self.registry)",
                    "        self.phase_scope.__enter__()",
                ])
                for c in service_classes:
                    lines.append(f"        self.{c['name'].lower()} = get_singleton({c['name']})")
                svc_tuple = ", ".join(f"self.{c['name'].lower()}" for c in service_classes)
                lines.append(f"        self.__dict__[\"_services\"] = ({svc_tuple},)")
            else:
                for c in service_classes:
                    lines.append(f"        self.{c['name'].lower()} = {c['name']}()")
                svc_tuple = ", ".join(f"self.{c['name'].lower()}" for c in service_classes)
                lines.append(f"        self.__dict__[\"_services\"] = ({svc_tuple},)")

            lines.extend([
                "",
                "    def __getattr__(self, name: str) -> Any:",
                "        if name.startswith(\"__\") and name.endswith(\"__\"):",
                "            raise AttributeError(name)",
                "        for service in self.__dict__.get(\"_services\", ()):",
                "            if hasattr(service, name):",
                "                return getattr(service, name)",
                f'        raise AttributeError(f"{{type(self).__name__}} has no attribute {{name!r}}")',
                "",
                f"def make_sut() -> {sut_cls_name}:",
                f"    return {sut_cls_name}()",
            ])
        else:
            single_cls = service_classes[0]["name"] if service_classes else target_cls_name
            lines.extend([
                f"def make_sut() -> {single_cls}:",
            ])
            if has_singleton:
                lines.extend([
                    "    registry = LifecycleRegistry()",
                    "    __initialize__(registry)",
                    "    scope = enter_phase(system, registry=registry)",
                    "    scope.__enter__()",
                    f"    return get_singleton({single_cls})",
                ])
            else:
                lines.extend([
                    f"    return {single_cls}()",
                ])

        lines.extend([
            "",
            "",
            f"{pascal_name}FuzzTest = compile_hypothesis_test_case(",
            "    proto=proto,",
            "    sut_factory=make_sut,",
            f"    initial_state_factory={state_cls_name},",
            f'    name="{pascal_name}FuzzTest",',
            ")",
            "",
        ])
        return "\n".join(lines)

    # --------------------------------------------------------------------------
    # 3. STANDALONE UNIFIED MODULE SKELETON (Fallback for single-component units)
    # --------------------------------------------------------------------------

    lines: list[str] = [
        f'"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for {target_cls_name}."""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass, field",
        "from typing import Any, Optional, Sequence, Set, Tuple",
        "import unittest",
        "",
        "from hypothesis import given, settings, strategies as st",
        "",
        "from pretense import (",
        "    Domain,",
        "    StateMachine,",
        "    call_target,",
        "    make_return_value,",
        "    raises,",
        "    require,",
        "    require_arg,",
        "    sut,",
        "    sut_state,",
        "    synthesize_fake,",
        "    transition,",
        ")",
        "from pretense.compiler import compile_hypothesis_test_case",
    ]

    if has_singleton:
        lines.append("from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system")

    # Import target classes from lib package
    import_module = f"{lib_pkg}.{impl_stem}" if lib_pkg else impl_stem
    import_classes = [
        c["name"] for c in classes
        if not c["name"].endswith(("Error", "Exception"))
    ]
    if not import_classes:
        import_classes = [target_cls_name]
    import_symbols = list(import_classes)
    if has_singleton:
        import_symbols.append("__initialize__")
    lines.append(f"from {import_module} import {', '.join(import_symbols)}")

    sm_cls_name = f"{pascal_name}StateMachine"

    lines.extend([
        "",
        "",
        "# ==============================================================================",
        "# 1. State Machine Specification (Model & Transitions)",
        "# ==============================================================================",
        "# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).",
        "# Operational branches and contracted exceptions (with raises(ExpectedException): make_return_value())",
        "# live naturally inside the single transition body (multi-transition splitting is prohibited).",
        "# require_arg defines the caller precondition contract (checked at runtime on real calls).",
        "# Use Domain.type(T) or open domain; use preferred=[...] to cluster/bias fuzz inputs without restricting the contract.",
        "",
        "def _unimplemented_transition(name: str) -> Any:",
        '    """Placeholder for unmodeled transition return contracts that crashes at runtime."""',
        '    raise NotImplementedError(',
        '        f"Pretense transition \'{name}\' returns contract must be implemented; dummy returns are strictly prohibited."',
        '    )',
        "",
        "",
        "@dataclass",
        f"class {state_cls_name}:",
        f'    """Canonical model state for {target_cls_name} operations."""',
        "    initialized: bool = True",
    ])

    for prop in all_props:
        lines.append(f"    {prop}: Optional[Any] = None")

    sut_cls_name = f"{pascal_name}SUT"
    if len(service_classes) > 1:
        sut_type = sut_cls_name
        lines.extend([
            "",
            "",
            f"class {sut_cls_name}:",
            f'    """Aggregate SUT exposing component services for {pascal_name} state machine testing."""',
            "",
            "    tier = system",
            "",
            "    def __init__(self) -> None:",
            "        self.__dict__[\"_services\"] = ()",
        ])
        if has_singleton:
            lines.extend([
                "        self.registry = LifecycleRegistry()",
                "        __initialize__(self.registry)",
                "        self.phase_scope = enter_phase(system, registry=self.registry)",
                "        self.phase_scope.__enter__()",
            ])
            for c in service_classes:
                lines.append(f"        self.{c['name'].lower()} = get_singleton({c['name']})")
            svc_tuple = ", ".join(f"self.{c['name'].lower()}" for c in service_classes)
            lines.append(f"        self.__dict__[\"_services\"] = ({svc_tuple},)")
        else:
            for c in service_classes:
                lines.append(f"        self.{c['name'].lower()} = {c['name']}()")
            svc_tuple = ", ".join(f"self.{c['name'].lower()}" for c in service_classes)
            lines.append(f"        self.__dict__[\"_services\"] = ({svc_tuple},)")

        lines.extend([
            "",
            "    def __getattr__(self, name: str) -> Any:",
            "        if name.startswith(\"__\") and name.endswith(\"__\"):",
            "            raise AttributeError(name)",
            "        for service in self.__dict__.get(\"_services\", ()):",
            "            if hasattr(service, name):",
            "                return getattr(service, name)",
            f'        raise AttributeError(f"{{type(self).__name__}} has no attribute {{name!r}}")',
        ])
    else:
        sut_type = service_classes[0]["name"] if service_classes else target_cls_name

    lines.extend([
        "",
        "",
        f"class {sm_cls_name}(StateMachine[{state_cls_name}]):",
        f'    """Unified Pretense State Machine for {pascal_name}."""',
        "",
        "    def __init__(",
        "        self,",
        f"        state: Optional[{state_cls_name}] = None,",
        "        singletons: Optional[dict[type[Any], Any]] = None,",
        "    ) -> None:",
        f"        super().__init__(state=state or {state_cls_name}(), singletons=singletons)",
    ])

    # Transitions for methods across all service classes
    transition_counter = 1
    for sc in service_classes:
        cls_name = sc["name"]
        for m in sc["methods"]:
            mname = m["name"]
            arg_info = m.get("arg_info", [{"name": a, "type": "Any"} for a in m["args"]])
            ret_type = m.get("return_type", "Any")
            fn_name = mname if method_counts[mname] == 1 else f"{cls_name.lower()}_{mname}"
            lines.extend([
                "",
                f"    @transition({cls_name}.{mname})",
                f"    def {fn_name}(",
                "        self,",
            ])
            for ai in arg_info:
                atype = ai["type"] if ai["type"] else "Any"
                lines.append(f"        {ai['name']}: {atype},")
            lines.extend([
                "    ) -> None:",
                "        require(self.state.initialized)",
            ])
            for ai in arg_info:
                dom_expr = _default_domain_arg(ai["name"], ai.get("type", ""))
                lines.append(f"        require_arg({ai['name']}, {dom_expr})")
            call_args = ", ".join(ai["name"] for ai in arg_info)
            if ret_type in ("None", "NoneType"):
                lines.extend([
                    "        ret = make_return_value()",
                    "        assert ret is None",
                    "        return ret",
                ])
            else:
                lines.extend([
                    f"        ret: {ret_type} = make_return_value(_unimplemented_transition('{fn_name}'))",
                    "        assert ret is not None",
                    "        return ret",
                ])
            transition_counter += 1

    # Transitions for properties across service classes
    for sc in service_classes:
        cls_name = sc["name"]
        for prop in sc.get("properties", []):
            fn_name = prop if method_counts[prop] == 0 else f"{cls_name.lower()}_{prop}"
            lines.extend([
                "",
                f'    @transition(name="{prop}")',
                f"    def {fn_name}(self) -> None:",
                "        require(self.state.initialized)",
                f"        ret: Any = make_return_value(_unimplemented_transition('{fn_name}'))",
                "        assert ret is not None",
                "        return ret",
            ])
            transition_counter += 1

    # Seeding transition
    lines.extend([
        "",
        "    @transition.seeding",
        "    def seed_initial(self) -> None:",
        '        """Seed state machine state for fake initialization."""',
        "        self.state.initialized = True",
    ])

    lines.extend([
        "",
        "",
        f"proto = {sm_cls_name}()",
        "",
        "",
        "# ==============================================================================",
        "# 2. State Machine Proto & Fakes",
        "# ==============================================================================",
        "",
    ])

    clean_stem = impl_stem.replace("_impl", "")
    fake_cls_name = f"Fake{pascal_name}"
    lines.append(f"{fake_cls_name} = synthesize_fake({sm_cls_name})")
    lines.append("")
    if len(service_classes) > 1:
        fake_ret_type = f"Tuple[{', '.join(c['name'] for c in service_classes)}]"
        lines.extend([
            f"def make_{clean_stem}_fakes(",
            f"    state: Optional[{state_cls_name}] = None,",
            f") -> {fake_ret_type}:",
            f'    """Synthesizes fake instances for component services sharing model state."""',
            f"    fake = {fake_cls_name}(state=state or {state_cls_name}())",
            f"    return (",
            f"        " + ",\n        ".join("fake" for _ in service_classes) + ",",
            f"    )",
        ])
    else:
        single_cls = service_classes[0]["name"] if service_classes else target_cls_name
        lines.extend([
            f"def make_{clean_stem}_fake(",
            f"    state: Optional[{state_cls_name}] = None,",
            f") -> {single_cls}:",
            f'    """Synthesizes fake instance for {single_cls}."""',
            f"    return {fake_cls_name}(state=state or {state_cls_name}())",
        ])

    lines.extend([
        "",
        "",
        "# ==============================================================================",
        "# 3. Real Implementation Tests",
        "# ==============================================================================",
        "",
        f"class Test{pascal_name}ImplReal(unittest.TestCase):",
        f'    """Verifies that concrete implementation satisfies contracts."""',
        "",
        "    def setUp(self) -> None:",
    ])

    if has_singleton:
        lines.extend([
            "        self.registry = LifecycleRegistry()",
            "        __initialize__(self.registry)",
            "        self.phase_scope = enter_phase(system, registry=self.registry)",
            "        self.phase_scope.__enter__()",
        ])
        if len(service_classes) > 1:
            for c in service_classes:
                lines.append(f"        self.{c['name'].lower()} = get_singleton({c['name']})")
            svc_dict = ", ".join(f"{c['name']}: self.{c['name'].lower()}" for c in service_classes)
            lines.append(f"        self.sm = {sm_cls_name}(singletons={{{svc_dict}}})")
            for c in service_classes:
                lines.append(f"        self.checked_{c['name'].lower()} = self.sm.as_checked({c['name']}, self.{c['name'].lower()})")
        else:
            lines.append(f"        self.real = get_singleton({target_cls_name})")
            lines.append(f"        self.sm = {sm_cls_name}(singletons={{{target_cls_name}: self.real}})")
            lines.append(f"        self.checked = self.sm.as_checked({target_cls_name}, self.real)")
        lines.extend([
            "",
            "    def tearDown(self) -> None:",
            "        self.phase_scope.__exit__(None, None, None)",
        ])
    else:
        if len(service_classes) > 1:
            for c in service_classes:
                lines.append(f"        self.{c['name'].lower()} = {c['name']}()")
            svc_dict = ", ".join(f"{c['name']}: self.{c['name'].lower()}" for c in service_classes)
            lines.append(f"        self.sm = {sm_cls_name}(singletons={{{svc_dict}}})")
            for c in service_classes:
                lines.append(f"        self.checked_{c['name'].lower()} = self.sm.as_checked({c['name']}, self.{c['name'].lower()})")
        else:
            lines.append(f"        self.real = {target_cls_name}()")
            lines.append(f"        self.sm = {sm_cls_name}(singletons={{{target_cls_name}: self.real}})")
            lines.append(f"        self.checked = self.sm.as_checked({target_cls_name}, self.real)")

    lines.extend([
        "",
        "    def test_real_conformance(self) -> None:",
        "        # Drive scenarios via self.checked.<method>(*args) or self.sm.dispatch_transition('<transition_name>', *args).",
        "        # Operational postconditions and invariants are verified automatically by ensure(...);",
        "        # fixed scenario tests should contain no redundant manual self.assertEqual/assertTrue assertions.",
        f'        self.fail("Test{pascal_name}ImplReal.test_real_conformance must be implemented with concrete scenarios.")',
    ])

    lines.extend([
        "",
        "",
        "# ==============================================================================",
        "# 4. Hypothesis Stateful Fuzzing",
        "# ==============================================================================",
        "",
    ])

    if len(service_classes) > 1:
        lines.extend([
            f"def make_sut() -> {sut_cls_name}:",
            f"    return {sut_cls_name}()",
        ])
    else:
        single_cls = service_classes[0]["name"] if service_classes else target_cls_name
        lines.extend([
            f"def make_sut() -> {single_cls}:",
        ])
        if has_singleton:
            lines.extend([
                "    registry = LifecycleRegistry()",
                "    __initialize__(registry)",
                "    scope = enter_phase(system, registry=registry)",
                "    scope.__enter__()",
                f"    return get_singleton({single_cls})",
            ])
        else:
            lines.extend([
                f"    return {single_cls}()",
            ])

    lines.extend([
        "",
        "",
        f"{pascal_name}FuzzTest = compile_hypothesis_test_case(",
        "    proto=proto,",
        "    sut_factory=make_sut,",
        f"    initial_state_factory={state_cls_name},",
        f'    name="{pascal_name}FuzzTest",',
        ")",
        "",
    ])

    return "\n".join(lines)


def _resolve_lib_dir_and_pkg(module_path: str, user_lib_pkg: str | None = None) -> tuple[str, str]:
    """Resolves (filesystem_lib_dir, dot_separated_pkg_name) for the library directory."""
    abs_mod = os.path.abspath(module_path)
    parent_dir = os.path.dirname(abs_mod)
    # Check if pretense or tests directory
    if os.path.basename(parent_dir) in ("pretense", "tests"):
        part_dir = os.path.dirname(parent_dir)
    else:
        part_dir = parent_dir

    curr = part_dir
    repo_root = ""
    try:
        from support.lib import app_info
    except Exception:
        try:
            from autofab_python.support.lib import app_info
        except Exception:
            import app_info  # type: ignore
    markers = getattr(app_info, "get_config_filenames", lambda: ())() + getattr(app_info, "get_roles_filenames", lambda: ())() + ("pyproject.toml",)
    while curr and curr != os.path.dirname(curr):
        if any(os.path.isfile(os.path.join(curr, marker)) for marker in markers):
            repo_root = curr
        curr = os.path.dirname(curr)


    default_lib_dir = os.path.join(part_dir, "lib")
    if user_lib_pkg:
        if os.path.isabs(user_lib_pkg) and os.path.isdir(user_lib_pkg):
            lib_dir = user_lib_pkg
        elif repo_root and os.path.isdir(os.path.join(repo_root, user_lib_pkg)):
            lib_dir = os.path.join(repo_root, user_lib_pkg)
        elif os.path.isdir(user_lib_pkg):
            lib_dir = os.path.abspath(user_lib_pkg)
        else:
            cand = user_lib_pkg.replace(".", os.sep)
            if repo_root and os.path.isdir(os.path.join(repo_root, cand)):
                lib_dir = os.path.join(repo_root, cand)
            elif os.path.isdir(cand):
                lib_dir = os.path.abspath(cand)
            else:
                lib_dir = default_lib_dir
    else:
        lib_dir = default_lib_dir

    if repo_root and os.path.isdir(lib_dir):
        rel = os.path.relpath(lib_dir, repo_root).replace("\\", "/")
        pkg_name = rel.replace("/", ".").strip(".")
    elif user_lib_pkg:
        pkg_name = user_lib_pkg.replace("/", ".").strip(".")
    else:
        pkg_name = "lib"

    return lib_dir, pkg_name


def _resolve_lib_pkg(module_path: str, user_lib_pkg: str | None = None) -> str:
    """Resolves full package name for the library directory."""
    _, pkg = _resolve_lib_dir_and_pkg(module_path, user_lib_pkg)
    return pkg


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify and scaffold Pretense modules.")
    ap.add_argument(
        "module_path",
        nargs="?",
        default=None,
        help="path to the pretense test module",
    )
    ap.add_argument(
        "--pyi",
        default="",
        help="path to the grounding specification .pyi file",
    )
    ap.add_argument(
        "--impl",
        default="",
        help="path to the library implementation .py file",
    )
    ap.add_argument(
        "--lib-pkg",
        default="",
        help="package path for the lib directory",
    )
    ap.add_argument(
        "--scaffold",
        action="store_true",
        help="generate pretense skeleton for missing or uninitialized module and exit",
    )
    ap.add_argument(
        "--interface",
        action="store_true",
        help="lint/scaffold as an interface pretense module",
    )
    ap.add_argument(
        "--implementation",
        action="store_true",
        help="lint/scaffold as an implementation pretense module",
    )
    args = ap.parse_args()

    if args.module_path is None:
        return 0

    stem = module_stem(args.module_path)
    impl_stem = stem[:-9] if stem.endswith("_pretense") else stem
    dir_name = os.path.dirname(args.module_path)

    pyi_path = args.pyi
    if not pyi_path or not os.path.isfile(pyi_path):
        pyi_path = find_spec_pyi(args.module_path)

    lib_dir, lib_pkg = _resolve_lib_dir_and_pkg(args.module_path, args.lib_pkg)

    if args.scaffold:
        if not pyi_path or not os.path.isfile(pyi_path):
            sys.stderr.write(f"Cannot scaffold {args.module_path}: specification .pyi not found\n")
            return 1
        is_interface = None
        if args.interface:
            is_interface = True
        elif args.implementation:
            is_interface = False
        skeleton = generate_pretense_scaffold(
            pyi_path=pyi_path,
            stem=stem,
            impl_stem=impl_stem,
            lib_pkg=lib_pkg,
            impl_path=args.impl or None,
            is_interface=is_interface,
        )
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        write_text(args.module_path, skeleton)
        return 0

    # Verification mode
    if not os.path.isfile(args.module_path):
        sys.stderr.write(f"File not found: {args.module_path}\n")
        return 1

    content = read_text(args.module_path)
    syntax_errs = check_syntax(args.module_path)
    if syntax_errs:
        for err in syntax_errs:
            sys.stderr.write(f"{err}\n")
        return 1

    if is_uninitialized_pretense_module(content) and "_unimplemented_transition" not in content:
        sys.stderr.write(
            f"{args.module_path} is uninitialized (missing State dataclass or TestCase classes). "
            f"Consult your Companion Guide (autofab_python/guides/pretense.md) for required structure.\n"
        )
        return 1

    try:
        tree = ast.parse(content, filename=args.module_path)
    except SyntaxError as e:
        sys.stderr.write(f"{format_syntax_error(args.module_path, e, content)}\n")
        return 1

    all_errors: list[str] = []

    is_interface = False
    if args.interface:
        is_interface = True
    elif args.implementation:
        is_interface = False
    elif pyi_path:
        is_interface = not os.path.basename(pyi_path).endswith("_impl.pyi") and os.path.exists(
            pyi_path.replace(".pyi", "_impl.pyi")
        )
    elif args.module_path:
        stem = os.path.basename(args.module_path)
        if not stem.endswith("_impl_pretense.py"):
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(args.module_path)))
            low_impl = os.path.join(parent_dir, "low", stem.replace("_pretense.py", "_impl.pyi"))
            if os.path.exists(low_impl):
                is_interface = True

    struct_errs = check_pretense_structure(tree, args.module_path, is_interface=is_interface)
    all_errors.extend(struct_errs)

    assert_errs = check_single_argument_assertions(tree, args.module_path)
    all_errors.extend(assert_errs)

    import_errs = check_pretense_imports(content, pyi_path, is_impl=not is_interface, file_path=args.module_path)
    all_errors.extend(import_errs)

    test_import_errs = check_test_imports(lib_pkg, args.module_path)
    all_errors.extend(test_import_errs)

    rel_import_errs = check_no_relative_parent_imports(args.module_path, tree=tree)
    all_errors.extend(rel_import_errs)

    bare_parts_errs = check_no_bare_parts_imports(args.module_path, tree=tree)
    all_errors.extend(bare_parts_errs)

    private_import_errs = check_no_private_imports(args.module_path, tree=tree)
    all_errors.extend(private_import_errs)

    tautology_errs = check_tautological_assertions(args.module_path, tree=tree, check_empty=True)
    all_errors.extend(tautology_errs)

    no_error_test_errs = check_no_error_testing(args.module_path, tree=tree)
    all_errors.extend(no_error_test_errs)

    sys_module_errs = check_no_sys_modules_tampering(args.module_path, tree=tree)
    all_errors.extend(sys_module_errs)

    outcome_errs = check_transition_outcomes(tree, args.module_path)
    all_errors.extend(outcome_errs)

    lifted_errs = check_lifted_expr_usage(tree, args.module_path, is_impl=not is_interface)
    all_errors.extend(lifted_errs)

    sentinel_errs = check_no_residual_sentinels(tree, args.module_path)
    all_errors.extend(sentinel_errs)

    disambig_errs = check_multi_transition_disambiguation(tree, args.module_path)
    all_errors.extend(disambig_errs)

    algo_sm_errs = check_no_algorithmic_state_machines(tree, args.module_path)
    all_errors.extend(algo_sm_errs)

    frozen_errs = check_no_frozen_exceptions(args.module_path)
    all_errors.extend(frozen_errs)

    skip_errs = check_banned_skips(args.module_path, tree=tree, error_code="PRE_LINT_NO_SKIP")
    all_errors.extend(skip_errs)

    pyi_elements = extract_pyi_elements(pyi_path) if pyi_path and os.path.isfile(pyi_path) else None
    target_internal_errs = check_pretense_target_internals(tree, args.module_path, pyi_elements=pyi_elements)
    all_errors.extend(target_internal_errs)

    proto_prop_errs = check_transition_protocol_properties(tree, args.module_path, pyi_elements=pyi_elements)
    all_errors.extend(proto_prop_errs)

    placeholder_errs = check_no_scaffold_placeholders(tree, args.module_path)
    all_errors.extend(placeholder_errs)

    type_ignore_errs = check_type_ignore(args.module_path)
    all_errors.extend(type_ignore_errs)

    if all_errors:
        for err in all_errors:
            sys.stderr.write(f"{err}\n")
        return 1

    dry_run_errs = check_test_dry_run(lib_dir, args.module_path)
    if dry_run_errs:
        for err in dry_run_errs:
            sys.stderr.write(f"{err}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
