"""
Application configuration and constants.
"""

from utils.image_data import image_to_data_uri

# --- Page Config ---
PAGE_TITLE = "Meet Khuong"
# Data URI (not a file path): file paths are served via Streamlit's media manager,
# whose /favicon.png and /media/... URLs can 500 on Streamlit Cloud. Emoji fallback.
PAGE_ICON = image_to_data_uri("static/panda_eat.png", max_width=64) or "🐼"
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
MODE_NLA = "NLA (Natural Language Autoencoder)"
MODE_VOICE = "Voice"

AVAILABLE_MODES = [MODE_FILE_BASED, MODE_RLM, MODE_VECTOR_RAG, MODE_NLA, MODE_VOICE]
DEFAULT_MODE_INDEX = 2  # Vector RAG

# --- Vector RAG Thresholds ---
VECTOR_CONFIDENCE_HIGH = 70
VECTOR_CONFIDENCE_LOW = 30
VECTOR_CAUTION_THRESHOLD = 35

# --- Modal NLA Endpoint ---
# Override this when switching Modal accounts via: modal profile activate <profile-name>
MODAL_NLA_ENDPOINT = "https://knguyen2000--portfolio-nla-web-generate.modal.run"

# --- Checkpoint Config ---
CHECKPOINT_ENABLED_DEFAULT = True
CHECKPOINT_TYPES = [
    "interpretation_confirmation",
    "direction_choice",
    "assumption_confirmation",
]
