"""
Workflow Intelligence Engine.

Runs on every chat turn to detect if the user is expressing a concern
(feature request, bug report, trust issue, etc.) and generates structured
backlog candidates for the AI/ML team review dashboard.
"""
import json
import os
import re
import time


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_capabilities() -> str:
    """Load the portfolio capabilities guide used as ground truth for the detector."""
    path = os.path.join("data", "portfolio_capabilities.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "No capabilities guide found."


def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output, stripping markdown code fences."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return json.loads(text.strip())


def _generate_content_with_fallback(client, prompt: str) -> str:
    """
    Call generate_content with retry + model fallback.

    Tries gemini-3.1-flash-lite-preview first (good for structured JSON output),
    falls back to gemini-2.0-flash on 503 / UNAVAILABLE errors.
    Note: the main chat uses Gemma via MODEL_ID; these Gemini models are used
    here because they are more reliable at returning strict JSON.
    """
    # Gemma can struggle with strict JSON so use Gemini though with lower rate limit
    models_to_try = [
        "gemini-3.1-flash-lite-preview", 
        "gemini-3.0-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b"
    ]
    last_error = None
    for model in models_to_try:
        try:
            response = client.models.generate_content(
                model=model, 
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=500, # Workflow analysis is short
                )
            )
            tokens = response.usage_metadata.total_token_count if hasattr(response, "usage_metadata") and response.usage_metadata else 0
            return response.text, tokens
        except Exception as e:
            last_error = e
            # If 503 or 429, don't wait too long, just try the next model in our robust list
            print(f"[workflow_intelligence] Model {model} failed: {e}")
            continue
    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_concern(client, message_text: str) -> dict:
    """
    Analyze a user message to detect workflow concerns in the portfolio context.

    Returns a dict with at minimum an ``is_concern`` boolean key.
    On any error, returns ``{"is_concern": False}`` so the caller is never blocked.
    """
    capabilities = _load_capabilities()
    prompt = f"""
    You are an intelligent workflow detector for a portfolio Streamlit app.
    A visitor is interacting with the portfolio chatbot.

    Below is a comprehensive guide of EVERYTHING this portfolio can currently do.
    Use this as the ground truth for what is and is not supported.

    --- PORTFOLIO CAPABILITIES ---
    {capabilities}
    --- END OF CAPABILITIES ---

    CRITICAL RULES:
    1. If the user asks HOW to do something OR complains about a missing feature, AND that feature ALREADY EXISTS in the capabilities guide above, this is NOT a concern. Set "is_concern" to false.
    2. If the user asks HOW to do something OR asks whether something is possible, AND that thing is listed under "What Is NOT Currently Supported", treat this as an IMPLICIT feature request. Set "is_concern" to true and category to "feature request". Example: "how can I toggle dark mode?" → dark mode is not supported → is_concern = true.
    3. Explicit complaints, bug reports, and trust concerns about unsupported or broken things are always concerns.
    4. Normal questions about Khuong's background, skills, experience, or projects are NOT concerns.

    Detect whether the message expresses:
    - workflow pain (something is slow, broken, hard to use)
    - feature request (explicit OR implicit — user wants something the portfolio doesn't have)
    - trust concern (e.g., "Is this really your code?", "The AI hallucinated")
    - bug report (e.g., "The UI breaks on mobile", "I got an error")

    If the user is just asking a normal question about Khuong or the portfolio's existing features, that is NOT a concern.

    Respond with ONLY a JSON object and no markdown formatting or other text:
    {{
        "is_concern": true or false,
        "category": "workflow pain" | "feature request" | "tool confusion" | "trust concern" | "bug report" | null,
        "workflow_stage": "e.g., Exploring Projects, Reading Resume, Chatting with AI",
        "affected_role": "Visitor / Recruiter",
        "root_cause": "e.g., UI lack of clarity, AI limitation, missing feature",
        "tool_match": "e.g., Use the Verify Sources button, Look at the Guestbook page, Switch to RAG mode, Not supported",
        "analysis": "A brief 1-sentence summary of the pain point."
    }}

    User Message: "{message_text}"
    """
    try:
        text, tokens = _generate_content_with_fallback(client, prompt)
        result = _extract_json(text)
        return result, tokens
    except Exception as e:
        print(f"[workflow_intelligence] detect_concern error (non-fatal): {e}")
        return {"is_concern": False}, 0


def generate_backlog_candidate(client, concerns_list: list) -> dict:
    """
    Generate a structured backlog candidate from a list of concern dicts.

    Raises on failure so the caller (dashboard) can surface the real error.
    """
    quotes = "\n".join([f"- {c['original_quote']}" for c in concerns_list])

    prompt = f"""
    You are an AI/ML Product Manager reviewing visitor feedback for a portfolio application.
    Given the following user quotes expressing concerns, generate a draft backlog candidate.

    Concerns:
    {quotes}

    Respond with ONLY a valid JSON object. Do not include any markdown, explanation, or text outside the JSON.
    {{
        "title": "Short title for the opportunity",
        "problem": "1-2 sentence problem description",
        "original_evidence": "The quotes that support this",
        "workflow_stage": "The stage of the user workflow",
        "user_group": "Visitor / Recruiter / Hiring Manager",
        "existing_tool_check": "Is there an existing tool that partially solves this?",
        "hypothesized_root_causes": "Root causes as a comma-separated string",
        "impact": "High / Medium / Low",
        "risk": "High / Medium / Low",
        "suggested_validation": "How should the developer validate this issue?",
        "potential_mvp": "What is a potential minimum viable product to fix this?",
        "acceptance_criteria": "Comma-separated list of acceptance criteria"
    }}
    """
    text, _ = _generate_content_with_fallback(client, prompt)
    return _extract_json(text)
