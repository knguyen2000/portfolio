import os

import streamlit as st

from components.guestbook import render_guestbook
from engines.trace_engine import load_corpus
from utils.sidebar import render_sidebar

st.set_page_config(layout="wide", page_title="Community Guestbook", page_icon="📝")

render_sidebar()

# Fetch docs for the PR dashboard (if needed for context)
# Since the app uses get_cached_corpus, we can do it here directly:
@st.cache_data
def get_cached_corpus():
    return load_corpus(os.path.join("data"))

docs = get_cached_corpus()

# Render Dashboard
render_guestbook(docs)
