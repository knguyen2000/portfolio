"""
Checkpoint Engine — Interactive Reasoning Checkpoints.

Pre-generation classifier that decides whether the model should pause and ask
the user to confirm an interpretation, direction, or assumption before
generating the full answer. Works as a layer around all agent modes.

Flow:
  1. should_checkpoint() runs BEFORE the agent call
  2. If checkpoint needed → store in session_state, show card, wait
  3. User responds → build_resume_prompt() enriches the original query
  4. Agent generates with the enriched prompt (zero agent code changes)
"""
import json
import os
import re
import time
import uuid
from google import genai

from config.app_config import CHECKPOINT_TYPES


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_capabilities() -> str:
    """Load portfolio capabilities so the classifier knows what the app can do."""
    path = os.path.join("data", "portfolio_capabilities.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output, stripping thinking blocks and markdown fences."""
    text = text.strip()
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start:end+1]
    return json.loads(text.strip())


def _generate_with_fallback(client, prompt: str, status_placeholder=None) -> tuple[str, str, int]:
    """Call Gemini with retry + model fallback. Streams thinking blocks to UI."""
    # Corrected model names and prioritized speed
    models = ["gemini-3.1-flash-lite-preview", "gemini-2.0-flash", "gemini-1.5-flash"]
    last_error = None
    
    for model in models:
        try:
            # Added config for speed and token efficiency
            response_stream = client.models.generate_content_stream(
                model=model, 
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=800, # Sufficient for <think> + JSON
                )
            )
            
            full_text = ""
            thoughts = ""
            in_think = False
            chunk_tokens = 0
            
            for chunk in response_stream:
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    chunk_tokens = chunk.usage_metadata.total_token_count or chunk_tokens
                    
                if not chunk.text: continue
                full_text += chunk.text
                
                if "<think>" in full_text and not in_think:
                    in_think = True
                    
                if in_think:
                    start_idx = full_text.find("<think>") + 7
                    end_idx = full_text.find("</think>")
                    
                    if end_idx != -1:
                        thoughts = full_text[start_idx:end_idx].strip()
                        in_think = False
                    else:
                        thoughts = full_text[start_idx:].strip()
                        
                    if status_placeholder and thoughts:
                        # Clean thinking status (remove trailing characters if it's getting long)
                        status_placeholder.markdown(thoughts + " ▌")
                        
            if status_placeholder and thoughts:
                status_placeholder.markdown(thoughts)
                
            return thoughts, full_text, chunk_tokens
            
        except Exception as e:
            last_error = e
            # Log the error and try the next model immediately unless it's a transient server error
            print(f"[checkpoint_engine] Model {model} failed: {e}")
            if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e):
                time.sleep(0.5) # Minimal sleep for transient errors
                continue # Try next model or next iteration
            # For other errors (like 404 or auth), we also try the next model
            continue

    if last_error:
        raise last_error
    return "", "", 0


# ---------------------------------------------------------------------------
# System prompt for the checkpoint classifier
# ---------------------------------------------------------------------------

_CLASSIFIER_PROMPT = """You are a checkpoint classifier for a portfolio chatbot.
The chatbot answers questions about Khuong Nguyen's skills, projects, and experience.

Your job: decide if the user's message is ambiguous enough that the model should
PAUSE and ask for confirmation before generating a full answer.

PORTFOLIO CONTEXT:
{capabilities}

CHECKPOINT TYPES you may use:
- interpretation_confirmation: The user's intent is genuinely ambiguous and could lead to very different answers.
- direction_choice: There are 2-3 meaningfully different angles to answer from.
- assumption_confirmation: The model must guess something important about the user's context.

CRITICAL RULES:
1. Most questions do NOT need a checkpoint. Default to "no checkpoint".
2. Simple greetings, clear skill questions, or specific project requests -> NO checkpoint.
3. Only checkpoint if the intent is genuinely ambiguous (could mean 2+ very different things).
4. If the user already provided enough context, do NOT ask for more.

Respond FIRST with a `<think>` block containing your internal reasoning, followed by ONLY a JSON object:
<think>
Your step-by-step reasoning about whether this is ambiguous and requires a checkpoint...
</think>
```json
{{
    "needs_checkpoint": true or false,
    "checkpoint_type": "interpretation_confirmation" | "direction_choice" | "assumption_confirmation" | null,
    "model_interpretation": "How you interpreted the user's question (1 sentence)",
    "question": "The question to ask the user to confirm/choose (1 sentence, conversational tone)",
    "options": ["option_1_label", "option_2_label"] or null,
    "next_step_if_approved": "What the model will do if user approves (1 sentence)",
    "reasoning": "A concise summary of your decision (1 sentence)"
}}
```

If no checkpoint is needed, set needs_checkpoint to false and all other fields to null.

User message: "{user_message}"
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def should_checkpoint(client, user_message: str, chat_history: list = None, status_placeholder=None) -> dict | None:
    """
    Classify whether the user's message needs a checkpoint before generation.

    Returns a checkpoint dict if one is needed, or None to proceed normally.
    Non-blocking: any error returns None so the chat flow is never interrupted.
    """
    # Skip checkpoint for very short messages (greetings, "hi", "thanks")
    if len(user_message.strip()) < 10:
        return None

    # Skip if this is clearly a follow-up (starts with pronouns or references)
    lower = user_message.lower().strip()
    follow_up_starters = ["yes", "no", "ok", "sure", "thanks", "thank you",
                          "that", "this", "it", "what about", "how about",
                          "can you", "could you", "please"]
    if any(lower.startswith(s) for s in follow_up_starters):
        return None

    # Skip if there's ongoing conversation context (follow-up is likely)
    if chat_history and len(chat_history) >= 2:
        # If the last 2 messages are user→assistant, this is a follow-up turn
        recent = chat_history[-2:]
        if (recent[0].get("role") == "assistant" and
                len(user_message.split()) < 15):
            return None

    capabilities = _load_capabilities()
    prompt = _CLASSIFIER_PROMPT.format(
        capabilities=capabilities[:3000],  # Truncate to save tokens
        user_message=user_message,
    )

    try:
        thoughts, text, chunk_tokens = _generate_with_fallback(client, prompt, status_placeholder)
        result = _extract_json(text)

        if not result.get("needs_checkpoint"):
            return {"needs_checkpoint": False, "tokens_used": chunk_tokens}

        # Validate checkpoint type
        ckpt_type = result.get("checkpoint_type")
        if ckpt_type not in CHECKPOINT_TYPES:
            return {"needs_checkpoint": False, "tokens_used": chunk_tokens}

        return {
            "needs_checkpoint": True,
            "tokens_used": chunk_tokens,
            "checkpoint_id": str(uuid.uuid4()),
            "checkpoint_type": ckpt_type,
            "model_interpretation": result.get("model_interpretation", ""),
            "question": result.get("question", "Is this correct?"),
            "options": result.get("options"),
            "next_step_if_approved": result.get("next_step_if_approved", ""),
            "original_message": user_message,
            "status": "waiting_for_user",
            "reasoning": thoughts or result.get("reasoning", ""),
        }
    except Exception as e:
        print(f"[checkpoint_engine] should_checkpoint error (non-fatal): {e}")
        return None


def build_resume_prompt(checkpoint: dict, user_decision: str,
                        user_edit: str = "") -> str:
    """
    Build an enriched prompt that includes the checkpoint context and user's
    decision, so the agent can continue with confirmed understanding.
    """
    original = checkpoint["original_message"]
    interpretation = checkpoint.get("model_interpretation", "")
    ckpt_type = checkpoint.get("checkpoint_type", "")

    if user_decision == "approved":
        context = (
            f"Original Question: {original}\n"
            f"Confirmed Context: {interpretation}\n\n"
            f"Please answer the Original Question using the Confirmed Context."
        )
    elif user_decision == "edited":
        context = (
            f"Original Question: {original}\n"
            f"User Clarification: {user_edit}\n\n"
            f"Please answer the question incorporating the User Clarification."
        )
    else:
        # "restart" — just return the original message
        return original

    return context
