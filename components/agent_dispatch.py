import streamlit as st
from config.app_config import MODEL_ID, MODE_RLM, MODE_VECTOR_RAG, MODE_FILE_BASED
from state import log_event, append_response
from engines.trace_engine import find_maximal_matches
from agents.rlm.rlm_agent import RLMAgent
from agents.vector.vector_agent import VectorRAGAgent
from agents.file_based.file_based_agent import FileBasedAgent

def _make_logger(status, steps_log):
    """Creates a closure that writes to a Streamlit status widget, debug log, and steps list."""
    def _log(msg):
        status.write(msg)
        log_event(msg)
        steps_log.append(msg)
    return _log

def generate_answer(client, agent_mode, prompt_text, docs, api_key):
    """Dispatches the prompt to the selected agent model and manages the process UI."""
    try:
        steps_log = []
        
        # --- Document Sandbox ---
        # Filter out the 'summaries' folder so RLM and Vector see only raw, authoritative documents
        raw_docs = {k: v for k, v in docs.items() if "summaries/" not in k.replace("\\", "/")}

        # --- Strategy Pattern for Agents ---
        if agent_mode == MODE_RLM:
            log_event("RLM Mode Selected")
            with st.status("🧠 RLM Thinking...", expanded=True) as status:
                logger = _make_logger(status, steps_log)
                agent = RLMAgent(client, MODEL_ID, docs=raw_docs, log_callback=logger)
                response_text, token_stats = agent.completion(prompt_text)
                status.update(label="RLM Finished!", state="complete", expanded=True)

        elif agent_mode == MODE_VECTOR_RAG:
            log_event("Vector RAG Mode Selected")
            with st.status("🛠️ Vector RAG Working...", expanded=True) as status:
                logger = _make_logger(status, steps_log)
                agent = VectorRAGAgent(client, MODEL_ID, api_key=api_key, docs=raw_docs, log_callback=logger)
                response_text, token_stats = agent.completion(
                    prompt_text, 
                    verify_enabled=st.session_state.verify_enabled
                )
                status.update(label="Vector Retrieval Complete!", state="complete", expanded=False)

        else:  # MODE_FILE_BASED
            log_event("File-Based Context Mode Selected")
            with st.status("🔍 File-Based Context Working...", expanded=True) as status:
                logger = _make_logger(status, steps_log)
                agent = FileBasedAgent(client, MODEL_ID, docs=docs, log_callback=logger)
                response_text, token_stats = agent.completion(
                    user_query=prompt_text,
                    chat_history=st.session_state.messages[:-1],
                    verify_enabled=st.session_state.verify_enabled
                )
                status.update(label="Response Ready!", state="complete", expanded=True)

        # --- Centralized Trace Engine Verification ---
        traced_html = None
        if st.session_state.verify_enabled:
            log_event("Verifying sources (Trace Engine)...")
            traced_html = find_maximal_matches(response_text, docs)
        
        st.session_state.last_html_debug = traced_html
        
        # --- Clean Final Rendering ---
        log_event("Appended AI msg -> Rerunning")
        append_response(response_text, html_content=traced_html, debug_steps=steps_log, token_usage=token_stats)

    except Exception as e:
        log_event(f"Error: {e}")
        st.error(f"Error communicating with Gemini: {e}")
        # Append an error response to cap the conversation turn and prevent infinite retries
        append_response(f"Sorry, the Gemini API encountered an error (e.g. 500 Internal Error). Please try your prompt again.", html_content=None)
