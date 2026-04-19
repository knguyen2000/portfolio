"""
Application configuration and constants.
"""

# --- Page Config ---
PAGE_TITLE = "Meet Khuong"
PAGE_ICON = "static/panda_eat.png"
PAGE_LAYOUT = "wide"

# --- Model Config ---
MODEL_ID = "models/gemma-4-31b-it"
EMBEDDING_MODEL_ID = "models/gemini-embedding-2-preview"

# --- Token Thresholds ---
# Token count above which a rate-limit warning is shown to the user.
HIGH_TOKEN_WARNING_THRESHOLD = 15000

# --- Agent Modes ---
MODE_FILE_BASED = "File-Based Context"
MODE_RLM = "Recursive Language Model (RLM)"
MODE_VECTOR_RAG = "Standard RAG (Vector + Sliding Window)"
# TODO: Re-enable once v2 is finalized
# MODE_INSIGHT_RLM = "Insight-Aware RLM"

AVAILABLE_MODES = [MODE_FILE_BASED, MODE_RLM, MODE_VECTOR_RAG]
DEFAULT_MODE_INDEX = 1  # RLM
