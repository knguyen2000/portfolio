"""
Insight-Aware RLM Agent (v2)
Implements the 4-phase state machine: EXPLORE → INCUBATE → ILLUMINATE → SYNTHESIZE
with episodic memory, impasse detection, context pruning, and recursive decomposition.

This is a NEW mode that runs alongside the existing RLMAgent (rlm_impl.py).
"""

import re
import io
import json
import random
import contextlib
from google import genai
from google.genai import types
from agents.rlm.prompts.insight_rlm_prompts import (
    EXPLORE_SYSTEM_PROMPT,
    EXPLORE_GENERAL_PROMPT,
    INCUBATE_SYSTEM_PROMPT,
    ILLUMINATE_SYSTEM_PROMPT,
    VERIFY_PROMPT,
    SYNTHESIZE_PROMPT,
)
from agents.rlm.base import build_corpus, execute_sandbox_code

# ── Config ──────────────────────────────────────────────────────────────────
MAX_DEPTH = 2              # Recursive solve depth limit
MAX_STEPS_PER_PHASE = 8    # Steps in EXPLORE before forced incubation
MAX_INCUBATIONS = 2        # Max incubation retries before giving up
STAGNATION_LIMIT = 3       # Consecutive no-finding steps → impasse


class EpisodicMemory:
    """
    Persistent memory that survives context resets.
    Paper §3.3.3 — stores findings, failures, and insights across phases.
    """

    def __init__(self):
        self.findings = []
        self.failed_approaches = []
        self.insights = []

    def log_finding(self, finding):
        if finding and finding not in self.findings:
            self.findings.append(finding)

    def log_failure(self, approach):
        if approach and approach not in self.failed_approaches:
            self.failed_approaches.append(approach)

    def store_insight(self, insight):
        if insight and insight not in self.insights:
            self.insights.append(insight)

    def findings_summary(self):
        if not self.findings:
            return "(none yet)"
        return "\n".join(f"- {f}" for f in self.findings)

    def failed_summary(self):
        if not self.failed_approaches:
            return "(none yet)"
        return "\n".join(f"- {f}" for f in self.failed_approaches)

    def insights_summary(self):
        if not self.insights:
            return "(none yet)"
        return "\n".join(f"- {ins}" for ins in self.insights)

    def serialize(self):
        """Compact summary for re-injection after context reset."""
        parts = []
        if self.findings:
            parts.append("FINDINGS:\n" + self.findings_summary())
        if self.failed_approaches:
            parts.append("FAILED APPROACHES:\n" + self.failed_summary())
        if self.insights:
            parts.append("INSIGHTS:\n" + self.insights_summary())
        return "\n\n".join(parts) if parts else "(empty memory)"


class InsightRLMAgent:
    """
    Insight-Aware RLM Controller.
    Implements EXPLORE → INCUBATE → ILLUMINATE → SYNTHESIZE with recursive depth.
    """

    def __init__(self, client, model_id, docs=None, log_callback=None):
        self.client = client
        self.model_id = model_id
        self.log_callback = log_callback

        # DEBUG: Verify docs
        if self.log_callback:
             if docs and isinstance(docs, dict):
                 self.log_callback(f"🛠️ InsightRLMAgent Init. Docs keys: {list(docs.keys())}")
             else:
                 self.log_callback(f"🛠️ InsightRLMAgent Init. Docs passed? {bool(docs)}")

        self.corpus = build_corpus(docs)

        # Cumulative token usage across ALL calls (main + sub-agents + recursive)
        self.token_usage = {"input": 0, "output": 0, "total": 0}

    # ── Logging ─────────────────────────────────────────────────────────────

    def log(self, msg):
        print(f"[InsightRLM] {msg}")
        if self.log_callback:
            self.log_callback(msg)

    # ── Token Tracking ──────────────────────────────────────────────────────

    def _update_tokens(self, usage_metadata):
        if usage_metadata:
            self.token_usage["input"] += usage_metadata.prompt_token_count or 0
            self.token_usage["output"] += usage_metadata.candidates_token_count or 0
            self.token_usage["total"] += usage_metadata.total_token_count or 0

    # ── REPL Sandbox (reused pattern from original RLM) ─────────────────────

    def _build_repl_globals(self, memory: EpisodicMemory):
        """Create a fresh REPL namespace with CORPUS and tools injected."""
        
        def grep(pattern, context_lines=0):
            """Search corpus for regex pattern and return matching lines."""
            matches = []
            lines = self.corpus.split('\n')
            count = 0 
            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    matches.append(f"Line {i+1}: " + "\n".join(lines[start:end]))
                    count += 1
                    if count >= 20: break
            return matches if matches else [f"Pattern '{pattern}' not found."]

        return {
            "CORPUS": self.corpus,
            "llm_query": self._llm_query,
            "llm_query_batched": self._llm_query_batched,
            "grep": grep,
            "findings": memory.findings,             # Mutable — shared ref
            "failed_approaches": memory.failed_approaches,  # Mutable — shared ref
            "re": re,
            "random": random,
        }

    def execute_code(self, code, repl_globals):
        """Execute code in the sandbox. Captures stdout/stderr."""
        return execute_sandbox_code(code, repl_globals)

    # ── Sub-Agent LLM Calls ─────────────────────────────────────────────────

    def _llm_query(self, prompt_text=""):
        """Stateless sub-agent call (injected into REPL as llm_query)."""
        if not prompt_text:
             return "Error: Please provide a prompt string, e.g. llm_query('What is...?')"

        query_preview = prompt_text.strip()[:150].replace('\n', ' ')
        self.log(f"   🤖 Sub-agent query: {query_preview}{'...' if len(prompt_text) > 150 else ''}")
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt_text,
                config=types.GenerateContentConfig(temperature=0),
            )
            self._update_tokens(response.usage_metadata)
            result = response.text
            result_preview = result.strip()[:200].replace('\n', ' ')
            self.log(f"   📨 Sub-agent response: {result_preview}{'...' if len(result) > 200 else ''}")
            return result
        except Exception as e:
            self.log(f"   ❌ Sub-agent error: {e}")
            return f"Error in llm_query: {e}"

    def _llm_query_batched(self, prompts):
        """Sequential batched sub-agent calls."""
        self.log(f"   🤖 Delegating analysis to sub-agents ({len(prompts)} chunks to process)...")
        results = []
        for i, p in enumerate(prompts):
            self.log(f"   📄 Processing chunk {i+1}/{len(prompts)}...")
            results.append(self._sub_query_silent(p))
        return results

    def _sub_query_silent(self, prompt_text):
        """Sub-agent call without individual logging (used by batched)."""
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

    # ── LLM Chat Helper ─────────────────────────────────────────────────────

    def _chat_turn(self, history):
        """Send the full history to the LLM and get a response."""
        past = history[:-1]
        chat = self.client.chats.create(
            model=self.model_id,
            config=types.GenerateContentConfig(temperature=0),
            history=past,
        )
        last_msg = history[-1]["parts"][0]["text"]
        response = chat.send_message(last_msg)
        self._update_tokens(response.usage_metadata)
        return response.text

    # ── Simple LLM generation (no chat history) ─────────────────────────────

    def _generate(self, prompt):
        """Single-shot generation for incubation/verification/synthesis."""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0),
            )
            self._update_tokens(response.usage_metadata)
            return response.text
        except Exception as e:
            return f"Error: {e}"

    # ── Impasse Detection ──────────────────────────────────────────────

    def _detect_impasse(self, recent_outputs, stagnation_count, step):
        """
        Approximate impasse detection (API-level, no Gnosis/EAS).
        Returns (is_stuck, reason).
        """
        # 1. Stagnation: too many steps with no new findings
        if stagnation_count >= STAGNATION_LIMIT:
            return True, f"No new findings in {STAGNATION_LIMIT} consecutive steps"

        # 2. Repetition: last 3 outputs are very similar (simple check)
        if len(recent_outputs) >= 3:
            last_three = recent_outputs[-3:]
            # Check if outputs are nearly identical (crude but effective)
            if all(self._rough_similarity(last_three[0], o) > 0.85 for o in last_three[1:]):
                return True, "Outputs are repeating (loop detected)"

        # 3. Error loop: consecutive execution errors
        if len(recent_outputs) >= 2:
            if all("Execution Error:" in o for o in recent_outputs[-2:]):
                return True, "Consecutive execution errors"

        # 4. Forced incubation at step limit
        if step >= MAX_STEPS_PER_PHASE - 1:
            return True, f"Reached step limit ({MAX_STEPS_PER_PHASE})"

        return False, ""

    def _rough_similarity(self, a, b):
        """Quick similarity check using character overlap ratio."""
        if not a or not b:
            return 0.0
        a_clean = a.strip().lower()
        b_clean = b.strip().lower()
        if a_clean == b_clean:
            return 1.0
        # Use set intersection on words
        words_a = set(a_clean.split())
        words_b = set(b_clean.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union) if union else 0.0

    # ── Random Chunk Injection (Opportunistic Assimilation) ────────────

    def _get_random_chunk(self, size=500):
        """Grab a random fragment from CORPUS for incubation noise injection."""
        if len(self.corpus) <= size:
            return self.corpus
        idx = random.randint(0, len(self.corpus) - size)
        return self.corpus[idx : idx + size]

    # ── Phase I: EXPLORE ────────────────────────────────────────────────────

    def _summarize_model_intent(self, content):
        """Extract a human-readable description of what the model is doing."""
        # Try to get reasoning text before any code block
        text_before_code = re.split(r'```', content)[0].strip()
        if text_before_code:
            # Get up to 2 sentences, generous limit
            sentences = re.split(r'(?<=[.!?])\s+', text_before_code)
            if len(sentences) >= 2:
                summary = sentences[0].strip() + '. ' + sentences[1].strip()
            else:
                summary = sentences[0].strip()
            if len(summary) > 300:
                summary = summary[:297] + '...'
            return summary

        # Fallback: if model jumped straight to code or FINAL
        if '<FINAL>' in content:
            return 'Formulating final answer based on gathered information'
        if '```python' in content or '```repl' in content:
            return 'Executing code to search the corpus'
        return 'Analyzing results...'

    def _describe_code_action(self, code):
        """Generate a human-friendly description of what the code does."""
        code_lower = code.lower()

        # File listing
        if 're.findall' in code_lower and 'file' in code_lower and 'name' in code_lower:
            return 'Listing available files in the corpus'

        # Map-reduce batch analysis
        if 'llm_query_batched' in code_lower:
            return 'Running map-reduce analysis across multiple files'

        # Sub-agent reasoning
        if 'llm_query' in code_lower:
            # Try to extract what's being asked
            query_match = re.search(r'llm_query\s*\(\s*[f]?["\'](.{10,60})', code)
            if query_match:
                topic = query_match.group(1).rstrip('"\'').strip()
                return f'Asking sub-agent: "{topic}..."'
            return 'Delegating reasoning to sub-agent'

        # File extraction — try to find which file is being accessed
        file_match = re.search(r"['\"]([a-zA-Z0-9_/]+\.\w{2,4})['\"]", code)
        if file_match and ('re.search' in code_lower or 'file' in code_lower):
            filename = file_match.group(1)
            return f'Reading file: {filename}'

        # Keyword search — look for search terms in string literals (skip regex patterns)
        if 're.search' in code_lower or 're.findall' in code_lower:
            # Try to extract target filename
            file_ref = re.search(r"['\"]([\w_]+\.(?:txt|md|pdf|csv))['\"]" , code)
            if file_ref:
                return f'Extracting content from: {file_ref.group(1)}'
            # Try to find a human-readable search term (not regex syntax)
            search_terms = re.findall(r'["\'](\w[\w\s]{2,30})["\']', code)
            # Filter out regex/code patterns
            terms = [t for t in search_terms if not any(c in t for c in ['file', 'name=', 'CORPUS', 'DOTALL', 'match', 'group'])]
            if terms:
                return f'Searching for: "{terms[0]}"'
            return 'Extracting and parsing corpus content'

        # Keyword scan in if-statements
        keyword_match = re.search(r'if\s+["\'](\w[\w\s]+)["\'].*in\s', code)
        if keyword_match:
            return f'Scanning for keyword: "{keyword_match.group(1)}"'

        # Recording findings
        if 'findings.append' in code_lower:
            return 'Recording a new finding'

        # Corpus inspection
        if 'print(corpus' in code_lower or 'print(context' in code_lower:
            return 'Peeking at raw corpus content'

        # Splitting
        if 'split' in code_lower and ('file' in code_lower or 'section' in code_lower):
            return 'Splitting corpus into sections for analysis'

        # Generic print
        if 'print(' in code_lower:
            return 'Extracting and displaying relevant content'

        return 'Executing search code'

    def _summarize_output(self, output):
        """Create a short summary of execution output for the user."""
        if not output or not output.strip():
            return '(no output)'
        if 'Execution Error:' in output:
            # Show the error but trimmed
            return f'⚠️ Code error — model will self-correct'
        if 'Available Files:' in output:
            # Parse file list
            match = re.search(r"\[(.*)\]", output)
            if match:
                files = match.group(1)
                count = files.count("'") // 2
                return f'Found {count} files in the corpus'
            return output[:150]
        # Generic: show first meaningful line, trimmed
        lines = [l.strip() for l in output.strip().split('\n') if l.strip()]
        if lines:
            first = lines[0]
            if len(first) > 200:
                first = first[:197] + '...'
            if len(lines) > 1:
                return f'{first} (+{len(lines)-1} more lines)'
            return first
        return output[:150]

    def _explore(self, query, memory, depth):
        """
        EXPLORE phase: write and execute code to search CORPUS.
        Returns: (result_type, data)
            result_type: "final" | "impasse"
            data: answer string | impasse reason
        """
        indent = '│ ' * depth
        is_general = not self.corpus.strip()
        self.log(f"{indent}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        if is_general:
            self.log(f"{indent}🔍 **Phase 1: EXPLORE** — Reasoning with general knowledge")
        else:
            self.log(f"{indent}🔍 **Phase 1: EXPLORE** — Searching the corpus for relevant information")
        if depth > 0:
            self.log(f"{indent}   (Recursive depth: {depth})")
        self.log(f"{indent}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        repl_globals = self._build_repl_globals(memory)
        explore_prompt = EXPLORE_GENERAL_PROMPT if is_general else EXPLORE_SYSTEM_PROMPT
        history = [
            {"role": "user", "parts": [{"text": explore_prompt + "\n\nQuery: " + query}]}
        ]

        recent_outputs = []
        stagnation_count = 0
        prev_findings_count = len(memory.findings)

        for step in range(MAX_STEPS_PER_PHASE):
            self.log(f"{indent}")
            self.log(f"{indent}📌 **Step {step + 1} of {MAX_STEPS_PER_PHASE}**")

            try:
                content = self._chat_turn(history)
                history.append({"role": "model", "parts": [{"text": content}]})
                
                # Show what the model is thinking (summarized)
                intent = self._summarize_model_intent(content)
                self.log(f"{indent}   💭 Reasoning: {intent}")

                # ── Check for <FINAL> ──
                if "<FINAL>" in content:
                    match = re.search(r"<FINAL>(.*?)(?:</FINAL>|$)", content, re.DOTALL)
                    if match:
                        self.log(f"{indent}   ✅ Answer found!")
                        return "final", match.group(1).strip()

                # ── Check for explicit <IMPASSE> ──
                if "<IMPASSE" in content:
                    reason_match = re.search(r'<IMPASSE\s+reason="(.*?)"', content, re.DOTALL)
                    reason = reason_match.group(1) if reason_match else "Model declared impasse"
                    self.log(f"{indent}   🚧 Model is stuck: {reason}")
                    memory.log_failure(reason)
                    return "impasse", reason

                # ── Execute code if present ──
                code_match = re.search(r"```python(.*?)```", content, re.DOTALL)
                if not code_match:
                    code_match = re.search(r"```repl(.*?)```", content, re.DOTALL)

                if code_match:
                    code = code_match.group(1).strip()
                    action_desc = self._describe_code_action(code)
                    self.log(f"{indent}   ⚙️ Action: {action_desc}")
                    output = self.execute_code(code, repl_globals)
                    output_summary = self._summarize_output(output)
                    self.log(f"{indent}   📋 Result: {output_summary}")
                    recent_outputs.append(output)

                    # Track findings and stagnation
                    if len(memory.findings) > prev_findings_count:
                        # Model explicitly recorded findings — great
                        new_findings = memory.findings[prev_findings_count:]
                        for f in new_findings:
                            f_preview = f[:200] + ('...' if len(f) > 200 else '')
                            self.log(f"{indent}   💡 Finding: {f_preview}")
                        stagnation_count = 0
                        prev_findings_count = len(memory.findings)
                    elif output and len(output.strip()) > 100 and 'Execution Error' not in output:
                        # Model got useful output but didn't record it — auto-record
                        auto_finding = output.strip()[:500]
                        memory.log_finding(f"[Auto-recorded from step {step+1}] {auto_finding}")
                        f_preview = auto_finding[:200] + ('...' if len(auto_finding) > 200 else '')
                        self.log(f"{indent}   💡 Auto-captured finding: {f_preview}")
                        stagnation_count = 0
                        prev_findings_count = len(memory.findings)
                        # Nudge model to use findings.append() itself
                        history.append({"role": "user", "parts": [{"text": f"Observation:\n{output}\n\n(Tip: use findings.append('...') to record important discoveries so they persist across phases.)"}]})
                        continue  # Skip the normal history append below
                    else:
                        stagnation_count += 1

                    history.append({"role": "user", "parts": [{"text": f"Observation:\n{output}"}]})
                else:
                    stagnation_count += 1
                    recent_outputs.append(content[:500])
                    self.log(f"{indent}   ⏳ No code generated — nudging model to continue...")
                    history.append({"role": "user", "parts": [{"text": "Continue. Write Python code to search CORPUS, or output <FINAL> if you have the answer, or <IMPASSE> if stuck."}]})

                # ── Impasse detection ──
                is_stuck, reason = self._detect_impasse(recent_outputs, stagnation_count, step)
                if is_stuck:
                    self.log(f"{indent}   🚧 Impasse detected: {reason}")
                    memory.log_failure(f"EXPLORE step {step + 1}: {reason}")
                    return "impasse", reason

            except Exception as e:
                self.log(f"{indent}   ❌ Error: {e}")
                history.append({"role": "user", "parts": [{"text": f"Error: {e}"}]})
                recent_outputs.append(f"Error: {e}")

        return "impasse", "Exhausted EXPLORE steps"

    # ── Phase II: INCUBATE ──────────────────────────────────────────────────

    def _incubate(self, query, memory, depth):
        """
        INCUBATE phase: reset context, inject noise, generate new strategy.
        Paper §5.1-5.2: Context Pruning + Opportunistic Assimilation.
        Returns: strategy string
        """
        indent = '│ ' * depth
        self.log(f"{indent}")
        self.log(f"{indent}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.log(f"{indent}🧘 **Phase 2: INCUBATE** — Rethinking approach after impasse")
        self.log(f"{indent}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.log(f"{indent}   🧹 Clearing working memory (context pruning)...")
        self.log(f"{indent}   🎲 Injecting random corpus fragment for fresh perspective...")

        random_chunk = self._get_random_chunk()

        if memory.failed_approaches:
            self.log(f"{indent}   📝 Previous failed approaches:")
            for fa in memory.failed_approaches[-3:]:  # Show last 3
                self.log(f"{indent}      • {fa[:100]}")

        prompt = INCUBATE_SYSTEM_PROMPT.format(
            query=query,
            findings_summary=memory.findings_summary(),
            failed_summary=memory.failed_summary(),
            random_chunk=random_chunk,
        )

        self.log(f"{indent}   🔄 Generating new strategy...")
        content = self._generate(prompt)

        # Extract strategy
        strat_match = re.search(r"<STRATEGY>(.*?)</STRATEGY>", content, re.DOTALL)
        if strat_match:
            strategy = strat_match.group(1).strip()
        else:
            strategy = content.strip()

        # Show strategy in a readable way
        strat_preview = strategy[:200] + ('...' if len(strategy) > 200 else '')
        self.log(f"{indent}   💡 New strategy: {strat_preview}")
        return strategy

    # ── Phase III: ILLUMINATE ───────────────────────────────────────────────

    def _illuminate(self, query, strategy, memory, depth):
        """
        ILLUMINATE phase: attempt recursive decomposition or direct re-solve.
        Paper §6.1: Representational Change through decomposition.
        Returns: (result_type, data)
            result_type: "final" | "impasse" | "insights"
            data: answer string | reason | list of insights
        """
        indent = '│ ' * depth
        strat_preview = strategy[:250] + ('...' if len(strategy) > 250 else '')
        self.log(f"{indent}")
        self.log(f"{indent}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.log(f"{indent}💡 **Phase 3: ILLUMINATE** — Trying a different approach")
        self.log(f"{indent}   Strategy: {strat_preview}")
        self.log(f"{indent}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Ask the LLM to either decompose or solve directly
        repl_globals = self._build_repl_globals(memory)
        prompt = ILLUMINATE_SYSTEM_PROMPT.format(
            query=query,
            strategy=strategy,
            findings_summary=memory.findings_summary(),
            failed_summary=memory.failed_summary(),
        )

        history = [{"role": "user", "parts": [{"text": prompt}]}]

        # Give it a few steps to work with the new strategy
        for step in range(MAX_STEPS_PER_PHASE):
            self.log(f"{indent}")
            self.log(f"{indent}📌 **Illuminate Step {step + 1} of {MAX_STEPS_PER_PHASE}**")
            content = self._chat_turn(history)
            history.append({"role": "model", "parts": [{"text": content}]})
            
            intent = self._summarize_model_intent(content)
            self.log(f"{indent}   💭 Reasoning: {intent}")

            # Check for FINAL
            if "<FINAL>" in content:
                match = re.search(r"<FINAL>(.*?)(?:</FINAL>|$)", content, re.DOTALL)
                if match:
                    self.log(f"{indent}   ✅ Answer found via new strategy!")
                    return "final", match.group(1).strip()

            # Check for SUBQUERIES (recursive decomposition)
            if "<SUBQUERIES>" in content:
                sq_match = re.search(r"<SUBQUERIES>(.*?)</SUBQUERIES>", content, re.DOTALL)
                if sq_match:
                    try:
                        sub_queries = json.loads(sq_match.group(1).strip())
                        if isinstance(sub_queries, list) and len(sub_queries) > 0:
                            self.log(f"{indent}   🔀 Decomposing into {len(sub_queries)} sub-queries:")
                            # Recursive solve each sub-query
                            sub_insights = []
                            for i, sq in enumerate(sub_queries):
                                sq_preview = sq[:100] + ('...' if len(sq) > 100 else '')
                                self.log(f"{indent}   📎 Sub-query {i + 1}/{len(sub_queries)}: \"{sq_preview}\"")
                                result = self.solve(sq, depth=depth + 1)
                                sub_insights.append(f"[Sub-query: {sq}]\n{result}")
                                self.log(f"{indent}   ✓ Sub-query {i + 1} resolved")
                            return "insights", sub_insights
                    except json.JSONDecodeError:
                        self.log(f"{indent}   ⚠️ Could not parse decomposition — retrying...")

            # Check for IMPASSE
            if "<IMPASSE" in content:
                self.log(f"{indent}   🚧 Still stuck even with new strategy")
                return "impasse", "Illuminate phase stuck"

            # Execute code if present
            code_match = re.search(r"```python(.*?)```", content, re.DOTALL)
            if not code_match:
                code_match = re.search(r"```repl(.*?)```", content, re.DOTALL)

            if code_match:
                code = code_match.group(1).strip()
                action_desc = self._describe_code_action(code)
                self.log(f"{indent}   ⚙️ Action: {action_desc}")
                output = self.execute_code(code, repl_globals)
                output_summary = self._summarize_output(output)
                self.log(f"{indent}   📋 Result: {output_summary}")
                history.append({"role": "user", "parts": [{"text": f"Observation:\n{output}"}]})
            else:
                self.log(f"{indent}   ⏳ Continuing reasoning...")
                history.append({"role": "user", "parts": [{"text": "Continue. Write code or output <FINAL> or <SUBQUERIES>."}]})

        return "impasse", "Exhausted ILLUMINATE steps"

    # ── Answer Sanitization (pre-verification) ────────────────────────────────

    def _sanitize_answer(self, answer):
        """
        Hard-coded pre-check to catch obvious bad answers BEFORE LLM verification.
        Returns (is_clean, reason).
        """
        if not answer or not answer.strip():
            return False, "Answer is empty"

        # Check for unresolved Python template variables like {variable_name}
        template_vars = re.findall(r'\{[a-zA-Z_][a-zA-Z0-9_]*\}', answer)
        if template_vars:
            return False, f"Answer contains unresolved template variables: {template_vars}"

        # Check for code-like syntax that shouldn't be in a final answer
        code_patterns = [
            (r'print\(', "contains print() calls"),
            (r'def \w+\(', "contains function definitions"),
            (r'import \w+', "contains import statements"),
            (r'for \w+ in ', "contains for loops"),
            (r'\w+\.\w+\(', None),  # method calls — only flag if answer is very short
        ]
        for pattern, reason in code_patterns:
            if reason and re.search(pattern, answer):
                # Only flag if it looks like the answer IS code, not just mentions code
                if len(answer) < 200:
                    return False, f"Answer appears to be code ({reason})"

        return True, ""

    # ── Verification ─────────────────────────────────────────────────

    def _verify_answer(self, query, answer, memory):
        """
        Verify that a proposed answer is consistent with findings.
        Returns True if the answer passes verification.
        """
        self.log("")
        self.log("🔎 **Verifying answer** — Checking consistency with source data...")

        # Step 1: Hard-coded sanitization (catches template vars, code artifacts)
        is_clean, reason = self._sanitize_answer(answer)
        if not is_clean:
            self.log(f"❌ Pre-check failed — {reason}")
            return False

        # Step 2: In General Knowledge mode (no corpus), skip LLM grounding check.
        # The model IS the knowledge source — there are no findings to ground against.
        if not self.corpus.strip():
            self.log("✅ Sanitization passed (General Knowledge mode — no grounding check)")
            return True

        # Step 3: LLM-based verification (only in Portfolio Data mode)
        prompt = VERIFY_PROMPT.format(
            query=query,
            answer=answer,
            findings_summary=memory.findings_summary(),
        )

        content = self._generate(prompt)

        if "<VERDICT>PASS</VERDICT>" in content:
            self.log("✅ Verification passed — answer is consistent with findings")
            return True
        elif "<VERDICT>FAIL</VERDICT>" in content:
            explanation = content.split("</VERDICT>")[-1].strip()[:300] if "</VERDICT>" in content else ""
            self.log(f"❌ Verification failed — {explanation or 'answer contains fabricated information'}")
            return False
        else:
            self.log("⚠️ Verification inconclusive — proceeding with answer")
            return True

    # ── Synthesis ──────────────────────────────────────────────────────

    def _synthesize(self, query, insights):
        """Combine multiple insights into a single coherent answer."""
        self.log("")
        self.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.log("📝 **Phase 4: SYNTHESIZE** — Combining insights into final answer")
        self.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.log(f"   Merging {len(insights)} insight(s)...")

        insights_text = "\n\n".join(insights)

        prompt = SYNTHESIZE_PROMPT.format(
            query=query,
            insights_text=insights_text,
        )

        content = self._generate(prompt)

        # Extract FINAL
        match = re.search(r"<FINAL>(.*?)(?:</FINAL>|$)", content, re.DOTALL)
        if match:
            self.log("   ✅ Final answer synthesized")
            return match.group(1).strip()
        self.log("   ✅ Final answer synthesized")
        return content.strip()

    # ── Master Control Loop ──────────────────────────────────────────

    def solve(self, query, depth=0):
        """
        The master recursive solve loop.
        Returns the answer string (no token stats — those are on self.token_usage).
        """
        indent = '│ ' * depth
        if depth > MAX_DEPTH:
            self.log(f"{indent}⛔ Recursion depth limit reached — returning partial result")
            return "Could not resolve at this depth."

        if depth == 0:
            self.log("🚀 **Starting Insight-Aware RLM**")
            self.log(f"   Query: \"{query[:120]}{'...' if len(query) > 120 else ''}\"")
            self.log("")

        memory = EpisodicMemory()
        incubation_count = 0

        # ── Phase I: EXPLORE ──
        result_type, data = self._explore(query, memory, depth)

        if result_type == "final":
            # Verify before accepting
            if depth == 0 and self._verify_answer(query, data, memory):
                return data
            elif depth > 0:
                return data  # Skip verification for sub-queries to save tokens
            else:
                # Verification failed — treat as impasse
                self.log("🔄 Answer didn't pass verification — switching to incubation...")
                memory.log_failure(f"Answer '{data[:80]}...' failed verification")
                result_type = "impasse"

        # ── Phase II + III: INCUBATE → ILLUMINATE loop ──
        while result_type == "impasse" and incubation_count < MAX_INCUBATIONS:
            incubation_count += 1
            self.log(f"{indent}")
            self.log(f"{indent}🔄 **Retry attempt {incubation_count} of {MAX_INCUBATIONS}**")

            # Phase II: INCUBATE — generate new strategy
            strategy = self._incubate(query, memory, depth)

            # Phase III: ILLUMINATE — execute new strategy / decompose
            result_type, data = self._illuminate(query, strategy, memory, depth)

            if result_type == "final":
                if depth == 0 and not self._verify_answer(query, data, memory):
                    memory.log_failure(f"Illuminated answer failed verification")
                    result_type = "impasse"
                    continue
                return data

            elif result_type == "insights":
                # Sub-queries returned insights — synthesize
                for ins in data:
                    memory.store_insight(ins)
                return self._synthesize(query, data)

        # ── Fallback: synthesize whatever we have ──
        if memory.findings:
            self.log(f"{indent}")
            self.log(f"{indent}⚠️ Could not find a complete answer, but have partial findings")
            return self._synthesize(query, [memory.findings_summary()])
        
        return "I was unable to find a conclusive answer after multiple reasoning attempts."

    # ── Public Entry Point ──────────────────────────────────────────────────

    def completion(self, user_query):
        """
        Main entry point (matches RLMAgent's interface).
        Returns (answer_text, token_stats).
        """
        self.token_usage = {"input": 0, "output": 0, "total": 0}

        answer = self.solve(user_query, depth=0)

        return answer, self.token_usage
