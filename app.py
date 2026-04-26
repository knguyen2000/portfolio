"""
Main entry point for the portfolio Streamlit app.
Orchestrates UI layout, agent mode selection, chat rendering, and document viewing.
"""
import streamlit as st
import os

# --- Internal Imports ---
from config.app_config import (
    PAGE_TITLE, PAGE_ICON, PAGE_LAYOUT,
    MODE_FILE_BASED, MODE_VECTOR_RAG,
    AVAILABLE_MODES, DEFAULT_MODE_INDEX,
)
from styles import APP_CSS, WARNING_STYLE
from state import init_session_state, log_event
from engines.trace_engine import load_corpus
from utils.sidebar import render_sidebar

from components.chat_renderer import render_chat_history, render_document_viewer
from components.agent_dispatch import generate_answer
from utils.guestbook_db import init_db
from components.editor_panel import render_editor_panel

# --- Page Config ---
st.set_page_config(layout=PAGE_LAYOUT, page_title=PAGE_TITLE, page_icon=PAGE_ICON)
st.markdown(APP_CSS, unsafe_allow_html=True)

# --- Data Ingestion ---
def get_dir_mtime(dir_path: str = "data") -> float:
    """Returns the latest modification time of any file in the directory."""
    if not os.path.exists(dir_path):
        return 0.0
    max_mtime = 0.0
    for root, _, files in os.walk(dir_path):
        for f in files:
            mtime = os.path.getmtime(os.path.join(root, f))
            max_mtime = max(max_mtime, mtime)
    return max_mtime

@st.cache_data
def get_cached_corpus(mtime: float):
    return load_corpus()

# By passing the latest mtime, the cache automatically invalidates if any file is edited manually!
docs = get_cached_corpus(get_dir_mtime("data"))

# --- LLM Setup ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")

client = None
if api_key:
    from google import genai
    client = genai.Client(api_key=api_key)
else:
    st.warning("Please set GOOGLE_API_KEY to enable AI features.")

# --- Session State ---
init_session_state()
init_db()

# --- Sidebar ---
render_sidebar()

# ------------------------------------------------------------------
# Main UI
# ------------------------------------------------------------------
try:
    st.markdown("<h1 class='main-header'>Hey there! Ask me anything about Khuong</h1>", unsafe_allow_html=True)

    # --- Agent Mode Selector ---
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        agent_mode = st.radio(
            "Select Agent Mode",
            AVAILABLE_MODES,
            horizontal=True,
            label_visibility="collapsed",
            index=DEFAULT_MODE_INDEX,
        )

    # --- Mode Description & Verify Toggle ---
    if agent_mode in (MODE_FILE_BASED, MODE_VECTOR_RAG):
        _, col_center, _ = st.columns([1, 1, 1])
        with col_center:
            btn_label = "✅ Verify ON" if st.session_state.verify_enabled else "🔍 Verify Sources"
            btn_type = "primary" if st.session_state.verify_enabled else "secondary"
            if st.button(btn_label, type=btn_type, use_container_width=True):
                st.session_state.verify_enabled = not st.session_state.verify_enabled
                st.rerun()

            if st.session_state.verify_enabled:
                st.markdown("<p style='text-align: center; color: gray; font-size: 0.85em;'><i>Click highlighted text in the answers to see the source and suggest edits to my portfolio!</i></p>", unsafe_allow_html=True)

            if agent_mode == MODE_FILE_BASED:
                st.markdown(f"<p style='{WARNING_STYLE}'>⚠️ Least efficient mode, consumes most tokens. Good for small docs, but slow for large portfolios.</p>", unsafe_allow_html=True)
            elif agent_mode == MODE_VECTOR_RAG:
                st.markdown(f"<p style='{WARNING_STYLE}'>⚡ Lowest token usage. Fast and cheap, but may miss context if retrieval fails (enable 'Verify Sources' to check).</p>", unsafe_allow_html=True)
    else:
        st.session_state.verify_enabled = False
        _, col_center, _ = st.columns([1, 2, 1])
        with col_center:
            st.markdown(f"<p style='{WARNING_STYLE}'>⚠️ Full data access, but takes long time to conclude final answer and more likely to get hallucinate (can be traced in thinking status)</p>", unsafe_allow_html=True)

    # Always use columns to keep the DOM context stable across reruns.
    # When the doc panel is closed, the chat column simply takes the full width.
    if st.session_state.view_doc:
        col_chat, col_docs = st.columns([3, 2])
    else:
        (col_chat,) = st.columns([1])  # Full width; single col keeps DOM context stable
        col_docs = None

    # ------------------------------------------------------------------
    # Chat History Rendering
    # ------------------------------------------------------------------
    with col_chat:
        render_chat_history()

    # ------------------------------------------------------------------
    # Chat Input
    # ------------------------------------------------------------------
    if prompt := st.chat_input("Ask about my skills..."):
        log_event("User Input received")
        st.session_state.messages.append({"role": "user", "content": prompt})
        log_event("Appended user msg -> Rerunning")
        st.rerun()

    # ------------------------------------------------------------------
    # Generate Answer
    # ------------------------------------------------------------------
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        if client:
            prompt_text = st.session_state.messages[-1]["content"]
            generate_answer(client, agent_mode, prompt_text, docs, api_key)
        else:
            st.error("AI model not configured.")

    # ------------------------------------------------------------------
    # Document Viewer Panel
    # ------------------------------------------------------------------
    if col_docs:
        with col_docs:
            if st.session_state.get("editing_doc"):
                render_editor_panel(docs)
            else:
                render_document_viewer(docs)

except Exception as main_e:
    st.error(f"Critical Application Error: {main_e}")
    st.exception(main_e)

# --- Let It Snow ---
if not st.session_state.has_snowed:
    st.snow()
    st.session_state.has_snowed = True
