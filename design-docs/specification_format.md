# Specification Format & Architecture Design

## 1. Overview & Core Philosophy

The Cleanroom specification language defines software components declaratively through their types, capabilities, and lifecycles in a **literate, high-level prose format**.

Its primary objective is **judging the quality of satisfiability**: given the types and capabilities declared in an architecture, can an LLM (using its weights and semantic reasoning) compose available operations to fulfill an implementation requirement without guesswork or ungrounded dependencies?

We intentionally embrace:
- **Literate Prose over Micro-Syntax**: Specifications read like natural, cohesive architectural prose rather than abstract syntax trees, pseudo-code, or deeply indented bullet hierarchies.
- **Selective Single-Level Bullet Paragraphs**: Under `## Types and Behavior`, bullets are used selectively to enumerate distinct parallel sub-items or constituent collections—never to itemize fields of an object. When bullets are used, formatting strictly uses at most one level of bullet points, with each bullet point formatted as its own standalone paragraph separated by a blank line.
- **Italics as Generalized Semantic Markers**: Rather than imposing rigid categorization schemes or syntactic tags, italics (`*term*`) are used as lightweight markers indicating a potential entity: an object type, data type, property/state, sub-type, constituent collection, or operation.
- **Deferred Extraction Phase**: The specification does not explicitly classify whether a term is a class, protocol, field, or method. The grounding engine decodes and classifies these italicized markers during a separate extraction pass.

---

## 2. Types and Behavior: Literate Semantic Markers

Types and behaviors are presented together in a unified **`## Types and Behavior`** section.

### 2.1 Prose Structure & Single-Level Bullets
- The section begins with fluid introductory prose defining foundational entities, services, and relationships.
- Subordinate capabilities, features, and properties are organized as a flat list of top-level bullets—**never nested sub-bullets**.
- Each bullet point is an independent paragraph, separated by blank lines, providing sufficient space for rich, complete sentences.

### 2.2 Italics as Semantic Markers
In the high-level specification, we do not call out or label whether an entity is an object type, data type, property/state, constituent collection, or operation. Instead, whatever could be one of those is placed in italics (`*term*`):
- Potential object types / services (e.g., `*dag storage*`, `*file paths*`, `*tool provider*`, `*file reader*`).
- Potential data types / records (e.g., `*node*`, `*host path*`, `*file content*`, `*matches*`).
- Potential properties or states (e.g., `*dependencies*`, `*dependents*`, `*messages*`, `*dirty*`, `*silent*`).
- Potential sub-types / variants (e.g., `*change*`, `*feedback*`, `*read-only file*`, `*read-write file*`).
- Potential operations / actions (e.g., `*registered*`, `*cleared*`, `*added*`, `*read*`, `*execute*`, `*convert*`).
- Operation arguments (e.g., executing by `*name*` with `*wire parameter bindings*`, converting a `*wire type*` value). The arguments of an operation must be italicized upon introduction so that the extraction phase can cleanly capture the operation's parameter names and signatures.

Common scalar attributes (such as `*name*` and `*description*`) must be italicized whenever they represent properties of an entity (e.g., on a `*tool*` or a `*parameter*`), ensuring that the extraction phase recognizes them as constituent properties rather than ambient prose.

**Italics on Introduction for Each Concept (Semantic vs. Lexical)**:
Italics mark the **introduction** of an entity, property, state, sub-type, or operation on a concept. This is a semantic declaration, not a lexical word-uniqueness check:
- **Introductions with the Same Name**: If a property or operation is introduced for a concept, it **must** be italicized, even if that word has already appeared or was introduced for another concept (or for another constituent of the same concept). For example:
  - Both `*tool*` and `*parameter*` introduce a `*name*` and a `*description*` (so `*name*` and `*description*` are italicized in both introductions).
  - A `*dag storage*` allows dependents to be `*cleared*`, and allows messages to be `*cleared*` (both are distinct operations being introduced on their respective constituents, so both are italicized).
  - A `*tool manager*` allows tools to be `*installed*`, and allows parameter converters to be `*installed*` (installing parameter converters is a distinct operation being introduced on tool manager, so both are italicized).
- **Subsequent References in Plain Text**: When a previously introduced concept, type, property, or operation is merely being **referred to** (e.g., used as a parameter, subject, or context, such as referring back to `tools`, `parameter converters`, `file aliases`, or `tool manager`), it is written in plain text without italics.
- **Imported Terms in Plain Text**: Any concept or term imported from an upstream dependency (such as `parameter converter` in `file_alias.md`, or `read-only files` in `file_reader.md`) must be written in plain text without italics, preventing the extraction pass from re-declaring or misattributing imported types to the importing component.


### 2.3 Relationships: Explicit and Naming Connections
Relationships can be specified in two natural ways:
1. **Explicitly**: Declared via natural relational verbs (e.g., `*dag storage* is a system service...`).
2. **Via Naming Connection**: Declared through natural ontological naming without requiring redundant relational boilerplate. For example, a `*read tool*` or `*search tool*` installed by a `*read manager*` is recognized as a tool by its naming connection alone, without needing an explicit statement that `a read tool is a tool`.

The grounding engine resolves these naming connections and extracts formal inheritance, composition, and method contracts during the separate extraction phase.



---

## 3. Lifecycle Tiers & Flat Object Architecture

Component visibility and lifetime are governed by **Lifecycle Tiers** expressed directly in natural language with italicized tier specifiers.

### 3.1 Lifecycle Tiers
Every service and object type declares its lifecycle tier in natural language, with the tier italicized:
- **`*system*` Services**: Live for the entire process or run (stateless services, external boundaries, or process-wide stores, e.g., `file_paths`, `dag_storage`).
  - *Example*: `A dag storage is a *system* service that maintains graph structure, change propagation, and node state.`
- **`*agent session*` Services**: Live for the duration of cleaning a single node or manifest target (e.g., `tool`, `parameter converter`, `tool provider`, `file reader`, `alias mapper`).
  - *Example*: `A tool is an *agent session* service that defines an executable action available to an agent...`
  - *Example*: `A tool provider is an *agent session* service that maintains tools and parameter converters for an agent session.`

### 3.2 No Object Type Hierarchy
Object types do not form containment or ownership hierarchies:
- **Flat Service Model**: Any object type can access and call operations on any other object type as long as they belong to the same lifecycle tier (or a longer-lived tier). A `*tool*` is not a subtype or contained type under `*tool provider*`; both are independent `*agent session*` services.
- **Constituent Properties vs. Object Types**: Hierarchy in specifications strictly represents constituent state, data records, or properties belonging to an entity (e.g., a tool's parameters, or a node's dependencies)—it does not represent containment of independent object types or services.
- **Registry Services via Explicit Operations**: Services that maintain collections of other services (such as `*tool provider*`) do not own their constituents as nested types. Instead, instances (such as tools and parameter converters) are independent session services that are *added* to the registry via explicit operations (e.g., `Tools can be *added* to a tool provider...`).

### 3.3 Visibility Rules
1. **Same-Tier Visibility**: Within a tier, any object can access and call operations on any other object in that same tier.
2. **Downward Visibility**: Short-lived tier objects (e.g., `*agent session*`) can access and call operations on long-lived tier objects (e.g., `*system*`).
3. **Upward Isolation**: A long-lived tier object (e.g., `*system*`) cannot hold references to short-lived tier objects (e.g., `*agent session*`), preventing memory leaks and stale cross-session references.
4. **No Factory Plumbing**: Factories are eliminated from the domain ontology. Container and runner frameworks instantiate session phase objects directly.
5. **Subsystem Assembly via `_asm` Components**: System and subsystem composition is handled by dedicated assembly components (`<name>_asm.md`) that aggregate constituent implementation modules and register their singletons into the `LifecycleRegistry`.

### 3.4 Data Types, Variants, and Hierarchy
- **Data Types vs. Object Services**: While active services are flat and governed by lifecycle tiers, passive data types (such as `file alias`, `node`, `line range`) represent structured immutable values with structural equality.
- **Component Locality & Data Type Closure**: Data types are strictly closed within the component that introduces them. Importing components **cannot** extend, subtype, or add variants to an imported data type (e.g., `file_reader` cannot define a `guide file` subtype or variant of `file_alias`). If an importing component uses an imported data type in a specific role, that role is represented as a property referencing the data type or an existing variant thereof (e.g., a read manager is configured with a guide file, which is an unbound file).
- **Variants Introducing Properties**: Variants of a data type can introduce constituent properties (e.g., `bound file` introduces a `workspace path` and an `owning node` for an actual workspace file, whereas `unbound file` is not mapped to an actual file). Sub-variants (`read-only file`, `read-write file`) inherit the properties of their parent variant.
- **Structural Value Equality**: Data types and their variants have value-based structural equality rather than reference identity. Any two instances constructed with identical field values compare as equal, allowing lookups across session services to match reliably.
- **Data Types Without Public Constructors**: Value records constructed exclusively through service operations (such as path representations or file aliases) rather than direct caller instantiation state this explicitly in prose. In grounding stubs, they are marked with `@dataclass(frozen=True, init=False)` without an `__init__` constructor method, ensuring callers cannot bypass system validation or construction invariants. Leaf data types with direct public construction declare `@dataclass(frozen=True, init=True)` (or default `@dataclass(frozen=True)`) and define a matching `__init__`.

### 3.5 Lifecycle Phase Execution & Non-Procedural Specifications
- **Phase Scoping**: A lifecycle phase (such as an `*agent session*`) is governed by execution logic that runs the phase from beginning to end (e.g., an execution block or context manager). Lifecycle phases do not have imperative `start` or `stop` operations; they are established as execution blocks within which session services exist and operate.
- **Scoping & Ambient Context**: The component driving execution within a lifecycle phase (e.g., `agent_node_cleaner_impl`) executes the workload within this block, establishing the scope for ambient session services (such as configuring the node being cleaned) before session services interact.
- **Avoiding Procedural Over-Specification**: High-level specifications must describe this declaratively rather than detailing step-by-step procedural recipes or lifecycle pseudo-code. State relationships and invariants declaratively (e.g., *"The agent node cleaner cleans a dirty node within an agent session phase, letting other agent session services know what the current node is"*), avoiding procedural ordering ("first", "then", "before doing X", "stops the agent session").

### 3.6 Knowledge Custody, Value Derivation, and True Grounding
- **Grounding is Value Derivation, Not Syntactic Presence**: Introducing a concept or property with italics or listing it in a table does not ground it. An entity, property, parameter, or dependency is grounded if and only if there is an unbroken, concrete derivation path to produce its runtime value from in-scope inputs, process environment variables, CLI parameters, build manifests, or known collaborators. If a value cannot be derived, it is ungrounded.
- **Strict Tier Custody Rules**:
  - `*system*` services have process-wide lifetimes. They cannot hold state or references to short-lived `*agent session*` services, and cannot magically access per-node or session-specific metadata unless explicitly passed as an operational argument or retrieved from an ambient system store.
  - `*agent session*` services operate strictly within an established agent session phase for a single node. They may freely access system services and other session services within the active phase.
- **The Anti-Hand-Waving Mandate**:
  - Specifications must never introduce floating sources or hand-wavy resolution logic (e.g., stating that a component *"loads execution parameters from a target module in runfiles"* without specifying what provides the target identity, what mechanism reads the module, or how it is bound).
  - Any external dependency or configuration input must be explicitly grounded by an in-scope collaborator, parameter, or process environment contract.
- **Syntactic Validation is Not Semantic Grounding**: Automated validators (regexes, table column parsers, filename matchers) verify surface formatting compliance only. They do not prove semantic grounding. Never claim an architecture is grounded merely because automated syntax checks pass.

---

## 4. Component Types & Naming Conventions

### 4.1 Document Title & Component Naming
- **Document Title**: The main title of the specification must name the component along with its component type:
  ```markdown
  # <name> <interface | implementation | external | assembly> component
  ```
  *(e.g., `# dag_storage interface component`, `# filesystem_ext external component`, `# file_reader implementation component`, `# dag_asm assembly component`)*.
- **Component Reference in Prose**: Always refer to the component by its full component name in prose (e.g., `the dag_storage interface component`).

### 4.2 Interface Components (`<name>.md`)
- Define the public object types, data types, and capabilities.
- Serve as the **Bill of Sale**: what outside consumers can expect and rely upon.
- Form the exact blueprint for **mock creation** during unit testing.
- **The Interface Completeness Mandate**: Other components that implement an interface type (e.g. concrete tools implementing `tool_provider.Tool`) or call its operations ONLY have access to the interface specification (`<name>.md`), never to implementation specifications (`<name>_impl.md`). Therefore, the interface specification MUST establish all public properties (such as `is_required`, `name`, `description`), operations, and general behavioral expectations (such as diagnostic content on failure) required by implementers and callers. An interface must never hide or omit properties that external implementers are required to define.
- **The Interface Minimality Principle**: If an interface can be used without a detail in the interface, that detail belongs in the implementation. Never leak internal mechanics, loop bounds, visit counters, or algorithmic limits into an interface contract when consumers can use the abstraction without them.
- **Preconditions on Client Operations**: Preconditions and input invariants on operations that client components invoke (such as `install_tool` requiring that all installed tools have unique names) MUST be exposed in the interface under `## Assumptions`, so calling components understand the constraints they must satisfy.

### 4.3 Implementation Components (`<name>_impl.md`)
- The concrete unit of library code and unit test execution.
- Declares `implements: <types>` in front-matter to explicitly specify all realized singleton interface services, tools, or types. In flat lifecycle specifications, `implements:` must list all realized singleton interfaces explicitly (e.g., `implements: bazel graph storage, dag storage` or `implements: agent node cleaner, cleaned node`). Polymorphic types (`poly type`) must NEVER be listed in `implements:` clauses; only concrete singleton interface services, tools, or types being realized are listed.
- Refine capabilities into concrete algorithms, naming, validation rules, and error conditions for the installed tools and services.
- Can declare implementation-private data types and parameters (e.g., `regex pattern parameter`).
- **Implementation Isolation & The Model Interaction Boundary**:
  - Requirements declared in an implementation specification govern ONLY the private code generated for that specific component. They are never inherited, shared, or relied upon by external implementers or callers.
  - **The AI Model is an Unreliable Black Box**: The language model is an external entity communicating via raw wire text. Orchestrators (such as `agent_runner`) are execution harnesses ferrying text back and forth, not semantic proxies for the model.
  - **`ToolManager.execute_tool` vs. `Tool.execute_tool`**:
    - `Tool.execute_tool` is a contract between deterministic software components, operating over typed `ActualParameterBindings`. Domain tool failures (such as `read_file` rejecting unanchored reads) are interface requirements that concrete tool components must implement.
    - `ToolManager.execute_tool` is the defensive boundary protecting the system against the black-box model. Resolving tool names, resolving parameter names, validating that required wire parameters were supplied, catching conversion failures, and generating diagnostic error strings for the model context are strictly **private implementation mechanics of `ToolManagerImpl`**. They are not contracts that other software components implement or inherit.

### 4.4 External Boundary Components (`<name>_ext.md`)
- Remain the strict boundary for external libraries, serialization formats (JSON, Proto), and OS APIs (e.g., `filesystem_ext`).
- Do not perform grounding satisfaction checks; they encapsulate foreign environments.

### 4.5 Assembly Components (`<name>_asm.md`)
- Aggregate and close a cohesive set of implementation components into a subsystem assembly.
- Declares `imports:` (which may import `*_impl` modules and other `*_asm` modules) and `implements:` (listing the closed interfaces provided to external consumers).
- Initializes constituent implementation components and registers their singletons into the `LifecycleRegistry`.
- Strictly isolated: Non-assembly components are prohibited from importing `*_impl` or `*_asm` specifications.

---

## 5. Capabilities and Requirements

An object type serves a role by providing **capabilities**. A capability consists of:
1. **Callable Operations**: What methods or actions can be invoked on the object.
2. **Behavioral Constraints**: What must be true when operations are called:
   - State mutations.
   - Return values and outputs.
   - Validation rules and failure conditions.

Requirements are phrased declaratively around the data types involved, without micromanaging collaborator routing or step-by-step pseudo-code.

---

## 6. Purpose Section: Motivation & Out of Scope

The `## Purpose` section provides the architectural justification for the component. It is strictly structured into three elements:

### 6.1 Summary Sentence (First Sentence)
- Must name the component (`The <name> <component_type> ...`).
- Must articulate **Why** the component exists (its reason for being, system role, friction solved) rather than **How** (enumerating internal data structures, algorithms, or mechanical steps).

### 6.2 Architectural Rationale (Second Paragraph)
- Must **motivate** `Types and Behavior` from an architectural perspective: system problems, cascading risks, workflow failure modes prevented, and boundary isolation.
- Must **not overlap or replicate** the operational/behavioral details declared in `Types and Behavior` (avoid naming specific fields, schemas, or method mechanics).
- **Motivate Model Boundary Defense**: For components sitting on the model interaction boundary, the rationale should explain why the system cannot assume the external model follows contracts. Unreliable model behavior necessitates comprehensive input verification and explicit expected failures in `Types and Behavior` rather than assuming valid caller inputs.

### 6.3 Out of Scope Paragraph
- A short paragraph at the end of `## Purpose` qualified by `**Out of scope:** <text>`.
- Identifies at a high level what details in `Types and Behavior` express client workflow purpose, background intent, or caller motivation rather than binding requirements on the component.
- Prevents the grounding engine from confusing workflow rationale (such as change notifications or message semantics) with active component requirements.
- **Distinguish Client Motivation, Not Implementation Delegation**: Out of scope is used strictly to differentiate usage cases mentioned as context or motivation in `Types and Behavior` from the component's actual obligations. Do not list low-level operations that the component delegates to its lower-level dependencies (e.g., do not say `file_reader` does not perform disk I/O or regex searches). Instead, scope out high-level client usage cases and orchestration motivations that appear in `Types and Behavior` (e.g., startup context injection, delivering progressive workflow instructions, or advancing workflow steps).
- **No Specific Other Components**: Never specify or name specific other components that will perform what this component does not do (e.g., avoid naming `agent runner`, `filesystem services`, or `editing tools`). Refer to them generically as **"other components"** (e.g., `...; these are handled by other components.`).

---

## 7. Punctuation, Typography & Formatting Rules

To ensure predictable parsing by LLMs and effortless human readability:

- **Italics for Concept Introductions (Semantic, Not Lexical)**: Italics (`*term*`) are used as semantic markers strictly when introducing an entity, property, state, sub-type, or operation for a concept. If another concept (or constituent) introduces a property or operation with the same name (such as `*name*`, `*description*`, `*added*`, or `*cleared*`), it is italicized upon introduction for that concept. In contrast, merely referring to an already-introduced concept, type, or property uses plain text. Terms imported from other components also remain in plain text.
- **Avoid Pseudo-Code Jargon ("Optional", "Flag") — Express Semantic Intent**:
  - Never describe a parameter or property as "optional". Instead, state its purpose directly (e.g., *"accepting line numbers to format content with line numbering"*).
  - Avoid calling boolean parameters or states "flags" (e.g., avoid `line number flag`). "Flag" reduces literate prose to pseudo-code variable naming and invites ambiguous tri-state confusion (`true` vs `false` vs empty). Instead, express the domain action or state directly (e.g., *"reading a read-write file requires requesting line numbers, whereas reading a read-only file requires omitting them"*).
- **Avoid "X is enabled" — Express Purpose**: Avoid describing features, modes, or options as "enabled" or "disabled" (e.g., avoid *"whether step mode is enabled"*). Instead, state their purpose directly in terms of domain action (e.g., *"whether the agent should use step mode to communicate a guide to the agent progressively"* or *"whether the agent should perform startup reads to inspect declared files at session start"*). "X is enabled" is a specification smell indicating incomplete or mechanical specification.
- **Declarative Statements over Procedural Recipes**: Specifications describe architectural capabilities, state invariants, and outcome mappings declaratively. Avoid procedural recipes that narrate step-by-step pseudo-code or chronological recipes (e.g., avoid *"First do X, then do Y, before Z do W, finally stop the session"*). Procedural narratives make requirements rigid, over-specified, and impossible to ground cleanly.
- **Plain Text for Everything Else (No Bolding)**: Never use `**` bolding in high-level specifications, except for qualifying prefixes such as `**Out of scope:**`. Eliminating bolding minimizes visual noise and token overhead.
- **Literate Prose in Paragraphs and Bullets**: Specifications should read as natural architectural prose rather than stilted pseudo-code. Bullets are fine as long as they are written as prose—often bullets make prose easier to realize and digest than an overly dense, monolithic paragraph.
- **Single-Level Bullet Paragraphs**: When bullets are used, each bullet point is an articulate, standalone prose paragraph separated by blank lines—never a fragmented keyword list, pseudo-code snippet, or nested sub-bullet.
- **Never End Complete Sentences with Colons**: Never end a grammatically complete sentence with a colon (`:`). Every complete sentence must terminate with a period (`.`).
- **Fragment + Colon Lead-In for Bullets**: When bullets are used, end the preceding sentence with a period, then provide a separate header as a sentence fragment followed by a colon (`:`). The subordinate bullets must grammatically complete the fragment lead-in:
  ```markdown
  The *read manager* is an agent session service that installs tools for inspecting workspace files:

  - A *read tool* that reads file content, taking a *file alias parameter*, and accepting *line numbers* to format content with line numbering. Executing the read tool distinguishes reading attempts on the guide file to provide *progressive delivery* feedback.

  - A *search tool* that searches pattern matches across the session's read-only and read-write files.
  ```
  ```markdown
  A *node* identifies a discrete unit of work in the graph. A *dag storage* is a system service that maintains node state, including its graph structure and change propagation. A node in a dag storage has:

  - *Dependencies* that refer to the node's upstream nodes in the graph...

  - *Dependents* that refer to downstream nodes depending on it...

  - *Messages* explaining why the node requires cleaning...
  ```

---

## 8. Specification Document Layout

### 8.1 Interface Component Layout (`<name>.md`)

```markdown
# <name> interface component

imports: <dependencies>   <!-- omitted if no dependencies -->

## Purpose

The <name> interface component <why-focused core reason for being>.

<1-2 paragraphs of architectural rationale motivating the component from a system perspective, without overlapping or replicating behavioral details.>

**Out of scope:** The <name> interface component does not <high-level workflow operations that describe client purpose rather than component requirements>; these are handled by other components.

## Types and Behavior

A *<data_type>* identifies <core description>. A *<root_object_type>* is a <system | agent session> service that <role and capabilities>. A <data_type> in a <root_object_type> has:

- *<Property_or_Type>* that <description and constraints>.

- *<Property_or_Type>* that <description>. An entity can be *<operation>* so that <rationale>.

- *<Property_or_Type>* indicating <state>. Entities can be *<operation>* and *<operation>*.
```

### 8.2 Implementation Component Layout (`<name>_impl.md`)

```markdown
# <name>_impl implementation component

imports: <dependencies>
implements: <types, tools, or services realized>

## Purpose

The <name>_impl implementation component <why-focused core reason for being>.

<1-2 paragraphs of architectural rationale motivating the concrete implementation choices and safety boundaries.>

**Out of scope:** The <name>_impl implementation component does not <high-level workflow operations>; these are handled by other components.

## Types and Behavior

<Declarative implementation behaviors, concrete tool naming, input validation preconditions, error guidance, and sanitized output formatting.>
```

### 8.3 Assembly Component Layout (`<name>_asm.md`)

```markdown
# <name>_asm assembly component

imports: <constituent implementation and interface dependencies>
implements: <closed interfaces provided to external callers>

## Purpose

The <name>_asm assembly component <why-focused core reason for being>.

<1-2 paragraphs of architectural rationale motivating the subsystem composition.>

**Out of scope:** The <name>_asm assembly component does not <high-level workflow operations>; these are handled by other components.

## Types and Behavior

The *<name> assembly* unites the concrete implementation components that realize <subsystem capability>. The assembly initializes its constituent implementation components and registers their singleton services with the system lifecycle prototype.

The <name> assembly aggregates the following implementation components:

- The <subsystem implementation> from <name>_impl, closing the <interface> interface to <capability>.
```

### 8.4 Canonical Examples

#### Interface Example: `dag_storage.md`

```markdown
# dag_storage interface component

## Purpose

The dag_storage interface component coordinates incremental workflow execution and inter-task diagnostic communication across multi-step agent runs.

Multi-step agent workflows require coordinated incremental execution to avoid redundant re-computation and prevent stale task outputs. As tasks evolve, dependent stages must understand why upstream changes necessitate re-execution, and downstream stages must communicate diagnostic issues back to their prerequisites. The dag_storage interface component provides a dedicated graph coordination boundary that isolates lifecycle tracking and inter-node communication state from the operational mechanics of individual task execution.

**Out of scope:** The dag_storage interface component does not dispatch change notifications, interpret message semantics, or execute node cleaning; these are handled by other components.

## Types and Behavior

A *node* identifies a discrete unit of work in the graph. A *dag storage* is a system service that maintains node state, including its graph structure and change propagation. A node in a dag storage has:

- *Dependencies* that refer to the node's upstream nodes in the graph. A dependency can be *silent* to indicate that the dependent node does not depend on the dependency's content and so does not need to receive change messages about the dependency.

- *Dependents* that refer to downstream nodes depending on it. A node can be *registered* as a dependent to all of its non-silent dependencies so that it can be notified when dependencies change. The dependents of a node can be *cleared* to avoid stale dependent relationships.

- *Messages* explaining why the node requires cleaning. A message can either indicate *change*, which informs of modifications made to upstream dependencies, or *feedback*, which informs of issues detected by downstream dependents. A node is *dirty*, meaning it needs to be cleaned, if, but not only if, it has messages. Messages can be *added* to a node, to inform on why it needs to be cleaned, as well as *cleared*, to inform that it no longer needs to be cleaned.
```

#### Implementation Example: `tool_provider_impl.md`

```markdown
# tool_provider_impl implementation component

imports: tool_provider
implements: tool provider

## Purpose

The tool_provider_impl implementation component realizes centralized tool discovery and parameter converter dispatch services for agent sessions.

Autonomous agent workflows require dynamic tool registration and structured argument resolution without coupling individual tools or callers to concrete lookup mechanics. Decentralized registry logic risks duplicate names, inconsistent missing-tool behaviors, and unhandled argument conversions across sessions. The tool_provider_impl implementation component establishes an in-memory session registry that indexes added tools by name and parameter converters by actual type, providing predictable lookup failures and reliable tool discovery for agent orchestration.

**Out of scope:** The tool_provider_impl implementation component does not execute tool actions, manage the agent turn loop, or parse model output streams; these are handled by other components.

## Types and Behavior

A tool provider maintains tools and parameter converters added during an agent session. Requesting a tool by name returns the matching tool if it was added, and produces an expected failure if no matching tool is found. Requesting a parameter converter by actual type returns the matching converter if it was added, and produces an expected failure if no converter was added for that actual type. A tool provider exposes the names of all currently added tools.
```


