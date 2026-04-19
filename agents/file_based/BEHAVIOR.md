# File-Based Behavior Analysis

This document analyzes the real-world performance of the File-Based agent, focusing on routing accuracy and the challenges of multi-perspective synthesis.

---

## Trace 1 — Pronoun Leakage (Person Mismatch)

**Outcome:** Observed Deficiency

### The Problem
When answering questions about the owner's biography, the agent sometimes produces mixed-perspective sentences:
> *"Khuong moved to Finland for **my** bachelor’s degree... taught **me**..."*

### Analysis
This happens because the source files (e.g., `my_life.txt`) are written in the first person ("I", "my"). While the agent is prompted to be a "professional assistant," it occasionally "leaks" the input pronouns into its synthesis. This is a common failure mode when the LLM extracts verbatim context but fails to re-write descriptors for a third-party audience.

### TODO
Refine the system prompt in `file_based_agent.py` to add a persona constraint: *"Always refer to the portfolio owner in the third person (Khuong, he, him) and never use first-person pronouns (I, me, my)."*

---

## Trace 2 — High-Precision Routing

**Query:** "Has he been to Hungary?" | **Outcome:** Success

### Observation
The Router correctly identified that only `my_life.txt` was relevant to this specific geopolitical trivia. It ignored larger summaries like `how_it_works.txt` or `README.md`.

### Finding
The **Router Mode** (Verify ON) is significantly more reliable than the **Vector Agent** for "needle-in-a-haystack" questions. While Vector RAG looks for semantic similarity, the LLM Librarian (File-Based Router) looks for **logical categorical matches**, making it better at identifying the single correct document for a specific fact.

---

## Trace 3 — Token Quota Pressure

**Outcome:** Performance Constraint

### Observation
A single "Fast Mode" query consumed **7,084 tokens**. 
- Free Tier Limit: 15,000 tokens per minute.
- Impact: A user asking two questions in 60 seconds would trigger a rate-limit crash.

### Finding
In the context of the free-tier Gemini API, **Routing is a survival mechanism.** Every file filtered out by the Librarian isn't just a win for accuracy—it’s a direct saving of the "token budget" required to keep the app operational for multiple users.

---

## TODO

### 1. Auto-Summary Generation
Currently, the agent relies on pre-generated summaries in `data/summaries/`. If a new file is added to root `data/` without a corresponding summary, the agent cannot see it in Router mode.
- **Goal**: Implement a "Just-In-Time" summarizer that creates these files if they are missing.

### 2. Pronoun Normalization
(See Trace 1) Force third-person output via prompt engineering.
