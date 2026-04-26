import streamlit as st
from utils.guestbook_db import create_change_request

def render_editor_panel(docs):
    doc_id = st.session_state.editing_doc
    if doc_id not in docs:
        st.error(f"Document not found: {doc_id}")
        if st.button("Back"):
            st.session_state.editing_doc = None
            st.rerun()
        return

    import os
    file_path = os.path.join("data", doc_id)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()
    except Exception as e:
        st.error(f"Failed to load raw document: {e}")
        return
    
    st.subheader(f"Suggesting Edits to: {doc_id}")
    
    # Simple editor
    proposed_content = st.text_area("Edit Document Content", value=original_content, height=600)
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.session_state.editing_doc = None
            st.rerun()
            
    with col2:
        if st.button("Submit Suggestion", type="primary", use_container_width=True):
            if proposed_content == original_content:
                st.warning("No changes detected.")
            else:
                user_id = st.session_state.get("user_role", "Unknown")
                request_id = create_change_request(doc_id, original_content, proposed_content, user_id)
                st.success(f"Suggestion submitted! ID: {request_id}")
                st.session_state.editing_doc = None
                st.rerun()
