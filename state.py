import streamlit as st
import datetime

def init_session_state():
    """Initialize necessary Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "view_doc" not in st.session_state:
        st.session_state.view_doc = None
    if "verify_enabled" not in st.session_state:
        st.session_state.verify_enabled = False
    if "debug_log" not in st.session_state:
        st.session_state.debug_log = []
    if "clicked_states" not in st.session_state:
        st.session_state.clicked_states = {}
    if "last_html_debug" not in st.session_state:
        st.session_state.last_html_debug = None
    if "has_snowed" not in st.session_state:
        st.session_state.has_snowed = False

def log_event(msg: str):
    """Appends a timestamped message to the debug log and prints it."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    log_msg = f"{ts}: {msg}"
    if "debug_log" in st.session_state:
        st.session_state.debug_log.append(log_msg)
    print(f"DEBUG_LOG: {log_msg}")

def append_response(content: str, html_content=None, debug_steps=None, token_usage=None):
    """Appends an assistant message to session state and reruns."""
    st.session_state.messages.append({
        "role": "assistant",
        "content": content,
        "html_content": html_content,
        "debug_steps": debug_steps or [],
        "token_usage": token_usage or {},
    })
    st.rerun()
