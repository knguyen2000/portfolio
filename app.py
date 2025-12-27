import streamlit as st
import google.generativeai as genai
from st_click_detector import click_detector
import os

from trace_engine import load_corpus, find_maximal_matches

# --- CONFIGURATION ---
st.set_page_config(layout="wide", page_title="John Doe's Verifiable Portfolio")

# --- CSS STYLING FOR HIGHLIGHTS ---
st.markdown("""
<style>
   .verbatim-match {
        background-color: #d4edda; 
        border-bottom: 2px solid #28a745;
        color: #155724;
        cursor: pointer;
        padding: 0 2px;
        border-radius: 3px;
        text-decoration: none;
    }
   .verbatim-match:hover {
        background-color: #c3e6cb;
    }
    .main-header {
        text-align: center;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- DATA INGESTION ---
docs = load_corpus()
full_context = "\n\n".join([f"--- SOURCE: {name} ---\n{content}" for name, content in docs.items()])

# --- TRACE ENGINE (ALGORITHM) ---
# trace_engine.py


# --- LLM SETUP ---
# Retrieve API Key from Secrets or Environment
api_key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        'models/gemini-2.5-flash',
        system_instruction=f"""
        You are a generic professional portfolio assistant.
        Your Knowledge Base consists ONLY of the provided context documents.
        
        Strict Rules:
        1. Grounding: You must answer the user's question using ONLY the facts, dates, and descriptions present in the Knowledge Base.
        2. Abstinence: If the user asks a question that cannot be answered using the Knowledge Base (e.g., "What is the capital of France?", "Write a Python script for me", "What are your political views?"), you must politely refuse. State: "I can only answer questions related to the candidate's professional background and the documents provided."
        3. Tone: Professional, concise, and objective.
        4. Verbatim Preference: When describing specific projects or roles, prefer using the exact phrasing found in the documents to ensure accuracy. This is CRITICAL for the verification engine.
        
        Knowledge Base:
        {full_context}
        """
    )
else:
    st.warning("Please set GOOGLE_API_KEY in .streamlit/secrets.toml or as an environment variable to enable the AI features.")
    model = None

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "view_doc" not in st.session_state:
    st.session_state.view_doc = None

# --- UI LAYOUT ---
st.markdown("<h1 class='main-header'>Verifiable AI Portfolio</h1>", unsafe_allow_html=True)
st.markdown("ask questions about my experience. **Click green highlights** to verify the source.")

col_chat, col_docs = st.columns([3, 2])

with col_chat:
    # Render History
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.write(msg["content"])
            else:
                # Use click_detector for the AI response
                clicked = click_detector(msg["html_content"], key=f"msg_{i}")
                
                # Only rerun if the selection CHANGED to avoid infinite loops
                # ID format can be "doc_name" or "doc_name:::encoded_text"
                if clicked:
                    import urllib.parse
                    parts = clicked.split(":::")
                    doc_name = parts[0]
                    highlight_text = None
                    if len(parts) > 1:
                        highlight_text = urllib.parse.unquote(parts[1])
                    
                    # Check if state changed
                    state_changed = False
                    if doc_name != st.session_state.view_doc:
                        st.session_state.view_doc = doc_name
                        state_changed = True
                    
                    current_highlight = st.session_state.get("highlight_phrase")
                    if highlight_text != current_highlight:
                        st.session_state.highlight_phrase = highlight_text
                        state_changed = True
                    
                    if state_changed:
                        st.rerun()

    # Chat Input
    if prompt := st.chat_input("Ask about my skills..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    # Process latest message if it's from user and we haven't responded
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        # Generate Answer
        if model:
            with st.spinner("Thinking..."):
                try:
                    # Construct history for Gemini
                    gemini_history = []
                    for m in st.session_state.messages:
                        if m["content"]: # Filter out empty messages
                            role = "model" if m["role"] == "assistant" else "user"
                            gemini_history.append({"role": role, "parts": [m["content"]]})
                    
                    # The prompt is already in st.session_state.messages[-1]
                    
                    history_for_chat = gemini_history[:-1]
                    prompt_container = st.session_state.messages[-1]
                    prompt_text = prompt_container["content"]
                    
                    chat = model.start_chat(history=history_for_chat)
                    response = chat.send_message(prompt_text, generation_config={"temperature": 0})

                    # Trace Answer
                    traced_html = find_maximal_matches(response.text, docs)
                    
                    # Add AI message
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response.text,
                        "html_content": traced_html
                    })
                    st.rerun()
                except Exception as e:
                    st.error(f"Error communicating with Gemini: {e}")
        else:
             st.error("AI model not configured.")

with col_docs:
    st.header("Document Viewer")
    doc_names = list(docs.keys())
    
    if not doc_names:
        st.info("No documents found in 'data/' folder.")
    else:
        # Determine which tab to select
        default_index = 0
        if st.session_state.view_doc in doc_names:
            default_index = doc_names.index(st.session_state.view_doc)
            st.success(f"Verified Source: {st.session_state.view_doc}")
        
        # Ensure valid state for the widget
        if st.session_state.view_doc not in doc_names:
            if doc_names:
                st.session_state.view_doc = doc_names[0]
            else:
                 st.session_state.view_doc = None
            
        if st.session_state.view_doc:
            st.radio(
                "Select Document", 
                doc_names, 
                horizontal=True,
                label_visibility="collapsed",
                key="view_doc" # bind to the session state variable
            )
        
        # Render Active Document
        if st.session_state.view_doc:
            current_doc_name = st.session_state.view_doc
            content = docs[current_doc_name]
            
            # Apply highlighting
            highlight_phrase = st.session_state.get("highlight_phrase")
            
            if highlight_phrase:
                 highlighted_content = content.replace(
                     highlight_phrase, 
                     f"<span style='background-color: #d4edda; color: #155724; padding: 2px; border-radius: 3px;'>{highlight_phrase}</span>"
                 )
                 st.markdown(highlighted_content, unsafe_allow_html=True)
            else:
                 st.markdown(content)

