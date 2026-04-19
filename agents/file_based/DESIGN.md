# File-Based Agent Design & Implementation Analysis

This document analyzes the File-Based retrieval system as implemented in this portfolio. This agent occupies the middle ground between **Vector Search** (fast but mathematically opaque) and **RLM** (deep but token-expensive). It operates as an "LLM Librarian" that manages a curated collection of document summaries.

---

## Files Structure

### `/agents/file_based`
- **`file_based_agent.py`**: The core logic. It handles the two-pass "Router" flow and the one-shot context construction.

### `/data/summaries`
- This is the source of truth for the File-Based agent. By operating on LLM-pre-generated summaries rather than raw files, the agent can consider the entire corpus at once while staying within context limits.

---

## 1. Core Idea

The mental model for this agent is a **Librarian**. When you ask a question:
1. It looks at the titles and high-level summaries of all available books (files).
2. It picks only the books it thinks are relevant.
3. It opens those specific books and synthesizes an answer.

This differs from **Vector RAG** because it doesn't use vector distance; it uses **LLM reasoning** to pick files. This is often more resilient to nuances that vector math might miss (e.g., recognizing that "The UVA project" is relevant to a "college" query based on summary text).

---

## 2. Dual-Mode Architecture

The agent supports two operational modes controlled by the `verify_enabled` flag (toggled by the "Verify" switch in the UI).

### Fast Mode (Verify OFF)
In Fast Mode, the agent skips the librarian step. It dumps every file in `data/summaries/` into the context window one-shot. 
- **Benefit**: Minimum latency (one LLM call).
- **Tradeoff**: Token expensive if the summaries are large; risks "Lost in the Middle" errors if the corpus grows.

### Router Mode (Verify ON)
In Router Mode, the agent performs a two-pass operation:
1. **The Router Pass**: It constructs a lightweight "Doc Index" of every file. To save space, it uses a **Head/Mid/Tail** preview heuristic (grabbing the first, middle, and last 600 characters of each summary).
2. **The Decision**: A dedicated prompt asks the LLM to return a JSON list of relevant filenames.
3. **The Synthesis Pass**: Only the selected files are loaded into the final context for the answer generation.

---

## 3. Instructional Design

### Verbatim Extraction Constraint
The system prompt contains a strict instruction:
> *"You MUST use exact, verbatim phrases from the Knowledge Base to support your claims."*

This is a **structural design choice** meant to synergize with the portfolio's UI. By forcing the LLM to use verbatim text without bolding or styling it, the frontend can perform a simple substring match to highlight the retrieved evidence in the "Sources" viewer automatically.

### Groundedness over Paraphrasing
Temperature is set to `0` to ensure that the agent stays grounded in the summary text. This prevents the "creative drift" that often happens in informational portfolios.

---

## 4. Summary of Tradeoffs

| Decision | Choice Made | Tradeoff |
|---|---|---|
| **Context Source** | `/data/summaries` | Higher quality/density info; requires developer to maintain a separate summary directory. |
| **Routing Logic** | LLM-based JSON selection | Much higher accuracy than vector search; adds significant latency (~5s+) in Verify mode. |
| **Doc Preview** | Head/Mid/Tail slicing | Allows indexing of dozens of files without context limit; might miss a keyword in the "sliced" gaps. |
| **Highlighting** | Verbatim constraint | Enables automated high-accuracy UI highlighting; makes the agent's prose slightly more "staccato." |
| **Token Cost** | Highest (One-shot) | Reliable for small corpora; needs the Router Pass to scale to larger datasets. |
