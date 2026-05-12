# NLA Agent — Natural Language Autoencoder

Agent that interprets model **activations as natural language**.

## Files

- `nla_agent.py` — Main agent implementation (calls Modal endpoint)

## How It Works

NLA is a **three-step inference pipeline** using **pre-trained supervised models** (implemented in `services/modal_nla.py`):

1. **Step 1: Response Generation** (Qwen2.5-7B-Instruct)
   - Generate response to user query
   - Extract layer-20 activation vector h_l via forward hook

2. **Step 2: AV (Activation Verbalizer)**
   - Inject h_l at special character ㈎ in prompt template
   - AV model (kitft/nla-qwen2.5-7b-L20-av) generates description
   - Output: Natural language explanation of what h_l represents

3. **Step 3: AR (Activation Reconstructor)**
   - AR model (kitft/nla-qwen2.5-7b-L20-ar) predicts ĥ_l from description
   - Compare predicted vs actual activation
   - Compute **FVE** (Fraction of Variance Explained) ≈ cosine similarity
   - Higher FVE = better explanation (target: 0.60–0.80)

### Training Approach

All three models are **pre-trained checkpoints** loaded in evaluation mode. The inference pipeline is **supervised learning** (not reinforcement learning):
- Qwen2.5-7B-Instruct: standard instruction-tuned LLM
- AV and AR: likely trained with supervised loss to optimize activation explanation quality
- FVE is an **evaluation metric** to measure reconstruction quality, not a training signal

The original NLA paper may describe how the AV and AR models were trained, but this implementation uses only the released checkpoints for inference—no retraining or RL-based refinement at runtime.

## When to Use

✓ Want to understand what the model was "thinking"  
✓ Interpret internal model representations  
✓ Research or analysis (not production grounding)  
✓ Trade-off: Slow, experimental, requires Modal  

## Key Metrics

- **FVE (Fraction of Variance Explained)**
  - Range: [-1, 1]
  - ≥ 0.5 (green): Good reconstruction
  - 0.3–0.5 (orange): Moderate reconstruction
  - < 0.3 (red): Poor reconstruction

- **Entropy** — Activation distribution entropy
- **L2 Norm** — Activation vector magnitude
- **Seq Len** — Sequence position (usually 1)

## Interface

```python
from agents.nla.nla_agent import NLAAgent

agent = NLAAgent(client, model_id)
response, token_stats, nla_analysis = agent.completion(user_query)

# nla_analysis contains:
# {
#     "stats": {"layer": 20, "entropy": 7.78, "l2_norm": 123.1, ...},
#     "verbalization": "Description of what the activation means",
#     "model": "Qwen2.5-7B-Instruct",
#     "fve": 0.9107,
#     "ar_trained": True
# }
```

## Deployment

NLA runs on Modal.com (serverless GPU). See `services/modal_nla.py` for:
- Model initialization
- Inference pipeline
- Endpoint configuration

Endpoint: Configured in `config/app_config.py` as `MODAL_NLA_ENDPOINT`

## Related

- **File-Based** — Simple context passing
- **Vector RAG** — Semantic search (grounded responses)
- **RLM** — Recursive refinement (grounded responses)

## References

- Paper: [Natural Language Autoencoders](https://transformer-circuits.pub/2026/nla/index.html)
- Released checkpoints: Qwen2.5-7B-Instruct, kitft/nla-qwen2.5-7b-L20-av, kitft/nla-qwen2.5-7b-L20-ar
- Special injection character: ㈎ (U+320E, single token in Qwen tokenizer)
