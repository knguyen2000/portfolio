# RLM Prompts — Prompt Templates for Recursive Language Model

This directory contains prompt templates for the RLM agent's planning, refinement, and response generation.

## Files

- `rlm_prompts.py` — **Active** prompts for standard RLM
- `insight_rlm_prompts.py` — Alternative prompts for insight-aware RLM (disabled)

## rlm_prompts.py

Defines templates for:

### 1. Planning Prompt
- Breaks down user query into logical sub-questions
- Generates step-by-step thinking process
- Output: List of sub-questions

### 2. Refinement Prompt
- Takes initial answer and search results
- Refines answer based on retrieved documents
- Iteratively improves quality

### 3. Final Response Prompt
- Generates polished final answer
- Incorporates refinements and feedback
- Formats output for user

## insight_rlm_prompts.py

Alternative approach with **insight awareness**:
- Focuses on key insights from documents
- Emphasizes surprising or important findings
- Currently disabled (see `config/app_config.py`)

To re-enable:
1. Add `MODE_INSIGHT_RLM` to available modes in `config/app_config.py`
2. Update `components/agent_dispatch.py` to route to `InsightRLMAgent`

## Usage

```python
from agents.rlm.prompts.rlm_prompts import (
    PLANNING_PROMPT,
    REFINEMENT_PROMPT,
    FINAL_RESPONSE_PROMPT
)

# Templates are formatted with .format() method
planning_prompt = PLANNING_PROMPT.format(query=user_query)
```

## Prompt Structure

Each prompt includes:
- **System instruction** — Define agent role and task
- **Examples** — Few-shot examples if applicable
- **Output format** — Expected response structure
- **Placeholders** — {query}, {results}, {feedback}, etc.

## When to Modify

Update prompts to:
- ✓ Change reasoning style (more/less detailed)
- ✓ Adjust output format
- ✓ Add domain-specific instructions
- ✓ Improve planning decomposition

**Be careful with:**
- ✗ Breaking expected output format (used by code)
- ✗ Removing key placeholders ({query}, {results}, etc.)
