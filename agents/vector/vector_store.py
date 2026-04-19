import os
import re
import time
import hashlib
from typing import Dict, List, Optional, Callable
import chromadb
from google import genai


def _corpus_fingerprint(docs_dict: Dict[str, str]) -> str:
    """
    Compute a stable fingerprint for the given corpus.

    We hash the sorted (filename, content-length, content-md5) tuples so that
    any change to a file — content edit, addition, or deletion — produces a
    different fingerprint. Using content md5 is more reliable than mtime alone
    because mtime can be preserved by some copy tools.
    """
    h = hashlib.md5()
    for fname in sorted(docs_dict.keys()):
        content = docs_dict[fname]
        h.update(fname.encode())
        h.update(str(len(content)).encode())
        h.update(hashlib.md5(content.encode(errors="replace")).hexdigest().encode())
    return h.hexdigest()


class VectorEngine:
    def __init__(self, api_key, persist_dir="./chroma_db", log_callback=None):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.api_key = api_key
        self.genai_client = genai.Client(api_key=api_key)
        self.log_callback = log_callback

        # Get or Create Collection
        self.collection = self.client.get_or_create_collection(
            name="portfolio_knowledge_base",
            metadata={"hnsw:space": "cosine"}  # Cosine similarity
        )

    def is_stale(self, docs_dict: Dict[str, str]) -> bool:
        """
        Return True if the persisted index does not match the current corpus.

        We store the corpus fingerprint as a metadata key on the collection when
        build_index completes. On subsequent calls, we recompute the fingerprint
        and compare. Any file edit, addition, or deletion will cause a mismatch
        and trigger a full rebuild.
        """
        if self.collection.count() == 0:
            return True
        meta = self.collection.metadata or {}
        stored = meta.get("corpus_fingerprint", "")
        return stored != _corpus_fingerprint(docs_dict)

    def get_embedding(self, text: str, max_retries: int = 5) -> List[float]:
        """
        Embed `text` with automatic retry on 429 RESOURCE_EXHAUSTED.

        The Gemini free tier is capped at 100 embed_content requests/minute.
        When we exceed the cap the API returns a retryDelay field (e.g. '33s').
        We parse that delay out of the error message and sleep exactly that long
        before retrying, so the rebuild self-throttles instead of hammering the
        quota indefinitely.
        """
        model = "models/gemini-embedding-001"
        for attempt in range(max_retries):
            try:
                result = self.genai_client.models.embed_content(
                    model=model,
                    contents=text
                )
                return result.embeddings[0].values
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    # Try to extract the suggested retry delay from the error
                    # message. The API returns something like 'retryDelay': '33s'.
                    delay_match = re.search(r"retryDelay.*?(\d+)s", msg)
                    wait = int(delay_match.group(1)) if delay_match else (30 * (attempt + 1))
                    # Add a small buffer so we don't hit the boundary again
                    wait = min(wait + 2, 120)
                    if self.log_callback:
                        self.log_callback(f"⏳ Rate limit hit. Waiting {wait}s before retry {attempt + 1}/{max_retries}...")
                    else:
                        print(f"[VectorEngine] Rate limit. Sleeping {wait}s...")
                    time.sleep(wait)
                else:
                    # Non-rate-limit error — surface immediately
                    self.last_error = f"{model}: {e}"
                    return []

        self.last_error = f"{model}: max retries exceeded"
        return []

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Sliding window chunking"""
        chunks = []
        if not text:
            return chunks

        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)

            # If we are splitting in the middle of a word, try to find a space (heuristic)
            if end < text_len:
                # look back up to 50 chars for a space
                last_space = text.rfind(' ', start, end)
                if last_space != -1 and end - last_space < 50:
                    end = last_space

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start += (chunk_size - overlap)

        return chunks

    def build_index(self, docs_dict: Dict[str, str], status_callback: Optional[Callable] = None) -> int:
        """
        Re-builds the Vector Index from scratch and stamps the new corpus fingerprint.
        docs_dict: {filename: content_string}
        """
        # Clear existing
        if self.collection.count() > 0:
            if status_callback: status_callback("Clearing old index...")
            self.client.delete_collection("portfolio_knowledge_base")
            self.collection = self.client.get_or_create_collection("portfolio_knowledge_base")

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        processed = 0
        total_chunks_expected = sum(
            len(self.chunk_text(content)) for content in docs_dict.values()
        )

        self.last_error = None  # Reset error

        for filename, content in docs_dict.items():
            if status_callback: status_callback(f"Processing {filename}...")

            # Chunk
            chunks = self.chunk_text(content)

            # Embed & Prepare
            for i, chunk in enumerate(chunks):
                # Generate stable ID
                chunk_id = hashlib.md5(f"{filename}_{i}".encode()).hexdigest()

                # Embedding (retries internally on 429)
                emb = self.get_embedding(chunk)
                if emb:
                    ids.append(chunk_id)
                    documents.append(chunk)
                    embeddings.append(emb)
                    metadatas.append({"source": filename, "chunk_index": i})
                elif self.last_error and status_callback:
                    # Only report the error once to avoid spamming
                    status_callback(f"❌ Error embedding chunk: {self.last_error}")
                    self.last_error = None  # Clear

            processed += 1

        # Batch Upsert
        if documents:
            if status_callback: status_callback(f"Upserting {len(documents)} chunks to Vector DB...")

            batch_size = 50
            for i in range(0, len(documents), batch_size):
                end = i + batch_size
                self.collection.add(
                    ids=ids[i:end],
                    documents=documents[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end]
                )

        # Only stamp the fingerprint if the rebuild fully succeeded.
        # A partial rebuild (some chunks skipped due to persistent errors) must
        # NOT be treated as fresh — otherwise is_stale() won't trigger a retry
        # on the next request, silently leaving a degraded index.
        successfully_embedded = len(documents)
        if successfully_embedded == total_chunks_expected:
            fingerprint = _corpus_fingerprint(docs_dict)
            self.collection.modify(metadata={
                "corpus_fingerprint": fingerprint,
            })
            if status_callback: status_callback(f"✅ Indexing complete. Fingerprint: {fingerprint[:8]}...")
        else:
            dropped = total_chunks_expected - successfully_embedded
            if status_callback:
                status_callback(
                    f"⚠️ Partial index: {successfully_embedded}/{total_chunks_expected} chunks embedded "
                    f"({dropped} dropped). Fingerprint NOT stamped — will retry on next query."
                )

        return successfully_embedded

    def search(self, query: str, k: int = 5) -> dict:
        """
        Semantic Search
        Returns dict: {'chunks': [], 'metadatas': [], 'distances': []}
        """
        query_emb = self.get_embedding(query)
        if not query_emb:
            return {"chunks": [], "metadatas": [], "distances": []}

        results = self.collection.query(
            query_embeddings=[query_emb],
            n_results=k
        )

        # Chroma returns structure: {'documents': [[c1, ...]], 'metadatas': [[m1, ...]], 'distances': [[d1, ...]]}
        return {
            "chunks": results['documents'][0] if results['documents'] else [],
            "metadatas": results['metadatas'][0] if results['metadatas'] else [],
            "distances": results['distances'][0] if results['distances'] else []
        }

    def count(self) -> int:
        return self.collection.count()
