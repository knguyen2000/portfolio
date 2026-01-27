import streamlit as st
from st_click_detector import click_detector
import os
import json
import re

# --- LOGIC IMPORT ---
from trace_engine import load_corpus, find_maximal_matches
from utils.sidebar import render_sidebar
from rlm_impl import RLMAgent

# --- CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Meet Khuong", page_icon="data/panda_eat.png")

# --- HIDE DEFAULT SIDEBAR IMMEDIATELY (MIGHT STILL APPEAR ONCE LOADED BUT TBD IN FUTURE) ---
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
""", unsafe_allow_html=True)


# --- CSS STYLING FOR HIGHLIGHTS & LAYOUT ---
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
    
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
        position: sticky;
        top: 4rem;
        align-self: flex-start;
        max-height: 90vh;
        overflow-y: auto;
    }
    div[role="radiogroup"], div[data-testid="stRadio"] > div {
        display: flex;
        justify-content: center;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- DATA INGESTION ---
docs = load_corpus()
full_context = "\n\n".join([f"--- SOURCE: {name} ---\n{content}" for name, content in docs.items()])

# --- LLM SETUP ---
# Retrieve API Key from Secrets or Environment
api_key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")

client = None
if api_key:
    from google import genai
    client = genai.Client(api_key=api_key)
    MODEL_ID = 'models/gemma-3-27b-it' 
else:
    st.warning("Please set GOOGLE_API_KEY to enable AI features.")

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "view_doc" not in st.session_state:
    st.session_state.view_doc = None
if "verify_enabled" not in st.session_state:
    st.session_state.verify_enabled = False

# --- ADMIN UPLOAD ---
# Just temporal for testing, permanent upload is TBD
render_sidebar()
with st.sidebar:

    if st.button("Reset Conversation"):
        st.session_state.messages = []
        st.session_state.view_doc = None
        st.session_state.highlight_phrase = None
        st.rerun()
    st.markdown("---")

    # Collapsible Admin Section
    with st.expander("Admin Access"):
        passcode = st.text_input("Passcode", type="password")
        
        # Retrieve Admin Passcode
        admin_pass = st.secrets.get("ADMIN_PASSCODE") or os.getenv("ADMIN_PASSCODE") or "1234"
        
        if admin_pass and passcode == admin_pass:
            st.success("Access Granted")
            uploaded_file = st.file_uploader("Upload Document", type=["txt", "md", "pdf", "docx"])
            
            if uploaded_file:
                # Check if this file was already processed to prevent infinite loops
                if "last_processed_file" not in st.session_state:
                    st.session_state.last_processed_file = None
                    
                # New file detected - Process & Save
                file_ext = uploaded_file.name.split(".")[-1].lower()
                save_name = uploaded_file.name
                final_content = b""

                # Convert to TXT if PDF or DOCX
                if file_ext in ["pdf", "docx"]:
                    import io
                    from trace_engine import clean_extracted_text
                    
                    text_content = ""
                    try:
                        if file_ext == "pdf":
                            import PyPDF2
                            pdf_reader = PyPDF2.PdfReader(uploaded_file)
                            for page in pdf_reader.pages:
                                text_content += page.extract_text() + "\n"
                        elif file_ext == "docx":
                            import docx
                            doc_file = docx.Document(uploaded_file)
                            text_content = "\n".join([para.text for para in doc_file.paragraphs])
                        
                        # Clean and Normalize
                        cleaned_text = clean_extracted_text(text_content)
                        final_content = cleaned_text.encode("utf-8")
                        
                        # Change extension to .txt
                        save_name = os.path.splitext(uploaded_file.name)[0] + ".txt"
                        
                    except Exception as e:
                        st.error(f"Error converting {uploaded_file.name}: {e}")
                        final_content = uploaded_file.getbuffer() # Fallback
                else:
                    # Text/MD files - just read bytes
                    final_content = uploaded_file.getbuffer()

                save_path = os.path.join("data", save_name)
                with open(save_path, "wb") as f:
                    f.write(final_content)
                
                st.session_state.last_processed_file = uploaded_file.name
                st.success(f"Saved {uploaded_file.name} as {save_name}")
                st.rerun()
            else:
                if st.session_state.get("last_processed_file"):
                     st.success(f"Last uploaded: {st.session_state.last_processed_file}")
            
            st.markdown("---")
            st.subheader("Manage Files")
            
            # Delete
            existing_files = [f for f in os.listdir("data") if os.path.isfile(os.path.join("data", f))]
            files_to_delete = st.multiselect("Select files to delete:", existing_files)
            
            if st.button("Delete Selected", type="primary", disabled=not files_to_delete):
                for fname in files_to_delete:
                    try:
                        os.remove(os.path.join("data", fname))
                        st.toast(f"Deleted {fname}")
                    except Exception as e:
                        st.error(f"Error deleting {fname}: {e}")
                
                # Clear cache and rerun
                st.session_state.last_processed_file = None
                st.rerun()
        elif passcode:
            st.error("Invalid Passcode")

# --- UI LAYOUT ---
if "debug_log" not in st.session_state:
    st.session_state.debug_log = []
if "clicked_states" not in st.session_state:
    st.session_state.clicked_states = {}

def log_event(msg):
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    log_msg = f"{ts}: {msg}"
    if "debug_log" in st.session_state:
        st.session_state.debug_log.append(log_msg)
    print(f"DEBUG_LOG: {log_msg}")

try:
    st.markdown("<h1 class='main-header'>Hey there! Ask me anything about Khuong</h1>", unsafe_allow_html=True)
    
    # --- AGENT MODE SELECTOR ---
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        agent_mode = st.radio(
            "Select Agent Mode", 
            ["Standard RAG", "Recursive Language Model (RLM)"], 
            horizontal=True,
            label_visibility="collapsed"
        )

    # --- VERIFY TOGGLE (RAG Only) ---
    if agent_mode == "Standard RAG":
        _, col_center, _ = st.columns([1, 1, 1])
        with col_center:
            btn_label = "✅ Verify ON" if st.session_state.verify_enabled else "🔍 Verify Sources"
            btn_type = "primary" if st.session_state.verify_enabled else "secondary"
            if st.button(btn_label, type=btn_type, use_container_width=True):
                st.session_state.verify_enabled = not st.session_state.verify_enabled
                st.rerun()
            
            if st.session_state.verify_enabled:
                st.markdown("<p style='text-align: center; color: gray; font-size: 0.85em;'><i>In your next prompt, click highlighted text to see source (might take a while)</i></p>", unsafe_allow_html=True)
    else:
        # In RLM mode, verify is implicit/different, so disable manual toggle or ensure it's off
        st.session_state.verify_enabled = False 
        
        _, col_center, _ = st.columns([1, 2, 1])
        with col_center:
             st.markdown("<p style='text-align: center; color: #856404; background-color: #fff3cd; border: 1px solid #ffeeba; padding: 0.5rem; border-radius: 0.25rem; font-size: 0.85em;'>⚠️ In this mode, models easily get hallucinate but you can trace it in the thinking status</p>", unsafe_allow_html=True)

    # Dynamic Column Layout
    # If a document is open, split screen [3, 2].
    # If closed, Chat takes full width.
    if st.session_state.view_doc:
        col_chat, col_docs = st.columns([3, 2])
    else:
        col_chat = st.container()
        col_docs = None

    with col_chat:
        # Render History
        for i, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"]):
                if msg["role"] == "user":
                    st.write(msg["content"])
                else:
                    # Render Token Usage
                    if "token_usage" in msg and msg["token_usage"]:
                        stats = msg["token_usage"]
                        stats = msg["token_usage"]
                        total_tokens = stats.get('total', 0)
                        st.caption(f"🪙 Tokens: {total_tokens}")
                        
                        if total_tokens > 6500:
                            st.warning(f"⚠️ High Token Usage ({total_tokens}). Limit is 15K/min (Khuong is poor 😔). You should wait ~60s to avoid rate limit error from Google.")
                    
                    # Render Debug/Status Steps if available
                    if msg.get("debug_steps"):
                        with st.status("🧠 Thinking Process", state="complete", expanded=False):
                            for step in msg["debug_steps"]:
                                st.write(step)

                    if not msg.get("html_content"):
                        st.write(msg["content"])
                        continue
                        
                    current_val = click_detector(msg["html_content"], key=f"msg_{i}")
                    
                    prev_val = st.session_state.clicked_states.get(i)
                    
                    if current_val and current_val != prev_val:
                        log_event(f"New click detected on msg_{i}: {current_val[:30]}...")
                        st.session_state.clicked_states[i] = current_val # Update last known
                        
                        import urllib.parse
                        parts = current_val.split(":::")
                        doc_name = parts[0]
                        highlight_text = None
                        if len(parts) > 1:
                            highlight_text = urllib.parse.unquote(parts[1])
                        
                        # Apply Changes
                        st.session_state.view_doc = doc_name
                        st.session_state.highlight_phrase = highlight_text
                        
                        log_event("Click processed -> Rerunning")
                        st.rerun()

    # Chat Input
    log_event("Rendering Chat Input")
    if prompt := st.chat_input("Ask about my skills..."):
        log_event("User Input received")
        st.session_state.messages.append({"role": "user", "content": prompt})
        log_event("Appended user msg -> Rerunning")
        st.rerun()

    # Generate Answer
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        if client:
            with st.spinner("Thinking..."):
                try:
                    # Retrieve prompt
                    prompt_container = st.session_state.messages[-1]
                    prompt_text = prompt_container["content"]

                    if agent_mode == "Recursive Language Model (RLM)":
                        log_event("RLM Mode Selected")
                        steps_log = []
                        
                        with st.status("🧠 RLM Thinking...", expanded=True) as status:
                            def ui_logger(msg):
                                status.write(msg)
                                log_event(msg)
                                steps_log.append(msg)
                                
                            rlm = RLMAgent(client, MODEL_ID, docs=docs, log_callback=ui_logger)
                            response_text, token_stats = rlm.completion(prompt_text)
                            
                            limit_msg = f"🪙 Total Tokens Used: {token_stats['total']}"
                            ui_logger(limit_msg)
                            status.update(label="RLM Finished!", state="complete", expanded=True)
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response_text,
                            "html_content": None,
                            "debug_steps": steps_log,
                            "token_usage": token_stats
                        })
                        st.rerun()
                    
                    with st.status("🔍 Standard RAG Working...", expanded=True) as status:
                        steps_log = []
                        def log_status(msg):
                            status.write(msg)
                            log_event(msg)
                            steps_log.append(msg)
                            
                        # Skip router when verify disabled for speed
                        if st.session_state.verify_enabled:
                            log_status("Router: Analyzing query...")
                            # Lightweight index for Router
                            doc_index = {}
                            for name, content in docs.items():
                                L = len(content)
                                if L < 2000:
                                    preview = content
                                else:
                                    start = content[:600]
                                    mid_idx = L // 2
                                    mid = content[mid_idx-300 : mid_idx+300]
                                    end = content[-600:]
                                    preview = f"{start}\n...\n{mid}\n...\n{end}"
                                doc_index[name] = preview

                            index_str = "\n".join([f"- {name}: {preview}" for name, preview in doc_index.items()])
                            
                            router_prompt = f"""
                            You are a data librarian.
                            User Query: "{prompt_text}"
                            
                            Available Documents:
                            {index_str}
                            
                            Task: Return a JSON list of filenames that are relevant to the query.
                            Example: ["file1.txt", "file2.pdf"]
                            Return ONLY the JSON list. If no specific document is needed, return all filenames.
                            """
                            
                            router_chat = client.chats.create(model=MODEL_ID)
                            router_response = router_chat.send_message(router_prompt)
                            
                            selected_files = list(docs.keys())
                            try:
                                json_match = re.search(r'\[.*\]', router_response.text, re.DOTALL)
                                if json_match:
                                    parsed_files = json.loads(json_match.group(0))
                                    valid_files = [f for f in parsed_files if f in docs]
                                    if valid_files:
                                        selected_files = valid_files
                                log_status(f"Router selected: {selected_files}")
                            except Exception as e:
                                log_status(f"Router Parse Error: {e}. using all docs.")
                                selected_files = list(docs.keys())
                        else:
                            # Fast path: skip router
                            log_status("Verify OFF - using all docs (Fast Mode)")
                            selected_files = list(docs.keys())
                            
                        log_status("Constructing context...")
                        
                        # Construct Context from Selected Files
                        relevant_context = "\n\n".join([f"--- SOURCE: {name} ---\n{docs[name]}" for name in selected_files])
                        
                        # System Prompt & Context
                        system_prompt_text = f"You are a professional portfolio assistant.\nKnowledge Base: {relevant_context}\n\n1. Answer the user's question directly and naturally.\n2. You MUST use exact, verbatim phrases from the Knowledge Base to support your claims.\n3. Do NOT use markdown bold (**) or italics or any marks to specify which part are from knowledge. The system extracts and highlights these phrases automatically.\n4. Do not just dump raw text; synthesize the answer"
                        
                        # Construct History
                        formatted_history = []
                        for m in st.session_state.messages[:-1]:
                            if m["content"]:
                                role = "model" if m["role"] == "assistant" else "user"
                                formatted_history.append({"role": role, "parts": [{"text": m["content"]}]})

                        chat = client.chats.create(
                            model=MODEL_ID,
                            config=genai.types.GenerateContentConfig(temperature=0),
                            history=formatted_history
                        )
                        
                        final_prompt = system_prompt_text + "\n\nUser Query: " + prompt_text
                        log_status("Generating answer...")
                        response = chat.send_message(final_prompt)
                        log_status("Answer received.")
                        
                        # Extract Token Usage
                        token_stats = {}
                        if hasattr(response, "usage_metadata"):
                            print(f"[DEBUG] Raw Metadata: {response.usage_metadata}")
                            token_stats = {
                                'total': response.usage_metadata.total_token_count or 0
                            }
                            log_status(f"🪙 Tokens: {token_stats['total']}")

                        # Skip trace engine when verify disabled
                        if st.session_state.verify_enabled:
                            log_status("Verifying sources (Trace Engine)...")
                            traced_html = find_maximal_matches(response.text, docs)
                        else:
                            traced_html = None
                            
                        status.update(label="Response Ready!", state="complete", expanded=True)
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response.text,
                        "html_content": traced_html,
                        "debug_steps": steps_log,
                        "token_usage": token_stats
                    })
                    st.session_state.last_html_debug = traced_html 
                    log_event("Appended AI msg -> Rerunning")
                    st.rerun()
                except Exception as e:
                    log_event(f"Error: {e}")
                    st.error(f"Error communicating with Gemini: {e}")
        else:
             st.error("AI model not configured.")

    if col_docs:
        with col_docs:
            # Only show content if a document is selected via click
            if st.session_state.view_doc:
                # Make the header a button to close the view
                if st.button("Verified Source Context (Click to Close)", type="secondary", use_container_width=True):
                    st.session_state.view_doc = None
                    st.session_state.highlight_phrase = None
                    st.rerun()

                st.success(f"Source: {st.session_state.view_doc}")
            
            current_doc_name = st.session_state.view_doc
            if current_doc_name in docs:
                content = docs[current_doc_name]
                highlight_phrase = st.session_state.get("highlight_phrase")
                
                if highlight_phrase:
                     # Find location of the match to create a snippet
                     idx = content.find(highlight_phrase)
                     if idx != -1:
                         # Radius of context (1000 chars)
                         start_idx = max(0, idx - 1000)
                         end_idx = min(len(content), idx + len(highlight_phrase) + 1000)
                         
                         snippet = content[start_idx:end_idx]
                         
                         # Add ellipses
                         if start_idx > 0: snippet = "... " + snippet
                         if end_idx < len(content): snippet = snippet + " ..."
                         
                         highlighted_content = snippet.replace(
                             highlight_phrase, 
                             f"<span style='background-color: #d4edda; color: #155724; padding: 2px; border-radius: 3px; font-weight: bold;'>{highlight_phrase}</span>"
                         )
                         st.markdown(highlighted_content, unsafe_allow_html=True)
                     else:
                         st.warning("Match location lost. Showing full text.")
                         st.markdown(content)
                else:
                     st.markdown(content)


            
except Exception as main_e:
    st.error(f"Critical Application Error: {main_e}")
    st.exception(main_e)

# --- LET IT SNOW ---
if "has_snowed" not in st.session_state:
    st.snow()
    st.session_state.has_snowed = True