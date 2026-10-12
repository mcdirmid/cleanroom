# Specification Grounding, External Boundaries, and Assembly Pipeline Architecture

This document establishes the architecture, validation constraints, and phased implementation roadmap for four interrelated specification and pipeline enhancements in Cleanroom:
1. **Low-Level Specification File Name Grounding via External Boundaries (`_ext`)**: Prohibiting floating or hardcoded filenames, paths, and schemas in low-level specifications (`low/*.pyi`), requiring them to be grounded via imported external boundary components (`<name>_ext`).
2. **Swatting Legacy `MODULE.bazel` References**: Eliminating remaining Bazel workspace markers and dependencies across High-Level Specifications, planning canvases, and low-level stubs in favor of native UV and Python repository conventions.
3. **Streamlined Assembly Component (`_asm`) Pipeline**: Treating assembly components like external boundary components by eliminating superfluous planning canvases and scenario files, allowing low-level stubs (`low/<name>_asm.pyi`) to mechanically mirror assembly instructions directly from the High-Level Specification (`high/<name>_asm.md`).
4. **Implementation Component (`_impl`) Import Accountability & Spec QA Attribution**: Enforcing complete usage of all declared imports in implementation components, requiring unexposed collaborators to be cited in natural language `GROUNDING:` arguments, and establishing Spec QA defect triage when imports are unaccounted for.

> [!NOTE]
> **Completed Architecture Document**
> This document specifies the architectural rules, validator designs, guide amendments, and boundary contracts for specification grounding and assembly simplification. All implementation phases in this document have been completed and verified.

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

### 2.3 Canonical External Boundary Structure: `cleanroom_files_ext` (COMPLETED)

To ground Cleanroom workspace and toolchain interactions, the external boundary component **`cleanroom_files_ext`** was canonically authored in `update_with_ai/parts/core/`:
- **[`high/cleanroom_files_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/cleanroom_files_ext.md)**
- **[`low/cleanroom_files_ext.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/low/cleanroom_files_ext.pyi)**

It exposes canonical path constants and schemas:
1. **`CLEANROOM_CONFIG_FILE: str = "cleanroom.toml"`**:
   Scoped methodology configuration binding (`methodology = "//update_python_with_ai"`).
2. **`CLEANROOM_ROLES_FILE: str = "cleanroom_roles.toml"`**:
   Declarative role definition tables (`[roles.<role_name>]`).
3. **`ROLE_DESCRIPTOR_FILE: str = ".cleanroom_role.json"`**:
   Isolated role workspace descriptor written at provisioned workspace roots.
4. **`WORKSPACES_REGISTRY_FILE: str = ".cleanroom_workspaces.json"`**:
   Multi-role active workspace registry with file locking.
5. **`CLEANROOM_LOG_FILE: str = ".cleanroom.log"`**:
   Append-only change and feedback diagnostic event log.

### 2.4 Specification Derivation Example

With external boundary grounding, contracts become epistemically traceable across workspace interfaces and implementations:

```python
# CORRECT ARCHITECTURE: Grounded file references in low/workspace_work.pyi
import cleanroom_files_ext

@singleton_type("agent_session")
class WorkspaceWork(InTier[AgentSessionTier], Protocol):
    """Manages session work queues using workspace state persistence.
    
    INVARIANTS:
    - MUST serialize pending targets conforming to cleanroom_files_ext schema.
    """

    @operation
    def clear_pending_work(self) -> None:
        """Clears pending work targets.

        POSTCONDITIONS:
        - MUST delete pending work file designated by cleanroom_files_ext from workspace directory.
        """
        ...
```

And in the implementation stub [`low/workspace_work_impl.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_work_impl.pyi):
```python
import workspace_work
import cleanroom_files_ext
import filesystem_ext

@singleton_type("agent_session")
class WorkspaceWork(workspace_work.WorkspaceWork, InTier[AgentSessionTier]):
    """Implementation managing session work queues.

    GROUNDING:
    - Reads and writes pending targets JSON using cleanroom_files_ext pending work
      filename and schema, invoking Path.read_text and Path.write_text from filesystem_ext.
    """
    ...
```

---

## 3. Todo Item: Swatting Legacy `MODULE.bazel` References

Cleanroom has completely eliminated Bazel from its runtime, dependency resolution, testing, and workspace execution. However, stale references to `MODULE.bazel` remain as historical residue.

### 3.1 Inventory of Legacy `MODULE.bazel` Residue & Status

The repo-wide build system migration eradicated all Bazel configuration (`.bazelrc`, `.bazelversion`, `MODULE.bazel`, `BUILD.bazel`, `parts/bazel`, Starlark macros). Residual references in workspace discovery, test fixtures, and support tools have been eradicated:

| File Path | Location / Line | Nature of Reference | Status |
|:---|:---|:---|:---|
| [`update_with_ai/parts/workspace/high/workspace_registry_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/workspace_registry_impl.md) | Line 11, 24 | Line 11 imports `cleanroom_files_ext`; line 24 prose references canonical Cleanroom configuration files | **COMPLETED**: Import updated to `cleanroom_files_ext`; prose updated to canonical root markers (`cleanroom.toml`, `cleanroom_roles.toml`, `pyproject.toml`, `.git`) |
| [`update_with_ai/parts/workspace/planning/workspace_registry_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/planning/workspace_registry_impl.md) | Line 19 | `searches ancestor directories for Cleanroom configuration files or .git markers [search_ancestor_markers]` | **COMPLETED**: Contract updated to reference `.git` or `cleanroom.toml` / `pyproject.toml` |
| [`update_with_ai/parts/workspace/low/workspace_registry.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_registry.pyi) | Line 105 | `- MUST locate ancestor containing repository markers or .git directory.` | **COMPLETED**: Postcondition updated to reference markers from `cleanroom_files_ext` |
| [`update_with_ai/parts/workspace/low/workspace_registry_impl.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_registry_impl.pyi) | Line 39 | `- Traverses upward from start_dir checking for repository markers or .git directories` | **COMPLETED**: `GROUNDING:` docstring updated to reference `cleanroom_files_ext` markers |
| [`update_with_ai/parts/workspace/lib/workspace_registry_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/lib/workspace_registry_impl.py) | Lines 418, 430, 448, 554, 562, 578 | Hardcoded checks for `MODULE.bazel` in root traversal | **COMPLETED**: Updated implementation to check `cleanroom_files_ext` markers (`cleanroom.toml`, `cleanroom_roles.toml`, `pyproject.toml`, `.git`) prioritizing `.git` across all ancestors |
| [`update_with_ai/parts/workspace/tests/workspace_provision_impl_test.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/tests/workspace_provision_impl_test.py) | Lines 159, 199 | Creating dummy `MODULE.bazel` file in tests | **COMPLETED**: Replaced dummy marker with `notes.txt` |
| [`update_with_ai/parts/workspace/tests/workspace_sync_impl_test.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/tests/workspace_sync_impl_test.py) | Lines 345, 361 | Creating dummy `MODULE.bazel` file in tests | **COMPLETED**: Replaced dummy marker with `notes.txt` |
| [`update_python_with_ai/support/lib/build_lint_common.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/support/lib/build_lint_common.py) | Lines 297–303, 2289 | Docstring & marker tuple checks for `MODULE.bazel` | **COMPLETED**: Removed `MODULE.bazel`; relies on `cleanroom_roles.toml`, `cleanroom.toml`, `pyproject.toml`, and `.git` |
| [`update_python_with_ai/support/lib/cleanroom_role_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/support/lib/cleanroom_role_tool.py) | Line 39 | Checking `os.path.isfile(os.path.join(curr, "MODULE.bazel"))` | **COMPLETED**: Removed `MODULE.bazel` check; checks `cleanroom.toml` |
| [`update_python_with_ai/support/lib/test_lint.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/support/lib/test_lint.py) | Line 337 | Checking `MODULE.bazel` in repo root marker tuple | **COMPLETED**: Removed `MODULE.bazel` check |

### 3.2 Todo Item Status
- **Status**: **COMPLETED**. All residual `MODULE.bazel` references have been eliminated repo-wide outside of design documentation. Full downstream alignment was executed per the Mandatory Specification-First rule, and the complete test suite (368 passed, 9 subtests passed) and pyright (0 errors) pass cleanly via `bin/test`.

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
- [x] **Linter Support for Implementation Import Accountability (`high_lint.py`) (COMPLETED)**:
  - Updated `high_lint.py` Check 5b: Extended import usage checking to `_impl` components.
  - Parse `low/<name>_impl.pyi` docstrings for `GROUNDING:` sections and extract candidate class tokens from dependencies.
  - If an import $C$ in `imports_list` is absent from both AST imports/nodes and docstring `GROUNDING:` text, report error blaming `high/<name>_impl.md` or flagging for Spec QA triage.
- [x] **Low-Level Spec Import Usage Checking (`low_lint.py`) (COMPLETED)**:
  - Added structural Check 12 in `low_lint.py` for `_impl.pyi`: Every imported module must either be utilized in type signatures/inheritance or cited in at least one `GROUNDING:` section.
- [x] **Hardcoded Filename Linter Check (`low_lint.py`) (COMPLETED)**:
  - Added Check 13 in `low_lint.py` flagging string literals and docstrings containing raw host file conventions (`.json`, `.toml`, `.cleanroom_*`, `.git`) in non-`_ext` specifications unless grounded via imported `cleanroom_files_ext`.

### Phase 2: Pipeline & Role Configuration (`cleanroom_roles.toml`)
- [x] **Streamline Assembly Pipeline in `cleanroom_roles.toml` (COMPLETED)**:
  - In `[roles.planning]`: Removed `"assembly"` from `active_component_types` (leaving `["implementation", "interface"]`).
  - In `[roles.scenario]`: Verified `"assembly"` remains absent.
  - In `[roles.low]`: Retained `"assembly"` in `active_component_types`, added `low_lint.py` to `verify_template` alongside pyright to ensure `_asm.pyi` passes lightweight structural check against `high/*_asm.md`.
  - In `[roles.spec_qa]`: Verified `verify_template` skips planning checks (`! test -f planning/{unit_name}.md`) when auditing `_asm` targets.
  - Safely retired all 9 redundant `planning/*_asm.md` files across parts directories.
- [x] **Assembly Scaffolding in `lib_lint.py` (COMPLETED)**:
  - Verified `lib_lint.py --scaffold` automatically generates `lib/<name>_asm.py` directly from `low/<name>_asm.pyi` with zero agent intervention needed.

### Phase 3: Guide Updates (`update_python_with_ai/guides/`)
- [x] **Update Spec QA Guide (`spec_qa.md`) (COMPLETED)**:
  - Added audit rule: Enforce that low-level specifications never hardcode file names not grounded in imported `_ext` components.
  - Added audit rule: Enforce that all `_impl` imports are accounted for in AST or `GROUNDING:` arguments.
  - Added triage protocol: Detailed when to blame HLS vs Planning vs Low for unaccounted imports.
  - Documented that `_asm` components bypass planning and scenario evaluation.
- [x] **Update Planning-to-Low Guide (`planning_to_low.md`) (COMPLETED)**:
  - Explicitly documented the requirement that `GROUNDING:` sections must mention all imported collaborator components.
  - Forbade hardcoding file names or format conventions in `low/*.pyi` without importing their defining `_ext` component.
  - Detailed `_asm` low-level spec generation directly from HLS without planning canvases.
- [x] **Update High-Level Spec Guide (`high_level_spec.md`) (COMPLETED)**:
  - Documented that file names, markers, and host conventions belong strictly in `_ext` components.
  - Reiterated that `_impl` front-matter imports must be strictly necessary and are verified against low-level `GROUNDING:` arguments.

### Phase 4: Component Refactoring & File Name Grounding
- [x] **Create/Consolidate External Boundary (`cleanroom_files_ext`) (COMPLETED)**:
  - Authored [`high/cleanroom_files_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/cleanroom_files_ext.md) and [`low/cleanroom_files_ext.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/low/cleanroom_files_ext.pyi) in `parts/core` defining canonical file names (`cleanroom.toml`, `cleanroom_roles.toml`, `.cleanroom_role.json`, `.cleanroom_workspaces.json`, `.cleanroom.log`, `.cleanroom_pending_work.json`, `.cleanroom_blame_buffer.json`) and their schemas.
  - Aligned `workspace_registry_impl.md` and `uv_manifest_loader_impl.md` to import `cleanroom_files_ext`.
- [x] **Refactor Remaining Workspace Low Stubs to Import `cleanroom_files_ext` (COMPLETED)**:
  - Cascaded alignment across `parts/workspace` (`workspace_work`, `workspace_sync`, `workspace_provision`, `workspace_tool` and their `_impl` counterparts) across `high/`, `planning/`, and `low/` to import `cleanroom_files_ext` and eliminate hardcoded file name literals from stubs, contracts, and postconditions.

### Phase 5: Swatting Legacy `MODULE.bazel` References
- [x] **Eradicate Bazel Build System Files (COMPLETED)**:
  - Deleted `.bazelrc`, `.bazelversion`, `MODULE.bazel`, `MODULE.bazel.lock`, all `BUILD.bazel` files across packages, legacy `parts/bazel` component, and Starlark macros repo-wide.
- [x] **Update Workspace HLS Imports (COMPLETED)**:
  - Removed `bazel_manifest_ext` import in `high/workspace_registry_impl.md` and replaced with `cleanroom_files_ext`.
- [x] **Clean Up Workspace HLS Prose (`high/workspace_registry_impl.md`) (COMPLETED)**:
  - Replaced line 24 prose "canonical Bazel workspace indicators" with canonical repository root markers (`cleanroom.toml`, `cleanroom_roles.toml`, `pyproject.toml`, `.git`).
- [x] **Cascade Downstream Alignment for `workspace_registry` (COMPLETED)**:
  - `planning/workspace_registry_impl.md`: Replaced `MODULE.bazel` in contract `[search_ancestor_markers]`.
  - `low/workspace_registry.pyi` and `low/workspace_registry_impl.pyi`: Updated postconditions and `GROUNDING:` to reference `cleanroom_files_ext` markers instead of `MODULE.bazel`.
  - `lib/workspace_registry_impl.py`: Updated root traversal functions (`_search_ancestor_markers`, `_fallback_to_ambient_working_directory`, and lines 554, 562, 578) to eliminate `MODULE.bazel` checks and correctly search ancestor directories.
  - `tests/*_test.py`: Updated `workspace_provision_impl_test.py` and `workspace_sync_impl_test.py` test fixtures to use `notes.txt` / cleanroom configuration instead of `MODULE.bazel`.
- [x] **Swat `MODULE.bazel` in Support Tools (COMPLETED)**:
  - Cleaned up `support/lib/build_lint_common.py`, `support/lib/cleanroom_role_tool.py`, and `support/lib/test_lint.py`.
