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
        check_no_frozen_exceptions,
        check_no_private_imports,
        check_no_sys_modules_tampering,
        check_syntax,
        check_tautological_assertions,
        find_spec_pyi,
        format_syntax_error,
        module_file,
        module_stem,
        package_of,
        read_text,
        write_text,
    )
except ImportError:
    from update_python_with_ai.support.lib.build_lint_common import (  # type: ignore
        check_no_frozen_exceptions,
        check_no_private_imports,
        check_no_sys_modules_tampering,
        check_syntax,
        check_tautological_assertions,
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
                    if base_id in ("TestCase", "unittest.TestCase"):
                        has_test = True
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and "FuzzTest" in target.id:
                        has_test = True
        return not (has_state and has_test)
    except SyntaxError:
        return False


def check_pretense_structure(tree: ast.AST) -> list[str]:
    """Validates that the pretense module defines model state, proto/transitions, and test cases."""
    errors: list[str] = []
    classes = [n for n in getattr(tree, "body", []) if isinstance(n, ast.ClassDef)]
    state_classes = [c for c in classes if c.name.endswith("State")]
    if not state_classes:
        errors.append("Missing Pretense model state class (must define a dataclass ending with 'State').")

    test_classes = []
    for c in classes:
        for base in c.bases:
            base_id = ""
            if isinstance(base, ast.Name):
                base_id = base.id
            elif isinstance(base, ast.Attribute):
                base_id = base.attr
            if base_id in ("TestCase", "unittest.TestCase"):
                test_classes.append(c)

    # Also check for compiled hypothesis test case assignment
    compiled_tests = []
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and "FuzzTest" in target.id:
                    compiled_tests.append(target.id)

    if not test_classes and not compiled_tests:
        errors.append(
            "Missing Pretense test cases: module must define at least one unittest.TestCase class or compiled Hypothesis test case."
        )

    return errors


def check_pretense_imports(content: str, pyi_path: str | None = None) -> list[str]:
    """Validates required Pretense imports and target library imports."""
    errors: list[str] = []
    if "pretense" not in content:
        errors.append("Missing pretense imports (must import from pretense.proto, pretense.sentinels, etc.).")
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

        has_raises = False
        has_returns = False
        raises_line = 0

        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if child.func.attr == "raises":
                    has_raises = True
                    raises_line = child.lineno
                    for kw in child.keywords:
                        if kw.arg not in ("match",):
                            errors.append(
                                f"{file_path}:{child.lineno}: error: Invalid keyword argument '{kw.arg}' in ctx.raises(...) for transition '{node.name}'. "
                                f"TransitionContext.raises only accepts (exc_type, match='')."
                            )
                elif child.func.attr == "returns":
                    has_returns = True

        if has_raises and has_returns:
            errors.append(
                f"{file_path}:{raises_line}: error: Transition '{node.name}' declares both ctx.raises(...) and ctx.returns(...). "
                f"These outcome declarations are mutually exclusive: use ctx.raises(...) for transitions that unconditionally raise an exception, "
                f"or return Raised(...) dynamically from ctx.returns(...)."
            )
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
            if val.func.attr in ("set", "range", "regex", "perturb", "of"):
                return True
            if val.func.attr == "type":
                return False
        for kw in val.keywords:
            if kw.arg == "validator":
                return not _is_trivial_recognizer(kw)
        return False
    if isinstance(val, (ast.Set, ast.List, ast.Tuple, ast.Constant)):
        return True
    return False


def check_multi_transition_disambiguation(tree: ast.AST, file_path: str = "") -> list[str]:
    """Flags multiple transitions for the same method that have undifferentiated requirements and recognizers."""
    errors: list[str] = []
    classes = [n for n in getattr(tree, "body", []) if isinstance(n, ast.ClassDef)]

    for cls in classes:
        target_map: dict[str, list[tuple[str, int, bool, bool]]] = {}

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

            has_custom_req = False
            has_custom_rec = False

            for child in ast.walk(item):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if child.func.attr == "requires":
                        if not _is_trivial_requirement(child):
                            has_custom_req = True
                    elif child.func.attr == "arguments":
                        for arg in child.args:
                            if _is_discriminating_domain_expr(arg):
                                has_custom_rec = True
                        for kw in child.keywords:
                            if kw.arg == "recognize":
                                if not _is_trivial_recognizer(kw):
                                    has_custom_rec = True
                            elif kw.arg not in ("generate", "recognize", "fn"):
                                if _is_discriminating_domain_expr(kw.value):
                                    has_custom_rec = True

            target_map.setdefault(target_name, []).append((item.name, item.lineno, has_custom_req, has_custom_rec))

        for target_name, transitions in target_map.items():
            if len(transitions) <= 1:
                continue

            undifferentiated = [t for t in transitions if not t[2] and not t[3]]
            if len(undifferentiated) > 1:
                first_name, _, _, _ = undifferentiated[0]
                for fn_name, lineno, _, _ in undifferentiated[1:]:
                    errors.append(
                        f"{file_path}:{lineno}: error: Multiple transitions for '{target_name}' ('{first_name}', '{fn_name}') "
                        f"have undifferentiated preconditions and argument recognizers. In Pretense Fake mode, multiple transitions "
                        f"for the same method must be partitioned using distinct ctx.requires(...) conditions or discriminative "
                        f"ctx.arguments(...) domain validators to prevent AmbiguousTransitionError."
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
                fn_id == "check"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value is False
                and len(node.args) > 1
                and isinstance(node.args[1], ast.Constant)
                and "postconditions must be specified in ctx.ensures" in str(node.args[1].value)
            ):
                errors.append(
                    f"{file_path}:{node.lineno}: error: transition postconditions still contain scaffold placeholder 'check(False, ...)'. "
                    f"You must specify concrete postcondition invariants in ctx.ensures."
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

            classes.append({
                "name": node.name,
                "methods": methods,
                "properties": properties,
            })

    return {"classes": classes, "has_singleton": has_singleton}


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
) -> str:
    """Generates canonical 5-section Pretense state machine, fake, unit tests, and fuzzing skeleton."""
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

    pascal_name = "".join(p.capitalize() for p in impl_stem.replace("_impl", "").split("_"))
    if not pascal_name:
        pascal_name = "Target"

    if len(service_classes) == 1:
        target_cls_name = service_classes[0]["name"]
    else:
        target_cls_name = pascal_name

    state_cls_name = f"{pascal_name}State"

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
        "from pretense import Domain, StateMachine, TransitionContext, transition",
        "from pretense.compiler import compile_hypothesis_test_case",
        "from pretense.sentinels import NotBound, NotBoundType, Outcome, Value",
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
            arg_types = ", ".join(ai["type"] if ai["type"] else "Any" for ai in arg_info)
            ctx_p = f"[{arg_types}]" if arg_info else "[]"
            lines.extend([
                "",
                f"    @transition({cls_name}.{mname})",
                f"    def {fn_name}(",
                "        self,",
                f"        ctx: TransitionContext[{cls_name}, {ctx_p}, {ret_type}],",
                "    ) -> None:",
                '        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))',
            ])
            if arg_info:
                lines.append("        ctx.arguments(")
                for ai in arg_info:
                    dom_expr = _default_domain_arg(ai["name"], ai.get("type", ""))
                    lines.append(f"            {ai['name']}={dom_expr},")
                lines.append("        )")
            else:
                lines.append("        ctx.arguments()")
            rec_args = ", ".join(f"{ai['name']}=None" for ai in arg_info) if arg_info else ""
            lines.append(f"        ctx.returns(lambda {rec_args}: _unimplemented_transition('{fn_name}'))")
            lines.append(
                f"        ctx.ensures(\n"
                f"            lambda res, target, check{', ' + rec_args if rec_args else ''}: (\n"
                f"                check(False, \"Pretense transition '{fn_name}' postconditions must be specified in ctx.ensures\"),\n"
                f"            )\n"
                f"        )"
            )
            lines.append(f"        ctx.update(lambda res{', ' + rec_args if rec_args else ''}: None)")
            transition_counter += 1

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
    if len(service_classes) > 1:
        fake_ret_type = f"Tuple[{', '.join(c['name'] for c in service_classes)}]"
        fake_tuple_elems = ",\n        ".join(f"sm.as_fake({c['name']})" for c in service_classes)
        lines.extend([
            f"def make_{clean_stem}_fakes(",
            f"    state: Optional[{state_cls_name}] = None,",
            f") -> {fake_ret_type}:",
            f'    """Synthesizes fake instances for component services sharing model state."""',
            f"    sm = {sm_cls_name}(state or {state_cls_name}())",
            f"    return (",
            f"        {fake_tuple_elems},",
            f"    )",
        ])
    else:
        single_cls = service_classes[0]["name"] if service_classes else target_cls_name
        lines.extend([
            f"def make_{clean_stem}_fake(",
            f"    state: Optional[{state_cls_name}] = None,",
            f") -> {single_cls}:",
            f'    """Synthesizes fake instance for {single_cls}."""',
            f"    sm = {sm_cls_name}(state or {state_cls_name}())",
            f"    return sm.as_fake({single_cls})",
        ])

    lines.extend([
        "",
        "",
        "# ==============================================================================",
        "# 3. Fake Unit Tests",
        "# ==============================================================================",
        "",
        f"class Test{pascal_name}Unit(unittest.TestCase):",
        f'    """Verifies that synthesized fakes conform to state machine specification."""',
        "",
        "    def setUp(self) -> None:",
        f"        self.state = {state_cls_name}()",
    ])

    if len(service_classes) > 1:
        setup_vars = ", ".join(f"self.{c['name'].lower()}" for c in service_classes)
        lines.append(f"        {setup_vars} = make_{clean_stem}_fakes(self.state)")
    else:
        lines.append(f"        self.fake = make_{clean_stem}_fake(self.state)")

    lines.extend([
        "",
        "    def test_fake_initial_state(self) -> None:",
        "        self.assertTrue(self.state.initialized)",
    ])

    for sc in service_classes:
        cls_name = sc["name"]
        target_var = f"self.{cls_name.lower()}" if len(service_classes) > 1 else "self.fake"
        for m in sc["methods"]:
            mname = m["name"]
            fn_name = mname if method_counts[mname] == 1 else f"{cls_name.lower()}_{mname}"
            lines.extend([
                "",
                f"    def test_fake_{fn_name}(self) -> None:",
                f"        # TODO: Implement transition verification against synthesized fake adapter",
                f'        self.fail("Test{pascal_name}Unit.test_fake_{fn_name} must be implemented with concrete inputs and assertions.")',
            ])

    lines.extend([
        "",
        "",
        "# ==============================================================================",
        "# 4. Real Implementation Tests",
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
        else:
            lines.append(f"        self.real = get_singleton({target_cls_name})")
            lines.append(f"        self.sm = {sm_cls_name}(singletons={{{target_cls_name}: self.real}})")
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
        else:
            lines.append(f"        self.real = {target_cls_name}()")
            lines.append(f"        self.sm = {sm_cls_name}(singletons={{{target_cls_name}: self.real}})")

    lines.extend([
        "",
        "    def test_real_conformance(self) -> None:",
        "        # Drive scenarios via self.sm.dispatch_transition('<transition_name>', *args).",
        "        # Operational postconditions and invariants are verified automatically by ctx.ensures(...);",
        "        # fixed scenario tests should contain no redundant manual self.assertEqual/assertTrue assertions.",
        f'        self.fail("Test{pascal_name}ImplReal.test_real_conformance must be implemented with concrete scenarios via self.sm.dispatch_transition(...).")',
    ])

    lines.extend([
        "",
        "",
        "# ==============================================================================",
        "# 5. Hypothesis Stateful Fuzzing",
        "# ==============================================================================",
        "",
    ])

    if len(service_classes) > 1:
        sut_cls_name = f"{pascal_name}SUT"
        lines.extend([
            f"class {sut_cls_name}:",
            f'    """Aggregate SUT exposing component services for Hypothesis fuzzing."""',
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
            "",
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


def _resolve_lib_pkg(module_path: str, user_lib_pkg: str | None = None) -> str:
    """Resolves full package name for the library directory."""
    if user_lib_pkg:
        return user_lib_pkg.replace("/", ".").strip(".")

    abs_mod = os.path.abspath(module_path)
    parent_dir = os.path.dirname(abs_mod)
    # Check if pretense directory
    if os.path.basename(parent_dir) == "pretense":
        part_dir = os.path.dirname(parent_dir)
    else:
        part_dir = parent_dir

    curr = part_dir
    repo_root = ""
    while curr and curr != os.path.dirname(curr):
        if any(
            os.path.isfile(os.path.join(curr, marker))
            for marker in ("cleanroom.toml", "pyproject.toml", "cleanroom_roles.toml")
        ):
            repo_root = curr
            break
        curr = os.path.dirname(curr)

    if repo_root:
        lib_dir = os.path.join(part_dir, "lib")
        rel = os.path.relpath(lib_dir, repo_root).replace("\\", "/")
        return rel.replace("/", ".")
    return "lib"


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
    args = ap.parse_args()

    if args.module_path is None:
        return 0

    stem = module_stem(args.module_path)
    impl_stem = stem[:-9] if stem.endswith("_pretense") else stem
    dir_name = os.path.dirname(args.module_path)

    pyi_path = args.pyi
    if not pyi_path or not os.path.isfile(pyi_path):
        pyi_path = find_spec_pyi(args.module_path)

    lib_pkg = _resolve_lib_pkg(args.module_path, args.lib_pkg)

    if args.scaffold:
        if not pyi_path or not os.path.isfile(pyi_path):
            sys.stderr.write(f"Cannot scaffold {args.module_path}: specification .pyi not found\n")
            return 1
        skeleton = generate_pretense_scaffold(
            pyi_path=pyi_path,
            stem=stem,
            impl_stem=impl_stem,
            lib_pkg=lib_pkg,
            impl_path=args.impl or None,
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

    if is_uninitialized_pretense_module(content):
        sys.stderr.write(
            f"{args.module_path} is uninitialized (missing State dataclass or TestCase classes). "
            f"Consult your Companion Guide (update_python_with_ai/guides/pretense.md) for required structure.\n"
        )
        return 1

    try:
        tree = ast.parse(content, filename=args.module_path)
    except SyntaxError as e:
        sys.stderr.write(f"{format_syntax_error(args.module_path, e, content)}\n")
        return 1

    all_errors: list[str] = []

    struct_errs = check_pretense_structure(tree)
    all_errors.extend(struct_errs)

    import_errs = check_pretense_imports(content, pyi_path)
    all_errors.extend(import_errs)

    private_import_errs = check_no_private_imports(args.module_path, tree=tree)
    all_errors.extend(private_import_errs)

    tautology_errs = check_tautological_assertions(args.module_path, tree=tree, check_empty=True)
    all_errors.extend(tautology_errs)

    sys_module_errs = check_no_sys_modules_tampering(args.module_path, tree=tree)
    all_errors.extend(sys_module_errs)

    outcome_errs = check_transition_outcomes(tree, args.module_path)
    all_errors.extend(outcome_errs)

    sentinel_errs = check_no_residual_sentinels(tree, args.module_path)
    all_errors.extend(sentinel_errs)

    disambig_errs = check_multi_transition_disambiguation(tree, args.module_path)
    all_errors.extend(disambig_errs)

    algo_sm_errs = check_no_algorithmic_state_machines(tree, args.module_path)
    all_errors.extend(algo_sm_errs)

    frozen_errs = check_no_frozen_exceptions(args.module_path)
    all_errors.extend(frozen_errs)

    pyi_elements = extract_pyi_elements(pyi_path) if pyi_path and os.path.isfile(pyi_path) else None
    target_internal_errs = check_pretense_target_internals(tree, args.module_path, pyi_elements=pyi_elements)
    all_errors.extend(target_internal_errs)

    placeholder_errs = check_no_scaffold_placeholders(tree, args.module_path)
    all_errors.extend(placeholder_errs)

    if all_errors:
        for err in all_errors:
            sys.stderr.write(f"{err}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
