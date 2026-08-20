### PROPOSAL: DYNAMIC TODO & SCRATCHPAD ARCHITECTURE FOR LONG-HORIZON AGENTS

### Executive Summary

Long-horizon coding agents frequently suffer from "plan drift"—losing track of their primary objective after encountering nested compiler errors or complex debugging loops. This proposal introduces a stateful, single-frame TODO list and Scratchpad designed to anchor the agent's focus. Positioned within the append-only dynamic viewport, this framework eliminates history clutter and remains 100% efficient with local prefix caching. 

### The Dual-Interface Design: File vs. Tool

To maximize utility, the TODO/Scratchpad is implemented as a virtual file (e.g., plan.md) located inside the agent's workspace. This provides two seamless interaction pathways depending on the model's current intent: 

### 1. The Direct File Interface

The agent interacts with the workspace via its standard file-editing tools. It is granted full permission to read and rewrite plan.md using its standard buffer editing commands. This raw text flexibility allows the agent to naturally brain-dump ideas, draft pseudocode snippets, or adjust markdown checkboxes as its reasoning evolves. 

### 2. The Structured Tool Interface

Alongside direct file editing, the framework exposes an explicit helper tool: update_plan(todo_items, current_hypothesis). When called, this tool performs a fast structural overwrite of the file. Gating certain high-stakes actions (such as initiating a major refactor or executing a terminal script) behind this tool forces the agent to explicitly state its hypothesis and check off its current progress before touching production code. 

### Layout and Cache Optimization

To maintain system-wide performance and prevent model version confusion, the active state of plan.md is managed with the following mechanics: 

* **Bottom-of-Prompt Pinning:** The active contents of plan.md are appended to the absolute end of the context window inside the Dynamic Viewport. Because the plan sits directly above the model’s generation window, it leverages recency bias to keep the agent tightly focused on the immediate task.
* **Prefix Cache Protection:** Modifying the plan at the absolute bottom ensures that the vast, static conversation history sitting above it is never invalidated. The local inference engine instantly recalls past turns from the SSD/RAM cache, only computing the token differences in the updated plan.
* **Cursor Integration:** When the agent updates the plan, the framework assigns a session handle (e.g., [CURSOR_PLAN]). If a subsequent code edit shifts the codebase state, the system emits an automated note: NOTICE: [CURSOR_PLAN] remains valid; code cursors invalidated. This cleanly decouples the agent's internal reasoning state from unstable codebase geometry.