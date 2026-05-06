# Exhaustive Code Flow & Function Reference

This document provides a comprehensive map of every function call and data transformation in the portfolio application, from boot-up to interactive verification.

---

## 1. High-Level Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant A as app.py
    participant D as agent_dispatch.py
    participant AG as Agent (RLM/Vector/File)
    participant E as Engines (Trace/Vector)
    participant G as Google Gemini API
    participant S as state.py
    participant R as chat_renderer.py
    participant WI as workflow_intelligence.py
    participant WDB as workflow_db.py

    Note over A,E: Phase 0: Initialization
    A->>E: load_corpus()
    A->>S: init_session_state()
    A->>WDB: init_db()
    A->>A: Inject APP_CSS
    
    U->>A: st.chat_input("Prompt")
    A->>S: st.session_state.messages.append(UserMsg)
    A->>A: st.rerun()
    
    rect rgb(240, 240, 240)
        Note over A,R: Phase 1-5: The Generation Loop
        A->>D: generate_answer / check_and_set_checkpoint
        
        opt IF checkpoint_enabled (Thinking Mode)
            D->>Ckpt: should_checkpoint(client, prompt)
            alt Checkpoint Needed
                D->>S: pending_checkpoint = data
                S->>A: st.rerun()
                A->>R: show checkpoint card (wait for user)
                U->>R: Continue (confirm/edit) / Start Over
                R->>D: resume_from_checkpoint()
                D->>Ckpt: build_resume_prompt()
            end
        end

        D->>AG: agent.completion(prompt)
        
        alt RLM Mode
            loop Reasoning Loop
                AG->>G: _send(next_user_msg)
                G-->>AG: Response with ```repl```
                AG->>AG: find_code_blocks()
                AG->>E: execute_sandbox_code(code)
                E-->>AG: REPLResult (stdout, stderr)
            end
        else Vector RAG Mode
            AG->>E: VectorEngine.search(query)
            E->>E: get_embedding(query)
            E-->>AG: top-k chunks + distances
        end
        
        AG-->>D: response_text, token_stats
        
        opt IF Verify Enabled
            D->>E: find_maximal_matches(text, docs)
            E-->>D: traced_html
        end

        Note over D,WDB: Phase 6.5: Workflow Intelligence
        D->>WI: detect_concern(client, prompt_text)
        WI->>G: generate_content (Gemini, JSON mode)
        G-->>WI: concern JSON + tokens
        WI-->>D: concern_data, concern_tokens
        D->>S: turn_tokens += concern_tokens
        alt is_concern == true
            D->>S: session_state.pending_concern = concern_data
        end
        
        D->>S: append_response(text, html, debug, {"total": turn_tokens})
        S->>A: st.rerun()
    end

    A->>R: render_chat_history()
    R->>R: st_click_detector(traced_html)
    opt pending_concern set
        R-->>U: Consent UI form
        U->>R: Submit / Submit Anonymously / Discard
        R->>WDB: insert_concern(concern_data, quote)
        R->>S: pending_concern = None + st.rerun()
    end
    R-->>U: Final UI Bubble
```

---

## Phase 0: Initialization & Boot
**File:** [app.py](file:///c:/Users/khuon/portfolio/app.py)

1.  **`load_corpus(data_dir)`** ([trace_engine.py](file:///c:/Users/khuon/portfolio/engines/trace_engine.py)): Walks the `data/` directory, reads `.md`, `.txt`, `.pdf`, and `.docx` files into a persistent dictionary.
2.  **`get_cached_corpus()`**: Wraps the loader in `@st.cache_data` to prevent disk thrashing on every rerun.
3.  **`init_session_state()`** ([state.py](file:///c:/Users/khuon/portfolio/state.py)): Ensures `messages`, `debug_log`, `clicked_states`, and `view_doc` keys exist in Streamlit memory.
4.  **`render_sidebar()`** ([sidebar.py](file:///c:/Users/khuon/portfolio/utils/sidebar.py)): Paints the profile card and social links.
5.  **`APP_CSS` Injection** ([styles.py](file:///c:/Users/khuon/portfolio/styles.py)): Injects custom CSS via `st.markdown(APP_CSS, unsafe_allow_html=True)`.

## Phase 1: User Input
1.  **`st.chat_input()`**: Captures the string.
2.  **`log_event(msg)`** ([state.py](file:///c:/Users/khuon/portfolio/state.py)): Adds a timestamped entry to the console and internal log.
3.  **`messages.append()`**: Stores the user turn.
4.  **`st.rerun()`**: Triggers a fresh execution of the script.

## Phase 2: Orchestration (Agent Dispatch)
**File:** [agent_dispatch.py](file:///c:/Users/khuon/portfolio/components/agent_dispatch.py)

1.  **`generate_answer(...)`**: The main entry point for AI logic.
2.  **`_make_logger(status, steps_log)`**: A closure that redirects agent logs to the `st.status` widget for real-time "thinking" updates.
3.  **Document Sandboxing**: Filters `docs` to exclude `summaries/` for RLM and Vector modes.
4.  **Strategy Selection**: Instantiates `RLMAgent`, `VectorRAGAgent`, or `FileBasedAgent`.

## Phase 3: Reasoning (Agent Layer)

### Recursive Language Model (RLM)
**File:** [rlm_agent.py](file:///c:/Users/khuon/portfolio/agents/rlm/rlm_agent.py)
*   **`completion(user_query)`**: The iterative loop.
*   **`_send(next_user_msg)`**: Manages the `client.chats.create` and `chat.send_message` calls to Gemini.
*   **`find_code_blocks(text)`**: Regex-based extraction of ```repl``` segments.
*   **`execute_code(code)`**: Wrapper around **`execute_sandbox_code`** ([base.py](file:///c:/Users/khuon/portfolio/agents/rlm/base.py)), which uses a restricted `__builtins__` dictionary to run code safely via Python's `exec()`.
*   **`find_final_answer(text)`**: Looks for the `FINAL(...)` trigger to break the loop.
*   **`llm_query_callback(prompt)`**: Exposed to the LLM's Python REPL to allow sub-questions.

### Vector RAG
**File:** [vector_store.py](file:///c:/Users/khuon/portfolio/agents/vector/vector_store.py)
*   **`VectorEngine.search(query)`**: Orchestrates the semantic lookup.
*   **`is_stale(docs)`**: Compares current files against **`_corpus_fingerprint`** to see if a rebuild is needed.
*   **`chunk_text(text)`**: Splits documents using a sliding window with overlap.
*   **`get_embedding(text)`**: Calls Gemini Embedding API with automatic **429 Rate Limit** retry logic (`retryDelay` parsing).
*   **`build_index(docs)`**: Clears ChromaDB and re-populates it with new embeddings.

### File-Based Context
**File:** [file_based_agent.py](file:///c:/Users/khuon/portfolio/agents/file_based/file_based_agent.py)
*   **`completion(...)`**: Implements both "Fast" and "Router" modes.
*   **Router Logic**: Performs an initial LLM call to identify relevant files from the corpus using small previews, then loads the full text of only those selected files. Router token usage is aggregated into the total turn cost.
*   **JSON Parsing**: Extracts filenames from LLM output using `re.search(r'\[.*\]', ...)` to parse JSON.

## Phase 4: Verification (Trace Engine)
**File:** [trace_engine.py](file:///c:/Users/khuon/portfolio/engines/trace_engine.py)

1.  **`find_maximal_matches(response, corpus)`**: The core verification algorithm.
    *   Iterates through every character of the response.
    *   Uses a greedy search to find the longest verbatim match (min 15 chars) in any document.
    *   Escapes HTML special characters via `html.escape()`.
    *   Wraps matches in clickable `<a>` tags with a `filename:::phrase` payload.

## Phase 5: State Persistence
1.  **`st.session_state.turn_tokens`**: A global accumulator that sums tokens from the Checkpoint Engine, the Agent (including sub-calls), and Workflow Intelligence.
2.  **`append_response(content, html, ...)`** ([state.py](file:///c:/Users/khuon/portfolio/state.py)): Saves the assistant's turn, including the **Total Lifecycle Token Cost**.
3.  **`st.rerun()`**: Triggers the final rendering pass.

## Phase 6: Rendering & Interaction
**File:** [chat_renderer.py](file:///c:/Users/khuon/portfolio/components/chat_renderer.py)

1.  **`render_chat_history()`**: Iterates over `st.session_state.messages`.
2.  **`st_click_detector()`**: Renders the `traced_html` and captures user clicks on highlighted phrases.
3.  **`render_document_viewer(docs)`**: Displays the source document in a 2nd column if `st.session_state.view_doc` is active.
    *   Calculates a **Context Snippet** (±1000 chars around the match).
    *   Injects a CSS-styled `<span>` to highlight the specific phrase within the document.

## Phase 6.5: Workflow Intelligence
**Files:** [workflow_intelligence.py](file:///c:/Users/khuon/portfolio/components/workflow_intelligence.py) · [workflow_db.py](file:///c:/Users/khuon/portfolio/utils/workflow_db.py)

After the agent produces its answer but **before** `append_response` triggers a rerun, the dispatch layer runs a lightweight LLM classifier on the *user's message* (not the answer).

1.  **`detect_concern(client, message_text)`** ([workflow_intelligence.py](file:///c:/Users/khuon/portfolio/components/workflow_intelligence.py)):
    *   Loads `data/portfolio_capabilities.md` as ground truth so the classifier can distinguish *existing* features from *missing* ones.
    *   Sends a structured prompt to Gemini (using `_generate_content_with_fallback` with retry + model fallback).
    *   Returns a concern dict with keys: `is_concern`, `category`, `workflow_stage`, `affected_role`, `root_cause`, `tool_match`, `analysis`.
    *   **Non-blocking**: any exception returns `{"is_concern": False}` so the chat is never affected.
2.  **`pending_concern` session state flag**: Set in `agent_dispatch.py` if `is_concern == True`; cleared to `None` if not, so stale concerns from previous turns never leak.
3.  **Consent UI** ([chat_renderer.py](file:///c:/Users/khuon/portfolio/components/chat_renderer.py)):
    *   Rendered at the bottom of `render_chat_history()` whenever `pending_concern` is set.
    *   Options: Submit, Submit Anonymously, Do not submit.
    *   On submit → calls `insert_concern()` and rewrites the last assistant message to confirm the action.
4.  **`insert_concern(concern_data, quote)`** ([workflow_db.py](file:///c:/Users/khuon/portfolio/utils/workflow_db.py)):
    *   Persists to the `feedback_concerns` SQLite table with status `unresolved`.

### Admin Review Dashboard
**File:** [feedback_dashboard.py](file:///c:/Users/khuon/portfolio/pages/feedback_dashboard.py)

Gated behind Admin login. Provides four tabs:

| Tab | Purpose |
|---|---|
| Unresolved Concerns | Triage view grouped by category. Per-concern checkboxes, Mark Solved, and Discard (with optional reason). |
| Backlog Candidates | AI-generated structured tickets drafted from selected concerns via `generate_backlog_candidate()`. |
| Metrics | Live counts of Total / Unresolved / Solved / Discarded / In Backlog concerns. |
| Audit Log | Chronological feed of every status transition with timestamp, note, and source quote. |

Status lifecycle: `unresolved` → `solved` | `discarded` | `accepted_to_backlog`

---

## Function Directory

| Layer | Function | File | Description |
|---|---|---|---|
| **Entry** | `st.chat_input` | `app.py` | Captures user prompt. |
| **Orch** | `generate_answer` | `agent_dispatch.py` | Strategy router for agents. |
| **Orch** | `_make_logger` | `agent_dispatch.py` | Closure for routing logs to `st.status`. |
| **Reason** | `agent.completion` | `agents/*_agent.py` | Main AI logic entry point. |
| **Logic** | `execute_sandbox_code`| `agents/rlm/base.py` | Securely runs model-generated Python. |
| **Logic** | `build_corpus` | `agents/rlm/base.py` | Bundles documents into a searchable string. |
| **Logic** | `format_execution_result`| `agents/rlm/base.py` | Formats REPL output for the model. |
| **Logic** | `VectorEngine.search` | `agents/vector/vector_store.py`| Semantic search via ChromaDB. |
| **Logic** | `get_embedding` | `agents/vector/vector_store.py`| API call with rate-limit retries. |
| **Logic** | `_corpus_fingerprint` | `agents/vector/vector_store.py`| Stable ID for index invalidation. |
| **Logic** | `chunk_text` | `agents/vector/vector_store.py`| Sliding window document segmentation. |
| **Logic** | `llm_query_batched` | `agents/rlm/rlm_agent.py` | Sequential fan-out for sub-queries. |
| **Service**| `find_maximal_matches`| `engines/trace_engine.py` | Verbatim text tracing algorithm. |
| **Service**| `load_corpus` | `engines/trace_engine.py` | Multi-format local file ingestor. |
| **State** | `append_response` | `state.py` | Persists AI message to history. |
| **State** | `log_event` | `state.py` | Timestamped event logging. |
| **UI** | `st_click_detector` | `components/chat_renderer.py`| Handles verification clicks. |
| **UI** | `render_document_viewer`| `components/chat_renderer.py`| Shows source file + highlight snippet. |
| **WI** | `detect_concern` | `components/workflow_intelligence.py`| Classifies user message into concern type. |
| **WI** | `generate_backlog_candidate`| `components/workflow_intelligence.py`| Drafts structured backlog ticket from concerns. |
| **WI** | `_generate_content_with_fallback`| `components/workflow_intelligence.py`| Gemini call with 503 retry + model fallback. |
| **WI** | `_load_capabilities` | `components/workflow_intelligence.py`| Loads portfolio UI ground truth for classifier. |
| **WI** | `insert_concern` | `utils/workflow_db.py` | Persists a new concern to SQLite. |
| **WI** | `mark_concern_resolved`| `utils/workflow_db.py` | Sets status to `solved` and logs action. |
| **WI** | `discard_concern` | `utils/workflow_db.py` | Sets status to `discarded` with reason. |
| **WI** | `mark_concern_accepted`| `utils/workflow_db.py` | Links concern to a backlog candidate. |
| **WI** | `insert_backlog_candidate`| `utils/workflow_db.py` | Persists AI-drafted backlog ticket. |
| **WI** | `log_activity` | `utils/workflow_db.py` | Writes action to immutable audit log. |
| **WI** | `get_activity_log` | `utils/workflow_db.py` | Retrieves audit log joined with concern data. |
| **WI** | `init_db` | `utils/workflow_db.py` | Creates all 3 WI tables on first boot. |
| **Ckpt**| `should_checkpoint`| `components/checkpoint_engine.py`| Classifies if message needs a checkpoint pause. |
| **Ckpt**| `build_resume_prompt`| `components/checkpoint_engine.py`| Enriches prompt with user checkpoint decision. |
| **Ckpt**| `check_and_set_checkpoint`| `components/agent_dispatch.py` | Orchestrates pre-generation checkpoint gating. |
| **Ckpt**| `resume_from_checkpoint`| `components/agent_dispatch.py` | Orchestrates resumption from a user decision. |
| **Ckpt**| `_render_checkpoint_card`| `components/chat_renderer.py`  | Renders interactive UI for pending checkpoints. |
