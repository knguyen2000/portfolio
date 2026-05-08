"""
NLA Agent — Natural Language Activation agent.

Pipeline:
  1. Calls the Modal-hosted Qwen2-0.5B endpoint, which returns a response
     AND activation statistics from layer 12 (real PyTorch forward hooks).
  2. Passes those stats to Gemini to produce a human-readable verbalization:
     "what was the model thinking when it generated this response."

Returns (response_text, token_stats, nla_analysis_dict).
"""
from google.genai import types


_VERBALIZE_PROMPT = """\
You are an interpretability analyst examining the intermediate activations of \
a small language model (Qwen2-0.5B, {hidden_dim} hidden dimensions).

The model was given this user prompt:
<prompt>{prompt}</prompt>

It produced this response:
<response>{response}</response>

These activation statistics were captured at layer {layer} (mid-network), \
at the final input token position — the state the model carries into generation:

  • L2 norm (activation magnitude): {l2_norm}
  • Activation entropy: {entropy}  \
(higher ≈ spread across many dimensions; lower ≈ concentrated on a few)
  • Mean: {mean}, Std: {std}
  • Sequence length processed: {seq_len} tokens
  • Peak-activity token position: {peak_pos} / {seq_len}

In 2–3 sentences, describe:
1. What the model appeared focused on or uncertain about
2. What the entropy level suggests about processing confidence
3. What the peak token position reveals about where the model's attention concentrated

Ground every claim in the numbers above. Do not invent neuron-level details.\
"""


class NLAAgent:
    def __init__(self, client, gemini_model_id, log_callback=None):
        self.client = client
        self.gemini_model_id = gemini_model_id
        self.log_callback = log_callback
        self.token_usage = {"input": 0, "output": 0, "total": 0}

    def log(self, msg):
        print(f"[NLA] {msg}")
        if self.log_callback:
            self.log_callback(msg)

    def _call_modal(self, prompt: str) -> dict:
        try:
            import modal
            NLAModel = modal.Cls.lookup("portfolio-nla", "NLAModel")
            return NLAModel().generate.remote(prompt)
        except Exception as e:
            raise RuntimeError(
                f"Modal endpoint unreachable. Make sure `modal deploy modal_model.py` "
                f"has been run and MODAL_TOKEN_ID / MODAL_TOKEN_SECRET are set. "
                f"Original error: {e}"
            ) from e

    def _verbalize(self, prompt: str, response: str, stats: dict) -> tuple:
        filled = _VERBALIZE_PROMPT.format(
            hidden_dim=stats.get("hidden_dim", "?"),
            prompt=prompt,
            response=response,
            layer=stats.get("layer", "?"),
            l2_norm=stats.get("l2_norm", 0.0),
            entropy=stats.get("entropy", 0.0),
            mean=stats.get("mean", 0.0),
            std=stats.get("std", 0.0),
            seq_len=stats.get("seq_len", 0),
            peak_pos=stats.get("peak_token_pos", 0),
        )
        resp = self.client.models.generate_content(
            model=self.gemini_model_id,
            contents=filled,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        tokens = (resp.usage_metadata.total_token_count or 0) if resp.usage_metadata else 0
        return resp.text, tokens

    def completion(self, user_query: str) -> tuple:
        """Returns (response_text, token_stats, nla_analysis_dict)."""
        self.token_usage = {"input": 0, "output": 0, "total": 0}

        self.log("Calling Modal NLA endpoint (Qwen2-0.5B + activation hooks)...")
        modal_result = self._call_modal(user_query)
        response_text = modal_result.get("response", "")
        stats = modal_result.get("activation_stats", {})

        self.log(
            f"Response received — "
            f"layer={stats.get('layer')}, "
            f"entropy={stats.get('entropy', 0)}, "
            f"L2={stats.get('l2_norm', 0)}"
        )

        self.log("Verbalizing activations via Gemini...")
        verbalization, tokens = self._verbalize(user_query, response_text, stats)
        self.token_usage["total"] += tokens

        nla_analysis = {
            "stats": stats,
            "verbalization": verbalization,
            "model": "Qwen2-0.5B-Instruct",
        }

        return response_text, self.token_usage, nla_analysis
