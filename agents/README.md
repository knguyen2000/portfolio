# Agents — LLM Agent Implementations

This directory contains different agent implementations that handle user queries through various approaches.

## Structure

```
agents/
├── __init__.py              [Package marker]
├── README.md                [This file]
├── file_based/              [File-based context agent]
├── nla/                     [Natural Language Autoencoder agent]
├── rlm/                     [Recursive Language Model agent]
│   └── prompts/             [RLM prompt templates]
└── vector/                  [Vector RAG agent]
```

## Agents Overview

| Agent | Module | Purpose | Models |
|-------|--------|---------|--------|
| **File-Based** | `file_based/` | Uses only user-uploaded files as context | Gemini |
| **Vector RAG** | `vector/` | Semantic search + retrieval-augmented generation | Gemini + Embeddings |
| **RLM** | `rlm/` | Recursive language model with planning/refinement | Gemini |
| **NLA** | `nla/` | Natural Language Autoencoder (activation interpretation) | Qwen2.5-7B via Modal |

## Agent Interface

All agents implement a consistent interface:

```python
class Agent:
    def __init__(self, client, model_id, **kwargs):
        # Initialize with API client and model
        pass
    
    def completion(self, user_query: str, **kwargs) -> tuple:
        # Returns: (response_text, token_stats, optional_analysis)
        return response, stats, analysis
```

## Adding a New Agent

1. Create new subdirectory: `agents/new_agent/`
2. Add `new_agent.py` with agent class
3. Add `__init__.py` to mark as package
4. Implement `completion()` method
5. Update `components/agent_dispatch.py` to include new agent
6. Add mode to `config/app_config.py`

## Agent Dispatch

All agents are routed through `components/agent_dispatch.py`:
- Routes user queries to selected agent
- Handles errors and retries
- Manages token usage tracking
- Integrates with checkpoint engine and trace engine

## Dependencies

- **config/app_config.py** — Constants, thresholds, available modes
- **state.py** — Session state and logging
- **engines/** — Trace engine, checkpoint engine, workflow intelligence

## Testing an Agent

```python
from agents.vector.vector_agent import VectorRAGAgent

client = # ... initialize API client
agent = VectorRAGAgent(client, model_id="models/gemini-1.5-pro")
response, stats = agent.completion("Your question here")
print(response)
```
