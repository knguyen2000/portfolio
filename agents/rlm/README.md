# RLM Agent — Recursive Language Model

Advanced agent with **planning, refinement, and recursive answering** capabilities.

## Files

- `rlm_agent.py` — Main agent implementation
- `base.py` — Base agent class
- `insight_rlm_agent.py` — Insight-aware RLM variant (disabled)
- `prompts/` — Prompt templates for planning and refinement

## How It Works

1. **Planning Phase** — Break down query into sub-questions
2. **Retrieval Phase** — Search for relevant documents
3. **Refinement Phase** — Iteratively refine answer based on feedback
4. **Response** — Generate final polished response

## When to Use

✓ Complex multi-part questions requiring decomposition  
✓ Need iterative refinement and fact-checking  
✓ Want to see reasoning steps  
✓ Trade-off: More expensive (multiple API calls)  

## Prompts

Located in `prompts/`:
- `rlm_prompts.py` — Planning and refinement templates
- `insight_rlm_prompts.py` — Insight-aware variant (disabled)

Prompts define:
- How to decompose queries
- How to refine answers
- Formatting and output structure

## Interface

```python
from agents.rlm.rlm_agent import RLMAgent

agent = RLMAgent(client, model_id, docs=documents)
response, token_stats = agent.completion(user_query)
```

## Related

- **File-Based** — Simple context passing
- **Vector RAG** — Semantic search without planning
- **NLA** — Activation interpretation (no retrieval)

## Notes

- `insight_rlm_agent.py` is currently disabled (see config)
- Re-enable by adding `MODE_INSIGHT_RLM` to `config/app_config.py`
