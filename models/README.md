# Models — Local Model Storage

This directory is reserved for **locally cached model files**.

## Purpose

Store downloaded or quantized models here when you want to:
- Cache large models locally to avoid repeated downloads
- Store fine-tuned model weights
- Keep private/custom models separate from code

## Current Setup

Models are currently **not** stored locally:
- **Qwen2.5-7B** — Downloaded from HuggingFace on first run (via Modal)
- **Vector embeddings** — Generated dynamically via Gemini API
- **NLA models** — Downloaded by Modal service (cached in Modal Volume)

## If You Add Local Models

Example structure:
```
models/
├── qwen2.5-7b-instruct/
│   ├── config.json
│   ├── pytorch_model.bin
│   └── tokenizer.model
├── embeddings/
│   └── ... embedding model files
└── nla/
    └── ... NLA checkpoint files
```

## When to Use This

- ✓ Storing quantized/fine-tuned models for local testing
- ✓ Custom model weights for specialized tasks
- ✓ Backup copies of critical models

**Do NOT use for:**
- ✗ Development/test files (use temp directories instead)
- ✗ Data (use `data/` directory)
- ✗ Code (use main codebase directories)
