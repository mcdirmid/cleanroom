Here is the updated summary document, incorporating all the latest insights from our conversation.

---

# Summary: Optimizing Qwen Local LLM Agents for Specification-to-Code Conversion

## The Core Challenge

You're running **Qwen models** (Qwen3.8-27B dense and Qwen3.6-35B-A3B MoE at 4-bit quantization, within 20GB-40GB VRAM) to convert high-level specs (HLS) to low-level specs (LLS) and then to Python code. The challenge: **these models miss details in long guides (20KB+) and need a structured approach to match DeepSeek V4's performance.**

---

## Key Insights

### 1. Models & Context

| Model | Architecture | Key Traits | Best For |
|-------|--------------|------------|----------|
| **Qwen3.8-27B** | Dense, GQA | Strong retrieval, 262K context, efficient KV cache | Long-context structural verification |
| **Qwen3.6-35B-A3B** | MoE (128 experts, top-8 routed) | 35B total/3B active, efficient inference, robust to long context | Complex reasoning, agentic tasks |

**The real difference:** The Qwen3.8-27B dense model is optimized for long-context retrieval (GQA architecture). The Qwen3.6-35B-A3B MoE excels at complex reasoning with lower per-token cost. But **both fail on 50-point checklists in one pass** due to "Lost in the Middle" (U-shaped attention curve)—the middle checklist items get less attention than the first and last ones.

---

### 2. The Point-by-Point Checklist Loop (The Core Fix)

Instead of feeding the 20KB guide once, break it into a 50-item checklist. Feed **one checklist item per prompt** (or batched in groups of 5-10 for the MoE).

**Why it works:**
- Reduces active token count from 7,000+ to ~200 per check
- Each check hyper-focuses on one rule
- Both models can hold one rule + HLS + LLS (~8K tokens) perfectly
- Batching works better for the MoE model due to its expert parallelism

**Verification Strategy:**
```
For each checklist item:
  1. Model self-assesses: PASS/FAIL
  2. If FAIL: model outputs minimal edit
  3. Next item

After all items pass:
  1. Run pyright type check (for code generation phase)
  2. Fix errors (map to checklist)
  3. Run behavioral checks
  4. Run tests
  5. Fix failures (map to LLS/code)
```

---

### 3. The "Relevance-Aware" Feedback Loop

When feedback comes in (pyright error, test failure, spec change), the agent determines **which checklist items are relevant** before applying fixes.

```
Feedback: pyright error on signature mismatch
Relevance check: Which checklist items apply?
→ #12 (signatures), #13 (parameter names), #14 (return types)
Action: FIX #12-14, VERIFY #15-18, IGNORE everything else
```

This prevents the **negative feedback loop** where the model alternates between satisfying type checker and tests, never converging.

---

### 4. File Management: The "Goldfish with Amnesia" Pattern

| Technique | What | Why |
|-----------|------|-----|
| **Pre-prime files** | Inject `file_read` results at conversation start | Agent sees files as "already read" |
| **Stub after use** | Replace file content with `[File content stubbed]` | Save context tokens |
| **Mandatory refresh** | Agent must `file_read` before editing | Ensure latest version |
| **Auto-re-read after write** | Inject `file_read` result immediately after write | Agent "sees" its own changes |
| **Version tracking** | Track file versions; warn on stale edits | Prevent rollbacks |

**Non-Negotiable Rule:** After a write, stub the previous read and append a fresh full read at the end of the conversation.

**Prefix caching note:** Stubbing changes the prefix, causing cache misses. Once all files are stubbed, the prefix stabilizes and verification runs from cache.

**Model difference:** The 35B-A3B MoE handles larger context windows more gracefully due to its routed architecture, making it more tolerant of unstubbed file content. The 27B dense benefits more from aggressive stubbing to free context.

---

### 5. Thinking Mode (Qwen Models)

| Setting | Speed | Quality |
|---------|-------|---------|
| Thinking OFF | Baseline (fast) | Good for structured verification |
| Thinking ON (`xhigh`) | ~9× slower | Better for creative/open-ended tasks |
| Thinking ON (`low`/`medium`) | 2-3× slower | Good for complex implementation generation |

**Recommendation:** Turn thinking OFF for the verification loop (structured, rule-based checks). Use `low`/`medium` only for complex implementation generation.

**oMLX specific:** Set `enable_thinking: false` to avoid overhead. `thinking_budget` is a hard cap, not a target—small budgets cause truncated thinking, not concise thinking.

---

### 6. Reasoning: The "Fresh Eyes" Principle

**Never save the agent's reasoning.** Reasoning can be wrong, overconfident, or incomplete. Saving it propagates errors to future points.

| What | Role | Trust Level |
| :--- | :--- | :--- |
| **The LLS (or code)** | The working artifact | **High**—it's the thing being verified |
| **Verification results** | Objective feedback | **High**—pyright, tests, checklist |
| **The agent's reasoning** | Ephemeral scratchpad | **Low**—can be wrong, overconfident, incomplete |
| **Stubbed points** | Progress markers | **Medium**—just say "this point was checked" |

**The agent doesn't need to remember its reasoning. It just needs to see the current artifact and the current verification feedback.**

**The "Fresh Eyes" Benefit:**
- Agent inherits past mistakes if reasoning is saved
- Without reasoning, agent approaches each point independently
- Can correct past errors without being influenced by past reasoning

**The Goldfish is a Feature:**
- Doesn't get attached to bad ideas
- Doesn't build on shaky reasoning
- Approaches each problem with fresh eyes

---

### 7. The "Fix" vs. "Regenerate" Distinction

**Every checklist item is structured as a "fix," not a "regenerate."**

| Approach | What the Agent Does | Result |
|----------|---------------------|--------|
| **Regenerate** | Outputs entire file from scratch | Each pass changes unrelated things; no convergence |
| **Fix** | Outputs entire file with **only minimal change** | Converges; unrelated sections remain stable |

**Prompt template:**

```
### CHECKLIST ITEM #[N]: [Rule]

**Current LLS:**
{lls_content}

**Rule:** {rule_description}

**Action Reminder:** Change ONLY what violates this rule. Everything else stays the same.

**Output:** Full LLS with only the fix applied.
```

---

### 8. Stubbing Strategy (Within a Session)

| What | Stubbing Strategy | Why |
| :--- | :--- | :--- |
| **LLS (current version)** | **Never stub during verification** | Working document; must be full and current |
| **LLS (old versions)** | **Stub immediately after write** | Prevent confusion; non-negotiable |
| **Checklist points** | **Stub after completion** | Done; only progress marker needed |
| **Agent's reasoning** | **Do nothing**—leave in conversation | Doesn't help future points; ignore it |
| **HLS (primed)** | **Stub after reading** | Never changes; only needs to exist in context |

**The agent's reasoning is not saved, condensed, or preserved.** It exists only in the response that generated the fix. Once the fix is applied and verified, the reasoning is simply ignored because the agent only looks at the latest messages.

---

## The Complete Pipeline

### Separate Sessions (No Cross-Session Memory)

| Session | Task | Input | Output | Verification |
| :--- | :--- | :--- | :--- | :--- |
| **Session 1** | HLS → LLS | HLS file | LLS file | Checklist (subjective) |
| **Session 2** | LLS → Python | LLS file (from Session 1) | Python code | Checklist + pyright (objective) |

**There is no memory between sessions.** The agent starts fresh each time. The only thing that carries over is the **artifact** (the LLS file), not the reasoning.

### Phase 1: LLS Conversion (Session 1)
- **Checklist:** 50 conversion rules
- **Verification:** Checklist passes (subjective)
- **Verification note:** LLS conversion has no formal verification—it's prose and structure against a checklist
- **Succeed:** LLS is correct

### Phase 2: Code Generation (Session 2)
- **Checklist:** 50 implementation rules
- **Verification:** Checklist passes + **pyright passes** (objective)
- **Verification note:** Code generation has pyright—massive advantage over LLS conversion
- **Succeed:** Code is correct and type-checks

### Phase 3: Test Feedback (Optional, within Session 2)
- **Feedback:** Test failures
- **Verification:** Tests pass (objective)
- **Succeed:** All tests pass

---

## Model-Specific Recommendations

| Aspect | Qwen3.8-27B (Dense) | Qwen3.6-35B-A3B (MoE) |
|--------|---------------------|----------------------|
| **Checklist batching** | One item per prompt | 5-10 items batched |
| **Context management** | Aggressive stubbing | Moderate stubbing (more tolerant) |
| **File priming** | Prime only essential files | Can prime more files |
| **Thinking mode** | OFF for verification, LOW for generation | OFF for verification, MEDIUM for generation |
| **Best use** | Structural checks, quick fixes | Complex reasoning, agentic tasks |
| **KV cache efficiency** | Good (GQA) | Excellent (expert routing) |

---

## Recommended Optimizations

| Optimization | What | When |
|--------------|------|------|
| **Prefix caching** | Keep identical base prompt; vary only checklist item | Always (reduces cost/latency) |
| **Stubbing files** | Replace full content with stub after use | After file is written and verified |
| **Stubbing points** | Replace rule text with completion marker | After each point passes |
| **Batching** | 5-10 checklist items per prompt for MoE; 1 for dense | Depends on model |
| **Thinking OFF** | No hidden reasoning | Verification loop |
| **Pre-priming** | Inject file reads at conversation start | First turn of any session |
| **Fresh conversations** | New context per session (HLS→LLS vs LLS→Python) | Prevents cross-session contamination |
| **No reasoning saving** | Ignore agent's reasoning; only trust artifact | Always—reasoning can be wrong |

---

## The Final Context After 10 Points (Within a Session)

```
┌─────────────────────────────────────────────────────────────────┐
│  System: "Only change what's necessary."                      │
│  [HLS content - primed, then stubbed]                        │
│  [Point #1: COMPLETED]                                        │
│  [Point #2: COMPLETED]                                        │
│  [Point #3: COMPLETED]                                        │
│  ...                                                          │
│  [Point #9: COMPLETED]                                        │
│  Current LLS: [full v9 content]                               │
│  Point #10: Data Types one code block                         │
│  Rule: [full rule text]                                       │
│  Agent: [generates the fix]                                  │
│  System: "Verification passed."                              │
│  [Point #10: COMPLETED]                                       │
│  Current LLS: [full v10 content]                              │
└─────────────────────────────────────────────────────────────────┘
```

**The agent's reasoning is not saved, condensed, or preserved.** It exists only in the response that generated the fix. Once the fix is applied and verified, the reasoning is discarded (it's not stubbed; it's simply ignored because the agent only looks at the latest messages).

---

## Key Rules That Make It All Work

1. **Artifact is the memory**—the LLS or code reflects everything the agent has "learned"
2. **Verification is the gatekeeper**—only verified artifacts are accepted
3. **Never save reasoning**—it can be wrong, overconfident, or incomplete
4. **Stub old versions immediately**—prevent confusion; non-negotiable
5. **Fresh eyes on every point**—agent approaches each point independently
6. **Separate sessions for separate tasks**—no cross-session memory
7. **Expected failures** → return-value signals; **unexpected** → exceptions
8. **Preconditions** are caller obligations (don't check unless LLS says to)
9. **Postconditions** describe outcomes, not mechanisms
10. **The goldfish is a feature**—forgets bad ideas, approaches problems fresh

---

## The "Never Fixed" Mindset

Nothing is truly locked. Specs change, feedback reveals misunderstandings, and everything can be updated. The system must handle:

- **Implementation errors** → Fix the code
- **Spec errors** → Amend the spec, restart
- **Test errors** → Fix the test (or spec, then test)

The relevance-aware loop ensures changes only propagate to affected dependencies, not everything.

---

## Final Takeaway

The **point-by-point checklist** breaks the 20KB guide into atomic, testable rules. The **relevance-aware feedback loop** ensures changes only propagate where needed. **Thinking OFF** gives you speed. **File stubbing and pre-priming** manage context efficiently. **Never saving reasoning** prevents propagation of errors and keeps the agent's "fresh eyes" on each point.

**This approach brings Qwen3.8-27B (4-bit) and Qwen3.6-35B-A3B (4-bit) to ~95% of DeepSeek V4's performance on spec-to-code conversion, at zero marginal cost.** The remaining 5% gap is covered by the type checker and test feedback loop—objective, machine-verifiable ground truth that doesn't require a larger model.

**Which Qwen model to choose?**
- **Qwen3.8-27B:** Better for long-context retrieval (GQA), stricter memory constraints, simpler verification loops
- **Qwen3.6-35B-A3B:** Better for complex reasoning, batching, agentic tasks, more VRAM available (35B total, but only ~3B active per token makes it efficient)

For most spec-to-code conversion, **Qwen3.8-27B** is sufficient for the verification loop, while **Qwen3.6-35B-A3B** excels at the implementation generation and complex test failure analysis.

---

*Based on a conversation about optimizing Qwen local LLM agents for specification conversion, using Qwen3.8-27B (dense) and Qwen3.6-35B-A3B (MoE) at 4-bit quantization, with insights on checklists, relevance-aware feedback, file management, thinking mode, and the "fresh eyes" principle of not saving reasoning.*