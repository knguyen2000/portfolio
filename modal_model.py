"""
Modal deployment for NLA (Natural Language Autoencoder) — real paper pipeline.

Full three-step inference using released checkpoints:
  1. Qwen/Qwen2.5-7B-Instruct  →  response + layer-20 activation h_l
  2. kitft/nla-qwen2.5-7b-L20-av  →  inject h_l at ㈎ token → description
  3. kitft/nla-qwen2.5-7b-L20-ar  →  predict ĥ_l from description → FVE

All three models loaded in 4-bit (NF4) on a single A10G (24 GB).
Model weights are cached in a Modal Volume so cold starts after the first
download are fast (~3-5 min instead of ~30 min).

Setup:
    # Create HF secret if models require login (Qwen2.5 needs license accept)
    modal secret create huggingface-secret HF_TOKEN=<your-hf-token>

    # (One-time) pre-download model weights into the volume
    modal run modal_model.py::download_models

    # Deploy
    modal deploy modal_model.py

Endpoint: POST https://<org>--portfolio-nla-web-generate.modal.run
Body: {"prompt": "..."}
Response: {"response": "...", "description": "...", "fve": 0.xx,
           "activation_stats": {"layer": 20, "hidden_dim": 3584, ...}}
"""
import modal

app = modal.App("portfolio-nla")

_volume = modal.Volume.from_name("nla-models", create_if_missing=True)
_MODELS_DIR = "/models"

_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "transformers>=4.46.0",
        "torch>=2.4.0",
        "accelerate>=0.34.0",
        "bitsandbytes>=0.43.0",
        "sentencepiece",
        "safetensors",
        "huggingface_hub",
        "fastapi[standard]",
    )
)

# ── NLA config for Qwen2.5-7B L20 ───────────────────────────────────────────

_BASE_ID = "Qwen/Qwen2.5-7B-Instruct"
_AV_ID   = "kitft/nla-qwen2.5-7b-L20-av"
_AR_ID   = "kitft/nla-qwen2.5-7b-L20-ar"

_LAYER   = 20             # activation extraction layer index
_D_MODEL = 3584           # Qwen2.5-7B hidden dimension
_SCALE   = _D_MODEL**0.5  # injection & mse normalisation scale ~59.87
_INJ_CHAR = "㈎"     # U+320E - single token in Qwen2.5 tokenizer

# Actor (AV) template - injection char sits inside <concept> tags
_AV_TEMPLATE = (
    "You are a meticulous AI researcher conducting an important investigation "
    "into activation vectors from a language model. Your overall task is to "
    "describe the semantic content of that activation vector.\n\n"
    "We will pass the vector enclosed in <concept> tags into your context. "
    "You must then produce an explanation for the vector, enclosed within "
    "<explanation> tags. The explanation consists of 2-3 text snippets "
    "describing that vector.\n\n"
    "Here is the vector:\n\n<concept>㈎</concept>\n\n"
    "Please provide an explanation."
)

# Critic (AR) template — explanation goes inside <text> tags
_AR_TEMPLATE = "Summary of the following text: <text>{explanation}</text> <summary>"


# ── service class (one instance per warm container) ──────────────────────────

class _NLAService:
    def __init__(self):
        import os
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        import torch.nn as nn
        from safetensors.torch import load_file
        from huggingface_hub import hf_hub_download

        hf_token = os.environ.get("HF_TOKEN")

        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )

        def _load(model_id, cache_sub):
            return AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=bnb,
                device_map="auto",
                cache_dir=f"{_MODELS_DIR}/{cache_sub}",
                token=hf_token,
            )

        print("[NLA] Loading tokenizer...")
        self.tok = AutoTokenizer.from_pretrained(
            _BASE_ID,
            cache_dir=f"{_MODELS_DIR}/base",
            token=hf_token,
        )

        print("[NLA] Loading Qwen2.5-7B-Instruct (base)...")
        self.base = _load(_BASE_ID, "base")
        self.base.eval()

        print("[NLA] Loading NLA-AV model...")
        self.av = _load(_AV_ID, "av")
        self.av.eval()

        print("[NLA] Loading NLA-AR backbone (21 layers)...")
        self.ar_bb = _load(_AR_ID, "ar")
        self.ar_bb.eval()

        print("[NLA] Loading value_head.safetensors...")
        vh_path = hf_hub_download(
            repo_id=_AR_ID,
            filename="value_head.safetensors",
            cache_dir=f"{_MODELS_DIR}/ar",
            token=hf_token,
        )
        self.vh = nn.Linear(_D_MODEL, _D_MODEL, bias=False)
        self.vh.load_state_dict(load_file(vh_path))
        # Move to same device as AR backbone, but keep float32 dtype
        # (AR backbone is 4-bit quantized with uint8 dtype, can't move nn.Module to uint8)
        last_p = next(self.ar_bb.model.layers[-1].parameters())
        self.vh.to(device=last_p.device, dtype=torch.float32)
        self.vh.eval()

        # Verify injection char is a single token
        inj_ids = self.tok.encode(_INJ_CHAR, add_special_tokens=False)
        assert len(inj_ids) == 1, f"㈎ must map to one token, got {inj_ids}"
        self._inj_id = inj_ids[0]
        print(f"[NLA] Ready. inj_token_id={self._inj_id}")

    # ── step 1 ────────────────────────────────────────────────────────────

    def _step1(self, prompt: str):
        """Generate response via Qwen2.5-7B-Instruct; capture layer-20 activation."""
        import torch

        msgs = [{"role": "user", "content": prompt}]
        text = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = self.tok(text, return_tensors="pt").to("cuda")
        in_len = inputs["input_ids"].shape[1]

        store = {}
        def _hook(_, __, out):
            if "h" not in store:
                # transformers 5.x may return tensor directly; 4.x returns tuple
                raw = out[0] if isinstance(out, (tuple, list)) else out
                if raw.ndim == 2:
                    raw = raw.unsqueeze(0)  # (seq, d) -> (1, seq, d)
                store["h"] = raw.detach()

        handle = self.base.model.layers[_LAYER].register_forward_hook(_hook)
        with torch.no_grad():
            out_ids = self.base.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=True,
                temperature=0.7,
            )
        handle.remove()

        response = self.tok.decode(out_ids[0][in_len:], skip_special_tokens=True)
        h = store["h"][0, in_len - 1, :].float()  # last input-token hidden state
        return response, h

    # ── step 2 ────────────────────────────────────────────────────────────

    def _step2(self, h) -> str:
        """Inject h into AV model at ㈎ position; generate description."""
        import re, torch

        ids = self.tok(
            _AV_TEMPLATE, return_tensors="pt", add_special_tokens=True
        )["input_ids"].to("cuda")

        with torch.no_grad():
            embeds = self.av.model.embed_tokens(ids).float()  # (1, T, d)

        pos_list = (ids[0] == self._inj_id).nonzero(as_tuple=True)[0]
        if len(pos_list) == 0:
            raise RuntimeError("Injection char not found in tokenised AV template")
        pos = pos_list[0].item()

        # L2-normalise to injection scale and inject
        h_inj = h / h.norm().clamp_min(1e-12) * _SCALE
        embeds[0, pos, :] = h_inj.to(embeds.dtype)

        dtype = next(self.av.parameters()).dtype
        attn = torch.ones(1, embeds.shape[1], dtype=torch.long, device="cuda")

        with torch.no_grad():
            gen_ids = self.av.generate(
                inputs_embeds=embeds.to(dtype),
                attention_mask=attn,
                max_new_tokens=300,
                do_sample=False,
            )

        text = self.tok.decode(gen_ids[0], skip_special_tokens=True)
        m = re.search(r"<explanation>(.*?)</explanation>", text, re.DOTALL)
        return m.group(1).strip() if m else text.strip()

    # ── step 3 ────────────────────────────────────────────────────────────

    def _step3(self, description: str, h_gold) -> float:
        """AR forward pass → predict ĥ_l → FVE ≈ cosine similarity."""
        import torch
        import torch.nn.functional as F

        prompt = _AR_TEMPLATE.format(explanation=description)
        inputs = self.tok(prompt, return_tensors="pt").to("cuda")

        store = {}
        def _hook(_, __, out):
            raw = out[0] if isinstance(out, (tuple, list)) else out
            if raw.ndim == 2:
                raw = raw.unsqueeze(0)
            store["h"] = raw.detach()

        handle = self.ar_bb.model.layers[-1].register_forward_hook(_hook)
        with torch.no_grad():
            self.ar_bb(**inputs)
        handle.remove()

        last_h = store["h"][0, -1, :].float()
        with torch.no_grad():
            pred = self.vh(last_h.unsqueeze(0)).squeeze(0).float()

        # FVE ≈ cosine_similarity when both vectors are normed to _SCALE
        def _norm(v):
            return v / v.norm().clamp_min(1e-12) * _SCALE

        return round(F.cosine_similarity(_norm(pred).unsqueeze(0),
                                         _norm(h_gold).unsqueeze(0)).item(), 4)

    # ── main ──────────────────────────────────────────────────────────────

    def run(self, prompt: str) -> dict:
        import numpy as np

        response, h = self._step1(prompt)

        h_np = h.cpu().numpy()
        abs_v = np.abs(h_np)
        probs = abs_v / (abs_v.sum() + 1e-8)
        entropy = float(-np.sum(probs * np.log(probs + 1e-8)))

        stats = {
            "layer": _LAYER,
            "hidden_dim": _D_MODEL,
            "l2_norm": round(float(np.linalg.norm(h_np)), 4),
            "entropy": round(entropy, 4),
            "seq_len": 1,
        }

        description = self._step2(h)
        fve = self._step3(description, h)

        return {
            "response": response,
            "description": description,
            "fve": fve,
            "activation_stats": stats,
        }


_svc: "_NLAService | None" = None


def _get_svc() -> "_NLAService":
    global _svc
    if _svc is None:
        _svc = _NLAService()
    return _svc


# ── optional: pre-download weights into the volume ────────────────────────────

@app.function(
    image=_image,
    volumes={_MODELS_DIR: _volume},
    timeout=3600,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def download_models():
    """Run once to cache all model weights: `modal run modal_model.py::download_models`"""
    import os
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from huggingface_hub import hf_hub_download

    hf_token = os.environ.get("HF_TOKEN")

    for model_id, sub in [(_BASE_ID, "base"), (_AV_ID, "av"), (_AR_ID, "ar")]:
        print(f"Downloading {model_id}...")
        AutoTokenizer.from_pretrained(model_id, cache_dir=f"{_MODELS_DIR}/{sub}", token=hf_token)
        AutoModelForCausalLM.from_pretrained(model_id, cache_dir=f"{_MODELS_DIR}/{sub}",
                                              token=hf_token)

    hf_hub_download(repo_id=_AR_ID, filename="value_head.safetensors",
                    cache_dir=f"{_MODELS_DIR}/ar", token=hf_token)
    _volume.commit()
    print("Done. All weights cached in volume.")


# ── HTTP endpoint ─────────────────────────────────────────────────────────────

@app.function(
    image=_image,
    gpu="A10G",
    volumes={_MODELS_DIR: _volume},
    scaledown_window=600,
    timeout=900,
    # Add HF secret when models need auth:
    #   modal secret create huggingface-secret HF_TOKEN=<token>
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
@modal.asgi_app()
def web_generate():
    from fastapi import FastAPI
    from pydantic import BaseModel

    fastapi_app = FastAPI()

    class NLARequest(BaseModel):
        prompt: str

    @fastapi_app.post("/")
    def generate(body: NLARequest):
        return _get_svc().run(body.prompt)

    return fastapi_app
