import streamlit as st
import streamlit.components.v1 as components
import difflib
from utils.pr_db import get_open_change_requests, update_change_request_status

def generate_html_diff(base_content, proposed_content):
    differ = difflib.HtmlDiff()
    html_diff = differ.make_file(
        base_content.splitlines(), 
        proposed_content.splitlines(), 
        fromdesc="Live Document", 
        todesc="Proposed Changes",
        context=True,
        numlines=3
    )
    # Add some CSS to make it look nicer inside Streamlit
    custom_css = """
    <style>
        table.diff {font-family: Courier; border: medium; width: 100%;}
        .diff_header {background-color: #e0e0e0; font-size: 0.8em; text-align: center;}
        td.diff_header {text-align: right;}
        .diff_next {background-color: #c0c0c0;}
        .diff_add {background-color: #aaffaa;}
        .diff_chg {background-color: #ffff77;}
        .diff_sub {background-color: #ffaaaa;}
    </style>
    """
    return html_diff.replace("<head>", f"<head>{custom_css}")

def render_pr_dashboard(docs):
    st.header("Pull Requests Dashboard")
    
    prs = get_open_change_requests()
    
    if not prs:
        st.info("No open Change Requests.")
        return
        
    for pr in prs:
        with st.expander(f"PR: {pr['document_id']} by {pr['created_by']}"):
            st.write(f"**Status:** {pr['status']}")
            
            # Show diff
            st.subheader("Changes")
            diff_html = generate_html_diff(pr['base_content'], pr['proposed_content'])
            components.html(diff_html, height=400, scrolling=True)
            
            # Review Actions
            if st.session_state.get("user_role") in ["Reviewer", "Admin"]:
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Reject", key=f"reject_{pr['id']}", type="secondary", use_container_width=True):
                        update_change_request_status(pr['id'], "rejected", st.session_state.user_role)
                        st.rerun()
                with col2:
                    if st.button("Approve & Merge", key=f"approve_{pr['id']}", type="primary", use_container_width=True):
                        update_change_request_status(pr['id'], "merged", st.session_state.user_role)
                        
                        # Apply changes to actual file (this assumes file exists in data directory)
                        doc_id = pr['document_id']
                        import os
                        doc_path = os.path.join("data", doc_id)
                        try:
                            with open(doc_path, "w", encoding="utf-8") as f:
                                f.write(pr['proposed_content'])
                            st.success(f"Merged and updated file: {doc_path}")
                            
                            # Clear cache
                            st.cache_data.clear()
                            
                        except Exception as e:
                            st.error(f"Failed to update file: {e}")
                        
                        st.rerun()
            else:
                st.info("You need Reviewer or Admin role to approve or reject.")
