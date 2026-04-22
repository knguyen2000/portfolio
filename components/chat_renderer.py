import streamlit as st
import urllib.parse
from st_click_detector import click_detector
from config.app_config import HIGH_TOKEN_WARNING_THRESHOLD
from state import log_event

def render_chat_history():
    """Renders the chat history from session state and handles click detections."""
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.write(msg["content"])
            else:
                # Token usage
                if "token_usage" in msg and msg["token_usage"]:
                    stats = msg["token_usage"]
                    total_tokens = stats.get('total', 0)
                    st.caption(f"🪙 Tokens: {total_tokens}")

                    if total_tokens > HIGH_TOKEN_WARNING_THRESHOLD:
                        st.warning(f"⚠️ High Token Usage ({total_tokens}).")

                # Debug steps
                if msg.get("debug_steps"):
                    with st.status("🧠 Thinking Process", state="complete", expanded=False):
                        for step in msg["debug_steps"]:
                            st.write(step)

                # Render HTML or plain text
                if not msg.get("html_content"):
                    st.write(msg["content"])
                    continue

                # Click-to-verify rendering
                current_val = click_detector(msg["html_content"], key=f"msg_{i}")
                prev_val = st.session_state.clicked_states.get(i)

                if current_val and current_val != prev_val:
                    log_event(f"New click detected on msg_{i}: {current_val[:30]}...")
                    st.session_state.clicked_states[i] = current_val

                    parts = current_val.split(":::")
                    doc_name = parts[0]
                    highlight_text = None
                    if len(parts) > 1:
                        highlight_text = urllib.parse.unquote(parts[1])

                    st.session_state.view_doc = doc_name
                    st.session_state.highlight_phrase = highlight_text

                    log_event("Click processed -> Rerunning")
                    st.rerun()

def render_document_viewer(docs):
    """Renders the source document preview pane on the right."""
    if st.session_state.view_doc:
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Verified Source Context (Click to Close)", type="secondary", use_container_width=True):
                st.session_state.view_doc = None
                st.session_state.highlight_phrase = None
                st.rerun()
        with col2:
            doc_is_guestbook = st.session_state.view_doc and "guestbook" in st.session_state.view_doc.lower()
            if st.session_state.get("user_role") in ["Editor", "Admin"] or doc_is_guestbook:
                if st.button("Propose Change", type="primary", use_container_width=True):
                    st.session_state.editing_doc = st.session_state.view_doc
                    st.rerun()

        st.success(f"Source: {st.session_state.view_doc}")

    current_doc_name = st.session_state.view_doc
    if current_doc_name in docs:
        content = docs[current_doc_name]
        highlight_phrase = st.session_state.get("highlight_phrase")

        if highlight_phrase:
            idx = content.find(highlight_phrase)
            if idx != -1:
                start_idx = max(0, idx - 1000)
                end_idx = min(len(content), idx + len(highlight_phrase) + 1000)

                snippet = content[start_idx:end_idx]
                if start_idx > 0:
                    snippet = "... " + snippet
                if end_idx < len(content):
                    snippet = snippet + " ..."

                highlighted_content = snippet.replace(
                    highlight_phrase,
                    f"<span style='background-color: #d4edda; color: #155724; padding: 2px; border-radius: 3px; font-weight: bold;'>{highlight_phrase}</span>",
                )
                st.markdown(highlighted_content, unsafe_allow_html=True)
            else:
                st.warning("Match location lost. Showing full text.")
                st.markdown(content)
        else:
            st.markdown(content)
