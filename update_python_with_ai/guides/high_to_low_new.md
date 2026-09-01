# Guide: Converting High-Level Specifications to Low-Level Specifications

## Summary

The artifact is the LLS for a component: it conforms to the LLS structure this guide states and aligns with the component's HLS and transitive closure. The LLS is the HLS elaborated, never replaced: it formalizes the HLS's declarative concepts and behaviors, adding concrete Python types (`TypeAlias`, `@dataclass`, `Protocol`), explicit method signatures, preconditions, postconditions, and typed failure return signals.

The conversion reads the immediate HLS and the transitive closure of both HLS specifications (`high/<name>.md`) and dependent LLS specifications (`low/<name>.md`). Adaptation is minimally invasive: the LLS is changed in place, and conformant content is left exactly as it is; the file is not rewritten, and no section is restructured unless a deviation requires it. Each deviation is fixed with the smallest change that resolves it; a file that is a template is filled in.

Every LLS statement traces to the HLS's effective constraint set: the LLS adds no behavior the closure does not imply, and implementation details appear only as necessary to fulfill HLS guarantees. Each HLS fact appears in exactly one LLS location, never duplicated. Type aliases are camelCase with the first letter capitalized (`PendingItem`, `ItemStatus`), defined in the Data Types Python block, and used in operation signatures. The LLS contains no markdown links. An implementation LLS contains only the implementation sections — `## Data Types`, optional `## Composition`, `## Behavioral Description`, `## Invariants`, `## Non-Concerns` — never interface sections such as `## Component-Provided Operations`. Each checklist section governs the document region it names, in document order.

---

## Front matter

- [ ] A component whose HLS has no `implements:` line is an interface — its LLS is `# Interface LLS: <name>`, or `# External LLS: <name>` for an external boundary spec (`<name>_ext.md`); an implementation LLS exists when the HLS defines an implementation (`<name>_impl.md`) or an assembly (`<name>_asm.md`), both of which declare `implements: <interface>`
- [ ] Filenames use underscores; no hyphens anywhere — high- and low-level specs are distinguished by directory (`high/<name>.md` vs `low/<name>.md`), not by filename suffix
- [ ] The dependency comment is the file's first line — the LLS's only front matter: lists each direct LLS dependency as one `- <dep_name>.md` entry
- [ ] LLS dependencies are expressed through interfaces or external specs, never implementation LLS files; a type is imported from its owner's LLS, never through a re-exporting interface
- [ ] The one exception: an assembly LLS's dependency comment lists the implementation (`- <name>_impl.md`) and assembly (`- <name>_asm.md`) LLS files it assembles; its Data Types imports the types of the assembled modules from those files
- [ ] The comment lists the LLS of every interface or external spec named in the converted HLS's imports or type references
- [ ] External boundaries (external services, external value formats, foreign runtime identifiers) are specified as standard LLS modules under `low/<name>_ext.md` and listed in the dependency comment as `- <name>_ext.md`
- [ ] Every non-standard-library import in the Python block appears in the dependency comment

## Data Types

- [ ] The Data Types section opens with exactly one Python code block; all imports, type aliases, dataclasses, and classes are defined inside it, never in the surrounding prose; in an interface LLS, the Protocol class is last
- [ ] No comments, docstrings, or markdown links inside the Python code block
- [ ] Explicitly imports every typing construct used: `from typing import Protocol, TypeAlias, Sequence, Mapping, Optional, Literal, TypeVar, Union`
- [ ] Every HLS type becomes a concrete Python type alias or class in the block, named as a camelCase domain concept with the first letter capitalized: the HLS type `pending shipment` becomes `PendingShipment: TypeAlias = str`
- [ ] Type alias names are camelCase with the first letter capitalized (`PendingItem`, `RecordStatus`); never lowercase-camel and never snake_case
- [ ] Every alias defined in the block is used in a signature, in a field, or in prose; an alias used nowhere is removed
- [ ] Operation signatures and fields are typed with the Data Types aliases, never their raw primitive expansions
- [ ] A same-named type in a dependency's LLS is imported, never redefined; a fresh local alias with the same value is still an invalid redefinition
- [ ] Type names name the domain concept — what the value is — never its representation suffix (`Key`, `Id`, `Text`, `Value`, `Data`, `Record`)
- [ ] Mutually exclusive outcomes are discriminated unions with `Literal` discriminators, never `Enum`
- [ ] A type solely classified by what information it carries is a `@dataclass` (typically `@dataclass(frozen=True)` unless mutable), unless it requires open polymorphic extensibility
- [ ] A type that holds state or is primarily classified by what it does (its operations and behaviors) is a `Protocol`
- [ ] Configuration an interface operation takes is interface-owned: typed in Data Types with a descriptive name (`PipelineConfig`, never `Config`); defaults the HLS states are `@dataclass` field defaults; configuration that only constructs the implementation is implementation-owned
- [ ] Every interface declares its Protocol class in Data Types: `class <Name>(Protocol):` named after the component and declaring every operation documented under Component-Provided Operations as a method
- [ ] Implementation classes inherit from the interface Protocol: `class <Name>Impl(<Name>):` and constructors take only implementation-owned configuration dataclasses or collaborator Protocol instances

## Component-Provided Operations

- [ ] Operations on a Protocol are derived directly from the active capability sentences in HLS ## Behavior:
  - Direct capability sentences ("A *<type>* can <action>...", "A *<type>* <verbs>...") yield an operational method for that action (e.g. "A *manifest validator* verifies a *batch item*" yields `def verify(...)`)
  - Retrieval and query sentences ("A *<type>* provides <item>...", "allows querying <state>") yield retrieval or inspection methods (e.g. "A *ledger* provides a *balance statement*" yields `def get_statement(...)`)
  - Invocations and mutations ("Executing a *<type>*...", "Appending <items> adds them to *<type>*") yield invocation or mutation methods (e.g. `def execute(...)`, `def append(...)`)
- [ ] Internal consequences, state side-effects, and routing rules triggered by an action (e.g. updating item indices during addition, or routing notification events after completion) are postconditions of the operation, not separate callable methods
- [ ] Every client-initiated capability in HLS `## Behavior` becomes an operation method in the Protocol class and a documented subsection under `## Component-Provided Operations`
- [ ] Internal behaviors (propagation, persistence, validation) are postconditions, not operations
- [ ] Each operation is documented under a `### `operation_name`` heading; its signature is echoed as `def <name>(...)` in a Python block directly under the heading, typed with the Data Types aliases and mirroring the Protocol method in Data Types
- [ ] Each operation documents **Purpose**, **Preconditions**, **Postconditions**, **Failure Handling**, and **HLS Justification** under its heading
- [ ] **Type Mapping & HLS Verbiage Preservation**:
  - Every type alias and class defined in the LLS Python block is explained in the prose following the block with an explicit mapping to its HLS domain concept: `- \`TypeName\` → corresponds to *<hls type name>*`
  - When an HLS concept is realized as a protocol method, parameter, or return value, use the exact descriptive terminology and verbiage from the HLS in the method's **Purpose**, **Postconditions**, and **HLS Justification** clauses
  - No HLS type or concept is dropped; preserving the exact mapping ensures automated and manual alignment checks can verify that every HLS requirement is fully accounted for in the LLS
- [ ] **Deriving Preconditions vs Expected Failures**:
  - Natural qualifying adjectives on inputs (e.g. "a *positive* quantity", "a *registered* account") and caller obligations are **Preconditions**; violating them is a caller bug resulting in undefined behavior or unhandled exceptions.
  - Runtime validation checks, policy boundaries, permission gates, and invalid caller inputs described in HLS rules (e.g. "Executing a shipment with invalid credentials produces a shipment rejection", "rejects a receipt exceeding item bounds") are **Expected Failures**, documented under **Failure Handling** with explicit typed return signals.
- [ ] **Postconditions:** describe outcomes and state transformations, not internal mechanisms; client-visible operation boundaries (atomicity, all-or-nothing) are postcondition guarantees
- [ ] **Failure Handling:** expected failures (validation failures, policy violations, permission checks, disallowed argument combinations) are return-value signals documented in the interface spec, never exceptions; unexpected failures are exceptions or undefined behavior
- [ ] **Failure Handling:** operational restrictions and permission rules in HLS are expected failures explicitly listed under Failure Handling with their return-value failure signal
- [ ] **HLS Justification:** each operation's justification is one brief phrase tracing to the HLS rule it fulfills

## Invariants

- [ ] Invariants are component-wide properties and cross-operation guarantees derived from HLS `## Behavior`:
  - Cross-cutting integrity rules that hold across all operations (e.g. "Each stock symbol in an exchange uniquely identifies at most one security")
  - Unbroken state consistency rules (e.g. "The ledger history is append-only except for explicitly authorized adjustments")
  - Lifecycle and atomicity bounds (e.g. "A final receipt is terminal and immutable; no further items are added once emitted")
- [ ] Each invariant is stated once; the Invariants section is never empty
- [ ] A statement of absence is an invariant when a test can assert it

## Non-Concerns

- [ ] Non-Concerns is optional; it records pinned choices as `- **[Aspect]:** [Choice] — [Justification]`; aspects intentionally unspecified: ordering, algorithm, representation
- [ ] An HLS non-concern is recorded here

## Implementation sections

- [ ] An Implementation LLS section exists only when the HLS defines an implementation (`*_impl.md`) or an assembly (`*_asm.md`)
- [ ] The implementation is declared as `class <Name>Impl(<Name>):` extending the fulfilled interface's Protocol imported from the interface LLS
- [ ] An assembly is declared as `class <Name>Asm(<Name>Impl):` subclassing the concrete implementation and ending with the `Asm` suffix; its `__init__` takes assembly construction parameters and pre-wires component factories
- [ ] Implementation sections reference the interface contract instead of the client; implementation sections never mention "client"
- [ ] Behavioral Description details concrete mechanisms, parameter schemas, formatting rules, and string constants
- [ ] Operations that compare, index, or store external value formats specify canonicalization and normalization behavior in Behavioral Description or Invariants
- [ ] The fulfilled interface's operations are documented in the interface LLS; the implementation documents them in Behavioral Description as bullets — never in an interface section, never under `### ` headings
- [ ] Assembler implementations list the wired concrete implementations in a Composition section; an assembly's Composition section is required, and its dependency comment lists the implementation LLS files those implementations come from
