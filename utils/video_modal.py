import streamlit as st


# --- Shared Video Modal CSS ---
_MODAL_CSS = """
<style>
  .about-modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: auto;
    height: auto;
    max-width: 95vw;
    max-height: 90vh;
    background: #000;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0,0,0,0.8);
    z-index: 1000000;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .about-modal video {
    display: block;
    max-width: 100%;
    max-height: 90vh;
    width: auto;
    height: auto;
    object-fit: contain;
  }

  .about-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.85);
    z-index: 999999;
    display: block;
    cursor: pointer;
    text-decoration: none;
  }

  .click-hint {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    color: rgba(255,255,255,0.6);
    font-size: 14px;
    z-index: 1000001;
    pointer-events: none;
  }
</style>
"""

# --- Shared Replay Button CSS ---
_REPLAY_CSS = """
<style>
    .floating-replay-btn {
        position: fixed;
        bottom: 30%;
        right: 0;

        writing-mode: vertical-rl;
        text-orientation: mixed;

        background-color: var(--secondary-background-color);
        color: #FF4B4B;
        border: 1px solid #FF4B4B;
        border-right: none;

        padding: 25px 12px;
        border-radius: 10px 0 0 10px;
        text-decoration: none;
        font-size: 15px;
        font-weight: 700;
        cursor: pointer;

        box-shadow: -2px 4px 10px rgba(0,0,0,0.2);
        z-index: 9998;
        transition: all 0.2s ease;

        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        font-family: sans-serif;

        opacity: 0;
        animation: fadeIn 0.5s forwards 1s;
    }
    @keyframes fadeIn {
        to { opacity: 0.8; }
    }
    .floating-replay-btn:hover {
        opacity: 1;
        padding-right: 8px;
        transform: translateX(-2px);
        background-color: #FF4B4B;
        color: white;
        box-shadow: -4px 6px 15px rgba(0,0,0,0.3);
    }
</style>
"""


def handle_video_state(close_param: str, replay_param: str, session_key: str):
    """
    Handles query-param-based video open/close/replay state.

    Args:
        close_param: Query parameter name for closing (e.g. "close_video").
        replay_param: Query parameter name for replaying (e.g. "replay_video").
        session_key: Session state key to track closed state (e.g. "about_intro_closed").

    Returns:
        True if the video overlay should be shown, False otherwise.
    """
    query_params = st.query_params
    action_close = query_params.get(close_param) == "1"
    action_replay = query_params.get(replay_param) == "1"

    if action_close or action_replay:
        st.session_state[session_key] = action_close
        st.query_params.clear()

    if session_key not in st.session_state:
        st.session_state[session_key] = False

    return not st.session_state[session_key]


def render_video_modal(video_url: str, close_param: str, autoplay_muted: bool = True):
    """
    Renders a full-screen video modal overlay with backdrop.

    Args:
        video_url: URL to the video source.
        close_param: Query parameter name for the close action.
        autoplay_muted: If True, video autoplays muted. If False, autoplays with sound.
    """
    muted_attr = "muted" if autoplay_muted else ""

    st.markdown(f"""
{_MODAL_CSS}

<!-- Backdrop Link -->
<a href="?{close_param}=1" target="_self" class="about-backdrop"></a>

<!-- Modal -->
<div class="about-modal">
    <video controls autoplay {muted_attr} playsinline>
      <source src="{video_url}" type="video/mp4" />
      <p>Your browser does not support the video tag.</p>
    </video>
</div>

<!-- Hint -->
<div class="click-hint">Click anywhere to skip</div>
""", unsafe_allow_html=True)


def render_replay_button(replay_param: str):
    """
    Renders a floating "Replay Intro" button on the right edge.

    Args:
        replay_param: Query parameter name for the replay action.
    """
    st.markdown(f"""
{_REPLAY_CSS}
<a href="?{replay_param}=1" target="_self" class="floating-replay-btn">
   Replay Intro
</a>
""", unsafe_allow_html=True)
