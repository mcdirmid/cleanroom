# Cleanroom Grounding Specification Format: Python Interface Stubs (`.pyi`)

## 1. Executive Summary & Design Philosophy

This document defines **Cleanroom's New Grounding Format**, superseding the legacy 4-column Markdown tables (`type | name | signature | comment`) previously stored in `grounding_new/`.

Grounding is the formal ontological bridge between literate High-Level Specifications (HLS prose) and Low-Level Specifications (LLS / library code). While the HLS is written in fluid prose designed for architectural reasoning, the **grounding specification** formalizes the exact structural contract: active singleton/poly services, passive data types, closed variants, type signatures, and behavioral requirement contracts.

The new grounding format transitions Cleanroom from fragile Markdown tables to native Python interface stubs (**`.pyi`**):
- **Clean Architectural Split (`framework.py` vs. `.pyi`)**:
  - `framework.py`: Written once as shared infrastructure defining the structural decorator tags (`@singleton_type`, `@poly_type`, `@data_type`, `@variant`, `@override`).
  - `spec.pyi`: Pure, code-free interface stubs. Method and property bodies contain strictly an optional docstring followed by an ellipsis (`...`).
- **Why Custom "By-Hand" AST Checking Replaces Pyright**:
  External type checkers like Pyright are designed to verify that *executable implementation code* matches type signatures. In pure `.pyi` grounding stubs where all bodies are `...`, Pyright only checks basic Python syntax (which Python's built-in `ast.parse` already checks for free) while creating friction over custom domain meta-types unless heavily configured. Instead, Cleanroom uses a custom, deterministic AST tool (`grounding_tool.py`) that performs "by-hand" symbol resolution, catches typos in type names, verifies `@override` parity against parent classes, and enforces domain DSL constraints.
- **Static AST Reflection (Zero Runtime Execution)**: Because Python's runtime interpreter never loads or executes `.pyi` stubs during normal execution, all grounding inspection, linting, and inheritance are performed via static AST traversal (`ast.parse`). Specifications are never imported or executed at runtime, guaranteeing absolute purity, crash resilience, and zero side-effects.
- **Human-Readable Compiler Diagnostics**: The custom AST linter outputs standard compiler-style diagnostics with exact file paths, line numbers, and column offsets (`file.pyi:24:12: error: ...`).
- **Deterministic Zero-Token Requirements Inheritance**: Rather than burning LLM tokens to summarize or copy down requirements across class hierarchies (which is slow, expensive, and prone to hallucinations), a deterministic Python tool (`grounding_tool.py --sync`) traverses the AST and Method Resolution Order (MRO), copying down parent requirements programmatically with 100% reliability in milliseconds.
- **Co-located Behavioral Contracts**: Requirements and assumptions are embedded directly into class and method docstrings under structured `Assumptions:` and `Requirements:` blocks, eliminating disconnected requirement lists.

---

## 2. Infrastructure Split & Structural Standards

### 2.1 The Split: `framework.py` vs. Grounding Stubs (`.pyi`)

To maintain clean separation between infrastructure code and pure specification declarations, the environment is strictly split into two parts:

#### 1. Core Framework Infrastructure (`framework.py`)
Defined once in the Cleanroom toolchain. It provides lightweight decorator implementations so the Python environment is syntactically sound:

```python
# framework.py
"""Cleanroom Specification Framework: Structural markers for pure .pyi groundings."""

from typing import Any, Callable, Literal, TypeVar

T = TypeVar("T")
LifecycleTier = Literal["system", "agent_session"]

def singleton_type(lifecycle: LifecycleTier = "agent_session") -> Callable[[type[T]], type[T]]:
    """Marks an active service as a singleton within its lifecycle tier ('system' or 'agent_session')."""
    def decorator(cls: type[T]) -> type[T]:
        return cls
    return decorator

def poly_type(cls: type[T]) -> type[T]:
    """Marks an active service as an open polymorphic multiton interface."""
    return cls

def data_type(cls: type[T]) -> type[T]:
    """Marks a passive structural value type with value equality."""
    return cls

def variant(cls: type[T]) -> type[T]:
    """Marks a closed sum-type variant extending a data type or variant."""
    return cls

def operation(func: Callable[..., Any]) -> Callable[..., Any]:
    """Marks a member as an active operation on a service or data type."""
    return func

def override(func: Callable[..., Any]) -> Callable[..., Any]:
    """Marks an operation or property as overriding an inherited contract."""
    return func
```

#### 2. Pure Grounding Stubs (`<component>.pyi`)
Every grounding specification is a `.pyi` file that imports its structural tags from `framework`:

```python
# tool_provider.pyi
from framework import data_type, singleton_type, variant, override
```

---

### 2.2 Structural Kinds (Class-Level Decorators)
Active services, passive records, and closed variants are classified using class-level decorators:

| Ontological Kind | Python Syntax | Description |
| :--- | :--- | :--- |
| `singleton type` | `@singleton_type("system")`<br>`@singleton_type("agent_session")` | Singular active service with process (`"system"`) or session (`"agent_session"`) lifetime; singularly addressable via container. Explicit lifecycle argument required. |
| `poly type` | `@poly_type` | Polymorphic active service; open multiton interface with multiple co-existing instances. Takes **no** lifecycle designator because polymorphic types do not correspond to concrete runtime objects. |
| `data type` | `@data_type` | Passive value object, entity identifier, or structural record with value equality. |
| `variant` | `@variant` | Discriminated sum-type variant / closed sub-classification extending a `@data_type` or another `@variant`. |

### 2.3 Member Declarations & Pure Body Rule
All members of a type are declared as methods or property-decorated methods with strict structural bodies:

- **Properties**: Decorated with `@property`. The method takes only `self` and declares its return type annotation.
- **Operations**: Decorated with `@operation`. Standard methods taking `self` and typed positional arguments, declaring a return type annotation. Every non-property method MUST be decorated with `@operation`.
- **Overrides & Inherited Members**: When an implementation or subtype realizes, specializes, or inherits a member from an ancestor, the method is decorated with `@override` (alongside `@property` or `@operation`). Missing overrides are synthesized automatically by tooling. Stale overrides without fresh contracts are pruned automatically when ancestor members are removed; stale overrides with fresh contracts raise an error.
- **Pure Body Rule**: Every property and operation body must contain strictly an optional docstring followed by an ellipsis (`...`). Statements such as `pass`, `return`, assignments, and expressions are forbidden.

### 2.4 Type Annotations & Signatures
Signatures utilize standard Python type hinting:
- Primitive types: `str`, `int`, `bool`, `float`.
- Meta-types and sum types: `Type`, `Union[str, int]`, `Optional[str]`.
- Collections: `Set[T]` for unordered sets, `List[T]` for ordered sequences, `Tuple[A, B]` for paired records.
- Forward references and self-references: Enclosed in strings (e.g. `-> "FileAlias"`).
### 2.5 Class Naming & Implementation Modules (`_impl.pyi`)
When a grounding module implements an abstract service defined in a sibling specification (e.g. `agent_runner_impl.pyi` implementing `agent_runner.pyi`), the implementation class preserves exact 1:1 name parity with the interface rather than adding an artificial `Impl` suffix.

To avoid name collisions, the implementation module imports the interface module directly and qualifies the base class:

```python
# agent_runner_impl.pyi
import agent_runner
from framework import singleton_type, override

@singleton_type("agent_session")
class AgentRunner(agent_runner.AgentRunner):
    """
    PURPOSE:
    Implements agent runner with model completions and continuation turns.
    """
    ...
```

### 2.6 Data Types, Structural Equality, and Construction Invariants
In Cleanroom, data types are passive value objects evaluated by structural equality. Consequently, **empty or token data types are strictly prohibited**:
- Every `@data_type` and `@variant` MUST declare at least one property that participates in its structural identity (or subclass a data type that does).
- Any entity previously declared without properties (such as `Node`) is defective. In Cleanroom, `Node` explicitly declares an `address: str` property to establish its identity.

#### `@dataclass(frozen=True)` & Constructor Policies
Data types and closed variants are represented in `.pyi` grounding stubs using the standard `@dataclass` decorator in conjunction with `@data_type` or `@variant`:
1. **Direct Public Construction (`init=True`)**:
   - Leaf data types that external callers can instantiate directly are decorated with `@dataclass(frozen=True)` (or `@dataclass(frozen=True, init=True)`).
   - They define a matching `def __init__(self, ...): ...` method signature establishing the positional parameters accepted during instantiation.
2. **Service-Constructed Data Types (`init=False`)**:
   - When a data type represents an entity whose instantiation must be guarded, validated, or mapped exclusively through designated service operations (such as `file_paths.HostPath`, `file_paths.WorkspacePath`, or `file_alias.FileAlias`), it is decorated with `@dataclass(frozen=True, init=False)`.
   - It **omits** `def __init__` in the `.pyi` specification. This guarantees callers cannot bypass system validation rules by calling a default constructor.
3. **Sum-Type Roots and Base Variants**:
   - Base data types with variants and sum-type roots never declare `def __init__`. Instances can only be created from leaf data types without variants or leaf variant branches.

### 2.7 Canonical Type Mapping
Informal type strings from legacy 4-column tables map deterministically to standard Python `typing` constructs:

| Legacy Table String | Canonical `.pyi` Type | Notes |
| :--- | :--- | :--- |
| `string` | `str` | Primitive string |
| `boolean` | `bool` | Primitive boolean |
| `integer` | `int` | Primitive integer |
| `None` | `None` | Null / unit return |
| `Type` | `Type` | Meta-type reference (from `typing import Type`) |
| `X or absent` / `X or None` | `Optional[X]` | Optional value |
| `X or Y or None` | `Optional[Union[X, Y]]` | Multi-type optional union |
| `(A, B)` | `Tuple[A, B]` | Fixed-length tuple / paired record |
| `Set of X` | `Set[X]` | Unordered collection |
| `List of X` | `List[X]` | Ordered sequence |
| `a.B` (qualified symbol) | `B` (via `from a import B`) | Direct imported symbol |

### 2.8 Reflection Model: Static AST Reflection vs. Runtime Reflection

A foundational architectural principle of Cleanroom groundings is how tools inspect specifications:

#### Why Runtime Reflection Fails for `.pyi`
The standard Python runtime interpreter never executes or loads `.pyi` stub files during normal module execution. If code calls `import` followed by runtime reflection (`inspect.getmembers()`, `getattr()`, or `hasattr()`), Python resolves symbols against the underlying `.py` implementation or runtime module, completely bypassing the `.pyi` stub file. Furthermore, attempting to execute specifications at runtime would violate Cleanroom's guarantee that groundings are zero-execution structural declarations.

#### The Static AST Reflection Engine
Because `.pyi` files are plain text files containing syntactically valid Python, all inspection, validation, and metadata extraction is performed **statically** using Python's built-in `ast` module. The toolchain reads `.pyi` files from disk and walks the Abstract Syntax Tree without ever importing or executing them:

```python
import ast

def inspect_grounding_stub(filepath: str):
    """Statically reflects over a .pyi stub without runtime execution."""
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            # Extract class-level structural kind decorators (@singleton_type, @variant, etc.)
            decorators = [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
            print(f"Grounding Class: {node.name} | Decorators: {decorators}")

            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    # Extract member-level decorators (@property, @override, etc.)
                    m_decorators = [d.id for d in item.decorator_list if isinstance(d, ast.Name)]
                    print(f"  Member: {item.name} | Decorators: {m_decorators}")
```

#### Key Guarantees of Static Reflection
1. **Zero Execution Safety**: Parsing the AST never executes module-level code, constructors, or imports. Untrusted or in-progress specifications cannot produce side effects or crash the environment.
2. **Lossless Structural Fidelity**: The AST preserves exact decorator identities, source line numbers, column offsets, docstring formatting, and argument types directly as authored.
3. **No Ambient Runtime Dependencies**: Static inspection operates purely on the syntax tree, requiring no module initialization, virtual environments, or external interpreters.

---

## 3. The Pure Docstring Pattern & Contract Grammar

In Cleanroom groundings, **all free-floating `#` comments are strictly forbidden**. All purposes, ontological justifications, operational assumptions, and behavioral requirements live exclusively inside docstrings (`"""..."""`).

### 3.1 Why the Pure Docstring Pattern Wins
1. **Guaranteed Structural Location**: Free-floating `#` comments can appear arbitrarily (above a class, between arguments, or trailing a line), making regex or text parsing fragile. By definition, a docstring is strictly the very first statement inside a class or function body (`node.body[0]`), giving the static AST tools a predictable, invariant location to inspect and mutate.
2. **Zero External Dependencies**: Python's native `ast` module handles docstrings as first-class AST nodes (`ast.Expr(value=ast.Constant(value=str))`). We do not need heavy third-party CST libraries like `libcst`.
3. **Lossless `ast.unparse()` Serialization**: While `ast.unparse()` strips unattached `#` comments, it preserves docstrings verbatim with clean triple-quote formatting and correct indentation.

### 3.2 Structure of a Specification Docstring
Every class, property, and operation docstring follows a rigid, literate header structure:

```python
"""
PURPOSE:
<Ontological Justification Sentence(s)>

INHERITANCE:
- <BaseInterfaceOrSupertype>: <Justification comment from is-a row>

GROUNDING_ARGUMENT:
<Grounding rationale establishing access to values, state, collaborators, or external sources (implementation files only)>

FRESH_ASSUMPTIONS:
- <Precondition sentence 1>
- <Precondition sentence 2>

INHERITED_ASSUMPTIONS:
- [<AncestorName>] <Propagated precondition 1>
- [<AncestorName>] <Propagated precondition 2>

FRESH_REQUIREMENTS:
- <Behavioral guarantee or failure-handling sentence 1>
- <Behavioral guarantee or failure-handling sentence 2>

INHERITED_REQUIREMENTS:
- [<AncestorName>] <Propagated requirement 1>
- [<AncestorName>] <Propagated requirement 2>
"""
```

### 3.3 Placement Rules
1. **Class-Level Docstrings**:
   - `PURPOSE:` justifies why the type exists in the structural model (replacing the legacy table's `comment` column).
   - `INHERITANCE:` explicitly preserves justifications for secondary base classes and implemented interfaces (preserving legacy `is-a` table comments).
   - `GROUNDING_ARGUMENT:` (only in `*_impl.pyi` specifications on `@singleton_type` classes): details the derivation path, collaborator wiring, and lifecycle scope necessary to satisfy its requirements. The default assumption is that the service is well-grounded; boilerplate prefixes such as "Well-grounded." are omitted. The special case is an ungrounded component or gap, which must be explicitly flagged, explaining what the gap is. Collaborators must be imported and reside in the same or more general lifecycle tier (`agent_session` can access `system`, but not vice-versa).
   - `FRESH_ASSUMPTIONS:` list environmental preconditions, scope boundaries, and lifecycle invariants governing the type.
   - `INHERITED_ASSUMPTIONS:` populated by the sync engine with assumptions propagated from ancestor classes.
   - `FRESH_REQUIREMENTS:` list global type invariants or value constraints (e.g. string formatting or structural equality).
   - `INHERITED_REQUIREMENTS:` populated by the sync engine with invariants propagated from ancestor classes.
2. **Member-Level Docstrings (Properties and Operations)**:
   - `PURPOSE:` provides the ontological justification for the member, weaving in authentic language from the HLS prose.
   - `GROUNDING_ARGUMENT:` (only in `*_impl.pyi` specifications on members of `@singleton_type` classes):
     - Formatted directly as the rationale (omitting ritual "Well-grounded." boilerplate). The argument explains *why* the member is grounded. Any ungrounded condition or gap is explicitly flagged.
     - For operations: details how the operation accesses necessary collaborator services, internal state, and arguments to meet its requirements.
     - For properties: details where property values originate (e.g. delegated from another collaborator, populated via mutable operations, configured via operations). Vague phrases such as "loaded from external data source" or "derived from environment" are strictly prohibited; external state derivation must specify the 3-part derivation path: (1) context provider collaborator, (2) loader service operation, and (3) return type transformation. All referenced collaborators must be imported.
   - `FRESH_ASSUMPTIONS:` list operation preconditions (what callers must guarantee before invoking the operation). Violating an assumption results in undefined behavior.
   - `INHERITED_ASSUMPTIONS:` preconditions propagated from ancestor declarations of this member.
   - `FRESH_REQUIREMENTS:` list guaranteed postconditions, state transitions, validation boundaries, return values, and explicit failure-handling contracts.
   - `INHERITED_REQUIREMENTS:` behavioral contracts propagated from ancestor declarations of this member.

### 3.4 External Boundary Components (`_ext`) & Orphan Requirements (`__orphan__()`)

#### External Boundary Components (`_ext`)
External boundary components (`high/<name>_ext.md`) specify interactions with the host operating system, third-party APIs (such as OpenAI endpoints), build system schemas, and foreign file formats. Rather than defining concrete Python API types or requiring a `.pyi` grounding stub, external components serve as a declarative **bill of sale on the grounding gaps they cover**:
1. **Section Structure**: Consists strictly of `## Purpose` (with an `**Out of scope:**` disclaimer) and `## Grounding Gaps Covered`. They do not contain a `## Types and Behavior` section.
2. **Zero Semantic Italics**: Written in clean declarative prose with no semantic italics (`*term*`).
3. **No Grounding Document**: External components lack `.pyi` files in `grounding/`. The high-level specification itself defines the external domain knowledge and protocols.
4. **Grounding Import**: Implementation specifications that rely on external mechanics import the external component at module scope (`import <name>_ext`), establishing that their operations and properties are grounded by the external knowledge described in the `_ext` specification.

#### Orphan Requirements & Top-Level `__orphan__()` Stubs
In Cleanroom, behavioral requirements describe active interactions, communications, or operations. Passive `@data_type` records are value objects and cannot own active behavioral contracts.

When behavioral requirements cannot be attributed to any active singleton service in a specification module, those requirements are captured in an unnested top-level `__orphan__()` function:

```python
def __orphan__() -> None:
    """
    PURPOSE:
    Captures orphaned requirements not associated with an active service.

    FRESH_REQUIREMENTS:
    - An orphaned requirement describes behavior not attributable to a singleton service.
    """
    ...
```

**Grammar & Invariants for `__orphan__()`**:
1. **Unnested Only**: Must be a top-level function at module scope; nesting inside a class is prohibited.
2. **Singular**: At most one `__orphan__()` function may exist per specification module.
3. **No Arguments or Decorators**: Must take no parameters (`()`) and have no decorators.
4. **Return Annotation**: Return type annotation must be `None` (or omitted).
5. **Pure Body**: Body must consist strictly of an optional docstring followed by an ellipsis (`...`).
6. **Docstring Headers**: Must contain `PURPOSE:` and `FRESH_REQUIREMENTS:`. Cannot contain `GROUNDING_ARGUMENT:`, `INHERITANCE:`, `INHERITED_ASSUMPTIONS:`, or `INHERITED_REQUIREMENTS:`.
7. **Tooling Conservation**: `grounding_tool.py --sync` and `--check` preserve `__orphan__()` verbatim without drift or modification.

#### Assembly Specifications & Subsystem Initialization Stubs (`__initialize__()`)
Assembly components (`<name>_asm.md`) define subsystem composition and lifecycle singleton registration. Their grounding stubs (`grounding/<name>_asm.pyi`) define strictly an unnested top-level `__initialize__()` function:

```python
def __initialize__() -> None:
    """
    PURPOSE:
    Assembles dag graph cleaning components into the dag assembly.

    CONSTITUENTS:
    - dag_cleaner_impl
    """
    ...
```

**Grammar & Invariants for `__initialize__()`**:
1. **Unnested Only**: Must be a top-level function at module scope in assembly grounding files (`<name>_asm.pyi`).
2. **Singular**: At most one `__initialize__()` function may exist per assembly specification module.
3. **No Arguments or Decorators**: Must take no parameters (`()`) and have no decorators.
4. **Return Annotation**: Return type annotation must be `None` (or omitted).
5. **Pure Body**: Body must consist strictly of an optional docstring followed by an ellipsis (`...`).
6. **Docstring Headers**: Must contain strictly `PURPOSE:` and `CONSTITUENTS:` listing the constituent implementation and sub-assembly modules.

---

## 4. Reference Implementation: `file_alias.pyi`

Below is the definitive reference specification demonstrating all structural conventions, decorators, type signatures, dataclass construction policies, and co-located requirements in a `.pyi` stub file:

```python
# file_alias.pyi
from typing import Protocol, Type
from framework import data_type, operation, override, singleton_type, variant
from dataclasses import dataclass
import dag_storage
import file_paths
import tool_provider

@data_type
class FileContent(str):
    """
    PURPOSE:
    Introduces file content to represent data read from or stored in a file
    """
    ...

@data_type
class RegexPattern(str):
    """
    PURPOSE:
    Introduces regex pattern as the pattern used to search in files
    """
    ...

@singleton_type('agent_session')
class AliasManager(tool_provider.ParameterConverter, Protocol):
    """
    PURPOSE:
    Defined as an agent session service configured with a workspace root that sanitizes output text

    INHERITANCE:
    - tool_provider.ParameterConverter: Established that the alias manager is a parameter converter for file aliases, allowing file aliases to be used as tool parameters
    """

    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        """
        PURPOSE:
        Established that the alias manager is configured with a workspace root
        """
        ...

    @property
    @override
    def actual_type(self) -> Type:
        """
        PURPOSE:
        Sets the converter actual type for the alias manager to file alias
        """
        ...

    @property
    @override
    def wire_type(self) -> tool_provider.WireType:
        """
        PURPOSE:
        Sets the converter wire type for the alias manager to string
        """
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> 'FileAlias':
        """
        PURPOSE:
        Converts a wire type string to a file alias, producing an unbound file if the short name is not found

        FRESH_REQUIREMENTS:
        - Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.
        """
        ...

    @operation
    def sanitize_text(self, text: str) -> str:
        """
        PURPOSE:
        Provides that the alias manager sanitizes text by masking occurrences of host paths with short names

        FRESH_REQUIREMENTS:
        - Sanitizing text masks occurrences of host paths with the corresponding file alias short names.
        """
        ...

@dataclass(frozen=True, init=False)
@data_type
class FileAlias:
    """
    PURPOSE:
    Defined to represent a session file, hiding physical filesystem details and paths from the agent

    FRESH_ASSUMPTIONS:
    - The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

    FRESH_REQUIREMENTS:
    - A file alias displays itself by its short name when converted to a string.
    """

    @property
    def short_name(self) -> str:
        """
        PURPOSE:
        Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
        """
        ...

@dataclass(frozen=True, init=False)
@variant
class BoundFile(FileAlias):
    """
    PURPOSE:
    Classifies bound file as a file alias mapped to an actual workspace file

    INHERITED_ASSUMPTIONS:
    - [FileAlias] The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

    INHERITED_REQUIREMENTS:
    - [FileAlias] A file alias displays itself by its short name when converted to a string.
    """

    @property
    def workspace_path(self) -> file_paths.WorkspacePath:
        """
        PURPOSE:
        Established that each bound file has a workspace path
        """
        ...

    @property
    def owning_node(self) -> dag_storage.Node:
        """
        PURPOSE:
        Established that each bound file has an owning node
        """
        ...

    @property
    @override
    def short_name(self) -> str:
        """
        PURPOSE:
        Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
        """
        ...

@dataclass(frozen=True)
@variant
class ReadOnlyFile(BoundFile):
    """
    PURPOSE:
    Classifies read-only file as a bound file restricted to inspection

    INHERITED_ASSUMPTIONS:
    - [FileAlias] The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

    INHERITED_REQUIREMENTS:
    - [FileAlias] A file alias displays itself by its short name when converted to a string.
    """

    def __init__(self, short_name: str, workspace_path: file_paths.WorkspacePath, owning_node: dag_storage.Node) -> None:
        ...

    @property
    @override
    def workspace_path(self) -> file_paths.WorkspacePath:
        """
        PURPOSE:
        Established that each bound file has a workspace path
        """
        ...

    @property
    @override
    def owning_node(self) -> dag_storage.Node:
        """
        PURPOSE:
        Established that each bound file has an owning node
        """
        ...

    @property
    @override
    def short_name(self) -> str:
        """
        PURPOSE:
        Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
        """
        ...

@dataclass(frozen=True)
@variant
class ReadWriteFile(BoundFile):
    """
    PURPOSE:
    Classifies read-write file as a bound file permitted for inspection and modification

    INHERITED_ASSUMPTIONS:
    - [FileAlias] The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

    INHERITED_REQUIREMENTS:
    - [FileAlias] A file alias displays itself by its short name when converted to a string.
    """

    def __init__(self, short_name: str, workspace_path: file_paths.WorkspacePath, owning_node: dag_storage.Node) -> None:
        ...

    @property
    @override
    def workspace_path(self) -> file_paths.WorkspacePath:
        """
        PURPOSE:
        Established that each bound file has a workspace path
        """
        ...

    @property
    @override
    def owning_node(self) -> dag_storage.Node:
        """
        PURPOSE:
        Established that each bound file has an owning node
        """
        ...

    @property
    @override
    def short_name(self) -> str:
        """
        PURPOSE:
        Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
        """
        ...

@dataclass(frozen=True)
@variant
class UnboundFile(FileAlias):
    """
    PURPOSE:
    Classifies unbound file as a file alias that is not mapped to an actual file

    INHERITED_ASSUMPTIONS:
    - [FileAlias] The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

    INHERITED_REQUIREMENTS:
    - [FileAlias] A file alias displays itself by its short name when converted to a string.
    """

    def __init__(self, short_name: str) -> None:
        ...

    @property
    @override
    def short_name(self) -> str:
        """
        PURPOSE:
        Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
        """
        ...
```

---

## 5. Toolchain Architecture: By-Hand AST Verification & Zero-Token Inheritance

The Cleanroom grounding toolchain consists of three deterministic pipeline passes implemented via Python's standard `ast` module. It eliminates external type-checker dependencies (like Pyright), enforces custom domain DSL rules "by hand," outputs human-readable compiler errors with exact line numbers, and copies down requirements with zero LLM token consumption.

```
+---------------------------------------------------+
|            Grounding Stub (.pyi)                  |
+---------------------------------------------------+
                          |
                          v
+---------------------------------------------------+
| Unified Grounding Tool: grounding_tool.py         |
|                                                   |
| Pass 1: By-Hand AST Linter & Type Checker         |  --> Syntactic validity, typo detection,
|                                                   |      symbol resolution, DSL domain rules.
| Pass 2: Closed-World Linker & Scoping             |  --> Validates closed imports, tier
|                                                   |      isolation, cross-spec references.
| Pass 3: Deterministic Zero-Token Inheritance Sync |  --> Syncs ancestor requirements,
|                                                   |      assumptions, and @override stubs.
+---------------------------------------------------+
                          |
                          +--------> --check : Verifies lint, links, zero drift.
                          |
                          +--------> --sync  : In-place idempotent synchronization.
                          v
+---------------------------------------------------+
|          Verified Grounding Artifact              |
+---------------------------------------------------+
```

### 5. Unified Specification Toolchain (`grounding_tool.py`)

All specification validation and code generation steps are consolidated into a single unified CLI tool: [`grounding_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/support/lib/grounding_tool.py) (Bazel binary: `//update_with_ai/support/lib:grounding_tool`, test suite: `//update_with_ai/support/tests:test_spec_toolchain`). For comprehensive toolchain architecture, see [Toolchain & Verification Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/toolchain_and_verification.md).

```bash
# Verify syntax, imports, and zero inheritance drift:
bazel run //update_with_ai/support/lib:grounding_tool -- --check
# Or directly via python3:
python3 update_with_ai/support/lib/grounding_tool.py --check

# Synchronize inherited requirements and @override stubs in-place:
bazel run //update_with_ai/support/lib:grounding_tool -- --sync
# Or directly via python3:
python3 update_with_ai/support/lib/grounding_tool.py --sync
```

### 5.1 Pass 1: Custom "By-Hand" AST Linter & Type-Checker

#### Why Pyright is Replaced with "By-Hand" AST Checking
External type checkers like Pyright are designed for large Python codebases to verify that *runtime implementations* match declared type signatures. In Cleanroom grounding stubs, there is **zero implementation code**—every method body is strictly `...`. 

Consequently, Pyright provides little value beyond checking that signatures are syntactically valid (which Python's native `ast.parse` does for free), while introducing severe friction: Pyright complains about custom domain meta-types, lifecycle decorators, and stub conventions unless complex stubs and settings are configured.

Instead, Cleanroom's unified `grounding_tool.py` performs **"by-hand" type-checking, symbol resolution, and DSL enforcement** tailored specifically to our domain model.

#### What the Custom Linter Catches
1. **Typo Protection & Symbol Resolution**:
   - Builds a symbol table from all `import` statements and local class declarations.
   - Inspects every type annotation in properties and operations (e.g. `workspace_root(self) -> DirectoryPath`).
   - If an unimported or undeclared type is encountered, it flags a typo with fuzzy matching:
     `file_alias.pyi:24:12: error: Unknown type 'DirecotryPath'. Did you mean 'DirectoryPath'? (Symbol not declared or imported)`
2. **Strict No-Code / Pure Body Invariant**:
   - Rejects any file containing control flow (`For`, `While`, `If`, `Try`), state mutations (`Assign`), expressions (`Call`, `Yield`), or `pass`.
   - Every body must strictly be an optional docstring followed by an ellipsis (`...`).
3. **Strict Override Verification**:
   - If a method is decorated with `@override`, the tool inspects the declared base classes.
   - If the method does not exist in any base class, or if its signature is incompatible with the base definition, the tool fails:
     `file_alias.pyi:42:5: error: Method 'convert' marked @override but no matching method found in base classes ('ParameterConverter',)`
4. **Ontological Hierarchy & Decorator Rules**:
   - Every class must have exactly one structural decorator: `@singleton_type("system")`, `@singleton_type("agent_session")`, `@poly_type`, `@data_type`, or `@variant`.
   - `@singleton_type` requires an explicit lifecycle tier argument: `"system"` (process lifetime) or `"agent_session"` (session lifetime).
   - `@poly_type` takes no arguments because open polymorphic interfaces do not correspond to concrete runtime objects.
   - Inheritance from obsolete base markers `SystemService` or `AgentSessionService` is strictly prohibited.
   - `@variant` classes must inherit from a `@data_type` or another `@variant` (cannot inherit from active services).
   - `@singleton_type` and `@poly_type` classes can inherit from polymorphic interfaces or abstract service classes, never from data types.
   - `@data_type` classes cannot inherit from active services.
5. **Docstring Contract Structure**:
   - Verifies the presence of the opening ontological justification.
   - Validates that `FRESH_ASSUMPTIONS:`, `INHERITED_ASSUMPTIONS:`, `FRESH_REQUIREMENTS:`, and `INHERITED_REQUIREMENTS:` sections strictly use bulleted sentences (`- <sentence>`).
6. **Top-Level Function Validation & Orphan Requirements**:
   - Rejects any top-level function other than `__orphan__()`.
   - Validates that `__orphan__()` takes no parameters, has no decorators, returns `None`, contains a pure ellipsis body, and contains strictly `PURPOSE:` and `FRESH_REQUIREMENTS:` docstring headers.

#### Human-Readable Compiler Diagnostics
`grounding_tool.py` formats all diagnostics using standard compiler syntax (`<file>:<line>:<col>: error: <message>`), enabling instant IDE navigation, terminal click-through, and clean CI logs.

---

### 5.2 Pass 2: Deterministic Zero-Token Requirements Inheritance Engine

#### The Zero-Token Mandate
Relying on LLMs to propagate or summarize requirements down class hierarchies burns tens of thousands of tokens, runs slowly, and is vulnerable to hallucinations, dropped edge-case requirements, or subtle phrasing mutations.

In Cleanroom, requirements inheritance is handled by a 100% deterministic Python tool (`grounding_tool.py`). It parses `.pyi` ASTs, resolves the Method Resolution Order (MRO), and copies down requirements programmatically with **zero LLM calls and zero token consumption**, running in milliseconds with mathematical reliability.

#### Mutation Architecture: AST Transformation (`ast.NodeTransformer`) vs. Text Patching
Patching `.pyi` files using regular expressions, string searches, or line-by-line splicing is fragile: it fails on irregular indentation, multi-line docstrings, character escapes, and trailing triple-quote (`"""`) boundaries.

Instead, `grounding_tool.py` performs direct **AST Transformation and Unparsing**:

| Strategy | Implementation Profile | Reliability & Failure Vectors |
| :--- | :--- | :--- |
| **Raw Text / Regex Patching** | Line-by-line string regex search; text index slicing. | **High failure rate**: breaks on varying indentation, multi-line expressions, quotes. |
| **AST Transformation** | Locate `ast.ClassDef` / `ast.FunctionDef`; mutate docstring `ast.Constant` node; serialize via `ast.unparse()`. | **100% structurally sound**: Guarantees valid Python syntax, resets clean indentation, preserves AST scopes. |

Because Cleanroom groundings use structured docstrings (`ast.Expr(value=ast.Constant(str))`) rather than free-floating `#` comments for all contracts, `ast.unparse()` preserves 100% of specification content with pristine formatting.

```python
import ast

class RequirementsInjectionTransformer(ast.NodeTransformer):
    """Mutates class and method docstrings in the AST to inject inherited requirements."""

    def __init__(self, target_name: str, ancestor_name: str, inherited_reqs: list[str]):
        self.target_name = target_name
        self.ancestor_name = ancestor_name
        self.inherited_reqs = inherited_reqs

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name == self.target_name:
            docstring = ast.get_docstring(node) or ""
            # Group inherited requirements cleanly under their source ancestor
            inherited_block = f"\nINHERITED FROM {self.ancestor_name}:\n" + "\n".join(
                f"- {r}" for r in self.inherited_reqs
            )
            updated_docstring = f"{docstring.strip()}\n{inherited_block}\n"

            # Replace or insert docstring node
            doc_node = ast.Expr(value=ast.Constant(value=updated_docstring))
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                node.body[0] = doc_node
            else:
                node.body.insert(0, doc_node)
        return node
```

#### Provenance Grouping Protocol (Structural Parent Names)
Rather than appending an undifferentiated flat list of requirements, inherited requirements are **strictly grouped by their structural ancestor name**:

```python
"""
PURPOSE:
Converts a wire type string to a file alias, producing an unbound 
file if the short name is not found.

FRESH_REQUIREMENTS:
- Converting a wire type string produces the matching file alias if its short name is found.

INHERITED_REQUIREMENTS:
- [ParameterConverter] Converting a wire value must produce an instance compatible with actual_type.
- [ParameterConverter] Converting an invalid wire value raises a ParameterConversionError.
"""
```
**Why Grouping Wins**:
1. **Traceability / Provenance**: Developers and AI models know exactly which supertype or interface imposed each constraint.
2. **Conflict & Ambiguity Elimination**: Distinguishes local specialized behavior from parent contracts.
3. **Clean Override Tracking**: Clearly marks the delta between subtype additions and base class obligations.

#### The In-Place Synchronization Model
Cleanroom inlines inherited requirements, assumptions, and ancestor stubs directly into the specification files in **`update_with_ai/specs/grounding/`**.

The synchronization engine (`grounding_tool.py --sync`) operates under a strict **idempotent wipe-and-replace lifecycle**:
- **Untouched Fresh Contracts**: `FRESH_REQUIREMENTS:` and `FRESH_ASSUMPTIONS:` authored locally in the `.pyi` file are strictly preserved and never mutated.
- **Wipe Phase**: On every sync run, all existing `INHERITED_REQUIREMENTS:` and `INHERITED_ASSUMPTIONS:` blocks are wiped clean.
- **Recomputation Phase**: The tool walks the closed-world type hierarchy, recomputing all ancestor assumptions and requirements, and injects them under `INHERITED_ASSUMPTIONS:` and `INHERITED_REQUIREMENTS:` labeled with their source ancestor (`- [<AncestorName>] <statement>`).
- **Member Synthesis & Override Lifecycle**:
  - Missing ancestor properties and operations are automatically synthesized in the child class stub with `@override` and `@property` / `@operation`.
  - When an ancestor member is removed, child `@override` members without fresh contracts are automatically pruned.
  - If a child `@override` member has fresh assumptions or requirements when its ancestor member is removed, the tool raises a compiler error diagnostic.
- **Zero Drift**: Running the sync tool consecutively is an idempotent no-op (`git diff` remains clean).

---

### 5.3 Pass 3: Closed-World Linker & Scoping
1. **Import Parity**: Ensures every imported symbol is declared in the target `.pyi` stub module.
2. **Lifecycle Tier Isolation**: Verifies that long-lived `@singleton_type("system")` services do not hold short-lived `@singleton_type("agent_session")` references.
3. **Closed Variant Completeness**: Verifies that operations switching on variant hierarchies exhaustively cover all closed `@variant` cases.

---

## 6. Comparison: Legacy Markdown Tables vs. New Grounding Format (`.pyi`)

| Feature | Legacy 4-Column Markdown Table | Cleanroom New Grounding Format (`.pyi`) |
| :--- | :--- | :--- |
| **File Format** | Markdown (`.md`) with raw table markup | Native Python interface stubs (`.pyi`) |
| **Infrastructure Split** | None | Clean split: `framework.py` tags vs. pure `.pyi` declarations |
| **Typo Protection** | None (manual human proofreading) | **Custom "by-hand" AST symbol resolver & typo detector** |
| **DSL Domain Rules** | Ad-hoc text linter | **AST-based validator (`grounding_tool.py`)** enforcing ontological kinds & pure bodies |
| **Requirements Inheritance** | Manual copy-pasting or expensive LLM token burn | **Deterministic, zero-token Python engine (`grounding_tool.py`)** |
| **Source Control Policy** | Manual requirement duplication in Markdown | **In-place sync in git: authored FRESH_* preserved; INHERITED_* contracts & @override stubs synced in place** |
| **Diagnostics** | Unstructured console errors | **Standard compiler format (`file:line:col: error: ...`)** |
| **Type Signatures** | Informal strings (e.g. `Set of BoundFile`) | Standard typing annotations (`Set[BoundFile]`) |
| **Requirements Location** | Disconnected `## Requirements` list at bottom | Co-located inside class and method docstrings |
| **IDE Support** | Basic Markdown preview | Full syntax highlighting, jump-to-definition, hover docs |
| **Purity Enforcement** | None (formatting only) | Hard AST rejection of any executable statements |

---

## 7. Migration & Build Pipeline Strategy

### 7.1 Bazel Pipeline Integration (`pyi_grounding_test` & `pyi_grounding_library`)
A dedicated pair of Bazel rules integrates `.pyi` groundings:
1. **`pyi_grounding_test`**:
   - Runs `grounding_tool.py --check` to verify syntax, pure ellipsis bodies, symbol resolution, no empty data types, import completeness, and zero inheritance drift.
2. **`pyi_grounding_library`**:
   - Runs `grounding_tool.py --out-dir bazel-bin/specs/grounding/` to compile source deltas into fully expanded `.pyi` stubs with all inherited requirements and `@override` stubs populated.

All checks execute locally in Bazel sandboxes in milliseconds with **zero external API calls and zero LLM token costs**.

### 7.2 Migration Path for Existing Specifications
1. **Phase 1: Framework & Toolchain**: Implement `framework.py` and the unified CLI tool ([`grounding_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/support/lib/grounding_tool.py)) with full unit test suites.
2. **Phase 2: Lossless Markdown-to-PYI Converter**: Construct a translator script converting legacy Markdown tables and requirement lists into `.pyi` grounding stubs placed in `update_with_ai/specs/grounding/`.
3. **Phase 3: Validation & Promotion**: Verify all files in `grounding/` pass linting and inheritance expansion as the canonical specification repository.

---

## 8. TODO / Future Architectural Extensions

### 8.1 Grounding Argument Component Ledger for Unused Import Discovery

Automated syntactic tools only see tokens; they cannot distinguish between an essential collaborator dependency and a speculative phantom. Because singletons are accessed on-demand across flat lifecycle tiers without appearing in method signatures, a pure signature-level AST check on `.pyi` stubs would falsely flag valid collaborator imports.

Only semantic reasoning knows which collaborator components are actually relied upon to derive values, satisfy preconditions, or execute delegated behaviors.

**TODO**:
- Enhance the grounding reasoning format so that each `GROUNDING_ARGUMENT:` explicitly tracks the specific collaborator components it relies upon to satisfy its obligations.
- By computing the union of components depended upon across all grounding arguments for a component:
  $$\text{Needed} = \bigcup_{m \in \text{members}} \text{Collaborators}(m) \;\cup\; \text{SignatureTypes}$$
  The toolchain can identify any imported component where $\text{Imports} \setminus \text{Needed} \neq \emptyset$ as an unneeded, ungrounded dependency.
- For now, unused dependency detection is enforced at the Python implementation level (`*_impl.py`), where unused imports in the AST directly and unambiguously identify dead dependencies.

### 8.2 Supervising LLM Verification for Natural Language Tool Guidance & Diagnostics

Grounding requirements for tool failure behavior stipulate that failure responses must include error diagnostics and corrective guidance for the agent (e.g. `When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly`).

In unit tests, string contents cannot be pinned or asserted deterministically, making such semantic guidance requirements currently untestable via conventional `unittest` without asserting brittle string phrasing.

**TODO**:
- Enable automated tests to generate a series of targeted evaluation questions to submit to a supervising LLM.
- The supervising LLM evaluates whether the tool's generated failure feedback accurately diagnoses the issue and provides sufficient, actionable guidance for an agent to recover.
- This provides robust verification for natural language agent communication contracts without hardcoding unpinned string assertions into unit tests.

### 8.3 Requirement Ordering & Prioritization Formalization (TODO)

When an HLS specifies that an operation evaluates failure conditions in a specific sequence (e.g. *"Tool execution fails in the following order when: ..."*), alignment translates each branch into an atomic requirement bullet under `FRESH_REQUIREMENTS:`.

However, the `.pyi` grounding specification treats requirement bullets as an unordered collection of declarative postcondition invariants. There is currently no formal grammatical mechanism in the `.pyi` stub to declare evaluation precedence or priority ranking among requirements.

**The Context Vulnerability**:
The only reason library implementations and unit tests currently evaluate these conditions in the intended sequence is that the High-Level Specification was coincidentally present in the author's prompt context during development. In cleanroom execution, however, code and tests must be synthesized from the `.pyi` contract alone—meaning HLS context is **not guaranteed** (and is explicitly prohibited in isolated cleanroom sessions). When HLS context is absent, the agent cannot deduce the required check ordering from the `.pyi` file alone, leading to arbitrary check sequencing in library code and brittle test failures.

**TODO**:
- Formulate a cleanroom grounding convention to explicitly preserve evaluation order (e.g., an `ORDERED_REQUIREMENTS:` block or explicit priority annotations `[P1]`, `[P2]`).
- Extend toolchain linters to verify that library implementation early-exit ladders reflect the declared priority ordering.
- Mandate that test suites include overlapping condition cases to verify that higher-priority failure branches strictly preempt lower-priority branches.

### 8.4 Decomposing Compound Failure & Response Requirements: Failure Monotonicity & Prioritized Decision Lists (TODO)

Currently, grounding requirements frequently conflate operational failure conditions with response messaging payloads in single compound sentences (e.g., `Tool execution fails when condition A, reminding the agent that X and specifying Y as follow-up`).

**Failure is Monotonic, Response Dispatch is Not**:
Failure itself has no ordering dependency because failure is logically monotonic: $\text{Failed} \iff A \lor B \lor C$. Ordering failure predicates is a category error; the operation simply fails if any failure condition is met.

The ordering requirement exists **exclusively in response dispatch** (which diagnostic text and follow-up tool call to return when multiple failure conditions coincide: $R_A$ if $A$, $R_B$ if $\neg A \wedge B$, $R_C$ if $\neg A \wedge \neg B \wedge C$).

**Avoiding the "Icky Booleans" Anti-Pattern**:
If the grounding contract models this via explicit combinatorial negations (`Response B when not A and B...`), runtime implementations face a dilemma:
- **Redundant boolean checks** (`if not a and b:`), creating verbose, unpythonic, defensive code with combinatorial boolean explosion.
- Or clean procedural early-returns (`if b:`), where the `not a` condition is satisfied implicitly by fallthrough rather than explicitly by expression, creating a gap between the requirement statement and the line of code.

**TODO**:
Grounding specifications should model failure as a monotonic invariant and response dispatch as a **Prioritized Decision List**:
1. **Monotonic Failure Invariant**:
   - `Tool execution fails if condition A, condition B, or condition C is met.`
2. **Prioritized Decision List for Response Dispatch**:
   - `When tool execution fails, the response is dispatched according to the first matching condition in priority order:`
     - `1. If condition A holds, the response reminds that X and specifies Y as follow-up.`
     - `2. If condition B holds, the response reminds that Z.`
     - `3. If condition C holds, the response reminds that W.`

This formally authorizes early-return `if` ladders in Python without redundant booleans (`not a and b`), preserves deterministic precedence for cleanroom agents working without HLS context, and allows AST linters to verify statement ordering against the declared priority list.

---

## 9. Grounding Translation & Alignment Challenges: Prompt Engineering vs. Deterministic Enforcement

### 9.1 Executive Problem Statement: Why Prompt Engineering Alone Fails

In literate Cleanroom engineering, High-Level Specifications (HLS) are translated into Python interface stubs (`.pyi` grounding contracts), which are subsequently implemented as runtime Python libraries (`.py`) and verified by unit test suites (`_test.py`).

Empirical evaluation of autonomous agent runs reveals that **prompt engineering alone cannot reliably enforce structural and semantic grounding boundaries**. LLMs suffer from fundamental cognitive limitations when operating across specification boundaries:

1. **The In-Context Syntax Bleed Effect**: When an LLM translates a `.pyi` grounding stub into a `.py` implementation, the stub tokens in its context window exert strong in-context attentional pull. Despite explicit prompt instructions (e.g. *"do not copy framework decorators"*), transformers frequently replicate spec-only syntax (`@singleton_type`, `@operation`, `@data_type`, specification docstring blocks) directly into executable runtime code. Negative prompt constraints (*"do not do X"*) are notoriously fragile in complex contexts.
2. **Structural Type Translation Divergence**: In `.pyi` grounding stubs, passive data records are specified as `@data_type` classes with `@property` stubs returning field types. In runtime Python, these must be implemented as `@dataclass` classes with type-annotated class attributes (e.g. `path: str`), *not* method stubs. Without external enforcement, agents repeatedly emit empty `def __init__(self): ...` or `@property` stubs inside dataclasses.
3. **Mock Drift vs. Spec Drift (Phantom Protocol Extensions)**: When unit tests mock a grounding protocol, test authors or generative agents frequently define convenience methods on the mock class (e.g. adding `extract_target_name(self, node)` to `MockBazelNodeIdentifierUtility`) that do not exist on the protocol. The implementation code under test then calls the hallucinated mock method, all unit tests pass, yet the implementation violates the canonical grounding contract and fails static type checking or runtime integration.
4. **Visibility Leakage & Global Environment Contamination**: When type checkers or runtimes rely on ambient `PYTHONPATH` or permissive global IDE configuration files (`pyrightconfig.json`), specification-only infrastructure (`update_with_ai/support/lib/framework.py`) becomes resolvable by library code, silently masking illegal architectural coupling.

To address these vulnerabilities, Cleanroom relies on a two-tier defense: **declarative upfront prompt guidance** to bias generative synthesis, backed by **uncompromising, deterministic AST linters and closed-world build rules** that reject drift with millisecond compiler diagnostics.

---

### 9.2 Comprehensive Ledger: Solved vs. Unsolved Challenges

The following ledger documents the grounding, translation, and verification challenges encountered in Cleanroom, their resolution status, and the technical mechanism employed:

| Challenge / Defect Class | Layer | Status | Resolution Mechanism / Root Cause |
| :--- | :--- | :--- | :--- |
| **Framework Decorator & Import Leakage** | Grounding $\to$ Lib | **SOLVED** | **AST Linter & Build Enforcement**: `lib_lint.py` inspects the AST of all `_impl.py` and library files, failing immediately if any `ast.Import` or `ast.ImportFrom` targets `framework`. In addition, `bin/pyright_library.bzl` fails analysis if `:framework` is in `deps`/`pyright_deps`. |
| **Dataclass Method Stub Generation** | Grounding $\to$ Lib | **SOLVED** | **AST Linter Enforcement**: `lib_lint.py` (`check_dataclass_stubs`) inspects all `@dataclass` definitions, rejecting any that define empty `__init__` or `@property` stubs. `grounding_to_lib.md` was updated upfront to mandate standard class attribute declarations. |
| **Specification Docstring Contamination** | Grounding $\to$ Lib | **SOLVED** | **Guide Alignment**: `grounding_to_lib.md` was updated to explicitly prohibit copying `PURPOSE:`, `GROUNDING_ARGUMENT:`, and `FRESH_REQUIREMENTS:` headers into runtime code docstrings. |
| **Fake `_type_check` Passes in Bazel Harness** | Toolchain / Bazel | **SOLVED** | **Harness Execution Fix**: `bin/pyright_library.bzl` previously failed silently on `cat ... \| xargs` due to missing `runfiles` and missing `set -o pipefail`. Fixed by declaring all dependencies in `runfiles`, adding `set -e -o pipefail`, and passing target source files only. |
| **Third-Party Namespace Pollution in Runfiles** | Toolchain / Pyright | **SOLVED** | **Runfiles Path Normalization**: Resolved pip wheel path injection where deep paths into `site-packages` (e.g. `openai/types`) shadowed standard library packages (such as `types`). Trimmed paths to the `site-packages` root. |
| **Zero-Token MRO Requirements Synchronization** | Grounding Stubs | **SOLVED** | **Deterministic AST Traversal**: `grounding_tool.py --sync` programmatically computes MRO, synthesizes `@override` stubs, and copies down inherited contracts with exact provenance labels in milliseconds, eliminating prompt hallucination in specification maintenance. |
| **Mock-to-Protocol Parity Drift** | Grounding $\to$ Tests | **UNSOLVED** *(Hard)* | **Protocol Conformance Verification Gap**: When tests define test doubles (e.g. `MockNodeIdentifierUtility`), agents add helper methods (like `extract_target_name`) absent from the spec protocol. While strict Pyright on the consumer caught the missing attribute, mocks themselves are not currently validated against their protocol signatures via `@typing.override` or runtime protocol assertions. |
| **Ergonomic Query Omission in Protocols** | Grounding Spec | **UNSOLVED** *(Hard)* | **Interface Completeness Gap**: When a protocol omits an ergonomic query needed by consumers (e.g. extracting the target name from a node when only package directory extraction is specified), agents either hallucinate the method or resort to ad-hoc string parsing (`dep_label.split(":")[-1]`). Prompt engineering cannot solve missing API ergonomics. |
| **Closed-World Per-Target Type Isolation** | Toolchain / Pyright | **UNSOLVED** *(Hard)* | **Global Config vs. Target Hermeticity**: Pyright defaults to reading a workspace-level `pyrightconfig.json`, which either leaks search paths or requires continuous manual synchronization of `executionEnvironments`. To be strictly closed, `pyright_library` must generate hermetic, per-target JSON configs passed via `--project`, independent of ambient workspace configs or `PYTHONPATH`. |
| **Semantic Efficacy of Agent Failure Diagnostics** | Grounding $\to$ QA | **UNSOLVED** *(Hard)* | **Supervising LLM Protocol (TODO)**: Tool failure contracts requiring actionable guidance for agent recovery cannot be verified via deterministic unit test string assertions. Requires automated questionnaire generation and independent supervisory model scoring. |
| **Requirement Ordering & Prioritization Formalization** | HLS $\to$ Grounding $\to$ Lib/Test | **UNSOLVED** *(Hard)* | **Requirement Prioritization Gap (TODO)**: When an HLS specifies prioritized failure conditions ("fails in the following order when..."), each condition translates into an atomic bullet under `FRESH_REQUIREMENTS:`. However, grounding stubs lack an explicit mechanism to declare execution priority or evaluation order. When agents generate code or tests from the `.pyi` specification alone without the HLS in context, priority ordering is lost. |
| **Decomposition of Failure vs. Response Requirements** | Grounding Spec $\to$ Lib/Test | **UNSOLVED** *(Hard)* | **Compound Requirement Conflation (TODO)**: Grounding contracts conflate failure predicates (`X fails if A`) with response guidance (`reminding that...`). Decoupling into distinct failure conditions and response payload requirements is needed for clean precedence ordering and targeted verification. |



---

### 9.3 Deep Dive: Hard Grounding Problems Resistant to Prompt Engineering

#### 1. Mock-to-Protocol Parity & Structural Drift
Prompting an agent to *"ensure mocks implement only what the protocol defines"* is inherently unreliable. Generative models construct mocks by backward-chaining from the needs of the test assertion. If a test assertion needs to know the target name of a node, the agent instinctively attaches `extract_target_name` to the mock utility object in scope. Because Python classes allow arbitrary method definitions, standard unit testing frameworks do not complain.

**Required Architectural Solution**:
- Mocks should be required to use static type annotations or runtime protocol checks:
  ```python
  # Must be type-checked as the protocol type, not the mock type
  node_util: BazelNodeIdentifierUtility = MockNodeIdentifierUtility()
  ```
- Pyright running with `reportAttributeAccessIssue` and `reportUnknownMemberType` then guarantees that tests cannot access ad-hoc mock methods on protocol-typed variables.

#### 2. Protocol Ergonomics & Semantic Workarounds
When an ontological grounding interface specifies low-level operations (e.g. `normalize` and `extract_directory`) but omits obvious derived queries (e.g. `extract_target_name`), agents face an architectural dilemma:
- If they respect the protocol, they write fragile string manipulations (`dep_label.split(":")[-1]`) scattered across consuming implementations.
- If they seek clean abstractions, they hallucinate methods on the service interface.

Prompt engineering cannot fix an incomplete grounding contract. The HLS-to-grounding alignment process must systematically audit consumer requirements against protocol capabilities, ensuring derived accessors are formally grounded as `@operation` methods on the protocol or standard utility functions.

#### 3. Closed-World Build Hermeticity vs. Typing Hacks
A recurring failure mode in type-checked multi-package repositories is **search path leakage**:
- When `pyrightconfig.json` adds `extraPaths` globally to satisfy one consumer, all consumers gain visibility into those packages, bypassing Bazel's explicit `deps` declarations.
- When `PYTHONPATH` is manipulated globally, module resolution order becomes non-deterministic and can shadow standard libraries.

Cleanroom's architecture requires **strict build-rule hermeticity**: each `pyright_test` must generate a dedicated, target-specific Pyright project file derived strictly from the target's explicit `deps` and `imports`, guaranteeing that undeclared dependencies fail resolution identically in Bazel, in the IDE, and in CI.

