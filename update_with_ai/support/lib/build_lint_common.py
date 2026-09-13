"""Shared BUILD-file maintenance for the lib_lint and test_lint fixers.

Both linters ensure a module's BUILD entry exists and is configured with the
known dependency set (spec-graph-derived, passed via --deps): they create the
BUILD file when missing, add the pyright load statement when missing, add the
named rule target when missing, and add any missing pyright_deps (add-only:
existing entries, including extras, are left in place). The dependency set is
closed over the sibling-module imports (local_imports / transitive_closure),
so pyright_deps cover every module the target's files import, directly or
transitively. Future checks slot in as pure-report errors (exit 1) rather
than fixes.

The linters write the BUILD file directly; the sandbox contract permits
verification to maintain a node's silent sources (see specs/high/sandbox.md).
"""

import ast
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import Optional, Sequence, Tuple


def load_line(names: Sequence[str]) -> str:
    """A pyright load statement loading the given names."""
    return 'load("//bin:pyright_library.bzl", ' + ", ".join('"%s"' % n for n in names) + ")"


def package_of(build_path: str) -> str:
    """The Bazel package of a BUILD file path (its directory)."""
    d = os.path.dirname(build_path)
    return d.lstrip("./") or ""


def module_stem(module_path: str) -> str:
    """The module's target name: its file stem (module.py -> module)."""
    base = os.path.basename(module_path)
    return base[:-3] if base.endswith(".py") else base


def module_file(module_path: str) -> str:
    """The module's file name (the srcs entry)."""
    return os.path.basename(module_path)


def label_target(label: str) -> str:
    """The target name of a label (//pkg:name or :name -> name)."""
    return label.split(":")[-1]


def read_text(path: str) -> str:
    """Read a file's content."""
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_text(path: str, text: str) -> None:
    """Write a file's content."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _render_list(values: list[str]) -> str:
    """Render a Starlark string list, one entry per line."""
    if not values:
        return "[]"
    body = ",\n        ".join('"' + v + '"' for v in values)
    return "[\n        " + body + ",\n    ]"


def _render_expr_list(values: Sequence[str]) -> str:
    """Render a Starlark list of expressions or labels, one entry per line."""
    if not values:
        return "[]"
    rendered: list[str] = []
    for v in values:
        v_s = v.strip()
        if (
            (v_s.startswith('"') and v_s.endswith('"'))
            or (v_s.startswith("'") and v_s.endswith("'"))
            or v_s.startswith("requirement(")
        ):
            rendered.append(v_s)
        else:
            rendered.append('"' + v_s + '"')
    body = ",\n        ".join(rendered)
    return "[\n        " + body + ",\n    ]"


def _attr_list(block: str, attr: str) -> list[str]:
    """Parse an `attr = [ ... ]` string list from a rule block."""
    m = re.search(r"\b" + re.escape(attr) + r"\s*=\s*\[", block)
    if not m:
        return []
    j = block.find("]", m.end() - 1)
    if j == -1:
        return []
    return re.findall(r'"([^"]*)"', block[m.end():j])


def _attr_expr_list(block: str, attr: str) -> list[str]:
    """Parse an `attr = [ ... ]` list preserving expressions like requirement("foo")."""
    m = re.search(r"\b" + re.escape(attr) + r"\s*=\s*\[", block)
    if not m:
        return []
    j = block.find("]", m.end() - 1)
    if j == -1:
        return []
    content = block[m.end():j]
    tokens = re.findall(r'requirement\([^)]+\)|"[^"]*"|\'[^\']*\'', content)
    return [t.strip() for t in tokens if t.strip()]


def _set_attr_list(block: str, attr: str, values: list[str]) -> str:
    """Return the block with attr's list replaced by values (inserted when
    the attribute is absent, after the srcs list or the name line)."""
    rendered = attr + " = " + _render_list(values)
    m = re.search(r"\b" + re.escape(attr) + r"\s*=\s*\[", block)
    if m:
        j = block.find("]", m.end() - 1)
        return block[:m.start()] + rendered + block[j + 1:]
    m2 = re.search(r"(\bsrcs\s*=\s*\[[^\]]*\]\s*,?)", block)
    if m2:
        srcs_part = m2.group(1).rstrip()
        if not srcs_part.endswith(","):
            srcs_part += ","
        return block[:m2.start()] + srcs_part + "\n    " + rendered + "," + block[m2.end():]
    m3 = re.search(r'(\bname\s*=\s*"[^"]*"\s*,?)', block)
    if m3:
        name_part = m3.group(1).rstrip()
        if not name_part.endswith(","):
            name_part += ","
        return block[:m3.start()] + name_part + "\n    " + rendered + "," + block[m3.end():]
    return block


def _set_attr_expr_list(block: str, attr: str, values: Sequence[str]) -> str:
    """Return the block with attr's list replaced by expression values."""
    rendered = attr + " = " + _render_expr_list(values)
    m = re.search(r"\b" + re.escape(attr) + r"\s*=\s*\[", block)
    if m:
        j = block.find("]", m.end() - 1)
        return block[:m.start()] + rendered + block[j + 1:]
    m2 = re.search(r"(\bsrcs\s*=\s*\[[^\]]*\]\s*,?)", block)
    if m2:
        srcs_part = m2.group(1).rstrip()
        if not srcs_part.endswith(","):
            srcs_part += ","
        return block[:m2.start()] + srcs_part + "\n    " + rendered + "," + block[m2.end():]
    m3 = re.search(r'(\bname\s*=\s*"[^"]*"\s*,?)', block)
    if m3:
        name_part = m3.group(1).rstrip()
        if not name_part.endswith(","):
            name_part += ","
        return block[:m3.start()] + name_part + "\n    " + rendered + "," + block[m3.end():]
    return block


def _find_block(text: str, rule: str, name: str) -> Optional[Tuple[int, int]]:
    """Return (start, end) offsets of the named rule block, or None."""
    m = re.search(
        r"\b" + re.escape(rule) + r"\(\s*name\s*=\s*\"" + re.escape(name) + r"\"",
        text,
    )
    if not m:
        return None
    i = text.find("(", m.start())
    depth = 0
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return (m.start(), i + 1)
        i += 1
    return None


def ensure_load(text: str, names: Sequence[str]) -> str:
    """Return text whose load statement for //bin:pyright_library.bzl loads
    every name in names: the statement is added at the top when absent, and
    missing names are added to an existing statement for the file."""
    m = re.search(r'load\(\s*"//bin:pyright_library\.bzl"\s*,\s*([^)]*)\)', text)
    if m:
        loaded = [n.strip().strip('"') for n in m.group(1).split(",") if n.strip()]
        missing = [n for n in names if n not in loaded]
        if not missing:
            return text
        line = load_line(loaded + missing)
        return text[: m.start()] + line + text[m.end():]
    return load_line(names) + "\n" + text


def ensure_pip_load(text: str) -> str:
    """Ensure load("@pip//:requirements.bzl", "requirement") exists in text."""
    if 'load("@pip//:requirements.bzl", "requirement")' in text:
        return text
    m = re.search(r'load\([^)]*\)\n', text)
    if m:
        idx = m.end()
        return text[:idx] + 'load("@pip//:requirements.bzl", "requirement")\n' + text[idx:]
    return 'load("@pip//:requirements.bzl", "requirement")\n' + text


def parse_spec_build_dependencies(spec_path: str) -> list[str]:
    """Parse dependencies declared under ## Build Dependencies in a .pyi spec.

    Returns a list of Starlark expressions to include in the target's deps = [...],
    such as 'requirement("openai")' or '@repo//:target'.
    """
    if not os.path.isfile(spec_path):
        return []
    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return []

    m = re.search(r"^##\s+Build Dependencies\s*$", content, re.MULTILINE)
    if not m:
        return []

    start = m.end()
    rest = content[start:]
    end_m = re.search(r"^##\s+", rest, re.MULTILINE)
    sec_text = rest[: end_m.start()] if end_m else rest

    doc_end = re.search(r"'''|\"\"\"", sec_text)
    if doc_end:
        sec_text = sec_text[: doc_end.start()]

    deps: list[str] = []
    for line in sec_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        bullet_m = re.match(r"^-\s*(.*)$", stripped)
        if bullet_m:
            item = bullet_m.group(1).strip().strip("`").strip()
            if item and item.lower() not in ("(none)", "none", "[]"):
                deps.append(item)
        elif stripped.lower() in ("(none)", "none", "[]"):
            continue
    return deps


def _new_target(
    rule: str,
    stem: str,
    srcs: str,
    deps: list[str],
    package: str,
    target_deps: Optional[Sequence[str]] = None,
) -> str:
    """A new rule block: name, srcs, deps (external deps), pyright_deps (the known deps), and public visibility."""
    want = ["//" + package + ":" + d for d in deps]
    rendered_deps = _render_expr_list(target_deps or [])
    if rule == "pyright_test":
        target_str = (
            rule + "(\n"
            '    name = "' + stem + '",\n'
            '    srcs = ["' + srcs + '"],\n'
        )
        if target_deps:
            target_str += "    deps = " + rendered_deps + ",\n"
        target_str += (
            "    pyright_deps = " + _render_list(want) + ",\n"
            ")\n"
        )
        return target_str
    return (
        rule + "(\n"
        '    name = "' + stem + '",\n'
        '    srcs = ["' + srcs + '"],\n'
        "    deps = " + rendered_deps + ",\n"
        "    pyright_deps = " + _render_list(want) + ",\n"
        '    visibility = ["//visibility:public"],\n'
        ")\n"
    )


def ensure_target(
    text: str,
    rule: str,
    stem: str,
    srcs: str,
    deps: list[str],
    package: str,
    target_deps: Optional[Sequence[str]] = None,
) -> str:
    """Return text with the named rule target present and its pyright_deps
    and deps covering the known deps (add-only)."""
    want = [d if d.startswith("//") else ("//" + package + ":" + d.lstrip(":")) for d in deps]
    span = _find_block(text, rule, stem)
    if span is None:
        if not text.endswith("\n"):
            text += "\n"
        return text + "\n" + _new_target(rule, stem, srcs, deps, package, target_deps=target_deps)
    start, end = span
    block = text[start:end]
    existing = _attr_list(block, "pyright_deps")
    # Canonical labels for the expected deps: a same-name entry in the wrong
    # package is replaced by the canonical label (the deps live in the given
    # package — the lib package for tests, the BUILD's own package for libs);
    # extras (names not expected) are preserved.
    new_list = list(existing)
    for w in want:
        if w in new_list:
            continue
        replaced = False
        for i, e in enumerate(new_list):
            if label_target(e) == label_target(w):
                new_list[i] = w
                replaced = True
                break
        if not replaced:
            new_list.append(w)
    if new_list != existing:
        block = _set_attr_list(block, "pyright_deps", new_list)

    if target_deps is not None:
        existing_deps = _attr_expr_list(block, "deps")
        new_deps = list(existing_deps)
        for td in target_deps:
            td_clean = td.strip()
            if td_clean not in new_deps and ('"' + td_clean + '"') not in new_deps:
                new_deps.append(td_clean)
        if new_deps != existing_deps or ("deps" not in block and (target_deps or rule != "pyright_test")):
            block = _set_attr_expr_list(block, "deps", new_deps)

    if rule != "pyright_test" and "visibility" not in block:
        block = _set_attr_list(block, "visibility", ["//visibility:public"])
    return text[:start] + block + text[end:]


def check_syntax(file_path: str) -> list[str]:
    """Check that a file contains valid Python syntax.
    Returns error messages for any SyntaxError encountered."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            ast.parse(f.read(), filename=file_path)
    except SyntaxError as e:
        line = e.lineno if e.lineno is not None else 1
        errors.append(f"{file_path}:{line}: error: syntax error: {e.msg}")
    except OSError:
        return errors
    return errors


def local_imports(modules_dir: str, file_path: str) -> list[str]:
    """The sibling module names a file imports: the last dotted component of
    each top-level or relative import that names a module file (`<name>.py`)
    in modules_dir. Stdlib/third-party and non-local imports are dropped; a
    missing or unparsable file yields no imports."""
    result: list[str] = []
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return result
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _add_local(modules_dir, alias.name, result)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _add_local(modules_dir, node.module, result)
            else:
                # A relative import of the package's own modules
                # (`from . import x`): the imported names are the modules.
                for alias in node.names:
                    _add_local(modules_dir, alias.name, result)
    return sorted(result)


def _add_local(modules_dir: str, dotted: str, result: list[str]) -> None:
    """Add dotted's last component to result when it names a module file in
    modules_dir (and is not already present)."""
    name = dotted.split(".")[-1]
    if name and os.path.isfile(os.path.join(modules_dir, name + ".py")) and name not in result:
        result.append(name)


def transitive_closure(modules_dir: str, roots: list[str]) -> list[str]:
    """The transitive closure of sibling-module imports reachable from the
    root module names: BFS over each module's local imports (per
    local_imports), so every module the roots import from the same directory
    — directly or transitively — is included. Missing files and cycles are
    handled; the result is sorted."""
    seen: set[str] = set()
    queue = list(roots)
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        if name.startswith("//"):
            continue
        path = os.path.join(modules_dir, name + ".py")
        for dep in local_imports(modules_dir, path):
            if dep not in seen:
                queue.append(dep)
    return sorted(seen)


def check_sibling_imports(modules_dir: str, file_path: str) -> list[str]:
    """Check that any imports of sibling modules in modules_dir use relative syntax.
    Returns a list of error messages for any non-relative imports."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return errors
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[-1]
                if name and os.path.isfile(os.path.join(modules_dir, name + ".py")):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: import of sibling module '{alias.name}' must be relative (use 'from .{name} import ...')"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                name = node.module.split(".")[-1]
                if name and os.path.isfile(os.path.join(modules_dir, name + ".py")):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: import of sibling module '{node.module}' must be relative (use 'from .{name} import ...')"
                    )
    return errors


def check_impl_imports(file_path: str) -> list[str]:
    """Check that non-assembly library modules do not import any Impl classes or *_impl modules.
    Only assembly modules (*_asm.py) are permitted to import implementation classes or modules."""
    errors: list[str] = []
    base = os.path.basename(file_path)
    if not base.endswith(".py") or base.endswith("_asm.py"):
        return errors
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return errors
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[-1]
                if name.endswith("Impl") or name.endswith("_impl"):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: non-assembly module must not import implementation class or module '{alias.name}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_name = node.module.split(".")[-1]
                if mod_name.endswith("_impl"):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: non-assembly module must not import from implementation module '{node.module}'"
                    )
            for alias in node.names:
                if alias.name.endswith("Impl"):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: non-assembly module must not import implementation class '{alias.name}'"
                    )
    return errors


def check_lib_structure(file_path: str) -> list[str]:
    """Check that library modules do not contain test runner boilerplate."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        return errors
    if "unittest.main()" in text:
        errors.append(
            f"{file_path}: error: library module must not call 'unittest.main()'; test runners belong in test modules only"
        )
    return errors


FRAMEWORK_DECORATORS = {
    "singleton_type",
    "poly_type",
    "data_type",
    "variant",
    "operation",
    "override",
}


def _extract_decorator_name(dec: ast.expr) -> Optional[str]:
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Call):
        return _extract_decorator_name(dec.func)
    return None


def check_framework_imports(file_path: str) -> list[str]:
    """Check that library modules do not import from 'framework' or use specification framework decorators.
    Specification framework decorators belong in .pyi grounding specifications only."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "framework" or alias.name.endswith(".framework"):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: library module must not import from 'framework'; "
                        f"specification decorators belong in .pyi grounding specifications only"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module == "framework" or (node.module and node.module.endswith(".framework")):
                errors.append(
                    f"{file_path}:{node.lineno}: error: library module must not import from 'framework'; "
                    f"specification decorators belong in .pyi grounding specifications only"
                )
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                dec_name = _extract_decorator_name(dec)
                if dec_name in FRAMEWORK_DECORATORS:
                    errors.append(
                        f"{file_path}:{dec.lineno}: error: specification framework decorator '@{dec_name}' must not be used in library code; "
                        f"specification decorators belong in .pyi grounding specifications only and must be omitted from library implementations"
                    )
    return errors


def check_dataclass_stubs(file_path: str) -> list[str]:
    """Check that dataclasses in library modules declare fields as class attributes,
    not empty __init__ or property stubs."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return errors

    def _is_ellipsis_body(body: list[ast.stmt]) -> bool:
        if len(body) == 1 and isinstance(body[0], ast.Expr):
            val = body[0].value
            if isinstance(val, ast.Constant) and val.value is Ellipsis:
                return True
        elif len(body) == 1 and isinstance(body[0], ast.Pass):
            return True
        return False

    def _is_dataclass(class_def: ast.ClassDef) -> bool:
        for dec in class_def.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "dataclass":
                return True
            if isinstance(dec, ast.Call):
                func = dec.func
                if isinstance(func, ast.Name) and func.id == "dataclass":
                    return True
                if isinstance(func, ast.Attribute) and func.attr == "dataclass":
                    return True
            if isinstance(dec, ast.Attribute) and dec.attr == "dataclass":
                return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _is_dataclass(node):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == "__init__" and _is_ellipsis_body(item.body):
                        errors.append(
                            f"{file_path}:{item.lineno}: error: dataclass '{node.name}' must declare fields as class attributes, "
                            f"not stub '__init__' methods"
                        )
                    for dec in item.decorator_list:
                        if isinstance(dec, ast.Name) and dec.id == "property" and _is_ellipsis_body(item.body):
                            errors.append(
                                f"{file_path}:{item.lineno}: error: dataclass '{node.name}' must declare fields as class attributes, "
                                f"not stub '@property' methods"
                            )
    return errors


def check_exception_eating(file_path: str) -> list[str]:
    """Check that library modules do not suppress unexpected failures by catching
    broad exceptions (bare except, Exception, BaseException) without re-raising."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for h in node.handlers:
                is_broad = False
                if h.type is None:
                    is_broad = True
                elif isinstance(h.type, ast.Name) and h.type.id in ("Exception", "BaseException"):
                    is_broad = True
                elif isinstance(h.type, ast.Tuple):
                    for elt in h.type.elts:
                        if isinstance(elt, ast.Name) and elt.id in ("Exception", "BaseException"):
                            is_broad = True
                if is_broad:
                    has_raise = any(isinstance(stmt, ast.Raise) for stmt in ast.walk(h))
                    if not has_raise:
                        type_str = ast.unparse(h.type) if h.type else "bare except"
                        errors.append(
                            f"{file_path}:{h.lineno}: error: broad exception eating detected: '{type_str}' "
                            f"must not suppress unexpected failures; re-raise or allow exceptions to propagate"
                        )
    return errors


def check_type_ignore(file_path: str) -> list[str]:
    """Check that library modules do not use '# type: ignore' comments.
    Type checker errors must be resolved through proper declarations rather than suppressed."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, "rb") as f:
            for tok in tokenize.tokenize(f.readline):
                if tok.type == tokenize.COMMENT:
                    if re.search(r"#\s*type:\s*ignore\b", tok.string):
                        errors.append(
                            f"{file_path}:{tok.start[0]}: error: '# type: ignore' is prohibited; "
                            f"type errors must be properly resolved rather than suppressed"
                        )
    except (tokenize.TokenError, OSError, SyntaxError):
        pass
    return errors


def check_test_impl_imports(lib_pkg: str, file_path: str) -> list[str]:
    """Check that a test module (<target>_test.py) only imports from its target module (<target>)
    and does not import any other implementation module (*_impl.py) or foreign Impl class."""
    errors: list[str] = []
    base = os.path.basename(file_path)
    if not base.endswith("_test.py"):
        return errors
    target_stem = base[:-8]
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return errors

    target_imported = False
    imported_target_classes: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name.split(".")[-1]
                if mod_name.endswith("_impl") and mod_name != target_stem:
                    errors.append(
                        f"{file_path}:{node.lineno}: error: test module must only import target implementation module '{target_stem}', but imports '{alias.name}'"
                    )
                elif alias.name.endswith("Impl"):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: implementation classes do not use an 'Impl' suffix; import '{alias.name[:-4]}' instead of '{alias.name}'"
                    )
                if alias.name in (f"lib.{target_stem}", target_stem) or alias.name.endswith(f".{target_stem}"):
                    target_imported = True
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_name = node.module.split(".")[-1]
                if mod_name.endswith("_impl") and mod_name != target_stem:
                    errors.append(
                        f"{file_path}:{node.lineno}: error: test module must only import target implementation module '{target_stem}', but imports from '{node.module}'"
                    )
                if node.module in (f"lib.{target_stem}", target_stem) or node.module.endswith(f".{target_stem}"):
                    target_imported = True
                    for alias in node.names:
                        imported_target_classes.add(alias.name)
            for alias in node.names:
                if alias.name.endswith("Impl"):
                    errors.append(
                        f"{file_path}:{node.lineno}: error: implementation classes do not use an 'Impl' suffix; import '{alias.name[:-4]}' instead of '{alias.name}'"
                    )

    impl_py = os.path.join(lib_pkg, target_stem + ".py")
    if target_stem.endswith("_impl") and os.path.isfile(impl_py):
        impl_classes: set[str] = set()
        try:
            with open(impl_py, encoding="utf-8") as f:
                impl_tree = ast.parse(f.read(), filename=impl_py)
            for node in impl_tree.body:
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    impl_classes.add(node.name)
        except (OSError, SyntaxError):
            pass

        if not target_imported:
            pkg_prefix = f"{lib_pkg.replace('/', '.')}.{target_stem}" if "/" in lib_pkg else f"lib.{target_stem}"
            errors.append(
                f"{file_path}: error: test module must import target implementation module '{pkg_prefix}'"
            )
        elif impl_classes and not (imported_target_classes & impl_classes):
            has_impl_suffix_match = any(f"{c}Impl" in imported_target_classes for c in impl_classes)
            if not has_impl_suffix_match:
                expected_str = ", ".join(sorted(impl_classes))
                errors.append(
                    f"{file_path}: error: test module must import target class ({expected_str}) from target implementation module '{target_stem}'"
                )

    return errors


def check_test_imports(lib_pkg: str, file_path: str) -> list[str]:
    """Check that imports in a test module from the lib package use standard package syntax."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return errors
    expected_prefix = lib_pkg.replace("/", ".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[-1]
                if name and os.path.isfile(os.path.join(lib_pkg, name + ".py")):
                    if alias.name != f"lib.{name}" and not alias.name.endswith(f".{name}"):
                        errors.append(
                            f"{file_path}:{node.lineno}: error: import of lib module '{alias.name}' must be 'import {expected_prefix}.{name}' or 'import lib.{name}'"
                        )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                name = node.module.split(".")[-1]
                if name and os.path.isfile(os.path.join(lib_pkg, name + ".py")):
                    if node.module != f"lib.{name}" and not node.module.endswith(f".{name}"):
                        errors.append(
                            f"{file_path}:{node.lineno}: error: import of lib module '{node.module}' must be 'from {expected_prefix}.{name} import ...' or 'from lib.{name} import ...'"
                        )
    return errors


STDLIB_MODULES = {
    "os", "sys", "json", "shutil", "pathlib", "subprocess",
    "time", "datetime", "requests", "urllib", "re", "math",
    "io", "tempfile", "glob", "hashlib", "random", "socket",
    "http", "logging", "asyncio", "threading", "multiprocessing",
}


def check_test_mocks(file_path: str) -> list[str]:
    """Check that patch() calls in test modules do not target standard library
    modules directly, the module or class under test is never mocked, and @patch
    decorators have matching parameters on the test method."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return errors

    base = os.path.basename(file_path)
    target_stem = base[:-8] if base.endswith("_test.py") else ""
    target_camel = ""
    if target_stem:
        prefix = target_stem[:-5] if target_stem.endswith("_impl") else target_stem
        target_camel = "".join(part.capitalize() for part in prefix.split("_"))

    for node in ast.walk(tree):
        # 1. Check for mock or redefined classes of the system under test
        if isinstance(node, ast.ClassDef) and target_camel:
            forbidden_sut_names = {target_camel, f"{target_camel}Impl"}
            forbidden_mock_names = {f"Mock{target_camel}", f"Mock{target_camel}Impl"}
            if node.name in forbidden_sut_names:
                errors.append(
                    f"{file_path}:{node.lineno}: error: test module must not define class '{node.name}' under test; import it from 'lib.{target_stem}'"
                )
            elif node.name in forbidden_mock_names:
                errors.append(
                    f"{file_path}:{node.lineno}: error: class under test '{target_camel}' must never be mocked; only collaborator interfaces may be mocked (found '{node.name}')"
                )

        # 2. Check patch calls (both function calls and decorators)
        if isinstance(node, ast.Call):
            is_patch = False
            if isinstance(node.func, ast.Name) and node.func.id == "patch":
                is_patch = True
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "patch":
                is_patch = True

            if is_patch and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    target = first_arg.value
                    prefix = target.split(".")[0]
                    if prefix in STDLIB_MODULES:
                        errors.append(
                            f"{file_path}:{node.lineno}: error: patch('{target}') targets standard library directly; "
                            f"patch where it is looked up in the module under test (e.g. 'lib.<module>.{target}')"
                        )
                    elif target_stem and target == f"lib.{target_stem}":
                        errors.append(
                            f"{file_path}:{node.lineno}: error: module under test 'lib.{target_stem}' must not be mocked"
                        )
                    elif target_camel and target in (
                        f"lib.{target_stem}.{target_camel}",
                        f"lib.{target_stem}.{target_camel}Impl",
                    ):
                        errors.append(
                            f"{file_path}:{node.lineno}: error: class under test '{target_camel}' must not be mocked"
                        )

        # 3. Check test method decorator arity
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            injected_patches = 0
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    is_patch = False
                    if isinstance(dec.func, ast.Name) and dec.func.id == "patch":
                        is_patch = True
                    elif isinstance(dec.func, ast.Attribute) and dec.func.attr == "patch":
                        is_patch = True
                    if is_patch:
                        # If 'new' keyword arg is provided, patch does NOT inject a parameter
                        has_new = any(kw.arg == "new" for kw in dec.keywords)
                        if not has_new:
                            injected_patches += 1
            if injected_patches > 0:
                param_count = len(node.args.args)
                has_self = param_count > 0 and node.args.args[0].arg == "self"
                mock_params = (param_count - 1) if has_self else param_count
                if mock_params < injected_patches:
                    errors.append(
                        f"{file_path}:{node.lineno}: error: method '{node.name}' has {injected_patches} @patch "
                        f"decorator(s) injecting mocks, but only {mock_params} parameter(s) besides self"
                    )

    return errors


def check_test_structure(file_path: str) -> list[str]:
    """Check that the test module defines at least one unittest.TestCase subclass
    containing at least one test method (starting with 'test_')."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except OSError:
        return errors

    test_method_count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test_"):
                    test_method_count += 1

    if test_method_count == 0:
        errors.append(
            f"{file_path}: error: test module must define at least one test method starting with 'test_'"
        )
    return errors


def check_test_dry_run(lib_pkg: str, module_path: str) -> list[str]:
    """Perform a dry-run test discovery/load to verify that the test module
    imports cleanly and loads into unittest without runtime import/decorator crashes."""
    errors: list[str] = []
    if not os.path.exists(module_path):
        return errors

    lib_parent = os.path.dirname(lib_pkg) or "."
    test_dir = os.path.dirname(module_path) or "."
    mod_stem = os.path.splitext(os.path.basename(module_path))[0]

    cmd = [
        sys.executable,
        "-c",
        (
            f"import sys, os, unittest; "
            f"sys.path.insert(0, os.path.abspath('.')); "
            f"sys.path.insert(0, os.path.abspath('update_python_with_ai')); "
            f"sys.path.insert(0, os.path.abspath('update_with_ai')); "
            f"sys.path.insert(0, os.path.abspath('{lib_parent}')); "
            f"sys.path.insert(0, os.path.abspath('{test_dir}')); "
            f"import importlib; "
            f"mod = importlib.import_module('{mod_stem}'); "
            f"suite = unittest.defaultTestLoader.loadTestsFromModule(mod)"
        ),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            err_msg = res.stderr.strip() or res.stdout.strip()
            errors.append(f"{module_path}: error: dry-run test collection failed:\n{err_msg}")
    except subprocess.TimeoutExpired:
        errors.append(f"{module_path}: error: dry-run test collection timed out after 10s")
    except Exception as e:
        errors.append(f"{module_path}: error: dry-run test collection execution error: {e}")

    return errors


def extract_public_types(file_path: str) -> dict[str, int]:
    """Extract top-level public types (classes, type aliases, and type assignments)
    defined in a Python or .pyi file, mapping each type name to its definition line number.
    Private types (prefixed with '_') and non-type constants (ALL_CAPS) are ignored."""
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return {}

    types: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                types[node.name] = node.lineno
        elif hasattr(ast, "TypeAlias") and isinstance(node, ast.TypeAlias):
            alias_name = node.name.id if isinstance(node.name, ast.Name) else str(node.name)
            if not alias_name.startswith("_"):
                types[alias_name] = node.lineno
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_"):
                    if t.id[0].isupper() and any(c.islower() for c in t.id):
                        types[t.id] = node.lineno
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and not node.target.id.startswith("_"):
                if node.target.id[0].isupper() and any(c.islower() for c in node.target.id):
                    types[node.target.id] = node.lineno
    return types


def find_spec_pyi(
    module_path: str,
    pyi_path: Optional[str] = None,
    pyi_deps: Sequence[str] = (),
    build_path: Optional[str] = None,
) -> Optional[str]:
    """Locate the grounding specification .pyi file corresponding to a module."""
    if pyi_path and os.path.isfile(pyi_path):
        return pyi_path
    base = os.path.basename(module_path)
    stem = base[:-3] if base.endswith(".py") else base
    spec_name = f"{stem}.pyi"
    for p in pyi_deps:
        if os.path.basename(p) == spec_name and os.path.isfile(p):
            return p
    module_dir = os.path.dirname(module_path)
    search_dirs = [
        os.path.join(module_dir, "..", "grounding"),
        os.path.join(module_dir, "..", "specs", "grounding"),
    ]
    if build_path:
        search_dirs.append(os.path.join(os.path.dirname(build_path), "..", "grounding"))
        search_dirs.append(os.path.join(os.path.dirname(build_path), "..", "specs", "grounding"))
    search_dirs.extend([
        "update_with_ai/specs/grounding",
        "specs/grounding",
    ])
    for d in search_dirs:
        candidate = os.path.join(d, spec_name)
        if os.path.isfile(candidate):
            return candidate
    for cand in Path("update_with_ai/parts").glob(f"*/grounding/{spec_name}"):
        if cand.is_file():
            return str(cand)
    return None


def check_public_types(
    module_path: str,
    pyi_path: Optional[str] = None,
    pyi_deps: Sequence[str] = (),
    build_path: Optional[str] = None,
) -> list[str]:
    """Check that only types declared in the grounding specification are defined
    in the library code without a preceding underscore, and that all declared types
    are defined in the library code."""
    errors: list[str] = []
    base = os.path.basename(module_path)
    if not base.endswith(".py") or base.endswith("_asm.py"):
        return errors
    if not os.path.exists(module_path):
        return errors

    spec_file = find_spec_pyi(module_path, pyi_path=pyi_path, pyi_deps=pyi_deps, build_path=build_path)
    if not spec_file:
        return errors

    expected_types = extract_public_types(spec_file)
    actual_types = extract_public_types(module_path)
    spec_display = os.path.basename(spec_file)

    # Extra public types in library module
    for name, lineno in sorted(actual_types.items()):
        if name not in expected_types:
            errors.append(
                f"{module_path}:{lineno}: error: public type '{name}' is defined in library code "
                f"but is not declared in grounding specification '{spec_display}'; "
                f"helper types must be prefixed with an underscore (e.g. '_{name}')"
            )

    # Missing public types in library module
    for name in sorted(expected_types.keys()):
        if name not in actual_types:
            errors.append(
                f"{module_path}: error: type '{name}' declared in grounding specification "
                f"'{spec_display}' is not defined in library code"
            )

    return errors


def check_dead_code(module_path: str) -> list[str]:
    """Check for unused private helper functions and classes in library code.

    A private helper definition starting with an underscore (and not a dunder like __init__
    or __initialize__) must be referenced at least once in the module's AST; otherwise it is
    dead code.
    """
    errors: list[str] = []
    base = os.path.basename(module_path)
    if not base.endswith(".py") or base.endswith("_asm.py"):
        return errors
    if not os.path.exists(module_path):
        return errors

    try:
        with open(module_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=module_path)
    except SyntaxError:
        return errors

    private_defs: list[Tuple[str, int, str]] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_") and not (node.name.startswith("__") and node.name.endswith("__")):
                private_defs.append((node.name, node.lineno, "function"))
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_") and not (node.name.startswith("__") and node.name.endswith("__")):
                private_defs.append((node.name, node.lineno, "class"))

    if not private_defs:
        return errors

    used_identifiers: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            used_identifiers.add(n.id)
        elif isinstance(n, ast.Attribute):
            used_identifiers.add(n.attr)

    for name, lineno, kind in sorted(private_defs, key=lambda x: x[1]):
        if name not in used_identifiers:
            errors.append(
                f"{module_path}:{lineno}: error: private {kind} '{name}' is defined in library code "
                f"but never referenced (dead code)"
            )

    return errors
