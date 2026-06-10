# Vector RAG Agent

Semantic search + **Retrieval-Augmented Generation** agent using vector embeddings.

## Files

- `vector_agent.py` — Main agent implementation
- `vector_store.py` — Vector database (ChromaDB) interface

## How It Works

1. User query is embedded using Gemini Embeddings 2
2. Vector store searches for semantically similar chunks
3. Top K results are ranked by similarity score
4. Selected chunks are passed to Gemini with query
5. Gemini generates response grounded in retrieved context

## When to Use

✓ Want semantic relevance (not just keyword matching)  
✓ Large corpus of documents  
✓ Need to find conceptually similar content  
✓ Trade-off: More complex, better retrieval  

## Configuration

From `config/app_config.py`:
```python
VECTOR_CONFIDENCE_HIGH = 70     # High confidence threshold
VECTOR_CONFIDENCE_LOW = 30      # Low confidence threshold
VECTOR_CAUTION_THRESHOLD = 35   # Warning threshold
```

## Vector Store

The `VectorEngine` in `vector_store.py`:
- Stores embeddings in ChromaDB (in `chroma_db/`)
- Builds on first run by embedding all documents
- Supports semantic search and filtering

```python
from agents.vector.vector_store import VectorEngine

ve = VectorEngine(api_key=api_key, model_id="models/gemini-embedding-2-preview")
results = ve.search("query", k=5)
# Returns: {'chunks': [...], 'metadatas': [...], 'distances': [...]}
```

## Interface

```python
from agents.vector.vector_agent import VectorRAGAgent

agent = VectorRAGAgent(client, model_id, api_key=api_key)
response, token_stats = agent.completion(user_query, verify_enabled=True)
```

## Related

- **File-Based** — Simple context passing without search
- **RLM** — Recursive refinement with planning
- **NLA** — Activation interpretation (no retrieval)
