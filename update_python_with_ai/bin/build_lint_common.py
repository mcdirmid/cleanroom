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
    m2 = re.search(r"\bsrcs\s*=\s*\[[^\]]*\]", block)
    if m2:
        insert_at = m2.end()
    else:
        m3 = re.search(r'\bname\s*=\s*"[^"]*"', block)
        insert_at = m3.end() if m3 else 0
    return block[:insert_at] + "\n    " + rendered + "," + block[insert_at:]


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
    deps, and public visibility."""
    want = ["//" + package + ":" + d for d in deps]
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
    if "visibility" not in block:
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
