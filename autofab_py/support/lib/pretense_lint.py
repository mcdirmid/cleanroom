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
        check_no_top_level_probes,
        check_no_error_testing,
        check_no_try_except_in_tests,
        check_no_lifecycle_scope_leaks,
        check_syntax,
        check_tautological_assertions,
        check_test_dry_run,
        check_test_impl_imports,
        check_test_imports,
        check_type_ignore,
        check_no_pragma_no_cover,
        find_spec_pyi,
        format_syntax_error,
        module_file,
        module_stem,
        package_of,
        read_text,
        write_text,
    )
except ImportError:
    from autofab_py.support.lib.build_lint_common import (  # type: ignore
        check_banned_skips,
        check_no_bare_parts_imports,
        check_no_frozen_exceptions,
        check_no_private_imports,
        check_no_relative_parent_imports,
        check_no_sys_modules_tampering,
        check_no_top_level_probes,
        check_no_error_testing,
        check_no_try_except_in_tests,
        check_no_lifecycle_scope_leaks,
        check_syntax,
        check_tautological_assertions,
        check_test_dry_run,
        check_test_impl_imports,
        check_test_imports,
        check_type_ignore,
        check_no_pragma_no_cover,
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
    if (
        "<TargetClass>" in content
        or "<target_impl>" in content
        or "_unimplemented_transition" in content
    ):
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
                    if base_id in ("TestCase", "unittest.TestCase", "LifecycleTestCase"):
                        has_test = True
                    elif (
                        base_id in ("StateMachine", "StateMachineProto")
                        or base_id.endswith("StateMachine")
                    ):
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
                    elif alias.name.endswith("StateMachine") and alias.name not in (
                        "StateMachine",
                        "StateMachineProto",
                    ):
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
            if base_id in ("TestCase", "unittest.TestCase", "LifecycleTestCase"):
                test_classes.append(c)
            elif base_id in ("StateMachine", "StateMachineProto") or base_id.endswith(
                "StateMachine"
            ):
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
            errors.append(
                "Missing Pretense StateMachine class in interface pretense module."
            )
        if not state_classes and not imported_state:
            errors.append(
                "Missing Pretense model state class (interface must define a dataclass ending with 'State')."
            )
        for tc in test_classes:
            if tc.name.endswith("Real") or "Real" in tc.name:
                errors.append(
                    f"{file_path}:{tc.lineno}: error: Interface pretense module must not contain real SUT test classes ('{tc.name}'). "
                    "Real SUT tests belong exclusively in the implementation pretense module (*_impl_pretense.py); "
                    "interface pretense modules define fixed tests against the synthesized fake ('Test<Name>Fake')."
                )
        return errors


    # Implementation pretense module
    if (imported_sm or imported_state) and state_classes:
        errors.append(
            f"{file_path}:{state_classes[0].lineno}: error [PN_IMPL_NO_STATE_CLASS]: "
            f"Implementation pretense module must not define State dataclasses ({', '.join(c.name for c in state_classes)}). "
            "The implementation pseudo-state machine defines zero state classes; it piggybacks on the interface StateMachine state."
        )

    if (
        not state_classes
        and not imported_state
        and not (test_classes or compiled_tests)
    ):
        errors.append(
            "Missing Pretense model state class (must define or import a dataclass ending with 'State')."
        )

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
                        if alias.name in (
                            "ensure",
                            "ensure_ret",
                            "ensure_raises",
                            "TransitionContext",
                            "Expr",
                        ):
                            errors.append(
                                f"{prefix}{node.lineno}: error [PN_NO_LEGACY_IMPORT]: Importing legacy Pretense symbol '{alias.name}' is strictly prohibited in Pretense 1 Next. "
                                "Use 'call_target', 'raises', 'assert', 'sut', 'sut_state', 'require', or inner transitions ('self.inner_<name>(...)')."
                            )
                        elif is_impl and alias.name == "require_arg":
                            errors.append(
                                f"{prefix}{node.lineno}: error [PN_IMPL_NO_REQUIRE_ARG_IMPORT]: Importing 'require_arg' is strictly prohibited in implementation pretense modules (*_impl_pretense.py). Domain constraints belong exclusively to the interface state machine."
                            )
                        elif is_impl and alias.name == "transition":
                            errors.append(
                                f"{prefix}{node.lineno}: error [PN_IMPL_NO_TRANSITION_IMPORT]: Importing 'transition' is strictly prohibited in implementation pretense modules (*_impl_pretense.py). Outer transitions are declared exclusively on interface state machines; implementation pseudo-state machines only override inner transitions ('inner_<name>')."
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
                target_id = (
                    child.func.value.id
                    if isinstance(child.func.value, ast.Name)
                    else ""
                )
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
                isinstance(func, ast.Attribute)
                and func.attr in ("transition", "seeding")
            ):
                has_trans_dec = True
                dec_call = d
                if (isinstance(func, ast.Attribute) and func.attr == "seeding") or any(
                    kw.arg == "seeding" for kw in d.keywords
                ):
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


    if is_impl:
        errors.append(
            f"{file_path}:{node.lineno}: error [PN_IMPL_NO_OUTER_TRANSITION]: Implementation pseudo-state machines must NOT declare '@transition' or override outer transition '{fn_name}'. Implementation pseudo-state machines must only override inner transitions ('inner_{fn_name}') to bind the SUT so that precondition and domain guards remain active."
        )

    # PN001: Correct decorator
    if (
        dec_call
        and not dec_call.args
        and not any(kw.arg in ("seeding", "name") for kw in dec_call.keywords)
        and getattr(dec_call.func, "attr", "") != "seeding"
    ):
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
            func_id = (
                child.func.id
                if isinstance(child.func, ast.Name)
                else getattr(child.func, "attr", "")
            )
            if func_id == "ensure":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PRE_LINT_NO_LEGACY_ENSURE]: 'ensure(...)' is obsolete in Pretense 1 Next. Use native Python 'assert ...' instead."
                )
            elif func_id == "ensure_ret":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PRE_LINT_NO_LEGACY_ENSURE_RET]: 'ensure_ret(...)' is obsolete in Pretense 1 Next. In interface SM, use inner transitions ('ret = self.inner_<name>(...)'); in impl pseudo-SM, override 'inner_<name>' and use 'target.method(...)'.",
                )
            elif func_id == "ensure_raises":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PRE_LINT_NO_LEGACY_ENSURE_RAISES]: 'ensure_raises(...)' is obsolete in Pretense 1 Next. Use 'Env[bool]' + 'require_env(healthy_cond, ExpectedException)'."
                )
            elif func_id == "require_arg":
                if is_impl:
                    errors.append(
                        f"{file_path}:{child.lineno}: error [PN_IMPL_NO_REQUIRE_ARG]: 'require_arg(...)' is strictly prohibited in implementation pseudo-state machines. Domain constraints and generation domains belong exclusively to the interface state machine."
                    )
            elif func_id == "require":
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Call) and (
                        (
                            isinstance(sub.func, ast.Name)
                            and sub.func.id == "sut"
                        )
                        or (
                            isinstance(sub.func, ast.Attribute)
                            and sub.func.attr == "sut"
                        )
                    ):
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN009_REQUIRE_PURITY]: require() cannot reference SUT via sut(...). It must only inspect 'self.state' or collaborator 'sut_state(...)'."
                        )
                    elif isinstance(sub, ast.Name) and sub.id in input_args:
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN009_REQUIRE_PURITY]: require() cannot reference transition input argument '{sub.id}'. "
                            f"Preconditions only evaluate state. To constrain input arguments relative to state collections (such as entity existence), use: "
                            f"'require_arg({sub.id}, Domain.in_set(self.state.<collection>))' (optionally with 'error=ExpectedError' as documentation)."
                        )

    # Pivot Node Verification (only for non-seeding transitions)
    if not is_seeding:
        has_inner_call = any(
            isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and isinstance(c.func.value, ast.Name)
            and c.func.value.id == "self"
            and (c.func.attr.startswith("inner_") or c.func.attr.startswith("_inner_"))
            for c in ast.walk(node)
        )
        call_target_calls = [
            c
            for c in ast.walk(node)
            if isinstance(c, ast.Call)
            and (
                (isinstance(c.func, ast.Name) and c.func.id == "call_target")
                or (isinstance(c.func, ast.Attribute) and c.func.attr == "call_target")
            )
        ]
        has_call_target = len(call_target_calls) > 0
        sut_calls = [
            c
            for c in ast.walk(node)
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
                "add",
                "remove",
                "discard",
                "pop",
                "popitem",
                "clear",
                "update",
                "append",
                "extend",
                "insert",
                "put",
                "assign",
                "set",
                "delete",
                "__setitem__",
            }

            def _is_self_state_target(n: ast.AST) -> bool:
                if (
                    isinstance(n, ast.Attribute)
                    and isinstance(n.value, ast.Name)
                    and n.value.id == "self"
                    and n.attr == "state"
                ):
                    return True
                if isinstance(n, ast.Attribute):
                    return _is_self_state_target(n.value)
                return False

            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for t in child.targets:
                        if _is_self_state_target(t):
                            errors.append(
                                f"{file_path}:{child.lineno}: error [PN_IMPL_NO_STATE_MUTATION]: Transition '{fn_name}' in implementation pseudo-state machine must not mutate 'self.state'. Model state transitions are already executed by the inherited interface transition before delegating to 'call_target(...)'. Implementation transitions must only invoke 'call_target(...)' and assert postconditions."
                            )
                elif isinstance(child, (ast.AugAssign, ast.AnnAssign)):
                    if _is_self_state_target(child.target):
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN_IMPL_NO_STATE_MUTATION]: Transition '{fn_name}' in implementation pseudo-state machine must not mutate 'self.state'. Model state transitions are already executed by the inherited interface transition before delegating to 'call_target(...)'. Implementation transitions must only invoke 'call_target(...)' and assert postconditions."
                        )
                elif isinstance(child, ast.Call) and isinstance(
                    child.func, ast.Attribute
                ):
                    if child.func.attr in mutating_methods and _is_self_state_target(
                        child.func.value
                    ):
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN_IMPL_NO_STATE_MUTATION]: Transition '{fn_name}' in implementation pseudo-state machine must not mutate 'self.state' (calling '{child.func.attr}()' on self.state). Model state transitions are already executed by the inherited interface transition before delegating to 'call_target(...)'. Implementation transitions must only invoke 'call_target(...)' and assert postconditions."
                        )

            if not has_call_target and not has_inner_call:
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
            if not has_inner_call:
                errors.append(
                    f"{file_path}:{node.lineno}: error [PN_IFACE_INNER_TRANSITION_REQUIRED]: Transition '{fn_name}' in interface state machine must call an inner transition ('ret = self.inner_{fn_name}(...)'). For void methods returning None, invoke an inner transition returning None."
                )

    return errors



def _check_inner_transition_body(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str,
    cls_name: str,
) -> list[str]:
    """Validates the body of an implementation pseudo-state machine inner transition."""
    errors: list[str] = []
    fn_name = node.name

    for child in ast.walk(node):
        if isinstance(child, ast.Lambda):
            errors.append(
                f"{file_path}:{child.lineno}: error [PN002_NO_LAMBDAS]: Lambdas are prohibited in Pretense Next transitions. Write plain Python expressions."
            )
        elif isinstance(child, ast.Call):
            func_id = (
                child.func.id
                if isinstance(child.func, ast.Name)
                else getattr(child.func, "attr", "")
            )
            if func_id == "require_arg":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PN_IMPL_NO_REQUIRE_ARG]: 'require_arg(...)' is strictly prohibited in implementation pseudo-state machines. Domain constraints and generation domains belong exclusively to the interface state machine."
                )
            elif func_id == "require":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PN_IMPL_NO_REQUIRE]: 'require(...)' is strictly prohibited in implementation inner transitions. Preconditions belong exclusively to the interface state machine outer transition."
                )
            elif func_id == "call_target":
                if len(child.args) == 0 and len(child.keywords) == 0:
                    errors.append(
                        f"{file_path}:{child.lineno}: error [PN_IMPL_CALL_TARGET_ARG_REQUIRED]: 'call_target()' requires an argument wrapping the target invocation (e.g. 'call_target(target.method(...))') or expected return type. Zero-argument 'call_target()' is strictly prohibited."
                    )
            elif func_id == "sut":
                if len(child.args) == 0 and len(child.keywords) == 0:
                    errors.append(
                        f"{file_path}:{child.lineno}: error [PN_SUT_ARG_REQUIRED]: 'sut()' requires the target class as an argument (e.g. 'target = sut(TargetClass)'). Zero-argument 'sut()' is strictly prohibited."
                    )
            elif func_id == "ensure":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PRE_LINT_NO_LEGACY_ENSURE]: 'ensure(...)' is obsolete in Pretense 1 Next. Use native Python 'assert ...' instead."
                )
            elif func_id == "ensure_ret":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PRE_LINT_NO_LEGACY_ENSURE_RET]: 'ensure_ret(...)' is obsolete in Pretense 1 Next. In impl pseudo-SM, use 'ret = call_target(...)' or native return."
                )
            elif func_id == "ensure_raises":
                errors.append(
                    f"{file_path}:{child.lineno}: error [PRE_LINT_NO_LEGACY_ENSURE_RAISES]: 'ensure_raises(...)' is obsolete in Pretense 1 Next. Use 'Env[bool]' + 'require_env(healthy_cond, ExpectedException)'."
                )

    mutating_methods = {
        "add",
        "remove",
        "discard",
        "pop",
        "popitem",
        "clear",
        "update",
        "append",
        "extend",
        "insert",
        "put",
        "assign",
        "set",
        "delete",
        "__setitem__",
    }

    def _is_self_state_target(n: ast.AST) -> bool:
        if (
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "self"
            and n.attr == "state"
        ):
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
            if child.func.attr in mutating_methods and _is_self_state_target(
                child.func.value
            ):
                errors.append(
                    f"{file_path}:{child.lineno}: error [PN_IMPL_NO_STATE_MUTATION]: Transition '{fn_name}' in implementation pseudo-state machine must not mutate 'self.state' (calling '{child.func.attr}()' on self.state). Model state transitions are already executed by the inherited interface transition before delegating to 'call_target(...)'. Implementation transitions must only invoke 'call_target(...)' and assert postconditions."
                )

    return errors



def check_impl_pseudo_state_machines(
    tree: ast.AST,
    file_path: str = "",
    is_impl: bool = False,
) -> list[str]:
    """Validates that implementation pseudo-state machines only override inner transitions.

    Prohibits:
    1. Declaring @transition on any method in implementation pretense modules (PN_IMPL_NO_OUTER_TRANSITION).
    2. Overriding outer transitions directly (methods not starting with 'inner_') (PN_IMPL_NO_OUTER_TRANSITION).
    3. Mutating self.state or calling require/require_arg inside inner transitions.
    """
    errors: list[str] = []

    def _get_base_name(base: ast.AST) -> str:
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return base.attr
        elif isinstance(base, ast.Subscript):
            return _get_base_name(base.value)
        return ""

    body = getattr(tree, "body", [])
    for node in body:
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [_get_base_name(b) for b in node.bases]
        is_sm = any(
            b in ("StateMachine", "StateMachineProto") or b.endswith("StateMachine")
            for b in base_names
        )
        is_impl_sm = any(
            b.endswith("StateMachine")
            and b not in ("StateMachine", "StateMachineProto")
            for b in base_names
        )
        is_impl_pseudo = (
            node.name.endswith("ImplPseudoStateMachine")
            or is_impl_sm
            or (is_impl and is_sm and not any("TestCase" in b for b in base_names))
        )

        if is_impl_pseudo:
            cls_name = node.name
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                fn_name = item.name

                has_trans = any(
                    (
                        isinstance(d, ast.Call)
                        and (
                            (isinstance(d.func, ast.Name) and d.func.id == "transition")
                            or (
                                isinstance(d.func, ast.Attribute)
                                and d.func.attr in ("transition", "seeding")
                            )
                        )
                    )
                    or (isinstance(d, ast.Name) and d.id == "transition")
                    or (
                        isinstance(d, ast.Attribute)
                        and d.attr in ("transition", "seeding")
                    )
                    for d in item.decorator_list
                )

                has_property = any(
                    isinstance(d, ast.Name) and d.id == "property"
                    for d in item.decorator_list
                )
                if fn_name.startswith("inner_") or fn_name.startswith("_inner_"):
                    if has_trans:
                        errors.append(
                            f"{file_path}:{item.lineno}: error [PN_IMPL_NO_OUTER_TRANSITION]: Inner transition '{fn_name}' in implementation pseudo-state machine '{cls_name}' must NOT be decorated with '@transition'. Inner transitions are plain Python methods called by inherited interface transitions."
                        )
                    errors.extend(
                        _check_inner_transition_body(item, file_path, cls_name)
                    )
                elif (
                    fn_name
                    in (
                        "__init__",
                        "__repr__",
                        "__str__",
                        "make_initial_state",
                        "make_sut",
                    )
                    or fn_name.startswith("_")
                    or (has_property and not has_trans)
                ):
                    if has_trans:
                        errors.append(
                            f"{file_path}:{item.lineno}: error [PN_IMPL_NO_OUTER_TRANSITION]: Method '{fn_name}' in implementation pseudo-state machine '{cls_name}' must NOT be decorated with '@transition'."
                        )
                else:
                    errors.append(
                        f"{file_path}:{item.lineno}: error [PN_IMPL_NO_OUTER_TRANSITION]: Method '{fn_name}' in implementation pseudo-state machine '{cls_name}' overrides outer transition. Implementation pseudo-state machines must NOT declare '@transition' or override outer transitions; they must only override inner transitions ('inner_{fn_name}') so that interface preconditions, domains, and model state mutations remain active."
                    )

    return errors



def check_lifted_expr_usage(
    tree: ast.AST, file_path: str = "", is_impl: bool = False
) -> list[str]:
    """Validates that lifted Expr.value() calls and self.state mutations are properly gated."""
    errors: list[str] = []
    errors.extend(check_impl_pseudo_state_machines(tree, file_path, is_impl=is_impl))
    mutating_methods = {
        "add",
        "remove",
        "discard",
        "pop",
        "popitem",
        "clear",
        "update",
        "append",
        "extend",
        "insert",
        "put",
        "assign",
        "set",
        "delete",
        "__setitem__",
    }

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        is_transition = False
        for d in node.decorator_list:
            if isinstance(d, ast.Call):
                func = d.func
                if (isinstance(func, ast.Name) and func.id == "transition") or (
                    isinstance(func, ast.Attribute)
                    and func.attr in ("transition", "seeding")
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
            errors.extend(
                check_pretense_next_transition(node, file_path, is_impl=is_impl)
            )
            continue

        expr_param_names = set(raw_params[:-1]) if len(raw_params) >= 2 else set()
        call_funcs = {c.func for c in ast.walk(node) if isinstance(c, ast.Call)}

        def _walk_stmt_or_expr(
            curr: ast.AST, in_gated_block: bool, in_updates_block: bool
        ) -> None:
            if (
                isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef))
                and curr is not node
            ):
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
                    _walk_stmt_or_expr(
                        stmt, in_gated_block or is_gated, in_updates_block or is_updates
                    )
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
                targets = (
                    curr.targets if isinstance(curr, ast.Assign) else [curr.target]
                )
                if any(_targets_self_state(t) for t in targets):
                    errors.append(
                        f"{file_path}:{curr.lineno}: error: Transition '{fn_name}' mutates 'self.state' outside "
                        f"'if ctx.updates:'. State mutations must be gated under 'if ctx.updates:'."
                    )

            for child in ast.iter_child_nodes(curr):
                _walk_stmt_or_expr(child, in_gated_block, in_updates_block)

        for stmt in node.body:
            _walk_stmt_or_expr(stmt, False, False)

    return list(dict.fromkeys(errors))


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
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "returns"
                ):
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
                elif (
                    isinstance(child, ast.Return)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == "NotBound"
                ):
                    errors.append(
                        f"{file_path}:{child.lineno}: error: Transition '{node.name}' returns sentinel 'NotBound'. "
                        f"Transitions must return concrete values, state expressions, or Raised(...) exceptions."
                    )

        if node.name.startswith("test_"):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(
                    child.func, ast.Attribute
                ):
                    if (
                        child.func.attr in ("assertEqual", "assertNotEqual")
                        and len(child.args) >= 2
                    ):
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
                if isinstance(cond, ast.Attribute) and cond.attr in (
                    "initialized",
                    "is_initialized",
                ):
                    if (
                        isinstance(cond.value, ast.Attribute)
                        and cond.value.attr == "state"
                    ):
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


def check_multi_transition_disambiguation(
    tree: ast.AST, file_path: str = ""
) -> list[str]:
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



def check_no_algorithmic_state_machines(
    tree: ast.AST, file_path: str = ""
) -> list[str]:
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
                if (
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child is not item
                ):
                    lower_name = child.name.lower()
                    if any(
                        algo_word in lower_name
                        for algo_word in ("backtrack", "solve", "search", "recurse")
                    ):
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

    target_attr_names = {c.lower() for c in target_classes} | {
        "sut",
        "target",
        "engine",
        "service",
    }

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
            if attr.startswith("_") and not (
                attr.startswith("__") and attr.endswith("__")
            ):
                val = node.value
                # Check self.<target>._private
                if (
                    isinstance(val, ast.Attribute)
                    and isinstance(val.value, ast.Name)
                    and val.value.id == "self"
                ):
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
                elif (
                    isinstance(first_arg, ast.Attribute)
                    and isinstance(first_arg.value, ast.Name)
                    and first_arg.value.id == "self"
                ):
                    if first_arg.attr.lower() in target_attr_names or any(
                        tc.lower() in first_arg.attr.lower() for tc in target_classes
                    ):
                        is_target = True
                        target_desc = f"target instance 'self.{first_arg.attr}'"
                elif (
                    isinstance(first_arg, ast.Name)
                    and first_arg.id in local_target_vars
                ):
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
                if (
                    node.args
                    and isinstance(node.args[0], ast.Constant)
                    and "must be implemented" in str(node.args[0].value)
                ):
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
        elif isinstance(node, ast.ClassDef):
            if node.name in ("TargetState", "TargetStateMachine"):
                errors.append(
                    f"{file_path}:{node.lineno}: error: class '{node.name}' is an unconfigured template placeholder. "
                    f"You must define concrete state machine classes matching the specification."
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                non_doc_stmts = [
                    s
                    for s in node.body
                    if not (
                        isinstance(s, ast.Expr)
                        and isinstance(s.value, ast.Constant)
                        and isinstance(s.value.value, str)
                    )
                ]
                if len(non_doc_stmts) == 1 and isinstance(non_doc_stmts[0], ast.Pass):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: test method '{node.name}' contains only 'pass'. "
                        f"Empty tests are strictly prohibited; tests must exercise transitions or assert concrete contracts."
                    )
    return errors



def check_no_pre_seeding(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures make_sut() starts components and collaborator fakes in blank initial states without pre-seeding,
    and forbids direct manipulation of internal model state in test methods."""
    errors: list[str] = []
    allowed_call_names = {
        "LifecycleRegistry",
        "enter_phase",
        "get_singleton",
        "register_instance",
        "register_singleton",
        "cast",
        "dict",
        "list",
        "set",
        "tuple",
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "make_sut"
        ):
            for child in ast.walk(node):
                if isinstance(child, (ast.For, ast.While)):
                    errors.append(
                        f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_PRE_SEEDING] loops are prohibited in 'make_sut()'; "
                        f"components and collaborator fakes must start in blank initial states. Use seeding transitions during fuzzing instead."
                    )
                elif isinstance(child, ast.Call):
                    func_name = ""
                    if isinstance(child.func, ast.Name):
                        func_name = child.func.id
                    elif isinstance(child.func, ast.Attribute):
                        func_name = child.func.attr

                    if (
                        func_name.startswith("__") and func_name.endswith("__")
                    ) or func_name == "__enter__":
                        continue
                    if func_name.startswith("make_") and "fake" in func_name:
                        if child.args or child.keywords:
                            errors.append(
                                f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_PRE_SEEDING] passing state arguments to '{func_name}' is prohibited in 'make_sut()'; "
                                f"components and collaborator fakes must start in blank default initial states. Found: '{ast.unparse(child)}'."
                            )
                        continue
                    if func_name.isupper():
                        continue
                    if func_name in allowed_call_names:
                        continue
                    if func_name in (
                        "submit",
                        "push",
                        "deposit",
                        "withdraw",
                        "put",
                        "add",
                        "dispatch",
                        "fetch_and_execute",
                        "clear",
                        "reset",
                    ) or func_name.startswith("set_"):
                        errors.append(
                            f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_PRE_SEEDING] pre-seeding call '{func_name}' is prohibited in 'make_sut()'; "
                            f"components and collaborator fakes must start in blank initial states. Use seeding transitions during fuzzing instead."
                        )

        # Check for direct state poking in TestCase classes
        elif isinstance(node, ast.ClassDef):
            if "StateMachine" in node.name or node.name.endswith("State"):
                continue
            is_test_case = any(
                (isinstance(b, ast.Name) and b.id in ("TestCase", "unittest.TestCase", "LifecycleTestCase"))
                or (isinstance(b, ast.Attribute) and b.attr in ("TestCase", "LifecycleTestCase"))
                for b in node.bases
            ) or (
                (
                    node.name.startswith("Test")
                    or node.name.endswith("Real")
                    or node.name.endswith("Fake")
                )
                and any(
                    isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and m.name.startswith("test")
                    for m in node.body
                )
            )
            if is_test_case:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for stmt in ast.walk(item):
                            if isinstance(stmt, ast.Assign):
                                for target in stmt.targets:
                                    target_str = ast.unparse(target)
                                    if ".state." in target_str or target_str.endswith(
                                        ".state"
                                    ):
                                        errors.append(
                                            f"{file_path}:{stmt.lineno}: error: [PRE_LINT_NO_STATE_POKING] direct mutation of internal model state '{target_str}' is prohibited in test methods. Manipulate state exclusively via public operations or declared '@transition.seeding' methods."
                                        )
                            elif isinstance(stmt, ast.AugAssign):
                                target_str = ast.unparse(stmt.target)
                                if ".state." in target_str or target_str.endswith(
                                    ".state"
                                ):
                                    errors.append(
                                        f"{file_path}:{stmt.lineno}: error: [PRE_LINT_NO_STATE_POKING] direct mutation of internal model state '{target_str}' is prohibited in test methods. Manipulate state exclusively via public operations or declared '@transition.seeding' methods."
                                    )
                            elif isinstance(stmt, ast.Call) and isinstance(
                                stmt.func, ast.Attribute
                            ):
                                if stmt.func.attr in (
                                    "append",
                                    "add",
                                    "extend",
                                    "insert",
                                    "remove",
                                    "pop",
                                    "clear",
                                    "update",
                                    "discard",
                                ):
                                    val_str = ast.unparse(stmt.func.value)
                                    if ".state." in val_str or val_str.endswith(
                                        ".state"
                                    ):
                                        errors.append(
                                            f"{file_path}:{stmt.lineno}: error: [PRE_LINT_NO_STATE_POKING] mutating internal model state via '{ast.unparse(stmt.func)}' is prohibited in test methods. Manipulate state exclusively via public operations or declared '@transition.seeding' methods."
                                        )
    return errors



def check_no_raises_in_test_cases(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures test methods in TestCase classes do not use 'with raises(...)', requiring 'self.assertRaises(...)'.

    'raises(...)' is Pretense DSL designed for transition pivot execution. Inside unittest.TestCase
    methods, 'raises' context manager does not suppress exceptions in standard test execution.
    Test methods must use standard unittest 'self.assertRaises(...)'.
    """
    errors: list[str] = []
    tree_body: list[ast.stmt] = getattr(tree, "body", [])
    for node in tree_body:
        if not isinstance(node, ast.ClassDef):
            continue
        if "StateMachine" in node.name or node.name.endswith("State"):
            continue
        is_test_case = any(
            (isinstance(b, ast.Name) and b.id in ("TestCase", "unittest.TestCase", "LifecycleTestCase"))
            or (isinstance(b, ast.Attribute) and b.attr in ("TestCase", "LifecycleTestCase"))
            for b in node.bases
        ) or (
            (
                node.name.startswith("Test")
                or node.name.endswith("Real")
                or node.name.endswith("Fake")
            )
            and any(
                isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and m.name.startswith("test")
                for m in node.body
            )
        )
        if not is_test_case:
            continue

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(item):
                if isinstance(child, ast.With):
                    for with_item in child.items:
                        ctx_expr = with_item.context_expr
                        func_name = ""
                        if isinstance(ctx_expr, ast.Call):
                            if isinstance(ctx_expr.func, ast.Name):
                                func_name = ctx_expr.func.id
                            elif isinstance(ctx_expr.func, ast.Attribute):
                                func_name = ctx_expr.func.attr
                        elif isinstance(ctx_expr, ast.Name):
                            func_name = ctx_expr.id
                        elif isinstance(ctx_expr, ast.Attribute):
                            func_name = ctx_expr.attr
                        if func_name == "raises":
                            errors.append(
                                f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_RAISES_IN_TEST_CASE] "
                                f"'with raises(...)' is strictly prohibited in pretense files. "
                                "Verify contract violations (*Error) via 'self.checked.violating(ExpectedError).<method>(...)', "
                                "and operational exceptions (*Exception) via 'with self.assertRaises(ExpectedException):'."
                            )
                elif isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
                    call = child.value
                    func_name = ""
                    if isinstance(call.func, ast.Name):
                        func_name = call.func.id
                    elif isinstance(call.func, ast.Attribute):
                        func_name = call.func.attr
                    if func_name == "raises":
                        errors.append(
                            f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_RAISES_IN_TEST_CASE] "
                            f"'raises(...)' is strictly prohibited in pretense files. "
                            "Verify contract violations (*Error) via 'self.checked.violating(ExpectedError).<method>(...)', "
                            "and operational exceptions (*Exception) via 'with self.assertRaises(ExpectedException):'."
                        )
    return errors



def check_no_assert_raises(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures test methods do not use 'assertRaises' for contract errors (*Error) or wrap 'violating(...)'.

    Contract violations (*Error) must be verified on the SUT via 'self.checked.violating(ExpectedError).<method>(...)'.
    Operational exceptions (*Exception) triggered via 'require_env(...)' may use 'with self.assertRaises(ExpectedException):'.
    """
    errors: list[str] = []

    def _extract_exc_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name in ("assertRaises", "assertRaisesRegex"):
                exc_name = _extract_exc_name(node.args[0]) if node.args else ""
                if exc_name.endswith("Exception") and exc_name not in ("Exception", "BaseException"):
                    continue
                errors.append(
                    f"{file_path}:{node.lineno}: error [PN_NO_ASSERT_RAISES]: "
                    f"Calling '{func_name}' for contract errors or non-*Exception types is prohibited in Pretense test modules. "
                    "Contract violations (*Error) must be verified via 'self.checked.violating(ExpectedError).<method>(...)'. "
                    "Operational exceptions (*Exception) may use 'with self.assertRaises(ExpectedException):'."
                )
    return errors



def check_no_raises_for_errors(tree: ast.AST, file_path: str = "") -> list[str]:
    """Prohibits 'raises(...)' / 'with raises(...)' in pretense files.

    Contract violations (*Error) must be gated via 'require(..., error=ExpectedError)' or
    'require_arg(param, Domain..., error=ExpectedError)' and tested via 'self.checked.violating(ExpectedError).method(...)'.
    Operational exceptions (*Exception) must be modeled via 'Env[T]' + 'require_env(healthy_cond, ExpectedException)',
    bound via 'self.bind(...)' in impl, and tested via 'with self.assertRaises(ExpectedException):'.
    """
    errors: list[str] = []

    def _extract_error_names(node: ast.AST) -> list[str]:
        names: list[str] = []
        if isinstance(node, ast.Name):
            if node.id.endswith("Error") or node.id in (
                "KeyError",
                "IndexError",
                "ValueError",
                "TypeError",
                "AssertionError",
            ):
                names.append(node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr.endswith("Error") or node.attr in (
                "KeyError",
                "IndexError",
                "ValueError",
                "TypeError",
                "AssertionError",
            ):
                names.append(node.attr)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                names.extend(_extract_error_names(elt))
        return names

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name == "raises":
                err_names: list[str] = []
                if node.args:
                    err_names.extend(_extract_error_names(node.args[0]))
                for kw in node.keywords:
                    if kw.arg in ("exc", "expected_exception", "error", "exc_type"):
                        err_names.extend(_extract_error_names(kw.value))
                if err_names:
                    for err_name in err_names:
                        errors.append(
                            f"{file_path}:{node.lineno}: error: [PRE_LINT_NO_RAISES_ERROR] 'raises({err_name})' is invalid for contract violation errors (*Error). "
                            f"'raises(...)' is prohibited in pretense files. Contract errors designate invalid inputs or state preconditions; "
                            f"gate them using 'require(..., error={err_name})' (or positional 'require(..., {err_name})') for state preconditions, or "
                            f"'require_arg(<param>, Domain.in_set(self.state.<collection>), error={err_name})' (or positional 'require_arg(<param>, Domain.in_set(self.state.<collection>), {err_name})') for argument domains (error is optional documentation of the contracted violation). "
                            f"To verify {err_name} in test cases, use 'self.checked.violating({err_name}).method(...)'. "
                            f"DO NOT rename or redefine {err_name} to an *Exception; exception types are strictly dictated by the Low-Level Specification (low/*.pyi)."
                        )
                else:
                    errors.append(
                        f"{file_path}:{node.lineno}: error: [PRE_LINT_NO_RAISES] 'raises(...)' is prohibited in pretense files. "
                        "Operational exceptions (*Exception) must use 'Env[bool]' + 'require_env(healthy_cond, ExpectedException)' "
                        "in interface state machines, 'self.bind(...)' in impl __init__, and 'with self.assertRaises(ExpectedException):' in Test*ImplReal."
                    )
    return errors



def check_require_sticks_to_error(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures 'require(...)' and 'require_arg(...)' only specify contract violation errors (*Error), never operational exceptions (*Exception)."""
    errors: list[str] = []

    def _extract_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return _extract_name(node.func)
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in ("require", "requires"):
                # Positional error argument: require(cond, ErrorCls) or require(cond, "msg", ErrorCls)
                for arg in node.args[1:]:
                    name = _extract_name(arg)
                    if name and (name.endswith("Exception") or name in ("Exception", "BaseException")):
                        errors.append(
                            f"{file_path}:{node.lineno}: error: [PRE_LINT_REQUIRE_MUST_BE_ERROR] 'require(...)' must only be used with contract violation errors (*Error). "
                            f"Found operational exception '{name}'. Use 'require_env(...)' for operational exceptions (*Exception). Contract errors designate caller-preventable "
                            f"precondition violations, whereas operational exceptions represent external environmental or collaborator states."
                        )
                # Keyword error argument: require(..., error=...) or require(..., exc_class=...)
                for kw in node.keywords:
                    if kw.arg in ("error", "exc_class"):
                        name = _extract_name(kw.value)
                        if name and (name.endswith("Exception") or name in ("Exception", "BaseException")):
                            errors.append(
                                f"{file_path}:{node.lineno}: error: [PRE_LINT_REQUIRE_MUST_BE_ERROR] 'require(..., {kw.arg}={name})' must only be used with contract violation errors (*Error). "
                                f"Found operational exception '{name}'. Use 'require_env(...)' for operational exceptions (*Exception). Contract errors designate caller-preventable "
                                f"precondition violations, whereas operational exceptions represent external environmental or collaborator states."
                            )
            elif func_name == "require_arg":
                # Positional extra arguments (after val, domain):
                for arg in node.args[2:]:
                    name = _extract_name(arg)
                    if name and (name.endswith("Exception") or name in ("Exception", "BaseException")):
                        errors.append(
                            f"{file_path}:{node.lineno}: error: [PRE_LINT_REQUIRE_MUST_BE_ERROR] 'require_arg(...)' must only be used with contract violation errors (*Error). "
                            f"Found operational exception '{name}'. Use 'require_env(...)' for operational exceptions (*Exception)."
                        )
                for kw in node.keywords:
                    if kw.arg == "error":
                        name = _extract_name(kw.value)
                        if name and (name.endswith("Exception") or name in ("Exception", "BaseException")):
                            errors.append(
                                f"{file_path}:{node.lineno}: error: [PRE_LINT_REQUIRE_MUST_BE_ERROR] 'require_arg(..., error={name})' must only be used with contract violation errors (*Error). "
                                f"Found operational exception '{name}'. Use 'require_env(...)' for operational exceptions (*Exception)."
                            )
    return errors



def check_require_env_sticks_to_exception(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures 'require_env(...)' only specifies operational exceptions (*Exception), never contract violation errors (*Error)."""
    errors: list[str] = []

    def _extract_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return _extract_name(node.func)
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "require_env":
                target_node = None
                if len(node.args) >= 2:
                    target_node = node.args[1]
                else:
                    for kw in node.keywords:
                        if kw.arg in ("exception_cls", "error", "exc", "exc_type"):
                            target_node = kw.value
                            break
                if target_node is not None:
                    name = _extract_name(target_node)
                    if name:
                        if name.endswith("Error") or name in (
                            "KeyError",
                            "IndexError",
                            "ValueError",
                            "TypeError",
                            "AssertionError",
                        ):
                            errors.append(
                                f"{file_path}:{node.lineno}: error: [PRE_LINT_REQUIRE_ENV_MUST_BE_EXCEPTION] 'require_env(...)' is reserved exclusively for operational exceptions (*Exception). "
                                f"Found contract violation error '{name}'. Contract errors designate caller-preventable precondition violations; "
                                f"gate them using 'require(..., error={name})' or 'require_arg(..., error={name})'."
                            )
                        elif not name.endswith("Exception"):
                            errors.append(
                                f"{file_path}:{node.lineno}: error: [PRE_LINT_REQUIRE_ENV_MUST_BE_EXCEPTION] 'require_env(...)' operational exception '{name}' must end with 'Exception' "
                                f"to clearly differentiate operational exceptions from contract violation errors (*Error)."
                            )
    return errors



def _is_env_annotation(ann: ast.AST) -> bool:
    """Returns True if an annotation AST node is Env[...] or Annotated[..., _EnvStateMarker]."""
    if isinstance(ann, ast.Subscript):
        val = ann.value
        if (isinstance(val, ast.Name) and val.id == "Env") or (
            isinstance(val, ast.Attribute) and val.attr == "Env"
        ):
            return True
        if (isinstance(val, ast.Name) and val.id == "Annotated") or (
            isinstance(val, ast.Attribute) and val.attr == "Annotated"
        ):
            for child in ast.walk(ann.slice):
                if (isinstance(child, ast.Name) and child.id == "_EnvStateMarker") or (
                    isinstance(child, ast.Attribute) and child.attr == "_EnvStateMarker"
                ):
                    return True
    return False


def _extract_env_state_fields(tree: ast.AST) -> set[str]:
    """Collects field names annotated with Env[...] on State dataclasses in a module AST."""
    env_fields: set[str] = set()
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.ClassDef):
            continue
        is_dataclass = any(
            (isinstance(d, ast.Name) and d.id == "dataclass")
            or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
            or (
                isinstance(d, ast.Call)
                and (
                    (isinstance(d.func, ast.Name) and d.func.id == "dataclass")
                    or (isinstance(d.func, ast.Attribute) and d.func.attr == "dataclass")
                )
            )
            for d in node.decorator_list
        )
        if not (is_dataclass or node.name.endswith("State")):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                if _is_env_annotation(stmt.annotation):
                    env_fields.add(stmt.target.id)
    return env_fields


def check_require_env_depends_on_env_state(
    tree: ast.AST, file_path: str = ""
) -> list[str]:
    """Ensures 'require_env(...)' conditions reference at least one declared Env[...] field."""
    errors: list[str] = []
    env_fields = _extract_env_state_fields(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        if func_name != "require_env":
            continue

        cond_node: ast.AST | None = None
        if node.args:
            cond_node = node.args[0]
        else:
            for kw in node.keywords:
                if kw.arg in ("condition", "cond"):
                    cond_node = kw.value
                    break
        if cond_node is None:
            continue

        refs_env = bool(env_fields) and any(
            isinstance(child, ast.Attribute) and child.attr in env_fields
            for child in ast.walk(cond_node)
        )
        if not refs_env:
            errors.append(
                f"{file_path}:{node.lineno}: error: [PRE_LINT_REQUIRE_ENV_NEEDS_ENV_STATE] "
                "'require_env(...)' condition must reference at least one declared 'Env[...]' "
                "state field on the State dataclass (e.g., 'self.state.<env_field>')."
            )
    return errors



def check_violating_sticks_to_error(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures '.violating(...)' only specifies contract violation errors (*Error), never *Exception."""
    errors: list[str] = []

    def _extract_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return _extract_name(node.func)
        return ""

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        is_violating = (
            isinstance(node.func, ast.Attribute) and node.func.attr == "violating"
        ) or (isinstance(node.func, ast.Name) and node.func.id == "violating")
        if not is_violating:
            continue

        target_node: ast.AST | None = None
        if node.args:
            target_node = node.args[0]
        else:
            for kw in node.keywords:
                if kw.arg in ("exc_type", "error", "exc"):
                    target_node = kw.value
                    break
        if target_node is None:
            continue

        name = _extract_name(target_node)
        if name and (name.endswith("Exception") or name in ("Exception", "BaseException")):
            errors.append(
                f"{file_path}:{node.lineno}: error: [PRE_LINT_VIOLATING_MUST_BE_ERROR] "
                f"'.violating({name})' is restricted exclusively to contract violation errors (*Error). "
                "Operational exceptions (*Exception) must be exercised by driving bound "
                "environmental/collaborator state via 'self.bind(...)' and 'require_env(...)'."
            )
    return errors



def check_impl_env_state_bindings(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures implementation pseudo-SMs bind every Env[...] field inherited from implemented interfaces."""
    errors: list[str] = []
    if not file_path or not file_path.endswith("_impl_pretense.py"):
        return errors


    pseudo_sm_cls: ast.ClassDef | None = None
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and (
            "PseudoStateMachine" in node.name
            or ("StateMachine" in node.name and node.name != "StateMachine")
        ):
            pseudo_sm_cls = node
            break
    if pseudo_sm_cls is None:
        return errors


    base_names: set[str] = set()
    for b in pseudo_sm_cls.bases:
        if isinstance(b, ast.Name):
            base_names.add(b.id)
        elif isinstance(b, ast.Attribute):
            base_names.add(b.attr)
        elif isinstance(b, ast.Subscript):
            val = b.value
            if isinstance(val, ast.Name):
                base_names.add(val.id)
            elif isinstance(val, ast.Attribute):
                base_names.add(val.attr)

    curr_path = Path(file_path).resolve()
    pretense_dir = curr_path.parent
    iface_paths: list[Path] = []

    # 1. Discover implemented interfaces from high/<unit>.md 'implements:' header
    if "parts" in curr_path.parts:
        try:
            parts_idx = curr_path.parts.index("parts")
            unit_name = curr_path.name.replace("_pretense.py", "")
            unit_dir = Path(*curr_path.parts[: parts_idx + 2])
            high_cand = unit_dir / "high" / f"{unit_name}.md"
            if high_cand.is_file():
                for line in high_cand.read_text(encoding="utf-8").splitlines()[:20]:
                    line_s = line.strip()
                    if line_s.startswith("implements:"):
                        raw = line_s[len("implements:") :].strip()
                        for target in (t.strip() for t in raw.split(",") if t.strip()):
                            cand = unit_dir / "pretense" / f"{target}_pretense.py"
                            if cand.is_file() and cand not in iface_paths:
                                iface_paths.append(cand)
                        break
        except Exception:
            pass

    # 2. Fallback when high/<unit>.md is absent: only inspect imported *_pretense modules
    # whose StateMachine class is actually inherited by pseudo_sm_cls (skip collaborators).
    if not iface_paths:
        for stmt in getattr(tree, "body", []):
            mod_names: list[str] = []
            if isinstance(stmt, ast.Import):
                mod_names = [alias.name.split(".")[-1] for alias in stmt.names]
            elif isinstance(stmt, ast.ImportFrom) and stmt.module:
                mod_names = [stmt.module.split(".")[-1]]
            for mod_name in mod_names:
                if mod_name.endswith("_pretense") and not mod_name.endswith("_impl_pretense"):
                    cand = pretense_dir / f"{mod_name}.py"
                    if cand.is_file() and cand not in iface_paths:
                        try:
                            cand_tree = ast.parse(cand.read_text(encoding="utf-8"))
                            cand_classes = {
                                n.name
                                for n in getattr(cand_tree, "body", [])
                                if isinstance(n, ast.ClassDef)
                            }
                            if cand_classes & base_names:
                                iface_paths.append(cand)
                        except (OSError, SyntaxError):
                            pass

    required_env_fields: set[str] = set()
    for iface_path in iface_paths:
        try:
            iface_tree = ast.parse(iface_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        required_env_fields.update(_extract_env_state_fields(iface_tree))

    if not required_env_fields:
        return errors


    bound_fields: set[str] = set()
    for item in pseudo_sm_cls.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            for child in ast.walk(item):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "bind"
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == "self"
                ):
                    attr_arg: ast.AST | None = child.args[0] if child.args else None
                    if attr_arg is None:
                        for kw in child.keywords:
                            if kw.arg == "attr_name":
                                attr_arg = kw.value
                                break
                    if isinstance(attr_arg, ast.Constant) and isinstance(
                        attr_arg.value, str
                    ):
                        bound_fields.add(attr_arg.value)

    for field_name in sorted(required_env_fields):
        if field_name not in bound_fields:
            errors.append(
                f"{file_path}:{pseudo_sm_cls.lineno}: error: [PRE_LINT_UNBOUND_ENV_STATE] "
                f"Implementation pseudo-state machine '{pseudo_sm_cls.name}' inherits environmental "
                f"state field '{field_name}' from an implemented interface, but does not bind it "
                f"via 'self.bind(\"{field_name}\", lambda: ...)' in '__init__'."
            )
    return errors



def check_no_local_exception_class(tree: ast.AST, file_path: str = "") -> list[str]:
    """Prohibits redefining exception/error classes locally inside pretense modules."""
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            base_names = {
                b.id if isinstance(b, ast.Name) else b.attr
                for b in node.bases
                if isinstance(b, (ast.Name, ast.Attribute))
            }
            if base_names & {"Exception", "BaseException"} or node.name.endswith(
                ("Error", "Exception")
            ):
                errors.append(
                    f"{file_path}:{node.lineno}: error [PRE_LINT_NO_LOCAL_EXCEPTION_CLASS]: "
                    f"Do not define exception class '{node.name}' locally in a pretense module; "
                    f"import contracted errors/exceptions from the target library interface module."
                )
    return errors


def check_no_module_level_sut(tree: ast.AST, file_path: str = "") -> list[str]:
    """Prohibits calling sut(...) at module or class-body level outside methods/functions."""
    errors: list[str] = []

    def _visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sut"
        ):
            errors.append(
                f"{file_path}:{node.lineno}: error [PRE_LINT_NO_MODULE_LEVEL_SUT]: "
                "'sut(...)' must only be called inside methods (e.g. 'target: TargetClass = sut(TargetClass)' "
                "inside 'inner_<name>'), never at module or class-body level where it raises KeyError at import time."
            )
            return
        for child in ast.iter_child_nodes(node):
            _visit(child)

    _visit(tree)
    return errors


def check_no_violating_in_interface(
    tree: ast.AST, file_path: str = "", is_interface: bool = True
) -> list[str]:
    """Prohibits .violating(...) in interface pretense modules (belongs in *_impl_pretense.py)."""
    if not is_interface:
        return []
    errors: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "violating"
        ):
            errors.append(
                f"{file_path}:{node.lineno}: error [PRE_LINT_NO_VIOLATING_IN_INTERFACE]: "
                "'.violating(...)' tests concrete SUT error-raising paths and belongs only in "
                "implementation pretense modules (*_impl_pretense.py), never in interface fake tests "
                "(Test<Target>Fake). On a fake, '.violating(...)' disables 'require(...)' preconditions "
                "and calls 'inner_*' directly."
            )
    return errors


def check_no_raise_in_state_machine(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures explicit 'raise' statements are never used within StateMachine definitions (PRE_LINT_NO_RAISE)."""
    errors: list[str] = []

    def _is_state_machine_class(c: ast.ClassDef) -> bool:
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
            if base_id in ("StateMachine", "StateMachineProto") or base_id.endswith(
                ("StateMachine", "PseudoStateMachine")
            ):
                return True
        return False

    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and _is_state_machine_class(node):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Raise):
                    errors.append(
                        f"{file_path}:{inner.lineno}: error: [PRE_LINT_NO_RAISE] Explicit 'raise' statements are strictly prohibited in state machines. "
                        f"Contract errors must be gated via 'require(...)' / 'require_arg(...)', and operational exceptions must be declared via 'require_env(...)'. "
                        f"Fake return synthesis and SUT invocation must not raise ad-hoc exceptions."
                    )
    return errors



def check_no_direct_real_access(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures test methods in TestCase classes do not access 'self.real' directly (PN_NO_DIRECT_REAL_ACCESS).

    'self.real' is only permitted during test fixture setup in setUp()/tearDown() to wire
    'self.checked = self.sm.as_checked(TargetClass, self.real)'.
    All test methods (def test_*) must interact with the SUT exclusively through 'self.checked'
    or 'self.checked.violating(...)'. Direct access to 'self.real' in test methods is strictly prohibited.
    """
    errors: list[str] = []
    tree_body: list[ast.stmt] = getattr(tree, "body", [])
    for node in tree_body:
        if not isinstance(node, ast.ClassDef):
            continue
        if "StateMachine" in node.name or node.name.endswith("State"):
            continue
        is_test_case = any(
            (isinstance(b, ast.Name) and b.id in ("TestCase", "unittest.TestCase", "LifecycleTestCase"))
            or (isinstance(b, ast.Attribute) and b.attr in ("TestCase", "LifecycleTestCase"))
            for b in node.bases
        ) or (
            (
                node.name.startswith("Test")
                or node.name.endswith("Real")
                or node.name.endswith("Fake")
            )
            and any(
                isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and m.name.startswith("test")
                for m in node.body
            )
        )
        if not is_test_case:
            continue

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith("test"):
                continue

            for child in ast.walk(item):
                if isinstance(child, ast.Attribute) and child.attr == "real":
                    if isinstance(child.value, ast.Name) and child.value.id == "self":
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN_NO_DIRECT_REAL_ACCESS]: "
                            f"Direct access to 'self.real' in test method '{item.name}' is strictly prohibited. "
                            "Tests must drive and verify the component exclusively through 'self.checked' "
                            "(or 'self.checked.violating(...)')."
                        )
    return errors



def check_no_direct_sm_access_in_real_tests(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures test methods in Test*Real classes do not access 'self.sm' directly (PN_NO_DIRECT_SM_ACCESS_IN_REAL_TEST).

    'self.sm' is only permitted during test fixture setup in setUp()/tearDown() to wire
    'self.checked = self.sm.as_checked(TargetClass, self.real)'.
    All real implementation test methods (def test_*) must interact with the SUT exclusively
    through 'self.checked' or 'self.checked.violating(...)'. Direct access to 'self.sm' in
    Test*Real test methods is strictly prohibited.
    """
    errors: list[str] = []
    tree_body: list[ast.stmt] = getattr(tree, "body", [])
    for node in tree_body:
        if not isinstance(node, ast.ClassDef):
            continue
        if "StateMachine" in node.name or node.name.endswith("State"):
            continue
        is_real_test_case = (
            (
                node.name.startswith("Test")
                or any(
                    (isinstance(b, ast.Name) and b.id in ("TestCase", "unittest.TestCase", "LifecycleTestCase"))
                    or (isinstance(b, ast.Attribute) and b.attr in ("TestCase", "LifecycleTestCase"))
                    for b in node.bases
                )
            )
            and "Real" in node.name
        )
        if not is_real_test_case:
            continue

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith("test"):
                continue

            for child in ast.walk(item):
                if isinstance(child, ast.Attribute) and child.attr == "sm":
                    if isinstance(child.value, ast.Name) and child.value.id == "self":
                        errors.append(
                            f"{file_path}:{child.lineno}: error [PN_NO_DIRECT_SM_ACCESS_IN_REAL_TEST]: "
                            f"Direct access to 'self.sm' in test method '{item.name}' of '{node.name}' is strictly prohibited. "
                            "Real implementation tests must drive operations and assertions exclusively through 'self.checked' "
                            "(or 'self.checked.violating(...)')."
                        )
    return errors



def check_impl_allowed_classes_only(
    tree: ast.AST, file_path: str = "", is_impl: bool = False
) -> list[str]:
    """Ensures implementation pretense modules only define implementation pseudo-state machines and TestCase classes (PN_IMPL_ALLOWED_CLASSES_ONLY).

    Defining auxiliary helper classes, custom protocols, mock wrappers, adapter proxies,
    or custom context managers (such as '_CheckedTarget', '_CheckedContext', '_CheckedAdapter')
    is strictly prohibited.
    """
    errors: list[str] = []
    if not is_impl:
        return errors


    def _get_base_name(base: ast.AST) -> str:
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return base.attr
        elif isinstance(base, ast.Subscript):
            return _get_base_name(base.value)
        return ""

    body = getattr(tree, "body", [])
    for node in body:
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [_get_base_name(b) for b in node.bases]
        is_test_case = any(
            b in ("TestCase", "unittest.TestCase") or b.endswith("TestCase")
            for b in base_names
        ) or node.name.startswith("Test")

        is_sm = any(
            b in ("StateMachine", "StateMachineProto") or b.endswith("StateMachine")
            for b in base_names
        ) or node.name.endswith("StateMachine") or node.name.endswith("ImplPseudoStateMachine")

        if not (is_test_case or is_sm):
            errors.append(
                f"{file_path}:{node.lineno}: error [PN_IMPL_ALLOWED_CLASSES_ONLY]: "
                f"Class '{node.name}' is strictly prohibited in implementation pretense modules. "
                "Implementation pretense modules must only define the implementation pseudo-state machine "
                "and TestCase classes."
            )
    return errors



def check_terminal_violating(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures 'violating(...)' is strictly the final statement of a test method (PN_TERMINAL_VIOLATING).

    In Pretense, invoking 'violating(...)' on a CheckedAdapter marks the adapter terminal upon
    asserting the expected contract violation. Any subsequent operation or violation call on that
    adapter instance raises PretenseSpecificationError. Therefore, each contract violation scenario
    must be isolated in its own dedicated test method where 'violating(...)' is the terminal statement.
    """
    errors: list[str] = []
    tree_body: list[ast.stmt] = getattr(tree, "body", [])

    def _has_violating(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if (isinstance(child.func, ast.Attribute) and child.func.attr == "violating") or (
                    isinstance(child.func, ast.Name) and child.func.id == "violating"
                ):
                    return True
        return False

    for node in tree_body:
        if not isinstance(node, ast.ClassDef):
            continue
        if "StateMachine" in node.name or node.name.endswith("State"):
            continue
        is_test_case = any(
            (isinstance(b, ast.Name) and b.id in ("TestCase", "unittest.TestCase", "LifecycleTestCase"))
            or (isinstance(b, ast.Attribute) and b.attr in ("TestCase", "LifecycleTestCase"))
            for b in node.bases
        ) or (
            (
                node.name.startswith("Test")
                or node.name.endswith("Real")
                or node.name.endswith("Fake")
            )
            and any(
                isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and m.name.startswith("test")
                for m in node.body
            )
        )
        if not is_test_case:
            continue

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith("test"):
                continue

            stmts = item.body
            if not stmts:
                continue

            violating_indices = [
                idx for idx, stmt in enumerate(stmts) if _has_violating(stmt)
            ]
            if not violating_indices:
                continue

            last_idx = len(stmts) - 1

            # Check if violating appears before the last statement:
            for idx in violating_indices:
                if idx != last_idx:
                    stmt = stmts[idx]
                    errors.append(
                        f"{file_path}:{stmt.lineno}: error [PN_TERMINAL_VIOLATING]: "
                        f"'violating(...)' must be the final statement of test method '{item.name}'. "
                        "Calling 'violating(...)' marks the checked adapter terminal; any subsequent statement in this method is prohibited. "
                        "Move subsequent operations to a separate test method."
                    )

            # Check for multiple violating calls across the method:
            violating_call_count = sum(
                1
                for stmt in stmts
                for child in ast.walk(stmt)
                if isinstance(child, ast.Call)
                and (
                    (isinstance(child.func, ast.Attribute) and child.func.attr == "violating")
                    or (isinstance(child.func, ast.Name) and child.func.id == "violating")
                )
            )
            if violating_call_count > 1:
                errors.append(
                    f"{file_path}:{item.lineno}: error [PN_TERMINAL_VIOLATING]: "
                    f"Test method '{item.name}' invokes 'violating(...)' multiple times ({violating_call_count} calls). "
                    "In Pretense, 'violating(...)' marks the checked adapter terminal; each contract violation scenario must be tested in its own dedicated test method."
                )

            # Prohibit using violating(...) as a context manager (PN_NO_WITH_VIOLATING):
            for stmt in stmts:
                if isinstance(stmt, (ast.With, ast.AsyncWith)):
                    if any(_has_violating(with_item) for with_item in stmt.items):
                        errors.append(
                            f"{file_path}:{stmt.lineno}: error [PN_NO_WITH_VIOLATING]: "
                            f"Using 'with ...violating(...):' as a context manager in '{item.name}' is strictly prohibited. "
                            "Contract violations must be invoked directly as a terminal call on the adapter: "
                            "'self.checked.violating(ExpectedError).<method>(*args)'."
                        )
    return errors



def check_no_call_target_in_interface(
    tree: ast.AST, file_path: str = "", is_interface: bool = False
) -> list[str]:
    """Ensures interface state machines do not invoke call_target, touch sut() in inner methods, or invoke SUT methods outside assert."""
    errors: list[str] = []
    if not is_interface:
        return errors


    tree_body: list[ast.stmt] = getattr(tree, "body", [])
    for node in tree_body:
        if (
            isinstance(node, ast.ClassDef)
            and "StateMachine" in node.name
            and not node.name.endswith("PseudoStateMachine")
        ):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    is_inner = item.name.startswith("inner_")
                    if is_inner:
                        for child in ast.walk(item):
                            if isinstance(child, ast.Assert):
                                errors.append(
                                    f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_ASSERT_IN_INNER] Interface inner transition '{item.name}' "
                                    f"must not contain 'assert' statements. Inner transitions exist exclusively to compute fake return values "
                                    f"or raise contracted exceptions. Assertions belong in the outer @transition method."
                                )
                            elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                                targets = getattr(child, "targets", [getattr(child, "target", None)])
                                for tgt in targets:
                                    if (
                                        isinstance(tgt, ast.Attribute)
                                        and isinstance(tgt.value, ast.Attribute)
                                        and isinstance(tgt.value.value, ast.Name)
                                        and tgt.value.value.id == "self"
                                        and tgt.value.attr == "state"
                                    ):
                                        errors.append(
                                            f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_STATE_MUTATION_IN_INNER] Interface inner transition '{item.name}' "
                                            f"must not mutate 'self.state'. State mutations belong exclusively in the outer @transition method."
                                        )
                            elif isinstance(child, ast.Raise):
                                exc_name = ""
                                if isinstance(child.exc, ast.Name):
                                    exc_name = child.exc.id
                                elif (
                                    isinstance(child.exc, ast.Call)
                                    and isinstance(child.exc.func, ast.Name)
                                ):
                                    exc_name = child.exc.func.id
                                if exc_name.endswith("Error"):
                                    errors.append(
                                        f"{file_path}:{child.lineno} Interface inner transition '{item.name}' "
                                        f"must never raise contract errors ('{exc_name}'); interface state machines rely strictly on "
                                        f"require(...) and require_arg(...) to gate contract error preconditions."
                                    )
                    sut_vars: set[str] = set()

                    for child in ast.walk(item):
                        if isinstance(child, (ast.Assign, ast.AnnAssign)):
                            val = getattr(child, "value", None)
                            if (
                                isinstance(val, ast.Call)
                                and isinstance(val.func, ast.Name)
                                and val.func.id == "sut"
                            ):
                                targets = getattr(child, "targets", [getattr(child, "target", None)])
                                for t in targets:
                                    if isinstance(t, ast.Name):
                                        sut_vars.add(t.id)

                    assert_calls: set[ast.Call] = set()
                    for child in ast.walk(item):
                        if isinstance(child, ast.Assert):
                            for sub in ast.walk(child):
                                if isinstance(sub, ast.Call):
                                    assert_calls.add(sub)

                    for child in ast.walk(item):
                        if isinstance(child, ast.Call):
                            call_name = ""
                            if isinstance(child.func, ast.Name):
                                call_name = child.func.id
                            elif isinstance(child.func, ast.Attribute):
                                call_name = child.func.attr

                            if call_name == "call_target":
                                errors.append(
                                    f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_CALL_TARGET_IN_INTERFACE] 'call_target' is prohibited in interface state machines. "
                                    f"Interface state machines are abstract models over state dataclasses; 'call_target' belongs strictly in implementation pseudo-state machines."
                                )

                            if is_inner:
                                is_sut = False
                                if isinstance(child.func, ast.Name) and child.func.id == "sut":
                                    is_sut = True
                                elif isinstance(child.func, ast.Attribute) and isinstance(child.func.value, ast.Name) and child.func.value.id in sut_vars:
                                    is_sut = True
                                if is_sut:
                                    errors.append(
                                        f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_CALL_TARGET_IN_INTERFACE] Calling 'sut(...)' inside inner transition '{item.name}' is strictly prohibited in interface state machines. "
                                        f"In interface state machines, 'inner_<method>' exists purely to compute fake return values from 'self.state' (or return None). "
                                        f"Calling the method under test on the SUT belongs exclusively to implementation pseudo-state machines."
                                    )

                            if not is_inner and child not in assert_calls and isinstance(child.func, ast.Attribute):
                                is_sut_method = False
                                if isinstance(child.func.value, ast.Name) and child.func.value.id in sut_vars:
                                    is_sut_method = True
                                elif (
                                    isinstance(child.func.value, ast.Call)
                                    and isinstance(child.func.value.func, ast.Name)
                                    and child.func.value.func.id == "sut"
                                ):
                                    is_sut_method = True
                                if is_sut_method:
                                    errors.append(
                                        f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_CALL_TARGET_IN_INTERFACE] Calling SUT method '{child.func.attr}' outside 'assert' statements is prohibited in interface state machines. "
                                        f"Interface state machines model abstract state transitions and fake computations; invoking methods on the SUT belongs strictly in implementation pseudo-state machines. "
                                        f"In interface state machines, 'sut(...)' may only be referenced within 'assert' statements to check observable properties."
                                    )
    return errors



def check_no_super_in_impl_inner(
    tree: ast.AST, file_path: str = "", is_impl: bool = False
) -> list[str]:
    """Ensures implementation pseudo-state machines do not invoke super() in inner transition methods (PRE_LINT_NO_SUPER_IN_IMPL_INNER)."""
    errors: list[str] = []
    if not is_impl:
        return errors


    tree_body: list[ast.stmt] = getattr(tree, "body", [])
    for node in tree_body:
        if (
            isinstance(node, ast.ClassDef)
            and ("PseudoStateMachine" in node.name or node.name.endswith("StateMachine"))
        ):
            for item in node.body:
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name.startswith("inner_")
                ):
                    for child in ast.walk(item):
                        if isinstance(child, ast.Call):
                            is_super = False
                            if isinstance(child.func, ast.Name) and child.func.id == "super":
                                is_super = True
                            elif (
                                isinstance(child.func, ast.Attribute)
                                and isinstance(child.func.value, ast.Call)
                                and isinstance(child.func.value.func, ast.Name)
                                and child.func.value.func.id == "super"
                            ):
                                is_super = True
                            if is_super:
                                errors.append(
                                    f"{file_path}:{child.lineno}: error: [PRE_LINT_NO_SUPER_IN_IMPL_INNER] "
                                    f"Implementation inner transition '{item.name}' must not invoke 'super()'. "
                                    f"Implementation inner transitions must delegate directly to the target via 'sut(TargetClass).{item.name[6:]}(...)'."
                                )
    return errors



def check_no_domain_any(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures state machines do not use Domain.any() (PRE_LINT_NO_DOMAIN_ANY)."""
    errors: list[str] = []
    reported_lines: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "any"
            and isinstance(node.value, ast.Name)
            and node.value.id == "Domain"
        ):
            lineno = getattr(node, "lineno", 1)
            if lineno not in reported_lines:
                reported_lines.add(lineno)
                errors.append(
                    f"{file_path}:{lineno}: error: [PRE_LINT_NO_DOMAIN_ANY] 'Domain.any()' is strictly banned. "
                    f"Cleanroom forbids untyped parameter domains; specify an explicit typed domain "
                    f"(e.g., Domain.type(...), Domain.integers(...), Domain.text(...))."
                )
    return errors



def check_multi_interface_inheritance(tree: ast.AST, file_path: str = "") -> list[str]:
    """Ensures multi-interface implementation pseudo-state machines inherit all implemented interface state machines."""
    errors: list[str] = []
    if not file_path or not file_path.endswith("_impl_pretense.py"):
        return errors


    high_spec_path: Path | None = None
    curr_path = Path(file_path).resolve()
    if "parts" in curr_path.parts:
        try:
            parts_idx = curr_path.parts.index("parts")
            unit_name = curr_path.name.replace("_pretense.py", "")
            unit_dir = Path(*curr_path.parts[: parts_idx + 2])
            cand = unit_dir / "high" / f"{unit_name}.md"
            if cand.is_file():
                high_spec_path = cand
        except Exception:
            pass

    if high_spec_path is None or not high_spec_path.is_file():
        return errors


    try:
        high_text = high_spec_path.read_text(encoding="utf-8")
    except OSError:
        return errors


    implements_targets: list[str] = []
    for line in high_text.splitlines()[:20]:
        line_s = line.strip()
        if line_s.startswith("implements:"):
            raw = line_s[len("implements:") :].strip()
            implements_targets = [t.strip() for t in raw.split(",") if t.strip()]
            break

    if len(implements_targets) <= 1:
        return errors


    pseudo_sm_cls: ast.ClassDef | None = None
    tree_body: list[ast.stmt] = getattr(tree, "body", [])
    for node in tree_body:
        if isinstance(node, ast.ClassDef) and (
            "PseudoStateMachine" in node.name
            or ("StateMachine" in node.name and node.name != "StateMachine")
        ):
            pseudo_sm_cls = node
            break

    if pseudo_sm_cls is None:
        return errors


    inherited_bases: set[str] = set()
    for base in pseudo_sm_cls.bases:
        if isinstance(base, ast.Name):
            inherited_bases.add(base.id)
        elif isinstance(base, ast.Subscript):
            if isinstance(base.value, ast.Name):
                inherited_bases.add(base.value.id)

    for target in implements_targets:
        expected_pascal = "".join(p.capitalize() for p in target.split("_"))
        expected_sm_name = f"{expected_pascal}StateMachine"
        if expected_sm_name not in inherited_bases:
            errors.append(
                f"{file_path}:{pseudo_sm_cls.lineno}: error: [PRE_LINT_MULTI_INTERFACE_INHERITANCE] component implements {implements_targets}, "
                f"but '{pseudo_sm_cls.name}' does not inherit from '{expected_sm_name}'. "
                f"Multi-interface implementation pseudo-state machines must inherit all implemented interface state machines."
            )

    return errors



def check_interface_transition_coverage(
    tree: ast.AST,
    file_path: str = "",
    is_interface: bool = False,
    pyi_elements: dict[str, Any] | None = None,
) -> list[str]:
    """Ensures interface pretense files define fixed fake tests that cover 100% of declared transitions and seeding transitions."""
    errors: list[str] = []
    if not is_interface:
        return errors


    sm_cls: ast.ClassDef | None = None
    tree_body: list[ast.stmt] = getattr(tree, "body", [])
    for node in tree_body:
        if (
            isinstance(node, ast.ClassDef)
            and "StateMachine" in node.name
            and not node.name.endswith("PseudoStateMachine")
        ):
            sm_cls = node
            break

    if sm_cls is None:
        return errors


    declared_transitions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for item in sm_cls.body:
        if isinstance(
            item, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and not item.name.startswith("_"):
            for dec in item.decorator_list:
                is_t = False
                alias_name: str | None = None
                if isinstance(dec, ast.Name) and dec.id == "transition":
                    is_t = True
                elif isinstance(dec, ast.Call):
                    if (isinstance(dec.func, ast.Name) and dec.func.id == "transition") or (
                        isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "transition"
                    ):
                        is_t = True
                        for kw in dec.keywords:
                            if (
                                kw.arg == "name"
                                and isinstance(kw.value, ast.Constant)
                                and isinstance(kw.value.value, str)
                            ):
                                alias_name = kw.value.value
                                break
                elif isinstance(dec, ast.Attribute) and dec.attr in (
                    "transition",
                    "seeding",
                ):
                    is_t = True
                if is_t:
                    declared_transitions[alias_name or item.name] = item
                    break

    if not declared_transitions:
        if pyi_elements and pyi_elements.get("classes"):
            total_methods = sum(
                len(c.get("methods", [])) for c in pyi_elements["classes"]
            )
            if total_methods > 0:
                errors.append(
                    f"{file_path}:{sm_cls.lineno}: error: [PRE_LINT_INTERFACE_TRANSITION_COVERAGE] state machine '{sm_cls.name}' "
                    f"defines 0 transitions, but interface specification declares {total_methods} method(s). "
                    f"State machine must define 1:1 transitions for all public methods."
                )
        return errors

    has_fuzz_suite = any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "compile_hypothesis_test_case")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "compile_hypothesis_test_case")
        )
        for stmt in tree_body
        for node in ast.walk(stmt)
    )
    if has_fuzz_suite:
        return errors

    test_cases: list[ast.ClassDef] = []
    for node in tree_body:
        if isinstance(node, ast.ClassDef):
            is_test_case_subclass = any(
                (isinstance(b, ast.Name) and b.id in ("TestCase", "unittest.TestCase", "LifecycleTestCase"))
                or (isinstance(b, ast.Attribute) and b.attr in ("TestCase", "LifecycleTestCase"))
                for b in node.bases
            )
            has_test_methods = any(
                isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and m.name.startswith("test")
                for m in node.body
            )
            if (
                is_test_case_subclass or node.name.startswith("Test")
            ) and has_test_methods:
                test_cases.append(node)

    if not test_cases:
        clean_name = sm_cls.name.replace("StateMachine", "")
        errors.append(
            f"{file_path}:1: error: [PRE_LINT_INTERFACE_TRANSITION_COVERAGE] interface pretense module is missing a fixed test suite (e.g. 'Test{clean_name}Fake(unittest.TestCase)'). "
            f"Interface pretense modules must include fixed fake tests covering 100% of transitions and seeding transitions."
        )
        return errors


    called_names: set[str] = set()
    accessed_names: set[str] = set()
    for tc in test_cases:
        for item in tc.body:
            if isinstance(
                item, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and item.name.startswith("test"):
                for child in ast.walk(item):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            called_names.add(child.func.attr)
                        elif isinstance(child.func, ast.Name):
                            called_names.add(child.func.id)
                    elif isinstance(child, ast.Attribute):
                        accessed_names.add(child.attr)

    exercised = called_names | accessed_names
    tc_name = test_cases[0].name

    for t_name, t_node in declared_transitions.items():
        if t_name not in exercised:
            errors.append(
                f"{file_path}:{t_node.lineno}: error: [PRE_LINT_INTERFACE_TRANSITION_COVERAGE] transition '{t_name}' on '{sm_cls.name}' "
                f"was not covered by fixed tests in '{tc_name}'. "
                f"Advice: Ensure its required conditions can be properly reached by existing transitions, or add seeding transitions if coverage is difficult."
            )

    return errors


def check_unbound_initial_state_factory(tree: ast.AST, file_path: str) -> list[str]:
    """Rejects unbound Class.make_initial_state passed to compile_hypothesis_test_case."""
    errors: list[str] = []
    class_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        is_compile = (
            isinstance(node.func, ast.Name)
            and node.func.id == "compile_hypothesis_test_case"
        ) or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "compile_hypothesis_test_case"
        )
        if not is_compile:
            continue
        for kw in node.keywords:
            if kw.arg != "initial_state_factory":
                continue
            val = kw.value
            if (
                isinstance(val, ast.Attribute)
                and val.attr == "make_initial_state"
                and isinstance(val.value, ast.Name)
                and (
                    val.value.id in class_names
                    or val.value.id.endswith("StateMachine")
                )
            ):
                errors.append(
                    f"{file_path}:{node.lineno}: error: [PRE_LINT_UNBOUND_INITIAL_STATE_FACTORY] "
                    f"initial_state_factory='{val.value.id}.make_initial_state' passes an unbound class method; "
                    f"pass a bound instance method (e.g. 'proto.make_initial_state') instead."
                )
    return errors


def check_setup_super_order(tree: ast.AST, file_path: str) -> list[str]:
    """Ensures LifecycleTestCase.setUp calls super().setUp() before get_singleton()/sut()."""
    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        is_lifecycle_tc = any(
            (isinstance(b, ast.Name) and b.id == "LifecycleTestCase")
            or (isinstance(b, ast.Attribute) and b.attr == "LifecycleTestCase")
            for b in node.bases
        )
        if not is_lifecycle_tc:
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef) or item.name != "setUp":
                continue
            seen_super = False
            for stmt in item.body:
                for sub in ast.walk(stmt):
                    if (
                        isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "setUp"
                        and isinstance(sub.func.value, ast.Call)
                        and isinstance(sub.func.value.func, ast.Name)
                        and sub.func.value.func.id == "super"
                    ):
                        seen_super = True
                        break
                if seen_super:
                    continue
                for sub in ast.walk(stmt):
                    if (
                        isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Name)
                        and sub.func.id in ("get_singleton", "sut")
                    ):
                        errors.append(
                            f"{file_path}:{sub.lineno}: error: [PRE_LINT_SETUP_SUPER_ORDER] "
                            f"'{sub.func.id}(...)' called before 'super().setUp()' in '{node.name}.setUp'; "
                            f"call 'super().setUp()' first so LifecycleTestCase auto-registers imported *_impl singletons."
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
                    if (
                        item.name.startswith("__")
                        and item.name.endswith("__")
                        and item.name != "__init__"
                    ):
                        continue
                    is_prop = any(
                        (isinstance(d, ast.Name) and d.id == "property")
                        or (isinstance(d, ast.Attribute) and d.attr == "property")
                        for d in item.decorator_list
                    )
                    if is_prop:
                        properties.append(item.name)
                    else:
                        raw_args: list[ast.arg] = [
                            a for a in item.args.args if a.arg != "self"
                        ]
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
                        methods.append(
                            {
                                "name": item.name,
                                "args": [a["name"] for a in arg_info],
                                "arg_info": arg_info,
                                "return_type": ret_type,
                            }
                        )

            is_protocol = any(
                (isinstance(b, ast.Name) and b.id == "Protocol")
                or (isinstance(b, ast.Attribute) and b.attr == "Protocol")
                for b in node.bases
            )

            classes.append(
                {
                    "name": node.name,
                    "methods": methods,
                    "properties": properties,
                    "is_protocol": is_protocol,
                }
            )

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
                is_trans = (isinstance(func, ast.Name) and func.id == "transition") or (
                    isinstance(func, ast.Attribute) and func.attr == "transition"
                )
                if is_trans and d.args:
                    arg0 = d.args[0]
                    if isinstance(arg0, ast.Attribute) and isinstance(
                        arg0.value, ast.Name
                    ):
                        cls_name = arg0.value.id
                        prop_name = arg0.attr
                        if (
                            cls_name in protocol_props
                            and prop_name in protocol_props[cls_name]
                        ):
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


def _discover_package_initializers(
    pyi_path: str,
    lib_dir: str | None = None,
    impl_path: str | None = None,
    impl_stem: str = "",
    has_singleton: bool = False,
) -> list[str]:
    """Inspects target unit directory (pyi_path / lib_dir) for all sibling modules defining __initialize__."""
    dirs_to_check: list[str] = []
    if lib_dir and os.path.isdir(lib_dir):
        cand = os.path.abspath(lib_dir)
        if cand not in dirs_to_check:
            dirs_to_check.append(cand)
    if impl_path and os.path.isfile(impl_path):
        cand = os.path.dirname(os.path.abspath(impl_path))
        if cand not in dirs_to_check and os.path.isdir(cand):
            dirs_to_check.append(cand)
    if pyi_path and os.path.isfile(pyi_path):
        pyi_dir = os.path.dirname(os.path.abspath(pyi_path))
        if pyi_dir not in dirs_to_check and os.path.isdir(pyi_dir):
            dirs_to_check.append(pyi_dir)
        if os.path.basename(pyi_dir) == "low":
            sibling_lib = os.path.join(os.path.dirname(pyi_dir), "lib")
            if sibling_lib not in dirs_to_check and os.path.isdir(sibling_lib):
                dirs_to_check.append(sibling_lib)

    stems_with_init: set[str] = set()
    if has_singleton and impl_stem:
        stems_with_init.add(impl_stem)

    for d in dirs_to_check:
        try:
            for entry in os.listdir(d):
                if entry.startswith((".", "_")) or entry == "__init__.py":
                    continue
                if not (entry.endswith(".py") or entry.endswith(".pyi")):
                    continue
                m_stem = entry[:-3] if entry.endswith(".py") else entry[:-4]
                if m_stem.startswith("_") or m_stem.endswith(
                    ("_test", "_pretense", "_ext")
                ):
                    continue
                file_full = os.path.join(d, entry)
                if not os.path.isfile(file_full):
                    continue

                has_init = False
                if entry.endswith(".py"):
                    try:
                        content = read_text(file_full)
                        if (
                            "def __initialize__" in content
                            or "singleton_type" in content
                            or "singleton" in content
                        ):
                            tree = ast.parse(content, filename=file_full)
                            for node in tree.body:
                                if (
                                    isinstance(node, ast.FunctionDef)
                                    and node.name == "__initialize__"
                                ):
                                    has_init = True
                                    break
                                elif isinstance(node, ast.ClassDef):
                                    for dec in node.decorator_list:
                                        dec_name = ""
                                        if isinstance(dec, ast.Name):
                                            dec_name = dec.id
                                        elif isinstance(dec, ast.Call) and isinstance(
                                            dec.func, ast.Name
                                        ):
                                            dec_name = dec.func.id
                                        if dec_name in ("singleton", "singleton_type"):
                                            has_init = True
                                            break
                                    if has_init:
                                        break
                    except Exception:
                        pass
                elif entry.endswith(".pyi"):
                    try:
                        elems = extract_pyi_elements(file_full)
                        if elems.get("has_singleton") or m_stem.endswith(
                            ("_impl", "_asm")
                        ):
                            has_init = True
                    except Exception:
                        pass

                if has_init:
                    stems_with_init.add(m_stem)
        except OSError:
            pass

    return sorted(stems_with_init)


def _generate_init_alias(stem: str, used_aliases: set[str]) -> str:
    clean = stem.replace("_impl", "").replace("_asm", "")
    parts = [p for p in clean.split("_") if p]
    initials = "".join(p[0] for p in parts)
    candidate = f"_{initials}_initialize" if initials else f"_{stem}_initialize"
    if candidate not in used_aliases:
        used_aliases.add(candidate)
        return candidate
    fallback = f"_{clean}_initialize"
    if fallback not in used_aliases:
        used_aliases.add(fallback)
        return fallback
    idx = 2
    while f"_{initials}_{idx}_initialize" in used_aliases:
        idx += 1
    alias = f"_{initials}_{idx}_initialize"
    used_aliases.add(alias)
    return alias


def generate_pretense_scaffold(
    pyi_path: str,
    stem: str,
    impl_stem: str,
    lib_pkg: str,
    impl_path: str | None = None,
    is_interface: bool | None = None,
    lib_dir: str | None = None,
) -> str:
    """Generates canonical Pretense state machine, fake, unit tests, and fuzzing skeleton."""
    elements = extract_pyi_elements(pyi_path)
    classes = elements["classes"]
    has_singleton = elements["has_singleton"] or impl_stem.endswith("_impl")

    package_inits = (
        _discover_package_initializers(
            pyi_path=pyi_path,
            lib_dir=lib_dir,
            impl_path=impl_path,
            impl_stem=impl_stem,
            has_singleton=has_singleton,
        )
        if has_singleton
        else []
    )

    init_aliases: dict[str, str] = {}
    if len(package_inits) > 1:
        used_al: set[str] = set()
        for mod in package_inits:
            init_aliases[mod] = _generate_init_alias(mod, used_al)

    # Filter service classes (exclude error, message, config, event, spec, state types)
    service_classes = [
        c
        for c in classes
        if not c["name"].endswith(
            ("Error", "Message", "Config", "Event", "Spec", "State")
        )
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
            "import unittest",
            "",
            "from hypothesis import given, settings, strategies as st",
            "",
            "from pretense import (",
            "    Domain,",
            "    StateMachine,",
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
            c["name"] for c in classes if not c["name"].endswith(("Error", "Exception"))
        ]
        if not import_classes:
            import_classes = [target_cls_name]
        lines.append(f"from {import_module} import {', '.join(import_classes)}")

        lines.extend(
            [
                "",
                "",
                "# ==============================================================================",
                "# 1. State Machine Specification (Model & Transitions)",
                "# ==============================================================================",
                "# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).",
                "# Contract violations (*Error, e.g. NodeNotFoundError) are preconditions: use require_arg(arg, Domain.in_set(self.state.items)) or require(condition) (optional error=ExpectedError is documentation only). NEVER use with raises(...) for *Error!",
                "# Operational exceptions (*Exception) use Env[bool] + require_env(healthy_cond, ExpectedException) in interface SMs, bound via self.bind(...) in impl.",
                "# require_arg defines the caller precondition contract (checked at runtime on real calls).",
                "# Use Domain.type(T) or open domain; use preferred=[...] to cluster/bias fuzz inputs without restricting the contract.",
                "#",
                "# REFERENCE PATTERNS:",
                "#   # 1:1 Transition Pattern with Domain strategies and inner transition delegation:",
                "#   @transition(TargetClass.method)",
                "#   def method(self, arg1: str, count: int) -> ReturnType:",
                "#       require(self.state.initialized)",
                '#       require_arg(arg1, Domain.type(str), preferred=["sample"])',
                "#       require_arg(count, Domain.range(1, 100), preferred=[10])",
                "#       ret = self.inner_method(arg1, count)",
                "#       self.state.items.append(ret)",
                "#       return ret",
                "#",
                "#   def inner_method(self, arg1: str, count: int) -> ReturnType:",
                "#       return ReturnType(...)  # or None / fake value",
                "#",
                "#   # Seeding Transition (sets up state dynamically outside default __init__):",
                "#   @transition.seeding",
                "#   def seed_initial(self) -> None:",
                "#       self.state.initialized = True",
                "#",
                "#   # Single service fake factory:",
                "#   FakeTarget = synthesize_fake(TargetStateMachine)",
                "#   def make_target_fake(state: Optional[TargetState] = None) -> TargetClass:",
                "#       return FakeTarget(state=state or TargetState())",
                "#",
                "#   # Fixed fake test suite covering 100% of transitions and seeding transitions:",
                "#   class TestTargetFake(unittest.TestCase):",
                "#       def setUp(self) -> None:",
                "#           self.fake = make_target_fake()",
                "#           self.sm = TargetStateMachine()",
                "#       def test_transitions_coverage(self) -> None:",
                "#           self.sm.seed_initial()",
                '#           self.fake.method("sample", 10)',
                "",
                "def _unimplemented_transition(name: str) -> Any:",
                '    """Placeholder for unmodeled transition return contracts that crashes at runtime."""',
                "    raise NotImplementedError(",
                "        f\"Pretense transition '{name}' returns contract must be implemented; dummy returns are strictly prohibited.\"",
                "    )",
                "",
                "",
                "@dataclass",
                f"class {state_cls_name}:",
                f'    """Canonical model state for {target_cls_name} operations."""',
                "    initialized: bool = True",
            ]
        )

        for prop in all_props:
            lines.append(f"    {prop}: Optional[Any] = None")

        lines.extend(
            [
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
                f"        super().__init__(state=state or self.make_initial_state(), singletons=singletons)",
                "",
                f"    def make_initial_state(self) -> {state_cls_name}:",
                f'        """Constructs initial model state. May be specialized by pseudo-state machines."""',
                f"        return {state_cls_name}()",
            ]
        )

        for sc in service_classes:
            cls_name = sc["name"]
            for m in sc["methods"]:
                mname = m["name"]
                arg_info = m.get(
                    "arg_info", [{"name": a, "type": "Any"} for a in m["args"]]
                )
                ret_type = m.get("return_type", "Any")
                fn_name = (
                    mname
                    if method_counts[mname] == 1
                    else f"{cls_name.lower()}_{mname}"
                )
                lines.extend(
                    [
                        "",
                        f"    @transition({cls_name}.{mname})",
                        f"    def {fn_name}(",
                        "        self,",
                    ]
                )
                for ai in arg_info:
                    atype = ai["type"] if ai["type"] else "Any"
                    lines.append(f"        {ai['name']}: {atype},")
                lines.extend(
                    [
                        "    ) -> None:",
                        "        require(self.state.initialized)",
                    ]
                )
                for ai in arg_info:
                    dom_expr = _default_domain_arg(ai["name"], ai.get("type", ""))
                    lines.append(f"        require_arg({ai['name']}, {dom_expr})")
                call_args = ", ".join(ai["name"] for ai in arg_info)
                if ret_type in ("None", "NoneType"):
                    lines.extend(
                        [
                            f"        ret = self.inner_{fn_name}({call_args})",
                            "        assert ret is None",
                            "        return ret",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            f"        ret: {ret_type} = self.inner_{fn_name}({call_args})",
                            "        assert ret is not None",
                            "        return ret",
                        ]
                    )
                lines.extend(
                    [
                        "",
                        f"    def inner_{fn_name}(",
                        "        self,",
                    ]
                )
                for ai in arg_info:
                    atype = ai["type"] if ai["type"] else "Any"
                    lines.append(f"        {ai['name']}: {atype},")
                if ret_type in ("None", "NoneType"):
                    lines.extend(
                        [
                            "    ) -> None:",
                            "        return None",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            f"    ) -> {ret_type}:",
                            f"        return _unimplemented_transition('{fn_name}')",
                        ]
                    )

        for sc in service_classes:
            cls_name = sc["name"]
            for prop in sc.get("properties", []):
                fn_name = (
                    prop if method_counts[prop] == 0 else f"{cls_name.lower()}_{prop}"
                )
                lines.extend(
                    [
                        "",
                        f'    @transition(name="{prop}")',
                        f"    def {fn_name}(self) -> Any:",
                        "        require(self.state.initialized)",
                        f"        ret: Any = self.inner_{fn_name}()",
                        "        assert ret is not None",
                        "        return ret",
                        "",
                        f"    def inner_{fn_name}(self) -> Any:",
                        f"        return _unimplemented_transition('{fn_name}')",
                    ]
                )

        lines.extend(
            [
                "",
                "    @transition.seeding",
                "    def seed_initial(self) -> None:",
                '        """Seed state machine state for fake initialization."""',
                "        self.state.initialized = True",
            ]
        )

        fake_cls_name = f"Fake{pascal_name}"
        lines.extend(
            [
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
            ]
        )
        single_cls = (
            service_classes[0]["name"] if service_classes else target_cls_name
        )
        if len(service_classes) > 1:
            fake_ret_type = f"Tuple[{', '.join(c['name'] for c in service_classes)}]"
            lines.extend(
                [
                    f"def make_{clean_stem}_fakes(",
                    f"    state: Optional[{state_cls_name}] = None,",
                    f") -> {fake_ret_type}:",
                    f'    """Synthesizes fake instances for component services sharing model state."""',
                    f"    fake = {fake_cls_name}(state=state or {state_cls_name}())",
                    f"    return (",
                    f"        "
                    + ",\n        ".join("fake" for _ in service_classes)
                    + ",",
                    f"    )",
                ]
            )
        else:
            lines.extend(
                [
                    f"def make_{clean_stem}_fake(",
                    f"    state: Optional[{state_cls_name}] = None,",
                    f") -> {single_cls}:",
                    f'    """Synthesizes fake instance for {single_cls}."""',
                    f"    return {fake_cls_name}(state=state or {state_cls_name}())",
                ]
            )

        test_fake_cls = f"Test{pascal_name}Fake"
        lines.extend(
            [
                "",
                "",
                "# ==============================================================================",
                "# 3. Fixed Scenarios on Fake",
                "# ==============================================================================",
                "",
                f"class {test_fake_cls}(unittest.TestCase):",
                f'    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""',
                "",
                "    def setUp(self) -> None:",
            ]
        )
        if len(service_classes) > 1:
            lines.append(f"        self.fakes = make_{clean_stem}_fakes()")
            lines.append(f"        self.sm = {iface_sm_cls_name}()")
        else:
            lines.append(f"        self.fake = make_{clean_stem}_fake()")
            lines.append(f"        self.sm = {iface_sm_cls_name}(singletons={{{single_cls}: self.fake}})")
        lines.extend(
            [
                "",
                "    def test_transitions_coverage(self) -> None:",
                '        """Exercises all transitions and seeding transitions on the fake."""',
                "        self.sm.seed_initial()",
            ]
        )
        for sc in service_classes:
            cls_name = sc["name"]
            for prop in sc.get("properties", []):
                fn_name = (
                    prop if method_counts[prop] == 0 else f"{cls_name.lower()}_{prop}"
                )
                if len(service_classes) > 1:
                    lines.append(f"        _ = self.sm.{fn_name}()")
                else:
                    lines.append(f"        _ = self.fake.{prop}")
            for m in sc["methods"]:
                fn_name = m["name"]
                arg_info = m.get(
                    "arg_info", [{"name": a, "type": "Any"} for a in m["args"]]
                )
                args_call = ", ".join(
                    _sample_val_for_arg(a["name"], a.get("type", "")) for a in arg_info
                )
                if len(service_classes) > 1:
                    lines.append(f"        self.sm.{fn_name}({args_call})")
                else:
                    lines.append(f"        self.fake.{fn_name}({args_call})")

        lines.extend(
            [
                "",
                "",
                "# ==============================================================================",
                "# 4. Hypothesis Stateful Fuzzing on Fake",
                "# ==============================================================================",
                "",
                f"Fake{pascal_name}FuzzTest = compile_hypothesis_test_case(",
                "    proto=proto,",
                "    initial_state_factory=proto.make_initial_state,",
                f'    name="Fake{pascal_name}FuzzTest",',
                ")",
                "",
            ]
        )
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
            ")",
            "from pretense.compiler import compile_hypothesis_test_case",
        ]

        if has_singleton:
            lines.append(
                "from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system"
            )

        pretense_pkg = (
            lib_pkg.rsplit(".", 1)[0] + ".pretense" if lib_pkg else "pretense"
        )
        iface_symbols = [iface_sm_cls_name, state_cls_name, f"Fake{pascal_name}"]
        if len(service_classes) > 1:
            iface_symbols.append(f"make_{clean_stem}_fakes")
        else:
            iface_symbols.append(f"make_{clean_stem}_fake")
        lines.append(
            f"from {pretense_pkg}.{clean_stem}_pretense import ({', '.join(iface_symbols)})"
        )

        import_module = f"{lib_pkg}.{impl_stem}" if lib_pkg else impl_stem
        import_classes = [
            c["name"] for c in classes if not c["name"].endswith(("Error", "Exception"))
        ]
        if not import_classes:
            import_classes = [target_cls_name]
        import_symbols = list(import_classes)
        if has_singleton and not init_aliases:
            import_symbols.append("__initialize__")
        lines.append(f"from {import_module} import {', '.join(import_symbols)}")
        if init_aliases:
            for mod, alias in init_aliases.items():
                m_imp = f"{lib_pkg}.{mod}" if lib_pkg else mod
                lines.append(f"from {m_imp} import __initialize__ as {alias}")

        lines.extend(
            [
                "",
                "",
                "# ==============================================================================",
                "# 1. Implementation Pseudo-State Machine",
                "# ==============================================================================",
                "# REFERENCE PATTERNS:",
                "#   # Implementation pseudo-state machine inner transition override with call_target:",
                "#   def inner_method(self, *args) -> Any:",
                "#       target: TargetClass = sut(TargetClass)",
                "#       old_val = target.property",
                "#       ret = call_target(target.method(*args))",
                "#       assert target.property == old_val",
                "#       return ret",
                "#",
                "#   # Real implementation scenario test driving self.checked (100% statement coverage):",
                "#   class TestTargetImplReal(unittest.TestCase):",
                "#       def setUp(self) -> None:",
                "#           self.registry = LifecycleRegistry()",
                "#           __initialize__(self.registry)",
                "#           self.phase_scope = enter_phase(system, registry=self.registry)",
                "#           self.phase_scope.__enter__()",
                "#           self.real = get_singleton(TargetClass)",
                "#           self.sm = TargetImplPseudoStateMachine(singletons={TargetClass: self.real})",
                "#           self.checked = self.sm.as_checked(TargetClass, self.real)",
                "#       def tearDown(self) -> None:",
                "#           self.phase_scope.__exit__(None, None, None)",
                "#       def test_real_conformance(self) -> None:",
                "#           self.checked.method(*args)",
                "",
                f"class {impl_sm_cls_name}({iface_sm_cls_name}):",
                f'    """Implementation pseudo-state machine for {pascal_name}."""',
            ]
        )

        for sc in service_classes:
            cls_name = sc["name"]
            for m in sc["methods"]:
                mname = m["name"]
                arg_info = m.get(
                    "arg_info", [{"name": a, "type": "Any"} for a in m["args"]]
                )
                fn_name = (
                    mname
                    if method_counts[mname] == 1
                    else f"{cls_name.lower()}_{mname}"
                )
                call_args = ", ".join(ai["name"] for ai in arg_info)
                lines.extend(
                    [
                        "",
                        f"    def inner_{fn_name}(",
                        "        self,",
                    ]
                )
                for ai in arg_info:
                    atype = ai["type"] if ai["type"] else "Any"
                    lines.append(f"        {ai['name']}: {atype},")
                lines.extend(
                    [
                        "    ) -> Any:",
                        f"        target: {cls_name} = sut({cls_name})",
                        f"        ret = call_target(target.{mname}({call_args}))",
                        "        return ret",
                    ]
                )

        for sc in service_classes:
            cls_name = sc["name"]
            for prop in sc.get("properties", []):
                fn_name = (
                    prop if method_counts[prop] == 0 else f"{cls_name.lower()}_{prop}"
                )
                lines.extend(
                    [
                        "",
                        f"    def inner_{fn_name}(self) -> Any:",
                        f"        target: {cls_name} = sut({cls_name})",
                        f'        ret = call_target(getattr(target, "{prop}"))',
                        "        return ret",
                    ]
                )

        lines.extend(
            [
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
            ]
        )

        if has_singleton:
            lines.extend(
                [
                    "        self.registry = LifecycleRegistry()",
                ]
            )
            if init_aliases:
                for alias in init_aliases.values():
                    lines.append(f"        {alias}(self.registry)")
            else:
                lines.append("        __initialize__(self.registry)")
            lines.extend(
                [
                    "        self.phase_scope = enter_phase(system, registry=self.registry)",
                    "        self.phase_scope.__enter__()",
                ]
            )
            if len(service_classes) > 1:
                for c in service_classes:
                    lines.append(
                        f"        self.{c['name'].lower()} = get_singleton({c['name']})"
                    )
                svc_dict = ", ".join(
                    f"{c['name']}: self.{c['name'].lower()}" for c in service_classes
                )
                lines.append(
                    f"        self.sm = {impl_sm_cls_name}(singletons={{{svc_dict}}})"
                )
                for c in service_classes:
                    lines.append(
                        f"        self.checked_{c['name'].lower()} = self.sm.as_checked({c['name']}, self.{c['name'].lower()})"
                    )
            else:
                lines.append(f"        self.real = get_singleton({target_cls_name})")
                lines.append(
                    f"        self.sm = {impl_sm_cls_name}(singletons={{{target_cls_name}: self.real}})"
                )
                lines.append(
                    f"        self.checked = self.sm.as_checked({target_cls_name}, self.real)"
                )
            lines.extend(
                [
                    "",
                    "    def tearDown(self) -> None:",
                    "        self.phase_scope.__exit__(None, None, None)",
                ]
            )
        else:
            if len(service_classes) > 1:
                for c in service_classes:
                    lines.append(f"        self.{c['name'].lower()} = {c['name']}()")
                svc_dict = ", ".join(
                    f"{c['name']}: self.{c['name'].lower()}" for c in service_classes
                )
                lines.append(
                    f"        self.sm = {impl_sm_cls_name}(singletons={{{svc_dict}}})"
                )
                for c in service_classes:
                    lines.append(
                        f"        self.checked_{c['name'].lower()} = self.sm.as_checked({c['name']}, self.{c['name'].lower()})"
                    )
            else:
                lines.append(f"        self.real = {target_cls_name}()")
                lines.append(
                    f"        self.sm = {impl_sm_cls_name}(singletons={{{target_cls_name}: self.real}})"
                )
                lines.append(
                    f"        self.checked = self.sm.as_checked({target_cls_name}, self.real)"
                )

        lines.extend(
            [
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
            ]
        )

        if len(service_classes) > 1:
            sut_cls_name = f"{pascal_name}SUT"
            lines.extend(
                [
                    f"class {sut_cls_name}:",
                    f'    """Aggregate SUT exposing component services for {pascal_name} state machine testing."""',
                    "",
                    "    def __init__(self) -> None:",
                    '        self.__dict__["_services"] = ()',
                ]
            )
            if has_singleton:
                lines.extend(
                    [
                        "        self.registry = LifecycleRegistry()",
                        "        __initialize__(self.registry)",
                        "        self.phase_scope = enter_phase(system, registry=self.registry)",
                        "        self.phase_scope.__enter__()",
                    ]
                )
                for c in service_classes:
                    lines.append(
                        f"        self.{c['name'].lower()} = get_singleton({c['name']})"
                    )
                svc_tuple = ", ".join(
                    f"self.{c['name'].lower()}" for c in service_classes
                )
                lines.append(f'        self.__dict__["_services"] = ({svc_tuple},)')
            else:
                for c in service_classes:
                    lines.append(f"        self.{c['name'].lower()} = {c['name']}()")
                svc_tuple = ", ".join(
                    f"self.{c['name'].lower()}" for c in service_classes
                )
                lines.append(f'        self.__dict__["_services"] = ({svc_tuple},)')

            lines.extend(
                [
                    "",
                    "    def __getattr__(self, name: str) -> Any:",
                    '        if name.startswith("__") and name.endswith("__"):',
                    "            raise AttributeError(name)",
                    '        for service in self.__dict__.get("_services", ()):',
                    "            if hasattr(service, name):",
                    "                return getattr(service, name)",
                    f'        raise AttributeError(f"{{type(self).__name__}} has no attribute {{name!r}}")',
                    "",
                    f"def make_sut() -> {sut_cls_name}:",
                    f"    return {sut_cls_name}()",
                ]
            )
        else:
            single_cls = (
                service_classes[0]["name"] if service_classes else target_cls_name
            )
            lines.extend(
                [
                    f"def make_sut() -> {single_cls}:",
                ]
            )
            if has_singleton:
                lines.extend(
                    [
                        "    registry = LifecycleRegistry()",
                    ]
                )
                if init_aliases:
                    for alias in init_aliases.values():
                        lines.append(f"    {alias}(registry)")
                else:
                    lines.append("    __initialize__(registry)")
                lines.extend(
                    [
                        "    scope = enter_phase(system, registry=registry)",
                        "    scope.__enter__()",
                        f"    return get_singleton({single_cls})",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"    return {single_cls}()",
                    ]
                )

        lines.extend(
            [
                "",
                "",
                f"{pascal_name}FuzzTest = compile_hypothesis_test_case(",
                "    proto=proto,",
                "    sut_factory=make_sut,",
                "    initial_state_factory=proto.make_initial_state,",
                f'    name="{pascal_name}FuzzTest",',
                ")",
                "",
            ]
        )
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
        lines.append(
            "from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system"
        )

    # Import target classes from lib package
    import_module = f"{lib_pkg}.{impl_stem}" if lib_pkg else impl_stem
    import_classes = [
        c["name"] for c in classes if not c["name"].endswith(("Error", "Exception"))
    ]
    if not import_classes:
        import_classes = [target_cls_name]
    import_symbols = list(import_classes)
    if has_singleton and not init_aliases:
        import_symbols.append("__initialize__")
    lines.append(f"from {import_module} import {', '.join(import_symbols)}")
    if init_aliases:
        for mod, alias in init_aliases.items():
            m_imp = f"{lib_pkg}.{mod}" if lib_pkg else mod
            lines.append(f"from {m_imp} import __initialize__ as {alias}")

    sm_cls_name = f"{pascal_name}StateMachine"

    lines.extend(
        [
            "",
            "",
            "# ==============================================================================",
            "# 1. State Machine Specification (Model & Transitions)",
            "# ==============================================================================",
            "# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).",
            "# Contract violations (*Error, e.g. NodeNotFoundError) are preconditions: use require_arg(arg, Domain.in_set(self.state.items)) or require(condition) (optional error=ExpectedError is documentation only). NEVER use with raises(...) for *Error!",
            "# Operational exceptions (*Exception) use Env[bool] + require_env(healthy_cond, ExpectedException) in interface SMs, bound via self.bind(...) in impl.",
            "# require_arg defines the caller precondition contract (checked at runtime on real calls).",
            "# Use Domain.type(T) or open domain; use preferred=[...] to cluster/bias fuzz inputs without restricting the contract.",
            "",
            "def _unimplemented_transition(name: str) -> Any:",
            '    """Placeholder for unmodeled transition return contracts that crashes at runtime."""',
            "    raise NotImplementedError(",
            "        f\"Pretense transition '{name}' returns contract must be implemented; dummy returns are strictly prohibited.\"",
            "    )",
            "",
            "",
            "@dataclass",
            f"class {state_cls_name}:",
            f'    """Canonical model state for {target_cls_name} operations."""',
            "    initialized: bool = True",
        ]
    )

    for prop in all_props:
        lines.append(f"    {prop}: Optional[Any] = None")

    sut_cls_name = f"{pascal_name}SUT"
    if len(service_classes) > 1:
        sut_type = sut_cls_name
        lines.extend(
            [
                "",
                "",
                f"class {sut_cls_name}:",
                f'    """Aggregate SUT exposing component services for {pascal_name} state machine testing."""',
                "",
                "    tier = system",
                "",
                "    def __init__(self) -> None:",
                '        self.__dict__["_services"] = ()',
            ]
        )
        if has_singleton:
            lines.extend(
                [
                    "        self.registry = LifecycleRegistry()",
                ]
            )
            if init_aliases:
                for alias in init_aliases.values():
                    lines.append(f"        {alias}(self.registry)")
            else:
                lines.append("        __initialize__(self.registry)")
            lines.extend(
                [
                    "        self.phase_scope = enter_phase(system, registry=self.registry)",
                    "        self.phase_scope.__enter__()",
                ]
            )
            for c in service_classes:
                lines.append(
                    f"        self.{c['name'].lower()} = get_singleton({c['name']})"
                )
            svc_tuple = ", ".join(f"self.{c['name'].lower()}" for c in service_classes)
            lines.append(f'        self.__dict__["_services"] = ({svc_tuple},)')
        else:
            for c in service_classes:
                lines.append(f"        self.{c['name'].lower()} = {c['name']}()")
            svc_tuple = ", ".join(f"self.{c['name'].lower()}" for c in service_classes)
            lines.append(f'        self.__dict__["_services"] = ({svc_tuple},)')

        lines.extend(
            [
                "",
                "    def __getattr__(self, name: str) -> Any:",
                '        if name.startswith("__") and name.endswith("__"):',
                "            raise AttributeError(name)",
                '        for service in self.__dict__.get("_services", ()):',
                "            if hasattr(service, name):",
                "                return getattr(service, name)",
                f'        raise AttributeError(f"{{type(self).__name__}} has no attribute {{name!r}}")',
            ]
        )
    else:
        sut_type = service_classes[0]["name"] if service_classes else target_cls_name

    lines.extend(
        [
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
        ]
    )

    # Transitions for methods across all service classes
    transition_counter = 1
    for sc in service_classes:
        cls_name = sc["name"]
        for m in sc["methods"]:
            mname = m["name"]
            arg_info = m.get(
                "arg_info", [{"name": a, "type": "Any"} for a in m["args"]]
            )
            ret_type = m.get("return_type", "Any")
            fn_name = (
                mname if method_counts[mname] == 1 else f"{cls_name.lower()}_{mname}"
            )
            lines.extend(
                [
                    "",
                    f"    @transition({cls_name}.{mname})",
                    f"    def {fn_name}(",
                    "        self,",
                ]
            )
            for ai in arg_info:
                atype = ai["type"] if ai["type"] else "Any"
                lines.append(f"        {ai['name']}: {atype},")
            lines.extend(
                [
                    "    ) -> None:",
                    "        require(self.state.initialized)",
                ]
            )
            for ai in arg_info:
                dom_expr = _default_domain_arg(ai["name"], ai.get("type", ""))
                lines.append(f"        require_arg({ai['name']}, {dom_expr})")
            call_args = ", ".join(ai["name"] for ai in arg_info)
            if ret_type in ("None", "NoneType"):
                lines.extend(
                    [
                        f"        ret = self.inner_{fn_name}({call_args})",
                        "        assert ret is None",
                        "        return ret",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"        ret: {ret_type} = self.inner_{fn_name}({call_args})",
                        "        assert ret is not None",
                        "        return ret",
                    ]
                )
            lines.extend(
                [
                    "",
                    f"    def inner_{fn_name}(",
                    "        self,",
                ]
            )
            for ai in arg_info:
                atype = ai["type"] if ai["type"] else "Any"
                lines.append(f"        {ai['name']}: {atype},")
            if ret_type in ("None", "NoneType"):
                lines.extend(
                    [
                        "    ) -> None:",
                        "        return None",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"    ) -> {ret_type}:",
                        f"        return _unimplemented_transition('{fn_name}')",
                    ]
                )
            transition_counter += 1

    # Transitions for properties across service classes
    for sc in service_classes:
        cls_name = sc["name"]
        for prop in sc.get("properties", []):
            fn_name = prop if method_counts[prop] == 0 else f"{cls_name.lower()}_{prop}"
            lines.extend(
                [
                    "",
                    f'    @transition(name="{prop}")',
                    f"    def {fn_name}(self) -> Any:",
                    "        require(self.state.initialized)",
                    f"        ret: Any = self.inner_{fn_name}()",
                    "        assert ret is not None",
                    "        return ret",
                    "",
                    f"    def inner_{fn_name}(self) -> Any:",
                    f"        return _unimplemented_transition('{fn_name}')",
                ]
            )
            transition_counter += 1

    # Seeding transition
    lines.extend(
        [
            "",
            "    @transition.seeding",
            "    def seed_initial(self) -> None:",
            '        """Seed state machine state for fake initialization."""',
            "        self.state.initialized = True",
        ]
    )

    lines.extend(
        [
            "",
            "",
            f"proto = {sm_cls_name}()",
            "",
            "",
            "# ==============================================================================",
            "# 2. State Machine Proto & Fakes",
            "# ==============================================================================",
            "",
        ]
    )

    clean_stem = impl_stem.replace("_impl", "")
    fake_cls_name = f"Fake{pascal_name}"
    lines.append(f"{fake_cls_name} = synthesize_fake({sm_cls_name})")
    lines.append("")
    if len(service_classes) > 1:
        fake_ret_type = f"Tuple[{', '.join(c['name'] for c in service_classes)}]"
        lines.extend(
            [
                f"def make_{clean_stem}_fakes(",
                f"    state: Optional[{state_cls_name}] = None,",
                f") -> {fake_ret_type}:",
                f'    """Synthesizes fake instances for component services sharing model state."""',
                f"    fake = {fake_cls_name}(state=state or {state_cls_name}())",
                f"    return (",
                f"        " + ",\n        ".join("fake" for _ in service_classes) + ",",
                f"    )",
            ]
        )
    else:
        single_cls = service_classes[0]["name"] if service_classes else target_cls_name
        lines.extend(
            [
                f"def make_{clean_stem}_fake(",
                f"    state: Optional[{state_cls_name}] = None,",
                f") -> {single_cls}:",
                f'    """Synthesizes fake instance for {single_cls}."""',
                f"    return {fake_cls_name}(state=state or {state_cls_name}())",
            ]
        )

    lines.extend(
        [
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
        ]
    )

    if has_singleton:
        lines.extend(
            [
                "        self.registry = LifecycleRegistry()",
            ]
        )
        if init_aliases:
            for alias in init_aliases.values():
                lines.append(f"        {alias}(self.registry)")
        else:
            lines.append("        __initialize__(self.registry)")
        lines.extend(
            [
                "        self.phase_scope = enter_phase(system, registry=self.registry)",
                "        self.phase_scope.__enter__()",
            ]
        )
        if len(service_classes) > 1:
            for c in service_classes:
                lines.append(
                    f"        self.{c['name'].lower()} = get_singleton({c['name']})"
                )
            svc_dict = ", ".join(
                f"{c['name']}: self.{c['name'].lower()}" for c in service_classes
            )
            lines.append(f"        self.sm = {sm_cls_name}(singletons={{{svc_dict}}})")
            for c in service_classes:
                lines.append(
                    f"        self.checked_{c['name'].lower()} = self.sm.as_checked({c['name']}, self.{c['name'].lower()})"
                )
        else:
            lines.append(f"        self.real = get_singleton({target_cls_name})")
            lines.append(
                f"        self.sm = {sm_cls_name}(singletons={{{target_cls_name}: self.real}})"
            )
            lines.append(
                f"        self.checked = self.sm.as_checked({target_cls_name}, self.real)"
            )
        lines.extend(
            [
                "",
                "    def tearDown(self) -> None:",
                "        self.phase_scope.__exit__(None, None, None)",
            ]
        )
    else:
        if len(service_classes) > 1:
            for c in service_classes:
                lines.append(f"        self.{c['name'].lower()} = {c['name']}()")
            svc_dict = ", ".join(
                f"{c['name']}: self.{c['name'].lower()}" for c in service_classes
            )
            lines.append(f"        self.sm = {sm_cls_name}(singletons={{{svc_dict}}})")
            for c in service_classes:
                lines.append(
                    f"        self.checked_{c['name'].lower()} = self.sm.as_checked({c['name']}, self.{c['name'].lower()})"
                )
        else:
            lines.append(f"        self.real = {target_cls_name}()")
            lines.append(
                f"        self.sm = {sm_cls_name}(singletons={{{target_cls_name}: self.real}})"
            )
            lines.append(
                f"        self.checked = self.sm.as_checked({target_cls_name}, self.real)"
            )

    lines.extend(
        [
            "",
            "    def test_real_conformance(self) -> None:",
            "        # Drive scenarios via self.checked.<method>(*args) or self.sm.dispatch_transition('<transition_name>', *args).",
            "        # Operational postconditions and invariants are verified automatically by ensure(...);",
            "        # fixed scenario tests should contain no redundant manual self.assertEqual/assertTrue assertions.",
            f'        self.fail("Test{pascal_name}ImplReal.test_real_conformance must be implemented with concrete scenarios.")',
        ]
    )

    lines.extend(
        [
            "",
            "",
            "# ==============================================================================",
            "# 4. Hypothesis Stateful Fuzzing",
            "# ==============================================================================",
            "",
        ]
    )

    if len(service_classes) > 1:
        lines.extend(
            [
                f"def make_sut() -> {sut_cls_name}:",
                f"    return {sut_cls_name}()",
            ]
        )
    else:
        single_cls = service_classes[0]["name"] if service_classes else target_cls_name
        lines.extend(
            [
                f"def make_sut() -> {single_cls}:",
            ]
        )
        if has_singleton:
            lines.extend(
                [
                    "    registry = LifecycleRegistry()",
                ]
            )
            if init_aliases:
                for alias in init_aliases.values():
                    lines.append(f"    {alias}(registry)")
            else:
                lines.append("    __initialize__(registry)")
            lines.extend(
                [
                    "    scope = enter_phase(system, registry=registry)",
                    "    scope.__enter__()",
                    f"    return get_singleton({single_cls})",
                ]
            )
        else:
            lines.extend(
                [
                    f"    return {single_cls}()",
                ]
            )

    lines.extend(
        [
            "",
            "",
            f"{pascal_name}FuzzTest = compile_hypothesis_test_case(",
            "    proto=proto,",
            "    sut_factory=make_sut,",
            "    initial_state_factory=proto.make_initial_state,",
            f'    name="{pascal_name}FuzzTest",',
            ")",
            "",
        ]
    )

    return "\n".join(lines)


def _resolve_lib_dir_and_pkg(
    module_path: str, user_lib_pkg: str | None = None
) -> tuple[str, str]:
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
            from autofab_py.support.lib import app_info
        except Exception:
            import app_info  # type: ignore
    config_markers = getattr(app_info, "get_config_filenames", lambda: ())() + getattr(
        app_info, "get_roles_filenames", lambda: ()
    )()
    fallback_root = ""
    while curr and curr != os.path.dirname(curr):
        if os.path.isfile(os.path.join(curr, "pyproject.toml")):
            repo_root = curr
            break
        if any(os.path.isfile(os.path.join(curr, marker)) for marker in config_markers):
            fallback_root = curr
        curr = os.path.dirname(curr)
    if not repo_root:
        repo_root = fallback_root

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
            sys.stderr.write(
                f"Cannot scaffold {args.module_path}: specification .pyi not found\n"
            )
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
            lib_dir=lib_dir,
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

    if (
        is_uninitialized_pretense_module(content)
        and "_unimplemented_transition" not in content
    ):
        sys.stderr.write(
            f"{args.module_path} is uninitialized (missing State dataclass or TestCase classes). "
            f"Consult your Companion Guide (autofab_py/guides/pretense.md) for required structure.\n"
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
        basename = os.path.basename(pyi_path)
        is_interface = not basename.endswith("_impl.pyi")
    elif args.module_path:
        stem = os.path.basename(args.module_path)
        is_interface = not stem.endswith("_impl_pretense.py")

    struct_errs = check_pretense_structure(
        tree, args.module_path, is_interface=is_interface
    )
    all_errors.extend(struct_errs)

    assert_errs = check_single_argument_assertions(tree, args.module_path)
    all_errors.extend(assert_errs)

    import_errs = check_pretense_imports(
        content, pyi_path, is_impl=not is_interface, file_path=args.module_path
    )
    all_errors.extend(import_errs)

    test_import_errs = check_test_imports(lib_pkg, args.module_path)
    all_errors.extend(test_import_errs)

    rel_import_errs = check_no_relative_parent_imports(args.module_path, tree=tree)
    all_errors.extend(rel_import_errs)

    bare_parts_errs = check_no_bare_parts_imports(args.module_path, tree=tree)
    all_errors.extend(bare_parts_errs)

    private_import_errs = check_no_private_imports(args.module_path, tree=tree)
    all_errors.extend(private_import_errs)

    tautology_errs = check_tautological_assertions(
        args.module_path, tree=tree, check_empty=True
    )
    all_errors.extend(tautology_errs)

    no_error_test_errs = check_no_error_testing(args.module_path, tree=tree)
    all_errors.extend(no_error_test_errs)

    no_try_except_errs = check_no_try_except_in_tests(args.module_path, tree=tree)
    all_errors.extend(no_try_except_errs)

    lifecycle_leak_errs = check_no_lifecycle_scope_leaks(args.module_path, tree=tree)
    all_errors.extend(lifecycle_leak_errs)

    sys_module_errs = check_no_sys_modules_tampering(args.module_path, tree=tree)
    all_errors.extend(sys_module_errs)

    probe_errs = check_no_top_level_probes(
        args.module_path, tree=tree, error_code="PRE_LINT_NO_TOP_LEVEL_PROBE"
    )
    all_errors.extend(probe_errs)

    outcome_errs = check_transition_outcomes(tree, args.module_path)
    all_errors.extend(outcome_errs)

    lifted_errs = check_lifted_expr_usage(
        tree, args.module_path, is_impl=not is_interface
    )
    all_errors.extend(lifted_errs)

    sentinel_errs = check_no_residual_sentinels(tree, args.module_path)
    all_errors.extend(sentinel_errs)

    disambig_errs = check_multi_transition_disambiguation(tree, args.module_path)
    all_errors.extend(disambig_errs)

    algo_sm_errs = check_no_algorithmic_state_machines(tree, args.module_path)
    all_errors.extend(algo_sm_errs)

    frozen_errs = check_no_frozen_exceptions(args.module_path)
    all_errors.extend(frozen_errs)

    skip_errs = check_banned_skips(
        args.module_path, tree=tree, error_code="PRE_LINT_NO_SKIP"
    )
    all_errors.extend(skip_errs)

    pre_seeding_errs = check_no_pre_seeding(tree, args.module_path)
    all_errors.extend(pre_seeding_errs)

    call_target_iface_errs = check_no_call_target_in_interface(
        tree, args.module_path, is_interface=is_interface
    )
    all_errors.extend(call_target_iface_errs)

    no_super_errs = check_no_super_in_impl_inner(
        tree, args.module_path, is_impl=not is_interface
    )
    all_errors.extend(no_super_errs)

    no_domain_any_errs = check_no_domain_any(tree, args.module_path)
    all_errors.extend(no_domain_any_errs)

    no_raises_errs = check_no_raises_in_test_cases(tree, args.module_path)
    all_errors.extend(no_raises_errs)

    assert_raises_errs = check_no_assert_raises(tree, args.module_path)
    all_errors.extend(assert_raises_errs)

    no_raises_error_errs = check_no_raises_for_errors(tree, args.module_path)
    all_errors.extend(no_raises_error_errs)

    require_error_errs = check_require_sticks_to_error(tree, args.module_path)
    all_errors.extend(require_error_errs)

    require_env_errs = check_require_env_sticks_to_exception(tree, args.module_path)
    all_errors.extend(require_env_errs)

    require_env_state_errs = check_require_env_depends_on_env_state(tree, args.module_path)
    all_errors.extend(require_env_state_errs)

    impl_env_bind_errs = check_impl_env_state_bindings(tree, args.module_path)
    all_errors.extend(impl_env_bind_errs)

    no_raise_sm_errs = check_no_raise_in_state_machine(tree, args.module_path)
    all_errors.extend(no_raise_sm_errs)

    direct_real_errs = check_no_direct_real_access(tree, args.module_path)
    all_errors.extend(direct_real_errs)

    direct_sm_errs = check_no_direct_sm_access_in_real_tests(tree, args.module_path)
    all_errors.extend(direct_sm_errs)

    allowed_classes_errs = check_impl_allowed_classes_only(
        tree, args.module_path, is_impl=not is_interface
    )
    all_errors.extend(allowed_classes_errs)

    terminal_violating_errs = check_terminal_violating(tree, args.module_path)
    all_errors.extend(terminal_violating_errs)

    violating_error_errs = check_violating_sticks_to_error(tree, args.module_path)
    all_errors.extend(violating_error_errs)

    multi_iface_errs = check_multi_interface_inheritance(tree, args.module_path)
    all_errors.extend(multi_iface_errs)

    pyi_elements = (
        extract_pyi_elements(pyi_path)
        if pyi_path and os.path.isfile(pyi_path)
        else None
    )

    coverage_errs = check_interface_transition_coverage(
        tree, args.module_path, is_interface=is_interface, pyi_elements=pyi_elements
    )
    all_errors.extend(coverage_errs)
    target_internal_errs = check_pretense_target_internals(
        tree, args.module_path, pyi_elements=pyi_elements
    )
    all_errors.extend(target_internal_errs)

    proto_prop_errs = check_transition_protocol_properties(
        tree, args.module_path, pyi_elements=pyi_elements
    )
    all_errors.extend(proto_prop_errs)

    placeholder_errs = check_no_scaffold_placeholders(tree, args.module_path)
    all_errors.extend(placeholder_errs)

    type_ignore_errs = check_type_ignore(args.module_path)
    all_errors.extend(type_ignore_errs)

    pragma_errs = check_no_pragma_no_cover(args.module_path)
    all_errors.extend(pragma_errs)

    local_exc_errs = check_no_local_exception_class(tree, args.module_path)
    all_errors.extend(local_exc_errs)

    module_sut_errs = check_no_module_level_sut(tree, args.module_path)
    all_errors.extend(module_sut_errs)

    violating_iface_errs = check_no_violating_in_interface(
        tree, args.module_path, is_interface=is_interface
    )
    all_errors.extend(violating_iface_errs)

    unbound_factory_errs = check_unbound_initial_state_factory(tree, args.module_path)
    all_errors.extend(unbound_factory_errs)

    setup_order_errs = check_setup_super_order(tree, args.module_path)
    all_errors.extend(setup_order_errs)

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
