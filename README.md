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
│  │    chat_renderer.py         │    │    vector_store.py       │ │
│  └──────┬───────────┬──────────┘    │    video_modal.py        │ │
│         │           │               └──────────────────────────┘ │
│         ▼           ▼                                            │
│  ┌───────────┐ ┌─────────────┐   ┌────────────────────────────┐  │
│  │ agents/   │ │ trace_engine│   │ state.py  styles.py        │  │
│  │   rlm/    │ │     .py     │   │ (session + CSS)            │  │
│  └─────┬─────┘ └──────┬──────┘   └────────────────────────────┘  │
└────────┼──────────────┼──────────────────────────────────────────┘
         │              │
         ▼              ▼
┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐
│ Google Gemini   │  │  ChromaDB       │  │  data/  (the       │
│   (LLM + embed) │  │  (vector store) │  │  "content DB")     │
└─────────────────┘  └─────────────────┘  └────────────────────┘
```

The project follows a **five-layer architecture**

### 1.1 Presentation Layer — `app.py`, `pages/`, `styles.py`

**Responsibility:** Turn Python state into HTML and handle user events.

This layer contains **no reasoning logic**. It only calls dispatchers and renders what comes back. This is good: you can rewrite the whole UI without touching intelligence.

### 1.2 Orchestration Layer — `components/`

**Responsibility:** Decide *which* agent handles a request and *how* to render the result.

This is the "traffic controller". It reads the selected mode, prepares the context, calls the right agent, and attaches metadata (token usage, debug trace, source highlights) to the response.

### 1.3 Reasoning Layer — `agents/`

**Responsibility:** Produce an answer given a question and a corpus.

### 1.4 Service Layer — `engines/trace_engine.py`, `utils/`

**Responsibility:** Reusable, stateless services.

These modules do not know *why* they are being called. They take inputs and return outputs. This is the most reusable tier: if I ever rewrite the frontend in Next.js, these modules could move to a backend API unchanged.

### 1.5 Data Layer — `data/`, `config/`, `static/`

**Responsibility:** Raw content and configuration.

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
[3] agent_dispatch.py inspects selected mode:
    ┌────────────────┬────────────────────┬────────────────────┐
    │  RLM mode      │  Vector RAG mode   │  File-Based mode   │
    ├────────────────┼────────────────────┼────────────────────┤
    │ RLMAgent()     │ VectorEngine()     │ load summaries     │
    │ .completion()  │ .search(k=5)       │ optional router    │
    │                │ generate_content() │ generate_content() │
    └────────────────┴────────────────────┴────────────────────┘
        │
        ▼
[4] Google Gemini API called (network hop)
    └── returns response text + usage_metadata (tokens)
        │
        ▼
[5] If "verify" is ON:
    └── trace_engine.find_maximal_matches(response, corpus)
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
- App's performance is O(C×N) where $C$ is the number of clicks and $N$ is the number of files. 

---

## 3. State, Sessions, and the Streamlit Constraint

`state.py` centralizes session bookkeeping. It initializes ten keys (`messages`, `view_doc`, `verify_enabled`, `debug_log`, `current_mode`, etc.) and wraps common mutations in helpers like `append_response(...)` and `log_event(...)`.

This matters because Streamlit re-runs the script on every keystroke-that-submits. Without a single source of truth, the UI would flicker, forget, or duplicate. By funneling writes through `state.py`, the author gets:

- One place to add a new stateful feature.
- One place to debug "why did the UI forget that?"
- A simple mental model: *state.py is my tiny Redux store*.

Wrapping a framework's native state is a common pattern. It makes migration easier. If tomorrow I want to swap Streamlit for FastAPI + React, `state.py` becomes the contract to reimplement.

---

## 4. Security Model

The attack surface is small, but worth enumerating:

- **API key exposure:** key is loaded from environment or `.streamlit/secrets.toml`. It must not be logged. Looks fine in current code.
- **Code execution sandbox:** the RLM's Python sandbox is the highest-risk component. It allowlists built-ins and removes `os`, `sys`, `open`, `exec`. This is good but **not bulletproof** — Python has known sandbox escapes via `__class__.__mro__`, `gc.get_referrers`, etc. For a single-author portfolio this is acceptable; for multi-tenant use it would need a separate container or WASM runtime.
- **HTML injection:** responses are rendered with `unsafe_allow_html=True`. The trace engine escapes content via `html.escape()` before wrapping in anchors. Good.
- **File reads:** `load_corpus()` reads only under `data/`. No user-controlled paths. Safe.

---

## 5. Weaknesses and Risks

1. **No automated tests.** May have tests for the trace engine and the vector chunker
2. **ChromaDB index freshness.** If `data/` files change, the index is not invalidated. A stale index silently serves old chunks. A simple "source file mtime" check would fix this.
3. **No structured logging.** `log_event` prints to console. For any deployment beyond a laptop, structured JSON logs and a log level would help.
4. **Token accounting is best-effort.** The `total_token_count` is summed across multi-step RLM runs, but if a step fails, the count is partial. Not a bug — just something to know before putting a usage bill in front of a real user.
5. **Single-threaded by design.** Streamlit serves one request at a time per session. Fine for a portfolio; becomes a wall if the same app is ever multi-user at scale.

---

## 6. Scalability and Performance

The system is optimized for a **single reader at a time, tens of documents, hundreds of chunks**.

| Axis | Current limit | What breaks first |
|---|---|---|
| Concurrent users | 1 per Streamlit session | API rate limit before server CPU. |
| Corpus size | ~100 docs comfortably | Trace engine's O(N·M) scan gets slow past ~10k docs. |
| Response length | ~3–4K tokens | Rate-limit warning fires at 6.5K tokens. |
| Query complexity | Bounded by RLM's max_steps=10 | Silent cutoff, returns "Max steps reached". |

**Cheap wins if scaling up:**
- Pre-compute a suffix array or use an Aho-Corasick automaton for `trace_engine`.
- Move ChromaDB to a server (chroma-client-server) and share it across sessions.
- Cache `load_corpus()` with `@st.cache_data(ttl=300)`.
- Batch Gemini calls with the async SDK.

---

## 7. Extensibility — How to Add Things

Because the architecture is layered, each kind of change has a known "surgery path":

- **Add a project** → drop `data/projects/new.md`. Zero code.
- **Add a page** → create `pages/xyz.py`. Streamlit auto-discovers it; update `utils/sidebar.py` if you want a nav link.
- **Add an AI mode** → create `agents/<mode>/agent.py` with a `.completion(query) -> (text, token_stats)` method; add a constant in `config/app_config.py`; add a branch in `components/agent_dispatch.py`.
- **Change embedding model** → one line in `agents/vector/vector_store.py`. But the existing index must be rebuilt (dimension change).
- **Swap LLM provider** → the Gemini client is passed into agents from `app.py`. Replace the client; adapt the response-parsing code in two spots. Not trivial but not huge.