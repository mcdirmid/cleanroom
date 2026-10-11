# Specification Grounding, External Boundaries, and Assembly Pipeline Architecture

This document establishes the architecture, validation constraints, and phased implementation roadmap for four interrelated specification and pipeline enhancements in Cleanroom:
1. **Low-Level Specification File Name Grounding via External Boundaries (`_ext`)**: Prohibiting floating or hardcoded filenames, paths, and schemas in low-level specifications (`low/*.pyi`), requiring them to be grounded via imported external boundary components (`<name>_ext`).
2. **Swatting Legacy `MODULE.bazel` References**: Eliminating remaining Bazel workspace markers and dependencies across High-Level Specifications, planning canvases, and low-level stubs in favor of native UV and Python repository conventions.
3. **Streamlined Assembly Component (`_asm`) Pipeline**: Treating assembly components like external boundary components by eliminating superfluous planning canvases and scenario files, allowing low-level stubs (`low/<name>_asm.pyi`) to mechanically mirror assembly instructions directly from the High-Level Specification (`high/<name>_asm.md`).
4. **Implementation Component (`_impl`) Import Accountability & Spec QA Attribution**: Enforcing complete usage of all declared imports in implementation components, requiring unexposed collaborators to be cited in natural language `GROUNDING:` arguments, and establishing Spec QA defect triage when imports are unaccounted for.

> [!NOTE]
> **Planning & Design Document (`_todo.md`)**
> This document specifies architectural rules, validator designs, guide amendments, and work items. No code or specification changes are implemented in this document.

---

## 1. Executive Summary & Core Motivations

Cleanroom coordinates software development through an epistemic pipeline of decoupled roles:
$$\text{High-Level Spec (HLS)} \longrightarrow \text{Planning Canvas} \longrightarrow \text{Low-Level Stubs (low)} \longrightarrow \text{Spec QA} \longrightarrow \text{Library (lib)} \longleftrightarrow \text{Tests (tests)}$$

To maintain total semantic integrity across this pipeline, every contract, type, dependency, and environmental interaction must be strictly grounded:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               PIPELINE GROUNDING REFINEMENTS                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  1. ENVIRONMENT GROUNDING VIA _ext                                                     │
│     [low/*.pyi] ──(Forbidden: Hardcoded paths/filenames)                              │
│          ▲                                                                             │
│          └── MUST import ── [low/*_ext.pyi] ── Exposes canonical files & schemas       │
│                                                                                        │
│  2. SWATTING LEGACY MARKERS                                                            │
│     [high/*.md, low/*.pyi] ── Swat 'MODULE.bazel' ── Replace with pyproject/cleanroom  │
│                                                                                        │
│  3. STREAMLINED ASSEMBLY PIPELINE (_asm)                                               │
│     [high/*_asm.md] ──────(Bypass planning & scenarios)──────► [low/*_asm.pyi]         │
│                                (Mechanical repetition of assembles:)                   │
│                                                                                        │
│  4. IMPLEMENTATION IMPORT ACCOUNTABILITY (_impl)                                       │
│     [high/*_impl.md] (imports: X)                                                      │
│            │                                                                           │
│            ▼                                                                           │
│     [low/*_impl.pyi] ── MUST use X in AST  OR  MUST cite X in GROUNDING: docstring     │
│            │                                                                           │
│            ▼ (Unaccounted import?)                                                     │
│     [spec_qa] ──► Triage: Blame HLS (remove dead import) OR Blame Planning (enrich)   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Incoherencies in the Current Pipeline

1. **Floating File Name Literals**:
   Low-level specifications (`low/*.pyi` and `low/*_impl.pyi`) frequently declare concrete host filenames and state persistence markers in `POSTCONDITIONS:` or `GROUNDING:` without any provenance (e.g. `".cleanroom_workspaces.json"`, `".cleanroom_pending_work.json"`, `".cleanroom_blame_buffer.json"`, `"cleanroom.toml"`, `"AGENTS.md"`, and `"MODULE.bazel"` in [`workspace_registry.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_registry.pyi), [`workspace_work.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_work.pyi), and [`workspace_provision.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_provision.pyi)). Hardcoding arbitrary file names in low-level specifications violates Cleanroom's epistemic derivation rules: a stub should not invent filesystem artifacts that were never declared in its imported dependencies.
2. **Lingering Bazel Artifacts**:
   Despite Cleanroom's architectural migration to native Python and UV toolchains ([`packaging_and_distribution_architecture.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/packaging_and_distribution_architecture.md)), references to `MODULE.bazel` and `bazel_manifest_ext` persist in High-Level Specifications ([`workspace_registry_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/workspace_registry_impl.md)) and downstream stubs. These outdated markers confuse autonomous agents and create split repository root heuristics.
3. **Redundant Ceremony for Assembly Components (`_asm`)**:
   Assembly components ([`loop_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_asm.md), [`control_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_asm.md)) are purely mechanical aggregations that bind constituent implementation singletons into the `LifecycleRegistry`. Forcing `_asm` components through the full planning canvas (`planning/*_asm.md`) and scenario evaluation produces empty ritual: planning canvases contain single trivial contracts, scenarios are either absent or meaningless, and agents waste turn cycles generating placeholder text.
4. **Unchecked Implementation Imports & Missing Grounding Attributions**:
   While interface specifications (`high/<name>.md`) strictly forbid unused imports (enforced by `high_lint.py` Check 5b and `spec_qa.md`), implementation specifications (`high/<name>_impl.md`) have lacked rigorous import usage auditing. Because implementations consume collaborators internally rather than exposing them in public signatures, unused imports in `_impl.md` could slip through undetected, or conversely, required imports could be present without any explanation in `low/<name>_impl.pyi` of how they ground the implementation.

---

## 2. Low-Level Specification File Name Grounding via `_ext` Boundary Components

### 2.1 The Anti-Pattern: Floating File Names in Low Stubs

Low-level specifications (`low/*.pyi`) are formal structural contracts. When a low-level specification declares:
```python
# ANTI-PATTERN: Hardcoded file literals in low/workspace_work.pyi
@operation
def clear_pending_work(self) -> None:
    """Clears pending work targets.

    POSTCONDITIONS:
    - MUST delete .cleanroom_pending_work.json from workspace directory.
    """
    ...
```
The file literal `".cleanroom_pending_work.json"` appears *ex nihilo*. The interface assumes specific disk serialization conventions without declaring where that knowledge originated. If the state serialization format, file location, or naming scheme changes, the contract is broken, yet no dependency links the component to the filesystem specification.

Similarly, in [`workspace_registry.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_registry.pyi):
```python
# ANTI-PATTERN: Hardcoded configuration and marker filenames
@operation
def discover_repository_root(self, start_dir: str) -> str:
    """Discovers canonical root.

    POSTCONDITIONS:
    - MUST locate ancestor containing MODULE.bazel or .git marker.
    """
    ...
```

### 2.2 Architectural Principle: External Boundary Encapsulation (`_ext`)

In Cleanroom, knowledge concerning external file formats, OS filesystem protocols, host markers, or serialization conventions **must belong to external boundary components (`<name>_ext`)**:
- An external component's low-level specification (`low/<name>_ext.pyi`) documents foreign schemas, file names, environment variables, and usage snippets in its module docstring.
- When an internal component interacts with specific files or schemas on disk, it **MUST import the corresponding `_ext` component**.
- Low-level specifications (`low/*.pyi` and `low/*_impl.pyi`) must only reference file names, path patterns, or markers that are explicitly defined and exposed by an imported `_ext` dependency.

### 2.3 Proposed External Boundary Structure for Workspace Conventions

To ground the workspace subsystem's file interactions, we introduce or consolidate external boundary components:

1. **`workspace_state_ext`** (or extension of [`src_metadata_ext`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/low/src_metadata_ext.pyi)):
   - Documents the filenames and schemas for Cleanroom state files:
     - Active workspace tracking: `.cleanroom_workspaces.json`
     - Pending work tracking: `.cleanroom_pending_work.json`
     - Feedback blame buffering: `.cleanroom_blame_buffer.json`
     - Role configuration descriptor: `.cleanroom_role.json`
   - Exposes path constants or schema models for dependent components.
2. **`uv_manifest_ext`** / **`project_manifest_ext`**:
   - Documents methodology and project configuration files:
     - Methodology binding: `cleanroom.toml`
     - Role definitions: `cleanroom_roles.toml`
     - Package manifests: `pyproject.toml`
   - Documents canonical root marker conventions (`.git`, `cleanroom_roles.toml`, `pyproject.toml`).

### 2.4 Specification Derivation Example

With external boundary grounding, the contracts become epistemically traceable:

```python
# CORRECT ARCHITECTURE: Grounded file references in low/workspace_work.pyi
import workspace_state_ext

@singleton_type("agent_session")
class WorkspaceWork(InTier[AgentSessionTier], Protocol):
    """Manages session work queues using workspace state persistence.
    
    INVARIANTS:
    - MUST serialize pending targets conforming to workspace_state_ext schema.
    """

    @operation
    def clear_pending_work(self) -> None:
        """Clears pending work targets.

        POSTCONDITIONS:
        - MUST delete pending work file designated by workspace_state_ext from workspace directory.
        """
        ...
```

And in the implementation stub [`low/workspace_work_impl.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_work_impl.pyi):
```python
import workspace_work
import workspace_state_ext
import filesystem_ext

@singleton_type("agent_session")
class WorkspaceWork(workspace_work.WorkspaceWork, InTier[AgentSessionTier]):
    """Implementation managing session work queues.

    GROUNDING:
    - Reads and writes pending targets JSON using workspace_state_ext pending work
      filename and schema, invoking Path.read_text and Path.write_text from filesystem_ext.
    """
    ...
```

---

## 3. Todo Item: Swatting Legacy `MODULE.bazel` References

Cleanroom has completely eliminated Bazel from its runtime, dependency resolution, testing, and workspace execution. However, stale references to `MODULE.bazel` remain as historical residue.

### 3.1 Inventory of Legacy `MODULE.bazel` Residue

| File Path | Location / Line | Nature of Reference | Action Required |
|:---|:---|:---|:---|
| [`update_with_ai/parts/workspace/high/workspace_registry_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/workspace_registry_impl.md) | Line 10, 23 | Imports `bazel_manifest_ext`; mentions "canonical Bazel workspace indicators" | Replace import with `uv_manifest_ext` / `workspace_state_ext`; replace prose with canonical root markers |
| [`update_with_ai/parts/workspace/planning/workspace_registry_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/planning/workspace_registry_impl.md) | Line 19 | `searches ancestor directories for MODULE.bazel or .git markers [search_ancestor_markers]` | Update contract to reference `.git` or `pyproject.toml` / `cleanroom_roles.toml` |
| [`update_with_ai/parts/workspace/low/workspace_registry.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_registry.pyi) | Line 105 | `- MUST locate ancestor containing MODULE.bazel or .git marker.` | Update postcondition to reference markers from `uv_manifest_ext` |
| [`update_with_ai/parts/workspace/low/workspace_registry_impl.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_registry_impl.pyi) | Line 39 | `- Traverses upward from start_dir checking for MODULE.bazel or .git files` | Update `GROUNDING:` docstring to reference `uv_manifest_ext` markers |
| [`update_with_ai/parts/workspace/lib/workspace_registry.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/lib/workspace_registry.py) | Lines 446–509 | Hardcoded checks for `MODULE.bazel` in root traversal | Update implementation to check `cleanroom_roles.toml`, `pyproject.toml`, or `.git` |
| [`update_with_ai/parts/workspace/tests/workspace_provision_impl_test.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/tests/workspace_provision_impl_test.py) | Lines 76, 116 | Creating dummy `MODULE.bazel` file in tests | Replace dummy marker with `pyproject.toml` |
| [`update_with_ai/parts/workspace/tests/workspace_sync_impl_test.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/tests/workspace_sync_impl_test.py) | Lines 138, 153 | Creating dummy `MODULE.bazel` file in tests | Replace dummy marker with `pyproject.toml` |
| [`update_python_with_ai/support/lib/build_lint_common.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/support/lib/build_lint_common.py) | Lines 297–303, 2129 | Heuristic searching for `MODULE.bazel` | Remove `MODULE.bazel`; rely exclusively on `cleanroom_roles.toml`, `pyproject.toml`, and `.git` |
| [`update_python_with_ai/support/lib/cleanroom_role_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/support/lib/cleanroom_role_tool.py) | Line 39 | Checking `os.path.isfile(os.path.join(curr, "MODULE.bazel"))` | Remove `MODULE.bazel` check |
| [`update_python_with_ai/support/lib/test_lint.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/support/lib/test_lint.py) | Line 337 | Checking `MODULE.bazel` in repo root marker tuple | Remove `MODULE.bazel` check |

### 3.2 Todo Item Scope & Constraints
- **Deferred Execution**: As requested, swatting these references is documented as an explicit work item to be executed in a dedicated refactoring turn.
- **Cascade Rule**: When this item is addressed, it must follow the Mandatory Specification-First rule: update `workspace_registry.md` and `workspace_registry_impl.md` first, then cascade down through planning, low, lib, and tests in `parts/workspace`.

---

## 4. Streamlined Assembly Component (`_asm`) Pipeline

### 4.1 Problem: Ritual Overhead for Mechanical Code

Assembly components (such as [`loop_asm`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_asm.md) and [`control_asm`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_asm.md)) serve a single, fixed purpose:
1. They aggregate concrete implementation singletons across a subsystem.
2. They define `__initialize__(registry: Optional[LifecycleRegistry] = None)` to register those singletons into the shared lifecycle environment.

Currently, the pipeline treats `_asm` like a standard component, requiring:
- `high/<name>_asm.md`
- `planning/<name>_asm.md` (which merely restates "Assembles loop service implementations... [assemble_loop_services]")
- `scenarios/<name>_asm.md` (unusable or artificial)
- `low/<name>_asm.pyi`
- `spec_qa` audit of planning vs high vs low
- `lib/<name>_asm.py`

This ceremony adds zero semantic value. There are no algorithmic trade-offs, state machines, error branches, or domain behaviors to plan or test with scenarios.

### 4.2 Architectural Proposal: Treat `_asm` Like `_ext`

We propose treating `_asm` components symmetrically to `_ext` components:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        STREAMLINED ASSEMBLY COMPONENT LIFECYCLE                        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   High-Level Specification: high/<name>_asm.md                                         │
│   • Declares 'assembles: comp1_impl, comp2_impl, ...'                                  │
│   • Declares 'implements: iface1, iface2, ...'                                         │
│   • Literary description of subsystem aggregation                                      │
│                                                                                        │
│                              │                                                         │
│                              │  NO PLANNING CANVAS (planning/*_asm.md omitted)         │
│                              │  NO SCENARIO DOCUMENT (scenarios/*_asm.md omitted)      │
│                              ▼                                                         │
│                                                                                        │
│   Low-Level Specification: low/<name>_asm.pyi                                          │
│   • Repeats assembly instructions directly from HLS                                    │
│   • Top-level 'def __initialize__() -> None:' with docstring                           │
│   • CONSTITUENTS: list mirroring HLS 'assembles:'                                      │
│                                                                                        │
│                              │                                                         │
│                              ▼                                                         │
│                                                                                        │
│   Library Implementation: lib/<name>_asm.py (100% Mechanical)                          │
│   • Imports constituent modules                                                        │
│   • Defines CONSTITUENTS tuple                                                         │
│   • Iterates and calls mod.__initialize__(registry)                                    │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Detailed Operational Mechanics for `_asm`

1. **No Planning Canvas (`planning/<name>_asm.md`)**:
   - `planning` role configuration in [`cleanroom_roles.toml`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/cleanroom_roles.toml) removes `"assembly"` from `active_component_types`.
   - `spec_lint.py` is never run on assembly components.
   - Any legacy `planning/*_asm.md` files are safely retired.
2. **No Scenario Document (`scenarios/<name>_asm.md`)**:
   - The `scenario` role already omits `"assembly"` from `active_component_types`. This constraint is preserved.
3. **Low-Level Specification (`low/<name>_asm.pyi`)**:
   - Directly authored or generated from `high/<name>_asm.md`.
   - Contains strictly:
     - Module docstring describing the subsystem assembly (derived from HLS Purpose).
     - Optional imports.
     - Single function:
       ```python
       def __initialize__() -> None:
           """Aggregates constituent implementations into the subsystem assembly.

           CONSTITUENTS:
           - <constituent_1_impl>
           - <constituent_2_impl>
           """
           ...
       ```
   - Contract rule: Every item listed in HLS front-matter `assembles:` must appear under `CONSTITUENTS:`, and vice-versa (1:1 parity).
4. **Mechanical Implementation (`lib/<name>_asm.py`)**:
   - Fully scaffoldable via `lib_lint.py --scaffold` or generated directly by copying the constituent tuple and looping `mod.__initialize__(registry)`.
5. **Spec QA Verification of `_asm`**:
   - Spec QA verifies `_asm` directly as a 2-point alignment: `high/<name>_asm.md` $\longleftrightarrow$ `low/<name>_asm.pyi`.
   - Checks that:
     1. All modules in HLS `assembles:` match `CONSTITUENTS:` in low stub.
     2. All interfaces in HLS `implements:` are implemented by at least one constituent.
     3. No extraneous classes or executable operations exist in `low/<name>_asm.pyi`.

---

## 5. Implementation Component (`_impl`) Import Accountability & Spec QA Attribution

### 5.1 The Interface vs. Implementation Distinction

In Cleanroom, dependency management differs fundamentally between interfaces and implementations:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        IMPORT ACCOUNTABILITY: INTERFACE VS IMPL                        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   INTERFACE COMPONENTS (<name>.pyi):                                                   │
│   • Decoupled, abstract protocols.                                                     │
│   • FORBIDDEN from naming collaborators in docstrings or contracts.                    │
│   • Every import MUST appear as a type in public AST signatures.                       │
│   • Any import not appearing in the AST is dead code -> BLAME HLS.                     │
│                                                                                        │
│   IMPLEMENTATION COMPONENTS (<name>_impl.pyi):                                         │
│   • Concrete realizing agents.                                                         │
│   • Public AST signatures inherit from interface protocol (may not mention helper).   │
│   • Private collaborators are invoked internally in member bodies.                     │
│   • Grounding argument rule: Every declared import MUST be cited in GROUNDING:         │
│     docstrings, or appear in the AST!                                                  │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 The Problem: Ghost Imports and Unused Declarations in `_impl`

Historically, `high_lint.py` Check 5b exempted `_impl` components:
```python
# In high_lint.py:
if not is_impl and not is_asm and not is_ext and imports_list:
    ...
```
Because of this exemption:
1. An author of `high/<name>_impl.md` could declare `imports: foo, bar, baz`.
2. `low/<name>_impl.pyi` might import `foo`, but completely ignore `bar` and `baz`.
3. Neither `high_lint.py`, `low_lint.py`, nor `spec_qa` would detect that `bar` and `baz` were completely unused or forgotten!
4. Alternatively, an author might import `bar` to fulfill a subtle runtime requirement, but fail to explain why in `GROUNDING:`, leaving the library implementer (`lib/<name>_impl.py`) guessing what `bar` was imported for.

### 5.3 The Grounding Argument Mandate for `_impl` Components

To close this gap, Cleanroom establishes the **Implementation Import Grounding Mandate**:

> **Rule: Implementation Import Usage & Grounding Accountability**
> In any implementation component (`_impl`), every module declared in front-matter `imports:` of `high/<name>_impl.md` MUST be accounted for in `low/<name>_impl.pyi`.
> An imported component $C$ is accounted for if and only if:
> 1. $C$ appears in the Python AST of `low/<name>_impl.pyi` (as a type annotation, base class, or decorator argument), **OR**
> 2. $C$ is explicitly cited by name in at least one `GROUNDING:` docstring section in `low/<name>_impl.pyi`.

#### Grounding Argument Citation Standards
Under [`planning_to_low.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/guides/planning_to_low.md) and [`low_level_spec_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/low_level_spec_format.md), `GROUNDING:` sections are the formal architectural blueprint for `lib/`. When an import is not part of the public AST signatures, the `GROUNDING:` section on the class or operation that uses it **must explicitly explain its role**:

```python
# CORRECT GROUNDING ARGUMENT CITING COLLABORATOR IMPORT
@operation
@override
def synchronize_workspaces(self, dir_scope: str) -> bool:
    """Synchronizes active role workspaces with main repository.

    GROUNDING:
    - Grounded via WorkspaceRegistry.get_active_workspaces from workspace_registry
      to resolve target workspaces, PathDiff.compute_sync_manifest from workspace_sync,
      and atomic file copying via filesystem_ext.
    """
    ...
```
Here, `workspace_registry`, `workspace_sync`, and `filesystem_ext` are all accounted for via explicit mention in `GROUNDING:`.

### 5.4 Spec QA Defect Triage & Blame Attribution

When automated checks (`high_lint.py`, `low_lint.py`) or semantic audits in `spec_qa` discover an imported module $C$ declared in `high/<name>_impl.md` that is **neither used in the AST nor cited in any `GROUNDING:` section** of `low/<name>_impl.pyi`, the Spec QA arbiter must attribute blame using the following triage logic:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        SPEC QA TRIAGE FOR UNACCOUNTED IMPORTS                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Spec QA detects: Module 'C' is declared in high/<name>_impl.md imports:              │
│   but neither referenced in AST nor cited in any GROUNDING: of low/<name>_impl.pyi     │
│                                                                                        │
│                                          │                                             │
│                     Is 'C' actually needed to fulfill any                              │
│                    behavioral obligation or capability from                            │
│                             high/<name>_impl.md?                                       │
│                                          │                                             │
│                         ┌────────────────┴────────────────┐                            │
│                         │ NO                              │ YES                        │
│                         ▼                                 ▼                            │
│                 BLAME HIGH SPEC                   BLAME PLANNING / LOW                 │
│              (high/<name>_impl.md)               (planning/<name>_impl.md              │
│                                                   or low/<name>_impl.pyi)              │
│                                                                                        │
│   Rationale:                              Rationale:                                   │
│   The import is superfluous dead         The collaborator is genuinely needed,         │
│   dependency residue. The HLS must       but the planning canvas failed to ground      │
│   remove 'C' from its front-matter        the requirement, or the low stub omitted      │
│   imports: list.                         the collaborator citation from GROUNDING:.    │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Detailed Blame Decision Criteria:
1. **Blame High (`high/<name>_impl.md`)**:
   - The arbiter reviews the high-level specification's Purpose, Delegated sections, and behavioral requirements.
   - If no requirement in the HLS relies on the capabilities exported by $C$, the import is superfluous.
   - **Blame feedback**: `"high/<name>_impl.md:line: error: implementation specification imports 'C', but 'C' is never utilized in types or behavioral realization; remove 'C' from front-matter imports"`
2. **Blame Planning (`planning/<name>_impl.md`)**:
   - If the capability provided by $C$ is necessary to fulfill an inherited deferred requirement, but `planning/<name>_impl.md` failed to cite $C$'s knowledge provision slugs under `### Inherited Deferred Requirements` or `### Knowledge Requirements`.
   - **Blame feedback**: `"planning/<name>_impl.md:line: error: component requires collaborator 'C' to fulfill deferred requirement [req_slug], but fails to cite knowledge provisions from 'C' in grounding derivation"`
3. **Blame Low (`low/<name>_impl.pyi`)**:
   - If planning correctly grounded the requirement on $C$, but `low/<name>_impl.pyi` failed to synthesize that grounding into its docstrings.
   - **Blame feedback**: `"low/<name>_impl.pyi:line: error: imported collaborator 'C' from high-level specification is not referenced in the stub AST or cited in any GROUNDING: argument; add grounding argument explaining collaborator usage or remove import"`

---

## 6. Phased Implementation Roadmap & Todo Checklist

The following work items capture the concrete development tasks required to realize this design doc:

### Phase 1: Tooling & Linters (`update_python_with_ai/support/lib/`)
- [ ] **Linter Support for Implementation Import Accountability (`high_lint.py`)**:
  - Update `high_lint.py` Check 5b: Extend import usage checking to `_impl` components.
  - Parse `low/<name>_impl.pyi` docstrings for `GROUNDING:` sections. Extract all tokenized identifiers.
  - If an import $C$ in `imports_list` is absent from both AST imports/nodes and docstring `GROUNDING:` text, report error blaming `high/<name>_impl.md` or flagging for Spec QA triage.
- [ ] **Low-Level Spec Import Usage Checking (`low_lint.py`)**:
  - Add structural check in `low_lint.py` for `_impl.pyi`: Every imported module must either be utilized in type signatures/inheritance or cited in at least one `GROUNDING:` section.
- [ ] **Hardcoded Filename Linter Check (`low_lint.py`)**:
  - Add heuristic check in `low_lint.py` flagging string literals or docstring references matching file extensions (`.json`, `.toml`, `.yaml`, `.bazel`, `.py`, `.md`) or hidden dot-files (`.cleanroom_*`, `.git`) in non-`_ext` specifications unless imported from an `_ext` component.

### Phase 2: Pipeline & Role Configuration (`cleanroom_roles.toml`)
- [ ] **Streamline Assembly Pipeline in `cleanroom_roles.toml`**:
  - In `[roles.planning]`: Remove `"assembly"` from `active_component_types` (leaving `["implementation", "interface"]`).
  - In `[roles.scenario]`: Verify `"assembly"` remains absent.
  - In `[roles.low]`: Retain `"assembly"` in `active_component_types`, updating verification template to ensure `_asm.pyi` passes lightweight structural check against `high/*_asm.md`.
  - In `[roles.spec_qa]`: Update `verify_template` and logic to skip planning checks when auditing `_asm` targets.
- [ ] **Assembly Scaffolding in `lib_lint.py`**:
  - Enhance `lib_lint.py --scaffold` to automatically generate `lib/<name>_asm.py` directly from `low/<name>_asm.pyi` with zero agent intervention needed.

### Phase 3: Guide Updates (`update_python_with_ai/guides/`)
- [ ] **Update Spec QA Guide (`spec_qa.md`)**:
  - Add audit rule: Enforce that low-level specifications never hardcode file names not grounded in imported `_ext` components.
  - Add audit rule: Enforce that all `_impl` imports are accounted for in AST or `GROUNDING:` arguments.
  - Add triage protocol: Detail when to blame HLS vs Planning vs Low for unaccounted imports.
  - Document that `_asm` components bypass planning and scenario evaluation.
- [ ] **Update Planning-to-Low Guide (`planning_to_low.md`)**:
  - Explicitly document the requirement that `GROUNDING:` sections must mention all imported collaborator components.
  - Forbid hardcoding file names or format conventions in `low/*.pyi` without importing their defining `_ext` component.
  - Detail `_asm` low-level spec generation directly from HLS without planning canvases.
- [ ] **Update High-Level Spec Guide (`high_level_spec.md`)**:
  - Document that file names, markers, and host conventions belong strictly in `_ext` components.
  - Reiterate that `_impl` front-matter imports must be strictly necessary and will be verified against low-level `GROUNDING:` arguments.

### Phase 4: Component Refactoring & File Name Grounding
- [ ] **Create/Consolidate External Boundary for Workspace State (`workspace_state_ext`)**:
  - Author `high/workspace_state_ext.md` and `low/workspace_state_ext.pyi` defining canonical file names (`.cleanroom_workspaces.json`, `.cleanroom_pending_work.json`, `.cleanroom_blame_buffer.json`, `.cleanroom_role.json`) and their schemas.
- [ ] **Refactor Workspace Low Stubs to Import `workspace_state_ext`**:
  - Cascade alignment across `parts/workspace` (`workspace_registry`, `workspace_work`, `workspace_sync`, `workspace_provision`) to import `workspace_state_ext` and eliminate hardcoded string literals.

### Phase 5: Todo Action Item — Swatting Legacy `MODULE.bazel` References
- [ ] **Update Workspace HLS (`high/workspace_registry_impl.md`)**:
  - Remove `bazel_manifest_ext` import and "canonical Bazel workspace indicators" text.
  - Replace with canonical root markers (`cleanroom_roles.toml`, `pyproject.toml`, `.git`).
- [ ] **Cascade Downstream Alignment for `workspace_registry`**:
  - `planning/workspace_registry_impl.md`: Replace `MODULE.bazel` in contracts.
  - `low/workspace_registry.pyi` and `low/workspace_registry_impl.pyi`: Update postconditions and grounding.
  - `lib/workspace_registry.py`: Update root traversal functions.
  - `tests/*_test.py`: Update test fixtures to use `pyproject.toml` instead of `MODULE.bazel`.
- [ ] **Swat `MODULE.bazel` in Support Tools**:
  - Clean up `support/lib/build_lint_common.py`, `support/lib/cleanroom_role_tool.py`, and `support/lib/test_lint.py`.
