# Welcome to my portfolio

It is a **Streamlit web application**. Its "database" is a folder of `.md` and `.txt` files in `data/`. The server is Streamlit, which re-runs the whole Python script on every user interaction.

**Tech stack:** Python 3.11+, Streamlit, Google GenAI SDK (Gemini / Gemma), ChromaDB (vector store), PyDeck (3D map), Pillow (images), PyPDF2 / python-docx (document ingestion).

---

## 1. Architecture

```
                        ┌──────────────────────────┐
                        │        Browser (UI)      │
                        └────────────┬─────────────┘
                                     │ HTTP / WebSocket
                                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                         STREAMLIT RUNTIME                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    app.py  (entry point)                   │  │
│  │       +  pages/about.py  pages/projects.py  pages/gallery  │  │
│  └──────────────┬─────────────────────────────────────────────┘  │
│                 │                                                │
│  ┌──────────────▼──────────────┐    ┌──────────────────────────┐ │
│  │  components/                │    │  utils/                  │ │
│  │    agent_dispatch.py  ◄─────┼────┤    sidebar.py            │ │
│  │    chat_renderer.py         │    │    video_modal.py        │ │
│  └──────┬──────────────────────┘    └──────────────────────────┘ │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────┐   ┌──────────────────────────┐ │
│  │  agents/                     │   │  engines/                │ │
│  │    rlm/        RLMAgent      │   │    trace_engine.py       │ │
│  │    vector/     VectorRAGAgent│   │                          │ │
│  │    file_based/ FileBasedAgent│   │                          │ │
│  └──────┬───────────────────────┘   └──────────────┬───────────┘ │
│         │                                          │             │
│         │           ┌──────────────────────────┐   │             │
│         │           │  state.py   styles.py    │   │             │
│         │           │  (session + CSS)         │   │             │
│         │           └──────────────────────────┘   │             │
└─────────┼──────────────────────────────────────────┼─────────────┘
          │                                          │
          ▼                                          ▼
┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐
│ Google Gemini   │  │  ChromaDB       │  │  data/             │
│   (LLM + embed) │  │  (vector store) │  │  ("content DB")    │
└─────────────────┘  └─────────────────┘  └────────────────────┘
```

The project follows a **five-layer architecture**.

### 1.1 Presentation Layer — `app.py`, `pages/`, `styles.py`

**Responsibility:** Turn Python state into HTML and handle user events.

This layer contains **no reasoning logic**. It only calls dispatchers and renders what comes back. This is good: I can rewrite the whole UI without touching intelligence.

### 1.2 Orchestration Layer — `components/`

**Responsibility:** Decide *which* agent handles a request and *how* to render the result.

This is the "traffic controller". It reads the selected mode, prepares the context, calls the right agent, and attaches metadata (token usage, debug trace, source highlights) to the response. After the recent refactor all three modes now go through the same shape: `agent = SomeAgent(...); text, tokens = agent.completion(prompt)`. The dispatcher is tiny because the agents are uniform.

### 1.3 Reasoning Layer — `agents/`

**Responsibility:** Produce an answer given a question and a corpus. Three sibling agent classes, each in its own sub-folder:

- **`agents/rlm/`** — `RLMAgent`. Iterative loop (max 10 steps). The model writes Python inside ```repl``` blocks that run in a sandboxed REPL with `context`, `llm_query`, and `llm_query_batched` pre-injected. It finishes by emitting `FINAL(answer)` or `FINAL_VAR(variable)` at the start of a line. This mirrors the reference RLM implementation.
- **`agents/vector/`** — `VectorRAGAgent` + `VectorEngine`. Embeds chunks with Gemini's embedding model, stores them in ChromaDB, retrieves top-k on each query. Has a **corpus fingerprint** (MD5 of model ID + sorted filenames/sizes) so the index invalidates itself when I edit a source file. Maps cosine distance to a "match quality %" and warns the user when confidence is low.
- **`agents/file_based/`** — `FileBasedAgent`. Two modes: Fast (dump all summaries, one call) and Router (first call selects relevant files from Head/Mid/Tail previews, second call answers). Designed for short, factual questions.

Each folder ships with a `DESIGN.md` (why it is shaped this way) and a `BEHAVIOR.md` (real execution traces + known bugs). I treat those as the source of truth for each agent's quirks.

### 1.4 Service Layer — `engines/`, `utils/`

**Responsibility:** Reusable, stateless services.

- **`engines/trace_engine.py`** — `load_corpus(data_dir)` reads `.txt`/`.md`/`.pdf`/`.docx` into a `{path: content}` dict. `find_maximal_matches(response, corpus)` is a greedy maximal-exact-match scanner that wraps every verbatim phrase (≥15 chars) in the model's answer with a clickable HTML anchor. This is what makes the "click a sentence to see its source" UI work.
- **`utils/sidebar.py`** — profile card + nav links.
- **`utils/video_modal.py`** — fullscreen video overlay CSS.

These modules do not know *why* they are being called. They take inputs and return outputs. This is the most reusable tier: if I ever rewrite the frontend in Next.js, these modules could move to a backend API unchanged.

### 1.5 Data Layer — `data/`, `config/`, `static/`

**Responsibility:** Raw content and configuration.

- **`data/projects/*.md`** — one Markdown file per project. The projects page auto-discovers them.
- **`data/summaries/*.txt`** — hand-written summaries of the root files, used by File-Based Router mode to save tokens.
- **`config/app_config.py`** — `MODEL_ID`, `EMBEDDING_MODEL_ID`, token warning threshold, mode list.
- **`config/profile.py`** — name, headline, social links.
- **`config/about_data.py`** — map coordinates + journey chapters for the About page.

Content (Markdown files) and configuration (Python constants) are deliberately kept separate from code. This turns `data/` into a **headless CMS** — add a file, the app picks it up.

---

## 2. The Life of a Request — End-to-End Trace

Here is what happens when a user types *"What projects has Khuong worked on?"* and presses Enter.

```
[1] User types in st.chat_input()
        │
        ▼
[2] app.py main loop receives the prompt
    └── appends {role: "user", content: ...} to session_state.messages
    └── calls components.agent_dispatch.generate_answer(...)
        │
        ▼
[3] agent_dispatch.py picks the agent class for the selected mode
    ┌─────────────────────┬─────────────────────┬─────────────────────┐
    │     RLM mode        │   Vector RAG mode   │   File-Based mode   │
    ├─────────────────────┼─────────────────────┼─────────────────────┤
    │ RLMAgent()          │ VectorRAGAgent()    │ FileBasedAgent()    │
    │ .completion(q)      │ .completion(q)      │ .completion(q)      │
    │  → repl loop        │  → embed + top-k    │  → route + answer   │
    └─────────────────────┴─────────────────────┴─────────────────────┘
        │
        ▼
[4] Google Gemini API called (network hop; RLM may loop here up to 10 times)
    └── returns response text + usage_metadata (tokens)
        │
        ▼
[5] If "verify" is ON:
    └── engines.trace_engine.find_maximal_matches(response, corpus)
        └── scans text char-by-char, wraps every substring ≥15 chars
            that appears verbatim in corpus with <a class='verbatim-match'>
        │
        ▼
[6] state.append_response(content, html_content, debug_steps, tokens)
    └── calls st.rerun() → Streamlit re-executes the whole script
        │
        ▼
[7] On rerun, chat_renderer.render_chat_history() redraws bubbles
    └── st_click_detector wraps the HTML — clicks are captured
        │
        ▼
[8] If the user clicks a highlighted phrase:
    └── session_state.view_doc = source filename
    └── st.rerun() → right panel shows the original file with phrase highlighted
```

**Note:** In step 6, Streamlit's execution model re-runs the script **from the top** on every interaction. There is no long-lived server object for this session. The only thing that survives between runs is `st.session_state`. This has consequences:

- Any expensive work must be cached (`@st.cache_data`) or gated behind `if not already_done`.
- "Global variables" do not exist in the usual sense; state must be carried through `session_state`.
- Debugging is easier (state is just a dict) but performance tuning is harder (the whole script runs again and again).
- The trace-engine cost per click is roughly O(N × M) where N is the response length and M is the corpus size.

---

## 3. State, Sessions, and the Streamlit Constraint

`state.py` centralizes session bookkeeping. It initializes a handful of keys (`messages`, `view_doc`, `verify_enabled`, `debug_log`, `clicked_states`, `last_html_debug`, …) and wraps common mutations in helpers like `append_response(...)` and `log_event(...)`.

This matters because Streamlit re-runs the script on every keystroke-that-submits. Without a single source of truth, the UI would flicker, forget, or duplicate. By funneling writes through `state.py`, I get:

- One place to add a new stateful feature.
- One place to debug "why did the UI forget that?"
- A simple mental model: *state.py is my tiny Redux store*.

Wrapping a framework's native state is a common pattern. It makes migration easier. If tomorrow I want to swap Streamlit for FastAPI + React, `state.py` becomes the contract to reimplement.

---

## 4. The Three Agents — A Comparative View

| Property | File-Based | Vector RAG | RLM |
|---|---|---|---|
| **Idea** | Dump (summarized) docs into the prompt. | Retrieve top-k chunks by semantic similarity, then generate. | Give the model a Python REPL so it can *program its own* retrieval. |
| **Pre-processing** | Pre-written summaries in `data/summaries/`. | Chunk (1000 chars, 200 overlap), embed, index in ChromaDB; fingerprint to detect staleness. | None — raw corpus is bundled into a `context` string at runtime. |
| **At query time** | Optional router pass picks which files are relevant from Head/Mid/Tail previews. | Embed query, cosine search, top-k, confidence label. | Model writes ```repl``` code to search/slice/summarize; `llm_query` for sub-questions; emits `FINAL(...)`. |
| **Token cost** | Medium-high (summaries are long). | Low. | Variable, usually the highest. |
| **Latency** | ~1 API call (Fast) or ~2 (Router). | ~1 embed + 1 generate. | Up to `max_steps` generate calls. |
| **Best at** | Broad, thematic questions. | Specific fact lookup. | Multi-hop reasoning, cross-document synthesis. |
| **Failure mode** | Hallucination when a summary loses detail. | Retrieval miss when the answer spans many chunks. | Runaway loops or hitting step cap. |
| **Public contract** | `completion(query, chat_history=None, verify_enabled=False) -> (text, tokens)` | `completion(query) -> (text, tokens)` | `completion(query) -> (text, tokens)` |

Each agent has its own `DESIGN.md` documenting the *why* and a `BEHAVIOR.md` documenting real traces (including known bugs like the content-tag collision in RLM or the "College" semantic gap in Vector RAG). Those files are the living documentation.

---

## 5. Security Model

The attack surface is small, but worth enumerating:

- **API key exposure:** key is loaded from environment or `.streamlit/secrets.toml`. It must not be logged. Looks fine in current code.
- **Code execution sandbox:** the RLM's Python sandbox is the highest-risk component. It allowlists ~70 safe built-ins (types, iteration helpers, exception classes, `__import__`) and explicitly blocks `eval`, `exec`, `compile`, `input`, `open`, `globals`, `locals`. Good but **not bulletproof** — Python has known sandbox escapes via `__class__.__mro__`, `gc.get_referrers`, etc. For a single-author portfolio this is acceptable; for multi-tenant use it would need a separate container or WASM runtime.
- **HTML injection:** responses are rendered with `unsafe_allow_html=True`. The trace engine escapes content via `html.escape()` before wrapping in anchors. Good.
- **File reads:** `load_corpus()` reads only under `data/`. No user-controlled paths. Safe.

---

## 6. Weaknesses and Risks

1. **No automated tests.** Even a small suite for `engines/trace_engine.py` and `agents/vector/vector_store.py` would catch regressions cheaply.
2. **No structured logging.** `log_event` prints to console and appends to session state. For any deployment beyond a laptop, structured JSON logs and a log level would help.
3. **Token accounting is best-effort.** `total_token_count` is summed across multi-step RLM runs, but if a step fails, the count is partial. Not a bug — just something to know before putting a usage bill in front of a real user.
4. **Single-threaded by design.** Streamlit serves one request at a time per session. Fine for a portfolio; becomes a wall if the app is ever multi-user at scale.
5. **`InsightRLMAgent` v2 is disabled but kept in-tree.** Useful as research material, but readers may wonder why code exists that nothing imports.
6. **Batched sub-LLM calls are sequential.** `llm_query_batched` in the RLM loops rather than fans out, which loses the speed benefit the prompt advertises.

---

## 7. Scalability and Performance

The system is optimized for a **single reader at a time, tens of documents, hundreds of chunks**.

| Axis | Current limit | What breaks first |
|---|---|---|
| Concurrent users | 1 per Streamlit session | API rate limit before server CPU. |
| Corpus size | ~100 docs comfortably | Trace engine's O(N·M) scan gets slow past ~10k docs. |
| Response length | ~3–4K tokens | Rate-limit warning fires at the `HIGH_TOKEN_WARNING_THRESHOLD` set in `config/app_config.py`. |
| Query complexity | Bounded by RLM `max_steps=10` | Falls back to a best-effort `FINAL(...)` prompt when the cap is hit. |

**Cheap wins if scaling up:**

- Pre-compute a suffix array or use an Aho-Corasick automaton for `engines/trace_engine.py`.
- Move ChromaDB to a server (chroma-client-server) and share it across sessions.
- Cache `load_corpus()` with `@st.cache_data(ttl=300)`.
- Fan out `llm_query_batched` concurrently instead of looping.

---

## 8. Extensibility — How to Add Things

Because the architecture is layered, each kind of change has a known "surgery path":

- **Add a project** → drop `data/projects/new.md`. Zero code.
- **Add a page** → create `pages/xyz.py`. Streamlit auto-discovers it; update `utils/sidebar.py` if you want a nav link.
- **Add an AI mode** → create `agents/<mode>/<mode>_agent.py` with a class that exposes `completion(query) -> (text, tokens)`; add a mode constant in `config/app_config.py`; add a branch in `components/agent_dispatch.py`. All three existing agents follow this shape, so the dispatcher branch is small.
- **Change embedding model** → update `EMBEDDING_MODEL_ID` in `config/app_config.py`. The corpus fingerprint will notice the change and trigger a full re-embed on next query.
- **Swap LLM provider** → the Gemini client is passed into agents from `app.py`. Replace the client; adapt the response-parsing code inside each agent's `completion`. Not trivial but not huge.
