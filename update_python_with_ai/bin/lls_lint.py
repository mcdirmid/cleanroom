#!/usr/bin/env python3
"""
lls_lint.py — lint low-level specification files per update_python_with_ai/guides/low_level_spec.md.

Usage:
    python3 update_python_with_ai/bin/lls_lint.py [files...]     # default: all *.md under specs/low/
    python3 update_python_with_ai/bin/lls_lint.py --deps <spec file paths...> -- <target files...>

Checks (E = error, exits nonzero; W = warning, does not affect exit code):
  E  missing dependency comment on the first line
  E  dependency comment references a spec that is not a `- <name>.md` entry (e.g. an HLS file)
  E  dependency-comment entry that is not a specified module dep (module_deps) or an external doc (specs/external/)
  E  module dep (module_deps) not listed in the dependency comment (the comment is exactly module_deps)
  E  dependency-comment entry that is a file path (`- foo/bar.md`); entries are bare `<name>.md` names

Dependency-comment entries resolve against the linted files, the `--deps`
list (the specified `module_deps` md files, passed directly — no transitive
closure), and the external dependency docs under `specs/external/` (e.g.
`- openai_api.md` for `specs/external/openai_api.md`); entries are bare
`<name>.md` names, never file paths.
  E  header not `# Interface LLS: <stem>` / `# Implementation LLS: <stem>`, or name/stem mismatch
  E  `# Implementation LLS:` heading in a non-`_impl`/non-`_asm` file, or `# Interface LLS:` in an `_impl`/`_asm` file (a component whose HLS has no `fulfills:` line is an interface; the one exception is an assembly spec, which uses the implementation LLS form)
  E  unknown `##` section (closed inventory: Data Types, Component-Provided Operations,
     Invariants, Non-Concerns for interfaces; Data Types, Composition, Behavioral
     Description, Invariants, Non-Concerns for implementations; term definitions
     between Data Types and Component-Provided Operations)
  E  section order deviates from the canonical order for the section kind
  E  interface section missing Data Types / Component-Provided Operations / Invariants
  E  implementation section missing Data Types / Behavioral Description / Invariants
  E  Data Types section does not open with exactly one Python code block
  E  comment or docstring inside a Python code block
  E  top-level annotated assignment without `TypeAlias` in a Data Types block
  E  single-field data class (use a type alias); a data class whose only field is a
     `Literal` discriminator (a union marker) is exempt
  E  `abc` abstract class used to express an interface (use `Protocol`)
  E  the interface's Protocol class is not last in the Data Types block
  E  operation documented under `### `name`` but not a method of the interface's Protocol class
  E  type name used in a code block but never defined or imported (`typing`/`dataclasses`/`enum` names included — `Protocol`, `TypeAlias`, `dataclass` must be imported, not assumed)
  E  type name redefined locally that a dependency (or another linted spec) already defines; import it from its owner's LLS
  E  type name imported from a dependency that does not define it (invented name, or import through a re-exporting interface)
  E  generic type name `Message`/`Result`/`Status`/`Data` defined in Data Types
  E  operation heading is not `### `name``
  E  operation missing one of Purpose / Preconditions / Postconditions / HLS Justification
  E  operation has no signature block under its `### `name`` heading (`def <name>(...)` in ```python)
  E  `TypedDict` used in a Data Types block (records are `@dataclass` or `TypeAlias`)
  E  `### ` heading inside any section other than Component-Provided Operations (Data Types included)
  E  implementation LLS mentions "client"
  E  imported module (non-stdlib) not listed in the dependency comment
  W  operation missing **Failure Handling:**
  W  one-word type name (use two descriptive words)
  W  type name names the representation (suffix `Key`/`Id`/`Text`/`Value`/`Data`/...) instead of the domain concept
  W  imported name (non-stdlib) never used in code or prose
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SPECS_DIR = ROOT / "update_with_ai" / "specs" / "low"
# External dependency docs: not low-level specs and not linted themselves,
# but nameable as dependency-comment entries (e.g. `- openai_api.md` for
# specs/external/openai_api.md).
EXTERNAL_DIR = ROOT / "update_with_ai" / "specs" / "external"

# Modules that are not specs and need no dependency-comment entry.
STDLIB_MODULES = {"__future__", "abc", "collections", "dataclasses", "enum", "typing"}

# Canonical subsection positions per section kind. Term-definition headings
# occupy position 1 (between Data Types and Component-Provided Operations).
INTERFACE_SECTIONS = {
    "Data Types": 0,
    "Component-Provided Operations": 2,
    "Invariants": 3,
    "Non-Concerns": 4,
}
IMPL_SECTIONS = {
    "Data Types": 0,
    "Composition": 1,
    "Behavioral Description": 2,
    "Invariants": 3,
    "Non-Concerns": 4,
}
TERM_DEF_RE = re.compile(r"^(Term definitions|.*\(term definition\))$")

# Guide: never generic `Message`, `Result`, `Status`, `Data`.
BANNED_TYPE_NAMES = {"Message", "Result", "Status", "Data"}

# One-word names like these are the clash-prone ones the guide warns about.
COMPOUND_RE = re.compile(r"[A-Z][a-z0-9]*|[a-z0-9]+")

errors: list[str] = []
warnings: list[str] = []


def err(f: Path, msg: str) -> None:
    errors.append(f"{f.name}: {msg}")


def warn(f: Path, msg: str) -> None:
    warnings.append(f"{f.name}: {msg}")


def stem_of(path: Path) -> str:
    return path.stem


# ---------------------------------------------------------------- parsing

def parse(text: str) -> list[tuple[int, str, list[str]]]:
    """Return [(level, heading, body_lines)] for `# ` and `## ` headings.

    `### ` lines are body content of the enclosing `## ` section.
    """
    parts: list[tuple[int, str, list[str]]] = []
    cur: tuple[int, str, list[str]] | None = None
    for line in text.splitlines():
        m2 = re.match(r"^## (.*)$", line)
        if m2:
            cur = (2, m2.group(1), [])
            parts.append(cur)
            continue
        m1 = re.match(r"^# (.*)$", line)
        if m1:
            cur = (1, m1.group(1), [])
            parts.append(cur)
            continue
        if cur is not None:
            cur[2].append(line)
    return parts


def grouped_sections(parts: list[tuple[int, str, list[str]]]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Group `## ` subsections under their enclosing `# ` heading."""
    groups: list[tuple[str, list[tuple[str, str]]]] = []
    cur: tuple[str, list[tuple[str, str]]] | None = None
    for level, heading, body in parts:
        if level == 1:
            cur = (heading, [])
            groups.append(cur)
        elif cur is not None:
            cur[1].append((heading, "\n".join(body)))
    return groups


def parse_comment(text: str) -> list[str] | None:
    """Return dependency entry filenames (e.g. 'inventory.md') from the
    leading comment, or None if the comment is missing or malformed."""
    first = text.splitlines()[0] if text.splitlines() else ""
    if not first.startswith("<!-- Dependencies"):
        return None
    end = text.find("-->")
    if end == -1:
        return None
    return re.findall(r"^\s*-\s*([\w]+\.md)\s*$", text[:end], re.M)


def check_comment_refs(f: Path, text: str, entries: list[str]) -> None:
    """The comment may contain only `- <name>.md` entry lines: any other
    spec filename inside it (an HLS file — a `specs/high/` reference — or an
    entry not on its own line) is an error — LLS files depend only on LLS
    files."""
    end = text.find("-->")
    if end == -1:
        return  # a malformed comment is reported by the caller
    comment = text[:end]
    for m in re.finditer(r"([\w]+\.md)", comment):
        line_start = comment.rfind("\n", 0, m.start()) + 1
        line_end = comment.find("\n", m.end())
        line = comment[line_start:line_end if line_end != -1 else len(comment)]
        if not (m.group(1) in entries and re.match(r"^\s*-\s*" + re.escape(m.group(1)) + r"\s*$", line)):
            err(f, f"dependency comment references {m.group(1)!r}, which is not a `- <name>.md` entry; LLS files depend only on LLS files")


def check_no_paths(f: Path, text: str) -> None:
    """Dependency-comment entries are bare `<name>.md` names, never file
    paths: an entry containing a path separator (`- foo/bar.md`) is an error —
    a file elsewhere in the repo is named by its bare stem, and the linter
    resolves it against the external docs when it is not a linted spec."""
    end = text.find("-->")
    if end == -1:
        return  # a malformed comment is reported by the caller
    comment = text[:end]
    for line in comment.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        entry = stripped[2:].strip()
        if "/" in entry or "\\" in entry:
            err(f, f"dependency comment entry {entry!r} is a file path; entries are bare `<name>.md` names (e.g. `- openai_api.md` for specs/external/openai_api.md)")


def check_comment_entries(f: Path, comment: list[str], files: list[Path], deps: list[str]) -> None:
    """Each comment entry must name a linted file, a specified module dep
    (the --deps list: the module_deps md files, direct only), or an external
    dependency doc under specs/external/."""
    resolvable = (
        {p.name for p in files}
        | {Path(d).name for d in deps}
        | {p.name for p in EXTERNAL_DIR.glob("*.md")}
    )
    for entry in comment:
        if entry not in resolvable:
            err(f, f"dependency comment lists {entry}, which is not a specified module dep (add it to module_deps) or an external doc (specs/external/)")


def check_deps_listed(f: Path, comment: list[str], deps: list[str]) -> None:
    """The comment is exactly module_deps: every specified module dep must be
    listed in the dependency comment (an entry that relies on transitive
    coverage is an error — the comment names only what is directly referred
    to in the spec)."""
    for d in deps:
        name = Path(d).name
        if name.endswith(".md") and name not in comment:
            err(f, f"module dep {name} (from module_deps) is not listed in the dependency comment")


def python_blocks(body: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", body, re.S)


# ---------------------------------------------------------------- checks

def _strip_strings(line: str) -> str:
    """Replace string literals with spaces so '#' or type tokens inside them
    are not mistaken for code."""
    return re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', lambda m: " " * len(m.group(0)), line)


def check_code_block(f: Path, code: str) -> None:
    """Comments and docstrings are prohibited inside code blocks (guide: Data Types)."""
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            err(f, f"comment inside code block: {stripped[:70]!r}")
            continue
        if "#" in _strip_strings(line):
            err(f, f"inline comment inside code block: {stripped[:70]!r}")
        if '"""' in line or "'''" in line:
            err(f, f"docstring inside code block: {stripped[:70]!r}")


def check_imports(f: Path, code: str, comment: list[str]) -> None:
    """Every non-stdlib import must be listed in the dependency comment.

    The module name in `from <module> import ...` is the comment entry's name
    with the `.md` suffix removed (an import of `from tool_provider import`
    maps to the `- tool_provider.md` entry). When the module is not listed,
    suggest the closest listed module: a wrong underscore variant
    (`tool_provider_low`) is a common mistake that leads to editing the comment
    instead of the import.
    """
    listed = {e[:-3] for e in comment if e.endswith(".md")}
    for m in re.finditer(r"^from\s+([A-Za-z_]\w*)\s+import", code, re.M):
        mod = m.group(1)
        if mod in STDLIB_MODULES:
            continue
        if mod + ".md" not in comment:
            hint = ""
            if listed:
                close = difflib.get_close_matches(mod, sorted(listed), n=1, cutoff=0.5)
                if close:
                    hint = f"; did you mean `from {close[0]} import` (the comment entry is `- {close[0]}.md`)?"
            err(f, f"imports '{mod}' but the dependency comment does not list {mod}.md{hint}")



def check_header(f: Path, text: str) -> None:
    first = next((p for p in parse(text) if p[0] == 1), None)
    if first is None:
        err(f, "missing '# Interface LLS: <name>' / '# Implementation LLS: <name>' heading")
        return
    m = re.match(r"^(Interface|Implementation) LLS: (.+)$", first[1])
    if m is None:
        err(f, f"first top-level heading must be '# Interface LLS: <name>' or '# Implementation LLS: <name>': {first[1]!r}")
        return
    stem = stem_of(f)
    if m.group(2) != stem:
        err(f, f"LLS heading name {m.group(2)!r} does not match filename stem {stem!r}")
    # A component whose HLS has no `fulfills:` line is an interface: its LLS
    # is an Interface LLS. Implementation LLS files are `<name>_impl.md` in
    # `specs/low/`; the one exception is an assembly spec (`<name>_asm.md`),
    # which has no `fulfills:` yet still uses the implementation LLS form
    # (it shares the implementation section inventory).
    impl_like = stem.endswith("_impl") or stem.endswith("_asm")
    if m.group(1) == "Implementation" and not impl_like:
        err(f, f"'# Implementation LLS: {stem}' in a non-`_impl`/non-`_asm` file: a component whose HLS has no `fulfills:` line is an interface (unless it is an assembly); its LLS is '# Interface LLS: {stem}'")
    elif m.group(1) == "Interface" and impl_like:
        err(f, f"'# Interface LLS: {stem}' in an `_impl`/`_asm` file: an implementation LLS is headed '# Implementation LLS: {stem}'")


def check_aliases(f: Path, code: str) -> None:
    """TypeAlias hygiene, generic names, and concept-based naming."""
    for line in code.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^=]+?)(?:\s*=\s*.*)?$", line)
        if m and not m.group(2).strip().startswith("TypeAlias"):
            err(f, f"annotated assignment without TypeAlias: {line.strip()[:70]!r} (use `X: TypeAlias = ...`)")
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?=[^\s\"'])(.*)$", line)
        if m and not m.group(2).strip().startswith("TypeVar"):
            err(f, f"bare type alias without TypeAlias: {line.strip()[:70]!r} (use `X: TypeAlias = ...`; only string constants and `TypeVar` declarations are bare assignments)")
    # Suffixes that name how a value is stored or referenced, not what it is.
    REPR_SUFFIXES = ("Key", "Id", "Text", "Value", "Data", "Info", "Record", "Json", "Dict", "List", "Str")
    for m in re.finditer(r"^class ([A-Za-z_]\w*)|^([A-Za-z_]\w*):\s*TypeAlias", code, re.M):
        name = m.group(1) or m.group(2)
        if name in BANNED_TYPE_NAMES:
            err(f, f"generic type name '{name}'; use a descriptive two-word name")
            continue
        if "TypeVar" in line_of(code, m.start()):
            continue
        if m.group(1) and re.search(r"\([^)]*\bProtocol\b", line_of(code, m.start())):
            continue  # Protocol class named after the component; two-word rule exempt
        words = COMPOUND_RE.findall(name)
        if len(words) < 2:
            warn(f, f"type name '{name}' is a single word; use two descriptive words (e.g. 'InventoryItem' rather than 'Item')")
        elif name.endswith(REPR_SUFFIXES):
            warn(f, f"type name '{name}' names the representation (suffix '{next(s for s in REPR_SUFFIXES if name.endswith(s))}'); name the domain concept (e.g. 'InventoryItem', not 'ItemKey')")


def line_of(code: str, pos: int) -> str:
    start = code.rfind("\n", 0, pos) + 1
    end = code.find("\n", pos)
    return code[start:end if end != -1 else len(code)]


def check_dataclasses(f: Path, code: str) -> None:
    """A data class that would carry a single field is a type alias instead."""
    lines = code.splitlines()
    i = 0
    while i < len(lines):
        if not re.match(r"^@(?:dataclasses\.)?dataclass", lines[i]):
            i += 1
            continue
        j = i + 1
        cm = re.match(r"^class ([A-Za-z_]\w*)", lines[j] if j < len(lines) else "")
        if cm is None:
            i += 1
            continue
        cls_name = cm.group(1)
        k = j + 1
        fields: list[tuple[str, str]] = []
        while k < len(lines) and (lines[k][:1] in (" ", "\t")):
            fm = re.match(r"^\s+([A-Za-z_]\w*)\s*:\s*(.+)$", lines[k])
            if fm and not lines[k].lstrip().startswith("def "):
                fields.append((fm.group(1), fm.group(2).split("=")[0].strip()))
            k += 1
        if len(fields) == 1:
            fname, anno = fields[0]
            if not (fname == "type" and "Literal" in anno):
                err(f, f"data class '{cls_name}' has a single field '{fname}'; use a type alias (`{cls_name}: TypeAlias = ...`)")
        i = k


def check_abc(f: Path, code: str) -> None:
    """Interfaces are Protocols; abc abstract classes are prohibited."""
    if re.search(r"\babc\.[A-Za-z_]+", code) or re.search(r"^from abc import", code, re.M):
        err(f, "abc abstract classes express interfaces; use `Protocol`")


def check_typeddict(f: Path, code: str) -> None:
    """Records are `@dataclass` classes or `TypeAlias` aliases; `TypedDict` is
    never used: a TypedDict cannot carry defaults, and its field shape is the
    same structure a dataclass or a type alias expresses (guide: Data Types).
    """
    if re.search(r"\bTypedDict\b", code):
        err(f, "'TypedDict' is used; records are `@dataclass` classes or `TypeAlias` aliases (a TypedDict cannot carry defaults)")


def protocol_methods(code: str) -> set[str] | None:
    """Method names declared by the interface's Protocol class (the last class).

    Returns None when the block declares no class at all (check_protocol_last
    reports the missing Protocol separately).
    """
    lines = code.splitlines()
    starts = [i for i, l in enumerate(lines) if re.match(r"^class ", l)]
    if not starts:
        return None
    methods: set[str] = set()
    for l in lines[starts[-1] + 1:]:
        m = re.match(r"^\s+def ([A-Za-z_]\w*)\(", l)
        if m:
            methods.add(m.group(1))
    return methods


# Built-in names that need no import; every other capitalized construct
# (typing/dataclasses/enum names) must be imported from its module.
BUILTIN_TYPES = {
    "str", "int", "float", "bool", "bytes", "bytearray",
    "list", "dict", "set", "frozenset", "tuple",
    "ValueError", "TypeError", "KeyError", "RuntimeError", "OSError",
    "Exception", "ImportError", "IndexError", "AttributeError",
    "FileNotFoundError", "NotADirectoryError",
    "None", "True", "False",
}

TYPING_NAMES = {
    "Any", "Literal", "Union", "Optional", "Protocol", "TypeAlias", "TypeVar",
    "Generic", "Callable", "Sequence", "Iterable", "Iterator", "AbstractSet",
    "FrozenSet", "Mapping", "MutableMapping", "Never", "NoReturn", "ClassVar",
    "Self", "Final", "overload", "NewType", "NamedTuple",
}

DATACLASS_NAMES = {"dataclass", "field"}

ENUM_NAMES = {"Enum", "IntEnum"}

IMPORT_MODULES = {
    name: "typing" for name in TYPING_NAMES
} | {name: "dataclasses" for name in DATACLASS_NAMES} | {name: "enum" for name in ENUM_NAMES}


def _imported_names(code: str) -> set[str]:
    """Names imported by a code block's `from X import ...` / `import X` lines."""
    names: set[str] = set()
    lines = code.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^from\s+([A-Za-z_]\w*)\s+import\s*(.*)$", lines[i])
        if m:
            clause = m.group(2)
            if "(" in clause:
                parts = [clause]
                while ")" not in clause and i + 1 < len(lines):
                    i += 1
                    clause = lines[i]
                    parts.append(clause)
                clause = " ".join(parts)
            for n in re.finditer(r"[A-Za-z_]\w*", clause):
                names.add(n.group(0))
        else:
            m = re.match(r"^import\s+([A-Za-z_]\w*)", lines[i])
            if m:
                names.add(m.group(1))
        i += 1
    return names


def block_names(blocks: list[str]) -> tuple[set[str], set[str]]:
    """Type names defined (classes, TypeAlias, TypeVar) and imported per file."""
    defined: set[str] = set()
    imported: set[str] = set()
    for code in blocks:
        for m in re.finditer(r"^class ([A-Za-z_]\w*)", code, re.M):
            defined.add(m.group(1))
        for m in re.finditer(r"^([A-Za-z_]\w*):\s*TypeAlias", code, re.M):
            defined.add(m.group(1))
        for m in re.finditer(r"^([A-Za-z_]\w*)\s*=\s*TypeVar", code, re.M):
            defined.add(m.group(1))
        imported |= _imported_names(code)
    return defined, imported


def imported_pairs(blocks: list[str]) -> list[tuple[str, str]]:
    """(module, name) pairs from `from <module> import ...` lines.

    Continuation lines of a parenthesized import are consumed so every name
    is collected exactly once.
    """
    pairs: list[tuple[str, str]] = []
    for code in blocks:
        lines = code.splitlines()
        i = 0
        while i < len(lines):
            m = re.match(r"^from\s+([A-Za-z_]\w*)\s+import\s*(.*)$", lines[i])
            if m:
                clause = m.group(2)
                if "(" in clause:
                    parts = [clause]
                    while ")" not in clause and i + 1 < len(lines):
                        i += 1
                        clause = lines[i]
                        parts.append(clause)
                    clause = " ".join(parts)
                for n in re.finditer(r"[A-Za-z_]\w*", clause):
                    pairs.append((m.group(1), n.group(0)))
            i += 1
    return pairs


def _strip_import_statements(text: str) -> str:
    """Return the text with `from X import ...` / `import X` statements removed.

    Used to decide whether an imported name is used elsewhere (in code or in
    prose); a mention inside the import statement itself is not a use.
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*from\s+[A-Za-z_]\w*\s+import", line) or re.match(r"^\s*import\s+[A-Za-z_]", line):
            if "(" in line and ")" not in line:
                i += 1
                while i < len(lines) and ")" not in lines[i]:
                    i += 1
            i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def check_import_owners(f: Path, text: str, owner_names: dict[str, set[str]]) -> None:
    """Every name imported from a dependency must be defined by that dependency.

    A type is imported from its owner's LLS; importing a name the owner does
    not define (an invented name, or a type imported through a re-exporting
    interface) is an error. Skipped for dependencies not among the linted
    files or the --deps closure (their definitions are unknown).
    """
    blocks = [code for _, _, body in parse(text) for code in python_blocks("\n".join(body))]
    for mod, name in imported_pairs(blocks):
        if mod in STDLIB_MODULES:
            continue
        owner_file = mod + ".md"
        if owner_file in owner_names and name not in owner_names[owner_file]:
            err(f, f"imports '{name}' from '{mod}', but {owner_file} does not define '{name}'; import it from its owner's LLS")


def check_unused_imports(f: Path, text: str) -> None:
    """A non-stdlib imported name is used somewhere: a signature, prose, or the
    fulfilled contract. A name that appears nowhere outside the import
    statement is a spurious import (guide: no spurious entries).
    """
    body = _strip_import_statements(text)
    blocks = [code for _, _, b in parse(text) for code in python_blocks("\n".join(b))]
    for mod, name in imported_pairs(blocks):
        if mod in STDLIB_MODULES:
            continue
        if not re.search(r"\b" + re.escape(name) + r"\b", body):
            warn(f, f"imports '{name}' from '{mod}' but never uses it in code or prose")


def check_undefined_types(f: Path, code: str, known: set[str], owner_names: dict[str, set[str]]) -> None:
    """Every capitalized type name in a code block is defined, imported, or a builtin.

    `typing`/`dataclasses`/`enum` names (Protocol, TypeAlias, dataclass, ...)
    must be imported from their module, exactly like any other name.
    """
    reported: set[str] = set()
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9_]*)\b", _strip_strings(code)):
        name = m.group(1)
        if name in known or name in BUILTIN_TYPES:
            continue
        if re.fullmatch(r"[A-Z]", name):
            continue  # single-letter type variable
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            continue  # ALL_CAPS constant name, not a type
        if name in reported:
            continue
        reported.add(name)
        owners = sorted(o for o, names in owner_names.items() if name in names)
        if owners:
            mod = owners[0][:-3]  # strip ".md"
            err(f, f"type name '{name}' is used but never defined or imported; import it from its owner ({owners[0]}, `from {mod} import {name}`) rather than defining it")
        elif name in IMPORT_MODULES:
            err(f, f"type name '{name}' is used but never defined or imported; import it from {IMPORT_MODULES[name]} (`from {IMPORT_MODULES[name]} import {name}`)")
        else:
            err(f, f"type name '{name}' is used but never defined or imported")


def spec_defined_names(text: str) -> set[str]:
    """Type names defined in a spec file's code blocks (classes, TypeAlias, TypeVar)."""
    names: set[str] = set()
    for code in python_blocks(text):
        for m in re.finditer(
            r"^class ([A-Za-z_]\w*)|^([A-Za-z_]\w*):\s*TypeAlias|^([A-Za-z_]\w*)\s*=\s*TypeVar|^([A-Za-z_]\w*)\s*=\s*(?=[^\s\"'])",
            code,
            re.M,
        ):
            names.add(m.group(1) or m.group(2) or m.group(3) or m.group(4))
    return names


def check_redefinitions(f: Path, text: str, owner_names: dict[str, set[str]]) -> None:
    """A type defined here that a dependency (or another linted spec) also
    defines is a redefinition: it must be imported from its owner's LLS."""
    local = spec_defined_names(text)
    for owner_file, names in sorted(owner_names.items()):
        for n in sorted(local & names):
            mod = owner_file[:-3]  # strip ".md"
            err(f, f"redefines '{n}', which is owned by {owner_file}; import it (`from {mod} import {n}`) instead of redefining")


def check_protocol_last(f: Path, code: str) -> None:
    """The interface's Protocol class is last in the Data Types block."""
    class_lines = [l for l in code.splitlines() if re.match(r"^class ", l)]
    if class_lines and not re.search(r"Protocol", class_lines[-1]):
        err(f, f"the interface's Protocol class must be last in the Data Types block; last class is {class_lines[-1].strip()!r}")


def check_data_types(f: Path, body: str, comment: list[str], is_impl: bool) -> None:
    blocks = python_blocks(body)
    if len(blocks) != 1:
        err(f, f"## Data Types must open with exactly one Python code block (found {len(blocks)})")
    if not blocks:
        return
    code = blocks[0]
    check_code_block(f, code)
    check_imports(f, code, comment)
    check_aliases(f, code)
    check_dataclasses(f, code)
    check_abc(f, code)
    check_typeddict(f, code)
    if not is_impl:
        check_protocol_last(f, code)


def op_chunks(body: str) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    cur_name: str | None = None
    cur: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^### `([^`]+)`", line)
        if m:
            if cur_name is not None:
                chunks.append((cur_name, "\n".join(cur)))
            cur_name = m.group(1)
            cur = []
        else:
            cur.append(line)
    if cur_name is not None:
        chunks.append((cur_name, "\n".join(cur)))
    return chunks


def check_operations(f: Path, body: str) -> None:
    for line in body.splitlines():
        if re.match(r"^### ", line) and not re.match(r"^### `[^`]+`$", line):
            err(f, f"operation heading must be `### `name``: {line.strip()!r}")
    chunks = op_chunks(body)
    if not chunks:
        err(f, "## Component-Provided Operations contains no operations")
        return
    for name, chunk in chunks:
        for block in ("**Purpose:**", "**Preconditions:**", "**Postconditions:**", "**HLS Justification:**"):
            if block not in chunk:
                err(f, f"operation '{name}' is missing its {block} block")
        if "**Failure Handling:**" not in chunk:
            warn(f, f"operation '{name}' has no **Failure Handling:** block")
    check_operation_signatures(f, body)


def check_operation_signatures(f: Path, body: str) -> None:
    """Each `### `name`` heading is followed by a ```python block echoing
    `def <name>(...)` (guide: Lint checks — the signature block is the
    operation's contract in code form; the template shows it)."""
    for m in re.finditer(r"^### `([^`]+)`", body, re.M):
        name = m.group(1)
        after = body[m.end():].lstrip("\n")
        if not after.startswith("```python"):
            err(f, f"operation '{name}' is missing its signature block; echo the signature as `def {name}(...) -> ...` in a ```python block directly under the heading")
            continue
        fence_end = after.find("```", 3)
        if fence_end == -1:
            err(f, f"operation '{name}' signature block is unclosed")
            continue
        code = after[3:fence_end]
        if not re.search(r"def\s+" + re.escape(name) + r"\s*\(", code):
            err(f, f"operation '{name}' signature block does not declare `def {name}(`")


def check_sections(f: Path, parts: list[tuple[int, str, list[str]]], comment: list[str]) -> None:
    for h1, subs in grouped_sections(parts):
        if not h1.startswith(("Interface LLS:", "Implementation LLS:")):
            continue  # header problems are reported by check_header
        is_impl = h1.startswith("Implementation LLS:")
        allowed = IMPL_SECTIONS if is_impl else INTERFACE_SECTIONS
        names = [h for h, _ in subs]
        for h in names:
            if h not in allowed and not TERM_DEF_RE.match(h):
                err(f, f"unknown section '## {h}' in an {'implementation' if is_impl else 'interface'} LLS")
        def pos(h: str) -> int | None:
            if h in allowed:
                return allowed[h]
            return 1 if TERM_DEF_RE.match(h) else None
        positions = [pos(h) for h in names]
        if None not in positions and positions != sorted(positions):
            err(f, f"section order {names} deviates from the canonical order for an {'implementation' if is_impl else 'interface'} LLS")
        for required in (["Data Types", "Component-Provided Operations", "Invariants"]
                         if not is_impl else ["Data Types", "Behavioral Description", "Invariants"]):
            if required not in names:
                err(f, f"{'implementation' if is_impl else 'interface'} LLS section missing '## {required}'")
        dt_code = ""
        ops_body = ""
        for h, body in subs:
            if h == "Component-Provided Operations":
                check_operations(f, body)
                ops_body = body
            else:
                # `### ` headings appear only under Component-Provided
                # Operations: term definitions are `## <Name> (term definition)`
                # headings between Data Types and Component-Provided Operations,
                # never `### ` headings inside another section.
                if re.search(r"^### ", body, re.M):
                    err(f, f"`### ` heading inside '## {h}'; `### ` headings appear only under Component-Provided Operations")
                if h == "Data Types":
                    check_data_types(f, body, comment, is_impl)
                    blocks = python_blocks(body)
                    dt_code = blocks[0] if blocks else ""
        if not is_impl and dt_code and ops_body:
            methods = protocol_methods(dt_code)
            if methods is not None:
                for name, _ in op_chunks(ops_body):
                    if name not in methods:
                        err(f, f"operation '{name}' is documented but not a method of the interface's Protocol class")
        if is_impl and re.search(r"\bclient\b", "\n".join(b for _, b in subs), re.I):
            err(f, "implementation LLS mentions 'client'")


# ---------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    deps: list[str] = []
    rest: list[str] = []
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--deps":
            i += 1
            while i < len(argv) and argv[i] != "--":
                deps.append(argv[i])
                i += 1
        elif arg == "--":
            rest.extend(argv[i + 1:])
            break
        else:
            rest.append(argv[i])
        i += 1

    files = [Path(p) for p in rest] or sorted(SPECS_DIR.glob("*.md"))
    for f in files:
        text = f.read_text(encoding="utf-8")
        check_header(f, text)
        first = text.splitlines()[0] if text.splitlines() else ""
        comment = parse_comment(text)
        if comment is None:
            if first.startswith("<!-- Dependencies"):
                err(f, "malformed dependency comment: expected `<!-- Dependencies (md files to read alongside this one): ... -->`")
            elif "<!-- Dependencies" in text:
                err(f, "the dependency comment must be the first line of the file, before `# Interface LLS:` / `# Implementation LLS:`")
            else:
                err(f, "missing dependency comment on the first line: `<!-- Dependencies (md files to read alongside this one): ... -->`")
            comment = []
        else:
            check_comment_refs(f, text, comment)
            check_no_paths(f, text)
            check_comment_entries(f, comment, files, deps)
            check_deps_listed(f, comment, deps)
        parts = parse(text)
        for level, heading, body in parts:
            if level == 2 and heading == "Data Types":
                continue  # handled per section kind in check_sections
            for code in python_blocks("\n".join(body)):
                check_code_block(f, code)
                check_imports(f, code, comment)
        check_sections(f, parts, comment)

        blocks = [code for level, heading, body in parts for code in python_blocks("\n".join(body))]
        defined, imported = block_names(blocks)
        known = defined | imported

        # Ownership map: every other linted file and every --deps closure
        # member defines types that must be imported, never redefined.
        owner_sources: dict[str, Path] = {}
        for p in files:
            if p != f:
                owner_sources[p.name] = p
        for d in deps:
            dp = Path(d)
            if dp.name.endswith(".md") and dp.name not in owner_sources:
                owner_sources[dp.name] = dp
        owner_names: dict[str, set[str]] = {}
        for name, p in owner_sources.items():
            if p.exists():
                owner_names[name] = spec_defined_names(p.read_text(encoding="utf-8"))

        check_import_owners(f, text, owner_names)
        check_unused_imports(f, text)
        for code in blocks:
            check_undefined_types(f, code, known, owner_names)
        check_redefinitions(f, text, owner_names)

    for w in warnings:
        print(f"W {w}")
    for e in errors:
        print(f"E {e}")
    print(f"\n{len(files)} files, {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
