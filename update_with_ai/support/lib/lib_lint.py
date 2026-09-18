#!/usr/bin/env python3
"""lib_lint.py — maintain a module's pyright_library BUILD entry.

Usage: lib_lint.py <BUILD.bazel> <module.py> [--deps dep1,dep2,...]

Fixes (idempotent, add-only):
  - creates the BUILD file when it does not exist (load statement included),
  - adds the pyright load statement when missing,
  - adds the pyright_library target when missing,
  - adds any missing pyright_deps (existing entries are left in place).

The expected pyright_deps are the spec-graph-derived module names passed via
--deps (the module names corresponding to the spec's module_deps) plus the
transitive closure of the module's sibling imports: pyright must resolve
every module the target's files import, directly or transitively.
Exits 0 when the BUILD entry is maintained; exits 1 on unexpected errors.
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path

from build_lint_common import (
    build_module_resolution_map,
    check_dataclass_stubs,
    check_dead_code,
    check_exception_eating,
    check_framework_imports,
    check_impl_imports,
    check_lib_structure,
    check_public_types,
    check_sibling_imports,
    check_syntax,
    check_type_ignore,
    check_undeclared_imports,
    ensure_dependency_header,
    ensure_load,
    ensure_pip_load,
    ensure_target,
    extract_target_pyright_deps,
    find_spec_pyi,
    load_line,
    local_imports,
    module_file,
    module_stem,
    package_of,
    parse_dependency_header,
    parse_package_build_dependencies,
    parse_pyi_dependencies,
    parse_spec_build_dependencies,
    read_text,
    rewrite_lib_imports,
    transitive_closure,
    write_text,
)

RULE = "pyright_library"


def generate_asm_content(dir_name: str, raw_deps: list[str]) -> str:
    lines = [
        "from __future__ import annotations",
        "from typing import Optional",
        "from support.lib.lifecycle import LifecycleRegistry",
    ]
    dep_stems = [d.split(":")[-1] for d in raw_deps]
    for dep in sorted(dep_stems):
        if os.path.isfile(os.path.join(dir_name, f"{dep}.py")):
            lines.append(f"from . import {dep}")
        else:
            found = False
            for p in Path("update_with_ai/parts").glob(f"*/lib/{dep}.py"):
                domain = p.parent.parent.name
                lines.append(f"from update_with_ai.parts.{domain}.lib import {dep}")
                found = True
                break
            if not found:
                lines.append(f"from . import {dep}")
    lines.append("")
    lines.append("CONSTITUENTS = (")
    for dep in sorted(dep_stems):
        lines.append(f"    {dep},")
    lines.append(")")
    lines.append("")
    lines.append(
        "def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:"
    )
    lines.append("    for mod in CONSTITUENTS:")
    lines.append("        mod.__initialize__(registry)")
    lines.append("")
    lines.append("_initialize_ = __initialize__")
    lines.append("")
    return "\n".join(lines)


def is_uninitialized_module(content: str) -> bool:
    stripped = content.strip()
    if not stripped:
        return True
    if "<TargetClass>" in content:
        return True
    try:
        tree = ast.parse(content)
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        funcs = [
            n
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name != "__initialize__"
        ]
        if not classes and not funcs:
            return True
    except SyntaxError:
        if "<" in content and ">" in content:
            return True
    return False


def generate_lib_skeleton(pyi_path: str, stem: str) -> str:
    with open(pyi_path, "r", encoding="utf-8") as f:
        pyi_content = f.read()
    tree = ast.parse(pyi_content, filename=pyi_path)

    is_impl = stem.endswith("_impl")
    lines: list[str] = [
        "from __future__ import annotations",
    ]

    typing_names: set[str] = set()
    has_dataclass = False

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.module == "typing":
                for alias in node.names:
                    typing_names.add(alias.name)
        elif isinstance(node, ast.ClassDef):
            for dec in node.decorator_list:
                dec_name = None
                if isinstance(dec, ast.Name):
                    dec_name = dec.id
                elif isinstance(dec, ast.Attribute):
                    dec_name = dec.attr
                elif isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        dec_name = dec.func.id
                    elif isinstance(dec.func, ast.Attribute):
                        dec_name = dec.func.attr
                if dec_name in ("data_type", "dataclass"):
                    has_dataclass = True

    if is_impl:
        typing_names.add("Optional")

    if not is_impl and any(
        isinstance(node, ast.ClassDef)
        and any(
            (isinstance(b, ast.Name) and b.id == "Protocol")
            or (isinstance(b, ast.Attribute) and b.attr == "Protocol")
            for b in node.bases
        )
        for node in tree.body
    ):
        typing_names.add("Protocol")

    if typing_names:
        lines.append(f"from typing import {', '.join(sorted(typing_names))}")
    if has_dataclass:
        lines.append("from dataclasses import dataclass")
    if is_impl:
        lines.append(
            "from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton"
        )

    pyi_basename = os.path.basename(pyi_path)
    lines.append("")
    lines.append(f"# Requirements specified in {pyi_basename}")
    lines.append("")

    singleton_classes: list[tuple[str, list[str], str]] = []

    for node in tree.body:
        if hasattr(ast, "TypeAlias") and isinstance(node, ast.TypeAlias):
            lines.append(ast.unparse(node))
            lines.append("")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            lines.append(ast.unparse(node))
            lines.append("")
        elif isinstance(node, ast.ClassDef):
            cls_name = node.name
            dec_names: set[str] = set()
            tier_val = "system"
            has_explicit_dataclass = False
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    dec_names.add(dec.id)
                    if dec.id == "dataclass":
                        has_explicit_dataclass = True
                elif isinstance(dec, ast.Attribute):
                    dec_names.add(dec.attr)
                    if dec.attr == "dataclass":
                        has_explicit_dataclass = True
                elif isinstance(dec, ast.Call):
                    fn_name = (
                        dec.func.id
                        if isinstance(dec.func, ast.Name)
                        else getattr(dec.func, "attr", "")
                    )
                    dec_names.add(fn_name)
                    if fn_name == "dataclass":
                        has_explicit_dataclass = True
                    elif fn_name == "singleton_type" and dec.args:
                        arg0 = dec.args[0]
                        if isinstance(arg0, ast.Constant) and isinstance(
                            arg0.value, str
                        ):
                            tier_val = arg0.value

            is_dc = has_explicit_dataclass or "data_type" in dec_names
            is_proto = "poly_type" in dec_names or any(
                (isinstance(b, ast.Name) and b.id == "Protocol")
                or (isinstance(b, ast.Attribute) and b.attr == "Protocol")
                for b in node.bases
            )
            is_cls_singleton = is_impl or "singleton_type" in dec_names

            base_strs = [
                ast.unparse(b)
                for b in node.bases
                if ast.unparse(b) not in ("data_type",)
            ]

            if is_impl and is_cls_singleton:
                if "Singleton" not in base_strs:
                    base_strs.append("Singleton")
                singleton_classes.append(
                    (
                        cls_name,
                        [b for b in base_strs if b != "Singleton"],
                        tier_val,
                    )
                )

            bases_formatted = (
                f"({', '.join(base_strs)})" if base_strs else ""
            )

            fields: list[str] = []
            if is_dc:
                for item in node.body:
                    if isinstance(item, ast.AnnAssign):
                        fields.append(ast.unparse(item))
                    elif isinstance(item, ast.FunctionDef):
                        if item.name == "__init__":
                            num_args = len(item.args.args)
                            num_defaults = len(item.args.defaults)
                            defaults_offset = num_args - num_defaults
                            for i, arg in enumerate(item.args.args):
                                if arg.arg == "self":
                                    continue
                                ann = (
                                    ast.unparse(arg.annotation)
                                    if arg.annotation
                                    else "Any"
                                )
                                if i >= defaults_offset:
                                    def_node = item.args.defaults[
                                        i - defaults_offset
                                    ]
                                    def_str = ast.unparse(def_node)
                                    fields.append(f"{arg.arg}: {ann} = {def_str}")
                                else:
                                    fields.append(f"{arg.arg}: {ann}")
                        elif any(
                            isinstance(d, ast.Name) and d.id == "property"
                            for d in item.decorator_list
                        ):
                            ann = (
                                ast.unparse(item.returns)
                                if item.returns
                                else "Any"
                            )
                            if not any(
                                f.startswith(f"{item.name}:") for f in fields
                            ):
                                fields.append(f"{item.name}: {ann}")

            if is_dc and (has_explicit_dataclass or fields or not base_strs):
                lines.append("@dataclass(frozen=True)")
                lines.append(f"class {cls_name}{bases_formatted}:")
                lines.append(f"    # TODO_{cls_name}_body")
                if fields:
                    for f_line in fields:
                        lines.append(f"    {f_line}")
                else:
                    lines.append("    pass")
                lines.append("")
                lines.append("")
            elif not is_impl and is_proto:
                if "Protocol" not in base_strs:
                    base_strs.append("Protocol")
                    bases_formatted = f"({', '.join(base_strs)})"
                lines.append(f"class {cls_name}{bases_formatted}:")
                methods = [
                    item
                    for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if not methods:
                    lines.append(f"    # TODO_{cls_name}_body")
                    lines.append("    pass")
                else:
                    for item in methods:
                        is_prop = any(
                            isinstance(d, ast.Name) and d.id == "property"
                            for d in item.decorator_list
                        )
                        if is_prop:
                            lines.append("    @property")
                        args_str = ast.unparse(item.args)
                        ret_str = (
                            f" -> {ast.unparse(item.returns)}"
                            if item.returns
                            else ""
                        )
                        lines.append(f"    def {item.name}({args_str}){ret_str}:")
                        lines.append(f"        # TODO_{item.name}_body")
                        lines.append("        ...")
                        lines.append("")
                lines.append("")
            elif is_impl:
                lines.append(f"class {cls_name}{bases_formatted}:")
                lines.append(f'    tier = "{tier_val}"')
                lines.append("")
                has_custom_init = any(
                    isinstance(item, ast.FunctionDef) and item.name == "__init__"
                    for item in node.body
                )
                if not has_custom_init:
                    lines.append("    def __init__(self) -> None:")
                    lines.append("        # TODO___init___body")
                    lines.append("        pass")
                    lines.append("")
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        is_prop = any(
                            isinstance(d, ast.Name) and d.id == "property"
                            for d in item.decorator_list
                        )
                        if is_prop:
                            lines.append("    @property")
                        args_str = ast.unparse(item.args)
                        ret_str = (
                            f" -> {ast.unparse(item.returns)}"
                            if item.returns
                            else ""
                        )
                        lines.append(f"    def {item.name}({args_str}){ret_str}:")
                        lines.append(f"        # TODO_{item.name}_body")
                        if item.name == "__init__":
                            lines.append("        pass")
                        else:
                            lines.append("        raise NotImplementedError")
                        lines.append("")
                lines.append("")
            else:
                lines.append(f"class {cls_name}{bases_formatted}:")
                lines.append(f"    # TODO_{cls_name}_body")
                lines.append("    pass")
                lines.append("")
                lines.append("")

    if is_impl and singleton_classes:
        lines.append(
            "def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:"
        )
        lines.append("    reg = get_default_registry() if registry is None else registry")
        for cls_name, bases, tier_val in singleton_classes:
            keys = [cls_name] + [b for b in bases if b != cls_name]
            keys_formatted = ", ".join(keys)
            lines.append("    reg.register_singleton(")
            lines.append(f"        {cls_name},")
            lines.append(f"        keys=[{keys_formatted}],")
            lines.append(f'        tier="{tier_val}",')
            lines.append("    )")
        lines.append("")
        lines.append("_initialize_ = __initialize__")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Maintain a pyright_library BUILD entry.")
    ap.add_argument("build_path", help="path to the package's BUILD.bazel file")
    ap.add_argument("module_path", help="path to the module the entry is for")
    ap.add_argument(
        "--deps",
        default="",
        help="comma-separated expected pyright_deps module names (spec-derived)",
    )
    ap.add_argument(
        "--pyi-deps",
        default="",
        help="comma-separated paths to dependent .pyi specification files",
    )
    ap.add_argument(
        "--pyi",
        default="",
        help="path to the module's grounding .pyi specification file",
    )
    args = ap.parse_args()

    package = package_of(args.build_path)
    stem = module_stem(args.module_path)
    srcs = module_file(args.module_path)
    raw_deps = [d for d in args.deps.split(",") if d]
    pyi_paths = [p for p in args.pyi_deps.split(",") if p]
    dir_name = os.path.dirname(args.module_path) or package or "."

    spec_file = find_spec_pyi(
        args.module_path,
        pyi_path=args.pyi or None,
        pyi_deps=pyi_paths,
        build_path=args.build_path,
    )
    if spec_file and not args.pyi:
        args.pyi = spec_file

    if spec_file and not stem.endswith("_asm"):
        mod_exists = os.path.isfile(args.module_path)
        mod_content = read_text(args.module_path) if mod_exists else ""
        if not mod_exists or is_uninitialized_module(mod_content):
            skeleton = generate_lib_skeleton(spec_file, stem)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            write_text(args.module_path, skeleton)

    pkg_build_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(args.build_path))),
        "BUILD.bazel",
    )
    pkg_deps = None
    if os.path.isfile(pkg_build_path):
        pkg_deps = parse_package_build_dependencies(
            pkg_build_path, stem, resolve_cross_package=False
        )

    if pkg_deps is not None:
        parent_pkg = package_of(pkg_build_path)
        content = (
            read_text(args.module_path) if os.path.isfile(args.module_path) else ""
        )
        pyi_content = (
            read_text(args.pyi) if args.pyi and os.path.isfile(args.pyi) else ""
        )
        uses_lifecycle = (
            "support.lib.lifecycle" in content
            or re.search(
                r"\b(LifecycleRegistry|Singleton|get_singleton|get_default_registry)\b",
                content,
            )
            is not None
            or stem.endswith("_impl")
            or "@singleton_type" in pyi_content
        )

        raw_deps = []
        lib_deps = []
        allowed_deps = set()
        ext_stems: set[str] = set()

        for d in pkg_deps:
            stem_d = d.split(":")[-1]
            if stem_d.endswith("_ext"):
                ext_stems.add(stem_d)
            else:
                if d.startswith("//"):
                    raw = d[2:]
                    p_part, t_part = (
                        raw.split(":", 1)
                        if ":" in raw
                        else (raw, os.path.basename(raw))
                    )
                    if p_part == parent_pkg:
                        lib_label = f":{t_part}"
                    else:
                        p_lib = p_part if p_part.endswith("/lib") else f"{p_part}/lib"
                        lib_label = f"//{p_lib}:{t_part}"
                    lib_deps.append(lib_label)
                    allowed_deps.add(t_part)
                    raw_deps.append(lib_label)
                elif d.startswith(":"):
                    t_part = d[1:]
                    lib_deps.append(f":{t_part}")
                    allowed_deps.add(t_part)
                    raw_deps.append(f":{t_part}")
                else:
                    lib_deps.append(f":{d}")
                    allowed_deps.add(d)
                    raw_deps.append(f":{d}")

        if uses_lifecycle:
            lifecycle_label = "//update_python_with_ai/support/lib:lifecycle"
            lib_deps.append(lifecycle_label)
            allowed_deps.add("lifecycle")

        for stem_d in ext_stems:
            spec_file = f"{stem_d}.pyi"
            build_dir = os.path.dirname(args.build_path)
            for search_dir in [
                os.path.join(build_dir, "..", "grounding"),
                os.path.join(build_dir, "..", "specs", "grounding"),
                "update_with_ai/specs/grounding",
                "specs/grounding",
            ]:
                candidate = os.path.join(search_dir, spec_file)
                if os.path.isfile(candidate):
                    pyi_paths.append(candidate)
                    break
            if not any(
                os.path.splitext(os.path.basename(p))[0] == stem_d
                for p in pyi_paths
            ):
                for cand in Path("update_with_ai/parts").glob(
                    f"*/grounding/{spec_file}"
                ):
                    pyi_paths.append(str(cand))
                    break

        target_deps: list[str] = []
        for p in pyi_paths:
            for dep_expr in parse_spec_build_dependencies(p):
                if dep_expr not in target_deps:
                    target_deps.append(dep_expr)

        if args.pyi and os.path.isfile(args.pyi):
            for d in parse_pyi_dependencies(args.pyi, pyi_paths):
                allowed_deps.add(d)
        elif pyi_paths:
            for d in parse_pyi_dependencies("", pyi_paths):
                allowed_deps.add(d)

        if stem.endswith("_asm"):
            asm_content = generate_asm_content(dir_name, raw_deps)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            if (
                not os.path.exists(args.module_path)
                or read_text(args.module_path) != asm_content
            ):
                write_text(args.module_path, asm_content)

        has_declared_deps = True
        import_map, label_map, sibling_stems = build_module_resolution_map(
            args.build_path, dir_name, raw_deps
        )
        if os.path.exists(args.module_path) and not stem.endswith("_asm"):
            rewrite_lib_imports(
                args.module_path, dir_name, import_map, sibling_stems
            )
            ensure_dependency_header(
                args.module_path,
                sorted(allowed_deps),
                import_map=import_map,
                sibling_stems=sibling_stems,
            )

        syntax_errors = check_syntax(args.module_path)
        if syntax_errors:
            for err in syntax_errors:
                sys.stderr.write(err + "\n")
            return 1

        has_pip_req = any(d.startswith("requirement(") for d in target_deps)
        if not os.path.exists(args.build_path):
            d = os.path.dirname(args.build_path)
            if d:
                os.makedirs(d, exist_ok=True)
            header = (
                "# " + (package + "/BUILD.bazel" if package else "BUILD.bazel") + "\n"
            )
            loads = load_line(["pyright_library"])
            if has_pip_req:
                loads += '\nload("@pip//:requirements.bzl", "requirement")'
            write_text(args.build_path, header + loads + "\n")
        text = read_text(args.build_path)
        text = ensure_load(text, ["pyright_library"])
        if has_pip_req:
            text = ensure_pip_load(text)

        text = ensure_target(
            text,
            RULE,
            stem,
            srcs,
            lib_deps,
            package,
            target_deps=target_deps,
            exact_deps=True,
        )
        write_text(args.build_path, text)
    else:
        if stem.endswith("_asm"):
            asm_content = generate_asm_content(dir_name, raw_deps)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            if (
                not os.path.exists(args.module_path)
                or read_text(args.module_path) != asm_content
            ):
                write_text(args.module_path, asm_content)

        allowed_deps = set()
        for d in raw_deps:
            m = re.search(r'requirement\(["\']([^"\']+)["\']\)', d)
            if m:
                allowed_deps.add(m.group(1))
            elif ":" in d:
                allowed_deps.add(d.split(":")[-1])
            elif d and not d.startswith("//"):
                allowed_deps.add(d)

        if args.pyi:
            for d in parse_pyi_dependencies(args.pyi, pyi_paths):
                allowed_deps.add(d)
        elif pyi_paths:
            for d in parse_pyi_dependencies("", pyi_paths):
                allowed_deps.add(d)

        for d in extract_target_pyright_deps(args.build_path, RULE, stem):
            allowed_deps.add(d.split(":")[-1])

        if not allowed_deps and os.path.exists(args.module_path):
            parsed = parse_dependency_header(read_text(args.module_path))
            if parsed is not None:
                allowed_deps = set(parsed)

        import_map, label_map, sibling_stems = build_module_resolution_map(
            args.build_path, dir_name, raw_deps
        )
        if os.path.exists(args.module_path) and not stem.endswith("_asm"):
            _, imported_cross_parts = rewrite_lib_imports(
                args.module_path, dir_name, import_map, sibling_stems
            )
            for s in imported_cross_parts:
                if s in label_map and label_map[s] not in raw_deps:
                    raw_deps.append(label_map[s])
                allowed_deps.add(s)

        has_declared_deps = bool(raw_deps or args.pyi or pyi_paths or allowed_deps)
        if (
            has_declared_deps
            and os.path.exists(args.module_path)
            and not stem.endswith("_asm")
        ):
            ensure_dependency_header(
                args.module_path,
                sorted(allowed_deps),
                import_map=import_map,
                sibling_stems=sibling_stems,
            )

        syntax_errors = check_syntax(args.module_path)
        if syntax_errors:
            for err in syntax_errors:
                sys.stderr.write(err + "\n")
            return 1

        # Separate library dependencies from external specification dependencies
        lib_deps = []
        for d in raw_deps:
            stem_d = d.split(":")[-1]
            if stem_d.endswith("_ext"):
                candidates = [
                    p
                    for p in pyi_paths
                    if os.path.splitext(os.path.basename(p))[0] == stem_d
                ]
                if not candidates:
                    spec_file = f"{stem_d}.pyi"
                    build_dir = os.path.dirname(args.build_path)
                    for search_dir in [
                        os.path.join(build_dir, "..", "grounding"),
                        os.path.join(build_dir, "..", "specs", "grounding"),
                        "update_with_ai/specs/grounding",
                        "specs/grounding",
                    ]:
                        candidate = os.path.join(search_dir, spec_file)
                        if os.path.isfile(candidate):
                            pyi_paths.append(candidate)
                            break
                    if not any(
                        os.path.splitext(os.path.basename(p))[0] == stem_d
                        for p in pyi_paths
                    ):
                        for cand in Path("update_with_ai/parts").glob(
                            f"*/grounding/{spec_file}"
                        ):
                            pyi_paths.append(str(cand))
                            break
            else:
                lib_deps.append(d)

        target_deps = []
        for p in pyi_paths:
            for dep_expr in parse_spec_build_dependencies(p):
                if dep_expr not in target_deps:
                    target_deps.append(dep_expr)

        has_pip_req = any(d.startswith("requirement(") for d in target_deps)

        if not os.path.exists(args.build_path):
            d = os.path.dirname(args.build_path)
            if d:
                os.makedirs(d, exist_ok=True)
            header = (
                "# " + (package + "/BUILD.bazel" if package else "BUILD.bazel") + "\n"
            )
            loads = load_line(["pyright_library"])
            if has_pip_req:
                loads += '\nload("@pip//:requirements.bzl", "requirement")'
            write_text(args.build_path, header + loads + "\n")
        text = read_text(args.build_path)
        text = ensure_load(text, ["pyright_library"])
        if has_pip_req:
            text = ensure_pip_load(text)
        roots = sorted(set(lib_deps + local_imports(package, args.module_path)))
        deps = transitive_closure(package, roots)
        text = ensure_target(
            text, RULE, stem, srcs, deps, package, target_deps=target_deps
        )
        write_text(args.build_path, text)

    structure_errors = check_lib_structure(args.module_path)
    import_errors = check_sibling_imports(package, args.module_path)
    impl_errors = check_impl_imports(args.module_path)
    exception_errors = check_exception_eating(args.module_path)
    framework_errors = check_framework_imports(args.module_path)
    dataclass_errors = check_dataclass_stubs(args.module_path)
    type_ignore_errors = check_type_ignore(args.module_path)
    type_errors = check_public_types(
        args.module_path,
        pyi_path=args.pyi or None,
        pyi_deps=pyi_paths,
        build_path=args.build_path,
    )
    dead_code_errors = check_dead_code(args.module_path)
    undeclared_errors = (
        check_undeclared_imports(args.module_path, sorted(allowed_deps))
        if has_declared_deps
        else []
    )
    all_errors = (
        structure_errors
        + import_errors
        + impl_errors
        + exception_errors
        + framework_errors
        + dataclass_errors
        + type_ignore_errors
        + type_errors
        + dead_code_errors
        + undeclared_errors
    )
    if all_errors:
        for err in all_errors:
            sys.stderr.write(err + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
