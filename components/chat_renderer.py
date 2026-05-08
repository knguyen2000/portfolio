"""
Chat Renderer — Renders the conversation history, checkpoint cards, and
Workflow Intelligence consent UI.
"""
import streamlit as st
import urllib.parse
from st_click_detector import click_detector
from config.app_config import HIGH_TOKEN_WARNING_THRESHOLD
from state import log_event


# ---------------------------------------------------------------------------
# Checkpoint card renderer
# ---------------------------------------------------------------------------

_CHECKPOINT_ICONS = {
    "interpretation_confirmation": "🔍",
    "direction_choice": "🧭",
    "assumption_confirmation": "💡",
}


def _render_checkpoint_card(checkpoint: dict, msg_index: int):
    """Render an interactive checkpoint card with action buttons."""
    ckpt_type = checkpoint.get("checkpoint_type", "")
    icon = _CHECKPOINT_ICONS.get(ckpt_type, "🔍")
    interpretation = checkpoint.get("model_interpretation", "")
    question = checkpoint.get("question", "Is this correct?")
    options = checkpoint.get("options")
    pending = st.session_state.get("pending_checkpoint")
    is_pending = (pending and pending.get("checkpoint_id") == checkpoint.get("checkpoint_id"))
    is_responded = (is_pending and pending.get("status") == "user_responded")
    
    # Only show buttons/form if the checkpoint is active and hasn't been answered yet
    is_active = is_pending and not is_responded

    # Card header
    if ckpt_type == "interpretation_confirmation":
        st.info(f"{icon} **Before I answer, let me confirm my understanding...**")
        st.markdown(f"I interpreted your question as:\n\n> *{interpretation}*")
    elif ckpt_type == "direction_choice":
        st.info(f"{icon} **There are a few ways I could approach this...**")
        st.markdown(f"My initial read: *{interpretation}*")
    elif ckpt_type == "assumption_confirmation":
        st.info(f"{icon} **I'd like to confirm an assumption before answering...**")
        st.markdown(f"I'm assuming: *{interpretation}*")

    st.markdown(f"**{question}**")

    # Options display (for direction_choice)
    if options and len(options) > 1 and is_active:
        st.markdown("Choose a direction:")
        for opt in options:
            st.markdown(f"- {opt}")

    # Action buttons (only for the active/pending checkpoint)
    if is_active:
        with st.form(key=f"checkpoint_form_{msg_index}"):
            # Edit field (shown inside the form)
            edit_text = st.text_input(
                "Clarify your intent (optional):",
                value="",
                placeholder="e.g., I meant specifically about backend experience...",
                key=f"checkpoint_edit_{msg_index}",
            )

            # Direction choice selector
            selected_option = None
            if options and len(options) > 1:
                selected_option = st.radio(
                    "Pick a direction (optional):",
                    options,
                    index=None,  # Do not select by default
                    key=f"checkpoint_option_{msg_index}",
                    horizontal=True,
                )

            st.write("") # Spacer

            col1, col2 = st.columns([1, 1])
            with col1:
                continue_btn = st.form_submit_button("Continue", type="primary", use_container_width=True)
            with col2:
                restart_btn = st.form_submit_button("❌ Start over", use_container_width=True)

            if continue_btn:
                checkpoint_data = st.session_state.pending_checkpoint
                
                # Determine user's intent based on what they filled out
                if edit_text.strip():
                    checkpoint_data["user_decision"] = "edited"
                    checkpoint_data["user_edit"] = edit_text.strip()
                elif selected_option:
                    checkpoint_data["user_decision"] = "edited"
                    checkpoint_data["user_edit"] = f"Focus on: {selected_option}"
                else:
                    checkpoint_data["user_decision"] = "approved"
                    checkpoint_data["user_edit"] = ""
                    
                checkpoint_data["status"] = "user_responded"
                st.session_state.pending_checkpoint = checkpoint_data
                st.rerun()

            elif restart_btn:
                # Remove the checkpoint message and the user's original message
                st.session_state.pending_checkpoint = None
                # Remove the last two messages (user question + checkpoint card)
                if len(st.session_state.messages) >= 2:
                    st.session_state.messages = st.session_state.messages[:-2]
                else:
                    st.session_state.messages = []
                st.rerun()
    elif is_responded:
        # Show a subtle confirmation that the action was received
        st.write("---")
        st.markdown("✅ *Decision received — processing...*")


# ---------------------------------------------------------------------------
# Main chat history renderer
# ---------------------------------------------------------------------------

def render_chat_history():
    """Renders the chat history from session state and handles click detections."""
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.write(msg["content"])
            else:
                # Check if this is a checkpoint message
                if msg.get("checkpoint"):
                    _render_checkpoint_card(msg["checkpoint"], i)
                    continue

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
                html_to_render = msg.get("html_content")
                
                if not html_to_render:
                    st.write(msg["content"])
                    continue

                # Click-to-verify rendering
                content_id = len(msg["content"])
                base_key = f"msg_{i}_{content_id}"
                
                # Create a dynamic key for the component to force unmount/remount on column resize
                instance_key = f"{base_key}_{st.session_state.get('rerun_id', 0)}"
                
                # Look up the last known click state
                prev_val = st.session_state.clicked_states.get(base_key, "")
                
                # st_click_detector in React 18 Strict Mode mounts twice and appends to innerHTML twice, causing duplicate text.
                # By wrapping our HTML in a unique class and hiding subsequent siblings of that class,
                # => hide the duplicate iframe
                unique_class = f"click-wrapper-{i}-{content_id}"
                css_hack = f"<style>.{unique_class} ~ .{unique_class} {{ display: none !important; }}</style>"
                
                safe_html = f"{css_hack}<div class='{unique_class}' style='height: 100%; overflow-y: auto; padding-bottom: 10px;'>{html_to_render}</div>"
                
                from st_click_detector import click_detector
                current_val = click_detector(safe_html, key=instance_key)
                
                if current_val and current_val != prev_val:
                    log_event(f"New click detected on {base_key}: {current_val[:30]}...")
                    st.session_state.clicked_states[base_key] = current_val

                    parts = current_val.split(":::")
                    doc_name = parts[0]
                    highlight_text = None
                    if len(parts) > 1:
                        import urllib.parse
                        highlight_text = urllib.parse.unquote(parts[1])

                    st.session_state.view_doc = doc_name
                    st.session_state.highlight_phrase = highlight_text

                    log_event("Click processed -> Rerunning")
                    st.session_state.rerun_id += 1
                    st.rerun()

    # Workflow Intelligence Consent UX
    if st.session_state.get("pending_concern"):
        concern = st.session_state.pending_concern
        st.markdown("---")
        with st.chat_message("assistant"):
            st.warning("💡 It sounds like this may be a workflow pain point or feature request.")
            st.write("Would you like to share this with Khuong as feedback?")
            
            with st.form(key="concern_form"):
                quote = st.text_area("Feedback details", value=concern.get("original_quote", ""), height=100)
                
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    submit = st.form_submit_button("✅ Submit", type="primary", use_container_width=True)
                with col2:
                    anon = st.form_submit_button("👻 Submit Anonymously", use_container_width=True)
                with col3:
                    cancel = st.form_submit_button("❌ Do not submit", use_container_width=True)
                    
                if submit or anon:
                    from utils.workflow_db import insert_concern
                    concern["original_quote"] = quote
                    if anon:
                        concern["affected_role"] = "Anonymous Visitor"
                    insert_concern(concern, quote)
                    
                    # Update the last assistant message to acknowledge submission
                    for m in reversed(st.session_state.messages):
                        if m["role"] == "assistant":
                            msg_append = f"\n\n✅ Thank you for the feedback! I've securely recorded this as a {concern.get('category', 'feature request')} for Khuong to review."
                            m["content"] += msg_append
                            if m.get("html_content"):
                                m["html_content"] += msg_append.replace("\n", "<br>")
                            break
                    
                    st.session_state.pending_concern = None
                    st.rerun()
                elif cancel:
                    for m in reversed(st.session_state.messages):
                        if m["role"] == "assistant":
                            msg_append = f"\n\nNo problem! I won't submit a request this time. Let me know if there's anything else I can help you find!"
                            m["content"] += msg_append
                            if m.get("html_content"):
                                m["html_content"] += msg_append.replace("\n", "<br>")
                            break
                    st.session_state.pending_concern = None
                    st.rerun()

def render_document_viewer(docs):
    """Renders the source document preview pane on the right."""
    if st.session_state.view_doc:
        doc_is_guestbook = st.session_state.view_doc and "guestbook" in st.session_state.view_doc.lower()
        show_propose_change = st.session_state.get("user_role") in ["Editor", "Admin"] or doc_is_guestbook
        
        if show_propose_change:
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button("Verified Source Context (Click to Close)", type="secondary", use_container_width=True):
                    st.session_state.view_doc = None
                    st.session_state.highlight_phrase = None
                    st.session_state.rerun_id += 1
                    st.rerun()
            with col2:
                if st.button("Propose Change", type="primary", use_container_width=True):
                    st.session_state.editing_doc = st.session_state.view_doc
                    st.rerun()
        else:
            if st.button("Verified Source Context (Click to Close)", type="secondary", use_container_width=True):
                st.session_state.view_doc = None
                st.session_state.highlight_phrase = None
                st.session_state.rerun_id += 1
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
