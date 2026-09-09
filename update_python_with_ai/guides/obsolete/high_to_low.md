# Guide: High-Level and Grounding to Low-Level Specification Alignment

## Summary

The artifact is a Low-Level Specification (`low/<name>.md`) that defines the concrete Python API signatures, dataclasses, protocols, operational contracts, and grounding arguments for a software component. The artifact conforms to this guide and translates declaratively from both the High-Level Specification (`high/<name>.md`) and the Grounding Specification (`grounding/<name>.pyi`). Interface specifications define frozen dataclasses and typing protocols; implementation specifications define concrete classes, bound member contracts, and code-generation grounding arguments.

External boundary specifications (`low/<name>_ext.md`) lack grounding stub sources and correspond to no standalone library files; instead, they translate external domain knowledge and grounding gap commitments from `high/<name>_ext.md` directly into concrete Python library API documentation, build rule dependencies needed by consuming implementation components (such as `requirement("openai")`), and runnable Python usage snippets. All non-external specifications strictly avoid runnable implementation code, restricting class and method bodies to pure ellipsis (`...`) definitions.

## Lint checks

- [ ] File header matches `# Interface LLS: <name>`, `# Implementation LLS: <name>`, or `# External LLS: <name>` matching the filename `<name>.md`
- [ ] Dependencies block at the top of the file uses `<!-- Dependencies (md files to read alongside this one): ... -->` listing sibling low-level specification names
- [ ] Section inventory for standard specifications is closed strictly to `## Data Types`, `## Term definitions`, optional `## Component-Provided Operations` (present only when operations exist), optional `## Invariants` (present only when invariants exist), and optional `## Grounding Arguments` (required for implementation specifications)
- [ ] Section inventory for external boundary specifications (`low/<name>_ext.md`) is closed strictly to `## External Mechanics & API Documentation`, `## Build Dependencies`, and `## Usage Snippets`
- [ ] Sub-headings (`###`) are permitted exclusively under `## Component-Provided Operations` (formatted as `### \`<ClassName>.<operation_name>\``), under `## Invariants` (formatted as `### \`<ClassName>\``), or under `## Usage Snippets`
- [ ] Every symbol declared in `grounding/<name>.pyi` has an exact 1:1 corresponding declaration in `low/<name>.md` with matching identifier spelling
- [ ] All method and function signatures use standard Python type annotations and terminate their bodies with an ellipsis (`...`)
- [ ] Operation sections contain strictly `**Purpose:**`, optional `**Preconditions:**`, optional `**Postconditions:**`, and optional `**Failure Handling:**` blocks with placeholder `None.` text and empty blocks omitted
- [ ] Zero `**HLS Justification:**` blocks appear anywhere in the document
- [ ] `## Grounding Arguments` is present in all implementation specifications (`low/<name>_impl.md`) and absent in all interface specifications (`low/<name>.md`)

## Document structure and dependencies

- [ ] Every low-level specification mirrors its source module boundaries exactly (`high/<name>.md` and `grounding/<name>.pyi` map to `low/<name>.md`)
- [ ] The file begins with an HTML dependency comment listing all imported specification files (`<!-- Dependencies (...): ... -->`)
- [ ] Every module imported in `high/<name>.md` or `grounding/<name>.pyi` is included in the dependency comment and imported in the Python type block
- [ ] Non-external specifications contain exactly one `python` code block under `## Data Types` declaring all types, dataclasses, and protocols for the module
- [ ] Data types and protocols appear in dependency order with dependent types declared after their prerequisite types
- [ ] Term definitions under `## Term definitions` list every declared class, protocol, and type alias with a brief description derived from its ontological purpose

## Data types and protocol definitions

- [ ] Value records declared with `@data_type` or `@variant` in `grounding/<name>.pyi` map to `@dataclass(frozen=True)` classes in `low/<name>.md`
- [ ] Scalar identifier types and specialized string primitives map to `TypeAlias` declarations (e.g. `CustomId: TypeAlias = str`)
- [ ] Active singleton services (`@singleton_type`) and polymorphic interfaces (`@poly_type`) in interface specifications map to `typing.Protocol` classes
- [ ] Concrete services in implementation specifications map to standard classes subclassing or realizing their corresponding interface protocol
- [ ] Properties declared with `@property` in `grounding/<name>.pyi` map to parameterless method accessors `def prop_name(self) -> ReturnType: ...` in protocols and classes
- [ ] Method accessors allow implementations to back properties interchangeably with instance attributes, cached properties, or computed methods
- [ ] Operations declared with `@operation` in `grounding/<name>.pyi` map to methods `def op_name(self, arg: ArgType) -> ReturnType: ...` preserving exact argument names and types
- [ ] Standard collection types from `typing` (`Sequence`, `Set`, `Mapping`, `Optional`, `Tuple`, `Type`) match the grounding type annotations

## Component-provided operations

- [ ] Every callable method or constructor has a dedicated `### \`<ClassName>.<operation_name>\`` section under `## Component-Provided Operations` identifying the owning class
- [ ] Top-level method headings without class qualification are prohibited
- [ ] Each operation section begins with a single `python` code block containing its exact signature
- [ ] `**Purpose:**` articulates the operation's role and target concept, adopting the wording from the corresponding `PURPOSE:` docstring in `grounding/<name>.pyi`
- [ ] `**Preconditions:**` lists all operational constraints caller must guarantee, incorporating entries from `FRESH_ASSUMPTIONS:` and `INHERITED_ASSUMPTIONS:`
- [ ] If an operation has no preconditions, the `**Preconditions:**` block is omitted entirely
- [ ] `**Postconditions:**` lists guaranteed results, state transitions, and return values, incorporating entries from `FRESH_REQUIREMENTS:` and `INHERITED_REQUIREMENTS:`
- [ ] Logical qualifications in requirements (such as `"if, but not only if,"`) are preserved verbatim in `**Postconditions:**`
- [ ] If an operation has no postconditions, the `**Postconditions:**` block is omitted entirely
- [ ] `**Failure Handling:**` explicitly defines error outcomes, diagnostic responses, or raised exceptions for all invalid inputs or boundary failures
- [ ] If an operation has no failure handling, the `**Failure Handling:**` block is omitted entirely
- [ ] Placeholder text (such as `None.` or `None`) is never used in operation sections; empty constraint sections are omitted

## Invariants and type assumptions

- [ ] `## Invariants` groups invariants by class or protocol under dedicated `### \`<ClassName>\`` subheadings
- [ ] If no class or protocol in the specification declares class-level requirements, the `## Invariants` section is omitted entirely
- [ ] Behavioral requirements declared at class scope in `grounding/<name>.pyi` map to entries under their corresponding `### \`<ClassName>\`` subheading
- [ ] Inherited class requirements from `INHERITED_REQUIREMENTS:` are included under their class subheading to maintain full local contract visibility
- [ ] Unscoped assumptions or domain-wide invariants that apply across all members of a type map to entries under their class subheading
- [ ] Invariants state permanent properties that remain true across the lifecycle of the component or data structure

## Grounding arguments and derivation paths

- [ ] Implementation specifications (`low/<name>_impl.md`) include a dedicated `## Grounding Arguments` section
- [ ] Every singleton service, property accessor, and operation in the implementation specification has an entry under `## Grounding Arguments`
- [ ] Property grounding arguments describe the exact runtime origin and derivation path of values (delegation from collaborator, loading from manifest, reading from disk, or configuration setting)
- [ ] Grounding arguments document the required lifecycle tier of collaborators (`system` vs `agent_session`), confirming tier isolation invariants hold
- [ ] Grounding arguments identify how collaborator capabilities satisfy implementation obligations to provide actionable context for code generators
- [ ] Grounding arguments note un-implemented collaborator requirements that are assumed to hold during runtime execution

## External boundary specifications

- [ ] External boundary specifications (`low/<name>_ext.md`) do not reference grounding stubs and correspond to no standalone library files, providing external API knowledge consumed directly by dependent implementation components
- [ ] `## External Mechanics & API Documentation` documents native third-party Python library APIs and SDKs (such as `openai`, standard library modules, or protobuf libraries) rather than raw HTTP wire transport protocols
- [ ] `## Build Dependencies` specifies exact build rule modifications and external dependency labels (such as `requirement("openai")` or proto targets) needed in the `deps` of dependent implementation components in `BUILD.bazel`
- [ ] `## Usage Snippets` provides generic, runnable Python code examples demonstrating third-party SDK calls, parameter construction, payload parsing, and error status handling
- [ ] Usage snippets provide generic reference examples rather than prescriptive examples coupled to specific domain components or Cleanroom project types
- [ ] Snippets demonstrate error recovery patterns mapping third-party library errors or OS exceptions to structured failure outcomes

## Common pitfalls

- [ ] Bare operation headings — omitting the class name prefix (e.g. `### \`<operation>\`` instead of `### \`<ClassName>.<operation>\``)
- [ ] Placeholder text in constraints — writing `**Preconditions:** None.` or similar placeholders instead of omitting the section
- [ ] Retaining HLS justification — adding `**HLS Justification:**` blocks into operation sections
- [ ] Scrubbed logical qualifiers — dropping or altering qualifiers like `"if, but not only if,"` from postconditions
- [ ] Ungrouped invariants — listing invariants as a flat list under `## Invariants` without `### \`<ClassName>\`` subheadings
- [ ] Empty invariants section — leaving an empty `## Invariants` section when no class has invariants
- [ ] Prescriptive external snippets — writing snippets coupled to Cleanroom domain concepts instead of generic third-party library usage patterns
- [ ] Constructor leak in protocols — defining `__init__` on `Protocol` classes instead of factory functions or class definitions
- [ ] Property decoration in protocols — using `@property` decorators in Protocol definitions instead of method accessors `def prop(self) -> T: ...`
- [ ] Name drifting from grounding — renaming fields, arguments, or methods from the spelling established in `grounding/<name>.pyi`
- [ ] Omitted inherited contracts — omitting `INHERITED_REQUIREMENTS:` or `INHERITED_ASSUMPTIONS:` from operation postconditions or invariants
- [ ] Suppressed failure handling — omitting explicit failure handling conditions when the grounding or HLS specifies failure responses
- [ ] Missing grounding arguments — omitting `## Grounding Arguments` from implementation specifications (`low/<name>_impl.md`)
- [ ] Code snippets in standard LLS — including executable implementation code in non-external LLS documents instead of reserving code snippets for `_ext` documents
- [ ] Standalone library files for external boundaries — assuming `_ext` components generate standalone library files instead of providing external library knowledge consumed by dependent implementation components
- [ ] Wire protocol documentation in external LLS — documenting raw HTTP endpoints, verbs, or wire headers instead of concrete Python SDK APIs and library call patterns
- [ ] Missing build dependencies in external LLS — documenting external APIs without identifying required Bazel BUILD rules or `requirement(...)` entries for dependent implementation components
