import os
import re
import time
import hashlib
from typing import Dict, List, Optional, Callable
import chromadb
from google import genai


def _corpus_fingerprint(docs_dict: Dict[str, str], model_id: str) -> str:
    """
    Compute a stable fingerprint for the given corpus and model.

    Includes the model_id so that switching embedding models correctly
    invalidates old indices.
    """
    h = hashlib.md5()
    h.update(model_id.encode())
    for fname in sorted(docs_dict.keys()):
        content = docs_dict[fname]
        h.update(fname.encode())
        h.update(str(len(content)).encode())
        h.update(hashlib.md5(content.encode(errors="replace")).hexdigest().encode())
    return h.hexdigest()


class VectorEngine:
    def __init__(self, api_key, model_id, persist_dir="./chroma_db", log_callback=None):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.api_key = api_key
        self.model_id = model_id
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
        return stored != _corpus_fingerprint(docs_dict, self.model_id)

    def get_embedding(self, text: str, max_retries: int = 5) -> List[float]:
        """
        Embed `text` with automatic retry on 429 RESOURCE_EXHAUSTED.
        """
        for attempt in range(max_retries):
            try:
                result = self.genai_client.models.embed_content(
                    model=self.model_id,
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
                    self.last_error = f"{self.model_id}: {e}"
                    return []

        self.last_error = f"{self.model_id}: max retries exceeded"
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
        Incrementally builds the Vector Index. Only re-embeds files that have changed.
        docs_dict: {filename: content_string}
        """
        import json
        meta = self.collection.metadata or {}
        stored_hashes_str = meta.get("file_hashes", "{}")
        stored_model = meta.get("model_id", "")

        try:
            stored_hashes = json.loads(stored_hashes_str)
        except:
            stored_hashes = {}

        # If embedding model changed, force full rebuild
        force_rebuild = (stored_model != self.model_id)

        if force_rebuild:
            if status_callback: status_callback("Model changed or first run. Forcing full rebuild...")
            stored_hashes = {}
            if self.collection.count() > 0:
                self.client.delete_collection("portfolio_knowledge_base")
                self.collection = self.client.get_or_create_collection(
                    name="portfolio_knowledge_base",
                    metadata={"hnsw:space": "cosine"}
                )

        current_hashes = {}
        for filename, content in docs_dict.items():
            current_hashes[filename] = hashlib.md5(content.encode(errors="replace")).hexdigest()

        files_to_embed = []
        files_to_delete = []

        for filename, fhash in current_hashes.items():
            if filename not in stored_hashes or stored_hashes[filename] != fhash:
                files_to_embed.append(filename)
                # If it existed before but changed, we must delete its old chunks
                if filename in stored_hashes:
                    files_to_delete.append(filename)

        for filename in stored_hashes:
            if filename not in current_hashes:
                files_to_delete.append(filename)

        if not files_to_embed and not files_to_delete and not force_rebuild:
            if status_callback: status_callback("✅ Index is already up-to-date.")
            return 0

        # Delete stale chunks
        for filename in files_to_delete:
            if status_callback: status_callback(f"Removing old chunks for {filename}...")
            self.collection.delete(where={"source": filename})

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        self.last_error = None
        failed_files = set()

        for filename in files_to_embed:
            content = docs_dict[filename]
            if status_callback: status_callback(f"Embedding {filename}...")
            chunks = self.chunk_text(content)
            
            file_failed = False
            for i, chunk in enumerate(chunks):
                chunk_id = hashlib.md5(f"{filename}_{i}".encode()).hexdigest()
                emb = self.get_embedding(chunk)
                if emb:
                    ids.append(chunk_id)
                    documents.append(chunk)
                    embeddings.append(emb)
                    metadatas.append({"source": filename, "chunk_index": i})
                else:
                    file_failed = True
                    if self.last_error and status_callback:
                        status_callback(f"❌ Error embedding chunk: {self.last_error}")
                        self.last_error = None
            
            if file_failed:
                failed_files.add(filename)

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

        # Update stored_hashes
        for filename in files_to_delete:
            if filename in stored_hashes and filename not in current_hashes:
                del stored_hashes[filename]

        for filename in files_to_embed:
            if filename not in failed_files:
                stored_hashes[filename] = current_hashes[filename]

        fingerprint = _corpus_fingerprint(docs_dict, self.model_id)
        
        self.collection.modify(metadata={
            "corpus_fingerprint": fingerprint,
            "file_hashes": json.dumps(stored_hashes),
            "model_id": self.model_id
        })

        if failed_files and status_callback:
            status_callback(f"⚠️ Partial index: {len(failed_files)} files failed to embed fully.")
        elif status_callback:
            status_callback(f"✅ Incremental indexing complete.")

        return len(documents)

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
