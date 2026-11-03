# Autofab DSH Desktop Plugin Architecture & Scope Tree Roadmap

> **Status: Future Roadmap / Deferred**  
> This design document specifies the architecture, extension points, and implementation plan for a dedicated DeepSeek Harness (DSH Desktop) plugin (`dsh-autofab`) that provides first-class, collapsible scope-to-role subagent navigation without violating Autofab's physical information embargo.

---

## 1. Context & Problem Statement

### 1.1 The Workspace Folder Impedance Mismatch
In DeepSeek Harness Desktop, workspace folders in the sidebar are strictly bound to a single physical directory on disk. As implemented in `@deepseek-ai/dsh-workspace`:

```typescript
// @deepseek-ai/dsh-workspace/src/workspace.ts
workspace.sessionIds = this.record.sessionIds.filter(
  (id) => this.host.sessionPath(id) === this.record.path
);
```

When attaching a session to a workspace, the harness enforces that `session.header.cwd === workspace.path` (an exact canonical path equality check). Furthermore, the UI sidebar hides any session whose `cwd` does not match the active workspace folder.

### 1.2 The Autofab Physical Information Embargo Invariant
Autofab enforces a strict physical information embargo across role workers:
- Each role worker (`lib`, `pretense`, `qa`, `spec_qa`, etc.) executes in an isolated role workspace provisioned parallel to the repository root:
  `../autofab_role_workspaces/<scope>_<role>/`
- Subagents are strictly forbidden from executing with `cwd` set to the repository root or parent scope directory, preventing language models from navigating parent directories (`../..`) to inspect unmasked source code or pre-existing solutions.
- Because role workspaces have distinct physical filesystem paths, they cannot share a single DSH Desktop workspace folder under DSH's native data model.
- Registering each role workspace as an independent DSH workspace folder creates catastrophic UI bloat (e.g. 129+ workspace folders clogging the sidebar).
- Registering subagents as native DSH child subagents (`origin: "subagent"`) causes the harness to hide them from the left sidebar entirely, eliminating real-time visual monitoring.

### 1.3 Interim Baseline (Approach A)
As implemented in [`dsh_telemetry_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/dsh/lib/dsh_telemetry_impl.py):
- Per-role workspace folder registration is eliminated.
- Subagent sessions execute directly within their isolated physical `cwd`.
- Conversation titles are formatted with explicit scope prefixes: `[<scope>] <role>` (e.g., `[benchmark_1] lib`, `[benchmark_1] pretense`, `[benchmark_1] qa`).
- Subagents appear in DSH Desktop's primary conversation list, allowing full real-time stream observation while preserving the physical embargo.

While functional, a flat list of scoped titles becomes noisy during large concurrent runs (e.g., 20+ subagents across multiple benchmark flights). A dedicated DSH Desktop plugin resolves this by creating a logical hierarchy in the presentation layer.

---

## 2. DSH Desktop Extension Architecture

DeepSeek Harness is built on the **Cordis** microkernel (`@deepseek-ai/cordis`) and an Electron + React web shell.

### 2.1 Plugin Layout
DSH plugins are standard Node/npm packages installed in the active profile directory:
`/Users/seanmcdirmid/Library/Application Support/dsh-desktop/harness/profiles/web/`

A full-stack DSH plugin consists of two tiers:
1. **Host-Side Service** (`lib/index.js`):
   - Runs in the Node.js/Electron main process.
   - Injects Cordis services: `webServer`, `workspaceRegistry`, `sessions`, `agents`, etc.
   - Intercepts or augments JSON-RPC calls, session metadata, and lifecycle events.
2. **Client-Side UI Extension** (`lib/client.js`):
   - Declared in `package.json` under `"dsh.client"`:
     ```json
     {
       "exports": {
         ".": "./lib/index.js",
         "./client": "./lib/client.js"
       },
       "dsh": {
         "bundle": {
           "patch": "./cordis.patch.yml"
         },
         "client": {
           "inject": [
             "@deepseek-ai/dsh-client-ui-slots"
           ],
           "platform": "web"
         }
       }
     }
     ```
   - Loaded into the Electron renderer process.
   - Injected with UI services: `slots`, `sessions`, `workspaces`, `uiWorkspace`, `locale`.

### 2.2 UI Slot Mechanism (`@deepseek-ai/dsh-client-ui-slots`)
The renderer exposes slot injection points via `ctx.slots.inject(slotName, componentFactory)`:
- `sidebar.panellist`: Registers a primary navigation icon/panel on the leftmost activity rail (alongside Chat, Workspaces, and Extensions).
- `sidebar.footer.action`: Adds persistent footer tools to the sidebar.
- `conversation.session.header.actions`: Injects contextual status badges or action buttons into the active conversation header.

---

## 3. Proposed Plugin Design: `dsh-autofab`

### 3.1 Logical Scope & Role Tree View
Instead of forcing subagents into DSH workspace folders, `dsh-autofab` injects a dedicated **Autofab Orchestrator Panel** into `sidebar.panellist`.

The panel dynamically reads all active sessions via `ctx.sessions`, parses scoped session headers, and renders an interactive tree:

```text
┌────────────────────────────────────────────────────────┐
│  AUTOFAB SESSIONS                                      │
├────────────────────────────────────────────────────────┤
│  [Search sessions...]                      [Collapse]  │
├────────────────────────────────────────────────────────┤
│  ▾ benchmark_1                               ● RUNNING │
│    ├── ● lib          Round 1, Step 4 · 42k tokens     │
│    ├── ○ pretense     Round 1 · Complete               │
│    └── ○ qa           Round 1 · Complete               │
│                                                        │
│  ▾ benchmarks_flight_2                       ● ACTIVE  │
│    ├── ● high         Round 1, Step 2 · 18k tokens     │
│    ├── ◌ planning     Pending upstream                 │
│    └── ◌ low          Pending upstream                 │
│                                                        │
│  ▸ ring_buffer                               ✔ CLEAN   │
│  ▸ lru_cache                                 ✔ CLEAN   │
└────────────────────────────────────────────────────────┘
```

### 3.2 Key Capabilities
1. **Dynamic Grouping**:
   - Parses conversation titles (`[<scope>] <role>`) or reads rich metadata (`session.header.metadata.autofab`) attached during session creation.
   - Automatically clusters sessions by `<scope>` without altering filesystem layout or DSH workspace records.
2. **One-Click Session Activation**:
   - Clicking any role node triggers `ctx.uiWorkspace.openSession(sessionId)`, instantly focusing the main chat window onto that subagent's live stream.
3. **Live Round & Step Indicators**:
   - Displays real-time role execution state:
     - `RUNNING`: actively executing steps with live token burn.
     - `WAITING`: waiting for tool response or coordinator dispatch.
     - `RESOLVED`: completed, submitted, or blamed.
4. **Context Header Badges**:
   - Injects a role status badge into `conversation.session.header.actions` showing the parent scope, current round index, and execution status.
5. **Cleanroom Embargo Preservation**:
   - Role workers remain strictly within their isolated `autofab_role_workspaces/<scope>_<role>/` directory. The UI tree is purely a presentation-layer projection.

---

## 4. Implementation Plan (When Scheduled)

### Phase 1: Plugin Scaffolding
- Create plugin package directory:
  `~/Library/Application Support/dsh-desktop/harness/profiles/web/plugins/dsh-autofab/`
- Author `package.json` declaring Cordis bundle patch and client entry point:
  - `main`: `lib/index.js`
  - `exports./client`: `lib/client.js`
  - `dsh.client.inject`: `["@deepseek-ai/dsh-client-ui-slots"]`

### Phase 2: Host Half (`lib/index.js`)
- Implement lightweight Cordis service:
  ```javascript
  import { Context } from 'cordis';
  
  export const name = 'autofab-orchestrator';
  export const inject = ['sessions', 'workspaceRegistry'];
  
  export function apply(ctx) {
    // Intercept or enrich session metadata if necessary
  }
  ```

### Phase 3: Client Half & UI Component (`lib/client.js`)
- Inject into `sidebar.panellist`:
  ```javascript
  export default function (ctx) {
    ctx.slots.inject('sidebar.panellist', () => ({
      id: 'autofab-panel',
      title: 'Autofab',
      icon: AutofabIcon,
      order: 15,
      render: () => <AutofabSessionTree ctx={ctx} />
    }));
  }
  ```
- Implement `AutofabSessionTree` in React:
  - Use `ctx.sessions` reactive state store.
  - Regex match `/^\[(?<scope>[^\]]+)\]\s+(?<role>.+)$/` on session titles.
  - Render collapsible scope groups with role items.
  - Bind `onClick` to `ctx.uiWorkspace.openSession(session.id)`.

### Phase 4: Autofab Telemetry Enrichment
- Update [`dsh_telemetry_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/dsh/lib/dsh_telemetry_impl.py) to pass structured metadata in RPC calls:
  ```python
  session_create_params = {
      "cwd": real_ws,
      "metadata": {
          "autofab": {
              "scope": clean_scope,
              "role": clean_role,
              "target": target,
              "round": round_idx,
          }
      }
  }
  ```

### Phase 5: Profile Activation
- Add plugin entry into:
  `/Users/seanmcdirmid/Library/Application Support/dsh-desktop/harness/profiles/web/cordis.patch.yml`
- Register in local `package.json` and run `pnpm install` in the DSH web profile directory.

---

## 5. Architectural Verification & Invariants

| Invariant | Enforcement Mechanism |
| :--- | :--- |
| **Information Embargo** | Subagents always run in isolated role workspaces; no shared parent directory permissions. |
| **Zero Harness Mutation** | Native DSH `workspace.json` is not modified; no ephemeral workspace folders created. |
| **Live Visibility** | All subagent sessions remain valid primary conversations; live streaming and tool inspection work out of the box. |
| **Terminology Compliance** | UI and telemetry strictly use **round** and **step**; prohibited historical terminology is avoided. |
