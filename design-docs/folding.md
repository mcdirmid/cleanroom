### PROPOSAL: STATEFUL CURSOR & DYNAMIC VIEWPORT ARCHITECTURE FOR LOCAL CODING AGENTS

### Executive Summary

This proposal outlines a highly efficient, deterministic framework for managing large codebase states in long-horizon AI agent loops. Optimized specifically for local inference engines (such as oMLX) and compatible with standard top-down prefix caching (e.g., DeepSeek), this architecture eliminates context bloat and version confusion without mutating historical conversation text. 

### Core Pillars of the Architecture

### 1. The End-of-Prompt Dynamic Viewport

To maximize prefix caching, the entire conversation history must remain strictly append-only and immutable. Instead of embedding large code layouts inside past tool responses, we decouple the active application state and pin it to the absolute end of the context window. This "Dynamic Viewport" contains the single source of truth for all open file buffers and structural tool results. Because past turns are never altered or stubbed, the local inference engine hits a near 100% cache rate for the static rules and conversation history log, only processing the newly appended turns and the updated viewport. 

### 2. Session-Based Conversation Cursors

To prevent the agent from referencing outdated layouts or dead code ranges after an edit, we establish an explicit cursor allocation and destruction protocol: 

* **Allocation:** When an agent inspects, folds, or executes code, the tool creates a unique, incrementing identifier (e.g., [CURSOR_101]) explicitly recorded in the chat log. The contents matching that ID are rendered exclusively inside the dynamic viewport at the bottom.
* **Destruction:** When a subsequent edit or refactor makes that code layout obsolete, the next tool output explicitly appends a destruction notice (e.g., NOTICE: [CURSOR_101] is destroyed).
This creates an explicit state log that the transformer's attention mechanism uses to safely disregard stale pointers, entirely avoiding version confusion while maintaining a fully cached history log.

### 3. Isolated Line Addressing

To allow the agent to navigate code without mistaking structural addresses for executable text, files within the viewport utilize a standard gutter format (e.g., 001 | code). This completely avoids verbose XML wrappers that bloat tokens. A strict system rule ensures the agent understands that the text to the left of the pipe is metadata, preventing line prefixes from bleeding into generated code edits. 

### 4. Semantic Context Folding

Rather than flooding the context window with raw line-by-line file content, files and dense tool outputs (such as massive terminal logs or compiler outputs) are passed as compressed skeletons. Irrelevant code scopes are collapsed into brief placeholder comments, while active blocks are left expanded under their respective cursor handles. The agent navigates the codebase by invoking tools to dynamically fold or unfold these blocks, updating only the viewport at the bottom of the prompt.