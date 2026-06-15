"""Tests for Story 3: sidebar uses inline SVGs instead of Font Awesome CDN."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def _mock_streamlit():
    """Patch Streamlit so ``render_sidebar`` can execute without a running app."""
    mock_st = MagicMock()
    mock_st.sidebar.__enter__ = MagicMock(return_value=mock_st)
    mock_st.sidebar.__exit__ = MagicMock(return_value=False)
    mock_st.query_params.get.return_value = None
    mock_st.session_state.get.return_value = None

    # Collect all HTML fragments passed to st.markdown
    captured: list[str] = []

    def _capture_markdown(html, **kwargs):
        if kwargs.get("unsafe_allow_html"):
            captured.append(html)

    mock_st.markdown.side_effect = _capture_markdown
    mock_st.sidebar.markdown = mock_st.markdown

    with patch.dict("sys.modules", {"streamlit": mock_st}):
        with patch("os.path.exists", return_value=False):
            yield captured, mock_st


def _get_sidebar_html(_mock_streamlit) -> str:
    """Import and call ``render_sidebar``, returning the concatenated HTML."""
    captured, _ = _mock_streamlit
    # Force re-import so the patched streamlit module is used
    import importlib

    import utils.sidebar as sidebar_mod

    importlib.reload(sidebar_mod)
    sidebar_mod.render_sidebar()
    return "\n".join(captured)


# ---------------------------------------------------------------------------
# Story 3 tests
# ---------------------------------------------------------------------------


class TestNoFontAwesomeCDN:
    """The sidebar must not load the Font Awesome stylesheet from cdnjs."""

    def test_no_cdnjs_link(self, _mock_streamlit):
        html = _get_sidebar_html(_mock_streamlit)
        assert "cdnjs.cloudflare.com" not in html, (
            "Sidebar HTML still references the Font Awesome CDN"
        )

    def test_no_font_awesome_i_tags(self, _mock_streamlit):
        html = _get_sidebar_html(_mock_streamlit)
        assert '<i class="fa-' not in html, (
            "Sidebar HTML still uses <i> tags with Font Awesome classes"
        )


class TestInlineSVGs:
    """Each social-link icon must be an inline SVG element."""

    def test_contains_svg_elements(self, _mock_streamlit):
        html = _get_sidebar_html(_mock_streamlit)
        assert html.count("<svg ") >= 4, (
            f"Expected at least 4 inline <svg> elements, found {html.count('<svg ')}"
        )

    def test_linkedin_svg_present(self, _mock_streamlit):
        html = _get_sidebar_html(_mock_streamlit)
        # LinkedIn SVG has viewBox 0 0 448 512
        assert 'viewBox="0 0 448 512"' in html

    def test_github_svg_present(self, _mock_streamlit):
        html = _get_sidebar_html(_mock_streamlit)
        # GitHub SVG has viewBox 0 0 496 512
        assert 'viewBox="0 0 496 512"' in html

    def test_envelope_svg_present(self, _mock_streamlit):
        html = _get_sidebar_html(_mock_streamlit)
        # Envelope SVG has viewBox 0 0 512 512
        assert 'viewBox="0 0 512 512"' in html

    def test_address_card_svg_present(self, _mock_streamlit):
        html = _get_sidebar_html(_mock_streamlit)
        # Address Card SVG has viewBox 0 0 576 512
        assert 'viewBox="0 0 576 512"' in html

    def test_svgs_use_current_color(self, _mock_streamlit):
        html = _get_sidebar_html(_mock_streamlit)
        assert html.count('fill="currentColor"') >= 4, (
            "All 4 SVG icons should use fill='currentColor'"
        )

    def test_svgs_have_correct_dimensions(self, _mock_streamlit):
        html = _get_sidebar_html(_mock_streamlit)
        assert html.count('width="28"') >= 4
        assert html.count('height="28"') >= 4
