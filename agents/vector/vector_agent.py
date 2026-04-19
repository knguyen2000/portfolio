from google import genai
from .vector_store import VectorEngine

class VectorRAGAgent:
    def __init__(self, client, model_id, api_key, docs=None, log_callback=None):
        self.client = client
        self.model_id = model_id
        self.api_key = api_key
        self.docs = docs or {}
        self.log_callback = log_callback
        self.token_usage = {'total': 0}

    def log(self, msg):
        import logging
        logging.info(f"[VectorRAG] {msg}")
        if self.log_callback:
            self.log_callback(msg)

    def completion(self, user_query):
        """
        Executes standard Vector RAG.
        Returns: (response_text, token_stats)
        """
        ve = VectorEngine(api_key=self.api_key, log_callback=self.log_callback)
        self.log(f"Vector Database Status: {ve.count()} chunks indexed.")

        if ve.is_stale(self.docs):
            self.log("⚠️ Index is stale or empty — rebuilding...")
            num_chunks = ve.build_index(self.docs, status_callback=self.log)
            self.log(f"✅ Indexed {num_chunks} chunks from {len(self.docs)} files.")
        else:
            self.log("✅ Index is fresh. Using existing index.")

        self.log(f"🔍 Searching knowledge base for: '{user_query}'")
        search_results = ve.search(user_query, k=5)
        
        # Calculate Match Quality (Cosine distance: 0 is 100%, 1.0+ is 0%)
        matches = []
        for chunk, meta, dist in zip(search_results["chunks"], search_results["metadatas"], search_results["distances"]):
            quality = max(0, int((1.0 - dist) * 100))
            matches.append({
                "chunk": chunk, 
                "source": meta.get("source", "Unknown"), 
                "quality": quality
            })

        if not matches:
            self.log("❌ No information found in the database.")
            return "I couldn't find any information about that in my knowledge base.", self.token_usage

        # Group and Log
        source_data = {}
        for m in matches:
            s = m["source"]
            if s not in source_data:
                source_data[s] = {"count": 0, "best_quality": 0}
            source_data[s]["count"] += 1
            source_data[s]["best_quality"] = max(source_data[s]["best_quality"], m["quality"])

        self.log(f"Found {len(matches)} potential segments across {len(source_data)} files:")
        best_overall_quality = 0
        for source, data in source_data.items():
            q = data["best_quality"]
            best_overall_quality = max(best_overall_quality, q)
            # Human-friendly labels
            if q > 70:
                label = f"🟢 High Confidence ({q}%)"
            elif q > 30:
                label = f"🟡 Moderate Confidence ({q}%)"
            else:
                label = f"🔴 Low Confidence ({q}%)"
            self.log(f"  {label} -> {source} ({data['count']} segments)")

        # Prepare context with quality indicators for the LLM
        context_parts = []
        for m in matches:
            context_parts.append(f"[Source: {m['source']}, Match Quality: {m['quality']}%]\n{m['chunk']}")
        
        context_str = "\n---\n".join(context_parts)

        # UI Caution for weak matches
        caution_prefix = ""
        if best_overall_quality < 35:
            caution_prefix = "*(Note: I found some information that might be related, but my confidence is low. Please verify these details.)*\n\n"

        system_prompt = f"""You are a helpful assistant.
        Use the following retrieved context chunks to answer the user's question.

        CONTEXT:
        {context_str}

        Instruction:
        Answer based ONLY on the context provided.
        If the answer is not in the context, say "I couldn't find that in the database."
        """

        self.log("Generating answer...")
        chat = self.client.chats.create(
            model=self.model_id,
            config=genai.types.GenerateContentConfig(temperature=0),
        )
        response = chat.send_message(system_prompt + "\n\nUser Question: " + user_query)

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            self.token_usage['total'] = response.usage_metadata.total_token_count or 0

        return caution_prefix + response.text, self.token_usage
