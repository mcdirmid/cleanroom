# DSH Web Architecture, Visual Subagent Hierarchy & UI Plugin Design Doc (`dsh_todo.md`)

> **Status: Active Proposal & Master Implementation Roadmap**  
> **Author:** Cleanroom Architecture Pair  
> **Scope:** DeepSeek Harness (`dsh`), DSH Web Daemon, Cordis UI Shell, Session Management & Visual Subagent Tree Hierarchy.

---

## Progress Checklist

- [x] **Phase 1: Architecture & Requirements Codification**
  - [x] Document DSH Web background daemon architecture, launchd service, and dynamic token remote access URL.
  - [x] Document Lean Preset parity (`preset-standard`) and token economy optimizations.
  - [x] Analyze the Subagent Hierarchy Invariant and root cause of `subagent/unauthorized` errors in DSH Web API Gateway.
  - [x] Verified Cordis client navigation API: `ctx.sessions.open(sessionId)` brings any session to foreground.
  - [x] Evaluated risks of direct Cordis plugin development vs. userscript prototyping; adopted Direct Approach 1.
- [x] **Phase 2: Native Cordis Client UI Plugin Development (`dsh-autofab-hierarchy`)**
  - [x] Scaffold local Cordis client plugin package at `~/.dsh/profiles/web/plugins/dsh-autofab-hierarchy/`.
  - [x] Inject client dependencies: `['slots', 'sessions', 'workspaces', 'locale']`.
  - [x] Register UI slots in sidebar (`sidebar.footer.action`) and header (`conversation.session.header.actions`).
  - [x] Group Ungrouped sessions by `[<scope>]` prefix and role into collapsible tree.
  - [x] Wire `onClick` handler to `ctx.sessions.open(sessionId)` to bring selected conversation to the foreground.
  - [x] Highlight active session using `ctx.sessions.list.getSnapshot().current`.
  - [x] Remove legacy clutter subagent plugin (`@leetoners/dsh-ui-subagent-monitor`).
- [x] **Phase 3: Cordis Profile Integration & Live Validation**
  - [x] Register plugin in `~/.dsh/profiles/web/package.json` and `cordis.patch.yml`.
  - [x] Kickstart daemon (`launchctl kickstart -k gui/$(id -u)/com.deepseek.dsh-web`) and verify bundle compilation.
  - [x] Validate repo integrity with `bin/test` (0 errors, code 0).
  - [x] Execute live validation benchmark flight with `uv run autofab benchmark --model qwen-moe --suite ring_buffer --units 1` across `lib`, `test`, `qa`, and `coverage` roles (100% convergence, PASS).
- [ ] **Phase 4: Python Coordinator Session Tagging & Metadata Enrichment**
  - [ ] Audit `autofab/parts/dsh/lib/dsh_telemetry_impl.py` session creation logic.
  - [ ] Enrich session projection payloads with structured metadata (`scope`, `role`, `flight_id`).
  - [ ] Ensure naming convention remains backwards-compatible: `[<scope>] <role>`.
- [ ] **Phase 6: Subagent Bridge Native Journal Header Probe (Advanced)**
  - [ ] Test hooking `service.create()` options in `dsh-subagent-bridge` to inject `origin: 'subagent'` and `parentSession: parentId` at binary journal instantiation (`session.v4.jsonl.zstd`).
  - [ ] Verify if DSH API Gateway validates `{ kind: "subagent", parentSessionId, childSessionId }` across browser reloads without core patches.

---

## Table of Contents

1. [Executive Summary & Motivation](#1-executive-summary--motivation)
   - [Background & Daemon Architecture](#background--daemon-architecture)
   - [The Problem: Top-Level Session Clutter in DSH Web](#the-problem-top-level-session-clutter-in-dsh-web)
   - [The Subagent Hierarchy Invariant & Gateway Validation](#the-subagent-hierarchy-invariant--gateway-validation)
2. [Current Session Naming Convention in Autofab Coordinator](#2-current-session-naming-convention-in-autofab-coordinator)
   - [Session Naming Logic in `dsh_telemetry_impl.py`](#session-naming-logic-in-dsh_telemetry_implpy)
   - [Session Lifecycles & Ungrouped Classification](#session-lifecycles--ungrouped-classification)
3. [Dual-Track Solution Architecture](#3-dual-track-solution-architecture)
   - [Approach 1: Native Cordis Client UI Plugin (Best Integration)](#approach-1-native-cordis-client-ui-plugin-best-integration)
   - [Approach 2: Lightweight Browser Userscript (Fastest Setup)](#approach-2-lightweight-browser-userscript-fastest-setup)
   - [Trade-off Matrix & Comparison](#trade-off-matrix--comparison)
4. [Technical Specification: Cordis Client Plugin (`@autofab/dsh-ui-dashboard`)](#4-technical-specification-cordis-client-plugin-autofabdsh-ui-dashboard)
   - [Plugin Structure & Manifest](#plugin-structure--manifest)
   - [UI Extension Slots in Cordis Web App](#ui-extension-slots-in-cordis-web-app)
   - [Session Model, WebSocket RPC & Live State](#session-model-websocket-rpc--live-state)
5. [Technical Specification: Browser Userscript Overlay](#5-technical-specification-browser-userscript-overlay)
   - [Metadata Header & Host Matching](#metadata-header--host-matching)
   - [DOM Traversal & Mutation Observer](#dom-traversal--mutation-observer)
   - [Navigation & Session Switching](#navigation--session-switching)
6. [Actionable Implementation Roadmap](#6-actionable-implementation-roadmap)

---

## 1. Executive Summary & Motivation

### Background & Daemon Architecture

Autofab provides deep integration with DeepSeek Harness (`dsh`) for both desktop GUI and browser-accessible web environments:
- **Daemon Service**: DSH Web runs as a macOS background daemon via `launchd`:
  `~/Library/LaunchAgents/com.deepseek.dsh-web.plist`
  listening on web port 3080 with bridge on port 47821.
- **Remote Access URL & Active Token**: The only supported remote access endpoint is:
  `http://seans-macbook-pro-2.local:3080/?token=<active_token>`
  (extracted dynamically from `~/.dsh/dsh-web.log`).
- **Browser-Trust Fence**: The `/api` boundary accepts connections matching `trustedHosts` in `~/.dsh/profiles/web/cordis.patch.yml` under `@deepseek-ai/dsh-client-connection`.
- **Lean Preset Parity**: `cordis.patch.yml` enforces the Cleanroom Lean Preset (`preset-standard`), exposing only `bash_run`, reducing tool token overhead from 5.5K to 1.7K tokens, and compacting system prompts to 967 tokens, identically matching DSH Desktop.

### The Problem: Top-Level Session Clutter in DSH Web

When the Autofab coordinator executes benchmark campaigns or cleaning waves (e.g., `uv run autofab clean <scope>` or `bin/evaluate_model_efficiency.py`), it commissions concurrent role workers:
- `lib` (implementation)
- `test` (unit test suite)
- `qa` (downstream behavioral verification)
- `coverage` (statement & branch coverage arbiter)
- `pretense` / `pretense_qa` / `pretense_coverage` (state-machine property fuzzing)

In DSH Desktop, these sessions execute cleanly. However, in DSH Web, each worker is instantiated as an independent top-level session residing under the **Ungrouped** section of the sidebar. A single 3-flight benchmark campaign spawns 15 to 30 top-level sessions labeled `[ring_buffer] lib`, `[ring_buffer] test`, `[dag_engine_lite] qa`, etc. This completely overwhelms the DSH Web navigation sidebar.

### The Subagent Hierarchy Invariant & Gateway Validation

Attempting to nest worker sessions under a single coordinator session using DSH's native subagent addressing `{ kind: "subagent", parentSessionId, childSessionId }` fails due to strict internal invariants:
1. **Closed Lifecycle Invariant**: `@deepseek-ai/dsh-base` and `@deepseek-ai/dsh-subagent` expect subagents to be spawned exclusively via internal LLM tool calls (`tool-subagent` or `agent-team`).
2. **Strict API Gateway Validation**: `@deepseek-ai/dsh-api-session-controller` validates session headers upon lookup and throws `subagent/unauthorized` if on-disk binary journal headers (`session.v4.jsonl.zstd`) lack matching parent records or an explicit `origin: "subagent"`.

Therefore, the visual hierarchy must be achieved at the **UI presentation layer**, organizing top-level sessions into a collapsible tree structure without breaking backend Gateway validation.

---

## 2. Current Session Naming Convention in Autofab Coordinator

### Session Naming Logic in `dsh_telemetry_impl.py`

In [`autofab/parts/dsh/lib/dsh_telemetry_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/dsh/lib/dsh_telemetry_impl.py#L778-L832), session creation formats the title as:

```python
clean_scope = dir_scope.strip("/").strip() if dir_scope else ""
clean_role = role_name.strip() if role_name else ""
session_title = f"[{clean_scope}] {clean_role}" if clean_scope and clean_role else (clean_role or clean_scope or "autofab")
```

When managing existing sessions, stale session detection uses the bracketed tag:
```python
target_tag = f"[{clean_scope}]"
```

### Session Lifecycles & Ungrouped Classification

- **CWD Assignment**: Each session is initialized with `cwd = real_ws` pointing to the ephemeral sibling role workspace (e.g. `../autofab_autofab_role_workspaces/<session>/`). Because these workspace paths are ephemeral and outside DSH Web's configured workspace projects, DSH Web categorizes them under **Ungrouped**.
- **Agent Preset**: `agentPreset: "standard"`.
- **Title Updates**: Set via `session/update` JSON-RPC calls immediately upon session creation.

---

## 3. Dual-Track Solution Architecture

Based on analysis of DSH Web's Cordis architecture and runtime feedback, two complementary approaches are available:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          DSH Web Architecture                          │
│                                                                        │
│   ┌─────────────────────┐                 ┌────────────────────────┐   │
│   │ Approach 2:         │                 │ Approach 1:            │   │
│   │ Browser Userscript  │                 │ Cordis UI Plugin       │   │
│   │ (Tampermonkey)      │                 │ (@autofab/dashboard)   │   │
│   └──────────┬──────────┘                 └───────────┬────────────┘   │
│              │ Injects DOM / Floating Panel           │ Registered in  │
│              ▼                                        │ cordis.patch   │
│   ┌───────────────────────────────────────────────────▼────────────┐   │
│   │                     DSH Web Frontend (Cordis)                  │   │
│   │   - Extension Slots (Header, Sidebar, Drawers)                 │   │
│   │   - Active WebSocket / RPC Connection to Daemon                │   │
│   └───────────────────────────────────────────────────┬────────────┘   │
│                                                       │                │
│                                                       ▼                │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │           DSH Web Daemon Service (Port 3080 / 47821)           │   │
│   │   - sessionController.list()                                   │   │
│   │   - Ungrouped Sessions: "[<scope>] <role>"                     │   │
│   └────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

### Approach 1: Native Cordis Client UI Plugin (Best Integration)

DSH Web mounts UI components through Cordis client plugins (e.g., `@deepseek-ai/dsh-client-ui-subagent`, `@leetoners/dsh-ui-subagent-monitor`, `dsh-session-manager`).
- **Mechanism**: A TypeScript/React plugin package loaded into DSH Web's Cordis profile (`~/.dsh/profiles/web/cordis.patch.yml`). Registers a custom drawer or sidebar icon in the UI.
- **Session Grouping**: Queries `sessionController.list()` (or client `listSessions`), filters for sessions where `!session.cwd` or title matches `\[(.*?)\]\s*(.*)`, and groups them into collapsible trees by `<scope>`.
- **Live Updates**: Shares DSH Web's native WebSocket/RPC connection, automatically reflecting streaming indicators, token metrics, and process states without manual polling.
- **Navigation**: Directly sets active session ID in the main viewport on click.

### Approach 2: Lightweight Browser Userscript (Fastest Setup)

Runs as a client-side script via Tampermonkey or Violentmonkey on `http://seans-macbook-pro-2.local:3080/*`.
- **Mechanism**: A ~120-line JavaScript script injected directly into the DOM.
- **Capabilities**:
  - Intercepts sidebar DOM nodes or fetches `/api` session listings.
  - Collapses top-level `[<scope>] <role>` items into a custom floating or docked panel.
  - Switches active sessions by triggering clicks on original session items or navigating DSH routes.
- **Advantage**: Zero build step, immediate 15-minute setup, impervious to DSH daemon updates.

### Trade-off Matrix & Comparison

| Criterion | Approach 1: Cordis Client Plugin | Approach 2: Browser Userscript |
| :--- | :--- | :--- |
| **Setup Time** | 1–2 hours (scaffolding, build, patch) | 15 minutes (paste into extension) |
| **Build Tooling** | Node.js / pnpm / TypeScript build | Pure client JavaScript |
| **UI Integration** | Seamless native Cordis theme & drawer | Injected floating/docked DOM element |
| **Live State** | Native RPC / WebSocket subscription | MutationObserver / DOM polling |
| **Token & Metric Access** | Direct access to telemetry store | Limited to DOM-visible badges |
| **Maintenance** | Rebuild on bundle updates | Browser extension configuration |

---

## 4. Technical Specification: Cordis Client Plugin (`@autofab/dsh-ui-dashboard`)

### Plugin Structure & Manifest

The plugin resides in `~/.dsh/plugins/autofab-dashboard/`:

```
~/.dsh/plugins/autofab-dashboard/
├── package.json
├── tsconfig.json
└── src/
    ├── index.ts        # Cordis plugin entrypoint & slot registration
    ├── TreeView.tsx    # Collapsible scope/flight tree component
    └── types.ts        # Session & state interfaces
```

`package.json`:
```json
{
  "name": "@autofab/dsh-ui-dashboard",
  "version": "0.1.0",
  "main": "dist/index.js",
  "dependencies": {
    "@deepseek-ai/dsh-client-ui": "^0.21.0"
  },
  "peerDependencies": {
    "cordis": "^3.0.0",
    "react": "^18.0.0"
  }
}
```

### UI Extension Slots & Foreground Session Navigation in Cordis Web App

Cordis client plugins declare injected services:
```javascript
const inject = ['slots', 'sessions', 'workspaces', 'locale'];
```

#### Foreground Navigation (`ctx.sessions.open`)
Verified directly in `dsh-session-manager`:
```javascript
// Bringing a conversation to the foreground in the main viewport:
ctx.sessions.open(sessionId);

// Inspecting active foreground conversation:
const currentSessionId = ctx.sessions.list.getSnapshot().current;
```
When `ctx.sessions.open(sessionId)` is called:
1. DSH Web immediately focuses and displays the selected conversation in the primary chat canvas/viewport.
2. The session history is hydrated and rendered.
3. Live WebSocket streaming deltas for the active session are attached to the foreground viewport.

#### Extension Slot Injection
Plugins register UI slots into the layout via `ctx.slots.inject`:
- `sidebar.footer.action`: Adds a button/modal to the bottom of the sidebar (used by `dsh-session-manager`).
- `sidebar.secondary`: Mounts a secondary side panel or tree.
- `conversation.session.header.actions`: Injects an action button into the active conversation header.

### Session Model, WebSocket RPC & Live State

The component accesses the active session store:
```typescript
const TITLE_REGEX = /^\[(.*?)\]\s*(.*)$/;

interface AutofabFlightGroup {
  scope: string;
  sessions: {
    sessionId: string;
    role: string;
    status: 'idle' | 'running' | 'done' | 'error';
    updatedAt: number;
  }[];
}

export function groupSessions(sessions: any[]): Record<string, AutofabFlightGroup> {
  const groups: Record<string, AutofabFlightGroup> = {};
  for (const s of sessions) {
    const match = s.title?.match(TITLE_REGEX);
    if (!match) continue;
    const [, scope, role] = match;
    if (!groups[scope]) {
      groups[scope] = { scope, sessions: [] };
    }
    groups[scope].sessions.push({
      sessionId: s.sessionId,
      role: role.trim(),
      status: s.status || 'idle',
      updatedAt: s.updatedAt || 0,
    });
  }
  return groups;
}
```

---

## 5. Technical Specification: Browser Userscript Overlay

### Metadata Header & Host Matching

```javascript
// ==UserScript==
// @name         Autofab DSH Web Subagent Hierarchy Tree
// @namespace    http://cleanroom.local/autofab
// @version      0.1.0
// @description  Groups flat [<scope>] <role> ungrouped sessions into collapsible trees in DSH Web
// @match        http://seans-macbook-pro-2.local:3080/*
// @grant        none
// ==/UserScript==
```

### DOM Traversal & Mutation Observer

The script targets DSH Web's sidebar items:
1. Observes DOM mutations on the session list container (`div[data-testid="session-list"]` or sidebar list).
2. Extracts session titles starting with `[` (e.g. `[ring_buffer] lib`).
3. Hides original flat elements from the Ungrouped list.
4. Mounts an interactive panel at the top of the sidebar containing collapsible groups:
   - `▼ [ring_buffer] (3 roles)`
     - `• lib`
     - `• test`
     - `• qa`
   - `▶ [dag_engine_lite] (2 roles)`
5. Clicking any child role triggers the click event on the corresponding hidden original element or invokes DSH client router navigation.

---

## 6. Actionable Implementation Roadmap

### Phase 1: Prototype Verification with Userscript (Immediate)
- Deploy the starter Tampermonkey script to verify grouping behavior against live benchmark sessions.
- Confirm click-to-navigate responsiveness and live DOM badge updates.

### Phase 2: Metadata Tagging in Coordinator (Next)
- Ensure all sessions created by `autofab` via `dsh_telemetry_impl.py` include structured labels.
- Support flight tags `[flight_<timestamp>][<scope>] <role>` for multi-flight benchmark separation.

### Phase 3: Cordis Plugin Packaging (Long-Term Production)
- Bundle `@autofab/dsh-ui-dashboard` into `~/.dsh/profiles/web/cordis.patch.yml`.
- Provide native theme styling and persistent sidebar integration.
