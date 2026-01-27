import re
import io
import sys
import contextlib
from google import genai
from google.genai import types

class RLMAgent:
    def __init__(self, client, model_id, docs=None, log_callback=None):
        self.client = client
        self.model_id = model_id
        self.max_steps = 10
        self.history = []
        self.docs = docs or {}
        self.log_callback = log_callback
        
        # Cumulative token usage
        self.token_usage = {'input': 0, 'output': 0, 'total': 0}

    def _update_tokens(self, usage_metadata):
        if usage_metadata:
            self.token_usage['input'] += usage_metadata.prompt_token_count or 0
            self.token_usage['output'] += usage_metadata.candidates_token_count or 0
            self.token_usage['total'] += usage_metadata.total_token_count or 0 or 0

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
            self._update_tokens(response.usage_metadata, len(response.text))
            return response.text
        except Exception as e:
            return f"Error in llm_query: {e}"

    def execute_code(self, code):
        """
        Executes code in a sandbox with llm_query injected.
        Captures stdout/stderr.
        """
        # Capture stdout
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        # Globals for the REPL
        # We inject 'llm_query' so the code can call it.
        repl_globals = {
            "llm_query": self.llm_query_callback,
            "docs": self.docs,
            "print": lambda *args, **kwargs: print(*args, file=stdout_capture, **kwargs)
        }

        try:
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                exec(code, repl_globals)
            output = stdout_capture.getvalue()
            error = stderr_capture.getvalue()
            return output + ("\nstderr:\n" + error if error else "")
        except Exception as e:
            return f"Execution Error: {e}"

    def completion(self, user_query):
        """
        Main Recursive Loop.
        """
        system_prompt = """
You are a Recursive Language Model (RLM) agent.
You can access, transform, and analyze this context interactively in a REPL environment that can recursively query sub-LLMs.

TOOLS AVAILABLE:
1. Python REPL: You can execute python code. Use the following format:
```repl
print("Hello")
```

2. llm_query(prompt: str) -> str:
   A special function available in the REPL. Use it to ask simple questions to a sub-agent.
   Example:
```repl
fact = llm_query("What is the capital of France?")
print(f"The capital is {fact}")
```

3. docs variable:
   You have access to a global dictionary `docs` containing the knowledge base.
   - Keys: Filenames (str)
   - Values: File content (str)
   You can use python to read, search, or summarize these documents.
   Example:
```repl
print(docs.keys())
content = docs['my_life.txt']
print(content[:100])
```

INSTRUCTIONS:
- Break down complex problems.
- Use `llm_query` to look up facts or perform sub-tasks.
- You can use python to process data, do math, or manipulate strings.
- When you have the final answer, you MUST output it in this format:
FINAL(The Answer Here)

Do not return FINAL until you are sure.
        """

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
                # We separate the last message as the one to 'send'
                current_msg_parts = self.history[-1]["parts"][0]["text"]
                past_history = self.history[:-1]

                chat = self.client.chats.create(
                    model=self.model_id,
                    config=types.GenerateContentConfig(temperature=0),
                    history=past_history
                )
                
                response = chat.send_message(current_msg_parts)
                self._update_tokens(response.usage_metadata)
                content = response.text
                
                self.history.append({"role": "model", "parts": [{"text": content}]})
                self.log(f"Model: {content}")

                # Check for FINAL
                if "FINAL(" in content:
                    match = re.search(r"FINAL\((.*?)\)", content, re.DOTALL)
                    if match:
                        return match.group(1), self.token_usage
                    else:
                        return content, self.token_usage # Fallback

                # Check for Code
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
