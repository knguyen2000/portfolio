from config.app_config import (
    AVAILABLE_MODES,
    DEFAULT_MODE_INDEX,
    MODE_FILE_BASED,
    MODE_NLA,
    MODE_RLM,
    MODE_VECTOR_RAG,
    MODE_VOICE,
)


def test_all_modes_present():
    assert MODE_FILE_BASED in AVAILABLE_MODES
    assert MODE_VECTOR_RAG in AVAILABLE_MODES
    assert MODE_RLM in AVAILABLE_MODES
    assert MODE_NLA in AVAILABLE_MODES
    assert MODE_VOICE in AVAILABLE_MODES


def test_mode_count():
    assert len(AVAILABLE_MODES) == 5


def test_default_mode_index_in_range():
    assert 0 <= DEFAULT_MODE_INDEX < len(AVAILABLE_MODES)


def test_default_mode_is_vector_rag():
    assert AVAILABLE_MODES[DEFAULT_MODE_INDEX] == MODE_VECTOR_RAG
