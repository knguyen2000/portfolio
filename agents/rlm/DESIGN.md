# RLM Design & Implementation Analysis

This document is a comprehensive technical deep-dive into the Recursive Language Model (RLM) agent as implemented in this portfolio. It covers every design decision from the corpus encoding layer up to the main loop, including tradeoffs relative to the original reference implementation.

Reference paper and implementation: https://github.com/alexzhang13/rlm

---

## Files Structure

### `/rlm`
Currently, this directory only contains the **Recursive Language Model (RLM)** package. By nesting it, the root `agents/` folder remains clean for future non-RLM agents.

#### `rlm/base.py`
Contains the low-level utilities shared across different agents.
- `build_corpus`: Formats standard Markdown/text files into a strict pseudo-XML structure (`<file name='...'>content</file>`) that LLMs process natively with higher accuracy.
- `execute_sandbox_code`: A **Security Layer**. When agents generate Python code to process data, this function executes it inside a restricted `__builtins__` dictionary. It strips away standard libraries like `os` or `subprocess` to ensure the agent cannot run malicious system-level queries on the server.

#### `rlm/rlm_agent.py`
The production-ready recursive model (V1). 
- Takes in the user's prompt and loops through a completion logic until it is satisfied it has found the answer.
- Dispatches logs back to the main UI by executing a `log_callback`.

#### `rlm/insight_rlm_agent.py` `[DISABLED]`
The experimental (V2) insight-aware model.
- Designed to build complex "Chain of Thought" data graphs instead of standard recursion.
- *TODO:* Currently disabled and disconnected from `agent_dispatch.py` due to instability and high token costs. Kept here for future testing and iteration.

#### `rlm/prompts/`
A subdirectory storing the massive system prompt string templates that dictate the exact behavior, tone, and JSON schemas the RLMs must follow.

## 1. Core Idea

The fundamental insight behind RLM is that a language model should not answer questions by reading everything and guessing. Instead, it should behave more like a programmer debugging a problem: explore selectively, gather evidence through code execution, evaluate what it found, and only commit to a final answer when it has enough grounded information to do so.

The model is given a Python REPL and a corpus of documents. It writes code to navigate the corpus, observes the outputs, and iterates until it either finds the answer or exhausts its step budget.

This is architecturally different from:
- **Standard RAG**: which does a one-shot embedding similarity search and generates from the retrieved chunks without any iteration or self-correction.
- **Naive prompting**: which dumps everything into the context window and hopes the model doesn't hallucinate.

---

## 2. Corpus Encoding — `build_corpus` in `base.py`

### What it does

```python
def build_corpus(docs):
    parts = []
    for fname, content in docs.items():
        parts.append(f"<file name='{fname}'>\n{content}\n</file>")
    return "\n".join(parts)
```

This takes the `docs` dictionary (filename → content strings) and flattens it into a single pseudo-XML string stored in a variable called `context`. The model is taught in its system prompt to navigate this string by running regex searches inside the REPL.

### Design Choice: Single Flat String vs. Structured Dict

The original RLM paper stores context as a flat string because LLMs process continuous text more naturally than structured Python objects. Passing a Python dictionary `{"file.txt": "content"}` would require the model to understand how to index into it, which is error-prone. The XML-like tag format gives the model a grammar to parse, and it matches patterns the model has seen during pretraining (HTML, XML, Markdown frontmatter).

**Tradeoff:** Simplicity vs. robustness. A dict would be indexable with `O(1)` lookups, but the model would need to call `context["myfile.txt"]` directly, which produces no output and requires knowing the exact key. The flat string enables fuzzy regex matching like `<file name='[^']*grace.*'>`, which is much more forgiving.

**Known issue:** If any file's content itself contains the string `<file name='...'>` (e.g., documentation files showing XML examples), the top-level `re.findall` will pick those up as fake filenames. This is a content-tag collision bug documented in `BEHAVIOR.md`. The fix requires HTML-escaping the content before wrapping or switching to a more unique delimiter.

### Design Choice: No Chunking

`build_corpus` does not chunk documents. Each file is inserted wholesale, regardless of length. This is intentional: the model explores with regex, not with vector similarity. Chunking would break the model's ability to read a whole file in one regex extraction. If a file is very long, the model is expected to use `llm_query` (the sub-LLM callback) to summarize it rather than printing all of it.

**Tradeoff:** Chunking would improve memory efficiency but would force the model to reason about chunk boundaries, which adds complexity. Keeping files whole gives the agent maximum flexibility at the cost of potential context overflow for extremely large documents.

---

## 3. The Sandbox — `execute_sandbox_code` in `base.py`

### What it does

```python
def execute_sandbox_code(code, repl_globals):
    if "__builtins__" not in repl_globals:
        repl_globals["__builtins__"] = _SAFE_BUILTINS.copy()

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    t0 = time.perf_counter()
    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            exec(code, repl_globals)
        ...
    except Exception as e:
        stderr = stderr_buf.getvalue() + f"\n{type(e).__name__}: {e}"
    ...
```

Python's `exec()` is used to execute the model-generated code. The key security layer is the `_SAFE_BUILTINS` dictionary, which replaces the standard `__builtins__` entirely. This strips away dangerous capabilities while preserving everything a data-processing script needs.

### Design Choice: `exec` over `subprocess`

Using `exec` inside the main process is far simpler than spinning up a subprocess or a container. For a portfolio application running in a single-user Streamlit server, the threat model is low: there is no untrusted code being executed, and the model is specifically prompted to write navigation code, not system commands.

The alternative (subprocess isolation) would add significant complexity: you would need to pass the `context` string across a process boundary, serialize/deserialize outputs, and handle process lifecycle. The `exec` approach handles this transparently because the sandbox runs inside the same Python process and can access `context` directly via `repl_globals`.

**Tradeoff:** Security vs. simplicity. A fully isolated container would be safer for a multi-user public app. `exec` inside a restricted dict is sufficient for a single-user portfolio but would not be appropriate if arbitrary users could reach the REPL.

### Design Choice: Persistent Namespace (`repl_globals`)

```python
self.repl_globals = {
    "llm_query": self.llm_query_callback,
    "llm_query_batched": self.llm_query_batched_callback,
    "context": self.context,
    "re": re,
}
```

The same `repl_globals` dict is passed to every `exec` call throughout the entire agent session. This means variables the model defines in step 1 are still accessible in step 4. The model can incrementally build up data structures (`buffers = []`, then `buffers.append(...)` in a later step) and read them back.

**Tradeoff:** This is the correct design because it mirrors how a real programmer uses a REPL (variables persist). The downside is that it accumulates garbage: if the model defines a huge `content` variable in step 2, that string stays in memory for all remaining steps even after it is no longer needed. For a 10-step loop with large corpora this is manageable; for a 100-step loop it could become a concern.

### Design Choice: Captured stdout, Separate stderr

```python
with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
    exec(code, repl_globals)
```

Both `stdout` and `stderr` are captured independently. `format_execution_result` then renders them separately, prepending `"stderr:\n"` to distinguish error output from normal print output. This gives the model an unambiguous signal when its code throws an exception: it will see `stderr: NameError: name 'x' is not defined` and can attempt a correction in the next step.

**Known issue:** Because `self.log()` uses `print()`, if a log call happens inside a callback that is invoked during `exec`, the log text gets captured into `stdout_buf` instead of going to the UI. This was observed in live traces where sub-LLM log lines appeared inside the REPL output. The fix is to route `self.log()` through Python's `logging` module, which writes to stderr or a file handler rather than stdout.

---

## 4. Sub-LLM Callbacks

### `llm_query_callback`

```python
def llm_query_callback(self, prompt_text):
    response = self.client.models.generate_content(
        model=self.model_id,
        contents=prompt_text,
        config=types.GenerateContentConfig(temperature=0),
    )
    self._update_tokens(response.usage_metadata)
    return response.text
```

This is injected into the REPL namespace as the `llm_query` function the model can call from inside its code blocks. It is a simple stateless one-shot generation: no chat history, no system prompt. The model uses it to delegate reasoning tasks that are expensive to do with regex ("summarize this 5,000-character excerpt", "does this section mention education?").

**Design Choice: `generate_content` not `chats.create`**
Sub-LLM calls use the stateless `generate_content` API, not the chat session. This is intentional: each sub-query is self-contained. Using a chat session would attach the sub-query to the main conversation history, polluting the root model's context with intermediate reasoning.

**Design Choice: `temperature=0`**
All calls (root + sub-LLM) use `temperature=0`. The goal is deterministic, grounded extraction, not creative synthesis. Temperature 0 minimizes the risk of the model paraphrasing a fact into an incorrect form.

### `llm_query_batched_callback`

```python
def llm_query_batched_callback(self, prompts):
    return [self.llm_query_callback(p) for p in prompts]
```

The reference implementation dispatches batched queries concurrently using async sockets. This portfolio version executes them sequentially in a for loop. This was a deliberate simplification: the Gemini free tier is rate-limited to 15,000 tokens per minute, and concurrent fan-out would cause immediate rate limit errors. Sequential execution adds latency but stays within quota.

**Tradeoff:** Performance vs. quota compliance. In a paid-tier environment, replacing this with `asyncio.gather` or `concurrent.futures.ThreadPoolExecutor` would cut batched query time by `N×` (where N is the number of prompts). That optimization is deferred.

---

## 5. The Main Loop — `completion` in `rlm_agent.py`

### Opening Turn

```python
opening = (
    f"Query: {user_query}\n\n"
    "You have not yet interacted with the REPL. Start by listing the "
    "files available inside `context` with a ```repl``` block; don't "
    "give a FINAL answer until you have inspected the relevant files."
)
```

The opening turn is not just the raw user query. It includes a soft directive that nudges the model toward the Map strategy as its first action. Without this, early experiments showed the model sometimes tried to answer from parametric memory immediately, hallucinating plausible-sounding but ungrounded answers.

**Design Choice: Fused Query + Directive**
The system prompt already contains navigation strategies, but a reminder in the opening user turn reinforces compliance. System prompts set long-range policy; opening turn reminders handle the specific situation of "you have not yet seen the corpus."

### History Management

```python
self.history.append({"role": "user", "parts": [{"text": next_user_msg}]})
self.history.append({"role": "model", "parts": [{"text": response_text}]})
```

History is appended explicitly before parsing the response. This is important: if the response fails to parse (no code block, no FINAL), the model still sees its own output in the next turn and can self-correct. An alternative design would only persist history after validating the response, but that risks the model contradicting itself ("I said X last turn?" — "no, you didn't, it was stripped").

Each turn, the history is fed to a freshly created chat session:

```python
chat = self.client.chats.create(
    model=self.model_id,
    config=types.GenerateContentConfig(
        temperature=0,
        system_instruction=RLM_SYSTEM_PROMPT,
    ),
    history=self.history,
)
response = chat.send_message(next_user_msg)
```

**Design Choice: Fresh Chat Per Turn**
Instead of keeping a single long-running `chat` object, a new one is created each turn with the full history injected. This supports the `system_instruction` field (which must be set at chat creation time, not per-message in the Gemini SDK). It also makes the system stateless across network failures: if the app restarts mid-loop, the history list can be persisted and replayed into a new chat object without any state loss.

**Tradeoff:** Slightly higher SDK overhead per turn (object instantiation), but much cleaner recovery semantics.

### Response Parsing Priority

```python
# 1) Is this the final answer?
final = find_final_answer(response_text, self.repl_globals)
if final is not None:
    return final, self.token_usage

# 2) Are there code blocks to execute?
code_blocks = find_code_blocks(response_text)
```

FINAL is checked before code blocks. This is the correct order: if the model emits a `FINAL(...)` line and also includes some stray code, the terminal condition wins and no code is executed. The alternative (code first) would cause a spurious REPL execution on what was intended to be the last turn.

### Code Block Execution

```python
for code in code_blocks:
    self.log("executing code...")
    result = self.execute_code(code)
    rendered = format_execution_result(result)
    rendered = _truncate(rendered)
    self.log(f"REPL output:\n{rendered}")
    observations.append(
        f"Code executed:\n```python\n{code}\n```\n\nREPL output:\n{rendered}"
    )
next_user_msg = "\n\n---\n\n".join(observations)
```

All code blocks in a single response are executed. Results are concatenated into a single next user message separated by `---` dividers. This allows the model to emit multiple independent code blocks in one turn (e.g., file listing + file read in the same response) and receive all their outputs together.

Observations are capped by `_truncate` at `_MAX_OBSERVATION_CHARS = 20_000`, matching the reference implementation's `format_iteration()` limit. Without this cap, a model that accidentally prints the entire corpus in a `print(context)` call would blow the context budget on the next turn.

### Nudge for Empty Responses

```python
next_user_msg = (
    "I did not find a ```repl``` block or a FINAL(...) line in "
    "your response. Either run a ```repl``` block to gather more "
    "information, or emit FINAL(answer) / FINAL_VAR(variable) to finish."
)
```

If the model returns a response with neither code nor a FINAL marker, the loop sends this nudge instead of giving up. This handles conversational drift, where the model narrates what it plans to do instead of doing it. The nudge is a hard constraint: "do one of these two things."

### Fallback Answer

```python
self.log("max steps reached, requesting fallback final answer")
fallback_prompt = (
    "You have used all iterations. Based on everything you have "
    f"observed so far, produce the best possible answer to the original "
    f"query: {user_query!r}\n\n"
    "Respond with a single line: FINAL(your answer)."
)
```

If the loop exhausts all `max_steps` without emitting FINAL, the model gets one more chance: a dedicated fallback prompt that summarizes everything it has seen and asks for its best guess. This mirrors the reference implementation's `_default_answer`. Importantly, the fallback still uses the `FINAL(...)` format, so the parser can extract just the answer text without stray explanation.

**Design Choice: max_steps=10**
The reference implementation uses 30 steps. This portfolio caps at 10 to stay under the free-tier 15K token-per-minute rate limit. Most simple factual questions resolve in 2-4 steps. If the model has not found an answer in 10 steps, one more step is unlikely to help, and the fallback prompt synthesizes from accumulated observations.

---

## 6. Parsing Helpers

### Code Block Regex

```python
_CODE_BLOCK_REGEX = re.compile(
    r"```(?:repl|python)\s*\n(.*?)\n```",
    re.DOTALL,
)
```

The regex accepts both `` ```repl `` and `` ```python `` fences. The `repl` identifier is the canonical form (matching the updated prompt), but `python` is accepted for backward compatibility with transcripts generated before the prompt rewrite. `re.DOTALL` allows the code block content to span multiple lines.

### FINAL Regex

```python
_FINAL_VAR_REGEX = re.compile(r"^\s*FINAL_VAR\((.*?)\)", re.MULTILINE | re.DOTALL)
_FINAL_REGEX = re.compile(r"^\s*FINAL\((.*?)\)", re.MULTILINE | re.DOTALL)
```

The `^` anchor with `re.MULTILINE` ensures that `FINAL(...)` is only matched at the start of a line. This prevents false positives where the model writes something like "A FINAL answer would be..." inside an explanation paragraph. The anchor is what made the earlier hallucination bug so subtle: when the model placed `<FINAL>` inside a code block in the old XML-tag format, the parser matched it regardless of position.

`FINAL_VAR` is checked first because it is more specific: it resolves a REPL variable by name, which is useful when the answer is a long buffer the model built up across multiple steps.

---

## 7. Token Accounting

```python
def _update_tokens(self, usage_metadata):
    self.token_usage["input"] += usage_metadata.prompt_token_count or 0
    self.token_usage["output"] += usage_metadata.candidates_token_count or 0
    self.token_usage["total"] += usage_metadata.total_token_count or 0
```

Token counts are accumulated across all API calls: root model turns and sub-LLM calls alike. This gives a true end-to-end token cost for a single user query. The dispatcher surface this count in the UI (`🪙 Total Tokens Used: ...`).

**Tradeoff:** History-based chat is inherently token-expensive. Every root turn resends the entire conversation history to the model, so token cost grows quadratically with step count: step 1 sends N tokens, step 2 sends 2N, step 3 sends 3N. For a 10-step loop with a large corpus this can reach 50-100K tokens total. The `max_steps=10` cap is partly a token budget decision, not just a safety valve against infinite loops.

---

## 8. System Prompt Design Principles (`rlm_prompts.py`)

The system prompt does five things:

1. **Environment declaration** — describes `context`, `llm_query`, `llm_query_batched`, `re` as available REPL globals. This prevents the model from trying to `import something` it does not have.

2. **Code fence specification** — explicitly shows the `` ```repl ``` `` format. LLMs trained on code are sensitive to the language identifier in code fences; specifying `repl` uniquely marks this as executable rather than illustrative.

3. **Navigation strategies with examples** — four named strategies with working code examples. Giving the model concrete templates dramatically reduces the chance of it inventing a strategy that does not work (e.g., trying to call a `read_file()` function that does not exist).

4. **Stop rule** — "STOP generating immediately after closing a repl block. Do NOT predict or simulate the output." This is the most critical line in the prompt. Before it was added, the model would auto-regressively continue generating, producing fake `Output:` sections and hallucinating file contents that it never actually executed.

5. **FINAL format** — specifies `FINAL(...)` not `<FINAL>...</FINAL>`. Function-style markers are less ambiguous than XML tags because they have a clearly defined content boundary and are less likely to appear in explanatory prose.

---

## 9. Summary of Key Design Decisions

| Decision | Choice Made | Alternative | Reason |
|---|---|---|---|
| Corpus format | Flat pseudo-XML string | Python dict / JSON | Enables fuzzy regex navigation; matches model pretraining |
| Code execution engine | `exec` in restricted namespace | `subprocess` / container | Simpler, sufficient threat model for single-user app |
| REPL persistence | Single shared `repl_globals` dict | Fresh namespace per step | Enables incremental computation across steps |
| Chat architecture | New chat object per turn, full history injected | Single long-running chat | Supports `system_instruction`; stateless recovery |
| Sub-LLM concurrency | Sequential for loop | `asyncio.gather` | Free-tier rate limit prevents concurrent fan-out |
| Step budget | 10 (vs. reference 30) | Higher cap | 15K TPM free-tier constraint |
| FINAL format | `FINAL(text)` function style | `<FINAL>text</FINAL>` XML tags | Harder to false-positive in prose; clearer boundary |
| Temperature | 0 everywhere | >0 for creativity | Deterministic extraction; hallucination mitigation |
