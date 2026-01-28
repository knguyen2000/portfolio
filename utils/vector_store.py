import os
import chromadb
from chromadb.utils import embedding_functions
import hashlib
from google import genai
import streamlit as st

class VectorEngine:
    def __init__(self, api_key, persist_dir="./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.api_key = api_key
        self.genai_client = genai.Client(api_key=api_key)
        
        # Get or Create Collection
        self.collection = self.client.get_or_create_collection(
            name="portfolio_knowledge_base",
            metadata={"hnsw:space": "cosine"} # Cosine similarity
        )

    def get_embedding(self, text):
        models_to_try = ["models/gemini-embedding-001"]
        
        for model in models_to_try:
            try:
                result = self.genai_client.models.embed_content(
                    model=model,
                    contents=text
                )
                return result.embeddings[0].values
            except Exception as e:
                # Store error for debugging
                self.last_error = f"{model}: {e}"
                continue
        
        print(f"Embedding Failed: {self.last_error}")
        return []

    def chunk_text(self, text, chunk_size=1000, overlap=200):
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

    def build_index(self, docs_dict, status_callback=None):
        """
        Re-builds the Vector Index from scratch.
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
        
        total_files = len(docs_dict)
        processed = 0
        
        self.last_error = None # Reset error
        
        for filename, content in docs_dict.items():
            if status_callback: status_callback(f"Processing {filename}...")
            
            # Chunk
            chunks = self.chunk_text(content)
            
            # Embed & Prepare
            for i, chunk in enumerate(chunks):
                # Generate stable ID
                chunk_id = hashlib.md5(f"{filename}_{i}".encode()).hexdigest()
                
                # Embedding
                emb = self.get_embedding(chunk)
                if emb:
                    ids.append(chunk_id)
                    documents.append(chunk)
                    embeddings.append(emb)
                    metadatas.append({"source": filename, "chunk_index": i})
                elif self.last_error and status_callback:
                     # Only report the error once to avoid spamming
                     status_callback(f"❌ Error embedding chunk: {self.last_error}")
                     self.last_error = None # Clear
            
            processed += 1
        
        # Batch Upsert
        if documents:
            if status_callback: status_callback(f"Upserting {len(documents)} chunks to Vector DB...")
            
            # Batch size of 100 to avoid API limits
            batch_size = 50
            for i in range(0, len(documents), batch_size):
                end = i + batch_size
                self.collection.add(
                    ids=ids[i:end],
                    documents=documents[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end]
                )
        
        if status_callback: status_callback("Indexing Complete!")
        return len(documents)

    def search(self, query, k=5):
        """
        Semantic Search
        Returns list of strings (chunks)
        """
        query_emb = self.get_embedding(query)
        if not query_emb:
            return []
            
        results = self.collection.query(
            query_embeddings=[query_emb],
            n_results=k
        )
        
        # Chroma returns structure: {'documents': [[c1, c2..]], 'metadatas': [[m1, m2..]]}
        if results['documents']:
            return results['documents'][0] # Return the list of chunks
        return []
        
    def count(self):
        return self.collection.count()
