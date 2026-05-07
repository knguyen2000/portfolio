"""
Main entry point for the portfolio Streamlit app.
Orchestrates UI layout, agent mode selection, chat rendering, and document viewing.
"""
import streamlit as st
import os

# --- Internal Imports ---
from config.app_config import (
    PAGE_TITLE, PAGE_ICON, PAGE_LAYOUT,
    MODE_FILE_BASED, MODE_VECTOR_RAG, MODE_RLM,
    AVAILABLE_MODES, DEFAULT_MODE_INDEX,
)
from styles import APP_CSS, WARNING_STYLE
from state import init_session_state, log_event
from engines.trace_engine import load_corpus
from utils.sidebar import render_sidebar

from components.chat_renderer import render_chat_history, render_document_viewer
from components.agent_dispatch import generate_answer, check_and_set_checkpoint, resume_from_checkpoint
from utils.guestbook_db import init_db
from utils.workflow_db import init_db as init_workflow_db
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
_raw_docs = get_cached_corpus(get_dir_mtime("data"))

# Exclude internal-only files that are not meant for user-facing RAG retrieval.
# portfolio_capabilities.md is used only by the Workflow Intelligence classifier;
# including it causes the AI to see near-duplicate content and repeat answers.
_INTERNAL_DOCS = {"data/portfolio_capabilities.md", "data\\portfolio_capabilities.md"}
docs = {k: v for k, v in _raw_docs.items() if k not in _INTERNAL_DOCS}

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
init_workflow_db()

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

    # Always use columns to keep the DOM context stable across reruns.
    # When the doc panel is closed, the chat column simply takes the full width.
    if st.session_state.view_doc:
        col_chat, col_docs = st.columns([3, 2])
    else:
        (col_chat,) = st.columns([1])
        col_docs = None

    with col_chat:
        # --- Feature Bar (Reasoning & Verification) ---
        show_verify = agent_mode in (MODE_FILE_BASED, MODE_VECTOR_RAG)
        feat_cols = st.columns(2) if show_verify else [st.container()]
        
        # 1. Reasoning Mode (Global)
        with feat_cols[0]:
            ckpt_on = st.session_state.get("checkpoint_enabled", True)
            ckpt_label = "🧠 Thinking" if ckpt_on else "⚡ Instant"
            ckpt_type = "primary" if ckpt_on else "secondary"
            if st.button(ckpt_label, type=ckpt_type, use_container_width=True, key="ckpt_toggle_btn"):
                st.session_state.checkpoint_enabled = not ckpt_on
                st.rerun()
                
        # 2. Verify Sources
        if show_verify:
            with feat_cols[1]:
                verify_on = st.session_state.get("verify_enabled", False)
                verify_label = "✅ Verify: ON" if verify_on else "🔍 Verify Sources"
                verify_type = "primary" if verify_on else "secondary"
                if st.button(verify_label, type=verify_type, use_container_width=True, key="verify_btn"):
                    st.session_state.verify_enabled = not verify_on
                    st.rerun()

        # Mode Description & Warnings
        if agent_mode == MODE_FILE_BASED:
            st.markdown(f"<p style='{WARNING_STYLE}'>⚠️ Retrieval Strategy: <b>Full Document Context</b>. Highest accuracy, but high token usage.</p>", unsafe_allow_html=True)
        elif agent_mode == MODE_VECTOR_RAG:
            st.markdown(f"<p style='{WARNING_STYLE}'>⚡ Retrieval Strategy: <b>Semantic Search (RAG)</b>. Fast and low token usage, but may miss context (enable 'Verify' to check).</p>", unsafe_allow_html=True)
        elif agent_mode == MODE_RLM:
            st.markdown(f"<p style='{WARNING_STYLE}'>🧠 Multi-Step Reasoning: Likely to consume the most tokens and take the longest to complete.</p>", unsafe_allow_html=True)

        if st.session_state.get("verify_enabled") and show_verify:
            st.markdown("<p style='text-align: center; color: gray; font-size: 0.85em; margin-top: -10px;'><i>Click highlighted text in answers to see sources!</i></p>", unsafe_allow_html=True)

        st.markdown("---")

    # ------------------------------------------------------------------
    # Chat History Rendering
    # ------------------------------------------------------------------
    with col_chat:
        # --- Pre-Render Checkpoint Cleanup ---
        pending_ckpt = st.session_state.get("pending_checkpoint")
        if pending_ckpt and pending_ckpt.get("status") == "user_responded":
            # Remove the checkpoint message so it vanishes instantly
            st.session_state.messages = [m for m in st.session_state.messages if not m.get("checkpoint")]
            
            # Update the user's original message to reflect their clarification
            user_decision = pending_ckpt.get("user_decision", "approved")
            user_edit = pending_ckpt.get("user_edit", "")
            if user_edit and user_decision == "edited":
                for m in reversed(st.session_state.messages):
                    if m["role"] == "user":
                        if f"*(Clarified: {user_edit})*" not in m["content"]:
                            m["content"] += f"\n\n*(Clarified: {user_edit})*"
                        break

        render_chat_history()

        # ------------------------------------------------------------------
        # Generate Answer (checkpoint-aware)
        # ------------------------------------------------------------------
        pending_ckpt = st.session_state.get("pending_checkpoint")

        if pending_ckpt and pending_ckpt.get("status") == "user_responded":
            # User responded to a checkpoint — resume generation
            if client:
                resume_from_checkpoint(client, agent_mode, docs, api_key)
            else:
                st.error("AI model not configured.")

        elif st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            if client:
                prompt_text = st.session_state.messages[-1]["content"]
                # Pre-generation checkpoint check (may set pending_checkpoint and rerun)
                if not check_and_set_checkpoint(client, prompt_text):
                    generate_answer(client, agent_mode, prompt_text, docs, api_key)
            else:
                st.error("AI model not configured.")

    # ------------------------------------------------------------------
    # Chat Input
    # ------------------------------------------------------------------
    if prompt := st.chat_input("Ask about my skills..."):
        log_event("User Input received")
        st.session_state.turn_tokens = 0
        st.session_state.messages.append({"role": "user", "content": prompt})
        log_event("Appended user msg -> Rerunning")
        st.rerun()

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
