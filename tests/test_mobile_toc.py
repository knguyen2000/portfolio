"""Tests for mobile TOC positioning and scroll-to-top button (SPEC Story 4)."""

import re


def _read_projects_page():
    with open("pages/projects.py", encoding="utf-8") as f:
        return f.read()


class TestMobileTocPosition:
    def test_mobile_toc_container_exists(self):
        src = _read_projects_page()
        assert "mobile-toc" in src, "Should have a mobile-specific TOC container"

    def test_mobile_toc_hidden_on_desktop(self):
        src = _read_projects_page()
        assert re.search(r"\.mobile-toc\s*\{[^}]*display:\s*none", src), (
            "mobile-toc should be display:none by default (desktop)"
        )

    def test_mobile_toc_visible_on_small_screens(self):
        src = _read_projects_page()
        assert re.search(
            r"@media.*max-width.*800px.*\.mobile-toc.*display:\s*block",
            src,
            re.DOTALL,
        ), "mobile-toc should be display:block inside <=800px media query"

    def test_desktop_toc_hidden_on_mobile(self):
        src = _read_projects_page()
        assert re.search(
            r"@media.*max-width.*800px.*#toc-container.*display:\s*none",
            src,
            re.DOTALL,
        ), "Desktop #toc-container should be hidden on mobile"

    def test_desktop_toc_still_fixed(self):
        src = _read_projects_page()
        assert re.search(r"#toc-container\s*\{[^}]*position:\s*fixed", src), "Desktop TOC should remain position:fixed"


class TestScrollToTopButton:
    def test_scroll_button_exists(self):
        src = _read_projects_page()
        assert "scroll-top-btn" in src, "Should have a scroll-to-top button element"

    def test_scroll_button_hidden_on_desktop(self):
        src = _read_projects_page()
        assert re.search(r"\.scroll-top-btn\s*\{[^}]*display:\s*none", src), (
            "Scroll button should be hidden by default (desktop)"
        )

    def test_scroll_button_uses_smooth_scroll(self):
        src = _read_projects_page()
        assert "smooth" in src and "scrollTo" in src, "Scroll button should use smooth scrollTo"
