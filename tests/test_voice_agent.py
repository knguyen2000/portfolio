"""Tests for Voice Agent mode (SPEC Story 3)."""

import os


class TestVoiceModeConfig:
    def test_voice_mode_constant_exists(self):
        from config.app_config import MODE_VOICE

        assert MODE_VOICE == "Voice"

    def test_voice_mode_in_available_modes(self):
        from config.app_config import AVAILABLE_MODES, MODE_VOICE

        assert MODE_VOICE in AVAILABLE_MODES

    def test_voice_state_initialized(self):
        with open("state.py", encoding="utf-8") as f:
            content = f.read()
        assert "voice_response" in content

    def test_voice_last_ts_state_initialized(self):
        with open("state.py", encoding="utf-8") as f:
            content = f.read()
        assert "voice_last_ts" in content


class TestVoiceComponent:
    def test_voice_component_file_exists(self):
        assert os.path.isfile("static/voice/index.html")

    def test_has_speech_recognition(self):
        with open("static/voice/index.html", encoding="utf-8") as f:
            content = f.read()
        assert "SpeechRecognition" in content or "webkitSpeechRecognition" in content

    def test_has_speech_synthesis(self):
        with open("static/voice/index.html", encoding="utf-8") as f:
            content = f.read()
        assert "SpeechSynthesisUtterance" in content

    def test_has_stop_command_detection(self):
        with open("static/voice/index.html", encoding="utf-8") as f:
            content = f.read()
        assert "stop" in content.lower()
        assert "shut" in content.lower()

    def test_has_unsupported_browser_fallback(self):
        with open("static/voice/index.html", encoding="utf-8") as f:
            content = f.read()
        assert "not supported" in content.lower() or "unsupported" in content.lower()

    def test_uses_streamlit_component_api(self):
        with open("static/voice/index.html", encoding="utf-8") as f:
            content = f.read()
        assert "Streamlit.setComponentValue" in content
        assert "Streamlit.setComponentReady" in content
        assert "Streamlit.setFrameHeight" in content

    def test_uses_postmessage_not_navigation(self):
        with open("static/voice/index.html", encoding="utf-8") as f:
            content = f.read()
        assert "postMessage" in content
        assert "window.parent.location" not in content


class TestVoiceRouting:
    def test_agent_dispatch_has_voice_handler(self):
        with open("components/agent_dispatch.py", encoding="utf-8") as f:
            content = f.read()
        assert "generate_voice_answer" in content

    def test_app_imports_voice_mode(self):
        with open("app.py", encoding="utf-8") as f:
            content = f.read()
        assert "MODE_VOICE" in content

    def test_app_uses_declare_component(self):
        with open("app.py", encoding="utf-8") as f:
            content = f.read()
        assert "declare_component" in content
        assert "voice_agent" in content

    def test_app_handles_component_value(self):
        with open("app.py", encoding="utf-8") as f:
            content = f.read()
        assert "voice_last_ts" in content
        assert "component_val" in content
