import streamlit as st
import os

def render_sidebar():
    """Renders the common sidebar profile and navigation."""
    with st.sidebar:
        # Back Button - Only on Project Detail View
        if st.query_params.get("project"):
            if st.button("← Back to Projects", use_container_width=True, type="primary"):
                st.query_params.clear()
                st.rerun()
            st.markdown("---")

        # Profile Image & Details
        if os.path.exists("data/KhuongProfile.jpeg"):
            st.image("data/KhuongProfile.jpeg", width=250)
        
        st.markdown("""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
        <div style="text-align: center; margin-top: -10px;">
            <h2 style="margin-bottom: 5px;">Khuong Nguyen</h2>
            <p style="font-weight: bold; margin-bottom: 5px;">Master CS @ UVA</p>
            <p style="font-style: italic; font-size: 0.9em; color: inherit; opacity: 0.7;">Research Interest: NLP, LLM, and Trustworthy AI</p>
            <div style="display: flex; justify-content: center; gap: 20px; margin-top: 15px;">
                <a href="https://www.linkedin.com/in/khuongng/" target="_blank" style="text-decoration: none; color: #0077b5; font-size: 28px;">
                    <i class="fa-brands fa-linkedin"></i>
                </a>
                <a href="https://github.com/knguyen2000" target="_blank" style="text-decoration: none; color: inherit; font-size: 28px;">
                    <i class="fa-brands fa-github"></i>
                </a>
                <a href="mailto:khuongnguyen211000@gmail.com" style="text-decoration: none; color: #ea4335; font-size: 28px;">
                    <i class="fa-solid fa-envelope"></i>
                </a>
                <a href="https://drive.google.com/file/d/1Nx6z3jjxkYVhexlMXxiZLns6Ucg7IR_9/view" target="_blank" style="text-decoration: none; color: inherit; font-size: 28px;">
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