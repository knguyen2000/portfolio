# File-Based Agent

Simple agent that uses **only user-uploaded files** as context, without semantic search or embeddings.

## Files

- `file_based_agent.py` — Main agent implementation

## How It Works

1. User uploads files (or uses default portfolio files)
2. Agent passes all file content directly to Gemini
3. Gemini generates response based only on provided files
4. No semantic search, no vector embeddings, no ranking

## When to Use

✓ User wants answers based **only** on specific files  
✓ Simple, direct context passing  
✓ No complex retrieval logic needed  

## Interface

```python
from agents.file_based.file_based_agent import FileBasedAgent

agent = FileBasedAgent(client, model_id)
response, token_stats = agent.completion(user_query)
```

## Output

- `response` — Generated answer (str)
- `token_stats` — Token usage dict {"input": N, "output": M, "total": P}

## Related

- **Vector RAG** — File-based with semantic search ranking
- **RLM** — File-based with recursive refinement
- **NLA** — Activation interpretation (no retrieval)
