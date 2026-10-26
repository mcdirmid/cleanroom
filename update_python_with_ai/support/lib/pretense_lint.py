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
        check_syntax,
        find_spec_pyi,
        module_file,
        module_stem,
        package_of,
        read_text,
        write_text,
    )
except ImportError:
    from update_python_with_ai.support.lib.build_lint_common import (  # type: ignore
        check_syntax,
        find_spec_pyi,
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
    if "<TargetClass>" in content or "<target_impl>" in content:
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
                        args = [a.arg for a in item.args.args if a.arg != "self"]
                        methods.append({"name": item.name, "args": args})

            classes.append({
                "name": node.name,
                "methods": methods,
                "properties": properties,
            })

    return {"classes": classes, "has_singleton": has_singleton}


def _default_arg_val(arg_name: str) -> str:
    """Returns a realistic default argument value representation based on parameter name."""
    lower = arg_name.lower()
    if any(k in lower for k in ("id", "name", "key", "path", "target", "stem", "file")):
        return f'"sample_{arg_name}"'
    if any(k in lower for k in ("count", "num", "limit", "retries", "priority", "index")):
        return "1"
    if any(k in lower for k in ("flag", "is_", "has_", "enabled", "force")):
        return "True"
    if any(k in lower for k in ("data", "payload", "items", "elements", "dependencies", "dependents")):
        return "[]"
    if any(k in lower for k in ("config", "options", "metadata", "kwargs", "mapping", "attributes")):
        return "{}"
    return "None"


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
        "from pretense.compiler import compile_hypothesis_test_case",
        "from pretense.proto import StateMachineProto",
        "from pretense.sentinels import NotBound, NotBoundType, Outcome, Value",
    ]

    if has_singleton:
        lines.append("from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system")

    # Import target classes from lib package
    import_module = f"{lib_pkg}.{impl_stem}" if lib_pkg else impl_stem
    cnames = [c["name"] for c in service_classes] if service_classes else [target_cls_name]
    import_symbols = list(cnames)
    if has_singleton:
        import_symbols.append("__initialize__")
    lines.append(f"from {import_module} import {', '.join(import_symbols)}")

    lines.extend([
        "",
        "",
        "# ==============================================================================",
        "# 1. State Machine Specification (Model & Transitions)",
        "# ==============================================================================",
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
        f"proto = StateMachineProto[{state_cls_name}]()",
    ])

    # Transitions for methods across all service classes
    transition_counter = 1
    for sc in service_classes:
        cls_name = sc["name"]
        for m in sc["methods"]:
            mname = m["name"]
            margs = m["args"]
            fn_name = mname if method_counts[mname] == 1 else f"{cls_name.lower()}_{mname}"
            lines.extend([
                "",
                "",
                "# ------------------------------------------------------------------------------",
                f"# 1.{transition_counter} {cls_name}.{mname}",
                "# ------------------------------------------------------------------------------",
                "",
                f"@proto.transition({cls_name}.{mname})",
                f"def {fn_name}(): pass",
                "",
                f"@{fn_name}.arguments",
                f"def _(",
                f"    state: {state_cls_name},",
                f"    this: Any,",
            ])
            for arg in margs:
                lines.append(f"    {arg}: Any | NotBoundType = NotBound,")
            lines.append(f") -> Optional[Tuple[Any, ...]]:")
            lines.append(f"    # Replace with strategy or default argument resolution")
            if margs:
                arg_tuples = ", ".join(
                    f"({a} if not isinstance({a}, NotBoundType) else {_default_arg_val(a)})"
                    for a in margs
                )
                lines.append(f"    return ({arg_tuples},)")
            else:
                lines.append(f"    return ()")

            lines.extend([
                "",
                f"@{fn_name}.returns",
                f"def _(",
                f"    state: {state_cls_name},",
                f"    this: Any,",
            ])
            for arg in margs:
                lines.append(f"    {arg}: Any,")
            lines.extend([
                f"    outcome: object = NotBound,",
                f") -> Optional[Outcome[Any]]:",
                f"    if outcome is NotBound:",
                f"        return Value(None)",
                f"    return outcome if isinstance(outcome, Outcome) else Value(outcome)",
                "",
                f"@{fn_name}.provide",
                f"def _(",
                f"    state: {state_cls_name},",
                f"    this: Any,",
            ])
            for arg in margs:
                lines.append(f"    {arg}: Any,")
            lines.extend([
                f"    result: Any,",
                f") -> None:",
                f"    # Mutate model state reflecting operation postconditions",
                f"    pass",
            ])
            transition_counter += 1

    lines.extend([
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
            f"    state: {state_cls_name},",
            f") -> {fake_ret_type}:",
            f'    """Synthesizes fake instances for component services sharing model state."""',
            f"    sm = proto.make_state_machine(state)",
            f"    return (",
            f"        {fake_tuple_elems},",
            f"    )",
        ])
    else:
        single_cls = service_classes[0]["name"] if service_classes else target_cls_name
        lines.extend([
            f"def make_{clean_stem}_fake(",
            f"    state: {state_cls_name},",
            f") -> {single_cls}:",
            f'    """Synthesizes fake instance for {single_cls}."""',
            f"    return proto.make_state_machine(state).as_fake({single_cls})",
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
        for m in sc["methods"]:
            mname = m["name"]
            fn_name = mname if method_counts[mname] == 1 else f"{cls_name.lower()}_{mname}"
            lines.extend([
                "",
                f"    def test_fake_{fn_name}(self) -> None:",
                f"        # Test transition execution against synthesized fake",
                f"        pass",
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
        else:
            lines.append(f"        self.real = get_singleton({target_cls_name})")
        lines.extend([
            "",
            "    def tearDown(self) -> None:",
            "        self.phase_scope.__exit__(None, None, None)",
        ])
    else:
        if len(service_classes) > 1:
            for c in service_classes:
                lines.append(f"        self.{c['name'].lower()} = {c['name']}()")
        else:
            lines.append(f"        self.real = {target_cls_name}()")

    lines.extend([
        "",
        "    def test_real_conformance(self) -> None:",
    ])
    if len(service_classes) > 1:
        for c in service_classes:
            lines.append(f"        self.assertIsNotNone(self.{c['name'].lower()})")
    else:
        lines.append("        self.assertIsNotNone(self.real)")

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
    syntax_errs = check_syntax(content)
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
        sys.stderr.write(f"Syntax error: {e}\n")
        return 1

    struct_errs = check_pretense_structure(tree)
    if struct_errs:
        for err in struct_errs:
            sys.stderr.write(f"{err}\n")
        return 1

    import_errs = check_pretense_imports(content, pyi_path)
    if import_errs:
        for err in import_errs:
            sys.stderr.write(f"{err}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
