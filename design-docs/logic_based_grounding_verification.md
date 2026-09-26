# Logic-Based Grounding Verification & Formal Specification

## 1. Executive Summary & Problem Statement

In the Cleanroom architecture, **Grounding** bridges literate High-Level Specifications (`high/*.md`) with structural Python interface stubs (`grounding/*.pyi`), which in turn guide the generation of executable library code (`lib/*.py`) and deterministic unit tests (`tests/*_test.py`).

Grounding is intended to guarantee that an implementation is **realizable** before any runtime code is authored:
- **Knowledge Custody**: Every input, configuration, and entity state has an unbroken derivation path from in-scope sources.
- **Operational Satisfiability**: All required capabilities and invariants can be achieved using accessible collaborator services and external primitives (`_ext`).
- **Absence of Floating Directives**: No component relies on ambient context, implicit global variables, or uncontracted behavior.

### 1.1 The Current Grounding Failure Mode
Today, structural AST rules (type annotations, decorators, MRO inheritance) are enforced deterministically by `grounding_tool.py`. However, semantic grounding itself—the proof that an operation can actually satisfy its requirements—relies on an unverified natural language block in implementation stubs:
```python
GROUNDING_ARGUMENT:
- Receives actual parameter bindings, resolves host paths using imported agent_file_alias.AliasManager workspace root in the same session lifecycle tier, resolves unbound .py and module requests...
```
Because `SpecLintVisitor` treats `GROUNDING_ARGUMENT:` as an opaque string, semantic grounding is an **unverifiable honor system**:
1. **LLM Hallucinations**: Models generate plausible-sounding narrative arguments that gloss over missing method arguments, inaccessible singleton collaborators, or unhandled branches.
2. **Delayed Error Discovery**: Grounding gaps are not detected at the specification stage. Instead, they manifest late during library code generation (`grounding_to_lib`) or unit testing, forcing emergency ad-hoc fixes or fabricated requirements.
3. **Premature Implementation Leaks**: Authors prematurely jump straight to concrete library APIs (e.g. hardcoding `tool_provider.ToolManager.install_tool(...)` into docstrings or requirements) instead of stating the high-level domain capability and letting grounding reason about how it is grounded.
4. **Lack of Falsifiability**: An agent or human cannot mechanically verify whether a proposed specification is sound without mentally executing the entire system.

### 1.2 Dual Objectives of Formal Grounding
Formalizing grounding is not merely a gatekeeping check. It serves two distinct generative and self-healing functions in the Cleanroom pipeline:
1. **Downstream Witness Generation (Code Generation Blueprint)**: When a grounding derivation is proven, the solver's proof tree serves as a concrete, step-by-step provenance guide for the AI agent generating library code (`lib/*_impl.py`), eliminating guesswork and hallucinated wiring.
2. **Upstream HLS Self-Healing (Specification Repair)**: When a grounding check fails due to an architectural mistake, omitted parameter, or missing collaborator in the High-Level Specification, the structured diagnostic (counterexample / unsatisfied derivation) is fed directly to an LLM to **repair the upstream HLS (`high/*.md`)**, automatically re-aligning the downstream pipeline.

---

## 2. Foundational Principles: Separating Grounding from Control Flow

### 2.1 The Two Orthogonal Functions in Grounding Stubs
Historically, `.pyi` grounding specifications have conflated two separate concerns:
1. **Presentation of Requirements**: A text-based organization of requirements under specific operations or types (`FRESH_REQUIREMENTS:`). This is an organizational convenience. It is orthogonal to semantic feasibility.
2. **Semantic Grounding Reasoning**: A formal proof establishing whether the requirements can be feasibly realized using accessible capabilities and state.

### 2.2 Eliminating Accidental Complexity
To make grounding mathematically verifiable, we discard two sources of accidental complexity:

1. **Control-Flow Conditions (`when`, `if/else`) are for Code Generation, NOT Grounding**:
   Grounding does not care whether a runtime branch evaluates to true or false. Grounding is strictly an **existential reachability problem**: can the component perform the required actions and observe the required information across all mandated behaviors? The runtime branching logic belongs strictly to library code generation (`grounding_to_lib`).
2. **Prohibitions (`prohibits`, "never do X") Do Not Require Grounding**:
   Doing nothing requires zero capability and zero state access. Prohibitions are safety invariants and unit test assertions, not grounding feasibility obligations.

### 2.3 The Reachable Scope Environment (a - e)
Every requirement has a scope to which it applies (an operation on an object type, or an invariant on an object type). For any given scope S, the accessible environment consists strictly of:
- **a. Parameters** of operation S (if an operation requirement).
- **b. Properties** of the enclosing object type (accessible via `self`).
- **c. Operations** accessible on the same type, or reachable by traversing properties or parameters.
- **d. Properties and operations** accessible via singleton objects visible from components imported into the local component, respecting lifecycle tier containment (child tiers can access ancestor tiers; ancestor tiers cannot access child tiers).
- **e. Assumptions and extension facts** in scope (`_ext`), which are taken as axioms.

### 2.4 Goal Extraction vs. Solver Inference

A core architectural principle of Cleanroom grounding is the strict separation between **Goal Extraction** (authoring specification obligations) and **Solver Inference** (proving reachability and synthesizing witnesses):

1. **Specification Extraction (Without Inference)**:
   - When extracting grounding requirements from High-Level Specifications (`high/*.md`), the author states **only direct domain obligations and explicit ambient observations**.
   - **No Manual Mental Execution**: Specification authors must never mentally execute the implementation or unroll internal assembly plumbing into docstrings (e.g. manually unrolling `action("read", BoundFile)` into `knows("workspace root")`, `knows("workspace path")`, and `filesystem_ext.read_text`).
   - **Compliance with HLS Rule 109**: High-level specifications must state capabilities and invariants declaratively around domain entities without micromanaging collaborator routing (e.g. stating "responses for read-only files mask host paths" rather than "sanitize host paths through the alias manager").

2. **Solver Inference (Reachability Proof & Witness Synthesis)**:
   - The automated reasoning engine (Datalog / Reachability solver) is responsible for determining *how* high-level domain actions reach concrete external boundary primitives (`_ext`) or collaborator methods.
   - The solver verifies that necessary context (e.g. `WorkspaceRoot` from `AliasManager`, `WorkspacePath` from `BoundFile`) is accessible in scope and proves the path to `filesystem_ext.read_text`.
   - The resulting proof tree forms the **derivation witness**, which guides downstream library code generation (`lib/*.py`) without hallucinated wiring.

3. **Interface Grounding Contracts and Compounding**:
   - Interface methods are abstract protocol stubs with ellipsis (`...`) bodies. They declare capability obligations and information guarantees that any conforming implementation must satisfy.
   - When an implementation accesses an interface type (via parameter `a`, property `b`, or imported singleton `d`), the interface's declared `GROUNDING_REQUIREMENTS:` compound into the implementation's accessible scope environment.

4. **Mandatory Numbered Requirements & Stable Citations**:
   - Requirements under `FRESH_REQUIREMENTS:` must be explicitly numbered (`1.`, `2.`, ...) to provide unambiguous, stable citation anchors for justifications under `GROUNDING_REQUIREMENTS:` and `GROUNDING_ASSUMPTIONS:`.

5. **Strongly Typed Domain Concepts**:
   - Grounding requires named types. Complex domain parameters and payloads must not degenerate into untyped generic primitives (`dict`, `Mapping[str, Any]`, `str`). Concepts passed across collaborators must be introduced as explicit named types (e.g. `@data_type class TemplateParameters(Mapping[str, Any]): ...`).

6. **Schema Properties Omit Grounding**:
   - Pure schema descriptors, constant identifiers, and parameter definitions (e.g. `name`, `description`, `path_parameter`) omit grounding blocks unless exercising an external capability.

7. **Elimination of Inherited Prose Duplication**:
   - Specifications using grounding contracts omit `INHERITED_REQUIREMENTS:` and `INHERITED_ASSUMPTIONS:`. Each type and operation declares its own fresh numbered requirements and justified grounding entries.

---

## 3. Deterministic Logic Reasoning: The Groundtalk Engine (Black Box)

Cleanroom outsources all relational logic specifications, subtyping subsumption, and reachability proofs to **Groundtalk**: a dedicated declarative logic language and forward-chaining engine.

> [!NOTE]
> For the complete formal syntax, Datalog Horn rules, subtyping proofs, hybrid evaluation algorithms, and engine implementation details of Groundtalk, see the companion specification:
> **[Groundtalk: Declarative Grounding Logic & Forward-Chaining Engine](file:///Users/seanmcdirmid/projects/cleanroom-grounding/design-docs/groundtalk.md)**.

From the perspective of the Cleanroom specification and compilation pipeline, the Groundtalk reasoner operates as a **deterministic black box** with a precise input/output boundary:

```
  ┌────────────────────────────────────────────────────────┐
  │                   INPUT TO GROUNDTALK                  │
  ├────────────────────────────────────────────────────────┤
  │ 1. Scoped Lexical Environment (a - e):                 │
  │    - Operation parameters (a)                          │
  │    - Object type properties of Self (b)                │
  │    - Reachable operations (c)                          │
  │    - Visible imported singletons & interfaces (d)      │
  │    - Hardware / OS boundary axioms (_ext) (e)          │
  │                                                        │
  │ 2. Groundtalk Specification Obligations:               │
  │    - GROUNDING_IMPLEMENTS: (Intrinsic capability axioms│
  │    - GROUNDING_PROVISIONS: (Exported guarantees)       │
  │    - GROUNDING_REQUIREMENTS: (Consumed dependencies)   │
  │                                                        │
  │ 3. Core Typed Predicates:                              │
  │    - action(verb, TargetType, [prep, AuxType])         │
  │    - knows(text_concept, pyi_type)                     │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │             GROUNDTALK ENGINE (BLACK BOX)              │
  │  - Goal-Directed Backward Relevance Pruner (Cone)      │
  │  - Scoped Semi-Naive Forward Chaining Closure          │
  │  - Subtyping & Polymorphic Subsumption                 │
  └───────────────────────────┬────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
  ┌────────────────────────┐      ┌────────────────────────┐
  │   GroundtalkSuccess    │      │   GroundtalkFailure    │
  │ - Complete Derivation  │      │ - Missing Goals (Diff) │
  │   Witness Tree         │      │ - Near-Miss Matches    │
  │   (Why-Provenance)     │      │ - Reachable Fact Pool  │
  └───────────┬────────────┘      └───────────┬────────────┘
              │                               │
              ▼                               ▼
  Downstream Code Gen              Neuro-Symbolic Gap
  (grounding_to_lib)               Inspector (LLM)
```

### 3.1 The Groundtalk Contract Boundary

1. **Extraction (AST to Groundtalk)**:
   [`grounding_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom-grounding/update_with_ai/support/lib/grounding_tool.py) parses the `.pyi` AST to extract scope entities, imports, and docstring grounding blocks, constructing the `ScopedEnvironment` and Groundtalk declarations.
2. **Execution**:
   The toolchain invokes `GroundtalkEngine.verify_scope(scope_id, env, implements, provisions, requirements)`.
3. **Outcomes**:
   - **On Success (`GroundtalkSuccess`)**: Returns the derivation witness tree (exact collaborator method calls, property paths, and parameter conversions) used directly as the execution blueprint for `lib/*.py` code generation.
   - **On Failure (`GroundtalkFailure`)**: Returns the unsatisfied goal difference ($\text{Gaps} = \text{Goals} - \text{Reachable}$) and partially satisfied candidate rules ("near-misses"), which are handed to the **Neuro-Symbolic Gap Inspector** for triage.

---

## 4. The Grounding Architecture & Specification Pipeline

```mermaid
flowchart TD
    subgraph Environment["Reachable Scope Environment (a - e)"]
        A["a. Operation Parameters"]
        B["b. Object Type Properties (self)"]
        C["c. Reachable Operations (self / params / props)"]
        D["d. Visible Singletons & Compounded Interfaces"]
        E["e. Boundary Primitives (_ext) & Assumptions"]
    end

    subgraph Queries["Atomic Grounding Queries"]
        Act["action(verb, TargetType, [prep, AuxType])<br/>Can S execute this capability?"]
        Know["knows(specifier, DataType)<br/>Can S access this ambient state?"]
    end

    Queries --> Reasoner["Logic Reasoner & Reachability Solver"]
    Environment --> Reasoner

    subgraph Outcomes["Grounding Proof"]
        Pass["Grounded -> Derivation Witness Blueprint"]
        Fail["Ungrounded -> Structured Diagnostic"]
    end

    Reasoner --> Pass
    Reasoner --> Fail
```

### 4.1 Interface Contracts & Compounding Example: `sandbox_file_reader.pyi`

Interface specifications declare numbered domain requirements alongside capability obligations with explicit justifications:

```python
@singleton_type('agent_session')
class ReadManager(Protocol):
    """
    PURPOSE:
    Defined as an agent session service that manages inspection of workspace files

    FRESH_REQUIREMENTS:
    1. The read manager is an agent session service that manages inspection of workspace files.
    2. The read manager exposes the session read-only files and read-write files.
    3. When step mode is active, the read manager is configured with an unbound guide file.

    GROUNDING_REQUIREMENTS:
      - action("install", tool_provider.Tool): Installs workspace file inspection tools into the session environment to satisfy requirement 1.
    """

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
        PURPOSE:
        Exposes the agent session's set of read-only files to support session startup context injection

        FRESH_REQUIREMENTS:
        1. Exposes the agent session read-only files.
        """
        ...
```

Notice that the property `read_only_files` simply declares its domain requirement and return type without ritual grounding blocks, while `ReadManager` justifies its `action("install", tool_provider.Tool)` directly against requirement 1.

### 4.2 Implementation Reachability Example: `sandbox_file_reader_impl.pyi`

Implementation specifications are the target of reachability verification:

#### `ReadManager.initialize`
```python
    @operation
    def initialize(self) -> None:
        """
        PURPOSE:
        Provides that initialization unconditionally installs the view file tool, installs the can read tool when mcp mode is active, and never installs the search tool

        FRESH_REQUIREMENTS:
        1. Provides that initialization unconditionally installs the view file tool, installs the can read tool when mcp mode is active, and never installs the search tool.

        GROUNDING_REQUIREMENTS:
          - action("install", tool_provider.Tool): Installs the view file tool and can read tool into the tool provider registry to satisfy requirement 1.
        """
        ...
```
Resolution:
1. `action("install", tool_provider.Tool)`: Resolved via imported singleton `tool_provider.ToolManager.install_tool(tool: Tool)`. Covariance satisfies installing both `ViewFileTool` and `CanReadTool`.

#### `ViewFileTool.execute_tool`
```python
    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
        PURPOSE:
        Implements execute_tool on the view file tool to read file content with line number formatting and alias validation

        FRESH_REQUIREMENTS:
        1. Records the read file on successful execution.
        2. Reads file content of the bound file from the filesystem, returning the content formatted with one-indexed right-aligned line numbers followed by a colon and space, and formatting read-only markdown files ending with .md with session template parameters after filtering out paragraphs beginning with > META:.
        3. Treats a read-write file as having empty content when the target file does not exist on disk, and fails with a response guiding agent recovery when reading a missing read-only file.
        4. Fails with a response guiding agent recovery, reminding the agent that only declared files can be read, listing available readable file aliases, when an unbound file is supplied.
        5. View file tool responses for read-write files carry a suppression key matching the file's relative path, while responses for read-only files omit suppression keys and mask host paths.

        GROUNDING_IMPLEMENTS:
          - action("call", Self): Implements tool execution for the view file tool.

        GROUNDING_REQUIREMENTS:
          - action("record", agent_file_alias.FileAlias): Records file read as required by requirement 1.
          - action("read", agent_file_alias.FileAlias): Reads file content from the filesystem as required by requirement 2.
          - action("format", str, "with", template_format.TemplateParameters): Formats markdown templates with session template parameters as required by requirement 2.
          - action("sanitize", str): Masks host paths in output responses as required by requirement 5.
        """
        ...
```

Notice the stark contrast with old, procedural grounding annotations:
- **No manual unrolling**: The author never writes `knows("workspace root")` or `knows("workspace path")`. The author states the domain goal: `action("read", agent_file_alias.BoundFile)`.
- **Automatic Solver Inference**: The solver automatically unifies `action("read", BoundFile)` with `filesystem_ext.read_text(path: HostPath)` by finding `BoundFile.workspace_path` on the input entity and `AliasManager.workspace_root` on the visible session singleton, resolving them via `file_paths.resolve_path`.
- **Derivation Witness**: The solver synthesizes the complete witness blueprint for library generation:
  ```
  host_path = file_paths.resolve_path(AliasManager.workspace_root, target_file.workspace_path)
  content = filesystem_ext.read_text(host_path)
  ```

---

## 5. The Bidirectional Neuro-Symbolic Workflow & Gap Bridging

```mermaid
flowchart TD
    HLS["1. High-Level Specification (HLS)<br/>high/<name>.md<br/>(Declarative requirements without collaborator routing)"]
    Grounding["2. Grounding Stubs<br/>grounding/<name>.pyi<br/>(Declares typed action and knows goals)"]
    
    HLS --> Grounding
    
    subgraph Verifier["3. Logic & Grounding Verifier"]
        ScopeCheck["Datalog Scope & Tier Check"]
        Reachability["Reachability & Witness Solver (a - e)"]
        ScopeCheck --> Reachability
    end
    
    Grounding --> Verifier
    
    subgraph Outcome["Proof Evaluation"]
        direction TB
        Pass["Proof Succeeded (All Goals Reached)"]
        Unsatisfied["Unproven Goals at Fixpoint"]
    end
    
    Reachability --> Pass
    Reachability --> Unsatisfied
    
    Pass --> Witness["4. Derivation Witness Extracted<br/>(Exact collaborator methods and property paths)"]
    Witness --> LibGen["5. Library Implementation<br/>lib/<name>.py<br/>(Weaves witnesses into runtime control flow)"]
    
    subgraph NeuroSymbolicBridge["6. Neuro-Symbolic Gap Inspector (LLM)"]
        Triage{"Gap Triage"}
        Synonym["Tier 1: Semantic Synonym / Aliasing<br/>alias(C1, C2) or Vocabulary Patch"]
        BridgeRule["Tier 2: Derivation Bridge Rules<br/>Synthesizes missing projection/chaining clause"]
        HardDefect["Tier 3: Structural Defect<br/>Generates Structured Diagnostic"]
    end
    
    Unsatisfied --> Triage
    Triage -- "Synonym Match" --> Synonym
    Triage -- "Derivation Gap" --> BridgeRule
    Triage -- "True Omission" --> HardDefect
    
    Synonym --> ReVerify["Re-feed Solver with Bridge"]
    BridgeRule --> ReVerify
    ReVerify --> Reachability
    
    HardDefect --> FaultRouter{"Fault Attribution"}
    FaultRouter -- "Local Defect" --> HLSRepair["7a. Local HLS Repair<br/>Patches high/<name>.md"]
    FaultRouter -- "Collaborator Defect" --> UpstreamRepair["7b. Upstream Escalation<br/>Patches high/<collaborator>.md"]
    HLSRepair --> HLS
    UpstreamRepair --> HLS
```

### 5.1 Downstream Witness Generation (Code Generation Blueprint)
When the grounding verifier succeeds, it outputs the **derivation witness**—the structured proof tree showing exactly which collaborator method produces each capability and which property path yields each value.

This witness is included directly in the prompt given to the AI agent authoring the library code (`update_python_with_ai/guides/grounding_to_lib.md`). The code generator takes the verified witnesses and weaves them into the required `if/else` control flow branches, eliminating hallucinations and guess-and-check API discovery.

### 5.2 The Intermediate Neuro-Symbolic Gap Bridging Engine

In practice, a purely symbolic solver fails whenever two independently authored specifications use slight vocabulary variations for the same domain concept (e.g. `template_parameters` vs. `template_bindings`) or when a capability requires a short chain of pure projections. 

Rather than treating solver reachability as a binary pass/fail cliff, Cleanroom introduces an **Intermediate Neuro-Symbolic Gap Inspector**. When the symbolic solver reaches a fixed point with unproven goals, it packages the unsatisfied goals, the available scope environment $(a - e)$, and the cited requirement prose, submitting them to an LLM evaluator.

The LLM triages the gap across three progressive tiers:

#### Tier 1: Semantic Synonym & Concept Aliasing
When the consumer and provider express the same concept using different terminology (e.g., consumer requires `knows("template_parameters", TemplateParameters)` while `NodeConfig` provides `knows("template_bindings", TemplateParameters)`):
1. The LLM recognizes that both terms refer to the identical domain concept.
2. The engine emits a symmetric alias fact into the Datalog knowledge base:
   ```datalog
   alias(template_parameters, template_bindings).
   ```
   Supported by the Datalog concept unification rule:
   ```datalog
   knows(C1, Type) :- knows(C2, Type), alias(C1, C2).
   ```
3. The solver re-evaluates the query. If the alias satisfies the proof, the system records the bridge and queues an upstream vocabulary alignment recommendation to standardize the HLS prose.

#### Tier 2: Derivation Bridge Rule Synthesis
When an action goal requires bridging a domain entity to an external primitive through accessible helper methods or properties:
- Example: Goal is `action("read", BoundFile)`.
- Accessible scope contains `knows("agent_session", WorkspaceRoot)` on `AliasManager`, `action("read_text", HostPath)` on imported `filesystem_ext`, and parameter `target_file: BoundFile` which exposes `workspace_path: WorkspacePath`.
- The LLM synthesizes the missing domain bridge rule:
  ```datalog
  action("read", BoundFile) :- 
      knows("agent_session", WorkspaceRoot),
      has_property(BoundFile, workspace_path, WorkspacePath),
      action("resolve_path", WorkspaceRoot, "to", HostPath),
      action("read_text", HostPath).
  ```
- The solver ingests this rule as a hypothesis. If the premises are indeed satisfied in the scoped environment, the proof succeeds and the synthesized derivation rule is incorporated directly into the code generation witness.

#### Tier 3: Upstream HLS Self-Healing & Fault Attribution
If the LLM determines that the goal cannot be bridged (e.g., an operation in `system` tier attempts to access `agent_session` state without passing a parameter, or a required external capability is completely missing from imports), the gap is classified as a genuine architectural defect.

The engine generates an actionable, machine-readable diagnostic:
```json
{
  "error": "UNGROUNDED_ACTION",
  "component": "sandbox_file_reader_impl",
  "operation": "execute_tool",
  "missing_capability": "action('read', 'file')",
  "required_by": "Tool execution reads file content from the filesystem...",
  "reason": "Component 'sandbox_file_reader_impl' does not import 'filesystem_ext'."
}
```
Or for missing knowledge:
```json
{
  "error": "FLOATING_DIRECTIVE",
  "component": "runner_logger_impl",
  "operation": "log_turn",
  "missing_knowledge": "knows('session id')",
  "required_by": "The runner logger records the session identifier...",
  "reason": "RunnerLogger is a 'system' service and cannot access 'agent_session' context without an explicit operation parameter."
}
```

The fault router attributes the defect:
- **Local Defect**: The local specification omitted an import, dropped a parameter, or violated tier custody. Repaired in local HLS.
- **Collaborator Defect**: The collaborator legitimately needs to expose a capability or state, but its interface omits it. Escalated upstream to collaborator HLS and interface.

---

## 6. Practical Implementation Roadmap

### Phase 1: Datalog Scope & Import Verifier (Complete)
- Extract relational facts from `.pyi` AST: `service`, `tier`, `imports`, `operation`.
- Enforce strict tier containment (`system` >= `agent_session`) and imports completeness.

### Phase 2: Atomic Grounding Queries & Interface Compounding (Complete)
- Introduce atomic `action("verb", "object")` and `knows("<concept/value>")` queries.
- Support `GROUNDING:` and `GROUNDING_ASSUMPTIONS:` across both interface (`<name>.pyi`) and implementation (`*_impl.pyi`) specifications.
- Compound interface guarantees into the accessible scope environment for implementing and consuming components.
- Implement the reachability solver in `grounding_tool.py` to verify that every query in scope S unifies with a provider in the scope environment (a - e).
- Transitive dependency resolution: auto-index repository specifications and transitively resolve imports.
- Output derivation witnesses for downstream code generation.

### Phase 3: Automated Upstream HLS Repair Loop
- When an atomic query fails reachability, generate structured diagnostic JSON.
- Implement automated prompt feeding the diagnostic to an LLM to patch the upstream HLS (`high/<name>.md`).

---

## 7. Conclusion

By separating orthogonal requirement presentation from semantic feasibility, discarding runtime control-flow distractions, and focusing on atomic `action(...)` and `knows(...)` reachability queries:
- **The authoring burden is minimal**: The LLM transcribes atomic capability and knowledge phrases directly from HLS prose.
- **No premature API leaks**: Authors never hardcode collaborator method calls or internal storage mechanisms into docstrings.
- **The logic reasoner does the heavy lifting**: The engine deterministically solves reachability across the scope environment (a - e) and generates the execution blueprint for code generation.
