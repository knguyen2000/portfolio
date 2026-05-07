# Components (`/components`)

This directory bridges the gap between our raw backend logic (like AI agents or the vector store) and our frontend Streamlit user interface. The files here act as "Controllers" — they process data and format it so the UI can display it smoothly.

## File Structure

### `agent_dispatch.py`
The traffic controller for AI requests. When a user submits a prompt in `app.py`, it is immediately sent here.
**What it does:**
- Manages the visual `st.spinner()` and `st.status()` expandable UI elements.
- Routes the prompt to the correct logic depending on the active mode (Vector RAG, File-Based, or RLM).
- Captures token usage and triggers the Trace Engine (if verification is enabled) before finally appending the answer back to the chat history.

### `chat_renderer.py`
The visual engine for the conversation. Streamlit requires iterating over the message history to keep chat bubbles on screen.
**What it does:**
- Renders the avatar icons (`role="user"` vs `role="assistant"`).
- Builds the interactive "Think Steps" expander boxes for the RLM mode.
- Injects CSS and dynamically displays the Trace Engine's highlighted HTML responses.
- Renders the secondary full-document viewer panel if a user clicks on a cited source.

## Best Practices
If you need to add a completely new AI mode or a new type of chat visual feature (like rendering charts inside chat bubbles), do wiring in this folder. Keep pure UI layout inside `app.py`, and pure mathematical AI logic inside `agents/` or `utils/`.
