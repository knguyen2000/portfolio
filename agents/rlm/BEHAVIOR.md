# RLM Live Trace Analysis

This document dissects real executions of the Recursive Language Model (RLM) agent captured during live portfolio testing. Each trace is analyzed step by step, with notes on what the model did correctly, what went wrong, and what the architecture reveals about RLM reasoning.
These are listed

---

## Trace 1 — "Where did Khuong go for college?"

**Token usage:** 6,912 | **Steps taken:** 3/10 | **Outcome:** Correct

### Step-by-Step Breakdown

**Step 1 — File Discovery (Map)**

```repl
files = re.findall(r"<file name='(.*?)'>", context)
print("Available files:", files)
```

The model correctly chose the File Listing strategy as its opening move, exactly as the system prompt prescribes. It did not attempt to guess the answer from its parametric memory. This is the system working as intended.

**Anomaly — Noise in the file list output:**
```
['how_it_works.txt', ..., 'resume.txt', 'projects/grace.md', '(.?)', '.?grace.md', ...]
```

The file listing returned artifacts like `(.?)` and `.?grace.md` mixed into the real filenames. This is a regex contamination bug: the `build_corpus` function in `base.py` wraps content in `<file name='...'>` tags, but if any file's *content* itself contains strings that look like `<file name='...'>`, the top-level `re.findall` picks those up as if they were real file tags. In this case, `how_it_works.txt` contains documentation examples with pseudo-XML, which leaked into the file listing. The model ignored these garbage entries and kept going, which is a sign of robustness — but the root cause is content-tag collision in the corpus structure.

**Step 2 — Targeted File Read (Zoom In)**

```repl
targets = ['my_life.txt', 'resume.txt']
for target in targets:
    pattern = fr"<file name='[^']*{re.escape(target)}'>\n(.*?)\n</file>"
    ...
```

The model correctly prioritized `my_life.txt` as the most likely location for biography data. It also speculatively included `resume.txt` — a file that does not exist in the corpus. This is a reasonable prior from training data (resume files commonly hold education info), but it reflects the model drawing on world knowledge rather than corpus knowledge. The code handled the miss cleanly with no crash.

The REPL output returned the full content of `my_life.txt`, approximately 4,000+ characters. The model received this in a single observation and extracted the answer from it directly.

**Step 3 — Answer and Termination**

The model read the phrase "For my Bachelor's degree, I moved to Finland and studied at Hame University of Applied Sciences" and emitted:

```
FINAL(Khuong went to Hame University of Applied Sciences in Finland for his Bachelor's degree
and the University of Virginia in the USA for his Master's degree.)
```

The FINAL was detected, the loop terminated at step 3, and the answer was returned. This is the happy path.

### Analysis

| Metric | Value |
|---|---|
| Steps used | 3 of 10 |
| Token efficiency | High (6,912 — under rate limit) |
| Hallucination risk | None — answer grounded in literal file text |
| Strategy chosen | Map → Zoom In → FINAL |
| Robustness | Handled missing `resume.txt` without crashing |

**Key:** When the corpus contains the exact fact and the system prompt has a clear stop rule (`FINAL(...)`), the RLM loop terminates early and efficiently. The fix to include the explicit university name in `my_life.txt` directly enabled this clean exit.

---

## Trace 2 — "What cuisine does Khuong like?"

**Token usage:** 10,212 | **Steps taken:** 4/10 | **Outcome:** Correct

### Step-by-Step Breakdown

**Step 1 — File Discovery (Map)**

Identical strategy to Trace 1. The model listed files first. Same `(.?)` and `.?grace.md` noise appeared in the output — this confirms the content-tag collision bug is systematic, not random.

**Step 2 — Keyword Search Across Files (Serial Scan)**

```repl
sections = context.split("</file>")
for s in sections:
    if "Khuong" in s:
        if any(word in s.lower() for word in ["cuisine", "food", "like", "favorite", "eat"]):
            keyword_matches.append(s)
```

This was a smart pivot. Instead of directly reading `my_life.txt`, the model ran a semantic keyword scan across the entire corpus. This is a more expensive strategy but defensible for a vague question like "what does Khuong like" — the answer could have been spread across multiple files.

**Anomaly — Wrong file matched first:**

The scan matched `how_it_works.txt` before `my_life.txt` because that file contains the sentence "The model never sees the raw context in its prompt — it must write code to navigate it" alongside the keyword "food" buried in file listing examples. The model printed the first 1,000 characters of this irrelevant section and correctly identified that it was not useful.

This reveals a design trade-off: keyword scanning is recall-oriented (finds everything) but low-precision (finds too much). A vector search on the same query would have ranked `my_life.txt` higher immediately.

**Step 3 — Targeted Read + Sub-LLM Delegation**

```repl
target = "my_life.txt"
match = re.search(pattern, context, re.DOTALL)
if match:
    content = match.group(1)
    answer = llm_query(f"Based on the following text, what cuisine does Khuong like?\n\n{content}")
    print(answer)
```

The model escalated to `llm_query` (a sub-LLM call) rather than extracting the answer with regex directly. This is valid but slightly expensive — the answer was a single explicit sentence at the end of `my_life.txt` that a simple `re.search(r"favorite cuisines", ...)` would have found deterministically.

The sub-LLM returned the correct verbatim answer: *"Korean, Japanese, Thai, Vietnamese, American, Mexican, and Kiwi."*

**Noise in REPL output:**

```
REPL output: [RLM] sub-LLM query: Based on the following text...
DEBUG_LOG: 22:34:15: sub-LLM query: Based on the following text...
Khuong's favorite cuisines are Korean, Japanese, Thai, Vietnamese, American, Mexican, and Kiwi.
```

The observation injected into the model's next turn included internal system log lines, not just the clean sub-LLM answer. This happened because `self.log()` was writing to the same stdout buffer that `execute_sandbox_code` was capturing. This is a logging contamination bug. The model correctly parsed through the noise to extract the real answer, but the log lines were wasting context tokens.

**Step 4 — Answer and Termination**

```
FINAL(Khuong's favorite cuisines are Korean, Japanese, Thai, Vietnamese, American, Mexican, and Kiwi.)
```

FINAL detected, loop terminated at step 4.

### Analysis

| Metric | Value |
|---|---|
| Steps used | 4 of 10 |
| Token efficiency | Moderate (10,212 — under rate limit but higher than Trace 1) |
| Hallucination risk | None — answer grounded in file text |
| Strategy chosen | Map → Serial Scan → Zoom In + Sub-LLM → FINAL |
| Robustness | Handled irrelevant match, extracted correct answer through log noise |

**Key:** The model correctly self-corrected after the keyword scan returned a noisy result. However, it over-delegated to a sub-LLM when a deterministic regex would have sufficed. This inflated token cost by approximately 3,000 tokens compared to Trace 1.

---

## Trace 3 — "Tell me about Khuong's project GRACE"

**Token usage:** 16,591 | **Steps taken:** 4/10 | **Outcome:** Partial / Interrupted

### Step-by-Step Breakdown

**Step 1 & 2 — Exploration**
The model correctly listed files and located `projects/grace.md`.

**Step 3 — Zoom-in**
The model read `projects/grace.md` in its entirety using a `re.search` block. The REPL returned a large block of text (the full project abstract and analysis).

**Step 4 — Final Answer (The Bracket Failure)**
The model attempted to provide a comprehensive summary starting with:
`FINAL(GRACE (Graph Reasoning with Adaptive Correlated Equilibrium) is a project developed by Khuong...)`

**Anomaly — Improper Termination:**
The system reported `FINAL detected (63 chars)`. 

### Analysis

| Metric | Value |
|---|---|
| Steps used | 4 of 10 |
| Token efficiency | **Critical** (16,591 — exceeded rate limit) |
| Strategy chosen | Map → Zoom In → FINAL |

**Finding: The Parentheses Nesting Bug**
The current `FINAL\((.*?)\)` regex uses a non-greedy match. Because the project title included its own parentheses, the regex captured everything up to the *first* closing bracket: `GRACE (Graph Reasoning with Adaptive Correlated Equilibrium`.
The rest of the model's high-quality synthesis was discarded. This explains why the "thinking process" showed a long response but the UI only showed a fragment.

---

## Findings

### 1. Content-Tag Collision (Systematic Bug)

Both traces produced garbage entries like `(.?)` and `.?grace.md` in the file listing. These are regex artifacts from documentation content embedded inside `how_it_works.txt`. The fix is to escape angle brackets in file content before wrapping them in `<file>` tags inside `build_corpus`, or to use a more unique tag delimiter that is unlikely to appear in natural text.

### 2. Logging Contamination (Bug — Fixed)

The sub-LLM log lines leaked into the REPL stdout in Trace 2 due to `self.log()` writing to the same capture buffer. This was caught and fixed by changing the logger to use Python's `logging` module instead of `print`. The fix ensures only intentional `print()` calls appear in REPL observations.

### 3. Over-Delegation to Sub-LLM

When the answer is a deterministic string fragment (a list, a date, a name), the model tends to delegate to `llm_query` anyway. This is a prompt engineering gap — the system prompt does not distinguish between questions that require reasoning (use `llm_query`) versus questions that require extraction (use regex). A targeted instruction could reduce sub-LLM calls by 30-50% for simple factual queries.

### 4. Early Termination — The System Working Correctly

Both traces terminated well before the 10-step limit. The updated system prompt's explicit rule — "STOP generating immediately after closing a repl block" — successfully prevented the auto-regressive hallucination loop observed in the earlier session (where the model fabricated `Output:` blocks and invented University of Washington). The comparison between the old hallucinating trace and these clean traces is a direct A/B validation of that prompt fix.

## TODO

### Content-Tag Collision in build_corpus

Files whose content contains <file name='...'> strings (e.g., how_it_works.txt documentation examples) leak fake filenames into the agent's file listing. 

Fix: HTML-escape angle brackets in file content before wrapping, or switch to a more unique delimiter like <<<FILE:filename>>>.

### Logging Contamination into REPL stdout

self.log() calls inside llm_query_callback write to stdout, which gets captured by the execute_sandbox_code buffer and injected back into the model's next observation. 

Fix: route internal logs through Python's logging module instead of print.

### Over-delegation to sub-LLM for simple extractions
The agent calls llm_query() for factual retrieval questions (lists, names, dates) that a single re.search could answer deterministically. 

Fix: expand the system prompt with a guideline like "prefer Python regex for verbatim extraction; only call llm_query when reasoning or synthesis is required"

### Hallucination stop sequence not enforced at the API level
The prompt has a rule saying STOP after a repl block, but the Gemini API has no hard stop sequence configured. The model can still violate this rule. 

Fix: pass stop_sequences=["Output:", "Observation:"] to GenerateContentConfig as a safety net.

### Include Trace Engine
UI not display option to enable Trace Engine. Intentional for now as not neccessary with eerything can be pretty much traced in thinking process window, but may want to enable it in future

### Parentheses Nesting in FINAL extraction
The current regex `FINAL\((.*?)\)` fails when the answer itself contains parentheses (e.g., "Project (GRACE) description"). 

Fix: Refactor the parser to use a stack-based bracket counter or a more robust greedy regex that stops at the *last* closing parenthesis of a line.