# Recursive Language Model (RLM) — Implementation Deep Dive

## What Is It?

The RLM is a **ReAct-style agentic loop** where the LLM doesn't answer questions directly — it writes and executes Python code in a sandboxed REPL to programmatically search through portfolio data, then returns a final answer. Code _is_ the retrieval mechanism.

## Architecture Overview

````
User Question
    │
    ▼
┌─────────────────────────────────────────────┐
│  RLMAgent.completion()                      │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  Loop (max 10 steps)                  │  │
│  │                                       │  │
│  │  1. Send full chat history to LLM     │  │
│  │  2. Parse response:                   │  │
│  │     • <FINAL>...</FINAL> → return ✅  │  │
│  │     • ```python ... ``` → execute 🔄  │  │
│  │     • neither → nudge to continue     │  │
│  │  3. Feed execution output back        │  │
│  │     as "Observation: {stdout}"        │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Sandbox REPL globals:                      │
│  ├── context        (entire corpus)         │
│  ├── llm_query()    (sub-agent call)        │
│  ├── llm_query_batched() (map-reduce)       │
│  ├── re             (regex module)          │
│  └── print()        (captured stdout)       │
└─────────────────────────────────────────────┘
    │
    ▼
Final Answer + Token Stats
````

## File Structure

| File                                | Role                                                                    |
| ----------------------------------- | ----------------------------------------------------------------------- |
| `rlm_impl.py`                       | Core `RLMAgent` class — REPL sandbox, recursive loop, sub-agent queries |
| `rlm/utils/prompts.py`              | System prompt defining agent behavior and 4 navigation strategies       |
| `app.py` (lines 306–330)            | Streamlit integration — instantiates agent and streams thinking steps   |
| `trace_engine.py` (`load_corpus()`) | Recursively loads all `.txt`, `.md`, `.pdf`, `.docx` from `data/`       |

> Note: The `rlm/` package has no `__init__.py` — it uses Python's implicit namespace packages.

## Step-by-Step Walkthrough

### 1. Data Ingestion & Context Construction

`load_corpus()` in `trace_engine.py` recursively walks `data/`, reads every `.txt`, `.md`, `.pdf`, and `.docx` file, normalizes whitespace, and returns a `dict[relative_path → content]`.

The `RLMAgent.__init__` flattens this dict into a single pseudo-XML string:

```xml
<file name='resume.txt'>
... cleaned content ...
</file>
<file name='projects/grace.md'>
... cleaned content ...
</file>
```

This string is stored in `self.context` and injected into the REPL sandbox as a global variable named `context`. The model never sees the raw context in its prompt — it must write code to navigate it.

**Current corpus includes:**

- `KhuongNguyen_CV.pdf` — resume
- `my_life.txt` — personal story
- `ProjectGRACE.txt` — project description
- `how_it_works.txt` — portfolio architecture
- `projects/` subdirectory — `grace.md`, `adaptive_rag.md`, `formal_methods.md`, `long_context.md`, `rag101.md`, `saasHandbook.md`

### 2. The REPL Sandbox

`execute_code()` (lines 79–97) runs LLM-generated Python via `exec()` in a persistent namespace (`self.repl_globals`). Key properties:

- **Persistent state**: Variables set in step 1 carry over to step 2. The model can incrementally build up results across steps.
- **Captured I/O**: `print()` is redirected to a `StringIO` buffer. Both stdout and stderr are captured and returned.
- **Error tolerance**: Exceptions are caught and returned as `"Execution Error: ..."` strings — they get fed back to the model so it can self-correct.

Injected globals:

| Global                       | Type       | Purpose                                          |
| ---------------------------- | ---------- | ------------------------------------------------ |
| `context`                    | `str`      | The full document corpus as pseudo-XML           |
| `llm_query(prompt)`          | `function` | Calls the LLM as a stateless sub-agent           |
| `llm_query_batched(prompts)` | `function` | Sends multiple prompts sequentially (map-reduce) |
| `re`                         | `module`   | Python's regex module for pattern matching       |
| `print`                      | `function` | Captured to return output to the agent loop      |

### 3. The Recursive Loop (`completion()`)

Lines 99–165. This is the core agentic loop:

1. **Initialize history** with the system prompt + user query as the first message
2. **Reset token counters** for this run
3. **Loop** up to `max_steps = 10`:
   - Create a new chat session with the full conversation history
   - Send the last message and get a response
   - Track token usage via `_update_tokens()`
   - **Parse the response**:
     - `<FINAL>...</FINAL>` found → extract content via regex `r"<FINAL>(.*?)(?:</FINAL>|$)"` (supports missing closing tag) → **return answer + token stats**
     - ` ```python ... ``` ` or ` ```repl ... ``` ` found → extract code → `execute_code()` → append stdout as `"Observation:\n{output}"` to history
     - Neither found → append nudge: `"Continue. Use code if needed or output FINAL()."`
   - If the LLM API call throws an exception, the error is appended to history as `"Error: {e}"` so the model can recover
4. If 10 steps exhausted → return `"Max steps reached without final answer."`

**LLM Configuration:**

- Model: `models/gemma-3-27b-it`
- Temperature: `0` (deterministic) — both for the main loop and sub-agent calls
- Chat mode: Creates a fresh `client.chats.create()` each step with full history (not a persistent chat object)

### 4. Navigation Strategies (System Prompt)

The system prompt in `rlm/utils/prompts.py` teaches the model four strategies:

#### Strategy 1: File Listing & Lookup ("Map") — Recommended Start

```python
import re
files = re.findall(r"<file name='(.*?)'>", context)
print(f"Available Files: {files}")

# Then extract a specific file
pattern = fr"<file name='.*?grace.md'>\n(.*?)\n</file>"
match = re.search(pattern, context, re.DOTALL)
if match:
    print(match.group(1)[:2000])
```

#### Strategy 2: Basic Slicing ("Peek")

```python
print(context[:1000])
```

#### Strategy 3: Iterative Looping ("Serial Read")

```python
sections = re.split(r"</file>", context)
for section in sections:
    if "Key Keyword" in section:
        print(section[:500])
```

#### Strategy 4: Batched Map-Reduce ("Global Scan")

```python
chunks = [c for c in context.split("</file>") if c.strip()]
prompts = [f"Does this chunk mention X? Text: {c[:1000]}" for c in chunks]
results = llm_query_batched(prompts)
print(results)
```

### 5. Sub-Agent Mechanism

#### `llm_query(prompt)` — Single Query

Makes a **fresh, stateless** `generate_content()` call (not part of the main chat history). Returns the response text or an error string. Used for reasoning tasks like "Summarize this section" or "Does this mention GPA?"

#### `llm_query_batched(prompts)` — Map-Reduce

Calls `llm_query()` sequentially for each prompt in the list. Returns a list of responses. There's a TODO comment noting parallel execution is planned for the future.

Both sub-agent calls use `temperature=0` and their token usage is tracked in the parent agent's cumulative counters.

### 6. Token Tracking

`_update_tokens()` (lines 38–42) accumulates input, output, and total token counts from `response.usage_metadata` across all LLM calls (main loop + sub-agents). The final stats dict `{'input', 'output', 'total'}` is returned alongside the answer.

### 7. Streamlit Integration (`app.py`)

When the user selects "Recursive Language Model (RLM)" mode:

1. A `ui_logger` callback is created that writes to a Streamlit `st.status` widget in real-time
2. `RLMAgent` is instantiated with the Gemini client, model ID, loaded docs, and the logger
3. `rlm.completion(prompt_text)` runs the full loop
4. Each step is streamed live into the expandable "🧠 RLM Thinking..." status box
5. The final answer, token stats, and thinking steps are saved to chat history
6. Thinking steps are later renderable in a collapsible "🧠 Thinking Process" section

**RLM-specific UI behavior:**

- Verify Sources toggle is disabled (set to `False`) — traceability comes from the visible thinking steps
- A warning banner notes: "Full data access, but takes long time to conclude final answer"

## Comparison with Other Modes

| Aspect              | File-Based Context                    | RLM                         | Standard RAG (Vector)        |
| ------------------- | ------------------------------------- | --------------------------- | ---------------------------- |
| Data access         | Root `data/` files only (TPM limited) | Full recursive `data/`      | Full recursive `data/`       |
| Retrieval           | Entire files in prompt                | Agent writes code to search | Vector similarity (ChromaDB) |
| LLM calls           | 1 (+ optional router)                 | 1–10+ (loop + sub-agents)   | 1                            |
| Token usage         | Highest (full context in prompt)      | Medium-high (cumulative)    | Lowest (only top-k chunks)   |
| Latency             | Fast                                  | Slowest                     | Fastest                      |
| Hallucination risk  | Lowest                                | Medium                      | Highest                      |
| Source verification | Trace Engine (exact match)            | Thinking steps              | Trace Engine (exact match)   |

## Key Design Decisions

1. **Global view, not chunked retrieval**: Unlike standard RAG which retrieves top-k chunks, the RLM has access to the _entire_ corpus via `context`. The model decides what to look at.

2. **Code as retrieval**: Instead of embedding similarity, the model uses regex, string operations, and sub-agent queries to find relevant information. This gives it full flexibility.

3. **Persistent REPL state**: Variables set in one step carry over to the next — the model can incrementally build up results across steps.

4. **Self-correcting errors**: Both execution errors and API errors are fed back into the conversation history, giving the model a chance to recover.

5. **Deterministic outputs**: `temperature=0` everywhere ensures reproducible behavior for the same inputs.
