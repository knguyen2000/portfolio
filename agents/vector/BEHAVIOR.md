# Vector RAG Behavior Analysis

This document analyzes the performance, failures, and evolution of the Vector RAG system in this portfolio. It tracks how the system handles API limits, semantic retrieval gaps, and UX challenges.

---

## Trace 1 — Bulk Indexing & Quota Exhaustion (429)

### Problem
During the first full rebuild of the index (approx. 274 chunks), the system hit the Gemini embedding API's free-tier limit of 100 requests per minute. The original code would fail fast, leading to an incomplete index and a wall of error messages.

### Fixed
We implemented an retry mechanism in `VectorEngine.get_embedding()`:
- **`retryDelay` Parsing**: The engine now reads the exact window-reset time provided by the Google API (e.g., "Wait 33s") using regex.
- **Buffer & Backoff**: Adds a +2s safety buffer to avoid hitting the microsecond boundary of the quota reset.
- **Thinking Process Integration**: Sleep messages are now piped to the UI status widget so the user knows why the app is "frozen."

### Finding
A "Burst and Chill" strategy is superior to a constant 0.6s delay. It utilizes the full burst capability of the API immediately and only pauses when necessary, making the overall rebuild time ~2x faster than a naive rate-limiter.

---

## Trace 2 — The "College" False Negative

**Query:** "where he went to for college" | **Outcome:** Failed (initially)

### The Problem
Despite the answer ("University of Virginia" and "Hame University") being clearly present in `my_life.txt`, the RAG agent returned *"I couldn't find any information."* 

Analysis revealed a **Semantic Gap**:
- The mathematical "distance" for the query was **0.91**.
- The system had a hard "Rejection Threshold" at **0.85**. 
- Because 0.91 > 0.85, the system threw the answer away before the LLM even saw it.

### Fixed: "Confidence-Aware UX"
We removed the hard threshold. The system now passes *all* top neighbors to the LLM but flags them with a **Match Quality %**.
- If the best quality is low (e.g., < 35%), the UI prefixes the answer with a **Low Confidence Warning**.
- This relies on the LLM's superior ability to "filter noise" compared to simple vector distance math.

---

## Trace 3 — ChromaDB Immutability Bug

### Problem
A rebuild attempt failed with: *"Changing the distance function of a collection once it is created is not supported."*

### Analysis
This happened because `collection.modify()` was being called with the full metadata dictionary, including `{"hnsw:space": "cosine"}`. Even though it wasn't changing the value, ChromaDB's safety checks interpreted any mention of a distance metric in an update call as a forbidden change attempt.

### Fixed
The `build_index` logic was updated to omit the `hnsw:space` key from the metadata update, only passing the `corpus_fingerprint`.

---

## Findings

### 1. Distance translates poorly to Human Intent
A distance of 0.9 seems "bad" mathematically, but for a high-reasoning model like Gemini, it's often more than enough to find a needle in a haystack. We have shifted the philosophy from **"Rejecting poor matches"** to **"Reporting all matches with a confidence warning."**

### 2. The Cost of "Nuclear" Rebuilds
Currently, modifying a single character in `data/` triggers a delete-and-rebuild of every file. While robust, it puts unnecessary pressure on the API quota. 

---

## TODO

### 1. Multi-Step Query Expansion
If a Vector search returns very low confidence (< 15%), trigger a "HyDE" (Hypothetical Document Embeddings) step where the LLM writes a fake answer first, and we search using that fake answer to find better semantic neighbors.

### 2. Search Result Reranking
Implement a lightweight "Cross-Encoder" pass after retrieval to re-sort the top 5 chunks. Vector distance is fast but "blunt"; a small model can perform a high-precision check to see which of the 5 chunks is best before passing them to the main LLM.

### 3. Incremental Indexing
Rebuilding the entire vector index (deleting the collection and re-embedding every file) on every content change is inefficient and hits API rate limits.
- **Fix**: Implement a per-file hashing check in `VectorEngine.build_index` to only re-embed files that have actually changed since the last build.
