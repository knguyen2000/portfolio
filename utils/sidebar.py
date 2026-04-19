import streamlit as st
import os
from config.profile import (
    PROFILE_IMAGE_PATH,
    PROFILE_NAME,
    PROFILE_HEADLINE,
    PROFILE_SUBTITLE,
    SOCIAL_LINKS
)

def render_sidebar():
    """Renders the common sidebar profile and navigation."""
    # Hide default Streamlit multi-page nav
    # TODO: Fix. Not effectively work yet
    st.markdown("""
        <style>
            [data-testid="stSidebarNav"] {display: none;}
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        # Back Button - Only on Project Detail View
        if st.query_params.get("project"):
            if st.button("← Back to Projects", use_container_width=True, type="primary"):
                st.query_params.clear()
                st.rerun()
            st.markdown("---")

        # Profile Image & Details
        if os.path.exists(PROFILE_IMAGE_PATH):
            st.image(PROFILE_IMAGE_PATH, width=250)
        
        st.markdown(f"""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
        <div style="text-align: center; margin-top: -10px;">
            <h2 style="margin-bottom: 5px;">{PROFILE_NAME}</h2>
            <p style="font-weight: bold; margin-bottom: 5px;">{PROFILE_HEADLINE}</p>
            <p style="font-style: italic; font-size: 0.9em; color: inherit; opacity: 0.7;">{PROFILE_SUBTITLE}</p>
            <div style="display: flex; justify-content: center; gap: 20px; margin-top: 15px;">
                <a href="{SOCIAL_LINKS.get('linkedin', '#')}" target="_blank" style="text-decoration: none; color: #0077b5; font-size: 28px;">
                    <i class="fa-brands fa-linkedin"></i>
                </a>
                <a href="{SOCIAL_LINKS.get('github', '#')}" target="_blank" style="text-decoration: none; color: inherit; font-size: 28px;">
                    <i class="fa-brands fa-github"></i>
                </a>
                <a href="{SOCIAL_LINKS.get('email', '#')}" style="text-decoration: none; color: #ea4335; font-size: 28px;">
                    <i class="fa-solid fa-envelope"></i>
                </a>
                <a href="{SOCIAL_LINKS.get('resume', '#')}" target="_blank" style="text-decoration: none; color: inherit; font-size: 28px;">
                    <i class="fa-solid fa-address-card"></i>
                </a>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Navigation
        st.page_link("app.py", label="Chat", icon="🐼", use_container_width=True)
        st.page_link("pages/about.py", label="About Me", icon="✈️", use_container_width=True)
        st.page_link("pages/projects.py", label="Projects", icon="🛋️", use_container_width=True)
        st.page_link("pages/gallery.py", label="Gallery", icon="🖼️", use_container_width=True)