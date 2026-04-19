"""
Recursive Language Model (RLM) agent — portfolio implementation.

The main loop:
  1. Send (system prompt + query) to the model.
  2. Parse response for code blocks and final answer.
  3. If FINAL/FINAL_VAR found -> return it.
  4. If code blocks found -> execute ALL of them, append observations.
  5. Otherwise nudge the model to continue.
  6. After `max_steps`, ask the model one last time for a final answer
"""

import re

from google.genai import types

from agents.rlm.prompts.rlm_prompts import RLM_SYSTEM_PROMPT
from agents.rlm.base import build_corpus, execute_sandbox_code, format_execution_result


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_CODE_BLOCK_REGEX = re.compile(
    r"```(?:repl|python)\s*\n(.*?)\n```",
    re.DOTALL,
)

_FINAL_VAR_REGEX = re.compile(r"^\s*FINAL_VAR\((.*?)\)", re.MULTILINE | re.DOTALL)
_FINAL_REGEX = re.compile(r"^\s*FINAL\((.*?)\)", re.MULTILINE | re.DOTALL)

# Keep REPL observations bounded so one runaway print() can't blow the context budget
_MAX_OBSERVATION_CHARS = 20_000


def find_code_blocks(text):
    """Return every ```repl``` (or ```python) code block found in `text`."""
    return [m.group(1).strip() for m in _CODE_BLOCK_REGEX.finditer(text)]


def find_final_answer(text, repl_globals=None):
    """
    Return the final answer string if `text` contains FINAL(...) or
    FINAL_VAR(...) at the start of a line; otherwise None.

    FINAL_VAR resolves the variable against `repl_globals` so the model
    can return a buffer it built up during reasoning.
    """
    m = _FINAL_VAR_REGEX.search(text)
    if m:
        var_name = m.group(1).strip().strip("\"'")
        if repl_globals is not None and var_name in repl_globals:
            return str(repl_globals[var_name])
        return f"[FINAL_VAR error: variable '{var_name}' not found in REPL]"

    m = _FINAL_REGEX.search(text)
    if m:
        return m.group(1).strip()

    return None


def _truncate(text, limit=_MAX_OBSERVATION_CHARS):
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated {len(text) - limit} chars]"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class RLMAgent:
    """
    Portfolio RLM agent backed by the Google GenAI SDK.

    Parameters
    ----------
    client      : google.genai.Client
    model_id    : model name string passed to `client.chats.create`
    docs        : dict[str, str] — the corpus (bundled into `context`)
    log_callback: optional callable(str) for UI-visible debug logs
    max_steps   : hard iteration cap. Gold uses 30; portfolio defaults to 10
                  to stay under the 15K-TPM free-tier budget.
    """

    def __init__(self, client, model_id, docs=None, log_callback=None, max_steps=10):
        self.client = client
        self.model_id = model_id
        self.max_steps = max_steps
        self.log_callback = log_callback

        if self.log_callback:
            if docs and isinstance(docs, dict):
                self.log_callback(f"🛠️ RLMAgent init. Docs: {list(docs.keys())}")
            else:
                self.log_callback(f"🛠️ RLMAgent init. Docs passed? {bool(docs)}")

        # Bundle docs into the `context` string the model is taught to navigate.
        self.context = build_corpus(docs)

        # Cumulative token usage across root + sub-LLM calls.
        self.token_usage = {"input": 0, "output": 0, "total": 0}

        # Persistent REPL namespace
        self.repl_globals = {
            "llm_query": self.llm_query_callback,
            "llm_query_batched": self.llm_query_batched_callback,
            "context": self.context,
            "re": re,  # pre-imported for convenience, matches what the prompt uses
        }

        # Gemini-format chat history ([{role: "user"|"model", parts:[{text}]}])
        self.history = []

    # ------------------------------------------------------------------
    # Logging + token accounting
    # ------------------------------------------------------------------

    def log(self, msg):
        print(f"[RLM] {msg}")
        if self.log_callback:
            self.log_callback(msg)

    def _update_tokens(self, usage_metadata):
        if not usage_metadata:
            return
        self.token_usage["input"] += usage_metadata.prompt_token_count or 0
        self.token_usage["output"] += usage_metadata.candidates_token_count or 0
        self.token_usage["total"] += usage_metadata.total_token_count or 0

    # ------------------------------------------------------------------
    # Sub-LLM callbacks exposed to the REPL
    # ------------------------------------------------------------------

    def llm_query_callback(self, prompt_text):
        """One-shot sub-LLM call (Gold: _llm_query)."""
        self.log(f"sub-LLM query: {str(prompt_text)[:60]}...")
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt_text,
                config=types.GenerateContentConfig(temperature=0),
            )
            self._update_tokens(response.usage_metadata)
            return response.text
        except Exception as e:
            return f"Error in llm_query: {e}"

    def llm_query_batched_callback(self, prompts):
        """Sequential fan-out (Gold uses concurrent socket dispatch)."""
        self.log(f"sub-LLM batched query x{len(prompts)}")
        return [self.llm_query_callback(p) for p in prompts]

    def execute_code(self, code):
        return execute_sandbox_code(code, self.repl_globals)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _send(self, next_user_msg):
        """
        Send `next_user_msg` to the model using a fresh chat seeded with the
        prior history. Returns the model's response text.

        Using system_instruction puts the system prompt in its own slot,
        as recommended by the Gemini SDK, rather than pasting it into the
        first user turn.
        """
        chat = self.client.chats.create(
            model=self.model_id,
            config=types.GenerateContentConfig(
                temperature=0,
                system_instruction=RLM_SYSTEM_PROMPT,
            ),
            history=self.history,
        )
        response = chat.send_message(next_user_msg)
        self._update_tokens(response.usage_metadata)
        return response.text or ""

    def completion(self, user_query):
        """
        Run the recursive loop. Returns (final_answer_text, token_usage_dict).
        """
        self.token_usage = {"input": 0, "output": 0, "total": 0}
        self.history = []

        # Opening user turn: the query + a nudge to start by exploring.
        opening = (
            f"Query: {user_query}\n\n"
            "You have not yet interacted with the REPL. Start by listing the "
            "files available inside `context` with a ```repl``` block; don't "
            "give a FINAL answer until you have inspected the relevant files."
        )

        next_user_msg = opening

        for step in range(self.max_steps):
            self.log(f"--- step {step + 1}/{self.max_steps} ---")

            try:
                response_text = self._send(next_user_msg)
            except Exception as e:
                # Record the error as an observation so the model can recover.
                self.log(f"Model call failed: {e}")
                self.history.append({"role": "user", "parts": [{"text": next_user_msg}]})
                next_user_msg = f"Previous step failed with error: {e}. Try again."
                continue

            # Persist the round-trip in history before we parse, so that
            # later chat.create() calls see this turn.
            self.history.append({"role": "user", "parts": [{"text": next_user_msg}]})
            self.history.append({"role": "model", "parts": [{"text": response_text}]})
            self.log(f"model: {response_text[:500]}")

            # 1) Is this the final answer?
            final = find_final_answer(response_text, self.repl_globals)
            if final is not None:
                self.log(f"FINAL detected ({len(final)} chars)")
                return final, self.token_usage

            # 2) Are there code blocks to execute?
            code_blocks = find_code_blocks(response_text)
            if code_blocks:
                observations = []
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
                continue

            # 3) Neither. Nudge the model to either act or conclude.
            next_user_msg = (
                "I did not find a ```repl``` block or a FINAL(...) line in "
                "your response. Either run a ```repl``` block to gather more "
                "information, or emit FINAL(answer) / FINAL_VAR(variable) to finish."
            )

        # Max steps exhausted — ask the model once more for a best-effort answer
        self.log("max steps reached, requesting fallback final answer")
        fallback_prompt = (
            "You have used all iterations. Based on everything you have "
            f"observed so far, produce the best possible answer to the original "
            f"query: {user_query!r}\n\n"
            "Respond with a single line: FINAL(your answer)."
        )
        try:
            fallback = self._send(fallback_prompt)
            final = find_final_answer(fallback, self.repl_globals)
            if final is not None:
                return final, self.token_usage
            # Strip any stray FINAL() wrapper; otherwise return raw text.
            return fallback.strip(), self.token_usage
        except Exception as e:
            return (
                f"Max steps reached and fallback failed: {e}",
                self.token_usage,
            )
