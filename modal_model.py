"""
Modal deployment for NLA (Natural Language Activation) model.

Hosts Qwen2-0.5B-Instruct with a PyTorch forward hook on layer 12
to capture intermediate activations alongside model responses.

Deploy:
    modal deploy modal_model.py

Required secrets for Streamlit Cloud (Settings → Secrets):
    MODAL_TOKEN_ID = "..."
    MODAL_TOKEN_SECRET = "..."

The Streamlit app calls NLAModel().generate.remote(prompt) via the
Modal SDK, which is installed as a normal pip dependency.
"""
import modal

app = modal.App("portfolio-nla")

_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "transformers>=4.46.0",
        "torch>=2.4.0",
        "accelerate>=0.34.0",
        "sentencepiece",
    )
)

_MODEL_ID = "Qwen/Qwen2-0.5B-Instruct"
_HOOK_LAYER = 12  # mid-network; Qwen2-0.5B has 24 layers total


@app.cls(
    image=_image,
    gpu="T4",
    container_idle_timeout=300,
    scaledown_window=600,
)
class NLAModel:
    @modal.enter()
    def load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
        self.model = AutoModelForCausalLM.from_pretrained(
            _MODEL_ID,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        self.model.eval()

    @modal.method()
    def generate(self, prompt: str, max_new_tokens: int = 256) -> dict:
        import numpy as np
        import torch

        activation_store = {}

        def _hook(module, input, output):
            # output is a tuple; index 0 is the hidden state tensor [batch, seq, dim]
            activation_store["hidden"] = output[0].detach().float()

        handle = self.model.model.layers[_HOOK_LAYER].register_forward_hook(_hook)

        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                do_sample=True,
            )

        handle.remove()

        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        response_text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)

        stats = {}
        if "hidden" in activation_store:
            h = activation_store["hidden"][0].cpu().numpy()  # [seq_len, hidden_dim]
            last_h = h[-1]  # final token position — what the model "carries" into generation

            abs_vals = np.abs(last_h)
            probs = abs_vals / (abs_vals.sum() + 1e-8)
            entropy = float(-np.sum(probs * np.log(probs + 1e-8)))

            # Which token position had the highest mean activation magnitude across all dims
            seq_means = np.abs(h).mean(axis=1)
            peak_pos = int(np.argmax(seq_means))

            stats = {
                "layer": _HOOK_LAYER,
                "hidden_dim": int(last_h.shape[0]),
                "l2_norm": round(float(np.linalg.norm(last_h)), 4),
                "entropy": round(entropy, 4),
                "mean": round(float(last_h.mean()), 6),
                "std": round(float(last_h.std()), 4),
                "peak_token_pos": peak_pos,
                "seq_len": int(h.shape[0]),
            }

        return {"response": response_text, "activation_stats": stats}
