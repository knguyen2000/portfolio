import os
import re
import json
from google import genai

class FileBasedAgent:
    def __init__(self, client, model_id, docs=None, log_callback=None):
        self.client = client
        self.model_id = model_id
        self.docs = docs or {}
        self.log_callback = log_callback
        self.token_usage = {'total': 0}

    def log(self, msg):
        import logging
        logging.info(f"[FileBasedAgent] {msg}")
        if self.log_callback:
            self.log_callback(msg)

    def completion(self, user_query, chat_history=None, verify_enabled=False):
        """
        Executes File-Based Context retrieval.
        Returns: (response_text, token_stats)
        """
        # Use all docs passed in directly (no summaries needed)
        available_docs = self.docs
        
        if not available_docs:
            self.log("⚠️ No documents found.")

        # Router: select relevant files
        if verify_enabled:
            self.log("Router: Analyzing query...")
            doc_index = {}
            for name, content in available_docs.items():
                L = len(content)
                if L < 2000:
                    preview = content
                else:
                    start = content[:600]
                    mid_idx = L // 2
                    mid = content[mid_idx-300 : mid_idx+300]
                    end = content[-600:]
                    preview = f"{start}\n...\n{mid}\n...\n{end}"
                doc_index[name] = preview

            index_str = "\n".join([f"- {name}: {preview}" for name, preview in doc_index.items()])

            router_prompt = f"""
            You are a data librarian.
            User Query: "{user_query}"

            Available Documents:
            {index_str}

            Task: Return a JSON list of filenames that are relevant to the query.
            Example: ["file1.txt", "file2.pdf"]
            Return ONLY the JSON list. If no specific document is needed, return all filenames.
            """

            router_chat = self.client.chats.create(model=self.model_id)
            router_response = router_chat.send_message(router_prompt)

            selected_files = list(available_docs.keys())
            try:
                json_match = re.search(r'\[.*\]', router_response.text, re.DOTALL)
                if json_match:
                    parsed_files = json.loads(json_match.group(0))
                    valid_files = [f for f in parsed_files if f in available_docs]
                    if valid_files:
                        selected_files = valid_files
                self.log(f"Router selected: {selected_files}")
            except Exception as e:
                self.log(f"Router Parse Error: {e}. using all docs.")
                selected_files = list(available_docs.keys())
        else:
            self.log("Verify OFF - using all docs (Fast Mode)")
            selected_files = list(available_docs.keys())

        self.log("Constructing context...")
        relevant_context = "\n\n".join([f"--- SOURCE: {name} ---\n{available_docs[name]}" for name in selected_files])

        system_prompt_text = f"You are a professional portfolio assistant.\nKnowledge Base: {relevant_context}\n\n1. Answer the user's question directly and naturally.\n2. You MUST use exact, verbatim phrases from the Knowledge Base to support your claims.\n3. Do NOT use markdown bold (**) or italics or any marks to specify which part are from knowledge.\n4. Always refer to the portfolio owner in the third person (he, him, his, Khuong) and NEVER use first-person pronouns (I, me, my, mine).\n5. Do not just dump raw text; synthesize the answer."

        # Chat history
        formatted_history = []
        if chat_history:
            for m in chat_history:
                if m.get("content"):
                    role = "model" if m.get("role") == "assistant" else "user"
                    formatted_history.append({"role": role, "parts": [{"text": m["content"]}]})

        chat = self.client.chats.create(
            model=self.model_id,
            config=genai.types.GenerateContentConfig(
                temperature=0,
                system_instruction=system_prompt_text
            ),
            history=formatted_history,
        )

        self.log("Generating answer...")
        response = chat.send_message(user_query)
        self.log("Answer received.")

        # Token usage
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            self.token_usage['total'] = response.usage_metadata.total_token_count or 0
            self.log(f"🪙 Tokens: {self.token_usage['total']}")

        return response.text, self.token_usage
