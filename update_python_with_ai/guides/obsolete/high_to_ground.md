# Guide: Deriving Grounding Specifications from High-Level Specifications

## Summary

The grounding specification formalizes the knowledge custody graph and atomic behavioral requirements from an HLS (`high/<name>.md`), deriving structural relationships (`kind`, `has`, `is a`, `param`, `parent`) and decomposing prose into testable atomic requirements without collaborator satisfaction checks. Grounding classifies types as object types (active components with atomic requirements) or data types (passive records and variants). All entries derive from `## Type and Behavior`; declared intent provides semantic context, omitting narrative rationale.

The artifact lives under `grounding/<name>.md`, mirroring the source specification basename. Editing is in place and preserves conformant entries. Requirements trace directly to explicit guarantees in the source HLS; speculative behaviors or unstated mechanics are prohibited.

## Artifact structure

- [ ] The artifact is titled `# <name> (Grounding)`, where `<name>` matches the source specification basename
- [ ] Front-matter headers (`imports:`, `assembles:`, `instantiates:`) are replicated from the source HLS; `types from <dep>:` lines declare every external type referenced in knowledge relationships or requirements
- [ ] The document contains exactly two top-level sections after the title and optional header: `## Knowledge Relationships` followed by `## Atomic Requirements`
- [ ] Section headings use `##`; both `## Knowledge Relationships` and `## Atomic Requirements` use consistent top-level list item headers (`- **<type>**` or `- **<entity>** in **<storage>**`)
- [ ] Requirements appear as indented sub-bullets under their component list item header
- [ ] Type names match the spelling and casing in `## Type and Behavior`; collections use singular type names preceded by "set of" (e.g. `has: set of **item**`), referenced as the singular type or "set of **<type>**" in requirements
- [ ] No markdown links, code execution directives, or file system paths appear anywhere in the artifact

## Knowledge relationships

- [ ] Knowledge relationships and requirements derive from `## Type and Behavior`; intent recorded via `intent:` is framed using structural references (`this`, `parent`, `grandparent`, `parent's <constituent>`), rather than copying unanchored pronouns from prose
- [ ] When an entity is an association pointing to a domain entity (via `has: <target>`), child properties on the reference distinguish the association record ("parent") from the referenced entity ("parent's <target>"), referring to the container holding the association as "grandparent"
- [ ] Every active component, factory, and domain type introduced or instantiated in `## Type and Behavior` appears in `## Knowledge Relationships`
- [ ] Every entity declared in `## Knowledge Relationships` specifies its classification via sub-bullet `kind: object type` or `kind: data type` (scoped `- **<entity>** in **<storage>**` entries omit `kind:`, inheriting the container's kind)
- [ ] Active components, services, and factories declare `kind: object type`; passive values, records, tokens, and variants declare `kind: data type`
- [ ] Ontological sub-types (`is a:`) inherit the kind of their super-type (a sub-type of a data type is a data type; a sub-type of an object type is an object type)
- [ ] For object types, `parent:` establishes reified structural custody granting access to container capabilities and dependencies; for data types, `parent:` establishes lexical scoping and association without mandating reified runtime custody
- [ ] Public constituent properties declared with "has" in the HLS appear as `- **<type>**` with sub-bullet `has: <constituent>` only when clients of the value can read that constituent directly from the data structure
- [ ] Declaring that an entity introduces or "has" a constituent automatically establishes that the constituent is parented by that entity (`parent: **<enclosing_type>**`), regardless of bullet indentation in the source specification
- [ ] Constructor parameters read only internally appear as sub-bullet `param: <dependency>`; parameters exposed as public readable constituents appear only as `has: <constituent>`
- [ ] Relational state in an enclosing store is scoped using `- **<entity>** in **<storage>**` with `has: <constituent>`; scoped entries implicitly parent to the container and inherit its kind, omitting `kind:` and `parent:`; relational attributes declare `kind: data type` with `parent: **<entity>** in **<storage>**`; domain identifiers omit `parent:`
- [ ] Ontological specializations declared with "is a" in the HLS appear as `- **<sub_type>**` with `is a: <parent_type>`. An entity Y that refers to X is only an X if explicitly declared as "Y is an X" in the HLS (e.g. `read-only document` is a `document`); if Y merely references X or incorporates X in its name (e.g. `target server`), Y is an association entity declaring `has: **X**`, never `is a: **X**`
- [ ] Subtypes cannot be parented by their super-type (`parent:` is structural containment, `is a:` is ontological specialization); a subtype shares its super-type's parent unless declared under another container that specializes or matches that parent
- [ ] Readable constituent collections on an enclosing component (such as `has: items`, `has: records`) are populated by child entities whose `parent:` points to the container and whose `is a:` specializes the collection element type
- [ ] Compound noun phrases that specialize an existing type (via explicit "is a" in the HLS) declare `is a: <base_type>`, rather than collapsing into bare references; role or association phrases without "is a" declare `has: <base_type>`
- [ ] Factory creation operations are declared as a first-class construct `- **<factory>.create**` with sub-bullet `parent: **<factory>**`, and creation parameters declared as `param: <dependencies>`
- [ ] Constructed products declare `parent: **<factory>.create**`, granting access to parent requirements and dependencies (downward `constructs:` directives are omitted)
- [ ] Contained sub-components declare sub-bullet `parent: **<container>**`, granting access to container requirements and dependencies throughout the parent hierarchy
- [ ] The `assembles:` directive belongs strictly in the replicated front-matter header of implementation specifications and never appears as a relationship bullet under `## Knowledge Relationships`
- [ ] Collaborator access is granted through the parent hierarchy; `knows via` relationship bullets are not used
- [ ] Constituents and property names avoid pointless prepositions or parenthetical commentary; only the clean constituent or type name appears
- [ ] All type names in knowledge relationships and requirements are unqualified; external types are declared in the `types from <dep>:` header rather than qualified with component prefixes
- [ ] Simple scalar attributes (name, description, content) are not domain entities, omit type blocks, and are not bolded (e.g. `has: name`). Domain identifiers beyond simple common nouns declare their own type blocks and are bolded

- [ ] Literal values, external tool names, or identifiers enclosed in quotes or backticks within message text represent literal strings and never declare domain entity types requiring knowledge relationships
- [ ] Nested entities appear as nested types declaring `parent: **<nesting_type>**` (no dot notation); a nested type is referred to only in the nesting type or types having the nesting type as an ancestor in their parent hierarchy
- [ ] Outside a nested type's parent hierarchy, references to that nested type are framed as property references through its nesting container (e.g. "a **<nesting_type>**'s **<nested_type>**") rather than bare entity references
- [ ] Passive data records, scalar parameters, enums, and boolean flags never declare "knows" dependencies on other types
- [ ] Imported types referenced in compound noun phrases or shortened specialized names (e.g. "read tool execution" for execution) count as valid references to those types

## Component requirements

- [ ] Only object types appear as top-level list item headers in `## Atomic Requirements`
- [ ] Data types (records, tokens, payload structures, variant tags, boolean flags) never appear as standalone list item headers in `## Atomic Requirements` and never declare `operation:` or `invariant:` requirements
- [ ] Requirements on storage-managed entities are grouped under the entity's store-scoped header (`- **<entity>** in **<storage>**`); requirements implicitly act on that scoped entity, omitting redundant references to it (e.g. `adds a **record**`, `clears the set of **item**`)
- [ ] Every requirement is flagged with a leading tag: `` `invariant`: `` for constraints, validation rules, and state invariants, and `` `operation`: `` for state mutations, actions, and capabilities
- [ ] Requirements are framed directly in terms of declared types and constituents rather than copied text from the source specification
- [ ] All references to declared types, constituents, and collaborating components in requirements are bolded
- [ ] State invariants express the exact condition on the constituent using bolded type names (e.g. `**<state>** is true if (but not only if) it has **<items>**`)
- [ ] Operations and capabilities express state mutations using active verbs and bolded type names for inputs and affected constituents
- [ ] Every requirement must be satisfiable by the component's implementation: if a statement cannot be satisfied by the type as a requirement (such as client usage intent, consumer needs, or passive ontology), it is intent and must not be listed as an atomic requirement
- [ ] Source specifications may use descriptive adjectives for conditions and states; grounding resolves these adjectives to declared constituent field names or formal type names (e.g. resolving "is active" to `**active flag** is true`)
- [ ] Every entity, property, or constituent referenced in a requirement must resolve to a declared relationship, constituent, or collaborator in scope; undeclared entities are prohibited
- [ ] Public constituents declared with "has" are directly accessible to clients and never generate getter or provision `operation:` requirements; storage repositories define requirements only for storage invariants and mutation operations
- [ ] Declaring or possessing constituent properties with "has" defines data structure shape and is not an invariant; setting, having, or populating a constituent property never appears as an `invariant` requirement
- [ ] Compound phrases in source specifications are decomposed into separate unidirectional `` `operation`: `` requirements (e.g. translating "between" representations decomposes into two unidirectional operations)
- [ ] Requirements state capabilities directly without naming collaborator routing details (e.g. omit "using <collaborator>"); when an operation uses a constituent produced or mapped by another operation, the requirement traces the derivation through that mapping directly
- [ ] Requirements state mechanical invariants and operations interpreted through declared intent; explanatory rationale clauses ("to support...", "so it can...") are never copied into requirement text
- [ ] Compound specification sentences are decomposed: constraints on passive output payload contents (such as diagnostic text) are independent invariants; only state mutations and callable capabilities are operations
- [ ] Specialized components inherit nested member types from base types without re-declaring formation operations or inventing new type names; atomic requirements on specialized nested instances are headed using the specialized component and nested type (e.g. `- **<specialized_component>** **<nested_type>**`)
- [ ] Explanations of what a constituent or flag signifies when set define the passive semantic interpretation of data, never an active operation to set or mutate that constituent
- [ ] Product construction is defined exclusively in `## Knowledge Relationships` through `- **<factory>.create**` and product `parent: **<factory>.create**`; factories never declare a redundant `operation:` creates requirement in `## Atomic Requirements`
- [ ] Decomposing requirements preserves communicative nuance: permissive phrasing (such as "can remind") expresses intent and must not be flattened into rigid constraints
- [ ] Atomic Requirements can be empty if the specification contains only knowledge relationships, high-level intent, or capabilities deferred to implementation specifications
- [ ] Grounding requirements elaborate conditions via exact structural mechanisms (parameter bindings, collaborator lookups, optional constructor dependencies) rather than copying conversational shorthand


## Common pitfalls

- [ ] Qualified type names — prepending imported types with component names instead of declaring them in the front-matter header and keeping body references unqualified
- [ ] Missing import headers — omitting `imports:`, `assembles:`, or derived `types from <dep>:` header lines from the grounding artifact
- [ ] Out-of-scope nested references — referencing a nested type outside of its nesting type or outside of types that have the nesting type in their parent hierarchy
- [ ] Dot notation on nested types — using dot-qualified names for nested entities instead of declaring them with parent: and unqualified names
- [ ] Parenting by super-type — setting parent: to an entity's super-type instead of its enclosing structural container (conflating ontological specialization is a: with structural containment parent:)
- [ ] Invalid subtype parent — parenting a subtype under an enclosing type that is not identical to or a subtype of the supertype's parent
- [ ] Indentation-derived parent — assigning parent: based on markdown bullet indentation rather than following the enclosing entity that introduced or "has" the constituent
- [ ] Missing type kind — omitting the `kind: object type` or `kind: data type` sub-bullet under an entity in `## Knowledge Relationships` (except scoped `- **<entity>** in **<storage>**` entries)
- [ ] Requirements on data types — placing a data type as a top-level header in `## Atomic Requirements` or attributing `operation:` or `invariant:` requirements to it
- [ ] Reified data type parent — treating a data type's lexical `parent:` as reified runtime custody requiring back-pointers
- [ ] Collapsing specialized types — substituting an existing base or value type for a new specialized entity when prose uses the existing type name as a modifier in a compound noun phrase
- [ ] Assembles in knowledge relationships — writing `assembles:` under a type block instead of keeping it strictly in the replicated front-matter header
- [ ] Using knows via — declaring `knows via` relationship bullets instead of relying on the parent hierarchy
- [ ] Using constructs — declaring downward `constructs:` bullets under factories instead of relying exclusively on the child's `parent:` relationship
- [ ] Redundant param on public constituent — listing an entity under both `param:` and `has:` when `has:` already captures publicly readable constructor parameters
- [ ] Constituent invariant inflation — framing the possession of a constituent as an atomic invariant instead of relying on `has`
- [ ] Getter operation inflation — defining an `operation:` to retrieve, access, or provide a constituent that the entity already declares with `has`
- [ ] Invented flag setters — creating an operation to set a flag or constituent when the specification only defines what it signifies if set
- [ ] Conflated condition and effect — combining a condition constraint and its resulting mutation or output into one requirement instead of splitting them
- [ ] Output content as operation — tagging declarative constraints on passive output payload content (such as diagnostic or payload text) as callable operations instead of invariants
- [ ] Conversational shorthand in grounding — echoing informal high-level phrases (such as "if processing target") instead of elaborating the exact parameter binding, collaborator lookup, or configuration state that evaluates the condition
- [ ] Re-specifying inherited formation — re-declaring instance formation on a derived component when the base component already defines the nested type's formation
- [ ] Redundant factory creation operation — declaring an `operation:` creates requirement under a factory when construction is already specified by `- **<factory>.create**`
- [ ] Semantic flattening — stripping communicative intent, guidance, or behavioral nuance when formalizing requirements into mechanical jargon (e.g. reducing caller diagnostic feedback into a raw token list)
- [ ] Client intent as requirements — converting client usage needs, external consumer distinctions, or un-enforceable intent into atomic requirements instead of recognizing them as domain intent
- [ ] Fabricated interface requirements — converting descriptive ontology from an interface specification into pseudo-operations instead of deferring requirements to implementation specifications
- [ ] Unresolved adjectives — copying descriptive adjectives from specification prose directly into requirements instead of resolving them to declared constituent fields or types
- [ ] Quoted literal as domain entity — treating literal strings or command identifiers enclosed in quotes or backticks within message text as domain types requiring knowledge relationships
- [ ] Purpose narrative leakage — extracting types, dependencies, or requirements from `## Purpose` rather than strictly from `## Type and Behavior`
- [ ] Vague dependency keywords — using "from" or "configured with" instead of "param" for implementation-read configuration parameters
- [ ] Ungrounded references — referencing an undeclared entity, property, or constituent in a requirement (a mystery name)
- [ ] Free-floating constituents — referencing a constituent without grounding it through the operation or mapping that produces its owning entity
- [ ] Unsatisfiable requirements — attributing an invariant or operation to a stateless or passive type that cannot enforce or satisfy it
- [ ] Compound operations in grounding — failing to decompose compound phrases from the source specification into separate unidirectional operations
- [ ] Unflagged requirements — omitting the leading `` `invariant`: `` or `` `operation`: `` tag on atomic requirements
- [ ] Verbatim copying — copying prose sentences verbatim instead of framing requirements in terms of declared types and constituents
- [ ] Passive object knowledge — declaring that passive records, identifiers, or flags "know" other entities
- [ ] Umbrella verbs — using vague procedural verbs ("maintains") instead of explicit storage invariants and state transitions
- [ ] Phantom collaborators — introducing external services or helpers not declared in the source HLS
- [ ] Directional hallucinations — adding unstated qualifications to relational entities
- [ ] Entity field inflation — attributing storage-managed relations to an entity's data structure when state is held by an enclosing store
- [ ] Ambiguous intent pronouns — copying prose pronouns or conflating an association ("parent") with its referenced target ("parent's <target>") instead of navigating the tree via "this", "parent", "grandparent", or "parent's <target>"
- [ ] Conflating role reference with subtype — declaring an entity as is a: **<type>** merely because its name contains or references that type, instead of has: **<type>** for association (subtyping strictly requires explicit "Y is an X" ontology in the source)
