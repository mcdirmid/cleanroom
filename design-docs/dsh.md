# DeepSeek Harness (`dsh`) Integration, Web Daemon, Visual Hierarchy UI Plugin & Session Management

> **Document Type:** Canonical Architectural Specification & System Guide  
> **Status:** Production / Implemented  
> **Scope:** DeepSeek Harness (`dsh`), DSH Web Daemon, Cordis UI Shell, Session Lifecycle, Workspace Retention, and Visual Subagent Hierarchy Plugin (`dsh-autofab-hierarchy`).

---

## 1. Executive Summary & Core Architecture

Autofab provides deep, first-class integration with the DeepSeek Harness (`dsh`) ecosystem across both local desktop CLI/GUI interfaces and remote browser-accessible daemon environments. This integration provides a high-throughput, low-cost execution substrate for Tier 1 (local quantized models such as Qwen 3.6 35B MoE via Apple Silicon) and Tier 2 (cloud models such as DeepSeek-V4 Flash).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               DEEPSEEK HARNESS (DSH) ECOSYSTEM                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   DESKTOP / CLI HARNESS                          DSH WEB DAEMON (launchd)              │
│   - Direct JSON-RPC socket streaming             - Port 3080 (Web UI / HTTP)           │
│   - Local Unix sockets                           - Port 47821 (RPC Bridge)             │
│   - Subprocess execution containment             - launchctl service management        │
│                                                  - Dynamic active token auth           │
│                                                                                        │
│                                      │                                                 │
│                                      ▼                                                 │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                         CORDIS FRONTEND UI SHELL                               │   │
│   │   - Extension slot architecture (sidebar, header, drawers)                     │   │
│   │   - Cleanroom Lean Preset (preset-standard, bash_run only)                     │   │
│   │   - Native Cordis Plugin: dsh-autofab-hierarchy                                │   │
│   │     • Sidebar mounting directly above Ungrouped                                │   │
│   │     • Real-time coordinator state polling (/autofab/api/state)                 │   │
│   │     • SVG vector role indicators (zero emoji)                                  │   │
│   │     • Active waves & collapsible "Prior waves" accordion                       │   │
│   │     • In-place DOM diffing & one-click session activation                      │   │
│   │     • Interactive Run Deletion (POST /autofab/api/delete-scope)                │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                                 │
│                                      ▼                                                 │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                     AUTOFAB COORDINATOR & RETENTION PIPELINE                   │   │
│   │   - Double-blind role worker dispatch (lib, test, qa, coverage, pretense)      │   │
│   │   - Ephemeral sibling workspaces & multi-segment scoping                       │   │
│   │   - Retained runs under benchmarks/runs/<suite>_<model>_<index>/               │   │
│   │   - Selective recycling: Finished recycled; Failed preserved in-place          │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Tenets
1. **Zero-Execution Coordinator**: The Autofab DAG coordinator executes in Python, performing topological wave clustering, dispatching role workers into isolated sub-workspaces, and monitoring progress without consuming generative tokens itself.
2. **First-Class Session Addressing**: Role workers are created via DSH JSON-RPC as independent top-level sessions. This circumvents internal Gateway subagent validation errors while preserving full streaming telemetry.
3. **Presentation-Layer Visual Hierarchy**: DSH Web's sidebar is dynamically transformed by a native Cordis UI plugin (`dsh-autofab-hierarchy`), grouping flat worker sessions by flight scope into clean, collapsible run cards with live status indicators and run deletion controls.
4. **Token Economy Parity**: DSH Web enforces the Cleanroom Lean Preset (`preset-standard`), exposing strictly `bash_run` to reduce tool token overhead from 5.5K to 1.7K tokens per step and compacting system prompts to 967 tokens, identically matching DSH Desktop.

---

## 2. DSH Web Service Architecture & Lifecycle Management

DSH Web is packaged and managed as an always-on macOS background daemon via `launchd`:

### Service Configuration
- **Property List Location**: `~/Library/LaunchAgents/com.deepseek.dsh-web.plist`
- **Standard Output Log**: `~/.dsh/dsh-web.log`
- **Standard Error Log**: `~/.dsh/dsh-web.err.log`
- **Networking**:
  - Web Server (HTTP / WebSocket): `3080`
  - Internal RPC Bridge: `47821`

### Lifecycle Controls
```bash
# Start or Restart the Daemon Service
launchctl kickstart -k gui/$(id -u)/com.deepseek.dsh-web

# Stop the Daemon Service
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.deepseek.dsh-web.plist

# Load the Daemon (Login/Boot Persistence)
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.deepseek.dsh-web.plist

# Status Check
launchctl list | grep com.deepseek.dsh-web
```

### Remote Access URL & Dynamic Token Authentication
DSH Web enforces authentication via dynamic, ephemeral session tokens generated on service boot. 

> [!IMPORTANT]
> **Strict URL Formatting**:
> - The **only supported URL** for remote access is:  
>   `http://seans-macbook-pro-2.local:3080/?token=<active_token>`
> - Never hardcode stale or static tokens.
> - Extract the dynamic active token path directly from the log file:
>   ```bash
>   echo "http://seans-macbook-pro-2.local:3080$(grep -o '/?token=[^ )]*' ~/.dsh/dsh-web.log | tail -n 1)"
>   ```
> - Always format the access URL as a clickable markdown hyperlink in agent communications.

### Security Fence & Browser Trust
The `/api` browser-trust fence accepts connections matching `trustedHosts` configured in `~/.dsh/profiles/web/cordis.patch.yml` under `@deepseek-ai/dsh-client-connection`. Requests from unlisted host headers or raw IP addresses are rejected with `403 Forbidden`.

---

## 3. The Visual Subagent Hierarchy & Gateway Invariant

### The Problem: Top-Level Session Clutter in DSH Web
When Autofab compiles or cleans a target scope (or executes a benchmark campaign), it commissions concurrent role workers across topological waves:
- Wave 1: `lib` (implementation) and `test` (unit tests) in double-blind isolation.
- Wave 2: `qa` (downstream behavioral verification) and `pretense_qa` (property verification).
- Wave 3: `coverage` (statement & branch coverage arbiter) and `pretense_coverage`.

In DSH Desktop, sessions execute cleanly. However, in DSH Web, each role worker is created as an independent top-level session residing in the **Ungrouped** section of the navigation sidebar. A single 3-flight benchmark flight generates 15 to 30 top-level sessions labeled `[ring_buffer] lib`, `[ring_buffer] test`, `[ring_buffer] qa`, etc. This completely overwhelms the DSH Web sidebar, making tracking active work or navigating between workers tedious and disorganized.

### The Subagent Hierarchy Invariant & Root Cause of Gateway Rejection
Directly creating sessions nested under a single parent coordinator session using DSH's native subagent addressing `{ kind: "subagent", parentSessionId, childSessionId }` causes fatal `subagent/unauthorized` errors in DSH Web's API Gateway.

Analysis of DSH internal components reveals two strict invariants:
1. **Closed Lifecycle Invariant (`@deepseek-ai/dsh-base`, `@deepseek-ai/dsh-subagent`)**: Subagents are designed to be spawned exclusively from within an active model execution loop via internal LLM tool calls (`tool-subagent` or `agent-team`).
2. **Binary Journal Header Invariant (`@deepseek-ai/dsh-api-session-controller`)**: The API Gateway validates session headers upon lookup. If on-disk binary journal files (`session.v4.jsonl.zstd`) lack matching parent records or an explicit `origin: "subagent"` header, the Gateway treats the lookup as unauthorized.

### The Solution: Presentation-Layer Visual Hierarchy
Rather than risking stability by modifying binary serialization formats or patching internal Gateway validation, Cleanroom implements the visual hierarchy at the **UI presentation layer**:
1. Role worker sessions are created as valid first-class sessions (`kind: "session"`), satisfying all Gateway security checks.
2. A native Cordis UI plugin intercepts the sidebar DOM, collapses flat worker sessions into an authoritative flight hierarchy, and provides instant one-click activation.

---

## 4. Native Cordis Client UI Plugin: `dsh-autofab-hierarchy`

The visual hierarchy is powered by a native Cordis plugin located at:
`~/.dsh/profiles/web/plugins/dsh-autofab-hierarchy/`

### Package Structure
```
~/.dsh/profiles/web/plugins/dsh-autofab-hierarchy/
├── package.json
└── lib/
    ├── index.js      # Backend server extension: API routes & state ingestion
    └── client.js     # Frontend Cordis client: sidebar mounting, DOM diffing, SVG styling
```

### Manifest & Injected Services (`package.json`)
The plugin registers as a standard Cordis plugin within `~/.dsh/profiles/web/package.json` and `cordis.patch.yml`:
```json
{
  "name": "dsh-autofab-hierarchy",
  "version": "0.1.0",
  "main": "lib/index.js",
  "peerDependencies": {
    "cordis": "^3.0.0"
  }
}
```

On the backend (`index.js`), the plugin injects the `webServer` service to register HTTP endpoints:
```javascript
export const inject = ["webServer"];
export function apply(ctx) {
  // Registers /autofab/api/state and /autofab/api/delete-scope
}
```

### Backend State Endpoints (`index.js`)
The backend exposes two high-performance JSON endpoints:
1. **`GET /autofab/api/state`**: Reads and returns `~/.dsh/autofab_state.json`. If unavailable, dynamically scans active sessions from the DSH session registry and parses `[<scope>] <role>` session titles as fallback.
2. **`POST /autofab/api/state`**: Ingests authoritative state updates from the Autofab Python coordinator, writing atomized JSON payloads directly to `~/.dsh/autofab_state.json`.
3. **`POST /autofab/api/delete-scope`**: Handles scope deletion, destroying corresponding sessions in the session manager and removing the scope from state.

### Frontend DOM Injection & In-Place Diffing (`client.js`)
The client script mounts directly inside DSH Web's browser runtime:
1. **Sidebar Attachment**: Uses `MutationObserver` to locate the primary navigation sidebar container (`div[data-component="sidebar"]`) and injects the `#autofab-hierarchy-container` immediately above the **Ungrouped** header.
2. **Suppression of Raw Ungrouped Items**: Identifies original flat session list items whose titles match `\[(.*?)\]\s*(.*)` and hides them (`display: none !important`), eliminating visual redundancy while keeping them hydrated in the background.
3. **In-Place DOM Diffing**: Periodically polls `/autofab/api/state` (every 1,500 ms). Rather than destroying and re-rendering the sidebar on each poll, the client uses keyed in-place diffing:
   - Scope containers are keyed by `data-scope`.
   - Existing scope cards are updated in-place (`updateExistingFlightGroup`).
   - Active roles update indicators smoothly without losing hover or focus states.
4. **Strict Zero-Emoji Policy & Vector SVG Icons**: All UI elements adhere strictly to the project's zero-emoji constraint. Status and role indicators are rendered via clean, scalable vector SVGs:
   - Running indicator: Animated SVG circular spinning ring (`.autofab-spinner`).
   - Idle / Completed indicator: Solid SVG green dot (`.autofab-dot-idle`).
   - Role badges: Styled typographic pills (`.role-badge`).
   - Action controls: Minimalist SVG trash icon for run deletion.

### Interactive Components
```
┌─────────────────────────────────────────────────────────────────┐
│ AUTOFAB RUNS                                                    │
├─────────────────────────────────────────────────────────────────┤
│ ▼ [ring_buffer_qwen_moe_1]                         [RUNNING] 🗑 │
│   Active Wave:                                                  │
│     [lib]  parts/ring_buffer/lib/ring_buffer_impl.py      ◌ RUN │
│     [test] parts/ring_buffer/tests/ring_buffer_test.py    ● IDLE│
│                                                                 │
│   ▶ Prior waves (1)                                             │
└─────────────────────────────────────────────────────────────────┘
```
- **Scope Group Header**: Displays the scope name, sequential flight index, status pill (`RUNNING`, `FINISHED`, `FAILED`), and a hover trash button (`🗑`).
- **Active Wave Card**: Lists current wave role workers. Clicking any role worker triggers `ctx.sessions.open(sessionId)` or dispatches a click to the underlying hidden session element, instantly focusing that worker in the main viewport with live streaming deltas.
- **Prior Waves Accordion**: Prior dispatched waves collapse neatly into an interactive disclosure panel (`Prior waves (N)`), providing full historical traceability without cluttering the active workspace view.

---

## 5. Scope Deletion & Session Lifecycle API

To prevent session accumulation across multiple test or benchmark runs, the visual hierarchy provides an interactive **Run Deletion** workflow:

### API Specification: `POST /autofab/api/delete-scope`
- **Request Body**:
  ```json
  {
    "scope": "benchmarks/runs/ring_buffer_qwen_moe_1"
  }
  ```
- **Server Execution**:
  1. Matches all sessions in the DSH session registry whose titles start with `[<scope>]` or `[<basename>]`.
  2. Invokes DSH `sessionController.destroy(sessionId)` or `sessionManager.deleteSession(sessionId)` to cleanly terminate processes, release sockets, and purge in-memory history.
  3. Updates `~/.dsh/autofab_state.json` by pruning the scope entry.
  4. Returns `{ "success": true, "deletedSessions": [...] }`.
- **Client Handling**:
  - The frontend trash button immediately applies opacity transition and removes the scope card from the DOM.
  - Re-polls state after 300ms to synchronize with the server.

---

## 6. Workspace Retention & Selective Recycling Architecture

Autofab's benchmark harness coordinates closely with DSH Web to provide deterministic workspace retention under `benchmarks/runs/`.

### Directory Structure & Naming Standard
Benchmark flight workspaces live under:
`benchmarks/runs/<suite>_<model_slug>_<index>/`
- Example: `benchmarks/runs/dag_engine_lite_qwen_moe_1/`
- Constituent target roots: `benchmarks/runs/<name>/parts/<suite>/`
- Status manifest: `benchmarks/runs/<name>/flight_status.json`

### `flight_status.json` Schema
```json
{
  "suite": "dag_engine_lite",
  "model": "qwen-moe",
  "flight_id": "dag_engine_lite_qwen_moe_1",
  "status": "finished",
  "created_at": "2026-11-10T09:30:00Z",
  "completed_at": "2026-11-10T09:45:00Z",
  "passed": true
}
```

### In-Place Failure Preservation (Deprecation of `.failed` Renaming)
Previously, failed flights were renamed with a `.failed` suffix (`dag_engine_lite_qwen_moe_1.failed`). This broke external shell paths, terminal inspectors, and IDE tabs.
Under the current architecture:
- Workspaces **never change their directory paths** upon failure.
- `_teardown_flight_scope` marks `flight_status.json` in-place with `"status": "failed"`.
- Developers can inspect logs, diffs, and test reports directly in the original workspace.

### Selective Slot Recycling Policy
When a new benchmark run is triggered:
1. **Finished Slots (`status: finished`)**: Automatically recycled and overwritten. Finished runs represent verified artifacts that do not require indefinite preservation once archived in `benchmarks/results/`.
2. **Failed Slots (`status: failed`)**: **Preserved strictly in-place**. The provisioner discovers the existing failed slot and advances the sequential index ($N \to N+1$), provisioning `dag_engine_lite_qwen_moe_2`.
3. **In-Flight Slots (`status: running`)**: Preserved; provisioner advances index to prevent stepping on concurrent runs.

### Multi-Segment Scoping Standard
To prevent toolchain truncation where `benchmarks/runs/...` was incorrectly chopped to `benchmarks`, `parse_cleanroom_target` in `autofab_role_tool.py` enforces full multi-segment scope preservation:
- Target address `benchmarks/runs/ring_buffer_qwen_moe_1/parts/ring_buffer/lib/ring_buffer_impl.py#lib` resolves cleanly to:
  - `scope`: `benchmarks/runs/ring_buffer_qwen_moe_1`
  - `dir_scope`: `benchmarks/runs/ring_buffer_qwen_moe_1`
  - `display_scope`: `ring_buffer_qwen_moe_1`

---

## 7. Python Coordinator Telemetry & Integration Details

### Session Title Formatting (`dsh_telemetry_impl.py`)
Session titles are constructed deterministically upon worker initialization:
```python
clean_scope = dir_scope.strip("/").strip() if dir_scope else ""
clean_role = role_name.strip() if role_name else ""
session_title = f"[{clean_scope}] {clean_role}" if clean_scope and clean_role else (clean_role or clean_scope or "autofab")
```

### Authoritative State Emission (`dsh_harness_impl.py`)
During DAG traversal, the coordinator continuously emits state updates to `~/.dsh/autofab_state.json`:
```python
state_payload = {
    "scopes": [scope_state_dict],
    "timestamp": time.time(),
    "version": 1
}
with open(state_file, "w") as f:
    json.dump(state_payload, f, indent=2)
```
This ensures DSH Web UI reflects real-time wave progression, target assignments, and worker states without relying on fragile DOM scraping or unstructured log parsing.

---

## 8. Subagent Concurrency & Hardware Contention Control (`concurrent_subagents`)

### The Single-GPU Contention Problem
Local offline models (such as Qwen MoE, Gemma MoE, and local MLX/Ollama backends running under Tier 1) operate on shared single-GPU hardware with unified memory architectures. While cloud API providers can scale horizontally to service dozens of parallel subagents, running multiple concurrent subagents against a single local GPU causes severe resource contention:
- GPU memory saturation and context thrashing.
- Unnecessary request queue serialization at the model server level.
- High step latency degradation across interleaved agent steps.

### Declarative Schema & Configuration
To eliminate local hardware contention, Autofab introduces the `concurrent_subagents` configuration parameter:
- **Location**: Defined in `model_configs.toml` under `[models.<profile>]` (and optionally in `~/.config/autofab/credentials.toml`).
- **Permitted Values**:
  - `None` / Unset: Unlimited concurrency (standard parallel wave dispatch for cloud API models).
  - `1`: Strictly enforces single-subagent execution, dispatching at most one subagent at any time.
  - Any value other than `1` (or `None`) is invalid and rejected with a `ValueError`.
- **Harness Restriction**: `concurrent_subagents` is **strictly disallowed for models using the `antigravity` harness**. Antigravity manages subagents through interactive desktop sessions and does not support headless hardware contention limits. Attempting to set `concurrent_subagents` on an Antigravity model raises a configuration error.
- **Tier 1 Local Defaults**: All local offline models (`qwen-moe`, `tiel-coder-qwen-moe`, `qwen-next-flash`, `qwen-dense`, `gemma-moe`, `gemma-dense`) set `concurrent_subagents = 1` alongside `subagent_batch_size = 1`.

### Most Recently Used (MRU) Priority Scheduling Policy
When `concurrent_subagents = 1`, the Python coordinator schedules work sequentially:
1. **Active Worker Guard**: At any point in the supervision loop, if `len(active_workers) >= 1`, no new subagents are dispatched until the running worker concludes its round and is harvested.
2. **Dynamic Role Selection via MRU**: When no subagent is actively executing (`len(active_workers) == 0`) and multiple unblocked candidate roles are available in `ready_roles_map`:
   - The coordinator prioritizes the **most recently run role** (the role whose previous dispatch timestamp is most recent).
   - If multiple unblocked candidate roles have never run, selection falls back to the natural topological/declaration order in the DAG.
3. **Benefits**: MRU scheduling ensures conversational context locality, prompt cache reuse on the local GPU, and focused iterative progress through role feedback loops before switching contexts.

---

## 9. Verification & Operational Health

The DSH integration is verified against the entire test suite and production benchmark flights:
- **Repo Verification**: `bin/test` passes 100% clean (0 errors, code 0).
- **Live Flight Pass Rates**:
  - `deepseek-flash` on `lru_cache` (Combined): PASS (19P / 0F, 0 pyright errors, $0.0753).
  - `gemini-flash` on `ring_buffer` (Standard): PASS (16P / 0F, 0 pyright errors, $0.1382).
  - `qwen-moe` on `ring_buffer` (Combined): PASS (20P / 0F, 0 pyright errors, $0.0000).
- **UI Responsiveness**: DOM diffing latency $< 15\text{ms}$; instant one-click session activation; immediate trash cleanup with server-side session termination.
