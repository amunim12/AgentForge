# Model Card — AgentForge LLMs

AgentForge uses three LLM calls per pipeline iteration. This document describes each model's intended use, observed characteristics, limitations, and ethical considerations.

---

## Planner — Gemini 1.5 Flash

**Provider:** Google AI Studio  
**Role:** Task decomposition — converts a user task description into a structured JSON plan  
**Endpoint:** `ChatGoogleGenerativeAI(model="gemini-1.5-flash")`

### Why This Model
Gemini 1.5 Flash has strong instruction-following and structured JSON output reliability at low latency. The Planner prompt requires strict schema adherence (TaskPlan Pydantic model), and Flash handles this consistently without requiring `response_mime_type=application/json` forcing.

### Observed Characteristics
- Produces verbose plans with many nested fields; normalised by Pydantic validation
- Temperature 0.1 gives highly deterministic plans for similar inputs (good for reproducibility)
- Typical latency: 3–8 seconds including streaming

### Limitations
- Can over-decompose simple tasks (5+ steps for what could be 2)
- Occasionally wraps JSON output in ```json fences — handled by `_strip_fences()` in planner.py
- No guaranteed recency — knowledge cutoff means web-search-dependent steps must still be present in the plan even when the answer seems known

### Ethical Considerations
- The Planner prompt includes no user PII; task descriptions are validated by guardrails before reaching the LLM
- Google's usage policies apply: do not use for tasks that violate Google's AI principles
- All calls are traced via LangSmith for auditability

---

## Executor — Llama 3.1 70B (Groq)

**Provider:** Groq Cloud  
**Role:** Step-by-step plan execution using tools (web search, code execution, file notebook)  
**Endpoint:** `ChatGroq(model="llama-3.1-70b-versatile")`

### Why This Model
Groq's inference speed (200+ tokens/second) is critical for the Executor, which may run 10–15 tool-calling iterations per task. Llama 3.1 70B has strong tool-use capabilities via LangChain's `create_tool_calling_agent`. The combination gives responsive streaming without the cost of GPT-4-class models.

### Observed Characteristics
- Prefers flat, terse output structures vs Gemini's verbosity
- Tool selection is reliable for the three provided tools (web_search, code_executor, file_tool)
- May duplicate tool calls when uncertain — the `max_iterations=15` cap prevents infinite loops
- Temperature 0.1 chosen for consistent, factual execution

### Limitations
- 70B context window: very long plans or accumulated scratchpad can cause truncation
- Groq free tier has rate limits (30 req/min); sustained load may hit these
- Tool-calling can fail silently on malformed tool inputs — `handle_parsing_errors=True` provides graceful recovery
- No native multimodal support; cannot process images in tasks

### Ethical Considerations
- Executor has access to E2B sandboxed code execution — code runs in an isolated cloud container with no access to host filesystem or network beyond the sandbox
- Web search results are unfiltered; the system does not fact-check sources
- Groq's usage policies apply; do not submit tasks that would generate harmful content

---

## Critic — Gemini 1.5 Flash

**Provider:** Google AI Studio  
**Role:** Quality scoring — evaluates execution output against the original task  
**Endpoint:** `ChatGoogleGenerativeAI(model="gemini-1.5-flash")`

### Why This Model
Same model as Planner for consistency in evaluation criteria. The Critic task is structured output (JSON score + lists), which Flash handles reliably.

### Scoring Rubric
The Critic evaluates on five axes:
1. **Completeness** — did the Executor address every step in the plan?
2. **Accuracy** — are factual claims supported by the sources cited?
3. **Clarity** — is the output readable and well-structured?
4. **Depth** — does the answer go beyond surface-level?
5. **Actionability** — can the user act on this output without further research?

Score = weighted average (0.0–1.0). Threshold to accept: 0.75.

### Observed Characteristics
- Scores tend to cluster in 0.60–0.90 range; rarely scores below 0.50 or above 0.95
- Improvements list is consistently specific and actionable
- Occasionally scores "correctness" too leniently when it cannot verify factual claims against live data

### Limitations
- The Critic cannot independently verify tool call results (it sees the formatted output, not the raw tool responses)
- Self-evaluation bias: both Planner and Critic use the same model family, which may create blind spots common to Gemini
- Score calibration has not been validated against human raters; the 0.75 threshold is empirical

### Ethical Considerations
- Critic feedback is stored in the Task record and visible to the task owner
- The Critic prompt instructs it to be specific and constructive — not to assign blame to the user
- Scores and feedback are not used for any purpose beyond pipeline routing

---

## General Ethical Considerations

**Prompt injection:** Guardrails (`app/core/guardrails.py`) validate task descriptions before any LLM call, blocking known injection patterns.

**Data retention:** Task descriptions, plans, execution results, and Critic scores are stored in the database. Users can delete their tasks via `DELETE /api/tasks/{id}`. ChromaDB vector embeddings are stored separately and not currently exposed for deletion.

**Bias:** The platform amplifies whatever biases exist in the underlying models (Gemini, Llama 3.1). Tasks involving sensitive categories (health, legal, financial advice) should include appropriate disclaimers in the system prompts.

**Misuse:** The rate limiter (10 tasks/hour per user) limits abuse. E2B sandboxing prevents code execution from affecting the host system.
