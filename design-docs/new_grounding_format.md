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
    """Marks an operation or property as overriding or inheriting a contract from a supertype."""
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

### 2.6 Data Types & Structural Equality Invariant (No Empty Data Types)
In Cleanroom, data types are passive value objects evaluated by structural equality. Consequently, **empty or token data types are strictly prohibited**:
- Every `@data_type` and `@variant` MUST declare at least one property that participates in its structural identity.
- Any entity previously declared without properties (such as `Node`) is defective. In Cleanroom, `Node` must explicitly declare an `address: str` property to establish its identity.

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
     - For properties: details where property values originate (e.g. delegated from another collaborator, populated via mutable operations, configured via operations, or loaded from external data sources or environment).
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

---

## 4. Reference Implementation: `file_alias.pyi`

Below is the definitive reference specification demonstrating all structural conventions, decorators, type signatures, and co-located requirements in a `.pyi` stub file:

```python
# file_alias.pyi
from typing import Optional, Set
from framework import data_type, variant, singleton_type, override, operation
from dag_storage import Node
from filesystem import DirectoryPath, WorkspacePath
from tool_provider import ParameterConverter, WireType, Type

@singleton_type("agent_session")
class AliasManager(ParameterConverter):
    """
    PURPOSE:
    Defined as an agent session service configured with a workspace root 
    that sanitizes output text.

    INHERITANCE:
    - ParameterConverter: Established that the alias manager is a parameter converter for file aliases, allowing file aliases to be used as tool parameters.
    """

    @property
    def workspace_root(self) -> DirectoryPath:
        """
        PURPOSE:
        Established that the alias manager is configured with a workspace root.
        """
        ...

    @property
    @override
    def actual_type(self) -> Type:
        """
        PURPOSE:
        Sets the converter actual type for the alias manager to file alias.
        """
        ...

    @property
    @override
    def wire_type(self) -> WireType:
        """
        PURPOSE:
        Sets the converter wire type for the alias manager to string.
        """
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> "FileAlias":
        """
        PURPOSE:
        Converts a wire type string to a file alias, producing an unbound 
        file if the short name is not found.
        
        FRESH_REQUIREMENTS:
        - Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.

        INHERITED_REQUIREMENTS:
        - [ParameterConverter] Converting a wire value must produce an instance compatible with actual_type.
        - [ParameterConverter] Converting an invalid wire value raises a ParameterConversionError.
        """
        ...
        
    @operation
    def sanitize_text(self, text: str) -> str:
        """
        PURPOSE:
        Provides that the alias manager sanitizes text by masking occurrences 
        of host paths with short names.
        
        FRESH_REQUIREMENTS:
        - Sanitizing text masks occurrences of host paths with the corresponding file alias short names.
        """
        ...


@data_type
class FileAlias:
    """
    PURPOSE:
    Defined to represent a session file, hiding physical filesystem details 
    and paths from the agent.
    
    FRESH_ASSUMPTIONS:
    - The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.
    
    FRESH_REQUIREMENTS:
    - A file alias displays itself by its short name when converted to a string.
    """

    @property
    def short_name(self) -> str:
        """
        PURPOSE:
        Established that each file alias has a short name.
        """
        ...


@variant
class BoundFile(FileAlias):
    """
    PURPOSE:
    Classifies bound file as a file alias mapped to an actual workspace file.
    """

    @property
    def workspace_path(self) -> WorkspacePath:
        """
        PURPOSE:
        Established that each bound file has a workspace path.
        """
        ...

    @property
    def owning_node(self) -> Node:
        """
        PURPOSE:
        Established that each bound file has an owning node.
        """
        ...


@variant
class ReadOnlyFile(BoundFile):
    """
    PURPOSE:
    Classifies read-only file as a bound file restricted to inspection.
    """
    ...


@variant
class ReadWriteFile(BoundFile):
    """
    PURPOSE:
    Classifies read-write file as a bound file permitted for inspection and modification.
    """
    ...


@variant
class UnboundFile(FileAlias):
    """
    PURPOSE:
    Classifies unbound file as a file alias that is not mapped to an actual file.
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

All specification validation and code generation steps are consolidated into a single unified CLI tool: [`grounding_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/tools/grounding_tool.py).

```bash
# Verify syntax, imports, and zero inheritance drift:
python3 update_with_ai/tools/grounding_tool.py --check update_with_ai/specs/grounding/*.pyi

# Synchronize inherited requirements and @override stubs in-place:
python3 update_with_ai/tools/grounding_tool.py --sync update_with_ai/specs/grounding/*.pyi
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
1. **Phase 1: Framework & Toolchain**: Implement `framework.py` and the unified CLI tool ([`grounding_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/tools/grounding_tool.py)) with full unit test suites.
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
