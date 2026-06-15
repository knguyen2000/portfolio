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

from config.app_config import MODE_NLA, MODE_RLM, MODE_VECTOR_RAG, MODEL_ID
from state import append_response, log_event


def _handle_booking_flow(client, agent_mode: str, prompt_text: str):
    """
    Multi-turn in-chat booking via Calendly (Story 5).

    Called before normal agent dispatch. Returns (response_text, token_stats) when
    the booking flow is active or scheduling intent was detected; returns None to
    fall through to the normal agent pipeline.
    """
    from services.calendly import (
        CalendlyClient,
        build_booking_link,
        detect_scheduling_intent,
        extract_booking_info,
        fetch_available_slots,
        fetch_event_types,
        format_slot_time,
        is_booking_supported,
        pick_best_slot,
        validate_email,
    )

    booking = st.session_state.get("booking_flow")
    is_scheduling = detect_scheduling_intent(prompt_text)

    # Not in an active flow and no scheduling intent → let normal agent handle
    if not booking and not is_scheduling:
        return None

    # NLA exclusion
    if not is_booking_supported(agent_mode):
        return (
            "NLA mode is for exploring model internals only and doesn't support booking. "
            "Please switch to another mode (e.g., Standard RAG) to schedule a meeting with Khuong.",
            {"total": 0},
        )

    # Require Calendly token
    try:
        token = st.secrets.get("CALENDLY_TOKEN")
    except Exception:
        token = None

    if not token:
        st.session_state.booking_flow = None
        return (
            "Khuong's calendar isn't connected yet. "
            "You can reach him via [email](mailto:khuongnguyen211000@gmail.com) "
            "or [LinkedIn](https://www.linkedin.com/in/khuongng/) to arrange a meeting.",
            {"total": 0},
        )

    total_tokens = 0
    log_event(f"[BOOKING DEBUG] booking={booking}, prompt={prompt_text!r}")

    if not booking:
        # First turn — try LLM extraction in case user provided everything up front
        # (e.g. "book a call, I'm Jane Doe, jane@example.com, Thursday 2pm")
        extracted, tokens = extract_booking_info(client, MODEL_ID, prompt_text)
        total_tokens += tokens
        st.session_state.booking_flow = {
            "name": extracted["name"],
            "email": extracted["email"],
            "preferred_time": extracted["preferred_time"],
            "awaiting": None,  # tracks which field we explicitly asked for last
        }
    else:
        # Subsequent turns — if we asked for a specific field, the message IS that field.
        # Store it directly without another LLM round-trip.
        awaiting = booking.get("awaiting")
        log_event(f"[BOOKING DEBUG] else branch — awaiting={awaiting!r}")
        if awaiting:
            booking[awaiting] = prompt_text.strip()
            booking["awaiting"] = None
        st.session_state.booking_flow = booking

    booking = st.session_state.booking_flow
    log_event(f"[BOOKING DEBUG] after update — booking={booking}")

    # --- Collect missing pieces one ask at a time, tracking what we asked for ---
    if not booking.get("name"):
        booking["awaiting"] = "name"
        st.session_state.booking_flow = booking
        return ("I'd love to help book a meeting with Khuong! What's your full name?", {"total": total_tokens})

    if not booking.get("email"):
        booking["awaiting"] = "email"
        st.session_state.booking_flow = booking
        return (
            f"Thanks, {booking['name']}! What's the best email address for the calendar invite?",
            {"total": total_tokens},
        )

    if not validate_email(booking["email"]):
        booking["email"] = None
        booking["awaiting"] = "email"
        st.session_state.booking_flow = booking
        return ("That email doesn't look quite right — could you double-check it?", {"total": total_tokens})

    if not booking.get("preferred_time"):
        booking["awaiting"] = "preferred_time"
        st.session_state.booking_flow = booking
        return (
            f"Got it! When works best for you, {booking['name']}? "
            "Feel free to be specific (e.g., 'Thursday at 2 pm') or general (e.g., 'any morning next week').",
            {"total": total_tokens},
        )

    # --- All info collected — hit the Calendly API ---
    calendly = CalendlyClient(token)

    try:
        event_types = fetch_event_types(calendly)
    except Exception as e:
        log_event(f"Calendly fetch_event_types error: {e}")
        st.session_state.booking_flow = None
        return ("I couldn't reach Khuong's calendar right now. Please try again in a moment.", {"total": total_tokens})

    if not event_types:
        st.session_state.booking_flow = None
        return ("There are no active meeting types on Khuong's calendar at the moment.", {"total": total_tokens})

    # Pick the first event type (30-min coffee chat, etc.)
    event_type = event_types[0]

    try:
        user_info = calendly.get_current_user()
        timezone = user_info.get("timezone", "America/Chicago")
        slots_by_date = fetch_available_slots(calendly, event_type["uri"])
    except Exception as e:
        log_event(f"Calendly fetch_available_slots error: {e}")
        st.session_state.booking_flow = None
        return ("I had trouble fetching available slots. Please try again later.", {"total": total_tokens})

    if not slots_by_date:
        st.session_state.booking_flow = None
        return (
            f"There are no open slots this week for a **{event_type['name']}**. "
            f"Try emailing Khuong at khuongnguyen211000@gmail.com to find a time.",
            {"total": total_tokens},
        )

    # Match preferred time to an actual slot
    best_slot, tokens = pick_best_slot(client, MODEL_ID, booking["preferred_time"], slots_by_date, timezone)
    total_tokens += tokens

    if not best_slot:
        # Show the next few available options and stay in the flow
        options = []
        for date_key in sorted(slots_by_date)[:3]:
            for slot in slots_by_date[date_key][:2]:
                options.append(f"- **{date_key}** at {format_slot_time(slot['start_time'], timezone)}")
        original_pref = booking["preferred_time"]
        booking["preferred_time"] = None
        booking["awaiting"] = "preferred_time"
        st.session_state.booking_flow = booking
        return (
            f"I couldn't find a slot close to *{original_pref}*. "
            f"Here are some open times:\n\n" + "\n".join(options) + "\n\nWhich works for you?",
            {"total": total_tokens},
        )

    # --- Generate a pre-filled booking link ---
    booking_url = build_booking_link(event_type, booking["name"], booking["email"], best_slot["date"])
    slot_time = format_slot_time(best_slot["start_time"], timezone=timezone)

    st.session_state.booking_flow = None

    return (
        f"Great news — I found a slot that matches!\n\n"
        f"📅 **{event_type['name']}** ({event_type['duration']} min)\n"
        f"🕐 **{best_slot['date']}** at **{slot_time}**\n\n"
        f"👉 [**Book this time**]({booking_url})\n\n"
        f"Your name and email are pre-filled — just confirm on the Calendly page to complete the booking!",
        {"total": total_tokens},
    )


def _make_logger(status, steps_log):
    """Creates a closure that writes to a Streamlit status widget, debug log, and steps list."""

    def _log(msg):
        status.write(msg)
        log_event(msg)
        steps_log.append(msg)

    return _log


def _deduplicate_response(text):
    """
    Defensively deduplicates mirrored text (A\nA) often seen in newer Gemini models
    when pushed for strict verbatim extraction. Robust against whitespace quirks.
    """
    if not text:
        return ""
    text = text.strip()

    import re

    # Remove all whitespace to check for perfect duplication
    clean_text = re.sub(r"\s+", "", text)
    if not clean_text:
        return text

    if len(clean_text) % 2 == 0:
        half_len = len(clean_text) // 2
        if clean_text[:half_len] == clean_text[half_len:]:
            # We found a perfect echo! Return the first half of the original text.
            char_count = 0
            for i, char in enumerate(text):
                if not char.isspace():
                    char_count += 1
                if char_count == half_len:
                    return text[: i + 1].strip()

    # Fallback to paragraph logic for weird formatting cases
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if len(paragraphs) > 1 and len(paragraphs) % 2 == 0:
        half = len(paragraphs) // 2
        if paragraphs[:half] == paragraphs[half:]:
            return "\n\n".join(paragraphs[:half])

    return text


def _run_agent(client, agent_mode, prompt_text, docs, api_key, steps_log, status=None):
    """Run the selected agent and return (response_text, token_stats)."""
    from agents.file_based.file_based_agent import FileBasedAgent
    from agents.rlm.rlm_agent import RLMAgent
    from agents.vector.vector_agent import VectorRAGAgent

    raw_docs = {k: v for k, v in docs.items() if "summaries/" not in k.replace("\\", "/")}
    logger = _make_logger(status, steps_log) if status else None

    if agent_mode == MODE_RLM:
        log_event("RLM Mode Selected")
        agent = RLMAgent(client, MODEL_ID, docs=raw_docs, log_callback=logger)
        response_text, token_stats = agent.completion(prompt_text)

    elif agent_mode == MODE_VECTOR_RAG:
        log_event("Vector RAG Mode Selected")
        agent = VectorRAGAgent(client, MODEL_ID, api_key=api_key, docs=raw_docs, log_callback=logger)
        response_text, token_stats = agent.completion(prompt_text, verify_enabled=st.session_state.verify_enabled)

    elif agent_mode == MODE_NLA:
        log_event("NLA Mode Selected")
        from agents.nla.nla_agent import NLAAgent

        agent = NLAAgent(client, MODEL_ID, log_callback=logger)
        response_text, token_stats, nla_analysis = agent.completion(prompt_text)
        st.session_state.pending_nla_analysis = nla_analysis

    else:  # MODE_FILE_BASED
        log_event("File-Based Context Mode Selected")
        agent = FileBasedAgent(client, MODEL_ID, docs=docs, log_callback=logger)
        response_text, token_stats = agent.completion(
            user_query=prompt_text,
            chat_history=st.session_state.messages[:-1],
            verify_enabled=st.session_state.verify_enabled,
        )

    return response_text, token_stats


def _run_post_generation(
    client, prompt_text, response_text, docs, steps_log, token_stats, status=None, force_concern_category=None
):
    """Run trace engine + workflow intelligence, then append the response."""
    from engines.trace_engine import find_maximal_matches
    from engines.workflow_intelligence import detect_concern

    # Collect any NLA analysis produced by the NLA agent
    nla_analysis = st.session_state.pop("pending_nla_analysis", None)

    # Global deduplication guard
    response_text = _deduplicate_response(response_text)

    # --- Centralized Trace Engine Verification ---
    traced_html = None
    sources = []
    if st.session_state.verify_enabled:
        if status:
            status.update(label="🔍 Verifying sources...", expanded=False)
        log_event("Verifying sources (Trace Engine)...")
        traced_html, sources = find_maximal_matches(response_text, docs)

    st.session_state.last_html_debug = traced_html

    # --- Workflow Intelligence: Detect Concern ---
    try:
        if force_concern_category:
            log_event(f"Workflow Intelligence: Auto-submitting via Checkpoint Engine ({force_concern_category})")
            from utils.workflow_db import insert_concern

            concern_data = {
                "is_concern": True,
                "category": force_concern_category,
                "original_quote": prompt_text,
                "affected_role": st.session_state.get("user_role", "Visitor"),
            }
            # Auto-submit to DB
            insert_concern(concern_data, prompt_text)
            st.session_state.pending_concern = None

            # Append success message directly to the agent's response
            msg_append = f"\n\n*✅ Thank you for the feedback! I've securely recorded this as a **{force_concern_category}** for Khuong to review.*"
            response_text += msg_append
            if traced_html:
                traced_html += msg_append.replace("\n", "<br>")
        else:
            if status:
                status.update(label="🖨️ Finalizing answer...", expanded=False)
            log_event("Workflow Intelligence: Analyzing message...")
            concern_data, concern_tokens = detect_concern(client, prompt_text)
            st.session_state.turn_tokens += concern_tokens

            log_event(
                f"Workflow Intelligence result: is_concern={concern_data.get('is_concern')}, category={concern_data.get('category')}"
            )
            if concern_data and concern_data.get("is_concern"):
                concern_data["original_quote"] = prompt_text
                st.session_state.pending_concern = concern_data
            else:
                st.session_state.pending_concern = None
    except Exception as wi_e:
        log_event(f"Workflow Intelligence error (non-fatal): {wi_e}")
        st.session_state.pending_concern = None

    # --- Clean Final Rendering ---
    if status:
        status.update(label="✅ Complete!", state="complete", expanded=False)
    log_event("Appended AI msg -> Rerunning")

    # Use the globally accumulated tokens for the final display
    total_turn_tokens = st.session_state.get("turn_tokens", token_stats.get("total", 0))
    append_response(
        response_text,
        html_content=traced_html,
        debug_steps=steps_log,
        token_usage={"total": total_turn_tokens},
        sources=sources,
        nla_analysis=nla_analysis,
    )


def check_and_set_checkpoint(client, prompt_text):
    """
    Pre-generation checkpoint check. If a checkpoint is needed, stores it
    in session state and appends a checkpoint message to the chat history.
    Returns True if a checkpoint was set (caller should NOT proceed to generation).
    """
    from engines.checkpoint_engine import should_checkpoint
    from services.calendly import detect_scheduling_intent

    if not st.session_state.checkpoint_enabled:
        return False

    # Active booking flow or scheduling intent: bypass checkpoint, booking handler owns these turns.
    if st.session_state.get("booking_flow") or detect_scheduling_intent(prompt_text):
        log_event("Checkpoint Engine: Booking flow active or scheduling intent detected — bypassing checkpoint.")
        return False

    log_event("Checkpoint Engine: Classifying message...")

    status_label = "🧠 Thinking..." if st.session_state.get("checkpoint_enabled", True) else "⚡ Analyzing request..."
    status_container = st.empty()
    with status_container.status(status_label, expanded=True):
        thought_placeholder = st.empty()
        thought_placeholder.markdown("Checking if the question needs clarification...")
        checkpoint = should_checkpoint(
            client, prompt_text, chat_history=st.session_state.messages[:-1], status_placeholder=thought_placeholder
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
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": "",
            "checkpoint": checkpoint,
            "debug_steps": [
                f"Checkpoint Engine: {checkpoint['checkpoint_type']}",
                f"Interpretation: {checkpoint.get('model_interpretation', '')}",
            ],
            "token_usage": {},
        }
    )
    st.rerun()
    return True  # unreachable after rerun, but semantically correct


def resume_from_checkpoint(client, agent_mode, docs, api_key):
    """
    Resume generation after the user responded to a checkpoint.
    Builds an enriched prompt from the checkpoint + user decision, then
    runs the normal agent flow.
    """
    from engines.checkpoint_engine import build_resume_prompt

    checkpoint = st.session_state.pending_checkpoint
    user_decision = checkpoint.get("user_decision", "approved")
    user_edit = checkpoint.get("user_edit", "")

    # Build enriched prompt
    enriched_prompt = build_resume_prompt(checkpoint, user_decision, user_edit)
    log_event(f"Resuming from checkpoint with decision: {user_decision}")

    # Clear checkpoint state
    st.session_state.pending_checkpoint = None

    # Run normal agent flow with the enriched prompt

    try:
        steps_log = [f"Resumed from checkpoint ({checkpoint['checkpoint_type']})"]

        force_concern = None
        if "feature request" in user_edit.lower() or "backlog" in user_edit.lower():
            force_concern = "feature request"

        if force_concern:
            # FAST PATH: Checkpoint Engine already confirmed it's missing. Bypass Main Agent!
            log_event("Checkpoint Engine confirmed missing feature. Bypassing Main Agent & Vector Search.")
            response_text = "Currently, this feature is not available."
            token_stats = {"total": 0}

            _run_post_generation(
                client,
                checkpoint["original_message"],
                response_text,
                docs,
                steps_log,
                token_stats,
                status=None,
                force_concern_category=force_concern,
            )
            return

        # Unified status bar across all generation phases
        # In NLA mode, collapse the status bar since the NLA analysis is the focus
        if agent_mode == MODE_RLM:
            label = "🧠 Thinking..."
            expanded = True
        elif agent_mode == MODE_NLA:
            label = "🔬 Analyzing Activations..."
            expanded = False  # Hide in NLA mode
        else:
            label = "🛠️ Generating Answer..."
            expanded = True

        with st.status(label, expanded=expanded) as status:
            response_text, token_stats = _run_agent(
                client, agent_mode, enriched_prompt, docs, api_key, steps_log, status=status
            )
            st.session_state.turn_tokens += token_stats.get("total", 0)

            _run_post_generation(
                client,
                checkpoint["original_message"],
                response_text,
                docs,
                steps_log,
                token_stats,
                status=status,
                force_concern_category=None,
            )
    except Exception as e:
        _handle_error(e)


def generate_answer(client, agent_mode, prompt_text, docs, api_key):
    """Dispatches the prompt to the selected agent model and manages the process UI."""
    try:
        steps_log = []

        # Intercept scheduling intent before normal agent — manages multi-turn booking flow
        booking_result = _handle_booking_flow(client, agent_mode, prompt_text)
        if booking_result is not None:
            response_text, token_stats = booking_result
            st.session_state.turn_tokens += token_stats.get("total", 0)
            _run_post_generation(client, prompt_text, response_text, docs, steps_log, token_stats)
            return

        # Unified status bar across all generation phases
        # In NLA mode, collapse the status bar since the NLA analysis is the focus
        if agent_mode == MODE_RLM:
            label = "🧠 Thinking..."
            expanded = True
        elif agent_mode == MODE_NLA:
            label = "🔬 Analyzing Activations..."
            expanded = False  # Hide in NLA mode
        else:
            label = "🛠️ Generating Answer..."
            expanded = True

        with st.status(label, expanded=expanded) as status:
            response_text, token_stats = _run_agent(
                client, agent_mode, prompt_text, docs, api_key, steps_log, status=status
            )
            st.session_state.turn_tokens += token_stats.get("total", 0)
            _run_post_generation(client, prompt_text, response_text, docs, steps_log, token_stats, status=status)
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
