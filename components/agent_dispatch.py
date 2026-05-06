"""
Agent Dispatch — Orchestrates agent selection, checkpoint gating, and response flow.

This module is the central traffic controller. It:
1. Checks for pending checkpoints (pre-generation pause)
2. Routes the prompt to the correct agent (RLM / Vector / File-Based)
3. Runs the Trace Engine for source verification
4. Runs Workflow Intelligence for concern detection
5. Handles all Gemini API errors with user-friendly messages
"""
import streamlit as st
from config.app_config import MODEL_ID, MODE_RLM, MODE_VECTOR_RAG, MODE_FILE_BASED
from state import log_event, append_response
from engines.trace_engine import find_maximal_matches
from agents.rlm.rlm_agent import RLMAgent
from agents.vector.vector_agent import VectorRAGAgent
from agents.file_based.file_based_agent import FileBasedAgent
from components.workflow_intelligence import detect_concern
from components.checkpoint_engine import should_checkpoint, build_resume_prompt


def _make_logger(status, steps_log):
    """Creates a closure that writes to a Streamlit status widget, debug log, and steps list."""
    def _log(msg):
        status.write(msg)
        log_event(msg)
        steps_log.append(msg)
    return _log


def _run_agent(client, agent_mode, prompt_text, docs, api_key, steps_log, status=None):
    """Run the selected agent and return (response_text, token_stats)."""
    raw_docs = {k: v for k, v in docs.items() if "summaries/" not in k.replace("\\", "/")}
    logger = _make_logger(status, steps_log) if status else None

    if agent_mode == MODE_RLM:
        log_event("RLM Mode Selected")
        agent = RLMAgent(client, MODEL_ID, docs=raw_docs, log_callback=logger)
        response_text, token_stats = agent.completion(prompt_text)

    elif agent_mode == MODE_VECTOR_RAG:
        log_event("Vector RAG Mode Selected")
        agent = VectorRAGAgent(client, MODEL_ID, api_key=api_key, docs=raw_docs, log_callback=logger)
        response_text, token_stats = agent.completion(
            prompt_text,
            verify_enabled=st.session_state.verify_enabled
        )

    else:  # MODE_FILE_BASED
        log_event("File-Based Context Mode Selected")
        agent = FileBasedAgent(client, MODEL_ID, docs=docs, log_callback=logger)
        response_text, token_stats = agent.completion(
            user_query=prompt_text,
            chat_history=st.session_state.messages[:-1],
            verify_enabled=st.session_state.verify_enabled
        )

    return response_text, token_stats


def _run_post_generation(client, prompt_text, response_text, docs, steps_log, token_stats, status=None):
    """Run trace engine + workflow intelligence, then append the response."""
    # --- Centralized Trace Engine Verification ---
    traced_html = None
    if st.session_state.verify_enabled:
        if status: status.update(label="🔍 Verifying sources...", expanded=False)
        log_event("Verifying sources (Trace Engine)...")
        traced_html = find_maximal_matches(response_text, docs)

    st.session_state.last_html_debug = traced_html

    # --- Workflow Intelligence: Detect Concern ---
    try:
        if status: status.update(label="🤖 Finalizing answer...", expanded=False)
        log_event("Workflow Intelligence: Analyzing message...")
        concern_data, concern_tokens = detect_concern(client, prompt_text)
        st.session_state.turn_tokens += concern_tokens
        
        log_event(f"Workflow Intelligence result: is_concern={concern_data.get('is_concern')}, category={concern_data.get('category')}")
        if concern_data and concern_data.get("is_concern"):
            concern_data["original_quote"] = prompt_text
            st.session_state.pending_concern = concern_data
            log_event(f"Pending concern set: {concern_data.get('category')}")
        else:
            st.session_state.pending_concern = None
    except Exception as wi_e:
        log_event(f"Workflow Intelligence error (non-fatal): {wi_e}")
        st.session_state.pending_concern = None

    # --- Clean Final Rendering ---
    if status: status.update(label="✅ Complete!", state="complete", expanded=False)
    log_event("Appended AI msg -> Rerunning")
    
    # Use the globally accumulated tokens for the final display
    total_turn_tokens = st.session_state.get("turn_tokens", token_stats.get("total", 0))
    append_response(response_text, html_content=traced_html, debug_steps=steps_log, token_usage={"total": total_turn_tokens})


def check_and_set_checkpoint(client, prompt_text):
    """
    Pre-generation checkpoint check. If a checkpoint is needed, stores it
    in session state and appends a checkpoint message to the chat history.
    Returns True if a checkpoint was set (caller should NOT proceed to generation).
    """
    if not st.session_state.checkpoint_enabled:
        return False

    log_event("Checkpoint Engine: Classifying message...")
    
    status_container = st.empty()
    with status_container.status("🧠 Analyzing request...", expanded=True) as status:
        thought_placeholder = st.empty()
        thought_placeholder.markdown("Checking if the question needs clarification...")
        checkpoint = should_checkpoint(
            client, prompt_text,
            chat_history=st.session_state.messages[:-1],
            status_placeholder=thought_placeholder
        )

    if checkpoint is None or not checkpoint.get("needs_checkpoint"):
        log_event("Checkpoint Engine: No checkpoint needed.")
        if checkpoint:
            st.session_state.turn_tokens += checkpoint.get("tokens_used", 0)
        status_container.empty()
        return False

    log_event(f"Checkpoint Engine: Checkpoint needed — {checkpoint['checkpoint_type']}")
    st.session_state.turn_tokens += checkpoint.get("tokens_used", 0)
    st.session_state.pending_checkpoint = checkpoint

    # Append a checkpoint message to the chat history so it renders as a card
    st.session_state.messages.append({
        "role": "assistant",
        "content": "",
        "checkpoint": checkpoint,
        "debug_steps": [
            f"Checkpoint Engine: {checkpoint['checkpoint_type']}",
            f"Interpretation: {checkpoint.get('model_interpretation', '')}",
        ],
        "token_usage": {},
    })
    st.rerun()
    return True  # unreachable after rerun, but semantically correct


def resume_from_checkpoint(client, agent_mode, docs, api_key):
    """
    Resume generation after the user responded to a checkpoint.
    Builds an enriched prompt from the checkpoint + user decision, then
    runs the normal agent flow.
    """
    checkpoint = st.session_state.pending_checkpoint
    user_decision = checkpoint.get("user_decision", "approved")
    user_edit = checkpoint.get("user_edit", "")

    # Build enriched prompt
    enriched_prompt = build_resume_prompt(checkpoint, user_decision, user_edit)
    log_event(f"Resuming from checkpoint with decision: {user_decision}")

    # Clear checkpoint state
    st.session_state.pending_checkpoint = None

    # Remove the checkpoint message from history to keep UI clean
    st.session_state.messages = [
        m for m in st.session_state.messages 
        if not m.get("checkpoint")
    ]

    # Update user's original message to reflect their clarification
    if user_edit and user_decision == "edited":
        for m in reversed(st.session_state.messages):
            if m["role"] == "user":
                m["content"] += f"\n\n*(Clarified: {user_edit})*"
                break

    # Run normal agent flow with the enriched prompt
    try:
        steps_log = [f"Resumed from checkpoint ({checkpoint['checkpoint_type']})"]
        
        # Unified status bar across all generation phases
        label = "🧠 RLM Thinking..." if agent_mode == MODE_RLM else "🛠️ Generating Answer..."
        with st.status(label, expanded=True) as status:
            response_text, token_stats = _run_agent(
                client, agent_mode, enriched_prompt, docs, api_key, steps_log, status=status
            )
            st.session_state.turn_tokens += token_stats.get("total", 0)
            _run_post_generation(
                client, checkpoint["original_message"], response_text,
                docs, steps_log, token_stats, status=status
            )
    except Exception as e:
        _handle_error(e)


def generate_answer(client, agent_mode, prompt_text, docs, api_key):
    """Dispatches the prompt to the selected agent model and manages the process UI."""
    try:
        steps_log = []
        
        # Unified status bar across all generation phases
        label = "🧠 RLM Thinking..." if agent_mode == MODE_RLM else "🛠️ Generating Answer..."
        with st.status(label, expanded=True) as status:
            response_text, token_stats = _run_agent(
                client, agent_mode, prompt_text, docs, api_key, steps_log, status=status
            )
            st.session_state.turn_tokens += token_stats.get("total", 0)
            _run_post_generation(
                client, prompt_text, response_text, docs, steps_log, token_stats, status=status
            )
    except Exception as e:
        _handle_error(e)


def _handle_error(e):
    """Convert API exceptions into user-friendly chat messages."""
    log_event(f"Error: {e}")
    err_str = str(e)
    if "500" in err_str or "Internal" in err_str:
        user_msg = "The AI model hit a temporary server hiccup (500). This usually clears up in a few seconds — please try sending your message again!"
    elif "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
        user_msg = "The AI is getting a lot of requests right now (rate limit). Please wait a moment and try again."
    elif "503" in err_str or "UNAVAILABLE" in err_str:
        user_msg = "The AI model is temporarily unavailable. Please try again in a few seconds."
    else:
        user_msg = "Something went wrong while thinking through your question. Please try again — and if it keeps happening, try switching to a different agent mode."
    append_response(user_msg, html_content=None)
