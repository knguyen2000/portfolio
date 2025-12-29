import streamlit as st
from st_click_detector import click_detector
import os

# --- LOGIC IMPORT ---
from trace_engine import load_corpus, find_maximal_matches

# --- CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Meet Khuong", page_icon="data/panda_eat.png")


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

# --- ADMIN UPLOAD ---
# Just temporal for testing, permanent upload is TBD
with st.sidebar:
    # 1. Profile Image & Details
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
            <a href="https://drive.google.com/file/d/1ZFrhWioHuzSf3SUmp-l_wn0aed4d86vd/view?usp=sharing" target="_blank" style="text-decoration: none; color: inherit; font-size: 28px;">
                <i class="fa-solid fa-address-card"></i>
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Spacer
    st.markdown("<br>" * 3, unsafe_allow_html=True)

    # Collapsible Admin Section (Bottom)
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
            
            # Delete Functionality
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
    
    st.markdown("---")
    if st.button("Reset Conversation"):
        st.session_state.messages = []
        st.session_state.view_doc = None
        st.session_state.highlight_phrase = None
        st.rerun()

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
    st.markdown("<div style='text-align: center; margin-bottom: 20px;'>Click <b>blue highlights</b> to verify the source</div>", unsafe_allow_html=True)

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
                    log_event("Generating response...")
                    
                    # Define System Prompt & Context
                    system_prompt_text = f"You are a professional portfolio assistant.\nKnowledge Base: {full_context}\n\n1. Answer the user's question directly and naturally.\n2. You MUST use exact, verbatim phrases from the Knowledge Base to support your claims.\n3. Do NOT use markdown bold (**) or italics or any marks to specify which part are from knowledge. The system extracts and highlights these phrases automatically.\n4. Do not just dump raw text; synthesize the answer."

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
                    response = chat.send_message(final_prompt)
                    log_event("Response received")
                    
                    traced_html = find_maximal_matches(response.text, docs)
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response.text,
                        "html_content": traced_html
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
                     highlighted_content = content.replace(
                         highlight_phrase, 
                         f"<span style='background-color: #d4edda; color: #155724; padding: 2px; border-radius: 3px;'>{highlight_phrase}</span>"
                     )
                     st.markdown(highlighted_content, unsafe_allow_html=True)
                else:
                     st.markdown(content)


            
except Exception as main_e:
    st.error(f"Critical Application Error: {main_e}")
    st.exception(main_e)

