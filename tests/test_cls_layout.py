"""
Tests that CSS layout reservation is in place to prevent CLS (Cumulative Layout Shift).
"""

import re


def test_main_content_has_min_height():
    """The main content container must have min-height to reserve space before hydration."""
    with open("styles.py", encoding="utf-8") as f:
        css = f.read()
    assert "min-height" in css, "styles.py should set min-height on the main content area"


def test_font_display_swap():
    """Any @font-face or font loading must use font-display: swap to prevent FOIT."""
    with open("styles.py", encoding="utf-8") as f:
        css = f.read()
    # If there's a @font-face declaration, it must include font-display: swap
    if "@font-face" in css:
        assert "font-display: swap" in css or "font-display:swap" in css, (
            "@font-face declarations must include font-display: swap"
        )
    # Even without @font-face, we should have a global font-display rule
    assert re.search(r"font-display\s*:\s*swap", css), (
        "styles.py should include font-display: swap for web fonts"
    )
