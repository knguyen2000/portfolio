# Vector RAG Design & Implementation Analysis

This document is a technical deep-dive into the Vector-based Retrieval-Augmented Generation (RAG) agent as implemented in this portfolio. It covers the storage architecture, embedding strategy, and the "Confidence-Aware" retrieval logic that powers the fast, semantic search capabilities.

---

## Files Structure

Contains the agent logic and core engine for Vector-based retrieval.
- **`vector_agent.py`**: The primary agent class. It manages the lifecycle of a query: checking for data freshness, triggering rebuilds, and synthesizing the final answer.
- **`vector_store.py`**: Home of the **`VectorEngine`**. This class encapsulates all ChromaDB and Gemini API interactions (persistence, chunking, embedding).

---

## 1. Core Idea

The Vector RAG system provides "Point-and-Shoot" semantic search. Unlike the **RLM Agent** (which navigates through code and recursion), the Vector Agent relies on pre-computed mathematical embeddings to find relevant information in a single shot.

This makes the Vector RAG:
- **Fast**: Retrieval happens in milliseconds once the index is built.
- **Cheap**: It uses significantly fewer tokens than the iterative RLM loop.
- **Intuitive**: It handles "synonym" queries (e.g., "university" matching "college") without needing explicit keyword logic.

---

## 2. The Vector Agent Logic (`vector_agent.py`)

The Agent acts as the orchestrator for the retrieval lifecycle.

### The Lifecycle of a Query
1. **Freshness Check**: Before every query, the Agent triggers `is_stale()` to ensure the on-disk files haven't drifted from the database.
2. **Context Synthesis**: It maps raw distance scores to human-readable percentages and "weights" the context chunks with these scores before passing them to the LLM.
3. **Safety Monitoring**: It monitors the overall match quality and injects UI-level warnings for low-confidence results.

---

## 3. The Vector Store Engine (`vector_store.py`)

Heavy-lifting component that encapsulates all database and embedding logic. It is designed for reliability

### A. The Chunking Pipeline
Instead of naive character splitting, the engine uses a **sliding window (1000 size / 200 overlap)** with a **Lookback Heuristic**:
- **Smart Splits**: If the window cuts a word in half, the engine looks back up to 50 characters to find the nearest space.
- **Impact**: This preserves word integrity and prevents semantic noise (e.g., "Khuo" and "ng" being split into different vectors).

### B. Embedding & Rate Limiting ("Burst and Chill")
The Gemini Free Tier is limited to 100 Embedding Requests per Minute. 
- **Deterministic IDs**: Every chunk ID is an MD5 hash of `filename_chunkIndex`. This ensures that even if a build fails and restarts, the IDs remain stable and unique.
- **Burst-Aware Retries**: A Regex parser extracts `retryDelay` directly from the API's `RESOURCE_EXHAUSTED` error. The engine sleeps for the exact duration requested (plus a 2-second safety buffer), allowing it to max out credit bursts without getting into a ban-loop.
- **Partial-Rebuild Rejection**: The engine tracks `total_chunks_expected`. If the build is interrupted, the **Corpus Fingerprint** is NOT stamped. The index remains "Stale" until a 100% successful pass occurs.

### C. Tradeoffs

| Feature | Design Choice | Tradeoff |
|---|---|---|
| **Storage** | ChromaDB PersistentClient (Local) | **Pros**: No cloud costs, low latency, privacy. **Cons**: No horizontal scaling; restricted to the web server's local disk volume. |
| **Indexing** | Sequential "Nuclear" Rebuild | **Pros**: Guaranteed consistency (no "ghost chunks" from deleted files). **Cons**: High API quota usage on large corpora. (Future: Incremental updates). |
| **Math** | Cosine Similarity | **Pros**: Focuses on semantic direction. **Cons**: More computationally expensive than Euclidean distance, though negligible at portfolio scales. |
| **Logic** | Blocking Wait on 429s | **Pros**: Simple code, easy to debug in Streamlit's synchronous model. **Cons**: Stalls the UI if a large rebuild is triggered while a user is waiting. |

---

## 4. Confidence-Aware Retrieval

### The Shift from Hard Thresholds
Early versions used a hard mathematical "Distance Threshold" (0.85) to discard "unrelated" data. However, real-world testing (the "College Query" case) proved that human language is too messy for a single cutoff.

The current design uses a **"Soft Threshold"** approach:
1. **Quality Mapping**: Technical cosine distances (0.0 to 1.0) are mapped to a human-readable **Match Quality %** (0% to 100%).
2. **Inclusive Retrieval**: We pass all $k=5$ top neighbors to the LLM, regardless of score. We trust the LLM’s reasoning to filter out noise while benefiting from "near-miss" segments that contain the answer.
3. **Disclosure**: The agent injects the `Match Quality` of each chunk directly into the LLM context (e.g., `[Source: about.md, Match Quality: 85%]`), helping the model "weigh" which evidence to trust during synthesis.

### UI Safety Guards
If the "Best Overall Quality" for a query is below **35%**, the agent automatically prefixes its response with a disclaimer:
> *(Note: I found some information that might be related, but my confidence is low. Please verify these details.)*

---

## 5. Summary Table

| Decision | Choice Made | Tradeoff |
|---|---|---|
| **Similarity Metric** | Cosine (`hnsw:space: cosine`) | Better for semantic meaning; slightly slower than Euclidean math. |
| **Chunking** | 1000 chars / 200 overlap | Good "context window"; includes a 50-char lookback heuristic to avoid splitting words in half. |
| **Persistence** | PersistentClient (Local Disk) | Faster than cloud DBs; requires persistent volume in deployment. |
| **Indexing IDs** | Deterministic (MD5) | We use MD5 of `filename_index` for chunk IDs. This ensures consistency across rebuilds and prevents ID bloat. |
| **Integrity** | Partial-Index Guard | Fingerprints are only stamped if the count of embedded chunks exactly matches the expected count. |
| **Confidence Logic** | Match Quality % + Cautions | Higher recall; uses `max(0, int((1.0 - dist) * 100))` to turn math into human intuition. |
| **Updating** | Nuclear Rebuild | Zero chance of "ghost chunks"; uses 50-chunk batch upserts for stability. |
