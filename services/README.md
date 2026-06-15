# Services — External Integrations & Deployment

This directory contains code for external API integrations and deployed services.

## calendly.py

**Calendly API integration** for the Availability page and chat-based booking.

- `CalendlyClient` — authenticated HTTP client wrapping the Calendly REST API (event types, available times, invitee creation)
- `fetch_event_types()` / `fetch_available_slots()` — high-level helpers for the Availability page
- `detect_scheduling_intent()` — regex-based intent detection for chat messages
- `create_booking()` / `extract_booking_info()` — chat-driven booking flow with LLM-assisted info extraction
- `is_booking_supported()` — returns `False` for NLA mode (no portfolio knowledge)

API token stored in `.streamlit/secrets.toml` as `CALENDLY_API_KEY`.

## modal_nla.py

**NLA (Natural Language Autoencoder) inference service** deployed on Modal.com.

Implements the full three-step NLA **inference** pipeline using pre-trained supervised models:
1. **Qwen2.5-7B-Instruct** — Generate response + extract layer-20 activation
2. **NLA-AV** — Inject activation → generate description (pre-trained Activation Verbalizer)
3. **NLA-AR** — Predict activation → compute FVE score (pre-trained Activation Reconstructor)

All models are loaded from released checkpoints in evaluation mode. No reinforcement learning or retraining occurs—this is pure inference using supervised learning models.

### Deployment

**Prerequisites:**
- Modal CLI installed: `pip install modal`
- Modal account with billing enabled
- HuggingFace token for Qwen model access

**Setup (one-time):**
```bash
# Create HF secret for model authentication
modal secret create huggingface-secret HF_TOKEN=<your-token>

# Pre-download model weights to Modal Volume (optional but faster)
modal run modal_nla.py::download_models

# Deploy the service
modal deploy modal_nla.py
```

**After deployment:**
- Endpoint URL: `https://<org>--portfolio-nla-web-generate.modal.run`
- Update `MODAL_NLA_ENDPOINT` in `config/app_config.py` with the new URL

**Testing:**
```bash
curl -X POST https://<org>--portfolio-nla-web-generate.modal.run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is artificial intelligence?"}'
```

### Switching Modal Accounts

When deploying under a different Modal account:
1. Log in to new account: `modal profile activate <new-profile>`
2. Deploy: `modal deploy services/modal_nla.py`
3. Copy new endpoint URL from deploy output
4. Update `MODAL_NLA_ENDPOINT` in `config/app_config.py`

### Architecture

The Modal service is **independent** of the main Streamlit app:
- The app calls the Modal endpoint via HTTP (see `agents/nla/nla_agent.py`)
- No code changes needed when switching Modal accounts
- Models loaded on first request (lazy initialization)
- 4-bit quantization (NF4) to fit all 3 models on A10G GPU

### Troubleshooting

**"workspace billing cycle spend limit reached"**
- Modal account has hit spending quota
- Upgrade plan or wait for quota reset

**"Modal endpoint unreachable"**
- Verify deployment succeeded: `modal app list`
- Check endpoint URL in `config/app_config.py`
- Verify MODAL_NLA_ENDPOINT points to correct account

**"HF_TOKEN not found"**
- Ensure secret was created: `modal secret list`
- Re-create if needed: `modal secret create huggingface-secret HF_TOKEN=<token>`
