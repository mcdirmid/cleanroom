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


def _attr_list(block: str, attr: str) -> list[str]:
    """Parse an `attr = [ ... ]` string list from a rule block."""
    m = re.search(r"\b" + re.escape(attr) + r"\s*=\s*\[", block)
    if not m:
        return []
    j = block.find("]", m.end() - 1)
    if j == -1:
        return []
    return re.findall(r'"([^"]*)"', block[m.end():j])


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


def _new_target(rule: str, stem: str, srcs: str, deps: list[str], package: str) -> str:
    """A new rule block: name, srcs, pyright_deps (the known deps), empty
    deps, and public visibility (for library rules)."""
    want = ["//" + package + ":" + d for d in deps]
    if rule == "pyright_test":
        return (
            rule + "(\n"
            "    name = \"" + stem + "\",\n"
            "    srcs = [\"" + srcs + "\"],\n"
            "    pyright_deps = " + _render_list(want) + ",\n"
            ")\n"
        )
    return (
        rule + "(\n"
        "    name = \"" + stem + "\",\n"
        "    srcs = [\"" + srcs + "\"],\n"
        "    pyright_deps = " + _render_list(want) + ",\n"
        "    deps = [],\n"
        "    visibility = [\"//visibility:public\"],\n"
        ")\n"
    )


def ensure_target(
    text: str,
    rule: str,
    stem: str,
    srcs: str,
    deps: list[str],
    package: str,
) -> str:
    """Return text with the named rule target present and its pyright_deps
    covering the known deps (add-only)."""
    want = ["//" + package + ":" + d for d in deps]
    span = _find_block(text, rule, stem)
    if span is None:
        if not text.endswith("\n"):
            text += "\n"
        return text + "\n" + _new_target(rule, stem, srcs, deps, package)
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
    if rule != "pyright_test" and "visibility" not in block:
        block = _set_attr_list(block, "visibility", ["//visibility:public"])
    return text[:start] + block + text[end:]


def local_imports(modules_dir: str, file_path: str) -> list[str]:
    """The sibling module names a file imports: the last dotted component of
    each top-level or relative import that names a module file (`<name>.py`)
    in modules_dir. Stdlib/third-party and non-local imports are dropped; a
    missing or unparsable file yields no imports."""
    result: list[str] = []
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (OSError, SyntaxError):
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
    except (OSError, SyntaxError):
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


def check_test_imports(lib_pkg: str, file_path: str) -> list[str]:
    """Check that imports in a test module from the lib package use 'lib.<name>' syntax,
    and not full package prefixes (e.g. testing.lib or update_with_ai.lib) or bare imports."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (OSError, SyntaxError):
        return errors
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[-1]
                if name and os.path.isfile(os.path.join(lib_pkg, name + ".py")):
                    if alias.name != f"lib.{name}":
                        errors.append(
                            f"{file_path}:{node.lineno}: error: import of lib module '{alias.name}' must be 'import lib.{name}'"
                        )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                name = node.module.split(".")[-1]
                if name and os.path.isfile(os.path.join(lib_pkg, name + ".py")):
                    if node.module != f"lib.{name}":
                        errors.append(
                            f"{file_path}:{node.lineno}: error: import of lib module '{node.module}' must be 'from lib.{name} import ...'"
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
    modules directly (they should target the module under test) and that @patch
    decorators have matching parameters on the test method."""
    errors: list[str] = []
    if not os.path.exists(file_path):
        return errors
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (OSError, SyntaxError):
        return errors

    for node in ast.walk(tree):
        # 1. Check patch calls (both function calls and decorators)
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

        # 2. Check test method decorator arity
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
    except (OSError, SyntaxError):
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


