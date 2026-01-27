import re
import io
import sys
import contextlib
from google import genai
from google.genai import types
from rlm.utils.prompts import RLM_SYSTEM_PROMPT

class RLMAgent:
    def __init__(self, client, model_id, docs=None, log_callback=None):
        self.client = client
        self.model_id = model_id
        self.max_steps = 10
        self.history = []
        self.log_callback = log_callback
        
        # Flatten docs into a single global context string
        # If docs is a dict, we format it as pseudo-XML or similar
        self.context = ""
        if docs:
            if isinstance(docs, dict):
                for fname, content in docs.items():
                    self.context += f"\n<file name='{fname}'>\n{content}\n</file>\n"
            else:
                self.context = str(docs)
        
        # Cumulative token usage
        self.token_usage = {'input': 0, 'output': 0, 'total': 0}
        
        # Initialize Persistent REPL Globals
        self.repl_globals = {
            "llm_query": self.llm_query_callback,
            "llm_query_batched": self.llm_query_batched_callback,
            "context": self.context,
            "re": re
        }

    def _update_tokens(self, usage_metadata, manual_prompt_len=0):
        if usage_metadata:
            self.token_usage['input'] += usage_metadata.prompt_token_count or manual_prompt_len
            self.token_usage['output'] += usage_metadata.candidates_token_count or 0
            self.token_usage['total'] += usage_metadata.total_token_count or 0

    def log(self, msg):
        print(f"[RLM] {msg}")
        if self.log_callback:
            self.log_callback(msg)

    def llm_query_callback(self, prompt_text):
        """
        The magic function injected into the REPL.
        It calls the LLM with a simple query (Sub-Agent).
        """
        self.log(f"Wait... Sub-Agent query: {prompt_text[:50]}...")
        try:
            # Create a fresh chat or simple generation for the sub-query
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt_text,
                config=types.GenerateContentConfig(temperature=0)
            )
            self._update_tokens(response.usage_metadata, 0)
            return response.text
        except Exception as e:
            return f"Error in llm_query: {e}"

    def llm_query_batched_callback(self, prompts):
        """
        Batched version of llm_query for Map-Reduce strategies.
        """
        self.log(f"Wait... Sub-Agent scanning {len(prompts)} chunks...")
        results = []
        for p in prompts:
            # TODO: will fix run in parallel in the future
            res = self.llm_query_callback(p)
            results.append(res)
        return results

    def execute_code(self, code):
        """
        Executes code in a sandbox with llm_query injected.
        Captures stdout/stderr.
        """
        # Capture stdout
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        self.repl_globals["print"] = lambda *args, **kwargs: print(*args, file=stdout_capture, **kwargs)

        try:
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                exec(code, self.repl_globals)
            output = stdout_capture.getvalue()
            error = stderr_capture.getvalue()
            return output + ("\nstderr:\n" + error if error else "")
        except Exception as e:
            return f"Execution Error: {e}"

    def completion(self, user_query):
        """
        Main Recursive Loop.
        """
        system_prompt = RLM_SYSTEM_PROMPT

        # Initialize history
        self.history = [
            {"role": "user", "parts": [{"text": system_prompt + "\n\nQuery: " + user_query}]}
        ]
        
        # Reset tokens for this run
        self.token_usage = {'input': 0, 'output': 0, 'total': 0}
        
        # Start the loop
        for step in range(self.max_steps):
            self.log(f"--- Step {step+1} ---")
            
            try:
                # Use chat mode to properly handle history
                past_history = self.history[:-1]

                chat = self.client.chats.create(
                    model=self.model_id,
                    config=types.GenerateContentConfig(temperature=0),
                    history=past_history
                )
                
                # Send the last message
                last_msg = self.history[-1]["parts"][0]["text"]
                response = chat.send_message(last_msg)
                
                self._update_tokens(response.usage_metadata)
                content = response.text
                
                self.history.append({"role": "model", "parts": [{"text": content}]})
                self.log(f"Model: {content}")

                # Check for FINAL (XML)
                if "<FINAL>" in content:
                    match = re.search(r"<FINAL>(.*?)(?:</FINAL>|$)", content, re.DOTALL)
                    if match:
                        return match.group(1).strip(), self.token_usage
                


                # Check for Code
                code_match = re.search(r"```python(.*?)```", content, re.DOTALL)
                if not code_match:
                    code_match = re.search(r"```repl(.*?)```", content, re.DOTALL)
                
                if code_match:
                    code = code_match.group(1).strip()
                    self.log(f"Executing Code:\n{code}")
                    output = self.execute_code(code)
                    self.log(f"Output: {output}")
                    
                    observation_msg = f"Observation:\n{output}"
                    self.history.append({"role": "user", "parts": [{"text": observation_msg}]})
                else:
                    self.history.append({"role": "user", "parts": [{"text": "Continue. Use code if needed or output FINAL()."}]})

            except Exception as e:
                self.history.append({"role": "user", "parts": [{"text": f"Error: {e}"}]})
        
        return "Max steps reached without final answer.", self.token_usage
