# Grounding Specification Format & Ontological Extraction Guide

## 1. Overview & Purpose

Grounding is the formal ontological bridge between literate High-Level Specifications (HLS) and executable Low-Level Specifications (LLS). 

While an HLS is written in fluid, human-readable prose designed for architectural clarity and LLM comprehension, a **grounding specification** extracts and formalizes the exact structural contract:
- **Singleton Types & Poly Types**: Active services, their lifecycle tiers, inheritance/interfaces (`is-a`), and callable operations.
- **Data Types**: Passive records, entity identifiers, and value structures.
- **Relationships**: First-class associations carrying qualifiers or metadata between entities.
- **Variants (Option B)**: Closed sum types / discriminated unions declared directly on super data types.
- **Strict Closed-World Scoping**: Grounding documents replicate `imports:`. An entity may only reference types defined locally or within imported specifications.
- **The Justification Mandate**: Every declaration must be justified by an explicit quote or rephrased meaning from the HLS prose in a dedicated `comment` column.

A grounding specification is **not** an open-ended object-oriented design session. It is a strict, loss-free ontological derivation of what the specification explicitly declares.

---

## 2. Linguistic & NLP Extraction Principles

Extracting formal groundings from prose requires precise natural-language processing. Naive extractions routinely fall into common architectural failure modes by projecting traditional OOP assumptions onto the prose. The following linguistic principles govern all grounding extractions.

### 2.1 The Justification Mandate (Articulate Derivation vs. Raw Excerpt)
Every declared element—whether a singleton type, poly type, data type, property, operation, variant, or `is-a` relationship—must have an articulate justification in the `comment` column based on the text of the specification.
- **The Rule**: The comment must explicitly justify *why* the row is declared, weaving in as much authentic language from the specification as possible, rather than being an isolated snippet or truncated clause (e.g. avoid `"having a name"` or `"so they can be executed"`).
- **Justification Style**: Do NOT precede every comment with "The specification" (avoid repetitive boilerplate like *"The specification establishes that each tool has a name identifying it"*). Instead, state directly how the construct is established (e.g., *"Established that each tool has a name identifying it"*, *"Defined as an agent session service..."*, *"Provides that tools can be installed..."*).
- **Zero-Hallucination Proof**: If you cannot formulate a justification rooted in the explicit text and terminology of the spec, **the row is an ungrounded hallucination and must not be declared**.
- **No Requirements in Comments**: Do NOT copy multi-step algorithms, conditional branches, or detailed error recovery rules into the `comment` column. The `comment` column is solely for ontological justification explaining why the entity, member, or operation override exists in the structural model. Behavioral and validation rules belong in `## Requirements`.

### 2.2 Services vs. Entity Identifiers (State Maintenance vs. State Holding)
Specifications frequently introduce a system service that coordinates state on behalf of discrete entities.
- **Linguistic Pattern**: *"A [Service] is a system service that maintains [Entity] state, including [X] and [Y]. An [Entity] in a [Service] has: - [Property A]... - [Property B]..."*
- **Linguistic Reality**: The phrase *"An [Entity] in a [Service] has..."* defines the state **maintained by the service**, not internal mutable fields of the entity itself. The entity is merely a reference or token identifying a unit of work.
- **The Rule**:
  - The [Entity] is declared as a passive Data Type with **no properties** (unless it has intrinsic fields declared independently of the service).
  - The state queries (`A(entity: Entity)`, `B(entity: Entity)`) and state mutations belong to the [Service] as operations taking `(entity: Entity)`.
- **Anti-Pattern**: Turning the entity into a stateful, mutable class containing all properties, stripping the service of its state-maintenance responsibility.

### 2.3 Attributive vs. Relational Qualifiers (Qualifying Edges vs. Nodes)
When relationships between entities have conditions or qualifiers, naive parsing often collapses the qualifier onto one of the endpoint entities.
- **Linguistic Pattern**: *"An [Entity] has [Associations] referring to upstream [Targets]. An [Association] can be [Qualified] to indicate that the entity does not depend on the target's content..."*
- **Linguistic Reality**: The qualifier applies to the **relationship** between the two entities, not to the target entity itself. The target entity is not globally qualified; it is only qualified within that specific relationship.
- **The Rule**: When an association carries a qualifier (e.g. conditional, advisory, silent, prioritized), model the association as a distinct **Relationship Data Type** holding a reference to the target and the qualifying flag.
- **Anti-Pattern**: Adding `qualified: boolean` directly to the target entity (e.g. declaring a target entity as "silent" or "advisory" globally).

### 2.4 Quantifiers and Holistic Operations (Respecting "All")
Specifications often define operations that coordinate multiple relationships at once.
- **Linguistic Pattern**: *"An entity can be [registered] to all of its non-[qualified] prerequisites so that it can be notified when prerequisites change."*
- **Linguistic Reality**: The operation coordinates the entity against its existing set of prerequisites. The quantifier *"all"* indicates a holistic, batch action executed by the service.
- **The Rule**: The operation signature on the service takes only the entity: `registered(entity: Entity)`. The service inspects the entity's prerequisites and filters them internally.
- **Anti-Pattern**: Decomposing holistic actions into pairwise edge calls (e.g. `registered(source: Entity, target: Entity)`), forcing callers to iterate manually and discarding the spec's declarative semantics.

### 2.5 Closed Variant Modeling (Option B)
When a data type encompasses a closed set of specialized classifications or outcomes:
- **The Rule**: Enumerate the variants directly under the super data type with `kind = variant`.
- **Anti-Pattern**: Creating open-ended abstract inheritance hierarchies with empty subclasses.

### 2.6 Identifier Casing, Parametric Types, and Meta-Types
To maintain mathematical clarity and eliminate ambiguous formatting across tables and requirements:
- **Type Names**: Always use CamelCase (PascalCase) for all types and lifecycle tiers (e.g. `ToolManager`, `AgentSessionService`, `Tool`, `Parameter`, `WireType`, `ParameterBindings`, `Response`, `FileAlias`, `AliasManager`, `DagStorage`, `Node`, `Dependency`, `Message`).
- **Property Names & Method Arguments**: Always use snake_case (e.g. `actual_type`, `wire_type`, `is_failed`, `short_name`, `owning_node`, `line_number`).
- **Collections**: Use `Set of <Type>` (e.g. `Set of Dependency`, `Set of Tool`) for unordered collections, or `List of <Type>` (e.g. `List of StepSection`) for ordered sequence data. Never use adjective stacking (`item set`).
  - Properties that represent data types rather than runtime values (e.g., `actual_type`) are typed with the built-in meta-type `Type`.
  - Because `actual_type` is a property (a value of type `Type`), it is NOT a type itself.
  - To denote a runtime value of the type referenced by `actual_type`, use the type constructor **`Value of actual_type`**.
  - Example: `Set of (Parameter, Value of actual_type)`.
  - Note the difference: `wire_type` is a property on `Parameter` and `ParameterConverter`, typed by the closed sum-type `WireType`.
- **No Pipe (`|`) for Union Types in Tables**:
  - Never use `|` (pipe) for union or sum types inside Markdown table cells. Because `|` acts as the Markdown table column delimiter, including raw pipes corrupts table formatting.
  - Always use English `or` for union type signatures (e.g. `(wire_value: string or integer or boolean) -> Value of actual_type`, or `FileAlias or unmapped`).

### 2.7 Operation & Property Naming Conventions
- **Operations Returning Values (`get_<noun>` or `get_<type_name>_<noun>`)**:
  - Operations that straight up return information or state must be named `get_<noun>` in snake_case (e.g. `get_dependencies`, `get_dependents`, `get_messages`, `get_content`).
  - If the operation focuses on a specific type inside or managed by the container type, use `<verb>_<type_name>_<noun>` for clarity (e.g. `get_tool_names` on `ToolManager` to retrieve names of tools, rather than a vague `get_names`).
- **Boolean Operations / Predicates (`is_<adjective/noun>`)**:
  - Operations that return `boolean` must sound like they obviously just return information: prefix with `is_` in snake_case (e.g. `is_dirty`, `is_registered`, `is_valid`).
- **Boolean Properties (`is_<adjective/noun>`)**:
  - Constituent properties of boolean type must also follow the `is_<adjective/noun>` snake_case pattern (e.g. `is_silent: boolean`, `is_required: boolean`, `is_failed: boolean`, `is_terminated: boolean`).
- **Mutators and Actions (`verb_noun`)**:
  - Operations that perform an action or mutation must consistently follow the `verb_noun` snake_case naming convention (e.g. `register_dependent`, `clear_dependents`, `add_message`, `clear_messages`, `install_tool`, `install_converter`, `request_tool`, `request_converter`, `translate_path`, `translate_alias`, `sanitize_text`, `find_matches`).
  - The name of a mutator must NEVER end in "-ed" (e.g. `register_dependent`, not `registered_dependent` or `registered`).

### 2.8 Fresh vs. Override Declarations (`singleton type`, `poly type`, `property`, `operation`)
- **Fresh Types & Members**:
  - Fresh active services: `singleton type` or `poly type`.
  - Fresh properties and operations: `property` or `operation`.
- **Override Types (`override singleton type`, `override poly type`)**:
  - When a component defines an active service type with the same name as an interface type it imports (typically an implementation component realizing interface types), its kind must be declared as **`override singleton type`** or **`override poly type`** (preceded with `override`).
  - This directly establishes that the type realizes the imported interface type of the same name without requiring a redundant `is-a` declaration.
- **Override Properties & Operations (`override property`, `override operation`)**:
  - If a property or operation is inherited from an extended or overridden type, or overrides a built-in lifecycle operation (`initialize`), its kind must be declared as **`override property`** or **`override operation`**. This maintains clear provenance of inherited and lifecycle contracts.
- **Interface Completeness vs Implementation Isolation**:
  - An interface specification defines the complete bill of sale (all types, properties, operations, and general behavioral contracts) required by outside callers and implementers.
  - Other components that implement an interface type (e.g. concrete tools implementing `tool_provider.Tool`) import ONLY the interface specification, never the implementation specification.
  - Therefore, an interface must never omit or hide properties (e.g. `is_required`, `name`, `description`), operations, or general output expectations needed by implementers.
  - Implementation specifications (`<name>_impl.md`) govern strictly the private code generated for that specific component; their requirements are never inherited or relied upon by external implementers.

### 2.9 Cross-Component Type Qualification
- When referencing a type defined in an imported component (that is not being refined in the current component), the type must be explicitly qualified with its originating component name: `<component>.<type>` (e.g. `filesystem_ext.DirectoryPath`, `dag_storage.Node`, `tool_provider.Tool`).
- Primitive and built-in types (`string`, `integer`, `boolean`, `Type`, `ExpectedFailure`) and locally defined types are written unqualified.

### 2.10 Lifecycle Phases & Built-in Object Initialization (`initialize`)
- **Principle**: All active service types (`singleton type` and `poly type`) are *initialized* when they are created during a lifecycle phase. They possess a built-in lifecycle operation: `initialize`.
- **Empty Signature & Dependency Resolution**: `initialize` has an empty signature `()` (no arguments, no return value). Objects residing in the same lifecycle phase can be accessed via the lifecycle object (an implementation detail akin to dependency injection). Therefore, singularly addressable singleton types do not need to be passed as arguments.
- **Overriding `initialize`**: If an HLS describes an active service type taking active startup action when brought online—such as interacting with other objects to register services or add resources—this must NOT be extracted as a bespoke ad-hoc verb. Instead, the type overrides the built-in operation:
  `override operation | initialize | () | <brief justification from HLS>`
- **Default Omission**: If an active service type does not need to perform active setup or interact with other objects when brought online, `initialize` is not overridden and is omitted from the table.

### 2.11 Singleton vs. Polymorphic Types (`singleton type` vs. `poly type`)
- **Singleton Types (`singleton type`)**: Default active services are singletons within their lifecycle phase (e.g., `tool manager`, `dag storage`, `filesystem`, `read manager`, `alias manager`). They are singularly addressable via the lifecycle object (dependency injection).
- **Polymorphic Types (`poly type`)**: Non-singular multiton interface types where multiple instances co-exist in the same lifecycle phase (e.g., `tool`, `parameter converter`). Because there are multiples, they cannot be singularly addressed via the lifecycle object.
- **Identification in HLS Prose**:
  - *Explicit Polymorphic Phrasing*: Polymorphic services explicitly declare themselves in HLS prose using the adjective **polymorphic** (in plain text without italics), e.g., *"A \*tool\* is a polymorphic agent session service..."* or *"A \*parameter converter\* is a polymorphic agent session service..."*.
  - *Singletons*: Singleton services are introduced simply as an active service without the polymorphic qualifier, e.g., *"The \*tool manager\* is an agent session service..."*. We do not rely solely on articles ("the" vs. "a/an") to infer polymorphism.
  - *Instance Discriminators & Collections*: Polymorphic types naturally carry an instance discriminator (such as `name` or `actual_type`) and are maintained in plural collections by manager services (`installed_tools`).
  - *Typography*: "Polymorphic" is an ordinary English adjective qualifying the service; it is not an introduced entity, property, or operation, and therefore remains in plain text without italics.
- **Subtyping & Collapsing Rules**:
  - A `singleton type` **can and does extend** a `poly type`, collapsing into a concrete singleton in that session (e.g., `read tool` extends `tool`, `alias manager` extends `parameter converter`).
  - A `poly type` **cannot extend** a `singleton type`.
  - If an intermediate subtype is to remain polymorphic, it must keep specifying `poly type`.
  - Eventually, all concrete runtime objects have their own singleton type even if they extend a poly type.

### 2.12 Properties and Singleton Types (No Singleton Properties)
- **The Rule**: A `property` must never declare a `singleton type` as its type signature.
- **Linguistic & Architectural Reality**: Singular active services (`singleton type`) are singletons within their lifecycle phase and are resolved directly via the lifecycle container (dependency injection). Holding a singleton service reference as a stored property on another singleton creates redundant coupling and misclassifies service collaboration as internal data state.
- **Allowed Property Types**: Properties can only hold:
  1. Passive **data types** (primitives, identifiers, records, sum-type variants).
  2. **Polymorphic types** (`poly type`) or collections thereof (e.g., `Set of tool_provider.Tool`), where individual instances cannot be resolved purely by type identity and must be dynamically registered and tracked by a manager/registry service.
- **"Installs" vs. "Has"**: When an HLS states that a service *"installs"* tools or parameter converters (e.g. *"the read manager installs the read tool, search tool, and alias manager"*), this describes an initialization responsibility (executed during `initialize ()`), not persistent instance state of the installing service. Furthermore, because the ambient `tool manager` uniquely provides `install_tool` and `install_converter`, a statement like *"installs the read tool"* naturally grounds to calling `install_tool` on the tool manager without needing to mention the tool manager explicitly.

### 2.13 Data Types, Variants, and Hierarchy
- **Component Locality & Data Type Closure**: Data types are strictly closed within the component where they are introduced. Importing components **cannot** extend, subtype, or introduce variants for imported data types (e.g. `file_reader` cannot define a `GuideFile` subtype of `file_alias.FileAlias`). Domain roles in importing components must be expressed as properties holding existing types or variants (e.g. `guide_file: file_alias.UnboundFile or absent`).
- **Structural Equality**: Data types and variants possess value-based structural equality (unlike active services, which have identity). Two data type instances with identical constituent values (such as two `UnboundFile` instances with the same `short_name`) are structurally equal, enabling deterministic comparisons across session services.
- **Variants Introducing Properties**: When a variant introduces constituent properties (such as `BoundFile` introducing `owning_node: dag_storage.Node`), the variant row specifies its parent data type or variant in `type signature`, and its introduced fields are declared as `property` rows directly underneath it. Sub-variants specify the intermediate variant as their parent in `type signature`.
- **Do Not Use "variant" in Comments**: Never use the meta-word "variant" in the `comment` column. Describe the type directly in natural domain terms (e.g. say `Classifies read-only file as a bound file restricted to inspection`, NOT `as a bound file variant restricted to inspection`).

### 2.14 Value Derivation, Knowledge Custody, and Semantic Grounding
- **Grounding is Value Derivation, Not Syntactic Presence**: Defining a type or property in the 4-column table does not ground it. A type, property, parameter, or dependency is grounded if and only if there is a concrete, sound derivation path to produce its runtime value from in-scope knowledge, inputs, or known collaborators.
- **No Floating or Unbound Properties**: Every property on an active service or data type must originate from explicit inputs, process environment, build manifests, or collaborators in scope. Declaring a property without a mechanism to bind or derive its value is a definition-only phantom and prohibited.
- **Syntactic Validation vs Semantic Grounding**: Automated validators (checking table columns, regex, or filename parity) verify structural well-formedness, not semantic correctness. A passing check script does not prove an architecture is grounded.
- **Polymorphic Types Prohibited in `implements:`**: The front-matter `implements:` header must only list concrete singleton interface services, tools, or types being realized. Polymorphic types (`poly type`) must never be listed in `implements:`.

---

## 3. Grounding Document Format & Table Standard

A grounding document consists of imports/implements headers followed by **exactly one 4-column Markdown table**:

### 3.1 Table Columns
1. **`kind`**: Indicates the ontological category:
   - `singleton type`: Defines a fresh singular active service or component (singleton in lifecycle).
   - `poly type`: Defines an open polymorphic active service (multiton in lifecycle).
   - `override singleton type`: Defines a singular active service that overrides/realizes an imported interface type of the same name.
   - `override poly type`: Defines a polymorphic active service that overrides/realizes an imported interface type of the same name.
   - `data type`: Defines a passive data type, record, or entity identifier.
   - `is-a`: Declares an additional extended lifecycle tier or implemented interface of a different name (used when a type has multiple supertypes or interfaces beyond the first).
   - `property`: Declares a fresh field or constituent state.
   - `override property`: Declares an inherited property from an extended or overridden type.
   - `operation`: Declares a fresh callable action or query.
   - `override operation`: Declares an inherited operation from an extended or overridden type, or the built-in lifecycle `initialize` operation.
   - `variant`: Declares an exhaustive sum-type variant.
2. **`name`**: The identifier of the element (if applicable):
   - For `singleton type`, `poly type`, and `data type`: The name of the type.
   - For `property` and `operation`: The name of the member.
   - For `variant`: The name of the variant.
   - For `is-a`: Empty (not applicable).
3. **`type signature`**: The formal type declaration or signature (if applicable):
   - For `singleton type`, `poly type`, and `data type`: The first extended lifecycle tier, supertype, or implemented interface (e.g. `SystemService`, `AgentSessionService`, `AbsolutePath`), listed directly together with the type row. If none, empty.
   - For `is-a`: The additional extended type or implemented interface beyond the first (e.g. `tool_provider.ParameterConverter`).
   - For `property`: The type of the field (e.g. `boolean`, `Set of Item`, `List of Item`, `string`).
   - For `operation`: The argument and return signature (e.g. `(entity: Entity) -> Set of Target`, `(entity: Entity)`).
   - For `variant`: The parent data type or intermediate variant it extends (e.g. `FileAlias`, `BoundFile`).
4. **`comment`**: An articulate justification for the row according to the text of the specification, using as much specification language as possible rather than a raw, isolated string excerpt (without the "The specification" prefix).

### 3.2 Structure & Scoping
- **Type Separation**: An empty row with non-breaking spaces (`| &nbsp; | &nbsp; | &nbsp; | &nbsp; |`) separates types to ensure a clean, full-height row in rendered output.
- **Implicit Scope**: All rows immediately following a `singleton type`, `poly type`, or `data type` row belong to that type until the next empty row.

### 3.3 Assumptions and Requirements Sections
Directly beneath the 4-column table, dynamic behavior is expressed in natural language prose:
1. **`## Assumptions` (Preconditions)**:
   - Lists preconditions and environmental invariants assumed by the component.
   - Every assumption lists the scope it applies to:
     - `- <Type>.<operation>: <assumption sentence>` (operation precondition).
     - `- <Type>: <assumption sentence>` (environmental invariant assumed by an object type).
     - `- orphaned: <assumption sentence>` (assumption not bound to an object type).
   - **Undefined Behavior**: Violating an assumption results in **undefined behavior**, unless an explicit requirement dictates handling.
   - Omitted if the component declares no assumptions.
2. **`## Requirements` (Observable Behavioral Contracts)**:
   - Lists guaranteed postconditions, state transitions, validation boundaries, and explicit failure-handling contracts.
   - Every requirement explicitly declares the scope it applies to:
     - `- <Type>.<operation>: <requirement sentence>` (postconditions, return values, state transitions, operational failure handling).
     - `- <Type>: <requirement sentence>` (invariants on an object type or its properties, or operator-like requirements on a data type).
     - `- orphaned: <requirement sentence>` (requirements that do not belong to an object type or valid data-type operator).
   - **Scope Rules on Types**:
     - Object types (`singleton type`, `poly type`, `override singleton type`, `override poly type`) own behavioral postconditions and state invariants.
     - Data types (`data type`, `variant`) **may** own requirements that describe operator-like behaviors (such as string conversion, formatting, display, or value comparisons, e.g. `FileAlias: A file alias displays itself by its short name when converted to a string.`).
     - Data types **cannot** own requirements specifying how their properties are formed, derived, or computed (e.g. `short_name is a minimal unambiguous relative path`). Such property formation rules belong to active object types/services that manage them (e.g. `AliasManager`). When unassigned to an active object type, they are labeled `orphaned:`.
   - **Exclusions from Requirements**:
     - *Properties*: Static record fields belong as `property` rows in the grounding table and must never be duplicated in `## Requirements`.
     - *Knowledge & Type Algebra*: Static relations between types (e.g., path concatenation definitions) belong in table comments, not in `## Requirements`.
     - *Domain Purpose ("indicates")*: Explanations of what a flag or value indicates to external callers are domain purpose, not component obligations.
   - Every requirement is a single, clear declarative sentence without formal logic notation or quantifiers.

---

## 4. Illustrative Derivation Example

To demonstrate the application of these extraction rules, consider the following domain-agnostic specification excerpt:

### Source HLS Prose Excerpt
> An *artifact* identifies a discrete build output in the compilation pipeline. An *artifact repository* is a system service that maintains artifact state, including provenance and verification records. An artifact in an artifact repository has:
> 
> - *Prerequisites* that refer to upstream artifacts required to produce it. A prerequisite can be *advisory* to indicate that downstream verification does not block on it.
> 
> - *Consumers* that refer to downstream artifacts depending on it. An artifact can be *registered* to all of its non-advisory prerequisites so that it can be notified when prerequisites change. The consumers of an artifact can be *cleared* to avoid stale dependencies.
> 
> - *Diagnostics* explaining why an artifact failed verification. A diagnostic can indicate either *warning*, which reports non-blocking issues, or *error*, which reports verification failure. Diagnostics can be *recorded* for an artifact to inform on verification status, as well as *cleared*.

---

### Faithfully Grounded 4-Column Table Specification

```markdown
# artifact_repository grounding

| kind | name | type signature | comment |
| :--- | :--- | :--- | :--- |
| singleton type | ArtifactRepository | SystemService | Defined as a system service maintaining artifact state, including provenance and verification records |
| operation | get_prerequisites | (artifact: Artifact) -> Set of Prerequisite | Refer to upstream artifacts required to produce it |
| operation | get_consumers | (artifact: Artifact) -> Set of Artifact | Refer to downstream artifacts depending on it |
| operation | get_diagnostics | (artifact: Artifact) -> Set of Diagnostic | Explaining why an artifact failed verification |
| operation | register_dependent | (artifact: Artifact) | Registered to all of its non-advisory prerequisites so that it can be notified when prerequisites change |
| operation | clear_consumers | (artifact: Artifact) | To avoid stale dependencies |
| operation | record_diagnostic | (diagnostic: Diagnostic, to: Artifact) | To inform on verification status |
| operation | clear_diagnostics | (artifact: Artifact) | To remove verification diagnostics |
| &nbsp; | &nbsp; | &nbsp; | &nbsp; |
| data type | Artifact | | Identifies a discrete build output in the compilation pipeline |
| &nbsp; | &nbsp; | &nbsp; | &nbsp; |
| data type | Prerequisite | | Refer to upstream artifacts required to produce it |
| property | artifact | Artifact | Upstream artifact required to produce it |
| property | is_advisory | boolean | To indicate that downstream verification does not block on it |
| &nbsp; | &nbsp; | &nbsp; | &nbsp; |
| data type | Diagnostic | | Explaining why an artifact failed verification |
| variant | Warning | | Reports non-blocking issues |
| variant | Error | | Reports verification failure |

## Requirements

- ArtifactRepository.register_dependent: An artifact can be registered to all of its non-advisory prerequisites so that it can be notified when prerequisites change.
- ArtifactRepository.clear_consumers: The consumers of an artifact can be cleared to avoid stale dependencies.
- ArtifactRepository.record_diagnostic: Diagnostics can be recorded for an artifact to inform on verification status.
- ArtifactRepository.clear_diagnostics: Diagnostics of an artifact can be cleared to remove verification diagnostics.
- orphaned: A prerequisite can be advisory to indicate that downstream verification does not block on it.
```
