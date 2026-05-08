"""
NLA Agent — Natural Language Autoencoder.

Calls the Modal endpoint which runs the full three-step NLA pipeline:
  1. Qwen2.5-7B-Instruct: generate response + extract layer-20 activation
  2. NLA-AV (kitft/nla-qwen2.5-7b-L20-av): inject activation → description
  3. NLA-AR (kitft/nla-qwen2.5-7b-L20-ar): predict activation → FVE score

Returns (response_text, token_stats, nla_analysis_dict).
FVE ≈ cosine similarity under L2-normalisation to sqrt(d_model); range [-1, 1].
"""
import requests

_MODAL_ENDPOINT = "https://knguyen2000--portfolio-nla-web-generate.modal.run"


class NLAAgent:
    def __init__(self, client, gemini_model_id, log_callback=None):
        # client / gemini_model_id kept for API compatibility; not used here
        self.log_callback = log_callback
        self.token_usage = {"input": 0, "output": 0, "total": 0}

    def log(self, msg):
        print(f"[NLA] {msg}")
        if self.log_callback:
            self.log_callback(msg)

    def completion(self, user_query: str) -> tuple:
        """Returns (response_text, token_stats, nla_analysis_dict)."""
        self.token_usage = {"input": 0, "output": 0, "total": 0}

        self.log("Calling Modal NLA endpoint (Qwen2.5-7B + AV + AR)...")
        try:
            resp = requests.post(
                _MODAL_ENDPOINT,
                json={"prompt": user_query},
                timeout=600,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Modal NLA endpoint unreachable. "
                f"Verify `modal deploy modal_model.py` succeeded. Error: {e}"
            ) from e

        response_text = data.get("response", "")
        description = data.get("description", "")
        fve = data.get("fve")
        stats = data.get("activation_stats", {})

        self.log(
            f"layer={stats.get('layer')}, entropy={stats.get('entropy', 0)}, "
            f"fve={fve}"
        )

        nla_analysis = {
            "stats": stats,
            "verbalization": description,
            "model": "Qwen2.5-7B-Instruct",
            "fve": fve,
            "ar_trained": True,
        }

        return response_text, self.token_usage, nla_analysis
