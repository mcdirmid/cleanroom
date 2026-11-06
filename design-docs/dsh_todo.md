# Autofab DeepSeek Harness (DSH Web) Subagent Roadmap

> **Status: Active Investigation & Design**  
> **Core Objective**: Enable true visual subagent hierarchy in DSH Web for Autofab multi-role workflows—either by authoring a dedicated Cleanroom/Autofab DSH Web UI plugin or by creating an improved subagent extension.

---

## 1. Executive Summary & Current Operational Baseline

### 1.1 The Operational Fallback: Ungrouped First-Class Sessions
While DSH Web subagent visualization is being solved, the multi-agent execution pipeline is **100% operational** in production using Ungrouped First-Class Sessions with Lean Preset Parity:
* **First-Class Navigation**: Role workers (`lib`, `test`, `qa`, `coverage`, `baseline`) spawn as independent top-level sessions labeled `[<scope>] <role>` (e.g. `[ring_buffer] lib`) residing in DSH Web's sidebar under **Ungrouped**.
* **Zero Gateway Authorization Errors**: Because these sessions open with standard `{ kind: "session" }` addresses, clicking them in Mac or iPad Safari opens the full streaming conversation without tripping `subagent/unauthorized`.
* **Token Overhead Parity**: The Cordis profile `~/.dsh/profiles/web/cordis.patch.yml` enforces the Cleanroom Lean Preset (`preset-standard`). Tool token overhead is reduced from 5.5K to 1.7K tokens, and system prompts are compacted from 1.5K to 967 tokens, matching DSH Desktop identically.
* **Autonomous Convergence**: Benchmark flights and cleanroom DAG convergence run headlessly with 0 pyright errors and 100% test pass rates across parallel runs.

### 1.2 The Open Problem: Subagent Hierarchy in the Web UI
Although Ungrouped sessions execute cleanly, spawning 5 to 10 top-level sessions per benchmark flight clutters the DSH Web sidebar. The target user experience is:
1. A **single top-level coordinator entry** in the sidebar representing the flight (e.g. `[Autofab] Run: ring_buffer`).
2. Inside that conversation, an interactive visual **Subagent Dashboard / Card** displaying child role workers (`lib`, `test`, `qa`, `coverage`).
3. Clicking a child worker seamlessly opens that worker's conversation thread or drawer in Mac/iPad Safari without `subagent/unauthorized` errors.

---

## 2. Technical Post-Mortem: Why DSH Web Rejects External Subagents

Previous attempts to force DSH Web to treat bridge sessions as subagents hit deep internal invariants in DSH's architecture:

### 2.1 The Closed Lifecycle Invariant
In `@deepseek-ai/dsh-base` and `@deepseek-ai/dsh-subagent`, subagents are not simply arbitrary sessions linked by ID. They are expected to be created through DSH's internal LLM tool dispatch loop (`tool-subagent` or `agent-team`), where the coordinator agent invokes subagents directly within DSH's process tree.

### 2.2 Immutable v4 Journal Headers
DSH persists conversation journals as compressed binary files (`session.v4.jsonl.zstd`). At format creation:
* `header.origin: "subagent"`
* `header.parentSession: "<parent_id>"`
* `header.delegationDepth: 1`

These headers are immutable. When sessions were created via `ctx.service('sessions').create({ cwd })` and in-memory headers were mutated (`live.header = ...`), DSH did **not** persist those header fields to disk. Upon client refresh or gateway routing, DSH re-read the session from disk where `origin` and `parentSession` were undefined.

### 2.3 Strict API Gateway Validation (`subagent/unauthorized`)
When the web frontend navigates to a subagent via `{ kind: "subagent", parentSessionId, childSessionId }`, `@deepseek-ai/dsh-api-session-controller` executes:
```javascript
function validateAddress(address, header, inheritedEventCount, projections) {
  if (header.origin !== "subagent" || header.parentSession !== address.parentSessionId) {
    throw new RemoteError("subagent/unauthorized", "subagent does not belong to the supplied parent");
  }
}
```
Because the child's on-disk header lacked `origin === "subagent"` and `parentSession === parentSessionId`, the API Gateway firmly threw `subagent/unauthorized`.

---

## 3. Targeted Solution Paths

To achieve a clean subagent user experience without fighting DSH internal binary invariants, two primary avenues are available:

### Approach A: Dedicated Cleanroom / Autofab DSH UI Plugin (Recommended)

Rather than trying to trick DSH's closed subagent gateway into accepting external sessions as `{ kind: "subagent" }`, we build a dedicated Cordis UI plugin for DSH Web (e.g. `@autofab/dsh-ui-dashboard` or `dsh-plugin-cleanroom`):

#### Architecture:
1. **First-Class Session Storage with Metadata Tagging**:
   - Role worker sessions are created as first-class sessions with `agentPreset: 'standard'`.
   - The session record or projection cache is annotated with Autofab metadata:
     ```json
     {
       "autofab": {
         "scope": "ring_buffer",
         "role": "lib",
         "flightId": "flight_20261106_200444",
         "runTitle": "[Autofab] ring_buffer",
         "status": "converged"
       }
     }
     ```
2. **Custom Cordis Web Component / Extension**:
   - Registers a custom card or panel in DSH Web (similar to `@leetoners/dsh-ui-subagent-monitor`, but purpose-built).
   - Queries `sessionController.list()` and groups all sessions matching `[<scope>]` or carrying the `autofab` metadata tag under a single collapsible Flight Run container.
   - Renders a DAG topology / role status board:
     - `lib` (Complete, 123s, $0.0104)
     - `test` (Complete, 60s, $0.0082)
     - `qa` (Complete, 10s, $0.0011)
     - `coverage` (Complete, 10s, $0.0011)
3. **Native Direct Navigation via `{ kind: "session" }`**:
   - Clicking any role worker in the dashboard opens it via standard `{ kind: "session", sessionId }`.
   - **Zero `subagent/unauthorized` errors**, because it uses DSH's sanctioned top-level session route while visually presenting as a hierarchical run.
   - The plugin can hide or collapse child worker sessions from the main sidebar "Ungrouped" list, keeping the sidebar spotless.

### Approach B: Upgraded Bridge / Subagent Creation Hook

If true `{ kind: "subagent" }` routing is required for standard UI subagent components:
1. **Hook Session Creation in `dsh-subagent-bridge`**:
   - Intercept DSH's session creation factory so the v4 header is initialized with `origin: 'subagent'` and `parentSession: parentId` at the exact moment of format instantiation, ensuring it is committed directly into `session.v4.jsonl.zstd`.
2. **Append Required Journal Projection Events**:
   - Append legitimate `subagent/catalog` and `subagent/start` events to the parent session journal so that DSH's internal `projections.values.subagent` index resolves the child correctly.
3. **Validate Against Gateway**:
   - Test address resolution `{ kind: "subagent", parentSessionId, childSessionId }` across browser reloads to ensure zero `subagent/unauthorized` rejections.

---

## 4. Work Breakdown & Next Milestones

- [x] **Milestone 1: Resilient Fallback Baseline (DONE)**
  - Ungrouped First-Class Sessions with `[<scope>] <role>` labels.
  - Lean prompt and tool preset parity (1.7K tool tokens, 967 system prompt tokens).
  - Parallel flight execution isolation in `PYTHONPATH`.
  - Configurable CLI flags (`--dsh-web`, `--dsh-desktop`) and `model_configs.toml` default toggle.

- [ ] **Milestone 2: Design DSH UI Extension Plugin**
  - Scaffold `@autofab/dsh-ui-dashboard` Cordis plugin package in `~/.dsh/plugins/` or repo packages.
  - Define custom view card rendering topological DAG waves and role workers.
  - Implement group-by-scope filtering for sidebar sessions.

- [ ] **Milestone 3: Bridge Native Header Injection Probe**
  - Prototype hooking `service.create()` options in `dsh-subagent-bridge` to test if `origin: 'subagent'` can be baked into the v4 binary journal cleanly without Homebrew core patching.
  - Verify if DSH's Gateway accepts the resulting session under `{ kind: "subagent" }`.

- [ ] **Milestone 4: Interactive Subagent Drawer Integration**
  - Integrate role inspector drawer into DSH Web so clicking a role worker slides out the conversation without navigating away from the flight coordinator view.
